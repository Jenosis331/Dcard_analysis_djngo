from django.shortcuts import render
from django.http import JsonResponse
from django.views.decorators.csrf import csrf_exempt
from django.conf import settings
import pandas as pd
import json
import os

# ── Dynamic Data Loading Helper ─────────────────────────────

def load_search_dataset(request):
    """Loads the dataset for the active theme dynamically."""
    theme = request.session.get('active_theme', '機場')
    processed_dir = os.path.join(settings.BASE_DIR, 'data', 'processed', theme)
    csv_path = os.path.join(processed_dir, 'articles_preprocessed_ai.csv')
    
    if not os.path.exists(csv_path):
        # Fallback to default airport dataset
        csv_path = os.path.join(
            settings.BASE_DIR, 'app_airport_analysis', 'dataset',
            'dcard_機場_20260418_preprocessed_ai.csv'
        )
        
    try:
        df = pd.read_csv(csv_path, sep='|', encoding='utf-8-sig', on_bad_lines='skip')
    except Exception as e:
        print(f"Error loading search dataset for {theme}: {e}")
        df = pd.DataFrame(columns=[
            'article_id', 'category', 'article_dates', 'title', 'content', 
            'summary', 'sentiment', 'tokens', 'tokens_v2', 'entities', 
            'token_pos', 'top_key_freq', 'links', 'llm_scenario'
        ])
        
    # Standardize columns
    df['llm_scenario'] = df['llm_scenario'].fillna('未分類').astype(str).str.strip()
    df['title']        = df['title'].fillna('').astype(str)
    df['content']      = df['content'].fillna('').astype(str)
    df['summary']      = df['summary'].fillna('').astype(str)
    df['links']        = df['links'].fillna('').astype(str)
    df['category']     = df['category'].fillna('').astype(str)
    df['article_dates']= df['article_dates'].fillna('').astype(str)
    df['article_id']   = pd.to_numeric(df['article_id'], errors='coerce')
    
    # Search helper composite text field
    df['_search_text'] = (
        df['title'] + ' ' + df['content'] + ' ' + df['summary']
    )
    
    return df


# ── Search Helper Functions ─────────────────────────────────

def _rows_to_results(rows, limit=200):
    out = []
    for _, row in rows.head(limit).iterrows():
        out.append({
            'article_id': int(row['article_id']) if pd.notna(row['article_id']) else '',
            'date':       row['article_dates'],
            'title':      row['title'],
            'scenario':   row['llm_scenario'],
            'category':   row['category'],
            'link':       row['links'],
            'summary':    row['summary'][:120] + ('…' if len(row['summary']) > 120 else ''),
        })
    return out

def _search_keyword(df_raw, query, logic, scenario):
    keywords = [k.strip() for k in query.split() if k.strip()]
    if not keywords:
        return [], 0

    text = df_raw['_search_text']
    if logic == 'AND':
        mask = pd.Series(True, index=df_raw.index)
        for kw in keywords:
            mask &= text.str.contains(kw, case=False, na=False, regex=False)
    else:  # OR
        mask = pd.Series(False, index=df_raw.index)
        for kw in keywords:
            mask |= text.str.contains(kw, case=False, na=False, regex=False)

    if scenario and scenario != 'all':
        mask &= (df_raw['llm_scenario'] == scenario)

    matched = df_raw[mask]
    return _rows_to_results(matched), len(matched)

def _search_by_id(df_raw, article_id_str):
    try:
        aid = int(article_id_str.strip())
    except (ValueError, AttributeError):
        return [], 0
    matched = df_raw[df_raw['article_id'] == aid]
    return _rows_to_results(matched), len(matched)


# ── Views ───────────────────────────────────────────────────

def home(request):
    theme = request.session.get('active_theme', '機場')
    df_raw = load_search_dataset(request)
    
    # Extrapolate scenario list dynamically
    scenarios_in_data = df_raw['llm_scenario'].unique().tolist()
    SCENARIO_ORDER = [
        '旅遊規劃資訊', '機場交通', '情緒與經驗', '機場設施服務',
        '工作求職', '出入境流程', '治安與突發事件', '航班異常', '其他', '未分類',
    ]
    scenario_list = [s for s in SCENARIO_ORDER if s in scenarios_in_data] + \
                    [s for s in scenarios_in_data if s not in SCENARIO_ORDER]
                    
    return render(request, 'app_airport_search/home.html', {
        'scenario_list': scenario_list,
        'total_articles': len(df_raw),
        'active_theme': theme,
    })

@csrf_exempt
def api_search(request):
    """
    POST params:
      search_type : "keyword" | "id"
      query       : 關鍵字字串（空格分隔）或 article_id
      logic       : "AND" | "OR"（僅 keyword 模式有效）
      scenario    : 情境篩選值，"all" 表示不篩選
    """
    if request.method != 'POST':
        return JsonResponse({'error': '僅接受 POST 請求'}, status=405)

    search_type = request.POST.get('search_type', 'keyword')
    query       = request.POST.get('query', '').strip()
    logic       = request.POST.get('logic', 'AND').upper()
    scenario    = request.POST.get('scenario', 'all').strip()

    if not query:
        return JsonResponse({'error': '請輸入搜尋內容'}, status=400)

    if logic not in ('AND', 'OR'):
        logic = 'AND'

    df_raw = load_search_dataset(request)

    if search_type == 'id':
        results, total = _search_by_id(df_raw, query)
    else:
        results, total = _search_keyword(df_raw, query, logic, scenario)

    return JsonResponse({
        'search_type': search_type,
        'query':       query,
        'logic':       logic,
        'scenario':    scenario,
        'total':       total,
        'results':     results,
    })
