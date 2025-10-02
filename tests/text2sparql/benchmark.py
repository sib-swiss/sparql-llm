import json
import logging
import os
import sys
import time
from collections import defaultdict

import httpx
import pandas as pd
from fastembed import TextEmbedding
from langchain_core.messages import HumanMessage, SystemMessage
from qdrant_client import QdrantClient
from qdrant_client.models import FieldCondition, Filter, MatchValue

from sparql_llm.agent.config import Configuration, settings
from sparql_llm.agent.prompts import RESOLUTION_PROMPT
from sparql_llm.agent.utils import load_chat_model
from sparql_llm.utils import query_sparql
from sparql_llm.validate_sparql import extract_sparql_queries

file_time_prefix = time.strftime("%Y%m%d_%H%M")
bench_folder = os.path.join("data", "benchmarks")
os.makedirs(bench_folder, exist_ok=True)

# Setup logging to both console and file
logger = logging.getLogger("benchmark")
# Disable the default console handler
logger.propagate = False
logger.setLevel(logging.INFO)

file_handler = logging.FileHandler(os.path.join(bench_folder, f"{file_time_prefix}_tests_output.md"), mode="w")
file_handler.setFormatter(logging.Formatter("%(message)s"))
logger.addHandler(file_handler)
console_handler = logging.StreamHandler(sys.stdout)
console_handler.setFormatter(logging.Formatter("%(message)s"))
logger.addHandler(console_handler)

# Suppress overly verbose logs from httpx
# logging.getLogger("httpx").setLevel(logging.WARNING)
RAG_PROMPT = (
    """

Here is a list of reference user questions and corresponding SPARQL query answers that will help you answer accurately:

{relevant_queries}


Here is a list of reference classes URIs accompanied by 1) the 20 most frequent predicates URIs, and 2) the data type or the classes of their predicates' objects, that will help you answer accurately:

{relevant_classes}

"""
    # """
    # Here is a list of documents (reference questions and query answers, classes schema or general endpoints information) relevant to the user question that will help you answer the user question accurately:
    # {relevant_docs}
    # """
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
    # """You are an assistant that helps users to formulate a query to run on a SPARQL endpoint.
    # Always derive your answer from the context provided in the prompt, do not use information that is not in the context.
    # Put the SPARQL query inside a markdown codeblock with the "sparql" language tag, and always add the URL of the endpoint on which the query should be executed in a comment at the start of the query inside the codeblocks starting with "#+ endpoint: " (always only 1 endpoint).
    # Try to always answer with one query, if the answer lies in different endpoints, provide a federated query. Do not add more codeblocks than necessary.
    # """
)

QUERIES_FILE = os.path.join(os.path.abspath(os.path.dirname(__file__)), "queries.csv")
ENDPOINT_URL = "http://localhost:8890/sparql/"
VECTORDB_URL = "http://localhost:6334"
VECTORDB_COLLECTION_NAME = "text2sparql-dbpedia"

embedding_model = TextEmbedding(settings.embedding_model)
vectordb = QdrantClient(url=VECTORDB_URL, prefer_grpc=True)

example_queries = pd.read_csv(QUERIES_FILE)
example_queries = (
    example_queries[(example_queries["dataset"] == "Text2SPARQL-db")].reset_index(drop=True).to_dict(orient="records")
)


def result_sets_are_same(gen_set, ref_set) -> bool:
    """Check if all items from ref_set have equivalent items in gen_set, ignoring variable names"""
    # return all(ref_item in list(gen_set) for ref_item in list(ref_set))
    if not ref_set or not gen_set:
        # If either set is empty, they're the same only if both are empty
        return len(ref_set) == len(gen_set) == 0
    # Extract just the values from each binding, ignoring the variable names
    ref_values_set = []
    for ref_binding in ref_set:
        # Create a sorted tuple of values from each binding
        binding_values = tuple(sorted([v["value"] for v in ref_binding.values()]))
        ref_values_set.append(binding_values)
    gen_values_set = []
    for gen_binding in gen_set:
        binding_values = tuple(sorted([v["value"] for v in gen_binding.values()]))
        gen_values_set.append(binding_values)
    # Check if all reference values are present in generated values
    return all(ref_values in gen_values_set for ref_values in ref_values_set)

    # print(gen_set, ref_set)
    # for ref_item in ref_set:
    #     if ref_item not in gen_set:
    #         # logger.info(f"> Missing from generated: {ref_item}")
    #         return False
    # return True

    # gen_set, ref_set = list(gen_set), list(ref_set)
    # for item in gen_set:
    #     if item not in ref_set:
    #         # logger.info(f"> Missing from reference: {item}")
    #         return False
    # return all(item in gen_set for item in ref_set)


# QLEVER_UNIPROT = "https://qlever.cs.uni-freiburg.de/api/uniprot"

# Price per million tokens, open source models based on fireworks.io pricing
# https://openai.com/api/pricing/
# https://fireworks.ai/pricing
models = {
    # "Llama3.1 8B": {
    #     "id": "hf:meta-llama/Meta-Llama-3.1-8B-Instruct",
    #     "price_input": 0.2,
    #     "price_output": 0.2,
    # },
    # "Mixtral 8x22B": {
    #     "id": "hf:mistralai/Mixtral-8x22B-Instruct-v0.1",
    #     "price_input": 1.20,
    #     "price_output": 1.20,
    # },
    # "o3-mini": {
    #     "id": "openai/o3-mini",
    #     "price_input": 1.1,
    #     "price_output": 4.4,
    # },
    # Before adding extraction step: 🎯 RAG with validation - Success: 27, Different results: 9, No results: 4, Error: 2
    # After adding extraction
    # 🎯 RAG without validation - Success: 27, Different results: 11, No results: 2, Error: 8
    # 🎯 RAG with validation - Success: 31, Different results: 10, No results: 4, Error: 3
    # Price before fixing the token_usage gathering: 0.01421
    # "gpt-4o": {
    #     "id": "openai/gpt-4o",
    #     "price_input": 5,
    #     "price_output": 15,
    # },
    # # 🎯 RAG with validation - Success: 32, Different results: 7, No results: 3, Error: 0
    "gpt-4o-mini": {
        "id": "openai/gpt-4o-mini",
        "price_input": 0.15,
        "price_output": 0.6,
    },
}


def answer_no_rag(question: str, model: str):
    client = load_chat_model(Configuration(model=model))
    response = client.invoke(
        [
            SystemMessage(content=RESOLUTION_PROMPT),
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
    return response


def answer_rag_without_validation(question: str, model: str):
    question_embeddings = next(iter(embedding_model.embed([question])))
    retrieved_queries = vectordb.query_points(
        collection_name=VECTORDB_COLLECTION_NAME,
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
        collection_name=VECTORDB_COLLECTION_NAME,
        query=question_embeddings,
        limit=50,
        query_filter=Filter(
            must=[
                FieldCondition(
                    key="metadata.doc_type",
                    match=MatchValue(value="predicates"),
                )
            ]
        ),
    )

    relevant_queries = "\n".join(json.dumps(doc.payload["metadata"], indent=2) for doc in retrieved_queries.points)
    relevant_classes = "\n".join(json.dumps(doc.payload["metadata"], indent=2) for doc in retrieved_classes.points)
    # logger.info(f"📚️ Retrieved {len(retrieved_docs.points)} documents")
    client = load_chat_model(Configuration(model=model))
    response = client.invoke(
        [
            SystemMessage(
                content=RESOLUTION_PROMPT
                + RAG_PROMPT.format(relevant_queries=relevant_queries, relevant_classes=relevant_classes)
            ),
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
    return response


def answer_rag_with_validation(question: str, model: str):
    response = httpx.post(
        "http://localhost:8000/chat",
        headers={"Authorization": f"Bearer {settings.chat_api_key}"},
        json={
            "model": model,
            "messages": [{"role": "user", "content": question}],
            "stream": False,
            "validate_output": True,
        },
        timeout=120,
        follow_redirects=True,
    )
    return response.json()


list_of_approaches = {
    # "No RAG": answer_no_rag,
    "RAG without validation": answer_rag_without_validation,
    # "RAG with validation": answer_rag_with_validation,
}

results_data = {
    "Model": [],
    "RAG Approach": [],
    "Success": [],
    "Different Results": [],
    "No Results": [],
    "Errors": [],
    "Price": [],
    # 'Precision': [],
    # "Recall": [],
    "F1": [],
}

number_of_tries = 3
start_time = time.time()

logger.info(
    f"🧪 Testing {len(example_queries)} queries using {settings.default_number_of_retrieved_docs} retrieved docs\n"
)
logger.info("## Executing references queries\n")

# Get results for the reference queries first
ref_results = []
for i, test_query in enumerate(example_queries):
    res_ref_finally_pass = False
    while not res_ref_finally_pass:
        try:
            query_start_time = time.time()
            res_from_ref = query_sparql(test_query["query"], test_query["endpoint"], timeout=300)["results"]["bindings"]
            logger.info(
                f"- [x] Reference query {i} '{test_query['question']}' took {time.time() - query_start_time:.2f} seconds"
            )
            ref_results.append(res_from_ref)
            res_ref_finally_pass = True
        except Exception as e:
            logger.info(f"- [ ] Timeout for reference query {i}: {e}, Trying again because we know it should work.")
            res_ref_finally_pass = False
    # res_from_ref = query_sparql(test_query["query"], QLEVER_UNIPROT)["results"]["bindings"]


for model_label, model in models.items():
    logger.info(f"\n## 🧠 Testing model {model_label}\n")
    res = defaultdict(dict)
    # e.g. res["No RAG"]["success"] += 1
    for approach in list_of_approaches:
        res[approach] = defaultdict(int)

    for query_num, test_query in enumerate(example_queries):
        for key in ["success", "different_results", "no_results", "fail"]:
            example_queries[query_num][key] = 0
        for approach, approach_func in list_of_approaches.items():
            # logger.info(f"Approach {approach}")
            for t in range(number_of_tries):
                response = approach_func(test_query["question"], model["id"])
                # logger.info(response)
                chat_resp_md = response["messages"][-1]["content"]
                # chat_resp_md = response["choices"][0]["message"]["content"]
                # TODO: loop over all messages to get the total token usage in case of multiple messages (fix by calling LLM)
                for msg in response["messages"]:
                    # Retrieve token usage for all messages in the response
                    if "response_metadata" in msg and "token_usage" in msg["response_metadata"]:
                        res[approach]["input_tokens"] += msg["response_metadata"]["token_usage"]["prompt_tokens"]
                        res[approach]["output_tokens"] += msg["response_metadata"]["token_usage"]["completion_tokens"]
                        # res[approach]["input_tokens"] += response["messages"][-1]["response_metadata"]["token_usage"]["  prompt_tokens"]
                        # res[approach]["output_tokens"] += response["messages"][-1]["response_metadata"]["token_usage"]["completion_tokens"]
                        # print(chat_resp_md)
                try:
                    generated_sparqls = extract_sparql_queries(chat_resp_md)
                    if len(generated_sparqls) == 0:
                        raise Exception(f"No SPARQL query could be extracted from {chat_resp_md}")
                    generated_sparql = generated_sparqls[-1]
                    example_queries[query_num]["generated_sparql_" + str(t)] = generated_sparql["query"].strip()
                    if generated_sparql["query"].strip() == test_query["query"].strip():
                        logger.info(f"✅ {t + 1}/{number_of_tries} {test_query['question']}. EXACT MATCH\n")
                        res[approach]["success"] += 1
                        example_queries[query_num]["success"] += 1
                        continue

                    # Execute the generated query
                    res_from_generated = query_sparql(
                        generated_sparql["query"],
                        ENDPOINT_URL,
                        timeout=300,
                    )["results"]["bindings"]
                    # res_from_generated = query_sparql(generated_sparql["query"], QLEVER_UNIPROT)["results"]["bindings"]

                    if not result_sets_are_same(res_from_generated, ref_results[query_num]):
                        if len(res_from_generated) == 0:
                            res[approach]["no_results"] += 1
                            example_queries[query_num]["no_results"] += 1
                        else:
                            res[approach]["different_results"] += 1
                            example_queries[query_num]["different_results"] += 1
                        raise Exception(
                            f"\nResults mismatch. Ref: {len(ref_results[query_num])} != gen: {len(res_from_generated)}\n"
                        )
                    else:
                        logger.info(
                            f"✅ {t + 1}/{number_of_tries} {test_query['question']} = {len(res_from_generated)}\n"
                        )
                        res[approach]["success"] += 1
                        example_queries[query_num]["success"] += 1

                except Exception as e:
                    res[approach]["fail"] += 1
                    example_queries[query_num]["fail"] += 1
                    if approach == "RAG with validation":
                        logger.info(f"❌ {t + 1}/{number_of_tries} {test_query['question']}\n{e}\n")
                        logger.info(f"```sparql\n{generated_sparql['query']}\n```\n")
                        logger.info("Correct query:\n")
                        logger.info(f"```sparql\n{test_query['query']}\n```\n")

        for approach in list_of_approaches:
            logger.info(
                f"🎯 {approach} - Success: {res[approach]['success']}, Different results: {res[approach]['different_results']}, No results: {res[approach]['no_results']}, Error: {res[approach]['fail'] - res[approach]['no_results'] - res[approach]['different_results']}\n"
            )

    for approach, result_row in res.items():
        mean_price = (
            (result_row["input_tokens"] * model["price_input"] / 1000000)
            + (result_row["output_tokens"] * model["price_output"] / 1000000)
        ) / (len(example_queries) * number_of_tries)
        precision = result_row["success"] / (result_row["success"] + result_row["fail"])
        recall = result_row["success"] / (result_row["success"] + result_row["fail"] - result_row["different_results"])
        results_data["Model"].append(model_label)
        results_data["RAG Approach"].append(approach)
        results_data["Success"].append(result_row["success"])
        results_data["Different Results"].append(result_row["different_results"])
        results_data["No Results"].append(result_row["no_results"])
        results_data["Errors"].append(result_row["fail"] - result_row["no_results"] - result_row["different_results"])
        results_data["Price"].append(round(mean_price, 5))
        # results_data['Precision'].append(precision)
        # results_data['Recall'].append(recall)
        if precision + recall == 0:
            results_data["F1"].append(0)
        else:
            results_data["F1"].append(round(2 * (precision * recall) / (precision + recall), 2))

logger.info("## Results\n")

df = pd.DataFrame(results_data)
logger.info(df)
logger.info("\n\n")
logger.info(df.to_csv(os.path.join(bench_folder, f"{file_time_prefix}_tests_results.csv"), index=False))

# Error analysis
logger.info("## Error Analysis\n")
error_analysis_df = pd.DataFrame.from_records(example_queries)
logger.info(
    f"Correlation between 'fails' and 'triple patterns': {error_analysis_df['fail'].corr(error_analysis_df['triple patterns'])}"
)
logger.info(
    f"Correlation between 'fails' and 'result length': {error_analysis_df['fail'].corr(error_analysis_df['result length'])}"
)
error_analysis_df.to_csv(os.path.join(bench_folder, f"{file_time_prefix}_Text2SPARQL_Error_Analysis.csv"), index=False)

# Output Latex table
# latex_str = ""
# prev_model = next(iter(models.keys()))
# for _index, row in df.iterrows():
#     row_str = " & ".join(
#         [str(item) for item in row]
#     )  # Join all values in the row with " & "
#     row_str += " \\\\"
#     if row["Model"] != prev_model:
#         latex_str += "\\midrule\n"
#         prev_model = row["Model"]
#     latex_str += row_str + "\n"
# with open(
#     os.path.join(bench_folder, f"{file_time_prefix}_tests_results_latex.txt"), "w"
# ) as f:
#     f.write(latex_str)


logger.info(f"⏱️ Total runtime: {(time.time() - start_time) / 60:.2f} minutes")
