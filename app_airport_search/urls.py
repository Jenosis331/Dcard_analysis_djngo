from django.urls import path
from app_airport_search import views

app_name = 'app_airport_search'

urlpatterns = [
    path('', views.home, name='home'),
    path('api/', views.api_search, name='api_search'),
]
