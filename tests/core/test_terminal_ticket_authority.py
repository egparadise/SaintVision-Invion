"""A syntactically valid command ID alone must never authorize a PTY ticket."""

from contextlib import contextmanager
from datetime import datetime, timezone
import json
from types import SimpleNamespace

import pytest

from inv.approvals import Principal
from inv.app import problem
from inv.errors import DomainError
from inv.terminal import TerminalService
import inv.terminal as terminal_module

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


def test_terminal_ticket_serving_path_rejects_invalid_issued_ticket(monkeypatch):
    """The contract validator is load-bearing on the actual ticket issue path."""

    class Connection:
        def __init__(self):
            self.statements = []

        def execute(self, statement, params=()):
            self.statements.append((statement, params))

    class Database:
        recovery_epoch = "00000000-0000-4000-8000-000000000001"

        def __init__(self):
            self.connection = Connection()

        @contextmanager
        def transaction(self, _tenant_id):
            yield self.connection

    db = Database()
    service = TerminalService(SimpleNamespace(db=db), ("https://studio.test",))
    authenticated = SimpleNamespace(
        principal=Principal(TENANT, "requester"),
        expires_at=2_000_000_000,
    )
    now = datetime(2026, 9, 21, tzinfo=timezone.utc)
    row = {
        "not_after": datetime(2026, 9, 21, 0, 10, tzinfo=timezone.utc),
        "project_id": "prj_contract",
        "run_id": "run_0123456789ABCDEFGHJKMNPQRS",
        "command_id": "11111111-1111-4111-8111-111111111111",
    }
    launch = {
        "workspaceId": "wsp_0123456789ABCDEFGHJKMNPQRS",
        "terminal": {"sessionId": "00000000-0000-4000-8000-000000000003"},
    }
    monkeypatch.setattr(service, "_current", lambda *_args: (row, launch, now))
    monkeypatch.setattr(terminal_module.secrets, "token_hex", lambda _size: "not-a-ticket")

    with pytest.raises(DomainError, match="VAL-0002"):
        service.issue(
            authenticated,
            launch["workspaceId"],
            {"commandId": row["command_id"]},
            "https://studio.test",
        )

    assert len(db.connection.statements) == 1
    assert "INSERT INTO inv.terminal_tickets" in db.connection.statements[0][0]
