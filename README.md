# Dcard 輿情分析與搜尋系統 (Dcard Opinion Analysis & Search System)

這是一個基於 **Django** 框架開發的 Dcard 輿情分析、自動爬蟲與智慧搜尋系統。本專案整合了 Selenium 自動化爬蟲、自然語言處理（斷詞與情緒分析）、Chroma 向量資料庫（RAG 檢索增強生成）、Google Gemini 大語言模型（LLM）API，以及 LangChain 智能代理（Agent），提供全方位的 Dcard 輿情監控、分析與問答解決方案。

---

## 🚀 核心功能

### 1. 自助爬蟲與定時排程管理 (`app_scrap_scheduling`)
* **雙爬取模式**：支援「**看板爬取**」與「**關鍵字搜尋**」兩種模式。
* **Selenium 自動化**：使用 Selenium 模擬瀏覽器行為，自動處理動態加載並採集 Dcard 貼文與留言。
* **自動定時排程**：整合 `django-apscheduler`，預設於每日凌晨 02:00 自動執行爬蟲任務與情緒分析。
* **視覺化管理介面**：提供手動即時觸發、查看當前排程狀態以及最近 50 筆的爬蟲執行歷史紀錄（包括成功與否、執行時長、錯誤訊息）。

### 2. 多維度輿情分析與檢索
* **熱門關鍵字分析 (`app_top_keyword`)**：分析特定時間區間內 Dcard 看板的熱門詞彙，並透過 Jieba 進行中文斷詞。
* **熱門人物分析 (`app_top_person`)**：從貼文內容中提取關鍵人物（如政治人物、公眾人物），分析其討論熱度。
* **使用者自訂關鍵字分析 (`app_user_keyword`)**：讓使用者手動輸入關鍵字，即時調研相關貼文趨勢。
* **全文檢索與關聯詞呈現 (`app_user_keyword_association`)**：提供高效的全文搜尋，並自動發掘與搜尋詞高度相關的聯想關鍵字。

### 3. 情緒與意見傾向分析
* **自訂關鍵字情緒分析 (`app_user_keyword_sentiment`)**：計算與關鍵字相關貼文的正向、中立、負向情緒比例與趨勢。
* **Dcard 留言情緒分析 (`app_comment_sentiment`)**：不僅分析貼文主體，還能深入分析文章下方的所有留言情緒，並依據情緒分數進行排序與過濾。

### 4. LLM 智慧輿情報告與 AI 代理
* **Gemini LLM 報告生成 (`app_user_keyword_llm_report`)**：串接 **Google Gemini API**，自動分析關鍵字的情緒分佈與貼文內容，產出結構化的輿情摘要與分析報告。
* **Dcard 輿情智能代理 (`app_poa_langchain`)**：
  * 基於 **LangChain** 框架與 **Chroma 向量資料庫**。
  * 將爬取到的 Dcard 貼文進行向量化（Embedding）並建立索引，實現 RAG（檢索增強生成）。
  * 整合 **Tavily 搜尋 API** 作為外部工具，提供 AI 輿情問答助手，能針對 Dcard 的最新討論內容進行智慧解答。

---

## 📂 專案目錄結構

```text
├── website_configs/               # Django 專案主設定目錄 (settings.py, urls.py, views.py)
├── app_scrap_scheduling/          # 自助爬蟲與排程管理模組 (含 Selenium 爬蟲腳本)
├── app_poa_langchain/             # LangChain 智能代理與向量資料庫模組 (Chroma DB)
├── app_top_keyword/               # 熱門關鍵字分析模組
├── app_top_person/                # 熱門人物提取與分析模組
├── app_user_keyword/              # 使用者自訂關鍵字分析模組
├── app_user_keyword_association/  # 全文檢索與關聯關鍵字模組
├── app_user_keyword_sentiment/    # 自訂關鍵字情緒分析模組
├── app_user_keyword_llm_report/   # Gemini LLM 報告生成模組
├── app_comment_sentiment/         # 留言情緒分析模組
├── app_airport_analysis/          # 機場相關數據分析模組
├── app_airport_search/            # 機場數據檢索模組
├── app_kop/                       # 特定人物 (如柯文哲等) 輿情專版模組
├── code/                          # 數據處理與分析管線 (dcard_pipeline: 斷詞、情緒計算等)
├── data/                          # 儲存爬蟲歷史紀錄與臨時資料的目錄
├── templates/                     # 共用的 HTML 模板檔案
├── db.sqlite3                     # 本地 SQLite 資料庫 (儲存 Dcard 貼文、留言及分析結果)
├── .env                           # 環境變數設定檔 (需自行配置 API Key)
├── Dockerfile                     # 專案 Docker 映像檔建置說明
├── docker-compose.yml             # Docker Compose 容器編排檔
├── requirements.txt               # Python 依賴套件清單
└── manage.py                      # Django 專案管理入口腳本
```

---

## 🛠️ 環境設定與本地安裝

### 1. Prerequisites (準備工作)
* **Python**：建議版本為 `3.12`。
* **瀏覽器環境**：本地執行 Selenium 爬蟲需要安裝 **Google Chrome** 瀏覽器。本專案使用 `undetected-chromedriver` 以避免爬蟲偵測。

### 2. 設定環境變數
在專案根目錄下建立 `.env` 檔案（或編輯已存在的 `.env`），並配置以下 API 金鑰：

```env
# Google Gemini API 金鑰 (用於 LLM 報告生成與 Agent)
GEMINI_API_KEY=your_gemini_api_key_here

# Tavily Search API 金鑰 (用於 Agent 搜尋外部最新資訊)
TAVILY_API_KEY=your_tavily_api_key_here
```

### 3. 本地部署步驟 (Python 虛擬環境)

1. **複製專案並進入目錄**：
   ```bash
   cd website-news-analysis_14_docker
   ```

2. **建立並啟用虛擬環境**：
   ```bash
   python -m venv venv
   # Windows 啟用方式
   .\venv\Scripts\activate
   # macOS/Linux 啟用方式
   source venv/bin/activate
   ```

3. **安裝依賴套件**：
   ```bash
   pip install --upgrade pip
   pip install -r requirements.txt
   ```

4. **資料庫遷移 (Migration)**：
   ```bash
   python manage.py migrate
   ```

5. **啟動 Django 開發伺服器**：
   ```bash
   python manage.py runserver
   ```
   啟動後，使用瀏覽器打開 [http://127.0.0.1:8000/](http://127.0.0.1:8000/) 即可進入系統首頁。

---

## 🐳 Docker 部署步驟

專案已完全容器化，支援透過 **Docker Compose** 一鍵啟動。

1. **確認已配置好 `.env` 檔案**。
2. **使用 Docker Compose 建置並啟動服務**：
   ```bash
   docker-compose up --build
   ```
3. 啟動完成後，即可在本地瀏覽器透過 [http://localhost:8000/](http://localhost:8000/) 存取系統。

---

## 📊 資料庫與向量庫說明

### SQLite 本地資料庫
專案使用 SQLite 作為主要結構化數據儲存，包含以下核心資料表：
* **`dcard_data1_all`**：儲存爬取下來的原始 Dcard 貼文資訊。
* **`dcard_data3_tokenpos_all`**：儲存經過 Jieba 斷詞、詞性標記（POS Tagging）處理後的貼文詞彙數據。

### Chroma 向量資料庫
位於 `app_poa_langchain/chroma_dcard_db`，儲存經 Embedding 後的貼文向量，提供給 RAG Agent 進行語意搜尋與智能對話。
