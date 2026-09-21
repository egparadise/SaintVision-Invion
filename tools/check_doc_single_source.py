"""Report-only: surface the rule-5 divergence surface -- substantive lines copied verbatim across
living vault docs.

Rule 5 (single source of truth) is a discipline, not a gate here. Tonight's doc failures -- a
correction not reflected in a handoff section, unverified items scattered across two docs -- are all
the same shape: the SAME evolving fact written in more than one place, where updating one copy and
not the other makes them diverge. This tool makes that surface visible.

Why REPORT-ONLY, never a hard gate (measured, 2026-09-22): the vault already contains ~80 such
duplicated substantive lines, dominated by a deliberate structural choice -- parallel status docs
(the agent 작업 현황 family copies status lines into 전체 개발 진행 현황 / 검증 상태 지도). A gate
would fail on that pre-existing backlog, and no purely-textual rule can separate a legitimate index
summary from an accidental copy that will silently diverge. So this prints an advisory a human
triages (consolidate to one source, or accept the summary), like check_contract_bindings' dead
grade. It never fails CI.

Scope: living docs only. Dated snapshots (YYYY-MM-DD_*), point-in-time reports (검증보고/개발과정/
독립검토/_검토_) and frozen sprint plans (S01..) are EXCLUDED -- duplication across time-stamped
records is expected and must not be flagged (that would be the wolf-crying this project keeps
guarding against).
"""
from __future__ import annotations

import re
from collections import defaultdict
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
VAULT = ROOT / "docs" / "vault"
BASELINE = ROOT / "tools" / "baselines" / "doc_single_source_pairs.txt"

MIN_LINE = 80          # substantive: shorter lines are boilerplate/rule one-liners
PAIR_THRESHOLD = 3     # report a doc-pair only if it shares at least this many substantive lines

_DATED = re.compile(r"^\d{4}-\d{2}-\d{2}")
_FROZEN = re.compile(r"검증보고|개발과정|독립검토|_검토_")
_SPRINT = re.compile(r"^S\d\d ")


def is_living(name: str) -> bool:
    """A doc whose content evolves (excludes dated snapshots, reports, frozen sprint plans)."""
    return not (_DATED.match(name) or _FROZEN.search(name) or _SPRINT.match(name))


def substantive_lines(text: str) -> set[str]:
    """Normalized content lines worth comparing: no frontmatter, headings, tables, quotes, code,
    list markers, short/boilerplate lines, or link-only footer lines."""
    if text.startswith("---"):
        end = text.find("\n---", 3)
        if end != -1:
            text = text[end + 4:]
    out: set[str] = set()
    in_fence = False
    for raw in text.splitlines():
        s = raw.strip()
        if s.startswith("```"):
            in_fence = not in_fence
            continue
        if in_fence or not s or s[0] in "#|>":
            continue
        s = re.sub(r"^[-*+]\s+", "", s)
        s = re.sub(r"^\d+\.\s+", "", s)
        s = re.sub(r"\s+", " ", s).strip()
        if len(s) < MIN_LINE or s.startswith("관련"):
            continue
        # a line that is mostly wiki-links (a "see also" enumeration) is not a copied conclusion
        if len(re.findall(r"\[\[[^\]]+\]\]", s)) >= 2 and len(re.sub(r"\[\[[^\]]+\]\]", "", s)) < 40:
            continue
        out.add(s)
    return out


def find_cross_doc_dups(files: list[Path]) -> dict[str, set[str]]:
    """Map each substantive line to the set of living docs it appears in (>=2 docs only)."""
    line_docs: dict[str, set[str]] = defaultdict(set)
    for path in files:
        if not is_living(path.name):
            continue
        for line in substantive_lines(path.read_text(encoding="utf-8-sig")):
            line_docs[line].add(path.name)
    return {line: docs for line, docs in line_docs.items() if len(docs) >= 2}


def flagged_pairs(files: list[Path]) -> dict[tuple[str, str], list[str]]:
    """Doc-pairs sharing >= PAIR_THRESHOLD substantive lines, mapped to those lines."""
    dups = find_cross_doc_dups(files)
    pair_lines: dict[tuple[str, str], list[str]] = defaultdict(list)
    for line, docs in dups.items():
        ordered = sorted(docs)
        for i in range(len(ordered)):
            for j in range(i + 1, len(ordered)):
                pair_lines[(ordered[i], ordered[j])].append(line)
    return {pair: lines for pair, lines in pair_lines.items() if len(lines) >= PAIR_THRESHOLD}


def _pair_key(a: str, b: str) -> str:
    return f"{a} || {b}"


def read_baseline() -> set[str]:
    """Accepted pairs, one 'A || B' per non-comment line. Missing file => empty (nothing accepted)."""
    if not BASELINE.is_file():
        return set()
    out = set()
    for raw in BASELINE.read_text(encoding="utf-8").splitlines():
        s = raw.strip()
        if s and not s.startswith("#"):
            out.add(s)
    return out


def run_report(files: list[Path]) -> int:
    flagged = flagged_pairs(files)
    print(
        f"REPORT check_doc_single_source (advisory, never fails): "
        f"{sum(len(v) for v in flagged.values())} shared lines across {len(flagged)} doc-pairs "
        f"(>= {PAIR_THRESHOLD} each)."
    )
    for (a, b), lines in sorted(flagged.items(), key=lambda kv: -len(kv[1])):
        print(f"  - {a}  <->  {b}: {len(lines)} shared substantive lines")
    if flagged:
        print("  (rule 5: prefer one source + [[links]]. Advisory only.)")
    return 0


def run_ratchet(files: list[Path]) -> int:
    """Gate on the DELTA, not the backlog. Fail on a pair not in the baseline (regression) AND on a
    baseline entry that no longer occurs (stale -> must be removed, ratcheting the floor down). Both
    require editing the baseline file, so every change to the accepted set is a visible commit line."""
    current = {_pair_key(a, b) for (a, b) in flagged_pairs(files)}
    baseline = read_baseline()
    new = sorted(current - baseline)
    stale = sorted(baseline - current)
    if not new and not stale:
        print(f"PASS check_doc_single_source --ratchet: {len(current)} pairs, all in baseline, none stale.")
        return 0
    if new:
        print(f"FAIL (regression): {len(new)} NEW duplicate doc-pair(s) not in the baseline:")
        for p in new:
            print(f"  + {p}")
        print("  Consolidate to one source (rule 5), or -- if deliberate -- add the named line to")
        print(f"  {BASELINE.relative_to(ROOT)} (a visible, reviewable raise of the floor).")
    if stale:
        print(f"FAIL (stale baseline): {len(stale)} baseline pair(s) no longer occur -- remove them to")
        print(f"  ratchet the floor down (leaving slack lets it regress silently):")
        for p in stale:
            print(f"  - {p}")
    return 1


def main() -> int:
    import argparse

    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--ratchet",
        action="store_true",
        help="gate mode: fail on a new pair (regression) or a stale baseline entry (ratchet-down)",
    )
    args = parser.parse_args()
    files = [p for p in VAULT.rglob("*.md") if p.is_file()]
    return run_ratchet(files) if args.ratchet else run_report(files)


if __name__ == "__main__":
    raise SystemExit(main())
