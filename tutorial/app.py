import logging

from langchain_core.language_models import BaseChatModel
from qdrant_client.models import FieldCondition, Filter, MatchValue, ScoredPoint

logging.getLogger("httpx").setLevel(logging.WARNING)
logging.info("Initializing endpoints metadata...")

## 1. Set up LLM provider


def load_chat_model(model: str) -> BaseChatModel:
    """Load a chat model based on the provider and model name."""
    provider, model_name = model.split("/", maxsplit=1)
    if provider == "google":
        # https://python.langchain.com/docs/integrations/chat/google_generative_ai/
        # https://docs.langchain.com/oss/python/integrations/providers/google
        # https://ai.google.dev/gemini-api/docs/models
        from langchain_google_genai import ChatGoogleGenerativeAI

        return ChatGoogleGenerativeAI(
            model=model_name,
            temperature=0,
        )
    if provider == "mistralai":
        # https://python.langchain.com/docs/integrations/chat/mistralai/
        # https://docs.langchain.com/oss/python/integrations/providers/mistralai
        from langchain_mistralai import ChatMistralAI

        return ChatMistralAI(
            model=model_name,
            temperature=0,
        )
    if provider == "openai":
        # https://python.langchain.com/docs/integrations/chat/openai/
        from langchain_openai import ChatOpenAI

        return ChatOpenAI(
            model_name=model_name,
            temperature=0,
        )
    if provider == "groq":
        # https://python.langchain.com/docs/integrations/chat/groq/
        from langchain_groq import ChatGroq

        return ChatGroq(
            model=model_name,
            temperature=0,
        )
    if provider == "ollama":
        # https://python.langchain.com/docs/integrations/chat/ollama/
        from langchain_ollama import ChatOllama

        return ChatOllama(model=model_name, temperature=0)
    raise ValueError(f"Unknown provider: {provider}")


# Change the model and provider used for the chat here
llm = load_chat_model("mistralai/mistral-small-latest")
# llm = load_chat_model("google/gemini-2.5-flash")
# llm = load_chat_model("openai/gpt-5-mini")
# llm = load_chat_model("groq/meta-llama/llama-4-scout-17b-16e-instruct")
# llm = load_chat_model("groq/moonshotai/kimi-k2-instruct")
# llm = load_chat_model("ollama/mistral")


## 2. Set up vector database for document retrieval

from fastembed import TextEmbedding
from langchain_core.documents import Document
from qdrant_client import QdrantClient
from qdrant_client.http.models import Distance, VectorParams
from sparql_llm import SparqlExamplesLoader, SparqlInfoLoader, SparqlVoidShapesLoader

# List of endpoints that will be used
# endpoints: list[SparqlEndpointLinks] = [
endpoints: list[dict[str, str]] = [
    {
        # The URL of the SPARQL endpoint from which most informations will be extracted
        "endpoint_url": "https://sparql.uniprot.org/sparql/",
        # If VoID description or SPARQL query examples are not available in the endpoint, you can provide a VoID file (local or remote URL)
        # "void_file": "../src/sparql-llm/tests/void_uniprot.ttl",
        # "void_file": "data/uniprot_void.ttl",
        # "examples_file": "data/uniprot_examples.ttl",
    },
    {
        "endpoint_url": "https://www.bgee.org/sparql/",
    },
    {
        "endpoint_url": "https://sparql.omabrowser.org/sparql/",
    },
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
    docs += SparqlInfoLoader(endpoints, source_iri="https://www.expasy.org/").load()

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
    relevant_docs = "\n".join(_format_doc(doc) for doc in retrieved_docs)
    async with cl.Step(name=f"{len(retrieved_docs)} relevant documents 📚️") as step:
        step.output = relevant_docs
    return relevant_docs


def _format_doc(doc: ScoredPoint) -> str:
    """Format a question/answer document to be provided as context to the model."""
    doc_lang = (
        "sparql"
        if "query" in doc.payload.get("doc_type", "")
        else "shex"
        if "schema" in doc.payload.get("doc_type", "")
        else ""
    )
    return f"\n{doc.payload['question']} ({doc.payload.get('endpoint_url', '')}):\n\n```{doc_lang}\n{doc.payload.get('answer')}\n```\n\n"


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


## 4. Set up SPARQL query validation (post-processing of LLM output)

from sparql_llm import validate_sparql_in_msg
from sparql_llm.utils import get_prefixes_and_schema_for_endpoints

# Retrieve the prefixes map and initialize VoID schema dictionary from the indexed endpoints
# Used for SPARQL query validation
prefixes_map, endpoints_void_dict = get_prefixes_and_schema_for_endpoints(endpoints)


async def validate_output(last_msg: str) -> str | None:
    """Validate the output of a LLM call, i.e. SPARQL queries generated."""
    validation_outputs = validate_sparql_in_msg(last_msg, prefixes_map, endpoints_void_dict)
    for validation_output in validation_outputs:
        if validation_output["fixed_query"]:
            async with cl.Step(name="missing prefixes correction ✅") as step:
                step.output = f"Missing prefixes added to the generated query:\n```sparql\n{validation_output['fixed_query']}\n```"
        if validation_output["errors"]:
            recall_msg = f"""Fix the SPARQL query helping yourself with the error message and context from previous messages in a way that it is a fully valid query.\n
### Error messages:\n- {"\n- ".join(validation_output["errors"])}\n
### Erroneous SPARQL query\n```sparql\n{validation_output.get("fixed_query", validation_output["original_query"])}\n```"""
            async with cl.Step(
                name=f"SPARQL query validation, got {len(validation_output['errors'])} errors to fix 🐞"
            ) as step:
                step.output = recall_msg
            return recall_msg


## 5. Setup chat web UI with Chainlit

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
    for _i in range(max_try_count):
        answer = cl.Message(content="")
        for resp in llm.stream(messages):
            await answer.stream_token(resp.content)
            if resp.usage_metadata:
                logging.info(resp.usage_metadata)
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
