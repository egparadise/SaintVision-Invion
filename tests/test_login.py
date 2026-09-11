"""Real login: a verified subject becomes a person, or is refused.

Token verification itself is the execution side's (``inv.identity.AccessTokens``)
and is not re-tested here — testing it twice would be the same mistake as
implementing it twice. What these hold is the layer above it: turning a verified
``oidc:`` subject into a ``public.users`` row, and every way that mapping can
quietly become a way in.
"""

from __future__ import annotations

import datetime as dt
import hashlib
import json
import uuid
from dataclasses import dataclass

import pytest
from sqlalchemy import text

from saintvision.db.session import tenant_scope
from saintvision.errors import InvError
from saintvision.identity.oidc import OidcPrincipalVerifier, principal_for_subject
from saintvision.ids import new_id
from saintvision.services import projects as project_service
from saintvision.services import settings as settings_service

pytestmark = pytest.mark.postgres

UTC = dt.timezone.utc
NOW = dt.datetime(2026, 9, 11, 10, 0, 0, tzinfo=UTC)
ISSUER = "https://idp.example.test"


def _subject(sub: str) -> str:
    """The same derivation the kernel uses, so both halves name one person once."""
    return (
        "oidc:"
        + hashlib.sha256(
            json.dumps([ISSUER, sub], separators=(",", ":")).encode()
        ).hexdigest()
    )


@dataclass(frozen=True)
class _CorePrincipal:
    tenant_id: str
    subject_id: str


@dataclass(frozen=True)
class _Identity:
    principal: _CorePrincipal
    expires_at: int


class _FakeTokens:
    """Stands in for the verifier, which is tested on its own side."""

    def __init__(self, tenant_id, mapping):
        self.tenant_id = str(tenant_id)
        self._mapping = mapping

    def verify(self, token):
        if token not in self._mapping:
            raise RuntimeError("token rejected")
        return _Identity(
            _CorePrincipal(self.tenant_id, self._mapping[token]), 0
        )


@pytest.fixture
def accounts(owner_engine, two_tenants):
    tenant_a, tenant_b = two_tenants
    ids = {
        "tenant_a": tenant_a,
        "tenant_b": tenant_b,
        "alice": new_id("user"),
        "suspended": new_id("user"),
    }
    ids["alice_subject"] = _subject("alice@example.test")
    ids["suspended_subject"] = _subject("gone@example.test")
    ids["unknown_subject"] = _subject("never-registered@example.test")
    with owner_engine.begin() as c:
        for key, subject, status in (
            ("alice", ids["alice_subject"], "active"),
            ("suspended", ids["suspended_subject"], "suspended"),
        ):
            c.execute(
                text(
                    "INSERT INTO users (user_id, tenant_id, external_subject, "
                    "display_name, status, created_at, updated_at, version) "
                    "VALUES (:u, :t, :s, :n, :st, now(), now(), 1)"
                ),
                {"u": ids[key], "t": tenant_a, "s": subject, "n": key, "st": status},
            )
    return ids


# --------------------------------------------------------------------------
# The mapping
# --------------------------------------------------------------------------


def test_a_verified_subject_becomes_the_person_it_belongs_to(
    app_sessionmaker, accounts
):
    with app_sessionmaker() as session:
        with session.begin():
            with tenant_scope(session, accounts["tenant_a"]):
                principal = principal_for_subject(
                    session,
                    tenant_id=accounts["tenant_a"],
                    subject=accounts["alice_subject"],
                )
    assert principal.user_id == accounts["alice"]
    assert principal.external_subject == accounts["alice_subject"]


def test_an_unknown_subject_is_refused_not_created(app_sessionmaker, accounts):
    """A verifier that creates a user on first sight hands the account list to the IdP.

    Whoever the identity provider will issue a token for becomes a user here,
    and nobody in this product decided that.
    """
    with app_sessionmaker() as session:
        with session.begin():
            with tenant_scope(session, accounts["tenant_a"]):
                with pytest.raises(InvError):
                    principal_for_subject(
                        session,
                        tenant_id=accounts["tenant_a"],
                        subject=accounts["unknown_subject"],
                    )
                count = session.execute(
                    text("SELECT count(*) FROM users WHERE external_subject = :s"),
                    {"s": accounts["unknown_subject"]},
                ).scalar_one()
    assert count == 0


def test_the_refusal_does_not_confirm_the_token_was_good(
    app_sessionmaker, accounts
):
    """An authenticated stranger learns nothing from being refused.

    "Your token is fine, you just have no account here" confirms the issuer is
    trusted and the signature verified, which is more than they need.
    """
    with app_sessionmaker() as session:
        with session.begin():
            with tenant_scope(session, accounts["tenant_a"]):
                with pytest.raises(InvError) as unknown:
                    principal_for_subject(
                        session, tenant_id=accounts["tenant_a"],
                        subject=accounts["unknown_subject"],
                    )
                with pytest.raises(InvError) as suspended:
                    principal_for_subject(
                        session, tenant_id=accounts["tenant_a"],
                        subject=accounts["suspended_subject"],
                    )
    assert unknown.value.message == suspended.value.message == "credential is not recognised"
    assert unknown.value.code == suspended.value.code
    # The reason is recorded for the operator and not returned to the caller.
    assert not unknown.value.public


def test_a_suspended_account_cannot_sign_in_with_a_still_valid_token(
    app_sessionmaker, accounts
):
    """The case suspension exists for.

    The token stays cryptographically valid until it expires; suspension has to
    be checked where the person is looked up, or it does nothing for that hour.
    """
    with app_sessionmaker() as session:
        with session.begin():
            with tenant_scope(session, accounts["tenant_a"]):
                with pytest.raises(InvError):
                    principal_for_subject(
                        session, tenant_id=accounts["tenant_a"],
                        subject=accounts["suspended_subject"],
                    )


def test_suspension_takes_effect_on_the_next_request(app_sessionmaker, accounts):
    with app_sessionmaker() as session:
        with session.begin():
            with tenant_scope(session, accounts["tenant_a"]):
                principal_for_subject(
                    session, tenant_id=accounts["tenant_a"],
                    subject=accounts["alice_subject"],
                )
                settings_service.set_user_status(
                    session, tenant_id=accounts["tenant_a"],
                    user_id=accounts["alice"], status="suspended", now=NOW,
                )
                with pytest.raises(InvError):
                    principal_for_subject(
                        session, tenant_id=accounts["tenant_a"],
                        subject=accounts["alice_subject"],
                    )


def test_the_subject_derivation_matches_the_execution_kernel(app_sessionmaker):
    """One person, named the same way on both sides of the seam.

    If the two derivations diverged, a user would exist for login and be a
    different subject entirely to the kernel — so they could sign in and never
    be able to approve anything, with nothing to point at.
    """
    from inv.identity import public_subject

    assert public_subject(ISSUER, "alice@example.test") == _subject(
        "alice@example.test"
    )
    # And a different issuer with the same sub is a different person.
    assert public_subject("https://other.test", "alice@example.test") != _subject(
        "alice@example.test"
    )


def test_the_verifier_reads_membership_from_the_database_not_the_token(
    app_sessionmaker, owner_engine, accounts
):
    """Groups in a JWT are a snapshot, and one the IdP controls rather than us."""
    with app_sessionmaker() as session:
        with session.begin():
            with tenant_scope(session, accounts["tenant_a"]):
                created = project_service.create_project(
                    session, tenant_id=accounts["tenant_a"], code="login-one",
                    display_name="L", created_by_user_id=accounts["alice"], now=NOW,
                )
                project_id = created["projectId"]

    verifier = OidcPrincipalVerifier(
        _FakeTokens(accounts["tenant_a"], {"tok": accounts["alice_subject"]}),
        _sessionmaker_for(app_sessionmaker),
    )
    principal = verifier.verify("tok")
    assert principal.user_id == accounts["alice"]
    # The project created a moment ago is present, because it was read now.
    assert project_id in principal.project_ids
    assert "owner" in principal.roles


def _sessionmaker_for(app_sessionmaker):
    return app_sessionmaker


def test_an_archived_projects_membership_is_not_carried(
    app_sessionmaker, accounts
):
    """A project nobody may execute in should not appear as access."""
    with app_sessionmaker() as session:
        with session.begin():
            with tenant_scope(session, accounts["tenant_a"]):
                created = project_service.create_project(
                    session, tenant_id=accounts["tenant_a"], code="login-two",
                    display_name="L2", created_by_user_id=accounts["alice"], now=NOW,
                )
                settings_service.set_project_status(
                    session, tenant_id=accounts["tenant_a"],
                    project_id=created["projectId"], status="archived",
                    acting_user_id=accounts["alice"],
                )
                principal = principal_for_subject(
                    session, tenant_id=accounts["tenant_a"],
                    subject=accounts["alice_subject"],
                )
    assert created["projectId"] not in principal.project_ids


# --------------------------------------------------------------------------
# Configuration
# --------------------------------------------------------------------------


def test_the_settings_no_longer_wait_for_a_decision_that_was_made():
    """INV_OIDC_JWKS_URL was pending and the decision went the other way.

    The chosen verifier is offline and takes a trust bundle from a file;
    fetching keys at verification time would make the identity provider's
    availability a dependency of every request. Leaving the name in the pending
    set kept a settled question looking open and pointed at the wrong answer.
    """
    from saintvision.config import S01_PENDING

    assert "INV_OIDC_JWKS_URL" not in S01_PENDING
    assert "INV_OIDC_ISSUER" not in S01_PENDING


def test_login_is_not_configured_by_halves():
    """Four values or none. Three of four is a deployment that cannot sign anyone in."""
    from saintvision.config import Settings

    partial = Settings(
        database_url="x",
        tenant_id=str(uuid.uuid4()),
        oidc_issuer="https://idp.example.test",
        oidc_audience="inv",
        oidc_client_ids=(),
        oidc_jwks_file=None,
    )
    assert not partial.login_configured


def test_the_old_placeholder_points_at_the_real_verifier():
    """An import that silently succeeds against nothing is worse than an error."""
    from saintvision.config import SettingUnresolved
    from saintvision.identity import principal as principal_module

    with pytest.raises(SettingUnresolved, match="saintvision.identity.oidc"):
        principal_module.OidcPrincipalVerifier()
