import json
import os
import re

import pandas as pd
import yaml
from rdflib.plugins.sparql.algebra import translateQuery
from rdflib.plugins.sparql.parser import parseQuery

from sparql_llm.utils import query_sparql

RAW_QUERIES_FOLDER = os.path.join("data", "benchmarks", "Text2SPARQL", "queries")
TEXT2SPARQL_DB_QUERIES_FILE = os.path.join(RAW_QUERIES_FOLDER, "questions_db25.yaml")
TEXT2SPARQL_CK_QUERIES_FILE = os.path.join(RAW_QUERIES_FOLDER, "questions_ck25.yaml")
GENERATED_CK_QUERIES_FILE = os.path.join(RAW_QUERIES_FOLDER, "generated_ck.json")
TEXT2SPARQL_ENDPOINT = "http://localhost:8890/sparql/"
QUALD_9_PLUS_QUERIES_FILE = os.path.join(RAW_QUERIES_FOLDER, "qald_9_plus_dbpedia.json")
QUALD_9_PLUS_ENDPOINT = "https://dbpedia.org/sparql"
LC_QuAD_QUERIES_FILE = os.path.join(RAW_QUERIES_FOLDER, "LC-QuAD_v1.json")
LC_QuAD_ENDPOINT = "https://dbpedia.org/sparql"
UNIPROT_QUERIES_FILE = os.path.join(RAW_QUERIES_FOLDER, "uniprot_questions.csv")
CELLOSAURUS_QUERIES_FILE = os.path.join(RAW_QUERIES_FOLDER, "cellosaurus_questions.csv")
BGEE_QUERIES_FILE = os.path.join(RAW_QUERIES_FOLDER, "bgee_questions.csv")
OUTPUT_QUERIES_FILE = os.path.join(os.path.abspath(os.path.dirname(__file__)), "queries.csv")


def count_triple_patterns(query: str) -> int:
    """
    Count the number of triple patterns recursively in a SPARQL query.
    Args:
        query (str): The SPARQL query string.
    Returns:
        int: The number of triple patterns in the query.
    """

    def _count_triples(expr):
        if hasattr(expr, "name") and expr.name == "BGP":
            return len(expr.triples)
        elif hasattr(expr, "name") and expr.name in ("Join", "Union", "LeftJoin"):
            return _count_triples(expr.p1) + _count_triples(expr.p2)
        elif (hasattr(expr, "name") and expr.name == "Filter") or hasattr(expr, "p"):
            return _count_triples(expr.p)
        else:
            return 0

    # Remove aggregate expressions and federations from the query (not parsed by rdflib)
    query = re.sub(r"(COUNT|SUM)\s*\(\s*(?:DISTINCT\s*)?([^\(\)]*|\([^\)]*\))\s*\)", "?x", query, flags=re.IGNORECASE)
    query = re.sub(r"SERVICE\b.*?\{", "{", query, flags=re.IGNORECASE | re.DOTALL)
    try:
        expr = translateQuery(parseQuery(query)).algebra
        count = _count_triples(expr)
    except Exception as e:
        print(f"Error parsing query: {query}, Error: {e}")
        count = None
    return count


def transform_text2sparql_queries(input_file: str, endpoint_url: str) -> pd.DataFrame:
    """
    Transforms text2sparql queries from a YAML file into a DataFrame.

    Args:
        input_file (str): Path to the YAML file containing text2sparql queries.

    Returns:
        pd.DataFrame: DataFrame containing the transformed queries.
    """

    # Load the YAML file
    with open(input_file, encoding="utf-8") as yaml_file:
        data = yaml.safe_load(yaml_file)

    # Parse the YAML data and extract queries
    queries = []
    for item in data.get("questions", []):
        query = {
            "question": item.get("question", {}).get("en", ""),
            "endpoint": endpoint_url,
            "query": item.get("query", {}).get("sparql", ""),
        }
        queries.append(query)
    queries = pd.DataFrame(queries)

    queries["triple patterns"] = queries["query"].apply(count_triple_patterns)

    def safe_query_sparql(query, endpoint):
        try:
            return query_sparql(query, endpoint)
        except Exception:
            return {"results": {"bindings": []}}

    queries["result"] = queries.apply(lambda q: safe_query_sparql(q["query"], q["endpoint"]), axis=1)
    queries["result length"] = queries["result"].apply(lambda r: len(r["results"]["bindings"]) if "results" in r else 1)
    queries["query type"] = queries["query"].apply(lambda q: "ASK" if "ASK WHERE" in q.upper() else "SELECT")
    queries["dataset"] = "Text2SPARQL-" + input_file.split("25.")[-2].split("_")[-1]
    return queries


def transform_qald_9_plus_queries(input_file: str, endpoint_url: str) -> pd.DataFrame:
    """Transforms QALD-9+ queries from a JSON file into a DataFrame.
    Args:
        input_file (str): Path to the JSON file containing QALD-9+ queries.
        endpoint_url (str): SPARQL endpoint URL.
    Returns:
        pd.DataFrame: DataFrame containing the transformed queries.
    """

    queries = []
    with open(input_file, encoding="utf-8") as file:
        data = json.load(file)
        for q in data["questions"]:
            queries.append(
                {
                    "question": next((item["string"] for item in q["question"] if item["language"] == "en"), None),
                    "endpoint": endpoint_url,
                    "query": q["query"]["sparql"],
                }
            )
    queries = pd.DataFrame(queries)
    queries["triple patterns"] = queries["query"].apply(count_triple_patterns)
    queries["result"] = queries.apply(lambda q: query_sparql(q["query"], q["endpoint"]), axis=1)
    queries["result length"] = queries["result"].apply(lambda r: len(r["results"]["bindings"]) if "results" in r else 1)
    queries["query type"] = queries["query"].apply(lambda q: "ASK" if "ASK WHERE" in q.upper() else "SELECT")
    queries["dataset"] = "QALD-9+"
    return queries


def transform_LC_QuAD_queries(input_file: str, endpoint_url: str) -> pd.DataFrame:
    """Transforms LC-QuAD queries from a JSON file into a DataFrame.
    Args:
        input_file (str): Path to the JSON file containing QALD-9+ queries.
        endpoint_url (str): SPARQL endpoint URL.
    Returns:
        pd.DataFrame: DataFrame containing the transformed queries.
    """

    queries = []
    with open(input_file, encoding="utf-8") as file:
        data = json.load(file)
        for q in data:
            queries.append(
                {
                    "question": q["corrected_question"],
                    "endpoint": endpoint_url,
                    "query": q["sparql_query"],
                }
            )
    queries = pd.DataFrame(queries)
    queries["triple patterns"] = queries["query"].apply(count_triple_patterns)
    queries["result"] = queries.apply(lambda q: query_sparql(q["query"], q["endpoint"]), axis=1)
    queries["result length"] = queries["result"].apply(lambda r: len(r["results"]["bindings"]) if "results" in r else 1)
    queries["query type"] = queries["query"].apply(lambda q: "ASK" if "ASK WHERE" in q.upper() else "SELECT")
    queries["dataset"] = "LC-QuAD"
    return queries


def transform_Generated_CK_queries(input_file: str, endpoint_url: str) -> pd.DataFrame:
    """Transforms generated CK queries from a JSON file into a DataFrame.
    Args:
        input_file (str): Path to the JSON file containing generated CK queries.
        endpoint_url (str): SPARQL endpoint URL.
    Returns:
        pd.DataFrame: DataFrame containing the transformed queries.
    """
    queries = []
    with open(input_file, encoding="utf-8") as file:
        data = json.load(file)
        for q in data:
            queries.append(
                {
                    "question": q["natural_language"],
                    "endpoint": endpoint_url,
                    "query": q["sparql_query"],
                }
            )

    queries = pd.DataFrame(queries)
    queries["triple patterns"] = queries["query"].apply(count_triple_patterns)

    def safe_query_sparql(query, endpoint):
        try:
            return query_sparql(query, endpoint)
        except Exception:
            return {"results": {"bindings": []}}

    queries["result"] = queries.apply(lambda q: safe_query_sparql(q["query"], q["endpoint"]), axis=1)
    queries["result length"] = queries["result"].apply(lambda r: len(r["results"]["bindings"]) if "results" in r else 1)
    queries["query type"] = queries["query"].apply(lambda q: "ASK" if "ASK WHERE" in q.upper() else "SELECT")
    queries = queries[queries["result length"] != 0]
    queries["dataset"] = "Generated-CK"

    return queries

def transform_bioqueries(uniprot_file: str, cellosaurus_file: str, bgee_file: str) -> pd.DataFrame:
    """
    Transforms bioqueries from CSV files into a DataFrame.
    CSV files dowloaded from https://sib-swiss.github.io/sparql-editor using the query for queries: https://github.com/sib-swiss/sparql-examples.

    Args:
        uniprot_file (str): Path to the CSV file containing Uniprot queries.
        cellosaurus_file (str): Path to the CSV file containing Cellosaurus queries.
        bgee_file (str): Path to the CSV file containing Bgee queries.

    Returns:
        pd.DataFrame: DataFrame containing the transformed queries.
    """

    uniprot = pd.read_csv(uniprot_file)
    uniprot["dataset"] = "Uniprot"
    cellosaurus = pd.read_csv(cellosaurus_file)
    cellosaurus["dataset"] = "Cellosaurus"
    bgee = pd.read_csv(bgee_file)
    bgee["dataset"] = "Bgee"

    queries = pd.concat([uniprot, cellosaurus, bgee], ignore_index=True)
    queries["triple patterns"] = queries["query"].apply(count_triple_patterns)
    queries["query type"] = queries["query"].apply(lambda q: "ASK" if "ASK WHERE" in q.upper() else "SELECT")
    queries["federated"] = queries["query"].apply(lambda q: True if "SERVICE" in q.upper() else False)
    queries = queries[queries['triple patterns'] != 0]

    return queries

if __name__ == "__main__":
    queries = []
    if os.path.exists(OUTPUT_QUERIES_FILE):
        queries.append(pd.read_csv(OUTPUT_QUERIES_FILE))
    else:
        queries.append(transform_text2sparql_queries(TEXT2SPARQL_DB_QUERIES_FILE, TEXT2SPARQL_ENDPOINT))
        queries.append(transform_text2sparql_queries(TEXT2SPARQL_CK_QUERIES_FILE, TEXT2SPARQL_ENDPOINT))
        queries.append(transform_qald_9_plus_queries(QUALD_9_PLUS_QUERIES_FILE, QUALD_9_PLUS_ENDPOINT))
        queries.append(transform_LC_QuAD_queries(LC_QuAD_QUERIES_FILE, LC_QuAD_ENDPOINT))
        queries.append(transform_Generated_CK_queries(GENERATED_CK_QUERIES_FILE, TEXT2SPARQL_ENDPOINT))
        queries.append(transform_bioqueries(UNIPROT_QUERIES_FILE, CELLOSAURUS_QUERIES_FILE, BGEE_QUERIES_FILE))
    queries = pd.concat(queries, ignore_index=True)
    queries.to_csv(OUTPUT_QUERIES_FILE, index=False)