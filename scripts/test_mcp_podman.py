import asyncio
from core.mcp_integration import mcp_manager

async def test_mcp_podman():
    print("Testing MCP connection via podman...")
    command = "podman run -i --rm docker.io/library/steam-store-search-mcp-mcp-server:latest"
    result = await mcp_manager.connect_server("steam_test", command)
    print("Result:")
    print(result)

if __name__ == "__main__":
    asyncio.run(test_mcp_podman())
