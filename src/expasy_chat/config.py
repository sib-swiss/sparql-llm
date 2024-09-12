from pydantic_settings import BaseSettings, SettingsConfigDict

from expasy_chat.utils import get_prefixes_for_endpoints

# import warnings
# warnings.simplefilter(action="ignore", category=UserWarning)


class Settings(BaseSettings):
    openai_api_key: str = ""
    glhf_api_key: str = ""
    expasy_api_key: str = ""
    logs_api_key: str = ""

    llm_model: str = "gpt-4o"
    # llm_model: str = "gpt-4o-mini"
    # Models from glhf:
    # llm_model: str = "hf:meta-llama/Meta-Llama-3.1-8B-Instruct"
    # llm_model: str = "hf:mistralai/Mixtral-8x22B-Instruct-v0.1"

    # llm_model: str = "hf:meta-lama/Meta-Llama-3.1-405B-Instruct"
    # llm_model: str = "hf:mistralai/Mistral-7B-Instruct-v0.3"

    # cheap_llm_model: str = "gpt-4o-mini"

    # https://qdrant.github.io/fastembed/examples/Supported_Models/
    embedding_model: str = "BAAI/bge-large-en-v1.5"
    embedding_dimensions: int = 1024
    ontology_chunk_size: int = 3000
    ontology_chunk_overlap: int = 200

    # Default is the IP address inside the podman network to solve a ridiculous bug from podman
    vectordb_host: str = "10.89.0.2"
    retrieved_queries_count: int = 20
    retrieved_docs_count: int = 15
    docs_collection_name: str = "expasy"

    max_try_fix_sparql: int = 5

    system_prompt: str = """You are Expasy, an assistant that helps users to navigate the resources and databases from the Swiss Institute of Bioinformatics.
Depending on the user request and provided context, you may provide general information about the resources available at the SIB, or help the user to formulate a query to run on a SPARQL endpoint.
If answering with a query:
put the query inside markdown codeblocks with the "sparql" language tag, and only use endpoints that are provided in the context.
Always indicate the URL of the endpoint on which the query should be executed in a comment in the codeblocks at the start of the query (no additional text, just the endpoint URL directly as comment, nothing else, always and only 1 endpoint).
If answering with a query always derive your answer from the queries provided as examples in the prompt, don't try to create a query from nothing and do not provide a generic query.
Try to always answer with one query, if the answer lies in different endpoints, provide a federated query.
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
        {
            "label": "MetaNetx",
            "endpoint_url": "https://rdf.metanetx.org/sparql/",
            "homepage": "https://www.metanetx.org/",
        },
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
