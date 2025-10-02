import argparse
import json
import os
from dataclasses import dataclass, field

from fastembed import TextEmbedding
from mcp.server.fastmcp import FastMCP
from qdrant_client import QdrantClient
from qdrant_client.models import FieldCondition, Filter, MatchValue, ScoredPoint
from sparql_llm.utils import query_sparql


@dataclass
class ServerConfig:
    embedding_name: str = "BAAI/bge-small-en-v1.5"
    embedding_dimensions: int = 384
    retrieved_docs_count: int = 5
    collection_name: str = "sparql-docs"
    vectordb_host: str = os.getenv("VECTORDB_HOST", "localhost")
    endpoints: list[dict[str, str]] = field(
        default_factory=lambda: [
            {"endpoint_url": "https://sparql.uniprot.org/sparql/"},
            {"endpoint_url": "https://www.bgee.org/sparql/"},
            {"endpoint_url": "https://sparql.omabrowser.org/sparql/"},
        ]
    )


config = ServerConfig()

# Load embedding model and init vector database
embedding_model = TextEmbedding(config.embedding_name)
vectordb = QdrantClient(path="data/vectordb")
# vectordb = QdrantClient(host=config.vectordb_host, prefer_grpc=True)


# Create MCP server https://github.com/modelcontextprotocol/python-sdk
mcp = FastMCP(
    "SIB BioData MCP",
    dependencies=["mcp", "qdrant_client", "fastembed", "sparql-llm"],
    # debug=True,
)


@mcp.tool()
async def access_sib_biodata_sparql(question: str, potential_classes: list[str], steps: list[str]) -> str:
    """Assist users in writing SPARQL queries to access SIB biodata resources by retrieving relevant examples and docs.
    Covers topics such as genes, proteins, lipids, chemical reactions, and metabolomics data.

    Args:
        question: The question to be answered with a SPARQL query
        potential_classes: High level concepts and potential classes that could be found in the SPARQL endpoints
        steps: Split the question in standalone smaller parts if relevant (if the question is already 1 step, leave empty)

    Returns:
        Relevant documents (examples, classes schemas)
    """
    relevant_docs: list[ScoredPoint] = []
    for search_embeddings in embedding_model.embed([question, *steps, *potential_classes]):
        # Get SPARQL example queries
        relevant_docs.extend(
            doc
            for doc in vectordb.query_points(
                query=search_embeddings,
                collection_name=config.collection_name,
                limit=config.retrieved_docs_count,
                query_filter=Filter(
                    must=[
                        FieldCondition(
                            key="doc_type",
                            match=MatchValue(value="SPARQL endpoints query examples"),
                        )
                    ]
                ),
            ).points
            # Make sure we don't add duplicate docs
            if doc.payload
            and doc.payload.get("metadata", {}).get("answer")
            not in {
                existing_doc.payload.get("metadata", {}).get("answer") if existing_doc.payload else None
                for existing_doc in relevant_docs
            }
        )
        # Get other relevant documentation (classes schemas, general information)
        relevant_docs.extend(
            doc
            for doc in vectordb.query_points(
                query=search_embeddings,
                collection_name=config.collection_name,
                limit=config.retrieved_docs_count,
                query_filter=Filter(
                    must_not=[
                        FieldCondition(
                            key="doc_type",
                            match=MatchValue(value="SPARQL endpoints query examples"),
                        )
                    ]
                ),
            ).points
            if doc.payload
            and doc.payload.get("metadata", {}).get("answer")
            not in {
                existing_doc.payload.get("metadata", {}).get("answer") if existing_doc.payload else None
                for existing_doc in relevant_docs
            }
        )
    return PROMPT_TOOL_SPARQL + format_docs(relevant_docs)


def format_docs(docs: list[ScoredPoint]) -> str:
    return "\n".join(_format_doc(doc) for doc in docs)


def _format_doc(doc: ScoredPoint) -> str:
    """Format a question/answer document to be provided as context to the model."""
    doc_lang = (
        f"sparql\n#+ endpoint: {doc.payload.get('endpoint_url', 'not provided')}"
        if "query" in doc.payload.get("doc_type", "")
        else ""
    )
    return f"\n{doc.payload['question']} ({doc.payload.get('endpoint_url', '')}):\n\n```{doc_lang}\n{doc.payload.get('answer')}\n```\n\n"


PROMPT_TOOL_SPARQL = """Depending on the user request and provided context, you may provide general information about
the resources available at the SIB, or help the user to formulate a query to run on a SPARQL endpoint.
If answering with a SPARQL query, always add the URL of the endpoint on which the query should be
executed in a comment at the start of the query inside the codeblocks starting with "#+ endpoint: " (always only 1
endpoint). Derive your answer from the context provided in the prompt, do not try to create a query from nothing and do
not provide a generic query.

Here is a list of documents (reference questions and query answers, classes schema or general endpoints information)
relevant to the user question that will help you answer the user question accurately:
"""


@mcp.tool()
def execute_sparql_query(sparql_query: str, endpoint_url: str) -> str:
    """Execute a SPARQL query against a SPARQL endpoint.

    Args:
        sparql_query: A valid SPARQL query string
        endpoint_url: The SPARQL endpoint URL to execute the query against

    Returns:
        The query results in JSON format
    """
    resp_msg = ""
    try:
        res = query_sparql(sparql_query, endpoint_url, timeout=10, post=True)
        # If no results, return a message to ask fix the query
        if not res.get("results", {}).get("bindings"):
            resp_msg += f"SPARQL query returned no results. {FIX_QUERY_PROMPT}\n```sparql\n{sparql_query}\n```"
        else:
            resp_msg += (
                f"Executed SPARQL query on {endpoint_url}:\n```sparql\n{sparql_query}\n```\n\nResults:\n"
                f"```\n{json.dumps(res, indent=2)}\n```"
            )
    except Exception as e:
        resp_msg += f"SPARQL query returned error: {e}. {FIX_QUERY_PROMPT}\n```sparql\n{sparql_query}\n```"
    return resp_msg


FIX_QUERY_PROMPT = """Please fix the query, and try again.
We suggest you to make the query less restricted, e.g. use a broader regex for string matching instead of exact match,
ignore case, make sure you are not overriding an existing variable with BIND, or break down your query in smaller parts
and check them one by one."""


# # https://modelcontextprotocol.io/docs/concepts/resources
# @mcp.resource("examples://{question}")
# def get_examples(question: str) -> str:
#     """Get relevant SPARQL query examples and other documents to help the user write a SPARQL query."""
#     return access_sib_biodata_sparql(question, [], [])


def main() -> None:
    """Run the MCP server with appropriate transport."""
    parser = argparse.ArgumentParser(
        description="A Model Context Protocol (MCP) server for BioData resources at the SIB."
    )
    parser.add_argument("--stdio", action="store_true", help="Use STDIO transport")
    parser.add_argument("--port", type=int, default=8888, help="Port to run the server on")
    args = parser.parse_args()
    if args.stdio:
        mcp.run()
    else:
        mcp.settings.port = args.port
        mcp.run(transport="streamable-http")
        # mcp.run(transport="sse")


if __name__ == "__main__":
    main()

# uv run mcp.py
