"""The one place the business surface touches the execution core.

Every call into ``inv`` goes through here. Not for tidiness — because there are
exactly three things that have to be translated at this boundary, and each of
them is a way to be silently wrong if it happens in more than one place:

**Identity flows one way.** ``public`` is authoritative for tenants, projects,
runs and nodes. The core needs rows for them because its own foreign keys
demand them, so this module projects them across, using **the same identifiers**
— a Run is ``run_`` plus the same ULID on both sides. It never reads a fact back
out of ``inv`` and treats it as authoritative. Where a value exists on both
sides, ``public`` wrote it.

**Resource observation flows the other way, and is not projected.** ``inv``
owns ``resources``: what a node actually has, as its own probes measured it.
This module resolves the core's resource ids and refuses when the core has
never seen a node, rather than inventing a row to make a reservation succeed.
Two writers for one table is how a pool reports capacity nobody has.

**The two halves name resource kinds differently.** ``public`` says ``ram`` and
``disk``; ``inv`` says ``memory`` and ``storage``. That translation is here, in
one dictionary, and nowhere else. A translation table that appears twice is one
that will eventually disagree with itself.

**On the transaction.** ``inv.db.BoundDatabase`` exists for "nested service
operations share one outer transaction", and that is exactly this situation:
since revision 0022 both schemas are reachable by ``inv_app``, and both halves
scope by ``SET LOCAL inv.tenant_id``. So the reservation and the binding update
commit together or not at all. Without that, a reservation could succeed while
the record of why it was made rolled back, leaving capacity held for a decision
nobody can find.

What this module deliberately does **not** do is reimplement anything. The lock
ordering, the fencing tokens, the ceiling arithmetic and the idempotency ledger
are the core's, and they are correct there.
"""

from __future__ import annotations

import datetime as dt
import uuid
from typing import Any, Final

from sqlalchemy.orm import Session

from ..errors import RES_NODE_NOT_FOUND, VAL_SCHEMA, InvError

#: ``public`` kind to ``inv`` kind. The vocabularies diverged before either
#: half knew about the other; ``public`` is authoritative for the concept and
#: this is the cost of that being true only in principle so far. When the core
#: adopts these names the mapping becomes the identity and this table goes away.
KIND_TO_CORE: Final[dict[str, str]] = {
    "cpu": "cpu",
    "ram": "memory",
    "disk": "storage",
    "gpu": "gpu",
}

#: The states a Run may hold a reservation in (``inv.leases._reserve_locked``).
RESERVABLE_STATES: Final[frozenset[str]] = frozenset({"planned", "scheduled", "running"})

#: Getting a freshly inserted core Run to a state that may reserve. Each step is
#: a legal edge of ``inv.guard_run`` and bumps the version by exactly one.
_TO_PLANNED: Final[tuple[str, ...]] = ("validated", "planned")


class _DictRows:
    """Give the core's services the row shape they expect, on our connection.

    The core reads ``row["state"]``; SQLAlchemy hands back tuples. Rather than
    changing the connection's row factory — which would alter how SQLAlchemy
    reads its own results for the rest of the transaction — each statement gets
    a cursor configured the way the core needs.
    """

    def __init__(self, raw: Any) -> None:
        self._raw = raw

    def execute(self, statement: str, params: Any = None):
        from psycopg.rows import dict_row

        return self._raw.cursor(row_factory=dict_row).execute(statement, params)


class _EpochOnly:
    """The one attribute ``BoundDatabase`` reads from a database object."""

    def __init__(self, recovery_epoch: str) -> None:
        self.recovery_epoch = str(uuid.UUID(recovery_epoch))


def bound_core(session: Session, *, tenant_id: uuid.UUID, recovery_epoch: str):
    """A core database handle that shares this session's transaction.

    The epoch passed in is the one the binding recorded, not the one currently
    in force. That is deliberate and is the whole point of recording it: the
    core stamps leases with this value and matches nodes against it, so a
    binding prepared under an older epoch cannot quietly reserve under the
    current one — it finds no ready node and fails.
    """
    from inv.db import BoundDatabase

    raw = session.connection().connection.driver_connection
    # The core's own Database.transaction sets these; BoundDatabase does not,
    # because it assumes the outer transaction already has them. Ours would not.
    # A capacity writer that waits indefinitely on a row lock is worse than one
    # that gives up and is retried with the same idempotency key.
    conn = _DictRows(raw)
    conn.execute("SET LOCAL lock_timeout = '500ms'")
    conn.execute("SET LOCAL statement_timeout = '2s'")
    return BoundDatabase(_EpochOnly(recovery_epoch), str(tenant_id), conn)


# --------------------------------------------------------------------------
# Identity: public -> inv, never the reverse
# --------------------------------------------------------------------------


def project_identity(
    session: Session,
    *,
    tenant_id: uuid.UUID,
    tenant_name: str,
    project_id: str,
    run_id: str,
) -> int:
    """Give the core the tenant, project and Run it needs, with our identifiers.

    Idempotent by ``ON CONFLICT DO NOTHING``: projecting twice is what a retry
    looks like, and a second projection must not disturb a Run the core has
    already advanced.

    Returns the core Run's version, which is what an approval binds to. Reading
    it back rather than assuming it is 1 matters: if the Run was projected
    earlier and has since moved, the caller must bind to where it actually is.
    """
    conn = _DictRows(session.connection().connection.driver_connection)
    conn.execute(
        "INSERT INTO inv.tenants (tenant_id, name) VALUES (%s, %s) "
        "ON CONFLICT (tenant_id) DO NOTHING",
        (str(tenant_id), tenant_name),
    )
    conn.execute(
        "INSERT INTO inv.projects (tenant_id, project_id) VALUES (%s, %s) "
        "ON CONFLICT (tenant_id, project_id) DO NOTHING",
        (str(tenant_id), project_id),
    )
    conn.execute(
        "INSERT INTO inv.runs (tenant_id, project_id, run_id) VALUES (%s, %s, %s) "
        "ON CONFLICT (tenant_id, run_id) DO NOTHING",
        (str(tenant_id), project_id, run_id),
    )
    row = conn.execute(
        "SELECT state, version FROM inv.runs WHERE tenant_id = %s AND run_id = %s",
        (str(tenant_id), run_id),
    ).fetchone()
    if row is None:  # pragma: no cover - the insert above guarantees it
        raise InvError(VAL_SCHEMA, "the core did not accept the projected run")
    return _advance_to_reservable(conn, tenant_id, run_id, row)


def _advance_to_reservable(conn: _DictRows, tenant_id: uuid.UUID, run_id: str, row) -> int:
    """Walk a freshly projected Run to ``planned``, one legal edge at a time.

    ``inv.guard_run`` refuses a jump: every transition moves exactly one edge
    and bumps the version by exactly one. Writing ``state='planned'`` directly
    from ``draft`` fails, and it should — the guard is what stops a Run
    appearing to have been validated when nothing validated it.
    """
    state, version = row["state"], row["version"]
    if state in RESERVABLE_STATES:
        return version
    if state != "draft":
        raise InvError(
            VAL_SCHEMA,
            "the core Run is not in a state that can be prepared for reservation",
            extra={"runId": run_id, "state": state},
        )
    for target in _TO_PLANNED:
        version += 1
        conn.execute(
            "UPDATE inv.runs SET state = %s, version = %s "
            "WHERE tenant_id = %s AND run_id = %s",
            (target, version, str(tenant_id), run_id),
        )
    return version


def project_grant(
    session: Session, *, tenant_id: uuid.UUID, project_id: str, user_id: str
) -> None:
    """Make the core's grant agree with ``public.project_members``.

    ``inv.approval_requests.requester_id`` has a foreign key to
    ``inv.project_grants``, so an approval cannot exist without a row here.
    That makes this projection load-bearing: without it the core's approval path
    is unreachable from the business surface, whatever ``public`` says.

    The application cannot write that table — it holds ``UPDATE(lock_sentinel)``
    and nothing more, so it can prove membership did not change under it and can
    never change it. That is the right permission and this does not widen it.
    The projection goes through a SECURITY DEFINER function that reads
    ``public.project_members`` and decides the permissions itself, so the caller
    chooses *whose* membership to project and never *what* it grants. An
    application that has been taken over can use this only to make the core
    agree with a table it also cannot write. See migration 0025.

    Called on every pass rather than only on insert: a revoked membership has to
    become a revoked grant, and a projection that only ever adds is a permission
    system that only ever grows.
    """
    conn = _DictRows(session.connection().connection.driver_connection)
    conn.execute(
        "SELECT inv.project_grants_from_members(%s, CAST(%s AS char(30)), "
        "CAST(%s AS char(30)))",
        (str(tenant_id), project_id, user_id),
    )


def project_node(
    session: Session,
    *,
    tenant_id: uuid.UUID,
    node_id: str,
    recovery_epoch: str,
    now: dt.datetime,
    clock_skew_seconds: float = 0.0,
) -> None:
    """Give the core the node identity it needs for a resource to reference.

    Only identity and liveness. What the node *has* is the core's own
    observation and is not written here — see the module docstring.
    """
    conn = _DictRows(session.connection().connection.driver_connection)
    conn.execute(
        "INSERT INTO inv.nodes "
        "(tenant_id, node_id, status, heartbeat_at, recovery_epoch, clock_skew_seconds) "
        "VALUES (%s, %s, 'online', %s, %s, %s) "
        "ON CONFLICT (tenant_id, node_id) DO UPDATE SET "
        "status = 'online', heartbeat_at = excluded.heartbeat_at, "
        "recovery_epoch = excluded.recovery_epoch, "
        "clock_skew_seconds = excluded.clock_skew_seconds",
        (str(tenant_id), node_id, now, recovery_epoch, clock_skew_seconds),
    )


# --------------------------------------------------------------------------
# Resources: resolved, never invented
# --------------------------------------------------------------------------


def resolve_resource(
    session: Session, *, tenant_id: uuid.UUID, node_id: str, kind: str
) -> str:
    """The core's resource id for one kind on one node.

    Refuses rather than creating one. ``inv.resources`` records what the core's
    own probes measured; a row written here to make a reservation succeed would
    be a reservation against capacity nobody observed, which is the failure the
    whole placement design exists to avoid.
    """
    core_kind = KIND_TO_CORE.get(kind)
    if core_kind is None:
        raise InvError(VAL_SCHEMA, f"unknown resource kind: {kind!r}")
    conn = _DictRows(session.connection().connection.driver_connection)
    row = conn.execute(
        "SELECT resource_id FROM inv.resources "
        "WHERE tenant_id = %s AND node_id = %s AND kind = %s "
        "ORDER BY resource_id LIMIT 1",
        (str(tenant_id), node_id, core_kind),
    ).fetchone()
    if row is None:
        raise InvError(
            RES_NODE_NOT_FOUND,
            "the execution core has not observed this resource on this node",
            extra={"nodeId": node_id, "kind": kind, "coreKind": core_kind},
        )
    return row["resource_id"]


def reserve(
    session: Session,
    *,
    tenant_id: uuid.UUID,
    project_id: str,
    run_id: str,
    recovery_epoch: str,
    allocations: list[tuple[str, str, int]],
    idempotency_key: str,
    ttl_seconds: int = 30,
) -> list[dict[str, Any]]:
    """Step 5. Reserve capacity through the core, in this transaction.

    ``allocations`` are ``(node_id, public kind, amount)`` in the canonical
    units — millicores, bytes, devices. The core's own ceiling table is
    ``cpu_millis`` and ``memory_bytes``, so the units already agree; that
    agreement is why the canonical CPU unit is millicores rather than cores.

    Nothing about locks, fencing or ceilings happens here. The core does all of
    it, in the order it documents, on our connection.
    """
    from inv.errors import DomainError
    from inv.leases import Allocation, LeaseStore

    if not allocations:
        raise InvError(VAL_SCHEMA, "a reservation needs at least one allocation")

    resolved = [
        Allocation(
            resource_id=resolve_resource(
                session, tenant_id=tenant_id, node_id=node_id, kind=kind
            ),
            amount=int(amount),
        )
        for node_id, kind, amount in allocations
    ]
    store = LeaseStore(
        bound_core(session, tenant_id=tenant_id, recovery_epoch=recovery_epoch)
    )
    try:
        return store.reserve(
            str(tenant_id),
            project_id,
            run_id,
            resolved,
            key=idempotency_key,
            ttl_seconds=ttl_seconds,
        )
    except DomainError as error:
        # Translated rather than leaked. The core's codes are its contract with
        # its own callers; a business-surface client should not have to learn a
        # second error vocabulary to find out its reservation was refused.
        raise InvError(
            VAL_SCHEMA,
            f"the execution core refused the reservation: {error.args[1] if len(error.args) > 1 else error}",
            extra={"coreCode": error.args[0] if error.args else None},
        ) from error


def reserve_for_binding(
    session: Session,
    *,
    tenant_id: uuid.UUID,
    binding,
    allocations: list[tuple[str, str, int]],
    now: dt.datetime,
    ttl_seconds: int = 30,
) -> list[dict[str, Any]]:
    """Reserve for an approved binding, and record that it is queued.

    The binding's epoch is passed to the core. If it moved, the core finds no
    node ready under that epoch and refuses — which is the recorded epoch doing
    the job it was recorded for, one layer deeper than the check in
    ``handoff.assert_binding_is_current``.

    The idempotency key is derived from the binding rather than supplied. A
    caller-chosen key would let two different bindings share one, and the
    binding id is already unique per (run, epoch, version) — exactly the scope a
    reservation should be idempotent over.
    """
    from . import handoff as handoff_service

    if binding.state != "approved":
        raise InvError(
            VAL_SCHEMA,
            "only an approved binding may reserve resources",
            extra={"state": binding.state},
        )
    leases = reserve(
        session,
        tenant_id=tenant_id,
        project_id=binding.project_id,
        run_id=binding.run_id,
        recovery_epoch=str(binding.recovery_epoch),
        allocations=allocations,
        idempotency_key=f"binding:{binding.binding_id}",
        ttl_seconds=ttl_seconds,
    )
    handoff_service.advance(
        session,
        tenant_id=tenant_id,
        binding_id=binding.binding_id,
        to="queued",
        now=now,
        note=f"{len(leases)} lease(s)",
    )
    return leases
