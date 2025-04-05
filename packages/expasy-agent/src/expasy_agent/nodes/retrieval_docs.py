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
from langchain_qdrant import QdrantVectorStore
from qdrant_client.models import FieldCondition, Filter, MatchValue

from expasy_agent.config import Configuration, settings
from expasy_agent.state import State, StepOutput
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
    user_question = get_message_text(state.messages[-1])
    docs: list[Document] = []

    if state.structured_question.intent == "general_information":
        # Handles when user asks for general informations about the resources
        configuration.search_kwargs["filter"] = Filter(
            must=[
                FieldCondition(
                    key="metadata.doc_type",
                    match=MatchValue(value="General information"),
                )
            ]
        )
        with make_qdrant_retriever(configuration) as retriever:
            docs += await retriever.ainvoke(user_question, config)
    else:
        # Handles when user asks for access to resources
        configuration.search_kwargs["filter"] = Filter(
            must=[
                FieldCondition(
                    key="metadata.doc_type",
                    match=MatchValue(value="SPARQL endpoints query examples"),
                )
            ]
        )
        with make_qdrant_retriever(configuration) as retriever:
            for step in [user_question, *state.structured_question.question_steps]:
                # Make sure we don't add duplicate docs
                docs.extend(
                    doc
                    for doc in await retriever.ainvoke(step, config)
                    if doc.metadata.get("answer")
                    not in {
                        existing_doc.metadata.get("answer") for existing_doc in docs
                    }
                )

        # Search anything else that is not a query example, e.g. SPARQL endpoints classes schema
        configuration.search_kwargs["filter"] = Filter(
            must_not=[
                FieldCondition(
                    key="metadata.doc_type",
                    match=MatchValue(value="SPARQL endpoints query examples"),
                )
            ]
        )
        with make_qdrant_retriever(configuration) as retriever:
            for extracted_class in state.structured_question.extracted_classes:
                docs.extend(
                    doc
                    for doc in await retriever.ainvoke(extracted_class, config)
                    if doc.metadata.get("answer")
                    not in {
                        existing_doc.metadata.get("answer") for existing_doc in docs
                    }
                )

    # Sort docs by score (highest score first)
    # docs.sort(key=lambda x: x.metadata.get("score", 0), reverse=True)

    # Create substeps for each doc type
    substeps: list[StepOutput] = []
    docs_by_type: dict[str, list[Document]] = {}
    for doc in docs:
        doc_type = doc.metadata.get("doc_type", "Miscellaneous")
        if doc_type not in docs_by_type:
            docs_by_type[doc_type] = []
        docs_by_type[doc_type].append(doc)
    substeps += [
        StepOutput(label=doc_type, details=format_docs(docs))
        for doc_type, docs in docs_by_type.items()
    ]

    return {
        "retrieved_docs": docs,
        "steps": [
            StepOutput(
                label=f"📚️ Using {len(docs)} documents",
                substeps=substeps,
            ),
        ],
    }


## Encoder constructors


def make_dense_encoder(embedding_model: str, gpu: bool = False) -> Embeddings:
    """Connect to the configured text encoder."""
    return FastEmbedEmbeddings(
        model_name=embedding_model,
        providers=["CUDAExecutionProvider"] if gpu else None,
        # batch_size=1024,
    )


# def make_vectordb(collection_name: str, gpu: bool = False):
#     """Connect to the configured vector database."""
#     return QdrantVectorStore(
#         client=qdrant_client,
#         collection_name=collection_name,
#         embedding=make_text_encoder(settings.embedding_model, gpu),
#         sparse_embedding=FastEmbedSparse(model_name=settings.sparse_embedding_model, batch_size=1024),
#         retrieval_mode=RetrievalMode.HYBRID,
#     )

## Retriever constructors


# https://python.langchain.com/docs/integrations/vectorstores/qdrant/
@contextmanager
def make_qdrant_retriever(
    configuration: Configuration,
) -> Generator["ScoredRetriever", None, None]:
    """Configure this agent to connect to a specific Qdrant index."""
    vectordb = QdrantVectorStore.from_existing_collection(
        # client=qdrant_client,
        url=settings.vectordb_url,
        prefer_grpc=True,
        collection_name=settings.docs_collection_name,
        embedding=make_dense_encoder(settings.embedding_model),
        # sparse_embedding=FastEmbedSparse(model_name=settings.sparse_embedding_model),
        # retrieval_mode=RetrievalMode.HYBRID,
    )
    yield ScoredRetriever(
        vectorstore=vectordb, search_kwargs=configuration.search_kwargs
    )
    # yield vectordb.as_retriever(search_kwargs=configuration.search_kwargs)


# TODO: to avoid generating twice embeddings for the same query? we could use a custom vectorstore
# vectordb.asimilarity_search_with_score_by_vector()
# https://python.langchain.com/docs/how_to/custom_retriever/#example
# https://api.python.langchain.com/en/latest/_modules/langchain_core/vectorstores.html#VectorStore.as_retriever
# VectorStoreRetriever(vectorstore=self, tags=tags, **kwargs)
class ScoredRetriever(VectorStoreRetriever):
    """Custom retriever for different types of documents for context about SPARQL endpoints."""

    async def _aget_relevant_documents(
        self, query: str, *, run_manager: CallbackManagerForRetrieverRun
    ) -> list[Document]:
        # # query_embedding = await self.vectorstore._aembed_query(query)
        # query_embedding = await self.vectorstore.embeddings.aembed_query(query)

        # docs, scores = await self.vectorstore.asimilarity_search_with_score(
        #     query_embedding,
        #     k,
        #     filter=filter,
        #     search_params=search_params,
        #     offset=offset,
        #     score_threshold=score_threshold,
        #     consistency=consistency,
        #     **kwargs,
        # )

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


## Document formatting


def _format_doc(doc: Document) -> str:
    """Format a single document as XML.

    Args:
        doc (Document): The document to format.

    Returns:
        str: The formatted document as an XML string.
    """
    if doc.metadata.get("answer"):
        doc_lang = ""
        doc_type = str(doc.metadata.get("doc_type", "")).lower()
        if "query" in doc_type:
            doc_lang = f"sparql\n#+ endpoint: {doc.metadata.get('endpoint_url', 'undefined')}"
        elif "schema" in doc_type:
            doc_lang = "shex"
        return f"<document>\n{doc.page_content}:\n\n```{doc_lang}\n{doc.metadata.get('answer')}\n```\n</document>"

    meta = "".join(f" {k}={v!r}" for k, v in doc.metadata.items())
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
