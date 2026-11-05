"""The Backend caller must require the standalone Node attestation result."""

import ast
from pathlib import Path
import textwrap

import pytest


WORKFLOW = Path(__file__).resolve().parents[1] / ".github/workflows/backend.yml"
# Independent acceptance expression: a finalized lifecycle includes verification
# of the distinct Node signature, four observed restarts and no bytecode cache.
VERIFIED_LIFECYCLE = {
    "bytecodeCacheCount": 0,
    "finalized": True,
    "finalizedAttestationVerified": True,
    "installRestartReceipt": True,
    "restartCount": 4,
    "rolledBack": True,
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
