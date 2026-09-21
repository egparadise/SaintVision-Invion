"""Both sides: the detector reports a copied substantive line, and stays quiet on unique content
and on legitimately-excluded (dated/frozen) docs. A report-only tool still has to bear weight --
it must actually fire on a duplicate and not fire on non-duplicates."""
from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "tools"))

from check_doc_single_source import find_cross_doc_dups, is_living, substantive_lines  # noqa: E402

LONG = "이 결론은 충분히 길어서 실질적 내용으로 취급되며 두 문서에 복사되면 분기 위험이 되는 문장이다 최소 길이 80자를 확실히 넘기도록 여유있게 늘린 검증용 결론 문장이며 SHA abc1234 같은 토큰도 포함한다"


def _write(d: Path, name: str, body: str) -> Path:
    p = d / name
    p.write_text(f"---\ndoc_id: X\n---\n\n{body}\n", encoding="utf-8")
    return p


def test_reports_a_line_copied_across_two_living_docs(tmp_path):
    a = _write(tmp_path, "living_a.md", f"- {LONG}\n- 고유한 문장 A 이지만 역시 충분히 길게 만들어 실질 라인으로 잡히게 한다 최소 길이 초과")
    b = _write(tmp_path, "living_b.md", f"- {LONG}\n- 고유한 문장 B 이지만 역시 충분히 길게 만들어 실질 라인으로 잡히게 한다 최소 길이 초과")
    dups = find_cross_doc_dups([a, b])
    assert LONG in dups and dups[LONG] == {"living_a.md", "living_b.md"}


def test_unique_line_is_not_reported(tmp_path):
    # The quiet side: a line in only one doc must NOT appear. An always-flagging tool fails here.
    a = _write(tmp_path, "living_a.md", f"- {LONG}")
    b = _write(tmp_path, "living_b.md", "- 전혀 다른 고유 문장으로 두 문서가 공유하지 않으며 충분히 길어 실질 라인이지만 복제는 아니다 최소 길이 초과함")
    dups = find_cross_doc_dups([a, b])
    assert LONG not in dups


def test_short_and_boilerplate_lines_are_ignored(tmp_path):
    a = _write(tmp_path, "living_a.md", "- 짧은 줄\n- 관련: [[X]] · [[Y]]")
    b = _write(tmp_path, "living_b.md", "- 짧은 줄\n- 관련: [[X]] · [[Y]]")
    assert find_cross_doc_dups([a, b]) == {}


def test_dated_and_frozen_docs_are_excluded_from_scope():
    assert is_living("Codex 작업 현황.md")
    assert not is_living("2026-09-21_무언가_검증보고.md")
    assert not is_living("2026-09-21_알람평가_GOV-ALERT-001_복구_Claude.md")  # dated -> excluded
    assert not is_living("S01 기준선.md")


def test_frontmatter_and_headings_are_not_substantive():
    body = "# 제목 헤딩은 실질 라인이 아니다 충분히 길어도 제외되어야 한다 최소 길이 초과 확인용 문장이다\n| 표 | 행 |\n> 인용문도 제외 대상이며 길이가 길어도 실질 라인 아님 최소 길이 초과"
    assert substantive_lines(f"---\ndoc_id: X\nupdated: 2026-09-22\n---\n\n{body}\n") == set()
