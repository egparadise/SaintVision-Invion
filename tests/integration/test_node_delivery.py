"""Real PostgreSQL + TLS + Go + Docker. Opt-in isolated CI fixtures only."""

from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timedelta, timezone
import json
import os
import select
import subprocess
import time
from uuid import uuid4
import psycopg
import pytest
from inv.errors import DomainError
from inv.node_channels import NodeChannels, node_uri, provision_channel, revoke_channel
from inv.node_transport import NodeTLSClient, NodeDelivery
from pki_support import authority, issue, credentials
from test_approvals import approval, count
from test_node_runtime import node_runtime, prepare, active, container

pytestmark = pytest.mark.postgres


def policy(a, version, pins, *, expiry=None):
    data = {
        "version": version,
        "tenantId": a.e.tenant,
        "nodeId": a.e.node,
        "recoveryEpoch": a.e.epoch,
        "expiresAt": (
            expiry or datetime.now(timezone.utc) + timedelta(hours=1)
        ).isoformat(),
        "clientFingerprints": pins,
    }
    temporary = a.peer_policy.with_suffix(".tmp")
    temporary.write_text(json.dumps(data), "utf-8")
    temporary.chmod(0o600)
    os.replace(temporary, a.peer_policy)


def start(a):
    process = subprocess.Popen(
        [
            *a.args,
            "--serve",
            "--listen",
            "127.0.0.1:0",
            "--tls-cert",
            str(a.server_files["certificate_file"]),
            "--tls-key",
            str(a.server_files["key_file"]),
            "--client-ca",
            str(a.server_files["ca_file"]),
            "--peer-policy",
            str(a.peer_policy),
        ],
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True,
    )
    ready, _, _ = select.select([process.stdout], [], [], 10)
    if not ready:
        process.kill()
        process.wait(timeout=5)
        pytest.fail("Synthetic Node TLS listener startup timed out")
    line = process.stdout.readline()
    assert line, (
        "Synthetic Node TLS listener rejected configuration: " + process.stderr.read()
    )
    a.endpoint = "https://" + json.loads(line)["listening"]
    a.daemon = process


@pytest.fixture
def remote(node_runtime):
    a = node_runtime
    a.ca = authority()
    a.server_cert = issue(a.ca, node_uri(a.node, a.e.epoch), server=True)
    a.control_uri = (
        f"spiffe://saintvision.ai/tenant/{a.e.tenant}/control-plane/epoch/{a.e.epoch}"
    )
    a.control_cert = issue(a.ca, a.control_uri)
    a.server_files = credentials(a.path, a.ca, a.server_cert, prefix="server")
    a.client_files = credentials(a.path, a.ca, a.control_cert, prefix="control")
    a.peer_policy = a.path / "peer-policy.json"
    policy(a, 1, [a.control_cert.fingerprint])
    start(a)
    with psycopg.connect(a.e.owner) as conn:
        provision_channel(
            conn,
            a.node,
            epoch=a.e.epoch,
            endpoint=a.endpoint,
            certificate_der=a.server_cert.der,
            expected_version=0,
        )
    a.client = NodeTLSClient(**a.client_files)
    a.delivery = NodeDelivery(a.e.db, a.client)
    try:
        yield a
    finally:
        if a.daemon.poll() is None:
            a.daemon.terminate()
            try:
                a.daemon.communicate(timeout=12)
            except subprocess.TimeoutExpired:
                a.daemon.kill()
                a.daemon.communicate(timeout=5)


def stopped(a, timeout=10):
    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline:
        paths = list((a.path / "state").glob("*.receipt"))
        if paths:
            return json.loads(paths[0].read_text("utf-8"))
        time.sleep(0.05)
    pytest.fail("Synthetic Node did not persist physical stop receipt")


def assert_recorded(a, result):
    assert result["receipt"]["stopped"] and active(a) == 0
    assert count(a, "node_stop_receipts") == 1
    assert a.e.runs.get(a.e.tenant, a.run["runId"])["state"] == "scheduled"
    with a.e.db.transaction(a.e.tenant) as conn:
        row = conn.execute(
            "SELECT channel_version,peer_sha256 FROM inv.node_stop_receipts"
        ).fetchone()
        assert (
            row["channel_version"] >= 1
            and row["peer_sha256"] == a.server_cert.fingerprint
        )


def test_mtls_delivery_executes_and_atomically_records_authenticated_stop(remote):
    a = remote
    prepare(a)
    result = a.delivery.deliver(a.node, a.permit)
    assert result["receipt"]["exitCode"] == 0 and not result["duplicate"]
    assert_recorded(a, result)
    duplicate = a.delivery.deliver(a.node, a.permit, observation_only=True)
    assert duplicate["duplicate"] and duplicate["receipt"] == result["receipt"]


def test_observation_cannot_create_even_a_fresh_valid_execution(remote):
    a = remote
    prepare(a)
    with pytest.raises(DomainError):
        a.delivery.deliver(a.node, a.permit, observation_only=True)
    assert (
        not list((a.path / "state").glob("*.intent"))
        and container(a) is None
        and active(a) == 2
    )


def test_dropped_response_restart_and_observation_do_not_restart_work(remote):
    a = remote
    prepare(a)
    channel = NodeChannels(a.e.db).snapshot(a.node)
    lost = a.client.exchange(channel, a.permit)  # Discard before DB receipt commit.
    assert active(a) == 2 and count(a, "node_stop_receipts") == 0
    a.daemon.terminate()
    a.daemon.communicate(timeout=12)
    start(a)
    with psycopg.connect(a.e.owner) as conn:
        provision_channel(
            conn,
            a.node,
            epoch=a.e.epoch,
            endpoint=a.endpoint,
            certificate_der=a.server_cert.der,
            expected_version=1,
        )
    result = a.delivery.deliver(a.node, a.permit, observation_only=True)
    assert result["duplicate"] and result["receipt"] == lost["receipt"]
    assert_recorded(a, result)


def test_network_timeout_cancels_work_but_does_not_release_without_receipt(remote):
    a = remote
    a.workload.update(command=["/probe", "sleep"], timeoutSeconds=10)
    prepare(a)
    delivery = NodeDelivery(a.e.db, NodeTLSClient(**a.client_files, timeout=2))
    with pytest.raises(DomainError, match="NODE-0030"):
        delivery.deliver(a.node, a.permit)
    assert active(a) == 2 and count(a, "node_stop_receipts") == 0
    receipt = stopped(a)
    assert receipt["processStarted"] and receipt["reason"] == "cancelled"
    # Journal persistence precedes releasing the original HTTP execution slot.
    # A receipt request can still be busy: retry observation only, never execute.
    observer = NodeDelivery(a.e.db, NodeTLSClient(**a.client_files, timeout=2))
    for attempt in range(3):
        try:
            result = observer.deliver(a.node, a.permit, observation_only=True)
            break
        except DomainError as exc:
            if exc.code != "NODE-0030" or attempt == 2:
                raise
            assert active(a) == 2 and count(a, "node_stop_receipts") == 0
            time.sleep(0.1 * (attempt + 1))
    assert_recorded(a, result)


@pytest.mark.parametrize(
    "fault",
    ["untrusted-ca", "wrong-uri", "expired-client", "server-eku", "unpinned-client"],
)
def test_mutual_tls_rejects_bad_control_plane_without_execution(remote, fault):
    a = remote
    prepare(a)
    ca = authority() if fault == "untrusted-ca" else a.ca
    cert = issue(
        ca,
        a.control_uri + "/wrong" if fault == "wrong-uri" else a.control_uri,
        server=fault == "server-eku",
        expired=fault == "expired-client",
    )
    if fault != "unpinned-client":
        policy(a, 2, [cert.fingerprint])
    # Client trusts the legitimate Node server CA even when its own certificate is from another CA.
    files = credentials(a.path, a.ca, cert, prefix="bad-client")
    with pytest.raises(DomainError):
        NodeDelivery(a.e.db, NodeTLSClient(**files)).deliver(a.node, a.permit)
    assert not list((a.path / "state").glob("*.intent")) and active(a) == 2


def test_live_client_revocation_stops_then_rotated_peer_observes(remote):
    a = remote
    a.workload.update(command=["/probe", "sleep"], timeoutSeconds=10)
    prepare(a)
    with ThreadPoolExecutor(max_workers=1) as pool:
        call = pool.submit(a.delivery.deliver, a.node, a.permit)
        deadline = time.monotonic() + 8
        while time.monotonic() < deadline:
            c = container(a)
            if c and c["State"]["Running"]:
                break
            time.sleep(0.05)
        else:
            pytest.fail("Synthetic remote execution did not start")
        replacement = issue(a.ca, a.control_uri)
        policy(a, 2, [replacement.fingerprint])
        with pytest.raises(DomainError):
            call.result(timeout=10)
    assert active(a) == 2
    receipt = stopped(a)
    assert receipt["reason"] == "cancelled" and receipt["processStarted"]
    files = credentials(a.path, a.ca, replacement, prefix="replacement")
    result = NodeDelivery(a.e.db, NodeTLSClient(**files)).deliver(
        a.node, a.permit, observation_only=True
    )
    assert_recorded(a, result)


def test_channel_revocation_before_commit_rejects_authentication_race(remote):
    a = remote
    prepare(a)

    class RacingClient:
        def exchange(self, channel, permit, *, observation_only=False):
            result = a.client.exchange(
                channel, permit, observation_only=observation_only
            )
            with psycopg.connect(a.e.owner) as conn:
                revoke_channel(conn, a.node, expected_version=1)
            return result

    with pytest.raises(DomainError, match="NODE-0033"):
        NodeDelivery(a.e.db, RacingClient()).deliver(a.node, a.permit)
    assert active(a) == 2 and count(a, "node_stop_receipts") == 0
    replacement = issue(a.ca, node_uri(a.node, a.e.epoch), server=True)
    # Atomic files; certificate/key mismatch during a rotation fails the handshake.
    for name, data in [
        ("certificate_file", replacement.pem),
        ("key_file", replacement.private),
    ]:
        temporary = a.server_files[name].with_suffix(".tmp")
        temporary.write_bytes(data)
        temporary.chmod(0o600)
        os.replace(temporary, a.server_files[name])
    a.server_cert = replacement
    with psycopg.connect(a.e.owner) as conn:
        provision_channel(
            conn,
            a.node,
            epoch=a.e.epoch,
            endpoint=a.endpoint,
            certificate_der=replacement.der,
            expected_version=2,
        )
    result = a.delivery.deliver(a.node, a.permit, observation_only=True)
    assert_recorded(a, result)


def test_old_policy_cannot_be_restored_after_node_restart(remote):
    a = remote
    prepare(a)
    old = a.peer_policy.read_bytes()
    policy(a, 2, [])
    with pytest.raises(DomainError):
        a.delivery.deliver(a.node, a.permit)
    a.daemon.terminate()
    a.daemon.communicate(timeout=12)
    a.peer_policy.write_bytes(old)
    process = subprocess.run(
        [
            *a.args,
            "--serve",
            "--listen",
            "127.0.0.1:0",
            "--tls-cert",
            str(a.server_files["certificate_file"]),
            "--tls-key",
            str(a.server_files["key_file"]),
            "--client-ca",
            str(a.server_files["ca_file"]),
            "--peer-policy",
            str(a.peer_policy),
        ],
        capture_output=True,
        text=True,
        timeout=10,
    )
    assert process.returncode == 1 and "NODE-0041" in process.stderr
    assert not list((a.path / "state").glob("*.intent")) and active(a) == 2


def test_channel_configuration_is_operator_only_and_tenant_isolated(remote):
    a = remote
    with a.e.db.transaction(a.e.tenant) as conn:
        with pytest.raises(psycopg.errors.InsufficientPrivilege):
            provision_channel(
                conn,
                a.node,
                epoch=a.e.epoch,
                endpoint=a.endpoint,
                certificate_der=a.server_cert.der,
                expected_version=1,
            )
    with a.e.db.transaction(a.e.tenant) as conn:
        with pytest.raises(psycopg.errors.InsufficientPrivilege):
            revoke_channel(conn, a.node, expected_version=1)
    with a.e.db.transaction(a.e.other) as conn:
        assert (
            conn.execute("SELECT count(*) AS n FROM inv.node_channels").fetchone()["n"]
            == 0
        )
        assert (
            conn.execute("SELECT count(*) AS n FROM inv.node_channel_audit").fetchone()[
                "n"
            ]
            == 0
        )


def test_concurrent_certificate_updates_require_current_version(remote):
    a = remote

    def update(_):
        try:
            with psycopg.connect(a.e.owner) as conn:
                return provision_channel(
                    conn,
                    a.node,
                    epoch=a.e.epoch,
                    endpoint=a.endpoint,
                    certificate_der=a.server_cert.der,
                    expected_version=1,
                )
        except DomainError as error:
            return error.code

    with ThreadPoolExecutor(max_workers=2) as pool:
        results = list(pool.map(update, range(2)))
    assert results.count(2) == 1 and results.count("NODE-0034") == 1
    with a.e.db.transaction(a.e.tenant) as conn:
        assert (
            conn.execute("SELECT count(*) AS n FROM inv.node_channel_audit").fetchone()[
                "n"
            ]
            == 2
        )


def test_authority_audit_failure_rolls_back_rotation(remote):
    a = remote
    with psycopg.connect(a.e.owner) as conn:
        # Pre-existing immutable audit version is a controlled conflict in this tenant only.
        conn.execute(
            "INSERT INTO inv.node_channel_audit(tenant_id,node_id,version,action,certificate_sha256) VALUES(%s,%s,2,'revoke',%s)",
            (a.e.tenant, a.e.node, a.server_cert.fingerprint),
        )
    with psycopg.connect(a.e.owner) as conn:
        with pytest.raises(psycopg.errors.UniqueViolation):
            revoke_channel(conn, a.node, expected_version=1)
    assert NodeChannels(a.e.db).snapshot(a.node).version == 1


def test_mtls_receipt_outbox_failure_can_be_recovered_without_execution(
    remote, monkeypatch
):
    import inv.node_execution as module

    a = remote
    prepare(a)
    original = module.event

    def fail(*args):
        raise RuntimeError("synthetic receipt audit failure")

    monkeypatch.setattr(module, "event", fail)
    with pytest.raises(RuntimeError):
        a.delivery.deliver(a.node, a.permit)
    assert active(a) == 2 and count(a, "node_stop_receipts") == 0
    first = stopped(a)
    monkeypatch.setattr(module, "event", original)
    result = a.delivery.deliver(a.node, a.permit, observation_only=True)
    assert result["duplicate"] and result["receipt"] == first
    assert_recorded(a, result)


def test_graceful_node_server_shutdown_finishes_physical_stop(remote):
    a = remote
    a.workload.update(command=["/probe", "sleep"], timeoutSeconds=10)
    prepare(a)
    with ThreadPoolExecutor(max_workers=1) as pool:
        call = pool.submit(a.delivery.deliver, a.node, a.permit)
        deadline = time.monotonic() + 8
        while time.monotonic() < deadline:
            value = container(a)
            if value and value["State"]["Running"]:
                break
            time.sleep(0.05)
        else:
            pytest.fail("Synthetic remote execution did not start")
        a.daemon.terminate()
        result = call.result(timeout=12)
        a.daemon.communicate(timeout=12)
    assert a.daemon.returncode == 0 and result["receipt"]["reason"] == "cancelled"
    assert_recorded(a, result)


def test_response_must_match_the_requested_execution(remote):
    a = remote
    prepare(a)

    class MisroutedClient:
        def exchange(self, channel, permit, *, observation_only=False):
            result = a.client.exchange(
                channel, permit, observation_only=observation_only
            )
            result["receipt"]["commandId"] = str(uuid4())
            return result

    with pytest.raises(DomainError, match="NODE-0035"):
        NodeDelivery(a.e.db, MisroutedClient()).deliver(a.node, a.permit)
    assert active(a) == 2 and count(a, "node_stop_receipts") == 0
    result = a.delivery.deliver(a.node, a.permit, observation_only=True)
    assert_recorded(a, result)
