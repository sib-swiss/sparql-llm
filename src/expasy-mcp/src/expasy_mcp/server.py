import argparse
import json

from mcp.server.fastmcp import FastMCP
from sparql_llm import query_sparql, validate_sparql
from SPARQLWrapper import SPARQLWrapper, JSON

from expasy_mcp.utils import format_docs, prompt_tool_sparql, retrieve_docs

# What are the rat orthologs of the human TP53?

# Create MCP server https://github.com/modelcontextprotocol/python-sdk
mcp = FastMCP(
    "SIB BioData MCP",
    # debug=True,
    # dependencies=["mcp", "qdrant_client", "fastembed"],
)


# query_sib_biodata_sparql("What are the rat orthologs of the human TP53?")
# , ctx: Context[Any, Any]
@mcp.tool()
async def access_sib_biodata_sparql(question: str) -> str:
    """Assist users in writing SPARQL queries to access SIB biodata resources by retrieving relevant examples and docs.
    Covers topics such as genes, proteins, lipids, chemical reactions, and metabolomics data.

    Args:
        question: The question to be answered with a SPARQL query

    Returns:
        List of relevant documents (examples, classes schemas) that can be used by the agent to write a SPARQL query
    """
    all_docs = retrieve_docs(question)
    # import urllib.parse
    # all_docs = list(await ctx.read_resource(f"examples://{urllib.parse.quote(question)}"))
    # await ctx.info(f"Using {len(all_docs)} documents to answer the question")
    return prompt_tool_sparql + format_docs(all_docs)


@mcp.tool()
def execute_sparql_query(query: str, endpoint: str) -> str:
    """Execute a SPARQL query against a SPARQL endpoint.

    Args:
        query: A valid SPARQL query string
        endpoint: The SPARQL endpoint URL to execute the query against

    Returns:
        The query results in JSON format
    """
    res = query_sparql(query, endpoint)
    return json.dumps(res, indent=2)


# @mcp.tool()
# def validate_sparql_query(query: str, endpoint: str) -> str:
#     """Validate a SPARQL query destinated to a SPARQL endpoint using the VoID description of the endpoint when available

#     Args:
#         query: A valid SPARQL query string
#         endpoint: The SPARQL endpoint URL to execute the query against

#     Returns:
#         The query results in JSON format
#     """
#     res = validate_sparql(query, endpoint)
#     return json.dumps(res, indent=2)


# https://modelcontextprotocol.io/docs/concepts/resources
@mcp.resource("examples://{question}")
def get_examples(question: str) -> str:
    """Get relevant SPARQL query examples and other documents to help the user write a SPARQL query."""
    return format_docs(retrieve_docs(question))

# @mcp.resource("schema://{endpoint}/cls/{uri}")
# def get_class_schema(endpoint: str, uri: str) -> str:
#     """Get the schema of a class given its URI."""
#     return format_docs(retrieve_docs(uri))

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
        mcp.run(transport="sse")


if __name__ == "__main__":
    main()
    # print(access_biodata_sparql("What are the rat orthologs of the human TP53?"))
    # print(execute_sparql_query("CONSTRUCT {?s ?p ?o } WHERE { ?s ?p ?o } LIMIT 10", "https://sparql.uniprot.org"))
