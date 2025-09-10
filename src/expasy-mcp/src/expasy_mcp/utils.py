import logging
import os
from dataclasses import dataclass, field

from fastembed import TextEmbedding
from qdrant_client import QdrantClient
from qdrant_client.models import ScoredPoint
from sparql_llm.utils import SparqlEndpointLinks

# Silence overly verbose info logs from httpx
logging.getLogger("httpx").setLevel(logging.WARNING)


@dataclass
class ServerConfig:
    embedding_name: str = "BAAI/bge-small-en-v1.5"
    embedding_dimensions: int = 384
    retrieved_docs_count: int = 5
    collection_name: str = "expasy"
    vectordb_host: str = os.getenv("VECTORDB_HOST", "localhost")

    endpoints: list[SparqlEndpointLinks] = field(
        default_factory=lambda: [
            {
                # The label of the endpoint for clearer display
                "label": "UniProt",
                # The URL of the SPARQL endpoint from which most informations will be extracted
                "endpoint_url": "https://sparql.uniprot.org/sparql/",
                "description": "UniProt is a comprehensive resource for protein sequence and annotation data.",
                # "void_file": "../sparql-llm/tests/void_uniprot.ttl",
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
                "description": "The MEtabolomes, TRaits, and INteractions-Knowledge Graph (METRIN-KG) is a project that aims to create a digital representation of chemo- and biodiversity, from botanical collections to the global scale in wild ecosystems.",
            },
        ]
    )


config = ServerConfig()

# Load embedding model and connect to vector database
embedding_model = TextEmbedding(
    config.embedding_name,
    # providers=["CUDAExecutionProvider"], # Replace the fastembed dependency with fastembed-gpu to use your GPUs
)
vectordb = QdrantClient(host=config.vectordb_host, prefer_grpc=True)


def format_docs(docs: list[ScoredPoint]) -> str:
    """Format a list of documents."""
    return f"{'\n'.join(_format_doc(doc) for doc in docs)}"


def _format_doc(doc: ScoredPoint) -> str:
    """Format a single document, with special formatting based on doc type (sparql, schema)."""
    if not doc.payload:
        return ""
    doc_meta: dict[str, str] = doc.payload.get("metadata", {})
    if doc_meta.get("answer"):
        doc_lang = ""
        doc_type = str(doc_meta.get("doc_type", "")).lower()
        if "query" in doc_type:
            doc_lang = f"sparql\n#+ endpoint: {doc_meta.get('endpoint_url', 'undefined')}"
        elif "schema" in doc_type:
            doc_lang = "shex"
        return f"{doc.payload['page_content']}:\n\n```{doc_lang}\n{doc_meta.get('answer')}\n```"
    # Generic formatting:
    meta = "".join(f" {k}={v!r}" for k, v in doc_meta.items())
    if meta:
        meta = f" {meta}"
    return f"{meta}\n{doc.payload['page_content']}\n"
