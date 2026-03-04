#!/bin/bash
# This script loads RDF data files into a Virtuoso database instance.
#
# Notes:
# - Expects data files in data/dumps/<dataset>.
# - Loads files into named graphs at https://text2sparql.aksw.org/2025/<dataset>/.

# docker compose exec virtuoso-dbpedia isql -U dba -P dba exec="ld_dir_all('/dumps', '*', ''); rdf_loader_run(); checkpoint;"

# # Check number of triples (2501 is default virtuoso init)
# docker compose exec virtuoso-dbpedia isql -U dba -P dba exec="SPARQL SELECT COUNT(*) WHERE { ?s ?p ?o };"

# # Check load status
# docker compose exec virtuoso-dbpedia isql -U dba -P dba exec="SELECT ll_file, ll_graph, ll_state, ll_error FROM DB.DBA.LOAD_LIST;"

docker compose -f compose.text2sparql.yml run --rm --entrypoint sh tentris-dbpedia -c "cat /dumps/* | tentris --config /config/tentris-server-config.toml --license /config/tentris-license.toml load"


# Generate schema:
# uv run tests/text2sparql/endpoint_schema.py
# uv run tests/text2sparql/index.py


# MAX_RETRIES=5
# VIRTUOSO_PORT=1111
# DBA_USER="dba"
# DBA_PASSWORD="dba"
# DATA_DIR="$(pwd)/data/dumps"

# for dataset in $(ls -1 "$DATA_DIR/"); do
#   # GRAPH_URI="https://text2sparql.aksw.org/2025/$dataset/"
#   for file_path in "$DATA_DIR/$dataset"/*.{nt,ttl,bz2}; do
#     [ -e "$file_path" ] || continue  # Skip if no files match
#     file_name=$(basename "$file_path")

#     retries=0
#     while [ $retries -lt $MAX_RETRIES ]; do
#       docker compose exec virtuoso-$dataset isql $VIRTUOSO_PORT $DBA_USER $DBA_PASSWORD exec="DB.DBA.TTLP_MT(file_to_string_output('/dumps/$dataset/$file_name'), '', ''); checkpoint;"
#       if [ $? -eq 0 ]; then
#         echo "✅ Successfully loaded $file_name into Virtuoso!"
#         break
#       else
#         retries=$((retries + 1))
#         echo "❌ Error loading $file_name (attempt $retries/$MAX_RETRIES). Retrying..."
#         sleep 5
#       fi
#     done

#     if [ $retries -eq $MAX_RETRIES ]; then
#       echo "❌❌ Failed to load $file_name after $MAX_RETRIES attempts."
#     fi
#   done

#   count=$(docker compose exec virtuoso-dbpedia isql $VIRTUOSO_PORT $DBA_USER $DBA_PASSWORD exec="SPARQL SELECT COUNT(*) WHERE { ?s ?p ?o };" 2>&1 | awk '/^_*$/ { in_block=1; next } /1 Rows\./ { in_block=0; next } in_block')
#   echo "Total triples in $dataset: $count"
# done
