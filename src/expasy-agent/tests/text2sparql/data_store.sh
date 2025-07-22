#!/bin/bash
# This script loads RDF data files into a Virtuoso database instance.
#
# Notes:
# - Expects data files in data/benchmarks/Text2SPARQL/dumps/<dataset>.
# - Loads files into named graphs at https://text2sparql.aksw.org/2025/<dataset>/.

MAX_RETRIES=5
VIRTUOSO_PORT=1111
DBA_USER="dba"
DBA_PASSWORD="dba"
DATA_DIR="$(pwd)/data/benchmarks/Text2SPARQL/dumps"

for dataset in $(ls -1 "$DATA_DIR/"); do  
  GRAPH_URI="https://text2sparql.aksw.org/2025/$dataset/"
  for file_path in "$DATA_DIR/$dataset"/*.{nt,ttl,bz2}; do
    [ -e "$file_path" ] || continue  # Skip if no files match
    file_name=$(basename "$file_path")

    retries=0
    while [ $retries -lt $MAX_RETRIES ]; do
      docker exec text2sparql-virtuoso isql $VIRTUOSO_PORT $DBA_USER $DBA_PASSWORD exec="DB.DBA.TTLP_MT(file_to_string_output('/dumps/$dataset/$file_name'), '', '$GRAPH_URI'); checkpoint;"
      if [ $? -eq 0 ]; then
        echo "✅ Successfully loaded $file_name into Virtuoso!"
        break
      else
        retries=$((retries + 1))
        echo "❌ Error loading $file_name (attempt $retries/$MAX_RETRIES). Retrying..."
        sleep 5
      fi
    done

    if [ $retries -eq $MAX_RETRIES ]; then
      echo "❌❌ Failed to load $file_name after $MAX_RETRIES attempts."
    fi
  done

  count=$(docker exec text2sparql-virtuoso isql $VIRTUOSO_PORT $DBA_USER $DBA_PASSWORD exec="SPARQL SELECT COUNT(*) WHERE { GRAPH <$GRAPH_URI> {?s ?p ?o} };" 2>&1 | awk '/^_*$/ { in_block=1; next } /1 Rows\./ { in_block=0; next } in_block')
  echo "Total triples in $dataset: $count"
done