import asyncio
import os
from dotenv import load_dotenv

# dotenv を読み込み環境変数をセット
load_dotenv()

from core.agent import agent
from core.tools.registry import tool_registry
from core.tools.file_ops import register_file_tools

async def mock_discord_send(msg):
    print(f"\n[DISCORD MOCK] {msg}\n")

async def run():
    print("--- ツールを登録 ---")
    register_file_tools(tool_registry)
    
    print("\n--- Agent のテスト開始 ---")
    prompt = "現在のディレクトリのファイル一覧を調べてから、README.md の最初の数行を読んで概要を教えてください。"
    print(f"ユーザー入力: {prompt}")
    
    error = await agent.process_message("test_session_1", prompt, mock_discord_send)
    if error:
        print(f"Agent Error: {error}")

if __name__ == "__main__":
    asyncio.run(run())
