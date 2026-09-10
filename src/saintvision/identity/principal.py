"""Who is calling.

OIDC is the intended user authentication (PLAN-BACKEND-001), but the issuer,
audience and JWKS endpoint are S01-BE decisions that have not been made. Rather
than hardcode a plausible issuer, this module defines the verifier interface and
ships two implementations:

``StaticPrincipalVerifier``
    Development and test only. Maps an opaque bearer token to a principal from
    an in-process table. Refuses to be constructed when the process is not
    explicitly marked as development.

``OidcPrincipalVerifier``
    Placeholder that raises ``SettingUnresolved`` until S01 supplies the issuer
    configuration. It exists so the wiring is real and the gap is visible at
    startup rather than discovered later.

Project membership is checked separately from tenancy: RLS gives tenant
isolation, but every user in a tenant passes RLS, so "another project's data"
(AC-02) is a service-layer check.
"""

from __future__ import annotations

import os
import uuid
from dataclasses import dataclass, field
from typing import Protocol

from ..config import SettingUnresolved
from ..errors import AUTH_INVALID_CREDENTIAL, AUTH_PROJECT_SCOPE, InvError


@dataclass(frozen=True, slots=True)
class Principal:
    user_id: str
    tenant_id: uuid.UUID
    external_subject: str
    #: Projects this principal belongs to. Empty means no project access at
    #: all, which is a valid state for a freshly created user.
    project_ids: frozenset[str] = field(default_factory=frozenset)
    roles: frozenset[str] = field(default_factory=frozenset)

    def require_project(self, project_id: str) -> None:
        if project_id not in self.project_ids:
            # Deliberately the same message whether the project does not exist
            # or the caller simply cannot see it: distinguishing them would
            # confirm the existence of another project's identifier.
            raise InvError(
                AUTH_PROJECT_SCOPE,
                "project is not accessible to this principal",
                extra={"projectId": project_id},
            )

    def has_role(self, code: str) -> bool:
        return code in self.roles


class PrincipalVerifier(Protocol):
    def verify(self, credential: str) -> Principal: ...


class StaticPrincipalVerifier:
    """Development verifier. Never usable in a deployed environment."""

    def __init__(self, principals: dict[str, Principal], *, allow_outside_dev: bool = False):
        if not allow_outside_dev and os.environ.get("INV_ENV") not in ("dev", "test"):
            raise SettingUnresolved(
                "StaticPrincipalVerifier requires INV_ENV=dev or INV_ENV=test"
            )
        self._principals = dict(principals)

    def verify(self, credential: str) -> Principal:
        principal = self._principals.get(credential)
        if principal is None:
            raise InvError(AUTH_INVALID_CREDENTIAL, "credential is not recognised")
        return principal


class OidcPrincipalVerifier:
    """Real verifier. Unimplemented until S01-BE decides the IdP.

    Constructing it raises rather than returning something that silently accepts
    nothing, so a misconfigured deployment fails at startup.
    """

    def __init__(self) -> None:
        raise SettingUnresolved(
            "OIDC issuer, audience and JWKS URL are S01-BE decisions and are not set; "
            "see docs/vault/30_Development/Claude 영역 구현 준비.md"
        )

    def verify(self, credential: str) -> Principal:  # pragma: no cover - unreachable
        raise SettingUnresolved("OIDC verifier is not configured")
