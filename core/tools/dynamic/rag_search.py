from core.tools.base import BaseTool
from core.memory import memory
from typing import Any

class RAGSearchTool(BaseTool):
    """
    過去の会話履歴や知識ベースから、現在のクエリに関連する情報を検索するツール。
    """
    @property
    def name(self) -> str:
        return "rag_search"

    @property
    def description(self) -> str:
        return "過去の会話履歴や記録された知識から、指定されたキーワードや内容に関連する情報を検索します。思い出せないことや過去の経緯を確認するのに役立ちます。"

    @property
    def parameters(self) -> dict:
        return {
            "type": "object",
            "properties": {
                "query": {
                    "type": "string",
                    "description": "検索したい内容や質問"
                },
                "n_results": {
                    "type": "integer",
                    "description": "取得する検索結果の数 (デフォルト5)",
                    "default": 5
                }
            },
            "required": ["query"]
        }

    async def execute(self, query: str, n_results: int = 5, **kwargs) -> Any:
        session_id = kwargs.get("session_id")
        if not session_id:
            return "Error: No session_id provided."
            
        try:
            context = memory.get_relevant_history(session_id, query, n_results=n_results)
            if not context:
                return "関連する情報は見つかりませんでした。"
            return context
        except Exception as e:
            return f"Error during RAG search: {e}"
