"""Static rejection-coverage tiers for kernel serving anchors (report-only proxy for "bears weight").

The gap this addresses (recorded 2026-09-22): `check_contract_bindings.py` proves a serving anchor
EXISTS and that SOME test names it and imports the serving module. It does NOT prove the test actually
exercises rejection -- and mutation testing showed a spectrum: some serving-anchor tests only assert the
anchor was *called* (they `monkeypatch.setattr` the validator to a name-recorder, which structurally
cannot test rejection), while others feed an invalid response through the real serving method and assert
the contract error. Removing the validator's effect is invisible to the first kind. See
`docs/vault/30_Development/History/2026-09-22_서빙앵커_무게_전수변이_부류확장_Claude.md`.

What this tool does (STATIC, report-only): classify each kernel serving anchor type into
  - rejection-tested : some serving-anchor test lets the REAL validator run and asserts it raises
                       (`pytest.raises(...)` present, validator NOT replaced) -- weight is plausibly tested.
  - called-only      : the serving-anchor test(s) REPLACE the validator (`setattr(mod, "validate_contract"
                       | "_checked", ...)`) and never assert rejection -- proves called, not rejects.
  - no-serving-test  : the anchor is on a serving path but no test both names the type and imports the
                       serving module (a genuine blind spot; e.g. EvidenceEnvelope).

What it deliberately does NOT do (and why it is report-only, not a gate):
  - It does NOT prove runtime weight. Only mutation proves "removing the anchor fails a test." The ground
    truth remains the on-demand mutation harness run in an ISOLATED worktree (procedure:
    `docs/vault/40_Governance/앵커_무게_검증_절차.md`). This static proxy is the cheap CI-able signal that
    catches the common `called-only` / `no-serving-test` cases without touching product code.
  - `called-only` is NOT by itself a defect: a type may still have rejection covered at the contract level
    (a `*_contract.py` test calling `validate_contract` on a broken fixture). The report says "serving-path
    rejection untested," not "wrong." A human decides whether to add a serving rejection test.
  - Replay-branch guard PRESENCE is already checked by `check_contract_bindings.py` (2b); replay runtime
    weight is supplied by negative-persisted-prior tests. This tool does not re-check those.

SCOPE (stated in the output, and why it is narrow by default): this tool scans the 7 frontend-facing
view/serving modules (SERVING_MODULES) -- the same "serving anchor" surface check_contract_bindings uses.
It answers ONE question: does a frontend-facing response's REJECTION get tested. It is kept narrow on
purpose. Replay-branch idempotency guards live largely in OTHER modules (containment, workspace_api,
workspace_start, business_handoff); their PRESENCE is already owned by check_contract_bindings 2b and
their runtime weight by negative-persisted-prior tests. Widening SERVING_MODULES (via --modules) pulls in
those non-serving anchors, but the recorder-vs-rejection signal is calibrated to the serving/view test
style, so widening would make this tool claim a question it does not answer well and would duplicate 2b.
The output therefore MEASURES and prints what it did not scan (out-of-scope replay anchors) so the numbers
never read broader than the surface examined. Two known blind spots, both printed: (1) module scope above;
(2) TYPE granularity -- it classifies by response type, not by branch, so a type can read rejection-tested
on its fresh path while its replay branch is untested (that gap is 2b + negative-prior tests, not here).

Detection is per-test-function pattern matching (a recorder helper does not poison a sibling rejection
function). Known false-negative: a "serving-anchor test" here must NAME the type literally (inherited
from check_contract_bindings' definition), so a rejection test that drives the serving method but never
mentions the type string reads as no-serving-test/called-only. Real rejection tests name the contract in
their `pytest.raises(match="X: invalid contract")`, so this holds in practice, but it is a heuristic.
Report-only by design; `--strict` exits 1 for opt-in local use. Cross-validated 2026-09-22: on the repo it
reproduced the mutation ground truth (7 rejection-tested / 7 called-only / 1 no-serving-test) exactly.
"""
from __future__ import annotations

import argparse
import re
import sys
from pathlib import Path

DEFAULT_ROOT = Path(__file__).resolve().parents[1]

SERVING_MODULES = [
    "result_view.py", "model_view.py", "storage_view.py", "workspace_editor.py",
    "control.py", "shards.py", "app.py",
]
RESPONSE_ARGS = {
    "result", "body", "response", "envelope", "evidence", "payload", "snapshot", "receipt", "prior",
}
_CHECKED = re.compile(r'_checked\(\s*"([A-Za-z]+)"')
_VALIDATE = re.compile(r'validate_contract\(\s*"([A-Za-z]+)"\s*,\s*([a-z_]+)\s*\)')
# A test that REPLACES the validator with its own callable proves "called", never "rejects".
_REPLACES_VALIDATOR = re.compile(
    r'setattr\(\s*[^,]+,\s*["\'](?:validate_contract|_checked)["\']'
)
_RAISES = re.compile(r'pytest\.raises\(')


# Replay-branch anchor: a stored-prior idempotency guard. Static pattern (folded onto one line).
_REPLAY_SITE = re.compile(
    r'if [^:]*prior[^:]*is not None:\s*validate_contract\(\s*"([A-Za-z]+)"\s*,\s*prior\s*\)'
)


def _replay_types(text: str) -> set[str]:
    """Response types validated on a `prior is not None:` replay branch in this module text."""
    joined = re.sub(r"\n\s*", " ", text)
    return {m.group(1) for m in _REPLAY_SITE.finditer(joined)}


def serving_anchor_types(inv_dir: Path, modules: list[str] = SERVING_MODULES) -> dict[str, set[str]]:
    """type name -> set of serving module basenames that anchor it (within `modules`)."""
    anchors: dict[str, set[str]] = {}
    for name in modules:
        path = inv_dir / name
        if not path.is_file():
            continue
        joined = re.sub(r"\n\s*", " ", path.read_text(encoding="utf-8"))
        for m in _CHECKED.finditer(joined):
            anchors.setdefault(m.group(1), set()).add(name[:-3])
        for m in _VALIDATE.finditer(joined):
            if m.group(2) in RESPONSE_ARGS:
                anchors.setdefault(m.group(1), set()).add(name[:-3])
    return anchors


def scope_report(inv_dir: Path, modules: list[str] = SERVING_MODULES) -> dict:
    """What the tool looked at and, measured from source, what it did NOT -- so the numbers cannot read
    broader than they are. Out-of-scope replay anchors are discovered (not hardcoded): replay guards in
    inv/*.py modules outside `modules` that this tool never inventories."""
    scanned = [m for m in modules if (inv_dir / m).is_file()]
    missing = [m for m in modules if not (inv_dir / m).is_file()]
    out_of_scope: dict[str, list[str]] = {}
    if inv_dir.is_dir():
        for path in sorted(inv_dir.glob("*.py")):
            if path.name in modules:
                continue
            for typ in _replay_types(path.read_text(encoding="utf-8")):
                out_of_scope.setdefault(path.name[:-3], []).append(typ)
    return {"scanned": scanned, "missing": missing, "out_of_scope_replay": out_of_scope}


def _function_blocks(text: str) -> list[str]:
    """Split a test module into per-function chunks (module preamble + each `def ...` body).

    A shared module-level helper that replaces the validator would still appear only in the preamble,
    so a recorder helper does not poison a sibling rejection function. Coarse but far better than
    file-level: it isolates each `pytest.raises` with the setattr calls in its own body.
    """
    parts = re.split(r"(?m)^(?=\s*def\s)", text)
    return parts if parts else [text]


def _imports_module(text: str, module: str) -> bool:
    return bool(
        re.search(rf"\bfrom inv\.{module} import\b", text)
        or re.search(rf"\bfrom inv import {module}\b", text)
        or re.search(rf"\binv\.{module}\b", text)
        or re.search(rf"\bimport {module}\b", text)
    )


def classify(root: Path = DEFAULT_ROOT, modules: list[str] = SERVING_MODULES) -> dict[str, dict]:
    inv = root / "services" / "control-plane" / "src" / "inv"
    tests_dir = root / "tests"
    anchors = serving_anchor_types(inv, modules)
    # Which in-scope types also sit on a replay branch (so a rejection verdict may reflect only the fresh
    # path; replay-branch weight is check_contract_bindings 2b + negative-prior tests, not this tool).
    replay_by_type: set[str] = set()
    for name in modules:
        p = inv / name
        if p.is_file():
            replay_by_type |= _replay_types(p.read_text(encoding="utf-8"))
    test_texts = {
        p: p.read_text(encoding="utf-8")
        for p in tests_dir.rglob("*.py")
        if "__pycache__" not in p.parts
    }
    out: dict[str, dict] = {}
    for typ, modules in sorted(anchors.items()):
        serving_tests = []
        for p, text in test_texts.items():
            if f'"{typ}"' not in text:
                continue
            if any(_imports_module(text, m) for m in modules):
                serving_tests.append(p)
        rejection = False
        recorder = False
        for p in serving_tests:
            # Classify PER TEST FUNCTION, not per file: a file may hold a recorder helper AND a real
            # rejection test in separate functions (e.g. test_artifact_content_contract). File-level
            # detection lets the recorder poison the rejection signal -> false "called-only".
            for block in _function_blocks(test_texts[p]):
                replaces = bool(_REPLACES_VALIDATOR.search(block))
                raises = bool(_RAISES.search(block))
                if raises and not replaces:
                    rejection = True
                if replaces:
                    recorder = True
        if rejection:
            tier = "rejection-tested"
        elif serving_tests and recorder:
            tier = "called-only"
        elif serving_tests:
            tier = "named-only"  # names + imports module, but neither replaces nor raises
        else:
            tier = "no-serving-test"
        out[typ] = {
            "tier": tier,
            "modules": sorted(modules),
            "serving_tests": sorted(p.name for p in serving_tests),
            "has_replay_branch": typ in replay_by_type,
        }
    return out


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--root", type=Path, default=DEFAULT_ROOT)
    parser.add_argument(
        "--strict", action="store_true",
        help="exit 1 if any anchor is called-only / named-only / no-serving-test (opt-in; default report-only)",
    )
    parser.add_argument(
        "--modules", default=None,
        help="comma-separated serving module basenames to scan (default: the 7 frontend-facing view/"
             "serving modules). Widening pulls in non-serving anchors; see docstring for why narrow is default.",
    )
    args = parser.parse_args(argv)
    modules = [m if m.endswith(".py") else m + ".py" for m in args.modules.split(",")] if args.modules else SERVING_MODULES
    inv = args.root / "services" / "control-plane" / "src" / "inv"
    scope = scope_report(inv, modules)
    result = classify(args.root, modules)

    order = {"rejection-tested": 0, "called-only": 1, "named-only": 2, "no-serving-test": 3}
    tiers: dict[str, list[str]] = {k: [] for k in order}
    for typ, info in result.items():
        tiers[info["tier"]].append(typ)

    # SCOPE FIRST -- the numbers must never read broader than what was scanned.
    print(
        f"SCOPE: scanned {len(scope['scanned'])} frontend-facing serving/view modules "
        f"({', '.join(m[:-3] for m in scope['scanned'])}); classifies by TYPE, not by branch "
        f"(a rejection verdict can reflect the fresh path while a replay branch of the same type is "
        f"untested)."
    )
    if scope["missing"]:
        print(f"SCOPE: expected modules not found: {[m[:-3] for m in scope['missing']]}")
    if scope["out_of_scope_replay"]:
        pairs = sorted((mod, typ) for mod, ts in scope["out_of_scope_replay"].items() for typ in ts)
        print(
            f"OUT OF SCOPE: >={len(pairs)} replay-branch anchors in "
            f"{sorted(scope['out_of_scope_replay'])} are NOT inventoried here (detected subset; "
            f"check_contract_bindings.py (2b) holds the AUTHORITATIVE replay set and their runtime weight "
            f"is the negative-persisted-prior tests). This tool does not cover them: {pairs}"
        )

    print(
        f"anchor rejection-coverage (static proxy; report-only): "
        f"{len(tiers['rejection-tested'])} rejection-tested, "
        f"{len(tiers['called-only'])} called-only, "
        f"{len(tiers['named-only'])} named-only, "
        f"{len(tiers['no-serving-test'])} no-serving-test "
        f"(of {len(result)} in-scope types)."
    )
    # Flag in-scope types whose rejection verdict may only cover the fresh path.
    for typ in sorted(tiers["rejection-tested"]):
        if result[typ].get("has_replay_branch"):
            print(
                f"  [rejection-tested*] {typ} -- has a replay branch too; this verdict may reflect only "
                f"the fresh path. Replay-branch weight is check_contract_bindings 2b + negative-prior tests."
            )
    for tier in ("called-only", "named-only", "no-serving-test"):
        for typ in sorted(tiers[tier]):
            info = result[typ]
            detail = (
                f"tests={info['serving_tests']}" if info["serving_tests"] else "no test names it + imports the module"
            )
            note = {
                "called-only": "serving-anchor test replaces the validator (proves called, not rejects); "
                               "add a serving rejection test or confirm contract-level coverage suffices",
                "named-only": "names the type + imports the module but neither replaces the validator nor "
                              "asserts rejection; unclear coverage -- review",
                "no-serving-test": "anchored on a serving path but no serving-anchor test -- blind spot",
            }[tier]
            replay = " (also has a replay branch)" if info.get("has_replay_branch") else ""
            print(f"  [{tier}] {typ} (anchors in {info['modules']}){replay} -- {note}. {detail}")

    print(
        "\nNOTE: static proxy. Runtime weight = the on-demand mutation harness in an isolated worktree "
        "(docs/vault/40_Governance/앵커_무게_검증_절차.md). called-only is not a defect if rejection is "
        "covered by a *_contract.py test on the schema; the report flags serving-path rejection gaps for "
        "human judgement. This tool and check_contract_bindings.py are COMPLEMENTARY, not substitutes: it "
        "covers frontend-facing serving/view anchor rejection; that tool covers fixture+anchor presence and "
        "replay-guard presence (2b)."
    )
    if args.strict and (tiers["called-only"] or tiers["named-only"] or tiers["no-serving-test"]):
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
