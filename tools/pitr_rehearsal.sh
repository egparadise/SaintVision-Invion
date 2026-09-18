#!/usr/bin/env bash
# Physical PITR rehearsal with a STRICT pass gate and OWNED, retry-safe docker use.
#
# Point-in-time recovery is proven AND the exclusion test is kept meaningful: a physical
# base backup, record A (before target T1), record B (after T1, CONFIRMED present in the
# source), then a restore of archived WAL to T1 in a separate isolated cluster (same host
# -- not a separate failure domain) that must PROMOTE and hold A only.
#
# Pass gate (PITR-R2-01): every step's exit is checked; psql ON_ERROR_STOP; A and B
# confirmed in the SOURCE (else exclusion is vacuous -> FAIL); promotion enforced before
# judging the restore. FAULT injects a broken prerequisite and the gate must FAIL:
#   before-insert | after-insert | basebackup | restore-start | promotion
#
# Docker safety (PITR-R2-02): the container is owned by a RANDOM run nonce (not a PID,
# which can be reused). cleanup_owned distinguishes a QUERY failure from a REMOVE failure
# from a CONFIRMED absence, and confirms removal by re-query; a container-create is only
# retried after cleanup CONFIRMS removal (never on an unconfirmed cleanup -> no duplicate)
# and only for a transient daemon timeout. The teardown result is reported alongside, not
# in place of, the body result. Set SOURCE_ONLY=1 to source the functions for testing;
# set DOCKER to a fake CLI to exercise the failure branches.
set -euo pipefail

DOCKER="${DOCKER:-docker}"

# ---- ownership / retry library (testable via SOURCE_ONLY + a fake $DOCKER) ----

transient() { case "$1" in *"i/o timeout"*|*"deadline exceeded"*|*"timeout exceeded"*|*"Cannot connect to the Docker daemon"*) return 0;; *) return 1;; esac; }

# Echo exactly one of: clean | query-error | rm-error
#   clean       = query succeeded and, after removing any owned container, a re-query
#                 confirms none remain (also the confirmed-absence case)
#   query-error = `docker ps` itself failed -> ownership is UNKNOWN, not "absent"
#   rm-error    = a remove failed, or a post-remove re-query still shows the container
# Only containers matching this run's unique label are ever considered or removed, so a
# different owner's or a past run's container is never touched.
cleanup_owned() {
    local ids id failed=0 after
    if ! ids="$("$DOCKER" ps -aq --filter "label=$LABEL" 2>/dev/null)"; then
        echo "query-error"; return 0
    fi
    if [ -n "$ids" ]; then
        while IFS= read -r id; do
            [ -z "$id" ] && continue
            "$DOCKER" rm -f "$id" >/dev/null 2>&1 || failed=1
        done <<EOF
$ids
EOF
    fi
    [ "$failed" = 1 ] && { echo "rm-error"; return 0; }
    if ! after="$("$DOCKER" ps -aq --filter "label=$LABEL" 2>/dev/null)"; then
        echo "query-error"; return 0          # cannot confirm removal
    fi
    [ -n "$after" ] && { echo "rm-error"; return 0; }
    echo "clean"; return 0
}

# Create the probe. Retry ONLY a transient daemon timeout, and ONLY after cleanup has
# CONFIRMED that any partial we own is gone -- an unconfirmed cleanup (query-error /
# rm-error) must not be followed by another mutating create (would duplicate).
start_probe() {
    local attempt out status
    for attempt in 1 2 3; do
        if out="$("$DOCKER" run -d --name "$NAME" --label "$LABEL" -e POSTGRES_PASSWORD="$PW" postgres:16-alpine \
                -c archive_mode=on -c "archive_command=$ACMD" -c archive_timeout=300 \
                -c wal_level=replica -c shared_buffers=32MB -c max_wal_size=256MB 2>&1)"; then
            return 0
        fi
        echo "  create attempt $attempt failed: $out"
        status="$(cleanup_owned)"
        if [ "$status" != clean ]; then
            echo "  cleanup did not CONFIRM removal ($status); NOT retrying a mutating create"
            return 1
        fi
        transient "$out" || { echo "  non-transient create failure; not retrying"; return 1; }
        sleep 5
    done
    return 1
}

[ "${SOURCE_ONLY:-}" = 1 ] && return 0

# ---- main ----

RUN="$(head -c16 /dev/urandom | od -An -tx1 | tr -d ' \n')"   # random run nonce (not a PID)
NAME="pitr-probe-$RUN"
LABEL="ai.saintvision.pitr-rehearsal.run=$RUN"
PW="$(head -c8 /dev/urandom | od -An -tx1 | tr -d ' \n')"
ARCH=/var/lib/postgresql/archive
FAULT="${FAULT:-}"
ACMD='if [ -f /var/lib/postgresql/archive/%f ]; then cmp -s %p /var/lib/postgresql/archive/%f; else cp %p /var/lib/postgresql/archive/%f.$$.tmp && mv /var/lib/postgresql/archive/%f.$$.tmp /var/lib/postgresql/archive/%f; fi'

fail() { echo "FAIL: $1"; exit 1; }

final_cleanup() {
    local status
    status="$(cleanup_owned)"
    [ "$status" = clean ] || echo "WARN: teardown cleanup did not confirm removal ($status) -- owned container may remain"
}
trap final_cleanup EXIT

echo "== start probe with proposed archiving config (run=$RUN FAULT='${FAULT}') =="
start_probe || fail "probe container did not start (see error above)"

for attempt in 1 2 3; do
    "$DOCKER" exec -u root "$NAME" sh -c "mkdir -p $ARCH && chown postgres:postgres $ARCH" && break
    [ "$attempt" = 3 ] && fail "archive dir setup"; sleep 4
done

echo "== wait for readiness =="
ready=no
for i in $(seq 1 60); do
    if "$DOCKER" exec -u postgres "$NAME" pg_isready -q; then ready=yes; break; fi
    sleep 1
done
[ "$ready" = yes ] || fail "probe never became ready"

echo "== (a) real server settings =="
"$DOCKER" exec -u postgres "$NAME" psql -v ON_ERROR_STOP=1 -tA -c \
    "SELECT name||'='||setting FROM pg_settings WHERE name IN ('archive_mode','archive_timeout','wal_level')" \
    || fail "could not read server settings"

echo "== (b) PITR round-trip (strict) =="
"$DOCKER" exec -i -u postgres -e FAULT="$FAULT" "$NAME" sh -s <<'SCRIPT' || fail "round-trip step failed (a prerequisite or restore step returned non-zero -- see markers above)"
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
