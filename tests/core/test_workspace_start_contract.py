import base64
from copy import deepcopy
import hashlib
from uuid import uuid4
import pytest
from inv.contracts import validate_contract
from inv.errors import DomainError
from inv.ids import new_id
from inv.sandbox import compile_launch
from inv.workspace_files import canonical
from inv.workspace_resume import workspace_output
from test_sandbox_contracts import launch
from test_workspace_resume_contract import snapshot


@pytest.fixture
def initialized(launch):
    w, profile = launch
    raw = canonical(snapshot(w["workspaceId"]))
    ref = dict(
        startId=str(uuid4()),
        stepId="first",
        inputSha256=hashlib.sha256(raw).hexdigest(),
        inputSizeBytes=len(raw),
        nodeId=new_id("nod"),
        cpuResourceId=new_id("res"),
        memoryResourceId=new_id("res"),
        profileVersion=profile.version,
        policyVersion="test:1",
    )
    w["workspaceStart"] = ref
    input = dict(
        startId=ref["startId"],
        stepId="first",
        sha256=ref["inputSha256"],
        sizeBytes=len(raw),
        dataBase64=base64.b64encode(raw).decode(),
    )
    return w, profile, input


def test_initial_launch_requires_approved_input_and_distinct_wire_identity(initialized):
    w, profile, input = initialized
    with pytest.raises(DomainError, match="AUTH-0044"):
        compile_launch(w, profile)
    plan = compile_launch(w, profile, workspace_input=input)
    assert plan["workspaceMode"] == "initialized" and not plan["hostAccess"]
    invalid = deepcopy(plan)
    invalid["workspaceInput"]["resumeId"] = str(uuid4())
    with pytest.raises(DomainError):
        validate_contract("SandboxLaunchSpec", invalid)
    invalid = deepcopy(plan)
    invalid["workspaceMode"] = "restored"
    with pytest.raises(DomainError):
        validate_contract("SandboxLaunchSpec", invalid)
    invalid = deepcopy(plan)
    del invalid["workspaceInput"]["startId"]
    with pytest.raises(DomainError):
        validate_contract("SandboxLaunchSpec", invalid)


@pytest.mark.parametrize("field", ["startId", "stepId", "inputSha256", "resumeId"])
def test_first_output_cannot_be_relabelled_as_another_execution(initialized, field):
    w, profile, input = initialized
    plan = compile_launch(w, profile, workspace_input=input)
    value = dict(
        startId=input["startId"],
        stepId="first",
        inputSha256=input["sha256"],
        snapshot=snapshot(w["workspaceId"]),
    )
    assert workspace_output({"workspace": value}, plan) == canonical(value["snapshot"])
    value[field] = "changed"
    with pytest.raises(DomainError):
        workspace_output({"workspace": value}, plan)
