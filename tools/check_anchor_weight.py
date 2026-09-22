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


def serving_anchor_types(inv_dir: Path) -> dict[str, set[str]]:
    """type name -> set of serving module basenames that anchor it."""
    anchors: dict[str, set[str]] = {}
    for name in SERVING_MODULES:
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


def classify(root: Path = DEFAULT_ROOT) -> dict[str, dict]:
    inv = root / "services" / "control-plane" / "src" / "inv"
    tests_dir = root / "tests"
    anchors = serving_anchor_types(inv)
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
        }
    return out


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--root", type=Path, default=DEFAULT_ROOT)
    parser.add_argument(
        "--strict", action="store_true",
        help="exit 1 if any anchor is called-only / named-only / no-serving-test (opt-in; default report-only)",
    )
    args = parser.parse_args(argv)
    result = classify(args.root)

    order = {"rejection-tested": 0, "called-only": 1, "named-only": 2, "no-serving-test": 3}
    tiers: dict[str, list[str]] = {k: [] for k in order}
    for typ, info in result.items():
        tiers[info["tier"]].append(typ)

    print(
        f"anchor rejection-coverage (static proxy; report-only): "
        f"{len(tiers['rejection-tested'])} rejection-tested, "
        f"{len(tiers['called-only'])} called-only, "
        f"{len(tiers['named-only'])} named-only, "
        f"{len(tiers['no-serving-test'])} no-serving-test."
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
            print(f"  [{tier}] {typ} (anchors in {info['modules']}) -- {note}. {detail}")

    print(
        "\nNOTE: static proxy. Runtime weight = the on-demand mutation harness in an isolated worktree "
        "(docs/vault/40_Governance/앵커_무게_검증_절차.md). called-only is not a defect if rejection is "
        "covered by a *_contract.py test on the schema; the report flags serving-path rejection gaps for "
        "human judgement."
    )
    if args.strict and (tiers["called-only"] or tiers["named-only"] or tiers["no-serving-test"]):
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
