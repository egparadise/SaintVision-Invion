"""PG-free tests for tools/check_doc_path_citations.py (card bf)."""

from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "tools"))

import check_doc_path_citations as tool  # noqa: E402


def _repo(tmp_path: Path) -> tuple[Path, Path]:
    root = tmp_path / "repo"
    vault = root / "docs" / "vault"
    vault.mkdir(parents=True)
    (root / "src" / "pkg").mkdir(parents=True)
    (root / "src" / "pkg" / "mod.py").write_text("a\nb\nc\n", encoding="utf-8")          # 3 lines
    (root / "tools").mkdir()
    (root / "tools" / "x.py").write_text("one line without newline", encoding="utf-8")   # 1 line
    (root / "apps" / "web").mkdir(parents=True)
    return root, vault


def _doc(vault: Path, name: str, body: str) -> None:
    (vault / name).write_text(body, encoding="utf-8")


# ---------------------------------------------------------------- parsing rules

def test_citation_shapes_and_exclusions():
    p = tool.parse_citation
    assert p("src/pkg/mod.py") == ("src/pkg/mod.py", None, None)
    assert p("src/pkg/mod.py:2") == ("src/pkg/mod.py", 2, None)
    assert p("src/pkg/mod.py:1-3") == ("src/pkg/mod.py", 1, 3)
    assert p("src/pkg/mod.py:1~3") == ("src/pkg/mod.py", 1, 3)
    assert p("src/pkg/mod.py:2 record_deployment") == ("src/pkg/mod.py", 2, None)   # trailing symbol ignored
    assert p("apps/web/") == ("apps/web/", None, None)                              # directory
    assert p(".github/workflows/docs.yml:30") == (".github/workflows/docs.yml", 30, None)
    # not citations: glob/brace/placeholder/ellipsis/URL/no-root/short-hand
    for span in ("contracts/**", "src/saintvision/services/{context,pilot}.py", "tests/test_*.py",
                 "src/<module>/x.py", "src/x/…", "src/x/...", "https://example/src/x.py",
                 "inv/app.py:449", "features/agent/RunDetail.tsx"):
        assert p(span) is None, span
    # trailing text after the path is ignored, only the leading path is checked
    assert p("src/pkg/mod.py compare_declaration") == ("src/pkg/mod.py", None, None)
    assert p("src/pkg/mod.py extra:3") == ("src/pkg/mod.py", None, None)


def test_fenced_code_blocks_are_not_scanned():
    text = "cite `src/pkg/mod.py`\n```bash\ncat `src/missing.py`\n```\nafter `tools/x.py`\n~~~\n`src/also-missing.py`\n~~~\n"
    found = [raw for *_rest, raw in tool.citations_in(text)]
    assert found == ["src/pkg/mod.py", "tools/x.py"]


# ---------------------------------------------------------------- checks

def test_existing_paths_and_valid_lines_pass(tmp_path):
    root, vault = _repo(tmp_path)
    _doc(vault, "a.md", "`src/pkg/mod.py` `src/pkg/mod.py:3` `src/pkg/mod.py:1-3` `tools/x.py:1` `apps/web/` `apps/web`")
    assert tool.broken_citations(root, vault) == {}


def test_missing_path_fails(tmp_path):
    root, vault = _repo(tmp_path)
    _doc(vault, "a.md", "see `src/App.tsx` and `apps/web/src/features/agent/RunDetail.tsx`")
    broken = tool.broken_citations(root, vault)
    assert set(broken) == {"a.md || src/App.tsx", "a.md || apps/web/src/features/agent/RunDetail.tsx"}
    assert all(r == "path does not exist" for r in broken.values())


def test_line_beyond_file_and_bad_ranges_fail(tmp_path):
    root, vault = _repo(tmp_path)
    _doc(vault, "a.md", "`src/pkg/mod.py:4` `src/pkg/mod.py:0` `src/pkg/mod.py:2-1` `src/pkg/mod.py:2-9` `tools/x.py:2` `apps/web/:3`")
    broken = tool.broken_citations(root, vault)
    assert set(broken) == {"a.md || src/pkg/mod.py:4", "a.md || src/pkg/mod.py:0", "a.md || src/pkg/mod.py:2-1",
                           "a.md || src/pkg/mod.py:2-9", "a.md || tools/x.py:2", "a.md || apps/web/:3"}
    assert broken["a.md || src/pkg/mod.py:4"] == "line 4 beyond 3 lines"
    assert broken["a.md || apps/web/:3"] == "line suffix on a directory"


def test_subdirectory_docs_are_keyed_by_relative_posix_path(tmp_path):
    root, vault = _repo(tmp_path)
    (vault / "30_Development" / "History").mkdir(parents=True)
    _doc(vault / "30_Development" / "History", "h.md", "`src/nope.py`")
    assert list(tool.broken_citations(root, vault)) == ["30_Development/History/h.md || src/nope.py"]


# ---------------------------------------------------------------- ratchet

def test_ratchet_passes_when_broken_set_equals_baseline(tmp_path, capsys):
    root, vault = _repo(tmp_path)
    _doc(vault, "a.md", "`src/App.tsx`")
    baseline = tmp_path / "baseline.txt"
    baseline.write_text("# accepted\na.md || src/App.tsx\n", encoding="utf-8")
    assert tool.run_ratchet(root, vault, baseline) == 0
    assert "PASS" in capsys.readouterr().out


def test_ratchet_fails_on_a_new_broken_citation(tmp_path, capsys):
    root, vault = _repo(tmp_path)
    _doc(vault, "a.md", "`src/App.tsx` `src/New.tsx`")
    baseline = tmp_path / "baseline.txt"
    baseline.write_text("a.md || src/App.tsx\n", encoding="utf-8")
    assert tool.run_ratchet(root, vault, baseline) == 1
    out = capsys.readouterr().out
    assert "FAIL (regression)" in out and "+ a.md || src/New.tsx" in out


def test_ratchet_fails_on_a_stale_baseline_entry_so_the_floor_only_goes_down(tmp_path, capsys):
    root, vault = _repo(tmp_path)
    _doc(vault, "a.md", "`src/pkg/mod.py`")  # fixed: nothing broken any more
    baseline = tmp_path / "baseline.txt"
    baseline.write_text("a.md || src/App.tsx\n", encoding="utf-8")
    assert tool.run_ratchet(root, vault, baseline) == 1
    assert "FAIL (stale baseline)" in capsys.readouterr().out


def test_missing_baseline_means_nothing_is_accepted(tmp_path):
    root, vault = _repo(tmp_path)
    _doc(vault, "a.md", "`src/App.tsx`")
    assert tool.run_ratchet(root, vault, tmp_path / "absent.txt") == 1
    _doc(vault, "a.md", "`src/pkg/mod.py`")
    assert tool.run_ratchet(root, vault, tmp_path / "absent.txt") == 0


def test_write_baseline_round_trips(tmp_path):
    root, vault = _repo(tmp_path)
    _doc(vault, "a.md", "`src/App.tsx` `src/pkg/mod.py:9`")
    baseline = tmp_path / "b.txt"
    tool.write_baseline(tool.broken_citations(root, vault), baseline)
    assert tool.read_baseline(baseline) == {"a.md || src/App.tsx", "a.md || src/pkg/mod.py:9"}
    assert tool.run_ratchet(root, vault, baseline) == 0


# ---------------------------------------------------------------- the real vault (self-check of the seeded baseline)

def test_real_vault_ratchet_is_green():
    """The committed baseline must match the committed tree; a new invented path in any doc fails here too."""
    assert tool.run_ratchet() == 0
