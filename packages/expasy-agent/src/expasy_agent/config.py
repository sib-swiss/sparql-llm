"""Define the service settings and configurable parameters for the agent."""

from __future__ import annotations

from dataclasses import dataclass, field, fields
from typing import Annotated, Any, Optional, Type, TypeVar

from langchain_core.runnables import RunnableConfig, ensure_config
from pydantic_settings import BaseSettings, SettingsConfigDict

from expasy_agent import prompts


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
            "void_file": "https://sparql.uniprot.org/.well-known/void/",
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
    # ⚠️ changing the embedding models require to reindex the data
    # https://qdrant.github.io/fastembed/examples/Supported_Models/
    embedding_model: str = "BAAI/bge-large-en-v1.5"
    embedding_dimensions: int = 1024
    # Sparse embeddings are only used for the entities resolution
    sparse_embedding_model: str = "Qdrant/bm25"
    # sparse_embedding_model: str = "prithivida/Splade_PP_en_v1"
    vectordb_url: str = "http://vectordb:6334/"
    docs_collection_name: str = "expasy"
    entities_collection_name: str = "entities"

    # Default settings for the agent that can be changed at runtime
    default_llm_model: str = "openai/gpt-4o"
    # TODO: default_llm_model_cheap: str = "openai/gpt-4o-mini"

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

    enable_entities_resolution: bool = field(
        default=False,
        metadata={
            "description": "Wherever to enable trying to resolve entities to their URIs in the SPARQL endpoints."
        },
    )

    enable_output_validation: bool = field(
        default=True,
        metadata={
            "description": "Wherever to validate or not the output of the LLM (e.g. SPARQL queries generated)."
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
