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

# Backgrounds in RunList:
# Surface: Light #ffffff, Dark #111827
# Subtle: Light #f1f5f9, Dark #1f2937

dark_surf = "#111827"
dark_subt = "#1f2937"
light_subt = "#f1f5f9"
light_surf = "#ffffff"

light_canvas = light_tokens.get('--color-bg-canvas', '#f8fafc')
dark_canvas = dark_tokens.get('--color-bg-canvas', '#090d16')

stale_warn_bg_d = alpha_composite((239, 68, 68, 0.10), dark_canvas)
stale_warn_bg_l = alpha_composite((239, 68, 68, 0.10), light_canvas)

fetch_err_bg_d = alpha_composite((239, 68, 68, 0.08), dark_surf)
fetch_err_bg_l = alpha_composite((239, 68, 68, 0.08), light_surf)

shard_child_bg_d = alpha_composite((59, 130, 246, 0.10), dark_surf)
shard_child_bg_l = alpha_composite((59, 130, 246, 0.10), light_surf)

shard_parent_bg_d = alpha_composite((139, 92, 246, 0.10), dark_surf)
shard_parent_bg_l = alpha_composite((139, 92, 246, 0.10), light_surf)

release_pending_bg_d = alpha_composite((217, 119, 6, 0.15), dark_surf)
release_pending_bg_l = alpha_composite((217, 119, 6, 0.15), light_surf)

# Dynamically parse RUN_STATE_CONFIG tokens from RunList.tsx
with open('apps/web/src/features/runs/RunList.tsx', 'r', encoding='utf-8') as f:
    runlist_src = f.read()

state_tokens = {}
for m in re.finditer(r"([a-z_]+):\s*\{\s*label:\s*'[^']+',\s*color:\s*'var\((--color-[a-z0-9-]+)\)',\s*bg:\s*'var\((--color-[a-z0-9-]+)\)'", runlist_src):
    state_tokens[m.group(1)] = (m.group(2), m.group(3))

# Base RUN_STATE_CONFIG badges before (cbb6df09 / 02d5ecd4):
# rendered in table over surface (#ffffff / #111827) with base rgba alpha composition
items = [
    ("badge: draft / subtle", "#64748b", "#64748b", alpha_composite((100, 116, 139, 0.15), light_surf), alpha_composite((100, 116, 139, 0.15), dark_surf), state_tokens["draft"][0], state_tokens["draft"][1]),
    ("badge: validated / subtle", "#3b82f6", "#3b82f6", alpha_composite((59, 130, 246, 0.15), light_surf), alpha_composite((59, 130, 246, 0.15), dark_surf), state_tokens["validated"][0], state_tokens["validated"][1]),
    ("badge: planned / subtle", "#0284c7", "#0284c7", alpha_composite((2, 132, 199, 0.15), light_surf), alpha_composite((2, 132, 199, 0.15), dark_surf), state_tokens["planned"][0], state_tokens["planned"][1]),
    ("badge: awaiting_approval / subtle", "#f59e0b", "#f59e0b", alpha_composite((245, 158, 11, 0.15), light_surf), alpha_composite((245, 158, 11, 0.15), dark_surf), state_tokens["awaiting_approval"][0], state_tokens["awaiting_approval"][1]),
    ("badge: scheduled / subtle", "#8b5cf6", "#8b5cf6", alpha_composite((139, 92, 246, 0.15), light_surf), alpha_composite((139, 92, 246, 0.15), dark_surf), state_tokens["scheduled"][0], state_tokens["scheduled"][1]),
    ("badge: running / subtle", "#3b82f6", "#3b82f6", alpha_composite((59, 130, 246, 0.20), light_surf), alpha_composite((59, 130, 246, 0.20), dark_surf), state_tokens["running"][0], state_tokens["running"][1]),
    ("badge: verifying / subtle", "#06b6d4", "#06b6d4", alpha_composite((6, 182, 212, 0.15), light_surf), alpha_composite((6, 182, 212, 0.15), dark_surf), state_tokens["verifying"][0], state_tokens["verifying"][1]),
    ("badge: recovering / subtle", "#f97316", "#f97316", alpha_composite((249, 115, 22, 0.15), light_surf), alpha_composite((249, 115, 22, 0.15), dark_surf), state_tokens["recovering"][0], state_tokens["recovering"][1]),
    ("badge: succeeded / subtle", "#10b981", "#10b981", alpha_composite((16, 185, 129, 0.15), light_surf), alpha_composite((16, 185, 129, 0.15), dark_surf), state_tokens["succeeded"][0], state_tokens["succeeded"][1]),
    ("badge: failed / subtle", "#ef4444", "#ef4444", alpha_composite((239, 68, 68, 0.15), light_surf), alpha_composite((239, 68, 68, 0.15), dark_surf), state_tokens["failed"][0], state_tokens["failed"][1]),
    ("badge: cancelled / subtle", "#6b7280", "#6b7280", alpha_composite((107, 114, 128, 0.15), light_surf), alpha_composite((107, 114, 128, 0.15), dark_surf), state_tokens["cancelled"][0], state_tokens["cancelled"][1]),
    ("stale warning banner text / subtle", "#fca5a5", "#fca5a5", stale_warn_bg_l, stale_warn_bg_d, "--color-status-offline", "--color-bg-subtle"),
    ("fetch error banner title / subtle", "#fca5a5", "#fca5a5", fetch_err_bg_l, fetch_err_bg_d, "--color-status-offline", "--color-bg-subtle"),
    ("fetch error retry button / offline-bg", "#ffffff", "#ffffff", "#ef4444", "#ef4444", "--color-brand-primary-fg", "--color-status-offline-bg"),
    ("shard child badge / subtle", "#3b82f6", "#3b82f6", shard_child_bg_l, shard_child_bg_d, "--color-brand-hover", "--color-bg-subtle"),
    ("shard parent badge / subtle", "#8b5cf6", "#8b5cf6", shard_parent_bg_l, shard_parent_bg_d, "--color-status-active", "--color-bg-subtle"),
    ("release pending badge / subtle", "#d97706", "#d97706", release_pending_bg_l, release_pending_bg_d, "--color-status-degraded", "--color-bg-subtle"),
    ("run select id link / surface", "#58a6ff", "#58a6ff", light_surf, dark_surf, "--color-brand-hover", "--color-bg-surface"),
    ("state updated at text / surface", "#60a5fa", "#60a5fa", light_surf, dark_surf, "--color-brand-hover", "--color-bg-surface"),
    ("completed at (succeeded) / surface", "#10b981", "#10b981", light_surf, dark_surf, "--color-status-online", "--color-bg-surface"),
    ("completed at (failed) / surface", "#f85149", "#f85149", light_surf, dark_surf, "--color-status-offline", "--color-bg-surface"),
]

items.sort(key=lambda x: x[0])

if __name__ == '__main__':
    for label, b_fg_l, b_fg_d, b_bg_l, b_bg_d, a_fg, a_bg in items:
        b_cr_l = cr(b_fg_l, b_bg_l)
        b_cr_d = cr(b_fg_d, b_bg_d)
        a_cr_l = cr(light_tokens[a_fg], light_tokens[a_bg])
        a_cr_d = cr(dark_tokens[a_fg], dark_tokens[a_bg])
        print(f"{label:38s} | Before: {b_cr_l:5.2f}:1 (L actual on {b_bg_l}) / {b_cr_d:5.2f}:1 (D actual on {b_bg_d}) | After: {a_cr_l:5.2f}:1 (Light) / {a_cr_d:5.2f}:1 (Dark)")
