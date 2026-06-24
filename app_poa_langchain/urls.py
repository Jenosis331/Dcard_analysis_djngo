from django.urls import path
from app_poa_langchain import views

app_name = 'app_poa_langchain'

urlpatterns = [
    path('chat/', views.chat_view, name='chat_view'),
]
