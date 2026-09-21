"""The first-contact grant has one tenant, one install, one scope and one end."""

from __future__ import annotations

from datetime import datetime, timedelta, timezone
import io
import uuid

import pytest

from saintvision.errors import InvError
from saintvision.identity.discovery_credentials import (
    DISCOVERY_SCOPE,
    TOKEN_TTL,
    token_sha256,
    validate_discovery_grant,
)
from tools import discovery_credential

NOW = datetime(2026, 9, 21, 12, tzinfo=timezone.utc)
TENANT = uuid.UUID("7c8c0e56-5237-4bb3-965e-8571d4c443a1")
INSTALLATION = "node-install-01"
TOKEN = "dsc1_" + "A" * 43


def _grant(**changes):
    value = {
        "token_sha256": token_sha256(TOKEN),
        "tenant_id": TENANT,
        "installation_id": INSTALLATION,
        "scope": DISCOVERY_SCOPE,
        "revoked_at": None,
        "expires_at": NOW + TOKEN_TTL,
        "last_announcement_at": None,
    }
    value.update(changes)
    return value


@pytest.mark.parametrize(
    ("changes", "tenant", "installation", "now", "reason"),
    [
        ({}, str(uuid.uuid4()), INSTALLATION, NOW, "tenant_mismatch"),
        ({}, str(TENANT), "other-installation", NOW, "installation_mismatch"),
        ({"expires_at": NOW}, str(TENANT), INSTALLATION, NOW, "expired"),
        ({"revoked_at": NOW}, str(TENANT), INSTALLATION, NOW, "revoked"),
        ({"scope": "nodes:enroll"}, str(TENANT), INSTALLATION, NOW, "scope_mismatch"),
    ],
)
def test_cross_scope_expiry_and_revocation_are_the_same_public_denial(
    changes, tenant, installation, now, reason
):
    with pytest.raises(InvError) as caught:
        validate_discovery_grant(
            _grant(**changes),
            token=TOKEN,
            asserted_tenant=tenant,
            installation_id=installation,
            now=now,
        )
    assert caught.value.status == 403
    assert caught.value.message == "discovery credential is not valid"
    assert getattr(caught.value, "reason_code", None) == reason
    assert TOKEN not in str(caught.value)


def test_a_matching_grant_is_usable_only_after_refresh_interval():
    row = _grant(last_announcement_at=NOW - timedelta(seconds=30))
    assert validate_discovery_grant(
        row,
        token=TOKEN,
        asserted_tenant=str(TENANT),
        installation_id=INSTALLATION,
        now=NOW,
    ) is row

    row["last_announcement_at"] = NOW - timedelta(seconds=29)
    with pytest.raises(InvError) as caught:
        validate_discovery_grant(
            row,
            token=TOKEN,
            asserted_tenant=str(TENANT),
            installation_id=INSTALLATION,
            now=NOW,
        )
    assert getattr(caught.value, "reason_code", None) == "refresh_too_soon"


def test_cli_refuses_non_operator_before_writing_or_revealing(monkeypatch):
    class Tty(io.StringIO):
        def isatty(self):
            return True

    class Connection:
        def __init__(self):
            self.calls = []

        def __enter__(self):
            return self

        def __exit__(self, *_):
            return False

        def transaction(self):
            return self

        def execute(self, sql, params=None):
            self.calls.append((sql, params))
            return self

        def fetchone(self):
            return {"actor": "ordinary_login", "allowed": False}

        def fetchall(self):
            return []

    connection = Connection()
    output, error = Tty(), io.StringIO()
    result = discovery_credential.run(
        ["issue", "--tenant", str(TENANT), "--installation", INSTALLATION, "--apply"],
        environ={discovery_credential.ISSUER_DSN_ENV: "synthetic-dsn"},
        connect=lambda _dsn: connection,
        output=output,
        error=error,
    )
    assert result == discovery_credential.EXIT_REFUSED
    assert "not an authorized discovery issuer" in error.getvalue()
    assert "dsc1_" not in output.getvalue()
    assert len(connection.calls) == 1


def test_cli_issue_stores_only_digest_and_reveals_secret_once_after_commit(monkeypatch):
    class Tty(io.StringIO):
        def isatty(self):
            return True

    class Connection:
        def __init__(self):
            self.calls = []
            self.committed = False

        def __enter__(self):
            return self

        def __exit__(self, *_):
            self.committed = True
            return False

        def transaction(self):
            return self

        def execute(self, sql, params=None):
            self.calls.append((sql, params))
            return self

        def fetchone(self):
            if "pg_has_role" in self.calls[-1][0]:
                return {"actor": "operator_login", "allowed": True}
            return {"exists": 1}

        def fetchall(self):
            return []

    connection = Connection()
    output, error = Tty(), io.StringIO()
    result = discovery_credential.run(
        ["issue", "--tenant", str(TENANT), "--installation", INSTALLATION, "--apply"],
        environ={discovery_credential.ISSUER_DSN_ENV: "synthetic-dsn"},
        connect=lambda _dsn: connection,
        output=output,
        error=error,
    )
    assert result == discovery_credential.EXIT_OK
    assert connection.committed
    token_lines = [line for line in output.getvalue().splitlines() if line.startswith("dsc1_")]
    assert len(token_lines) == 1
    token = token_lines[0]
    assert token.count("dsc1_") == 1
    assert error.getvalue() == ""
    query_params = [params for _sql, params in connection.calls if params is not None]
    assert all(token not in repr(params) for params in query_params)
    assert any(token_sha256(token) in repr(params) for params in query_params)
    assert all(token not in sql for sql, _params in connection.calls)


def test_cli_does_not_write_if_one_time_secret_would_be_redirected():
    connected = []
    output, error = io.StringIO(), io.StringIO()
    result = discovery_credential.run(
        ["issue", "--tenant", str(TENANT), "--installation", INSTALLATION, "--apply"],
        environ={discovery_credential.ISSUER_DSN_ENV: "synthetic-dsn"},
        connect=lambda _dsn: connected.append(True),
        output=output,
        error=error,
    )
    assert result == discovery_credential.EXIT_REFUSED
    assert connected == []
    assert "interactive terminal" in error.getvalue()
    assert "dsc1_" not in output.getvalue()
