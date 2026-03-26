"""TEXT2SPARQL API"""

import json
import os
import time
from typing import Any

import fastapi
from fastembed import TextEmbedding
from langchain_core.messages import HumanMessage, SystemMessage
from qdrant_client import QdrantClient
from qdrant_client.models import FieldCondition, Filter, MatchValue

from sparql_llm.agent.utils import load_chat_model
from sparql_llm.config import Configuration, settings
from sparql_llm.utils import query_sparql
from sparql_llm.validate_sparql import extract_sparql_queries, validate_sparql

app = fastapi.FastAPI(title="SPARQL-LLM TEXT2SPARQL API")


def get_dataset_id_from_iri(dataset_iri: str) -> str:
    return dataset_iri.split("/")[-2]


# TODO: refactor to use different endbpoints instead of different graphs
DATASETS_ENDPOINTS = {
    "https://text2sparql.aksw.org/2025/dbpedia/": os.getenv("DBPEDIA_URL", "http://virtuoso-dbpedia:8890/sparql"),
    "https://text2sparql.aksw.org/2025/corporate/": os.getenv("CORPORATE_URL", "http://virtuoso-corporate:8890/sparql"),
}

MODEL = os.getenv("BENCH_MODEL", "openrouter/openai/gpt-oss-120b")

SCHEMAS = {}
for dataset_iri in DATASETS_ENDPOINTS.keys():
    try:
        with open(
            os.path.join("data", f"{get_dataset_id_from_iri(dataset_iri)}_schema.json"),
            encoding="utf-8",
        ) as f:
            print(f"Loading schema for dataset {dataset_iri} from {f}...")
            SCHEMAS[dataset_iri] = json.load(f)
    except FileNotFoundError:
        print(
            f"⚠️ Schema file for dataset {dataset_iri} not found. Please run the indexing script to generate the schema files."
        )
        SCHEMAS[dataset_iri] = {}

RAG_PROMPT = """

Here is a list of reference user questions and corresponding SPARQL query answers that will help you formulate the SPARQL query:

{relevant_queries}

If the information provided in the examples above is not sufficient to answer the question, you can advise the schema information below to help you formulate the SPARQL query.
Here is a list of relevant classes, the predicates of each class in descending order of frequency, and optionally their ranges (object classes or datatypes).
When there is no range information for a predicate, try to infer it based on the predicate name.

{relevant_classes}

"""

RESOLUTION_PROMPT = """
You are an assistant that helps users formulate SPARQL queries to be executed on a SPARQL endpoint.
Your role is to transform the user question into a SPARQL query based on the context provided in the prompt.

Your response must follow these rules:
    - Always output one SPARQL query.
    - Enclose the SPARQL query in a single markdown code block using the "sparql" language tag.
    - Use unicode characters in the SPARQL query if they are present in the question or the provided context.
    - Include a comment at the beginning of the query that specifies the target endpoint using the following format: "#+ endpoint: ".
    - Use full URIs for all entities in the SPARQL query.
    - Prefer a single endpoint; use a federated SPARQL query only if access across multiple endpoints is required.
    - Do not add more codeblocks than necessary.
"""

embedding_model = TextEmbedding(settings.embedding_model)
qdrant_client = QdrantClient(url=settings.vectordb_url, prefer_grpc=True)

# Statistics
question_num = 0
statistics: Any = {
    "DBpedia (EN)": {
        "llm_time": [],
        "input_tokens": [],
        "output_tokens": [],
    },
    "DBpedia (ES)": {
        "llm_time": [],
        "input_tokens": [],
        "output_tokens": [],
    },
    "Corporate": {
        "llm_time": [],
        "input_tokens": [],
        "output_tokens": [],
    },
}


@app.get("/")
async def get_answer(question: str, dataset: str):
    if dataset not in DATASETS_ENDPOINTS:
        raise fastapi.HTTPException(404, "Unknown dataset ...")
    endpoint_url = DATASETS_ENDPOINTS[dataset]
    # Retrieve relevant queries
    question_embeddings = next(iter(embedding_model.embed([question])))
    retrieved_queries = qdrant_client.query_points(
        collection_name=f"text2sparql-{get_dataset_id_from_iri(dataset)}",
        query=question_embeddings,
        limit=settings.default_number_of_retrieved_docs,
        query_filter=Filter(
            must=[
                FieldCondition(
                    key="doc_type",
                    match=MatchValue(value="SPARQL endpoints query examples"),
                )
            ]
        ),
    )

    # Retrieve relevant classes
    retrieved_classes = qdrant_client.query_points(
        collection_name=f"text2sparql-{get_dataset_id_from_iri(dataset)}",
        query=question_embeddings,
        limit=settings.default_number_of_retrieved_docs,
        query_filter=Filter(
            must=[
                FieldCondition(
                    key="doc_type",
                    match=MatchValue(value="classes"),
                )
            ]
        ),
    )

    # Initial interaction with the chat model
    relevant_queries = "\n\n".join(json.dumps(doc.payload, indent=2) for doc in retrieved_queries.points)
    relevant_classes = "\n\n".join(doc.payload["desc"] for doc in retrieved_classes.points)
    # print(f"📚️ Retrieved {len(retrieved_queries.points)} relevant queries and {len(retrieved_classes.points)} relevant classes")
    client = load_chat_model(Configuration(model=MODEL))
    messages = [
        SystemMessage(
            content=RESOLUTION_PROMPT
            + RAG_PROMPT.format(relevant_queries=relevant_queries, relevant_classes=relevant_classes)
        ),
        HumanMessage(content=question),
    ]

    client_time = time.perf_counter()
    response = client.invoke(messages)
    total_client_time = time.perf_counter() - client_time
    total_input_tokens = response.model_dump()["response_metadata"]["token_usage"]["prompt_tokens"]
    total_output_tokens = response.model_dump()["response_metadata"]["token_usage"]["completion_tokens"]

    # Validation and fixing of the generated SPARQL query
    num_of_tries = 0
    resp_msg = "\n\n# Make sure you will not repeat the mistakes below: \n"
    generated_sparql = ""
    while num_of_tries < settings.default_max_try_fix_sparql:
        generated_sparql = ""
        try:
            chat_resp_md = response.model_dump()["content"]
            generated_sparqls = extract_sparql_queries(chat_resp_md)
            generated_sparql = generated_sparqls[-1]["query"].strip()
            # print(f"Generated SPARQL query: {generated_sparql}")
            # print(f"Response message: {resp_msg}")
        except Exception:
            resp_msg += "## No SPARQL query could be extracted from the model response. Please provide a valid SPARQL query based on the provided information and try again.\n"
        if generated_sparql != "":
            try:
                res = query_sparql(generated_sparql, endpoint_url)
                if res.get("results", {}).get("bindings"):
                    # Successfully generated a query with results
                    if num_of_tries > 0:
                        print("✅ Fixed SPARQL query. Conversation:\n")
                        for msg in messages:
                            print(f"{msg.type}: {msg.content}\n")
                    break
                else:
                    raise Exception("No results")

            except Exception as e:
                validation_output = validate_sparql(
                    query=generated_sparql, endpoint_url=endpoint_url, endpoints_void_dict=SCHEMAS.get(dataset, {})
                )
                if validation_output["errors"]:
                    error_str = "- " + "\n- ".join(validation_output["errors"])
                    resp_msg += f"## SPARQL query not valid. Please fix the query based on the provided information and try again.\n### Erroneous SPARQL query\n```sparql\n{validation_output['original_query']}\n```\n### Validation Errors:\n{error_str}\n"
                else:
                    resp_msg += f"## SPARQL query returned error: {e}. Please provide an alternative query based on the provided information and try again.\n### Erroneous SPARQL query\n```sparql\n{generated_sparql}\n```\n"

        num_of_tries += 1
        if num_of_tries == settings.default_max_try_fix_sparql:
            print(f"❌ Could not fix generate SPARQL query for question: {question} \n")

        # If no valid SPARQL query was generated, ask the model to fix it
        messages = [HumanMessage(content=question + resp_msg)]

        client_time = time.perf_counter()
        response = client.invoke(messages)
        total_client_time += time.perf_counter() - client_time
        total_input_tokens = response.model_dump()["response_metadata"]["token_usage"]["prompt_tokens"]
        total_output_tokens = response.model_dump()["response_metadata"]["token_usage"]["completion_tokens"]

    # Statistics
    global question_num
    if dataset == "https://text2sparql.aksw.org/2025/dbpedia/" and question_num % 2 == 0:
        statistics["DBpedia (EN)"]["llm_time"].append(total_client_time)
        statistics["DBpedia (EN)"]["input_tokens"].append(total_input_tokens)
        statistics["DBpedia (EN)"]["output_tokens"].append(total_output_tokens)
    elif dataset == "https://text2sparql.aksw.org/2025/dbpedia/" and question_num % 2 == 1:
        statistics["DBpedia (ES)"]["llm_time"].append(total_client_time)
        statistics["DBpedia (ES)"]["input_tokens"].append(total_input_tokens)
        statistics["DBpedia (ES)"]["output_tokens"].append(total_output_tokens)
    elif dataset == "https://text2sparql.aksw.org/2025/corporate/":
        statistics["Corporate"]["llm_time"].append(total_client_time)
        statistics["Corporate"]["input_tokens"].append(total_input_tokens)
        statistics["Corporate"]["output_tokens"].append(total_output_tokens)
    question_num += 1

    return {"dataset": dataset, "question": question, "query": generated_sparql}


@app.get("/stats")
async def get_stats():
    return statistics
