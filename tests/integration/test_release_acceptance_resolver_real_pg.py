"""Migration 0058 and authoritative release Evidence resolution on PostgreSQL 16."""

from __future__ import annotations

import datetime as dt
import json
import uuid

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import text
from sqlalchemy.exc import DBAPIError, IntegrityError, ProgrammingError

from saintvision.api.app import create_app
from saintvision.config import Settings
from saintvision.db.session import tenant_scope
from saintvision.identity.principal import Principal, StaticPrincipalVerifier
from saintvision.ids import new_id
from saintvision.services import evidence as evidence_service
from saintvision.services import release_acceptance as acceptance
from saintvision.services import release_acceptance_policy as policy
from saintvision.services import release_acceptance_resolver as resolver

pytestmark = pytest.mark.postgres

UTC = dt.timezone.utc
NOW = dt.datetime(2026, 10, 1, 12, 34, 56, 123456, tzinfo=UTC)


def test_0058_downgrade_forward_and_partition_column_propagation(
    owner_engine, database_url, clean_tables, monkeypatch
):
    from alembic import command
    from alembic.config import Config

    config = Config("alembic.ini")
    config.set_main_option("script_location", "migrations")
    monkeypatch.setenv("INV_DATABASE_URL", database_url)
    monkeypatch.setenv("INV_MIGRATION_DSN", database_url)
    command.downgrade(config, "0057_release_acceptance_quorum")
    command.upgrade(config, "head")

    with owner_engine.begin() as connection:
        assert connection.execute(text("SELECT version_num FROM alembic_version")).scalar_one() == (
            "0060_build_execution_admissions"
        )
        columns = connection.execute(
            text(
                "SELECT count(*) FROM information_schema.columns "
                "WHERE column_name='envelope_sha256' AND "
                "(table_name='evidence_envelopes' OR table_name LIKE 'evidence_envelopes_%')"
            )
        ).scalar_one()
        partitions = connection.execute(
            text(
                "SELECT count(*) FROM pg_inherits " "WHERE inhparent='evidence_envelopes'::regclass"
            )
        ).scalar_one()
        assert columns == partitions + 1


@pytest.fixture
def resolved_rows(owner_engine, app_sessionmaker, clean_tables):
    tenant = uuid.uuid4()
    other_tenant = uuid.uuid4()
    user = new_id("user")
    project = new_id("project")
    other_project = new_id("project")
    workspace = new_id("workspace")
    workload = new_id("workload")
    run = new_id("run")
    release = new_id("release")
    with owner_engine.begin() as connection:
        connection.execute(
            text(
                "INSERT INTO tenants(tenant_id,slug,display_name,created_at,version) "
                "VALUES(:t,:s,'Resolver',now(),1),(:o,:os,'Other',now(),1)"
            ),
            {
                "t": tenant,
                "s": f"resolver-{str(tenant)[:8]}",
                "o": other_tenant,
                "os": f"other-{str(other_tenant)[:8]}",
            },
        )
        connection.execute(
            text(
                "INSERT INTO users(user_id,tenant_id,external_subject,display_name,status,"
                "created_at,updated_at,version) VALUES(:u,:t,'oidc:resolver','Resolver',"
                "'active',now(),now(),1)"
            ),
            {"u": user, "t": tenant},
        )
        connection.execute(
            text(
                "INSERT INTO inv.business_admin_grants(tenant_id,user_id,permission,enabled) "
                "VALUES(:t,:u,'releases.accept',true)"
            ),
            {"t": tenant, "u": user},
        )
        connection.execute(
            text(
                "INSERT INTO projects(project_id,tenant_id,code,display_name,status,created_at,version) "
                "VALUES(:p,:t,'resolver','Resolver','active',now(),1),"
                "(:other_p,:t,'resolver-other','Resolver Other','active',now(),1)"
            ),
            {"p": project, "other_p": other_project, "t": tenant},
        )
        connection.execute(
            text(
                "INSERT INTO workspaces(workspace_id,tenant_id,project_id,name,status,"
                "created_by_user_id,created_at,version) "
                "VALUES(:w,:t,:p,'resolver','ready',:u,now(),1)"
            ),
            {"w": workspace, "t": tenant, "p": project, "u": user},
        )
        connection.execute(
            text(
                "INSERT INTO workloads(workload_id,tenant_id,project_id,kind,objective,spec,"
                "spec_sha256,contract_version,created_by_user_id,created_at,version) "
                "VALUES(:wl,:t,:p,'batch','resolve','{}',:sha,'1.0.0',:u,now(),1)"
            ),
            {"wl": workload, "t": tenant, "p": project, "u": user, "sha": "1" * 64},
        )
        connection.execute(
            text(
                "INSERT INTO runs(run_id,tenant_id,workload_id,workspace_id,state,"
                "requested_by_user_id,attempt_count,retry_budget,created_at,version) "
                "VALUES(:r,:t,:wl,:w,'draft',:u,0,2,now(),1)"
            ),
            {"r": run, "t": tenant, "wl": workload, "w": workspace, "u": user},
        )
        connection.execute(
            text(
                "INSERT INTO release_manifests(release_id,tenant_id,version,components,"
                "component_count,manifest_sha256,created_by_user_id,created_at,policy_version,"
                "policy_registry_sha256,target_registry_version,target_registry_git_blob_sha,"
                "target_registry_file_sha256) VALUES(:r,:t,'R194',cast(:components AS jsonb),"
                "1,:manifest,:u,now(),1,:policy,1,:blob,:file)"
            ),
            {
                "r": release,
                "t": tenant,
                "components": json.dumps(
                    [{"name": "control-plane", "kind": "service", "digest": "2" * 64}]
                ),
                "manifest": "3" * 64,
                "u": user,
                "policy": policy.digest_of(),
                "blob": resolver.REGISTRY_GIT_BLOB_SHA,
                "file": resolver.REGISTRY_FILE_SHA256,
            },
        )

    with app_sessionmaker() as session:
        with session.begin(), tenant_scope(session, tenant):
            evidence_id = evidence_service.record_evidence(
                session,
                tenant_id=tenant,
                run_id=run,
                action="release.acceptance.measure",
                actor_type="system",
                actor_id="hosted-core",
                input_schema="ReleaseAcceptanceMeasurement@1",
                input_payload={"releaseId": release},
                result="succeeded",
                now=NOW,
                telemetry={"b": 2, "a": 1},
                component_versions={"control-plane": "card-194"},
            )
            forged_evidence_id = new_id("evidence")
            forged_at = NOW + dt.timedelta(microseconds=1)
            forged_digest = "f" * 64
            session.execute(
                text(
                    "INSERT INTO evidence_envelopes("
                    "evidence_id,recorded_at,tenant_id,run_id,step_id,trace_id,actor_type,"
                    "actor_id,action,policy_id,effect,approval_id,input_schema,input_sha256,"
                    "output_schema,output_ref,result,telemetry,component_versions,"
                    "envelope_sha256) VALUES("
                    ":e,:at,:t,:r,NULL,NULL,'system','hosted-core',"
                    "'release.acceptance.measure',NULL,NULL,NULL,"
                    "'ReleaseAcceptanceMeasurement@1',:input,NULL,NULL,'succeeded',"
                    "cast(:telemetry AS jsonb),cast(:components AS jsonb),:forged)"
                ),
                {
                    "e": forged_evidence_id,
                    "at": forged_at,
                    "t": tenant,
                    "r": run,
                    "input": "4" * 64,
                    "telemetry": json.dumps({"a": 1, "b": 2}),
                    "components": json.dumps({"control-plane": "card-194"}),
                    "forged": forged_digest,
                },
            )
    with owner_engine.begin() as connection:
        connection.execute(text("SET LOCAL TimeZone='Asia/Seoul'"))
        digest = connection.execute(
            text(
                "SELECT envelope_sha256, public.evidence_envelope_digest_v1(e) "
                "FROM evidence_envelopes e WHERE evidence_id=:e AND recorded_at=:at"
            ),
            {"e": evidence_id, "at": NOW},
        ).one()
        assert digest[0] == digest[1]
        assert digest[0] != evidence_service.canonical_sha256({"releaseId": release})
        forged_stored = connection.execute(
            text("SELECT envelope_sha256 FROM evidence_envelopes WHERE evidence_id=:e"),
            {"e": forged_evidence_id},
        ).scalar_one()
        assert forged_stored != forged_digest

    with app_sessionmaker() as session:
        with session.begin(), tenant_scope(session, tenant):
            resolver.bind_evidence(
                session,
                tenant_id=tenant,
                release_id=release,
                evidence_id=evidence_id,
                observed_at=NOW,
                now=NOW,
            )
    return {
        "tenant": tenant,
        "other": other_tenant,
        "release": release,
        "user": user,
        "evidence": evidence_id,
        "digest": digest[0],
        "forged_evidence": forged_evidence_id,
        "forged_at": forged_at,
        "forged_digest": forged_stored,
        "other_project": other_project,
    }


def test_inv_app_insert_trigger_overwrites_digest_and_owner_helper_is_not_executable(
    app_sessionmaker, owner_engine, resolved_rows
):
    # The normal app INSERT already proved the trigger path. Direct helper execution is
    # separately refused to the application role; the transaction is expected to abort.
    with pytest.raises(ProgrammingError):
        with app_sessionmaker() as session:
            with session.begin(), tenant_scope(session, resolved_rows["tenant"]):
                session.execute(
                    text(
                        "SELECT public.evidence_envelope_digest_v1(e) "
                        "FROM evidence_envelopes e WHERE evidence_id=:e"
                    ),
                    {"e": resolved_rows["evidence"]},
                ).scalar_one()

    with owner_engine.begin() as connection:
        stored = connection.execute(
            text("SELECT envelope_sha256 FROM evidence_envelopes WHERE evidence_id=:e"),
            {"e": resolved_rows["evidence"]},
        ).scalar_one()
        assert stored == resolved_rows["digest"]


@pytest.mark.parametrize("damage", ["project", "digest"])
def test_binding_trigger_rejects_caller_forged_scope_or_digest(
    app_sessionmaker, resolved_rows, damage
):
    values = {
        "tenant": resolved_rows["tenant"],
        "release": resolved_rows["release"],
        "evidence": resolved_rows["forged_evidence"],
        "at": resolved_rows["forged_at"],
        "project": resolved_rows["other_project"] if damage == "project" else None,
        "digest": "0" * 64 if damage == "digest" else resolved_rows["forged_digest"],
    }
    # The correct project is intentionally recovered only for the digest mutation; the
    # caller never gets to make either value authoritative.
    with app_sessionmaker() as session:
        with session.begin(), tenant_scope(session, resolved_rows["tenant"]):
            if values["project"] is None:
                values["project"] = session.execute(
                    text(
                        "SELECT w.project_id FROM evidence_envelopes e "
                        "JOIN runs r ON r.tenant_id=e.tenant_id AND r.run_id=e.run_id "
                        "JOIN workloads w ON w.tenant_id=r.tenant_id "
                        "AND w.workload_id=r.workload_id "
                        "WHERE e.evidence_id=:e AND e.recorded_at=:at"
                    ),
                    {"e": values["evidence"], "at": values["at"]},
                ).scalar_one()
            with pytest.raises(IntegrityError):
                with session.begin_nested():
                    session.execute(
                        text(
                            "INSERT INTO release_evidence_bindings("
                            "tenant_id,release_id,evidence_id,evidence_recorded_at,project_id,"
                            "envelope_sha256,bound_at) VALUES("
                            ":tenant,:release,:evidence,:at,:project,:digest,:at)"
                        ),
                        values,
                    )


def test_inv_app_cannot_repin_a_release_target_registry(app_sessionmaker, resolved_rows):
    with pytest.raises(DBAPIError):
        with app_sessionmaker() as session:
            with session.begin(), tenant_scope(session, resolved_rows["tenant"]):
                session.execute(
                    text(
                        "UPDATE release_manifests SET target_registry_version=2 "
                        "WHERE tenant_id=:tenant AND release_id=:release"
                    ),
                    {
                        "tenant": resolved_rows["tenant"],
                        "release": resolved_rows["release"],
                    },
                )


def test_inv_app_cannot_mutate_an_append_only_evidence_binding(app_sessionmaker, resolved_rows):
    with pytest.raises(DBAPIError):
        with app_sessionmaker() as session:
            with session.begin(), tenant_scope(session, resolved_rows["tenant"]):
                session.execute(
                    text(
                        "UPDATE release_evidence_bindings SET envelope_sha256=:digest "
                        "WHERE tenant_id=:tenant AND release_id=:release"
                    ),
                    {
                        "digest": "0" * 64,
                        "tenant": resolved_rows["tenant"],
                        "release": resolved_rows["release"],
                    },
                )


def test_release_without_a_target_registry_pin_is_a_prerequisite_failure(
    owner_engine, app_sessionmaker, resolved_rows
):
    legacy_release = new_id("release")
    with owner_engine.begin() as connection:
        connection.execute(
            text(
                "INSERT INTO release_manifests(release_id,tenant_id,version,components,"
                "component_count,manifest_sha256,created_by_user_id,created_at,policy_version,"
                "policy_registry_sha256) VALUES(:release,:tenant,'legacy-card194',"
                "cast(:components AS jsonb),1,:manifest,:user,now(),1,:policy)"
            ),
            {
                "release": legacy_release,
                "tenant": resolved_rows["tenant"],
                "components": json.dumps(
                    [{"name": "legacy", "kind": "service", "digest": "7" * 64}]
                ),
                "manifest": "8" * 64,
                "user": resolved_rows["user"],
                "policy": policy.digest_of(),
            },
        )
    target = resolver.load_target_registry().document.targets[0]
    with app_sessionmaker() as session:
        with session.begin(), tenant_scope(session, resolved_rows["tenant"]):
            with pytest.raises(acceptance.PrerequisitesUnavailable):
                resolver.RESOLVER.resolve(
                    session,
                    tenant_id=resolved_rows["tenant"],
                    release_id=legacy_release,
                    target_refs=[
                        {"targetId": target.target_id, "targetSha256": target.target_sha256}
                    ],
                    measurement_refs=[
                        {
                            "evidenceId": resolved_rows["evidence"],
                            "evidenceSha256": resolved_rows["digest"],
                            "observedAt": NOW,
                        }
                    ],
                )


def test_exact_resolve_discovery_and_cross_scope_fail_closed(app_sessionmaker, resolved_rows):
    loaded = resolver.load_target_registry().document.targets[0]
    with app_sessionmaker() as session:
        with session.begin(), tenant_scope(session, resolved_rows["tenant"]):
            answer = resolver.RESOLVER.resolve(
                session,
                tenant_id=resolved_rows["tenant"],
                release_id=resolved_rows["release"],
                target_refs=[{"targetId": loaded.target_id, "targetSha256": loaded.target_sha256}],
                measurement_refs=[
                    {
                        "evidenceId": resolved_rows["evidence"],
                        "evidenceSha256": resolved_rows["digest"],
                        "observedAt": NOW,
                    }
                ],
            )
            assert answer.all_resolved is True
            assert answer.scope_verified is True
            page = resolver.discovery_page(
                session,
                tenant_id=resolved_rows["tenant"],
                release_id=resolved_rows["release"],
                acceptance_id_ref="AC-12",
                limit=100,
                cursor=None,
            )
            assert len(page.items) == 1
            assert page.items[0].evidence_sha256 == resolved_rows["digest"]

            with pytest.raises(acceptance.ReferencesUnresolvable):
                resolver.RESOLVER.resolve(
                    session,
                    tenant_id=resolved_rows["tenant"],
                    release_id=resolved_rows["release"],
                    target_refs=[
                        {"targetId": loaded.target_id, "targetSha256": loaded.target_sha256}
                    ],
                    measurement_refs=[
                        {
                            "evidenceId": resolved_rows["evidence"],
                            "evidenceSha256": "0" * 64,
                            "observedAt": NOW,
                        }
                    ],
                )

    with app_sessionmaker() as session:
        with session.begin(), tenant_scope(session, resolved_rows["other"]):
            with pytest.raises(acceptance.ReferenceNotFound):
                resolver.RESOLVER.resolve(
                    session,
                    tenant_id=resolved_rows["other"],
                    release_id=resolved_rows["release"],
                    target_refs=[
                        {"targetId": loaded.target_id, "targetSha256": loaded.target_sha256}
                    ],
                    measurement_refs=[
                        {
                            "evidenceId": resolved_rows["evidence"],
                            "evidenceSha256": resolved_rows["digest"],
                            "observedAt": NOW,
                        }
                    ],
                )


def test_legacy_null_digest_is_not_relabelled_as_input_digest(
    owner_engine, app_sessionmaker, resolved_rows
):
    with owner_engine.begin() as connection:
        connection.execute(
            text("UPDATE evidence_envelopes SET envelope_sha256=NULL WHERE evidence_id=:e"),
            {"e": resolved_rows["evidence"]},
        )
    loaded = resolver.load_target_registry().document.targets[0]
    with app_sessionmaker() as session:
        with session.begin(), tenant_scope(session, resolved_rows["tenant"]):
            with pytest.raises(acceptance.PrerequisitesUnavailable):
                resolver.RESOLVER.resolve(
                    session,
                    tenant_id=resolved_rows["tenant"],
                    release_id=resolved_rows["release"],
                    target_refs=[
                        {"targetId": loaded.target_id, "targetSha256": loaded.target_sha256}
                    ],
                    measurement_refs=[
                        {
                            "evidenceId": resolved_rows["evidence"],
                            "evidenceSha256": resolved_rows["digest"],
                            "observedAt": NOW,
                        }
                    ],
                )


def test_discovery_route_requires_and_returns_only_fresh_server_bound_identity(
    app_engine, owner_engine, resolved_rows
):
    principal = Principal(
        user_id=resolved_rows["user"],
        tenant_id=resolved_rows["tenant"],
        external_subject="oidc:resolver",
        verified_fresh_auth_claims=True,
        auth_time=int(NOW.timestamp()) - 30,
        amr=frozenset({"mfa"}),
        verified_token_issuer="https://idp.example/realms/inv",
        verified_token_client_id="portal",
        verified_token_expires_at=int(NOW.timestamp()) + 600,
    )
    app = create_app(
        engine=app_engine,
        settings=Settings(database_url="test-only"),
        verifier=StaticPrincipalVerifier({"token": principal}, allow_outside_dev=True),
        clock=lambda: NOW,
        check_partitions_on_startup=False,
    )
    client = TestClient(app, raise_server_exceptions=False)
    response = client.get(
        f"/v1/release-manifests/{resolved_rows['release']}/acceptance-evidence",
        params={"acceptanceIdRef": "AC-12"},
        headers={"Authorization": "Bearer token"},
    )
    assert response.status_code == 200, response.text
    body = response.json()
    assert body["scopeVerified"] is True
    assert body["items"] == [
        {
            "evidenceId": resolved_rows["evidence"],
            "evidenceSha256": resolved_rows["digest"],
            "observedAt": "2026-10-01T12:34:56.123456Z",
        }
    ]
    assert "projectId" not in json.dumps(body)
    assert "telemetry" not in json.dumps(body)

    with owner_engine.begin() as connection:
        connection.execute(
            text(
                "DELETE FROM release_evidence_bindings "
                "WHERE tenant_id=:tenant AND release_id=:release"
            ),
            {
                "tenant": resolved_rows["tenant"],
                "release": resolved_rows["release"],
            },
        )
    unavailable = client.get(
        f"/v1/release-manifests/{resolved_rows['release']}/acceptance-evidence",
        params={"acceptanceIdRef": "AC-12"},
        headers={"Authorization": "Bearer token"},
    )
    assert unavailable.status_code == 503, unavailable.text
    assert unavailable.json()["code"] == "SYS-0003"
