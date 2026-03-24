import asyncio
import os
import sys

# プロジェクトルートをパスに追加
sys.path.append(os.getcwd())

from core.memory import memory

def test_clear():
    session_id = "test_clear_session"
    
    # ダミーデータをセット
    memory.add_message(session_id, "user", "Hello")
    memory.episode_summaries[session_id] = "Previous conversation summary"
    
    print(f"--- Before Clear ---")
    print(f"Messages: {len(memory.get_messages(session_id))}")
    print(f"Episode Summary exists: {session_id in memory.episode_summaries}")
    
    # クリア実行
    print(f"\n--- Running memory.clear('{session_id}') ---")
    memory.clear(session_id)
    
    print(f"\n--- After Clear ---")
    print(f"Messages: {len(memory.get_messages(session_id))}")
    print(f"Episode Summary exists: {session_id in memory.episode_summaries}")
    
    if len(memory.get_messages(session_id)) == 0 and session_id not in memory.episode_summaries:
        print("\n✅ Verification Successful: clear() resets both messages and episode summary.")
    else:
        print("\n❌ Verification Failed.")

if __name__ == "__main__":
    test_clear()
