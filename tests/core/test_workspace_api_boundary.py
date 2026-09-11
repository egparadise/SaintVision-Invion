from dataclasses import replace
import importlib.util
from pathlib import Path
import pytest
from fastapi.testclient import TestClient
from inv.app import create_app, create_configured_app
from inv.contracts import validate_contract
from inv.errors import DomainError


def test_unconfigured_production_never_serves_demo_runs(monkeypatch):
    monkeypatch.delenv("INV_API_CONFIG", raising=False)
    with pytest.raises(RuntimeError, match="configuration unavailable"):
        create_configured_app()
    from saintvision.server import create_app as production

    with pytest.raises(RuntimeError, match="configuration unavailable"):
        production()
    with TestClient(create_app()) as client:
        assert client.get("/readyz").status_code == 503
        assert client.get("/v1/runs").status_code == 404
        assert (
            client.get("/v1/projects", headers={"Authorization": "Bearer sample-token"}).status_code
            == 503
        )


def test_workspace_api_inputs_reject_implicit_or_client_supplied_authority():
    for name in ("WorkspacePrepareInput", "WorkspaceEnqueueInput"):
        for data in ({}, {"expectedVersion": True}, {"policy": {"effect": "allow"}}):
            with pytest.raises(DomainError):
                validate_contract(name, data)


def test_integrated_migration_keeps_both_published_histories():
    import sys

    path = Path(__file__).resolve().parents[2] / "tools/migration_graph.py"
    spec = importlib.util.spec_from_file_location("workspace_migration_graph", path)
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    revisions = module.load()
    ordered = module.chain(revisions)
    # The head is derived, not named. This assertion used to carry the literal
    # "0027_business_api_guards" and failed the moment a migration was added --
    # the sixth hardcoded revision list in this repository. What the test is
    # actually about is the shape below: one integrated head, and both published
    # histories still reachable from it.
    parented = {
        parent
        for r in revisions
        for parent in (
            r.down_revision
            if isinstance(r.down_revision, tuple)
            else (r.down_revision,)
        )
        if parent
    }
    heads = [r.revision for r in revisions if r.revision not in parented]
    assert heads == [ordered[-1].revision], heads
    parents = {r.revision: r.down_revision for r in revisions}
    assert parents["0008_node_certificate_lookup"] == "0006_control_api"
    assert parents["0007_delivery_queue"] == "0006_control_api"
    assert set(parents["0026_business_start_merge"]) == {"0025_workspace_start", "0025_workspace_tool_choice"}
    assert parents["0025_workspace_start"] == "0023_containment_approvals"
    assert parents["0025_workspace_tool_choice"] == "0024_project_kernel_link"
    # The downgrade target is the newest irreversible-or-merge revision, which
    # is a different thing from the head; the two coincided at 0027 and the old
    # assertion pinned that coincidence rather than any property.
    #
    # Checked against an independent reverse scan. The first replacement here
    # asserted "nothing irreversible lies after the target", which reads like a
    # safety property and cannot fail -- the target *is* the last irreversible
    # one by construction, so the set after it is empty whatever the function
    # returns. This version catches a wrong direction or an off-by-one, which
    # is what could actually go wrong.
    names = [r.revision for r in ordered]
    expected = next(
        (
            r.revision
            for r in reversed(ordered)
            if r.irreversible or isinstance(r.down_revision, tuple)
        ),
        "base",
    )
    target = module.downgrade_target(revisions)
    assert target == expected, (target, expected)
    assert target == "base" or target in names

    # Cut the graph immediately before its first merge. What remains is both
    # branches that fed that merge, with nothing joining them -- which is the
    # unmerged shape this check exists for. Derived rather than listed: the
    # previous version named the revisions to drop, and once 0028 onward arrived
    # the leftovers pointed at parents that were no longer there, so the error
    # raised was "unknown revision parent" and the unmerged case stopped being
    # exercised at all.
    merge = next(r for r in ordered if isinstance(r.down_revision, tuple))
    with pytest.raises(ValueError, match="unmerged"):
        module.chain(ordered[: names.index(merge.revision)])
    # A disconnected cycle must not be hidden behind the valid merged head.
    extra = [
        replace(ordered[0], revision="cycle_a", down_revision="cycle_b"),
        replace(ordered[0], revision="cycle_b", down_revision="cycle_a"),
    ]
    with pytest.raises(ValueError, match="unreachable"):
        module.chain(revisions + extra)
