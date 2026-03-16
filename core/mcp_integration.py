import asyncio
import shlex
import os
import json
import re
from typing import Any, Dict, Optional, List
from mcp import ClientSession, StdioServerParameters
from mcp.client.stdio import stdio_client
from core.tools.base import BaseTool
from core.tools.registry import tool_registry

class MCPToolWrapper(BaseTool):
    """
    外部 MCP サーバーのツールを ClawSpore の BaseTool として振る舞わせるラッパー。
    """
    def __init__(self, server_name: str, mcp_tool_def: Any, session: ClientSession):
        self._server_name = server_name
        self._mcp_tool_def = mcp_tool_def
        self._session = session
        
        # MCP の Tool 定義を取得
        self._name = mcp_tool_def.name
        self._description = mcp_tool_def.description or ""
        self._parameters = mcp_tool_def.inputSchema

    @property
    def name(self) -> str:
        # LLM の関数名として使えるようにサニタイズ (英数字とアンダースコアのみ)
        raw_name = f"{self._server_name}_{self._name}"
        return re.sub(r'[^a-zA-Z0-9_]', '_', raw_name)

    @property
    def description(self) -> str:
        return f"[MCP: {self._server_name}] {self._description}"

    @property
    def parameters(self) -> Dict[str, Any]:
        return self._parameters

    async def execute(self, **kwargs) -> Any:
        try:
            # 引数の型変換 (LLM が文字列で渡してくることがあるため、Schema に合わせる)
            processed_args = {}
            properties = self._parameters.get("properties", {})
            for k, v in kwargs.items():
                target_type = properties.get(k, {}).get("type")
                if target_type == "integer" and isinstance(v, str):
                    try:
                        processed_args[k] = int(v)
                    except ValueError:
                        processed_args[k] = v
                elif target_type == "number" and isinstance(v, str):
                    try:
                        processed_args[k] = float(v)
                    except ValueError:
                        processed_args[k] = v
                else:
                    processed_args[k] = v

            # MCP サーバーに対してツール実行をリクエスト
            result = await self._session.call_tool(self._name, arguments=processed_args)
            
            # 結果をテキスト化して返す
            output = []
            for content in result.content:
                if content.type == "text":
                    output.append(content.text)
            
            return "\n".join(output) if output else "No text output."
        except Exception as e:
            return f"Error executing MCP tool '{self._name}': {e}"

class MCPIntegrationManager:
    """
    外部 MCP サーバーを管轄するマネージャー
    """
    def __init__(self):
        self.active_sessions: Dict[str, ClientSession] = {}
        # 終了時にプロセスを閉じるためのコンテキスト管理用リスト
        self._exit_stacks = []
        
        # 設定の保存先
        self.config_path = os.path.join(os.path.dirname(__file__), 'data', 'mcp_servers.json')
        # 保存先ディレクトリがなければ作成
        os.makedirs(os.path.dirname(self.config_path), exist_ok=True)
        # メモリ上の設定キャッシュ
        self.saved_servers = self._load_config()

    def _load_config(self) -> Dict[str, Any]:
        if os.path.exists(self.config_path):
            try:
                with open(self.config_path, 'r') as f:
                    return json.load(f)
            except Exception as e:
                print(f"Error loading MCP config: {e}")
        return {}

    def _save_config(self):
        try:
            with open(self.config_path, 'w') as f:
                json.dump(self.saved_servers, f, indent=2, ensure_ascii=False)
        except Exception as e:
            print(f"Error saving MCP config: {e}")

    async def load_servers(self):
        """起動時に保存されたサーバーを再接続する。"""
        if not self.saved_servers:
            return
        
        print(f"MCPManager: 永続化された {len(self.saved_servers)} 件のMCPサーバーを自動復元します...")
        for server_name, config in self.saved_servers.items():
            try:
                result = await self.connect_server(
                    server_name, 
                    config.get("command"), 
                    env=config.get("env"),
                    save=False # すでに保存されているので再保存しない
                )
                print(f"Restored MCP server '{server_name}': {result}")
            except Exception as e:
                print(f"Failed to restore MCP server '{server_name}': {e}")

    async def connect_server(self, server_name: str, command: str, env: Optional[Dict[str, str]] = None, save: bool = True) -> str:
        """
        サブプロセスとして MCP サーバーを起動し、接続を確立してツールを登録する。
        """
        # サーバー名をサニタイズ (英数字とアンダースコアのみ)
        server_name = re.sub(r'[^a-zA-Z0-9_]', '_', server_name)
        
        if server_name in self.active_sessions:
            return f"Error: MCP Server '{server_name}' is already connected."

        import contextlib
        # SSH鍵が生成されていることを保証するため executor をロード
        from limbs.executor import executor
        
        print(f"MCPManager: Connecting to {server_name} with command: {command}")
        
        cmd_parts = shlex.split(command)
        if not cmd_parts:
            return "Error: Invalid command."
            
        server_env = os.environ.copy()
        if env:
            server_env.update(env)

        # podman 経由のコマンド起動をサポート (ホストの Podman へ接続)
        podman_socket = os.getenv("PODMAN_SOCKET")
        if cmd_parts[0] == "podman" and podman_socket:
            server_env["CONTAINER_HOST"] = podman_socket
            if "--remote" not in cmd_parts:
                # --remote と --identity を追加
                cmd_parts.insert(1, "--remote")
                cmd_parts.insert(2, "--identity")
                cmd_parts.insert(3, "/root/.ssh/id_rsa")
                print(f"MCPManager: Injected --remote flag, --identity and CONTAINER_HOST for podman.")

        server_params = StdioServerParameters(
            command=cmd_parts[0],
            args=cmd_parts[1:],
            env=server_env
        )

        try:
            from contextlib import AsyncExitStack
            stack = AsyncExitStack()
            
            # stdio でサーバーを起動
            read, write = await stack.enter_async_context(stdio_client(server_params))
            session = await stack.enter_async_context(ClientSession(read, write))
            
            # 初期化
            await session.initialize()
            
            self.active_sessions[server_name] = session
            self._exit_stacks.append(stack)

            # ツールの取得と登録
            tools_response = await session.list_tools()
            registered_tools = []
            
            for mcp_tool in tools_response.tools:
                wrapper = MCPToolWrapper(server_name, mcp_tool, session)
                tool_registry.register_tool(wrapper)
                registered_tools.append(wrapper.name)

            if save:
                self.saved_servers[server_name] = {
                    "command": command,
                    "env": env or {}
                }
                self._save_config()

            return f"Successfully connected to MCP Server '{server_name}'. Registered tools: {', '.join(registered_tools)}"

        except Exception as e:
            return f"Failed to connect to MCP Server '{server_name}': {e}"

# シングルトン
mcp_manager = MCPIntegrationManager()
