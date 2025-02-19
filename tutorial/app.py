from typing import Literal
from langchain_qdrant import QdrantVectorStore
from langchain_community.embeddings import FastEmbedEmbeddings
from langchain_core.documents import Document
from langchain_core.language_models import BaseChatModel
from langchain_core.prompts import ChatPromptTemplate
from langgraph.graph import StateGraph
from langgraph.graph.message import MessagesState
from qdrant_client.models import FieldCondition, Filter, MatchValue
import chainlit as cl

# https://docs.chainlit.io/integrations/langchain


def load_chat_model(model: str) -> BaseChatModel:
    provider, model_name = model.split("/", maxsplit=1)
    if provider == "groq":
        # https://python.langchain.com/docs/integrations/chat/groq/
        from langchain_groq import ChatGroq
        return ChatGroq(
            model_name=model_name,
            temperature=0,
        )
    if provider == "openai":
        # https://python.langchain.com/docs/integrations/chat/openai/
        from langchain_openai import ChatOpenAI
        return ChatOpenAI(
            model_name=model_name,
            temperature=0,
        )
    if provider == "ollama":
        # https://python.langchain.com/docs/integrations/chat/ollama/
        from langchain_ollama import ChatOllama
        return ChatOllama(
            model=model_name,
            temperature=0,
        )
    raise ValueError(f"Unknown provider: {provider}")

# llm = load_chat_model("groq/llama-3.3-70b-versatile")
llm = load_chat_model("openai/gpt-4o-mini")


vectordb = QdrantVectorStore.from_existing_collection(
    # path="data/qdrant",
    host="localhost",
    prefer_grpc=True,
    collection_name="sparql-docs",
    embedding=FastEmbedEmbeddings(model_name="BAAI/bge-small-en-v1.5"),
)
retriever = vectordb.as_retriever()


class AgentState(MessagesState):
    """State of the agent available inside each node."""
    relevant_docs: str
    passed_validation: bool
    try_count: int

retrieved_docs_count = 3
async def retrieve_docs(state: AgentState) -> dict[str, str]:
    """Retrieve documents relevant to the user's question."""
    last_msg = state["messages"][-1]
    retriever = vectordb.as_retriever()
    retrieved_docs = retriever.invoke(
        last_msg.content,
        k=retrieved_docs_count,
        filter=Filter(
            must=[
                FieldCondition(
                    key="metadata.doc_type",
                    match=MatchValue(value="SPARQL endpoints query examples"),
                )
            ]
        )
    )
    retrieved_docs += retriever.invoke(
        last_msg.content,
        k=retrieved_docs_count,
        filter=Filter(
            must_not=[
                FieldCondition(
                    key="metadata.doc_type",
                    match=MatchValue(value="SPARQL endpoints query examples"),
                )
            ]
        ),
    )
    relevant_docs = f"<documents>\n{'\n'.join(_format_doc(doc) for doc in retrieved_docs)}\n</documents>"
    async with cl.Step(name=f"{len(retrieved_docs)} relevant documents 📚️") as step:
        step.output = relevant_docs
    return {"relevant_docs": relevant_docs}


def _format_doc(doc: Document) -> str:
    """Format a question/answer document to be provided as context to the model."""
    doc_lang = (
        "sparql" if "query" in doc.metadata.get("doc_type", "")
        else "shex" if "schema" in doc.metadata.get("doc_type", "")
        else ""
    )
    return f"<document>\n{doc.page_content} ({doc.metadata.get('endpoint_url', '')}):\n\n```{doc_lang}\n{doc.metadata.get('answer')}\n```\n</document>"
    # # Default formatting
    # meta = "".join(f" {k}={v!r}" for k, v in doc.metadata.items())
    # if meta:
    #     meta = f" {meta}"
    # return f"<document{meta}>\n{doc.page_content}\n</document>"


SYSTEM_PROMPT = """You are an assistant that helps users to write SPARQL queries.
Put the SPARQL query inside a markdown codeblock with the "sparql" language tag, and always add the URL of the endpoint on which the query should be executed in a comment at the start of the query inside the codeblocks.
Use the queries examples and classes shapes provided in the prompt to derive your answer, don't try to create a query from nothing and do not provide a generic query.
Try to always answer with one query, if the answer lies in different endpoints, provide a federated query.
And briefly explain the query.
Here is a list of documents (reference questions and query answers, classes schema) relevant to the user question that will help you answer the user question accurately:
{relevant_docs}
"""
prompt_template = ChatPromptTemplate.from_messages([
    ("system", SYSTEM_PROMPT),
    ("placeholder", "{messages}"),
])

def call_model(state: AgentState):
    """Call the model with the retrieved documents as context."""
    prompt_with_context = prompt_template.invoke({
        "messages": state["messages"],
        "relevant_docs": state['relevant_docs'],
    })
    response = llm.invoke(prompt_with_context)
    # # Fix id of response to use the same as the rest of the messages
    # response.id = state["messages"][-1].id
    return {"messages": [response]}


import logging
from sparql_llm.utils import get_prefixes_and_schema_for_endpoints
from index import endpoints

logging.getLogger("httpx").setLevel(logging.WARNING)
logging.info("Initializing endpoints metadata...")
# Retrieve the prefixes map and initialize VoID schema dictionary from the indexed endpoints
prefixes_map, endpoints_void_dict = get_prefixes_and_schema_for_endpoints(endpoints)


from sparql_llm import validate_sparql_in_msg

async def validate_output(state: AgentState) -> dict[str, bool | list[tuple[str, str]] | int]:
    """Node to validate the output of a LLM call, e.g. SPARQL queries generated."""
    recall_messages = []
    validation_outputs = validate_sparql_in_msg(state["messages"][-1].content, prefixes_map, endpoints_void_dict)
    for validation_output in validation_outputs:
        if validation_output["fixed_query"]:
            async with cl.Step(name="missing prefixes correction ✅") as step:
                step.output = f"Missing prefixes added to the generated query:\n```sparql\n{validation_output['fixed_query']}\n```"
        if validation_output["errors"]:
            # errors_str = "- " + "\n- ".join(validation_output["errors"])
            recall_msg = f"""Fix the SPARQL query helping yourself with the error message and context from previous messages in a way that it is a fully valid query.\n
### Error messages:\n- {'\n- '.join(validation_output['errors'])}\n
### Erroneous SPARQL query\n```sparql\n{validation_output['original_query']}\n```"""
            # print(error_str, flush=True)
            async with cl.Step(name=f"SPARQL query validation, got {len(validation_output['errors'])} errors to fix 🐞") as step:
                step.output = recall_msg
            # Add a new message to ask the model to fix the error
            recall_messages.append(("human", recall_msg))
    return {
        "messages": recall_messages,
        "try_count": state.get("try_count", 0) + 1,
        "passed_validation": not recall_messages,
    }




max_try_fix_sparql = 3
def route_model_output(state: AgentState) -> Literal["__end__", "call_model"]:
    """Determine the next node based on the model's output."""
    if state["try_count"] > max_try_fix_sparql:
        return "__end__"

    # # Check for tool calls first
    # if isinstance(last_msg, AIMessage) and state["messages"][-1].tool_calls:
    #     return "tools"

    # If validation failed, we need to call the model again
    if not state["passed_validation"]:
        return "call_model"
    return "__end__"




# Define the LangGraph graph
builder = StateGraph(AgentState)

builder.add_node(retrieve_docs)
builder.add_node(call_model)
builder.add_node(validate_output)

builder.add_edge("__start__", "retrieve_docs")
builder.add_edge("retrieve_docs", "call_model")
builder.add_edge("call_model", "validate_output")
# Add a conditional edge to determine the next step after `validate_output`
builder.add_conditional_edges("validate_output", route_model_output)

graph = builder.compile()


# Setup chainlit web UI
@cl.on_message
async def on_message(msg: cl.Message):
    # config = {"configurable": {"thread_id": cl.context.session.id}}
    # cb = cl.LangchainCallbackHandler()
    print(cl.chat_context.to_openai())
    answer = cl.Message(content="")
    async for msg, metadata in graph.astream(
        # {"messages": [HumanMessage(content=msg.content)]},
        # {"messages": [("human", msg.content)]},
        {"messages": cl.chat_context.to_openai()},
        stream_mode="messages",
        # config=RunnableConfig(callbacks=[cb], **config),
    ):
        if not msg.response_metadata:
            # and msg.content and not isinstance(msg, HumanMessage) and metadata["langgraph_node"] == "call_model"
            # print(msg, metadata)
            await answer.stream_token(msg.content)
        else:
            await answer.send()
            answer = cl.Message(content="")


@cl.set_starters
async def set_starters():
    return [
        cl.Starter(
            label="Rat orthologs",
            message="What are the rat orthologs of human TP53?",
            # icon="/public/idea.svg",
        ),
        cl.Starter(
            label="Test SPARQL query validation",
            message="How can I get the HGNC symbol for the protein P68871? (modify your answer to use `rdfs:label` instead of `rdfs:comment`, and add the type `up:Resource` to ?hgnc, and purposefully forget 2 prefixes declarations, it is for a test)",
        ),
    ]

# uv run chainlit run app.py
