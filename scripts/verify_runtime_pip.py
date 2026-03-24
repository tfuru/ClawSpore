import asyncio
import os
import sys

# プロジェクトルートをパスに追加
sys.path.append(os.getcwd())

from core.tools.base import BaseTool
from core.tools.registry import tool_registry

class RuntimeImportTool(BaseTool):
    @property
    def name(self): return "runtime_import_test"
    @property
    def description(self): return "Test runtime import"
    @property
    def parameters(self): return {"type": "object", "properties": {}}

    async def execute(self, **kwargs):
        # 実行時にインポートを試みる (qrcode はインストールされていない想定)
        import qrcode
        img = qrcode.make('ClawSpore Runtime Test')
        return f"Successfully generated QR code object: {type(img)}"

async def verify_runtime():
    # ツールを手動で登録
    tool = RuntimeImportTool()
    tool_registry.register_tool(tool)
    
    print("--- Verifying runtime pip install (qrcode) ---")
    # call_tool 経由で実行 (ここでエラーハンドリングが走るはず)
    result = await tool_registry.call_tool("runtime_import_test")
    print(f"Final Result: {result}")
    
    if "Successfully generated" in result:
        print("✅ Success: Runtime dependency was resolved and execution succeeded on retry.")
    else:
        print("❌ Failed.")

if __name__ == "__main__":
    asyncio.run(verify_runtime())
