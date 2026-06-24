import os
import json
import time
import pandas as pd
from google import genai
from google.genai import types
from dotenv import load_dotenv


# =========================
# 1. 基本設定
# =========================
# 由於檔案移動到 code/dcard_pipeline，BASE_DIR 改為向外推 3 層以取得專案根目錄
BASE_DIR = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

# 載入專案根目錄的 .env
load_dotenv(os.path.join(BASE_DIR, ".env"))

GEMINI_API_KEY = os.getenv("GEMINI_API_KEY")

INPUT_FILE = os.path.join(BASE_DIR, "data", "comments_processed", "dcard_data1_sub_all.csv")
OUTPUT_FILE = os.path.join(BASE_DIR, "data", "comments_processed", "dcard_data1_sub_all_sorted_labeled.csv")

SEP = "|"
ENCODING = "utf-8-sig"

# 是否只處理前 N 筆
LIMIT_ROWS = 525   # 如果要全部處理，改成 None

# API 間隔秒數
SLEEP_SECONDS = 1

if not GEMINI_API_KEY:
    raise ValueError("找不到 GEMINI_API_KEY，請確認專案根目錄下的 .env 檔案中是否已設定")

client = genai.Client(api_key=GEMINI_API_KEY)


INTERACTION_TYPES = [
    "問題詢問",
    "回答／解釋",
    "補充資訊",
    "經驗分享",
    "建議與意見",
    "單純聊天",
    "感謝回覆",
]

SENTIMENT_TYPES = [
    "正面留言",
    "負面留言",
    "中立留言",
]


# =========================
# 2. Gemini 留言分類函式
# =========================
def classify_comment(text: str) -> dict:
    if pd.isna(text) or str(text).strip() == "":
        return {
            "互動類型": "單純聊天",
            "情緒傾向": "中立留言",
        }

    prompt = f"""
你是一個 Dcard 留言分類助手。
請根據留言內容，分類出「互動類型」與「情緒傾向」。

互動類型只能從以下選一個：
{INTERACTION_TYPES}

情緒傾向只能從以下選一個：
{SENTIMENT_TYPES}

留言內容：
{text}

請只回傳 JSON，格式如下：
{{
  "互動類型": "...",
  "情緒傾向": "..."
}}
"""

    try:
        response = client.models.generate_content(
            model="gemini-3.1-flash-lite",
            contents=prompt,
            config=types.GenerateContentConfig(
                response_mime_type="application/json",
                temperature=0
            )
        )

        result = json.loads(response.text)

        interaction = result.get("互動類型", "單純聊天")
        sentiment = result.get("情緒傾向", "中立留言")

        if interaction not in INTERACTION_TYPES:
            interaction = "單純聊天"

        if sentiment not in SENTIMENT_TYPES:
            sentiment = "中立留言"

        return {
            "互動類型": interaction,
            "情緒傾向": sentiment,
        }

    except Exception as e:
        print(f"分類失敗：{e}")
        return {
            "互動類型": "單純聊天",
            "情緒傾向": "中立留言",
        }


# =========================
# 3. 主程式
# =========================
def main():
    print(f"讀取檔案：{INPUT_FILE}")

    df = pd.read_csv(
        INPUT_FILE,
        sep=SEP,
        encoding=ENCODING
    )

    # 檢查必要欄位
    if "article_id" not in df.columns:
        raise ValueError("找不到 article_id 欄位，無法排序")

    if "text" not in df.columns:
        raise ValueError("找不到 text 欄位，無法分類留言")

    # article_id 轉成數值
    df["article_id"] = pd.to_numeric(
        df["article_id"],
        errors="coerce"
    )

    # 依 article_id 排序
    df = df.sort_values(
        by="article_id",
        ascending=True
    ).reset_index(drop=True)

    # 只取前 N 筆
    if LIMIT_ROWS is not None:
        df = df.head(LIMIT_ROWS).reset_index(drop=True)

    print(f"總共要分類 {len(df)} 筆留言")

    results = []

    for idx, row in df.iterrows():
        text = row.get("text", "")

        print(f"正在分類第 {idx + 1}/{len(df)} 筆留言...")

        label = classify_comment(text)
        results.append(label)

        time.sleep(SLEEP_SECONDS)

    label_df = pd.DataFrame(results)

    df["interaction_type"] = label_df["互動類型"]
    df["sentiment_type"] = label_df["情緒傾向"]

    df.to_csv(
        OUTPUT_FILE,
        sep=SEP,
        index=False,
        encoding=ENCODING
    )

    print(f"完成！已排序並分類輸出：{OUTPUT_FILE}")


if __name__ == "__main__":
    main()
