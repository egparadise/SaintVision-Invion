"""The extraction that produced two wrong numbers by hand.

Each case here is a form the ad-hoc version missed or would have missed. The
point of the file is that the measurement stops depending on whoever typed the
regex that day.
"""

from __future__ import annotations

import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "tools"))

from route_coverage import client_paths, normalise, served_routes  # noqa: E402


def test_registered_surface_ignores_unmounted_router_and_keeps_prefix_and_websocket():
    from fastapi import FastAPI, APIRouter
    from route_coverage import registered_routes

    app = FastAPI()
    mounted, unmounted = APIRouter(prefix='/v1/projects'), APIRouter()
    mounted.add_api_route('/{project}/approvals', lambda: {}, methods=['GET'])
    mounted.add_api_websocket_route('/{project}/socket', lambda: None)
    unmounted.add_api_route('/v1/fixture-only', lambda: {}, methods=['GET'])
    app.include_router(mounted)

    @app.websocket('/v1/workspaces/{workspace}/terminals/{session}')
    async def terminal(socket):
        pass

    assert registered_routes(app) == {
        '/v1/projects/{}/approvals', '/v1/workspaces/{}/terminals/{}',
        '/v1/projects/{}/socket',
    }


def test_business_dispatch_does_not_expose_its_unselected_routes():
    from fastapi import FastAPI
    from inv.business_surface import BusinessDispatch
    from route_coverage import registered_routes

    app, business = FastAPI(), FastAPI()
    for route in ['/v1/projects', '/v1/projects/{project}/approvals', '/v1/projects/{project}/members']:
        app.add_api_route(route, lambda: {})
    business.add_api_route('/v1/projects', lambda: {})
    business.add_api_route('/v1/fixture-only', lambda: {})
    app.add_middleware(BusinessDispatch, business=business)
    # Member listing is shadowed by dispatch but absent from this business app.
    assert registered_routes(app) == {'/v1/projects', '/v1/projects/{}/approvals'}


def test_configured_failure_is_sanitized_and_never_falls_back(tmp_path, monkeypatch, capsys):
    import route_coverage
    monkeypatch.setattr(sys, 'argv', ['route_coverage.py', '--configured-surface', '--client', str(tmp_path)])
    def broken():
        raise RuntimeError('private-dsn-and-key-path')
    monkeypatch.setattr(route_coverage, 'configured_routes', broken)
    with pytest.raises(SystemExit) as error:
        route_coverage.main()
    assert error.value.code == 2
    captured = capsys.readouterr()
    assert 'no source fallback' in captured.err
    assert 'private-dsn' not in captured.err


def test_empty_source_measurement_never_claims_operating_acceptance(tmp_path, monkeypatch, capsys):
    import json
    import route_coverage
    monkeypatch.setattr(sys, 'argv', ['route_coverage.py', '--served', str(tmp_path), '--client', str(tmp_path), '--json'])
    assert route_coverage.main() == 2
    output = json.loads(capsys.readouterr().out)
    assert output['assessment'] == 'inconclusive-no-client-paths'
    assert output['measurement'] == 'source-declarations'
    assert output['operationalAcceptanceAssessed'] is False
    assert 'dynamic prefixes' in output['limitations']


def test_missing_input_directory_is_not_zero_unserved(tmp_path, monkeypatch):
    import route_coverage
    monkeypatch.setattr(sys, 'argv', ['route_coverage.py', '--served', str(tmp_path), '--client', str(tmp_path / 'missing')])
    with pytest.raises(SystemExit) as error:
        route_coverage.main()
    assert error.value.code == 2


def test_the_kernel_decorator_form_is_found() -> None:
    """The miss that made a 54-route service look like a 10-route one.

    The kernel builds its application inside a factory and calls it ``api``, so
    a pattern anchored on ``@app.`` or ``@router.`` finds almost nothing.
    """
    source = '''
    def create_app():
        api = FastAPI()

        @api.get("/v1/projects/{project}/runs")
        def runs(): ...

        @api.post("/v1/projects/{project}/runs/{run_id}/cancel")
        def cancel(): ...
    '''
    assert served_routes(source) == {
        "/v1/projects/{}/runs",
        "/v1/projects/{}/runs/{}/cancel",
    }


@pytest.mark.parametrize("holder", ["app", "api", "router", "business", "control"])
def test_any_holder_name_works(holder: str) -> None:
    """The application object's variable name is not part of the contract."""
    assert served_routes(f'@{holder}.get("/v1/health")\ndef h(): ...') == {"/v1/health"}


def test_websocket_routes_count() -> None:
    """A terminal is reached over a websocket, and the screen still calls it."""
    source = '@api.websocket("/v1/workspaces/{workspace_id}/terminals/{session_id}")'
    assert served_routes(source) == {"/v1/workspaces/{}/terminals/{}"}


def test_a_router_prefix_is_applied() -> None:
    source = '''
    router = APIRouter(prefix="/v1", tags=["nodes"])

    @router.get("/nodes/{node_id}")
    def one(): ...
    '''
    assert served_routes(source) == {"/v1/nodes/{}"}


def test_an_f_string_path_is_found() -> None:
    assert served_routes('@api.get(f"/v1/runs/{run_id}/result")') == {
        "/v1/runs/{}/result"
    }


def test_parameter_spellings_collapse_to_one() -> None:
    """Three languages name the same route three ways."""
    assert (
        normalise("/v1/runs/{run_id}")
        == normalise("/v1/runs/${runId}")
        == normalise("/v1/runs/{id}")
        == "/v1/runs/{}"
    )


def test_a_client_interpolation_is_captured() -> None:
    source = 'await get(`/v1/runs/${activeRunId}/result`)'
    assert "/v1/runs/{}/result" in client_paths(source)


def test_a_plain_client_literal_is_captured() -> None:
    assert client_paths("""fetch('/v1/approvals')""") == {"/v1/approvals"}


def test_non_v1_paths_are_ignored() -> None:
    """Static assets and health checks outside the API are not the question."""
    assert client_paths("""fetch('/assets/app.css'); fetch('/v1/runs')""") == {
        "/v1/runs"
    }


def test_a_hardcoded_fixture_id_is_reported_as_its_own_path() -> None:
    """It is not a parameter, and flattening it would hide it.

    The SPA carries /v1/projects/prj_01JABCDE/runs as a literal, where
    prj_01JABCDE is the demo server's project id. That is worth seeing in the
    output rather than normalising away.
    """
    found = client_paths("""fetch('/v1/projects/prj_01JABCDE/runs')""")
    assert found == {"/v1/projects/prj_01JABCDE/runs"}


def test_a_served_tree_and_a_client_tree_can_disagree_completely() -> None:
    """The shape mismatch, in miniature: same capability, different names."""
    served = served_routes('@api.post("/v1/projects/{p}/approvals/{a}/decision")')
    wanted = client_paths("""fetch(`/v1/approvals/${id}/approve`)""")
    assert not (wanted & served)


def test_a_bare_v1_base_constant_is_not_a_call() -> None:
    """A base-URL literal like `${API}/v1` is configuration, not a request."""
    assert client_paths('const API_BASE = "/v1";') == set()


def test_a_hole_fused_to_a_segment_is_dropped_as_an_artefact() -> None:
    """/v1/${prj}runs, where prj already ends in projects/<id>/, must not be
    reported as the malformed /v1/{}runs -- that is the tool's artefact, not a
    path the SPA asks for."""
    source = 'apiClient(`/v1/${prj}runs/${run.id}/result`)'
    got = client_paths(source)
    assert "/v1/{}runs/{}/result" not in got
    # It is dropped entirely rather than half-corrected; the well-formed sibling
    # (with a slash before the hole) is what the same screen also calls and what
    # the coverage should credit.
    assert all("{}runs" not in p for p in got)


def test_a_properly_separated_interpolation_still_counts() -> None:
    """The fix must not suppress a legitimate leading-parameter path."""
    source = 'apiClient(`/v1/projects/${prj}/runs`)'
    assert "/v1/projects/{}/runs" in client_paths(source)


@pytest.mark.parametrize('served,expected', [(False, 1), (True, 0)])
def test_nonempty_route_comparison_can_pass_or_fail(tmp_path, monkeypatch, capsys, served, expected):
    import json
    import route_coverage
    (tmp_path / 'client.ts').write_text("fetch('/v1/projects')")
    if served:
        (tmp_path / 'api.py').write_text('@api.get("/v1/projects")')
    monkeypatch.setattr(sys, 'argv', ['route_coverage.py', '--served', str(tmp_path),
                                    '--client', str(tmp_path), '--json'])
    assert route_coverage.main() == expected
    report = json.loads(capsys.readouterr().out)
    assert report['assessment'] == 'compared'
    assert report['clientPaths'] == ['/v1/projects']
    assert report['unserved'] == ([] if served else ['/v1/projects'])


def test_client_source_does_not_request_unserved_evidence_or_bare_events_endpoints() -> None:
    """Regression test: client source must never probe non-existent /evidence or bare /v1/events."""
    from pathlib import Path
    from route_coverage import scan_client

    client_root = Path(__file__).resolve().parents[1] / "apps" / "web" / "src"
    paths = scan_client(client_root)
    assert not any("evidence" in p for p in paths), f"Unserved /evidence path detected: {paths}"
    assert "/v1/events" not in paths, f"Bare /v1/events detected: {paths}"


def test_evidence_viewer_integrity_contract_invariants() -> None:
    """Bidirectional regression: EvidenceViewer must never synthesize fake PASS, mock digests, or tool calls."""
    from pathlib import Path

    viewer_path = Path(__file__).resolve().parents[1] / "apps" / "web" / "src" / "features" / "evidence" / "EvidenceViewer.tsx"
    content = viewer_path.read_text(encoding="utf-8")

    # 1. No mock 'sha256:verified' digests
    assert "sha256:verified" not in content, "Mock digest 'sha256:verified' found in EvidenceViewer.tsx"

    # 2. No fabricated tool calls or wall times
    for fake in ["git.checkout", "test.run", "artifact.write", "wallTimeMs"]:
        assert fake not in content, f"Fabricated telemetry '{fake}' found in EvidenceViewer.tsx"

    # 3. Execution success must NOT be equated to cryptographic integrity PASS
    # Integrity PASS must be strictly gated on res.output?.verified === true
    assert "res.output?.verified === true" in content
    assert "integrityStatus = 'UNVERIFIED'" in content

    # 4. Static policy specifications must be labeled distinctly from per-run dynamic verdicts
    assert "[시스템 정책 사양]" in content
    assert "출력 무결성 미검증 (UNVERIFIED)" in content


def test_ui_priority_6_fallback_boundary_invariants() -> None:
    """UI Priority 6 regression: zero mock data fallbacks in ResourceExplorer, PlacementSimulator, and DeveloperStudio."""
    from pathlib import Path

    web_src = Path(__file__).resolve().parents[1] / "apps" / "web" / "src"

    # 1. UI-FB-01 ResourceExplorer: No synthetic candidate in initial state, no fake capacity/capabilities fallback
    re_path = web_src / "features" / "desktop" / "ResourceExplorer.tsx"
    re_content = re_path.read_text(encoding="utf-8")
    assert "ann_node06_unverified" not in re_content, "Synthetic candidate 'ann_node06_unverified' found in ResourceExplorer.tsx"
    assert "totalOfferedCores: 48" not in re_content, "Synthetic 48-core pool fallback found in ResourceExplorer.tsx"
    assert "totalOfferedRamBytes: 192 * 1024 ** 3" not in re_content, "Synthetic 192GiB RAM pool fallback found in ResourceExplorer.tsx"
    assert "vendor: 'DDR4/DDR5'" not in re_content, "Synthetic RAM vendor fallback found in ResourceExplorer.tsx"
    assert "vendor: 'AMD/Intel'" not in re_content, "Synthetic CPU vendor fallback found in ResourceExplorer.tsx"
    assert "discovery-error-banner" in re_content, "Missing discovery-error-banner in ResourceExplorer.tsx"
    assert "discovery-empty-state" in re_content, "Missing discovery-empty-state in ResourceExplorer.tsx"
    assert "pool-capacity-error" in re_content, "Missing pool-capacity-error in ResourceExplorer.tsx"

    # 2. UI-FB-02 PlacementSimulator: UNVERIFIED local evaluation label and preview error banner
    ps_path = web_src / "features" / "placement" / "PlacementSimulator.tsx"
    ps_content = ps_path.read_text(encoding="utf-8")
    assert "UNVERIFIED: 로컬 시뮬레이션 전용" in ps_content, "Missing UNVERIFIED local simulation label in PlacementSimulator.tsx"
    assert "preview-error-banner" in ps_content, "Missing preview-error-banner in PlacementSimulator.tsx"
    assert "pools-error-banner" in ps_content, "Missing pools-error-banner in PlacementSimulator.tsx"
    assert "서버 어드미션 미검증: 가짜 샤드 상태를 생성하지 않습니다" in ps_content, "Missing fake shard prevention message in PlacementSimulator.tsx"

    # 3. UI-FB-03 DeveloperStudio: ResultView fallback gated strictly on isRouteNotFoundError
    ds_path = web_src / "features" / "studio" / "DeveloperStudio.tsx"
    ds_content = ds_path.read_text(encoding="utf-8")
    assert "isRouteNotFoundError" in ds_content, "Missing isRouteNotFoundError import or usage in DeveloperStudio.tsx"
    assert "isRouteNotFoundError(err)" in ds_content, "ResultView catch must test isRouteNotFoundError(err)"
    assert "artifact-error-banner" in ds_content, "Missing artifact-error-banner in DeveloperStudio.tsx"
    assert "artifact-fallback-badge" in ds_content, "Missing artifact-fallback-badge in DeveloperStudio.tsx"


