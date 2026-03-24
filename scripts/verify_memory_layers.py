import asyncio
import os
import sys

# プロジェクトルートをパスに追加
sys.path.append(os.getcwd())

from core.memory import memory
from core.agent import agent

async def verify():
    session_id = "test_session_1"
    
    # 1. 初期状態の確認
    print("--- 1. 初期状態 ---")
    print(f"Episode Summary: {memory.get_episode_summary(session_id)}")
    
    # 2. 擬似的な会話の入力と要約更新のテスト
    print("\n--- 2. 会話入力 & エピソード要約更新 ---")
    user_msg = "今日は新しいメモリシステムの実装について話したいです。"
    assistant_msg = "承知いたしました。三層構造メモリ（短期・エピソード・長期）の設計と実装を進めましょう。"
    
    # メモリへの追加（本来は agent.process_message 内で行われる）
    memory.add_message(session_id, "user", user_msg)
    memory.add_message(session_id, "assistant", assistant_msg)
    
    # 手動で更新メソッドを呼ぶ（agent.py で実装したロジックの確認）
    await memory.update_episode_summary(session_id, user_msg, assistant_msg)
    
    new_summary = memory.get_episode_summary(session_id)
    print(f"Updated Episode Summary:\n{new_summary}")
    
    # 3. 三層プロンプト構築のテスト
    print("\n--- 3. 三層プロンプト構築 ---")
    # agent.process_message の一部をシミュレート
    system_msg = {"role": "system", "content": "You are ClawSpore."}
    other_messages = memory.get_messages(session_id)
    
    # Working Memory (Last 10 msgs)
    window_size = 10
    recent_context = other_messages[-window_size:]
    
    # Knowledge Memory (RAG)
    rag_context = memory.get_relevant_history(session_id, "メモリシステム", cross_session=True)
    
    # Episode Memory
    episode_context = memory.get_episode_summary(session_id)
    
    mem_instructions = []
    if episode_context:
        mem_instructions.append(f"### EPISODE MEMORY\n{episode_context}")
    if rag_context:
        mem_instructions.append(f"### KNOWLEDGE MEMORY\n{rag_context}")
        
    if mem_instructions:
        mem_msg = {"role": "system", "content": "\n\n".join(mem_instructions)}
        final_messages = [system_msg, mem_msg] + recent_context
    else:
        final_messages = [system_msg] + recent_context
        
    print(f"Final Message count: {len(final_messages)}")
    for i, m in enumerate(final_messages):
        print(f"Msg {i} ({m['role']}): {m['content'][:50]}...")

if __name__ == "__main__":
    asyncio.run(verify())
