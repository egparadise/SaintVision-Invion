#!/usr/bin/env python3
"""
tools/test_c273_mutations.py:
Verification runner for 40 accessibility, contrast, contract, and fail-closed mutants (W1-W40)
targeting Card 273 Shared & Minor UI components:
  - apps/web/src/shared/ui/RiskBadge.tsx
  - apps/web/src/shared/ui/Button.tsx
  - apps/web/src/features/workspaces/ExecutionResultView.tsx
  - apps/web/src/features/workspaces/WorkspaceCreateModal.tsx

Requirements:
- Each mutant MUST compile cleanly under TypeScript (npx tsc -b).
- Each mutant MUST be killed by vitest run tests/acc09-contrast-tokens.test.tsx with timeout=120s.
- If timeout, record as TIMEOUT (do not count as killed).
- Restore original code after each mutant and verify byte equality + git diff 0.
- 5~10 mutants per batch (8 per batch across 5 batches).
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
RESULTS_FILE = WORKTREE_ROOT / "tools" / ".c273_mutation_results.json"

TARGET_FILES = {
    "RiskBadge": APPS_WEB / "src" / "shared" / "ui" / "RiskBadge.tsx",
    "Button": APPS_WEB / "src" / "shared" / "ui" / "Button.tsx",
    "ExecutionResultView": APPS_WEB / "src" / "features" / "workspaces" / "ExecutionResultView.tsx",
    "WorkspaceCreateModal": APPS_WEB / "src" / "features" / "workspaces" / "WorkspaceCreateModal.tsx",
}

MUTANTS = [
    # Batch 1 (W1-W8): RiskBadge contract & config
    {
        "id": "W1",
        "file": "RiskBadge",
        "desc": "RiskBadge: L0 colorVar==bgVar collision (colorVar: var(--color-bg-subtle))",
        "target": "colorVar: 'var(--color-risk-l0)',",
        "replacement": "colorVar: 'var(--color-bg-subtle)',",
    },
    {
        "id": "W2",
        "file": "RiskBadge",
        "desc": "RiskBadge: L0 bgVar==colorVar collision (bgVar: var(--color-risk-l0))",
        "target": "L0: {\n    label: 'L0',\n    description: '읽기 전용 (안전)',\n    icon: '🛡️',\n    colorVar: 'var(--color-risk-l0)',\n    bgVar: 'var(--color-bg-subtle)',\n  },",
        "replacement": "L0: {\n    label: 'L0',\n    description: '읽기 전용 (안전)',\n    icon: '🛡️',\n    colorVar: 'var(--color-risk-l0)',\n    bgVar: 'var(--color-risk-l0)',\n  },",
    },
    {
        "id": "W3",
        "file": "RiskBadge",
        "desc": "RiskBadge: L1 colorVar synchronized low-contrast mutation (colorVar: var(--color-text-inverse))",
        "target": "colorVar: 'var(--color-risk-l1)',",
        "replacement": "colorVar: 'var(--color-text-inverse)',",
    },
    {
        "id": "W4",
        "file": "RiskBadge",
        "desc": "RiskBadge: L2 colorVar synchronized low-contrast mutation (colorVar: var(--color-text-inverse))",
        "target": "colorVar: 'var(--color-risk-l2)',",
        "replacement": "colorVar: 'var(--color-text-inverse)',",
    },
    {
        "id": "W5",
        "file": "RiskBadge",
        "desc": "RiskBadge: L3 colorVar synchronized low-contrast mutation (colorVar: var(--color-text-inverse))",
        "target": "colorVar: 'var(--color-risk-l3)',",
        "replacement": "colorVar: 'var(--color-text-inverse)',",
    },
    {
        "id": "W6",
        "file": "RiskBadge",
        "desc": "RiskBadge: L3 bgVar==colorVar collision (bgVar: var(--color-risk-l3))",
        "target": "  L3: {\n    label: 'L3',\n    description: '기본 차단 (위험)',\n    icon: '🛑',\n    colorVar: 'var(--color-risk-l3)',\n    bgVar: 'var(--color-bg-subtle)',",
        "replacement": "  L3: {\n    label: 'L3',\n    description: '기본 차단 (위험)',\n    icon: '🛑',\n    colorVar: 'var(--color-risk-l3)',\n    bgVar: 'var(--color-risk-l3)',",
    },
    {
        "id": "W7",
        "file": "RiskBadge",
        "desc": "RiskBadge: fail-closed prototype check bypass (remove Object.hasOwn, use 'in' operator)",
        "target": "if (typeof level === 'string' && Object.hasOwn(RISK_CONFIG, level)) {",
        "replacement": "if (typeof level === 'string' && level in RISK_CONFIG) {",
    },
    {
        "id": "W8",
        "file": "RiskBadge",
        "desc": "RiskBadge: UNKNOWN label mutation (change UNKNOWN to UNKNOWN_BAD)",
        "target": "label: raw ? `UNKNOWN (${raw})` : 'UNKNOWN',",
        "replacement": "label: raw ? `UNKNOWN_BAD (${raw})` : 'UNKNOWN',",
    },

    # Batch 2 (W9-W16): RiskBadge fallback & rendering
    {
        "id": "W9",
        "file": "RiskBadge",
        "desc": "RiskBadge: fallback colorVar==bgVar collision (colorVar: var(--color-bg-subtle))",
        "target": "    colorVar: 'var(--color-status-unknown)',\n    bgVar: 'var(--color-bg-subtle)',",
        "replacement": "    colorVar: 'var(--color-bg-subtle)',\n    bgVar: 'var(--color-bg-subtle)',",
    },
    {
        "id": "W10",
        "file": "RiskBadge",
        "desc": "RiskBadge: fallback bgVar==colorVar collision (bgVar: var(--color-status-unknown))",
        "target": "    colorVar: 'var(--color-status-unknown)',\n    bgVar: 'var(--color-bg-subtle)',",
        "replacement": "    colorVar: 'var(--color-status-unknown)',\n    bgVar: 'var(--color-status-unknown)',",
    },
    {
        "id": "W11",
        "file": "RiskBadge",
        "desc": "RiskBadge: fallback low-contrast text mutation (colorVar: var(--color-text-inverse))",
        "target": "    colorVar: 'var(--color-status-unknown)',\n    bgVar: 'var(--color-bg-subtle)',",
        "replacement": "    colorVar: 'var(--color-text-inverse)',\n    bgVar: 'var(--color-bg-subtle)',",
    },
    {
        "id": "W12",
        "file": "RiskBadge",
        "desc": "RiskBadge: container border==bgVar collision (border: 1px solid var(--color-bg-subtle))",
        "target": "border: `1px solid ${config.colorVar}`,",
        "replacement": "border: '1px solid var(--color-bg-subtle)',",
    },
    {
        "id": "W13",
        "file": "RiskBadge",
        "desc": "RiskBadge: rendered label mutated to static HARDCODED string",
        "target": "<span>{config.label}</span>",
        "replacement": "<span>HARDCODED</span>",
    },
    {
        "id": "W14",
        "file": "RiskBadge",
        "desc": "RiskBadge: accessibility role='status' removed from container",
        "target": "    <span\n      role=\"status\"",
        "replacement": "    <span",
    },
    {
        "id": "W15",
        "file": "RiskBadge",
        "desc": "RiskBadge: accessibility aria-label suppressed to empty string",
        "target": "      aria-label={`위험 등급 ${config.label}: ${config.description}`}",
        "replacement": "      aria-label=\"\"",
    },
    {
        "id": "W16",
        "file": "RiskBadge",
        "desc": "RiskBadge: L0 bgVar mutated to var(--color-bg-canvas) breaking uniform subtle styling",
        "target": "L0: {\n    label: 'L0',\n    description: '읽기 전용 (안전)',\n    icon: '🛡️',\n    colorVar: 'var(--color-risk-l0)',\n    bgVar: 'var(--color-bg-subtle)',\n  },",
        "replacement": "L0: {\n    label: 'L0',\n    description: '읽기 전용 (안전)',\n    icon: '🛡️',\n    colorVar: 'var(--color-risk-l0)',\n    bgVar: 'var(--color-bg-canvas)',\n  },",
    },

    # Batch 3 (W17-W24): Button variants & contrast
    {
        "id": "W17",
        "file": "Button",
        "desc": "Button: primary color==bg collision (color: var(--color-brand-primary-bg))",
        "target": "      backgroundColor: 'var(--color-brand-primary-bg, var(--color-brand-primary))',\n      color: 'var(--color-brand-primary-fg)',",
        "replacement": "      backgroundColor: 'var(--color-brand-primary-bg, var(--color-brand-primary))',\n      color: 'var(--color-brand-primary-bg)',",
    },
    {
        "id": "W18",
        "file": "Button",
        "desc": "Button: primary low-contrast text mutation (color: var(--color-text-muted))",
        "target": "      backgroundColor: 'var(--color-brand-primary-bg, var(--color-brand-primary))',\n      color: 'var(--color-brand-primary-fg)',",
        "replacement": "      backgroundColor: 'var(--color-brand-primary-bg, var(--color-brand-primary))',\n      color: 'var(--color-text-muted)',",
    },
    {
        "id": "W19",
        "file": "Button",
        "desc": "Button: baseStyle outline: 'none' suppressing focus ring (focus ring suppression violation)",
        "target": "    opacity: disabled || isLoading ? 0.6 : 1,\n    userSelect: 'none',\n  };",
        "replacement": "    opacity: disabled || isLoading ? 0.6 : 1,\n    userSelect: 'none',\n    outline: 'none',\n  };",
    },
    {
        "id": "W20",
        "file": "Button",
        "desc": "Button: danger color==bg collision (color: var(--color-status-offline-bg))",
        "target": "      backgroundColor: 'var(--color-status-offline-bg, var(--color-status-offline))',\n      color: 'var(--color-brand-primary-fg)',",
        "replacement": "      backgroundColor: 'var(--color-status-offline-bg, var(--color-status-offline))',\n      color: 'var(--color-status-offline-bg)',",
    },
    {
        "id": "W21",
        "file": "Button",
        "desc": "Button: danger low-contrast text mutation (color: var(--color-text-secondary))",
        "target": "      backgroundColor: 'var(--color-status-offline-bg, var(--color-status-offline))',\n      color: 'var(--color-brand-primary-fg)',",
        "replacement": "      backgroundColor: 'var(--color-status-offline-bg, var(--color-status-offline))',\n      color: 'var(--color-text-secondary)',",
    },
    {
        "id": "W22",
        "file": "Button",
        "desc": "Button: secondary color==bg collision (color: var(--color-bg-subtle))",
        "target": "      backgroundColor: 'var(--color-bg-subtle)',\n      color: 'var(--color-text-primary)',",
        "replacement": "      backgroundColor: 'var(--color-bg-subtle)',\n      color: 'var(--color-bg-subtle)',",
    },
    {
        "id": "W23",
        "file": "Button",
        "desc": "Button: secondary bg==color collision (backgroundColor: var(--color-text-primary))",
        "target": "      backgroundColor: 'var(--color-bg-subtle)',\n      color: 'var(--color-text-primary)',",
        "replacement": "      backgroundColor: 'var(--color-text-primary)',\n      color: 'var(--color-text-primary)',",
    },
    {
        "id": "W24",
        "file": "Button",
        "desc": "Button: secondary border==bg collision (border: 1px solid var(--color-bg-subtle))",
        "target": "      border: '1px solid var(--color-border-strong)',",
        "replacement": "      border: '1px solid var(--color-bg-subtle)',",
    },

    # Batch 4 (W25-W32): Button & ExecutionResultView
    {
        "id": "W25",
        "file": "Button",
        "desc": "Button: primary color revert to raw literal #ffffff (multiset ratchet failure)",
        "target": "primary: {\n      backgroundColor: 'var(--color-brand-primary-bg, var(--color-brand-primary))',\n      color: 'var(--color-brand-primary-fg)',",
        "replacement": "primary: {\n      backgroundColor: 'var(--color-brand-primary-bg, var(--color-brand-primary))',\n      color: '#ffffff',",
    },
    {
        "id": "W26",
        "file": "Button",
        "desc": "Button: danger color revert to raw literal #ffffff (multiset ratchet failure)",
        "target": "danger: {\n      backgroundColor: 'var(--color-status-offline-bg, var(--color-status-offline))',\n      color: 'var(--color-brand-primary-fg)',",
        "replacement": "danger: {\n      backgroundColor: 'var(--color-status-offline-bg, var(--color-status-offline))',\n      color: '#ffffff',",
    },
    {
        "id": "W27",
        "file": "ExecutionResultView",
        "desc": "ExecutionResultView: success pill bg revert to raw literal rgba(16, 185, 129, 0.15)",
        "target": "backgroundColor: isSuccess ? 'var(--color-bg-subtle)' : 'var(--color-risk-l3-bg)',",
        "replacement": "backgroundColor: isSuccess ? 'rgba(16, 185, 129, 0.15)' : 'var(--color-risk-l3-bg)',",
    },
    {
        "id": "W28",
        "file": "ExecutionResultView",
        "desc": "ExecutionResultView: success pill bg==color collision (backgroundColor: var(--color-brand-success))",
        "target": "backgroundColor: isSuccess ? 'var(--color-bg-subtle)' : 'var(--color-risk-l3-bg)',\n                color: isSuccess ? 'var(--color-brand-success)' : 'var(--color-brand-danger)',",
        "replacement": "backgroundColor: isSuccess ? 'var(--color-brand-success)' : 'var(--color-risk-l3-bg)',\n                color: isSuccess ? 'var(--color-brand-success)' : 'var(--color-brand-danger)',",
    },
    {
        "id": "W29",
        "file": "ExecutionResultView",
        "desc": "ExecutionResultView: success pill color==bg collision (color: var(--color-bg-subtle))",
        "target": "backgroundColor: isSuccess ? 'var(--color-bg-subtle)' : 'var(--color-risk-l3-bg)',\n                color: isSuccess ? 'var(--color-brand-success)' : 'var(--color-brand-danger)',",
        "replacement": "backgroundColor: isSuccess ? 'var(--color-bg-subtle)' : 'var(--color-risk-l3-bg)',\n                color: isSuccess ? 'var(--color-bg-subtle)' : 'var(--color-brand-danger)',",
    },
    {
        "id": "W30",
        "file": "ExecutionResultView",
        "desc": "ExecutionResultView: exit code card bg mutated to var(--color-bg-canvas)",
        "target": "        {/* Exit Code Card */}\n        <div\n          style={{\n            padding: '20px',\n            backgroundColor: 'var(--color-bg-surface)',",
        "replacement": "        {/* Exit Code Card */}\n        <div\n          style={{\n            padding: '20px',\n            backgroundColor: 'var(--color-bg-canvas)',",
    },
    {
        "id": "W31",
        "file": "ExecutionResultView",
        "desc": "ExecutionResultView: success status text changed from '정상 종료 (SUCCESS)' to 'SUCCESS'",
        "target": "{isSuccess ? '정상 종료 (SUCCESS)' : '비정상 종료 (FAILED)'}",
        "replacement": "{isSuccess ? 'SUCCESS' : '비정상 종료 (FAILED)'}",
    },
    {
        "id": "W32",
        "file": "ExecutionResultView",
        "desc": "ExecutionResultView: allowed event row bg mutated to var(--color-bg-surface)",
        "target": "                  padding: '8px 12px',\n                  backgroundColor: 'var(--color-bg-subtle)',",
        "replacement": "                  padding: '8px 12px',\n                  backgroundColor: 'var(--color-bg-surface)',",
    },

    # Batch 5 (W33-W40): WorkspaceCreateModal & RiskBadge
    {
        "id": "W33",
        "file": "WorkspaceCreateModal",
        "desc": "WorkspaceCreateModal: backdrop bg revert to raw literal rgba(0, 0, 0, 0.65)",
        "target": "        position: 'fixed',\n        inset: 0,\n        backgroundColor: 'var(--color-bg-backdrop)',",
        "replacement": "        position: 'fixed',\n        inset: 0,\n        backgroundColor: 'rgba(0, 0, 0, 0.65)',",
    },
    {
        "id": "W34",
        "file": "WorkspaceCreateModal",
        "desc": "WorkspaceCreateModal: backdrop bg mutated to var(--color-bg-surface)",
        "target": "        position: 'fixed',\n        inset: 0,\n        backgroundColor: 'var(--color-bg-backdrop)',",
        "replacement": "        position: 'fixed',\n        inset: 0,\n        backgroundColor: 'var(--color-bg-surface)',",
    },
    {
        "id": "W35",
        "file": "WorkspaceCreateModal",
        "desc": "WorkspaceCreateModal: dialog surface bg mutated to var(--color-bg-subtle)",
        "target": "      <div\n        style={{\n          backgroundColor: 'var(--color-bg-surface)',",
        "replacement": "      <div\n        style={{\n          backgroundColor: 'var(--color-bg-subtle)',",
    },
    {
        "id": "W36",
        "file": "WorkspaceCreateModal",
        "desc": "WorkspaceCreateModal: dialog accessibility role='dialog' removed",
        "target": "    <div\n      ref={containerRef}\n      role=\"dialog\"",
        "replacement": "    <div\n      ref={containerRef}",
    },
    {
        "id": "W37",
        "file": "RiskBadge",
        "desc": "RiskBadge: L0 bgVar revert to raw literal rgba(16, 185, 129, 0.15)",
        "target": "L0: {\n    label: 'L0',\n    description: '읽기 전용 (안전)',\n    icon: '🛡️',\n    colorVar: 'var(--color-risk-l0)',\n    bgVar: 'var(--color-bg-subtle)',\n  },",
        "replacement": "L0: {\n    label: 'L0',\n    description: '읽기 전용 (안전)',\n    icon: '🛡️',\n    colorVar: 'var(--color-risk-l0)',\n    bgVar: 'rgba(16, 185, 129, 0.15)',\n  },",
    },
    {
        "id": "W38",
        "file": "RiskBadge",
        "desc": "RiskBadge: L1 bgVar revert to raw literal rgba(59, 130, 246, 0.15)",
        "target": "L1: {\n    label: 'L1',\n    description: '격리 실행 (경미)',\n    icon: 'ℹ️',\n    colorVar: 'var(--color-risk-l1)',\n    bgVar: 'var(--color-bg-subtle)',\n  },",
        "replacement": "L1: {\n    label: 'L1',\n    description: '격리 실행 (경미)',\n    icon: 'ℹ️',\n    colorVar: 'var(--color-risk-l1)',\n    bgVar: 'rgba(59, 130, 246, 0.15)',\n  },",
    },
    {
        "id": "W39",
        "file": "RiskBadge",
        "desc": "RiskBadge: L2 bgVar revert to raw literal rgba(245, 158, 11, 0.15)",
        "target": "L2: {\n    label: 'L2',\n    description: '2인 승인 필요 (주의)',\n    icon: '⚠️',\n    colorVar: 'var(--color-risk-l2)',\n    bgVar: 'var(--color-bg-subtle)',\n  },",
        "replacement": "L2: {\n    label: 'L2',\n    description: '2인 승인 필요 (주의)',\n    icon: '⚠️',\n    colorVar: 'var(--color-risk-l2)',\n    bgVar: 'rgba(245, 158, 11, 0.15)',\n  },",
    },
    {
        "id": "W40",
        "file": "RiskBadge",
        "desc": "RiskBadge: L3 bgVar revert to raw literal rgba(239, 68, 68, 0.15)",
        "target": "L3: {\n    label: 'L3',\n    description: '기본 차단 (위험)',\n    icon: '🛑',\n    colorVar: 'var(--color-risk-l3)',\n    bgVar: 'var(--color-bg-subtle)',\n  },",
        "replacement": "L3: {\n    label: 'L3',\n    description: '기본 차단 (위험)',\n    icon: '🛑',\n    colorVar: 'var(--color-risk-l3)',\n    bgVar: 'rgba(239, 68, 68, 0.15)',\n  },",
    },
]


def apply_mutation(mutant):
    file_path = TARGET_FILES[mutant["file"]]
    content = file_path.read_text(encoding="utf-8")
    target = mutant["target"]
    replacement = mutant["replacement"]
    if target not in content:
        raise ValueError(f"Target pattern not found in {file_path}:\n{target[:100]}...")
    new_content = content.replace(target, replacement, 1)
    file_path.write_text(new_content, encoding="utf-8", newline="")


def restore_file(file_key: str, original_bytes: bytes):
    file_path = TARGET_FILES[file_key]
    file_path.write_bytes(original_bytes)
    current_bytes = file_path.read_bytes()
    if current_bytes != original_bytes:
        raise RuntimeError(
            f"Byte mismatch after restoration of {file_path}! Expected {len(original_bytes)} bytes, got {len(current_bytes)} bytes"
        )


def run_tsc_check():
    """Run npx tsc -b to ensure the mutant compiles."""
    local_tsc = APPS_WEB / "node_modules" / "typescript" / "bin" / "tsc"
    if local_tsc.exists():
        cmd = ["node", str(local_tsc), "-b"]
    else:
        cmd = [
            "npx.cmd" if os.name == "nt" else "npx",
            "tsc",
            "-b",
        ]
    try:
        proc = subprocess.run(
            cmd,
            cwd=str(APPS_WEB),
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
            encoding="utf-8",
            errors="replace",
            timeout=60,
        )
        return proc.returncode == 0, (proc.stdout or "") + (proc.stderr or "")
    except Exception as e:
        return False, str(e)


def run_vitest_acc09(timeout=120):
    """Run vitest on acc09-contrast-tokens.test.tsx."""
    cmd = [
        "npx.cmd" if os.name == "nt" else "npx",
        "vitest",
        "run",
        "tests/acc09-contrast-tokens.test.tsx",
    ]
    try:
        proc = subprocess.run(
            cmd,
            cwd=str(APPS_WEB),
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
            encoding="utf-8",
            errors="replace",
            timeout=timeout,
        )
        return proc.returncode, proc.stdout or "", proc.stderr or "", False
    except subprocess.TimeoutExpired as e:
        stdout = e.stdout.decode("utf-8", errors="replace") if isinstance(e.stdout, bytes) else (e.stdout or "")
        stderr = e.stderr.decode("utf-8", errors="replace") if isinstance(e.stderr, bytes) else (e.stderr or "")
        return -1, stdout, stderr, True


def test_mutant(mutant, original_bytes_map, timeout=120, head_sha=""):
    mutant_id = mutant["id"]
    file_key = mutant["file"]
    desc = mutant["desc"]
    observed_time = datetime.now(timezone.utc).isoformat()

    print(f"\n--- Testing Mutant {mutant_id} [{file_key}]: {desc} ---")
    try:
        apply_mutation(mutant)
    except Exception as e:
        print(f"  [ERROR] Failed to apply mutation: {e}")
        return {
            "id": mutant_id,
            "desc": desc,
            "status": "ERROR",
            "reason": str(e),
            "killed": False,
            "sourceHeadSha": head_sha,
            "observedAt": observed_time,
        }

    # Verify compilation
    compiled_ok, tsc_out = run_tsc_check()
    if not compiled_ok:
        print(f"  [COMPILATION FAILED] Mutant does not compile under TypeScript!")
        restore_file(file_key, original_bytes_map[file_key])
        return {
            "id": mutant_id,
            "desc": desc,
            "status": "TSC_FAIL",
            "killed": False,
            "output": tsc_out[:300],
            "sourceHeadSha": head_sha,
            "observedAt": observed_time,
        }

    retcode, stdout, stderr, timed_out = run_vitest_acc09(timeout=timeout)
    restore_file(file_key, original_bytes_map[file_key])

    if timed_out:
        print(f"  [TIMEOUT] Execution timed out after {timeout}s (NOT counted as killed)")
        return {
            "id": mutant_id,
            "desc": desc,
            "status": "TIMEOUT",
            "killed": False,
            "sourceHeadSha": head_sha,
            "observedAt": observed_time,
        }

    if retcode != 0:
        failed_test = "acc09-contrast-tokens.test.tsx"
        for line in (stdout + stderr).splitlines():
            if "FAIL" in line or "AssertionError" in line:
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
    parser = argparse.ArgumentParser(description="Test Card 273 mutations across shared and minor UI components")
    parser.add_argument("--batch", type=int, choices=[1, 2, 3, 4, 5], help="Run specific batch (1-5, 8 per batch)")
    parser.add_argument("--mutant", type=str, help="Run single mutant by ID (e.g. W1)")
    parser.add_argument("--all", action="store_true", help="Run all 40 mutants sequentially")
    parser.add_argument("--verify-targets", action="store_true", help="Verify all targets exist in files")
    parser.add_argument("--timeout", type=int, default=120, help="Per-mutant vitest timeout in seconds")
    args = parser.parse_args()

    original_bytes_map = {k: v.read_bytes() for k, v in TARGET_FILES.items()}

    if args.verify_targets:
        print("Verifying all mutation targets exist in target files...")
        missing = 0
        for m in MUTANTS:
            content = original_bytes_map[m["file"]].decode("utf-8")
            if m["target"] not in content:
                print(f"  [MISSING] {m['id']} in {m['file']}: {m['desc']}")
                missing += 1
            else:
                print(f"  [FOUND] {m['id']} in {m['file']}")
        if missing == 0:
            print(f"All {len(MUTANTS)} mutant targets verified!")
            return 0
        else:
            print(f"ERROR: {missing} mutant targets missing!")
            return 1

    try:
        head_sha = subprocess.check_output(["git", "rev-parse", "HEAD"], text=True).strip()
    except Exception:
        head_sha = "unknown"

    selected_mutants = []
    if args.mutant:
        selected_mutants = [m for m in MUTANTS if m["id"] == args.mutant]
        if not selected_mutants:
            print(f"Unknown mutant: {args.mutant}")
            return 1
    elif args.batch:
        start_idx = (args.batch - 1) * 8
        end_idx = start_idx + 8
        selected_mutants = MUTANTS[start_idx:end_idx]
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

    # If updating full results
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
