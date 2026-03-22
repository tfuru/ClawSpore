from core.tools.base import BaseTool
from core.memory import memory
from typing import Dict, Any, List

class CheckMemoryTool(BaseTool):
    """
    現在のセッションの短期記憶（履歴）、長期記憶（サマリー）、
    またはベクトル検索による関連履歴を取得するツール。
    """
    @property
    def name(self) -> str:
        return "check_memory"

    @property
    def description(self) -> str:
        return "Retrieve and display recorded memories for the current session. Modes: 'short' (latest chat history), 'long' (past summaries), or 'search' (find relevant past events using a query)."

    @property
    def parameters(self) -> Dict[str, Any]:
        return {
            "type": "object",
            "properties": {
                "mode": {
                    "type": "string",
                    "enum": ["short", "long", "search"],
                    "description": "Memory retrieval mode."
                },
                "query": {
                    "type": "string",
                    "description": "Search query (required for 'search' mode)."
                },
                "limit": {
                    "type": "integer",
                    "description": "Number of items to retrieve (default: 10 for short/long, 5 for search)."
                }
            },
            "required": ["mode"]
        }

    async def execute(self, mode: str, query: str = None, limit: int = None, **kwargs) -> str:
        session_id = kwargs.get("session_id")
        if not session_id:
            return "Error: No session_id provided."

        if mode == "short":
            msgs = memory.get_messages(session_id)
            n = limit if limit else 10
            recent_msgs = msgs[-n:] if len(msgs) > n else msgs
            
            output = [f"--- Short-term Memory (Last {len(recent_msgs)} messages) ---"]
            for m in recent_msgs:
                role = m.get("role", "unknown")
                content = m.get("content", "")
                ts = m.get("timestamp", "Unknown Time")
                # content が長すぎる場合は切り詰め
                if content and len(content) > 200:
                    content = content[:200] + "...(truncated)"
                output.append(f"[{ts}] {role}: {content}")
            return "\n".join(output)

        elif mode == "long":
            context = memory.get_long_term_context(session_id)
            if not context:
                return "No long-term summaries found for this session."
            
            summaries = context.split("\n---\n")
            n = limit if limit else 10
            recent_summaries = summaries[-n:] if len(summaries) > n else summaries
            
            output = [f"--- Long-term Memory (Last {len(recent_summaries)} summaries) ---"]
            output.extend(recent_summaries)
            return "\n".join(output)

        elif mode == "search":
            if not query:
                return "Error: Query is required for 'search' mode."
            n = limit if limit else 5
            results = memory.get_relevant_history(session_id, query, n_results=n)
            if not results:
                return f"No similar memories found for query: '{query}'"
            return results

        return f"Unknown mode: {mode}"
