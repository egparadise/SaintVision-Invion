"""Verify that repository paths cited in ``docs/vault`` markdown actually exist (card bf).

Background: PR #154 and #156 shipped documents citing paths that do not exist
(``features/agent/RunDetail.tsx``, ``src/App.tsx``) and invented routes, and
``check_docs.py`` let them through because it only checks wiki links, ids and
secrets.  This tool closes that hole for *path* citations.

What counts as a citation
-------------------------
An inline code span (single backticks) whose text is a repository path, i.e. it
starts with one of the citation roots ``apps/ src/ services/ tests/ tools/
migrations/ contracts/ packages/ deploy/ .github/`` and optionally carries a line
suffix ``:N``, ``:N-M`` or ``:N~M``.  Text after the line suffix separated by a
space (a symbol name, e.g. ``src/x.py:454 record_deployment`` or
``src/x.py compare_declaration``) is allowed and ignored -- only the leading
path and its optional line suffix are checked.  A trailing ``/`` cites a
directory.

What is deliberately NOT checked (false-positive rules)
-------------------------------------------------------
* anything inside a fenced code block (``` or ~~~) -- code blocks are examples,
  commands and quoted output, not citations;
* spans containing glob or brace patterns (``* ? [ ] { }``) or an ellipsis
  (``…`` / ``...``) or a placeholder in angle brackets (``<name>``);
* spans containing ``://`` (URLs) or whitespace before the optional line suffix;
* spans that do not start with a citation root (``inv/app.py:449`` is a
  short-hand this tool does not resolve; it is neither checked nor counted).

Checks
------
* the path must exist under the repository root (file or directory);
* ``:N`` requires ``1 <= N <= number of lines`` of that file; ``:N-M`` requires
  ``N <= M <= lines``; a line suffix on a directory is a failure.

Ratchet
-------
``tools/baselines/doc_path_citations.txt`` lists ACCEPTED broken citations as
``<doc relative to docs/vault> || <citation>``.  ``--ratchet`` (the CI mode)
fails on a broken citation NOT in the baseline (a new regression) AND on a
baseline line that is no longer broken (stale -> remove it; the floor only goes
down).  Both directions require editing the baseline, so every change to the
accepted set is a visible, reviewable line.  ``--report`` prints every broken
citation without failing; ``--write-baseline`` rewrites the baseline from the
current tree (used once to seed it; later use is a visible commit).

Exit codes: 0 pass; 1 ratchet failure; 2 usage.
"""

from __future__ import annotations

import argparse
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
VAULT = ROOT / "docs" / "vault"
BASELINE = ROOT / "tools" / "baselines" / "doc_path_citations.txt"

CITATION_ROOTS = ("apps", "src", "services", "tests", "tools", "migrations", "contracts", "packages", "deploy", ".github")

_FENCE = re.compile(r"^(```|~~~)", re.M)
_SPAN = re.compile(r"`([^`\n]+)`")
_CITATION = re.compile(
    r"^(?P<path>(?:" + "|".join(re.escape(r) for r in CITATION_ROOTS) + r")/[^\s:`]*)"
    r"(?::(?P<start>\d+)(?:[-~](?P<end>\d+))?)?"
    r"(?:\s+\S.*)?$"
)
_EXCLUDE_CHARS = re.compile(r"[*?\[\]{}<>…]|\.\.\.|://")


def strip_fenced_blocks(text: str) -> str:
    """Remove fenced code blocks; keeps line structure irrelevant (we only need spans)."""
    out: list[str] = []
    fence: str | None = None
    for line in text.splitlines():
        m = _FENCE.match(line)
        if m:
            if fence is None:
                fence = m.group(1)
            elif line.startswith(fence):
                fence = None
            continue
        if fence is None:
            out.append(line)
    return "\n".join(out)


def parse_citation(span: str) -> tuple[str, int | None, int | None] | None:
    """Return (path, start, end) for a span that is a checkable citation, else None."""
    span = span.strip()
    if _EXCLUDE_CHARS.search(span):
        return None
    m = _CITATION.match(span)
    if not m:
        return None
    path = m.group("path")
    start = int(m.group("start")) if m.group("start") else None
    end = int(m.group("end")) if m.group("end") else None
    return path, start, end


def citations_in(text: str) -> list[tuple[str, int | None, int | None, str]]:
    found = []
    for m in _SPAN.finditer(strip_fenced_blocks(text)):
        parsed = parse_citation(m.group(1))
        if parsed:
            found.append((*parsed, m.group(1).strip()))
    return found


def line_count(path: Path) -> int:
    data = path.read_bytes()
    if not data:
        return 0
    return data.count(b"\n") + (0 if data.endswith(b"\n") else 1)


def check_citation(root: Path, path: str, start: int | None, end: int | None) -> str | None:
    """Return a failure reason, or None when the citation resolves."""
    target = root / path.rstrip("/")
    if not target.exists():
        return "path does not exist"
    if start is None:
        return None
    if target.is_dir():
        return "line suffix on a directory"
    total = line_count(target)
    if start < 1 or start > total:
        return f"line {start} beyond {total} lines"
    if end is not None and (end < start or end > total):
        return f"line range {start}-{end} invalid for {total} lines"
    return None


def broken_citations(root: Path = ROOT, vault: Path | None = None) -> dict[str, str]:
    """Map ``'<doc> || <citation>'`` -> reason for every broken citation in the vault."""
    vault = vault or (root / "docs" / "vault")
    broken: dict[str, str] = {}
    for doc in sorted(vault.rglob("*.md")):
        text = doc.read_text(encoding="utf-8-sig")
        rel = doc.relative_to(vault).as_posix()
        for path, start, end, raw in citations_in(text):
            reason = check_citation(root, path, start, end)
            if reason:
                broken[f"{rel} || {raw}"] = reason
    return broken


def read_baseline(path: Path = BASELINE) -> set[str]:
    if not path.is_file():
        return set()
    return {s for s in (line.strip() for line in path.read_text(encoding="utf-8").splitlines())
            if s and not s.startswith("#")}


def write_baseline(entries: dict[str, str], path: Path = BASELINE) -> None:
    header = (
        "# Ratchet baseline for check_doc_path_citations --ratchet.\n"
        "# Each line is an ACCEPTED broken repository-path citation: '<doc relative to docs/vault> || <citation>'.\n"
        "# --ratchet FAILS on a broken citation NOT listed here (a NEW regression) AND on a listed citation that is\n"
        "# no longer broken (STALE -> remove it, ratcheting the floor down). The floor only goes down: fix the\n"
        "# citation in the document, then delete its line here. Never add a line to hide a new invented path.\n"
    )
    body = "\n".join(sorted(entries)) + ("\n" if entries else "")
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(header + body, encoding="utf-8", newline="\n")


def run_ratchet(root: Path = ROOT, vault: Path | None = None, baseline_path: Path = BASELINE) -> int:
    current = broken_citations(root, vault)
    baseline = read_baseline(baseline_path)
    new = sorted(set(current) - baseline)
    stale = sorted(baseline - set(current))
    if not new and not stale:
        print(f"PASS check_doc_path_citations --ratchet: {len(current)} broken citation(s), all in baseline, none stale.")
        return 0
    if new:
        print(f"FAIL (regression): {len(new)} NEW broken path citation(s) not in the baseline:")
        for key in new:
            print(f"  + {key}  [{current[key]}]")
        try:
            shown = baseline_path.relative_to(root).as_posix()
        except ValueError:
            shown = str(baseline_path)
        print("  Fix the document to cite a real path (or drop the line suffix). Adding a baseline line is a")
        print(f"  visible, reviewable raise of the floor in {shown} -- not for new inventions.")
    if stale:
        print(f"FAIL (stale baseline): {len(stale)} baseline citation(s) no longer broken -- remove them to")
        print("  ratchet the floor down (leaving slack lets it regress silently):")
        for key in stale:
            print(f"  - {key}")
    return 1


def run_report(root: Path = ROOT, vault: Path | None = None) -> int:
    current = broken_citations(root, vault)
    print(f"REPORT check_doc_path_citations: {len(current)} broken repository-path citation(s).")
    for key, reason in sorted(current.items()):
        print(f"  - {key}  [{reason}]")
    return 0


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    mode = parser.add_mutually_exclusive_group()
    mode.add_argument("--ratchet", action="store_true", help="CI mode: fail on new broken citations or stale baseline entries")
    mode.add_argument("--report", action="store_true", help="list every broken citation; never fails")
    mode.add_argument("--write-baseline", action="store_true", help="rewrite the baseline from the current tree (visible commit)")
    args = parser.parse_args(argv)
    if args.report:
        return run_report()
    if args.write_baseline:
        current = broken_citations()
        write_baseline(current)
        print(f"WROTE {BASELINE.relative_to(ROOT)}: {len(current)} accepted broken citation(s).")
        return 0
    return run_ratchet()


if __name__ == "__main__":
    sys.exit(main())
