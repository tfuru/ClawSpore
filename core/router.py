import json
from core.llm_client import llm
from core.tools.registry import tool_registry

class ToolRouter:
    """
    ユーザーの入力に基づいて、利用可能なツールの中から最適なものを選択・フィルタリングするルーター。
    """
    def __init__(self):
        self.system_prompt = """You are the Tool Selection Advisor for ClawSpore.
Your task is to analyze the user's message (and context) and select the most relevant tools (up to 5) from the available list to achieve the user's intent.

### Selection Rules:
1. If the user seeks specific information (search, calculation, file ops, etc.), select the corresponding tools.
2. If multiple tools are needed to complete a complex task, select all of them (max 5).
3. If no tools are needed (casual chat or direct answer possible), return an empty list `[]`.
4. Return ONLY the tool names in a JSON array. Do not include any explanation.

### Output Format:
JSON array of strings.
Example: ["tool_a", "tool_b"]
"""

    async def select_tools(self, user_prompt: str, context: list = None) -> list:
        """
        Filter and select relevant tools based on user input.
        """
        tools_overview = tool_registry.get_tools_overview()
        
        # Router choice prompt
        router_prompt = f"""You are a tool selection specialist. Analyze the user intent and select the optimal tools.

User Prompt: "{user_prompt}"

Select the necessary tools from the list below to solve this request.
If no tools are relevant or it's just a casual conversation, return an empty list `[]`.

Available Tools:
{tools_overview}

Output MUST be a JSON list only. No reasoning, no thoughts, no extra text.
Example: ["tool_name1", "tool_name2"]
"""

        messages = [
            {"role": "system", "content": self.system_prompt},
        ]
        
        if context:
            # 最新の5件を対象にする
            target_context = context[-5:]
            for msg in target_context:
                role = msg.get("role")
                content = msg.get("content")
                if not content: continue
                
                # Normalize roles
                if role == "tool" or role == "system":
                    new_role = "user"
                    new_content = f"[{role.upper()} INFO] {content}"
                else:
                    new_role = role
                    new_content = content
                
                # 直前のメッセージと同じロールならマージ、そうでなければ新規追加
                if messages and messages[-1]["role"] == new_role:
                    messages[-1]["content"] += f"\n\n{new_content}"
                else:
                    messages.append({"role": new_role, "content": new_content})
        
        # 最後にルーター用プロンプトを追加（直前が user ならマージ）
        if messages and messages[-1]["role"] == "user":
            messages[-1]["content"] += f"\n\n--- ROUTER INSTRUCTION ---\n{router_prompt}"
        else:
            messages.append({"role": "user", "content": router_prompt})

        try:
            # Use standard model (LM Studio) for routing as per user request
            response = await llm.chat(messages, use_gemini=False)
            content = response.content.strip() if hasattr(response, "content") else ""
            
            # JSON extraction (robust pattern for any [ ... ] structure)
            import re
            json_match = re.search(r'\[.*\]', content, re.DOTALL)
            if json_match:
                try:
                    # JSON としてパースを試みる。失敗した場合は eval 的な処理を避けて空にする
                    import json
                    raw_json = json_match.group(0).replace("'", '"') # シングルクォートをダブルクォートに簡易置換
                    selected_names = json.loads(raw_json)
                    if not isinstance(selected_names, list):
                        selected_names = []
                    else:
                        # 全ての要素が文字列であることを確認
                        selected_names = [str(name) for name in selected_names]
                        # 重複を除去 (順序を維持)
                        selected_names = list(dict.fromkeys(selected_names))
                except:
                    selected_names = []
                    
                # Filter to existing tools only
                valid_tools = [name for name in selected_names if tool_registry.get_tool(name)]
                print(f"ToolRouter: Selected {len(valid_tools)} tools: {valid_tools}")
                return valid_tools
            
            return []
        except Exception as e:
            print(f"ToolRouter Error: {e}")
            return []

# シングルトン
tool_router = ToolRouter()
