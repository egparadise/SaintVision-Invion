#!/usr/bin/env python3
"""Find the browser lane's run and artifact for one source SHA and write the evidence document.

Why this exists: the AC-11 aggregate lane imported the security artifact with three arguments and
never passed the browser lane's artifact, so ``SEC-VF-001`` was absent from every envelope that
lane produced -- measured in #319 r2 and recorded in the v1.12 rescore.  This tool is the missing
discovery step (card 233).

What it does, and deliberately only this:

* reads **which** workflow and **which** artifact name from the reviewed sources -- the allowlist's
  ``secVf001.workflow.path`` and the importer's ``VF_ARTIFACT_NAME`` -- so this file adds no second
  definition of the browser lane's identity;
* enumerates the population GitHub actually has **at that commit** and pages to the end, refusing
  a listing it cannot prove complete -- a truncated window could hide the inconvenient candidate;
* requires the candidates to be **one piece of evidence**: successful runs of that workflow at
  that source SHA from an approved event, each with one artifact of the reviewed name.  Zero is an
  answer ("no evidence at this SHA").  Several are accepted **only when their proofs agree on every
  field the report asserts** (``importer.VF_DECISIVE_FIELDS``) -- then choosing between them is not
  a choice, and the lowest run id is taken so the result is reproducible.  Any disagreement is a
  refusal, never a pick.  Measured on the lane (card 233): pushing a branch and dispatching the
  browser lane leaves two successful runs at one head, an "exactly one" rule dropped SEC-VF-001
  from the envelope whenever that happened (aggregate run 36993502607), and comparing the artifact
  *digests* would not have helped -- runs 36993192700 and 36993193630 differ by a fresh run uuid,
  two timestamps, the paths built from that uuid and a JUnit digest whose durations differ, while
  every decisive field is identical;
* downloads the three inputs and writes an ``ac11-vf-evidence:1`` document naming them.

What it does **not** do: verify the run and artifact.  That is ``import_ac11_security_scan``'s
``vf_report`` -- head, tree from ``head_commit``, repository, workflow, event, conclusion, artifact
name, digest recomputed from the bytes, expiry -- and duplicating it here would make two
definitions of one rule.  This tool hands the importer three files; the importer decides.

Exit codes: 0 wrote the document; 3 no single candidate (the reason is on stderr, and the caller
should continue without ``SEC-VF-001`` rather than fail); 2 the environment or ``gh`` failed.
"""

from __future__ import annotations

import argparse
import json
import subprocess
import sys
from pathlib import Path
from typing import Any

REPO_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO_ROOT / "tools"))

import import_ac11_security_scan as importer  # noqa: E402

#: The events a VF run may come from.  The browser lane's attestation-grade inputs are only
#: produced on an explicit opt-in, which is the same set the importer accepts.
APPROVED_EVENTS = ("workflow_dispatch", "pull_request")
#: How the population is enumerated.  ``gh run list --limit 50`` was a silent truncation: it
#: returns the repository's most recent fifty runs of one workflow and the SHA filter was applied
#: *after* that, so a conflicting older run at the same commit could sit outside the window while a
#: newer one sat inside -- "do not pick the convenient candidate" with the inconvenient one unseen
#: (#332 r3 F2).  The REST endpoint takes the commit itself, states ``total_count``, and carries
#: each run's ``path``; this tool pages to the end and refuses anything it cannot enumerate whole.
RUNS_PER_PAGE = 100
#: GitHub serves at most 1000 results from a listing endpoint, so a larger population cannot be
#: proved complete and is a refusal rather than a shorter list.
MAX_RUN_PAGES = 10
ARCHIVE_NAME = "vf-archive.zip"
RUN_METADATA_NAME = "vf-run.json"
ARTIFACT_METADATA_NAME = "vf-artifact.json"
DOCUMENT_NAME = "vf-evidence.json"


class NoSingleCandidate(RuntimeError):
    """Zero or more than one candidate: not an error of this tool, but not evidence either."""


def _gh(*args: str) -> str:
    """One text answer from ``gh``.  The two callers of the CLI live here and nowhere else."""

    result = subprocess.run(
        ["gh", *args], capture_output=True, text=True, timeout=120, cwd=REPO_ROOT
    )
    if result.returncode != 0:
        raise RuntimeError(f"gh {' '.join(args)} failed: {result.stderr.strip()[:200]}")
    return result.stdout


def _gh_bytes(*args: str) -> bytes:
    """The artifact zip, as bytes.  Separate from ``_gh`` because text mode would corrupt it."""

    result = subprocess.run(["gh", *args], capture_output=True, timeout=300, cwd=REPO_ROOT)
    if result.returncode != 0 or not result.stdout:
        raise RuntimeError(f"gh {' '.join(args)} returned no bytes")
    return result.stdout


def runs_at_head(source_sha: str, fetch) -> list[dict[str, Any]]:
    """Every workflow run GitHub has at that exact commit, enumerated to the end.

    ``fetch(page)`` returns one page of ``GET /repos/{repo}/actions/runs?head_sha=...``.  The
    population is only usable if it is **complete**, so what GitHub states (``total_count``) is
    compared with what was actually listed: a page that stops early, a page that is not a list, and
    a population larger than the listing endpoint will serve are all refusals.  A short list would
    otherwise be indistinguishable from "there is no other candidate" (#332 r3 F2).
    """

    collected: list[dict[str, Any]] = []
    stated: int | None = None
    for page in range(1, MAX_RUN_PAGES + 1):
        payload = fetch(page)
        if not isinstance(payload, dict):
            raise RuntimeError("the runs response is not an object")
        total = payload.get("total_count")
        if not isinstance(total, int) or isinstance(total, bool) or total < 0:
            raise RuntimeError("the runs response states no usable total_count")
        rows = payload.get("workflow_runs")
        if not isinstance(rows, list):
            raise RuntimeError("the runs response carries no workflow_runs list")
        if stated is None:
            stated = total
            if stated > RUNS_PER_PAGE * MAX_RUN_PAGES:
                raise NoSingleCandidate(
                    f"GitHub states {stated} runs at {source_sha}, more than the "
                    f"{RUNS_PER_PAGE * MAX_RUN_PAGES} a listing can enumerate"
                )
        elif total != stated:
            raise NoSingleCandidate(
                f"the run population changed while it was being listed ({stated} then {total})"
            )
        collected.extend(row for row in rows if isinstance(row, dict))
        if len(collected) >= stated or not rows:
            break
    if stated is None or len(collected) != stated:
        raise NoSingleCandidate(
            f"GitHub states {stated} runs at {source_sha} but {len(collected)} could be listed; "
            f"a truncated population is not evidence"
        )
    return collected


def candidate_runs(rows: Any, source_sha: str, workflow_path: str) -> list[int]:
    """Every successful run of that workflow at that SHA from an approved event, by id.

    The rows come from the REST listing, whose run objects do carry ``path`` (``gh run list
    --json`` does not -- measured: it refuses the name and prints the fifteen fields it has).  The
    workflow path is still **verified by the importer** against the reviewed allowlist, from the run
    metadata this tool downloads, so selecting on it here adds no second definition of "the reviewed
    workflow"; it only keeps other lanes' runs at the same commit out of the population.
    """

    if not isinstance(rows, list):
        raise RuntimeError("the run population is not a list")
    found = []
    for row in rows:
        if not isinstance(row, dict):
            continue
        if (
            row.get("head_sha") != source_sha
            or str(row.get("path", "")).split("@", 1)[0] != workflow_path
            or row.get("status") != "completed"
            or row.get("conclusion") != "success"
            or row.get("event") not in APPROVED_EVENTS
        ):
            continue
        run_id = row.get("id")
        if not isinstance(run_id, int) or isinstance(run_id, bool) or run_id <= 0:
            raise NoSingleCandidate("a matching run has no usable id")
        found.append(run_id)
    if not found:
        raise NoSingleCandidate(
            f"no successful {workflow_path} run at {source_sha} from {list(APPROVED_EVENTS)}"
        )
    return sorted(set(found))


def select_evidence(
    run_ids: list[int], artifacts_of, archive_of, name: str
) -> tuple[int, dict[str, Any]]:
    """(run id, artifact) for the one piece of evidence those runs carry.

    Several runs at one head are ordinary -- pushing the branch and dispatching the lane both run
    it -- so the question is not "how many runs" but "do they say the same thing".  Byte equality
    cannot answer it: two such runs differ by a fresh run uuid, two timestamps, the paths built
    from that uuid and the digest of a JUnit file whose durations differ (measured on runs
    36993192700 and 36993193630 at one head), so their artifact digests always differ.  What the
    report asserts is ``importer.VF_DECISIVE_FIELDS`` -- the fields ``vf_report`` checks against the
    reviewed allowlist and records -- and those are compared here, read out of each candidate's own
    archive.  All equal: one piece of evidence, and the lowest run id is taken so the answer is
    reproducible; the importer then verifies that run in full.  Any difference is a refusal, because
    choosing which of two observations to believe is not this tool's job (card 233).
    """

    ordered = sorted(set(run_ids))
    chosen_id = ordered[0]
    chosen = select_artifact(artifacts_of(chosen_id), name)
    if len(ordered) == 1:
        return chosen_id, chosen
    try:
        decisive = importer.vf_decisive(
            importer.vf_proof_of_archive(archive_of(chosen_id)), f"run {chosen_id}"
        )
        for run_id in ordered[1:]:
            # Each candidate must also carry exactly one artifact of that name, or its evidence
            # cannot be compared at all.
            select_artifact(artifacts_of(run_id), name)
            other = importer.vf_decisive(
                importer.vf_proof_of_archive(archive_of(run_id)), f"run {run_id}"
            )
            differing = [field for field in decisive if decisive[field] != other[field]]
            if differing:
                raise NoSingleCandidate(
                    f"runs {chosen_id} and {run_id} disagree about "
                    f"{', '.join(sorted(differing))}; this tool does not choose between them"
                )
    except importer.SecurityImportError as unusable:
        raise NoSingleCandidate(str(unusable)) from None
    return chosen_id, chosen


def select_artifact(payload: Any, name: str) -> dict[str, Any]:
    """The one artifact of that name in the run."""

    artifacts = payload.get("artifacts") if isinstance(payload, dict) else None
    if not isinstance(artifacts, list):
        raise RuntimeError("the artifacts response carries no artifacts list")
    matching = [
        row for row in artifacts if isinstance(row, dict) and row.get("name") == name
    ]
    if len(matching) != 1:
        raise NoSingleCandidate(
            f"expected exactly 1 artifact named {name}, found {len(matching)}"
        )
    artifact_id = matching[0].get("id")
    if not isinstance(artifact_id, int) or isinstance(artifact_id, bool) or artifact_id <= 0:
        raise NoSingleCandidate("the matching artifact has no usable id")
    return matching[0]


def document(run_id: int, artifact_id: int, workflow_path: str) -> dict[str, Any]:
    return {
        "schemaVersion": importer.VF_EVIDENCE_SCHEMA,
        "repository": importer.REPOSITORY,
        "workflowPath": workflow_path,
        "runId": str(run_id),
        "artifactId": str(artifact_id),
        "archive": ARCHIVE_NAME,
        "runMetadata": RUN_METADATA_NAME,
        "artifactMetadata": ARTIFACT_METADATA_NAME,
    }


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--source-sha", required=True)
    parser.add_argument("--out-dir", type=Path, required=True)
    args = parser.parse_args(argv)
    if not importer.SHA1_RE.fullmatch(args.source_sha):
        print("--source-sha must be a 40-character lowercase Git SHA", file=sys.stderr)
        return 2
    try:
        workflow_path = importer._reviewed_allowlist()["secVf001"]["workflow"]["path"]
    except Exception as error:  # the reviewed allowlist is the one source of this name
        print(f"the reviewed allowlist is unusable: {error}", file=sys.stderr)
        return 2
    repository = importer.REPOSITORY
    def fetch_runs(page: int) -> Any:
        return json.loads(
            _gh(
                "api", "-X", "GET", f"repos/{repository}/actions/runs",
                "-f", f"head_sha={args.source_sha}",
                "-f", f"per_page={RUNS_PER_PAGE}", "-f", f"page={page}",
            )
            or "{}"
        )

    try:
        rows = runs_at_head(args.source_sha, fetch_runs)
        run_ids = candidate_runs(rows, args.source_sha, workflow_path)

        artifacts: dict[int, Any] = {}
        archives: dict[int, bytes] = {}

        def artifacts_of(candidate: int) -> Any:
            if candidate not in artifacts:
                artifacts[candidate] = json.loads(
                    _gh("api", f"repos/{repository}/actions/runs/{candidate}/artifacts") or "{}"
                )
            return artifacts[candidate]

        def archive_of(candidate: int) -> bytes:
            # Only reached when there is more than one candidate, and memoised by artifact id so
            # the chosen archive is downloaded once however often it is read.
            artifact_of_candidate = select_artifact(
                artifacts_of(candidate), importer.VF_ARTIFACT_NAME
            )
            key = int(artifact_of_candidate["id"])
            if key not in archives:
                archives[key] = _gh_bytes(
                    "api", f"repos/{repository}/actions/artifacts/{key}/zip"
                )
            return archives[key]

        run_id, artifact = select_evidence(
            run_ids, artifacts_of, archive_of, importer.VF_ARTIFACT_NAME
        )
        artifact_id = int(artifact["id"])
    except NoSingleCandidate as reason:
        print(f"no browser lane evidence at {args.source_sha}: {reason}", file=sys.stderr)
        return 3
    except (RuntimeError, json.JSONDecodeError, OSError) as error:
        print(f"browser lane discovery failed: {error}", file=sys.stderr)
        return 2

    args.out_dir.mkdir(parents=True, exist_ok=True)
    try:
        (args.out_dir / RUN_METADATA_NAME).write_text(
            _gh("api", f"repos/{repository}/actions/runs/{run_id}"), encoding="utf-8"
        )
        (args.out_dir / ARTIFACT_METADATA_NAME).write_text(
            _gh("api", f"repos/{repository}/actions/artifacts/{artifact_id}"), encoding="utf-8"
        )
        (args.out_dir / ARCHIVE_NAME).write_bytes(
            archives.get(artifact_id)
            or _gh_bytes("api", f"repos/{repository}/actions/artifacts/{artifact_id}/zip")
        )
    except (RuntimeError, OSError, subprocess.SubprocessError) as error:
        print(f"browser lane download failed: {error}", file=sys.stderr)
        return 2

    target = args.out_dir / DOCUMENT_NAME
    target.write_text(
        json.dumps(document(run_id, artifact_id, workflow_path), indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    print(str(target))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
