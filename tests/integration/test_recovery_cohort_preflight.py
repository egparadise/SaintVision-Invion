"""Dedicated input rows in the hosted disposable schema0067 PostgreSQL fixture."""
import sys
import json
import os
import hashlib
import shutil
import subprocess
from uuid import uuid4
from pathlib import Path

import psycopg
from psycopg import sql
import pytest
from inv.ids import new_id

HERE=Path(__file__).resolve().parent
TOOLS=Path(__file__).resolve().parents[2]/"tools/recovery_preflight"
HARNESS=HERE/"recovery_reader_namespace_harness.py"
sys.path.insert(0,str(TOOLS))
sys.path.insert(0,str(HERE))
from cp import observe
from common import Hold
from recovery_guard_trace import GUARD_SQL, TracingConnection, attribute

pytestmark=pytest.mark.postgres
UNKNOWN="OPERATOR_VISIBILITY_UNKNOWN"
NOBODY=65534
VERIFY_ORDER=["session-role-database-oid","control-function-privilege","cluster-identifier","operator-grant"]


def write_receipt(name,payload):
    if os.environ.get("SV_PREFLIGHT_PG_RECEIPT")=="1":
        folder=Path("dist/recovery-readonly-pg")
        folder.mkdir(parents=True,exist_ok=True)
        (folder/name).write_text(json.dumps(dict(sourceSHA=os.environ["GITHUB_SHA"],**payload),indent=2,default=str))


def seed_cohort(env):
    """Three enabled members, audited channels, one open run and a current can_contain grant."""
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
    return d,binding,(prior_control,prior_grant)


def restore_privileges(env,prior):
    prior_control,prior_grant=prior
    if not prior_control:
        with psycopg.connect(env.owner) as owner:
            owner.execute(sql.SQL("REVOKE EXECUTE ON FUNCTION pg_catalog.pg_control_system() FROM {}").format(sql.Identifier(env.runtime_role)))
    if not prior_grant:
        with psycopg.connect(env.owner) as owner:
            owner.execute(sql.SQL("REVOKE SELECT ON public.alembic_version FROM {}").format(sql.Identifier(env.runtime_role)))


def owner_execute(env,statement,params=()):
    with psycopg.connect(env.owner) as owner:
        owner.execute(statement,params)


def set_grant(env,binding,column,value):
    assert column in ("enabled","can_contain")
    owner_execute(env,sql.SQL("UPDATE inv.operator_grants SET {}=%s WHERE tenant_id=%s AND subject_id=%s").format(
        sql.Identifier(column)),(value,env.tenant,binding["subject"]))


CONTROL_FUNCTION=sql.SQL("FUNCTION pg_catalog.pg_control_system()")


def withdraw_control_privilege(env):
    """PostgreSQL grants EXECUTE on pg_control_system() to PUBLIC by default, so revoking the
    role's own grant alone leaves the privilege in place. Function ACLs live in this disposable
    database's pg_proc, so withdraw PUBLIC and any direct grant here, prove it is gone, and
    return exactly what to restore."""
    with psycopg.connect(env.owner) as owner:
        public,direct=owner.execute("""SELECT has_function_privilege('public','pg_catalog.pg_control_system()','EXECUTE'),
            EXISTS(SELECT 1 FROM pg_proc p,aclexplode(p.proacl) a JOIN pg_roles r ON r.oid=a.grantee
                   WHERE p.oid='pg_catalog.pg_control_system()'::regprocedure AND r.rolname=%s
                   AND a.privilege_type='EXECUTE')""",(env.runtime_role,)).fetchone()
        owner.execute(sql.SQL("REVOKE EXECUTE ON {} FROM PUBLIC").format(CONTROL_FUNCTION))
        owner.execute(sql.SQL("REVOKE EXECUTE ON {} FROM {}").format(CONTROL_FUNCTION,sql.Identifier(env.runtime_role)))
        held,=owner.execute("SELECT has_function_privilege(%s,'pg_catalog.pg_control_system()','EXECUTE')",
                            (env.runtime_role,)).fetchone()
    assert held is False,"runtime role still holds pg_control_system() through another membership"
    return {"public":public,"direct":direct}


def restore_control_privilege(env,acl):
    with psycopg.connect(env.owner) as owner:
        if acl["public"]:
            owner.execute(sql.SQL("GRANT EXECUTE ON {} TO PUBLIC").format(CONTROL_FUNCTION))
        if acl["direct"]:
            owner.execute(sql.SQL("GRANT EXECUTE ON {} TO {}").format(CONTROL_FUNCTION,sql.Identifier(env.runtime_role)))


def refused_guard(db,d,binding):
    """The public result stays one code; the guard is recovered from outside the collector."""
    traced=TracingConnection(db)
    refused={"facts":{},"holds":[]}
    with pytest.raises(Hold) as rejected:
        observe(traced,d,refused,binding)
    db.execute("ROLLBACK")
    assert str(rejected.value)==UNKNOWN
    assert refused["facts"]=={"transactionReadOnly":"on"} and refused["holds"]==[]
    guard,rows=attribute(rejected.value,traced.trace)
    return dict(code=str(rejected.value),guard=guard,guardRows=rows),traced.trace


def guard_statements(trace):
    labels=[]
    for statement in trace:
        for token,label in GUARD_SQL:
            if token in statement["sql"]:
                labels.append((label,len(statement["rows"] or [])))
                break
    return labels


def test_cohort_visibility_and_readonly_transaction(request):
    env=request.getfixturevalue("env")
    d,binding,prior=seed_cohort(env)
    control_acl=None
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
                    hidden_result,hidden_trace=refused_guard(db,d,binding)
                    # The session-tenant predicate refuses before verify_reader issues any query.
                    assert hidden_result["guard"]=="session-facts" and guard_statements(hidden_trace)==[]
                else:
                    traced=TracingConnection(db)
                    observe(traced,d,out,binding)
                    # Positive control: every verify_reader predicate ran and matched exactly one row.
                    assert guard_statements(traced.trace)==[(label,1) for label in VERIFY_ORDER]
                    assert out["facts"]["transactionReadOnly"]=="on"
                    assert out["facts"]["assignedTransactionID"] is None
                    assert out["facts"]["obligations"]["openRuns"]==1
                    assert "ACTIVE_WORK_REQUIRES_RECONCILIATION" in out["holds"]
                    for node,version,der,expiry,_ in before:
                        ch=out["facts"]["channels"][node]
                        assert (ch["C"],ch["leafDER"],ch["expiresAt"])==(version,der,expiry.isoformat())
                db.execute("ROLLBACK")
            # R2-01: each negative changes one field of the otherwise exact binding (or one database
            # fact) and must be refused by its intended predicate. guardRows pins which side refused:
            # 0 = the SQL predicate returned no row; 1 = one row returned and the equality refused it.
            without_person={k:v for k,v in binding.items() if k!="person"}
            negatives=[
                ("same-name-foreign-role-oid",{**binding,"roleOID":"0"},"session-role-database-oid",1),
                ("wrong-database-name",{**binding,"database":"inv_absent_"+uuid4().hex[:8]},"session-role-database-oid",1),
                ("wrong-database-oid",{**binding,"databaseOID":"0"},"session-role-database-oid",1),
                ("wrong-cluster",{**binding,"clusterID":"0"},"cluster-identifier",1),
                ("wrong-project",{**binding,"project":new_id("prj")},"binding-shape-scope",None),
                ("wrong-tenant-binding",{**binding,"tenant":env.other},"binding-shape-scope",None),
                ("wrong-epoch",{**binding,"epoch":str(uuid4())},"binding-shape-scope",None),
                ("wrong-role-name",{**binding,"role":"absent_reader"},"binding-shape-scope",None),
                ("wrong-grant-kind",{**binding,"grant":"can_resume"},"binding-shape-scope",None),
                ("wrong-schema",{**binding,"schema":"sv-db-operator-binding:2"},"binding-shape-scope",None),
                ("extra-field",{**binding,"extra":"fixture"},"binding-shape-scope",None),
                ("missing-field",without_person,"binding-shape-scope",None),
                ("wrong-subject",{**binding,"subject":"fixture-reader-"+uuid4().hex},"operator-grant",0),
                ("wrong-person",{**binding,"person":str(uuid4())},"operator-grant",0),
                ("contain-withdrawn",binding,"operator-grant",0),
                ("control-privilege-revoked",binding,"control-function-privilege",1),
                ("revoked-grant",binding,"operator-grant",0),
            ]
            negative_codes={}
            negative_guards={}
            for label,candidate,guard,guard_rows in negatives:
                if label=="contain-withdrawn":
                    set_grant(env,binding,"can_contain",False)
                if label=="control-privilege-revoked":
                    control_acl=withdraw_control_privilege(env)
                    control_withdrawn=dict(control_acl)
                if label=="revoked-grant":
                    set_grant(env,binding,"enabled",False)
                result,_=refused_guard(db,d,candidate)
                assert (result["guard"],result["guardRows"])==(guard,guard_rows),(label,result)
                negative_codes[label]=result["code"]
                negative_guards[label]={"guard":result["guard"],"guardRows":result["guardRows"]}
                if label=="contain-withdrawn":
                    set_grant(env,binding,"can_contain",True)
                if label=="control-privilege-revoked":
                    restore_control_privilege(env,control_acl)
                    control_acl=None
        after=rows()
        assert before==after
        def checksum(items):
            return hashlib.sha256(json.dumps(items,default=str).encode()).hexdigest()
        write_receipt("observations.json",dict(fixture="disposable-postgres-schema0067",hiddenChannelCount=hidden,
            hiddenDisposition=hidden_result["code"],hiddenGuard=hidden_result["guard"],
            bindingNegatives=negative_codes,bindingNegativeGuards=negative_guards,
            controlPrivilegeWithdrawnFrom=control_withdrawn,
            observed=out["facts"],holds=out["holds"],channelRowsBefore=checksum(before),channelRowsAfter=checksum(after),
            activationAllowed=False))
    finally:
        if control_acl is not None:
            restore_control_privilege(env,control_acl)
        restore_privileges(env,prior)


def root_namespace_command():
    """sudo -n unshare --mount: the fixture /etc exists only inside the child's private mount namespace."""
    def unavailable(reason):
        if os.environ.get("CI"):
            pytest.fail(reason)
        pytest.skip(reason)
    if not sys.platform.startswith("linux"):
        unavailable("provisioned reader namespace fixture requires Linux")
    unshare=shutil.which("unshare")
    if unshare is None:
        unavailable("provisioned reader namespace fixture requires util-linux unshare")
    prefix=[]
    if os.geteuid()!=0:
        if shutil.which("sudo") is None or subprocess.run(["sudo","-n","true"],capture_output=True).returncode!=0:
            unavailable("provisioned reader namespace fixture requires root or passwordless sudo")
        prefix=["sudo","-n"]
    passthrough=[f"{key}={os.environ[key]}" for key in ("LD_LIBRARY_PATH",) if key in os.environ]
    return prefix+[unshare,"--mount","--propagation","private","--","env",*passthrough,
                   sys.executable,"-I","-B",str(HARNESS)]


def test_provisioned_reader_path_in_private_mount_namespace(request):
    """R2-02: main() never injects a binding; exercise provisioned_reader() itself, unmodified."""
    env=request.getfixturevalue("env")
    command=root_namespace_command()
    host_descriptor=Path("/etc/saintvision/recovery-reader.json")
    host_etc=os.stat("/etc")
    host_had_descriptor=host_descriptor.exists()
    d,binding,prior=seed_cohort(env)
    try:
        trusted=json.dumps(binding)
        def regular(content,**layout):
            return dict(kind="regular",content=content,**layout)
        cases=[
            ("trusted",regular(trusted),None),
            ("trusted-owner-only-0600",regular(trusted,fileMode=0o600),None),
            ("missing-descriptor",dict(kind="missing",content=None),"descriptor-open:ENOENT"),
            ("missing-directory",dict(kind="missing-dir",content=None),"descriptor-open:ENOENT"),
            ("wrong-identity-role-oid",regular(json.dumps({**binding,"roleOID":"0"})),"session-role-database-oid"),
            ("wrong-identity-person",regular(json.dumps({**binding,"person":str(uuid4())})),"operator-grant"),
            ("wrong-identity-project",regular(json.dumps({**binding,"project":new_id("prj")})),"binding-shape-scope"),
            ("file-owner-not-root",regular(trusted,fileOwner=NOBODY),"descriptor-owner-mode"),
            ("file-group-writable",regular(trusted,fileMode=0o664),"descriptor-owner-mode"),
            ("file-world-writable",regular(trusted,fileMode=0o646),"descriptor-owner-mode"),
            ("directory-owner-not-root",regular(trusted,dirOwner=NOBODY),"descriptor-owner-mode"),
            ("directory-world-writable",regular(trusted,dirMode=0o757),"descriptor-owner-mode"),
            ("etc-owner-not-root",regular(trusted,etcOwner=NOBODY),"descriptor-owner-mode"),
            ("etc-group-writable",regular(trusted,etcMode=0o775),"descriptor-owner-mode"),
            ("file-symlink",dict(kind="symlink",content=trusted),"descriptor-open:ELOOP"),
            # O_DIRECTORY|O_NOFOLLOW on a symlink: Linux refuses the link inode itself as ENOTDIR.
            ("directory-symlink",dict(kind="dir-symlink",content=trusted),"descriptor-open:ENOTDIR"),
            ("file-hardlink",dict(kind="hardlink",content=trusted),"descriptor-type-links-size"),
            ("file-empty",regular(""),"descriptor-type-links-size"),
            ("file-oversize",regular(trusted+" "*(65537-len(trusted))),"descriptor-type-links-size"),
            ("not-regular-fifo",dict(kind="fifo",content=None),"descriptor-type-links-size"),
            ("not-regular-directory",dict(kind="directory",content=None),"descriptor-type-links-size"),
            ("duplicate-field",regular('{"schema":"sv-db-operator-binding:1","schema":"x"}'),"descriptor-json:DUPLICATE_FIELD"),
            ("not-json",regular("{"),"descriptor-json-syntax"),
            ("revoked-grant",regular(trusted),"operator-grant"),
        ]
        results={}
        for name,layout,guard in cases:
            if name=="revoked-grant":
                set_grant(env,binding,"enabled",False)
            spec=dict(connection=env.runtime,tenant=env.tenant,descriptor=d,toolDir=str(TOOLS),case=dict(name=name,**layout))
            proc=subprocess.run(command,input=json.dumps(spec).encode(),capture_output=True,timeout=120)
            assert proc.returncode==0,(name,proc.stderr.decode(errors="replace")[-3000:])
            result=json.loads(proc.stdout.decode().strip().splitlines()[-1])
            assert result["etcFixture"]["sameInode"] is True,name
            if guard is None:
                assert result["complete"] is True and result["code"] is None,(name,result)
                observed=result["observed"]
                assert observed["transactionReadOnly"]=="on" and observed["assignedTransactionID"] is None
                assert observed["transactionTupleChanges"]=={"inserted":0,"updated":0,"deleted":0}
                assert observed["channelMembers"]==sorted(d["nodes"]) and observed["obligations"]["openRuns"]==1
                assert "ACTIVE_WORK_REQUIRES_RECONCILIATION" in observed["holds"]
            else:
                # Public result unchanged: one code, nothing observed beyond the read-only session fact.
                assert result["complete"] is False and result["code"]==UNKNOWN,(name,result)
                assert result["facts"]=={"transactionReadOnly":"on"},name
                assert result["guard"]==guard,(name,result)
                if guard=="operator-grant":
                    assert result["guardRows"]==0,name
            results[name]=result
        # The host /etc was never the fixture and gained no descriptor.
        assert host_descriptor.exists()==host_had_descriptor
        after_etc=os.stat("/etc")
        assert (after_etc.st_dev,after_etc.st_ino,after_etc.st_mode)==(host_etc.st_dev,host_etc.st_ino,host_etc.st_mode)
        write_receipt("provisioned-reader.json",dict(fixture="disposable-postgres-schema0067+private-mount-namespace-/etc",
            collectorEntry="cp.observe(db,descriptor,out) with binding=None -> cp.provisioned_reader()",
            hostDescriptorPresent=host_had_descriptor,cases=results,activationAllowed=False))
    finally:
        restore_privileges(env,prior)


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
                result,_=refused_guard(reader,d,binding)
                # The retired OID is refused by the live role/database OID predicate, not by name.
                assert (result["guard"],result["guardRows"])==("session-role-database-oid",1)
        finally:
            owner.execute(sql.SQL("DROP ROLE IF EXISTS {}").format(sql.Identifier(login)))
