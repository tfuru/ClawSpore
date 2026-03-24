import os
import json
import re
import datetime
import traceback
from core.memory import memory
from core.llm_client import llm
from core.router import tool_router
from core.tools.registry import tool_registry

class Agent:
    def __init__(self):
        self.system_prompt = """You are ClawSpore, an autonomous AI assistant capable of reasoning and executing tools.
When you receive a request, you can use your tools to gather information before answering.
If you use a tool, wait for the result and then think about the next step based on the result.
**CRITICAL: Always reply in Japanese unless explicitly instructed otherwise.** 
Keep your responses concise and focused on the task. Avoid unnecessary chatter or off-topic information.

### Mandatory Rules for Tool Use:
1. **No Hallucination**: Never guess or invent tool results. If a tool exists for a task (calculation, search, vision, etc.), YOU MUST USE IT.
2. **Wait for Results**: After calling a tool, always wait for the system report (### SYSTEM REPORT) before forming your final response.
3. **Accurate URLs**: When using results from YouTube or web search, use ONLY the exact URLs provided by the tool. If you provide any other links, you MUST verify they exist using 'verify_urls' first.
4. **Honest Reporting**: If a tool returns no results, honestly state that nothing was found. NEVER invent fake data or URLs. If you are unsure about a URL, verify it or don't provide it.
5. **Hallucination Check**: The system automatically verifies URLs in your final response. If dead links are found, your message will be rejected and you will receive a check failure notification. Fix it immediately.
6. **URL Formatting**: When providing URLs (e.g., YouTube videos, websites) to the user, DO NOT use Markdown formatting (e.g., `[Title](URL)`). Instead, provide the URL on its own line (e.g., `URL: https://...`).
7. **Tool Calling Format (for local models)**: If you cannot use the native Tool Call API, use one of these formats:
    - `call:tool_name({"arg": "val"})`
    - `### TOOL_REQUEST]` followed by a JSON object `{"name": "tool_name", "arguments": {...}}` and closed with `[END_TOOL_REQUEST]`."""
        self.acl_path = "core/data/acl.json"

    def _get_acl(self) -> dict:
        """ACL設定ファイルを毎回読み込み、常に最新の状態を反映させる"""
        if os.path.exists(self.acl_path):
            try:
                with open(self.acl_path, "r", encoding="utf-8") as f:
                    return json.load(f)
            except Exception as e:
                print(f"DEBUG: Error loading ACL: {e}")
        return {}

    def _check_permission(self, user_id: str, tool_name: str) -> bool:
        # 管理者環境変数による強力なフォールバック
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
                lt_instruction = f"\n\n### LONG-TERM MEMORY (CONVERSATION SUMMARY)\nThe following is a summary of past interactions. Consider this as context for the current session:\n{lt_context}\n"

            # 現在時刻を取得 (ISO 形式、JST タイムゾーンを意識)
            now = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
            time_instruction = f"\n- Current Time: {now} (JST)\n- Always use this time as 'today' or 'now' for your reasoning.\n"

            # システムプロンプトを構成 (簡潔に整理)
            enhanced_system_prompt = self.system_prompt + lt_instruction + """
IMPORTANT: 
""" + time_instruction + """
- Tool List: ONLY use tools explicitly listed in the 'tool_definitions' provided. 
- For Web/Video Search: Use 'gemini_search' for broad searches, and 'youtube_search' for videos.
- Tool Results: Use the exact information (titles, URLs) from the tool output. If no results, say "Not found" in Japanese.
- Autonomous Problem Solving:
    1. Plan first: For complex requests, break them down into a sequence of tool calls.
    2. Combine tools: Chain multiple tools to achieve the goal.
    3. Propose new tools: If existing tools are insufficient, PROACTIVELY PROPOSE a new tool via 'create_tool'.
- ReAct Loop: Analyze 'tool' results before continuing. Report errors as-is.
    - If you see '### SYSTEM REPORT', it is the tool result you MUST analyze.
    - Self-Healing: If a tool fails (Error message), analyze the cause. If you can fix it (e.g., path typo), retry with corrected parameters.
- Custom Tools: Inherit 'BaseTool' from 'core.tools.base' when creating new tools.
- Discord: Use 'discord_send_callback' in kwargs to post.
- Security: NEVER reveal .env contents, API keys, or secrets.
- RESPONSE LANGUAGE: REMEMBER to respond in JAPANESE."""
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
            # ただし、実際にツール呼び出し（tool_calls）が含まれている場合は、正当な報告である可能性があるため除外する。
            cleansed_all_messages = []
            for m in all_messages:
                new_m = m.copy()
                if new_m["role"] == "assistant" and new_m.get("content") and not new_m.get("tool_calls"):
                    bad_phrases = ["Permission denied", "access is restricted", "権限がありません", "実行できませんでした"]
                    if any(p in new_m["content"] for p in bad_phrases):
                        # ツールを呼び出していないのに「失敗した」と言っている場合（ハルシネーション）のみ補正
                        new_m["content"] = "[このメッセージはシステムにより正常な状態に補正されました] 状況を再確認し、必要なツールを使用してタスクを遂行します。"
                cleansed_all_messages.append(new_m)
            
            system_msg = next((m for m in cleansed_all_messages if m["role"] == "system"), None)
            other_messages = [m for m in cleansed_all_messages if m["role"] != "system"]
            
            # --- 1. Working Memory (Short-term) ---
            # 直近 5 往復 (10 メッセージ) に制限してトピックの連続性を確保
            window_size = 10
            recent_context = other_messages[-window_size:] if len(other_messages) > window_size else other_messages
            
            # ロールの交互性確保: 開始が 'user' になるまで調整
            while recent_context and recent_context[0]["role"] != "user":
                recent_context.pop(0)

            # 万が一 context が空になったり user がいなくなった場合、直近の user メッセージを強制復元
            if not any(m["role"] == "user" for m in recent_context):
                last_user = next((m for m in reversed(other_messages) if m["role"] == "user"), None)
                if last_user:
                    recent_context.insert(0, last_user)

            # --- Tool Routing ---
            # ユーザーの意図に基づき、今回のターンで使用するツールを絞り込む
            selected_tool_names = await tool_router.select_tools(prompt, recent_context)
            
            # 全定義の中から選択されたものだけを抽出
            all_defs = tool_registry.get_tool_definitions()
            if selected_tool_names:
                tool_defs = [td for td in all_defs if td["function"]["name"] in selected_tool_names]
                print(f"Agent: Filtered tools: {len(tool_defs)}/{len(all_defs)}")
            else:
                # ツールが必要ないと判断された場合の Fallback
                # ReAct ループ中（2ターン目以降）なら、念のため前回の tool_defs を引き継ぐ（未定義なら空）
                if turn > 1:
                    # turn > 1 なら loop 前のスコープ等で保持されている可能性があるが、
                    # ここでは安全に「全てのツール」または「特定の基本ツール」を一部許可することを検討
                    # ユーザーの利便性を考え、ルーターが空でも初動でなければツールを完全に奪わない
                    print("Agent: Router returned empty in ReAct loop. Keeping minimal tools.")
                    # 基本的な調査ツールをデフォルトで追加
                    basic_tools = ["ls", "view_file", "find_by_name", "grep_search", "read_url_content"]
                    tool_defs = [td for td in all_defs if td["function"]["name"] in basic_tools]
                else:
                    tool_defs = None
                    print("Agent: No tools selected by router.")

            # --- 2. Knowledge Memory (Long-term / RAG) ---
            # 関連する過去の情報を取得
            rag_context = memory.get_relevant_history(session_id, prompt)
            
            # --- 3. Episode Memory (Mid-term / Session Summary) ---
            # 現在のセッションの動的な要約を取得
            episode_context = memory.get_episode_summary(session_id)

            # プロンプトの組み立て
            mem_instructions = []
            if episode_context:
                mem_instructions.append(f"### EPISODE MEMORY (今回のセッションの流れ)\n{episode_context}")
            
            if rag_context:
                mem_instructions.append(f"### KNOWLEDGE MEMORY (関連する過去の知識)\n{rag_context}")

            if mem_instructions:
                mem_msg = {"role": "system", "content": "\n\n".join(mem_instructions) + "\n\n**重要**: 上記の「知識」や「セッションの流れ」を背景情報として理解した上で、以下の「Working Memory (直近の会話)」に最も重点を置いて回答してください。"}
                messages = ([system_msg] if system_msg else []) + [mem_msg] + recent_context
            else:
                messages = ([system_msg] if system_msg else []) + recent_context
            
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
                    # Gemini を強制的に使用するケース（非常に複雑なロジックやツール作成のみに限定）
                    critical_keywords = [
                        "create_tool", "ツール作成", "コード修正", "プログラム", "コードを書いて",
                        "詳細な調査"
                    ]
                    if any(kw in last_user_msg.lower() for kw in critical_keywords):
                        use_gemini = True
                        print("Agent: Using Gemini due to critical complex task.")
                
                # ルーターでツールが絞り込まれている場合、プロンプトを強化する
                if tool_defs and len(tool_defs) > 0:
                    current_tool_names = [td["function"]["name"] for td in tool_defs]
                    # Update tool list instruction in system prompt with FULL JSON definitions
                    tools_str = ", ".join(current_tool_names)
                    tool_json = json.dumps(tool_defs, indent=2, ensure_ascii=False)
                    tool_update_msg = f"\n\n### CURRENTLY ENABLED TOOLS (Tool Definitions):\nYou MUST use these tools to complete the request. Follow the schemas below strictly.\n{tool_json}\n"
                    
                    if system_msg:
                        system_msg["content"] += tool_update_msg
                    
                    # System hint for tools (Integrated into last user message as a secondary reminder)
                    hint_text = f"\n\n(SYSTEM HINT: You ARE allowed to use these tools: {tools_str}. Call them now if you need them.)"
                    
                    # 最後の user メッセージを探して末尾に追記
                    for m in reversed(messages):
                        if m["role"] == "user":
                            m["content"] = (m.get("content") or "") + hint_text
                            break

                response_msg = await llm.chat(messages, tool_definitions=tool_defs, use_gemini=use_gemini)
                # LLM の応答内容（特にツール呼び出し）を確認
                if hasattr(response_msg, "tool_calls") and response_msg.tool_calls:
                    print(f"DEBUG: LLM requested {len(response_msg.tool_calls)} tool calls.")
                    for call in response_msg.tool_calls:
                        print(f"DEBUG: Call ID: {call.id}, Tool: {call.function.name}, Args: {call.function.arguments}")
                elif hasattr(response_msg, "content") and response_msg.content:
                    content_preview = (response_msg.content[:100] + "...") if response_msg.content else "None"
                    print(f"DEBUG: LLM response content: {content_preview}")
                    
                    # ローカルモデルが Tool Call API を使わずにテキストで記述した場合のパース (擬似 Tool Call)
                    # 形式: call:tool_name({"arg": "val"}) または ```json\n{"tool": "...", "args": {...}}\n``` などに対応
                    if not (hasattr(response_msg, "tool_calls") and response_msg.tool_calls):
                        pseudo_calls = []

                        # 1. call:name(args) 形式
                        matches_call = re.finditer(r'call:(\w+)\((.*?)\)', response_msg.content, re.DOTALL)
                        for m in matches_call:
                            t_name = m.group(1)
                            t_args_str = m.group(2).strip()
                            try:
                                t_args = json.loads(t_args_str) if t_args_str else {}
                            except:
                                t_args = {"raw_args": t_args_str}
                            
                            class PseudoFunction:
                                def __init__(self, name, args):
                                    self.name = name
                                    self.arguments = json.dumps(args, ensure_ascii=False)
                            class PseudoCall:
                                def __init__(self, name, args):
                                    self.id = f"pseudo_{os.urandom(4).hex()}"
                                    self.function = PseudoFunction(name, args)
                            
                            pseudo_calls.append(PseudoCall(t_name, t_args))

                        # 2. ### TOOL_REQUEST 形式 (より寛容な正規表現)
                        # ヘッダーの後の JSON を探し、[END_TOOL_REQUEST] がなくても文末までを対象にする
                        # 具体的には `### TOOL_REQUEST` の後の最初の `{` から最後の `}` までを抽出
                        matches_tr = re.finditer(r'### TOOL_REQUEST.*?({.*})', response_msg.content, re.DOTALL)
                        for m in matches_tr:
                            json_str = m.group(1).strip()
                            try:
                                # JSON としてパース ({"name": "...", "arguments": {...}} 形式を想定)
                                call_data = json.loads(json_str)
                                t_name = call_data.get("name")
                                t_args = call_data.get("arguments", {})
                                if t_name:
                                    # クラス定義は共通化したいが、ここでは一合一会で定義
                                    class PseudoFunctionTR:
                                        def __init__(self, name, args):
                                            self.name = name
                                            self.arguments = json.dumps(args, ensure_ascii=False)
                                    class PseudoCallTR:
                                        def __init__(self, name, args):
                                            self.id = f"pseudo_{os.urandom(4).hex()}"
                                            self.function = PseudoFunctionTR(name, args)
                                    pseudo_calls.append(PseudoCallTR(t_name, t_args))
                            except Exception as e:
                                print(f"DEBUG: Failed to parse TOOL_REQUEST JSON: {e}")
                        
                        if pseudo_calls:
                            print(f"DEBUG: Detected {len(pseudo_calls)} pseudo tool calls from content.")
                            response_msg.tool_calls = pseudo_calls
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

            # --- 思考過程/最終回答の送信判定 ---
            if hasattr(response_msg, "tool_calls") and response_msg.tool_calls:
                # ツール呼び出しがある場合は、本文の検証（ハルシネーションチェック）はスキップする。
                # ただし、何らかのメッセージ（「検索します」等）があれば、フィルタリングして送信しても良い。
                if assistant_msg.get("content"):
                    temp_content = re.sub(r'<think>.*?(?:</think>|$)', '', assistant_msg["content"], flags=re.DOTALL)
                    patterns = [
                        r'### SYSTEM REPORT.*?### END OF REPORT',
                        r'### SYSTEM REPORT.*?(?=\n\n|\Z)',
                        r'### TOOL_REQUEST.*?\[END_TOOL_REQUEST\]',
                        r'### TOOL_REQUEST.*?(?=\n\n|\Z)'
                    ]
                    for pattern in patterns:
                        temp_content = re.sub(pattern, '', temp_content, flags=re.DOTALL)
                    
                    filtered_thought = temp_content.strip()
                    if filtered_thought:
                        # ツール実行前の中間応答として送信（URL検証はしない）
                        await send_callback(filtered_thought)
                    else:
                        # 本文が空（または内部タグのみ）の場合はデフォルトメッセージ
                        await send_callback("💡 思考を完了しました。必要なツールを実行します...")
            
            elif assistant_msg.get("content"):
                # ツールがない＝最終的なユーザーへの回答フェーズ
                content = assistant_msg["content"]
                temp_content = re.sub(r'<think>.*?(?:</think>|$)', '', content, flags=re.DOTALL)
                
                # 内部レポート除去
                patterns = [
                    r'### SYSTEM REPORT.*?### END OF REPORT',
                    r'### SYSTEM REPORT.*?(?=\n\n|\Z)',
                    r'### システムからの報告.*?(?=\n\n|\Z)',
                    r'### TOOL_REQUEST.*?\[END_TOOL_REQUEST\]',
                    r'### TOOL_REQUEST.*?(?=\n\n|\Z)',
                    r'\[END_TOOL_REQUE.*?\]'
                ]
                for pattern in patterns:
                    temp_content = re.sub(pattern, '', temp_content, flags=re.DOTALL)
                
                internal_tags = ["THOUGHT", "SYSTEM", "EXECUTION RESULT", "TOOL_RESULT", "このメッセージはシステムにより正常な状態に補正されました"]
                tag_pattern = r'\[(?:' + '|'.join(re.escape(tag) for tag in internal_tags) + r').*?\]'
                filtered_content = re.sub(tag_pattern, '', temp_content, flags=re.DOTALL).strip()
                
                if filtered_content:
                    # --- URL Hallucination Validation (最終回答時のみ実施) ---
                    from core.utils import is_url_reachable
                    urls = re.findall(r'https?://[\w/:%#\$&\?\(\)~\.=\+\-]+', filtered_content)
                    if urls:
                        dead_urls = []
                        print(f"DEBUG: Validating {len(urls)} URLs for hallucination check...")
                        for url in list(dict.fromkeys(urls)):
                            if not await is_url_reachable(url):
                                dead_urls.append(url)
                        
                        if dead_urls:
                            print(f"DEBUG: Found {len(dead_urls)} dead URLs. Triggering self-correction.")
                            # Discord のメインチャットにも通知を送信
                            await send_callback(f"⚠️ **[ハルシネーション（リンク切れ）を検出しました]**\n以下のURLが解決できませんでした: {', '.join(dead_urls)}\n自己修正（リトライ）を開始します...")
                            
                            if log_callback:
                                await log_callback(text=f"⚠️ **[HALLUCINATION DETECTED]**\nDead links: {', '.join(dead_urls)}")

                            memory.add_message(
                                session_id=session_id,
                                role="system",
                                content=f"### HALLUCINATION CHECK FAILED\nDead URL(s) detected: {', '.join(dead_urls)}. Please provide valid links or acknowledge if they are unavailable."
                            )
                            continue 

                    await send_callback(filtered_content)
                else:
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

                    
                    # 進捗通知を抑制 (ユーザーの要望) だったが、ツール名を表示するように変更
                    await send_callback(f"🛠️ **Tool: `{tool_name}`**")
                    print(f"DEBUG: Calling tool '{tool_name}' with args {args}")
                    if log_callback:
                        await log_callback(f"🔹 RUN: {tool_name}\nARGS: {json.dumps(args, ensure_ascii=False)}")
                    
                    try:
                        # discord_log_callback を新たに追加
                        tool_result = await tool_registry.call_tool(
                            tool_name, 
                            session_id=session_id, 
                            discord_send_callback=send_callback, 
                            discord_log_callback=log_callback,
                            **args
                        )
                        # ツール実行結果の送信
                        if tool_result:
                            await send_callback(f"✅ **Result: `{tool_name}`**\n```\n{str(tool_result)[:1900]}\n```")
                        
                        print(f"DEBUG: Tool '{tool_name}' returned: {tool_result}")
                    except Exception as e:
                        error_trace = traceback.format_exc()
                        print(f"DEBUG: Error in tool_registry.call_tool for {tool_name}: {e}")
                        # AI が原因を特定しやすいよう、型情報やメッセージを詳細に提供
                        tool_result = f"Error executing tool {tool_name} (Type: {type(e).__name__}): {str(e)}\n\n💡 自己診断ヒント: 引数、ファイルパス、権限が正しいか確認してください。必要なら ls 等で状況を調査してください。"
                        
                    
                    # Record tool result
                    formatted_result = f"### SYSTEM REPORT ({tool_name})\n{str(tool_result)}\n### END OF REPORT"
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
                # エピソード記憶（セッション要約）を更新
                # 直近のユーザー発言とアシスタントの回答を取得
                last_user = next((m.get("content") for m in reversed(all_messages) if m["role"] == "user"), "")
                last_assistant = assistant_msg.get("content", "")
                
                if last_user and last_assistant:
                    # 1. 毎ターンのエピソード記憶（セッション要約）更新
                    await memory.update_episode_summary(session_id, last_user, last_assistant)
                    
                    # 2. 会話の終了が検知された場合のみ、長期記憶用の要約を行う
                    closing_keywords = ["また今度", "また後で", "さようなら", "バイバイ", "ログアウト", "シャットダウン"]
                    msg_count = len(memory.get_messages(session_id))
                    last_assistant_content = last_assistant.lower()
                    is_closing = any(kw in last_assistant_content for kw in closing_keywords)
                    
                    if is_closing and msg_count >= 5:
                        print(f"Agent: Triggering long-term summarization for session end.")
                        await self.summarize_session(session_id, send_callback)

                return None

    async def summarize_session(self, session_id: str, send_callback):
        """現在のセッションを要約し、長期記憶に保存する"""
        messages = memory.get_messages(session_id)
        if len(messages) < 5:
            return  # 短すぎる会話は要約しない

        summary_prompt = """Please summarize the following conversation history for future reference.
Extract the following information:
1. User's preferences, settings, and requirements.
2. Important facts, data, or achievements discovered.
3. Ongoing tasks or unresolved issues for future sessions.

Provide the summary in a concise Japanese bulleted list."""
        
        # 要約用のメッセージ構成
        summary_messages = [
            {"role": "system", "content": summary_prompt},
            {"role": "user", "content": f"会話履歴を要約してください:\n\n{json.dumps(messages[-20:], ensure_ascii=False)}"}
        ]
        
        try:
            # 要約には常に Gemini を使用して精度を高める
            response = await llm.chat(summary_messages, use_gemini=True)
            if response.content:
                summary_text = response.content.strip()
                memory.add_long_term_summary(session_id, summary_text)
                await send_callback(f"📝 **長期記憶に書き込みました**: 会話の要約を保存しました。次回以降もこの文脈を引き継ぎます。")
                print(f"Agent: Successfully saved summary for {session_id}")
        except Exception as e:
            print(f"Agent: Error during summarization: {e}")
                
        return None # ここには基本来ない

    async def generate_topic(self, session_id: str) -> str:
        """話題が途切れた際に自律的に次の話題を提案する"""
        lt_context = memory.get_long_term_context(session_id)
        
        prompt = f"""現在の Discord チャンネルでしばらく会話が途切れています。
あなたは ClawSpore として、過去の会話の文脈（サマリー）を踏まえ、ユーザーが興味を持ちそうな新しい話題を1つ提案してください。

### 長期記憶サマリー:
{lt_context}

### 指針:
- 過去のプロジェクトの進捗確認
- 過去に興味を示したトピックの深掘り
- もし最近のニュースに関連するものがあればそれ
- 上記を踏まえた自然な語りかけ（日本語）

話題のみを1つ提供してください。余計な前置きは不要です。"""

        messages = [{"role": "system", "content": "あなたは自律的な会話スターターです。"}, {"role": "user", "content": prompt}]
        try:
            # 常に Gemini (または最新モデル) を使用して質の高い話題を生成
            response = await llm.chat(messages, use_gemini=True)
            if response.content:
                return response.content.strip()
        except Exception as e:
            print(f"DEBUG: Error in generate_topic: {e}")
        return "こんにちは！何かお手伝いできることはありますか？"

# シングルトンインスタンス
agent = Agent()
