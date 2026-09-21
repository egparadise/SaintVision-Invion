"""Helpers for validating that machine evidence covers exact named scenarios."""

import re

# These independent acceptance inventories are intentionally pinned. Do not
# derive them from the tests or report being checked: deletion of a scenario
# must remain visible as missing evidence until this list is reviewed.
EXPECTED_NODE_DOCKER_COMPAT_MODES = frozenset({"isolation", "output", "fail", "sleep"})
EXPECTED_WORKSPACE_UPGRADE_CASE_NAMES = frozenset({
    "test_real_upgrade_preserves_credentials_journal_and_replays",
    "test_real_failed_start_restores_prior_container_and_journal",
    "test_real_trust_mismatch_does_not_stop_node",
})
EXPECTED_REMOTE_WORKSPACE_CASE_NAMES = frozenset({
    "python", "ai", "cancel-before-start", "cancel-running",
    "failure", "timeout", "output-recovery",
})


def case_name_drift(expected_names, names):
    names = list(names)
    actual = set(names)
    expected = set(expected_names)
    return {
        "missing": sorted(expected - actual),
        "unexpected": sorted(actual - expected),
        "duplicates": sorted({name for name in names if names.count(name) > 1}),
    }


def case_mode_drift(expected_modes, cases):
    modes = [match.group(1) for case in cases
             if (match := re.search(r"\bmode=([a-z-]+)\b", case))]
    actual = set(modes)
    expected = set(expected_modes)
    return {
        "missing": sorted(expected - actual),
        "unexpected": sorted(actual - expected),
        "duplicates": sorted({mode for mode in modes if modes.count(mode) > 1}),
    }
