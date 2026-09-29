"""Tenant-scoped operator service credentials (S10-BE stage 2, design #168 §4).

**Boundary with 0035 (``inv.credential_versions`` / ``inv.credential_grants``).**
The 0035 registry is the *Run* contract: a grant binds a project, a subject,
a non-terminal run and a recovery epoch, and its lookup refuses once the run
has ended. The mirror worker runs after the canonical commit, usually for a
run that has ended, from a service principal rather than a user, so the 0035
lookup is refused by definition and is never called. These two tables are the
separate, tenant-scoped contract the design chose instead (decision (b)):

* ``service_credential_versions`` -- a version-pinned secret *file* reference
  in the same shape as 0035 (``<32 hex>.secret`` name, device/inode identity,
  ``content_sha256``), bound to a ``purpose`` and a ``destination`` alias whose
  normalised URI digest is recorded. The database holds no secret bytes.
* ``service_credential_grants`` -- who may use it: a worker principal, an
  ``enabled`` flag, expiry, revocation and the recovery epoch. No project, no
  run.

Both are tenant-scoped under RLS. The application role may INSERT and SELECT;
a grant's ``enabled``/``revoked_at`` and a version's ``revoked_at`` may move
forward (column-level UPDATE, the 0004 lifecycle pattern), and nothing else
can be rewritten. The reader is the existing Linux descriptor-bound reader
(``credentials.linux_file``) through :mod:`saintvision.tracking.service_credentials`,
so the file checks are not re-implemented here.
"""

from __future__ import annotations

import uuid

from sqlalchemy import (
    BigInteger,
    CheckConstraint,
    ForeignKeyConstraint,
    Index,
    Integer,
    PrimaryKeyConstraint,
    String,
    UniqueConstraint,
    text,
)
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column

from ..base import Base, InvId, Sha256, TenantId, Utc

SERVICE_CREDENTIAL_PURPOSES: tuple[str, ...] = ("mlflow.mirror",)
DESTINATION_ALIAS_PATTERN = "^[a-z][a-z0-9-]{0,63}$"
SECRET_FILE_PATTERN = "^[0-9a-f]{32}[.]secret$"
WORKER_PRINCIPAL_PATTERN = "^[a-z][a-z0-9._-]{2,63}$"


class ServiceCredentialVersion(Base):
    __tablename__ = "service_credential_versions"
    __table_args__ = (
        PrimaryKeyConstraint("tenant_id", "credential_id", "version_id", name="pk_service_credential_versions"),
        CheckConstraint(
            "purpose IN (" + ",".join(f"'{p}'" for p in SERVICE_CREDENTIAL_PURPOSES) + ")",
            name="purpose_allowed",
        ),
        CheckConstraint(f"destination ~ '{DESTINATION_ALIAS_PATTERN}'", name="destination_alias"),
        CheckConstraint("destination_uri_sha256 ~ '^[0-9a-f]{64}$'", name="destination_uri_sha256_hex"),
        CheckConstraint(f"file_name ~ '{SECRET_FILE_PATTERN}'", name="file_name_secret"),
        CheckConstraint("content_sha256 ~ '^[0-9a-f]{64}$'", name="content_sha256_hex"),
        CheckConstraint("device >= 0 AND inode >= 0", name="identity_non_negative"),
        Index("ix_service_credential_versions_lookup", "tenant_id", "purpose", "destination"),
    )

    tenant_id: Mapped[TenantId] = mapped_column()
    credential_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True))
    version_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True))
    purpose: Mapped[str] = mapped_column(String(32))
    destination: Mapped[str] = mapped_column(String(64))
    #: sha256 of the normalised tracking URI the alias stands for (§2.2). The
    #: worker uses the credential only when this equals the configured URI's.
    destination_uri_sha256: Mapped[Sha256] = mapped_column()
    file_name: Mapped[str] = mapped_column(String(40))
    device: Mapped[int] = mapped_column(BigInteger)
    inode: Mapped[int] = mapped_column(BigInteger)
    content_sha256: Mapped[Sha256] = mapped_column()
    created_at: Mapped[Utc] = mapped_column(server_default=text("now()"))
    revoked_at: Mapped[Utc | None] = mapped_column(nullable=True)


class ServiceCredentialGrant(Base):
    __tablename__ = "service_credential_grants"
    __table_args__ = (
        PrimaryKeyConstraint("tenant_id", "grant_id", name="pk_service_credential_grants"),
        ForeignKeyConstraint(
            ["tenant_id", "credential_id", "version_id"],
            [
                "service_credential_versions.tenant_id",
                "service_credential_versions.credential_id",
                "service_credential_versions.version_id",
            ],
            name="fk_service_credential_grants_version",
        ),
        UniqueConstraint(
            "tenant_id", "credential_id", "version_id", "worker_principal",
            name="uq_service_credential_grants_principal",
        ),
        CheckConstraint(f"worker_principal ~ '{WORKER_PRINCIPAL_PATTERN}'", name="worker_principal_shape"),
        CheckConstraint("recovery_epoch >= 0", name="recovery_epoch_non_negative"),
        CheckConstraint("expires_at > created_at", name="expiry_after_creation"),
    )

    tenant_id: Mapped[TenantId] = mapped_column()
    grant_id: Mapped[InvId] = mapped_column()
    credential_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True))
    version_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True))
    worker_principal: Mapped[str] = mapped_column(String(64))
    enabled: Mapped[bool] = mapped_column(default=True)
    recovery_epoch: Mapped[int] = mapped_column(Integer, default=0)
    created_at: Mapped[Utc] = mapped_column(server_default=text("now()"))
    expires_at: Mapped[Utc] = mapped_column()
    revoked_at: Mapped[Utc | None] = mapped_column(nullable=True)
