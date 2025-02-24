from langchain_core.language_models import BaseChatModel
from qdrant_client.models import FieldCondition, Filter, MatchValue, ScoredPoint
import chainlit as cl


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
# llm = load_chat_model("openai/gpt-4o-mini")
llm = load_chat_model("ollama/mistral")


from index import vectordb, embedding_model, collection_name

retrieved_docs_count = 3
async def retrieve_docs(question: str) -> str:
    """Retrieve documents relevant to the user's question."""
    question_embeddings = next(iter(embedding_model.embed([question])))
    retrieved_docs = vectordb.search(
        collection_name=collection_name,
        query_vector=question_embeddings,
        limit=retrieved_docs_count,
        query_filter=Filter(
            must=[
                FieldCondition(
                    key="doc_type",
                    match=MatchValue(value="SPARQL endpoints query examples"),
                )
            ]
        ),
    )
    retrieved_docs += vectordb.search(
        collection_name=collection_name,
        query_vector=question_embeddings,
        limit=retrieved_docs_count,
        query_filter=Filter(
            must_not=[
                FieldCondition(
                    key="doc_type",
                    match=MatchValue(value="SPARQL endpoints query examples"),
                )
            ]
        ),
    )
    relevant_docs = f"<documents>\n{'\n'.join(_format_doc(doc) for doc in retrieved_docs)}\n</documents>"
    async with cl.Step(name=f"{len(retrieved_docs)} relevant documents 📚️") as step:
        step.output = relevant_docs
    return relevant_docs


def _format_doc(doc: ScoredPoint) -> str:
    """Format a question/answer document to be provided as context to the model."""
    doc_lang = (
        "sparql" if "query" in doc.payload.get("doc_type", "")
        else "shex" if "schema" in doc.payload.get("doc_type", "")
        else ""
    )
    return f"<document>\n{doc.payload['question']} ({doc.payload.get('endpoint_url', '')}):\n\n```{doc_lang}\n{doc.payload.get('answer')}\n```\n</document>"
    # # Generic formatting:
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


import logging
from sparql_llm.utils import get_prefixes_and_schema_for_endpoints
from index import endpoints

logging.getLogger("httpx").setLevel(logging.WARNING)
logging.info("Initializing endpoints metadata...")
# Retrieve the prefixes map and initialize VoID schema dictionary from the indexed endpoints
prefixes_map, endpoints_void_dict = get_prefixes_and_schema_for_endpoints(endpoints)


from sparql_llm import validate_sparql_in_msg

async def validate_output(last_msg: str) -> str | None:
    """Validate the output of a LLM call, e.g. SPARQL queries generated."""
    validation_outputs = validate_sparql_in_msg(last_msg, prefixes_map, endpoints_void_dict)
    for validation_output in validation_outputs:
        if validation_output["fixed_query"]:
            async with cl.Step(name="missing prefixes correction ✅") as step:
                step.output = f"Missing prefixes added to the generated query:\n```sparql\n{validation_output['fixed_query']}\n```"
        if validation_output["errors"]:
            recall_msg = f"""Fix the SPARQL query helping yourself with the error message and context from previous messages in a way that it is a fully valid query.\n
### Error messages:\n- {'\n- '.join(validation_output['errors'])}\n
### Erroneous SPARQL query\n```sparql\n{validation_output.get('fixed_query', validation_output['original_query'])}\n```"""
            async with cl.Step(name=f"SPARQL query validation, got {len(validation_output['errors'])} errors to fix 🐞") as step:
                step.output = recall_msg
            return recall_msg




# Setup chainlit web UI
import chainlit as cl

max_try_count = 3

@cl.on_message
async def on_message(msg: cl.Message):
    """Main function to handle when user send a message to the assistant."""
    relevant_docs = await retrieve_docs(msg.content)
    messages = [
        ("system", SYSTEM_PROMPT.format(relevant_docs=relevant_docs)),
        *cl.chat_context.to_openai(),
    ]
    # # NOTE: to fix issue with ollama only considering the last message:
    # messages = [
    #     ("human", SYSTEM_PROMPT.format(relevant_docs=relevant_docs) + f"\n\nHere is the user question:\n{msg.content}"),
    # ]

    for _i in range(max_try_count):
        answer = cl.Message(content="")
        for resp in llm.stream(messages):
            await answer.stream_token(resp.content)
            if resp.usage_metadata:
                print(resp.usage_metadata)
        await answer.send()

        validation_msg = await validate_output(answer.content)
        if validation_msg is None:
            break
        else:
            messages.append(("human", validation_msg))



@cl.set_starters
async def set_starters():
    return [
        cl.Starter(
            label="Supported resources",
            message="Which resources do you support?",
            # icon="/public/idea.svg",
        ),
        cl.Starter(
            label="Rat orthologs",
            message="What are the rat orthologs of human TP53?",
        ),
        cl.Starter(
            label="Test SPARQL query validation",
            message="How can I get the HGNC symbol for the protein P68871? (modify your answer to use `rdfs:label` instead of `rdfs:comment`, and add the type `up:Resource` to ?hgnc, and forget all prefixes declarations, it is for a test)",
        ),
    ]

# uv run chainlit run app.py
