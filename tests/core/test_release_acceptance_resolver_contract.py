from __future__ import annotations

import copy
import hashlib
import json
import subprocess
from pathlib import Path

import pytest
from pydantic import ValidationError

from saintvision.api.schemas import (
    ReleaseAcceptanceEvidenceDiscoveryPageResponse,
    ReleaseAcceptanceReferenceResolutionResponse,
    ReleaseAcceptanceTargetRegistryResponse,
    load_release_acceptance_target_registry_json,
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
        "releaseId": "rel-1",
        "acceptanceIdRef": "AC-12",
        "policyRegistryVersion": 1,
        "policyRegistrySha256": "9" * 64,
        "targetRegistryId": "release-acceptance-targets-v1",
        "targetRegistryVersion": 1,
        "targetRegistryGitBlobSha": "a" * 40,
        "targetRegistryFileSha256": "b" * 64,
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


def _discovery_page() -> dict:
    resolution = _resolution()
    return {
        "schemaVersion": "release-acceptance-evidence-discovery-page:1",
        "releaseId": resolution["releaseId"],
        "acceptanceIdRef": resolution["acceptanceIdRef"],
        "policyRegistryVersion": resolution["policyRegistryVersion"],
        "policyRegistrySha256": resolution["policyRegistrySha256"],
        "targetRegistryVersion": resolution["targetRegistryVersion"],
        "targetRegistryGitBlobSha": resolution["targetRegistryGitBlobSha"],
        "targetRegistryFileSha256": resolution["targetRegistryFileSha256"],
        "targets": resolution["targets"],
        "items": resolution["measurements"],
        "nextCursor": None,
        "scopeVerified": True,
    }


def test_checked_in_target_registry_is_strict_nonempty_and_self_consistent():
    raw = _registry()
    parsed = load_release_acceptance_target_registry_json(
        REGISTRY.read_text(encoding="utf-8")
    )

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
    subprocess.run(
        ["git", "merge-base", "--is-ancestor", source["commitSha"], "HEAD"],
        cwd=ROOT,
        check=True,
    )


@pytest.mark.parametrize(
    "mutate",
    [
        lambda text: text.replace(
            '"owner": "S12-BE",',
            '"owner": "S12-BE",\n  "owner": "S12-BE",',
            1,
        ),
        lambda text: text.replace(
            "The five-node development, deployment, and recovery journey is recorded.",
            "The five-node development, deployment, and recovery journey is recorded. ",
            1,
        ),
    ],
)
def test_registry_loader_rejects_duplicate_keys_and_implicit_string_trimming(mutate):
    raw = REGISTRY.read_text(encoding="utf-8")
    with pytest.raises(ValueError):
        load_release_acceptance_target_registry_json(mutate(raw))


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
    assert document["targets"][0]["targetSha256"] != _canonical_target_sha256(
        document["targets"][0]
    )
    with pytest.raises(ValidationError, match="targetSha256"):
        ReleaseAcceptanceTargetRegistryResponse.model_validate(document)


def test_non_nfc_target_string_is_rejected_even_with_recomputed_digest():
    document = _registry()
    target = document["targets"][0]
    target["criteria"][0]["statement"] += " e\u0301"
    target["targetSha256"] = _canonical_target_sha256(target)
    with pytest.raises(ValidationError, match="NFC-normalized"):
        ReleaseAcceptanceTargetRegistryResponse.model_validate(document)


def test_target_owner_is_literal_even_with_recomputed_digest():
    document = _registry()
    target = document["targets"][0]
    target["owner"] = "operator"
    target["targetSha256"] = _canonical_target_sha256(target)
    with pytest.raises(ValidationError):
        ReleaseAcceptanceTargetRegistryResponse.model_validate(document)


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
        lambda document: document.pop("releaseId"),
        lambda document: document.pop("acceptanceIdRef"),
        lambda document: document.pop("policyRegistrySha256"),
        lambda document: document.update({"policyRegistrySha256": "A" * 64}),
        lambda document: document.update({"targetRegistryFileSha256": "a" * 63}),
        lambda document: document.update({"targetRegistryFileSha256": "A" * 64}),
        lambda document: document["targets"][0].update({"acceptanceIdRef": "AC-11"}),
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


def test_discovery_page_is_bounded_scoped_and_criterion_consistent():
    parsed = ReleaseAcceptanceEvidenceDiscoveryPageResponse.model_validate(
        _discovery_page()
    )
    assert parsed.scope_verified is True
    assert len(parsed.items) == 1

    for mutate in (
        lambda document: document.update({"items": []}),
        lambda document: document.update({"scopeVerified": False}),
        lambda document: document["targets"][0].update(
            {"acceptanceIdRef": "AC-11"}
        ),
        lambda document: document.update({"operatorSelectedProjectId": "project-1"}),
    ):
        document = _discovery_page()
        mutate(document)
        with pytest.raises(ValidationError):
            ReleaseAcceptanceEvidenceDiscoveryPageResponse.model_validate(document)


def test_public_schema_keeps_digest_and_resolution_guards_literal():
    registry_schema = ReleaseAcceptanceTargetRegistryResponse.model_json_schema(by_alias=True)
    resolution_schema = ReleaseAcceptanceReferenceResolutionResponse.model_json_schema(by_alias=True)
    discovery_schema = ReleaseAcceptanceEvidenceDiscoveryPageResponse.model_json_schema(
        by_alias=True
    )

    assert registry_schema["additionalProperties"] is False
    assert registry_schema["properties"]["targets"]["minItems"] == 1
    assert resolution_schema["additionalProperties"] is False
    assert resolution_schema["properties"]["allResolved"]["const"] is True
    assert resolution_schema["properties"]["scopeVerified"]["const"] is True
    assert resolution_schema["properties"]["policyRegistrySha256"]["pattern"] == "^[0-9a-f]{64}$"
    assert resolution_schema["properties"]["targetRegistryGitBlobSha"]["pattern"] == "^[0-9a-f]{40}$"
    assert resolution_schema["properties"]["targetRegistryFileSha256"]["pattern"] == "^[0-9a-f]{64}$"
    assert discovery_schema["additionalProperties"] is False
    assert discovery_schema["properties"]["items"]["minItems"] == 1
    assert discovery_schema["properties"]["items"]["maxItems"] == 100
    assert discovery_schema["properties"]["scopeVerified"]["const"] is True
    sha = resolution_schema["$defs"]["ReleaseAcceptanceResolvedMeasurement"]["properties"][
        "evidenceSha256"
    ]
    assert sha["pattern"] == "^[0-9a-f]{64}$"
