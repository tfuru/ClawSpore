import asyncio
from limbs.executor import executor

async def test_executor():
    print("🏃 隔離コンテナ内でのコマンド実行テストを開始します...")
    
    # テスト1: 基本的なコマンド
    print("\n[Test 1] Simple echo:")
    result = await executor.execute_tool(["echo", "Hello from sandbox!"])
    print(f"Result: {result.strip()}")

    # テスト2: ネットワーク遮断の確認
    print("\n[Test 2] Network isolation check (ping):")
    result = await executor.execute_tool(["ping", "-c", "1", "google.com"])
    print(f"Result: {result.strip()}")

    # テスト3: システム情報の取得 (隔離されているか)
    print("\n[Test 3] System info (hostname):")
    result = await executor.execute_tool(["hostname"])
    print(f"Result: {result.strip()}")

if __name__ == "__main__":
    asyncio.run(test_executor())
