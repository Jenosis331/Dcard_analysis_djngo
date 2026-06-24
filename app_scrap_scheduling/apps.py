from django.apps import AppConfig
try:
    from celery import shared_task
except ImportError:
    def shared_task(func):
        return func
import subprocess
import sys
import os

class AppUserKeywordConfig(AppConfig):
    default_auto_field = "django.db.models.BigAutoField"
    name = "app_scrap_scheduling"




@shared_task
def run_dcard_crawler():
    crawler_path = r"C:\Users\Chen\Desktop\proj\get_web\get_dcard_by_keyword_v3.py"

    result = subprocess.run(
        [sys.executable, crawler_path],
        capture_output=True,
        text=True,
        cwd=os.path.dirname(crawler_path)
    )

    return {
        "returncode": result.returncode,
        "stdout": result.stdout,
        "stderr": result.stderr,
    }