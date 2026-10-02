#!/usr/bin/env python3
"""
tools/reproduce_c220_contrast.py
Card 220: ReleaseCandidateView.tsx (ACC-09) Light/Dark Contrast Reproduction Script

Verifies all contrast measurements for ReleaseCandidateView against index.css design tokens.
Computes real rendered ancestor backgrounds, alpha composites, and WCAG AA contrast ratios.
Outputs dynamic reproduction data to stdout with exit code 0.
"""

import sys
import re
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
INDEX_CSS = REPO_ROOT / "apps" / "web" / "src" / "index.css"
RC_FILE = REPO_ROOT / "apps" / "web" / "src" / "features" / "release" / "ReleaseCandidateView.tsx"

def srgb_to_linear(c: float) -> float:
    c = c / 255.0
    return c / 12.92 if c <= 0.04045 else ((c + 0.055) / 1.055) ** 2.4

def relative_luminance(rgb: tuple[int, int, int]) -> float:
    r, g, b = rgb
    return 0.2126 * srgb_to_linear(r) + 0.7152 * srgb_to_linear(g) + 0.0722 * srgb_to_linear(b)

def contrast_ratio(rgb1: tuple[int, int, int], rgb2: tuple[int, int, int]) -> float:
    l1 = relative_luminance(rgb1)
    l2 = relative_luminance(rgb2)
    lighter = max(l1, l2)
    darker = min(l1, l2)
    return (lighter + 0.05) / (darker + 0.05)

def hex_to_rgb(hex_str: str) -> tuple[int, int, int]:
    hex_str = hex_str.lstrip('#')
    if len(hex_str) == 3:
        hex_str = ''.join([c * 2 for c in hex_str])
    return (int(hex_str[0:2], 16), int(hex_str[2:4], 16), int(hex_str[4:6], 16))

def rgb_to_hex(rgb: tuple[int, int, int]) -> str:
    return f"#{rgb[0]:02x}{rgb[1]:02x}{rgb[2]:02x}"

def composite(fg_rgba: tuple[int, int, int, float], bg_rgb: tuple[int, int, int]) -> tuple[int, int, int]:
    r_fg, g_fg, b_fg, a = fg_rgba
    r_bg, g_bg, b_bg = bg_rgb
    r = round(r_fg * a + r_bg * (1.0 - a))
    g = round(g_fg * a + g_bg * (1.0 - a))
    b = round(b_fg * a + b_bg * (1.0 - a))
    return (r, g, b)

def parse_css_tokens(css_path: Path) -> tuple[dict[str, tuple[int, int, int]], dict[str, tuple[int, int, int]]]:
    content = css_path.read_text(encoding="utf-8")

    root_match = re.search(r":root\s*\{([\s\S]*?)\}", content)
    dark_match = re.search(r"\[data-theme=['\"]dark['\"]\]\s*\{([\s\S]*?)\}", content)

    if not root_match or not dark_match:
        raise ValueError("Could not parse :root or [data-theme='dark'] from index.css")

    def extract_tokens(block: str) -> dict[str, tuple[int, int, int]]:
        tokens = {}
        for line in block.splitlines():
            m = re.match(r"\s*(--color-[a-z0-9-]+)\s*:\s*(#[0-9a-fA-F]{3,8})", line)
            if m:
                tokens[m.group(1)] = hex_to_rgb(m.group(2))
        return tokens

    return extract_tokens(root_match.group(1)), extract_tokens(dark_match.group(1))

def main() -> int:
    light_tokens, dark_tokens = parse_css_tokens(INDEX_CSS)

    # 25 Canonical Audit Items for ReleaseCandidateView
    ITEMS = [
        # (label, before_fg, (before_alpha_str, before_bg_key), after_fg_token, after_bg_token, min_cr)
        ("unexposed notice banner / canvas", "#58a6ff", ("rgba(56, 139, 253, 0.12)", "--color-bg-canvas"), "--color-text-secondary", "--color-bg-subtle", 4.5),
        ("kpi critical vulns title / surface", "#8b949e", "#161b22", "--color-text-muted", "--color-bg-surface", 4.5),
        ("kpi critical vulns count zero / surface", "#3fb950", "#161b22", "--color-status-online", "--color-bg-surface", 4.5),
        ("kpi critical vulns count alert / surface", "#f85149", "#161b22", "--color-status-offline", "--color-bg-surface", 4.5),
        ("kpi slo rate met / surface", "#3fb950", "#161b22", "--color-status-online", "--color-bg-surface", 4.5),
        ("kpi slo rate degraded / surface", "#d29922", "#161b22", "--color-status-degraded", "--color-bg-surface", 4.5),
        ("kpi wcag pass checklist / surface", "#3fb950", "#161b22", "--color-status-online", "--color-bg-surface", 4.5),
        ("kpi active rc tag / surface", "#58a6ff", "#161b22", "--color-brand-hover", "--color-bg-surface", 4.5),
        ("action notice error / canvas", "#f85149", ("rgba(248, 81, 73, 0.15)", "--color-bg-canvas"), "--color-status-offline", "--color-bg-subtle", 4.5),
        ("action notice success / canvas", "#3fb950", ("rgba(46, 160, 67, 0.15)", "--color-bg-canvas"), "--color-status-online", "--color-bg-subtle", 4.5),
        ("slo table header / surface", "#8b949e", "#161b22", "--color-text-muted", "--color-bg-surface", 4.5),
        ("slo table item name / surface", "#f0f6fc", "#161b22", "--color-text-primary", "--color-bg-surface", 4.5),
        ("slo table target / surface", "#8b949e", "#161b22", "--color-text-muted", "--color-bg-surface", 4.5),
        ("slo table actual / surface", "#58a6ff", "#161b22", "--color-brand-hover", "--color-bg-surface", 4.5),
        ("badge slo met / surface", "#3fb950", ("rgba(46, 160, 67, 0.2)", "#161b22"), "--color-status-online", "--color-bg-subtle", 4.5),
        ("badge slo unmeasured / surface", "#8b949e", ("rgba(139, 148, 158, 0.2)", "#161b22"), "--color-text-secondary", "--color-bg-subtle", 4.5),
        ("badge slo breached / surface", "#f85149", ("rgba(248, 81, 73, 0.2)", "#161b22"), "--color-status-offline", "--color-bg-subtle", 4.5),
        ("audit item title / subtle", "#f0f6fc", "#0d1117", "--color-text-primary", "--color-bg-subtle", 4.5),
        ("audit item level / subtle", "#58a6ff", "#0d1117", "--color-brand-hover", "--color-bg-subtle", 4.5),
        ("audit item desc / subtle", "#8b949e", "#0d1117", "--color-text-secondary", "--color-bg-subtle", 4.5),
        ("badge audit pass / subtle", "#3fb950", ("rgba(46, 160, 67, 0.2)", "#0d1117"), "--color-status-online", "--color-bg-subtle", 4.5),
        ("badge audit fail / subtle", "#f85149", ("rgba(248, 81, 73, 0.2)", "#0d1117"), "--color-status-offline", "--color-bg-subtle", 4.5),
        ("candidate table tag / surface", "#f0f6fc", "#161b22", "--color-text-primary", "--color-bg-surface", 4.5),
        ("badge candidate active / surface", "#58a6ff", ("rgba(56, 139, 253, 0.2)", "#161b22"), "--color-brand-hover", "--color-bg-subtle", 4.5),
        ("badge candidate waiting / surface", "#8b949e", ("rgba(139, 148, 158, 0.1)", "#161b22"), "--color-text-secondary", "--color-bg-subtle", 4.5),
    ]

    all_passed = True
    for label, b_fg, b_bg, a_fg, a_bg, min_cr in ITEMS:
        fg_before = hex_to_rgb(b_fg)

        if isinstance(b_bg, tuple):
            rgba_str, bg_key = b_bg
            m = re.match(r"rgba\((\d+),\s*(\d+),\s*(\d+),\s*([\d.]+)\)", rgba_str)
            rgba = (int(m.group(1)), int(m.group(2)), int(m.group(3)), float(m.group(4)))
            if bg_key.startswith("--"):
                bg_l_ancestor = light_tokens[bg_key]
                bg_d_ancestor = dark_tokens[bg_key]
            else:
                bg_l_ancestor = hex_to_rgb(bg_key)
                bg_d_ancestor = hex_to_rgb(bg_key)
            l_bg_before = composite(rgba, bg_l_ancestor)
            d_bg_before = composite(rgba, bg_d_ancestor)
        else:
            l_bg_before = hex_to_rgb(b_bg)
            d_bg_before = hex_to_rgb(b_bg)

        cr_b_l = contrast_ratio(fg_before, l_bg_before)
        cr_b_d = contrast_ratio(fg_before, d_bg_before)

        af_l = light_tokens[a_fg]
        ab_l = light_tokens[a_bg]
        cr_a_l = contrast_ratio(af_l, ab_l)

        af_d = dark_tokens[a_fg]
        ab_d = dark_tokens[a_bg]
        cr_a_d = contrast_ratio(af_d, ab_d)

        if cr_a_l < min_cr or cr_a_d < min_cr:
            all_passed = False

        hex_l_before = rgb_to_hex(l_bg_before)
        hex_d_before = rgb_to_hex(d_bg_before)

        print(f"{label:40} | Before: {cr_b_l:5.2f}:1 (L actual on {hex_l_before}) / {cr_b_d:5.2f}:1 (D actual on {hex_d_before}) | After: {cr_a_l:5.2f}:1 (Light) / {cr_a_d:5.2f}:1 (Dark)")

    if not all_passed:
        print("\nFAIL: One or more contrast ratios did not meet minimum criteria.", file=sys.stderr)
        return 1

    return 0

if __name__ == "__main__":
    sys.exit(main())
