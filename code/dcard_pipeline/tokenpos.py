import os
import sqlite3
from collections import Counter
import pandas as pd

# 由於檔案移動到 code/dcard_pipeline，BASE_DIR 改為向外推 3 層以取得專案根目錄
BASE_DIR = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
db_path = os.path.join(BASE_DIR, "db.sqlite3")

#input_path = os.path.join(BASE_DIR, 'data', 'csv_file', 'dcard_data2_preprocessed_all.csv')
output_path = os.path.join(BASE_DIR, 'data', 'csv_file', 'dcard_data3_tokenpos_all.csv')

# 從 SQLite 資料庫讀取 dcard_data2_preprocessed_all
conn = sqlite3.connect(db_path)
df = pd.read_sql("SELECT category, token_pos FROM dcard_data2_preprocessed_all", conn)
conn.close()

news_categories = df['category'].unique().tolist()
# Filter condition: two words and specified POS
# 過濾條件:兩個字以上 特定的詞性
allowedPOS=['Na','Nb','Nc']

# 
# get topk keyword function
def get_top_words():
    top_cate_words={}
    counter_all = Counter()
    for category in news_categories:

        df_group = df[df.category == category]

        # concatenate all filtered words in the same category
        words_group = []
        for row in df_group.token_pos:
            if not isinstance(row, str) or not row.strip():
                continue

            # filter words for each news
            filtered_words =[]
            for (word, pos) in eval(row):
                if (len(word) >= 2) & (pos in allowedPOS):
                    filtered_words.append(word)

            # concatenate filtered words  
            words_group += filtered_words

        # now we can count word frequency
        counter = Counter( words_group )

        # counter 
        counter_all += counter
        topwords = counter.most_common(100)

        # store topwords
        top_cate_words[category]= topwords

    # Process category '全部'
    top_cate_words['全部'] = counter_all.most_common(100)
    
    # To conveniently save data using pandas, we should convert dict to list.
    return list(top_cate_words.items())

top_group_words = get_top_words()
df_top_group_words = pd.DataFrame(top_group_words, columns = ['category','top_keys'])
df_top_group_words.to_csv(output_path, sep='|', index=False)


def save_to_sqlite(df_to_save):
    conn = sqlite3.connect(db_path)
    try:
        cursor = conn.cursor()
        cursor.execute("DROP TABLE IF EXISTS dcard_data3_tokenpos_all")
        cursor.execute("""
            CREATE TABLE dcard_data3_tokenpos_all (
                category TEXT PRIMARY KEY,
                top_keys TEXT
            )
        """)
        conn.commit()

        # Convert top_keys (list of tuples/list) to string representation before saving to SQLite
        # df_to_save['top_keys'] = df_to_save['top_keys'].astype(str)
        # Note: top_keys is already a list of tuples, pandas to_sql can write it as string or object.
        # But to be safe, let's copy and convert it to string.
        db_df = df_to_save.copy()
        db_df['top_keys'] = db_df['top_keys'].astype(str)
        db_df.to_sql("dcard_data3_tokenpos_all", conn, if_exists="append", index=False)
        print(f"SQLite 資料庫：已同步更新 dcard_data3_tokenpos_all ({len(db_df)} 筆)")
    except Exception as e:
        print(f"寫入 SQLite 發生錯誤: {e}")
    finally:
        conn.close()

save_to_sqlite(df_top_group_words)
