import os
import json
import datetime
from typing import List, Dict, Any

from core.utils import recursive_sanitize
import uuid
try:
    from core.vector_store import vector_store
except ImportError:
    vector_store = None

class CustomJSONEncoder(json.JSONEncoder):
    def default(self, obj):
        if isinstance(obj, bytes):
            try:
                return obj.decode('utf-8')
            except:
                return f"base64:{base64.b64encode(obj).decode('ascii')}"
        return super().default(obj)


class Memory:
    """
    セッション（ユーザーやチャンネル）ごとの会話履歴とツール実行履歴を管理し、
    ディスクへの永続化をサポートします。
    """
    def __init__(self, st_dir: str = "core/data/sessions", lt_dir: str = "core/data/long_term"):
        self.sessions: Dict[str, List[Dict[str, Any]]] = {}
        self.long_term_memories: Dict[str, List[str]] = {}
        self.st_dir = st_dir
        self.lt_dir = lt_dir
        
        for d in [self.st_dir, self.lt_dir]:
            if not os.path.exists(d):
                os.makedirs(d, exist_ok=True)
        
    def _get_st_path(self, session_id: str) -> str:
        return os.path.join(self.st_dir, f"{session_id}.json")

    def _get_lt_path(self, session_id: str) -> str:
        return os.path.join(self.lt_dir, f"{session_id}.json")

    def _load_session(self, session_id: str):
        """短期記憶を読み込む"""
        path = self._get_st_path(session_id)
        if os.path.exists(path):
            try:
                with open(path, "r", encoding="utf-8") as f:
                    self.sessions[session_id] = json.load(f)
                    print(f"Memory: Loaded ST memory '{session_id}'")
            except Exception as e:
                print(f"Memory: Error loading ST '{session_id}': {e}")
                print(f"Memory: Deleting corrupted session file '{path}'")
                try:
                    os.remove(path)
                except:
                    pass
                self.sessions[session_id] = []
        else:
            self.sessions[session_id] = []

    def _load_long_term(self, session_id: str):
        """長期記憶（サマリー）を読み込む"""
        path = self._get_lt_path(session_id)
        if os.path.exists(path):
            try:
                with open(path, "r", encoding="utf-8") as f:
                    self.long_term_memories[session_id] = json.load(f)
                    print(f"Memory: Loaded LT memory '{session_id}'")
            except Exception as e:
                print(f"Memory: Error loading LT '{session_id}': {e}")
                print(f"Memory: Deleting corrupted long-term file '{path}'")
                try:
                    os.remove(path)
                except:
                    pass
                self.long_term_memories[session_id] = []
        else:
            self.long_term_memories[session_id] = []

    def _save_session(self, session_id: str):
        path = self._get_st_path(session_id)
        try:
            with open(path, "w", encoding="utf-8") as f:
                json.dump(self.sessions[session_id], f, ensure_ascii=False, indent=2, cls=CustomJSONEncoder)
        except Exception as e:
            print(f"Memory: Error saving ST '{session_id}': {e}")

    def _save_long_term(self, session_id: str):
        path = self._get_lt_path(session_id)
        try:
            with open(path, "w", encoding="utf-8") as f:
                json.dump(self.long_term_memories[session_id], f, ensure_ascii=False, indent=2, cls=CustomJSONEncoder)
        except Exception as e:
            print(f"Memory: Error saving LT '{session_id}': {e}")

    def _ensure_session(self, session_id: str):
        if session_id not in self.sessions:
            self._load_session(session_id)
        if session_id not in self.long_term_memories:
            self._load_long_term(session_id)

    def get_messages(self, session_id: str) -> List[Dict[str, Any]]:
        self._ensure_session(session_id)
        return self.sessions[session_id]

    def get_long_term_context(self, session_id: str) -> str:
        """長期記憶（サマリー）を結合してテキストとして取得する"""
        self._ensure_session(session_id)
        summaries = self.long_term_memories.get(session_id, [])
        if not summaries:
            return ""
        return "\n---\n".join(summaries)

    def add_long_term_summary(self, session_id: str, summary: str):
        """長期記憶にサマリーを追加し保存する"""
        self._ensure_session(session_id)
        if session_id not in self.long_term_memories:
            self.long_term_memories[session_id] = []
        
        # サマリーに作成日時を付与
        now = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        timestamped_summary = f"[{now} JST] {summary}"
        self.long_term_memories[session_id].append(timestamped_summary)
        self._save_long_term(session_id)

    def add_message(self, session_id: str, role: str, content: str = None, **kwargs):
        self._ensure_session(session_id)
        # JSTタイムスタンプを付与
        now = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        msg = {"role": role, "timestamp": now}
        if content is not None:
            msg["content"] = recursive_sanitize(content)
        # kwargs も sanitize する (tool_calls など)
        sanitized_kwargs = recursive_sanitize(kwargs)
        msg.update(sanitized_kwargs)
        self.sessions[session_id].append(msg)
        self._save_session(session_id)

        # RAG 用にインデックス登録
        if vector_store and role in ["user", "assistant"]:
            msg_id = str(uuid.uuid4())
            vector_store.add_message(
                session_id=session_id,
                message_id=msg_id,
                text=content or "",
                metadata={"role": role, "timestamp": now}
            )

    def add_raw_message(self, session_id: str, message_dict: Dict[str, Any]):
        self._ensure_session(session_id)
        # JSTタイムスタンプを付与
        if "timestamp" not in message_dict:
            now = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
            message_dict["timestamp"] = now
        else:
            now = message_dict["timestamp"]

        sanitized_msg = recursive_sanitize(message_dict)
        self.sessions[session_id].append(sanitized_msg)
        self._save_session(session_id)

        # RAG 用にインデックス登録
        if vector_store:
            role = sanitized_msg.get("role")
            content = sanitized_msg.get("content")
            if role in ["user", "assistant"] and content:
                msg_id = str(uuid.uuid4())
                vector_store.add_message(
                    session_id=session_id,
                    message_id=msg_id,
                    text=content,
                    metadata={"role": role, "timestamp": now}
                )

    def clear(self, session_id: str):
        """短期記憶のみをクリアする（長期記憶は維持）"""
        self.sessions[session_id] = []
        path = self._get_st_path(session_id)
        if os.path.exists(path):
            try:
                os.remove(path)
                print(f"Memory: Deleted ST session file '{session_id}.json'")
            except Exception as e:
                print(f"Memory: Error deleting ST file: {e}")

    def clear_all(self, session_id: str):
        """短期・長期両方の記憶をクリアする"""
        self.clear(session_id)
        self.long_term_memories[session_id] = []
        path = self._get_lt_path(session_id)
        if os.path.exists(path):
            try:
                os.remove(path)
                print(f"Memory: Deleted LT session file '{session_id}.json'")
            except Exception as e:
                print(f"Memory: Error deleting LT file: {e}")
                
    def get_relevant_history(self, session_id: str, query: str, n_results: int = 5) -> str:
        """現在のクエリに関連する過去の履歴をベクトルDBから取得する"""
        if not vector_store:
            return ""
        
        hits = vector_store.search_similar(session_id, query, n_results=n_results)
        if not hits:
            return ""
            
        context_parts = ["(あなたが思い出した記憶の断片:)"]
        for hit in hits:
            role = hit["metadata"].get("role", "unknown")
            ts = hit["metadata"].get("timestamp", "Unknown Time")
            # 簡潔な形式で履歴を提示
            context_parts.append(f"[{ts}] {role}: {hit['text']}")
        
        return "\n".join(context_parts)

# シングルトン
memory = Memory()
