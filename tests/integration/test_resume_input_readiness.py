"""Current pending input is read from a real prepared recovery, then expires."""

import sys
from uuid import uuid4

import psycopg
import pytest

from saintvision.ids import new_id
from test_workspace_api import workspace_http, prepare
from test_node_delivery import remote
from test_node_runtime import node_runtime, active, container
from test_snapshots import storage
from test_approvals import approval
from test_tool_admission import gateway

pytestmark = [
    pytest.mark.postgres,
    pytest.mark.skipif(sys.platform != "linux", reason="Linux recovery runtime"),
]


def test_real_prepared_recovery_is_readable_until_cancelled(workspace_http):
    a = workspace_http
    prepared = prepare(a)
    # Create only business metadata for the same workspace. Execution input
    # above came from the actual authenticated kernel prepare path.
    user = new_id("user")
    with psycopg.connect(a.e.owner) as c:
        c.execute(
            "INSERT INTO public.tenants(tenant_id,slug,display_name) VALUES(%s,%s,'resume input')",
            (a.e.tenant, uuid4().hex),
        )
        c.execute(
            "INSERT INTO public.users(tenant_id,user_id,external_subject,display_name) VALUES(%s,%s,%s,'tester')",
            (a.e.tenant, user, user),
        )
        c.execute(
            "INSERT INTO public.projects(tenant_id,project_id,code,display_name) VALUES(%s,%s,'resume','resume')",
            (a.e.tenant, a.e.project),
        )
        c.execute(
            "INSERT INTO public.workspaces(tenant_id,project_id,workspace_id,name,created_by_user_id) VALUES(%s,%s,%s,'resume',%s)",
            (a.e.tenant, a.e.project, a.workspace_id, user),
        )

    def read():
        with psycopg.connect(a.e.owner) as c:
            c.execute("SET LOCAL ROLE inv_app")
            c.execute("SELECT set_config('inv.tenant_id',%s,true)", (a.e.tenant,))
            return c.execute(
                "SELECT prepared,kind,run_id,step_id,snapshot_bytes FROM public.workspace_input_state(%s,%s)",
                (a.e.tenant, a.workspace_id),
            ).fetchone()

    row = read()
    assert row[:4] == (True, "resume", a.run["runId"], "public-step")
    assert 0 < row[4] <= 65536
    a.e.runs.transition(
        a.e.tenant, a.run["runId"], "cancelled", expected_version=prepared["run"]["version"]
    )
    assert read() is None
