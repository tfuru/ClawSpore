import asyncio
import os
import sys

# プロジェクトルートをパスに追加
sys.path.append(os.getcwd())

from core.memory import memory
from core.tools.dynamic.check_memory import CheckMemoryTool

async def verify_tool():
    session_id = "test_tool_session"
    tool = CheckMemoryTool()
    
    # ダミーのエピソード要約をセット
    memory.episode_summaries[session_id] = "これはテスト用のセッション要約です。三層メモリの動作を確認しています。"
    
    print("--- Testing check_memory mode='episode' ---")
    result = await tool.execute(mode="episode", session_id=session_id)
    print(result)
    
    if "これはテスト用のセッション要約です" in result:
        print("\n✅ Verification Successful: episode mode returned correct summary.")
    else:
        print("\n❌ Verification Failed.")

if __name__ == "__main__":
    asyncio.run(verify_tool())
