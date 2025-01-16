#!/bin/bash

ssh_cmd() {
    ssh expasychat "sudo -u podman bash -c 'cd /var/containers/podman/sparql-llm ; $1'"
}

if [ "$1" = "build" ]; then
    echo "📦️ Re-building"
    scp -r ./packages/expasy-agent/src/expasy_agent/webapp expasychat:/var/containers/podman/sparql-llm/packages/expasy-agent/src/expasy_agent/webapp
    ssh_cmd "git pull ; podman-compose up --force-recreate --build -d"

elif [ "$1" = "clean" ]; then
    echo "🧹 Cleaning up the vector database"
    ssh_cmd "git pull ; rm -rf data/qdrant ; podman-compose up --force-recreate -d"

elif [ "$1" = "logs" ]; then
    ssh_cmd "podman-compose logs api"

elif [ "$1" = "index" ]; then
    echo "🔎 Indexing endpoints in the vector database"
    ssh_cmd "podman-compose exec api python src/expasy_agent/indexing/index_endpoints.py"

elif [ "$1" = "likes" ]; then
    mkdir -p data/prod
    scp expasychat:/var/containers/podman/sparql-llm/data/logs/likes.jsonl ./data/prod/
    scp expasychat:/var/containers/podman/sparql-llm/data/logs/dislikes.jsonl ./data/prod/
    scp expasychat:/var/containers/podman/sparql-llm/data/logs/user_questions.log ./data/prod/

else
    ssh_cmd "git pull ; podman-compose up --force-recreate -d"
fi
