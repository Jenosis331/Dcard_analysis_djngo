from django.shortcuts import render
import pandas as pd
import os
from django.http import JsonResponse
from django.views.decorators.csrf import csrf_exempt
from datetime import datetime, timedelta
from website_configs.categories import CATEGORIES as CATEGORIES

# (1) we can load data using read_csv()
# global variable
# df = pd.read_csv('dataset/news_dataset_preprocessed_for_django.csv', sep='|')

# (2) we can load data using reload_df_data() function
def load_df_data():
    # df is a global variable
    global  df
    base_dir = os.path.dirname(os.path.abspath(__file__))
    project_root = os.path.dirname(os.path.dirname(base_dir))
    csv_path = os.path.join(project_root, 'app_user_keyword', 'dataset', 'dcard_data2_process_all.csv')
    df = pd.read_csv(csv_path, sep='|')

# We should reload df when necessary
load_df_data() 

# hoem page
def home(request):
    return render(request, 'app_user_keyword/home.html', {'categories': CATEGORIES})


# When POST is used, make this function be exempted from the csrf 
@csrf_exempt
def api_get_top_userkey(request):
    # (1) get keywords, category, condition, and weeks passed from frontend
    userkey = request.POST.get('userkey')
    cate = request.POST.get('cate')
    cond = request.POST.get('cond')
    weeks = int(request.POST.get('weeks'))
    key = userkey.split()
    
    # (2) make df_query global, so it can be used by other functions
    global  df_query 

    # (3) filter dataframe
    df_query = filter_dataFrame(key, cond, cate, weeks)
    #print(df_query)

    # (4) get frequency data
    key_freq_cat, key_occurrence_cat = count_keyword(df_query, key)
    #print(key_occurrence_cat)
    
    # (5) get line chart data
    # key_time_freq = [
    # '{"x": "2019-03-07", "y": 2}',
    # '{"x": "2019-03-08", "y": 2}',
    # '{"x": "2019-03-09", "y": 13}']
    key_time_freq = get_keyword_time_based_freq(df_query)

    # (6) response all data to frontend home page
    response = {
    'key_occurrence_cat': key_occurrence_cat,
    'key_freq_cat': key_freq_cat,
    'key_time_freq': key_time_freq, }

    return JsonResponse(response)


# Searching keywords from "content" column
# Here this function uses df.content column, while filter_dataFrame() uses df.tokens_v2
def filter_dataFrame(user_keywords, cond, cate, weeks):

    # end date: the date of the latest record of news
    end_date = df.article_dates.max()

    # start date
    start_date = (datetime.strptime(end_date, '%Y/%m/%d').date() - timedelta(weeks=weeks)).strftime('%Y/%m/%d')

    # (1) proceed filtering: a duration of a period of time
    # 期間條件
    period_condition = (df.article_dates >= start_date) & (df.article_dates <= end_date)
    
    # (2) proceed filtering: news category
    # 新聞類別條件
    if (cate == "全部"):
        condition = period_condition  # "全部"類別不必過濾新聞種類
    else:
        # category新聞類別條件
        condition = period_condition & (df.category == cate)

    # (3) proceed filtering: keywords 
    # and or 條件
    if (cond == 'and'):
        # query keywords condition使用者輸入關鍵字條件and
        condition = condition & df.content.apply(lambda text: all((qk in str(text)) for qk in user_keywords)) #寫法:all()
    elif (cond == 'or'):
        # query keywords condition使用者輸入關鍵字條件 #寫法:any()
        condition = condition & df.content.apply(lambda text: any((qk in str(text)) for qk in user_keywords))
    # condiction is a list of True or False boolean value
    df_query = df[condition]

    return df_query

# For the df_query, count the occurence and frequency for every category:
# (1) cate_occurence={}  number of pieces containing the keywords
# (2) cate_freq={}       number of times the keywords were mentioned

news_categories = CATEGORIES

def count_keyword(query_df, user_keywords):
    cate_occurence={}
    cate_freq={}

    for cate in news_categories:
        cate_occurence[cate]=0
        cate_freq[cate]=0

    for idx, row in query_df.iterrows():
        # count number of news
        if row.category in cate_occurence:
            cate_occurence[row.category] += 1
        cate_occurence['全部'] += 1
        
        # count user keyword frequency by checking every word in tokens_v2
        tokens = eval(row.tokens_v2)
        freq =  len([word for word in tokens if (word in user_keywords)])
        if row.category in cate_freq:
            cate_freq[row.category] += freq
        cate_freq['全部'] += freq
        
    return cate_freq, cate_occurence

def get_keyword_time_based_freq(df_query):
    date_samples = df_query.article_dates
    query_freq = pd.DataFrame({'date_index': pd.to_datetime(date_samples), 'freq': [1 for _ in range(len(df_query))]})
    data = query_freq.groupby(pd.Grouper(key='date_index', freq='D')).sum()
    time_data = []
    for i, idx in enumerate(data.index):
        row = {'x': idx.strftime('%Y-%m-%d'), 'y': int(data.iloc[i].freq)}
        time_data.append(row)
    return time_data

print("app_user_keyword was loaded!")
