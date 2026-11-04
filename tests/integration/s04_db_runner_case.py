"""One real-PostgreSQL S04 acceptance evidence case, invoked only by its tool."""

from __future__ import annotations

import json
import os
from pathlib import Path
from datetime import datetime, timedelta, timezone
import time

import pytest

from inv.errors import DomainError
from inv.outbox import Outbox
from inv.runs import event
from test_approvals import approval, challenge, decide, dispatch, request  # noqa: F401
from test_control_api import api

pytestmark = pytest.mark.postgres


class _RedactedApi:
    """Delegate to the fixture without exposing its DSNs in pytest failures."""

    def __init__(self, value):
        self._value = value

    def __getattr__(self, name):
        return getattr(self._value, name)

    def __repr__(self):
        return "<S04Api redacted>"


@pytest.fixture
def s04_api(api):
    return _RedactedApi(api)


def _write_report(report: dict) -> None:
    target_value = os.environ.get("INV_S04_DB_EVIDENCE_JSON")
    if not target_value:
        pytest.fail("run only through tools/run_s04_db_evidence.py")
    target = Path(target_value)
    temporary = target.with_suffix(target.suffix + ".tmp")
    temporary.write_text(json.dumps(report, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    temporary.replace(target)


def test_http_pg_expiry_cancel_idempotency_and_outbox_crash_retry(s04_api):
    a = s04_api
    cases = []

    # HTTP create/cancel exact replay must not duplicate the Run or cancel event.
    with a.e.db.transaction(a.e.tenant) as conn:
        runs_before = conn.execute("SELECT count(*) AS n FROM inv.runs").fetchone()["n"]
    create_headers = a.headers(key="s04-create")
    created = a.client.post(a.url + "/runs", json={}, headers=create_headers)
    replayed = a.client.post(a.url + "/runs", json={}, headers=create_headers)
    assert created.status_code == replayed.status_code == 201
    assert created.json() == replayed.json()
    run = created.json()
    run_url = a.url + "/runs/" + run["runId"]
    cancel_headers = a.headers(key="s04-cancel")
    cancelled = a.client.post(
        run_url + "/cancel",
        json={"expectedVersion": run["version"]},
        headers=cancel_headers,
    )
    cancel_replay = a.client.post(
        run_url + "/cancel",
        json={"expectedVersion": run["version"]},
        headers=cancel_headers,
    )
    assert cancelled.status_code == cancel_replay.status_code == 200
    assert cancelled.json() == cancel_replay.json()
    with a.e.db.transaction(a.e.tenant) as conn:
        created_run_count = (
            conn.execute("SELECT count(*) AS n FROM inv.runs").fetchone()["n"] - runs_before
        )
        cancel_events = conn.execute(
            "SELECT count(*) AS n FROM inv.outbox "
            "WHERE run_id=%s AND event_type='inv.run.cancel_requested'",
            (run["runId"],),
        ).fetchone()["n"]
    assert created_run_count == cancel_events == 1
    cases.append(
        {
            "id": "http-run-idempotency-cancel",
            "status": "PASS",
            "httpStatuses": [201, 201, 200, 200],
            "runCount": created_run_count,
            "cancelOutboxCount": cancel_events,
        }
    )

    # Approval votes travel over HTTP; dispatch is blocked before quorum. The
    # immutable deadline passes naturally; expiry closes the Run exactly once.
    a.policy["expiresAt"] = (datetime.now(timezone.utc) + timedelta(seconds=10)).isoformat()
    approval = request(a, key="s04-approval")
    approval_url = a.url + "/approvals/" + approval["approvalId"]
    first_nonce = a.client.post(approval_url + "/challenge", json={}, headers=a.headers("alice"))
    assert first_nonce.status_code == 200
    first_body = {
        "decision": "approve",
        "nonce": first_nonce.json()["nonce"],
        "actionDigest": approval["actionDigest"],
    }
    first_vote_headers = a.headers("alice", key="s04-vote-alice")
    first_vote = a.client.post(
        approval_url + "/decision", json=first_body, headers=first_vote_headers
    )
    first_vote_replay = a.client.post(
        approval_url + "/decision", json=first_body, headers=first_vote_headers
    )
    assert first_vote.status_code == first_vote_replay.status_code == 200
    assert first_vote.json() == first_vote_replay.json()
    assert first_vote.json()["status"] == "pending"
    with pytest.raises(DomainError, match="AUTH-0031"):
        dispatch(a, approval, key="s04-before-quorum")
    second_nonce = a.client.post(approval_url + "/challenge", json={}, headers=a.headers("bob"))
    assert second_nonce.status_code == 200
    second_vote = a.client.post(
        approval_url + "/decision",
        json={
            "decision": "approve",
            "nonce": second_nonce.json()["nonce"],
            "actionDigest": approval["actionDigest"],
        },
        headers=a.headers("bob", key="s04-vote-bob"),
    )
    assert second_vote.status_code == 200 and second_vote.json()["status"] == "approved"
    remaining = (
        datetime.fromisoformat(approval["expiresAt"]) - datetime.now(timezone.utc)
    ).total_seconds()
    time.sleep(max(0, remaining) + 0.05)
    with pytest.raises(DomainError, match="AUTH-0031"):
        dispatch(a, approval, key="s04-after-expiry")
    assert a.store.expire(a.e.tenant, a.e.project, approval["approvalId"])
    assert not a.store.expire(a.e.tenant, a.e.project, approval["approvalId"])
    with a.e.db.transaction(a.e.tenant) as conn:
        dispatch_count = conn.execute(
            "SELECT count(*) AS n FROM inv.approval_dispatches WHERE approval_id=%s",
            (approval["approvalId"],),
        ).fetchone()["n"]
        authorized_count = conn.execute(
            "SELECT count(*) AS n FROM inv.outbox "
            "WHERE run_id=%s AND event_type='inv.command.authorized'",
            (a.run["runId"],),
        ).fetchone()["n"]
        approval_status = conn.execute(
            "SELECT status,expires_at FROM inv.approval_requests WHERE approval_id=%s",
            (approval["approvalId"],),
        ).fetchone()
    assert approval_status["expires_at"] == datetime.fromisoformat(approval["expiresAt"])
    approval_status = approval_status["status"]
    assert dispatch_count == authorized_count == 0
    assert approval_status == "expired"
    assert a.e.runs.get(a.e.tenant, a.run["runId"])["state"] == "failed"
    cases.append(
        {
            "id": "approval-before-execution-and-expiry",
            "status": "PASS",
            "httpVoteStatuses": [200, 200, 200],
            "approvalStatus": approval_status,
            "dispatchCount": dispatch_count,
            "authorizedCommandOutboxCount": authorized_count,
            "expiryClosedExactlyOnce": True,
        }
    )

    # A broker ACK followed by process failure republishes the same event. The
    # downstream consumer transaction rolls back on failure and deduplicates a
    # later exact replay after one successful effect.
    outbox = Outbox(a.e.db)
    sent = []

    def crash(payload):
        sent.append(payload)
        raise RuntimeError("injected broker ACK then process crash")

    with pytest.raises(RuntimeError, match="injected broker"):
        outbox.publish_batch(a.e.tenant, crash, limit=1)
    crashed_event_id = sent[0]["eventId"]
    outbox.publish_batch(a.e.tenant, sent.append, limit=100)
    duplicate_publications = sum(payload["eventId"] == crashed_event_id for payload in sent)
    assert duplicate_publications == 2
    cases.append(
        {
            "id": "outbox-publisher-crash-retry",
            "status": "PASS",
            "sameEventPublicationCount": duplicate_publications,
        }
    )

    effect_type = "inv.s04_evidence.consumer_effect"

    def consumer_effect(conn):
        event(conn, a.e.tenant, a.run["runId"], effect_type, {})

    def consumer_counts():
        with a.e.db.transaction(a.e.tenant) as conn:
            effects = conn.execute(
                "SELECT count(*) AS n FROM inv.outbox WHERE run_id=%s AND event_type=%s",
                (a.run["runId"], effect_type),
            ).fetchone()["n"]
            inbox = conn.execute(
                "SELECT count(*) AS n FROM inv.consumer_inbox WHERE consumer=%s AND event_id=%s",
                ("s04-card34", crashed_event_id),
            ).fetchone()["n"]
        return effects, inbox

    def consumer_crash(conn):
        consumer_effect(conn)
        raise RuntimeError("injected consumer failure before commit")

    with pytest.raises(RuntimeError, match="injected consumer"):
        outbox.consume(a.e.tenant, "s04-card34", crashed_event_id, consumer_crash)
    assert consumer_counts() == (0, 0)
    assert outbox.consume(
        a.e.tenant,
        "s04-card34",
        crashed_event_id,
        consumer_effect,
    )
    assert not outbox.consume(
        a.e.tenant,
        "s04-card34",
        crashed_event_id,
        consumer_effect,
    )
    committed_effects, committed_inbox = consumer_counts()
    assert (committed_effects, committed_inbox) == (1, 1)
    cases.append(
        {
            "id": "outbox-consumer-rollback-dedup",
            "status": "PASS",
            "committedEffects": committed_effects,
            "committedInboxRows": committed_inbox,
            "rolledBackEffects": 0,
            "duplicateEffectCount": 0,
        }
    )

    provenance = json.loads(os.environ["INV_S04_DB_PROVENANCE"])
    _write_report(
        {
            "schemaVersion": 1,
            "taskId": "S04-DB",
            "measurementScope": "disposable-postgresql-http-kernel",
            "provenance": provenance,
            "codeSha": provenance["codeSha"],
            "publicContractChanged": False,
            "migrationChanged": False,
            "physicalNodeDeliveryResumption": "UNMEASURED",
            "operationalAcceptanceAssessed": False,
            "cases": cases,
        }
    )
