"""Finding machines on the internal network, and admitting them.

The Node Agent announces itself; the Control Plane lists it as a candidate. The
security property that makes this safe is simple and absolute:

**Announcing grants nothing.** A candidate is a row a person can look at. It
becomes a node only when someone admits it, and admission goes through the same
one-time bootstrap token the manual path already uses. Discovery changes how
you *find* a machine, not who may join.

Everything a machine says about itself is a claim. ``claimed_ram_bytes`` is
what the agent reported, not what the machine has; the authoritative figures
arrive after enrollment over an authenticated channel. The capacity maths in
:mod:`saintvision.services.pools` reads only the authoritative ones.
"""

from __future__ import annotations

import datetime as dt
import uuid
from dataclasses import dataclass
from typing import Any

from sqlalchemy import func, select, update
from sqlalchemy.dialects.postgresql import insert as pg_insert
from sqlalchemy.orm import Session

from ..db.models import (
    ANNOUNCEMENT_TTL_SECONDS,
    MAX_CANDIDATES_PER_TENANT,
    NodeAnnouncement,
)
from ..errors import RES_NODE_NOT_FOUND, VAL_SCHEMA, InvError
from ..identity.tokens import IssuedToken, issue_bootstrap_token
from ..ids import new_id


class CandidateFlood(InvError):
    """Too many candidates. Announcing is unauthenticated, so it is capped."""

    def __init__(self, count: int) -> None:
        super().__init__(
            VAL_SCHEMA,
            f"the candidate list is full ({count}); admit or decline before accepting more",
        )


@dataclass(frozen=True, slots=True)
class Announcement:
    """What an agent said about itself. None of it is verified."""

    instance_id: str
    hostname: str
    os_type: str
    os_version: str
    agent_version: str
    cpu_cores: int = 0
    ram_bytes: int = 0
    gpu_count: int = 0
    labels: dict[str, str] | None = None

    def validate(self) -> None:
        if not self.instance_id or len(self.instance_id) > 128:
            raise InvError(VAL_SCHEMA, "instance_id must be 1..128 characters")
        if not self.hostname or len(self.hostname) > 253:
            raise InvError(VAL_SCHEMA, "hostname must be 1..253 characters")
        if self.os_type not in ("windows", "linux"):
            raise InvError(VAL_SCHEMA, f"unsupported os_type: {self.os_type!r}")
        for name, value in (
            ("cpu_cores", self.cpu_cores),
            ("ram_bytes", self.ram_bytes),
            ("gpu_count", self.gpu_count),
        ):
            if value < 0:
                raise InvError(VAL_SCHEMA, f"{name} must not be negative")


def record_announcement(
    session: Session,
    *,
    tenant_id: uuid.UUID,
    source_ip: str,
    announcement: Announcement,
    now: dt.datetime,
) -> NodeAnnouncement:
    """Record or refresh a candidate.

    Upserts on ``(tenant, instance_id, source_ip)`` so an agent that restarts
    every minute stays one row rather than becoming a thousand. ``source_ip``
    comes from the connection, never from the body — a field the announcer
    controls cannot be part of its own identity.

    An already-admitted or declined announcement is refreshed but not revived:
    re-announcing does not undo a person's decision.
    """
    announcement.validate()

    existing = session.scalar(
        select(NodeAnnouncement).where(
            NodeAnnouncement.tenant_id == tenant_id,
            NodeAnnouncement.instance_id == announcement.instance_id,
            NodeAnnouncement.source_ip == source_ip,
        )
    )
    if existing is None:
        open_candidates = session.scalar(
            select(func.count())
            .select_from(NodeAnnouncement)
            .where(
                NodeAnnouncement.tenant_id == tenant_id,
                NodeAnnouncement.state == "candidate",
            )
        )
        if open_candidates >= MAX_CANDIDATES_PER_TENANT:
            raise CandidateFlood(open_candidates)

    # populate_existing: without it the ORM hands back the object already in the
    # identity map and the values the database just computed in the ON CONFLICT
    # SET — announce_count above all — are invisible to the caller.
    row = session.execute(
        pg_insert(NodeAnnouncement)
        .values(
            announcement_id=new_id("announcement"),
            tenant_id=tenant_id,
            state="candidate",
            instance_id=announcement.instance_id,
            source_ip=source_ip,
            claimed_hostname=announcement.hostname,
            claimed_os_type=announcement.os_type,
            claimed_os_version=announcement.os_version,
            claimed_agent_version=announcement.agent_version,
            claimed_cpu_cores=announcement.cpu_cores,
            claimed_ram_bytes=announcement.ram_bytes,
            claimed_gpu_count=announcement.gpu_count,
            claimed_labels=announcement.labels or {},
            first_seen_at=now,
            last_seen_at=now,
            announce_count=1,
        )
        .on_conflict_do_update(
            index_elements=["tenant_id", "instance_id", "source_ip"],
            set_={
                "last_seen_at": now,
                "announce_count": NodeAnnouncement.announce_count + 1,
                "claimed_hostname": announcement.hostname,
                "claimed_os_version": announcement.os_version,
                "claimed_agent_version": announcement.agent_version,
                "claimed_cpu_cores": announcement.cpu_cores,
                "claimed_ram_bytes": announcement.ram_bytes,
                "claimed_gpu_count": announcement.gpu_count,
                "claimed_labels": announcement.labels or {},
                # state is deliberately absent: re-announcing does not revive a
                # declined candidate or re-open an admitted one.
            },
        )
        .returning(NodeAnnouncement),
        execution_options={"populate_existing": True},
    ).scalar_one()
    session.flush()
    return row


def list_candidates(
    session: Session,
    *,
    tenant_id: uuid.UUID,
    now: dt.datetime,
    include_stale: bool = False,
    ttl_seconds: int = ANNOUNCEMENT_TTL_SECONDS,
) -> list[dict[str, Any]]:
    """Candidates a person can choose from.

    Stale ones are excluded by default. A machine that stopped announcing five
    minutes ago should not sit in the list looking available — offering it for
    selection would produce an admission that cannot complete.
    """
    cutoff = now - dt.timedelta(seconds=ttl_seconds)
    query = select(NodeAnnouncement).where(
        NodeAnnouncement.tenant_id == tenant_id,
        NodeAnnouncement.state == "candidate",
    )
    if not include_stale:
        query = query.where(NodeAnnouncement.last_seen_at >= cutoff)

    rows = session.scalars(query.order_by(NodeAnnouncement.announcement_id)).all()
    return [
        {
            "announcementId": row.announcement_id,
            "instanceId": row.instance_id,
            "sourceIp": str(row.source_ip),
            # Named "claimed" all the way to the API so a UI cannot present a
            # self-reported figure as a measured one.
            "claimedHostname": row.claimed_hostname,
            "claimedOsType": row.claimed_os_type,
            "claimedCpuCores": row.claimed_cpu_cores,
            "claimedRamBytes": row.claimed_ram_bytes,
            "claimedGpuCount": row.claimed_gpu_count,
            "firstSeenAt": row.first_seen_at,
            "lastSeenAt": row.last_seen_at,
            "announceCount": row.announce_count,
            "stale": row.last_seen_at < cutoff,
            "state": row.state,
            "verified": False,
        }
        for row in rows
    ]


def expire_stale_candidates(
    session: Session,
    *,
    tenant_id: uuid.UUID,
    now: dt.datetime,
    ttl_seconds: int = ANNOUNCEMENT_TTL_SECONDS,
) -> int:
    """Mark candidates that stopped announcing as expired."""
    cutoff = now - dt.timedelta(seconds=ttl_seconds)
    result = session.execute(
        update(NodeAnnouncement)
        .where(
            NodeAnnouncement.tenant_id == tenant_id,
            NodeAnnouncement.state == "candidate",
            NodeAnnouncement.last_seen_at < cutoff,
        )
        .values(state="expired", decided_at=now)
    )
    return result.rowcount or 0


def admit_candidate(
    session: Session,
    *,
    tenant_id: uuid.UUID,
    announcement_id: str,
    admitted_by_user_id: str,
    now: dt.datetime,
    ttl_seconds: int = 900,
) -> IssuedToken:
    """A person selects a candidate; the platform mints its enrollment token.

    This does **not** create the node. It issues a one-time bootstrap token
    that the agent then exchanges through the ordinary enrollment endpoint,
    which is where identity, capabilities and the certificate fingerprint are
    established over an authenticated channel.

    Keeping admission and enrollment apart is the point: the person authorises
    a machine to join, and the machine still has to prove what it is.
    """
    row = session.get(NodeAnnouncement, announcement_id)
    if row is None or row.tenant_id != tenant_id:
        raise InvError(RES_NODE_NOT_FOUND, "announcement not found")
    if row.state != "candidate":
        raise InvError(
            VAL_SCHEMA,
            f"only a candidate can be admitted, not one that is {row.state}",
            cause_ref=announcement_id,
        )

    issued = issue_bootstrap_token(
        session,
        tenant_id=tenant_id,
        issued_by_user_id=admitted_by_user_id,
        now=now,
        ttl_seconds=ttl_seconds,
    )
    # The announcement stays a candidate until enrolment actually completes —
    # see complete_admission. A token that is never redeemed must not leave a
    # record claiming the machine joined.
    row.admitted_by_user_id = admitted_by_user_id
    session.flush()
    return issued


def complete_admission(
    session: Session,
    *,
    tenant_id: uuid.UUID,
    announcement_id: str,
    node_id: str,
    now: dt.datetime,
) -> NodeAnnouncement:
    """Close the loop once enrolment produced a node."""
    row = session.get(NodeAnnouncement, announcement_id)
    if row is None or row.tenant_id != tenant_id:
        raise InvError(RES_NODE_NOT_FOUND, "announcement not found")
    row.state = "admitted"
    row.admitted_node_id = node_id
    row.decided_at = now
    session.flush()
    return row


def decline_candidate(
    session: Session,
    *,
    tenant_id: uuid.UUID,
    announcement_id: str,
    now: dt.datetime,
    reason: str | None = None,
) -> NodeAnnouncement:
    """Refuse a candidate. Re-announcing will not undo this."""
    row = session.get(NodeAnnouncement, announcement_id)
    if row is None or row.tenant_id != tenant_id:
        raise InvError(RES_NODE_NOT_FOUND, "announcement not found")
    if row.state == "admitted":
        raise InvError(VAL_SCHEMA, "an admitted machine cannot be declined; retire the node")
    row.state = "declined"
    row.decided_at = now
    row.decline_reason = reason
    session.flush()
    return row
