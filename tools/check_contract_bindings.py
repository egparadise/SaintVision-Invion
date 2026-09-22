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
      e.g. a bound response model with no producer). LIMITATION: serving detection is pattern/grep based, so a
      contract served only through fully dynamic construction that never names the type could read as
      dead (false positive). To avoid crying wolf it is (a) conservative -- any naming or nested-field
      reference counts as alive; (b) restricted to real contract types; (c) report-only (never fails the
      gate), since the fix is a human decision (wire the endpoint vs remove the contract). Verified both
      ways: it flagged the now-removed legacy project envelope and does NOT flag live or nested-item contracts.

  (2b) replay-anchor inventory -- the twelve audited idempotency replay branches must retain the
      expected ``validate_contract(..., prior)`` call. This catches deletion of a replay guard,
      but it does not by itself prove that the guard has runtime weight; the negative persisted-prior
      test is deliberately kept separate for that proof.

What this does NOT check (needs human judgment -- see the governance doc): whether a serving-anchor test
actually exercises every replay branch and fails when the anchor is removed (the runtime-weight question);
whether an anchor sits on the serving path vs an ingestion/verify-worker path (the ModelManifest lesson);
whether a value that is shape-valid points at something real (the placeholder-identifier class).
saintvision responses are anchored by FastAPI response_model (framework-enforced) and are out of this
kernel-anchor check.
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
    "node_resource_usage.py",  # Claude: GET .../nodes/{node_id}/resource-usage (decision #2 A)
]
# Argument names that mark a validate_contract call as validating a RESPONSE (not an input/id).
RESPONSE_ARGS = {"result", "body", "response", "envelope", "evidence", "payload", "snapshot", "receipt", "prior"}

# Replay guards are a stricter subset of serving anchors.  A stored idempotency
# result is an untrusted persisted wire value, so each audited branch must keep
# its contract check immediately after ``prior is not None``.  Counting these
# guards prevents a refactor from silently leaving only the fresh path checked.
REPLAY_GUARD_COUNTS = {
    "control.py": {"ControlRunView": 1, "ControlRunDetail": 1},
    "business_handoff.py": {
        "BusinessEditLockView": 1,
        "BusinessBindingView": 1,
        "BusinessEditLockReleaseView": 1,
    },
    "approvals.py": {"ApprovalView": 1},
    "workspace_api.py": {"WorkspacePrepareResult": 1, "WorkspaceEnqueueResult": 2},
    "workspace_start.py": {
        "WorkspaceStartPrepareResult": 1,
        "WorkspaceStartEnqueueResult": 2,
    },
}

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


def _anchor_sites() -> dict[str, list[str]]:
    """type -> module basename PER anchor call-site (NOT deduped). len() is the site count.

    `_kernel_response_anchors` keeps one module per type (setdefault), so "N types each have a serving-
    anchor test" says nothing about types anchored at MULTIPLE sites where only one site is tested
    (e.g. EvidenceEnvelope is validated on 5 serving paths). This exposes the site count so the passing
    line cannot read broader than the sites actually covered. Site->test mapping is not statically
    decidable (same limit as branch granularity), so per-site test coverage is deferred, not claimed.
    """
    # Scan ALL inv modules (not just SERVING_MODULES) so the site count is not undercounted: a response
    # like EvidenceEnvelope is anchored on 5 serving paths, 4 of them outside SERVING_MODULES. The GATE
    # stays serving-module-scoped (`enforced`), but the reported site count reflects the true total.
    sites: dict[str, list[str]] = {}
    if not INV.is_dir():
        return sites
    for path in sorted(INV.glob("*.py")):
        joined = re.sub(r"\n\s*", " ", path.read_text(encoding="utf-8"))
        for m in _CHECKED.finditer(joined):
            sites.setdefault(m.group(1), []).append(path.name[:-3])
        for m in _VALIDATE.finditer(joined):
            if m.group(2) in RESPONSE_ARGS:
                sites.setdefault(m.group(1), []).append(path.name[:-3])
    return sites


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


def _replay_guard_errors() -> list[str]:
    """Return missing/mismatched checks on the twelve audited replay branches.

    This is intentionally source-level: it is a guard against deleting an
    otherwise hard-to-reach replay check during refactoring.  Runtime weight
    is supplied by the negative-prior test in
    ``tests/core/test_run_approval_observation_contract.py``.
    """
    errors: list[str] = []
    for filename, expected in REPLAY_GUARD_COUNTS.items():
        path = INV / filename
        text = re.sub(r"\n\s*", " ", path.read_text(encoding="utf-8"))
        for contract, count in expected.items():
            pattern = rf"if prior is not None:\s+validate_contract\(\s*\"{contract}\"\s*,\s*prior\s*\)"
            actual = len(re.findall(pattern, text))
            if actual != count:
                errors.append(
                    f"(2b) replay guard {filename}:{contract} expected {count}, found {actual}"
                )
    return errors


def validate(root: Path = ROOT) -> None:
    errors: list[str] = []

    errors.extend(_replay_guard_errors())

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

    sites = _anchor_sites()
    enforced_sites = sum(len(sites.get(n, [])) for n in enforced)
    multi_enforced = {n: sites[n] for n in enforced if len(sites.get(n, [])) > 1}
    multi_all = {t: ms for t, ms in sites.items() if len(ms) > 1}

    if errors:
        raise SystemExit("FAIL check_contract_bindings:\n  " + "\n  ".join(errors))
    print(
        f"PASS check_contract_bindings: {len(fixtures)} fixtures each referenced by a test; "
        f"{len(enforced)} bound kernel response TYPES each have >=1 serving-anchor test "
        f"(counted PER TYPE, not per anchor SITE: those types occupy {enforced_sites} anchor sites; a "
        f"multi-site type counts covered even if only one site is tested -- site-level weight is not "
        f"decidable here, use tools/check_anchor_weight.py + the mutation harness); "
        f"{sum(sum(v.values()) for v in REPLAY_GUARD_COUNTS.values())} replay guards present."
    )
    if multi_all:
        print(
            "  UNIT NOTE: TYPE count <= SITE count. Multi-site types (per-type coverage can mask an "
            "untested site): "
            + ", ".join(f"{t}({len(ms)} sites: {sorted(set(ms))})" for t, ms in sorted(multi_all.items()))
        )
        print(
            "  (Reporting sites is not a regression -- the TYPE number never meant 'sites verified'; "
            "this makes the counting unit explicit. EvidenceEnvelope-class multi-site anchors are why.)"
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
