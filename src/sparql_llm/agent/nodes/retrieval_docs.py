"""Document retrieval using semantic similarity search."""

from langchain_core.messages import HumanMessage
from langchain_core.runnables import RunnableConfig
from qdrant_client.models import FieldCondition, Filter, MatchValue, ScoredPoint

from sparql_llm.agent.state import State, StepOutput
from sparql_llm.agent.utils import get_msg_text
from sparql_llm.config import Configuration, embedding_model, qdrant_client, settings

# TODO: use grouping? https://qdrant.tech/documentation/concepts/search/#grouping-api
# Which tools can I use for enrichment analysis?


async def retrieve(state: State, config: RunnableConfig) -> dict[str, list[StepOutput | HumanMessage]]:
    """Retrieve documents based on the latest message in the state.

    This function takes the current state and configuration, uses the latest query
    from the state to retrieve relevant documents using qdrant_client, and returns
    the retrieved documents.

    Args:
        state (State): The current state containing queries and the retriever.
        config (RunnableConfig | None, optional): Configuration for the retrieval process.

    Returns:
        dict[str, list[ScoredPoint]]: A dictionary with a single key "retrieved_docs"
        containing a list of retrieved ScoredPoint objects.
    """
    configuration = Configuration.from_runnable_config(config)
    user_question = get_msg_text(state.messages[-1])
    docs: list[ScoredPoint] = []

    # Prepare all search queries
    search_queries: list[str] = []

    if state.structured_question.intent == "general_information":
        # For general information, search with user question
        search_queries.append(user_question)
        search_filter = Filter(
            must=[
                FieldCondition(
                    key="doc_type",
                    match=MatchValue(value="General information"),
                )
            ]
        )
        limit = configuration.search_kwargs.get("k", settings.default_number_of_retrieved_docs) * 2

        # Generate embeddings for all queries at once
        for search_embedding in embedding_model.embed(search_queries):
            try:
                docs.extend(
                    doc
                    for doc in qdrant_client.query_points(
                        query=search_embedding,
                        collection_name=settings.docs_collection_name,
                        limit=limit,
                        query_filter=search_filter,
                    ).points
                    if doc.payload
                )
            except Exception as _e:
                # If error, probably due to no results, so retry without filter
                docs.extend(
                    doc
                    for doc in qdrant_client.query_points(
                        query=search_embedding,
                        collection_name=settings.docs_collection_name,
                        limit=limit,
                    ).points
                    if doc.payload
                )
    else:
        # Handles when user asks for access to resources
        # Prepare search queries: user question + extracted steps + extracted classes
        search_queries = [
            user_question,
            *state.structured_question.question_steps,
            *state.structured_question.extracted_classes,
        ]
        limit = configuration.search_kwargs.get("k", settings.default_number_of_retrieved_docs)

        # Generate embeddings for all queries at once and perform searches
        for search_embedding in embedding_model.embed(search_queries):
            # Get SPARQL example queries
            docs.extend(
                doc
                for doc in qdrant_client.query_points(
                    query=search_embedding,
                    collection_name=settings.docs_collection_name,
                    limit=limit,
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
                not in {existing_doc.payload.get("answer") if existing_doc.payload else None for existing_doc in docs}
            )

            # Get other relevant documentation (classes schemas, general information)
            docs.extend(
                doc
                for doc in qdrant_client.query_points(
                    query=search_embedding,
                    collection_name=settings.docs_collection_name,
                    limit=limit,
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
                not in {existing_doc.payload.get("answer") if existing_doc.payload else None for existing_doc in docs}
            )

    # Sort docs by score (highest score first)
    docs.sort(key=lambda x: x.score, reverse=True)

    # Create substeps for each doc type
    substeps: list[StepOutput] = []
    docs_by_type: dict[str, list[ScoredPoint]] = {}
    for doc in docs:
        doc_type = doc.payload.get("doc_type", "Miscellaneous") if doc.payload else "Miscellaneous"
        if doc_type not in docs_by_type:
            docs_by_type[doc_type] = []
        docs_by_type[doc_type].append(doc)
    substeps += [
        StepOutput(label=doc_type, details=format_docs(docs_list)) for doc_type, docs_list in docs_by_type.items()
    ]

    return {
        "messages": [
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


## Document formatting


def _format_doc(doc: ScoredPoint) -> str:
    """Format a single document.

    Args:
        doc (ScoredPoint): The document to format.

    Returns:
        str: The formatted document.
    """
    if not doc.payload:
        return ""
    page_content = doc.payload.get("question", "")
    if doc.payload.get("answer"):
        doc_lang = ""
        endpoint_url = ""
        doc_type = str(doc.payload.get("doc_type", "")).lower()
        if "query" in doc_type:
            doc_lang = f"sparql\n#+ endpoint: {doc.payload.get('endpoint_url', 'undefined')}"
        elif "schema" in doc_type:
            doc_lang = "shex"
            endpoint_url = f" ({doc.payload.get('endpoint_url', 'undefined endpoint')})"
        return f"\n{page_content}{endpoint_url}:\n\n```{doc_lang}\n{doc.payload.get('answer')}\n```\n"

    return f"\n{page_content}\n"


def format_docs(docs: list[ScoredPoint] | None) -> str:
    """Format a list of documents.

    This function takes a list of ScoredPoint objects and formats them into a string.

    Args:
        docs (Optional[list[ScoredPoint]]): A list of ScoredPoint objects to format, or None.

    Returns:
        str: A string containing the formatted documents.
    """
    if not docs:
        return ""
    return "\n\n---\n\n".join(_format_doc(doc) for doc in docs)
