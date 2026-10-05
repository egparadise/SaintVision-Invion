#!/usr/bin/env python3
"""
Dynamic contrast reproduction script for Card 275: EvidenceViewer Screen
Validates WCAG 2.2 AA contrast compliance against apps/web/src/index.css tokens.
Audit Items: 21 (EvidenceViewer tokens, badges, banners, fallbacks)
"""
import re
import sys
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


def srgb_to_linear(val):
    c = val / 255.0
    return c / 12.92 if c <= 0.04045 else ((c + 0.055) / 1.055) ** 2.4


def get_luminance(rgb):
    r, g, b = [srgb_to_linear(v) for v in rgb]
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
    l_canvas = parse_hex(light['--color-bg-canvas'])
    d_canvas = parse_hex(dark['--color-bg-canvas'])
    l_surface = parse_hex(light['--color-bg-surface'])
    d_surface = parse_hex(dark['--color-bg-surface'])
    l_subtle = parse_hex(light['--color-bg-subtle'])
    d_subtle = parse_hex(dark['--color-bg-subtle'])

    # Semantic tokens
    l_brand_pri = parse_hex(light['--color-brand-primary'])
    d_brand_pri = parse_hex(dark['--color-brand-primary'])
    l_brand_suc = parse_hex(light['--color-brand-success'])
    d_brand_suc = parse_hex(dark['--color-brand-success'])
    l_brand_dan = parse_hex(light['--color-brand-danger'])
    d_brand_dan = parse_hex(dark['--color-brand-danger'])
    l_st_unk = parse_hex(light['--color-status-unknown'])
    d_st_unk = parse_hex(dark['--color-status-unknown'])
    l_risk_l3_bg = parse_hex(light['--color-risk-l3-bg'])
    d_risk_l3_bg = parse_hex(dark['--color-risk-l3-bg'])
    l_risk_l3_bdr = parse_hex(light['--color-risk-l3-border'])
    d_risk_l3_bdr = parse_hex(dark['--color-risk-l3-border'])
    l_risk_l3_txt = parse_hex(light['--color-risk-l3-text'])
    d_risk_l3_txt = parse_hex(dark['--color-risk-l3-text'])

    items = [
        # Error Alert Banner (L183-198)
        {
            "id": "IT01",
            "desc": "Error alert banner border on canvas (L191)",
            "req": 3.0,
            "light": get_contrast(l_risk_l3_bdr, l_canvas),
            "dark": get_contrast(d_risk_l3_bdr, d_canvas),
        },
        {
            "id": "IT02",
            "desc": "Error alert banner text on risk-l3-bg (L193)",
            "req": 4.5,
            "light": get_contrast(l_risk_l3_txt, l_risk_l3_bg),
            "dark": get_contrast(d_risk_l3_txt, d_risk_l3_bg),
        },

        # PASS Dynamic Status Badge (L226-253)
        {
            "id": "IT03",
            "desc": "PASS status badge border on card surface (L247)",
            "req": 3.0,
            "light": get_contrast(l_brand_suc, l_surface),
            "dark": get_contrast(d_brand_suc, d_surface),
        },
        {
            "id": "IT04",
            "desc": "PASS status badge text on subtle (L246)",
            "req": 4.5,
            "light": get_contrast(l_brand_suc, l_subtle),
            "dark": get_contrast(d_brand_suc, d_subtle),
        },

        # FAIL Dynamic Status Badge (L226-253)
        {
            "id": "IT05",
            "desc": "FAIL status badge border on card surface (L247)",
            "req": 3.0,
            "light": get_contrast(l_brand_dan, l_surface),
            "dark": get_contrast(d_brand_dan, d_surface),
        },
        {
            "id": "IT06",
            "desc": "FAIL status badge text on subtle (L246)",
            "req": 4.5,
            "light": get_contrast(l_brand_dan, l_subtle),
            "dark": get_contrast(d_brand_dan, d_subtle),
        },

        # RUN_FAILED Dynamic Status Badge (L226-253)
        {
            "id": "IT07",
            "desc": "RUN_FAILED status badge border on card surface (L247)",
            "req": 3.0,
            "light": get_contrast(l_brand_dan, l_surface),
            "dark": get_contrast(d_brand_dan, d_surface),
        },
        {
            "id": "IT08",
            "desc": "RUN_FAILED status badge text on subtle (L246)",
            "req": 4.5,
            "light": get_contrast(l_brand_dan, l_subtle),
            "dark": get_contrast(d_brand_dan, d_subtle),
        },

        # UNVERIFIED Dynamic Status Badge (L226-253)
        {
            "id": "IT09",
            "desc": "UNVERIFIED status badge border on card surface (L247)",
            "req": 3.0,
            "light": get_contrast(l_st_unk, l_surface),
            "dark": get_contrast(d_st_unk, d_surface),
        },
        {
            "id": "IT10",
            "desc": "UNVERIFIED status badge text on subtle (L246)",
            "req": 4.5,
            "light": get_contrast(l_st_unk, l_subtle),
            "dark": get_contrast(d_st_unk, d_subtle),
        },

        # SEALED Status Badge (L254-269)
        {
            "id": "IT11",
            "desc": "SEALED status badge border on card surface (L264)",
            "req": 3.0,
            "light": get_contrast(l_brand_pri, l_surface),
            "dark": get_contrast(d_brand_pri, d_surface),
        },
        {
            "id": "IT12",
            "desc": "SEALED status badge text on subtle (L263)",
            "req": 4.5,
            "light": get_contrast(l_brand_pri, l_subtle),
            "dark": get_contrast(d_brand_pri, d_subtle),
        },

        # Copy Success Indicator (L274)
        {
            "id": "IT13",
            "desc": "Copy success message text on card surface (L274)",
            "req": 4.5,
            "light": get_contrast(l_brand_suc, l_surface),
            "dark": get_contrast(d_brand_suc, d_surface),
        },

        # RUN_FAILED Notice Banner (L295-317)
        {
            "id": "IT14",
            "desc": "RUN_FAILED notice banner border on card surface (L303)",
            "req": 3.0,
            "light": get_contrast(l_risk_l3_bdr, l_surface),
            "dark": get_contrast(d_risk_l3_bdr, d_surface),
        },
        {
            "id": "IT15",
            "desc": "RUN_FAILED notice banner text on risk-l3-bg (L305)",
            "req": 4.5,
            "light": get_contrast(l_risk_l3_txt, l_risk_l3_bg),
            "dark": get_contrast(d_risk_l3_txt, d_risk_l3_bg),
        },

        # FAIL Notice Banner (L321-343)
        {
            "id": "IT16",
            "desc": "FAIL notice banner border on card surface (L329)",
            "req": 3.0,
            "light": get_contrast(l_risk_l3_bdr, l_surface),
            "dark": get_contrast(d_risk_l3_bdr, d_surface),
        },
        {
            "id": "IT17",
            "desc": "FAIL notice banner text on risk-l3-bg (L331)",
            "req": 4.5,
            "light": get_contrast(l_risk_l3_txt, l_risk_l3_bg),
            "dark": get_contrast(d_risk_l3_txt, d_risk_l3_bg),
        },

        # UNVERIFIED Notice Banner (L347-368)
        {
            "id": "IT18",
            "desc": "UNVERIFIED notice banner border on card surface (L354)",
            "req": 3.0,
            "light": get_contrast(l_st_unk, l_surface),
            "dark": get_contrast(d_st_unk, d_surface),
        },
        {
            "id": "IT19",
            "desc": "UNVERIFIED notice banner text on subtle (L356)",
            "req": 4.5,
            "light": get_contrast(l_st_unk, l_subtle),
            "dark": get_contrast(d_st_unk, d_subtle),
        },

        # UNKNOWN Fallback Badge
        {
            "id": "IT20",
            "desc": "UNKNOWN fallback badge border on card surface",
            "req": 3.0,
            "light": get_contrast(l_st_unk, l_surface),
            "dark": get_contrast(d_st_unk, d_surface),
        },
        {
            "id": "IT21",
            "desc": "UNKNOWN fallback badge text on subtle",
            "req": 4.5,
            "light": get_contrast(l_st_unk, l_subtle),
            "dark": get_contrast(d_st_unk, d_subtle),
        },
    ]

    print("================================================================================")
    print("Card 275 Contrast Reproduction Suite: EvidenceViewer Screen")
    print("================================================================================")
    print(f"{'ID':<6} {'Description':<52} {'Req':<6} {'Light':<8} {'Dark':<8} {'Status':<6}")
    print("-" * 88)

    all_passed = True
    for item in items:
        light_pass = item["light"] >= item["req"]
        dark_pass = item["dark"] >= item["req"]
        passed = light_pass and dark_pass
        if not passed:
            all_passed = False
        status_str = "PASS" if passed else "FAIL"
        print(f"{item['id']:<6} {item['desc']:<52} {item['req']:<6.1f} {item['light']:<8.2f} {item['dark']:<8.2f} {status_str:<6}")

    print("=" * 88)
    if all_passed:
        print(f"All {len(items)} audit items meet WCAG 2.2 AA contrast standards in both themes!")
        return 0
    else:
        print("Some audit items failed contrast requirements!")
        return 1


if __name__ == "__main__":
    sys.exit(main())
