import json
from pathlib import Path

import pytest

from inv.contracts import validate_contract
from inv.errors import DomainError

ROOT = Path(__file__).resolve().parents[2]
FIXTURES = {
    "WorkspaceRestoreView": "workspace-restore-response.json",
    "WorkspaceCheckoutView": "workspace-checkout-response.json",
}


@pytest.mark.parametrize("name,filename", FIXTURES.items())
def test_workspace_recovery_response_fixture_is_strict(name, filename):
    value = json.loads((ROOT / "contracts" / "fixtures" / filename).read_text("utf-8"))
    validate_contract(name, value)
    for broken in (
        {**value, "unexpected": True},
        {key: item for key, item in value.items() if key != "sha256"},
        {**value, "generation": "../working"},
        {**value, "sha256": "not-a-digest"},
    ):
        with pytest.raises(DomainError):
            validate_contract(name, broken)


@pytest.mark.parametrize(
    "name,value",
    [
        (
            "WorkspaceRestoreInput",
            {
                "workspaceId": "wsp_0123456789ABCDEFGHJKMNPQRS",
                "sourceAttempt": 1,
                "stepId": "files-v1",
                "expectedVersion": 2,
            },
        ),
        ("WorkspaceCheckoutInput", {"expectedVersion": 2}),
    ],
)
def test_workspace_recovery_input_contract_rejects_unknown_or_boolean_version(name, value):
    validate_contract(name, value)
    for broken in ({**value, "unexpected": True}, {**value, "expectedVersion": True}):
        with pytest.raises(DomainError):
            validate_contract(name, broken)
