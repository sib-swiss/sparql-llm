#!/bin/bash

# Script to help deploy the system on the server
# SSH connections:
# expasychat is connecting to the server with your user

# NOTE: sudo password is stored in macOS Keychain under service "expasychat-sudo".
# To store it: security add-generic-password -a "$USER" -s "expasychat-sudo" -w
# To update it: security add-generic-password -U -a "$USER" -s "expasychat-sudo" -w


# Alternatively, connect manually:
# ssh expasychat

## Check env variables
# sudo -u podman bash -c 'cd /var/containers/podman/sparql-llm ; vim .env'

# NOTE: if OOM error, check `dmesg` on server and search for `oom`
# sudo -u podman bash -c 'dmesg'
# sudo -u podman bash -c 'journalctl -k '

# Get sudo password from macOS Keychain, or prompt if not stored
_get_sudo_pass() {
    if command -v security &>/dev/null; then
        security find-generic-password -a "$USER" -s "expasychat-sudo" -w 2>/dev/null && return
    fi
    read -rs -p "sudo password for expasychat: " _PASS
    echo ""
    printf '%s' "$_PASS"
}

ssh_cmd() {
    local sudo_pass
    sudo_pass=$(_get_sudo_pass)
    ssh expasychat "echo '${sudo_pass}' | sudo -S -u podman bash -c 'export XDG_RUNTIME_DIR=/run/user/1001 ; cd /var/containers/podman/sparql-llm ; $1'"
}

if [ "$1" = "build" ]; then
    echo "📦️ Re-building"
    ssh_cmd "git pull ; podman-compose -f compose.prod.yml up --force-recreate --build -d"

elif [ "$1" = "clean" ]; then
    echo "🧹 Cleaning up the vector database"
    ssh_cmd "git pull ; rm -rf data/qdrant data/endpoints_metadata.json ; podman-compose -f compose.prod.yml up --force-recreate -d"

elif [ "$1" = "logs" ]; then
    ssh_cmd "podman-compose -f compose.prod.yml logs api"

elif [ "$1" = "index" ]; then
    echo "🔎 Indexing endpoints in the vector database"
    ssh_cmd "podman-compose -f compose.prod.yml exec api uv run src/sparql_llm/indexing/index_resources.py"

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
    ssh_cmd "git pull ; podman-compose -f compose.prod.yml up --force-recreate -d"
fi

# Fix connectivities issues between api and vectordb (which happens sometimes with podman compose)
# podman exec -it api bash
# podman inspect vectordb | grep IPAddress

# See service that starts the podman-compose:
# systemctl --user cat podman-compose@sparql-llm.service
