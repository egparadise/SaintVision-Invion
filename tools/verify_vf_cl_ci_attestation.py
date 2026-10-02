"""Verify the signed VF-CL receipt against GitHub's Sigstore identity and exact source.

No bundle means no verification.  The verifier never accepts a receipt-shaped JSON as a
substitute: it asks ``gh attestation verify`` to validate the signature, repository,
signer workflow, source commit and branch, then independently binds the verified subject
digest to the exact receipt bytes.
"""

from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path
import subprocess
from typing import Any, Callable

try:
    from tools import create_vf_cl_ci_attestation_receipt as receipt_contract
except ModuleNotFoundError:  # Direct ``python tools/...py`` execution in Actions.
    import create_vf_cl_ci_attestation_receipt as receipt_contract


class AttestationError(ValueError):
    pass


Runner = Callable[..., subprocess.CompletedProcess[str]]


def _strict_object(pairs: list[tuple[str, Any]]) -> dict[str, Any]:
    result: dict[str, Any] = {}
    for key, value in pairs:
        if key in result:
            raise AttestationError(f"duplicate JSON key {key!r}")
        result[key] = value
    return result


def load_receipt(path: Path) -> dict[str, Any]:
    try:
        value = json.loads(path.read_text(encoding="utf-8"), object_pairs_hook=_strict_object)
    except (OSError, UnicodeError, json.JSONDecodeError) as error:
        raise AttestationError(f"receipt is unavailable or invalid: {type(error).__name__}") from None
    if not isinstance(value, dict) or set(value) != receipt_contract.RECEIPT_KEYS:
        raise AttestationError("receipt key set is not exact")
    if value.get("schemaVersion") != receipt_contract.SCHEMA:
        raise AttestationError("receipt schema is not authoritative")
    if set(value.get("producerJob") or {}) != receipt_contract.PRODUCER_KEYS:
        raise AttestationError("producerJob key set is not exact")
    if set(value.get("evidenceArtifact") or {}) != receipt_contract.ARTIFACT_KEYS:
        raise AttestationError("evidenceArtifact key set is not exact")
    if value.get("receiptSha256") != receipt_contract.canonical_digest(value):
        raise AttestationError("receipt canonical digest does not match")
    return value


def verified_subjects(result: Any) -> list[dict[str, Any]]:
    if not isinstance(result, list) or not result:
        raise AttestationError("gh returned no verified attestation")
    subjects: list[dict[str, Any]] = []
    for row in result:
        try:
            statement = row["verificationResult"]["statement"]
            predicate_type = statement["predicateType"]
            row_subjects = statement["subject"]
        except (KeyError, TypeError):
            raise AttestationError("gh verification output has an unknown shape") from None
        if predicate_type != "https://slsa.dev/provenance/v1":
            raise AttestationError("verified attestation is not SLSA provenance v1")
        if not isinstance(row_subjects, list):
            raise AttestationError("verified attestation has no subject array")
        subjects.extend(subject for subject in row_subjects if isinstance(subject, dict))
    return subjects


def verify(receipt_path: Path, bundle_path: Path, *, expected_repository: str,
           expected_workflow: str, expected_head: str, expected_ref: str,
           output_path: Path | None = None, runner: Runner = subprocess.run) -> dict[str, Any]:
    if not bundle_path.is_file():
        raise AttestationError("attestation bundle is missing")
    receipt = load_receipt(receipt_path)
    for field, actual, expected in (
        ("repository", receipt.get("repository"), expected_repository),
        ("workflowPath", receipt.get("workflowPath"), expected_workflow),
        ("headSha", receipt.get("headSha"), expected_head),
        ("headRef", receipt.get("headRef"), expected_ref),
    ):
        if actual != expected:
            raise AttestationError(f"receipt {field} is {actual!r}, expected {expected!r}")
    signer = f"{expected_repository}/{expected_workflow}"
    command = [
        "gh", "attestation", "verify", str(receipt_path),
        "--repo", expected_repository,
        "--bundle", str(bundle_path),
        "--signer-workflow", signer,
        "--source-digest", expected_head,
        "--source-ref", expected_ref,
        "--deny-self-hosted-runners",
        "--format", "json",
    ]
    # ``text=True`` alone decodes with the host's locale encoding, which is **not** UTF-8 on a
    # default Windows console (cp949 here).  ``gh attestation verify --format json`` emits UTF-8,
    # so the locale default raised ``UnicodeDecodeError`` and the verification never ran -- found
    # by review on this PC (#339 r1 F1).  The encoding is therefore stated, not inherited, and a
    # byte sequence that is not UTF-8 is an explicit refusal rather than a traceback.
    try:
        completed = runner(
            command, capture_output=True, text=True, encoding="utf-8", errors="strict"
        )
    except UnicodeDecodeError:
        raise AttestationError("gh verification output is not valid UTF-8") from None
    if completed.returncode != 0:
        raise AttestationError("GitHub attestation signature or identity verification failed")
    # A runner that did not capture stdout leaves it ``None``; ``json.loads(None)`` is a
    # ``TypeError``, which exits 1 with a traceback instead of saying what was wrong.
    if not isinstance(completed.stdout, str) or not completed.stdout.strip():
        raise AttestationError("gh verification produced no output to verify")
    try:
        verification = json.loads(completed.stdout, object_pairs_hook=_strict_object)
    except (json.JSONDecodeError, AttestationError):
        raise AttestationError("gh verification output is invalid JSON") from None
    digest = hashlib.sha256(receipt_path.read_bytes()).hexdigest()
    expected_name = receipt_path.name
    matched = False
    for subject in verified_subjects(verification):
        sha = subject.get("digest")
        if subject.get("name") == expected_name and isinstance(sha, dict) \
                and sha.get("sha256") == digest and set(sha) == {"sha256"}:
            matched = True
            break
    if not matched:
        raise AttestationError("verified subjects do not bind the exact receipt bytes")
    if output_path is not None:
        output_path.parent.mkdir(parents=True, exist_ok=True)
        output_path.write_text(json.dumps(verification, ensure_ascii=False, indent=2) + "\n",
                               encoding="utf-8")
    return receipt


def parser() -> argparse.ArgumentParser:
    result = argparse.ArgumentParser(description=__doc__)
    result.add_argument("--receipt", type=Path, required=True)
    result.add_argument("--bundle", type=Path, required=True)
    result.add_argument("--expected-repository", default=receipt_contract.REPOSITORY)
    result.add_argument("--expected-workflow", default=receipt_contract.WORKFLOW_PATH)
    result.add_argument("--expected-head", required=True)
    result.add_argument("--expected-ref", required=True)
    result.add_argument("--output", type=Path)
    return result


def main(argv: list[str] | None = None) -> int:
    args = parser().parse_args(argv)
    try:
        receipt = verify(
            args.receipt, args.bundle,
            expected_repository=args.expected_repository,
            expected_workflow=args.expected_workflow,
            expected_head=args.expected_head,
            expected_ref=args.expected_ref,
            output_path=args.output,
        )
    except AttestationError as error:
        print(f"refused: {error}")
        return 2
    print(json.dumps({
        "status": "VERIFIED", "runId": receipt["runId"],
        "headSha": receipt["headSha"], "receiptSha256": receipt["receiptSha256"],
    }, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
