from core.tools.base import BaseTool
from typing import Any
import os

class PostFileToDiscordTool(BaseTool):
    @property
    def name(self) -> str:
        return "post_file_to_discord"

    @property
    def description(self) -> str:
        return "指定されたローカルファイルを Discord に投稿します。画像やドキュメントを共有するのに適しています。"

    @property
    def parameters(self) -> dict:
        return {
            "type": "object",
            "properties": {
                "file_path": {
                    "type": "string",
                    "description": "投稿するファイルのパス（例: character_design.png）"
                },
                "text": {
                    "type": "string",
                    "description": "投稿に添えるメッセージ（任意）"
                }
            },
            "required": ["file_path"]
        }

    async def execute(self, file_path: str, text: str = "", **kwargs) -> Any:
        import os
        session_id = kwargs.get("session_id")
        upload_path = file_path
        
        # セッションIDがある場合、ワークスペース内を優先的に探す
        if session_id and not os.path.isabs(file_path):
            # 1. ワークスペース内を探す
            workspace_path = os.path.join(os.getcwd(), "workspaces", session_id, file_path)
            if os.path.exists(workspace_path):
                upload_path = workspace_path
            # 2. ルートディレクトリも探す (フォールバック)
            elif os.path.exists(os.path.join(os.getcwd(), file_path)):
                upload_path = os.path.join(os.getcwd(), file_path)
        
        # discord_send_callback を kwargs から取得
        send_callback = kwargs.get("discord_send_callback")
        
        if not send_callback:
            return "Error: Discord への投稿機能（コールバック）が利用できません。"
            
        if not os.path.exists(upload_path):
            return f"Error: ファイル '{file_path}' が見つかりませんでした。(検索パス: {upload_path})"
            
        try:
            # コールバックを使用して Discord に送信
            await send_callback(text=text, file_path=upload_path)
            return f"✅ ファイル '{os.path.basename(upload_path)}' を Discord に投稿しました。"
        except Exception as e:
            import traceback
            error_details = traceback.format_exc()
            return f"❌ 投稿に失敗しました: {str(e)}\n\n詳細:\n{error_details}"
