if [ "$1" = "--build" ]; then
    echo "📦️ Re-building"
    ssh expasychat 'sudo -u podman bash -c "cd /var/containers/podman/sparql-llm ; git pull ; podman-compose up --force-recreate --build -d"'
elif [ "$1" = "--logs" ]; then
    ssh expasychat 'sudo -u podman bash -c "cd /var/containers/podman/sparql-llm ; podman-compose logs api"'
elif [ "$1" = "--likes" ]; then
    mkdir -p data/prod
    scp expasychat:/var/containers/podman/sparql-llm/data/logs/likes.jsonl ./data/prod/
    scp expasychat:/var/containers/podman/sparql-llm/data/logs/dislikes.jsonl ./data/prod/
    scp expasychat:/var/containers/podman/sparql-llm/data/logs/user_questions.log ./data/prod/
else
    ssh expasychat 'sudo -u podman bash -c "cd /var/containers/podman/sparql-llm ; git pull ; podman-compose up --force-recreate -d"'
fi
