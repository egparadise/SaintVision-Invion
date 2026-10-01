"""Verify, at the SHA that just landed on integration, that every required lane ran.

A merge train lands by fast-forwarding `integration/all-agents-unified`. What each pull
request proved was proved at *its own* head; nothing yet says the six lanes pass at the tree
that is now integration. One lane cannot say it from pull-request runs at all -- `AC-11
Security Critical High Scan` runs only on a label or a manual dispatch -- which is why the
48-task re-score records its axis as measurable with no execution record bound to a landed
SHA.

So this binds a run to the landed SHA for each lane, waits, and writes down what happened.
It records; it does not promote. No score moves because this ran.

**It adopts the landing's own push run rather than dispatching a second one.** Five of the
six workflows trigger on `push` to `integration/all-agents-unified`, so the landing already
started them at exactly this SHA. Those workflows also set `cancel-in-progress: false` for
that ref, so a dispatch does not replace the push run -- it **queues behind it**, spending a
second runner and roughly doubling the wall-clock to learn the same thing. The tool therefore
dispatches a lane only when no run exists at the landed SHA, which in practice is AC-11, the
one lane with no push trigger. `--always-dispatch` restores the unconditional behaviour.

Four things it refuses to do, because each would make the record untrue:

* **It will not look for runs when the ref is not at the landed SHA.** A dispatch runs
  whatever the ref points at *now*. If integration has moved on, the runs would describe a
  different tree while this evidence named ours, so it stops before spending CI time. The
  tip is read with `git ls-remote`, not from a local `origin/...` ref that may be hours
  stale and may agree with the landed SHA by being old.
* **It will not accept a run whose `headSha` differs from the landed SHA**, even one it
  dispatched itself -- the ref can move between the dispatch and the run being created.
  Dispatched runs are additionally identified by a `databaseId` greater than the newest id
  seen before the dispatch, which run ids being monotonic makes exact.
* **It will not count a skipped job as a pass.** A workflow whose job was skipped still
  concludes `success`; that is the shape that let an earlier "rollback verified" step pass
  without a rollback. Every job of every lane is gated on `github.event_name !=
  'pull_request'` or on an explicit `workflow_dispatch`, so on a push to integration or on a
  dispatch there is no job that may legitimately skip -- and so the tool requires *every*
  job to have concluded `success`, naming any that did not.
* **It will not guess a workflow file from a check name.** The AC-11 lane's check is
  `security-critical-high` and its file is `ac11-security-scan.yml`; a tool that guessed
  would silently fail to bind the one lane this exercise exists for.

The `gh` and `git` calls go through an injected runner, so the tests drive every branch
without dispatching anything. `--dry-run` prints the plan and exits.

Exit codes: 0 every required job succeeded at the landed SHA, 1 something failed or was
skipped, 2 the inputs or the ref make the question unanswerable.
"""

from __future__ import annotations

import argparse
import datetime as dt
import json
from pathlib import Path
import subprocess
import sys
import time
from typing import Any, Callable, Sequence

REPO_ROOT = Path(__file__).resolve().parents[1]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from tools.operational_evidence import (  # noqa: E402
    COMMIT_PATTERN,
    LABEL_PATTERN,
    STATUSES,
    assert_no_secrets,
    collect_provenance_at_root,
    collector_sha256,
    default_label,
    input_binding_sha256,
    iso,
    overall_verdict,
    sha256_text,
    write_evidence,
)

SCHEMA_VERSION = "post-landing-verify:1"
DEFAULT_REF = "integration/all-agents-unified"
DEFAULT_OUT_DIR = REPO_ROOT / "docs/vault/30_Development/Evidence/landing"

#: The six lanes. `workflow` is the **file**, `jobs` maps each job id to how many jobs that
#: id must contribute -- `backend` is a two-version matrix, so GitHub names its jobs
#: `backend (3.12)` and `backend (3.14)` and both have to be there.
LANES: tuple[dict[str, Any], ...] = (
    {"key": "backend", "workflow": "backend.yml", "jobs": {"backend": 2, "mlflow-live": 1}},
    {"key": "core", "workflow": "core.yml", "jobs": {"core": 1, "s01-storage-roundtrip": 1}},
    {"key": "frontend", "workflow": "frontend.yml", "jobs": {"frontend": 1}},
    {
        "key": "desktopBrowser",
        "workflow": "desktop-browser.yml",
        "jobs": {"desktop-browser": 1},
    },
    {"key": "docs", "workflow": "docs.yml", "jobs": {"docs": 1}},
    {
        # The file name is not the check name. See the module docstring.
        "key": "securityCriticalHigh",
        "workflow": "ac11-security-scan.yml",
        "jobs": {"security-critical-high": 1},
    },
)

PRE_FLIGHT = ("landingWasFastForward", "refIsAtLandedSha")
REQUIRED = tuple(lane["key"] for lane in LANES) + PRE_FLIGHT

CRITERIA = {
    "landingWasFastForward": (
        "the previous SHA is an ancestor of the landed SHA, so this is the landing it "
        "claims to be and not an unrelated tree"
    ),
    "refIsAtLandedSha": (
        "the remote integration ref points at the landed SHA, so the runs describe the "
        "tree this evidence names"
    ),
    **{
        lane["key"]: (
            f"a run of {lane['workflow']} exists at the landed SHA and every one of its "
            "jobs concluded success, including "
            + ", ".join(
                name if count == 1 else f"{count} x {name}"
                for name, count in lane["jobs"].items()
            )
        )
        for lane in LANES
    },
}

#: Long on purpose. These lanes take ten to forty-five minutes and a dispatch can queue
#: behind the landing's own push run, so a short interval buys nothing and spends API quota.
#: One sleeping process is also the lightest thing to leave running on a small host.
DEFAULT_POLL_SECONDS = 120
DEFAULT_DEADLINE_SECONDS = 4 * 60 * 60


class VerifyRefused(RuntimeError):
    """The question cannot be answered, which is not the same as the answer being no."""


def passed(**facts: Any) -> dict[str, Any]:
    return {"status": "MEASURED_PASS", **facts}


def failed(reason: str, /, **facts: Any) -> dict[str, Any]:
    facts.pop("reason", None)
    return {"status": "MEASURED_FAIL", "reason": reason, **facts}


def unmeasured(reason: str, /, **facts: Any) -> dict[str, Any]:
    facts.pop("reason", None)
    return {"status": "NOT_OBSERVED", "reason": reason, **facts}


# --- the injected command runner ---------------------------------------------------


def real_runner(args: Sequence[str], *, timeout: float = 180.0) -> tuple[int, str]:
    """Run `gh` or `git` and return its exit code and stdout.

    stderr is deliberately not returned. It carries whatever the tool chose to print, and
    this evidence records our own conclusions rather than someone else's prose.
    """
    done = subprocess.run(
        list(args), cwd=REPO_ROOT, capture_output=True, text=True,
        encoding="utf-8", errors="replace", timeout=timeout,
    )
    return done.returncode, done.stdout


def commit_sha(value: str, label: str) -> str:
    text = (value or "").strip().lower()
    if not COMMIT_PATTERN.fullmatch(text):
        raise VerifyRefused(f"--{label} must be a full 40-hex commit, not {value!r}")
    return text


def json_out(runner, args: Sequence[str], fallback):
    code, out = runner(list(args))
    if code != 0:
        return fallback
    try:
        parsed = json.loads(out or "null")
    except json.JSONDecodeError:
        return fallback
    return parsed if parsed is not None else fallback


# --- the two checks that happen before any CI time is spent ------------------------


def check_fast_forward(runner, previous: str, landed: str) -> dict[str, Any]:
    """A landing is a fast-forward. If it is not, this is a different event.

    "We cannot tell" and "it is not an ancestor" are different answers, and a clone missing
    the objects gives the first. Only the second is a failure.
    """
    if previous == landed:
        return failed(
            "the previous and landed SHAs are the same, so nothing landed",
            landedSha=landed,
        )
    for sha in (previous, landed):
        code, _ = runner(["git", "cat-file", "-e", sha + "^{commit}"])
        if code != 0:
            return unmeasured(
                "a commit is missing from this clone, so ancestry cannot be judged; "
                "fetch the integration ref and run again",
                missingSha=sha,
            )
    code, _ = runner(["git", "merge-base", "--is-ancestor", previous, landed])
    if code != 0:
        return failed(
            "the previous SHA is not an ancestor of the landed SHA, so this was not a "
            "fast-forward landing",
            previousSha=previous,
            landedSha=landed,
        )
    return passed(previousSha=previous, landedSha=landed)


def remote_tip(runner, ref: str) -> str | None:
    """The ref as the remote has it now.

    `git rev-parse origin/<ref>` answers from the last fetch, which can be hours old, and a
    stale answer can agree with the landed SHA while the remote has moved on -- the exact
    vacuous pass this check exists to prevent.
    """
    code, out = runner(["git", "ls-remote", "origin", "refs/heads/" + ref])
    if code != 0:
        return None
    for line in (out or "").splitlines():
        sha, _, name = line.partition("\t")
        if name.strip() == "refs/heads/" + ref:
            candidate = sha.strip().lower()
            if COMMIT_PATTERN.fullmatch(candidate):
                return candidate
    return None


def check_ref_tip(runner, ref: str, landed: str) -> dict[str, Any]:
    tip = remote_tip(runner, ref)
    if tip is None:
        return unmeasured(f"the remote ref {ref} could not be read", ref=ref)
    if tip != landed:
        return failed(
            "the integration ref is not at the landed SHA, so a run of it would describe "
            "another tree",
            ref=ref,
            refTipSha=tip,
            landedSha=landed,
        )
    return passed(ref=ref, refTipSha=tip)


# --- find or start a run, then wait for it -----------------------------------------


#: Events whose run is about the ref itself. A `pull_request` run is excluded: for a pull
#: request GitHub reports the PR head as `headSha`, so a branch that was just fast-forwarded
#: has PR runs carrying the landed SHA while describing a merge of someone's branch, not the
#: integration ref. The branch check below excludes them too; both are kept because either
#: alone would be a single point of failure.
REF_EVENTS = frozenset({"push", "workflow_dispatch"})
DISPATCH_EVENT = "workflow_dispatch"


def runs_for(runner, workflow: str, ref: str, limit: int = 30) -> list[dict[str, Any]]:
    """Runs of this workflow on this branch.

    `--branch` is passed so the listing is already narrowed, and `headBranch` is checked
    again in `candidates_at_sha`: a filter we asked a tool for is not a fact we observed.
    """
    rows = json_out(
        runner,
        [
            "gh", "run", "list",
            "--workflow", workflow,
            "--branch", ref,
            "--limit", str(limit),
            "--json", "databaseId,headSha,headBranch,status,conclusion,event,createdAt",
        ],
        [],
    )
    if not isinstance(rows, list):
        return []
    return [row for row in rows if isinstance(row, dict)]


def candidates_at_sha(rows: list[dict[str, Any]], landed: str, ref: str, *,
                      events: frozenset[str], above: int = 0) -> list[dict[str, Any]]:
    """Every run that could be the one we mean, newest id first.

    Four things have to agree, and each excludes a real way of being wrong:

    * `headSha` -- otherwise the run is about another tree;
    * `headBranch` -- otherwise a pull-request run at the same commit, or a run on another
      branch that happens to point here, is read as the landing's own run;
    * `event` -- otherwise the same confusion arrives by a different door;
    * `databaseId > above` -- otherwise a run that was already there is read as the one we
      just started.

    The list is returned rather than a single row, because *more than one* candidate is
    itself an answer: when two dispatches of the same workflow are in flight at the same
    SHA, this tool cannot tell which is its own, and saying so is better than picking.
    """
    found = []
    for row in rows:
        if str(row.get("headSha", "")).lower() != landed:
            continue
        if str(row.get("headBranch", "")) != ref:
            continue
        if str(row.get("event", "")) not in events:
            continue
        identifier = row.get("databaseId")
        if not isinstance(identifier, int) or identifier <= above:
            continue
        found.append(row)
    return sorted(found, key=lambda row: row["databaseId"], reverse=True)


def highest_id(rows: list[dict[str, Any]]) -> int:
    return max(
        (row["databaseId"] for row in rows if isinstance(row.get("databaseId"), int)),
        default=0,
    )


def dispatch(runner, workflow: str, ref: str) -> bool:
    code, _ = runner(["gh", "workflow", "run", workflow, "--ref", ref])
    return code == 0


def view_run(runner, run_id: int) -> dict[str, Any]:
    document = json_out(
        runner,
        [
            "gh", "run", "view", str(run_id),
            "--json", "status,conclusion,headSha,headBranch,event,jobs",
        ],
        {},
    )
    return document if isinstance(document, dict) else {}


def matrix_matches(names, job_id: str) -> list[str]:
    """A job id matches a name exactly, or as the prefix of a matrix leg `id (value)`."""
    return [name for name in names if name == job_id or name.startswith(job_id + " (")]


def judge_lane(lane: dict[str, Any], run_id: int, view: dict[str, Any],
               landed: str, ref: str, *, event: str | None) -> dict[str, Any]:
    """A lane passes when a run of this ref at the landed SHA has every job `success`.

    The SHA, the branch and the event are re-read from the run itself rather than trusted
    from the listing that selected it: the listing is how we found the run, and this is what
    the run says it is.
    """
    head = str(view.get("headSha", "")).lower()
    if head != landed:
        return failed(
            "the run's headSha is not the landed SHA",
            workflow=lane["workflow"], runId=run_id, headSha=head,
        )
    branch = str(view.get("headBranch", ""))
    if branch != ref:
        return failed(
            "the run is not a run of the integration ref",
            workflow=lane["workflow"], runId=run_id, headBranch=branch,
        )
    seen = str(view.get("event", ""))
    if seen not in REF_EVENTS:
        return failed(
            "the run was triggered by an event that does not describe the ref",
            workflow=lane["workflow"], runId=run_id, event=seen,
        )
    jobs = [job for job in (view.get("jobs") or []) if isinstance(job, dict)]
    if not jobs:
        return unmeasured(
            "the run reported no jobs", workflow=lane["workflow"], runId=run_id
        )
    conclusions = {str(job.get("name")): str(job.get("conclusion")) for job in jobs}
    short = {
        job_id: {"expected": count, "found": len(matrix_matches(conclusions, job_id))}
        for job_id, count in lane["jobs"].items()
        if len(matrix_matches(conclusions, job_id)) < count
    }
    if short:
        return failed(
            "a required job is missing from the run",
            workflow=lane["workflow"], runId=run_id, missingJobs=short,
            observedJobs=sorted(conclusions),
        )
    # No job of these workflows may legitimately skip on a push to integration or on a
    # dispatch, so every job counts -- including ones this tool does not name.
    unpassed = {
        name: conclusion for name, conclusion in conclusions.items()
        if conclusion != "success"
    }
    if unpassed:
        return failed(
            "a job did not conclude success; a skipped job leaves its axis unobserved",
            workflow=lane["workflow"], runId=run_id, jobsNotPassed=unpassed,
            skippedJobs=sorted(n for n, c in unpassed.items() if c == "skipped"),
        )
    return passed(
        workflow=lane["workflow"], runId=run_id, headSha=head, headBranch=branch,
        event=seen or event, runConclusion=view.get("conclusion"),
        jobCount=len(conclusions), jobConclusions=conclusions,
    )


def bind_runs(runner, ref: str, landed: str, *, always_dispatch: bool):
    """Adopt a run at the landed SHA where one exists; dispatch where none does."""
    bound: dict[str, dict[str, Any]] = {}
    problems: dict[str, dict[str, Any]] = {}
    for lane in LANES:
        rows = runs_for(runner, lane["workflow"], ref)
        existing = None
        if not always_dispatch:
            # Adopting the newest is right here: several runs of the same workflow on the
            # same ref at the same SHA are re-runs of one question, not rival answers.
            found = candidates_at_sha(rows, landed, ref, events=REF_EVENTS)
            existing = found[0] if found else None
        if existing is not None:
            bound[lane["key"]] = {
                "workflow": lane["workflow"],
                "runId": existing["databaseId"],
                "event": existing.get("event"),
                "headBranch": existing.get("headBranch"),
                "dispatched": False,
            }
            continue
        baseline = highest_id(rows)
        if not dispatch(runner, lane["workflow"], ref):
            problems[lane["key"]] = failed(
                "the workflow could not be dispatched", workflow=lane["workflow"]
            )
            continue
        bound[lane["key"]] = {
            "workflow": lane["workflow"],
            "runId": None,
            "event": DISPATCH_EVENT,
            "headBranch": ref,
            "dispatched": True,
            "baselineRunId": baseline,
        }
    return bound, problems


def wait_for(runner, bound: dict[str, dict[str, Any]], landed: str, ref: str, *,
             poll_seconds: int, deadline_seconds: int,
             sleep: Callable[[float], None] = time.sleep,
             now: Callable[[], float] = time.monotonic) -> dict[str, dict[str, Any]]:
    """Poll until every bound run is completed, or the deadline passes.

    A lane whose run never appears, never finishes, or cannot be told apart from somebody
    else's dispatch is NOT_OBSERVED rather than a failure: the lane did not fail, we failed
    to watch it, and those are different facts.
    """
    started = now()
    results: dict[str, dict[str, Any]] = {}
    waiting = dict(bound)
    while waiting:
        for key, entry in list(waiting.items()):
            if entry["runId"] is None:
                # A dispatched run may not exist yet, and there may be more than one --
                # anyone can dispatch the same workflow on the same ref at the same SHA.
                # Nothing in the API ties a dispatch to the run it created, so when two
                # are candidates this tool refuses to choose.
                fresh = candidates_at_sha(
                    runs_for(runner, entry["workflow"], ref), landed, ref,
                    events=frozenset({DISPATCH_EVENT}),
                    above=entry.get("baselineRunId", 0),
                )
                if not fresh:
                    continue
                if len(fresh) > 1:
                    entry["ambiguous"] = sorted(row["databaseId"] for row in fresh)
                    results[key] = {**entry, "view": None}
                    waiting.pop(key)
                    continue
                entry["runId"] = fresh[0]["databaseId"]
                entry["event"] = fresh[0].get("event")
                entry["headBranch"] = fresh[0].get("headBranch")
            view = view_run(runner, entry["runId"])
            if str(view.get("status")) == "completed":
                results[key] = {**entry, "view": view}
                waiting.pop(key)
        if not waiting:
            break
        if now() - started > deadline_seconds:
            for key, entry in waiting.items():
                results[key] = {**entry, "view": None}
            break
        sleep(poll_seconds)
    return results


# --- the report -------------------------------------------------------------------


def validate_evidence(evidence: dict[str, Any]) -> None:
    """The collector's own checks.

    `operational_evidence.validate_common` is not used: it requires a database binding and
    an `acceptanceClaim`, and this collector observes neither a database nor an acceptance
    -- it records which lanes ran. The checks that do apply are repeated here.
    """
    if evidence.get("schemaVersion") != SCHEMA_VERSION:
        raise ValueError("schemaVersion mismatch")
    if not COMMIT_PATTERN.fullmatch(str(evidence.get("codeSha") or "")):
        raise ValueError("codeSha must be an exact 40-hex commit")
    if evidence.get("criteria") != CRITERIA:
        raise ValueError("criteria binding mismatch")
    observations = evidence.get("observations") or {}
    if set(observations) != set(REQUIRED):
        raise ValueError("observations must be exactly the required ones")
    for name, observation in observations.items():
        if observation.get("status") not in STATUSES:
            raise ValueError(f"{name} has no recognised status")
    if evidence.get("verdict") != overall_verdict(observations, REQUIRED):
        raise ValueError("verdict was not recomputed from observations")
    if evidence.get("promotesScore") is not False:
        raise ValueError("this collector records evidence and never promotes a score")
    source = evidence.get("source") or {}
    for field in ("landedSha", "previousSha"):
        if not COMMIT_PATTERN.fullmatch(str(source.get(field) or "")):
            raise ValueError(f"{field} must be a full 40-hex commit")
    # Every lane that passed names the run it passed on, so the record can be rechecked.
    for lane in LANES:
        item = observations[lane["key"]]
        if item["status"] == "MEASURED_PASS" and not isinstance(item.get("runId"), int):
            raise ValueError(f"{lane['key']} passed without naming a run")
    provenance = evidence.get("provenance") or {}
    # Content-clean, not status-clean: this tool writes its own evidence under
    # docs/vault/.../Evidence/landing, so a previous run's untracked output must not block
    # the next run. A tracked modification still does.
    if provenance.get("contentClean") is not True:
        raise ValueError("evidence source tree has uncommitted tracked changes")


def render_markdown(evidence: dict[str, Any]) -> str:
    source = evidence["source"]
    dispatched = ", ".join(source["dispatchedWorkflows"]) or "none"
    lines = [
        f"# Post-landing verification — {evidence['verdict']}",
        "",
        f"- landed SHA: `{source['landedSha']}`",
        f"- previous SHA: `{source['previousSha']}`",
        f"- ref: `{source['ref']}`",
        f"- observed: {source['observedAt']} → {source['sourceFinishedAt']}",
        f"- collector: `{evidence['collectorSha256'][:16]}` at `{str(evidence['codeSha'])[:12]}`",
        f"- dispatched by this run: {dispatched}",
        "- **this record promotes no score.** It says which lanes ran at this tree.",
        "",
        "| lane | status | run | detail |",
        "|---|---|---|---|",
    ]
    for key in REQUIRED:
        item = evidence["observations"][key]
        run_id = item.get("runId") or "—"
        if key in PRE_FLIGHT:
            detail = item.get("reason") or item.get("refTipSha") or item.get("landedSha", "")
        elif item["status"] == "MEASURED_PASS":
            detail = f"{item.get('jobCount', 0)} jobs success ({item.get('event')})"
        else:
            detail = item.get("reason", "")
        lines.append(f"| `{key}` | {item['status']} | {run_id} | {detail} |")
    return "\n".join(lines) + "\n"


def parser() -> argparse.ArgumentParser:
    result = argparse.ArgumentParser(
        description="Bind a CI run to the SHA that just landed on integration, for each "
                    "required lane, and record what happened."
    )
    result.add_argument("--landed", required=True, help="the SHA that landed on the ref")
    result.add_argument("--previous", required=True, help="the SHA the ref was at before")
    result.add_argument("--ref", default=DEFAULT_REF)
    result.add_argument("--out-dir", type=Path, default=DEFAULT_OUT_DIR)
    result.add_argument("--poll-seconds", type=int, default=DEFAULT_POLL_SECONDS)
    result.add_argument("--deadline-seconds", type=int, default=DEFAULT_DEADLINE_SECONDS)
    result.add_argument(
        "--always-dispatch", action="store_true",
        help="dispatch every lane even when a run already exists at the landed SHA "
             "(costs a second runner per lane and queues behind the landing's push run)",
    )
    result.add_argument("--label")
    result.add_argument("--executor", default="claude")
    result.add_argument(
        "--dry-run", action="store_true",
        help="print what would be checked and exit without dispatching",
    )
    return result


def run(args, runner, *, sleep=time.sleep, now=time.monotonic):
    landed = commit_sha(args.landed, "landed")
    previous = commit_sha(args.previous, "previous")

    observations: dict[str, dict[str, Any]] = {
        "landingWasFastForward": check_fast_forward(runner, previous, landed),
        "refIsAtLandedSha": check_ref_tip(runner, args.ref, landed),
    }
    # A proven-wrong pre-flight blocks, and so does an unreadable ref: both mean the runs
    # would be about a tree this evidence does not name. Unjudgeable ancestry does not
    # block -- the runs would still be about the landed SHA -- and leaves the verdict
    # NOT_OBSERVED, which is the honest outcome.
    blocked = sorted(
        {name for name in PRE_FLIGHT if observations[name]["status"] == "MEASURED_FAIL"}
        | ({"refIsAtLandedSha"} if observations["refIsAtLandedSha"]["status"] != "MEASURED_PASS" else set())
    )
    if blocked:
        for lane in LANES:
            observations[lane["key"]] = unmeasured(
                "not observed: " + ", ".join(blocked), workflow=lane["workflow"]
            )
        return observations, {
            "landedSha": landed, "previousSha": previous, "ref": args.ref,
            "dispatchedWorkflows": [], "adoptedWorkflows": [],
        }

    bound, problems = bind_runs(runner, args.ref, landed, always_dispatch=args.always_dispatch)
    observations.update(problems)
    results = wait_for(
        runner, bound, landed, args.ref,
        poll_seconds=args.poll_seconds, deadline_seconds=args.deadline_seconds,
        sleep=sleep, now=now,
    )
    by_key = {lane["key"]: lane for lane in LANES}
    for key, entry in results.items():
        if entry.get("ambiguous"):
            observations[key] = unmeasured(
                "more than one dispatch of this workflow is a candidate at the landed SHA, "
                "and nothing ties a dispatch to the run it created, so this tool will not "
                "choose between them",
                workflow=entry["workflow"], candidateRunIds=entry["ambiguous"],
            )
            continue
        if entry["view"] is None:
            observations[key] = unmeasured(
                "the run did not complete within the deadline",
                workflow=entry["workflow"], runId=entry["runId"],
            )
            continue
        observations[key] = judge_lane(
            by_key[key], entry["runId"], entry["view"], landed, args.ref,
            event=entry.get("event"),
        )
    for lane in LANES:
        observations.setdefault(
            lane["key"],
            unmeasured("the lane was neither adopted nor dispatched", workflow=lane["workflow"]),
        )

    return observations, {
        "landedSha": landed, "previousSha": previous, "ref": args.ref,
        "dispatchedWorkflows": sorted(
            entry["workflow"] for entry in bound.values() if entry["dispatched"]
        ),
        "adoptedWorkflows": sorted(
            entry["workflow"] for entry in bound.values() if not entry["dispatched"]
        ),
    }


def build_evidence(observations, facts, provenance, started, finished) -> dict[str, Any]:
    verdict = overall_verdict(observations, REQUIRED)
    return {
        "schemaVersion": SCHEMA_VERSION,
        "codeSha": provenance.get("commit_sha"),
        "collectorSha256": collector_sha256(__file__),
        "criteria": CRITERIA,
        "promotesScore": False,
        "provenance": {
            "branch": provenance.get("branch"),
            "workingTreeClean": provenance.get("working_tree_clean_status"),
            "contentClean": provenance.get("content_clean_diff"),
            "executor": provenance.get("executor"),
        },
        "source": {
            "observedAt": iso(started),
            "sourceFinishedAt": iso(finished),
            "landedShaSha256": sha256_text(facts["landedSha"]),
            "inputBindingSha256": input_binding_sha256({
                "landedSha": facts["landedSha"],
                "previousSha": facts["previousSha"],
                "ref": facts["ref"],
            }),
            **facts,
        },
        "observations": observations,
        "verdict": verdict,
    }


def main(argv: list[str] | None = None, runner=real_runner) -> int:
    args = parser().parse_args(argv)
    if args.dry_run:
        print(json.dumps({
            "ref": args.ref,
            "landed": args.landed,
            "previous": args.previous,
            "lanes": {lane["key"]: lane["workflow"] for lane in LANES},
            "requiredJobs": {lane["key"]: lane["jobs"] for lane in LANES},
            "alwaysDispatch": bool(args.always_dispatch),
            "pollSeconds": args.poll_seconds,
            "dispatched": False,
        }, indent=2, sort_keys=True))
        return 0

    started = dt.datetime.now(dt.timezone.utc)
    provenance = collect_provenance_at_root(args.executor)
    try:
        observations, facts = run(args, runner)
    except VerifyRefused as refusal:
        print(f"refused: {refusal}", file=sys.stderr)
        return 2
    except (OSError, subprocess.SubprocessError) as error:
        print(f"refused: {type(error).__name__}", file=sys.stderr)
        return 2

    evidence = build_evidence(
        observations, facts, provenance, started, dt.datetime.now(dt.timezone.utc)
    )
    try:
        validate_evidence(evidence)
    except ValueError as error:
        print(f"refused: {error}", file=sys.stderr)
        return 2

    label = args.label or default_label("post-landing-verify", str(evidence["codeSha"]))
    if not LABEL_PATTERN.fullmatch(label):
        print(f"refused: label {label!r} is not a safe file name", file=sys.stderr)
        return 2
    assert_no_secrets(json.dumps(evidence, ensure_ascii=False, sort_keys=True))
    assert_no_secrets(render_markdown(evidence))
    json_path, markdown_path = write_evidence(
        evidence, args.out_dir, label, render_markdown=render_markdown
    )
    printed = json.dumps({
        "verdict": evidence["verdict"],
        "json": json_path.name,
        "markdown": markdown_path.name,
        "promotesScore": False,
    }, ensure_ascii=False, sort_keys=True)
    assert_no_secrets(printed)
    print(printed)
    return 0 if evidence["verdict"] == "PASS" else 1


if __name__ == "__main__":
    raise SystemExit(main())
