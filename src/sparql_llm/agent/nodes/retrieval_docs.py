"""Document retrieval using semantic similarity search."""

from collections.abc import Generator
from contextlib import contextmanager

from langchain_community.embeddings import FastEmbedEmbeddings
from langchain_core.callbacks import CallbackManagerForRetrieverRun
from langchain_core.documents import Document
from langchain_core.embeddings import Embeddings
from langchain_core.messages import FunctionMessage, HumanMessage
from langchain_core.runnables import RunnableConfig
from langchain_core.vectorstores import VectorStoreRetriever
from langchain_qdrant import QdrantVectorStore
from qdrant_client.models import FieldCondition, Filter, MatchValue

from sparql_llm.agent.config import Configuration, qdrant_client, settings
from sparql_llm.agent.state import State, StepOutput
from sparql_llm.agent.utils import get_msg_text

# TODO: use grouping? https://qdrant.tech/documentation/concepts/search/#grouping-api
# Which tools can I use for enrichment analysis?


async def retrieve(
    state: State, config: RunnableConfig
) -> dict[str, list[StepOutput | FunctionMessage | HumanMessage]]:
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
    user_question = get_msg_text(state.messages[-1])
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
        # For general information, we can use a larger k to get more results
        configuration.search_kwargs["k"] = configuration.search_kwargs["k"] * 2
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
            # We use the steps extracted instead of directly the user question
            for step in [user_question, *state.structured_question.question_steps]:
                # Make sure we don't add duplicate docs
                docs.extend(
                    doc
                    for doc in await retriever.ainvoke(step, config)
                    if doc.metadata.get("answer") not in {existing_doc.metadata.get("answer") for existing_doc in docs}
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
                    if doc.metadata.get("answer") not in {existing_doc.metadata.get("answer") for existing_doc in docs}
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
    substeps += [StepOutput(label=doc_type, details=format_docs(docs)) for doc_type, docs in docs_by_type.items()]
    # print(format_docs(docs))
    return {
        # "retrieved_docs": docs,
        "messages": [
            # Mistral does not support FunctionMessage
            # FunctionMessage(
            #     content=format_docs(docs),
            #     name="retrieve_docs",
            # )
            HumanMessage(
                content=format_docs(docs),
                name="retrieve_docs",
            )
        ],
        "steps": [
            StepOutput(
                label=f"📚️ {len(docs)} documents used",
                substeps=substeps,
            ),
        ],
    }


def make_dense_encoder(embedding_model: str, gpu: bool = False) -> Embeddings:
    """Connect to the configured text encoder."""
    return FastEmbedEmbeddings(
        model_name=embedding_model,
        providers=["CUDAExecutionProvider"] if gpu else None,
        # batch_size=1024,
    )


# https://python.langchain.com/docs/integrations/vectorstores/qdrant/
@contextmanager
def make_qdrant_retriever(
    configuration: Configuration,
) -> Generator["ScoredRetriever", None, None]:
    """Configure this agent to connect to a specific Qdrant index."""
    vectordb = QdrantVectorStore(
        client=qdrant_client,
        # url=settings.vectordb_url,
        # prefer_grpc=True,
        collection_name=settings.docs_collection_name,
        embedding=make_dense_encoder(settings.embedding_model),
        # sparse_embedding=FastEmbedSparse(model_name=settings.sparse_embedding_model),
        # retrieval_mode=RetrievalMode.HYBRID,
    )
    yield ScoredRetriever(vectorstore=vectordb, search_kwargs=configuration.search_kwargs)
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
        # query_em`bedding = await self.vectorstore.embeddings.aembed_query(query)

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

        docs, scores = zip(*self.vectorstore.similarity_search_with_score(query, **self.search_kwargs), strict=False)
        for doc, score in zip(docs, scores, strict=False):
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
    """Format a single document.

    Args:
        doc (Document): The document to format.

    Returns:
        str: The formatted document.
    """
    if doc.metadata.get("answer"):
        doc_lang = ""
        endpoint_url = ""
        doc_type = str(doc.metadata.get("doc_type", "")).lower()
        if "query" in doc_type:
            doc_lang = f"sparql\n#+ endpoint: {doc.metadata.get('endpoint_url', 'undefined')}"
        elif "schema" in doc_type:
            doc_lang = "shex"
            # endpoint_url = f" ({doc.metadata.get('endpoint_url', 'undefined')})"
            endpoint_url = f" ({doc.metadata.get('endpoint_url', 'undefined endpoint')})"
        return f"\n{doc.page_content}{endpoint_url}:\n\n```{doc_lang}\n{doc.metadata.get('answer')}\n```\n"

    # meta = "".join(f" {k}={v!r}" for k, v in doc.metadata.items())
    # if meta:
    #     meta = f" {meta}"
    # return f"<document{meta}>\n\n{doc.page_content}\n\n</document>"
    return f"\n{doc.page_content}\n"


def format_docs(docs: list[Document] | None) -> str:
    """Format a list of documents.

    This function takes a list of Document objects and formats them into a string.

    Args:
        docs (Optional[list[Document]]): A list of Document objects to format, or None.

    Returns:
        str: A string containing the formatted documents.
    """
    if not docs:
        return ""
    return "\n\n---\n\n".join(_format_doc(doc) for doc in docs)
