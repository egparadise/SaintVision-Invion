"""The node-agent receipt collector against the card 214 contract (consumer side).

These tests are about the seam, not the orchestration: the collector reads a file the
node agent wrote and holds it to the strict contract.  They also record one conflict the
contract and the implementation do not yet agree on -- see the last test.
"""

import json
import os
from datetime import datetime, timezone
from types import SimpleNamespace
from uuid import UUID

import pytest

from inv.build_execution import BuildExecutionService, PRODUCT_ENABLE_SETTING
from inv.buildkit_transport import NodeAgentReceipts, PRODUCT_HEALTH_RECEIPT
from inv.errors import DomainError

NODE = "nod_01M3PTP800EEMWMDYKEZZ3CWNP"
RESOURCE = "res_01M3PTP800EEMWMDYKEZZ3CWNQ"
LEASE = "lse_01M3PTP800EEMWMDYKEZZ3CWNR"
DAEMON = {"pid": 42, "processUid": 1000, "processStartTicks": 28815, "comm": "buildkitd"}
FIELD_SOURCES = {
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
}


def conforming_health(**overrides):
    document = {
        "schemaVersion": "build-provider-health-receipt:1",
        "writerKind": "node-agent",
        "nodeId": NODE,
        "builderInstanceId": "builder-c214",
        "builderProfileId": "rootless-product-v1",
        "recoveryEpoch": "223e4567-e89b-12d3-a456-426614174000",
        "observedAt": "2026-10-02T08:00:00Z",
        "runtimeIdentity": "sha256:" + "a" * 64,
        "daemonIdentity": dict(DAEMON),
        "rootless": True,
        "privileged": False,
        "hostAccess": False,
        "entitlements": [],
        "devices": [],
        "binds": [],
        "buildkitVersion": "v0.20.2",
        "rootlesskitVersion": "v2.3.4",
        "isolation": {
            "userNamespace": True,
            "seccompMode": "filter",
            "lsm": "apparmor",
            "noNewPrivileges": True,
            "cgroupMode": "v2",
        },
        "fieldSources": dict(FIELD_SOURCES),
    }
    document.update(overrides)
    return document


def write_health(directory, document):
    """Write the receipt the way a node agent must: readable by its owner only.

    ``_protected_json`` refuses any group or other permission bit on POSIX, which is the
    point of an operator receipt.  A fixture that leaves the default 0644 only passes where
    that check cannot apply -- Windows -- so hosted Linux refused every reading with RES-0006
    while the same tests were green locally (#312 r2 hosted regression).
    """

    path = directory / PRODUCT_HEALTH_RECEIPT
    path.write_text(json.dumps(document) + "\n", encoding="utf-8")
    os.chmod(path, 0o600)
    return path


@pytest.mark.skipif(
    os.name == "nt",
    reason="POSIX permission bits: Windows has no group/other mode for the product to refuse",
)
def test_a_receipt_other_accounts_can_read_is_refused(tmp_path):
    """The refusal under test is the product's, and it only exists on POSIX."""

    path = write_health(tmp_path, conforming_health())
    os.chmod(path, 0o644)
    with pytest.raises(DomainError) as refused:
        NodeAgentReceipts(tmp_path).collect_product_health()
    assert refused.value.code == "RES-0006"


def test_the_collector_accepts_a_conforming_node_agent_receipt(tmp_path):
    write_health(tmp_path, conforming_health())
    receipt = NodeAgentReceipts(tmp_path).collect_product_health()
    assert receipt["writerKind"] == "node-agent"
    assert receipt["daemonIdentity"]["comm"] == "buildkitd"


@pytest.mark.parametrize(
    "override",
    [
        {"writerKind": "control-plane"},
        {"rootless": False},
        {"privileged": True},
        {"hostAccess": True},
        {"schemaVersion": "build-provider-health-receipt:0"},
        {"daemonIdentity": {**DAEMON, "comm": "rootlesskit"}},
        {"isolation": {"userNamespace": True, "seccompMode": "unconfined-ci-reference",
                       "lsm": "apparmor", "noNewPrivileges": True, "cgroupMode": "v2"}},
        {"extra": 1},
    ],
    ids=["writer", "rootless", "privileged", "host-access", "schema", "comm",
         "ci-reference-seccomp", "extra-key"],
)
def test_the_collector_refuses_a_receipt_the_contract_does_not_allow(tmp_path, override):
    write_health(tmp_path, conforming_health(**override))
    with pytest.raises(DomainError) as refused:
        NodeAgentReceipts(tmp_path).collect_product_health()
    assert refused.value.code in {"VAL-0002", "RES-0006"}


def test_a_missing_receipt_is_a_refusal_not_an_empty_reading(tmp_path):
    with pytest.raises(DomainError) as refused:
        NodeAgentReceipts(tmp_path).collect_product_health()
    assert refused.value.code == "RES-0006"


def test_the_uuid_epoch_now_satisfies_the_three_way_agreement():
    """The conflict this test used to record is closed, so it records the resolution.

    Until #311 r2 the contract typed ``recoveryEpoch`` as ``integer``, which could never
    equal this tree's UUID epoch, and the earlier version of this test asserted that
    refusal so that resolving the contract would break it.  It did break -- the contract
    now types it ``string/format uuid`` -- so the assertion is inverted: an agreeing UUID
    passes, a different UUID still refuses, and case alone never decides.
    """

    class _Database:
        recovery_epoch = "223E4567-E89B-12D3-A456-426614174000"   # upper case on purpose

    service = BuildExecutionService(
        _Database(), object(), object(), environment={PRODUCT_ENABLE_SETTING: "1"}
    )
    lowercase = _Database.recovery_epoch.lower()
    identity = service._health_authority(
        conforming_health(recoveryEpoch=lowercase), leased_node_id=NODE, lease_epoch=lowercase
    )
    assert identity["comm"] == "buildkitd"

    with pytest.raises(DomainError) as refused:
        service._health_authority(
            conforming_health(recoveryEpoch="99999999-9999-4999-8999-999999999999"),
            leased_node_id=NODE,
            lease_epoch=lowercase,
        )
    assert "recovery epoch" in str(refused.value)


class _QuarantineClient:
    def __init__(self, mutate=None):
        self.requests = []
        self._mutate = mutate

    def quarantine(self, channel, request):
        self.requests.append((channel, dict(request)))
        receipt = {
            **request,
            "schemaVersion": "build-quarantine-receipt:1",
            "writerKind": "node-agent",
            "recordedAt": "2026-10-02T08:00:01Z",
            "durable": True,
            "replayed": False,
        }
        if self._mutate:
            self._mutate(receipt)
        return receipt


class _FailOnceQuarantineClient(_QuarantineClient):
    def quarantine(self, channel, request):
        if not self.requests:
            self.requests.append((channel, dict(request)))
            raise DomainError("NODE-0030", "synthetic lost acknowledgement", 503)
        return super().quarantine(channel, request)


def _quarantine_boundary(tmp_path, client):
    channel = SimpleNamespace(
        tenant_id="123e4567-e89b-12d3-a456-426614174000",
        node_id=NODE,
        recovery_epoch="223e4567-e89b-12d3-a456-426614174000",
    )
    return NodeAgentReceipts(
        tmp_path,
        quarantine_client=client,
        quarantine_channel=channel,
        request_id_factory=lambda: UUID("33333333-3333-4333-8333-333333333333"),
        clock=lambda: datetime(2026, 10, 2, 8, 0, tzinfo=timezone.utc),
    )


def test_quarantine_capability_exists_only_with_a_complete_mtls_channel(tmp_path):
    assert NodeAgentReceipts(tmp_path).records_durable_quarantine is False
    channel = SimpleNamespace(
        tenant_id="123e4567-e89b-12d3-a456-426614174000",
        node_id=NODE,
        recovery_epoch="223e4567-e89b-12d3-a456-426614174000",
    )
    with pytest.raises(DomainError, match="configuration is incomplete"):
        NodeAgentReceipts(tmp_path, quarantine_client=_QuarantineClient())
    with pytest.raises(DomainError, match="configuration is incomplete"):
        NodeAgentReceipts(tmp_path, quarantine_channel=channel)


def test_quarantine_request_and_receipt_are_exactly_bound(tmp_path):
    client = _QuarantineClient()
    boundary = _quarantine_boundary(tmp_path, client)
    assert boundary.records_durable_quarantine is True
    receipt = boundary.cancel_and_quarantine_session(
        "44444444-4444-4444-8444-444444444444", "VERIFY-0022"
    )
    request = client.requests[0][1]
    assert request == {
        "schemaVersion": "build-quarantine-request:1",
        "requestId": "33333333-3333-4333-8333-333333333333",
        "tenantId": "123e4567-e89b-12d3-a456-426614174000",
        "nodeId": NODE,
        "recoveryEpoch": "223e4567-e89b-12d3-a456-426614174000",
        "scope": "build-session",
        "buildSessionId": "44444444-4444-4444-8444-444444444444",
        "reasonCode": "VERIFY-0022",
        "requestedAt": "2026-10-02T08:00:00Z",
    }
    assert receipt["durable"] is True

    boundary.cancel_and_quarantine_session(
        "44444444-4444-4444-8444-444444444444", "VERIFY-0022"
    )
    assert client.requests[1][1] == request


def test_quarantine_retry_after_an_uncertain_response_reuses_the_exact_request(tmp_path):
    client = _FailOnceQuarantineClient()
    boundary = _quarantine_boundary(tmp_path, client)
    with pytest.raises(DomainError, match="lost acknowledgement"):
        boundary.quarantine_node(NODE, "RES-0006")
    receipt = boundary.quarantine_node(NODE, "RES-0006")
    assert client.requests[0][1] == client.requests[1][1]
    assert receipt["requestId"] == "33333333-3333-4333-8333-333333333333"


@pytest.mark.parametrize(
    "mutate",
    [
        lambda receipt: receipt.__setitem__("nodeId", "nod_11111111111111111111111111"),
        lambda receipt: receipt.__setitem__("reasonCode", "VERIFY-0022"),
        lambda receipt: receipt.__setitem__("durable", False),
        lambda receipt: receipt.__setitem__("writerKind", "control-plane"),
    ],
    ids=["node", "reason", "not-durable", "writer"],
)
def test_quarantine_rejects_an_unbound_or_non_durable_receipt(tmp_path, mutate):
    boundary = _quarantine_boundary(tmp_path, _QuarantineClient(mutate))
    with pytest.raises(DomainError):
        boundary.quarantine_node(NODE, "RES-0006")


@pytest.mark.parametrize(
    ("node_id", "session_id", "reason"),
    [
        ("nod_11111111111111111111111111", None, "RES-0006"),
        (NODE, "NOT-A-UUID", "RES-0006"),
        (NODE, None, "bad"),
    ],
)
def test_quarantine_rejects_invalid_authority_inputs(tmp_path, node_id, session_id, reason):
    boundary = _quarantine_boundary(tmp_path, _QuarantineClient())
    with pytest.raises(DomainError) as refused:
        if session_id is None:
            boundary.quarantine_node(node_id, reason)
        else:
            boundary.cancel_and_quarantine_session(session_id, reason)
    assert refused.value.code == "VERIFY-0022"
