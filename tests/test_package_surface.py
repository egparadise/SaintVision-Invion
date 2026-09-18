"""What the deployable package exposes.

``src/saintvision`` is what gets installed and what an operator points a server
at. Everything importable from it is therefore reachable in production, whether
or not anything currently imports it — "nothing wires it up" is a property of
today's configuration, not of the artefact.

These tests exist because a second FastAPI application appeared in the package
during the integration merge (now ``saintvision.demo_server``): a complete control plane
built on in-memory fixtures, whose ``POST /v1/approvals/{id}/approve`` takes no
credential of any kind and whose ``POST /v1/auth/token`` mints an unsigned
string and returns a hardcoded tenant id. It is a mock backend for the web
client, and as a mock it is reasonable. Inside the production package, under
the name ``server.py``, it is one ``uvicorn saintvision.server:app`` away from
being the approval mechanism — beside the real one, which spends four tables,
a nonce, a quorum and row level security on the same decision.

VF-CX-01 preserves both historical controllers under tests/fixtures. Neither
is installable or present in the production container. The configured server
factory remains the sole deployment entry point; the business factory is only
composed through that authenticated boundary.
"""

from __future__ import annotations

import ast
import pathlib

import pytest

PACKAGE = pathlib.Path(__file__).resolve().parents[1] / "src" / "saintvision"

#: The one application. Everything else that constructs a FastAPI app inside
#: the package is a second front door onto the same product.
SANCTIONED_APP_MODULE = "api/app.py"

#: Known and accepted for now, with the reason. Removing an entry here should
#: mean the file moved out of the package, never that the test was relaxed.
QUARANTINE: dict[str, str] = {}  # Fixtures now live only under tests/fixtures.


def _modules_constructing_an_app() -> set[str]:
    found = set()
    for path in sorted(PACKAGE.rglob("*.py")):
        tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
        for node in ast.walk(tree):
            if (
                isinstance(node, ast.Call)
                and isinstance(node.func, ast.Name)
                and node.func.id == "FastAPI"
            ):
                found.add(path.relative_to(PACKAGE).as_posix())
    return found


def test_the_package_exposes_one_application_plus_the_known_quarantine():
    """A new front door must be a decision, not a merge outcome."""
    found = _modules_constructing_an_app()
    unexpected = found - {SANCTIONED_APP_MODULE} - set(QUARANTINE)
    assert not unexpected, (
        f"new FastAPI applications in the installed package: {sorted(unexpected)}. "
        "The package is what an operator serves; a second application in it is a "
        "second answer to who may do what. Move it out, or add it to QUARANTINE "
        "with the reason and an owner."
    )


def test_no_production_module_imports_test_controllers():
    for path in PACKAGE.rglob("*.py"):
        tree = ast.parse(path.read_text(encoding="utf-8"))
        for node in ast.walk(tree):
            modules = ([node.module or ""] if isinstance(node, ast.ImportFrom)
                       else [n.name for n in node.names] if isinstance(node, ast.Import) else [])
            assert not any(m.startswith(("tests.", "fixtures.")) or "demo_server" in m
                           for m in modules), str(path)


def test_the_quarantine_list_has_not_grown_silently():
    """No fixture application belongs in the installable production package."""
    assert not QUARANTINE
    assert all(len(reason) > 40 for reason in QUARANTINE.values())
