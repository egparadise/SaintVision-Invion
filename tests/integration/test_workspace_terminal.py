"""Actual PTY/mTLS/DB boundary, with isolated synthetic identities and containers."""

import base64
from concurrent.futures import ThreadPoolExecutor
from dataclasses import replace
import hashlib
import secrets
import sys
import time
from uuid import uuid4

import psycopg
import pytest
from fastapi.testclient import TestClient
from starlette.websockets import WebSocketDisconnect
from inv.app import create_app
from inv.dispatch import DeliveryWorker
from inv.errors import DomainError
from inv.terminal import TerminalService
from inv.workspace_api import WorkspaceAPI
from inv.workspace_files import canonical
from test_workspace_start import first, prepare, approve, enqueue, run
from test_approvals import approval, count
from test_node_delivery import remote
from test_node_runtime import node_runtime, active, container
from test_snapshots import storage

pytestmark = [pytest.mark.postgres, pytest.mark.skipif(sys.platform != "linux", reason="Linux PTY")]
ORIGIN = "https://studio.test"


def frame(operation="poll", *, sequence=0, cursor=0, text=""):
    return dict(
        operation=operation,
        sequence=sequence,
        cursor=cursor,
        dataBase64=base64.b64encode(text.encode()).decode(),
        rows=24,
        columns=80,
        nonce=secrets.token_hex(32),
    )


@pytest.fixture
def terminal(first):
    a = first
    a.profile = replace(a.profile, allow_terminal=True)
    a.runtime.profile = a.profile
    a.service = WorkspaceAPI(a.e.db, a.working, a.runtime)
    a.http.close()
    a.http = TestClient(
        create_app(a.e.db, a.jwt.auth, workspace=a.service, allowed_origins=(ORIGIN,)),
        raise_server_exceptions=False,
    )
    script = b"import sys\nprint('ready', flush=True)\nfor line in sys.stdin:\n print('ACK:' + line.strip(), flush=True)\n"
    snapshot = canonical(
        dict(
            format="workspace-snapshot:1",
            workspaceId=a.workspace_id,
            directories=["src"],
            files=[
                dict(
                    path="src/app.py",
                    executable=False,
                    sha256=hashlib.sha256(script).hexdigest(),
                    sizeBytes=len(script),
                    dataBase64=base64.b64encode(script).decode(),
                )
            ],
        )
    )
    a.prepare_input["snapshotBase64"] = base64.b64encode(snapshot).decode()
    a.prepare_input["workload"].update(
        timeoutSeconds=30,
        terminal=dict(
            sessionId=str(uuid4()), rows=24, columns=80, maxInputBytes=4096, maxOutputBytes=8192
        ),
    )
    prepare(a)
    approve(a)
    assert enqueue(a).status_code == 202
    a.terminal = TerminalService(a.service, (ORIGIN,))
    with ThreadPoolExecutor(max_workers=1) as pool:
        future = pool.submit(
            DeliveryWorker(a.e.db, a.delivery, output_provider=a.storage.provider).once, a.e.tenant
        )
        try:
            deadline = time.monotonic() + 8
            while time.monotonic() < deadline:
                state = container(a)
                if run(a)["state"] == "running" and state and state["State"]["Running"]:
                    break
                if future.done():
                    future.result()
                    pytest.fail("PTY execution stopped before attachment")
                time.sleep(0.05)
            else:
                pytest.fail("PTY execution did not start")
            yield a
        finally:
            current = run(a)
            if current["state"] == "running":
                response = a.http.post(
                    a.url + "/cancel",
                    json={"expectedVersion": current["version"]},
                    headers=a.headers(key="terminal-cleanup"),
                )
                assert response.status_code == 200, response.text
            DeliveryWorker(a.e.db, a.delivery).once(a.e.tenant, control_only=True)
            future.result(timeout=40)
    # Physical deletion and reservation release must follow the signed stop receipt.
    worker = DeliveryWorker(a.e.db, a.delivery, output_provider=a.storage.provider)
    for _ in range(3):
        if active(a) == 0:
            break
        worker.once(a.e.tenant)
    assert container(a) is None and active(a) == 0


def ticket(a, *, actor="requester", origin=ORIGIN):
    return a.http.post(
        f"/v1/workspaces/{a.workspace_id}/terminal-tickets",
        json=a.command,
        headers={**a.headers(actor), "Origin": origin},
    )


def redeem(a, value):
    return a.terminal.redeem(
        a.e.tenant, a.workspace_id, value["sessionId"], value["ticket"], ORIGIN
    )


def test_actual_terminal_input_replay_reconnect_and_cancel(terminal):
    a = terminal
    response = ticket(a)
    assert response.status_code == 201, response.text
    value = response.json()
    attached = redeem(a, value)
    with pytest.raises(DomainError):
        redeem(a, value)
    request = frame("input", sequence=1, text="one\n")
    first_result = a.terminal.frame(attached, request)
    assert a.terminal.frame(attached, request) == first_result
    with pytest.raises(DomainError):
        a.terminal.frame(attached, frame("input", sequence=1, text="different\n"))
    a.terminal.release(attached)
    second_ticket = ticket(a).json()
    attached2 = redeem(a, second_ticket)
    assert attached2.session_id == attached.session_id
    a.terminal.release(attached)  # Old disconnect must not evict the new attachment.
    output = b""
    deadline = time.monotonic() + 4
    while time.monotonic() < deadline:
        part = a.terminal.frame(attached2, frame(cursor=len(output)))
        output += base64.b64decode(part["dataBase64"])
        if b"ACK:one" in output:
            break
        time.sleep(0.05)
    assert output.count(b"ACK:one") == 1 and b"different" not in output
    with a.e.db.transaction(a.e.tenant) as conn:
        assert (
            conn.execute("SELECT count(*) AS n FROM inv.terminal_frame_audit").fetchone()["n"] == 1
        )
        assert conn.execute("SELECT count(*) AS n FROM inv.execution_attempts").fetchone()["n"] == 1
    cancelled = a.http.post(
        a.url + "/cancel",
        json={"expectedVersion": run(a)["version"]},
        headers=a.headers(key="terminal-cancel"),
    )
    assert cancelled.status_code == 200, cancelled.text
    with pytest.raises(DomainError):
        a.terminal.frame(attached2, frame("input", sequence=2, text="after-cancel\n"))
    assert ticket(a).status_code == 403


def test_terminal_ticket_scope_expiry_and_current_grant(terminal):
    a = terminal
    assert ticket(a, origin="https://untrusted.test").status_code == 403
    assert ticket(a, actor="alice").status_code == 403
    # Expiry must be tested without mutating an immutable ticket row.
    value = a.terminal.issue(
        a.jwt.auth.verify(a.jwt.token("requester", claims={"exp": int(time.time()) + 2})),
        a.workspace_id,
        a.command,
        ORIGIN,
    )
    with pytest.raises(DomainError):
        a.terminal.redeem(a.e.tenant, "ws_other", value["sessionId"], value["ticket"], ORIGIN)
    time.sleep(2.1)
    with pytest.raises(DomainError):
        redeem(a, value)
    value = ticket(a).json()
    attached = redeem(a, value)
    second = ticket(a).json()
    with pytest.raises(DomainError) as busy:
        redeem(a, second)
    assert busy.value.status == 409
    with psycopg.connect(a.e.owner) as conn:
        conn.execute(
            "UPDATE inv.project_grants SET enabled=false WHERE tenant_id=%s AND subject_id=%s",
            (a.e.tenant, a.jwt.subject("requester")),
        )
    try:
        assert ticket(a).status_code == 403
        with pytest.raises(DomainError):
            a.terminal.frame(attached, frame("input", sequence=1, text="revoked\n"))
        assert count(a, "terminal_frame_audit") == 0
    finally:
        with psycopg.connect(a.e.owner) as conn:
            conn.execute(
                "UPDATE inv.project_grants SET enabled=true WHERE tenant_id=%s AND subject_id=%s",
                (a.e.tenant, a.jwt.subject("requester")),
            )


def test_actual_terminal_websocket_uses_single_use_ticket(terminal):
    a = terminal
    value = ticket(a).json()
    with a.http.websocket_connect(
        value["websocketPath"], headers={"Origin": ORIGIN}, subprotocols=["inv-terminal-v1"]
    ) as ws:
        ws.send_json({"ticket": value["ticket"]})
        received = ws.receive_json()
        assert received["outputMode"] == "redacted-complete-lines"
        ws.send_json(frame("input", sequence=1, cursor=received["cursor"], text="browser\n"))
        output = ""
        for _ in range(8):
            received = ws.receive_json()
            output += received["text"]
            if "ACK:browser" in output:
                break
        assert "ACK:browser" in output
    with pytest.raises(WebSocketDisconnect):
        with a.http.websocket_connect(
            value["websocketPath"], headers={"Origin": ORIGIN}, subprotocols=["inv-terminal-v1"]
        ) as ws:
            ws.send_json({"ticket": value["ticket"]})
            ws.receive_json()


@pytest.mark.parametrize("fault", ["before_send", "lost_response", "wrong_scope"])
def test_terminal_intent_survives_uncertain_dispatch_and_pins_replay(terminal, monkeypatch, fault):
    a = terminal
    attached = redeem(a, ticket(a).json())
    request = frame("input", sequence=1, text="intent-once\n")
    original = a.runtime.client.terminal_frame
    calls = []

    def uncertain(channel, payload):
        calls.append(payload)
        # A separate transaction can see the committed intent before transport.
        assert count(a, "terminal_frame_intents") == 1
        assert count(a, "terminal_frame_audit") == 0
        if fault == "before_send":
            raise TimeoutError("test transport unavailable")
        result = original(channel, payload)
        if fault == "lost_response":
            raise TimeoutError("test response lost after Node accepted input")
        return {**result, "nonce": "0" * 64}

    monkeypatch.setattr(a.runtime.client, "terminal_frame", uncertain)
    with pytest.raises((TimeoutError, DomainError)):
        a.terminal.frame(attached, request)
    assert count(a, "terminal_frame_intents") == 1
    assert count(a, "terminal_frame_audit") == 0
    # A fresh service object must respect durable intent, not process memory.
    service = TerminalService(a.service, (ORIGIN,))
    for invalid in [
        frame("input", sequence=1, text="changed\n"),
        frame("input", sequence=2, text="overtake\n"),
    ]:
        with pytest.raises(DomainError):
            service.frame(attached, invalid)
    assert len(calls) == 1  # Rejections occur before contacting the Node.
    monkeypatch.setattr(a.runtime.client, "terminal_frame", original)
    service.frame(attached, frame())  # Reading alone is not completion evidence.
    assert count(a, "terminal_frame_audit") == 0
    service.frame(attached, request)
    assert count(a, "terminal_frame_audit") == 1
    assert count(a, "terminal_frame_intents") == 1
    with a.e.db.transaction(a.e.tenant) as conn:
        events = conn.execute(
            "SELECT event_type,payload FROM inv.outbox WHERE run_id=%s AND event_type IN ('inv.terminal.frame_intended','inv.terminal.frame')",
            (run(a)["runId"],),
        ).fetchall()
    assert sorted(e["event_type"] for e in events) == [
        "inv.terminal.frame",
        "inv.terminal.frame_intended",
    ]
    assert all("dataBase64" not in e["payload"] and "nonce" not in e["payload"] for e in events)
    output = b""
    deadline = time.monotonic() + 4
    while time.monotonic() < deadline:
        result = service.frame(attached, frame(cursor=len(output)))
        output += base64.b64decode(result["dataBase64"])
        if b"ACK:intent-once" in output:
            break
        time.sleep(0.02)
    assert output.count(b"ACK:intent-once") == 1
    assert b"changed" not in output and b"overtake" not in output
    with a.e.db.transaction(a.e.other) as conn:
        assert (
            conn.execute("SELECT count(*) AS n FROM inv.terminal_frame_intents").fetchone()["n"]
            == 0
        )
    with psycopg.connect(a.e.owner) as conn, pytest.raises(psycopg.Error):
        conn.execute("DELETE FROM inv.terminal_frame_intents")


def test_terminal_failed_intent_transaction_never_dispatches(terminal, monkeypatch):
    import inv.terminal as module

    a = terminal
    attached = redeem(a, ticket(a).json())
    original_event = module.event
    calls = []

    def fail_event(conn, tenant, run_id, event_type, payload):
        if event_type == "inv.terminal.frame_intended":
            raise RuntimeError("test intent transaction failure")
        return original_event(conn, tenant, run_id, event_type, payload)

    monkeypatch.setattr(module, "event", fail_event)
    monkeypatch.setattr(a.runtime.client, "terminal_frame", lambda *args: calls.append(args))
    with pytest.raises(RuntimeError, match="intent transaction failure"):
        a.terminal.frame(attached, frame("input", sequence=1, text="not-dispatched\n"))
    assert calls == []
    assert count(a, "terminal_frame_intents") == count(a, "terminal_frame_audit") == 0
