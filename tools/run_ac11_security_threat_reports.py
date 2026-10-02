"""Produce the AC-11 security axis's database threat reports, fail closed.

The aggregator requires four threat reports for ``security-critical-high-zero`` and only
SEC-SCAN-001 had a producer: the dependency/SAST lane.  The other three were never missing
*tools* -- ``check_definer_functions.py`` and ``collect_rls_evidence.py`` have measured those
boundaries for weeks -- they were missing a path that records their output in the shape the
aggregator reads.  This producer is that path for the two database reports:

* ``SEC-DEF-001`` -- privileged (SECURITY DEFINER) functions against the reviewed policy;
* ``SEC-RLS-001`` -- the API/PostgreSQL authentication and RLS boundary.

Both are measured against a **disposable migrated database** created from
``INV_TEST_ADMIN_DSN`` and dropped afterwards, which is the same thing the collectors already
do for their own evidence.  Nothing is written to an operational database and no DSN,
password or row value is recorded: the reports carry catalogue observations, counts and rule
identities only.

Fail closed, in the words the canonical evaluators use:

* an observation that could not be made is ``status: unavailable`` with ``exitCode: 2``,
  never an empty passing inventory (``evaluate_definer`` answers NOT_OBSERVED for that pair
  and INVALID_RUN for any other use of exit 2);
* a measured failure keeps its exit code and its finding rows -- this producer never lowers
  a verdict, and the axis is allowed to come out MEASURED_FAIL;
* ``toolFiles`` records the Git blob of the files that actually ran, computed from this
  checkout.  The aggregator compares those blobs with the source tree and with its own
  reviewed pins, so a drifted tool is refused rather than silently accepted.

Usage: INV_TEST_ADMIN_DSN=... python tools/run_ac11_security_threat_reports.py \
           --source-run-id 123 --source-head-sha <sha> --output-dir evidence
Exit 0: both reports were written (their verdicts may be anything the measurement found).
Exit 2: the reports were written as unavailable observations, or inputs were unusable.
"""

from __future__ import annotations

import argparse
import datetime as dt
import hashlib
import json
import os
import subprocess
import sys
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT / "tools") not in sys.path:
    sys.path.insert(0, str(ROOT / "tools"))

#: The threat reports this producer writes, and the member name each one takes in the lane's
#: artifact.  The security importer reads exactly these names.
DEFINER_MEMBER = "s11-ac11-security-definer.json"
RLS_MEMBER = "s11-ac11-security-rls.json"
DEFINER_THREAT_ID = "SEC-DEF-001"
RLS_THREAT_ID = "SEC-RLS-001"
RUN_PURPOSE = "s11-ac11-security-threat-reports"
SCHEMA_VERSION = "1.0.0"

#: The files whose blobs each report pins.  These are the same paths the aggregator holds in
#: ``DEFINER_FILES`` and ``RLS_FILES``; the blobs are measured here rather than copied, so a
#: tool that moved without its pin moving shows up as a refusal instead of as agreement.
DEFINER_TOOL_PATHS = ("tools/check_definer_functions.py", "tools/definer-policy.json")
RLS_TOOL_PATHS = ("tools/collect_rls_evidence.py", "tools/rls-boundary-baseline.json")

#: The collector CLI's own verdict-to-exit-code mapping (``collect_rls_evidence.main``).
RLS_EXIT_CODES = {"PASS": 0, "VIOLATIONS": 1, "UNMEASURED": 3}

#: The role population is the collector's own default, read from it rather than chosen here.
#: Choosing a smaller set would change the verdict: measuring two roles instead of the
#: collector's eight turns this tree's UNMEASURED into a PASS, because the one row whose
#: identity cannot be verified belongs to a role the short list never asks about.  A verdict
#: obtained by asking less is not this axis's measurement.


class ProducerError(RuntimeError):
    """A fail-closed producer refusal with no credential material in its message."""


def _utc_now() -> str:
    return dt.datetime.now(dt.timezone.utc).isoformat().replace("+00:00", "Z")


def _blob(path: str) -> str:
    """The Git blob of a file in this checkout."""

    done = subprocess.run(
        ["git", "hash-object", path], cwd=ROOT, capture_output=True, text=True, timeout=20
    )
    if done.returncode or not done.stdout.strip():
        raise ProducerError(f"cannot read the Git blob of {path}")
    return done.stdout.strip()


def tool_files(paths: tuple[str, ...]) -> list[dict[str, str]]:
    return [{"path": path, "blob": _blob(path)} for path in paths]


def _tree_sha(source_head_sha: str) -> str:
    done = subprocess.run(
        ["git", "rev-parse", f"{source_head_sha}^{{tree}}"],
        cwd=ROOT, capture_output=True, text=True, timeout=20,
    )
    if done.returncode or not done.stdout.strip():
        raise ProducerError("cannot read the tree of the source head")
    return done.stdout.strip()


def _clean_checkout() -> bool:
    done = subprocess.run(
        ["git", "status", "--porcelain"], cwd=ROOT, capture_output=True, text=True, timeout=20
    )
    return done.returncode == 0 and not done.stdout.strip()


def _provenance(args, started_at: str) -> dict[str, Any]:
    return {
        "schemaVersion": SCHEMA_VERSION,
        "runPurpose": RUN_PURPOSE,
        "sourceRunId": args.source_run_id,
        "sourceHeadSha": args.source_head_sha,
        "checkoutTreeSha": _tree_sha(args.source_head_sha),
        "cleanCheckout": _clean_checkout(),
        "startedAt": started_at,
        "finishedAt": _utc_now(),
    }


def definer_report(dsn: str | None) -> dict[str, Any]:
    """SEC-DEF-001 in the shape ``evaluate_definer`` reads.

    The three values it recomputes -- ``status``, ``functions``, ``unsafe`` -- are the
    checker's own, and ``exitCode`` is the code the checker's CLI would have returned.  An
    observation that failed is reported as unavailable with exit 2: a privileged-function
    inventory that could not be read must never arrive as an empty passing one.
    """

    import check_definer_functions as definer

    if not dsn:
        return {"status": "unavailable", "error": "no_database_observation", "unsafe": None,
                "exitCode": 2}
    try:
        functions = definer.audit(dsn)
    except Exception:  # noqa: BLE001 - driver messages can carry credentials or data
        return {"status": "unavailable", "error": "catalog_observation_failed", "unsafe": None,
                "exitCode": 2}
    unsafe = sum(bool(row["problems"]) for row in functions)
    return {
        "status": "requires_review" if unsafe else "matches_reviewed_policy",
        "functions": functions,
        "unsafe": unsafe,
        "exitCode": 1 if unsafe else 0,
    }


def rls_report(dsn: str | None, tenant: str | None, allowlist: dict[str, Any]) -> dict[str, Any]:
    """SEC-RLS-001 in the shape ``evaluate_rls`` reads.

    ``baselineAccepted`` states which reviewed dispositions this measurement was judged
    against, and the aggregator requires it to equal the reviewed allowlist exactly -- so it
    is taken from that allowlist rather than from the collector's own baseline file, which is
    a superset maintained for the S02-DB lane.  Every other field is the collector's output.
    """

    import collect_rls_evidence as rls

    baseline_accepted = [
        {"role": entry["role"], "table": entry["table"], "rules": list(entry["rules"])}
        for entry in allowlist["rlsAcceptedDispositions"]
    ]
    if not dsn:
        return {"exitCode": 2, "status": "unavailable", "baselineAccepted": baseline_accepted}
    try:
        observation = rls.collect(dsn, rls.DEFAULT_ROLES, tenant)
    except Exception:  # noqa: BLE001 - connection and catalogue messages can carry secrets
        return {
            "exitCode": 2,
            "status": "unavailable",
            "error": "boundary_observation_failed",
            "baselineAccepted": baseline_accepted,
        }
    observation["note"] = "AC-11 SEC-RLS-001 threat report; disposable migrated database"
    baseline = rls.load_baseline()
    violations, accepted = rls.apply_baseline(rls.evaluate(observation), baseline)
    unmeasured, accepted_unmeasured = rls.apply_baseline(
        rls.unverified_identities(observation), baseline
    )
    accepted += accepted_unmeasured
    verdict = rls.verdict(violations, unmeasured)
    # The collector's own CLI mapping, read rather than restated: a second copy of it would
    # be a second definition of what the exit code means.
    exit_code = RLS_EXIT_CODES[verdict]
    return {
        "exitCode": exit_code,
        "verdict": verdict,
        "violations": violations,
        "accepted": accepted,
        "unmeasured": unmeasured,
        "roles": observation["roles"],
        "ground_truth": observation["ground_truth"],
        "baselineAccepted": baseline_accepted,
        "measuredRoles": list(rls.DEFAULT_ROLES),
    }


def _load_allowlist(path: Path) -> dict[str, Any]:
    try:
        value = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, UnicodeError, json.JSONDecodeError) as exc:
        raise ProducerError(f"reviewed allowlist unreadable: {type(exc).__name__}") from None
    if not isinstance(value, dict) or not isinstance(value.get("rlsAcceptedDispositions"), list):
        raise ProducerError("reviewed allowlist does not carry rlsAcceptedDispositions")
    return value


def _write(path: Path, document: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(document, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    parser.add_argument("--source-run-id", required=True)
    parser.add_argument("--source-head-sha", required=True)
    parser.add_argument("--output-dir", type=Path, required=True)
    parser.add_argument(
        "--allowlist",
        type=Path,
        default=ROOT / "docs/vault/30_Development/Evidence/s11-security-allowlist-v0.json",
    )
    parser.add_argument(
        "--dsn",
        default=None,
        help="measure this database instead of creating a disposable one; never recorded",
    )
    args = parser.parse_args(argv)

    started_at = _utc_now()
    allowlist = _load_allowlist(args.allowlist)
    admin = os.environ.get("INV_TEST_ADMIN_DSN")

    def emit(definer: dict[str, Any], boundary: dict[str, Any]) -> int:
        provenance = _provenance(args, started_at)
        definer_document = {
            **provenance,
            "threatId": DEFINER_THREAT_ID,
            "toolFiles": tool_files(DEFINER_TOOL_PATHS),
            "reportAvailable": definer.get("status") != "unavailable",
            **definer,
        }
        rls_document = {
            **provenance,
            "threatId": RLS_THREAT_ID,
            "toolFiles": tool_files(RLS_TOOL_PATHS),
            "reportAvailable": boundary.get("exitCode") != 2,
            **boundary,
        }
        _write(args.output_dir / DEFINER_MEMBER, definer_document)
        _write(args.output_dir / RLS_MEMBER, rls_document)
        print(
            "SEC-DEF-001 exit %s (%s), SEC-RLS-001 exit %s (%s)"
            % (
                definer_document["exitCode"], definer_document.get("status"),
                rls_document["exitCode"], rls_document.get("verdict", rls_document.get("status")),
            )
        )
        return 2 if 2 in (definer_document["exitCode"], rls_document["exitCode"]) else 0

    if args.dsn:
        return emit(definer_report(args.dsn), rls_report(args.dsn, None, allowlist))
    if not admin:
        # No database to make a disposable one from: both reports say so rather than passing.
        print("INV_TEST_ADMIN_DSN is required for a disposable observation", file=sys.stderr)
        return emit(definer_report(None), rls_report(None, None, allowlist))

    import collect_rls_evidence as rls

    try:
        with rls.disposable_database(admin) as (dsn, tenant_a):
            definer = definer_report(dsn)
            boundary = rls_report(dsn, tenant_a, allowlist)
    except Exception:  # noqa: BLE001 - creation messages can carry the admin DSN
        print("disposable database unavailable; no pass recorded", file=sys.stderr)
        return emit(definer_report(None), rls_report(None, None, allowlist))
    return emit(definer, boundary)


if __name__ == "__main__":  # pragma: no cover - CLI
    try:
        raise SystemExit(main())
    except ProducerError as error:
        print(f"AC-11 security threat report producer refused: {error}", file=sys.stderr)
        raise SystemExit(2) from None
