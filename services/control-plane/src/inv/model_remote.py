"""Bounded remote byte reader, not an execution verifier or permission grant.

Trusted callers capture authorized channel/location snapshots before reading and
must recheck them inside their commit transaction afterwards. No database lock
is held here. This reader is deliberately not wired into ModelRuntimeStore.
"""

from dataclasses import dataclass
import hashlib
import re
import secrets

from .model_manifest import LocationSnapshot, canonical, manifest_copy, rejected
from .node_channels import ChannelProof, endpoint_parts
from .node_chunk import verified_chunk
from .node_transport import NodeTLSClient


@dataclass(frozen=True)
class RemoteModelBytes:
    manifest_hash: str
    channels: tuple[ChannelProof, ...]
    locations: tuple[LocationSnapshot, ...]
    shards: tuple[bytes, ...]


class ConfiguredRemoteModelReader:
    """Read at most eight replicas of a <=32 KiB unencrypted model.

    Each pinned TLS call has the client's <=40 second deadline. There is no
    retry, redirect, URI resolution, disk write or whole-model prefetch fallback.
    A returned receipt is byte evidence only; it has no authorization flag.
    """

    def __init__(self, client):
        if not isinstance(client, NodeTLSClient):
            raise ValueError("Explicit operator Node TLS client required")
        self.client = client

    def read(self, manifest, locations, channels, *, tenant_id, recovery_epoch):
        body = manifest_copy(manifest)
        if (
            body["encryption"] != "none"
            or body["totalBytes"] > 32768
            or len(body["replicas"]) > 8
            or not isinstance(locations, tuple)
            or not isinstance(channels, tuple)
            or not 1 <= len(locations) <= 8
            or not 1 <= len(channels) <= 8
            or any(not isinstance(v, LocationSnapshot) for v in locations)
            or any(not isinstance(v, ChannelProof) for v in channels)
        ):
            rejected()
        by_location = {v.location_id: v for v in locations}
        by_node = {v.node_id: v for v in channels}
        if (
            len(by_location) != len(locations)
            or len(by_node) != len(channels)
            or set(by_location) != {r["locationId"] for r in body["replicas"]}
            or set(by_node) != {r["nodeId"] for r in body["replicas"]}
        ):
            rejected()
        for channel in channels:
            if (
                channel.tenant_id != tenant_id
                or channel.recovery_epoch != recovery_epoch
                or not isinstance(tenant_id, str) or not tenant_id
                or not isinstance(recovery_epoch, str) or not recovery_epoch
                or type(channel.version) is not int or channel.version < 1
                or not isinstance(channel.certificate_sha256, str)
                or re.fullmatch("[0-9a-f]{64}", channel.certificate_sha256) is None
            ):
                rejected()
            endpoint_parts(channel.endpoint)
        # Validate every replica before the first request, including later shards.
        replicas = sorted(body["replicas"], key=lambda r: (r["shardIndex"], r["locationId"]))
        for replica in replicas:
            location = by_location[replica["locationId"]]
            shard = body["shards"][replica["shardIndex"]]
            if (
                replica["state"] != "verified"
                or (location.node_id, location.location_version)
                != (replica["nodeId"], replica["locationVersion"])
                or (location.sha256, location.byte_size) != (shard["sha256"], shard["byteLength"])
                or location.byte_size < 1
            ):
                rejected()
        chunks = {}
        for replica in replicas:
            location = by_location[replica["locationId"]]
            request = {
                "sha256": location.sha256,
                "sizeBytes": location.byte_size,
                "offset": 0,
                "nonce": secrets.token_hex(32),
            }
            result = self.client.read_chunk(by_node[location.node_id], request)
            chunk = verified_chunk(request, result)
            # chunkSha256 is remote metadata; also compare the trusted manifest.
            if hashlib.sha256(chunk).hexdigest() != location.sha256:
                rejected()
            chunks.setdefault(replica["shardIndex"], chunk)
        shards = tuple(chunks[i] for i in range(len(body["shards"])))
        if hashlib.sha256(b"".join(shards)).hexdigest() != body["contentHash"]:
            rejected()
        return RemoteModelBytes(
            hashlib.sha256(canonical(body)).hexdigest(), channels, locations, shards
        )
