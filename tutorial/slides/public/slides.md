## Introduction

In this tutorial, you'll learn how to build an LLM-powered app that assists in writing SPARQL queries to access biodata resources, step by step.

As we progress, you'll be provided with code snippets to gradually construct the system. Note that some earlier code may need to be modified or removed to prevent redundancy, ensuring a clean and efficient implementation.

---

## Outline

1. Programmatically query LLMs
2. Index documents
3. Use indexed documents as context
4. Execute generated query
5. Add a chat web UI

---

## Setup

[Install `uv`](https://docs.astral.sh/uv/getting-started/installation/) to easily handle dependencies and run scripts.

If you use VSCode we recommend to have the [`Python` extension](https://marketplace.visualstudio.com/items?itemName=ms-python.python) installed.

Create a new folder, you will be using this same folder along the tutorial.

Create a `.env` file with the API key for the LLM provider you will use:

```sh
MISTRAL_API_KEY=YYY
GROQ_API_KEY=YYY
```

> Many providers offers a relatively generous **free tier** that you can use for developments
>
> - [MistralAI](https://console.mistral.ai/api-keys) (requires your phone number) 🇪🇺
> - [Groq](https://console.groq.com/keys) (login with GitHub or Google), gives access to [various open-source models](https://groq.com/pricing/) with a limit of 6k tokens/min.

---

## Setup dependencies

Create a `pyproject.toml` file with this content:

```toml
[project]
name = "tutorial-biodata-agent"
version = "0.0.1"
requires-python = "==3.12.*"
dependencies = [
    "sparql-llm >=0.0.8",
    "langchain >=0.3.27",
    "langchain-mistralai >=0.2.12",
    "langchain-groq >=0.3.8",
    "langchain-ollama >=0.3.8",
    "qdrant-client >=1.15.1",
    "fastembed >=0.7.3",
    "chainlit >=2.8.1",
]
```

---

## Workflow skeleton

Create a `app.py` file in the same folder, alongside the `pyproject.toml`, it will be used to build your workflow.

The numbered comments are placeholders for the different parts of your workflow.

```python
import asyncio
import logging

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
logging.getLogger("httpx").setLevel(logging.WARNING)

## 1. Set up LLM provider

## 2. Initialize vector database for similarity search, and index relevant documents

## 3. Set up document retrieval, and pass relevant context to the system prompt

## 4. Automatically execute generated query and interpret results

## 5. Setup chat web UI (with Chainlit)

async def main() -> None:
    question = "What are the rat orthologs of human TP53?"
    logging.info("Hello world")
    # 🔨 Call the different steps of the pipeline here

if __name__ == "__main__":
    asyncio.run(main())
```

Run it with:

```sh
uv run --env-file .env app.py
```

---

## Programmatically query a LLM

Setup the LLM provider, and update the `main` function to call it

```python
from langchain_mistralai import ChatMistralAI

## 1. Set up LLM provider
llm = ChatMistralAI(
    model_name="mistral-small-latest",
    temperature=0,
    max_tokens=1024,
)

async def main():
    question = "What are the rat orthologs of human TP53?"
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
async def main():
    question = "What are the rat orthologs of human TP53?"
    for msg in llm.stream(question):
        print(msg.content, end="", flush=True)
```

---

## Easily switch the model used

```python
from langchain_core.language_models import BaseChatModel

## 1. Set up LLM provider
def load_chat_model(model: str) -> BaseChatModel:
    provider, model_name = model.split("/", maxsplit=1)
    if provider == "mistralai":
        # https://python.langchain.com/docs/integrations/chat/mistralai/
        from langchain_mistralai import ChatMistralAI

        return ChatMistralAI(
            model=model_name,
            temperature=0,
            max_tokens=1024,
        )
    if provider == "groq":
        # https://python.langchain.com/docs/integrations/chat/groq/
        from langchain_groq import ChatGroq

        return ChatGroq(
            model=model_name,
            temperature=0,
            max_tokens=1024,
        )
    raise ValueError(f"Unknown provider: {provider}")

llm = load_chat_model("mistralai/mistral-small-latest")
# llm = load_chat_model("google/gemini-2.5-flash")
```

> Alternatively you could replace LangChain by [LiteLLM](https://docs.litellm.ai/docs/) here

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

> Ollama is mainly a wrapper around [llama.cpp](https://python.langchain.com/docs/integrations/chat/llamacpp/), you can also [download `.gguf` files](https://huggingface.co/lmstudio-community/Mistral-7B-Instruct-v0.3-GGUF) and use them directly.

> [vLLM](https://github.com/vllm-project/vllm) and [llamafile](https://github.com/Mozilla-Ocho/llamafile) are other solutions to serve LLMs locally.

---

## Add context from a CSV file

We will use [this CSV file](https://github.com/sib-swiss/sparql-llm/blob/main/src/expasy-agent/expasy_resources_metadata.csv) containing informations about SIB resources.

```python
import httpx

SYSTEM_PROMPT = """You are an assistant that helps users to navigate the resources and databases from the SIB Swiss Institute of Bioinformatics.
Here is the description of resources available at the SIB:
{context}
Use it to answer the question"""

async def main() -> None:
  	question = "..."
    response = httpx.get("https://github.com/sib-swiss/sparql-llm/raw/refs/heads/main/src/expasy-agent/expasy_resources_metadata.csv", follow_redirects=True)
    messages = [
        ("system", SYSTEM_PROMPT.format(context=response.text)),
        ("human", question),
    ]
    for resp in llm.stream(messages):
        print(resp.content, end="", flush=True)
        if resp.usage_metadata:
            print(f"\n\n{resp.usage_metadata}")
```

> ⚠️ Checkout the amount of used tokens: this approach uses a lot of them! Splitting the file in smaller indexable pieces could help

> 💡 You can do this directly through most LLM provider web UI: upload a file and ask a question!

---

## Index context

A solution to handle large context is to build a **semantic search index**, and only retrieve the documents or part of documents that are relevant to the question.

It also brings explainability of how the response was generated, reducing the black box effect.

When preparing data for semantic search, focus on two essential components:

- **Semantic label**: a short, human-readable title or description that guides the search engine in matching questions effectively.
- **Detailed information**: the set of metadata or full  content of the data element, which will be passed to the LLM and used to generate informed responses.

> 💡 While you can use the same text for both parts, complex data often benefits from a clear, concise semantic label(s) paired with a richer, detailed description for the LLM.

---

## Index context

Setup the [Qdrant vector database](https://qdrant.tech/documentation/) and embedding model using fastembed, see [supported models](https://qdrant.github.io/fastembed/examples/Supported_Models/#supported-text-embedding-models).

```python
from fastembed import TextEmbedding
from qdrant_client import QdrantClient

## 2. Set up vector database for document retrieval
embedding_model = TextEmbedding("BAAI/bge-small-en-v1.5")
embedding_dimensions = 384
collection_name = "sparql-docs"
vectordb = QdrantClient(path="data/vectordb")
```

---

## Index context

1. Use the loaders from the **[sparql-llm](https://pypi.org/project/sparql-llm/)** library to fetch documents from SPARQL endpoints (queries examples and classes schemas),
2. Generate embeddings for the documents descriptions locally using **[FastEmbed](https://qdrant.github.io/fastembed/)**,
3. Index these documents embeddings in the **[Qdrant](https://qdrant.tech/documentation/)** vector store.

```python
from langchain_core.documents import Document
from qdrant_client.http.models import Distance, VectorParams
from sparql_llm import SparqlExamplesLoader, SparqlVoidShapesLoader, SparqlInfoLoader

## 2. Set up vector database for document retrieval
endpoints: list[dict[str, str]] = [
    { "endpoint_url": "https://sparql.uniprot.org/sparql/" },
    { "endpoint_url": "https://www.bgee.org/sparql/" },
    { "endpoint_url": "https://sparql.omabrowser.org/sparql/" },
]

def index_endpoints():
    """Index SPARQL endpoints metadata in the vector database."""
    docs: list[Document] = []
    # Fetch documents from endpoints
    for endpoint in endpoints:
        logging.info(f"🔎 Retrieving metadata for {endpoint['endpoint_url']}")
        docs += SparqlExamplesLoader(
            endpoint["endpoint_url"],
            examples_file=endpoint.get("examples_file"),
        ).load()
        docs += SparqlVoidShapesLoader(
            endpoint["endpoint_url"],
            void_file=endpoint.get("void_file"),
            examples_file=endpoint.get("examples_file"),
        ).load()
    docs += SparqlInfoLoader(endpoints, source_iri="https://www.expasy.org/").load()

    # Load documents in vectordb
    if vectordb.collection_exists(collection_name):
        vectordb.delete_collection(collection_name)
    vectordb.create_collection(
        collection_name=collection_name,
        vectors_config=VectorParams(size=embedding_dimensions, distance=Distance.COSINE),
    )
    embeddings = embedding_model.embed([q.page_content for q in docs])
    vectordb.upload_collection(
        collection_name=collection_name,
        vectors=[embed.tolist() for embed in embeddings],
        payload=[doc.metadata for doc in docs],
    )
    logging.info(f"✅ Indexed {len(docs)} documents in collection {collection_name}")
```

----

You could also provide the list of Document directly from your script

```python
ex_question = "How to retrieve proteins?"
docs.append(Document(
    page_content=ex_question,
    metadata={
        "question": ex_question,
        "answer": """SELECT ?protein WHERE {
	?protein a up:Protein .
}""",
        "endpoint_url": "https://sparql.uniprot.org/",
        "query_type": "SelectQuery",
        "doc_type": "SPARQL endpoints query examples",
    },
))
```

---

## Index context

Run initialization function, that will only run if the vector database has no entries

```python
## 2. Set up vector database for document retrieval
if not vectordb.collection_exists(collection_name) or vectordb.get_collection(collection_name).points_count == 0:
    index_endpoints()
else:
    logging.info(
        f"ℹ️  Using existing collection '{collection_name}' with {vectordb.get_collection(collection_name).points_count} vectors"
    )
```

---

## Provide context to the LLM

Retrieve documents related to the user question using the vector store

```python
from qdrant_client.models import ScoredPoint

## 3. Set up document retrieval and system prompt
retrieved_docs_count = 3
def retrieve_docs(question: str) -> list[ScoredPoint]:
    """Retrieve documents relevant to the user's question."""
    question_embeddings = next(iter(embedding_model.embed([question])))
    retrieved_docs = vectordb.query_points(
        collection_name=collection_name,
        query=question_embeddings,
        limit=retrieved_docs_count,
        query_filter=Filter(
            must=[
                FieldCondition(
                    key="doc_type",
                    match=MatchValue(value="SPARQL endpoints query examples"),
                )
            ]
        ),
    ).points
    retrieved_docs += vectordb.query_points(
        collection_name=collection_name,
        query=question_embeddings,
        limit=retrieved_docs_count,
        query_filter=Filter(
            must=[
                FieldCondition(
                    key="doc_type",
                    match=MatchValue(value="SPARQL endpoints classes schema"),
                )
            ]
        ),
    ).points
    return retrieved_docs
```

---

## Provide context to the LLM

Format the retrieved documents in order to pass them to the LLM

```python
## 3. Set up document retrieval and system prompt
def format_doc(doc: ScoredPoint) -> str:
    """Format a question/answer document to be provided as context to the model."""
    doc_lang = (
        f"sparql\n#+ endpoint: {doc.payload.get('endpoint_url', 'not provided')}"
        if "query" in doc.payload.get("doc_type", "")
        else ""
    )
    return f"\n{doc.payload['question']} ({doc.payload.get('endpoint_url', '')}):\n\n```{doc_lang}\n{doc.payload.get('answer')}\n```\n\n"
```

---

## Provide context to the LLM

Provide the system prompt that is the instructions the LLM will follow in priority

```python
SYSTEM_PROMPT = """You are an assistant that helps users to write SPARQL queries.
Put the SPARQL query inside a markdown codeblock with the "sparql" language tag, and always add the URL of the endpoint on which the query should be executed in a comment at the start of the query inside the codeblocks starting with "#+ endpoint: " (always only 1 endpoint).
Use the queries examples and classes shapes provided in the prompt to derive your answer, don't try to create a query from nothing and do not provide a generic query.
Try to always answer with one query, if the answer lies in different endpoints, provide a federated query.
And briefly explain the query.
Here is a list of documents (reference questions and query answers, classes schema) relevant to the user question that will help you answer the user question accurately:
{relevant_docs}
"""
```

---

## Complete workflow

Put the workflow together in the `main` function

```python
async def main():
    question = "What are the rat orthologs of human TP53?"
    retrieved_docs = retrieve_docs(question)
    formatted_docs = "\n".join(format_doc(doc) for doc in retrieved_docs)
    messages = [
        ("system", SYSTEM_PROMPT.format(relevant_docs=formatted_docs)),
        ("user", question),
    ]
    for resp in llm.stream(messages):
        print(resp.content, end="", flush=True)
        if resp.usage_metadata:
            print("\n")
            logging.info(f"🎰 {resp.usage_metadata}")
```

---

## Add query execution step

Use helper function from the `sparql-llm` package

```python
from sparql_llm.validate_sparql import extract_sparql_queries
from sparql_llm.utils import query_sparql

## 4. Execute generated SPARQL query
def execute_query(last_msg: str) -> list[dict[str, str]]:
    """Extract SPARQL query from markdown and execute it."""
    for extracted_query in extract_sparql_queries(last_msg):
        if extracted_query.get("query") and extracted_query.get("endpoint_url"):
            res = query_sparql(extracted_query.get("query"), extracted_query.get("endpoint_url"))
            return res.get("results", {}).get("bindings", [])
```

---

## Add query execution step

Change the `main` function to execute the query, and loop on the LLM if no results

```python
max_try_count = 3

async def main():
    question = "What are the rat orthologs of human TP53?"
    # Retrieve relevant documents and add them to conversation
    retrieved_docs = retrieve_docs(question)
    formatted_docs = "\n".join(format_doc(doc) for doc in retrieved_docs)
    messages = [
        ("system", SYSTEM_PROMPT.format(relevant_docs=formatted_docs)),
        ("user", question),
    ]
    # Loop until query execution is successful or max tries reached
    query_success = False
    for _i in range(max_try_count):
        complete_answer = ""
        for resp in llm.stream(messages):
            print(resp.content, end="", flush=True)
            complete_answer += resp.content
            if resp.usage_metadata:
                print("\n")
                logging.info(f"🎰 {resp.usage_metadata}")

        messages.append(("assistant", complete_answer))
        if query_success:
            break

        # Run execution on the final answer
        query_res = execute_query(complete_answer)
        if len(query_res) < 1:
            logging.warning("⚠️ No results, trying to fix")
            messages.append(("user", f"""The query you provided returned no results, please fix the query:\n\n{complete_answer}"""))
        else:
            logging.info(f"✅ Got {len(query_res)} results, summarizing them")
            messages.append(("user", f"""The query you provided returned these results, summarize them:\n\n{json.dumps(query_res, indent=2)}"""))
            query_success = True
```

---

## Deploy with a nice web UI

For this we will move the workflow code to a custom chainlit `@cl.on_message` function instead of the `main` function, and start the app with the [`chainlit`](https://github.com/Chainlit/chainlit) command line tool

```python
import chainlit as cl

@cl.on_message
async def on_message(msg: cl.Message):
    """Main function to handle when user send a message to the assistant."""
    retrieved_docs = retrieve_docs(msg.content)
    formatted_docs = "\n".join(format_doc(doc) for doc in retrieved_docs)
    async with cl.Step(name=f"{len(retrieved_docs)} relevant documents 📚️") as step:
        step.output = formatted_docs
    messages = [
        ("system", SYSTEM_PROMPT.format(relevant_docs=formatted_docs)),
        *cl.chat_context.to_openai(),
    ]

    query_success = False
    for _i in range(max_try_count):
        answer = cl.Message(content="")
        for resp in llm.stream(messages):
            await answer.stream_token(resp.content)
            if resp.usage_metadata:
                logging.info(f"🎰 {resp.usage_metadata}")
        await answer.send()

        if query_success:
            break

        query_res = execute_query(answer.content)
        if len(query_res) < 1:
            logging.warning("⚠️ No results, trying to fix")
            messages.append(("user", f"""The query you provided returned no results, please fix the query:\n\n{answer.content}"""))
        else:
            logging.info(f"✅ Got {len(query_res)} results! Summarizing them, then stopping the chat")
            async with cl.Step(name=f"{len(query_res)} query results ✨") as step:
                step.output = f"```json\n{json.dumps(query_res, indent=2)}\n```"
            messages.append(("user", f"""The query you provided returned these results, summarize them:\n\n{json.dumps(query_res, indent=2)}"""))
            query_success = True
```

Deploy the UI on http://localhost:8000 with:

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

And [customize the UI](https://docs.chainlit.io/customisation/overview) in `.chainlit/config.toml`

- set `custom_css= "/public/style.css"` containing: `div.watermark { display: none !important; }`
- set `logo_file_url`

---

## Use an agent framework

Optionally you can move to fully use an "agent framework" like [LangGraph](https://langchain-ai.github.io/langgraph/#):

✅ Give access to some nice features

- switch between streaming and complete response
- parallel execution of nodes
- generate a visual diagram for your workflow

✅ Provide structure to build your workflow

⚠️ Can be slower at runtime than doing things yourself

⚠️ Relies on more dependencies increasing the overall complexity of the system, some people might find it more confusing than just using good old loops

---

## Use an agent framework

Add the `langgraph` dependency to your `pyproject.toml`

Define the state and update the retrieve function

```python
from langgraph.graph.message import MessagesState

class AgentState(MessagesState):
    """State of the agent available inside each node."""
    relevant_docs: str
    execution_success: bool
    try_count: int


async def retrieve_docs(state: AgentState) -> dict[str, str]:
	question = state["messages"][-1].content
    # [...]
    # This will update relevant_docs in the state:
    return {"relevant_docs": relevant_docs}
```

---

## Use an agent framework

Define the node to call the LLM

```python
def call_model(state: AgentState):
    """Call the model with the retrieved documents as context."""
    response = llm.invoke([
        ("system", SYSTEM_PROMPT.format(relevant_docs=state["relevant_docs"])),
        *state["messages"],
    ])
    return {"messages": [response]}
```

---

## Use an agent framework

Update the function that does validation

```python
async def execute_query(state) -> dict[str, bool | list[tuple[str, str]] | int]:
    last_msg = next(msg.content for msg in reversed(state["messages"]) if msg.content)
    # [...]
    return {
        "messages": messages,
        "try_count": state.get("try_count", 0) + 1,
        "execution_success": len(res) > 0,
    }
```



---

## Use an agent framework

Create a conditional edge to route the workflow based on validation results

```python
from typing import Literal

max_try_count = 3
def route_model_output(state: AgentState) -> Literal["call_model", "__end__"]:
    """Determine the next node based on the model's output."""
    if state["try_count"] > max_try_count:
        return "__end__"
    if not state["execution_success"]:
        return "call_model"
    return "__end__"
```

---

## Use an agent framework

Define the workflow "graph"

```python
from langgraph.graph import StateGraph

builder = StateGraph(AgentState)

builder.add_node(retrieve_docs)
builder.add_node(call_model)
builder.add_node(execute_query)

builder.add_edge("__start__", "retrieve_docs")
builder.add_edge("retrieve_docs", "call_model")
builder.add_edge("call_model", "execute_query")
builder.add_conditional_edges("execute_query", route_model_output)

graph = builder.compile()
```

---

## Use an agent framework

Update the UI

```python
@cl.on_message
async def on_message(msg: cl.Message):
    answer = cl.Message(content="")
    async for msg, metadata in graph.astream(
        {"messages": cl.chat_context.to_openai()},
        stream_mode="messages",
    ):
        if not msg.response_metadata:
            await answer.stream_token(msg.content)
        else:
            print(msg.usage_metadata)
            await answer.send()
            answer = cl.Message(content="")
```

> Try running your agent again now

---

## Thank you

[Complete script on GitHub](https://github.com/sib-swiss/sparql-llm/blob/main/tutorial/app.py)

&nbsp;

Live deployment for SIB endpoints (UniProt, Bgee, OMA, Rhea…)

[**chat.expasy.org**](https://chat.expasy.org)

&nbsp;

Code: [**github.com/sib-swiss/sparql-llm**](https://github.com/sib-swiss/sparql-llm)

Short paper: [arxiv.org/abs/2410.06062](https://arxiv.org/abs/2410.06062)

Standalone components available as a pip package: [pypi.org/project/sparql-llm](https://pypi.org/project/sparql-llm)
