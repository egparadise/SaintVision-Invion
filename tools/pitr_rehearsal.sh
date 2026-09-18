#!/usr/bin/env bash
# Physical PITR rehearsal with a STRICT pass gate and OWNED, retry-safe docker use.
#
# Proves point-in-time recovery works AND that the exclusion test is meaningful: a
# physical base backup, record A (before target T1), record B (after T1, CONFIRMED to
# exist in the source), then a restore of archived WAL to T1 in a separate isolated
# cluster (same host -- not a separate failure domain) that must PROMOTE and hold A only.
#
# Pass gate (PITR-R2-01): every step's exit code is checked; psql ON_ERROR_STOP; A and
# B confirmed in the SOURCE (else the exclusion test is vacuous -> FAIL); promotion
# (target reached) enforced before the restore content is judged. Each failure has a
# distinct exit code (11-14) so the broken step is visible.
#
# Docker safety (PITR-R2-02): the container carries a unique owner label; cleanup removes
# ONLY containers with that label (never a blind rm on a shared name); a container-create
# failure is retried at most for a transient daemon timeout, and only after removing any
# partial WE own (never duplicating or touching another run's container); a non-transient
# failure is reported, not blindly retried; cleanup failures are reported.
#
# Negative regression: FAULT injects a broken prerequisite and the gate must FAIL:
#   before-insert | after-insert | basebackup | restore-start | promotion
set -euo pipefail

NAME="pitr-probe-$$"
LABEL="ai.saintvision.pitr-rehearsal=$NAME"    # unique owner label for this run
PW="$(head -c8 /dev/urandom | od -An -tx1 | tr -d ' \n')"
ARCH=/var/lib/postgresql/archive
FAULT="${FAULT:-}"
ACMD='if [ -f /var/lib/postgresql/archive/%f ]; then cmp -s %p /var/lib/postgresql/archive/%f; else cp %p /var/lib/postgresql/archive/%f.$$.tmp && mv /var/lib/postgresql/archive/%f.$$.tmp /var/lib/postgresql/archive/%f; fi'

fail() { echo "FAIL: $1"; exit 1; }

# Remove ONLY containers this run owns (by unique label). Never a blind rm on the name,
# so a name collision with another run's container cannot delete it. Reports failure.
cleanup() {
  local ids
  ids="$(docker ps -aq --filter "label=$LABEL" 2>/dev/null || true)"
  if [ -n "$ids" ]; then
    docker rm -f $ids >/dev/null 2>&1 || echo "WARN: cleanup could not remove owned container(s) [$ids]"
  fi
}
trap cleanup EXIT

# Retry a container create ONLY for a transient daemon timeout, and only after removing
# any partial WE own -- so a retry never duplicates or orphans a container. A
# non-transient failure (e.g. name already in use by another owner) is reported, not
# retried; unclassified failures are NOT relabelled "daemon busy".
transient() { case "$1" in *"i/o timeout"*|*"deadline exceeded"*|*"timeout exceeded"*|*"Cannot connect to the Docker daemon"*) return 0;; *) return 1;; esac; }

start_probe() {
  local attempt out
  for attempt in 1 2 3; do
    if out="$(docker run -d --name "$NAME" --label "$LABEL" -e POSTGRES_PASSWORD="$PW" postgres:16-alpine \
        -c archive_mode=on -c "archive_command=$ACMD" -c archive_timeout=300 \
        -c wal_level=replica -c shared_buffers=32MB -c max_wal_size=256MB 2>&1)"; then
      return 0
    fi
    echo "  docker run attempt $attempt failed: $out"
    cleanup                                  # remove any partial WE own before retrying
    transient "$out" || return 1             # only retry a transient daemon timeout
    sleep 5
  done
  return 1
}

echo "== start probe with proposed archiving config (FAULT='${FAULT}') =="
start_probe || fail "probe container did not start (see error above)"

# mkdir is idempotent -> safe to retry a transient timeout
for attempt in 1 2 3; do
  docker exec -u root "$NAME" sh -c "mkdir -p $ARCH && chown postgres:postgres $ARCH" && break
  [ "$attempt" = 3 ] && fail "archive dir setup"; sleep 4
done

echo "== wait for readiness =="
ready=no
for i in $(seq 1 60); do
  if docker exec -u postgres "$NAME" pg_isready -q; then ready=yes; break; fi
  sleep 1
done
[ "$ready" = yes ] || fail "probe never became ready"

echo "== (a) real server settings =="
docker exec -u postgres "$NAME" psql -v ON_ERROR_STOP=1 -tA -c \
  "SELECT name||'='||setting FROM pg_settings WHERE name IN ('archive_mode','archive_timeout','wal_level')" \
  || fail "could not read server settings"

echo "== (b) PITR round-trip (strict) =="
# The round-trip is a MUTATING sequence -> run exactly once, never retried.
docker exec -i -u postgres -e FAULT="$FAULT" "$NAME" sh -s <<'SCRIPT' || fail "round-trip step failed (a prerequisite or restore step returned non-zero -- see markers above)"
set -eu
export PGDATA=/var/lib/postgresql/data
ARCH=/var/lib/postgresql/archive
P="psql -v ON_ERROR_STOP=1 -qtA"
F="${FAULT:-}"

echo "local replication all trust" >> "$PGDATA/pg_hba.conf"
$P -c "SELECT pg_reload_conf()" >/dev/null
$P -c "CREATE TABLE t(v text)"

echo "step: physical base backup"
if [ "$F" = "basebackup" ]; then
  echo "INJECT: base backup to an unwritable path (simulate basebackup failure)"
  pg_basebackup -D /proc/nonexistent/base -Fp -Xstream
else
  pg_basebackup -D /var/lib/postgresql/base -Fp -Xstream
fi

if [ "$F" = "before-insert" ]; then echo "INJECT: skipping 'before' INSERT"; else $P -c "INSERT INTO t VALUES('before')"; fi
[ "$($P -c "SELECT count(*) FROM t WHERE v='before'")" = "1" ] || { echo "ASSERT-FAIL: 'before' not committed in source"; exit 11; }
T1=$($P -c "SELECT now()")
echo "step: T1=$T1"
$P -c "CHECKPOINT" >/dev/null
$P -c "SELECT pg_switch_wal()" >/dev/null
sleep 3

if [ "$F" = "after-insert" ]; then echo "INJECT: skipping 'after' INSERT"; else $P -c "INSERT INTO t VALUES('after')"; fi
AFTER_SRC=$($P -c "SELECT count(*) FROM t WHERE v='after'")
[ "$AFTER_SRC" = "1" ] || { echo "ASSERT-FAIL: 'after' is not present in the SOURCE -> an exclusion result would be vacuous"; exit 12; }
$P -c "SELECT pg_switch_wal()" >/dev/null
sleep 3

echo "step: prepare + start restore cluster on 5433"
cp -a /var/lib/postgresql/base /var/lib/postgresql/restore
rm -f /var/lib/postgresql/restore/postmaster.pid
touch /var/lib/postgresql/restore/recovery.signal
RTA=promote
if [ "$F" = "promotion" ]; then echo "INJECT: recovery_target_action=pause (never promotes)"; RTA=pause; fi
cat >> /var/lib/postgresql/restore/postgresql.auto.conf <<CONF
restore_command = 'cp $ARCH/%f %p'
recovery_target_time = '$T1'
recovery_target_action = '$RTA'
port = 5433
shared_buffers = 32MB
CONF
chmod 700 /var/lib/postgresql/restore
if [ "$F" = "restore-start" ]; then
  echo "INJECT: invalid port -> pg_ctl start fails"
  echo "port = 999999" >> /var/lib/postgresql/restore/postgresql.auto.conf
fi
pg_ctl -D /var/lib/postgresql/restore -w -t 60 -l /tmp/restore.log start

promoted=no
for i in $(seq 1 45); do
  st=$($P -p 5433 -c "SELECT pg_is_in_recovery()" 2>/dev/null || echo "?")
  if [ "$st" = "f" ]; then promoted=yes; break; fi
  sleep 1
done
[ "$promoted" = yes ] || { echo "ASSERT-FAIL: restore did not promote / target time not reached (state=$st)"; tail -5 /tmp/restore.log; exit 13; }

ROWS=$($P -p 5433 -c "SELECT string_agg(v,',' ORDER BY v) FROM t")
echo "result: sourceHadAfter=$AFTER_SRC targetTime=$T1 restoredRows=[$ROWS]"
[ "$ROWS" = "before" ] || { echo "ASSERT-FAIL: expected restored rows [before], got [$ROWS]"; exit 14; }
echo "INNER-PASS: source held before+after; restore promoted to T1; restore has before only (after excluded)"
SCRIPT

echo "PASS: physical PITR verified -- prerequisites (base backup, before+after in source, promotion) all held, and the restore recovered to T1 with 'before' present and 'after' excluded"
