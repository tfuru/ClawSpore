import os
import json
import traceback
from openai import AsyncOpenAI
try:
    from google import genai
    from google.genai import types
except ImportError:
    genai = None
    types = None
from dotenv import load_dotenv

load_dotenv()

from core.utils import recursive_sanitize

class LLMClient:
    def __init__(self):
        # LM Studio (Local)
        self.lm_studio_base_url = os.getenv("LM_STUDIO_URL", "http://localhost:1234/v1")
        self.lm_studio_model = os.getenv("LM_STUDIO_MODEL", "local-model")
        self.local_client = AsyncOpenAI(
            api_key="lm-studio",
            base_url=self.lm_studio_base_url
        )

        # Gemini (Native SDK via google-genai)
        self.gemini_api_key = os.getenv("GEMINI_API_KEY")
        self.gemini_model_name = os.getenv("GEMINI_MODEL", "gemini-1.5-flash")

        self.genai_client = None
        if self.gemini_api_key and genai:
            if self.gemini_api_key.startswith("encrypted:"):
                print("WARNING: GEMINI_API_KEY is still encrypted.")
            else:
                api_version = 'v1'
                if "preview" in self.gemini_model_name or "gemini-3" in self.gemini_model_name:
                    api_version = 'v1alpha'
                
                try:
                    self.genai_client = genai.Client(
                        api_key=self.gemini_api_key,
                        http_options={'api_version': api_version}
                    )
                except Exception as e:
                    print(f"DEBUG: Error initializing GenAI Client: {e}")

    async def chat(self, messages: list, tool_definitions: list = None, use_gemini: bool = False):
        if use_gemini and self.gemini_api_key:
            return await self._chat_gemini_native(messages, tool_definitions)
        return await self._chat_local(messages, tool_definitions)

    async def _chat_local(self, messages: list, tool_definitions: list = None):
        client = self.local_client
        model = self.lm_studio_model
        print(f"LLMClient: Using Local Model ({model}) for this request.")
        
        # message 内に bytes 型が混入していると JSON シリアライズで落ちるため再帰的に整形
        messages = [recursive_sanitize(msg) for msg in messages]

        # LM Studio (Local) 向けのロール正規化:
        # 1. 'tool' ロールを 'user' へ変換
        # 2. ロールが連続する場合にマージ
        normalized = []
        for msg in messages:
            role = msg["role"]
            content = msg.get("content") or ""
            
            # [EXECUTION RESULT] などの内部用タグを local model には見せないように除去 (ハルシネーション防止)
            import re
            content = re.sub(r'\[EXECUTION RESULT\].*?\[END OF RESULT\]', lambda m: m.group(0).replace("[EXECUTION RESULT]", "").replace("[END OF RESULT]", ""), content, flags=re.DOTALL)
            content = re.sub(r'\[TOOL_RESULT\].*?\[END_TOOL_RESULT\]', lambda m: m.group(0).replace("[TOOL_RESULT]", "").replace("[END_TOOL_RESULT]", ""), content, flags=re.DOTALL)

            # tool ロールの平坦化
            if role == "tool":
                role = "user"
                # 「システムが報告した結果」として簡潔に提示
                content = f"### システムからの報告 (ツール: {msg.get('name', 'unknown')} の実行結果)\n{content.strip()}"
            
            if normalized and normalized[-1]["role"] == role:
                if content:
                    normalized[-1]["content"] = (normalized[-1].get("content", "") + "\n\n" + content).strip()
            else:
                normalized.append({"role": role, "content": content})

        try:
            params = {"model": model, "messages": normalized, "temperature": 0.7}
            if tool_definitions:
                # ツール定義全体をサニタイズするが、構造が壊れないようにする
                params["tools"] = recursive_sanitize(tool_definitions)
                params["tool_choice"] = "auto"
            response = await client.chat.completions.create(**params)
            return response.choices[0].message
        except Exception as e:
            error_msg = str(e)
            print(f"Error in LLMClient chat (local): {error_msg}")
            raise RuntimeError(f"LLM(Local) との通信中にエラーが発生しました: {error_msg}")

    async def _chat_gemini_native(self, messages: list, tool_definitions: list = None):
        if not self.genai_client:
            raise RuntimeError("Gemini Client is not initialized.")
        
        # bytes 型混入防止
        messages = [recursive_sanitize(msg) for msg in messages]

        try:
            system_instruction = None
            contents = []
            for i, msg in enumerate(messages):
                role = msg.get("role")
                content = msg.get("content", "") or ""
                if role == "system":
                    system_instruction = content
                elif role == "user":
                    parts = []
                    if isinstance(content, str):
                        parts.append(types.Part(text=content))
                    elif isinstance(content, list):
                        # マルチモーダル：テキストと画像（Partオブジェクト相当の辞書など）のリストを想定
                        for item in content:
                            if isinstance(item, str):
                                parts.append(types.Part(text=item))
                            elif isinstance(item, dict):
                                if "text" in item:
                                    parts.append(types.Part(text=item["text"]))
                                elif "inline_data" in item:
                                    data = item["inline_data"]
                                    mime_type = item.get("mime_type", "image/png")
                                    parts.append(types.Part(inline_data=types.Blob(mime_type=mime_type, data=data)))
                    contents.append(types.Content(role="user", parts=parts))
                elif role == "assistant":
                    parts = []
                    if content:
                        parts.append(types.Part(text=content))
                    if "tool_calls" in msg and msg["tool_calls"]:
                        for call in msg["tool_calls"]:
                            if not isinstance(call, dict): continue
                            fn = call.get("function")
                            if not fn: continue
                            fc_data = {
                                "name": fn.get("name"),
                                "args": json.loads(fn.get("arguments", "{}")) if isinstance(fn.get("arguments"), str) else (fn.get("arguments") or {})
                            }
                            if not fc_data["name"]: continue
                            p = types.Part(function_call=types.FunctionCall(
                                name=fc_data["name"],
                                args=fc_data["args"]
                            ))
                            ts = call.get("thought_signature")
                            if ts:
                                # bytes型ならそのまま、文字列ならエンコード、base64: プレフィックスがあればデコード
                                if isinstance(ts, bytes):
                                    p.thought_signature = ts
                                elif isinstance(ts, str) and ts.startswith("base64:"):
                                    import base64
                                    try:
                                        p.thought_signature = base64.b64decode(ts[7:])
                                    except:
                                        p.thought_signature = ts.encode('utf-8')
                                elif isinstance(ts, str):
                                    p.thought_signature = ts.encode('utf-8')
                                else:
                                    p.thought_signature = ts
                            parts.append(p)
                    contents.append(types.Content(role="model", parts=parts))
                elif role == "tool":
                    contents.append(types.Content(role="tool", parts=[
                        types.Part(function_response=types.FunctionResponse(
                            name=msg.get("name") or "unknown",
                            response={"result": msg.get("content") or ""}
                        ))
                    ]))

            tools = []
            if tool_definitions:
                def sanitize_schema(schema):
                    if not isinstance(schema, dict): return schema
                    return {k: sanitize_schema(v) for k, v in schema.items() if k != "default"}
                
                # 通常の関数（gemini_search 以外）を抽出
                gemini_functions = []
                has_gemini_search = False
                for td in tool_definitions:
                    if not isinstance(td, dict): continue
                    f = td.get("function")
                    if not f or not f.get("name"): continue
                    
                    if f.get("name") == "gemini_search":
                        has_gemini_search = True
                        continue
                        
                    params = sanitize_schema(f.get("parameters", {}))
                    gemini_functions.append(types.FunctionDeclaration(
                        name=f.get("name"),
                        description=f.get("description", ""),
                        parameters=params
                    ))
                
                # Google Search と Function Calling は現在共存できない（いずれかが無効化される）ため、
                # 通常のツールがある場合は、通常のツールを優先して登録する。
                # ただし、通常のツールがなく gemini_search のみがある場合は Google Search を有効にする。
                if gemini_functions:
                    tools.append(types.Tool(function_declarations=gemini_functions))
                    # 通常のツールがある場合でも、gemini_search を提供したい場合はここでの判断が必要だが、
                    # 現状の SDK/API の制約を回避するため、通常のツール（youtube_search等）を優先。
                elif has_gemini_search:
                    tools.append(types.Tool(google_search=types.GoogleSearch()))
            
            if not tools:
                tools = None

            # 手動での安全設定はトラブルの元になりやすいため、まずはデフォルトで試すか、正しいカテゴリ名を使用
            safety_settings = [
                types.SafetySetting(category="HARM_CATEGORY_HATE_SPEECH", threshold="BLOCK_NONE"),
                types.SafetySetting(category="HARM_CATEGORY_HARASSMENT", threshold="BLOCK_NONE"),
                types.SafetySetting(category="HARM_CATEGORY_SEXUALLY_EXPLICIT", threshold="BLOCK_NONE"),
                types.SafetySetting(category="HARM_CATEGORY_DANGEROUS_CONTENT", threshold="BLOCK_NONE"),
                types.SafetySetting(category="HARM_CATEGORY_CIVIC_INTEGRITY", threshold="BLOCK_NONE"),
            ]

            response = await self.genai_client.aio.models.generate_content(
                model=self.gemini_model_name,
                contents=contents,
                config=types.GenerateContentConfig(
                    tools=tools, 
                    system_instruction=system_instruction,
                    safety_settings=safety_settings
                )
            )
            
            content = ""
            tool_calls = []
            if response.candidates:
                candidate = response.candidates[0]
                if candidate.content and candidate.content.parts:
                    for part in candidate.content.parts:
                        if hasattr(part, "text") and part.text:
                            content += part.text
                        if hasattr(part, "function_call") and part.function_call:
                            fc = part.function_call
                            ts = getattr(part, "thought_signature", None)
                            tool_calls.append({
                                "id": f"call_{os.urandom(4).hex()}",
                                "name": fc.name,
                                "args": dict(fc.args) if fc.args else {},
                                "thought_signature": ts
                            })

            # Mock objects
            class MockFunction:
                def __init__(self, name, args):
                    self.name, self.arguments = name, json.dumps(args, ensure_ascii=False) if args else "{}"
            class MockToolCall:
                def __init__(self, d):
                    self.id, self.type = d["id"], "function"
                    self.function = MockFunction(d["name"], d.get("args", {}))
                    self.thought_signature = d.get("thought_signature")
            class MockMessage:
                def __init__(self, c, t):
                    self.content, self.tool_calls = c, ([MockToolCall(tc) for tc in t] if t else None)
                def to_dict(self):
                    tc_dicts = []
                    if self.tool_calls:
                        for tc in self.tool_calls:
                            d = {"id": tc.id, "type": "function", "function": {"name": tc.function.name, "arguments": tc.function.arguments}}
                            if tc.thought_signature: d["thought_signature"] = tc.thought_signature
                            tc_dicts.append(d)
                    return {"role": "assistant", "content": self.content, "tool_calls": tc_dicts}

            return MockMessage(content if content else None, tool_calls if tool_calls else None)

        except Exception as e:
            tb = traceback.format_exc()
            raise RuntimeError(f"{e}\n{tb}")

    async def generate_response(self, prompt: str, system_message: str = "You are ClawSpore.", tool_definitions: list = None, use_gemini: bool = False):
        messages = [{"role": "system", "content": system_message}, {"role": "user", "content": prompt}]
        try:
            message = await self.chat(messages, tool_definitions, use_gemini=use_gemini)
            return message if (hasattr(message, "tool_calls") and message.tool_calls) else message.content
        except Exception as e: return f"Error: {e}"

llm = LLMClient()
