from core.tools.base import BaseTool
from typing import Any
import urllib.request

class SaveAttachmentTool(BaseTool):
    @property
    def name(self) -> str:
        return 'save_attachment'

    @property
    def description(self) -> str:
        return '指定されたURLからファイルをダウンロードし、セッション専用のワークスペースに保存します。Discordの添付画像などを保存するのに適しています。'

    @property
    def parameters(self) -> dict:
        return {
            "type": "object",
            "properties": {
                "url": {
                    "type": "string",
                    "description": "ダウンロードするファイルのURL"
                },
                "filename": {
                    "type": "string",
                    "description": "保存するファイル名（例: 'image.png'）"
                }
            },
            "required": ["url", "filename"]
        }

    async def execute(self, url: str, filename: str, **kwargs) -> Any:
        import os
        session_id = kwargs.get('session_id')
        
        # パスの解決: 相対パスの場合はワークスペース内に保存
        if session_id and not os.path.isabs(filename):
            workspace_dir = os.path.join(os.getcwd(), "workspaces", session_id)
            os.makedirs(workspace_dir, exist_ok=True)
            filename = os.path.join(workspace_dir, filename)

        try:
            print(f"DEBUG: [save_attachment] Starting download from {url}")
            # User-Agentを設定してアクセス制限を回避しやすくする
            req = urllib.request.Request(url, headers={'User-Agent': 'Mozilla/5.0'})
            with urllib.request.urlopen(req) as response:
                print(f"DEBUG: [save_attachment] Writing to {filename}")
                with open(filename, 'wb') as f:
                    f.write(response.read())
            
            print(f"DEBUG: [save_attachment] Successfully saved as {filename}")
            return f"✅ 成功: ファイルを '{os.path.basename(filename)}' としてワークスペースに保存しました。"
        except Exception as e:
            return f"❌ 失敗: ダウンロードまたは保存中にエラーが発生しました: {str(e)}"
