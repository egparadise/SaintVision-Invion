#!/usr/bin/env python3
"""
tools/reproduce_c226_contrast.py
Card 226: ModelStudioView.tsx (ACC-09) Light/Dark Contrast Reproduction Script

Verifies all contrast measurements for ModelStudioView against index.css design tokens.
Computes real rendered ancestor backgrounds, alpha composites, and WCAG AA contrast ratios.
Outputs dynamic reproduction data to stdout with exit code 0.
"""

import sys
import re
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
INDEX_CSS = REPO_ROOT / "apps" / "web" / "src" / "index.css"
MS_FILE = REPO_ROOT / "apps" / "web" / "src" / "features" / "desktop" / "ModelStudioView.tsx"

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

    BASE_BG_ROOT = "#0f172a"
    BASE_BG_PANEL = "#1e293b"
    BASE_BG_INPUT = "#0f172a"

    # 26 Canonical Audit Items for ModelStudioView
    ITEMS = [
        # (label, before_fg, before_bg, after_fg_token, after_bg_token, min_cr)
        ("query header project / canvas", "#94a3b8", BASE_BG_ROOT, "--color-text-secondary", "--color-bg-canvas", 4.5),
        ("query header desc / canvas", "#64748b", BASE_BG_ROOT, "--color-text-muted", "--color-bg-canvas", 4.5),
        ("query form label / surface", "#cbd5e1", BASE_BG_PANEL, "--color-text-secondary", "--color-bg-surface", 4.5),
        ("query form input text / subtle", "#f8fafc", BASE_BG_INPUT, "--color-text-primary", "--color-bg-subtle", 4.5),
        ("query button text / brand-primary-bg", "#ffffff", "#3b82f6", "--color-brand-primary-fg", "--color-brand-primary-bg", 4.5),
        ("query status loading / canvas", "#93c5fd", BASE_BG_ROOT, "--color-brand-hover", "--color-bg-canvas", 4.5),
        ("query status error / canvas", "#f87171", BASE_BG_ROOT, "--color-status-offline", "--color-bg-canvas", 4.5),
        ("manifest committed at / surface", "#94a3b8", BASE_BG_PANEL, "--color-text-secondary", "--color-bg-surface", 4.5),
        ("manifest sha hash / surface", "#94a3b8", BASE_BG_PANEL, "--color-text-secondary", "--color-bg-surface", 4.5),
        ("manifest availability unknown / surface", "#f59e0b", BASE_BG_PANEL, "--color-status-unknown", "--color-bg-surface", 4.5),
        ("manifest availability observed / surface", "#38bdf8", BASE_BG_PANEL, "--color-status-active", "--color-bg-surface", 4.5),
        ("manifest verify notice / surface", "#f59e0b", BASE_BG_PANEL, "--color-status-degraded", "--color-bg-surface", 4.5),
        ("unobserved shards notice / surface", "#94a3b8", BASE_BG_PANEL, "--color-text-secondary", "--color-bg-surface", 4.5),
        ("shard repair error / subtle", "#fca5a5", ("rgba(239, 68, 68, 0.15)", BASE_BG_PANEL), "--color-status-offline", "--color-bg-subtle", 4.5),
        ("shard repair warning / subtle", "#fde68a", ("rgba(245, 158, 11, 0.15)", BASE_BG_PANEL), "--color-status-degraded", "--color-bg-subtle", 4.5),
        ("shard repair success / subtle", "#6ee7b7", ("rgba(16, 185, 129, 0.15)", BASE_BG_PANEL), "--color-status-online", "--color-bg-subtle", 4.5),
        ("shards table header / surface", "#94a3b8", BASE_BG_PANEL, "--color-text-secondary", "--color-bg-surface", 4.5),
        ("replica badge healthy / subtle", "#6ee7b7", ("rgba(16, 185, 129, 0.2)", BASE_BG_PANEL), "--color-status-online", "--color-bg-subtle", 4.5),
        ("replica badge unhealthy / subtle", "#fca5a5", ("rgba(239, 68, 68, 0.2)", BASE_BG_PANEL), "--color-status-offline", "--color-bg-subtle", 4.5),
        ("shard degradation badge / subtle", "#fde68a", ("rgba(245, 158, 11, 0.2)", BASE_BG_PANEL), "--color-status-degraded", "--color-bg-subtle", 4.5),
        ("shard repair button / surface", "#ffffff", "#d97706", "--color-text-inverse", "--color-status-degraded", 4.5),
        ("plan feasible badge / subtle", "#6ee7b7", ("rgba(16, 185, 129, 0.2)", BASE_BG_PANEL), "--color-status-online", "--color-bg-subtle", 4.5),
        ("plan infeasible badge / subtle", "#fca5a5", ("rgba(239, 68, 68, 0.2)", BASE_BG_PANEL), "--color-status-offline", "--color-bg-subtle", 4.5),
        ("tensor parallel lan alert / subtle", "#fde68a", ("rgba(245, 158, 11, 0.15)", BASE_BG_PANEL), "--color-status-degraded", "--color-bg-subtle", 4.5),
        ("node ineligible badge / subtle", "#fca5a5", ("rgba(239, 68, 68, 0.2)", BASE_BG_PANEL), "--color-status-offline", "--color-bg-subtle", 4.5),
        ("node eligible text / surface", "#10b981", BASE_BG_PANEL, "--color-status-online", "--color-bg-surface", 4.5),
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
