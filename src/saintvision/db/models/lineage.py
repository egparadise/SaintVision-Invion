"""Dataset, commit, image and model lineage (S10-DB, S10-ST).

AC-10 asks that a model be traceable back to its data, code, evaluation and
approval. That is only answerable if every one of those is pinned by something
immutable, so the identity rules here are strict:

* **A container image is its digest, not its tag.** ``app:latest`` is a
  different image every week. Storing the tag as identity would make a lineage
  record that reads correctly and means nothing.
* **A dataset version and a model version are immutable once released.** They
  carry a checksum and the application role cannot update or delete them.
* **A deployment records the digest that was deployed**, and the approval binds
  to that digest — the same rule as the workload spec in S03. An approval for
  one artifact does not carry over to another.

Datasets and models are retained manually (PLAN-STORAGE-001): they are outside
the 90 day artifact lifetime, and ``retention_pinned_until`` only ever extends.
"""

from __future__ import annotations

from sqlalchemy import (
    BigInteger,
    CheckConstraint,
    ForeignKeyConstraint,
    Index,
    Integer,
    String,
    Text,
    UniqueConstraint,
    text,
)
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column

from ..base import Base, InvId, Sha256, TenantId, Utc

DEPLOYMENT_ENVIRONMENTS = ("lab", "staging", "pilot")
DEPLOYMENT_STATUSES = ("pending", "active", "superseded", "rolled_back", "failed")
LINEAGE_KINDS = ("dataset_version", "code_commit", "container_image", "eval_run", "approval")


class Dataset(Base):
    """A named dataset. Versions carry the content; this carries the name."""

    __tablename__ = "datasets"
    __table_args__ = (
        ForeignKeyConstraint(
            ["tenant_id", "project_id"],
            ["projects.tenant_id", "projects.project_id"],
        ),
        UniqueConstraint("tenant_id", "dataset_id", name="uq_datasets_tenant_id_dataset_id"),
        UniqueConstraint("tenant_id", "name", name="uq_datasets_tenant_id_name"),
        # ADR-013: real clinical originals are out of the initial trials, and a
        # classification is never lowered automatically.
        CheckConstraint(
            "sensitivity IN ('synthetic','internal','restricted')",
            name="sensitivity_allowed",
        ),
    )

    dataset_id: Mapped[InvId] = mapped_column(primary_key=True)
    tenant_id: Mapped[TenantId] = mapped_column()
    project_id: Mapped[InvId] = mapped_column()
    name: Mapped[str] = mapped_column(String(128))
    #: The pilot uses synthetic data. Downgrading this is an owner decision, not
    #: an automatic consequence of de-identification (ADR-013).
    sensitivity: Mapped[str] = mapped_column(String(16), default="synthetic")
    description: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_at: Mapped[Utc] = mapped_column(server_default=text("now()"))


class DatasetVersion(Base):
    """An immutable snapshot of a dataset, addressed ``name@version``."""

    __tablename__ = "dataset_versions"
    __table_args__ = (
        ForeignKeyConstraint(
            ["tenant_id", "dataset_id"],
            ["datasets.tenant_id", "datasets.dataset_id"],
        ),
        UniqueConstraint(
            "tenant_id", "dataset_version_id", name="uq_dataset_versions_tenant_id_version_id"
        ),
        UniqueConstraint("dataset_id", "version", name="uq_dataset_versions_dataset_id_version"),
        CheckConstraint("byte_size >= 0", name="byte_size_non_negative"),
        CheckConstraint("record_count >= 0", name="record_count_non_negative"),
        CheckConstraint(
            "content_sha256 = lower(content_sha256)", name="checksum_is_lowercase"
        ),
    )

    dataset_version_id: Mapped[InvId] = mapped_column(primary_key=True)
    tenant_id: Mapped[TenantId] = mapped_column()
    dataset_id: Mapped[InvId] = mapped_column()
    version: Mapped[str] = mapped_column(String(64))
    #: Over the actual bytes, by a trusted worker (ADR-011).
    content_sha256: Mapped[Sha256] = mapped_column()
    byte_size: Mapped[int] = mapped_column(BigInteger, default=0)
    record_count: Mapped[int] = mapped_column(BigInteger, default=0)
    #: inv://datasets/<name>@<version> (ADR-010).
    uri: Mapped[str] = mapped_column(Text)
    #: Manual retention: datasets sit outside the 90 day lifetime and are only
    #: released deliberately. The pin extends, never shortens.
    retention_pinned_until: Mapped[Utc | None] = mapped_column(nullable=True)
    created_at: Mapped[Utc] = mapped_column(server_default=text("now()"))


class CodeCommit(Base):
    """The code that produced something. Identity is the commit SHA."""

    __tablename__ = "code_commits"
    __table_args__ = (
        UniqueConstraint("tenant_id", "commit_id", name="uq_code_commits_tenant_id_commit_id"),
        UniqueConstraint(
            "tenant_id", "repository", "commit_sha", name="uq_code_commits_repo_sha"
        ),
        # A 40 character hex SHA-1, or a 64 character SHA-256 for repositories
        # that have moved. Anything else is not a commit.
        CheckConstraint(
            "commit_sha ~ '^[0-9a-f]{40}$' OR commit_sha ~ '^[0-9a-f]{64}$'",
            name="commit_sha_is_hex",
        ),
        Index("ix_code_commits_tenant_id_repository", "tenant_id", "repository"),
    )

    commit_id: Mapped[InvId] = mapped_column(primary_key=True)
    tenant_id: Mapped[TenantId] = mapped_column()
    repository: Mapped[str] = mapped_column(String(255))
    commit_sha: Mapped[str] = mapped_column(String(64))
    #: The branch or tag it was reached by. Metadata — a ref moves, the SHA
    #: does not, so lineage joins on the SHA.
    ref: Mapped[str | None] = mapped_column(String(255), nullable=True)
    dirty: Mapped[bool] = mapped_column(default=False)
    committed_at: Mapped[Utc | None] = mapped_column(nullable=True)
    recorded_at: Mapped[Utc] = mapped_column(server_default=text("now()"))


class ContainerImage(Base):
    """A container image. Identity is the digest.

    The tag is recorded and is never the key. ``app:latest`` resolves to a
    different image over time, so a lineage row keyed on a tag would look
    precise while pointing at whatever is current.
    """

    __tablename__ = "container_images"
    __table_args__ = (
        UniqueConstraint("tenant_id", "image_id", name="uq_container_images_tenant_id_image_id"),
        UniqueConstraint("tenant_id", "digest", name="uq_container_images_tenant_id_digest"),
        # OCI digests are "<algorithm>:<hex>".
        CheckConstraint("digest ~ '^sha256:[0-9a-f]{64}$'", name="digest_is_oci_sha256"),
        Index("ix_container_images_tenant_id_repository", "tenant_id", "repository"),
    )

    image_id: Mapped[InvId] = mapped_column(primary_key=True)
    tenant_id: Mapped[TenantId] = mapped_column()
    repository: Mapped[str] = mapped_column(String(255))
    digest: Mapped[str] = mapped_column(String(80))
    #: Whatever tag it happened to carry when recorded. Informational only.
    tag: Mapped[str | None] = mapped_column(String(128), nullable=True)
    byte_size: Mapped[int] = mapped_column(BigInteger, default=0)
    built_at: Mapped[Utc | None] = mapped_column(nullable=True)
    recorded_at: Mapped[Utc] = mapped_column(server_default=text("now()"))


class Model(Base):
    __tablename__ = "models"
    __table_args__ = (
        ForeignKeyConstraint(
            ["tenant_id", "project_id"],
            ["projects.tenant_id", "projects.project_id"],
        ),
        UniqueConstraint("tenant_id", "model_id", name="uq_models_tenant_id_model_id"),
        UniqueConstraint("tenant_id", "name", name="uq_models_tenant_id_name"),
    )

    model_id: Mapped[InvId] = mapped_column(primary_key=True)
    tenant_id: Mapped[TenantId] = mapped_column()
    project_id: Mapped[InvId] = mapped_column()
    name: Mapped[str] = mapped_column(String(128))
    task: Mapped[str | None] = mapped_column(String(64), nullable=True)
    description: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_at: Mapped[Utc] = mapped_column(server_default=text("now()"))


class ModelVersion(Base):
    """An immutable model build (S10-ST).

    Append-only for the application role. A model version whose weights can be
    replaced under a fixed name is the thing every lineage claim would be built
    on top of and would silently invalidate.
    """

    __tablename__ = "model_versions"
    __table_args__ = (
        ForeignKeyConstraint(
            ["tenant_id", "model_id"], ["models.tenant_id", "models.model_id"]
        ),
        UniqueConstraint(
            "tenant_id", "model_version_id", name="uq_model_versions_tenant_id_version_id"
        ),
        UniqueConstraint("model_id", "version", name="uq_model_versions_model_id_version"),
        UniqueConstraint(
            "tenant_id", "content_sha256", name="uq_model_versions_tenant_id_content_sha256"
        ),
        CheckConstraint("byte_size >= 0", name="byte_size_non_negative"),
        CheckConstraint(
            "content_sha256 = lower(content_sha256)", name="checksum_is_lowercase"
        ),
        CheckConstraint(
            "stage IN ('draft','candidate','released','retired')", name="stage_allowed"
        ),
        # A released version is one someone can deploy, so it must be verified
        # and pinned before it can be released.
        CheckConstraint(
            "stage <> 'released' OR (verified_at IS NOT NULL AND retention_pinned_until IS NOT NULL)",
            name="release_requires_verification_and_pin",
        ),
        Index("ix_model_versions_tenant_id_stage", "tenant_id", "stage"),
    )

    model_version_id: Mapped[InvId] = mapped_column(primary_key=True)
    tenant_id: Mapped[TenantId] = mapped_column()
    model_id: Mapped[InvId] = mapped_column()
    version: Mapped[str] = mapped_column(String(64))
    stage: Mapped[str] = mapped_column(String(16), default="draft")
    #: Over the actual weights, by a trusted worker. Unique per tenant: two
    #: names for identical bytes is a mistake worth catching.
    content_sha256: Mapped[Sha256] = mapped_column()
    byte_size: Mapped[int] = mapped_column(BigInteger, default=0)
    uri: Mapped[str] = mapped_column(Text)
    verified_at: Mapped[Utc | None] = mapped_column(nullable=True)
    #: Manual retention (PLAN-STORAGE-001). Extends only.
    retention_pinned_until: Mapped[Utc | None] = mapped_column(nullable=True)
    #: The Run that produced it, when one did.
    produced_by_run_id: Mapped[InvId | None] = mapped_column(nullable=True)
    created_at: Mapped[Utc] = mapped_column(server_default=text("now()"))


class ModelLineage(Base):
    """One edge: this model version came from that thing.

    A single edge table rather than five foreign keys, because the set of
    things a model derives from grows and a column per kind would mean a
    migration each time. ``subject_id`` is the referenced row's id and is not a
    foreign key for that reason — the kind says which table to read, and
    :func:`services.lineage.trace_model` does the reading.
    """

    __tablename__ = "model_lineage"
    __table_args__ = (
        ForeignKeyConstraint(
            ["tenant_id", "model_version_id"],
            ["model_versions.tenant_id", "model_versions.model_version_id"],
        ),
        CheckConstraint(
            "kind IN ('dataset_version','code_commit','container_image','eval_run','approval')",
            name="kind_allowed",
        ),
        Index("ix_model_lineage_tenant_id_kind", "tenant_id", "kind"),
        Index("ix_model_lineage_subject_id", "subject_id"),
    )

    tenant_id: Mapped[TenantId] = mapped_column(primary_key=True)
    model_version_id: Mapped[InvId] = mapped_column(primary_key=True)
    kind: Mapped[str] = mapped_column(String(24), primary_key=True)
    subject_id: Mapped[InvId] = mapped_column(primary_key=True)
    #: How it was used: "trained_on", "validated_on", "built_with", ...
    relation: Mapped[str] = mapped_column(String(32), default="derived_from")
    recorded_at: Mapped[Utc] = mapped_column(server_default=text("now()"))


class Deployment(Base):
    """A released model version put somewhere, pinned by digest.

    ``deployed_digest`` is what AC-10 calls the deployment digest: the exact
    content that went out, recorded at the moment it went out. The approval is
    bound to that digest, so approving one build does not authorise shipping a
    different one under the same version name.
    """

    __tablename__ = "deployments"
    __table_args__ = (
        ForeignKeyConstraint(
            ["tenant_id", "model_version_id"],
            ["model_versions.tenant_id", "model_versions.model_version_id"],
        ),
        UniqueConstraint(
            "tenant_id", "deployment_id", name="uq_deployments_tenant_id_deployment_id"
        ),
        CheckConstraint(
            "environment IN ('lab','staging','pilot')", name="environment_allowed"
        ),
        CheckConstraint(
            "status IN ('pending','active','superseded','rolled_back','failed')",
            name="status_allowed",
        ),
        CheckConstraint(
            "deployed_digest = lower(deployed_digest)", name="digest_is_lowercase"
        ),
        # Nothing reaches an environment without a recorded approval.
        CheckConstraint(
            "status = 'failed' OR approval_id IS NOT NULL", name="deployment_requires_approval"
        ),
        Index("ix_deployments_tenant_id_environment_status", "tenant_id", "environment", "status"),
    )

    deployment_id: Mapped[InvId] = mapped_column(primary_key=True)
    tenant_id: Mapped[TenantId] = mapped_column()
    model_version_id: Mapped[InvId] = mapped_column()
    environment: Mapped[str] = mapped_column(String(16))
    status: Mapped[str] = mapped_column(String(16), default="pending")
    #: The content digest that actually shipped. Frozen here.
    deployed_digest: Mapped[Sha256] = mapped_column()
    #: The image it ran in, when it ran in one.
    image_id: Mapped[InvId | None] = mapped_column(nullable=True)
    approval_id: Mapped[InvId | None] = mapped_column(nullable=True)
    deployed_by_user_id: Mapped[InvId] = mapped_column()
    deployed_at: Mapped[Utc] = mapped_column(server_default=text("now()"))
    superseded_at: Mapped[Utc | None] = mapped_column(nullable=True)
    notes: Mapped[dict] = mapped_column(JSONB, server_default=text("'{}'::jsonb"))
