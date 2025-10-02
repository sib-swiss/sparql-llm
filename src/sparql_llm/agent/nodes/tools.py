# import json
# from typing import Any, Callable, List

# from fastembed import TextEmbedding
# from langchain_core.tools import tool
# from qdrant_client import QdrantClient
# from qdrant_client.models import FieldCondition, Filter, MatchValue, ScoredPoint
# from sparql_llm.utils import query_sparql
# from sparql_llm.validate_sparql import validate_sparql

# from sparql_llm.agent.config import settings
# from sparql_llm.agent.nodes.validation import endpoints_void_dict, prefixes_map
# from sparql_llm.agent.prompts import FIX_QUERY_PROMPT

# # To use tools:
# # 1. Use bind_tools in nodes/call_model.py
# # 2. Change the langgraph edges in graph.py


# @tool
# def execute_sparql_query(sparql_query: str, endpoint_url: str) -> str:
#     """Execute a SPARQL query against a SPARQL endpoint. Called whenever there is a SPARQL query in the last message.

#     Args:
#         sparql_query (str): A valid SPARQL query string
#         endpoint_url (str): The SPARQL endpoint URL to execute the query against

#     Returns:
#         str: The query results in JSON format as string
#     """
#     # First run validation of the query using classes schema and known prefixes
#     resp_msg = ""
#     validation_output = validate_sparql(
#         sparql_query, endpoint_url, prefixes_map, endpoints_void_dict
#     )
#     if validation_output["fixed_query"]:
#         # Pass the fixed query to the client
#         resp_msg += f"Fixed the prefixes of the generated SPARQL query automatically:\n\n```sparql\n{validation_output['fixed_query']}\n```\n"
#         sparql_query = validation_output["fixed_query"]
#     if validation_output["errors"]:
#         # Recall the LLM to try to fix the errors
#         error_str = "- " + "\n- ".join(validation_output["errors"])
#         resp_msg += f"The query generated in the original response is not valid according to the endpoints schema.\n### Validation results\n{error_str}\n### Erroneous SPARQL query\n```sparql\n{validation_output['original_query']}\n```\n"
#         resp_msg += "Fix the SPARQL query helping yourself with the error message and context from previous messages in a way that it is a fully valid query."
#         return resp_msg
#     # Execute the SPARQL query
#     try:
#         res = query_sparql(
#             sparql_query, endpoint_url, timeout=10, check_service_desc=False, post=True
#         )
#         # If no results, return a message to ask fix the query
#         if not res.get("results", {}).get("bindings"):
#             resp_msg += f"SPARQL query returned no results. {FIX_QUERY_PROMPT}\n```sparql\n{sparql_query}\n```"
#         else:
#             resp_msg += f"Executed SPARQL query on {endpoint_url}:\n```sparql\n{sparql_query}\n```\n\nResults:\n```\n{json.dumps(res, indent=2)}\n```"
#     except Exception as e:
#         resp_msg += f"SPARQL query returned error: {e}. {FIX_QUERY_PROMPT}\n```sparql\n{sparql_query}\n```"
#     return resp_msg


# # TODO: use grouping? https://qdrant.tech/documentation/concepts/search/#grouping-api
# # Which tools can I use for enrichment analysis?

# # Load embedding model and connect to vector database
# embedding_model = TextEmbedding(
#     settings.embedding_model,
#     # providers=["CUDAExecutionProvider"],
# )
# vectordb = QdrantClient(url=settings.vectordb_url, prefer_grpc=True)


# @tool
# def access_biomedical_resources(
#     question: str,
#     potential_classes: list[str],
#     potential_entities: list[str],
#     steps: list[str],
# ) -> str:
#     """Answer a biomedical question using SIB public resources.

#     Retrieves context to generate a SPARQL query for the user question.

#     Args:
#         question (str): The user question to be answered.
#         potential_classes (list[str]): High level concepts and potential classes that could be found in the SPARQL endpoints and used to answer the question
#         potential_entities (list[str]): Potential entities and instances of classes
#         steps (list[str]): Split the question in standalone smaller parts if relevant (if the question is already 1 step, leave empty)

#     Returns:
#         str: A string containing document that will help the assistant to generate the SPARQL query to answer the question.
#     """
#     relevant_docs: list[ScoredPoint] = []
#     for search_embeddings in embedding_model.embed(
#         [question, *steps, *potential_classes]
#     ):
#         # Get SPARQL example queries
#         relevant_docs.extend(
#             doc
#             for doc in vectordb.query_points(
#                 collection_name=settings.docs_collection_name,
#                 query=search_embeddings,
#                 limit=settings.default_number_of_retrieved_docs,
#                 query_filter=Filter(
#                     must=[
#                         FieldCondition(
#                             key="metadata.doc_type",
#                             match=MatchValue(value="SPARQL endpoints query examples"),
#                         )
#                     ]
#                 ),
#             ).points
#             # Make sure we don't add duplicate docs
#             if doc.payload.get("metadata", {}).get("answer")
#             not in {
#                 existing_doc.payload.get("metadata", {}).get("answer")
#                 for existing_doc in relevant_docs
#             }
#         )
#         # Get classes schemas
#         relevant_docs.extend(
#             doc
#             for doc in vectordb.query_points(
#                 collection_name=settings.docs_collection_name,
#                 query=search_embeddings,
#                 limit=int(settings.default_number_of_retrieved_docs / 2),
#                 query_filter=Filter(
#                     must=[
#                         FieldCondition(
#                             key="metadata.doc_type",
#                             match=MatchValue(value="SPARQL endpoints classes schema"),
#                         )
#                     ]
#                 ),
#             ).points
#             if doc.payload.get("metadata", {}).get("answer")
#             not in {
#                 existing_doc.payload.get("metadata", {}).get("answer")
#                 for existing_doc in relevant_docs
#             }
#         )
#     args = {
#         "question": question,
#         "potential_classes": potential_classes,
#         "potential_entities": potential_entities,
#         "steps": steps,
#     }
#     return f"""```\n{json.dumps(args, indent=2)}\n```\n\n---

# Here is a list of **{len(relevant_docs)}** documents (reference questions and query answers, classes schema) relevant to the question that will help answer it accurately:

# {format_points(relevant_docs)}"""

#     # formatted_docs = format_points(relevant_docs)
#     # # Define substeps for each doc type
#     # substeps: list[StepOutput] = []
#     # docs_by_type: dict[str, list[Document]] = {}
#     # for doc in relevant_docs:
#     #     doc_type = doc.payload.get("metadata", {}).get("doc_type", "Miscellaneous")
#     #     if doc_type not in docs_by_type:
#     #         docs_by_type[doc_type] = []
#     #     docs_by_type[doc_type].append(doc)
#     # substeps += [
#     #     StepOutput(label=doc_type, details=format_docs(docs))
#     #     for doc_type, docs in docs_by_type.items()
#     # ]
#     # # https://langchain-ai.github.io/langgraph/how-tos/tool-calling/#read-state
#     # return Command(update={
#     #     # "retrieved_docs": docs,
#     #     "messages": [
#     #         ToolMessage(
#     #             formatted_docs,
#     #             tool_call_id="access_biomedical_resources",
#     #         )
#     #     ],
#     #     "steps": [
#     #         StepOutput(
#     #             label=f"📚️ {len(relevant_docs)} documents used",
#     #             substeps=substeps,
#     #         ),
#     #     ],
#     # })


# @tool
# def get_resources_info(question: str) -> str:
#     """Get information about the service and resources available at the SIB Swiss Institute of Bioinformatics.

#     Args:
#         question: The user question.

#     Returns:
#         str: Information about the resources.
#     """
#     search_embeddings = next(iter(embedding_model.embed([question])))
#     relevant_docs = vectordb.query_points(
#         collection_name=settings.docs_collection_name,
#         query=search_embeddings,
#         limit=settings.default_number_of_retrieved_docs,
#         query_filter=Filter(
#             must=[
#                 FieldCondition(
#                     key="metadata.doc_type",
#                     match=MatchValue(value="General information"),
#                 )
#             ]
#         ),
#     ).points
#     return format_points(relevant_docs)


# def format_points(docs: list[ScoredPoint]) -> str:
#     """Format a list of documents."""
#     return f"\n{'\n'.join(_format_point(doc) for doc in docs)}\n"


# def _format_point(doc: ScoredPoint) -> str:
#     """Format a single document, with special formatting based on doc type (sparql, schema)."""
#     doc_meta: dict[str, str] = (
#         doc.payload.get("metadata", {}) if doc.payload is not None else {}
#     )
#     if doc_meta.get("answer"):
#         doc_lang = ""
#         doc_type = str(doc_meta.get("doc_type", "")).lower()
#         if "query" in doc_type:
#             doc_lang = (
#                 f"sparql\n#+ endpoint: {doc_meta.get('endpoint_url', 'undefined')}"
#             )
#         elif "schema" in doc_type:
#             doc_lang = "shex"
#         return f"\n{doc.payload['page_content']}:\n\n```{doc_lang}\n{doc_meta.get('answer')}\n```\n"
#     # Generic formatting:
#     meta = "".join(f" {k}={v!r}" for k, v in doc_meta.items())
#     if meta:
#         meta = f" {meta}"
#     return f"{meta}\n{doc.payload['page_content']}\n"


# TOOLS: List[Callable[..., Any]] = [
#     access_biomedical_resources,
#     get_resources_info,
#     execute_sparql_query,
# ]


# ## Example search tool
# # from langchain_community.tools.tavily_search import TavilySearchResults
# # from langchain_core.runnables import RunnableConfig
# # from langchain_core.tools import InjectedToolArg
# # from typing_extensions import Annotated
# # from sparql_llm.agent.config import Configuration
# # async def search(
# #     query: str, *, config: Annotated[RunnableConfig, InjectedToolArg]
# # ) -> Optional[list[dict[str, Any]]]:
# #     """Search for general web results.
# #     This function performs a search using the Tavily search engine, which is designed
# #     to provide comprehensive, accurate, and trusted results. It's particularly useful
# #     for answering questions about current events.
# #     """
# #     configuration = Configuration.from_runnable_config(config)
# #     wrapped = TavilySearchResults(max_results=configuration.max_search_results)
# #     result = await wrapped.ainvoke({"query": query})
# #     return cast(list[dict[str, Any]], result)
