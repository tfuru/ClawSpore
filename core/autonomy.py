import asyncio
import datetime
import os
import subprocess
from discord.ext import tasks

class AutonomyManager:
    """
    エージェントの自律思考（巡回、無視関監視など）を管理するクラス。
    特定のインターフェース（Discord等）に依存せず、コールバックを介して動作する。
    """
    def __init__(self, agent, send_callback, log_callback=None):
        self.agent = agent
        self.send_callback = send_callback # async def callback(text, channel_id, file_path=None)
        self.log_callback = log_callback   # async def callback(text)
        
        # 状態管理
        self.last_activity_time = datetime.datetime.now(datetime.timezone.utc)
        self.last_channel_id = None
        self.log_channel_id = None # ログ出力先チャンネルID
        
    def start(self):
        """バックグラウンドタスクの開始"""
        self.check_inactivity.start()
        self.autonomous_patrol.start()

    def update_activity(self, channel_id: int):
        """外部からのアクティビティ通知を受け取る"""
        self.last_activity_time = datetime.datetime.now(datetime.timezone.utc)
        self.last_channel_id = channel_id

    @tasks.loop(minutes=60)
    async def check_inactivity(self):
        """定期的に無反応時間をチェックし、必要に応じて話題を振る"""
        if not self.last_channel_id:
            return

        now = datetime.datetime.now(datetime.timezone.utc)
        elapsed = now - self.last_activity_time
        
        # しきい値（デフォルト12時間）
        threshold_hours = float(os.getenv('DISCORD_INACTIVITY_THRESHOLD_HOURS', '12'))
        threshold = datetime.timedelta(hours=threshold_hours)
        
        if elapsed > threshold:
            print(f"AutonomyManager: Inactivity detected ({elapsed.total_seconds() / 3600:.1f} hours). Generating topic...")
            try:
                session_id = str(self.last_channel_id)
                
                # トピック生成
                topic = await self.agent.generate_topic(session_id)
                await self.send_callback(f"💡 **ClawSpore Insights**\n{topic}", self.last_channel_id)
                
                # 連続投稿を防ぐため、時刻を現在に更新
                self.last_activity_time = now
            except Exception as e:
                print(f"AutonomyManager Error: in check_inactivity task: {e}")

    @check_inactivity.before_loop
    async def before_check_inactivity(self):
        # メインループ開始まで待機が必要な場合はここで調整（現状は即時）
        pass

    @tasks.loop(hours=24)
    async def autonomous_patrol(self):
        """定期的にワークスペースやシステム状態を巡回し、自律的に提案を行う"""
        if not self.last_channel_id:
            return

        print("AutonomyManager: Executing Autonomous Patrol...")
        try:
            if self.log_callback:
                await self.log_callback("🕵️ **Autonomous Patrol (定期監視) 実行中...**")

            session_id = f"patrol_{self.last_channel_id}"

            # 観察対象の情報収集 (安全なパスのみ)
            dirs_to_check = ["workspaces", "core/data", "core/tools/dynamic"]
            inspection_results = []
            
            for d in dirs_to_check:
                if os.path.exists(d):
                    try:
                        # ボットコンテナ内で直接実行
                        res = subprocess.check_output(["ls", "-F", d], text=True, stderr=subprocess.STDOUT)
                        inspection_results.append(f"### ls -F {d}\n{res}")
                    except Exception as e:
                        inspection_results.append(f"### ls -F {d}\nError: {e}")

            inspection_str = "\n\n".join(inspection_results)
            
            # 観察モード用のプロンプト
            observation_prompt = f"""[AUTONOMOUS OBSERVATION MODE]
You are performing a scheduled background check. Analyze the current environment and your long-term memory to find issues, missing tasks, or improvements.

### CURRENT ENVIRONMENT STATE (Target Directories):
{inspection_str}

### INSTRUCTIONS:
1. Review the directories for any clutter or missing components based on recent context.
2. If you find something worthwhile, provide a concise suggestion in Japanese.
3. Start response with "💡 **自律巡回レポート**".
4. If there's nothing important, reply ONLY with "NOTHING_TO_REPORT".
5. DO NOT execute any modification tools during this patrol turn.
"""

            suggestion = ""
            async def silent_send(text, file_path=None):
                nonlocal suggestion
                suggestion += str(text)

            # エージェントによる分析
            await self.agent.process_message(
                session_id, 
                observation_prompt, 
                silent_send, 
                user_id="autonomy_system"
            )

            if suggestion and "NOTHING_TO_REPORT" not in suggestion.upper():
                # ログチャンネルがあればそちらに、なければ最後のアクティブチャンネルに送信
                target_id = self.log_channel_id or self.last_channel_id
                if target_id:
                    await self.send_callback(suggestion, target_id)
                    print(f"AutonomyManager: Autonomous Patrol sent a suggestion to {target_id}.")
            else:
                print("AutonomyManager: Autonomous Patrol decided nothing to report.")

        except Exception as e:
            print(f"AutonomyManager Error: in autonomous_patrol task: {e}")

    @autonomous_patrol.before_loop
    async def before_autonomous_patrol(self):
        pass

    async def run_manual_patrol(self, channel_id):
        """手動で巡回を実行する"""
        self.update_activity(channel_id)
        await self.autonomous_patrol()
