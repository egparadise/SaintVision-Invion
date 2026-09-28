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
``<doc relative to docs/vault> || <citation>``.  ``--ratchet --base-ref REF``
(the CI mode) fails on: a broken citation NOT in the baseline (a new
regression); a baseline line that is no longer broken (stale -> remove it);
and a baseline line that is not in the baseline committed at REF (the floor
was raised -- a new broken citation and its baseline line arriving together
must not cancel out).  ``--base-ref`` is required in ratchet mode; an unknown
ref fails; a ref where the baseline file does not exist yet (first
introduction) skips the floor check and says so.  ``--report`` prints every
broken citation without failing; ``--write-baseline`` is shrink-only (existing
baseline intersected with what is still broken, refused additions listed);
``--seed-baseline`` writes everything once and refuses if a baseline exists.

Containment: a cited path with a ``.``/``..`` segment, a symlink anywhere on
it, or a resolved location outside the repository root fails even when
something exists there.

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

#: CommonMark fence: up to three spaces of indentation, three or more backticks
#: or tildes. The closing fence must use the same character and be at least as
#: long; the opening marker is remembered so a shorter run inside does not close.
_FENCE = re.compile(r"^ {0,3}(`{3,}|~{3,})(.*)$")
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
    fence: str | None = None  # the opening marker, e.g. "```" or "~~~~"
    for line in text.splitlines():
        m = _FENCE.match(line)
        if m:
            marker, rest = m.group(1), m.group(2)
            if fence is None:
                fence = marker
                continue
            # Closing: same character, at least as long, nothing but spaces after.
            if marker[0] == fence[0] and len(marker) >= len(fence) and not rest.strip():
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
    """Return a failure reason, or None when the citation resolves.

    Containment is fail-closed: a ``..`` segment, a symlink anywhere on the
    cited path, or a resolved location outside the repository root is a
    failure even when something exists there. "A repository path exists"
    must mean a path *inside* the repository.
    """
    parts = [p for p in path.rstrip("/").split("/") if p]
    if ".." in parts or "." in parts:
        return "path escapes the repository (dot segment)"
    target = root / path.rstrip("/")
    probe = root
    for part in parts:
        probe = probe / part
        if probe.is_symlink():
            return "path goes through a symlink"
    try:
        resolved_root = root.resolve()
        resolved = target.resolve(strict=False)
    except OSError:
        return "path cannot be resolved"
    if resolved != resolved_root and resolved_root not in resolved.parents:
        return "path escapes the repository"
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


def baseline_at_ref(ref: str, root: Path = ROOT, rel: str = "tools/baselines/doc_path_citations.txt") -> set[str] | None:
    """The baseline committed at ``ref``; None when the file is absent there.

    An unknown ref is an error, not an empty baseline: an empty floor would
    make every current entry look like an addition, and a silently accepted
    ref typo would make the floor check pass without a floor.
    """
    import subprocess

    check = subprocess.run(["git", "rev-parse", "--verify", "--quiet", f"{ref}^{{commit}}"],
                           cwd=root, capture_output=True, text=True)
    if check.returncode != 0:
        raise ValueError(f"base ref {ref!r} is not a commit in this repository")
    shown = subprocess.run(["git", "show", f"{ref}:{rel}"], cwd=root, capture_output=True, text=True,
                           encoding="utf-8")
    if shown.returncode != 0:
        return None
    return {s for s in (line.strip() for line in shown.stdout.splitlines()) if s and not s.startswith("#")}


def write_baseline(entries: dict[str, str], path: Path = BASELINE, *, seed: bool = False) -> list[str]:
    """Rewrite the baseline; returns the broken citations it refused to add.

    Shrink-only by default: the new file is the existing baseline intersected
    with what is broken now, so an entry can leave but never join. ``seed``
    writes every broken citation and is only for the first introduction (it
    refuses when a baseline already exists).
    """
    if seed:
        if path.is_file():
            raise FileExistsError(f"{path} exists; --seed-baseline is for a first introduction only")
        accepted = dict(entries)
        refused: list[str] = []
    else:
        existing = read_baseline(path)
        accepted = {key: reason for key, reason in entries.items() if key in existing}
        refused = sorted(set(entries) - existing)
    _write_baseline_file(accepted, path)
    return refused


def _write_baseline_file(entries: dict[str, str], path: Path) -> None:
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


def run_ratchet(
    root: Path = ROOT,
    vault: Path | None = None,
    baseline_path: Path = BASELINE,
    *,
    base_baseline: set[str] | None = None,
) -> int:
    """CI mode. ``base_baseline`` is the baseline at the base commit.

    Three failures, each named: a broken citation not in the baseline (new
    regression), a baseline entry no longer broken (stale), and a baseline
    entry that is not in ``base_baseline`` (the floor was raised in this
    change -- the case where a new broken citation and its baseline line
    arrive together and would otherwise cancel out). ``None`` means no base
    baseline exists (first introduction); the floor check is then skipped and
    said so.
    """
    current = broken_citations(root, vault)
    baseline = read_baseline(baseline_path)
    new = sorted(set(current) - baseline)
    stale = sorted(baseline - set(current))
    raised = sorted(baseline - base_baseline) if base_baseline is not None else []
    if not new and not stale and not raised:
        floor = "floor unchanged" if base_baseline is not None else "no base baseline (first introduction)"
        print(f"PASS check_doc_path_citations --ratchet: {len(current)} broken citation(s), "
              f"all in baseline, none stale, {floor}.")
        return 0
    if raised:
        print(f"FAIL (floor raised): {len(raised)} baseline entr{'y' if len(raised) == 1 else 'ies'} "
              "not present in the base commit's baseline -- the baseline may only shrink:")
        for key in raised:
            print(f"  + {key}")
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
    mode.add_argument("--write-baseline", action="store_true",
                      help="shrink the baseline to what is still broken; never adds an entry")
    mode.add_argument("--seed-baseline", action="store_true",
                      help="first introduction only: write every broken citation (refuses if a baseline exists)")
    parser.add_argument("--base-ref", metavar="REF",
                        help="--ratchet: git ref of the base commit; the baseline must be a subset of the "
                             "baseline at REF (required in ratchet mode so the floor cannot be raised)")
    args = parser.parse_args(argv)
    if args.report:
        return run_report()
    if args.seed_baseline:
        current = broken_citations()
        write_baseline(current, seed=True)
        print(f"SEEDED {BASELINE.relative_to(ROOT)}: {len(current)} accepted broken citation(s).")
        return 0
    if args.write_baseline:
        current = broken_citations()
        refused = write_baseline(current)
        kept = len(read_baseline())
        print(f"WROTE {BASELINE.relative_to(ROOT)}: {kept} accepted broken citation(s) (shrink-only).")
        for key in refused:
            print(f"  refused to add: {key}  [{current[key]}]")
        return 0
    if not args.base_ref:
        parser.error("--ratchet requires --base-ref REF (the floor is checked against that commit's baseline)")
    try:
        base = baseline_at_ref(args.base_ref)
    except ValueError as exc:
        print(f"FAIL: {exc}")
        return 1
    return run_ratchet(base_baseline=base)


if __name__ == "__main__":
    sys.exit(main())
