import base64
from core.tools.base import BaseTool

class SaveImageTool(BaseTool):
    @property
    def name(self) -> str:
        return "save_image"

    @property
    def description(self) -> str:
        return "Base64エンコードされた画像データを受け取り、指定したファイル名で保存します。"

    @property
    def parameters(self) -> dict:
        return {
            "type": "object",
            "properties": {
                "filename": {
                    "type": "string",
                    "description": "保存するファイル名（例: 'sample.png'）"
                },
                "base64_data": {
                    "type": "string",
                    "description": "画像のBase64エンコード文字列"
                }
            },
            "required": ["filename", "base64_data"]
        }

    async def execute(self, filename: str, base64_data: str, **kwargs) -> str:
        session_id = kwargs.get("session_id")
        if session_id and not os.path.isabs(filename):
            import os
            workspace_dir = os.path.join(os.getcwd(), "workspaces", session_id)
            os.makedirs(workspace_dir, exist_ok=True)
            filename = os.path.join(workspace_dir, filename)

        try:
            # data:image/png;base64,... のようなヘッダーがあれば除去
            if "," in base64_data:
                base64_data = base64_data.split(",")[1]
            
            img_data = base64.b64decode(base64_data)
            with open(filename, "wb") as f:
                f.write(img_data)
            return f"✅ 画像を '{os.path.basename(filename)}' としてワークスペースに保存しました。"
        except Exception as e:
            return f"❌ 画像の保存に失敗しました: {str(e)}"
