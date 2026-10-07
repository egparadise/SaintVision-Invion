from __future__ import annotations

import pytest

from inv.errors import DomainError
from node_delivery_support import deliver_once_then_observe


class ScriptedDelivery:
    def __init__(self, outcomes):
        self.outcomes = iter(outcomes)
        self.calls = []

    def deliver(self, node, envelope, *, observation_only=False):
        self.calls.append((node, envelope, observation_only))
        outcome = next(self.outcomes)
        if isinstance(outcome, Exception):
            raise outcome
        return outcome


def uncertain():
    return DomainError("NODE-0030", "delivery unconfirmed", 503)


def test_uncertain_execution_is_reconciled_without_reexecution():
    delivery = ScriptedDelivery([uncertain(), uncertain(), {"verdict": "failed"}])
    sleeps = []

    result = deliver_once_then_observe(
        delivery,
        {"nodeId": "node-1"},
        {"commandId": "command-1"},
        sleeper=sleeps.append,
    )

    assert result == {"verdict": "failed"}
    assert [call[2] for call in delivery.calls] == [False, True, True]
    assert sleeps == [0.1]


def test_observation_exhaustion_stays_fail_closed_and_never_reexecutes():
    delivery = ScriptedDelivery([uncertain(), uncertain(), uncertain(), uncertain()])

    with pytest.raises(DomainError) as failure:
        deliver_once_then_observe(
            delivery,
            {"nodeId": "node-1"},
            {"commandId": "command-1"},
            sleeper=lambda _: None,
        )

    assert failure.value.code == "NODE-0030"
    assert [call[2] for call in delivery.calls] == [False, True, True, True]


def test_non_uncertainty_failure_is_not_observed_or_retried():
    delivery = ScriptedDelivery([DomainError("AUTH-0030", "denied", 403)])

    with pytest.raises(DomainError) as failure:
        deliver_once_then_observe(
            delivery,
            {"nodeId": "node-1"},
            {"commandId": "command-1"},
        )

    assert failure.value.code == "AUTH-0030"
    assert [call[2] for call in delivery.calls] == [False]
