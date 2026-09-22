"""Real PostgreSQL HTTP boundaries for model retry authorization and manifest projection."""

from copy import deepcopy
import hashlib
from types import SimpleNamespace

import psycopg
from psycopg.types.json import Jsonb
import pytest
from fastapi.testclient import TestClient

from inv.app import create_app
from inv.approvals import Principal
from inv.contracts import validate_contract
from inv.ids import new_id
from inv.model_manifest import canonical
from inv.model_retry import ModelRetryStore
from inv.model_view import ModelExecutionManifestObservation
from test_model_runtime import runtime
from test_model_locality import locality
from test_model_commit import model
from test_storage_commit import sample, storage_subject
from test_approvals import approval


pytestmark = pytest.mark.postgres


def tokens(a, principal):
    class Tokens:
        tenant_id = principal.tenant_id

        @staticmethod
        def verify(value):
            return SimpleNamespace(principal=principal, expires_at="2026-09-22T20:00:00Z")

        @staticmethod
        def _keys():
            return None

    return Tokens()


def auth():
    return {"Authorization": "Bearer synthetic"}


def retry_body(a):
    request = a.request
    return {
        "cpuMillis": request.cpu_millis,
        "memoryBytes": request.memory_bytes,
        "gpuCount": request.gpu_count,
        "minVramBytes": request.min_vram_bytes,
        "requiredBytes": request.required_bytes,
        "maxHostLoad": float(request.max_host_load),
        "runtime": request.runtime,
        "policyVersion": "model-retry:1",
    }


def test_model_retry_cross_tenant_is_honest_403_problem_details(runtime):
    a = runtime
    outsider = Principal(a.e.other, "oidc:unrelated")
    key = "cross-tenant-model-retry"
    app = create_app(
        a.e.db,
        tokens(a, outsider),
        model_retry=ModelRetryStore(a.e.db, a.verifier),
    )
    with TestClient(app, raise_server_exceptions=False) as client:
        response = client.post(
            f"/v1/projects/{a.e.project}/runs/{a.target}/model-retries",
            json=retry_body(a),
            headers={**auth(), "Idempotency-Key": key},
        )
    assert response.status_code == 403
    assert response.json()["code"] == "AUTH-0030"
    validate_contract("ProblemDetails", response.json())
    with psycopg.connect(a.e.owner) as conn:
        assert not conn.execute(
            "SELECT 1 FROM inv.idempotency WHERE key=%s", (key,)
        ).fetchone()


def test_execution_manifest_reports_ready_stale_and_missing_mapping_honestly(runtime):
    a = runtime
    with psycopg.connect(a.e.owner) as conn:
        location = conn.execute(
            """SELECT location_id,version,checksum_sha256,byte_size
            FROM public.data_locations WHERE contribution_id=%s""",
            (a.contribution,),
        ).fetchone()
        conn.execute(
            """INSERT INTO public.data_replicas
            (replica_id,tenant_id,location_id,node_id,contribution_id,state,local_bytes,
             checksum_sha256,verified_at)
            VALUES(%s,%s,%s,%s,%s,'ready',%s,%s,clock_timestamp())""",
            (
                new_id("rep"),
                a.e.tenant,
                location[0],
                a.e.node,
                a.contribution,
                location[3],
                location[2],
            ),
        )

    url = (
        f"/v1/projects/{a.e.project}/models/{a.body['modelId']}"
        f"/versions/{a.body['version']}/execution-manifest"
    )
    direct = ModelExecutionManifestObservation(a.e.db).get(
        a.principal, a.e.project, a.body["modelId"], a.body["version"]
    )
    validate_contract("ModelExecutionManifestObservation", direct)
    app = create_app(a.e.db, tokens(a, a.principal))
    with TestClient(app, raise_server_exceptions=False) as client:
        ready = client.get(url, headers=auth())
        commitment = client.get(url.replace("execution-manifest", "commitment"), headers=auth())
        with psycopg.connect(a.e.owner) as conn:
            conn.execute(
                "UPDATE public.data_replicas SET state='stale' WHERE location_id=%s",
                (location[0],),
            )
        no_ready = client.get(url, headers=auth())
        with psycopg.connect(a.e.owner) as conn:
            conn.execute(
                "UPDATE public.data_replicas SET state='ready' WHERE location_id=%s",
                (location[0],),
            )
            conn.execute(
                "UPDATE public.data_locations SET version=version+1 WHERE location_id=%s",
                (location[0],),
            )
        stale = client.get(url, headers=auth())

        missing = deepcopy(a.body)
        missing["version"] = "missing-map"
        missing_hash = hashlib.sha256(canonical(missing)).hexdigest()
        with psycopg.connect(a.e.owner) as conn:
            conn.execute(
                """INSERT INTO inv.model_manifests
                (tenant_id,project_id,model_id,version,manifest,manifest_sha256,
                 source_run_id,recovery_epoch)
                VALUES(%s,%s,%s,%s,%s,%s,%s,%s)""",
                (
                    a.e.tenant,
                    a.e.project,
                    missing["modelId"],
                    missing["version"],
                    Jsonb(missing),
                    missing_hash,
                    a.run,
                    a.e.epoch,
                ),
            )
        absent_mapping = client.get(
            f"/v1/projects/{a.e.project}/models/{missing['modelId']}"
            f"/versions/{missing['version']}/execution-manifest",
            headers=auth(),
        )
    outsider = Principal(a.e.other, "oidc:unrelated")
    with TestClient(
        create_app(a.e.db, tokens(a, outsider)), raise_server_exceptions=False
    ) as client:
        forbidden = client.get(url, headers=auth())

    assert ready.status_code == 200, ready.json()
    validate_contract("ModelExecutionManifestObservation", ready.json())
    assert ready.json()["shards"] == a.body["shards"]
    assert ready.json()["shardLocations"] == [
        {
            "shardIndex": 0,
            "locationId": location[0],
            "locationVersion": location[1],
            "readyNodes": [a.e.node],
            "materialisable": True,
        }
    ]
    assert ready.json()["materialisable"] is True
    assert ready.json()["executionAuthorized"] is False
    assert ready.json()["licensePolicy"] == a.body["licensePolicy"]
    assert ready.json()["classification"] == a.body["classification"]
    assert commitment.status_code == 200
    validate_contract("ModelCommitObservation", commitment.json())
    assert commitment.json()["currentAvailability"] == "unknown"
    assert no_ready.status_code == 200
    assert no_ready.json()["shardLocations"][0]["readyNodes"] == []
    assert no_ready.json()["shardLocations"][0]["materialisable"] is False
    assert no_ready.json()["materialisable"] is False
    assert stale.status_code == 200
    assert stale.json()["shardLocations"][0]["readyNodes"] == []
    assert stale.json()["shardLocations"][0]["materialisable"] is False
    assert stale.json()["materialisable"] is False
    assert absent_mapping.status_code == 409
    assert absent_mapping.json()["code"] == "MODEL-0001"
    validate_contract("ProblemDetails", absent_mapping.json())
    assert forbidden.status_code == 403
    assert forbidden.json()["code"] == "AUTH-0030"
    validate_contract("ProblemDetails", forbidden.json())
    with psycopg.connect(a.e.owner) as conn:
        assert conn.execute(
            "SELECT has_function_privilege('inv_kernel',"
            "'public.model_location_readiness(text[])','EXECUTE')"
        ).fetchone()[0]
        assert not conn.execute(
            "SELECT has_function_privilege('inv_app',"
            "'public.model_location_readiness(text[])','EXECUTE')"
        ).fetchone()[0]
        assert not conn.execute(
            "SELECT has_table_privilege('inv_kernel','public.data_replicas','SELECT')"
        ).fetchone()[0]
