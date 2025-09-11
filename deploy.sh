#!/bin/bash

# Script to help deploy the system on the server
# SSH connections:
# expasychat is connecting to the server with your user
# expasychatpodman is connecting to the server with the podman user (used to run the containers)

# ssh expasychat
## Just restart:
# sudo -u podman bash -c 'cd /var/containers/podman/sparql-llm ; XDG_RUNTIME_DIR=/run/user/1001 podman-compose up --force-recreate -d'
## Pull and restart:
# sudo -u podman bash -c 'cd /var/containers/podman/sparql-llm ; git pull ; XDG_RUNTIME_DIR=/run/user/1001 podman-compose up --force-recreate -d'
## Show logs:
# sudo -u podman bash -c 'cd /var/containers/podman/sparql-llm ; XDG_RUNTIME_DIR=/run/user/1001 podman-compose logs'

## Re-index
# sudo -u podman bash -c 'cd /var/containers/podman/sparql-llm ; XDG_RUNTIME_DIR=/run/user/1001 podman-compose exec api uv run src/expasy_agent/indexing/index_resources.py'


# NOTE: if OOM error, check `dmsg` on server and search for `oom`
# sudo -u podman bash -c 'journalctl -k '

# sudo -u podman bash -c 'cd /var/containers/podman/sparql-llm ; tail -f data/logs/expasygpt_podman.log'



ssh_cmd() {
    ssh -t expasychat "sudo -u podman bash -c 'cd /var/containers/podman/sparql-llm ; XDG_RUNTIME_DIR=/run/user/1001 $1'"
}

if [ "$1" = "build" ]; then
    echo "📦️ Re-building"
    # cd chat-with-context
    # npm run build:demo
    # cd ..
    # ssh_cmd "git pull ; rm -rf src/expasy-agent/src/expasy_agent/webapp"
    # scp -r ./src/expasy-agent/src/expasy_agent/webapp expasychatpodman:/var/containers/podman/sparql-llm/src/expasy-agent/src/expasy_agent/
    ssh_cmd "git pull ; podman-compose up --force-recreate --build -d"

elif [ "$1" = "clean" ]; then
    echo "🧹 Cleaning up the vector database"
    ssh_cmd "git pull ; rm -rf data/qdrant ; podman-compose up --force-recreate -d"

elif [ "$1" = "logs" ]; then
    ssh_cmd "podman-compose logs api"

elif [ "$1" = "index" ]; then
    echo "🔎 Indexing endpoints in the vector database"
    ssh_cmd "podman-compose exec api uv run src/expasy_agent/indexing/index_resources.py"

elif [ "$1" = "import-entities-index" ]; then
    echo "Import entities embeddings from adsicore which has GPU to generate them"
    scp -r adsicore:/mnt/scratch/sparql-llm/data/qdrant/collections/entities ./data/qdrant/collections/entities
    # ssh adsicore "tar cJf - /mnt/scratch/sparql-llm/data/qdrant/collections/entities" | tar xJf - -C ./data/qdrant/collections/entities

    # scp -r adsicore:/mnt/scratch/sparql-llm/data/qdrant/collections/entities expasychatpodman:/var/containers/podman/sparql-llm/data/qdrant/collections/entities
    # zip -r data/entities.zip data/qdrant/collections/entities

elif [ "$1" = "likes" ]; then
    mkdir -p data/prod
    scp expasychat:/var/containers/podman/sparql-llm/data/logs/likes.jsonl ./data/prod/
    scp expasychat:/var/containers/podman/sparql-llm/data/logs/dislikes.jsonl ./data/prod/
    scp expasychat:/var/containers/podman/sparql-llm/data/logs/user_questions.log ./data/prod/

else
    ssh_cmd "git pull ; podman-compose up --force-recreate -d"
fi

# Fix connectivities issues between api and vectordb (which happens sometimes with podman compose)
# podman exec -it api bash
# podman inspect vectordb | grep IPAddress

# See service that starts the podman-compose:
# systemctl --user cat podman-compose@sparql-llm.service
