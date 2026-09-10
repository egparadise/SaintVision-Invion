"""Read the migration chain without importing or running it.

CI used to prove migrations were sound by running ``upgrade head`` then
``downgrade base``. That assumed every revision is reversible, and some are
deliberately not: PLAN-DB-001 says an irreversible migration must state a
verified restore and forward-fix plan **instead of** forcing a downgrade, and
``0006_control_api`` does exactly that — its ``downgrade()`` raises rather than
unpicking an event ordering that cannot be safely reversed.

So the round trip was testing the wrong property. What matters is:

* the graph is acyclic and has one integrated head — two heads mean nobody knows what
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
    down_revision: str | tuple[str, ...] | None
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
        body = [
            n
            for n in node.body
            if not isinstance(n, ast.Expr)
            or not isinstance(getattr(n, "value", None), ast.Constant)
        ]
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
        assignments = {}
        for node in tree.body:
            if isinstance(node, ast.Assign):
                for target in node.targets:
                    if isinstance(target, ast.Name) and target.id in {"revision", "down_revision"}:
                        assignments[target.id] = ast.literal_eval(node.value)
        if set(assignments) != {"revision", "down_revision"}:
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
                revision=assignments["revision"],
                down_revision=assignments["down_revision"],
                path=path,
                irreversible=irreversible,
                recovery_note=note,
            )
        )
    return revisions


def chain(revisions: list[Revision] | None = None) -> list[Revision]:
    """Return a deterministic topological order with one fully integrated head."""
    revisions = revisions or load()
    by_revision = {r.revision: r for r in revisions}
    if len(by_revision) != len(revisions):
        raise ValueError("duplicate revision identifiers")

    parents = {
        r.revision: (
            ()
            if r.down_revision is None
            else (r.down_revision,) if isinstance(r.down_revision, str) else r.down_revision
        )
        for r in revisions
    }
    if any(not isinstance(p, tuple) or len(set(p)) != len(p) for p in parents.values()):
        raise ValueError("invalid revision parents")
    if len([p for p in parents.values() if not p]) != 1:
        raise ValueError("expected exactly one root revision")
    referenced = {p for ps in parents.values() for p in ps}
    if referenced - by_revision.keys():
        raise ValueError("unknown revision parent")
    heads = by_revision.keys() - referenced
    if len(heads) != 1:
        raise ValueError("unmerged migration branches: expected exactly one head")
    ordered, visiting, visited = [], set(), set()

    def visit(name):
        if name in visiting:
            raise ValueError("migration cycle")
        if name in visited:
            return
        visiting.add(name)
        for parent in sorted(parents[name]):
            visit(parent)
        visiting.remove(name)
        visited.add(name)
        ordered.append(by_revision[name])

    visit(next(iter(heads)))
    if len(visited) != len(revisions):
        raise ValueError("unreachable revisions")
    return ordered


def downgrade_target(revisions: list[Revision] | None = None) -> str:
    """How far a rollback test may safely go.

    Returns the revision an operator could roll back *to* — the newest
    irreversible one — or ``base`` when every revision reverses. Downgrading
    past an irreversible revision is not a test failure to fix; it is a thing
    the plan says not to do.
    """
    ordered = chain(revisions)
    # Crossing a merge requires branch-aware rollback, so stop at the merge itself.
    last_irreversible = None
    for revision in ordered:
        if revision.irreversible or isinstance(revision.down_revision, tuple):
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
