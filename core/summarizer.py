import json
from core.llm_client import llm

class MemorySummarizer:
    """
    会話履歴を要約して長期記憶用のサマリーを生成するクラス。
    """
    def __init__(self):
        self.system_prompt = """あなたは優秀な記録係です。
提供された会話履歴を分析し、将来の参照のために重要な情報を簡潔に要約してください。
以下の点に注目して要約を作成してください：
1. ユーザーの好みや特定の指示
2. これまでに作成・修正されたツールやファイルの情報
3. 解決済みの問題や現在進行中のタスクの状況
4. その他、将来の会話で役立つ重要な文脈

要約は箇条書きで、日本語で作成してください。"""

    async def summarize(self, messages: list) -> str:
        """
        メッセージリストを要約する。
        """
        if not messages:
            return ""

        # 会話内容をテキスト化
        chat_text = ""
        for m in messages:
            role = m.get("role")
            content = m.get("content", "")
            if content:
                chat_text += f"{role}: {content}\n"
        
        prompt = f"以下の会話履歴を要約してください：\n\n{chat_text}"
        
        try:
            # Gemini を使用して要約を生成 (信頼性と性能のため)
            summary = await llm.generate_response(
                prompt=prompt,
                system_message=self.system_prompt,
                use_gemini=True
            )
            return summary
        except Exception as e:
            print(f"Summarizer Error: {e}")
            return f"要約の生成に失敗しました: {e}"

summarizer = MemorySummarizer()
