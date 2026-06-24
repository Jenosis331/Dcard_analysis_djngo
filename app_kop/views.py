from django.http import JsonResponse
from django.shortcuts import render
from django.views.decorators.csrf import csrf_exempt
import pandas as pd
import os


def load_data_kop():
    # Read data from csv file
    base_dir = os.path.dirname(os.path.abspath(__file__))
    csv_path = os.path.join(base_dir, 'dataset', 'KoP_data.csv')
    df_data = pd.read_csv(csv_path, sep=",")
    global data
    data = {}
    for idx, row in df_data.iterrows():
        data[row['name']] = eval(row['value'])
    del df_data
    return data


# load data
load_data_kop()

def home(request):
    print("home was called!")
    summary = data['vos_summary']
    category_data = data['vos_article_count_by_category']
    context = {
    "article_count_for_django": data['article_count_for_django'],
    "freqByDate": data['vos_frequency_date_based'],
    "freqByCate": category_data['article_count'],
    "category": category_data['category'],
    "num_occurrence": summary['num_occurrence'],
    "num_frequency": summary['num_frequency'],
    "photo": summary['photo_url'],
    }
    return render(request, "app_kop/home.html", context)

# csrf_exempt is used for POST
# 單獨指定這一支程式忽略csrf驗證
@csrf_exempt
def api_chen_shih_chung(request):
  print("api_chen_shih_chung was called!")
  return JsonResponse(data)


print("app_kop was loaded!")


# get the frequency of each category
# 讓前端用表格方式顯示 (使用Django Template語法)
"""
          <tbody>
            {% for category, count in article_count_for_django %}
            <tr>
              <td>{{ category }}</td>
              <td>{{ count }}</td>
            </tr>
            {% endfor %}
          </tbody>
"""

