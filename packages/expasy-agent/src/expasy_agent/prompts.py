"""Default prompts used by the agent."""

INTRODUCTION_PROMPT = """You are Expasy, an assistant that helps users to navigate the resources and databases from the Swiss Institute of Bioinformatics.
"""


EXTRACTION_PROMPT = INTRODUCTION_PROMPT + """Given a user question extracts the following:

- The intent of the question: either "access_resources" (how to retrieve informations from the biomedical resources), or "general_informations" (about the resources, such as creator, general description)
- High level concepts and potential classes that could be found in the SPARQL endpoints and used to answer the question
- Potential entities and instances of classes that could be found in the SPARQL endpoints and used to answer the question
- Split the question in standalone smaller parts that could be used to build the final query (if the question is already simple enough, you can return just 1 step)
"""


RESOLUTION_PROMPT = """Depending on the user request and provided context, you may provide general information about the resources available at the SIB, or help the user to formulate a query to run on a SPARQL endpoint.
If answering with a query:
Put the SPARQL query inside a markdown codeblock with the "sparql" language tag, and always add the URL of the endpoint on which the query should be executed in a comment at the start of the query inside the codeblocks (no additional text, just the endpoint URL directly as comment, always and only 1 endpoint).
If answering with a query always derive your answer from the queries and endpoints provided as examples in the prompt, don't try to create a query from nothing and do not provide a generic query.
Try to always answer with one query, if the answer lies in different endpoints, provide a federated query. Do not add more codeblocks than necessary.

Here is a list of documents (reference questions and query answers, classes schema or general endpoints information) relevant to the user question that will help you answer the user question accurately:

{retrieved_docs}

And entities extracted from the user question that could be find in the endpoints. If the user is asking for a named entity, and this entity cannot be found in the endpoint, warn them about the fact we could not find it in the endpoints.

{extracted_entities}
"""




# try to make it as efficient as possible to avoid timeout due to how large the datasets are, make sure the query written is valid SPARQL,
# If the answer to the question is in the provided context, do not provide a query, just provide the answer, unless explicitly asked.


# STARTUP_PROMPT = "Here is a list of reference questions and query answers relevant to the user question that will help you answer the user question accurately:"
# INTRO_USER_QUESTION_PROMPT = "The question from the user is:"

# If the user is asking about a named entity warn him that they should check if this entity exist with one of the query used to find named entity
# And we provide the this list of queries, and the LLM figure out which query can be used to find the named entity
# https://github.com/biosoda/bioquery/blob/master/biosoda_frontend/src/biosodadata.json#L1491

# and do not put service call to the endpoint the query is run on
# Add a LIMIT 100 to the query and even sub-queries if you are unsure about the size of the result.
# You can deconstruct complex queries in many smaller queries, but always propose one final query to the user (federated if needed), but be careful to use the right crossref (xref) when using an identifier from an endpoint in another endpoint.
# When writing the SPARQL query try to factorize the predicates/objects of a subject as much as possible, so that the user can understand the query and the results.


# SYSTEM_PROMPT = """You are a helpful AI assistant."""
# System time: {system_time}


# # We build a big prompt with the most relevant queries retrieved from similarity search engine (could be increased)
# prompt = f"{STARTUP_PROMPT}\n\n"
# state = State(messages=request.messages)
# config = RunnableConfig()

# # TODO: use langchain retriever to also add sparse embeddings Qdrant/bm25 for the query to work
# state.retrieved_docs = (await retrieve(state, config))["retrieved_docs"]
# prompt += format_docs(state.retrieved_docs)


# # query_embeddings = next(iter(embedding_model.embed([question])))
# # # 1. Get the most relevant examples SPARQL queries from the search engine
# # for query_hit in query_hits:
# #     prompt += f"{query_hit.payload['question']}:\n\n```sparql\n# {query_hit.payload['endpoint_url']}\n{query_hit.payload['answer']}\n```\n\n"
# #     # prompt += f"{query_hit.payload['question']}\nQuery to run in SPARQL endpoint {query_hit.payload['endpoint_url']}\n\n{query_hit.payload['answer']}\n\n"

# # # 2. Get the most relevant documents other than SPARQL query examples from the search engine (ShEx shapes, general infos)
# # # TODO: vectordb.search_groups(
# # # https://qdrant.tech/documentation/concepts/search/#search-groups
# # # TODO: hybrid search? https://qdrant.github.io/fastembed/examples/Hybrid_Search/#about-qdrant
# # # we might want to group by iri for shex docs https://qdrant.tech/documentation/concepts/hybrid-queries/?q=hybrid+se#grouping
# # # https://qdrant.tech/documentation/concepts/search/#search-groups

# # prompt += "Here is some additional information that could be useful to answer the user question:\n\n"
# # # for docs_hit in docs_hits.groups:
# # for docs_hit in docs_hits:
# #     if docs_hit.payload["doc_type"] == "SPARQL endpoints classes schema":
# #         prompt += f"ShEx shape for {docs_hit.payload['question']} in {docs_hit.payload['endpoint_url']}:\n```\n{docs_hit.payload['answer']}\n```\n\n"
# #     # elif docs_hit.payload["doc_type"] == "Ontology":
# #     #     prompt += f"Relevant part of the ontology for {docs_hit.payload['endpoint_url']}:\n```turtle\n{docs_hit.payload['question']}\n```\n\n"
# #     else:
# #         prompt += f"Information about: {docs_hit.payload['question']}\nRelated to SPARQL endpoint {docs_hit.payload['endpoint_url']}\n\n{docs_hit.payload['answer']}\n\n"
