#!/usr/bin/env bash
set -eu
HERE="$(cd "$(dirname "$0")" && pwd)"
SOURCE_ONLY=1 . "$HERE/tools/pitr_rehearsal.sh"
export REVIEW_STATE="$HERE/state"
mkdir -p "$REVIEW_STATE"
cat > "$HERE/fake-docker" <<'FAKE'
#!/usr/bin/env bash
set -eu
D="$REVIEW_STATE"
printf '%s\n' "$*" >> "$D/calls"
case "$1" in
ps)
 [ "$*" = 'ps -aq --filter label=ai.saintvision.pitr-rehearsal.run=current' ] || { echo filter-mismatch >&2; exit 91; }
 n=$(cat "$D/n"); echo $((n+1)) > "$D/n"
 if [ "$SCENARIO" = query ] || { [ "$SCENARIO" = postquery ] && [ "$n" -gt 0 ]; }; then exit 23; fi
 [ ! -f "$D/owned" ] || echo owned-id
 ;;
rm)
 [ "$*" = 'rm -f owned-id' ] || exit 92
 [ "$SCENARIO" != rmfail ] || exit 24
 [ "$SCENARIO" = retained ] || rm "$D/owned"
 ;;
run)
 n=$(cat "$D/runs"); echo $((n+1)) > "$D/runs"
 if [ "$n" = 0 ]; then touch "$D/owned"; echo 'i/o timeout' >&2; exit 1; fi
 echo created-id
 ;;
esac
FAKE
chmod +x "$HERE/fake-docker"
DOCKER="$HERE/fake-docker"; LABEL=ai.saintvision.pitr-rehearsal.run=current
NAME=current;PW=x;ACMD=x
sleep(){ :; }
for SCENARIO in clean query rmfail postquery retained; do
 export SCENARIO
 echo 0 > "$REVIEW_STATE/n";echo 0 > "$REVIEW_STATE/runs";: > "$REVIEW_STATE/calls"
 touch "$REVIEW_STATE/foreign" "$REVIEW_STATE/past" "$REVIEW_STATE/owned"
 rc=0;start_probe > "$REVIEW_STATE/output" || rc=$?
 runs=$(cat "$REVIEW_STATE/runs")
 if [ "$SCENARIO" = clean ]; then [ "$rc|$runs" = '0|2' ];else [ "$rc|$runs" = '1|1' ];fi
 [ -f "$REVIEW_STATE/foreign" ] && [ -f "$REVIEW_STATE/past" ]
 printf 'PASS %s: exit=%s runCalls=%s foreign/past preserved, exact filter checked\n' "$SCENARIO" "$rc" "$runs"
done
