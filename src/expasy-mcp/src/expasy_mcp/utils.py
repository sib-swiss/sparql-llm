import os
from dataclasses import dataclass

from fastembed import TextEmbedding
from qdrant_client import QdrantClient
from qdrant_client.models import FieldCondition, Filter, MatchValue, ScoredPoint


@dataclass
class ServerConfig:
    embedding_name: str = "BAAI/bge-small-en-v1.5"
    embedding_dimensions: int = 384
    retrieved_docs_count: int = 5
    collection_name: str = "expasy"
    vectordb_host: str = os.getenv("VECTORDB_HOST", "localhost")


config = ServerConfig()

# Load embedding model and connect to vector database
embedding_model = TextEmbedding(
    config.embedding_name,
    # providers=["CUDAExecutionProvider"], # Replace the fastembed dependency with fastembed-gpu to use your GPUs
)
vectordb = QdrantClient(host=config.vectordb_host, prefer_grpc=True)


def retrieve_docs(question: str) -> list[ScoredPoint]:
    """Retrieve relevant documents from the vector database using the question as a query."""
    question_embeddings = next(iter(embedding_model.embed([question])))
    # Get SPARQL example queries
    example_queries = vectordb.query_points(
        collection_name=config.collection_name,
        query=question_embeddings,
        limit=config.retrieved_docs_count,
        query_filter=Filter(
            must=[
                FieldCondition(
                    key="metadata.doc_type",
                    match=MatchValue(value="SPARQL endpoints query examples"),
                )
            ]
        ),
    )
    # Get other relevant documentation (classes schemas, general information)
    other_docs = vectordb.query_points(
        collection_name=config.collection_name,
        query=question_embeddings,
        limit=config.retrieved_docs_count,
        query_filter=Filter(
            must_not=[
                FieldCondition(
                    key="metadata.doc_type",
                    match=MatchValue(value="SPARQL endpoints query examples"),
                )
            ]
        ),
    )
    return example_queries.points + other_docs.points


prompt_tool_sparql = """Depending on the user request and provided context, you may provide general information about
the resources available at the SIB, or help the user to formulate a query to run on a SPARQL endpoint.
If answering with a SPARQL query, always add the URL of the endpoint on which the query should be
executed in a comment at the start of the query inside the codeblocks starting with "#+ endpoint: " (always only 1
endpoint). Derive your answer from the context provided in the prompt, do not try to create a query from nothing and do
not provide a generic query.

Here is a list of documents (reference questions and query answers, classes schema or general endpoints information)
relevant to the user question that will help you answer the user question accurately:
"""


def format_docs(docs: list[ScoredPoint]) -> str:
    """Format a list of documents as pseudo-XML with introduction system prompt."""
    return f"<documents>\n{'\n'.join(_format_doc(doc) for doc in docs)}\n</documents>"


def _format_doc(doc: ScoredPoint) -> str:
    """Format a single document as XML, with special formatting based on doc type (sparql, schema)."""
    doc_meta: dict[str, str] = doc.payload.get("metadata", {}) if doc.payload is not None else {}
    if doc_meta.get("answer"):
        doc_lang = ""
        doc_type = str(doc_meta.get("doc_type", "")).lower()
        if "query" in doc_type:
            doc_lang = f"sparql\n#+ endpoint: {doc_meta.get('endpoint_url', 'undefined')}"
        elif "schema" in doc_type:
            doc_lang = "shex"
        return f"<document>\n{doc_meta.get('question')}:\n\n```{doc_lang}\n{doc_meta.get('answer')}\n```\n</document>"
    # Generic formatting:
    meta = "".join(f" {k}={v!r}" for k, v in doc_meta.items())
    if meta:
        meta = f" {meta}"
    return f"<document{meta}>\n{doc_meta.get('question')}\n</document>"
