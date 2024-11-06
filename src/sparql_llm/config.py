from fastembed import TextEmbedding
from openai import OpenAI
from pydantic_settings import BaseSettings, SettingsConfigDict
from qdrant_client import QdrantClient

from sparql_llm.utils import get_prefixes_for_endpoints

# import warnings
# warnings.simplefilter(action="ignore", category=UserWarning)

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


def get_llm_client(model: str) -> OpenAI:
    if model.startswith("hf:"):
        # Automatically use glhf API key if the model starts with "hf:"
        return OpenAI(
            api_key=settings.glhf_api_key,
            base_url="https://glhf.chat/api/openai/v1",
        )
    return OpenAI()


class Settings(BaseSettings):
    openai_api_key: str = ""
    glhf_api_key: str = ""
    expasy_api_key: str = ""
    logs_api_key: str = ""
    azure_inference_credential: str = ""
    azure_inference_endpoint: str = ""
    # llm_model: str = "gpt-4o"
    # cheap_llm_model: str = "gpt-4o-mini"

    # https://qdrant.github.io/fastembed/examples/Supported_Models/
    embedding_model: str = "BAAI/bge-large-en-v1.5"
    embedding_dimensions: int = 1024
    # embedding_model: str = "jinaai/jina-embeddings-v2-base-en"
    # embedding_dimensions: int = 768

    ontology_chunk_size: int = 3000
    ontology_chunk_overlap: int = 200

    vectordb_host: str = "vectordb"
    # NOTE: old hack to fix a bug with podman internal network, can be removed soon
    # vectordb_host: str = "10.89.0.2"

    retrieved_queries_count: int = 20
    retrieved_docs_count: int = 15
    docs_collection_name: str = "expasy"

    entities_collection_name: str = "entities"

    max_try_fix_sparql: int = 5

    system_prompt: str = """You are Expasy, an assistant that helps users to navigate the resources and databases from the Swiss Institute of Bioinformatics.
Depending on the user request and provided context, you may provide general information about the resources available at the SIB, or help the user to formulate a query to run on a SPARQL endpoint.
If answering with a query:
Put the SPARQL query inside a markdown codeblock with the "sparql" language tag, and indicate the URL of the endpoint on which the query should be executed in a comment at the start of the query (no additional text, just the endpoint URL directly as comment, always and only 1 endpoint).
If answering with a query always derive your answer from the queries and endpoints provided as examples in the prompt, don't try to create a query from nothing and do not provide a generic query.
Try to always answer with one query, if the answer lies in different endpoints, provide a federated query. Do not add more codeblocks than necessary.
"""
    # try to make it as efficient as possible to avoid timeout due to how large the datasets are, make sure the query written is valid SPARQL,
    # If the answer to the question is in the provided context, do not provide a query, just provide the answer, unless explicitly asked.

    endpoints: list[dict[str, str]] = [
        {
            "label": "UniProt",
            "endpoint_url": "https://sparql.uniprot.org/sparql/",
            "homepage": "https://www.uniprot.org/",
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
        # Nothing in those endpoints:
        {
            "label": "Rhea",
            "endpoint_url": "https://sparql.rhea-db.org/sparql/",
            "homepage": "https://www.rhea-db.org/",
        },
        # {
        #     "label": "MetaNetx",
        #     "endpoint_url": "https://rdf.metanetx.org/sparql/",
        #     "homepage": "https://www.metanetx.org/",
        # },
        {
            "label": "OrthoDB",
            "endpoint_url": "https://sparql.orthodb.org/sparql/",
            "homepage": "https://www.orthodb.org/",
        },
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

    logs_filepath: str = "/logs/user_questions.log"

    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8")


settings = Settings()


def get_prefixes_dict() -> dict[str, str]:
    """Return a dictionary of all prefixes."""
    endpoints_urls = [endpoint["endpoint_url"] for endpoint in settings.endpoints]
    return get_prefixes_for_endpoints(endpoints_urls)


def get_embedding_model() -> TextEmbedding:
    # return TextEmbedding(settings.embedding_model, cuda=True)
    return TextEmbedding(settings.embedding_model)


def get_vectordb(host=settings.vectordb_host) -> QdrantClient:
    return QdrantClient(
        host=host,
        prefer_grpc=True,
    )
