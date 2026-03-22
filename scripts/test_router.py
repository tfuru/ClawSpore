import asyncio
import os
import sys

# プロジェクトルートをパスに追加
sys.path.append(os.getcwd())

from core.tools.registry import tool_registry
from core.router import tool_router
from core.tools.base import BaseTool

# Mock Tools for testing the router logic
class CalculatorMock(BaseTool):
    @property
    def name(self): return "calculator"
    @property
    def description(self): return "数値の計算を行います。"
    @property
    def parameters(self): return {"type": "object", "properties": {"expression": {"type": "string"}}}
    async def execute(self, **kwargs): return "result"

class SearchMock(BaseTool):
    @property
    def name(self): return "gemini_search"
    @property
    def description(self): return "インターネットで情報を検索します。"
    @property
    def parameters(self): return {"type": "object", "properties": {"query": {"type": "string"}}}
    async def execute(self, **kwargs): return "result"

async def test_router():
    """
    ToolRouter のフィルタリング機能を検証するテスト。
    """
    print("Agent Router Verification Start...")
    
    # 既存のレジストリにモックを追加（テスト用の一時登録）
    tool_registry.register_tool(CalculatorMock())
    tool_registry.register_tool(SearchMock())
    
    test_cases = [
        {
            "prompt": "1+1は？",
            "expected_contain": "calculator"
        },
        {
            "prompt": "最新のニュースを教えて",
            "expected_contain": "gemini_search"
        },
        {
            "prompt": "おはよう！",
            "expected_not_contain": ["calculator", "gemini_search"]
        }
    ]
    
    for case in test_cases:
        prompt = case["prompt"]
        print(f"\n- Query: {prompt}")
        selected = await tool_router.select_tools(prompt)
        print(f"  Selected tools: {selected}")
        
        if "expected_contain" in case:
            assert case["expected_contain"] in selected, f"Failed: Expected {case['expected_contain']} to be selected."
        if "expected_not_contain" in case:
            for t in case["expected_not_contain"]:
                assert t not in selected, f"Failed: Tool {t} should NOT be selected for casual prompt."
    
    print("\n✅ Verification SUCCESS (Agent Router functionality is working correctly)")

if __name__ == "__main__":
    # このスクリプトは dotenvx run -- python ... で実行してください
    asyncio.run(test_router())
