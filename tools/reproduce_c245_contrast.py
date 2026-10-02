"""
Dynamic contrast reproduction script for Card 245: ApprovalCenter
Validates WCAG 2.2 AA contrast compliance against apps/web/src/index.css tokens.
Audit Items: 31
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
    l_brand_subtle = parse_hex(light['--color-brand-subtle'])
    d_brand_subtle = parse_hex(dark['--color-brand-subtle'])

    # Audit items
    items = [
        # 1. Freshness indicator
        ("IT01", "freshness-badge text", 4.5, light['--color-brand-hover'], dark['--color-brand-hover'], l_brand_subtle, d_brand_subtle),
        ("IT02", "freshness-badge border", 3.0, light['--color-brand-hover'], dark['--color-brand-hover'], l_brand_subtle, d_brand_subtle),

        # 2. Topbar refresh button
        ("IT03", "refresh-btn text", 4.5, light['--color-text-primary'], dark['--color-text-primary'], l_subtle, d_subtle),
        ("IT04", "refresh-btn border", 3.0, light['--color-border-subtle'], dark['--color-border-subtle'], l_subtle, d_subtle),

        # 3. Stale warning banner
        ("IT05", "stale-warning text", 4.5, light['--color-status-offline'], dark['--color-status-offline'], l_subtle, d_subtle),
        ("IT06", "stale-warning subtext", 4.5, light['--color-status-offline'], dark['--color-status-offline'], l_subtle, d_subtle),
        ("IT07", "stale-warning border", 3.0, light['--color-status-offline'], dark['--color-status-offline'], l_subtle, d_subtle),

        # 4. Metrics cards
        ("IT08", "metric-pending text", 4.5, light['--color-status-degraded'], dark['--color-status-degraded'], l_surface, d_surface),
        ("IT09", "metric-approved text", 4.5, light['--color-status-online'], dark['--color-status-online'], l_surface, d_surface),
        ("IT10", "metric-rejected text", 4.5, light['--color-status-offline'], dark['--color-status-offline'], l_surface, d_surface),

        # 5. Fetch error state
        ("IT11", "error-state-title", 4.5, light['--color-status-offline'], dark['--color-status-offline'], l_surface, d_surface),
        ("IT12", "error-state-border", 3.0, light['--color-status-offline'], dark['--color-status-offline'], l_surface, d_surface),
        ("IT13", "error-retry-btn text", 4.5, light['--color-text-primary'], dark['--color-text-primary'], l_subtle, d_subtle),
        ("IT14", "error-retry-btn border", 3.0, light['--color-border-subtle'], dark['--color-border-subtle'], l_subtle, d_subtle),

        # 6. Card selected indicator
        ("IT15", "card-selected-border", 3.0, light['--color-brand-primary'], dark['--color-brand-primary'], l_subtle, d_subtle),

        # 7. Status badge PENDING
        ("IT16", "status-badge-pending text", 4.5, light['--color-status-degraded'], dark['--color-status-degraded'], l_subtle, d_subtle),
        ("IT17", "status-badge-pending border", 3.0, light['--color-status-degraded'], dark['--color-status-degraded'], l_subtle, d_subtle),

        # 8. Status badge APPROVED
        ("IT18", "status-badge-approved text", 4.5, light['--color-status-online'], dark['--color-status-online'], l_subtle, d_subtle),
        ("IT19", "status-badge-approved border", 3.0, light['--color-status-online'], dark['--color-status-online'], l_subtle, d_subtle),

        # 9. Status badge REJECTED
        ("IT20", "status-badge-rejected text", 4.5, light['--color-status-offline'], dark['--color-status-offline'], l_subtle, d_subtle),
        ("IT21", "status-badge-rejected border", 3.0, light['--color-status-offline'], dark['--color-status-offline'], l_subtle, d_subtle),

        # 10. Status badge EXPIRED
        ("IT22", "status-badge-expired text", 4.5, light['--color-status-offline'], dark['--color-status-offline'], l_subtle, d_subtle),
        ("IT23", "status-badge-expired border", 3.0, light['--color-status-offline'], dark['--color-status-offline'], l_subtle, d_subtle),

        # 11. Status badge DISPATCHED
        ("IT24", "status-badge-dispatched text", 4.5, light['--color-brand-hover'], dark['--color-brand-hover'], l_subtle, d_subtle),
        ("IT25", "status-badge-dispatched border", 3.0, light['--color-brand-hover'], dark['--color-brand-hover'], l_subtle, d_subtle),

        # 12. Status badge UNKNOWN
        ("IT26", "status-badge-unknown text", 4.5, light['--color-status-unknown'], dark['--color-status-unknown'], l_subtle, d_subtle),
        ("IT27", "status-badge-unknown border", 3.0, light['--color-status-unknown'], dark['--color-status-unknown'], l_subtle, d_subtle),

        # 13. Two-person progression badge
        ("IT28", "two-person-progress text", 4.5, light['--color-brand-hover'], dark['--color-brand-hover'], l_subtle, d_subtle),
        ("IT29", "two-person-progress border", 3.0, light['--color-brand-hover'], dark['--color-brand-hover'], l_subtle, d_subtle),
        ("IT30", "two-person-required text", 4.5, light['--color-text-secondary'], dark['--color-text-secondary'], l_subtle, d_subtle),
        ("IT31", "two-person-required border", 3.0, light['--color-border-subtle'], dark['--color-border-subtle'], l_subtle, d_subtle),
    ]

    print("=" * 100)
    print(" Card 245 ApprovalCenter Contrast Verification Report (tools/reproduce_c245_contrast.py)")
    print("=" * 100)
    print(f"{'ID':<5} | {'Element / Role':<28} | {'MinCR':<5} | {'Light CR':<10} | {'Dark CR':<10} | {'Status'}")
    print("-" * 100)

    all_passed = True
    passed_count = 0
    for item_id, name, min_cr, l_fg_token, d_fg_token, l_bg, d_bg in items:
        l_fg = parse_hex(l_fg_token)
        d_fg = parse_hex(d_fg_token)
        l_cr = get_contrast(l_fg, l_bg)
        d_cr = get_contrast(d_fg, d_bg)

        ok = l_cr >= min_cr and d_cr >= min_cr
        status = "PASS" if ok else "FAIL"
        if ok:
            passed_count += 1
        else:
            all_passed = False

        print(f"{item_id:<5} | {name:<28} | {min_cr:<5.1f} | {l_cr:<10.2f} | {d_cr:<10.2f} | {status}")

    print("-" * 100)
    print(f"Total Audit Items: {len(items)} | Passed: {passed_count} | Failed: {len(items) - passed_count}")
    print("=" * 100)
    if all_passed:
        print("[SUCCESS] All 31 items strictly pass WCAG AA contrast thresholds in both Light and Dark themes.")
    else:
        print("[FAILURE] Some items failed contrast thresholds.")
        exit(1)

if __name__ == '__main__':
    main()
