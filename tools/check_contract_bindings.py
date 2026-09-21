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

  (3) dead-contract (report-only, SEPARATE grade) -- a contract that is bound (fixture + contract test)
      and is a real contract type (a pydantic schema class or a kernel $def anchor) but that NO backend
      path builds or serves: zero serving references (`validate_contract`/`_checked`, response_model,
      schemas.X/models.X use, .model_validate) and not composed as another schema's field type. Catches
      the purest exists-vs-works gap (schema+fixture+green test, yet nothing produces the response --
      e.g. LegacyProjectCatalogResponse). LIMITATION: serving detection is pattern/grep based, so a
      contract served only through fully dynamic construction that never names the type could read as
      dead (false positive). To avoid crying wolf it is (a) conservative -- any naming or nested-field
      reference counts as alive; (b) restricted to real contract types; (c) report-only (never fails the
      gate), since the fix is a human decision (wire the endpoint vs remove the contract). Verified both
      ways: it flags LegacyProjectCatalogResponse and does NOT flag live or nested-item contracts.

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

    Collect PascalCase names referenced in tests/core/*contract*.py three ways: quoted "X" (literal or
    parametrized validate_contract / FIXTURES key), and attribute form schemas.X / models.X (pydantic
    contract tests pass the model class, not a string). PascalCase avoids field names; callers intersect
    with anchors or schema classes, so stray matches cannot widen the result.
    """
    names: set[str] = set()
    for path in TESTS.rglob("*contract*.py"):
        text = path.read_text(encoding="utf-8")
        names.update(re.findall(r'"([A-Z][A-Za-z]+)"', text))
        names.update(re.findall(r'\b(?:schemas|models)\.([A-Z][A-Za-z]+)', text))
    return names


def _is_served(name: str) -> bool:
    """Does any NON-test backend source build or serve this response? Match specific serving patterns on
    whitespace-folded source (so a multi-line `_checked(\\n "Name",` is caught, and a bare "Name", export
    line is NOT mistaken for one). Conservative for the dead verdict: any of these patterns => alive.

    Patterns: `validate_contract("Name"` / `_checked("Name"` (kernel anchor, single or multi-line);
    `response_model=[schemas.|models.]Name`; attribute use `schemas.Name`/`models.Name` (construction or
    annotation in serving code); `Name.model_validate`. Its own `class Name` definition never matches
    these, so a schema-only contract stays unserved.
    """
    patterns = [
        rf'(?:_checked|validate_contract)\(\s*"{name}"',
        rf'response_model\s*=\s*(?:schemas\.|models\.)?{name}\b',
        rf'\b(?:schemas|models)\.{name}\b',
        rf'\b{name}\.model_validate\b',
    ]
    compiled = [re.compile(p) for p in patterns]
    for base in (ROOT / "src", ROOT / "services"):
        for path in base.rglob("*.py"):
            if "tests" in path.parts or path.name.startswith("test_"):
                continue
            folded = re.sub(r"\s+", " ", path.read_text(encoding="utf-8"))
            if any(c.search(folded) for c in compiled):
                return True
    # Composed/nested: a type used as another schema's field (list[Name] / : Name / Name | ...) is part
    # of a served composite contract, not dead. Checked against schemas.py to avoid the false positive
    # where only a nested item type (e.g. DiscoveryCandidateResponse inside DiscoveryCandidatesResponse)
    # is never named with a schemas. prefix.
    schemas_py = ROOT / "src" / "saintvision" / "api" / "schemas.py"
    if schemas_py.is_file():
        text = schemas_py.read_text(encoding="utf-8")
        if re.search(rf'\[{name}\]|:\s*{name}\b|\b{name}\s*\||\|\s*{name}\b', text):
            return True
    return False


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

    # (3) dead-contract: bound + a real contract type, but no backend code builds/serves it.
    schemas_text = ""
    schemas_py = ROOT / "src" / "saintvision" / "api" / "schemas.py"
    if schemas_py.is_file():
        schemas_text = schemas_py.read_text(encoding="utf-8")
    schema_classes = set(re.findall(r"^class ([A-Z][A-Za-z]+)\b", schemas_text, re.M))
    contract_types = schema_classes | set(anchors)  # pydantic schema classes + kernel $def anchors
    # Dead contracts are a SEPARATE, report-only grade (not a hard gate): detection is confident
    # (0 references) but resolution is a human decision (wire the endpoint vs remove the contract), and
    # a known-pending one must not block the gate. Checks (1)(2) stay hard errors.
    dead = sorted(
        name for name in (bound & contract_types) if not _is_served(name)
    )

    if errors:
        raise SystemExit("FAIL check_contract_bindings:\n  " + "\n  ".join(errors))
    print(
        f"PASS check_contract_bindings: {len(fixtures)} fixtures each referenced by a test; "
        f"{len(enforced)} bound kernel responses each have a serving-anchor test."
    )
    if dead:
        print("WARN dead contracts (report-only; owner must decide wire-or-remove):")
        for name in dead:
            print(
                f"  - {name}: bound (fixture + contract test) but 0 backend references outside its schema "
                f"definition -- no code builds or serves it."
            )


if __name__ == "__main__":
    validate()
