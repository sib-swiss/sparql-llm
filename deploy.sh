if [ "$1" = "--no-cache" ]; then
    echo "📦️ Building without cache"
    ssh expasychat 'sudo -u podman bash -c "cd /var/containers/podman/expasy-chat ; git pull ; podman-compose up --force-recreate --build -d"'
else
    ssh expasychat 'sudo -u podman bash -c "cd /var/containers/podman/expasy-chat ; git pull ; podman-compose up --force-recreate -d"'
fi
