"""Real login: a verified access token becomes a business principal.

``OidcPrincipalVerifier`` used to raise ``SettingUnresolved`` because the
issuer, audience and JWKS endpoint were open S01-BE decisions. They are not open
any more — they were decided on the other side of the seam, and
``inv.identity.AccessTokens`` is the result: an offline resource-server verifier
with an operator-supplied trust bundle, no discovery URL and no token-header
key lookup.

**So this delegates to it rather than verifying a second time.** Two JWT
verifiers in one product means two answers to "who is this caller", and the one
that matters is whichever is wrong. It would also mean two places to get an
audience check right, two places to reject ``alg: none``, and two places to
remember that a JWKS bundle expires. The kernel's is thorough — canonical
base64 re-encoding, the decoded claims compared against the untrusted segment,
required claims, bounded token lifetime, RS256 with a bounded key size, and a
refusal to start at all without a valid bundle — and duplicating it would not
make it more correct.

**What this layer adds is the part the kernel deliberately does not do: mapping
a verified subject to a person.** The kernel stops at
``oidc:<sha256(issuer, sub)>``, which is stable across key rotation and distinct
across issuers. The business surface has to turn that into a ``public.users``
row, and there are two ways to get that wrong:

*Creating the user on first sight.* Convenient, and it means anyone the identity
provider will issue a token for becomes a user here — so the question "who may
have an account" is answered by the IdP's entire user directory rather than by
anyone in this product. An unknown subject is refused.

*Reading membership from the token.* Groups and roles in a JWT are a snapshot
from the moment it was issued, and they are also claims the IdP controls rather
than facts this product decided. Project access is read from
``project_members`` at the point of use — the same row the kernel reads.

There is one more state worth naming. A user can be able to sign in and still
not be able to **approve**, because approval identity lives in
``inv.business_subjects``, which an operator registers and which is immutable
and one-to-one on purpose: a two-person rule that one person can satisfy with
two identities is not a two-person rule. That is reported, not hidden, so the
difference between "you may not" and "an operator has not registered you yet"
is visible.
"""

from __future__ import annotations

import uuid
from typing import Any, Protocol

from sqlalchemy import select
from sqlalchemy.orm import Session

from ..config import SettingUnresolved
from ..db.models import Project, ProjectMember, User
from ..errors import AUTH_INVALID_CREDENTIAL, InvError
from .principal import Principal


class TokenVerifier(Protocol):
    """The shape ``inv.identity.AccessTokens`` already has."""

    def verify(self, token: str) -> Any: ...


def load_access_tokens(settings: Any) -> TokenVerifier:
    """Build the kernel's verifier from configuration, or say what is missing.

    Constructing it validates the trust bundle, so a deployment with an expired
    or wrongly scoped bundle fails at startup rather than at the first login —
    which is the difference between an operator seeing it and a user seeing it.
    """
    from inv.identity import AccessTokens

    missing = [
        name
        for name in ("oidc_issuer", "oidc_audience", "oidc_client_ids", "oidc_jwks_file")
        if not getattr(settings, name, None)
    ]
    if missing:
        raise SettingUnresolved(
            "real login needs " + ", ".join(missing) + "; the verifier is "
            "offline by design and will not discover them"
        )
    return AccessTokens(
        tenant_id=str(settings.tenant_id),
        issuer=settings.oidc_issuer,
        audience=settings.oidc_audience,
        client_ids=settings.oidc_client_ids,
        jwks_file=settings.oidc_jwks_file,
    )


class OidcPrincipalVerifier:
    """Turns a verified access token into a business principal.

    Needs a session factory because the subject-to-user mapping is a database
    read, and it has to happen per request: a user suspended a minute ago must
    not keep working because their token is still valid.
    """

    def __init__(self, tokens: TokenVerifier, session_factory) -> None:
        self._tokens = tokens
        self._session_factory = session_factory

    def verify(self, credential: str) -> Principal:
        identity = self._tokens.verify(credential)
        subject = identity.principal.subject_id
        tenant_id = uuid.UUID(identity.principal.tenant_id)

        from ..db.session import tenant_scope

        with self._session_factory() as session:
            with session.begin():
                with tenant_scope(session, tenant_id):
                    return principal_for_subject(
                        session, tenant_id=tenant_id, subject=subject
                    )


def principal_for_subject(
    session: Session, *, tenant_id: uuid.UUID, subject: str
) -> Principal:
    """Find the person this verified subject belongs to.

    Refuses an unknown subject instead of creating one. A verifier that creates
    a user on first sight makes the identity provider's whole directory into
    this product's user list, and nobody here decided that.

    The message is deliberately the same as an invalid credential: telling an
    authenticated stranger "your token is fine, you just have no account here"
    confirms the issuer is trusted and the token is good, which is more than
    they need to know.
    """
    user = session.scalars(
        select(User).where(
            User.tenant_id == tenant_id, User.external_subject == subject
        )
    ).one_or_none()
    if user is None:
        raise InvError(
            AUTH_INVALID_CREDENTIAL,
            "credential is not recognised",
            extra={"reason": "no account is linked to this subject"},
            public=False,
        )
    if user.status != "active":
        # A suspended account with a live token is exactly the case suspension
        # exists for, and the token stays valid until it expires.
        raise InvError(
            AUTH_INVALID_CREDENTIAL,
            "credential is not recognised",
            extra={"reason": f"the account is {user.status}"},
            public=False,
        )

    memberships = session.execute(
        select(ProjectMember.project_id, ProjectMember.role_code)
        .join(
            Project,
            (Project.tenant_id == ProjectMember.tenant_id)
            & (Project.project_id == ProjectMember.project_id),
        )
        .where(
            ProjectMember.tenant_id == tenant_id,
            ProjectMember.user_id == user.user_id,
            Project.status == "active",
        )
    ).all()

    return Principal(
        user_id=user.user_id,
        tenant_id=tenant_id,
        external_subject=subject,
        # Populated for callers that still read it, and no longer the thing
        # authorisation rests on: every check reads project_members at the
        # point of use, because this set is already stale by the time the
        # request it was built for is handled.
        project_ids=frozenset(project_id for project_id, _ in memberships),
        roles=frozenset(role for _, role in memberships),
    )
