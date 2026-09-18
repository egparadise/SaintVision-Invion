"""Transport failure is final; revocation is checked again in the write transaction."""

import hashlib
import pytest
from sqlalchemy import text
from sqlalchemy.exc import DBAPIError

from saintvision.db.session import tenant_scope
from saintvision.errors import InvError
from saintvision.identity import node_auth
from saintvision.api.v1 import nodes as routes
from test_node_auth import nodes, FINGERPRINT, _auth
from test_api import client, seeded


@pytest.mark.parametrize("error", ["expired certificate", "unknown CA", "", False, 0])
def test_tls_error_is_terminal_even_with_trusted_proxy(error, monkeypatch):
    monkeypatch.setenv(node_auth.TRUSTED_PROXY_ENV, "10.9.9.9/32")
    calls = []
    monkeypatch.setattr(node_auth, "resolve_node", lambda *a, **kw: calls.append(kw))
    with pytest.raises(InvError) as caught:
        node_auth.authenticate_node(
            None,
            scope={
                "extensions": {
                    "tls": {"client_cert_chain": [b"certificate"], "client_cert_error": error}
                }
            },
            headers={node_auth.PROXY_FINGERPRINT_HEADER: FINGERPRINT},
            peer_address="10.9.9.9",
        )
    assert caught.value.code == "AUTH-INVALID-CREDENTIAL" and calls == []
    assert "expired certificate" not in str(caught.value.to_problem(trace_id="1" * 32))


@pytest.mark.parametrize("chain", [[None], [b""], ["bad pem!"], "cert", b"cert", 123, None])
def test_malformed_direct_chain_cannot_fall_back(chain, monkeypatch):
    monkeypatch.setenv(node_auth.TRUSTED_PROXY_ENV, "10.9.9.9/32")
    with pytest.raises(InvError):
        node_auth.authenticate_node(
            None,
            scope={"extensions": {"tls": {"client_cert_chain": chain}}},
            headers={node_auth.PROXY_FINGERPRINT_HEADER: FINGERPRINT},
            peer_address="10.9.9.9",
        )


def test_asgi_iterable_certificate_chain_is_supported():
    scope = {
        "extensions": {
            "tls": {
                "client_cert_chain": iter([b"transport-verified-der"]),
                "client_cert_error": None,
            }
        }
    }
    assert (
        node_auth.fingerprint_from_scope(scope)
        == hashlib.sha256(b"transport-verified-der").hexdigest()
    )


def test_failed_transport_cannot_resolve_even_an_enrolled_fingerprint(app_sessionmaker, nodes):
    der = b"enrolled-but-expired-test-certificate"
    fingerprint = hashlib.sha256(der).hexdigest()
    with app_sessionmaker() as s, s.begin(), tenant_scope(s, nodes["tenant_a"]):
        s.execute(
            text("UPDATE nodes SET certificate_fingerprint=:f WHERE node_id=:n"),
            {"f": fingerprint, "n": nodes["node_a"]},
        )
        with pytest.raises(InvError):
            node_auth.authenticate_node(
                s,
                scope={
                    "extensions": {
                        "tls": {"client_cert_chain": [der], "client_cert_error": "expired"}
                    }
                },
                headers={},
                peer_address=None,
            )


@pytest.mark.parametrize("change", ["retired", "rotated", "cleared"])
def test_api_rechecks_binding_after_authentication_before_heartbeat(
    client, nodes, owner_engine, monkeypatch, change
):
    original = routes.authenticate_node

    def authenticate_then_revoke(*a, **kw):
        principal = original(*a, **kw)
        sql = {
            "retired": "UPDATE nodes SET status='retired' WHERE node_id=:n",
            "rotated": "UPDATE nodes SET certificate_fingerprint=:f WHERE node_id=:n",
            "cleared": "UPDATE nodes SET certificate_fingerprint=NULL WHERE node_id=:n",
        }[change]
        with owner_engine.begin() as c:
            c.execute(text(sql), {"n": nodes["node_a"], "f": "d" * 64})
        return principal

    monkeypatch.setattr(routes, "authenticate_node", authenticate_then_revoke)
    response = client.post(
        f"/v1/nodes/{nodes['node_a']}/heartbeats",
        json={"sequence": 1},
        headers={node_auth.PROXY_FINGERPRINT_HEADER: FINGERPRINT},
    )
    assert response.status_code == 403
    assert response.json()["code"] == "AUTH-INVALID-CREDENTIAL"
    with owner_engine.connect() as c:
        assert (
            c.scalar(
                text("SELECT heartbeat_sequence FROM nodes WHERE node_id=:n"),
                {"n": nodes["node_a"]},
            )
            == 0
        )


def test_guard_holds_binding_until_transaction_end(
    app_sessionmaker, owner_engine, nodes, monkeypatch
):
    with app_sessionmaker() as s, s.begin(), tenant_scope(s, nodes["tenant_a"]):
        principal = _auth(s, fingerprint=FINGERPRINT, monkeypatch=monkeypatch)
        principal.lock_current(s)
        with pytest.raises(DBAPIError):
            with owner_engine.begin() as c:
                c.execute(text("SET LOCAL lock_timeout='20ms'"))
                c.execute(
                    text("UPDATE nodes SET status='retired' WHERE node_id=:n"),
                    {"n": nodes["node_a"]},
                )
    with owner_engine.begin() as c:
        c.execute(
            text("UPDATE nodes SET status='retired' WHERE node_id=:n"), {"n": nodes["node_a"]}
        )
    with app_sessionmaker() as s, s.begin(), tenant_scope(s, nodes["tenant_a"]):
        with pytest.raises(InvError):
            principal.lock_current(s)


def test_binding_guard_cannot_cross_tenant_scope(app_sessionmaker, nodes, monkeypatch):
    with app_sessionmaker() as s, s.begin(), tenant_scope(s, nodes["tenant_a"]):
        principal = _auth(s, fingerprint=FINGERPRINT, monkeypatch=monkeypatch)
    with app_sessionmaker() as s, s.begin(), tenant_scope(s, nodes["tenant_b"]):
        with pytest.raises(InvError):
            principal.lock_current(s)
