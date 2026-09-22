"""PG-free invariants for the opt-in project placement semaphore."""

from asyncio import CancelledError
from contextlib import ExitStack
import json
from types import SimpleNamespace
from uuid import uuid4

import pytest

import inv.placement as placement_module
from inv.db import (
    BoundDatabase,
    Database,
    _PlacementSemaphoreLimit,
    _ProjectPermitRegistry,
)
from inv.errors import DomainError
from inv.placement import PlacementStore
from tools import placement_benchmark


def _database(*, registry=None, metrics=None, enabled=True, limit=4):
    return Database(
        "postgresql://not-connected/secret-dsn",
        recovery_epoch=str(uuid4()),
        placement_short_commit=True,
        placement_project_semaphore_enabled=enabled,
        placement_project_semaphore_limit=limit,
        placement_metric_sink=(metrics.append if metrics is not None else None),
        _placement_permit_registry=registry or _ProjectPermitRegistry(),
    )


def _acquire(db, tenant, project):
    return db.acquire_placement_project_permit(tenant, project)


def test_flag_defaults_off_and_bound_database_preserves_private_settings():
    default = Database("postgresql://not-connected", recovery_epoch=str(uuid4()))
    assert default.placement_project_semaphore_enabled is False
    assert default.placement_project_semaphore_limit == 4

    candidate = _database(limit=4)
    bound = BoundDatabase(candidate, str(uuid4()), object())
    assert bound.placement_project_semaphore_enabled is True
    assert bound.placement_project_semaphore_limit == 4


@pytest.mark.parametrize("value", [None, 0, -1, 21, 4.0, "4", True, False])
def test_semaphore_limit_rejects_non_integer_or_out_of_range(value):
    with pytest.raises(
        ValueError,
        match="placement_project_semaphore_limit must be an integer between 1 and 20",
    ):
        _database(limit=value)


@pytest.mark.parametrize("value", [None, 0, 1, "true"])
def test_semaphore_flag_requires_boolean(value):
    with pytest.raises(ValueError, match="placement_project_semaphore_enabled must be boolean"):
        Database(
            "postgresql://not-connected",
            recovery_epoch=str(uuid4()),
            placement_project_semaphore_enabled=value,
        )


def test_flag_off_creates_no_registry_entry_or_metric():
    registry = _ProjectPermitRegistry()
    metrics = []
    db = _database(registry=registry, metrics=metrics, enabled=False)
    with db._root_transaction_lifecycle():
        assert _acquire(db, str(uuid4()), "prj_flag_off") is False
    assert registry.inspect() == {}
    assert metrics == []


@pytest.mark.parametrize("limit", [1, 3, 4])
def test_limit_is_nonblocking_and_n_plus_one_keeps_res_0007(limit):
    registry = _ProjectPermitRegistry()
    tenant = str(uuid4())
    project = "prj_same_project"
    holders = []
    with ExitStack() as stack:
        for _ in range(limit):
            db = _database(registry=registry, limit=limit)
            stack.enter_context(db._root_transaction_lifecycle())
            assert _acquire(db, tenant, project) is True
            holders.append(db)

        rejected_metrics = []
        rejected = _database(registry=registry, metrics=rejected_metrics, limit=limit)
        with pytest.raises(DomainError) as caught:
            with rejected._root_transaction_lifecycle():
                _acquire(rejected, tenant, project)

        error = caught.value
        assert (error.code, error.status, error.retryable) == (
            "RES-0007",
            503,
            True,
        )
        assert type(error.__cause__).__name__ == "_PlacementSemaphoreLimit"
        metric = next(item for item in rejected_metrics if item["outcome"] == "rejected")
        assert metric["reason"] == "project-semaphore-limit"
        assert metric["inUseBefore"] == limit
        assert metric["admissionElapsedMs"] >= 0
        assert registry.inspect()[(tenant, project)] == limit

    assert registry.inspect() == {}


def test_tenant_and_project_keys_are_independent():
    registry = _ProjectPermitRegistry()
    tenant_a, tenant_b = str(uuid4()), str(uuid4())
    project_x, project_y = "prj_x", "prj_y"
    holder = _database(registry=registry, limit=1)
    with holder._root_transaction_lifecycle():
        assert _acquire(holder, tenant_a, project_x)

        for tenant, project in ((tenant_b, project_x), (tenant_a, project_y)):
            independent = _database(registry=registry, limit=1)
            with independent._root_transaction_lifecycle():
                assert _acquire(independent, tenant, project)

        blocked = _database(registry=registry, limit=1)
        with pytest.raises(DomainError):
            with blocked._root_transaction_lifecycle():
                _acquire(blocked, tenant_a, project_x)

    assert registry.inspect() == {}


@pytest.mark.parametrize(
    ("error", "release_cause"),
    [
        (None, "commit"),
        (DomainError("VAL-0003", "rollback"), "rollback"),
        (RuntimeError("exception"), "exception"),
        (CancelledError(), "cancel"),
        (KeyboardInterrupt(), "exception"),
    ],
)
def test_root_finalizer_releases_once_for_every_exit(error, release_cause):
    registry = _ProjectPermitRegistry()
    metrics = []
    tenant = str(uuid4())
    db = _database(registry=registry, metrics=metrics, limit=1)

    if error is None:
        with db._root_transaction_lifecycle():
            assert _acquire(db, tenant, "prj_release")
    else:
        with pytest.raises(type(error)):
            with db._root_transaction_lifecycle():
                assert _acquire(db, tenant, "prj_release")
                raise error

    assert registry.inspect() == {}
    released = [item for item in metrics if item["outcome"] == "released"]
    assert len(released) == 1
    assert released[0]["releaseCause"] == release_cause
    assert released[0]["registryEntries"] == 0


def test_reentrant_root_transaction_uses_one_permit_and_savepoint_like_rollback_keeps_it():
    registry = _ProjectPermitRegistry()
    metrics = []
    tenant = str(uuid4())
    project = "prj_reentrant"
    db = _database(registry=registry, metrics=metrics, limit=1)

    with db._root_transaction_lifecycle():
        assert _acquire(db, tenant, project)
        try:
            assert _acquire(db, tenant, project)
            raise DomainError("RES-0007", "savepoint rollback", 503, True)
        except DomainError:
            pass
        assert registry.inspect() == {(tenant, project): 1}

    assert registry.inspect() == {}
    acquired = [item for item in metrics if item["outcome"] == "acquired"]
    released = [item for item in metrics if item["outcome"] == "released"]
    assert [item["reentrant"] for item in acquired] == [False, True]
    assert len(released) == 1


def test_bound_database_delegates_to_outer_root_finalizer():
    registry = _ProjectPermitRegistry()
    tenant = str(uuid4())
    project = "prj_bound_outer"
    root = _database(registry=registry, limit=1)

    with root._root_transaction_lifecycle():
        bound = BoundDatabase(root, tenant, object())
        assert bound.acquire_placement_project_permit(tenant, project)
        assert registry.inspect() == {(tenant, project): 1}

    assert registry.inspect() == {}


def test_exact_replay_and_changed_body_classify_before_permit(monkeypatch):
    calls = []
    database = SimpleNamespace(acquire_placement_project_permit=lambda *args: calls.append(args))
    store = PlacementStore(database)
    principal = SimpleNamespace(tenant_id=str(uuid4()), subject_id="subject")
    prior = {"runId": "run_prior", "placement": {}, "leases": []}

    class Ledger:
        def __init__(self, result=None, error=None):
            self.result, self.error = result, error

        def _ledger(self, *args):
            if self.error is not None:
                raise self.error
            return self.result

    grants = []
    monkeypatch.setattr(
        placement_module,
        "Control",
        lambda db: SimpleNamespace(grant=lambda *args: grants.append(args)),
    )
    assert (
        store._candidate_replay_or_admit(
            object(), Ledger(result=prior), principal, "prj_replay", "key", {}
        )
        == prior
    )
    assert calls == []
    assert len(grants) == 1

    changed = DomainError("IDEM-0001", "different request content")
    with pytest.raises(DomainError, match="IDEM-0001"):
        store._candidate_replay_or_admit(
            object(), Ledger(error=changed), principal, "prj_replay", "key", {}
        )
    assert calls == []

    assert (
        store._candidate_replay_or_admit(object(), Ledger(), principal, "prj_new", "key", {})
        is None
    )
    assert calls == [(principal.tenant_id, "prj_new")]


def test_metrics_are_identifier_free_and_two_registries_can_each_admit_n():
    tenant = str(uuid4())
    project = "prj_private_marker"
    secret = "secret-idempotency-key"
    dsn = "postgresql://user:password@host/database"
    metrics = []
    registry = _ProjectPermitRegistry()
    db = Database(
        dsn,
        recovery_epoch=str(uuid4()),
        placement_short_commit=True,
        placement_project_semaphore_enabled=True,
        placement_metric_sink=metrics.append,
        _placement_permit_registry=registry,
    )
    with db._root_transaction_lifecycle():
        assert _acquire(db, tenant, project)

    rendered = json.dumps(metrics, sort_keys=True)
    for forbidden in (tenant, project, secret, dsn, "password"):
        assert forbidden not in rendered

    registries = (_ProjectPermitRegistry(), _ProjectPermitRegistry())
    key = (tenant, project)
    admitted = sum(
        registry_item.try_acquire(key, 4)["acquired"]
        for registry_item in registries
        for _ in range(4)
    )
    assert admitted == 8
    assert sum(registry_item.inspect()[key] for registry_item in registries) == 8


def test_benchmark_cli_keeps_semaphore_opt_in_and_bounded(monkeypatch, tmp_path):
    seen = []
    monkeypatch.setattr(
        placement_benchmark,
        "_run_pytest_adapter",
        lambda args: seen.append((args.project_semaphore, args.project_semaphore_limit)) or 0,
    )
    common = [
        "--requests",
        "1",
        "--concurrency",
        "1",
        "--rounds",
        "1",
        "--junit",
        str(tmp_path / "result.xml"),
        "--report",
        str(tmp_path / "result.json"),
    ]
    assert placement_benchmark.main(common) == 0
    assert seen == [(False, 4)]

    assert (
        placement_benchmark.main(
            common
            + [
                "--mode",
                "short-commit",
                "--project-semaphore",
                "--project-semaphore-limit",
                "4",
            ]
        )
        == 0
    )
    assert seen[-1] == (True, 4)

    with pytest.raises(SystemExit, match="only valid with --mode short-commit"):
        placement_benchmark.main(common + ["--project-semaphore"])
    with pytest.raises(SystemExit, match="must be between 1 and 20"):
        placement_benchmark.main(
            common
            + [
                "--mode",
                "short-commit",
                "--project-semaphore",
                "--project-semaphore-limit",
                "21",
            ]
        )
    with pytest.raises(SystemExit, match="only valid with --project-semaphore"):
        placement_benchmark.main(common + ["--project-semaphore-limit", "3"])


def test_benchmark_adapter_passes_semaphore_only_through_test_env(monkeypatch, tmp_path):
    captured = {}
    monkeypatch.setattr(
        placement_benchmark.subprocess,
        "check_output",
        lambda *args, **kwargs: "reachable-sha\n",
    )

    def completed(command, *, cwd, env, timeout):
        captured.update({"command": command, "env": env})
        return SimpleNamespace(returncode=0)

    monkeypatch.setattr(placement_benchmark.subprocess, "run", completed)
    args = placement_benchmark.parse_args(
        [
            "--requests",
            "1",
            "--concurrency",
            "1",
            "--rounds",
            "1",
            "--mode",
            "short-commit",
            "--project-semaphore",
            "--project-semaphore-limit",
            "4",
            "--junit",
            str(tmp_path / "result.xml"),
            "--report",
            str(tmp_path / "result.json"),
        ]
    )
    assert placement_benchmark._run_pytest_adapter(args) == 0
    assert captured["env"]["INV_PLACEMENT_PROJECT_SEMAPHORE"] == "1"
    assert captured["env"]["INV_PLACEMENT_PROJECT_SEMAPHORE_LIMIT"] == "4"


def test_benchmark_classifies_semaphore_reject_separately_from_sql_timeout():
    def rejected(_index):
        raise DomainError(
            "RES-0007",
            "Transaction contention; retry with the same key",
            503,
            retryable=True,
        ) from _PlacementSemaphoreLimit("project-semaphore-limit")

    evidence, samples = placement_benchmark.run_round(
        name="semaphore-reject",
        request_count=1,
        concurrency=1,
        reserve=rejected,
    )
    assert evidence.failure_count == 1
    assert evidence.errors_by_code == {"RES-0007": 1}
    assert evidence.errors_by_sqlstate == {"none": 1}
    assert samples[0].cause_type == "_PlacementSemaphoreLimit"
    assert samples[0].sqlstate is None
    assert samples[0].timeout_kind is None
