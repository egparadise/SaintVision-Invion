"""Shared strict inventory and read-only registration/mTLS preflight for the five-node lab."""

from __future__ import annotations

from datetime import datetime, timezone
import hashlib
import ipaddress
import json
from pathlib import Path
import re
from typing import Any, Callable
from urllib.parse import urlsplit

FIVE_NODE_INVENTORY_SCHEMA_VERSION = "1.0.0"
FIVE_NODE_PROFILE = "lan-workspace-v1"
FIVE_NODE_FRESHNESS_SECONDS = 15.0
_SHA256_RE = re.compile(r"^[0-9a-f]{64}$")
_NODE_ID_RE = re.compile(r"^nod_[A-Za-z0-9][A-Za-z0-9_-]{0,126}$")


def five_node_inventory_revision(payload: dict[str, Any]) -> str:
    """Return the revision for an inventory, excluding its self-reference."""

    revision_body = {key: value for key, value in payload.items() if key != "revision"}
    canonical = json.dumps(
        revision_body,
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":"),
    ).encode("utf-8")
    return f"sha256:{hashlib.sha256(canonical).hexdigest()}"


def _require_exact_keys(value: dict[str, Any], expected: set[str], *, where: str) -> None:
    actual = set(value)
    if actual != expected:
        missing = sorted(expected - actual)
        extra = sorted(actual - expected)
        raise ValueError(f"{where} keys mismatch: missing={missing}, extra={extra}")


def load_five_node_inventory(path: Path) -> dict[str, Any]:
    """Load and strictly validate the revision-fixed physical-node inventory."""

    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, UnicodeError, json.JSONDecodeError) as error:
        raise ValueError(f"Cannot read five-node inventory: {error}") from None
    if not isinstance(payload, dict):
        raise ValueError("five-node inventory root must be an object")
    _require_exact_keys(
        payload,
        {"schemaVersion", "revision", "controlPlaneHostId", "nodes"},
        where="inventory",
    )
    if payload["schemaVersion"] != FIVE_NODE_INVENTORY_SCHEMA_VERSION:
        raise ValueError(f"inventory schemaVersion must be {FIVE_NODE_INVENTORY_SCHEMA_VERSION}")
    if (
        not isinstance(payload["controlPlaneHostId"], str)
        or not payload["controlPlaneHostId"].strip()
    ):
        raise ValueError("inventory controlPlaneHostId must be a non-empty string")
    if not isinstance(payload["nodes"], list) or not 1 <= len(payload["nodes"]) <= 5:
        raise ValueError("inventory nodes must contain between 1 and 5 physical nodes")

    revision = payload["revision"]
    expected_revision = five_node_inventory_revision(payload)
    if revision != expected_revision:
        raise ValueError(
            "inventory revision mismatch: " f"expected {expected_revision}, got {revision!r}"
        )

    seen: dict[str, set[str]] = {
        "nodeId": set(),
        "ip": set(),
        "certificateSHA256": set(),
        "hostId": set(),
    }
    colocated_count = 0
    for index, node in enumerate(payload["nodes"]):
        where = f"inventory.nodes[{index}]"
        if not isinstance(node, dict):
            raise ValueError(f"{where} must be an object")
        _require_exact_keys(
            node,
            {
                "nodeId",
                "ip",
                "certificateSHA256",
                "profile",
                "hostId",
                "failureDomainId",
                "coLocatedWithControlPlane",
                "measurementEligible",
                "exclusionReason",
            },
            where=where,
        )
        for field in ("nodeId", "ip", "certificateSHA256", "profile", "hostId", "failureDomainId"):
            if not isinstance(node[field], str) or not node[field].strip():
                raise ValueError(f"{where}.{field} must be a non-empty string")
        if not _NODE_ID_RE.fullmatch(node["nodeId"]):
            raise ValueError(f"{where}.nodeId is not a valid node identifier")
        try:
            address = ipaddress.ip_address(node["ip"])
        except ValueError:
            raise ValueError(f"{where}.ip must be an IPv4 address") from None
        if address.version != 4 or not address.is_private:
            raise ValueError(f"{where}.ip must be a private IPv4 address")
        if not _SHA256_RE.fullmatch(node["certificateSHA256"]):
            raise ValueError(f"{where}.certificateSHA256 must be 64 lowercase hex characters")
        if not isinstance(node["coLocatedWithControlPlane"], bool):
            raise ValueError(f"{where}.coLocatedWithControlPlane must be boolean")
        eligible = node["measurementEligible"]
        if not isinstance(eligible, dict):
            raise ValueError(f"{where}.measurementEligible must be an object")
        _require_exact_keys(eligible, {"s05", "s07"}, where=f"{where}.measurementEligible")
        if not all(isinstance(eligible[key], bool) for key in ("s05", "s07")):
            raise ValueError(f"{where}.measurementEligible values must be boolean")

        derived_colocation = node["hostId"] == payload["controlPlaneHostId"]
        if node["coLocatedWithControlPlane"] != derived_colocation:
            raise ValueError(f"{where}.coLocatedWithControlPlane disagrees with host identity")
        if derived_colocation:
            colocated_count += 1
            if colocated_count > 1:
                raise ValueError("inventory can contain at most one CP-colocated node")
            if eligible != {"s05": False, "s07": False}:
                raise ValueError(f"{where} CP-colocated node cannot join timed waves")
            if node["exclusionReason"] != "cp-host-colocation":
                raise ValueError(f"{where}.exclusionReason must be cp-host-colocation")
        else:
            if eligible != {"s05": True, "s07": True}:
                raise ValueError(f"{where} independent node must be eligible for S05 and S07")
            if node["exclusionReason"] is not None:
                raise ValueError(f"{where}.exclusionReason must be null")

        for field in seen:
            value = node[field]
            if value in seen[field]:
                raise ValueError(f"{where}.{field} duplicates another physical node")
            seen[field].add(value)
    return payload


_FIVE_NODE_PREFLIGHT_SQL = """
SELECT
    n.tenant_id::text AS tenant_id,
    n.node_id,
    n.status,
    n.heartbeat_at,
    n.recovery_epoch::text AS node_recovery_epoch,
    n.clock_skew_seconds,
    c.recovery_epoch::text AS channel_recovery_epoch,
    c.version AS channel_version,
    c.endpoint,
    c.certificate_sha256,
    c.certificate_not_after,
    c.enabled AS channel_enabled,
    s.recovery_epoch::text AS snapshot_recovery_epoch,
    s.channel_version AS snapshot_channel_version,
    s.received_at AS snapshot_received_at,
    s.snapshot,
    statement_timestamp() AS database_now
FROM inv.nodes AS n
LEFT JOIN inv.node_channels AS c
  ON c.tenant_id = n.tenant_id AND c.node_id = n.node_id
LEFT JOIN inv.node_resource_snapshots AS s
  ON s.tenant_id = n.tenant_id AND s.node_id = n.node_id
WHERE n.node_id = ANY(%s)
ORDER BY n.node_id, n.tenant_id
"""


def _seconds_since(value: datetime | None, now: datetime) -> float | None:
    if value is None:
        return None
    return (now - value).total_seconds()


def _endpoint_ip(endpoint: str | None) -> str | None:
    if not endpoint:
        return None
    try:
        parsed = urlsplit(endpoint)
        if parsed.scheme != "https":
            return None
        return parsed.hostname
    except ValueError:
        return None


def _assert_database_identity(node: dict[str, Any], row: dict[str, Any]) -> None:
    """Reject identity drift; readiness failures are reported separately."""

    node_id = node["nodeId"]
    if (
        row["certificate_sha256"] is not None
        and row["certificate_sha256"] != node["certificateSHA256"]
    ):
        raise ValueError(f"{node_id}: database certificate fingerprint differs from inventory")
    if row["endpoint"] is not None and _endpoint_ip(row["endpoint"]) != node["ip"]:
        raise ValueError(f"{node_id}: database mTLS endpoint differs from inventory IP")
    epochs = {
        row["node_recovery_epoch"],
        row["channel_recovery_epoch"],
        row["snapshot_recovery_epoch"],
    } - {None}
    if len(epochs) > 1:
        raise ValueError(f"{node_id}: node/channel/snapshot recovery epochs differ")
    if (
        row["channel_version"] is not None
        and row["snapshot_channel_version"] is not None
        and row["channel_version"] != row["snapshot_channel_version"]
    ):
        raise ValueError(f"{node_id}: channel and resource snapshot versions differ")
    snapshot = row["snapshot"]
    if snapshot is None:
        return
    if not isinstance(snapshot, dict):
        raise ValueError(f"{node_id}: resource snapshot is not an object")
    expected = {
        "tenantId": row["tenant_id"],
        "nodeId": node_id,
        "recoveryEpoch": row["node_recovery_epoch"],
        "profileVersion": node["profile"],
    }
    for field, value in expected.items():
        if snapshot.get(field) != value:
            raise ValueError(
                f"{node_id}: resource snapshot {field} differs from registered identity"
            )


def _resource_snapshot_complete(snapshot: dict[str, Any] | None) -> bool:
    if not isinstance(snapshot, dict):
        return False
    values = [
        snapshot.get("cpuCapacityMillis"),
        snapshot.get("memoryCapacityBytes"),
        snapshot.get("memoryAvailableBytes"),
    ]
    if not all(isinstance(value, (int, float)) and not isinstance(value, bool) for value in values):
        return False
    cpu_capacity, memory_capacity, memory_available = values
    return cpu_capacity > 0 and memory_capacity > 0 and 0 <= memory_available <= memory_capacity


def _node_preflight(node: dict[str, Any], row: dict[str, Any] | None) -> dict[str, Any]:
    reasons: list[str] = []
    if row is None:
        reasons.append("not-registered")
        readiness = {
            "registered": False,
            "statusOnline": False,
            "heartbeatFresh": False,
            "channelReady": False,
            "snapshotFresh": False,
            "resourceSnapshotComplete": False,
            "clockSkewAcceptable": False,
            "profileReady": node["profile"] == FIVE_NODE_PROFILE,
            "ready": False,
            "reasons": reasons,
        }
    else:
        _assert_database_identity(node, row)
        now = row["database_now"]
        heartbeat_age = _seconds_since(row["heartbeat_at"], now)
        snapshot_age = _seconds_since(row["snapshot_received_at"], now)
        status_online = row["status"] == "online"
        heartbeat_fresh = (
            heartbeat_age is not None and 0 <= heartbeat_age <= FIVE_NODE_FRESHNESS_SECONDS
        )
        channel_ready = bool(
            row["channel_enabled"]
            and row["certificate_not_after"] is not None
            and row["certificate_not_after"] > now
            and row["endpoint"] is not None
            and row["certificate_sha256"] is not None
        )
        snapshot_fresh = (
            snapshot_age is not None and 0 <= snapshot_age <= FIVE_NODE_FRESHNESS_SECONDS
        )
        snapshot_complete = _resource_snapshot_complete(row["snapshot"])
        clock_ok = row["clock_skew_seconds"] is not None and abs(row["clock_skew_seconds"]) <= 5
        profile_ready = node["profile"] == FIVE_NODE_PROFILE
        if not status_online:
            reasons.append("status-not-online")
        if not heartbeat_fresh:
            reasons.append("heartbeat-stale-or-missing")
        if not channel_ready:
            reasons.append("mtls-channel-not-ready")
        if not snapshot_fresh:
            reasons.append("resource-snapshot-stale-or-missing")
        if not snapshot_complete:
            reasons.append("resource-snapshot-incomplete")
        if not clock_ok:
            reasons.append("clock-skew-unacceptable")
        if not profile_ready:
            reasons.append("profile-not-lan-workspace-v1")
        readiness = {
            "registered": True,
            "statusOnline": status_online,
            "heartbeatFresh": heartbeat_fresh,
            "heartbeatAgeSeconds": round(heartbeat_age, 3) if heartbeat_age is not None else None,
            "channelReady": channel_ready,
            "snapshotFresh": snapshot_fresh,
            "resourceSnapshotComplete": snapshot_complete,
            "snapshotAgeSeconds": round(snapshot_age, 3) if snapshot_age is not None else None,
            "clockSkewAcceptable": clock_ok,
            "profileReady": profile_ready,
            "ready": not reasons,
            "reasons": reasons,
        }
    return {
        "nodeId": node["nodeId"],
        "ip": node["ip"],
        "certificateSHA256": node["certificateSHA256"],
        "profile": node["profile"],
        "hostId": node["hostId"],
        "failureDomainId": node["failureDomainId"],
        "coLocatedWithControlPlane": node["coLocatedWithControlPlane"],
        "coLocationValidation": "matched",
        "measurementEligible": node["measurementEligible"],
        "exclusionReason": node["exclusionReason"],
        "readiness": readiness,
        "selectedForAllFiveSmoke": readiness["ready"],
        "selectedForTimedWave": readiness["ready"] and node["measurementEligible"]["s05"],
    }


def five_node_lab_dry_run(
    inventory: dict[str, Any],
    dsn: str,
    *,
    connect: Callable[..., Any] | None = None,
) -> dict[str, Any]:
    """Read physical registration state without creating or refreshing it."""

    if connect is None:
        from psycopg import connect as psycopg_connect
        from psycopg.rows import dict_row

        connect = lambda value: psycopg_connect(value, row_factory=dict_row)
    node_ids = [node["nodeId"] for node in inventory["nodes"]]
    try:
        with connect(dsn) as connection:
            connection.execute("SET TRANSACTION READ ONLY")
            read_only_row = connection.execute("SHOW transaction_read_only").fetchone()
            read_only_value = (
                next(iter(read_only_row.values()))
                if isinstance(read_only_row, dict)
                else read_only_row[0]
            )
            if str(read_only_value).lower() != "on":
                raise RuntimeError("database did not confirm a read-only transaction")
            rows = connection.execute(_FIVE_NODE_PREFLIGHT_SQL, (node_ids,)).fetchall()
    except ValueError:
        raise
    except Exception as error:
        raise RuntimeError(
            f"five-node-lab database preflight failed: {type(error).__name__}"
        ) from None

    rows_by_node: dict[str, dict[str, Any]] = {}
    tenants: set[str] = set()
    for row in rows:
        node_id = row["node_id"]
        if node_id in rows_by_node:
            raise ValueError(f"{node_id}: registered under more than one tenant")
        rows_by_node[node_id] = row
        tenants.add(row["tenant_id"])
    missing_node_ids = sorted(set(node_ids) - set(rows_by_node))
    if missing_node_ids:
        raise ValueError(
            "inventory nodes are not registered in PostgreSQL: " + ", ".join(missing_node_ids)
        )
    if len(tenants) > 1:
        raise ValueError("inventory nodes are registered under different tenants")

    nodes = [_node_preflight(node, rows_by_node.get(node["nodeId"])) for node in inventory["nodes"]]
    ready_nodes = [node for node in nodes if node["readiness"]["ready"]]
    timed_nodes = [node for node in nodes if node["selectedForTimedWave"]]
    colocated_count = sum(node["coLocatedWithControlPlane"] for node in nodes)
    eligible_count = sum(node["measurementEligible"]["s05"] for node in nodes)
    all_five_ready = (
        len(nodes) == 5 and len(ready_nodes) == 5 and colocated_count == 1 and eligible_count == 4
    )
    return {
        "schemaVersion": "five-node-lab-preflight:1",
        "generatedAt": datetime.now(timezone.utc).isoformat(),
        "adapter": "five-node-lab",
        "dryRun": True,
        "inventoryRevision": inventory["revision"],
        "databaseReadOnly": True,
        "syntheticRowsCreated": False,
        "heartbeatUpdated": False,
        "loadExecuted": False,
        "nodes": nodes,
        "counts": {
            "inventory": len(nodes),
            "physicalExecutionHosts": len({node["hostId"] for node in nodes}),
            "registered": sum(node["readiness"]["registered"] for node in nodes),
            "ready": len(ready_nodes),
            "cpColocated": colocated_count,
            "cpIndependent": len(nodes) - colocated_count,
            "timedWaveEligible": eligible_count,
            "timedWaveSelected": len(timed_nodes),
        },
        "allFiveSmokeNodeIds": [node["nodeId"] for node in ready_nodes],
        "timedWaveNodeIds": [node["nodeId"] for node in timed_nodes],
        "allFiveSmokeReady": all_five_ready,
        "timedWaveReady": all_five_ready and len(timed_nodes) == 4,
    }


def write_registration_mtls_preflight(
    inventory_path: Path,
    dsn: str,
    report_path: Path,
    *,
    connect: Callable[..., Any] | None = None,
) -> dict[str, Any]:
    """Replace a preflight artifact only after a current observation succeeds."""

    if inventory_path.resolve() == report_path.resolve():
        raise ValueError("five-node inventory and preflight report paths must differ")
    report_path.unlink(missing_ok=True)
    inventory = load_five_node_inventory(inventory_path)
    report = five_node_lab_dry_run(inventory, dsn, connect=connect)
    report_path.parent.mkdir(parents=True, exist_ok=True)
    report_path.write_text(
        json.dumps(report, indent=2, ensure_ascii=False) + "\n", encoding="utf-8"
    )
    return report
