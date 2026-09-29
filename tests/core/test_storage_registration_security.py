"""Storage contribution idempotency serialization and conflict translation."""

from __future__ import annotations

from contextlib import contextmanager, nullcontext
import datetime as dt
from types import SimpleNamespace
import uuid

import pytest
from sqlalchemy.exc import IntegrityError

from saintvision.api import schemas
from saintvision.api.v1 import storage
from saintvision.config import Settings
from saintvision.errors import GRAPH_INVALID_TRANSITION, InvError
from saintvision.identity.principal import Principal


TENANT = uuid.UUID("cf179c2a-1f1e-489e-8a92-a6aca19077dd")
PRINCIPAL = Principal("usr_storage_owner", TENANT, "storage-owner")
NOW = dt.datetime(2026, 9, 29, 2, 35, tzinfo=dt.timezone.utc)
PAYLOAD = schemas.ContributionRequest(
    nodeId="nod_01ARZ3NDEKTSV4RRFFQ69G5FAV",
    declaredPath="/srv/inv/share",
)


class _Session:
    def begin_nested(self):
        return nullcontext()


class _Original(Exception):
    def __init__(self, constraint):
        super().__init__(constraint or "integrity error")
        self.diag = SimpleNamespace(constraint_name=constraint)


def _integrity(constraint):
    return IntegrityError("statement", {}, _Original(constraint))


def _request():
    return SimpleNamespace(
        state=SimpleNamespace(trace_id="trc_storage"),
        client=SimpleNamespace(host="127.0.0.1"),
        headers={"user-agent": "pytest"},
    )


def _settings():
    return Settings(
        database_url="postgresql://unused",
        idempotency_ttl_seconds=600,
        business_lock_timeout_ms=500,
    )


def _install_lock_spies(monkeypatch, calls):
    @contextmanager
    def bounded(_session, *, timeout_ms):
        calls.append(("bounded", timeout_ms))
        yield

    monkeypatch.setattr(storage, "bounded_lock_wait", bounded)
    monkeypatch.setattr(
        storage,
        "serialise_idempotent_write",
        lambda *_args, **_kwargs: calls.append(("serialise", _kwargs["idempotency_key"])),
    )


def test_replay_serialises_before_ledger_read_and_skips_side_effect(monkeypatch):
    calls = []
    replay = {"contribution": {"contributionId": "stc_existing"}}
    _install_lock_spies(monkeypatch, calls)
    monkeypatch.setattr(
        storage,
        "replay_or_reserve",
        lambda *_args, **_kwargs: calls.append(("replay", _kwargs["idempotency_key"])) or replay,
    )
    monkeypatch.setattr(
        storage.storage_service,
        "register_contribution",
        lambda *_args, **_kwargs: pytest.fail("replay must not call the service"),
    )

    result = storage.register_contribution(
        request=_request(), payload=PAYLOAD, principal=PRINCIPAL, session=_Session(),
        settings=_settings(), now=NOW, idempotency_key="idem-1",
    )

    assert result == replay
    assert calls == [("bounded", 500), ("serialise", "idem-1"), ("replay", "idem-1")]


def test_registered_path_unique_conflict_is_409_without_key(monkeypatch):
    calls = []
    _install_lock_spies(monkeypatch, calls)
    monkeypatch.setattr(storage, "replay_or_reserve", lambda *_args, **_kwargs: None)
    monkeypatch.setattr(
        storage.storage_service,
        "register_contribution",
        lambda *_args, **_kwargs: (_ for _ in ()).throw(
            _integrity(storage._CONTRIBUTION_PATH_UNIQUE)
        ),
    )

    with pytest.raises(InvError) as caught:
        storage.register_contribution(
            request=_request(), payload=PAYLOAD, principal=PRINCIPAL, session=_Session(),
            settings=_settings(), now=NOW, idempotency_key=None,
        )

    assert caught.value.code == GRAPH_INVALID_TRANSITION
    assert caught.value.status == 409
    assert calls == [("bounded", 500)]


def test_unknown_integrity_error_is_not_relabelled_as_client_conflict(monkeypatch):
    _install_lock_spies(monkeypatch, [])
    monkeypatch.setattr(storage, "replay_or_reserve", lambda *_args, **_kwargs: None)
    monkeypatch.setattr(
        storage.storage_service,
        "register_contribution",
        lambda *_args, **_kwargs: (_ for _ in ()).throw(_integrity("unexpected_constraint")),
    )

    with pytest.raises(IntegrityError):
        storage.register_contribution(
            request=_request(), payload=PAYLOAD, principal=PRINCIPAL, session=_Session(),
            settings=_settings(), now=NOW, idempotency_key=None,
        )


def test_first_write_keeps_service_audit_and_ledger_in_one_serialised_scope(monkeypatch):
    calls = []
    contribution = SimpleNamespace(
        contribution_id="stc_created",
        node_id=PAYLOAD.node_id,
        declared_path=PAYLOAD.declared_path,
        normalized_path=PAYLOAD.declared_path,
        mode="read_only",
        status="pending",
        capacity_bytes=None,
        available_bytes=None,
        registered_at=NOW,
    )
    _install_lock_spies(monkeypatch, calls)
    monkeypatch.setattr(
        storage,
        "replay_or_reserve",
        lambda *_args, **_kwargs: calls.append(("replay", _kwargs["idempotency_key"])),
    )
    monkeypatch.setattr(
        storage.storage_service,
        "register_contribution",
        lambda *_args, **_kwargs: calls.append(("service", None)) or contribution,
    )
    monkeypatch.setattr(
        storage,
        "record_event",
        lambda *_args, **_kwargs: calls.append(("audit", _kwargs["target_id"])),
    )
    monkeypatch.setattr(
        storage,
        "store_idempotent_response",
        lambda *_args, **_kwargs: calls.append(("ledger", _kwargs["idempotency_key"])),
    )

    result = storage.register_contribution(
        request=_request(), payload=PAYLOAD, principal=PRINCIPAL, session=_Session(),
        settings=_settings(), now=NOW, idempotency_key="idem-2",
    )

    assert result["contribution"]["contributionId"] == "stc_created"
    assert calls == [
        ("bounded", 500),
        ("serialise", "idem-2"),
        ("replay", "idem-2"),
        ("service", None),
        ("audit", "stc_created"),
        ("ledger", "idem-2"),
    ]
