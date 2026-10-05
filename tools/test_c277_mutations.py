#!/usr/bin/env python3
"""
tools/test_c277_mutations.py:
Verification runner for 40 accessibility, contrast, contract, and fail-closed mutants (M1-M40)
targeting Card 277 components:
  - apps/web/src/app/App.tsx (M1-M30)
  - apps/web/src/features/release/releaseEngine.ts (M31-M40)

Requirements:
- Each mutant MUST compile cleanly under TypeScript (npx tsc -b).
- Each mutant MUST be killed by vitest run tests/acc09-contrast-tokens.test.tsx with timeout=120s.
- If timeout, record as TIMEOUT (do not count as killed).
- Restore original code after each mutant and verify byte equality + git diff 0.
- Sequential execution only (under 1GB memory).
- 100% kill rate (40/40) required.
"""

import os
import sys
import json
import argparse
import subprocess
from datetime import datetime, timezone
from pathlib import Path

WORKTREE_ROOT = Path(__file__).resolve().parent.parent
APPS_WEB = WORKTREE_ROOT / "apps" / "web"
RESULTS_FILE = WORKTREE_ROOT / "tools" / ".c277_mutation_results.json"

TARGET_FILES = {
    "App": APPS_WEB / "src" / "app" / "App.tsx",
    "releaseEngine": APPS_WEB / "src" / "features" / "release" / "releaseEngine.ts",
}

MUTANTS = [
    # Batch 1 (M1-M10): App.tsx Global Error Banner & Dismiss Button
    {
        "id": "M1",
        "file": "App",
        "desc": "App: Global error banner color==bg 1:1 collision (color: var(--color-risk-l3-bg))",
        "target": "        backgroundColor: 'var(--color-risk-l3-bg)',\n        color: 'var(--color-risk-l3-text)',",
        "replacement": "        backgroundColor: 'var(--color-risk-l3-bg)',\n        color: 'var(--color-risk-l3-bg)',",
    },
    {
        "id": "M2",
        "file": "App",
        "desc": "App: Global error banner border collision (borderBottom: 1px solid var(--color-risk-l3-bg))",
        "target": "        color: 'var(--color-risk-l3-text)',\n        borderBottom: '1px solid var(--color-risk-l3-border)',",
        "replacement": "        color: 'var(--color-risk-l3-text)',\n        borderBottom: '1px solid var(--color-risk-l3-bg)',",
    },
    {
        "id": "M3",
        "file": "App",
        "desc": "App: Global error banner low-contrast text (color: var(--color-text-inverse))",
        "target": "        backgroundColor: 'var(--color-risk-l3-bg)',\n        color: 'var(--color-risk-l3-text)',",
        "replacement": "        backgroundColor: 'var(--color-risk-l3-bg)',\n        color: 'var(--color-text-inverse)',",
    },
    {
        "id": "M4",
        "file": "App",
        "desc": "App: Global error banner inline outline:none focus suppression",
        "target": "        borderBottom: '1px solid var(--color-risk-l3-border)',\n        display: 'flex',",
        "replacement": "        borderBottom: '1px solid var(--color-risk-l3-border)',\n        outline: 'none',\n        display: 'flex',",
    },
    {
        "id": "M5",
        "file": "App",
        "desc": "App: Global error banner literal regression (color: #991b1b)",
        "target": "        backgroundColor: 'var(--color-risk-l3-bg)',\n        color: 'var(--color-risk-l3-text)',",
        "replacement": "        backgroundColor: 'var(--color-risk-l3-bg)',\n        color: '#991b1b',",
    },
    {
        "id": "M6",
        "file": "App",
        "desc": "App: Global error banner bg literal regression (backgroundColor: #fee2e2)",
        "target": "        backgroundColor: 'var(--color-risk-l3-bg)',\n        color: 'var(--color-risk-l3-text)',",
        "replacement": "        backgroundColor: '#fee2e2',\n        color: 'var(--color-risk-l3-text)',",
    },
    {
        "id": "M7",
        "file": "App",
        "desc": "App: Global error banner border literal regression (borderBottom: 1px solid #f87171)",
        "target": "        color: 'var(--color-risk-l3-text)',\n        borderBottom: '1px solid var(--color-risk-l3-border)',",
        "replacement": "        color: 'var(--color-risk-l3-text)',\n        borderBottom: '1px solid #f87171',",
    },
    {
        "id": "M8",
        "file": "App",
        "desc": "App: Dismiss button color==bg 1:1 collision (color: var(--color-bg-surface))",
        "target": "          backgroundColor: 'var(--color-bg-surface)',\n          color: 'var(--color-risk-l3-text)',",
        "replacement": "          backgroundColor: 'var(--color-bg-surface)',\n          color: 'var(--color-bg-surface)',",
    },
    {
        "id": "M9",
        "file": "App",
        "desc": "App: Dismiss button border collision (border: 1px solid var(--color-bg-surface))",
        "target": "          border: '1px solid var(--color-risk-l3-border)',\n          borderRadius: '4px',",
        "replacement": "          border: '1px solid var(--color-bg-surface)',\n          borderRadius: '4px',",
    },
    {
        "id": "M10",
        "file": "App",
        "desc": "App: Dismiss button border literal regression (border: 1px solid #dc2626)",
        "target": "          border: '1px solid var(--color-risk-l3-border)',\n          borderRadius: '4px',",
        "replacement": "          border: '1px solid #dc2626',\n          borderRadius: '4px',",
    },

    # Batch 2 (M11-M20): App.tsx Dismiss Button & Node Sim State Buttons
    {
        "id": "M11",
        "file": "App",
        "desc": "App: Dismiss button text literal regression (color: #991b1b)",
        "target": "          backgroundColor: 'var(--color-bg-surface)',\n          color: 'var(--color-risk-l3-text)',",
        "replacement": "          backgroundColor: 'var(--color-bg-surface)',\n          color: '#991b1b',",
    },
    {
        "id": "M12",
        "file": "App",
        "desc": "App: Dismiss button bg literal regression (backgroundColor: #ffffff)",
        "target": "          borderRadius: '4px',\n          backgroundColor: 'var(--color-bg-surface)',",
        "replacement": "          borderRadius: '4px',\n          backgroundColor: '#ffffff',",
    },
    {
        "id": "M13",
        "file": "App",
        "desc": "App: Dismiss button outline:0 focus suppression",
        "target": "          color: 'var(--color-risk-l3-text)',\n          cursor: 'pointer',",
        "replacement": "          color: 'var(--color-risk-l3-text)',\n          outline: '0',\n          cursor: 'pointer',",
    },
    {
        "id": "M14",
        "file": "App",
        "desc": "App: Node sim active button text==bg 1:1 collision (color: var(--color-brand-primary-bg))",
        "target": "                        backgroundColor: nodeSimState === key ? 'var(--color-brand-primary-bg)' : 'var(--color-bg-subtle)',\n                        color: nodeSimState === key ? 'var(--color-brand-primary-fg)' : 'var(--color-text-secondary)',",
        "replacement": "                        backgroundColor: nodeSimState === key ? 'var(--color-brand-primary-bg)' : 'var(--color-bg-subtle)',\n                        color: nodeSimState === key ? 'var(--color-brand-primary-bg)' : 'var(--color-text-secondary)',",
    },
    {
        "id": "M15",
        "file": "App",
        "desc": "App: Node sim active button border collision (border: var(--color-brand-primary-bg))",
        "target": "                        border: nodeSimState === key ? '1px solid var(--color-brand-primary-fg)' : '1px solid var(--color-border-strong)',\n                        backgroundColor: nodeSimState === key ? 'var(--color-brand-primary-bg)' : 'var(--color-bg-subtle)',",
        "replacement": "                        border: nodeSimState === key ? '1px solid var(--color-brand-primary-bg)' : '1px solid var(--color-border-strong)',\n                        backgroundColor: nodeSimState === key ? 'var(--color-brand-primary-bg)' : 'var(--color-bg-subtle)',",
    },
    {
        "id": "M16",
        "file": "App",
        "desc": "App: Node sim active button low-contrast text (color: var(--color-text-inverse))",
        "target": "                        backgroundColor: nodeSimState === key ? 'var(--color-brand-primary-bg)' : 'var(--color-bg-subtle)',\n                        color: nodeSimState === key ? 'var(--color-brand-primary-fg)' : 'var(--color-text-secondary)',",
        "replacement": "                        backgroundColor: nodeSimState === key ? 'var(--color-brand-primary-bg)' : 'var(--color-bg-subtle)',\n                        color: nodeSimState === key ? 'var(--color-text-inverse)' : 'var(--color-text-secondary)',",
    },
    {
        "id": "M17",
        "file": "App",
        "desc": "App: Node sim active button literal regression (color: #ffffff)",
        "target": "                        backgroundColor: nodeSimState === key ? 'var(--color-brand-primary-bg)' : 'var(--color-bg-subtle)',\n                        color: nodeSimState === key ? 'var(--color-brand-primary-fg)' : 'var(--color-text-secondary)',",
        "replacement": "                        backgroundColor: nodeSimState === key ? 'var(--color-brand-primary-bg)' : 'var(--color-bg-subtle)',\n                        color: nodeSimState === key ? '#ffffff' : 'var(--color-text-secondary)',",
    },
    {
        "id": "M18",
        "file": "App",
        "desc": "App: Node sim button outlineStyle:none suppression",
        "target": "                        cursor: 'pointer',\n                        border: nodeSimState === key",
        "replacement": "                        cursor: 'pointer',\n                        outlineStyle: 'none',\n                        border: nodeSimState === key",
    },
    {
        "id": "M19",
        "file": "App",
        "desc": "App: Node sim inactive button text==bg 1:1 collision (color: var(--color-bg-subtle))",
        "target": "                        backgroundColor: nodeSimState === key ? 'var(--color-brand-primary-bg)' : 'var(--color-bg-subtle)',\n                        color: nodeSimState === key ? 'var(--color-brand-primary-fg)' : 'var(--color-text-secondary)',",
        "replacement": "                        backgroundColor: nodeSimState === key ? 'var(--color-brand-primary-bg)' : 'var(--color-bg-subtle)',\n                        color: nodeSimState === key ? 'var(--color-brand-primary-fg)' : 'var(--color-bg-subtle)',",
    },
    {
        "id": "M20",
        "file": "App",
        "desc": "App: Node sim inactive button border collision (border: var(--color-bg-subtle))",
        "target": "                        border: nodeSimState === key ? '1px solid var(--color-brand-primary-fg)' : '1px solid var(--color-border-strong)',\n                        backgroundColor: nodeSimState === key ? 'var(--color-brand-primary-bg)' : 'var(--color-bg-subtle)',",
        "replacement": "                        border: nodeSimState === key ? '1px solid var(--color-brand-primary-fg)' : '1px solid var(--color-bg-subtle)',\n                        backgroundColor: nodeSimState === key ? 'var(--color-brand-primary-bg)' : 'var(--color-bg-subtle)',",
    },

    # Batch 3 (M21-M30): App.tsx Workspace Error Banner & Terminal Notice
    {
        "id": "M21",
        "file": "App",
        "desc": "App: Workspace error banner color==bg 1:1 collision (color: var(--color-risk-l3-bg))",
        "target": "                  backgroundColor: 'var(--color-risk-l3-bg)',\n                  border: '1px solid var(--color-risk-l3-border)',\n                  borderRadius: 'var(--radius-md)',\n                  color: 'var(--color-risk-l3-text)',",
        "replacement": "                  backgroundColor: 'var(--color-risk-l3-bg)',\n                  border: '1px solid var(--color-risk-l3-border)',\n                  borderRadius: 'var(--radius-md)',\n                  color: 'var(--color-risk-l3-bg)',",
    },
    {
        "id": "M22",
        "file": "App",
        "desc": "App: Workspace error banner border collision (border: 1px solid var(--color-risk-l3-bg))",
        "target": "                  backgroundColor: 'var(--color-risk-l3-bg)',\n                  border: '1px solid var(--color-risk-l3-border)',",
        "replacement": "                  backgroundColor: 'var(--color-risk-l3-bg)',\n                  border: '1px solid var(--color-risk-l3-bg)',",
    },
    {
        "id": "M23",
        "file": "App",
        "desc": "App: Workspace error banner low-contrast text (color: var(--color-text-inverse))",
        "target": "                  color: 'var(--color-risk-l3-text)',\n                  fontSize: '0.875rem',",
        "replacement": "                  color: 'var(--color-text-inverse)',\n                  fontSize: '0.875rem',",
    },
    {
        "id": "M24",
        "file": "App",
        "desc": "App: Workspace error banner literal regression (color: #fca5a5)",
        "target": "                  color: 'var(--color-risk-l3-text)',\n                  fontSize: '0.875rem',",
        "replacement": "                  color: '#fca5a5',\n                  fontSize: '0.875rem',",
    },
    {
        "id": "M25",
        "file": "App",
        "desc": "App: Workspace error banner bg literal regression (backgroundColor: rgba(239, 68, 68, 0.1))",
        "target": "                  padding: '12px 16px',\n                  backgroundColor: 'var(--color-risk-l3-bg)',",
        "replacement": "                  padding: '12px 16px',\n                  backgroundColor: 'rgba(239, 68, 68, 0.1)',",
    },
    {
        "id": "M26",
        "file": "App",
        "desc": "App: Workspace error banner border literal regression (border: 1px solid #ef4444)",
        "target": "                  backgroundColor: 'var(--color-risk-l3-bg)',\n                  border: '1px solid var(--color-risk-l3-border)',",
        "replacement": "                  backgroundColor: 'var(--color-risk-l3-bg)',\n                  border: '1px solid #ef4444',",
    },
    {
        "id": "M27",
        "file": "App",
        "desc": "App: Terminal notice guidance text literal regression (color: #fed7aa)",
        "target": "                  <div style={{ marginTop: '4px', fontSize: '0.75rem', color: 'var(--color-status-degraded)' }}>",
        "replacement": "                  <div style={{ marginTop: '4px', fontSize: '0.75rem', color: '#fed7aa' }}>",
    },
    {
        "id": "M28",
        "file": "App",
        "desc": "App: Terminal notice guidance low-contrast text (color: var(--color-text-inverse))",
        "target": "                  <div style={{ marginTop: '4px', fontSize: '0.75rem', color: 'var(--color-status-degraded)' }}>",
        "replacement": "                  <div style={{ marginTop: '4px', fontSize: '0.75rem', color: 'var(--color-text-inverse)' }}>",
    },
    {
        "id": "M29",
        "file": "App",
        "desc": "App: Terminal notice outlineWidth:0 focus suppression",
        "target": "                    color: 'var(--color-text-muted)',\n                    lineHeight: '1.4',",
        "replacement": "                    color: 'var(--color-text-muted)',\n                    outlineWidth: '0',\n                    lineHeight: '1.4',",
    },
    {
        "id": "M30",
        "file": "App",
        "desc": "App: Terminal notice guidance color==bg 1:1 collision (color: var(--color-bg-surface))",
        "target": "                  <div style={{ marginTop: '4px', fontSize: '0.75rem', color: 'var(--color-status-degraded)' }}>",
        "replacement": "                  <div style={{ marginTop: '4px', fontSize: '0.75rem', color: 'var(--color-bg-surface)' }}>",
    },

    # Batch 4 (M31-M40): releaseEngine.ts Accessibility Audits
    {
        "id": "M31",
        "file": "releaseEngine",
        "desc": "releaseEngine: WCAG 1.4.3 description literal regression (#0d1117)",
        "target": "      description: '본문 텍스트와 배경 간 명도 대비가 최소 4.5:1 이상이어야 함',",
        "replacement": "      description: '본문 텍스트와 배경 간 명도 대비가 최소 4.5:1 이상(#0d1117)이어야 함',",
    },
    {
        "id": "M32",
        "file": "releaseEngine",
        "desc": "releaseEngine: WCAG 1.4.3 description literal regression (#c9d1d9)",
        "target": "      description: '본문 텍스트와 배경 간 명도 대비가 최소 4.5:1 이상이어야 함',",
        "replacement": "      description: '본문 텍스트(#c9d1d9)와 배경 간 명도 대비가 최소 4.5:1 이상이어야 함',",
    },
    {
        "id": "M33",
        "file": "releaseEngine",
        "desc": "releaseEngine: WCAG 1.4.11 description literal regression (#6e7681)",
        "target": "      description: '버튼, 칩, 입력창 등 UI 컴포넌트 인터랙티브 경계선(--color-border-subtle on --color-bg-canvas) 명도 대비가 최소 3:1 이상(실측 4.12:1)이어야 함',",
        "replacement": "      description: '버튼, 칩, 입력창 등 UI 컴포넌트 인터랙티브 경계선(#6e7681 on --color-bg-canvas) 명도 대비가 최소 3:1 이상(실측 4.12:1)이어야 함',",
    },
    {
        "id": "M34",
        "file": "releaseEngine",
        "desc": "releaseEngine: WCAG 1.4.11 description literal regression (#0d1117)",
        "target": "      description: '버튼, 칩, 입력창 등 UI 컴포넌트 인터랙티브 경계선(--color-border-subtle on --color-bg-canvas) 명도 대비가 최소 3:1 이상(실측 4.12:1)이어야 함',",
        "replacement": "      description: '버튼, 칩, 입력창 등 UI 컴포넌트 인터랙티브 경계선(--color-border-subtle on #0d1117) 명도 대비가 최소 3:1 이상(실측 4.12:1)이어야 함',",
    },
    {
        "id": "M35",
        "file": "releaseEngine",
        "desc": "releaseEngine: WCAG 1.4.3 ratio regression (contrastRatio: 3.5)",
        "target": "      contrastRatio: 12.26, // var(--color-text-secondary) on var(--color-bg-canvas)",
        "replacement": "      contrastRatio: 3.5, // var(--color-text-secondary) on var(--color-bg-canvas)",
    },
    {
        "id": "M36",
        "file": "releaseEngine",
        "desc": "releaseEngine: WCAG 1.4.11 ratio regression (contrastRatio: 2.1)",
        "target": "      contrastRatio: 4.12, // var(--color-border-subtle) on var(--color-bg-canvas)",
        "replacement": "      contrastRatio: 2.1, // var(--color-border-subtle) on var(--color-bg-canvas)",
    },
    {
        "id": "M37",
        "file": "releaseEngine",
        "desc": "releaseEngine: WCAG 1.4.3 status regression (status: fail)",
        "target": "      ruleId: 'wcag21-1.4.3-contrast-minimum',\n      wcagLevel: 'AA',\n      description: '본문 텍스트와 배경 간 명도 대비가 최소 4.5:1 이상이어야 함',\n      status: 'pass',",
        "replacement": "      ruleId: 'wcag21-1.4.3-contrast-minimum',\n      wcagLevel: 'AA',\n      description: '본문 텍스트와 배경 간 명도 대비가 최소 4.5:1 이상이어야 함',\n      status: 'fail',",
    },
    {
        "id": "M38",
        "file": "releaseEngine",
        "desc": "releaseEngine: WCAG 1.4.11 status regression (status: fail)",
        "target": "      ruleId: 'wcag21-1.4.11-non-text-contrast',\n      wcagLevel: 'AA',\n      description: '버튼, 칩, 입력창 등 UI 컴포넌트 인터랙티브 경계선(--color-border-subtle on --color-bg-canvas) 명도 대비가 최소 3:1 이상(실측 4.12:1)이어야 함',\n      status: 'pass',",
        "replacement": "      ruleId: 'wcag21-1.4.11-non-text-contrast',\n      wcagLevel: 'AA',\n      description: '버튼, 칩, 입력창 등 UI 컴포넌트 인터랙티브 경계선(--color-border-subtle on --color-bg-canvas) 명도 대비가 최소 3:1 이상(실측 4.12:1)이어야 함',\n      status: 'fail',",
    },
    {
        "id": "M39",
        "file": "releaseEngine",
        "desc": "releaseEngine: WCAG 1.4.11 description token omission (remove --color-border-subtle)",
        "target": "      description: '버튼, 칩, 입력창 등 UI 컴포넌트 인터랙티브 경계선(--color-border-subtle on --color-bg-canvas) 명도 대비가 최소 3:1 이상(실측 4.12:1)이어야 함',",
        "replacement": "      description: '버튼, 칩, 입력창 등 UI 컴포넌트 인터랙티브 경계선(boundary on --color-bg-canvas) 명도 대비가 최소 3:1 이상(실측 4.12:1)이어야 함',",
    },
    {
        "id": "M40",
        "file": "releaseEngine",
        "desc": "releaseEngine: WCAG 1.4.3 audit deletion (filter out wcag21-1.4.3-contrast-minimum)",
        "target": "  getAccessibilityAudits(): AccessibilityAuditResult[] {\n    return [...this.accessibilityAudits];\n  }",
        "replacement": "  getAccessibilityAudits(): AccessibilityAuditResult[] {\n    return this.accessibilityAudits.filter(a => a.ruleId !== 'wcag21-1.4.3-contrast-minimum');\n  }",
    },
]


def restore_files(original_bytes_map):
    for name, orig_bytes in original_bytes_map.items():
        file_path = TARGET_FILES[name]
        current_bytes = file_path.read_bytes()
        if current_bytes != orig_bytes:
            file_path.write_bytes(orig_bytes)


def test_mutant(mutant, original_bytes_map, timeout=120, head_sha="unknown"):
    mutant_id = mutant["id"]
    target_file = TARGET_FILES[mutant["file"]]
    desc = mutant["desc"]
    target = mutant["target"]
    replacement = mutant["replacement"]

    print(f"\n=== Testing Mutant {mutant_id}: {desc} ===")
    content = target_file.read_text(encoding="utf-8")
    if target not in content:
        print(f"  [ERROR] Target snippet not found in {mutant['file']}:")
        print(f"  {repr(target)}")
        return {"id": mutant_id, "desc": desc, "status": "TARGET_NOT_FOUND", "killed": False}

    count = content.count(target)
    if count > 1:
        print(f"  [ERROR] Target snippet found {count} times (ambiguous) in {mutant['file']}:")
        return {"id": mutant_id, "desc": desc, "status": "TARGET_AMBIGUOUS", "killed": False}

    mutated_content = content.replace(target, replacement, 1)
    target_file.write_text(mutated_content, encoding="utf-8")

    # 1. Typecheck: Each mutant must compile cleanly under TypeScript
    tsc_res = subprocess.run(
        ["npx.cmd" if os.name == "nt" else "npx", "tsc", "-b"],
        cwd=str(APPS_WEB),
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True,
        encoding="utf-8",
        errors="replace",
        timeout=60,
    )
    if tsc_res.returncode != 0:
        print(f"  [TSC FAIL] Mutant introduced TypeScript compilation errors (not clean mutant):")
        print(tsc_res.stdout[:500])
        restore_files(original_bytes_map)
        return {"id": mutant_id, "desc": desc, "status": "TSC_FAIL", "killed": False}

    # 2. Test Execution: Must be killed by vitest run tests/acc09-contrast-tokens.test.tsx
    observed_time = datetime.now(timezone.utc).isoformat()
    try:
        vitest_res = subprocess.run(
            ["npx.cmd" if os.name == "nt" else "npx", "vitest", "run", "tests/acc09-contrast-tokens.test.tsx"],
            cwd=str(APPS_WEB),
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
            encoding="utf-8",
            errors="replace",
            timeout=timeout,
        )
        retcode = vitest_res.returncode
        stdout = vitest_res.stdout
    except subprocess.TimeoutExpired:
        print(f"  [TIMEOUT] Vitest exceeded {timeout}s timeout!")
        restore_files(original_bytes_map)
        return {
            "id": mutant_id,
            "desc": desc,
            "status": "TIMEOUT",
            "killed": False,
            "sourceHeadSha": head_sha,
            "observedAt": observed_time,
        }

    restore_files(original_bytes_map)

    post_bytes = target_file.read_bytes()
    if post_bytes != original_bytes_map[mutant["file"]]:
        print(f"  [FATAL] Byte verification failed after restoration for {mutant['file']}!")
        sys.exit(1)

    if retcode != 0:
        failed_test = "acc09-contrast-tokens.test.tsx"
        for line in stdout.splitlines():
            if "FAIL" in line and ".test." in line:
                failed_test = line.strip()
                break
            elif "AssertionError:" in line:
                failed_test = line.strip()
                break
        print(f"  [KILLED] Retcode {retcode}, caught by: {failed_test}")
        return {
            "id": mutant_id,
            "desc": desc,
            "status": "KILLED",
            "killed": True,
            "killer": failed_test,
            "sourceHeadSha": head_sha,
            "observedAt": observed_time,
        }
    else:
        print(f"  [SURVIVED] Vitest passed! Mutant was NOT killed!")
        return {
            "id": mutant_id,
            "desc": desc,
            "status": "SURVIVED",
            "killed": False,
            "sourceHeadSha": head_sha,
            "observedAt": observed_time,
        }


def main():
    parser = argparse.ArgumentParser(description="Test Card 277 mutations across App and releaseEngine components")
    parser.add_argument("--batch", type=int, choices=[1, 2, 3, 4], help="Run specific batch (1: M1-M10, 2: M11-M20, 3: M21-M30, 4: M31-M40)")
    parser.add_argument("--mutant", type=str, help="Run single mutant by ID (e.g. M1)")
    parser.add_argument("--all", action="store_true", help="Run all 40 mutants sequentially")
    parser.add_argument("--verify-targets", action="store_true", help="Verify all targets exist in files")
    parser.add_argument("--timeout", type=int, default=120, help="Per-mutant vitest timeout in seconds")
    args = parser.parse_args()

    original_bytes_map = {k: v.read_bytes() for k, v in TARGET_FILES.items()}

    if args.verify_targets:
        print("Verifying mutant targets...")
        missing = 0
        for m in MUTANTS:
            content = TARGET_FILES[m["file"]].read_text(encoding="utf-8")
            if m["target"] not in content:
                print(f"  [MISSING] {m['id']} in {m['file']}: target not found!")
                missing += 1
            else:
                count = content.count(m["target"])
                if count > 1:
                    print(f"  [AMBIGUOUS] {m['id']} in {m['file']}: target found {count} times!")
                    missing += 1
                else:
                    print(f"  [FOUND] {m['id']} in {m['file']}")
        if missing == 0:
            print(f"All {len(MUTANTS)} mutant targets verified uniquely!")
            return 0
        else:
            print(f"ERROR: {missing} mutant targets missing or ambiguous!")
            return 1

    try:
        head_sha = subprocess.check_output(["git", "rev-parse", "HEAD"], cwd=str(WORKTREE_ROOT), text=True).strip()
    except Exception:
        head_sha = "unknown"

    selected_mutants = []
    if args.mutant:
        selected_mutants = [m for m in MUTANTS if m["id"] == args.mutant]
        if not selected_mutants:
            print(f"Unknown mutant: {args.mutant}")
            return 1
    elif args.batch:
        if args.batch == 1:
            selected_mutants = MUTANTS[0:10]
        elif args.batch == 2:
            selected_mutants = MUTANTS[10:20]
        elif args.batch == 3:
            selected_mutants = MUTANTS[20:30]
        elif args.batch == 4:
            selected_mutants = MUTANTS[30:40]
    elif args.all:
        selected_mutants = MUTANTS
    else:
        print("Please specify --mutant, --batch, --all, or --verify-targets")
        return 1

    print(f"Starting mutation testing for {len(selected_mutants)} mutant(s) (head SHA: {head_sha})")

    results = []
    for m in selected_mutants:
        res = test_mutant(m, original_bytes_map, timeout=args.timeout, head_sha=head_sha)
        results.append(res)

    if args.all:
        killed_count = sum(1 for r in results if r["killed"])
        summary = {
            "sourceHeadSha": head_sha,
            "observedAt": datetime.now(timezone.utc).isoformat(),
            "totalTested": len(results),
            "totalMutants": len(MUTANTS),
            "killed": killed_count,
            "survived": sum(1 for r in results if r.get("status") == "SURVIVED"),
            "timeouts": sum(1 for r in results if r.get("status") == "TIMEOUT"),
            "tsc_fails": sum(1 for r in results if r.get("status") == "TSC_FAIL"),
            "mutations": results,
        }
        RESULTS_FILE.write_text(json.dumps(summary, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
        print(f"\nSaved complete mutation results to {RESULTS_FILE}")
        print(f"Kill Rate: {killed_count}/{len(results)} ({killed_count/len(results)*100:.1f}%)")
        return 0 if killed_count == len(results) else 1

    return 0

if __name__ == "__main__":
    sys.exit(main())
