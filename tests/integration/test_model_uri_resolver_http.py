"""Real-PG operational binding for the project-scoped ``inv://`` model resolver."""

from types import SimpleNamespace
from uuid import uuid4

import psycopg
from psycopg import sql
from psycopg.conninfo import conninfo_to_dict, make_conninfo
from psycopg.errors import InsufficientPrivilege
import pytest
from fastapi.testclient import TestClient
from sqlalchemy.engine import URL

from inv.app import create_app
from inv.business_surface import configured_business
from inv.contracts import validate_contract
from inv.ids import new_id
from test_model_runtime import runtime
from test_model_locality import locality
from test_model_commit import model
from test_storage_commit import sample, storage_subject
from test_approvals import approval

pytestmark = pytest.mark.postgres


def _tokens(principal):
    class Tokens:
        tenant_id = principal.tenant_id

        @staticmethod
        def verify(_value):
            return SimpleNamespace(principal=principal, expires_at="2026-09-22T20:00:00Z")

        @staticmethod
        def _keys():
            return None

    return Tokens()


def _auth():
    return {"Authorization": "Bearer synthetic"}


def test_model_uri_resolution_rechecks_both_roles_and_never_replays_authority(runtime, monkeypatch):
    a = runtime
    role = "inv_model_resolver_" + uuid4().hex[:20]
    password = uuid4().hex
    model_uri = f"inv://models/runtime-model@{a.body['version']}/weights.bin"
    model_version_id = new_id("mdv")
    other_project = new_id("prj")
    with psycopg.connect(a.e.owner) as conn:
        conn.execute(
            sql.SQL("CREATE ROLE {} LOGIN PASSWORD {} NOSUPERUSER NOBYPASSRLS").format(
                sql.Identifier(role), sql.Literal(password)
            )
        )
        conn.execute(sql.SQL("GRANT inv_app TO {}").format(sql.Identifier(role)))
        location = conn.execute(
            "SELECT location_id,version,checksum_sha256,byte_size "
            "FROM public.data_locations WHERE contribution_id=%s",
            (a.contribution,),
        ).fetchone()
        conn.execute(
            "INSERT INTO public.models(model_id,tenant_id,project_id,name) "
            "VALUES(%s,%s,%s,'runtime-model')",
            (a.body["modelId"], a.e.tenant, a.e.project),
        )
        conn.execute(
            """INSERT INTO public.model_versions
            (model_version_id,tenant_id,model_id,version,content_sha256,byte_size,uri)
            VALUES(%s,%s,%s,%s,%s,%s,%s)""",
            (
                model_version_id,
                a.e.tenant,
                a.body["modelId"],
                a.body["version"],
                a.body["contentHash"],
                a.body["totalBytes"],
                model_uri,
            ),
        )
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
        conn.execute(
            "INSERT INTO inv.projects(tenant_id,project_id) VALUES(%s,%s)",
            (a.e.tenant, other_project),
        )

    target = conninfo_to_dict(a.e.owner)
    business_pg = make_conninfo(a.e.owner, user=role, password=password)
    business_url = URL.create(
        "postgresql+psycopg",
        username=role,
        password=password,
        host=target["host"],
        port=int(target["port"]),
        database=target["dbname"],
    ).render_as_string(hide_password=False)
    monkeypatch.setenv("INV_BUSINESS_DSN", business_url)
    tokens = _tokens(a.principal)
    business = None
    try:
        # The production reader is a separate login.  With no tenant GUC its
        # public RLS reads are empty, while direct kernel-table reads are denied.
        with psycopg.connect(business_pg) as conn:
            assert conn.execute("SELECT count(*) FROM public.models").fetchone()[0] == 0
        with psycopg.connect(business_pg) as conn:
            with pytest.raises(InsufficientPrivilege):
                conn.execute("SELECT 1 FROM inv.model_manifests").fetchone()

        business = configured_business(a.e.db, tokens)
        app = create_app(a.e.db, tokens, business=business)
        url = f"/v1/projects/{a.e.project}/models/resolve"
        with TestClient(app, raise_server_exceptions=False) as client:
            ready = client.get(url, params={"uri": model_uri}, headers=_auth())
            missing = client.get(
                url,
                params={"uri": "inv://models/missing@1/weights.bin"},
                headers=_auth(),
            )
            forbidden = client.get(
                f"/v1/projects/{other_project}/models/resolve",
                params={"uri": model_uri},
                headers=_auth(),
            )
            with psycopg.connect(a.e.owner) as conn:
                conn.execute(
                    "UPDATE public.data_replicas SET state='stale' WHERE location_id=%s",
                    (location[0],),
                )
            stale = client.get(url, params={"uri": model_uri}, headers=_auth())
            with psycopg.connect(a.e.owner) as conn:
                conn.execute(
                    "UPDATE public.data_replicas SET state='ready' WHERE location_id=%s",
                    (location[0],),
                )
                conn.execute(
                    "UPDATE public.storage_contributions "
                    "SET status='revoked',revoked_at=now() WHERE contribution_id=%s",
                    (a.contribution,),
                )
            kernel_after_reader_scope_revocation = client.get(
                f"/v1/projects/{a.e.project}/models/{a.body['modelId']}"
                f"/versions/{a.body['version']}/execution-manifest",
                headers=_auth(),
            )
            business_after_reader_scope_revocation = client.get(
                url, params={"uri": model_uri}, headers=_auth()
            )
            with psycopg.connect(a.e.owner) as conn:
                conn.execute(
                    "DELETE FROM public.project_members "
                    "WHERE tenant_id=%s AND project_id=%s AND user_id=%s",
                    (a.e.tenant, a.e.project, a.user),
                )
            replay_after_revocation = client.get(url, params={"uri": model_uri}, headers=_auth())

        assert ready.status_code == 200, ready.text
        validate_contract("ModelExecutionManifestObservation", ready.json())
        assert ready.json()["projectId"] == a.e.project
        assert ready.json()["modelId"] == a.body["modelId"]
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
        assert stale.status_code == 200
        validate_contract("ModelExecutionManifestObservation", stale.json())
        assert stale.json()["shardLocations"][0]["readyNodes"] == []
        assert stale.json()["shardLocations"][0]["materialisable"] is False
        assert stale.json()["materialisable"] is False
        assert kernel_after_reader_scope_revocation.status_code == 200
        assert kernel_after_reader_scope_revocation.json()["shardLocations"][0][
            "readyNodes"
        ] == [a.e.node]
        assert business_after_reader_scope_revocation.status_code == 200
        validate_contract(
            "ModelExecutionManifestObservation",
            business_after_reader_scope_revocation.json(),
        )
        assert business_after_reader_scope_revocation.json()["shardLocations"][0][
            "readyNodes"
        ] == []
        assert business_after_reader_scope_revocation.json()["shardLocations"][0][
            "materialisable"
        ] is False
        assert business_after_reader_scope_revocation.json()["materialisable"] is False
        assert missing.status_code == 404
        assert missing.json()["code"] == "MODEL-0004"
        validate_contract("ProblemDetails", missing.json())
        assert forbidden.status_code == 403
        assert forbidden.json()["code"] == "AUTH-0030"
        validate_contract("ProblemDetails", forbidden.json())
        assert replay_after_revocation.status_code == 403
        assert replay_after_revocation.json()["code"] == "AUTH-0030"
        validate_contract("ProblemDetails", replay_after_revocation.json())
    finally:
        if business is not None:
            business.state.engine.dispose()
        with psycopg.connect(a.e.owner) as conn:
            conn.execute(sql.SQL("DROP ROLE {}").format(sql.Identifier(role)))
