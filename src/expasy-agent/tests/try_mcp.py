# /// script
# requires-python = ">=3.9"
# dependencies = ["mcp"]
# ///

import asyncio

from mcp import ClientSession
from mcp.client.streamable_http import streamablehttp_client


async def main():
    mcp_url = "http://localhost:8888/mcp"
    # mcp_url = "http://localhost:8000/mcp/mcp"
    async with (
        streamablehttp_client(mcp_url) as (
            read_stream,
            write_stream,
            _,
        ),
        ClientSession(read_stream, write_stream) as session,
    ):
        # Initialize the connection
        await session.initialize()
        # List available tools
        tools = await session.list_tools()
        print(f"Available tools: {[tool.name for tool in tools.tools]}")


if __name__ == "__main__":
    asyncio.run(main())
