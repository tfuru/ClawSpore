import os
import json
import asyncio
import httpx
from typing import Any, Dict
from core.tools.base import BaseTool

class SystemInspectorTool(BaseTool):
    """ClawSpore の稼働環境を自己診断するツール"""
    
    @property
    def name(self) -> str:
        return "system_inspector"

    @property
    def description(self) -> str:
        return "ClawSpore の健康状態を診断します。環境変数、接続、設定ファイル、リソース使用量をチェックして詳細なレポートを生成します。"

    @property
    def parameters(self) -> Dict[str, Any]:
        return {
            "type": "object",
            "properties": {
                "verbose": {
                    "type": "boolean",
                    "description": "詳細な情報を出力するかどうか",
                    "default": False
                }
            }
        }

    async def execute(self, verbose: bool = False, **kwargs) -> str:
        report = ["=== ClawSpore 自己診断レポート ==="]
        
        # 1. 環境変数のチェック
        report.append("\n[1] 環境変数の確認:")
        critical_envs = ["DISCORD_TOKEN", "LM_STUDIO_URL", "ADMIN_DISCORD_USER_ID"]
        for env in critical_envs:
            val = os.getenv(env)
            status = "✅ 設定済み" if val else "❌ 未設定"
            # セキュリティのため値はマスク
            report.append(f"  - {env}: {status}")

        # 2. LM Studio 接続テスト
        report.append("\n[2] 外部サービス接続:")
        lm_url = os.getenv("LM_STUDIO_URL", "http://localhost:1234")
        try:
            async with httpx.AsyncClient(timeout=3.0) as client:
                res = await client.get(f"{lm_url.rstrip('/')}/v1/models")
                if res.status_code == 200:
                    report.append(f"  - LM Studio: ✅ 接続成功 ({lm_url})")
                else:
                    report.append(f"  - LM Studio: ⚠️ 応答異常 (HTTP {res.status_code})")
        except Exception as e:
            report.append(f"  - LM Studio: ❌ 接続失敗 ({str(e)})")

        # 3. Podman / Docker ソケットの確認
        report.append("\n[3] 実行環境 (Podman):")
        socket_path = os.getenv("DOCKER_HOST", "/run/user/1000/podman/podman.sock")
        if socket_path.startswith("unix://"):
            actual_path = socket_path[7:]
            if os.path.exists(actual_path):
                report.append(f"  - ソケット: ✅ 存在します ({actual_path})")
            else:
                report.append(f"  - ソケット: ⚠️ 行方不明 ({actual_path})")
        else:
            report.append(f"  - Docker Host: {socket_path}")

        # 4. ディスクおよびワークスペースの確認
        report.append("\n[4] リソース使用量:")
        workspace_dir = "workspaces"
        if os.path.exists(workspace_dir):
            try:
                # 簡易的なサイズ計算 (深さ1まで)
                total_size = 0
                count = 0
                for root, dirs, files in os.walk(workspace_dir):
                    count += len(files)
                    for f in files:
                        total_size += os.path.getsize(os.path.join(root, f))
                report.append(f"  - {workspace_dir}/: {count} ファイル, {total_size / 1024:.1f} KB")
            except Exception as e:
                report.append(f"  - {workspace_dir}/: ⚠️ 読み取りエラー ({str(e)})")
        else:
            report.append(f"  - {workspace_dir}/: ❌ フォルダが見つかりません")

        # 5. 設定ファイル (ACL) の確認
        report.append("\n[5] 設定ファイル整合性:")
        acl_path = "core/data/acl.json"
        if os.path.exists(acl_path):
            try:
                with open(acl_path, "r", encoding="utf-8") as f:
                    json.load(f)
                report.append(f"  - {acl_path}: ✅ 正常 (JSON 構文正常)")
            except Exception as e:
                report.append(f"  - {acl_path}: ❌ JSON 構文エラー ({str(e)})")
        else:
            report.append(f"  - {acl_path}: ⚠️ ファイルが存在しません (デフォルト拒否が適用されます)")

        report.append("\n=== 診断完了 ===")
        return "\n".join(report)

def register_system_tools(registry):
    registry.register_tool(SystemInspectorTool())
