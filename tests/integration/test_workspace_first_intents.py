"""Production HTTP writes use restricted inv_kernel login, never fixture Run mappings.

Owner setup supplies only isolated existing account/project/ready Workspace metadata.
The new serving API creates every workload/public Run/business Run under test.
"""
from concurrent.futures import ThreadPoolExecutor
from copy import deepcopy
from types import SimpleNamespace
from uuid import uuid4
import base64
import json

import psycopg
from psycopg import sql
import pytest
from fastapi.testclient import TestClient
from inv.app import create_app
from inv.approvals import digest
from inv.contracts import validate_contract
from inv.ids import new_id
from inv.sandbox import SandboxProfile
from inv.tooling import NodePrincipal
from inv.workspace_api import RestrictedWorkspaceRuntime, WorkspaceAPI
from inv.workspace_files import WorkingGenerations, canonical
from test_control_api import api
from test_approvals import approval

pytestmark = pytest.mark.postgres


@pytest.fixture
def intents(api, tmp_path):
    a = api
    a.workspace_id = new_id("wsp")
    a.user = new_id("usr")
    a.memory = new_id("res")
    with psycopg.connect(a.e.owner) as conn:
        conn.execute("INSERT INTO public.tenants(tenant_id,slug,display_name) VALUES(%s,%s,'Isolated')", (a.e.tenant, a.e.tenant))
        conn.execute("INSERT INTO public.projects(tenant_id,project_id,code,display_name) VALUES(%s,%s,%s,'Isolated')", (a.e.tenant,a.e.project,a.e.project))
        for actor in ("requester", "alice", "bob"):
            user = a.user if actor == "requester" else new_id("usr")
            conn.execute("INSERT INTO public.users(tenant_id,user_id,external_subject,display_name) VALUES(%s,%s,%s,%s)", (a.e.tenant,user,a.jwt.subject(actor),actor))
            conn.execute("INSERT INTO public.project_members(tenant_id,project_id,user_id,role_code) VALUES(%s,%s,%s,%s)", (a.e.tenant,a.e.project,user,"owner" if actor == "requester" else "approver"))
            conn.execute("INSERT INTO inv.business_subjects(tenant_id,subject_id,user_id) VALUES(%s,%s,%s)", (a.e.tenant,a.jwt.subject(actor),user))
        conn.execute("INSERT INTO inv.business_projects(tenant_id,project_id) VALUES(%s,%s)", (a.e.tenant,a.e.project))
        conn.execute("INSERT INTO public.workspaces(tenant_id,project_id,workspace_id,name,status,created_by_user_id) VALUES(%s,%s,%s,'Isolated','ready',%s)", (a.e.tenant,a.e.project,a.workspace_id,a.user))
        conn.execute("INSERT INTO inv.project_nodes(tenant_id,project_id,node_id) VALUES(%s,%s,%s)", (a.e.tenant,a.e.project,a.e.node))
        conn.execute("INSERT INTO inv.resources VALUES(%s,%s,%s,'memory',67108864,67108864)", (a.e.tenant,a.memory,a.e.node))
    root = tmp_path / "working"
    root.mkdir(mode=0o700)
    a.runtime = RestrictedWorkspaceRuntime(a.e.db, profile=SandboxProfile("isolated-cpu:1", frozenset({"sha256:"+"a"*64}), frozenset({"/usr/local/bin/python3"}),500,67108864,30),
        node=NodePrincipal(a.e.tenant,a.e.node), resources={"cpu":a.e.resource,"memory":a.memory}, signing_key=None, policy_version="isolated-policy:1",client=None)
    a.http = TestClient(create_app(a.e.db,a.jwt.auth,workspace=WorkspaceAPI(a.e.db,WorkingGenerations(root),a.runtime)),raise_server_exceptions=False)
    a.base = f"/v1/projects/{a.e.project}/workspaces/{a.workspace_id}/first-intents"
    a.input = dict(objective="Isolated user-selected CPU task",imageDigest="sha256:"+"a"*64,command=["/usr/local/bin/python3","-B","src/app.py"],
        resources=dict(cpuMillis=1,memoryBytes=8388608,gpuCount=0,minVramBytes=0),timeoutSeconds=10)
    a.ws_headers = lambda key="intent-create",actor="requester": {**a.headers(actor,key=key),"If-Match":'"workspace-v1"'}
    yield a
    a.http.close()


def create_intent(a, key="intent-create"):
    r = a.http.post(a.base,json=a.input,headers=a.ws_headers(key))
    assert r.status_code == 201, r.text
    item=r.json()
    validate_contract("WorkspaceFirstIntent",item)
    return item


def create_run(a,item,key="run-create",**kwargs):
    return a.http.post(a.base+"/"+item["workload"]["workloadId"]+"/runs",json={},
        headers={**a.headers(key=key),"If-Match":item["intentEtag"]},**kwargs)


def counts(a):
    with psycopg.connect(a.e.owner) as conn:
        return tuple(conn.execute(f"SELECT count(*) FROM {table} WHERE tenant_id=%s",(a.e.tenant,)).fetchone()[0]
            for table in ("inv.runs","public.runs","inv.business_runs","inv.outbox","inv.idempotency"))


def test_contract_serving_profile_metadata_and_atomic_run_under_real_runtime_role(intents):
    a=intents
    before=counts(a)
    empty=a.http.get(a.base,headers=a.headers())
    assert empty.status_code==200 and empty.headers["cache-control"]=="no-store"
    validate_contract("WorkspaceFirstIntentPage",empty.json())
    assert empty.json()["items"]==[] and empty.json()["profile"]["minMemoryBytes"]==8388608
    item=create_intent(a)
    assert item["workload"]["targetNodeId"]==a.e.node
    assert item["workloadSha256"]==digest(item["workload"])
    page=a.http.get(a.base,headers=a.headers()).json()
    assert page["items"][0]["workload"]==item["workload"]
    created=create_run(a,item)
    assert created.status_code==201,created.text
    result=created.json()
    validate_contract("WorkspaceFirstRunCreateResult",result)
    assert result["run"]["state"]=="draft" and result["run"]["attempt"]==0
    assert result["requesterId"]==a.jwt.subject("requester")
    with psycopg.connect(a.e.owner) as conn:
        rows=conn.execute("""SELECT k.run_id,p.run_id,b.run_id,p.requested_by_user_id,w.node_id
            FROM inv.runs k JOIN public.runs p USING(tenant_id,run_id)
            JOIN inv.business_runs b USING(tenant_id,run_id)
            JOIN public.workspaces w ON w.tenant_id=b.tenant_id AND w.workspace_id=b.workspace_id
            WHERE k.run_id=%s""",(result["run"]["runId"],)).fetchone()
        assert rows[:3]==(result["run"]["runId"],)*3 and rows[3]==a.user and rows[4] is None
    replay=create_run(a,item)
    assert replay.status_code==201 and replay.json()==result
    assert counts(a)==tuple(n+v for n,v in zip(before,(1,1,1,1,2)))
    # A real business mapping now passes the existing first prepare boundary.
    raw=canonical(dict(format="workspace-snapshot:1",workspaceId=a.workspace_id,directories=[],files=[]))
    prepared=a.http.post(f'/v1/projects/{a.e.project}/runs/{result["run"]["runId"]}/start/prepare',
        json=dict(startId=str(uuid4()),stepId="isolated-step",workload=item["workload"],expectedVersion=1,
                  snapshotBase64=base64.b64encode(raw).decode(),targetNodeId=a.e.node),headers=a.headers(key="prepare"))
    assert prepared.status_code==201,prepared.text
    assert prepared.json()["approval"]["requiredApprovals"]==2
    assert prepared.json()["run"]["state"]=="awaiting_approval"


def test_same_key_races_one_atomic_triple_and_original_snapshot_timestamp(intents):
    a=intents
    with ThreadPoolExecutor(max_workers=3) as pool:
        items=list(pool.map(lambda _:create_intent(a),range(3)))
    assert items[0]==items[1]==items[2]
    before=counts(a)
    with ThreadPoolExecutor(max_workers=3) as pool:
        results=list(pool.map(lambda _:create_run(a,items[0]),range(3)))
    assert [r.status_code for r in results]==[201]*3
    assert results[0].json()==results[1].json()==results[2].json()
    assert counts(a)==tuple(n+v for n,v in zip(before,(1,1,1,1,1)))


@pytest.mark.parametrize("change",["suspended-user","disabled-subject","disabled-business","revoked-kernel","role","workspace","version","spec","digest","node","containment"])
def test_replay_rechecks_current_authority_and_intent(intents,change):
    a=intents;item=create_intent(a);first=create_run(a,item);assert first.status_code==201,first.text
    with psycopg.connect(a.e.owner) as conn:
        if change=="suspended-user":conn.execute("UPDATE public.users SET status='suspended' WHERE user_id=%s",(a.user,))
        if change=="disabled-subject":conn.execute("UPDATE inv.business_subjects SET enabled=false WHERE subject_id=%s",(a.jwt.subject("requester"),))
        if change=="disabled-business":conn.execute("UPDATE inv.business_projects SET enabled=false WHERE project_id=%s",(a.e.project,))
        if change=="revoked-kernel":conn.execute("UPDATE inv.project_grants SET enabled=false WHERE project_id=%s AND subject_id=%s",(a.e.project,a.jwt.subject("requester")))
        if change=="role":conn.execute("UPDATE public.project_members SET role_code='viewer' WHERE project_id=%s AND user_id=%s",(a.e.project,a.user))
        if change=="workspace":conn.execute("UPDATE public.workspaces SET status='suspended' WHERE workspace_id=%s",(a.workspace_id,))
        if change=="version":conn.execute("UPDATE public.workloads SET version=version+1 WHERE workload_id=%s",(item["workload"]["workloadId"],))
        if change=="spec":conn.execute("UPDATE public.workloads SET spec=jsonb_set(spec,'{workspaceId}',to_jsonb(%s::text)) WHERE workload_id=%s",(new_id("wsp"),item["workload"]["workloadId"]))
        if change=="digest":conn.execute("UPDATE public.workloads SET spec_sha256=%s WHERE workload_id=%s",("f"*64,item["workload"]["workloadId"]))
        if change=="node":conn.execute("UPDATE inv.project_nodes SET enabled=false WHERE project_id=%s",(a.e.project,))
        if change=="containment":conn.execute("UPDATE inv.tenant_controls SET kill_switch=true WHERE tenant_id=%s",(a.e.tenant,))
    before=counts(a)
    replay=create_run(a,item)
    assert replay.status_code in (403,409),replay.text
    assert counts(a)==before


@pytest.mark.parametrize("etag",[None,'W/"workspace-v1"','"workspace-v01"','workspace-v1','"workspace-v1", "workspace-v2"','"workspace-v9007199254740992"'])
def test_exact_strong_etag_required_before_metadata_write(intents,etag):
    a=intents;headers=a.headers()
    if etag is not None:headers["If-Match"]=etag
    before=counts(a)
    r=a.http.post(a.base,json=a.input,headers=headers)
    assert r.status_code==422,r.text
    assert counts(a)==before


@pytest.mark.parametrize("change",[{"actor":"forged"},{"riskLevel":"L0"},{"resources":{"cpuMillis":1,"memoryBytes":8388607,"gpuCount":0,"minVramBytes":0}},{"command":["/bin/sh"]},{"timeoutSeconds":31},{"imageDigest":"sha256:"+"b"*64}])
def test_closed_input_profile_and_node_minima(intents,change):
    a=intents
    r=a.http.post(a.base,json={**a.input,**change},headers=a.ws_headers())
    assert r.status_code in (403,422),r.text
    assert a.http.get(a.base,headers=a.headers()).json()["items"]==[]


def test_pagination_and_no_silent_invalid_intent_filtering(intents):
    a=intents;items=[create_intent(a,key=f"intent-{n}") for n in range(3)]
    result=a.http.get(a.base+"?limit=2",headers=a.headers()).json()
    assert [i["workload"]["workloadId"] for i in result["items"]]==sorted(i["workload"]["workloadId"] for i in items)[:2]
    last=a.http.get(a.base+"?limit=2&after="+result["nextCursor"],headers=a.headers()).json()
    assert len(last["items"])==1 and last["nextCursor"] is None
    with psycopg.connect(a.e.owner) as conn:
        conn.execute("UPDATE public.workloads SET spec_sha256=%s WHERE workload_id=%s",("e"*64,items[0]["workload"]["workloadId"]))
    assert a.http.get(a.base,headers=a.headers()).status_code==409


def test_write_failure_rolls_back_kernel_public_mapping_event_and_ledger(intents):
    a=intents;item=create_intent(a);before=counts(a)
    with psycopg.connect(a.e.owner) as conn:
        # Isolated failure injection uses a real DB trigger, never a production bypass.
        conn.execute("CREATE FUNCTION public.reject_isolated_first_run() RETURNS trigger LANGUAGE plpgsql AS $$ BEGIN RAISE EXCEPTION 'isolated write failure'; END $$")
        conn.execute("CREATE TRIGGER reject_isolated_first_run BEFORE INSERT ON inv.business_runs FOR EACH ROW EXECUTE FUNCTION public.reject_isolated_first_run()")
    try:
        assert create_run(a,item).status_code==500
        assert counts(a)==before
    finally:
        with psycopg.connect(a.e.owner) as conn:
            conn.execute("DROP TRIGGER reject_isolated_first_run ON inv.business_runs")
            conn.execute("DROP FUNCTION public.reject_isolated_first_run()")
    assert create_run(a,item).status_code==201


def test_helper_privileges_rls_and_missing_context_are_real_not_superuser_results(intents):
    a=intents
    with psycopg.connect(a.e.runtime) as conn:
        row=conn.execute("SELECT rolcanlogin,rolsuper,rolbypassrls,rolinherit FROM pg_roles WHERE rolname='inv_first_workspace_writer'").fetchone()
        assert row==(False,False,False,False)
        assert not conn.execute("SELECT pg_has_role(current_user,'inv_first_workspace_writer','MEMBER')").fetchone()[0]
        assert not conn.execute("SELECT has_function_privilege('inv_app','inv.append_first_workspace_run(text,text,text,text,bigint,bigint,text,text)','EXECUTE')").fetchone()[0]
        assert conn.execute("SELECT bool_and(relrowsecurity AND relforcerowsecurity) FROM pg_class WHERE oid IN ('public.workloads'::regclass,'public.runs'::regclass,'inv.business_runs'::regclass)").fetchone()[0]
        assert all('search_path=pg_catalog' in config and 'row_security=on' in config for (config,) in conn.execute("SELECT proconfig FROM pg_proc WHERE proname IN ('append_first_workspace_run','append_first_workspace_intent')"))
    item=create_intent(a)
    for subject,tenant in [(None,a.e.tenant),(a.jwt.subject("requester"),a.e.other)]:
        with psycopg.connect(a.e.runtime) as conn:
            conn.execute("SELECT set_config('inv.tenant_id',%s,true)",(tenant,))
            if subject:conn.execute("SELECT set_config('inv.first_workspace_subject',%s,true)",(subject,))
            with pytest.raises(psycopg.errors.InsufficientPrivilege):
                conn.execute("SELECT inv.append_first_workspace_run(%s,%s,%s,%s,1,1,%s,%s)",(a.e.project,a.workspace_id,item["workload"]["workloadId"],new_id("run"),item["workloadSha256"],canonical(item["workload"]).decode()))
    # Connection-local context is transaction-local on success and rollback.
    with psycopg.connect(a.e.runtime) as conn:
        for rollback in (False,True):
            conn.execute("SELECT set_config('inv.first_workspace_subject',%s,true)",(a.jwt.subject("requester"),))
            conn.rollback() if rollback else conn.commit()
            assert not conn.execute("SELECT nullif(current_setting('inv.first_workspace_subject',true),'')").fetchone()[0]
            conn.rollback()


def test_cross_project_and_auth_and_http_bounds_are_not_inferred_ready(intents):
    a=intents
    assert a.http.get(a.base).status_code==401
    assert a.http.get(a.base,headers=a.headers("alice")).status_code==403
    assert a.http.post(a.base,json={**a.input,"objective":"한"*30000},headers=a.ws_headers()).status_code==413
    with psycopg.connect(a.e.owner) as conn:
        conn.execute("UPDATE public.workspaces SET status='provisioning' WHERE workspace_id=%s",(a.workspace_id,))
    assert a.http.get(a.base,headers=a.headers()).status_code==403
    assert a.http.post(a.base,json=a.input,headers=a.ws_headers()).status_code==403


def test_epoch_change_refuses_initial_and_replay_without_partial_writes(intents):
    a=intents;item=create_intent(a);assert create_run(a,item).status_code==201
    with psycopg.connect(a.e.owner) as conn:conn.execute("UPDATE inv.control_epoch SET epoch=%s",(str(uuid4()),))
    before=counts(a)
    assert create_run(a,item).status_code==503
    assert create_run(a,item,key="new-key").status_code==503
    assert counts(a)==before


def test_actual_business_role_cannot_call_or_assume_writer(intents):
    from psycopg.conninfo import make_conninfo
    a=intents;role="inv_first_deny_"+uuid4().hex[:16];password=uuid4().hex
    with psycopg.connect(a.e.owner) as conn:
        conn.execute(sql.SQL("CREATE ROLE {} LOGIN PASSWORD {} NOSUPERUSER NOBYPASSRLS").format(sql.Identifier(role),sql.Literal(password)))
        conn.execute(sql.SQL("GRANT inv_app TO {}").format(sql.Identifier(role)))
    try:
        with psycopg.connect(make_conninfo(a.e.owner,user=role,password=password)) as conn:
            with pytest.raises(psycopg.errors.InsufficientPrivilege):
                conn.execute("SELECT inv.append_first_workspace_run('x','x','x','x',1,1,'x','x')")
            conn.rollback()
            with pytest.raises(psycopg.errors.InsufficientPrivilege):conn.execute("SET ROLE inv_first_workspace_writer")
    finally:
        with psycopg.connect(a.e.owner) as conn:conn.execute(sql.SQL("DROP ROLE {}").format(sql.Identifier(role)))


def test_hostile_search_path_cannot_redirect_qualified_helper_writes(intents):
    a=intents;item=create_intent(a);run_id=new_id("run")
    with a.e.db.transaction(a.e.tenant) as conn:
        conn.execute("SELECT set_config('inv.first_workspace_subject',%s,true)",(a.jwt.subject("requester"),))
        conn.execute("CREATE TEMP TABLE runs(marker text)")
        conn.execute("SET LOCAL search_path=pg_temp,public,inv,pg_catalog")
        conn.execute("SELECT inv.append_first_workspace_run(%s,%s,%s,%s,1,1,%s,%s)",
            (a.e.project,a.workspace_id,item["workload"]["workloadId"],run_id,item["workloadSha256"],canonical(item["workload"]).decode()))
        assert conn.execute("SELECT count(*) AS n FROM pg_temp.runs").fetchone()["n"]==0
        assert conn.execute("SELECT run_id FROM inv.business_runs WHERE run_id=%s",(run_id,)).fetchone()["run_id"]==run_id


def test_create_replay_races_existing_first_prepare_without_new_run_or_state_reset(intents):
    a=intents;item=create_intent(a);created=create_run(a,item);assert created.status_code==201
    run_id=created.json()["run"]["runId"]
    raw=canonical(dict(format="workspace-snapshot:1",workspaceId=a.workspace_id,directories=[],files=[]))
    data=dict(startId=str(uuid4()),stepId="isolated-step",workload=item["workload"],expectedVersion=1,snapshotBase64=base64.b64encode(raw).decode(),targetNodeId=a.e.node)
    before=counts(a)
    with ThreadPoolExecutor(max_workers=2) as pool:
        first=pool.submit(a.http.post,f"/v1/projects/{a.e.project}/runs/{run_id}/start/prepare",json=data,headers=a.headers(key="first-prepare"))
        replay=pool.submit(create_run,a,item)
        assert first.result(timeout=10).status_code==201
        assert replay.result(timeout=10).json()==created.json()
    current=a.http.get(f"/v1/projects/{a.e.project}/runs/{run_id}",headers=a.headers()).json()
    assert current["state"]=="awaiting_approval" and current["version"]==4
    assert counts(a)[:3]==before[:3]
