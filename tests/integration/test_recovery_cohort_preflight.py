"""Dedicated input rows in the hosted disposable schema0067 PostgreSQL fixture."""
import sys
import json
import os
import hashlib
from uuid import uuid4
from pathlib import Path

import psycopg
from psycopg import sql
import pytest
from inv.ids import new_id

sys.path.insert(0,str(Path(__file__).parents[2]/"tools/recovery_preflight"))
from cp import observe
from common import Hold

pytestmark=pytest.mark.postgres


def test_cohort_visibility_and_readonly_transaction(request):
    env=request.getfixturevalue("env")
    nodes=[env.node,new_id("nod"),new_id("nod")]
    d=dict(tenant=env.tenant,epoch=env.epoch,project=env.project,databaseRole=env.runtime_role,
           nodes=dict.fromkeys(nodes))
    with psycopg.connect(env.owner) as owner:
        role_oid,db_name,db_oid=owner.execute("""SELECT r.oid::text,db.datname,db.oid::text FROM pg_roles r,pg_database db
            WHERE r.rolname=%s AND db.datname=current_database()""",(env.runtime_role,)).fetchone()
        cluster_id,=owner.execute("SELECT system_identifier::text FROM pg_control_system()").fetchone()
        prior_control,=owner.execute("SELECT has_function_privilege(%s,'pg_catalog.pg_control_system()','EXECUTE')",(env.runtime_role,)).fetchone()
        if not prior_control:
            owner.execute(sql.SQL("GRANT EXECUTE ON FUNCTION pg_catalog.pg_control_system() TO {}").format(sql.Identifier(env.runtime_role)))
        binding=dict(clusterID=cluster_id,schema="sv-db-operator-binding:1",role=env.runtime_role,roleOID=role_oid,database=db_name,
                     databaseOID=db_oid,tenant=env.tenant,epoch=env.epoch,project=env.project,
                     subject="fixture-reader-"+uuid4().hex,person=str(uuid4()),grant="can_contain")
        owner.execute("""INSERT INTO inv.operator_grants(tenant_id,subject_id,person_id,can_contain)
                         VALUES(%s,%s,%s,true)""",(env.tenant,binding["subject"],binding["person"]))
        prior_grant,=owner.execute("SELECT has_table_privilege(%s,'public.alembic_version','SELECT')",
                                   (env.runtime_role,)).fetchone()
        if not prior_grant:
            owner.execute(sql.SQL("GRANT SELECT ON public.alembic_version TO {}").format(sql.Identifier(env.runtime_role)))
        for i,node in enumerate(nodes):
            if i:
                owner.execute("INSERT INTO inv.nodes(tenant_id,node_id,status,recovery_epoch) VALUES(%s,%s,'online',%s)",
                              (env.tenant,node,env.epoch))
                owner.execute("INSERT INTO inv.resources VALUES(%s,%s,%s,'cpu',10,10)",(env.tenant,new_id("res"),node))
            owner.execute("INSERT INTO inv.project_nodes(tenant_id,project_id,node_id) VALUES(%s,%s,%s)",(env.tenant,env.project,node))
            owner.execute("""INSERT INTO inv.node_channels
                (tenant_id,node_id,recovery_epoch,version,endpoint,certificate_sha256,certificate_not_after,enabled)
                VALUES(%s,%s,%s,%s,'https://fixture.invalid:18443',%s,now()-interval '1 hour',true)""",
                (env.tenant,node,env.epoch,7+i,format(i+1,'064x')))
            owner.execute("""INSERT INTO inv.node_channel_audit(tenant_id,node_id,version,action,certificate_sha256)
                VALUES(%s,%s,%s,'provision',%s)""",(env.tenant,node,7+i,format(i+1,'064x')))
        owner.execute("INSERT INTO inv.runs(tenant_id,project_id,run_id) VALUES(%s,%s,%s)",(env.tenant,env.project,new_id("run")))
    try:
        def rows():
            with psycopg.connect(env.owner) as db:
                return db.execute("""SELECT node_id,version,certificate_sha256,certificate_not_after,xmin::text
                                  FROM inv.node_channels WHERE tenant_id=%s ORDER BY node_id""",(env.tenant,)).fetchall()
        before=rows()
        with psycopg.connect(env.runtime,autocommit=True) as db:
            for tenant in (env.other,env.tenant):
                db.execute("SELECT set_config('inv.tenant_id',%s,false)",(tenant,))
                out={"facts":{},"holds":[]}
                if tenant!=env.tenant:
                    hidden,=db.execute("SELECT count(*) FROM inv.node_channels WHERE tenant_id=%s",(env.tenant,)).fetchone()
                    assert hidden==0
                    with pytest.raises(Hold,match="OPERATOR_VISIBILITY_UNKNOWN") as failure:
                        observe(db,d,out,binding)
                else:
                    observe(db,d,out,binding)
                    assert out["facts"]["transactionReadOnly"]=="on"
                    assert out["facts"]["assignedTransactionID"] is None
                    assert out["facts"]["obligations"]["openRuns"]==1
                    assert "ACTIVE_WORK_REQUIRES_RECONCILIATION" in out["holds"]
                    for node,version,der,expiry,_ in before:
                        ch=out["facts"]["channels"][node]
                        assert (ch["C"],ch["leafDER"],ch["expiresAt"])==(version,der,expiry.isoformat())
                db.execute("ROLLBACK")
            negatives={}
            for label,change in [("same-name-foreign-role-oid",{"roleOID":"0"}),("wrong-project",{"project":new_id("prj")}),
                                 ("wrong-person",{"person":str(uuid4())}),("revoked-grant",{})]:
                if label=="revoked-grant":
                    with psycopg.connect(env.owner) as owner:
                        owner.execute("UPDATE inv.operator_grants SET enabled=false WHERE tenant_id=%s AND subject_id=%s",
                                      (env.tenant,binding["subject"]))
                refused={"facts":{},"holds":[]}
                with pytest.raises(Hold,match="OPERATOR_VISIBILITY_UNKNOWN") as rejected:
                    observe(db,d,refused,{**binding,**change})
                assert refused["facts"]=={"transactionReadOnly":"on"}
                negatives[label]=str(rejected.value)
                db.execute("ROLLBACK")
        after=rows()
        assert before==after
        if os.environ.get("SV_PREFLIGHT_PG_RECEIPT")=="1":
            folder=Path("dist/recovery-readonly-pg")
            folder.mkdir(parents=True,exist_ok=True)
            def checksum(items):
                return hashlib.sha256(json.dumps(items,default=str).encode()).hexdigest()
            (folder/"observations.json").write_text(json.dumps(dict(sourceSHA=os.environ["GITHUB_SHA"],
                fixture="disposable-postgres-schema0067",hiddenChannelCount=hidden,hiddenDisposition=str(failure.value),
                bindingNegatives=negatives,observed=out["facts"],holds=out["holds"],channelRowsBefore=checksum(before),channelRowsAfter=checksum(after),
                activationAllowed=False),indent=2))
    finally:
        if not prior_control:
            with psycopg.connect(env.owner) as owner:
                owner.execute(sql.SQL("REVOKE EXECUTE ON FUNCTION pg_catalog.pg_control_system() FROM {}").format(sql.Identifier(env.runtime_role)))
        if not prior_grant:
            with psycopg.connect(env.owner) as owner:
                owner.execute(sql.SQL("REVOKE SELECT ON public.alembic_version FROM {}").format(sql.Identifier(env.runtime_role)))

def test_recreated_login_with_same_name_cannot_use_retired_binding(request):
    from psycopg.conninfo import make_conninfo
    env=request.getfixturevalue("env")
    login="fixture_reader_"+uuid4().hex[:16]
    password=uuid4().hex
    with psycopg.connect(env.owner,autocommit=True) as owner:
        owner.execute(sql.SQL("CREATE ROLE {} NOLOGIN").format(sql.Identifier(login)))
        try:
            old_oid,=owner.execute("SELECT oid::text FROM pg_roles WHERE rolname=%s",(login,)).fetchone()
            owner.execute(sql.SQL("DROP ROLE {}").format(sql.Identifier(login)))
            owner.execute(sql.SQL("CREATE ROLE {} LOGIN PASSWORD {}").format(sql.Identifier(login),sql.Literal(password)))
            new_oid,=owner.execute("SELECT oid::text FROM pg_roles WHERE rolname=%s",(login,)).fetchone()
            assert old_oid!=new_oid
            cluster,db_name,db_oid=owner.execute("""SELECT system_identifier::text,current_database(),d.oid::text
                FROM pg_control_system(),pg_database d WHERE d.datname=current_database()""").fetchone()
            d=dict(databaseRole=login,tenant=env.tenant,epoch=env.epoch,project=env.project,nodes={})
            binding=dict(schema="sv-db-operator-binding:1",role=login,roleOID=old_oid,clusterID=cluster,database=db_name,
                         databaseOID=db_oid,tenant=env.tenant,epoch=env.epoch,project=env.project,
                         subject="retired-fixture-reader",person=str(uuid4()),grant="can_contain")
            with psycopg.connect(make_conninfo(env.owner,user=login,password=password),autocommit=True) as reader:
                reader.execute("SELECT set_config('inv.tenant_id',%s,false)",(env.tenant,))
                assert reader.execute("SELECT session_user").fetchone()==(login,)
                out={"facts":{},"holds":[]}
                with pytest.raises(Hold,match="OPERATOR_VISIBILITY_UNKNOWN"):
                    observe(reader,d,out,binding)
                assert out["facts"]=={"transactionReadOnly":"on"}
                reader.execute("ROLLBACK")
        finally:
            owner.execute(sql.SQL("DROP ROLE IF EXISTS {}").format(sql.Identifier(login)))
