from core.tools.base import BaseTool
from typing import Any
import json
import os

class RevokeTool(BaseTool):
    @property
    def name(self) -> str:
        return "revoke_tool"

    @property
    def description(self) -> str:
        return "指定したユーザーから特定のツールの実行権限を剥奪します。管理者のみが実行可能です。"

    @property
    def parameters(self) -> dict:
        return {
            "type": "object",
            "properties": {
                "target_user_id": {
                    "type": "string",
                    "description": "権限を剥奪する対象の Discord ユーザー ID"
                },
                "tool_name": {
                    "type": "string",
                    "description": "剥奪するツールの名前"
                }
            },
            "required": ["target_user_id", "tool_name"]
        }

    async def execute(self, target_user_id: str, tool_name: str, **kwargs) -> Any:
        acl_path = "core/data/acl.json"
        if not os.path.exists(acl_path):
            return "Error: ACL設定ファイルが見つかりません。"

        try:
            with open(acl_path, "r", encoding="utf-8") as f:
                acl = json.load(f)

            if "USERS" not in acl:
                return f"ℹ️ ユーザー `{target_user_id}` の設定が存在しません。"
            
            if target_user_id not in acl["USERS"]:
                return f"ℹ️ ユーザー `{target_user_id}` の個別権限設定はありません。"
            
            user_config = acl["USERS"][target_user_id]
            
            # 許可リストから削除
            removed = False
            if "allowed_tools" in user_config and tool_name in user_config["allowed_tools"]:
                user_config["allowed_tools"].remove(tool_name)
                removed = True
            
            # 明示的な拒否リストに追加
            if "denied_tools" not in user_config:
                user_config["denied_tools"] = []
            if tool_name not in user_config["denied_tools"]:
                user_config["denied_tools"].append(tool_name)
                removed = True
            
            if removed:
                with open(acl_path, "w", encoding="utf-8") as f:
                    json.dump(acl, f, indent=2, ensure_ascii=False)
                return f"✅ ユーザー `{target_user_id}` からツール `{tool_name}` の実行権限を剥奪しました。"
            else:
                return f"ℹ️ ユーザー `{target_user_id}` は既に `{tool_name}` の権限を持っていません。"
        except Exception as e:
            return f"❌ 権限の剥奪中にエラーが発生しました: {str(e)}"
