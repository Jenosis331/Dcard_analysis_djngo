import pandas as pd
import os


# ======================
# 路徑設定
# ======================
# 由於檔案移動到 code/dcard_pipeline，BASE_DIR 改為向外推 3 層以取得專案根目錄
BASE_DIR = os.path.dirname(
    os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
)

# 統一輸出路徑至 data/comments_processed
output_path = os.path.join(
    BASE_DIR,
    "data",
    "comments_processed",
    "dcard_data1_sub_all.csv"
)


# ======================
# 1. 讀取資料夾中的所有 csv
# ======================
new_dfs = []

for subfolder in ["by_category", "by_keyword"]:
    folder_path = os.path.join(BASE_DIR, "data", "dcard_data", subfolder)
    if os.path.exists(folder_path):
        for file in os.listdir(folder_path):
            # 看板爬取與關鍵字搜尋皆放在該模式目錄，留言明細檔案名稱開頭是 dcard_sub_
            if file.endswith(".csv") and file.startswith("dcard_sub_"):
                file_path = os.path.join(folder_path, file)

                try:
                    df = pd.read_csv(
                        file_path,
                        sep=",",
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
    raise ValueError("爬蟲資料夾中找不到留言 csv 檔")


# ======================
# 3. 合併所有 csv
# ======================
merged_df = pd.concat(
    new_dfs,
    ignore_index=True
)

print(f"總共合併 {len(merged_df)} 筆資料")


# ======================
# 4. 建立輸出資料夾
# ======================
os.makedirs(
    os.path.dirname(output_path),
    exist_ok=True
)


# ======================
# 5. 儲存
# 會直接覆蓋原本的 dcard_data1_sub_all.csv
# ======================
merged_df.to_csv(
    output_path,
    sep="|",
    index=False,
    encoding="utf-8-sig"
)


# ======================
# 6. 完成訊息
# ======================
print()
print("====== 完成 ======")
print(f"合併後總筆數：{len(merged_df)}")
print(f"輸出檔案：{output_path}")
