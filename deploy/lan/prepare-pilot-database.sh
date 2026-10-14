#!/usr/bin/env bash
set -euo pipefail
umask 077

image=${1:?usage: prepare-pilot-database.sh postgres@sha256:<digest> [container] [host-port] <operator-private-dir> [network] [database]}
container=${2:-saintvision-card150-pilot-db}
host_port=${3:-55440}
private_dir=${4:?an absolute operator-private credential directory is required}
network=${5:-${container}-internal}
database=${6:-saintvision_lan}
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
[[ ${#database} -le 63 && "$database" =~ ^saintvision_lan(_[a-z0-9]+)*$ ]] || {
    echo 'The database name is outside the SaintVision pilot namespace.' >&2
    exit 2
}
runtime_role=${database/saintvision_lan/inv_lan_runtime}
command -v docker >/dev/null
command -v openssl >/dev/null
image_id=$(docker image inspect --format '{{.Id}}' "$image")
mkdir -p "$private_dir"
chmod 700 "$private_dir"
postgres_password=$private_dir/postgres.password
if [[ "$database" == saintvision_lan ]]; then
    runtime_password=$private_dir/inv-lan-runtime.password
    admin_pgpass=$private_dir/admin.pgpass
    runtime_pgpass=$private_dir/runtime.pgpass
else
    runtime_password=$private_dir/${runtime_role}.password
    admin_pgpass=$private_dir/${database}-admin.pgpass
    runtime_pgpass=$private_dir/${database}-runtime.pgpass
fi
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
printf '127.0.0.1:%s:%s:postgres:%s\n' "$host_port" "$database" "$postgres_value" >"$admin_pgpass"
printf '127.0.0.1:%s:%s:%s:%s\n' \
    "$host_port" "$database" "$runtime_role" "$runtime_value" >"$runtime_pgpass"
chmod 600 "$admin_pgpass" "$runtime_pgpass"

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

container_preexisting=false
if docker container inspect "$container" >/dev/null 2>&1; then
    container_preexisting=true
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
    if ! docker exec -i "$container" sh -ec '
        IFS= read -r PGPASSWORD
        export PGPASSWORD
        exec psql -h 127.0.0.1 -U postgres -d postgres -Atqc "SELECT 1"
    ' <"$postgres_password" 2>/dev/null | grep -qx 1; then
        echo 'The operator admin credential does not match the existing pilot database.' >&2
        exit 1
    fi
else
    if docker volume inspect "$volume" >/dev/null 2>&1; then
        echo 'Existing pilot database volume has no matching owned container; preserving it.' >&2
        exit 1
    fi
    docker run -d --name "$container" \
        --label ai.saintvision.lan-pilot=card150 \
        --restart unless-stopped --pids-limit 256 --memory 768m --cpus 1 \
        --network "$network" \
        --publish "127.0.0.1:${host_port}:5432" \
        --env "POSTGRES_DB=$database" \
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
        'PGPASSWORD=$(cat /run/secrets/postgres-password); export PGPASSWORD; exec psql -U postgres -d postgres -Atqc "SELECT 1"' \
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

if [[ "$container_preexisting" == true ]]; then
    existing_database=$(docker exec -i "$container" sh -s -- "$database" <<'CONTAINER'
set -eu
export PGPASSWORD="$(cat /run/secrets/postgres-password)"
exec psql -U postgres -d postgres -v ON_ERROR_STOP=1 -v database_name="$1" -At <<'SQL'
SELECT count(*) FROM pg_database WHERE datname = :'database_name';
SQL
CONTAINER
)
    existing_role=$(docker exec -i "$container" sh -s -- "$runtime_role" <<'CONTAINER'
set -eu
export PGPASSWORD="$(cat /run/secrets/postgres-password)"
exec psql -U postgres -d postgres -v ON_ERROR_STOP=1 -v runtime_role="$1" -At <<'SQL'
SELECT count(*) FROM pg_roles WHERE rolname = :'runtime_role';
SQL
CONTAINER
)
    [[ "$existing_database" == 0 && "$existing_role" == 0 ]] || {
        echo 'Requested pilot database or runtime role already exists; preserving it.' >&2
        exit 1
    }
    if ! docker exec -i "$container" sh -s -- "$database" <<'CONTAINER' >/dev/null
set -eu
export PGPASSWORD="$(cat /run/secrets/postgres-password)"
exec psql -U postgres -d postgres -v ON_ERROR_STOP=1 -v database_name="$1" <<'SQL'
SELECT format('CREATE DATABASE %I', :'database_name') \gexec
SQL
CONTAINER
    then
        echo 'Pilot database creation failed; no existing database was overwritten.' >&2
        exit 1
    fi
fi

if ! {
    cat <<'SQL'
SET log_statement = 'none';
SET log_min_error_statement = 'panic';
SQL
    printf "\\set runtime_password '%s'\n" "$runtime_value"
    cat <<'SQL'
SELECT format(
    'CREATE ROLE %I LOGIN NOSUPERUSER NOBYPASSRLS NOCREATEDB NOCREATEROLE NOREPLICATION',
    :'runtime_role'
) WHERE NOT EXISTS (SELECT 1 FROM pg_roles WHERE rolname = :'runtime_role') \gexec
SELECT format(
    'ALTER ROLE %I LOGIN NOSUPERUSER NOBYPASSRLS NOCREATEDB NOCREATEROLE NOREPLICATION PASSWORD %L',
    :'runtime_role', :'runtime_password'
) \gexec
SQL
} | docker exec -i "$container" sh -ec '
set -eu
export PGPASSWORD="$(cat /run/secrets/postgres-password)"
exec psql -U postgres -d "$1" -v ON_ERROR_STOP=1 -v runtime_role="$2" 2>/dev/null
' _ "$database" "$runtime_role" >/dev/null
then
    echo 'Pilot runtime role hardening failed; diagnostics suppressed.' >&2
    exit 1
fi
unset postgres_value runtime_value
printf '{"database":"ready","databaseName":"%s","runtimeRole":"%s","listen":"127.0.0.1:%s","authenticationBoundary":"scram-plus-ssh-tunnel","credentialStorage":"operator-private-files","network":"dedicated-user-defined"}\n' \
    "$database" "$runtime_role" "$host_port"
