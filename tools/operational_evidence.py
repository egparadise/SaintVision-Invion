"""Shared skeleton for operational-verdict collectors.

The S04/S08 collector (card 123) established this shape and it is the one
contract every later operational collector reuses: a verdict is recomputed from
per-observation statuses, an observation nobody measured stays explicitly
unmeasured, and the numbers are bound to a committed code SHA, the collector's
own bytes, a database identity and a transaction snapshot -- without recording a
DSN, a database name, a host, a row id or a secret.

It holds only what is task-independent.  The SQL, the per-observation
evaluators, the unmeasured defaults and the Markdown rendering belong to each
collector, because those are the parts that differ.

``STATUSES`` is the closed set every collector may use:

* ``MEASURED_PASS``   -- measured, and the pre-registered threshold held.
* ``MEASURED_FAIL``   -- measured, and it did not.
* ``NOT_OBSERVED``    -- the input exists in principle but was not supplied.
* ``NOT_REGISTERED``  -- the producer does not exist in this revision.
* ``BLOCKED_EXTERNAL``-- an external precondition (G-xx) is missing.
* ``RECORDED_ONLY``   -- recorded for later comparison; not a verdict.

Only ``MEASURED_PASS`` on every required observation yields ``PASS``; any
``MEASURED_FAIL`` yields ``FAIL``; anything else is ``NOT_OBSERVED``.  There is
no path by which an unmeasured observation reaches a pass.
"""

from __future__ import annotations

import datetime as dt
import hashlib
import json
import os
from pathlib import Path
import re
import sys
from typing import Any, Callable, Iterable, Sequence


REPO_ROOT = Path(__file__).resolve().parents[1]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from tools.provenance import collect as collect_provenance  # noqa: E402


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

EXIT_BY_VERDICT = {"PASS": 0, "FAIL": 1, "NOT_OBSERVED": 3}

SHA256_PATTERN = re.compile(r"^[0-9a-f]{64}$")
COMMIT_PATTERN = re.compile(r"^[0-9a-f]{40}$")
LABEL_PATTERN = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._-]{0,127}$")

#: Environment variables that may hold a DSN. Their values -- and the password
#: inside them -- must never reach an evidence file.
DSN_ENVIRONMENT_NAMES = (
    "INV_AUDIT_DSN",
    "INV_TEST_DATABASE_URL",
    "INV_TEST_ADMIN_DSN",
    "INV_DATABASE_URL",
)


def sha256_text(value: str) -> str:
    return hashlib.sha256(value.encode("utf-8")).hexdigest()


def iso(value: dt.datetime) -> str:
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


def overall_verdict(
    observations: dict[str, dict[str, Any]], required: Sequence[str] | Iterable[str]
) -> str:
    """Recompute the verdict. An unknown status is a defect, not a pass."""
    for item in observations.values():
        if item.get("status") not in STATUSES:
            raise ValueError(f"unknown observation status: {item.get('status')!r}")
    if any(item["status"] == "MEASURED_FAIL" for item in observations.values()):
        return "FAIL"
    if all(observations.get(key, {}).get("status") == "MEASURED_PASS" for key in required):
        return "PASS"
    return "NOT_OBSERVED"


def database_identity(conn) -> dict[str, Any]:
    """Identify the observed database without naming it.

    The name and the cluster's system identifier are hashed, so two evidence
    files can be compared for "same database" without either disclosing which.
    """
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
        "databaseIdentitySha256": sha256_text(raw_identity),
        "databaseNameSha256": sha256_text(row["database_name"]),
        "systemIdentifierObserved": True,
        "databaseOid": row["database_oid"],
        "serverVersionNum": row["server_version_num"],
        "migrationHead": row["migration_head"],
        "transactionIsolation": row["transaction_isolation"],
        "transactionReadOnly": row["transaction_read_only"],
        "snapshotSha256": sha256_text(row["snapshot_id"]),
        "observedAt": iso(row["observed_at"]),
    }


def normalise_dsn(dsn: str) -> str:
    return dsn.replace("postgresql+psycopg://", "postgresql://", 1)


def collect_provenance_at_root(executor: str) -> dict[str, Any]:
    previous = os.getcwd()
    os.chdir(REPO_ROOT)
    try:
        return collect_provenance(executor=executor)
    finally:
        os.chdir(previous)


def collector_sha256(module_file: str | Path) -> str:
    return hashlib.sha256(Path(module_file).read_bytes()).hexdigest()


def input_binding_sha256(binding: dict[str, Any]) -> str:
    return sha256_text(json.dumps(binding, sort_keys=True, separators=(",", ":")))


def secret_values() -> list[str]:
    values: list[str] = []
    for key in DSN_ENVIRONMENT_NAMES:
        value = os.environ.get(key)
        if not value:
            continue
        values.append(value)
        match = re.search(r"://[^:/]+:([^@]+)@", value)
        if match:
            values.append(match.group(1))
    return [value for value in values if value]


def assert_no_secrets(text: str) -> None:
    for value in secret_values():
        if value in text:
            raise ValueError("evidence would contain a DSN or credential")


def validate_common(
    evidence: dict[str, Any],
    *,
    schema_version: str,
    criteria: dict[str, str],
    required: Sequence[str] | Iterable[str],
) -> None:
    """The checks that hold for every collector, in one place.

    A collector adds its own checks on top; it never replaces these.
    """
    if evidence.get("schemaVersion") != schema_version:
        raise ValueError("schemaVersion mismatch")
    if not COMMIT_PATTERN.fullmatch(str(evidence.get("codeSha") or "")):
        raise ValueError("codeSha must be an exact 40-hex commit")
    if evidence.get("criteria") != criteria:
        raise ValueError("criteria binding mismatch")
    provenance = evidence.get("provenance") or {}
    if provenance.get("workingTreeClean") is not True or provenance.get("contentClean") is not True:
        raise ValueError("evidence source tree must be clean")
    source = evidence.get("source") or {}
    database = source.get("database") or {}
    for key in ("databaseIdentitySha256", "databaseNameSha256", "snapshotSha256"):
        if not SHA256_PATTERN.fullmatch(str(database.get(key) or "")):
            raise ValueError(f"missing or invalid database binding: {key}")
    if database.get("systemIdentifierObserved") is not True:
        raise ValueError("database system identifier was not observed")
    if not SHA256_PATTERN.fullmatch(str(source.get("inputBindingSha256") or "")):
        raise ValueError("input binding is missing")
    started = parse_timestamp(source.get("sourceStartedAt"))
    finished = parse_timestamp(source.get("sourceFinishedAt"))
    if started is None or finished is None or started > finished:
        raise ValueError("source timestamps are reversed")
    observations = evidence.get("observations") or {}
    if evidence.get("verdict") != overall_verdict(observations, required):
        raise ValueError("verdict was not recomputed from observations")
    if evidence.get("acceptanceClaim") is not (evidence.get("verdict") == "PASS"):
        raise ValueError("acceptanceClaim must follow the recomputed verdict")


def write_evidence(
    evidence: dict[str, Any],
    out_dir: Path,
    label: str,
    *,
    render_markdown: Callable[[dict[str, Any]], str],
) -> tuple[Path, Path]:
    """Write the pair, refusing to overwrite and refusing to leak a secret."""
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


def default_label(prefix: str, code_sha: str) -> str:
    return f"{prefix}-{code_sha[:12]}-{dt.datetime.now(dt.timezone.utc):%Y%m%dT%H%M%SZ}"
