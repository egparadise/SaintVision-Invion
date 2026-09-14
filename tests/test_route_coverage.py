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
