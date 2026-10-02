#!/usr/bin/env python3
"""
tools/reproduce_c230_contrast.py

Card 230: Desktop Shell screen (DesktopShell.tsx) WCAG 2.2 AA Contrast Audit.
Evaluates 33 representative UI elements across the Desktop Shell (Top Menu Bar,
Start Menu Dropdown, Notification Center Drawer, Surface Shortcuts, and Bottom Floating Dock)
in both Light and Dark themes using tokens dynamically parsed from apps/web/src/index.css.

Usage:
    python tools/reproduce_c230_contrast.py
"""

import sys
import os
import re
import math

if hasattr(sys.stdout, 'reconfigure'):
    sys.stdout.reconfigure(encoding='utf-8', errors='replace')

REPO_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), '..'))
INDEX_CSS = os.path.join(REPO_ROOT, 'apps', 'web', 'src', 'index.css')

def parse_hex(hex_str: str):
    clean = hex_str.replace('#', '').strip()
    if len(clean) == 3:
        clean = ''.join(c + c for c in clean)
    num = int(clean, 16)
    return ((num >> 16) & 255, (num >> 8) & 255, num & 255)

def srgb_to_linear(val: float) -> float:
    norm = val / 255.0
    return norm / 12.92 if norm <= 0.04045 else math.pow((norm + 0.055) / 1.055, 2.4)

def get_luminance(hex_str: str) -> float:
    r, g, b = parse_hex(hex_str)
    return 0.2126 * srgb_to_linear(r) + 0.7152 * srgb_to_linear(g) + 0.0722 * srgb_to_linear(b)

def get_contrast(hex1: str, hex2: str) -> float:
    l1 = get_luminance(hex1)
    l2 = get_luminance(hex2)
    lighter = max(l1, l2)
    darker = min(l1, l2)
    return (lighter + 0.05) / (darker + 0.05)

def blend_rgba(tint_rgb, alpha: float, underlay_hex: str) -> str:
    under_rgb = parse_hex(underlay_hex)
    r = round(alpha * tint_rgb[0] + (1 - alpha) * under_rgb[0])
    g = round(alpha * tint_rgb[1] + (1 - alpha) * under_rgb[1])
    b = round(alpha * tint_rgb[2] + (1 - alpha) * under_rgb[2])
    return f"#{r:02x}{g:02x}{b:02x}"

def extract_tokens(css_content: str):
    root_match = re.search(r':root\s*\{([\s\S]*?)\}', css_content)
    dark_match = re.search(r"\[data-theme='dark'\]\s*\{([\s\S]*?)\}", css_content)

    def parse_block(block: str):
        tokens = {}
        for line in block.splitlines():
            line = line.strip()
            m = re.match(r'(--color-[a-z0-9-]+)\s*:\s*([^;]+);', line)
            if m:
                tokens[m.group(1)] = m.group(2).strip()
        return tokens

    return parse_block(root_match.group(1)), parse_block(dark_match.group(1))

with open(INDEX_CSS, 'r', encoding='utf-8') as f:
    css_data = f.read()

light_tokens, dark_tokens = extract_tokens(css_data)

AUDIT_ITEMS = [
    # Top System Menu Bar
    ('header text / surface', '--color-text-primary', '--color-bg-surface', 4.5),
    ('header border / surface', '--color-border-subtle', '--color-bg-surface', 3.0),
    ('start menu trigger / surface', '--color-brand-hover', '--color-bg-surface', 4.5),
    ('active window title / surface', '--color-text-primary', '--color-bg-surface', 4.5),
    ('active window sep / surface', '--color-text-muted', '--color-bg-surface', 4.5),
    ('fabric status online / surface', '--color-status-online', '--color-bg-surface', 4.5),
    ('rtt latency text / surface', '--color-text-muted', '--color-bg-surface', 4.5),
    ('mode switcher text / brand-subtle', '--color-brand-hover', '--color-brand-subtle', 4.5),
    ('mode switcher border / brand-subtle', '--color-brand-hover', '--color-brand-subtle', 3.0),
    ('theme toggle icon / surface', '--color-text-secondary', '--color-bg-surface', 4.5),
    ('notif trigger icon / surface', '--color-text-secondary', '--color-bg-surface', 4.5),
    ('notif unread dot / surface', '--color-status-offline', '--color-bg-surface', 3.0),
    ('system clock / surface', '--color-text-primary', '--color-bg-surface', 4.5),

    # Start Menu Dropdown
    ('start menu title / surface', '--color-text-primary', '--color-bg-surface', 4.5),
    ('start menu user id / surface', '--color-text-muted', '--color-bg-surface', 4.5),
    ('start menu border / surface', '--color-border-subtle', '--color-bg-surface', 3.0),
    ('start menu shortcut / surface', '--color-text-primary', '--color-bg-surface', 4.5),
    ('start menu exit link / surface', '--color-brand-hover', '--color-bg-surface', 4.5),

    # Notification Center Drawer
    ('notif center title / surface', '--color-text-primary', '--color-bg-surface', 4.5),
    ('notif close btn / surface', '--color-text-muted', '--color-bg-surface', 4.5),
    ('notif item border / surface', '--color-border-subtle', '--color-bg-surface', 3.0),
    ('notif message text / subtle', '--color-text-secondary', '--color-bg-subtle', 4.5),
    ('notif badge INFO / subtle', '--color-brand-hover', '--color-bg-subtle', 4.5),
    ('notif badge SUCCESS / subtle', '--color-status-online', '--color-bg-subtle', 4.5),
    ('notif badge WARNING / subtle', '--color-status-degraded', '--color-bg-subtle', 4.5),
    ('notif badge ERROR / subtle', '--color-status-offline', '--color-bg-subtle', 4.5),
    ('notif badge UNKNOWN / subtle', '--color-status-unknown', '--color-bg-subtle', 4.5),

    # Desktop Surface Canvas
    ('surface shortcut border / canvas', '--color-border-subtle', '--color-bg-canvas', 3.0),
    ('surface shortcut label / canvas', '--color-text-primary', '--color-bg-canvas', 4.5),

    # Floating Dock Toolbar
    ('dock toolbar border / canvas', '--color-border-subtle', '--color-bg-canvas', 3.0),
    ('dock tile active border / brand-subtle', '--color-brand-hover', '--color-brand-subtle', 3.0),
    ('dock tile inactive border / surface', '--color-border-subtle', '--color-bg-surface', 3.0),
    ('dock running active dot / surface', '--color-brand-hover', '--color-bg-surface', 3.0),
    ('dock running inactive dot / surface', '--color-border-strong', '--color-bg-surface', 3.0),
]

def main():
    print('=' * 110)
    print(' CARD 230: DesktopShell CONTRAST AUDIT (WCAG 2.2 AA)')
    print('=' * 110)
    print(f"{'Item Description':<38} | {'Light Mode':<18} | {'Dark Mode':<18} | {'Min CR':<8} | Status")
    print('-' * 110)

    all_pass = True
    for desc, fg_tok, bg_tok, min_cr in AUDIT_ITEMS:
        l_fg = light_tokens[fg_tok]
        l_bg = light_tokens[bg_tok]
        d_fg = dark_tokens[fg_tok]
        d_bg = dark_tokens[bg_tok]

        l_cr = get_contrast(l_fg, l_bg)
        d_cr = get_contrast(d_fg, d_bg)

        l_ok = l_cr >= min_cr
        d_ok = d_cr >= min_cr
        passed = l_ok and d_ok
        if not passed:
            all_pass = False

        status_str = 'PASS' if passed else 'FAIL'
        l_str = f"{l_cr:5.2f}:1 ({'OK' if l_ok else 'FAIL'})"
        d_str = f"{d_cr:5.2f}:1 ({'OK' if d_ok else 'FAIL'})"

        print(f"{desc:<38} | {l_str:<18} | {d_str:<18} | >={min_cr:<6.1f} | {status_str}")

    print('-' * 110)
    total = len(AUDIT_ITEMS)
    passed_count = total if all_pass else 0
    print(f"Total Audit Items: {total} | Passed: {passed_count} | Failed: {total - passed_count}")

    if all_pass:
        print(f"\n[SUCCESS] All {total} items strictly pass WCAG AA contrast thresholds in both Light and Dark themes.\n")
        return 0
    else:
        print("\n[FAILURE] Contrast regressions detected!\n")
        return 1

if __name__ == '__main__':
    sys.exit(main())
