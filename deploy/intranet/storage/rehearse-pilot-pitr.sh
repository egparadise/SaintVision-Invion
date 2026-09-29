#!/bin/sh
set -eu

POSTGRES_IMAGE='postgres@sha256:1a6ab3f5345eb6dbe04a1349529caabdb0ab09293a09590fad07b2246bfa4b54'
MINIO_IMAGE='docker.io/coollabsio/minio@sha256:72b4794d7faa001823364f8ee239717141327fc450a3264414f573a6abf3c629'
CONFIG_DIR="${SV_STORAGE_CONFIG_DIR:-$HOME/.config/saintvision-intranet}"
WORK_ROOT="${SV_PITR_WORK_ROOT:-$HOME/.local/share/saintvision-intranet/pitr}"
SOURCE_ENV="${SV_PITR_SOURCE_ENV:-$CONFIG_DIR/pilot-postgres.env}"
PITR_ENV="$CONFIG_DIR/pitr-service-user.env"
RETENTION_TOOL="${SV_PITR_RETENTION_TOOL:-$CONFIG_DIR/pitr_archive_retention.py}"
SOURCE_HOST="${SV_PITR_SOURCE_HOST:-127.0.0.1}"
SOURCE_PORT="${SV_PITR_SOURCE_PORT:-55440}"
MINIO_ENDPOINT="${SV_PITR_MINIO_ENDPOINT:-http://127.0.0.1:9000}"
RUN_ID="${SV_PITR_RUN_ID:-$(date -u +%Y%m%dT%H%M%SZ)}"
CODE_SHA="${SV_CODE_SHA:-UNMEASURED}"

case "$RUN_ID" in
  *[!A-Za-z0-9_-]*|'') printf 'invalid run id\n' >&2; exit 2 ;;
esac
RUN_DIR="$WORK_ROOT/$RUN_ID"
BACKUPS="$RUN_DIR/backups"
BASE="$BACKUPS/base-$RUN_ID"
ARCHIVE="$RUN_DIR/wal"
DOWNLOAD="$RUN_DIR/download"
RESTORE="$RUN_DIR/restore"
REPORT="$RUN_DIR/pitr-report.json"
DB="card151_pitr_$(printf '%s' "$RUN_ID" | tr '[:upper:]' '[:lower:]' | tr -cd 'a-z0-9_' | cut -c1-40)"
RECEIVER="saintvision-pitr-receive-$RUN_ID"
RESTORE_CONTAINER="saintvision-pitr-restore-$RUN_ID"
UPLOAD="saintvision-pitr-transfer-$RUN_ID"
DB_CREATED=false

fail() {
  printf '%s\n' "$1" >&2
  exit 2
}

case "$CODE_SHA" in *[!0-9a-f]*|'') fail 'SV_CODE_SHA must be a lowercase 40-hex commit' ;; esac
[ "${#CODE_SHA}" -eq 40 ] || fail 'SV_CODE_SHA must be a lowercase 40-hex commit'

write_blocked_report() {
  reason="$1"
  python3 - "$REPORT" "$RUN_ID" "$CODE_SHA" "$reason" <<'PY'
from datetime import datetime, timezone
import json
from pathlib import Path
import sys

path, run_id, code_sha, reason = sys.argv[1:]
payload = {
    "schemaVersion": "intranet-pitr-rehearsal:1",
    "status": "BLOCKED_EXTERNAL",
    "runId": run_id,
    "codeSha": code_sha,
    "observedAt": datetime.now(timezone.utc).isoformat().replace("+00:00", "Z"),
    "reason": reason,
    "sourceMutated": False,
    "restoreAttempted": False,
    "measuredRtoSeconds": None,
    "measuredRpoSeconds": None,
}
Path(path).write_text(json.dumps(payload, sort_keys=True, separators=(",", ":")) + "\n", encoding="utf-8")
print(json.dumps({"status": payload["status"], "reason": reason}, sort_keys=True))
PY
}

for file in "$SOURCE_ENV" "$PITR_ENV" "$RETENTION_TOOL"; do
  [ -f "$file" ] && [ ! -L "$file" ] || fail 'required protected input is absent'
done
case "$MINIO_ENDPOINT" in
  http://*) MINIO_SCHEME=http ;;
  https://*) MINIO_SCHEME=https ;;
  *) fail 'MinIO endpoint must be HTTP(S)' ;;
esac
MINIO_AUTHORITY=${MINIO_ENDPOINT#*://}
case "$MINIO_AUTHORITY" in
  *[!A-Za-z0-9.:-]*|*'/'*|*'?'*|*'#'*|'') fail 'MinIO endpoint must be a root URL' ;;
esac
CA_CHAIN="$CONFIG_DIR/minio-certs/ca-chain.pem"
if [ "$MINIO_SCHEME" = https ]; then
  [ -f "$CA_CHAIN" ] && [ ! -L "$CA_CHAIN" ] || fail 'trusted MinIO CA chain is absent'
fi
mkdir -p "$BACKUPS" "$ARCHIVE"
chmod 700 "$WORK_ROOT" "$RUN_DIR" "$BACKUPS" "$ARCHIVE"

remove_owned() {
  name="$1"
  if docker inspect "$name" >/dev/null 2>&1; then
    owner="$(docker inspect --format '{{ index .Config.Labels "ai.saintvision.owner" }}' "$name")"
    run="$(docker inspect --format '{{ index .Config.Labels "ai.saintvision.run" }}' "$name")"
    [ "$owner" = codex ] && [ "$run" = "$RUN_ID" ] || fail 'refusing to remove an unowned container'
    docker rm -f "$name" >/dev/null
  fi
}

mc_container() {
  if [ "$MINIO_SCHEME" = https ]; then
    docker run --rm \
      --name "$UPLOAD" \
      --label ai.saintvision.owner=codex \
      --label ai.saintvision.task=intranet-storage-card151 \
      --label "ai.saintvision.run=$RUN_ID" \
      --user "$(id -u):$(id -g)" \
      --read-only \
      --tmpfs /tmp:rw,noexec,nosuid,nodev,size=67108864 \
      --security-opt no-new-privileges \
      --cap-drop ALL \
      --network host \
      -e "SV_MINIO_SCHEME=$MINIO_SCHEME" \
      -e "SV_MINIO_AUTHORITY=$MINIO_AUTHORITY" \
      -e SSL_CERT_FILE=/ca/ca-chain.pem \
      -v "$PITR_ENV:/run/secrets/pitr.env:ro" \
      -v "$CA_CHAIN:/ca/ca-chain.pem:ro" \
      "$@"
  else
    docker run --rm \
      --name "$UPLOAD" \
      --label ai.saintvision.owner=codex \
      --label ai.saintvision.task=intranet-storage-card151 \
      --label "ai.saintvision.run=$RUN_ID" \
      --user "$(id -u):$(id -g)" \
      --read-only \
      --tmpfs /tmp:rw,noexec,nosuid,nodev,size=67108864 \
      --security-opt no-new-privileges \
      --cap-drop ALL \
      --network host \
      -e "SV_MINIO_SCHEME=$MINIO_SCHEME" \
      -e "SV_MINIO_AUTHORITY=$MINIO_AUTHORITY" \
      -v "$PITR_ENV:/run/secrets/pitr.env:ro" \
      "$@"
  fi
}

MC_WRAPPER='
  . /run/secrets/pitr.env
  case "$PITR_KEY$PITR_SECRET" in
    *[!A-Za-z0-9._-]*) printf "%s\n" "PITR credential alphabet is invalid" >&2; exit 2 ;;
  esac
  export MC_HOST_pitr="$SV_MINIO_SCHEME://${PITR_KEY}:${PITR_SECRET}@${SV_MINIO_AUTHORITY}"
  exec "$@"
'

source_psql() {
  database="$1"
  shift
  docker run --rm --network host -v "$SOURCE_ENV:/run/secrets/source.env:ro" "$POSTGRES_IMAGE" \
    /bin/sh -ceu '. /run/secrets/source.env; export PGPASSWORD="$POSTGRES_PASSWORD"; host=$1; port=$2; database=$3; shift 3; exec psql -v ON_ERROR_STOP=1 -h "$host" -p "$port" -U "$POSTGRES_USER" -d "$database" "$@"' \
    shell "$SOURCE_HOST" "$SOURCE_PORT" "$database" "$@"
}

cleanup() {
  status=$?
  set +e
  remove_owned "$RECEIVER"
  remove_owned "$RESTORE_CONTAINER"
  remove_owned "$UPLOAD"
  if [ "$DB_CREATED" = true ]; then
    source_psql postgres -c "DROP DATABASE IF EXISTS $DB WITH (FORCE)" >/dev/null 2>&1
  fi
  exit "$status"
}
trap cleanup EXIT HUP INT TERM

remove_owned "$RECEIVER"
remove_owned "$RESTORE_CONTAINER"
remove_owned "$UPLOAD"

docker run -d \
  --name "$RECEIVER" \
  --label ai.saintvision.owner=codex \
  --label ai.saintvision.task=intranet-storage-card151 \
  --label "ai.saintvision.run=$RUN_ID" \
  --user "$(id -u):$(id -g)" \
  --network host \
  -v "$SOURCE_ENV:/run/secrets/source.env:ro" \
  -v "$RUN_DIR:/work" \
  "$POSTGRES_IMAGE" \
  /bin/sh -ceu '. /run/secrets/source.env; export PGPASSWORD="$POSTGRES_PASSWORD"; exec pg_receivewal --synchronous --verbose -D /work/wal -h "$1" -p "$2" -U "$POSTGRES_USER"' shell "$SOURCE_HOST" "$SOURCE_PORT" >/dev/null
sleep 2
if [ "$(docker inspect --format '{{.State.Running}}' "$RECEIVER")" != true ]; then
  receiver_log="$(docker logs "$RECEIVER" 2>&1 || true)"
  reason=physical-replication-unavailable
  printf '%s' "$receiver_log" | grep -q 'no pg_hba.conf entry for replication' && reason=physical-replication-hba-rejected
  write_blocked_report "$reason"
  fail 'WAL receiver did not start'
fi
attempt=0
while [ "$(source_psql postgres -At -c "SELECT count(*) FROM pg_stat_replication WHERE application_name='pg_receivewal' AND state='streaming'")" -lt 1 ]; do
  attempt=$((attempt + 1))
  [ "$attempt" -lt 15 ] || fail 'WAL receiver is running but not streaming'
  sleep 1
done

# Do not mutate the source until the physical replication boundary is proven.
SOURCE_ARCHIVE_MODE="$(source_psql postgres -At -c 'SHOW archive_mode')"
SOURCE_SERVER_VERSION_NUM="$(source_psql postgres -At -c 'SHOW server_version_num')"
SOURCE_DB_USER="$(source_psql postgres -At -c 'SELECT current_user')"
IMAGE_MAJOR="$(docker run --rm "$POSTGRES_IMAGE" postgres --version | sed -n 's/.* \([0-9][0-9]*\).*/\1/p')"
[ "$((SOURCE_SERVER_VERSION_NUM / 10000))" = "$IMAGE_MAJOR" ] || fail 'source and restore PostgreSQL major versions differ'
source_psql postgres -c "CREATE DATABASE $DB" >/dev/null
DB_CREATED=true
source_psql "$DB" -c 'CREATE TABLE public.card151_pitr_marker(label text PRIMARY KEY, committed_at timestamptz NOT NULL DEFAULT clock_timestamp())' >/dev/null

docker run --rm \
  --user "$(id -u):$(id -g)" \
  --network host \
  -v "$SOURCE_ENV:/run/secrets/source.env:ro" \
  -v "$RUN_DIR:/work" \
  "$POSTGRES_IMAGE" \
  /bin/sh -ceu '. /run/secrets/source.env; export PGPASSWORD="$POSTGRES_PASSWORD"; exec pg_basebackup -h "$1" -p "$2" -U "$POSTGRES_USER" -D /work/backups/base-'"$RUN_ID"' -Fp -X stream -c fast -l card151-'"$RUN_ID"'' shell "$SOURCE_HOST" "$SOURCE_PORT"

BEFORE_TIME="$(source_psql "$DB" -At -c "INSERT INTO public.card151_pitr_marker(label) VALUES ('before') RETURNING committed_at AT TIME ZONE 'UTC'")"
TARGET_TIME="$(source_psql "$DB" -At -c "SELECT clock_timestamp() AT TIME ZONE 'UTC'")"
sleep 1
AFTER_TIME="$(source_psql "$DB" -At -c "INSERT INTO public.card151_pitr_marker(label) VALUES ('after') RETURNING committed_at AT TIME ZONE 'UTC'")"
before_segments="$(find "$ARCHIVE" -maxdepth 1 -type f -name '????????????????????????' | wc -l)"
source_psql postgres -At -c 'SELECT pg_switch_wal()' >/dev/null
attempt=0
while :; do
  complete_segments="$(find "$ARCHIVE" -maxdepth 1 -type f -name '????????????????????????' | wc -l)"
  [ "$complete_segments" -gt "$before_segments" ] && break
  attempt=$((attempt + 1))
  [ "$attempt" -lt 30 ] || fail 'switched WAL segment was not durably received'
  sleep 1
done
remove_owned "$RECEIVER"

RETENTION_TOOL_SHA256="$(sha256sum "$RETENTION_TOOL" | awk '{print $1}')"
python3 "$RETENTION_TOOL" --archive "$ARCHIVE" --backups "$BACKUPS" --days 7 > "$RUN_DIR/retention-plan.json"

# The transient transfer container mounts only the scoped credential file, the
# data mount, and (for HTTPS) the public CA chain. The secret never appears in
# the host process arguments or Docker Config.Env, and the broader config tree
# is never mounted.
mc_container \
  -v "$RUN_DIR:/evidence:ro" \
  "$MINIO_IMAGE" /bin/sh -ceu "$MC_WRAPPER" shell /usr/bin/mc mirror --overwrite /evidence \
  "pitr/saintvision-pitr/pilot/rehearsals/$RUN_ID" >/dev/null

restore_started_ns="$(date +%s%N)"
mkdir -p "$DOWNLOAD"
chmod 700 "$DOWNLOAD"
mc_container \
  -v "$DOWNLOAD:/download" \
  "$MINIO_IMAGE" /bin/sh -ceu "$MC_WRAPPER" shell /usr/bin/mc mirror \
  "pitr/saintvision-pitr/pilot/rehearsals/$RUN_ID" /download >/dev/null

(cd "$RUN_DIR" && find backups wal -type f -print0 | sort -z | xargs -0 sha256sum) > "$RUN_DIR/source-sha256.txt"
(cd "$DOWNLOAD" && find backups wal -type f -print0 | sort -z | xargs -0 sha256sum) > "$RUN_DIR/download-sha256.txt"
cmp "$RUN_DIR/source-sha256.txt" "$RUN_DIR/download-sha256.txt" >/dev/null || fail 'downloaded backup or WAL differs from uploaded bytes'

cp -a "$DOWNLOAD/backups/base-$RUN_ID" "$RESTORE"
cat >> "$RESTORE/postgresql.auto.conf" <<EOF
restore_command = 'cp /wal/%f %p'
recovery_target_time = '$TARGET_TIME UTC'
recovery_target_action = 'promote'
EOF
: > "$RESTORE/recovery.signal"

docker run -d \
  --name "$RESTORE_CONTAINER" \
  --label ai.saintvision.owner=codex \
  --label ai.saintvision.task=intranet-storage-card151 \
  --label "ai.saintvision.run=$RUN_ID" \
  --user "$(id -u):$(id -g)" \
  --read-only \
  --tmpfs /tmp:rw,noexec,nosuid,nodev,size=67108864 \
  --security-opt no-new-privileges \
  --cap-drop ALL \
  --network none \
  -v "$RESTORE:/var/lib/postgresql/data" \
  -v "$DOWNLOAD/wal:/wal:ro" \
  --entrypoint postgres \
  "$POSTGRES_IMAGE" -D /var/lib/postgresql/data -k /tmp >/dev/null
attempt=0
until [ "$(docker exec "$RESTORE_CONTAINER" psql -h /tmp -U "$SOURCE_DB_USER" -d "$DB" -At -c 'SELECT NOT pg_is_in_recovery()' 2>/dev/null || true)" = t ]; do
  attempt=$((attempt + 1))
  if [ "$attempt" -ge 90 ]; then
    docker logs --tail 30 "$RESTORE_CONTAINER" >&2
    fail 'restored PostgreSQL did not become ready'
  fi
  sleep 1
done
restore_ready_ns="$(date +%s%N)"
RESTORED="$(docker exec "$RESTORE_CONTAINER" psql -h /tmp -v ON_ERROR_STOP=1 -U "$SOURCE_DB_USER" -d "$DB" -At -c "SELECT string_agg(label, ',' ORDER BY label) FROM public.card151_pitr_marker")"
PROMOTED="$(docker exec "$RESTORE_CONTAINER" psql -h /tmp -v ON_ERROR_STOP=1 -U "$SOURCE_DB_USER" -d "$DB" -At -c 'SELECT NOT pg_is_in_recovery()')"
[ "$RESTORED" = before ] || fail 'target-time restore did not preserve/exclude the expected markers'
[ "$PROMOTED" = t ] || fail 'target-time restore did not promote'

python3 - "$REPORT" "$RUN_ID" "$CODE_SHA" "$BEFORE_TIME" "$TARGET_TIME" "$AFTER_TIME" "$restore_started_ns" "$restore_ready_ns" "$complete_segments" "$SOURCE_ARCHIVE_MODE" "$SOURCE_SERVER_VERSION_NUM" "$RETENTION_TOOL_SHA256" <<'PY'
from datetime import datetime, timezone
import json
from pathlib import Path
import sys

def stamp(value):
    parsed = datetime.fromisoformat(value.replace(" ", "T"))
    return parsed.replace(tzinfo=timezone.utc) if parsed.tzinfo is None else parsed.astimezone(timezone.utc)

path, run_id, code_sha, before, target, after, started, ready, segments, archive_mode, server_version_num, retention_sha = sys.argv[1:]
before_at, target_at, after_at = map(stamp, (before, target, after))
payload = {
    "schemaVersion": "intranet-pitr-rehearsal:1",
    "status": "PASS",
    "runId": run_id,
    "codeSha": code_sha,
    "observedAt": datetime.now(timezone.utc).isoformat().replace("+00:00", "Z"),
    "source": {"kind": "lan-pilot", "archiveModeObserved": archive_mode, "serverVersionNum": int(server_version_num)},
    "storage": {"provider": "s3-compatible-v1", "bucketScope": "pilot/rehearsals", "uploadDownloadDigestMatched": True},
    "physicalBackup": {"pgBasebackup": True, "continuousWalReceiver": True, "completedWalSegmentCount": int(segments)},
    "restore": {"recoveryTargetTime": target_at.isoformat().replace("+00:00", "Z"), "beforeMarkerPresent": True, "afterMarkerAbsent": True, "promoted": True},
    "measuredRtoSeconds": round((int(ready) - int(started)) / 1_000_000_000, 3),
    "measuredRpoSeconds": None,
    "targetGapSeconds": round((target_at - before_at).total_seconds(), 6),
    "excludedAfterTargetSeconds": round((after_at - target_at).total_seconds(), 6),
    "retentionPlanner": {"protectedCopySha256": retention_sha, "days": 7, "apply": False},
    "limitations": [
        "source archive_mode remains off; this rehearsal used a bounded pg_receivewal sidecar",
        "continuous post-rehearsal WAL delivery is not configured",
        "RPO is not measured by this bounded target-time rehearsal",
        "the source physical-replication HBA is an operator-managed prerequisite"
    ],
}
Path(path).write_text(json.dumps(payload, sort_keys=True, separators=(",", ":")) + "\n", encoding="utf-8")
print(json.dumps({k: payload[k] for k in ("status", "measuredRtoSeconds", "measuredRpoSeconds", "excludedAfterTargetSeconds")}, sort_keys=True))
PY

mc_container \
  -v "$REPORT:/pitr-report.json:ro" \
  "$MINIO_IMAGE" /bin/sh -ceu "$MC_WRAPPER" shell /usr/bin/mc cp /pitr-report.json \
  "pitr/saintvision-pitr/pilot/rehearsals/$RUN_ID/pitr-report.json" >/dev/null

remove_owned "$RESTORE_CONTAINER"
source_psql postgres -c "DROP DATABASE $DB WITH (FORCE)" >/dev/null
DB_CREATED=false
trap - EXIT HUP INT TERM
printf 'pitrRehearsal=PASS report=%s\n' "$REPORT"
