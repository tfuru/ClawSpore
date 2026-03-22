from core.tools.base import BaseTool
from typing import Any
import requests
import re
import json
import urllib.parse

class YouTubeSearchTool(BaseTool):
    @property
    def name(self) -> str:
        return 'youtube_search'

    @property
    def description(self) -> str:
        return 'YouTubeで動画を検索し、タイトルとURLのリストを返します。'

    @property
    def parameters(self) -> dict:
        return {
            'type': 'object',
            'properties': {
                'query': {
                    'type': 'string',
                    'description': '検索するキーワード'
                }
            },
            'required': ['query']
        }

    async def execute(self, query: str, **kwargs) -> Any:
        try:
            search_url = f"https://www.youtube.com/results?search_query={urllib.parse.quote(query)}"
            headers = {
                "User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/122.0.0.0 Safari/537.36",
                "Accept-Language": "ja,en-US;q=0.9,en;q=0.8"
            }
            
            response = requests.get(search_url, headers=headers, timeout=10)
            if response.status_code != 200:
                return f"Error: YouTube returned status code {response.status_code}"
            
            html = response.text
            # 複数のパターンの正規表現で ytInitialData を探す
            patterns = [
                r'ytInitialData\s*=\s*({.*?});',
                r'window\["ytInitialData"\]\s*=\s*({.*?});',
                r'var\s+ytInitialData\s*=\s*({.*?});'
            ]
            
            json_text = None
            for p in patterns:
                match = re.search(p, html)
                if match:
                    json_text = match.group(1)
                    break
            
            if not json_text:
                return "Error: YouTube の検索結果を解析できませんでした（データ構造が変更された可能性があります）。"
            
            data = json.loads(json_text)
            videos = []
            
            try:
                # 複雑な YouTube のデータ構造を探索
                contents_base = data.get('contents', {}).get('twoColumnSearchResultsRenderer', {}).get('primaryContents', {}).get('sectionListRenderer', {}).get('contents', [])
                
                for section in contents_base:
                    if 'itemSectionRenderer' in section:
                        items = section['itemSectionRenderer'].get('contents', [])
                        for item in items:
                            if 'videoRenderer' in item:
                                v = item['videoRenderer']
                                video_id = v.get('videoId')
                                # タイトルの取得
                                title = "Unknown Title"
                                if 'title' in v:
                                    if 'runs' in v['title']:
                                        title = v['title']['runs'][0].get('text', title)
                                    elif 'simpleText' in v['title']:
                                        title = v['title']['simpleText']
                                
                                # 動画チャンネル情報など必要に応じて追加可能
                                if video_id:
                                    videos.append({
                                        "title": title,
                                        "url": f"https://www.youtube.com/watch?v={video_id}"
                                    })
            except Exception as parse_e:
                print(f"DEBUG: YouTube parse error details: {parse_e}")
                # 一部でも取得できていれば続行、全滅ならエラーを返す
                if not videos:
                    return f"Error during parsing YouTube data: {parse_e}"
                
            if not videos:
                return "[]" # 見つからなかった場合
            
            # ツール内での報告はエージェント側の応答と重複するため廃止
            # 必要な整理（上位5件に制限）をしてJSONで返す
            return json.dumps(videos[:5], ensure_ascii=False, indent=2)
            
        except Exception as e:
            import traceback
            error_trace = traceback.format_exc()
            print(f"DEBUG: YouTube search fatal error: {error_trace}")
            return f"Error: YouTube 検索中に致命的なエラーが発生しました: {str(e)}"
