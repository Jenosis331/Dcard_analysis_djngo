# -*- coding: utf-8 -*-
"""
csv_sentiment_summary_tool.py

功能：
讀取 CSV，依照 content 欄位補上 summary 與 sentiment 欄位，並輸出成新的 CSV。

使用前安裝：
pip install pandas transformers torch tqdm

基本使用：
1. 直接修改下方「使用者設定區」的 INPUT_DATA / OUTPUT_DATA
2. 執行：python csv_sentiment_summary_tool.py

CSV 預設分隔符號為 |，若你的檔案是逗號分隔，請把 SEP 改成 ","。
"""

import os
from typing import Dict, Optional

import pandas as pd
from tqdm import tqdm

import torch
from transformers import AutoTokenizer, AutoModelForSequenceClassification


# ==========================
# 使用者設定區
# ==========================
# 由於檔案移動到 code/dcard_pipeline，BASE_DIR 改為向外推 3 層以取得專案根目錄
BASE_DIR = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
INPUT_DATA = os.path.join(BASE_DIR, "data", "csv_file", "csv_tmp", "dcard_data2_preprocessed_tmp.csv")
OUTPUT_DATA = os.path.join(BASE_DIR, "data", "csv_file", "csv_tmp", "dcard_data2_preprocessed_tmp.csv")

SEP = "|"                 # 你的 CSV 分隔符號，常見為 "|" 或 ","
ENCODING = "utf-8-sig"    # 若讀取失敗，可改成 "utf-8" 或 "cp950"
TEXT_COLUMN = "content"   # 要分析的文字欄位

MODEL_NAME = "clhuang/albert-sentiment"
MAX_LENGTH = 300

SUMMARY_MAX_CHARS = 100    # 摘要保留前 N 個字，可自行調整
OVERWRITE_EXISTING = True  # True：已有 sentiment/summary 也重新產生；False：只補空值
REMOVE_DUPLICATE_HEADER_ROWS = True  # 避免 CSV 中間重複出現標頭列
# ==========================


_model = None
_tokenizer = None
_device = None


def load_sentiment_model() -> None:
    """載入 Hugging Face 情緒分析模型。"""
    global _model, _tokenizer, _device

    if _model is not None and _tokenizer is not None:
        return

    _device = torch.device("cuda" if torch.cuda.is_available() else "cpu")
    print(f"載入情緒分析模型：{MODEL_NAME}")
    print(f"使用裝置：{_device}")

    _tokenizer = AutoTokenizer.from_pretrained(MODEL_NAME)
    _model = AutoModelForSequenceClassification.from_pretrained(MODEL_NAME)
    _model.to(_device)
    _model.eval()


def clean_text(text: object) -> str:
    """清理文字，避免 NaN、換行符號造成處理問題。"""
    if pd.isna(text):
        return ""
    return str(text).replace("\r", " ").replace("\n", " ").strip()


def generate_summary(text: object, max_chars: int = SUMMARY_MAX_CHARS) -> str:
    """
    產生簡易摘要。
    目前採用「前 N 字摘要法」，適合大量 CSV 快速處理。
    若之後要接 Gemini / OpenAI / 本地摘要模型，可以只改這個函式。
    """
    text = clean_text(text)
    if not text:
        return ""
    return text[:max_chars]


def get_sentiment_proba(text: object) -> Dict[str, float]:
    """
    回傳 Negative / Positive 機率。
    範例：{'Negative': 0.13, 'Positive': 0.87}
    """
    load_sentiment_model()

    text = clean_text(text)
    if not text:
        return {"Negative": 0.0, "Positive": 0.0}

    inputs = _tokenizer(
        text,
        padding=True,
        truncation=True,
        max_length=MAX_LENGTH,
        return_tensors="pt",
    ).to(_device)

    with torch.no_grad():
        outputs = _model(**inputs)

    probs = outputs.logits.softmax(dim=1)
    return {
        "Negative": round(float(probs[0, 0]), 4),
        "Positive": round(float(probs[0, 1]), 4),
    }


def generate_sentiment(text: object) -> float:
    """
    產生 sentiment 分數。
    這裡沿用 notebook 的做法：取 Positive 機率作為 sentiment。
    越接近 1 代表越正向，越接近 0 代表越負向。
    """
    return get_sentiment_proba(text)["Positive"]


def remove_duplicate_header_rows(df: pd.DataFrame) -> pd.DataFrame:
    """
    移除 CSV 中間重複出現的標頭列。
    例如某些合併 CSV 會在資料列中再次出現 title|content|sentiment...
    """
    if TEXT_COLUMN not in df.columns:
        return df

    mask = df[TEXT_COLUMN].astype(str).str.strip().eq(TEXT_COLUMN)
    removed = int(mask.sum())
    if removed > 0:
        print(f"偵測並移除重複標頭列：{removed} 列")
        df = df.loc[~mask].copy()
    return df


def should_process_value(value: Optional[object]) -> bool:
    """判斷欄位是否需要重新處理。"""
    if OVERWRITE_EXISTING:
        return True
    if value is None:
        return True
    if pd.isna(value):
        return True
    return str(value).strip() == ""


def main() -> None:
    if not os.path.exists(INPUT_DATA):
        raise FileNotFoundError(f"找不到輸入檔案：{INPUT_DATA}")

    print(f"讀取檔案：{INPUT_DATA}")
    df = pd.read_csv(INPUT_DATA, sep=SEP, encoding=ENCODING)

    if TEXT_COLUMN not in df.columns:
        raise ValueError(f"找不到文字欄位：{TEXT_COLUMN}，目前欄位有：{list(df.columns)}")

    if REMOVE_DUPLICATE_HEADER_ROWS:
        df = remove_duplicate_header_rows(df)

    # ==========================
    # 【修正區塊】：確保欄位型態正確
    # ==========================
    # 確保 summary 是字串物件型態
    if "summary" not in df.columns:
        df["summary"] = pd.Series(dtype='object')
        
    # 確保 sentiment 是浮點數型態
    if "sentiment" not in df.columns:
        # 若無此欄位，直接初始化為 float64
        df["sentiment"] = pd.Series(dtype='float64')
    else:
        # 若已有此欄位（可能是之前的空字串），強制轉換為數值，無法轉換的空字串會變成 NaN
        df["sentiment"] = pd.to_numeric(df["sentiment"], errors='coerce')
    # ==========================

    print(f"資料筆數：{len(df)}")
    print("開始產生 summary...")
    for idx in tqdm(df.index, desc="Summary"):
        if should_process_value(df.at[idx, "summary"]):
            df.at[idx, "summary"] = generate_summary(df.at[idx, TEXT_COLUMN])

    print("開始產生 sentiment...")
    load_sentiment_model()
    for idx in tqdm(df.index, desc="Sentiment"):
        if should_process_value(df.at[idx, "sentiment"]):
            df.at[idx, "sentiment"] = generate_sentiment(df.at[idx, TEXT_COLUMN])

    output_dir = os.path.dirname(OUTPUT_DATA)
    if output_dir:
        os.makedirs(output_dir, exist_ok=True)

    df.to_csv(OUTPUT_DATA, sep=SEP, encoding="utf-8-sig", index=False)
    print(f"完成，已輸出：{OUTPUT_DATA}")

if __name__ == "__main__":
    main()
