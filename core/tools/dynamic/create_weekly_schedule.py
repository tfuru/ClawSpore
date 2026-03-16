from core.tools.base import BaseTool

class WeeklyScheduleTool(BaseTool):
    @property
    def name(self) -> str:
        return "create_weekly_schedule"

    @property
    def description(self) -> str:
        return "キーワードを指定して、月曜から日曜までの1週間のスケジュールを自動的に作成します。"

    @property
    def parameters(self):
        return {
            "keywords": "カンマやスペースで区切られた予定のキーワード"
        }

    async def execute(self, keywords: str, **kwargs) -> str:
        import re
        items = re.split(r'[,\s、\n]+', keywords)
        items = [i.strip() for i in items if i.strip()]
        
        if not items:
            return "キーワードが指定されていないため、スケジュールを作成できませんでした。"

        days = ["月曜日", "火曜日", "水曜日", "木曜日", "金曜日", "土曜日", "日曜日"]
        schedule = []
        for i, day in enumerate(days):
            task = items[i % len(items)]
            schedule.append(f"【{day}】: {task}")
            
        return "📅 生成された週間スケジュール:\n" + "\n".join(schedule)
