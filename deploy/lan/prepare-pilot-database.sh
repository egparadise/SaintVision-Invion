#!/usr/bin/env bash
set -euo pipefail
umask 077

image=${1:?usage: prepare-pilot-database.sh postgres@sha256:<digest> [container] [host-port]}
container=${2:-saintvision-card150-pilot-db}
host_port=${3:-55440}
volume=${container}-data

[[ "$image" =~ ^postgres@sha256:[a-f0-9]{64}$ ]] || {
    echo 'A digest-pinned PostgreSQL image is required.' >&2
    exit 2
}
[[ "$container" =~ ^saintvision-[a-z0-9-]+$ ]] || {
    echo 'The container name is outside the SaintVision ownership namespace.' >&2
    exit 2
}
[[ "$host_port" =~ ^[0-9]+$ ]] && (( host_port >= 1024 && host_port <= 65535 )) || {
    echo 'The loopback host port is invalid.' >&2
    exit 2
}
command -v docker >/dev/null
image_id=$(docker image inspect --format '{{.Id}}' "$image")

if docker container inspect "$container" >/dev/null 2>&1; then
    owner=$(docker container inspect \
        --format '{{index .Config.Labels "ai.saintvision.lan-pilot"}}' "$container")
    existing_image=$(docker container inspect --format '{{.Image}}' "$container")
    [[ "$owner" == 'card150' && "$existing_image" == "$image_id" ]] || {
        echo 'Existing container ownership or image differs; preserving it.' >&2
        exit 1
    }
    if [[ "$(docker container inspect --format '{{.State.Running}}' "$container")" != true ]]; then
        docker start "$container" >/dev/null
    fi
else
    docker run -d --name "$container" \
        --label ai.saintvision.lan-pilot=card150 \
        --restart unless-stopped --pids-limit 256 --memory 768m --cpus 1 \
        --publish "127.0.0.1:${host_port}:5432" \
        --env POSTGRES_DB=saintvision_lan \
        --env POSTGRES_USER=postgres \
        --env POSTGRES_HOST_AUTH_METHOD=trust \
        --mount "type=volume,source=$volume,target=/var/lib/postgresql/data" \
        "$image" >/dev/null
fi

for _attempt in $(seq 1 40); do
    if docker exec "$container" pg_isready -U postgres -d saintvision_lan >/dev/null 2>&1; then
        printf '{"database":"ready","listen":"127.0.0.1:%s","authenticationBoundary":"ssh-tunnel","passwordStored":false}\n' "$host_port"
        exit 0
    fi
    sleep 1
done
echo 'Pilot database readiness timed out.' >&2
exit 1
