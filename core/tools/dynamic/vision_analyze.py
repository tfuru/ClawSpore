import requests
from core.tools.base import BaseTool
from typing import Any
import base64

class VisionAnalyzeTool(BaseTool):
    @property
    def name(self) -> str:
        return 'vision_analyze'

    @property
    def description(self) -> str:
        return '指定された画像URLの内容を解析し、詳細な説明を返します。'

    @property
    def parameters(self) -> dict:
        return {
            'type': 'object',
            'properties': {
                'image_url': {
                    'type': 'string',
                    'description': '解析する画像のURL'
                },
                'prompt': {
                    'type': 'string',
                    'description': '画像についての具体的な質問や指示（例：「何が写っていますか？」「文字を読み取ってください」）'
                }
            },
            'required': ['image_url']
        }

    async def execute(self, image_url: str, prompt: str = "この画像の内容を詳しく説明してください。", **kwargs) -> Any:
        try:
            # 画像のダウンロード
            response = requests.get(image_url, timeout=10)
            if response.status_code != 200:
                return f"Error: 画像の取得に失敗しました (Status: {response.status_code})"
            
            image_data = response.content
            mime_type = response.headers.get("Content-Type", "image/png")
            
            # 画像のリサイズ処理 (Pillowを使用)
            try:
                from PIL import Image
                import io
                
                img = Image.open(io.BytesIO(image_data))
                max_size = 2048
                if max(img.size) > max_size:
                    # アスペクト比を維持して縮小
                    img.thumbnail((max_size, max_size), Image.Resampling.LANCZOS)
                    output = io.BytesIO()
                    # MIMEタイプに合わせて保存 (不明な場合はPNG)
                    format_ext = mime_type.split('/')[-1].upper() if '/' in mime_type else 'PNG'
                    if format_ext not in ['JPEG', 'PNG', 'WEBP', 'GIF']:
                        format_ext = 'PNG'
                    
                    img.save(output, format=format_ext)
                    image_data = output.getvalue()
                    print(f"DEBUG: Image resized to {img.size}")
            except Exception as resize_e:
                print(f"DEBUG: Image resize failed (using original): {resize_e}")
            
            # llm_client への直接の再帰呼び出しを避けるため、
            # ツールとしての結果ではなく、特別な形式でデータを返すか、
            # ここでは解析結果そのものを取得するために llm.chat を使用する検討が必要
            # しかし、現在の構造ではツール実行中に llm.chat を呼ぶのは再帰的で複雑
            
            # 方針転換: このツールは「画像をLLMに渡すためのPartを生成する」のではなく、
            # 内部で Gemini API を直接叩いて「解析結果のテキスト」を返すようにする。
            
            from core.llm_client import llm
            if not llm.genai_client:
                return "Error: Gemini Client が初期化されていません。"
            
            from google.genai import types
            
            contents = [
                types.Content(
                    role="user",
                    parts=[
                        types.Part(text=prompt),
                        types.Part(inline_data=types.Blob(
                            mime_type=mime_type,
                            data=image_data
                        ))
                    ]
                )
            ]
            
            res = await llm.genai_client.aio.models.generate_content(
                model=llm.gemini_model_name,
                contents=contents
            )
            
            if res.candidates and res.candidates[0].content and res.candidates[0].content.parts:
                return res.candidates[0].content.parts[0].text
            
            return "画像を解析しましたが、結果が得られませんでした。"
            
        except Exception as e:
            return f"Error in vision_analyze: {str(e)}"
