import asyncio
import os
import sys

sys.path.append(os.getcwd())

from core.tools.file_ops import WriteFileTool, ReadFileTool, ListFilesTool

async def test():
    print("--- テスト開始 ---")
    
    write_tool = WriteFileTool()
    print("\n1. 書き込みテスト...")
    res = await write_tool.execute('sample.txt', 'Hello Test', session_id='test_session_1')
    print("結果:", repr(res))
    
    read_tool = ReadFileTool()
    print("\n2. 読み込みテスト...")
    res2 = await read_tool.execute('sample.txt', session_id='test_session_1')
    print("結果:", repr(res2))
    
    ls_tool = ListFilesTool()
    print("\n3. LSテスト...")
    res3 = await ls_tool.execute('.', session_id='test_session_1')
    print("結果:", repr(res3))

if __name__ == "__main__":
    asyncio.run(test())
