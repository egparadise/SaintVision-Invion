"""Real PostgreSQL evidence for the core-only S04/S08 C1 collector."""

from __future__ import annotations

import datetime as dt
import uuid

import pytest
from sqlalchemy import text

from saintvision.ids import new_id
from tools import collect_s04_s08_operational_evidence as collector


pytestmark = pytest.mark.postgres


def test_real_pg_c1_uses_attempt_time_latest_approval_digest_and_cancel_history(
    owner_engine, database_url, clean_tables
):
    now = dt.datetime.now(dt.timezone.utc)
    tenant = uuid.uuid4()
    user = new_id("user")
    project = new_id("project")
    workspace = new_id("workspace")
    workload = new_id("workload")
    digest = "a" * 64

    with owner_engine.begin() as connection:
        connection.execute(
            text(
                "INSERT INTO tenants(tenant_id,slug,display_name,created_at) "
                "VALUES (:tenant,:slug,'Collector',:now)"
            ),
            {"tenant": tenant, "slug": "collector-" + uuid.uuid4().hex[:12], "now": now},
        )
        connection.execute(
            text(
                "INSERT INTO users(user_id,tenant_id,external_subject,display_name,status,created_at,updated_at,version) "
                "VALUES (:user,:tenant,'collector-subject','Collector','active',:now,:now,1)"
            ),
            {"user": user, "tenant": tenant, "now": now},
        )
        connection.execute(
            text(
                "INSERT INTO projects(project_id,tenant_id,code,display_name,status,created_at,version) "
                "VALUES (:project,:tenant,:code,'Collector','active',:now,1)"
            ),
            {
                "project": project,
                "tenant": tenant,
                "code": "c-" + uuid.uuid4().hex[:12],
                "now": now,
            },
        )
        connection.execute(
            text(
                "INSERT INTO workspaces(workspace_id,tenant_id,project_id,name,status,created_by_user_id,created_at,version) "
                "VALUES (:workspace,:tenant,:project,'collector','ready',:user,:now,1)"
            ),
            {
                "workspace": workspace,
                "tenant": tenant,
                "project": project,
                "user": user,
                "now": now,
            },
        )
        connection.execute(
            text(
                "INSERT INTO workloads(workload_id,tenant_id,project_id,kind,objective,spec,spec_sha256,contract_version,created_by_user_id,created_at,version) "
                "VALUES (:workload,:tenant,:project,'batch','collector','{}'::jsonb,:digest,'1.0.0',:user,:now,1)"
            ),
            {
                "workload": workload,
                "tenant": tenant,
                "project": project,
                "digest": digest,
                "user": user,
                "now": now,
            },
        )

        def run_case(name: str, *, approval: str | None, cancel: bool = False, later_reject=False):
            run_id = new_id("run")
            connection.execute(
                text(
                    "INSERT INTO runs(run_id,tenant_id,workload_id,workspace_id,state,requested_by_user_id,attempt_count,retry_budget,created_at,version) "
                    "VALUES (:run,:tenant,:workload,:workspace,'running',:user,1,2,:created,1)"
                ),
                {
                    "run": run_id,
                    "tenant": tenant,
                    "workload": workload,
                    "workspace": workspace,
                    "user": user,
                    "created": now - dt.timedelta(minutes=2),
                },
            )
            if approval is not None:
                approval_digest = "b" * 64 if approval == "mismatch" else digest
                expiry = (
                    now - dt.timedelta(seconds=1)
                    if approval == "expired"
                    else now + dt.timedelta(minutes=5)
                )
                connection.execute(
                    text(
                        "INSERT INTO approvals(approval_id,tenant_id,run_id,subject_sha256,decision,risk_level,scope,decided_by_user_id,decided_at,expires_at) "
                        "VALUES (:approval,:tenant,:run,:digest,'approved',1,'{}'::jsonb,:user,:decided,:expires)"
                    ),
                    {
                        "approval": new_id("approval"),
                        "tenant": tenant,
                        "run": run_id,
                        "digest": approval_digest,
                        "user": user,
                        "decided": now - dt.timedelta(minutes=1),
                        "expires": expiry,
                    },
                )
            if later_reject:
                connection.execute(
                    text(
                        "INSERT INTO approvals(approval_id,tenant_id,run_id,subject_sha256,decision,risk_level,scope,decided_by_user_id,decided_at,expires_at) "
                        "VALUES (:approval,:tenant,:run,:digest,'rejected',1,'{}'::jsonb,:user,:decided,:expires)"
                    ),
                    {
                        "approval": new_id("approval"),
                        "tenant": tenant,
                        "run": run_id,
                        "digest": digest,
                        "user": user,
                        "decided": now - dt.timedelta(seconds=10),
                        "expires": now + dt.timedelta(minutes=5),
                    },
                )
            if cancel:
                connection.execute(
                    text(
                        "INSERT INTO audit_events(event_id,occurred_at,tenant_id,actor_type,actor_id,action,outcome,target_type,target_id,detail) "
                        "VALUES (:event,:occurred,:tenant,'user',:user,'run.cancel.requested','allow','run',:run,'{}'::jsonb)"
                    ),
                    {
                        "event": new_id("audit_event"),
                        "occurred": now - dt.timedelta(seconds=5),
                        "tenant": tenant,
                        "user": user,
                        "run": run_id,
                    },
                )
            connection.execute(
                text(
                    "INSERT INTO run_attempts(attempt_id,tenant_id,run_id,attempt_number,placement_snapshot,started_at) "
                    "VALUES (:attempt,:tenant,:run,1,'{}'::jsonb,:started)"
                ),
                {
                    "attempt": new_id("attempt"),
                    "tenant": tenant,
                    "run": run_id,
                    "started": now,
                },
            )

        run_case("valid", approval="valid")
        run_case("latest-reject-is-not-a-false-violation", approval="valid", later_reject=True)
        run_case("missing", approval=None)
        run_case("expired", approval="expired")
        run_case("mismatch", approval="mismatch")
        run_case("cancelled", approval="valid", cancel=True)

    measured = collector.collect_database(database_url)
    assert measured["c1"] == {
        "attempt_count": 6,
        "valid_count": 2,
        "violation_count": 4,
        "no_approved_before_attempt": 1,
        "approval_expired": 1,
        "approval_digest_mismatch": 1,
        "cancelled_before_attempt": 1,
    }
    observation = collector.evaluate_c1_summary(measured["c1"])
    assert observation["status"] == "MEASURED_FAIL"
    assert measured["identity"]["systemIdentifierObserved"] is True
    assert measured["identity"]["databaseIdentitySha256"]
    assert measured["sourceStartedAt"] <= measured["sourceFinishedAt"]
