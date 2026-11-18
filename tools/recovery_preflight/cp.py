"""PC3 operator collector. The caller supplies a pinned session on stdin."""
import sys
sys.dont_write_bytecode=True
import json
import os
import stat
from contextlib import ExitStack
from datetime import datetime, timezone
from common import Hold, SCHEMA, decode, now, report, require, scope

TABLES = ("project_nodes","nodes","resources","node_channels","node_channel_audit",
          "runs","execution_deliveries","resource_leases","tool_claims","operator_grants")
POLICY = "(tenant_id = (NULLIF(current_setting('inv.tenant_id'::text, true), ''::text))::uuid)"


def provisioned_reader():
    """Fixed operator-installed public descriptor. No caller path override."""
    flags=os.O_RDONLY|os.O_CLOEXEC|os.O_NOFOLLOW|os.O_NONBLOCK
    try:
        with ExitStack() as stack:
            fd=os.open("/",flags|os.O_DIRECTORY)
            stack.callback(os.close,fd)
            for name in ("etc","saintvision","recovery-reader.json"):
                fd=os.open(name,flags|(0 if name.endswith(".json") else os.O_DIRECTORY),dir_fd=fd)
                stack.callback(os.close,fd)
                st=os.fstat(fd)
                require(st.st_uid==0 and not st.st_mode&0o022,"OPERATOR_VISIBILITY_UNKNOWN")
            require(stat.S_ISREG(st.st_mode) and st.st_nlink==1 and 0<st.st_size<=65536,"OPERATOR_VISIBILITY_UNKNOWN")
            raw=os.read(fd,65537)
            require(len(raw)==st.st_size and os.fstat(fd).st_ctime_ns==st.st_ctime_ns,"OPERATOR_VISIBILITY_UNKNOWN")
            return decode(raw)
    except Exception:
        raise Hold("OPERATOR_VISIBILITY_UNKNOWN") from None


def verify_reader(c,d,binding):
    unknown="OPERATOR_VISIBILITY_UNKNOWN"
    require(type(binding) is dict and set(binding)=={"schema","role","roleOID","clusterID","database","databaseOID",
            "tenant","epoch","project","subject","person","grant"} and binding["schema"]=="sv-db-operator-binding:1"
            and binding["grant"]=="can_contain" and binding["role"]==d["databaseRole"] and
            all(binding[k]==d[k] for k in ("tenant","epoch","project")),unknown)
    c.execute("""SELECT r.oid::text,db.datname,db.oid::text FROM pg_roles r,pg_database db
                 WHERE r.rolname=session_user AND db.datname=current_database()""")
    require(c.fetchall()==[(binding["roleOID"],binding["database"],binding["databaseOID"])],unknown)
    c.execute("SELECT has_function_privilege(current_user,'pg_catalog.pg_control_system()','EXECUTE')")
    require(c.fetchone()==(True,),unknown)
    c.execute("SELECT system_identifier::text FROM pg_control_system()")
    require(c.fetchall()==[(binding["clusterID"],)],unknown)
    c.execute("""SELECT subject_id,person_id::text FROM inv.operator_grants WHERE tenant_id=%s AND
                 subject_id=%s AND person_id=%s AND enabled AND can_contain""",
              (binding["tenant"],binding["subject"],binding["person"]))
    require(c.fetchall()==[(binding["subject"],binding["person"])],unknown)


def observe(db,d,out,binding=None):
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
        try:
            verify_reader(c,d,binding if binding is not None else provisioned_reader())
        except Exception:
            raise Hold("OPERATOR_VISIBILITY_UNKNOWN") from None
        c.execute("SELECT version_num FROM public.alembic_version")
        require(c.fetchall()==[(SCHEMA,)],"DATABASE_REVISION_UNKNOWN")
        c.execute("""SELECT c.relname,c.relrowsecurity,c.relforcerowsecurity,
                     pg_get_userbyid(c.relowner)=current_user,p.polname,p.polpermissive,
                     p.polcmd::text,p.polroles::text,pg_get_expr(p.polqual,p.polrelid)
                     FROM pg_class c JOIN pg_namespace n ON n.oid=c.relnamespace
                     LEFT JOIN pg_policy p ON p.polrelid=c.oid
                     WHERE n.nspname='inv' AND row_security_active(c.oid) AND c.relname=ANY(%s)""",(list(TABLES),))
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
        if any(datetime.fromisoformat(row["expiresAt"])<=datetime.now(timezone.utc) for row in channels.values()):
            out["holds"].append("CHANNEL_LEAF_EXPIRED")
        out["facts"]["channels"]=channels
        out["facts"]["operationOutcome"]="UNKNOWN"
        out["holds"].append("OPERATION_OUTCOME_UNKNOWN")
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
          (SELECT count(*) FROM inv.runs r WHERE r.tenant_id=%s AND r.state NOT IN ('succeeded','failed','cancelled')
           AND (r.project_id=%s OR EXISTS (SELECT 1 FROM inv.tool_claims c WHERE c.tenant_id=r.tenant_id AND c.run_id=r.run_id AND c.node_id=ANY(%s))))""",
          (tenant,members,tenant,members,tenant,members,tenant,project,members))
        counts=c.fetchone()
        out["facts"]["obligations"]=dict(zip(("unreleasedLeases","deliveries","unsettledClaims","openRuns"),counts))
        if any(counts):
            out["holds"].append("ACTIVE_WORK_REQUIRES_RECONCILIATION")
        c.execute("""SELECT count(*),sum(n_tup_ins),sum(n_tup_upd),sum(n_tup_del)
                     FROM pg_stat_xact_user_tables WHERE schemaname='inv'""")
        tables,inserted,updated,deleted=c.fetchone()
        require(tables>=len(TABLES) and (inserted,updated,deleted)==(0,0,0),"UNEXPECTED_TRANSACTION_MUTATION")
        out["facts"]["transactionTupleChanges"]={"inserted":int(inserted),"updated":int(updated),"deleted":int(deleted)}
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
