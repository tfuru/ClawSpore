from typing import Any, Dict
from core.tools.base import BaseTool
from limbs.executor import executor
import shlex

class ListFilesTool(BaseTool):
    """隔離環境内のファイル一覧を取得するツール"""
    
    @property
    def name(self) -> str:
        return "ls"

    @property
    def description(self) -> str:
        return "隔離環境内の指定されたディレクトリにあるファイルやフォルダの一覧を取得します。"

    @property
    def parameters(self) -> Dict[str, Any]:
        return {
            "type": "object",
            "properties": {
                "path": {
                    "type": "string",
                    "description": "一覧を表示するディレクトリパス (デフォルトは現在のディレクトリ '.')",
                    "default": "."
                },
                "all": {
                    "type": "boolean",
                    "description": "隠しファイルも表示するかどうか",
                    "default": False
                }
            }
        }

    async def execute(self, path: str = ".", all: bool = False, **kwargs) -> str:
        cmd = ["ls", "-F"]
        if all:
            cmd.append("-a")
        cmd.append(path)
        
        session_id = kwargs.get("session_id")
        result = await executor.execute_tool(cmd, session_id=session_id)
        return result

class ReadFileTool(BaseTool):
    """隔離環境内のファイル内容を読み取るツール"""
    
    @property
    def name(self) -> str:
        return "cat"

    @property
    def description(self) -> str:
        return "隔離環境内の指定されたファイルのテキスト内容を読み取ります。"

    @property
    def parameters(self) -> Dict[str, Any]:
        return {
            "type": "object",
            "properties": {
                "path": {
                    "type": "string",
                    "description": "読み取るファイルのパス"
                }
            },
            "required": ["path"]
        }

    async def execute(self, path: str, **kwargs) -> str:
        cmd = ["cat", path]
        session_id = kwargs.get("session_id")
        result = await executor.execute_tool(cmd, session_id=session_id)
        return result

class WriteFileTool(BaseTool):
    """ファイルにテキストを書き込むツール"""
    
    @property
    def name(self) -> str:
        return "write_file"

    @property
    def description(self) -> str:
        return "隔離環境内の指定されたファイルにテキストを書き込みます。"

    @property
    def parameters(self) -> Dict[str, Any]:
        return {
            "type": "object",
            "properties": {
                "path": {"type": "string", "description": "書き込むファイルのパス"},
                "content": {"type": "string", "description": "書き込む内容"}
            },
            "required": ["path", "content"]
        }

    @property
    def requires_approval(self) -> bool:
        return True

    @property
    def is_dangerous(self) -> bool:
        return True

    async def execute(self, path: str, content: str, **kwargs) -> str:
        import base64
        b64_content = base64.b64encode(content.encode()).decode()
        cmd = ["sh", "-c", f"echo {b64_content} | base64 -d > {path}"]
        session_id = kwargs.get("session_id")
        return await executor.execute_tool(cmd, session_id=session_id)

class DeleteFileTool(BaseTool):
    """ファイルを削除するツール"""
    
    @property
    def name(self) -> str:
        return "rm"

    @property
    def description(self) -> str:
        return "隔離環境内の指定されたファイルまたはディレクトリを削除します。（危険な操作）"

    @property
    def parameters(self) -> Dict[str, Any]:
        return {
            "type": "object",
            "properties": {
                "path": {"type": "string", "description": "削除するファイルのパス"},
                "recursive": {"type": "boolean", "description": "ディレクトリを再帰的に削除するかどうか", "default": False}
            },
            "required": ["path"]
        }

    @property
    def requires_approval(self) -> bool:
        return True

    @property
    def is_dangerous(self) -> bool:
        return True

    async def execute(self, path: str, recursive: bool = False, **kwargs) -> str:
        cmd = ["rm"]
        if recursive:
            cmd.append("-rf")
        cmd.append(path)
        session_id = kwargs.get("session_id")
        return await executor.execute_tool(cmd, session_id=session_id)

# ツールをレジストリに登録するための関数
def register_file_tools(registry):
    registry.register_tool(ListFilesTool())
    registry.register_tool(ReadFileTool())
    registry.register_tool(WriteFileTool())
    registry.register_tool(DeleteFileTool())
