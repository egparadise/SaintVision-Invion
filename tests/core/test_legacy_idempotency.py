"""Optional ledger consumption for the seven legacy audit-producing writes."""

from __future__ import annotations

from contextlib import contextmanager
import datetime as dt
import inspect
from types import SimpleNamespace
import uuid

import pytest

from saintvision.api import deps, schemas
from saintvision.api.v1 import projects, settings
from saintvision.config import Settings
from saintvision.identity.principal import Principal


TENANT = uuid.UUID("cf179c2a-1f1e-489e-8a92-a6aca19077dd")
PRINCIPAL = Principal("usr_legacy_actor", TENANT, "legacy-actor")
NOW = dt.datetime(2026, 9, 29, 2, 45, tzinfo=dt.timezone.utc)
CONFIG = Settings(
    database_url="postgresql://unused",
    idempotency_ttl_seconds=600,
    business_lock_timeout_ms=500,
)
REQUEST = SimpleNamespace(state=SimpleNamespace(trace_id="trc_legacy"))


def test_optional_helper_serialises_before_replay_and_finishes_same_ledger(monkeypatch):
    calls = []

    @contextmanager
    def bounded(_session, *, timeout_ms):
        calls.append(("bounded", timeout_ms))
        yield

    monkeypatch.setattr("saintvision.api.lock_wait.bounded_lock_wait", bounded)
    monkeypatch.setattr(
        deps,
        "serialise_idempotent_write",
        lambda *_args, **kwargs: calls.append(("serialise", kwargs["idempotency_key"])),
    )
    monkeypatch.setattr(
        deps,
        "replay_or_reserve",
        lambda *_args, **kwargs: calls.append(("replay", kwargs["payload"])) or None,
    )
    monkeypatch.setattr(
        deps,
        "store_idempotent_response",
        lambda *_args, **kwargs: calls.append(("store", kwargs["response_body"])),
    )

    with deps.optional_idempotent_write(
        object(), principal=PRINCIPAL, endpoint="PUT /legacy", idempotency_key="idem-1",
        payload={"value": 1}, now=NOW, ttl_seconds=600, lock_timeout_ms=500,
    ) as (replay, finish):
        assert replay is None
        finish({"ok": True})

    assert calls == [
        ("bounded", 500),
        ("serialise", "idem-1"),
        ("replay", {"value": 1}),
        ("store", {"ok": True}),
    ]


def test_optional_helper_yields_the_stored_replay_without_finishing(monkeypatch):
    stored = {"projectId": "prj_replay", "status": "archived"}

    @contextmanager
    def bounded(_session, *, timeout_ms):
        assert timeout_ms == 500
        yield

    monkeypatch.setattr("saintvision.api.lock_wait.bounded_lock_wait", bounded)
    monkeypatch.setattr(deps, "serialise_idempotent_write", lambda *_args, **_kwargs: None)
    monkeypatch.setattr(deps, "replay_or_reserve", lambda *_args, **_kwargs: stored)
    monkeypatch.setattr(
        deps,
        "store_idempotent_response",
        lambda *_args, **_kwargs: pytest.fail("a replay must not write another ledger result"),
    )

    with deps.optional_idempotent_write(
        object(), principal=PRINCIPAL, endpoint="PUT /legacy", idempotency_key="idem-hit",
        payload={"status": "archived"}, now=NOW, ttl_seconds=600, lock_timeout_ms=500,
    ) as (replay, _finish):
        assert replay is stored


def test_optional_helper_without_key_bounds_but_does_not_take_advisory_lock(monkeypatch):
    calls = []

    @contextmanager
    def bounded(_session, *, timeout_ms):
        calls.append(("bounded", timeout_ms))
        yield

    monkeypatch.setattr("saintvision.api.lock_wait.bounded_lock_wait", bounded)
    monkeypatch.setattr(
        deps,
        "serialise_idempotent_write",
        lambda *_args, **_kwargs: pytest.fail("no key must not take an advisory lock"),
    )
    monkeypatch.setattr(deps, "replay_or_reserve", lambda *_args, **_kwargs: None)
    monkeypatch.setattr(deps, "store_idempotent_response", lambda *_args, **_kwargs: None)

    with deps.optional_idempotent_write(
        object(), principal=PRINCIPAL, endpoint="DELETE /legacy", idempotency_key=None,
        payload={}, now=NOW, ttl_seconds=600, lock_timeout_ms=500,
    ) as (replay, finish):
        assert replay is None
        finish({"removed": True})

    assert calls == [("bounded", 500)]


@pytest.mark.parametrize(
    ("module", "route", "kwargs"),
    [
        (
            projects,
            projects.set_workspace_tool,
            {
                "workspace_id": "wsp_replay",
                "payload": schemas.WorkspaceToolRequest(toolName="codex-cli"),
            },
        ),
        (
            settings,
            settings.set_member_role,
            {
                "project_id": "prj_replay",
                "user_id": "usr_target",
                "payload": schemas.MemberRoleRequest(roleCode="viewer"),
            },
        ),
        (
            settings,
            settings.remove_member,
            {"project_id": "prj_replay", "user_id": "usr_target"},
        ),
        (
            settings,
            settings.set_user_status,
            {"user_id": "usr_target", "payload": schemas.UserStatusRequest(status="suspended")},
        ),
        (
            settings,
            settings.set_project_status,
            {
                "project_id": "prj_replay",
                "payload": schemas.ProjectStatusRequest(status="archived"),
            },
        ),
        (
            settings,
            settings.set_workspace_status,
            {
                "workspace_id": "wsp_replay",
                "payload": schemas.WorkspaceStatusRequest(status="suspended"),
            },
        ),
        (
            settings,
            settings.set_resource_offer,
            {
                "capability_id": "cap_replay",
                "payload": schemas.ResourceOfferRequest(offeredQuantity=1, unit="cores"),
            },
        ),
    ],
)
def test_every_legacy_audit_write_replays_before_service_or_audit(
    monkeypatch, module, route, kwargs
):
    replay = {"replayed": route.__name__}
    seen = []

    @contextmanager
    def optional_write(*_args, **options):
        seen.append(options)
        yield replay, lambda *_finish_args, **_finish_kwargs: pytest.fail(
            "replay must not write a second ledger result"
        )

    monkeypatch.setattr(module, "optional_idempotent_write", optional_write)
    if module is projects:
        monkeypatch.setattr(
            projects.project_service,
            "require_project_access",
            lambda *_args, **_kwargs: {"canRequest": True, "roleCode": "owner"},
        )
        monkeypatch.setattr(
            projects.project_service,
            "set_workspace_tool",
            lambda *_args, **_kwargs: pytest.fail("replay reached service"),
        )
        monkeypatch.setattr(
            projects, "record_event", lambda *_args, **_kwargs: pytest.fail("replay audited")
        )
    else:
        monkeypatch.setattr(
            settings.settings_service, "require_administrator", lambda *_args, **_kwargs: None
        )
        monkeypatch.setattr(
            settings.settings_service,
            "require_global_administrator",
            lambda *_args, **_kwargs: None,
        )
        monkeypatch.setattr(settings, "_audit", lambda *_args, **_kwargs: pytest.fail("replay audited"))

    session = SimpleNamespace(
        get=lambda *_args, **_kwargs: SimpleNamespace(
            tenant_id=TENANT,
            project_id="prj_replay",
        )
    )
    result = route(
        **kwargs,
        request=REQUEST,
        principal=PRINCIPAL,
        session=session,
        settings=CONFIG,
        now=NOW,
        idempotency_key="idem-replay",
    )

    assert result == replay
    assert len(seen) == 1
    assert seen[0]["idempotency_key"] == "idem-replay"
    assert "idempotency_key" in inspect.signature(route).parameters
