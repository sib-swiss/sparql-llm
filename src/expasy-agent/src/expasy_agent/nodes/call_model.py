"""Node to call the model to solve the user question given the context previosuly extracted.

Works with a chat model with tool calling support.
"""

from typing import Any, Dict, List

from langchain_core.messages import AIMessage, ToolMessage, FunctionMessage
from langchain_core.messages.base import BaseMessage
from langchain_core.prompts import ChatPromptTemplate
from langchain_core.runnables import RunnableConfig

from expasy_agent.config import Configuration, settings
from expasy_agent.nodes.tools import TOOLS
from expasy_agent.state import State
from expasy_agent.utils import load_chat_model

# from expasy_agent.nodes.retrieval_docs import format_docs
# from expasy_agent.nodes.retrieval_entities import format_extracted_entities

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
    # model = load_chat_model(configuration).bind_tools(TOOLS)
    model = load_chat_model(configuration).bind_tools(TOOLS) if settings.use_tools else load_chat_model(configuration)

    structured_prompt: dict[str, Any] = {
        "messages": state.messages,
    }
    # structured_prompt["retrieved_docs"] = format_docs(state.retrieved_docs)
    # if configuration.enable_entities_resolution:
    #     structured_prompt["extracted_entities"] = format_extracted_entities(state.extracted_entities)
    # else:
    #     structured_prompt["extracted_entities"] = ""

    prompt_template = ChatPromptTemplate.from_messages(
        [
            ("system", configuration.system_prompt),
            ("placeholder", "{messages}"),
        ]
    )
    message_value = prompt_template.invoke(structured_prompt, config)
    # print(message_value.messages[0].content)
    response_msg: BaseMessage = model.invoke(message_value, config)

    # Check if the current response contains tool calls that should be processed
    if response_msg.tool_calls and not state.is_last_step:
        return {"messages": [response_msg], "passed_validation": False}

    # TODO: improve the tool use with a supervizor node that check if tool calls are needed or stop
    # last_msg = state.messages[-1]
    # if isinstance(last_msg, (ToolMessage, FunctionMessage)) and last_msg.name in ["access_biomedical_resources", "execute_sparql_query"]:
    #     # If the last message is from one of these tools, we need to check if the response
    #     # might require further tool calls, regardless of whether it explicitly has tool_calls
    #     # This handles cases where output from previous tool calls might trigger a need for more tools
    #     return {"messages": [response_msg], "passed_validation": False}

    # Handle the case when it's the last step and the model still wants to use a tool
    if state.is_last_step and response_msg.tool_calls:
        print("IS_LAST_STEP reached")
        return {
            "messages": [
                AIMessage(
                    id=response_msg.id,
                    content="Sorry, I could not find an answer to your question in the specified number of steps.",
                )
            ]
        }
    # Return the model response as a list to be added to existing messages
    return {"messages": [response_msg], "passed_validation": True}
