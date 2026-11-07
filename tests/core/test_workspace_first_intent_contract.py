"""Exact R1 DTO/headers and node-memory minima, no live service prerequisites."""
from copy import deepcopy
import json
from pathlib import Path
import pytest
from inv.contracts import catalog, validate_contract
from inv.errors import DomainError
from inv.workspace_intents import header_versions

GOLDEN = Path(__file__).resolve().parents[2]/"apps/web/tests/fixtures/first-workspace-golden.json"


@pytest.fixture
def intent():
    golden=json.loads(GOLDEN.read_text("utf8"))
    w=golden["workload"]
    from inv.approvals import digest
    return dict(workspaceId=w["workspaceId"],workspaceVersion=1,workloadVersion=1,
        workloadSha256=digest(w),intentEtag=f'"workspace-v1-workload-v1-sha256-{digest(w)}"',
        workload=w,observedAt="2026-11-07T09:00:00Z")


def test_scoped_response_contracts_bind_unchanged_workload_and_control_run(intent):
    golden=json.loads(GOLDEN.read_text("utf8"))
    profile=dict(nodeId=intent["workload"]["targetNodeId"],profileVersion="isolated-cpu",images=[intent["workload"]["imageDigest"]],
        executables=["/usr/local/bin/python3"],maxCpuMillis=500,minMemoryBytes=8388608,maxMemoryBytes=67108864,maxTimeoutSeconds=30,terminalAllowed=False)
    validate_contract("WorkspaceFirstProfile",profile)
    validate_contract("WorkspaceFirstIntent",intent)
    validate_contract("WorkspaceFirstIntentPage",dict(projectId=intent["workload"]["projectId"],workspaceId=intent["workspaceId"],workspaceVersion=1,
        profile=profile,items=[intent],nextCursor=None,observedAt=intent["observedAt"]))
    validate_contract("WorkspaceFirstRunCreateResult",dict(run=golden["run"],intent=intent,requesterId="oidc:"+"a"*64,observedAt=intent["observedAt"]))
    for bad in [dict(profile,minMemoryBytes=1),dict(profile,terminalAllowed=True),dict(profile,maxMemoryBytes=8388607)]:
        with pytest.raises(DomainError):validate_contract("WorkspaceFirstProfile",bad)


def test_closed_intent_input_cannot_assert_actor_or_tiny_memory(intent):
    w=intent["workload"]
    data={k:w[k] for k in ["imageDigest","command","resources","timeoutSeconds"]}
    data["objective"]="Isolated CPU task"
    validate_contract("WorkspaceFirstIntentCreateInput",data)
    for field in ["requestedBy","tenantId","riskLevel","grant","policy","workspaceId"]:
        with pytest.raises(DomainError):validate_contract("WorkspaceFirstIntentCreateInput",{**data,field:"forged"})
    tiny=deepcopy(data);tiny["resources"]["memoryBytes"]=8388607
    with pytest.raises(DomainError):validate_contract("WorkspaceFirstIntentCreateInput",tiny)
    nul=deepcopy(data);nul["command"]=["/usr/local/bin/python3", "bad\x00argument"]
    with pytest.raises(DomainError):validate_contract("WorkspaceFirstIntentCreateInput",nul)
    # The old generic resource contract is not tightened by this pilot-specific DTO.
    validate_contract("ResourceRequest",tiny["resources"])


def test_original_generic_resource_root_has_one_matching_alternative():
    from jsonschema import Draft202012Validator
    root=Draft202012Validator(catalog())
    # A nested pilot-resource DTO must not be appended as an overlapping root
    # oneOf alternative that makes existing canonical ResourceRequest invalid.
    for memory in (1,8388608,67108864):
        assert root.is_valid(dict(cpuMillis=1,memoryBytes=memory,gpuCount=0,minVramBytes=0))


@pytest.mark.parametrize("value",[None,'"workspace-v01"','W/"workspace-v1"','"workspace-v1", "workspace-v2"','"workspace-v9007199254740992"'])
def test_exact_header_versions_reject_weak_noncanonical_or_unsafe(value):
    with pytest.raises(DomainError):header_versions(value)


def test_etag_parser_keeps_workspace_workload_digest_bound():
    assert header_versions('"workspace-v1"')==("1",)
    assert header_versions('"workspace-v1-workload-v2-sha256-'+"a"*64+'"',intent=True)==("1","2","a"*64)
