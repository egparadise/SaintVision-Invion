"""Was a person, recently, with something more than a password (S12-BE, #282 §2-1).

A release acceptance vote has to rest on an interactive human authenticating a few
minutes ago. Nothing in a request body can establish that -- a body is what the caller
chose to send -- so this module reads only what a verifier already checked.

**It does not decide.** ``saintvision.identity.principal.has_fresh_interactive_auth()``
decides, on the values ``inv.identity.AccessTokens.verify()`` normalised after checking
the signature, issuer, audience, client and expiry. This module is the consumer that
turns a true answer into the facts a vote row stores.

That split is Codex's #286 decision, and it closes a measured defect rather than a
matter of taste. The first version of this module carried its own RFC 8176 allowlist, its
own second-factor rule and its own window constant, and the merge of ``#285`` with
``#286`` put the two policies side by side: ``mfa+sms`` passed this module's registry
check while the canonical allowlist refused it, and the other direction was worse --
this module's reader expected ``identity.issuer``/``client_id``, which the kernel did not
emit, so on the real OIDC path the proof was permanently absent. One representation can
be wrong; two can be wrong in opposite directions at the same time.

So what remains here is narrow:

* ask the canonical predicate, and refuse if it says no. No second opinion, no widened
  registry, no local window;
* read the token provenance the verifier handed over -- issuer, client, expiry -- and
  refuse if any is missing, is not the right type, or has already passed. These are
  receipt facts, not policy inputs, and nothing re-reads a token or a body to get them;
* return the vote's facts, with the AMR set as a **digest** rather than a list, because
  the vote table must not become a claim store.
"""

from __future__ import annotations

import datetime as dt
import hashlib
from dataclasses import dataclass

from ..identity.principal import (
    FRESH_AUTH_MAX_AGE_SECONDS,
    Principal,
    has_fresh_interactive_auth,
)

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
    #: The earlier of ``auth_time + the canonical window`` and the token's expiry: after
    #: it, a new fresh-auth proposal is needed rather than a longer-lived one (§2-2).
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


def proof_of_interactive_human(principal: Principal, *, now: dt.datetime) -> FreshAuthProof:
    """The proof, or ``NotInteractiveHuman``. Never a partial answer.

    Raises rather than returning ``None`` because every caller must stop, and an
    optional return invites a caller that forgets to look.

    The window is not a parameter. A caller that could pass a wider one would be a
    second policy, which is the thing this module stopped being.
    """
    if now.tzinfo is None or now.utcoffset() is None:
        raise NotInteractiveHuman("the request time must say which zone it is in")

    # The one judgement, made in one place. Everything below is bookkeeping about a
    # request that has already been admitted.
    if not has_fresh_interactive_auth(principal, now=now):
        raise NotInteractiveHuman("no verified fresh interactive authentication")

    auth_time = principal.auth_time
    if type(auth_time) is not int:                       # pragma: no cover - predicate holds
        raise NotInteractiveHuman("auth_time is not an integer")

    issuer = principal.verified_token_issuer
    client_id = principal.verified_token_client_id
    expires_at = principal.verified_token_expires_at
    if not isinstance(issuer, str) or not issuer.startswith("https://"):
        raise NotInteractiveHuman("the verified issuer is not an https issuer")
    if not isinstance(client_id, str) or not client_id:
        raise NotInteractiveHuman("the verified client is unnamed")
    if type(expires_at) is not int or expires_at <= 0:
        raise NotInteractiveHuman("the token expiry is not a time")

    token_expiry = dt.datetime.fromtimestamp(expires_at, tz=dt.timezone.utc)
    if token_expiry <= now:
        # A receipt whose token had already expired would record a window that was over
        # before the vote was cast.
        raise NotInteractiveHuman("the verified token had already expired")

    authenticated = dt.datetime.fromtimestamp(auth_time, tz=dt.timezone.utc)
    return FreshAuthProof(
        auth_time=auth_time,
        amr_sha256=amr_digest(frozenset(principal.amr)),
        issuer=issuer,
        client_id=client_id,
        # The earlier of the two, so neither a long-lived token nor a long window can
        # extend the other (§2-2). The window length is the canonical one.
        window_ends_at=min(
            authenticated + dt.timedelta(seconds=FRESH_AUTH_MAX_AGE_SECONDS),
            token_expiry,
        ),
    )
