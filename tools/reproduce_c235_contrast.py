"""
Dynamic contrast reproduction script for Card 235: PlacementSimulator
Validates WCAG 2.2 AA contrast compliance against apps/web/src/index.css tokens.
Audit Items: 35
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
        # 1. local-simulation-badge
        ('IT01', 'local-sim-badge text', 'Text', 4.5, '--color-status-degraded', 'subtle'),
        ('IT02', 'local-sim-badge border', 'Border', 3.0, '--color-status-degraded', 'subtle'),
        # 2. pools-error-banner
        ('IT03', 'pools-error title', 'Text', 4.5, '--color-status-offline', 'subtle'),
        ('IT04', 'pools-error border', 'Border', 3.0, '--color-status-offline', 'subtle'),
        ('IT05', 'pools-retry-btn text', 'Text', 4.5, '--color-text-primary', 'subtle'),
        ('IT06', 'pools-retry-btn border', 'Border', 3.0, '--color-border-subtle', 'subtle'),
        # 3. pool button selection
        ('IT07', 'pool-btn-selected text', 'Text', 4.5, '--color-brand-hover', 'brand_subtle'),
        ('IT08', 'pool-btn-selected border', 'Border', 3.0, '--color-brand-hover', 'brand_subtle'),
        ('IT09', 'pool-btn-unselected text', 'Text', 4.5, '--color-text-secondary', 'subtle'),
        ('IT10', 'pool-btn-unselected border', 'Border', 3.0, '--color-border-subtle', 'subtle'),
        # 4. pool-capacity-error
        ('IT11', 'pool-capacity-error text', 'Text', 4.5, '--color-status-offline', 'subtle'),
        ('IT12', 'pool-capacity-error border', 'Border', 3.0, '--color-status-offline', 'subtle'),
        # 5. idle unverified badges
        ('IT13', 'pools-idle-unverified text', 'Text', 4.5, '--color-status-degraded', 'subtle'),
        ('IT14', 'pools-fallback-unverified text', 'Text', 4.5, '--color-status-degraded', 'subtle'),
        # 6. GPU toggle button
        ('IT15', 'gpu-btn-active text', 'Text', 4.5, '--color-brand-hover', 'brand_subtle'),
        ('IT16', 'gpu-btn-active border', 'Border', 3.0, '--color-brand-hover', 'brand_subtle'),
        ('IT17', 'gpu-btn-inactive text', 'Text', 4.5, '--color-text-secondary', 'subtle'),
        ('IT18', 'gpu-btn-inactive border', 'Border', 3.0, '--color-border-subtle', 'subtle'),
        # 7. server explanation
        ('IT19', 'server-explanation text', 'Text', 4.5, '--color-text-primary', 'subtle'),
        ('IT20', 'server-explanation border', 'Border', 3.0, '--color-status-online', 'subtle'),
        # 8. preview loading & error
        ('IT21', 'preview-loading text', 'Text', 4.5, '--color-text-muted', 'surface'),
        ('IT22', 'preview-error text', 'Text', 4.5, '--color-status-offline', 'subtle'),
        ('IT23', 'preview-error subtext', 'Text', 4.5, '--color-status-offline', 'subtle'),
        ('IT24', 'preview-error border', 'Border', 3.0, '--color-status-offline', 'subtle'),
        ('IT25', 'preview-retry-btn text', 'Text', 4.5, '--color-text-primary', 'subtle'),
        ('IT26', 'preview-retry-btn border', 'Border', 3.0, '--color-border-subtle', 'subtle'),
        # 9. candidates loading, error, empty note
        ('IT27', 'candidates-loading text', 'Text', 4.5, '--color-text-muted', 'surface'),
        ('IT28', 'candidates-error text', 'Text', 4.5, '--color-status-offline', 'subtle'),
        ('IT29', 'candidates-error border', 'Border', 3.0, '--color-status-offline', 'subtle'),
        ('IT30', 'candidates-retry-btn text', 'Text', 4.5, '--color-text-primary', 'subtle'),
        ('IT31', 'candidates-retry-btn border', 'Border', 3.0, '--color-border-subtle', 'subtle'),
        ('IT32', 'candidates-empty note', 'Text', 4.5, '--color-brand-hover', 'surface'),
        # 10. candidate status badges (candidate & unknown fallback)
        ('IT33', 'candidate-status text', 'Text', 4.5, '--color-status-degraded', 'subtle'),
        ('IT34', 'candidate-status border', 'Border', 3.0, '--color-status-degraded', 'subtle'),
        ('IT35', 'candidate-unknown text', 'Text', 4.5, '--color-status-unknown', 'subtle'),
    ]

    print("====================================================================================================")
    print(" Card 235 PlacementSimulator Contrast Verification Report (tools/reproduce_c235_contrast.py)")
    print("====================================================================================================")
    print(f"{'ID':<5} | {'Element / Role':<28} | {'MinCR':<5} | {'Light CR':<10} | {'Dark CR':<10} | {'Status':<6}")
    print("----------------------------------------------------------------------------------------------------")

    bg_map_l = {'subtle': l_subtle, 'surface': l_surface, 'canvas': l_canvas, 'brand_subtle': l_brand_subtle}
    bg_map_d = {'subtle': d_subtle, 'surface': d_surface, 'canvas': d_canvas, 'brand_subtle': d_brand_subtle}

    passed_count = 0
    for it in items:
        iid, name, kind, min_cr, token, bg_key = it
        l_bg = bg_map_l[bg_key]
        d_bg = bg_map_d[bg_key]
        l_fg = parse_hex(light[token])
        d_fg = parse_hex(dark[token])

        cr_l = get_contrast(l_fg, l_bg)
        cr_d = get_contrast(d_fg, d_bg)

        ok = (cr_l >= min_cr) and (cr_d >= min_cr)
        status_str = "PASS" if ok else "FAIL"
        if ok:
            passed_count += 1

        print(f"{iid:<5} | {name:<28} | {min_cr:<5.1f} | {cr_l:<10.2f} | {cr_d:<10.2f} | {status_str:<6}")

    print("----------------------------------------------------------------------------------------------------")
    print(f"Total Audit Items: {len(items)} | Passed: {passed_count} | Failed: {len(items) - passed_count}")
    print("====================================================================================================")

    if passed_count != len(items):
        exit(1)
    exit(0)

if __name__ == '__main__':
    main()
