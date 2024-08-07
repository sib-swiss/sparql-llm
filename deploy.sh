if [ "$1" = "--build" ]; then
    echo "📦️ Re-building"
    ssh expasychat 'sudo -u podman bash -c "cd /var/containers/podman/expasy-chat ; git pull ; podman-compose up --force-recreate --build -d"'
elif [ "$1" = "--logs" ]; then
    ssh expasychat 'sudo -u podman bash -c "cd /var/containers/podman/expasy-chat ; podman-compose logs api"'
elif [ "$1" = "--likes" ]; then
    mkdir -p data/prod
    scp expasychat:/var/containers/podman/expasy-chat/data/logs/likes.jsonl ./data/prod/
    scp expasychat:/var/containers/podman/expasy-chat/data/logs/dislikes.jsonl ./data/prod/
    scp expasychat:/var/containers/podman/expasy-chat/data/logs/user_questions.log ./data/prod/
else
    ssh expasychat 'sudo -u podman bash -c "cd /var/containers/podman/expasy-chat ; git pull ; podman-compose up --force-recreate -d"'
fi
