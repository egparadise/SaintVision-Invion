from dataclasses import replace
from datetime import datetime, timezone, timedelta
from decimal import Decimal as D
import hashlib
import json
from pathlib import Path
import pytest
from fastapi.testclient import TestClient
from inv.app import app
from inv.contracts import validate_contract, catalog
from inv.errors import DomainError
from inv.ids import new_id
from inv.policy import action_digest, enforce_decision
from inv.scheduler import Candidate, Request, place
from inv.state import RunState, FORWARD, TERMINAL, check_transition
from inv.storage import parse_uri, resolve_scoped, verify_content

NOW = datetime(2026, 9, 9, tzinfo=timezone.utc)
TENANT = "f908a7f6-7d2e-44fc-8dde-0c3ec1301e72"
PROJECT = "prj_01K00000000000000000000000"
ROOT = Path(__file__).resolve().parents[2]


def candidate(node="a", **kwargs):
    base = Candidate(
        node,
        "online",
        NOW,
        4000,
        8000,
        (("gpu0", 16000),),
        0,
        8000,
        D(".1"),
        clock_skew_seconds=D(0),
    )
    return replace(base, **kwargs)


def placement(candidates, request=None):
    return place(
        request or Request(1000, 1000),
        candidates,
        now=NOW,
        snapshot_id="snapshot1",
        policy_version="p1",
    )


def test_state_matrix():
    for before in RunState:
        for after in RunState:
            allowed = (
                before == after
                or after in FORWARD.get(before, set())
                or (
                    before not in TERMINAL
                    and after in {RunState.FAILED, RunState.CANCELLED}
                )
            )
            if allowed:
                check_transition(before, after, evidence_ready=True)
            else:
                with pytest.raises(DomainError):
                    check_transition(before, after, evidence_ready=True)


def test_success_requires_evidence():
    with pytest.raises(DomainError, match="evidence"):
        check_transition("verifying", "succeeded")
    with pytest.raises(DomainError):
        check_transition("lost", "failed")


def test_ids_unique_and_contract_valid():
    values = {new_id("nod") for _ in range(1000)}
    assert len(values) == 1000
    for value in values:
        validate_contract("NodeId", value)


@pytest.mark.parametrize("bad", [-1, True, 1.5, 9007199254740992])
def test_contract_bad_units(bad):
    with pytest.raises(DomainError):
        validate_contract(
            "ResourceRequest",
            {"cpuMillis": bad, "memoryBytes": 10, "gpuCount": 0, "minVramBytes": 0},
        )


def test_contract_unknown_field_and_formats():
    with pytest.raises(DomainError):
        validate_contract("Timestamp", "yesterday")
    with pytest.raises(DomainError):
        validate_contract("TenantId", "a")
    with pytest.raises(DomainError):
        validate_contract(
            "ResourceRequest",
            {
                "cpuMillis": 1,
                "memoryBytes": 1,
                "gpuCount": 0,
                "minVramBytes": 0,
                "secret": "do not log",
            },
        )
    assert (
        json.loads((ROOT / "contracts/v1alpha1/core.schema.json").read_text())
        == catalog()
    )


def test_replay_tie_and_permutation():
    a, b = candidate("a"), candidate("b")
    assert placement([b, a]) == placement([a, b])
    assert placement([b, a])["nodeId"] == "a"
    assert placement([a])["scores"] == {"a": "0.00"}


def test_filter_and_gpu_slices():
    result = placement(
        [candidate("bad", status="offline"), candidate("ok")],
        Request(1, 1, gpu_count=1, min_vram_bytes=15000),
    )
    assert result["gpuDeviceIds"] == ["gpu0"]
    assert result["rejected"]["bad"] == ["node_not_online"]
    with pytest.raises(DomainError):
        placement([candidate()], Request(1, 1, gpu_count=1, min_vram_bytes=16001))


@pytest.mark.parametrize(
    "kwargs",
    [
        {"status": "draining"},
        {"allowed": False},
        {"observed_at": NOW - timedelta(seconds=16)},
        {"observed_at": NOW + timedelta(seconds=1)},
        {"observed_at": NOW.replace(tzinfo=None)},
        {"runtime": "host"},
        {"cpu_millis": 0},
        {"host_load": D(".41")},
        {"host_load": D("NaN")},
        {"cache": D("NaN")},
        {"gpu_devices": (("g", 1), ("g", 2))},
        {"bandwidth_bps": -1},
    ],
)
def test_scheduler_rejects_unsafe_candidates(kwargs):
    with pytest.raises(DomainError):
        placement([candidate(**kwargs)])


def test_bandwidth_is_bits_and_empty_locality():
    result = placement([candidate()], Request(1000, 1000, required_bytes=1000))
    assert result["metrics"]["a"]["transfer"] == "1"
    assert placement([candidate()])["metrics"]["a"]["data_locality"] == "0"
    with pytest.raises(DomainError):
        placement([candidate(bandwidth_bps=None)], Request(1, 1, required_bytes=1))


def test_duplicate_nodes_rejected():
    with pytest.raises(DomainError):
        placement([candidate(), candidate()])


@pytest.mark.parametrize(
    "uri",
    [
        "inv://datasets/brain@1.2.3",
        "inv://models/model-v1@latest",
        "inv://artifacts/run_01K00000000000000000000000/art_01K00000000000000000000000",
        "inv://workspaces/wsp_01K00000000000000000000000/results/a.txt",
    ],
)
def test_uris(uri):
    assert parse_uri(uri).namespace


@pytest.mark.parametrize(
    "uri",
    [
        "file:///a",
        "inv://datasets/../secret",
        "inv://datasets/a%2f..%2fx",
        "inv://datasets/a%252f..",
        "inv://datasets/a?token=x",
        "inv://datasets/a#x",
        "inv://datasets/a\\b",
        "inv://datasets/a//b",
        "inv://workspaces/wsp_01K00000000000000000000000/../../x",
        "inv://artifacts/foo/bar",
        "inv://datasets/a:stream",
        "inv://datasets/%00",
    ],
)
def test_unsafe_uri(uri):
    with pytest.raises(DomainError):
        parse_uri(uri)


def test_checksum_uses_actual_bytes(tmp_path):
    file = tmp_path / "sample"
    file.write_bytes(b"hello")
    digest = hashlib.sha256(b"hello").hexdigest()
    verify_content(file, digest, 5)
    for wrong_hash, wrong_size in [("0" * 64, 5), (digest, 4), (digest, 6)]:
        with pytest.raises(DomainError):
            verify_content(file, wrong_hash, wrong_size)
    file.write_bytes(b"jello")
    with pytest.raises(DomainError):
        verify_content(file, digest, 5)


def test_path_scope(tmp_path):
    root = tmp_path / "root"
    root.mkdir()
    assert resolve_scoped(root, "a/b") == root / "a" / "b"
    for path in ["../out", "/out", "C:/out", "a\\b", "file:stream"]:
        with pytest.raises(DomainError):
            resolve_scoped(root, path)


def decision():
    action = {"tool": "inspect", "node": "n"}
    return action, {
        "decisionId": "d1",
        "tenantId": TENANT,
        "projectId": PROJECT,
        "subjectId": "u1",
        "effect": "allow",
        "riskLevel": "L1",
        "actionDigest": action_digest(action),
        "expiresAt": (NOW + timedelta(seconds=30)).isoformat(),
        "requiredApprovals": 1,
        "approvedBy": [],
    }


def enforce(d, a):
    enforce_decision(
        d, action=a, tenant_id=TENANT, project_id=PROJECT, subject_id="u1", now=NOW
    )


def test_policy_scope_and_fail_closed():
    a, d = decision()
    enforce(d, a)
    for changes in [
        {"tenantId": "different"},
        {"actionDigest": "0" * 64},
        {"expiresAt": NOW.isoformat()},
        {"effect": "deny"},
        {"riskLevel": "L3"},
        {"riskLevel": "L2"},
        {"approvedBy": "admin"},
        {"unexpected": "field"},
    ]:
        with pytest.raises(DomainError):
            enforce({**d, **changes}, a)
    with pytest.raises(DomainError):
        enforce(None, a)
    with pytest.raises(DomainError):
        enforce(d, {**a, "node": "other"})


def test_approval_unique_and_required():
    a, d = decision()
    d.update(riskLevel="L2", requiredApprovals=2, approvedBy=["alice", "bob"])
    enforce(d, a)
    with pytest.raises(DomainError):
        enforce({**d, "approvedBy": ["alice", "alice"]}, a)


def test_health_is_not_readiness():
    client = TestClient(app)
    assert client.get("/healthz").status_code == 200
    assert client.get("/readyz").status_code == 503
    assert client.post("/runs", json={}).status_code == 404


@pytest.mark.parametrize("skew", [None, D("NaN"), D("6"), D("-6")])
def test_scheduler_clock_measurement_required(skew):
    with pytest.raises(DomainError):
        placement([candidate(clock_skew_seconds=skew)])


def test_scheduler_ignores_ambient_decimal_precision():
    from decimal import localcontext

    candidates = [candidate("a", cpu_millis=3000), candidate("b", cpu_millis=4000)]
    with localcontext() as context:
        context.prec = 3
        low = placement(candidates)
    with localcontext() as context:
        context.prec = 50
        high = placement(candidates)
    assert low == high


@pytest.mark.parametrize("bad", [True, 1.5, -1])
def test_scheduler_invalid_request_units(bad):
    with pytest.raises(DomainError):
        placement([candidate()], Request(bad, 1000))
