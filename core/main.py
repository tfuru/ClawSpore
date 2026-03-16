import asyncio
from dotenv import load_dotenv
from interface.discord_client import start_discord_bot
from core.tools.registry import tool_registry
from core.tools.file_ops import register_file_tools
from core.tools.meta_tools import register_meta_tools

load_dotenv()

async def main():
    print("クロウスポア Core 起動中...")
    print("自律判断システムを準備しています...")
    register_file_tools(tool_registry)
    register_meta_tools(tool_registry)
    print("ツールの登録を完了しました。")
    
    # 過去にAI自身が作成した動的ツールのロード
    tool_registry.load_dynamic_tools()
    # 永続化されたMCPサーバー設定の自動ロード
    from core.mcp_integration import mcp_manager
    await mcp_manager.load_servers()
    
    try:
        # 複数のタスクを並行して実行可能にする基盤
        await asyncio.gather(
            start_discord_bot(),
        )
    except asyncio.CancelledError:
        print("Core task was cancelled.")
    except Exception as e:
        print(f"An error occurred in Core: {e}")
    finally:
        print("クロウスポア Core 終了します。")

if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        pass
