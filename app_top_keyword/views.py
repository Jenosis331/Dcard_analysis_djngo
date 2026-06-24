from django.shortcuts import render
from django.http import  JsonResponse
import pandas as pd
import os
from website_configs.categories import CATEGORIES as CATEGORIES

# render渲染網頁
def home(request):
    return render(request, 'app_top_keyword/home.html', {'categories': CATEGORIES})

# read from database
import sqlite3
from django.conf import settings

db_path = os.path.join(settings.BASE_DIR, 'db.sqlite3')
conn = sqlite3.connect(db_path)
df_topkey = pd.read_sql_query('SELECT * FROM dcard_data3_tokenpos_all', conn)
conn.close()

# prepare data
data={}
for idx, row in df_topkey.iterrows():
    data[row['category']] = eval(row['top_keys'])

# We don't use it anymore, so delete it to save memory.
del df_topkey

# POST: csrf_exempt should be used
# 指定這一支程式忽略csrf驗證
from django.views.decorators.csrf import csrf_exempt
@csrf_exempt
def api_get_cate_topword(request):
    cate = request.POST.get('news_category')
    #cate = request.GET['news_category'] # this command also works.
    topk = request.POST.get('topk')
    topk = int(topk)
    print(cate, topk)

    chart_data, wf_pairs = get_category_topword(cate, topk)
    response = {'chart_data': chart_data,
         'wf_pairs': wf_pairs,
         }
    print(response)
    return JsonResponse(response)

def get_category_topword(cate, topk=10):
    wf_pairs = data.get(cate, [])[0:topk]
    words = [w for w, f in wf_pairs]
    freqs = [f for w, f in wf_pairs]
    chart_data = {
        "category": cate,
        "labels": words,
        "values": freqs}
    return chart_data, wf_pairs

print("app_top_keywords--類別熱門關鍵字載入成功!")
