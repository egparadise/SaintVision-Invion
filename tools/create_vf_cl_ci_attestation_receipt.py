"""Create the VF-CL-04 receipt inside its authoritative GitHub Actions run.

This is deliberately not the offline recorder.  Every run/repository/ref value comes from
GitHub's runner environment and the evidence artifact is selected from the current run's
Actions API response.  The resulting file is still only data until ``actions/attest`` signs
its digest; ``verify_vf_cl_ci_attestation.py`` is the trust boundary.
"""

from __future__ import annotations

import argparse
import datetime as dt
import hashlib
import json
import os
from pathlib import Path
import re
from typing import Any


SCHEMA = "vf-cl-ci-attestation-receipt:1"
REPOSITORY = "egparadise/SaintVision-Invion"
WORKFLOW_PATH = ".github/workflows/s12-acceptance-evidence.yml"
CARD = "VF-CL-04"
SHA = re.compile(r"^[0-9a-f]{40}$")
ARTIFACT_DIGEST = re.compile(r"^sha256:[0-9a-f]{64}$")
RECEIPT_KEYS = frozenset({
    "schemaVersion", "card", "repository", "workflowPath", "runId", "runAttempt",
    "event", "headSha", "headRef", "producerJob", "requiredSteps", "evidenceArtifact",
    "recordedAt", "receiptSha256",
})
PRODUCER_KEYS = frozenset({"name", "conclusion"})
ARTIFACT_KEYS = frozenset({"id", "name", "digest", "createdAt", "expiresAt"})
UNDIGESTED = frozenset({"recordedAt", "receiptSha256"})


class ReceiptError(ValueError):
    pass


def _strict_object(pairs: list[tuple[str, Any]]) -> dict[str, Any]:
    result: dict[str, Any] = {}
    for key, value in pairs:
        if key in result:
            raise ReceiptError(f"duplicate JSON key {key!r}")
        result[key] = value
    return result


def load_json(path: Path) -> dict[str, Any]:
    try:
        value = json.loads(path.read_text(encoding="utf-8"), object_pairs_hook=_strict_object)
    except (OSError, UnicodeError, json.JSONDecodeError) as error:
        raise ReceiptError(f"artifact metadata is unreadable: {type(error).__name__}") from None
    if not isinstance(value, dict):
        raise ReceiptError("artifact metadata must be an object")
    return value


def canonical_digest(receipt: dict[str, Any]) -> str:
    body = {key: value for key, value in receipt.items() if key not in UNDIGESTED}
    encoded = json.dumps(
        body, sort_keys=True, separators=(",", ":"), ensure_ascii=False
    ).encode("utf-8")
    return hashlib.sha256(encoded).hexdigest()


def _utc(value: Any, field: str) -> str:
    if not isinstance(value, str) or not value.endswith("Z"):
        raise ReceiptError(f"artifact {field} must be a UTC RFC3339 timestamp")
    try:
        parsed = dt.datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError:
        raise ReceiptError(f"artifact {field} must be a UTC RFC3339 timestamp") from None
    if parsed.utcoffset() != dt.timedelta(0):
        raise ReceiptError(f"artifact {field} must be UTC")
    return value


def select_artifact(metadata: dict[str, Any], *, artifact_id: str, artifact_name: str,
                    run_id: str, head_sha: str) -> dict[str, str]:
    artifacts = metadata.get("artifacts")
    if not isinstance(artifacts, list):
        raise ReceiptError("artifact metadata needs an artifacts array")
    matches = [row for row in artifacts if isinstance(row, dict)
               and str(row.get("id")) == artifact_id and row.get("name") == artifact_name]
    if len(matches) != 1:
        raise ReceiptError("current run must expose exactly one named evidence artifact")
    row = matches[0]
    workflow_run = row.get("workflow_run")
    if not isinstance(workflow_run, dict) or str(workflow_run.get("id")) != run_id:
        raise ReceiptError("evidence artifact does not belong to the current run")
    if workflow_run.get("head_sha") != head_sha:
        raise ReceiptError("evidence artifact is not bound to the current head")
    if row.get("expired") is not False:
        raise ReceiptError("evidence artifact is expired or expiry is unknown")
    digest = row.get("digest")
    if not isinstance(digest, str) or not ARTIFACT_DIGEST.fullmatch(digest):
        raise ReceiptError("evidence artifact digest is missing or malformed")
    return {
        "id": artifact_id,
        "name": artifact_name,
        "digest": digest,
        "createdAt": _utc(row.get("created_at"), "created_at"),
        "expiresAt": _utc(row.get("expires_at"), "expires_at"),
    }


def build_receipt(*, metadata: dict[str, Any], artifact_id: str, artifact_name: str,
                  repository: str, run_id: str, run_attempt: str, event: str,
                  head_sha: str, head_ref: str, producer_conclusion: str,
                  required_steps: list[str], now: dt.datetime | None = None) -> dict[str, Any]:
    if repository != REPOSITORY:
        raise ReceiptError(f"repository must be {REPOSITORY}")
    if not run_id.isdigit() or not run_attempt.isdigit():
        raise ReceiptError("run id and attempt must be decimal strings")
    if event != "workflow_dispatch":
        raise ReceiptError("authoritative receipt generation is workflow_dispatch-only")
    if not SHA.fullmatch(head_sha):
        raise ReceiptError("head SHA must be a full lowercase commit")
    if not head_ref.startswith("refs/heads/"):
        raise ReceiptError("head ref must be a branch ref")
    if producer_conclusion != "success":
        raise ReceiptError("the producer job did not succeed")
    if not required_steps or len(required_steps) != len(set(required_steps)) or not all(
        isinstance(step, str) and step.strip() for step in required_steps
    ):
        raise ReceiptError("required steps must be a non-empty unique string list")
    moment = now or dt.datetime.now(dt.timezone.utc)
    if moment.tzinfo is None:
        raise ReceiptError("recordedAt source must be timezone-aware")
    receipt: dict[str, Any] = {
        "schemaVersion": SCHEMA,
        "card": CARD,
        "repository": repository,
        "workflowPath": WORKFLOW_PATH,
        "runId": run_id,
        "runAttempt": run_attempt,
        "event": event,
        "headSha": head_sha,
        "headRef": head_ref,
        "producerJob": {"name": "s12-acceptance-evidence", "conclusion": producer_conclusion},
        "requiredSteps": required_steps,
        "evidenceArtifact": select_artifact(
            metadata, artifact_id=artifact_id, artifact_name=artifact_name,
            run_id=run_id, head_sha=head_sha,
        ),
        "recordedAt": moment.astimezone(dt.timezone.utc).isoformat().replace("+00:00", "Z"),
    }
    receipt["receiptSha256"] = canonical_digest(receipt)
    return receipt


def parser() -> argparse.ArgumentParser:
    result = argparse.ArgumentParser(description=__doc__)
    result.add_argument("--artifact-metadata", type=Path, required=True)
    result.add_argument("--artifact-id", required=True)
    result.add_argument("--artifact-name", required=True)
    result.add_argument("--producer-conclusion", required=True)
    result.add_argument("--required-step", action="append", required=True)
    result.add_argument("--out", type=Path, required=True)
    return result


def main(argv: list[str] | None = None) -> int:
    args = parser().parse_args(argv)
    try:
        receipt = build_receipt(
            metadata=load_json(args.artifact_metadata),
            artifact_id=args.artifact_id,
            artifact_name=args.artifact_name,
            repository=os.environ.get("GITHUB_REPOSITORY", ""),
            run_id=os.environ.get("GITHUB_RUN_ID", ""),
            run_attempt=os.environ.get("GITHUB_RUN_ATTEMPT", ""),
            event=os.environ.get("GITHUB_EVENT_NAME", ""),
            head_sha=os.environ.get("SOURCE_HEAD_SHA", ""),
            head_ref=os.environ.get("GITHUB_REF", ""),
            producer_conclusion=args.producer_conclusion,
            required_steps=args.required_step,
        )
        args.out.parent.mkdir(parents=True, exist_ok=True)
        args.out.write_text(json.dumps(receipt, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    except ReceiptError as error:
        print(f"refused: {error}")
        return 2
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
