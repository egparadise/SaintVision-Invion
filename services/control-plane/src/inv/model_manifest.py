"""Immutable model contract and trusted, bounded full-byte verification.

Root bindings are operator configuration. Neither a path nor a caller-supplied
verification flag is an authority. Network/signed Node transport is separate;
this local worker boundary does not certify remote possession or GPU execution.
"""

from dataclasses import dataclass
import hashlib
import json
from pathlib import Path

from saintvision.storage.readroot import ReadRoot
from .contracts import validate_contract
from .errors import DomainError


def canonical(value):
    return json.dumps(value, sort_keys=True, separators=(",", ":"), allow_nan=False).encode()


def rejected():
    raise DomainError("MODEL-0001", "Model manifest or verified bytes are unavailable", 409)


def manifest_copy(value):
    validate_contract("ModelManifest", value)
    body = json.loads(canonical(value))
    if len(canonical(body)) > 1024 * 1024:
        rejected()
    if body["version"] in {"latest", "current", "head"}:
        rejected()
    adapters = [(v["adapter"], v["version"]) for v in body["runtimeCompatibility"]]
    if len(set(adapters)) != len(adapters):
        rejected()
    offset = 0
    for index, shard in enumerate(body["shards"]):
        if shard["index"] != index or shard["offset"] != offset:
            rejected()
        offset += shard["byteLength"]
    if offset != body["totalBytes"]:
        rejected()
    seen, covered = set(), set()
    for replica in body["replicas"]:
        identity = (replica["shardIndex"], replica["nodeId"])
        if (
            replica["shardIndex"] >= len(body["shards"])
            or identity in seen
            or replica["locationId"] in covered
        ):
            rejected()
        seen.add(identity)
        covered.add(replica["locationId"])
    if {r["shardIndex"] for r in body["replicas"]} != set(range(len(body["shards"]))):
        rejected()
    if (body["encryption"] == "none") != (body["keyRef"] is None):
        rejected()
    return body


@dataclass(frozen=True)
class LocationSnapshot:
    location_id: str
    location_version: int
    contribution_id: str
    contribution_version: int
    node_id: str
    relative_path: str
    byte_size: int
    sha256: str


@dataclass(frozen=True)
class RootBinding:
    node_id: str
    contribution_id: str
    contribution_version: int
    root: ReadRoot


class ConfiguredModelVerifier:
    def __init__(self, roots, *, max_read_bytes=1024 * 1024 * 1024):
        roots = tuple(roots)
        if (
            not roots
            or len(roots) > 128
            or any(
                not isinstance(r, RootBinding) or not isinstance(r.root, ReadRoot) for r in roots
            )
            or len({r.contribution_id for r in roots}) != len(roots)
            or type(max_read_bytes) is not int
            or not 1 <= max_read_bytes <= 4 * 1099511627776
        ):
            raise ValueError("Explicit bounded worker root configuration required")
        self.roots = {r.contribution_id: r for r in roots}
        self.max_read_bytes = max_read_bytes

    def verify(self, manifest, snapshots):
        body = manifest_copy(manifest)
        if body["encryption"] != "none":
            raise DomainError("MODEL-0002", "Encrypted model verifier is not configured", 422)
        if sum(s.byte_size for s in snapshots) > self.max_read_bytes:
            raise DomainError(
                "MODEL-0002", "Model verification exceeds configured byte budget", 422
            )
        locations = {s.location_id: s for s in snapshots}
        if set(locations) != {r["locationId"] for r in body["replicas"]}:
            rejected()
        whole, done = hashlib.sha256(), set()
        try:
            for replica in sorted(
                body["replicas"], key=lambda r: (r["shardIndex"], r["locationId"])
            ):
                shard = body["shards"][replica["shardIndex"]]
                location = locations[replica["locationId"]]
                binding = self.roots.get(location.contribution_id)
                if (
                    replica["state"] != "verified"
                    or binding is None
                    or (binding.node_id, binding.contribution_version)
                    != (location.node_id, location.contribution_version)
                    or (replica["nodeId"], replica["locationVersion"])
                    != (location.node_id, location.location_version)
                    or (location.byte_size, location.sha256)
                    != (shard["byteLength"], shard["sha256"])
                ):
                    rejected()
                first = shard["index"] not in done
                digest, total = hashlib.sha256(), 0
                # ReadRoot rejects traversal, links, hardlinks and changing files at open/close.
                with binding.root.open(binding.root.path / location.relative_path) as (
                    stream,
                    size,
                ):
                    if size != shard["byteLength"]:
                        rejected()
                    while chunk := stream.read(min(1024 * 1024, shard["byteLength"] - total + 1)):
                        total += len(chunk)
                        if total > shard["byteLength"]:
                            rejected()
                        digest.update(chunk)
                        if first:
                            whole.update(chunk)
                if total != shard["byteLength"] or digest.hexdigest() != shard["sha256"]:
                    rejected()
                done.add(shard["index"])
        except (OSError, ValueError):
            rejected()
        if whole.hexdigest() != body["contentHash"]:
            rejected()
        return hashlib.sha256(canonical(body)).hexdigest()
