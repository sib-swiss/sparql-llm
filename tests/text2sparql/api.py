"""TEXT2SPARQL API"""

import json
import os
import time
from typing import Any

import fastapi
from lancedb.pydantic import LanceModel
from langchain_core.messages import HumanMessage, SystemMessage

from sparql_llm.agent.utils import load_chat_model
from sparql_llm.config import Configuration, settings
from sparql_llm.utils import query_sparql
from sparql_llm.validate_sparql import extract_sparql_queries, validate_sparql
from sparql_llm.vectordb import db, embedder

app = fastapi.FastAPI(title="SPARQL-LLM TEXT2SPARQL API")


def get_dataset_id_from_iri(dataset_iri: str) -> str:
    return dataset_iri.split("/")[-2]


# Query examples and classes of a dataset, in its own LanceDB table
class Text2SparqlDoc(LanceModel):
    doc_type: str
    # Embedded: question of a query example, or name of a class
    text: str = embedder.SourceField()
    # Metadata of the document given to the model, as JSON
    payload: str
    vector: list[float] = embedder.VectorField()


def table_name(dataset_iri: str) -> str:
    return f"text2sparql-{get_dataset_id_from_iri(dataset_iri)}"


def search(dataset_iri: str, question: str, doc_type: str) -> list[dict[str, Any]]:
    """Vector search of the documents of a type in the table of a dataset, returns their metadata"""
    hits = (
        db()
        .open_table(table_name(dataset_iri))
        .search(question)
        .where(f"doc_type = '{doc_type}'", prefilter=True)
        .limit(settings.default_number_of_retrieved_docs)
        .to_list()
    )
    return [json.loads(hit["payload"]) for hit in hits]


# TODO: refactor to use different endbpoints instead of different graphs
DATASETS_ENDPOINTS = {
    "https://text2sparql.aksw.org/2026/dbpedia/": os.getenv("DBPEDIA_URL", "http://virtuoso-dbpedia:8890/sparql"),
    "https://text2sparql.aksw.org/2026/corporate/": os.getenv("CORPORATE_URL", "http://virtuoso-corporate:8890/sparql"),
}

MODEL = os.getenv("BENCH_MODEL", "openrouter/openai/gpt-oss-120b")

SCHEMAS = {}
for dataset_iri in DATASETS_ENDPOINTS.keys():
    try:
        with open(
            os.path.join("data", f"{get_dataset_id_from_iri(dataset_iri)}_schema.json"),
            encoding="utf-8",
        ) as f:
            print(f"Loading schema for dataset {dataset_iri} from {os.path.abspath(f.name)}...")
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
    - Unless explictly asked use one variable for the answer, if not explicitly specified it is most probably the URI that is expected.
    - Use only the endpoint provided in the context to execute the query. Do not use any other endpoints.
"""

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
    # Retrieve relevant queries and classes
    retrieved_queries = search(dataset, question, "SPARQL endpoints query examples")
    retrieved_classes = search(dataset, question, "classes")
    relevant_queries = "\n\n".join(json.dumps(doc, indent=2) for doc in retrieved_queries)
    relevant_classes = "\n\n".join(doc["desc"] for doc in retrieved_classes)
    # print(f"📚️ Retrieved {len(retrieved_queries)} relevant queries and {len(retrieved_classes)} relevant classes")
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
    messages.append(response)
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
            generated_sparql = generated_sparqls[-1].get("query", "").strip()  # type: ignore
            # print(f"Generated SPARQL query: {generated_sparql}")
            # print(f"Response message: {resp_msg}")
        except Exception:
            resp_msg += "## No SPARQL query could be extracted from the model response. Please provide a valid SPARQL query based on the provided information and try again.\n"
        if generated_sparql != "":
            print(f"[Try {num_of_tries}] Generated SPARQL:\n{generated_sparql}\n")
            try:
                res = query_sparql(generated_sparql, endpoint_url)
                bindings = res.get("results", {}).get("bindings", [])
                print(f"[Try {num_of_tries}] Query returned {len(bindings)} result(s)")
                if bindings:
                    break
                    # # Ask the LLM if the results actually answer the original question
                    # results_preview = str(res)
                    # with contextlib.suppress(Exception):
                    #     results_preview = json.dumps(res["results"]["bindings"][:10], indent=2)

                    # satisfaction_response = client.invoke(
                    #     [
                    #         HumanMessage(
                    #             content=(
                    #                 f'The following SPARQL query was executed to answer this question: "{question}"\n\n'
                    #                 f"```sparql\n{generated_sparql}\n```\n\n"
                    #                 f"It returned these results:\n```json\n{results_preview}\n```\n\n"
                    #                 "Do these results satisfactorily answer the original question?\n"
                    #                 'Reply with only "YES" or "NO" on the first line, optionally followed by a brief explanation of what is wrong.'
                    #             )
                    #         )
                    #     ]
                    # )
                    # satisfaction_content = satisfaction_response.model_dump()["content"].strip()
                    # total_input_tokens += satisfaction_response.model_dump()["response_metadata"]["token_usage"][
                    #     "prompt_tokens"
                    # ]
                    # total_output_tokens += satisfaction_response.model_dump()["response_metadata"]["token_usage"][
                    #     "completion_tokens"
                    # ]
                    # print(f"[Try {num_of_tries}] Satisfaction check: {satisfaction_content[:300]}")

                    # if satisfaction_content.upper().startswith("YES"):
                    #     # Successfully generated a query with satisfactory results
                    #     break
                    # else:
                    #     resp_msg += (
                    #         f"## The query returned results but they do not satisfactorily answer the original question.\n"
                    #         f"### Generated query\n```sparql\n{generated_sparql}\n```\n"
                    #         f"### Results obtained\n```json\n{results_preview}\n```\n"
                    #         f"### Why the results are unsatisfactory\n{satisfaction_content}\n"
                    #     )
                else:
                    raise Exception("No results")

            except Exception as e:
                print(f"[Try {num_of_tries}] Query failed: {e}")
                validation_output = validate_sparql(
                    query=generated_sparql, endpoint_url=endpoint_url, endpoints_void_dict=SCHEMAS.get(dataset, {})
                )
                if validation_output["errors"]:
                    error_str = "- " + "\n- ".join(validation_output["errors"])
                    print(f"[Try {num_of_tries}] Validation errors: {error_str[:300]}")
                    resp_msg += f"## SPARQL query not valid. Please fix the query based on the provided information and try again.\n### Erroneous SPARQL query\n```sparql\n{validation_output['original_query']}\n```\n### Validation Errors:\n{error_str}\n"
                else:
                    resp_msg += f"## SPARQL query returned error: {e}. Please provide an alternative query based on the provided information and try again.\n### Erroneous SPARQL query\n```sparql\n{generated_sparql}\n```\n"

        num_of_tries += 1
        if num_of_tries == settings.default_max_try_fix_sparql:
            print(f"❌ Could not fix generate SPARQL query for question: {question} \n")
            break

        # If no valid SPARQL query was generated, ask the model to fix it
        messages.append(HumanMessage(content=question + resp_msg))

        client_time = time.perf_counter()
        response = client.invoke(messages)
        total_client_time += time.perf_counter() - client_time
        total_input_tokens = response.model_dump()["response_metadata"]["token_usage"]["prompt_tokens"]
        total_output_tokens = response.model_dump()["response_metadata"]["token_usage"]["completion_tokens"]

    # Statistics
    global question_num
    if dataset == "https://text2sparql.aksw.org/2026/dbpedia/" and question_num % 2 == 0:
        statistics["DBpedia (EN)"]["llm_time"].append(total_client_time)
        statistics["DBpedia (EN)"]["input_tokens"].append(total_input_tokens)
        statistics["DBpedia (EN)"]["output_tokens"].append(total_output_tokens)
    elif dataset == "https://text2sparql.aksw.org/2026/dbpedia/" and question_num % 2 == 1:
        statistics["DBpedia (ES)"]["llm_time"].append(total_client_time)
        statistics["DBpedia (ES)"]["input_tokens"].append(total_input_tokens)
        statistics["DBpedia (ES)"]["output_tokens"].append(total_output_tokens)
    elif dataset == "https://text2sparql.aksw.org/2026/corporate/":
        statistics["Corporate"]["llm_time"].append(total_client_time)
        statistics["Corporate"]["input_tokens"].append(total_input_tokens)
        statistics["Corporate"]["output_tokens"].append(total_output_tokens)
    question_num += 1

    return {"dataset": dataset, "question": question, "query": generated_sparql}


@app.get("/stats")
async def get_stats():
    return statistics
