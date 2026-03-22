import os
import shutil
import time
from typing import Any, Dict
from core.tools.base import BaseTool

class WorkspaceVacuumTool(BaseTool):
    """workspaces/ 内の不要なファイルを削除し、リソースを整理するツール"""
    
    @property
    def name(self) -> str:
        return "workspace_vacuum"

    @property
    def description(self) -> str:
        return "workspaces/ 内の古い一時ファイルやセッションデータを削除してディスク容量を解放します。"

    @property
    def parameters(self) -> Dict[str, Any]:
        return {
            "type": "object",
            "properties": {
                "dry_run": {
                    "type": "boolean",
                    "description": "実際には削除せず、削除対象のリストのみを表示するかどうか",
                    "default": False
                },
                "older_than_days": {
                    "type": "integer",
                    "description": "指定した日数より古いファイルを削除（現在はデモ用のため無視され、全削除を試みます）",
                    "default": 0
                }
            }
        }

    @property
    def requires_approval(self) -> bool:
        return True

    @property
    def is_dangerous(self) -> bool:
        return True

    async def execute(self, dry_run: bool = False, older_than_days: int = 0, **kwargs) -> str:
        # 短期記憶セッションの保存先をターゲットにする
        target_dir = "core/data/sessions"
        if not os.path.exists(target_dir):
            return f"❌ ターゲットディレクトリ `{target_dir}` が存在しません。"

        try:
            items = os.listdir(target_dir)
            if not items:
                return f"ℹ️ `{target_dir}` はすでに空です。"

            if dry_run:
                return f"🔍 [Dry Run] 以下のアイテムが削除対象です: {', '.join(items)}"

            # 実際の削除処理
            count = 0
            for item in items:
                item_path = os.path.join(target_dir, item)
                try:
                    if os.path.isfile(item_path) or os.path.islink(item_path):
                        os.unlink(item_path)
                    elif os.path.isdir(item_path):
                        shutil.rmtree(item_path)
                    count += 1
                except Exception as e:
                    print(f"Failed to delete {item_path}: {e}")

            return f"✅ `{target_dir}` から {count} 個のアイテムを削除しました。クリーンアップ完了です。"
        except Exception as e:
            return f"❌ クリーンアップ中にエラーが発生しました: {str(e)}"

def register_vacuum_tools(registry):
    registry.register_tool(WorkspaceVacuumTool())
