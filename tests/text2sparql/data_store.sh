#!/bin/bash
# This script loads RDF data files into a Virtuoso database instance.
#
# Notes:
# - Expects data files in data/dumps/<dataset>.
# - Loads files into named graphs at https://text2sparql.aksw.org/2025/<dataset>/.


## Load in Virtuoso

nohup docker compose exec virtuoso-dbpedia isql -U dba -P dba exec="ld_dir_all('/dumps', '*', ''); rdf_loader_run(); checkpoint;" > virtuoso-load.log 2>&1 &
nohup docker compose exec virtuoso-corporate isql -U dba -P dba exec="ld_dir_all('/dumps', '*', ''); rdf_loader_run(); checkpoint;" > virtuoso-load.log 2>&1 &

# # Check number of triples (2501 is default virtuoso init)
# docker compose exec virtuoso-dbpedia isql -U dba -P dba exec="SPARQL SELECT COUNT(*) WHERE { ?s ?p ?o };"

# # Check load status
# docker compose exec virtuoso-dbpedia isql -U dba -P dba exec="SELECT ll_file, ll_graph, ll_state, ll_error FROM DB.DBA.LOAD_LIST;"


## Run indexing

nohup docker compose -f compose.text2sparql.yml run text2sparql-api tests/text2sparql/index.py https://text2sparql.aksw.org/2025/dbpedia/ > indexing-dbpedia.log 2>&1 &

nohup docker compose -f compose.text2sparql.yml run text2sparql-api tests/text2sparql/index.py https://text2sparql.aksw.org/2025/corporate/ > indexing-corporate.log 2>&1 &


## Query API

# curl -G https://biosoda.unil.ch/sparql-llm/ --data-urlencode "dataset=https://text2sparql.aksw.org/2025/dbpedia/" --data-urlencode "query=How many unique authors have written science fiction novels?"
