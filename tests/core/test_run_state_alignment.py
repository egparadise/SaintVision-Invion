"""Service and execution kernel must expose the same non-idempotent graph."""
import pytest
from inv.state import FORWARD, TERMINAL, RunState as KernelState
from saintvision.runs.state import TRANSITIONS, RunState as ServiceState


@pytest.mark.parametrize("state", [s.value for s in KernelState])
def test_common_run_graph_edges_agree(state):
    expected = {str(s) for s in FORWARD.get(KernelState(state), set())}
    if KernelState(state) not in TERMINAL:
        expected |= {"failed", "cancelled"}
    assert expected == {s.value for s in TRANSITIONS[ServiceState(state)]}
