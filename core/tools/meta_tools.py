import os
from typing import Any
from core.tools.base import BaseTool
from core.tools.registry import tool_registry

class CreateToolTool(BaseTool):
    """
    AI自身が新しいツール（Pythonコード）を生成し、システムに登録するための「ツールを作るツール」。
    このツールを使うことで、現在のツールセットでは不可能なタスクを解決できるようになります。
    """
    
    @property
    def name(self) -> str:
        return "create_tool"

    @property
    def description(self) -> str:
        return (
            "システムに新しいツール（Pythonスクリプト）を動的に作成し、追加登録します。\n"
            "【重要】Pythonの構文（特に括弧の対応、インデント）に細心の注意を払ってください。\n"
            "JSON形式と混同して、Pythonコード内のブロックの終わりに '}' を置かないように注意してください。\n"
            "現在のツールで解決できない問題がある場合、このツールを使って専用のコードを書き、新しいツールとして組み込みます。"
        )

    @property
    def parameters(self) -> dict:
        return {
            "type": "object",
            "properties": {
                "new_tool_name": {
                    "type": "string",
                    "description": "作成するツールのファイル名（拡張子なし）。例: 'web_search_tool'"
                },
                "content": {
                    "type": "string",
                    "description": "ツールのPythonコード全体。BaseToolを継承したクラスを定義し、正しいPython構文で記述してください。"
                }
            },
            "required": ["new_tool_name", "content"]
        }

    def requires_approval(self) -> bool:
        return True  # 任意のコードを実行可能にするため、必ずユーザーの承認を求める

    @property
    def is_dangerous(self) -> bool:
        return True

    async def execute(self, new_tool_name: str, content: str, **kwargs) -> Any:
        try:
            # --- 1. 構文チェック ---
            try:
                compile(content, f"<dynamic_tool:{new_tool_name}>", "exec")
            except SyntaxError as se:
                return (
                    f"Error: Syntax error detected in your Python code.\n"
                    f"Line {se.lineno}: {se.msg}\n"
                    f"Code: {se.text.strip() if se.text else ''}\n"
                    "Please fix the syntax and try again."
                )

            # dynamic ツール用ディレクトリのパス
            dynamic_dir = os.path.join(os.path.dirname(__file__), "dynamic")
            os.makedirs(dynamic_dir, exist_ok=True)
            
            # __init__.py がなければ作成
            init_file = os.path.join(dynamic_dir, "__init__.py")
            if not os.path.exists(init_file):
                with open(init_file, "w") as f:
                    f.write("# Auto-generated package init\n")
            
            # Python ファイルの保存
            file_path = os.path.join(dynamic_dir, f"{new_tool_name}.py")
            with open(file_path, "w") as f:
                f.write(content)
                
            print(f"MetaTool: Saved new tool to {file_path}")
            
            # --- 2. ツールを動的にロード ---
            load_result = tool_registry.load_dynamic_tools("core.tools.dynamic")
            
            # ロード結果の判定
            # 作成したツールが詳細に含まれているか、および 0 tools でないかを確認
            detail = load_result["details"].get(new_tool_name, "")
            is_success = "Loaded" in detail and "Loaded 0 tools" not in detail
            
            if not is_success:
                # ロードに失敗した場合はファイルを削除してロールバック
                if os.path.exists(file_path):
                    os.remove(file_path)
                    print(f"MetaTool: Deleted failed tool file {file_path}")
                
                error_info = detail if detail else 'Tool class not found or failed to initialize'
                if "Loaded 0 tools" in detail:
                    error_info = "The code compiled BUT no BaseTool subclass was found. You MUST define a class inheriting from BaseTool."

                return (
                    f"Action Required: The tool '{new_tool_name}' was saved but FAILED to register.\n"
                    f"Error Detail: {error_info}\n"
                    "The invalid file has been removed. Please correct the Python code (ensure you use a class) and try again."
                )
            
            return f"Successfully created and loaded dynamic tool: {new_tool_name}. You can now use the new tools from this file."
            
        except Exception as e:
            return f"Error creating new tool: {e}"

class RemoveToolTool(BaseTool):
    """
    動的に作成された不要なツール（Pythonファイル）を削除し、システムから抹消します。
    """
    @property
    def name(self) -> str:
        return "remove_tool"

    @property
    def description(self) -> str:
        return "指定された動的ツール（ファイル）を物理削除し、システムから登録解除します。"

    @property
    def parameters(self) -> dict:
        return {
            "type": "object",
            "properties": {
                "tool_filename": {
                    "type": "string",
                    "description": "削除するツールのファイル名（拡張子なし）。例: 'web_search_tool'"
                }
            },
            "required": ["tool_filename"]
        }

    def requires_approval(self) -> bool:
        return True

    @property
    def is_dangerous(self) -> bool:
        return True

    async def execute(self, tool_filename: str, **kwargs) -> Any:
        try:
            dynamic_dir = os.path.join(os.path.dirname(__file__), "dynamic")
            file_path = os.path.join(dynamic_dir, f"{tool_filename}.py")
            
            if not os.path.exists(file_path):
                return f"Error: Tool file {tool_filename}.py not found."
            
            # ファイルを削除
            os.remove(file_path)
            print(f"MetaTool: Removed tool file {file_path}")
            
            # キャッシュも削除を試みる
            pycache_dir = os.path.join(dynamic_dir, "__pycache__")
            if os.path.exists(pycache_dir):
                import shutil
                try:
                    shutil.rmtree(pycache_dir)
                except Exception:
                    pass

            # 現在ロードされているツールの中から、このファイルに由来するものを抹消
            # (ファイル名とツール名が一致している前提、または再ロードで反映)
            # 一旦、登録されている全ツールをリフレッシュするために、
            # 現在のツールセットから dynamic 系を一旦すべて消すのは難しいため、
            # 再読み込みを行う
            tool_registry.load_dynamic_tools("core.tools.dynamic")
            
            # 注意: 既存のクラス定義がメモリに残る可能性があるため、
            # 本来は unregister_tool(name) を確実に呼ぶ必要があるが、
            # load_dynamic_tools は「ファイルがあるものだけを登録」するため、
            # 物理ファイルがない場合は上書きされない。
            # そのため、現状の Registry の仕組み上は、手動で辞書から消す必要がある。
            # ここではシンプルに「リロード」を促し、ユーザーには再起動を推奨する形にするか、
            # あるいはツール名 = ファイル名と想定して削除を試みる。
            tool_registry.unregister_tool(tool_filename) 
            
            return f"Successfully removed tool: {tool_filename}. The file has been deleted and the tool has been unregistered."
            
        except Exception as e:
            return f"Error removing tool: {e}"

class InspectTool(BaseTool):
    """
    既存のツールの詳細（説明、パラメータ、ソースコード）を確認するためのツール。
    自己修復や、他のツールの実装を参考にするために使用します。
    """
    @property
    def name(self) -> str:
        return "inspect_tool"

    @property
    def description(self) -> str:
        return "指定されたツールの登録情報とPythonソースコードを表示します。"

    @property
    def parameters(self) -> dict:
        return {
            "type": "object",
            "properties": {
                "tool_name": {
                    "type": "string",
                    "description": "確認したいツールの名前"
                }
            },
            "required": ["tool_name"]
        }

    async def execute(self, tool_name: str, **kwargs) -> Any:
        tool = tool_registry.get_tool(tool_name)
        if not tool:
            return f"Error: Tool '{tool_name}' not found."
        
        source = tool_registry.get_tool_source(tool_name)
        return (
            f"--- Tool Info: {tool_name} ---\n"
            f"Description: {tool.description}\n"
            f"Parameters: {tool.parameters}\n\n"
            f"--- Source Code ---\n{source}"
        )

from core.tools.test_runner import TestRunnerTool

def register_meta_tools(registry):
    """メタツールをレジストリに登録する"""
    registry.register_tool(CreateToolTool())
    registry.register_tool(RemoveToolTool())
    registry.register_tool(TestRunnerTool())
    registry.register_tool(InspectTool())
