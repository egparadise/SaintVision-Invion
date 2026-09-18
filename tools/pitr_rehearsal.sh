#!/usr/bin/env bash
# PITR isolated rehearsal: prove point-in-time recovery works and the recovery point
# is bounded, on a probe postgres with the proposed archiving config. Single container.
set -u
NAME=pitr-probe-$$
PW=$(head -c8 /dev/urandom | od -An -tx1 | tr -d ' \n')
ARCH=/var/lib/postgresql/archive
FAIL=0

cleanup() { docker rm -f "$NAME" >/dev/null 2>&1; }
trap cleanup EXIT

dk() { for a in 1 2 3 4 5; do docker "$@" && return 0; echo "  (docker $1 retry $a: daemon busy)"; sleep 5; done; return 1; }

echo "== start probe with proposed archiving config (low shared_buffers for memory pressure) =="
dk run -d --name "$NAME" -e POSTGRES_PASSWORD="$PW" postgres:16-alpine \
  -c archive_mode=on \
  -c 'archive_command=if [ -f /var/lib/postgresql/archive/%f ]; then cmp -s %p /var/lib/postgresql/archive/%f; else cp %p /var/lib/postgresql/archive/%f.tmp && mv /var/lib/postgresql/archive/%f.tmp /var/lib/postgresql/archive/%f; fi' \
  -c archive_timeout=300 \
  -c wal_level=replica -c shared_buffers=32MB -c max_wal_size=256MB >/dev/null || { echo "docker run failed"; exit 3; }

# archive dir must exist and be writable by postgres
dk exec -u root "$NAME" sh -c "mkdir -p $ARCH && chown postgres:postgres $ARCH" || { echo "mkdir archive failed"; exit 3; }

echo "== wait for readiness =="
for i in $(seq 1 60); do
  docker exec -u postgres "$NAME" pg_isready -q && break
  sleep 1
done
docker exec -u postgres "$NAME" pg_isready || { echo "probe never ready"; exit 3; }

echo "== (a) real server settings (SHOW) =="
docker exec -u postgres "$NAME" psql -tA -c \
  "SELECT name||'='||setting FROM pg_settings WHERE name IN ('archive_mode','archive_timeout','wal_level')"

echo "== (b) PITR round-trip =="
docker exec -i -u postgres "$NAME" sh -s <<'SCRIPT' 2>&1
export PGDATA=/var/lib/postgresql/data
ARCH=/var/lib/postgresql/archive
echo "local replication all trust" >> "$PGDATA/pg_hba.conf"
psql -q -c "SELECT pg_reload_conf()" >/dev/null
psql -q -c "CREATE TABLE t(v text)"
echo "step: base backup"
pg_basebackup -D /var/lib/postgresql/base -Fp -Xstream 2>/tmp/bb.err; echo "  basebackup rc=$? ; $(tail -1 /tmp/bb.err)"
psql -q -c "INSERT INTO t VALUES('before')"
T1=$(psql -tAc "SELECT now()")
echo "step: T1=$T1 (after 'before', before 'after')"
psql -q -c "CHECKPOINT; SELECT pg_switch_wal()" >/dev/null
sleep 4
psql -q -c "INSERT INTO t VALUES('after')"
psql -q -c "SELECT pg_switch_wal()" >/dev/null
sleep 4
echo "step: archived WAL files: $(ls $ARCH | wc -l)"
echo "step: prepare restore cluster"
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
echo "step: start restore instance on 5433"
pg_ctl -D /var/lib/postgresql/restore -w -t 90 -l /tmp/restore.log start; echo "  pg_ctl rc=$?"
for i in $(seq 1 60); do
  st=$(psql -p 5433 -tAc "SELECT pg_is_in_recovery()" 2>/dev/null || echo "?")
  [ "$st" = "f" ] && break
  sleep 1
done
echo "step: in_recovery=$st"
echo "restore.log tail:"; tail -5 /tmp/restore.log
echo "targetTime=$T1"
echo "restoredRows=[$(psql -p 5433 -tAc "SELECT string_agg(v,',' ORDER BY v) FROM t" 2>&1)]"
SCRIPT

echo "== verdict =="
ROWS=$(docker exec -u postgres "$NAME" psql -p 5433 -tAc "SELECT string_agg(v,',' ORDER BY v) FROM t" 2>/dev/null)
echo "restored table content = [$ROWS]"
if [ "$ROWS" = "before" ]; then
  echo "PASS: recovered to target time -> 'before' present, 'after' correctly excluded (PITR works, recovery point bounded)"
else
  echo "INCONCLUSIVE/FAIL: expected [before], got [$ROWS]"; FAIL=1
fi
exit $FAIL
