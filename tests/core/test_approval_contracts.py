from uuid import uuid4
import pytest
from inv.approvals import Principal
from inv.contracts import validate_contract
from inv.errors import DomainError


@pytest.mark.parametrize(
    "change",
    [
        {"nonce": "short"},
        {"nonce": "!" * 43},
        {"decision": "allow"},
        {"actionDigest": "x" * 64},
        {"subjectId": "forged"},
        {"approvedBy": ["alice", "bob"]},
    ],
)
def test_decision_payload_cannot_forge_identity_or_bypass_nonce(change):
    payload = {
        "decision": "approve",
        "nonce": "a" * 43,
        "actionDigest": "b" * 64,
        **change,
    }
    with pytest.raises(DomainError):
        validate_contract("ApprovalDecisionInput", payload)


@pytest.mark.parametrize(
    "tenant,subject",
    [
        ("not-a-uuid", "alice"),
        (str(uuid4()), ""),
        (str(uuid4()), "a" * 201),
        (str(uuid4()), None),
    ],
)
def test_trusted_principal_requires_valid_identity(tenant, subject):
    with pytest.raises(ValueError):
        Principal(tenant, subject)
