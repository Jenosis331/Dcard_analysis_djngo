import time
import pandas as pd
from typing import Literal
from pydantic import BaseModel, Field
from google import genai
from google.genai import types


# ===== 1. API 與檔案設定 =====
client = genai.Client(api_key=api_key)

INPUT_CSV = "/content/dcard_機場_20260421_preprocessed.csv"
OUTPUT_CSV = "dcard_機場_20260421_preprocessed_ai.csv"
SEP = "|"

# ===== 2. 分類類別：名稱要前後完全一致 =====
ALLOWED_SCENARIOS = [
    "出入境流程",
    "航班異常",
    "行李問題",
    "機場交通",
    "機場設施服務",
    "旅遊規劃資訊",
    "工作求職",
    "情緒與經驗",
    "治安與突發事件",
    "其他"
]

# ===== 3. 結構化輸出 schema =====
class ScenarioResult(BaseModel):
    scenario: Literal[
        "出入境流程",
        "航班異常",
        "行李問題",
        "機場交通",
        "機場設施服務",
        "旅遊規劃資訊",
        "工作求職",
        "情緒與經驗",
        "治安與突發事件",
        "其他"
    ] = Field(description="文章最主要的單一語意分類，只能選一個。")

    reason: str = Field(description="20字內簡短原因。")

# ===== 4. 分類函式 =====
def classify_article(title, content):
    title = "" if pd.isna(title) else str(title).strip()
    content = "" if pd.isna(content) else str(content).strip()
    content_for_model = content[:2500]

    prompt = f"""
你是一個論壇文章分類助手。
請根據文章的 title 與 content，判斷「最主要」的單一語意分類。

【規則】
1. 只能從指定類別中選擇一個主分類，不能複選。
2. 只有完全不符合時才可選「其他」。
3. 請以文章主要討論重點為準，不要只看單一關鍵字。
4. 即使文章同時提到多個主題，也要選出最核心的一個。

【可選類別】
- 出入境流程
- 航班異常
- 行李問題
- 機場交通
- 機場設施服務
- 旅遊規劃資訊
- 工作求職
- 情緒與經驗
- 治安與突發事件
- 其他

【類別參考】
出入境流程：登機、報到、護照、安檢、轉機、入境、出境
航班異常：延誤、取消、班機問題、改票
行李問題：托運、超重、行李遺失、損壞
機場交通：接機、送機、捷運、高鐵、客運、停車、到市區
機場設施服務：免稅店、餐廳、貴賓室、Wi-Fi、休息區
旅遊規劃資訊：路線安排、航廈資訊、搭乘建議、周邊資訊
工作求職：地勤、空服員、招募、面試、薪資、通勤
情緒與經驗：離別、感動、焦慮、緊張、心得、經驗分享
治安與突發事件：偷竊、警方、衝突、受傷、安全事件

title: {title}
content: {content_for_model}
"""

    try:
        response = client.models.generate_content(
            model="gemini-3.1-flash-lite-preview",
            contents=prompt,
            config=types.GenerateContentConfig(
                temperature=0,
                response_mime_type="application/json",
                response_schema=ScenarioResult,
            )
        )

        raw_text = response.text.strip()

        # SDK 在 schema 模式下通常會直接給合法 JSON
        parsed = ScenarioResult.model_validate_json(raw_text)

        return {
            "scenario": parsed.scenario,
            "reason": parsed.reason,
            "raw_response": raw_text,
            "error": ""
        }

    except Exception as e:
        return {
            "scenario": "其他",
            "reason": "",
            "raw_response": "",
            "error": str(e)
        }

# ===== 5. 讀取 CSV =====
df = pd.read_csv(INPUT_CSV, sep=SEP)

# 檢查必要欄位
required_cols = ["title", "content"]
missing_cols = [col for col in required_cols if col not in df.columns]
if missing_cols:
    raise ValueError(f"CSV 缺少必要欄位: {missing_cols}")

# 若欄位已存在就沿用，避免重跑整份
for col in ["llm_scenario", "llm_reason", "llm_raw_response", "llm_error"]:
    if col not in df.columns:
        df[col] = ""

# ===== 6. 逐筆分類 =====
for i, row in df.iterrows():
    # 如果已經有分類結果，可跳過
    if str(df.at[i, "llm_scenario"]).strip():
        continue

    result = classify_article(row["title"], row["content"])

    df.at[i, "llm_scenario"] = result["scenario"]
    df.at[i, "llm_reason"] = result["reason"]
    df.at[i, "llm_raw_response"] = result["raw_response"]
    df.at[i, "llm_error"] = result["error"]

    title_str = "" if pd.isna(row["title"]) else str(row["title"])
    print(f"[{i+1}/{len(df)}] {result['scenario']} | {title_str[:30]}")

    # 每 10 筆先暫存一次
    if (i + 1) % 10 == 0:
        df.to_csv(OUTPUT_CSV, sep=SEP, index=False, encoding="utf-8-sig")
        print(f"已暫存：{OUTPUT_CSV}")

    time.sleep(1)

# ===== 7. 最後輸出 =====
df.to_csv(OUTPUT_CSV, sep=SEP, index=False, encoding="utf-8-sig")

print("\n分類完成，類別分布：")
print(df["llm_scenario"].value_counts(dropna=False))