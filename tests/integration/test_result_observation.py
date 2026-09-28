"""Canonical result HTTP reads after real Go/Docker execution, with real JWTs."""

import base64
from copy import deepcopy
import hashlib
import json
import os
from uuid import uuid4

import psycopg
import pytest
from fastapi.testclient import TestClient

from inv.app import create_app
from inv.dispatch import DeliveryWorker
from inv.approvals import Principal
from inv.contracts import validate_contract
from inv.errors import DomainError
from inv.output_ingestion import OutputIngestion
from inv.object_store import LocalObjectStore, ObjectStoreRegistry
from inv.result_view import ResultView
from inv.s3_client import S3Client, S3Config
from inv.s3_object_store import S3Objects
from inv.snapshots import SnapshotStore
from inv.workspace_api import WorkspaceAPI
from test_approvals import approval
from test_workspace_start import (
    first,
    input_files,
    prepare,
    enqueue,
    approve,
    run,
    remote,
    storage,
    node_runtime,
    record,
)


def _get(a, suffix, **kwargs):
    response = a.http.get(a.url + suffix, headers=a.headers(), **kwargs)
    assert response.status_code == 200, response.text
    assert response.headers["cache-control"] == "no-store"
    return response


def _execute(a, *, publish=True):
    prepare(a)
    approve(a)
    assert enqueue(a).status_code == 202
    worker = DeliveryWorker(
        a.e.db, a.delivery, output_provider=a.storage.provider if publish else None
    )
    assert worker.once(a.e.tenant) == "stopped"


def _hosted_s3_provider():
    required = (
        "INV_OBJECT_STORE_ENDPOINT",
        "INV_OBJECT_STORE_BUCKET",
        "INV_OBJECT_STORE_ACCESS_KEY_ID",
        "INV_OBJECT_STORE_SECRET_ACCESS_KEY",
        "INV_OBJECT_STORE_REGION",
    )
    missing = [name for name in required if not os.environ.get(name)]
    assert not missing, "Core product ObjectStore configuration is incomplete"
    return S3Objects(
        "s3-compatible-v1",
        "core/" + uuid4().hex,
        S3Client(
            S3Config(
                endpoint=os.environ["INV_OBJECT_STORE_ENDPOINT"],
                bucket=os.environ["INV_OBJECT_STORE_BUCKET"],
                access_key=os.environ["INV_OBJECT_STORE_ACCESS_KEY_ID"],
                secret_key=os.environ["INV_OBJECT_STORE_SECRET_ACCESS_KEY"],
                region=os.environ["INV_OBJECT_STORE_REGION"],
            )
        ),
    )


def test_result_and_download_match_actual_node_output_and_current_grant(first):
    a = first
    input_files(a, "ai")
    _execute(a)
    result = _get(a, "/result").json()
    assert result["source"] == "execution-kernel"
    assert result["state"] == "succeeded" and result["sealed"] and result["executionConfirmed"]
    assert result["attemptCount"] == 1 and not result["resourceReleasePending"]
    assert result["stateUpdatedAt"]
    with a.e.db.transaction(a.e.tenant) as c:
        row = c.execute(
            "SELECT evidence_id,completed_at FROM inv.result_completions WHERE command_id=%s",
            (a.enqueued["commandId"],),
        ).fetchone()
        saved_run = c.execute(
            "SELECT updated_at FROM inv.runs WHERE run_id=%s", (a.run["runId"],)
        ).fetchone()
        assert result["evidence"]["evidenceId"] == row["evidence_id"]
        assert result["stateUpdatedAt"] == saved_run["updated_at"].isoformat()
        facts = ResultView._current(
            c, c.execute("SELECT * FROM inv.runs WHERE run_id=%s", (a.run["runId"],)).fetchone()
        )
    assert result["stopReceipt"]["receiptId"] == str(facts["receipt_id"])
    alias = "/v1/runs/" + a.run["runId"]
    assert a.http.get(alias + "/result", headers=a.headers()).json() == result
    artifacts = _get(a, "/artifacts").json()
    assert artifacts["count"] > 0 and artifacts["count"] == artifacts["verifiedCount"]
    assert artifacts["completedAt"] == row["completed_at"].isoformat()
    item = next(f for f in artifacts["artifacts"] if f["path"] == "outputs/metrics.json")
    response = _get(a, "/artifacts/content", params={"path": item["path"]})
    assert len(response.content) == item["byteSize"]
    assert (
        hashlib.sha256(response.content).hexdigest()
        == item["checksumSha256"]
        == response.headers["x-content-sha256"]
    )
    assert response.headers["content-disposition"].startswith("attachment;")
    validate_contract(
        "ArtifactContentResponse",
        {
            "statusCode": response.status_code,
            "contentType": response.headers["content-type"],
            "contentDisposition": response.headers["content-disposition"],
            "artifact": item,
            "contentTypeOptions": response.headers["x-content-type-options"],
        },
    )
    assert response.headers["cache-control"] == "no-store"
    assert json.loads(response.content)["evaluationMSE"] < 1e-8
    logs = _get(a, "/logs").json()
    assert logs["stdout"] is not None
    assert logs["completedAt"] == row["completed_at"].isoformat()
    attempts = _get(a, "/attempts").json()
    assert attempts["count"] == 1 and attempts["attempts"][0]["evidenceId"] == row["evidence_id"]
    assert _get(a, "/attempts?after=1").json()["count"] == 0
    assert a.http.get(alias + "/attempts?limit=201", headers=a.headers()).status_code == 422
    assert (
        a.http.get(
            alias + "/artifacts/content", params={"path": "../outside"}, headers=a.headers()
        ).status_code
        == 422
    )
    assert (
        a.http.get(
            alias + "/artifacts/content", params={"path": "not-present"}, headers=a.headers()
        ).status_code
        == 404
    )
    assert a.http.get(alias + "/result").status_code == 401
    assert a.http.get(alias + "/result", headers=a.headers("unregistered")).status_code == 403
    with pytest.raises(DomainError) as denied:
        ResultView(a.e.db).result(Principal(a.e.other, a.jwt.subject("requester")), a.run["runId"])
    assert denied.value.status == 403
    local = ObjectStoreRegistry([LocalObjectStore(a.storage.provider)])
    with pytest.raises(DomainError) as denied_download:
        ResultView(a.e.db, local).download(
            Principal(a.e.other, a.jwt.subject("requester")),
            a.run["runId"],
            item["path"],
            a.e.project,
        )
    assert denied_download.value.status == 403
    # A corrupted stored receipt cannot produce a verified downloadable file.
    bad = deepcopy(facts)
    bad["receipt"]["output"]["data"] = base64.b64encode(b"changed").decode()
    with pytest.raises(DomainError, match="Output bytes"):
        ResultView._output(bad)
    with psycopg.connect(a.e.owner) as c:
        c.execute(
            "UPDATE inv.project_grants SET enabled=false WHERE tenant_id=%s AND subject_id=%s",
            (a.e.tenant, a.jwt.subject("requester")),
        )
    for suffix in (
        "/result",
        "/artifacts",
        "/attempts",
        "/logs",
        "/artifacts/content?path=outputs/metrics.json",
    ):
        assert a.http.get(alias + suffix, headers=a.headers()).status_code == 403


def test_s3_published_result_downloads_through_http_and_missing_object_fails_closed(first):
    a = first
    provider = _hosted_s3_provider()
    a.storage = SnapshotStore(a.e.db, provider)
    a.http.close()
    a.http = TestClient(
        create_app(
            a.e.db,
            a.jwt.auth,
            workspace=WorkspaceAPI(a.e.db, a.working, a.runtime),
            object_stores=ObjectStoreRegistry([provider]),
        ),
        raise_server_exceptions=False,
    )

    input_files(a, "ai")
    _execute(a)
    item = next(
        artifact
        for artifact in _get(a, "/artifacts").json()["artifacts"]
        if artifact["path"] == "outputs/metrics.json"
    )
    response = _get(a, "/artifacts/content", params={"path": item["path"]})
    assert hashlib.sha256(response.content).hexdigest() == item["checksumSha256"]
    assert response.headers["x-content-sha256"] == item["checksumSha256"]

    with a.e.db.transaction(a.e.tenant) as connection:
        row = connection.execute(
            """SELECT o.provider_id,o.locator,o.content_hash,o.size_bytes
            FROM inv.storage_objects o JOIN inv.result_commitments c USING(tenant_id,project_id,object_id)
            WHERE c.run_id=%s""",
            (a.run["runId"],),
        ).fetchone()
    assert row["provider_id"] == provider.provider_id
    # The storage digest covers the outer bounded output object. The HTTP hash
    # covers the selected manifest file; neither level is silently substituted.
    outer = provider.get(row["locator"], row["content_hash"], row["size_bytes"])
    assert hashlib.sha256(outer).hexdigest() == row["content_hash"]

    provider.delete(row["locator"])
    missing = a.http.get(
        a.url + "/artifacts/content",
        params={"path": item["path"]},
        headers=a.headers(),
    )
    assert missing.status_code == 503
    assert missing.json()["code"] == "STORE-0001"


def test_draft_and_cancelled_run_never_report_success_or_placeholder_output(first):
    a = first
    body = _get(a, "/result").json()
    assert body["state"] == "draft" and body["output"] is None and body["evidence"] is None
    assert not body["sealed"] and not body["executionConfirmed"] and body["commandId"] is None
    assert body["stateUpdatedAt"]
    artifacts = _get(a, "/artifacts").json()
    assert artifacts["artifacts"] == [] and artifacts["completedAt"] is None
    logs = _get(a, "/logs").json()
    assert logs["stdout"] is None and logs["completedAt"] is None
    assert _get(a, "/attempts").json()["attempts"] == []
    response = a.http.post(
        a.url + "/cancel",
        json={"expectedVersion": run(a)["version"]},
        headers=a.headers(key="cancel-result"),
    )
    assert response.status_code == 200
    body = _get(a, "/result").json()
    assert body["state"] == "cancelled" and not body["sealed"] and body["evidence"] is None
    assert (
        a.http.get("/v1/runs/run_" + "0" * 26 + "/result", headers=a.headers()).status_code == 403
    )


def test_failed_process_reports_actual_exit_without_success_evidence(first):
    a = first
    a.prepare_input["workload"]["command"] = ["/usr/local/bin/python3", "-c", "raise SystemExit(7)"]
    _execute(a)
    body = _get(a, "/result").json()
    assert body["state"] == "failed" and body["executionConfirmed"]
    assert body["stopReceipt"]["exitCode"] == 7
    assert body["evidence"] is None and not body["sealed"]
    assert _get(a, "/artifacts").json()["artifacts"] == []
    assert _get(a, "/attempts").json()["attempts"][0]["exitCode"] == 7


def test_queued_cancellation_exposes_tombstone_without_inventing_attempt(first):
    a = first
    prepare(a)
    approve(a)
    assert enqueue(a).status_code == 202
    response = a.http.post(
        a.url + "/cancel",
        json={"expectedVersion": run(a)["version"]},
        headers=a.headers(key="queued-cancel-result"),
    )
    assert response.status_code == 200
    assert (
        DeliveryWorker(a.e.db, a.delivery, output_provider=a.storage.provider).once(a.e.tenant)
        == "stopped"
    )
    body = _get(a, "/result").json()
    assert body["state"] == "cancelled" and body["attemptCount"] == 0
    assert body["stopReceipt"] is not None and not body["executionConfirmed"]
    assert body["stopReceipt"]["processStarted"] is False and body["evidence"] is None
    assert _get(a, "/attempts").json()["attempts"] == []


def test_physical_stop_is_distinct_from_result_recovery_and_logs_are_redacted(first):
    a = first
    a.prepare_input["workload"]["command"] = [
        "/usr/local/bin/python3",
        "-c",
        "print('ordinary output'); print('password=synthetic-do-not-display')",
    ]
    _execute(a, publish=False)
    body = _get(a, "/result").json()
    assert body["executionConfirmed"] and body["stopReceipt"]["exitCode"] == 0
    assert body["evidence"] is None and not body["sealed"] and body["output"] is None
    assert _get(a, "/logs").json()["stdout"] is None
    assert (
        OutputIngestion(a.e.db, a.storage.provider).once(
            a.e.tenant, command_id=a.enqueued["commandId"]
        )
        == "completed"
    )
    body = _get(a, "/result").json()
    assert body["state"] == "succeeded" and body["sealed"]
    logs = _get(a, "/logs").json()
    assert logs["redacted"] and "ordinary output" in logs["stdout"]
    assert "synthetic-do-not-display" not in logs["stdout"]
    assert logs["truncated"] is False
