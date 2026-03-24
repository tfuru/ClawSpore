import asyncio
import os
import sys

# プロジェクトルートをパスに追加
sys.path.append(os.getcwd())

from core.tools.base import BaseTool
from core.tools.registry import tool_registry

class StringErrorTool(BaseTool):
    @property
    def name(self): return "string_error_test"
    @property
    def description(self): return "Test string error response"
    @property
    def parameters(self): return {"type": "object", "properties": {}}

    async def execute(self, **kwargs):
        try:
            # lxml はインストールされていない想定 (または適当な名前)
            import some_missing_package_xyz
            return "Success"
        except Exception as e:
            # ツールが自前でエラーメッセージを返すケースを模倣
            return f"Error occurred: {e}"

async def verify_string_error():
    # ツールを手動で登録
    tool = StringErrorTool()
    tool_registry.register_tool(tool)
    
    print("--- Verifying runtime pip install via string error (some_missing_package_xyz) ---")
    # call_tool 経由で実行
    result = await tool_registry.call_tool("string_error_test")
    print(f"Final Result: {result}")
    
    if "Successfully installed" in str(sys.modules.get('some_missing_package_xyz', '')): # install_package mocks might be needed but let's see
        # Actually in verify_runtime_pip, it really installed qrcode.
        # This will try to pip install some_missing_package_xyz which will fail.
        # But we want to see if it ATTEMPTED it.
        pass
    
    # We expect it to TRY installing some_missing_package_xyz
    # Since that package doesn't exist, it will eventually fail the install, 
    # but the logs should show the attempt.

if __name__ == "__main__":
    asyncio.run(verify_string_error())
