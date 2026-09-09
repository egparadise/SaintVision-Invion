"""Pure, replayable placement calculation. No resource writes occur here."""

from dataclasses import dataclass
from datetime import datetime
from decimal import Decimal, Context, ROUND_HALF_EVEN, localcontext
from .errors import DomainError

D = Decimal
WEIGHTS = {
    "data_locality": D(".30"),
    "resource_fit": D(".20"),
    "cache": D(".15"),
    "network": D(".10"),
    "reliability": D(".10"),
    "transfer": D("-.25"),
    "host_load": D("-.20"),
    "thermal": D("-.05"),
    "cost": D("-.05"),
}


@dataclass(frozen=True)
class Candidate:
    node_id: str
    status: str
    observed_at: datetime
    cpu_millis: int
    memory_bytes: int
    gpu_devices: tuple[tuple[str, int], ...]
    local_bytes: int
    bandwidth_bps: int | None
    host_load: Decimal
    allowed: bool = True
    runtime: str = "container"
    cache: Decimal = D(0)
    reliability: Decimal = D(1)
    thermal: Decimal = D(0)
    cost: Decimal = D(0)
    clock_skew_seconds: Decimal | None = None


@dataclass(frozen=True)
class Request:
    cpu_millis: int
    memory_bytes: int
    gpu_count: int = 0
    min_vram_bytes: int = 0
    required_bytes: int = 0
    max_host_load: Decimal = D(".40")
    runtime: str = "container"


def place(
    request: Request,
    candidates: list[Candidate],
    *,
    now: datetime,
    snapshot_id: str,
    policy_version: str,
    ttl_seconds: int = 15
) -> dict:
    # Ambient Decimal precision must not change the placement decision or evidence.
    with localcontext(Context(prec=28, rounding=ROUND_HALF_EVEN)):
        return _place(
            request,
            candidates,
            now=now,
            snapshot_id=snapshot_id,
            policy_version=policy_version,
            ttl_seconds=ttl_seconds,
        )


def _place(
    request: Request,
    candidates: list[Candidate],
    *,
    now: datetime,
    snapshot_id: str,
    policy_version: str,
    ttl_seconds: int = 15
) -> dict:
    if now.tzinfo is None or ttl_seconds <= 0:
        raise ValueError("An aware clock and positive snapshot TTL are required")
    units = (
        request.cpu_millis,
        request.memory_bytes,
        request.gpu_count,
        request.min_vram_bytes,
        request.required_bytes,
    )
    if (
        any(type(v) is not int or not 0 <= v <= 9007199254740991 for v in units)
        or min(request.cpu_millis, request.memory_bytes) <= 0
    ):
        raise DomainError("VAL-0003", "Invalid resource request", 422)
    if not request.max_host_load.is_finite() or not D(0) <= request.max_host_load <= D(
        1
    ):
        raise DomainError("VAL-0003", "Invalid load ceiling", 422)
    if len({c.node_id for c in candidates}) != len(candidates):
        raise DomainError("VAL-0003", "Duplicate candidate node", 422)
    rejected, eligible, values = {}, {}, {}
    for c in sorted(candidates, key=lambda x: x.node_id):
        reasons = []
        if c.status != "online":
            reasons.append("node_not_online")
        if (
            c.clock_skew_seconds is None
            or not c.clock_skew_seconds.is_finite()
            or abs(c.clock_skew_seconds) > 5
        ):
            reasons.append("clock_unmeasured_or_skewed")
        quantities = (c.cpu_millis, c.memory_bytes, c.local_bytes) + tuple(
            vram for _, vram in c.gpu_devices
        )
        if any(
            type(v) is not int or not 0 <= v <= 9007199254740991 for v in quantities
        ):
            rejected[c.node_id] = reasons + ["invalid_capacity_units"]
            continue
        if not c.allowed:
            reasons.append("policy_denied")
        if (
            c.observed_at.tzinfo is None
            or not 0 <= (now - c.observed_at).total_seconds() <= ttl_seconds
        ):
            reasons.append("snapshot_stale_or_future")
        if c.runtime != request.runtime:
            reasons.append("runtime_mismatch")
        if c.cpu_millis < request.cpu_millis or c.memory_bytes < request.memory_bytes:
            reasons.append("insufficient_capacity")
        if (
            not c.host_load.is_finite()
            or not D(0) <= c.host_load <= D(1)
            or c.host_load > request.max_host_load
        ):
            reasons.append("host_load")
        devices = sorted(
            device for device, vram in c.gpu_devices if vram >= request.min_vram_bytes
        )
        if len(set(device for device, _ in c.gpu_devices)) != len(c.gpu_devices):
            reasons.append("duplicate_gpu")
        if len(devices) < request.gpu_count:
            reasons.append("insufficient_gpu")
        if c.local_bytes < 0:
            reasons.append("invalid_locality")
        if c.bandwidth_bps is not None and (
            type(c.bandwidth_bps) is not int or c.bandwidth_bps < 0
        ):
            reasons.append("invalid_bandwidth")
        for metric in (c.cache, c.reliability, c.thermal, c.cost):
            if not metric.is_finite() or metric < 0:
                reasons.append("invalid_metric")
        transfer = max(request.required_bytes - c.local_bytes, 0)
        if transfer and (c.bandwidth_bps is None or c.bandwidth_bps <= 0):
            reasons.append("unknown_transfer_bandwidth")
        if reasons:
            rejected[c.node_id] = reasons
            continue
        eligible[c.node_id] = devices[: request.gpu_count]
        values[c.node_id] = {
            "data_locality": (
                D(min(c.local_bytes, request.required_bytes))
                / D(request.required_bytes)
                if request.required_bytes
                else D(0)
            ),
            "resource_fit": (
                D(request.cpu_millis) / D(c.cpu_millis)
                + D(request.memory_bytes) / D(c.memory_bytes)
            )
            / D(2),
            "cache": c.cache,
            "network": D(c.bandwidth_bps or 0),
            "reliability": c.reliability,
            "transfer": D(transfer * 8) / D(c.bandwidth_bps) if transfer else D(0),
            "host_load": c.host_load,
            "thermal": c.thermal,
            "cost": c.cost,
        }
    if not values:
        raise DomainError("RES-0003", "No eligible node", retryable=True)
    spans = {
        key: (
            min(v[key] for v in values.values()),
            max(v[key] for v in values.values()),
        )
        for key in WEIGHTS
    }
    scores = {}
    for node, metrics in values.items():
        scores[node] = sum(
            (
                WEIGHTS[key]
                * ((metrics[key] - low) / (high - low) if high != low else D(0))
                for key, (low, high) in spans.items()
            ),
            D(0),
        )
    selected = sorted(scores, key=lambda node: (-scores[node], node))[0]
    return {
        "nodeId": selected,
        "gpuDeviceIds": eligible[selected],
        "snapshotId": snapshot_id,
        "policyVersion": policy_version,
        "weightsVersion": "1.0.0",
        "rejected": rejected,
        "scores": {n: str(s) for n, s in scores.items()},
        "metrics": {n: {k: str(v) for k, v in m.items()} for n, m in values.items()},
    }
