"""Node enrollment, heartbeat and listing (S02-BE).

Scope: registration and observation. Nothing here reserves a resource; that is
ADR-005 territory and belongs to S05.

Every function takes an open session already inside a tenant scope. None of them
opens its own transaction, because the caller composes them — the enrollment
path writes the node, its capabilities, its offers and an audit row, and those
must land together or not at all.
"""

from __future__ import annotations

import datetime as dt
import uuid
from dataclasses import dataclass

from sqlalchemy import case, select, update

from ..db.models import Node, NodeCapability, ResourceOffer, ResourceSnapshot
from ..errors import RES_NODE_NOT_FOUND, VAL_SCHEMA, InvError
from ..identity.tokens import consume_bootstrap_token
from ..ids import new_id
from ..units import KINDS, canonical_unit, to_canonical
from .pagination import Page, build_page, clamp_limit, validate_cursor

OS_TYPES = ("windows", "linux")


@dataclass(frozen=True, slots=True)
class CapabilityInput:
    """What a node says it has, in whatever unit its agent measured.

    The unit is converted to the canonical one for the kind before anything is
    stored (``saintvision.units``). A node that reports GiB and a node that
    reports bytes must end up comparable, because the platform's entire job is
    to add their capacity together and subtract what is in use.
    """

    kind: str
    total_quantity: float
    unit: str
    device_index: int | None = None
    vendor: str | None = None
    model: str | None = None
    divisible: bool = False
    offered_quantity: float | None = None

    def canonical_total(self) -> int:
        return to_canonical(self.kind, self.total_quantity, self.unit)

    def canonical_offered(self) -> int | None:
        if self.offered_quantity is None:
            return None
        return to_canonical(self.kind, self.offered_quantity, self.unit)

    def validate(self) -> None:
        if self.kind not in KINDS:
            raise InvError(VAL_SCHEMA, f"unknown capability kind: {self.kind!r}")
        if self.total_quantity < 0:
            raise InvError(VAL_SCHEMA, "total_quantity must not be negative")
        # Raises if the unit is not one this kind can be measured in. Doing it
        # during validation rather than at the INSERT means the node is told
        # what was wrong with its report instead of getting a constraint name.
        self.canonical_total()
        self.canonical_offered()
        if (self.kind == "gpu") != (self.device_index is not None):
            raise InvError(
                VAL_SCHEMA, "device_index is required for gpu and forbidden otherwise"
            )
        if self.offered_quantity is not None:
            if self.offered_quantity < 0:
                raise InvError(VAL_SCHEMA, "offered_quantity must not be negative")
            # The owner cannot offer more than the machine has. Enforced here
            # as well as by the scheduler, because a bad offer poisons every
            # later placement decision.
            if self.offered_quantity > self.total_quantity:
                raise InvError(
                    VAL_SCHEMA, "offered_quantity must not exceed total_quantity"
                )


def enroll_node(
    session,
    *,
    tenant_id: uuid.UUID,
    bootstrap_secret: str,
    hostname: str,
    os_type: str,
    os_version: str,
    agent_version: str,
    capabilities: list[CapabilityInput],
    certificate_fingerprint: str | None,
    labels: dict | None,
    now: dt.datetime,
) -> Node:
    """Exchange a one-time bootstrap token for an enrolled node.

    The token is consumed *before* the node row is written, so a failure after
    consumption cannot leave a usable token behind — the operator reissues
    rather than the platform silently accepting the same secret twice.
    """
    if os_type not in OS_TYPES:
        raise InvError(VAL_SCHEMA, f"unsupported os_type: {os_type!r}")
    if not hostname or len(hostname) > 253:
        raise InvError(VAL_SCHEMA, "hostname must be 1..253 characters")
    for capability in capabilities:
        capability.validate()

    node_id = new_id("node")
    consume_bootstrap_token(session, secret=bootstrap_secret, node_id=node_id, now=now)

    node = Node(
        node_id=node_id,
        tenant_id=tenant_id,
        hostname=hostname,
        os_type=os_type,
        os_version=os_version,
        agent_version=agent_version,
        status="active" if certificate_fingerprint else "enrolling",
        certificate_fingerprint=certificate_fingerprint,
        labels=labels or {},
        enrolled_at=now,
        heartbeat_sequence=0,
    )
    session.add(node)
    session.flush()

    for capability in capabilities:
        capability_id = new_id("capability")
        session.add(
            NodeCapability(
                capability_id=capability_id,
                tenant_id=tenant_id,
                node_id=node_id,
                kind=capability.kind,
                device_index=capability.device_index,
                vendor=capability.vendor,
                model=capability.model,
                total_quantity=capability.canonical_total(),
                unit=canonical_unit(capability.kind),
                divisible=capability.divisible,
                detected_at=now,
            )
        )
        if capability.offered_quantity is not None:
            session.add(
                ResourceOffer(
                    offer_id=new_id("offer"),
                    tenant_id=tenant_id,
                    capability_id=capability_id,
                    offered_quantity=capability.canonical_offered(),
                    effective_from=now,
                )
            )
    session.flush()
    return node


@dataclass(frozen=True, slots=True)
class HeartbeatOutcome:
    """What the heartbeat did. ``applied`` is decided by the database, not by us."""

    node: Node
    applied: bool


def record_heartbeat(
    session,
    *,
    tenant_id: uuid.UUID,
    node_id: str,
    sequence: int,
    now: dt.datetime,
) -> HeartbeatOutcome:
    """Apply a heartbeat if — and only if — its sequence advances.

    One conditional UPDATE, not a read followed by a write. Reading the current
    sequence and then writing it back lets two heartbeats that arrive together
    both observe the old value and both proceed, so a replayed sequence 5 can
    overwrite a live sequence 7 and the node's liveness runs backwards. The
    ``heartbeat_sequence < :sequence`` predicate is evaluated by PostgreSQL
    while it holds the row, which is the only place the comparison and the
    write are indivisible.

    Zero rows updated means the sequence did not advance: a replay, a reorder,
    or a duplicate delivery. That is ignored rather than an error — at-least-once
    delivery makes it a normal event (ADR-007) — but it is reported as
    ``applied=False`` so the caller never mistakes it for a fresh beat.
    """
    updated = session.execute(
        update(Node)
        .where(
            Node.node_id == node_id,
            Node.tenant_id == tenant_id,
            # The guard. Anything not strictly greater is stale by definition.
            Node.heartbeat_sequence < sequence,
        )
        .values(
            heartbeat_sequence=sequence,
            last_heartbeat_at=now,
            # A node that was declared lost and is heard from again is back.
            # Written in the same statement so it cannot be applied to a row
            # whose sequence check failed.
            status=case((Node.status == "lost", "active"), else_=Node.status),
        )
        .returning(Node)
        .execution_options(synchronize_session=False, populate_existing=True)
    ).scalar_one_or_none()

    if updated is not None:
        return HeartbeatOutcome(node=updated, applied=True)

    # Nothing advanced. Distinguish "no such node" from "stale sequence": the
    # first is a caller error and the second is routine.
    node = session.get(Node, node_id)
    if node is None or node.tenant_id != tenant_id:
        # A node in another tenant is reported as absent, not as forbidden.
        raise InvError(RES_NODE_NOT_FOUND, "node not found")
    session.refresh(node)
    return HeartbeatOutcome(node=node, applied=False)


@dataclass(frozen=True, slots=True)
class ObservationInput:
    """One utilisation reading, in whatever unit the node's agent measured."""

    capability_id: str
    used_quantity: float
    unit: str


def record_observations(
    session,
    *,
    tenant_id: uuid.UUID,
    node_id: str,
    observations: list[ObservationInput],
    now: dt.datetime,
) -> int:
    """Store utilisation readings for capabilities this node actually has.

    Two things are checked here that the database now also enforces, and the
    reason to check them here as well is that the node deserves to be told what
    was wrong with its report rather than receiving a constraint violation.

    **The capability must belong to the reporting node.** Nothing used to say
    so. An enrolled node could post utilisation against any capability id in
    its tenant, and ``node_spare`` files each reading under the *reporting*
    node while taking the kind from the *named* capability. A busy machine
    could therefore report zero against a capability it does not own, leave its
    real RAM unobserved, and be ranked as the idlest node in the pool — which
    is precisely the placement the heartbeat authentication was added to
    protect.

    **The unit is converted, not trusted.** The reading is compared against the
    offer by subtraction, so a reading in MB against an offer in GiB is not a
    smaller error than a missing reading.

    ``observed_at`` is the server's clock, never the node's. A node that is
    ahead of the control plane would otherwise write a reading that stays
    "fresh" for as long as the skew lasts, keeping a stale utilisation figure
    in front of every placement decision. ADR-021 puts clock skew on the
    control plane's side of every ordering question, and this is one.
    """
    if not observations:
        return 0

    owned = {
        capability_id: kind
        for capability_id, kind in session.execute(
            select(NodeCapability.capability_id, NodeCapability.kind).where(
                NodeCapability.tenant_id == tenant_id,
                NodeCapability.node_id == node_id,
            )
        ).all()
    }

    rows = []
    for observation in observations:
        kind = owned.get(observation.capability_id)
        if kind is None:
            raise InvError(
                VAL_SCHEMA,
                "the observed capability does not belong to this node",
                extra={"capabilityId": observation.capability_id},
            )
        rows.append(
            ResourceSnapshot(
                snapshot_id=new_id("snapshot"),
                observed_at=now,
                tenant_id=tenant_id,
                node_id=node_id,
                capability_id=observation.capability_id,
                used_quantity=to_canonical(
                    kind, observation.used_quantity, observation.unit
                ),
            )
        )
    session.add_all(rows)
    session.flush()
    return len(rows)


def mark_lost_nodes(
    session, *, tenant_id: uuid.UUID, now: dt.datetime, timeout_seconds: int = 60
) -> int:
    """Mark active nodes whose heartbeat is older than the timeout as lost.

    AC-02's detection target is 60 seconds. Nodes that never sent a heartbeat
    are judged from ``enrolled_at`` instead, so a node that enrolls and then
    goes silent is still detected.
    """
    cutoff = now - dt.timedelta(seconds=timeout_seconds)
    nodes = session.scalars(
        select(Node).where(Node.tenant_id == tenant_id, Node.status == "active")
    ).all()
    changed = 0
    # Node loss is also a storage event.  Keep the catalogue and its manifests,
    # but make copies on the departed node unavailable in the same transaction
    # as the liveness transition.  Without this call the replica repair service
    # existed only as a directly-tested helper and placement could continue to
    # count a lost node's copy as ready.
    from .replica_repair import mark_node_replicas_unavailable

    for node in nodes:
        last_seen = node.last_heartbeat_at or node.enrolled_at
        if last_seen < cutoff:
            node.status = "lost"
            mark_node_replicas_unavailable(
                session,
                tenant_id=tenant_id,
                node_id=node.node_id,
                now=now,
            )
            changed += 1
    if changed:
        session.flush()
    return changed


def get_node(session, *, tenant_id: uuid.UUID, node_id: str) -> Node:
    node = session.get(Node, node_id)
    if node is None or node.tenant_id != tenant_id:
        raise InvError(RES_NODE_NOT_FOUND, "node not found")
    return node


def list_nodes(
    session,
    *,
    tenant_id: uuid.UUID,
    limit: int | None = None,
    cursor: str | None = None,
    status: str | None = None,
    default_limit: int = 50,
    max_limit: int = 200,
) -> Page:
    effective = clamp_limit(limit, default=default_limit, maximum=max_limit)
    after = validate_cursor(cursor)
    query = select(Node).where(Node.tenant_id == tenant_id)
    if status is not None:
        query = query.where(Node.status == status)
    if after is not None:
        query = query.where(Node.node_id > after)
    rows = session.scalars(query.order_by(Node.node_id).limit(effective + 1)).all()
    return build_page(rows, limit=effective, id_attr="node_id")


def list_capabilities(session, *, tenant_id: uuid.UUID, node_id: str) -> list[NodeCapability]:
    return list(
        session.scalars(
            select(NodeCapability)
            .where(
                NodeCapability.tenant_id == tenant_id,
                NodeCapability.node_id == node_id,
            )
            .order_by(NodeCapability.capability_id)
        ).all()
    )
