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
    tool.write_baseline(tool.broken_citations(root, vault), baseline, seed=True)
    assert tool.read_baseline(baseline) == {"a.md || src/App.tsx", "a.md || src/pkg/mod.py:9"}
    assert tool.run_ratchet(root, vault, baseline) == 0


# ---------------------------------------------------------------- the real vault (self-check of the seeded baseline)

def test_real_vault_ratchet_is_green():
    """The committed baseline must match the committed tree; a new invented path in any doc fails here too."""
    assert tool.run_ratchet() == 0


# ---------------------------------------------------------------- Codex review of #169: floor, containment, fences

def test_indented_and_longer_fences_are_recognised():
    """CommonMark allows up to three spaces before a fence and longer markers."""
    text = (
        "keep `src/pkg/mod.py`\n"
        "   ```bash\n"
        "cat `src/inside-indented-fence.py`\n"
        "   ```\n"
        "````\n"
        "```\n"                       # a shorter run does not close a 4-backtick fence
        "`src/inside-long-fence.py`\n"
        "````\n"
        "  ~~~~\n"
        "`src/inside-tilde.py`\n"
        "~~~\n"                       # too short: still inside
        "`src/still-inside.py`\n"
        "~~~~~\n"                     # long enough: closes
        "after `tools/x.py`\n"
    )
    found = [raw for *_rest, raw in tool.citations_in(text)]
    assert found == ["src/pkg/mod.py", "tools/x.py"]


def test_dot_segments_cannot_escape_the_repository(tmp_path):
    root, vault = _repo(tmp_path)
    (tmp_path / "outside.txt").write_text("secret\n", encoding="utf-8")   # exists, but outside root
    _doc(vault, "a.md", "`src/../../outside.txt` `src/./pkg/mod.py` `src/pkg/../pkg/mod.py`")
    broken = tool.broken_citations(root, vault)
    assert broken["a.md || src/../../outside.txt"].startswith("path escapes the repository")
    assert broken["a.md || src/./pkg/mod.py"].startswith("path escapes the repository")
    assert broken["a.md || src/pkg/../pkg/mod.py"].startswith("path escapes the repository")


def test_a_symlink_on_the_cited_path_fails_even_when_it_points_inside(tmp_path):
    root, vault = _repo(tmp_path)
    outside = tmp_path / "outside.txt"
    outside.write_text("secret\n", encoding="utf-8")
    try:
        (root / "src" / "leak.txt").symlink_to(outside)                 # file symlink -> outside
        (root / "tools" / "alias").symlink_to(root / "src" / "pkg", target_is_directory=True)
    except (OSError, NotImplementedError) as exc:
        import pytest
        pytest.skip(f"symlink creation not permitted here: {exc}")
    _doc(vault, "a.md", "`src/leak.txt` `tools/alias/mod.py` `src/pkg/mod.py`")
    broken = tool.broken_citations(root, vault)
    assert broken == {
        "a.md || src/leak.txt": "path goes through a symlink",
        "a.md || tools/alias/mod.py": "path goes through a symlink",
    }


def test_ratchet_fails_when_a_new_broken_citation_and_its_baseline_line_arrive_together(tmp_path, capsys):
    """Codex #169 finding 1: current == baseline must not pass when the floor was raised."""
    root, vault = _repo(tmp_path)
    _doc(vault, "a.md", "`src/App.tsx` `src/New.tsx`")
    baseline = tmp_path / "baseline.txt"
    baseline.write_text("a.md || src/App.tsx\na.md || src/New.tsx\n", encoding="utf-8")
    base_baseline = {"a.md || src/App.tsx"}                                   # what the base commit accepted
    assert tool.run_ratchet(root, vault, baseline, base_baseline=base_baseline) == 1
    out = capsys.readouterr().out
    assert "FAIL (floor raised)" in out and "+ a.md || src/New.tsx" in out
    # The same tree passes against a base that already accepted both, and when
    # the floor is lowered (base had more) it also passes.
    assert tool.run_ratchet(root, vault, baseline, base_baseline=base_baseline | {"a.md || src/New.tsx"}) == 0
    assert tool.run_ratchet(root, vault, baseline, base_baseline=base_baseline | {"a.md || src/New.tsx", "b.md || src/Old.tsx"}) == 0


def test_write_baseline_is_shrink_only_and_seed_refuses_an_existing_file(tmp_path):
    root, vault = _repo(tmp_path)
    _doc(vault, "a.md", "`src/App.tsx` `src/New.tsx`")
    baseline = tmp_path / "b.txt"
    baseline.write_text("a.md || src/App.tsx\na.md || src/Gone.tsx\n", encoding="utf-8")
    refused = tool.write_baseline(tool.broken_citations(root, vault), baseline)
    assert refused == ["a.md || src/New.tsx"]                               # never added
    assert tool.read_baseline(baseline) == {"a.md || src/App.tsx"}          # stale entry dropped
    import pytest
    with pytest.raises(FileExistsError):
        tool.write_baseline(tool.broken_citations(root, vault), baseline, seed=True)


def test_baseline_at_ref_reads_git_and_fails_closed_on_an_unknown_ref(tmp_path):
    import subprocess
    repo = tmp_path / "git"
    repo.mkdir()
    run = lambda *args: subprocess.run(["git", *args], cwd=repo, check=True, capture_output=True, text=True)
    run("init", "-q")
    run("config", "user.email", "t@example")
    run("config", "user.name", "t")
    run("commit", "-q", "--allow-empty", "-m", "empty")
    assert tool.baseline_at_ref("HEAD", repo) is None                       # file absent: first introduction
    (repo / "tools" / "baselines").mkdir(parents=True)
    (repo / "tools" / "baselines" / "doc_path_citations.txt").write_text("# c\na.md || src/App.tsx\n", encoding="utf-8")
    run("add", "-A")
    run("commit", "-q", "-m", "baseline")
    assert tool.baseline_at_ref("HEAD", repo) == {"a.md || src/App.tsx"}
    import pytest
    with pytest.raises(ValueError):
        tool.baseline_at_ref("no-such-ref", repo)


def _git_repo_with_vault(tmp_path):
    """A git repo with the citation roots, one vault doc and a seeded baseline (commit 0)."""
    import subprocess
    repo = tmp_path / "git"
    root, vault = _repo(tmp_path / "git")
    run = lambda *args: subprocess.run(["git", *args], cwd=repo, check=True, capture_output=True, text=True)
    run("init", "-q")
    run("config", "user.email", "t@example")
    run("config", "user.name", "t")
    _doc(vault, "a.md", "`src/App.tsx`")
    baseline = repo / "tools" / "baselines" / "doc_path_citations.txt"
    baseline.parent.mkdir(parents=True, exist_ok=True)
    tool.write_baseline(tool.broken_citations(root, vault), baseline, seed=True)
    run("add", "-A")
    run("commit", "-q", "-m", "c0: seeded baseline")
    return repo, vault, baseline, run


def test_a_two_commit_push_that_raises_the_floor_in_commit_one_fails_against_the_pre_push_sha(tmp_path):
    """Codex #169 r2: HEAD~1 would already contain the raised floor; github.event.before must not."""
    import subprocess
    repo, vault, baseline, run = _git_repo_with_vault(tmp_path)
    before = subprocess.run(["git", "rev-parse", "HEAD"], cwd=repo, capture_output=True, text=True, check=True).stdout.strip()
    # commit 1: a new broken citation together with its baseline line (floor raised)
    _doc(vault, "a.md", "`src/App.tsx` `src/New.tsx`")
    baseline.write_text(baseline.read_text(encoding="utf-8") + "a.md || src/New.tsx\n", encoding="utf-8")
    run("add", "-A")
    run("commit", "-q", "-m", "c1: raise the floor")
    # commit 2: unrelated
    (repo / "tools" / "note.txt").write_text("unrelated\n", encoding="utf-8")
    run("add", "-A")
    run("commit", "-q", "-m", "c2: unrelated")
    # HEAD~1 is commit 1 and already holds the raised floor: the bypass Codex described.
    assert tool.run_ratchet(repo, vault, baseline, base_baseline=tool.baseline_at_ref("HEAD~1", repo)) == 0
    # The pre-push SHA is the real floor, and the gate fails.
    assert tool.run_ratchet(repo, vault, baseline, base_baseline=tool.baseline_at_ref(before, repo)) == 1


def test_the_docs_workflow_names_a_base_per_trigger_and_never_uses_head_minus_one():
    """Static check of the wiring: push uses github.event.before, no HEAD~1 anywhere."""
    workflow = (Path(__file__).resolve().parents[1] / ".github" / "workflows" / "docs.yml").read_text(encoding="utf-8")
    step = workflow[workflow.index("Repository path citations exist"):workflow.index("check_contract_bindings.py")]
    assert "HEAD~1" not in step
    assert "${{ github.event.before }}" in step
    assert "0000000000000000000000000000000000000000" in step and "exit 1" in step   # zero SHA fails closed
    assert 'origin/$GITHUB_BASE_REF' in step                                           # pull_request base
    assert "--ratchet --base-ref" in step
    assert 'base="HEAD"' in step and "consistency only" in step                        # workflow_dispatch, stated


def test_cli_ratchet_requires_a_base_ref(capsys):
    import pytest
    with pytest.raises(SystemExit) as exc:
        tool.main(["--ratchet"])
    assert exc.value.code == 2
