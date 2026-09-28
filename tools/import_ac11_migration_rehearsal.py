"""Import a downloaded migration rehearsal artifact into AC-11 axis envelopes.

The rehearsal cannot include the GitHub artifact digest in the artifact whose
digest is being computed.  This importer therefore runs after download and
binds the immutable GitHub artifact metadata to the redacted producer report.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import re
import subprocess
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[1]
REGISTRY_PATH = "docs/vault/30_Development/Evidence/s11-ac11-target-registry-v0.json"
REGISTRY_BLOB = "99e64cb4125d47ae681a2e8e7c8f76c05193a892"
TARGET_ID = "s11-irreversible-restore-forward-v0"
HEX40 = re.compile(r"^[0-9a-f]{40}$")
HEX64 = re.compile(r"^[0-9a-f]{64}$")


class ImportError(ValueError):
    """Fail-closed artifact import error."""


def _git(*args: str) -> str:
    result = subprocess.run(
        ["git", *args], cwd=ROOT, text=True, capture_output=True, encoding="utf-8"
    )
    if result.returncode:
        raise ImportError("Git provenance is unreachable")
    return result.stdout.strip()


def _utc(value: Any, field: str) -> str:
    if not isinstance(value, str):
        raise ImportError(f"{field} must be a UTC RFC3339 string")
    try:
        parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError as exc:
        raise ImportError(f"{field} must be a UTC RFC3339 string") from exc
    if parsed.tzinfo is None or parsed.utcoffset() != timezone.utc.utcoffset(parsed):
        raise ImportError(f"{field} must be UTC")
    return parsed.isoformat().replace("+00:00", "Z")


def _artifact_digest(value: str) -> str:
    normalized = value.removeprefix("sha256:")
    if not HEX64.fullmatch(normalized):
        raise ImportError("artifact digest must be a full SHA-256")
    return normalized


def _observation(metric: str, value: int) -> dict[str, Any]:
    return {
        "metric": metric,
        "value": value,
        "unit": "count",
        "n": 1,
        "successCount": 1,
        "failureCount": 0,
        "skipCount": 0,
        "errorsByClass": {},
    }


def import_report(
    report: dict[str, Any], *, artifact_digest: str, artifact_expires_at: str
) -> dict[str, Any]:
    if report.get("schemaVersion") != "1.0.0" or report.get("runPurpose") != (
        "s11-ac11-migration-rehearsal"
    ):
        raise ImportError("producer report schema or purpose is unknown")
    if report.get("verdict") != "MEASURED_PASS" or report.get("failureType") is not None:
        raise ImportError("a failed rehearsal cannot become AC-11 evidence")
    source = report.get("sourceHeadSha")
    tree = report.get("checkoutTreeSha")
    if not isinstance(source, str) or not HEX40.fullmatch(source):
        raise ImportError("sourceHeadSha is invalid")
    if not isinstance(tree, str) or not HEX40.fullmatch(tree):
        raise ImportError("checkoutTreeSha is invalid")
    if _git("rev-parse", f"{source}^{{tree}}") != tree or report.get("cleanCheckout") is not True:
        raise ImportError("producer checkout provenance is invalid")
    if _git("rev-parse", f"{source}:{REGISTRY_PATH}") != REGISTRY_BLOB:
        raise ImportError("source tree does not contain the reviewed target registry")
    registry = json.loads(_git("show", f"{source}:{REGISTRY_PATH}"))
    targets = [row for row in registry.get("targets", []) if row.get("targetId") == TARGET_ID]
    if len(targets) != 1:
        raise ImportError("restore target is absent or duplicated")
    target = targets[0]
    criteria = target.get("criteria")
    expected_criteria = {
        "catalogMismatchCount": {"operator": "eq", "value": 0},
        "negativeFixturePassCount": {"operator": "eq", "value": 3},
        "restoreForwardPassCount": {"operator": "eq", "value": 1},
    }
    if criteria != expected_criteria:
        raise ImportError("restore target criteria differ from the importer contract")
    axes = report.get("axes")
    if not isinstance(axes, list) or len(axes) != 2:
        raise ImportError("producer axes are missing or duplicated")
    by_name = {row.get("axis"): row for row in axes if isinstance(row, dict)}
    reversible = by_name.get("migration-reversible-segment")
    restore = by_name.get("irreversible-restore-forward")
    if set(by_name) != {"migration-reversible-segment", "irreversible-restore-forward"}:
        raise ImportError("producer axes are missing or duplicated")
    if reversible != {
        "axis": "migration-reversible-segment",
        "verdict": "NOT_APPLICABLE",
        "structuralException": {"reason": "no-reversible-tail", "reversibleTailCount": 0},
    }:
        raise ImportError("reversible axis lacks the approved structural exception")
    if not isinstance(restore, dict) or restore.get("verdict") != "MEASURED_PASS":
        raise ImportError("restore axis did not pass")
    details = restore.get("details")
    negative = details.get("negativeFixtures") if isinstance(details, dict) else None
    if (
        not isinstance(negative, dict)
        or negative.get("passedCount") != 3
        or sorted(row.get("case") for row in negative.get("cases", []) if isinstance(row, dict))
        != ["0009-duplicate-key", "ellipsis-noop", "existing-object-deletion"]
        or any(row.get("verdict") != "EXPECTED_FINDING" for row in negative.get("cases", []))
    ):
        raise ImportError("negative fixture evidence is incomplete")
    cleanup = report.get("cleanup")
    if not isinstance(cleanup, dict) or cleanup.get("residueCount") != 0:
        raise ImportError("producer cleanup is incomplete")
    digest = _artifact_digest(artifact_digest)
    expiry = _utc(artifact_expires_at, "artifactExpiresAt")
    started = _utc(report.get("startedAt"), "startedAt")
    finished = _utc(report.get("finishedAt"), "finishedAt")
    environment = report.get("environment")
    if not isinstance(environment, dict):
        raise ImportError("producer environment is missing")
    common = {
        "schemaVersion": "1.0.0",
        "runPurpose": "ac11-axis-evidence",
        "sourceRunId": report.get("sourceRunId"),
        "sourceHeadSha": source,
        "checkoutTreeSha": tree,
        "artifactSha256": digest,
        "artifactObservedSha256": digest,
        "artifactAvailable": True,
        "artifactExpiresAt": expiry,
        "cleanCheckout": True,
        "runConclusion": "success",
        "environment": {
            **environment,
            "comparableGroup": "hosted-ubuntu-postgres16-migration-rehearsal",
        },
        "startedAt": started,
        "finishedAt": finished,
        "cleanup": cleanup,
    }
    target_ref = {
        "commit": source,
        "path": REGISTRY_PATH,
        "blob": REGISTRY_BLOB,
        "targetId": TARGET_ID,
        "criteria": criteria,
    }
    imported_axes = [
        {
            **common,
            "axis": "migration-reversible-segment",
            "verdict": "NOT_APPLICABLE",
            "structuralException": reversible["structuralException"],
        },
        {
            **common,
            "axis": "irreversible-restore-forward",
            "targetRef": target_ref,
            "verdict": "MEASURED_PASS",
            "observations": [
                _observation("catalogMismatchCount", 0),
                _observation("negativeFixturePassCount", 3),
                _observation("restoreForwardPassCount", 1),
            ],
        },
    ]
    canonical_report = json.dumps(
        report, sort_keys=True, separators=(",", ":"), ensure_ascii=False
    ).encode("utf-8")
    return {
        "schemaVersion": "1.0.0",
        "runPurpose": "ac11-migration-rehearsal-import",
        "producerReportSha256": hashlib.sha256(canonical_report).hexdigest(),
        "axes": imported_axes,
    }


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--report", type=Path, required=True)
    parser.add_argument("--artifact-digest", required=True)
    parser.add_argument("--artifact-expires-at", required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args(argv)
    try:
        report = json.loads(args.report.read_text(encoding="utf-8"))
        imported = import_report(
            report,
            artifact_digest=args.artifact_digest,
            artifact_expires_at=args.artifact_expires_at,
        )
    except (OSError, json.JSONDecodeError, ImportError) as exc:
        print(f"AC-11 migration import refused: {exc}")
        return 2
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(
        json.dumps(imported, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
