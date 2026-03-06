#!/bin/bash
# This script loads RDF data files into a Virtuoso database instance.
#
# Notes:
# - Expects data files in data/dumps/<dataset>.
# - Loads files into named graphs at https://text2sparql.aksw.org/2025/<dataset>/.


## Load in Virtuoso

nohup docker compose exec virtuoso-dbpedia isql -U dba -P dba exec="ld_dir_all('/dumps', '*', ''); rdf_loader_run(); checkpoint;" > virtuoso-load.log 2>&1 &

# # Check number of triples (2501 is default virtuoso init)
# docker compose exec virtuoso-dbpedia isql -U dba -P dba exec="SPARQL SELECT COUNT(*) WHERE { ?s ?p ?o };"

# # Check load status
# docker compose exec virtuoso-dbpedia isql -U dba -P dba exec="SELECT ll_file, ll_graph, ll_state, ll_error FROM DB.DBA.LOAD_LIST;"


## Load in Tentris

# nohup docker compose -f compose.text2sparql.yml run --rm --entrypoint sh tentris-dbpedia -c "cat /dumps/* | tentris --config /config/tentris-config.toml --license /config/tentris-license.toml load" > tentris-load.log 2>&1 &

# files=(
#   dbpedia_2015-10.nt
#   infobox_properties_en.ttl
#   infobox_properties_es.ttl
#   instance_types_en.ttl
#   instance_types_es.ttl
#   instance_types_transitive_en.ttl
#   instance_types_transitive_es.ttl
#   labels_en.ttl
#   labels_es.ttl
#   mappingbased_literals_en.ttl
#   mappingbased_literals_es.ttl
#   mappingbased_objects_en.ttl
#   mappingbased_objects_es.ttl
#   persondata_en.ttl
#   short_abstracts_en.ttl
#   short_abstracts_es.ttl
# )

# for f in "${files[@]}"; do
#   echo "Loading $f ..."
#   curl -s -X POST --data-urlencode "update=LOAD <file:///dumps/$f>" http://localhost:9080/update
#   echo
# done

# # Count triples in Tentris
# curl -H "Content-Type: application/sparql-query" --data "SELECT (COUNT(*) AS ?c) WHERE { ?s ?p ?o }" http://localhost:9080/sparql

# curl -s -X POST http://localhost:9080/sparql -H "Content-Type: application/x-www-form-urlencoded" -H "Accept: application/sparql-results+json" --data-urlencode 'query=SELECT (COUNT(*) AS ?count) WHERE { ?s ?p ?o }'

# curl -sG http://localhost:9080/sparql -H "Accept: application/sparql-results+json" --data-urlencode 'query=SELECT (COUNT(*) AS ?count) WHERE { ?s ?p ?o }'



## Run indexing

# uv run tests/text2sparql/endpoint_schema.py
# VECTORDB_URL=http://localhost:6334/ nohup uv run --extra agent tests/text2sparql/index.py &

nohup docker compose -f compose.text2sparql.yml run text2sparql-api tests/text2sparql/index.py https://text2sparql.aksw.org/2025/dbpedia/ > indexing-endpoint.log 2>&1 &

# nohup docker compose -f compose.text2sparql.yml run text2sparql-api tests/text2sparql/index.py https://text2sparql.aksw.org/2025/corporate/ > indexing-endpoint.log 2>&1 &


## Old script for loading data into Virtuoso with retries

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
