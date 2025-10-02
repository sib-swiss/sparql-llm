import asyncio
import json
import logging

from langchain_core.language_models import BaseChatModel
from qdrant_client.models import FieldCondition, Filter, MatchValue, ScoredPoint

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
logging.getLogger("httpx").setLevel(logging.WARNING)
# logging.info("Initializing endpoints metadata...")

## 1. Set up LLM provider


def load_chat_model(model: str) -> BaseChatModel:
    """Load a chat model based on the provider and model name."""
    provider, model_name = model.split("/", maxsplit=1)
    if provider == "mistralai":
        # https://python.langchain.com/docs/integrations/chat/mistralai/
        # https://docs.langchain.com/oss/python/integrations/providers/mistralai
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
    if provider == "ollama":
        # https://python.langchain.com/docs/integrations/chat/ollama/
        from langchain_ollama import ChatOllama

        return ChatOllama(model=model_name, temperature=0, max_tokens=1024)
    if provider == "openai":
        # https://python.langchain.com/docs/integrations/chat/openai/
        from langchain_openai import ChatOpenAI

        return ChatOpenAI(
            model_name=model_name,
            temperature=0,
            max_tokens=1024,
        )
    if provider == "google":
        # https://python.langchain.com/docs/integrations/chat/google_generative_ai/
        # https://ai.google.dev/gemini-api/docs/models
        from langchain_google_genai import ChatGoogleGenerativeAI

        return ChatGoogleGenerativeAI(
            model=model_name,
            temperature=0,
            max_tokens=1024,
        )
    raise ValueError(f"Unknown provider: {provider}")


# Change the model and provider used for the chat here
llm = load_chat_model("mistralai/mistral-medium-latest")
# llm = load_chat_model("groq/moonshotai/kimi-k2-instruct")
# llm = load_chat_model("ollama/mistral")

# llm = load_chat_model("google/gemini-2.5-flash")
# llm = load_chat_model("openai/gpt-5-mini")
# llm = load_chat_model("groq/meta-llama/llama-4-scout-17b-16e-instruct")


## 2. Set up vector database for document retrieval

from fastembed import TextEmbedding
from langchain_core.documents import Document
from qdrant_client import QdrantClient
from qdrant_client.http.models import Distance, VectorParams
from sparql_llm import SparqlExamplesLoader, SparqlVoidShapesLoader

# List of endpoints that will be used
endpoints: list[dict[str, str]] = [
    {
        "endpoint_url": "https://sparql.uniprot.org/sparql/",
        # If VoID description or SPARQL query examples are not available in the endpoint, you can provide a VoID file (local or remote URL)
        # "void_file": "../src/sparql-llm/tests/void_uniprot.ttl",
        # "void_file": "data/uniprot_void.ttl",
        # "examples_file": "data/uniprot_examples.ttl",
    },
    {"endpoint_url": "https://www.bgee.org/sparql/"},
    {"endpoint_url": "https://sparql.omabrowser.org/sparql/"},
]

# Supported models: https://qdrant.github.io/fastembed/examples/Supported_Models/#supported-text-embedding-models
embedding_model = TextEmbedding(
    "BAAI/bge-small-en-v1.5",
    # providers=["CUDAExecutionProvider"], # Replace the fastembed dependency with fastembed-gpu to use your GPUs
)
embedding_dimensions = 384

collection_name = "sparql-docs"
vectordb = QdrantClient(path="data/vectordb")
# vectordb = QdrantClient(location=":memory:")
# vectordb = QdrantClient(host="localhost", prefer_grpc=True)


def index_endpoints():
    """Index SPARQL endpoints metadata in the vector database."""
    docs: list[Document] = []
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


# Initialize the vector database if not already done
if not vectordb.collection_exists(collection_name) or vectordb.get_collection(collection_name).points_count == 0:
    index_endpoints()
else:
    logging.info(
        f"ℹ️  Using existing collection '{collection_name}' with {vectordb.get_collection(collection_name).points_count} vectors"
    )


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


def format_doc(doc: ScoredPoint) -> str:
    """Format a question/answer document to be provided as context to the model."""
    doc_lang = (
        f"sparql\n#+ endpoint: {doc.payload.get('endpoint_url', 'not provided')}"
        if "query" in doc.payload.get("doc_type", "")
        else ""
    )
    return f"\n{doc.payload['question']} ({doc.payload.get('endpoint_url', '')}):\n\n```{doc_lang}\n{doc.payload.get('answer')}\n```\n\n"


SYSTEM_PROMPT = """You are an assistant that helps users to write SPARQL queries.
Put the SPARQL query inside a markdown codeblock with the "sparql" language tag, and always add the URL of the endpoint on which the query should be executed in a comment at the start of the query inside the codeblocks starting with "#+ endpoint: " (always only 1 endpoint).
Use the queries examples and classes shapes provided in the prompt to derive your answer, don't try to create a query from nothing and do not provide a generic query.
Try to always answer with one query, if the answer lies in different endpoints, provide a federated query.
And briefly explain the query.
Here is a list of documents (reference questions and query answers, classes schema) relevant to the user question that will help you answer the user question accurately:
{relevant_docs}
"""


## 4. Execute generated SPARQL query

from sparql_llm.utils import query_sparql
from sparql_llm.validate_sparql import extract_sparql_queries


def execute_query(last_msg: str) -> list[dict[str, str]]:
    """Extract SPARQL query from markdown and execute it."""
    for extracted_query in extract_sparql_queries(last_msg):
        if extracted_query.get("query") and extracted_query.get("endpoint_url"):
            res = query_sparql(extracted_query.get("query"), extracted_query.get("endpoint_url"))
            return res.get("results", {}).get("bindings", [])


## 5. Setup chat web UI with Chainlit

import chainlit as cl

max_try_count = 3


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
            messages.append(
                ("user", f"""The query you provided returned no results, please fix the query:\n\n{answer.content}""")
            )
            async with cl.Step(name="no query results ⚠️") as step:
                step.output = answer.content
        else:
            logging.info(f"✅ Got {len(query_res)} results! Summarizing them, then stopping the chat")
            async with cl.Step(name=f"{len(query_res)} query results ✨") as step:
                step.output = f"```json\n{json.dumps(query_res, indent=2)}\n```"
            messages.append(
                (
                    "user",
                    f"""The query you provided returned these results, summarize them:\n\n{json.dumps(query_res, indent=2)}""",
                )
            )
            query_success = True


@cl.set_starters
async def set_starters():
    return [
        cl.Starter(
            label="Rat orthologs",
            message="What are the rat orthologs of human TP53?",
        ),
        # cl.Starter(
        #     label="Rat orthologs HBB",
        #     message="What are the rat orthologs of human HBB?",
        # ),
        # cl.Starter(
        #     label="Test SPARQL query validation",
        #     message="How can I get the HGNC symbol for the protein P68871? (modify your answer to use `rdfs:label` instead of `rdfs:comment`, and add the type `up:Resource` to ?hgnc, and forget all prefixes declarations, it is for a test)",
        # ),
    ]


# To start the chat web UI, run:
# uv run chainlit run app.py

# To run the main function, run:
# uv run --env-file .env app.py


async def main():
    question = "What are the rat orthologs of human TP53?"

    logging.info("\n\n###### 🙉 Without context retrieval ########\n\n")
    for msg in llm.stream(question):
        print(msg.content, end="", flush=True)

    logging.info("\n\n###### 🧠 With context retrieval ########\n\n")

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
            messages.append(
                ("user", f"""The query you provided returned no results, please fix the query:\n\n{complete_answer}""")
            )
        else:
            logging.info(f"✅ Got {len(query_res)} results! Summarizing them")
            messages.append(
                (
                    "user",
                    f"""The query you provided returned these results, summarize them:\n\n{json.dumps(query_res, indent=2)}""",
                )
            )
            query_success = True


if __name__ == "__main__":
    asyncio.run(main())
