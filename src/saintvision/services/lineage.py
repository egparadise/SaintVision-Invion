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

from sqlalchemy import func, select, text, update
from sqlalchemy.orm import Session

from ..db.models import (
    Approval,
    CodeCommit,
    ContainerImage,
    Dataset,
    DatasetVersion,
    Deployment,
    EvalRun,
    EvalSuite,
    Model,
    ModelLineage,
    ModelVersion,
    Run,
    Workload,
)
from ..errors import (
    AUTH_APPROVAL_DIGEST_MISMATCH,
    RES_ARTIFACT_NOT_FOUND,
    VAL_SCHEMA,
    InvError,
)
from ..ids import new_id
from .pagination import build_page
from .tracking import (
    deployment_mirror_payload,
    enqueue_mirror,
    model_version_mirror_payload,
    release_mirror_payload,
)

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
    # Mirror intent in the same transaction (design #168 §2). Absent or
    # invalid configuration records nothing; the version is registered either way.
    enqueue_mirror(
        session,
        tenant_id=tenant_id,
        subject_kind="model_version",
        subject_id=row.model_version_id,
        project_id=model.project_id,
        payload=model_version_mirror_payload(row, model_name=model.name, now=now),
        now=now,
    )
    return row


#: The row each lineage kind points at, and the column that identifies it. One
#: table per kind, so "does the subject exist" is one lookup rather than five
#: branches at every call site (card 257 §4-2).
SUBJECT_TABLES: dict[str, tuple[Any, str]] = {
    "dataset_version": (DatasetVersion, "dataset_version_id"),
    "code_commit": (CodeCommit, "commit_id"),
    "container_image": (ContainerImage, "image_id"),
    "eval_run": (EvalRun, "eval_run_id"),
    "approval": (Approval, "approval_id"),
}


def subject_exists(session: Session, *, tenant_id: uuid.UUID, kind: str, subject_id: str):
    """The subject row, in this tenant, or the one refusal absence gets.

    An edge whose subject is not there is worse than a missing edge -- the trace
    then claims a link it cannot substantiate, which is why ``trace_model``
    reports ``dangling`` at all. Checking at write time is cheaper than reporting
    it forever, and it is checked **here** rather than at a route so that every
    caller of :func:`record_lineage` gets the same rule.

    Absence and another tenant's row are **one refusal**: distinguishing them
    would confirm that a subject id exists to someone who cannot see it.
    """
    entity, column = SUBJECT_TABLES[kind]
    row = session.scalar(
        select(entity).where(
            getattr(entity, column) == subject_id, entity.tenant_id == tenant_id
        )
    )
    if row is None:
        raise InvError(RES_ARTIFACT_NOT_FOUND, "lineage subject not found")
    return row


def subject_project(session: Session, *, tenant_id: uuid.UUID, kind: str, subject_id: str) -> str | None:
    """The project a subject can **prove** it belongs to, or ``None``.

    None means "this kind cannot prove a project in the current schema", not
    "any project" -- the caller fails closed on it (card 257 §4-2). The chains
    are the only ones the tables support, and each hop is read in this tenant:

    * ``dataset_version`` -> ``datasets.project_id`` (NOT NULL);
    * ``eval_run`` -> ``eval_suites.project_id`` (**nullable**: an unscoped suite
      proves nothing, so that is ``None`` too);
    * ``approval`` -> ``runs.workload_id`` -> ``workloads.project_id`` (NOT NULL);
    * ``code_commit``, ``container_image`` -> the tables carry no project at all.
    """
    subject = subject_exists(session, tenant_id=tenant_id, kind=kind, subject_id=subject_id)
    if kind == "dataset_version":
        dataset = session.scalar(
            select(Dataset).where(
                Dataset.dataset_id == subject.dataset_id, Dataset.tenant_id == tenant_id
            )
        )
        return dataset.project_id if dataset is not None else None
    if kind == "eval_run":
        suite = session.scalar(
            select(EvalSuite).where(
                EvalSuite.suite_id == subject.suite_id, EvalSuite.tenant_id == tenant_id
            )
        )
        return suite.project_id if suite is not None else None
    if kind == "approval":
        run = session.scalar(
            select(Run).where(Run.run_id == subject.run_id, Run.tenant_id == tenant_id)
        )
        if run is None:
            return None
        workload = session.scalar(
            select(Workload).where(
                Workload.workload_id == run.workload_id, Workload.tenant_id == tenant_id
            )
        )
        return workload.project_id if workload is not None else None
    return None


def record_lineage(
    session: Session,
    *,
    tenant_id: uuid.UUID,
    model_version_id: str,
    edge: LineageEdge,
    now: dt.datetime,
) -> ModelLineage:
    if edge.kind not in SUBJECT_TABLES:
        raise InvError(VAL_SCHEMA, f"unknown lineage kind: {edge.kind!r}")
    subject_exists(session, tenant_id=tenant_id, kind=edge.kind, subject_id=edge.subject_id)

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


#: The measurement a verification binds to, read through the tenant-bound
#: SECURITY DEFINER reader of 0054: the application role has no privilege on
#: the kernel table itself, and the reader takes the tenant from the session's
#: ``inv.tenant_id`` scope, never from an argument.
_MEASUREMENT = text(
    "SELECT model_version_id, sha256, byte_size, observed_at "
    "FROM public.model_version_measurement(:measurement_id)"
)


def verify_model_version(
    session: Session,
    *,
    tenant_id: uuid.UUID,
    model_version_id: str,
    measurement_id: str,
    content_sha256: str,
    now: dt.datetime,
) -> ModelVersion:
    """Record that a trusted worker hashed the actual weights (ADR-011).

    "A trusted worker hashed them" is not a claim the caller may make: it is
    the existence of a signed node measurement (``inv.model_version_measurements``,
    written only by the kernel's accept path) of *this* version whose digest
    is the registered one. ``measurement_id`` is therefore required, and the
    digest the caller passes must agree with both the measurement and the
    row -- a digest alone cannot set ``verified_at`` (design #209 v1.1 §4).
    ``verified_at`` and ``verified_measurement_id`` are set together; the
    database CHECK refuses one without the other. The size is compared exactly
    as the digest is: a registration that recorded 0 bytes is proved only by a
    measurement of 0 bytes.
    """
    row = _load_model_version(session, tenant_id=tenant_id, model_version_id=model_version_id)
    measurement = session.execute(_MEASUREMENT, {"measurement_id": measurement_id}).one_or_none()
    if measurement is None:
        raise InvError(RES_ARTIFACT_NOT_FOUND, "measurement not found", cause_ref=measurement_id)
    if measurement.model_version_id != row.model_version_id:
        raise InvError(
            VAL_SCHEMA, "the measurement belongs to a different model version", cause_ref=measurement_id
        )
    if measurement.sha256 != content_sha256 or row.content_sha256 != content_sha256:
        raise InvError(
            VAL_SCHEMA,
            "the computed checksum does not match the recorded one",
            cause_ref=model_version_id,
        )
    # Always, with no sentinel (Codex #213 F2): a registered size of 0 is a
    # size like any other and must be what the worker measured.
    if int(measurement.byte_size) != int(row.byte_size):
        raise InvError(
            VAL_SCHEMA, "the measured size does not match the recorded one", cause_ref=model_version_id
        )
    if row.verified_at is not None:
        if row.verified_measurement_id == measurement_id:
            return row
        raise InvError(
            VAL_SCHEMA, "the model version is already verified by another measurement", cause_ref=model_version_id
        )
    row.verified_at = now
    row.verified_measurement_id = measurement_id
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
    # The stage transition is its own mirror intent (design #168 §1): the tag
    # ``inv.stage`` moves to ``released`` only because a new intent says so.
    model = session.get(Model, row.model_id)
    enqueue_mirror(
        session,
        tenant_id=tenant_id,
        subject_kind="model_version",
        subject_id=row.model_version_id,
        project_id=model.project_id if model is not None else None,
        payload=release_mirror_payload(row, now=now),
        now=now,
    )
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


@dataclass(frozen=True, slots=True)
class DeploymentAuthority:
    """Everything a deployment write may rest on, read from rows it has locked.

    Produced by :func:`locked_deployment_authority`, consumed by
    :func:`apply_deployment`. The split exists so a caller can re-judge the
    actor's permission **after** the rows are locked and **before** anything is
    written -- the window a single function cannot offer (card 257 §4-3-1).
    """

    version: Any
    approval: Any
    deployed_digest: str
    environment: str


def locked_deployment_authority(
    session: Session,
    *,
    tenant_id: uuid.UUID,
    project_id: str,
    model_version_id: str,
    environment: str,
    approval_id: str,
    now: dt.datetime,
) -> DeploymentAuthority:
    """Lock the rows a deployment depends on and judge them. **Writes nothing.**

    The digest is **not an argument**: it comes from the model version, and the
    approval is checked against it. Approving one build does not authorise
    shipping a different one under the same version name.

    Six failures are **one refusal** (``AUTH_APPROVAL_DIGEST_MISMATCH``): the
    approval is absent, belongs to another tenant, cannot prove this project, is
    not an approval, is outside its validity, or was given for other content.
    Separating them would confirm that an approval id exists to someone who
    cannot see it -- the same oracle rule the lineage subjects follow.

    The project proof is the chain the schema supports: ``approvals.run_id`` ->
    ``runs.workload_id`` -> ``workloads.project_id``. Without it a same-tenant
    approval from another project would authorise this project's deployment,
    because the digest alone does not say whose build it was.
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
    if approval_project(session, tenant_id=tenant_id, approval=approval) != project_id:
        raise InvError(
            AUTH_APPROVAL_DIGEST_MISMATCH,
            "the approval does not belong to this project",
            cause_ref=approval_id,
        )
    return DeploymentAuthority(
        version=version,
        approval=approval,
        deployed_digest=version.content_sha256,
        environment=environment,
    )


def approval_project(session: Session, *, tenant_id: uuid.UUID, approval: Any) -> str | None:
    """The project an approval can prove, through its run's workload, or ``None``.

    ``None`` is "cannot prove", never "any project": every caller refuses on it.
    """
    run = session.scalar(
        select(Run).where(Run.run_id == approval.run_id, Run.tenant_id == tenant_id)
    )
    if run is None:
        return None
    workload = session.scalar(
        select(Workload).where(
            Workload.workload_id == run.workload_id, Workload.tenant_id == tenant_id
        )
    )
    return workload.project_id if workload is not None else None


def apply_deployment(
    session: Session,
    *,
    authority: DeploymentAuthority,
    deployed_by_user_id: str,
    now: dt.datetime,
    image_id: str | None = None,
    notes: dict[str, Any] | None = None,
) -> Deployment:
    """Write the deployment the locked authority permits. **Validates nothing.**

    An existing active deployment of this version in this environment is marked
    superseded in the same transaction, so "what is live" is never ambiguous.

    This records registry metadata at the trusted caller's timezone-aware
    ``now``; it does not perform deployment or issue a kernel execution permit.
    """
    version = authority.version
    tenant_id = version.tenant_id
    session.execute(
        update(Deployment).where(
            Deployment.tenant_id == tenant_id,
            Deployment.model_version_id == version.model_version_id,
            Deployment.environment == authority.environment,
            Deployment.status == "active",
        ).values(status="superseded", superseded_at=now)
    )

    deployment = Deployment(
        deployment_id=new_id("deployment"),
        tenant_id=tenant_id,
        model_version_id=version.model_version_id,
        environment=authority.environment,
        status="active",
        deployed_digest=authority.deployed_digest,
        image_id=image_id,
        approval_id=authority.approval.approval_id,
        deployed_by_user_id=deployed_by_user_id,
        deployed_at=now,
        notes=notes or {},
    )
    session.add(deployment)
    session.flush()
    model = session.get(Model, version.model_id)
    enqueue_mirror(
        session,
        tenant_id=tenant_id,
        subject_kind="deployment",
        subject_id=deployment.deployment_id,
        project_id=model.project_id if model is not None else None,
        payload=deployment_mirror_payload(deployment, now=now),
        now=now,
    )
    return deployment


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
    project_id: str | None = None,
) -> Deployment:
    """Lock, judge and write in one call -- the shape every existing caller uses.

    Kept so the split above is not a breaking change. ``project_id`` is optional
    **only** for callers that already proved the project themselves; when it is
    absent the approval's own chain supplies it, which keeps the old behaviour
    for a caller that has no path project to compare with.
    """
    if project_id is None:
        approval = session.scalar(
            select(Approval).where(
                Approval.tenant_id == tenant_id, Approval.approval_id == approval_id
            )
        )
        if approval is None:
            raise InvError(AUTH_APPROVAL_DIGEST_MISMATCH, "approval not found")
        project_id = approval_project(session, tenant_id=tenant_id, approval=approval)
    authority = locked_deployment_authority(
        session,
        tenant_id=tenant_id,
        project_id=project_id,
        model_version_id=model_version_id,
        environment=environment,
        approval_id=approval_id,
        now=now,
    )
    return apply_deployment(
        session,
        authority=authority,
        deployed_by_user_id=deployed_by_user_id,
        now=now,
        image_id=image_id,
        notes=notes,
    )


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


# --------------------------------------------------------------------------
# Project-scoped reads (S10-DB lineage query API)
# --------------------------------------------------------------------------

#: The most items any lineage array carries. Taken from the ``maximum=200``
#: convention in ``pagination.py`` rather than from a measurement, and recorded
#: as such: whatever is over the bound is reported, never silently dropped.
ARRAY_LIMIT: int = 200

#: Kinds whose detail a project-scoped read may serve, because their ownership
#: is provable -- ``dataset_version`` through ``datasets.project_id``, and
#: ``deployment`` through the model version the path already bound.
DETAILED_KINDS: tuple[str, ...] = ("dataset_version", "deployment")

#: Kinds with no project column anywhere, so a project member cannot be served
#: their detail on the strength of that membership. Counted only.
COUNT_ONLY_KINDS: tuple[str, ...] = (
    "code_commit",
    "container_image",
    "eval_run",
    "approval",
)


def _bounded(rows: list, key: str, truncated: dict[str, int]) -> list:
    """Cut a list to ``ARRAY_LIMIT`` and record what was cut.

    A slice with nothing recorded is the failure this exists to prevent: the
    consumer cannot tell a complete answer from a cut one.
    """
    if len(rows) > ARRAY_LIMIT:
        truncated[key] = len(rows)
        return rows[:ARRAY_LIMIT]
    return rows


def trace_model_for_project(
    session: Session,
    *,
    tenant_id: uuid.UUID,
    project_id: str,
    model_version_id: str,
) -> dict[str, Any]:
    """``trace_model`` reduced to what a project member may be shown.

    Not a filter over :func:`trace_model`: that function loads the detail of all
    five kinds, and a project-scoped read that loaded rows and then dropped them
    would leak the moment a filter went missing, besides putting them within
    reach of a log or a traceback. Here the rows that will not be served are
    never read.

    What a caller cannot be given is reported as a count under ``unresolved``,
    and the three reasons -- the subject row is absent, it belongs to another
    project, or its kind has no project column at all -- are deliberately **not**
    distinguished. Separating them would confirm that a hidden identifier exists
    and belongs to someone else, which is an existence oracle over the tenant.

    ``missing`` stays as it is: it says an edge is absent from *our* model
    version and reveals nothing about anyone else's rows.
    """
    version = _load_model_version(
        session, tenant_id=tenant_id, model_version_id=model_version_id
    )
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

    truncated: dict[str, int] = {}
    unresolved: dict[str, int] = {}

    subjects = by_kind.get("dataset_version", [])
    rows = (
        list(
            session.execute(
                select(DatasetVersion)
                .join(
                    Dataset,
                    (Dataset.tenant_id == DatasetVersion.tenant_id)
                    & (Dataset.dataset_id == DatasetVersion.dataset_id),
                )
                .where(
                    DatasetVersion.tenant_id == tenant_id,
                    DatasetVersion.dataset_version_id.in_(subjects),
                    Dataset.project_id == project_id,
                )
                .order_by(DatasetVersion.dataset_version_id)
            )
            .scalars()
            .all()
        )
        if subjects
        else []
    )
    if len(rows) < len(subjects):
        unresolved["dataset_version"] = len(subjects) - len(rows)
    datasets = [
        {
            "datasetVersionId": row.dataset_version_id,
            "version": row.version,
            "contentSha256": row.content_sha256,
            "uri": row.uri,
        }
        for row in _bounded(rows, "datasets", truncated)
    ]

    for kind in COUNT_ONLY_KINDS:
        count = len(by_kind.get(kind, []))
        if count:
            unresolved[kind] = count

    deployment_rows = list(
        session.scalars(
            select(Deployment)
            .where(
                Deployment.tenant_id == tenant_id,
                Deployment.model_version_id == model_version_id,
            )
            .order_by(Deployment.deployment_id)
        ).all()
    )
    deployments = [
        {
            "deploymentId": row.deployment_id,
            "environment": row.environment,
            "status": row.status,
            "deployedDigest": row.deployed_digest,
            "imageId": row.image_id,
            "approvalId": row.approval_id,
            "deployedAt": row.deployed_at,
            "supersededAt": row.superseded_at,
        }
        for row in _bounded(deployment_rows, "deployments", truncated)
    ]

    missing = [kind for kind in REQUIRED_KINDS if not by_kind.get(kind)]
    unresolved_list = [
        {"kind": kind, "count": unresolved[kind]} for kind in sorted(unresolved)
    ]
    return {
        "modelVersionId": version.model_version_id,
        "version": version.version,
        "stage": version.stage,
        "contentSha256": version.content_sha256,
        "producedByRunId": version.produced_by_run_id,
        "datasets": datasets,
        "deployments": deployments,
        "missing": missing,
        "unresolved": unresolved_list,
        "truncated": truncated,
        "fullyTraceable": not missing and not unresolved_list and not truncated,
        # Says why ``fullyTraceable`` is false. Without it an operator reads that
        # false as a recording gap and goes looking for records to fix, when the
        # cause is this route's permission boundary.
        "traceabilityLimitedByScope": any(
            kind in unresolved for kind in COUNT_ONLY_KINDS
        ),
        "detailedKinds": list(DETAILED_KINDS),
        "countOnlyKinds": list(COUNT_ONLY_KINDS),
    }


def models_from_dataset_digest(
    session: Session,
    *,
    tenant_id: uuid.UUID,
    project_id: str,
    content_sha256: str,
    limit: int,
    cursor: str | None = None,
) -> dict[str, Any]:
    """Which model versions were built from the bytes with this digest.

    The reverse of a traceback, and the question #144/#146 found no way to ask.

    Two invariants live in the SQL rather than in prose. The dataset-version set
    is bounded first and the ``IN`` list is *exactly* that bounded set, so every
    item can be traced back to a listed dataset version; and the distinct is
    taken on ``model_version_id`` **before** the cursor and the limit, because
    several dataset versions can converge on one model version and paginating the
    pre-distinct rows duplicates items and loses others at the page edge.
    """
    if not _SHA256.match(content_sha256):
        raise InvError(VAL_SCHEMA, "content digest must be 64 lowercase hex characters")

    truncated: dict[str, int] = {}
    dataset_versions = list(
        session.execute(
            select(DatasetVersion.dataset_version_id)
            .join(
                Dataset,
                (Dataset.tenant_id == DatasetVersion.tenant_id)
                & (Dataset.dataset_id == DatasetVersion.dataset_id),
            )
            .where(
                DatasetVersion.tenant_id == tenant_id,
                DatasetVersion.content_sha256 == content_sha256,
                Dataset.project_id == project_id,
            )
            .order_by(DatasetVersion.dataset_version_id)
        )
        .scalars()
        .all()
    )
    if not dataset_versions:
        # Absent, another project's and another tenant's are one answer.
        raise InvError(RES_ARTIFACT_NOT_FOUND, "dataset version not found")
    dataset_versions = _bounded(dataset_versions, "datasetVersionIds", truncated)

    wanted = sorted(
        set(
            session.execute(
                select(ModelLineage.model_version_id).where(
                    ModelLineage.tenant_id == tenant_id,
                    ModelLineage.kind == "dataset_version",
                    ModelLineage.subject_id.in_(dataset_versions),
                )
            )
            .scalars()
            .all()
        )
    )

    rows: list = []
    resolvable = 0
    if wanted:
        in_project = (
            select(ModelVersion.model_version_id)
            .join(
                Model,
                (Model.tenant_id == ModelVersion.tenant_id)
                & (Model.model_id == ModelVersion.model_id),
            )
            .where(
                ModelVersion.tenant_id == tenant_id,
                ModelVersion.model_version_id.in_(wanted),
                Model.project_id == project_id,
            )
            .distinct()
        )
        # Counted over the whole wanted set rather than over this page, so the
        # number means the same thing on page one and page four.
        resolvable = int(
            session.execute(
                select(func.count()).select_from(in_project.subquery())
            ).scalar_one()
        )
        statement = (
            select(ModelVersion)
            .join(
                Model,
                (Model.tenant_id == ModelVersion.tenant_id)
                & (Model.model_id == ModelVersion.model_id),
            )
            .where(
                ModelVersion.tenant_id == tenant_id,
                ModelVersion.model_version_id.in_(wanted),
                Model.project_id == project_id,
            )
            .distinct()
            .order_by(ModelVersion.model_version_id)
        )
        if cursor is not None:
            statement = statement.where(ModelVersion.model_version_id > cursor)
        rows = list(session.execute(statement.limit(limit + 1)).scalars().all())
    page = build_page(rows, limit=limit, id_attr="model_version_id")
    # One number for "belongs to another project" and for "no such row": telling
    # them apart is the same oracle ``unresolved`` closes on the forward side.
    unresolved_model_versions = len(wanted) - resolvable
    return {
        "contentSha256": content_sha256,
        "datasetVersionIds": list(dataset_versions),
        "items": [
            {
                "modelVersionId": row.model_version_id,
                "modelId": row.model_id,
                "version": row.version,
                "stage": row.stage,
                "contentSha256": row.content_sha256,
            }
            for row in page.items
        ],
        "nextCursor": page.next_cursor,
        "unresolvedModelVersions": max(unresolved_model_versions, 0),
        "truncated": truncated,
        "complete": not truncated and unresolved_model_versions <= 0,
    }
