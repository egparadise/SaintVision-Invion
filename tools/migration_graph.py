"""Read the migration chain without importing or running it.

CI used to prove migrations were sound by running ``upgrade head`` then
``downgrade base``. That assumed every revision is reversible, and some are
deliberately not: PLAN-DB-001 says an irreversible migration must state a
verified restore and forward-fix plan **instead of** forcing a downgrade, and
``0006_control_api`` does exactly that — its ``downgrade()`` raises rather than
unpicking an event ordering that cannot be safely reversed.

So the round trip was testing the wrong property. What matters is:

* the chain is linear and has one head — two heads mean nobody knows what
  ``head`` refers to;
* a fresh database reaches head;
* the **reversible tail** really does reverse, because that is the part an
  operator might actually roll back.

Irreversibility is detected from the source rather than by running the
downgrade and catching the exception. A property discovered by triggering it is
one you find out about during an incident.

Usage:
    python tools/migration_graph.py            # print the chain
    python tools/migration_graph.py --downgrade-target
"""

from __future__ import annotations

import argparse
import ast
import re
from dataclasses import dataclass
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
VERSIONS = ROOT / "migrations" / "versions"


@dataclass(frozen=True, slots=True)
class Revision:
    revision: str
    down_revision: str | None
    path: Path
    irreversible: bool
    #: What the revision says to do instead of downgrading, if anything.
    recovery_note: str | None

    @property
    def name(self) -> str:
        return self.path.name


def _downgrade_is_refusal(tree: ast.Module) -> tuple[bool, str | None]:
    """Whether ``downgrade()`` does nothing but refuse, and what it says."""
    for node in tree.body:
        if not isinstance(node, ast.FunctionDef) or node.name != "downgrade":
            continue
        body = [n for n in node.body if not isinstance(n, ast.Expr) or not isinstance(
            getattr(n, "value", None), ast.Constant
        )]
        if len(body) == 1 and isinstance(body[0], ast.Raise):
            message = None
            exc = body[0].exc
            if isinstance(exc, ast.Call) and exc.args:
                first = exc.args[0]
                if isinstance(first, ast.Constant) and isinstance(first.value, str):
                    message = first.value
            return True, message
        return False, None
    # No downgrade at all is also irreversible, and more quietly so.
    return True, None


def load() -> list[Revision]:
    revisions: list[Revision] = []
    for path in sorted(VERSIONS.glob("*.py")):
        source = path.read_text(encoding="utf-8")
        tree = ast.parse(source)
        revision = re.search(r'^revision\s*=\s*"([^"]+)"', source, re.M)
        down = re.search(r'^down_revision\s*=\s*(None|"[^"]+")', source, re.M)
        if not revision or not down:
            raise ValueError(f"{path.name}: revision or down_revision not declared")
        irreversible, message = _downgrade_is_refusal(tree)
        docstring = ast.get_docstring(tree) or ""
        note = message
        if note is None and irreversible:
            for line in docstring.splitlines():
                if re.search(r"restore|forward|irreversible|불가역|복원", line, re.I):
                    note = line.strip()
                    break
        revisions.append(
            Revision(
                revision=revision.group(1),
                down_revision=None if down.group(1) == "None" else down.group(1).strip('"'),
                path=path,
                irreversible=irreversible,
                recovery_note=note,
            )
        )
    return revisions


def chain(revisions: list[Revision] | None = None) -> list[Revision]:
    """Return the revisions in application order, or raise if it is not a chain."""
    revisions = revisions or load()
    by_revision = {r.revision: r for r in revisions}
    if len(by_revision) != len(revisions):
        raise ValueError("duplicate revision identifiers")

    roots = [r for r in revisions if r.down_revision is None]
    if len(roots) != 1:
        raise ValueError(f"expected exactly one root revision, found {len(roots)}")

    children: dict[str | None, list[Revision]] = {}
    for r in revisions:
        children.setdefault(r.down_revision, []).append(r)
    forks = {parent: [c.revision for c in kids] for parent, kids in children.items() if len(kids) > 1}
    if forks:
        # Two heads mean "head" is ambiguous, and an upgrade picks one at random.
        raise ValueError(f"the chain forks: {forks}")

    ordered: list[Revision] = []
    current: str | None = None
    while True:
        kids = children.get(current)
        if not kids:
            break
        node = kids[0]
        ordered.append(node)
        current = node.revision
    if len(ordered) != len(revisions):
        missing = {r.revision for r in revisions} - {r.revision for r in ordered}
        raise ValueError(f"revisions not reachable from the root: {sorted(missing)}")
    return ordered


def downgrade_target(revisions: list[Revision] | None = None) -> str:
    """How far a rollback test may safely go.

    Returns the revision an operator could roll back *to* — the newest
    irreversible one — or ``base`` when every revision reverses. Downgrading
    past an irreversible revision is not a test failure to fix; it is a thing
    the plan says not to do.
    """
    ordered = chain(revisions)
    last_irreversible = None
    for revision in ordered:
        if revision.irreversible:
            last_irreversible = revision.revision
    return last_irreversible or "base"


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--downgrade-target", action="store_true")
    parser.add_argument("--head", action="store_true")
    args = parser.parse_args()

    ordered = chain()
    if args.head:
        print(ordered[-1].revision)
        return 0
    if args.downgrade_target:
        print(downgrade_target(ordered))
        return 0

    for revision in ordered:
        mark = "irreversible" if revision.irreversible else "reversible"
        note = f" — {revision.recovery_note}" if revision.recovery_note else ""
        print(f"{revision.revision:32} {mark:12} {revision.name}{note}")
    print()
    print(f"head: {ordered[-1].revision}")
    print(f"safe downgrade target: {downgrade_target(ordered)}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
