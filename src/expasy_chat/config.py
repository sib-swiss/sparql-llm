from pydantic_settings import BaseSettings, SettingsConfigDict

# import warnings
# warnings.simplefilter(action="ignore", category=UserWarning)


class Settings(BaseSettings):
    openai_api_key: str = ""
    expasy_api_key: str = ""
    logs_api_key: str = ""

    llm_model: str = "gpt-4o"
    # llm_model: str = "gpt-4o-mini"

    # https://qdrant.github.io/fastembed/examples/Supported_Models/
    embedding_model: str = "BAAI/bge-large-en-v1.5"
    embedding_dimensions: int = 1024
    ontology_chunk_size: int = 3000
    ontology_chunk_overlap: int = 200

    # Default is the IP address inside the podman network to solve a ridiculous bug from podman
    vectordb_host: str = "10.89.0.2"
    retrieved_docs_count: int = 20
    docs_collection_name: str = "expasy"

    max_try_fix_sparql: int = 5

    endpoints: list[dict[str, str]] = [
        {
            "label": "UniProt",
            "endpoint": "https://sparql.uniprot.org/sparql/",
            "homepage": "https://www.uniprot.org/",
            "ontology": "https://ftp.uniprot.org/pub/databases/uniprot/current_release/rdf/core.owl",
        },
        {
            "label": "Bgee",
            "endpoint": "https://www.bgee.org/sparql/",
            "homepage": "https://www.bgee.org/",
            "ontology": "http://purl.org/genex",
        },
        {
            "label": "Orthology MAtrix (OMA)",
            "endpoint": "https://sparql.omabrowser.org/sparql/",
            "homepage": "https://omabrowser.org/",
            "ontology": "http://purl.org/net/orth",
        },
        {
            "label": "Rhea",
            "endpoint": "https://sparql.rhea-db.org/sparql/",
            "homepage": "https://www.rhea-db.org/",
        },
        {
            "label": "MetaNetx",
            "endpoint": "https://rdf.metanetx.org/sparql/",
            "homepage": "https://www.metanetx.org/",
        },
        {
            "label": "SwissLipids",
            "endpoint": "https://beta.sparql.swisslipids.org/",
            "homepage": "https://www.swisslipids.org",
        },
        {
            "label": "HAMAP",
            "endpoint": "https://hamap.expasy.org/sparql/",
            "homepage": "https://hamap.expasy.org/",
        },
        {
            "label": "NextProt",
            # "endpoint": "https://api.nextprot.org/sparql",
            "endpoint": "https://sparql.nextprot.org",
            "homepage": "https://www.nextprot.org/",
        },
        {
            "label": "OrthoDB",
            # "endpoint": "https://api.nextprot.org/sparql",
            "endpoint": "https://sparql.orthodb.org/sparql/",
            "homepage": "https://www.orthodb.org/",
        },
        {
            "label": "dbgi",
            "endpoint": "https://biosoda.unil.ch/graphdb/repositories/emi-dbgi",
            # "homepage": "https://dbgi.eu/",
        },
        # {
        #     "label": "GlyConnect",
        #     "endpoint": "https://glyconnect.expasy.org/sparql",
        #     "homepage": "https://glyconnect.expasy.org/",
        # },
    ]

    all_prefixes_filepath: str = "all_prefixes.json"
    logs_filepath: str = "/logs/user_questions.log"

    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8")


settings = Settings()
