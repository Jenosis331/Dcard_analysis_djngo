"""
機場 Dcard 資料前處理腳本
輸入：app_airport_analysis/dataset/dcard_機場_20260418_preprocessed_ai.csv
輸出：app_airport_analysis/dataset/ 下三個分析用 CSV
"""

import ast
import os
import sys
from collections import defaultdict

import pandas as pd

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
DATASET_DIR = os.path.join(BASE_DIR, '..', 'app_airport_analysis', 'dataset')
SRC = os.path.join(DATASET_DIR, 'dcard_機場_20260418_preprocessed_ai.csv')


def load_raw():
    df = pd.read_csv(SRC, sep='|', encoding='utf-8')
    df['article_dates'] = pd.to_datetime(df['article_dates'], format='%Y/%m/%d', errors='coerce')
    df['llm_scenario'] = df['llm_scenario'].fillna('其他').replace('', '其他')
    return df


def parse_keywords(raw):
    """Parse top_key_freq string like "[('kw', 3), ...]" into dict {kw: freq}."""
    try:
        pairs = ast.literal_eval(raw)
        return {kw: freq for kw, freq in pairs if len(kw) >= 2}
    except Exception:
        return {}


# ── 1. 情境 × 關鍵字聚合 (airport_keyword_analysis.csv) ──────────────────────
def build_keyword_analysis(df):
    scenario_kw = defaultdict(lambda: defaultdict(int))
    scenario_articles = defaultdict(set)

    for _, row in df.iterrows():
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

    out = pd.DataFrame(records)
    path = os.path.join(DATASET_DIR, 'airport_keyword_analysis.csv')
    out.to_csv(path, index=False, encoding='utf-8')
    print(f'[OK] airport_keyword_analysis.csv  ({len(out)} rows)')
    return out


# ── 2. 月度趨勢 (airport_monthly_trend.csv) ──────────────────────────────────
def build_monthly_trend(df):
    tmp = df.dropna(subset=['article_dates']).copy()
    tmp['year_month'] = tmp['article_dates'].dt.to_period('M').astype(str)

    trend = (
        tmp.groupby(['year_month', 'llm_scenario'])
        .size()
        .reset_index(name='article_count')
    )
    path = os.path.join(DATASET_DIR, 'airport_monthly_trend.csv')
    trend.to_csv(path, index=False, encoding='utf-8')
    print(f'[OK] airport_monthly_trend.csv     ({len(trend)} rows)')
    return trend


# ── 3. 討論板分佈 (airport_category.csv) ─────────────────────────────────────
def build_category(df):
    cat = (
        df.groupby(['category', 'llm_scenario'])
        .size()
        .reset_index(name='article_count')
    )
    path = os.path.join(DATASET_DIR, 'airport_category.csv')
    cat.to_csv(path, index=False, encoding='utf-8')
    print(f'[OK] airport_category.csv          ({len(cat)} rows)')
    return cat


if __name__ == '__main__':
    df = load_raw()
    print(f'Loaded {len(df)} rows from source CSV')
    build_keyword_analysis(df)
    build_monthly_trend(df)
    build_category(df)
    print('Done.')
