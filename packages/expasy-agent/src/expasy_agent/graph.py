"""Define a custom Reasoning and Action agent.

Works with a chat model with tool calling support.
"""

from typing import Dict, List, Literal

from langchain_core.messages import AIMessage
from langchain_core.messages.base import BaseMessage
from langchain_core.prompts import ChatPromptTemplate
from langchain_core.runnables import RunnableConfig
from langgraph.graph import StateGraph
from langgraph.prebuilt import ToolNode

from expasy_agent.configuration import Configuration
from expasy_agent.nodes.retrieval import format_docs, retrieve
from expasy_agent.nodes.tools import TOOLS
from expasy_agent.nodes.validation import validate_sparql
from expasy_agent.state import InputState, State
from expasy_agent.utils import load_chat_model


# Define the function that calls the model
async def call_model(
    state: State, config: RunnableConfig
) -> Dict[str, List[AIMessage]]:
    """Call the LLM powering our "agent".

    This function prepares the prompt, initializes the model, and processes the response.

    Args:
        state (State): The current state of the conversation.
        config (RunnableConfig): Configuration for the model run.

    Returns:
        dict: A dictionary containing the model's response message.
    """
    configuration = Configuration.from_runnable_config(config)
    # Initialize the model with tool binding
    model = load_chat_model(configuration.model).bind_tools(TOOLS)

    prompt = ChatPromptTemplate.from_messages(
        [
            ("system", configuration.system_prompt),
            ("placeholder", "{messages}"),
        ]
    )
    retrieved_docs = format_docs(state.retrieved_docs)
    message_value = await prompt.ainvoke(
        {
            "messages": state.messages,
            "retrieved_docs": retrieved_docs,
            # "system_time": datetime.now(tz=timezone.utc).isoformat(),
        },
        config,
    )
    response: BaseMessage = await model.ainvoke(message_value, config)

    # # Format the prompt
    # system_message = configuration.system_prompt.format(
    #     system_time=datetime.now(tz=timezone.utc).isoformat()
    # )
    # response = cast(
    #     AIMessage,
    #     await model.ainvoke(
    #         [{"role": "system", "content": system_message}, *state.messages], config
    #     ),
    # )

    # Handle the case when it's the last step and the model still wants to use a tool
    if state.is_last_step and response.tool_calls:
        return {
            "messages": [
                AIMessage(
                    id=response.id,
                    content="Sorry, I could not find an answer to your question in the specified number of steps.",
                )
            ]
        }
    # Return the model's response as a list to be added to existing messages
    return {"messages": [response]}


# How can I get the HGNC symbol for the protein P68871? Purposefully forget 2 prefixes declarations to test my validation step
# In bgee how can I retrieve the confidence level and false discovery rate of a gene expression? Use genex:confidence as predicate for the confidence level (do not use the one provided in documents), and do not put prefixes declarations. its for testing
def route_model_output(state: State) -> Literal["__end__", "tools", "call_model"]:
    """Determine the next node based on the model's output.

    This function checks if the model's last message contains tool calls.

    Args:
        state (State): The current state of the conversation.

    Returns:
        str: The name of the next node to call ("__end__" or "tools").
    """
    last_msg = state.messages[-1]
    if not isinstance(last_msg, AIMessage):
        raise ValueError(
            f"Expected AIMessage in output edges, but got {type(last_msg).__name__}"
        )
    # Check for tool calls first
    if last_msg.tool_calls:
        return "tools"
    # Check if recall requested by validate_sparql
    if last_msg.name == "recall-model":
        return "call_model"
    return "__end__"


# Define a new graph
builder = StateGraph(State, input=InputState, config_schema=Configuration)

# Define the nodes we will cycle between
builder.add_node(retrieve)
builder.add_node(call_model)
builder.add_node("tools", ToolNode(TOOLS))
builder.add_node(validate_sparql)

# Add edges
builder.add_edge("__start__", "retrieve")
builder.add_edge("retrieve", "call_model")
builder.add_edge("call_model", "validate_sparql")

# Add a conditional edge to determine the next step after `validate_sparql`
builder.add_conditional_edges(
    "validate_sparql",
    # Next nodes are scheduled based on the output from route_model_output
    route_model_output,
)

# This creates a cycle: after using tools, we always return to the model
builder.add_edge("tools", "call_model")

# Compile the builder into an executable graph
# You can customize this by adding interrupt points for state updates
graph = builder.compile(
    interrupt_before=[],  # Add node names here to update state before they're called
    interrupt_after=[],  # Add node names here to update state after they're called
)
graph.name = "Expasy Agent"  # This customizes the name in LangSmith

# TODO: integrate langgraph in FastAPI https://github.com/JoshuaC215/agent-service-toolkit/blob/main/src/service/service.py
