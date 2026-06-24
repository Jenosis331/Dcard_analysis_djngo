import pandas as pd
import os


# ======================
# 路徑設定
# ======================
# 由於檔案移動到 code/dcard_pipeline，BASE_DIR 改為向外推 3 層以取得專案根目錄
BASE_DIR = os.path.dirname(
    os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
)

output_path = os.path.join(
    BASE_DIR,
    "data",
    "csv_file",
    "csv_tmp",
    "dcard_data1_tmp.csv"
)


# ======================
# 1. 讀取資料夾中的所有 csv
# ======================
new_dfs = []

for subfolder in ["by_category"]:
    folder_path = os.path.join(BASE_DIR, "data", "dcard_data", subfolder)
    if os.path.exists(folder_path):
        for file in os.listdir(folder_path):
            # 看板爬取與關鍵字搜尋皆放在該模式目錄，文章主檔檔案名稱開頭不是 dcard_sub_
            if file.endswith(".csv") and not file.startswith("dcard_sub_"):
                file_path = os.path.join(folder_path, file)

                try:
                    df = pd.read_csv(
                        file_path,
                        sep="|",
                        encoding="utf-8"
                    )
                    new_dfs.append(df)
                    print(f"讀取成功：{subfolder}/{file}，共 {len(df)} 筆")

                except Exception as e:
                    print(f"讀取失敗：{subfolder}/{file}")
                    print(e)


# ======================
# 2. 檢查是否有讀到資料
# ======================
if len(new_dfs) == 0:
    raise ValueError("爬蟲資料夾中找不到文章 csv 檔")


# ======================
# 3. 合併本次資料夾內所有 csv
# ======================
new_df = pd.concat(new_dfs, ignore_index=True)

print(f"本次讀取到 {len(new_df)} 筆資料")


# ======================
# 4. 檢查 article_id 欄位是否存在
# ======================
if "article_id" not in new_df.columns:
    raise ValueError("找不到 article_id 欄位，無法去重")


# ======================
# 5. 只使用本次新資料
# 完全覆蓋舊的 dcard_data1_tmp.csv
# ======================
merged_df = new_df.copy()

before_count = len(merged_df)

merged_df = merged_df.drop_duplicates(
    subset=["article_id"],
    keep="last"
)

after_count = len(merged_df)


# ======================
# 6. 建立輸出資料夾
# ======================
os.makedirs(
    os.path.dirname(output_path),
    exist_ok=True
)


# ======================
# 7. 儲存
# 這裡會直接覆蓋原本的 dcard_data1_tmp.csv
# ======================
merged_df.to_csv(
    output_path,
    sep="|",
    index=False,
    encoding="utf-8-sig"
)


# ======================
# 8. 統計資訊
# ======================
print()
print("====== 完成 ======")
