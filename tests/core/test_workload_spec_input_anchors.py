"""Input-boundary rejection checks for the six WorkloadSpec anchor modules.

These tests deliberately pass an empty workload before any database, hash, or runtime work.  The
shard-recovery outer request is excluded from the direct set because its ShardRecoveryPrepareInput
schema already validates the nested WorkloadSpec before the method's second validation call.
"""

from datetime import datetime, timedelta, timezone
from types import SimpleNamespace
from uuid import uuid4

import pytest

from inv.approvals import ApprovalStore
from inv.errors import DomainError
from inv.model_runtime import ModelRuntimeStore
from inv.sandbox import compile_launch
from inv.tooling import NodePrincipal, ToolGateway
from inv.workspace_resume import WorkspaceResume
from inv.ids import new_id


def _principal(tenant):
    return SimpleNamespace(tenant_id=tenant, subject_id="usr_test")


def _command(tenant, project, run_id, approval_id, recovery_epoch):
    return {
        "commandId": str(uuid4()),
        "approvalId": approval_id,
        "runId": run_id,
        "tenantId": tenant,
        "projectId": project,
        "actionDigest": "a" * 64,
        "policyVersion": "policy-test",
        "recoveryEpoch": recovery_epoch,
        "expiresAt": (datetime.now(timezone.utc) + timedelta(seconds=30)).isoformat(),
    }


def _assert_invalid(call):
    with pytest.raises(DomainError, match="WorkloadSpec: invalid contract"):
        call()


def test_approval_request_rejects_workload_before_state_access():
    tenant, run_id = str(uuid4()), str(uuid4())
    _assert_invalid(
        lambda: ApprovalStore.__new__(ApprovalStore).request(
            _principal(tenant), run_id, {}, {}, policy_version="p", expected_version=1, key="k"
        )
    )


def test_model_runtime_prepare_rejects_workload_before_state_access():
    tenant, project, run_id = str(uuid4()), "prj_test", str(uuid4())
    _assert_invalid(
        lambda: ModelRuntimeStore.__new__(ModelRuntimeStore).prepare(
            _principal(tenant), project, run_id, {}, {}, key="k"
        )
    )


def test_sandbox_compile_rejects_workload_before_profile_access():
    _assert_invalid(lambda: compile_launch({}, None))


def test_tool_claim_rejects_workload_after_command_before_runtime_access():
    tenant, project, run_id, approval_id, epoch = (
        str(uuid4()),
        new_id("prj"),
        new_id("run"),
        new_id("apr"),
        str(uuid4()),
    )
    command = _command(tenant, project, run_id, approval_id, epoch)
    node = NodePrincipal(tenant, "nod_01ARZ3NDEKTSV4RRFFQ69G5FAV")
    _assert_invalid(
        lambda: ToolGateway.__new__(ToolGateway).claim(
            node, command, {}, {}, policy=None, runtime=None
        )
    )


def test_workspace_resume_prepare_rejects_workload_before_database_access():
    tenant, project, run_id = str(uuid4()), "prj_test", str(uuid4())
    _assert_invalid(
        lambda: WorkspaceResume.__new__(WorkspaceResume).prepare(
            tenant,
            project,
            run_id,
            str(uuid4()),
            str(uuid4()),
            "step-next",
            {},
            expected_version=1,
        )
    )
