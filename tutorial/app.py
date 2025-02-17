from langchain_core.language_models import BaseChatModel

# question = "What are the rat orthologs of human TP53?"

def load_chat_model(model: str) -> BaseChatModel:
    provider, model_name = model.split("/", maxsplit=1)
    if provider == "groq":
        # https://python.langchain.com/docs/integrations/chat/groq/
        from langchain_groq import ChatGroq
        return ChatGroq(model_name=model_name, temperature=0)
    if provider == "openai":
        # https://python.langchain.com/docs/integrations/chat/openai/
        from langchain_openai import ChatOpenAI
        return ChatOpenAI(model_name=model_name, temperature=0)
    if provider == "ollama":
        # https://python.langchain.com/docs/integrations/chat/ollama/
        from langchain_ollama import ChatOllama
        return ChatOllama(model=model_name, temperature=0)
    raise ValueError(f"Unknown provider: {provider}")

llm = load_chat_model("groq/llama-3.3-70b-versatile")
# llm = load_chat_model("openai/gpt-4o-mini")
# llm = load_chat_model("ollama/mistral")

from langchain_qdrant import QdrantVectorStore
from langchain_community.embeddings import FastEmbedEmbeddings

vectordb = QdrantVectorStore.from_existing_collection(
    path="data/qdrant",
    collection_name="sparql-docs",
    embedding=FastEmbedEmbeddings(model_name="BAAI/bge-small-en-v1.5"),
)

retriever = vectordb.as_retriever()
number_of_docs_retrieved = 5

# retrieved_docs = retriever.invoke(question, k=number_of_docs_retrieved)

from qdrant_client.models import FieldCondition, Filter, MatchValue
from langchain_core.documents import Document

def retrieve_docs(question: str) -> list[Document]:
    retrieved_docs = retriever.invoke(
        question,
        k=number_of_docs_retrieved,
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
        question,
        k=number_of_docs_retrieved,
        filter=Filter(
            must_not=[
                FieldCondition(
                    key="metadata.doc_type",
                    match=MatchValue(value="SPARQL endpoints query examples"),
                )
            ]
        ),
    )
    return retrieved_docs

# retrieved_docs = retrieve_docs(question)

# print(f"📚️ Retrieved {len(retrieved_docs)} documents")
# # print(retrieved_docs)
# for doc in retrieved_docs:
#     print(f"{doc.metadata.get('doc_type')} - {doc.metadata.get('endpoint_url')} - {doc.page_content}")


from langchain_core.prompts import ChatPromptTemplate

def _format_doc(doc: Document) -> str:
    """Format a question/answer document to be provided as context to the model."""
    doc_lang = (
        "sparql" if "query" in doc.metadata.get("doc_type", "")
        else "shex" if "schema" in doc.metadata.get("doc_type", "")
        else ""
    )
    return f"<document>\n{doc.page_content} ({doc.metadata.get('endpoint_url')}):\n\n```{doc_lang}\n{doc.metadata.get('answer')}\n```\n</document>"


SYSTEM_PROMPT = """You are an assistant that helps users to write SPARQL queries.
Put the SPARQL query inside a markdown codeblock with the "sparql" language tag, and always add the URL of the endpoint on which the query should be executed in a comment at the start of the query inside the codeblocks.
Use the queries examples and classes shapes provided in the prompt to derive your answer, don't try to create a query from nothing and do not provide a generic query.
Try to always answer with one query, if the answer lies in different endpoints, provide a federated query.
And briefly explain the query.
Here is a list of documents (reference questions and query answers, classes schema) relevant to the user question that will help you answer the user question accurately:
{retrieved_docs}
"""
prompt_template = ChatPromptTemplate.from_messages([
        ("system", SYSTEM_PROMPT),
        ("placeholder", "{messages}"),
])

# formatted_docs = "\n".join(doc.page_content + "\n" + doc.metadata.get("answer") for doc in retrieved_docs)
# formatted_docs = f"<documents>\n{'\n'.join(_format_doc(doc) for doc in retrieved_docs)}\n</documents>"
# prompt_with_context = prompt_template.invoke({
#     "messages": [("human", question)],
#     "retrieved_docs": formatted_docs,
# })

# print(str("\n".join(prompt_with_context.messages)))

# resp = llm.invoke("What are the rat orthologs of human TP53?")
# print(resp)

# for msg in llm.stream(prompt_with_context):
#     print(msg.content, end='')


import chainlit as cl

@cl.on_message
async def on_message(msg: cl.Message):
    retrieved_docs = retrieve_docs(msg.content)
    formatted_docs = f"<documents>\n{'\n'.join(_format_doc(doc) for doc in retrieved_docs)}\n</documents>"
    async with cl.Step(name=f"{len(retrieved_docs)} relevant documents") as step:
        # step.input = msg.content
        step.output = formatted_docs

    prompt_with_context = prompt_template.invoke({
        "messages": [("human", msg.content)],
        "retrieved_docs": formatted_docs,
    })
    final_answer = cl.Message(content="")
    for resp in llm.stream(prompt_with_context):
        await final_answer.stream_token(resp.content)
    await final_answer.send()
