"""Verify both published heads upgrade in newly allocated disposable databases."""

import os
import argparse
from pathlib import Path
import subprocess
import sys
from uuid import uuid4
import psycopg
from psycopg import sql
from psycopg.conninfo import conninfo_to_dict, make_conninfo
from sqlalchemy.engine import URL


def main():
    admin = os.environ.get("INV_TEST_ADMIN_DSN")
    if not admin:
        print("Migration validation not run: INV_TEST_ADMIN_DSN is absent; disposable PostgreSQL is required.", file=sys.stderr)
        return 2
    root = Path(__file__).resolve().parents[1]
    # Both paths, because this runs as a standalone script: pytest supplies
    # them from pyproject, and the subprocess it launches inherits neither. The
    # missing one failed the ninth prior on every run, and the credential-safe
    # diagnostic suppression turned a plain ModuleNotFoundError into
    # "migration validation failed" — which reads as a broken migration.
    sys.path.insert(0, str(root / "tools"))
    sys.path.insert(0, str(root / "src"))
    sys.path.insert(0, str(root / "services/control-plane/src"))
    from migration_graph import chain

    expected_head = chain()[-1].revision
    priors = (
        "0018_workspace_resume",
        "0010_canonical_resource_units",
        "0019_workspace_api_integration",
        "0020_shard_recovery",
        "0021_business_kernel",
        "0022_node_containment",
        "0023_containment_approvals",
        "0024_workspace_bridge",
        "0025_workspace_start",
        "0025_workspace_tool_choice",
        "0026_subject_kernel_link",
        "0027_business_api_guards",
        "0028_result_readiness_merge",
        "0028_subject_kernel_link",
        "0029_run_outputs",
        "0030_provisioning_integrity",
        "0030_apply_resource_offer",
        "0031_resource_offer_integrity",
        "0031_workspace_input_state",
        "0032_workspace_readiness_merge",
        "0033_workspace_bridge_merge",
        "0034_terminal_frame_intents",
        "0035_credential_registry",
        "0036_recovery_target_outcome",
        "0037_storage_sample_commit",
        "0038_approval_review_snapshot",
        "0039_model_manifest",
        "0040_model_run_input",
        "0041_model_runtime_input",
        "0043_replica_retention",
    )
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--from-revision", choices=priors, help="Test one published starting revision; default tests all")
    args = parser.parse_args()
    for prior in ((args.from_revision,) if args.from_revision else priors):
        name = "inv_upgrade_test_" + uuid4().hex
        with psycopg.connect(admin, autocommit=True) as conn:
            conn.execute(sql.SQL("CREATE DATABASE {}").format(sql.Identifier(name)))
        try:
            sentinel = uuid4()
            preserved_workspace = None
            preserved_drill = None
            preserved_lease = None
            info = conninfo_to_dict(admin)
            url = URL.create(
                "postgresql+psycopg",
                username=info.get("user"),
                password=info.get("password"),
                host=info.get("host"),
                port=int(info.get("port", 5432)),
                database=name,
            )
            env = {**os.environ, "INV_MIGRATION_DSN": url.render_as_string(hide_password=False)}
            for target in (prior, "head", "head"):
                result = subprocess.run(
                    [sys.executable, "-m", "alembic", "upgrade", target],
                    cwd=root,
                    env=env,
                    capture_output=True,
                )
                if result.returncode:
                    raise RuntimeError("Migration path failed: " + prior + " -> " + target)
                if target == prior and prior in {"0037_storage_sample_commit", "0038_approval_review_snapshot", "0039_model_manifest", "0040_model_run_input", "0041_model_runtime_input"}:
                    from inv.ids import new_id as kernel_id
                    lease_id = kernel_id('lse')
                    project, node, resource, run_id = (kernel_id(p) for p in ('prj','nod','res','run'))
                    epoch = uuid4()
                    with psycopg.connect(make_conninfo(admin, dbname=name)) as conn:
                        conn.execute("INSERT INTO inv.control_epoch(singleton,epoch) VALUES(true,%s)", (epoch,))
                        conn.execute("INSERT INTO inv.tenants VALUES(%s,'lease-preservation')", (sentinel,))
                        conn.execute("INSERT INTO inv.projects VALUES(%s,%s)", (sentinel,project))
                        conn.execute("INSERT INTO inv.nodes(tenant_id,node_id,status,recovery_epoch) VALUES(%s,%s,'online',%s)", (sentinel,node,epoch))
                        conn.execute("INSERT INTO inv.resources VALUES(%s,%s,%s,'cpu',10,10)", (sentinel,resource,node))
                        conn.execute("INSERT INTO inv.runs(tenant_id,project_id,run_id) VALUES(%s,%s,%s)", (sentinel,project,run_id))
                        for state in ('validated','planned'):
                            conn.execute("UPDATE inv.runs SET state=%s,version=version+1 WHERE run_id=%s", (state,run_id))
                        conn.execute("""INSERT INTO inv.resource_leases(tenant_id,project_id,run_id,resource_id,lease_id,amount,recovery_epoch,expires_at)
                            VALUES(%s,%s,%s,%s,%s,1,%s,clock_timestamp()+interval '300 seconds')""", (sentinel,project,run_id,resource,lease_id,epoch))
                        preserved_lease = conn.execute("SELECT row_to_json(l) FROM inv.resource_leases l WHERE lease_id=%s", (lease_id,)).fetchone()[0]
                        preserved_sequence = conn.execute("SELECT last_value FROM inv.fencing_token_seq").fetchone()[0]
                if target == prior and prior == "0035_credential_registry":
                    from saintvision.ids import new_id
                    user, preserved_drill = new_id('user'), new_id('drill')
                    with psycopg.connect(make_conninfo(admin, dbname=name)) as conn:
                        conn.execute("INSERT INTO public.tenants(tenant_id,slug,display_name) VALUES(%s,%s,'legacy claim')", (sentinel,'upgrade-'+sentinel.hex))
                        conn.execute("INSERT INTO public.users(tenant_id,user_id,external_subject,display_name) VALUES(%s,%s,'synthetic','legacy operator')", (sentinel,user))
                        conn.execute("""INSERT INTO public.recovery_drills
                            (drill_id,tenant_id,scope,outcome,measured_rpo_seconds,measured_rto_seconds,target_rpo_seconds,target_rto_seconds,met_targets,fencing_verified,integrity_verified,performed_by_user_id,performed_at,notes)
                            VALUES(%s,%s,'database','failed',1,1,900,3600,true,false,false,%s,now(),'{}')""", (preserved_drill,sentinel,user))
                if target == prior and prior in {"0023_containment_approvals", "0025_workspace_start", "0025_workspace_tool_choice"}:
                    with psycopg.connect(make_conninfo(admin, dbname=name)) as conn:
                        conn.execute("INSERT INTO public.tenants(tenant_id,slug,display_name) VALUES(%s,%s,'preserve-me')",
                                     (sentinel, 'upgrade-'+sentinel.hex))
                        if prior == "0025_workspace_tool_choice":
                            from saintvision.ids import new_id
                            user, project, preserved_workspace = new_id('user'), new_id('project'), new_id('workspace')
                            conn.execute("INSERT INTO public.users(tenant_id,user_id,external_subject,display_name) VALUES(%s,%s,'synthetic','preserve')",(sentinel,user))
                            conn.execute("INSERT INTO public.projects(tenant_id,project_id,code,display_name) VALUES(%s,%s,'preserve','preserve')",(sentinel,project))
                            conn.execute("INSERT INTO public.workspaces(tenant_id,project_id,workspace_id,name,created_by_user_id,tool_name) VALUES(%s,%s,%s,'preserve',%s,'codex-cli')",(sentinel,project,preserved_workspace,user))
            with psycopg.connect(make_conninfo(admin, dbname=name)) as conn:
                # Derived, not pinned. A literal head here goes stale the
                # moment anyone adds a revision — which is what a tool that
                # exists to prove upgrades work should be least able to do —
                # and the failure reads as a broken migration path rather than
                # a stale expectation.
                assert conn.execute("SELECT version_num FROM alembic_version").fetchall() == [
                    (expected_head,)
                ]
                assert conn.execute(
                    "SELECT rolsuper,rolcanlogin,rolbypassrls FROM pg_roles WHERE rolname='inv_kernel'"
                ).fetchone() == (False, False, False)
                assert conn.execute(
                    "SELECT has_column_privilege('inv_kernel','inv.control_epoch','epoch','UPDATE')"
                ).fetchone() == (False,)
                assert conn.execute(
                    "SELECT has_column_privilege('inv_kernel','inv.project_grants','enabled','UPDATE')"
                ).fetchone() == (False,)
                assert conn.execute("""SELECT
                    has_table_privilege('inv_app','inv.business_admin_grants','INSERT'),
                    has_table_privilege('inv_app','inv.business_admin_grants','SELECT'),
                    has_table_privilege('inv_kernel','inv.business_admin_grants','UPDATE')""").fetchone() == (False,False,False)
                if prior in {"0023_containment_approvals", "0025_workspace_start", "0025_workspace_tool_choice"}:
                    assert conn.execute("SELECT display_name FROM public.tenants WHERE tenant_id=%s",(sentinel,)).fetchone()==('preserve-me',)
                if preserved_drill:
                    assert conn.execute("SELECT outcome,met_targets FROM public.recovery_drills WHERE drill_id=%s", (preserved_drill,)).fetchone() == ('failed',True)
                    assert conn.execute("SELECT convalidated FROM pg_constraint WHERE conname='ck_recovery_drills_met_targets_requires_passed'").fetchone() == (False,)
                    try:
                        with conn.transaction():
                            conn.execute("UPDATE public.recovery_drills SET met_targets=true WHERE drill_id=%s", (preserved_drill,))
                    except psycopg.errors.CheckViolation:
                        pass
                    else:
                        raise AssertionError('New writes must enforce outcome without rewriting historic claims')
                if preserved_lease:
                    assert conn.execute("SELECT row_to_json(l) FROM inv.resource_leases l WHERE lease_id=%s", (lease_id,)).fetchone()[0] == preserved_lease
                    assert conn.execute("SELECT last_value FROM inv.fencing_token_seq").fetchone()[0] == preserved_sequence
                if preserved_workspace:
                    assert conn.execute("SELECT tool_name FROM public.workspaces WHERE workspace_id=%s",(preserved_workspace,)).fetchone()==('codex-cli',)
            from check_definer_functions import audit

            findings = audit(make_conninfo(admin, dbname=name))
            assert findings and not any(f["problems"] for f in findings), (
                "Applied privileged function catalogue differs from policy"
            )
            print("PASS: " + prior + " -> integrated head, replay, restricted runtime grants, privileged function policy")
        finally:
            assert name.startswith("inv_upgrade_test_") and len(name) == 49
            with psycopg.connect(admin, autocommit=True) as conn:
                conn.execute(sql.SQL("DROP DATABASE {} WITH (FORCE)").format(sql.Identifier(name)))


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except Exception:
        raise SystemExit(
            "Disposable migration validation failed; credential-bearing diagnostics suppressed"
        ) from None
