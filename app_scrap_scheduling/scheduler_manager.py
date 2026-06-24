from apscheduler.schedulers.background import BackgroundScheduler
from django_apscheduler.jobstores import DjangoJobStore
import subprocess
import datetime
import sys
import os
import json
import uuid
import threading
from django.conf import settings

# pip install django-apscheduler

scheduler = BackgroundScheduler()
scheduler.add_jobstore(DjangoJobStore(), "default")

def load_crawler_config():
    path = os.path.join(settings.BASE_DIR, "app_scrap_scheduling", "crawler_keywords.json")
    default_config = {
        "keywords": ["tech_job", "job", "talk", "youtuber", "trending"],
        "mode": "category"
    }
    if not os.path.exists(path):
        return default_config
    try:
        with open(path, "r", encoding="utf-8") as f:
            data = json.load(f)
            if "keywords" not in data:
                data["keywords"] = default_config["keywords"]
            if "mode" not in data:
                data["mode"] = default_config["mode"]
            return data
    except Exception:
        return default_config

def load_keywords():
    config = load_crawler_config()
    return config["keywords"]

def run_crawler_job():
    config = load_crawler_config()
    mode = config.get("mode", "category")
    keywords = config.get("keywords", [])
    mode_text = "關鍵字搜尋" if mode == "keyword" else "看板爬取"
    
    if mode == "keyword":
        crawler_script = "get_dcard_by_keyword.py"
    else:
        crawler_script = "get_dcard_by_category.py"
        
    crawler_path = os.path.join(settings.BASE_DIR, "app_scrap_scheduling", crawler_script)
    
    run_id = start_execution_log(f"自動排程任務 ({mode_text}模式)，目標：{', '.join(keywords)}")
    try:
        env = os.environ.copy()
        env['PYTHONIOENCODING'] = 'utf-8'
        result = subprocess.run([sys.executable, crawler_path] + keywords, capture_output=True, encoding='utf-8', env=env)
        if result.returncode == 0:
            end_execution_log(run_id, "success")
        else:
            err = result.stderr.strip() if result.stderr else f"Exit code: {result.returncode}"
            end_execution_log(run_id, "failed", error_msg=err[:500])
    except Exception as e:
        end_execution_log(run_id, "failed", error_msg=str(e)[:500])

def run_analyzer_job():
    subprocess.call([sys.executable, "manage.py", "analyze_sentiment"])


# 啟動排程器 (背景執行)
try:
    if not scheduler.running:
        scheduler.start()
except Exception as e:
    print(f"啟動排程器時發生錯誤: {e}")

def start_jobs():
    if not scheduler.get_job('crawler_job'):
        
        ## 每天凌晨2:00執行爬蟲任務
        scheduler.add_job(
            run_crawler_job,
            'cron',
            hour=2,
            minute=0,
            id='crawler_job',
            replace_existing=True,
            misfire_grace_time=3600
        )
        
        # 每小時執行一次爬蟲任務
        # scheduler.add_job(
        #     run_crawler_job,
        #     'interval',
        #     hours=1,
        #     id='crawler_job',
        #     replace_existing=True,
        #     misfire_grace_time=3600
        # )
    if not scheduler.get_job('analyzer_job'):
        scheduler.add_job(
            run_analyzer_job,
            'cron',
            hour=2,
            minute=0,
            id='analyzer_job',
            replace_existing=True,
            misfire_grace_time=3600
        )

def stop_jobs():
    if scheduler.get_job('crawler_job'):
        scheduler.remove_job('crawler_job')
    if scheduler.get_job('analyzer_job'):
        scheduler.remove_job('analyzer_job')

def get_job_status():
    # 獲取所有任務的詳細資訊
    jobs = []

    def format_job_time(job, attr):
        timestamp = getattr(job, attr, None)
        return timestamp.strftime('%Y-%m-%d %H:%M:%S') if timestamp else None
    
    crawler_job = scheduler.get_job('crawler_job')
    # analyzer_job = scheduler.get_job('analyzer_job')
    
    if crawler_job:
        config = load_crawler_config()
        mode = config.get("mode", "category")
        mode_text = "關鍵字搜尋" if mode == "keyword" else "看板爬取"
        jobs.append({
            'name': 'Dcard 爬蟲任務',
            'description': f'自動 Dcard 爬蟲任務 ({mode_text}模式)',
            'schedule': '每天 02:00',
            'status': 'running' if crawler_job.next_run_time else 'stopped',
            'last_run': format_job_time(crawler_job, 'last_run_time'),
            'next_run': format_job_time(crawler_job, 'next_run_time')
        })
    
    # if analyzer_job:
    #     jobs.append({
    #         'name': '情緒分析任務',
    #         'description': '每天凌晨2:00執行情緒分析',
    #         'schedule': '每天 02:00',
    #         'status': 'running' if analyzer_job.next_run_time else 'stopped',
    #         'last_run': format_job_time(analyzer_job, 'last_run_time'),
    #         'next_run': format_job_time(analyzer_job, 'next_run_time')
    #     })
    
    return {
        'scheduled': len(jobs) > 0,
        'jobs': jobs,
        'timestamp': datetime.datetime.now().strftime('%Y-%m-%d %H:%M:%S')
    }

# 新增：獲取任務執行歷史
def get_execution_history():
    return {
        'history': _load_history()
    }


history_lock = threading.Lock()

def _get_history_file_path():
    path = os.path.join(settings.BASE_DIR, "data", "crawler_history.json")
    os.makedirs(os.path.dirname(path), exist_ok=True)
    return path

def _load_history():
    path = _get_history_file_path()
    if not os.path.exists(path):
        return []
    try:
        with open(path, "r", encoding="utf-8") as f:
            return json.load(f)
    except Exception:
        return []

def _save_history(history):
    path = _get_history_file_path()
    try:
        with open(path, "w", encoding="utf-8") as f:
            json.dump(history, f, ensure_ascii=False, indent=2)
    except Exception as e:
        print(f"Error saving history: {e}")

def start_execution_log(task_name):
    with history_lock:
        history = _load_history()
        run_id = str(uuid.uuid4())
        now = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        record = {
            "run_id": run_id,
            "task": task_name,
            "start_time": now,
            "end_time": None,
            "status": "running",
            "duration": None,
            "error_msg": None
        }
        history.insert(0, record)
        _save_history(history[:50])
        return run_id

def end_execution_log(run_id, status, error_msg=None):
    with history_lock:
        history = _load_history()
        now = datetime.datetime.now()
        now_str = now.strftime("%Y-%m-%d %H:%M:%S")
        
        for record in history:
            if record.get("run_id") == run_id:
                record["status"] = status
                record["end_time"] = now_str
                record["error_msg"] = error_msg
                
                try:
                    start_dt = datetime.datetime.strptime(record["start_time"], "%Y-%m-%d %H:%M:%S")
                    diff = now - start_dt
                    seconds = int(diff.total_seconds())
                    
                    if seconds < 60:
                        record["duration"] = f"{seconds}秒"
                    else:
                        minutes = seconds // 60
                        sec = seconds % 60
                        record["duration"] = f"{minutes}分{sec}秒"
                except Exception:
                    record["duration"] = "未知"
                break
        _save_history(history)

def run_manual_crawler(crawler_path, keywords, mode_text):
    run_id = start_execution_log(f"手動爬蟲任務 ({mode_text}模式)，目標：{', '.join(keywords)}")
    try:
        env = os.environ.copy()
        env['PYTHONIOENCODING'] = 'utf-8'
        result = subprocess.run([sys.executable, crawler_path] + keywords, capture_output=True, encoding='utf-8', env=env)
        if result.returncode == 0:
            end_execution_log(run_id, "success")
        else:
            err = result.stderr.strip() if result.stderr else f"Exit code: {result.returncode}"
            end_execution_log(run_id, "failed", error_msg=err[:500])
    except Exception as e:
        end_execution_log(run_id, "failed", error_msg=str(e)[:500])
