#!/usr/bin/env bash
set -euo pipefail
umask 077

image=${1:?usage: prepare-pilot-database.sh postgres@sha256:<digest> [container] [host-port] <operator-private-dir> [network]}
container=${2:-saintvision-card150-pilot-db}
host_port=${3:-55440}
private_dir=${4:?an absolute operator-private credential directory is required}
network=${5:-${container}-internal}
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
[[ "$private_dir" == /* && ! -L "$private_dir" ]] || {
    echo 'The credential directory must be an absolute non-symlink path.' >&2
    exit 2
}
[[ "$network" =~ ^saintvision-[a-z0-9-]+$ ]] || {
    echo 'The network name is outside the SaintVision ownership namespace.' >&2
    exit 2
}
command -v docker >/dev/null
command -v openssl >/dev/null
image_id=$(docker image inspect --format '{{.Id}}' "$image")
mkdir -p "$private_dir"
chmod 700 "$private_dir"
postgres_password=$private_dir/postgres.password
runtime_password=$private_dir/inv-lan-runtime.password
admin_pgpass=$private_dir/admin.pgpass
runtime_pgpass=$private_dir/runtime.pgpass
if [[ ! -e "$postgres_password" ]]; then
    openssl rand -hex 32 >"$postgres_password"
fi
if [[ ! -e "$runtime_password" ]]; then
    openssl rand -hex 32 >"$runtime_password"
fi
chmod 600 "$postgres_password" "$runtime_password"
postgres_value=$(tr -d '\r\n' <"$postgres_password")
runtime_value=$(tr -d '\r\n' <"$runtime_password")
[[ "$postgres_value" =~ ^[a-f0-9]{64}$ && "$runtime_value" =~ ^[a-f0-9]{64}$ ]] || {
    echo 'Stored database credentials are invalid.' >&2
    exit 1
}
printf '127.0.0.1:%s:saintvision_lan:postgres:%s\n' "$host_port" "$postgres_value" >"$admin_pgpass"
printf '127.0.0.1:%s:saintvision_lan:inv_lan_runtime:%s\n' "$host_port" "$runtime_value" >"$runtime_pgpass"
chmod 600 "$admin_pgpass" "$runtime_pgpass"
unset postgres_value runtime_value

if docker network inspect "$network" >/dev/null 2>&1; then
    owner=$(docker network inspect --format '{{index .Labels "ai.saintvision.lan-pilot"}}' "$network")
    internal=$(docker network inspect --format '{{.Internal}}' "$network")
    [[ "$owner" == 'card150' && "$internal" == false ]] || {
        echo 'Existing network ownership or isolation differs; preserving it.' >&2
        exit 1
    }
else
    docker network create --label ai.saintvision.lan-pilot=card150 "$network" >/dev/null
fi

if docker container inspect "$container" >/dev/null 2>&1; then
    owner=$(docker container inspect \
        --format '{{index .Config.Labels "ai.saintvision.lan-pilot"}}' "$container")
    existing_image=$(docker container inspect --format '{{.Image}}' "$container")
    attached=$(docker container inspect --format "{{if index .NetworkSettings.Networks \"$network\"}}yes{{end}}" "$container")
    [[ "$owner" == 'card150' && "$existing_image" == "$image_id" && "$attached" == yes ]] || {
        echo 'Existing container ownership, image, or isolated network differs; preserving it.' >&2
        exit 1
    }
    if [[ "$(docker container inspect --format '{{.State.Running}}' "$container")" != true ]]; then
        docker start "$container" >/dev/null
    fi
else
    docker run -d --name "$container" \
        --label ai.saintvision.lan-pilot=card150 \
        --restart unless-stopped --pids-limit 256 --memory 768m --cpus 1 \
        --network "$network" \
        --publish "127.0.0.1:${host_port}:5432" \
        --env POSTGRES_DB=saintvision_lan \
        --env POSTGRES_USER=postgres \
        --env POSTGRES_PASSWORD_FILE=/run/secrets/postgres-password \
        --env 'POSTGRES_INITDB_ARGS=--auth-host=scram-sha-256 --auth-local=scram-sha-256' \
        --mount "type=bind,source=$postgres_password,target=/run/secrets/postgres-password,readonly" \
        --mount "type=bind,source=$runtime_password,target=/run/secrets/runtime-password,readonly" \
        --mount "type=volume,source=$volume,target=/var/lib/postgresql/data" \
        "$image" >/dev/null
fi

ready=false
for _attempt in $(seq 1 40); do
    if docker exec "$container" sh -ec \
        'PGPASSWORD=$(cat /run/secrets/postgres-password); export PGPASSWORD; exec psql -U postgres -d saintvision_lan -Atqc "SELECT 1"' \
        2>/dev/null | grep -qx 1; then
        ready=true
        break
    fi
    sleep 1
done
[[ "$ready" == true ]] || {
    echo 'Pilot database readiness timed out.' >&2
    exit 1
}
docker exec -i "$container" sh -s <<'CONTAINER' >/dev/null
set -eu
export PGPASSWORD="$(cat /run/secrets/postgres-password)"
runtime_password=$(cat /run/secrets/runtime-password)
psql -U postgres -d saintvision_lan -v ON_ERROR_STOP=1 \
    --set=runtime_password="$runtime_password" <<'SQL'
DO $$
BEGIN
    IF NOT EXISTS (SELECT 1 FROM pg_roles WHERE rolname = 'inv_lan_runtime') THEN
        CREATE ROLE inv_lan_runtime LOGIN NOSUPERUSER NOBYPASSRLS NOCREATEDB NOCREATEROLE;
    END IF;
END
$$;
SELECT format('ALTER ROLE inv_lan_runtime PASSWORD %L', :'runtime_password') \gexec
SQL
CONTAINER
printf '{"database":"ready","listen":"127.0.0.1:%s","authenticationBoundary":"scram-plus-ssh-tunnel","credentialStorage":"operator-private-files","network":"dedicated-user-defined"}\n' "$host_port"
