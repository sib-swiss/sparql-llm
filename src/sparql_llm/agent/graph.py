"""Define a custom agent.

Works    max_tries_message = AIMessage(
        content=f"I've reached the maximum number of attempts ({configuration.max_try_fix_sparql}) to fix the SPARQL query. "
        "The query may have complex validation issues that require manual review. "
        "Please check the query syntax and try rephrasing your question."
    ) a chat model with tool calling support.
"""

from typing import Literal

from langchain_core.messages import AIMessage
from langchain_core.runnables import RunnableConfig
from langgraph.graph import StateGraph

from sparql_llm.agent.nodes.call_model import call_model
from sparql_llm.agent.nodes.llm_extraction import extract_user_question
from sparql_llm.agent.nodes.mcp_tools import mcp_tools_node
from sparql_llm.agent.nodes.retrieval_docs import retrieve
from sparql_llm.agent.nodes.validation import validate_output
from sparql_llm.agent.state import InputState, State
from sparql_llm.config import Configuration, settings

# from sparql_llm.agent.nodes.tools import TOOLS


# How can I get the HGNC symbol for the protein P68871? Purposefully forget 2 prefixes declarations to test my validation step
# How can I get the HGNC symbol for the protein P68871? (modify your answer to use rdfs:label instead of rdfs:comment, and add the type up:Resource to ?hgnc, it is for a test)
# How can I get the HGNC symbol for the protein P68871? (modify your answer to use rdfs:label instead of rdfs:comment, and add the type up:Resource to ?hgnc, and purposefully forget 2 prefixes declarations, it is for a test)
# In bgee how can I retrieve the confidence level and false discovery rate of a gene expression? Use genex:confidence as predicate for the confidence level (do not use the one provided in documents), and do not put prefixes declarations, and add a rdf:type for the main subject. Its for testing
def route_model_output(
    state: State, config: RunnableConfig
) -> Literal["__end__", "call_model", "max_tries_reached"]:  # , "tools"
    """Determine the next node based on the model's output.

    This function checks if the model's last message contains tool calls or if a recall is requested by validation.

    Args:
        state: The current state of the conversation.

    Returns:
        The name of the next node to call ("__end__", "call_model", "tools", or "max_tries_reached").
    """
    configuration = Configuration.from_runnable_config(config)
    # last_msg = state.messages[-1]
    # print(state.messages)

    if state.try_count > configuration.max_try_fix_sparql:
        # print("TRY COUNT EXCEEDED", state.try_count)
        return "max_tries_reached"

    # # Check for tool calls first
    # if isinstance(last_msg, AIMessage) and last_msg.tool_calls:
    #     return "tools"

    # If validation failed, we need to call the model again
    if not state.passed_validation:
        return "call_model"

    # if not isinstance(last_msg, AIMessage):
    #     raise ValueError(
    #         f"Expected AIMessage in output edges, but got {type(last_msg).__name__}"
    #     )
    return "__end__"


def max_tries_reached(state: State, config: RunnableConfig) -> dict[str, list[AIMessage]]:
    """Node that handles the case when maximum tries are reached.

    Args:
        state: The current state of the conversation.
        config: The runnable configuration.

    Returns:
        Dictionary with the max tries message.
    """
    configuration = Configuration.from_runnable_config(config)
    max_tries_message = AIMessage(
        content=f"I've reached the maximum number of attempts ({configuration.max_try_fix_sparql}) to fix the SPARQL query. "
        "The query may have complex validation issues that require manual review. "
        "Please check the query syntax and try to execute it."
    )
    return {"messages": [max_tries_message]}


# Define the nodes we will cycle between
# https://github.com/langchain-ai/react-agent/blob/main/src/react_agent/graph.py
builder: StateGraph[State, Configuration, InputState, State] = StateGraph(
    State, context_schema=Configuration, input_schema=InputState
)
# builder = StateGraph(State, input=InputState, config_schema=Configuration)
builder.add_node(extract_user_question)
builder.add_node(retrieve)
builder.add_node(call_model)
builder.add_node(validate_output)
builder.add_node(max_tries_reached)

# Add edges depending on whether tools are used or not
if settings.use_tools:
    # builder.add_node("tools", ToolNode(tools))
    builder.add_node("tools", mcp_tools_node)
    builder.add_edge("__start__", "call_model")
    builder.add_conditional_edges(
        "call_model",
        # Next nodes are scheduled based on the output from route_model_output
        route_model_output,
    )
    # This creates a cycle: after using tools, we always return to the model
    builder.add_edge("tools", "call_model")
    # Add edge from max_tries_reached to end
    builder.add_edge("max_tries_reached", "__end__")
    pass
else:
    # When not using tools (default behavior)
    builder.add_edge("__start__", "extract_user_question")
    builder.add_edge("extract_user_question", "retrieve")
    builder.add_edge("retrieve", "call_model")
    builder.add_edge("call_model", "validate_output")
    # Add a conditional edge to determine the next step after `validate_output`
    builder.add_conditional_edges(
        "validate_output",
        # Next nodes are scheduled based on the output from route_model_output
        route_model_output,
    )
    # Add edge from max_tries_reached to end
    builder.add_edge("max_tries_reached", "__end__")

# Entity extraction node
# builder.add_node(resolve_entities)
# builder.add_edge("extract_user_question", "resolve_entities")
# builder.add_edge("resolve_entities", "call_model")

# Compile the builder into an executable graph
graph = builder.compile()
graph.name = settings.app_name
