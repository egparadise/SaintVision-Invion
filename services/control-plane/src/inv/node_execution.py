"""Signed permits and trusted Node stop receipts. No public mutation endpoint.

The signing key stays at Control Plane. Node holds only the pinned public key.
A receipt caller must already be authenticated as its Node by the transport adapter.
"""

import base64
from copy import deepcopy
from datetime import datetime, timezone
import json
from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey
from psycopg.types.json import Jsonb
from .approvals import digest
from .contracts import validate_contract
from .db import Database
from .errors import DomainError
from .leases import lock_run, lock_resources, fence
from .runs import event
from .tooling import ClaimResult, NodePrincipal

DOMAIN = b"SaintVision.NodePermit.v1\x00"


def seal_permit(
    result: ClaimResult, allocations, signing_key: Ed25519PrivateKey, *, now=None
):
    if not result.may_start or result.launch is None:
        raise DomainError("NODE-0001", "A replay cannot issue a Node permit", 403)
    now = now or datetime.now(timezone.utc)
    payload = deepcopy(
        {
            "claim": result.claim,
            "launch": result.launch,
            "allocations": allocations,
            "issuedAt": now.isoformat(),
        }
    )
    validate_contract("NodeExecutionPermit", payload)
    claim = payload["claim"]
    launch = payload["launch"]
    deadline = datetime.fromisoformat(claim["notAfter"].replace("Z", "+00:00"))
    if (
        not now.tzinfo
        or not now < deadline
        or digest(launch) != claim["planDigest"]
        or launch["profileVersion"] != claim["profileVersion"]
    ):
        raise DomainError("NODE-0001", "Claim does not bind the launch", 403)
    leases = [a["lease"] for a in payload["allocations"]]
    if len({l["leaseId"] for l in leases}) != len(leases):
        raise DomainError("NODE-0001", "Duplicate allocation", 403)
    for allocation in payload["allocations"]:
        lease = allocation["lease"]
        if (
            allocation["nodeId"] != claim["nodeId"]
            or lease["tenantId"] != claim["tenantId"]
            or lease["runId"] != claim["runId"]
            or not lease["fencingToken"].startswith(claim["recoveryEpoch"] + ":")
            or datetime.fromisoformat(lease["expiresAt"].replace("Z", "+00:00"))
            < deadline
        ):
            raise DomainError("NODE-0001", "Claim allocation differs", 403)
    raw = json.dumps(
        payload, sort_keys=True, separators=(",", ":"), allow_nan=False
    ).encode()
    if len(raw) > 1048576:
        raise DomainError("NODE-0001", "Permit is too large", 422)
    return {
        "payload": base64.b64encode(raw).decode(),
        "signature": base64.b64encode(signing_key.sign(DOMAIN + raw)).decode(),
    }


class NodeReceiptStore:
    def __init__(self, database: Database):
        self.db = database

    def record(self, node: NodePrincipal, receipt, *, channel=None):
        receipt = deepcopy(receipt)
        validate_contract("NodeStopReceipt", receipt)
        if (
            receipt["tenantId"] != node.tenant_id
            or receipt["nodeId"] != node.node_id
            or receipt["recoveryEpoch"] != self.db.recovery_epoch
        ):
            raise DomainError(
                "AUTH-0042", "Receipt belongs to another Node or recovery epoch", 403
            )
        fingerprint = digest(receipt)
        with self.db.transaction(node.tenant_id) as conn:
            run = lock_run(conn, receipt["runId"], receipt["projectId"])
            if channel is not None:
                from .node_channels import assert_channel

                if (
                    channel.tenant_id != node.tenant_id
                    or channel.node_id != node.node_id
                    or channel.recovery_epoch != self.db.recovery_epoch
                ):
                    raise DomainError("NODE-0033", "Channel receipt scope differs", 403)
                current_node = conn.execute(
                    "SELECT recovery_epoch FROM inv.nodes WHERE node_id=%s FOR UPDATE",
                    (node.node_id,),
                ).fetchone()
                if (
                    not current_node
                    or str(current_node["recovery_epoch"]) != channel.recovery_epoch
                ):
                    raise DomainError(
                        "NODE-0033", "Node identity changed during delivery", 403
                    )
                assert_channel(conn, channel)
            prior = conn.execute(
                "SELECT content_hash,envelope FROM inv.node_stop_receipts WHERE command_id=%s",
                (receipt["commandId"],),
            ).fetchone()
            if prior:
                if prior["content_hash"] != fingerprint:
                    raise DomainError("IDEM-0001", "Stop receipt content changed")
                return prior["envelope"]
            claim = conn.execute(
                "SELECT * FROM inv.tool_claims WHERE command_id=%s",
                (receipt["commandId"],),
            ).fetchone()
            if not claim or any(
                receipt[key] != value
                for key, value in {
                    "claimId": str(claim["claim_id"]),
                    "runId": claim["run_id"],
                    "projectId": claim["project_id"],
                    "nodeId": claim["node_id"],
                    "recoveryEpoch": str(claim["recovery_epoch"]),
                    "planDigest": claim["plan_digest"],
                }.items()
            ):
                raise DomainError(
                    "NODE-0002", "Receipt is not bound to the admitted execution", 403
                )
            rows = conn.execute(
                "SELECT * FROM inv.resource_leases WHERE run_id=%s AND released_at IS NULL ORDER BY lease_id",
                (run["run_id"],),
            ).fetchall()
            reported = {a["lease"]["leaseId"]: a for a in receipt["allocations"]}
            if len(reported) != len(receipt["allocations"]) or set(reported) != {
                r["lease_id"] for r in rows
            }:
                raise DomainError(
                    "LEASE-0002",
                    "Receipt does not cover the exact reserved allocation set",
                )
            resources = lock_resources(conn, [r["resource_id"] for r in rows])
            for row in rows:
                allocation = reported[row["lease_id"]]
                lease = allocation["lease"]
                resource = resources[row["resource_id"]]
                if (
                    allocation["nodeId"] != node.node_id
                    or resource["node_id"] != node.node_id
                    or allocation["kind"] != resource["kind"]
                    or lease["resourceId"] != row["resource_id"]
                    or lease["runId"] != row["run_id"]
                    or lease["tenantId"] != node.tenant_id
                    or lease["amount"] != row["amount"]
                    or lease["fencingToken"] != fence(row)
                ):
                    raise DomainError(
                        "LEASE-0002", "Stop receipt allocation proof differs"
                    )
            conn.execute(
                "INSERT INTO inv.node_stop_receipts(tenant_id,command_id,claim_id,receipt_id,content_hash,envelope,channel_version,peer_sha256) VALUES(%s,%s,%s,%s,%s,%s,%s,%s)",
                (
                    node.tenant_id,
                    receipt["commandId"],
                    receipt["claimId"],
                    receipt["receiptId"],
                    fingerprint,
                    Jsonb(receipt),
                    channel.version if channel is not None else None,
                    channel.certificate_sha256 if channel is not None else None,
                ),
            )
            conn.execute(
                "UPDATE inv.resource_leases SET released_at=clock_timestamp(),stop_receipt=%s WHERE lease_id=ANY(%s)",
                (receipt["receiptId"], sorted(reported)),
            )
            event(conn, node.tenant_id, run["run_id"], "inv.execution.stopped", receipt)
            # Exit 0 is process termination, not verified application success.
            return receipt
