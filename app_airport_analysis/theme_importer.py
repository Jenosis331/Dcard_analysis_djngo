import os
import re
import json
import time
import pandas as pd
from openai import OpenAI
from django.conf import settings

google_model = "gemini-3.5-flash"  # Updated model name for Gemini Pro Preview

def get_client():
    """Initializes the OpenAI API client configured for Gemini."""
    api_key = os.getenv("GEMINI_API_KEY")
    if not api_key:
        from dotenv import load_dotenv
        load_dotenv(os.path.join(settings.BASE_DIR, ".env"))
        api_key = os.getenv("GEMINI_API_KEY")
    
    if not api_key:
        raise ValueError("GEMINI_API_KEY environment variable not set.")
        
    url = "https://generativelanguage.googleapis.com/v1beta/openai/"
    return OpenAI(base_url=url, api_key=api_key)

def clean_and_parse_json(text):
    """Safely extracts and parses JSON from LLM response text."""
    if not text:
        raise ValueError("Empty response text")
        
    text = text.strip()
    
    # 1. Try direct parsing
    try:
        return json.loads(text)
    except json.JSONDecodeError:
        pass
        
    # 2. Extract JSON block from markdown fences or text
    first_brace = text.find('{')
    first_bracket = text.find('[')
    
    start_idx = -1
    end_idx = -1
    is_array = False
    
    if first_brace != -1 and (first_bracket == -1 or first_brace < first_bracket):
        start_idx = first_brace
        end_idx = text.rfind('}')
    elif first_bracket != -1:
        start_idx = first_bracket
        end_idx = text.rfind(']')
        is_array = True
        
    if start_idx == -1 or end_idx == -1:
        raise ValueError(f"Could not find valid JSON boundaries in text: {text[:100]}...")
        
    json_str = text[start_idx:end_idx + 1]
    
    # 3. Try parsing extracted JSON
    try:
        return json.loads(json_str)
    except json.JSONDecodeError:
        pass
        
    # 4. Clean common JSON issues (single quotes, trailing commas, raw newlines)
    cleaned = json_str
    cleaned = re.sub(r"'\s*:", r'":', cleaned)
    cleaned = re.sub(r":\s*'", r':"', cleaned)
    cleaned = re.sub(r"'\s*,\s*'", r'","', cleaned)
    cleaned = re.sub(r"\[\s*'", r'["', cleaned)
    cleaned = re.sub(r"'\s*\]", r'"]', cleaned)
    cleaned = re.sub(r"'\s*\}", r'"}', cleaned)
    cleaned = re.sub(r"\{\s*'", r'{"', cleaned)
    cleaned = re.sub(r"'\s*,", r'",', cleaned)
    cleaned = re.sub(r",\s*'", r',"', cleaned)
    
    # Replace raw newlines in string values with escaped \n
    def escape_inner_newlines(match):
        return match.group(0).replace('\n', '\\n').replace('\r', '')
    
    cleaned = re.sub(r'"[^"\\]*(?:\\.[^"\\]*)*"', escape_inner_newlines, cleaned)
    
    # Try parsing cleaned JSON
    try:
        return json.loads(cleaned)
    except json.JSONDecodeError as e:
        # 5. Last resort fallback parsing for key-value extraction using regex
        if not is_array:
            fallback = {}
            for key in ['category', 'reason', 'summary', 'keywords']:
                match = re.search(r'[\'"]' + key + r'[\'"]\s*:\s*([\'"])(.*?)\1', json_str, re.DOTALL)
                if match:
                    val = match.group(2).strip()
                    fallback[key] = val
                elif key == 'keywords':
                    kw_match = re.search(r'[\'"]keywords[\'"]\s*:\s*\[(.*?)\]', json_str, re.DOTALL)
                    if kw_match:
                        kws = []
                        pairs = re.findall(r'\[\s*[\'"](.*?)[\'"]\s*,\s*(\d+)\s*\]', kw_match.group(1))
                        for w, f in pairs:
                            kws.append([w, int(f)])
                        fallback[key] = kws
                        
            if 'category' in fallback:
                return fallback
                
        raise ValueError(f"Failed to parse JSON even after cleaning. Error: {e}. Cleaned text: {cleaned[:200]}")

def list_raw_themes():
    """Scans raw data folder to find available topics."""
    themes = set()
    for subfolder in ['by_keyword']:
        raw_dir = os.path.join(settings.BASE_DIR, 'data', 'dcard_data', subfolder)
        if os.path.exists(raw_dir):
            for filename in os.listdir(raw_dir):
                if filename.endswith('.csv') and not filename.startswith('dcard_sub_'):
                    match = re.match(r"^dcard_(.+?)_\d{8}\.csv$", filename)
                    if match:
                        themes.add(match.group(1))
    return sorted(list(themes))

def list_processed_themes():
    """Scans processed data folder to see what is already imported."""
    processed_dir = os.path.join(settings.BASE_DIR, 'data', 'processed')
    if not os.path.exists(processed_dir):
        return ["機場"]
    themes = ["機場"]  # default
    for name in os.listdir(processed_dir):
        path = os.path.join(processed_dir, name)
        if os.path.isdir(path) and name != "機場":
            # Check if all required files exist
            required = ['articles_preprocessed_ai.csv', 'comments_labeled.csv', 'keyword_analysis.csv', 'monthly_trend.csv', 'category.csv']
            if all(os.path.exists(os.path.join(path, f)) for f in required):
                themes.append(name)
    return sorted(list(set(themes)))

def combine_raw_theme_data(theme):
    """Combines raw CSV files for a given theme, handling separators correctly."""
    posts_dfs = []
    comments_dfs = []
    
    for subfolder in ['by_category', 'by_keyword']:
        posts_dir = os.path.join(settings.BASE_DIR, 'data', 'dcard_data', subfolder)
        
        if os.path.exists(posts_dir):
            for filename in os.listdir(posts_dir):
                if filename.startswith(f"dcard_{theme}_") and filename.endswith('.csv') and not filename.startswith('dcard_sub_'):
                    path = os.path.join(posts_dir, filename)
                    try:
                        df = pd.read_csv(path, sep='|', encoding='utf-8')
                        posts_dfs.append(df)
                    except Exception as e:
                        print(f"Error reading posts {path}: {e}")
                        
                elif filename.startswith(f"dcard_sub_{theme}_") and filename.endswith('.csv'):
                    path = os.path.join(posts_dir, filename)
                    try:
                        df = pd.read_csv(path, sep=',', encoding='utf-8')
                        comments_dfs.append(df)
                    except Exception as e:
                        print(f"Error reading comments {path}: {e}")
                        
    if not posts_dfs:
        raise ValueError(f"No posts found for theme: {theme}")
        
    df_posts = pd.concat(posts_dfs, ignore_index=True)
    df_posts = df_posts.drop_duplicates(subset=['article_id']).reset_index(drop=True)
    
    if comments_dfs:
        df_comments = pd.concat(comments_dfs, ignore_index=True)
        df_comments = df_comments.drop_duplicates(subset=['article_id', 'floor']).reset_index(drop=True)
    else:
        df_comments = pd.DataFrame(columns=['article_id', 'floor', 'time', 'likes', 'text'])
        
    return df_posts, df_comments

def define_theme_categories(theme, df_posts, num_classes=6):
    """Asks Gemini to analyze posts and define suitable categories."""
    client = get_client()
    sample_posts = df_posts.head(30)
    samples_text = ""
    for idx, row in sample_posts.iterrows():
        title = row.get('title', '')
        content = str(row.get('content', ''))[:150]
        samples_text += f"ID: {row.get('article_id')}\n標題: {title}\n摘要: {content}...\n\n"
        
    prompt = f"""
我們正在對一個關於「{theme}」的 Dcard 討論貼文數據集進行主題分類。
請仔細分析以下這些代表性貼文的標題與摘要：

{samples_text}

現在，請為主題「{theme}」定義最多 {num_classes - 1} 個互斥的分類標籤（例如：對工作主題，可以設計為「求職面試」、「薪資福利」、「職場人際」等；對理財主題，可以設計為「股票投資」、「保險規劃」、「理財新手」等）。
這些分類標籤的名稱字數應在 2 到 6 個字之間，並使用繁體中文。
請務必在最後加入一個「其他」分類，使得總共的分類數不超過 {num_classes}。

請僅以 JSON 格式回傳，格式如下：
{{
  "categories": ["類別A", "類別B", "類別C", "其他"]
}}
"""
    
    try:
        response = client.chat.completions.create(
            model=google_model,
            messages=[
                {"role": "system", "content": "你是一個貼文分析與結構化資料輸出助手。請只回傳 JSON 格式物件。"},
                {"role": "user", "content": prompt}
            ],
            response_format={"type": "json_object"},
            temperature=0.2
        )
        content = response.choices[0].message.content.strip()
        res_data = clean_and_parse_json(content)
        
        if isinstance(res_data, dict) and "categories" in res_data:
            categories = res_data["categories"]
        elif isinstance(res_data, list):
            categories = res_data
        else:
            raise ValueError("Invalid categories format returned")
            
        if not isinstance(categories, list) or len(categories) == 0:
            raise ValueError("Empty category list returned")
            
        categories = [str(c).strip() for c in categories]
        if "其他" in categories:
            categories.remove("其他")
        categories.append("其他")
        categories = categories[:num_classes]
        return categories
    except Exception as e:
        print(f"Error defining categories for theme {theme}: {e}")
        return ["主要討論", "經驗分享", "疑難解答", "心情閒聊", "其他"]

def classify_posts(df_posts, categories, theme_name, existing_df=None, progress_callback=None):
    """Classifies Dcard posts and generates summary/key frequencies."""
    client = get_client()
    classified_records = []
    
    existing_data = {}
    if existing_df is not None and not existing_df.empty:
        existing_df['article_id'] = existing_df['article_id'].astype(str)
        for _, row in existing_df.iterrows():
            existing_data[row['article_id']] = {
                'llm_scenario': row.get('llm_scenario', '其他'),
                'llm_reason': row.get('llm_reason', ''),
                'summary': row.get('summary', '暫無'),
                'top_key_freq': row.get('top_key_freq', '[]'),
                'sentiment': row.get('sentiment', '暫無'),
                'tokens': row.get('tokens', '[]'),
                'tokens_v2': row.get('tokens_v2', '[]'),
                'entities': row.get('entities', '[]'),
                'token_pos': row.get('token_pos', '[]'),
            }
            
    categories_str = ", ".join([f"「{c}」" for c in categories])
    total_posts = len(df_posts)
    
    for i, row in df_posts.iterrows():
        art_id = str(row['article_id'])
        
        # Check if already processed
        if art_id in existing_data:
            record = {**row.to_dict()}
            for col, val in existing_data[art_id].items():
                record[col] = val
            classified_records.append(record)
            if progress_callback:
                progress_callback(i + 1, total_posts, f"載入已分類貼文: {art_id}")
            continue
            
        title = row.get('title', '')
        content = str(row.get('content', ''))[:1500]
        
        prompt = f"""
你是一個貼文分類與文本分析助手。
請根據以下 Dcard 貼文，將其歸類到指定的分類之一。
同時請為貼文撰寫一段 100 字以內的簡短繁體中文摘要。
並從內容中提取最關鍵的 5 個核心詞彙（過濾掉無意義詞彙，每個詞字數在 2 到 4 字之間）並估算出現頻率，格式為 `[("詞彙", 頻率), ...]` 的字串表示。

指定的分類標籤：{categories_str}

貼文標題：{title}
貼文內容：{content}

請只以 JSON 格式回傳，格式如下：
{{
  "category": "指定的分類標籤之一",
  "reason": "15字內的簡短分類原因",
  "summary": "100字內摘要",
  "keywords": [["詞彙A", 3], ["詞彙B", 2]]
}}
"""
        try:
            response = client.chat.completions.create(
                model=google_model,
                messages=[
                    {"role": "system", "content": "你是一個貼文分析與分類助手。請只回傳 JSON 格式內容。"},
                    {"role": "user", "content": prompt}
                ],
                response_format={"type": "json_object"},
                temperature=0.0
            )
            res_text = response.choices[0].message.content.strip()
            result = clean_and_parse_json(res_text)
            
            category = result.get('category', '其他').strip()
            
            # Fuzzy match category
            matched = False
            for c in categories:
                if c.strip() == category:
                    category = c
                    matched = True
                    break
            if not matched:
                for c in categories:
                    if c.strip().lower() in category.lower() or category.lower() in c.strip().lower():
                        category = c
                        matched = True
                        break
            if not matched:
                category = '其他'
                
            reason = result.get('reason', '')
            summary = result.get('summary', '暫無')
            keywords = result.get('keywords', [])
            top_key_freq = str([(str(kw).strip(), int(freq)) for kw, freq in keywords if kw])
            
        except Exception as e:
            print(f"Error classifying article {art_id}: {e}")
            category = '其他'
            reason = '分類出錯'
            summary = '暫無'
            top_key_freq = '[]'
            
        record = {
            **row.to_dict(),
            'llm_scenario': category,
            'llm_reason': reason,
            'summary': summary,
            'top_key_freq': top_key_freq,
            'sentiment': '暫無',
            'tokens': '[]',
            'tokens_v2': '[]',
            'entities': '[]',
            'token_pos': '[]'
        }
        classified_records.append(record)
        
        if progress_callback:
            progress_callback(i + 1, total_posts, f"分類貼文: {title[:20]}...")
            
        time.sleep(0.3)
        
    return pd.DataFrame(classified_records)

def classify_comments_batch(df_comments, existing_df=None, progress_callback=None):
    """Classifies Dcard comments in batches for sentiment and interaction types."""
    client = get_client()
    labeled_records = []
    
    existing_data = {}
    if existing_df is not None and not existing_df.empty:
        for _, row in existing_df.iterrows():
            key = (str(row['article_id']), str(row['floor']))
            existing_data[key] = {
                'sentiment_type': row.get('sentiment_type', '中立留言'),
                'interaction_type': row.get('interaction_type', '單純聊天')
            }
            
    to_classify = []
    total_comments = len(df_comments)
    
    for idx, row in df_comments.iterrows():
        key = (str(row['article_id']), str(row['floor']))
        if key in existing_data:
            record = {**row.to_dict()}
            record['sentiment_type'] = existing_data[key]['sentiment_type']
            record['interaction_type'] = existing_data[key]['interaction_type']
            labeled_records.append(record)
        else:
            to_classify.append((idx, row))
            
    batch_size = 15
    total_to_classify = len(to_classify)
    
    for i in range(0, total_to_classify, batch_size):
        batch = to_classify[i:i+batch_size]
        batch_items = []
        for idx, row in batch:
            batch_items.append({
                "id": idx,
                "text": str(row.get('text', ''))[:300]
            })
            
        prompt = f"""
你是一個 Dcard 留言情感與互動類型分類助手。
請將以下 Dcard 留言列表進行分類。

對於每一則留言，請從以下類別中選擇「最貼切」的一個：

情緒傾向（sentiment_type）：
["正面留言", "負面留言", "中立留言"]

互動類型（interaction_type）：
["經驗分享", "建議與意見", "問題詢問", "單純聊天", "回答／解釋", "補充資訊", "感謝回覆"]

輸入留言列表（JSON）：
{json.dumps(batch_items, ensure_ascii=False)}

請嚴格回傳一個 JSON 物件，格式如下：
{{
  "results": [
    {{"id": 留言的id, "sentiment_type": "...", "interaction_type": "..."}},
    ...
  ]
}}
"""
        try:
            response = client.chat.completions.create(
                model=google_model,
                messages=[
                    {"role": "system", "content": "你是一個留言分類器。請只回傳 JSON 格式物件。"},
                    {"role": "user", "content": prompt}
                ],
                response_format={"type": "json_object"},
                temperature=0.0
            )
            res_text = response.choices[0].message.content.strip()
            res_data = clean_and_parse_json(res_text)
            
            if isinstance(res_data, dict) and "results" in res_data:
                results = res_data["results"]
            elif isinstance(res_data, list):
                results = res_data
            else:
                results = []
                
            results_dict = {}
            for item in results:
                if 'id' in item:
                    try:
                        results_dict[int(item['id'])] = item
                    except Exception:
                        pass
                    try:
                        results_dict[str(item['id'])] = item
                    except Exception:
                        pass
            
            for idx, row in batch:
                res = results_dict.get(idx, results_dict.get(str(idx), {}))
                senti = res.get('sentiment_type', '中立留言')
                inter = res.get('interaction_type', '單純聊天')
                
                if senti not in ["正面留言", "負面留言", "中立留言"]:
                    senti = "中立留言"
                if inter not in ["經驗分享", "建議與意見", "問題詢問", "單純聊天", "回答／解釋", "補充資訊", "感謝回覆"]:
                    inter = "單純聊天"
                    
                record = {**row.to_dict()}
                record['sentiment_type'] = senti
                record['interaction_type'] = inter
                labeled_records.append(record)
                
        except Exception as e:
            print(f"Error classifying comment batch: {e}")
            for idx, row in batch:
                record = {**row.to_dict()}
                record['sentiment_type'] = '中立留言'
                record['interaction_type'] = '單純聊天'
                labeled_records.append(record)
                
        if progress_callback:
            progress_callback(len(labeled_records), total_comments, f"分類留言: {len(labeled_records)}/{total_comments}")
            
        time.sleep(0.3)
        
    df_out = pd.DataFrame(labeled_records)
    if df_out.empty:
        df_out = pd.DataFrame(columns=['article_id', 'floor', 'time', 'likes', 'text', 'sentiment_type', 'interaction_type'])
    return df_out

def generate_aggregated_files(df_posts, processed_dir):
    """Replicates the prepare_airport_data.py logic to build keyword_analysis, monthly_trend, and category csvs."""
    os.makedirs(processed_dir, exist_ok=True)
    
    # ── 1. 情境 × 關鍵字聚合 (keyword_analysis.csv) ──
    from collections import defaultdict
    import ast
    
    def parse_keywords(raw):
        try:
            pairs = ast.literal_eval(raw)
            return {kw: freq for kw, freq in pairs if len(kw) >= 2}
        except Exception:
            return {}

    scenario_kw = defaultdict(lambda: defaultdict(int))
    scenario_articles = defaultdict(set)

    for _, row in df_posts.iterrows():
        sc = row['llm_scenario']
        article_id = row['article_id']
        scenario_articles[sc].add(article_id)
        kws = parse_keywords(str(row['top_key_freq']))
        for kw, freq in kws.items():
            scenario_kw[sc][kw] += freq

    records = []
    for sc, kws in scenario_kw.items():
        n = len(scenario_articles[sc])
        for kw, freq in kws.items():
            records.append({
                'context': sc,
                'context_mentions': n,
                'keyword': kw,
                'keyword_freq': freq,
            })

    df_kw = pd.DataFrame(records)
    if df_kw.empty:
        df_kw = pd.DataFrame(columns=['context', 'context_mentions', 'keyword', 'keyword_freq'])
    df_kw.to_csv(os.path.join(processed_dir, 'keyword_analysis.csv'), index=False, encoding='utf-8')
    
    # ── 2. 月度趨勢 (monthly_trend.csv) ──
    tmp = df_posts.copy()
    tmp['article_dates'] = pd.to_datetime(tmp['article_dates'], errors='coerce')
    tmp = tmp.dropna(subset=['article_dates'])
    tmp['year_month'] = tmp['article_dates'].dt.to_period('M').astype(str)

    df_trend = (
        tmp.groupby(['year_month', 'llm_scenario'])
        .size()
        .reset_index(name='article_count')
    )
    if df_trend.empty:
        df_trend = pd.DataFrame(columns=['year_month', 'llm_scenario', 'article_count'])
    df_trend.to_csv(os.path.join(processed_dir, 'monthly_trend.csv'), index=False, encoding='utf-8')
    
    # ── 3. 討論板分佈 (category.csv) ──
    df_cat = (
        df_posts.groupby(['category', 'llm_scenario'])
        .size()
        .reset_index(name='article_count')
    )
    if df_cat.empty:
        df_cat = pd.DataFrame(columns=['category', 'llm_scenario', 'article_count'])
    df_cat.to_csv(os.path.join(processed_dir, 'category.csv'), index=False, encoding='utf-8')

def import_and_process_theme(theme_name, num_classes=6, progress_logger=None):
    """Main workflow to import raw Dcard files, run AI labeling, and generate processed files."""
    try:
        if progress_logger:
            progress_logger(5, "開始讀取並整合原始資料...")
            
        df_posts, df_comments = combine_raw_theme_data(theme_name)
        
        processed_dir = os.path.join(settings.BASE_DIR, 'data', 'processed', theme_name)
        os.makedirs(processed_dir, exist_ok=True)
        
        existing_posts = None
        existing_comments = None
        
        posts_out_path = os.path.join(processed_dir, 'articles_preprocessed_ai.csv')
        comments_out_path = os.path.join(processed_dir, 'comments_labeled.csv')
        
        if os.path.exists(posts_out_path):
            try:
                existing_posts = pd.read_csv(posts_out_path, sep='|', encoding='utf-8')
            except Exception:
                pass
        if os.path.exists(comments_out_path):
            try:
                existing_comments = pd.read_csv(comments_out_path, sep='|', encoding='utf-8')
            except Exception:
                pass
                
        if progress_logger:
            progress_logger(15, "正在用 AI 定義主題分類...")
            
        categories = define_theme_categories(theme_name, df_posts, num_classes)
        print(f"Defined categories for {theme_name}: {categories}")
        
        if progress_logger:
            progress_logger(25, "正在分類貼文內容中...")
            
        def posts_progress(current, total, msg):
            percent = 25 + int((current / total) * 45)
            if progress_logger:
                progress_logger(percent, f"分類貼文 ({current}/{total}): {msg}")
                
        df_posts_processed = classify_posts(
            df_posts, categories, theme_name, 
            existing_df=existing_posts, 
            progress_callback=posts_progress
        )
        
        df_posts_processed.to_csv(posts_out_path, sep='|', index=False, encoding='utf-8-sig')
        
        if progress_logger:
            progress_logger(70, "正在分析留言情感...")
            
        def comments_progress(current, total, msg):
            percent = 70 + int((current / total) * 20)
            if progress_logger:
                progress_logger(percent, f"分類留言 ({current}/{total}): {msg}")
                
        df_comments_processed = classify_comments_batch(
            df_comments, 
            existing_df=existing_comments, 
            progress_callback=comments_progress
        )
        
        df_comments_processed.to_csv(comments_out_path, sep='|', index=False, encoding='utf-8-sig')
        
        if progress_logger:
            progress_logger(90, "正在計算統計資料與生成圖表數據...")
            
        generate_aggregated_files(df_posts_processed, processed_dir)
        
        if progress_logger:
            progress_logger(100, "資料導入與 AI 分類完成！")
            
        return True
    except Exception as e:
        import traceback
        traceback.print_exc()
        if progress_logger:
            progress_logger(-1, f"錯誤: {str(e)}")
        raise e
