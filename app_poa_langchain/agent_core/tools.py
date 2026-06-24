from datetime import datetime
from pathlib import Path
import re
from typing import Optional
import sys
import subprocess
import shutil
import contextlib

def print(*args, **kwargs):
    import builtins
    try:
        builtins.print(*args, **kwargs)
    except UnicodeEncodeError:
        encoding = sys.stdout.encoding or 'utf-8'
        safe_args = []
        for arg in args:
            if isinstance(arg, str):
                safe_args.append(arg.encode(encoding, errors='replace').decode(encoding))
            else:
                safe_args.append(arg)
        builtins.print(*safe_args, **kwargs)

from langchain_core.tools import tool
import os
from dotenv import load_dotenv
import requests
from bs4 import BeautifulSoup
import pandas as pd
from django.conf import settings

from app_top_keyword.views import get_category_topword
from app_top_person.views import get_category_topPerson
from app_user_keyword_association.views import filter_dataFrame_fullText, get_same_para

load_dotenv()

@tool
def search_and_read_web(query: str) -> str:
    """
    使用關鍵字搜尋網路資訊，並讀取最相關網頁的內容摘要。
    適合用來查詢最新的網路資訊或外部即時新聞（例如：今日新聞、最新政治動態）。
    """
    print(f"\n[Agent Tool] 執行 Tavily 安全搜尋: '{query}'")
    
    # 1. 嘗試呼叫 Tavily API
    try:
        from tavily import TavilyClient
        
        api_key = os.environ.get("TAVILY_API_KEY")
        if not api_key:
            raise ValueError("找不到 TAVILY_API_KEY 環境變數")
            
        client = TavilyClient(api_key=api_key)
        # get_search_context 會直接回傳最適合給 LLM 閱讀的文字串
        response = client.get_search_context(query=query, max_results=3)
        
        if response:
            return response
            
    except Exception as e:
        # 當 401 錯誤或任何網路異常發生時，記錄 Log，但不中斷 Django，啟動 Fallback
        print(f"Tavily 搜尋失敗 ({str(e)})，啟動在地知識庫備援計畫。")

    # 2. 【通用防禦機制】不硬寫特定事件，而是告訴 AI 當前系統連線的真實狀況
    return (
        f"【系統通知：當前外部搜尋引擎 API 驗證受限（401 Unauthorized 或 額度用盡）。】\n"
        f"無法即時連網抓取關於「{query}」的最新網頁內容。\n"
        f"請助理（LLM）委婉向使用者說明目前無法即時連網更新資訊，"
        f"並嘗試根據你現有的知識庫提供協助，或者請使用者換個方式提問。"
    )


@tool
def read_local_document(filepath: str) -> str:
    """Read the content of a local file (e.g., .txt, .md, .csv).
    Use this tool when you need to read local document files to answer user questions.

    Args:
        filepath: 本地檔案的相對路徑或絕對路徑 (例如: 'README.md' 或 'app_poa_agent/第一階段說明.md')。
    """
    print(f"\n[LangChain Tool] 執行 read_local_document(filepath='{filepath}')")

    if not os.path.exists(filepath):
        return f"錯誤：找不到檔案 '{filepath}'。請確認路徑是否正確。"

    try:
        with open(filepath, "r", encoding="utf-8") as f:
            content = f.read()

        # 為了避免檔案過長超過 Token 限制，擷取前 4000 個字元
        if len(content) > 4000:
            return f"【檔案內容過長，僅顯示前4000字】\n{content[:4000]}..."
        return content
    except Exception as e:
        return f"讀取檔案時發生錯誤: {str(e)}"


@tool
def save_report_to_file(report_text: str, filename: Optional[str] = None) -> dict:
    """Save generated report text into a local text file.

    Args:
        report_text: The report content that should be written to disk.
        filename: Optional file name without extension. If omitted, a timestamped name is generated.
    """
    # 取得專案根目錄下的 knowledge_base 資料夾
    reports_dir = Path(__file__).resolve().parent.parent.parent / 'knowledge_base'
    reports_dir.mkdir(parents=True, exist_ok=True)

    # 清理 report_text：如果模型在內容前後包了 markdown code block，將其去除
    if report_text.startswith("```"):
        report_text = re.sub(r'^```[\w]*\n|```$', '', report_text, flags=re.MULTILINE)

    if filename:
        safe_name = Path(filename).stem
    else:
        safe_name = datetime.now().strftime('report_%Y%m%d_%H%M%S')

    file_path = reports_dir / f"{safe_name}.txt"
    with file_path.open('w', encoding='utf-8') as f:
        f.write(report_text)

    print(f"[Agent Tool Execution] save_report_to_file 執行完畢，已儲存至 {file_path}\n")
    return {
        "saved_path": str(file_path),
        "message": "Report saved successfully.",
    }
    



@tool
def get_top_keywords(category: str, topk: int = 10) -> list:
    """Get the top keywords and their frequencies for a specific news category.

    Args:
        category: The news category (e.g., '政治', '科技', '運動').
        topk: The number of top keywords to return. Default is 10.
    """
    print(
        f"\n[LangChain Tool] 執行 get_top_keywords(category='{category}', topk={topk})"
    )
    topk = int(topk)
    _, wf_pairs = get_category_topword(category, topk)
    return [{"keyword": w, "frequency": f} for w, f in wf_pairs]


@tool
def get_top_persons(category: str, topk: int = 5) -> list:
    """Get the most frequently mentioned people in a specific news category.

    Args:
        category: The news category (e.g., '政治', '科技', '運動').
        topk: The number of top people to return. Default is 5.
    """
    print(
        f"\n[LangChain Tool] 執行 get_top_persons(category='{category}', topk={topk})"
    )
    topk = int(topk)
    _, wf_pairs = get_category_topPerson(category, topk)
    return [{"person": w, "frequency": f} for w, f in wf_pairs]


@tool
def search_userkeyword_association(keywords: str, category: str = "全部", cond: str = "and", weeks: int = 12) -> dict:
    """使用關鍵字在新聞資料庫中檢索相關文章段落、關聯字及相關新聞連結。
    當使用者想要尋找特定關鍵字或一組關鍵字在新聞中的關聯、共現段落、脈絡或統計數據時，呼叫此工具。
    
    Args:
        keywords: 關鍵字字串，多個關鍵字請以空格分隔 (例如: '台積電 張忠謀')。
        category: 新聞分類，可選: '全部', '工作', '閒聊', '科技業', '時事', 'YouTube'，預設為 '全部'。
        cond: 關鍵字結合條件 ('and' 或 'or')，預設為 'and'。
        weeks: 檢索過去幾週的新聞，預設為 12 週。
    """
    print(f"\n[Agent Tool] 執行新聞關聯檢索 (userkeyword_assoc): '{keywords}', 分類: {category}, 條件: {cond}, 週數: {weeks}")
    
    try:
        kw_list = keywords.strip().split()
        if not kw_list:
            return {"error": "關鍵字不能為空"}
            
        df_query = filter_dataFrame_fullText(kw_list, cond, category, weeks)
        
        if df_query is None or len(df_query) == 0:
            return {
                "message": f"在過去 {weeks} 週的「{category}」分類中，找不到與關鍵字「{keywords}」相關的新聞。"
            }
            
        from app_user_keyword_association.views import get_title_link_topk, get_related_word_clouddata
        
        newslinks = get_title_link_topk(df_query, k=5)
        related_words, _ = get_related_word_clouddata(df_query)
        same_paragraphs = get_same_para(df_query, kw_list, cond, k=10)
        
        return {
            "num_articles": len(df_query),
            "news_links": newslinks,
            "related_keywords": [{"keyword": w, "frequency": f} for w, f in related_words[:10]],
            "matching_paragraphs": same_paragraphs
        }
        
    except Exception as e:
        return {"error": f"檢索過程發生錯誤: {str(e)}"}


@tool
def search_chroma_dcard_posts(query: str, n_results: int = 5) -> dict:
    """從本地 Dcard 向量資料庫 (chroma_dcard_db) 中進行語意檢索，尋找與查詢主題最相關的討論內容。
    當使用者詢問關於 Dcard 網友對某主題的討論、經驗分享、態度或輿情分析時，使用此工具來檢索相關的文章段落，
    檢索出來的內容將提供給 AI (Gemini) 進行總結與情緒分析。
    
    Args:
        query: 檢索的查詢字串/主題 (例如: '科技業加班狀況', '聯發科面試')。
        n_results: 檢索的結果筆數，預設為 5 筆。
    """
    print(f"\n[Agent Tool] 執行 Chroma 向量資料庫檢索: '{query}', 筆數: {n_results}")
    
    db_path = os.path.join(settings.BASE_DIR, 'app_poa_langchain', 'chroma_dcard_db')
    
    if not os.path.exists(db_path):
        return {"error": f"找不到 Chroma 向量資料庫路徑 '{db_path}'，請確認資料庫是否已正確放置。"}
        
    try:
        from google import genai
        import chromadb
        
        api_key = os.environ.get("GEMINI_API_KEY")
        if not api_key:
            raise ValueError("找不到 GEMINI_API_KEY 環境變數")
            
        genai_client = genai.Client(api_key=api_key)
        
        # 產生查詢的 Embedding (gemini-embedding-001)
        embed_response = genai_client.models.embed_content(
            model="gemini-embedding-001",
            contents=query
        )
        query_vector = embed_response.embeddings[0].values
        
        # 連線至 ChromaDB
        chroma_client = chromadb.PersistentClient(path=db_path)
        collection = chroma_client.get_collection(name="dcard_articles")
        
        # 檢索相似內容
        results = collection.query(
            query_embeddings=[query_vector],
            n_results=int(n_results)
        )
        
        # 整理結果
        retrieved_items = []
        if results and "documents" in results and len(results["documents"]) > 0:
            docs = results["documents"][0]
            metadatas = results["metadatas"][0]
            distances = results["distances"][0]
            
            for doc, meta, dist in zip(docs, metadatas, distances):
                retrieved_items.append({
                    "title": meta.get("title", "無標題"),
                    "published_date": meta.get("article_dates", "無日期"),
                    "distance": float(dist),
                    "content": doc
                })
                
        return {
            "query": query,
            "count": len(retrieved_items),
            "results": retrieved_items
        }
        
    except Exception as e:
        return {"error": f"Chroma 向量檢索失敗: {str(e)}"}


def _execute_python_script(script_relative_path: str, cwd_dir: str, args: Optional[list] = None) -> dict:
    """Helper function to execute a Python script using the current Python interpreter."""
    script_path = os.path.join(settings.BASE_DIR, script_relative_path)
    if not os.path.exists(script_path):
        return {
            "status": "error",
            "message": f"Python script not found: {script_relative_path} (full path: {script_path})"
        }
    
    print(f"\n[Agent Tool] Running script: '{script_relative_path}' with args {args} in directory '{cwd_dir}'...")
    try:
        # Run python script via subprocess using current environment variables and force UTF-8 output
        env = os.environ.copy()
        env['PYTHONIOENCODING'] = 'utf-8'
        env['USE_TF'] = '0'
        env['USE_TORCH'] = '1'
        
        cmd = [sys.executable, script_path]
        if args:
            cmd.extend(args)
            
        result = subprocess.run(
            cmd,
            cwd=cwd_dir,
            capture_output=True,
            text=True,
            encoding='utf-8',
            errors='ignore',
            env=env
        )
        if result.returncode == 0:
            return {
                "status": "success",
                "stdout": result.stdout.strip(),
                "message": f"Successfully executed script {script_relative_path}"
            }
        else:
            return {
                "status": "error",
                "stderr": result.stderr.strip(),
                "stdout": result.stdout.strip(),
                "message": f"Failed to execute script {script_relative_path} with exit code: {result.returncode}"
            }
    except Exception as e:
        return {
            "status": "error",
            "message": f"Exception occurred while executing script: {str(e)}"
        }


@contextlib.contextmanager
def _swap_files(target_name: str, custom_input_path: Optional[str], custom_output_path: Optional[str], default_output_name: str):
    """
    A context manager to temporarily swap input/output files to match the hardcoded paths in scripts.
    """
    base_dir = settings.BASE_DIR
    target_input_full = os.path.normpath(os.path.abspath(os.path.join(base_dir, target_name)))
    target_output_full = os.path.normpath(os.path.abspath(os.path.join(base_dir, default_output_name)))
    
    # Check if the custom path is the same as the target path
    if custom_input_path:
        custom_input_full = os.path.normpath(os.path.abspath(os.path.join(base_dir, custom_input_path)))
        if custom_input_full == target_input_full:
            custom_input_path = None  # No need to swap, it is the same file
            
    if custom_output_path:
        custom_output_full = os.path.normpath(os.path.abspath(os.path.join(base_dir, custom_output_path)))
        if custom_output_full == target_output_full:
            custom_output_path = None  # No need to swap, it is the same file

    backup_input = None
    backup_output = None
    
    try:
        # 1. Swap input file
        if custom_input_path:
            custom_input_full = os.path.normpath(os.path.abspath(os.path.join(base_dir, custom_input_path)))
            if not os.path.exists(custom_input_full):
                raise FileNotFoundError(f"Custom input file not found: {custom_input_path}")
            
            # If target input file already exists, backup it first
            if os.path.exists(target_input_full):
                backup_input = target_input_full + ".bak"
                shutil.copy2(target_input_full, backup_input)
            
            # Copy custom input file to target input path
            shutil.copy2(custom_input_full, target_input_full)
            
        # 2. Backup target output file if it exists (only when custom_output_path is provided)
        if custom_output_path and os.path.exists(target_output_full):
            backup_output = target_output_full + ".bak"
            shutil.copy2(target_output_full, backup_output)
            
        yield
        
        # 3. Handle output file
        if custom_output_path:
            custom_output_full = os.path.normpath(os.path.abspath(os.path.join(base_dir, custom_output_path)))
            if os.path.exists(target_output_full):
                # Copy the generated output file to custom output path
                os.makedirs(os.path.dirname(custom_output_full), exist_ok=True)
                shutil.copy2(target_output_full, custom_output_full)
                print(f"[Agent Tool] Saved generated file {default_output_name} to {custom_output_path}")
                os.remove(target_output_full)
                
    finally:
        # 4. Clean up / Restore input file
        if custom_input_path:
            if os.path.exists(target_input_full):
                os.remove(target_input_full)
            if backup_input and os.path.exists(backup_input):
                shutil.move(backup_input, target_input_full)
                
        # 5. Restore output file (only when custom_output_path is provided)
        if custom_output_path and backup_output and os.path.exists(backup_output):
            shutil.move(backup_output, target_output_full)


@tool
def run_combine_repeat_id_dcard_data1() -> dict:
    """合併並去重原始 Dcard 文章資料。
    會自動讀取資料夾 'data/dcard_data/dcard_data1' 中的 CSV 檔案並進行合併與去重，
    最後將結果儲存至 'data/csv_file/csv_tmp/dcard_data1_tmp.csv'。
    """
    data_dir = os.path.join(settings.BASE_DIR, 'data')
    return _execute_python_script('code/dcard_pipeline/combine_repeat_id_dcard_data1.py', data_dir)


@tool
def run_add_repeat_id_dcard_data1() -> dict:
    """將去重後的暫存文章資料 (csv_file/csv_tmp/dcard_data1_tmp.csv) 新增追加到總資料庫 (csv_file/dcard_data1_all.csv)。
    此工具會自動進行去重比對，只保留新的文章 (根據 article_id 判斷)。
    """
    data_dir = os.path.join(settings.BASE_DIR, 'data')
    return _execute_python_script('code/dcard_pipeline/add_repeat_id_dcard_data1.py', data_dir)


@tool
def run_content_processing() -> dict:
    """使用 CKIP 模型對合併去重後的暫存文章內容 (csv_file/csv_tmp/dcard_data1_tmp.csv) 進行預處理。
    會完成斷詞 (Tokenization)、詞性標記 (POS) 與命名實體辨識 (NER)，
    並輸出至 'csv_file/csv_tmp/dcard_data2_preprocessed_tmp.csv'。
    """
    data_dir = os.path.join(settings.BASE_DIR, 'data')
    return _execute_python_script('code/dcard_pipeline/content_processing.py', data_dir)


@tool
def run_csv_sentiment_summary() -> dict:
    """使用 Hugging Face 的 albert-sentiment 情緒分析模型為預處理後的暫存文章資料
    (csv_file/csv_tmp/dcard_data2_preprocessed_tmp.csv) 生成摘要 (Summary) 與情緒極性 (Sentiment 分數)，
    並原地更新該暫存檔案。
    """
    data_dir = os.path.join(settings.BASE_DIR, 'data')
    return _execute_python_script('code/dcard_pipeline/csv_sentiment_summary.py', data_dir)


@tool
def run_add_repeat_id_dcard_data2() -> dict:
    """將已標註情緒與摘要的暫存文章資料 (csv_file/csv_tmp/dcard_data2_preprocessed_tmp.csv)
    追加寫入總文章資料庫 (csv_file/dcard_data2_preprocessed_all.csv)，並根據 article_id 自動去重。
    """
    data_dir = os.path.join(settings.BASE_DIR, 'data')
    return _execute_python_script('code/dcard_pipeline/add_repeat_id_dcard_data2.py', data_dir)


@tool
def run_tokenpos() -> dict:
    """根據預處理總資料庫 (csv_file/dcard_data2_preprocessed_all.csv) 統計並生成各版別的熱門關鍵詞頻率統計檔 (csv_file/dcard_data3_tokenpos_all.csv)。
    """
    data_dir = os.path.join(settings.BASE_DIR, 'data')
    return _execute_python_script('code/dcard_pipeline/tokenpos.py', data_dir)


@tool
def run_top_person() -> dict:
    """根據預處理總資料庫 (csv_file/dcard_data2_preprocessed_all.csv) 統計並生成各版別的熱門人物頻率統計檔 (csv_file/dcard_top_person.csv)。
    """
    data_dir = os.path.join(settings.BASE_DIR, 'data')
    return _execute_python_script('code/dcard_pipeline/top_person.py', data_dir)


@tool
def run_combine_repeat_id_dcard_data2() -> dict:
    """合併並去重原始 Dcard 留言資料。
    會自動讀取資料夾 'data/dcard_data/dcard_data1_sub' 中的 CSV 檔案並進行合併與去重，
    最後將結果儲存至 'data/comments_processed/dcard_data1_sub_all.csv'。
    """
    data_dir = os.path.join(settings.BASE_DIR, 'data')
    return _execute_python_script('code/dcard_pipeline/combine_repeat_id_dcard_data2.py', data_dir)


@tool
def run_comment_sentiment_sort(input_file: Optional[str] = None, output_file: Optional[str] = None) -> dict:
    """完成 Dcard 留言的情緒分類與排序標註（情緒分類與排序）。
    預設讀取 'data/comments_processed/dcard_data1_sub_all.csv'，並將完成排序且標籤化的留言資料輸出至 'data/comments_processed/dcard_data1_sub_all_sorted_labeled.csv'。
    
    Args:
        input_file: 自訂輸入 CSV 檔案路徑（相對於專案根目錄，如 'data/comments_processed/dcard_data1_sub_all.csv'）。如果未提供，則使用預設路徑。
        output_file: 自訂輸出 CSV 檔案路詢（相對於專案根目錄，如 'data/comments_processed/dcard_data1_sub_all_sorted_labeled.csv'）。如果未提供，則使用預設路徑。
    """
    base_dir = settings.BASE_DIR
    target_input = os.path.join("data", "comments_processed", "dcard_data1_sub_all.csv")
    target_output = os.path.join("data", "comments_processed", "dcard_data1_sub_all_sorted_labeled.csv")
    with _swap_files(
        target_name=target_input,
        custom_input_path=input_file,
        custom_output_path=output_file,
        default_output_name=target_output
    ):
        return _execute_python_script(
            'code/dcard_pipeline/comment_sentiment_sort.py',
            base_dir
        )


@tool
def run_update_chroma_dcard_db(source: str = "db") -> dict:
    """增量更新 Dcard 向量資料庫 (chroma_dcard_db)，將新文章進行 Embedding 並追加寫入。
    
    Args:
        source: 資料來源，可選 'db' (自 SQLite 資料表 dcard_data1_all 讀取) 或 'tmp' (自 csv_tmp/dcard_data1_tmp.csv 讀取)。預設為 'db'。
    """
    base_dir = settings.BASE_DIR
    args = ["--source", source]
    return _execute_python_script('app_poa_langchain/rag/update_vector_db.py', base_dir, args=args)


@tool
def run_dcard_pipeline2_all() -> str:
    """一鍵執行完整 Dcard 留言資料處理管線二 (Comments Pipeline)。
    包含以下所有步驟：
    1. 合併並去重原始留言資料 (run_combine_repeat_id_dcard_data2)
    2. 留言情緒分類與排序標註 (run_comment_sentiment_sort)
    
    執行時會回傳管線二的詳細執行報告。
    """
    import sys
    
    def safe_print(text: str):
        try:
            sys.stdout.write(text)
            sys.stdout.flush()
        except UnicodeEncodeError:
            encoding = sys.stdout.encoding or 'utf-8'
            safe_text = text.encode(encoding, errors='replace').decode(encoding)
            sys.stdout.write(safe_text)
            sys.stdout.flush()

    steps = [
        ("步驟 1/2: 合併並去重原始留言資料 (run_combine_repeat_id_dcard_data2)", 
         run_combine_repeat_id_dcard_data2.func if hasattr(run_combine_repeat_id_dcard_data2, 'func') else run_combine_repeat_id_dcard_data2),
        ("步驟 2/2: 執行 Dcard 留言情緒分類與排序 (run_comment_sentiment_sort)", 
         run_comment_sentiment_sort.func if hasattr(run_comment_sentiment_sort, 'func') else run_comment_sentiment_sort)
    ]
    
    safe_print("\n=========================================\n")
    safe_print("🚀 開始一鍵執行 Dcard 留言資料處理管線二...\n")
    safe_print("=========================================\n")
    
    results_summary = []
    
    for i, (name, func) in enumerate(steps, 1):
        safe_print(f"\n👉 [正在執行 {i}/2] {name}...\n")
        
        try:
            res = func()
            
            if isinstance(res, dict) and res.get("status") == "error":
                err_msg = res.get("message", "未知錯誤")
                stderr = res.get("stderr", "")
                full_err = f"{err_msg}\n{stderr}".strip()
                
                safe_print(f"❌ [執行失敗] {name}\n原因: {full_err}\n")
                safe_print("⚠️ 執行中斷，後續步驟取消。\n")
                
                results_summary.append(f"- **{name}**: [失敗] FAILED\n  - 原因: `{err_msg}`\n  - 詳細資料: {stderr}")
                break
            else:
                stdout_msg = ""
                if isinstance(res, dict) and "stdout" in res:
                    stdout_msg = res["stdout"]
                
                safe_print(f"✅ [執行成功] {name}\n")
                if stdout_msg:
                    safe_print(f"   輸出內容: {stdout_msg}\n")
                
                sum_msg = f"- **{name}**: [成功] SUCCESS"
                if stdout_msg:
                    sum_msg += f"\n  - 輸出: `{stdout_msg}`"
                results_summary.append(sum_msg)
                
        except Exception as e:
            safe_print(f"❌ [執行例外失敗] {name}\n例外原因: {str(e)}\n")
            safe_print("⚠️ 執行中斷，後續步驟取消。\n")
            results_summary.append(f"- **{name}**: [例外失敗] FAILED (`{str(e)}`)")
            break
            
    safe_print("\n=========================================\n")
    safe_print("🏁 Dcard 留言資料處理管線二執行結束！\n")
    safe_print("=========================================\n\n")
    
    summary_text = "### [管線二執行報告] Dcard 留言處理管線二執行報告\n\n" + "\n".join(results_summary)
    return summary_text


@tool
def run_dcard_pipeline1_all() -> str:
    """一鍵執行完整 Dcard 文章資料處理管線一 (Articles Pipeline)。
    包含以下所有步驟：
    1. 合併並去重原始文章資料 (run_combine_repeat_id_dcard_data1)
    2. 追加新文章至總原始文章庫 (run_add_repeat_id_dcard_data1)
    3. 斷詞與詞性標記預處理 (run_content_processing)
    4. 生成摘要與情緒分數 (run_csv_sentiment_summary)
    5. 追加寫入情緒預處理總庫 (run_add_repeat_id_dcard_data2)
    6. 統計並生成各版別的熱門關鍵詞頻統計檔 (run_tokenpos)
    7. 統計並生成各版別的熱門人物頻率統計檔 (run_top_person)
    
    執行時會在終端機輸出即時進度。如果其中某個步驟失敗，將會中斷執行並回傳錯誤。
    """
    import sys
    
    def safe_print(text: str):
        try:
            sys.stdout.write(text)
            sys.stdout.flush()
        except UnicodeEncodeError:
            encoding = sys.stdout.encoding or 'utf-8'
            # Replace characters that cannot be encoded by the target code page
            safe_text = text.encode(encoding, errors='replace').decode(encoding)
            sys.stdout.write(safe_text)
            sys.stdout.flush()

    steps = [
        ("步驟 1/7: 合併並去重原始文章資料 (run_combine_repeat_id_dcard_data1)", 
         run_combine_repeat_id_dcard_data1.func if hasattr(run_combine_repeat_id_dcard_data1, 'func') else run_combine_repeat_id_dcard_data1),
        ("步驟 2/7: 追加新文章至總原始文章庫 (run_add_repeat_id_dcard_data1)", 
         run_add_repeat_id_dcard_data1.func if hasattr(run_add_repeat_id_dcard_data1, 'func') else run_add_repeat_id_dcard_data1),
        ("步驟 3/7: 執行中研院 CKIP 斷詞與詞性預處理 (run_content_processing)", 
         run_content_processing.func if hasattr(run_content_processing, 'func') else run_content_processing),
        ("步驟 4/7: 執行 Albert 模型情緒與摘要標籤標記 (run_csv_sentiment_summary)", 
         run_csv_sentiment_summary.func if hasattr(run_csv_sentiment_summary, 'func') else run_csv_sentiment_summary),
        ("步驟 5/7: 追加寫入情緒預處理總庫 (run_add_repeat_id_dcard_data2)", 
         run_add_repeat_id_dcard_data2.func if hasattr(run_add_repeat_id_dcard_data2, 'func') else run_add_repeat_id_dcard_data2),
        ("步驟 6/7: 統計並生成各版別的熱門關鍵詞頻率檔 (run_tokenpos)", 
         run_tokenpos.func if hasattr(run_tokenpos, 'func') else run_tokenpos),
        ("步驟 7/7: 統計並生成各版別的熱門人物頻率檔 (run_top_person)", 
         run_top_person.func if hasattr(run_top_person, 'func') else run_top_person)
    ]
    
    safe_print("\n=========================================\n")
    safe_print("🚀 開始一鍵執行 Dcard 文章資料處理管線一 (1-7 步驟)...\n")
    safe_print("=========================================\n")
    
    results_summary = []
    
    for i, (name, func) in enumerate(steps, 1):
        safe_print(f"\n👉 [正在執行 {i}/7] {name}...\n")
        
        try:
            # 執行該步驟
            res = func()
            
            # 判斷執行結果
            if isinstance(res, dict) and res.get("status") == "error":
                err_msg = res.get("message", "未知錯誤")
                stderr = res.get("stderr", "")
                full_err = f"{err_msg}\n{stderr}".strip()
                
                safe_print(f"❌ [執行失敗] {name}\n原因: {full_err}\n")
                safe_print("⚠️ 執行中斷，後續步驟取消。\n")
                
                results_summary.append(f"- **{name}**: [失敗] FAILED\n  - 原因: `{err_msg}`\n  - 詳細資料: {stderr}")
                break
            else:
                stdout_msg = ""
                if isinstance(res, dict) and "stdout" in res:
                    stdout_msg = res["stdout"]
                
                safe_print(f"✅ [執行成功] {name}\n")
                if stdout_msg:
                    safe_print(f"   輸出內容: {stdout_msg}\n")
                
                sum_msg = f"- **{name}**: [成功] SUCCESS"
                if stdout_msg:
                    sum_msg += f"\n  - 輸出: `{stdout_msg}`"
                results_summary.append(sum_msg)
                
        except Exception as e:
            safe_print(f"❌ [執行例外失敗] {name}\n例外原因: {str(e)}\n")
            safe_print("⚠️ 執行中斷，後續步驟取消。\n")
            results_summary.append(f"- **{name}**: [例外失敗] FAILED (`{str(e)}`)")
            break
            
    safe_print("\n=========================================\n")
    safe_print("🏁 Dcard 文章資料處理管線一執行結束！\n")
    safe_print("=========================================\n\n")
    
    summary_text = "### [管線一執行報告] Dcard 文章處理管線一執行報告\n\n" + "\n".join(results_summary)
    return summary_text



"""
(1) Google 也有提供搜尋的API服務，但需要申請 Google Custom Search Engine，並且有每日免費配額限制（100次/天）。如果你想要使用 Google 的搜尋 API，可以參考以下步驟：

1. 前往 Google Custom Search Engine 官網 (https://cse.google.com/cse/)。

2. 建立一個新的搜尋引擎，設定要搜尋的網站（如果想搜尋整個網路，可以在「Sites to search」欄位輸入 `www.google.com`）。

3. 取得搜尋引擎 ID（cx）和 API Key。

4. 使用 Google 的搜尋 API，發送 GET 請求到以下 URL：

https://www.googleapis.com/customsearch/v1?q={query}&cx={cx}&key={API_KEY}

其中 `{query}` 是你的搜尋關鍵字，`{cx}` 是你的搜尋引擎 ID，`{API_KEY}` 是你的 API Key。

不過需要注意的是，Google 的搜尋 API 也有使用限制和配額，如果你需要大量的搜尋次數，可能需要付費升級配額。此外，Google 的搜尋 API 回傳的結果格式比較複雜，需要額外的程式碼來解析和整理成適合 LLM 使用的格式。





(2) DuckDuckGo 的搜尋 API 經常會遇到 401 Unauthorized 的問題，這是因為他們的防爬蟲機制非常嚴格，尤其是對於頻繁 of API 請求。這種情況下，最好的解決方案是改用一個更穩定且專為 AI Agent 設計的搜尋引擎，例如 Tavily。



(3) 改用穩定且免費的 Tavily API

如果你希望這個 Agent 能夠穩定搜尋、不再跟 DuckDuckGo 的防爬蟲機制捉迷藏，最快且最符合 LangChain 生態系的方法就是換成 Tavily。



為什麼推薦 Tavily？



它是 LangChain 官方推薦、專門為 AI Agent 打造的搜尋引擎。



每月提供 1,000 次完全免費的 API 呼叫額度，對開發和中小規模使用完全夠用。



它不需要你用 BeautifulSoup 去痛苦地解析 HTML，它會直接把搜尋結果整理成最適合 LLM 閱讀的乾淨文字摘要。



步驟 1：安裝 Tavily 的 LangChain 整合套件

請在你的虛擬環境終端機執行：



pip install tavily-python

步驟 2：取得免費的 API Key

前往 Tavily 官網 (tavily.com) 註冊一個免費帳號。

https://app.tavily.com/home



在 Dashboard 複製你的 API Key（格式通常是 tvly-....）。



將此 Key 設定到你的 Django .env 檔案中，或者在環境變數中設定：

"""