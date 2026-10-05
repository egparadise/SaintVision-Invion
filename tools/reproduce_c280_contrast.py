#!/usr/bin/env python3
"""
tools/reproduce_c280_contrast.py

Reproduce WCAG 2.2 AA Contrast Compliance for Card 280 (Editor Modals Contrast Tokenization).
Audits:
- apps/web/src/features/editor/ConflictResolutionModal.tsx
- apps/web/src/features/editor/DiffViewer.tsx
- apps/web/src/features/editor/GitCommitModal.tsx

Strict compliance:
- WCAG SC 1.4.3: Contrast (Minimum) >= 4.5:1 for normal text.
- WCAG SC 1.4.11: Non-text Contrast >= 3.0:1 for user interface component boundaries and states.
- Non-boundary fills (containers, subtle backgrounds against surface/canvas) classified as INFO.
- Modal backdrop overlay classified as INFO (non-text visual scrim for light dimming behind dialog; WCAG SC 1.4.11 / SC 1.4.3 N/A).
- All tokens verified directly against apps/web/src/index.css declarations.
"""

import sys
import re
from pathlib import Path
from typing import Dict, Any

def parse_hex(hex_str: str):
    h = hex_str.lstrip('#')
    if len(h) == 3:
        h = ''.join(c * 2 for c in h)
    return [int(h[i:i+2], 16) for i in (0, 2, 4)]

def parse_rgba(rgba_str: str):
    m = re.match(r'rgba?\s*\(\s*(\d+)\s*,\s*(\d+)\s*,\s*(\d+)(?:\s*,\s*([\d.]+))?\s*\)', rgba_str)
    if not m:
        raise ValueError(f"Invalid rgba: {rgba_str}")
    r, g, b = int(m.group(1)), int(m.group(2)), int(m.group(3))
    a = float(m.group(4)) if m.group(4) is not None else 1.0
    return [r, g, b, a]

def blend_rgba(fg_rgba, bg_hex: str) -> str:
    r_f, g_f, b_f, a = fg_rgba
    r_b, g_b, b_b = parse_hex(bg_hex)
    r = round((1 - a) * r_b + a * r_f)
    g = round((1 - a) * g_b + a * g_f)
    b = round((1 - a) * b_b + a * b_f)
    return f"#{r:02x}{g:02x}{b:02x}"

def get_luminance(hex_str: str) -> float:
    r, g, b = [x / 255.0 for x in parse_hex(hex_str)]
    def channel(c: float) -> float:
        return c / 12.92 if c <= 0.03928 else ((c + 0.055) / 1.055) ** 2.4
    return 0.2126 * channel(r) + 0.7152 * channel(g) + 0.0722 * channel(b)

def get_contrast(c1: str, c2: str) -> float:
    l1 = get_luminance(c1)
    l2 = get_luminance(c2)
    lighter = max(l1, l2)
    darker = min(l1, l2)
    return (lighter + 0.05) / (darker + 0.05)

# Canonical tokens from apps/web/src/index.css
TOKENS = {
    'light': {
        '--color-bg-canvas': '#f8fafc',
        '--color-bg-surface': '#ffffff',
        '--color-bg-subtle': '#f1f5f9',
        '--color-bg-backdrop': 'rgba(0, 0, 0, 0.75)',
        '--color-border-subtle': '#7b8b9e',
        '--color-border-strong': '#475569',
        '--color-text-primary': '#0f172a',
        '--color-text-secondary': '#475569',
        '--color-text-muted': '#59677b',
        '--color-brand-primary': '#2563eb',
        '--color-brand-hover': '#1d4ed8',
        '--color-brand-subtle': '#dbeafe',
        '--color-brand-primary-fg': '#ffffff',
        '--color-status-online': '#15803d',
        '--color-status-offline': '#b91c1c',
        '--color-status-degraded': '#b45309',
        '--color-status-unknown': '#92400e',
        '--color-risk-l3-bg': '#fee2e2',
        '--color-risk-l3-border': '#b91c1c',
        '--color-risk-l3-text': '#991b1b',
        '--color-diff-added-bg': '#dcfce7',
        '--color-diff-added-text': '#166534',
        '--color-diff-added-border': '#16a34a',
        '--color-diff-removed-bg': '#fee2e2',
        '--color-diff-removed-text': '#991b1b',
        '--color-diff-removed-border': '#b91c1c',
    },
    'dark': {
        '--color-bg-canvas': '#090d16',
        '--color-bg-surface': '#111827',
        '--color-bg-subtle': '#1f2937',
        '--color-bg-backdrop': 'rgba(0, 0, 0, 0.75)',
        '--color-border-subtle': '#64748b',
        '--color-border-strong': '#9ca3af',
        '--color-text-primary': '#f9fafb',
        '--color-text-secondary': '#e5e7eb',
        '--color-text-muted': '#9ca3af',
        '--color-brand-primary': '#60a5fa',
        '--color-brand-hover': '#93c5fd',
        '--color-brand-subtle': '#1e293b',
        '--color-brand-primary-fg': '#ffffff',
        '--color-status-online': '#22c55e',
        '--color-status-offline': '#f87171',
        '--color-status-degraded': '#f59e0b',
        '--color-status-unknown': '#d29922',
        '--color-risk-l3-bg': '#3b1219',
        '--color-risk-l3-border': '#f87171',
        '--color-risk-l3-text': '#fecaca',
        '--color-diff-added-bg': '#052e16',
        '--color-diff-added-text': '#4ade80',
        '--color-diff-added-border': '#22c55e',
        '--color-diff-removed-bg': '#3b1219',
        '--color-diff-removed-text': '#fca5a5',
        '--color-diff-removed-border': '#f87171',
    }
}

def verify_tokens_against_index_css():
    css_path = Path(__file__).resolve().parent.parent / 'apps' / 'web' / 'src' / 'index.css'
    if not css_path.exists():
        print(f"Warning: CSS file not found at {css_path}", file=sys.stderr)
        return
    css = css_path.read_text(encoding='utf-8')
    root_match = re.search(r':root\s*\{([^}]+)\}', css)
    dark_match = re.search(r"\[data-theme='dark'\]\s*\{([^}]+)\}", css)
    if not root_match or not dark_match:
        print("Warning: Could not parse root or dark theme from index.css", file=sys.stderr)
        return
    
    root_block = root_match.group(1)
    dark_block = dark_match.group(1)
    
    for theme, block in [('light', root_block), ('dark', dark_block)]:
        for token, expected in TOKENS[theme].items():
            pattern = re.compile(rf'{re.escape(token)}\s*:\s*([^;]+);')
            m = pattern.search(block)
            if not m:
                print(f"CSS Token Missing: {token} in {theme}", file=sys.stderr)
                sys.exit(1)
            actual = m.group(1).strip()
            if actual != expected:
                print(f"CSS Token Mismatch for {token} in {theme}: expected {expected}, got {actual}", file=sys.stderr)
                sys.exit(1)
    print("Machine verification: All 26 token declarations match apps/web/src/index.css exactly.")

AUDIT_ITEMS = [
    # ConflictResolutionModal (EM-1 ~ EM-11)
    {
        "id": "EM-1",
        "name": "Modal backdrop overlay (scrim on canvas)",
        "loc": "ConflictResolutionModal:131",
        "target": "INFO",
        "kind": "bg",
        "underlay": "--color-bg-canvas",
        "before_hex": {"light": ("#000000", "#f8fafc"), "dark": ("#000000", "#090d16")},
        "after_token": ("--color-bg-backdrop", "--color-bg-canvas"),
        "nature": "스크림 오버레이 토큰화(WCAG SC 1.4.11 / 1.4.3 N/A)",
    },
    {
        "id": "EM-2",
        "name": "Dialog container (surface on canvas)",
        "loc": "ConflictResolutionModal:145",
        "target": "INFO",
        "kind": "bg",
        "underlay": "--color-bg-canvas",
        "before_hex": {"light": ("#161b22", "#f8fafc"), "dark": ("#161b22", "#090d16")},
        "after_token": ("--color-bg-surface", "--color-bg-canvas"),
        "nature": "모달 컨테이너 표면 테마 시맨틱 토큰화",
    },
    {
        "id": "EM-3",
        "name": "Dialog boundary (offline status border on surface)",
        "loc": "ConflictResolutionModal:146",
        "target": ">= 3.0:1",
        "kind": "border",
        "underlay": "--color-bg-surface",
        "before_hex": {"light": ("#f85149", "#ffffff"), "dark": ("#f85149", "#111827")},
        "after_token": ("--color-status-offline", "--color-bg-surface"),
        "nature": "상태 연동 경계선 비텍스트 대비 충족",
    },
    {
        "id": "EM-4",
        "name": "Warning banner (risk-l3 fill on surface)",
        "loc": "ConflictResolutionModal:159",
        "target": "INFO",
        "kind": "bg",
        "underlay": "--color-bg-surface",
        "before_hex": {"light": ("#fee2e2", "#ffffff"), "dark": ("#3b1219", "#111827")},
        "after_token": ("--color-risk-l3-bg", "--color-bg-surface"),
        "nature": "경고 배너 배경 시맨틱 위험도 토큰화",
    },
    {
        "id": "EM-5",
        "name": "Warning title text (offline status on risk-l3-bg)",
        "loc": "ConflictResolutionModal:168",
        "target": ">= 4.5:1",
        "kind": "text",
        "underlay": "--color-risk-l3-bg",
        "before_hex": {"light": ("#f85149", "#fee2e2"), "dark": ("#f85149", "#3b1219")},
        "after_token": ("--color-status-offline", "--color-risk-l3-bg"),
        "nature": "경고 제목 텍스트 최소 대비 보장",
    },
    {
        "id": "EM-6",
        "name": "Warning description (text-muted on risk-l3-bg)",
        "loc": "ConflictResolutionModal:184",
        "target": ">= 4.5:1",
        "kind": "text",
        "underlay": "--color-risk-l3-bg",
        "before_hex": {"light": ("#8b949e", "#fee2e2"), "dark": ("#8b949e", "#3b1219")},
        "after_token": ("--color-text-muted", "--color-risk-l3-bg"),
        "nature": "부제목 보조 텍스트 대비 보장",
    },
    {
        "id": "EM-7",
        "name": "Warning code text (brand-hover on risk-l3-bg)",
        "loc": "ConflictResolutionModal:185",
        "target": ">= 4.5:1",
        "kind": "text",
        "underlay": "--color-risk-l3-bg",
        "before_hex": {"light": ("#58a6ff", "#fee2e2"), "dark": ("#58a6ff", "#3b1219")},
        "after_token": ("--color-brand-hover", "--color-risk-l3-bg"),
        "nature": "파일 경로 모노스페이스 텍스트 대비 보장",
    },
    {
        "id": "EM-8",
        "name": "Action footer background (canvas on surface)",
        "loc": "ConflictResolutionModal:204",
        "target": "INFO",
        "kind": "bg",
        "underlay": "--color-bg-surface",
        "before_hex": {"light": ("#0d1117", "#ffffff"), "dark": ("#0d1117", "#111827")},
        "after_token": ("--color-bg-canvas", "--color-bg-surface"),
        "nature": "하단 액션 영역 배경 시맨틱 토큰화",
    },
    {
        "id": "EM-9",
        "name": "Action footer borderTop (border-subtle on canvas)",
        "loc": "ConflictResolutionModal:203",
        "target": ">= 3.0:1",
        "kind": "border",
        "underlay": "--color-bg-canvas",
        "before_hex": {"light": ("#30363d", "#f8fafc"), "dark": ("#30363d", "#090d16")},
        "after_token": ("--color-border-subtle", "--color-bg-canvas"),
        "nature": "액션 영역 상단 경계선 비텍스트 대비 보장",
    },
    {
        "id": "EM-10",
        "name": "Action footer guidance text (text-muted on canvas)",
        "loc": "ConflictResolutionModal:210",
        "target": ">= 4.5:1",
        "kind": "text",
        "underlay": "--color-bg-canvas",
        "before_hex": {"light": ("#8b949e", "#f8fafc"), "dark": ("#8b949e", "#090d16")},
        "after_token": ("--color-text-muted", "--color-bg-canvas"),
        "nature": "안내 문구 보조 텍스트 대비 보장",
    },
    {
        "id": "EM-11",
        "name": "Force overwrite button text (offline status on canvas)",
        "loc": "ConflictResolutionModal:222",
        "target": ">= 4.5:1",
        "kind": "text",
        "underlay": "--color-bg-canvas",
        "before_hex": {"light": ("#f85149", "#f8fafc"), "dark": ("#f85149", "#090d16")},
        "after_token": ("--color-status-offline", "--color-bg-canvas"),
        "nature": "파괴적 액션 버튼 텍스트 대비 보장",
    },

    # DiffViewer (EM-12 ~ EM-24)
    {
        "id": "EM-12",
        "name": "Diff container background (canvas on surface)",
        "loc": "DiffViewer:75",
        "target": "INFO",
        "kind": "bg",
        "underlay": "--color-bg-surface",
        "before_hex": {"light": ("#0d1117", "#ffffff"), "dark": ("#0d1117", "#111827")},
        "after_token": ("--color-bg-canvas", "--color-bg-surface"),
        "nature": "코드 뷰어 배경 시맨틱 토큰화",
    },
    {
        "id": "EM-13",
        "name": "Diff header background (surface on canvas)",
        "loc": "DiffViewer:89",
        "target": "INFO",
        "kind": "bg",
        "underlay": "--color-bg-canvas",
        "before_hex": {"light": ("#161b22", "#f8fafc"), "dark": ("#161b22", "#090d16")},
        "after_token": ("--color-bg-surface", "--color-bg-canvas"),
        "nature": "헤더 바 배경 시맨틱 토큰화",
    },
    {
        "id": "EM-14",
        "name": "Diff header borderBottom (border-subtle on surface)",
        "loc": "DiffViewer:88",
        "target": ">= 3.0:1",
        "kind": "border",
        "underlay": "--color-bg-surface",
        "before_hex": {"light": ("#30363d", "#ffffff"), "dark": ("#30363d", "#111827")},
        "after_token": ("--color-border-subtle", "--color-bg-surface"),
        "nature": "헤더 구분 경계선 비텍스트 대비 충족",
    },
    {
        "id": "EM-15",
        "name": "Diff file path text (text-primary on surface)",
        "loc": "DiffViewer:93",
        "target": ">= 4.5:1",
        "kind": "text",
        "underlay": "--color-bg-surface",
        "before_hex": {"light": ("#f0f6fc", "#ffffff"), "dark": ("#f0f6fc", "#111827")},
        "after_token": ("--color-text-primary", "--color-bg-surface"),
        "nature": "파일 경로 주요 텍스트 고대비 보장",
    },
    {
        "id": "EM-16",
        "name": "Diff additions count (diff-added-text on surface)",
        "loc": "DiffViewer:94",
        "target": ">= 4.5:1",
        "kind": "text",
        "underlay": "--color-bg-surface",
        "before_hex": {"light": ("#3fb950", "#ffffff"), "dark": ("#3fb950", "#111827")},
        "after_token": ("--color-diff-added-text", "--color-bg-surface"),
        "nature": "추가 줄 카운트 시맨틱 텍스트 대비 보장",
    },
    {
        "id": "EM-17",
        "name": "Diff deletions count (diff-removed-text on surface)",
        "loc": "DiffViewer:95",
        "target": ">= 4.5:1",
        "kind": "text",
        "underlay": "--color-bg-surface",
        "before_hex": {"light": ("#f85149", "#ffffff"), "dark": ("#f85149", "#111827")},
        "after_token": ("--color-diff-removed-text", "--color-bg-surface"),
        "nature": "삭제 줄 카운트 시맨틱 텍스트 대비 보장",
    },
    {
        "id": "EM-18",
        "name": "Diff added line background (added-bg on canvas)",
        "loc": "DiffViewer:143",
        "target": "INFO",
        "kind": "bg",
        "underlay": "--color-bg-canvas",
        "before_hex": {"light": ("#dcfce7", "#f8fafc"), "dark": ("#052e16", "#090d16")},
        "after_token": ("--color-diff-added-bg", "--color-bg-canvas"),
        "nature": "추가 코드 줄 전용 배경 토큰화",
    },
    {
        "id": "EM-19",
        "name": "Diff added line text (added-text on added-bg)",
        "loc": "DiffViewer:178",
        "target": ">= 4.5:1",
        "kind": "text",
        "underlay": "--color-diff-added-bg",
        "before_hex": {"light": ("#3fb950", "#dcfce7"), "dark": ("#3fb950", "#052e16")},
        "after_token": ("--color-diff-added-text", "--color-diff-added-bg"),
        "nature": "추가 줄 배경 위 코드 텍스트 4.5:1 대비 충족",
    },
    {
        "id": "EM-20",
        "name": "Diff added line border (added-border on canvas)",
        "loc": "DiffViewer:144",
        "target": ">= 3.0:1",
        "kind": "border",
        "underlay": "--color-bg-canvas",
        "before_hex": {"light": ("#3fb950", "#f8fafc"), "dark": ("#3fb950", "#090d16")},
        "after_token": ("--color-diff-added-border", "--color-bg-canvas"),
        "nature": "추가 줄 좌측 인디케이터 경계선 대비 보장",
    },
    {
        "id": "EM-21",
        "name": "Diff removed line background (removed-bg on canvas)",
        "loc": "DiffViewer:143",
        "target": "INFO",
        "kind": "bg",
        "underlay": "--color-bg-canvas",
        "before_hex": {"light": ("#fee2e2", "#f8fafc"), "dark": ("#3b1219", "#090d16")},
        "after_token": ("--color-diff-removed-bg", "--color-bg-canvas"),
        "nature": "삭제 코드 줄 전용 배경 토큰화",
    },
    {
        "id": "EM-22",
        "name": "Diff removed line text (removed-text on removed-bg)",
        "loc": "DiffViewer:178",
        "target": ">= 4.5:1",
        "kind": "text",
        "underlay": "--color-diff-removed-bg",
        "before_hex": {"light": ("#f85149", "#fee2e2"), "dark": ("#f85149", "#3b1219")},
        "after_token": ("--color-diff-removed-text", "--color-diff-removed-bg"),
        "nature": "삭제 줄 배경 위 코드 텍스트 4.5:1 대비 충족",
    },
    {
        "id": "EM-23",
        "name": "Diff removed line border (removed-border on canvas)",
        "loc": "DiffViewer:144",
        "target": ">= 3.0:1",
        "kind": "border",
        "underlay": "--color-bg-canvas",
        "before_hex": {"light": ("#f85149", "#f8fafc"), "dark": ("#f85149", "#090d16")},
        "after_token": ("--color-diff-removed-border", "--color-bg-canvas"),
        "nature": "삭제 줄 좌측 인디케이터 경계선 대비 보장",
    },
    {
        "id": "EM-24",
        "name": "Diff line numbers gutter (text-muted on canvas)",
        "loc": "DiffViewer:152",
        "target": ">= 4.5:1",
        "kind": "text",
        "underlay": "--color-bg-canvas",
        "before_hex": {"light": ("#484f58", "#f8fafc"), "dark": ("#484f58", "#090d16")},
        "after_token": ("--color-text-muted", "--color-bg-canvas"),
        "nature": "거터 줄 번호 텍스트 가독성 확보",
    },

    # GitCommitModal (EM-25 ~ EM-32)
    {
        "id": "EM-25",
        "name": "Commit input background (canvas on surface)",
        "loc": "GitCommitModal:198",
        "target": "INFO",
        "kind": "bg",
        "underlay": "--color-bg-surface",
        "before_hex": {"light": ("#0d1117", "#ffffff"), "dark": ("#0d1117", "#111827")},
        "after_token": ("--color-bg-canvas", "--color-bg-surface"),
        "nature": "입력 필드 배경 시맨틱 토큰화",
    },
    {
        "id": "EM-26",
        "name": "Commit input border (border-subtle on surface)",
        "loc": "GitCommitModal:199",
        "target": ">= 3.0:1",
        "kind": "border",
        "underlay": "--color-bg-surface",
        "before_hex": {"light": ("#30363d", "#ffffff"), "dark": ("#30363d", "#111827")},
        "after_token": ("--color-border-subtle", "--color-bg-surface"),
        "nature": "입력 필드 외곽선 비텍스트 대비 보장",
    },
    {
        "id": "EM-27",
        "name": "Commit input text (text-primary on canvas)",
        "loc": "GitCommitModal:201",
        "target": ">= 4.5:1",
        "kind": "text",
        "underlay": "--color-bg-canvas",
        "before_hex": {"light": ("#c9d1d9", "#f8fafc"), "dark": ("#c9d1d9", "#090d16")},
        "after_token": ("--color-text-primary", "--color-bg-canvas"),
        "nature": "사용자 입력 내용 고대비 텍스트 충족",
    },
    {
        "id": "EM-28",
        "name": "Required asterisk indicator (offline status on surface)",
        "loc": "GitCommitModal:210",
        "target": ">= 4.5:1",
        "kind": "text",
        "underlay": "--color-bg-surface",
        "before_hex": {"light": ("#f85149", "#ffffff"), "dark": ("#f85149", "#111827")},
        "after_token": ("--color-status-offline", "--color-bg-surface"),
        "nature": "필수 입력 항목 인디케이터 대비 충족",
    },
    {
        "id": "EM-29",
        "name": "Stage all action button (brand-hover on surface)",
        "loc": "GitCommitModal:243",
        "target": ">= 4.5:1",
        "kind": "text",
        "underlay": "--color-bg-surface",
        "before_hex": {"light": ("#58a6ff", "#ffffff"), "dark": ("#58a6ff", "#111827")},
        "after_token": ("--color-brand-hover", "--color-bg-surface"),
        "nature": "빠른 실행 버튼 텍스트 대비 충족",
    },
    {
        "id": "EM-30",
        "name": "Staged files list border (border-subtle on surface)",
        "loc": "GitCommitModal:264",
        "target": ">= 3.0:1",
        "kind": "border",
        "underlay": "--color-bg-surface",
        "before_hex": {"light": ("#30363d", "#ffffff"), "dark": ("#30363d", "#111827")},
        "after_token": ("--color-border-subtle", "--color-bg-surface"),
        "nature": "파일 목록 스크롤 영역 경계선 대비 보장",
    },
    {
        "id": "EM-31",
        "name": "Modified file status text (status-degraded on canvas)",
        "loc": "GitCommitModal:294",
        "target": ">= 4.5:1",
        "kind": "text",
        "underlay": "--color-bg-canvas",
        "before_hex": {"light": ("#e3b341", "#f8fafc"), "dark": ("#e3b341", "#090d16")},
        "after_token": ("--color-status-degraded", "--color-bg-canvas"),
        "nature": "수정된 파일명 상태 텍스트 대비 보장",
    },
    {
        "id": "EM-32",
        "name": "Clean file status text (text-secondary on canvas)",
        "loc": "GitCommitModal:294",
        "target": ">= 4.5:1",
        "kind": "text",
        "underlay": "--color-bg-canvas",
        "before_hex": {"light": ("#c9d1d9", "#f8fafc"), "dark": ("#c9d1d9", "#090d16")},
        "after_token": ("--color-text-secondary", "--color-bg-canvas"),
        "nature": "미수정 파일명 보조 텍스트 대비 충족",
    },
]

def run_audits():
    verify_tokens_against_index_css()
    print("========================================================================================")
    print("CARD 280 (EditorModals) WCAG 2.2 AA DYNAMIC CONTRAST AUDIT REPORT")
    print("========================================================================================")
    print(f"{'ID':<6} | {'Target':<10} | {'Before (L/D)':<14} | {'After (L/D)':<14} | {'Status':<6} | {'Item Name'}")
    print("----------------------------------------------------------------------------------------")

    failures = 0
    for item in AUDIT_ITEMS:
        target = item["target"]
        if target == "INFO":
            status = "INFO"
            b_str = "N/A"
            a_str = "N/A"
        else:
            # Before calculations
            b_fg_l, b_bg_l = item["before_hex"]["light"]
            b_fg_d, b_bg_d = item["before_hex"]["dark"]
            b_l_cr = get_contrast(b_fg_l, b_bg_l)
            b_d_cr = get_contrast(b_fg_d, b_bg_d)

            # After calculations
            a_fg_tok, a_bg_tok = item["after_token"]
            a_fg_l = TOKENS['light'][a_fg_tok]
            a_bg_l = TOKENS['light'][a_bg_tok]
            a_fg_d = TOKENS['dark'][a_fg_tok]
            a_bg_d = TOKENS['dark'][a_bg_tok]

            a_l_cr = get_contrast(a_fg_l, a_bg_l)
            a_d_cr = get_contrast(a_fg_d, a_bg_d)

            if target == ">= 4.5:1":
                status = "PASS" if a_l_cr >= 4.5 and a_d_cr >= 4.5 else "FAIL"
            elif target == ">= 3.0:1":
                status = "PASS" if a_l_cr >= 3.0 and a_d_cr >= 3.0 else "FAIL"
            else:
                status = "UNKNOWN"

            if status == "FAIL":
                failures += 1

            b_str = f"{b_l_cr:.2f} / {b_d_cr:.2f}"
            a_str = f"{a_l_cr:.2f} / {a_d_cr:.2f}"

        print(f"{item['id']:<6} | {target:<10} | {b_str:<14} | {a_str:<14} | {status:<6} | {item['name']}")

    print("----------------------------------------------------------------------------------------")
    print(f"Total Audit Items: {len(AUDIT_ITEMS)}, Failures: {failures}")
    if failures == 0:
        print("ALL AUDIT ITEMS COMPLIANT WITH WCAG 2.2 AA SPECIFICATIONS.")
    else:
        print("SOME AUDIT ITEMS FAILED COMPLIANCE.")
        sys.exit(1)

if __name__ == '__main__':
    run_audits()
