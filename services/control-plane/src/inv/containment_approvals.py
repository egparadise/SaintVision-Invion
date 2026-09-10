"""Fixed L2 administrative intent, two other verified people, single-use nonce."""

import secrets
from uuid import UUID, uuid4
from psycopg.types.json import Jsonb
from .approvals import Principal, digest
from .contracts import validate_contract
from .containment import Containment, operator
from .errors import DomainError


def key_valid(key):
    if not isinstance(key, str) or not 1 <= len(key) <= 200:
        raise DomainError("VAL-0003", "Idempotency-Key required", 422)


def identity(value):
    try:
        return str(UUID(value))
    except (ValueError, TypeError, AttributeError):
        raise DomainError("VAL-0003", "Approval UUID required", 422) from None


def view(row):
    result = {
        "approvalId": str(row["approval_id"]),
        "operation": row["operation"],
        "nodeId": row["node_id"],
        "expectedVersion": row["expected_version"],
        "gateVersion": row["gate_version"],
        "reasonCode": row["reason_code"],
        "contentDigest": row["content_digest"],
        "status": row["status"],
        "expiresAt": row["expires_at"].isoformat(),
        "requiredApprovals": 2,
    }
    validate_contract("ContainmentApprovalView", result)
    return result


class ControlApprovals:
    def __init__(self, db):
        self.db = db

    def _load(self, conn, approval_id):
        row = conn.execute(
            "SELECT * FROM inv.containment_approvals WHERE approval_id=%s FOR UPDATE",
            (identity(approval_id),),
        ).fetchone()
        if not row:
            raise DomainError("RES-0004", "Containment approval unavailable", 404)
        return row

    def _current(self, conn, row):
        now = conn.execute("SELECT clock_timestamp() AS now").fetchone()["now"]
        current = Containment(self.db)._view(conn, row["node_id"])
        gate = conn.execute("SELECT version FROM inv.tenant_controls").fetchone()["version"]
        if (
            row["expires_at"] <= now
            or str(row["recovery_epoch"]) != self.db.recovery_epoch
            or row["gate_version"] != gate
            or row["expected_version"] != current["version"]
        ):
            raise DomainError("AUTH-0063", "Containment approval expired or scope changed", 403)
        requester = operator(
            conn,
            Principal(str(row["tenant_id"]), row["requester_id"]),
            "can_resume" if row["operation"] in {"clear", "resume"} else "can_contain",
        )
        if requester["person_id"] != row["requester_person_id"]:
            raise DomainError("AUTH-0063", "Requester identity changed", 403)

    def propose(self, principal, data, key):
        validate_contract("ContainmentProposalInput", data)
        key_valid(key)
        if (data["nodeId"] is None) != (data["operation"] in {"kill", "clear"}):
            raise DomainError("VAL-0003", "Containment proposal scope differs", 422)
        request_hash = digest({"actor": principal.subject_id, **data})
        with self.db.transaction(principal.tenant_id) as conn:
            requester = operator(
                conn,
                principal,
                "can_resume" if data["operation"] in {"clear", "resume"} else "can_contain",
            )
            prior = conn.execute(
                "SELECT * FROM inv.containment_approvals WHERE requester_id=%s AND key=%s",
                (principal.subject_id, key),
            ).fetchone()
            if prior:
                if prior["request_hash"] != request_hash:
                    raise DomainError("IDEM-0001", "Proposal key has different content")
                return view(prior)
            current = Containment(self.db)._view(conn, data["nodeId"])
            if current["version"] != data["expectedVersion"]:
                raise DomainError("GRAPH-0003", "Control version changed; reload before approval")
            gate = conn.execute("SELECT version FROM inv.tenant_controls").fetchone()["version"]
            content = digest(
                {
                    "tenant": principal.tenant_id,
                    "requester": principal.subject_id,
                    "person": str(requester["person_id"]),
                    "epoch": self.db.recovery_epoch,
                    "gateVersion": gate,
                    **data,
                }
            )
            row = conn.execute(
                """INSERT INTO inv.containment_approvals(tenant_id,approval_id,key,requester_id,requester_person_id,operation,node_id,expected_version,gate_version,recovery_epoch,reason_code,content_digest,request_hash,created_at,expires_at)
                VALUES(%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,statement_timestamp(),statement_timestamp()+interval '5 minutes')
                ON CONFLICT DO NOTHING RETURNING *""",
                (
                    principal.tenant_id,
                    uuid4(),
                    key,
                    principal.subject_id,
                    requester["person_id"],
                    data["operation"],
                    data["nodeId"],
                    data["expectedVersion"],
                    gate,
                    self.db.recovery_epoch,
                    data["reasonCode"],
                    content,
                    request_hash,
                ),
            ).fetchone()
            if not row:
                row = conn.execute(
                    "SELECT * FROM inv.containment_approvals WHERE requester_id=%s AND key=%s",
                    (principal.subject_id, key),
                ).fetchone()
                if row["request_hash"] != request_hash:
                    raise DomainError("IDEM-0001", "Proposal key has different content")
            return view(row)

    def get(self, principal, approval_id):
        with self.db.transaction(principal.tenant_id) as conn:
            operator(conn, principal)
            return view(self._load(conn, approval_id))

    def challenge(self, principal, approval_id):
        with self.db.transaction(principal.tenant_id) as conn:
            actor = operator(conn, principal, "can_approve")
            row = self._load(conn, approval_id)
            self._current(conn, row)
            if row["status"] != "pending" or actor["person_id"] == row["requester_person_id"]:
                raise DomainError("AUTH-0063", "A distinct current approver is required", 403)
            nonce = secrets.token_hex(32)
            conn.execute(
                "INSERT INTO inv.containment_challenges(tenant_id,approval_id,actor_id,person_id,nonce,expires_at) VALUES(%s,%s,%s,%s,%s,least(clock_timestamp()+interval '60 seconds',%s))",
                (
                    principal.tenant_id,
                    row["approval_id"],
                    principal.subject_id,
                    actor["person_id"],
                    nonce,
                    row["expires_at"],
                ),
            )
            return {"nonce": nonce, "contentDigest": row["content_digest"]}

    def decide(self, principal, approval_id, data, key):
        validate_contract("ContainmentDecisionInput", data)
        key_valid(key)
        hashed = digest({"actor": principal.subject_id, **data})
        with self.db.transaction(principal.tenant_id) as conn:
            actor = operator(conn, principal, "can_approve")
            row = self._load(conn, approval_id)
            prior = conn.execute(
                "SELECT * FROM inv.containment_votes WHERE approval_id=%s AND (actor_id=%s OR key=%s)",
                (row["approval_id"], principal.subject_id, key),
            ).fetchone()
            if prior:
                if (
                    prior["request_hash"] != hashed
                    or prior["key"] != key
                    or prior["actor_id"] != principal.subject_id
                ):
                    raise DomainError("IDEM-0001", "Vote identity or key differs")
                return prior["response"]
            self._current(conn, row)
            if (
                row["status"] != "pending"
                or row["content_digest"] != data["contentDigest"]
                or actor["person_id"] == row["requester_person_id"]
            ):
                raise DomainError(
                    "AUTH-0063", "Distinct current approval of fixed content required", 403
                )
            used = conn.execute(
                "UPDATE inv.containment_challenges SET used_at=clock_timestamp() WHERE approval_id=%s AND actor_id=%s AND person_id=%s AND nonce=%s AND used_at IS NULL AND expires_at>clock_timestamp() RETURNING nonce",
                (row["approval_id"], principal.subject_id, actor["person_id"], data["nonce"]),
            ).fetchone()
            if not used:
                raise DomainError(
                    "AUTH-0063", "Approval challenge expired, used or mismatched", 403
                )
            conn.execute(
                "INSERT INTO inv.containment_votes(tenant_id,approval_id,actor_id,person_id,key,decision,request_hash) VALUES(%s,%s,%s,%s,%s,%s,%s)",
                (
                    principal.tenant_id,
                    row["approval_id"],
                    principal.subject_id,
                    actor["person_id"],
                    key,
                    data["decision"],
                    hashed,
                ),
            )
            votes = conn.execute(
                "SELECT decision FROM inv.containment_votes WHERE approval_id=%s",
                (row["approval_id"],),
            ).fetchall()
            status = (
                "rejected"
                if data["decision"] == "reject"
                else "approved" if len(votes) == 2 else "pending"
            )
            if status != "pending":
                row = conn.execute(
                    "UPDATE inv.containment_approvals SET status=%s WHERE approval_id=%s RETURNING *",
                    (status, row["approval_id"]),
                ).fetchone()
            result = view(row)
            conn.execute(
                "UPDATE inv.containment_votes SET response=%s WHERE approval_id=%s AND actor_id=%s",
                (Jsonb(result), row["approval_id"], principal.subject_id),
            )
            return result

    def consume(self, conn, principal, operation, node_id, data, request_id):
        row = self._load(conn, data["approvalId"])
        self._current(conn, row)
        if (
            row["status"] != "approved"
            or row["requester_id"] != principal.subject_id
            or row["operation"] != operation
            or row["node_id"] != node_id
            or row["expected_version"] != data["expectedVersion"]
            or row["reason_code"] != data["reasonCode"]
        ):
            raise DomainError("AUTH-0063", "Matching current L2 approval required", 403)
        votes = conn.execute(
            "SELECT * FROM inv.containment_votes WHERE approval_id=%s ORDER BY actor_id",
            (row["approval_id"],),
        ).fetchall()
        people = {row["requester_person_id"]}
        if len(votes) != 2:
            raise DomainError("AUTH-0063", "Two distinct current approvals required", 403)
        for vote in votes:
            actor = operator(conn, Principal(principal.tenant_id, vote["actor_id"]), "can_approve")
            if (
                vote["decision"] != "approve"
                or actor["person_id"] != vote["person_id"]
                or vote["person_id"] in people
            ):
                raise DomainError("AUTH-0063", "Two distinct current people required", 403)
            people.add(vote["person_id"])
        conn.execute(
            "UPDATE inv.containment_approvals SET status='consumed',consumed_request_id=%s WHERE approval_id=%s",
            (request_id, row["approval_id"]),
        )
