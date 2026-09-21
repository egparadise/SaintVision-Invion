"""Storage list responses share one strict fixture across provider and UI."""

from __future__ import annotations

import json
from datetime import datetime
from pathlib import Path
from types import SimpleNamespace
import uuid

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient
from pydantic import ValidationError

from saintvision.api import schemas
from saintvision.api.v1 import storage
from saintvision.identity.principal import Principal
from saintvision.services.pagination import Page


ROOT = Path(__file__).resolve().parents[2]
FIXTURES = ROOT / "contracts/fixtures"


def _fixture(name: str) -> dict:
    return json.loads((FIXTURES / name).read_text(encoding="utf-8"))


def _datetime(value: str | None) -> datetime | None:
    return datetime.fromisoformat(value.replace("Z", "+00:00")) if value else None


@pytest.mark.parametrize(
    ("filename", "model"),
    [
        ("storage-contributions-response.json", schemas.ContributionPageResponse),
        ("storage-locations-response.json", schemas.DataLocationPageResponse),
    ],
)
def test_shared_storage_fixture_matches_strict_page_contract(filename, model):
    payload = _fixture(filename)
    parsed = model.model_validate(payload)
    assert parsed.model_dump(by_alias=True, mode="json") == payload


@pytest.mark.parametrize(
    ("filename", "model"),
    [
        ("storage-contributions-response.json", schemas.ContributionPageResponse),
        ("storage-locations-response.json", schemas.DataLocationPageResponse),
    ],
)
@pytest.mark.parametrize("mutation", ["missing-page-cursor", "extra-page-field", "missing-item-field", "extra-item-field"])
def test_storage_fixture_shape_drift_is_rejected(filename, model, mutation):
    payload = _fixture(filename)
    if mutation == "missing-page-cursor":
        payload.pop("nextCursor")
    elif mutation == "extra-page-field":
        payload["fabricatedCount"] = 1
    elif mutation == "missing-item-field":
        payload["items"][0].pop(next(iter(payload["items"][0])))
    else:
        payload["items"][0]["fabricatedStatus"] = "success"

    with pytest.raises(ValidationError):
        model.model_validate(payload)


@pytest.mark.parametrize(
    ("path", "filename", "service_name"),
    [
        ("/v1/storage/contributions", "storage-contributions-response.json", "list_contributions"),
        ("/v1/storage/locations", "storage-locations-response.json", "list_locations"),
    ],
)
def test_fastapi_storage_list_response_serializes_the_shared_fixture(
    monkeypatch, path, filename, service_name
):
    payload = _fixture(filename)
    item = payload["items"][0]
    if service_name == "list_contributions":
        row = SimpleNamespace(
            contribution_id=item["contributionId"],
            node_id=item["nodeId"],
            declared_path=item["declaredPath"],
            normalized_path=item["normalizedPath"],
            mode=item["mode"],
            status=item["status"],
            capacity_bytes=item["capacityBytes"],
            available_bytes=item["availableBytes"],
            registered_at=_datetime(item["registeredAt"]),
        )
        list_model = schemas.ContributionPageResponse
    else:
        row = SimpleNamespace(
            location_id=item["locationId"],
            contribution_id=item["contributionId"],
            uri=item["uri"],
            kind=item["kind"],
            relative_path=item["relativePath"],
            byte_size=item["byteSize"],
            checksum_sha256=item["checksumSha256"],
            ready=item["ready"],
            verified_at=_datetime(item["verifiedAt"]),
            retention_pinned_until=_datetime(item["retentionPinnedUntil"]),
        )
        list_model = schemas.DataLocationPageResponse

    page = Page(items=[row], next_cursor=payload["nextCursor"])
    monkeypatch.setattr(storage.storage_service, service_name, lambda *_args, **_kwargs: page)
    principal = Principal(
        user_id="usr_contract_fixture",
        tenant_id=uuid.UUID("00000000-0000-4000-8000-000000000041"),
        external_subject="contract-fixture",
    )
    app = FastAPI()
    app.include_router(storage.router)
    app.dependency_overrides[storage.get_principal] = lambda: principal
    app.dependency_overrides[storage.get_session] = lambda: object()
    app.dependency_overrides[storage.get_settings] = lambda: SimpleNamespace(
        page_limit_default=50, page_limit_max=200
    )

    response = TestClient(app).get(path)

    assert response.status_code == 200
    assert response.json() == payload
    list_model.model_validate(response.json())
