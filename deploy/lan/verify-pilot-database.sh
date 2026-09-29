#!/usr/bin/env bash
set -euo pipefail

container=${1:?usage: verify-pilot-database.sh <container> <network>}
network=${2:?usage: verify-pilot-database.sh <container> <network>}
[[ "$container" =~ ^saintvision-[a-z0-9-]+$ && "$network" =~ ^saintvision-[a-z0-9-]+$ ]] || {
    echo 'Container or network is outside the SaintVision ownership namespace.' >&2
    exit 2
}

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
    'PGPASSFILE=/dev/null exec psql -h 127.0.0.1 -U postgres -d saintvision_lan -Atqc "SELECT 1"' \
    >/dev/null 2>&1; then
    echo 'Pilot database accepted a missing credential.' >&2
    exit 1
fi
if docker exec "$container" sh -ec \
    'PGPASSWORD=wrong; export PGPASSWORD; exec psql -h 127.0.0.1 -U postgres -d saintvision_lan -Atqc "SELECT 1"' \
    >/dev/null 2>&1; then
    echo 'Pilot database accepted an incorrect credential.' >&2
    exit 1
fi
admin=$(docker exec "$container" sh -ec \
    'PGPASSWORD=$(cat /run/secrets/postgres-password); export PGPASSWORD; exec psql -h 127.0.0.1 -U postgres -d saintvision_lan -Atqc "SELECT current_user"')
runtime=$(docker exec "$container" sh -ec \
    'PGPASSWORD=$(cat /run/secrets/runtime-password); export PGPASSWORD; exec psql -h 127.0.0.1 -U inv_lan_runtime -d saintvision_lan -Atqc "SELECT current_user"')
runtime_privileges=$(docker exec "$container" sh -ec \
    'PGPASSWORD=$(cat /run/secrets/postgres-password); export PGPASSWORD; exec psql -U postgres -d saintvision_lan -Atqc "SELECT rolsuper, rolbypassrls, rolcreatedb, rolcreaterole, rolreplication FROM pg_roles WHERE rolname = '\''inv_lan_runtime'\''"')
methods=$(docker exec "$container" sh -ec \
    'PGPASSWORD=$(cat /run/secrets/postgres-password); export PGPASSWORD; exec psql -U postgres -d saintvision_lan -Atqc "SELECT string_agg(DISTINCT auth_method, '"'"','"'"' ORDER BY auth_method) FROM pg_hba_file_rules WHERE type='"'"'host'"'"' AND error IS NULL"')
encryption=$(docker exec "$container" sh -ec \
    'PGPASSWORD=$(cat /run/secrets/postgres-password); export PGPASSWORD; exec psql -U postgres -d saintvision_lan -Atqc "SHOW password_encryption"')
unexpected_memberships=$(docker exec "$container" sh -ec \
    'PGPASSWORD=$(cat /run/secrets/postgres-password); export PGPASSWORD; exec psql -U postgres -d saintvision_lan -Atqc "SELECT count(*) FROM pg_auth_members m JOIN pg_roles child ON child.oid=m.member JOIN pg_roles parent ON parent.oid=m.roleid WHERE child.rolname='\''inv_lan_runtime'\'' AND parent.rolname<>'\''inv_kernel'\''"')
[[ "$admin" == postgres && "$runtime" == inv_lan_runtime ]] || {
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

printf '{"missingCredentialRejected":true,"wrongCredentialRejected":true,"adminCredentialAccepted":true,"runtimeCredentialAccepted":true,"hostAuthentication":"scram-sha-256","networkDedicated":true,"networkInternal":false,"networkCount":1,"publishAddress":"loopback"}\n'
