"""Real-PG HTTP binding and least-privilege boundary for snapshot recovery."""

from contextlib import contextmanager
import hashlib
from pathlib import Path
from types import SimpleNamespace
from uuid import UUID, uuid4

import psycopg
from psycopg import sql
from psycopg.conninfo import make_conninfo
from psycopg.errors import InsufficientPrivilege
from psycopg.types.json import Jsonb
import pytest
from fastapi.testclient import TestClient

from inv.app import create_app
from inv.approvals import Principal
from inv.contracts import validate_contract
from inv.ids import new_id
from inv.snapshots import SnapshotStore, object_key
from inv.workspace_recovery import WorkspaceRecovery
from test_approvals import approval

pytestmark = pytest.mark.postgres


class MemoryObjects:
    def __init__(self, raw, object_id):
        self.raw = raw
        self.key = object_key(object_id)

    @contextmanager
    def locked(self):
        yield self

    def read(self, key, digest, size):
        assert key == self.key
        assert len(self.raw) == size
        assert hashlib.sha256(self.raw).hexdigest() == digest
        return self.raw


class MemoryGenerations:
    def __init__(self, label):
        self.root = Path("/") / label
        self.identity = (label, "memory")
        self.values = {}

    @contextmanager
    def locked(self):
        yield self

    def publish(self, _root, identity, raw, workspace_id, *, allow_create=True):
        generation = "generation-" + UUID(str(identity)).hex
        prior = self.values.get(generation)
        if prior is None and not allow_create:
            raise AssertionError("committed generation disappeared")
        if prior is not None:
            assert prior == (raw, workspace_id)
        else:
            self.values[generation] = (raw, workspace_id)
        return generation

    def inspect_committed(self, _root, generation, workspace_id, digest, identity=None):
        raw, stored_workspace = self.values[generation]
        assert stored_workspace == workspace_id
        assert hashlib.sha256(raw).hexdigest() == digest
        return identity or [1, 2, 3, 4]


class Tokens:
    def __init__(self, tenant, principals):
        self.tenant_id = tenant
        self.principals = principals

    def verify(self, value):
        return SimpleNamespace(principal=self.principals[value], expires_at="2026-09-23T00:00:00Z")

    @staticmethod
    def _keys():
        return None


def _auth(name="requester"):
    return {"Authorization": "Bearer " + name}


def test_workspace_snapshot_reader_http_rechecks_scope_and_reads_with_kernel_role(approval):
    a = approval
    run_id = a.run["runId"]
    workspace_id = new_id("wsp")
    restore_id, checkout_id, object_id = str(uuid4()), str(uuid4()), str(uuid4())
    step_id = "files-v1"
    raw = (
        b'{"directories":[],"files":[],"format":"workspace-snapshot:1","workspaceId":"'
        + workspace_id.encode()
        + b'"}'
    )
    digest = hashlib.sha256(raw).hexdigest()
    other_project = new_id("prj")
    app_role = "inv_workspace_reader_" + uuid4().hex[:16]
    password = uuid4().hex
    with psycopg.connect(a.e.owner) as conn:
        conn.execute(
            sql.SQL("CREATE ROLE {} LOGIN PASSWORD {} NOSUPERUSER NOBYPASSRLS").format(
                sql.Identifier(app_role), sql.Literal(password)
            )
        )
        conn.execute(sql.SQL("GRANT inv_app TO {}").format(sql.Identifier(app_role)))
        conn.execute(
            "INSERT INTO inv.projects(tenant_id,project_id) VALUES(%s,%s)",
            (a.e.tenant, other_project),
        )
        conn.execute(
            "UPDATE inv.runs SET state='scheduled',version=version+1 WHERE run_id=%s",
            (run_id,),
        )
        conn.execute(
            "UPDATE inv.runs SET state='running',attempt=attempt+1,version=version+1 WHERE run_id=%s",
            (run_id,),
        )
        conn.execute(
            "INSERT INTO inv.run_attempts(tenant_id,run_id,attempt) VALUES(%s,%s,1)",
            (a.e.tenant, run_id),
        )
        conn.execute(
            "UPDATE inv.runs SET state='recovering',version=version+1 WHERE run_id=%s",
            (run_id,),
        )
        version = conn.execute(
            "SELECT version FROM inv.runs WHERE run_id=%s", (run_id,)
        ).fetchone()[0]
        conn.execute(
            "INSERT INTO inv.storage_budgets VALUES(%s,%s,%s)",
            (a.e.tenant, a.e.project, len(raw) + 1024),
        )
        conn.execute(
            "INSERT INTO inv.storage_objects(tenant_id,project_id,object_id,content_hash,size_bytes) VALUES(%s,%s,%s,%s,%s)",
            (a.e.tenant, a.e.project, object_id, digest, len(raw)),
        )
        conn.execute(
            "UPDATE inv.storage_objects SET state='ready' WHERE object_id=%s", (object_id,)
        )
        conn.execute(
            "INSERT INTO inv.checkpoints(tenant_id,run_id,attempt,step_id,content_hash,checkpoint) VALUES(%s,%s,1,%s,%s,%s)",
            (a.e.tenant, run_id, step_id, digest, Jsonb({"sha256": digest})),
        )
        conn.execute(
            "INSERT INTO inv.checkpoint_objects VALUES(%s,%s,%s,1,%s,%s)",
            (a.e.tenant, a.e.project, run_id, step_id, object_id),
        )

    app_dsn = make_conninfo(a.e.owner, user=app_role, password=password)
    provider = MemoryObjects(raw, object_id)
    restores, working = MemoryGenerations("restores"), MemoryGenerations("working")
    recovery = WorkspaceRecovery(SnapshotStore(a.e.db, provider), restores)
    workspace = SimpleNamespace(recovery=recovery, working=working)
    tokens = Tokens(
        a.e.tenant,
        {
            "requester": a.people["requester"],
            "other": Principal(a.e.other, "outsider"),
        },
    )
    restore_url = f"/v1/projects/{a.e.project}/runs/{run_id}/restores/{restore_id}"
    body = {
        "workspaceId": workspace_id,
        "sourceAttempt": 1,
        "stepId": step_id,
        "expectedVersion": version,
    }
    try:
        with psycopg.connect(app_dsn) as conn:
            with pytest.raises(InsufficientPrivilege):
                conn.execute("SELECT 1 FROM inv.workspace_restores").fetchone()
        with psycopg.connect(a.e.runtime) as conn:
            assert conn.execute("SELECT count(*) FROM inv.workspace_restores").fetchone()[0] == 0
            assert conn.execute("SELECT count(*) FROM inv.checkpoint_objects").fetchone()[0] == 0

        with TestClient(
            create_app(a.e.db, tokens, workspace=workspace), raise_server_exceptions=False
        ) as client:
            restored = client.post(restore_url, json=body, headers=_auth())
            replayed = client.post(restore_url, json=body, headers=_auth())
            checkout = client.post(
                restore_url + f"/checkouts/{checkout_id}",
                json={"expectedVersion": version},
                headers=_auth(),
            )
            foreign_project = client.post(
                f"/v1/projects/{other_project}/runs/{run_id}/restores/{uuid4()}",
                json=body,
                headers=_auth(),
            )
            foreign_tenant = client.post(restore_url, json=body, headers=_auth("other"))
            with psycopg.connect(a.e.owner) as conn:
                conn.execute(
                    "UPDATE inv.project_grants SET enabled=false WHERE project_id=%s AND subject_id='requester'",
                    (a.e.project,),
                )
            revoked_replay = client.post(restore_url, json=body, headers=_auth())

        assert restored.status_code == 201, restored.text
        assert restored.json()["replayed"] is False
        validate_contract("WorkspaceRestoreView", restored.json())
        assert replayed.status_code == 201 and replayed.json()["replayed"] is True
        validate_contract("WorkspaceRestoreView", replayed.json())
        assert checkout.status_code == 201, checkout.text
        validate_contract("WorkspaceCheckoutView", checkout.json())
        for response in (foreign_project, foreign_tenant):
            assert response.status_code == 404, response.text
            validate_contract("ProblemDetails", response.json())
        assert revoked_replay.status_code == 403, revoked_replay.text
        validate_contract("ProblemDetails", revoked_replay.json())
    finally:
        with psycopg.connect(a.e.owner) as conn:
            conn.execute(sql.SQL("DROP ROLE {}").format(sql.Identifier(app_role)))
