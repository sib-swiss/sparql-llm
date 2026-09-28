"""Utilities for the AI agent, e.g. load model."""

import os
from typing import Any

from langchain.chat_models import init_chat_model
from langchain_core.language_models import BaseChatModel
from langchain_core.messages import AnyMessage
from langchain_openai import ChatOpenAI
from pydantic import SecretStr

from sparql_llm.config import Configuration


def load_chat_model(configuration: Configuration) -> BaseChatModel:
    """Load a chat model from a fully specified name.

    Args:
        fully_specified_name (str): String in the format 'provider/model'.
    """
    provider, model_name = configuration.model.split("/", maxsplit=1)
    if provider == "openrouter":
        # https://openrouter.ai/docs/community/lang-chain
        return ChatOpenAI(
            base_url="https://openrouter.ai/api/v1",
            model=model_name,
            temperature=configuration.temperature,
            api_key=SecretStr(os.getenv("OPENROUTER_API_KEY") or ""),
            seed=configuration.seed,
            # Include token usage in streamed responses, and ask OpenRouter for the cost of each call
            stream_usage=True,
            extra_body={"usage": {"include": True}},
            # default_headers={
            #     "HTTP-Referer": getenv("YOUR_SITE_URL"),
            #     "X-Title": getenv("YOUR_SITE_NAME"),
            # },
        )

    # if provider == "groq":
    #     # https://python.langchain.com/docs/integrations/chat/groq/
    #     from langchain_groq import ChatGroq

    #     return ChatGroq(
    #         model=model_name,
    #         max_tokens=configuration.max_tokens,
    #         temperature=configuration.temperature,
    #         timeout=None,
    #         max_retries=2,
    #     )
    # if provider == "together":
    #     # https://python.langchain.com/docs/integrations/chat/together/
    #     from langchain_together import ChatTogether
    #     return ChatTogether(
    #         model=model_name,
    #         max_tokens=configuration.max_tokens,
    #         temperature=configuration.temperature,
    #         timeout=None,
    #         max_retries=2,
    #     )
    # if provider == "hf":
    #     # https://python.langchain.com/docs/integrations/chat/huggingface/
    #     from langchain_huggingface import ChatHuggingFace, HuggingFaceEndpoint
    #     return ChatHuggingFace(
    #         llm=HuggingFaceEndpoint(
    #             # repo_id="HuggingFaceH4/zephyr-7b-beta",
    #             repo_id=model_name,
    #             task="text-generation",
    #             max_new_tokens=configuration.max_tokens,
    #             do_sample=False,
    #             repetition_penalty=1.03,
    #         )
    #     )
    # if provider == "azure":
    #     # https://learn.microsoft.com/en-us/azure/ai-studio/how-to/develop/langchain
    #     from langchain_azure_ai.chat_models import AzureAIChatCompletionsModel
    #     return AzureAIChatCompletionsModel(
    #         endpoint=settings.azure_inference_endpoint,
    #         credential=settings.azure_inference_credential,
    #         model_name=model_name,
    #     )
    # if provider == "deepseek":
    #     # https://python.langchain.com/docs/integrations/chat/deepseek/
    #     from langchain_deepseek import ChatDeepSeek
    #     return ChatDeepSeek(
    #         model=model_name,
    #         temperature=configuration.temperature,
    #     )
    return init_chat_model(
        model_name,
        model_provider=provider,
        max_tokens=configuration.max_tokens,
        temperature=configuration.temperature,
        timeout=None,
        max_retries=2,
        seed=configuration.seed,
        # reasoning={
        #     "effort": "low",  # 'low', 'medium', or 'high'
        #     "summary": "auto",  # 'detailed', 'auto', or None
        # },
    )


def get_msg_text(msg: AnyMessage) -> str:
    """Get the text content of a chat message."""
    content = msg.content
    if isinstance(content, str):
        return content
    elif isinstance(content, dict):
        return content.get("text", "")
    else:
        txts = [c if isinstance(c, str) else (c.get("text") or "") for c in content]
        return "".join(txts).strip()


def convert_chunk_to_dict(obj: Any) -> Any:
    """Recursively convert a langgraph chunk object to a dict.

    Required because LangGraph objects are not serializable by default.
    And they use a mix of tuples, dataclasses (State, Configuration) and pydantic BaseModel (BaseMessage).
    """
    # {'retrieve': {'retrieved_docs': [Document(metadata={'endpoint_url':
    # When sending a msg LangGraph sends a tuple with the message and the metadata
    if isinstance(obj, tuple) and len(obj) == 2:
        # Message and metadata
        return [convert_chunk_to_dict(obj[0]), convert_chunk_to_dict(obj[1])]
    elif isinstance(obj, list):
        return [convert_chunk_to_dict(item) for item in obj]
    elif isinstance(obj, dict):
        return {k: convert_chunk_to_dict(v) for k, v in obj.items()}
    elif hasattr(obj, "model_dump"):
        return obj.model_dump()  # type: ignore
    elif hasattr(obj, "dict"):
        return obj.dict()  # type: ignore
    elif hasattr(obj, "__dict__"):
        return obj.__dict__
    # elif hasattr(obj, "__dict__") and not isinstance(obj, type):
    #     # Convert dataclass or other objects to dict, but skip type objects
    #     return {k: convert_chunk_to_dict(v) for k, v in obj.__dict__.items()}
    else:
        return obj
