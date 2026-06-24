from django.http import JsonResponse
from django.shortcuts import render
import pandas as pd
import os
from datetime import datetime, timedelta
from django.views.decorators.csrf import csrf_exempt
import app_user_keyword.views as userkeyword_views
from app_user_keyword.views import filter_dataFrame
from website_configs.categories import CATEGORIES as CATEGORIES
# Create your views here.

def load_df_data():
    global df
    df = userkeyword_views.df

load_df_data()

def home(request):
    return render(request, 'app_user_keyword_sentiment/home.html', {'categories': CATEGORIES})
 
# GET: csrf_exempt is not necessary
# POST: csrf_exempt should be used
@csrf_exempt
def api_get_userkey_sentiment(request):

    userkey = request.POST.get('userkey')
    cate = request.POST.get('cate')
    cond = request.POST.get('cond')
    weeks = int(request.POST.get('weeks'))

    query_keywords = userkey.split()
    # Proceed filtering
    df_query = filter_dataFrame(query_keywords, cond, cate, weeks)
    print(len(df_query))
    
    # if df_query is empty, return an error message
    if len(df_query) == 0:
        return JsonResponse({'error': 'No results found for the given keywords.'})
    
    sentiCount, sentiPercnt = get_article_sentiment(df_query)

    if weeks <= 4:
        freq_type = 'D'
    else:
        freq_type = 'W'

    line_data_pos = get_daily_basis_sentiment_count(df_query, sentiment_type='pos', freq_type=freq_type)
    line_data_neg = get_daily_basis_sentiment_count(df_query, sentiment_type='neg', freq_type=freq_type)

    response = {
        'sentiCount': sentiCount,
        'data_pos':line_data_pos,
        'data_neg':line_data_neg,
    }
    return JsonResponse(response)

def get_article_sentiment(df_query):
    sentiCount = {'Positive': 0, 'Negative': 0, 'Neutral': 0}
    sentiPercnt = {'Positive': 0, 'Negative': 0, 'Neutral': 0}
    numberOfArticle = len(df_query)
    for senti in df_query.sentiment:
        # determine sentimental polarity
        if float(senti) >= 0.6:
            sentiCount['Positive'] += 1
        elif float(senti) <= 0.4:
            sentiCount['Negative'] += 1
        else:
            sentiCount['Neutral'] += 1
    for polar in sentiCount :
        try:
            sentiPercnt[polar]=int(sentiCount[polar]/numberOfArticle*100)
        except:
            sentiPercnt[polar] = 0 # 若分母 numberOfArticle=0會報錯
    return sentiCount, sentiPercnt


def get_daily_basis_sentiment_count(df_query, sentiment_type='pos', freq_type='D'):

    # 自訂正負向中立的標準，sentiment score是機率值，介於0~1之間
    # Using lambda to determine if an article is postive or not.
    if sentiment_type == 'pos':
        lambda_function = lambda senti: 1 if senti >= 0.6 else 0 #大於0.6為正向 
    elif sentiment_type == 'neg':
        lambda_function = lambda senti: 1 if senti <= 0.4 else 0 #小於0.4為負向
    elif sentiment_type == 'neutral':
        lambda_function = lambda senti: 1 if senti > 0.4 & senti < 0.4 else 0 #介於中間為中立
    else:
        return None 
        
    freq_df = pd.DataFrame({'date_index': pd.to_datetime(df_query.article_dates),
                             'frequency': [lambda_function(senti) for senti in df_query.sentiment]})
    # Group rows by the date to the daily number of articles. 加總合併同一天新聞，篇數就被計算好了
    freq_df_group = freq_df.groupby(pd.Grouper(key='date_index',freq=freq_type)).sum()
    
    # 'date_index'為index(索引)，將其變成欄位名稱，inplace=True表示原始檔案會被異動
    freq_df_group.reset_index(inplace=True)
    
    # x,y，用於畫趨勢線圖
    xy_line_data = [{'x':date.strftime('%Y-%m-%d'),'y':freq} for date, freq in zip(freq_df_group.date_index,freq_df_group.frequency)]
    return xy_line_data


print("app_userkey_sentiment was loaded!")
