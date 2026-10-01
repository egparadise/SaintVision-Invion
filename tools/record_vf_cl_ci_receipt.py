"""Bind a VF-CL card's ``ciVerified`` claim to GitHub's own answer about one run.

The claim this produces a receipt for is "CI re-derives this card". Before this existed,
the registry said so in prose and ``tools/check_vf_cl_registry.py`` checked the *shape* of
that prose -- a numeric run id, ``conclusion: success``, some step names. Codex probed it
and every one of five fabrications passed with no findings: an invented run id, a different
40-hex head, a workflow name nobody runs, invented steps, and all four at once. Shape is
not evidence. A boolean nobody can re-check is the thing this registry keeps correcting.

So the facts come from GitHub and are written down once, with their digests, and the
checker binds the registry to this file rather than to a sentence.

**Offline on purpose, like tools/import_ac11_security_scan.py.** The caller fetches three
documents with ``gh api`` and passes them as bytes; nothing here opens a socket. That keeps
the registry checker -- which runs inside the Backend and Core lanes, whose workflow
permissions are ``contents: read`` -- able to answer without a token and without a network,
and it keeps this tool's refusals reproducible from the files alone.

What it refuses, each because the claim would otherwise be unfounded:

* a run that is not ``completed``/``success``, or not in this repository, or not a run of
  the workflow the card names, or not an opt-in event;
* a job set where **any** job did not succeed, or where one of the card's required steps
  is missing or did not succeed -- "the run was green" is not "the step that derives the
  evidence ran";
* an artifact whose name is not ``<prefix><head sha>``, or that has expired, or whose
  expiry has passed, or whose digest is not a sha256 -- an unreachable artifact is a claim
  nobody can re-check;
* a head that is neither the claimed tree nor an ancestor of it.

The residual boundary, stated rather than hidden: the three inputs are what an
authenticated caller's ``gh api`` returned. That is the same trust boundary
``import_ac11_security_scan.py`` declares. Removing it means having CI produce this receipt
under ``actions: read`` and bringing it in as an artifact; that is a workflow-permission
decision, not something this tool can close.

Usage::

    gh api repos/<owner>/<repo>/actions/runs/<run>           > run.json
    gh api repos/<owner>/<repo>/actions/runs/<run>/jobs      > jobs.json
    gh api repos/<owner>/<repo>/actions/runs/<run>/artifacts > artifacts.json
    python tools/record_vf_cl_ci_receipt.py --card VF-CL-04 \
        --workflow .github/workflows/s12-acceptance-evidence.yml \
        --require-step "Derive the AC-12 acceptance items" \
        --artifact-prefix s12-acceptance- \
        --claimed-tree <40 hex> \
        --run-metadata run.json --jobs-metadata jobs.json \
        --artifact-metadata artifacts.json \
        --output docs/vf-cl-ci-receipts/VF-CL-04.json

Exit codes: 0 the receipt was written, 2 the inputs do not support the claim.
"""

from __future__ import annotations

import argparse
import datetime as dt
import hashlib
import json
from pathlib import Path
import re
import subprocess
import sys
from typing import Any

REPO_ROOT = Path(__file__).resolve().parents[1]
REPOSITORY = "egparadise/SaintVision-Invion"
SCHEMA = "vf-cl-ci-receipt:1"
CARD_PATTERN = re.compile(r"^VF-CL-\d{2}$")
SHA1 = re.compile(r"^[0-9a-f]{40}$")
SHA256 = re.compile(r"^[0-9a-f]{64}$")
DIGITS = re.compile(r"^[0-9]+$")
#: The events a card's evidence may come from. A ``push`` run of a shared branch is not
#: excluded because it is untrustworthy but because no card's evidence is produced that
#: way today, and widening this silently is how an unrelated run becomes evidence.
EVENTS = frozenset({"workflow_dispatch", "pull_request"})
#: The two fields of the receipt that are *derived*, so they are not part of what is
#: digested: including a digest in its own input is not a thing that can be recomputed.
UNDIGESTED = ("receiptSha256", "recordedAt")


class Refused(RuntimeError):
    """The inputs do not support the claim, which is not the same as the claim being false."""


def _document(path: Path, label: str) -> tuple[dict[str, Any], str]:
    try:
        raw = path.read_bytes()
    except OSError as error:
        raise Refused(f"{label} unreadable: {type(error).__name__}") from None
    try:
        value = json.loads(raw.decode("utf-8"))
    except (UnicodeError, json.JSONDecodeError) as error:
        raise Refused(f"{label} is not readable JSON: {type(error).__name__}") from None
    if not isinstance(value, dict):
        raise Refused(f"{label} must be a JSON object")
    return value, hashlib.sha256(raw).hexdigest()


def _utc(value: Any, label: str) -> dt.datetime:
    if not isinstance(value, str):
        raise Refused(f"{label} must be an RFC3339 timestamp")
    try:
        parsed = dt.datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError:
        raise Refused(f"{label} must be an RFC3339 timestamp") from None
    if parsed.tzinfo is None:
        raise Refused(f"{label} must carry a timezone")
    return parsed.astimezone(dt.timezone.utc)


def canonical_digest(receipt: dict[str, Any]) -> str:
    """The digest of everything the receipt asserts, so a hand edit is visible.

    It is not a signature and does not pretend to be: anybody who can edit the file can
    recompute it. What it closes is the *silent* edit -- a value changed in one place and
    not the other -- which is how this registry drifted twice.
    """
    body = {key: value for key, value in receipt.items() if key not in UNDIGESTED}
    return hashlib.sha256(
        json.dumps(body, sort_keys=True, separators=(",", ":"), ensure_ascii=False)
        .encode("utf-8")
    ).hexdigest()


def is_ancestor(candidate: str, descendant: str, root: Path) -> bool | None:
    """None when this clone cannot answer -- which is not the same as 'no'."""
    for sha in (candidate, descendant):
        probe = subprocess.run(
            ["git", "cat-file", "-e", f"{sha}^{{commit}}"],
            cwd=root, capture_output=True, text=True,
        )
        if probe.returncode != 0:
            return None
    done = subprocess.run(
        ["git", "merge-base", "--is-ancestor", candidate, descendant],
        cwd=root, capture_output=True, text=True,
    )
    return done.returncode == 0


def build(
    *,
    card: str,
    workflow: str,
    required_steps: list[str],
    artifact_prefix: str,
    claimed_tree: str,
    run: dict[str, Any],
    jobs: dict[str, Any],
    artifacts: dict[str, Any],
    digests: dict[str, str],
    root: Path,
    now: dt.datetime,
) -> dict[str, Any]:
    if not CARD_PATTERN.fullmatch(card):
        raise Refused(f"{card!r} is not a VF-CL card id")
    if not SHA1.fullmatch(claimed_tree):
        raise Refused("--claimed-tree must be a full 40-hex commit")
    if not required_steps:
        raise Refused("a card must name at least one required step")

    # ------------------------------------------------------------------ the run
    run_id = str(run.get("id") or "")
    if isinstance(run.get("id"), bool) or not DIGITS.fullmatch(run_id):
        raise Refused(f"run id is {run.get('id')!r}")
    repository = run.get("repository")
    if not isinstance(repository, dict) or repository.get("full_name") != REPOSITORY:
        raise Refused("the run is not a run of this repository")
    path = str(run.get("path") or "").split("@", 1)[0]
    if path != workflow:
        raise Refused(f"the run is a run of {path!r}, not {workflow!r}")
    if run.get("status") != "completed" or run.get("conclusion") != "success":
        raise Refused(
            f"the run concluded {run.get('conclusion')!r} with status {run.get('status')!r}"
        )
    event = run.get("event")
    if event not in EVENTS:
        raise Refused(f"the run's event is {event!r}")
    head = str(run.get("head_sha") or "")
    if not SHA1.fullmatch(head):
        raise Refused(f"the run's head_sha is {run.get('head_sha')!r}")

    relation = "same" if head == claimed_tree else None
    if relation is None:
        answer = is_ancestor(head, claimed_tree, root)
        if answer is None:
            raise Refused(
                "this clone cannot tell whether the run's head is in the claimed tree"
            )
        if not answer:
            raise Refused("the run's head is neither the claimed tree nor an ancestor of it")
        relation = "ancestor"

    # ------------------------------------------------------------------ the jobs
    entries = jobs.get("jobs")
    if not isinstance(entries, list) or not entries:
        raise Refused("the jobs document names no jobs")
    if any(entry.get("run_id") is not None and str(entry.get("run_id")) != run_id
           for entry in entries if isinstance(entry, dict)):
        raise Refused("the jobs document describes a different run")
    observed: dict[str, str] = {}
    for entry in entries:
        if not isinstance(entry, dict):
            raise Refused("a job entry is not an object")
        if entry.get("conclusion") != "success":
            raise Refused(
                f"job {entry.get('name')!r} concluded {entry.get('conclusion')!r}"
            )
        for step in entry.get("steps") or []:
            if not isinstance(step, dict) or not isinstance(step.get("name"), str):
                raise Refused("a step entry is not an object with a name")
            observed[step["name"]] = str(step.get("conclusion"))
    missing = [name for name in required_steps if name not in observed]
    if missing:
        raise Refused("required step(s) did not run: " + ", ".join(sorted(missing)))
    not_passed = sorted(name for name in required_steps if observed[name] != "success")
    if not_passed:
        raise Refused("required step(s) did not succeed: " + ", ".join(not_passed))

    # ------------------------------------------------------------------ the artifact
    uploaded = artifacts.get("artifacts")
    if not isinstance(uploaded, list):
        raise Refused("the artifacts document names no artifacts array")
    expected_name = f"{artifact_prefix}{head}"
    named = [entry for entry in uploaded
             if isinstance(entry, dict) and entry.get("name") == expected_name]
    if len(named) != 1:
        raise Refused(f"expected exactly one artifact named {expected_name!r}, found {len(named)}")
    artifact = named[0]
    artifact_id = str(artifact.get("id") or "")
    if isinstance(artifact.get("id"), bool) or not DIGITS.fullmatch(artifact_id):
        raise Refused(f"artifact id is {artifact.get('id')!r}")
    if artifact.get("expired") is not False:
        raise Refused("the artifact is expired or its expiry is unknown")
    expires = _utc(artifact.get("expires_at"), "artifact expires_at")
    if expires <= now:
        raise Refused("the artifact's expiry has passed")
    digest = str(artifact.get("digest") or "")
    if not digest.startswith("sha256:") or not SHA256.fullmatch(digest.removeprefix("sha256:")):
        raise Refused(f"artifact digest is {artifact.get('digest')!r}")

    receipt = {
        "schemaVersion": SCHEMA,
        "card": card,
        "repository": REPOSITORY,
        "workflowPath": workflow,
        "runId": run_id,
        "event": str(event),
        "conclusion": "success",
        "headSha": head,
        "headBranch": str(run.get("head_branch") or ""),
        "claimedTree": claimed_tree,
        "headRelationToClaimedTree": relation,
        "requiredSteps": sorted(required_steps),
        "artifact": {
            "id": artifact_id,
            "name": expected_name,
            "digest": digest,
            "expiresAt": expires.isoformat().replace("+00:00", "Z"),
        },
        "inputDigests": dict(sorted(digests.items())),
        "recordedAt": now.isoformat().replace("+00:00", "Z"),
    }
    receipt["receiptSha256"] = canonical_digest(receipt)
    return receipt


def parser() -> argparse.ArgumentParser:
    result = argparse.ArgumentParser(
        description="Bind a VF-CL card's ciVerified claim to GitHub's answer about one run."
    )
    result.add_argument("--card", required=True)
    result.add_argument("--workflow", required=True, help="the workflow file path")
    result.add_argument("--require-step", action="append", default=[], dest="require_step")
    result.add_argument("--artifact-prefix", required=True)
    result.add_argument("--claimed-tree", required=True, help="the tree the claim is about")
    result.add_argument("--run-metadata", type=Path, required=True)
    result.add_argument("--jobs-metadata", type=Path, required=True)
    result.add_argument("--artifact-metadata", type=Path, required=True)
    result.add_argument("--output", type=Path, required=True)
    return result


def main(argv: list[str] | None = None) -> int:
    args = parser().parse_args(argv)
    try:
        run, run_digest = _document(args.run_metadata, "run metadata")
        jobs, jobs_digest = _document(args.jobs_metadata, "jobs metadata")
        artifacts, artifacts_digest = _document(args.artifact_metadata, "artifact metadata")
        receipt = build(
            card=args.card,
            workflow=args.workflow,
            required_steps=list(args.require_step),
            artifact_prefix=args.artifact_prefix,
            claimed_tree=args.claimed_tree.strip().lower(),
            run=run,
            jobs=jobs,
            artifacts=artifacts,
            digests={
                "runMetadataSha256": run_digest,
                "jobsMetadataSha256": jobs_digest,
                "artifactMetadataSha256": artifacts_digest,
            },
            root=REPO_ROOT,
            now=dt.datetime.now(dt.timezone.utc),
        )
    except Refused as refusal:
        print(f"refused: {refusal}", file=sys.stderr)
        return 2
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(
        json.dumps(receipt, ensure_ascii=False, indent=1, sort_keys=True) + "\n",
        encoding="utf-8",
        # LF explicitly: the default translates on Windows, and a receipt that differs
        # between the writer's disk and the committed blob is a diff nobody meant.
        newline="\n",
    )
    print(json.dumps({
        "card": receipt["card"],
        "runId": receipt["runId"],
        "headSha": receipt["headSha"],
        "receipt": str(args.output),
    }, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
