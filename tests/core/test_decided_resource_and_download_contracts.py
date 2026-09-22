"""Approved 2026-09-22 resource-usage and artifact-download contract decisions."""

from copy import deepcopy
import json
from pathlib import Path

import pytest

from inv.contracts import validate_contract
from inv.errors import DomainError
from inv.generated.models import ArtifactDownloadMetadata, NodeResourceUsageResponse


ROOT = Path(__file__).resolve().parents[2]
FIXTURES = ROOT / "contracts" / "fixtures"


def fixture(name):
    return json.loads((FIXTURES / name).read_text(encoding="utf-8"))


def test_capability_resource_usage_fixture_roundtrips_generated_contract():
    payload = fixture("node-resource-usage-response.json")
    validate_contract("NodeResourceUsageResponse", payload)
    assert NodeResourceUsageResponse.model_validate(payload).model_dump(mode="json") == payload
    units = {
        "cpu": "millicores",
        "memory": "bytes",
        "gpu": "devices",
        "storage": "bytes",
        "network": "bitsPerSecond",
    }
    for resource in payload["resources"]:
        assert resource["unit"] == units[resource["kind"]]
        assert resource["offered"] <= resource["capacity"]
        if resource["measured"]:
            assert resource["reserved"] + resource["spare"] == resource["offered"]
        else:
            assert (resource["reserved"], resource["spare"], resource["observedAt"]) == (
                None,
                None,
                None,
            )


@pytest.mark.parametrize(
    "field,value",
    [
        ("unit", "percent"),
        ("reserved", -1),
        ("extra", 1),
    ],
)
def test_resource_usage_schema_rejects_shape_drift(field, value):
    payload = fixture("node-resource-usage-response.json")
    payload["resources"][0][field] = value
    with pytest.raises(DomainError, match="NodeResourceUsageResponse: invalid contract"):
        validate_contract("NodeResourceUsageResponse", payload)


def test_unmeasured_resource_cannot_publish_synthetic_usage():
    payload = fixture("node-resource-usage-response.json")
    payload["resources"][1]["reserved"] = 0
    with pytest.raises(DomainError, match="NodeResourceUsageResponse: invalid contract"):
        validate_contract("NodeResourceUsageResponse", payload)


def test_artifact_download_metadata_fixture_is_canonical():
    payload = fixture("artifact-download-metadata.json")
    validate_contract("ArtifactDownloadMetadata", payload)
    assert ArtifactDownloadMetadata.model_validate(payload).model_dump(mode="json") == payload
    assert payload["digestHeader"] == "X-Content-SHA256"
    assert payload["source"] == "storage-object"


@pytest.mark.parametrize(
    "field,value",
    [
        ("digestHeader", "X-Checksum-SHA256"),
        ("contentSha256", "sha256:" + "0" * 64),
        ("source", "database-receipt"),
    ],
)
def test_artifact_download_contract_rejects_legacy_or_noncanonical_metadata(field, value):
    payload = deepcopy(fixture("artifact-download-metadata.json"))
    payload[field] = value
    with pytest.raises(DomainError, match="ArtifactDownloadMetadata: invalid contract"):
        validate_contract("ArtifactDownloadMetadata", payload)
