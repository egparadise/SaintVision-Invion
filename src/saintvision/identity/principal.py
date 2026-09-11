"""Who is calling.

OIDC is the intended user authentication (PLAN-BACKEND-001), but the issuer,
audience and JWKS endpoint are S01-BE decisions that have not been made. Rather
than hardcode a plausible issuer, this module defines the verifier interface and
ships two implementations:

``StaticPrincipalVerifier``
    Development and test only. Maps an opaque bearer token to a principal from
    an in-process table. Refuses to be constructed when the process is not
    explicitly marked as development.

``saintvision.identity.oidc.OidcPrincipalVerifier``
    The real one. It delegates token verification to ``inv.identity.AccessTokens``
    — the offline resource-server verifier the execution side already built —
    and adds the part that side deliberately stops short of: mapping a verified
    ``oidc:`` subject to a ``public.users`` row, refusing an unknown one rather
    than creating it.

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
    #: Projects this principal belonged to when the credential was verified.
    #:
    #: **Not what authorisation rests on.** It is a snapshot, and it is wrong in
    #: both directions: a project created after sign-in is missing from it, so
    #: its own creator could not open it; and a membership revoked after the
    #: token was issued stays in it until the token expires, which is the whole
    #: span during which revocation is supposed to matter. Every check reads
    #: ``project_members`` at the point of use — see
    #: ``saintvision.services.projects.require_project_access`` — which is also
    #: the row the execution kernel reads.
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


def _real_verifier_moved(*args, **kwargs):  # pragma: no cover - see below
    raise SettingUnresolved(
        "the real verifier now lives in saintvision.identity.oidc, because the "
        "decision this placeholder was waiting for was made on the execution "
        "side: inv.identity.AccessTokens verifies offline against an "
        "operator-supplied trust bundle, and duplicating it here would be a "
        "second answer to who a caller is"
    )


#: Kept as a name so an import does not silently succeed against nothing.
#: :class:`saintvision.identity.oidc.OidcPrincipalVerifier` is the real one.
OidcPrincipalVerifier = _real_verifier_moved
