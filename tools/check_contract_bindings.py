"""Guard against formal-only contract bindings re-accumulating.

Two structural checks, no human judgment required:

  (1) fixture coverage -- every contracts/fixtures/*.json is referenced by at least one file under
      tests/ (a contract test exists; a fixture with no test is a binding in name only).

  (2) serving-anchor coverage -- every response contract that (a) has a shared fixture+contract test
      AND (b) is validated on a KERNEL serving path (`_checked("X", ...)` or
      `validate_contract("X", <response-arg>)`) must have a serving-anchor test: some file under tests/
      that both names "X" and imports the serving module. This is the "exists != works" question turned
      into structure -- a new bound kernel response without a serving-anchor test is reported, so
      bucket 2 (anchor present, but removing it breaks nothing) cannot silently re-accumulate.

What this does NOT check (needs human judgment -- see the governance doc): whether a serving-anchor test
actually exercises the path and fails when the anchor is removed (bears-weight); whether an anchor sits
on the serving path vs an ingestion/verify-worker path (the ModelManifest lesson); whether a value that
is shape-valid points at something real (the placeholder-identifier class). saintvision responses are
anchored by FastAPI response_model (framework-enforced) and are out of this kernel-anchor check.
"""
from __future__ import annotations

import re
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
FIXTURES = ROOT / "contracts" / "fixtures"
TESTS = ROOT / "tests"
INV = ROOT / "services" / "control-plane" / "src" / "inv"

# Kernel modules that build and serve a response to the frontend.
SERVING_MODULES = [
    "result_view.py", "model_view.py", "storage_view.py", "workspace_editor.py",
    "control.py", "shards.py", "app.py",
]
# Argument names that mark a validate_contract call as validating a RESPONSE (not an input/id).
RESPONSE_ARGS = {"result", "body", "response", "envelope", "evidence", "payload", "snapshot", "receipt", "prior"}

# `_checked(` and `validate_contract(` may put the name on the next line; join for scanning.
_CHECKED = re.compile(r'_checked\(\s*"([A-Za-z]+)"')
_VALIDATE = re.compile(r'validate_contract\(\s*"([A-Za-z]+)"\s*,\s*([a-z_]+)\s*\)')


def _kernel_response_anchors() -> dict[str, str]:
    """Map response contract name -> serving module basename (kernel serving anchors only)."""
    anchors: dict[str, str] = {}
    for name in SERVING_MODULES:
        path = INV / name
        if not path.is_file():
            continue
        text = path.read_text(encoding="utf-8")
        joined = re.sub(r"\n\s*", " ", text)  # fold multi-line calls onto one line
        for m in _CHECKED.finditer(joined):
            anchors.setdefault(m.group(1), name)
        for m in _VALIDATE.finditer(joined):
            if m.group(2) in RESPONSE_ARGS:
                anchors.setdefault(m.group(1), name)
    return anchors


def _bound_contract_names() -> set[str]:
    """Contract names that appear in a contract test (paired with a shared fixture there).

    Collect any PascalCase quoted token in tests/core/*contract*.py -- this catches literal
    validate_contract("X", ...) AND parametrized cases where the name is passed as a variable but still
    appears as a quoted string in the parametrize table or a FIXTURES dict key. PascalCase avoids field
    names; the caller intersects with kernel anchors, so stray matches cannot widen the enforced set.
    """
    names: set[str] = set()
    for path in TESTS.rglob("*contract*.py"):
        text = path.read_text(encoding="utf-8")
        names.update(re.findall(r'"([A-Z][A-Za-z]+)"', text))
    return names


def _tests_naming(name: str) -> list[Path]:
    return [p for p in TESTS.rglob("*.py") if re.search(rf'"{name}"', p.read_text(encoding="utf-8"))]


def validate(root: Path = ROOT) -> None:
    errors: list[str] = []

    fixtures = sorted(FIXTURES.glob("*.json"))
    all_test_text = {p: p.read_text(encoding="utf-8") for p in TESTS.rglob("*.py")}
    for fx in fixtures:
        if not any(fx.name in text for text in all_test_text.values()):
            errors.append(f"(1) fixture with no test references it: contracts/fixtures/{fx.name}")

    anchors = _kernel_response_anchors()
    bound = _bound_contract_names()
    enforced = sorted(bound & set(anchors))  # bound AND kernel-serving-anchored
    for name in enforced:
        module = anchors[name].removesuffix(".py")
        has_serving_test = any(
            (f'"{name}"' in text) and re.search(rf"\b(from inv\.{module} import|from inv import {module}|inv\.{module})\b", text)
            for text in all_test_text.values()
        )
        if not has_serving_test:
            errors.append(
                f"(2) bound kernel response '{name}' (anchor in {anchors[name]}) has no serving-anchor "
                f"test: no test both names it and imports inv.{module}"
            )

    if errors:
        raise SystemExit("FAIL check_contract_bindings:\n  " + "\n  ".join(errors))
    print(
        f"PASS check_contract_bindings: {len(fixtures)} fixtures each referenced by a test; "
        f"{len(enforced)} bound kernel responses each have a serving-anchor test."
    )


if __name__ == "__main__":
    validate()
