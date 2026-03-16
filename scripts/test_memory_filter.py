import sys
import os

# プロジェクトルートをパスに追加
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from core.memory import memory

def test_filter():
    print("--- RAG Memory Filter Test ---")
    
    # 1. 正常なテキスト
    normal_text = "こんにちは、ころねぽちの動画を探して。"
    cleaned = memory._clean_for_rag(normal_text)
    assert cleaned == normal_text, f"Failed normal text: {cleaned}"
    print("✅ Normal text preserved.")

    # 2. Traceback 単体
    traceback_text = "エラーが発生しました。\n--- Traceback ---\nFile 'xxx.py', line 10...\nImportError: module not found\n\n続きのメッセージ。"
    cleaned = memory._clean_for_rag(traceback_text)
    assert "[Traceback omitted]" in cleaned
    assert "ImportError" not in cleaned
    print("✅ Traceback filtered.")

    # 3. Traceback と Source Code の複合 (registry.py の形式)
    complex_text = "❌ Error executing tool 'test': error\n--- Traceback ---\nstack trace here\n--- Tool Source Code (test) ---\ndef test(): pass\nPlease analyze the error."
    cleaned = memory._clean_for_rag(complex_text)
    assert "[Technical error details omitted]" in cleaned
    assert "stack trace here" not in cleaned
    assert "def test()" not in cleaned
    assert "Please analyze the error." in cleaned
    print("✅ Complex error components filtered.")

    # 4. ソースコード単体
    source_only = "ソースです。\n--- Tool Source Code (abc) ---\nprint('hello')\n\n終わり。"
    cleaned = memory._clean_for_rag(source_only)
    assert "[Source code omitted]" in cleaned
    assert "print('hello')" not in cleaned
    print("✅ Source code only filtered.")

    print("\n🎉 All filter tests passed!")

if __name__ == "__main__":
    test_filter()
