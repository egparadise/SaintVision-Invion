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
    assert ordered[-1].revision == "0020_shard_recovery"
    parents = {r.revision: r.down_revision for r in revisions}
    assert parents["0008_node_certificate_lookup"] == "0006_control_api"
    assert parents["0007_delivery_queue"] == "0006_control_api"
    assert module.downgrade_target(revisions) == "0020_shard_recovery"
    with pytest.raises(ValueError, match="unmerged"):
        module.chain(
            [
                r
                for r in revisions
                if r.revision not in {"0019_workspace_api_integration", "0020_shard_recovery"}
            ]
        )
    # A disconnected cycle must not be hidden behind the valid merged head.
    extra = [
        replace(ordered[0], revision="cycle_a", down_revision="cycle_b"),
        replace(ordered[0], revision="cycle_b", down_revision="cycle_a"),
    ]
    with pytest.raises(ValueError, match="unreachable"):
        module.chain(revisions + extra)
