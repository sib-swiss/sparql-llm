"""Node to call the model.

Works with a chat model with tool calling support.
"""

from typing import Any, Dict, List

from langchain.chat_models import init_chat_model
from langchain_core.language_models import BaseChatModel
from langchain_core.messages import AIMessage
from langchain_core.messages.base import BaseMessage
from langchain_core.prompts import ChatPromptTemplate
from langchain_core.runnables import RunnableConfig

from expasy_agent.config import Configuration, settings
from expasy_agent.nodes.extraction import format_extracted_entities
from expasy_agent.nodes.retrieval import format_docs
from expasy_agent.nodes.tools import TOOLS
from expasy_agent.state import State


def load_chat_model(configuration: Configuration) -> BaseChatModel:
    """Load a chat model from a fully specified name.

    Args:
        fully_specified_name (str): String in the format 'provider/model'.
    """
    provider, model_name = configuration.model.split("/", maxsplit=1)
    if provider == "groq":
        from langchain_groq import ChatGroq
        return ChatGroq(
            model_name=model_name,
            temperature=configuration.temperature,
        )

    if provider == "deepseek":
        # https://python.langchain.com/docs/integrations/chat/deepseek/
        from langchain_deepseek import ChatDeepSeek
        return ChatDeepSeek(
            model=model_name,
            temperature=configuration.temperature,
        )

    if provider == "azure":
        # https://learn.microsoft.com/en-us/azure/ai-studio/how-to/develop/langchain
        from langchain_azure_ai.chat_models import AzureAIChatCompletionsModel
        return AzureAIChatCompletionsModel(
            endpoint=settings.azure_inference_endpoint,
            credential=settings.azure_inference_credential,
            model_name=model_name,
        )
    return init_chat_model(model_name, model_provider=provider)


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
    # model = load_chat_model(configuration).bind_tools(TOOLS)
    model = load_chat_model(configuration)

    structured_prompt: dict[str, Any] = {
        "messages": state.messages,
    }
    structured_prompt["retrieved_docs"] = format_docs(state.retrieved_docs)
    structured_prompt["extracted_entities"] = format_extracted_entities(state.extracted_entities)

    prompt_template = ChatPromptTemplate.from_messages([
        ("system", configuration.system_prompt),
        ("placeholder", "{messages}"),
    ])
    message_value = await prompt_template.ainvoke(structured_prompt, config)
    # print(message_value)
    # print(message_value.messages[0].content)
    response_msg: BaseMessage = await model.ainvoke(message_value, config)

    # Handle the case when it's the last step and the model still wants to use a tool
    if state.is_last_step and response_msg.tool_calls:
        return {
            "messages": [
                AIMessage(
                    id=response_msg.id,
                    content="Sorry, I could not find an answer to your question in the specified number of steps.",
                )
            ]
        }
    # Return the model response as a list to be added to existing messages
    return {"messages": [response_msg]}

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
