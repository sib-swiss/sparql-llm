"""Define the service settings and configurable parameters for the agent."""

from __future__ import annotations

from dataclasses import dataclass, field, fields
from typing import Annotated, Any, Optional, Type, TypeVar

from fastembed import TextEmbedding
from langchain_core.runnables import RunnableConfig, ensure_config
from openai import OpenAI
from pydantic_settings import BaseSettings, SettingsConfigDict
from qdrant_client import QdrantClient

from expasy_agent import prompts

# import warnings
# warnings.simplefilter(action="ignore", category=UserWarning)


class Settings(BaseSettings):
    """Define the service settings for the agent that can be set using environment variables."""

    # The list of endpoints that will be indexed and supported by the service
    endpoints: list[dict[str, str]] = [
        {
            # The label of the endpoint for clearer display
            "label": "UniProt",
            # The URL of the SPARQL endpoint from which most informations will be extracted
            "endpoint_url": "https://sparql.uniprot.org/sparql/",
            # Optional, homepage from which we can extract more information using the JSON-LD context
            # "homepage": "https://www.uniprot.org/",
            "ontology": "https://ftp.uniprot.org/pub/databases/uniprot/current_release/rdf/core.owl",
        },
        {
            "label": "Bgee",
            "endpoint_url": "https://www.bgee.org/sparql/",
            "homepage": "https://www.bgee.org/",
            "ontology": "http://purl.org/genex",
        },
        {
            "label": "Orthology MAtrix (OMA)",
            "endpoint_url": "https://sparql.omabrowser.org/sparql/",
            "homepage": "https://omabrowser.org/",
            "ontology": "http://purl.org/net/orth",
        },
        {
            "label": "HAMAP",
            "endpoint_url": "https://hamap.expasy.org/sparql/",
            "homepage": "https://hamap.expasy.org/",
        },
        {
            "label": "dbgi",
            "endpoint_url": "https://biosoda.unil.ch/graphdb/repositories/emi-dbgi",
            # "homepage": "https://dbgi.eu/",
        },
        {
            "label": "SwissLipids",
            "endpoint_url": "https://beta.sparql.swisslipids.org/",
            "homepage": "https://www.swisslipids.org",
        },
        {
            "label": "Rhea",
            "endpoint_url": "https://sparql.rhea-db.org/sparql/",
            "homepage": "https://www.rhea-db.org/",
        },
        # No metadata in these endpoints
        # {
        #     "label": "OrthoDB",
        #     "endpoint_url": "https://sparql.orthodb.org/sparql/",
        #     "homepage": "https://www.orthodb.org/",
        # },
        # {
        #     "label": "MetaNetx",
        #     "endpoint_url": "https://rdf.metanetx.org/sparql/",
        #     "homepage": "https://www.metanetx.org/",
        # },
        # Error querying NExtProt
        # {
        #     "label": "NextProt",
        #     # "endpoint_url": "https://api.nextprot.org/sparql",
        #     "endpoint_url": "https://sparql.nextprot.org",
        #     "homepage": "https://www.nextprot.org/",
        # },
        # {
        #     "label": "GlyConnect",
        #     "endpoint_url": "https://glyconnect.expasy.org/sparql",
        #     "homepage": "https://glyconnect.expasy.org/",
        # },
    ]

    # List of example questions to display in the chat UI
    example_questions: list[str] = [
        "Which resources are available at the SIB?",
        "How can I get the HGNC symbol for the protein P68871?",
        "What are the rat orthologs of the human TP53?",
        "Where is expressed the gene ACE2 in human?",
        "Anatomical entities where the INS zebrafish gene is expressed and its gene GO annotations",
        "List the genes in primates orthologous to genes expressed in the fruit fly eye",
    ]

    # The name of the application used for display
    app_name: str = "Expasy GPT"
    # Public API key used by the frontend to access the chatbot and prevent abuse from bots
    chat_api_key: str = ""
    # Secret API key used by admins to access log file easily from the API
    logs_api_key: str = ""

    # Settings for the vector store
    # https://qdrant.github.io/fastembed/examples/Supported_Models/
    embedding_model: str = "BAAI/bge-large-en-v1.5"
    sparse_embedding_model: str = "Qdrant/bm25"
    vectordb_url: str = "http://vectordb:6334/"
    docs_collection_name: str = "expasy"
    entities_collection_name: str = "entities"

    # Default settings for the agent that can be changed at runtime
    default_llm_model: str = "openai/gpt-4o"
    # default_llm_model: str = "azure/DeepSeek-R1"

    # default_number_of_retrieved_docs: int = 15
    default_number_of_retrieved_docs: int = 10
    default_max_try_fix_sparql: int = 3
    default_temperature: float = 0.0
    default_max_tokens: int = 120000

    logs_filepath: str = "/logs/user_questions.log"

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="allow",
    )

    # External services API keys
    azure_inference_credential: str = ""
    azure_inference_endpoint: str = ""
    # openai_api_key: str = ""
    # glhf_api_key: str = ""

settings = Settings()




@dataclass(kw_only=True)
class Configuration:
    """The configuration for the agent that can be changed at runtime when calling the agent."""

    system_prompt: str = field(
        default=prompts.SYSTEM_PROMPT,
        metadata={
            "description": "The system prompt to use for the agent's interactions."
            "This prompt sets the context and behavior for the agent."
        },
    )

    validate_output: bool = field(
        default=True,
        metadata={
            "description": "Wherever to validate or not the output of the LLM (e.g. SPARQL queries generated)."
        },
    )

    model: Annotated[str, {"__template_metadata__": {"kind": "llm"}}] = field(
        default=settings.default_llm_model,
        metadata={
            "description": "The name of the language model to use for the agent's main interactions."
            "Should be in the form: provider/model-name."
        },
    )

    temperature: Annotated[float, {"__template_metadata__": {"kind": "llm"}}] = field(
        default=settings.default_temperature,
        metadata={
            "description": "The temperature of the language model."
            "Should be between 0.0 and 2.0. Higher values make the model more creative but less deterministic."
        },
    )
    max_tokens: Annotated[int, {"__template_metadata__": {"kind": "llm"}}] = field(
        default=settings.default_max_tokens,
        metadata={
            "description": "The maximum number of tokens to generate in the response."
            "Should be between 4000 and 120000 (depends on the model context window)."
        },
    )

    # Number of retrieved docs
    search_kwargs: dict[str, Any] = field(
        default_factory=lambda: {"k": settings.default_number_of_retrieved_docs},
        # default_factory=dict,
        metadata={
            "description": "Additional keyword arguments to pass to the search function of the retriever."
        },
    )

    max_try_fix_sparql: int = field(
        default=settings.default_max_try_fix_sparql,
        metadata={
            "description": "The maximum number of tries when calling the model to fix a SPARQL query."
        },
    )

    # vectordb_url: str = field(
    #     default=settings.vectordb_url,
    #     metadata={"description": "URL for the vector store API, e.g. qdrant."},
    # )
    # collection_name: str = field(
    #     default="expasy",
    #     metadata={"description": "Name of collection, e.g. for qdrant."},
    # )
    # embedding_model: Annotated[
    #     str,
    #     {"__template_metadata__": {"kind": "embeddings"}},
    # ] = field(
    #     default=settings.embedding_model,
    #     metadata={
    #         "description": "Name of the embedding model to use. Must be a valid embedding model name supported by FastEmbed."
    #     },
    # )
    # sparse_embedding_model: Annotated[
    #     str,
    #     {"__template_metadata__": {"kind": "embeddings"}},
    # ] = field(
    #     default="Qdrant/bm25",
    #     metadata={"description": "Sparse embedding model supported by FastEmbed."},
    # )
    # retriever_provider: Annotated[
    #     Literal["qdrant", "elastic", "elastic-local", "pinecone", "mongodb"],
    #     {"__template_metadata__": {"kind": "retriever"}},
    # ] = field(
    #     default="qdrant",
    #     metadata={
    #         "description": "The vector store provider to use for retrieval. Options are 'qdrant', 'elastic', 'pinecone', or 'mongodb'."
    #     },
    # )

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


T = TypeVar("T", bound=Configuration)



# NOTE: still in use by tests, to be replaced with litellm
def get_llm_client(model: str) -> OpenAI:
    if model.startswith("hf:"):
        # Automatically use glhf API key if the model starts with "hf:"
        return OpenAI(
            api_key=settings.glhf_api_key,
            base_url="https://glhf.chat/api/openai/v1",
        )
    return OpenAI()


def get_embedding_model(gpu: bool = False) -> TextEmbedding:
    if gpu:
        return TextEmbedding(settings.embedding_model, providers=["CUDAExecutionProvider"])
    return TextEmbedding(settings.embedding_model)


# def get_vectordb(host=settings.vectordb_url) -> QdrantClient:
#     return QdrantClient(
#         host=host,
#         prefer_grpc=True,
#     )


# https://learn.microsoft.com/en-us/azure/ai-studio/reference/reference-model-inference-api?tabs=python
# https://github.com/Azure/azure-sdk-for-python/tree/main/sdk/ai/azure-ai-inference
# Or use LlamaIndex: https://docs.llamaindex.ai/en/stable/examples/llm/azure_inference/
# Langchain does not seems to have support for azure inference yet https://github.com/langchain-ai/langchain-azure/tree/main/libs

# from azure.ai.inference import ChatCompletionsClient
# from azure.core.credentials import AzureKeyCredential

# api_key = os.getenv("AZURE_INFERENCE_CREDENTIAL", '')
# if not api_key:
#   raise Exception("A key should be provided to invoke the endpoint")

# client = ChatCompletionsClient(
#     endpoint='https://mistral-large-2407-kru.swedencentral.models.ai.azure.com',
#     credential=AzureKeyCredential(api_key)
# )

# model_info = client.get_model_info()
# print("Model name:", model_info.model_name)
# print("Model type:", model_info.model_type)
# print("Model provider name:", model_info.model_provider_name)

# payload = {
#   "messages": [
#     {
#       "role": "user",
#       "content": "I am going to Paris, what should I see?"
#     },
#     {
#       "role": "assistant",
#       "content": "Paris, the capital of France, is known for its stunning architecture, art museums, historical landmarks, and romantic atmosphere. Here are some of the top attractions to see in Paris:\n\n1. The Eiffel Tower: The iconic Eiffel Tower is one of the most recognizable landmarks in the world and offers breathtaking views of the city.\n2. The Louvre Museum: The Louvre is one of the world's largest and most famous museums, housing an impressive collection of art and artifacts, including the Mona Lisa.\n3. Notre-Dame Cathedral: This beautiful cathedral is one of the most famous landmarks in Paris and is known for its Gothic architecture and stunning stained glass windows.\n\nThese are just a few of the many attractions that Paris has to offer. With so much to see and do, it's no wonder that Paris is one of the most popular tourist destinations in the world."
#     },
#     {
#       "role": "user",
#       "content": "What is so great about #1?"
#     }
#   ],
#   "max_tokens": 2048,
#   "temperature": 0.8,
#   "top_p": 0.1
# }
# response = client.complete(payload)

# print("Response:", response.choices[0].message.content)
# print("Model:", response.model)
# print("Usage:")
# print("	Prompt tokens:", response.usage.prompt_tokens)
# print("	Total tokens:", response.usage.total_tokens)
# print("	Completion tokens:", response.usage.completion_tokens)
