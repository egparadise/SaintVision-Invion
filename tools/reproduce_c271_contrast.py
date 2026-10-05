"""
Dynamic contrast reproduction script for Card 271: NodeList
Validates WCAG 2.2 AA contrast compliance against apps/web/src/index.css tokens.
Audit Items: 25
"""
import re
from pathlib import Path


def parse_tokens(css_text):
    root_match = re.search(r':root\s*\{([^}]+)\}', css_text)
    dark_match = re.search(r'\[data-theme=[\'"]dark[\'"]\]\s*\{([^}]+)\}', css_text)

    token_pat = re.compile(r'(--color-[a-z0-9-]+)\s*:\s*([^;]+);')

    light_tokens = dict(token_pat.findall(root_match.group(1)))
    dark_tokens = dict(token_pat.findall(dark_match.group(1)))
    return light_tokens, dark_tokens


def parse_hex(hex_str):
    hex_str = hex_str.strip().lstrip('#')
    if len(hex_str) == 3:
        hex_str = ''.join(c * 2 for c in hex_str)
    elif len(hex_str) == 8:
        hex_str = hex_str[:6]
    return [int(hex_str[i:i+2], 16) for i in (0, 2, 4)]


def get_luminance(rgb):
    def channel(c):
        c = c / 255.0
        return c / 12.92 if c <= 0.03928 else ((c + 0.055) / 1.055) ** 2.4
    r, g, b = [channel(v) for v in rgb]
    return 0.2126 * r + 0.7152 * g + 0.0722 * b


def get_contrast(rgb1, rgb2):
    l1 = get_luminance(rgb1)
    l2 = get_luminance(rgb2)
    lighter = max(l1, l2)
    darker = min(l1, l2)
    return (lighter + 0.05) / (darker + 0.05)


def main():
    css_path = Path('apps/web/src/index.css')
    if not css_path.exists():
        css_path = Path('../apps/web/src/index.css')
    css_text = css_path.read_text(encoding='utf-8')
    light, dark = parse_tokens(css_text)

    # Base backgrounds
    l_surface = parse_hex(light['--color-bg-surface'])
    d_surface = parse_hex(dark['--color-bg-surface'])
    l_subtle = parse_hex(light['--color-bg-subtle'])
    d_subtle = parse_hex(dark['--color-bg-subtle'])

    items = [
        # 1. Code block & Copy action
        ("IT01", "code-block text", 4.5, light['--color-status-online'], dark['--color-status-online'], l_subtle, d_subtle),
        ("IT02", "btn-copy text", 4.5, light['--color-text-primary'], dark['--color-text-primary'], l_subtle, d_subtle),
        ("IT03", "copy-feedback text", 4.5, light['--color-status-online'], dark['--color-status-online'], l_surface, d_surface),

        # 2. Banners & Notices
        ("IT04", "obs-banner text", 4.5, light['--color-status-unknown'], dark['--color-status-unknown'], l_subtle, d_subtle),
        ("IT05", "obs-banner border", 3.0, light['--color-status-unknown'], dark['--color-status-unknown'], l_subtle, d_subtle),
        ("IT06", "active-notice text", 4.5, light['--color-status-active'], dark['--color-status-active'], l_subtle, d_subtle),
        ("IT07", "active-notice border", 3.0, light['--color-status-active'], dark['--color-status-active'], l_subtle, d_subtle),

        # 3. Interactive Buttons
        ("IT08", "btn-studio-open text", 4.5, light['--color-brand-primary-fg'], dark['--color-brand-primary-fg'], parse_hex(light['--color-brand-primary-bg']), parse_hex(dark['--color-brand-primary-bg'])),
        ("IT09", "btn-studio-obsonly text", 4.5, light['--color-text-inverse'], dark['--color-text-inverse'], parse_hex(light['--color-border-strong']), parse_hex(dark['--color-border-strong'])),
        ("IT10", "btn-refresh text", 4.5, light['--color-text-primary'], dark['--color-text-primary'], l_subtle, d_subtle),
        ("IT11", "btn-select-all text", 4.5, light['--color-text-primary'], dark['--color-text-primary'], l_subtle, d_subtle),

        # 4. Status Badges Text (on --color-bg-subtle)
        ("IT12", "badge-online text", 4.5, light['--color-status-online'], dark['--color-status-online'], l_subtle, d_subtle),
        ("IT13", "badge-active text", 4.5, light['--color-status-active'], dark['--color-status-active'], l_subtle, d_subtle),
        ("IT14", "badge-degraded text", 4.5, light['--color-status-degraded'], dark['--color-status-degraded'], l_subtle, d_subtle),
        ("IT15", "badge-lost text", 4.5, light['--color-status-lost'], dark['--color-status-lost'], l_subtle, d_subtle),
        ("IT16", "badge-unknown text", 4.5, light['--color-status-unknown'], dark['--color-status-unknown'], l_subtle, d_subtle),

        # 5. Status Badges Border (on --color-bg-subtle)
        ("IT17", "badge-online border", 3.0, light['--color-status-online'], dark['--color-status-online'], l_subtle, d_subtle),
        ("IT18", "badge-active border", 3.0, light['--color-status-active'], dark['--color-status-active'], l_subtle, d_subtle),
        ("IT19", "badge-degraded border", 3.0, light['--color-status-degraded'], dark['--color-status-degraded'], l_subtle, d_subtle),
        ("IT20", "badge-lost border", 3.0, light['--color-status-lost'], dark['--color-status-lost'], l_subtle, d_subtle),
        ("IT21", "badge-unknown border", 3.0, light['--color-status-unknown'], dark['--color-status-unknown'], l_subtle, d_subtle),

        # 6. Header & Empty States
        ("IT22", "header-title text", 4.5, light['--color-text-primary'], dark['--color-text-primary'], l_surface, d_surface),
        ("IT23", "header-subtitle text", 4.5, light['--color-text-muted'], dark['--color-text-muted'], l_surface, d_surface),
        ("IT24", "empty-title text", 4.5, light['--color-text-primary'], dark['--color-text-primary'], l_surface, d_surface),
        ("IT25", "empty-desc text", 4.5, light['--color-text-muted'], dark['--color-text-muted'], l_surface, d_surface),
    ]

    print("=" * 100)
    print(" Card 271 NodeList Contrast Verification Report (tools/reproduce_c271_contrast.py)")
    print("=" * 100)
    print(f"{'ID':<6}| {'Element / Role':<29}| {'MinCR':<6}| {'Light CR':<11}| {'Dark CR':<11}| {'Status'}")
    print("-" * 100)

    passed_count = 0
    for item_id, label, min_cr, l_fg, d_fg, l_bg, d_bg in items:
        l_rgb = parse_hex(l_fg)
        d_rgb = parse_hex(d_fg)
        l_cr = get_contrast(l_rgb, l_bg)
        d_cr = get_contrast(d_rgb, d_bg)

        is_pass = (l_cr >= min_cr) and (d_cr >= min_cr)
        status_str = "PASS" if is_pass else "FAIL"
        if is_pass:
            passed_count += 1

        print(f"{item_id:<6}| {label:<29}| {min_cr:<6.1f}| {l_cr:<11.2f}| {d_cr:<11.2f}| {status_str}")

    print("-" * 100)
    print(f"Total Audit Items: {len(items)} | Passed: {passed_count} | Failed: {len(items) - passed_count}")
    print("=" * 100)

    if passed_count == len(items):
        print("[SUCCESS] All items strictly pass WCAG AA contrast thresholds in both Light and Dark themes.")
        return 0
    else:
        print("[FAILURE] Some items failed contrast thresholds.")
        return 1


if __name__ == '__main__':
    import sys
    sys.exit(main())
