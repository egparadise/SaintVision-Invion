"""Report whether wire fixtures have a plausible non-circular producer witness.

This is a deliberately conservative static proxy, not proof that a producer can
emit every fixture value.  It complements schema validation: for each
``contracts/fixtures/*.json`` file it finds tests that name the fixture and
classifies their strongest evidence as:

* ``runtime-witness``: a referencing test file exercises an HTTP/runtime call
  without replacing production behavior in that file;
* ``circular-witness``: a runtime-looking test also monkeypatches production,
  so the fixture may merely be fed back to the consumer;
* ``schema-only``: references only validate shape/model round-tripping;
* ``unreferenced``: no test names the fixture (the binding gate also catches it).

Default mode is report-only and always exits zero after a successful scan.
``--strict`` is an opt-in experiment which exits one unless every fixture has a
runtime witness.  Do not promote it until the backlog and false-positive rate
are both measured at zero.
"""

from __future__ import annotations

import argparse
from pathlib import Path
import re
from typing import NamedTuple


ROOT = Path(__file__).resolve().parents[1]
RUNTIME = re.compile(
    r"TestClient\s*\(|\.(?:get|post|put|patch|delete)\s*\(|"
    r"create_app\s*\(|\.(?:result|list|status|download)\s*\("
)
REPLACEMENT = re.compile(r"monkeypatch\.setattr|patch\.(?:object|dict)\s*\(|\bpatch\s*\(")


class Finding(NamedTuple):
    fixture: str
    tier: str
    tests: tuple[str, ...]


def classify(root: Path = ROOT) -> list[Finding]:
    fixtures = root / "contracts" / "fixtures"
    tests = root / "tests"
    texts = {
        path: path.read_text(encoding="utf-8")
        for path in tests.rglob("*.py")
        if "__pycache__" not in path.parts
    }
    findings: list[Finding] = []
    for fixture in sorted(fixtures.glob("*.json")):
        referenced = {path: text for path, text in texts.items() if fixture.name in text}
        runtime = [
            path for path, text in referenced.items() if RUNTIME.search(text) and not REPLACEMENT.search(text)
        ]
        circular = [
            path for path, text in referenced.items() if RUNTIME.search(text) and REPLACEMENT.search(text)
        ]
        if runtime:
            tier, evidence = "runtime-witness", runtime
        elif circular:
            tier, evidence = "circular-witness", circular
        elif referenced:
            tier, evidence = "schema-only", list(referenced)
        else:
            tier, evidence = "unreferenced", []
        findings.append(
            Finding(
                fixture.name,
                tier,
                tuple(sorted(str(path.relative_to(root)).replace("\\", "/") for path in evidence)),
            )
        )
    return findings


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--root", type=Path, default=ROOT)
    parser.add_argument("--strict", action="store_true")
    args = parser.parse_args(argv)
    findings = classify(args.root)
    tiers = {name: [] for name in ("runtime-witness", "circular-witness", "schema-only", "unreferenced")}
    for finding in findings:
        tiers[finding.tier].append(finding)
    print(
        "fixture reachability (static proxy; report-only): "
        + ", ".join(f"{len(tiers[name])} {name}" for name in tiers)
        + f" (of {len(findings)} fixtures)."
    )
    print(
        "LIMIT: runtime-witness means a plausible non-monkeypatched producer test was found; "
        "it does not prove every value/combination is reachable."
    )
    for tier in ("circular-witness", "schema-only", "unreferenced"):
        for finding in tiers[tier]:
            detail = ", ".join(finding.tests) if finding.tests else "no test reference"
            print(f"  [{tier}] {finding.fixture}: {detail}")
    if args.strict and any(finding.tier != "runtime-witness" for finding in findings):
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
