"""Custom MCP tool node for handling async tool calls."""

from langchain_core.messages import AIMessage, ToolMessage
from langchain_core.runnables import RunnableConfig
from langchain_mcp_adapters.client import MultiServerMCPClient

from sparql_llm.agent.state import State
from sparql_llm.config import settings

# NOTE: experimental, not actually used by the chat agent


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

    # Set up MCP client
    mcp_client = MultiServerMCPClient(
        {
            "expasy-mcp": {
                "url": f"{settings.server_url}/mcp",
                "transport": "streamable_http",
            }
        }
    )

    tool_messages = []
    async with mcp_client.session("expasy-mcp") as mcp_session:
        # Process each tool call
        for tool_call in last_msg.tool_calls:
            print(tool_call)
            try:
                # Execute the tool via MCP client
                # The langchain-mcp-adapters should handle the tool name mapping
                result = await mcp_session.call_tool(tool_call["name"], tool_call.get("args", {}))  # type: ignore
                print(result)

                # Create tool message with the result
                # The result from MCP client should have content accessible
                content = ""
                if hasattr(result, "content"):
                    if isinstance(result.content, list):
                        # Handle list of content items
                        content = "\n".join(str(item) for item in result.content)
                    else:
                        content = str(result.content)
                else:
                    content = str(result)

                tool_messages.append(
                    ToolMessage(
                        content=content,
                        tool_call_id=tool_call["id"],
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
