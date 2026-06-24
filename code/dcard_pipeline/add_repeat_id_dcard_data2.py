import pandas as pd
import os
import sqlite3
import sys

# 確保在 Windows 環境下主控台中文輸出正常
if hasattr(sys.stdout, 'reconfigure'):
    sys.stdout.reconfigure(encoding='utf-8')

# 專案資料庫路徑 (專案根目錄下的 db.sqlite3)
# 由於檔案移動到 code/dcard_pipeline，BASE_DIR 改為向外推 3 層以取得專案根目錄
BASE_DIR = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
db_path = os.path.join(BASE_DIR, "db.sqlite3")

# 本次新增資料
input_path = os.path.join(BASE_DIR, "data", "csv_file", "csv_tmp", "dcard_data2_preprocessed_tmp.csv")

# 總資料庫
output_path = os.path.join(BASE_DIR, "data", "csv_file", "dcard_data2_preprocessed_all.csv")

# 1. 讀取本次資料
new_df = pd.read_csv(input_path, sep="|")

# 本次資料內部去重
new_df = new_df.drop_duplicates(
    subset=["article_id"],
    keep="first"
)
new_count = len(new_df)

# 2. 連接 SQLite 資料庫並比對去重
conn = sqlite3.connect(db_path)
insert_df = pd.DataFrame()
add_count = 0

try:
    cursor = conn.cursor()
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS dcard_data2_preprocessed_all (
            article_id TEXT PRIMARY KEY,
            category TEXT,
            article_dates TEXT,
            title TEXT,
            content TEXT,
            summary TEXT,
            sentiment REAL,
            tokens TEXT,
            tokens_v2 TEXT,
            entities TEXT,
            token_pos TEXT,
            top_key_freq TEXT,
            links TEXT
        )
    """)
    conn.commit()

    # 讀取現有資料庫中的 ID
    existing_db_ids = pd.read_sql_query("SELECT article_id FROM dcard_data2_preprocessed_all", conn)
    existing_set = set(existing_db_ids["article_id"].astype(str))

    # 比對資料庫，只保留資料庫中沒有的新文章
    insert_df = new_df[~new_df["article_id"].astype(str).isin(existing_set)]
    add_count = len(insert_df)

    if add_count > 0:
        # 寫入 SQLite
        insert_df.to_sql("dcard_data2_preprocessed_all", conn, if_exists="append", index=False)
        print(f"SQLite 資料庫：已同步新增 {add_count} 筆預處理資料")
    else:
        print("SQLite 資料庫：無新增預處理資料 (已同步)")

except Exception as e:
    print(f"寫入 SQLite 發生錯誤: {e}")
finally:
    conn.close()

# 3. 同步寫入總 CSV 檔案 (僅新增部分)
if add_count > 0:
    if os.path.exists(output_path):
        # 有總資料庫時，以追加模式寫入
        insert_df.to_csv(
            output_path,
            sep="|",
            mode="a",
            header=False,
            index=False,
            encoding="utf-8-sig"
        )
    else:
        # 第一次建立總資料庫
        insert_df.to_csv(
            output_path,
            sep="|",
            index=False,
            encoding="utf-8-sig"
        )

# 4. 印出結果
print(f"本次讀取 {new_count} 筆")
print(f"新增 {add_count} 筆")
print(f"忽略 {new_count - add_count} 筆重複資料")
