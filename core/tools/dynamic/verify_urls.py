from core.tools.base import BaseTool
from core.utils import is_url_reachable
from typing import List, Dict, Any
import asyncio

class VerifyUrlsTool(BaseTool):
    """
    指定された URL のリストが実在するかどうかを確認し、True/False で結果を返すツール。
    """
    @property
    def name(self) -> str:
        return "verify_urls"

    @property
    def description(self) -> str:
        return "Check if the given URLs are reachable and return their status (True/False). Use this to prevent hallucination when providing links to the user."

    @property
    def parameters(self) -> Dict[str, Any]:
        return {
            "type": "object",
            "properties": {
                "urls": {
                    "type": "array",
                    "items": { "type": "string" },
                    "description": "List of URLs to verify."
                }
            },
            "required": ["urls"]
        }

    async def execute(self, urls: List[str], **kwargs) -> str:
        if not urls:
            return "No URLs provided."

        results = {}
        tasks = []
        
        # 重複を排除して並列実行
        unique_urls = list(dict.fromkeys(urls))
        
        for url in unique_urls:
            results[url] = False # 初期値
            tasks.append(self._check_url(url, results))
        
        await asyncio.gather(*tasks)
        
        # 結果のテキスト化
        output = []
        for url, status in results.items():
            status_str = "✅ Valid (Exists)" if status else "❌ Invalid (Dead or unreachable)"
            output.append(f"- {url}: {status_str}")
        
        result_text = "URL Verification Results:\n" + "\n".join(output)
            
        # Discord ログ送信 (kwargs からログ専用コールバックを取得)
        log_callback = kwargs.get("discord_log_callback")
        if log_callback:
            try:
                await log_callback(text=f"### [URL Verification Log]\n{result_text}")
            except Exception as e:
                print(f"DEBUG: Failed to send URL log to Discord: {e}")

        return result_text

    async def _check_url(self, url: str, results: dict):
        results[url] = await is_url_reachable(url)
