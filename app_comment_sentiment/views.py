from django.shortcuts import render
from django.core.paginator import Paginator
from django.conf import settings
import pandas as pd
import os
from collections import Counter

# 留言情緒類別 (對應 sentiment_type 欄位)
SENTI_CLASSES = ['正面留言', '負面留言', '中立留言']

# 留言互動類型 (對應 interaction_type 欄位)
INTERACTION_CLASSES = [
    '經驗分享', '建議與意見', '問題詢問', '單純聊天',
    '回答／解釋', '補充資訊', '感謝回覆',
]

def get_theme_comments_data(request):
    """Loads article and comment datasets dynamically for the active theme."""
    theme = request.session.get('active_theme', '機場')
    processed_dir = os.path.join(settings.BASE_DIR, 'data', 'processed', theme)
    
    art_path = os.path.join(processed_dir, 'articles_preprocessed_ai.csv')
    cmt_path = os.path.join(processed_dir, 'comments_labeled.csv')
    
    if not (os.path.exists(art_path) and os.path.exists(cmt_path)):
        # Fallback to defaults
        base_dir = os.path.dirname(os.path.abspath(__file__))
        base = os.path.join(base_dir, 'dataset')
        art_path = os.path.join(base, 'dcard_data1_all.csv')
        cmt_path = os.path.join(base, 'dcard_data1_sub_all_sorted_labeled.csv')
        
    try:
        df_art = pd.read_csv(art_path, sep='|')
        df_cmt = pd.read_csv(cmt_path, sep='|')
    except Exception as e:
        print(f"Error loading comment sentiment data for {theme}: {e}")
        df_art = pd.DataFrame(columns=['article_id', 'category', 'article_dates', 'title', 'content', 'links'])
        df_cmt = pd.DataFrame(columns=['article_id', 'floor', 'time', 'likes', 'text', 'sentiment_type', 'interaction_type'])
        
    # Standardize types
    df_art['article_id'] = df_art['article_id'].astype(str)
    df_cmt['article_id'] = df_cmt['article_id'].astype(str)
    df_cmt['likes'] = pd.to_numeric(df_cmt['likes'], errors='coerce').fillna(0).astype(int)
    
    # Sort articles by date
    df_art['_dt'] = pd.to_datetime(df_art['article_dates'], errors='coerce')
    df_art = df_art.sort_values('_dt', ascending=False).reset_index(drop=True)
    
    valid_ids = set(df_cmt['article_id'].unique())
    comments_by_article = {
        aid: sub_df for aid, sub_df in df_cmt.groupby('article_id')
    }
    
    return df_art, df_cmt, valid_ids, comments_by_article


def _search_articles(request, keyword: str):
    """Searches articles matching the keyword, returning filtered articles and comment index."""
    df_articles, df_comments, valid_ids, comments_by_article = get_theme_comments_data(request)
    
    # Filter to articles that actually have comments
    base_df = df_articles[
        df_articles['article_id'].isin(valid_ids)
    ]

    if not keyword:
        return base_df, comments_by_article

    kw = keyword.strip()
    if not kw:
        return base_df, comments_by_article

    title = base_df['title'].fillna('').astype(str)
    content = base_df['content'].fillna('').astype(str)

    mask = (
        title.str.contains(kw, case=False, na=False)
        |
        content.str.contains(kw, case=False, na=False)
    )

    return base_df[mask], comments_by_article


def _build_article_block(row, comments_by_article) -> dict:
    """Assembles comment sentiment analysis and ratios for a single article."""
    aid = str(row['article_id'])
    sub = comments_by_article.get(aid)

    senti_count = {k: 0 for k in SENTI_CLASSES}
    inter_count = {k: 0 for k in INTERACTION_CLASSES}
    comments_list = []
    num_comments = 0

    if sub is not None and len(sub) > 0:
        num_comments = len(sub)

        # Sentiment frequency count
        c1 = Counter(sub['sentiment_type'].fillna('中立留言').astype(str))
        for k in SENTI_CLASSES:
            senti_count[k] = int(c1.get(k, 0))

        # Interaction type frequency count
        c2 = Counter(sub['interaction_type'].fillna('單純聊天').astype(str))
        for k in INTERACTION_CLASSES:
            inter_count[k] = int(c2.get(k, 0))

        # Sort comments by likes descending
        sub_sorted = sub.sort_values('likes', ascending=False)
        for _, c in sub_sorted.iterrows():
            comments_list.append({
                'floor': str(c.get('floor', '')),
                'time': str(c.get('time', '')),
                'likes': int(c.get('likes', 0) or 0),
                'text': str(c.get('text', '')),
                'interaction_type': str(c.get('interaction_type', '')),
                'sentiment_type': str(c.get('sentiment_type', '')),
            })

    # Calculate sentiment percentage
    total_senti = sum(senti_count.values())
    senti_percent = {
        k: (round(v / total_senti * 100, 1) if total_senti else 0)
        for k, v in senti_count.items()
    }

    # Calculate interaction type ratio
    total_inter = sum(inter_count.values())
    inter_ratio = []
    for k, v in sorted(inter_count.items(), key=lambda x: -x[1]):
        if v == 0:
            continue
        inter_ratio.append({
            'name': k,
            'count': v,
            'percent': round(v / total_inter * 100, 1) if total_inter else 0,
        })

    # Pick top 3 comments as hot comments
    top_comments = comments_list[:3]

    return {
        'article_id': aid,
        'title': str(row.get('title', '')),
        'category': str(row.get('category', '')),
        'article_dates': str(row.get('article_dates', '')),
        'links': str(row.get('links', '')),
        'num_comments': num_comments,
        'senti_count': senti_count,
        'senti_percent': senti_percent,
        'inter_ratio': inter_ratio,
        'top_comments': top_comments,
        'all_comments': comments_list,
    }


def home(request):
    keyword = request.GET.get('q', '').strip()
    theme = request.session.get('active_theme', '機場')

    filtered, comments_by_article = _search_articles(request, keyword)

    # Paginate: 10 articles per page
    paginator = Paginator(filtered.to_dict('records'), 10)
    page_number = request.GET.get('page', 1)
    page_obj = paginator.get_page(page_number)

    blocks = [_build_article_block(row, comments_by_article) for row in page_obj.object_list]

    context = {
        'keyword': keyword,
        'total_articles': len(filtered),
        'blocks': blocks,
        'page_obj': page_obj,
        'senti_classes': SENTI_CLASSES,
        'active_theme': theme,
    }
    return render(request, 'app_comment_sentiment/home.html', context)


print("app_comment_sentiment was loaded dynamically!")
