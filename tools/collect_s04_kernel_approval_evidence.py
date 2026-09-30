"""Collect fail-closed S04-DB C1-K kernel approval binding evidence.

The collector reads one repeatable-read, read-only PostgreSQL snapshot and
recomputes approval -> dispatch -> claim -> delivery -> execution bindings.
It emits aggregate counts only.  Historical current-epoch proof remains
NOT_REGISTERED because ``inv.control_epoch`` stores only the current value.

Exit codes: 0 PASS (not currently reachable), 1 FAIL, 2 unavailable/invalid
input, and 3 NOT_OBSERVED.
"""

from __future__ import annotations

import argparse
import base64
import binascii
from collections import Counter
import datetime as dt
import json
import os
from pathlib import Path
import re
import sys
from typing import Any, Callable


REPO_ROOT = Path(__file__).resolve().parents[1]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from tools.operational_evidence import (  # noqa: E402
    EXIT_BY_VERDICT,
    collect_provenance_at_root as _collect_provenance_at_root,
    collector_sha256,
    database_identity as _database_identity,
    input_binding_sha256,
    iso as _iso,
    normalise_dsn,
    parse_timestamp,
    validate_common,
    write_evidence as _write_evidence_pair,
)
from tools.operational_evidence import overall_verdict as _overall_verdict  # noqa: E402


SCHEMA_VERSION = "s04-kernel-approval-evidence:1"
CRITERIA_VERSION = "1.0.0"
CRITERIA_HEAD = "8cf8c1ab1385d56faa8ca8e33d22fc00dd80109c"
CRITERIA_PATH = "docs/vault/30_Development/S04-DB_C1-K_kernel_승인_결속_Evidence_계약.md"
DEFAULT_OUT_DIR = REPO_ROOT / "docs/vault/30_Development/Evidence/s04-kernel-approval"
REQUIRED_OBSERVATIONS = ("K1", "K2", "K3", "K4")

CLAIM_KEYS = frozenset(
    {
        "commandId",
        "claimId",
        "runId",
        "tenantId",
        "projectId",
        "nodeId",
        "actionDigest",
        "planDigest",
        "policyVersion",
        "profileVersion",
        "recoveryEpoch",
        "notAfter",
    }
)
K1_REASONS = (
    "missing_approval_dispatch",
    "approval_not_dispatched",
    "scope_mismatch",
    "action_digest_mismatch",
    "policy_version_mismatch",
    "policy_decision_mismatch",
    "recovery_epoch_mismatch",
    "timestamp_mismatch",
)
K2_REASONS = (
    "missing_claim_row",
    "invalid_envelope_shape",
    "invalid_payload_encoding",
    "invalid_payload_shape",
    "invalid_claim_shape",
    "claim_payload_mismatch",
    "invalid_issued_at",
    "invalid_signature_encoding",
)
K3_REASONS = (
    "missing_chain_row",
    "scope_mismatch",
    "timestamp_mismatch",
    "run_attempt_mismatch",
    "scheduled_event_mismatch",
    "running_event_mismatch",
)

K1_SQL = """
SELECT c.tenant_id::text AS claim_tenant_id,
       c.project_id AS claim_project_id,
       c.run_id AS claim_run_id,
       c.command_id::text AS claim_command_id,
       c.claim_id::text AS claim_id,
       c.node_id AS claim_node_id,
       c.action_digest AS claim_action_digest,
       c.plan_digest AS claim_plan_digest,
       c.policy_version AS claim_policy_version,
       c.profile_version AS claim_profile_version,
       c.policy_decision_id AS claim_policy_decision_id,
       c.recovery_epoch::text AS claim_recovery_epoch,
       c.not_after AS claim_not_after,
       c.created_at AS claim_created_at,
       d.tenant_id::text AS dispatch_tenant_id,
       d.approval_id AS dispatch_approval_id,
       d.command_id::text AS dispatch_command_id,
       d.created_at AS dispatch_created_at,
       a.tenant_id::text AS approval_tenant_id,
       a.project_id AS approval_project_id,
       a.run_id AS approval_run_id,
       a.approval_id,
       a.action_digest AS approval_action_digest,
       a.policy_version AS approval_policy_version,
       a.policy_decision_id AS approval_policy_decision_id,
       a.recovery_epoch::text AS approval_recovery_epoch,
       a.bound_run_version,
       a.status AS approval_status,
       a.expires_at AS approval_expires_at
  FROM inv.tool_claims c
  LEFT JOIN inv.approval_dispatches d
    ON (d.tenant_id,d.command_id)=(c.tenant_id,c.command_id)
  LEFT JOIN inv.approval_requests a
    ON (a.tenant_id,a.approval_id)=(d.tenant_id,d.approval_id)
 ORDER BY c.created_at,c.command_id
"""

K2_SQL = """
SELECT c.tenant_id::text AS claim_tenant_id,
       c.project_id AS claim_project_id,
       c.run_id AS claim_run_id,
       c.command_id::text AS claim_command_id,
       c.claim_id::text AS claim_id,
       c.node_id AS claim_node_id,
       c.action_digest AS claim_action_digest,
       c.plan_digest AS claim_plan_digest,
       c.policy_version AS claim_policy_version,
       c.profile_version AS claim_profile_version,
       c.recovery_epoch::text AS claim_recovery_epoch,
       c.not_after AS claim_not_after,
       q.envelope,
       q.created_at AS delivery_created_at
  FROM inv.execution_deliveries q
  LEFT JOIN inv.tool_claims c
    ON (c.tenant_id,c.command_id)=(q.tenant_id,q.command_id)
 ORDER BY q.created_at,q.command_id
"""

K3_SQL = """
SELECT x.tenant_id::text AS attempt_tenant_id,
       x.project_id AS attempt_project_id,
       x.run_id AS attempt_run_id,
       x.node_id AS attempt_node_id,
       x.command_id::text AS attempt_command_id,
       x.attempt AS execution_attempt,
       ra.attempt AS run_attempt,
       ra.started_at AS attempt_started_at,
       c.created_at AS claim_created_at,
       c.project_id AS claim_project_id,
       c.run_id AS claim_run_id,
       c.node_id AS claim_node_id,
       q.created_at AS delivery_created_at,
       q.project_id AS delivery_project_id,
       q.run_id AS delivery_run_id,
       q.node_id AS delivery_node_id,
       d.created_at AS dispatch_created_at,
       a.project_id AS approval_project_id,
       a.run_id AS approval_run_id,
       a.bound_run_version,
       coalesce(
         jsonb_agg(o.payload ORDER BY o.created_at,o.event_id)
           FILTER (WHERE o.event_id IS NOT NULL AND o.event_type='inv.run.state_changed'),
         '[]'::jsonb
       ) AS state_events
  FROM inv.execution_attempts x
  LEFT JOIN inv.run_attempts ra
    ON (ra.tenant_id,ra.run_id,ra.attempt)=(x.tenant_id,x.run_id,x.attempt)
  LEFT JOIN inv.tool_claims c
    ON (c.tenant_id,c.command_id)=(x.tenant_id,x.command_id)
  LEFT JOIN inv.execution_deliveries q
    ON (q.tenant_id,q.command_id)=(x.tenant_id,x.command_id)
  LEFT JOIN inv.approval_dispatches d
    ON (d.tenant_id,d.command_id)=(x.tenant_id,x.command_id)
  LEFT JOIN inv.approval_requests a
    ON (a.tenant_id,a.approval_id)=(d.tenant_id,d.approval_id)
  LEFT JOIN inv.outbox o
    ON (o.tenant_id,o.run_id)=(x.tenant_id,x.run_id)
 GROUP BY x.tenant_id,x.project_id,x.run_id,x.node_id,x.command_id,x.attempt,
          ra.attempt,ra.started_at,c.created_at,c.project_id,c.run_id,c.node_id,
          q.created_at,q.project_id,q.run_id,q.node_id,d.created_at,
          a.project_id,a.run_id,a.bound_run_version
 ORDER BY ra.started_at,x.command_id
"""


def _aware(value: Any) -> dt.datetime | None:
    if not isinstance(value, dt.datetime) or value.tzinfo is None:
        return None
    return value.astimezone(dt.timezone.utc)


def _observation(rows: list[dict[str, Any]], reasons: Counter[str], *, noun: str) -> dict[str, Any]:
    unknown = set(reasons) - set(K1_REASONS) - set(K2_REASONS) - set(K3_REASONS)
    if unknown or any(not isinstance(value, int) or value < 0 for value in reasons.values()):
        raise ValueError("invalid violation reason counts")
    count = len(rows)
    violation_count = sum(reasons.values())
    metrics = {
        f"{noun}Count": count,
        "validCount": count - violation_count,
        "violationCount": violation_count,
        "violationsByReason": dict(sorted(reasons.items())),
    }
    if violation_count > count:
        raise ValueError("violation count exceeds observed row count")
    if not count:
        return {
            "status": "NOT_OBSERVED",
            "reason": f"no {noun} rows were present; safety was not exercised",
            "metrics": metrics,
        }
    if violation_count:
        return {
            "status": "MEASURED_FAIL",
            "reason": f"one or more {noun} rows violated the C1-K binding",
            "metrics": metrics,
        }
    return {
        "status": "MEASURED_PASS",
        "reason": f"all observed {noun} rows satisfied the preregistered C1-K binding",
        "metrics": metrics,
    }


def _first_reason(
    row: dict[str, Any], checks: tuple[tuple[str, Callable[[], bool]], ...]
) -> str | None:
    for reason, check in checks:
        try:
            if check():
                return reason
        except (KeyError, TypeError, ValueError):
            return reason
    return None


def evaluate_k1(rows: list[dict[str, Any]]) -> dict[str, Any]:
    reasons: Counter[str] = Counter()
    for row in rows:
        reason = _first_reason(
            row,
            (
                (
                    "missing_approval_dispatch",
                    lambda: not row.get("approval_id") or not row.get("dispatch_approval_id"),
                ),
                ("approval_not_dispatched", lambda: row.get("approval_status") != "dispatched"),
                (
                    "scope_mismatch",
                    lambda: len(
                        {
                            (
                                row.get("claim_tenant_id"),
                                row.get("claim_project_id"),
                                row.get("claim_run_id"),
                            ),
                            (
                                row.get("dispatch_tenant_id"),
                                row.get("approval_project_id"),
                                row.get("approval_run_id"),
                            ),
                            (
                                row.get("approval_tenant_id"),
                                row.get("approval_project_id"),
                                row.get("approval_run_id"),
                            ),
                        }
                    )
                    != 1
                    or row.get("claim_command_id") != row.get("dispatch_command_id")
                    or row.get("dispatch_approval_id") != row.get("approval_id"),
                ),
                (
                    "action_digest_mismatch",
                    lambda: row.get("claim_action_digest") != row.get("approval_action_digest"),
                ),
                (
                    "policy_version_mismatch",
                    lambda: row.get("claim_policy_version") != row.get("approval_policy_version"),
                ),
                (
                    "policy_decision_mismatch",
                    lambda: row.get("claim_policy_decision_id")
                    != row.get("approval_policy_decision_id"),
                ),
                (
                    "recovery_epoch_mismatch",
                    lambda: row.get("claim_recovery_epoch") != row.get("approval_recovery_epoch"),
                ),
                (
                    "timestamp_mismatch",
                    lambda: any(
                        value is None
                        for value in (
                            _aware(row.get("dispatch_created_at")),
                            _aware(row.get("claim_created_at")),
                            _aware(row.get("claim_not_after")),
                            _aware(row.get("approval_expires_at")),
                        )
                    )
                    or not (
                        _aware(row["dispatch_created_at"])
                        <= _aware(row["claim_created_at"])
                        < _aware(row["claim_not_after"])
                        <= _aware(row["approval_expires_at"])
                    ),
                ),
            ),
        )
        if reason:
            reasons[reason] += 1
    return _observation(rows, reasons, noun="claim")


def _strict_object(raw: bytes) -> dict[str, Any]:
    def pairs(values):
        result: dict[str, Any] = {}
        for key, value in values:
            if key in result:
                raise ValueError("duplicate JSON key")
            result[key] = value
        return result

    value = json.loads(raw.decode("utf-8"), object_pairs_hook=pairs)
    if not isinstance(value, dict):
        raise ValueError("payload must be an object")
    return value


def _wire_claim(row: dict[str, Any]) -> dict[str, Any]:
    not_after = _aware(row.get("claim_not_after"))
    if not_after is None:
        raise ValueError("claim not_after is invalid")
    return {
        "commandId": row.get("claim_command_id"),
        "claimId": row.get("claim_id"),
        "runId": row.get("claim_run_id"),
        "tenantId": row.get("claim_tenant_id"),
        "projectId": row.get("claim_project_id"),
        "nodeId": row.get("claim_node_id"),
        "actionDigest": row.get("claim_action_digest"),
        "planDigest": row.get("claim_plan_digest"),
        "policyVersion": row.get("claim_policy_version"),
        "profileVersion": row.get("claim_profile_version"),
        "recoveryEpoch": row.get("claim_recovery_epoch"),
        "notAfter": not_after.isoformat(),
    }


def _k2_reason(row: dict[str, Any]) -> str | None:
    if any(
        row.get(key) is None
        for key in (
            "claim_tenant_id",
            "claim_project_id",
            "claim_run_id",
            "claim_command_id",
            "claim_id",
            "claim_node_id",
            "claim_not_after",
        )
    ):
        return "missing_claim_row"
    envelope = row.get("envelope")
    if not isinstance(envelope, dict) or set(envelope) != {"payload", "signature"}:
        return "invalid_envelope_shape"
    try:
        payload_raw = base64.b64decode(envelope["payload"], validate=True)
        payload = _strict_object(payload_raw)
    except (
        binascii.Error,
        UnicodeError,
        json.JSONDecodeError,
        RecursionError,
        TypeError,
        ValueError,
    ):
        return "invalid_payload_encoding"
    if set(payload) != {"claim", "launch", "allocations", "issuedAt"}:
        return "invalid_payload_shape"
    claim = payload.get("claim")
    if not isinstance(claim, dict) or set(claim) != CLAIM_KEYS:
        return "invalid_claim_shape"
    try:
        if claim != _wire_claim(row):
            return "claim_payload_mismatch"
    except ValueError:
        return "claim_payload_mismatch"
    try:
        issued = parse_timestamp(payload.get("issuedAt"))
    except (TypeError, ValueError):
        return "invalid_issued_at"
    not_after = _aware(row.get("claim_not_after"))
    if issued is None or not_after is None or issued > not_after:
        return "invalid_issued_at"
    try:
        signature = base64.b64decode(envelope["signature"], validate=True)
    except (binascii.Error, TypeError, ValueError):
        return "invalid_signature_encoding"
    if len(signature) != 64:
        return "invalid_signature_encoding"
    return None


def evaluate_k2(rows: list[dict[str, Any]]) -> dict[str, Any]:
    reasons: Counter[str] = Counter()
    for row in rows:
        reason = _k2_reason(row)
        if reason:
            reasons[reason] += 1
    result = _observation(rows, reasons, noun="delivery")
    result["metrics"]["signatureVerificationStatus"] = "RECORDED_ONLY"
    return result


def _event_matches(event: Any, *, state: str, version: int, attempt: int) -> bool:
    return (
        isinstance(event, dict)
        and event.get("state") == state
        and type(event.get("version")) is int
        and event["version"] == version
        and type(event.get("attempt")) is int
        and event["attempt"] == attempt
    )


def evaluate_k3(rows: list[dict[str, Any]]) -> dict[str, Any]:
    reasons: Counter[str] = Counter()
    for row in rows:
        bound = row.get("bound_run_version")
        events = row.get("state_events")
        reason = _first_reason(
            row,
            (
                (
                    "missing_chain_row",
                    lambda: any(
                        row.get(key) is None
                        for key in (
                            "run_attempt",
                            "claim_created_at",
                            "delivery_created_at",
                            "dispatch_created_at",
                            "bound_run_version",
                        )
                    ),
                ),
                (
                    "scope_mismatch",
                    lambda: len(
                        {
                            (
                                row.get("attempt_project_id"),
                                row.get("attempt_run_id"),
                                row.get("attempt_node_id"),
                            ),
                            (
                                row.get("claim_project_id"),
                                row.get("claim_run_id"),
                                row.get("claim_node_id"),
                            ),
                            (
                                row.get("delivery_project_id"),
                                row.get("delivery_run_id"),
                                row.get("delivery_node_id"),
                            ),
                            (
                                row.get("approval_project_id"),
                                row.get("approval_run_id"),
                                row.get("attempt_node_id"),
                            ),
                        }
                    )
                    != 1,
                ),
                (
                    "timestamp_mismatch",
                    lambda: any(
                        _aware(row.get(key)) is None
                        for key in (
                            "dispatch_created_at",
                            "claim_created_at",
                            "delivery_created_at",
                            "attempt_started_at",
                        )
                    )
                    or not (
                        _aware(row["dispatch_created_at"])
                        <= _aware(row["claim_created_at"])
                        <= _aware(row["delivery_created_at"])
                        <= _aware(row["attempt_started_at"])
                    ),
                ),
                (
                    "run_attempt_mismatch",
                    lambda: row.get("execution_attempt") != row.get("run_attempt"),
                ),
                (
                    "scheduled_event_mismatch",
                    lambda: type(bound) is not int
                    or not isinstance(events, list)
                    or sum(
                        _event_matches(event, state="scheduled", version=bound + 1, attempt=0)
                        for event in events
                    )
                    != 1,
                ),
                (
                    "running_event_mismatch",
                    lambda: type(bound) is not int
                    or not isinstance(events, list)
                    or sum(
                        _event_matches(
                            event,
                            state="running",
                            version=bound + 2,
                            attempt=row.get("execution_attempt"),
                        )
                        for event in events
                    )
                    != 1,
                ),
            ),
        )
        if reason:
            reasons[reason] += 1
    return _observation(rows, reasons, noun="executionAttempt")


def collect_database(dsn: str) -> dict[str, Any]:
    """Read one target DB snapshot without mutating it."""
    import psycopg
    from psycopg.rows import dict_row

    with psycopg.connect(normalise_dsn(dsn), row_factory=dict_row) as conn:
        conn.execute("SET TRANSACTION ISOLATION LEVEL REPEATABLE READ, READ ONLY")
        conn.execute("SET LOCAL statement_timeout = '30s'")
        identity = _database_identity(conn)
        started_at = conn.execute("SELECT clock_timestamp() AS value").fetchone()["value"]
        k1_rows = [dict(row) for row in conn.execute(K1_SQL).fetchall()]
        k2_rows = [dict(row) for row in conn.execute(K2_SQL).fetchall()]
        k3_rows = [dict(row) for row in conn.execute(K3_SQL).fetchall()]
        finished_at = conn.execute("SELECT clock_timestamp() AS value").fetchone()["value"]
        conn.rollback()
    return {
        "identity": identity,
        "sourceStartedAt": _iso(started_at),
        "sourceFinishedAt": _iso(finished_at),
        "k1": k1_rows,
        "k2": k2_rows,
        "k3": k3_rows,
    }


def build_evidence(
    *, database: dict[str, Any], provenance: dict[str, Any], source_env: str
) -> dict[str, Any]:
    observations = {
        "K1": evaluate_k1(database["k1"]),
        "K2": evaluate_k2(database["k2"]),
        "K3": evaluate_k3(database["k3"]),
        "K4": {
            "status": "NOT_REGISTERED",
            "reason": "execution-time control epoch history producer is absent",
            "metrics": {"currentEpochSubstitutionAllowed": False},
        },
    }
    verdict = _overall_verdict(observations, REQUIRED_OBSERVATIONS)
    collector_sha = collector_sha256(__file__)
    binding = {
        "codeSha": provenance.get("commit_sha"),
        "collectorSha256": collector_sha,
        "databaseIdentitySha256": database["identity"]["databaseIdentitySha256"],
        "snapshotSha256": database["identity"]["snapshotSha256"],
        "sourceStartedAt": database["sourceStartedAt"],
        "sourceFinishedAt": database["sourceFinishedAt"],
    }
    evidence = {
        "schemaVersion": SCHEMA_VERSION,
        "taskIds": ["S04-DB"],
        "criteria": {
            "version": CRITERIA_VERSION,
            "sourceHead": CRITERIA_HEAD,
            "path": CRITERIA_PATH,
        },
        "acceptanceClaim": verdict == "PASS",
        "verdict": verdict,
        "codeSha": provenance.get("commit_sha"),
        "provenance": {
            "branch": provenance.get("branch"),
            "workingTreeClean": provenance.get("working_tree_clean_status"),
            "contentClean": provenance.get("content_clean_diff"),
            "executor": provenance.get("executor"),
            "collectorSha256": collector_sha,
        },
        "source": {
            "kind": "kernel-postgresql",
            "dsnEnvironment": source_env,
            "sourceStartedAt": database["sourceStartedAt"],
            "sourceFinishedAt": database["sourceFinishedAt"],
            "database": database["identity"],
            "inputBindingSha256": input_binding_sha256(binding),
        },
        "observations": observations,
        "redaction": {
            "identifiersRecorded": False,
            "payloadRecorded": False,
            "rawErrorsRecorded": False,
        },
    }
    validate_evidence(evidence)
    return evidence


def validate_evidence(evidence: dict[str, Any]) -> None:
    validate_common(
        evidence,
        schema_version=SCHEMA_VERSION,
        criteria={"version": CRITERIA_VERSION, "sourceHead": CRITERIA_HEAD, "path": CRITERIA_PATH},
        required=REQUIRED_OBSERVATIONS,
    )
    if evidence.get("taskIds") != ["S04-DB"]:
        raise ValueError("taskIds mismatch")
    observations = evidence.get("observations") or {}
    if set(observations) != set(REQUIRED_OBSERVATIONS):
        raise ValueError("observation set mismatch")
    if observations["K4"].get("status") != "NOT_REGISTERED":
        raise ValueError("K4 cannot pass without an execution-time epoch producer")
    if (observations["K4"].get("metrics") or {}).get(
        "currentEpochSubstitutionAllowed"
    ) is not False:
        raise ValueError("current epoch cannot substitute for execution-time history")
    if (observations["K2"].get("metrics") or {}).get(
        "signatureVerificationStatus"
    ) != "RECORDED_ONLY":
        raise ValueError("signature verification must remain recorded-only without key provenance")
    if evidence.get("redaction") != {
        "identifiersRecorded": False,
        "payloadRecorded": False,
        "rawErrorsRecorded": False,
    }:
        raise ValueError("redaction declaration mismatch")


def render_markdown(evidence: dict[str, Any]) -> str:
    source = evidence["source"]
    lines = [
        "# S04-DB C1-K kernel approval binding evidence",
        "",
        f"- verdict: **{evidence['verdict']}** · acceptanceClaim: `{str(evidence['acceptanceClaim']).lower()}`",
        f"- code SHA: `{evidence['codeSha']}` · criteria: v{CRITERIA_VERSION} @ `{CRITERIA_HEAD[:12]}`",
        f"- source: `{source['kind']}` via env name `{source['dsnEnvironment']}` (value not recorded)",
        f"- database identity: `{source['database']['databaseIdentitySha256']}` · migration `{source['database']['migrationHead']}`",
        f"- captured: `{source['sourceStartedAt']}` .. `{source['sourceFinishedAt']}` · binding `{source['inputBindingSha256']}`",
        "",
        "| observation | status | reason |",
        "|---|---|---|",
    ]
    for key in REQUIRED_OBSERVATIONS:
        item = evidence["observations"][key]
        lines.append(f"| {key} | **{item['status']}** | {item['reason']} |")
    lines += [
        "",
        "- Permit signature bytes are format-checked only; key provenance is absent, so cryptographic verification is RECORDED_ONLY.",
        "- No DSN, host, database name, tenant/project/run/node/approval/command/claim identifier, payload, signature, or raw error is stored.",
    ]
    return "\n".join(lines) + "\n"


def write_evidence(evidence: dict[str, Any], out_dir: Path, label: str) -> tuple[Path, Path]:
    return _write_evidence_pair(evidence, out_dir, label, render_markdown=render_markdown)


def parser() -> argparse.ArgumentParser:
    result = argparse.ArgumentParser(description=__doc__.split("\n\n", 1)[0])
    result.add_argument(
        "--dsn-env",
        choices=("INV_AUDIT_DSN", "INV_TEST_DATABASE_URL", "INV_TEST_ADMIN_DSN"),
        default="INV_AUDIT_DSN",
    )
    result.add_argument("--out-dir", type=Path, default=DEFAULT_OUT_DIR)
    result.add_argument("--label")
    result.add_argument("--executor", default="Codex")
    return result


def main(argv: list[str] | None = None) -> int:
    args = parser().parse_args(argv)
    dsn = os.environ.get(args.dsn_env)
    if not dsn:
        print(f"{args.dsn_env} is required; no database was observed", file=sys.stderr)
        return 2
    if args.label is not None and not re.fullmatch(r"[A-Za-z0-9][A-Za-z0-9._-]{0,127}", args.label):
        print("label must be 1-128 safe filename characters", file=sys.stderr)
        return 2
    provenance = _collect_provenance_at_root(args.executor)
    if not provenance.get("working_tree_clean_status") or not provenance.get("content_clean_diff"):
        print("a clean committed working tree is required", file=sys.stderr)
        return 2
    try:
        database = collect_database(dsn)
        evidence = build_evidence(database=database, provenance=provenance, source_env=args.dsn_env)
        label = args.label or (
            f"s04-kernel-approval-{evidence['codeSha'][:12]}-"
            f"{dt.datetime.now(dt.timezone.utc):%Y%m%dT%H%M%SZ}"
        )
        json_path, markdown_path = write_evidence(evidence, args.out_dir, label)
    except Exception as error:
        print(f"collector unavailable: {type(error).__name__}", file=sys.stderr)
        return 2
    print(
        json.dumps(
            {
                "verdict": evidence["verdict"],
                "observations": {
                    key: value["status"] for key, value in evidence["observations"].items()
                },
                "json": str(json_path),
                "markdown": str(markdown_path),
            },
            ensure_ascii=False,
        )
    )
    return EXIT_BY_VERDICT[evidence["verdict"]]


if __name__ == "__main__":
    raise SystemExit(main())
