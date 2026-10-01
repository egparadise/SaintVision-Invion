"""Was a person, recently, with something more than a password (S12-BE, #282 §2-1).

A release acceptance vote has to rest on an interactive human authenticating a few
minutes ago. Nothing in a request body can establish that -- a body is what the caller
chose to send -- so this module reads only what a verifier already checked, and it
refuses by default:

* **no fresh-auth claims at all is a refusal, not a gap to fill in later.** Today that
  is every token, because no identity provider in this deployment emits ``auth_time``
  or ``amr`` yet (card 188 is building that supply). The acceptance routes are
  consequently closed, and this module is the reason they are closed *honestly* rather
  than by a flag somebody could flip without the claims arriving;
* ``auth_time`` must be an integer, not in the future, and within 300 seconds of now.
  A future value is refused rather than clamped: a clock that disagrees that much is
  not evidence of anything, and treating it as "very fresh" would reward the error;
* ``amr`` must contain only values from the IANA AMR registry (RFC 8176). An
  unregistered string is refused even when it sounds strong -- ``webauthn`` is the
  example the design names, and the point is that this code cannot know what a string
  it does not recognise means;
* the methods must amount to more than a password: ``mfa``, or ``pwd`` together with
  one of ``otp`` / ``hwk`` / ``swk``. ``pwd`` alone is refused. A token lifetime
  (``exp - iat``) is not a substitute, however short.

What it returns is a ``FreshAuthProof``: the facts a vote row stores. The AMR set
travels as a digest, not as a list, because the vote table must not become a claim
store -- a digest cannot grow a free-text field.
"""

from __future__ import annotations

import datetime as dt
import hashlib
from dataclasses import dataclass

from ..identity.principal import FreshAuth, Principal

#: The IANA "Authentication Method Reference Values" registry (RFC 8176 §2). Written
#: out because the rule is "only registered values", and a rule that referred to a
#: document nobody can check at runtime would be a comment, not a check.
RFC8176_VALUES = frozenset(
    {
        "face",
        "fpt",
        "geo",
        "hwk",
        "iris",
        "kba",
        "mca",
        "mfa",
        "otp",
        "pin",
        "pop",
        "pwd",
        "retina",
        "rba",
        "sc",
        "sms",
        "swk",
        "tel",
        "user",
        "vbm",
        "wia",
    }
)

#: Methods that, with ``pwd``, make the authentication more than a password.
SECOND_FACTORS = frozenset({"otp", "hwk", "swk"})

#: How recently the human must have authenticated (§2-1). Also the length of an
#: accepted proposal's confirmation window (§2-2), which is why it is one constant.
FRESH_AUTH_WINDOW_SECONDS = 300

#: Which rule admitted a vote. Stored on the row, so a later reader learns what was
#: checked rather than assuming today's rule.
ATTESTATION_VERSION = "fresh-interactive-v1"


@dataclass(frozen=True)
class FreshAuthProof:
    """The facts a vote records about the human who cast it."""

    auth_time: int
    amr_sha256: str
    issuer: str
    client_id: str
    #: The earlier of ``auth_time + 300s`` and the token's expiry: after it, a new
    #: fresh-auth proposal is needed rather than a longer-lived one (§2-2).
    window_ends_at: dt.datetime
    attestation_version: str = ATTESTATION_VERSION


class NotInteractiveHuman(Exception):
    """No verified fresh interactive authentication. Carries no claim values.

    The reason is for a log and a test, never for a response: §7 requires that a 403
    not distinguish a missing permission from stale fresh-auth, so the route maps every
    instance of this to the same ``AUTH-0030``.
    """

    def __init__(self, reason: str) -> None:
        super().__init__(reason)
        self.reason = reason


def amr_digest(values: frozenset[str]) -> str:
    """SHA-256 over the normalised set: sorted, comma-joined, UTF-8.

    Normalised so two orderings of the same methods digest identically, and a digest
    rather than the list so this value can be stored beside a vote without the row
    becoming somewhere claims accumulate.
    """
    return hashlib.sha256(",".join(sorted(values)).encode("utf-8")).hexdigest()


def _check_methods(amr: frozenset[str]) -> None:
    if not amr:
        raise NotInteractiveHuman("the token names no authentication method")
    unknown = sorted(amr - RFC8176_VALUES)
    if unknown:
        # Named in the reason for a log, not for a response. An unregistered value is
        # refused even if it sounds strong: this code cannot know what it means.
        raise NotInteractiveHuman(f"unregistered authentication method reference: {unknown}")
    if "mfa" in amr:
        return
    if "pwd" in amr and amr & SECOND_FACTORS:
        return
    raise NotInteractiveHuman("the authentication was not more than a password")


def proof_of_interactive_human(
    principal: Principal, *, now: dt.datetime, window_seconds: int = FRESH_AUTH_WINDOW_SECONDS
) -> FreshAuthProof:
    """The proof, or ``NotInteractiveHuman``. Never a partial answer.

    Raises rather than returning ``None`` because every caller must stop, and an
    optional return invites a caller that forgets to look.
    """
    fresh: FreshAuth | None = getattr(principal, "fresh_auth", None)
    if fresh is None:
        raise NotInteractiveHuman("the verified credential carries no fresh-auth claims")
    if not isinstance(fresh.auth_time, int) or isinstance(fresh.auth_time, bool):
        raise NotInteractiveHuman("auth_time is not an integer")
    if fresh.auth_time <= 0:
        raise NotInteractiveHuman("auth_time is not a time")
    if not isinstance(fresh.expires_at, int) or fresh.expires_at <= 0:
        raise NotInteractiveHuman("the token expiry is not a time")
    if not isinstance(fresh.issuer, str) or not fresh.issuer.startswith("https://"):
        raise NotInteractiveHuman("the verified issuer is not an https issuer")
    if not isinstance(fresh.client_id, str) or not fresh.client_id:
        raise NotInteractiveHuman("the verified client is unnamed")
    if now.tzinfo is None:
        raise NotInteractiveHuman("the request time must say which zone it is in")

    authenticated = dt.datetime.fromtimestamp(fresh.auth_time, tz=dt.timezone.utc)
    if authenticated > now:
        # Not clamped. A clock this wrong is not evidence, and calling a future
        # authentication "very fresh" would make the error useful to an attacker.
        raise NotInteractiveHuman("auth_time is in the future")
    if (now - authenticated).total_seconds() > window_seconds:
        raise NotInteractiveHuman("the interactive authentication is not recent enough")

    _check_methods(frozenset(fresh.amr or frozenset()))

    token_expiry = dt.datetime.fromtimestamp(fresh.expires_at, tz=dt.timezone.utc)
    return FreshAuthProof(
        auth_time=fresh.auth_time,
        amr_sha256=amr_digest(frozenset(fresh.amr)),
        issuer=fresh.issuer,
        client_id=fresh.client_id,
        # The earlier of the two, so neither a long-lived token nor a long window can
        # extend the other (§2-2).
        window_ends_at=min(authenticated + dt.timedelta(seconds=window_seconds), token_expiry),
    )
