"""Manual ApprovalStore response validators must protect their real serving methods."""

from contextlib import contextmanager
from datetime import datetime, timezone
import json
from pathlib import Path
from types import SimpleNamespace

import pytest

from inv.approvals import ApprovalStore, Principal
from inv.errors import DomainError

ROOT = Path(__file__).resolve().parents[2]
FIXTURES = ROOT / "contracts" / "fixtures"
TENANT = "00000000-0000-4000-8000-000000000041"


def fixture(name):
    return json.loads((FIXTURES / name).read_text(encoding="utf-8"))


class _Database:
    def __init__(self, row=None):
        self.row = row or {}

    @contextmanager
    def transaction(self, _tenant_id):
        yield SimpleNamespace(
            execute=lambda *_args, **_kwargs: SimpleNamespace(fetchone=lambda: self.row)
        )


@pytest.mark.parametrize(
    ("contract", "method", "broken_response"),
    [
        ("ApprovalReviewView", "review", {"approval": {}, "workload": {}, "riskLevel": "L1"}),
    ],
)
def test_approval_review_serving_method_rejects_invalid_response(monkeypatch, contract, method, broken_response):
    store = ApprovalStore(_Database())
    monkeypatch.setattr(store, "_locked", lambda *_args: ({}, {}))
    monkeypatch.setattr(store, "_grant", lambda *_args: None)
    monkeypatch.setattr(store, "_current", lambda *_args: None)
    monkeypatch.setattr(store, "_review_snapshot", lambda *_args: broken_response)
    with pytest.raises(DomainError, match="VAL-0002"):
        getattr(store, method)(Principal(TENANT, "reviewer"), "prj_contract", "apr_01ARZ3NDEKTSV4RRFFQ69G5FAV")


def test_approval_challenge_serving_method_rejects_invalid_generated_nonce(monkeypatch):
    expires_at = datetime(2099, 1, 1, tzinfo=timezone.utc)
    class ChallengeDatabase:
        @contextmanager
        def transaction(self, _tenant_id):
            class Connection:
                def execute(self, statement, *_args, **_kwargs):
                    if "SELECT 1 FROM inv.approval_votes" in statement:
                        return SimpleNamespace(fetchone=lambda: None)
                    return SimpleNamespace(fetchone=lambda: {"expires_at": expires_at})

            yield Connection()

    store = ApprovalStore(ChallengeDatabase())
    row = {"requester_id": "requester", "expires_at": expires_at}
    monkeypatch.setattr(store, "_locked", lambda *_args: ({}, row))
    monkeypatch.setattr(store, "_grant", lambda *_args: None)
    monkeypatch.setattr(store, "_current", lambda *_args: None)
    monkeypatch.setattr("inv.approvals.secrets.token_urlsafe", lambda _size: "short")

    with pytest.raises(DomainError, match="VAL-0002"):
        store.challenge(Principal(TENANT, "reviewer"), "prj_contract", "apr_01ARZ3NDEKTSV4RRFFQ69G5FAV")
