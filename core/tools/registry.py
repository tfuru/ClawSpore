from typing import Dict, List, Any
from core.tools.base import BaseTool
import importlib
import pkgutil
import os
import inspect

class ToolRegistry:
    """
    利用可能なツールを管理し、LLM へ提供する定義を生成するクラス。
    """
    def __init__(self):
        self._tools: Dict[str, BaseTool] = {}

    def register_tool(self, tool: BaseTool):
        """ツールを登録する"""
        self._tools[tool.name] = tool
        print(f"ToolRegistry: Registered tool '{tool.name}'")

    def get_tool(self, name: str) -> BaseTool:
        """名前でツールを取得する"""
        return self._tools.get(name)

    def unregister_tool(self, name: str):
        """指定された名前のツールを登録解除する"""
        if name in self._tools:
            del self._tools[name]
            print(f"ToolRegistry: Unregistered tool '{name}'")

    def get_tool_definitions(self) -> List[Dict[str, Any]]:
        """全てのツールの定義をリスト形式で取得 (LLM 用)"""
        return [tool.to_tool_def() for tool in self._tools.values()]

    def get_tools_overview(self) -> str:
        """全てのツールの名前と説明の概要を取得 (ルーター用)"""
        overview = []
        for tool in self._tools.values():
            overview.append(f"- {tool.name}: {tool.description}")
        return "\n".join(overview)

    def get_tool_source(self, name: str) -> str:
        """指定されたツールのソースコードを取得する"""
        tool = self.get_tool(name)
        if not tool:
            return f"Error: Tool '{name}' not found."
        try:
            return inspect.getsource(tool.__class__)
        except Exception as e:
            return f"Error retrieving source for '{name}': {e}"

    async def call_tool(self, name: str, **kwargs) -> Any:
        """名前を指定してツールを実行する"""
        tool = self.get_tool(name)
        if not tool:
            return f"Error: Tool '{name}' not found."
        
        try:
            # kwargs には session_id や discord_send_callback などが含まれる
            return await tool.execute(**kwargs)
        except Exception as e:
            import traceback
            tb = traceback.format_exc()
            print(f"DEBUG: Error executing tool '{name}': {e}")
            print(tb)
            
            # 自己修復のための詳細なフィードバック
            source = self.get_tool_source(name)
            return (
                f"❌ Error executing tool '{name}': {e}\n\n"
                f"--- Traceback ---\n{tb}\n"
                f"--- Tool Source Code ({name}) ---\n{source}\n"
                "Please analyze the error and source code, and fix the tool if necessary using 'create_tool'."
            )

    def load_dynamic_tools(self, package_path: str = "core.tools.dynamic") -> Dict[str, Any]:
        """
        指定されたパッケージ（ディレクトリ）内のツールを動的にロードする。
        戻り値: { "success": bool, "details": { "module_name": "status or error" } }
        """
        results = {"success": True, "details": {}}
        try:
            importlib.invalidate_caches()
            
            try:
                if package_path in os.sys.modules:
                    package = importlib.reload(os.sys.modules[package_path])
                else:
                    package = importlib.import_module(package_path)
            except Exception as e:
                msg = f"Failed to load/reload package: {e}"
                print(f"ToolRegistry Warning: {msg}")
                return {"success": False, "details": {"package": msg}}

            if not hasattr(package, "__path__"):
                return {"success": True, "details": {"info": "No tools directory found."}}

            all_modules_success = True
            for _, name, is_pkg in pkgutil.iter_modules(package.__path__):
                if is_pkg:
                    continue
                
                module_name = f"{package_path}.{name}"
                try:
                    if module_name in os.sys.modules:
                        module = importlib.reload(os.sys.modules[module_name])
                    else:
                        module = importlib.import_module(module_name)
                    
                    found_classes = 0
                    for member_name, obj in inspect.getmembers(module):
                        if inspect.isclass(obj) and issubclass(obj, BaseTool) and obj is not BaseTool:
                            instance = obj()
                            self.register_tool(instance)
                            found_classes += 1
                    
                    results["details"][name] = f"Loaded {found_classes} tools"
                except Exception as module_error:
                    error_msg = str(module_error)
                    print(f"ToolRegistry Error: Failed to load module '{name}': {error_msg}")
                    results["details"][name] = f"Error: {error_msg}"
                    all_modules_success = False
            
            results["success"] = all_modules_success
            return results
        except Exception as e:
            msg = f"Fatal error during dynamic loading: {e}"
            print(f"ToolRegistry Error: {msg}")
            return {"success": False, "details": {"fatal": msg}}

# シングルトンインスタンス
tool_registry = ToolRegistry()
