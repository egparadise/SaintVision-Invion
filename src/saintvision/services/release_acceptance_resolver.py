"""Authoritative S12 target and Evidence reference resolution.

Caller values are comparison inputs only.  Targets come from the checked-in registry;
measurements come from an append-only release binding and the stored Evidence envelope
digest.  No method in this module accepts a caller-selected project.
"""

from __future__ import annotations

import base64
import datetime as dt
import hashlib
import hmac
import json
import uuid
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from sqlalchemy import and_, desc, or_, select
from sqlalchemy.exc import OperationalError
from sqlalchemy.orm import Session

from ..db.models import EvidenceEnvelope, ReleaseEvidenceBinding, ReleaseManifest, Run, Workload
from . import release_acceptance_policy as policy

REGISTRY_PATH = (
    Path(__file__).resolve().parents[3]
    / "contracts"
    / "release-acceptance-target-registry-v1.json"
)
REGISTRY_ID = "release-acceptance-targets-v1"
REGISTRY_VERSION = 1
REGISTRY_GIT_BLOB_SHA = "3da9f53b36961590690606bfe459083c6722a47a"
REGISTRY_FILE_SHA256 = "114db67830599bc5c07142083bb897afd1dd584158fd05ab62d5cb0487c62cbf"
DISCOVERY_PAGE_MAX = 100
RETRYABLE_SQLSTATES = frozenset({"40P01", "55P03", "57014"})


def _retryable(error: OperationalError) -> None:
    from .release_acceptance import ReferenceRetryable

    if getattr(getattr(error, "orig", None), "sqlstate", None) in RETRYABLE_SQLSTATES:
        raise ReferenceRetryable("resolver database wait exceeded its bound") from error
    raise error


@dataclass(frozen=True)
class LoadedTargetRegistry:
    document: Any
    raw: bytes
    git_blob_sha: str
    file_sha256: str


def load_target_registry(path: Path = REGISTRY_PATH) -> LoadedTargetRegistry:
    """Load the exact checked-in registry or fail closed.

    Parsing delegates to the public strict contract so duplicate keys, whitespace
    normalisation, empty targets and target digest drift have one implementation.
    """

    from ..api.schemas import load_release_acceptance_target_registry_json
    from .release_acceptance import PrerequisitesUnavailable

    try:
        raw = path.read_bytes()
    except OSError as error:
        raise PrerequisitesUnavailable("the target registry is absent") from error
    observed = hashlib.sha256(raw).hexdigest()
    if observed != REGISTRY_FILE_SHA256:
        raise PrerequisitesUnavailable("the target registry file digest moved")
    try:
        document = load_release_acceptance_target_registry_json(raw)
    except (UnicodeError, ValueError) as error:
        raise PrerequisitesUnavailable("the target registry is invalid") from error
    if document.registry_id != REGISTRY_ID or document.registry_version != REGISTRY_VERSION:
        raise PrerequisitesUnavailable("the target registry version is unsupported")
    return LoadedTargetRegistry(
        document=document,
        raw=raw,
        git_blob_sha=REGISTRY_GIT_BLOB_SHA,
        file_sha256=observed,
    )


def _release(
    session: Session, *, tenant_id: uuid.UUID, release_id: str
) -> ReleaseManifest:
    from .release_acceptance import ReferenceNotFound

    row = session.scalars(
        select(ReleaseManifest).where(
            ReleaseManifest.tenant_id == tenant_id,
            ReleaseManifest.release_id == release_id,
        )
    ).one_or_none()
    if row is None:
        raise ReferenceNotFound("release is absent or outside the verified scope")
    return row


def _registry_for_release(release: ReleaseManifest) -> LoadedTargetRegistry:
    from .release_acceptance import PrerequisitesUnavailable

    registry = load_target_registry()
    pins = (
        release.target_registry_version,
        release.target_registry_git_blob_sha,
        release.target_registry_file_sha256,
    )
    if any(value is None for value in pins):
        raise PrerequisitesUnavailable("the release has no target registry pin")
    if (
        release.target_registry_version != REGISTRY_VERSION
        or not hmac.compare_digest(
            str(release.target_registry_git_blob_sha), registry.git_blob_sha
        )
        or not hmac.compare_digest(
            str(release.target_registry_file_sha256), registry.file_sha256
        )
    ):
        raise PrerequisitesUnavailable("the release target registry pin is unavailable")
    loaded_policy = policy.load(
        pinned_sha256=release.policy_registry_sha256,
        pinned_version=release.policy_version,
    )
    if not loaded_policy.usable:
        raise PrerequisitesUnavailable("the release policy registry pin is unavailable")
    return registry


def _read(value: Any, python_name: str, json_name: str) -> Any:
    if isinstance(value, dict):
        return value.get(json_name)
    return getattr(value, python_name, None)


def _normalise_instant(value: Any) -> dt.datetime:
    from .release_acceptance import ReferencesUnresolvable

    if not isinstance(value, dt.datetime) or value.tzinfo is None or value.utcoffset() is None:
        raise ReferencesUnresolvable("measurement time is not timezone-aware")
    return value.astimezone(dt.timezone.utc)


def _targets(registry: LoadedTargetRegistry, refs: list[Any]) -> tuple[str, list[dict[str, Any]]]:
    from .release_acceptance import ReferencesUnresolvable

    if not refs:
        raise ReferencesUnresolvable("no target reference was supplied")
    by_id = {target.target_id: target for target in registry.document.targets}
    resolved: list[dict[str, Any]] = []
    seen: set[str] = set()
    acceptance_refs: set[str] = set()
    for ref in refs:
        target_id = _read(ref, "target_id", "targetId")
        supplied_sha = _read(ref, "target_sha256", "targetSha256")
        target = by_id.get(target_id)
        if target is None or not isinstance(supplied_sha, str):
            raise ReferencesUnresolvable("target reference does not match the registry")
        if target_id in seen or not hmac.compare_digest(target.target_sha256, supplied_sha):
            raise ReferencesUnresolvable("target reference does not match the registry")
        seen.add(target_id)
        acceptance_refs.add(target.acceptance_id_ref)
        resolved.append(
            {
                "targetId": target.target_id,
                "targetVersion": target.target_version,
                "acceptanceIdRef": target.acceptance_id_ref,
                "targetSha256": target.target_sha256,
            }
        )
    if len(acceptance_refs) != 1:
        raise ReferencesUnresolvable("target references span more than one criterion")
    return next(iter(acceptance_refs)), resolved


def _measurement_row(
    session: Session,
    *,
    tenant_id: uuid.UUID,
    release_id: str,
    evidence_id: str,
    observed_at: dt.datetime,
) -> tuple[ReleaseEvidenceBinding, EvidenceEnvelope]:
    from .release_acceptance import ReferenceNotFound, PrerequisitesUnavailable

    row = session.execute(
        select(ReleaseEvidenceBinding, EvidenceEnvelope)
        .join(
            EvidenceEnvelope,
            and_(
                EvidenceEnvelope.evidence_id == ReleaseEvidenceBinding.evidence_id,
                EvidenceEnvelope.recorded_at
                == ReleaseEvidenceBinding.evidence_recorded_at,
                EvidenceEnvelope.tenant_id == ReleaseEvidenceBinding.tenant_id,
            ),
        )
        .join(
            Run,
            and_(
                Run.tenant_id == EvidenceEnvelope.tenant_id,
                Run.run_id == EvidenceEnvelope.run_id,
            ),
        )
        .join(
            Workload,
            and_(
                Workload.tenant_id == Run.tenant_id,
                Workload.workload_id == Run.workload_id,
                Workload.project_id == ReleaseEvidenceBinding.project_id,
            ),
        )
        .where(
            ReleaseEvidenceBinding.tenant_id == tenant_id,
            ReleaseEvidenceBinding.release_id == release_id,
            ReleaseEvidenceBinding.evidence_id == evidence_id,
            ReleaseEvidenceBinding.evidence_recorded_at == observed_at,
        )
    ).one_or_none()
    if row is None:
        raise ReferenceNotFound("Evidence is absent or outside the verified scope")
    binding, evidence = row
    if evidence.envelope_sha256 is None:
        raise PrerequisitesUnavailable("legacy Evidence has no canonical envelope digest")
    if not hmac.compare_digest(str(binding.envelope_sha256), str(evidence.envelope_sha256)):
        raise PrerequisitesUnavailable("the stored Evidence binding is inconsistent")
    return binding, evidence


@dataclass(frozen=True)
class DatabaseReferenceResolver:
    """Resolve every reference or raise; a partial response does not exist."""

    bound: bool = True

    def resolve(
        self,
        session: Session,
        *,
        tenant_id: uuid.UUID,
        release_id: str,
        target_refs: list[Any],
        measurement_refs: list[Any],
    ) -> Any:
        from ..api.schemas import ReleaseAcceptanceReferenceResolutionResponse
        from .release_acceptance import ReferencesUnresolvable

        try:
            release = _release(session, tenant_id=tenant_id, release_id=release_id)
            registry = _registry_for_release(release)
            acceptance_id_ref, targets = _targets(registry, target_refs)
            if not measurement_refs:
                raise ReferencesUnresolvable("no measurement reference was supplied")
            measurements: list[dict[str, Any]] = []
            seen: set[str] = set()
            for ref in measurement_refs:
                evidence_id = _read(ref, "evidence_id", "evidenceId")
                supplied_sha = _read(ref, "evidence_sha256", "evidenceSha256")
                observed_at = _normalise_instant(_read(ref, "observed_at", "observedAt"))
                if not isinstance(evidence_id, str) or not isinstance(supplied_sha, str):
                    raise ReferencesUnresolvable("measurement reference is malformed")
                if evidence_id in seen:
                    raise ReferencesUnresolvable("measurement reference is duplicated")
                seen.add(evidence_id)
                _binding, evidence = _measurement_row(
                    session,
                    tenant_id=tenant_id,
                    release_id=release_id,
                    evidence_id=evidence_id,
                    observed_at=observed_at,
                )
                if not hmac.compare_digest(str(evidence.envelope_sha256), supplied_sha):
                    raise ReferencesUnresolvable("measurement digest does not match Evidence")
                measurements.append(
                    {
                        "evidenceId": evidence.evidence_id,
                        "evidenceSha256": evidence.envelope_sha256,
                        "observedAt": evidence.recorded_at,
                    }
                )
        except OperationalError as error:
            _retryable(error)
        return ReleaseAcceptanceReferenceResolutionResponse.model_validate(
            {
                "schemaVersion": "release-acceptance-reference-resolution:1",
                "releaseId": release_id,
                "acceptanceIdRef": acceptance_id_ref,
                "policyRegistryVersion": release.policy_version,
                "policyRegistrySha256": release.policy_registry_sha256,
                "targetRegistryId": REGISTRY_ID,
                "targetRegistryVersion": registry.document.registry_version,
                "targetRegistryGitBlobSha": registry.git_blob_sha,
                "targetRegistryFileSha256": registry.file_sha256,
                "targets": targets,
                "measurements": measurements,
                "scopeVerified": True,
                "allResolved": True,
            }
        )


RESOLVER = DatabaseReferenceResolver()


def bind_evidence(
    session: Session,
    *,
    tenant_id: uuid.UUID,
    release_id: str,
    evidence_id: str,
    observed_at: dt.datetime,
    now: dt.datetime,
) -> ReleaseEvidenceBinding:
    """Bind one stored Evidence row; no public generic binding route exists."""

    from .release_acceptance import ReferenceNotFound, PrerequisitesUnavailable

    release = _release(session, tenant_id=tenant_id, release_id=release_id)
    _registry_for_release(release)
    observed_at = _normalise_instant(observed_at)
    row = session.execute(
        select(EvidenceEnvelope, Workload.project_id)
        .join(
            Run,
            and_(Run.tenant_id == EvidenceEnvelope.tenant_id, Run.run_id == EvidenceEnvelope.run_id),
        )
        .join(
            Workload,
            and_(Workload.tenant_id == Run.tenant_id, Workload.workload_id == Run.workload_id),
        )
        .where(
            EvidenceEnvelope.tenant_id == tenant_id,
            EvidenceEnvelope.evidence_id == evidence_id,
            EvidenceEnvelope.recorded_at == observed_at,
        )
    ).one_or_none()
    if row is None:
        raise ReferenceNotFound("Evidence is absent or outside the verified scope")
    evidence, project_id = row
    if evidence.envelope_sha256 is None:
        raise PrerequisitesUnavailable("legacy Evidence has no canonical envelope digest")
    binding = ReleaseEvidenceBinding(
        tenant_id=tenant_id,
        release_id=release_id,
        evidence_id=evidence_id,
        evidence_recorded_at=observed_at,
        project_id=project_id,
        envelope_sha256=evidence.envelope_sha256,
        bound_at=now,
    )
    session.add(binding)
    session.flush()
    return binding


def _encode_cursor(recorded_at: dt.datetime, evidence_id: str) -> str:
    payload = json.dumps(
        {"recordedAt": recorded_at.astimezone(dt.timezone.utc).isoformat(), "evidenceId": evidence_id},
        separators=(",", ":"),
        sort_keys=True,
    ).encode("utf-8")
    return base64.urlsafe_b64encode(payload).decode("ascii").rstrip("=")


def _decode_cursor(value: str | None) -> tuple[dt.datetime, str] | None:
    from .release_acceptance import ReferencesUnresolvable

    if value is None:
        return None
    try:
        raw = base64.urlsafe_b64decode(value + "=" * (-len(value) % 4))
        document = json.loads(raw.decode("utf-8"))
        if set(document) != {"recordedAt", "evidenceId"}:
            raise ValueError
        instant = dt.datetime.fromisoformat(document["recordedAt"])
        evidence_id = document["evidenceId"]
        if instant.tzinfo is None or not isinstance(evidence_id, str) or not evidence_id:
            raise ValueError
        return instant.astimezone(dt.timezone.utc), evidence_id
    except (UnicodeError, ValueError, TypeError, json.JSONDecodeError) as error:
        raise ReferencesUnresolvable("discovery cursor is invalid") from error


def discovery_page(
    session: Session,
    *,
    tenant_id: uuid.UUID,
    release_id: str,
    acceptance_id_ref: str,
    limit: int,
    cursor: str | None,
) -> Any:
    """Return only identities already bound by the server, never raw Evidence."""

    from ..api.schemas import ReleaseAcceptanceEvidenceDiscoveryPageResponse
    from .release_acceptance import ReferenceNotFound, ReferencesUnresolvable

    if not 1 <= limit <= DISCOVERY_PAGE_MAX:
        raise ReferencesUnresolvable("discovery limit is outside the contract")
    release = _release(session, tenant_id=tenant_id, release_id=release_id)
    registry = _registry_for_release(release)
    targets = [
        target
        for target in registry.document.targets
        if target.acceptance_id_ref == acceptance_id_ref
    ]
    if not targets:
        raise ReferenceNotFound("criterion is absent from the target registry")
    loaded_policy = policy.load(
        pinned_sha256=release.policy_registry_sha256,
        pinned_version=release.policy_version,
    )
    required = next(
        (item for item in loaded_policy.required_criteria if item.acceptance_id_ref == acceptance_id_ref),
        None,
    )
    if required is None or required.target_registry_ref != REGISTRY_ID:
        raise ReferenceNotFound("criterion is absent from the release policy")

    query = select(ReleaseEvidenceBinding).where(
        ReleaseEvidenceBinding.tenant_id == tenant_id,
        ReleaseEvidenceBinding.release_id == release_id,
    )
    decoded = _decode_cursor(cursor)
    if decoded is not None:
        instant, evidence_id = decoded
        query = query.where(
            or_(
                ReleaseEvidenceBinding.evidence_recorded_at < instant,
                and_(
                    ReleaseEvidenceBinding.evidence_recorded_at == instant,
                    ReleaseEvidenceBinding.evidence_id < evidence_id,
                ),
            )
        )
    try:
        rows = session.scalars(
            query.order_by(
                desc(ReleaseEvidenceBinding.evidence_recorded_at),
                desc(ReleaseEvidenceBinding.evidence_id),
            ).limit(limit + 1)
        ).all()
    except OperationalError as error:
        _retryable(error)
    if not rows:
        raise ReferenceNotFound("no bound Evidence is available in this scope")
    page = rows[:limit]
    verified_items: list[dict[str, Any]] = []
    try:
        for row in page:
            _binding, evidence = _measurement_row(
                session,
                tenant_id=tenant_id,
                release_id=release_id,
                evidence_id=row.evidence_id,
                observed_at=row.evidence_recorded_at,
            )
            verified_items.append(
                {
                    "evidenceId": evidence.evidence_id,
                    "evidenceSha256": evidence.envelope_sha256,
                    "observedAt": evidence.recorded_at,
                }
            )
    except OperationalError as error:
        _retryable(error)
    next_cursor = (
        _encode_cursor(page[-1].evidence_recorded_at, page[-1].evidence_id)
        if len(rows) > limit
        else None
    )
    return ReleaseAcceptanceEvidenceDiscoveryPageResponse.model_validate(
        {
            "schemaVersion": "release-acceptance-evidence-discovery-page:1",
            "releaseId": release_id,
            "acceptanceIdRef": acceptance_id_ref,
            "policyRegistryVersion": release.policy_version,
            "policyRegistrySha256": release.policy_registry_sha256,
            "targetRegistryVersion": registry.document.registry_version,
            "targetRegistryGitBlobSha": registry.git_blob_sha,
            "targetRegistryFileSha256": registry.file_sha256,
            "targets": [
                {
                    "targetId": target.target_id,
                    "targetVersion": target.target_version,
                    "acceptanceIdRef": target.acceptance_id_ref,
                    "targetSha256": target.target_sha256,
                }
                for target in targets
            ],
            "items": verified_items,
            "nextCursor": next_cursor,
            "scopeVerified": True,
        }
    )
