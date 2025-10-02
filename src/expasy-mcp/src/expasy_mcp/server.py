import argparse
import json

from mcp.server.fastmcp import FastMCP
from qdrant_client.models import FieldCondition, Filter, MatchValue, ScoredPoint
from sparql_llm.utils import get_prefixes_and_schema_for_endpoints, query_sparql

# from sparql_llm.validate_sparql import validate_sparql
from expasy_mcp.utils import config, embedding_model, format_docs, vectordb

# What are the rat orthologs of the human TP53?

# Create MCP server https://github.com/modelcontextprotocol/python-sdk
mcp = FastMCP(
    "SIB BioData MCP",
    debug=True,
    dependencies=["mcp", "qdrant_client", "fastembed", "sparql-llm"],
)

## TOOL: retrieve docs to generate SPARQL query


# ctx: Context[Any, Any], potential_entities: list[str],
# potential_entities: Potential entities and instances of classes
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
                            key="metadata.doc_type",
                            match=MatchValue(value="SPARQL endpoints query examples"),
                        )
                    ]
                ),
            ).points
            # Make sure we don't add duplicate docs
            if doc.payload
            and doc.payload.get("metadata", {}).get("answer")
            not in {
                existing_doc.payload.get("metadata", {}).get("answer") if existing_doc.payload else None for existing_doc in relevant_docs
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
                            key="metadata.doc_type",
                            match=MatchValue(value="SPARQL endpoints query examples"),
                        )
                    ]
                ),
            ).points
            if doc.payload
            and doc.payload.get("metadata", {}).get("answer")
            not in {
                existing_doc.payload.get("metadata", {}).get("answer") if existing_doc.payload else None for existing_doc in relevant_docs
            }
        )
    # await ctx.info(f"Using {len(relevant_docs)} documents to answer the question")
    return PROMPT_TOOL_SPARQL.format(docs_count=str(len(relevant_docs))) + format_docs(relevant_docs)


# Here is a list of **{len(relevant_docs)}** documents (reference questions and query answers, classes schema) relevant to the question that will help answer it accurately:

# {format_points(relevant_docs)}"""
#     return PROMPT_TOOL_SPARQL.format(docs_count=str(len(relevant_docs))) + format_docs(relevant_docs)

PROMPT_TOOL_SPARQL = """Depending on the user request and provided context, you may provide general information about
the resources available at the SIB, or help the user to formulate a query to run on a SPARQL endpoint.
If answering with a SPARQL query, always add the URL of the endpoint on which the query should be
executed in a comment at the start of the query inside the codeblocks starting with "#+ endpoint: " (always only 1
endpoint). Derive your answer from the context provided in the prompt, do not try to create a query from nothing and do
not provide a generic query.

Here is a list of {docs_count} documents (reference questions and query answers, classes schema or general endpoints information)
relevant to the user question that will help you answer the user question accurately:
"""

## TOOL: get resources infos


@mcp.tool()
def get_resources_info(question: str) -> str:
    """Get information about the service and resources available at the SIB Swiss Institute of Bioinformatics.

    Args:
        question: The user question.

    Returns:
        str: Information about the resources.
    """
    search_embeddings = next(iter(embedding_model.embed([question])))
    relevant_docs = vectordb.query_points(
        collection_name=config.collection_name,
        query=search_embeddings,
        limit=config.retrieved_docs_count,
        query_filter=Filter(
            must=[
                FieldCondition(
                    key="metadata.doc_type",
                    match=MatchValue(value="General information"),
                )
            ]
        ),
    ).points
    return PROMPT_TOOL_SPARQL.format(docs_count=str(len(relevant_docs))) + format_docs(relevant_docs)


## TOOL: execute SPARQL query


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
    # validation_output = validate_sparql(sparql_query, endpoint_url, prefixes_map, endpoints_void_dict)
    # if validation_output["fixed_query"]:
    #     # Pass the fixed query to the client
    #     resp_msg += f"Fixed the prefixes of the generated SPARQL query automatically:\n```sparql\n{validation_output['fixed_query']}\n```\n"
    #     sparql_query = validation_output["fixed_query"]
    # if validation_output["errors"]:
    #     # Recall the LLM to try to fix the errors
    #     error_str = "- " + "\n- ".join(validation_output["errors"])
    #     resp_msg += (
    #         "The query generated in the original response is not valid according to the endpoints schema.\n"
    #         f"### Validation results\n{error_str}\n"
    #         f"### Erroneous SPARQL query\n```sparql\n{validation_output['original_query']}\n```\n"
    #         "Fix the SPARQL query helping yourself with the error message and context from previous messages."
    #     )
    #     return resp_msg
    # Execute the SPARQL query
    try:
        res = query_sparql(sparql_query, endpoint_url, timeout=10)
        # res = query_sparql(sparql_query, endpoint_url, timeout=10, check_service_desc=False, post=True)
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


prefixes_map, endpoints_void_dict = get_prefixes_and_schema_for_endpoints(config.endpoints)

FIX_QUERY_PROMPT = """Please fix the query, and try again.
We suggest you to make the query less restricted, e.g. use a broader regex for string matching instead of exact match,
ignore case, make sure you are not overriding an existing variable with BIND, or break down your query in smaller parts
and check them one by one."""


# https://modelcontextprotocol.io/docs/concepts/resources
@mcp.resource("examples://{question}")
def get_examples(question: str) -> str:
    """Get relevant SPARQL query examples and other documents to help the user write a SPARQL query."""
    # return format_docs(retrieve_docs(question))
    return access_sib_biodata_sparql(question, [], [])


# @mcp.resource("schema://{endpoint}/cls/{uri}")
# def get_class_schema(endpoint: str, uri: str) -> str:
#     """Get the schema of a class given its URI."""
#     return format_docs(retrieve_docs(uri))


def main() -> None:
    """Run the MCP server with appropriate transport."""
    parser = argparse.ArgumentParser(description="A Model Context Protocol (MCP) server for BioData resources at the SIB.")
    parser.add_argument("--stdio", action="store_true", help="Use STDIO transport")
    parser.add_argument("--port", type=int, default=8888, help="Port to run the server on")
    args = parser.parse_args()
    if args.stdio:
        mcp.run()
    else:
        mcp.settings.port = args.port
        mcp.settings.host = "0.0.0.0"  # noqa: S104
        mcp.run(transport="streamable-http")
        # mcp.run(transport="sse")


if __name__ == "__main__":
    main()
    # print(access_biodata_sparql("What are the rat orthologs of the human TP53?"))
    # print(execute_sparql_query("CONSTRUCT {?s ?p ?o } WHERE { ?s ?p ?o } LIMIT 10", "https://sparql.uniprot.org"))
