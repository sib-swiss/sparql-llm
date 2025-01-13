import pytest

from expasy_agent import graph

# from langsmith import unit

# @unit
@pytest.mark.asyncio
async def test_expasy_agent_simple_passthrough() -> None:
    res = await graph.ainvoke(
        {"messages": [("user", "Who is the founder of LangChain?")]},
        {"configurable": {"system_prompt": "You are a helpful AI assistant."}},
    )

    assert "harrison" in str(res["messages"][-1].content).lower()
