"""Which test modules need a real Node runtime, derived rather than listed.

Backend Build runs both halves of the product against one PostgreSQL, which is
the only place their combined behaviour is exercised. It cannot run the suites
that need the Go agent binary and a built container image — Core Build provides
those, and duplicating the toolchain would run the same tests twice.

Those suites refuse to skip under ``CI`` (``pytest.fail("CI must enable real
Node execution tests")``), which is the right discipline for the job that
*should* run them. For the job that structurally cannot, they have to be
deselected instead — and the list of which ones cannot be typed out. It was
three files; one merge later it was ten, reached transitively: a module imports
``approval`` from ``test_approvals``, another imports ``node_runtime`` from
``test_node_runtime``, and the dependency is invisible from the filename.

So it is computed. A new suite that depends on the Node runtime is excluded the
day it lands, and a suite that stops depending on it is included again, without
anyone remembering to edit a list. Three hardcoded lists in this repository
have already gone stale exactly this way, and each time the symptom was a test
that quietly stopped running rather than an error.

Usage:
    python tools/node_dependent_tests.py                 # one path per line
    python tools/node_dependent_tests.py --pytest-args   # --ignore=... flags
"""

from __future__ import annotations

import argparse
import ast
import pathlib

ROOT = pathlib.Path(__file__).resolve().parents[1]
SUITE = ROOT / "tests" / "integration"

#: The fixture that demands ``INV_RUN_NODE_TESTS=1``. A module that reaches it,
#: directly or through another module's fixtures, cannot run without the agent.
ROOT_FIXTURE_MODULE = "test_node_runtime"


def _imports(path: pathlib.Path) -> set[str]:
    """Sibling test modules this one imports from.

    The suite uses a flat layout, so ``from test_approvals import approval`` is
    an ordinary absolute import of a sibling. Only siblings are followed —
    ``inv.*`` and third-party imports say nothing about the runtime.
    """
    # utf-8-sig: some suites carry a BOM, which ast.parse rejects outright.
    tree = ast.parse(path.read_text(encoding="utf-8-sig"), filename=str(path))
    names: set[str] = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.ImportFrom) and node.module and node.level == 0:
            names.add(node.module)
        elif isinstance(node, ast.Import):
            names.update(alias.name for alias in node.names)
    return {n for n in names if (SUITE / f"{n}.py").is_file()}


def dependents() -> list[str]:
    """Modules that transitively reach the Node runtime fixture."""
    graph = {p.stem: _imports(p) for p in sorted(SUITE.glob("test_*.py"))}
    reached = {ROOT_FIXTURE_MODULE}
    changed = True
    while changed:
        changed = False
        for module, imports in graph.items():
            if module not in reached and imports & reached:
                reached.add(module)
                changed = True
    # The root itself is in `reached`; keep it, it is the most obvious member.
    return sorted(
        f"tests/integration/{module}.py" for module in reached if module in graph
    )


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--pytest-args", action="store_true")
    args = parser.parse_args()

    paths = dependents()
    if args.pytest_args:
        print(" ".join(f"--ignore={path}" for path in paths))
    else:
        print("\n".join(paths))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
