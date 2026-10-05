#!/usr/bin/env python3
"""
tools/reproduce_c277_contrast.py

Reproduce WCAG 2.2 AA Contrast Compliance for Card 277 (App Shell & Release Engine Contrast Tokenization).
Audits:
- App.tsx (Global action error banner, simulation controls, workspace error banner, terminal notice)
- releaseEngine.ts (WCAG 1.4.3 text contrast audit, WCAG 1.4.11 non-text boundary audit)

Strict compliance:
- WCAG SC 1.4.3: Contrast (Minimum) >= 4.5:1 for normal text.
- WCAG SC 1.4.11: Non-text Contrast >= 3.0:1 for user interface component boundaries and states.
- Non-boundary fills (component backgrounds against underlays) classified as INFO.
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
        '--color-brand-primary-bg': '#2563eb',
        '--color-brand-primary-fg': '#ffffff',
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
        '--color-brand-primary-bg': '#1d4ed8',
        '--color-brand-primary-fg': '#ffffff',
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
    """Verify that TOKENS table exactly matches index.css declarations."""
    css_path = Path(__file__).resolve().parent.parent / 'apps' / 'web' / 'src' / 'index.css'
    content = css_path.read_text(encoding='utf-8')
    root_match = re.search(r':root\s*\{([^}]+)\}', content)
    dark_match = re.search(r"\[data-theme=['\"]dark['\"]\]\s*\{([^}]+)\}", content)
    assert root_match and dark_match, "Failed to parse index.css theme blocks"

    def parse_block(block_str):
        decl = {}
        for m in re.finditer(r'(--[a-z0-9-]+)\s*:\s*([^;]+);', block_str):
            decl[m.group(1).strip()] = m.group(2).strip()
        return decl

    light_decl = parse_block(root_match.group(1))
    dark_decl = parse_block(dark_match.group(1))

    for token, val in TOKENS['light'].items():
        assert token in light_decl, f"Token {token} missing in index.css :root"
        assert light_decl[token] == val, f"Token {token} mismatch in light: script={val}, css={light_decl[token]}"
    for token, val in TOKENS['dark'].items():
        assert token in dark_decl, f"Token {token} missing in index.css dark"
        assert dark_decl[token] == val, f"Token {token} mismatch in dark: script={val}, css={dark_decl[token]}"

AUDIT_ITEMS = [
    # App.tsx items
    {
        'id': 'AP-1',
        'component': 'App',
        'name': 'Global action error banner text',
        'type': 'text',
        'target': '4.5:1 text',
        'before': {'fg_raw': '#991b1b', 'bg_raw': '#fee2e2'},
        'after': {'fg_token': '--color-risk-l3-text', 'bg_token': '--color-risk-l3-bg'},
    },
    {
        'id': 'AP-2',
        'component': 'App',
        'name': 'Global action error banner borderBottom',
        'type': 'border',
        'target': '3.0:1 non-text',
        'before': {'border_raw': '#f87171', 'parent_token': '--color-bg-canvas'},
        'after': {'border_token': '--color-risk-l3-border', 'parent_token': '--color-bg-canvas'},
    },
    {
        'id': 'AP-3',
        'component': 'App',
        'name': 'Global error dismiss button background (fill on banner)',
        'type': 'background',
        'target': 'INFO (non-boundary fill; boundary defined by risk-l3-border AP-5)',
        'before': {'bg_raw': '#ffffff', 'parent_raw': '#fee2e2'},
        'after': {'bg_token': '--color-bg-surface', 'parent_token': '--color-risk-l3-bg'},
    },
    {
        'id': 'AP-4',
        'component': 'App',
        'name': 'Global error dismiss button text',
        'type': 'text',
        'target': '4.5:1 text',
        'before': {'fg_raw': '#991b1b', 'bg_raw': '#ffffff'},
        'after': {'fg_token': '--color-risk-l3-text', 'bg_token': '--color-bg-surface'},
    },
    {
        'id': 'AP-5',
        'component': 'App',
        'name': 'Global error dismiss button border',
        'type': 'border',
        'target': '3.0:1 non-text',
        'before': {'border_raw': '#dc2626', 'parent_raw': '#ffffff'},
        'after': {'border_token': '--color-risk-l3-border', 'parent_token': '--color-bg-surface'},
    },
    {
        'id': 'AP-6',
        'component': 'App',
        'name': 'Node simulation active button background (fill on surface)',
        'type': 'background',
        'target': 'INFO (fill underlay; boundary defined by brand-primary-fg border AP-8)',
        'before': {'bg_token': '--color-brand-primary-bg', 'parent_token': '--color-bg-surface'},
        'after': {'bg_token': '--color-brand-primary-bg', 'parent_token': '--color-bg-surface'},
    },
    {
        'id': 'AP-7',
        'component': 'App',
        'name': 'Node simulation active button text',
        'type': 'text',
        'target': '4.5:1 text',
        'before': {'fg_raw': '#ffffff', 'bg_token': '--color-brand-primary-bg'},
        'after': {'fg_token': '--color-brand-primary-fg', 'bg_token': '--color-brand-primary-bg'},
    },
    {
        'id': 'AP-8',
        'component': 'App',
        'name': 'Node simulation active button border',
        'type': 'border',
        'target': '3.0:1 non-text',
        'before': {'border_token': '--color-border-strong', 'parent_token': '--color-brand-primary-bg'},
        'after': {'border_token': '--color-brand-primary-fg', 'parent_token': '--color-brand-primary-bg'},
    },
    {
        'id': 'AP-9',
        'component': 'App',
        'name': 'Node simulation inactive button text',
        'type': 'text',
        'target': '4.5:1 text',
        'before': {'fg_token': '--color-text-secondary', 'bg_token': '--color-bg-subtle'},
        'after': {'fg_token': '--color-text-secondary', 'bg_token': '--color-bg-subtle'},
    },
    {
        'id': 'AP-10',
        'component': 'App',
        'name': 'Node simulation inactive button border',
        'type': 'border',
        'target': '3.0:1 non-text',
        'before': {'border_token': '--color-border-strong', 'parent_token': '--color-bg-surface'},
        'after': {'border_token': '--color-border-strong', 'parent_token': '--color-bg-surface'},
    },
    {
        'id': 'AP-11',
        'component': 'App',
        'name': 'Workspace error banner background (fill on canvas)',
        'type': 'background',
        'target': 'INFO (container fill; boundary defined by risk-l3-border AP-12)',
        'before': {'bg_raw': 'rgba(239, 68, 68, 0.1)', 'parent_token': '--color-bg-canvas'},
        'after': {'bg_token': '--color-risk-l3-bg', 'parent_token': '--color-bg-canvas'},
    },
    {
        'id': 'AP-12',
        'component': 'App',
        'name': 'Workspace error banner border',
        'type': 'border',
        'target': '3.0:1 non-text',
        'before': {'border_raw': '#ef4444', 'parent_token': '--color-bg-canvas'},
        'after': {'border_token': '--color-risk-l3-border', 'parent_token': '--color-bg-canvas'},
    },
    {
        'id': 'AP-13',
        'component': 'App',
        'name': 'Workspace error banner text',
        'type': 'text',
        'target': '4.5:1 text',
        'before': {'fg_raw': '#fca5a5', 'bg_raw': 'rgba(239, 68, 68, 0.1)', 'parent_token': '--color-bg-canvas'},
        'after': {'fg_token': '--color-risk-l3-text', 'bg_token': '--color-risk-l3-bg'},
    },
    {
        'id': 'AP-14',
        'component': 'App',
        'name': 'Terminal notice container background (fill on canvas)',
        'type': 'background',
        'target': 'INFO (container fill; boundary defined by border-subtle AP-15)',
        'before': {'bg_token': '--color-bg-surface', 'parent_token': '--color-bg-canvas'},
        'after': {'bg_token': '--color-bg-surface', 'parent_token': '--color-bg-canvas'},
    },
    {
        'id': 'AP-15',
        'component': 'App',
        'name': 'Terminal notice container border',
        'type': 'border',
        'target': '3.0:1 non-text',
        'before': {'border_token': '--color-border-subtle', 'parent_token': '--color-bg-canvas'},
        'after': {'border_token': '--color-border-subtle', 'parent_token': '--color-bg-canvas'},
    },
    {
        'id': 'AP-16',
        'component': 'App',
        'name': 'Terminal notice muted text',
        'type': 'text',
        'target': '4.5:1 text',
        'before': {'fg_token': '--color-text-muted', 'bg_token': '--color-bg-surface'},
        'after': {'fg_token': '--color-text-muted', 'bg_token': '--color-bg-surface'},
    },
    {
        'id': 'AP-17',
        'component': 'App',
        'name': 'Terminal notice action guidance text',
        'type': 'text',
        'target': '4.5:1 text',
        'before': {'fg_raw': '#fed7aa', 'bg_token': '--color-bg-surface'},
        'after': {'fg_token': '--color-status-degraded', 'bg_token': '--color-bg-surface'},
    },
    {
        'id': 'AP-18',
        'component': 'App',
        'name': 'Terminal run select input text',
        'type': 'text',
        'target': '4.5:1 text',
        'before': {'fg_token': '--color-text-primary', 'bg_token': '--color-bg-surface'},
        'after': {'fg_token': '--color-text-primary', 'bg_token': '--color-bg-surface'},
    },
    {
        'id': 'AP-19',
        'component': 'App',
        'name': 'Terminal run select input border',
        'type': 'border',
        'target': '3.0:1 non-text',
        'before': {'border_token': '--color-border-subtle', 'parent_token': '--color-bg-surface'},
        'after': {'border_token': '--color-border-subtle', 'parent_token': '--color-bg-surface'},
    },
    # releaseEngine.ts items
    {
        'id': 'RE-1',
        'component': 'releaseEngine',
        'name': 'WCAG 1.4.3 minimum body text contrast audit',
        'type': 'text',
        'target': '4.5:1 text',
        'before': {'fg_raw': '#c9d1d9', 'bg_raw': '#0d1117'},
        'after': {'fg_token': '--color-text-secondary', 'bg_token': '--color-bg-canvas'},
    },
    {
        'id': 'RE-2',
        'component': 'releaseEngine',
        'name': 'WCAG 1.4.11 non-text interactive boundary contrast audit',
        'type': 'border',
        'target': '3.0:1 non-text',
        'before': {'border_raw': '#6e7681', 'parent_raw': '#0d1117'},
        'after': {'border_token': '--color-border-subtle', 'parent_token': '--color-bg-canvas'},
    },
]

def resolve_color(spec: Dict[str, str], theme: str) -> str:
    tokens = TOKENS[theme]
    if 'fg_token' in spec:
        return tokens[spec['fg_token']]
    if 'bg_token' in spec:
        return tokens[spec['bg_token']]
    if 'border_token' in spec:
        return tokens[spec['border_token']]
    if 'fg_raw' in spec:
        raw = spec['fg_raw']
        if raw.startswith('rgba'):
            underlay = tokens[spec['parent_token']]
            return blend_rgba(parse_rgba(raw), underlay)
        if raw.startswith('var('):
            tok = raw.replace('var(', '').replace(')', '')
            return tokens[tok]
        return raw
    if 'bg_raw' in spec:
        raw = spec['bg_raw']
        if raw.startswith('rgba'):
            underlay = tokens[spec.get('parent_token', '--color-bg-canvas')]
            return blend_rgba(parse_rgba(raw), underlay)
        if raw.startswith('var('):
            tok = raw.replace('var(', '').replace(')', '')
            return tokens[tok]
        return raw
    if 'border_raw' in spec:
        raw = spec['border_raw']
        if raw == 'none':
            return tokens[spec['parent_token']]
        if raw.startswith('var('):
            tok = raw.replace('var(', '').replace(')', '')
            return tokens[tok]
        return raw
    if 'parent_token' in spec:
        return tokens[spec['parent_token']]
    if 'parent_raw' in spec:
        return spec['parent_raw']
    raise ValueError(f"Unknown color spec: {spec}")

def compute_contrast(item: Dict[str, Any], state: 'before' or 'after') -> (float, float):
    spec = item[state]
    item_type = item['type']

    if item_type == 'text':
        # fg vs bg
        fg_spec = {'fg_token': spec['fg_token']} if 'fg_token' in spec else {'fg_raw': spec['fg_raw']}
        if 'parent_token' in spec:
            fg_spec['parent_token'] = spec['parent_token']
        if 'bg_token' in spec:
            bg_spec = {'bg_token': spec['bg_token']}
        elif 'bg_raw' in spec:
            bg_spec = {'bg_raw': spec['bg_raw']}
            if 'parent_token' in spec:
                bg_spec['parent_token'] = spec['parent_token']
        else:
            raise ValueError(f"No bg in {spec}")
        l_fg = resolve_color(fg_spec, 'light')
        l_bg = resolve_color(bg_spec, 'light')
        d_fg = resolve_color(fg_spec, 'dark')
        d_bg = resolve_color(bg_spec, 'dark')
        return get_contrast(l_fg, l_bg), get_contrast(d_fg, d_bg)

    elif item_type == 'border':
        # border vs parent
        b_spec = {'border_token': spec['border_token']} if 'border_token' in spec else {'border_raw': spec['border_raw']}
        if 'parent_token' in spec:
            p_spec = {'parent_token': spec['parent_token']}
        elif 'parent_raw' in spec:
            p_spec = {'parent_raw': spec['parent_raw']}
        else:
            raise ValueError(f"No parent in {spec}")
        if b_spec.get('border_raw') == 'none' and 'parent_token' in spec:
            b_spec['parent_token'] = spec['parent_token']
        l_b = resolve_color(b_spec, 'light')
        l_p = resolve_color(p_spec, 'light')
        d_b = resolve_color(b_spec, 'dark')
        d_p = resolve_color(p_spec, 'dark')
        return get_contrast(l_b, l_p), get_contrast(d_b, d_p)

    elif item_type == 'background':
        # bg vs parent
        bg_spec = {'bg_token': spec['bg_token']} if 'bg_token' in spec else {'bg_raw': spec['bg_raw']}
        if 'parent_token' in spec:
            bg_spec['parent_token'] = spec['parent_token']
            p_spec = {'parent_token': spec['parent_token']}
        elif 'parent_raw' in spec:
            p_spec = {'parent_raw': spec['parent_raw']}
        else:
            raise ValueError(f"No parent in {spec}")
        l_bg = resolve_color(bg_spec, 'light')
        l_p = resolve_color(p_spec, 'light')
        d_bg = resolve_color(bg_spec, 'dark')
        d_p = resolve_color(p_spec, 'dark')
        return get_contrast(l_bg, l_p), get_contrast(d_bg, d_p)

    raise ValueError(f"Unknown type: {item_type}")

def main():
    print("=" * 80)
    print("Card 277: ACC-09 App Shell & Release Engine WCAG 2.2 AA Contrast Reproduction")
    print("=" * 80)

    verify_tokens_against_index_css()
    print("[PASS] Verified TOKENS table against apps/web/src/index.css declarations.")

    pass_count = 0
    total_count = len(AUDIT_ITEMS)

    print(f"\n{'ID':<6} | {'Target':<10} | {'Before (L/D)':<14} | {'After (L/D)':<14} | {'Status':<6} | {'Item Name'}")
    print("-" * 88)

    for item in AUDIT_ITEMS:
        item_id = item['id']
        name = item['name']
        item_type = item['type']
        target_desc = item['target']

        l_before, d_before = compute_contrast(item, 'before')
        l_after, d_after = compute_contrast(item, 'after')

        if item_type == 'text':
            min_req = 4.5
            is_pass = (l_after >= min_req and d_after >= min_req)
            status = "PASS" if is_pass else "FAIL"
            target_str = ">= 4.5:1"
        elif item_type == 'border':
            min_req = 3.0
            is_pass = (l_after >= min_req and d_after >= min_req)
            status = "PASS" if is_pass else "FAIL"
            target_str = ">= 3.0:1"
        else: # background / fill
            is_pass = True
            status = "INFO"
            target_str = "INFO"

        if is_pass:
            pass_count += 1

        before_str = f"{l_before:.2f} / {d_before:.2f}"
        after_str = f"{l_after:.2f} / {d_after:.2f}"
        print(f"{item_id:<6} | {target_str:<10} | {before_str:<14} | {after_str:<14} | {status:<6} | {name}")

    print("-" * 88)
    print(f"Total Audit Items: {total_count}, Passed / Info: {pass_count}/{total_count}")
    assert pass_count == total_count, f"Contrast audit failed: {pass_count}/{total_count} passed"
    print("ALL AUDIT ITEMS COMPLIANT WITH WCAG 2.2 AA SPECIFICATIONS.")

if __name__ == '__main__':
    main()
