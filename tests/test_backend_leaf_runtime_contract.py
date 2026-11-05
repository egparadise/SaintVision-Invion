"""The Backend caller must require the standalone Node attestation result."""

import ast
from pathlib import Path
import textwrap

import pytest


WORKFLOW = Path(__file__).resolve().parents[1] / ".github/workflows/backend.yml"
# Independent :3 contract for two synthetic CLI cycles. Native Go acceptance is
# separate; a forward-only renewal proves rollback refusal, not rollback success.
VERIFIED_LIFECYCLE = {
    "schemaVersion": "saintvision-leaf-rotation-standalone-lifecycle:3",
    "fixtureOnly": True,
    "actualGoAcceptanceAssessed": False,
    "completedNormalCycles": 2,
    "bytecodeCacheCount": 0,
    "finalized": True,
    "finalizedAttestationVerified": True,
    "installRestartReceipt": True,
    "restartCount": 4,
    "rolledBack": False,
    "rollbackRejected": True,
}


def _validate_as_workflow(value):
    text = WORKFLOW.read_text(encoding="utf-8")
    start = text.index("          python - <<'PY'\n") + len("          python - <<'PY'\n")
    end = text.index("          PY", start)
    tree = ast.parse(textwrap.dedent(text[start:end]))
    ast.increment_lineno(tree, text[:start].count("\n"))
    checks = [statement for statement in tree.body if isinstance(statement, ast.Assert)
              and any(isinstance(node, ast.Name) and node.id == "lifecycle"
                      for node in ast.walk(statement))]
    assert checks, "Backend must enforce the measured lifecycle result"
    # Execute only caller assertions, never workflow imports, reads or commands.
    exec(compile(ast.Module(body=checks, type_ignores=[]), str(WORKFLOW), "exec"),
         {"lifecycle": value})


def test_backend_accepts_complete_verified_standalone_lifecycle_contract():
    _validate_as_workflow(dict(VERIFIED_LIFECYCLE))


@pytest.mark.parametrize("proof", ["missing", False, 1, "true"])
def test_backend_refuses_absent_or_failed_node_finalization_attestation(proof):
    value = dict(VERIFIED_LIFECYCLE)
    if proof == "missing":
        del value["finalizedAttestationVerified"]
    else:
        value["finalizedAttestationVerified"] = proof
    with pytest.raises(AssertionError):
        _validate_as_workflow(value)


@pytest.mark.parametrize("field,bad", [
    (field, bad)
    for field in ("finalized", "finalizedAttestationVerified", "installRestartReceipt", "rollbackRejected", "fixtureOnly")
    for bad in (1, 1.0, False, "true", None)
] + [
    (field, bad)
    for field in ("rolledBack", "actualGoAcceptanceAssessed")
    for bad in (0, 0.0, True, "false", None)
] + [
    ("restartCount", bad) for bad in (4.0, True, False, "4", None)
] + [
    ("bytecodeCacheCount", bad) for bad in (False, 0.0, True, "0", None)
] + [
    ("completedNormalCycles", bad) for bad in (2.0, True, False, "2", None)
] + [
    ("schemaVersion", bad) for bad in (
        "saintvision-leaf-rotation-standalone-lifecycle:2",
        "saintvision-leaf-rotation-standalone-lifecycle:4", 3, True, None,
    )
])
def test_backend_rejects_wrong_types_for_every_lifecycle_field(field, bad):
    value = dict(VERIFIED_LIFECYCLE)
    value[field] = bad
    with pytest.raises(AssertionError):
        _validate_as_workflow(value)


def test_versioned_fixture_contract_matches_actual_producer_predicate():
    from check_leaf_rotation_standalone_lifecycle import validate_result

    assert validate_result(dict(VERIFIED_LIFECYCLE)) == VERIFIED_LIFECYCLE
    _validate_as_workflow(dict(VERIFIED_LIFECYCLE))


@pytest.mark.parametrize("field", list(VERIFIED_LIFECYCLE))
def test_backend_requires_the_exact_lifecycle_key_set(field):
    missing = dict(VERIFIED_LIFECYCLE)
    del missing[field]
    with pytest.raises(AssertionError):
        _validate_as_workflow(missing)
    extra = {**VERIFIED_LIFECYCLE, "unrecognized": True}
    with pytest.raises(AssertionError):
        _validate_as_workflow(extra)
