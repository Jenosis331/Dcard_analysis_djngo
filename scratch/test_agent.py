import os
import sys
import django

# Setup Django environment
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'website_configs.settings')
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
sys.stdout.reconfigure(encoding='utf-8')
sys.stderr.reconfigure(encoding='utf-8')
django.setup()

from app_poa_langchain.agent_core.agent import run_agent_phase2

def test_prompt(prompt):
    print(f"\n==================================================")
    print(f"Testing Prompt: '{prompt}'")
    print(f"==================================================")
    history = []
    reply, history = run_agent_phase2(prompt, history, session_id="test_session")
    print(f"\nFinal Bot Reply:\n{reply}")

if __name__ == "__main__":
    # Test comments pipeline
    test_prompt("請幫我完成 Dcard 留言資料的情緒分類與排序流程")
