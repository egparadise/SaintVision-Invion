#!/usr/bin/env python3
"""
tools/reproduce_c279_contrast.py

Reproduce WCAG 2.2 AA Contrast Compliance for Card 279 (TerminalSessionView Contrast Tokenization).
Audits:
- apps/web/src/features/desktop/TerminalSessionView.tsx:
  - Session view container & empty notice container
  - Tablist container & borderBottom
  - Active & Inactive tabs (background, borderTop, borderRight, text)
  - Tab close button
  - New session select & dropdown
  - Observation node error alert (background, borderBottom, text)
  - Active node hostname & IP
  - Shell badges (powershell, bash, zsh, cmd, fallback UNKNOWN)
  - PTY auth badges (ticket_bound, awaiting_command, fallback UNKNOWN)
  - Run select & Command ID inputs
  - Switch mode button (IDE / Terminal)
  - Empty nodes notice (banner background, borderBottom, text, operator advice)

Strict compliance:
- WCAG SC 1.4.3: Contrast (Minimum) >= 4.5:1 for normal text.
- WCAG SC 1.4.11: Non-text Contrast >= 3.0:1 for user interface component boundaries and states.
- Non-boundary fills (containers, subtle backgrounds against surface/canvas) classified as INFO.
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
        '--color-border-subtle': '#7b8b9e',
        '--color-border-strong': '#475569',
        '--color-text-primary': '#0f172a',
        '--color-text-secondary': '#475569',
        '--color-text-muted': '#59677b',
        '--color-brand-primary': '#2563eb',
        '--color-brand-hover': '#1d4ed8',
        '--color-brand-subtle': '#dbeafe',
        '--color-status-online': '#15803d',
        '--color-status-offline': '#b91c1c',
        '--color-status-degraded': '#b45309',
        '--color-status-unknown': '#92400e',
        '--color-risk-l3-bg': '#fee2e2',
        '--color-risk-l3-border': '#b91c1c',
        '--color-risk-l3-text': '#991b1b',
    },
    'dark': {
        '--color-bg-canvas': '#090d16',
        '--color-bg-surface': '#111827',
        '--color-bg-subtle': '#1f2937',
        '--color-border-subtle': '#64748b',
        '--color-border-strong': '#9ca3af',
        '--color-text-primary': '#f9fafb',
        '--color-text-secondary': '#e5e7eb',
        '--color-text-muted': '#9ca3af',
        '--color-brand-primary': '#60a5fa',
        '--color-brand-hover': '#93c5fd',
        '--color-brand-subtle': '#1e293b',
        '--color-status-online': '#22c55e',
        '--color-status-offline': '#f87171',
        '--color-status-degraded': '#f59e0b',
        '--color-status-unknown': '#d29922',
        '--color-risk-l3-bg': '#3b1219',
        '--color-risk-l3-border': '#f87171',
        '--color-risk-l3-text': '#fecaca',
    }
}

def verify_tokens_against_index_css():
    index_css_path = Path(__file__).resolve().parent.parent / 'apps' / 'web' / 'src' / 'index.css'
    if not index_css_path.exists():
        print(f"WARN: index.css not found at {index_css_path}")
        return
    css = index_css_path.read_text(encoding='utf-8')
    light_m = re.search(r":root\s*\{([^}]+)\}", css)
    dark_m = re.search(r"\[data-theme='dark'\]\s*\{([^}]+)\}", css)
    if not light_m or not dark_m:
        print("WARN: Could not parse theme blocks in index.css")
        return

    def parse_vars(block: str) -> Dict[str, str]:
        res = {}
        for line in block.splitlines():
            line = line.strip()
            if line.startswith('--') and ':' in line:
                k, v = line.split(':', 1)
                res[k.strip()] = v.split(';')[0].strip()
        return res

    light_css = parse_vars(light_m.group(1))
    dark_css = parse_vars(dark_m.group(1))

    for theme in ('light', 'dark'):
        css_dict = light_css if theme == 'light' else dark_css
        for tok, hex_val in TOKENS[theme].items():
            actual = css_dict.get(tok)
            if not actual or actual.lower() != hex_val.lower():
                raise AssertionError(f"Token mismatch in {theme}: {tok} expected {hex_val}, got {actual}")

# Helper for switch mode button base background (rgba(59, 130, 246, 0.15) over --color-bg-subtle)
b_switch_bg_l = blend_rgba(parse_rgba("rgba(59, 130, 246, 0.15)"), TOKENS['light']['--color-bg-subtle'])
b_switch_bg_d = blend_rgba(parse_rgba("rgba(59, 130, 246, 0.15)"), TOKENS['dark']['--color-bg-subtle'])

# Audit items for TerminalSessionView
AUDIT_ITEMS = [
    {
        "id": "TS-1",
        "name": "Session view container (surface on canvas)",
        "loc": "TerminalSessionView:255",
        "target": "INFO",
        "kind": "bg",
        "underlay": "--color-bg-canvas",
        "before_hex": {"light": ("#ffffff", "#f8fafc"), "dark": ("#111827", "#090d16")},
        "after_token": ("--color-bg-surface", "--color-bg-canvas"),
        "nature": "미사용 fallback 제거(위생)",
    },
    {
        "id": "TS-2",
        "name": "Tablist container (subtle on surface)",
        "loc": "TerminalSessionView:267",
        "target": "INFO",
        "kind": "bg",
        "underlay": "--color-bg-surface",
        "before_hex": {"light": ("#f1f5f9", "#ffffff"), "dark": ("#1e293b", "#111827")},
        "after_token": ("--color-bg-subtle", "--color-bg-surface"),
        "nature": "미사용 fallback 제거(위생)",
    },
    {
        "id": "TS-3",
        "name": "Tablist borderBottom (boundary on subtle)",
        "loc": "TerminalSessionView:268",
        "target": ">= 3.0:1",
        "kind": "border",
        "underlay": "--color-bg-subtle",
        "before_hex": {"light": ("#7b8b9e", "#f1f5f9"), "dark": ("#64748b", "#1f2937")},
        "after_token": ("--color-border-subtle", "--color-bg-subtle"),
        "nature": "미사용 fallback 제거(위생)",
    },
    {
        "id": "TS-4",
        "name": "Active tab background (surface on subtle)",
        "loc": "TerminalSessionView:289",
        "target": "INFO",
        "kind": "bg",
        "underlay": "--color-bg-subtle",
        "before_hex": {"light": ("#ffffff", "#f1f5f9"), "dark": ("#111827", "#1f2937")},
        "after_token": ("--color-bg-surface", "--color-bg-subtle"),
        "nature": "미사용 fallback 제거(위생)",
    },
    {
        "id": "TS-5",
        "name": "Active tab indicator borderTop (brand on surface)",
        "loc": "TerminalSessionView:290",
        "target": ">= 3.0:1",
        "kind": "border",
        "underlay": "--color-bg-surface",
        "before_hex": {"light": ("#2563eb", "#ffffff"), "dark": ("#60a5fa", "#111827")},
        "after_token": ("--color-brand-primary", "--color-bg-surface"),
        "nature": "미사용 fallback 제거(위생)",
    },
    {
        "id": "TS-6",
        "name": "Active tab right border (subtle on surface)",
        "loc": "TerminalSessionView:291",
        "target": ">= 3.0:1",
        "kind": "border",
        "underlay": "--color-bg-surface",
        "before_hex": {"light": ("#7b8b9e", "#ffffff"), "dark": ("#64748b", "#111827")},
        "after_token": ("--color-border-subtle", "--color-bg-surface"),
        "nature": "미사용 fallback 제거(위생)",
    },
    {
        "id": "TS-7",
        "name": "Active tab text (text on surface)",
        "loc": "TerminalSessionView:292",
        "target": ">= 4.5:1",
        "kind": "text",
        "underlay": "--color-bg-surface",
        "before_hex": {"light": ("#0f172a", "#ffffff"), "dark": ("#f9fafb", "#111827")},
        "after_token": ("--color-text-primary", "--color-bg-surface"),
        "nature": "미사용 fallback 제거(위생)",
    },
    {
        "id": "TS-8",
        "name": "Inactive tab text (text on subtle)",
        "loc": "TerminalSessionView:292",
        "target": ">= 4.5:1",
        "kind": "text",
        "underlay": "--color-bg-subtle",
        "before_hex": {"light": ("#59677b", "#f1f5f9"), "dark": ("#9ca3af", "#1f2937")},
        "after_token": ("--color-text-muted", "--color-bg-subtle"),
        "nature": "미사용 fallback 제거(위생)",
    },
    {
        "id": "TS-9",
        "name": "Tab close button text (text on surface)",
        "loc": "TerminalSessionView:313",
        "target": ">= 4.5:1",
        "kind": "text",
        "underlay": "--color-bg-surface",
        "before_hex": {"light": ("#59677b", "#ffffff"), "dark": ("#9ca3af", "#111827")},
        "after_token": ("--color-text-muted", "--color-bg-surface"),
        "nature": "미사용 fallback 제거(위생)",
    },
    {
        "id": "TS-10",
        "name": "New session select background (surface on subtle)",
        "loc": "TerminalSessionView:343",
        "target": "INFO",
        "kind": "bg",
        "underlay": "--color-bg-subtle",
        "before_hex": {"light": ("#ffffff", "#f1f5f9"), "dark": ("#111827", "#1f2937")},
        "after_token": ("--color-bg-surface", "--color-bg-subtle"),
        "nature": "미사용 fallback 제거(위생)",
    },
    {
        "id": "TS-11",
        "name": "New session select border (border on subtle)",
        "loc": "TerminalSessionView:345",
        "target": ">= 3.0:1",
        "kind": "border",
        "underlay": "--color-bg-subtle",
        "before_hex": {"light": ("#475569", "#f1f5f9"), "dark": ("#9ca3af", "#1f2937")},
        "after_token": ("--color-border-strong", "--color-bg-subtle"),
        "nature": "미사용 fallback 제거(위생)",
    },
    {
        "id": "TS-12",
        "name": "Observation node error alert background (risk-l3-bg on surface)",
        "loc": "TerminalSessionView:379",
        "target": "INFO",
        "kind": "bg",
        "underlay": "--color-bg-surface",
        "before_hex": {"light": ("#7f1d1d", "#ffffff"), "dark": ("#7f1d1d", "#111827")},
        "after_token": ("--color-risk-l3-bg", "--color-bg-surface"),
        "nature": "테마 시맨틱 토큰화",
    },
    {
        "id": "TS-13",
        "name": "Observation node error alert borderBottom (risk-l3-border on risk-l3-bg)",
        "loc": "TerminalSessionView:382",
        "target": ">= 3.0:1",
        "kind": "border",
        "underlay": "--color-risk-l3-bg",
        "before_hex": {"light": ("#ef4444", "#7f1d1d"), "dark": ("#ef4444", "#7f1d1d")},
        "after_token": ("--color-risk-l3-border", "--color-risk-l3-bg"),
        "nature": "대비 결손 수리 (경계선 비텍스트 대비 보장)",
    },
    {
        "id": "TS-14",
        "name": "Observation node error alert text (risk-l3-text on risk-l3-bg)",
        "loc": "TerminalSessionView:380",
        "target": ">= 4.5:1",
        "kind": "text",
        "underlay": "--color-risk-l3-bg",
        "before_hex": {"light": ("#fecaca", "#7f1d1d"), "dark": ("#fecaca", "#7f1d1d")},
        "after_token": ("--color-risk-l3-text", "--color-risk-l3-bg"),
        "nature": "테마 시맨틱 토큰화",
    },
    {
        "id": "TS-15",
        "name": "Active node hostname text (primary on subtle)",
        "loc": "TerminalSessionView:423",
        "target": ">= 4.5:1",
        "kind": "text",
        "underlay": "--color-bg-subtle",
        "before_hex": {"light": ("#0f172a", "#f1f5f9"), "dark": ("#f9fafb", "#1f2937")},
        "after_token": ("--color-text-primary", "--color-bg-subtle"),
        "nature": "미사용 fallback 제거(위생)",
    },
    {
        "id": "TS-16",
        "name": "Shell badge: powershell text (on subtle)",
        "loc": "TerminalSessionView:14",
        "target": ">= 4.5:1",
        "kind": "text",
        "underlay": "--color-bg-subtle",
        "before_hex": {"light": ("#38bdf8", "#f1f5f9"), "dark": ("#38bdf8", "#1f2937")},
        "after_token": ("--color-brand-hover", "--color-bg-subtle"),
        "nature": "대비 결손 수리 (라이트 텍스트 대비 미달 해소)",
    },
    {
        "id": "TS-17",
        "name": "Shell badge: bash text (on subtle)",
        "loc": "TerminalSessionView:18",
        "target": ">= 4.5:1",
        "kind": "text",
        "underlay": "--color-bg-subtle",
        "before_hex": {"light": ("#4ade80", "#f1f5f9"), "dark": ("#4ade80", "#1f2937")},
        "after_token": ("--color-status-online", "--color-bg-subtle"),
        "nature": "대비 결손 수리 (라이트 텍스트 대비 미달 해소)",
    },
    {
        "id": "TS-18",
        "name": "Shell badge: zsh text (on subtle)",
        "loc": "TerminalSessionView:22",
        "target": ">= 4.5:1",
        "kind": "text",
        "underlay": "--color-bg-subtle",
        "before_hex": {"light": ("#fbbf24", "#f1f5f9"), "dark": ("#fbbf24", "#1f2937")},
        "after_token": ("--color-brand-hover", "--color-bg-subtle"),
        "nature": "대비 결손 수리 (라이트 텍스트 대비 미달 해소)",
    },
    {
        "id": "TS-19",
        "name": "Shell badge: cmd text (on subtle)",
        "loc": "TerminalSessionView:26",
        "target": ">= 4.5:1",
        "kind": "text",
        "underlay": "--color-bg-subtle",
        "before_hex": {"light": ("#0f172a", "#f1f5f9"), "dark": ("#f9fafb", "#1f2937")},
        "after_token": ("--color-text-primary", "--color-bg-subtle"),
        "nature": "테마 시맨틱 토큰화",
    },
    {
        "id": "TS-20",
        "name": "PTY auth badge: ticket_bound text (on subtle)",
        "loc": "TerminalSessionView:51",
        "target": ">= 4.5:1",
        "kind": "text",
        "underlay": "--color-bg-subtle",
        "before_hex": {"light": ("#fbbf24", "#f1f5f9"), "dark": ("#fbbf24", "#1f2937")},
        "after_token": ("--color-status-degraded", "--color-bg-subtle"),
        "nature": "대비 결손 수리 (라이트 텍스트 대비 미달 해소)",
    },
    {
        "id": "TS-21",
        "name": "PTY auth badge: awaiting_command text (on subtle)",
        "loc": "TerminalSessionView:55",
        "target": ">= 4.5:1",
        "kind": "text",
        "underlay": "--color-bg-subtle",
        "before_hex": {"light": ("#94a3b8", "#f1f5f9"), "dark": ("#94a3b8", "#1f2937")},
        "after_token": ("--color-text-muted", "--color-bg-subtle"),
        "nature": "대비 결손 수리 (라이트 텍스트 대비 미달 해소)",
    },
    {
        "id": "TS-22",
        "name": "Run select & Command ID border (on subtle)",
        "loc": "TerminalSessionView:459",
        "target": ">= 3.0:1",
        "kind": "border",
        "underlay": "--color-bg-subtle",
        "before_hex": {"light": ("#334155", "#f1f5f9"), "dark": ("#334155", "#1f2937")},
        "after_token": ("--color-border-strong", "--color-bg-subtle"),
        "nature": "대비 결손 수리 (다크 비텍스트 대비 미달 해소)",
    },
    {
        "id": "TS-23",
        "name": "Run select & Command ID text (on surface)",
        "loc": "TerminalSessionView:461",
        "target": ">= 4.5:1",
        "kind": "text",
        "underlay": "--color-bg-surface",
        "before_hex": {"light": ("#f8fafc", "#0f172a"), "dark": ("#f8fafc", "#0f172a")},
        "after_token": ("--color-text-primary", "--color-bg-surface"),
        "nature": "테마 시맨틱 토큰화",
    },
    {
        "id": "TS-24",
        "name": "Switch mode button background (brand-subtle on subtle)",
        "loc": "TerminalSessionView:501",
        "target": "INFO",
        "kind": "bg",
        "underlay": "--color-bg-subtle",
        "before_hex": {"light": (b_switch_bg_l, TOKENS['light']['--color-bg-subtle']), "dark": (b_switch_bg_d, TOKENS['dark']['--color-bg-subtle'])},
        "after_token": ("--color-brand-subtle", "--color-bg-subtle"),
        "nature": "생 rgba 투명도 리터럴을 테마 시맨틱 토큰으로 승격 (시맨틱 토큰화)",
    },
    {
        "id": "TS-25",
        "name": "Switch mode button border (brand-primary on brand-subtle)",
        "loc": "TerminalSessionView:502",
        "target": ">= 3.0:1",
        "kind": "border",
        "underlay": "--color-brand-subtle",
        "before_hex": {"light": ("#2563eb", b_switch_bg_l), "dark": ("#60a5fa", b_switch_bg_d)},
        "after_token": ("--color-brand-primary", "--color-brand-subtle"),
        "nature": "비텍스트 대비 보장",
    },
    {
        "id": "TS-26",
        "name": "Switch mode button text (brand-hover on brand-subtle)",
        "loc": "TerminalSessionView:503",
        "target": ">= 4.5:1",
        "kind": "text",
        "underlay": "--color-brand-subtle",
        "before_hex": {"light": ("#60a5fa", b_switch_bg_l), "dark": ("#60a5fa", b_switch_bg_d)},
        "after_token": ("--color-brand-hover", "--color-brand-subtle"),
        "nature": "대비 결손 수리 (라이트 텍스트 대비 미달 해소)",
    },
    {
        "id": "TS-27",
        "name": "Empty nodes notice container background (subtle on surface)",
        "loc": "TerminalSessionView:176",
        "target": "INFO",
        "kind": "bg",
        "underlay": "--color-bg-surface",
        "before_hex": {"light": ("#1e293b", "#ffffff"), "dark": ("#1e293b", "#111827")},
        "after_token": ("--color-bg-subtle", "--color-bg-surface"),
        "nature": "테마 시맨틱 토큰화 (라이트 다크 패널 해소)",
    },
    {
        "id": "TS-28",
        "name": "Empty nodes notice borderBottom (subtle on subtle)",
        "loc": "TerminalSessionView:179",
        "target": ">= 3.0:1",
        "kind": "border",
        "underlay": "--color-bg-subtle",
        "before_hex": {"light": ("#334155", "#1e293b"), "dark": ("#334155", "#1e293b")},
        "after_token": ("--color-border-subtle", "--color-bg-subtle"),
        "nature": "대비 결손 수리 (경계선 비텍스트 대비 보장)",
    },
    {
        "id": "TS-29",
        "name": "Empty nodes notice text (text-muted on subtle)",
        "loc": "TerminalSessionView:177",
        "target": ">= 4.5:1",
        "kind": "text",
        "underlay": "--color-bg-subtle",
        "before_hex": {"light": ("#94a3b8", "#1e293b"), "dark": ("#94a3b8", "#1e293b")},
        "after_token": ("--color-text-muted", "--color-bg-subtle"),
        "nature": "테마 시맨틱 토큰화",
    },
    {
        "id": "TS-30",
        "name": "Empty nodes notice operator advice (degraded on subtle)",
        "loc": "TerminalSessionView:187",
        "target": ">= 4.5:1",
        "kind": "text",
        "underlay": "--color-bg-subtle",
        "before_hex": {"light": ("#fed7aa", "#f1f5f9"), "dark": ("#fed7aa", "#1e293b")},
        "after_token": ("--color-status-degraded", "--color-bg-subtle"),
        "nature": "대비 결손 수리 (라이트 텍스트 대비 미달 해소)",
    },
    {
        "id": "TS-31",
        "name": "Fallback UNKNOWN shell badge text (unknown on subtle)",
        "loc": "TerminalSessionView:36",
        "target": ">= 4.5:1",
        "kind": "text",
        "underlay": "--color-bg-subtle",
        "before_hex": {"light": ("#92400e", "#f1f5f9"), "dark": ("#d29922", "#1f2937")},
        "after_token": ("--color-status-unknown", "--color-bg-subtle"),
        "nature": "fail-closed UNKNOWN 토큰화",
    },
    {
        "id": "TS-32",
        "name": "Fallback UNKNOWN PTY auth badge text (unknown on subtle)",
        "loc": "TerminalSessionView:69",
        "target": ">= 4.5:1",
        "kind": "text",
        "underlay": "--color-bg-subtle",
        "before_hex": {"light": ("#92400e", "#f1f5f9"), "dark": ("#d29922", "#1f2937")},
        "after_token": ("--color-status-unknown", "--color-bg-subtle"),
        "nature": "fail-closed UNKNOWN 토큰화",
    },
]

def run_audits():
    verify_tokens_against_index_css()
    print("========================================================================================")
    print("CARD 279 (TerminalSessionView) WCAG 2.2 AA DYNAMIC CONTRAST AUDIT REPORT")
    print("========================================================================================")
    print(f"{'ID':<6} | {'Target':<10} | {'Before (L/D)':<14} | {'After (L/D)':<14} | {'Status':<6} | {'Item Name'}")
    print("----------------------------------------------------------------------------------------")

    failures = 0
    for item in AUDIT_ITEMS:
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

        target = item["target"]
        if target == "INFO":
            status = "INFO"
        elif target == ">= 4.5:1":
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
