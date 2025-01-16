"""Node to call the model.

Works with a chat model with tool calling support.
"""

from typing import Dict, List

from langchain_core.messages import AIMessage
from langchain_core.messages.base import BaseMessage
from langchain_core.prompts import ChatPromptTemplate
from langchain_core.runnables import RunnableConfig

from expasy_agent.config import Configuration
from expasy_agent.nodes.retrieval import format_docs
from expasy_agent.nodes.tools import TOOLS
from expasy_agent.state import State
from expasy_agent.utils import load_chat_model


async def call_model(state: State, config: RunnableConfig) -> Dict[str, List[AIMessage]]:
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
    # print(message_value)
    response: BaseMessage = await model.ainvoke(message_value, config)

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

# # Another way to format the prompt
# system_message = configuration.system_prompt.format(
#     system_time=datetime.now(tz=timezone.utc).isoformat()
# )
# response = cast(
#     AIMessage,
#     await model.ainvoke(
#         [{"role": "system", "content": system_message}, *state.messages], config
#     ),
# )
