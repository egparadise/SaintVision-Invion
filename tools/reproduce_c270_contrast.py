"""
Dynamic contrast reproduction script for Card 270: WorkspaceList
Validates WCAG 2.2 AA contrast compliance against apps/web/src/index.css tokens.
Audit Items: 24
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

    # Canvas and base ancestors
    l_canvas = parse_hex(light['--color-bg-canvas'])
    d_canvas = parse_hex(dark['--color-bg-canvas'])
    l_surface = parse_hex(light['--color-bg-surface'])
    d_surface = parse_hex(dark['--color-bg-surface'])
    l_subtle = parse_hex(light['--color-bg-subtle'])
    d_subtle = parse_hex(dark['--color-bg-subtle'])

    # Audit items
    items = [
        # 1. Status Badges (on --color-bg-subtle)
        ("IT01", "badge-ready text", 4.5, light['--color-status-online'], dark['--color-status-online'], l_subtle, d_subtle),
        ("IT02", "badge-ready border", 3.0, light['--color-status-online'], dark['--color-status-online'], l_subtle, d_subtle),
        ("IT03", "badge-provisioning text", 4.5, light['--color-status-degraded'], dark['--color-status-degraded'], l_subtle, d_subtle),
        ("IT04", "badge-provisioning border", 3.0, light['--color-status-degraded'], dark['--color-status-degraded'], l_subtle, d_subtle),
        ("IT05", "badge-suspended text", 4.5, light['--color-text-muted'], dark['--color-text-muted'], l_subtle, d_subtle),
        ("IT06", "badge-suspended border", 3.0, light['--color-border-subtle'], dark['--color-border-subtle'], l_subtle, d_subtle),
        ("IT07", "badge-deleting text", 4.5, light['--color-status-offline'], dark['--color-status-offline'], l_subtle, d_subtle),
        ("IT08", "badge-deleting border", 3.0, light['--color-status-offline'], dark['--color-status-offline'], l_subtle, d_subtle),
        ("IT09", "badge-deleted text", 4.5, light['--color-text-muted'], dark['--color-text-muted'], l_subtle, d_subtle),
        ("IT10", "badge-deleted border", 3.0, light['--color-border-subtle'], dark['--color-border-subtle'], l_subtle, d_subtle),
        ("IT11", "badge-unknown fallback text", 4.5, light['--color-status-unknown'], dark['--color-status-unknown'], l_subtle, d_subtle),
        ("IT12", "badge-unknown fallback border", 3.0, light['--color-status-unknown'], dark['--color-status-unknown'], l_subtle, d_subtle),

        # 2. Error Banner (on --color-bg-subtle)
        ("IT13", "error-banner heading", 4.5, light['--color-status-offline'], dark['--color-status-offline'], l_subtle, d_subtle),
        ("IT14", "error-banner body", 4.5, light['--color-text-primary'], dark['--color-text-primary'], l_subtle, d_subtle),
        ("IT15", "error-banner border", 3.0, light['--color-status-offline'], dark['--color-status-offline'], l_subtle, d_subtle),

        # 3. Header & Actions (header on canvas, button on brand-bg)
        ("IT16", "header-title text", 4.5, light['--color-text-primary'], dark['--color-text-primary'], l_canvas, d_canvas),
        ("IT17", "header-subtitle text", 4.5, light['--color-text-muted'], dark['--color-text-muted'], l_canvas, d_canvas),
        ("IT18", "btn-create-workspace text", 4.5, light['--color-brand-primary-fg'], dark['--color-brand-primary-fg'], parse_hex(light['--color-brand-primary-bg']), parse_hex(dark['--color-brand-primary-bg'])),

        # 4. Workspace Cards
        ("IT19", "card-border", 3.0, light['--color-border-subtle'], dark['--color-border-subtle'], l_canvas, d_canvas),
        ("IT20", "card-title text", 4.5, light['--color-text-primary'], dark['--color-text-primary'], l_surface, d_surface),
        ("IT21", "card-meta text", 4.5, light['--color-text-muted'], dark['--color-text-muted'], l_surface, d_surface),
        ("IT22", "card-studio-btn text", 4.5, light['--color-text-primary'], dark['--color-text-primary'], l_subtle, d_subtle),

        # 5. Empty State
        ("IT23", "empty-title text", 4.5, light['--color-text-primary'], dark['--color-text-primary'], l_surface, d_surface),
        ("IT24", "empty-description text", 4.5, light['--color-text-muted'], dark['--color-text-muted'], l_surface, d_surface),
    ]

    print("=" * 100)
    print(" Card 270 WorkspaceList Contrast Verification Report (tools/reproduce_c270_contrast.py)")
    print("=" * 100)
    print(f"{'ID':<6}| {'Element / Role':<29}| {'MinCR':<6}| {'Light CR':<11}| {'Dark CR':<11}| {'Status'}")
    print("-" * 100)

    passed_count = 0
    for item_id, label, min_cr, l_fg, d_fg, l_bg, d_bg in items:
        l_rgb = parse_hex(l_fg)
        d_rgb = parse_hex(d_fg)
        l_cr = get_contrast(l_rgb, l_bg)
        d_cr = get_contrast(d_rgb, d_bg)
        passed = (l_cr >= min_cr) and (d_cr >= min_cr)
        if passed:
            passed_count += 1
            status = "PASS"
        else:
            status = f"FAIL (L:{l_cr:.2f}, D:{d_cr:.2f} < {min_cr})"

        print(f"{item_id:<6}| {label:<29}| {min_cr:<6.1f}| {l_cr:<11.2f}| {d_cr:<11.2f}| {status}")

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
