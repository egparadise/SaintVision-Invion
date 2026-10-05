"""
Dynamic contrast reproduction script for Card 274: Node & Placement Detail Screens
Validates WCAG 2.2 AA contrast compliance against apps/web/src/index.css tokens.
Audit Items: 27 (NodeDetail, PlacementExplainView, ResourceTopologyGraph)
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
    l_canvas = parse_hex(light['--color-bg-canvas'])
    d_canvas = parse_hex(dark['--color-bg-canvas'])
    l_surface = parse_hex(light['--color-bg-surface'])
    d_surface = parse_hex(dark['--color-bg-surface'])
    l_subtle = parse_hex(light['--color-bg-subtle'])
    d_subtle = parse_hex(dark['--color-bg-subtle'])

    # Semantic tokens
    l_txt_pri = parse_hex(light['--color-text-primary'])
    d_txt_pri = parse_hex(dark['--color-text-primary'])
    l_txt_mut = parse_hex(light['--color-text-muted'])
    d_txt_mut = parse_hex(dark['--color-text-muted'])
    l_bdr_sub = parse_hex(light['--color-border-subtle'])
    d_bdr_sub = parse_hex(dark['--color-border-subtle'])
    l_st_onl = parse_hex(light['--color-status-online'])
    d_st_onl = parse_hex(dark['--color-status-online'])
    l_st_off = parse_hex(light['--color-status-offline'])
    d_st_off = parse_hex(dark['--color-status-offline'])
    l_st_lost = parse_hex(light['--color-status-lost'])
    d_st_lost = parse_hex(dark['--color-status-lost'])
    l_st_unk = parse_hex(light['--color-status-unknown'])
    d_st_unk = parse_hex(dark['--color-status-unknown'])

    items = [
        # NodeDetail.tsx
        {
            "id": "IT01",
            "desc": "Observation callout heading (NodeDetail.tsx:103)",
            "req": 4.5,
            "light": get_contrast(l_st_unk, l_subtle),
            "dark": get_contrast(d_st_unk, d_subtle),
        },
        {
            "id": "IT02",
            "desc": "Observation callout body text (NodeDetail.tsx:105)",
            "req": 4.5,
            "light": get_contrast(l_txt_pri, l_subtle),
            "dark": get_contrast(d_txt_pri, d_subtle),
        },
        {
            "id": "IT03",
            "desc": "Resource usage error alert text (NodeDetail.tsx:188)",
            "req": 4.5,
            "light": get_contrast(l_st_lost, l_subtle),
            "dark": get_contrast(d_st_lost, d_subtle),
        },
        {
            "id": "IT04",
            "desc": "Schedulable box status-unknown text (NodeDetail.tsx:396)",
            "req": 4.5,
            "light": get_contrast(l_st_unk, l_subtle),
            "dark": get_contrast(d_st_unk, d_subtle),
        },
        {
            "id": "IT05",
            "desc": "Schedulable box border (NodeDetail.tsx:397)",
            "req": 3.0,
            "light": get_contrast(l_st_unk, l_subtle),
            "dark": get_contrast(d_st_unk, d_subtle),
        },
        {
            "id": "IT06",
            "desc": "Timeline offline status text (NodeDetail.tsx:200)",
            "req": 4.5,
            "light": get_contrast(l_st_off, l_surface),
            "dark": get_contrast(d_st_off, d_surface),
        },
        {
            "id": "IT07",
            "desc": "Timeline unknown status text (NodeDetail.tsx:200)",
            "req": 4.5,
            "light": get_contrast(l_st_unk, l_surface),
            "dark": get_contrast(d_st_unk, d_surface),
        },

        # PlacementExplainView.tsx
        {
            "id": "IT08",
            "desc": "Simulation badge text (PlacementExplainView.tsx:35)",
            "req": 4.5,
            "light": get_contrast(l_st_unk, l_subtle),
            "dark": get_contrast(d_st_unk, d_subtle),
        },
        {
            "id": "IT09",
            "desc": "Simulation badge border (PlacementExplainView.tsx:37)",
            "req": 3.0,
            "light": get_contrast(l_st_unk, l_subtle),
            "dark": get_contrast(d_st_unk, d_subtle),
        },
        {
            "id": "IT10",
            "desc": "Winner banner border (PlacementExplainView.tsx:61)",
            "req": 3.0,
            "light": get_contrast(l_st_onl, l_subtle),
            "dark": get_contrast(d_st_onl, d_subtle),
        },
        {
            "id": "IT11",
            "desc": "Winner banner text (PlacementExplainView.tsx:59)",
            "req": 4.5,
            "light": get_contrast(l_txt_pri, l_subtle),
            "dark": get_contrast(d_txt_pri, d_subtle),
        },
        {
            "id": "IT12",
            "desc": "Passed candidate badge text (PlacementExplainView.tsx:112)",
            "req": 4.5,
            "light": get_contrast(l_st_onl, l_subtle),
            "dark": get_contrast(d_st_onl, d_subtle),
        },
        {
            "id": "IT13",
            "desc": "Passed candidate badge border (PlacementExplainView.tsx:114)",
            "req": 3.0,
            "light": get_contrast(l_st_onl, l_subtle),
            "dark": get_contrast(d_st_onl, d_subtle),
        },
        {
            "id": "IT14",
            "desc": "Rejected candidate badge text (PlacementExplainView.tsx:112)",
            "req": 4.5,
            "light": get_contrast(l_st_lost, l_subtle),
            "dark": get_contrast(d_st_lost, d_subtle),
        },
        {
            "id": "IT15",
            "desc": "Rejected candidate badge border (PlacementExplainView.tsx:114)",
            "req": 3.0,
            "light": get_contrast(l_st_lost, l_subtle),
            "dark": get_contrast(d_st_lost, d_subtle),
        },
        {
            "id": "IT16",
            "desc": "Rejection reason text (PlacementExplainView.tsx:136)",
            "req": 4.5,
            "light": get_contrast(l_st_lost, l_subtle),
            "dark": get_contrast(d_st_lost, d_subtle),
        },
        {
            "id": "IT17",
            "desc": "Winner score text (PlacementExplainView.tsx:179)",
            "req": 4.5,
            "light": get_contrast(l_st_onl, l_subtle),
            "dark": get_contrast(d_st_onl, d_subtle),
        },
        {
            "id": "IT18",
            "desc": "Candidate card border (PlacementExplainView.tsx:96)",
            "req": 3.0,
            "light": get_contrast(l_bdr_sub, l_surface),
            "dark": get_contrast(d_bdr_sub, d_surface),
        },

        # ResourceTopologyGraph.tsx
        {
            "id": "IT19",
            "desc": "Selected node card border (ResourceTopologyGraph.tsx:69)",
            "req": 3.0,
            "light": get_contrast(l_st_onl, l_surface),
            "dark": get_contrast(d_st_onl, d_surface),
        },
        {
            "id": "IT20",
            "desc": "Fenced node card border (ResourceTopologyGraph.tsx:69)",
            "req": 3.0,
            "light": get_contrast(l_st_lost, l_surface),
            "dark": get_contrast(d_st_lost, d_surface),
        },
        {
            "id": "IT21",
            "desc": "Normal node card border (ResourceTopologyGraph.tsx:69)",
            "req": 3.0,
            "light": get_contrast(l_bdr_sub, l_surface),
            "dark": get_contrast(d_bdr_sub, d_surface),
        },
        {
            "id": "IT22",
            "desc": "Selected badge text (ResourceTopologyGraph.tsx:92)",
            "req": 4.5,
            "light": get_contrast(l_st_onl, l_subtle),
            "dark": get_contrast(d_st_onl, d_subtle),
        },
        {
            "id": "IT23",
            "desc": "Selected badge border (ResourceTopologyGraph.tsx:93)",
            "req": 3.0,
            "light": get_contrast(l_st_onl, l_subtle),
            "dark": get_contrast(d_st_onl, d_subtle),
        },
        {
            "id": "IT24",
            "desc": "Fenced badge text (ResourceTopologyGraph.tsx:107)",
            "req": 4.5,
            "light": get_contrast(l_st_lost, l_subtle),
            "dark": get_contrast(d_st_lost, d_subtle),
        },
        {
            "id": "IT25",
            "desc": "Fenced badge border (ResourceTopologyGraph.tsx:108)",
            "req": 3.0,
            "light": get_contrast(l_st_lost, l_subtle),
            "dark": get_contrast(d_st_lost, d_subtle),
        },
        {
            "id": "IT26",
            "desc": "Card hostname text (ResourceTopologyGraph.tsx:80)",
            "req": 4.5,
            "light": get_contrast(l_txt_pri, l_subtle),
            "dark": get_contrast(d_txt_pri, d_subtle),
        },
        {
            "id": "IT27",
            "desc": "Card id code text (ResourceTopologyGraph.tsx:81)",
            "req": 4.5,
            "light": get_contrast(l_txt_mut, l_subtle),
            "dark": get_contrast(d_txt_mut, d_subtle),
        },
    ]

    print("=" * 115)
    print(f"{'ID':<6} {'Element / Indicator':<60} {'Req':<5} {'Light':<8} {'Dark':<8} {'Status':<6}")
    print("=" * 115)

    all_pass = True
    for it in items:
        status = "PASS" if it["light"] >= it["req"] and it["dark"] >= it["req"] else "FAIL"
        if status == "FAIL":
            all_pass = False
        print(f"{it['id']:<6} {it['desc']:<60} {it['req']:<5.1f} {it['light']:<8.2f} {it['dark']:<8.2f} {status:<6}")

    print("=" * 115)
    print(f"Overall Result: {'ALL PASS' if all_pass else 'FAIL'}")
    return 0 if all_pass else 1


if __name__ == '__main__':
    sys.exit(main())
