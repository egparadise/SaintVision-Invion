"""Bind the PTY ticket response to the canonical wire contract and shared fixture."""

import json
from pathlib import Path

import pytest

from inv.contracts import validate_contract
from inv.errors import DomainError

ROOT = Path(__file__).resolve().parents[2]
FIXTURE = ROOT / "contracts" / "fixtures" / "terminal-ticket-result.json"
INPUT_FIXTURE = ROOT / "contracts" / "fixtures" / "terminal-ticket-input.json"


def _fixture() -> dict:
    return json.loads(FIXTURE.read_text(encoding="utf-8"))


def test_shared_terminal_ticket_response_fixture_matches_kernel_contract():
    validate_contract("TerminalTicketResult", _fixture())


def test_shared_terminal_ticket_request_fixture_matches_kernel_contract():
    request = json.loads(INPUT_FIXTURE.read_text(encoding="utf-8"))
    validate_contract("TerminalTicketInput", request)
    with pytest.raises(DomainError, match="VAL-0002"):
        validate_contract("TerminalTicketInput", {})


def test_every_terminal_ticket_response_field_is_load_bearing():
    value = _fixture()
    for field in list(value):
        broken = {key: item for key, item in value.items() if key != field}
        with pytest.raises(DomainError, match="VAL-0002"):
            validate_contract("TerminalTicketResult", broken)


@pytest.mark.parametrize(
    "field,value",
    [
        ("ticket", "not-a-ticket"),
        ("expiresAt", "not-a-date"),
        ("sessionId", "not-a-uuid"),
        ("websocketPath", "wss://attacker.invalid/socket"),
    ],
)
def test_terminal_ticket_rejects_invalid_security_boundary_fields(field, value):
    body = _fixture()
    body[field] = value
    with pytest.raises(DomainError, match="VAL-0002"):
        validate_contract("TerminalTicketResult", body)


def test_terminal_ticket_response_rejects_frontend_aliases_and_extra_fields():
    body = _fixture()
    body["ticketId"] = body.pop("ticket")
    body["ptyWsUrl"] = body.pop("websocketPath")
    with pytest.raises(DomainError, match="VAL-0002"):
        validate_contract("TerminalTicketResult", body)


def test_ticket_first_websocket_frame_matches_kernel_auth_contract():
    validate_contract("TerminalTicketAuthFrame", {"ticket": _fixture()["ticket"]})


def test_ticket_auth_frame_rejects_extra_properties_and_malformed_ticket():
    with pytest.raises(DomainError, match="VAL-0002"):
        validate_contract("TerminalTicketAuthFrame", {"ticket": "not-a-ticket"})
    with pytest.raises(DomainError, match="VAL-0002"):
        validate_contract("TerminalTicketAuthFrame", {"ticket": _fixture()["ticket"], "workspaceId": "wsp_ignored"})
