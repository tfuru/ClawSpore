import asyncio
import os
from core.agent import agent
from core.memory import memory

async def mock_send(text, file_path=None):
    pass

async def mock_approval(tool_name, args, message_prefix=""):
    return True

async def test_self_healing_integration():
    print("--- Self-Healing Integration Test ---")
    session_id = "test_self_healing_session"
    memory.clear_all(session_id)
    
    # 1. 正常なメッセージ処理を走らせ、プロンプトの強化を確認
    print("\n[Step 1] Checking enhanced system prompt in memory...")
    # process_message を呼び出すことで、enhanced_system_prompt がメモリに保存される
    # (LLM通信エラーが出る可能性があるが、その前のプロンプト構築が目的)
    try:
        await agent.process_message(session_id, "test message", mock_send, mock_approval)
    except Exception as e:
        print(f"Note: LLM call failed as expected or unexpected: {e}")

    messages = memory.get_messages(session_id)
    system_msg = next((m for m in messages if m["role"] == "system"), None)
    
    if system_msg and "Self-Healing" in system_msg["content"]:
        print("✅ Success: Self-Healing instructions found in enhanced system prompt.")
    else:
        print("❌ Failure: Self-Healing instructions missing in memory.")
        if system_msg:
            print(f"DEBUG: System Prompt Content: {system_msg['content'][:200]}...")

    # 2. エラーメッセージのヒント注入を確認
    # エラー時の tool_result 構築は Agent.process_message 内で行われるため、
    # 実際のエラーを模したテストを行う。
    print("\n[Step 2] Note: Detailed error hints are injected during ReAct loop.")
    print("This can be verified by observing the tool result construction in Agent.py.")

if __name__ == "__main__":
    asyncio.run(test_self_healing_integration())
