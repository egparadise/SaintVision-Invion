"""Dedicated input rows in the hosted disposable schema0068 PostgreSQL fixture."""
import sys
import json
import os
import hashlib
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
                        observe(db,d,out)
                else:
                    observe(db,d,out)
                    assert out["facts"]["transactionReadOnly"]=="on"
                    assert out["facts"]["assignedTransactionID"] is None
                    assert out["facts"]["obligations"]["openRuns"]==1
                    assert "ACTIVE_WORK_REQUIRES_RECONCILIATION" in out["holds"]
                    for node,version,der,expiry,_ in before:
                        ch=out["facts"]["channels"][node]
                        assert (ch["C"],ch["leafDER"],ch["expiresAt"])==(version,der,expiry.isoformat())
                db.execute("ROLLBACK")
        after=rows()
        assert before==after
        if os.environ.get("SV_PREFLIGHT_PG_RECEIPT")=="1":
            folder=Path("dist/recovery-readonly-pg")
            folder.mkdir(parents=True,exist_ok=True)
            def checksum(items):
                return hashlib.sha256(json.dumps(items,default=str).encode()).hexdigest()
            (folder/"observations.json").write_text(json.dumps(dict(sourceSHA=os.environ["GITHUB_SHA"],
                fixture="disposable-postgres-schema0068",hiddenChannelCount=hidden,hiddenDisposition=str(failure.value),
                observed=out["facts"],holds=out["holds"],channelRowsBefore=checksum(before),channelRowsAfter=checksum(after),
                activationAllowed=False),indent=2))
    finally:
        if not prior_grant:
            with psycopg.connect(env.owner) as owner:
                owner.execute(sql.SQL("REVOKE SELECT ON public.alembic_version FROM {}").format(sql.Identifier(env.runtime_role)))
