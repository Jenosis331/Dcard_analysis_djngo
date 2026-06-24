from django.urls import path
from app_airport_analysis import views

app_name = 'app_airport_analysis'

urlpatterns = [
    path('', views.home_overview, name='home_overview'),
    path('trend/', views.home_trend, name='home_trend'),
    path('deepdive/', views.home_deepdive, name='home_deepdive'),
    path('api/', views.api_get_airport_analysis, name='api'),
    path('set_theme/', views.set_theme, name='set_theme'),
    path('theme_manager/', views.theme_manager, name='theme_manager'),
    path('theme_manager/api/import/', views.api_theme_import, name='api_theme_import'),
    path('theme_manager/api/progress/', views.api_theme_progress, name='api_theme_progress'),
]
