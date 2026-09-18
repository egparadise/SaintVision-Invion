#!/usr/bin/env bash
# Physical PITR rehearsal with a STRICT pass gate (VF/PITR-R2-01).
#
# Proves that point-in-time recovery works AND that the exclusion test is meaningful:
# a physical base backup, a record A (before the target), a target time T1, a record B
# (after T1) that is CONFIRMED to exist in the source, then a restore of archived WAL to
# T1 in a separate isolated cluster (same host -- not a separate failure domain) that
# must PROMOTE and contain A only.
#
# Every step's exit code is checked; psql uses ON_ERROR_STOP; PASS requires all
# prerequisites (base backup ok, A present in source, B present in source, promotion
# reached) -- so a failed prerequisite fails the gate instead of yielding a vacuous
# "before only". Set FAULT=after-insert to simulate a missing 'after' and confirm the
# gate FAILS (the counterexample Codex demonstrated).
set -euo pipefail

NAME=pitr-probe-$$
PW=$(head -c8 /dev/urandom | od -An -tx1 | tr -d ' \n')
ARCH=/var/lib/postgresql/archive
FAULT="${FAULT:-}"

cleanup() { docker rm -f "$NAME" >/dev/null 2>&1 || true; }
trap cleanup EXIT

fail() { echo "FAIL: $1"; exit 1; }
dk() { for a in 1 2 3 4 5; do docker "$@" && return 0; echo "  (docker $1 retry $a: daemon busy)"; sleep 5; done; return 1; }

echo "== start probe with proposed archiving config (FAULT='${FAULT}') =="
dk run -d --name "$NAME" -e POSTGRES_PASSWORD="$PW" postgres:16-alpine \
  -c archive_mode=on \
  -c 'archive_command=if [ -f /var/lib/postgresql/archive/%f ]; then cmp -s %p /var/lib/postgresql/archive/%f; else cp %p /var/lib/postgresql/archive/%f.$$.tmp && mv /var/lib/postgresql/archive/%f.$$.tmp /var/lib/postgresql/archive/%f; fi' \
  -c archive_timeout=300 \
  -c wal_level=replica -c shared_buffers=32MB -c max_wal_size=256MB >/dev/null || fail "probe container did not start"
dk exec -u root "$NAME" sh -c "mkdir -p $ARCH && chown postgres:postgres $ARCH" || fail "archive dir setup"

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
docker exec -i -u postgres -e FAULT="$FAULT" "$NAME" sh -s <<'SCRIPT' || fail "round-trip step failed (a prerequisite or restore step returned non-zero -- see markers above)"
set -eu
export PGDATA=/var/lib/postgresql/data
ARCH=/var/lib/postgresql/archive
P="psql -v ON_ERROR_STOP=1 -qtA"

echo "local replication all trust" >> "$PGDATA/pg_hba.conf"
$P -c "SELECT pg_reload_conf()" >/dev/null
$P -c "CREATE TABLE t(v text)"

echo "step: physical base backup"
pg_basebackup -D /var/lib/postgresql/base -Fp -Xstream

$P -c "INSERT INTO t VALUES('before')"
[ "$($P -c "SELECT count(*) FROM t WHERE v='before'")" = "1" ] || { echo "ASSERT-FAIL: 'before' not committed in source"; exit 11; }
T1=$($P -c "SELECT now()")
echo "step: T1=$T1"
$P -c "CHECKPOINT" >/dev/null
$P -c "SELECT pg_switch_wal()" >/dev/null
sleep 3

# fault injection point: a broken prerequisite must fail the gate, not pass it
if [ "${FAULT:-}" = "after-insert" ]; then
  echo "INJECT: skipping the 'after' INSERT to simulate a prerequisite failure"
else
  $P -c "INSERT INTO t VALUES('after')"
fi

# R2-01 core: the exclusion test is only meaningful if 'after' ACTUALLY exists in the
# source. Confirm it before trusting its absence in the restore.
AFTER_SRC=$($P -c "SELECT count(*) FROM t WHERE v='after'")
[ "$AFTER_SRC" = "1" ] || { echo "ASSERT-FAIL: 'after' is not present in the SOURCE -> an exclusion result would be vacuous"; exit 12; }
$P -c "SELECT pg_switch_wal()" >/dev/null
sleep 3

echo "step: prepare + start restore cluster on 5433"
cp -a /var/lib/postgresql/base /var/lib/postgresql/restore
rm -f /var/lib/postgresql/restore/postmaster.pid
touch /var/lib/postgresql/restore/recovery.signal
cat >> /var/lib/postgresql/restore/postgresql.auto.conf <<CONF
restore_command = 'cp $ARCH/%f %p'
recovery_target_time = '$T1'
recovery_target_action = 'promote'
port = 5433
shared_buffers = 32MB
CONF
chmod 700 /var/lib/postgresql/restore
pg_ctl -D /var/lib/postgresql/restore -w -t 90 -l /tmp/restore.log start

# enforce promotion (target reached) as its own gate
promoted=no
for i in $(seq 1 60); do
  st=$($P -p 5433 -c "SELECT pg_is_in_recovery()" 2>/dev/null || echo "?")
  if [ "$st" = "f" ]; then promoted=yes; break; fi
  sleep 1
done
[ "$promoted" = yes ] || { echo "ASSERT-FAIL: restore did not promote / target time not reached"; tail -5 /tmp/restore.log; exit 13; }

ROWS=$($P -p 5433 -c "SELECT string_agg(v,',' ORDER BY v) FROM t")
echo "result: sourceHadAfter=$AFTER_SRC targetTime=$T1 restoredRows=[$ROWS]"
[ "$ROWS" = "before" ] || { echo "ASSERT-FAIL: expected restored rows [before], got [$ROWS]"; exit 14; }
echo "INNER-PASS: source held before+after; restore promoted to T1; restore has before only (after excluded)"
SCRIPT

echo "PASS: physical PITR verified -- prerequisites (base backup, before+after in source, promotion) all held, and the restore recovered to T1 with 'before' present and 'after' excluded"
