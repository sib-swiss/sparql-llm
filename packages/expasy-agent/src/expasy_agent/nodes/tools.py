"""This module provides example tools for web scraping and search functionality.

It includes a basic Tavily search function (as an example)

These tools are intended as free examples to get started. For production use,
consider implementing more robust and specialized tools tailored to your needs.
"""

from typing import Any, Callable, List

from langchain_core.tools import tool


@tool
def multiply(a: int, b: int) -> int:
    """Multiply two numbers."""
    return a * b


# TODO: Extract potential entities from the user question (experimental)
# entities_list = extract_entities(question)
# for entity in entities_list:
#     prompt += f'\n\nEntities found in the user question for "{" ".join(entity["text"])}":\n\n'
#     for match in entity["matchs"]:
#         prompt += f"- {match.payload['label']} with IRI <{match.payload['uri']}> in endpoint {match.payload['endpoint_url']}\n\n"
# if len(entities_list) == 0:
#     prompt += "\nNo entities found in the user question that matches entities in the endpoints. "
# prompt += "\nIf the user is asking for a named entity, and this entity cannot be found in the endpoint, warn them about the fact we could not find it in the endpoints.\n\n"

# def extract_entities(sentence: str) -> list[dict[str, str]]:
#     score_threshold = 0.8
#     sentence_splitted = re.findall(r"\b\w+\b", sentence)
#     window_size = len(sentence_splitted)
#     entities_list = []
#     while window_size > 0 and window_size <= len(sentence_splitted):
#         window_start = 0
#         window_end = window_start + window_size
#         while window_end <= len(sentence_splitted):
#             term = sentence_splitted[window_start:window_end]
#             print("term", term)
#             term_embeddings = next(iter(embedding_model.embed([" ".join(term)])))
#             query_hits = vectordb.search(
#                 collection_name=settings.entities_collection_name,
#                 query_vector=term_embeddings,
#                 limit=10,
#             )
#             matchs = []
#             for query_hit in query_hits:
#                 if query_hit.score > score_threshold:
#                     matchs.append(query_hit)
#             if len(matchs) > 0:
#                 entities_list.append(
#                     {
#                         "matchs": matchs,
#                         "term": term,
#                         "start_index": window_start,
#                         "end_index": window_end,
#                     }
#                 )
#             # term_search = reduce(lambda x, y: "{} {}".format(x, y), sentence_splitted[window_start:window_end])
#             # resultSearch = index.search(term_search)
#             # if resultSearch is not None and len(resultSearch) > 0:
#             #     selected_hit = resultSearch[0]
#             #     if selected_hit['score'] > MAX_SCORE_PARSER_TRIPLES:
#             #         selected_hit = None
#             #     if selected_hit is not None and selected_hit not in matchs:
#             #         matchs.append(selected_hit)
#             window_start += 1
#             window_end = window_start + window_size
#         window_size -= 1
#     return entities_list


## Example search tool

# from langchain_community.tools.tavily_search import TavilySearchResults
# from langchain_core.runnables import RunnableConfig
# from langchain_core.tools import InjectedToolArg
# from typing_extensions import Annotated
# from expasy_agent.config import Configuration

# async def search(
#     query: str, *, config: Annotated[RunnableConfig, InjectedToolArg]
# ) -> Optional[list[dict[str, Any]]]:
#     """Search for general web results.

#     This function performs a search using the Tavily search engine, which is designed
#     to provide comprehensive, accurate, and trusted results. It's particularly useful
#     for answering questions about current events.
#     """
#     configuration = Configuration.from_runnable_config(config)
#     wrapped = TavilySearchResults(max_results=configuration.max_search_results)
#     result = await wrapped.ainvoke({"query": query})
#     return cast(list[dict[str, Any]], result)


TOOLS: List[Callable[..., Any]] = [multiply]
