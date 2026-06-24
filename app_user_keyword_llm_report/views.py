from django.shortcuts import render
from django.views.decorators.csrf import csrf_exempt
from django.http import JsonResponse


from app_user_keyword.views import filter_dataFrame, api_get_top_userkey
from app_user_keyword_sentiment.views import api_get_userkey_sentiment
import json
import os
from pathlib import Path
from dotenv import load_dotenv
from openai import OpenAI

from website_configs.categories import CATEGORIES as CATEGORIES
# pip install openai dotenv 


BASE_DIR = Path(__file__).resolve().parent.parent
load_dotenv(BASE_DIR / ".env")

api_key = os.getenv("GEMINI_API_KEY")

if not api_key:
    raise ValueError(f"GEMINI_API_KEY not found. env path = {BASE_DIR / '.env'}")

# 使用 REST API 直接呼叫
url = "https://generativelanguage.googleapis.com/v1beta/openai/"


client = OpenAI(
    base_url=url,
    api_key=api_key,
)

model_name = "gemini-3.1-flash-lite" # 或替換成你使用的 Gemini 模型

# For the key association analysis
def home(request):
    return render(request, 'app_user_keyword_llm_report/home.html', {'categories': CATEGORIES})


# Get userkey data including occurrence, time frequency, sentiment analysis, etc. from internal modules, and return the combined data as a dictionary
# 取得使用者輸入的關鍵字，並從內部模組取得相關的分析資料，最後將資料合併成一個字典返回
def get_userkey_data(request):
    userkey = request.POST.get('userkey')
    cate = request.POST['cate'] # This is an alternative way to get POST data.
    cond = request.POST.get('cond')
    weeks = int(request.POST.get('weeks'))
    key = userkey.split()
    
    df_query = filter_dataFrame(key, cond, cate,weeks)

    # if df_query is empty, return an error message
    if len(df_query) == 0:
        return {'error': 'No results found for the given keywords.'}
    
   
    # (1)從內部取得聲量分布資料 get frequency data from internal module
    try:
        response_from_sentiment = api_get_userkey_sentiment(request)
        response_from_sentiment = response_from_sentiment.content.decode('utf-8') # 取得的格式是bytes，必須Decode the response content to a string
        response_from_sentiment = json.loads(response_from_sentiment) # 將字串轉換為字典
        

    except Exception as e:
        print(f"Error calling api_get_userkey_sentiment: {e}")
        return{'error': 'Failed to get sentiment data.'}


    # (2)從內部取得聲量分布資料 get frequency data from internal module
    try:
        response_from_userkeyword = api_get_top_userkey(request)
        response_from_userkeyword = response_from_userkeyword.content.decode('utf-8') # 取得的格式是bytes，必須Decode the response content to a string
        response_from_userkeyword = json.loads(response_from_userkeyword) # 將字串轉換為字典

    except Exception as e:
        print(f"Error calling api_get_top_userkey: {e}")
        return {'error': 'Failed to get keyword frequency data.'}
   
    return response_from_userkeyword, response_from_sentiment
    # return {**response_from_userkeyword, **response_from_sentiment}


# API endpoint for getting userkey data including occurrence, time frequency, sentiment analysis, etc. from internal modules, and return the combined data as a dictionary
# 取得使用者輸入的關鍵字，並從內部模組取得相關的分析資料，最後將資料合併成一個字典返回
@csrf_exempt
def api_get_userkey_data(request):
    
    result = get_userkey_data(request)    

    # Check if result is an error dictionary
    if isinstance(result, dict) and 'error' in result:
        return JsonResponse(result)
    
    response_from_userkeyword, response_from_sentiment = result 
    # Combine dictionaries correctly
    combined_response = {**response_from_userkeyword, **response_from_sentiment}
    return JsonResponse(combined_response)

# API endpoint for getting LLM report
# 取得使用者輸入的關鍵字，從內部模組取得相關的分析資料，然後將資料整理成提示詞，最後呼叫AI大型模型的API來生成分析報告，並將報告內容返回
@csrf_exempt
def api_get_userkey_llm_report(request):
    
    result = get_userkey_data(request)    

    # Check if result is an error dictionary
    if isinstance(result, dict) and 'error' in result:
        return JsonResponse(result)
    
    response_from_userkeyword, response_from_sentiment = result
    
    userkey = request.POST.get('userkey')
    key_occurrence_cat = response_from_userkeyword['key_occurrence_cat']
    key_time_freq = response_from_userkeyword['key_time_freq']
    key_freq_cat = response_from_userkeyword['key_freq_cat']    
    
    sentiCount = response_from_sentiment['sentiCount']
    line_data_pos = response_from_sentiment['data_pos']
    line_data_neg = response_from_sentiment['data_neg']
        
    # print(response1_data)
    # 系統提示指令
    system_prompt = f"你是一位資深的網路數據與輿情分析專家。以下是有關於[{userkey}]的網路聲量資訊，請為我做一份至少500字的詳細專業分析報告。請務必使用繁體中文，並使用 Markdown 語法進行排版。"

    # 都出所有的輸入提示詞
    prompt = f'''根據以下資料，請幫我撰寫一份大約500字的詳細專業分析報告。

### (1) 聲量分析
以下是熱門程度（多篇新聞報導提到）：
{key_occurrence_cat}

以下是時間趨勢（過去幾天的報導數量變化）：
{key_time_freq}

### (2) 情緒分析
以下是情緒分析比率（正面負面的分布情況）：
{sentiCount}

以下是情緒變化的時間趨勢（過去幾天的正負面報導數量變化）：
- 正面情緒趨勢：{line_data_pos}
- 負面情緒趨勢：{line_data_neg}

### (3) 輸出內容要求
分析的內容包括但不限於以下幾個方面：
1. 標題
2. 摘要
3. 關鍵字
4. 內容
5. 建議
6. 總結
'''
    print(prompt)
    
    
    # 這裡你可以呼叫ChatGPT的API來生成報告，或其他任何AI大型模型的API
    try:
        response = client.chat.completions.create(
            model=model_name,
            messages=[
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": prompt}
            ],
            timeout=100
        )
        report_content = response.choices[0].message.content
        print(report_content)
    except Exception as e:
        print("Error:", str(e))
        return JsonResponse({'error': 'Failed to generate report. Please try again later.'})
    
    # 取得AI生成的報告
    response_report = {
        'report': report_content
        #'report': markdown.markdown(report_content)
    }
    
    # Combine dictionaries correctly
    return JsonResponse(response_report)
    
print("app_user_keyword_llm_report was loaded!")
