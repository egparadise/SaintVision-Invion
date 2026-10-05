#!/usr/bin/env python3
"""
tools/reproduce_c281_contrast.py

Reproduce WCAG 2.2 AA Contrast Compliance for Card 281 (MonacoWorkspaceEditor Contrast Tokenization).
Audits:
- apps/web/src/features/editor/MonacoWorkspaceEditor.tsx

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
        '--color-text-primary': '#0f172a',
        '--color-text-secondary': '#475569',
        '--color-text-muted': '#59677b',
        '--color-brand-primary': '#2563eb',
        '--color-brand-hover': '#1d4ed8',
        '--color-brand-subtle': '#dbeafe',
        '--color-brand-warning': '#92400e',
        '--color-status-online': '#15803d',
        '--color-status-offline': '#b91c1c',
        '--color-status-degraded': '#b45309',
        '--color-status-unknown': '#92400e',
        '--color-risk-l3-bg': '#fee2e2',
        '--color-risk-l3-border': '#b91c1c',
        '--color-diff-added-bg': '#dcfce7',
        '--color-diff-added-border': '#16a34a',
    },
    'dark': {
        '--color-bg-canvas': '#090d16',
        '--color-bg-surface': '#111827',
        '--color-bg-subtle': '#1f2937',
        '--color-border-subtle': '#64748b',
        '--color-text-primary': '#f9fafb',
        '--color-text-secondary': '#e5e7eb',
        '--color-text-muted': '#9ca3af',
        '--color-brand-primary': '#60a5fa',
        '--color-brand-hover': '#93c5fd',
        '--color-brand-subtle': '#1e293b',
        '--color-brand-warning': '#f59e0b',
        '--color-status-online': '#22c55e',
        '--color-status-offline': '#f87171',
        '--color-status-degraded': '#f59e0b',
        '--color-status-unknown': '#d29922',
        '--color-risk-l3-bg': '#3b1219',
        '--color-risk-l3-border': '#f87171',
        '--color-diff-added-bg': '#052e16',
        '--color-diff-added-border': '#22c55e',
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
    print("Machine verification: All 19 token declarations match apps/web/src/index.css exactly.")

AUDIT_ITEMS = [
    # Root Container & Notice Banners
    {
        "id": "MWE-1",
        "component": "MonacoWorkspaceEditor",
        "element": "Root editor container",
        "role": "fill",
        "property": "backgroundColor",
        "underlay": "underlay: #f8fafc (L317 desktop canvas background)",
        "before": "#0d1117",
        "token": "--color-bg-canvas",
        "status": "INFO",
        "notes": "Non-boundary fill; container surface background"
    },
    {
        "id": "MWE-2",
        "component": "MonacoWorkspaceEditor",
        "element": "Root editor boundary border",
        "role": "boundary",
        "property": "border",
        "underlay": "underlay: #f8fafc (L319 desktop canvas background)",
        "before": "#30363d",
        "token": "--color-border-subtle",
        "status": "PASS",
        "notes": "WCAG SC 1.4.11 UI boundary border (>= 3.0:1)"
    },
    {
        "id": "MWE-3",
        "component": "MonacoWorkspaceEditor",
        "element": "Root editor base text",
        "role": "text",
        "property": "color",
        "underlay": "underlay: #f8fafc (L318 editor canvas background)",
        "before": "#c9d1d9",
        "token": "--color-text-primary",
        "status": "PASS",
        "notes": "WCAG SC 1.4.3 primary text on canvas (>= 4.5:1)"
    },
    {
        "id": "MWE-4",
        "component": "MonacoWorkspaceEditor",
        "element": "Unexposed notice connected background",
        "role": "fill",
        "property": "backgroundColor",
        "underlay": "underlay: #f8fafc (L331 container background)",
        "before": "rgba(46, 160, 67, 0.12)",
        "token": "--color-diff-added-bg",
        "status": "INFO",
        "notes": "Non-boundary fill; connected status banner fill"
    },
    {
        "id": "MWE-5",
        "component": "MonacoWorkspaceEditor",
        "element": "Unexposed notice connected border",
        "role": "boundary",
        "property": "borderBottom",
        "underlay": "underlay: #dcfce7 (L332 banner background)",
        "before": "#30363d",
        "token": "--color-diff-added-border",
        "status": "PASS",
        "notes": "WCAG SC 1.4.11 status boundary divider (>= 3.0:1)"
    },
    {
        "id": "MWE-6",
        "component": "MonacoWorkspaceEditor",
        "element": "Unexposed notice connected text",
        "role": "text",
        "property": "color",
        "underlay": "underlay: #dcfce7 (L333 banner background)",
        "before": "#3fb950",
        "token": "--color-status-online",
        "status": "PASS",
        "notes": "WCAG SC 1.4.3 connected status text (>= 4.5:1)"
    },
    {
        "id": "MWE-7",
        "component": "MonacoWorkspaceEditor",
        "element": "Unexposed notice unconnected background",
        "role": "fill",
        "property": "backgroundColor",
        "underlay": "underlay: #f8fafc (L331 container background)",
        "before": "rgba(56, 139, 253, 0.12)",
        "token": "--color-brand-subtle",
        "status": "INFO",
        "notes": "Non-boundary fill; sandbox notice banner fill"
    },
    {
        "id": "MWE-8",
        "component": "MonacoWorkspaceEditor",
        "element": "Unexposed notice unconnected border",
        "role": "boundary",
        "property": "borderBottom",
        "underlay": "underlay: #dbeafe (L332 banner background)",
        "before": "#30363d",
        "token": "--color-brand-primary",
        "status": "PASS",
        "notes": "WCAG SC 1.4.11 boundary divider on brand subtle (>= 3.0:1)"
    },
    {
        "id": "MWE-9",
        "component": "MonacoWorkspaceEditor",
        "element": "Unexposed notice unconnected text",
        "role": "text",
        "property": "color",
        "underlay": "underlay: #dbeafe (L333 banner background)",
        "before": "#58a6ff",
        "token": "--color-brand-hover",
        "status": "PASS",
        "notes": "WCAG SC 1.4.3 accent text on brand subtle (>= 4.5:1)"
    },
    {
        "id": "MWE-10",
        "component": "MonacoWorkspaceEditor",
        "element": "Save error banner background",
        "role": "fill",
        "property": "backgroundColor",
        "underlay": "underlay: #f8fafc (L361 container background)",
        "before": "rgba(248, 81, 73, 0.15)",
        "token": "--color-risk-l3-bg",
        "status": "INFO",
        "notes": "Non-boundary fill; error alert banner background"
    },
    {
        "id": "MWE-11",
        "component": "MonacoWorkspaceEditor",
        "element": "Save error banner border",
        "role": "boundary",
        "property": "borderBottom",
        "underlay": "underlay: #fee2e2 (L362 banner background)",
        "before": "#f85149",
        "token": "--color-risk-l3-border",
        "status": "PASS",
        "notes": "WCAG SC 1.4.11 alert boundary divider (>= 3.0:1)"
    },
    {
        "id": "MWE-12",
        "component": "MonacoWorkspaceEditor",
        "element": "Save error banner text",
        "role": "text",
        "property": "color",
        "underlay": "underlay: #fee2e2 (L363 banner background)",
        "before": "#f85149",
        "token": "--color-status-offline",
        "status": "PASS",
        "notes": "WCAG SC 1.4.3 error alert text (>= 4.5:1)"
    },
    {
        "id": "MWE-13",
        "component": "MonacoWorkspaceEditor",
        "element": "Save warning notice background",
        "role": "fill",
        "property": "backgroundColor",
        "underlay": "underlay: #f8fafc (L378 container background)",
        "before": "rgba(227, 179, 65, 0.15)",
        "token": "--color-bg-subtle",
        "status": "INFO",
        "notes": "Non-boundary fill; warning alert banner background"
    },
    {
        "id": "MWE-14",
        "component": "MonacoWorkspaceEditor",
        "element": "Save warning notice border",
        "role": "boundary",
        "property": "borderBottom",
        "underlay": "underlay: #f1f5f9 (L379 banner background)",
        "before": "#e3b341",
        "token": "--color-status-degraded",
        "status": "PASS",
        "notes": "WCAG SC 1.4.11 warning boundary divider (>= 3.0:1)"
    },
    {
        "id": "MWE-15",
        "component": "MonacoWorkspaceEditor",
        "element": "Save warning notice text",
        "role": "text",
        "property": "color",
        "underlay": "underlay: #f1f5f9 (L380 banner background)",
        "before": "#e3b341",
        "token": "--color-status-degraded",
        "status": "PASS",
        "notes": "WCAG SC 1.4.3 warning alert text (>= 4.5:1)"
    },
    {
        "id": "MWE-16",
        "component": "MonacoWorkspaceEditor",
        "element": "Save success notice background",
        "role": "fill",
        "property": "backgroundColor",
        "underlay": "underlay: #f8fafc (L395 container background)",
        "before": "rgba(46, 160, 67, 0.15)",
        "token": "--color-diff-added-bg",
        "status": "INFO",
        "notes": "Non-boundary fill; success alert banner background"
    },
    {
        "id": "MWE-17",
        "component": "MonacoWorkspaceEditor",
        "element": "Save success notice border",
        "role": "boundary",
        "property": "borderBottom",
        "underlay": "underlay: #dcfce7 (L396 banner background)",
        "before": "#2ea043",
        "token": "--color-diff-added-border",
        "status": "PASS",
        "notes": "WCAG SC 1.4.11 success boundary divider (>= 3.0:1)"
    },
    {
        "id": "MWE-18",
        "component": "MonacoWorkspaceEditor",
        "element": "Save success notice text",
        "role": "text",
        "property": "color",
        "underlay": "underlay: #dcfce7 (L397 banner background)",
        "before": "#3fb950",
        "token": "--color-status-online",
        "status": "PASS",
        "notes": "WCAG SC 1.4.3 success alert text (>= 4.5:1)"
    },

    # Main Toolbar & Explorer Sidebar
    {
        "id": "MWE-19",
        "component": "MonacoWorkspaceEditor",
        "element": "Top main toolbar background",
        "role": "fill",
        "property": "backgroundColor",
        "underlay": "underlay: #f8fafc (L413 container background)",
        "before": "#161b22",
        "token": "--color-bg-surface",
        "status": "INFO",
        "notes": "Non-boundary fill; main toolbar surface"
    },
    {
        "id": "MWE-20",
        "component": "MonacoWorkspaceEditor",
        "element": "Top main toolbar border",
        "role": "boundary",
        "property": "borderBottom",
        "underlay": "underlay: #ffffff (L414 toolbar surface)",
        "before": "#30363d",
        "token": "--color-border-subtle",
        "status": "PASS",
        "notes": "WCAG SC 1.4.11 toolbar bottom divider (>= 3.0:1)"
    },
    {
        "id": "MWE-21",
        "component": "MonacoWorkspaceEditor",
        "element": "Top main toolbar workspace label",
        "role": "text",
        "property": "color",
        "underlay": "underlay: #ffffff (L418 toolbar surface)",
        "before": "#f0f6fc",
        "token": "--color-text-primary",
        "status": "PASS",
        "notes": "WCAG SC 1.4.3 toolbar primary label (>= 4.5:1)"
    },
    {
        "id": "MWE-22",
        "component": "MonacoWorkspaceEditor",
        "element": "Top main toolbar workspace ID code",
        "role": "text",
        "property": "color",
        "underlay": "underlay: #ffffff (L419 toolbar surface)",
        "before": "#58a6ff",
        "token": "--color-brand-hover",
        "status": "PASS",
        "notes": "WCAG SC 1.4.3 workspace ID highlight text (>= 4.5:1)"
    },
    {
        "id": "MWE-23",
        "component": "MonacoWorkspaceEditor",
        "element": "Top main toolbar simulate conflict label",
        "role": "text",
        "property": "color",
        "underlay": "underlay: #ffffff (L447 toolbar surface)",
        "before": "#8b949e",
        "token": "--color-text-muted",
        "status": "PASS",
        "notes": "WCAG SC 1.4.3 toolbar checkbox label text (>= 4.5:1)"
    },
    {
        "id": "MWE-24",
        "component": "MonacoWorkspaceEditor",
        "element": "Explorer sidebar background",
        "role": "fill",
        "property": "backgroundColor",
        "underlay": "underlay: #f8fafc (L487 container canvas)",
        "before": "#0d1117",
        "token": "--color-bg-canvas",
        "status": "INFO",
        "notes": "Non-boundary fill; explorer panel background"
    },
    {
        "id": "MWE-25",
        "component": "MonacoWorkspaceEditor",
        "element": "Explorer sidebar border",
        "role": "boundary",
        "property": "borderRight",
        "underlay": "underlay: #f8fafc (L488 sidebar canvas)",
        "before": "#30363d",
        "token": "--color-border-subtle",
        "status": "PASS",
        "notes": "WCAG SC 1.4.11 explorer sidebar vertical divider (>= 3.0:1)"
    },
    {
        "id": "MWE-26",
        "component": "MonacoWorkspaceEditor",
        "element": "Explorer header label",
        "role": "text",
        "property": "color",
        "underlay": "underlay: #f8fafc (L493 sidebar canvas)",
        "before": "#8b949e",
        "token": "--color-text-muted",
        "status": "PASS",
        "notes": "WCAG SC 1.4.3 explorer section header text (>= 4.5:1)"
    },
    {
        "id": "MWE-27",
        "component": "MonacoWorkspaceEditor",
        "element": "Explorer inactive file item text",
        "role": "text",
        "property": "color",
        "underlay": "underlay: #f8fafc (L510 sidebar canvas)",
        "before": "#c9d1d9",
        "token": "--color-text-primary",
        "status": "PASS",
        "notes": "WCAG SC 1.4.3 file item text (>= 4.5:1)"
    },
    {
        "id": "MWE-28",
        "component": "MonacoWorkspaceEditor",
        "element": "Explorer active file item background",
        "role": "fill",
        "property": "backgroundColor",
        "underlay": "underlay: #f8fafc (L509 sidebar canvas)",
        "before": "#1f242c",
        "token": "--color-brand-subtle",
        "status": "INFO",
        "notes": "Non-boundary fill; active file selection highlight"
    },
    {
        "id": "MWE-29",
        "component": "MonacoWorkspaceEditor",
        "element": "Explorer active file item text",
        "role": "text",
        "property": "color",
        "underlay": "underlay: #dbeafe (L510 active item highlight)",
        "before": "#58a6ff",
        "token": "--color-brand-hover",
        "status": "PASS",
        "notes": "WCAG SC 1.4.3 active file text on brand subtle (>= 4.5:1)"
    },
    {
        "id": "MWE-30",
        "component": "MonacoWorkspaceEditor",
        "element": "Explorer dirty file indicator dot",
        "role": "text",
        "property": "color",
        "underlay": "underlay: #dbeafe (L515 active item background)",
        "before": "#e3b341",
        "token": "--color-brand-warning",
        "status": "PASS",
        "notes": "WCAG SC 1.4.3 dirty indicator dot on active highlight (>= 4.5:1)"
    },
    {
        "id": "MWE-31",
        "component": "MonacoWorkspaceEditor",
        "element": "Explorer Git summary commit ID",
        "role": "text",
        "property": "color",
        "underlay": "underlay: #f8fafc (L524 sidebar canvas)",
        "before": "#58a6ff",
        "token": "--color-brand-hover",
        "status": "PASS",
        "notes": "WCAG SC 1.4.3 commit ID monospace text (>= 4.5:1)"
    },
    {
        "id": "MWE-32",
        "component": "MonacoWorkspaceEditor",
        "element": "Explorer Git summary commit message",
        "role": "text",
        "property": "color",
        "underlay": "underlay: #f8fafc (L527 sidebar canvas)",
        "before": "#c9d1d9",
        "token": "--color-text-secondary",
        "status": "PASS",
        "notes": "WCAG SC 1.4.3 commit message summary text (>= 4.5:1)"
    },

    # Frozen Snapshot View & Editor Areas
    {
        "id": "MWE-33",
        "component": "MonacoWorkspaceEditor",
        "element": "Frozen snapshot banner background",
        "role": "fill",
        "property": "backgroundColor",
        "underlay": "underlay: #f8fafc (L548 editor panel canvas)",
        "before": "rgba(56, 139, 253, 0.12)",
        "token": "--color-brand-subtle",
        "status": "INFO",
        "notes": "Non-boundary fill; frozen snapshot header fill"
    },
    {
        "id": "MWE-34",
        "component": "MonacoWorkspaceEditor",
        "element": "Frozen snapshot banner border",
        "role": "boundary",
        "property": "borderBottom",
        "underlay": "underlay: #dbeafe (L549 banner background)",
        "before": "rgba(56, 139, 253, 0.3)",
        "token": "--color-brand-primary",
        "status": "PASS",
        "notes": "WCAG SC 1.4.11 boundary divider on brand subtle (>= 3.0:1)"
    },
    {
        "id": "MWE-35",
        "component": "MonacoWorkspaceEditor",
        "element": "Frozen snapshot banner title",
        "role": "text",
        "property": "color",
        "underlay": "underlay: #dbeafe (L557 banner background)",
        "before": "#58a6ff",
        "token": "--color-brand-hover",
        "status": "PASS",
        "notes": "WCAG SC 1.4.3 frozen title text on brand subtle (>= 4.5:1)"
    },
    {
        "id": "MWE-36",
        "component": "MonacoWorkspaceEditor",
        "element": "Frozen snapshot banner attempt text",
        "role": "text",
        "property": "color",
        "underlay": "underlay: #dbeafe (L560 banner background)",
        "before": "#8b949e",
        "token": "--color-text-secondary",
        "status": "PASS",
        "notes": "WCAG SC 1.4.3 attempt info text on brand subtle (>= 4.5:1)"
    },
    {
        "id": "MWE-37",
        "component": "MonacoWorkspaceEditor",
        "element": "Frozen snapshot read-only badge background",
        "role": "fill",
        "property": "backgroundColor",
        "underlay": "underlay: #ffffff (L591 tab bar surface)",
        "before": "rgba(210, 153, 34, 0.2)",
        "token": "--color-bg-subtle",
        "status": "INFO",
        "notes": "Non-boundary fill; badge background fill"
    },
    {
        "id": "MWE-38",
        "component": "MonacoWorkspaceEditor",
        "element": "Frozen snapshot read-only badge border",
        "role": "boundary",
        "property": "border",
        "underlay": "underlay: #f1f5f9 (L592 badge background)",
        "before": "var(--color-status-degraded)",
        "token": "--color-status-degraded",
        "status": "PASS",
        "notes": "WCAG SC 1.4.11 badge boundary border (>= 3.0:1)"
    },
    {
        "id": "MWE-39",
        "component": "MonacoWorkspaceEditor",
        "element": "Frozen snapshot read-only badge text",
        "role": "text",
        "property": "color",
        "underlay": "underlay: #f1f5f9 (L592 badge background)",
        "before": "#e3b341",
        "token": "--color-status-degraded",
        "status": "PASS",
        "notes": "WCAG SC 1.4.3 badge status text (>= 4.5:1)"
    },
    {
        "id": "MWE-40",
        "component": "MonacoWorkspaceEditor",
        "element": "Editor line number gutter background",
        "role": "fill",
        "property": "backgroundColor",
        "underlay": "underlay: #f8fafc (L610 editor canvas)",
        "before": "#070a0e",
        "token": "--color-bg-subtle",
        "status": "INFO",
        "notes": "Non-boundary fill; gutter column background"
    },
    {
        "id": "MWE-41",
        "component": "MonacoWorkspaceEditor",
        "element": "Editor line number gutter border",
        "role": "boundary",
        "property": "borderRight",
        "underlay": "underlay: #f1f5f9 (L611 gutter background)",
        "before": "#21262d",
        "token": "--color-border-subtle",
        "status": "PASS",
        "notes": "WCAG SC 1.4.11 gutter vertical separator (>= 3.0:1)"
    },
    {
        "id": "MWE-42",
        "component": "MonacoWorkspaceEditor",
        "element": "Editor line number gutter text",
        "role": "text",
        "property": "color",
        "underlay": "underlay: #f1f5f9 (L612 gutter background)",
        "before": "#484f58",
        "token": "--color-text-muted",
        "status": "PASS",
        "notes": "WCAG SC 1.4.3 line numbers text (>= 4.5:1)"
    },
    {
        "id": "MWE-43",
        "component": "MonacoWorkspaceEditor",
        "element": "Frozen snapshot textarea text",
        "role": "text",
        "property": "color",
        "underlay": "underlay: #f8fafc (L634 editor canvas)",
        "before": "#8b949e",
        "token": "--color-text-secondary",
        "status": "PASS",
        "notes": "WCAG SC 1.4.3 frozen code content text (>= 4.5:1)"
    },
    {
        "id": "MWE-44",
        "component": "MonacoWorkspaceEditor",
        "element": "Normal editor tab bar background",
        "role": "fill",
        "property": "backgroundColor",
        "underlay": "underlay: #f8fafc (L656 editor canvas)",
        "before": "#161b22",
        "token": "--color-bg-surface",
        "status": "INFO",
        "notes": "Non-boundary fill; tab bar surface"
    },
    {
        "id": "MWE-45",
        "component": "MonacoWorkspaceEditor",
        "element": "Normal editor tab bar border",
        "role": "boundary",
        "property": "borderBottom",
        "underlay": "underlay: #ffffff (L657 tab bar surface)",
        "before": "#30363d",
        "token": "--color-border-subtle",
        "status": "PASS",
        "notes": "WCAG SC 1.4.11 tab bar bottom separator (>= 3.0:1)"
    },
    {
        "id": "MWE-46",
        "component": "MonacoWorkspaceEditor",
        "element": "Normal editor tab active file text",
        "role": "text",
        "property": "color",
        "underlay": "underlay: #ffffff (L662 tab bar surface)",
        "before": "#f0f6fc",
        "token": "--color-text-primary",
        "status": "PASS",
        "notes": "WCAG SC 1.4.3 active file tab text (>= 4.5:1)"
    },
    {
        "id": "MWE-47",
        "component": "MonacoWorkspaceEditor",
        "element": "Normal editor tab modified text",
        "role": "text",
        "property": "color",
        "underlay": "underlay: #ffffff (L665 tab bar surface)",
        "before": "#e3b341",
        "token": "--color-status-degraded",
        "status": "PASS",
        "notes": "WCAG SC 1.4.3 modified indicator text (>= 4.5:1)"
    },
    {
        "id": "MWE-48",
        "component": "MonacoWorkspaceEditor",
        "element": "Normal editor code textarea text",
        "role": "text",
        "property": "color",
        "underlay": "underlay: #f8fafc (L703 editor canvas)",
        "before": "#c9d1d9",
        "token": "--color-text-primary",
        "status": "PASS",
        "notes": "WCAG SC 1.4.3 code editor text content (>= 4.5:1)"
    },

    # Embedded Terminal PTY Area
    {
        "id": "MWE-49",
        "component": "MonacoWorkspaceEditor",
        "element": "Terminal container border",
        "role": "boundary",
        "property": "borderTop",
        "underlay": "underlay: #f8fafc (L722 terminal canvas)",
        "before": "#30363d",
        "token": "--color-border-subtle",
        "status": "PASS",
        "notes": "WCAG SC 1.4.11 terminal top divider (>= 3.0:1)"
    },
    {
        "id": "MWE-50",
        "component": "MonacoWorkspaceEditor",
        "element": "Terminal title bar background",
        "role": "fill",
        "property": "backgroundColor",
        "underlay": "underlay: #f8fafc (L735 terminal canvas)",
        "before": "#161b22",
        "token": "--color-bg-surface",
        "status": "INFO",
        "notes": "Non-boundary fill; terminal toolbar surface"
    },
    {
        "id": "MWE-51",
        "component": "MonacoWorkspaceEditor",
        "element": "Terminal title bar border",
        "role": "boundary",
        "property": "borderBottom",
        "underlay": "underlay: #ffffff (L736 terminal toolbar surface)",
        "before": "#21262d",
        "token": "--color-border-subtle",
        "status": "PASS",
        "notes": "WCAG SC 1.4.11 terminal title bar divider (>= 3.0:1)"
    },
    {
        "id": "MWE-52",
        "component": "MonacoWorkspaceEditor",
        "element": "Terminal title text",
        "role": "text",
        "property": "color",
        "underlay": "underlay: #ffffff (L741 terminal toolbar surface)",
        "before": "#f0f6fc",
        "token": "--color-text-primary",
        "status": "PASS",
        "notes": "WCAG SC 1.4.3 terminal title text (>= 4.5:1)"
    },
    {
        "id": "MWE-53",
        "component": "MonacoWorkspaceEditor",
        "element": "Terminal mock notice text",
        "role": "text",
        "property": "color",
        "underlay": "underlay: #f1f5f9 (L750 mock badge subtle background)",
        "before": "#e3b341",
        "token": "--color-status-degraded",
        "status": "PASS",
        "notes": "WCAG SC 1.4.3 mock notice text on subtle (>= 4.5:1)"
    },
    {
        "id": "MWE-54",
        "component": "MonacoWorkspaceEditor",
        "element": "Terminal mock notice border",
        "role": "boundary",
        "property": "border",
        "underlay": "underlay: #f1f5f9 (L754 mock badge subtle background)",
        "before": "rgba(227, 179, 65, 0.3)",
        "token": "--color-status-degraded",
        "status": "PASS",
        "notes": "WCAG SC 1.4.11 mock notice badge border (>= 3.0:1)"
    },
    {
        "id": "MWE-55",
        "component": "MonacoWorkspaceEditor",
        "element": "Terminal status connected text",
        "role": "text",
        "property": "color",
        "underlay": "underlay: #dcfce7 (L773 connected badge background)",
        "before": "#3fb950",
        "token": "--color-status-online",
        "status": "PASS",
        "notes": "WCAG SC 1.4.3 connected status text (>= 4.5:1)"
    },
    {
        "id": "MWE-56",
        "component": "MonacoWorkspaceEditor",
        "element": "Terminal status connected border",
        "role": "boundary",
        "property": "border",
        "underlay": "underlay: #dcfce7 (L777 connected badge background)",
        "before": "var(--color-diff-added-border)",
        "token": "--color-diff-added-border",
        "status": "PASS",
        "notes": "WCAG SC 1.4.11 connected badge boundary border (>= 3.0:1)"
    },
    {
        "id": "MWE-57",
        "component": "MonacoWorkspaceEditor",
        "element": "Terminal status recovered text",
        "role": "text",
        "property": "color",
        "underlay": "underlay: #dbeafe (L775 recovered badge background)",
        "before": "#58a6ff",
        "token": "--color-brand-hover",
        "status": "PASS",
        "notes": "WCAG SC 1.4.3 recovered status text on brand subtle (>= 4.5:1)"
    },
    {
        "id": "MWE-58",
        "component": "MonacoWorkspaceEditor",
        "element": "Terminal status recovered border",
        "role": "boundary",
        "property": "border",
        "underlay": "underlay: #dbeafe (L777 recovered badge background)",
        "before": "var(--color-brand-primary)",
        "token": "--color-brand-primary",
        "status": "PASS",
        "notes": "WCAG SC 1.4.11 recovered badge boundary border (>= 3.0:1)"
    },
    {
        "id": "MWE-59",
        "component": "MonacoWorkspaceEditor",
        "element": "Terminal status reconnecting text",
        "role": "text",
        "property": "color",
        "underlay": "underlay: #f1f5f9 (L777 reconnecting badge subtle background)",
        "before": "var(--color-status-degraded)",
        "token": "--color-status-degraded",
        "status": "PASS",
        "notes": "WCAG SC 1.4.3 reconnecting status text (>= 4.5:1)"
    },
    {
        "id": "MWE-60",
        "component": "MonacoWorkspaceEditor",
        "element": "Terminal status disconnected text",
        "role": "text",
        "property": "color",
        "underlay": "underlay: #fee2e2 (L776 disconnected badge background)",
        "before": "#f85149",
        "token": "--color-status-offline",
        "status": "PASS",
        "notes": "WCAG SC 1.4.3 disconnected status text (>= 4.5:1)"
    },
    {
        "id": "MWE-61",
        "component": "MonacoWorkspaceEditor",
        "element": "Terminal status disconnected border",
        "role": "boundary",
        "property": "border",
        "underlay": "underlay: #fee2e2 (L777 disconnected badge background)",
        "before": "var(--color-risk-l3-border)",
        "token": "--color-risk-l3-border",
        "status": "PASS",
        "notes": "WCAG SC 1.4.11 disconnected badge boundary border (>= 3.0:1)"
    },
    {
        "id": "MWE-62",
        "component": "MonacoWorkspaceEditor",
        "element": "Terminal prompt command text",
        "role": "text",
        "property": "color",
        "underlay": "underlay: #f8fafc (L819 terminal output canvas)",
        "before": "#58a6ff",
        "token": "--color-brand-primary",
        "status": "PASS",
        "notes": "WCAG SC 1.4.3 command line prompt text (>= 4.5:1)"
    },
    {
        "id": "MWE-63",
        "component": "MonacoWorkspaceEditor",
        "element": "Terminal command output text",
        "role": "text",
        "property": "color",
        "underlay": "underlay: #f8fafc (L820 terminal output canvas)",
        "before": "#c9d1d9",
        "token": "--color-text-primary",
        "status": "PASS",
        "notes": "WCAG SC 1.4.3 command stdout text (>= 4.5:1)"
    },
    {
        "id": "MWE-64",
        "component": "MonacoWorkspaceEditor",
        "element": "Terminal resume report background",
        "role": "fill",
        "property": "backgroundColor",
        "underlay": "underlay: #f8fafc (L828 terminal output canvas)",
        "before": "rgba(56, 139, 253, 0.1)",
        "token": "--color-brand-subtle",
        "status": "INFO",
        "notes": "Non-boundary fill; recovery callout fill"
    },
    {
        "id": "MWE-65",
        "component": "MonacoWorkspaceEditor",
        "element": "Terminal resume report accent border",
        "role": "boundary",
        "property": "borderLeft",
        "underlay": "underlay: #dbeafe (L829 callout background)",
        "before": "#58a6ff",
        "token": "--color-brand-primary",
        "status": "PASS",
        "notes": "WCAG SC 1.4.11 callout accent border (>= 3.0:1)"
    },
    {
        "id": "MWE-66",
        "component": "MonacoWorkspaceEditor",
        "element": "Terminal resume report text",
        "role": "text",
        "property": "color",
        "underlay": "underlay: #dbeafe (L830 callout background)",
        "before": "#f0f6fc",
        "token": "--color-text-primary",
        "status": "PASS",
        "notes": "WCAG SC 1.4.3 callout message text (>= 4.5:1)"
    },
    {
        "id": "MWE-67",
        "component": "MonacoWorkspaceEditor",
        "element": "Terminal resume report code text",
        "role": "text",
        "property": "color",
        "underlay": "underlay: #dbeafe (L834 callout background)",
        "before": "#58a6ff",
        "token": "--color-brand-hover",
        "status": "PASS",
        "notes": "WCAG SC 1.4.3 callout hash code text (>= 4.5:1)"
    },
    {
        "id": "MWE-68",
        "component": "MonacoWorkspaceEditor",
        "element": "Terminal command form prompt $ symbol",
        "role": "text",
        "property": "color",
        "underlay": "underlay: #f8fafc (L851 terminal input canvas)",
        "before": "#3fb950",
        "token": "--color-status-online",
        "status": "PASS",
        "notes": "WCAG SC 1.4.3 prompt $ symbol text (>= 4.5:1)"
    },
    {
        "id": "MWE-69",
        "component": "MonacoWorkspaceEditor",
        "element": "Terminal command form input text",
        "role": "text",
        "property": "color",
        "underlay": "underlay: #f8fafc (L864 terminal input canvas)",
        "before": "#c9d1d9",
        "token": "--color-text-primary",
        "status": "PASS",
        "notes": "WCAG SC 1.4.3 command input text (>= 4.5:1)"
    }
]

def run_audit():
    verify_tokens_against_index_css()

    print("=" * 80)
    print("ACC-09 Card 281: MonacoWorkspaceEditor Contrast Audit Table")
    print("=" * 80)
    print(f"{'ID':<7} | {'Element':<35} | {'Role':<8} | {'Token':<25} | {'Light CR':<9} | {'Dark CR':<9} | {'Status'}")
    print("-" * 115)

    passed_count = 0
    info_count = 0
    failed_count = 0

    for item in AUDIT_ITEMS:
        tok = item['token']
        role = item['role']

        # Determine underlay hex in light and dark
        # Parse underlay line from string: e.g. "underlay: #f8fafc ..."
        m_underlay = re.search(r'underlay:\s*(#[0-9a-fA-F]{6})', item['underlay'])
        if not m_underlay:
            print(f"Error: underlay hex missing in {item['id']}", file=sys.stderr)
            sys.exit(1)

        ref_light_bg = m_underlay.group(1).lower()

        # Map light underlay hex to token key to look up corresponding dark underlay
        bg_token_key = None
        for k, v in TOKENS['light'].items():
            if v.lower() == ref_light_bg:
                bg_token_key = k
                break

        if not bg_token_key:
            print(f"Error: underlay hex {ref_light_bg} not found in light TOKENS for {item['id']}", file=sys.stderr)
            sys.exit(1)

        light_bg = TOKENS['light'][bg_token_key]
        dark_bg = TOKENS['dark'][bg_token_key]

        light_fg = TOKENS['light'][tok]
        dark_fg = TOKENS['dark'][tok]

        light_cr = get_contrast(light_fg, light_bg)
        dark_cr = get_contrast(dark_fg, dark_bg)

        min_req = 4.5 if role == 'text' else (3.0 if role == 'boundary' else 0.0)

        if role == 'fill':
            status = 'INFO'
            info_count += 1
        elif light_cr >= min_req and dark_cr >= min_req:
            status = 'PASS'
            passed_count += 1
        else:
            status = 'FAIL'
            failed_count += 1

        print(f"{item['id']:<7} | {item['element']:<35} | {role:<8} | {tok:<25} | {light_cr:6.2f}:1  | {dark_cr:6.2f}:1  | {status}")

    print("-" * 115)
    print(f"Summary: {len(AUDIT_ITEMS)} items evaluated.")
    print(f"  PASS: {passed_count} (all WCAG SC 1.4.3 & SC 1.4.11 criteria met)")
    print(f"  INFO: {info_count} (non-boundary fills / surface backgrounds)")
    print(f"  FAIL: {failed_count}")

    if failed_count > 0:
        print("FAIL: One or more audit items failed contrast criteria!", file=sys.stderr)
        sys.exit(1)

    print("SUCCESS: Card 281 MonacoWorkspaceEditor contrast reproduction 100% verified.")

if __name__ == '__main__':
    run_audit()
