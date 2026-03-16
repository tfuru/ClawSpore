import asyncio
from core.llm_client import llm

async def test_llm():
    print("🤖 LM Studio へのテスト送信を開始します...")
    prompt = "「クロウスポア」のシステムチェックを開始します。応答してください。"
    response = await llm.generate_response(prompt)
    print("-" * 30)
    print(f"LLM からの応答:\n{response}")
    print("-" * 30)

if __name__ == "__main__":
    asyncio.run(test_llm())
