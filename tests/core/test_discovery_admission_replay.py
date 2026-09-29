"""Admission must never mint two live bootstrap credentials for one candidate."""

from __future__ import annotations

import datetime as dt
from types import SimpleNamespace
import uuid

import pytest

from saintvision.errors import GRAPH_INVALID_TRANSITION, InvError
from saintvision.identity.tokens import IssuedToken
from saintvision.services import discovery


NOW = dt.datetime(2026, 9, 29, 11, 0, tzinfo=dt.timezone.utc)
TENANT = uuid.UUID("52b101ad-acb1-4132-8e08-69fdad71d002")


class _EmptyScalars:
    def all(self):
        return []


class _Session:
    def __init__(self, row):
        self.row = row
        self.locked = False

    def scalar(self, statement):
        self.locked = statement._for_update_arg is not None
        return self.row

    def scalars(self, _statement):
        return _EmptyScalars()

    def add(self, _value):
        return None

    def flush(self):
        return None


def test_repeat_admission_is_locked_and_rejected_before_a_second_token(monkeypatch):
    row = SimpleNamespace(
        tenant_id=TENANT,
        state="candidate",
        admitted_by_user_id=None,
    )
    session = _Session(row)
    issued = []

    def issue(_session, **_kwargs):
        issued.append("issued")
        return IssuedToken(
            token_id="bootstrap_token_test",
            secret="returned-once",
            expires_at=NOW + dt.timedelta(minutes=15),
        )

    monkeypatch.setattr(discovery, "issue_bootstrap_token", issue)

    first = discovery.admit_candidate(
        session,
        tenant_id=TENANT,
        announcement_id="announcement_test",
        admitted_by_user_id="user_test",
        now=NOW,
    )
    with pytest.raises(InvError) as caught:
        discovery.admit_candidate(
            session,
            tenant_id=TENANT,
            announcement_id="announcement_test",
            admitted_by_user_id="user_test",
            now=NOW,
        )

    assert session.locked is True
    assert first.secret == "returned-once"
    assert issued == ["issued"]
    assert caught.value.code == GRAPH_INVALID_TRANSITION
    assert caught.value.status == 409
    assert caught.value.retryable is False
