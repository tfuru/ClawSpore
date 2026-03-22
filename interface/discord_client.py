import discord
import os
import datetime
from discord.ext import tasks

class ClawSporeClient(discord.Client):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.log_channel_name = os.getenv('DISCORD_LOG_CHANNEL_NAME', 'log')
        self.log_channel = None
        self.processing_messages = set() # 重複処理防止用
        
        # 自律性管理マネージャーの初期化
        from core.agent import agent
        from core.autonomy import AutonomyManager
        self.autonomy_manager = AutonomyManager(
            agent=agent,
            send_callback=self._autonomy_send_callback,
            log_callback=self._autonomy_log_callback
        )
        
        # バックグラウンドタスクの開始
        self.autonomy_manager.start()

    async def on_ready(self):
        print(f'Logged on as {self.user}!')
        print(f'DEBUG: Bot is in {len(self.guilds)} guilds.')
        
        # ログ用チャンネルの準備
        await self._prepare_log_channel()
        
        if self.log_channel:
            await self.log_channel.send(f'🚀 **ClawSpore Core 起動完了**\nLogged on as `{self.user}`')
            print(f'Startup message sent to #{self.log_channel_name} (ID: {self.log_channel.id})')
        
        print('--- ClawSpore Discord Interface is Ready ---')

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
            print(f"DEBUG: Inactivity detected ({elapsed.total_seconds() / 3600:.1f} hours). Generating topic...")
            try:
                channel = self.get_channel(self.last_channel_id) or await self.fetch_channel(self.last_channel_id)
                if channel:
                    from core.agent import agent
                    session_id = str(channel.id)
                    
                    async with channel.typing():
                        topic = await agent.generate_topic(session_id)
                        await channel.send(f"💡 **ClawSpore Insights**\n{topic}")
                    
                    # 連続投稿を防ぐため、時刻を現在に更新
                    self.last_activity_time = now
                    print(f"DEBUG: Proactive topic sent to channel {channel.id}")
            except Exception as e:
                print(f"DEBUG: Error in check_inactivity task: {e}")

    async def _autonomy_send_callback(self, text, channel_id, file_path=None):
        """AutonomyManager からのメッセージ送信依頼を処理する"""
        try:
            channel = self.get_channel(channel_id) or await self.fetch_channel(channel_id)
            if channel:
                # Agent の汎用コールバックを流用できるか検討したが、
                # ここではシンプルに送信のみを行う
                if len(text) > 2000:
                    chunks = [text[i:i+1900] for i in range(0, len(text), 1900)]
                    for chunk in chunks:
                        await channel.send(chunk)
                else:
                    await channel.send(text)
        except Exception as e:
            print(f"DEBUG: Error in _autonomy_send_callback: {e}")

    async def _autonomy_log_callback(self, text):
        """AutonomyManager からのログ出力をログチャンネルに転送する"""
        if self.log_channel:
            try:
                await self.log_channel.send(f"🕵️ {text}")
            except Exception:
                pass

    async def _prepare_log_channel(self):
        """全てのサーバーでログチャンネルを確認し、どこにもなければ作成する"""
        target_name = self.log_channel_name.lower()
        print(f"Preparing log channel... (Target: #{self.log_channel_name})")
        
        if not self.guilds:
            print("Warning: Bot がどのサーバーにも参加していません。")
            return

        # 1. 全ギルドから既存のチャンネルを検索
        for guild in self.guilds:
            # fetch_channels() を使ってキャッシュではなく最新の情報を取得
            try:
                channels = await guild.fetch_channels()
                for channel in channels:
                    if isinstance(channel, discord.TextChannel) and channel.name.lower() == target_name:
                        self.log_channel = channel
                        print(f"Found existing log channel: #{channel.name} (ID: {channel.id}) in '{guild.name}'")
                        return
            except Exception as e:
                print(f"Error fetching channels for {guild.name}: {e}")

        # 2. 見つからなかった場合のみ作成を試行
        print(f"Log channel '#{self.log_channel_name}' が見つかりませんでした。新規作成を試行します...")
        for guild in self.guilds:
            try:
                self.log_channel = await guild.create_text_channel(self.log_channel_name)
                print(f"Successfully created new log channel: #{self.log_channel.name} in '{guild.name}'")
                return
            except discord.Forbidden:
                print(f"Forbidden: '{guild.name}' でのチャンネル作成権限がありません。")
            except Exception as e:
                print(f"Error: '{guild.name}' でのチャンネル作成中にエラーが発生しました: {e}")
        
        if not self.log_channel:
            print(f"Critical: ログチャンネル '#{self.log_channel_name}' を作成または見つけることができませんでした。")

    async def on_message(self, message):
        # 自分自身のメッセージには反応しない
        if message.author == self.user:
            return

        # アクティビティ情報の更新 (AutonomyManager へ通知)
        self.autonomy_manager.update_activity(message.channel.id)

        try:
            # 重複排除ガード: 既に処理中のメッセージIDなら無視
            if message.id in self.processing_messages:
                print(f"DEBUG: Skipping duplicate message ID: {message.id}")
                return
            self.processing_messages.add(message.id)

            print(f"DEBUG: Received message from {message.author} (ID: {message.author.id}): {message.content}")

            # ユーザー名（メンション）の除去と整形
            prompt = message.content.replace(f'<@!{self.user.id}>', '').replace(f'<@{self.user.id}>', '').strip()

            # 添付ファイルの処理 (画像URLなどをプロンプトに付与)
            attachments_info = ""
            if message.attachments:
                urls = [a.url for a in message.attachments]
                attachments_info = "\n(添付ファイルURL: " + ", ".join(urls) + ")"
            
            # 各種コマンド判定
            is_exec = message.content.startswith('!exec ')
            is_create_tool = message.content.startswith('!create_tool ')
            is_remove_tool = message.content.startswith('!remove_tool ')
            is_add_mcp = message.content.startswith('!add_mcp ')
            is_list_mcp = message.content.startswith('!list_mcp')
            is_list_tools = message.content.startswith('!list_tools')
            is_summarize = message.content.startswith('!summarize')
            is_clear = message.content.startswith('!clear')
            is_clear_all = message.content.startswith('!clear_all')
            is_check_memory = message.content.startswith('!check_memory')
            is_patrol = message.content.startswith('!patrol')
            is_help = message.content.startswith('!help')
            
            # MCP サーバー追加 (!add_mcp)
            if is_add_mcp:
                content = message.content[9:].strip()
                if not content:
                    await message.channel.send('実行する MCP サーバーの起動コマンドを入力してください。\n(例: !add_mcp npx -y @modelcontextprotocol/server-postgres\nPOSTGRES_URL=postgresql://...)')
                    return
                    
                lines = content.split('\n')
                command_str = lines[0].strip()
                
                env_vars = {}
                for line in lines[1:]:
                    line = line.strip()
                    if not line: continue
                    if '=' in line:
                        k, v = line.split('=', 1)
                        env_vars[k.strip()] = v.strip()
                    
                async with message.channel.typing():
                    try:
                        from core.mcp_integration import mcp_manager
                        # サーバー名をコマンドの最後の部分から簡易生成
                        parts = command_str.split()
                        server_name = parts[-1].replace('@', '').replace('/', '_').replace('-', '_')
                        if len(server_name) < 2:
                            server_name = f"mcp_server_{len(mcp_manager.active_sessions) + 1}"
                            
                        env_msg = f" (環境変数: {len(env_vars)}件)" if env_vars else ""
                        await message.channel.send(f"⏳ MCP サーバー `{server_name}` に接続中...{env_msg}")
                        
                        # 接続処理
                        result = await mcp_manager.connect_server(server_name, command_str, env=env_vars if env_vars else None)
                        await message.channel.send(f"```\n{result}\n```")
                    except Exception as e:
                        await message.channel.send(f"MCP サーバーの追加中にエラーが発生しました: {e}")
                return

            # MCP サーバー一覧 (!list_mcp)
            if is_list_mcp:
                from core.mcp_integration import mcp_manager
                from core.tools.registry import tool_registry
                
                sessions = mcp_manager.active_sessions
                if not sessions:
                    await message.channel.send("🔌 現在接続中の MCP サーバーはありません。")
                    return
                    
                msg = "**🔌 接続中の MCP サーバー一覧**\n"
                for server_name in sessions.keys():
                    # そのサーバーから提供されているツールを探す
                    server_tools = []
                    for tool in tool_registry._tools.values():
                        # MCPToolWrapper インスタンスがもつ _server_name 属性を判定
                        if getattr(tool, "_server_name", None) == server_name:
                            server_tools.append(tool._name) # 元のツール名
                    
                    tool_count = len(server_tools)
                    msg += f"- **Server: `{server_name}`** ({tool_count} tools)\n"
                    if server_tools:
                        msg += f"  - `{'`, `'.join(sorted(server_tools))}`\n"

                await message.channel.send(msg)
                return

            # ツール一覧 (!list_tools)
            if is_list_tools:
                from core.tools.registry import tool_registry
                all_tools = tool_registry._tools.keys()
                if not all_tools:
                    await message.channel.send("🛠 登録されているツールはありません。")
                    return
                
                msg = "**🛠 登録済みツール一覧**\n"
                for tool_name in sorted(all_tools):
                    msg += f"- `{tool_name}`\n"
                await message.channel.send(msg)
                return

            # ヘルプコマンド (!help)
            if is_help:
                help_msg = """**🛠️ ClawSpore 専用コマンド一覧**
- `!list_tools` : 登録されているすべてのツール（標準/動的/MCP）を表示します。
- `!list_mcp` : 現在接続中の MCP サーバーと提供ツールの一覧を表示します。
- `!add_mcp [コマンド]` : 新しい MCP サーバーを接続・登録します（改行後に環境変数指定可）。
- `!exec [コマンド]` : サンドボックス内で直接シェルコマンドを実行します。
- `!create_tool [ファイル名.py]` : 新しい Python ツールを作成・登録します（改行後にコードを記述）。
- `!remove_tool [ファイル名]` : 動的に追加したツールを削除します。
- `!summarize` : 現在の会話（短期記憶）を要約して長期記憶に保存します。
- `!check_memory [mode]` : 記憶を表示します（mode: short=履歴, long=サマリー, search=検索）。
- `!clear` : 現在のチャンネルの短期記憶のみをクリアします（長期記憶は維持）。
- `!clear_all` : 短期記憶と長期記憶の両方を完全にリセットします。
- `!patrol` : 自律監視（巡回）タスクを今すぐ手動で実行します。
- `!hello` : Bot の生存確認（挨拶）を行います。
- `!help` : このヘルプメニューを表示します。

※ 上記以外のメッセージはすべて AI への問いかけとして処理されます。"""
                await message.channel.send(help_msg)
                return

            # 手動巡回 (!patrol)
            if is_patrol:
                await message.channel.send("🕵️ **手動巡回を開始します...**")
                await self.autonomy_manager.run_manual_patrol(message.channel.id)
                return

            # ツール削除 (!remove_tool)
            if is_remove_tool:
                filename = message.content[13:].strip()
                if not filename:
                    await message.channel.send('削除するツールのファイル名を入力してください。 (例: !remove_tool get_server_time)')
                    return
                
                if filename.endswith('.py'):
                    filename = filename[:-3]
                
                async with message.channel.typing():
                    try:
                        import os
                        dynamic_dir = os.path.join('core', 'tools', 'dynamic')
                        file_path = os.path.join(dynamic_dir, f"{filename}.py")
                        
                        if not os.path.exists(file_path):
                            await message.channel.send(f'❌ ツールファイル `{filename}.py` が見つかりません。')
                            return
                        
                        # 物理削除
                        os.remove(file_path)
                        
                        # レジストリからの登録解除
                        from core.tools.registry import tool_registry
                        tool_registry.unregister_tool(filename)
                        # 他のクラスが混ざっている可能性を考慮してリロードも実行
                        tool_registry.load_dynamic_tools()
                        
                        await message.channel.send(f'✅ ツール `{filename}` を削除しました。')
                    except Exception as e:
                        await message.channel.send(f"ツールの削除中にエラーが発生しました: {e}")
                return

            # 短期記憶クリア (!clear)
            if is_clear and not is_clear_all:
                from core.memory import memory
                session_id = str(message.channel.id)
                memory.clear(session_id)
                await message.channel.send('🧹 このチャンネルの短期記憶（直近の履歴）をリセットしました。過去の要約（長期記憶）は維持されています。')
                return

            # 全記憶クリア (!clear_all)
            if is_clear_all:
                from core.memory import memory
                session_id = str(message.channel.id)
                memory.clear_all(session_id)
                await message.channel.send('💥 このチャンネルの短期記憶および長期記憶をすべて完全にリセットしました。')
                return

            # 記憶確認 (!check_memory)
            if is_check_memory:
                from core.tools.dynamic.check_memory import CheckMemoryTool
                content = message.content[13:].strip()
                parts = content.split()
                mode = parts[0] if parts else "short"
                query = " ".join(parts[1:]) if len(parts) > 1 else None
                
                async with message.channel.typing():
                    tool = CheckMemoryTool()
                    session_id = str(message.channel.id)
                    result = await tool.execute(mode=mode, query=query, session_id=session_id)
                    
                    # 2000文字制限の処理
                    if len(result) > 2000:
                        chunks = [result[i:i+1900] for i in range(0, len(result), 1900)]
                        for chunk in chunks:
                            await message.channel.send(f"```\n{chunk}\n```")
                    else:
                        await message.channel.send(f"```\n{result}\n```")
                return

            # 要約生成 (!summarize)
            if is_summarize:
                from core.memory import memory
                from core.summarizer import summarizer
                session_id = str(message.channel.id)
                
                messages = memory.get_messages(session_id)
                if not messages:
                    await message.channel.send('⚠️ 要約する履歴がありません。')
                    return

                async with message.channel.typing():
                    try:
                        await message.channel.send('⏳ 現在の会話を要約しています...')
                        summary = await summarizer.summarize(messages)
                        
                        # 長期記憶に保存
                        memory.add_long_term_summary(session_id, summary)
                        
                        await message.channel.send(f"✅ **長期記憶として保存しました**:\n\n{summary}")
                        await message.channel.send("💡 次回、履歴がリセットされた際や再起動後に、この要約が AI の記憶として読み込まれます。")
                    except Exception as e:
                        await message.channel.send(f"要約の生成中にエラーが発生しました: {e}")
                return

            # ツール新規作成 (!create_tool)
            if is_create_tool:
                content = message.content[13:].strip()
                # 形式: [filename] [code...]
                parts = content.split('\n', 1)
                if len(parts) < 2:
                    await message.channel.send('形式が正しくありません。`!create_tool [ファイル名.py]\n[コード]` の形式で送ってください。')
                    return
                
                filename = parts[0].strip()
                code = parts[1].strip()
                
                # コードブロック(```python...)の除去
                if code.startswith('```'):
                    lines = code.split('\n')
                    if lines[0].startswith('```'):
                        lines = lines[1:]
                    if lines[-1].strip() == '```':
                        lines = lines[:-1]
                    code = '\n'.join(lines)

                if not filename.endswith('.py'):
                    filename += '.py'
                
                async with message.channel.typing():
                    try:
                        # ファイルの保存
                        save_path = os.path.join('core', 'tools', 'dynamic', filename)
                        with open(save_path, 'w') as f:
                            f.write(code)
                        
                        # ホットリロードの実行
                        from core.tools.registry import tool_registry
                        tool_registry.load_dynamic_tools()
                        
                        await message.channel.send(f'✅ ツール `{filename}` を登録し、リロードしました。')
                    except Exception as e:
                        await message.channel.send(f"ツールの登録中にエラーが発生しました: {e}")
                return

            # ツール実行 (!exec)
            if is_exec:
                command_str = message.content[6:].strip()
                if not command_str:
                    await message.channel.send('実行するコマンドを入力してください。 (例: !exec ls)')
                    return
                
                async with message.channel.typing():
                    try:
                        from limbs.executor import executor
                        # コマンドをパース（簡易的な shlex 相当の分割）
                        import shlex
                        command = shlex.split(command_str)
                        
                        session_id = str(message.channel.id)
                        result = await executor.execute_tool(command, session_id=session_id)
                        
                        # 結果の送信 (2000文字制限考慮)
                        result_msg = f"```\n{result}\n```"
                        if len(result_msg) > 2000:
                            await message.channel.send("実行結果が長すぎるため、先頭部分のみ表示します。")
                            await message.channel.send(result_msg[:1990] + "\n```")
                        else:
                            await message.channel.send(result_msg)
                    except Exception as e:
                        await message.channel.send(f"実行中にエラーが発生しました: {e}")
                return

            # 簡単な挨拶への即時応答
            if prompt == 'こんにちは' or prompt == 'こんにちは！':
                await message.channel.send('こんにちは！何かお手伝いできることはありますか？')
                return

            # 簡単な疎通確認用
            if message.content == '!hello':
                await message.channel.send('こんにちは！クロウスポア・インターフェースです。')
                return

            # 他の特殊コマンドでない場合は、すべて通常のチャットとして AI に思考させる
            
            # !ask がついている場合は互換性のため取り除く
            if prompt.startswith("!ask "):
                prompt = prompt[5:].strip()
                
            if not prompt:
                return
                
            async with message.channel.typing():
                    try:
                        from core.agent import agent
                        
                        # 長文送信やツール経過送信のためのコールバック
                        async def send_callback(text, file_path=None):
                            import os
                            file = None
                            if file_path:
                                if os.path.exists(file_path):
                                    print(f"DEBUG: send_callback attaching file: {file_path}")
                                    file = discord.File(file_path)
                                else:
                                    print(f"DEBUG: send_callback file NOT FOUND: {file_path}")
                            
                            # text が None の場合は空文字列に変換
                            safe_text = str(text) if text is not None else ""
                            
                            # ファイルのみの送信
                            if not safe_text and file:
                                await message.channel.send(file=file)
                                return

                            # 2000文字制限の処理
                            if len(safe_text) > 2000:
                                chunks = [safe_text[i:i+2000] for i in range(0, len(safe_text), 2000)]
                                for i, chunk in enumerate(chunks):
                                    # 最初のチャンクにファイルを添付する
                                    if i == 0 and file:
                                        await message.channel.send(chunk, file=file)
                                    else:
                                        await message.channel.send(chunk)
                            else:
                                await message.channel.send(safe_text, file=file)

                        # セッションIDとしてチャンネルIDを利用（チャンネルごとのコンテキストを維持）
                        session_id = str(message.channel.id)

                        # ログチャンネル専用のコールバック
                        async def log_callback(text):
                            if self.log_channel:
                                try:
                                    if len(text) > 1900:
                                        text = text[:1900] + "\n...[TRUNCATED]"
                                    # 視認性向上のためにコードブロック化して送信
                                    await self.log_channel.send(f"```\n{text}\n```")
                                except Exception as e:
                                    print(f"Failed to send log to channel: {e}")
                        
                        async def ask_approval_callback(tool_name, args, message_prefix=""):
                            import json
                            prompt_msg = f"{message_prefix}⚠️ **承認待ち**\nツール `{tool_name}` が以下の引数で実行されようとしています。\n```json\n{json.dumps(args, indent=2, ensure_ascii=False)}\n```\n実行を許可しますか？ (👍 許可 / 👎 拒否)"
                            
                            # メッセージ分割処理
                            msg = None
                            if len(prompt_msg) > 2000:
                                chunks = [prompt_msg[i:i+1900] for i in range(0, len(prompt_msg), 1900)]
                                for i, chunk in enumerate(chunks):
                                    # 最後のチャンクのみリアクション用メッセージとして保持
                                    if i == len(chunks) - 1:
                                        msg = await message.channel.send(chunk)
                                    else:
                                        await message.channel.send(chunk)
                            else:
                                msg = await message.channel.send(prompt_msg)
                            
                            try:
                                await msg.add_reaction("👍")
                                await msg.add_reaction("👎")
                            except Exception as e:
                                print(f"Failed to add reactions: {e}")
                                
                            def check(reaction, user):
                                return user == message.author and str(reaction.emoji) in ["👍", "👎"] and reaction.message.id == msg.id

                            import asyncio
                            try:
                                reaction, user = await self.wait_for('reaction_add', timeout=60.0, check=check)
                                if str(reaction.emoji) == "👍":
                                    await message.channel.send("✅ 実行が許可されました。")
                                    return True
                                else:
                                    await message.channel.send("❌ 実行が拒否されました。")
                                    return False
                            except asyncio.TimeoutError:
                                await message.channel.send("⌛ タイムアウトにより実行がキャンセルされました。")
                                return False

                        try:
                            print(f"DEBUG: Processing message for session {session_id}...")
                            final_error = await agent.process_message(
                                session_id, 
                                prompt + attachments_info, 
                                send_callback, 
                                ask_approval_callback,
                                user_id=str(message.author.id),
                                log_callback=log_callback
                            )
                            if final_error:
                                await send_callback(final_error)
                        except Exception as inner_e:
                            print(f"DEBUG: Error inside agent.process_message: {inner_e}")
                            import traceback
                            traceback.print_exc()
                            await message.channel.send(f"AI処理中にエラーが発生しました(内部): {inner_e}")
                            
                    except Exception as e:
                        print(f"Error handling AI process: {e}")
                        import traceback
                        traceback.print_exc()
                        error_msg = f"AI処理中にエラーが発生しました: {e}"
                        await message.channel.send(error_msg[:2000])

        except Exception as e:
            print(f"Critical error in on_message: {e}")
            import traceback
            traceback.print_exc()
        finally:
            # 処理完了（成功・失敗問わず）後にIDを削除
            if message.id in self.processing_messages:
                self.processing_messages.remove(message.id)

async def start_discord_bot():
    token = os.getenv('DISCORD_TOKEN')
    if not token:
        print("Error: DISCORD_TOKEN is not set in environment variables.")
        return

    # インテントの設定
    intents = discord.Intents.default()
    intents.message_content = True
    intents.guilds = True # ギルド情報（チャンネル作成用）に必要

    client = ClawSporeClient(intents=intents)
    
    print(f"Starting Discord Bot (Log Channel: #{os.getenv('DISCORD_LOG_CHANNEL_NAME', 'log')})...")
    try:
        await client.start(token)
    except discord.errors.PrivilegedIntentsRequired:
        print("\n" + "!" * 50)
        print("CRITICAL ERROR: Privileged Intents are not enabled!")
        print("Discord Developer Portal で 'MESSAGE CONTENT INTENT' を有効にする必要があります。")
        print("詳細: https://discord.com/developers/applications/")
        print("!" * 50 + "\n")
    except Exception as e:
        print(f"An unexpected error occurred: {e}")
    finally:
        if not client.is_closed():
            await client.close()
            print("Discord client closed.")
