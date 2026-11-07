"""Operator-only, fresh CPU Node metadata; never enrollment or execution.

Public leaf identity/validity is checked by the existing channel contract. CA
chain/custody approval remains an external operator prerequisite: this module
does not install trust or authenticate a certificate issuer. IDs are fresh in
the selected tenant (the existing composite-PK identity namespace).

The selected connection and its authentication/TLS profile are trusted operator
deployment inputs. This library is not a libpq filesystem or DSN sandbox; it
does not discover credentials, install trust, or authorize a deployment profile.

Connections must be idle. Each call owns its transaction; APPLY cannot return a
COMMITTED receipt from a caller's uncommitted savepoint. No retries/upserts are
provided. A lost commit acknowledgement requires read-only reconciliation.
"""

import base64
import binascii
from dataclasses import dataclass
import hashlib
import json
import re
from uuid import UUID

from psycopg import errors
from psycopg.pq import TransactionStatus
from psycopg.rows import tuple_row

from .errors import DomainError
from .node_channels import certificate_identity, endpoint_parts, provision_channel
from .tooling import NodePrincipal

MAX_REQUEST_BYTES = 128 * 1024
MAX_DER_BYTES = 65536
CPU_MILLIS = 500
MEMORY_BYTES = 67108864
MAX_VERSION = 9007199254740991
FIELDS = frozenset({
    "requestVersion", "tenantId", "recoveryEpoch", "projectId", "nodeId",
    "cpuResourceId", "memoryResourceId", "endpoint", "certificateDERBase64",
    "expectedTenantControlVersion", "cpuMillis", "memoryBytes",
})
# This closed map also constrains CLI errors; exception messages are never output.
SAFE_ERRORS = {
    "FRESH-0001": 422, "FRESH-0002": 409, "FRESH-0003": 409,
    "FRESH-0004": 403, "FRESH-0005": 409, "FRESH-0006": 409,
    "FRESH-0007": 409, "FRESH-0008": 409, "FRESH-0009": 500,
    "FRESH-0010": 503, "FRESH-0011": 503, "FRESH-0012": 503,
    "NODE-0031": 422, "NODE-0032": 403, "NODE-0033": 403,
    "NODE-0034": 409,
}


def refuse(code):
    raise DomainError(code, "Fresh CPU metadata admission refused", SAFE_ERRORS[code]) from None


def _pairs(pairs):
    result = {}
    for key, value in pairs:
        if key in result:
            refuse("FRESH-0001")
        result[key] = value
    return result


def _constant(_):
    refuse("FRESH-0001")


@dataclass(frozen=True)
class PreparedAdmission:
    tenant: str
    epoch: str
    project: str
    node: str
    cpu: str
    memory: str
    endpoint: str
    der: bytes
    control_version: int
    fingerprint: str
    not_after: object

    def plan_body(self):
        return {
            "planVersion": 1,
            "tenantId": self.tenant, "recoveryEpoch": self.epoch,
            "projectId": self.project, "nodeId": self.node,
            "cpuResourceId": self.cpu, "memoryResourceId": self.memory,
            "endpoint": self.endpoint,
            "certificateSHA256": self.fingerprint,
            "certificateNotAfter": self.not_after.isoformat(),
            "expectedTenantControlVersion": self.control_version,
            "cpuMillis": CPU_MILLIS, "memoryBytes": MEMORY_BYTES,
            "initialStatus": "offline", "initialChannelVersion": 1,
            "projectMembershipEnabled": True,
            "certificateIssuerChainVerified": False,
            "executionAuthorized": False,
        }

    def digest(self):
        return hashlib.sha256(json.dumps(
            self.plan_body(), sort_keys=True, separators=(",", ":"),
            ensure_ascii=True, allow_nan=False,
        ).encode("ascii")).hexdigest()


def prepare_request(raw):
    """Bound/parse/validate public bytes before DB work or held DB locks."""
    if type(raw) is not bytes or not 0 < len(raw) <= MAX_REQUEST_BYTES:
        refuse("FRESH-0001")
    try:
        body = json.loads(raw.decode("utf-8"), object_pairs_hook=_pairs,
                          parse_constant=_constant)
        if type(body) is not dict or set(body) != FIELDS:
            refuse("FRESH-0001")
        for key in FIELDS - {"requestVersion", "expectedTenantControlVersion",
                             "cpuMillis", "memoryBytes"}:
            if type(body[key]) is not str:
                refuse("FRESH-0001")
        for key, expected in (("requestVersion", 1), ("cpuMillis", CPU_MILLIS),
                              ("memoryBytes", MEMORY_BYTES)):
            if type(body[key]) is not int or body[key] != expected:
                refuse("FRESH-0001")
        version = body["expectedTenantControlVersion"]
        if type(version) is not int or not 0 <= version <= MAX_VERSION:
            refuse("FRESH-0001")
        for key in ("tenantId", "recoveryEpoch"):
            if str(UUID(body[key])) != body[key]:
                refuse("FRESH-0001")
        for key, prefix in (("projectId", "prj"), ("nodeId", "nod"),
                            ("cpuResourceId", "res"), ("memoryResourceId", "res")):
            if not re.fullmatch(prefix + r"_[0-9A-HJKMNP-TV-Z]{26}", body[key]):
                refuse("FRESH-0001")
        if body["cpuResourceId"] == body["memoryResourceId"]:
            refuse("FRESH-0001")
        encoded = body["certificateDERBase64"]
        if not 0 < len(encoded) <= 4 * ((MAX_DER_BYTES + 2) // 3):
            refuse("FRESH-0001")
        der = base64.b64decode(encoded, validate=True)
        if not 0 < len(der) <= MAX_DER_BYTES or base64.b64encode(der).decode() != encoded:
            refuse("FRESH-0001")
    except (ValueError, TypeError, UnicodeError, binascii.Error, RecursionError):
        refuse("FRESH-0001")
    endpoint_parts(body["endpoint"])
    fingerprint, not_after = certificate_identity(
        der, NodePrincipal(body["tenantId"], body["nodeId"]), body["recoveryEpoch"],
    )
    return PreparedAdmission(
        body["tenantId"], body["recoveryEpoch"], body["projectId"],
        body["nodeId"], body["cpuResourceId"], body["memoryResourceId"],
        body["endpoint"], der, version, fingerprint, not_after,
    )


def _idle(conn):
    if conn.info.transaction_status != TransactionStatus.IDLE:
        refuse("FRESH-0003")


def _operator(cursor):
    # Identifiers here are source constants, never request table/column names.
    privileges = cursor.execute("""SELECT count(*)=5 AND
        coalesce(bool_and(has_table_privilege(current_user,c.oid,'INSERT')),false)
        AND has_schema_privilege(current_user,'inv','USAGE')
        FROM pg_catalog.pg_class c JOIN pg_catalog.pg_namespace n ON n.oid=c.relnamespace
        WHERE n.nspname='inv' AND c.relname IN
        ('nodes','resources','project_nodes','node_channels','node_channel_audit')""").fetchone()
    if not privileges or privileges[0] is not True:
        refuse("FRESH-0004")


def _preflight(cursor, item, *, locked):
    _operator(cursor)
    cursor.execute("SELECT set_config('inv.tenant_id',%s,true)", (item.tenant,))
    lock = " FOR SHARE" if locked else ""
    epoch = cursor.execute(
        "SELECT epoch FROM inv.control_epoch WHERE singleton" + lock,
    ).fetchone()
    if not epoch or str(epoch[0]) != item.epoch:
        refuse("FRESH-0006")
    tenant = cursor.execute(
        "SELECT tenant_id FROM inv.tenants WHERE tenant_id=%s" + lock,
        (item.tenant,),
    ).fetchone()
    project = cursor.execute(
        "SELECT project_id FROM inv.projects WHERE tenant_id=%s AND project_id=%s" + lock,
        (item.tenant, item.project),
    ).fetchone()
    if not tenant or not project:
        refuse("FRESH-0005")
    control = cursor.execute(
        "SELECT version,kill_switch,updated_at FROM inv.tenant_controls WHERE tenant_id=%s" + lock,
        (item.tenant,),
    ).fetchone()
    if not control or control[0] != item.control_version:
        refuse("FRESH-0007")
    business = cursor.execute(
        "SELECT enabled FROM inv.business_projects WHERE tenant_id=%s AND project_id=%s" + lock,
        (item.tenant, item.project),
    ).fetchone()
    if business:
        public = cursor.execute(
            "SELECT status FROM public.projects WHERE tenant_id=%s AND project_id=%s" + lock,
            (item.tenant, item.project),
        ).fetchone()
        if not business[0] or not public or public[0] != "active":
            refuse("FRESH-0005")
    collision = cursor.execute("""SELECT
        EXISTS(SELECT 1 FROM inv.nodes WHERE tenant_id=%s AND node_id=%s),
        EXISTS(SELECT 1 FROM inv.resources WHERE tenant_id=%s AND resource_id IN (%s,%s)),
        EXISTS(SELECT 1 FROM inv.project_nodes WHERE tenant_id=%s AND node_id=%s),
        EXISTS(SELECT 1 FROM inv.node_channels WHERE tenant_id=%s AND node_id=%s),
        EXISTS(SELECT 1 FROM inv.node_channel_audit WHERE tenant_id=%s AND node_id=%s)""",
        (item.tenant, item.node, item.tenant, item.cpu, item.memory,
         item.tenant, item.node, item.tenant, item.node, item.tenant, item.node),
    ).fetchone()
    if any(collision):
        refuse("FRESH-0008")
    return control


def _receipt(item, mode, status):
    return {"mode": mode, "status": status, "planSha256": item.digest(),
            "plan": item.plan_body()}


def plan_admission(conn, raw):
    """SELECT-only preflight. READY is an observation, never an apply grant."""
    item = prepare_request(raw)
    _idle(conn)
    try:
        with conn.transaction(), conn.cursor(row_factory=tuple_row) as cursor:
            _preflight(cursor, item, locked=False)
    except DomainError:
        raise
    except Exception:
        refuse("FRESH-0011")
    return _receipt(item, "PLAN", "READY")


def _readback(cursor, item, control):
    node = cursor.execute("""SELECT status,recovery_epoch FROM inv.nodes
        WHERE tenant_id=%s AND node_id=%s""", (item.tenant, item.node)).fetchone()
    resources = cursor.execute("""SELECT resource_id,node_id,kind,capacity,offered
        FROM inv.resources WHERE tenant_id=%s AND node_id=%s ORDER BY resource_id""",
        (item.tenant, item.node)).fetchall()
    expected_resources = sorted([
        (item.cpu, item.node, "cpu", CPU_MILLIS, CPU_MILLIS),
        (item.memory, item.node, "memory", MEMORY_BYTES, MEMORY_BYTES),
    ])
    memberships = cursor.execute("""SELECT project_id,enabled FROM inv.project_nodes
        WHERE tenant_id=%s AND node_id=%s""", (item.tenant, item.node)).fetchall()
    channel = cursor.execute("""SELECT recovery_epoch,version,endpoint,certificate_sha256,
        certificate_not_after,enabled FROM inv.node_channels WHERE tenant_id=%s AND node_id=%s""",
        (item.tenant, item.node)).fetchone()
    audit = cursor.execute("""SELECT version,action,certificate_sha256 FROM inv.node_channel_audit
        WHERE tenant_id=%s AND node_id=%s""", (item.tenant, item.node)).fetchall()
    after = cursor.execute("""SELECT version,kill_switch,updated_at FROM inv.tenant_controls
        WHERE tenant_id=%s""", (item.tenant,)).fetchone()
    seeded = cursor.execute("""SELECT version FROM inv.node_controls
        WHERE tenant_id=%s AND node_id=%s""", (item.tenant, item.node)).fetchall()
    if (not node or node[0] != "offline" or str(node[1]) != item.epoch
            or resources != expected_resources or memberships != [(item.project, True)]
            or not channel or str(channel[0]) != item.epoch
            or channel[1:] != (1, item.endpoint, item.fingerprint, item.not_after, True)
            or audit != [(1, "provision", item.fingerprint)] or after != control
            or seeded != [(0,)]):
        refuse("FRESH-0009")


def apply_admission(conn, raw, *, expected_plan_sha256):
    """Atomic fresh insert; commit acknowledged before returning COMMITTED.

    No retry on collision, serialization failure or uncertain commit. The existing
    node trigger seeds its own version-0 node_controls row. No existing control,
    grant, snapshot, probe, lease, Run or approval is changed by this writer.
    """
    item = prepare_request(raw)
    if (type(expected_plan_sha256) is not str
            or not re.fullmatch(r"[0-9a-f]{64}", expected_plan_sha256)
            or expected_plan_sha256 != item.digest()):
        refuse("FRESH-0002")
    _idle(conn)
    ready_to_commit = False
    try:
        with conn.transaction(), conn.cursor(row_factory=tuple_row) as cursor:
            control = _preflight(cursor, item, locked=True)
            cursor.execute("""INSERT INTO inv.nodes(tenant_id,node_id,status,recovery_epoch)
                VALUES(%s,%s,'offline',%s)""", (item.tenant, item.node, item.epoch))
            cursor.execute("""INSERT INTO inv.resources
                (tenant_id,resource_id,node_id,kind,capacity,offered)
                VALUES(%s,%s,%s,'cpu',%s,%s),(%s,%s,%s,'memory',%s,%s)""",
                (item.tenant, item.cpu, item.node, CPU_MILLIS, CPU_MILLIS,
                 item.tenant, item.memory, item.node, MEMORY_BYTES, MEMORY_BYTES))
            cursor.execute("""INSERT INTO inv.project_nodes(tenant_id,project_id,node_id,enabled)
                VALUES(%s,%s,%s,true)""", (item.tenant, item.project, item.node))
            provision_channel(
                conn, NodePrincipal(item.tenant, item.node), epoch=item.epoch,
                endpoint=item.endpoint, certificate_der=item.der, expected_version=0,
            )
            _readback(cursor, item, control)
            ready_to_commit = True
    except DomainError:
        raise
    except errors.UniqueViolation:
        refuse("FRESH-0008")
    except Exception:
        # No raw PostgreSQL/driver diagnostics may cross the CLI boundary.
        refuse("FRESH-0010" if ready_to_commit else "FRESH-0011")
    result = _receipt(item, "APPLY", "COMMITTED")
    result["readbackVerifiedBeforeCommit"] = True
    result["nodeControlSeedVersion"] = 0
    return result


def reconcile_admission(conn, raw):
    """Read-only exact-row check after an unknown commit; never retries APPLY.

    A match proves present metadata, not which attempt committed it. A mismatch
    remains HOLD; absence is not permission to apply again. Read-only SELECTs
    take one repeatable-read snapshot, with no externally held DB transaction.
    """
    item = prepare_request(raw)
    _idle(conn)
    try:
        with conn.transaction(), conn.cursor(row_factory=tuple_row) as cursor:
            cursor.execute("SET TRANSACTION ISOLATION LEVEL REPEATABLE READ, READ ONLY")
            _operator(cursor)
            cursor.execute("SELECT set_config('inv.tenant_id',%s,true)", (item.tenant,))
            epoch = cursor.execute("SELECT epoch FROM inv.control_epoch WHERE singleton").fetchone()
            if not epoch or str(epoch[0]) != item.epoch:
                refuse("FRESH-0006")
            control = cursor.execute("""SELECT version,kill_switch,updated_at
                FROM inv.tenant_controls WHERE tenant_id=%s""", (item.tenant,)).fetchone()
            if not control or control[0] != item.control_version:
                refuse("FRESH-0007")
            _readback(cursor, item, control)
    except DomainError:
        raise
    except Exception:
        refuse("FRESH-0011")
    return _receipt(item, "RECONCILE", "MATCHED_METADATA_REQUIRES_OPERATOR_DISPOSITION")
