#!/usr/bin/env python3
"""Run the four currently hosted AC-11 axes for one exact source SHA.

This is orchestration, not a second evaluator.  It finds the security, accessibility and
migration-rehearsal producer runs at one exact SHA, dispatches only a producer that has no usable
run, waits for those runs, and then dispatches the aggregate lane.  The uploaded aggregate is not
trusted: this tool downloads it and calls :mod:`tools.aggregate_ac11_evidence` again from the exact
clean checkout.  The recomputed document is the only verdict written to the receipt.

The trust boundary is deliberately narrower than ``gh run list | first``:

* source SHA, branch, event, workflow path and run attempt are all checked again on the run view;
* a repeated attempt, two usable runs, a reused run/artifact id, or two artifacts of the expected
  name is refused;
* artifact expiry, workflow-run binding and the SHA-256 of the downloaded zip are checked;
* after aggregation, producer uniqueness is checked again and every emitted envelope is bound to
  the selected run and artifact digest;
* stderr and artifact contents are never copied to the receipt, so credentials cannot be echoed.

Exit 0 means orchestration and canonical recomputation completed.  It does *not* mean AC-11 passed:
``canonicalResult.verdict`` can honestly be ``MEASURED_FAIL`` or ``INVALID_RUN``.  Exit 2 is a
fail-closed refusal.  This tool changes no evaluator, schema or target registry.
"""

from __future__ import annotations

import argparse
import datetime as dt
import hashlib
import io
import json
import os
import re
import subprocess
import sys
import time
import uuid
import zipfile
from dataclasses import dataclass
from pathlib import Path, PurePosixPath
from typing import Any, Callable, Protocol, Sequence
from urllib.parse import quote

# Support the documented direct invocation (`python tools/<name>.py`) as well as module imports.
# Python otherwise puts only `tools/` on sys.path, so `from tools ...` fails before argument
# validation and no operator can run the exact-SHA procedure.
if __package__ in {None, ""}:
    sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from tools import aggregate_ac11_evidence as canonical
from tools.operational_evidence import assert_no_secrets


ROOT = Path(__file__).resolve().parents[1]
SOURCE_MAP = ROOT / "docs" / "ac11-axis-sources.json"
ALLOWLIST = ROOT / "docs" / "vault" / "30_Development" / "Evidence" / "s11-security-allowlist-v0.json"
SCHEMA_VERSION = "ac11-exact-sha-orchestration:1"
AGGREGATE_WORKFLOW = ".github/workflows/ac11-aggregate.yml"
AGGREGATE_ARTIFACT_PREFIX = "s11-ac11-aggregate-"
SHA_RE = re.compile(r"[0-9a-f]{40}")
DIGEST_RE = re.compile(r"sha256:([0-9a-f]{64})")
REPOSITORY_RE = re.compile(r"[A-Za-z0-9_.-]+/[A-Za-z0-9_.-]+")
REF_RE = re.compile(r"[A-Za-z0-9._/-]{1,200}")
UTC_RE = re.compile(r"\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}Z")
EXPECTED_WORKFLOWS = {
    ".github/workflows/ac11-security-scan.yml": True,
    ".github/workflows/ac11-accessibility-e2e.yml": True,
    ".github/workflows/ac11-migration-rehearsal.yml": False,
}
RUN_JSON_FIELDS = (
    "attempt,databaseId,displayTitle,event,headBranch,headSha,status,conclusion,workflowName,url,createdAt"
)
RUN_STATUSES = frozenset({"queued", "requested", "waiting", "pending", "in_progress", "completed"})


class Refused(RuntimeError):
    """The requested measurement cannot be bound without guessing."""


class Runner(Protocol):
    def __call__(self, args: Sequence[str], *, timeout: float = 300.0) -> tuple[int, bytes]: ...


@dataclass(frozen=True)
class Producer:
    workflow: str
    artifact_prefix: str
    axes: tuple[str, ...]
    correlation_supported: bool


@dataclass(frozen=True)
class Artifact:
    artifact_id: int
    name: str
    digest: str
    expires_at: str
    archive: bytes


@dataclass(frozen=True)
class BoundRun:
    producer: Producer
    row: dict[str, Any]
    artifact: Artifact
    reused: bool
    correlation_id: str | None = None


def real_runner(args: Sequence[str], *, timeout: float = 300.0) -> tuple[int, bytes]:
    """Run a command without returning stderr, which may contain environment details."""

    done = subprocess.run(
        list(args), cwd=ROOT, capture_output=True, timeout=timeout, check=False
    )
    return done.returncode, done.stdout


def _pairs(pairs: list[tuple[str, Any]]) -> dict[str, Any]:
    result: dict[str, Any] = {}
    for key, value in pairs:
        if key in result:
            raise Refused(f"duplicate JSON key {key!r}")
        result[key] = value
    return result


def strict_json(data: bytes | str, label: str) -> Any:
    try:
        text = data.decode("utf-8") if isinstance(data, bytes) else data
        return json.loads(text, object_pairs_hook=_pairs)
    except (UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise Refused(f"{label} is not strict UTF-8 JSON") from exc


def command(runner: Runner, args: Sequence[str], label: str, *, timeout: float = 300.0) -> bytes:
    code, out = runner(args, timeout=timeout)
    if code != 0:
        raise Refused(f"{label} failed with exit {code}")
    return out


def command_json(runner: Runner, args: Sequence[str], label: str, *, timeout: float = 300.0) -> Any:
    return strict_json(command(runner, args, label, timeout=timeout), label)


def source_sha(value: str) -> str:
    text = str(value or "").strip().lower()
    if not SHA_RE.fullmatch(text):
        raise Refused("source SHA must be a full lowercase 40-hex commit")
    return text


def repository_name(value: str) -> str:
    text = str(value or "").strip()
    if not REPOSITORY_RE.fullmatch(text):
        raise Refused("repository must be owner/name without URL or whitespace")
    return text


def branch_name(value: str) -> str:
    text = str(value or "").strip()
    if (
        not REF_RE.fullmatch(text)
        or text.startswith(("-", "/"))
        or text.endswith(("/", ".", ".lock"))
        or ".." in text
        or "//" in text
        or "@{" in text
    ):
        raise Refused("ref is not a safe branch name")
    return text


def utc(value: Any, label: str) -> dt.datetime:
    if not isinstance(value, str) or not UTC_RE.fullmatch(value):
        raise Refused(f"{label} must be second-precision UTC RFC3339")
    parsed = dt.datetime.strptime(value, "%Y-%m-%dT%H:%M:%SZ").replace(tzinfo=dt.timezone.utc)
    return parsed


def iso(value: dt.datetime) -> str:
    return value.astimezone(dt.timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")


def load_producers(root: Path = ROOT) -> tuple[Producer, ...]:
    document = strict_json((root / SOURCE_MAP.relative_to(ROOT)).read_bytes(), "axis source map")
    if not isinstance(document, dict) or not isinstance(document.get("axes"), list):
        raise Refused("axis source map has no axes list")
    grouped: dict[str, dict[str, Any]] = {}
    for row in document["axes"]:
        if not isinstance(row, dict) or row.get("chain") != "complete":
            continue
        workflow = row.get("workflow")
        if workflow not in EXPECTED_WORKFLOWS:
            raise Refused(f"unexpected complete AC-11 producer workflow {workflow!r}")
        prefix = row.get("artifactNamePrefix")
        axis = row.get("axis")
        if not isinstance(prefix, str) or not prefix or not isinstance(axis, str) or not axis:
            raise Refused("complete producer row lacks artifact prefix or axis")
        entry = grouped.setdefault(workflow, {"prefix": prefix, "axes": []})
        if entry["prefix"] != prefix or axis in entry["axes"]:
            raise Refused(f"conflicting source-map rows for {workflow}")
        entry["axes"].append(axis)
    if set(grouped) != set(EXPECTED_WORKFLOWS):
        raise Refused("complete producer workflow set differs from the reviewed three-lane set")
    return tuple(
        Producer(workflow, grouped[workflow]["prefix"], tuple(grouped[workflow]["axes"]), correlated)
        for workflow, correlated in EXPECTED_WORKFLOWS.items()
    )


def local_checkout(runner: Runner, sha: str) -> str:
    head = command(runner, ["git", "rev-parse", "HEAD"], "read local HEAD").decode().strip().lower()
    if head != sha:
        raise Refused(f"local HEAD is not source SHA {sha}")
    dirty = command(runner, ["git", "status", "--porcelain"], "read local status").decode().strip()
    if dirty:
        raise Refused("local checkout is not clean")
    tree = command(
        runner, ["git", "rev-parse", f"{sha}^{{tree}}"], "read source tree"
    ).decode().strip().lower()
    if not SHA_RE.fullmatch(tree):
        raise Refused("source tree is not a full Git object id")
    return tree


def ensure_remote_ref(runner: Runner, repository: str, ref: str, sha: str) -> None:
    encoded = quote(ref, safe="")
    doc = command_json(
        runner,
        ["gh", "api", f"repos/{repository}/git/ref/heads/{encoded}"],
        "read remote ref",
    )
    observed = doc.get("object", {}).get("sha") if isinstance(doc, dict) else None
    if observed != sha:
        raise Refused(f"remote ref {ref} is not at source SHA {sha}")


def list_runs(runner: Runner, repository: str, ref: str, workflow: str) -> list[dict[str, Any]]:
    rows = command_json(
        runner,
        [
            "gh", "run", "list", "--repo", repository, "--workflow", Path(workflow).name,
            "--branch", ref, "--limit", "100", "--json", RUN_JSON_FIELDS,
        ],
        f"list {workflow} runs",
    )
    if not isinstance(rows, list) or not all(isinstance(row, dict) for row in rows):
        raise Refused(f"{workflow} run listing is not an object list")
    return rows


def _row_id(row: dict[str, Any]) -> int:
    value = row.get("databaseId")
    if not isinstance(value, int) or isinstance(value, bool) or value <= 0:
        raise Refused("run has no positive integer id")
    return value


def exact_rows(rows: list[dict[str, Any]], producer: Producer, sha: str, ref: str) -> list[dict[str, Any]]:
    selected: list[dict[str, Any]] = []
    for row in rows:
        if row.get("headSha") != sha or row.get("headBranch") != ref:
            continue
        if row.get("event") != "workflow_dispatch" or row.get("workflowName") != producer.workflow:
            continue
        _row_id(row)
        attempt = row.get("attempt")
        if attempt != 1 or isinstance(attempt, bool):
            raise Refused(f"{producer.workflow} reused run attempt {attempt!r}")
        status = row.get("status")
        if status not in RUN_STATUSES:
            raise Refused(f"{producer.workflow} has unknown run status {status!r}")
        selected.append(row)
    return sorted(selected, key=_row_id)


def usable_rows(rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
    return [
        row for row in rows
        if row.get("status") != "completed" or row.get("conclusion") == "success"
    ]


def view_run(runner: Runner, repository: str, run_id: int) -> dict[str, Any]:
    doc = command_json(
        runner,
        ["gh", "run", "view", str(run_id), "--repo", repository, "--json", RUN_JSON_FIELDS],
        f"view run {run_id}",
    )
    if not isinstance(doc, dict):
        raise Refused(f"run {run_id} view is not an object")
    return doc


def validate_run(row: dict[str, Any], producer: Producer, sha: str, ref: str, *,
                 correlation_id: str | None = None) -> None:
    if _row_id(row) <= 0:
        raise AssertionError("unreachable")
    expected = {
        "headSha": sha,
        "headBranch": ref,
        "event": "workflow_dispatch",
        "workflowName": producer.workflow,
        "attempt": 1,
    }
    for key, value in expected.items():
        if row.get(key) != value:
            raise Refused(f"run {_row_id(row)} {key} differs from the exact-SHA binding")
    if correlation_id is not None and row.get("displayTitle") != correlation_id:
        raise Refused(f"run {_row_id(row)} does not carry this dispatch correlation id")
    if row.get("status") != "completed" or row.get("conclusion") != "success":
        raise Refused(f"run {_row_id(row)} did not complete successfully")


def _deadline_wait(started: float, deadline: float, now: Callable[[], float]) -> None:
    if now() - started > deadline:
        raise Refused("workflow did not complete before the deadline")


def wait_existing(runner: Runner, repository: str, row: dict[str, Any], producer: Producer,
                  sha: str, ref: str, *, poll_seconds: float, deadline_seconds: float,
                  sleep: Callable[[float], None], now: Callable[[], float]) -> dict[str, Any]:
    started = now()
    run_id = _row_id(row)
    while True:
        current = view_run(runner, repository, run_id)
        if current.get("status") == "completed":
            validate_run(current, producer, sha, ref)
            return current
        _deadline_wait(started, deadline_seconds, now)
        sleep(poll_seconds)


def correlation_id(workflow: str) -> str:
    stem = Path(workflow).stem.replace("_", "-")
    return f"ac11-exact-sha/{stem}/{uuid.uuid4().hex}"


def dispatch_and_wait(runner: Runner, repository: str, ref: str, sha: str, producer: Producer,
                      baseline: list[dict[str, Any]], *, poll_seconds: float,
                      deadline_seconds: float, sleep: Callable[[float], None],
                      now: Callable[[], float], correlation_factory: Callable[[str], str]) \
        -> tuple[dict[str, Any], str | None]:
    ensure_remote_ref(runner, repository, ref, sha)
    baseline_id = max((_row_id(row) for row in baseline), default=0)
    correlation = correlation_factory(producer.workflow) if producer.correlation_supported else None
    args = [
        "gh", "workflow", "run", Path(producer.workflow).name,
        "--repo", repository, "--ref", ref,
    ]
    if correlation is not None:
        args += ["-f", f"correlation_id={correlation}"]
    command(runner, args, f"dispatch {producer.workflow}")
    started = now()
    run_id: int | None = None
    while True:
        rows = exact_rows(list_runs(runner, repository, ref, producer.workflow), producer, sha, ref)
        if correlation is not None:
            candidates = [row for row in rows if row.get("displayTitle") == correlation]
        else:
            candidates = [row for row in rows if _row_id(row) > baseline_id]
        if len(candidates) > 1:
            raise Refused(f"duplicate dispatched runs for {producer.workflow}")
        if candidates:
            run_id = _row_id(candidates[0])
            break
        _deadline_wait(started, deadline_seconds, now)
        sleep(poll_seconds)
    while True:
        current = view_run(runner, repository, run_id)
        if current.get("status") == "completed":
            validate_run(current, producer, sha, ref, correlation_id=correlation)
            return current, correlation
        _deadline_wait(started, deadline_seconds, now)
        sleep(poll_seconds)


def _artifact_digest(value: Any) -> str:
    if not isinstance(value, str) or not DIGEST_RE.fullmatch(value):
        raise Refused("artifact digest is not canonical sha256:<64hex>")
    return value


def artifact_for_run(runner: Runner, repository: str, run: dict[str, Any], expected_name: str,
                     sha: str, ref: str, *, now_utc: Callable[[], dt.datetime]) -> Artifact:
    run_id = _row_id(run)
    listing = command_json(
        runner,
        ["gh", "api", f"repos/{repository}/actions/runs/{run_id}/artifacts?per_page=100"],
        f"list run {run_id} artifacts",
    )
    rows = listing.get("artifacts") if isinstance(listing, dict) else None
    if not isinstance(rows, list):
        raise Refused(f"run {run_id} artifact listing has no artifacts array")
    matching = [row for row in rows if isinstance(row, dict) and row.get("name") == expected_name]
    if len(matching) != 1:
        raise Refused(f"run {run_id} must have exactly one artifact named {expected_name}")
    artifact_id = matching[0].get("id")
    if not isinstance(artifact_id, int) or isinstance(artifact_id, bool) or artifact_id <= 0:
        raise Refused(f"run {run_id} artifact id is invalid")
    detail = command_json(
        runner,
        ["gh", "api", f"repos/{repository}/actions/artifacts/{artifact_id}"],
        f"read artifact {artifact_id}",
    )
    if not isinstance(detail, dict) or detail.get("id") != artifact_id or detail.get("name") != expected_name:
        raise Refused(f"artifact {artifact_id} metadata identity differs")
    if detail.get("expired") is not False:
        raise Refused(f"artifact {artifact_id} is expired or has no expiry status")
    expires_at = detail.get("expires_at")
    if utc(expires_at, "artifact expires_at") <= now_utc().astimezone(dt.timezone.utc):
        raise Refused(f"artifact {artifact_id} has expired")
    digest = _artifact_digest(detail.get("digest"))
    binding = detail.get("workflow_run")
    if (
        not isinstance(binding, dict)
        or binding.get("id") != run_id
        or binding.get("head_sha") != sha
        or binding.get("head_branch") != ref
    ):
        raise Refused(f"artifact {artifact_id} is not bound to run {run_id}, source SHA and ref")
    archive = command(
        runner,
        ["gh", "api", f"repos/{repository}/actions/artifacts/{artifact_id}/zip"],
        f"download artifact {artifact_id}",
        timeout=600,
    )
    observed = "sha256:" + hashlib.sha256(archive).hexdigest()
    if observed != digest:
        raise Refused(f"artifact {artifact_id} downloaded digest differs from GitHub metadata")
    return Artifact(artifact_id, expected_name, digest, expires_at, archive)


def bind_producer(runner: Runner, repository: str, ref: str, sha: str, producer: Producer, *,
                  poll_seconds: float, deadline_seconds: float, sleep: Callable[[float], None],
                  now: Callable[[], float], now_utc: Callable[[], dt.datetime],
                  correlation_factory: Callable[[str], str]) -> BoundRun:
    rows = list_runs(runner, repository, ref, producer.workflow)
    exact = exact_rows(rows, producer, sha, ref)
    usable = usable_rows(exact)
    if len(usable) > 1:
        raise Refused(f"duplicate usable runs for {producer.workflow} at the exact SHA")
    if usable:
        current = wait_existing(
            runner, repository, usable[0], producer, sha, ref,
            poll_seconds=poll_seconds, deadline_seconds=deadline_seconds, sleep=sleep, now=now,
        )
        correlation = None
        reused = True
    else:
        current, correlation = dispatch_and_wait(
            runner, repository, ref, sha, producer, rows,
            poll_seconds=poll_seconds, deadline_seconds=deadline_seconds, sleep=sleep, now=now,
            correlation_factory=correlation_factory,
        )
        reused = False
    artifact = artifact_for_run(
        runner, repository, current, producer.artifact_prefix + sha, sha, ref, now_utc=now_utc
    )
    return BoundRun(producer, current, artifact, reused, correlation)


def _zip_documents(archive: bytes) -> dict[str, bytes]:
    try:
        handle = zipfile.ZipFile(io.BytesIO(archive))
    except zipfile.BadZipFile as exc:
        raise Refused("aggregate artifact is not a ZIP archive") from exc
    result: dict[str, bytes] = {}
    seen: set[str] = set()
    with handle:
        for info in handle.infolist():
            name = info.filename.replace("\\", "/")
            path = PurePosixPath(name)
            if name in seen:
                raise Refused(f"aggregate artifact has duplicate member {name!r}")
            seen.add(name)
            if path.is_absolute() or ".." in path.parts:
                raise Refused("aggregate artifact contains a path outside its archive")
            mode = (info.external_attr >> 16) & 0o170000
            if mode == 0o120000:
                raise Refused("aggregate artifact contains a symlink")
            if info.is_dir():
                continue
            base = path.name
            if base in {
                "ac11-checkout.json", "ac11-aggregate-manifest.json", "ac11-aggregate-result.json"
            }:
                if base in result:
                    raise Refused(f"aggregate artifact has two {base} members")
                result[base] = handle.read(info)
    expected = {"ac11-checkout.json", "ac11-aggregate-manifest.json", "ac11-aggregate-result.json"}
    if set(result) != expected:
        raise Refused("aggregate artifact lacks its checkout, manifest or result document")
    return result


def recompute(archive: bytes, sha: str, aggregate_run: dict[str, Any], correlation: str,
              producers: tuple[BoundRun, ...], root: Path = ROOT,
              now_utc: Callable[[], dt.datetime] = lambda: dt.datetime.now(dt.timezone.utc)) \
        -> dict[str, Any]:
    docs = _zip_documents(archive)
    checkout = strict_json(docs["ac11-checkout.json"], "aggregate checkout")
    required_checkout = {
        "schemaVersion": "ac11-aggregate-checkout:1",
        "sourceSha": sha,
        "checkoutSha": sha,
        "event": "workflow_dispatch",
        "runId": str(_row_id(aggregate_run)),
        "correlationId": correlation,
    }
    if checkout != required_checkout:
        raise Refused("aggregate checkout receipt differs from the dispatched run")
    manifest = strict_json(docs["ac11-aggregate-manifest.json"], "aggregate manifest")
    uploaded = strict_json(docs["ac11-aggregate-result.json"], "aggregate result")
    if not isinstance(manifest, dict) or manifest.get("releaseSha") != sha:
        raise Refused("aggregate manifest releaseSha differs from the exact source SHA")
    rows = manifest.get("axes")
    if not isinstance(rows, list) or not all(isinstance(row, dict) for row in rows):
        raise Refused("aggregate manifest axes are not an object list")
    by_axis: dict[str, dict[str, Any]] = {}
    for row in rows:
        axis = row.get("axis")
        if not isinstance(axis, str) or axis in by_axis:
            raise Refused("aggregate manifest has missing or duplicate axis names")
        by_axis[axis] = row
    for bound in producers:
        digest = bound.artifact.digest.removeprefix("sha256:")
        for axis in bound.producer.axes:
            row = by_axis.get(axis)
            if row is None:
                raise Refused(f"aggregate omitted complete source-map axis {axis}")
            if row.get("sourceHeadSha") != sha or str(row.get("sourceRunId")) != str(_row_id(bound.row)):
                raise Refused(f"aggregate axis {axis} is bound to another producer run")
            if row.get("artifactSha256") != digest or row.get("artifactObservedSha256") != digest:
                raise Refused(f"aggregate axis {axis} is bound to another producer artifact")
    allowlist_path = root / ALLOWLIST.relative_to(ROOT)
    allowlist_bytes = allowlist_path.read_bytes()
    blob = hashlib.sha1(f"blob {len(allowlist_bytes)}\0".encode() + allowlist_bytes).hexdigest()
    if blob != canonical.ALLOWLIST_BLOB:
        raise Refused("security allowlist file differs from the evaluator's reviewed Git blob")
    allowlist = strict_json(allowlist_bytes, "security allowlist")
    result = canonical.aggregate(
        manifest, canonical.RepositoryGit(root), allowlist, now=now_utc().astimezone(dt.timezone.utc)
    )
    if uploaded != result:
        raise Refused("uploaded aggregate result differs from canonical recomputation")
    return result


def _run_receipt(bound: BoundRun) -> dict[str, Any]:
    return {
        "workflow": bound.producer.workflow,
        "runId": _row_id(bound.row),
        "runAttempt": bound.row["attempt"],
        "event": bound.row["event"],
        "headSha": bound.row["headSha"],
        "artifactId": bound.artifact.artifact_id,
        "artifactName": bound.artifact.name,
        "artifactDigest": bound.artifact.digest,
        "artifactExpiresAt": bound.artifact.expires_at,
        "reused": bound.reused,
    }


def orchestrate(*, source: str, ref: str, repository: str, runner: Runner = real_runner,
                poll_seconds: float = 60.0, deadline_seconds: float = 7200.0,
                sleep: Callable[[float], None] = time.sleep,
                monotonic: Callable[[], float] = time.monotonic,
                now_utc: Callable[[], dt.datetime] = lambda: dt.datetime.now(dt.timezone.utc),
                correlation_factory: Callable[[str], str] = correlation_id,
                root: Path = ROOT) -> dict[str, Any]:
    sha = source_sha(source)
    branch = branch_name(ref)
    repo = repository_name(repository)
    started_at = now_utc()
    tree = local_checkout(runner, sha)
    ensure_remote_ref(runner, repo, branch, sha)
    producers = load_producers(root)
    bound = tuple(
        bind_producer(
            runner, repo, branch, sha, producer,
            poll_seconds=poll_seconds, deadline_seconds=deadline_seconds,
            sleep=sleep, now=monotonic, now_utc=now_utc,
            correlation_factory=correlation_factory,
        )
        for producer in producers
    )
    run_ids = [_row_id(item.row) for item in bound]
    artifact_ids = [item.artifact.artifact_id for item in bound]
    if len(run_ids) != len(set(run_ids)) or len(artifact_ids) != len(set(artifact_ids)):
        raise Refused("a producer run or artifact was reused for another workflow")

    # Recheck producer uniqueness after the last producer completed. A concurrent duplicate must
    # not be allowed to make the aggregate lane's `first success` selection ambiguous.
    for item in bound:
        rows = exact_rows(list_runs(runner, repo, branch, item.producer.workflow), item.producer, sha, branch)
        usable = usable_rows(rows)
        if len(usable) != 1 or _row_id(usable[0]) != _row_id(item.row):
            raise Refused(f"producer set changed before aggregation for {item.producer.workflow}")

    aggregate = Producer(AGGREGATE_WORKFLOW, AGGREGATE_ARTIFACT_PREFIX, (), True)
    ensure_remote_ref(runner, repo, branch, sha)
    aggregate_rows = list_runs(runner, repo, branch, aggregate.workflow)
    aggregate_correlation = correlation_factory(aggregate.workflow)
    baseline_id = max((_row_id(row) for row in aggregate_rows), default=0)
    command(
        runner,
        [
            "gh", "workflow", "run", Path(aggregate.workflow).name,
            "--repo", repo, "--ref", branch,
            "-f", f"source_sha={sha}",
            "-f", f"correlation_id={aggregate_correlation}",
        ],
        "dispatch aggregate workflow",
    )
    started = monotonic()
    aggregate_run: dict[str, Any] | None = None
    while aggregate_run is None:
        rows = exact_rows(list_runs(runner, repo, branch, aggregate.workflow), aggregate, sha, branch)
        candidates = [
            row for row in rows
            if _row_id(row) > baseline_id and row.get("displayTitle") == aggregate_correlation
        ]
        if len(candidates) > 1:
            raise Refused("duplicate aggregate runs carry this correlation id")
        if candidates:
            aggregate_run = candidates[0]
            break
        _deadline_wait(started, deadline_seconds, monotonic)
        sleep(poll_seconds)
    while aggregate_run.get("status") != "completed":
        aggregate_run = view_run(runner, repo, _row_id(aggregate_run))
        _deadline_wait(started, deadline_seconds, monotonic)
        if aggregate_run.get("status") != "completed":
            sleep(poll_seconds)
    validate_run(aggregate_run, aggregate, sha, branch, correlation_id=aggregate_correlation)
    if _row_id(aggregate_run) in run_ids:
        raise Refused("aggregate run id reuses a producer run id")
    aggregate_artifact = artifact_for_run(
        runner, repo, aggregate_run, AGGREGATE_ARTIFACT_PREFIX + sha, sha, branch,
        now_utc=now_utc,
    )
    if aggregate_artifact.artifact_id in artifact_ids:
        raise Refused("aggregate artifact id reuses a producer artifact id")
    result = recompute(
        aggregate_artifact.archive, sha, aggregate_run, aggregate_correlation, bound,
        root=root, now_utc=now_utc,
    )
    finished_at = now_utc()
    receipt = {
        "schemaVersion": SCHEMA_VERSION,
        "sourceSha": sha,
        "ref": branch,
        "repository": repo,
        "checkoutTreeSha": tree,
        "cleanCheckout": True,
        "startedAt": iso(started_at),
        "finishedAt": iso(finished_at),
        "producerRuns": [_run_receipt(item) for item in bound],
        "aggregateRun": {
            "workflow": aggregate.workflow,
            "runId": _row_id(aggregate_run),
            "runAttempt": aggregate_run["attempt"],
            "event": aggregate_run["event"],
            "headSha": aggregate_run["headSha"],
            "correlationId": aggregate_correlation,
            "artifactId": aggregate_artifact.artifact_id,
            "artifactName": aggregate_artifact.name,
            "artifactDigest": aggregate_artifact.digest,
            "artifactExpiresAt": aggregate_artifact.expires_at,
        },
        "dispatchedWorkflows": sorted(
            [item.producer.workflow for item in bound if not item.reused] + [aggregate.workflow]
        ),
        "canonicalResult": result,
        "promotesScore": False,
        "secretsRequired": False,
    }
    rendered = json.dumps(receipt, ensure_ascii=False, sort_keys=True)
    assert_no_secrets(rendered)
    return receipt


def parser() -> argparse.ArgumentParser:
    result = argparse.ArgumentParser(description=__doc__)
    result.add_argument("--source-sha", required=True)
    result.add_argument("--ref", required=True, help="remote branch that must still point at source SHA")
    result.add_argument("--repository", default=os.environ.get("GITHUB_REPOSITORY", "egparadise/SaintVision-Invion"))
    result.add_argument("--output", type=Path, required=True)
    result.add_argument("--poll-seconds", type=float, default=60.0)
    result.add_argument("--deadline-seconds", type=float, default=7200.0)
    return result


def main(argv: list[str] | None = None, runner: Runner = real_runner) -> int:
    args = parser().parse_args(argv)
    if args.poll_seconds < 0 or args.deadline_seconds <= 0:
        print("refused: polling values are outside their allowed range", file=sys.stderr)
        return 2
    try:
        receipt = orchestrate(
            source=args.source_sha,
            ref=args.ref,
            repository=args.repository,
            runner=runner,
            poll_seconds=args.poll_seconds,
            deadline_seconds=args.deadline_seconds,
        )
        rendered = json.dumps(receipt, ensure_ascii=False, indent=2, sort_keys=True) + "\n"
        assert_no_secrets(rendered)
        args.output.parent.mkdir(parents=True, exist_ok=True)
        temporary = args.output.with_suffix(args.output.suffix + ".tmp")
        temporary.write_text(rendered, encoding="utf-8")
        temporary.replace(args.output)
        print(rendered, end="")
        return 0
    except (Refused, OSError, subprocess.SubprocessError, ValueError) as exc:
        # The refusal names only the boundary and identifiers this tool created. Command stderr,
        # artifact bodies and environment values are deliberately excluded.
        print(f"refused: {exc}", file=sys.stderr)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
