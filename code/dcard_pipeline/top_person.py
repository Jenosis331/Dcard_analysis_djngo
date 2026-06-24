import os
import sqlite3
import pandas as pd
from collections import Counter, namedtuple

# Define NerToken so eval() can parse the entities column
NerToken = namedtuple('NerToken', ['word', 'ner', 'idx'])

allowedNE = ['PERSON']

# 由於檔案移動到 code/dcard_pipeline，BASE_DIR 改為向外推 3 層以取得專案根目錄
BASE_DIR = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
db_path = os.path.join(BASE_DIR, "db.sqlite3")

#input_path = os.path.join(BASE_DIR, 'data', 'csv_file', 'dcard_data2_preprocessed_all.csv')
output_path = os.path.join(BASE_DIR, 'data', 'csv_file', 'dcard_top_person.csv')

# Read preprocessed dcard data from SQLite database instead of CSV
conn = sqlite3.connect(db_path)
df = pd.read_sql("SELECT category, entities FROM dcard_data2_preprocessed_all", conn)
conn.close()

news_categories = df['category'].unique().tolist()


def get_top_ner_words():
    top_cate_ner_words = {}  # final result
    counter_all = Counter()  # counter for category '全部'

    for category in news_categories:
        df_group = df[df.category == category]

        words_group = []
        for row in df_group.entities:
            if not isinstance(row, str) or not row.strip():
                continue
            filtered_words = []
            for token in eval(row):
                if (len(token.word) >= 2) and (token.ner in allowedNE):
                    filtered_words.append(token.word)
            words_group += filtered_words

        counter = Counter(words_group)
        counter_all += counter
        topwords = counter.most_common(20)
        top_cate_ner_words[category] = topwords

    top_cate_ner_words['全部'] = counter_all.most_common(20)
    return list(top_cate_ner_words.items())


if __name__ == '__main__':
    results = get_top_ner_words()

    output_df = pd.DataFrame(results, columns=['category', 'top_keys'])
    output_df.to_csv(output_path, index=False, encoding='utf-8-sig')
    print(f'Saved to {output_path}')

    def save_to_sqlite(df_to_save):
        conn = sqlite3.connect(db_path)
        try:
            cursor = conn.cursor()
            cursor.execute("DROP TABLE IF EXISTS dcard_top_person")
            cursor.execute("""
                CREATE TABLE dcard_top_person (
                    category TEXT PRIMARY KEY,
                    top_keys TEXT
                )
            """)
            conn.commit()

            db_df = df_to_save.copy()
            db_df['top_keys'] = db_df['top_keys'].astype(str)
            db_df.to_sql("dcard_top_person", conn, if_exists="append", index=False)
            print(f"SQLite 資料庫：已同步更新 dcard_top_person ({len(db_df)} 筆)")
        except Exception as e:
            print(f"寫入 SQLite 發生錯誤: {e}")
        finally:
            conn.close()

    save_to_sqlite(output_df)

    for cat, topwords in results:
        print(f'\n[{cat}]')
        print(topwords[:10])
