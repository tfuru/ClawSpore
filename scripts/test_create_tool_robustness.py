import asyncio
import os
import sys

# プロジェクトルートをパスに追加
sys.path.append(os.getcwd())

from core.tools.meta_tools import CreateToolTool
from core.tools.registry import tool_registry

async def test_robustness():
    tool = CreateToolTool()
    
    # テストケース1: new_tool_name なし、かつ末尾に } がある
    content_bad = """
class WikipediaSearchTool(BaseTool):
    def execute(self, query: str):
        return f"Searching for {query}"
}
"""
    print("--- Test Case 1: Missing new_tool_name + trailing } ---")
    # 実際は core.main 等でセッションIDが渡されるが、ここでは直接 execute を呼ぶ
    result = await tool.execute(content=content_bad, session_id="test_robust")
    print(f"Result: {result}")
    
    if "Successfully created" in result:
        print("✅ Test Case 1 Passed!")
        # 作成されたファイルを削除
        import glob
        files = glob.glob("core/tools/dynamic/wikipedia_search.py")
        for f in files:
            os.remove(f)
            print(f"Cleaned up: {f}")
    else:
        print("❌ Test Case 1 Failed.")

    # テストケース2: Markdown コードブロックが含まれている
    content_md = """```python
class MdTool(BaseTool):
    def execute(self, **kwargs):
        return "md"
```"""
    print("\n--- Test Case 2: Markdown code blocks ---")
    result = await tool.execute(content=content_md, session_id="test_md")
    print(f"Result: {result}")
    
    if "Successfully created" in result:
        print("✅ Test Case 2 Passed!")
        import glob
        files = glob.glob("core/tools/dynamic/md.py")
        for f in files:
            os.remove(f)
            print(f"Cleaned up: {f}")
    else:
        print("❌ Test Case 2 Failed.")

if __name__ == "__main__":
    asyncio.run(test_robustness())
