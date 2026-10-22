import argparse
import fcntl
import json
import pathlib
import time
from datetime import datetime, timezone
from typing import Any

import httpx
from mcp.server.context import CallNext, HandlerResult, ServerRequestContext
from mcp.server.mcpserver import MCPServer
from mcp.server.mcpserver.exceptions import ToolError
from mcp.server.transport_security import TransportSecuritySettings
from pydantic import BaseModel
from qdrant_client.models import FieldCondition, Filter, MatchValue, ScoredPoint
from rdflib.plugins.sparql import prepareQuery
from typing_extensions import NotRequired, TypedDict

# Widget tools of other SIB resources are registered on the UniProt MCP Apps extension when imported
from sparql_llm import (  # noqa: F401
    __version__,
    bgee_tools,
    cellosaurus_tools,
    metanetx_tools,
    oma_tools,
    orthodb_tools,
    rhea_tools,
    swisslipids_tools,
)
from sparql_llm.config import settings
from sparql_llm.indexing.index_resources import embedding_model, endpoints_metadata, init_vectordb, qdrant_client
from sparql_llm.loaders.sparql_info_loader import GENERAL_INFO_DOC_TYPE
from sparql_llm.uniprot_tools import READ_ONLY, add_uniprot_tools
from sparql_llm.uniprot_tools import apps as uniprot_apps
from sparql_llm.utils import logger, query_sparql
from sparql_llm.validate_sparql import validate_sparql

# What are the rat orthologs of the human TP53?
# TODO: MCP integrated https://github.com/modelcontextprotocol/python-sdk/pull/1007

SPARQL_QUERY_GUIDELINES = """## SPARQL Query Guidelines
- **Always include the endpoint URL** as a comment at the start: `#+ endpoint: http://example.org/sparql`
- **Use only ONE endpoint** per query
- **Base your query on the provided context**, never create generic or unsupported queries
- **Use appropriate prefixes** and class names from the schema documentation
"""

MAX_RESULT_ROWS = 50

EXAMPLES_DOC_TYPE = "SPARQL endpoints query examples"
CLASSES_SCHEMA_DOC_TYPE = "SPARQL endpoints classes schema"


class QueryExample(TypedDict):
    question: str
    query: str
    endpoint_url: str


class ClassSchema(TypedDict):
    label: str
    iri: str
    shex: str
    endpoint_url: str


class ResourceInfo(TypedDict):
    question: str
    answer: str
    endpoint_url: NotRequired[str]


class SparqlExamplesSearchResults(TypedDict):
    query_examples: list[QueryExample]


class ClassesSchemaSearchResults(TypedDict):
    classes_schemas: list[ClassSchema]


class ResourcesInfoSearchResults(TypedDict):
    resources_info: list[ResourceInfo]


# SPARQL 1.1 query results JSON format https://www.w3.org/TR/sparql11-results-json/
# Functional syntax since `xml:lang` is not a valid identifier
SparqlTerm = TypedDict(
    "SparqlTerm",
    {
        "type": str,
        "value": str,
        "xml:lang": NotRequired[str],
        "datatype": NotRequired[str],
    },
)


class SparqlHead(TypedDict):
    vars: list[str]


class SparqlBindings(TypedDict):
    bindings: list[dict[str, SparqlTerm]]


class SparqlQueryResults(TypedDict):
    """SPARQL JSON results, with extra info on the executed query and truncation."""

    head: SparqlHead
    results: SparqlBindings
    total_results: int
    truncated: bool
    fixed_query: NotRequired[str]


def get_transport_security() -> TransportSecuritySettings | None:
    """Allow the public host when deployed, otherwise use the SDK default localhost-only DNS rebinding protection."""
    if not settings.app_public_host:
        return None
    # https://github.com/modelcontextprotocol/python-sdk/issues/1798
    return TransportSecuritySettings(
        enable_dns_rebinding_protection=True,
        allowed_hosts=["localhost:*", "127.0.0.1:*", settings.app_public_host],
        allowed_origins=["http://localhost:*", f"https://{settings.app_public_host}"],
    )


async def log_tool_calls(ctx: ServerRequestContext[Any, Any], call_next: CallNext) -> HandlerResult:
    """Server middleware appending each tool call, with its args and result, to a JSONL file."""
    if ctx.method != "tools/call" or not settings.mcp_logs_filepath:
        return await call_next(ctx)
    started_at = time.time()
    result: HandlerResult = None
    error: str | None = None
    try:
        result = await call_next(ctx)
        return result
    except Exception as e:
        # Protocol-level failures (unknown tool, invalid params) are raised, tool failures come back as `isError` results
        error = repr(e)
        raise
    finally:
        params = ctx.params or {}
        client = ctx.session.client_params.client_info if ctx.session.client_params else None
        entry = {
            "timestamp": datetime.fromtimestamp(started_at, tz=timezone.utc).isoformat(),
            "latency": round(time.time() - started_at, 3),
            "tool": params.get("name"),
            "args": params.get("arguments"),
            "result": result.model_dump(mode="json", by_alias=True, exclude_none=True)
            if isinstance(result, BaseModel)
            else result,
            "error": error,
            "requestId": ctx.request_id,
            "client": client.model_dump(mode="json", exclude_none=True) if client else None,
        }
        path = settings.mcp_logs_filepath
        try:
            line = json.dumps(entry, ensure_ascii=False, default=str) + "\n"
            with open(path, "a", encoding="utf-8") as f:
                # Lock so lines from concurrent workers are never interleaved
                fcntl.flock(f, fcntl.LOCK_EX)
                try:
                    f.write(line)
                finally:
                    fcntl.flock(f, fcntl.LOCK_UN)
        except Exception as e:
            logger.warning(f"⚠️ Could not write MCP tool call log to {path}: {e}")


def get_mcp_app(enable_resources_info_tool: bool = True, enable_uniprot_tools: bool = True) -> MCPServer:
    """Get the MCP server instance.

    Transport options (stateless, JSON response, path, security) are passed when building the app,
    e.g. `mcp.streamable_http_app(stateless_http=True, json_response=True, transport_security=get_transport_security())`
    """
    instructions = (
        "Provide tools that helps users to access biological data resources from the Swiss Institute of Bioinformatics (SIB) through the SPARQL query language. "
        "To answer a question: search relevant query examples with `search_sparql_examples`, or relevant classes with "
        "`search_sparql_classes`, then run the query with `execute_sparql_query`."
    )
    if enable_uniprot_tools:
        instructions += (
            " For simple questions on UniProtKB proteins, `search_proteins` and `get_protein` query the UniProt REST API "
            "directly, and the `show_*` and `search_proteins_table` tools show interactive views of proteins to the user. "
            "Other `show_*` tools show interactive views of gene expression (Bgee), biochemical reactions with their atom "
            "map (Rhea), metabolites and reactions across databases and metabolic models (MetaNetX), lipids (SwissLipids), "
            "cell lines with their STR authentication (Cellosaurus), gene family history and conserved gene "
            "neighbourhood (OMA), and ortholog groups with their phyletic profile (OrthoDB)."
        )
    # Create MCP server https://github.com/modelcontextprotocol/python-sdk
    # UniProt tools showing widgets are added through the MCP Apps extension
    # Title, description and website are sent in `serverInfo` for clients to show in their connectors UI
    mcp = MCPServer(
        "Expasy MCP",
        title="Expasy",
        description=(
            "Query bioinformatics resources of the SIB Swiss Institute of Bioinformatics such as UniProt, Bgee, "
            "Rhea, OMA, OrthoDB, Cellosaurus, SwissLipids and MetaNetX, through their SPARQL endpoints and "
            "interactive views of proteins, gene expression, reactions, lipids, cell lines and orthologs."
        ),
        website_url="https://expasy.org/chat",
        instructions=instructions,
        version=__version__,
        debug=True,
        dependencies=["mcp", "qdrant_client", "fastembed", "sparql-llm"],
        extensions=[uniprot_apps] if enable_uniprot_tools else [],
        middleware=[log_tool_calls],
    )
    if enable_uniprot_tools:
        add_uniprot_tools(mcp)
    if settings.mcp_logs_filepath:
        pathlib.Path(settings.mcp_logs_filepath).parent.mkdir(parents=True, exist_ok=True)

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

    # potential_entities: Potential entities and instances of classes

    search_sparql_examples_desc = (
        f"""Search SPARQL query examples relevant to a question related to {settings.app_topics}

Use the examples as a base to write a SPARQL query answering the question, then use `search_sparql_classes`
to check the details of classes and predicates used in the query.

Args:
    question: The question to be answered with a SPARQL query
    steps: Split the question in standalone smaller parts if relevant (if the question is already 1 step, leave empty)

Returns:
    Relevant SPARQL query examples, with the question they answer and the endpoint to run them on

"""
        + SPARQL_QUERY_GUIDELINES
    )

    @mcp.tool(description=search_sparql_examples_desc, annotations=READ_ONLY)
    async def search_sparql_examples(question: str, steps: list[str]) -> SparqlExamplesSearchResults:
        docs = search_docs(
            list(embedding_model.embed([question, *steps])), Filter(must=[doc_type_condition(EXAMPLES_DOC_TYPE)])
        )
        return {"query_examples": [to_query_example(doc) for doc in docs]}

    @mcp.tool(annotations=READ_ONLY)
    async def search_sparql_classes(classes: list[str]) -> ClassesSchemaSearchResults:
        """Search classes and their schema (predicates and the types of their values) in the SPARQL endpoints.

        Args:
            classes: High level concepts and potential classes that could be found in the SPARQL endpoints

        Returns:
            Relevant classes schemas in ShEx format, with the endpoint where the class is found
        """
        docs = search_docs(
            list(embedding_model.embed(classes)), Filter(must=[doc_type_condition(CLASSES_SCHEMA_DOC_TYPE)])
        )
        return {"classes_schemas": [to_class_schema(doc) for doc in docs]}

    if enable_resources_info_tool:

        @mcp.tool(annotations=READ_ONLY)
        async def search_resources(question: str) -> ResourcesInfoSearchResults:
            """Search general information about the resources and SPARQL endpoints indexed by this MCP server.

            Only call this tool when the user explicitly asks for information about the resources themselves.

            Args:
                question: The user question

            Returns:
                Relevant information about the resources (description, endpoints, metadata)
            """
            docs = search_docs(
                list(embedding_model.embed([question])), Filter(must=[doc_type_condition(GENERAL_INFO_DOC_TYPE)])
            )
            return {"resources_info": [to_resource_info(doc) for doc in docs]}

    @mcp.tool(annotations=READ_ONLY)
    def execute_sparql_query(sparql_query: str, endpoint_url: str) -> SparqlQueryResults | str:
        """Execute a SPARQL query against a SPARQL endpoint.

        If the query returns no results, make it less restrictive (e.g. case-insensitive regex instead of exact
        string match, no variable overridden with BIND), or break it down in smaller parts and check them one by one.

        Args:
            sparql_query: A valid SPARQL query string
            endpoint_url: The SPARQL endpoint URL to execute the query against

        Returns:
            For SELECT and ASK queries: the results in the SPARQL JSON format (first 50 rows), with the total number of results.
            For CONSTRUCT and DESCRIBE queries: the resulting RDF graph in Turtle format.
        """
        # First check if query valid based on classes schema and known prefixes
        validation_output = validate_sparql(
            sparql_query, endpoint_url, endpoints_metadata.prefixes_map, endpoints_metadata.void_dict
        )
        fixed_query = validation_output["fixed_query"]
        if fixed_query:
            sparql_query = fixed_query
        if validation_output["errors"]:
            error_str = "- " + "\n- ".join(validation_output["errors"])
            raise ToolError(
                "The SPARQL query is not valid according to the endpoint schema:\n"
                f"{error_str}\n\nErroneous SPARQL query:\n```sparql\n{sparql_query}\n```\n"
                "Fix the query using the error messages and the classes schema."
            )

        # Execute the query, turning each kind of failure into an error message the client can act on
        try:
            if is_graph_query(sparql_query):
                # CONSTRUCT and DESCRIBE return an RDF graph, request it as Turtle
                resp = httpx.post(
                    endpoint_url,
                    headers={"Accept": "text/turtle"},
                    data={"query": sparql_query},
                    timeout=10,
                    follow_redirects=True,
                )
                resp.raise_for_status()
                return resp.text
            res = query_sparql(sparql_query, endpoint_url, timeout=10, post=True)
        except httpx.HTTPStatusError as e:
            # Endpoints usually put the parser or execution error in the response body
            body = e.response.text.strip()[:2000] or "(empty response body)"
            raise ToolError(
                f"SPARQL endpoint {endpoint_url} returned HTTP {e.response.status_code}:\n{body}\n\n"
                f"Query:\n```sparql\n{sparql_query}\n```\nFix the query using the error message and try again."
            ) from e
        except httpx.TimeoutException as e:
            raise ToolError(
                f"SPARQL query timed out after 10s on {endpoint_url}. Make the query more specific, "
                f"add a LIMIT, or avoid expensive patterns (unbound predicates, FILTER on large sets, regex).\n"
                f"Query:\n```sparql\n{sparql_query}\n```"
            ) from e
        except httpx.RequestError as e:
            raise ToolError(f"Could not reach SPARQL endpoint {endpoint_url}: {type(e).__name__} {e}") from e
        except json.JSONDecodeError as e:
            raise ToolError(
                f"SPARQL endpoint {endpoint_url} did not return SPARQL JSON results, check the endpoint URL "
                "and that the query is a SELECT, ASK, CONSTRUCT or DESCRIBE query."
            ) from e

        # Limit the number of rows returned to the client
        bindings = res.get("results", {}).get("bindings", [])
        output: SparqlQueryResults = {
            "head": {"vars": res.get("head", {}).get("vars", [])},
            "results": {"bindings": bindings[:MAX_RESULT_ROWS]},
            "total_results": len(bindings),
            "truncated": len(bindings) > MAX_RESULT_ROWS,
        }
        if fixed_query:
            output["fixed_query"] = fixed_query
        return output

    return mcp

    # # https://modelcontextprotocol.io/docs/concepts/resources
    # @mcp.resource("examples://{question}")
    # async def get_examples(question: str) -> str:
    #     """Get relevant SPARQL query examples and other documents to help the user write a SPARQL query."""
    #     embeddings = list(embedding_model.embed([question]))
    #     docs = search_docs(embeddings, Filter(must=[doc_type_condition(EXAMPLES_DOC_TYPE)])) + search_docs(
    #         embeddings, Filter(must_not=[doc_type_condition(EXAMPLES_DOC_TYPE)])
    #     )
    #     return PROMPT_TOOL_SPARQL.format(docs_count=str(len(docs)), formatted_docs=format_docs(docs))
    # @mcp.resource("schema://{endpoint}/cls/{uri}")
    # def get_class_schema(endpoint: str, uri: str) -> str:
    #     """Get the schema of a class given its URI."""
    #     return format_docs(retrieve_docs(uri))


def is_graph_query(sparql_query: str) -> bool:
    """Check if a query returns an RDF graph (CONSTRUCT or DESCRIBE) rather than SPARQL JSON results."""
    return prepareQuery(sparql_query).algebra.name in ("ConstructQuery", "DescribeQuery")


def doc_type_condition(doc_type: str) -> FieldCondition:
    """Qdrant condition matching documents of a given type."""
    return FieldCondition(key="doc_type", match=MatchValue(value=doc_type))


def search_docs(embeddings: list[Any], query_filter: Filter) -> list[ScoredPoint]:
    """Search the vectordb for each embedding, deduplicating documents by their answer."""
    docs: list[ScoredPoint] = []
    seen_answers: set[str] = set()
    for embedding in embeddings:
        for doc in qdrant_client.query_points(
            query=embedding,
            collection_name=settings.docs_collection_name,
            limit=settings.default_number_of_retrieved_docs,
            query_filter=query_filter,
        ).points:
            answer = doc.payload.get("answer") if doc.payload else None
            if answer and answer not in seen_answers:
                seen_answers.add(answer)
                docs.append(doc)
    return docs


# Convert retrieved documents payloads to the tools structured output
def to_query_example(doc: ScoredPoint) -> QueryExample:
    payload = doc.payload or {}
    return {
        "question": str(payload.get("question", "")),
        "query": str(payload.get("answer", "")),
        "endpoint_url": str(payload.get("endpoint_url", "")),
    }


def to_class_schema(doc: ScoredPoint) -> ClassSchema:
    payload = doc.payload or {}
    return {
        "label": str(payload.get("question", "")),
        "iri": str(payload.get("iri", "")),
        "shex": str(payload.get("answer", "")),
        "endpoint_url": str(payload.get("endpoint_url", "")),
    }


def to_resource_info(doc: ScoredPoint) -> ResourceInfo:
    payload = doc.payload or {}
    info: ResourceInfo = {"question": str(payload.get("question", "")), "answer": str(payload.get("answer", ""))}
    if payload.get("endpoint_url"):
        info["endpoint_url"] = str(payload["endpoint_url"])
    return info


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
    # meta = "".join(f" {k}={v!r}" for k, v in doc.payload.items())
    # if meta:
    #     meta = f" {meta}"
    return "".join(f" {k}={v!r}" for k, v in doc.payload.items())


def cli() -> None:
    """Run the MCP server with appropriate transport."""
    parser = argparse.ArgumentParser(
        description="A Model Context Protocol (MCP) server for BioData resources at the SIB."
    )
    parser.add_argument("--http", action="store_true", help="Use Streamable HTTP transport")
    parser.add_argument("--port", type=int, default=8888, help="Port to run the server on")
    # parser.add_argument("settings_filepath", type=str, nargs="?", default="sparql-mcp.json", help="Path to settings file")
    args = parser.parse_args()
    mcp = get_mcp_app()
    # settings = Settings.from_file(args.settings_filepath)
    if args.http:
        mcp.run(
            transport="streamable-http",
            port=args.port,
            stateless_http=True,
            json_response=True,
            transport_security=get_transport_security(),
        )
    else:
        mcp.run()


# if __name__ == "__main__":
#     cli()

# PROMPT_TOOL_SPARQL = (
#     "Formulate a precise SPARQL query to access specific biological data and answer the user's question.\n\n"
#     + SPARQL_QUERY_GUIDELINES
#     + """
# ## Knowledge Base
# The following {docs_count} documents contain relevant query examples, and classes schemas to help you construct an accurate response:

# {formatted_docs}
# """
# )
