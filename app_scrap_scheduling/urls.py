from django.urls import path
from . import views

app_name = "app_scrap_scheduling"

urlpatterns = [
    path("", views.scheduler, name="scheduler"),
    path("api/scheduler/status/", views.api_scheduler_status, name="api_scheduler_status"),
    path("api/scheduler/start/", views.api_scheduler_start, name="api_scheduler_start"),
    path("api/scheduler/stop/", views.api_scheduler_stop, name="api_scheduler_stop"),
    path("api/scheduler/history/", views.api_scheduler_history, name="api_scheduler_history"),
    path("api/run-task/", views.api_run_task, name="api_run_task"),
    path("api/keywords/", views.api_keywords, name="api_keywords"),
    path("api/crawler-mode/", views.api_crawler_mode, name="api_crawler_mode"),
    path("api/download-files/", views.api_download_files, name="api_download_files"),
    path("api/delete-file/", views.api_delete_file, name="api_delete_file"),
    path("api/delete-all-files/", views.api_delete_all_files, name="api_delete_all_files"),
]