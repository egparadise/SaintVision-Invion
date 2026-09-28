"""Service credential lookup for the mirror worker (design #168 §4, decision (b)).

:class:`ServiceCredentialRegistry.lookup` answers one question: may *this
worker principal*, for *this purpose* and *this destination*, at *this
recovery epoch*, use a version-pinned secret file for the tracking URI that
is actually configured? Every condition is checked in one query, and the
answer is a :class:`CredentialBinding` (file name, device, inode, content
digest) or ``None``; ``None`` is ``TRACK-0002`` upstream. The registry never
reads the file.

Reading is delegated to the existing Linux descriptor-bound reader
(``credentials.linux_file.LinuxFileCredentials``) through
:class:`ServiceRegistryAdapter`, which speaks the 0035 lookup signature that
reader expects. The adapter ignores the run-bound fields of the context
(project, run): this contract is tenant-scoped by design, and the 0035
registry is never consulted (a test spies on it).
"""

from __future__ import annotations

import datetime as dt
import re
import uuid
from dataclasses import dataclass
from typing import Final

from sqlalchemy import select
from sqlalchemy.orm import Session

from ..credentials.contract import CredentialContext
from ..credentials.linux_file import CredentialBinding
from ..db.models.service_credentials import (
    SERVICE_CREDENTIAL_PURPOSES,
    ServiceCredentialGrant,
    ServiceCredentialVersion,
)

PURPOSE_MLFLOW_MIRROR: Final[str] = "mlflow.mirror"
_REFERENCE: Final[str] = "svcred:1:{credential_id}:{version_id}"
_UUID: Final[re.Pattern[str]] = re.compile(r"^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$")


def credential_reference(credential_id: uuid.UUID, version_id: uuid.UUID) -> str:
    """The ``svcred:1:<credential>:<version>`` reference the file reader accepts."""
    return _REFERENCE.format(credential_id=credential_id, version_id=version_id)


@dataclass(frozen=True, slots=True)
class LookupRequest:
    tenant_id: uuid.UUID
    purpose: str
    destination: str
    destination_uri_sha256: str
    worker_principal: str
    recovery_epoch: int
    now: dt.datetime

    def __post_init__(self) -> None:
        if self.purpose not in SERVICE_CREDENTIAL_PURPOSES:
            raise ValueError(f"unknown purpose {self.purpose!r}")
        if not re.fullmatch(r"[0-9a-f]{64}", self.destination_uri_sha256):
            raise ValueError("destination_uri_sha256 must be lowercase hex")
        if self.recovery_epoch < 0:
            raise ValueError("recovery_epoch is non-negative")
        if self.now.tzinfo is None:
            raise ValueError("now must be timezone-aware")


@dataclass(frozen=True, slots=True)
class ServiceCredentialMatch:
    credential_id: uuid.UUID
    version_id: uuid.UUID
    binding: CredentialBinding

    @property
    def reference(self) -> str:
        return credential_reference(self.credential_id, self.version_id)


class ServiceCredentialRegistry:
    """Tenant-scoped lookup; ``None`` means refused (``TRACK-0002``)."""

    def __init__(self, session: Session) -> None:
        self._session = session

    def lookup(self, request: LookupRequest) -> ServiceCredentialMatch | None:
        row = self._session.execute(
            select(ServiceCredentialVersion, ServiceCredentialGrant)
            .join(
                ServiceCredentialGrant,
                (ServiceCredentialGrant.tenant_id == ServiceCredentialVersion.tenant_id)
                & (ServiceCredentialGrant.credential_id == ServiceCredentialVersion.credential_id)
                & (ServiceCredentialGrant.version_id == ServiceCredentialVersion.version_id),
            )
            .where(
                ServiceCredentialVersion.tenant_id == request.tenant_id,
                ServiceCredentialVersion.purpose == request.purpose,
                ServiceCredentialVersion.destination == request.destination,
                ServiceCredentialVersion.destination_uri_sha256 == request.destination_uri_sha256,
                ServiceCredentialVersion.revoked_at.is_(None),
                ServiceCredentialGrant.worker_principal == request.worker_principal,
                ServiceCredentialGrant.enabled.is_(True),
                ServiceCredentialGrant.revoked_at.is_(None),
                ServiceCredentialGrant.expires_at > request.now,
                ServiceCredentialGrant.recovery_epoch == request.recovery_epoch,
            )
            .order_by(ServiceCredentialVersion.created_at.desc())
            .limit(1)
        ).first()
        if row is None:
            return None
        version, _grant = row
        return ServiceCredentialMatch(
            credential_id=version.credential_id,
            version_id=version.version_id,
            binding=CredentialBinding(
                file_name=version.file_name,
                device=int(version.device),
                inode=int(version.inode),
                content_sha256=version.content_sha256,
            ),
        )

    def lookup_pinned(
        self, credential_id: uuid.UUID, version_id: uuid.UUID, request: LookupRequest
    ) -> CredentialBinding | None:
        """Re-check one exact version at use time (the reader calls this again)."""
        match = self.lookup(request)
        if match is None or (match.credential_id, match.version_id) != (credential_id, version_id):
            return None
        return match.binding


class ServiceRegistryAdapter:
    """The 0035 lookup signature over the service registry, for the file reader.

    ``LinuxFileCredentials`` calls ``registry.lookup(credential_id, version_id,
    context, purpose, destination)`` before and after every read. The context's
    tenant and subject are the only fields used: project and run are not part
    of this contract.
    """

    def __init__(self, registry: ServiceCredentialRegistry, template: LookupRequest) -> None:
        self._registry = registry
        self._template = template

    def lookup(self, credential_id: str, version_id: str, context: CredentialContext, purpose: str, destination: str):
        if not (_UUID.match(credential_id) and _UUID.match(version_id)):
            return None
        if str(context.tenant_id) != str(self._template.tenant_id):
            return None
        if context.subject_id != self._template.worker_principal:
            return None
        if purpose != self._template.purpose or destination != self._template.destination:
            return None
        return self._registry.lookup_pinned(uuid.UUID(credential_id), uuid.UUID(version_id), self._template)


def worker_context(request: LookupRequest) -> CredentialContext:
    """A context for the reader: tenant and principal are real, project/run are not bound."""
    return CredentialContext(
        tenant_id=str(request.tenant_id),
        project_id="-",
        subject_id=request.worker_principal,
        run_id="-",
    )
