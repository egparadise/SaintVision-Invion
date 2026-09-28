"""Fail-closed provider selection before immutable object I/O or state change."""

from contextlib import contextmanager
import json
from types import SimpleNamespace
from uuid import UUID

import pytest

from inv.app import _configured_object_stores
from inv.errors import DomainError
from inv.object_store import (
    LOCAL_PROVIDER_ID,
    LocalObjectStore,
    ObjectStoreRegistry,
    require_object_provider,
)
from inv.snapshots import SnapshotStore
from inv.workspace_recovery import WorkspaceRecovery

OBJECT = UUID("22222222-2222-4222-8222-222222222222")
ROW = {
    "object_id": OBJECT,
    "provider_id": "s3-compatible-v1",
    "locator": "opaque-locator",
    "content_hash": "a" * 64,
    "size_bytes": 7,
    "state": "ready",
}


class Provider:
    def __init__(self, provider_id, body=b"payload"):
        self.provider_id = provider_id
        self.body = body
        self.calls = []

    def get(self, locator, digest, size):
        self.calls.append(("get", locator, digest, size))
        return self.body

    def delete(self, locator):
        self.calls.append(("delete", locator))


class Result:
    def __init__(self, *, one=None, many=None):
        self.one, self.many = one, many or []

    def fetchone(self):
        return self.one

    def fetchall(self):
        return self.many


class Connection:
    def __init__(self, row):
        self.row = row
        self.statements = []

    def execute(self, statement, params=()):
        self.statements.append((statement, params))
        if "FROM inv.runs" in statement:
            return Result(one={"project_id": "project"})
        if "FROM inv.checkpoint_objects" in statement:
            return Result(one={"object_id": OBJECT})
        if "FROM inv.storage_objects" in statement and "SELECT *" in statement:
            return Result(one=self.row)
        if "FROM inv.storage_budgets" in statement:
            return Result(one={"quota_bytes": 100})
        return Result()


class Database:
    def __init__(self, row):
        self.connection = Connection(row)

    @contextmanager
    def transaction(self, _tenant):
        yield self.connection


def test_provider_mismatch_is_retryable_503():
    with pytest.raises(DomainError) as raised:
        require_object_provider(Provider(LOCAL_PROVIDER_ID), ROW)
    assert (raised.value.code, raised.value.status, raised.value.retryable) == (
        "STORE-0001",
        503,
        True,
    )


def test_mixed_provider_collect_fails_before_deleting_state_or_bytes():
    database = Database(dict(ROW))
    local = Provider(LOCAL_PROVIDER_ID)
    store = SnapshotStore(database, local)
    with pytest.raises(DomainError, match="STORE-0001"):
        store.collect("tenant", "project", OBJECT)
    assert local.calls == []
    assert not any("SET state='deleting'" in sql for sql, _ in database.connection.statements)


def test_restore_resolves_the_persisted_provider_from_registry():
    database = Database(dict(ROW))
    local = Provider(LOCAL_PROVIDER_ID)
    remote = Provider("s3-compatible-v1")
    store = SnapshotStore(
        database,
        local,
        ObjectStoreRegistry([local, remote]),
    )
    assert store.restore("tenant", "project", "run", 1, "step") == b"payload"
    assert local.calls == []
    assert remote.calls == [("get", "opaque-locator", "a" * 64, 7)]


def test_workspace_recovery_resolves_the_persisted_checkpoint_provider():
    database = Database(dict(ROW))
    local = Provider(LOCAL_PROVIDER_ID)
    remote = Provider("s3-compatible-v1")
    store = SnapshotStore(database, local, ObjectStoreRegistry([local, remote]))
    recovery = WorkspaceRecovery(store, generations=None)

    assert recovery._checkpoint_reader("tenant", "project", "run", 1, "step") is remote
    assert local.calls == [] and remote.calls == []


def test_configured_registry_always_includes_recovery_local_and_optional_s3():
    legacy = object()
    snapshots = SimpleNamespace(provider=legacy, object_stores=None)
    workspace = SimpleNamespace(recovery=SimpleNamespace(snapshots=snapshots))
    local_only = _configured_object_stores(workspace)
    assert isinstance(local_only.resolve(LOCAL_PROVIDER_ID), LocalObjectStore)
    assert snapshots.object_stores is local_only

    remote = Provider("s3-compatible-v1")
    combined = _configured_object_stores(workspace, remote)
    assert isinstance(combined.resolve(LOCAL_PROVIDER_ID), LocalObjectStore)
    assert combined.resolve("s3-compatible-v1") is remote
    assert snapshots.object_stores is combined


def test_create_configured_app_propagates_local_only_and_combined_registries(monkeypatch, tmp_path):
    import inv.app as app_module
    import inv.configuration_readiness as readiness_module
    import inv.object_store_config as config_module
    import inv.workspace_config as workspace_module

    configuration = tmp_path / "operator.json"
    monkeypatch.setenv("INV_API_CONFIG", str(configuration))
    monkeypatch.setenv("INV_RUNTIME_DSN", "postgresql://not-connected")
    monkeypatch.setenv("INV_RECOVERY_EPOCH", "11111111-1111-4111-8111-111111111111")
    monkeypatch.setattr(
        app_module,
        "AccessTokens",
        lambda **_kwargs: SimpleNamespace(tenant_id="tenant"),
    )
    legacy = object()
    snapshots = SimpleNamespace(provider=legacy, object_stores=None)
    workspace = SimpleNamespace(recovery=SimpleNamespace(snapshots=snapshots))
    monkeypatch.setattr(workspace_module, "configured_workspace", lambda *_args: workspace)
    monkeypatch.setattr(readiness_module, "configured_s01_readiness", lambda _value: None)
    captured = []
    monkeypatch.setattr(
        app_module,
        "create_app",
        lambda *_args, **kwargs: captured.append(kwargs["object_stores"])
        or kwargs["object_stores"],
    )

    configuration.write_text(json.dumps({"identity": {}, "workspace": {}}), encoding="utf-8")
    local = app_module.create_configured_app()
    assert isinstance(local.resolve(LOCAL_PROVIDER_ID), LocalObjectStore)

    remote = Provider("s3-compatible-v1")
    monkeypatch.setattr(config_module, "parse_object_store_configuration", lambda _value: object())
    monkeypatch.setattr(config_module, "unresolved_object_store", lambda _value: [])
    monkeypatch.setattr(config_module, "configured_object_store", lambda _value: remote)
    configuration.write_text(
        json.dumps(
            {
                "identity": {},
                "workspace": {},
                "configurationReadiness": {"objectStore": {}},
            }
        ),
        encoding="utf-8",
    )
    combined = app_module.create_configured_app()
    assert isinstance(combined.resolve(LOCAL_PROVIDER_ID), LocalObjectStore)
    assert combined.resolve("s3-compatible-v1") is remote
    assert captured == [local, combined]
