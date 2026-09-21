"""The operator-issued discovery grant is tested through PostgreSQL and HTTP."""

from __future__ import annotations

from datetime import datetime, timedelta, timezone
import io
import os
import re
import secrets
from uuid import uuid4

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import text
from sqlalchemy.engine import make_url

from saintvision.api.app import create_app
from saintvision.config import Settings
from saintvision.db.session import tenant_scope
from saintvision.identity.discovery_credentials import token_sha256
from saintvision.identity.principal import StaticPrincipalVerifier
from saintvision.ids import new_id
from saintvision.services import discovery as discovery_service
from saintvision.services.discovery_credentials import issue

pytestmark = pytest.mark.postgres
NOW = datetime(2026, 9, 21, 12, tzinfo=timezone.utc)


class Tty(io.StringIO):
    def isatty(self):
        return True


def _require_secret_absent(secret, text_value, message):
    if secret in text_value:
        pytest.fail(message, pytrace=False)


def _api(app_engine, now):
    return create_app(
        engine=app_engine,
        settings=Settings(database_url="test-only"),
        verifier=StaticPrincipalVerifier({}, allow_outside_dev=True),
        clock=lambda: now[0],
        check_partitions_on_startup=False,
    )


def _announce(client, tenant, installation, token):
    return client.post(
        "/v1/discovery/announcements",
        headers={
            "Authorization": f"Bearer {token}",
            "X-Inv-Tenant": str(tenant),
        },
        json={
            "instanceId": installation,
            "hostname": "claimed-host",
            "osType": "linux",
            "osVersion": "test-os",
            "agentVersion": "test-agent",
            "cpuCores": 8,
            "ramBytes": 4096,
            "gpuCount": 0,
        },
    )


def _issue_owner(owner_engine, tenant, installation, now=NOW):
    secret = "dsc1_" + secrets.token_urlsafe(32)
    from sqlalchemy.orm import Session

    with Session(owner_engine) as session, session.begin():
        grant = issue(
            session,
            tenant_id=tenant,
            installation_id=installation,
            actor="synthetic-test-issuer",
            secret=secret,
            now=now,
        )
        return secret, grant.credential_id


def test_cli_credential_is_digest_only_and_works_from_issue_to_admission(
    owner_engine, app_engine, app_sessionmaker, database_url, two_tenants, caplog
):
    from tools import discovery_credential

    tenant_a, _tenant_b = two_tenants
    installation = "e2e-node-" + uuid4().hex[:10]
    operator = "dcr_op_" + uuid4().hex[:20]
    operator_password = secrets.token_hex(32)
    with owner_engine.begin() as connection:
        connection.exec_driver_sql(
            f'CREATE ROLE "{operator}" LOGIN NOSUPERUSER NOBYPASSRLS '
            f"NOCREATEDB NOCREATEROLE NOREPLICATION NOINHERIT PASSWORD '{operator_password}'"
        )
        connection.exec_driver_sql(f'GRANT inv_discovery_issuer TO "{operator}"')
    operator_dsn = make_url(database_url).set(
        drivername="postgresql",
        username=operator, password=operator_password
    ).render_as_string(hide_password=False)
    environment = {discovery_credential.ISSUER_DSN_ENV: operator_dsn}
    check_out, check_err = io.StringIO(), io.StringIO()
    try:
        assert discovery_credential.run(
            ["issue", "--tenant", str(tenant_a), "--installation", installation],
            environ=environment,
            output=check_out,
            error=check_err,
        ) == discovery_credential.EXIT_OK, check_err.getvalue()
        assert "no credential written" in check_out.getvalue()
        assert "dsc1_" not in check_out.getvalue()

        output, error = Tty(), io.StringIO()
        assert discovery_credential.run(
            ["issue", "--tenant", str(tenant_a), "--installation", installation, "--apply"],
            environ=environment,
            output=output,
            error=error,
        ) == discovery_credential.EXIT_OK
        if error.getvalue():
            pytest.fail("successful issue must not write diagnostics", pytrace=False)
        token_lines = [line for line in output.getvalue().splitlines() if line.startswith("dsc1_")]
        if len(token_lines) != 1:
            pytest.fail("issuer CLI must reveal exactly one bearer after commit", pytrace=False)
        token = token_lines[0]
        credential_id = re.search(r"credentialId=(dcr_[0-9A-HJKMNP-TV-Z]{26})", output.getvalue())[1]

        with owner_engine.connect() as connection:
            row = connection.execute(
                text(
                    "SELECT token_sha256, issued_at, expires_at, revoked_at FROM discovery_machine_credentials "
                    "WHERE credential_id=:id"
                ),
                {"id": credential_id},
            ).mappings().one()
        if row["token_sha256"] != token_sha256(token):
            pytest.fail("database must contain only the matching bearer digest", pytrace=False)
        assert row["expires_at"] - row["issued_at"] == timedelta(minutes=15)
        _require_secret_absent(token, repr(dict(row)), "raw bearer was stored in the credential row")

        now = [datetime.now(timezone.utc)]
        app = _api(app_engine, now)
        with TestClient(app, raise_server_exceptions=False, client=("10.2.0.17", 51000)) as client:
            list_response = client.get(
                "/v1/discovery/candidates",
                headers={
                    "Authorization": f"Bearer {token}",
                    "X-Inv-Tenant": str(tenant_a),
                },
            )
            assert list_response.status_code == 403
            assert list_response.json()["code"] == "AUTH-INVALID-CREDENTIAL"
            response = _announce(client, tenant_a, installation, token)
            assert response.status_code == 202, response.text
            _require_secret_absent(token, caplog.text, "discovery bearer appeared in application logs")
            with owner_engine.connect() as connection:
                announcement_id = connection.execute(
                    text(
                        "SELECT announcement_id FROM node_announcements "
                        "WHERE tenant_id=:tenant AND instance_id=:instance"
                    ),
                    {"tenant": tenant_a, "instance": installation},
                ).scalar_one()
            candidate = {"announcementId": announcement_id}
            now[0] += timedelta(seconds=30)
            linked = _announce(client, tenant_a, installation, token)
            assert linked.status_code == 202, linked.text
            assert linked.json()["state"] == "candidate"

        with app_sessionmaker() as session, session.begin():
            with tenant_scope(session, tenant_a):
                bootstrap = discovery_service.admit_candidate(
                    session,
                    tenant_id=tenant_a,
                    announcement_id=candidate.get("announcementId", ""),
                    admitted_by_user_id=new_id("user"),
                    now=now[0],
                )
                assert bootstrap.secret
                active = session.execute(
                    text(
                        "SELECT count(*) FROM discovery_machine_credentials "
                        "WHERE credential_id=:id AND revoked_at IS NULL"
                    ),
                    {"id": credential_id},
                ).scalar_one()
                assert active == 0

        revoke_out, revoke_err = io.StringIO(), io.StringIO()
        assert discovery_credential.run(
            ["revoke", "--tenant", str(tenant_a), "--credential-id", credential_id, "--apply"],
            environ=environment,
            output=revoke_out,
            error=revoke_err,
        ) == discovery_credential.EXIT_OK
        # Admission already revoked the grant; CLI revocation is idempotent.
        assert revoke_out.getvalue() == "ALREADY REVOKED\n"

        explicit_installation = installation + "-second"
        explicit_output = Tty()
        assert discovery_credential.run(
            ["issue", "--tenant", str(tenant_a), "--installation", explicit_installation, "--apply"],
            environ=environment,
            output=explicit_output,
            error=io.StringIO(),
        ) == discovery_credential.EXIT_OK
        explicit_token = next(
            line for line in explicit_output.getvalue().splitlines() if line.startswith("dsc1_")
        )
        explicit_id = re.search(
            r"credentialId=(dcr_[0-9A-HJKMNP-TV-Z]{26})", explicit_output.getvalue()
        )[1]
        with TestClient(app, raise_server_exceptions=False, client=("10.2.0.19", 51002)) as client:
            announced = _announce(client, tenant_a, explicit_installation, explicit_token)
            assert announced.status_code == 202, announced.text
            revoked_out, revoked_err = io.StringIO(), io.StringIO()
            assert discovery_credential.run(
                ["revoke", "--tenant", str(tenant_a), "--credential-id", explicit_id, "--apply"],
                environ=environment,
                output=revoked_out,
                error=revoked_err,
            ) == discovery_credential.EXIT_OK
            assert revoked_out.getvalue() == "REVOKED\n"
            now[0] += timedelta(seconds=30)
            denied_after_revoke = _announce(
                client, tenant_a, explicit_installation, explicit_token
            )
            assert denied_after_revoke.status_code == 403
            assert denied_after_revoke.json()["code"] == "AUTH-INVALID-CREDENTIAL"
        # The issue command's captured output is the one authorized reveal.
        # Assert the bearer is absent from every diagnostic and later command,
        # without printing the captured secret if a regression fails.
        if output.getvalue().count(token) != 1:
            pytest.fail("issuer CLI must reveal the bearer exactly once", pytrace=False)
        _require_secret_absent(token,
            error.getvalue()
            + check_out.getvalue()
            + check_err.getvalue()
            + revoke_out.getvalue()
            + revoke_err.getvalue(),
            "bearer appeared in CLI diagnostics or follow-up output",
        )
        if explicit_output.getvalue().count(explicit_token) != 1:
            pytest.fail("issuer CLI must reveal the replacement bearer exactly once", pytrace=False)
        _require_secret_absent(
            explicit_token,
            revoked_out.getvalue() + revoked_err.getvalue(),
            "replacement bearer appeared in revoke output",
        )
    finally:
        with owner_engine.begin() as connection:
            connection.exec_driver_sql(f'REVOKE inv_discovery_issuer FROM "{operator}"')
            connection.exec_driver_sql(f'DROP ROLE "{operator}"')


def test_wrong_tenant_install_expiry_and_revocation_do_not_create_candidates(
    owner_engine, app_engine, two_tenants
):
    tenant_a, tenant_b = two_tenants
    cases = [
        ("cross-tenant", tenant_a, tenant_b, None, False),
        ("wrong-install", tenant_a, tenant_a, "different-install", False),
        ("expired", tenant_a, tenant_a, None, True),
        ("revoked", tenant_a, tenant_a, None, False),
    ]
    now = [NOW]
    app = _api(app_engine, now)
    with TestClient(app, raise_server_exceptions=False, client=("10.2.0.18", 51001)) as client:
        for case, grant_tenant, asserted_tenant, supplied_installation, expire in cases:
            installation = f"node-{case}-{uuid4().hex[:8]}"
            token, credential_id = _issue_owner(
                owner_engine, grant_tenant, installation, NOW
            )
            with owner_engine.begin() as connection:
                if expire:
                    connection.execute(
                        text(
                            "UPDATE discovery_machine_credentials "
                            "SET issued_at=:issued, expires_at=:past WHERE credential_id=:id"
                        ),
                        {
                            "issued": NOW - timedelta(minutes=16),
                            "past": NOW - timedelta(seconds=1),
                            "id": credential_id,
                        },
                    )
                if case == "revoked":
                    connection.execute(
                        text("UPDATE discovery_machine_credentials SET revoked_at=:now WHERE credential_id=:id"),
                        {"now": NOW, "id": credential_id},
                    )
            response = _announce(
                client,
                asserted_tenant,
                supplied_installation or installation,
                token,
            )
            assert response.status_code == 403, f"{case}: {response.status_code} {response.text}"
            assert response.json()["code"] == "AUTH-INVALID-CREDENTIAL"
            with owner_engine.connect() as connection:
                count = connection.execute(
                    text(
                        "SELECT count(*) FROM node_announcements "
                        "WHERE tenant_id=:tenant AND instance_id=:instance"
                    ),
                    {"tenant": grant_tenant, "instance": installation},
                ).scalar_one()
            assert count == 0, case


def test_cli_requires_explicit_database_issuer_membership(
    owner_engine, database_url, two_tenants
):
    from tools import discovery_credential

    tenant, _ = two_tenants
    installation = "unauthorized-" + uuid4().hex[:12]
    login = "dcr_noissuer_" + uuid4().hex[:16]
    password = secrets.token_hex(32)
    with owner_engine.begin() as connection:
        connection.exec_driver_sql(
            f'CREATE ROLE "{login}" LOGIN NOSUPERUSER NOBYPASSRLS '
            f"NOCREATEDB NOCREATEROLE NOREPLICATION NOINHERIT PASSWORD '{password}'"
        )
    dsn = make_url(database_url).set(
        drivername="postgresql", username=login, password=password
    ).render_as_string(hide_password=False)
    output, error = Tty(), io.StringIO()
    try:
        result = discovery_credential.run(
            ["issue", "--tenant", str(tenant), "--installation", installation, "--apply"],
            environ={discovery_credential.ISSUER_DSN_ENV: dsn},
            output=output,
            error=error,
        )
        assert result == discovery_credential.EXIT_REFUSED
        if "not an authorized discovery issuer" not in error.getvalue():
            pytest.fail("unprivileged database login was not refused", pytrace=False)
        _require_secret_absent("dsc1_", output.getvalue(), "unprivileged login received a bearer")
        with owner_engine.connect() as connection:
            count = connection.execute(
                text(
                    "SELECT count(*) FROM discovery_machine_credentials "
                    "WHERE tenant_id=:tenant AND installation_id=:installation"
                ),
                {"tenant": tenant, "installation": installation},
            ).scalar_one()
        assert count == 0
    finally:
        with owner_engine.begin() as connection:
            connection.exec_driver_sql(f'DROP ROLE "{login}"')


def test_discovery_issuer_budget_blocks_cli_and_direct_sql_beyond_ten_per_tenant(
    owner_engine, database_url, two_tenants
):
    import psycopg

    from tools import discovery_credential
    from saintvision.services.discovery_credentials import new_secret

    tenant, _ = two_tenants
    login = "dcr_budget_" + uuid4().hex[:16]
    password = secrets.token_hex(32)
    with owner_engine.begin() as connection:
        connection.exec_driver_sql(
            f'CREATE ROLE "{login}" LOGIN NOSUPERUSER NOBYPASSRLS '
            f"NOCREATEDB NOCREATEROLE NOREPLICATION NOINHERIT PASSWORD '{password}'"
        )
        connection.exec_driver_sql(f'GRANT inv_discovery_issuer TO "{login}"')
    dsn = make_url(database_url).set(
        drivername="postgresql", username=login, password=password
    ).render_as_string(hide_password=False)
    environment = {discovery_credential.ISSUER_DSN_ENV: dsn}
    try:
        for index in range(10):
            output, error = Tty(), io.StringIO()
            result = discovery_credential.run(
                [
                    "issue", "--tenant", str(tenant),
                    "--installation", f"budget-install-{index}", "--apply",
                ],
                environ=environment,
                output=output,
                error=error,
            )
            if result != discovery_credential.EXIT_OK:
                pytest.fail("issuer budget rejected an issuance below its limit", pytrace=False)
            if error.getvalue():
                pytest.fail("successful issuance wrote diagnostics", pytrace=False)
            if len([line for line in output.getvalue().splitlines() if line.startswith("dsc1_")]) != 1:
                pytest.fail("successful issuance must reveal one bearer", pytrace=False)

        blocked_output, blocked_error = Tty(), io.StringIO()
        blocked = discovery_credential.run(
            ["issue", "--tenant", str(tenant), "--installation", "budget-overflow", "--apply"],
            environ=environment,
            output=blocked_output,
            error=blocked_error,
        )
        if blocked != discovery_credential.EXIT_REFUSED:
            pytest.fail("CLI must refuse the 11th tenant issuance", pytrace=False)
        if blocked_error.getvalue() != (
            "REFUSED tenant discovery issuance limit reached (10 per rolling 24 hours)\n"
        ):
            pytest.fail("quota refusal must report only its stable non-secret reason", pytrace=False)
        _require_secret_absent("dsc1_", blocked_output.getvalue(), "quota refusal revealed a bearer")

        # The DB trigger must also stop an issuer-role SQL client that bypasses
        # the CLI, and leave both the credential and audit count at the limit.
        raw_token = new_secret()
        try:
            with psycopg.connect(dsn) as connection:
                connection.execute("SET ROLE inv_discovery_issuer")
                connection.execute(
                    "INSERT INTO discovery_machine_credentials "
                    "(credential_id, tenant_id, installation_id, scope, token_sha256, issued_by, "
                    "issued_at, expires_at) VALUES (%s,%s,%s,%s,%s,%s,%s,%s)",
                    (
                        new_id("discovery_credential"), tenant, "direct-sql-overflow",
                        "discovery:announce", token_sha256(raw_token), login,
                        datetime.now(timezone.utc), datetime.now(timezone.utc) + timedelta(minutes=15),
                    ),
                )
        except psycopg.Error as exc:
            if exc.sqlstate != "P0001":
                pytest.fail("direct SQL was not rejected by the quota trigger", pytrace=False)
        else:
            pytest.fail("direct SQL bypassed the tenant issuance budget", pytrace=False)
        _require_secret_absent(raw_token, blocked_error.getvalue(), "raw test bearer appeared in diagnostics")

        with owner_engine.connect() as connection:
            issued_count = connection.execute(
                text(
                    "SELECT count(*) FROM discovery_machine_credentials "
                    "WHERE tenant_id=:tenant AND issued_by=:actor"
                ),
                {"tenant": tenant, "actor": login},
            ).scalar_one()
            event_count = connection.execute(
                text(
                    "SELECT count(*) FROM discovery_credential_events "
                    "WHERE tenant_id=:tenant AND actor=:actor AND event_type='issued'"
                ),
                {"tenant": tenant, "actor": login},
            ).scalar_one()
            budget_count = connection.execute(
                text("SELECT cardinality(issue_timestamps) FROM discovery_credential_issue_budgets WHERE tenant_id=:tenant"),
                {"tenant": tenant},
            ).scalar_one()
        assert issued_count == event_count == budget_count == 10
    finally:
        with owner_engine.begin() as connection:
            connection.exec_driver_sql(f'REVOKE inv_discovery_issuer FROM "{login}"')
            connection.exec_driver_sql(f'DROP ROLE "{login}"')
