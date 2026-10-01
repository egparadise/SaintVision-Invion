from __future__ import annotations

import datetime as dt
import json
import time
from contextlib import nullcontext
from types import SimpleNamespace
from uuid import uuid4

import pytest

from inv.errors import DomainError
from saintvision.api.schemas import FreshAuthenticationStepUpRequest
from saintvision.identity.principal import Principal, has_fresh_interactive_auth
from jwt_support import jwt_fixture


UTC = dt.timezone.utc
NOW = dt.datetime(2026, 10, 1, 12, 0, 0, tzinfo=UTC)


def _principal(*, auth_time=None, amr=(), verified=True):
    return Principal(
        user_id="usr_fresh",
        tenant_id=uuid4(),
        external_subject="oidc:fresh",
        verified_fresh_auth_claims=verified,
        auth_time=auth_time,
        amr=frozenset(amr),
    )


@pytest.mark.parametrize(
    "amr",
    [
        ("mfa",),
        ("pwd", "otp"),
        ("pwd", "hwk"),
        ("pwd", "swk"),
    ],
)
def test_exact_interactive_combinations_are_fresh(amr):
    assert has_fresh_interactive_auth(
        _principal(auth_time=int(NOW.timestamp()) - 300, amr=amr), now=NOW
    )


@pytest.mark.parametrize(
    ("auth_time", "amr", "verified"),
    [
        (None, ("mfa",), True),
        (int(NOW.timestamp()) + 1, ("mfa",), True),
        (int(NOW.timestamp()) - 301, ("mfa",), True),
        (int(NOW.timestamp()), (), True),
        (int(NOW.timestamp()), ("pwd",), True),
        (int(NOW.timestamp()), ("webauthn",), True),
        (int(NOW.timestamp()), ("otp",), True),
        (int(NOW.timestamp()), ("mfa",), False),
        (str(int(NOW.timestamp())), ("mfa",), True),
        (float(int(NOW.timestamp())), ("mfa",), True),
        (-1, ("mfa",), True),
    ],
)
def test_missing_stale_future_or_noninteractive_proof_is_not_fresh(auth_time, amr, verified):
    assert not has_fresh_interactive_auth(
        _principal(auth_time=auth_time, amr=amr, verified=verified), now=NOW
    )


def test_only_signature_verified_claims_enter_the_access_identity(tmp_path):
    """The verifier normalises shape. It no longer judges which methods count (#286 F1).

    It used to erase the claims when a value fell outside its own allowlist, which made two
    allowlists and moved the real refusal here -- Codex added ``sms`` to the product set
    alone and 59 tests still passed. So the cases below are all about *shape*, and the
    unknown-method case moved to the test under it.
    """
    identity = jwt_fixture(tmp_path, str(uuid4()))
    fixed_now = int(time.time())

    accepted = identity.auth.verify(
        identity.token(claims={"auth_time": fixed_now, "amr": ["pwd", "otp"]})
    )
    assert accepted.auth_time == fixed_now
    assert accepted.amr == ("otp", "pwd")

    for claims in (
        {},
        {"auth_time": True, "amr": ["mfa"]},
        {"auth_time": str(fixed_now), "amr": ["mfa"]},
        {"auth_time": float(fixed_now), "amr": ["mfa"]},
        {"auth_time": fixed_now, "amr": "mfa"},
        {"auth_time": fixed_now, "amr": ["pwd", "pwd"]},
        # Shape, not policy: an empty token, one that is too long, one that is not a
        # printable token, a list that is too long, and a non-string member.
        {"auth_time": fixed_now, "amr": [""]},
        {"auth_time": fixed_now, "amr": ["a" * 33]},
        {"auth_time": fixed_now, "amr": ["mfa pwd"]},
        {"auth_time": fixed_now, "amr": [f"m{index}" for index in range(9)]},
        {"auth_time": fixed_now, "amr": ["mfa", 3]},
    ):
        value = identity.auth.verify(identity.token(claims=claims))
        assert value.auth_time is None
        assert value.amr == ()


@pytest.mark.parametrize("unknown", ["webauthn", "sms", "kba", "tel"])
def test_an_unknown_method_reaches_the_identity_and_is_refused_by_the_policy(tmp_path, unknown):
    """#286 F1: the verifier passes it on, and the one policy refuses it.

    This is the half that was missing. With the value filtered at the verifier, the product
    allowlist could be widened without any test noticing -- the refusal was happening
    somewhere else. Now the claim arrives verified, and ``has_fresh_interactive_auth`` is
    what says no, which is a thing this test can hold.
    """
    identity = jwt_fixture(tmp_path, str(uuid4()))
    fixed_now = int(time.time())
    value = identity.auth.verify(
        identity.token(claims={"auth_time": fixed_now, "amr": ["mfa", unknown]})
    )
    assert value.auth_time == fixed_now
    assert set(value.amr) == {"mfa", unknown}, "the verifier normalises, it does not filter"

    principal = _principal(auth_time=fixed_now, amr=value.amr)
    assert not has_fresh_interactive_auth(
        principal, now=dt.datetime.fromtimestamp(fixed_now, tz=UTC)
    ), "the canonical predicate is what refuses an unknown method"


def test_the_amr_allowlist_lives_in_exactly_one_place():
    """The drift this closes, pinned by name rather than by behaviour.

    A behavioural test cannot see a second allowlist that happens to agree. These
    assertions can: the kernel must carry no value set at all, and the product's set must
    be exactly the five values -- so adding ``sms`` to it is a one-line change that fails
    here and in the two tests above.
    """
    from pathlib import Path

    from inv import identity as kernel
    from saintvision.identity import principal as policy

    assert not hasattr(kernel, "_FRESH_AUTH_AMR_VALUES")
    source = Path(kernel.__file__).read_text(encoding="utf-8")
    for value in ("mfa", "pwd", "otp", "hwk", "swk"):
        assert f'"{value}"' not in source, f"the kernel still names {value}"
    assert policy.FRESH_AUTH_AMR_VALUES == frozenset({"mfa", "pwd", "otp", "hwk", "swk"})
    assert "sms" not in policy.FRESH_AUTH_AMR_VALUES
    assert "webauthn" not in policy.FRESH_AUTH_AMR_VALUES
    assert policy.FRESH_AUTH_SECOND_FACTORS == frozenset({"otp", "hwk", "swk"})


def test_tampered_signature_cannot_supply_fresh_auth_claims(tmp_path):
    identity = jwt_fixture(tmp_path, str(uuid4()))
    token = identity.token(claims={"auth_time": int(time.time()), "amr": ["mfa"]})
    header, payload, signature = token.split(".")
    offset = len(signature) // 2
    replacement = "A" if signature[offset] != "A" else "B"
    tampered_signature = signature[:offset] + replacement + signature[offset + 1 :]
    with pytest.raises(DomainError):
        identity.auth.verify(".".join((header, payload, tampered_signature)))


def test_step_up_redirect_contract_is_exact_and_has_no_credential_fields():
    assert FreshAuthenticationStepUpRequest.model_validate(
        {"prompt": "login", "max_age": 300}
    ).model_dump(by_alias=True) == {"prompt": "login", "max_age": 300}
    for value in (
        {"prompt": "none", "max_age": 300},
        {"prompt": "login", "max_age": 301},
        {"prompt": "login"},
        {"prompt": "login", "max_age": 300, "token": "secret"},
    ):
        with pytest.raises(ValueError):
            FreshAuthenticationStepUpRequest.model_validate(value)

    schema = FreshAuthenticationStepUpRequest.model_json_schema(by_alias=True)
    assert schema["additionalProperties"] is False
    assert schema["required"] == ["prompt", "max_age"]
    assert schema["properties"]["prompt"]["const"] == "login"
    assert schema["properties"]["max_age"]["const"] == 300
    assert "token" not in json.dumps(schema)


def test_freshness_policy_rejects_naive_time_and_wider_windows():
    principal = _principal(auth_time=int(NOW.timestamp()), amr=("mfa",))
    with pytest.raises(ValueError, match="timezone-aware"):
        has_fresh_interactive_auth(principal, now=NOW.replace(tzinfo=None))
    with pytest.raises(ValueError, match="1..300"):
        has_fresh_interactive_auth(principal, now=NOW, max_age_seconds=301)


def test_oidc_principal_receives_claims_only_from_the_verified_identity(monkeypatch):
    from saintvision.identity import oidc
    from saintvision.db import session as session_module

    tenant = uuid4()
    subject = "oidc:verified-fresh"
    captured = {}

    class _Session:
        def __enter__(self):
            return self

        def __exit__(self, *args):
            return False

        def begin(self):
            return nullcontext()

    class _Tokens:
        def verify(self, credential):
            assert credential == "signed-token"
            return SimpleNamespace(
                principal=SimpleNamespace(tenant_id=str(tenant), subject_id=subject),
                auth_time=123,
                amr=("otp", "pwd"),
            )

    def _principal_for_subject(_session, **kwargs):
        captured.update(kwargs)
        return _principal(
            auth_time=kwargs["auth_time"],
            amr=kwargs["amr"],
            verified=kwargs["verified_fresh_auth_claims"],
        )

    monkeypatch.setattr(oidc, "principal_for_subject", _principal_for_subject)
    monkeypatch.setattr(session_module, "tenant_scope", lambda *_args: nullcontext())
    result = oidc.OidcPrincipalVerifier(_Tokens(), _Session).verify("signed-token")

    assert result.verified_fresh_auth_claims is True
    assert result.auth_time == 123
    assert result.amr == frozenset({"pwd", "otp"})
    assert captured["tenant_id"] == tenant
    assert captured["subject"] == subject
