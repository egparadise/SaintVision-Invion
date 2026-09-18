"""Pull heartbeats prove current TLS possession; inventory fields cannot do so."""

from datetime import datetime
import secrets
from psycopg.types.json import Jsonb
from .contracts import validate_contract
from .errors import DomainError
from .node_channels import NodeChannels, assert_channel


class NodeObservation:
    def __init__(self, database, client):
        self.db, self.client = database, client
        self.channels = NodeChannels(database)

    def begin(self, node):
        proof = self.channels.snapshot(node, observation_only=True)
        nonce = secrets.token_hex(32)
        with self.db.transaction(node.tenant_id) as conn:
            conn.execute(
                "INSERT INTO inv.node_probes(tenant_id,node_id,nonce) VALUES(%s,%s,%s)",
                (node.tenant_id, node.node_id, nonce),
            )
        return proof, {"nonce": nonce}

    def accept(self, node, proof, request, response, *, snapshot=None):
        if snapshot is not None:
            validate_contract("NodeResourceSnapshot", snapshot)
            if (
                any(snapshot[k] != v for k, v in response.items())
                or snapshot["cpuBusyMillis"] > snapshot["cpuCapacityMillis"]
                or snapshot["memoryAvailableBytes"] > snapshot["memoryCapacityBytes"]
            ):
                raise DomainError("NODE-0051", "Resource observation is inconsistent", 422)
        validate_contract("NodeProbeInput", request)
        validate_contract("NodeProbeResult", response)
        if (
            any(
                response[k] != v
                for k, v in {
                    "tenantId": node.tenant_id,
                    "nodeId": node.node_id,
                    "recoveryEpoch": self.db.recovery_epoch,
                    "nonce": request["nonce"],
                }.items()
            )
            or proof.tenant_id != node.tenant_id
            or proof.node_id != node.node_id
        ):
            raise DomainError("NODE-0050", "Heartbeat challenge scope differs", 403)
        observed = datetime.fromisoformat(response["observedAt"].replace("Z", "+00:00"))
        with self.db.transaction(node.tenant_id) as conn:
            current = conn.execute(
                "SELECT * FROM inv.nodes WHERE node_id=%s FOR UPDATE", (node.node_id,)
            ).fetchone()
            if not current or str(current["recovery_epoch"]) != self.db.recovery_epoch:
                raise DomainError("NODE-0050", "Heartbeat epoch differs", 403)
            assert_channel(conn, proof)
            pending = conn.execute(
                "SELECT * FROM inv.node_probes WHERE nonce=%s AND node_id=%s FOR UPDATE",
                (request["nonce"], node.node_id),
            ).fetchone()
            now = conn.execute("SELECT clock_timestamp() AS now").fetchone()["now"]
            if (
                not pending
                or pending["consumed_at"]
                or not 0 <= (now - pending["issued_at"]).total_seconds() <= 10
            ):
                raise DomainError("NODE-0050", "Heartbeat challenge expired or reused", 403)
            if (
                current["probe_started_at"] is not None
                and current["probe_started_at"] >= pending["issued_at"]
            ):
                raise DomainError(
                    "NODE-0050", "Out-of-order heartbeat rejected", 409, retryable=True
                )
            # Conservative clock check against both ends of the DB-timed exchange.
            if (
                abs((observed - now).total_seconds()) > 5
                or abs((observed - pending["issued_at"]).total_seconds()) > 5
            ):
                raise DomainError("NODE-0050", "Node clock outside admission bounds", 403)
            conn.execute(
                "UPDATE inv.node_probes SET consumed_at=%s WHERE nonce=%s",
                (now, request["nonce"]),
            )
            row = conn.execute(
                "UPDATE inv.nodes SET heartbeat_at=%s,probe_started_at=%s,clock_skew_seconds=%s,status=CASE WHEN status='offline' THEN 'online' ELSE status END WHERE node_id=%s RETURNING status",
                (
                    now,
                    pending["issued_at"],
                    (observed - now).total_seconds(),
                    node.node_id,
                ),
            ).fetchone()
            if snapshot is not None:
                conn.execute(
                    """INSERT INTO inv.node_resource_snapshots(tenant_id,node_id,recovery_epoch,channel_version,received_at,snapshot)
                    VALUES(%s,%s,%s,%s,%s,%s) ON CONFLICT(tenant_id,node_id) DO UPDATE SET
                    recovery_epoch=excluded.recovery_epoch,channel_version=excluded.channel_version,received_at=excluded.received_at,snapshot=excluded.snapshot""",
                    (
                        node.tenant_id,
                        node.node_id,
                        self.db.recovery_epoch,
                        proof.version,
                        now,
                        Jsonb(snapshot),
                    ),
                )
            return {
                "nodeId": node.node_id,
                "status": row["status"],
                "lastHeartbeatAt": now.isoformat(),
                "profileVersion": response["profileVersion"],
            }

    def poll(self, node):
        proof, request = self.begin(node)
        response = self.client.probe(proof, request)
        return self.accept(node, proof, request, response)

    def poll_resources(self, node):
        proof, request = self.begin(node)
        snapshot = self.client.resource_snapshot(proof, request)
        response = {
            k: snapshot[k]
            for k in (
                "nonce",
                "tenantId",
                "nodeId",
                "recoveryEpoch",
                "profileVersion",
                "observedAt",
            )
        }
        return self.accept(node, proof, request, response, snapshot=snapshot)

    def mark_offline(self, tenant_id):
        with self.db.transaction(tenant_id) as conn:
            rows = conn.execute(
                "SELECT node_id FROM inv.nodes WHERE status='online' ORDER BY node_id FOR UPDATE"
            ).fetchall()
            changed = []
            for row in rows:
                if conn.execute(
                    "UPDATE inv.nodes SET status='offline' WHERE node_id=%s AND heartbeat_at < clock_timestamp()-interval '60 seconds' AND status='online' RETURNING node_id",
                    (row["node_id"],),
                ).fetchone():
                    changed.append(row["node_id"])
            # A missing heartbeat never returns leases or asserts process termination.
            return changed
