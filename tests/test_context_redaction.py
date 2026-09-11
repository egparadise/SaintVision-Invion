"""A declared redaction is not a performed one.

``ContextItem.redacted`` has always been the caller's claim, and the module said
so honestly while still storing whatever arrived. These tests pin the refusal
that now stands between a credential and a record that is never rewritten.

The honest limit is tested too: recognising is not proving, and a bundle that
passes has not been certified clean.
"""

from __future__ import annotations

import pytest

from saintvision.adapters.conformance import REDACTION_PROBES
from saintvision.adapters.reference import recognised_secrets, redact_text
from saintvision.errors import InvError
from saintvision.services.context import ContextItem, _refuse_recognised_secrets


def _item(content: str, *, declared: bool = True, item_id: str = "itm_probe") -> ContextItem:
    return ContextItem(
        item_id=item_id,
        item_version=1,
        kind="document",
        content=content,
        redacted=declared,
    )


@pytest.mark.parametrize("label,probe", REDACTION_PROBES)
def test_every_conformance_probe_is_refused(label: str, probe: str) -> None:
    """The same probes the adapter conformance suite uses, at the other end.

    An adapter that redacts its output and a context store that accepts
    anything would leave the platform leaking through the second door.
    """
    with pytest.raises(InvError):
        _refuse_recognised_secrets([_item(probe)])


@pytest.mark.parametrize("label,probe", REDACTION_PROBES)
def test_the_refusal_never_echoes_the_secret(label: str, probe: str) -> None:
    """Naming the match would write it into the error, the log and the audit.

    This is the failure that makes a redaction feature worse than none, so it
    is checked for every probe rather than argued for once.
    """
    with pytest.raises(InvError) as raised:
        _refuse_recognised_secrets([_item(probe)])
    message = str(raised.value)
    # The distinctive tail of each probe: the token, the signature, the key body.
    secret = max(probe.replace("\n", " ").split(), key=len)
    assert secret not in message
    # It still has to be useful: the kind and the item are named.
    assert label.replace("_url", "") in message or "private_key" in message
    assert "itm_probe" in message


def test_declaring_redacted_does_not_make_it_so() -> None:
    """The case the refusal exists for: a true claim about untrue content."""
    token = "Authorization: Bearer abcdefghijklmnopqrstuvwxyz012345"
    with pytest.raises(InvError, match="does not make it so"):
        _refuse_recognised_secrets([_item(token, declared=True)])


def test_clean_content_is_accepted_even_when_not_declared_redacted() -> None:
    """The declaration stays a record of what the caller says it did.

    Refusing content because a caller admitted it did not redact would punish
    honesty and teach callers to set the flag.
    """
    _refuse_recognised_secrets([_item("an ordinary note", declared=False)])


def test_content_that_has_been_redacted_passes() -> None:
    """The intended path: redact, then store. The replacement is not a match."""
    for _, probe in REDACTION_PROBES:
        cleaned, changed = redact_text(probe)
        assert changed
        _refuse_recognised_secrets([_item(cleaned)])


def test_the_offending_item_is_identified_by_position() -> None:
    """A rejected bundle has to say which item, not just that one was bad."""
    items = [
        _item("fine", declared=False, item_id="itm_a"),
        _item("fine too", declared=False, item_id="itm_b"),
        _item("key sk-test-000111222333444555666777888999", item_id="itm_c"),
    ]
    with pytest.raises(InvError) as raised:
        _refuse_recognised_secrets(items)
    assert "itm_c" in str(raised.value)
    assert "position 2" in str(raised.value)


def test_recognising_is_not_proving() -> None:
    """The limit, asserted so nothing downstream can read more into a pass.

    A secret in a shape ADR-014's first pass does not carry is stored without
    complaint. That is the honest state of this check, and a caller that treats
    a stored bundle as certified clean is wrong in a way this test records.
    """
    unrecognised = "the database password is hunter2, please keep it safe"
    assert recognised_secrets(unrecognised) == ()
    _refuse_recognised_secrets([_item(unrecognised, declared=True)])
