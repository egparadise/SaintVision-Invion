import re
import math

with open('apps/web/src/index.css', 'r', encoding='utf-8') as f:
    css = f.read()

def parse_tokens(block):
    clean = re.sub(r'/\*[\s\S]*?\*/', '', block)
    tokens = {}
    for m in re.finditer(r'(--color-[a-z0-9-]+)\s*:\s*([^;]+);', clean):
        tokens[m.group(1).strip()] = m.group(2).strip()
    return tokens

light_tokens = parse_tokens(re.search(r':root\s*\{([\s\S]*?)\}', css).group(1))
dark_tokens = parse_tokens(re.search(r"\[data-theme=['\"]?dark['\"]?\]\s*\{([\s\S]*?)\}", css).group(1))

def hex_to_rgb(h):
    return [int(h.lstrip('#')[i:i+2], 16) for i in (0, 2, 4)]

def rgb_to_hex(r, g, b):
    return f"#{int(round(r)):02x}{int(round(g)):02x}{int(round(b)):02x}"

def alpha_composite(fg_rgba, bg_hex):
    bg_rgb = hex_to_rgb(bg_hex)
    a = fg_rgba[3]
    r = fg_rgba[0] * a + bg_rgb[0] * (1 - a)
    g = fg_rgba[1] * a + bg_rgb[1] * (1 - a)
    b = fg_rgba[2] * a + bg_rgb[2] * (1 - a)
    return rgb_to_hex(r, g, b)

def lum(h):
    rgb = hex_to_rgb(h)
    def adj(c):
        v = c / 255.0
        return v / 12.92 if v <= 0.03928 else math.pow((v + 0.055) / 1.055, 2.4)
    return 0.2126 * adj(rgb[0]) + 0.7152 * adj(rgb[1]) + 0.0722 * adj(rgb[2])

def cr(c1, c2):
    l1, l2 = lum(c1), lum(c2)
    return (max(l1, l2) + 0.05) / (min(l1, l2) + 0.05)

# Backgrounds in DistributedRecoveryView:
# Canvas: Light #f8fafc, Dark #090d16
# Surface: Light #ffffff, Dark #111827 (originally var(--color-bg-surface, #161b22))
# Card/Panel: Hardcoded #161b22 in both light and dark in base 3ebfb1b8
# Items: Hardcoded #0d1117 in both light and dark in base 3ebfb1b8

dark_canvas = "#090d16"
light_canvas = "#f8fafc"
dark_surface = "#111827"
light_surface = "#ffffff"
base_card_bg = "#161b22"
base_item_bg = "#0d1117"

# 21 items corresponding to all key UI elements with actual base 3ebfb1b8 renders
items = [
    ("unexposed notice banner / canvas", "#58a6ff", "#58a6ff", alpha_composite((56, 139, 253, 0.10), light_canvas), alpha_composite((56, 139, 253, 0.10), dark_canvas), "--color-brand-hover", "--color-bg-subtle"),
    ("kpi detection title / surface", "#8b949e", "#8b949e", light_surface, dark_surface, "--color-text-secondary", "--color-bg-surface"),
    ("kpi zombie write count / surface", "#3fb950", "#3fb950", light_surface, dark_surface, "--color-status-online", "--color-bg-surface"),
    ("kpi recovery rate text / surface", "#58a6ff", "#58a6ff", light_surface, dark_surface, "--color-brand-hover", "--color-bg-surface"),
    ("action notice error / canvas", "#f85149", "#f85149", alpha_composite((248, 81, 73, 0.15), light_canvas), alpha_composite((248, 81, 73, 0.15), dark_canvas), "--color-status-offline", "--color-bg-subtle"),
    ("action notice success / canvas", "#3fb950", "#3fb950", alpha_composite((46, 160, 67, 0.15), light_canvas), alpha_composite((46, 160, 67, 0.15), dark_canvas), "--color-status-online", "--color-bg-subtle"),
    ("action notice info / canvas", "#58a6ff", "#58a6ff", alpha_composite((56, 139, 253, 0.15), light_canvas), alpha_composite((56, 139, 253, 0.15), dark_canvas), "--color-brand-hover", "--color-bg-subtle"),
    ("empty screen title / surface", "#f0f6fc", "#f0f6fc", light_surface, dark_surface, "--color-text-primary", "--color-bg-surface"),
    ("node card title / surface", "#f0f6fc", "#f0f6fc", base_card_bg, base_card_bg, "--color-text-primary", "--color-bg-surface"),
    ("node actual status badge / card", "#8b949e", "#8b949e", "#21262d", "#21262d", "--color-text-secondary", "--color-bg-subtle"),
    ("badge: online / card", "#3fb950", "#3fb950", alpha_composite((63, 185, 80, 34/255), base_card_bg), alpha_composite((63, 185, 80, 34/255), base_card_bg), "--color-status-online", "--color-bg-subtle"),
    ("badge: stale / card", "#e3b341", "#e3b341", alpha_composite((227, 179, 65, 34/255), base_card_bg), alpha_composite((227, 179, 65, 34/255), base_card_bg), "--color-status-degraded", "--color-bg-subtle"),
    ("badge: offline / card", "#f85149", "#f85149", alpha_composite((248, 81, 73, 34/255), base_card_bg), alpha_composite((248, 81, 73, 34/255), base_card_bg), "--color-status-offline", "--color-bg-subtle"),
    ("badge: recovering / card", "#58a6ff", "#58a6ff", alpha_composite((88, 166, 255, 34/255), base_card_bg), alpha_composite((88, 166, 255, 34/255), base_card_bg), "--color-status-active", "--color-bg-subtle"),
    ("badge: fenced / card", "#a371f7", "#a371f7", alpha_composite((163, 113, 247, 34/255), base_card_bg), alpha_composite((163, 113, 247, 34/255), base_card_bg), "--color-status-neutral", "--color-bg-subtle"),
    ("target action node name / surface", "#58a6ff", "#58a6ff", base_card_bg, base_card_bg, "--color-brand-hover", "--color-bg-surface"),
    ("checkout item id link / subtle", "#58a6ff", "#58a6ff", base_item_bg, base_item_bg, "--color-brand-hover", "--color-bg-subtle"),
    ("checkout item active badge / subtle", "#3fb950", "#3fb950", base_item_bg, base_item_bg, "--color-status-online", "--color-bg-subtle"),
    ("rejection item blocked text / subtle", "#f85149", "#f85149", base_item_bg, base_item_bg, "--color-status-offline", "--color-bg-subtle"),
    ("reconciliation item success / subtle", "#3fb950", "#3fb950", base_item_bg, base_item_bg, "--color-status-online", "--color-bg-subtle"),
    ("reconciliation item failure / subtle", "#f85149", "#f85149", base_item_bg, base_item_bg, "--color-status-offline", "--color-bg-subtle"),
]

for name, b_fg_l, b_fg_d, b_bg_l, b_bg_d, a_fg, a_bg in items:
    b_l = cr(b_fg_l, b_bg_l)
    b_d = cr(b_fg_d, b_bg_d)
    a_l = cr(light_tokens[a_fg], light_tokens[a_bg])
    a_d = cr(dark_tokens[a_fg], dark_tokens[a_bg])
    print(f"{name:37s} | Before: {b_l:5.2f}:1 (L actual on {b_bg_l}) / {b_d:5.2f}:1 (D actual on {b_bg_d}) | After: {a_l:5.2f}:1 (Light) / {a_d:5.2f}:1 (Dark)")
