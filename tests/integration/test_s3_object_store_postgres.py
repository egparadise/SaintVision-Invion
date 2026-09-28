"""Hosted product S3 adapter with real migrated PostgreSQL and RLS.

This file is intentionally excluded from the ordinary Core collection because
it requires both disposable PostgreSQL and the digest-pinned MinIO service.  The
``s01-storage-roundtrip`` job owns those dependencies and executes it directly.
"""

from __future__ import annotations

import hashlib
import base64
import json
import os
from uuid import NAMESPACE_URL, uuid4, uuid5

import psycopg
import pytest

from inv.s3_client import S3Client, S3Config
from inv.s3_object_store import S3Objects
from inv.errors import DomainError
from inv.ids import new_id
from inv.leases import Allocation
from inv.object_store import ObjectStoreRegistry
from inv.snapshots import SnapshotStore
from inv.workspace_files import canonical
from inv.workspace_resume import commit_workspace_output

pytestmark = pytest.mark.postgres


def _provider(prefix: str, provider_id="s3-compatible-v1") -> S3Objects:
    required = (
        "INV_OBJECT_STORE_ENDPOINT",
        "INV_OBJECT_STORE_BUCKET",
        "INV_OBJECT_STORE_ACCESS_KEY_ID",
        "INV_OBJECT_STORE_SECRET_ACCESS_KEY",
        "INV_OBJECT_STORE_REGION",
    )
    missing = [name for name in required if not os.environ.get(name)]
    assert not missing, "Hosted S3/PostgreSQL lane configuration is incomplete"
    client = S3Client(
        S3Config(
            endpoint=os.environ["INV_OBJECT_STORE_ENDPOINT"],
            bucket=os.environ["INV_OBJECT_STORE_BUCKET"],
            access_key=os.environ["INV_OBJECT_STORE_ACCESS_KEY_ID"],
            secret_key=os.environ["INV_OBJECT_STORE_SECRET_ACCESS_KEY"],
            region=os.environ["INV_OBJECT_STORE_REGION"],
        )
    )
    return S3Objects(provider_id, prefix, client)


def _running(env):
    run = env.runs.create(env.tenant, env.project)
    for state in ("validated", "planned"):
        run = env.runs.transition(env.tenant, run["runId"], state, expected_version=run["version"])
    lease = env.leases.reserve(
        env.tenant,
        env.project,
        run["runId"],
        [Allocation(env.resource, 1)],
        key=str(uuid4()),
    )[0]
    proofs = {lease["leaseId"]: lease["fencingToken"]}
    for state in ("scheduled", "running"):
        run = env.runs.transition(
            env.tenant,
            run["runId"],
            state,
            expected_version=run["version"],
            proofs=proofs,
        )
    return run, proofs


def _publish(store, env, object_id, body):
    digest = hashlib.sha256(body).hexdigest()
    store.begin(env.tenant, env.project, object_id, digest, len(body))
    store.put_part(env.tenant, env.project, object_id, 0, body)
    store.finalize(env.tenant, env.project, object_id)
    return digest


def _counts(env, run_id, event_type):
    with env.db.transaction(env.tenant) as connection:
        return tuple(
            connection.execute(statement, (run_id,)).fetchone()["n"]
            for statement in (
                "SELECT count(*) AS n FROM inv.checkpoints WHERE run_id=%s",
                "SELECT count(*) AS n FROM inv.checkpoint_objects WHERE run_id=%s",
                "SELECT count(*) AS n FROM inv.outbox WHERE run_id=%s AND event_type='"
                + event_type
                + "'",
            )
        )


def test_snapshot_store_persists_s3_locator_and_rls_hides_it_from_other_tenant(env):
    data = b"hosted product s3 persistence"
    digest = hashlib.sha256(data).hexdigest()
    object_id = str(uuid4())
    provider = _provider("hosted/" + uuid4().hex)
    store = SnapshotStore(env.db, provider)

    with psycopg.connect(env.owner) as owner:
        owner.execute(
            "INSERT INTO inv.storage_budgets VALUES(%s,%s,%s)",
            (env.tenant, env.project, len(data) * 4),
        )

    store.begin(env.tenant, env.project, object_id, digest, len(data))
    store.put_part(env.tenant, env.project, object_id, 0, data)
    assert store.finalize(env.tenant, env.project, object_id) == digest

    with env.db.transaction(env.tenant) as connection:
        row = connection.execute(
            """SELECT provider_id,locator,content_hash,size_bytes,state
            FROM inv.storage_objects WHERE project_id=%s AND object_id=%s""",
            (env.project, object_id),
        ).fetchone()
    assert row["provider_id"] == "s3-compatible-v1"
    assert row["content_hash"] == digest
    assert row["size_bytes"] == len(data) and row["state"] == "ready"
    assert f"/tenants/{env.tenant}/projects/{env.project}/" in "/" + row["locator"]
    assert provider.get(row["locator"], digest, len(data)) == data

    # The other application tenant cannot discover the locator and therefore
    # cannot use the provider as an authority bypass.
    with env.db.transaction(env.other) as connection:
        assert (
            connection.execute(
                "SELECT locator FROM inv.storage_objects WHERE object_id=%s",
                (object_id,),
            ).fetchone()
            is None
        )

    store.collect(env.tenant, env.project, object_id)
    assert provider.exists(row["locator"]) is False


def test_snapshot_checkpoint_replay_is_quiet_and_registry_restores_s3(env):
    body = b"hosted s3 checkpoint replay"
    provider = _provider("checkpoint/" + uuid4().hex)
    store = SnapshotStore(env.db, provider)
    with psycopg.connect(env.owner) as owner:
        owner.execute(
            "INSERT INTO inv.storage_budgets VALUES(%s,%s,%s)",
            (env.tenant, env.project, len(body) * 8),
        )
    run, proofs = _running(env)
    object_id = str(uuid4())
    _publish(store, env, object_id, body)

    first = store.checkpoint(env.tenant, run["runId"], "s3-step", object_id, proofs=proofs)
    assert store.checkpoint(env.tenant, run["runId"], "s3-step", object_id, proofs=proofs) == first
    assert _counts(env, run["runId"], "inv.run.checkpoint_published") == (1, 1, 1)

    reader = SnapshotStore(
        env.db,
        _provider("unused/" + uuid4().hex, "unused-writer-v1"),
        ObjectStoreRegistry([provider]),
    )
    assert reader.restore(env.tenant, env.project, run["runId"], 1, "s3-step") == body

    changed = _provider("changed/" + uuid4().hex, "s3-compatible-v2")
    changed_store = SnapshotStore(env.db, changed)
    changed_id = str(uuid4())
    _publish(changed_store, env, changed_id, body)
    with pytest.raises(DomainError, match="GRAPH-0004"):
        changed_store.checkpoint(env.tenant, run["runId"], "s3-step", changed_id, proofs=proofs)
    assert _counts(env, run["runId"], "inv.run.checkpoint_published") == (1, 1, 1)


class _DeliveryResult:
    def __init__(self, row):
        self.row = row

    def fetchone(self):
        return self.row


class _DeliveryConnection:
    def __init__(self, connection, envelope, object_row=None):
        self.connection = connection
        self.envelope = envelope
        self.object_row = object_row

    def execute(self, statement, params=()):
        if statement.startswith("SELECT envelope FROM inv.execution_deliveries"):
            return _DeliveryResult({"envelope": self.envelope})
        if self.object_row is not None and statement.startswith(
            "SELECT * FROM inv.storage_objects"
        ):
            return _DeliveryResult(self.object_row)
        return self.connection.execute(statement, params)


def test_workspace_output_replay_binds_provider_and_writes_one_pin_event(env):
    provider = _provider("workspace/" + uuid4().hex)
    store = SnapshotStore(env.db, provider)
    with psycopg.connect(env.owner) as owner:
        owner.execute(
            "INSERT INTO inv.storage_budgets VALUES(%s,%s,%s)",
            (env.tenant, env.project, 1024 * 1024),
        )
    run, _proofs = _running(env)
    command = str(uuid4())
    workspace_id = new_id("wsp")
    resume_id = str(uuid4())
    input_sha = "b" * 64
    snapshot = {
        "format": "workspace-snapshot:1",
        "workspaceId": workspace_id,
        "directories": [],
        "files": [],
    }
    raw = canonical(snapshot)
    artifact = {
        "stdout": "",
        "stderr": "",
        "truncated": False,
        "workspace": {
            "resumeId": resume_id,
            "stepId": "workspace-step",
            "inputSha256": input_sha,
            "snapshot": snapshot,
        },
    }
    result_bytes = json.dumps(artifact, sort_keys=True, separators=(",", ":")).encode()
    receipt = {
        "output": {
            "data": base64.b64encode(result_bytes).decode(),
            "sha256": hashlib.sha256(result_bytes).hexdigest(),
            "sizeBytes": len(result_bytes),
        }
    }
    launch = {
        "workspaceId": workspace_id,
        "workspaceInput": {
            "resumeId": resume_id,
            "stepId": "workspace-step",
            "sha256": input_sha,
        },
    }
    envelope = {
        "payload": base64.b64encode(
            json.dumps({"launch": launch}, separators=(",", ":")).encode()
        ).decode()
    }
    object_id = str(uuid5(NAMESPACE_URL, "inv.workspace-output:" + env.tenant + ":" + command))
    digest = _publish(store, env, object_id, raw)

    def commit(files, object_row=None):
        with env.db.transaction(env.tenant) as connection:
            commit_workspace_output(
                _DeliveryConnection(connection, envelope, object_row),
                files,
                env.tenant,
                env.project,
                run,
                command,
                receipt,
                result_bytes,
            )

    commit(provider)
    commit(provider)
    assert _counts(env, run["runId"], "inv.workspace.step_committed") == (1, 1, 1)

    changed = _provider("workspace-changed/" + uuid4().hex, "s3-compatible-v2")
    changed_locator = changed.locator(env.tenant, env.project, "workspace-outputs", object_id)
    changed.put(changed_locator, raw, digest)
    changed_row = {
        "object_id": object_id,
        "provider_id": changed.provider_id,
        "locator": changed_locator,
        "content_hash": digest,
        "size_bytes": len(raw),
        "state": "ready",
    }
    with pytest.raises(DomainError, match="GRAPH-0004"):
        commit(changed, changed_row)
    assert _counts(env, run["runId"], "inv.workspace.step_committed") == (1, 1, 1)
