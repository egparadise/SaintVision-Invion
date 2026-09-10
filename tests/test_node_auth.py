"""Inbound node authentication and heartbeat concurrency.

Two defects this file pins shut.

**The heartbeat route had no authentication.** Any caller who knew a node id
could post a beat for it — keeping a decommissioned machine looking alive past
the 60 second detection target, or injecting utilisation figures that steer
placement onto a machine that is actually saturated.

**The sequence guard was a read followed by a write.** Two beats arriving
together both read the old sequence, both concluded they had advanced it, and
both wrote. A replayed sequence 5 could land after a live 7 and run the node's
liveness backwards.
"""

from __future__ import annotations

import datetime as dt
import hashlib
import threading
import uuid

import pytest
from sqlalchemy import text
from sqlalchemy.orm import sessionmaker

from saintvision.db.session import tenant_scope
from saintvision.errors import InvError
from saintvision.identity import node_auth
from saintvision.ids import new_id
from saintvision.services import nodes as node_service

pytestmark = pytest.mark.postgres

UTC = dt.timezone.utc
NOW = dt.datetime(2026, 9, 10, 7, 0, 0, tzinfo=UTC)
FINGERPRINT = "a" * 64
OTHER_FINGERPRINT = "b" * 64


@pytest.fixture
def nodes(owner_engine, two_tenants):
    """Two enrolled nodes with certificates, and one still enrolling."""
    tenant_a, tenant_b = two_tenants
    ids = {"tenant_a": tenant_a, "tenant_b": tenant_b}
    with owner_engine.begin() as c:
        for key, fingerprint, status, host in (
            ("node_a", FINGERPRINT, "active", "lab-a"),
            ("node_b", OTHER_FINGERPRINT, "active", "lab-b"),
            ("node_retired", "c" * 64, "retired", "lab-old"),
            ("node_bare", None, "enrolling", "lab-bare"),
        ):
            node_id = new_id("node")
            ids[key] = node_id
            c.execute(
                text(
                    "INSERT INTO nodes (node_id, tenant_id, hostname, os_type, os_version, "
                    "agent_version, status, certificate_fingerprint, enrolled_at, "
                    "heartbeat_sequence, version) "
                    "VALUES (:n, :t, :h, 'linux', '22.04', '0.1', :s, :f, now(), 0, 1)"
                ),
                {"n": node_id, "t": tenant_a, "h": host, "s": status, "f": fingerprint},
            )
    return ids


def _auth(session, *, fingerprint=None, peer="10.9.9.9", scope=None, allowlist="10.9.9.9/32",
          monkeypatch=None):
    if monkeypatch is not None:
        if allowlist is None:
            monkeypatch.delenv(node_auth.TRUSTED_PROXY_ENV, raising=False)
        else:
            monkeypatch.setenv(node_auth.TRUSTED_PROXY_ENV, allowlist)
    headers = {}
    if fingerprint is not None:
        headers[node_auth.PROXY_FINGERPRINT_HEADER] = fingerprint
    return node_auth.authenticate_node(
        session, scope=scope or {}, headers=headers, peer_address=peer
    )


# --------------------------------------------------------------------------
# The credential must come from the transport
# --------------------------------------------------------------------------


def test_a_forwarded_fingerprint_from_an_unlisted_peer_is_ignored(
    app_sessionmaker, nodes, monkeypatch
):
    """The header is only a credential because a trusted proxy set it.

    From anywhere else it is a string the caller chose, which is exactly the
    forgeable thing the allowlist exists to exclude.
    """
    with app_sessionmaker() as session:
        with session.begin():
            with tenant_scope(session, nodes["tenant_a"]):
                with pytest.raises(InvError) as caught:
                    _auth(session, fingerprint=FINGERPRINT, peer="203.0.113.7",
                          monkeypatch=monkeypatch)
    assert caught.value.code in ("AUTH-MISSING-CREDENTIAL",)


def test_with_no_allowlist_the_proxy_path_is_closed(app_sessionmaker, nodes, monkeypatch):
    """An empty allowlist means closed, not "trust every proxy"."""
    with app_sessionmaker() as session:
        with session.begin():
            with tenant_scope(session, nodes["tenant_a"]):
                with pytest.raises(InvError):
                    _auth(session, fingerprint=FINGERPRINT, allowlist=None,
                          monkeypatch=monkeypatch)


def test_no_certificate_at_all_is_refused(app_sessionmaker, nodes, monkeypatch):
    with app_sessionmaker() as session:
        with session.begin():
            with tenant_scope(session, nodes["tenant_a"]):
                with pytest.raises(InvError) as caught:
                    _auth(session, fingerprint=None, monkeypatch=monkeypatch)
    assert caught.value.code == "AUTH-MISSING-CREDENTIAL"


def test_an_allowlisted_proxy_authenticates_the_node(app_sessionmaker, nodes, monkeypatch):
    with app_sessionmaker() as session:
        with session.begin():
            with tenant_scope(session, nodes["tenant_a"]):
                principal = _auth(session, fingerprint=FINGERPRINT, monkeypatch=monkeypatch)
    assert principal.node_id == nodes["node_a"]
    assert principal.source == "trusted-proxy"
    assert principal.tenant_id == nodes["tenant_a"]


def test_direct_mtls_needs_no_allowlist(app_sessionmaker, nodes, monkeypatch):
    """The scope path involves no third party, so nothing has to be trusted."""
    der = b"pretend-certificate-der"
    scope = {"extensions": {"tls": {"client_cert_chain": [der]}}}
    fingerprint = hashlib.sha256(der).hexdigest()
    with app_sessionmaker() as session:
        with session.begin():
            with tenant_scope(session, nodes["tenant_a"]):
                session.execute(
                    text("UPDATE nodes SET certificate_fingerprint = :f WHERE node_id = :n"),
                    {"f": fingerprint, "n": nodes["node_a"]},
                )
                principal = _auth(session, scope=scope, allowlist=None,
                                  monkeypatch=monkeypatch)
    assert principal.node_id == nodes["node_a"]
    assert principal.source == "mtls"


def test_direct_mtls_beats_a_forwarded_header(app_sessionmaker, nodes, monkeypatch):
    """When both are present the one the caller cannot forge wins."""
    der = b"real-cert"
    fingerprint = hashlib.sha256(der).hexdigest()
    scope = {"extensions": {"tls": {"client_cert_chain": [der]}}}
    with app_sessionmaker() as session:
        with session.begin():
            with tenant_scope(session, nodes["tenant_a"]):
                session.execute(
                    text("UPDATE nodes SET certificate_fingerprint = :f WHERE node_id = :n"),
                    {"f": fingerprint, "n": nodes["node_b"]},
                )
                principal = _auth(
                    session, scope=scope, fingerprint=FINGERPRINT, monkeypatch=monkeypatch
                )
    # The header named node_a; the certificate is node_b's.
    assert principal.node_id == nodes["node_b"]


def test_an_unknown_certificate_is_refused(app_sessionmaker, nodes, monkeypatch):
    with app_sessionmaker() as session:
        with session.begin():
            with tenant_scope(session, nodes["tenant_a"]):
                with pytest.raises(InvError) as caught:
                    _auth(session, fingerprint="9" * 64, monkeypatch=monkeypatch)
    assert caught.value.code == "AUTH-INVALID-CREDENTIAL"


def test_a_retired_nodes_certificate_stops_working(app_sessionmaker, nodes, monkeypatch):
    """Otherwise retirement is a label rather than a revocation."""
    with app_sessionmaker() as session:
        with session.begin():
            with tenant_scope(session, nodes["tenant_a"]):
                with pytest.raises(InvError) as caught:
                    _auth(session, fingerprint="c" * 64, monkeypatch=monkeypatch)
    assert caught.value.code == "AUTH-INVALID-CREDENTIAL"


def test_a_malformed_fingerprint_is_refused(app_sessionmaker, nodes, monkeypatch):
    with app_sessionmaker() as session:
        with session.begin():
            with tenant_scope(session, nodes["tenant_a"]):
                with pytest.raises(InvError):
                    _auth(session, fingerprint="not-a-digest", monkeypatch=monkeypatch)


def test_a_node_may_only_act_as_itself(app_sessionmaker, nodes, monkeypatch):
    with app_sessionmaker() as session:
        with session.begin():
            with tenant_scope(session, nodes["tenant_a"]):
                principal = _auth(session, fingerprint=FINGERPRINT, monkeypatch=monkeypatch)
                principal.require_node(nodes["node_a"])
                with pytest.raises(InvError) as caught:
                    principal.require_node(nodes["node_b"])
    assert caught.value.code == "AUTH-NODE-MISMATCH"


def test_a_typo_in_the_allowlist_does_not_widen_it(monkeypatch):
    """``10.0.0.1/8`` is a mistake, not a request to trust a /8."""
    monkeypatch.setenv(node_auth.TRUSTED_PROXY_ENV, "10.0.0.1/8")
    with pytest.raises(ValueError):
        node_auth.trusted_proxies()


def test_auth_errors_do_not_echo_the_credential(app_sessionmaker, nodes, monkeypatch):
    """A rejected fingerprint must not come back in the response body."""
    with app_sessionmaker() as session:
        with session.begin():
            with tenant_scope(session, nodes["tenant_a"]):
                try:
                    _auth(session, fingerprint="9" * 64, monkeypatch=monkeypatch)
                except InvError as error:
                    problem = error.to_problem(trace_id="0" * 31 + "1")
    assert "9" * 64 not in str(problem)
    assert "detail" not in problem


# --------------------------------------------------------------------------
# Heartbeat concurrency and ordering
# --------------------------------------------------------------------------


def test_a_sequence_that_does_not_advance_is_not_applied(app_sessionmaker, nodes):
    with app_sessionmaker() as session:
        with session.begin():
            with tenant_scope(session, nodes["tenant_a"]):
                first = node_service.record_heartbeat(
                    session, tenant_id=nodes["tenant_a"], node_id=nodes["node_a"],
                    sequence=7, now=NOW,
                )
                replay = node_service.record_heartbeat(
                    session, tenant_id=nodes["tenant_a"], node_id=nodes["node_a"],
                    sequence=7, now=NOW + dt.timedelta(seconds=30),
                )
                backwards = node_service.record_heartbeat(
                    session, tenant_id=nodes["tenant_a"], node_id=nodes["node_a"],
                    sequence=3, now=NOW + dt.timedelta(seconds=60),
                )
    assert first.applied is True
    assert replay.applied is False
    assert backwards.applied is False
    # Liveness never ran backwards.
    assert backwards.node.heartbeat_sequence == 7
    assert first.node.last_heartbeat_at == NOW


def test_a_beat_revives_a_node_that_was_declared_lost(app_sessionmaker, nodes):
    with app_sessionmaker() as session:
        with session.begin():
            with tenant_scope(session, nodes["tenant_a"]):
                session.execute(
                    text("UPDATE nodes SET status = 'lost' WHERE node_id = :n"),
                    {"n": nodes["node_a"]},
                )
                outcome = node_service.record_heartbeat(
                    session, tenant_id=nodes["tenant_a"], node_id=nodes["node_a"],
                    sequence=1, now=NOW,
                )
    assert outcome.applied is True
    assert outcome.node.status == "active"


def test_a_stale_beat_does_not_revive_a_lost_node(app_sessionmaker, nodes):
    """The revival rides on the same statement as the sequence guard, so a beat
    that failed the guard cannot resurrect the node as a side effect."""
    with app_sessionmaker() as session:
        with session.begin():
            with tenant_scope(session, nodes["tenant_a"]):
                node_service.record_heartbeat(
                    session, tenant_id=nodes["tenant_a"], node_id=nodes["node_a"],
                    sequence=9, now=NOW,
                )
                session.execute(
                    text("UPDATE nodes SET status = 'lost' WHERE node_id = :n"),
                    {"n": nodes["node_a"]},
                )
                outcome = node_service.record_heartbeat(
                    session, tenant_id=nodes["tenant_a"], node_id=nodes["node_a"],
                    sequence=4, now=NOW + dt.timedelta(minutes=5),
                )
    assert outcome.applied is False
    assert outcome.node.status == "lost"


def test_only_one_of_two_concurrent_beats_applies(app_engine, nodes):
    """The defect this change exists for.

    Two real connections race the same sequence. With a read-then-write guard
    both would observe the old value and both would report success; with the
    comparison inside the UPDATE exactly one can win.
    """
    factory = sessionmaker(bind=app_engine, expire_on_commit=False)
    barrier = threading.Barrier(2)
    results: list[bool] = []
    errors: list[BaseException] = []
    lock = threading.Lock()

    def beat() -> None:
        try:
            with factory() as session:
                with session.begin():
                    with tenant_scope(session, nodes["tenant_a"]):
                        # Both transactions are open and scoped before either
                        # issues its UPDATE.
                        barrier.wait(timeout=10)
                        outcome = node_service.record_heartbeat(
                            session,
                            tenant_id=nodes["tenant_a"],
                            node_id=nodes["node_a"],
                            sequence=5,
                            now=NOW,
                        )
                        with lock:
                            results.append(outcome.applied)
        except BaseException as exc:  # noqa: BLE001 - reported, not swallowed
            with lock:
                errors.append(exc)

    threads = [threading.Thread(target=beat) for _ in range(2)]
    for thread in threads:
        thread.start()
    for thread in threads:
        thread.join(timeout=30)

    assert not errors, errors
    assert sorted(results) == [False, True], results


def test_concurrent_increasing_beats_leave_the_highest(app_engine, nodes):
    """Whatever the interleaving, the stored sequence is the largest sent."""
    factory = sessionmaker(bind=app_engine, expire_on_commit=False)
    sequences = [3, 9, 5, 7, 2]
    errors: list[BaseException] = []
    lock = threading.Lock()

    def beat(sequence: int) -> None:
        try:
            with factory() as session:
                with session.begin():
                    with tenant_scope(session, nodes["tenant_a"]):
                        node_service.record_heartbeat(
                            session, tenant_id=nodes["tenant_a"],
                            node_id=nodes["node_a"], sequence=sequence, now=NOW,
                        )
        except BaseException as exc:  # noqa: BLE001
            with lock:
                errors.append(exc)

    threads = [threading.Thread(target=beat, args=(s,)) for s in sequences]
    for thread in threads:
        thread.start()
    for thread in threads:
        thread.join(timeout=30)

    assert not errors, errors
    with factory() as session:
        with session.begin():
            with tenant_scope(session, nodes["tenant_a"]):
                stored = session.execute(
                    text("SELECT heartbeat_sequence FROM nodes WHERE node_id = :n"),
                    {"n": nodes["node_a"]},
                ).scalar_one()
    assert stored == max(sequences)


def test_a_beat_for_an_unknown_node_is_not_found(app_sessionmaker, nodes):
    with app_sessionmaker() as session:
        with session.begin():
            with tenant_scope(session, nodes["tenant_a"]):
                with pytest.raises(InvError) as caught:
                    node_service.record_heartbeat(
                        session, tenant_id=nodes["tenant_a"],
                        node_id=new_id("node"), sequence=1, now=NOW,
                    )
    assert caught.value.code == "RES-NODE-NOT-FOUND"


def test_a_beat_cannot_cross_tenants(app_sessionmaker, nodes):
    with app_sessionmaker() as session:
        with session.begin():
            with tenant_scope(session, nodes["tenant_b"]):
                with pytest.raises(InvError) as caught:
                    node_service.record_heartbeat(
                        session, tenant_id=nodes["tenant_b"],
                        node_id=nodes["node_a"], sequence=1, now=NOW,
                    )
    assert caught.value.code == "RES-NODE-NOT-FOUND"
