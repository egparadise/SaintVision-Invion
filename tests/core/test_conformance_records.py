"""The conformance record producer, its invariants, the host identity and the table.

Design #218 v1.2 §5: **T12** (fixture only -- no real adapter, no subprocess, no
credential; the fixture's ``install``/``authenticate`` *are* called and change
nothing), **T14** (counts recomputed from the report, ``failed`` derived, no
caller-supplied numbers), the reader side of **T13** (every §2-8 invariant
refuses), **T15(b)** (strict host identity parsing) and the schema facts the
migration and the model must agree on. No database: the session is a stand-in
that records what would be inserted, and the migration is read as text.
"""

from __future__ import annotations

import ast
import datetime as dt
import importlib.util
import inspect
import os
import pathlib
import subprocess
import uuid

import pytest

from saintvision.adapters import agents, cli, conformance, reference
from saintvision.adapters.conformance import CHECKLIST, Check, ConformanceReport
from saintvision.adapters.contract import CONTRACT_VERSION
from saintvision.config import Settings, parse_control_plane_host_id
from saintvision.db import models
from saintvision.db.base import Base
from saintvision.services import conformance_records as service
from saintvision.services.conformance_records import (
    DUMMY_CREDENTIAL_REF,
    Outcome,
    ProducerRefused,
    StoredRecordInvalid,
    record_fixture_conformance,
    validate_outcomes,
)

HOST = uuid.UUID("0f8fad5b-d9cb-469f-a165-70867728950e")
NOW = dt.datetime(2026, 9, 28, 6, 0, tzinfo=dt.timezone.utc)
ROOT = pathlib.Path(__file__).resolve().parents[2]
MIGRATION = ROOT / "migrations" / "versions" / "0055_adapter_conformance_records.py"
NAMES = [spec.name for spec in CHECKLIST]


class FakeSession:
    """Records what the producer adds; the flush is where a real session would INSERT."""

    def __init__(self, flush_error=None):
        self.added = []
        self.flushed = 0
        self.statements = []
        self.flush_error = flush_error

    def in_transaction(self):
        return True

    def execute(self, statement, params=None):
        self.statements.append(str(statement))
        return None

    # The command uses the session as a context manager around one transaction.
    def __enter__(self):
        return self

    def __exit__(self, *_exc):
        return None

    def begin(self):
        import contextlib

        return contextlib.nullcontext()

    def add(self, row):
        self.added.append(row)

    def flush(self):
        self.flushed += 1
        if self.flush_error is not None:
            raise self.flush_error


def outcomes(*, failed=(), skipped=("declared_server_cancel_actually_stops",)):
    return [
        {
            "name": name,
            "passed": name not in failed and name not in skipped,
            "skipped": name in skipped,
        }
        for name in NAMES
    ]


def counts(checks):
    return dict(
        total=len(checks),
        passed=sum(1 for c in checks if c["passed"] and not c["skipped"]),
        failed=sum(1 for c in checks if not c["passed"] and not c["skipped"]),
        skipped=sum(1 for c in checks if c["skipped"]),
    )


def load_migration():
    spec = importlib.util.spec_from_file_location("migration_0055", MIGRATION)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


# --------------------------------------------------------------------------
# The producer stores what the suite observed, under the fixture subject
# --------------------------------------------------------------------------


def test_the_producer_stores_the_fixture_run_for_a_tool_name():
    session = FakeSession()
    row = record_fixture_conformance(session, adapter="codex-cli", host_id=HOST, now=NOW)
    assert session.added == [row] and session.flushed == 1
    assert isinstance(row, models.AdapterConformanceRecord)
    assert row.record_id.startswith("cfr_") and len(row.record_id) == 30
    assert row.host_id == HOST
    assert row.adapter == "codex-cli"
    assert row.subject == "fixture-adapter"
    assert row.provenance == "in-server"
    assert row.contract_version == CONTRACT_VERSION
    assert row.suite_contract_version == CONTRACT_VERSION
    assert row.recorded_at == NOW
    # The fixture adapter's real result: every check but the ungated cancel one.
    assert (row.total, row.passed, row.failed, row.skipped) == (15, 14, 0, 1)
    assert [c["name"] for c in row.checks] == NAMES
    assert all(set(c) == {"name", "passed", "skipped"} for c in row.checks)
    assert row.checks[NAMES.index("declared_server_cancel_actually_stops")] == {
        "name": "declared_server_cancel_actually_stops",
        "passed": False,
        "skipped": True,
    }
    # No detail, anywhere in the row.
    assert "detail" not in str(row.checks)


@pytest.mark.parametrize("adapter", ["reference", "nope", "", "Codex-CLI"])
def test_the_producer_refuses_a_name_that_is_not_a_tool(adapter):
    session = FakeSession()
    with pytest.raises(ProducerRefused):
        record_fixture_conformance(session, adapter=adapter, host_id=HOST, now=NOW)
    assert session.added == []


# T12. Fixture only.
def test_T12_the_producer_measures_the_fixture_and_never_a_real_adapter(monkeypatch):
    forbidden = []

    def explode(what):
        def _inner(*_a, **_k):
            forbidden.append(what)
            raise AssertionError(f"the producer must not use {what}")

        return _inner

    monkeypatch.setattr(cli.CliAdapter, "__init__", explode("CliAdapter"))
    monkeypatch.setattr(agents, "adapter_for", explode("agents.adapter_for"))
    monkeypatch.setattr(subprocess, "Popen", explode("subprocess.Popen"))
    monkeypatch.setattr(subprocess, "run", explode("subprocess.run"))
    monkeypatch.setattr(os, "system", explode("os.system"))

    # The fixture's install and authenticate stubs *are* called -- the suite's
    # checks call them -- and they change nothing on the host.
    called = {"install": 0, "authenticate": []}
    real_install = reference.ReferenceAdapter.install
    real_authenticate = reference.ReferenceAdapter.authenticate

    def install(self):
        called["install"] += 1
        return real_install(self)

    def authenticate(self, credential_ref):
        called["authenticate"].append(credential_ref)
        return real_authenticate(self, credential_ref)

    monkeypatch.setattr(reference.ReferenceAdapter, "install", install)
    monkeypatch.setattr(reference.ReferenceAdapter, "authenticate", authenticate)

    environment_before = dict(os.environ)
    cwd_before = sorted(os.listdir(os.getcwd()))

    row = record_fixture_conformance(FakeSession(), adapter="claude-code", host_id=HOST, now=NOW)

    assert forbidden == []
    assert called["install"] == 1
    assert called["authenticate"] == [DUMMY_CREDENTIAL_REF]
    assert dict(os.environ) == environment_before
    assert sorted(os.listdir(os.getcwd())) == cwd_before
    assert row.subject == "fixture-adapter"


def test_T12b_the_producer_takes_no_credential_other_than_the_suites_dummy():
    session = FakeSession()
    for ref in ("secret://real", "", "conformance://real", "conformance://dummy2"):
        with pytest.raises(ProducerRefused):
            record_fixture_conformance(
                session, adapter="codex-cli", host_id=HOST, now=NOW, credential_ref=ref
            )
    assert session.added == []
    assert DUMMY_CREDENTIAL_REF == "conformance://dummy"
    assert inspect.signature(conformance.run_conformance).parameters["credential_ref"].default == (
        DUMMY_CREDENTIAL_REF
    )


def test_T12c_the_producer_module_names_no_real_adapter():
    tree = ast.parse(inspect.getsource(service))
    names = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Name):
            names.add(node.id)
        elif isinstance(node, ast.Attribute):
            names.add(node.attr)
        elif isinstance(node, ast.alias):
            names.add(node.name.split(".")[-1])
    assert "ReferenceAdapter" in names
    for forbidden in ("CliAdapter", "adapter_for", "subprocess", "Popen", "TOOLS"):
        assert forbidden not in names, forbidden
    # BY_NAME is consulted for the *name* allowlist only, never to pick an adapter.
    source = inspect.getsource(service.record_fixture_conformance)
    assert "run_conformance(ReferenceAdapter()" in source


# T14. Counts come from the report, and failed is derived.
def test_T14_the_counts_are_recounted_from_the_report_not_taken_from_anyone(monkeypatch):
    checks = [
        Check(name=name, passed=name != "redact_is_idempotent", detail="host output here")
        for name in NAMES
    ]
    checks[NAMES.index("declared_server_cancel_actually_stops")] = Check(
        "declared_server_cancel_actually_stops", True, "not declared", skipped=True
    )

    class LyingReport(ConformanceReport):
        """A report whose properties disagree with its checks."""

        passed = property(lambda self: 99)
        failed = property(lambda self: 0)
        skipped = property(lambda self: 7)
        total = property(lambda self: 3)

    report = LyingReport(adapter="reference", contract_version=CONTRACT_VERSION, checks=checks)
    monkeypatch.setattr(service, "run_conformance", lambda *_a, **_k: report)

    row = record_fixture_conformance(FakeSession(), adapter="codex-cli", host_id=HOST, now=NOW)
    assert (row.total, row.passed, row.failed, row.skipped) == (15, 13, 1, 1)
    assert row.checks[NAMES.index("redact_is_idempotent")] == {
        "name": "redact_is_idempotent",
        "passed": False,
        "skipped": False,
    }
    assert "host output here" not in str(row.checks)


def test_T14b_the_producer_accepts_no_count_and_no_failed_argument():
    parameters = inspect.signature(record_fixture_conformance).parameters
    assert not {"total", "passed", "failed", "skipped", "checks", "report", "counts"} & set(parameters)
    assert set(parameters) == {"session", "adapter", "host_id", "now", "credential_ref"}


def test_T14c_a_report_with_the_wrong_names_is_refused_before_it_is_stored(monkeypatch):
    report = ConformanceReport(adapter="reference", contract_version=CONTRACT_VERSION,
                               checks=[Check(name, True, "") for name in NAMES[:-1]])
    monkeypatch.setattr(service, "run_conformance", lambda *_a, **_k: report)
    session = FakeSession()
    with pytest.raises(StoredRecordInvalid):
        record_fixture_conformance(session, adapter="codex-cli", host_id=HOST, now=NOW)
    assert session.added == []


@pytest.mark.parametrize("host_id", [None, "0f8fad5b-d9cb-469f-a165-70867728950e", "cp-01"])
def test_T15_the_producer_does_not_start_without_a_uuid_host_identity(host_id):
    session = FakeSession()
    with pytest.raises(ProducerRefused) as refused:
        record_fixture_conformance(session, adapter="codex-cli", host_id=host_id, now=NOW)
    assert session.added == []
    assert "cp-01" not in str(refused.value)


def test_a_naive_clock_is_refused():
    with pytest.raises(ProducerRefused):
        record_fixture_conformance(
            FakeSession(), adapter="codex-cli", host_id=HOST, now=NOW.replace(tzinfo=None)
        )


# --------------------------------------------------------------------------
# T13, reader side: every §2-8 invariant refuses, naming the rule and not the row
# --------------------------------------------------------------------------


def _valid():
    checks = outcomes()
    return checks, counts(checks)


def test_a_well_formed_record_validates_to_outcomes_in_checklist_order():
    checks, c = _valid()
    result = validate_outcomes(checks, suite_contract_version=CONTRACT_VERSION, **c)
    assert [o.name for o in result] == NAMES
    assert isinstance(result, tuple) and all(isinstance(o, Outcome) for o in result)


@pytest.mark.parametrize(
    "label, mutate",
    [
        ("empty-with-total", lambda ch, c: ([], c)),
        ("not-a-list", lambda ch, c: ({"name": "x"}, c)),
        ("duplicate-names", lambda ch, c: ([dict(x, name=NAMES[0]) for x in ch], c)),
        ("unknown-name", lambda ch, c: ([dict(x, name="install_actually_installs") if i == 3 else x for i, x in enumerate(ch)], c)),
        ("shuffled-order", lambda ch, c: ([ch[1], ch[0], *ch[2:]], c)),
        ("one-short", lambda ch, c: (ch[:-1], c)),
        ("one-extra", lambda ch, c: ([*ch, ch[0]], c)),
        ("passed-and-skipped", lambda ch, c: ([dict(x, passed=True, skipped=True) if x["skipped"] else x for x in ch], c)),
        ("detail-key", lambda ch, c: ([dict(x, detail="Exception: /srv/cp") if i == 0 else x for i, x in enumerate(ch)], c)),
        ("missing-key", lambda ch, c: ([{"name": x["name"], "passed": x["passed"]} if i == 0 else x for i, x in enumerate(ch)], c)),
        ("non-bool-flag", lambda ch, c: ([dict(x, passed="true") if i == 0 else x for i, x in enumerate(ch)], c)),
        ("int-flag", lambda ch, c: ([dict(x, skipped=0) if i == 0 else x for i, x in enumerate(ch)], c)),
        ("empty-name", lambda ch, c: ([dict(x, name="") if i == 0 else x for i, x in enumerate(ch)], c)),
        ("total-off", lambda ch, c: (ch, {**c, "total": 16})),
        ("passed-off", lambda ch, c: (ch, {**c, "passed": 13, "failed": 1})),
        ("failed-not-derived", lambda ch, c: (ch, {**c, "failed": 1, "skipped": 0})),
        ("skipped-off", lambda ch, c: (ch, {**c, "skipped": 0, "passed": 15})),
    ],
)
def test_T13_every_invariant_refuses_and_says_nothing_about_the_row(label, mutate):
    checks, c = _valid()
    bad_checks, bad_counts = mutate(checks, c)
    with pytest.raises(StoredRecordInvalid) as refused:
        validate_outcomes(bad_checks, suite_contract_version=CONTRACT_VERSION, **bad_counts)
    message = str(refused.value)
    for name in NAMES:
        assert name not in message, label
    assert "install_actually_installs" not in message
    assert "/srv/cp" not in message
    assert "16" not in message and "13" not in message


def test_T13b_an_unknown_suite_version_is_refused_rather_than_compared_to_todays_list():
    checks, c = _valid()
    with pytest.raises(StoredRecordInvalid) as refused:
        validate_outcomes(checks, suite_contract_version="0.9.0", **c)
    assert "0.9.0" not in str(refused.value)


def test_T13c_the_row_lifter_refuses_a_subject_provenance_or_adapter_outside_the_stage():
    checks, c = _valid()
    base = dict(
        record_id="cfr_01J8Z3XQ2K9WMV5T7N4B6C8D0E",
        host_id=HOST,
        adapter="codex-cli",
        contract_version=CONTRACT_VERSION,
        suite_contract_version=CONTRACT_VERSION,
        subject="fixture-adapter",
        provenance="in-server",
        checks=checks,
        recorded_at=NOW,
        **c,
    )
    assert service.to_recorded(models.AdapterConformanceRecord(**base)).adapter == "codex-cli"
    for change in (
        {"subject": "installed-cli"},
        {"provenance": "hosted-ci-import"},
        {"adapter": "reference"},
        {"recorded_at": NOW.replace(tzinfo=None)},
        {"recorded_at": None},
    ):
        with pytest.raises(StoredRecordInvalid):
            service.to_recorded(models.AdapterConformanceRecord(**{**base, **change}))


# F3 (Codex #221): a row the database accepts but the contract would not.
@pytest.mark.parametrize(
    "change",
    [
        {"contract_version": ""},
        {"contract_version": "x" * 33},
        {"contract_version": " 1.0.0"},
        {"suite_contract_version": ""},
        {"suite_contract_version": "y" * 33},
        {"total": -1},
        {"passed": True},
    ],
)
def test_F3_a_db_valid_row_outside_the_contract_bounds_is_refused_by_the_reader(change):
    checks, c = _valid()
    base = dict(
        record_id="cfr_01J8Z3XQ2K9WMV5T7N4B6C8D0E", host_id=HOST, adapter="codex-cli",
        contract_version=CONTRACT_VERSION, suite_contract_version=CONTRACT_VERSION,
        subject="fixture-adapter", provenance="in-server", checks=checks, recorded_at=NOW, **c,
    )
    base.update(change)
    with pytest.raises(StoredRecordInvalid) as refused:
        service.to_recorded(models.AdapterConformanceRecord(**base))
    # The rule, never the value.
    assert "x" * 33 not in str(refused.value) and "y" * 33 not in str(refused.value)


def test_F3_every_bound_the_contract_puts_on_a_lifted_field_is_checked_by_the_reader():
    """Whatever ``to_recorded`` returns must validate as an item: the reader's
    refusal is the only refusal, so response assembly cannot be the first
    place a stored row fails."""
    from saintvision.api import schemas

    checks, c = _valid()
    row = models.AdapterConformanceRecord(
        record_id="cfr_01J8Z3XQ2K9WMV5T7N4B6C8D0E", host_id=HOST, adapter="codex-cli",
        contract_version="1", suite_contract_version=CONTRACT_VERSION,
        subject="fixture-adapter", provenance="in-server", checks=checks, recorded_at=NOW, **c,
    )
    lifted = service.to_recorded(row)
    schemas.ConformanceRecordItem(
        adapter=lifted.adapter, subject=lifted.subject, provenance=lifted.provenance,
        contractVersion=lifted.contract_version, suiteContractVersion=lifted.suite_contract_version,
        total=lifted.total, passed=lifted.passed, failed=lifted.failed, skipped=lifted.skipped,
        outcomes=[{"name": o.name, "passed": o.passed, "skipped": o.skipped} for o in lifted.outcomes],
        recordedAt=lifted.recorded_at,
    )
    assert service.VERSION_MAX == schemas.ConformanceRecordItem.model_fields["contract_version"].metadata[1].max_length
    assert service.VERSION_MIN == schemas.ConformanceRecordItem.model_fields["contract_version"].metadata[0].min_length


def test_the_lifted_record_carries_no_host_id():
    checks, c = _valid()
    row = models.AdapterConformanceRecord(
        record_id="cfr_01J8Z3XQ2K9WMV5T7N4B6C8D0E", host_id=HOST, adapter="codex-cli",
        contract_version=CONTRACT_VERSION, suite_contract_version=CONTRACT_VERSION,
        subject="fixture-adapter", provenance="in-server", checks=checks, recorded_at=NOW, **c,
    )
    lifted = service.to_recorded(row)
    assert not hasattr(lifted, "host_id")
    assert "host" not in str(lifted)


# --------------------------------------------------------------------------
# T15(b). The host identity is strict
# --------------------------------------------------------------------------


@pytest.mark.parametrize(
    "value",
    [
        "cp-01.internal",
        "10.0.0.7",
        "/srv/cp",
        "",
        " ",
        "0F8FAD5B-D9CB-469F-A165-70867728950E",
        " 0f8fad5b-d9cb-469f-a165-70867728950e",
        "0f8fad5b-d9cb-469f-a165-70867728950e ",
        "0f8fad5bd9cb469fa16570867728950e",
        "{0f8fad5b-d9cb-469f-a165-70867728950e}",
        "urn:uuid:0f8fad5b-d9cb-469f-a165-70867728950e",
        "0f8fad5b-d9cb-469f-a165-70867728950",
        "0f8fad5b-d9cb-469f-a165-70867728950eZ",
        "gf8fad5b-d9cb-469f-a165-70867728950e",
        None,
        123,
        uuid.UUID("0f8fad5b-d9cb-469f-a165-70867728950e"),
    ],
)
def test_T15b_anything_but_a_canonical_uuid_string_is_refused_without_being_echoed(value):
    with pytest.raises(ValueError) as refused:
        parse_control_plane_host_id(value)
    if isinstance(value, str) and value.strip():
        assert value.strip() not in str(refused.value)


def test_T15b_the_canonical_form_parses_to_the_uuid():
    assert parse_control_plane_host_id("0f8fad5b-d9cb-469f-a165-70867728950e") == HOST


def test_T15c_settings_read_the_variable_strictly(monkeypatch):
    monkeypatch.setenv("INV_DATABASE_URL", "postgresql://unused")
    monkeypatch.delenv("INV_CONTROL_PLANE_HOST_ID", raising=False)
    assert Settings.from_env().control_plane_host_id is None
    monkeypatch.setenv("INV_CONTROL_PLANE_HOST_ID", "0f8fad5b-d9cb-469f-a165-70867728950e")
    assert Settings.from_env().control_plane_host_id == HOST
    for bad in ("cp-01.internal", "10.0.0.7", "/srv/cp", "", "0F8FAD5B-D9CB-469F-A165-70867728950E"):
        monkeypatch.setenv("INV_CONTROL_PLANE_HOST_ID", bad)
        with pytest.raises(ValueError) as refused:
            Settings.from_env()
        assert bad not in str(refused.value) or bad == ""
    # The dataclass itself refuses a string: a uuid or nothing.
    with pytest.raises(ValueError):
        Settings(database_url="x", control_plane_host_id="0f8fad5b-d9cb-469f-a165-70867728950e")
    assert Settings(database_url="x", control_plane_host_id=HOST).control_plane_host_id == HOST
    # Never inferred: no hostname, address or path lookup in the module.
    source = inspect.getsource(Settings.__module__ and __import__("saintvision.config").config)
    for forbidden in ("gethostname", "getfqdn", "uname", "getnode", "MAC"):
        assert forbidden not in source, forbidden


# --------------------------------------------------------------------------
# The operator command
# --------------------------------------------------------------------------


def _load_command():
    spec = importlib.util.spec_from_file_location(
        "record_fixture_conformance_cmd", ROOT / "tools" / "record_fixture_conformance.py"
    )
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def test_the_command_refuses_to_start_without_a_host_identity(monkeypatch, capsys):
    command = _load_command()
    monkeypatch.setenv("INV_DATABASE_URL", "postgresql://unused")
    monkeypatch.delenv("INV_CONTROL_PLANE_HOST_ID", raising=False)
    assert command.main([]) == 2
    monkeypatch.setenv("INV_CONTROL_PLANE_HOST_ID", "cp-01.internal")
    assert command.main([]) == 2
    captured = capsys.readouterr()
    assert "refusing to start" in captured.err
    assert "cp-01.internal" not in captured.err


def test_the_command_only_offers_the_platforms_tool_names():
    command = _load_command()
    with pytest.raises(SystemExit) as exited:
        command.main(["--adapter", "reference"])
    assert exited.value.code == 2


def _command_with(monkeypatch, session):
    import types

    import sqlalchemy
    import sqlalchemy.orm

    command = _load_command()
    monkeypatch.setenv("INV_DATABASE_URL", "postgresql://unused")
    monkeypatch.setenv("INV_CONTROL_PLANE_HOST_ID", "0f8fad5b-d9cb-469f-a165-70867728950e")
    monkeypatch.setenv("INV_BUSINESS_LOCK_TIMEOUT_MS", "250")
    disposed = []
    monkeypatch.setattr(
        sqlalchemy, "create_engine",
        lambda url, **kw: types.SimpleNamespace(dispose=lambda: disposed.append(url)),
    )
    monkeypatch.setattr(sqlalchemy.orm, "sessionmaker", lambda **kw: (lambda: session))
    return command, disposed


def _operational(sqlstate):
    from sqlalchemy.exc import OperationalError

    class Orig(Exception):
        pass

    orig = Orig("locked")
    orig.sqlstate = sqlstate
    return OperationalError("INSERT INTO adapter_conformance_records", {}, orig)


def test_the_command_records_every_tool_in_one_bounded_transaction(monkeypatch, capsys):
    session = FakeSession()
    command, disposed = _command_with(monkeypatch, session)

    assert command.main([]) == 0
    assert [row.adapter for row in session.added] == [tool.name for tool in agents.TOOLS]
    assert {row.host_id for row in session.added} == {HOST}
    assert disposed == ["postgresql://unused"]
    # The write span is bounded with the configured budget, once.
    assert [s for s in session.statements if "lock_timeout" in s] == ["SET LOCAL lock_timeout = '250ms'"]
    out = capsys.readouterr().out
    assert out.count("subject=fixture-adapter") == len(agents.TOOLS)
    assert "0f8fad5b" not in out


@pytest.mark.parametrize("sqlstate", ["55P03", "40P01"])
def test_the_command_ends_a_lock_wait_with_the_fixed_sentence_and_nothing_printed(monkeypatch, capsys, sqlstate):
    from saintvision.api.lock_wait import LOCK_WAIT_DETAIL

    session = FakeSession(flush_error=_operational(sqlstate))
    command, disposed = _command_with(monkeypatch, session)
    assert command.main([]) == 3
    captured = capsys.readouterr()
    assert captured.out == ""
    assert LOCK_WAIT_DETAIL in captured.err
    for forbidden in (sqlstate, "INSERT INTO", "0f8fad5b"):
        assert forbidden not in captured.err
    assert disposed == ["postgresql://unused"]


@pytest.mark.parametrize("sqlstate", ["57P01", "08006"])
def test_the_command_does_not_disguise_another_failure_as_a_lock_wait(monkeypatch, sqlstate):
    from sqlalchemy.exc import OperationalError

    session = FakeSession(flush_error=_operational(sqlstate))
    command, disposed = _command_with(monkeypatch, session)
    with pytest.raises(OperationalError):
        command.main([])
    assert disposed == ["postgresql://unused"]


# --------------------------------------------------------------------------
# The table: model, migration and their agreement
# --------------------------------------------------------------------------


def test_the_table_is_append_only_and_not_tenant_scoped():
    assert "adapter_conformance_records" in models.APPEND_ONLY_TABLES
    assert "adapter_conformance_records" not in models.TENANT_SCOPED_TABLES
    table = Base.metadata.tables["adapter_conformance_records"]
    assert "tenant_id" not in table.columns
    assert not {"project_id", "user_id", "detail", "source_ref"} & set(table.columns.keys())
    assert str(table.columns["host_id"].type).upper() == "UUID"
    assert table.columns["checks"].type.__class__.__name__ == "JSONB"


def test_the_id_kind_exists_and_is_three_letters():
    from saintvision.ids import PREFIXES, is_id, new_id

    assert PREFIXES["conformance_record"] == "cfr"
    assert is_id(new_id("conformance_record"), "conformance_record")
    assert list(PREFIXES.values()).count("cfr") == 1


def test_the_migration_and_the_model_declare_the_same_checks_and_index():
    migration = load_migration()
    table = Base.metadata.tables["adapter_conformance_records"]
    from sqlalchemy import CheckConstraint

    model_checks = {
        c.name.removeprefix("ck_adapter_conformance_records_"): str(c.sqltext)
        for c in table.constraints
        if isinstance(c, CheckConstraint)
    }
    assert model_checks == migration.CHECKS
    assert set(migration.EXPECTED_CONSTRAINTS) == {
        f"ck_adapter_conformance_records_{name}" for name in migration.CHECKS
    } | {"pk_adapter_conformance_records"}
    (index,) = table.indexes
    assert index.name == migration.INDEX
    assert [str(e).removeprefix("adapter_conformance_records.") for e in index.expressions] == [
        "host_id", "adapter", "recorded_at DESC", "record_id DESC"
    ]
    assert migration.EXPECTED_COLUMNS == tuple(
        (c.name, _pg_type(c), not c.nullable) for c in table.columns
    )
    assert migration.down_revision == "0054_model_version_measurements"
    assert migration.revision == "0055_adapter_conformance_records"


def _pg_type(column):
    """The type as ``format_type`` renders it, which is what the migration compares."""
    from sqlalchemy.dialects import postgresql

    compiled = column.type.compile(dialect=postgresql.dialect()).lower()
    return compiled.replace("varchar(", "character varying(").replace("char(", "character(", 1) if not compiled.startswith("character") else compiled


def test_the_rendered_upgrade_grants_insert_and_select_only_and_no_policy():
    """Read from the migration's own DDL builder without a server."""
    source = MIGRATION.read_text(encoding="utf-8")
    assert "GRANT SELECT, INSERT ON {TABLE} TO {APP_ROLE}" in source
    assert "ROW LEVEL SECURITY" not in source.split("def _create")[1].split("def upgrade")[0]
    assert "CREATE POLICY" not in source
    assert "UPDATE" not in source.split("GRANT SELECT, INSERT")[1].split("\n")[0]
    # The design's one reversal reason, and the guard that keeps observations.
    assert "DROP TABLE IF EXISTS {TABLE}" in source
    assert "would discard observations" in source


def test_the_downgrade_is_classified_reversible_by_the_ac11_runner():
    import sys

    spec = importlib.util.spec_from_file_location(
        "ac11_runner_for_0055", ROOT / "tools" / "run_ac11_migration_rehearsal.py"
    )
    runner = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = runner  # its dataclasses resolve annotations by module
    spec.loader.exec_module(runner)
    assert runner.downgrade_body_kind(MIGRATION.read_text(encoding="utf-8")) == "reversible"


def test_the_migration_shape_comparison_normalises_like_the_kernel_one():
    migration = load_migration()
    expected = migration.expected_shape()
    assert migration.shape_differences(expected, expected) == []
    changed = {**expected, "privileges": {"inv_app": "INSERT,SELECT,UPDATE"}}
    assert migration.shape_differences(changed, expected) == ["privileges"]
    changed = {**expected, "rls": (True, True)}
    assert migration.shape_differences(changed, expected) == ["rls"]
    assert migration.normalise("CHECK ((passed + failed) + skipped = total)") == migration.normalise(
        "CHECK (passed + failed + skipped = total)"
    )
    assert migration.normalise("CHECK (((subject)::text = 'fixture-adapter'::text))") == (
        migration.normalise("CHECK (subject = 'fixture-adapter')")
    )
