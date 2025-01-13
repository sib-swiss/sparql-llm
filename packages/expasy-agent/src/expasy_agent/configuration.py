"""Define the configurable parameters for the agent."""

from __future__ import annotations

from dataclasses import dataclass, field, fields
from typing import Annotated, Any, Literal, Optional, Type, TypeVar

from langchain_core.runnables import RunnableConfig, ensure_config

from expasy_agent import prompts


@dataclass(kw_only=True)
class IndexConfiguration:
    """Configuration class for indexing and retrieval operations.

    This class defines the parameters needed for configuring the indexing and
    retrieval processes, including user identification, embedding model selection,
    retriever provider choice, and search parameters.
    """

    vectordb_url: str = field(
        # default="http://vectordb:6334/",
        default="http://localhost:6334/",
        metadata={"description": "URL for the vector store API, e.g. qdrant."},
    )
    collection_name: str = field(
        default="expasy",
        metadata={"description": "Name of collection, e.g. for qdrant."},
    )
    sparse_embedding_model: str = field(
        default="Qdrant/bm25",
        metadata={"description": "Sparse embedding model supported by FastEmbed."},
    )
    embedding_model: Annotated[
        str,
        {"__template_metadata__": {"kind": "embeddings"}},
    ] = field(
        default="BAAI/bge-large-en-v1.5",
        metadata={
            "description": "Name of the embedding model to use. Must be a valid embedding model name supported by FastEmbed."
        },
    )

    retriever_provider: Annotated[
        Literal["qdrant", "elastic", "elastic-local", "pinecone", "mongodb"],
        {"__template_metadata__": {"kind": "retriever"}},
    ] = field(
        default="qdrant",
        metadata={
            "description": "The vector store provider to use for retrieval. Options are 'qdrant', 'elastic', 'pinecone', or 'mongodb'."
        },
    )

    search_kwargs: dict[str, Any] = field(
        default_factory=lambda: {"k": 15},
        # default_factory=dict,
        metadata={
            "description": "Additional keyword arguments to pass to the search function of the retriever."
        },
    )

    # user_id: str = field(metadata={"description": "Unique identifier for the user."})

    @classmethod
    def from_runnable_config(
        cls: Type[T], config: Optional[RunnableConfig] = None
    ) -> T:
        """Create an IndexConfiguration instance from a RunnableConfig object.

        Adds defaults values to the configurable.

        Args:
            cls (Type[T]): The class itself.
            config (Optional[RunnableConfig]): The configuration object to use.

        Returns:
            T: An instance of IndexConfiguration with the specified configuration.
        """
        config = ensure_config(config)
        configurable = config.get("configurable") or {}
        _fields = {f.name for f in fields(cls) if f.init}
        return cls(**{k: v for k, v in configurable.items() if k in _fields})


T = TypeVar("T", bound=IndexConfiguration)


@dataclass(kw_only=True)
class Configuration(IndexConfiguration):
    """The configuration for the agent."""

    system_prompt: str = field(
        default=prompts.SYSTEM_PROMPT,
        metadata={
            "description": "The system prompt to use for the agent's interactions. "
            "This prompt sets the context and behavior for the agent."
        },
    )

    model: Annotated[str, {"__template_metadata__": {"kind": "llm"}}] = field(
        # default="anthropic/claude-3-5-sonnet-20240620",
        default="openai/gpt-4o",
        # default="openai/gpt-4o-mini",
        metadata={
            "description": "The name of the language model to use for the agent's main interactions. "
            "Should be in the form: provider/model-name."
        },
    )

    max_try_fix_sparql: int = field(
        default=3,
        metadata={
            "description": "The maximum number of tries when calling the model to fix a SPARQL query."
        },
    )
