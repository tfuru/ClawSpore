from core.tools.base import BaseTool
from typing import Any
import requests
from bs4 import BeautifulSoup

class GetWebsiteInfoTool(BaseTool):
    @property
    def name(self) -> str:
        return 'get_website_info'

    @property
    def description(self) -> str:
        return '指定されたURLのウェブページからタイトルと本文を取得します。'

    @property
    def parameters(self) -> dict:
        return {
            'type': 'object',
            'properties': {
                'url': {'type': 'string', 'description': '取得対象のウェブサイトのURL'}
            },
            'required': ['url']
        }

    async def execute(self, url: str, **kwargs) -> Any:
        try:
            response = requests.get(url, timeout=10)
            if response.status_code != 200:
                return f"Error: ページにアクセスできませんでした。HTTP ステータスコード: {response.status_code}"
            
            response.raise_for_status()
            soup = BeautifulSoup(response.text, 'html.parser')
            
            title = soup.title.string if soup.title else 'No Title'
            # 本文の抽出（簡易的にpタグのテキストを結合）
            paragraphs = [p.get_text() for p in soup.find_all('p')]
            content = '\n'.join(paragraphs)[:1000] # 長すぎる場合は制限
            
            return {
                'title': title,
                'content': content
            }
        except requests.exceptions.Timeout:
            return "Error: タイムアウトが発生しました。サーバーからの応答がありません。"
        except requests.exceptions.ConnectionError:
            return "Error: 接続エラーが発生しました。URLが正しいか、またはサイトがダウンしていないか確認してください。"
        except Exception as e:
            return f'Error: 予期せぬエラーが発生しました: {e}'
