from tools.acceptance_evidence import (
    EXPECTED_NODE_DOCKER_COMPAT_MODES,
    EXPECTED_REMOTE_WORKSPACE_CASE_NAMES,
    EXPECTED_WORKSPACE_UPGRADE_CASE_NAMES,
    case_mode_drift,
    case_name_drift,
)


def test_docker_compat_evidence_rejects_same_count_with_replaced_scenario():
    lines = [f"api=v1.45 mode={mode} outputSHA256=synthetic" for mode in EXPECTED_NODE_DOCKER_COMPAT_MODES]
    assert case_mode_drift(EXPECTED_NODE_DOCKER_COMPAT_MODES, lines) == {
        "missing": [], "unexpected": [], "duplicates": []
    }

    lines[-1] = "api=v1.45 mode=unreviewed outputSHA256=synthetic"
    assert case_mode_drift(EXPECTED_NODE_DOCKER_COMPAT_MODES, lines)["missing"]
    assert case_mode_drift(EXPECTED_NODE_DOCKER_COMPAT_MODES, lines)["unexpected"] == ["unreviewed"]


def test_workspace_upgrade_evidence_rejects_same_count_with_replaced_scenario():
    assert case_name_drift(EXPECTED_WORKSPACE_UPGRADE_CASE_NAMES, EXPECTED_WORKSPACE_UPGRADE_CASE_NAMES) == {
        "missing": [], "unexpected": [], "duplicates": []
    }
    replaced = set(EXPECTED_WORKSPACE_UPGRADE_CASE_NAMES)
    replaced.remove("test_real_trust_mismatch_does_not_stop_node")
    replaced.add("test_unreviewed_scenario")
    assert case_name_drift(EXPECTED_WORKSPACE_UPGRADE_CASE_NAMES, replaced)["missing"] == [
        "test_real_trust_mismatch_does_not_stop_node"
    ]
    assert case_name_drift(EXPECTED_WORKSPACE_UPGRADE_CASE_NAMES, replaced)["unexpected"] == ["test_unreviewed_scenario"]


def test_acceptance_evidence_inventories_reject_duplicate_scenario_rows():
    docker_cases = [f"api=v1.45 mode={mode} outputSHA256=synthetic" for mode in EXPECTED_NODE_DOCKER_COMPAT_MODES]
    docker_cases.append(docker_cases[0])
    assert case_mode_drift(EXPECTED_NODE_DOCKER_COMPAT_MODES, docker_cases)["duplicates"]

    upgrade_cases = list(EXPECTED_WORKSPACE_UPGRADE_CASE_NAMES)
    upgrade_cases.append(upgrade_cases[0])
    assert case_name_drift(EXPECTED_WORKSPACE_UPGRADE_CASE_NAMES, upgrade_cases)["duplicates"]


def test_remote_workspace_evidence_pins_all_scenario_names():
    assert case_name_drift(EXPECTED_REMOTE_WORKSPACE_CASE_NAMES,
                           EXPECTED_REMOTE_WORKSPACE_CASE_NAMES) == {
        "missing": [], "unexpected": [], "duplicates": []
    }
    changed = set(EXPECTED_REMOTE_WORKSPACE_CASE_NAMES)
    changed.remove("output-recovery")
    changed.add("unreviewed")
    assert case_name_drift(EXPECTED_REMOTE_WORKSPACE_CASE_NAMES, changed)["missing"] == [
        "output-recovery"
    ]
    assert case_name_drift(EXPECTED_REMOTE_WORKSPACE_CASE_NAMES, changed)["unexpected"] == [
        "unreviewed"
    ]
