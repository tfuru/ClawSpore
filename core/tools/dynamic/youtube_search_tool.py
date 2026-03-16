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
            headers = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/110.0.0.0 Safari/537.36"}
            
            response = requests.get(search_url, headers=headers, timeout=10)
            if response.status_code != 200:
                print(f"DEBUG: YouTube returned status code {response.status_code}")
                return "[]"
            
            html = response.text
            json_text = re.search(r'ytInitialData\s*=\s*({.*?});', html)
            if not json_text:
                print("DEBUG: Could not parse YouTube search results.")
                return "[]"
            
            data = json.loads(json_text.group(1))
            videos = []
            
            try:
                contents = data['contents']['twoColumnSearchResultsRenderer']['primaryContents']['sectionListRenderer']['contents']
                for content in contents:
                    if 'itemSectionRenderer' in content:
                        items = content['itemSectionRenderer']['contents']
                        for item in items:
                            if 'videoRenderer' in item:
                                v = item['videoRenderer']
                                video_id = v.get('videoId')
                                title_data = v.get('title', {}).get('runs', [{}])[0]
                                title = title_data.get('text', 'Unknown')
                                if video_id:
                                    videos.append({
                                        "title": title,
                                        "url": f"https://www.youtube.com/watch?v={video_id}"
                                    })
            except Exception:
                pass
                
            if not videos:
                return "[]"
            
            # JSON形式で返すことでLLMのパース精度を向上させる
            return json.dumps(videos[:5], ensure_ascii=False, indent=2)
        except Exception as e:
            print(f"DEBUG: Error during youtube_search execution: {str(e)}")
            return "[]"
