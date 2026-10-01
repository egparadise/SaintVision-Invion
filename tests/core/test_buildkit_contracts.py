"""Strict contract boundary for the first S08-BE BuildKit implementation card.

These are contracts only: no public route or builder daemon is claimed here.  The tests pin the
unsafe choices that must remain compiler-owned before an adapter is allowed to execute a build.
"""

from copy import deepcopy
import json
from pathlib import Path

import pytest

from inv.contracts import validate_contract
from inv.errors import DomainError


ULID = "01ARZ3NDEKTSV4RRFFQ69G5FAV"
TENANT = "123e4567-e89b-12d3-a456-426614174000"
SHA1 = "a" * 40
DIGEST = "b" * 64
TRACE = "c" * 32
ROOT = Path(__file__).resolve().parents[2]


def _request() -> dict:
    return {
        "apiVersion": "inv.saintvision.ai/v1alpha1",
        "kind": "BuildRequest",
        "tenantId": TENANT,
        "projectId": f"prj_{ULID}",
        "workspaceId": f"wsp_{ULID}",
        "sourceCommitSha": SHA1,
        "sourceTreeSha": "d" * 40,
        "contextPath": "services/worker",
        "dockerfilePath": "services/worker/Dockerfile",
        "targetPlatform": "linux/amd64",
        "targetStage": "runtime",
        "networkPolicyId": "none",
        "cachePolicyId": "cachepol_s08-default",
        "secretRefIds": [f"sec_{ULID}"],
        "timeoutSeconds": 300,
    }


def _plan() -> dict:
    return {
        "apiVersion": "inv.saintvision.ai/v1alpha1",
        "kind": "BuildPlan",
        "tenantId": TENANT,
        "projectId": f"prj_{ULID}",
        "workspaceId": f"wsp_{ULID}",
        "traceId": TRACE,
        "requestDigest": DIGEST,
        "actionDigest": "c" * 64,
        "policyDecisionId": "policy-s08-build-1",
        "policyVersion": "s08-build-v1",
        "policyExpiresAt": "2026-10-01T03:00:00Z",
        "builderInstanceId": "builder-rootless-01",
        "builderProfileId": "buildkit-rootless-v1",
        "builderObservationDigest": "a" * 64,
        "recoveryEpoch": 7,
        "rootless": True,
        "privileged": False,
        "hostAccess": False,
        "networkMode": "none",
        "networkPolicyId": "none",
        "egressAllowlistDigest": "0" * 64,
        "devices": [],
        "binds": [],
        "budget": {
            "cpuMillis": 2000,
            "memoryBytes": 2 * 1024**3,
            "storageBytes": 10 * 1024**3,
        },
        "lease": {
            "leaseId": f"lse_{ULID}",
            "resourceId": f"res_{ULID}",
            "fencingToken": "123e4567-e89b-12d3-a456-426614174000:7",
            "expiresAt": "2026-10-01T03:00:00Z",
        },
        "cacheNamespaceDigest": "e" * 64,
        "secretRefsDigest": "f" * 64,
        "resolvedBaseImageDigests": ["sha256:" + "1" * 64],
    }


def _receipt() -> dict:
    return {
        "apiVersion": "inv.saintvision.ai/v1alpha1",
        "kind": "BuildReceipt",
        "tenantId": TENANT,
        "projectId": f"prj_{ULID}",
        "workspaceId": f"wsp_{ULID}",
        "traceId": TRACE,
        "planDigest": DIGEST,
        "sourceCommitSha": SHA1,
        "sourceTreeSha": "d" * 40,
        "outputImageDigest": "sha256:" + "2" * 64,
        "outputConfigDigest": "sha256:" + "3" * 64,
        "sbomEvidenceDigest": "4" * 64,
        "scanEvidenceDigest": "5" * 64,
        "cacheInputDigest": "6" * 64,
        "cacheOutputDigest": "7" * 64,
        "networkSummaryDigest": "8" * 64,
        "startedAt": "2026-10-01T02:00:00Z",
        "finishedAt": "2026-10-01T02:01:00Z",
        "result": "succeeded",
        "cleanup": {
            "leaseReleased": True,
            "builderClaimReleased": True,
            "cgroupRemoved": True,
            "cacheDisposition": "retained",
            "verifiedAt": "2026-10-01T02:01:01Z",
            "physicalReceipt": _physical_cleanup_receipt(),
            "physicalReceiptDigest": "a" * 64,
        },
        "auditEvents": [
            {
                "event": "cleanup_verified",
                "traceId": TRACE,
                "timestamp": "2026-10-01T02:01:01Z",
                "decisionId": "policy-s08-build-1",
                "inputDigest": DIGEST,
                "outputDigest": "9" * 64,
            }
        ],
    }


def _failed_receipt() -> dict:
    receipt = _receipt()
    receipt["result"] = "failed"
    for field in (
        "outputImageDigest",
        "outputConfigDigest",
        "sbomEvidenceDigest",
        "scanEvidenceDigest",
        "cacheOutputDigest",
    ):
        receipt[field] = None
    receipt["cleanup"]["cacheDisposition"] = "quarantined"
    receipt["cleanup"]["physicalReceipt"]["cacheDisposition"] = "quarantined"
    receipt["cleanup"]["physicalReceipt"]["partialExportDisposition"] = "quarantined"
    return receipt


def _daemon_identity() -> dict:
    return {
        "pid": 4242,
        "processUid": 1000,
        "processStartTicks": 987654,
        "comm": "buildkitd",
    }


def _health_receipt() -> dict:
    return {
        "schemaVersion": "build-provider-health-receipt:1",
        "writerKind": "node-agent",
        "nodeId": f"nod_{ULID}",
        "builderInstanceId": "builder-rootless-01",
        "builderProfileId": "buildkit-rootless-v1",
        "recoveryEpoch": 7,
        "observedAt": "2026-10-01T02:00:00Z",
        "runtimeIdentity": "sha256:" + "1" * 64,
        "daemonIdentity": _daemon_identity(),
        "rootless": True,
        "privileged": False,
        "hostAccess": False,
        "entitlements": [],
        "devices": [],
        "binds": [],
        "buildkitVersion": "v0.20.2",
        "rootlesskitVersion": "v2.3.5",
        "isolation": {
            "userNamespace": True,
            "seccompMode": "filter",
            "lsm": "apparmor",
            "noNewPrivileges": True,
            "cgroupMode": "v2",
        },
        "fieldSources": {
            "daemonIdentity": "node-proc-buildkitd",
            "runtimeIdentity": "node-buildkitd-binary-sha256",
            "rootless": "node-proc-user-namespace",
            "privileged": "node-runtime-security-readback",
            "hostAccess": "node-runtime-security-readback",
            "entitlements": "node-runtime-security-readback",
            "devices": "node-runtime-security-readback",
            "binds": "node-runtime-security-readback",
            "userNamespace": "node-proc-user-namespace",
            "seccompMode": "node-host-security-readback",
            "lsm": "node-host-security-readback",
            "noNewPrivileges": "node-host-security-readback",
            "cgroupMode": "node-host-security-readback",
        },
    }


def _physical_cleanup_receipt() -> dict:
    return {
        "schemaVersion": "build-physical-cleanup-receipt:1",
        "writerKind": "node-agent",
        "buildSessionId": "123e4567-e89b-42d3-a456-426614174000",
        "nodeId": f"nod_{ULID}",
        "resourceId": f"res_{ULID}",
        "leaseId": f"lse_{ULID}",
        "recoveryEpoch": 7,
        "daemonIdentity": _daemon_identity(),
        "stopResult": "stopped",
        "partialExportDisposition": None,
        "cacheDisposition": "retained",
        "builderClaimReleased": True,
        "cgroupRemoved": True,
        "verifiedAt": "2026-10-01T02:01:01Z",
    }


def _dispatch_completed_payload() -> dict:
    return {
        "decisionId": "policy-s08-build-1",
        "bindingDigest": "b" * 64,
        "resourceId": f"res_{ULID}",
        "leaseId": f"lse_{ULID}",
        "evidenceId": f"evd_{ULID}",
        "evidenceDigest": "e" * 64,
    }


def _rejected(contract: str, value: dict) -> None:
    with pytest.raises(DomainError, match="VAL-0002"):
        validate_contract(contract, value)


def test_build_contract_patterns_stay_go_re2_compatible():
    schema = json.loads(
        (ROOT / "contracts" / "v1alpha1" / "core.schema.json").read_text(encoding="utf-8")
    )

    def patterns(value):
        if isinstance(value, dict):
            if "pattern" in value:
                yield value["pattern"]
            for nested in value.values():
                yield from patterns(nested)
        elif isinstance(value, list):
            for nested in value:
                yield from patterns(nested)

    build_defs = {name: value for name, value in schema["$defs"].items() if name.startswith("Build")}
    assert build_defs
    assert all("(?" not in pattern for pattern in patterns(build_defs))


def test_build_contract_enum_vocabularies_are_literal_and_complete():
    schema = json.loads(
        (ROOT / "contracts" / "v1alpha1" / "core.schema.json").read_text(encoding="utf-8")
    )
    defs = schema["$defs"]
    assert defs["BuildPlan"]["properties"]["networkMode"]["enum"] == ["none", "allowlist"]
    assert defs["BuildCleanupReceipt"]["properties"]["cacheDisposition"]["enum"] == [
        "retained",
        "quarantined",
        "purged",
    ]
    assert defs["BuildResult"]["enum"] == ["succeeded", "failed", "cancelled"]
    assert defs["BuildAuditEvent"]["properties"]["event"]["enum"] == [
        "request_validated",
        "policy_bound",
        "builder_claimed",
        "build_started",
        "network_decision",
        "output_verified",
        "build_failed",
        "build_cancelled",
        "cleanup_verified",
        "dispatch_completed",
    ]

    assert defs["BuildProviderHealthReceipt"]["properties"]["writerKind"]["const"] == "node-agent"
    assert defs["BuildPhysicalCleanupReceipt"]["properties"]["writerKind"]["const"] == "node-agent"


@pytest.mark.parametrize(
    "contract,factory",
    [
        ("BuildRequest", _request),
        ("BuildPlan", _plan),
        ("BuildProviderHealthReceipt", _health_receipt),
        ("BuildPhysicalCleanupReceipt", _physical_cleanup_receipt),
        ("BuildDispatchCompletedPayload", _dispatch_completed_payload),
        ("BuildReceipt", _receipt),
    ],
)
def test_build_contract_positive_controls_and_every_top_level_field_is_required(contract, factory):
    value = factory()
    validate_contract(contract, value)
    for field in tuple(value):
        changed = deepcopy(value)
        del changed[field]
        _rejected(contract, changed)


@pytest.mark.parametrize(
    "field,value",
    [
        ("rootless", False),
        ("privileged", True),
        ("hostAccess", True),
        ("devices", ["/dev/kvm"]),
        ("binds", ["/var/run/docker.sock:/var/run/docker.sock"]),
    ],
)
def test_build_plan_isolation_literals_are_not_caller_options(field, value):
    changed = _plan()
    changed[field] = value
    _rejected("BuildPlan", changed)


@pytest.mark.parametrize("field", ["budget", "lease", "cacheNamespaceDigest", "secretRefsDigest", "resolvedBaseImageDigests"])
def test_build_plan_cannot_omit_budget_fencing_cache_or_resolved_bases(field):
    changed = _plan()
    del changed[field]
    _rejected("BuildPlan", changed)


@pytest.mark.parametrize(
    "container,fields",
    [
        ("budget", ("cpuMillis", "memoryBytes", "storageBytes")),
        ("lease", ("leaseId", "resourceId", "fencingToken", "expiresAt")),
    ],
)
def test_build_plan_nested_budget_and_fence_fields_are_load_bearing(container, fields):
    for field in fields:
        changed = _plan()
        del changed[container][field]
        _rejected("BuildPlan", changed)


@pytest.mark.parametrize(
    "mode,policy",
    [("none", "netpol_outbound"), ("allowlist", "none")],
)
def test_build_plan_network_mode_and_policy_are_bound(mode, policy):
    changed = _plan()
    changed["networkMode"] = mode
    changed["networkPolicyId"] = policy
    _rejected("BuildPlan", changed)


@pytest.mark.parametrize(
    "contract,factory,mutate",
    [
        ("BuildPlan", _plan, lambda value: value.__setitem__("networkMode", "host")),
        (
            "BuildReceipt",
            _failed_receipt,
            lambda value: value["cleanup"].__setitem__("cacheDisposition", "reused"),
        ),
        ("BuildReceipt", _receipt, lambda value: value.__setitem__("result", "partial")),
        (
            "BuildReceipt",
            _receipt,
            lambda value: value["auditEvents"][0].__setitem__("event", "secret_exposed"),
        ),
        (
            "BuildRequest",
            _request,
            lambda value: value.__setitem__("networkPolicyId", "NETPOL_untrusted"),
        ),
        (
            "BuildPlan",
            _plan,
            lambda value: value["lease"].__setitem__(
                "fencingToken", "123e4567-e89b-12d3-a456-426614174000:0"
            ),
        ),
        (
            "BuildRequest",
            _request,
            lambda value: value.__setitem__("secretRefIds", ["literal-secret-name"]),
        ),
        (
            "BuildPlan",
            _plan,
            lambda value: value.__setitem__("egressAllowlistDigest", "g" * 64),
        ),
    ],
    ids=[
        "network-mode-enum",
        "cache-disposition-enum",
        "build-result-enum",
        "audit-event-enum",
        "network-policy-id-pattern",
        "fencing-token-pattern",
        "secret-ref-id-pattern",
        "digest-64-hex-pattern",
    ],
)
def test_build_contract_value_domains_are_fail_closed(contract, factory, mutate):
    changed = factory()
    mutate(changed)
    _rejected(contract, changed)


@pytest.mark.parametrize(
    "contract,factory,path,value",
    [
        ("BuildProviderHealthReceipt", _health_receipt, ("writerKind",), "control-plane"),
        ("BuildProviderHealthReceipt", _health_receipt, ("nodeId",), "nod_untrusted"),
        ("BuildProviderHealthReceipt", _health_receipt, ("daemonIdentity", "comm"), "rootlesskit"),
        ("BuildProviderHealthReceipt", _health_receipt, ("isolation", "seccompMode"), "unavailable-ci-reference"),
        ("BuildProviderHealthReceipt", _health_receipt, ("isolation", "lsm"), "unconfined-ci-reference"),
        ("BuildProviderHealthReceipt", _health_receipt, ("fieldSources", "daemonIdentity"), "caller-asserted"),
        ("BuildPhysicalCleanupReceipt", _physical_cleanup_receipt, ("writerKind",), "control-plane"),
        ("BuildPhysicalCleanupReceipt", _physical_cleanup_receipt, ("stopResult",), "unknown"),
        ("BuildPhysicalCleanupReceipt", _physical_cleanup_receipt, ("partialExportDisposition",), "retained"),
        ("BuildPhysicalCleanupReceipt", _physical_cleanup_receipt, ("builderClaimReleased",), False),
        ("BuildPhysicalCleanupReceipt", _physical_cleanup_receipt, ("cgroupRemoved",), False),
    ],
)
def test_authenticated_build_receipts_reject_unmeasured_or_untrusted_values(
    contract, factory, path, value
):
    changed = factory()
    target = changed
    for field in path[:-1]:
        target = target[field]
    target[path[-1]] = value
    _rejected(contract, changed)


@pytest.mark.parametrize(
    "contract,factory",
    [
        ("BuildProviderHealthReceipt", _health_receipt),
        ("BuildPhysicalCleanupReceipt", _physical_cleanup_receipt),
    ],
)
def test_authenticated_build_receipts_reject_unknown_fields(contract, factory):
    changed = factory()
    changed["callerAssertion"] = True
    _rejected(contract, changed)


@pytest.mark.parametrize(
    "contract,factory,container",
    [
        ("BuildProviderHealthReceipt", _health_receipt, "daemonIdentity"),
        ("BuildProviderHealthReceipt", _health_receipt, "isolation"),
        ("BuildProviderHealthReceipt", _health_receipt, "fieldSources"),
        ("BuildPhysicalCleanupReceipt", _physical_cleanup_receipt, "daemonIdentity"),
    ],
)
def test_authenticated_build_receipt_nested_fields_are_all_required(contract, factory, container):
    for field in tuple(factory()[container]):
        changed = factory()
        del changed[container][field]
        _rejected(contract, changed)


def test_success_receipt_requires_no_partial_export_and_a_canonical_physical_digest():
    changed = _receipt()
    changed["cleanup"]["physicalReceipt"]["partialExportDisposition"] = "quarantined"
    _rejected("BuildReceipt", changed)

    changed = _receipt()
    changed["cleanup"]["physicalReceiptDigest"] = "sha256:" + "a" * 64
    _rejected("BuildReceipt", changed)


def test_dispatch_completed_is_a_closed_audit_event_value():
    changed = _receipt()
    changed["auditEvents"][0]["event"] = "dispatch_completed"
    validate_contract("BuildReceipt", changed)

    changed["auditEvents"][0]["event"] = "inv.build.dispatch_completed"
    _rejected("BuildReceipt", changed)


def test_dispatch_completed_payload_is_redacted_and_digest_bound():
    validate_contract("BuildDispatchCompletedPayload", _dispatch_completed_payload())

    changed = _dispatch_completed_payload()
    changed["builderTopology"] = {"address": "unix:///run/buildkit/buildkitd.sock"}
    _rejected("BuildDispatchCompletedPayload", changed)

    changed = _dispatch_completed_payload()
    changed["evidenceDigest"] = "sha256:" + "e" * 64
    _rejected("BuildDispatchCompletedPayload", changed)


def test_build_plan_rejects_unknown_compiler_output_fields():
    changed = _plan()
    changed["unboundedRuntimeOption"] = "caller-controlled"
    _rejected("BuildPlan", changed)


@pytest.mark.parametrize(
    "field,value",
    [
        ("sourceBranch", "main"),
        ("sourceTag", "latest"),
        ("baseImage", "ubuntu:latest"),
        ("secret", "literal-secret"),
        ("env", {"TOKEN": "literal-secret"}),
        ("buildArgs", {"UNBOUNDED": "value"}),
        ("outputImageDigest", "sha256:" + "0" * 64),
    ],
)
def test_build_request_has_no_mutable_secret_or_caller_output_surface(field, value):
    changed = _request()
    changed[field] = value
    _rejected("BuildRequest", changed)


@pytest.mark.parametrize(
    "field,value",
    [
        ("contextPath", "../outside"),
        ("contextPath", "/absolute"),
        ("contextPath", "a//b"),
        ("dockerfilePath", "a\\Dockerfile"),
        ("dockerfilePath", "a/./Dockerfile"),
    ],
)
def test_build_context_paths_are_canonical_and_bounded(field, value):
    changed = _request()
    changed[field] = value
    _rejected("BuildRequest", changed)


def test_build_context_allows_canonical_hidden_repository_paths():
    changed = _request()
    changed["contextPath"] = ".build/context"
    changed["dockerfilePath"] = ".build/Dockerfile"
    validate_contract("BuildRequest", changed)


@pytest.mark.parametrize(
    "field,value",
    [
        ("leaseReleased", False),
        ("builderClaimReleased", False),
        ("cgroupRemoved", False),
        ("cacheDisposition", "quarantined"),
    ],
)
def test_success_receipt_requires_verified_cleanup(field, value):
    changed = _receipt()
    changed["cleanup"][field] = value
    _rejected("BuildReceipt", changed)


@pytest.mark.parametrize(
    "field",
    ["outputImageDigest", "outputConfigDigest", "sbomEvidenceDigest", "scanEvidenceDigest", "cacheOutputDigest"],
)
def test_success_receipt_cannot_claim_missing_output_or_scan_evidence(field):
    changed = _receipt()
    changed[field] = None
    _rejected("BuildReceipt", changed)


def test_failed_receipt_records_unavailable_outputs_as_null_without_fabrication():
    changed = _receipt()
    changed["result"] = "failed"
    for field in (
        "outputImageDigest",
        "outputConfigDigest",
        "sbomEvidenceDigest",
        "scanEvidenceDigest",
        "cacheOutputDigest",
    ):
        changed[field] = None
    changed["cleanup"]["cacheDisposition"] = "quarantined"
    validate_contract("BuildReceipt", changed)


def test_receipt_audit_is_strict_and_nonempty():
    changed = _receipt()
    changed["auditEvents"][0]["rawSecret"] = "must-not-appear"
    _rejected("BuildReceipt", changed)

    changed = _receipt()
    changed["auditEvents"] = []
    _rejected("BuildReceipt", changed)


@pytest.mark.parametrize(
    "container,fields",
    [
        (
            "cleanup",
            (
                "leaseReleased",
                "builderClaimReleased",
                "cgroupRemoved",
                "cacheDisposition",
                "verifiedAt",
                "physicalReceipt",
                "physicalReceiptDigest",
            ),
        ),
        ("auditEvents", ("event", "traceId", "timestamp", "decisionId", "inputDigest", "outputDigest")),
    ],
)
def test_receipt_nested_cleanup_and_audit_fields_are_load_bearing(container, fields):
    for field in fields:
        changed = _receipt()
        target = changed[container][0] if container == "auditEvents" else changed[container]
        del target[field]
        _rejected("BuildReceipt", changed)


def test_workload_contract_cannot_be_reinterpreted_as_build_request():
    workload = {
        "apiVersion": "inv.saintvision.ai/v1alpha1",
        "kind": "Workload",
        "workloadId": f"wld_{ULID}",
        "tenantId": TENANT,
        "projectId": f"prj_{ULID}",
        "workspaceId": f"wsp_{ULID}",
        "resources": {"cpuMillis": 100, "memoryBytes": 1024, "gpuCount": 0, "minVramBytes": 0},
        "imageDigest": "sha256:" + "a" * 64,
        "command": ["/bin/true"],
        "timeoutSeconds": 10,
    }
    validate_contract("WorkloadSpec", workload)
    workload["dockerfilePath"] = "Dockerfile"
    _rejected("WorkloadSpec", workload)
