#!/bin/bash
# This script runs Text2SPARQL evaluation tests against a local API.
# Run Command: $ uv run src/expasy-agent/tests/text2sparql/evaluate.sh

API_URL='http://localhost:8765'
ENDPOINT_URL='http://localhost:8890/sparql'
TIMESTAMP=$(date +"%Y%m%d_%H%M")
QUESTIONS="data/benchmarks/Text2SPARQL/queries/questions_db25.yaml"
QUERIES="data/benchmarks/${TIMESTAMP}_Text2SPARQL_queries.json"
RESULTS_EN="data/benchmarks/${TIMESTAMP}_EN_Text2SPARQL_results.json"
RESULTS_ES="data/benchmarks/${TIMESTAMP}_ES_Text2SPARQL_results.json"
RESULTS_FULL="data/benchmarks/${TIMESTAMP}_FULL_Text2SPARQL_results.json"
CACHE="data/benchmarks/${TIMESTAMP}_Text2SPARQL_responses.db"


# Install the text2sparql-client package in uv environment
uv pip install text2sparql-client

# Ask questions from the questions file on your endpoint
text2sparql ask --answers-db "$CACHE" -o "$QUERIES" "$QUESTIONS" "$API_URL"

# Evaluate the queries against the SPARQL endpoint and save results
text2sparql evaluate -l "['en']" -e "$ENDPOINT_URL" -o "$RESULTS_EN" expasy "$QUESTIONS" "$QUERIES"
text2sparql evaluate -l "['es']" -e "$ENDPOINT_URL" -o "$RESULTS_ES" expasy "$QUESTIONS" "$QUERIES"
text2sparql evaluate -l "['en','es']" -e "$ENDPOINT_URL" -o "$RESULTS_FULL" expasy "$QUESTIONS" "$QUERIES"

# Clean up temporary files
rm -f "$QUERIES" "$CACHE"

# Print the results
echo "Average F1 score (EN): $(jq -r '.average.set_F' "$RESULTS_EN")"
echo "Average F1 score (ES): $(jq -r '.average.set_F' "$RESULTS_ES")"
echo "Average F1 score (FULL): $(jq -r '.average.set_F' "$RESULTS_FULL")"