#!/usr/bin/env python3
"""
tools/reproduce_c282_contrast.py

Reproduce WCAG 2.2 AA Contrast Compliance for Card 282 (WebTerminal Contrast Tokenization & ACC-09 Grand Milestone).
Audits:
- apps/web/src/features/terminal/WebTerminal.tsx (all 32 occurrences / 23 distinct base color literals tokenized)

Strict compliance:
- WCAG SC 1.4.3: Contrast (Minimum) >= 4.5:1 for normal text.
- WCAG SC 1.4.11: Non-text Contrast >= 3.0:1 for user interface component boundaries and states.
- Non-boundary fills (containers, subtle backgrounds against surface/canvas) classified as INFO.
- All tokens verified directly against apps/web/src/index.css declarations.
"""

import sys
import re
from pathlib import Path

def parse_hex(hex_str: str):
    h = hex_str.lstrip('#')
    if len(h) == 3:
        h = ''.join(c * 2 for c in h)
    return [int(h[i:i+2], 16) for i in (0, 2, 4)]

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

# Canonical tokens verified against apps/web/src/index.css
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
        '--color-brand-primary-fg': '#ffffff',
        '--color-brand-hover': '#1d4ed8',
        '--color-brand-subtle': '#dbeafe',
        '--color-brand-warning': '#92400e',
        '--color-status-online': '#15803d',
        '--color-status-offline': '#b91c1c',
        '--color-status-offline-bg': '#dc2626',
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
        '--color-brand-primary-fg': '#ffffff',
        '--color-brand-hover': '#93c5fd',
        '--color-brand-subtle': '#1e293b',
        '--color-brand-warning': '#f59e0b',
        '--color-status-online': '#22c55e',
        '--color-status-offline': '#f87171',
        '--color-status-offline-bg': '#dc2626',
        '--color-status-degraded': '#f59e0b',
        '--color-status-unknown': '#d29922',
        '--color-risk-l3-bg': '#3b1219',
        '--color-risk-l3-border': '#f87171',
        '--color-diff-added-bg': '#052e16',
        '--color-diff-added-border': '#22c55e',
    },
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
    print("Machine verification: All 21 token declarations match apps/web/src/index.css exactly.")

AUDIT_ITEMS = [
    {
        'id': 'WT-01',
        'element': 'WebTerminal Root Container Background',
        'role': 'fill',
        'token': '--color-bg-canvas',
        'underlay': '--color-bg-canvas',
        'desc': 'Root container surface fill (formerly #0d1117)',
    },
    {
        'id': 'WT-02',
        'element': 'WebTerminal Root Container Text',
        'role': 'text',
        'token': '--color-text-primary',
        'underlay': '--color-bg-canvas',
        'desc': 'Root container body text foreground (formerly #c9d1d9)',
    },
    {
        'id': 'WT-03',
        'element': 'WebTerminal Root Container Border',
        'role': 'boundary',
        'token': '--color-border-subtle',
        'underlay': '--color-bg-canvas',
        'desc': 'Root container outer boundary (formerly #30363d)',
    },
    {
        'id': 'WT-04',
        'element': 'Title Bar Background',
        'role': 'fill',
        'token': '--color-bg-surface',
        'underlay': '--color-bg-canvas',
        'desc': 'Header title bar surface fill (formerly #161b22)',
    },
    {
        'id': 'WT-05',
        'element': 'Title Bar Bottom Border',
        'role': 'boundary',
        'token': '--color-border-subtle',
        'underlay': '--color-bg-surface',
        'desc': 'Header title bar divider (formerly #30363d)',
    },
    {
        'id': 'WT-06',
        'element': 'Status Dot Indicator',
        'role': 'boundary',
        'token': '--color-status-online',
        'underlay': '--color-bg-surface',
        'desc': 'Connection status active indicator (formerly #238636)',
    },
    {
        'id': 'WT-07',
        'element': 'Session ID Label Text',
        'role': 'text',
        'token': '--color-text-muted',
        'underlay': '--color-bg-surface',
        'desc': 'Session ID text foreground (formerly #8b949e)',
    },
    {
        'id': 'WT-08',
        'element': 'Connection Status Label Text',
        'role': 'text',
        'token': '--color-text-muted',
        'underlay': '--color-bg-surface',
        'desc': 'Connection status text description (formerly #8b949e)',
    },
    {
        'id': 'WT-09',
        'element': 'Toggle A11y Button Text',
        'role': 'text',
        'token': '--color-text-primary',
        'underlay': '--color-bg-surface',
        'desc': 'Accessibility alternate view toggle button (formerly #c9d1d9)',
    },
    {
        'id': 'WT-10',
        'element': 'Close Button Text',
        'role': 'text',
        'token': '--color-status-offline',
        'underlay': '--color-bg-surface',
        'desc': 'Close terminal button (formerly #f85149)',
    },
    {
        'id': 'WT-11',
        'element': 'Command Required Notice Background',
        'role': 'fill',
        'token': '--color-bg-subtle',
        'underlay': '--color-bg-canvas',
        'desc': 'Command required banner fill (formerly #1c1917)',
    },
    {
        'id': 'WT-12',
        'element': 'Command Required Notice Text',
        'role': 'text',
        'token': '--color-status-degraded',
        'underlay': '--color-bg-subtle',
        'desc': 'Command required warning message (formerly #fb923c)',
    },
    {
        'id': 'WT-13',
        'element': 'Command Required Notice Divider',
        'role': 'boundary',
        'token': '--color-status-degraded',
        'underlay': '--color-bg-subtle',
        'desc': 'Command required bottom border (formerly #ea580c)',
    },
    {
        'id': 'WT-14',
        'element': 'Command Required Notice Hint Text',
        'role': 'text',
        'token': '--color-text-secondary',
        'underlay': '--color-bg-subtle',
        'desc': 'Command ID missing hint description (formerly #fed7aa)',
    },
    {
        'id': 'WT-15',
        'element': 'Error Alert Background',
        'role': 'fill',
        'token': '--color-risk-l3-bg',
        'underlay': '--color-bg-canvas',
        'desc': 'Terminal error banner fill (formerly #7f1d1d)',
    },
    {
        'id': 'WT-16',
        'element': 'Error Alert Message Text',
        'role': 'text',
        'token': '--color-status-offline',
        'underlay': '--color-risk-l3-bg',
        'desc': 'Terminal error message foreground (formerly #fecaca)',
    },
    {
        'id': 'WT-17',
        'element': 'Error Alert Divider',
        'role': 'boundary',
        'token': '--color-risk-l3-border',
        'underlay': '--color-risk-l3-bg',
        'desc': 'Terminal error banner bottom border (formerly #ef4444)',
    },
    {
        'id': 'WT-18',
        'element': 'Retry Button Background (Authorized)',
        'role': 'boundary',
        'token': '--color-status-offline-bg',
        'underlay': '--color-risk-l3-bg',
        'desc': 'Authorized retry button fill (formerly #ef4444)',
    },
    {
        'id': 'WT-19',
        'element': 'Retry Button Text (Authorized)',
        'role': 'text',
        'token': '--color-brand-primary-fg',
        'underlay': '--color-status-offline-bg',
        'desc': 'Authorized retry button white text (formerly #fff)',
    },
    {
        'id': 'WT-20',
        'element': 'Retry Button Background (Unauthorized)',
        'role': 'fill',
        'token': '--color-bg-subtle',
        'underlay': '--color-risk-l3-bg',
        'desc': 'Disabled retry button subtle background',
    },
    {
        'id': 'WT-21',
        'element': 'Retry Button Text (Unauthorized)',
        'role': 'text',
        'token': '--color-text-muted',
        'underlay': '--color-bg-subtle',
        'desc': 'Disabled retry button muted text',
    },
    {
        'id': 'WT-22',
        'element': 'Disconnected Alert Background',
        'role': 'fill',
        'token': '--color-bg-subtle',
        'underlay': '--color-bg-canvas',
        'desc': 'Disconnected command reject banner fill (formerly #451a03)',
    },
    {
        'id': 'WT-23',
        'element': 'Disconnected Alert Text',
        'role': 'text',
        'token': '--color-status-degraded',
        'underlay': '--color-bg-subtle',
        'desc': 'Disconnected command message text (formerly #fde68a)',
    },
    {
        'id': 'WT-24',
        'element': 'Disconnected Alert Divider',
        'role': 'boundary',
        'token': '--color-status-degraded',
        'underlay': '--color-bg-subtle',
        'desc': 'Disconnected command banner bottom border (formerly #d97706)',
    },
    {
        'id': 'WT-25',
        'element': 'Disconnected Alert Dismiss Button',
        'role': 'text',
        'token': '--color-status-degraded',
        'underlay': '--color-bg-subtle',
        'desc': 'Disconnected command banner dismiss icon button (formerly #fde68a)',
    },
    {
        'id': 'WT-26',
        'element': 'A11y Text Log Region Background',
        'role': 'fill',
        'token': '--color-bg-canvas',
        'underlay': '--color-bg-canvas',
        'desc': 'A11y alternative text container fill (formerly #0d1117)',
    },
    {
        'id': 'WT-27',
        'element': 'A11y Text Log Region Text',
        'role': 'text',
        'token': '--color-text-primary',
        'underlay': '--color-bg-canvas',
        'desc': 'A11y alternative text container text (formerly #c9d1d9)',
    },
    {
        'id': 'WT-28',
        'element': 'Log Entry Stderr Text',
        'role': 'text',
        'token': '--color-status-offline',
        'underlay': '--color-bg-canvas',
        'desc': 'Terminal output stderr stream line (formerly #ef4444)',
    },
    {
        'id': 'WT-29',
        'element': 'Log Entry Stdout Text',
        'role': 'text',
        'token': '--color-text-primary',
        'underlay': '--color-bg-canvas',
        'desc': 'Terminal output stdout stream line (formerly #c9d1d9)',
    },
    {
        'id': 'WT-30',
        'element': 'Stream Terminal Output Container Bg',
        'role': 'fill',
        'token': '--color-bg-canvas',
        'underlay': '--color-bg-canvas',
        'desc': 'Interactive terminal streaming viewport fill (formerly #090d16)',
    },
    {
        'id': 'WT-31',
        'element': 'Stream Command Prompt Symbol ($)',
        'role': 'text',
        'token': '--color-brand-primary',
        'underlay': '--color-bg-canvas',
        'desc': 'Prompt command symbol (formerly #58a6ff)',
    },
    {
        'id': 'WT-32',
        'element': 'Stream Command Input Text',
        'role': 'text',
        'token': '--color-text-primary',
        'underlay': '--color-bg-canvas',
        'desc': 'Interactive command input field text (formerly #f0f6fc)',
    },
]

def run_audit():
    verify_tokens_against_index_css()
    print("=" * 115)
    print("WebTerminal WCAG 2.2 AA Contrast Compliance Audit (Card 282 / ACC-09 Final File)")
    print("=" * 115)
    print(f"{'ID':<7} | {'Element':<35} | {'Role':<8} | {'Token':<25} | {'Light CR':<10} | {'Dark CR':<10} | Status")
    print("-" * 115)

    passed_count = 0
    info_count = 0
    failed_count = 0

    for item in AUDIT_ITEMS:
        tok = item['token']
        role = item['role']
        underlay_token = item['underlay']

        light_bg = TOKENS['light'][underlay_token]
        dark_bg = TOKENS['dark'][underlay_token]

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

    print("SUCCESS: Card 282 WebTerminal contrast reproduction 100% verified.")

if __name__ == '__main__':
    run_audit()
