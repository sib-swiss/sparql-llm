import os

# Set environment variables before importing other modules to avoid resource leaks
os.environ["LOKY_MAX_CPU_COUNT"] = "1"
os.environ["TOKENIZERS_PARALLELISM"] = "false"

import gc
import json
import logging
import re
import statistics
import sys
import time
from typing import Any

import httpx
import pytrec_eval
from langchain_core.documents import Document
from qdrant_client import models as qdrant_models
from qdrant_client.http.models import Distance, VectorParams
from sklearn.model_selection import KFold

# from sklearn.model_selection import KFold
from sparql_llm import SparqlExamplesLoader, SparqlVoidShapesLoader
from sparql_llm.config import embedding_model, qdrant_client, settings
from sparql_llm.utils import get_prefixes_and_schema_for_endpoints, query_sparql
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

# TODO: make sure only 1 endpoint indexed at the time, run clean up + reindex before each test

# text2sparql TREC eval: https://github.com/AKSW/text2sparql-client/blob/main/text2sparql_client/utils/evaluation_metrics.py

endpoints = [
    "https://sparql.uniprot.org/sparql",
    "https://www.bgee.org/sparql/",
    "https://sparql.cellosaurus.org/sparql",
    # "https://sparql.rhea-db.org/sparql/",
]


files = [
    "uniprot",
    "bgee",
    "cellosaurus",
    # "rhea",
]


# NOTE: for dev reduce the size of test examples
# LIMIT_FOR_DEV = 4
LIMIT_FOR_DEV = None

# DOCS_COLLECTION_NAME=biodata_benchmark
vector_collection = "expasy"

models = [
    # "openrouter/openai/gpt-4o",
    # "openrouter/google/gemini-pro-1.5",
    # "openrouter/mistralai/mistral-large-2411",
    # "openrouter/anthropic/claude-3.5-sonnet",
    # "openrouter/openai/gpt-4.1",
    # TODO:
    "openrouter/openai/gpt-4o-mini",
    "openrouter/openai/gpt-oss-120b",
    "openrouter/openai/gpt-5",  # ?
]

# We need to compile examples from Git repo because the one stored in SPARQL endpoints are way behind in version, e.g.
# java -jar sparql-examples-utils.jar convert -i examples/ -p Cellosaurus -f ttl > data/examples_cellosaurus.ttl
# Put them in tests/data/examples_{files[i]}.ttl


def sparql_results_to_trec(question: str, sparql_dict: dict[str, Any]) -> dict[str, Any]:
    """Transform a SPARQL results dict into a dict to be evaluated through the pyTREC library.

    Args:
        sparql_dict (dict): Dictionary of the URIs, returned by the end-point

    Returns:
        dict: Dictionary of the predicted lists in which all items have the same weight
    """
    d: dict[str, Any] = {}
    d[question] = {}
    try:
        if "boolean" in sparql_dict:
            bool_result = sparql_dict["boolean"]
            d[question]["true"] = 1 if bool_result else 0
        else:
            # print(sparql_dict)
            list_results = sparql_dict["results"]["bindings"]
            list_vars = sparql_dict["head"]["vars"]
            # We add all vars found flattened and compare this
            for var in list_vars:
                for value in list_results:
                    if var in value:
                        d[question][value[var]["value"]] = 1
    except Exception as e:
        print(f"⚠️ Could not transform SPARQL results to TREC format: {e}")
    return d


def ensure_limit(query: str, limit: int = 50) -> str:
    """Ensure the given SPARQL query ends with a trailing LIMIT.

    Args:
        query: the SPARQL query string
        limit: the numeric limit to apply (default 50)

    Returns:
        The modified SPARQL query with a trailing LIMIT <limit>.
    """
    if query is None:
        return query
    # Normalize trailing whitespace and optional trailing semicolon
    q = query.rstrip()
    has_semicolon = q.endswith(";")
    if has_semicolon:
        q = q[:-1].rstrip()
    # Regex: match a trailing LIMIT <number> at end of string (case-insensitive)
    # Only matches when LIMIT is the last clause in the query. We don't try to parse SPARQL fully here.
    trailing_limit_re = re.compile(r"LIMIT\s+\d+\s*$", re.IGNORECASE)
    q = trailing_limit_re.sub(f"LIMIT {limit}", q) if trailing_limit_re.search(q) else q + f" LIMIT {limit}"
    # Restore semicolon if present originally
    if has_semicolon:
        q = q + ";"
    return q


# TODO: This one should return a list of reference SPARQL queries used for testing
def get_folds(docs_list: list[Document]) -> list[tuple[list[Document], list[Document]]]:
    """Return 3-fold train/test splits as a list of tuples (train_docs, test_docs).

    Each tuple contains two lists of Documents: index 0 -> train, index 1 -> test.
    The function uses KFold(n_splits=3, shuffle=True, random_state=42) to produce
    deterministic shuffled splits.
    """
    if not isinstance(docs_list, list):
        raise TypeError("docs_list must be a list of Document objects")
    if len(docs_list) <= 3:
        raise ValueError(f"Not enough examples: {len(docs_list)}")

    kf = KFold(n_splits=3, shuffle=True, random_state=42)
    # KFold.split expects an array-like; pass the docs_list directly and ignore type-checker here
    splits = list(kf.split(docs_list))  # type: ignore
    folds: list[tuple[list[Document], list[Document]]] = []
    for train_idx, test_idx in splits:
        train_docs = [docs_list[i] for i in train_idx]
        test_docs = [docs_list[i] for i in test_idx]
        folds.append((train_docs, test_docs))
    gc.collect()
    return folds


BOLD = "\033[1m"
BLUE = "\033[34m"
RESET = "\033[0m"


def query_chat(question: str, model: str, client: httpx.Client) -> dict[str, Any]:
    """Query the chat API with validation enabled."""
    response = client.post(
        "http://localhost:8000/chat",
        headers={"Authorization": f"Bearer {settings.chat_api_key}"},
        json={
            "model": model,
            "messages": [{"role": "user", "content": question}],
            "stream": False,
            "validate_output": True,
            "enable_sparql_execution": False,
        },
        timeout=120,
    )
    # logger.info(response.status_code)
    response.raise_for_status()
    return response.json()


httpx_client = httpx.Client(follow_redirects=True, timeout=180)
avg_results: dict[str, Any] = {}

ref_res_cache_path = "data/biodata_ref_results_cache.json"


def log_query_to_jsonl(
    filepath: str,
    query_num: int,
    question: str,
    expected_query: str,
    generated_query: str | None,
    reference_results: dict[str, Any],
    generated_results: dict[str, Any],
    trec_scores: dict[str, float] | None,
    runtime: float,
    token_usage: dict[str, int] | None,
    messages: list[dict[str, str]] | None,
    error: str | None = None,
) -> None:
    """Log a single query execution to a JSONL file.

    Args:
        filepath: Path to the JSONL file
        query_num: Query number/index
        question: The natural language question
        expected_query: The expected/reference SPARQL query
        generated_query: The generated SPARQL query
        reference_results: Results from reference query execution
        generated_results: Results from generated query execution
        trec_scores: TREC evaluation scores (set_P, set_recall, set_F)
        runtime: Query execution runtime in seconds
        token_usage: Token usage data (prompt, completion, total)
        messages: Conversation messages from the chat API
        error: Error message if query failed
    """
    record = {
        "runtime_seconds": runtime,
        "query_num": query_num,
        "question": question,
        "expected_query": expected_query,
        "generated_query": generated_query,
        "reference_results": reference_results,
        "generated_results": generated_results,
        "trec_scores": trec_scores,
        "token_usage": token_usage,
        "messages": messages,
        "error": error,
    }
    try:
        os.makedirs(os.path.dirname(filepath) or ".", exist_ok=True)
        with open(filepath, "a") as f:
            f.write(json.dumps(record) + "\n")
    except Exception as e:
        logger.warning(f"⚠️ Failed to write to {filepath}: {e}")


# Try to load a persistent cache of reference query results so we don't re-run
# long-running reference queries across separate runs of the benchmark script.
ref_results_cache: dict[str, dict[str, Any] | None] = {}


def persist_ref_results_cache(cache: dict[str, Any] | None) -> None:
    logger.info(f"Persisting reference results cache to {ref_res_cache_path}")
    try:
        with open(ref_res_cache_path, "w") as fh:
            json.dump(cache or {}, fh, indent=2)
    except Exception as e:
        logger.warning(f"⚠️ Failed to write reference results cache to {ref_res_cache_path}: {e}")


def main() -> None:
    try:
        if os.path.exists(ref_res_cache_path):
            with open(ref_res_cache_path) as fh:
                ref_results = json.load(fh) or {}
            logger.info(f"Loaded {len(ref_results)} cached reference results from {ref_res_cache_path}")
        else:
            os.makedirs(os.path.dirname(ref_res_cache_path), exist_ok=True)
            ref_results = {}
    except Exception as e:
        logger.info(f"⚠️ Could not load reference results cache from {ref_res_cache_path}: {e}")
        ref_results = {}

    for i, endpoint_url in enumerate(endpoints):
        # Print the endpoint URL in bold blue for terminals that support ANSI escape sequences
        print(f"\n\n===== Benchmarking {BOLD}{BLUE}{endpoint_url}{RESET} =====\n")
        avg_results[endpoint_url] = {}

        prefix_map, _void_schema = get_prefixes_and_schema_for_endpoints([{"endpoint_url": endpoint_url}])
        docs_examples = SparqlExamplesLoader(endpoint_url, examples_file=f"tests/data/examples_{files[i]}.ttl").load()

        # Use special void file for UniProt endpoint
        void_file = None
        if endpoint_url == "https://sparql.uniprot.org/sparql":
            void_file = "tests/void_uniprot.ttl"

        docs_classes = SparqlVoidShapesLoader(endpoint_url, prefix_map=prefix_map, void_file=void_file).load()

        print(f"Found {len(docs_examples)} examples, and {len(docs_classes)} classes")

        splitted_examples = get_folds(docs_examples)
        # Cache reference query results across folds to avoid re-running identical queries.
        for fold_idx, examples_fold in enumerate(splitted_examples):
            fold_num = fold_idx + 1
            print(f"\n--- Running test fold {fold_num} with {len(examples_fold[1])} examples ---\n")

            # Initialize the vector store collection with the training examples (fold[0])
            if qdrant_client.collection_exists(vector_collection):
                qdrant_client.delete_collection(vector_collection)
            qdrant_client.create_collection(
                collection_name=vector_collection,
                vectors_config=VectorParams(size=settings.embedding_dimensions, distance=Distance.COSINE),
            )

            # Generate embeddings and add documents to vectordb
            docs_to_index = examples_fold[0] + docs_classes
            embeddings = list(embedding_model.embed([d.page_content for d in docs_to_index]))
            qdrant_client.upsert(
                collection_name=vector_collection,
                points=qdrant_models.Batch(
                    ids=list(range(1, len(docs_to_index) + 1)),
                    vectors=[emb.tolist() for emb in embeddings],
                    payloads=[doc.metadata for doc in docs_to_index],
                ),
            )

            test_examples = examples_fold[1]
            if LIMIT_FOR_DEV:
                test_examples = test_examples[:LIMIT_FOR_DEV]

            # 1. Run each reference query first and cache their results across folds
            # Also filter out examples that don't have valid reference results
            logger.info("⚡️ Executing reference queries")
            valid_test_examples = []
            for query_num, test_doc in enumerate(test_examples):
                example_endpoint: str = test_doc.metadata.get("endpoint_url", endpoint_url)
                cache_key = f"{example_endpoint} {test_doc.metadata.get('question', '')}"

                # If we've already executed this reference query in a previous fold, reuse it
                if cache_key in ref_results:
                    logger.info(f"🔁 Using cached reference result for query '{test_doc.metadata.get('question')}'")
                    # Only add to valid_test_examples if it has results
                    if ref_results[cache_key] is not None:
                        valid_test_examples.append(test_doc)
                    else:
                        logger.info(
                            f"⊘ Skipping query with no reference results: '{test_doc.metadata.get('question')}'"
                        )
                    continue

                max_retries = 1
                retry_count = 0
                res_ref_finally_pass = False
                while not res_ref_finally_pass and retry_count < max_retries:
                    time.sleep(1)
                    try:
                        query_start_time = time.time()
                        logger.info(f"⏳ {test_doc.metadata['question']}")
                        # logger.info(endpoint_for_query + query_text)
                        # TODO: getting errors from UniProt here
                        res_from_ref = query_sparql(
                            ensure_limit(test_doc.metadata.get("answer", "")),
                            example_endpoint,
                            post=False,
                            client=httpx_client,
                        )
                        logger.info(
                            f"✅ [{query_num}] {len(res_from_ref['results']['bindings'])} results in {time.time() - query_start_time:.2f}s"
                        )
                        # store in cache and per-fold results, persist immediately
                        ref_results[cache_key] = res_from_ref
                        persist_ref_results_cache(ref_results)
                        res_ref_finally_pass = True
                        # Add to valid_test_examples only if it has results
                        valid_test_examples.append(test_doc)
                    except Exception as e:
                        retry_count += 1
                        logger.info(
                            f"❌ Error for reference query {query_num} (attempt {retry_count}/{max_retries}): {e}"
                        )
                        if retry_count >= max_retries:
                            logger.info(f"⚠️ Skipping reference query {query_num} after {max_retries} failed attempts")
                            # Save failed result as None in cache so we don't repeatedly retry across folds
                            ref_results[cache_key] = None
                            # ref_results.append(None)
                            # _persist_ref_results_cache(ref_res_cache_path, ref_results_cache)

            # Use the filtered list of examples that have valid reference results
            test_examples = valid_test_examples
            logger.info(
                f"Testing with {len(test_examples)} valid examples (filtered from original {len(examples_fold[1])})"
            )

            # Executing the test examples
            for model in models:
                model_short = model.split("/")[-1]
                print(f"\n--- Testing model {model} ---\n")

                # Create per-fold JSONL file for logging queries
                file_name = files[i]
                jsonl_filepath = os.path.join(bench_folder, f"{file_name}_{model_short}_fold{fold_num}.jsonl")
                # Clear the JSONL file if it exists from a previous run
                with open(jsonl_filepath, "w") as f:
                    pass

                ref_trec_results = {}
                gen_trec_results = {}

                # Track runtime and token usage per query
                query_metrics: dict[str, list[int | float]] = {
                    "runtimes": [],  # In seconds
                    "prompt_tokens": [],
                    "completion_tokens": [],
                    "total_tokens": [],
                }

                logger.info(f"🔥 Running benchmark with test queries for {model}")
                for query_num, test_doc in enumerate(test_examples):
                    question = test_doc.metadata["question"]
                    expected_query = test_doc.metadata["answer"]
                    example_endpoint = test_doc.metadata["endpoint_url"]
                    cache_key = f"{example_endpoint} {question}"
                    generated_sparql = None
                    query_start_time = time.time()
                    error_msg = None
                    token_usage_data = None
                    res_from_generated = {}
                    response_messages = []

                    try:
                        response = query_chat(question, model, httpx_client)
                        response_messages = response.get("messages", [])
                        chat_resp_md: str = response["messages"][-1]["content"]

                        # Track token usage
                        for msg in response["messages"]:
                            if "response_metadata" in msg and "token_usage" in msg["response_metadata"]:
                                token_usage_data = msg["response_metadata"]["token_usage"]
                                # print(msg["response_metadata"])
                                # Store token usage for this query
                                if token_usage_data:
                                    query_metrics["prompt_tokens"].append(token_usage_data.get("prompt_tokens", 0))
                                    query_metrics["completion_tokens"].append(
                                        token_usage_data.get("completion_tokens", 0)
                                    )
                                    query_metrics["total_tokens"].append(token_usage_data.get("total_tokens", 0))

                        # Extract SPARQL query from response
                        generated_sparqls = extract_sparql_queries(chat_resp_md)
                        # logger.info(generated_sparqls)
                        if len(generated_sparqls) == 0:
                            raise Exception(f"No SPARQL query could be extracted from {chat_resp_md}")
                        generated_sparql = generated_sparqls[-1]

                        # 3. Execute the generated query and compare results
                        res_from_generated = query_sparql(
                            ensure_limit(str(generated_sparql.get("query", "") or "")),
                            str(generated_sparql.get("endpoint_url", "") or ""),
                            client=httpx_client,
                        )

                        # TODO: Get results in TREC eval format and add to main dicts
                        # Only update reference TREC results if we have a valid reference result
                        # ref_res = ref_results[query_num]
                        ref_res = ref_results[cache_key] or {}
                        ref_trec_results.update(sparql_results_to_trec(test_doc.metadata["question"], ref_res))
                        gen_trec_results.update(
                            sparql_results_to_trec(test_doc.metadata["question"], res_from_generated)
                        )

                        # Track runtime
                        query_runtime = time.time() - query_start_time
                        query_metrics["runtimes"].append(query_runtime)

                    except Exception as e:
                        # results["errors"] += 1
                        error_msg = str(e)
                        logger.info(f"❌ Query {query_num}: {question}\n{e}\n")
                        if generated_sparql:
                            logger.info(
                                f"```sparql\n{ensure_limit(str(generated_sparql.get('query', '') or ''))}\n```\n"
                            )
                        logger.info("Expected query:\n")
                        logger.info(f"```sparql\n{expected_query}\n```\n")

                        # Track runtime even on error
                        query_runtime = time.time() - query_start_time
                        query_metrics["runtimes"].append(query_runtime)

                    # Log query to JSONL file
                    ref_res = ref_results.get(cache_key, {})
                    log_query_to_jsonl(
                        filepath=jsonl_filepath,
                        query_num=query_num,
                        question=question,
                        expected_query=expected_query,
                        generated_query=generated_sparql.get("query") if generated_sparql else None,
                        reference_results=ref_res,
                        generated_results=res_from_generated,
                        trec_scores=None,  # Will be added after TREC eval
                        runtime=query_runtime,
                        token_usage=token_usage_data,
                        messages=[
                            {"role": msg.get("role", ""), "content": msg.get("content", "")}
                            for msg in response_messages
                        ],
                        error=error_msg,
                    )

                # 5. Compute TREC eval metrics
                metrics = {"set_F", "set_P", "set_recall"}
                evaluator = pytrec_eval.RelevanceEvaluator(ref_trec_results, metrics)
                trec_results = evaluator.evaluate(gen_trec_results)
                avg: dict[str, float] = {}
                for measure in metrics:
                    avg[measure] = float(
                        pytrec_eval.compute_aggregated_measure(
                            measure,
                            [query_measures[measure] for query_measures in trec_results.values()],
                        )
                    )

                # Calculate average runtime and token usage
                avg["runtime"] = sum(query_metrics["runtimes"]) / len(query_metrics["runtimes"])
                avg["prompt_tokens"] = sum(query_metrics["prompt_tokens"]) / len(query_metrics["prompt_tokens"])
                avg["completion_tokens"] = sum(query_metrics["completion_tokens"]) / len(
                    query_metrics["completion_tokens"]
                )
                avg["total_tokens"] = sum(query_metrics["total_tokens"]) / len(query_metrics["total_tokens"])

                # Calculate median runtime and token usage
                median: dict[str, float] = {}
                median["runtime"] = statistics.median(query_metrics["runtimes"])
                median["prompt_tokens"] = statistics.median(query_metrics["prompt_tokens"])
                median["completion_tokens"] = statistics.median(query_metrics["completion_tokens"])
                median["total_tokens"] = statistics.median(query_metrics["total_tokens"])

                trec_results["average"] = avg
                trec_results["median"] = median
                logger.info(f"📑 TREC evaluation metrics for fold {fold_num} - {model}\n")
                logger.info(trec_results)

                if model not in avg_results[endpoint_url]:
                    avg_results[endpoint_url][model] = {}
                avg_results[endpoint_url][model][fold_num] = avg
        logger.info(f"🏆 Average results across folds for {endpoint_url}")
        for model in avg_results[endpoint_url]:
            logger.info(f"Model: {model}")
            logger.info(json.dumps(avg_results[endpoint_url][model], indent=2))

    logger.info(json.dumps(avg_results, indent=2))

    # Save results to file
    results_file = os.path.join(bench_folder, f"{file_time_prefix}_benchmark_biodata.json")
    with open(results_file, "w") as f:
        json.dump(avg_results, f, indent=2)
    logger.info(f"✅ Benchmark results saved to {results_file}")


if __name__ == "__main__":
    main()
