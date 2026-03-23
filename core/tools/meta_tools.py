import os
import re
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
            "システムに新しいツール（Pythonスクリプト）を動的に作成、または既存のツールを上書き更新します。\n"
            "以下の実装ルールを厳守してください：\n"
            "1. 'from core.tools.base import BaseTool' をインポートしてください（自動補完機能もあります）。\n"
            "2. 'BaseTool' を継承したクラスを定義してください。\n"
            "3. 必須プロパティ: 'name' (str), 'description' (str), 'parameters' (dict) を実装してください。\n"
            "   - 'name' は必ずスペースなしの小文字（例: 'my_new_tool'）にしてください。\n"
            "4. 必須メソッド: 'async def execute(self, **kwargs) -> Any' を実装し、必ず **kwargs を受け取るようにしてください。\n"
            "5. Pythonの構文（特に括弧の対応、インデント）に細心の注意を払ってください。\n"
            "既存のツールを更新する場合は、new_tool_name にそのツールのファイル名を指定して実行してください。"
        )

    @property
    def parameters(self) -> dict:
        return {
            "type": "object",
            "properties": {
                "new_tool_name": {
                    "type": "string",
                    "description": "作成または更新するツールのファイル名（拡張子なし）。既存のツールを更新する場合は、InspectTool等で確認した正確な名前を指定してください。"
                },
                "content": {
                    "type": "string",
                    "description": "ツールのPythonコード全体。'from core.tools.base import BaseTool' を含み、BaseToolを継承したクラスを定義してください。name, description, parameters プロパティと execute(self, **kwargs) メソッドが必須です。"
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
            # --- 0. 自動修正ロジック ---
            # クラス定義を探す (class Name または class Name(Parent))
            class_match = re.search(r"^class\s+([a-zA-Z0-9_]+)(\(([^)]*)\))?\s*:", content, re.MULTILINE)
            if class_match:
                class_name = class_match.group(1)
                parents = class_match.group(3) or ""
                
                # BaseTool が継承リストにない場合、追加
                if "BaseTool" not in parents:
                    if parents:
                        new_parents = f"BaseTool, {parents}"
                    else:
                        new_parents = "BaseTool"
                    
                    # クラス定義行を置換
                    old_class_def = class_match.group(0)
                    new_class_def = f"class {class_name}({new_parents}):"
                    content = content.replace(old_class_def, new_class_def)
            
            # BaseTool の import がない場合、先頭に追加
            if "from core.tools.base import BaseTool" not in content:
                content = "from core.tools.base import BaseTool\n" + content

            # --- 0.5. 抽象メソッドの自動補完 ---
            # クラスの内容を解析して不足しているプロパティ/メソッドを補完
            if class_match:
                class_body = content[class_match.end():]
                
                # 1. name プロパティ (クラス変数としての定義もチェック、および snake_case 強制)
                has_name_prop = "@property\n    def name" in class_body or "def name(self)" in class_body
                if has_name_prop:
                    # 既存の name プロパティの戻り値を snake_case に強制
                    def normalize_name(match):
                        name_val = match.group(1).strip("'\"")
                        # スペースをアンダースコアに変換し、小文字化
                        snake_val = re.sub(r'\s+', '_', name_val).lower()
                        return f"return \"{snake_val}\""
                    
                    content = re.sub(r"return\s+(['\"].*?['\"])", normalize_name, content, count=1)
                else:
                    # クラス変数としての定義 (name = "...") を探す
                    var_match = re.search(r"^\s+name\s*=\s*(['\"].*?['\"])", class_body, re.MULTILINE)
                    if var_match:
                        val = var_match.group(1).strip("'\"")
                        snake_val = re.sub(r'\s+', '_', val).lower()
                        content = content.replace(var_match.group(0), f"\n    @property\n    def name(self) -> str:\n        return \"{snake_val}\"")
                    else:
                        snake_name = re.sub(r'(?<!^)(?=[A-Z])', '_', class_name).lower().replace("_tool", "")
                        insertion = f"\n    @property\n    def name(self) -> str:\n        return \"{snake_name}\"\n"
                        content = re.sub(r"(class\s+" + class_name + r"(?:\([^)]*\))?\s*:)", r"\1" + insertion, content)

                # 2. description プロパティ
                has_desc_prop = "@property\n    def description" in content or "def description(self)" in content
                if not has_desc_prop:
                    var_match = re.search(r"^\s+description\s*=\s*(['\"].*?['\"])", content, re.MULTILINE)
                    if var_match:
                        val = var_match.group(1)
                        content = content.replace(var_match.group(0), f"\n    @property\n    def description(self) -> str:\n        return {val}")
                    else:
                        insertion = f"\n    @property\n    def description(self) -> str:\n        return \"Auto-generated tool for {class_name}\"\n"
                        content = re.sub(r"(class\s+" + class_name + r"(?:\([^)]*\))?\s*:)", r"\1" + insertion, content)

                # 3. parameters プロパティの補完
                has_params_prop = "@property\n    def parameters" in content or "def parameters(self)" in content
                if not has_params_prop:
                    var_match = re.search(r"^\s+parameters\s*=\s*(\{.*?\})", content, re.DOTALL | re.MULTILINE)
                    if var_match:
                        val = var_match.group(1)
                        content = content.replace(var_match.group(0), f"\n    @property\n    def parameters(self) -> dict:\n        return {val}")
                    else:
                        # run または execute の引数から推論
                        target_method = "run" if "def run(self" in content else "execute"
                        method_match = re.search(r"def " + target_method + r"\(self,?\s*([^)]*)\)", content)
                        props = {}
                        req = []
                        if method_match:
                            args = method_match.group(1)
                            for arg in args.split(","):
                                arg = arg.strip()
                                if not arg or arg == "**kwargs": continue
                                name_part = arg.split(":")[0].split("=")[0].strip()
                                props[name_part] = {"type": "string", "description": f"Argument {name_part}"}
                                if "=" not in arg: req.append(name_part)
                        
                        import json
                        params_json = json.dumps({"type": "object", "properties": props, "required": req}, indent=8)
                        insertion = f"\n    @property\n    def parameters(self) -> dict:\n        return {params_json.strip()}\n"
                        content = re.sub(r"(class\s+" + class_name + r"(?:\([^)]*\))?\s*:)", r"\1" + insertion, content)

                # 4. execute メソッドの補完 (run がある場合)
                if "async def execute" not in content and "def execute(self)" not in content:
                    if "def run(self" in content or "async def run(self" in content:
                        is_async_run = "async def run(self" in content
                        await_prefix = "await " if is_async_run else ""
                        insertion = f"\n    async def execute(self, **kwargs) -> Any:\n        return {await_prefix}self.run(**kwargs)\n"
                        content = re.sub(r"(class\s+" + class_name + r"(?:\([^)]*\))?\s*:)", r"\1" + insertion, content)

                # 5. execute メソッドの引数に **kwargs を強制
                if "def execute(self" in content:
                    # execute が定義されているが **kwargs がない場合を修正
                    # async や型ヒント、戻り値の型指定 (-> Type) に対応
                    def_match = re.search(r"(async\s+)?def\s+execute\(self,?\s*([^)]*)\)(\s*->\s*[^:]+)?\s*:", content)
                    if def_match:
                        prefix = def_match.group(1) or ""
                        args_content = def_match.group(2)
                        return_type = def_match.group(3) or ""
                        
                        if "**kwargs" not in args_content:
                            new_args = args_content.strip()
                            if new_args and not new_args.endswith(","):
                                new_args += ", **kwargs"
                            elif not new_args:
                                new_args = "**kwargs"
                            else:
                                new_args += " **kwargs"
                            
                            old_line = def_match.group(0)
                            new_line = f"{prefix}def execute(self, {new_args}){return_type}:"
                            content = content.replace(old_line, new_line)

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
            
            return f"Successfully created/updated dynamic tool: {new_tool_name}. You can now use the new tools from this file."
            
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
            
            # 1. tool_filename をツール名（name）として解釈し、モジュール名からファイル名を逆引きしてみる
            actual_filename = tool_filename
            tool = tool_registry.get_tool(tool_filename)
            if tool:
                module_name = tool.__class__.__module__
                if module_name.startswith("core.tools.dynamic."):
                    actual_filename = module_name.split(".")[-1]
                    print(f"MetaTool: Resolved tool name '{tool_filename}' to file '{actual_filename}.py'")

            file_path = os.path.join(dynamic_dir, f"{actual_filename}.py")
            
            if not os.path.exists(file_path):
                # もし解決後のパスで見つからない場合は、元々の名前でもう一度試す
                file_path = os.path.join(dynamic_dir, f"{tool_filename}.py")
                if not os.path.exists(file_path):
                    return f"Error: Tool file for '{tool_filename}' not found (checked {actual_filename}.py and {tool_filename}.py)."
                actual_filename = tool_filename
            
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
            module_name = f"core.tools.dynamic.{actual_filename}"
            tool_registry.unregister_tools_by_module(module_name)
            
            return f"Successfully removed tool from file: {actual_filename}.py. The tool has been unregistered."
            
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
        module = tool.__class__.__module__
        return (
            f"--- Tool Info: {tool_name} ---\n"
            f"Module: {module}\n"
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
