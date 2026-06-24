from django.urls import path
from app_comment_sentiment import views

app_name = "app_comment_sentiment"

urlpatterns = [
    path('', views.home, name='home'),
]
