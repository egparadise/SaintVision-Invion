import base64
from datetime import datetime, timedelta, timezone
from dataclasses import replace
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
import json
from types import SimpleNamespace
import ssl
from threading import Thread
import time
from uuid import uuid4
import pytest
from inv.ids import new_id
from inv.tooling import NodePrincipal
from inv.node_channels import (
    ChannelProof,
    certificate_identity,
    node_uri,
    endpoint_parts,
)
from inv.node_transport import NodeTLSClient, strict_json
from inv.errors import DomainError
from pki_support import authority, issue, credentials


def receipt(node, epoch):
    now = datetime.now(timezone.utc)
    run = new_id("run")
    return {
        "duplicate": False,
        "cleanupPending": False,
        "receipt": {
            "receiptId": str(uuid4()),
            "claimId": str(uuid4()),
            "commandId": str(uuid4()),
            "tenantId": node.tenant_id,
            "projectId": new_id("prj"),
            "runId": run,
            "nodeId": node.node_id,
            "recoveryEpoch": epoch,
            "planDigest": "a" * 64,
            "containerId": "b" * 64,
            "stopped": True,
            "processStarted": True,
            "exitCode": 0,
            "reason": "exited",
            "finishedAt": now.isoformat(),
            "allocations": [
                {
                    "nodeId": node.node_id,
                    "kind": "cpu",
                    "lease": {
                        "leaseId": new_id("lse"),
                        "tenantId": node.tenant_id,
                        "runId": run,
                        "resourceId": new_id("res"),
                        "amount": 1,
                        "fencingToken": epoch + ":1",
                        "grantedAt": now.isoformat(),
                        "expiresAt": (now + timedelta(minutes=1)).isoformat(),
                    },
                }
            ],
        },
    }


@pytest.fixture
def peer(tmp_path):
    ca = authority()
    node = NodePrincipal(str(uuid4()), new_id("nod"))
    epoch = str(uuid4())
    server = issue(ca, node_uri(node, epoch), server=True)
    cp = issue(ca, "synthetic-control-plane")
    files = credentials(tmp_path, ca, server, prefix="server")
    client_files = credentials(tmp_path, ca, cp, prefix="client")
    state = SimpleNamespace(requests=0, result=receipt(node, epoch), status=200, drip=False)

    class Handler(BaseHTTPRequestHandler):
        def log_message(self, *args):
            pass

        def do_POST(self):
            state.requests += 1
            self.rfile.read(int(self.headers["Content-Length"]))
            body = json.dumps(state.result).encode()
            self.send_response(state.status)
            self.send_header("Content-Type", "application/json")
            self.send_header("Content-Length", str(len(body)))
            self.end_headers()
            try:
                if state.drip:
                    for part in body[:100]:
                        self.wfile.write(bytes([part]))
                        self.wfile.flush()
                        time.sleep(0.05)
                else:
                    self.wfile.write(body)
            except (OSError, ssl.SSLError):
                pass

    class QuietServer(ThreadingHTTPServer):
        def handle_error(self, request, address):
            pass  # Expected peer aborts after rejecting a synthetic certificate.

    httpd = QuietServer(("127.0.0.1", 0), Handler)
    context = ssl.SSLContext(ssl.PROTOCOL_TLS_SERVER)
    context.minimum_version = ssl.TLSVersion.TLSv1_3
    context.load_cert_chain(files["certificate_file"], files["key_file"])
    context.load_verify_locations(files["ca_file"])
    context.verify_mode = ssl.CERT_REQUIRED
    httpd.socket = context.wrap_socket(httpd.socket, server_side=True)
    worker = Thread(target=httpd.serve_forever, daemon=True)
    worker.start()
    channel = ChannelProof(
        node.tenant_id,
        node.node_id,
        epoch,
        1,
        f"https://127.0.0.1:{httpd.server_port}",
        server.fingerprint,
    )
    try:
        yield SimpleNamespace(
            ca=ca,
            node=node,
            epoch=epoch,
            cert=server,
            state=state,
            channel=channel,
            client=NodeTLSClient(**client_files),
            client_files=client_files,
            path=tmp_path,
        )
    finally:
        httpd.shutdown()
        httpd.server_close()
        worker.join(timeout=3)


def test_real_python_tls_verifies_identity_before_transmitting(peer, monkeypatch):
    a = peer
    monkeypatch.setenv("HTTPS_PROXY", "http://127.0.0.1:1")
    keylog = a.path / "forbidden-keylog.txt"
    monkeypatch.setenv("SSLKEYLOGFILE", str(keylog))
    client = NodeTLSClient(**a.client_files)
    result = client.exchange(a.channel, {"synthetic": "private-payload"})
    assert client.context.keylog_filename is None and not keylog.exists()
    assert result == a.state.result and a.state.requests == 1


@pytest.mark.parametrize("change", ["pin", "node", "tenant", "epoch", "ca"])
def test_wrong_server_authority_sends_no_application_request(peer, change):
    a = peer
    channel = a.channel
    client = a.client
    if change == "pin":
        channel = replace(channel, certificate_sha256="c" * 64)
    elif change == "node":
        channel = replace(channel, node_id=new_id("nod"))
    elif change == "tenant":
        channel = replace(channel, tenant_id=str(uuid4()))
    elif change == "epoch":
        channel = replace(channel, recovery_epoch=str(uuid4()))
    else:
        other = authority()
        path = a.path / "other.pem"
        path.write_bytes(other.pem)
        client = NodeTLSClient(**{**a.client_files, "ca_file": path})
    with pytest.raises(DomainError) as error:
        client.exchange(channel, {"synthetic": "private-payload"})
    assert "private-payload" not in str(error.value) and a.state.requests == 0


def test_redirect_is_not_followed(peer):
    peer.state.status = 302
    with pytest.raises(DomainError):
        peer.client.exchange(peer.channel, {})
    assert peer.state.requests == 1


@pytest.mark.parametrize("path", ["/v1/heartbeats", "/v1/snapshots", "/v1/executions"])
def test_capacity_rejection_is_retryable_only_for_observation(peer, path):
    peer.state.status = 429
    with pytest.raises(DomainError) as failure:
        peer.client._request(peer.channel, {}, path, "NodeProbeResult")
    assert peer.state.requests == 1  # Transport itself never resends anything.
    assert failure.value.retryable is (path != "/v1/executions")
    assert failure.value.code == ("NODE-0030" if path == "/v1/executions" else "NODE-0050")


def test_slow_response_is_bounded_without_reconnect(peer):
    peer.state.drip = True
    client = NodeTLSClient(**peer.client_files, timeout=0.3)
    started = time.monotonic()
    with pytest.raises(DomainError):
        client.exchange(peer.channel, {})
    assert time.monotonic() - started < 1.2 and peer.state.requests == 1


@pytest.mark.parametrize("value", ['{"a":1,"a":2}', '{"a":NaN}', "{} {}", '{"invalid":'])
def test_ambiguous_json_response_is_rejected(value):
    with pytest.raises(DomainError):
        strict_json(value)


@pytest.mark.parametrize(
    "url",
    [
        "http://127.0.0.1",
        "https://user:secret@host",
        "https://host/path",
        "https://host?token=secret",
        "https://host#fragment",
        "https://host:0",
        "https://host:99999",
        "https://host\n",
        "https://host/../",
    ],
)
def test_untrusted_origin_forms_are_rejected(url):
    with pytest.raises(DomainError):
        endpoint_parts(url)


@pytest.mark.parametrize("change", ["expired", "client-eku", "other-uri", "extra-uri"])
def test_server_certificate_contract_is_strict(change):
    ca = authority()
    node = NodePrincipal(str(uuid4()), new_id("nod"))
    epoch = str(uuid4())
    uri = node_uri(node, epoch)
    cert = issue(
        ca,
        uri if change != "other-uri" else uri + "/wrong",
        server=change != "client-eku",
        expired=change == "expired",
        extra_uri="synthetic-extra" if change == "extra-uri" else None,
    )
    with pytest.raises(DomainError):
        certificate_identity(cert.der, node, epoch)
