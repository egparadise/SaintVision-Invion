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

# An executable downgrade can be treated as an irreversible security boundary
# only after its revision and exact fail-closed operation have been reviewed.
# Keeping the SQL here makes adding ``irreversible = True`` to an arbitrary
# future migration insufficient to erase the reversible AC-11 axis.
REVIEWED_SECURITY_PRESERVING_DOWNGRADES = {
    "0066_tenant_registry_revoke": (
        "REVOKE SELECT ON public.tenants FROM inv_app",
    ),
}


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


def _explicit_irreversible_marker(tree: ast.Module) -> bool:
    for node in tree.body:
        if not isinstance(node, ast.Assign):
            continue
        if any(isinstance(target, ast.Name) and target.id == "irreversible" for target in node.targets):
            try:
                return ast.literal_eval(node.value) is True
            except (ValueError, TypeError):
                return False
    return False


def _normalized_sql(value: str) -> str:
    return " ".join(value.strip().removesuffix(";").split())


def reviewed_security_preserving_downgrade(tree: ast.Module, revision: str) -> bool:
    """Validate the sole reviewed executable irreversible downgrade.

    A marked revision outside the reviewed set, or any statement other than
    the exact reviewed REVOKE call, is invalid rather than irreversible.
    """
    if not _explicit_irreversible_marker(tree):
        return False
    expected = REVIEWED_SECURITY_PRESERVING_DOWNGRADES.get(revision)
    if expected is None:
        raise ValueError(f"{revision}: unreviewed explicit irreversible marker")
    downgrade = next(
        (
            node
            for node in tree.body
            if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef))
            and node.name == "downgrade"
        ),
        None,
    )
    if downgrade is None:
        raise ValueError(f"{revision}: reviewed security downgrade is missing")
    body = list(downgrade.body)
    if body and isinstance(body[0], ast.Expr) and isinstance(body[0].value, ast.Constant):
        if isinstance(body[0].value.value, str):
            body = body[1:]
    statements: list[str] = []
    for node in body:
        if not (
            isinstance(node, ast.Expr)
            and isinstance(node.value, ast.Call)
            and isinstance(node.value.func, ast.Attribute)
            and isinstance(node.value.func.value, ast.Name)
            and node.value.func.value.id == "op"
            and node.value.func.attr == "execute"
            and len(node.value.args) == 1
            and not node.value.keywords
            and isinstance(node.value.args[0], ast.Constant)
            and isinstance(node.value.args[0].value, str)
        ):
            raise ValueError(f"{revision}: security-preserving downgrade must contain REVOKE only")
        statements.append(_normalized_sql(node.value.args[0].value))
    if tuple(statements) != tuple(_normalized_sql(sql) for sql in expected):
        raise ValueError(f"{revision}: security-preserving downgrade differs from reviewed REVOKE")
    return True


def _downgrade_is_refusal(tree: ast.Module, revision: str) -> tuple[bool, str | None]:
    """Whether a downgrade is an explicit irreversible security boundary."""
    if reviewed_security_preserving_downgrade(tree, revision):
        return True, None
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
        irreversible, message = _downgrade_is_refusal(tree, assignments["revision"])
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
