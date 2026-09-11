"""What the deployable package exposes.

``src/saintvision`` is what gets installed and what an operator points a server
at. Everything importable from it is therefore reachable in production, whether
or not anything currently imports it — "nothing wires it up" is a property of
today's configuration, not of the artefact.

These tests exist because a second FastAPI application appeared in the package
during the integration merge (``saintvision.server``): a complete control plane
built on in-memory fixtures, whose ``POST /v1/approvals/{id}/approve`` takes no
credential of any kind and whose ``POST /v1/auth/token`` mints an unsigned
string and returns a hardcoded tenant id. It is a mock backend for the web
client, and as a mock it is reasonable. Inside the production package, under
the name ``server.py``, it is one ``uvicorn saintvision.server:app`` away from
being the approval mechanism — beside the real one, which spends four tables,
a nonce, a quorum and row level security on the same decision.

The tests do not delete it. They state the boundary it crossed, so it is moved
deliberately rather than discovered by whoever runs the wrong command.
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
QUARANTINE: dict[str, str] = {
    "server.py": (
        "Mock control plane for the web client, added during the integration "
        "merge. In-memory state, unsigned tokens, a hardcoded tenant, and "
        "mutating routes — cancel, reclaim-resources, resume/enqueue, "
        "approvals/approve — with no credential check. Belongs beside the web "
        "app it serves, not in the installed package. Owner: Gemini."
    ),
}


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


@pytest.mark.parametrize("module", sorted(QUARANTINE))
def test_a_quarantined_application_is_not_reachable_from_the_real_one(module):
    """It must at least stay disconnected while it is still in the tree.

    An import from the sanctioned application would make the quarantined one
    load in every process that serves the real API, and from there its routes
    are one ``include_router`` away.
    """
    stem = module.removesuffix(".py").replace("/", ".")
    sources = [
        p.read_text(encoding="utf-8")
        for p in (PACKAGE / "api").rglob("*.py")
    ]
    joined = "\n".join(sources)
    assert f"saintvision.{stem}" not in joined, (
        f"the API package imports {stem}, which is quarantined"
    )
    assert f"from ..{stem} import" not in joined
    assert f"from .{stem} import" not in joined


def test_the_quarantine_list_has_not_grown_silently():
    """One entry, with a reason. A growing list is a policy that stopped working."""
    assert set(QUARANTINE) == {"server.py"}
    assert all(len(reason) > 40 for reason in QUARANTINE.values())
