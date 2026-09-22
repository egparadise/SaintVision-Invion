"""Run and approval pages share strict fixtures with the web observation adapter."""

from __future__ import annotations

from contextlib import contextmanager
from datetime import datetime
import json
from pathlib import Path
from types import SimpleNamespace
import uuid

import pytest
from pydantic import ValidationError

from inv.approvals import view
from inv.control import Control
from inv.contracts import validate_contract
from inv.errors import DomainError
from inv.generated.models import (
    ApprovalPage,
    BusinessEditLockView,
    ControlRunDetail,
    ControlRunPage,
)

ROOT = Path(__file__).resolve().parents[2]
FIXTURES = ROOT / "contracts" / "fixtures"


def fixture(name: str) -> dict:
    return json.loads((FIXTURES / name).read_text(encoding="utf-8"))


@pytest.mark.parametrize(
    ("filename", "contract", "model"),
    [
        ("control-run-page-response.json", "ControlRunPage", ControlRunPage),
        ("approval-page-response.json", "ApprovalPage", ApprovalPage),
    ],
)
def test_shared_page_fixtures_match_runtime_and_generated_contracts(filename, contract, model):
    payload = fixture(filename)
    validate_contract(contract, payload)
    serialized = model.model_validate(payload).model_dump(by_alias=True, mode="json")
    if contract == "ApprovalPage":
        # The wire provider uses datetime.isoformat() (+00:00); Pydantic's JSON
        # serializer canonicalizes the same UTC instant as Z.
        serialized["items"][0]["expiresAt"] = payload["items"][0]["expiresAt"]
    assert serialized == payload


@pytest.mark.parametrize(
    ("filename", "model"),
    [
        ("control-run-page-response.json", ControlRunPage),
        ("approval-page-response.json", ApprovalPage),
    ],
)
def test_page_contract_rejects_a_missing_cursor_field(filename, model):
    payload = fixture(filename)
    payload.pop("nextCursor")
    with pytest.raises(ValidationError):
        model.model_validate(payload)


class _Rows:
    def __init__(self, rows):
        self.rows = rows

    def fetchall(self):
        return self.rows

    def fetchone(self):
        return self.rows[0] if self.rows else None


class _Connection:
    def __init__(self, rows):
        self.rows = rows

    def execute(self, *_args, **_kwargs):
        return _Rows(self.rows)


class _Database:
    def __init__(self, rows):
        self.connection = _Connection(rows)

    @contextmanager
    def transaction(self, _tenant_id):
        yield self.connection


def _control_with_rows(monkeypatch, rows):
    control = Control(_Database(rows))
    monkeypatch.setattr(control, "grant", lambda *_args, **_kwargs: None)
    return control


def test_run_listing_provider_returns_the_shared_control_page_fixture(monkeypatch):
    expected = fixture("control-run-page-response.json")
    run = expected["items"][0]
    row = {
        "run_id": run["runId"],
        "tenant_id": uuid.UUID(run["tenantId"]),
        "project_id": run["projectId"],
        "state": run["state"],
        "version": run["version"],
        "attempt": run["attempt"],
    }
    result = _control_with_rows(monkeypatch, [row]).list_runs(
        SimpleNamespace(tenant_id=uuid.UUID(run["tenantId"])), run["projectId"]
    )
    assert result == expected


def test_control_run_view_fixture_is_the_single_run_contract():
    """The single-run/create projection uses the same canonical wire view."""
    payload = fixture("control-run-page-response.json")["items"][0]
    validate_contract("ControlRunView", payload)


def test_control_run_detail_fixture_matches_the_get_response_contract():
    payload = fixture("control-run-detail-response.json")
    validate_contract("ControlRunDetail", payload)
    assert ControlRunDetail.model_validate(payload).model_dump(mode="json") == payload


def test_control_run_detail_rejects_missing_release_hint():
    payload = fixture("control-run-detail-response.json")
    payload.pop("resourceReleasePending")
    with pytest.raises(ValidationError):
        ControlRunDetail.model_validate(payload)


def test_single_run_anchor_rejects_an_invalid_state(monkeypatch):
    """Removing the get() anchor must make this serving-path test fail."""
    expected = fixture("control-run-page-response.json")["items"][0]
    row = {
        "run_id": expected["runId"],
        "tenant_id": uuid.UUID(expected["tenantId"]),
        "project_id": expected["projectId"],
        "state": "not-a-run-state",
        "version": expected["version"],
        "attempt": expected["attempt"],
    }

    class _GetConnection(_Connection):
        def execute(self, sql, *_args, **_kwargs):
            if "SELECT * FROM inv.runs" in sql:
                return _Rows([row])
            return _Rows([{"n": 0}])

    class _GetDatabase(_Database):
        def __init__(self):
            self.connection = _GetConnection([row])

    control = Control(_GetDatabase())
    monkeypatch.setattr(control, "grant", lambda *_args, **_kwargs: None)
    with pytest.raises(DomainError, match="ControlRunDetail: invalid contract"):
        control.get(
            SimpleNamespace(tenant_id=uuid.UUID(expected["tenantId"])),
            expected["projectId"],
            expected["runId"],
        )


def test_run_creation_anchor_rejects_an_invalid_state(monkeypatch):
    """The POST producer is anchored before its event/outbox side effects."""
    expected = fixture("control-run-page-response.json")["items"][0]
    row = {
        "run_id": expected["runId"],
        "tenant_id": uuid.UUID(expected["tenantId"]),
        "project_id": expected["projectId"],
        "state": "not-a-run-state",
        "version": expected["version"],
        "attempt": expected["attempt"],
    }

    class _CreateConnection:
        def execute(self, sql, *_args, **_kwargs):
            if "INSERT INTO inv.runs" in sql:
                return _Rows([row])
            return _Rows([])

    class _CreateDatabase:
        @contextmanager
        def transaction(self, _tenant_id):
            yield _CreateConnection()

    control = Control(_CreateDatabase())
    monkeypatch.setattr(control, "grant", lambda *_args, **_kwargs: None)
    monkeypatch.setattr(control.approvals, "_ledger", lambda *_args, **_kwargs: None)
    monkeypatch.setattr(control.approvals, "_save", lambda *_args, **_kwargs: row)
    monkeypatch.setattr("inv.containment.require_execution", lambda _conn: None)
    with pytest.raises(DomainError, match="ControlRunView: invalid contract"):
        control.create(
            SimpleNamespace(tenant_id=uuid.UUID(expected["tenantId"])),
            expected["projectId"],
            "idem-1",
        )


def test_parent_cancel_anchor_rejects_an_invalid_state(monkeypatch):
    """The shard-parent cancel response is a serving path, not only a fixture."""
    expected = fixture("control-run-page-response.json")["items"][0]

    class _ShardRuntime:
        def __init__(self, *_args, **_kwargs):
            pass

        def cancel(self, *_args, **_kwargs):
            invalid = dict(expected)
            invalid["state"] = "not-a-run-state"
            return {"parentRun": invalid}

    monkeypatch.setattr("inv.shards.ShardRuntime", _ShardRuntime)
    control = Control(_Database([{"plan_id": "plan-1"}]))

    with pytest.raises(DomainError, match="ControlRunView: invalid contract"):
        control.cancel(
            SimpleNamespace(tenant_id=uuid.UUID(expected["tenantId"])),
            expected["projectId"],
            expected["runId"],
            expected["version"],
            "cancel-parent-anchor",
        )


def test_business_edit_lock_view_contract_rejects_missing_target_identity():
    payload = {
        "lockId": "00000000-0000-4000-8000-000000000042",
        "workspaceId": "wsp_0123456789ABCDEFGHJKMNPQRS",
        "runId": "run_0123456789ABCDEFGHJKMNPQRS",
        "contentSha256": "0" * 64,
        "inputSizeBytes": 1,
    }
    validate_contract("BusinessEditLockView", payload)
    assert BusinessEditLockView.model_validate(payload).model_dump(mode="json") == payload
    payload.pop("lockId")
    with pytest.raises(ValidationError):
        BusinessEditLockView.model_validate(payload)


def test_approval_listing_provider_returns_the_shared_approval_page_fixture(monkeypatch):
    expected = fixture("approval-page-response.json")
    approval = expected["items"][0]
    row = {
        "approval_id": approval["approvalId"],
        "run_id": approval["runId"],
        "project_id": approval["projectId"],
        "requester_id": approval["requesterId"],
        "action_digest": approval["actionDigest"],
        "policy_version": approval["policyVersion"],
        "required_approvals": approval["requiredApprovals"],
        "status": approval["status"],
        "expires_at": datetime.fromisoformat(approval["expiresAt"].replace("Z", "+00:00")),
        "bound_run_version": approval["runVersion"],
    }
    result = _control_with_rows(monkeypatch, [row]).list_approvals(
        SimpleNamespace(tenant_id=uuid.UUID("00000000-0000-4000-8000-000000000041")),
        approval["projectId"],
    )
    assert result == expected


def test_approval_view_is_the_same_projection_used_by_approval_listing():
    approval = fixture("approval-page-response.json")["items"][0]
    row = {
        "approval_id": approval["approvalId"],
        "run_id": approval["runId"],
        "project_id": approval["projectId"],
        "requester_id": approval["requesterId"],
        "action_digest": approval["actionDigest"],
        "policy_version": approval["policyVersion"],
        "required_approvals": approval["requiredApprovals"],
        "status": approval["status"],
        "expires_at": datetime.fromisoformat(approval["expiresAt"].replace("Z", "+00:00")),
        "bound_run_version": approval["runVersion"],
    }
    assert view(row) == approval


@pytest.mark.parametrize(
    ("method", "contract", "row_field", "bad_value"),
    [
        ("list_runs", "ControlRunPage", "state", "not-a-run-state"),
        ("list_approvals", "ApprovalPage", "status", "not-an-approval-state"),
    ],
)
def test_listing_serving_path_rejects_invalid_response_before_return(
    monkeypatch, method, contract, row_field, bad_value
):
    """A fixture-only test must not be the only protection for the runtime anchor."""
    if contract == "ControlRunPage":
        expected = fixture("control-run-page-response.json")["items"][0]
        row = {
            "run_id": expected["runId"],
            "tenant_id": uuid.UUID(expected["tenantId"]),
            "project_id": expected["projectId"],
            "state": expected["state"],
            "version": expected["version"],
            "attempt": expected["attempt"],
        }
        principal = SimpleNamespace(tenant_id=uuid.UUID(expected["tenantId"]))
        project = expected["projectId"]
    else:
        expected = fixture("approval-page-response.json")["items"][0]
        row = {
            "approval_id": expected["approvalId"],
            "run_id": expected["runId"],
            "project_id": expected["projectId"],
            "requester_id": expected["requesterId"],
            "action_digest": expected["actionDigest"],
            "policy_version": expected["policyVersion"],
            "required_approvals": expected["requiredApprovals"],
            "status": expected["status"],
            "expires_at": datetime.fromisoformat(expected["expiresAt"].replace("Z", "+00:00")),
            "bound_run_version": expected["runVersion"],
        }
        principal = SimpleNamespace(tenant_id=uuid.UUID("00000000-0000-4000-8000-000000000041"))
        project = expected["projectId"]
    row[row_field] = bad_value
    control = _control_with_rows(monkeypatch, [row])

    with pytest.raises(DomainError, match="VAL-0002"):
        getattr(control, method)(principal, project)
