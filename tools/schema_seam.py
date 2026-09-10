"""Report the seam between the two halves of the control plane.

The integration merge brought together two implementations that had been built
in parallel, and they overlap. This tool states the overlap as fact rather than
impression, because "connect the business API to the execution core" cannot be
done sensibly until someone decides what happens where the two already do the
same job.

It reports three things:

**Duplicated concepts.** Eleven entities exist in both schemas — including
``runs``, ``evidence``, ``approvals``, ``outbox`` and ``idempotency``. Two
tables for one concept means two answers to "what state is this run in", and a
bridge between them would make that permanent rather than resolving it.

**Complementary concepts.** Most tables exist on exactly one side, and those
compose cleanly: the execution core owns leases, fencing, channels and
dispatch; the business surface owns context, evaluation, lineage, pools,
locality and pilot operations.

**The grant gap.** The ``public`` schema grants a named application role in its
migrations. The ``inv`` schema grants nothing in its migrations — access is
conferred by the integration test fixture to a per-test role it creates. That
works in tests and leaves a deployment with no access path, which is the kind
of gap that passes CI and fails on the day it is installed.

Usage:
    python tools/schema_seam.py
    python tools/schema_seam.py --json
"""

from __future__ import annotations

import argparse
import json
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
INV_SQL = ROOT / "services" / "control-plane" / "src" / "inv" / "migrations"
PY_VERSIONS = ROOT / "migrations" / "versions"

#: Names for the same concept on each side. Left is the `public` table, right
#: is the `inv` one. Recorded explicitly because the duplication is not
#: detectable from the names alone.
SYNONYMS: dict[str, str] = {
    "evidence_envelopes": "evidence",
    "outbox_events": "outbox",
    "inbox_events": "consumer_inbox",
    "idempotency_records": "idempotency",
    "approvals": "approval_requests",
}


def inv_tables() -> set[str]:
    tables: set[str] = set()
    for path in sorted(INV_SQL.glob("*.sql")):
        text = path.read_text(encoding="utf-8")
        tables |= set(
            re.findall(r"CREATE TABLE (?:IF NOT EXISTS )?inv\.([a-z_]+)", text)
        )
    return tables


def inv_grants() -> set[str]:
    """Roles the inv migrations grant to. Empty is the finding, not an error."""
    roles: set[str] = set()
    for path in sorted(INV_SQL.glob("*.sql")):
        text = path.read_text(encoding="utf-8")
        roles |= set(re.findall(r"GRANT [^;]*? TO ([a-zA-Z_][a-zA-Z0-9_]*)", text))
    return roles


def public_tables() -> set[str]:
    sys.path.insert(0, str(ROOT / "src"))
    from saintvision.db.models import TENANT_SCOPED_TABLES

    return set(TENANT_SCOPED_TABLES) | {"tenants"}


def resource_vocabulary() -> dict:
    """How each side names and measures a resource.

    Not a duplicated *table* — ``public.node_capabilities`` and
    ``inv.resources`` are different shapes — but the same *quantity*, and the
    execution core leases against it. Two things have to agree before a lease
    can be checked against an offer:

    **The kinds.** ``public`` says ``ram`` and ``disk``; ``inv`` says ``memory``
    and ``storage`` and adds ``network``, which has no counterpart at all. A
    lease for 'memory' cannot be matched to an offer of 'ram' by string
    comparison, and matching it by a translation table nobody wrote is worse.

    **The units.** ``public`` now stores one canonical unit per kind and
    constrains it (migration 0010). ``inv.resources.capacity`` and
    ``inv.resource_leases.amount`` are bare ``bigint`` with no unit column
    anywhere — the unit is whatever the writer meant. Bigint is the right type
    for millicores, bytes and devices; what is missing is the statement that
    those are what the integers count.
    """
    sys.path.insert(0, str(ROOT / "src"))
    from saintvision.units import CANONICAL_UNIT

    inv_kinds = set()
    for path in sorted(INV_SQL.glob("*.sql")):
        text = path.read_text(encoding="utf-8")
        for match in re.finditer(r"kind text NOT NULL CHECK \(kind IN \(([^)]+)\)\)", text):
            inv_kinds |= {value.strip().strip("'") for value in match.group(1).split(",")}

    # Left is the public kind, right is what inv calls the same thing.
    equivalents = {"cpu": "cpu", "ram": "memory", "disk": "storage", "gpu": "gpu"}
    return {
        "publicKinds": dict(CANONICAL_UNIT),
        "invKinds": sorted(inv_kinds),
        "renames": {k: v for k, v in equivalents.items() if k != v},
        "onlyInv": sorted(inv_kinds - set(equivalents.values())),
        "invDeclaresUnits": False,
    }


def report() -> dict:
    inv = inv_tables()
    mine = public_tables()
    normalised = {SYNONYMS.get(t, t): t for t in mine}

    duplicated = sorted(
        (
            {"concept": concept, "public": normalised[concept], "inv": concept}
            for concept in set(normalised) & inv
        ),
        key=lambda row: row["concept"],
    )
    only_public = sorted(set(normalised) - inv)
    only_inv = sorted(inv - set(normalised))

    return {
        "duplicated": duplicated,
        "onlyPublic": only_public,
        "onlyInv": only_inv,
        "resources": resource_vocabulary(),
        "invGrantRoles": sorted(inv_grants()),
        "publicGrantRole": "inv_app",
        # An empty inv grant list is the gap: the schema has no access path
        # outside the test fixture that provisions one per test.
        "invHasProductionGrantPath": bool(inv_grants()),
    }


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--json", action="store_true")
    args = parser.parse_args()

    data = report()
    if args.json:
        print(json.dumps(data, indent=2, ensure_ascii=False))
        return 0

    print(f"Duplicated concepts ({len(data['duplicated'])}) — two tables, one meaning:")
    for row in data["duplicated"]:
        print(f"  public.{row['public']:24} <-> inv.{row['inv']}")
    print(f"\nOnly in public ({len(data['onlyPublic'])}): business surface and downstream")
    print("  " + ", ".join(data["onlyPublic"]))
    print(f"\nOnly in inv ({len(data['onlyInv'])}): execution mechanics")
    print("  " + ", ".join(data["onlyInv"]))
    resources = data["resources"]
    print("\nResource vocabulary — the same quantity, named and measured differently:")
    for kind, unit in resources["publicKinds"].items():
        renamed = resources["renames"].get(kind)
        as_inv = f"inv.{renamed}" if renamed else f"inv.{kind}"
        print(f"  public.{kind:5} in {unit:12} <-> {as_inv:14} in (no unit declared)")
    if resources["onlyInv"]:
        print(f"  only in inv: {', '.join(resources['onlyInv'])} — no counterpart in public")
    print(
        "  inv.resources.capacity and inv.resource_leases.amount are bigint with\n"
        "  no unit column. bigint is right for millicores, bytes and devices;\n"
        "  what is missing is the statement that those are what they count."
    )

    print("\nApplication role:")
    print(f"  public: granted to {data['publicGrantRole']} in its migrations")
    if data["invHasProductionGrantPath"]:
        print(f"  inv:    granted to {', '.join(data['invGrantRoles'])}")
    else:
        print("  inv:    NO grant in its migrations — the integration test fixture")
        print("          confers access on a role it creates per test, so a")
        print("          deployment has no access path.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
