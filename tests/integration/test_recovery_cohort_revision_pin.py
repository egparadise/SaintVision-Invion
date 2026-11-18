"""The read-only collector observes only the exact unified Alembic head (0067).

Every other database revision, including 0068_first_workspace_intent, fails closed
with DATABASE_REVISION_UNKNOWN before any membership, channel or resource row is read.
"""
import sys
from pathlib import Path
from uuid import uuid4

import psycopg
from psycopg import sql
import pytest

sys.path.insert(0,str(Path(__file__).parents[2]/"tools/recovery_preflight"))
import cp
from common import Hold, SCHEMA

pytestmark=pytest.mark.postgres

FOREIGN_REVISIONS=("0068_first_workspace_intent","0066_tenant_registry_revoke","0067_audit_reader_revoke_x")


@pytest.fixture
def reader(env):
    """A bound reader that passes every check ordered before the revision check."""
    with psycopg.connect(env.owner,autocommit=True) as owner:
        role_oid,db_name,db_oid=owner.execute("""SELECT r.oid::text,db.datname,db.oid::text FROM pg_roles r,pg_database db
            WHERE r.rolname=%s AND db.datname=current_database()""",(env.runtime_role,)).fetchone()
        cluster_id,=owner.execute("SELECT system_identifier::text FROM pg_control_system()").fetchone()
        prior_control,=owner.execute("SELECT has_function_privilege(%s,'pg_catalog.pg_control_system()','EXECUTE')",
                                     (env.runtime_role,)).fetchone()
        prior_grant,=owner.execute("SELECT has_table_privilege(%s,'public.alembic_version','SELECT')",
                                   (env.runtime_role,)).fetchone()
        revision=owner.execute("SELECT version_num FROM public.alembic_version").fetchall()
        if not prior_control:
            owner.execute(sql.SQL("GRANT EXECUTE ON FUNCTION pg_catalog.pg_control_system() TO {}").format(sql.Identifier(env.runtime_role)))
        if not prior_grant:
            owner.execute(sql.SQL("GRANT SELECT ON public.alembic_version TO {}").format(sql.Identifier(env.runtime_role)))
        binding=dict(clusterID=cluster_id,schema="sv-db-operator-binding:1",role=env.runtime_role,roleOID=role_oid,database=db_name,
                     databaseOID=db_oid,tenant=env.tenant,epoch=env.epoch,project=env.project,
                     subject="revision-pin-reader-"+uuid4().hex,person=str(uuid4()),grant="can_contain")
        owner.execute("INSERT INTO inv.operator_grants(tenant_id,subject_id,person_id,can_contain) VALUES(%s,%s,%s,true)",
                      (env.tenant,binding["subject"],binding["person"]))
    d=dict(tenant=env.tenant,epoch=env.epoch,project=env.project,databaseRole=env.runtime_role,nodes={env.node:None})
    try:
        yield d,binding,revision
    finally:
        with psycopg.connect(env.owner,autocommit=True) as owner:
            # Restore the shared disposable database's revision row exactly.
            owner.execute("DELETE FROM public.alembic_version")
            for row in revision:
                owner.execute("INSERT INTO public.alembic_version(version_num) VALUES(%s)",row)
            if not prior_control:
                owner.execute(sql.SQL("REVOKE EXECUTE ON FUNCTION pg_catalog.pg_control_system() FROM {}").format(sql.Identifier(env.runtime_role)))
            if not prior_grant:
                owner.execute(sql.SQL("REVOKE SELECT ON public.alembic_version FROM {}").format(sql.Identifier(env.runtime_role)))


def observe_as_reader(env,d,binding,out=None):
    out={"facts":{},"holds":[]} if out is None else out
    with psycopg.connect(env.runtime,autocommit=True) as db:
        db.execute("SELECT set_config('inv.tenant_id',%s,false)",(env.tenant,))
        try:
            cp.observe(db,d,out,binding)
        finally:
            db.execute("ROLLBACK")
    return out


def set_revision(env,rows):
    with psycopg.connect(env.owner,autocommit=True) as owner:
        owner.execute("DELETE FROM public.alembic_version")
        for row in rows:
            owner.execute("INSERT INTO public.alembic_version(version_num) VALUES(%s)",(row,))


def test_fixture_database_is_the_pinned_unified_head(reader):
    _,_,revision=reader
    assert SCHEMA=="0067_audit_reader_revoke"
    assert revision==[(SCHEMA,)]


def test_pinned_revision_passes_the_revision_check(env,reader):
    d,binding,_=reader
    # Membership is deliberately incomplete, so a pass of the revision check
    # surfaces as the next ordered refusal rather than DATABASE_REVISION_UNKNOWN.
    with pytest.raises(Hold) as stopped:
        observe_as_reader(env,d,binding)
    assert str(stopped.value)=="MEMBERSHIP_UNKNOWN"


@pytest.mark.parametrize("rows",[[r] for r in FOREIGN_REVISIONS]+[[],[SCHEMA,"0068_first_workspace_intent"]],
                         ids=list(FOREIGN_REVISIONS)+["no-revision","two-heads"])
def test_mismatched_database_revision_fails_closed(env,reader,rows):
    d,binding,_=reader
    set_revision(env,rows)
    out={"facts":{},"holds":[]}
    with pytest.raises(Hold,match="^DATABASE_REVISION_UNKNOWN$"):
        observe_as_reader(env,d,binding,out)
    assert out["facts"]=={"transactionReadOnly":"on"}


@pytest.mark.parametrize("expected",["0068_first_workspace_intent","0066_tenant_registry_revoke",""])
def test_collector_expecting_another_revision_refuses_unified_head(env,reader,monkeypatch,expected):
    d,binding,_=reader
    monkeypatch.setattr(cp,"SCHEMA",expected)
    with pytest.raises(Hold,match="^DATABASE_REVISION_UNKNOWN$"):
        observe_as_reader(env,d,binding)
