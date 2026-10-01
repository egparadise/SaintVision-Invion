"""Which criteria a release must have accepted, read fail-closed (S12-BE, #282 §5-1).

``operatorSignOff`` is "every required criterion is accepted by two attested people".
The dangerous half of that sentence is **required**, because ``all([])`` is ``True``:
a registry that failed to load, or loaded empty, would make every release signed off
by nobody. So this module's contract is that it either returns a non-empty set of
criteria *and* the version and digest they came from, or it refuses with a reason --
there is no third state and no default.

What it refuses, each because it is a way of accidentally reporting sign-off:

* the file is absent, unreadable, or not a JSON object;
* the schema version is not the one this code understands;
* ``policyVersion`` is not a positive integer;
* ``requiredCriteria`` is missing, not a list, or **empty**;
* a criterion is malformed, or names a registry it does not;
* two criteria name the same ``acceptanceIdRef``, which would make "all required" a
  question with two answers;
* the caller passes no pinned digest, or the file's bytes do not hash to it.

The pin is the part that makes this a contract rather than a file. A deployment
records this file's sha256 and ``policyVersion`` in the release manifest; the reader
binds to that pair, so editing the registry does not retroactively re-scope a
decision made under the old one -- it invalidates it, exactly as a manifest change
does (§5-1).
"""

from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass
from pathlib import Path

#: The Git-owned registry. One path, in ``contracts`` with the other published
#: contracts, because "where is the authoritative list" must have one answer.
REGISTRY_PATH = Path(__file__).resolve().parents[3] / "contracts" / "release-acceptance-policy-registry-v1.json"

SCHEMA_VERSION = "release-acceptance-policy-registry:1"

#: A criterion reference, matching the public contract's ``acceptanceIdRef`` pattern.
_REF_MAX = 16


@dataclass(frozen=True)
class RequiredCriterion:
    """One criterion a release must have accepted, and where its refs resolve."""

    acceptance_id_ref: str
    target_registry_ref: str
    measurement_registry_ref: str


@dataclass(frozen=True)
class PolicyRegistry:
    """A loaded registry, or the reason there isn't one.

    ``refused`` is not an exception because the read path has to answer "is this
    release signed off" with ``false`` and a reason, not raise -- a projection that
    raised would turn a missing file into a 500 on a page that should say "no".
    """

    policy_version: int | None
    registry_sha256: str | None
    required_criteria: tuple[RequiredCriterion, ...]
    refused: str | None

    @property
    def usable(self) -> bool:
        """True only with a reason-free load of at least one criterion.

        Both halves matter: ``refused is None`` alone would admit an empty set, and a
        non-empty set alone would admit one assembled while something was refused.
        """
        return self.refused is None and bool(self.required_criteria)

    def names(self) -> frozenset[str]:
        return frozenset(item.acceptance_id_ref for item in self.required_criteria)


def _refuse(reason: str) -> PolicyRegistry:
    return PolicyRegistry(
        policy_version=None, registry_sha256=None, required_criteria=(), refused=reason
    )


def digest_of(path: Path = REGISTRY_PATH) -> str | None:
    """The registry file's sha256, or None when there is no file to hash."""
    try:
        return hashlib.sha256(path.read_bytes()).hexdigest()
    except OSError:
        return None


def load(
    *, pinned_sha256: str | None, pinned_version: int | None = None, path: Path = REGISTRY_PATH
) -> PolicyRegistry:
    """Read the registry and bind it to the pin a release recorded.

    ``pinned_sha256`` is what the release manifest stored at deployment. Without it
    this refuses: an unpinned release is one whose required criteria nobody wrote
    down, and treating today's file as its policy would be deciding retroactively
    what it was accepted against.
    """
    if not isinstance(pinned_sha256, str) or len(pinned_sha256) != 64 or pinned_sha256 != pinned_sha256.lower():
        return _refuse("the release records no pinned policy registry digest")
    try:
        raw = path.read_bytes()
    except OSError:
        return _refuse("the policy registry file is absent or unreadable")
    actual = hashlib.sha256(raw).hexdigest()
    if actual != pinned_sha256:
        return _refuse("the policy registry has changed since this release pinned it")
    try:
        document = json.loads(raw.decode("utf-8"))
    except (UnicodeDecodeError, ValueError):
        return _refuse("the policy registry is not valid JSON")
    if not isinstance(document, dict):
        return _refuse("the policy registry must be a JSON object")
    if document.get("schemaVersion") != SCHEMA_VERSION:
        return _refuse("the policy registry declares a schema this build does not read")

    version = document.get("policyVersion")
    if not isinstance(version, int) or isinstance(version, bool) or version < 1:
        return _refuse("policyVersion must be a positive integer")
    if pinned_version is not None and version != pinned_version:
        return _refuse("the policy registry version has moved since this release pinned it")

    listed = document.get("requiredCriteria")
    if not isinstance(listed, list) or not listed:
        # The empty case is called out because it is the one that fails *upward*:
        # "every required criterion is accepted" is vacuously true of no criteria.
        return _refuse("requiredCriteria must list at least one criterion")

    criteria: list[RequiredCriterion] = []
    for entry in listed:
        if not isinstance(entry, dict):
            return _refuse("each required criterion must be an object")
        ref = entry.get("acceptanceIdRef")
        target = entry.get("targetRegistryRef")
        measurement = entry.get("measurementRegistryRef")
        if not isinstance(ref, str) or not 1 < len(ref) <= _REF_MAX or ref != ref.upper():
            return _refuse("a required criterion names no usable acceptanceIdRef")
        if not isinstance(target, str) or not target:
            return _refuse(f"{ref} names no target registry")
        if not isinstance(measurement, str) or not measurement:
            return _refuse(f"{ref} names no measurement registry")
        criteria.append(
            RequiredCriterion(
                acceptance_id_ref=ref,
                target_registry_ref=target,
                measurement_registry_ref=measurement,
            )
        )

    names = [item.acceptance_id_ref for item in criteria]
    if len(set(names)) != len(names):
        return _refuse("requiredCriteria names the same criterion twice")

    return PolicyRegistry(
        policy_version=version,
        registry_sha256=actual,
        required_criteria=tuple(criteria),
        refused=None,
    )
