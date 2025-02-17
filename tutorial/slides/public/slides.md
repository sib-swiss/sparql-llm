## Setup

This tutorial will guide you through creating an LLM-based app step by step, you will be given pieces of code to build up the system, while we advance through the tutorial you will need to comment out or delete some previous pieces of code to avoid useless repetitions.

[Install `uv`](https://docs.astral.sh/uv/getting-started/installation/) to easily handle dependencies and run scripts

Create a new folder, you will be using this same folder along the tutorial.

Create a `.env` file with the API key for the LLM provider you will use:

```sh
GROQ_API_KEY=gsk_YYY
OPENAI_API_KEY=sk-proj-YYY
```

---

## Setup dependencies

Create a `pyproject.toml` file with this content:

```toml
[project]
name = "tutorial-sparql-agent"
version = "0.0.1"
requires-python = "==3.12.*"
dependencies = [
    "sparql-llm >=0.0.4",
    "langgraph >=0.2.73",
    "langchain >=0.3.14",
    "langchain-community >=0.3.17",
    "langchain-openai >=0.3.6",
    "langchain-groq >=0.2.4",
    "langchain-ollama >=0.2.3",
    "langchain-qdrant >=0.2.0",
    "qdrant-client >=1.13.0",
    "fastembed >=0.5.1",
    "chainlit >=2.2.1",
]
```

---

## Call a LLM

Create a `app.py` file in the same folder

```python
from langchain_groq import ChatGroq

question = "What are the rat orthologs of human TP53?"

llm = ChatGroq(
    model_name="llama-3.3-70b-versatile", 
    temperature=0,
)

resp = llm.invoke(question)
print(resp)
```

Run it with:

```sh
uv run --env-file .env app.py
```

---

## Stream a LLM response

```python
for msg in llm.stream(question):
    print(msg.content, end="")
```

---

## Easily switch the model used

```python
from langchain_core.language_models import BaseChatModel

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
    raise ValueError(f"Unknown provider: {provider}")

llm = load_chat_model("groq/llama-3.3-70b-versatile")
# llm = load_chat_model("openai/gpt-4o-mini")
```

---

## Use a local LLM

Install ollama: [ollama.com/download](https://www.ollama.com/download)

Pull the [model](https://www.ollama.com/search) you want to use (⚠️ 4GB): 

```sh
ollama pull mistral
```

Add the new provider:

```python
    if provider == "ollama":
        # https://python.langchain.com/docs/integrations/chat/ollama/
        from langchain_ollama import ChatOllama
        return ChatOllama(model=model_name, temperature=0)

llm = load_chat_model("ollama/mistral")
```

---

## Index context

Create a new script that will be run to index data from SPARQL endpoints: `index.py`

```python
endpoints: list[dict[str, str]] = [
    {
        # The URL of the SPARQL endpoint from which most info will be extracted
        "endpoint_url": "https://sparql.uniprot.org/sparql/",
        # If VoID or query examples are not in the endpoint,
        # you can provide a VoID file (local or remote URL)
        "void_file": "uniprot_void.ttl",
        "examples_file": "uniprot_examples.ttl",
    },
    { "endpoint_url": "https://www.bgee.org/sparql/" },
    { "endpoint_url": "https://sparql.omabrowser.org/sparql/" },
]
```

> Replace the values by your own endpoints URLs, and previously generated files for the VoID description and examples if applicable.

---

## Index context

Use the loaders from **[sparql-llm](https://pypi.org/project/sparql-llm/)** to easily extract and load documents for queries examples and ShEx shapes in the endpoint:

```python
from langchain_core.documents import Document
from sparql_llm import SparqlExamplesLoader, SparqlVoidShapesLoader

docs: list[Document] = []
for endpoint in endpoints:
    print(f"\n  🔎 Getting metadata for {endpoint['endpoint_url']}")
    queries_loader = SparqlExamplesLoader(
        endpoint["endpoint_url"],
        examples_file=endpoint.get("examples_file"),
        verbose=True,
    )
    docs += queries_loader.load()
    void_loader = SparqlVoidShapesLoader(
        endpoint["endpoint_url"],
        void_file=endpoint.get("void_file"),
        verbose=True,
    )
    docs += void_loader.load()
    
print(len(docs))
print(docs[0])
```

Run with:

```sh
uv run index.py
```

---

## Index context

Finally we can load these documents in the **[Qdrant](https://qdrant.tech/documentation/)**  vector store. 

We use **[FastEmbed](https://qdrant.github.io/fastembed/)** to generate embeddings locally with [open source embedding models](https://qdrant.github.io/fastembed/examples/Supported_Models/#supported-text-embedding-models).

```python
import os
from langchain_qdrant import QdrantVectorStore
from langchain_community.embeddings import FastEmbedEmbeddings

os.makedirs('data', exist_ok=True)
vectordb = QdrantVectorStore.from_documents(
    docs,
    path="data/qdrant",
    collection_name="sparql-docs",
    embedding=FastEmbedEmbeddings(
        model_name="BAAI/bge-small-en-v1.5",
        # providers=["CUDAExecutionProvider"], # Uncomment this line to use your GPUs
    ),
    force_recreate=True,
)
```

---

## Provide context to the LLM

Now we can go back to our `app.py` file.

And retrieve documents related to the user question using the vector store

```python
from langchain_qdrant import QdrantVectorStore
from langchain_community.embeddings import FastEmbedEmbeddings

vectordb = QdrantVectorStore.from_existing_collection(
    path="data/qdrant",
    collection_name="sparql-docs",
    embedding=FastEmbedEmbeddings(model_name="BAAI/bge-small-en-v1.5"),
)
retriever = vectordb.as_retriever()

number_of_docs_retrieved = 3
retrieved_docs = retriever.invoke(question, k=number_of_docs_retrieved)

print(f"📚️ Retrieved {len(retrieved_docs)} documents")
print(retrieved_docs[0])
```

---

## Provide context to the LLM

Customize the system prompt to provide the retrieved documents

```python
from langchain_core.prompts import ChatPromptTemplate

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
formatted_docs = "\n".join(doc.page_content + "\n" + doc.metadata.get("answer") for doc in retrieved_docs)
prompt_with_context = prompt_template.invoke({
    "messages": [("human", question)],
    "retrieved_docs": formatted_docs,
})


```

---

## Provide context to the LLM

We can improve how the documents are formatted when passed to the LLM:

```python
from langchain_core.documents import Document

def _format_doc(doc: Document) -> str:
    """Format our question/answer document to be provided as context to the model."""
    doc_lang = ""
    if "query" in doc.metadata.get("doc_type", ""):
        doc_lang = "sparql"
    elif "schema" in doc.metadata.get("doc_type", ""):
        doc_lang = "shex"
    return f"<document>\n{doc.page_content} ({doc.metadata.get('endpoint_url', '')}):\n\n```{doc_lang}\n{doc.metadata.get('answer')}\n```\n</document>"

formatted_docs = f"<documents>\n{'\n'.join(_format_doc(doc) for doc in retrieved_docs)}\n</documents>"
```

---

## Provide context to the LLM

We can retrieve documents related to query examples and classes shapes separately, to make sure we always get a number of examples and classes shapes.

```python
from qdrant_client.models import FieldCondition, Filter, MatchValue

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
        )
    )
    return retrieved_docs

retrieved_docs = retrieve_docs(question)
```

---

## Deploy with a nice web UI

Using [Chainlit](https://chainlit.io/)

```python
import chainlit as cl

@cl.on_message
async def on_message(msg: cl.Message):
    retrieved_docs = retrieve_docs(msg.content)
    formatted_docs = f"<documents>\n{'\n'.join(_format_doc(doc) for doc in retrieved_docs)}\n</documents>"
    async with cl.Step(name=f"{len(retrieved_docs)} relevant documents") as step:
        step.input = msg.content
        step.output = formatted_docs

    prompt_with_context = prompt_template.invoke({
        "messages": [("human", msg.content)],
        "retrieved_docs": formatted_docs,
    })
    final_answer = cl.Message(content="")
    for resp in llm.stream(prompt_with_context):
        if resp.content:
            await final_answer.stream_token(resp.content)
    await final_answer.send()
```

Deploy with:

```sh
uv run chainlit run app.py
```

---

## Creating more complex "agents"

e.g. reactive agent that can loop over themselves and use tools using [LangGraph](https://langchain-ai.github.io/langgraph/#)
