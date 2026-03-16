import asyncio
from core.tools.dynamic.youtube_search_tool import YouTubeSearchTool

async def test():
    tool = YouTubeSearchTool()
    result = await tool.execute(query="cat videos")
    print(f"Result:\n{result}")

if __name__ == "__main__":
    asyncio.run(test())
