"""The registry either answers with criteria or refuses with a reason (#282 §5-1).

``all([])`` is ``True``. That one fact is why this file exists: every refusal below is
a way the reader could otherwise have reported "every required criterion is accepted"
about a release nobody accepted. So each test asserts the refusal *and* that
``usable`` is false, because a caller that only looked at the criteria would read an
empty tuple as "nothing required".
"""

from __future__ import annotations

import hashlib
import json
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "src"))

from saintvision.services import release_acceptance_policy as policy  # noqa: E402

SHIPPED = ROOT / "contracts" / "release-acceptance-policy-registry-v1.json"


def pin(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def write(tmp_path: Path, document, *, name="registry.json") -> Path:
    path = tmp_path / name
    if isinstance(document, (dict, list)):
        path.write_text(json.dumps(document, ensure_ascii=False), encoding="utf-8")
    else:
        path.write_bytes(document if isinstance(document, bytes) else document.encode("utf-8"))
    return path


def valid() -> dict:
    return {
        "schemaVersion": policy.SCHEMA_VERSION,
        "policyVersion": 3,
        "requiredCriteria": [
            {
                "acceptanceIdRef": "AC-12",
                "targetRegistryRef": "release-acceptance-targets-v1",
                "measurementRegistryRef": "evidence-canonical-digest-v1",
            }
        ],
    }


# ----------------------------------------------------------------- the shipped file


def test_the_shipped_registry_loads_and_requires_at_least_one_criterion():
    """The file in ``contracts`` is the one deployments pin, so it must load."""
    loaded = policy.load(pinned_sha256=pin(SHIPPED), path=SHIPPED)
    assert loaded.usable, loaded.refused
    assert loaded.refused is None
    assert "AC-12" in loaded.names()
    assert loaded.registry_sha256 == pin(SHIPPED)
    assert loaded.policy_version >= 1
    for criterion in loaded.required_criteria:
        assert criterion.target_registry_ref
        assert criterion.measurement_registry_ref


def test_digest_of_the_shipped_registry_is_its_bytes():
    assert policy.digest_of(SHIPPED) == pin(SHIPPED)


def test_digest_of_an_absent_file_is_none_rather_than_an_exception():
    assert policy.digest_of(SHIPPED.parent / "no-such-registry.json") is None


# ----------------------------------------------------------------- the pin


def test_an_unpinned_release_is_refused(tmp_path):
    """A release that recorded no pin has no policy, and today's file is not it."""
    path = write(tmp_path, valid())
    refused = policy.load(pinned_sha256=None, path=path)
    assert not refused.usable
    assert "no pinned policy registry digest" in refused.refused


@pytest.mark.parametrize("bad", ["", "a" * 63, "A" * 64, "z" * 64 + "z", 12, True])
def test_a_pin_that_is_not_a_lowercase_sha256_is_refused(tmp_path, bad):
    path = write(tmp_path, valid())
    assert not policy.load(pinned_sha256=bad, path=path).usable


def test_a_registry_that_changed_since_the_pin_is_refused(tmp_path):
    """The whole point of pinning: an edit invalidates, it does not re-scope."""
    path = write(tmp_path, valid())
    before = pin(path)
    moved = valid()
    moved["requiredCriteria"] = []
    write(tmp_path, moved)
    refused = policy.load(pinned_sha256=before, path=path)
    assert not refused.usable
    assert "changed since this release pinned it" in refused.refused


def test_a_version_that_moved_under_the_same_pin_is_refused(tmp_path):
    path = write(tmp_path, valid())
    refused = policy.load(pinned_sha256=pin(path), pinned_version=2, path=path)
    assert not refused.usable
    assert "version has moved" in refused.refused


def test_the_matching_version_is_accepted(tmp_path):
    path = write(tmp_path, valid())
    assert policy.load(pinned_sha256=pin(path), pinned_version=3, path=path).usable


# ----------------------------------------------------------------- the file


def test_an_absent_registry_is_refused(tmp_path):
    missing = tmp_path / "gone.json"
    refused = policy.load(pinned_sha256="a" * 64, path=missing)
    assert not refused.usable
    assert "absent or unreadable" in refused.refused


def test_a_registry_that_is_not_json_is_refused(tmp_path):
    path = write(tmp_path, "{not json")
    refused = policy.load(pinned_sha256=pin(path), path=path)
    assert not refused.usable
    assert "not valid JSON" in refused.refused


def test_a_registry_that_is_not_an_object_is_refused(tmp_path):
    path = write(tmp_path, [valid()])
    refused = policy.load(pinned_sha256=pin(path), path=path)
    assert not refused.usable
    assert "must be a JSON object" in refused.refused


def test_a_registry_with_undecodable_bytes_is_refused(tmp_path):
    path = write(tmp_path, b"\xff\xfe\x00not utf-8")
    refused = policy.load(pinned_sha256=pin(path), path=path)
    assert not refused.usable


def test_another_schema_version_is_refused(tmp_path):
    document = valid()
    document["schemaVersion"] = "release-acceptance-policy-registry:2"
    path = write(tmp_path, document)
    refused = policy.load(pinned_sha256=pin(path), path=path)
    assert not refused.usable
    assert "schema this build does not read" in refused.refused


@pytest.mark.parametrize("version", [0, -1, "3", 3.0, True, None])
def test_a_policy_version_that_is_not_a_positive_integer_is_refused(tmp_path, version):
    """``True`` is an int in Python, and a version of ``True`` is not a version."""
    document = valid()
    document["policyVersion"] = version
    path = write(tmp_path, document)
    refused = policy.load(pinned_sha256=pin(path), path=path)
    assert not refused.usable
    assert "positive integer" in refused.refused


# ----------------------------------------------------------------- the criteria


@pytest.mark.parametrize("listed", [[], None, {}, "AC-12"])
def test_a_registry_without_criteria_is_refused(tmp_path, listed):
    """The empty list is the dangerous one: it would make sign-off vacuously true."""
    document = valid()
    document["requiredCriteria"] = listed
    path = write(tmp_path, document)
    refused = policy.load(pinned_sha256=pin(path), path=path)
    assert not refused.usable
    assert refused.required_criteria == ()
    assert "at least one criterion" in refused.refused


def test_the_empty_set_can_never_be_read_as_every_criterion_accepted(tmp_path):
    """Stated as its own test because it is the failure mode, not a shape error.

    A caller asking "are all required criteria accepted" over ``load(...).required_criteria``
    would get ``True`` from an empty tuple. ``usable`` is what stands between that
    caller and a release signed off by nobody, so it is false for every refusal.
    """
    document = valid()
    document["requiredCriteria"] = []
    path = write(tmp_path, document)
    refused = policy.load(pinned_sha256=pin(path), path=path)
    assert all(True for _ in refused.required_criteria)  # vacuously true, and
    assert not refused.usable  # this is why that does not matter


def test_a_duplicate_criterion_is_refused(tmp_path):
    """Two entries for one criterion make "all required" a question with two answers."""
    document = valid()
    document["requiredCriteria"] = [
        document["requiredCriteria"][0],
        dict(document["requiredCriteria"][0], targetRegistryRef="other-targets-v1"),
    ]
    path = write(tmp_path, document)
    refused = policy.load(pinned_sha256=pin(path), path=path)
    assert not refused.usable
    assert "same criterion twice" in refused.refused


@pytest.mark.parametrize(
    "entry",
    [
        "AC-12",
        {"acceptanceIdRef": "ac-12", "targetRegistryRef": "t", "measurementRegistryRef": "m"},
        {"acceptanceIdRef": "A", "targetRegistryRef": "t", "measurementRegistryRef": "m"},
        {"acceptanceIdRef": "A" * 17, "targetRegistryRef": "t", "measurementRegistryRef": "m"},
        {"acceptanceIdRef": "AC-12", "measurementRegistryRef": "m"},
        {"acceptanceIdRef": "AC-12", "targetRegistryRef": "", "measurementRegistryRef": "m"},
        {"acceptanceIdRef": "AC-12", "targetRegistryRef": "t"},
        {"acceptanceIdRef": "AC-12", "targetRegistryRef": "t", "measurementRegistryRef": ""},
        {"acceptanceIdRef": 12, "targetRegistryRef": "t", "measurementRegistryRef": "m"},
    ],
)
def test_a_malformed_criterion_is_refused(tmp_path, entry):
    """Each way an entry can fail to name what it must, one at a time."""
    document = valid()
    document["requiredCriteria"] = [entry]
    path = write(tmp_path, document)
    refused = policy.load(pinned_sha256=pin(path), path=path)
    assert not refused.usable
    assert refused.refused


def test_an_unknown_top_level_key_is_tolerated_but_changes_the_digest(tmp_path):
    """Extra keys are not refused -- ``owner`` and ``note`` are in the shipped file.

    What makes that safe is the pin: adding a key changes the bytes, so a release
    pinned to the old digest refuses rather than silently reading the new document.
    """
    document = valid()
    document["note"] = "who owns this and why"
    path = write(tmp_path, document)
    assert policy.load(pinned_sha256=pin(path), path=path).usable
    assert pin(path) != hashlib.sha256(json.dumps(valid(), ensure_ascii=False).encode()).hexdigest()
