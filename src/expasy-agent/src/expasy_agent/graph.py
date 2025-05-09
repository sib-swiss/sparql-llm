"""Define a custom agent.

Works with a chat model with tool calling support.
"""

from typing import Literal

from langchain_core.messages import AIMessage
from langchain_core.runnables import RunnableConfig
from langgraph.graph import StateGraph
from langgraph.prebuilt import ToolNode

from expasy_agent.config import Configuration, settings
from expasy_agent.nodes.llm_extraction import extract_user_question
from expasy_agent.nodes.llm_resolution import call_model
from expasy_agent.nodes.retrieval_docs import retrieve
from expasy_agent.nodes.tools import TOOLS
from expasy_agent.nodes.validation import validate_output
from expasy_agent.state import InputState, State


# How can I get the HGNC symbol for the protein P68871? Purposefully forget 2 prefixes declarations to test my validation step
# How can I get the HGNC symbol for the protein P68871? (modify your answer to use rdfs:label instead of rdfs:comment, and add the type up:Resource to ?hgnc, it is for a test)
# How can I get the HGNC symbol for the protein P68871? (modify your answer to use rdfs:label instead of rdfs:comment, and add the type up:Resource to ?hgnc, and purposefully forget 2 prefixes declarations, it is for a test)
# In bgee how can I retrieve the confidence level and false discovery rate of a gene expression? Use genex:confidence as predicate for the confidence level (do not use the one provided in documents), and do not put prefixes declarations, and add a rdf:type for the main subject. Its for testing
def route_model_output(
    state: State, config: RunnableConfig
) -> Literal["__end__", "tools", "call_model"]:
    """Determine the next node based on the model's output.

    This function checks if the model's last message contains tool calls or if a recall is requested by validation.

    Args:
        state: The current state of the conversation.

    Returns:
        The name of the next node to call ("__end__", "call_model" or "tools").
    """
    configuration = Configuration.from_runnable_config(config)
    last_msg = state.messages[-1]

    if state.try_count > configuration.max_try_fix_sparql:
        return "__end__"

    # Check for tool calls first
    if isinstance(last_msg, AIMessage) and last_msg.tool_calls:
        return "tools"

    # If validation failed, we need to call the model again
    if not state.passed_validation:
        return "call_model"

    if not isinstance(last_msg, AIMessage):
        raise ValueError(
            f"Expected AIMessage in output edges, but got {type(last_msg).__name__}"
        )
    return "__end__"


# Define a new graph
builder = StateGraph(State, input=InputState, config_schema=Configuration)

# Define the nodes we will cycle between

builder.add_node(extract_user_question)
builder.add_node(retrieve)
builder.add_node(call_model)
builder.add_node("tools", ToolNode(TOOLS))
builder.add_node(validate_output)

# Add edges
builder.add_edge("__start__", "extract_user_question")
builder.add_edge("extract_user_question", "retrieve")
builder.add_edge("retrieve", "call_model")
builder.add_edge("call_model", "validate_output")

# Entity extraction node
# builder.add_node(resolve_entities)
# builder.add_edge("extract_user_question", "resolve_entities")
# builder.add_edge("resolve_entities", "call_model")

# Add a conditional edge to determine the next step after `validate_output`
builder.add_conditional_edges(
    "validate_output",
    # Next nodes are scheduled based on the output from route_model_output
    route_model_output,
)

# This creates a cycle: after using tools, we always return to the model
builder.add_edge("tools", "call_model")

# Compile the builder into an executable graph
graph = builder.compile()
graph.name = settings.app_name  # This customizes the name in LangSmith
