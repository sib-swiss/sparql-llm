"""Manage the configuration of various retrievers.

This module provides functionality to create and manage retrievers for different
vector store backends, specifically Qdrant.
"""

from contextlib import contextmanager
from typing import Generator, Optional

from langchain_community.embeddings import FastEmbedEmbeddings
from langchain_core.callbacks import CallbackManagerForRetrieverRun
from langchain_core.documents import Document
from langchain_core.embeddings import Embeddings
from langchain_core.runnables import RunnableConfig
from langchain_core.vectorstores import VectorStoreRetriever
from langchain_qdrant import FastEmbedSparse, QdrantVectorStore, RetrievalMode
from qdrant_client.models import FieldCondition, Filter, MatchValue

from expasy_agent.configuration import Configuration, IndexConfiguration
from expasy_agent.state import State
from expasy_agent.utils import get_message_text


async def retrieve(state: State, config: RunnableConfig) -> dict[str, list[Document]]:
    """Retrieve documents based on the latest message in the state.

    This function takes the current state and configuration, uses the latest query
    from the state to retrieve relevant documents using the retriever, and returns
    the retrieved documents.

    Args:
        state (State): The current state containing queries and the retriever.
        config (RunnableConfig | None, optional): Configuration for the retrieval process.

    Returns:
        dict[str, list[Document]]: A dictionary with a single key "retrieved_docs"
        containing a list of retrieved Document objects.
    """
    configuration = Configuration.from_runnable_config(config)
    human_input = get_message_text(state.messages[-1])
    # print("human_input", human_input)
    # Search SPARQL query examples
    configuration.search_kwargs["filter"] = Filter(
        must=[
            FieldCondition(
                key="metadata.doc_type",
                match=MatchValue(value="SPARQL endpoints query examples"),
            )
        ]
    )
    with make_retriever(configuration) as retriever:
        example_queries_docs = await retriever.ainvoke(human_input, config)

    # Search anything else that is not a query example, e.g. SPARQL endpoints classes schema
    configuration.search_kwargs["filter"] = Filter(
        must_not=[
            FieldCondition(
                key="metadata.doc_type",
                match=MatchValue(value="SPARQL endpoints query examples"),
            )
        ]
    )
    with make_retriever(configuration) as retriever:
        other_docs = await retriever.ainvoke(human_input, config)
    return {"retrieved_docs": example_queries_docs + other_docs}


## Encoder constructors

def make_text_encoder(embedding_model: str) -> Embeddings:
    """Connect to the configured text encoder."""
    return FastEmbedEmbeddings(model_name=embedding_model)
    # provider, model = embedding_model.split("/", maxsplit=1)
    # match provider:
    #     case "cohere":
    #         from langchain_cohere import CohereEmbeddings
    #         return CohereEmbeddings(model=model)  # type: ignore
    #     case _:
    #         raise ValueError(f"Unsupported embedding provider: {provider}")


## Retriever constructors

# https://python.langchain.com/docs/integrations/vectorstores/qdrant/
@contextmanager
def make_qdrant_retriever(
    configuration: IndexConfiguration, embedding_model: Embeddings
) -> Generator["ScoredRetriever", None, None]:
    """Configure this agent to connect to a specific Qdrant index."""
    vectordb = QdrantVectorStore.from_existing_collection(
        url=configuration.vectordb_url,
        # host="vectordb",
        collection_name=configuration.collection_name,
        embedding=embedding_model,
        # sparse_embedding=FastEmbedSparse(model_name=configuration.sparse_embedding_model),
        # retrieval_mode=RetrievalMode.HYBRID,
        prefer_grpc=True,
    )
    yield ScoredRetriever(vectorstore=vectordb, search_kwargs=configuration.search_kwargs)
    # yield vectordb.as_retriever(search_kwargs=configuration.search_kwargs)

# https://python.langchain.com/docs/how_to/custom_retriever/#example
# https://api.python.langchain.com/en/latest/_modules/langchain_core/vectorstores.html#VectorStore.as_retriever
# VectorStoreRetriever(vectorstore=self, tags=tags, **kwargs)
class ScoredRetriever(VectorStoreRetriever):
    """Custom retriever for different types of documents for context about SPARQL endpoints."""

    async def _aget_relevant_documents(
        self, query: str, *, run_manager: CallbackManagerForRetrieverRun
    ) -> list[Document]:
        docs, scores = zip(
            *self.vectorstore.similarity_search_with_score(query, **self.search_kwargs)
        )
        for doc, score in zip(docs, scores):
            doc.metadata["score"] = score
        return list(docs)
        # # Search SPARQL query examples
        # example_queries_docs, scores = zip(
        #     *self.vectorstore.similarity_search_with_score(
        #         query=query,
        #         filter=Filter(
        #             must=[
        #                 FieldCondition(
        #                     key="metadata.doc_type",
        #                     match=MatchValue(value="SPARQL endpoints query examples"),
        #                 )
        #             ]
        #         ),
        #         **self.search_kwargs
        #     )
        # )
        # for doc, score in zip(example_queries_docs, scores):
        #     doc.metadata["score"] = score
        # # Anything that is not a query example, e.g. SPARQL endpoints classes schema
        # other_docs, scores = zip(
        #     *self.vectorstore.similarity_search_with_score(
        #         query=query,
        #         filter=Filter(
        #             must_not=[
        #                 FieldCondition(
        #                     key="metadata.doc_type",
        #                     match=MatchValue(value="SPARQL endpoints query examples"),
        #                 )
        #             ]
        #         ),
        #         **self.search_kwargs
        #     )
        # )
        # for doc, score in zip(other_docs, scores):
        #     doc.metadata["score"] = score
        # return list(example_queries_docs) + list(other_docs)


@contextmanager
def make_retriever(configuration: Configuration) -> Generator[VectorStoreRetriever, None, None]:
    """Create a retriever for the agent, based on the current configuration."""
    embedding_model = make_text_encoder(configuration.embedding_model)
    # user_id = configuration.user_id
    # if not user_id:
    #     raise ValueError("Please provide a valid user_id in the configuration.")
    match configuration.retriever_provider:
        case "qdrant":
            with make_qdrant_retriever(configuration, embedding_model) as retriever:
                yield retriever
        # case "mongodb":
        #     with make_mongodb_retriever(configuration, embedding_model) as retriever:
        #         yield retriever
        case _:
            raise ValueError(
                "Unrecognized retriever_provider in configuration. "
                f"Expected one of: {', '.join(Configuration.__annotations__['retriever_provider'].__args__)}\n"
                f"Got: {configuration.retriever_provider}"
            )


## Document formatting

def _format_doc(doc: Document) -> str:
    """Format a single document as XML.

    Args:
        doc (Document): The document to format.

    Returns:
        str: The formatted document as an XML string.
    """
    metadata = doc.metadata or {}
    if doc.metadata.get("answer"):
        endpoint_info = f" ({doc.metadata.get('endpoint_url')})" if doc.metadata.get("endpoint_url") else ""
        return f"<document>\n{doc.page_content}{endpoint_info}:\n{doc.metadata.get('answer')}\n</document>"

    meta = "".join(f" {k}={v!r}" for k, v in metadata.items())
    if meta:
        meta = f" {meta}"
    return f"<document{meta}>\n{doc.page_content}\n</document>"


def format_docs(docs: Optional[list[Document]]) -> str:
    """Format a list of documents as XML.

    This function takes a list of Document objects and formats them into a single XML string.

    Args:
        docs (Optional[list[Document]]): A list of Document objects to format, or None.

    Returns:
        str: A string containing the formatted documents in XML format.

    Examples:
        >>> docs = [Document(page_content="Hello"), Document(page_content="World")]
        >>> print(format_docs(docs))
        <documents>
        <document>
        Hello
        </document>
        <document>
        World
        </document>
        </documents>

        >>> print(format_docs(None))
        <documents></documents>
    """
    if not docs:
        return "<documents></documents>"
    formatted = "\n".join(_format_doc(doc) for doc in docs)
    return f"""<documents>
{formatted}
</documents>"""

GET_PREFIXES_QUERY = """PREFIX sh: <http://www.w3.org/ns/shacl#>
PREFIX rdfs: <http://www.w3.org/2000/01/rdf-schema#>
SELECT DISTINCT ?prefix ?namespace
WHERE {
    [] sh:namespace ?namespace ;
        sh:prefix ?prefix .
} ORDER BY ?prefix"""


# @contextmanager
# def make_elastic_retriever(
#     configuration: IndexConfiguration, embedding_model: Embeddings
# ) -> Generator[VectorStoreRetriever, None, None]:
#     """Configure this agent to connect to a specific elastic index."""
#     from langchain_elasticsearch import ElasticsearchStore

#     connection_options = {}
#     if configuration.retriever_provider == "elastic-local":
#         connection_options = {
#             "es_user": os.environ["ELASTICSEARCH_USER"],
#             "es_password": os.environ["ELASTICSEARCH_PASSWORD"],
#         }
#     else:
#         connection_options = {"es_api_key": os.environ["ELASTICSEARCH_API_KEY"]}
#     vstore = ElasticsearchStore(
#         **connection_options,  # type: ignore
#         es_url=os.environ["ELASTICSEARCH_URL"],
#         index_name="langchain_index",
#         embedding=embedding_model,
#     )
#     search_kwargs = configuration.search_kwargs
#     # search_filter = search_kwargs.setdefault("filter", [])
#     # search_filter.append({"term": {"metadata.user_id": configuration.user_id}})
#     yield vstore.as_retriever(search_kwargs=search_kwargs)

# @contextmanager
# def make_pinecone_retriever(
#     configuration: IndexConfiguration, embedding_model: Embeddings
# ) -> Generator[VectorStoreRetriever, None, None]:
#     """Configure this agent to connect to a specific pinecone index."""
#     from langchain_pinecone import PineconeVectorStore

#     search_kwargs = configuration.search_kwargs
#     # search_filter = search_kwargs.setdefault("filter", {})
#     # search_filter.update({"user_id": configuration.user_id})
#     vstore = PineconeVectorStore.from_existing_index(
#         os.environ["PINECONE_INDEX_NAME"], embedding=embedding_model
#     )
#     yield vstore.as_retriever(search_kwargs=search_kwargs)

# @contextmanager
# def make_mongodb_retriever(
#     configuration: IndexConfiguration, embedding_model: Embeddings
# ) -> Generator[VectorStoreRetriever, None, None]:
#     """Configure this agent to connect to a specific MongoDB Atlas index & namespaces."""
#     from langchain_mongodb.vectorstores import MongoDBAtlasVectorSearch

#     vstore = MongoDBAtlasVectorSearch.from_connection_string(
#         os.environ["MONGODB_URI"],
#         namespace="langgraph_retrieval_agent.default",
#         embedding=embedding_model,
#     )
#     search_kwargs = configuration.search_kwargs
#     # pre_filter = search_kwargs.setdefault("pre_filter", {})
#     # pre_filter["user_id"] = {"$eq": configuration.user_id}
#     yield vstore.as_retriever(search_kwargs=search_kwargs)
