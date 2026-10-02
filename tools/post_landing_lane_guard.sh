#!/usr/bin/env bash
# Fail-closed gates for the post-landing runbook (docs/vault/40_Operations/착지_직후_첫_행동_정본.md).
#
# Why this is a file and not three lines in the runbook (#320 r2):
#
#   * the runbook validated $LAND with a case pattern of eight [0-9a-f] followed by `*`, which
#     accepts `deadbeef`, `deadbeefZZ` and anything longer than 40 characters -- a prefix is
#     not a SHA (F1);
#   * it *printed* a run's status/conclusion/headSha/event for the operator to read, and
#     printing is not a gate: the next section started downloading regardless (F2);
#   * it dispatched the two AC-11 producers and then the aggregator with only a comment
#     between them, so the aggregator could start first and read nothing (F3).
#
# Every function here refuses with a non-zero status instead of printing, and
# tests/test_post_landing_lane_guard.py drives each refusal with a fake `gh` on PATH, so a
# later edit that turns a gate back into an echo fails a test rather than a landing.
#
# Exit statuses: 2 = malformed SHA, 3 = not exactly one matching run, 4 = run state refused.
#
# Usage (inside the runbook's shell session):
#   source tools/post_landing_lane_guard.sh
#   require_sha LAND "$LAND"
#   RUN=$(select_and_await s12-acceptance-evidence.yml "$LAND" workflow_dispatch "$CID")
#   ac11_dispatch_in_order "$LAND"
#
# Tunables (the tests set them; a real landing wants the defaults):
#   GUARD_LIST_ATTEMPTS (default 10)  how many times to look for a just-dispatched run
#   GUARD_LIST_SLEEP    (default 6)   seconds between those attempts
#   GUARD_DISPATCH_REF  (default integration/all-agents-unified)
#   GUARD_PYTHON        (default python)  the interpreter that runs the run selector

# The directory this file lives in, so the selector beside it is found however the runbook's
# shell session was started.
GUARD_DIR="${GUARD_DIR:-$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)}"

guard_refuse() {
  printf 'post-landing guard: %s\n' "$*" >&2
}

# require_sha <name> <value> -- exactly 40 lowercase hex characters, nothing else.
#
# The refusal never prints the value.  An operator pasting into this terminal may paste a token
# instead of a SHA, and a refusal that echoed it would write that token into the session log and
# into whatever captures it (#320 r2 F2).  Length and the failing property are enough to fix the
# paste; the value itself adds nothing a person does not already have in their clipboard.
require_sha() {
  local name="${1:-value}" value="${2-}" why
  if [[ ! $value =~ ^[0-9a-f]{40}$ ]]; then
    if [ "${#value}" -ne 40 ]; then
      why="length ${#value}, expected 40"
    elif [[ $value =~ [A-F] ]]; then
      why="contains upper-case hex; this must be lower case"
    else
      why="contains a character outside 0-9a-f"
    fi
    guard_refuse "$name is not a 40-character lowercase Git SHA ($why); the value is not printed"
    return 2
  fi
}

# select_unique_run <workflow> <sha> <event> <title> -- print the one run id that matches all
# four, or refuse.  Two runs with the same correlation id is a refusal, not a choice: `[0]`
# would silently pick one of a race.
select_unique_run() {
  local workflow="${1-}" sha="${2-}" event="${3-}" title="${4-}"
  local attempts="${GUARD_LIST_ATTEMPTS:-10}" pause="${GUARD_LIST_SLEEP:-6}"
  local attempt ids count
  require_sha "$workflow run headSha" "$sha" || return $?
  if [ -z "$workflow" ] || [ -z "$event" ] || [ -z "$title" ]; then
    guard_refuse "select_unique_run needs workflow, sha, event and title"
    return 3
  fi
  for ((attempt = 1; attempt <= attempts; attempt++)); do
    ids=$(gh run list --workflow "$workflow" --limit 50 \
      --json databaseId,headSha,event,displayTitle |
      "${GUARD_PYTHON:-python}" "$GUARD_DIR/post_landing_select_run.py" \
        --sha "$sha" --event "$event" --title "$title" |
      tr -d '\r' | grep -E '^[0-9]+$' || true)
    count=$(printf '%s' "$ids" | grep -c . || true)
    if [ "${count:-0}" -ge 1 ]; then
      break
    fi
    if [ "$attempt" -lt "$attempts" ]; then
      sleep "$pause"
    fi
  done
  if [ "${count:-0}" -ne 1 ]; then
    guard_refuse "expected exactly 1 run of $workflow at $sha (event $event, title '$title'), found ${count:-0}"
    return 3
  fi
  printf '%s\n' "$ids"
}

# await_run <run id> <sha> -- wait for that run and refuse unless it ended completed/success at
# that exact head.  `gh run watch --exit-status` is the wait; the re-read is the gate, because a
# watch that returns 0 still has to be about the right commit.
await_run() {
  local run="${1-}" sha="${2-}" state status conclusion head
  require_sha "awaited run headSha" "$sha" || return $?
  if [ -z "$run" ]; then
    guard_refuse "await_run needs a run id"
    return 3
  fi
  if ! gh run watch "$run" --exit-status >/dev/null; then
    guard_refuse "run $run did not finish successfully (gh run watch --exit-status)"
    return 4
  fi
  state=$(gh run view "$run" --json status,conclusion,headSha \
    --jq '[.status, .conclusion, .headSha] | @tsv' | tr -d '\r')
  IFS=$'\t' read -r status conclusion head <<<"$state"
  if [ "$status" != "completed" ] || [ "$conclusion" != "success" ] || [ "$head" != "$sha" ]; then
    guard_refuse "run $run is ${status:-?}/${conclusion:-?} at ${head:-?} -- required completed/success at $sha"
    return 4
  fi
}

# select_and_await <workflow> <sha> <event> <title> -- the pair, printing the run id it verified.
select_and_await() {
  local run
  run=$(select_unique_run "$1" "$2" "$3" "$4") || return $?
  await_run "$run" "$2" || return $?
  printf '%s\n' "$run"
}

# ac11_dispatch_in_order <landed sha> -- the order the runbook's table declares, enforced.
# Each producer is dispatched, found by its own correlation id at that head, and waited for
# before the next step; the aggregator is dispatched only after both have succeeded, so a
# producer that is still running, failed, or ran at another head means zero aggregate calls.
ac11_dispatch_in_order() {
  local land="${1-}" ref="${GUARD_DISPATCH_REF:-integration/all-agents-unified}"
  local workflow cid run
  require_sha LAND "$land" || return $?
  for workflow in ac11-security-scan.yml ac11-accessibility-e2e.yml; do
    cid="post-landing-$workflow-$land"
    gh workflow run "$workflow" --ref "$ref" -f correlation_id="$cid" || return $?
    run=$(select_and_await "$workflow" "$land" workflow_dispatch "$cid") || return $?
    printf '%s\t%s\n' "$workflow" "$run"
  done
  cid="post-landing-aggregate-$land"
  gh workflow run ac11-aggregate.yml --ref "$ref" \
    -f source_sha="$land" -f correlation_id="$cid" || return $?
  run=$(select_and_await ac11-aggregate.yml "$land" workflow_dispatch "$cid") || return $?
  printf '%s\t%s\n' ac11-aggregate.yml "$run"
}
