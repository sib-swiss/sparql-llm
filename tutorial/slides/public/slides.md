## Introduction

In this tutorial, you'll learn how to build an LLM-powered app that assists in writing SPARQL queries, step by step.

As we progress, you'll be provided with code snippets to gradually construct the system. Note that some earlier code may need to be modified or removed to prevent redundancy, ensuring a clean and efficient implementation.

---

## Setup

[Install `uv`](https://docs.astral.sh/uv/getting-started/installation/) to easily handle dependencies and run scripts

Create a new folder, you will be using this same folder along the tutorial.

Create a `.env` file with the API key for the LLM provider you will use:

```sh
GROQ_API_KEY=gsk_YYY
OPENAI_API_KEY=sk-proj-YYY
```

> You can get a [free API key on groq.com](https://console.groq.com/keys) after logging in with GitHub or Google. This gives you access to [various open-source models](https://groq.com/pricing/) with a limit of 6k tokens per minute.

---

## Setup vector store

Deploy a **[Qdrant](https://qdrant.tech/documentation/)** vector store using docker:

```sh
docker run -d -p 6333:6333 -p 6334:6334 -v $(pwd)/data/qdrant:/qdrant/storage qdrant/qdrant
```

If you don't have docker you can try [download and deploy the binary](https://github.com/qdrant/qdrant/releases/tag/v1.13.4) for your platform (might require installing additional dependencies though)

> Using in-memory vector store is also an option, but limited to 1 thread, with high risk of conflicts and no dashboard.

---

## Setup dependencies

Create a `pyproject.toml` file with this content:

```toml
[project]
name = "tutorial-sparql-agent"
version = "0.0.1"
requires-python = "==3.12.*"
dependencies = [
    "sparql-llm >=0.0.5",
    "langchain >=0.3.19",
    "langchain-community >=0.3.17",
    "langchain-openai >=0.3.6",
    "langchain-groq >=0.2.4",
    "langchain-ollama >=0.2.3",
    "langchain-qdrant >=0.2.0",
    "qdrant-client >=1.13.0",
    "fastembed >=0.5.1",
    "chainlit >=2.2.1",
    "langgraph >=0.2.73",
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

def index_endpoints():
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
    print(f"✅ {len(docs)} documents indexed")
    print(docs[0])

if __name__ == "__main__":
    index_endpoints()
```

Run with:

```sh
uv run index.py
```

---

## Index context

Finally we can load these documents in the **[Qdrant](https://qdrant.tech/documentation/)** vector store. 

We use **[FastEmbed](https://qdrant.github.io/fastembed/)** to generate embeddings locally with [open source embedding models](https://qdrant.github.io/fastembed/examples/Supported_Models/#supported-text-embedding-models).

```python
from langchain_qdrant import QdrantVectorStore
from langchain_community.embeddings import FastEmbedEmbeddings

vectordb = QdrantVectorStore.from_documents(
    docs,
    host="localhost",
    prefer_grpc=True,
    # path="data/qdrant", # if not using Qdrant as a service
    collection_name="sparql-docs",
    embedding=FastEmbedEmbeddings(
        model_name="BAAI/bge-small-en-v1.5",
        # providers=["CUDAExecutionProvider"], # Replace the fastembed dependency with fastembed-gpu to use your GPUs
    ),
    force_recreate=True,
)
```

> Checkout indexed docs at http://localhost:6333/dashboard

---

## Provide context to the LLM

Now we can go back to our `app.py` file.

And retrieve documents related to the user question using the vector store

```python
from langchain_qdrant import QdrantVectorStore
from langchain_community.embeddings import FastEmbedEmbeddings

vectordb = QdrantVectorStore.from_existing_collection(
    host="localhost",
    prefer_grpc=True,
    collection_name="sparql-docs",
    embedding=FastEmbedEmbeddings(model_name="BAAI/bge-small-en-v1.5"),
)
retriever = vectordb.as_retriever()

retrieved_docs_count = 3
retrieved_docs = retriever.invoke(question, k=retrieved_docs_count)
relevant_docs = "\n".join(doc.page_content + "\n" + doc.metadata.get("answer") for doc in retrieved_docs)

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
{relevant_docs}
"""
prompt_template = ChatPromptTemplate.from_messages([
        ("system", SYSTEM_PROMPT),
        ("placeholder", "{messages}"),
])
prompt_with_context = prompt_template.invoke({
    "messages": [("human", question)],
    "relevant_docs": relevant_docs,
})
```

---

## Provide context to the LLM

We can improve how the documents are formatted when passed to the LLM:

```python
from langchain_core.documents import Document

def _format_doc(doc: Document) -> str:
    """Format our question/answer document to be provided as context to the model."""
    doc_lang = (
        "sparql" if "query" in doc.metadata.get("doc_type", "")
        else "shex" if "schema" in doc.metadata.get("doc_type", "")
        else ""
    )
    return f"<document>\n{doc.page_content} ({doc.metadata.get('endpoint_url', '')}):\n\n```{doc_lang}\n{doc.metadata.get('answer')}\n```\n</document>"

relevant_docs = f"<documents>\n{'\n'.join(_format_doc(doc) for doc in retrieved_docs)}\n</documents>"
```

---

## Provide context to the LLM

We can retrieve documents related to query examples and classes shapes separately, to make sure we always get a number of examples and classes shapes.

```python
from qdrant_client.models import FieldCondition, Filter, MatchValue

def retrieve_docs(question: str) -> str:
    retrieved_docs = retriever.invoke(
        question,
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
        question,
        k=retrieved_docs_count,
        filter=Filter(
            must_not=[
                FieldCondition(
                    key="metadata.doc_type",
                    match=MatchValue(value="SPARQL endpoints query examples"),
                )
            ]
        )
    )
    return f"<documents>\n{'\n'.join(_format_doc(doc) for doc in retrieved_docs)}\n</documents>"

relevant_docs = retrieve_docs(question)
```

---

## Deploy with a nice web UI

Using [Chainlit](https://chainlit.io/)

```python
import chainlit as cl

@cl.on_message
async def on_message(msg: cl.Message):
    relevant_docs = retrieve_docs(msg.content)
    async with cl.Step(name="relevant documents 📚️") as step:
        step.output = relevant_docs
    prompt_with_context = prompt_template.invoke({
        "messages": [("human", msg.content)],
        "relevant_docs": relevant_docs,
    })
    final_answer = cl.Message(content="")
    for resp in llm.stream(prompt_with_context):
        await final_answer.stream_token(resp.content)
    await final_answer.send()
```

Deploy the UI with:

```sh
uv run chainlit run app.py
```

---

## Deploy with a nice web UI

You can add some question examples:

```python
@cl.set_starters
async def set_starters():
    return [
        cl.Starter(
            label="Rat orthologs",
            message="What are the rat orthologs of human TP53?",
        ),
    ]
```

[Customize the UI](https://docs.chainlit.io/customisation/overview):

- Change general settings in `.chainlit/config.toml`
- Add your logo in the `public` folder:
  - `logo_dark.png`
  - `logo_light.png`
  - `favicon`

---

## Creating more complex "agents"

e.g. reactive agent that can loop over themselves using [LangGraph](https://langchain-ai.github.io/langgraph/#):

- To validate a generated query
- To use tools

---

## Define the state and update the retrieve function

```python
from langgraph.graph.message import MessagesState

class AgentState(MessagesState):
    """State of the agent available inside each node."""
    relevant_docs: str
    
    
async def retrieve_docs(state: AgentState) -> dict[str, str]:
	question = state["messages"][-1].content
    # [...] 
    async with cl.Step(name=f"{len(retrieved_docs)} relevant documents 📚️") as step:
        step.output = relevant_docs
    # This will update relevant_docs in the state:
    return {"relevant_docs": relevant_docs}
```

---

## Define the node to call the LLM

```python
def call_model(state: AgentState):
    """Call the model with the retrieved documents as context."""
    prompt_with_context = prompt_template.invoke({
        "messages": state["messages"],
        "relevant_docs": state['relevant_docs'],
    })
    response = llm.invoke(prompt_with_context)
    return {"messages": [response]}
```

---

## Define the workflow

```python
from langgraph.graph import StateGraph

builder = StateGraph(AgentState)

builder.add_node(retrieve_docs)
builder.add_node(call_model)

builder.add_edge("__start__", "retrieve_docs")
builder.add_edge("retrieve_docs", "call_model")
builder.add_edge("call_model", "__end__")

graph = builder.compile()
```

---

## Update the UI

```python
@cl.on_message
async def on_message(msg: cl.Message):
    answer = cl.Message(content="")
    async for msg, metadata in graph.astream(
        {"messages": [("human", msg.content)]},
        stream_mode="messages",
    ):
        if not msg.response_metadata:
            await answer.stream_token(msg.content)
        else:
            await answer.send()
            answer = cl.Message(content="")
```

> Try again your agent now

---

## Add SPARQL query validation

Add fields to the state related to validation

```python
class AgentState(MessagesState):
    # [...]
    passed_validation: bool
    try_count: int
```

---

## Add SPARQL query validation

Initialize the prefixes map and VoID classes schema that will be used by validation

```python
import logging
from sparql_llm.utils import get_prefixes_and_schema_for_endpoints
from index import endpoints

logging.getLogger("httpx").setLevel(logging.WARNING)

prefixes_map, endpoints_void_dict = get_prefixes_and_schema_for_endpoints(endpoints)
```

---

## Add SPARQL query validation

Create the validation node

```python
from sparql_llm import validate_sparql_in_msg

async def validate_output(state: AgentState) -> dict[str, bool | list[tuple[str, str]] | int]:
    """Node to validate the output of a LLM call, e.g. SPARQL queries generated."""
    recall_messages = []
    validation_outputs = validate_sparql_in_msg(state["messages"][-1].content, prefixes_map, endpoints_void_dict)
    for validation_output in validation_outputs:
        # Handle when missing prefixes have been fixed
        if validation_output["fixed_query"]:
            async with cl.Step(name="missing prefixes correction ✅") as step:
                step.output = f"Missing prefixes added to the generated query:\n```sparql\n{validation_output['fixed_query']}\n```"
        # Add a new message to ask the model to fix the errors
        if validation_output["errors"]:
            recall_msg = f"""Fix the SPARQL query helping yourself with the error message and context from previous messages in a way that it is a fully valid query.\n
### Error messages:\n- {'\n- '.join(validation_output['errors'])}\n
### Erroneous SPARQL query\n```sparql\n{validation_output['original_query']}\n```"""
            async with cl.Step(name=f"SPARQL query validation, got {len(validation_output['errors'])} errors to fix 🐞") as step:
                step.output = recall_msg
            recall_messages.append(("human", recall_msg))
    return {
        "messages": recall_messages,
        "try_count": state.get("try_count", 0) + 1,
        "passed_validation": not recall_messages,
    }
```

---

## Add SPARQL query validation

Create a conditional edge to route the workflow based on validation results 

```python
max_try_fix_sparql = 3
def route_model_output(state: AgentState) -> Literal["__end__", "call_model"]:
    """Determine the next node based on the model's output."""
    if state["try_count"] > max_try_fix_sparql:
        return "__end__"
    if not state["passed_validation"]:
        return "call_model"
    return "__end__"
```

---

## Add SPARQL query validation

Add this new edge to the workflow graph

```python
builder.add_node(validate_output)

builder.add_edge("call_model", "validate_output")
builder.add_conditional_edges("validate_output", route_model_output)
```

