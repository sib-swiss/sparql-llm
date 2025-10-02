# /// script
# requires-python = ">=3.9"
# dependencies = ["mcp", "langchain-mcp-adapters", "langchain >=1.0.0a10", "langchain-mistralai"]
# ///

import asyncio

from langchain.agents import create_agent
from langchain_mcp_adapters.client import MultiServerMCPClient
from mcp import ClientSession
from mcp.client.streamable_http import streamablehttp_client

mcp_url = "http://localhost:8888/mcp"


async def main():
    # Use official MCP SDK client
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

    # Use LangChain built-in agent
    client = MultiServerMCPClient(
        {
            "biodata": {
                "transport": "streamable_http",
                "url": mcp_url,
            }
        }
    )
    tools = await client.get_tools()
    agent = create_agent("mistralai:mistral-small-latest", tools)
    resp = await agent.ainvoke(
        {"messages": [{"role": "user", "content": "Get the uniprot ID for HBB by executing a SPARQL query."}]}
    )
    print(resp)


if __name__ == "__main__":
    asyncio.run(main())

# uv run --env-file .env --prerelease=allow mcp_client.py
