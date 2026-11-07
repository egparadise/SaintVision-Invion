"""New selected-intent HTTP path through real isolated Linux Node receipts/output.

Synthetic fixture accounts and certificates are CI-only, never real user votes or
five-PC acceptance. No public workload/Run/business mapping is seeded for this Run.
"""
import sys
import psycopg
import pytest
from inv.dispatch import DeliveryWorker
from inv.ids import new_id
from test_workspace_start import first, prepare, enqueue, run
from test_workspace_api import approve
from test_node_delivery import remote
from test_node_runtime import node_runtime, active
from test_tool_admission import gateway
from test_snapshots import storage
from test_approvals import approval, count

pytestmark = [pytest.mark.postgres, pytest.mark.skipif(sys.platform != "linux", reason="Linux first Workspace execution")]


def test_selected_intent_atomic_run_two_real_fixture_votes_and_committed_output(first):
    a = first
    users = {name: new_id("usr") for name in ("requester", "alice", "bob")}
    with psycopg.connect(a.e.owner) as conn:
        conn.execute("INSERT INTO public.tenants(tenant_id,slug,display_name) VALUES(%s,%s,'Isolated first intent')", (a.e.tenant,a.e.tenant))
        conn.execute("INSERT INTO public.projects(tenant_id,project_id,code,display_name) VALUES(%s,%s,%s,'Isolated first intent')", (a.e.tenant,a.e.project,a.e.project))
        for actor,user in users.items():
            conn.execute("INSERT INTO public.users(tenant_id,user_id,external_subject,display_name) VALUES(%s,%s,%s,%s)", (a.e.tenant,user,a.jwt.subject(actor),actor))
            conn.execute("INSERT INTO public.project_members(tenant_id,project_id,user_id,role_code) VALUES(%s,%s,%s,%s)", (a.e.tenant,a.e.project,user,"operator" if actor=="requester" else "approver"))
            conn.execute("INSERT INTO inv.business_subjects(tenant_id,subject_id,user_id) VALUES(%s,%s,%s)", (a.e.tenant,a.jwt.subject(actor),user))
        conn.execute("INSERT INTO inv.business_projects(tenant_id,project_id) VALUES(%s,%s)", (a.e.tenant,a.e.project))
        conn.execute("INSERT INTO public.workspaces(tenant_id,project_id,workspace_id,name,status,created_by_user_id) VALUES(%s,%s,%s,'Isolated ready Workspace','ready',%s)", (a.e.tenant,a.e.project,a.workspace_id,users["requester"]))
    base=f"/v1/projects/{a.e.project}/workspaces/{a.workspace_id}/first-intents"
    page=a.http.get(base,headers=a.headers())
    assert page.status_code==200,page.text
    assert page.json()["items"]==[]
    resources={**a.workload["resources"],"cpuMillis":min(500,a.workload["resources"]["cpuMillis"]),"memoryBytes":min(67108864,a.workload["resources"]["memoryBytes"])}
    response=a.http.post(base,json=dict(objective="Execute the actual isolated frozen Python program",imageDigest=a.workload["imageDigest"],command=a.workload["command"],resources=resources,timeoutSeconds=min(30,a.workload["timeoutSeconds"])),
        headers={**a.headers(key="selected-intent"),"If-Match":'"workspace-v1"'})
    assert response.status_code==201,response.text
    item=response.json()
    create_url=base+"/"+item["workload"]["workloadId"]+"/runs"
    response=a.http.post(create_url,json={},headers={**a.headers(key="selected-run"),"If-Match":item["intentEtag"]})
    assert response.status_code==201,response.text
    a.run=response.json()["run"];a.workload=item["workload"]
    a.url=f'/v1/projects/{a.e.project}/runs/{a.run["runId"]}'
    a.prepare_input.update(workload=a.workload,expectedVersion=a.run["version"])
    assert a.run["state"]=="draft" and a.run["attempt"]==0
    prepare(a)
    assert enqueue(a).status_code==403
    assert count(a,"execution_attempts")==0 and count(a,"execution_deliveries")==0
    approve(a)  # Existing production challenge/decision routes, distinct isolated alice/bob.
    assert enqueue(a).status_code==202
    assert DeliveryWorker(a.e.db,a.delivery,output_provider=a.storage.provider).once(a.e.tenant)=="stopped"
    assert run(a)["state"]=="succeeded" and run(a)["attempt"]==1 and active(a)==0
    result=a.http.get(a.url+"/result",headers=a.headers())
    assert result.status_code==200,result.text
    served=result.json()
    assert served["runId"]==a.run["runId"] and served["completedAt"]
    assert served["output"]["sha256"] and served["evidence"]["evidenceId"] and served["stopReceipt"]
    with a.e.db.transaction(a.e.tenant) as conn:
        assert conn.execute("SELECT state FROM public.runs WHERE run_id=%s",(a.run["runId"],)).fetchone()["state"]=="draft"
        assert conn.execute("SELECT node_id FROM public.workspaces WHERE workspace_id=%s",(a.workspace_id,)).fetchone()["node_id"] is None
