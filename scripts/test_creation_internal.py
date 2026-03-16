import asyncio
import os
import json
import sys

# プロジェクトルートをパスに追加
sys.path.append('/app')

from core.agent import agent
from core.llm_client import llm
from core.tools.registry import tool_registry

async def test_tool_creation():
    print("--- Starting Internal Tool Creation Test ---")
    
    # 1. 環境確認
    print(f"Gemini API Key set: {bool(llm.gemini_api_key)}")
    print(f"Gemini Model: {llm.gemini_model_name}")
    
    # 2. テスト用プロンプト
    session_id = "internal_test_session"
    prompt = "YouTubeでキーワード検索して動画のURLを5件取得するツール youtube_search_v2 を作って、実際に実行してみて。"
    
    async def dummy_send_callback(text):
        print(f"AI Response: {text[:200]}...")

    async def auto_approve_callback(tool_name, args):
        print(f"Auto-approving tool: {tool_name} with args: {args}")
        return True

    # 3. 処理実行
    try:
        print("Processing message (this involves multi-turn reasoning and thought_signature handling)...")
        error = await agent.process_message(
            session_id=session_id,
            prompt=prompt,
            send_callback=dummy_send_callback,
            ask_approval_callback=auto_approve_callback
        )
        
        if error:
            print(f"Test Failed with Error: {error}")
        else:
            print("--- Test Completed Successfully (Log indicates if reasoning finished) ---")
            
            # 作成されたファイルの確認
            created_file = "/app/core/tools/dynamic/youtube_search_v2.py"
            if os.path.exists(created_file):
                print(f"SUCCESS: {created_file} was created.")
                # ツールが登録されているか確認
                if 'youtube_search_v2' in tool_registry._tools:
                    print("SUCCESS: youtube_search_v2 is registered in ToolRegistry.")
                else:
                    print("FAILURE: youtube_search_v2 not found in ToolRegistry.")
            else:
                print(f"FAILURE: {created_file} was not created.")

    except Exception as e:
        print(f"Exception during test: {e}")

if __name__ == "__main__":
    asyncio.run(test_tool_creation())
