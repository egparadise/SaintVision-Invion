"""Remote channel provenance bound to frozen model bytes, never caller authority."""

from dataclasses import asdict
import hashlib

from .model_manifest import LocationSnapshot, canonical, rejected
from .node_channels import ChannelProof, assert_channel, proof
from .workspace_files import decode_snapshot

SOURCE_FILE = "model/source.json"


def source_content(records):
    # Bind private channel/location metadata without exposing it to the process.
    return canonical({"mode": "node-mtls-v1", "sourceHash": hashlib.sha256(canonical(records)).hexdigest()})


def capture_channels(conn, tenant, epoch, locations):
    """Call after _capture locked current Nodes, grants and Locations."""
    channels = []
    for node_id in sorted({location.node_id for location in locations}):
        row = conn.execute(
            "SELECT * FROM inv.node_channels WHERE node_id=%s FOR SHARE", (node_id,)
        ).fetchone()
        if not row:
            rejected()
        channel = proof(row)
        if channel.tenant_id != str(tenant) or channel.recovery_epoch != epoch:
            rejected()
        assert_channel(conn, channel)
        channels.append(channel)
    return tuple(channels)


def source_records(locations, channels=()):
    """Existing local array format; every remote Location includes its channel."""
    by_node = {channel.node_id: channel for channel in channels}
    if channels and (len(by_node) != len(channels)
                     or set(by_node) != {location.node_id for location in locations}):
        rejected()
    return [
        {**asdict(location), **({"channel": asdict(by_node[location.node_id])} if channels else {})}
        for location in locations
    ]


def frozen_sources(raw, workspace_id, records, tenant, epoch):
    """A missing/partial remote marker cannot silently downgrade to local mode."""
    try:
        if not isinstance(records, list) or not records:
            rejected()
        remote = any("channel" in row for row in records)
        locations, channels = [], {}
        for row in records:
            if ("channel" in row) != remote:
                rejected()
            location = LocationSnapshot(**{k: v for k, v in row.items() if k != "channel"})
            locations.append(location)
            if remote:
                channel = ChannelProof(**row["channel"])
                if (channel.tenant_id != str(tenant) or channel.recovery_epoch != epoch
                    or channel.node_id != location.node_id
                    or (channel.node_id in channels and channels[channel.node_id] != channel)):
                    rejected()
                channels[channel.node_id] = channel
        _, files = decode_snapshot(raw, workspace_id)
        if remote:
            if files.get(SOURCE_FILE) != source_content(records):
                rejected()
        elif SOURCE_FILE in files:
            rejected()
        return tuple(locations), tuple(channels[node] for node in sorted(channels))
    except (TypeError, ValueError, KeyError, AttributeError):
        rejected()
