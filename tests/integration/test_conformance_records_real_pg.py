"""Real PostgreSQL for conformance records (G-03 stage two, design #218 v1.2 §5).

What a stand-in cannot establish is here, and nothing else:

* the producer writing through the **application role** and the read routes
  serving that row back (the whole seam, once, end to end);
* **T8** append-only: the application role has no UPDATE and no DELETE;
* **T2/T3** on the database: the CHECKs refuse counts that do not add up, a
  ``checks`` array of the wrong length, and any subject or provenance this
  stage does not produce;
* **T10** the latest record is per host and deterministic on ties;
* **T13** a stored row that passes every CHECK but breaks a reader invariant
  is refused with ``SYS-0002``/500/not retryable, both routes, fixed detail;
* **T15** with no host identity the read refuses even though rows exist;
* **T9** the denial reaching ``audit_events`` on the single route, an unknown
  adapter not being audited, and the anonymous 401;
* a lock this read waits on (an ``ACCESS EXCLUSIVE`` lock on the table held
  by another transaction) answered ``SYS-0001/503/retryable`` within the
  budget, not held open (card 103 addendum, two bounded spans);
* the migration's convergence shape matching what the DDL actually produced.

Response shape, model validation and the stand-in refusals are
``tests/core/test_conformance_status_route.py``; the producer's invariants are
``tests/core/test_conformance_records.py``. Both run everywhere.
"""

from __future__ import annotations

import datetime as dt
import importlib.util
import pathlib
import sys
import uuid

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import text
from sqlalchemy.exc import DBAPIError, IntegrityError, ProgrammingError

from saintvision.adapters import agents
from saintvision.adapters.conformance import CHECKLIST
from saintvision.adapters.contract import CONTRACT_VERSION
from saintvision.api.app import create_app
from saintvision.api.problem import CANONICAL_KEYS
from saintvision.api.v1 import conformance_status
from saintvision.config import Settings
from saintvision.identity.principal import Principal, StaticPrincipalVerifier
from saintvision.ids import new_id
from saintvision.services.conformance_records import record_fixture_conformance

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parents[1]))
from lock_wait_harness import within_deadline  # noqa: E402

pytestmark = pytest.mark.postgres

TOKEN = "conformance-records-token"
BUDGET_MS = 300
DEADLINE_SECONDS = 20
HOST = uuid.UUID("0f8fad5b-d9cb-469f-a165-70867728950e")
OTHER_HOST = uuid.UUID("7c9e6679-7425-40de-944b-e07fc1f90ae7")
TABLE = "adapter_conformance_records"
ROOT = pathlib.Path(__file__).resolve().parents[2]


def _insert(connection, table_name, **values):
    """Insert through the model metadata, so a wrong column cannot reach hosted CI."""
    from saintvision.db import models  # noqa: F401  (registers the tables)
    from saintvision.db.base import Base

    table = Base.metadata.tables[table_name]
    unknown = set(values) - set(table.columns.keys())
    assert not unknown, f"{table_name} has no column(s) {sorted(unknown)}"
    required = {
        column.name
        for column in table.columns
        if not column.nullable and column.default is None and column.server_default is None
    }
    assert required <= set(values), f"{table_name} needs {sorted(required - set(values))}"
    connection.execute(table.insert().values(**values))


def _seed(connection, *, tenant_id, now, label, role="requester"):
    user_id = new_id("user")
    project_id = new_id("project")
    _insert(
        connection,
        "users",
        user_id=user_id,
        tenant_id=tenant_id,
        external_subject=f"conformance-{label}",
        display_name=f"conformance-{label}",
        status="active",
        created_at=now,
        updated_at=now,
        version=1,
    )
    _insert(
        connection,
        "projects",
        project_id=project_id,
        tenant_id=tenant_id,
        code=label,
        display_name=label,
        status="active",
        created_at=now,
        version=1,
    )
    _insert(
        connection,
        "project_members",
        tenant_id=tenant_id,
        project_id=project_id,
        user_id=user_id,
        role_code=role,
    )
    return {"user_id": user_id, "project_id": project_id}


def _outcomes(*, failed=(), skipped=("declared_server_cancel_actually_stops",)):
    return [
        {
            "name": spec.name,
            "passed": spec.name not in failed and spec.name not in skipped,
            "skipped": spec.name in skipped,
        }
        for spec in CHECKLIST
    ]


def _well_formed(*, adapter, host_id, recorded_at, record_id=None, outcomes=None):
    """A row every CHECK and every reader invariant accepts."""
    checks = outcomes if outcomes is not None else _outcomes()
    return dict(
        record_id=record_id or new_id("conformance_record"),
        host_id=host_id,
        adapter=adapter,
        contract_version=CONTRACT_VERSION,
        suite_contract_version=CONTRACT_VERSION,
        subject="fixture-adapter",
        provenance="in-server",
        total=len(checks),
        passed=sum(1 for c in checks if c["passed"] and not c["skipped"]),
        failed=sum(1 for c in checks if not c["passed"] and not c["skipped"]),
        skipped=sum(1 for c in checks if c["skipped"]),
        checks=checks,
        recorded_at=recorded_at,
    )


def _store(connection, **kwargs):
    """Store one row as the owner, bypassing the producer. Returns the record id."""
    values = _well_formed(**kwargs)
    _insert(connection, TABLE, **values)
    return values["record_id"]


#: T13. Each passes the database's own CHECKs (length == total, counts add up,
#: subject and provenance allowed) and breaks exactly one reader invariant.
def _duplicate_names(values):
    checks = [dict(c, name=CHECKLIST[0].name) for c in values["checks"]]
    return {"checks": checks}


def _unknown_name(values):
    checks = [dict(c) for c in values["checks"]]
    checks[3]["name"] = "install_actually_installs"
    return {"checks": checks}


def _shuffled_order(values):
    checks = [dict(c) for c in values["checks"]]
    checks[0], checks[1] = checks[1], checks[0]
    return {"checks": checks}


def _passed_and_skipped(values):
    checks = [dict(c) for c in values["checks"]]
    # The skipped entry marked passed as well: counts still add up because
    # the row's passed count is recomputed here from the same list.
    checks[-3] = dict(checks[-3], passed=True, skipped=True)
    return {"checks": checks, "passed": 15 - 1, "skipped": 1, "failed": 0}


def _detail_smuggled(values):
    checks = [dict(c) for c in values["checks"]]
    checks[0]["detail"] = "Exception: /srv/cp token=abc"
    return {"checks": checks}


def _counts_swapped(values):
    # Adds up to total, but not to the outcomes: 13 passed + 2 failed + 0 skipped.
    return {"passed": 13, "failed": 2, "skipped": 0}


def _unknown_suite_version(values):
    return {"suite_contract_version": "0.9.0"}


def _empty_contract_version(values):
    # VARCHAR(32) NOT NULL admits '' -- the contract's min_length=1 does not
    # (Codex #221 F3). The reader must refuse before response assembly.
    return {"contract_version": ""}


TAMPERINGS = {
    "empty-contract-version": _empty_contract_version,
    "duplicate-names": _duplicate_names,
    "unknown-name": _unknown_name,
    "shuffled-order": _shuffled_order,
    "passed-and-skipped": _passed_and_skipped,
    "detail-smuggled": _detail_smuggled,
    "counts-swapped": _counts_swapped,
    "unknown-suite-version": _unknown_suite_version,
}


def _client(app_engine, *, tenant_id, user_id, now, host_id=HOST, lock_timeout_ms=5_000):
    principal = Principal(
        user_id=user_id, tenant_id=tenant_id, external_subject="conformance-records"
    )
    app = create_app(
        engine=app_engine,
        settings=Settings(
            database_url="test-only",
            control_plane_host_id=host_id,
            business_lock_timeout_ms=lock_timeout_ms,
        ),
        verifier=StaticPrincipalVerifier({TOKEN: principal}, allow_outside_dev=True),
        clock=lambda: now,
        check_partitions_on_startup=False,
    )
    return TestClient(app, raise_server_exceptions=False)


def _list_path(project_id):
    return f"/v1/projects/{project_id}/adapters/conformance"


def _one_path(project_id, name):
    return f"/v1/projects/{project_id}/adapters/{name}/conformance"


def _get(client, path, *, token=TOKEN):
    headers = {"Authorization": f"Bearer {token}"} if token else {}
    return client.get(path, headers=headers)


def _canonical(response, *, code, status, retryable=False):
    assert response.status_code == status, response.text
    body = response.json()
    assert set(body) == set(CANONICAL_KEYS), body
    assert body["type"] == "about:blank"
    assert body["code"] == code
    assert body["retryable"] is retryable
    return body


def _denials(owner_engine):
    with owner_engine.begin() as connection:
        rows = connection.execute(
            text(
                "SELECT tenant_id, actor_type, actor_id, action, outcome, reason_code, "
                "target_type, target_id, trace_id, detail "
                "FROM audit_events WHERE outcome = 'deny' ORDER BY occurred_at"
            )
        )
        return rows.mappings().all()


def _rows(owner_engine):
    with owner_engine.begin() as connection:
        return connection.execute(
            text(f"SELECT record_id, host_id, adapter, subject, provenance, total, passed, "
                 f"failed, skipped, checks, recorded_at FROM {TABLE} ORDER BY record_id")
        ).mappings().all()


@pytest.fixture
def member(owner_engine, two_tenants, frozen_now):
    tenant, _ = two_tenants
    with owner_engine.begin() as connection:
        seeded = _seed(connection, tenant_id=tenant, now=frozen_now, label="records-ok")
    return {"tenant": tenant, **seeded}


# --------------------------------------------------------------------------
# The seam, end to end, through the application role
# --------------------------------------------------------------------------


def test_the_producer_writes_as_the_application_role_and_the_routes_serve_it(
    owner_engine, app_engine, app_sessionmaker, member, frozen_now
):
    with app_sessionmaker() as session, session.begin():
        row = record_fixture_conformance(
            session, adapter="codex-cli", host_id=HOST, now=frozen_now
        )
        record_id = row.record_id

    stored = _rows(owner_engine)
    assert len(stored) == 1
    assert stored[0]["record_id"] == record_id
    assert stored[0]["host_id"] == HOST
    assert (stored[0]["subject"], stored[0]["provenance"]) == ("fixture-adapter", "in-server")
    assert (stored[0]["total"], stored[0]["passed"], stored[0]["failed"], stored[0]["skipped"]) == (
        15, 14, 0, 1
    )
    assert [c["name"] for c in stored[0]["checks"]] == [spec.name for spec in CHECKLIST]
    assert all(set(c) == {"name", "passed", "skipped"} for c in stored[0]["checks"])

    client = _client(app_engine, tenant_id=member["tenant"], user_id=member["user_id"], now=frozen_now)
    body = _get(client, _list_path(member["project_id"])).json()
    assert body["status"] == "RECORDED"
    assert [r["adapter"] for r in body["records"]] == ["codex-cli"]
    assert body["records"][0]["recordedAt"] == "2026-09-09T07:00:00Z"
    assert body["latestRecordedAt"] == "2026-09-09T07:00:00Z"
    assert body["adapters"] == [tool.name for tool in agents.TOOLS]

    single = _get(client, _one_path(member["project_id"], "codex-cli")).json()
    assert single["status"] == "RECORDED"
    assert (single["total"], single["passed"], single["failed"], single["skipped"]) == (15, 14, 0, 1)
    unrecorded = _get(client, _one_path(member["project_id"], "gemini-cli")).json()
    assert unrecorded["status"] == "NOT_OBSERVED"
    assert unrecorded["recordedAt"] is None
    # Reads write nothing: no audit row, no record.
    assert _denials(owner_engine) == []
    assert len(_rows(owner_engine)) == 1


def test_with_no_row_the_list_is_the_stage_one_shape(app_engine, member, frozen_now):
    client = _client(app_engine, tenant_id=member["tenant"], user_id=member["user_id"], now=frozen_now)
    body = _get(client, _list_path(member["project_id"])).json()
    assert body["status"] == "NOT_OBSERVED"
    assert set(body) == {"status", "reason", "scope", "contractVersion", "adapters", "checks", "recordedAt"}
    assert body["reason"] == conformance_status.NOT_OBSERVED_REASON
    assert body["recordedAt"] is None


# --------------------------------------------------------------------------
# T8. Append-only for the application role
# --------------------------------------------------------------------------


def test_T8_the_application_role_cannot_update_or_delete_a_record(
    owner_engine, app_engine, member, frozen_now
):
    with owner_engine.begin() as connection:
        record_id = _store(connection, adapter="codex-cli", host_id=HOST, recorded_at=frozen_now)

    for statement in (
        f"UPDATE {TABLE} SET passed = 0 WHERE record_id = :id",
        f"DELETE FROM {TABLE} WHERE record_id = :id",
    ):
        with pytest.raises((ProgrammingError, DBAPIError)) as refused:
            with app_engine.begin() as connection:
                connection.execute(text(statement), {"id": record_id})
        assert "permission denied" in str(refused.value).lower()

    # And it can still read: the seam's read side is this very role.
    with app_engine.begin() as connection:
        count = connection.execute(text(f"SELECT count(*) FROM {TABLE}")).scalar_one()
    assert count == 1


# --------------------------------------------------------------------------
# T2 / T3. The database's own CHECKs
# --------------------------------------------------------------------------


@pytest.mark.parametrize(
    "label, change",
    [
        ("counts-do-not-add-up", {"passed": 13}),
        ("negative-count", {"failed": -1, "passed": 15}),
        ("checks-shorter-than-total", {"checks": _outcomes()[:-1]}),
        ("checks-not-an-array", {"checks": {"name": "x"}}),
        ("subject-installed-cli", {"subject": "installed-cli"}),
        ("subject-empty", {"subject": ""}),
        ("provenance-hosted-ci-import", {"provenance": "hosted-ci-import"}),
        ("provenance-empty", {"provenance": ""}),
    ],
)
def test_T2_T3_the_checks_refuse_a_row_this_stage_cannot_produce(
    owner_engine, clean_tables, frozen_now, label, change
):
    values = _well_formed(adapter="codex-cli", host_id=HOST, recorded_at=frozen_now)
    values.update(change)
    with pytest.raises(IntegrityError):
        with owner_engine.begin() as connection:
            _insert(connection, TABLE, **values)
    assert _rows(owner_engine) == []


@pytest.mark.parametrize("value", ["cp-01.internal", "10.0.0.7", "/srv/cp", ""])
def test_T15_host_id_is_a_uuid_column_so_an_identifying_string_cannot_be_stored(
    owner_engine, clean_tables, frozen_now, value
):
    values = _well_formed(adapter="codex-cli", host_id=HOST, recorded_at=frozen_now)
    with pytest.raises(DBAPIError):
        with owner_engine.begin() as connection:
            connection.execute(
                text(
                    f"INSERT INTO {TABLE} (record_id, host_id, adapter, contract_version, "
                    "suite_contract_version, subject, provenance, total, passed, failed, "
                    "skipped, checks, recorded_at) VALUES (:record_id, :host, :adapter, "
                    ":contract_version, :suite_contract_version, :subject, :provenance, "
                    ":total, :passed, :failed, :skipped, CAST(:checks AS jsonb), :recorded_at)"
                ),
                {**{k: v for k, v in values.items() if k not in ("host_id", "checks")},
                 "host": value, "checks": "[]"},
            )


# --------------------------------------------------------------------------
# T10. Latest per host, deterministic on ties
# --------------------------------------------------------------------------


def test_T10_another_hosts_newer_record_does_not_change_this_hosts_answer(
    owner_engine, app_engine, member, frozen_now
):
    later = frozen_now + dt.timedelta(hours=2)
    with owner_engine.begin() as connection:
        mine = _store(connection, adapter="codex-cli", host_id=HOST, recorded_at=frozen_now)
        _store(connection, adapter="codex-cli", host_id=OTHER_HOST, recorded_at=later,
               outcomes=_outcomes(failed=("redact_removes_known_secrets",)))
        _store(connection, adapter="claude-code", host_id=OTHER_HOST, recorded_at=later)

    client = _client(app_engine, tenant_id=member["tenant"], user_id=member["user_id"], now=frozen_now)
    body = _get(client, _list_path(member["project_id"])).json()
    assert [r["adapter"] for r in body["records"]] == ["codex-cli"]
    assert body["records"][0]["recordedAt"] == "2026-09-09T07:00:00Z"
    assert body["records"][0]["failed"] == 0
    assert body["latestRecordedAt"] == "2026-09-09T07:00:00Z"
    # The other host's claude-code record is invisible here.
    single = _get(client, _one_path(member["project_id"], "claude-code")).json()
    assert single["status"] == "NOT_OBSERVED"

    # Seen from the other host, the answer is its own.
    other = _client(app_engine, tenant_id=member["tenant"], user_id=member["user_id"],
                    now=frozen_now, host_id=OTHER_HOST)
    body = _get(other, _list_path(member["project_id"])).json()
    assert [r["adapter"] for r in body["records"]] == ["claude-code", "codex-cli"]
    assert body["records"][1]["failed"] == 1
    assert body["latestRecordedAt"] == "2026-09-09T09:00:00Z"
    assert mine not in str(body)


def test_T10b_a_tie_on_recorded_at_is_broken_by_record_id_the_same_way_every_time(
    owner_engine, app_engine, member, frozen_now
):
    low = "cfr_01J8Z3XQ2K9WMV5T7N4B6C8D00"
    high = "cfr_01J8Z3XQ2K9WMV5T7N4B6C8D0Z"
    with owner_engine.begin() as connection:
        # Inserted high first, then low: insertion order must not decide.
        _store(connection, adapter="codex-cli", host_id=HOST, recorded_at=frozen_now, record_id=high)
        _store(connection, adapter="codex-cli", host_id=HOST, recorded_at=frozen_now, record_id=low,
               outcomes=_outcomes(failed=("redact_is_idempotent",)))

    client = _client(app_engine, tenant_id=member["tenant"], user_id=member["user_id"], now=frozen_now)
    answers = [
        _get(client, _one_path(member["project_id"], "codex-cli")).json() for _ in range(3)
    ]
    assert answers[0] == answers[1] == answers[2]
    # ``record_id DESC``: the high id wins, which is the row with no failure.
    assert answers[0]["failed"] == 0

    # A third row with the same instant and a lower id still does not win.
    with owner_engine.begin() as connection:
        _store(connection, adapter="codex-cli", host_id=HOST, recorded_at=frozen_now,
               record_id="cfr_01J8Z3XQ2K9WMV5T7N4B6C8D0A",
               outcomes=_outcomes(failed=("redact_is_idempotent",)))
    assert _get(client, _one_path(member["project_id"], "codex-cli")).json() == answers[0]


def test_T10c_the_index_is_the_read_order(owner_engine, migrated):
    with owner_engine.begin() as connection:
        definition = connection.execute(
            text("SELECT indexdef FROM pg_indexes WHERE tablename = :t AND indexname = :i"),
            {"t": TABLE, "i": "ix_adapter_conformance_records_latest"},
        ).scalar_one()
    assert definition.endswith("(host_id, adapter, recorded_at DESC, record_id DESC)")


# --------------------------------------------------------------------------
# T13. A broken stored row is refused, not served
# --------------------------------------------------------------------------


@pytest.mark.parametrize("label", sorted(TAMPERINGS))
def test_T13_a_row_that_passes_the_checks_but_breaks_an_invariant_is_sys_0002(
    owner_engine, app_engine, member, frozen_now, label
):
    values = _well_formed(adapter="codex-cli", host_id=HOST, recorded_at=frozen_now)
    values.update(TAMPERINGS[label](values))
    with owner_engine.begin() as connection:
        _insert(connection, TABLE, **values)  # the database accepts it

    client = _client(app_engine, tenant_id=member["tenant"], user_id=member["user_id"], now=frozen_now)
    for path in (_list_path(member["project_id"]), _one_path(member["project_id"], "codex-cli")):
        body = _canonical(_get(client, path), code="SYS-0002", status=500, retryable=False)
        assert body["detail"] == conformance_status.RECORD_INVALID_DETAIL
        text_body = str(body)
        for spec in CHECKLIST:
            assert spec.name not in text_body
        assert "install_actually_installs" not in text_body
        assert "/srv/cp" not in text_body and "token=" not in text_body
        assert "0.9.0" not in text_body
        assert "contract_version" not in text_body and "string_too_short" not in text_body
    # Not a denial, so not audited.
    assert _denials(owner_engine) == []


def test_T13b_a_well_formed_row_beside_a_broken_one_does_not_rescue_the_read(
    owner_engine, app_engine, member, frozen_now
):
    """No partial answers: the list is refused as a whole."""
    values = _well_formed(adapter="claude-code", host_id=HOST, recorded_at=frozen_now)
    values.update(_shuffled_order(values))
    with owner_engine.begin() as connection:
        _insert(connection, TABLE, **values)
        _store(connection, adapter="codex-cli", host_id=HOST, recorded_at=frozen_now)

    client = _client(app_engine, tenant_id=member["tenant"], user_id=member["user_id"], now=frozen_now)
    _canonical(_get(client, _list_path(member["project_id"])), code="SYS-0002", status=500)
    # The single route for the intact adapter still answers: its row is fine.
    assert _get(client, _one_path(member["project_id"], "codex-cli")).json()["status"] == "RECORDED"


# --------------------------------------------------------------------------
# T15. No host identity: refuse, do not report another host
# --------------------------------------------------------------------------


def test_T15_without_a_host_identity_the_read_refuses_although_rows_exist(
    owner_engine, app_engine, member, frozen_now
):
    with owner_engine.begin() as connection:
        _store(connection, adapter="codex-cli", host_id=HOST, recorded_at=frozen_now)
    client = _client(app_engine, tenant_id=member["tenant"], user_id=member["user_id"],
                     now=frozen_now, host_id=None)
    for path in (_list_path(member["project_id"]), _one_path(member["project_id"], "codex-cli")):
        body = _canonical(_get(client, path), code="SYS-0002", status=500, retryable=False)
        assert body["detail"] == conformance_status.HOST_UNCONFIGURED_DETAIL
        assert "NOT_OBSERVED" not in str(body)
    assert _denials(owner_engine) == []


# --------------------------------------------------------------------------
# T9. The read boundary on the single route
# --------------------------------------------------------------------------


def test_T9_a_non_member_is_refused_on_the_single_route_and_recorded_once(
    owner_engine, app_engine, two_tenants, frozen_now
):
    tenant, _ = two_tenants
    with owner_engine.begin() as connection:
        theirs = _seed(connection, tenant_id=tenant, now=frozen_now, label="rec-own")
        outsider = _seed(connection, tenant_id=tenant, now=frozen_now, label="rec-out")
        _store(connection, adapter="codex-cli", host_id=HOST, recorded_at=frozen_now)

    client = _client(app_engine, tenant_id=tenant, user_id=outsider["user_id"], now=frozen_now)
    body = _canonical(
        _get(client, _one_path(theirs["project_id"], "codex-cli")), code="AUTH-0030", status=403
    )
    rows = _denials(owner_engine)
    assert len(rows) == 1, rows
    row = rows[0]
    assert row["actor_id"] == outsider["user_id"]
    assert row["reason_code"] == "AUTH-0030"
    assert (row["target_type"], row["target_id"]) == ("project", theirs["project_id"])
    assert row["trace_id"] == body["traceId"]
    assert theirs["project_id"] not in row["action"]
    assert "codex-cli" not in row["action"]
    assert "conformance" in row["action"]
    # The record itself is not disclosed to a non-member.
    assert "RECORDED" not in str(body)


def test_T9b_an_unknown_adapter_is_404_and_not_a_denial(
    owner_engine, app_engine, member, frozen_now
):
    client = _client(app_engine, tenant_id=member["tenant"], user_id=member["user_id"], now=frozen_now)
    body = _canonical(_get(client, _one_path(member["project_id"], "nope")), code="RES-0004", status=404)
    assert "nope" not in str(body)
    assert _denials(owner_engine) == []


def test_T9c_no_credential_on_the_single_route_is_401_and_anonymous(
    owner_engine, app_engine, member, frozen_now
):
    client = _client(app_engine, tenant_id=member["tenant"], user_id=member["user_id"], now=frozen_now)
    response = _get(client, _one_path(member["project_id"], "codex-cli"), token=None)
    assert response.status_code == 401, response.text
    rows = _denials(owner_engine)
    assert len(rows) == 1
    assert rows[0]["actor_type"] == "anonymous"
    assert "codex-cli" not in rows[0]["action"]


# --------------------------------------------------------------------------
# A lock the read waits on is answered within the budget
# --------------------------------------------------------------------------


@pytest.mark.parametrize("which", ["list", "single"])
def test_a_wait_past_the_budget_on_the_record_table_is_a_retryable_503(
    owner_engine, app_engine, member, frozen_now, which
):
    """Another transaction holds the table exclusively; the read's second span
    waits, hits the budget and answers SYS-0001 -- it does not hang."""
    with owner_engine.begin() as connection:
        _store(connection, adapter="codex-cli", host_id=HOST, recorded_at=frozen_now)
    holder = owner_engine.connect()
    tx = holder.begin()
    holder.execute(text(f"LOCK TABLE {TABLE} IN ACCESS EXCLUSIVE MODE"))
    try:
        client = _client(app_engine, tenant_id=member["tenant"], user_id=member["user_id"],
                         now=frozen_now, lock_timeout_ms=BUDGET_MS)
        path = _list_path(member["project_id"]) if which == "list" else _one_path(member["project_id"], "codex-cli")
        response, elapsed = within_deadline(lambda: _get(client, path), seconds=DEADLINE_SECONDS)
    finally:
        tx.rollback()
        holder.close()
    body = _canonical(response, code="SYS-0001", status=503, retryable=True)
    assert elapsed < DEADLINE_SECONDS
    for forbidden in ("55P03", "LOCK", TABLE, "SELECT"):
        assert forbidden not in body["detail"]
    # Not a denial, and the lock released, the same read answers.
    assert _denials(owner_engine) == []
    assert _get(client, path).status_code == 200


# --------------------------------------------------------------------------
# The migration's convergence shape is what the DDL produced
# --------------------------------------------------------------------------


def test_the_migration_converges_on_its_own_result(owner_engine, migrated):
    spec = importlib.util.spec_from_file_location(
        "migration_0055", ROOT / "migrations" / "versions" / "0055_adapter_conformance_records.py"
    )
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    with owner_engine.begin() as connection:
        observed = module._observed_shape(connection)
    assert module.shape_differences(observed, module.expected_shape()) == []
    # No row security, no policy: host-global by design.
    assert observed["rls"] == (False, False)
    with owner_engine.begin() as connection:
        policies = connection.execute(
            text("SELECT count(*) FROM pg_policies WHERE tablename = :t"), {"t": TABLE}
        ).scalar_one()
    assert policies == 0
