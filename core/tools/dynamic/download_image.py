from core.tools.base import BaseTool
import urllib.request
import os

class DownloadImageTool(BaseTool):
    @property
    def name(self) -> str:
        return "download_image"

    @property
    def description(self) -> str:
        return "指定されたURLから画像をダウンロードしてファイルとして保存します。"

    @property
    def parameters(self) -> dict:
        return {
            "type": "object",
            "properties": {
                "url": {
                    "type": "string",
                    "description": "ダウンロードする画像のURL"
                },
                "filename": {
                    "type": "string",
                    "description": "保存する際のファイル名（例: 'image.png'）"
                }
            },
            "required": ["url", "filename"]
        }

    async def execute(self, url: str, filename: str, **kwargs) -> str:
        import os
        session_id = kwargs.get("session_id")
        if session_id and not os.path.isabs(filename):
            workspace_dir = os.path.join(os.getcwd(), "workspaces", session_id)
            os.makedirs(workspace_dir, exist_ok=True)
            filename = os.path.join(workspace_dir, filename)

        try:
            # User-Agentを設定してアクセス制限を回避しやすくする
            req = urllib.request.Request(url, headers={'User-Agent': 'Mozilla/5.0'})
            with urllib.request.urlopen(req) as response:
                with open(filename, 'wb') as f:
                    f.write(response.read())
            return f"✅ 成功: 画像を '{os.path.basename(filename)}' としてワークスペースに保存しました。"
        except Exception as e:
            return f"❌ 失敗: {str(e)}"
