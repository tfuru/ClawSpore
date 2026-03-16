import asyncio
import os
import json
import sys

# プロジェクトルートをパスに追加
sys.path.append('/app')

from core.agent import agent
from core.llm_client import llm
from core.tools.registry import tool_registry

async def test_tool_workflow():
    print("--- Starting Internal Tool Workflow Test ---")
    
    # 1. 環境確認
    print(f"Gemini API Key set: {bool(llm.gemini_api_key)}")
    print(f"Gemini Model: {llm.gemini_model_name}")
    
    # 2. テスト用プロンプト (ls を実行させる)
    session_id = "internal_workflow_test_session"
    prompt = "現在のディレクトリのファイル一覧を確認して、その結果を教えてください。"
    
    async def dummy_send_callback(text):
        print(f"AI Response Part: {text[:100]}...")

    async def auto_approve_callback(tool_name, args):
        print(f"Auto-approving tool: {tool_name} with args: {args}")
        return True

    # 3. 処理実行
    try:
        print("Processing workflow (ls -> result -> answer)...")
        error = await agent.process_message(
            session_id=session_id,
            prompt=prompt,
            send_callback=dummy_send_callback,
            ask_approval_callback=auto_approve_callback
        )
        
        if error:
            print(f"TEST FAILED with Error: {error}")
        else:
            print("--- Workflow Test Completed Successfully ---")
            print("Check logs above to ensure no 400 thought_signature errors occurred.")

    except Exception as e:
        print(f"Exception during test: {e}")

if __name__ == "__main__":
    asyncio.run(test_tool_workflow())
