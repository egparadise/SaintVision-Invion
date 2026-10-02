"""Fail-closed tests for the Card 251 fixed-SHA evidence boundary."""

from __future__ import annotations

from copy import deepcopy
import json
from pathlib import Path
import xml.etree.ElementTree as ET

import pytest

from tools import collect_s08_build_acceptance_evidence as tool


SOURCE_SHA = "a" * 40
TREE_SHA = "b" * 40


def _write_junit(path: Path, specs: list[dict[str, str]], *, failed: str | None = None):
    suite = ET.Element("testsuite", name=path.stem, tests=str(len(specs)))
    for spec in specs:
        case = ET.SubElement(
            suite, "testcase", classname=spec["classname"], name=spec["name"]
        )
        if spec["caseId"] == failed:
            ET.SubElement(case, "failure", message="redacted")
    ET.ElementTree(suite).write(path, encoding="utf-8", xml_declaration=True)


@pytest.fixture
def inputs(tmp_path):
    core = tmp_path / "core-tests.xml"
    runtime = tmp_path / "build-product-runtime-real-pg.xml"
    runtime_specs = [
        spec for spec in tool.CASE_SPECS
        if spec["classname"] == "tests.integration.test_build_product_runtime_real_pg"
    ]
    core_specs = [spec for spec in tool.CASE_SPECS if spec not in runtime_specs]
    _write_junit(core, core_specs)
    _write_junit(runtime, runtime_specs)
    worker = tmp_path / "worker.json"
    worker.write_bytes(
        (Path(__file__).parents[1] / "tools/specs/s08-build-acceptance-worker-v1.json").read_bytes()
    )
    return [core, runtime], worker


def evidence(inputs):
    junit, worker = inputs
    return tool.collect(
        junit_paths=junit,
        worker_path=worker,
        code_sha=SOURCE_SHA,
        checkout_tree_sha=TREE_SHA,
        clean_checkout=True,
        run_id=123,
        run_attempt=1,
    )


def evaluate(value, inputs):
    junit, worker = inputs
    return tool.evaluate(
        value, junit_paths=junit, worker_path=worker, expected_source_sha=SOURCE_SHA
    )


def test_fixed_case_set_is_recomputed_from_both_junit_artifacts(inputs):
    value = evidence(inputs)
    result = evaluate(value, inputs)
    assert result == {
        "schemaVersion": tool.EVALUATION_VERSION,
        "evidenceSha256": tool.sha256(tool.canonical_bytes(value)),
        "sourceSha": SOURCE_SHA,
        "verdict": "MEASURED_PASS",
        "requiredCaseCount": 10,
        "passedCaseCount": 10,
        "failedCaseCount": 0,
        "scoreChangeClaim": False,
    }
    assert {row["caseId"] for row in value["observations"]} == {
        spec["caseId"] for spec in tool.CASE_SPECS
    }


def test_a_real_junit_failure_recomputes_measured_fail(inputs):
    junit, worker = inputs
    runtime_specs = [
        spec for spec in tool.CASE_SPECS
        if spec["classname"] == "tests.integration.test_build_product_runtime_real_pg"
    ]
    _write_junit(junit[1], runtime_specs, failed="two-worker-dispatch-once")
    value = tool.collect(
        junit_paths=junit, worker_path=worker, code_sha=SOURCE_SHA,
        checkout_tree_sha=TREE_SHA, clean_checkout=True, run_id=123, run_attempt=1,
    )
    result = evaluate(value, inputs)
    assert result["verdict"] == "MEASURED_FAIL"
    assert (result["passedCaseCount"], result["failedCaseCount"]) == (9, 1)


def test_every_exact_shape_key_is_required_and_extra_keys_are_refused(inputs):
    baseline = evidence(inputs)
    objects = [
        (baseline, tool.TOP_KEYS),
        (baseline["source"], tool.SOURCE_KEYS),
        (baseline["workerConfiguration"], tool.WORKER_ENVELOPE_KEYS),
        (baseline["workerConfiguration"]["configuration"], tool.WORKER_KEYS),
        (baseline["junitArtifacts"][0], tool.JUNIT_KEYS),
        (baseline["observations"][0], tool.OBSERVATION_KEYS),
        (baseline["claims"], tool.CLAIM_KEYS),
    ]
    for target, keys in objects:
        for key in keys:
            mutated = deepcopy(baseline)
            # Locate the corresponding object by its exact key set in the copy.
            candidates = [mutated, mutated["source"], mutated["workerConfiguration"],
                          mutated["workerConfiguration"]["configuration"],
                          mutated["junitArtifacts"][0], mutated["observations"][0],
                          mutated["claims"]]
            copy_target = next(item for item in candidates if set(item) == set(target))
            copy_target.pop(key)
            with pytest.raises(tool.InvalidEvidence):
                evaluate(mutated, inputs)
        mutated = deepcopy(baseline)
        candidates = [mutated, mutated["source"], mutated["workerConfiguration"],
                      mutated["workerConfiguration"]["configuration"],
                      mutated["junitArtifacts"][0], mutated["observations"][0],
                      mutated["claims"]]
        copy_target = next(item for item in candidates if set(item) == set(target))
        copy_target["unexpected"] = 1
        with pytest.raises(tool.InvalidEvidence):
            evaluate(mutated, inputs)


def test_drop_add_and_duplicate_case_sweep_is_fail_closed(inputs):
    baseline = evidence(inputs)
    for index in range(len(tool.CASE_SPECS)):
        mutated = deepcopy(baseline)
        mutated["observations"].pop(index)
        with pytest.raises(tool.InvalidEvidence):
            evaluate(mutated, inputs)
    added = deepcopy(baseline)
    added["observations"].append({**added["observations"][0], "caseId": "invented"})
    with pytest.raises(tool.InvalidEvidence):
        evaluate(added, inputs)
    duplicated = deepcopy(baseline)
    duplicated["observations"][-1] = deepcopy(duplicated["observations"][0])
    with pytest.raises(tool.InvalidEvidence):
        evaluate(duplicated, inputs)


@pytest.mark.parametrize(
    ("path", "value"),
    [
        (("source", "codeSha"), "c" * 40),
        (("source", "cleanCheckout"), False),
        (("workerConfiguration", "sha256"), "0" * 64),
        (("junitArtifacts", 0, "passedCount"), 0),
        (("observations", 0, "outcome"), "passed"),
        (("claims", "scoreChangeClaim"), True),
        (("claims", "physicalBuilderAcceptance"), "MEASURED_PASS"),
    ],
)
def test_cross_field_or_claim_tampering_is_refused(inputs, path, value):
    mutated = evidence(inputs)
    cursor = mutated
    for key in path[:-1]:
        cursor = cursor[key]
    cursor[path[-1]] = value
    # The observation mutation deliberately assigns its existing value; replace it
    # with an invented status so it is a real mutation.
    if path == ("observations", 0, "outcome"):
        cursor[path[-1]] = "not-run"
    with pytest.raises(tool.InvalidEvidence):
        evaluate(mutated, inputs)


def test_duplicate_json_keys_are_refused_before_shape_validation(tmp_path):
    path = tmp_path / "duplicate.json"
    path.write_text('{"schemaVersion":"a","schemaVersion":"b"}', "utf-8")
    with pytest.raises(tool.InvalidEvidence, match="duplicate JSON key"):
        tool.load_json(path)


def test_collector_refuses_dirty_or_misnamed_inputs(inputs, tmp_path):
    junit, worker = inputs
    with pytest.raises(tool.InvalidEvidence, match="clean checkout"):
        tool.collect(
            junit_paths=junit, worker_path=worker, code_sha=SOURCE_SHA,
            checkout_tree_sha=TREE_SHA, clean_checkout=False, run_id=1, run_attempt=1,
        )
    renamed = tmp_path / "other.xml"
    renamed.write_bytes(junit[0].read_bytes())
    with pytest.raises(tool.InvalidEvidence, match="canonical JUnit"):
        tool.collect(
            junit_paths=[renamed, junit[1]], worker_path=worker, code_sha=SOURCE_SHA,
            checkout_tree_sha=TREE_SHA, clean_checkout=True, run_id=1, run_attempt=1,
        )


def test_worker_configuration_is_bound_to_the_reviewed_canonical_digest(inputs):
    junit, worker = inputs
    mutated = json.loads(worker.read_text("utf-8"))
    mutated["builderAuthority"] = "caller-supplied"
    worker.write_text(json.dumps(mutated), "utf-8")
    with pytest.raises(tool.InvalidEvidence, match="reviewed fixed-SHA lane"):
        tool.collect(
            junit_paths=junit, worker_path=worker, code_sha=SOURCE_SHA,
            checkout_tree_sha=TREE_SHA, clean_checkout=True, run_id=1, run_attempt=1,
        )


def test_core_workflow_exposes_only_an_explicit_exact_sha_evidence_phase():
    workflow = (Path(__file__).parents[1] / ".github/workflows/core.yml").read_text("utf-8")
    assert "run_s08_acceptance:" in workflow
    assert workflow.count("github.event_name == 'workflow_dispatch' && inputs.run_s08_acceptance") == 2
    assert 'test "$(git rev-parse HEAD)" = "$GITHUB_SHA"' in workflow
    assert 'test -z "$(git status --porcelain)"' in workflow
    assert workflow.count("tools/collect_s08_build_acceptance_evidence.py") == 2
    assert "--junit dist/core-tests.xml" in workflow
    assert "--junit dist/build-product-runtime-real-pg.xml" in workflow
    assert "--worker-config tools/specs/s08-build-acceptance-worker-v1.json" in workflow
