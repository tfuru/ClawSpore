import asyncio
import os
import sys

# プロジェクトルートをパスに追加
sys.path.append(os.getcwd())

from core.tools.meta_tools import CreateToolTool
from core.tools.registry import tool_registry

async def verify_pip():
    tool = CreateToolTool()
    
    # wikipedia モジュールをインポートするツール
    # wikipedia は標準ではインストールされていないはず
    content = """
import wikipedia
from core.tools.base import BaseTool

class WikipediaSearchTool(BaseTool):
    @property
    def name(self):
        return "wikipedia_search"
        
    @property
    def description(self):
        return "Search Wikipedia"
        
    @property
    def parameters(self):
        return {"type": "object", "properties": {"query": {"type": "string"}}, "required": ["query"]}

    async def execute(self, query: str, **kwargs):
        wikipedia.set_lang("ja")
        return wikipedia.summary(query, sentences=1)
"""

    print("--- Verifying create_tool with automatic pip install (wikipedia) ---")
    result = await tool.execute(content=content, new_tool_name="wikipedia_search_test")
    print(f"Result: {result}")
    
    if "Successfully created" in result:
        print("✅ Success: Tool created and registered.")
        
        # 実際に使えるか試してみる
        wiki_tool = tool_registry.get_tool("wikipedia_search")
        if wiki_tool:
            try:
                res = await wiki_tool.execute(query="富士山")
                print(f"Tool Execution Result: {res[:100]}...")
                print("✅ Success: Tool executed and wikipedia module worked!")
            except Exception as e:
                print(f"❌ Execution Failed: {e}")
        else:
            print("❌ Tool not found in registry.")
            
        # クリーンアップ
        file_path = "core/tools/dynamic/wikipedia_search_test.py"
        if os.path.exists(file_path):
            os.remove(file_path)
    else:
        print(f"❌ Failed: {result}")

if __name__ == "__main__":
    asyncio.run(verify_pip())
