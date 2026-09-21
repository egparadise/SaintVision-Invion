"""A syntactically valid command ID alone must never authorize a PTY ticket."""

from contextlib import contextmanager
import json
from types import SimpleNamespace

import pytest

from inv.approvals import Principal
from inv.app import problem
from inv.errors import DomainError
from inv.terminal import TerminalService

TENANT = "00000000-0000-4000-8000-000000000002"


class _NoCommandRow:
    def __init__(self):
        self.statements = []

    def execute(self, statement, params=()):
        self.statements.append((statement, params))
        return SimpleNamespace(fetchone=lambda: None)


class _NoCommandDatabase:
    recovery_epoch = "00000000-0000-4000-8000-000000000001"

    def __init__(self):
        self.connection = _NoCommandRow()

    @contextmanager
    def transaction(self, tenant_id):
        assert tenant_id == TENANT
        yield self.connection


def test_known_placeholder_uuid_without_approved_execution_cannot_issue_ticket():
    db = _NoCommandDatabase()
    service = TerminalService(SimpleNamespace(db=db), ("https://studio.test",))
    authenticated = SimpleNamespace(
        principal=Principal(TENANT, "requester"),
        expires_at=2_000_000_000,
    )

    with pytest.raises(DomainError) as denied:
        service.issue(
            authenticated,
            "wsp_0123456789ABCDEFGHJKMNPQRS",
            {"commandId": "11111111-1111-4111-8111-111111111111"},
            "https://studio.test",
        )

    assert denied.value.code == "AUTH-0070"
    assert denied.value.status == 403
    response = problem(denied.value, "a" * 32)
    body = json.loads(response.body)
    assert response.status_code == 403
    assert response.media_type == "application/problem+json"
    assert body["code"] == "AUTH-0070" and body["status"] == 403
    assert "ticket" not in body
    assert "11111111-1111-4111-8111-111111111111" not in response.body.decode()
    assert len(db.connection.statements) == 1
    query, params = db.connection.statements[0]
    assert "SELECT c.*,d.envelope,a.requester_id" in query
    assert params == ("11111111-1111-4111-8111-111111111111",)
    assert all(
        "INSERT INTO inv.terminal_tickets" not in sql
        for sql, _ in db.connection.statements
    )
