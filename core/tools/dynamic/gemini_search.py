from core.tools.base import BaseTool
from typing import Any

class GeminiSearchTool(BaseTool):
    @property
    def name(self) -> str:
        return 'gemini_search'

    @property
    def description(self) -> str:
        return 'Google 検索を使用して、最新のニュース、イベント、事実、詳細な情報をウェブから検索します。特定のURLではなく、一般的な知識や最新情報を探すのに適しています。'

    @property
    def parameters(self) -> dict:
        return {
            'type': 'object',
            'properties': {
                'queries': {
                    'type': 'array',
                    'items': {'type': 'string'},
                    'description': '検索したいクエリのリスト'
                }
            },
            'required': ['queries']
        }

    async def execute(self, queries: list, **kwargs) -> Any:
        # このツールは LLMClient 側で Google Search グラウンディングを有効化するためのトリガーです。
        # Gemini が実際に検索を実行した場合、結果は Gemini SDK によって直接回答に組み込まれます。
        # もし Gemini が検索を実行せずにこの関数を呼び出した場合のフォールバックとしてメッセージを返します。
        return f"Gemini の Google Search 機能がリクエストされました（クエリ: {queries}）。結果は Gemini の回答に直接反映されます。"
