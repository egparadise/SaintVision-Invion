"""Replay reviewed frontend payloads against actual kernel HTTP/isolated PG.

Frontend source: integration/all-agents-unified 70ea3fb. This is not a browser
test and does not imply that the frontend has consumed the corrected contract.
"""

import pytest

from test_approvals import approval, request
from test_control_api import api

pytestmark = pytest.mark.postgres


@pytest.mark.parametrize("payload", [
    {"decision": "approve", "nonce": ""},
    {"decision": "reject", "reason": "review rejected"},
])
def test_frontend_decision_payload_rejected_without_mutating_approval(api, payload):
    row = request(api)
    url = api.url + "/approvals/" + row["approvalId"]
    before = api.client.get(url, headers=api.headers("alice")).json()
    response = api.client.post(url + "/decision", json=payload, headers=api.headers("alice"))
    assert response.status_code == 422
    assert api.client.get(url, headers=api.headers("alice")).json() == before


@pytest.mark.parametrize("reason", ["user_requested", "Parent batch cancellation requested"])
def test_frontend_cancel_payload_cannot_cancel_but_versioned_request_can(api, reason):
    run = api.client.post(api.url + "/runs", json={}, headers=api.headers()).json()
    url = api.url + "/runs/" + run["runId"]
    before = api.client.get(url, headers=api.headers()).json()
    response = api.client.post(url + "/cancel", json={"reason": reason}, headers=api.headers())
    assert response.status_code == 422
    assert api.client.get(url, headers=api.headers()).json() == before
    response = api.client.post(url + "/cancel", json={"expectedVersion": before["version"]},
                               headers=api.headers(key="valid-cancel"))
    assert response.status_code == 200 and response.json()["state"] == "cancelled"


@pytest.mark.parametrize("decision", ["approve", "reject"])
def test_challenge_digest_decision_roundtrip_is_the_working_contract(api, decision):
    row = request(api)
    url = api.url + "/approvals/" + row["approvalId"]
    view = api.client.get(url, headers=api.headers("alice")).json()
    assert "nonce" not in view and view["actionDigest"]
    challenge = api.client.post(url + "/challenge", json={}, headers=api.headers("alice"))
    assert challenge.status_code == 200
    response = api.client.post(url + "/decision", headers=api.headers("alice"),
                               json={"decision": decision, "nonce": challenge.json()["nonce"],
                                     "actionDigest": view["actionDigest"]})
    assert response.status_code == 200
