# /// script
# requires-python = ">=3.10"
# dependencies = ["mcp >=2.2.0"]
# ///

import asyncio

from mcp import Client


async def main():
    mcp_url = "http://localhost:8888/mcp"
    # mcp_url = "http://localhost:8000/mcp/"
    async with Client(mcp_url) as client:
        # List available tools
        tools = await client.list_tools()
        print(f"Available tools: {[tool.name for tool in tools.tools]}")


if __name__ == "__main__":
    asyncio.run(main())
