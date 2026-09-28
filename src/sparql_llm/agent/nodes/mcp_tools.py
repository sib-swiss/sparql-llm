"""Custom MCP tool node for handling async tool calls."""

from typing import Any

from langchain_core.messages import AIMessage, ToolMessage
from langchain_core.runnables import RunnableConfig
from mcp import Client
from mcp.types import CallToolResult, TextContent

from sparql_llm.agent.state import State
from sparql_llm.config import settings

# NOTE: experimental, not actually used by the chat agent

# The MCP app is mounted at /mcp and serves at its root
MCP_URL = f"{settings.server_url}/mcp/"


async def get_mcp_tools() -> list[dict[str, Any]]:
    """List the MCP server tools, in the OpenAI function format accepted by `bind_tools`."""
    async with Client(MCP_URL) as client:
        tools = await client.list_tools()
    return [
        {
            "type": "function",
            "function": {"name": tool.name, "description": tool.description or "", "parameters": tool.input_schema},
        }
        for tool in tools.tools
    ]


def format_tool_result(result: CallToolResult) -> str:
    """Join the text content blocks of a tool call result."""
    return "\n".join(item.text if isinstance(item, TextContent) else str(item) for item in result.content)


async def mcp_tools_node(state: State, config: RunnableConfig) -> dict[str, list[ToolMessage]]:
    """Handle MCP tool calls asynchronously.

    Args:
        state: The current state of the conversation.
        config: The runnable configuration.

    Returns:
        Dictionary with tool messages.
    """
    # Get the last message which should contain tool calls
    last_msg = state.messages[-1]

    if not isinstance(last_msg, AIMessage) or not last_msg.tool_calls:
        # No tool calls to process
        return {"messages": []}

    tool_messages = []
    async with Client(MCP_URL) as mcp_client:
        # Process each tool call
        for tool_call in last_msg.tool_calls:
            print(tool_call)
            try:
                # Execute the tool via MCP client, and pass its text output back to the model
                result = await mcp_client.call_tool(tool_call["name"], tool_call.get("args", {}))
                tool_messages.append(
                    ToolMessage(
                        content=format_tool_result(result),
                        tool_call_id=tool_call["id"],
                        status="error" if result.is_error else "success",
                    )
                )

            except Exception as e:
                # Handle tool execution errors
                print(f"Error executing tool '{tool_call['name']}': {e!s}")
                tool_messages.append(
                    ToolMessage(
                        content=f"Error executing tool '{tool_call['name']}': {e!s}",
                        tool_call_id=tool_call["id"],
                    )
                )

    return {"messages": tool_messages}
