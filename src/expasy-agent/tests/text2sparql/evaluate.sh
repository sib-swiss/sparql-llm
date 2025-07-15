#!/bin/bash
# This script runs Text2SPARQL evaluation tests against a local API.


API_URL='http://localhost:8765'
ENDPOINT_URL='http://localhost:8890/sparql'
TIMESTAMP=$(date +"%Y%m%d_%H%M")
QUESTIONS="data/benchmarks/Text2SPARQL/queries/questions_db25.yaml"
QUERIES="data/benchmarks/${TIMESTAMP}_Text2SPARQL_queries.json"
RESULTS="data/benchmarks/${TIMESTAMP}_Text2SPARQL_results.json"
CACHE="data/benchmarks/${TIMESTAMP}_Text2SPARQL_responses.db"


# Install the text2sparql-client package in uv environment
uv pip install text2sparql-client

# Ask questions from the questions file on your endpoint
text2sparql ask --answers-db "$CACHE" -o "$QUERIES" "$QUESTIONS" "$API_URL"

# Evaluate the queries against the SPARQL endpoint and save results
text2sparql evaluate -e "$ENDPOINT_URL" -o "$RESULTS" expasy "$QUESTIONS" "$QUERIES"

# Clean up temporary files
rm -f "$QUERIES" "$CACHE"

# Print the results
echo "Average F1 score: $(jq -r '.average.set_F' "$RESULTS")"