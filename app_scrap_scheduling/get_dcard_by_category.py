import undetected_chromedriver as uc
from selenium.webdriver.common.by import By
import os
import sys
import json
import datetime
import time
import re
import emoji
import random
import pandas as pd
from collections import Counter
from ckip_transformers.nlp import CkipWordSegmenter, CkipPosTagger, CkipNerChunker

import argparse

def init_driver():
    options = uc.ChromeOptions()
    options.add_argument("--start-maximized")
    
    current_dir = os.path.dirname(os.path.abspath(__file__))
    profile_dir = os.path.join(current_dir, "selenium_profile")
    options.add_argument(f"--user-data-dir={profile_dir}")
    options.add_argument("--profile-directory=Default")

    driver = uc.Chrome(
        options=options,
        use_subprocess=True,
        version_main=148,
    )

    return driver

def random_scroll(driver, scroll_times, amount_range, sleep_range):
    """執行頁面隨機滾動，模擬真人行為"""
    for _ in range(scroll_times):
        scroll_amount = random.randint(*amount_range)
        driver.execute_script(f"window.scrollBy(0, {scroll_amount});")
        time.sleep(random.uniform(*sleep_range))

def get_article_list(driver, search_url, max_articles=None):
    """抓取搜尋結果頁面的文章列表，回傳包含文章資訊的字典列表

    Args:
        max_articles: 最多抓取的文章篇數，None 表示不限制
    """
    driver.get(search_url)
    time.sleep(10)

    # 滾動加載整個頁面
    random_scroll(driver, scroll_times=5, amount_range=(2500, 5000), sleep_range=(1.0, 5.0))

    items = driver.find_elements(By.TAG_NAME, "article")
    articles_info = []

    limit = min(max_articles, len(items)) if max_articles is not None else len(items)
    print(f"--- 開始抓取文章列表，共發現 {len(items)} 個項目，預計抓取 {limit} 篇 ---")
    for i, item in enumerate(items[:limit]):
        # 1. 文章日期
        try:
            date_elem = item.find_element(By.XPATH, ".//time").get_attribute("title")
            date_elem = date_elem.split(' ')[0]
        except:
            date_elem = "找不到日期"

        # 3. 標題
        try:
            title_elem = item.find_element(By.XPATH, ".//h2").text
        except:
            title_elem = "找不到標題"

        # 4. 網址與 ID
        try:
            link_elem = item.find_element(By.XPATH, ".//a[@aria-label='查看全文']")
            url = link_elem.get_attribute("href")
            article_id = url.split('/')[-1]
        except:
            url = "找不到連結"
            article_id = "找不到ID"

        # 將單筆資料存成字典
        article_data = {
            "category": "",  # 類別將在 get_article_details() 中抓取
            "article_dates": date_elem,
            "title": title_elem,
            "links": url,
            "article_id": article_id,
            "content": "" # 預留欄位給後續的內文爬取
        }
        articles_info.append(article_data)
        safe_title = emoji.replace_emoji(title_elem, replace='')
        print(f"[{i+1}] 已獲取：{safe_title} ({article_id})")

    return articles_info



def get_article_details(driver, url):
    """前往單篇文章網址，同時抓取內文與所有留言"""
    driver.get(url)
    time.sleep(random.uniform(10.0, 15.0))

    random_scroll(driver, scroll_times=6, amount_range=(2000, 5000), sleep_range=(1.0, 5.0))

    details = {
        "category": "無分類",
        "content": "找不到 content 欄位",
        "comments": []
    }

    # 1. 抓取文章類別
    try:
        category_elem = driver.find_element(By.CSS_SELECTOR, "span.d_d8_1rxfbh5")
        details["category"] = category_elem.text
    except Exception:
        details["category"] = "無分類"

    # 2. 抓取文章內文
    try:
        html_content = driver.page_source
        match = re.search(r'"content":"(.*?)"', html_content)

        if match:
            extracted_content = match.group(1).replace('\\n', ' ')
            text = re.sub(r'https?://\S+', '', extracted_content)
            text = emoji.replace_emoji(text, replace='')
            details["content"] = re.sub(r'\s+', ',', text.strip())

    except Exception as e:
        print(f"處理內文時發生錯誤: {e}")
        details["content"] = "抓取內文時發生錯誤"

    # 3. 抓取文章留言
    try:
        items = driver.find_elements(By.XPATH, "//div[starts-with(@id, 'comment-')]")

        for item in items:
            comment_data = {}

            # 3.1 定位樓層
            try:
                floor_elem = item.find_element(By.XPATH, ".//span[starts-with(text(), 'B')]")
                comment_data["floor"] = floor_elem.text
            except Exception:
                comment_data["floor"] = "找不到樓層"

            # 3.2 定位時間
            try:
                time_elem = item.find_element(By.XPATH, ".//time")
                comment_data["time"] = time_elem.get_attribute("title")
            except Exception:
                comment_data["time"] = "找不到時間"

            # 3.3 定位按讚數
            try:
                likes_elem = item.find_element(
                    By.XPATH,
                    ".//div[contains(@style, '--color-text-secondary')]"
                )
                comment_data["likes"] = likes_elem.text
            except Exception:
                comment_data["likes"] = "0"

            # 3.4 定位留言內容
            try:
                comment_elem = item.find_element(
                    By.XPATH,
                    ".//div[@aria-label='comment content']"
                )

                raw_text = comment_elem.text
                clean_text = emoji.replace_emoji(raw_text, replace='')
                clean_text = clean_text.replace('\n', ' ')
                comment_data["text"] = re.sub(r'\s+', ',', clean_text.strip())

            except Exception:
                comment_data["text"] = "找不到留言內容"

            details["comments"].append(comment_data)

    except Exception as e:
        print(f"處理留言時發生錯誤: {e}")

    return details


def process_with_ckip(df):
    """使用 CKIP 對文章內容進行斷詞、詞性標記、命名實體辨識"""
    print("正在載入 CKIP 模型 (albert-tiny)...")
    ws = CkipWordSegmenter(model="albert-tiny")
    pos = CkipPosTagger(model="albert-tiny")
    ner = CkipNerChunker(model="albert-tiny")

    allowPOS = ['Na', 'Nb', 'Nc', 'VC']

    print("正在進行斷詞...")
    tokens = ws(df.content)
    tokens_pos = pos(tokens)
    word_pos_pair = [list(zip(w, p)) for w, p in zip(tokens, tokens_pos)]
    entity_list = ner(df.content)

    tokens_v2 = []
    for wp in word_pos_pair:
        tokens_v2.append([w for w, p in wp if (len(w) >= 2) and p in allowPOS])

    def word_frequency(wp_pair):
        filtered_words = [word for word, p in wp_pair if (p in allowPOS) and (len(word) >= 2)]
        return Counter(filtered_words).most_common(200)

    keyfreqs = [word_frequency(wp) for wp in word_pos_pair]

    df = df.copy()
    df['tokens'] = tokens
    df['tokens_v2'] = tokens_v2
    df['entities'] = entity_list
    df['token_pos'] = word_pos_pair
    df['top_key_freq'] = keyfreqs
    df['summary'] = "暫無"
    df['sentiment'] = "暫無"

    df = df[['category', 'article_dates', 'article_id', 'title', 'content', 'summary', 'sentiment',
             'tokens', 'tokens_v2', 'entities', 'token_pos', 'top_key_freq', 'links']]
    return df


def save_raw_articles_csv(df, keyword):
    """將原始文章資料存成 CSV"""
    today = datetime.datetime.now()
    safe_date_string = today.strftime("%Y%m%d")
    safe_keyword = keyword.replace(" ", "_")
    output_dir = os.path.join("data", "dcard_data", "by_category")
    os.makedirs(output_dir, exist_ok=True)
    file_name = os.path.join(output_dir, f"dcard_{safe_keyword}_{safe_date_string}.csv")
    df.to_csv(file_name, sep='|', index=False, encoding='utf-8-sig')
    print(f"原始文章資料已儲存為：{file_name}")


def save_preprocessed_csv(df, keyword):
    """將 CKIP 處理後的文章資料存成 CSV"""
    today = datetime.datetime.now()
    safe_date_string = today.strftime("%Y%m%d")
    safe_keyword = keyword.replace(" ", "_")
    output_dir = os.path.join("data", "by_category", "dcard_data2_process")
    os.makedirs(output_dir, exist_ok=True)
    file_name = os.path.join(output_dir, f"dcard_{safe_keyword}_{safe_date_string}_preprocessed.csv")
    df.to_csv(file_name, sep='|', index=False, encoding='utf-8-sig')
    print(f"CKIP 處理結果已儲存為：{file_name}")


def save_sub_preprocessed_csv(df, keyword):
    """將 CKIP 處理後的留言資料存成 CSV"""
    today = datetime.datetime.now()
    safe_date_string = today.strftime("%Y%m%d")
    safe_keyword = keyword.replace(" ", "_")
    output_dir = os.path.join("data", "by_category", "dcard_data2_sub_process")
    os.makedirs(output_dir, exist_ok=True)
    file_name = os.path.join(output_dir, f"dcard_sub_{safe_keyword}_{safe_date_string}_preprocessed.csv")
    df.to_csv(file_name, sep='|', index=False, encoding='utf-8-sig')
    print(f"留言 CKIP 處理結果已儲存為：{file_name}")


def save_category_tokenpos_csv(df_articles, df_sub, keyword):
    """依版別統計關鍵詞頻率（合併文章與留言），存成 CSV"""
    allowedPOS = ['Na', 'Nb', 'Nc']

    # 合併文章與留言的 category + token_pos
    combined = pd.concat(
        [df_articles[['category', 'token_pos']], df_sub[['category', 'token_pos']]],
        ignore_index=True
    )

    news_categories = combined['category'].unique().tolist()
    top_cate_words = {}
    counter_all = Counter()

    for category in news_categories:
        df_group = combined[combined.category == category]
        words_group = []
        for row in df_group.token_pos:
            for word, p in (row if isinstance(row, list) else eval(row)):
                if (len(word) >= 2) and (p in allowedPOS):
                    words_group.append(word)
        counter = Counter(words_group)
        counter_all += counter
        top_cate_words[category] = counter.most_common(100)

    top_cate_words['全部'] = counter_all.most_common(100)

    df_top = pd.DataFrame(list(top_cate_words.items()), columns=['category', 'top_keys'])

    today = datetime.datetime.now()
    safe_date_string = today.strftime("%Y%m%d")
    safe_keyword = keyword.replace(" ", "_")
    output_dir = os.path.join("data", "by_category", "dcard_data3_categray_topkey")
    os.makedirs(output_dir, exist_ok=True)
    file_name = os.path.join(output_dir, f"dcard_{safe_keyword}_{safe_date_string}_category_tokenpos.csv")
    df_top.to_csv(file_name, sep='|', index=False, encoding='utf-8-sig')
    print(f"版別關鍵詞統計已儲存為：{file_name}")


def process_sub_with_ckip(df_sub, df_articles):
    """使用 CKIP 對留言內容進行斷詞、詞性標記、命名實體辨識，並透過 article_id 對應 category"""
    # 透過 article_id 對應 category
    id_to_category = df_articles.set_index('article_id')['category'].to_dict()
    df_sub = df_sub.copy()
    df_sub['category'] = df_sub['article_id'].map(id_to_category).fillna('無分類')

    print("正在載入 CKIP 模型進行留言斷詞 (albert-tiny)...")
    ws = CkipWordSegmenter(model="albert-tiny")
    pos = CkipPosTagger(model="albert-tiny")
    ner = CkipNerChunker(model="albert-tiny")

    allowPOS = ['Na', 'Nb', 'Nc', 'VC']

    text_series = df_sub['text'].fillna('').tolist()

    print("正在進行留言斷詞...")
    tokens = ws(text_series)
    tokens_pos = pos(tokens)
    word_pos_pair = [list(zip(w, p)) for w, p in zip(tokens, tokens_pos)]
    entity_list = ner(text_series)

    tokens_v2 = []
    for wp in word_pos_pair:
        tokens_v2.append([w for w, p in wp if (len(w) >= 2) and p in allowPOS])

    def word_frequency(wp_pair):
        filtered_words = [word for word, p in wp_pair if (p in allowPOS) and (len(word) >= 2)]
        return Counter(filtered_words).most_common(200)

    keyfreqs = [word_frequency(wp) for wp in word_pos_pair]

    df_sub['tokens'] = tokens
    df_sub['tokens_v2'] = tokens_v2
    df_sub['entities'] = entity_list
    df_sub['token_pos'] = word_pos_pair
    df_sub['top_key_freq'] = keyfreqs

    df_sub = df_sub[['category', 'article_id', 'floor', 'time', 'likes', 'text',
                      'tokens', 'tokens_v2', 'entities', 'token_pos', 'top_key_freq']]
    return df_sub


def save_to_comments_csv(articles, keyword):
    """將爬取到的文章資料中的「留言」獨立抽出來，存成明細 CSV 檔案，並回傳 DataFrame"""
    if not articles:
        print("沒有資料可以存檔！")
        return None

    # 1. 準備一個大箱子，用來裝所有文章的所有留言
    all_comments = []

    # 2. 把它們全部倒出來
    for article in articles:
        current_article_id = article.get('article_id', '未知ID')
        # 確認這篇文章有留言陣列 (避免有些文章沒留言導致報錯)
        if 'comments' in article:
            for comment in article['comments']:
                comment['article_id'] = current_article_id  # 加上 article_id 欄位
                all_comments.append(comment)

    # 如果抓半天結果完全沒有任何留言，就提早結束
    if not all_comments:
        print("沒有任何留言可以存檔！")
        return None

    # 3. 把這個純淨的「留言總清單」交給 Pandas
    df = pd.DataFrame(all_comments)

    # 4. 指定欄位順序
    df = df[['article_id', 'floor', 'time', 'likes', 'text']]

    today = datetime.datetime.now()
    safe_date_string = today.strftime("%Y%m%d")
    safe_keyword = keyword.replace(" ", "_")
    output_dir = os.path.join("data", "dcard_data", "by_category")
    os.makedirs(output_dir, exist_ok=True)
    file_name = os.path.join(output_dir, f"dcard_sub_{safe_keyword}_{safe_date_string}.csv")

    # 5. 存檔並回傳 DataFrame
    df.to_csv(file_name, index=False, encoding='utf-8-sig')
    print(f"留言明細已成功儲存為：{file_name}")
    return df



def main():
    """主程式執行流程"""
    today = datetime.datetime.now()
    print(f"今天的日期是：{today.strftime('%Y/%m/%d')}")
    
    # 載入關鍵字邏輯
    keywords = []
    
    # 支援 1: --keywords 格式 (如 "--keywords", "tech_job,job")
    if "--keywords" in sys.argv:
        try:
            kw_idx = sys.argv.index("--keywords") + 1
            if kw_idx < len(sys.argv):
                raw_kws = sys.argv[kw_idx]
                keywords = [k.strip() for k in raw_kws.split(",") if k.strip()]
                print(f"從 --keywords 參數解析到關鍵字：{keywords}")
        except Exception as e:
            print(f"解析 --keywords 參數錯誤: {e}")
            
    # 支援 2: 直接傳遞 positional 參數 (如 "tech_job", "job")
    if not keywords and len(sys.argv) > 1:
        keywords = sys.argv[1:]
        print(f"從 positional 參數讀取關鍵字：{keywords}")
        
    # 支援 3: 從 crawler_keywords.json 載入
    if not keywords:
        script_dir = os.path.dirname(os.path.abspath(__file__))
        json_path = os.path.join(script_dir, "crawler_keywords.json")
        default_keywords = ["tech_job", "job", "talk", "youtuber", "trending"]
        if os.path.exists(json_path):
            try:
                with open(json_path, "r", encoding="utf-8") as f:
                    data = json.load(f)
                    keywords = data.get("keywords", default_keywords)
                print(f"從設定檔 crawler_keywords.json 載入關鍵字：{keywords}")
            except Exception as e:
                keywords = default_keywords
                print(f"讀取設定檔時發生錯誤，使用預設值：{e}")
        else:
            keywords = default_keywords
            print(f"未找到設定檔，使用預設關鍵字：{keywords}")
            
    max_articles = 1  # 設定最多抓取篇數，改為 None 表示不限制 

    # 1. 啟動瀏覽器
    print("正在啟動瀏覽器...")
    driver = init_driver()
    time.sleep(5)  # 給瀏覽器一點時間啟動

    try:
        for keyword in keywords:
            # target_url = f"https://www.dcard.tw/search?query={keyword}"
            target_url = f"https://www.dcard.tw/f/{keyword}"
            print(f"\n{'=' * 40}")
            print(f"開始處理關鍵字：{keyword}")
            print(f"{'=' * 40}")

            # 2. 抓取文章列表
            articles = get_article_list(driver, target_url, max_articles=max_articles)
            if not articles:
                print(f"警告：未找到關於看板/關鍵字 [{keyword}] 的文章！跳過。")
                continue

            # 3. 逐一抓取單篇文章內文
            print("-" * 30)
            print(f"總共有 {len(articles)} 個商品準備爬取內文！")
            print("-" * 30)

            for article in articles:
                url = article['links']
                if url == "找不到連結":
                    continue
                
                time.sleep(5)
                details = get_article_details(driver, url)

                # 將抓到的內文存回原本的字典中
                article['category'] = details['category']
                article['content'] = details['content']
                article['comments'] = details['comments']

                # 預防被鎖，單篇抓完休息一下
                time.sleep(random.uniform(10.0, 20.0))

            # 輸出檔案 1：原始文章 CSV
            df_articles = pd.DataFrame(articles, columns=['category', 'article_dates', 'article_id', 'title', 'content', 'links'])
            save_raw_articles_csv(df_articles, keyword)

            # 輸出檔案 2：留言明細 CSV（回傳 df 供後續處理）
            # df_sub = save_to_comments_csv(articles, keyword)

            # 輸出檔案 3：文章 CKIP 處理
            # df_processed = process_with_ckip(df_articles)
            # save_preprocessed_csv(df_processed, keyword)

            # 輸出檔案 4：留言 CKIP 處理（透過 article_id 對應 category）
            # if df_sub is not None:
            #     df_sub_processed = process_sub_with_ckip(df_sub, df_articles)
            #     save_sub_preprocessed_csv(df_sub_processed, keyword)

            #     # 輸出檔案 5：版別關鍵詞統計（合併文章 + 留言）
            #     save_category_tokenpos_csv(df_processed, df_sub_processed, keyword)
            # else:
            #     # 如果沒有留言，僅用文章資料產生版別統計
            #     save_category_tokenpos_csv(df_processed, pd.DataFrame(columns=['category', 'token_pos']), keyword)

            print(f"關鍵字 [{keyword}] 爬取完畢！")

        print("\n所有關鍵字爬取完畢！")

    finally:
        # 無論程式是成功跑完還是中間報錯，確保最後都會關閉瀏覽器
        driver.quit()

if __name__ == "__main__":
    main()