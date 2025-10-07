#!/bin/bash
# This script runs Text2SPARQL evaluation tests against a local API.
# Run Command: $ uv run src/expasy-agent/tests/text2sparql/evaluate.sh [ck|db]

API_URL='http://localhost:8765'
ENDPOINT_URL='http://localhost:8890/sparql'
TIMESTAMP=$(date +"%Y%m%d_%H%M")
QUESTIONS_DB="data/benchmarks/Text2SPARQL/queries/questions_db25.yaml"
QUESTIONS_CK="data/benchmarks/Text2SPARQL/queries/questions_ck25.yaml"
QUERIES="data/benchmarks/${TIMESTAMP}_Text2SPARQL_queries.json"
RESULTS_EN="data/benchmarks/${TIMESTAMP}_EN_Text2SPARQL_results.json"
RESULTS_ES="data/benchmarks/${TIMESTAMP}_ES_Text2SPARQL_results.json"
RESULTS_CK="data/benchmarks/${TIMESTAMP}_CK_Text2SPARQL_results.json"
CACHE="data/benchmarks/${TIMESTAMP}_Text2SPARQL_responses.db"


# Install the text2sparql-client package in uv environment
uv pip install text2sparql-client

#if the argument contains "ck" then use the ck questions file
if [[ "$1" == *"ck"* ]]; then
    # Ask questions from the questions file on your endpoint
    uv run text2sparql ask --answers-db "$CACHE" -o "$QUERIES" "$QUESTIONS_CK" "$API_URL"

    # Evaluate the queries against the SPARQL endpoint and save results
    uv run text2sparql evaluate -e "$ENDPOINT_URL" -o "$RESULTS_CK" ExpasyGPT "$QUESTIONS_CK" "$QUERIES"
fi

# if the argument contains "db" then use the db questions file
if [[ "$1" == *"db"* ]]; then
    # Ask questions from the questions file on your endpoint
    uv run text2sparql ask --answers-db "$CACHE" -o "$QUERIES" "$QUESTIONS_DB" "$API_URL"

    # Evaluate the queries against the SPARQL endpoint and save results
    uv run text2sparql evaluate -l "['en']" -e "$ENDPOINT_URL" -o "$RESULTS_EN" ExpasyGPT "$QUESTIONS_DB" "$QUERIES"
    uv run text2sparql evaluate -l "['es']" -e "$ENDPOINT_URL" -o "$RESULTS_ES" ExpasyGPT "$QUESTIONS_DB" "$QUERIES"
fi

# Print the results
if [[ "$1" == *"ck"* ]]; then
    echo "Average F1 score (CK): $(jq -r '.average.set_F' "$RESULTS_CK")"
fi
if [[ "$1" == *"db"* ]]; then
    echo "Average F1 score (EN): $(jq -r '.average.set_F' "$RESULTS_EN")"
    echo "Average F1 score (ES): $(jq -r '.average.set_F' "$RESULTS_ES")"
fi