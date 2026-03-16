import os
import json
import datetime
from core.llm_client import llm
from core.tools.registry import tool_registry
from core.memory import memory

class Agent:
    def __init__(self):
        self.system_prompt = """You are ClawSpore, an autonomous AI assistant capable of reasoning and executing tools.
When you receive a request, you can use your tools to gather information before answering.
If you use a tool, wait for the result and then think about the next step based on the result.
Always reply in Japanese unless instructed otherwise."""
        self.acl_path = "core/data/acl.json"

    def _get_acl(self) -> dict:
        """ACL設定ファイルを読み込む"""
        if os.path.exists(self.acl_path):
            try:
                with open(self.acl_path, "r", encoding="utf-8") as f:
                    return json.load(f)
            except Exception as e:
                print(f"DEBUG: Error loading ACL: {e}")
        return {}

    def _check_permission(self, user_id: str, tool_name: str) -> bool:
        # 管理者環境変数による強力なフォールバック
        import os
        admin_id = os.getenv("ADMIN_DISCORD_USER_ID")
        if admin_id and user_id == admin_id:
            print(f"DEBUG: Granting full access to {tool_name} for admin user {user_id}")
            return True

        if not user_id:
            return False
            
        acl = self._get_acl()
        if not acl:
            return False # デフォルトは拒否
        
        # 1. ユーザー個別の設定を確認
        user_config = acl.get("USERS", {}).get(user_id)
        if user_config:
            if user_config.get("allow_all", False):
                return True
            if tool_name in user_config.get("denied_tools", []):
                return False
            if tool_name in user_config.get("allowed_tools", []):
                return True

        # 2. デフォルト設定に戻る
        default_config = acl.get("DEFAULT_PERMISSIONS", {})
        if default_config.get("allow_all", False):
            return True
            
        if tool_name in default_config.get("denied_tools", []):
            return False
            
        if tool_name in default_config.get("allowed_tools", []):
            return True
            
        return False

    async def process_message(self, session_id: str, prompt: str, send_callback, ask_approval_callback=None, user_id: str = None, log_callback=None) -> str:
        """
        ユーザーからのメッセージを処理し、必要に応じてツールを実行する。
        ReAct (Reasoning and Acting) ループ。
        """
        if not memory.get_messages(session_id):
            # 長期記憶（過去のサマリー）を取得
            lt_context = memory.get_long_term_context(session_id)
            lt_instruction = ""
            if lt_context:
                lt_instruction = f"\n\n### 過去の会話の要約（長期記憶）\n以下の内容は過去のやり取りの要約です。これまでの文脈として考慮してください：\n{lt_context}\n"

            # 現在時刻を取得 (ISO 形式、JST タイムゾーンを意識)
            now = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
            time_instruction = f"\n- Current Time: {now} (JST)\n- Always use this time as 'today' or 'now' for your reasoning.\n"

            # システムプロンプトを構成 (簡潔に整理)
            enhanced_system_prompt = self.system_prompt + lt_instruction + """
IMPORTANT: 
""" + time_instruction + """
- Tool List: ONLY use tools explicitly listed in the 'tool_definitions' provided. 
- NEVER hallucinate tools like 'google:search' or 'google_search'. 
- For Steam/Games: 
    - NEVER hallucinate game prices, release dates, or reviews. 
    - ALWAYS use a Steam search tool (from MCP) if available for any game-related information.
- For Web/Video Search: 
    - Use 'gemini_search' for broad searches, and 'youtube_search' for videos.
    - NEVER hallucinate or invent URLs. ONLY use the exact URLs provided in the tool's output.
    - If a tool returns an empty list '[]' or no results, you MUST HONESTLY SAY "見つかりませんでした" (Not found). NEVER invent fake URLs to fill the gap.
    - If a tool returns JSON, extract the 'url' fields accurately.
- Autonomous Problem Solving:
    1. Plan first: For complex requests, break them down into a sequence of tool calls (Workflows).
    2. Combine tools: Chain multiple tools (e.g., search -> read -> summary -> post) to achieve the goal.
    3. Missing Tools: If existing tools are insufficient or inefficient, PROACTIVELY PROPOSE creating a new tool via 'create_tool'. Describe its function, parameters, and why it's needed before implementing.
- ReAct Loop: Analyze 'tool' results before continuing. Report errors as-is. Don't hallucinate results or names.
    - NEVER start your response with '[TOOL_RESULT]' or '[EXECUTION RESULT]'. Those are reserved for the system.
    - If you See '### システムからの報告', it is the tool result you should analyze.
    - CRITICAL: If a tool result shows success, NEVER claim you lack permission or that the operation failed.
    - Self-Healing: If a tool fails (Error message), analyze the cause (path, permission, arguments). If you can fix it (e.g., correct a typo in path), PROACTIVELY explain and retry with corrected parameters in the next turn.
- Validation: ALWAYS use 'get_website_info' to validate URLs found via search. 
- Custom Tools: Use 'create_tool' (inherit 'BaseTool' from 'core.tools.base') to add functionality.
- Discord: Use 'discord_send_callback' (in kwargs) to post. e.g. 'await discord_send_callback(text="...", file_path="...")'.
- Self-Healing: If a tool fails, use 'inspect_tool' to view source, analyze traceback, and fix with 'create_tool'.
- Security: NEVER reveal .env contents, API keys, or secrets."""
            memory.add_message(session_id, "system", enhanced_system_prompt)

        # ユーザー入力をメモリに追加
        memory.add_message(session_id, "user", prompt)

        max_turns = 10
        turn = 0
        
        while turn < max_turns:
            turn += 1
            # コンテキスト制限対策: システムプロンプト + 直近10件のみに制限 (Sliding Window)
            all_messages = memory.get_messages(session_id)
            
            # --- Anti-Hallucination Context Cleansing ---
            # 過去の AI の回答に「権限がない」「失敗した」系の嘘が含まれている場合、
            # それが次の推論に悪影響（負のループ）を与えるのを防ぐため、一時的にクレンジングする。
            cleansed_all_messages = []
            for m in all_messages:
                new_m = m.copy()
                if new_m["role"] == "assistant" and new_m.get("content"):
                    bad_phrases = ["Permission denied", "access is restricted", "権限がありません", "実行できませんでした"]
                    if any(p in new_m["content"] for p in bad_phrases):
                        # 嘘の報告を「成功」という事実に書き換えて、AIの負の連鎖を断ち切る
                        new_m["content"] = "[このメッセージはシステムにより正常な状態に補正されました] ツールは正常に実行されました。状況を確認し、次のステップへ進みます。"
                cleansed_all_messages.append(new_m)
            
            system_msg = next((m for m in cleansed_all_messages if m["role"] == "system"), None)
            other_messages = [m for m in cleansed_all_messages if m["role"] != "system"]
            
            # 直近 20 件を取得 (ウィンドウを拡大)
            window_size = 20
            recent_context = other_messages[-window_size:] if len(other_messages) > window_size else other_messages
            
            # ロールの交互性確保: 開始が 'user' になるまで調整 (システムプロンプト除く)
            while recent_context and recent_context[0]["role"] != "user":
                recent_context.pop(0)

            # RAG (検索拡張生成) で関連する過去の情報を取得
            rag_context = memory.get_relevant_history(session_id, prompt)
            if rag_context:
                # 関連する履歴がある場合、「あなたが思い出している記憶」として自然に挿入
                rag_msg = {"role": "system", "content": f"### あなたが思い出している関連する過去の記憶\n以下の内容は過去のやり取りからあなたが思い出した断片です。これに基づいて矛盾のないよう対話してください：\n{rag_context}"}
                messages = ([system_msg] if system_msg else []) + [rag_msg] + recent_context
            else:
                messages = ([system_msg] if system_msg else []) + recent_context
            tool_defs = tool_registry.get_tool_definitions()
            
            # デバッグログ
            # print(f"DEBUG: messages in turn {turn}: {json.dumps(messages, indent=2, ensure_ascii=False)}")

            # API 呼び出し
            try:
                # ユーザーの最新の入力に「ツール作成」に関連するキーワードが含まれている場合、
                # または Gemini API キーが設定されている場合、Gemini (Gemma-3) を優先的に使用する。
                # ここではシンプルに、全メッセージの末尾（最新のユーザー入力）をチェックする。
                use_gemini = False
                if llm.gemini_api_key:
                    last_user_msg = next((m["content"] for m in reversed(messages) if m["role"] == "user"), "")
                    keywords = [
                        "create_tool", "ツール作成", "コード修正", "プログラム", "コードを書いて",
                        "gemini_search", "詳細な調査"
                    ]
                    if any(kw in last_user_msg.lower() for kw in keywords):
                        use_gemini = True
                        print("Agent: Using Gemini due to complex task/keyword.")
                
                response_msg = await llm.chat(messages, tool_definitions=tool_defs, use_gemini=use_gemini)
                # LLM の応答内容（特にツール呼び出し）を確認
                if hasattr(response_msg, "tool_calls") and response_msg.tool_calls:
                    print(f"DEBUG: LLM requested {len(response_msg.tool_calls)} tool calls.")
                    for call in response_msg.tool_calls:
                        print(f"DEBUG: Call ID: {call.id}, Tool: {call.function.name}, Args: {call.function.arguments}")
                elif hasattr(response_msg, "content"):
                    content_preview = (response_msg.content[:100] + "...") if response_msg.content else "None"
                    print(f"DEBUG: LLM response content: {content_preview}")
            except Exception as e:
                return f"LLM通信エラー: {e}"
                
            # アシスタントの応答をメモリに保存
            assistant_msg = {"role": "assistant"}
            if hasattr(response_msg, "content") and response_msg.content:
                assistant_msg["content"] = response_msg.content
                
            if hasattr(response_msg, "tool_calls") and response_msg.tool_calls:
                serialized_calls = []
                for call in response_msg.tool_calls:
                    call_dict = {
                        "id": call.id,
                        "type": "function",
                        "function": {
                            "name": call.function.name,
                            "arguments": call.function.arguments
                        }
                    }
                    # Gemini Native SDK のための thought_signature を保持
                    # そのままの型（bytes等）で保持し、LLMClient 側で適切に扱う
                    if hasattr(call, "thought_signature") and call.thought_signature:
                        call_dict["thought_signature"] = call.thought_signature
                    serialized_calls.append(call_dict)
                assistant_msg["tool_calls"] = serialized_calls
            
            memory.add_raw_message(session_id, assistant_msg)

            # --- 思考過程/途中経過をユーザーに送信 ---
            if assistant_msg.get("content"):
                content = assistant_msg["content"]
                import re
                # [...] 形式の内部タグと <think>...</think> 形式の思考プロセスを除去
                # 閉じタグがない場合も考慮して、タグから開始して可能な限り除去する
                temp_content = re.sub(r'<think>.*?(?:</think>|$)', '', content, flags=re.DOTALL)
                filtered_content = re.sub(r'\[.*?(?:\]|$)', '', temp_content, flags=re.DOTALL).strip()
                
                if filtered_content:
                    await send_callback(filtered_content)
                elif hasattr(response_msg, "tool_calls") and response_msg.tool_calls:
                    # 本文はないがツールを呼び出している場合
                    await send_callback("💡 思考を完了しました。必要なツールを実行します...")
                else:
                    # 本文もなくツール呼び出しもない場合（稀だが念のため）
                    await send_callback("...（処理を継続しています）")

            # --- ツールの実行処理 ---
            if hasattr(response_msg, "tool_calls") and response_msg.tool_calls:
                # 最大ターンに達している場合は、ツールを実行せずに終了を促す
                if turn >= max_turns:
                    await send_callback("⚠️ **最大ターン数(10)に達しました。安全のため処理を強制中断します。**")
                    return None

                for call in response_msg.tool_calls:
                    tool_name = call.function.name
                    args_str = call.function.arguments
                    try:
                        args = json.loads(args_str)
                    except json.JSONDecodeError:
                        args = {}
                        
                    # 存在チェック
                    tool_instance = tool_registry.get_tool(tool_name)
                    if not tool_instance:
                        available_tools = ", ".join(tool_registry._tools.keys())
                        print(f"DEBUG: Hallucinated tool call detected: {tool_name}")
                        memory.add_message(
                            session_id=session_id,
                            role="tool",
                            content=f"Error: Tool '{tool_name}' not found. Please ONLY use tools from the following list: {available_tools}. If you need a search, use 'gemini_search'.",
                            tool_call_id=call.id,
                            name=tool_name
                        )
                        continue

                    if not self._check_permission(user_id, tool_name):
                        await send_callback(f"🚫 **アクセス拒否**: `{tool_name}` を実行する権限がありません。")
                        memory.add_message(
                            session_id=session_id,
                            role="tool",
                            content=f"Access Denied: You do not have permission to execute tool '{tool_name}'. Please ask the administrator for access if needed.",
                            tool_call_id=call.id,
                            name=tool_name
                        )
                        continue

                    # 承認チェック
                    # 危険なツールの管理者確認
                    if getattr(tool_instance, "is_dangerous", False):
                        admin_id = os.getenv("ADMIN_DISCORD_USER_ID")
                        if admin_id and user_id != admin_id:
                            # ACL で許可されていても、is_dangerous は管理者のみ (追加の安全策)
                            await send_callback(f"🚫 **管理者制限**: `{tool_name}` は危険な操作に分類されており、管理者以外は実行できません。")
                            memory.add_message(
                                session_id=session_id,
                                role="tool",
                                content=f"Access Denied: Tool '{tool_name}' is marked as dangerous and restricted to admins only.",
                                tool_call_id=call.id,
                                name=tool_name
                            )
                            continue

                        # 承認チェック (危険なツールは強制、その他はツールの設定に従う)
                        should_approve = getattr(tool_instance, "requires_approval", False) or getattr(tool_instance, "is_dangerous", False)
                        
                        if should_approve:
                            if ask_approval_callback:
                                warning_prefix = "⚠️ **警告: これは危険な操作です**\n" if getattr(tool_instance, "is_dangerous", False) else ""
                                approved = await ask_approval_callback(tool_name, args, message_prefix=warning_prefix)
                                if not approved:
                                    memory.add_message(
                                        session_id=session_id,
                                        role="tool",
                                        content=f"User denied permission to execute '{tool_name}'. Proceed without it.",
                                        tool_call_id=call.id,
                                        name=tool_name
                                    )
                                    continue # 次のツールコールへ

                    
                    await send_callback(f"🛠️ 実行中: `{tool_name}(...)`")
                    print(f"DEBUG: Calling tool '{tool_name}' with args {args}")
                    if log_callback:
                        await log_callback(f"🔹 RUN: {tool_name}\nARGS: {json.dumps(args, ensure_ascii=False)}")
                    
                    try:
                        tool_result = await tool_registry.call_tool(tool_name, session_id=session_id, discord_send_callback=send_callback, **args)
                        print(f"DEBUG: Tool '{tool_name}' returned: {tool_result}")
                    except Exception as e:
                        import traceback
                        error_trace = traceback.format_exc()
                        print(f"DEBUG: Error in tool_registry.call_tool for {tool_name}: {e}")
                        # AI が原因を特定しやすいよう、型情報やメッセージを詳細に提供
                        tool_result = f"Error executing tool {tool_name} (Type: {type(e).__name__}): {str(e)}\n\n💡 自己診断ヒント: 引数、ファイルパス、権限が正しいか確認してください。必要なら ls 等で状況を調査してください。"
                        
                    
                    # 結果を記録
                    formatted_result = f"--- ツール実行結果 ({tool_name}) ---\n{str(tool_result)}\n--- 実行結果終了 ---"
                    print(f"DEBUG: Adding tool result to memory for {tool_name}")
                    if log_callback:
                        await log_callback(f"✅ RESULT: {tool_name}\nOUTPUT:\n{str(tool_result)}")
                    
                    memory.add_message(
                        session_id=session_id,
                        role="tool",
                        content=formatted_result,
                        tool_call_id=call.id,
                        name=tool_name
                    )
                # 全てのツール実行後に再考ループへ
                print("DEBUG: All tools executed. Continuing to next turn.")
                continue
            else:
                # ツール呼び出しがなければ正常終了
                return None
                
        return None # ここには基本来ない

# シングルトンインスタンス
agent = Agent()
