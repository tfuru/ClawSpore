from core.tools.base import BaseTool
from typing import Any
import json
import os

class GrantTool(BaseTool):
    @property
    def name(self) -> str:
        return "grant_tool"

    @property
    def description(self) -> str:
        return "指定したユーザーに特定のツールの実行権限を付与します。管理者のみが実行可能です。"

    @property
    def parameters(self) -> dict:
        return {
            "type": "object",
            "properties": {
                "target_user_id": {
                    "type": "string",
                    "description": "権限を付与する対象の Discord ユーザー ID"
                },
                "tool_name": {
                    "type": "string",
                    "description": "許可するツールの名前"
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
                acl["USERS"] = {}
            
            if target_user_id not in acl["USERS"]:
                acl["USERS"][target_user_id] = {"allowed_tools": [], "denied_tools": []}
            
            user_config = acl["USERS"][target_user_id]
            if "allowed_tools" not in user_config:
                user_config["allowed_tools"] = []
            
            if tool_name not in user_config["allowed_tools"]:
                user_config["allowed_tools"].append(tool_name)
                # 拒否リストに入っていたら削除
                if "denied_tools" in user_config and tool_name in user_config["denied_tools"]:
                    user_config["denied_tools"].remove(tool_name)
            
            with open(acl_path, "w", encoding="utf-8") as f:
                json.dump(acl, f, indent=2, ensure_ascii=False)
            
            return f"✅ ユーザー `{target_user_id}` にツール `{tool_name}` の実行権限を付与しました。"
        except Exception as e:
            return f"❌ 権限の付与中にエラーが発生しました: {str(e)}"
