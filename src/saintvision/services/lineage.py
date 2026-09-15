"""Lineage recording and the AC-10 traceback (S10-DB, S10-ST).

AC-10: "모델의 데이터·코드·평가·승인 역추적". :func:`trace_model` is that
sentence as a function — given a model version, return the datasets, the
commit, the image, the evaluation and the approval it came from, and say
plainly which of those are **missing**.

Reporting the gaps is the part that matters. A traceback that returns only what
it found looks complete for a model nobody recorded anything about.
"""

from __future__ import annotations

import datetime as dt
import re
import uuid
from dataclasses import dataclass
from typing import Any

from sqlalchemy import select, update
from sqlalchemy.orm import Session

from ..db.models import (
    Approval,
    CodeCommit,
    ContainerImage,
    Dataset,
    DatasetVersion,
    Deployment,
    EvalRun,
    Model,
    ModelLineage,
    ModelVersion,
)
from ..errors import (
    AUTH_APPROVAL_DIGEST_MISMATCH,
    RES_ARTIFACT_NOT_FOUND,
    VAL_SCHEMA,
    InvError,
)
from ..ids import new_id

_SHA256 = re.compile(r"^[0-9a-f]{64}$")
_OCI_DIGEST = re.compile(r"^sha256:[0-9a-f]{64}$")
_COMMIT_SHA = re.compile(r"^[0-9a-f]{40}$|^[0-9a-f]{64}$")

#: The kinds AC-10 requires. A model missing any of these is traceable only in
#: part, and :func:`trace_model` says which.
REQUIRED_KINDS: tuple[str, ...] = (
    "dataset_version",
    "code_commit",
    "eval_run",
    "approval",
)


@dataclass(frozen=True, slots=True)
class LineageEdge:
    kind: str
    subject_id: str
    relation: str = "derived_from"


def register_dataset_version(
    session: Session,
    *,
    tenant_id: uuid.UUID,
    dataset_id: str,
    version: str,
    content_sha256: str,
    uri: str,
    now: dt.datetime,
    byte_size: int = 0,
    record_count: int = 0,
    retention_pinned_until: dt.datetime | None = None,
) -> DatasetVersion:
    if not _SHA256.match(content_sha256 or ""):
        raise InvError(VAL_SCHEMA, "content_sha256 must be a lowercase hex SHA-256")
    dataset = session.get(Dataset, dataset_id)
    if dataset is None or dataset.tenant_id != tenant_id:
        raise InvError(RES_ARTIFACT_NOT_FOUND, "dataset not found")

    row = DatasetVersion(
        dataset_version_id=new_id("dataset_version"),
        tenant_id=tenant_id,
        dataset_id=dataset_id,
        version=version,
        content_sha256=content_sha256,
        byte_size=byte_size,
        record_count=record_count,
        uri=uri,
        retention_pinned_until=retention_pinned_until,
        created_at=now,
    )
    session.add(row)
    session.flush()
    return row


def register_commit(
    session: Session,
    *,
    tenant_id: uuid.UUID,
    repository: str,
    commit_sha: str,
    now: dt.datetime,
    ref: str | None = None,
    dirty: bool = False,
) -> CodeCommit:
    """Record the code. ``dirty`` is kept, not rejected.

    A build from an uncommitted tree is a real thing that happens; recording it
    honestly is more useful than refusing it and having someone record a clean
    SHA that does not describe what ran.
    """
    if not _COMMIT_SHA.match(commit_sha or ""):
        raise InvError(VAL_SCHEMA, "commit_sha must be a 40 or 64 character hex SHA")

    existing = session.scalar(
        select(CodeCommit).where(
            CodeCommit.tenant_id == tenant_id,
            CodeCommit.repository == repository,
            CodeCommit.commit_sha == commit_sha,
        )
    )
    if existing is not None:
        return existing

    row = CodeCommit(
        commit_id=new_id("commit"),
        tenant_id=tenant_id,
        repository=repository,
        commit_sha=commit_sha,
        ref=ref,
        dirty=dirty,
        recorded_at=now,
    )
    session.add(row)
    session.flush()
    return row


def register_image(
    session: Session,
    *,
    tenant_id: uuid.UUID,
    repository: str,
    digest: str,
    now: dt.datetime,
    tag: str | None = None,
    byte_size: int = 0,
) -> ContainerImage:
    """Record an image by digest.

    The tag is stored and is never the identity: ``app:latest`` resolves to
    something different next week, and a lineage row keyed on it would look
    precise while pointing at whatever is current.
    """
    if not _OCI_DIGEST.match(digest or ""):
        raise InvError(VAL_SCHEMA, "digest must look like sha256:<64 hex>")

    existing = session.scalar(
        select(ContainerImage).where(
            ContainerImage.tenant_id == tenant_id, ContainerImage.digest == digest
        )
    )
    if existing is not None:
        return existing

    row = ContainerImage(
        image_id=new_id("image"),
        tenant_id=tenant_id,
        repository=repository,
        digest=digest,
        tag=tag,
        byte_size=byte_size,
        recorded_at=now,
    )
    session.add(row)
    session.flush()
    return row


def register_model_version(
    session: Session,
    *,
    tenant_id: uuid.UUID,
    model_id: str,
    version: str,
    content_sha256: str,
    uri: str,
    now: dt.datetime,
    byte_size: int = 0,
    produced_by_run_id: str | None = None,
    lineage: list[LineageEdge] | None = None,
) -> ModelVersion:
    """Record a model build and where it came from.

    Created as ``draft``. Releasing is a separate, checked step — see
    :func:`release_model_version`.
    """
    if not _SHA256.match(content_sha256 or ""):
        raise InvError(VAL_SCHEMA, "content_sha256 must be a lowercase hex SHA-256")
    model = session.get(Model, model_id)
    if model is None or model.tenant_id != tenant_id:
        raise InvError(RES_ARTIFACT_NOT_FOUND, "model not found")

    row = ModelVersion(
        model_version_id=new_id("model_version"),
        tenant_id=tenant_id,
        model_id=model_id,
        version=version,
        stage="draft",
        content_sha256=content_sha256,
        byte_size=byte_size,
        uri=uri,
        produced_by_run_id=produced_by_run_id,
        created_at=now,
    )
    session.add(row)
    session.flush()

    for edge in lineage or []:
        record_lineage(
            session,
            tenant_id=tenant_id,
            model_version_id=row.model_version_id,
            edge=edge,
            now=now,
        )
    session.flush()
    return row


def record_lineage(
    session: Session,
    *,
    tenant_id: uuid.UUID,
    model_version_id: str,
    edge: LineageEdge,
    now: dt.datetime,
) -> ModelLineage:
    if edge.kind not in (
        "dataset_version",
        "code_commit",
        "container_image",
        "eval_run",
        "approval",
    ):
        raise InvError(VAL_SCHEMA, f"unknown lineage kind: {edge.kind!r}")

    existing = session.get(
        ModelLineage, (tenant_id, model_version_id, edge.kind, edge.subject_id)
    )
    if existing is not None:
        return existing

    row = ModelLineage(
        tenant_id=tenant_id,
        model_version_id=model_version_id,
        kind=edge.kind,
        subject_id=edge.subject_id,
        relation=edge.relation,
        recorded_at=now,
    )
    session.add(row)
    session.flush()
    return row


def verify_model_version(
    session: Session,
    *,
    tenant_id: uuid.UUID,
    model_version_id: str,
    content_sha256: str,
    now: dt.datetime,
) -> ModelVersion:
    """Record that a trusted worker hashed the actual weights (ADR-011)."""
    row = _load_model_version(session, tenant_id=tenant_id, model_version_id=model_version_id)
    if row.content_sha256 != content_sha256:
        raise InvError(
            VAL_SCHEMA,
            "the computed checksum does not match the recorded one",
            cause_ref=model_version_id,
        )
    row.verified_at = now
    session.flush()
    return row


def pin_retention(
    session: Session, *, tenant_id: uuid.UUID, model_version_id: str, until: dt.datetime
) -> ModelVersion:
    """Extend the retention pin. Never shortens it.

    Datasets and models are retained manually (PLAN-STORAGE-001); a later,
    weaker claim must not release something an earlier one held.
    """
    row = _load_model_version(session, tenant_id=tenant_id, model_version_id=model_version_id)
    current = row.retention_pinned_until
    if current is None or until > current:
        row.retention_pinned_until = until
        session.flush()
    return row


def release_model_version(
    session: Session,
    *,
    tenant_id: uuid.UUID,
    model_version_id: str,
    now: dt.datetime,
) -> ModelVersion:
    """Move a version to ``released``.

    Refuses unless it is verified, pinned, and traceable. The database enforces
    the first two; the third is checked here, because "released" is the point
    at which someone may deploy it and the lineage is what makes that
    defensible (AC-10).
    """
    row = _load_model_version(session, tenant_id=tenant_id, model_version_id=model_version_id)
    if row.verified_at is None:
        raise InvError(VAL_SCHEMA, "an unverified model version cannot be released")
    if row.retention_pinned_until is None:
        raise InvError(VAL_SCHEMA, "a model version must be retention pinned before release")

    trace = trace_model(session, tenant_id=tenant_id, model_version_id=model_version_id)
    if trace["missing"]:
        raise InvError(
            VAL_SCHEMA,
            "model version is not fully traceable: missing "
            + ", ".join(trace["missing"]),
            cause_ref=model_version_id,
            extra={"missing": trace["missing"]},
        )

    row.stage = "released"
    session.flush()
    return row


def trace_model(
    session: Session, *, tenant_id: uuid.UUID, model_version_id: str
) -> dict[str, Any]:
    """AC-10's traceback: data, code, evaluation and approval for one model.

    Reports what is **missing** alongside what was found. A traceback that
    returned only its hits would look complete for a model nobody recorded
    anything about, which is precisely the case worth catching.
    """
    version = _load_model_version(session, tenant_id=tenant_id, model_version_id=model_version_id)
    edges = list(
        session.scalars(
            select(ModelLineage).where(
                ModelLineage.tenant_id == tenant_id,
                ModelLineage.model_version_id == model_version_id,
            )
        ).all()
    )
    by_kind: dict[str, list[str]] = {}
    for edge in edges:
        by_kind.setdefault(edge.kind, []).append(edge.subject_id)

    datasets = [
        {
            "datasetVersionId": row.dataset_version_id,
            "version": row.version,
            "contentSha256": row.content_sha256,
            "uri": row.uri,
        }
        for row in _load_all(session, DatasetVersion, DatasetVersion.dataset_version_id,
                             tenant_id, by_kind.get("dataset_version", []))
    ]
    commits = [
        {
            "commitId": row.commit_id,
            "repository": row.repository,
            "commitSha": row.commit_sha,
            "dirty": row.dirty,
        }
        for row in _load_all(session, CodeCommit, CodeCommit.commit_id,
                             tenant_id, by_kind.get("code_commit", []))
    ]
    images = [
        {"imageId": row.image_id, "repository": row.repository, "digest": row.digest}
        for row in _load_all(session, ContainerImage, ContainerImage.image_id,
                             tenant_id, by_kind.get("container_image", []))
    ]
    evaluations = [
        {
            "evalRunId": row.eval_run_id,
            "passedGate": row.passed_gate,
            "violations": row.violations,
            "passedCases": row.passed_cases,
            "totalCases": row.total_cases,
        }
        for row in _load_all(session, EvalRun, EvalRun.eval_run_id,
                             tenant_id, by_kind.get("eval_run", []))
    ]
    approvals = [
        {
            "approvalId": row.approval_id,
            "decision": row.decision,
            "riskLevel": row.risk_level,
            "subjectSha256": row.subject_sha256,
        }
        for row in _load_all(session, Approval, Approval.approval_id,
                             tenant_id, by_kind.get("approval", []))
    ]

    found = {
        "dataset_version": datasets,
        "code_commit": commits,
        "container_image": images,
        "eval_run": evaluations,
        "approval": approvals,
    }
    missing = [kind for kind in REQUIRED_KINDS if not found[kind]]

    # A recorded edge whose subject row is gone is worse than a missing edge:
    # the trace claims a link it cannot substantiate.
    dangling = [
        {"kind": kind, "subjectId": subject}
        for kind, subjects in by_kind.items()
        for subject in subjects
        if subject not in {
            item.get("datasetVersionId")
            or item.get("commitId")
            or item.get("imageId")
            or item.get("evalRunId")
            or item.get("approvalId")
            for item in found.get(kind, [])
        }
    ]

    return {
        "modelVersionId": version.model_version_id,
        "version": version.version,
        "stage": version.stage,
        "contentSha256": version.content_sha256,
        "producedByRunId": version.produced_by_run_id,
        "datasets": datasets,
        "commits": commits,
        "images": images,
        "evaluations": evaluations,
        "approvals": approvals,
        "missing": missing,
        "dangling": dangling,
        "fullyTraceable": not missing and not dangling,
    }


def record_deployment(
    session: Session,
    *,
    tenant_id: uuid.UUID,
    model_version_id: str,
    environment: str,
    approval_id: str,
    deployed_by_user_id: str,
    now: dt.datetime,
    image_id: str | None = None,
    notes: dict[str, Any] | None = None,
) -> Deployment:
    """Deploy a released version, pinning the digest that actually shipped.

    The digest comes from the model version, not the caller, and the approval
    is checked against it. Approving one build does not authorise shipping a
    different one under the same version name — the same rule the workload
    spec digest enforces in S03.

    An existing active deployment of this version in this environment is marked
    superseded in the same transaction, so "what is live" is never ambiguous.

    This records registry metadata at the trusted caller's timezone-aware
    ``now``; it does not perform deployment or issue a kernel execution permit.
    Approval validity is the half-open interval [decided_at, expires_at).
    """
    if environment not in ("lab", "staging", "pilot"):
        raise InvError(VAL_SCHEMA, f"unknown environment: {environment!r}")

    # The version exists even when no deployment does: lock it before looking
    # for a previous active record, serializing concurrent first registrations.
    # Refresh ORM identities so earlier reads cannot preserve stale authority.
    version = session.scalar(
        select(ModelVersion).where(
            ModelVersion.tenant_id == tenant_id,
            ModelVersion.model_version_id == model_version_id,
        ).with_for_update().execution_options(populate_existing=True)
    )
    if version is None:
        raise InvError(RES_ARTIFACT_NOT_FOUND, "model version not found")
    if version.stage != "released":
        raise InvError(
            VAL_SCHEMA,
            f"only a released model version can be deployed, not one in {version.stage}",
            cause_ref=model_version_id,
        )

    approval = session.scalar(
        select(Approval).where(
            Approval.tenant_id == tenant_id, Approval.approval_id == approval_id,
        ).with_for_update(read=True).execution_options(populate_existing=True)
    )
    if approval is None or approval.tenant_id != tenant_id:
        raise InvError(AUTH_APPROVAL_DIGEST_MISMATCH, "approval not found")
    if approval.decision != "approved":
        raise InvError(AUTH_APPROVAL_DIGEST_MISMATCH, "the recorded decision is not an approval")
    if not approval.decided_at <= now < approval.expires_at:
        raise InvError(AUTH_APPROVAL_DIGEST_MISMATCH, "approval is not valid at the recorded deployment time")
    if approval.subject_sha256 != version.content_sha256:
        raise InvError(
            AUTH_APPROVAL_DIGEST_MISMATCH,
            "the approval was given for different content than this model version",
            cause_ref=approval_id,
        )

    session.execute(
        update(Deployment).where(
            Deployment.tenant_id == tenant_id,
            Deployment.model_version_id == model_version_id,
            Deployment.environment == environment,
            Deployment.status == "active",
        ).values(status="superseded", superseded_at=now)
    )

    deployment = Deployment(
        deployment_id=new_id("deployment"),
        tenant_id=tenant_id,
        model_version_id=model_version_id,
        environment=environment,
        status="active",
        deployed_digest=version.content_sha256,
        image_id=image_id,
        approval_id=approval_id,
        deployed_by_user_id=deployed_by_user_id,
        deployed_at=now,
        notes=notes or {},
    )
    session.add(deployment)
    session.flush()
    return deployment


def _load_model_version(
    session: Session, *, tenant_id: uuid.UUID, model_version_id: str
) -> ModelVersion:
    row = session.get(ModelVersion, model_version_id)
    if row is None or row.tenant_id != tenant_id:
        raise InvError(RES_ARTIFACT_NOT_FOUND, "model version not found")
    return row


def _load_all(session: Session, entity, id_column, tenant_id: uuid.UUID, ids: list[str]):
    if not ids:
        return []
    return list(
        session.scalars(
            select(entity).where(entity.tenant_id == tenant_id, id_column.in_(ids))
        ).all()
    )
