from expasy_agent.config import Configuration


def test_configuration_empty() -> None:
    conf = Configuration.from_runnable_config({})
    assert len(conf.model) > 0


# import pytest
# from expasy_agent.graph import graph
# @pytest.mark.asyncio
# async def test_expasy_agent_simple_passthrough() -> None:
#     res = await graph.ainvoke(
#         {"messages": [("user", "Who is the founder of LangChain?")]},
#         {"configurable": {"system_prompt": "You are a helpful AI assistant."}},
#     )
#     assert "harrison" in str(res["messages"][-1].content).lower()
