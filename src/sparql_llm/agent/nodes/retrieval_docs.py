"""Document retrieval using semantic similarity search."""

from typing import Any

from langchain_core.messages import HumanMessage
from langchain_core.runnables import RunnableConfig

from sparql_llm.agent.state import State, StepOutput
from sparql_llm.agent.utils import get_msg_text
from sparql_llm.config import Configuration, settings
from sparql_llm.vectordb import search_docs

EXAMPLES_FILTER = "doc_type = 'SPARQL endpoints query examples'"


async def retrieve(state: State, config: RunnableConfig) -> dict[str, list[StepOutput | HumanMessage]]:
    """Retrieve documents based on the latest message in the state.

    This function takes the current state and configuration, uses the latest query
    from the state to retrieve relevant documents with hybrid search, and returns
    the retrieved documents.

    Args:
        state (State): The current state containing queries and the retriever.
        config (RunnableConfig | None, optional): Configuration for the retrieval process.

    Returns:
        dict[str, list[StepOutput | HumanMessage]]: The retrieved documents formatted in a message, and the steps.
    """
    configuration = Configuration.from_runnable_config(config)
    user_question = get_msg_text(state.messages[-1])
    limit = configuration.search_kwargs.get("k", settings.default_number_of_retrieved_docs)

    if state.structured_question.intent == "general_information":
        docs = search_docs([user_question], "doc_type = 'General information'", limit)
    else:
        # If there are many steps or classes, reduce the number of retrieved docs for each to avoid too many docs
        steps = state.structured_question.question_steps
        # Relevant query examples
        docs = search_docs([user_question, *steps], EXAMPLES_FILTER, max(1, limit // 2) if len(steps) > 3 else limit)
        # Other relevant documentation (classes schemas, general information)
        classes = state.structured_question.extracted_classes
        if classes:
            docs += search_docs(classes, f"NOT ({EXAMPLES_FILTER})", max(1, limit // 2) if len(classes) > 3 else limit)

    # Sort docs by score (highest score first)
    docs.sort(key=lambda x: x["_relevance_score"], reverse=True)

    # Create substeps for each doc type
    substeps: list[StepOutput] = []
    docs_by_type: dict[str, list[dict[str, Any]]] = {}
    for doc in docs:
        doc_type = doc["doc_type"] or "Miscellaneous"
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


def _format_doc(doc: dict[str, Any]) -> str:
    """Format a single document, with its answer in a code block for query examples and classes schemas."""
    if doc["answer"]:
        doc_lang = ""
        endpoint_url = ""
        doc_type = doc["doc_type"].lower()
        if "query" in doc_type:
            doc_lang = f"sparql\n#+ endpoint: {doc['endpoint_url'] or 'undefined'}"
        elif "schema" in doc_type:
            doc_lang = "shex"
            endpoint_url = f" ({doc['endpoint_url'] or 'undefined endpoint'})"
        return f"\n{doc['question']}{endpoint_url}:\n\n```{doc_lang}\n{doc['answer']}\n```\n"
    return f"\n{doc['question']}\n"


def format_docs(docs: list[dict[str, Any]] | None) -> str:
    """Format a list of retrieved documents."""
    if not docs:
        return ""
    return "\n\n---\n\n".join(_format_doc(doc) for doc in docs)
