"""
Dynamic contrast reproduction script for Card 273: Shared & Minor UI Components
Validates WCAG 2.2 AA contrast compliance against apps/web/src/index.css tokens.
Audit Items: 22 (Button, RiskBadge, ExecutionResultView, WorkspaceCreateModal)
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
    l_canvas = parse_hex(light['--color-bg-canvas'])
    d_canvas = parse_hex(dark['--color-bg-canvas'])
    l_surface = parse_hex(light['--color-bg-surface'])
    d_surface = parse_hex(dark['--color-bg-surface'])
    l_subtle = parse_hex(light['--color-bg-subtle'])
    d_subtle = parse_hex(dark['--color-bg-subtle'])

    items = [
        # 1. Button.tsx (Button.tsx:38, 43, 48, 53)
        ("IT01", "btn-primary text (on brand-primary-bg, Button.tsx:38)", 4.5,
         light['--color-brand-primary-fg'], dark['--color-brand-primary-fg'],
         parse_hex(light['--color-brand-primary-bg']), parse_hex(dark['--color-brand-primary-bg'])),

        ("IT02", "btn-danger text (on status-offline-bg, Button.tsx:48)", 4.5,
         light['--color-brand-primary-fg'], dark['--color-brand-primary-fg'],
         parse_hex(light['--color-status-offline-bg']), parse_hex(dark['--color-status-offline-bg'])),

        ("IT03", "btn-secondary text (on bg-subtle, Button.tsx:43)", 4.5,
         light['--color-text-primary'], dark['--color-text-primary'],
         l_subtle, d_subtle),

        ("IT04", "btn-secondary border (on bg-subtle, Button.tsx:43)", 3.0,
         light['--color-border-strong'], dark['--color-border-strong'],
         l_subtle, d_subtle),

        ("IT05", "btn-ghost text (on canvas, Button.tsx:53)", 4.5,
         light['--color-text-secondary'], dark['--color-text-secondary'],
         l_canvas, d_canvas),

        ("IT06", "btn-ghost text (on surface, Button.tsx:53)", 4.5,
         light['--color-text-secondary'], dark['--color-text-secondary'],
         l_surface, d_surface),

        # 2. RiskBadge.tsx (RiskBadge.tsx:23, 30, 37, 44, 58, 78)
        ("IT07", "risk-l0 text (on bg-subtle, RiskBadge.tsx:23,78)", 4.5,
         light['--color-risk-l0'], dark['--color-risk-l0'],
         l_subtle, d_subtle),

        ("IT08", "risk-l0 border (on bg-subtle, RiskBadge.tsx:23,79)", 3.0,
         light['--color-risk-l0'], dark['--color-risk-l0'],
         l_subtle, d_subtle),

        ("IT09", "risk-l1 text (on bg-subtle, RiskBadge.tsx:30,78)", 4.5,
         light['--color-risk-l1'], dark['--color-risk-l1'],
         l_subtle, d_subtle),

        ("IT10", "risk-l1 border (on bg-subtle, RiskBadge.tsx:30,79)", 3.0,
         light['--color-risk-l1'], dark['--color-risk-l1'],
         l_subtle, d_subtle),

        ("IT11", "risk-l2 text (on bg-subtle, RiskBadge.tsx:37,78)", 4.5,
         light['--color-risk-l2'], dark['--color-risk-l2'],
         l_subtle, d_subtle),

        ("IT12", "risk-l2 border (on bg-subtle, RiskBadge.tsx:37,79)", 3.0,
         light['--color-risk-l2'], dark['--color-risk-l2'],
         l_subtle, d_subtle),

        ("IT13", "risk-l3 text (on bg-subtle, RiskBadge.tsx:44,78)", 4.5,
         light['--color-risk-l3'], dark['--color-risk-l3'],
         l_subtle, d_subtle),

        ("IT14", "risk-l3 border (on bg-subtle, RiskBadge.tsx:44,79)", 3.0,
         light['--color-risk-l3'], dark['--color-risk-l3'],
         l_subtle, d_subtle),

        ("IT15", "risk-unknown text (on bg-subtle, RiskBadge.tsx:58,78)", 4.5,
         light['--color-status-unknown'], dark['--color-status-unknown'],
         l_subtle, d_subtle),

        ("IT16", "risk-unknown border (on bg-subtle, RiskBadge.tsx:58,79)", 3.0,
         light['--color-status-unknown'], dark['--color-status-unknown'],
         l_subtle, d_subtle),

        # 3. ExecutionResultView.tsx (ExecutionResultView.tsx:24, 47, 88, 157, 188)
        ("IT17", "exec-header text (on canvas, ExecutionResultView.tsx:24)", 4.5,
         light['--color-text-primary'], dark['--color-text-primary'],
         l_canvas, d_canvas),

        ("IT18", "exec-card-label text (on surface, ExecutionResultView.tsx:47)", 4.5,
         light['--color-text-muted'], dark['--color-text-muted'],
         l_surface, d_surface),

        ("IT19", "exec-envelope-id text (on surface, ExecutionResultView.tsx:88)", 4.5,
         light['--color-brand-primary'], dark['--color-brand-primary'],
         l_surface, d_surface),

        # 4. WorkspaceCreateModal.tsx (WorkspaceCreateModal.tsx:91, 92, 117, 118)
        # Note: line 70 backdrop (var(--color-bg-backdrop)) is non-text overlay scrim.
        ("IT20", "modal-title text (on surface, WorkspaceCreateModal.tsx:91)", 4.5,
         light['--color-text-primary'], dark['--color-text-primary'],
         l_surface, d_surface),

        ("IT21", "modal-subtitle text (on surface, WorkspaceCreateModal.tsx:92)", 4.5,
         light['--color-text-muted'], dark['--color-text-muted'],
         l_surface, d_surface),

        ("IT22", "modal-notice border (on bg-subtle, WorkspaceCreateModal.tsx:118)", 3.0,
         light['--color-border-subtle'], dark['--color-border-subtle'],
         l_subtle, d_subtle),
    ]

    print("=" * 115)
    print(f"{'ID':<6} {'Element / Indicator':<60} {'Req':<5} {'Light':<8} {'Dark':<8} {'Status':<6}")
    print("=" * 115)

    all_pass = True
    for item_id, label, req, l_fg, d_fg, l_bg, d_bg in items:
        l_cr = get_contrast(parse_hex(l_fg), l_bg)
        d_cr = get_contrast(parse_hex(d_fg), d_bg)

        l_pass = l_cr >= req
        d_pass = d_cr >= req
        status = "PASS" if (l_pass and d_pass) else "FAIL"
        if not (l_pass and d_pass):
            all_pass = False

        print(f"{item_id:<6} {label:<60} {req:<5.1f} {l_cr:<8.2f} {d_cr:<8.2f} {status:<6}")

    print("=" * 115)
    print(f"Overall Result: {'ALL PASS' if all_pass else 'SOME FAILED'}")
    return 0 if all_pass else 1


if __name__ == '__main__':
    import sys
    sys.exit(main())
