from django.shortcuts import render
import pandas as pd
import os

from django.http import JsonResponse
from django.views.decorators.csrf import csrf_exempt

'''
the format of data:
{'政治': [('韓國瑜', 6344),
  ('蔡英文', 2114),
  ('賴清德', 1480),
  ...
  }
'''

# load data
def load_data_topPerson():
    # read from database
    import sqlite3
    from django.conf import settings
    db_path = os.path.join(settings.BASE_DIR, 'db.sqlite3')
    conn = sqlite3.connect(db_path)
    df_topPerson = pd.read_sql_query('SELECT * FROM dcard_top_person', conn)
    conn.close()

    # refresh data
    global data # make data global. It can be used everywhere.
    data = {}
    for idx, row in df_topPerson.iterrows():
        data[row['category']] = eval(row['top_keys'])


from website_configs.categories import CATEGORIES as CATEGORIES


# Load data first when starting server.
load_data_topPerson()


def home(request):
    return render(request, 'app_top_person/home.html', {'categories': CATEGORIES})

# csrf_exempt is used for POST
# 單獨指定這一支程式忽略csrf驗證
@csrf_exempt
def api_get_topPerson(request):

    # chart_data, wf_pairs = get_category_topkey("科技", 10) #先做簡單的測試

    cate = request.POST.get('news_category')
    topk = request.POST.get('topk')
    topk = int(topk)
    #print(cate, topk)

    chart_data, wf_pairs = get_category_topPerson(cate, topk)

    # print(chart_data)
    response = {'chart_data':  chart_data,
                'wf_pairs': wf_pairs,
                }
    return JsonResponse(response)


def get_category_topPerson(cate, topk):
    wf_pairs = data.get(cate, [])[0:topk]
    words = [w for w, f in wf_pairs]
    freqs = [f for w, f in wf_pairs]
    chart_data = {
        "category": cate,
        "labels": words,
        "values": freqs}
    return chart_data, wf_pairs  # chart_data is for charting


print("app_news_analysis--類別熱門人物載入成功!")


