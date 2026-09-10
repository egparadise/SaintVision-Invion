"""One unit per resource kind, and the conversion into it.

The platform's whole purpose is to add up the CPU, RAM, GPU and disk that
several machines offer and place work on whichever is idlest. Every one of
those steps is a subtraction or a comparison between two numbers that came from
different machines — ``offered - used``, ``spare >= required``. Those
operations are only meaningful if both numbers are in the same unit, and until
now nothing said they were.

``unit`` was a free-text ``varchar(16)`` written three times: on the capability,
on the offer, and on every observation. A node could declare 32 "GiB" of RAM
and report 4096 "MB" used, and ``node_spare`` would compute ``32 - 4096``,
clamp it at zero, and conclude the machine was full. Report it the other way
around and the machine looks completely idle and wins every placement. Nothing
rejected either reading, because nothing compared the two strings.

So the unit stops being data the node supplies and becomes a property of the
kind:

=========  ==============  ====================================================
kind       canonical unit  why
=========  ==============  ====================================================
``cpu``    ``millicores``  Integer. A quarter of a core is 250, not 0.25, so
                           summing offers across a pool cannot drift.
``ram``    ``bytes``       The only unit with no ambiguity. "GB" is 10^9 to a
                           disk vendor and 2^30 to an operating system.
``disk``   ``bytes``       Same.
``gpu``    ``devices``     A GPU is not divisible in this pilot, so the only
                           honest unit is whole devices.
=========  ==============  ====================================================

Nodes still *report* in whatever they measured — an agent that reads GiB should
not have to do arithmetic to be correct. :func:`to_canonical` converts at the
edge and refuses anything it does not recognise. Refusing is the point: a unit
it cannot convert is a number it cannot compare, and guessing at that boundary
is how the wrong machine gets the work.

**On the seam with the execution core.** ``inv.resources`` stores ``capacity``
and ``offered`` as bare ``bigint`` with no unit column at all, and
``inv.resource_leases.amount`` likewise. Bigints are exactly right for
millicores, bytes and devices, and exactly wrong for fractional cores — which
is the reason the canonical CPU unit here is millicores rather than cores. The
two halves can hold the same integers as long as they agree what the integers
count, and this table is that agreement.
"""

from __future__ import annotations

from typing import Final

from .errors import VAL_SCHEMA, InvError

#: The unit every stored quantity of each kind is in.
CANONICAL_UNIT: Final[dict[str, str]] = {
    "cpu": "millicores",
    "ram": "bytes",
    "disk": "bytes",
    "gpu": "devices",
}

KINDS: Final[tuple[str, ...]] = tuple(CANONICAL_UNIT)

#: Units accepted on the wire, and what one of them is worth in the canonical
#: unit for that kind. Multipliers are exact integers so conversion never
#: introduces a fraction that later rounds the wrong way.
#:
#: Binary and decimal prefixes are both here and they are *not* the same: "GB"
#: is 10^9 and "GiB" is 2^30, a 7% difference that would otherwise show up as a
#: node mysteriously being unable to hold a shard that fits.
_ACCEPTED: Final[dict[str, dict[str, int]]] = {
    "cpu": {
        "millicores": 1,
        "mcores": 1,
        "millicore": 1,
        "cores": 1000,
        "core": 1000,
        "cpus": 1000,
        "vcpu": 1000,
        "vcpus": 1000,
    },
    "ram": {
        "bytes": 1,
        "byte": 1,
        "b": 1,
        "kb": 1000,
        "mb": 1000**2,
        "gb": 1000**3,
        "tb": 1000**4,
        "kib": 1024,
        "mib": 1024**2,
        "gib": 1024**3,
        "tib": 1024**4,
    },
    "gpu": {
        "devices": 1,
        "device": 1,
        "gpus": 1,
        "gpu": 1,
        "count": 1,
    },
}
# Disk is measured the same way memory is; sharing the table keeps one place to
# add a prefix rather than two that can fall out of step.
_ACCEPTED["disk"] = _ACCEPTED["ram"]


def canonical_unit(kind: str) -> str:
    """The unit quantities of ``kind`` are stored in."""
    try:
        return CANONICAL_UNIT[kind]
    except KeyError:
        raise InvError(VAL_SCHEMA, f"unknown resource kind: {kind!r}") from None


def to_canonical(kind: str, quantity: float, unit: str) -> int:
    """Convert a reported quantity into the canonical unit for its kind.

    Returns an integer, because every canonical unit counts indivisible things:
    a millicore, a byte, a device. A conversion that produced 3.7 bytes would be
    a sign the caller meant something else.

    Raises rather than guessing when the unit is not recognised for this kind.
    A ``varchar`` the platform cannot interpret is not a smaller problem than a
    missing one — it is the same problem, arriving later and looking like data.
    """
    accepted = _ACCEPTED.get(kind)
    if accepted is None:
        raise InvError(VAL_SCHEMA, f"unknown resource kind: {kind!r}")
    if quantity < 0:
        raise InvError(VAL_SCHEMA, "quantity must not be negative")

    key = (unit or "").strip().lower()
    multiplier = accepted.get(key)
    if multiplier is None:
        raise InvError(
            VAL_SCHEMA,
            f"unit {unit!r} is not a recognised unit for {kind!r}; "
            f"expected one of {', '.join(sorted(accepted))}",
            extra={"kind": kind, "unit": unit, "canonicalUnit": canonical_unit(kind)},
        )

    scaled = quantity * multiplier
    rounded = round(scaled)
    # A GiB figure with a fractional tail is a real quantity; a fractional
    # *canonical* value means the caller's number was finer than the unit can
    # express, and silently truncating it is how a 1.5-core offer becomes 1.
    if abs(scaled - rounded) > 1e-6:
        raise InvError(
            VAL_SCHEMA,
            f"{quantity} {unit} is {scaled} {canonical_unit(kind)}, which is not a "
            f"whole {canonical_unit(kind)[:-1]}",
            extra={"kind": kind, "unit": unit},
        )
    return int(rounded)


def format_quantity(kind: str, quantity: int) -> dict[str, object]:
    """A quantity together with the unit it is in.

    Every API response that carries a resource number carries this shape rather
    than a bare integer. A consumer that has to infer the unit from the field
    name is a consumer that will eventually infer it wrong.
    """
    return {"value": int(quantity), "unit": canonical_unit(kind)}
