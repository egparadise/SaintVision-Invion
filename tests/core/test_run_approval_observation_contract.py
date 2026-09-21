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
from inv.generated.models import ApprovalPage, ControlRunPage

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
