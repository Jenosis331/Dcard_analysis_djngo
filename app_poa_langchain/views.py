from django.shortcuts import render
from django.http import JsonResponse
from app_poa_langchain.agent_core.agent import run_agent_phase2


def chat_view(request):
    """
    Renders the Chat interface for LangChain Agent (Phase 2)
    Uses Django sessions to persist 'chat_history' so the agent maintains conversational context.
    """
    # 確保當前 session 中有一個列表可以儲存對話紀錄
    if "chat_history" not in request.session:
        request.session["chat_history"] = []

    if request.method == "POST":
        action = request.POST.get("action", "")

        # 處理使用者按下清除記憶按鈕
        if action == "clear":
            request.session["chat_history"] = []
            return JsonResponse({"reply": "記憶已清除，我們可以開始新的對話了！"})

        user_message = request.POST.get("message", "")
        if not user_message:
            return JsonResponse({"error": "Message is empty"}, status=400)

        try:
            print(f"=== [Phase 2 - LangChain Agent] 開始處理請求 ===")
            print(f"User Message: {user_message}")

            # 讀取當前的對話記憶
            history = request.session["chat_history"]

            # 將訊息與記憶傳給 LangChain 代理人執行，並取回更新後的記憶
            bot_reply, new_history = run_agent_phase2(user_message, history)

            # 將新的記憶寫回 Session 並標記更動，讓 Django 將其存回 DB
            request.session["chat_history"] = new_history
            request.session.modified = True

            print(f"=== [Phase 2 - LangChain Agent] 請求處理完成 ===")
            return JsonResponse({"reply": bot_reply})
        except Exception as e:
            print(f"=== [Phase 2 - LangChain Agent] 發生錯誤: {str(e)} ===")
            return JsonResponse({"error": str(e)}, status=500)

    return render(request, "app_poa_langchain/home.html")
