if [ "$1" = "--build" ]; then
    echo "📦️ Re-building"
    ssh expasychat 'sudo -u podman bash -c "cd /var/containers/podman/expasy-chat ; git pull ; podman-compose up --force-recreate --build -d"'
elif [ "$1" = "--logs" ]; then
    ssh expasychat 'sudo -u podman bash -c "cd /var/containers/podman/expasy-chat ; podman-compose logs api"'
else
    ssh expasychat 'sudo -u podman bash -c "cd /var/containers/podman/expasy-chat ; git pull ; podman-compose up --force-recreate -d"'
fi
