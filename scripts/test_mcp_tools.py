import asyncio
import json
from core.tools.registry import tool_registry
from core.tools.file_ops import register_file_tools
from core.llm_client import llm

async def test_tool_integration():
    print("🛠️  MCP ツール統合テストを開始します...")
    
    # 1. ツール登録
    register_file_tools(tool_registry)
    
    # 2. ツール定義の取得テスト
    tool_defs = tool_registry.get_tool_definitions()
    print(f"\n[Test 1] Tool Definitions (Total: {len(tool_defs)}):")
    # print(json.dumps(tool_defs, indent=2, ensure_ascii=False))

    # 3. ツール単体実行テスト (ls)
    print("\n[Test 2] Direct tool execution (ls):")
    result = await tool_registry.call_tool("ls", path=".")
    print(f"Result of 'ls .':\n{result}")

    # 4. LLM へのツール提示テスト (擬似)
    print("\n[Test 3] LLM tool suggestion test:")
    prompt = "隔離環境内のファイル構成を教えてください。"
    print(f"Prompt: {prompt}")
    
    # 注意: LM Studio 側のモデルが Tool Use に対応している必要があります
    response = await llm.generate_response(prompt, tool_definitions=tool_defs)
    
    if hasattr(response, "tool_calls") and response.tool_calls:
        print("✅ LLM がツール実行を要求しました!")
        for call in response.tool_calls:
            print(f"- Tool: {call.function.name}")
            print(f"- Args: {call.function.arguments}")
            
            # 要求に従ってツールを実行
            args = json.loads(call.function.arguments)
            tool_result = await tool_registry.call_tool(call.function.name, **args)
            print(f"- Tool Result:\n{tool_result}")
    else:
        print("ℹ️  LLM は通常のテキストで回答しました（モデルが対応していないか、不要と判断されました）")
        print(f"Response: {response}")

if __name__ == "__main__":
    asyncio.run(test_tool_integration())
