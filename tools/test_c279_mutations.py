#!/usr/bin/env python3
"""
tools/test_c279_mutations.py:
Verification runner for 40 accessibility, contrast, contract, and fail-closed mutants (M1-M40)
targeting Card 279:
  - apps/web/src/features/desktop/TerminalSessionView.tsx (M1-M40)

Requirements:
- Each mutant MUST compile cleanly under TypeScript (npx tsc -b).
- Each mutant MUST be killed by vitest run tests/acc09-contrast-tokens.test.tsx with timeout=120s.
- If timeout, record as TIMEOUT (do not count as killed).
- Restore original code after each mutant using binary read_bytes/write_bytes and verify git status byte-clean.
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
RESULTS_FILE = WORKTREE_ROOT / "tools" / ".c279_mutation_results.json"

TARGET_FILE = APPS_WEB / "src" / "features" / "desktop" / "TerminalSessionView.tsx"

MUTANTS = [
    # M1-M8: TERMINAL_SHELL_CONFIG
    {
        "id": "M1",
        "desc": "powershell color subtle collision: color: 'var(--color-bg-subtle)'",
        "target": "  powershell: {\n    color: 'var(--color-brand-hover)',",
        "replacement": "  powershell: {\n    color: 'var(--color-bg-subtle)',",
    },
    {
        "id": "M2",
        "desc": "powershell color literal regression: color: '#38bdf8'",
        "target": "  powershell: {\n    color: 'var(--color-brand-hover)',\n    label: 'POWERSHELL',",
        "replacement": "  powershell: {\n    color: '#38bdf8',\n    label: 'POWERSHELL',",
    },
    {
        "id": "M3",
        "desc": "bash color subtle collision: color: 'var(--color-bg-subtle)'",
        "target": "  bash: {\n    color: 'var(--color-status-online)',",
        "replacement": "  bash: {\n    color: 'var(--color-bg-subtle)',",
    },
    {
        "id": "M4",
        "desc": "bash color literal regression: color: '#4ade80'",
        "target": "  bash: {\n    color: 'var(--color-status-online)',\n    label: 'BASH',",
        "replacement": "  bash: {\n    color: '#4ade80',\n    label: 'BASH',",
    },
    {
        "id": "M5",
        "desc": "zsh color subtle collision: color: 'var(--color-bg-subtle)'",
        "target": "  zsh: {\n    color: 'var(--color-brand-hover)',",
        "replacement": "  zsh: {\n    color: 'var(--color-bg-subtle)',",
    },
    {
        "id": "M6",
        "desc": "zsh color literal regression: color: '#fbbf24'",
        "target": "  zsh: {\n    color: 'var(--color-brand-hover)',\n    label: 'ZSH',",
        "replacement": "  zsh: {\n    color: '#fbbf24',\n    label: 'ZSH',",
    },
    {
        "id": "M7",
        "desc": "cmd color subtle collision: color: 'var(--color-bg-subtle)'",
        "target": "  cmd: {\n    color: 'var(--color-text-primary)',",
        "replacement": "  cmd: {\n    color: 'var(--color-bg-subtle)',",
    },
    {
        "id": "M8",
        "desc": "cmd color literal regression: color: '#94a3b8'",
        "target": "  cmd: {\n    color: 'var(--color-text-primary)',\n    label: 'CMD',",
        "replacement": "  cmd: {\n    color: '#94a3b8',\n    label: 'CMD',",
    },
    {
        "id": "M9",
        "desc": "getTerminalShellConfig Object.hasOwn own-property guard suppression",
        "target": "  if (typeof shellType === 'string' && Object.hasOwn(TERMINAL_SHELL_CONFIG, shellType)) {",
        "replacement": "  if (typeof shellType === 'string' && shellType in TERMINAL_SHELL_CONFIG) {",
    },
    {
        "id": "M10",
        "desc": "getTerminalShellConfig fallback label UNKNOWN indicator stripping regression",
        "target": "  return {\n    color: 'var(--color-status-unknown)',\n    label: typeof shellType === 'string' && shellType.trim() ? `UNKNOWN (${shellType})` : 'UNKNOWN',",
        "replacement": "  return {\n    color: 'var(--color-status-unknown)',\n    label: typeof shellType === 'string' && shellType.trim() ? `${shellType}` : 'UNKNOWN',",
    },
    # M11-M16: PTY_AUTH_STATUS_CONFIG
    {
        "id": "M11",
        "desc": "ticket_bound color subtle collision: color: 'var(--color-bg-subtle)'",
        "target": "  ticket_bound: {\n    color: 'var(--color-status-degraded)',",
        "replacement": "  ticket_bound: {\n    color: 'var(--color-bg-subtle)',",
    },
    {
        "id": "M12",
        "desc": "ticket_bound color literal regression: color: '#f59e0b'",
        "target": "  ticket_bound: {\n    color: 'var(--color-status-degraded)',\n    label: '30초 암호학적 1회용 PTY 티켓 인증 연동 (mTLS 격리)',",
        "replacement": "  ticket_bound: {\n    color: '#f59e0b',\n    label: '30초 암호학적 1회용 PTY 티켓 인증 연동 (mTLS 격리)',",
    },
    {
        "id": "M13",
        "desc": "awaiting_command color subtle collision: color: 'var(--color-bg-subtle)'",
        "target": "  awaiting_command: {\n    color: 'var(--color-text-muted)',",
        "replacement": "  awaiting_command: {\n    color: 'var(--color-bg-subtle)',",
    },
    {
        "id": "M14",
        "desc": "awaiting_command color literal regression: color: '#64748b'",
        "target": "  awaiting_command: {\n    color: 'var(--color-text-muted)',\n    label: '승인 명령 ID 대기 중 (인증 대기 · mTLS)',",
        "replacement": "  awaiting_command: {\n    color: '#64748b',\n    label: '승인 명령 ID 대기 중 (인증 대기 · mTLS)',",
    },
    {
        "id": "M15",
        "desc": "getPtyAuthStatusConfig Object.hasOwn own-property guard suppression",
        "target": "  if (typeof status === 'string' && Object.hasOwn(PTY_AUTH_STATUS_CONFIG, status)) {",
        "replacement": "  if (typeof status === 'string' && status in PTY_AUTH_STATUS_CONFIG) {",
    },
    {
        "id": "M16",
        "desc": "derivePtyAuthStatus inversion: return awaiting_command when commandId present",
        "target": "export function derivePtyAuthStatus(commandId?: string | null): UiPtyAuthProjectionStatus {\n  return commandId && commandId.trim() ? 'ticket_bound' : 'awaiting_command';",
        "replacement": "export function derivePtyAuthStatus(commandId?: string | null): UiPtyAuthProjectionStatus {\n  return commandId && commandId.trim() ? 'awaiting_command' : 'ticket_bound';",
    },
    # M17-M23: Empty nodes notice
    {
        "id": "M17",
        "desc": "Empty nodes container bg collision: backgroundColor: 'var(--color-bg-canvas)'",
        "target": "          backgroundColor: 'var(--color-bg-surface)',\n          color: 'var(--color-text-primary)',\n        }}\n      >\n        <div\n          id=\"terminal-empty-nodes-notice\"",
        "replacement": "          backgroundColor: 'var(--color-bg-canvas)',\n          color: 'var(--color-text-primary)',\n        }}\n      >\n        <div\n          id=\"terminal-empty-nodes-notice\"",
    },
    {
        "id": "M18",
        "desc": "Empty nodes banner bg collision: backgroundColor: 'var(--color-bg-surface)'",
        "target": "          style={{\n            padding: '16px',\n            backgroundColor: 'var(--color-bg-subtle)',\n            color: 'var(--color-text-muted)',",
        "replacement": "          style={{\n            padding: '16px',\n            backgroundColor: 'var(--color-bg-surface)',\n            color: 'var(--color-text-muted)',",
    },
    {
        "id": "M19",
        "desc": "Empty nodes banner borderBottom collision: borderBottom: '1px solid var(--color-bg-subtle)'",
        "target": "            color: 'var(--color-text-muted)',\n            fontSize: '0.875rem',\n            borderBottom: '1px solid var(--color-border-subtle)',",
        "replacement": "            color: 'var(--color-text-muted)',\n            fontSize: '0.875rem',\n            borderBottom: '1px solid var(--color-bg-subtle)',",
    },
    {
        "id": "M20",
        "desc": "Empty nodes banner borderBottom literal: borderBottom: '1px solid #334155'",
        "target": "            borderBottom: '1px solid var(--color-border-subtle)',\n            display: 'flex',\n            alignItems: 'center',",
        "replacement": "            borderBottom: '1px solid #334155',\n            display: 'flex',\n            alignItems: 'center',",
    },
    {
        "id": "M21",
        "desc": "Empty nodes banner degraded text color collision: color: 'var(--color-bg-subtle)'",
        "target": "            <span style={{ marginLeft: '8px', color: 'var(--color-status-degraded)', fontSize: '0.8125rem' }}>",
        "replacement": "            <span style={{ marginLeft: '8px', color: 'var(--color-bg-subtle)', fontSize: '0.8125rem' }}>",
    },
    {
        "id": "M22",
        "desc": "Empty nodes banner degraded literal regression: color: '#fed7aa'",
        "target": "            <span style={{ marginLeft: '8px', color: 'var(--color-status-degraded)', fontSize: '0.8125rem' }}>\n              🛠️ <strong>[운영자 조치 필요]</strong>",
        "replacement": "            <span style={{ marginLeft: '8px', color: '#fed7aa', fontSize: '0.8125rem' }}>\n              🛠️ <strong>[운영자 조치 필요]</strong>",
    },
    {
        "id": "M23",
        "desc": "Empty nodes text color collision: color: 'var(--color-bg-subtle)'",
        "target": "          style={{\n            padding: '16px',\n            backgroundColor: 'var(--color-bg-subtle)',\n            color: 'var(--color-text-muted)',\n            fontSize: '0.875rem',",
        "replacement": "          style={{\n            padding: '16px',\n            backgroundColor: 'var(--color-bg-subtle)',\n            color: 'var(--color-bg-subtle)',\n            fontSize: '0.875rem',",
    },
    # M24-M32: Tab bar / Header
    {
        "id": "M24",
        "desc": "Active session view container bg collision: backgroundColor: 'var(--color-bg-canvas)'",
        "target": "      data-testid=\"terminal-session-view-container\"\n      style={{\n        display: 'flex',\n        flexDirection: 'column',\n        height: '100%',\n        backgroundColor: 'var(--color-bg-surface)',",
        "replacement": "      data-testid=\"terminal-session-view-container\"\n      style={{\n        display: 'flex',\n        flexDirection: 'column',\n        height: '100%',\n        backgroundColor: 'var(--color-bg-canvas)',",
    },
    {
        "id": "M25",
        "desc": "Tablist container bg collision: backgroundColor: 'var(--color-bg-surface)'",
        "target": "          justifyContent: 'space-between',\n          backgroundColor: 'var(--color-bg-subtle)',\n          borderBottom: '1px solid var(--color-border-subtle)',",
        "replacement": "          justifyContent: 'space-between',\n          backgroundColor: 'var(--color-bg-surface)',\n          borderBottom: '1px solid var(--color-border-subtle)',",
    },
    {
        "id": "M26",
        "desc": "Tablist borderBottom collision: borderBottom: '1px solid var(--color-bg-subtle)'",
        "target": "          backgroundColor: 'var(--color-bg-subtle)',\n          borderBottom: '1px solid var(--color-border-subtle)',\n          padding: '0 12px',",
        "replacement": "          backgroundColor: 'var(--color-bg-subtle)',\n          borderBottom: '1px solid var(--color-bg-subtle)',\n          padding: '0 12px',",
    },
    {
        "id": "M27",
        "desc": "Active tab bg collision: backgroundColor: isActive ? 'var(--color-bg-subtle)' : 'transparent'",
        "target": "                  backgroundColor: isActive ? 'var(--color-bg-surface)' : 'transparent',",
        "replacement": "                  backgroundColor: isActive ? 'var(--color-bg-subtle)' : 'transparent',",
    },
    {
        "id": "M28",
        "desc": "Active tab borderTop brand collision: borderTop: isActive ? '2px solid var(--color-bg-surface)'",
        "target": "                  borderTop: isActive ? '2px solid var(--color-brand-primary)' : '2px solid transparent',",
        "replacement": "                  borderTop: isActive ? '2px solid var(--color-bg-surface)' : '2px solid transparent',",
    },
    {
        "id": "M29",
        "desc": "Active tab text color collision: color: isActive ? 'var(--color-bg-surface)' : 'var(--color-text-muted)'",
        "target": "                  color: isActive ? 'var(--color-text-primary)' : 'var(--color-text-muted)',\n                  fontSize: '0.8125rem',",
        "replacement": "                  color: isActive ? 'var(--color-bg-surface)' : 'var(--color-text-muted)',\n                  fontSize: '0.8125rem',",
    },
    {
        "id": "M30",
        "desc": "Active tab text color literal regression: color: isActive ? '#f8fafc' : 'var(--color-text-muted)'",
        "target": "                  borderRight: '1px solid var(--color-border-subtle)',\n                  color: isActive ? 'var(--color-text-primary)' : 'var(--color-text-muted)',\n                  fontSize: '0.8125rem',",
        "replacement": "                  borderRight: '1px solid var(--color-border-subtle)',\n                  color: isActive ? '#f8fafc' : 'var(--color-text-muted)',\n                  fontSize: '0.8125rem',",
    },
    {
        "id": "M31",
        "desc": "Inactive tab text color collision: color: isActive ? 'var(--color-text-primary)' : 'var(--color-bg-subtle)'",
        "target": "                  borderRight: '1px solid var(--color-border-subtle)',\n                  color: isActive ? 'var(--color-text-primary)' : 'var(--color-text-muted)',\n                  fontSize: '0.8125rem',",
        "replacement": "                  borderRight: '1px solid var(--color-border-subtle)',\n                  color: isActive ? 'var(--color-text-primary)' : 'var(--color-bg-subtle)',\n                  fontSize: '0.8125rem',",
    },
    {
        "id": "M32",
        "desc": "Tab close button color collision: color: 'var(--color-bg-surface)'",
        "target": "                      border: 'none',\n                      color: 'var(--color-text-muted)',\n                      cursor: 'pointer',",
        "replacement": "                      border: 'none',\n                      color: 'var(--color-bg-surface)',\n                      cursor: 'pointer',",
    },
    # M33-M35: New session select
    {
        "id": "M33",
        "desc": "New session select bg collision: backgroundColor: 'var(--color-bg-canvas)'",
        "target": "              borderRadius: '4px',\n              backgroundColor: 'var(--color-bg-surface)',\n              color: 'inherit',",
        "replacement": "              borderRadius: '4px',\n              backgroundColor: 'var(--color-bg-canvas)',\n              color: 'inherit',",
    },
    {
        "id": "M34",
        "desc": "New session select border collision: border: '1px solid var(--color-bg-surface)'",
        "target": "              color: 'inherit',\n              border: '1px solid var(--color-border-strong)',",
        "replacement": "              color: 'inherit',\n              border: '1px solid var(--color-bg-surface)',",
    },
    {
        "id": "M35",
        "desc": "New session select border literal regression: border: '1px solid #334155'",
        "target": "              backgroundColor: 'var(--color-bg-surface)',\n              color: 'inherit',\n              border: '1px solid var(--color-border-strong)',",
        "replacement": "              backgroundColor: 'var(--color-bg-surface)',\n              color: 'inherit',\n              border: '1px solid #334155',",
    },
    # M36-M38: Observation node error alert
    {
        "id": "M36",
        "desc": "Error alert bg collision: backgroundColor: 'var(--color-bg-surface)'",
        "target": "            padding: '8px 16px',\n            backgroundColor: 'var(--color-risk-l3-bg)',\n            color: 'var(--color-risk-l3-text)',",
        "replacement": "            padding: '8px 16px',\n            backgroundColor: 'var(--color-bg-surface)',\n            color: 'var(--color-risk-l3-text)',",
    },
    {
        "id": "M37",
        "desc": "Error alert text color collision: color: 'var(--color-bg-surface)'",
        "target": "            backgroundColor: 'var(--color-risk-l3-bg)',\n            color: 'var(--color-risk-l3-text)',\n            fontSize: '0.8125rem',",
        "replacement": "            backgroundColor: 'var(--color-risk-l3-bg)',\n            color: 'var(--color-bg-surface)',\n            fontSize: '0.8125rem',",
    },
    {
        "id": "M38",
        "desc": "Error alert borderBottom collision: borderBottom: '1px solid var(--color-bg-surface)'",
        "target": "            fontSize: '0.8125rem',\n            borderBottom: '1px solid var(--color-risk-l3-border)',\n            display: 'flex',",
        "replacement": "            fontSize: '0.8125rem',\n            borderBottom: '1px solid var(--color-bg-surface)',\n            display: 'flex',",
    },
    # M39-M40: Switch mode button
    {
        "id": "M39",
        "desc": "Switch mode button bg collision: backgroundColor: 'var(--color-bg-subtle)'",
        "target": "              borderRadius: '4px',\n              backgroundColor: 'var(--color-brand-subtle)',\n              border: '1px solid var(--color-brand-primary)',",
        "replacement": "              borderRadius: '4px',\n              backgroundColor: 'var(--color-bg-subtle)',\n              border: '1px solid var(--color-brand-primary)',",
    },
    {
        "id": "M40",
        "desc": "Switch mode button text color collision: color: 'var(--color-bg-subtle)'",
        "target": "              border: '1px solid var(--color-brand-primary)',\n              color: 'var(--color-brand-hover)',\n              fontSize: '0.6875rem',",
        "replacement": "              border: '1px solid var(--color-brand-primary)',\n              color: 'var(--color-bg-subtle)',\n              fontSize: '0.6875rem',",
    },
]

def check_clean_tree():
    """Ensure tracked files in working directory are strictly clean."""
    res = subprocess.run(
        ["git", "status", "--porcelain", "--untracked-files=no"],
        cwd=WORKTREE_ROOT,
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace"
    )
    if res.stdout.strip():
        print(f"FATAL: Working tree is dirty before/after mutant execution:\n{res.stdout}")
        sys.exit(1)

def apply_mutant(mutant):
    content_bytes = TARGET_FILE.read_bytes()
    content_str = content_bytes.decode("utf-8")
    target = mutant["target"]
    replacement = mutant["replacement"]

    if target not in content_str:
        raise ValueError(f"Target pattern not found for {mutant['id']}:\n{target}")

    count = content_str.count(target)
    if count != 1:
        raise ValueError(f"Target pattern found {count} times (expected exactly 1) for {mutant['id']}")

    new_content_str = content_str.replace(target, replacement, 1)
    new_content_bytes = new_content_str.encode("utf-8")
    TARGET_FILE.write_bytes(new_content_bytes)

def run_test(mutant):
    original_bytes = TARGET_FILE.read_bytes()
    try:
        apply_mutant(mutant)

        # 1. Typecheck: must pass cleanly (or fail if AST/syntax error)
        npx_cmd = "npx.cmd" if sys.platform == "win32" else "npx"
        tsc_res = subprocess.run(
            [npx_cmd, "tsc", "-b"],
            cwd=APPS_WEB,
            capture_output=True,
            text=True,
            encoding="utf-8",
            errors="replace",
            timeout=120
        )
        if tsc_res.returncode != 0:
            return {"status": "TSC_FAIL", "output": tsc_res.stderr or tsc_res.stdout}

        # 2. Vitest: mutant MUST be killed by test suite
        vitest_res = subprocess.run(
            [npx_cmd, "vitest", "run", "tests/acc09-contrast-tokens.test.tsx"],
            cwd=APPS_WEB,
            capture_output=True,
            text=True,
            encoding="utf-8",
            errors="replace",
            timeout=120
        )

        if vitest_res.returncode != 0:
            return {"status": "KILLED", "output": vitest_res.stdout}
        else:
            return {"status": "SURVIVED", "output": vitest_res.stdout}

    except subprocess.TimeoutExpired:
        return {"status": "TIMEOUT", "output": "Subprocess timed out after 120s"}
    finally:
        TARGET_FILE.write_bytes(original_bytes)
        check_clean_tree()

def main():
    parser = argparse.ArgumentParser(description="Run mutation tests for Card 279 (TerminalSessionView)")
    parser.add_argument("--verify-targets", action="store_true", help="Verify all mutant targets match uniquely")
    parser.add_argument("--mutant", type=str, help="Run a specific mutant by ID (e.g. M1)")
    parser.add_argument("--all", action="store_true", help="Run all 40 mutants and seal results to JSON")
    args = parser.parse_args()

    check_clean_tree()

    head_sha = subprocess.run(
        ["git", "rev-parse", "HEAD"],
        cwd=WORKTREE_ROOT,
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace"
    ).stdout.strip()

    if args.verify_targets:
        print(f"Verifying target patterns for {len(MUTANTS)} mutants...")
        content_str = TARGET_FILE.read_bytes().decode("utf-8")
        all_ok = True
        for m in MUTANTS:
            target = m["target"]
            cnt = content_str.count(target)
            if cnt != 1:
                print(f"ERROR: {m['id']} target matched {cnt} times (expected 1)")
                all_ok = False
            else:
                print(f"OK: {m['id']} uniquely matched")
        if all_ok:
            print("All 40 mutant targets verified successfully!")
            sys.exit(0)
        else:
            sys.exit(1)

    if args.mutant:
        m = next((x for x in MUTANTS if x["id"] == args.mutant), None)
        if not m:
            print(f"Mutant {args.mutant} not found")
            sys.exit(1)
        print(f"Testing {m['id']}: {m['desc']} ...")
        res = run_test(m)
        print(f"Result: {res['status']}")
        return

    if args.all:
        print("Verifying clean baseline tests before mutation run...")
        npx_cmd = "npx.cmd" if sys.platform == "win32" else "npx"
        clean_tsc = subprocess.run([npx_cmd, "tsc", "-b"], cwd=APPS_WEB, capture_output=True, text=True, encoding="utf-8", errors="replace")
        if clean_tsc.returncode != 0:
            print(f"FATAL: Clean baseline tsc failed:\n{clean_tsc.stdout}\n{clean_tsc.stderr}")
            sys.exit(1)
        clean_vitest = subprocess.run([npx_cmd, "vitest", "run", "tests/acc09-contrast-tokens.test.tsx"], cwd=APPS_WEB, capture_output=True, text=True, encoding="utf-8", errors="replace")
        if clean_vitest.returncode != 0:
            print(f"FATAL: Clean baseline vitest failed:\n{clean_vitest.stdout}\n{clean_vitest.stderr}")
            sys.exit(1)
        print("Clean baseline verified 100% PASS.\n")
        results = {
            "card": "CARD-279",
            "component": "TerminalSessionView",
            "sourceHeadSha": head_sha,
            "startedAt": datetime.now(timezone.utc).isoformat(),
            "mutants": [],
            "totalMutants": len(MUTANTS),
            "killed": 0,
            "survived": 0,
            "timeouts": 0,
            "tsc_fails": 0,
        }

        print(f"Starting mutation testing for {len(MUTANTS)} mutant(s) (head SHA: {head_sha})\n")
        for i, m in enumerate(MUTANTS, 1):
            print(f"=== Testing Mutant {m['id']}: {m['desc']} ===")
            res = run_test(m)
            status = res["status"]
            print(f"  [{status}]")
            record = {
                "id": m["id"],
                "desc": m["desc"],
                "status": status,
            }
            if status == "KILLED":
                results["killed"] += 1
            elif status == "SURVIVED":
                results["survived"] += 1
            elif status == "TIMEOUT":
                results["timeouts"] += 1
            elif status == "TSC_FAIL":
                results["tsc_fails"] += 1
            results["mutants"].append(record)

        results["completedAt"] = datetime.now(timezone.utc).isoformat()
        results["killRate"] = f"{(results['killed'] / len(MUTANTS)) * 100:.1f}%"

        with open(RESULTS_FILE, "w", encoding="utf-8") as f:
            json.dump(results, f, indent=2, ensure_ascii=False)

        print(f"\nSaved complete mutation results to {RESULTS_FILE}")
        print(f"Kill Rate: {results['killed']}/{len(MUTANTS)} ({results['killRate']})\n")

        if results["killed"] != len(MUTANTS):
            sys.exit(1)
        sys.exit(0)

    parser.print_help()

if __name__ == "__main__":
    main()
