"""Define the service settings and configurable parameters for the agent."""

from __future__ import annotations

import json
import os
from dataclasses import dataclass, field, fields
from pathlib import Path
from typing import Annotated, Any, TypeVar

from fastembed import TextEmbedding
from langchain_core.runnables import RunnableConfig, ensure_config
from pydantic_settings import BaseSettings, SettingsConfigDict
from qdrant_client import QdrantClient

from sparql_llm.agent import prompts
from sparql_llm.utils import SparqlEndpointLinks


class Settings(BaseSettings):
    """Define the service settings for the agent that can be set using environment variables."""

    use_tools: bool = False
    """Whether to use tools or not. If set to False, the agent will use the functions sequentially to answer questions."""

    # The list of endpoints that will be indexed and supported by the service
    endpoints: list[SparqlEndpointLinks] = [
        {
            # The label of the endpoint for clearer display
            "label": "UniProt",
            # The URL of the SPARQL endpoint from which most informations will be extracted
            "endpoint_url": "https://sparql.uniprot.org/sparql/",
            "description": "UniProt is a comprehensive resource for protein sequence and annotation data.",
            # If VoID description or SPARQL query examples are not available in the endpoint, you can provide a VoID file (local or remote)
            "void_file": "./tests/void_uniprot.ttl",
            # "void_file": "https://sparql.uniprot.org/.well-known/void/",
            # "examples_file": "../sparql-llm/tests/examples_uniprot.ttl",
            # Optional, a homepage from which we can extract more information using the JSON-LD context
            # "homepage_url": "https://www.uniprot.org/",
            # "ontology": "https://ftp.uniprot.org/pub/databases/uniprot/current_release/rdf/core.owl",
        },
        {
            "label": "Bgee",
            "description": "Bgee is a database for retrieval and comparison of gene expression patterns across multiple animal species.",
            "endpoint_url": "https://www.bgee.org/sparql/",
            "homepage_url": "https://www.bgee.org/",
            # "ontology": "http://purl.org/genex",
        },
        {
            "label": "Orthology MAtrix (OMA)",
            "endpoint_url": "https://sparql.omabrowser.org/sparql/",
            "homepage_url": "https://omabrowser.org/",
            # "ontology": "http://purl.org/net/orth",
            "description": "OMA is a method and database for the inference of orthologs among complete genomes.",
        },
        {
            "label": "HAMAP",
            "endpoint_url": "https://hamap.expasy.org/sparql/",
            "homepage_url": "https://hamap.expasy.org/",
            "description": "HAMAP is a system for the classification and annotation of protein sequences. It consists of a collection of manually curated family profiles for protein classification, and associated, manually created annotation rules that specify annotations that apply to family members.",
        },
        {
            "label": "SwissLipids",
            "endpoint_url": "https://beta.sparql.swisslipids.org/",
            "homepage_url": "https://www.swisslipids.org",
            "description": "SwissLipids is an expert curated resource that provides a framework for the integration of lipid and lipidomic data with biological knowledge and models.",
        },
        {
            "label": "Rhea",
            "endpoint_url": "https://sparql.rhea-db.org/sparql/",
            "homepage_url": "https://www.rhea-db.org/",
            "description": "Rhea is an expert-curated knowledgebase of chemical and transport reactions of biological interest - and the standard for enzyme and transporter annotation in UniProtKB.",
        },
        {
            "label": "Cellosaurus",
            "endpoint_url": "https://sparql.cellosaurus.org/sparql",
            "homepage_url": "https://cellosaurus.org/",
            "description": "Cellosaurus is a knowledge resource on cell lines.",
        },
        {
            "label": "OrthoDB",
            "endpoint_url": "https://sparql.orthodb.org/sparql/",
            "homepage_url": "https://www.orthodb.org/",
            "description": "The hierarchical catalog of orthologs mapping genomics to functional data",
        },
        {
            "label": "METRIN-KG ",
            "endpoint_url": "https://kg.earthmetabolome.org/metrin/api/",
            "description": """METRIN-KG is a knowledge graph developed under the Earth Metabolome Initiative that integrates data on plant metabolomes, measurable plant traits, and their biotic interactions.
It provides a unified, searchable framework that connects chemical profiles of plants with ecological and biological attributes.""",
            # "homepage_url": "https://dbgi.eu/",
        },
        {
            "label": "MetaNetX",
            "endpoint_url": "https://rdf.metanetx.org/sparql/",
            "homepage_url": "https://www.metanetx.org/",
        },
        {
            "label": "SIBiLS",
            "endpoint_url": "https://sparql.sibils.org/sparql",
            "description": """SIBiLS (Swiss Institute of Bioinformatics Literature Services) provide personalized Information Retrieval in the biological literature.
It covers 4 collections: MEDLINE, PubMedCentral (PMC), Plazi treatments, and PMC supplementary files.""",
            # "homepage_url": "https://sibils.org/",
        },
        # Error querying NExtProt
        # {
        #     "label": "NextProt",
        #     # "endpoint_url": "https://api.nextprot.org/sparql",
        #     "endpoint_url": "https://sparql.nextprot.org",
        #     "homepage_url": "https://www.nextprot.org/",
        # },
        # {
        #     "label": "GlyConnect",
        #     "endpoint_url": "https://glyconnect.expasy.org/sparql",
        #     "homepage_url": "https://glyconnect.expasy.org/",
        # },
    ]

    # Settings for the vector store and embeddings
    # ⚠️ changing the embedding models require to reindex the data
    # vectordb_url: str = "http://vectordb:6334/"
    vectordb_url: str = "data/vectordb"
    # https://qdrant.github.io/fastembed/examples/Supported_Models/#supported-text-embedding-models
    # embedding_model: str = "BAAI/bge-large-en-v1.5"
    # embedding_dimensions: int = 1024
    # embedding_model: str = "BAAI/bge-base-en-v1.5"
    # embedding_dimensions: int = 768
    embedding_model: str = "BAAI/bge-small-en-v1.5"
    embedding_dimensions: int = 384
    force_index: bool = False
    # Automatically initialize the vector store client, should be False when deploying in prod with multiple workers
    auto_init: bool = True

    # Sparse embeddings are only used for the entities resolution
    sparse_embedding_model: str = "Qdrant/bm25"
    # sparse_embedding_model: str = "prithivida/Splade_PP_en_v1"
    docs_collection_name: str = "expasy"
    entities_collection_name: str = "entities"

    # Default settings for the agent that can be changed at runtime
    default_llm_model: str = "openrouter/openai/gpt-4o"
    # default_llm_model: str = "openai/gpt-4o"
    # TODO: default_llm_model_cheap: str = "openai/gpt-4o-mini"

    default_number_of_retrieved_docs: int = 10
    default_max_try_fix_sparql: int = 3
    default_temperature: float = 0.0
    default_max_tokens: int = 16384
    default_seed: int = 42

    # List of example questions to display in the chat UI
    example_questions: list[str] = [
        "Which SIB resources are supported by ExpasyGPT? ",
        "Where is the ACE2 gene expressed in humans?",
        "List primate genes expressed in the fruit fly eye",
        "What are the rat orthologs of the human HBB gene?",
        "What is the HGNC symbol for the P68871 protein?",
        "Anatomical entities where the INS zebrafish gene is expressed and their gene GO annotations",
    ]

    # The name of the application used for display
    app_name: str = "ExpasyGPT"
    # Public API key used by the frontend to access the chatbot and prevent abuse from bots
    chat_api_key: str = ""
    # Secret API key used by admins to access log file easily from the API
    logs_api_key: str = ""
    # Optional Sentry error report API key
    sentry_url: str = ""

    logs_folder: str = "./data/logs"
    logs_filepath: str = "./data/logs/user_questions.log"

    # External services API keys
    azure_inference_credential: str = ""
    azure_inference_endpoint: str = ""

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="allow",
    )

    @classmethod
    def from_file(cls, filepath: str) -> Settings:
        """Create a Settings instance from a file.

        Args:
            filepath: The path to the file.
        """
        path = Path(filepath)  # your JSON file path
        if not path.exists():
            return Settings()
        with path.open("r") as f:
            return Settings(**json.load(f))


settings_filepath = os.getenv("SETTINGS_FILEPATH")
settings = Settings.from_file(settings_filepath) if settings_filepath else Settings()
# logger.info(f"📂 Using SETTINGS file: {settings_filepath}")

# settings = Settings()

# TODO: Getting `TypeError: cannot pickle '_thread.RLock' object` when doing `QdrantVectorStore.from_existing_collection(client=qdrant_client)`
qdrant_client = (
    QdrantClient(url=settings.vectordb_url, prefer_grpc=True, timeout=600)
    if settings.vectordb_url.startswith(("http", "https"))
    else QdrantClient(path=settings.vectordb_url)
)

embedding_model = TextEmbedding(
    settings.embedding_model,
    # providers=["CUDAExecutionProvider"], # Replace the fastembed dependency with fastembed-gpu to use your GPUs
)


# Configuration defined at runtime
@dataclass(kw_only=True)
class Configuration:
    """The configuration for the agent that can be changed at runtime when calling the agent."""

    enable_entities_resolution: bool = field(
        default=False,
        metadata={
            "description": "Wherever to enable trying to resolve entities to their URIs in the SPARQL endpoints."
        },
    )

    enable_output_validation: bool = field(
        default=True,
        metadata={"description": "Wherever to validate or not the output of the LLM (e.g. SPARQL queries generated)."},
    )

    enable_sparql_execution: bool = field(
        default=True,
        metadata={
            "description": "Wherever to enable automatically executing a SPARQL query against its endpoint after passing its validation step."
        },
    )

    system_prompt: str = field(
        default=prompts.RESOLUTION_PROMPT,
        metadata={
            "description": "The system prompt to use for the agent's interactions."
            "This prompt sets the context and behavior for the agent."
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
    seed: Annotated[int, {"__template_metadata__": {"kind": "llm"}}] = field(
        default=settings.default_seed,
        metadata={"description": "The random seed used for reproducibility."},
    )
    # Number of retrieved docs
    search_kwargs: dict[str, Any] = field(
        default_factory=lambda: {"k": settings.default_number_of_retrieved_docs},
        # default_factory=dict,
        metadata={"description": "Additional keyword arguments to pass to the search function of the retriever."},
    )

    max_try_fix_sparql: int = field(
        default=settings.default_max_try_fix_sparql,
        metadata={"description": "The maximum number of tries when calling the model to fix a SPARQL query."},
    )

    @classmethod
    def from_runnable_config(cls: type[T], config: RunnableConfig | None = None) -> T:
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
