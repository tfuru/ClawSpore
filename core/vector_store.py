import os
import chromadb
from typing import List, Dict, Any

class VectorStore:
    def __init__(self, persist_directory: str = "core/data/vector_db"):
        self.persist_directory = persist_directory
        os.makedirs(persist_directory, exist_ok=True)
        
        self.client = chromadb.PersistentClient(path=persist_directory)
        # セッションごとにコレクションを分けるか、一つのコレクションで metadata でフィルタリングするか
        # ここでは後者 (単一コレクション 'clawspore_memories') を採用
        self.collection = self.client.get_or_create_collection(name="clawspore_memories")

    def add_message(self, session_id: str, message_id: str, text: str, metadata: Dict[str, Any] = None):
        """メッセージをベクトルDBに追加する"""
        if not text:
            return
            
        final_metadata = metadata or {}
        final_metadata["session_id"] = session_id
        
        self.collection.add(
            documents=[text],
            metadatas=[final_metadata],
            ids=[message_id]
        )

    def search_similar(self, session_id: str, query: str, n_results: int = 5) -> List[Dict[str, Any]]:
        """関連するメッセージを検索する"""
        if not query:
            return []
            
        results = self.collection.query(
            query_texts=[query],
            n_results=n_results,
            where={"session_id": session_id}
        )
        
        # 結果を整形
        hits = []
        if results["documents"]:
            for i in range(len(results["documents"][0])):
                hits.append({
                    "text": results["documents"][0][i],
                    "metadata": results["metadatas"][0][i] if results["metadatas"] else {},
                    "distance": results["distances"][0][i] if results["distances"] else 0
                })
        return hits

    def clear_session(self, session_id: str):
        """特定のセッションの記憶を削除する"""
        self.collection.delete(where={"session_id": session_id})

# シングルトン
vector_store = VectorStore()
