import os
import sys
from dotenv import load_dotenv
from langchain_google_genai import ChatGoogleGenerativeAI
from langgraph.prebuilt import create_react_agent
from langchain_core.messages import HumanMessage, AIMessage, SystemMessage
from langgraph.checkpoint.memory import MemorySaver

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

from .tools import (
    get_top_keywords,
    get_top_persons,
    search_userkeyword_association,
    search_and_read_web,
    read_local_document,
    save_report_to_file,
    search_chroma_dcard_posts,
    run_combine_repeat_id_dcard_data1,
    run_add_repeat_id_dcard_data1,
    run_content_processing,
    run_csv_sentiment_summary,
    run_add_repeat_id_dcard_data2,
    run_tokenpos,
    run_top_person,
    run_combine_repeat_id_dcard_data2,
    run_comment_sentiment_sort,
    run_dcard_pipeline1_all,
    run_dcard_pipeline2_all,
    run_update_chroma_dcard_db,
)

# 可以使用 pip install langgraph langgraph-prebuilt duckduckgo-search requests beautifulsoup4 安裝最新依賴


def get_or_create_agent():
    """初始化並回傳具備記憶功能的 LangGraph Agent"""
    load_dotenv()
    api_key = os.getenv("GEMINI_API_KEY")

    if not api_key:
        raise ValueError("GEMINI_API_KEY not found in .env")

    # 1. 建立 LangChain 的 LLM 物件，此時支援 gemini-3.1-flash-lite
    llm = ChatGoogleGenerativeAI(model="gemini-3.1-flash-lite", google_api_key=api_key)

    # 2. 定義工具陣列 (這些工具都已經加上了 @tool 裝飾器)
    tools = [
        get_top_keywords,
        get_top_persons,
        search_userkeyword_association,
        search_and_read_web,
        read_local_document,
        save_report_to_file,
        search_chroma_dcard_posts,
        run_combine_repeat_id_dcard_data1,
        run_add_repeat_id_dcard_data1,
        run_content_processing,
        run_csv_sentiment_summary,
        run_add_repeat_id_dcard_data2,
        run_tokenpos,
        run_top_person,
        run_combine_repeat_id_dcard_data2,
        run_comment_sentiment_sort,
        run_dcard_pipeline1_all,
        run_dcard_pipeline2_all,
        run_update_chroma_dcard_db,
    ]

    # 3. 定義 System Prompt
    system_instruction = (
        "你是專業的 Dcard 輿情與社群分析智能代理人（POA Agent）。你具備分析本地與新聞資料庫、檢索 Dcard 討論文章與留言、讀取本地文件以及搜尋網路的能力。\n"
        "- 當使用者詢問 Dcard 論壇中關於某個關鍵字 or 主題的網友看法、討論點 or 發言態度時，務必呼叫 `search_chroma_dcard_posts` 工具對 Dcard 向量資料庫進行語意檢索獲取相關貼文片段，並利用你的 AI 能力進行輿情、情緒與發言態度分析。\n"
        "- 查詢熱門趨勢或議題時，依據指定的類別，取 3 個關鍵詞，若沒有指定類別，預設用政治類，呼叫 `get_top_keywords`。\n"
        "- 查詢熱門關鍵人物時，呼叫 `get_top_persons`。\n"
        "- 當需要搜尋一組關鍵字在新聞中的關聯、共現段落或進行交叉檢索時，呼叫 `search_userkeyword_association` 來獲取關聯新聞段落與數據，並利用你的 AI 能力分析 these 內容，歸納出其關聯性與脈絡。\n"
        "- 當用戶要求上網搜尋最新即時新聞或外部資訊時，呼叫 `search_and_read_web`。\n"
        "- 當需要讀取知識庫文件時，直接傳入檔名給 `read_local_document`（系統會自動去 knowledge_base/ 尋找）。\n"
        "- 當使用者要求「存檔」、「生成報告檔案」或「存到文件」時，呼叫 `save_report_to_file`。將寫好的報告存檔提供使用者下載。\n\n"
        "**Dcard 資料處理與管線執行指令：**\n"
        "- 當使用者要求「處理 Dcard 原始文章與管線流程」或「一鍵執行管線一所有流程」、「對爬蟲文章進行斷詞預處理、情緒標記、統計關鍵詞與人物，並存入總資料表」時，務必呼叫 `run_dcard_pipeline1_all` 工具以一鍵串接並完成管線一的所有 7 個步驟。不要分開單獨調用 7 個子工具，除非使用者特別明確要求執行特定單一步驟（例如：只做合併去重）。\n"
        "- 當使用者要求「一鍵執行管線二所有流程」、「執行 Dcard 留言一鍵管線」時，務必呼叫 `run_dcard_pipeline2_all` 工具以一鍵完成留言的合併與分類排序。\n"
        "- 當使用者單獨要求「留言合併去重」或單獨跑留言合併去重時，請呼叫 `run_combine_repeat_id_dcard_data2`。\n"
        "- 當使用者要求「更新向量資料庫」、「增量更新向量資料庫」、「同步文章至向量資料庫」時，請呼叫 `run_update_chroma_dcard_db` 工具。\n\n"
        "- 當沒有任何工具可用時，請以繁體中文並基於專業分析角度進行回答，保持口吻客觀理性。\n"
        "- 可用的category有: '工作', '閒聊', '科技業', '時事', 'YouTube', '全部'。\n\n"
        "**互動範例：**\n"
        "1. 「請分析 Dcard 網友對於『加班』這件事的看法與情緒走向。」\n"
        "2. 「請幫我執行 Dcard 原始文章資料的合併與去重流程」\n"
        "3. 「請幫我對爬蟲文章進行斷詞預處理、情緒標記、統計關鍵詞與人物，並存入總資料庫」\n"
        "4. 「請幫我完成 Dcard 留言資料的情緒分類與排序流程」\n"
        "請將工具獲取的數據深度融會貫通，產出結構完整、有數據佐證的 Markdown 專業報告。"
    )

    # 使用 LangGraph 預建的 ReAct 架構，並加入 Checkpointer 實現自動記憶
    # 請確保已執行 pip install -U langgraph 以支援 state_modifier
    memory = MemorySaver()
    agent_executor = create_react_agent(
        llm, 
        tools, 
        prompt=system_instruction, 
        checkpointer=memory
    )

    return agent_executor

# 將 Agent 實例化移至全域範圍，這樣 Agent 只會在 Django 啟動或首次匯入時初始化一次
agent_executor_instance = get_or_create_agent()

def run_agent_phase2(user_message: str, history_dicts: list, session_id: str = "default_user") -> tuple[str, list]:
    print(f"\n[LangGraph Core] 收到使用者訊息: {user_message}")

    # 使用 thread_id 讓 LangGraph 的 MemorySaver 自動處理歷史對話
    config = {"configurable": {"thread_id": session_id}}
    
    # 重要優化：
    # 因為我們使用了 MemorySaver 並帶入 thread_id，LangGraph 會自動從記憶體讀取歷史。
    # 我們只需要傳入「最新的一則訊息」。
    # 如果傳入整個 messages 列表，會導致對話紀錄在記憶體中重複。
    input_message = HumanMessage(content=user_message)
    response = agent_executor_instance.invoke({"messages": [input_message]}, config=config)

    # === [新增 DEBUG 觀察] 解析並印出中間過程 ===
    print("\n" + "="*50)
    print("🤖 [LangGraph 對話與工具執行軌跡解析]")
    print("="*50)
    for i, msg in enumerate(response["messages"]):
        msg_type = type(msg).__name__
        print(f"\n[{i+1}] 角色結構: {msg_type}")
        
        if msg_type == "HumanMessage":
            print(f"👤 使用者提問: {msg.content}")
        
        elif msg_type == "AIMessage":
            # 判斷模型是準備呼叫工具，還是純粹回文字
            if hasattr(msg, 'tool_calls') and msg.tool_calls:
                for tc in msg.tool_calls:
                    print(f"🛠️  模型決定呼叫工具: {tc.get('name')}")
                    print(f"      傳入參數: {tc.get('args')}")
            
            # Gemini 有時候最後的文字會包在 List[dict] 裡面
            text_content = ""
            if isinstance(msg.content, list):
                text_content = "".join([c.get('text', '') for c in msg.content if isinstance(c, dict) and c.get('type') == 'text'])
            elif isinstance(msg.content, str):
                text_content = msg.content
                
            if text_content.strip():
                print(f"🤖 模型最終回覆:\n{text_content.strip()}")
                
        elif msg_type == "ToolMessage":
            print(f"⚙️  工具 ({msg.name}) 執行結果:")
            print(f"      {msg.content}")
            
    print("\n" + "="*50 + "\n")
    print("前面的資訊一整串呈現如下:\n",response)
    print("\n" + "="*50 + "\n")

    # LangGraph 的回傳結構將不斷追加 messages，最後一筆就是 Agent 的回答
    bot_reply = response["messages"][-1].content

    # Gemini 3.1 Flash Lite 有時會將 content 回傳為 List[dict] (包含 signature 等資訊)
    if isinstance(bot_reply, list):
        bot_reply = "".join(
            [
                chunk.get("text", "")
                for chunk in bot_reply
                if chunk.get("type") == "text"
            ]
        )

    # 更新記憶並回傳（準備寫回 Django Session）
    history_dicts.append({"role": "user", "content": user_message})
    history_dicts.append({"role": "assistant", "content": bot_reply})

    print("[LangGraph Core] 生成最終回覆完畢！")
    return bot_reply, history_dicts


'''
`response = agent_executor.invoke({"messages": messages})` 這一行的確是 **正式啟動並呼叫語言模型** 的地方。

但更準確地說，因為你用的是 LangGraph 的 `create_react_agent`（ReAct 架構），所以這 **「一行指令」其實在背景包辦了多個步驟**：

1. **第一次呼叫 LLM：** 把你準備好的 System Prompt、對話歷史 (`messages`)、以及所有工具（包括 `search_and_read_web`）的說明傳給 Gemini。
2. **LLM 決定使用工具：** 如果 Gemini 決定要查詢天氣，它會要求從 `search_and_read_web` 工具拿資料。
3. **Agent Executor 自動執行工具：** `agent_executor` 會中途攔截這個請求，在你的 Python 環境中執行 `search_and_read_web`，取得結果。
4. **再次（或多次）呼叫 LLM：** 將工具的結果丟回給 Gemini，讓它決定是否繼續查下一個網站（如同你在上一個問題中看到的第二次查詢），或是總結回答。
5. **返回最終結果：** 直到 Gemini 說「我收集夠資訊了，這就是最終回答」，`invoke` 才會結束並把最終結果回傳給 `response`。

所以，雖然從程式碼來看只有一行 `.invoke()`，語言模型實際上可能已經被 Agent 架構在背後自動**自動呼叫了很多次**了！
'''

'''
{'messages': [HumanMessage(content='請幫我列出資料庫最近新聞中，政治最熱門的前 1 個關鍵字', additional_kwargs={}, response_metadata={}, id='995b794d-efe1-42a4-9fa0-b039c7cafd60'), AIMessage(content=[], additional_kwargs={'function_call': {'name': 'get_top_keywords', 'arguments': '{"topk": 1, "category": "\\u653f\\u6cbb"}'}, '__gemini_function_call_thought_signatures__': {'15f80e45-f1ed-441d-a28b-f730fa81f9f4': 'EjQKMgEMOdbHSmLFc3ogTQEnKGkw4KERItPB/P7vlbhKXZ5MpOIBkL2BezttkFWK5FyIBPvr'}}, response_metadata={'finish_reason': 'STOP', 'model_name': 'gemini-3.1-flash-lite', 'safety_ratings': [], 'model_provider': 'google_genai'}, id='lc_run--019e4034-2552-79a1-82de-e4685161dd8c-0', tool_calls=[{'name': 'get_top_keywords', 'args': {'topk': 1, 'category': '政治'}, 'id': '15f80e45-f1ed-441d-a28b-f730fa81f9f4', 'type': 'tool_call'}], invalid_tool_calls=[], usage_metadata={'input_tokens': 1086, 'output_tokens': 23, 'total_tokens': 1109, 'input_token_details': {'cache_read': 0}}), ToolMessage(content='[{"keyword": "台灣", "frequency": 67}]', name='get_top_keywords', id='e0ce68cf-a1c1-4a3c-a7a7-49944c337482', tool_call_id='15f80e45-f1ed-441d-a28b-f730fa81f9f4'), AIMessage(content=[{'type': 'text', 'text': '根據資料庫內最近的新聞數據，在「政治」類別中最熱門的關鍵字是：\n\n### **「台灣」**\n*   **提及頻率：** 67 次\n\n此關鍵字在目前的政治新聞版面中佔據了首位，顯示出近期與「台灣」相關的政治議題討論度最高。', 'extras': {'signature': 'EjQKMgEMOdbHcm8pCq7lapBBICA0TL/Qdl1ntFMCj6auXpsgsVEXlBz590EFNuIo6ZDJ1jyc'}}], additional_kwargs={}, response_metadata={'finish_reason': 'STOP', 'model_name': 'gemini-3.1-flash-lite', 'safety_ratings': [], 'model_provider': 'google_genai'}, id='lc_run--019e4034-4ada-7c33-81fd-d6af76cad439-0', tool_calls=[], invalid_tool_calls=[], usage_metadata={'input_tokens': 1133, 'output_tokens': 75, 'total_tokens': 1208, 'input_token_details': {'cache_read': 0}})]}
'''