from core.tools.base import BaseTool

class WikipediaSearch(BaseTool):
    @property
    def name(self) -> str:
        return "wikipedia_search"

    @property
    def description(self) -> str:
        return 'Wikipediaから情報を検索するツール'

    @property
    def parameters(self) -> dict:
        return {
        'query': {'type': 'string', 'description': '検索するキーワード'} 
    }

    async def execute(self, query: str, **kwargs) -> str:
        try:
            import wikipedia
            wikipedia.set_lang('ja') # 日本語で検索するように設定
            result = wikipedia.summary(query, sentences=2)
            return result
        except Exception as e:
            return f'エラーが発生しました: {e}'