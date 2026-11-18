"""PC3 operator collector. The caller supplies a pinned session on stdin."""
import sys
import json
from common import Hold, SCHEMA, decode, now, report, require, scope

TABLES = ("project_nodes","nodes","resources","node_channels","node_channel_audit",
          "runs","execution_deliveries","resource_leases","tool_claims")
POLICY = "(tenant_id = (NULLIF(current_setting('inv.tenant_id'::text, true), ''::text))::uuid)"


def observe(db,d,out):
    tenant,epoch,project=d["tenant"],d["epoch"],d["project"]
    members=sorted(d["nodes"])
    with db.cursor() as c:
        c.execute("BEGIN ISOLATION LEVEL REPEATABLE READ READ ONLY")
        c.execute("SET LOCAL search_path TO pg_catalog")
        c.execute("SET LOCAL statement_timeout TO '4s'")
        c.execute("""SELECT current_setting('transaction_read_only'), current_user, session_user,
                     current_setting('inv.tenant_id',true),r.rolsuper,r.rolbypassrls
                     FROM pg_roles r WHERE r.rolname=current_user""")
        ro,user,login,bound,superuser,bypass=c.fetchone()
        out["facts"]["transactionReadOnly"]=ro
        require(ro=="on" and user==login==d["databaseRole"] and bound==tenant and
                not superuser and not bypass,"OPERATOR_VISIBILITY_UNKNOWN")
        c.execute("SELECT version_num FROM public.alembic_version")
        require(c.fetchall()==[(SCHEMA,)],"DATABASE_REVISION_UNKNOWN")
        c.execute("""SELECT c.relname,c.relrowsecurity,c.relforcerowsecurity,
                     pg_get_userbyid(c.relowner)=current_user,p.polname,p.polpermissive,
                     p.polcmd,p.polroles::text,pg_get_expr(p.polqual,p.polrelid)
                     FROM pg_class c JOIN pg_namespace n ON n.oid=c.relnamespace
                     LEFT JOIN pg_policy p ON p.polrelid=c.oid
                     WHERE n.nspname='inv' AND c.relname=ANY(%s)""",(list(TABLES),))
        policies=c.fetchall()
        require(len(policies)==len(TABLES) and {r[0] for r in policies}==set(TABLES)
                and all(row[1:8]==(True,True,False,"tenant_isolation",True,"*","{0}") and
                        row[8] in (POLICY,POLICY.replace("(NULLIF","NULLIF").replace("))::uuid",")::uuid"))
                        for row in policies),"OPERATOR_VISIBILITY_UNKNOWN")
        c.execute("SELECT epoch::text FROM inv.control_epoch WHERE singleton")
        require(c.fetchall()==[(epoch,)],"DATABASE_EPOCH_UNKNOWN")
        c.execute("""SELECT node_id FROM inv.project_nodes WHERE tenant_id=%s AND project_id=%s
                     AND enabled ORDER BY node_id""",(tenant,project))
        require([n for n, in c.fetchall()]==members,"MEMBERSHIP_UNKNOWN")
        c.execute("""SELECT ch.node_id,ch.version,ch.certificate_sha256,ch.certificate_not_after,
                     ch.enabled,a.action,a.certificate_sha256,a.recorded_at
                     FROM inv.node_channels ch JOIN inv.nodes n USING(tenant_id,node_id)
                     LEFT JOIN inv.node_channel_audit a USING(tenant_id,node_id,version)
                     WHERE ch.tenant_id=%s AND ch.recovery_epoch=%s AND n.recovery_epoch=%s
                     AND ch.node_id=ANY(%s) ORDER BY ch.node_id""",(tenant,epoch,epoch,members))
        channels={}
        for node,version,der,expiry,enabled,action,auditder,at in c.fetchall():
            require(enabled and action=="provision" and der==auditder,"CHANNEL_AUDIT_UNKNOWN")
            channels[node]=dict(C=version,leafDER=der,expiresAt=expiry.isoformat(),auditedAt=at.isoformat())
        require(sorted(channels)==members,"CHANNEL_VISIBILITY_UNKNOWN")
        out["facts"]["channels"]=channels
        c.execute("""SELECT node_id,resource_id,kind,capacity,offered FROM inv.resources
                     WHERE tenant_id=%s AND node_id=ANY(%s) ORDER BY node_id,resource_id LIMIT 1025""",(tenant,members))
        resources=c.fetchall()
        require(len(resources)<=1024 and {r[0] for r in resources}==set(members),"RESOURCES_UNKNOWN")
        out["facts"]["resources"]=resources
        c.execute("""SELECT
          (SELECT count(*) FROM inv.resource_leases l JOIN inv.resources r USING(tenant_id,resource_id)
            WHERE l.tenant_id=%s AND r.node_id=ANY(%s) AND l.released_at IS NULL),
          (SELECT count(*) FROM inv.execution_deliveries WHERE tenant_id=%s AND node_id=ANY(%s) AND phase<>'stopped'),
          (SELECT count(*) FROM inv.tool_claims t WHERE t.tenant_id=%s AND t.node_id=ANY(%s) AND NOT EXISTS
            (SELECT 1 FROM inv.execution_deliveries e WHERE e.tenant_id=t.tenant_id AND e.command_id=t.command_id AND e.phase='stopped')),
          (SELECT count(*) FROM inv.runs WHERE tenant_id=%s AND project_id=%s AND state NOT IN ('succeeded','failed','cancelled'))""",
          (tenant,members,tenant,members,tenant,members,tenant,project))
        counts=c.fetchone()
        out["facts"]["obligations"]=dict(zip(("unreleasedLeases","deliveries","unsettledClaims","openRuns"),counts))
        if any(counts):
            out["holds"].append("ACTIVE_WORK_REQUIRES_RECONCILIATION")
        c.execute("SELECT pg_current_xact_id_if_assigned()::text")
        xid,=c.fetchone()
        out["facts"]["assignedTransactionID"]=xid
        require(xid is None,"UNEXPECTED_TRANSACTION_ID")
        out["observationComplete"]=True


def main():
    import psycopg
    out={"observationComplete":False,"recoveryReady":False,"activationAllowed":False,"release":False,"holds":[]}
    try:
        data=decode(sys.stdin.buffer.read(65537))
        d=scope(data["descriptor"])
        out=report(d,"control-plane")
        with psycopg.connect(data["connection"],autocommit=True,connect_timeout=4) as db:
            try:
                observe(db,d,out)
            finally:
                db.execute("ROLLBACK")
    except Exception as err:
        out["observationComplete"]=False
        out["holds"].append(str(err) if isinstance(err,Hold) else "DATABASE_OBSERVATION_UNKNOWN")
    out["observedAt"]=now()
    print(json.dumps(out))
    return 0 if out["observationComplete"] else 2


if __name__=="__main__":
    sys.exit(main())
