from __future__ import annotations

import copy
import hashlib
import json
import subprocess
from pathlib import Path

import pytest
from pydantic import ValidationError

from saintvision.api.schemas import (
    ReleaseAcceptanceReferenceResolutionResponse,
    ReleaseAcceptanceTargetRegistryResponse,
)


ROOT = Path(__file__).resolve().parents[2]
REGISTRY = ROOT / "contracts" / "release-acceptance-target-registry-v1.json"


def _registry() -> dict:
    return json.loads(REGISTRY.read_text(encoding="utf-8"))


def _canonical_target_sha256(target: dict) -> str:
    payload = copy.deepcopy(target)
    payload.pop("targetSha256")
    raw = json.dumps(
        payload,
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":"),
    ).encode("utf-8")
    return hashlib.sha256(raw).hexdigest()


def _resolution() -> dict:
    return {
        "schemaVersion": "release-acceptance-reference-resolution:1",
        "targetRegistryId": "release-acceptance-targets-v1",
        "targetRegistryVersion": 1,
        "targetRegistryBlobSha256": "a" * 64,
        "targets": [
            {
                "targetId": "AC-12.release-acceptance-v1",
                "targetVersion": 1,
                "acceptanceIdRef": "AC-12",
                "targetSha256": "b" * 64,
            }
        ],
        "measurements": [
            {
                "evidenceId": "evidence-1",
                "evidenceSha256": "c" * 64,
                "observedAt": "2026-10-01T12:00:00Z",
            }
        ],
        "scopeVerified": True,
        "allResolved": True,
    }


def test_checked_in_target_registry_is_strict_nonempty_and_self_consistent():
    raw = _registry()
    parsed = ReleaseAcceptanceTargetRegistryResponse.model_validate(raw)

    assert parsed.registry_id == "release-acceptance-targets-v1"
    assert len(parsed.targets) == 1
    target = raw["targets"][0]
    assert [criterion["criterionId"] for criterion in target["criteria"]] == [
        "five-node-journey-recorded",
        "quantitative-targets-recorded",
        "known-limitations-recorded",
        "human-acceptance-recorded",
    ]
    assert target["targetSha256"] == _canonical_target_sha256(target)


def test_target_source_commit_and_blob_are_real_git_objects():
    source = _registry()["targets"][0]["source"]
    blob = subprocess.run(
        ["git", "rev-parse", f"{source['commitSha']}:{source['path']}"],
        cwd=ROOT,
        check=True,
        capture_output=True,
        text=True,
    ).stdout.strip()
    assert blob == source["blobSha"]


@pytest.mark.parametrize(
    "mutate",
    [
        lambda document: document.update({"targets": []}),
        lambda document: document.update({"owner": "operator"}),
        lambda document: document.update({"registryVersion": 2}),
        lambda document: document.update({"unexpected": True}),
        lambda document: document["targets"][0].update({"targetSha256": "A" * 64}),
        lambda document: document["targets"][0].update({"criteria": []}),
        lambda document: document["targets"][0]["criteria"].append(
            copy.deepcopy(document["targets"][0]["criteria"][0])
        ),
        lambda document: document["targets"].append(copy.deepcopy(document["targets"][0])),
    ],
)
def test_target_registry_shape_mutations_are_rejected(mutate):
    document = _registry()
    mutate(document)
    with pytest.raises(ValidationError):
        ReleaseAcceptanceTargetRegistryResponse.model_validate(document)


def test_target_digest_mutation_is_detected_even_when_shape_remains_valid():
    document = _registry()
    document["targets"][0]["criteria"][0]["statement"] += " altered"
    parsed = ReleaseAcceptanceTargetRegistryResponse.model_validate(document)
    assert parsed.targets
    assert document["targets"][0]["targetSha256"] != _canonical_target_sha256(
        document["targets"][0]
    )


def test_reference_resolution_contract_is_all_or_nothing():
    parsed = ReleaseAcceptanceReferenceResolutionResponse.model_validate(_resolution())
    assert parsed.scope_verified is True
    assert parsed.all_resolved is True


@pytest.mark.parametrize(
    "mutate",
    [
        lambda document: document.update({"allResolved": False}),
        lambda document: document.update({"scopeVerified": False}),
        lambda document: document.update({"targets": []}),
        lambda document: document.update({"measurements": []}),
        lambda document: document["measurements"][0].update(
            {"observedAt": "2026-10-01T12:00:00"}
        ),
        lambda document: document["measurements"].append(
            copy.deepcopy(document["measurements"][0])
        ),
        lambda document: document["targets"].append(copy.deepcopy(document["targets"][0])),
        lambda document: document.update({"callerSuppliedFallback": "forbidden"}),
    ],
)
def test_partial_ambiguous_or_unscoped_resolution_is_rejected(mutate):
    document = _resolution()
    mutate(document)
    with pytest.raises(ValidationError):
        ReleaseAcceptanceReferenceResolutionResponse.model_validate(document)


def test_public_schema_keeps_digest_and_resolution_guards_literal():
    registry_schema = ReleaseAcceptanceTargetRegistryResponse.model_json_schema(by_alias=True)
    resolution_schema = ReleaseAcceptanceReferenceResolutionResponse.model_json_schema(by_alias=True)

    assert registry_schema["additionalProperties"] is False
    assert registry_schema["properties"]["targets"]["minItems"] == 1
    assert resolution_schema["additionalProperties"] is False
    assert resolution_schema["properties"]["allResolved"]["const"] is True
    assert resolution_schema["properties"]["scopeVerified"]["const"] is True
    sha = resolution_schema["$defs"]["ReleaseAcceptanceResolvedMeasurement"]["properties"][
        "evidenceSha256"
    ]
    assert sha["pattern"] == "^[0-9a-f]{64}$"
