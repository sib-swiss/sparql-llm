ssh expasychat 'sudo -u podman bash -c "cd /var/containers/podman/expasy-chat ; git pull ; podman-compose up --force-recreate --build -d"'
