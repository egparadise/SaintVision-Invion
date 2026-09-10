import base64
from copy import deepcopy
import hashlib
from uuid import uuid4
import pytest
from inv.errors import DomainError
from inv.contracts import validate_contract
from inv.workspace_files import canonical
from inv.workspace_resume import bounded_snapshot, workspace_output
from test_sandbox_contracts import launch
from inv.sandbox import compile_launch


def snapshot(workspace, content=b"frozen"):
    return {
        "format": "workspace-snapshot:1",
        "workspaceId": workspace,
        "directories": [],
        "files": [
            {
                "path": "file",
                "executable": False,
                "sha256": hashlib.sha256(content).hexdigest(),
                "sizeBytes": len(content),
                "dataBase64": base64.b64encode(content).decode(),
            }
        ],
    }


def test_workspace_launch_requires_explicit_bound_content(launch):
    w, profile = launch
    raw = canonical(snapshot(w["workspaceId"]))
    ref = {
        "resumeId": str(uuid4()),
        "checkoutId": str(uuid4()),
        "sourceAttempt": 1,
        "sourceStepId": "before",
        "stepId": "after",
        "inputSha256": hashlib.sha256(raw).hexdigest(),
        "inputSizeBytes": len(raw),
    }
    w["workspaceResume"] = ref
    with pytest.raises(DomainError, match="AUTH-0044"):
        compile_launch(w, profile)
    input = {
        "resumeId": ref["resumeId"],
        "stepId": "after",
        "sha256": ref["inputSha256"],
        "sizeBytes": len(raw),
        "dataBase64": base64.b64encode(raw).decode(),
    }
    plan = compile_launch(w, profile, workspace_input=input)
    assert plan["workspaceMode"] == "restored" and not plan["hostAccess"]
    del plan["workspaceInput"]
    with pytest.raises(DomainError):
        validate_contract("SandboxLaunchSpec", plan)


@pytest.mark.parametrize(
    "field", ["resumeId", "stepId", "inputSha256", "workspaceId", "fileHash", "oversized"]
)
def test_workspace_output_must_match_approved_input_and_bounded_files(launch, field):
    w, _ = launch
    snap = snapshot(w["workspaceId"])
    input = {"resumeId": str(uuid4()), "stepId": "after", "sha256": "a" * 64}
    plan = {"workspaceInput": input, "workspaceId": w["workspaceId"]}
    value = {
        "resumeId": input["resumeId"],
        "stepId": "after",
        "inputSha256": "a" * 64,
        "snapshot": snap,
    }
    assert workspace_output({"workspace": value}, plan) == canonical(snap)
    if field in {"resumeId", "stepId", "inputSha256"}:
        value[field] = "changed"
    elif field == "workspaceId":
        snap["workspaceId"] = "wsp_01J00000000000000000000000"
    elif field == "fileHash":
        snap["files"][0]["sha256"] = "b" * 64
    else:
        value["snapshot"] = snapshot(w["workspaceId"], b"x" * 32769)
    with pytest.raises(DomainError):
        workspace_output({"workspace": value}, plan)
