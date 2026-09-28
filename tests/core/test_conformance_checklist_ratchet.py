"""The conformance check list, held against an independent baseline (G-03 7c).

Codex's review of the design found that the safety net v1.1 claimed did not
exist. Grepping all fifteen names showed it:

* ``implements_every_member``, ``run_returns_a_usable_handle`` and
  ``redact_is_idempotent`` appear **only** in ``adapters/conformance.py``;
  ``tests/`` never names them;
* the other twelve appear only inside ``tests/test_adapters.py`` as
  ``assert "<name>" in {c.name for c in report.failures()}`` -- one direction,
  driven by a deliberately broken adapter;
* nothing anywhere asserted the *set*.

So deleting a ``CheckSpec`` killed no test for three of the names, and *adding*
one killed no test for any of them. That is what this file closes.

The expected values below are a **policy baseline**, copied from ``CHECKLIST``'s
definition and held here rather than read from it. Reading them from the thing
under test would make this file agree with any change, which is the failure mode
it exists to prevent. It is the same kind of baseline as
``tools/definer-policy.json``'s revision or the hosted skip distribution: names
are not judgment logic, so this does not duplicate a decision -- and the runtime
still has one source, ``CHECKLIST``, which is what ``run_conformance`` loops over.

Adding or removing a check is therefore a two-place change. That is the point.
"""

from __future__ import annotations

from saintvision.adapters.conformance import CHECKLIST, CheckSpec, run_conformance
from saintvision.adapters.contract import Capability

#: Every check the contract defines, in the order the suite runs them. Order is
#: part of the baseline because the status route serves ``checks[]`` in this
#: order, so a reshuffle reshuffles a screen.
EXPECTED_CHECKS = (
    "declares_contract_version",
    "implements_every_member",
    "probe_without_credentials",
    "install_reports_without_installing",
    "authenticate_takes_a_reference",
    "run_returns_a_usable_handle",
    "collect_returns_redacted_content",
    "redact_removes_known_secrets",
    "redact_is_idempotent",
    "cancel_returns_a_tri_state",
    "cancel_after_completion_is_not_stopped",
    "attest_does_not_overclaim",
    "declared_server_cancel_actually_stops",
    "declared_usage_is_reported",
    "declared_model_pinning_returns_an_id",
)

#: The three capability-gated checks and the capability each one is gated on.
#: Losing a gate is as much a change as losing a check: an ungated check would
#: run against an adapter that never declared the capability.
EXPECTED_GATED = {
    "declared_server_cancel_actually_stops": Capability.SERVER_SIDE_CANCEL,
    "declared_usage_is_reported": Capability.USAGE_REPORTING,
    "declared_model_pinning_returns_an_id": Capability.MODEL_PINNING,
}


def test_the_checklist_is_exactly_these_fifteen_checks_in_this_order():
    assert tuple(spec.name for spec in CHECKLIST) == EXPECTED_CHECKS


def test_exactly_these_three_checks_are_capability_gated():
    assert {s.name: s.capability for s in CHECKLIST if s.capability is not None} == EXPECTED_GATED


def test_the_other_twelve_are_not_gated():
    ungated = {spec.name for spec in CHECKLIST if spec.capability is None}
    assert ungated == set(EXPECTED_CHECKS) - set(EXPECTED_GATED)
    assert len(ungated) == 12


def test_the_names_are_unique():
    """A duplicated name would make the response ambiguous and the set assertion
    above still pass if it were written as a set rather than a tuple."""
    names = [spec.name for spec in CHECKLIST]
    assert len(names) == len(set(names))


def test_every_entry_is_a_frozen_descriptor_with_a_callable():
    for spec in CHECKLIST:
        assert isinstance(spec, CheckSpec)
        assert callable(spec.run)
        assert spec.capability is None or isinstance(spec.capability, Capability)


def test_running_the_suite_produces_exactly_the_checklist_in_order():
    """``run_conformance`` consumes ``CHECKLIST`` rather than its own literals.

    This is the other half of the ratchet: the baseline pins the list, and this
    pins that the suite runs *that* list. A ``run_conformance`` that went back to
    inline names would pass the baseline test and fail this one.
    """

    class Narrow:
        """An adapter declaring nothing, so all three gated checks are skipped."""

        name = "narrow"
        contract_version = "0.0.0"
        capabilities = frozenset()

        def __getattr__(self, item):
            raise AssertionError(f"the suite should not need {item!r} for this test")

    report = run_conformance(Narrow())
    assert tuple(check.name for check in report.checks) == EXPECTED_CHECKS
    # The gated three are reported as skipped, not as passed.
    skipped = {check.name for check in report.checks if check.skipped}
    assert skipped == set(EXPECTED_GATED)
