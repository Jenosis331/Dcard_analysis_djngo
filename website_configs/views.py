from django.shortcuts import render
from django.http import JsonResponse
from django.views.decorators.csrf import csrf_exempt
import sqlite3
import os
from django.conf import settings
from website_configs.categories import CATEGORIES

@csrf_exempt
def home(request):
    db_path = os.path.join(settings.BASE_DIR, 'db.sqlite3')
    
    if request.method == 'POST':
        import json
        try:
            if request.content_type == 'application/json':
                body = json.loads(request.body)
                selected_categories = body.get('categories', [])
            else:
                selected_categories = request.POST.getlist('categories')
            
            selected_categories = [str(x).strip() for x in selected_categories if x]
            
            categories_file_path = os.path.join(settings.BASE_DIR, 'website_configs', 'categories.py')
            
            new_content = f"""# 統一管理新聞類別設定
# 新增/修改類別只需在這裡更動，所有頁面會自動同步

# Dcard 看板類別 (用於 app_top_keyword)
CATEGORIES = {repr(selected_categories)}
"""
            with open(categories_file_path, 'w', encoding='utf-8') as f:
                f.write(new_content)
            
            # In-place modify the imported CATEGORIES list to reflect immediately
            from website_configs import categories
            categories.CATEGORIES.clear()
            categories.CATEGORIES.extend(selected_categories)
            
            return JsonResponse({'status': 'success', 'categories': selected_categories})
        except Exception as e:
            return JsonResponse({'status': 'error', 'message': str(e)}, status=400)
            
    # GET method
    conn = sqlite3.connect(db_path)
    cursor = conn.cursor()
    
    # Get categories
    all_categories = []
    try:
        cursor.execute('SELECT category FROM dcard_data3_tokenpos_all')
        all_categories = sorted(list(set([row[0] for row in cursor.fetchall()])))
    except Exception as e:
        print(f"Error getting categories: {e}")
        
    # Get SQLite record count from dcard_data1_all
    db_count = 0
    try:
        cursor.execute('SELECT COUNT(*) FROM dcard_data1_all')
        db_count = cursor.fetchone()[0]
    except Exception as e:
        print(f"Error querying SQLite count: {e}")
        
    conn.close()

    # Get Chroma DB count
    chroma_count = 0
    try:
        chroma_db_path = os.path.join(settings.BASE_DIR, "app_poa_langchain", "chroma_dcard_db")
        if os.path.exists(chroma_db_path):
            import chromadb
            chroma_client = chromadb.PersistentClient(path=chroma_db_path)
            collections = chroma_client.list_collections()
            for col in collections:
                if col.name == "dcard_articles":
                    chroma_count = col.count()
                    break
    except Exception as e:
        print(f"Error querying Chroma count: {e}")

    context = {
        'all_categories': all_categories,
        'current_categories': CATEGORIES,
        'db_count': db_count,
        'chroma_count': chroma_count,
    }
    return render(request, 'home.html', context)


