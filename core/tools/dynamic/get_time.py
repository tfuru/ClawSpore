from core.tools.base import BaseTool
from typing import Any
import datetime

class GetTimeTool(BaseTool):
    @property
    def name(self) -> str:
        return "get_time"

    @property
    def description(self) -> str:
        return "現在のシステム時刻を取得します。"

    @property
    def parameters(self) -> dict:
        return {"type": "object", "properties": {}}

    async def execute(self, **kwargs) -> Any:
        return datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
