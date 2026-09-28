"""Collect S04-DB retransmission and S08-DB retention operational evidence.

This collector implements the verdict boundaries registered by
``S04-DB_S08-DB_운영_판정_기준.md`` v1.1.1.  It directly measures only inputs
that are actually available in the target core PostgreSQL database:

* O1 outbox flow, when an explicit observation-window start is supplied; and
* O3/C1, the *core* approval boundary over ``public.approvals``,
  ``run_attempts``, ``workloads`` and ``runs``.

Everything else remains explicitly NOT_OBSERVED, NOT_REGISTERED or
BLOCKED_EXTERNAL until its independent input exists.  In particular this tool
does not claim the kernel C1-K recovery-epoch boundary, O8' continuous audit,
physical Node delivery, operational backup/PITR, or retention/GC execution.

The output contains aggregate counts only.  It binds them to a committed code
SHA, collector hash, database fingerprint, transaction snapshot and database
timestamps without recording a DSN, database name, host, row id or secret.

Exit codes: 0 PASS (all required observations measured; currently unreachable
without future input adapters), 1 FAIL, 2 UNAVAILABLE/invalid input, and
3 NOT_OBSERVED.
"""

from __future__ import annotations

import argparse
import datetime as dt
import hashlib
import json
import os
from pathlib import Path
import re
import sys
from typing import Any


REPO_ROOT = Path(__file__).resolve().parents[1]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from tools.provenance import collect as collect_provenance  # noqa: E402


SCHEMA_VERSION = "s04-s08-operational-evidence:1"
CRITERIA_VERSION = "1.1.1"
CRITERIA_HEAD = "90a2051d450f5b52744129035bead25c50551217"
CRITERIA_PATH = "docs/vault/30_Development/S04-DB_S08-DB_운영_판정_기준.md"
DEFAULT_OUT_DIR = REPO_ROOT / "docs/vault/30_Development/Evidence/s04-s08-operational"

STATUSES = frozenset(
    {
        "MEASURED_PASS",
        "MEASURED_FAIL",
        "NOT_OBSERVED",
        "NOT_REGISTERED",
        "BLOCKED_EXTERNAL",
        "RECORDED_ONLY",
    }
)
REQUIRED_OBSERVATIONS = (
    "O1",
    "O2",
    "O3",
    "O4",
    "O5",
    "O6",
    "O7",
    "O8_PRIME",
    "O9",
    "O10",
    "O11",
    "O12",
    "O13",
)
C1_REASONS = frozenset(
    {
        "no_approved_before_attempt",
        "approval_expired",
        "approval_digest_mismatch",
        "cancelled_before_attempt",
    }
)
_SHA256 = re.compile(r"^[0-9a-f]{64}$")


# C1 is intentionally public/core-only.  ``inv.approval_requests`` and every
# recovery-epoch field belong to the separate C1-K collector.
C1_SQL = """
WITH evaluated AS (
    SELECT ra.tenant_id,
           ra.attempt_id,
           ra.run_id,
           ra.started_at,
           CASE
             WHEN chosen.approval_id IS NULL THEN 'no_approved_before_attempt'
             WHEN chosen.expires_at <= ra.started_at THEN 'approval_expired'
             WHEN chosen.subject_sha256 <> w.spec_sha256 THEN 'approval_digest_mismatch'
             WHEN EXISTS (
                 SELECT 1
                   FROM public.audit_events ae
                  WHERE ae.tenant_id = ra.tenant_id
                    AND ae.target_type = 'run'
                    AND ae.target_id = ra.run_id
                    AND ae.action LIKE 'run.cancel%'
                    AND ae.occurred_at <= ra.started_at
             ) THEN 'cancelled_before_attempt'
             ELSE NULL
           END AS violation_reason
      FROM public.run_attempts ra
      JOIN public.runs r
        ON r.tenant_id = ra.tenant_id AND r.run_id = ra.run_id
      JOIN public.workloads w
        ON w.tenant_id = r.tenant_id AND w.workload_id = r.workload_id
      LEFT JOIN LATERAL (
          SELECT a.approval_id, a.expires_at, a.subject_sha256
            FROM public.approvals a
           WHERE a.tenant_id = ra.tenant_id
             AND a.run_id = ra.run_id
             AND a.decision = 'approved'
             AND a.decided_at <= ra.started_at
           ORDER BY a.decided_at DESC, a.approval_id DESC
           LIMIT 1
      ) chosen ON true
)
SELECT count(*)::bigint AS attempt_count,
       count(*) FILTER (WHERE violation_reason IS NULL)::bigint AS valid_count,
       count(*) FILTER (WHERE violation_reason IS NOT NULL)::bigint AS violation_count,
       count(*) FILTER (WHERE violation_reason = 'no_approved_before_attempt')::bigint
           AS no_approved_before_attempt,
       count(*) FILTER (WHERE violation_reason = 'approval_expired')::bigint
           AS approval_expired,
       count(*) FILTER (WHERE violation_reason = 'approval_digest_mismatch')::bigint
           AS approval_digest_mismatch,
       count(*) FILTER (WHERE violation_reason = 'cancelled_before_attempt')::bigint
           AS cancelled_before_attempt
  FROM evaluated
"""

OUTBOX_SQL = """
SELECT count(*)::bigint AS event_count,
       count(*) FILTER (WHERE status = 'published')::bigint AS published_count,
       count(*) FILTER (WHERE status = 'failed')::bigint AS failed_count,
       count(*) FILTER (
           WHERE status = 'pending' AND created_at < %(finished_at)s - interval '10 minutes'
       )::bigint AS stale_pending_count,
       coalesce(max(publish_attempts), 0)::bigint AS max_publish_attempts
  FROM public.outbox_events
 WHERE created_at >= %(started_at)s
   AND created_at <= %(finished_at)s
"""


def _sha256_text(value: str) -> str:
    return hashlib.sha256(value.encode("utf-8")).hexdigest()


def _iso(value: dt.datetime) -> str:
    if value.tzinfo is None:
        raise ValueError("timestamp must be timezone-aware")
    return value.astimezone(dt.timezone.utc).isoformat(timespec="seconds").replace("+00:00", "Z")


def parse_timestamp(value: str | None) -> dt.datetime | None:
    if value is None:
        return None
    parsed = dt.datetime.fromisoformat(value.replace("Z", "+00:00"))
    if parsed.tzinfo is None:
        raise ValueError("timestamp must carry an offset")
    return parsed.astimezone(dt.timezone.utc)


def evaluate_c1_summary(summary: dict[str, int]) -> dict[str, Any]:
    """Turn aggregate C1 SQL counts into a fail-closed O3 observation."""
    attempt_count = int(summary.get("attempt_count", 0))
    violation_count = int(summary.get("violation_count", 0))
    valid_count = int(summary.get("valid_count", 0))
    reasons = {reason: int(summary.get(reason, 0)) for reason in sorted(C1_REASONS)}
    if attempt_count < 0 or valid_count < 0 or violation_count < 0:
        raise ValueError("C1 counts cannot be negative")
    if valid_count + violation_count != attempt_count:
        raise ValueError("C1 count identity does not hold")
    if sum(reasons.values()) != violation_count:
        raise ValueError("C1 violation reasons do not sum to violation_count")
    metrics = {
        "attemptCount": attempt_count,
        "validCount": valid_count,
        "violationCount": violation_count,
        "violationsByReason": reasons,
    }
    if attempt_count == 0:
        return {
            "status": "NOT_OBSERVED",
            "reason": "no core run_attempts rows were present; safety was not exercised",
            "metrics": metrics,
        }
    if violation_count:
        return {
            "status": "MEASURED_FAIL",
            "reason": "one or more attempts violated the core C1 approval boundary",
            "metrics": metrics,
        }
    return {
        "status": "MEASURED_PASS",
        "reason": "every observed attempt satisfied core C1",
        "metrics": metrics,
    }


def evaluate_outbox_summary(summary: dict[str, int] | None) -> dict[str, Any]:
    """Record O1 without treating DB rows as deployed publisher evidence.

    A failed or stale row is a directly observed failure. A clean aggregate is
    reference-only until a publisher/consumer deployment identity is bound;
    the criteria document explicitly lists that producer as preceding O1.
    """
    if summary is None:
        return {
            "status": "NOT_OBSERVED",
            "reason": "no explicit observation window was supplied",
            "metrics": None,
        }
    metrics = {
        "eventCount": int(summary.get("event_count", 0)),
        "publishedCount": int(summary.get("published_count", 0)),
        "failedCount": int(summary.get("failed_count", 0)),
        "stalePendingCount": int(summary.get("stale_pending_count", 0)),
        "maxPublishAttempts": int(summary.get("max_publish_attempts", 0)),
    }
    if any(value < 0 for value in metrics.values()):
        raise ValueError("outbox counts cannot be negative")
    if metrics["publishedCount"] + metrics["failedCount"] > metrics["eventCount"]:
        raise ValueError("outbox terminal counts exceed eventCount")
    if metrics["eventCount"] == 0:
        return {
            "status": "NOT_OBSERVED",
            "reason": "the observation window contained no outbox events",
            "metrics": metrics,
        }
    if metrics["failedCount"] or metrics["stalePendingCount"]:
        return {
            "status": "MEASURED_FAIL",
            "reason": "failed or older-than-10-minute pending outbox rows were observed",
            "metrics": metrics,
        }
    if metrics["publishedCount"] < 100:
        return {
            "status": "NOT_OBSERVED",
            "reason": "published denominator is below the preregistered 100-event minimum",
            "metrics": metrics,
        }
    return {
        "status": "RECORDED_ONLY",
        "reason": "clean DB aggregate is reference-only until publisher and consumer deployment identity is bound",
        "metrics": metrics,
    }


def default_unobserved() -> dict[str, dict[str, Any]]:
    """Every unbound safety claim is explicit; none is silently assumed true."""
    return {
        "O2": {
            "status": "NOT_OBSERVED",
            "reason": "broker redelivery and E1 effect identity input absent",
        },
        "O4": {
            "status": "NOT_OBSERVED",
            "reason": "independent request fingerprint producer is not deployed",
        },
        "O5": {
            "status": "BLOCKED_EXTERNAL",
            "reason": "physical Node resume evidence G-19/G-24 absent",
        },
        "O6": {
            "status": "NOT_REGISTERED",
            "reason": "audited bounded outbox disposition command does not exist",
        },
        "O7": {
            "status": "NOT_OBSERVED",
            "reason": "collect_rls_evidence output is not bound to this snapshot",
        },
        "O8": {
            "status": "NOT_OBSERVED",
            "reason": "two-point audit/grant snapshots were not supplied; O8 is record-only",
        },
        "O8_PRIME": {
            "status": "NOT_REGISTERED",
            "reason": "continuous DB audit/change-feed integrity source is absent",
        },
        "O9": {
            "status": "NOT_REGISTERED",
            "reason": "traceId denial probe has not been implemented",
        },
        "O10": {
            "status": "NOT_REGISTERED",
            "reason": "D1 retention and D5 deletion executor are undecided",
        },
        "O11": {
            "status": "BLOCKED_EXTERNAL",
            "reason": "operational backup G-21 and D6 RPO/RTO declaration absent",
        },
        "O12": {
            "status": "BLOCKED_EXTERNAL",
            "reason": "Tier-A PITR/off-device drill G-22 remains deferred",
        },
        "O13": {
            "status": "BLOCKED_EXTERNAL",
            "reason": "product GC cycle and G-20 pin evidence absent",
        },
    }


def overall_verdict(observations: dict[str, dict[str, Any]]) -> str:
    for item in observations.values():
        if item.get("status") not in STATUSES:
            raise ValueError(f"unknown observation status: {item.get('status')!r}")
    if any(item["status"] == "MEASURED_FAIL" for item in observations.values()):
        return "FAIL"
    if all(
        observations.get(key, {}).get("status") == "MEASURED_PASS" for key in REQUIRED_OBSERVATIONS
    ):
        return "PASS"
    return "NOT_OBSERVED"


def _database_identity(conn) -> dict[str, Any]:
    row = conn.execute(
        """
        SELECT current_database() AS database_name,
               (SELECT oid::text FROM pg_database WHERE datname = current_database()) AS database_oid,
               current_setting('server_version_num') AS server_version_num,
               current_setting('transaction_isolation') AS transaction_isolation,
               current_setting('transaction_read_only') AS transaction_read_only,
               txid_current_snapshot()::text AS snapshot_id,
               (SELECT version_num FROM alembic_version LIMIT 1) AS migration_head,
               clock_timestamp() AS observed_at
        """
    ).fetchone()
    system_identifier = conn.execute(
        "SELECT system_identifier::text AS system_identifier FROM pg_control_system()"
    ).fetchone()["system_identifier"]
    raw_identity = "\0".join((system_identifier, row["database_name"], row["database_oid"]))
    return {
        "databaseIdentitySha256": _sha256_text(raw_identity),
        "databaseNameSha256": _sha256_text(row["database_name"]),
        "systemIdentifierObserved": True,
        "databaseOid": row["database_oid"],
        "serverVersionNum": row["server_version_num"],
        "migrationHead": row["migration_head"],
        "transactionIsolation": row["transaction_isolation"],
        "transactionReadOnly": row["transaction_read_only"],
        "snapshotSha256": _sha256_text(row["snapshot_id"]),
        "observedAt": _iso(row["observed_at"]),
    }


def collect_database(dsn: str, *, window_start: dt.datetime | None = None) -> dict[str, Any]:
    """Read one target DB in a repeatable-read, read-only transaction."""
    import psycopg
    from psycopg.rows import dict_row

    dsn = dsn.replace("postgresql+psycopg://", "postgresql://", 1)
    with psycopg.connect(dsn, row_factory=dict_row) as conn:
        conn.execute("SET TRANSACTION ISOLATION LEVEL REPEATABLE READ, READ ONLY")
        conn.execute("SET LOCAL statement_timeout = '30s'")
        identity = _database_identity(conn)
        started_at = conn.execute("SELECT clock_timestamp() AS value").fetchone()["value"]
        c1_summary = dict(conn.execute(C1_SQL).fetchone())
        finished_at = conn.execute("SELECT clock_timestamp() AS value").fetchone()["value"]
        outbox_summary = None
        if window_start is not None:
            outbox_summary = dict(
                conn.execute(
                    OUTBOX_SQL,
                    {"started_at": window_start, "finished_at": finished_at},
                ).fetchone()
            )
        conn.rollback()
    return {
        "identity": identity,
        "sourceStartedAt": _iso(started_at),
        "sourceFinishedAt": _iso(finished_at),
        "windowStartedAt": _iso(window_start) if window_start else None,
        "c1": c1_summary,
        "outbox": outbox_summary,
    }


def _collect_provenance_at_root(executor: str) -> dict[str, Any]:
    previous = os.getcwd()
    os.chdir(REPO_ROOT)
    try:
        return collect_provenance(executor=executor)
    finally:
        os.chdir(previous)


def build_evidence(
    *, database: dict[str, Any], provenance: dict[str, Any], source_env: str
) -> dict[str, Any]:
    observations = default_unobserved()
    observations["O1"] = evaluate_outbox_summary(database.get("outbox"))
    observations["O3"] = evaluate_c1_summary(database["c1"])
    verdict = overall_verdict(observations)
    collector_sha = hashlib.sha256(Path(__file__).read_bytes()).hexdigest()
    binding = {
        "codeSha": provenance.get("commit_sha"),
        "collectorSha256": collector_sha,
        "databaseIdentitySha256": database["identity"]["databaseIdentitySha256"],
        "snapshotSha256": database["identity"]["snapshotSha256"],
        "sourceStartedAt": database["sourceStartedAt"],
        "sourceFinishedAt": database["sourceFinishedAt"],
        "windowStartedAt": database.get("windowStartedAt"),
    }
    evidence = {
        "schemaVersion": SCHEMA_VERSION,
        "taskIds": ["S04-DB", "S08-DB"],
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
            "kind": "core-postgresql",
            "dsnEnvironment": source_env,
            "sourceStartedAt": database["sourceStartedAt"],
            "sourceFinishedAt": database["sourceFinishedAt"],
            "windowStartedAt": database.get("windowStartedAt"),
            "database": database["identity"],
            "inputBindingSha256": _sha256_text(
                json.dumps(binding, sort_keys=True, separators=(",", ":"))
            ),
        },
        "observations": observations,
        "excludedBoundaries": {
            "C1-K": {
                "status": "NOT_OBSERVED",
                "reason": "kernel inv.approval_requests recovery_epoch/bound_run_version is a separate collector contract",
            }
        },
    }
    validate_evidence(evidence)
    return evidence


def validate_evidence(evidence: dict[str, Any]) -> None:
    if evidence.get("schemaVersion") != SCHEMA_VERSION:
        raise ValueError("schemaVersion mismatch")
    if not re.fullmatch(r"[0-9a-f]{40}", str(evidence.get("codeSha") or "")):
        raise ValueError("codeSha must be an exact 40-hex commit")
    if evidence.get("criteria") != {
        "version": CRITERIA_VERSION,
        "sourceHead": CRITERIA_HEAD,
        "path": CRITERIA_PATH,
    }:
        raise ValueError("criteria binding mismatch")
    provenance = evidence.get("provenance") or {}
    if provenance.get("workingTreeClean") is not True or provenance.get("contentClean") is not True:
        raise ValueError("evidence source tree must be clean")
    source = evidence.get("source") or {}
    database = source.get("database") or {}
    for key in ("databaseIdentitySha256", "databaseNameSha256", "snapshotSha256"):
        if not _SHA256.fullmatch(str(database.get(key) or "")):
            raise ValueError(f"missing or invalid database binding: {key}")
    if database.get("systemIdentifierObserved") is not True:
        raise ValueError("database system identifier was not observed")
    if not _SHA256.fullmatch(str(source.get("inputBindingSha256") or "")):
        raise ValueError("input binding is missing")
    started = parse_timestamp(source.get("sourceStartedAt"))
    finished = parse_timestamp(source.get("sourceFinishedAt"))
    if started is None or finished is None or started > finished:
        raise ValueError("source timestamps are reversed")
    if (evidence.get("excludedBoundaries") or {}).get("C1-K", {}).get("status") != "NOT_OBSERVED":
        raise ValueError("C1-K must remain explicitly excluded")
    if evidence.get("verdict") != overall_verdict(evidence.get("observations") or {}):
        raise ValueError("verdict was not recomputed from observations")


def _secret_values() -> list[str]:
    values: list[str] = []
    for key in ("INV_AUDIT_DSN", "INV_TEST_DATABASE_URL", "INV_TEST_ADMIN_DSN", "INV_DATABASE_URL"):
        value = os.environ.get(key)
        if not value:
            continue
        values.append(value)
        match = re.search(r"://[^:/]+:([^@]+)@", value)
        if match:
            values.append(match.group(1))
    return [value for value in values if value]


def assert_no_secrets(text: str) -> None:
    for value in _secret_values():
        if value in text:
            raise ValueError("evidence would contain a DSN or credential")


def render_markdown(evidence: dict[str, Any]) -> str:
    source = evidence["source"]
    lines = [
        "# S04-DB / S08-DB operational evidence",
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
    for key in sorted(evidence["observations"]):
        item = evidence["observations"][key]
        lines.append(f"| {key.replace('_PRIME', '′')} | **{item['status']}** | {item['reason']} |")
    lines += [
        "",
        "- C1-K kernel recovery-epoch/bound-run-version boundary: **NOT_OBSERVED** (separate collector).",
        "- No DSN, hostname, database name, tenant/run/attempt id, approval id, payload or raw error is stored.",
    ]
    return "\n".join(lines) + "\n"


def write_evidence(evidence: dict[str, Any], out_dir: Path, label: str) -> tuple[Path, Path]:
    out_dir.mkdir(parents=True, exist_ok=True)
    json_path = out_dir / f"{label}.json"
    markdown_path = out_dir / f"{label}.md"
    if json_path.exists() or markdown_path.exists():
        raise ValueError("refusing to overwrite existing evidence")
    json_text = json.dumps(evidence, ensure_ascii=False, indent=2, sort_keys=True) + "\n"
    markdown_text = render_markdown(evidence)
    assert_no_secrets(json_text)
    assert_no_secrets(markdown_text)
    json_path.write_text(json_text, encoding="utf-8")
    markdown_path.write_text(markdown_text, encoding="utf-8")
    return json_path, markdown_path


EXIT_BY_VERDICT = {"PASS": 0, "FAIL": 1, "NOT_OBSERVED": 3}


def parser() -> argparse.ArgumentParser:
    result = argparse.ArgumentParser(description=__doc__.split("\n\n", 1)[0])
    result.add_argument(
        "--dsn-env", choices=("INV_AUDIT_DSN", "INV_TEST_DATABASE_URL"), default="INV_AUDIT_DSN"
    )
    result.add_argument("--window-start", help="RFC3339 start of the O1 operational window")
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
        window_start = parse_timestamp(args.window_start)
        database = collect_database(dsn, window_start=window_start)
        evidence = build_evidence(database=database, provenance=provenance, source_env=args.dsn_env)
        label = args.label or (
            f"s04-s08-operational-{evidence['codeSha'][:12]}-"
            f"{dt.datetime.now(dt.timezone.utc):%Y%m%dT%H%M%SZ}"
        )
        json_path, markdown_path = write_evidence(evidence, args.out_dir, label)
    except Exception as error:
        # Database errors can echo connection details. Preserve only the class
        # in terminal output; raw failures are never evidence.
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
