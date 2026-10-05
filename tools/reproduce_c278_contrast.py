#!/usr/bin/env python3
"""
tools/reproduce_c278_contrast.py

Reproduce WCAG 2.2 AA Contrast Compliance for Card 278 (DesktopWindow Frame & Controls Contrast Tokenization).
Audits:
- apps/web/src/features/desktop/DesktopWindow.tsx:
  - Window container frame (maximized & floating)
  - Window focus ring / border (active & inactive)
  - Titlebar background and borderBottom (active & inactive)
  - Traffic light controls (close, minimize, maximize) on active subtle & inactive surface
  - Title text and appId status indicator (active & inactive)
  - Fail-closed UNKNOWN fallback in getWindowControlConfig

Strict compliance:
- WCAG SC 1.4.3: Contrast (Minimum) >= 4.5:1 for normal text.
- WCAG SC 1.4.11: Non-text Contrast >= 3.0:1 for user interface component boundaries and states.
- Non-boundary fills (window container / titlebar background against underlays) classified as INFO.
- Box shadow is classified as decorative elevation effect (INFO), with component boundaries defined by solid border or geometry.
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
        '--color-status-online': '#15803d',
        '--color-status-offline': '#b91c1c',
        '--color-status-degraded': '#b45309',
        '--color-status-unknown': '#92400e',
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
        '--color-status-online': '#22c55e',
        '--color-status-offline': '#f87171',
        '--color-status-degraded': '#f59e0b',
        '--color-status-unknown': '#d29922',
    }
}

def verify_tokens_against_index_css():
    """Verify that all tokens in TOKENS exactly match apps/web/src/index.css."""
    index_css_path = Path(__file__).resolve().parent.parent / 'apps' / 'web' / 'src' / 'index.css'
    if not index_css_path.exists():
        index_css_path = Path('apps/web/src/index.css')
    assert index_css_path.exists(), f"Cannot find {index_css_path}"
    content = index_css_path.read_text(encoding='utf-8')

    root_match = re.search(r':root\s*\{([^}]+)\}', content)
    dark_match = re.search(r"\[data-theme=['\"]dark['\"]\]\s*\{([^}]+)\}", content)
    assert root_match, "Failed to find :root block in index.css"
    assert dark_match, "Failed to find [data-theme='dark'] block in index.css"

    def extract_vars(block: str) -> Dict[str, str]:
        res = {}
        for line in block.splitlines():
            line = line.strip()
            m = re.match(r'(--color-[a-z0-9-]+)\s*:\s*([^;]+);', line)
            if m:
                res[m.group(1)] = m.group(2).strip().lower()
        return res

    light_css = extract_vars(root_match.group(1))
    dark_css = extract_vars(dark_match.group(1))

    for theme, expected_dict, actual_css in [
        ('light', TOKENS['light'], light_css),
        ('dark', TOKENS['dark'], dark_css),
    ]:
        for var_name, expected_val in expected_dict.items():
            actual_val = actual_css.get(var_name)
            assert actual_val is not None, f"Token {var_name} missing from index.css ({theme})"
            assert actual_val == expected_val.lower(), (
                f"Token mismatch for {var_name} ({theme}): script has {expected_val}, index.css has {actual_val}"
            )
    print("[PASS] Verified TOKENS table against apps/web/src/index.css declarations.")

AUDIT_ITEMS = [
    {
        'id': 'DW-1',
        'name': 'Window container surface (maximized)',
        'type': 'background',
        'target': 'INFO',
        'line': 'DesktopWindow:110',
        'underlay': 'Desktop viewport canvas (App.tsx:880)',
        'before': {'light': ('#ffffff', '#f8fafc'), 'dark': ('#111827', '#090d16')},
        'after': {'fg': '--color-bg-surface', 'bg': '--color-bg-canvas'},
        'desc': 'Maximized window background fill against desktop canvas underlay',
    },
    {
        'id': 'DW-2',
        'name': 'Window container border (maximized)',
        'type': 'border',
        'target': '>= 3.0:1',
        'line': 'DesktopWindow:113',
        'underlay': 'Desktop viewport canvas (App.tsx:880)',
        'before': {'light': ('#7b8b9e', '#f8fafc'), 'dark': ('#64748b', '#090d16')},
        'after': {'fg': '--color-border-subtle', 'bg': '--color-bg-canvas'},
        'desc': 'Maximized window 1px perimeter border against desktop canvas',
    },
    {
        'id': 'DW-3',
        'name': 'Window container surface (floating)',
        'type': 'background',
        'target': 'INFO',
        'line': 'DesktopWindow:132',
        'underlay': 'Desktop viewport canvas (App.tsx:880)',
        'before': {'light': ('#ffffff', '#f8fafc'), 'dark': ('#111827', '#090d16')},
        'after': {'fg': '--color-bg-surface', 'bg': '--color-bg-canvas'},
        'desc': 'Floating window card background fill against desktop canvas',
    },
    {
        'id': 'DW-4',
        'name': 'Window container border (floating focused)',
        'type': 'border',
        'target': '>= 3.0:1',
        'line': 'DesktopWindow:136',
        'underlay': 'Desktop viewport canvas (App.tsx:880)',
        'before': {'light': ('#475569', '#f8fafc'), 'dark': ('#9ca3af', '#090d16')},
        'after': {'fg': '--color-border-strong', 'bg': '--color-bg-canvas'},
        'desc': 'Floating window perimeter border against desktop canvas underlay (미사용 fallback 제거(위생))',
    },
    {
        'id': 'DW-5',
        'name': 'Window focus ring outline (floating focused)',
        'type': 'border',
        'target': '>= 3.0:1',
        'line': 'DesktopWindow:134',
        'underlay': 'Desktop viewport canvas (App.tsx:880)',
        'before': {'light': ('#2563eb', '#f8fafc'), 'dark': ('#60a5fa', '#090d16')},
        'after': {'fg': '--color-brand-primary', 'bg': '--color-bg-canvas'},
        'desc': 'Active floating window 1px brand focus ring against desktop canvas',
    },
    {
        'id': 'DW-6',
        'name': 'Titlebar background (active)',
        'type': 'background',
        'target': 'INFO',
        'line': 'DesktopWindow:152',
        'underlay': 'Window container surface (DesktopWindow:132)',
        'before': {'light': ('#f1f5f9', '#ffffff'), 'dark': ('#1f2937', '#111827')},
        'after': {'fg': '--color-bg-subtle', 'bg': '--color-bg-surface'},
        'desc': 'Active window title bar background fill against window surface (미사용 fallback 제거(위생))',
    },
    {
        'id': 'DW-7',
        'name': 'Titlebar borderBottom (active)',
        'type': 'border',
        'target': '>= 3.0:1',
        'line': 'DesktopWindow:153',
        'underlay': 'Titlebar subtle (DesktopWindow:152)',
        'before': {'light': ('#7b8b9e', '#f1f5f9'), 'dark': ('#64748b', '#1f2937')},
        'after': {'fg': '--color-border-subtle', 'bg': '--color-bg-subtle'},
        'desc': 'Active window title bar bottom divider border against titlebar subtle (미사용 fallback 제거(위생))',
    },
    {
        'id': 'DW-8',
        'name': 'Titlebar background (inactive)',
        'type': 'background',
        'target': 'INFO',
        'line': 'DesktopWindow:152',
        'underlay': 'Window container surface (DesktopWindow:132)',
        'before': {'light': ('#ffffff', '#ffffff'), 'dark': ('#111827', '#111827')},
        'after': {'fg': '--color-bg-surface', 'bg': '--color-bg-surface'},
        'desc': 'Inactive window title bar background fill against window surface (미사용 fallback 제거(위생))',
    },
    {
        'id': 'DW-9',
        'name': 'Titlebar borderBottom (inactive)',
        'type': 'border',
        'target': '>= 3.0:1',
        'line': 'DesktopWindow:153',
        'underlay': 'Window container surface (DesktopWindow:132)',
        'before': {'light': ('#7b8b9e', '#ffffff'), 'dark': ('#64748b', '#111827')},
        'after': {'fg': '--color-border-subtle', 'bg': '--color-bg-surface'},
        'desc': 'Inactive window title bar bottom divider border against window surface (미사용 fallback 제거(위생))',
    },
    {
        'id': 'DW-10',
        'name': 'Traffic light close button (on active subtle)',
        'type': 'border',
        'target': '>= 3.0:1',
        'line': 'DesktopWindow:174',
        'underlay': 'Titlebar subtle (DesktopWindow:152)',
        'before': {'light': ('#ef4444', '#f1f5f9'), 'dark': ('#ef4444', '#1f2937')},
        'after': {'fg': '--color-status-offline', 'bg': '--color-bg-subtle'},
        'desc': 'Traffic light close button circular boundary against active titlebar',
    },
    {
        'id': 'DW-11',
        'name': 'Traffic light close button (on inactive surface)',
        'type': 'border',
        'target': '>= 3.0:1',
        'line': 'DesktopWindow:174',
        'underlay': 'Titlebar surface (DesktopWindow:152)',
        'before': {'light': ('#ef4444', '#ffffff'), 'dark': ('#ef4444', '#111827')},
        'after': {'fg': '--color-status-offline', 'bg': '--color-bg-surface'},
        'desc': 'Traffic light close button circular boundary against inactive titlebar',
    },
    {
        'id': 'DW-12',
        'name': 'Traffic light minimize button (on active subtle)',
        'type': 'border',
        'target': '>= 3.0:1',
        'line': 'DesktopWindow:193',
        'underlay': 'Titlebar subtle (DesktopWindow:152)',
        'before': {'light': ('#f59e0b', '#f1f5f9'), 'dark': ('#f59e0b', '#1f2937')},
        'after': {'fg': '--color-status-degraded', 'bg': '--color-bg-subtle'},
        'desc': 'Traffic light minimize button circular boundary against active titlebar [DEFECT REPAIR: Light 1.96:1 -> 4.58:1]',
    },
    {
        'id': 'DW-13',
        'name': 'Traffic light minimize button (on inactive surface)',
        'type': 'border',
        'target': '>= 3.0:1',
        'line': 'DesktopWindow:193',
        'underlay': 'Titlebar surface (DesktopWindow:152)',
        'before': {'light': ('#f59e0b', '#ffffff'), 'dark': ('#f59e0b', '#111827')},
        'after': {'fg': '--color-status-degraded', 'bg': '--color-bg-surface'},
        'desc': 'Traffic light minimize button circular boundary against inactive titlebar [DEFECT REPAIR: Light 2.15:1 -> 5.02:1]',
    },
    {
        'id': 'DW-14',
        'name': 'Traffic light maximize button (on active subtle)',
        'type': 'border',
        'target': '>= 3.0:1',
        'line': 'DesktopWindow:212',
        'underlay': 'Titlebar subtle (DesktopWindow:152)',
        'before': {'light': ('#10b981', '#f1f5f9'), 'dark': ('#10b981', '#1f2937')},
        'after': {'fg': '--color-status-online', 'bg': '--color-bg-subtle'},
        'desc': 'Traffic light maximize button circular boundary against active titlebar [DEFECT REPAIR: Light 2.32:1 -> 4.58:1]',
    },
    {
        'id': 'DW-15',
        'name': 'Traffic light maximize button (on inactive surface)',
        'type': 'border',
        'target': '>= 3.0:1',
        'line': 'DesktopWindow:212',
        'underlay': 'Titlebar surface (DesktopWindow:152)',
        'before': {'light': ('#10b981', '#ffffff'), 'dark': ('#10b981', '#111827')},
        'after': {'fg': '--color-status-online', 'bg': '--color-bg-surface'},
        'desc': 'Traffic light maximize button circular boundary against inactive titlebar [DEFECT REPAIR: Light 2.55:1 -> 5.02:1]',
    },
    {
        'id': 'DW-16',
        'name': 'Title text (active)',
        'type': 'text',
        'target': '>= 4.5:1',
        'line': 'DesktopWindow:231',
        'underlay': 'Titlebar subtle (DesktopWindow:152)',
        'before': {'light': ('#0f172a', '#f1f5f9'), 'dark': ('#f9fafb', '#1f2937')},
        'after': {'fg': '--color-text-primary', 'bg': '--color-bg-subtle'},
        'desc': 'Active window title heading text against active titlebar subtle (미사용 fallback 제거(위생))',
    },
    {
        'id': 'DW-17',
        'name': 'Title text (inactive)',
        'type': 'text',
        'target': '>= 4.5:1',
        'line': 'DesktopWindow:231',
        'underlay': 'Titlebar surface (DesktopWindow:152)',
        'before': {'light': ('#59677b', '#ffffff'), 'dark': ('#9ca3af', '#111827')},
        'after': {'fg': '--color-text-muted', 'bg': '--color-bg-surface'},
        'desc': 'Inactive window title heading text against inactive titlebar surface (미사용 fallback 제거(위생))',
    },
    {
        'id': 'DW-18',
        'name': 'Window appId status indicator (active)',
        'type': 'text',
        'target': '>= 4.5:1',
        'line': 'DesktopWindow:240',
        'underlay': 'Titlebar subtle (DesktopWindow:152)',
        'before': {'light': ('#59677b', '#f1f5f9'), 'dark': ('#9ca3af', '#1f2937')},
        'after': {'fg': '--color-text-muted', 'bg': '--color-bg-subtle'},
        'desc': 'Active window auxiliary appId text against active titlebar subtle (미사용 fallback 제거(위생))',
    },
    {
        'id': 'DW-19',
        'name': 'Window appId status indicator (inactive)',
        'type': 'text',
        'target': '>= 4.5:1',
        'line': 'DesktopWindow:240',
        'underlay': 'Titlebar surface (DesktopWindow:152)',
        'before': {'light': ('#59677b', '#ffffff'), 'dark': ('#9ca3af', '#111827')},
        'after': {'fg': '--color-text-muted', 'bg': '--color-bg-surface'},
        'desc': 'Inactive window auxiliary appId text against inactive titlebar surface (미사용 fallback 제거(위생))',
    },
    {
        'id': 'DW-20',
        'name': 'Window control fallback UNKNOWN badge text',
        'type': 'text',
        'target': '>= 4.5:1',
        'line': 'DesktopWindow:39',
        'underlay': 'Titlebar subtle (DesktopWindow:152)',
        'before': {'light': ('#92400e', '#f1f5f9'), 'dark': ('#d29922', '#1f2937')},
        'after': {'fg': '--color-status-unknown', 'bg': '--color-bg-subtle'},
        'desc': 'Fail-closed unknown action badge text on fallback subtle background',
    },
    {
        'id': 'DW-21',
        'name': 'Window control fallback UNKNOWN badge border',
        'type': 'border',
        'target': '>= 3.0:1',
        'line': 'DesktopWindow:41',
        'underlay': 'Titlebar subtle (DesktopWindow:152)',
        'before': {'light': ('#92400e', '#f1f5f9'), 'dark': ('#d29922', '#1f2937')},
        'after': {'fg': '--color-status-unknown', 'bg': '--color-bg-subtle'},
        'desc': 'Fail-closed unknown action badge boundary on fallback subtle background',
    },
]

def main():
    print("=" * 88)
    print("Card 278: ACC-09 DesktopWindow WCAG 2.2 AA Contrast Reproduction")
    print("=" * 88)
    verify_tokens_against_index_css()
    print()

    print(f"{'ID':6} | {'Target':10} | {'Before (L/D)':14} | {'After (L/D)':14} | {'Status':6} | {'Item Name'}")
    print("-" * 88)

    all_passed = True
    for item in AUDIT_ITEMS:
        # Calculate Before
        b_l_fg, b_l_bg = item['before']['light']
        b_d_fg, b_d_bg = item['before']['dark']
        b_cr_l = get_contrast(b_l_fg, b_l_bg)
        b_cr_d = get_contrast(b_d_fg, b_d_bg)

        # Calculate After
        a_fg_tok = item['after']['fg']
        a_bg_tok = item['after']['bg']
        a_l_fg = TOKENS['light'][a_fg_tok]
        a_l_bg = TOKENS['light'][a_bg_tok]
        a_d_fg = TOKENS['dark'][a_fg_tok]
        a_d_bg = TOKENS['dark'][a_bg_tok]

        a_cr_l = get_contrast(a_l_fg, a_l_bg)
        a_cr_d = get_contrast(a_d_fg, a_d_bg)

        target = item['target']
        if target == '>= 4.5:1':
            passed = (a_cr_l >= 4.5 and a_cr_d >= 4.5)
            status = 'PASS' if passed else 'FAIL'
        elif target == '>= 3.0:1':
            passed = (a_cr_l >= 3.0 and a_cr_d >= 3.0)
            status = 'PASS' if passed else 'FAIL'
        elif target == 'INFO':
            passed = True
            status = 'INFO'
        else:
            raise ValueError(f"Unknown target: {target}")

        if not passed:
            all_passed = False

        before_str = f"{b_cr_l:.2f} / {b_cr_d:.2f}"
        after_str = f"{a_cr_l:.2f} / {a_cr_d:.2f}"

        print(f"{item['id']:6} | {target:10} | {before_str:14} | {after_str:14} | {status:6} | {item['name']}")

    print("-" * 88)
    if all_passed:
        print(f"Total Audit Items: {len(AUDIT_ITEMS)}, Passed / Info: {len(AUDIT_ITEMS)}/{len(AUDIT_ITEMS)}")
        print("ALL AUDIT ITEMS COMPLIANT WITH WCAG 2.2 AA SPECIFICATIONS.")
        sys.exit(0)
    else:
        print("SOME AUDIT ITEMS FAILED WCAG 2.2 AA SPECIFICATIONS.")
        sys.exit(1)

if __name__ == '__main__':
    main()
