"""Single-use browser attachment to an already approved, bounded Node PTY.

Tickets and connection leases are durable. Each frame rechecks current authority
before and after mTLS. Disconnect cannot restart a command or extend its deadline.
Raw input/output and bearer tickets are never added to events or exception text.
"""

import base64
import hashlib
import re
import secrets
from dataclasses import dataclass
from datetime import datetime, timezone, timedelta
from uuid import uuid4

from .approvals import Principal, digest
from .containment import require_execution
from .contracts import validate_contract
from .control import Control
from .errors import DomainError
from .leases import lock_run
from .node_channels import NodeChannels, assert_channel
from .node_transport import strict_json
from .runs import event
from .snapshots import identity
from .tooling import NodePrincipal


@dataclass(frozen=True)
class Attachment:
    principal: Principal
    command_id: str
    session_id: str
    connection_id: str
    expires_at: datetime
    workspace_id: str


class TerminalService:
    def __init__(self, workspace, origins):
        self.workspace, self.db = workspace, workspace.db
        self.origins = frozenset(origins)

    def _current(self, conn, principal, command_id):
        command_id = identity(command_id)
        row = conn.execute(
            """SELECT c.*,d.envelope,a.requester_id FROM inv.tool_claims c
            JOIN inv.execution_deliveries d USING(tenant_id,command_id)
            JOIN inv.approval_dispatches x USING(tenant_id,command_id)
            JOIN inv.approval_requests a ON a.tenant_id=x.tenant_id AND a.approval_id=x.approval_id
            WHERE c.command_id=%s""",
            (command_id,),
        ).fetchone()
        if not row or row["requester_id"] != principal.subject_id:
            raise DomainError("AUTH-0070", "Current terminal requester required", 403)
        run = lock_run(conn, row["run_id"], row["project_id"])
        Control(self.db).grant(conn, principal, row["project_id"], "can_request")
        if conn.execute(
            "SELECT 1 FROM inv.business_runs WHERE run_id=%s", (row["run_id"],)
        ).fetchone():
            from .business_handoff import scope

            scope(conn, self.db, principal, row["project_id"], row["run_id"], "can_request")
        require_execution(conn)
        if run["state"] != "running" or str(row["recovery_epoch"]) != self.db.recovery_epoch:
            raise DomainError("AUTH-0070", "Original terminal execution must still be running", 403)
        if not conn.execute(
            "SELECT 1 FROM inv.execution_attempts WHERE command_id=%s AND attempt=%s",
            (row["command_id"], run["attempt"]),
        ).fetchone():
            raise DomainError("AUTH-0070", "Terminal attempt has been superseded", 403)
        node = conn.execute(
            "SELECT status,recovery_epoch FROM inv.nodes WHERE node_id=%s FOR SHARE",
            (row["node_id"],),
        ).fetchone()
        if (
            not node
            or node["status"] not in {"online", "draining"}
            or str(node["recovery_epoch"]) != self.db.recovery_epoch
        ):
            raise DomainError("AUTH-0070", "Terminal Node is unavailable", 403)
        now = conn.execute("SELECT clock_timestamp() AS now").fetchone()["now"]
        if row["not_after"] <= now + timedelta(seconds=5):
            raise DomainError("AUTH-0070", "Terminal execution deadline reached", 403)
        leases = conn.execute(
            "SELECT * FROM inv.resource_leases WHERE run_id=%s AND released_at IS NULL",
            (row["run_id"],),
        ).fetchall()
        if not leases or any(
            l["expires_at"] <= now or str(l["recovery_epoch"]) != self.db.recovery_epoch
            for l in leases
        ):
            raise DomainError("LEASE-0003", "Current terminal allocations required")
        launch = strict_json(base64.b64decode(row["envelope"]["payload"], validate=True))["launch"]
        if "terminal" not in launch or "workspaceInput" not in launch:
            raise DomainError("AUTH-0070", "Command has no explicit terminal capability", 403)
        if not conn.execute(
            "SELECT 1 FROM inv.project_nodes WHERE project_id=%s AND node_id=%s AND enabled FOR SHARE",
            (row["project_id"], row["node_id"]),
        ).fetchone():
            raise DomainError("AUTH-0030", "Current project Node membership required", 403)
        return row, launch, now

    def issue(self, authenticated, workspace_id, data, origin):
        validate_contract("TerminalTicketInput", data)
        validate_contract("WorkspaceId", workspace_id)
        if origin not in self.origins:
            raise DomainError("AUTH-0070", "Exact configured browser Origin required", 403)
        principal = authenticated.principal
        with self.db.transaction(principal.tenant_id) as conn:
            row, launch, now = self._current(conn, principal, data["commandId"])
            if launch["workspaceId"] != workspace_id:
                raise DomainError("AUTH-0011", "Terminal Workspace differs", 403)
            expiry = min(
                now + timedelta(seconds=30),
                row["not_after"] - timedelta(seconds=5),
                datetime.fromtimestamp(authenticated.expires_at, timezone.utc),
            )
            if expiry <= now:
                raise DomainError("AUTH-0070", "Terminal identity expired", 403)
            token = secrets.token_hex(32)
            session = launch["terminal"]["sessionId"]
            conn.execute(
                """INSERT INTO inv.terminal_tickets(tenant_id,ticket_hash,project_id,run_id,command_id,session_id,subject_id,origin,recovery_epoch,expires_at,created_at)
                VALUES(%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s)""",
                (
                    principal.tenant_id,
                    hashlib.sha256(token.encode()).hexdigest(),
                    row["project_id"],
                    row["run_id"],
                    row["command_id"],
                    session,
                    principal.subject_id,
                    origin,
                    self.db.recovery_epoch,
                    expiry,
                    now,
                ),
            )
            result = {
                "ticket": token,
                "expiresAt": expiry.isoformat(),
                "sessionId": session,
                "websocketPath": f"/v1/workspaces/{workspace_id}/terminals/{session}",
            }
            validate_contract("TerminalTicketResult", result)
            return result

    def redeem(self, tenant, workspace_id, session_id, token, origin):
        if (
            origin not in self.origins
            or not isinstance(token, str)
            or not re.fullmatch("[0-9a-f]{64}", token)
        ):
            raise DomainError("AUTH-0070", "Terminal attachment rejected", 403)
        with self.db.transaction(tenant) as conn:
            ticket_hash = hashlib.sha256(token.encode()).hexdigest()
            ticket = conn.execute(
                "SELECT * FROM inv.terminal_tickets WHERE ticket_hash=%s", (ticket_hash,)
            ).fetchone()
            if not ticket:
                raise DomainError("AUTH-0070", "Terminal attachment rejected", 403)
            principal = Principal(tenant, ticket["subject_id"])
            row, launch, now = self._current(conn, principal, str(ticket["command_id"]))
            if (
                ticket["consumed_at"] is not None
                or ticket["expires_at"] <= now
                or ticket["origin"] != origin
                or str(ticket["recovery_epoch"]) != self.db.recovery_epoch
                or str(ticket["session_id"]) != session_id
                or launch["workspaceId"] != workspace_id
                or launch["terminal"]["sessionId"] != session_id
            ):
                raise DomainError("AUTH-0070", "Terminal ticket expired, used or mismatched", 403)
            # Run lock serializes all attachments and frame leases for this command.
            conn.execute(
                "INSERT INTO inv.terminal_connections(tenant_id,command_id) VALUES(%s,%s) ON CONFLICT DO NOTHING",
                (tenant, row["command_id"]),
            )
            current = conn.execute(
                "SELECT * FROM inv.terminal_connections WHERE command_id=%s FOR UPDATE",
                (row["command_id"],),
            ).fetchone()
            if current["connection_id"] is not None and current["expires_at"] > now:
                raise DomainError("RES-0007", "A terminal attachment is already active", 409)
            used = conn.execute(
                "UPDATE inv.terminal_tickets SET consumed_at=clock_timestamp() WHERE ticket_hash=%s AND consumed_at IS NULL RETURNING ticket_hash",
                (ticket_hash,),
            ).fetchone()
            if not used:
                raise DomainError("AUTH-0070", "Terminal ticket already used", 403)
            connection_id = str(uuid4())
            conn.execute(
                "UPDATE inv.terminal_connections SET connection_id=%s,expires_at=least(%s,clock_timestamp()+interval '5 seconds') WHERE command_id=%s",
                (connection_id, ticket["expires_at"], row["command_id"]),
            )
            event(conn, tenant, row["run_id"], "inv.terminal.attached", {"sessionId": session_id})
            return Attachment(
                principal,
                str(row["command_id"]),
                session_id,
                connection_id,
                ticket["expires_at"],
                workspace_id,
            )

    def _connection(self, conn, attachment, now):
        row = conn.execute(
            "SELECT * FROM inv.terminal_connections WHERE command_id=%s FOR UPDATE",
            (attachment.command_id,),
        ).fetchone()
        if (
            not row
            or str(row["connection_id"]) != attachment.connection_id
            or row["expires_at"] <= now
            or attachment.expires_at <= now
        ):
            raise DomainError("AUTH-0070", "Terminal attachment expired or superseded", 403)
        conn.execute(
            "UPDATE inv.terminal_connections SET expires_at=least(%s,clock_timestamp()+interval '5 seconds') WHERE command_id=%s",
            (attachment.expires_at, attachment.command_id),
        )

    def frame(self, attachment, data):
        validate_contract("TerminalFrameInput", data)
        principal = attachment.principal
        with self.db.transaction(principal.tenant_id) as conn:
            row, launch, now = self._current(conn, principal, attachment.command_id)
            self._connection(conn, attachment, now)
            node = NodePrincipal(principal.tenant_id, row["node_id"])
        # An existing draining Node may finish its approved terminal. A kill is
        # denied by _current and its durable cancellation proceeds independently.
        channel = NodeChannels(self.db).snapshot(node, observation_only=True)
        runtime = self.workspace.runtime.for_workload({"targetNodeId": node.node_id})
        result = runtime.client.terminal_frame(channel, {"permit": row["envelope"], "frame": data})
        if (
            result["commandId"] != attachment.command_id
            or result["sessionId"] != attachment.session_id
            or result["nonce"] != data["nonce"]
            or (data["operation"] != "poll" and result["sequence"] != data["sequence"])
        ):
            raise DomainError("AUTH-0070", "Terminal response scope differs", 403)
        with self.db.transaction(principal.tenant_id) as conn:
            row, _, now = self._current(conn, principal, attachment.command_id)
            self._connection(conn, attachment, now)
            assert_channel(conn, channel)
            if data["operation"] != "poll":
                inserted = conn.execute(
                    "INSERT INTO inv.terminal_frame_audit(tenant_id,command_id,sequence,frame_digest) VALUES(%s,%s,%s,%s) ON CONFLICT DO NOTHING RETURNING sequence",
                    (principal.tenant_id, attachment.command_id, data["sequence"], digest(data)),
                ).fetchone()
                prior = conn.execute(
                    "SELECT frame_digest FROM inv.terminal_frame_audit WHERE command_id=%s AND sequence=%s",
                    (attachment.command_id, data["sequence"]),
                ).fetchone()
                if prior["frame_digest"] != digest(data):
                    raise DomainError("AUTH-0070", "Terminal sequence audit differs", 403)
                if inserted:
                    event(
                        conn,
                        principal.tenant_id,
                        row["run_id"],
                        "inv.terminal.frame",
                        {
                            "sessionId": attachment.session_id,
                            "sequence": data["sequence"],
                            "operation": data["operation"],
                        },
                    )
        return result

    def release(self, attachment):
        with self.db.transaction(attachment.principal.tenant_id) as conn:
            conn.execute(
                "UPDATE inv.terminal_connections SET connection_id=NULL,expires_at=clock_timestamp() WHERE command_id=%s AND connection_id=%s",
                (attachment.command_id, attachment.connection_id),
            )


class TerminalText:
    """Bounded complete-line redaction, including secrets split across frames.

    Every attachment starts at cursor zero. Never release a fragment of a line,
    private-key block, OSC/CSI control sequence or invalid UTF-8 to the browser.
    Prompts lacking a newline stay buffered; the UI must state this limitation.
    """

    def __init__(self):
        self.cursor, self.pending, self.private = 0, b"", False

    def accept(self, response):
        data = base64.b64decode(response["dataBase64"], validate=True)
        if len(data) > 4096 or response["cursor"] != self.cursor + len(data):
            raise DomainError("AUTH-0070", "Terminal output cursor differs", 403)
        self.cursor = response["cursor"]
        self.pending += data
        if len(self.pending) > 65536:
            raise DomainError("AUTH-0070", "Terminal line exceeds bound", 403)
        out = []
        while b"\n" in self.pending:
            raw, self.pending = self.pending.split(b"\n", 1)
            try:
                line = raw.decode("utf-8", errors="strict")
            except UnicodeError:
                out.append("[invalid terminal encoding]\n")
                continue
            # Remove complete escape sequences, then remaining control bytes.
            line = re.sub(r"\x1b\][^\x07]*(?:\x07|\x1b\\)", "", line)
            line = re.sub(r"\x1b\[[0-?]*[ -/]*[@-~]", "", line)
            line = "".join(c for c in line if c in "\t\r" or ord(c) >= 32 and ord(c) != 127)
            if "BEGIN " in line and "PRIVATE KEY" in line:
                self.private = True
            if self.private:
                if "END " in line and "PRIVATE KEY" in line:
                    self.private = False
                out.append("[redacted]\n")
                continue
            if re.search(
                r"(?i)(authorization\s*:|bearer\s+|(?:token|secret|password)\s*[=:]|(?:sk|pk|rk)-[A-Za-z0-9._-]{16,}|gh[pousr]_[A-Za-z0-9]{20,}|(?:x-amz-signature|signature|sig)=)",
                line,
            ):
                line = "[redacted]"
            out.append(line + "\n")
        return "".join(out)
