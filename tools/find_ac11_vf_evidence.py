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
* requires **exactly one** candidate at every step: one successful run of that workflow at that
  source SHA from an approved event, and one artifact of that name in it.  Zero is an answer
  ("no evidence at this SHA") and two is a refusal, never a pick;
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


def select_run(rows: Any, source_sha: str, workflow_path: str) -> dict[str, Any]:
    """The one run of that workflow at that SHA which finished successfully.

    ``gh run list --json`` has no ``path`` field (measured: it refuses the name and prints the
    fifteen it has), so the workflow is selected by the ``--workflow`` argument here and the
    **path itself is verified by the importer** against the reviewed allowlist, from the run
    metadata this tool downloads.  That keeps one definition of "the reviewed workflow".
    """

    if not isinstance(rows, list):
        raise RuntimeError("gh run list did not return a list")
    matching = [
        row for row in rows
        if isinstance(row, dict)
        and row.get("headSha") == source_sha
        and row.get("status") == "completed"
        and row.get("conclusion") == "success"
        and row.get("event") in APPROVED_EVENTS
    ]
    if len(matching) != 1:
        raise NoSingleCandidate(
            f"expected exactly 1 successful {workflow_path} run at {source_sha} from "
            f"{list(APPROVED_EVENTS)}, found {len(matching)}"
        )
    run_id = matching[0].get("databaseId")
    if not isinstance(run_id, int) or isinstance(run_id, bool) or run_id <= 0:
        raise NoSingleCandidate("the matching run has no usable databaseId")
    return matching[0]


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
    try:
        rows = json.loads(
            _gh(
                "run", "list", "--workflow", workflow_path.rsplit("/", 1)[-1], "--limit", "50",
                "--json", "databaseId,headSha,status,conclusion,event",
            )
            or "[]"
        )
        run = select_run(rows, args.source_sha, workflow_path)
        run_id = int(run["databaseId"])
        payload = json.loads(
            _gh("api", f"repos/{repository}/actions/runs/{run_id}/artifacts") or "{}"
        )
        artifact = select_artifact(payload, importer.VF_ARTIFACT_NAME)
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
            _gh_bytes("api", f"repos/{repository}/actions/artifacts/{artifact_id}/zip")
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
