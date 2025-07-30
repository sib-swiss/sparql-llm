"""TEXT2SPARQL API"""

import json
import fastapi
from fastembed import TextEmbedding
from qdrant_client import QdrantClient
from qdrant_client.models import FieldCondition, Filter, MatchValue
from langchain_core.messages import HumanMessage, SystemMessage
from sparql_llm.validate_sparql import extract_sparql_queries
from expasy_agent.config import Configuration, settings
from expasy_agent.utils import load_chat_model

app = fastapi.FastAPI(title="TEXT2SPARQL API")

KNOWN_DATASETS = [
    "https://text2sparql.aksw.org/2025/dbpedia/",
    "https://text2sparql.aksw.org/2025/corporate/"
]

MODEL = 'openai/gpt-4o-mini'

RAG_PROMPT = (
"""

Here is a list of reference user questions and corresponding SPARQL query answers that will help you answer accurately:

{relevant_queries}

Here is schema information about related classes, their most frequent predicates, and their most frequent predicate ranges (datatypes or other classes) that will help you answer accurately:

{relevant_classes}

"""
)

RESOLUTION_PROMPT = (
"""
You are an assistant that helps users formulate SPARQL queries to be executed on a SPARQL endpoint.
Your role is to transform the user question into a SPARQL query based on the context provided in the prompt.

Your response must follow these rules:
    - Always output one SPARQL query.
    - Enclose the SPARQL query in a single markdown code block using the "sparql" language tag.
    - Include a comment at the beginning of the query that specifies the target endpoint using the following format: "#+ endpoint: ".
    - Prefer a single endpoint; use a federated SPARQL query only if access across multiple endpoints is required.
    - Do not add more codeblocks than necessary.
"""
)

embedding_model = TextEmbedding(settings.embedding_model)
vectordb = QdrantClient(url=settings.vectordb_url, prefer_grpc=True)

@app.get("/")
async def get_answer(question: str, dataset: str):
    if dataset not in KNOWN_DATASETS:
        raise fastapi.HTTPException(404, "Unknown dataset ...")
    
    question_embeddings = next(iter(embedding_model.embed([question])))
    retrieved_queries = vectordb.query_points(
        collection_name=f"text2sparql-{dataset.split('/')[-2]}",
        query=question_embeddings,
        limit=settings.default_number_of_retrieved_docs,
        query_filter=Filter(
            must=[
                FieldCondition(
                    key="metadata.doc_type",
                    match=MatchValue(value="SPARQL endpoints query examples"),
                )
            ]
        ),
    )

    retrieved_classes = vectordb.query_points(
        collection_name=f"text2sparql-{dataset.split('/')[-2]}",
        query=question_embeddings,
        limit=settings.default_number_of_retrieved_docs,
        query_filter=Filter(
            must=[
                FieldCondition(
                    key="metadata.doc_type",
                    match=MatchValue(value="classes"),
                )
            ]
        ),
    )

    relevant_queries = '\n'.join(json.dumps(doc.payload['metadata'], indent=2) for doc in retrieved_queries.points)
    relevant_classes = '\n'.join(f"Class: {json.dumps(doc.payload['metadata']['Class'], indent=2)} \nPredicates: {json.dumps(doc.payload['metadata']['Predicates'], indent=2)}" for doc in retrieved_classes.points)
    # logger.info(f"📚️ Retrieved {len(retrieved_docs.points)} documents")
    client = load_chat_model(Configuration(model=MODEL))
    response = client.invoke(
        [
            SystemMessage(content=RESOLUTION_PROMPT + RAG_PROMPT.format(relevant_queries=relevant_queries, relevant_classes=relevant_classes)),
            HumanMessage(content=question),
        ]
    )
    response = response.model_dump()
    response["messages"] = [
        {
            "content": response["content"],
            "response_metadata": response["response_metadata"],
        }
    ]
    chat_resp_md = response["messages"][-1]["content"]

    generated_sparqls = extract_sparql_queries(chat_resp_md)
    if len(generated_sparqls) == 0:
        raise Exception(
            f"No SPARQL query could be extracted from {chat_resp_md}"
        )
    generated_sparql = generated_sparqls[-1]['query'].strip()

    return {
        "dataset": dataset,
        "question": question,
        "query": generated_sparql
    }