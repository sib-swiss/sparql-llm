import argparse
import json

from mcp.server.fastmcp import FastMCP
from qdrant_client.models import FieldCondition, Filter, MatchValue, ScoredPoint

from sparql_llm.agent.nodes.validation import endpoints_void_dict, prefixes_map
from sparql_llm.config import embedding_model, qdrant_client, settings
from sparql_llm.indexing.index_resources import init_vectordb
from sparql_llm.utils import logger, query_sparql
from sparql_llm.validate_sparql import validate_sparql

# What are the rat orthologs of the human TP53?
# TODO: MCP integrated https://github.com/modelcontextprotocol/python-sdk/pull/1007

# Create MCP server https://github.com/modelcontextprotocol/python-sdk
mcp = FastMCP(
    name="SIB BioData MCP",
    debug=True,
    dependencies=["mcp", "qdrant_client", "fastembed", "sparql-llm"],
    instructions="Provide tools that helps users to access biological data resources from the Swiss Institute of Bioinformatics (SIB) through the SPARQL query language.",
    json_response=True,
    stateless_http=True,
    streamable_http_path="/",
)

# Check if the docs collection exists and has data, initialize if not
# In prod with multiple workers, auto_init should be set to False to avoid race conditions
try:
    collection_needs_init = (
        settings.force_index
        or not qdrant_client.collection_exists(settings.docs_collection_name)
        or not qdrant_client.get_collection(settings.docs_collection_name).points_count
    )
    if settings.auto_init and collection_needs_init:
        logger.info("📊 Initializing vectordb...")
        init_vectordb()
    elif not settings.auto_init and collection_needs_init:
        logger.warning(
            f"⚠️ Collection '{settings.docs_collection_name}' does not exist or is empty. Run the following command to initialize it:\n"
            "docker compose -f compose.prod.yml exec api uv run src/sparql_llm/indexing/index_resources.py"
        )
    else:
        logger.info(
            f"✅ Collection '{settings.docs_collection_name}' exists with {qdrant_client.get_collection(settings.docs_collection_name).points_count} points. Skipping initialization."
        )
except Exception as e:
    logger.error(f"⚠️ Error checking or initializing vectordb: {e}")
    # Continue without initialization to avoid blocking the app startup


# TODO: tool get_classes_schema
# potential_entities: Potential entities and instances of classes
@mcp.tool()
async def search_sparql_docs(question: str, potential_classes: list[str], steps: list[str]) -> str:
    """Assist users in writing SPARQL queries to access SIB biodata resources by retrieving relevant examples and classes schema.
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
            for doc in qdrant_client.query_points(
                query=search_embeddings,
                collection_name=settings.docs_collection_name,
                limit=settings.default_number_of_retrieved_docs,
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
            and doc.payload.get("answer")
            not in {
                existing_doc.payload.get("answer") if existing_doc.payload else None for existing_doc in relevant_docs
            }
        )
        # Get other relevant documentation (classes schemas, general information)
        relevant_docs.extend(
            doc
            for doc in qdrant_client.query_points(
                query=search_embeddings,
                collection_name=settings.docs_collection_name,
                limit=settings.default_number_of_retrieved_docs,
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
            and doc.payload.get("answer")
            not in {
                existing_doc.payload.get("answer") if existing_doc.payload else None for existing_doc in relevant_docs
            }
        )
    # await ctx.info(f"Using {len(relevant_docs)} documents to answer the question")
    return PROMPT_TOOL_SPARQL.format(docs_count=str(len(relevant_docs)), formatted_docs=format_docs(relevant_docs))


PROMPT_TOOL_SPARQL = """Formulate a precise SPARQL query to access specific biological data and answer the user's question.

## SPARQL Query Guidelines
- **Always include the endpoint URL** as a comment at the start: `#+ endpoint: http://example.org/sparql`
- **Use only ONE endpoint** per query
- **Base your query on the provided context** - never create generic or unsupported queries
- **Use appropriate prefixes** and class names from the schema documentation

## Knowledge Base
The following {docs_count} documents contain relevant query examples, and classes schemas to help you construct an accurate response:

{formatted_docs}
"""

# PROMPT_TOOL_SPARQL = """Depending on the user request and provided context, you may provide general information about
# the resources available at the SIB, or help the user to formulate a query to run on a SPARQL endpoint.
# If answering with a SPARQL query, always add the URL of the endpoint on which the query should be
# executed in a comment at the start of the query inside the codeblocks starting with "#+ endpoint: " (always only 1
# endpoint). Derive your answer from the context provided in the prompt, do not try to create a query from nothing and do
# not provide a generic query.
# Here is a list of {docs_count} documents (reference questions and query answers, classes schema or general endpoints information)
# relevant to the user question that will help you answer the user question accurately:
# """


@mcp.tool()
async def get_classes_schema(classes: list[str]) -> str:
    """Search for specific classes and their schema in the SPARQL endpoints.

    Args:
        classes: High level concepts and potential classes that could be found in the SPARQL endpoints

    Returns:
        Relevant classes schemas
    """
    relevant_docs: list[ScoredPoint] = []
    for search_embeddings in embedding_model.embed(classes):
        # Get other relevant documentation (classes schemas, general information)
        relevant_docs.extend(
            doc
            for doc in qdrant_client.query_points(
                query=search_embeddings,
                collection_name=settings.docs_collection_name,
                limit=settings.default_number_of_retrieved_docs,
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
            and doc.payload.get("answer")
            not in {
                existing_doc.payload.get("answer") if existing_doc.payload else None for existing_doc in relevant_docs
            }
        )
    return f"""Here is a list of {len(relevant_docs)} classes schema relevant to the request:
{format_docs(relevant_docs)}"""


@mcp.tool()
def get_resources_info(question: str) -> str:
    """Get information about the services and resources available at the SIB Swiss Institute of Bioinformatics and indexed by this MCP server.

    Args:
        question: The user question.

    Returns:
        str: Information about the resources.
    """
    search_embeddings = next(iter(embedding_model.embed([question])))
    relevant_docs = qdrant_client.query_points(
        collection_name=settings.docs_collection_name,
        query=search_embeddings,
        limit=settings.default_number_of_retrieved_docs,
        query_filter=Filter(
            must=[
                FieldCondition(
                    key="doc_type",
                    match=MatchValue(value="General information"),
                )
            ]
        ),
    ).points
    return f"""Here is a list of {len(relevant_docs)} documents relevant to the question that will help answer it accurately:
{format_docs(relevant_docs)}"""


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
    # First check if query valid based on classes schema and known prefixes
    validation_output = validate_sparql(sparql_query, endpoint_url, prefixes_map, endpoints_void_dict)
    if validation_output["fixed_query"]:
        # Pass the fixed query to the client
        resp_msg += f"Fixed the prefixes of the generated SPARQL query automatically:\n```sparql\n{validation_output['fixed_query']}\n```\n"
        sparql_query = validation_output["fixed_query"]
    if validation_output["errors"]:
        # Recall the LLM to try to fix the errors
        error_str = "- " + "\n- ".join(validation_output["errors"])
        resp_msg += (
            "The query generated in the original response is not valid according to the endpoints schema.\n"
            f"### Validation results\n{error_str}\n"
            f"### Erroneous SPARQL query\n```sparql\n{validation_output['original_query']}\n```\n"
            "Fix the SPARQL query helping yourself with the error message and context from previous messages."
        )
        return resp_msg
    # Execute the SPARQL query
    try:
        res = query_sparql(sparql_query, endpoint_url, timeout=10, post=True)
        bindings = res.get("results", {}).get("bindings")
        if not bindings:
            # If no results, return a message to ask fix the query
            resp_msg += f"SPARQL query returned no results. {FIX_QUERY_PROMPT}\n```sparql\n{sparql_query}\n```"
        else:
            # If results, return them (limit to first 50 rows if too many)
            resp_msg += f"Results of SPARQL query execution on {endpoint_url}"
            if len(bindings) > 50:
                res["results"]["bindings"] = bindings[:50]
                resp_msg += f" (showing first 50 of {len(bindings)} results)"
            resp_msg += f":\n```\n{json.dumps(res, indent=2)}\n```"
    except Exception as e:
        resp_msg += f"SPARQL query returned error: {e}. {FIX_QUERY_PROMPT}\n```sparql\n{sparql_query}\n```"
    return resp_msg


# prefixes_map, endpoints_void_dict = get_prefixes_and_schema_for_endpoints(settings.endpoints)

FIX_QUERY_PROMPT = """Please fix the query, and try again.
We suggest you to make the query less restricted, e.g. use a broader regex for string matching instead of exact match,
ignore case, make sure you are not overriding an existing variable with BIND, or break down your query in smaller parts
and check them one by one."""


# https://modelcontextprotocol.io/docs/concepts/resources
@mcp.resource("examples://{question}")
def get_examples(question: str) -> str:
    """Get relevant SPARQL query examples and other documents to help the user write a SPARQL query."""
    return search_sparql_docs(question, [], [])


# @mcp.resource("schema://{endpoint}/cls/{uri}")
# def get_class_schema(endpoint: str, uri: str) -> str:
#     """Get the schema of a class given its URI."""
#     return format_docs(retrieve_docs(uri))


def format_docs(docs: list[ScoredPoint]) -> str:
    """Format a list of documents."""
    return "\n".join(_format_doc(doc) for doc in docs)


def _format_doc(doc: ScoredPoint) -> str:
    """Format a single document, with special formatting based on doc type (sparql, schema)."""
    if not doc.payload:
        return ""
    if doc.payload.get("answer"):
        doc_lang = ""
        doc_type = str(doc.payload.get("doc_type", "")).lower()
        if "query" in doc_type:
            doc_lang = f"sparql\n#+ endpoint: {doc.payload.get('endpoint_url', 'undefined')}"
        elif "schema" in doc_type:
            doc_lang = "shex"
        return f"{doc.payload['question']}:\n\n```{doc_lang}\n{doc.payload.get('answer')}\n```"
    # Generic formatting:
    meta = "".join(f" {k}={v!r}" for k, v in doc.payload.items())
    if meta:
        meta = f" {meta}"
    return f"{meta}\n{doc.payload['page_content']}\n"


def cli() -> None:
    """Run the MCP server with appropriate transport."""
    parser = argparse.ArgumentParser(
        description="A Model Context Protocol (MCP) server for BioData resources at the SIB."
    )
    parser.add_argument("--http", action="store_true", help="Use Streamable HTTP transport")
    parser.add_argument("--port", type=int, default=8888, help="Port to run the server on")
    # parser.add_argument("settings_filepath", type=str, nargs="?", default="sparql-mcp.json", help="Path to settings file")
    args = parser.parse_args()
    # settings = Settings.from_file(args.settings_filepath)
    if args.http:
        mcp.run()
        mcp.settings.port = args.port
        mcp.settings.log_level = "INFO"
        mcp.run(transport="streamable-http")
    else:
        mcp.run()


# if __name__ == "__main__":
#     cli()
