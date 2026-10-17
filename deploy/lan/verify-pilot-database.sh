#!/usr/bin/env bash
set -euo pipefail

container=${1:?usage: verify-pilot-database.sh <container> <network> [database] [operator-private-dir]}
network=${2:?usage: verify-pilot-database.sh <container> <network> [database] [operator-private-dir]}
database=${3-saintvision_lan}
private_dir=${4:-}
[[ "$container" =~ ^saintvision-[a-z0-9-]+$ && "$network" =~ ^saintvision-[a-z0-9-]+$ ]] || {
    echo 'Container or network is outside the SaintVision ownership namespace.' >&2
    exit 2
}
[[ ${#database} -le 63 && "$database" =~ ^saintvision_lan(_[a-z0-9]+)*$ ]] || {
    echo 'The database name is outside the SaintVision pilot namespace.' >&2
    exit 2
}
runtime_role=${database/saintvision_lan/inv_lan_runtime}
if [[ "$database" != saintvision_lan && -z "$private_dir" ]]; then
    echo 'A private credential directory is required for a namespaced pilot database.' >&2
    exit 2
fi
if [[ -n "$private_dir" ]]; then
    [[ "$private_dir" == /* && ! -L "$private_dir" ]] || {
        echo 'The credential directory must be an absolute non-symlink path.' >&2
        exit 2
    }
    runtime_password=$private_dir/${runtime_role}.password
    [[ -f "$runtime_password" && ! -L "$runtime_password" ]] || {
        echo 'The runtime credential file is missing or unsafe.' >&2
        exit 2
    }
    [[ "$(stat -c '%a' "$runtime_password")" == 600 ]] || {
        echo 'The runtime credential file must be owner-only.' >&2
        exit 2
    }
fi

internal=$(docker network inspect --format '{{.Internal}}' "$network")
owner=$(docker network inspect --format '{{index .Labels "ai.saintvision.lan-pilot"}}' "$network")
network_count=$(docker container inspect --format '{{len .NetworkSettings.Networks}}' "$container")
attached=$(docker container inspect --format "{{if index .NetworkSettings.Networks \"$network\"}}yes{{end}}" "$container")
loopback=$(docker container inspect \
    --format '{{with (index (index .HostConfig.PortBindings "5432/tcp") 0)}}{{.HostIp}}{{end}}' \
    "$container")
[[ "$internal" == false && "$owner" == card150 && "$network_count" == 1 && "$attached" == yes ]] || {
    echo 'Pilot database network isolation differs.' >&2
    exit 1
}
[[ "$loopback" == 127.0.0.1 ]] || {
    echo 'Pilot database publish address is not loopback.' >&2
    exit 1
}

if docker exec "$container" sh -ec \
    'PGPASSFILE=/dev/null exec psql -h 127.0.0.1 -U postgres -d "$1" -Atqc "SELECT 1"' \
    _ "$database" \
    >/dev/null 2>&1; then
    echo 'Pilot database accepted a missing credential.' >&2
    exit 1
fi
if docker exec "$container" sh -ec \
    'PGPASSWORD=wrong; export PGPASSWORD; exec psql -h 127.0.0.1 -U postgres -d "$1" -Atqc "SELECT 1"' \
    _ "$database" \
    >/dev/null 2>&1; then
    echo 'Pilot database accepted an incorrect credential.' >&2
    exit 1
fi
admin=$(docker exec "$container" sh -ec \
    'PGPASSWORD=$(cat /run/secrets/postgres-password); export PGPASSWORD; exec psql -h 127.0.0.1 -U postgres -d "$1" -Atqc "SELECT current_user"' \
    _ "$database")
if [[ -n "$private_dir" ]]; then
    runtime=$(docker exec -i "$container" sh -ec \
        'IFS= read -r PGPASSWORD; export PGPASSWORD; exec psql -h 127.0.0.1 -U "$1" -d "$2" -Atqc "SELECT current_user"' \
        _ "$runtime_role" "$database" <"$runtime_password")
else
    runtime=$(docker exec "$container" sh -ec \
        'PGPASSWORD=$(cat /run/secrets/runtime-password); export PGPASSWORD; exec psql -h 127.0.0.1 -U "$1" -d "$2" -Atqc "SELECT current_user"' \
        _ "$runtime_role" "$database")
fi
runtime_privileges=$(docker exec -i "$container" sh -s -- "$database" "$runtime_role" <<'CONTAINER'
set -eu
export PGPASSWORD="$(cat /run/secrets/postgres-password)"
exec psql -U postgres -d "$1" -v ON_ERROR_STOP=1 -v runtime_role="$2" -At <<'SQL'
SELECT rolsuper, rolbypassrls, rolcreatedb, rolcreaterole, rolreplication
FROM pg_roles
WHERE rolname = :'runtime_role';
SQL
CONTAINER
)
methods=$(docker exec "$container" sh -ec \
    'PGPASSWORD=$(cat /run/secrets/postgres-password); export PGPASSWORD; exec psql -U postgres -d "$1" -Atqc "SELECT string_agg(DISTINCT auth_method, '"'"','"'"' ORDER BY auth_method) FROM pg_hba_file_rules WHERE type='"'"'host'"'"' AND error IS NULL"' \
    _ "$database")
encryption=$(docker exec "$container" sh -ec \
    'PGPASSWORD=$(cat /run/secrets/postgres-password); export PGPASSWORD; exec psql -U postgres -d "$1" -Atqc "SHOW password_encryption"' \
    _ "$database")
unexpected_memberships=$(docker exec -i "$container" sh -s -- "$database" "$runtime_role" <<'CONTAINER'
set -eu
export PGPASSWORD="$(cat /run/secrets/postgres-password)"
exec psql -U postgres -d "$1" -v ON_ERROR_STOP=1 -v runtime_role="$2" -At <<'SQL'
SELECT count(*)
FROM pg_auth_members m
JOIN pg_roles child ON child.oid = m.member
JOIN pg_roles parent ON parent.oid = m.roleid
WHERE child.rolname = :'runtime_role'
  AND parent.rolname <> 'inv_kernel';
SQL
CONTAINER
)
[[ "$admin" == postgres && "$runtime" == "$runtime_role" ]] || {
    echo 'Pilot database credentials are not role-bound.' >&2
    exit 1
}
[[ "$runtime_privileges" == 'f|f|f|f|f' ]] || {
    echo 'Pilot runtime role has elevated privileges.' >&2
    exit 1
}
[[ "$unexpected_memberships" == 0 ]] || {
    echo 'Pilot runtime role has an unexpected inherited membership.' >&2
    exit 1
}
[[ "$methods" == scram-sha-256 && "$encryption" == scram-sha-256 ]] || {
    echo 'Pilot database authentication is not exclusively SCRAM.' >&2
    exit 1
}

printf '{"databaseName":"%s","runtimeRole":"%s","missingCredentialRejected":true,"wrongCredentialRejected":true,"adminCredentialAccepted":true,"runtimeCredentialAccepted":true,"hostAuthentication":"scram-sha-256","networkDedicated":true,"networkInternal":false,"networkCount":1,"publishAddress":"loopback"}\n' \
    "$database" "$runtime_role"
