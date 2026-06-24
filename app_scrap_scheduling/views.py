from django.shortcuts import render
from django.http import JsonResponse, FileResponse, HttpResponse
from django.views.decorators.http import require_http_methods
from django.views.decorators.csrf import csrf_exempt
from django.db.models import Q
import subprocess
import sys
import os
import json
import re
from django.conf import settings

from . import scheduler_manager

def _get_keywords_file_path():
    return os.path.join(settings.BASE_DIR, "app_scrap_scheduling", "crawler_keywords.json")

def load_crawler_config():
    path = _get_keywords_file_path()
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

def save_crawler_config(config):
    path = _get_keywords_file_path()
    try:
        with open(path, "w", encoding="utf-8") as f:
            json.dump(config, f, ensure_ascii=False, indent=2)
        return True
    except Exception:
        return False

def load_keywords():
    config = load_crawler_config()
    return config["keywords"]

def save_keywords(keywords):
    config = load_crawler_config()
    config["keywords"] = keywords
    return save_crawler_config(config)

@csrf_exempt
@require_http_methods(["GET", "POST"])
def api_keywords(request):
    if request.method == "GET":
        kws = load_keywords()
        return JsonResponse({"status": "success", "keywords": kws})
    
    elif request.method == "POST":
        raw_keywords = request.POST.get("keywords", "").strip()
        if not raw_keywords:
            return JsonResponse({"status": "error", "message": "關鍵字不能為空"}, status=400)
        
        kws = [k.strip() for k in re.split(r'[,\s，]+', raw_keywords) if k.strip()]
        if not kws:
            return JsonResponse({"status": "error", "message": "關鍵字不能為空"}, status=400)
        
        if save_keywords(kws):
            return JsonResponse({"status": "success", "message": "關鍵字已成功儲存至 crawler_keywords.json", "keywords": kws})
        else:
            return JsonResponse({"status": "error", "message": "儲存設定時發生錯誤"}, status=500)


@csrf_exempt
@require_http_methods(["GET", "POST"])
def api_crawler_mode(request):
    if request.method == "GET":
        config = load_crawler_config()
        return JsonResponse({"status": "success", "mode": config.get("mode", "category")})
    
    elif request.method == "POST":
        mode = request.POST.get("mode", "").strip()
        if mode not in ["category", "keyword"]:
            return JsonResponse({"status": "error", "message": "無效的爬蟲模式"}, status=400)
        
        config = load_crawler_config()
        config["mode"] = mode
        if save_crawler_config(config):
            mode_text = "看板爬取" if mode == "category" else "關鍵字搜尋"
            return JsonResponse({"status": "success", "message": f"已成功切換為：{mode_text}模式", "mode": mode})
        else:
            return JsonResponse({"status": "error", "message": "儲存模式設定時發生錯誤"}, status=500)


def scheduler(request):
    """Render the scheduler management page."""
    return render(request, "app_scrap_scheduling/home.html")


# Note: api_data is commented out because the Article model is not defined in this application
# def api_data(request):
#     """Return JSON data for the frontend."""
#     query = request.GET.get("q", "").strip()
#     articles = Article.objects.all().order_by("-published_date", "-created_at")
# 
#     if query:
#         articles = articles.filter(
#             Q(title__icontains=query) | Q(content__icontains=query)
#         )
# 
#     data = []
# 
#     for article in articles:
#         emotion_data = {}
# 
#         if hasattr(article, "emotion") and article.emotion is not None:
#             emotion = article.emotion
#             emotion_data = {
#                 "cheer_up": emotion.cheer_up,
#                 "happy": emotion.happy,
#                 "mixed": emotion.mixed,
#                 "dumbfounded": emotion.dumbfounded,
#                 "angry": emotion.angry,
#                 "sad": emotion.sad,
#             }
# 
#         comments = list(
#             article.comments.all()
#             .order_by("-upvotes")
#             .values("content", "upvotes", "downvotes")[:30]
#         )
# 
#         data.append({
#             "id": article.id,
#             "title": article.title,
#             "category": article.category,
#             "url": article.url,
#             "content": article.content,
#             "published_date": (
#                 article.published_date.strftime("%Y-%m-%d")
#                 if article.published_date
#                 else ""
#             ),
#             "positive_score": article.positive_score,
#             "negative_score": article.negative_score,
#             "neutral_score": article.neutral_score,
#             "comments_count": article.comments.count(),
#             "emotion": emotion_data,
#             "analyzed": article.analyzed_at is not None,
#             "comments": comments,
#         })
# 
#     return JsonResponse({"articles": data})


@require_http_methods(["GET"])
def api_scheduler_status(request):
    status = scheduler_manager.get_job_status()
    return JsonResponse(status)


@csrf_exempt
@require_http_methods(["POST"])
def api_scheduler_start(request):
    scheduler_manager.start_jobs()
    return JsonResponse({"status": "success", "message": "排程已啟動"})


@csrf_exempt
@require_http_methods(["POST"])
def api_scheduler_stop(request):
    scheduler_manager.stop_jobs()
    return JsonResponse({"status": "success", "message": "排程已取消"})


@csrf_exempt
@require_http_methods(["POST"])
def api_run_task(request):
    task = request.POST.get("task", "")

    if task == "scraper":
        config = load_crawler_config()
        mode = config.get("mode", "category")
        keywords = config.get("keywords", [])
        
        if mode == "keyword":
            crawler_script = "get_dcard_by_keyword.py"
            mode_text = "關鍵字搜尋"
        else:
            crawler_script = "get_dcard_by_category.py"
            mode_text = "看板爬取"
            
        crawler_path = os.path.join(
            settings.BASE_DIR,
            "app_scrap_scheduling",
            crawler_script
        )
        import threading
        threading.Thread(
            target=scheduler_manager.run_manual_crawler,
            args=(crawler_path, keywords, mode_text),
            daemon=True
        ).start()

        return JsonResponse({
            "status": "success",
            "message": f"Dcard 手動爬蟲任務已啟動 ({mode_text}模式)，目標：{', '.join(keywords)}"
        })


@require_http_methods(["GET"])
def api_scheduler_history(request):
    try:
        history = scheduler_manager.get_execution_history()
        return JsonResponse(history)
    except Exception as e:
        return JsonResponse({"error": str(e)}, status=500)


@csrf_exempt
@require_http_methods(["GET"])
def api_download_files(request):
    import mimetypes
    from datetime import datetime

    file_param = request.GET.get("file", "").strip()
    type_param = request.GET.get("type", "").strip()

    # 定義檔案存放的絕對目錄
    base_dirs = {
        "category": os.path.join(settings.BASE_DIR, "data", "dcard_data", "by_category"),
        "keyword": os.path.join(settings.BASE_DIR, "data", "dcard_data", "by_keyword")
    }

    # 1. 處理單一檔案下載請求
    if file_param:
        if type_param not in base_dirs:
            return JsonResponse({"status": "error", "message": "無效的檔案類型參數"}, status=400)
        
        # 安全性防範：Path Traversal 防禦
        if ".." in file_param or "/" in file_param or "\\" in file_param:
            return HttpResponse("Permission Denied: Invalid characters in filename.", status=403)
        
        if not file_param.lower().endswith(".csv"):
            return HttpResponse("Permission Denied: Only CSV files are allowed to be downloaded.", status=403)
        
        target_dir = base_dirs[type_param]
        file_path = os.path.join(target_dir, file_param)

        if not os.path.exists(file_path):
            return HttpResponse("File Not Found.", status=404)

        # 回傳下載檔案
        mime_type, _ = mimetypes.guess_type(file_path)
        if not mime_type:
            mime_type = "text/csv"
        
        response = FileResponse(open(file_path, "rb"), content_type=mime_type)
        response["Content-Disposition"] = f'attachment; filename="{file_param}"'
        return response

    # 2. 處理檔案清單瀏覽請求
    file_list = []
    
    for file_type, dir_path in base_dirs.items():
        if os.path.exists(dir_path):
            try:
                for entry in os.scandir(dir_path):
                    if entry.is_file() and entry.name.lower().endswith(".csv"):
                        stat = entry.stat()
                        size_kb = round(stat.st_size / 1024, 2)
                        size_str = f"{size_kb} KB" if size_kb < 1024 else f"{round(size_kb / 1024, 2)} MB"
                        
                        modified_time = datetime.fromtimestamp(stat.st_mtime).strftime("%Y-%m-%d %H:%M:%S")
                        
                        # 產生對應的下載連結
                        download_url = f"/scrap_scheduling/api/download-files/?file={entry.name}&type={file_type}"
                        
                        file_list.append({
                            "name": entry.name,
                            "type": "看板爬取資料" if file_type == "category" else "關鍵字搜尋資料",
                            "type_code": file_type,
                            "size": size_str,
                            "modified": modified_time,
                            "download_url": download_url
                        })
            except Exception as e:
                print(f"讀取目錄 {dir_path} 時發生錯誤: {e}")
                
    # 依修改時間由新到舊排序
    file_list.sort(key=lambda x: x["modified"], reverse=True)
    return JsonResponse({"status": "success", "files": file_list})


@csrf_exempt
@require_http_methods(["POST"])
def api_delete_file(request):
    file_param = request.POST.get("file", "").strip()
    type_param = request.POST.get("type", "").strip()

    base_dirs = {
        "category": os.path.join(settings.BASE_DIR, "data", "dcard_data", "by_category"),
        "keyword": os.path.join(settings.BASE_DIR, "data", "dcard_data", "by_keyword")
    }

    if type_param not in base_dirs:
        return JsonResponse({"status": "error", "message": "無效的檔案類型參數"}, status=400)
    
    # 安全性防範：Path Traversal 防禦
    if ".." in file_param or "/" in file_param or "\\" in file_param:
        return JsonResponse({"status": "error", "message": "Permission Denied: Invalid characters in filename."}, status=403)
    
    if not file_param.lower().endswith(".csv"):
        return JsonResponse({"status": "error", "message": "Permission Denied: Only CSV files are allowed to be deleted."}, status=403)
    
    target_dir = base_dirs[type_param]
    file_path = os.path.join(target_dir, file_param)

    if not os.path.exists(file_path):
        return JsonResponse({"status": "error", "message": "找不到該檔案。"}, status=404)

    try:
        os.remove(file_path)
        return JsonResponse({"status": "success", "message": f"檔案 {file_param} 已成功刪除。"})
    except Exception as e:
        return JsonResponse({"status": "error", "message": f"刪除檔案時發生錯誤: {str(e)}"}, status=500)


@csrf_exempt
@require_http_methods(["POST"])
def api_delete_all_files(request):
    base_dirs = {
        "category": os.path.join(settings.BASE_DIR, "data", "dcard_data", "by_category"),
        "keyword": os.path.join(settings.BASE_DIR, "data", "dcard_data", "by_keyword")
    }

    deleted_count = 0
    errors = []

    for name, dir_path in base_dirs.items():
        if os.path.exists(dir_path):
            try:
                for entry in os.scandir(dir_path):
                    if entry.is_file() and entry.name.lower().endswith(".csv"):
                        try:
                            os.remove(entry.path)
                            deleted_count += 1
                        except Exception as e:
                            errors.append(f"無法刪除 {entry.name}: {str(e)}")
            except Exception as e:
                errors.append(f"讀取目錄 {name} 時發生錯誤: {str(e)}")

    if errors:
        return JsonResponse({
            "status": "partial_success" if deleted_count > 0 else "error",
            "message": f"已刪除 {deleted_count} 個檔案。但發生以下錯誤：\n" + "\n".join(errors),
            "deleted_count": deleted_count
        })
    else:
        return JsonResponse({
            "status": "success",
            "message": f"成功刪除所有已爬取的檔案（共 {deleted_count} 個）。"
        })
    