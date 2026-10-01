"""Fail-closed binding from an authenticated Node snapshot to one GPU lease.

Discovery announcements are deliberately absent from this module.  A launch is
eligible only when the current Node channel supplied a fresh strict resource
snapshot, the selected GPU resource has an exclusive live lease, and the
device observation digest still matches its measured fields.
"""

from datetime import datetime, timedelta

from .contracts import validate_contract
from .errors import DomainError
from .policy import action_digest

GPU_FRESHNESS_SECONDS = 15


def _device_digest(device: dict) -> str:
    return action_digest(
        {key: value for key, value in device.items() if key != "observationDigest"}
    )


def verified_gpu_devices(snapshot: dict, resources: dict, node_id: str) -> dict[str, dict]:
    """Return exact healthy device observations backed by GPU resource rows."""

    validate_contract("NodeResourceSnapshot", snapshot)
    devices = {}
    resource_ids = set()
    for device in snapshot.get("gpuDevices", []):
        resource = resources.get(device["resourceId"])
        if (
            resource is None
            or resource["node_id"] != node_id
            or resource["kind"] != "gpu"
            or device["observationDigest"] != _device_digest(device)
            or device["deviceId"] in devices
            or device["resourceId"] in resource_ids
        ):
            continue
        devices[device["deviceId"]] = device
        resource_ids.add(device["resourceId"])
    return devices


def current_single_gpu_allocation(
    conn,
    database,
    *,
    node_id: str,
    workload: dict,
    allocations: list,
    resources: dict,
    profile_version: str,
    now: datetime,
) -> dict | None:
    """Return one measured GPU allocation or preserve the default deny path."""

    requested = workload["resources"]
    gpu_count = requested["gpuCount"]
    min_vram = requested["minVramBytes"]
    gpu_leases = [row for row in allocations if resources[row["resource_id"]]["kind"] == "gpu"]
    if gpu_count == 0:
        if min_vram != 0 or gpu_leases:
            raise DomainError("SANDBOX-0002", "GPU allocation differs from the workload", 403)
        return None
    if gpu_count != 1 or min_vram < 1 or len(gpu_leases) != 1:
        raise DomainError("SANDBOX-0002", "Exactly one measured GPU allocation is required", 403)
    lease = gpu_leases[0]
    resource = resources[lease["resource_id"]]
    if lease["amount"] != 1 or resource["node_id"] != node_id:
        raise DomainError("LEASE-0002", "GPU lease scope differs", 409)

    row = conn.execute(
        """SELECT n.status,n.recovery_epoch AS node_epoch,n.heartbeat_at,
        n.clock_skew_seconds,s.recovery_epoch AS snapshot_epoch,s.channel_version,
        s.received_at,s.snapshot,c.version AS current_channel_version,c.enabled,
        c.certificate_not_after,c.recovery_epoch AS channel_epoch
        FROM inv.nodes n
        JOIN inv.node_resource_snapshots s USING(tenant_id,node_id)
        JOIN inv.node_channels c USING(tenant_id,node_id)
        WHERE n.node_id=%s""",
        (node_id,),
    ).fetchone()
    if not row:
        raise DomainError("RES-0008", "Measured GPU provider is unavailable", 422)
    snapshot = row["snapshot"]
    validate_contract("NodeResourceSnapshot", snapshot)
    observed = datetime.fromisoformat(snapshot["observedAt"].replace("Z", "+00:00"))
    try:
        skew_current = row["clock_skew_seconds"] is not None and abs(row["clock_skew_seconds"]) <= 5
    except (ArithmeticError, TypeError, ValueError):
        skew_current = False
    if (
        now.tzinfo is None
        or observed.tzinfo is None
        or row["status"] != "online"
        or str(row["node_epoch"]) != database.recovery_epoch
        or str(row["snapshot_epoch"]) != database.recovery_epoch
        or str(row["channel_epoch"]) != database.recovery_epoch
        or row["channel_version"] != row["current_channel_version"]
        or not row["enabled"]
        or row["certificate_not_after"] <= now
        or not now - timedelta(seconds=GPU_FRESHNESS_SECONDS) <= row["heartbeat_at"] <= now
        or not now - timedelta(seconds=GPU_FRESHNESS_SECONDS) <= row["received_at"] <= now
        or not now - timedelta(seconds=GPU_FRESHNESS_SECONDS) <= observed <= now
        or snapshot["profileVersion"] != profile_version
        or not skew_current
    ):
        raise DomainError("RES-0003", "Measured GPU provider is stale", 409)

    devices = [
        device
        for device in verified_gpu_devices(snapshot, resources, node_id).values()
        if device["resourceId"] == lease["resource_id"]
    ]
    if len(devices) != 1:
        raise DomainError("RES-0008", "Exact measured GPU device is unavailable", 422)
    device = devices[0]
    if device["totalVramBytes"] < min_vram:
        raise DomainError("RES-0008", "Measured GPU device binding differs", 422)

    allocation = {
        "nodeId": node_id,
        "resourceId": lease["resource_id"],
        "leaseId": lease["lease_id"],
        "fencingToken": f"{lease['recovery_epoch']}:{lease['fencing_token']}",
        "deviceId": device["deviceId"],
        "vramBytes": device["totalVramBytes"],
        "providerVersion": device["providerVersion"],
        "profileVersion": profile_version,
        "recoveryEpoch": database.recovery_epoch,
        "observationDigest": device["observationDigest"],
        "observedAt": snapshot["observedAt"],
        "exclusive": device["exclusive"],
        "runtimeCompatible": device["runtimeCompatible"],
        "healthy": device["healthy"],
        "deviceRequestDriver": device["deviceRequestDriver"],
    }
    validate_contract("GPUAllocation", allocation)
    return allocation
