from django.shortcuts import render, redirect
from django.http import JsonResponse
from django.views.decorators.csrf import csrf_exempt
from django.conf import settings
import pandas as pd
import json
import os
import threading
from . import theme_importer

# Global dictionary to track progress of theme imports
IMPORT_PROGRESS = {}

# ── Dynamic Data Loading Helpers ──────────────────────────

def get_active_theme(request):
    """Returns the active theme from session, default to '機場'."""
    return request.session.get('active_theme', '機場')

def load_theme_datasets(theme):
    """Dynamically loads keyword, monthly trend, and category datasets for active theme."""
    processed_dir = os.path.join(settings.BASE_DIR, 'data', 'processed', theme)
    
    # Check if files exist in the processed directory
    kw_path = os.path.join(processed_dir, 'keyword_analysis.csv')
    trend_path = os.path.join(processed_dir, 'monthly_trend.csv')
    cat_path = os.path.join(processed_dir, 'category.csv')
    
    if not (os.path.exists(kw_path) and os.path.exists(trend_path) and os.path.exists(cat_path)):
        # Fallback to default airport dataset
        default_dir = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'dataset')
        kw_path = os.path.join(default_dir, 'airport_keyword_analysis.csv')
        trend_path = os.path.join(default_dir, 'airport_monthly_trend.csv')
        cat_path = os.path.join(default_dir, 'airport_category.csv')
        
    try:
        df_kw = pd.read_csv(kw_path)
        df_trend = pd.read_csv(trend_path)
        df_cat = pd.read_csv(cat_path)
    except Exception as e:
        print(f"Error loading theme datasets for {theme}: {e}")
        df_kw = pd.DataFrame(columns=['context', 'context_mentions', 'keyword', 'keyword_freq'])
        df_trend = pd.DataFrame(columns=['year_month', 'llm_scenario', 'article_count'])
        df_cat = pd.DataFrame(columns=['category', 'llm_scenario', 'article_count'])
        
    return df_kw, df_trend, df_cat

def build_ranking(df_kw):
    """Computes scenario ranking dynamically from keywords dataset."""
    if df_kw.empty or 'context' not in df_kw.columns:
        return []
    
    # Make sure required columns exist
    if 'context_mentions' not in df_kw.columns:
        df_kw['context_mentions'] = 1
        
    summary = (
        df_kw.groupby('context')['context_mentions']
        .first()
        .reset_index()
        .sort_values('context_mentions', ascending=False)
        .rename(columns={'context': 'scenario', 'context_mentions': 'article_count'})
    )
    return summary.to_dict('records')


# ── Pages ──────────────────────────────────────────────────

def home_overview(request):
    theme = get_active_theme(request)
    df_kw, _, _ = load_theme_datasets(theme)
    ranking = build_ranking(df_kw)
    
    return render(request, 'app_airport_analysis/home_overview.html', {
        'scenario_ranking': json.dumps(ranking, ensure_ascii=False),
        'active_theme': theme,
    })

def home_trend(request):
    theme = get_active_theme(request)
    return render(request, 'app_airport_analysis/home_trend.html', {
        'active_theme': theme,
    })

def home_deepdive(request):
    theme = get_active_theme(request)
    df_kw, _, _ = load_theme_datasets(theme)
    ranking = build_ranking(df_kw)
    scenario_list = [r['scenario'] for r in ranking]
    
    return render(request, 'app_airport_analysis/home_deepdive.html', {
        'scenario_list': scenario_list,
        'active_theme': theme,
    })


# ── AJAX API ──────────────────────────────────────────────

@csrf_exempt
def api_get_airport_analysis(request):
    """
    mode=overview   : 總覽（情境排行 + 板塊分佈 + 月趨勢）
    mode=deepdive   : 單情境關鍵字深度分析
    mode=trend      : 月趨勢資料（所有情境）
    mode=category   : 各板討論板統計
    """
    mode = request.POST.get('mode', 'overview')
    theme = get_active_theme(request)
    df_kw, df_trend, df_cat = load_theme_datasets(theme)
    ranking = build_ranking(df_kw)
    scenario_list = [r['scenario'] for r in ranking]

    # ── 深度分析 ──────────────────────────────────────────
    if mode == 'deepdive':
        scenario = request.POST.get('scenario', scenario_list[0] if scenario_list else '')
        rows = df_kw[df_kw['context'] == scenario].sort_values('keyword_freq', ascending=False)

        if rows.empty:
            return JsonResponse({'error': '找不到該情境資料'}, status=404)

        keywords = rows[['keyword', 'keyword_freq']].head(40).to_dict('records')
        return JsonResponse({
            'scenario': scenario,
            'mentions': int(rows['context_mentions'].iloc[0]) if not rows.empty else 0,
            'keywords': keywords,
        })

    # ── 月趨勢 ────────────────────────────────────────────
    if mode == 'trend':
        if df_trend.empty:
            return JsonResponse({'months': [], 'datasets': []})
            
        pivot = df_trend.pivot_table(
            index='year_month', columns='llm_scenario',
            values='article_count', aggfunc='sum', fill_value=0
        ).reset_index()
        
        months    = pivot['year_month'].tolist()
        scenarios = [c for c in pivot.columns if c != 'year_month']
        datasets  = [
            {'scenario': sc, 'data': pivot[sc].tolist()}
            for sc in scenarios
        ]
        return JsonResponse({'months': months, 'datasets': datasets})

    # ── 討論板分佈 ────────────────────────────────────────
    if mode == 'category':
        if df_cat.empty:
            return JsonResponse({'categories': [], 'counts': []})
            
        top_cats = (
            df_cat.groupby('category')['article_count']
            .sum()
            .reset_index()
            .sort_values('article_count', ascending=False)
            .head(12)
        )
        return JsonResponse({
            'categories': top_cats['category'].tolist(),
            'counts':     top_cats['article_count'].tolist(),
        })

    return JsonResponse({'error': '未知的 mode'}, status=400)


# ── Theme Management Views ────────────────────────────────

def set_theme(request):
    """Sets the active theme session variable."""
    theme = request.GET.get('theme', '機場').strip()
    processed_themes = theme_importer.list_processed_themes()
    
    if theme in processed_themes:
        request.session['active_theme'] = theme
    else:
        request.session['active_theme'] = '機場'
        
    referer = request.META.get('HTTP_REFERER', '/')
    return redirect(referer)

def theme_manager(request):
    """Renders the Theme Manager control panel page."""
    raw_themes = theme_importer.list_raw_themes()
    processed_themes = theme_importer.list_processed_themes()
    active_theme = get_active_theme(request)
    
    themes_status = []
    for t in raw_themes:
        status = "imported" if t in processed_themes else "not_imported"
        themes_status.append({
            'name': t,
            'status': status
        })
        
    # Ensure default '機場' is listed first and as imported
    if "機場" not in [x['name'] for x in themes_status]:
        themes_status.insert(0, {'name': '機場', 'status': 'imported'})
        
    return render(request, 'app_airport_analysis/theme_manager.html', {
        'themes': themes_status,
        'active_theme': active_theme,
    })

@csrf_exempt
def api_theme_import(request):
    """API endpoint to trigger background process for dynamic AI categorization."""
    if request.method != 'POST':
        return JsonResponse({'error': 'Only POST method is allowed'}, status=405)
        
    theme = request.POST.get('theme', '').strip()
    num_classes = request.POST.get('num_classes', '6')
    
    try:
        num_classes = int(num_classes)
        if num_classes < 2 or num_classes > 10:
            num_classes = 6
    except ValueError:
        num_classes = 6
        
    if not theme or theme == '機場':
        return JsonResponse({'error': '無效的主題名稱'}, status=400)
        
    # Check if already running
    if theme in IMPORT_PROGRESS and IMPORT_PROGRESS[theme]['status'] == 'running':
        return JsonResponse({'status': 'running', 'message': '該主題分類正在處理中'})
        
    # Initialize progress tracking
    IMPORT_PROGRESS[theme] = {
        'progress': 0,
        'status': 'running',
        'message': '開始啟動背景分類工作...'
    }
    
    def progress_logger(percent, msg):
        if percent == -1:
            IMPORT_PROGRESS[theme] = {
                'progress': 100,
                'status': 'error',
                'message': msg
            }
        else:
            IMPORT_PROGRESS[theme] = {
                'progress': percent,
                'status': 'running' if percent < 100 else 'success',
                'message': msg
            }
            
    def run_importer():
        try:
            theme_importer.import_and_process_theme(theme, num_classes, progress_logger)
        except Exception as e:
            progress_logger(-1, f"導入失敗: {str(e)}")
            
    t = threading.Thread(target=run_importer)
    t.daemon = True
    t.start()
    
    return JsonResponse({'status': 'started', 'message': '背景導入工作已啟動'})

def api_theme_progress(request):
    """API endpoint to poll the progress of the theme import."""
    theme = request.GET.get('theme', '').strip()
    if not theme:
        return JsonResponse({'error': '未指定主題'}, status=400)
        
    progress = IMPORT_PROGRESS.get(theme, {
        'progress': 0,
        'status': 'idle',
        'message': '無進行中的工作'
    })
    return JsonResponse(progress)
