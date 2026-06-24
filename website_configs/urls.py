from django.contrib import admin
from django.urls import path
from django.urls import include
from website_configs import views

urlpatterns = [
    # 首頁 (Homepage)
    path('', views.home, name='home'),

    # top keywords
    path('topword/', include('app_top_keyword.urls')),
    # app top persons
    path('topperson/', include('app_top_person.urls')),
    # user keyword analysis
    path('userkeyword/', include('app_user_keyword.urls')),
    # app shih chung chen
    path('kop/', include('app_kop.urls')),
    # full text search and associated keyword display
    path('userkeyword_assoc/', include('app_user_keyword_association.urls')), 
    # user keyword sentiment
    path('userkeyword_sentiment/', include('app_user_keyword_sentiment.urls')),
    #gemini api分析'user_keyword_sentiment'
    path('user_keyword_llm_report/', include('app_user_keyword_llm_report.urls')),
    # admin 後台資料庫管理
    path('admin/', admin.site.urls),

    path('airport/', include('app_airport_analysis.urls')),
    path('airport_search/', include('app_airport_search.urls')),
    # Dcard 留言情緒分析
    path('comment_sentiment/', include('app_comment_sentiment.urls')),
    # 自助爬蟲
    path('scrap_scheduling/', include('app_scrap_scheduling.urls')),
    # Dcard輿情智能代理
    path('agent/', include('app_poa_langchain.urls')),
]
