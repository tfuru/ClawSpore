import json
import base64
from typing import Any

def recursive_sanitize(obj: Any, parent_key: str = None) -> Any:
    """
    再帰的に JSON シリアライズ不能なオブジェクトをクリーンアップし、JSON 安全な形式に変換する。
    - bytes: 文字列または Base64 化
    - callable (method/function): 名前を文字列化
    - dict: 各要素を再帰的にサニタイズ（プライベートキー '_' 始まりは除外）
    - list/tuple: 各要素を再帰的にサニタイズ
    - Class instances: to_dict() や model_dump() があれば実行、なければ __dict__ を使用、それもなければ文字列化
    """
    if obj is None:
        return None
        
    if isinstance(obj, (int, float, bool, str)):
        return obj

    if isinstance(obj, bytes):
        # critical: thought_signature は絶対にデコードせず Base64 化する
        if parent_key == "thought_signature":
            return f"base64:{base64.b64encode(obj).decode('ascii')}"
        try:
            return obj.decode('utf-8')
        except:
            return f"base64:{base64.b64encode(obj).decode('ascii')}"
            
    if callable(obj):
        # メソッドや関数が混入している場合は、その名前（または文字列表現）にする
        return str(obj)

    if isinstance(obj, dict):
        return {str(k): recursive_sanitize(v, parent_key=str(k)) for k, v in obj.items() if not str(k).startswith("_")}
    
    if isinstance(obj, (list, tuple)):
        return [recursive_sanitize(i, parent_key=parent_key) for i in obj]
    
    # OpenAI/Pydantic オブジェクトなどの Class Instance 対策
    if hasattr(obj, "to_dict") and callable(obj.to_dict):
        return recursive_sanitize(obj.to_dict(), parent_key=parent_key)
    if hasattr(obj, "model_dump") and callable(obj.model_dump):
        return recursive_sanitize(obj.model_dump(), parent_key=parent_key)
    if hasattr(obj, "__dict__"):
        return recursive_sanitize(obj.__dict__, parent_key=parent_key)

    # 最終手段: JSON シリアライズを試みる
    try:
        # dict はすでに上で処理されているはずだが、念のためここでも型チェックして保護
        if isinstance(obj, dict):
            return {str(k): recursive_sanitize(v, parent_key=str(k)) for k, v in obj.items() if not str(k).startswith("_")}
        
        json.dumps(obj)
        return obj
    except (TypeError, OverflowError):
        # メソッドなどは文字列にするが、dict は絶対に文字列にしない
        if isinstance(obj, dict):
             return {str(k): recursive_sanitize(v, parent_key=str(k)) for k, v in obj.items() if not str(k).startswith("_")}
        return str(obj)
