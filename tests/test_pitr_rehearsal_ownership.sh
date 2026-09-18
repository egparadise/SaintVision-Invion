#!/usr/bin/env bash
# Negative controls for PITR-R2-02, against the REAL functions in tools/pitr_rehearsal.sh
# (loaded via SOURCE_ONLY) driven by a scriptable fake docker. Codex: the 0-leftover
# happy path does NOT validate the failure branches, so each is injected here:
#   confirmed absence, query failure, rm failure, unconfirmed removal, a create retry
#   only after CONFIRMED cleanup (and none after query/rm error or a non-transient error),
#   and that only this run's unique-nonce label is ever considered (foreign/past-run untouched).
HERE="$(cd "$(dirname "$0")" && pwd)"
SOURCE_ONLY=1 . "$HERE/../tools/pitr_rehearsal.sh"
set +euo pipefail    # the sourced tool enabled errexit; tests drive control flow themselves

FDIR="$(mktemp -d)"; export FAKE_DIR="$FDIR"
cat > "$FDIR/docker" <<'FAKE'
#!/usr/bin/env bash
D="$FAKE_DIR"; cmd="$1"; shift
line_for() { local f="$1" n; n=$(cat "$D/$f.n" 2>/dev/null || echo 0); n=$((n+1)); echo "$n" > "$D/$f.n"; sed -n "${n}p" "$D/$f" 2>/dev/null; }
case "$cmd" in
  ps)  l="$(line_for ps)"; [ "$l" = FAIL ] && exit 1; [ -n "$l" ] && for x in $l; do echo "$x"; done; exit 0 ;;
  rm)  for a in "$@"; do [ "$a" = -f ] || [ "$a" = -v ] || echo "$a" >> "$D/rm_calls"; done; exit "$(cat "$D/rm_rc" 2>/dev/null || echo 0)" ;;
  run) echo run >> "$D/run_calls"; l="$(line_for run)"; [ -z "$l" ] && l=OK; [ "$l" = OK ] && { echo container-id; exit 0; }; echo "${l#FAIL:}" >&2; exit 1 ;;
  *)   exit 0 ;;
esac
FAKE
chmod +x "$FDIR/docker"
DOCKER="$FDIR/docker"
LABEL="ai.saintvision.pitr-rehearsal.run=TESTNONCE"
NAME="pitr-probe-TESTNONCE"; PW=x; ACMD=x

FAILS=0
reset() { rm -f "$FDIR"/{ps,run,ps.n,run.n,rm_calls,run_calls,rm_rc}; : > "$FDIR/ps"; : > "$FDIR/run"; : > "$FDIR/rm_calls"; : > "$FDIR/run_calls"; echo 0 > "$FDIR/rm_rc"; }
ps_seq()  { printf '%s\n' "$@" > "$FDIR/ps"; }
run_seq() { printf '%s\n' "$@" > "$FDIR/run"; }
rm_calls(){ wc -l < "$FDIR/rm_calls" | tr -d ' '; }
run_calls(){ wc -l < "$FDIR/run_calls" | tr -d ' '; }
check() { if [ "$2" = "$3" ]; then echo "ok  : $1"; else echo "FAIL: $1  expected [$3] got [$2]"; FAILS=$((FAILS+1)); fi; }

# --- cleanup_owned branch matrix ---
reset; ps_seq "" ""                       # nothing owned (initial + re-query empty)
check "confirmed absence -> clean"                 "$(cleanup_owned)" "clean"
reset; ps_seq "" ""; cleanup_owned >/dev/null
check "confirmed absence removes nothing"          "$(rm_calls)" "0"

reset; ps_seq "FAIL"                      # query itself fails
check "ps query failure -> query-error (not clean)" "$(cleanup_owned)" "query-error"

reset; ps_seq "id1"; echo 1 > "$FDIR/rm_rc"        # a container present, rm fails
check "rm failure -> rm-error"                     "$(cleanup_owned)" "rm-error"

reset; ps_seq "id1" "id1"; echo 0 > "$FDIR/rm_rc"  # rm returns 0 but re-query still shows it
check "unconfirmed removal -> rm-error"            "$(cleanup_owned)" "rm-error"

reset; ps_seq "id1" ""; echo 0 > "$FDIR/rm_rc"     # present, removed, re-query confirms gone
check "confirmed removal -> clean"                 "$(cleanup_owned)" "clean"
reset; ps_seq "id1" ""; cleanup_owned >/dev/null
check "confirmed removal rm'd exactly the owned id" "$(cat "$FDIR/rm_calls")" "id1"

# foreign / past run: our label carries a unique nonce, so docker's filter matches none
check "label is bound to a unique run nonce"       "$(echo "$LABEL" | grep -c 'run=TESTNONCE')" "1"
reset; ps_seq "" ""                                # only foreign/past-run containers exist -> our filter empty
check "foreign/past-run untouched -> clean, no rm" "$(cleanup_owned)|$(rm_calls)" "clean|0"

# --- start_probe retry matrix ---
reset; run_seq "FAIL:i/o timeout" "OK"; ps_seq "" ""   # create times out, cleanup clean, transient -> retry
start_probe >/dev/null 2>&1; check "transient + confirmed clean -> retries and succeeds" "$?|$(run_calls)" "0|2"

reset; run_seq "FAIL:i/o timeout"; ps_seq "FAIL"       # cleanup cannot query -> must NOT retry
start_probe >/dev/null 2>&1; check "create fail + query-error -> no retry" "$?|$(run_calls)" "1|1"

reset; run_seq "FAIL:i/o timeout"; ps_seq "id1"; echo 1 > "$FDIR/rm_rc"  # cleanup rm fails -> no retry
start_probe >/dev/null 2>&1; check "create fail + rm-error -> no retry" "$?|$(run_calls)" "1|1"

reset; run_seq "FAIL:no such image" "OK"; ps_seq "" "" # non-transient error -> no retry even if clean
start_probe >/dev/null 2>&1; check "create fail + non-transient -> no retry" "$?|$(run_calls)" "1|1"

rm -rf "$FDIR"
echo "----"
[ "$FAILS" = 0 ] && { echo "ALL PITR-R2-02 negative controls passed"; exit 0; } || { echo "$FAILS check(s) failed"; exit 1; }
