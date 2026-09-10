"""Authenticated bounded Node -> CP transfer; resume at verified part boundaries.

No supplied checksum is accepted as byte evidence. The trusted business adapter
provides the project catalog digest/size and authorizes reads before calling.
"""

import base64
import binascii
import hashlib
import secrets
from time import monotonic_ns
from .errors import DomainError
from .node_channels import NodeChannels, assert_channel
from .object_store import PART_BYTES

CHUNK_BYTES = 256 * 1024


class NodeTransfer:
    def __init__(self, database, client, snapshots):
        self.db, self.client, self.snapshots = database, client, snapshots
        self.channels = NodeChannels(database)

    def fetch(self, node, project, object_id, digest, size):
        # This is Node -> CP effective transfer time, not a Node -> Node link.
        started = monotonic_ns()
        received = 0
        self.snapshots.begin(node.tenant_id, project, object_id, digest, size)
        state = self.snapshots.status(node.tenant_id, project, object_id)
        complete = {p["part_index"] for p in state["parts"]}
        channel = self.channels.snapshot(node)
        authorize = lambda conn: assert_channel(conn, channel)
        if state["state"] == "uploading":
            for index, start in enumerate(range(0, size, PART_BYTES)):
                if index in complete:
                    continue
                data = bytearray()
                for offset in range(start, min(start + PART_BYTES, size), CHUNK_BYTES):
                    request = {
                        "sha256": digest,
                        "sizeBytes": size,
                        "offset": offset,
                        "nonce": secrets.token_hex(32),
                    }
                    with self.db.transaction(node.tenant_id) as conn:
                        authorize(conn)
                    result = self.client.read_chunk(channel, request)
                    if any(result[k] != v for k, v in request.items()):
                        raise DomainError(
                            "NODE-0052", "Transfer response scope differs", 403
                        )
                    try:
                        chunk = base64.b64decode(result["dataBase64"], validate=True)
                    except (ValueError, binascii.Error):
                        raise DomainError(
                            "NODE-0052", "Invalid transfer bytes", 422
                        ) from None
                    if (
                        len(chunk) != min(CHUNK_BYTES, size - offset)
                        or hashlib.sha256(chunk).hexdigest() != result["chunkSha256"]
                        or base64.b64encode(chunk).decode() != result["dataBase64"]
                    ):
                        raise DomainError(
                            "VERIFY-0010", "Transferred chunk differs", 422
                        )
                    data.extend(chunk)
                    received += len(chunk)
                self.snapshots.put_part(
                    node.tenant_id,
                    project,
                    object_id,
                    index,
                    bytes(data),
                    authorize=authorize,
                )
        self.snapshots.finalize(node.tenant_id, project, object_id, authorize=authorize)
        elapsed = max(monotonic_ns() - started, 1)
        return {
            "objectId": str(object_id),
            "sha256": digest,
            "sizeBytes": size,
            "transferredBytes": received,
            "elapsedNanoseconds": elapsed,
            "effectiveBitsPerSecond": (
                received * 8 * 1000000000 // elapsed if received else None
            ),
            "path": "node-to-control-plane",
            "channelVersion": channel.version,
        }
