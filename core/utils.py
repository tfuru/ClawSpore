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

async def is_url_reachable(url: str) -> bool:
    """
    指定された URL が実在するかどうかを確認する。
    """
    import httpx
    import re
    import urllib3

    # SSL 警告の抑制
    urllib3.disable_warnings()

    # URL 形式の簡易チェック
    if not re.match(r'https?://[\w/:%#\$&\?\(\)~\.=\+\-]+', url):
        return False

    try:
        # User-Agent を設定して通常のブラウザを装う（ブロック回避）
        headers = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"}
        
        async with httpx.AsyncClient(follow_redirects=True, verify=False, headers=headers) as client:
            # 高速化のため HEAD リクエストを試行
            response = await client.head(url, timeout=5.0)
            if response.is_success:
                return True
            
            # HEAD が許可されていない場合（405等）は GET を試行
            if 400 <= response.status_code < 500:
                response = await client.get(url, timeout=5.0)
                return response.is_success
            
            return False
    except Exception as e:
        print(f"DEBUG: URL check failed for {url}: {e}")
        return False

def install_package(package_name: str) -> bool:
    """
    指定された Python パッケージを pip でインストールする。
    """
    import subprocess
    import sys
    try:
        print(f"Utils: Installing package '{package_name}'...")
        subprocess.check_call([sys.executable, "-m", "pip", "install", package_name])
        return True
    except Exception as e:
        print(f"Utils: Error installing package {package_name}: {e}")
        return False
