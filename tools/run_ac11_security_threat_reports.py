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
do for their own evidence.  That database's ``public.audit_events`` is **seeded first**, through
the product's own writers as ``inv_app`` (see :data:`AUDIT_SEED_PATH`): with an empty audit table
the role visibility cells for it compared no rows with no rows, so "this role cannot see the
other tenant's rows" was true of nothing (card 236).  Nothing is written to an operational database and no DSN,
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
import re
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

#: The seed path for ``public.audit_events``, named here because it is the whole point of the
#: seed: the rows have to be ones **the product itself could have written** (card 236).
#:
#: ``audit_events`` was empty in every disposable database this producer measured, so the role
#: visibility cells for that table compared *no rows with no rows*: "this role sees none of the
#: other tenant's rows" was true because there were none at all.  The fix is rows, and the only
#: honest way to get them is the application's own writers under the application's own role:
#:
#: * ``saintvision.services.audit.record_denial_out_of_band(engine, tenant_id=...)`` -- what the
#:   API calls for an authorisation denial that resolved a principal.  It opens its own
#:   transaction, sets the tenant scope and inserts through the ORM.
#: * ``saintvision.services.audit.record_event(session, ...)`` inside
#:   ``saintvision.db.session.tenant_scope`` -- what a request transaction calls for an allow.
#:
#: Both go through ``audit_events_tenant_isolation`` (0047), whose ``WITH CHECK`` is
#: ``tenant_id = current_setting('inv.tenant_id')``.  Nothing here grants a privilege, excludes a
#: role, relaxes a definition or inserts a row around a policy; ``_prove_policy_enforced`` fails
#: the whole observation closed if the write turns out **not** to be policy-enforced.
AUDIT_SEED_TABLE = "public.audit_events"
AUDIT_SEED_PATH = (
    "saintvision.services.audit.record_denial_out_of_band + "
    "record_event under saintvision.db.session.tenant_scope, as inv_app"
)
#: Two rows per tenant -- one denial, one allow -- so "this role sees two of the four rows" is a
#: statement about rows that exist, in both directions, for two different tenants.
AUDIT_SEED_ROWS_PER_TENANT = 2
APP_ROLE = "inv_app"
#: The policy that must be the one doing the refusing, and the exact refusal that proves it.
#:
#: Measured against PostgreSQL 16 (0047's policy, the write of another tenant's row under this
#: tenant's scope): ``sqlalchemy.exc.ProgrammingError`` wrapping
#: ``psycopg.errors.InsufficientPrivilege``, ``sqlstate`` **42501**, message ``new row violates
#: row-level security policy for table "audit_events"`` -- ``diag.table_name`` is not populated for
#: this error, so the table comes from the message.  Any *other* error is not a proof: a sqlite
#: engine, a typo, a missing table or a dropped connection all raise ``DBAPIError`` too, and taking
#: them as "the policy refused" would certify an unenforced seed (#334 r1).
AUDIT_SEED_POLICY = "audit_events_tenant_isolation"
RLS_REFUSAL_SQLSTATE = "42501"
RLS_REFUSAL_RE = re.compile(
    r'^new row violates row-level security policy(?: "(?P<policy>[^"]+)")?'
    r' for table "(?P<table>[^"]+)"'
)

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


def _app_engine(dsn: str):
    """A SQLAlchemy engine whose every connection **is** the application role.

    The DSN this lane uses has to create and drop a database, so it is an owner or superuser --
    and a superuser bypasses every policy, which would make a seeded row one the product could
    not have written.  ``SET ROLE`` on connect is how ``collect_rls_evidence`` already measures
    each role's own view from this same DSN, and it is what puts these writes *through*
    ``audit_events_tenant_isolation`` rather than around it.
    """

    from psycopg.conninfo import conninfo_to_dict
    from sqlalchemy import create_engine, event
    from sqlalchemy.engine import URL
    from sqlalchemy.pool import NullPool

    info = conninfo_to_dict(dsn)
    url = URL.create(
        "postgresql+psycopg",
        username=info.get("user"),
        password=info.get("password"),
        host=info.get("host"),
        port=int(info.get("port", 5432)),
        database=info.get("dbname"),
    )
    engine = create_engine(url, future=True, poolclass=NullPool)

    @event.listens_for(engine, "connect")
    def _become_the_application(dbapi_connection, _record):  # noqa: ANN001, ARG001
        with dbapi_connection.cursor() as cursor:
            # Part of the proof that the policy refused is PostgreSQL's own wording, which the
            # server translates, so the probe asks for the untranslated messages first.  It is
            # ``PGC_SUSET`` and this DSN may not be a superuser, so a refusal here is not fatal:
            # the wording check then fails on a translated message and the producer records the
            # observation as unavailable rather than claiming an unproved seed (#334 r1).
            try:
                cursor.execute("SET lc_messages = 'C'")
            except Exception:  # noqa: BLE001 - the SQLSTATE check still applies either way
                dbapi_connection.rollback()
            cursor.execute(f"SET ROLE {APP_ROLE}")

    return engine


def _seed_tenants(dsn: str) -> list[tuple[str, str]]:
    """``(tenant_id, project_id)`` for the two tenants the disposable database was seeded with."""

    import psycopg

    with psycopg.connect(dsn) as conn:
        rows = conn.execute(
            "SELECT p.tenant_id::text, p.project_id FROM public.projects p "
            "JOIN public.tenants t ON t.tenant_id = p.tenant_id ORDER BY p.tenant_id"
        ).fetchall()
    tenants: dict[str, str] = {}
    for tenant_id, project_id in rows:
        tenants.setdefault(str(tenant_id), str(project_id))
    if len(tenants) < 2:
        raise ProducerError(
            f"the disposable database has {len(tenants)} tenant(s) with a project; "
            "a cross-tenant audit observation needs two"
        )
    return sorted(tenants.items())[:2]


def rls_refusal(error: Any, table: str, policy: str) -> str:
    """PostgreSQL's own RLS refusal for that table, or ``ProducerError``.

    What makes this a proof is **which** refusal it is: SQLSTATE ``42501`` *and* the row-level
    security wording *and* the table named in it -- and, when the server names the policy, that
    policy.  Accepting any ``DBAPIError`` instead proved nothing at all: a sqlite engine, a typo, a
    missing table or a dropped connection raise one too, so an unenforced seed would have been
    certified as enforced (#334 r1).

    The refusal text is returned so the History can quote the database's own words; nothing else
    from the exception is, because a connection failure's message can carry host and user.
    """

    sqlstate = getattr(error, "sqlstate", None)
    first_line = str(error).strip().splitlines()[0] if str(error).strip() else ""
    detail = f"{type(error).__name__} sqlstate={sqlstate!r}"
    if sqlstate != RLS_REFUSAL_SQLSTATE:
        raise ProducerError(
            f"the cross-tenant write failed with {detail}, which is not a row-level security "
            f"refusal; no visibility measurement is recorded"
        )
    match = RLS_REFUSAL_RE.match(first_line)
    if match is None:
        raise ProducerError(
            f"the cross-tenant write failed with {detail} but not with PostgreSQL's row-level "
            f"security wording; no visibility measurement is recorded"
        )
    named_table = match.group("table")
    if named_table not in (table, table.split(".")[-1]):
        raise ProducerError(
            f"the row-level security refusal names table {named_table!r}, not {table!r}; "
            f"no visibility measurement is recorded"
        )
    named_policy = match.group("policy")
    if named_policy is not None and named_policy != policy:
        raise ProducerError(
            f"the row-level security refusal names policy {named_policy!r}, not {policy!r}; "
            f"no visibility measurement is recorded"
        )
    return first_line[:200]


def _prove_policy_enforced(engine, tenant: str, foreign_tenant: str, now) -> str:
    """Write one row of the *other* tenant under this tenant's scope and require a refusal.

    Without this the seed could be silently writing as a role that bypasses RLS, and then every
    visibility cell measured afterwards would be about rows no policy ever checked -- a vacuous
    PASS of a different shape.  :func:`rls_refusal` decides whether what came back is that policy
    refusing; its words are returned so the History can quote the database.
    """

    import uuid as _uuid

    from sqlalchemy.exc import DBAPIError
    from sqlalchemy.orm import sessionmaker

    from saintvision.db.session import tenant_scope
    from saintvision.services.audit import record_event

    factory = sessionmaker(bind=engine, expire_on_commit=False)
    try:
        with factory() as session:
            with session.begin():
                with tenant_scope(session, tenant):
                    record_event(
                        session,
                        now=now,
                        actor_type="system",
                        action="ac11.audit_seed.cross_tenant_probe",
                        outcome="deny",
                        tenant_id=_uuid.UUID(foreign_tenant),
                        reason_code="AC11-SEED-PROBE",
                    )
    except DBAPIError as refusal:
        return rls_refusal(
            getattr(refusal, "orig", None) or refusal, AUDIT_SEED_TABLE, AUDIT_SEED_POLICY
        )
    raise ProducerError(
        "the seed path wrote another tenant's audit row, so it is not policy-enforced; "
        "no visibility measurement is recorded"
    )


def seed_audit_rows(dsn: str) -> dict[str, Any]:
    """Representative ``public.audit_events`` rows for two tenants, by the product's own writers.

    See :data:`AUDIT_SEED_PATH`.  Returns a summary for the run log and the History; the threat
    report's shape is unchanged, so the evaluator's contract is untouched.

    Fails closed: a seed that cannot be written, that writes the wrong number of rows, that adds a
    tenant-less row, or that turns out **not** to be policy-enforced raises ``ProducerError`` and
    the caller records the observation as unavailable rather than as a pass over an empty table.
    """

    import uuid as _uuid

    import psycopg

    if str(ROOT / "src") not in sys.path:
        sys.path.insert(0, str(ROOT / "src"))

    from sqlalchemy.orm import sessionmaker

    from saintvision.db.session import tenant_scope
    from saintvision.services.audit import record_denial_out_of_band, record_event

    pairs = _seed_tenants(dsn)
    now = dt.datetime.now(dt.timezone.utc)
    engine = _app_engine(dsn)
    written: dict[str, int] = {}
    try:
        factory = sessionmaker(bind=engine, expire_on_commit=False)
        for tenant_id, project_id in pairs:
            # 1. The denial path: the product's own out-of-band writer, which sets the scope
            #    itself because no request transaction is open.
            record_denial_out_of_band(
                engine,
                now=now,
                actor_type="user",
                # ``audit_events.action`` is varchar(64); these are the bounded template
                # actions the API records, not free text.
                action="POST /v1/projects/{project_id}/models/{model_id}/release",
                outcome="deny",
                tenant_id=_uuid.UUID(tenant_id),
                actor_id="usr_AC11AUDITSEED",
                reason_code="AUTH-0030",
                target_type="project",
                target_id=project_id,
            )
            # 2. The allow path: what a request transaction records, inside the same scope.
            with factory() as session:
                with session.begin():
                    with tenant_scope(session, tenant_id):
                        record_event(
                            session,
                            now=now,
                            actor_type="user",
                            action="GET /v1/projects/{project_id}",
                            outcome="allow",
                            tenant_id=_uuid.UUID(tenant_id),
                            actor_id="usr_AC11AUDITSEED",
                            target_type="project",
                            target_id=project_id,
                        )
            written[tenant_id] = AUDIT_SEED_ROWS_PER_TENANT
        refusal = _prove_policy_enforced(engine, pairs[0][0], pairs[1][0], now)
    except ProducerError:
        raise
    except Exception as error:  # noqa: BLE001 - driver messages can carry the DSN
        raise ProducerError(f"audit seed failed: {type(error).__name__}") from None
    finally:
        engine.dispose()

    # The owner counts what is there.  The seed is only usable evidence if it is exactly the rows
    # it meant to write: two per tenant, nothing tenant-less, nothing for a third tenant.
    with psycopg.connect(dsn) as conn:
        counted = dict(
            conn.execute(
                "SELECT coalesce(tenant_id::text,'<null>'), count(*) FROM public.audit_events "
                "GROUP BY 1 ORDER BY 1"
            ).fetchall()
        )
    expected = {tenant_id: AUDIT_SEED_ROWS_PER_TENANT for tenant_id, _ in pairs}
    if counted != expected:
        raise ProducerError(
            "the seeded audit rows are not what was written "
            f"(expected {len(expected)} tenants x {AUDIT_SEED_ROWS_PER_TENANT}, "
            f"counted {sorted(counted.values())} over {len(counted)} group(s))"
        )
    return {
        "table": AUDIT_SEED_TABLE,
        "path": AUDIT_SEED_PATH,
        "role": APP_ROLE,
        "tenants": [tenant_id for tenant_id, _ in pairs],
        "rowsPerTenant": AUDIT_SEED_ROWS_PER_TENANT,
        "crossTenantWriteRefusedWith": refusal,
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


def reviewed_baseline(allowlist: dict[str, Any]) -> dict[str, Any]:
    """The reviewed dispositions in the shape ``collect_rls_evidence.apply_baseline`` takes.

    The report's ``baselineAccepted`` says which dispositions the measurement was judged against,
    and ``evaluate_rls`` requires that list to equal the reviewed allowlist exactly -- then
    separately refuses any ``accepted`` row whose (role, table, rule) is **not** in that list.  So
    judging with the collector's own baseline file, which is a superset maintained for the S02-DB
    lane, made the report state one thing and do another: with ``public.audit_events`` seeded
    (card 236) the superset's fourth entry accepted three real cross-tenant observations the
    reviewed allowlist does not mention, the report still claimed PASS against three dispositions,
    and the evaluator answered INVALID_RUN -- neither a PASS nor a FAIL of anything.

    This is the same list in both places.  Nothing is widened: an exception the reviewed allowlist
    does not carry is a violation here, which is what the evaluator already assumed.
    """

    return {
        "accepted": [
            {
                "role": entry["role"],
                "table": entry["table"],
                "rules": list(entry["rules"]),
                "reason": str(entry["proof"]),
                "since": str(entry["disposition"]),
            }
            for entry in allowlist["rlsAcceptedDispositions"]
        ]
    }


def rls_report(dsn: str | None, tenant: str | None, allowlist: dict[str, Any]) -> dict[str, Any]:
    """SEC-RLS-001 in the shape ``evaluate_rls`` reads.

    ``baselineAccepted`` states which reviewed dispositions this measurement was judged
    against, and the aggregator requires it to equal the reviewed allowlist exactly -- so it
    is taken from that allowlist rather than from the collector's own baseline file, which is
    a superset maintained for the S02-DB lane.  Since card 236 the **judgement** uses that same
    reviewed list (see :func:`reviewed_baseline`), so the report is judged by what it says it was
    judged by.  Every other field is the collector's output.
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
    baseline = reviewed_baseline(allowlist)
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
        # The collector's catalogue census travels with the report: the evaluator binds it to the
        # reviewed table list, so the population a verdict covers is not the report's own choice
        # (#322 r2 F-R7).
        "table_census": observation["table_census"],
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
            # The audit table is seeded *before* anything is measured, and a seed that cannot be
            # written -- or that turns out not to be policy-enforced -- makes the observation
            # unavailable.  An empty audit table measures nothing and must not read as a pass
            # (card 236).
            seed = seed_audit_rows(dsn)
            print(
                "audit seed: {tenants} tenants x {rows} rows via {path}; "
                "cross-tenant write refused with: {refusal}".format(
                    tenants=len(seed["tenants"]), rows=seed["rowsPerTenant"],
                    path=seed["path"], refusal=seed["crossTenantWriteRefusedWith"],
                ),
                file=sys.stderr,
            )
            definer = definer_report(dsn)
            boundary = rls_report(dsn, tenant_a, allowlist)
    except ProducerError as refused:
        print(f"audit seed refused: {refused}", file=sys.stderr)
        return emit(definer_report(None), rls_report(None, None, allowlist))
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
