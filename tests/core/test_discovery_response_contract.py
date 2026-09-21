"""The discovery-candidates wire contract is checked without a database."""

from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path
from types import SimpleNamespace
import uuid

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient
from pydantic import ValidationError

from saintvision.api import schemas
from saintvision.api.v1 import pools
from saintvision.identity.principal import Principal
from saintvision.services import discovery


ROOT = Path(__file__).resolve().parents[2]
FIXTURE_PATH = ROOT / "contracts/fixtures/discovery-candidates-response.json"


def fixture_payload() -> dict:
    return json.loads(FIXTURE_PATH.read_text(encoding="utf-8"))


def test_shared_fixture_has_exact_contract_properties_and_validates():
    payload = fixture_payload()
    assert set(payload) == {
        field.alias or name
        for name, field in schemas.DiscoveryCandidatesResponse.model_fields.items()
    }
    assert set(payload["items"][0]) == set(
        field.alias or name
        for name, field in schemas.DiscoveryCandidateResponse.model_fields.items()
    )
    parsed = schemas.DiscoveryCandidatesResponse.model_validate(payload)
    assert parsed.items[0].state == "candidate"
    assert parsed.items[0].verified is False


def test_discovery_service_projection_matches_the_shared_candidate_contract():
    item = fixture_payload()["items"][0]
    row = SimpleNamespace(
        announcement_id=item["announcementId"],
        instance_id=item["instanceId"],
        source_ip=item["sourceIp"],
        claimed_hostname=item["claimedHostname"],
        claimed_os_type=item["claimedOsType"],
        claimed_cpu_cores=item["claimedCpuCores"],
        claimed_ram_bytes=item["claimedRamBytes"],
        claimed_gpu_count=item["claimedGpuCount"],
        first_seen_at=datetime.fromisoformat(item["firstSeenAt"].replace("Z", "+00:00")),
        last_seen_at=datetime.fromisoformat(item["lastSeenAt"].replace("Z", "+00:00")),
        announce_count=item["announceCount"],
        state="candidate",
    )

    class ScalarRows:
        def all(self):
            return [row]

    class Session:
        def scalars(self, _query):
            return ScalarRows()

    projected = discovery.list_candidates(
        Session(),
        tenant_id=uuid.UUID("00000000-0000-4000-8000-000000000041"),
        now=datetime(2026, 9, 21, 8, 10, tzinfo=timezone.utc),
    )
    parsed = schemas.DiscoveryCandidateResponse.model_validate(projected[0])
    assert parsed.model_dump(by_alias=True, mode="json") == item


@pytest.mark.parametrize(
    ("mutation", "value"),
    [
        ("missing", "state"),
        ("extra", "fabricatedMeasuredCpu"),
        ("verified", True),
        ("state", "admitted"),
    ],
)
def test_fixture_drift_is_rejected(mutation: str, value):
    payload = fixture_payload()
    item = payload["items"][0]
    if mutation == "missing":
        item.pop(value)
    elif mutation == "extra":
        item[value] = 8
    else:
        item["verified" if mutation == "verified" else "state"] = value
    with pytest.raises(ValidationError):
        schemas.DiscoveryCandidatesResponse.model_validate(payload)


@pytest.mark.parametrize("include_stale", [False, True])
def test_fastapi_provider_serializes_the_shared_response_contract(monkeypatch, include_stale):
    payload = fixture_payload()
    principal = Principal(
        user_id="usr_contract_fixture",
        tenant_id=uuid.UUID("00000000-0000-4000-8000-000000000041"),
        external_subject="contract-fixture",
    )
    now = datetime(2026, 9, 21, 8, 10, tzinfo=timezone.utc)
    calls: list[bool] = []

    def list_candidates(_session, *, tenant_id, now, include_stale=False):
        assert tenant_id == principal.tenant_id
        assert now == datetime(2026, 9, 21, 8, 10, tzinfo=timezone.utc)
        calls.append(include_stale)
        return payload["items"]

    monkeypatch.setattr(pools.discovery_service, "list_candidates", list_candidates)
    app = FastAPI()
    app.include_router(pools.router)
    app.dependency_overrides[pools.get_principal] = lambda: principal
    app.dependency_overrides[pools.get_session] = lambda: object()
    app.dependency_overrides[pools.get_now] = lambda: now

    response = TestClient(app).get(
        "/v1/discovery/candidates",
        params={"includeStale": "true"} if include_stale else None,
    )

    assert response.status_code == 200
    assert response.json() == payload
    assert schemas.DiscoveryCandidatesResponse.model_validate(response.json())
    assert calls == [include_stale]
