#!/usr/bin/env python3
"""
tools/test_c276_mutations.py:
Verification runner for 40 accessibility, contrast, contract, and fail-closed mutants (M1-M40)
targeting Card 276 components:
  - apps/web/src/features/approvals/ApprovalDetail.tsx (M1-M20)
  - apps/web/src/shared/ui/Header.tsx (M21-M40)

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
RESULTS_FILE = WORKTREE_ROOT / "tools" / ".c276_mutation_results.json"

TARGET_FILES = {
    "ApprovalDetail": APPS_WEB / "src" / "features" / "approvals" / "ApprovalDetail.tsx",
    "Header": APPS_WEB / "src" / "shared" / "ui" / "Header.tsx",
}

MUTANTS = [
    # Batch 1 (M1-M10): ApprovalDetail Bound Version & Rollback Risk Banner
    {
        "id": "M1",
        "file": "ApprovalDetail",
        "desc": "ApprovalDetail: Bound version badge color==bg 1:1 collision (color: var(--color-bg-surface))",
        "target": "                backgroundColor: 'var(--color-bg-surface)',\n                color: 'var(--color-brand-primary)',",
        "replacement": "                backgroundColor: 'var(--color-bg-surface)',\n                color: 'var(--color-bg-surface)',",
    },
    {
        "id": "M2",
        "file": "ApprovalDetail",
        "desc": "ApprovalDetail: Bound version badge border collision (border: 1px solid var(--color-bg-surface))",
        "target": "                color: 'var(--color-brand-primary)',\n                border: '1px solid var(--color-brand-primary)',",
        "replacement": "                color: 'var(--color-brand-primary)',\n                border: '1px solid var(--color-bg-surface)',",
    },
    {
        "id": "M3",
        "file": "ApprovalDetail",
        "desc": "ApprovalDetail: Bound version badge low contrast text mutation (color: var(--color-text-inverse))",
        "target": "                backgroundColor: 'var(--color-bg-surface)',\n                color: 'var(--color-brand-primary)',",
        "replacement": "                backgroundColor: 'var(--color-bg-surface)',\n                color: 'var(--color-text-inverse)',",
    },
    {
        "id": "M4",
        "file": "ApprovalDetail",
        "desc": "ApprovalDetail: Bound version badge inline outline:none focus suppression",
        "target": "                border: '1px solid var(--color-brand-primary)',\n              }}",
        "replacement": "                border: '1px solid var(--color-brand-primary)',\n                outline: 'none',\n              }}",
    },
    {
        "id": "M5",
        "file": "ApprovalDetail",
        "desc": "ApprovalDetail: Bound version badge color literal regression (#58a6ff)",
        "target": "                backgroundColor: 'var(--color-bg-surface)',\n                color: 'var(--color-brand-primary)',",
        "replacement": "                backgroundColor: 'var(--color-bg-surface)',\n                color: '#58a6ff',",
    },
    {
        "id": "M6",
        "file": "ApprovalDetail",
        "desc": "ApprovalDetail: Bound version badge bg literal regression (rgba(56, 139, 253, 0.15))",
        "target": "                backgroundColor: 'var(--color-bg-surface)',\n                color: 'var(--color-brand-primary)',",
        "replacement": "                backgroundColor: 'rgba(56, 139, 253, 0.15)',\n                color: 'var(--color-brand-primary)',",
    },
    {
        "id": "M7",
        "file": "ApprovalDetail",
        "desc": "ApprovalDetail: Rollback warning banner color==bg 1:1 collision (color: var(--color-risk-l3-bg))",
        "target": "              backgroundColor: 'var(--color-risk-l3-bg)',\n              border: '1px solid var(--color-risk-l3-border)',\n              borderRadius: 'var(--radius-md)',\n              color: 'var(--color-risk-l3-text)',",
        "replacement": "              backgroundColor: 'var(--color-risk-l3-bg)',\n              border: '1px solid var(--color-risk-l3-border)',\n              borderRadius: 'var(--radius-md)',\n              color: 'var(--color-risk-l3-bg)',",
    },
    {
        "id": "M8",
        "file": "ApprovalDetail",
        "desc": "ApprovalDetail: Rollback warning banner border collision (border: 1px solid var(--color-risk-l3-bg))",
        "target": "              backgroundColor: 'var(--color-risk-l3-bg)',\n              border: '1px solid var(--color-risk-l3-border)',",
        "replacement": "              backgroundColor: 'var(--color-risk-l3-bg)',\n              border: '1px solid var(--color-risk-l3-bg)',",
    },
    {
        "id": "M9",
        "file": "ApprovalDetail",
        "desc": "ApprovalDetail: Rollback warning banner low-contrast text mutation (color: var(--color-text-inverse))",
        "target": "              color: 'var(--color-risk-l3-text)',\n              fontSize: '0.875rem',",
        "replacement": "              color: 'var(--color-text-inverse)',\n              fontSize: '0.875rem',",
    },
    {
        "id": "M10",
        "file": "ApprovalDetail",
        "desc": "ApprovalDetail: Rollback warning banner bg literal regression (rgba(220, 38, 38, 0.1))",
        "target": "              backgroundColor: 'var(--color-risk-l3-bg)',\n              border: '1px solid var(--color-risk-l3-border)',",
        "replacement": "              backgroundColor: 'rgba(220, 38, 38, 0.1)',\n              border: '1px solid var(--color-risk-l3-border)',",
    },

    # Batch 2 (M11-M20): ApprovalDetail Rollback Border, Unified Diff, Backdrop & Outline
    {
        "id": "M11",
        "file": "ApprovalDetail",
        "desc": "ApprovalDetail: Rollback warning banner border literal regression (#dc2626)",
        "target": "              backgroundColor: 'var(--color-risk-l3-bg)',\n              border: '1px solid var(--color-risk-l3-border)',",
        "replacement": "              backgroundColor: 'var(--color-risk-l3-bg)',\n              border: '1px solid #dc2626',",
    },
    {
        "id": "M12",
        "file": "ApprovalDetail",
        "desc": "ApprovalDetail: Rollback warning banner inline outline:none focus suppression",
        "target": "              display: 'flex',\n              alignItems: 'center',\n              gap: '8px',\n            }}",
        "replacement": "              display: 'flex',\n              alignItems: 'center',\n              gap: '8px',\n              outline: 'none',\n            }}",
    },
    {
        "id": "M13",
        "file": "ApprovalDetail",
        "desc": "ApprovalDetail: Unified Diff <pre> color==bg 1:1 collision (color: var(--color-bg-canvas))",
        "target": "              backgroundColor: 'var(--color-bg-canvas)',\n              color: 'var(--color-text-primary)',",
        "replacement": "              backgroundColor: 'var(--color-bg-canvas)',\n              color: 'var(--color-bg-canvas)',",
    },
    {
        "id": "M14",
        "file": "ApprovalDetail",
        "desc": "ApprovalDetail: Unified Diff <pre> border collision (border: 1px solid var(--color-bg-canvas))",
        "target": "              border: isDiffLoadFailed ? '1px solid var(--color-status-offline)' : '1px solid var(--color-border-strong)',",
        "replacement": "              border: isDiffLoadFailed ? '1px solid var(--color-status-offline)' : '1px solid var(--color-bg-canvas)',",
    },
    {
        "id": "M15",
        "file": "ApprovalDetail",
        "desc": "ApprovalDetail: Unified Diff <pre> low-contrast text mutation (color: var(--color-text-inverse))",
        "target": "              backgroundColor: 'var(--color-bg-canvas)',\n              color: 'var(--color-text-primary)',",
        "replacement": "              backgroundColor: 'var(--color-bg-canvas)',\n              color: 'var(--color-text-inverse)',",
    },
    {
        "id": "M16",
        "file": "ApprovalDetail",
        "desc": "ApprovalDetail: Unified Diff <pre> bg literal regression (#0d1117)",
        "target": "              backgroundColor: 'var(--color-bg-canvas)',\n              color: 'var(--color-text-primary)',",
        "replacement": "              backgroundColor: '#0d1117',\n              color: 'var(--color-text-primary)',",
    },
    {
        "id": "M17",
        "file": "ApprovalDetail",
        "desc": "ApprovalDetail: Unified Diff <pre> border literal regression (#30363d)",
        "target": "              border: isDiffLoadFailed ? '1px solid var(--color-status-offline)' : '1px solid var(--color-border-strong)',",
        "replacement": "              border: isDiffLoadFailed ? '1px solid var(--color-status-offline)' : '1px solid #30363d',",
    },
    {
        "id": "M18",
        "file": "ApprovalDetail",
        "desc": "ApprovalDetail: Unified Diff <pre> text literal regression (#c9d1d9)",
        "target": "              backgroundColor: 'var(--color-bg-canvas)',\n              color: 'var(--color-text-primary)',",
        "replacement": "              backgroundColor: 'var(--color-bg-canvas)',\n              color: '#c9d1d9',",
    },
    {
        "id": "M19",
        "file": "ApprovalDetail",
        "desc": "ApprovalDetail: Unified Diff <pre> inline outline:none focus suppression",
        "target": "              border: isDiffLoadFailed ? '1px solid var(--color-status-offline)' : '1px solid var(--color-border-strong)',\n            }}",
        "replacement": "              border: isDiffLoadFailed ? '1px solid var(--color-status-offline)' : '1px solid var(--color-border-strong)',\n              outline: 'none',\n            }}",
    },
    {
        "id": "M20",
        "file": "ApprovalDetail",
        "desc": "ApprovalDetail: Reject modal backdrop literal regression (rgba(0, 0, 0, 0.5))",
        "target": "            position: 'fixed',\n            inset: 0,\n            backgroundColor: 'var(--color-bg-backdrop)',",
        "replacement": "            position: 'fixed',\n            inset: 0,\n            backgroundColor: 'rgba(0, 0, 0, 0.5)',",
    },

    # Batch 3 (M21-M30): Header Gateway, User Pill Container & User Name
    {
        "id": "M21",
        "file": "Header",
        "desc": "Header: Gateway offline indicator dot literal regression (#f85149)",
        "target": "              backgroundColor: gatewayStatus.online ? 'var(--color-status-online)' : 'var(--color-status-offline)',",
        "replacement": "              backgroundColor: gatewayStatus.online ? 'var(--color-status-online)' : '#f85149',",
    },
    {
        "id": "M22",
        "file": "Header",
        "desc": "Header: Gateway offline text literal regression (#f85149)",
        "target": "Gateway: {gatewayStatus.online ? <strong>{gatewayStatus.rttMs ?? 0}ms</strong> : <strong style={{ color: 'var(--color-status-offline)' }}>Offline</strong>}",
        "replacement": "Gateway: {gatewayStatus.online ? <strong>{gatewayStatus.rttMs ?? 0}ms</strong> : <strong style={{ color: '#f85149' }}>Offline</strong>}",
    },
    {
        "id": "M23",
        "file": "Header",
        "desc": "Header: Gateway offline text low-contrast text mutation (color: var(--color-text-inverse))",
        "target": "<strong style={{ color: 'var(--color-status-offline)' }}>Offline</strong>",
        "replacement": "<strong style={{ color: 'var(--color-text-inverse)' }}>Offline</strong>",
    },
    {
        "id": "M24",
        "file": "Header",
        "desc": "Header: Gateway offline text color==bg collision (color: var(--color-bg-subtle))",
        "target": "<strong style={{ color: 'var(--color-status-offline)' }}>Offline</strong>",
        "replacement": "<strong style={{ color: 'var(--color-bg-subtle)' }}>Offline</strong>",
    },
    {
        "id": "M25",
        "file": "Header",
        "desc": "Header: User pill container bg literal regression (rgba(56, 139, 253, 0.12))",
        "target": "              backgroundColor: 'var(--color-bg-subtle)',\n              border: '1px solid var(--color-border-strong)',",
        "replacement": "              backgroundColor: 'rgba(56, 139, 253, 0.12)',\n              border: '1px solid var(--color-border-strong)',",
    },
    {
        "id": "M26",
        "file": "Header",
        "desc": "Header: User pill container border literal regression (rgba(56, 139, 253, 0.3))",
        "target": "              backgroundColor: 'var(--color-bg-subtle)',\n              border: '1px solid var(--color-border-strong)',",
        "replacement": "              backgroundColor: 'var(--color-bg-subtle)',\n              border: '1px solid rgba(56, 139, 253, 0.3)',",
    },
    {
        "id": "M27",
        "file": "Header",
        "desc": "Header: User pill container border collision (border: 1px solid var(--color-bg-subtle))",
        "target": "              backgroundColor: 'var(--color-bg-subtle)',\n              border: '1px solid var(--color-border-strong)',",
        "replacement": "              backgroundColor: 'var(--color-bg-subtle)',\n              border: '1px solid var(--color-bg-subtle)',",
    },
    {
        "id": "M28",
        "file": "Header",
        "desc": "Header: User pill container inline outline:none focus suppression",
        "target": "              borderRadius: 'var(--radius-md)',\n              fontSize: '0.8125rem',\n            }}",
        "replacement": "              borderRadius: 'var(--radius-md)',\n              fontSize: '0.8125rem',\n              outline: 'none',\n            }}",
    },
    {
        "id": "M29",
        "file": "Header",
        "desc": "Header: User name text literal regression (#58a6ff)",
        "target": "            <span style={{ fontWeight: 600, color: 'var(--color-brand-primary)' }}>",
        "replacement": "            <span style={{ fontWeight: 600, color: '#58a6ff' }}>",
    },
    {
        "id": "M30",
        "file": "Header",
        "desc": "Header: User name color==bg 1:1 collision (color: var(--color-bg-subtle))",
        "target": "            <span style={{ fontWeight: 600, color: 'var(--color-brand-primary)' }}>",
        "replacement": "            <span style={{ fontWeight: 600, color: 'var(--color-bg-subtle)' }}>",
    },

    # Batch 4 (M31-M40): Header User Role Badge, Logout & Web Desktop Button
    {
        "id": "M31",
        "file": "Header",
        "desc": "Header: User name low-contrast text mutation (color: var(--color-text-inverse))",
        "target": "            <span style={{ fontWeight: 600, color: 'var(--color-brand-primary)' }}>",
        "replacement": "            <span style={{ fontWeight: 600, color: 'var(--color-text-inverse)' }}>",
    },
    {
        "id": "M32",
        "file": "Header",
        "desc": "Header: User role badge bg literal regression (rgba(56, 139, 253, 0.25))",
        "target": "                fontSize: '0.6875rem',\n                backgroundColor: 'var(--color-bg-surface)',",
        "replacement": "                fontSize: '0.6875rem',\n                backgroundColor: 'rgba(56, 139, 253, 0.25)',",
    },
    {
        "id": "M33",
        "file": "Header",
        "desc": "Header: User role badge text literal regression (#79c0ff)",
        "target": "                borderRadius: 'var(--radius-sm)',\n                color: 'var(--color-text-secondary)',",
        "replacement": "                borderRadius: 'var(--radius-sm)',\n                color: '#79c0ff',",
    },
    {
        "id": "M34",
        "file": "Header",
        "desc": "Header: User role badge color==bg 1:1 collision (color: var(--color-bg-surface))",
        "target": "                borderRadius: 'var(--radius-sm)',\n                color: 'var(--color-text-secondary)',",
        "replacement": "                borderRadius: 'var(--radius-sm)',\n                color: 'var(--color-bg-surface)',",
    },
    {
        "id": "M35",
        "file": "Header",
        "desc": "Header: User role badge low-contrast text mutation (color: var(--color-text-inverse))",
        "target": "                borderRadius: 'var(--radius-sm)',\n                color: 'var(--color-text-secondary)',",
        "replacement": "                borderRadius: 'var(--radius-sm)',\n                color: 'var(--color-text-inverse)',",
    },
    {
        "id": "M36",
        "file": "Header",
        "desc": "Header: Logout button text literal regression (#f85149)",
        "target": "              <Button variant=\"ghost\" size=\"sm\" onClick={onLogout} style={{ padding: '2px 6px', fontSize: '0.75rem', color: 'var(--color-status-offline)' }}>",
        "replacement": "              <Button variant=\"ghost\" size=\"sm\" onClick={onLogout} style={{ padding: '2px 6px', fontSize: '0.75rem', color: '#f85149' }}>",
    },
    {
        "id": "M37",
        "file": "Header",
        "desc": "Header: Logout button inline outline:none focus suppression",
        "target": "              <Button variant=\"ghost\" size=\"sm\" onClick={onLogout} style={{ padding: '2px 6px', fontSize: '0.75rem', color: 'var(--color-status-offline)' }}>",
        "replacement": "              <Button variant=\"ghost\" size=\"sm\" onClick={onLogout} style={{ padding: '2px 6px', fontSize: '0.75rem', color: 'var(--color-status-offline)', outline: 'none' }}>",
    },
    {
        "id": "M38",
        "file": "Header",
        "desc": "Header: Web Desktop button bg literal regression (rgba(59, 130, 246, 0.2))",
        "target": "              backgroundColor: 'var(--color-bg-subtle)',\n              border: '1px solid var(--color-brand-primary)',",
        "replacement": "              backgroundColor: 'rgba(59, 130, 246, 0.2)',\n              border: '1px solid var(--color-brand-primary)',",
    },
    {
        "id": "M39",
        "file": "Header",
        "desc": "Header: Web Desktop button border literal regression (rgba(59, 130, 246, 0.4))",
        "target": "              backgroundColor: 'var(--color-bg-subtle)',\n              border: '1px solid var(--color-brand-primary)',",
        "replacement": "              backgroundColor: 'var(--color-bg-subtle)',\n              border: '1px solid rgba(59, 130, 246, 0.4)',",
    },
    {
        "id": "M40",
        "file": "Header",
        "desc": "Header: Web Desktop button text literal regression (#60a5fa)",
        "target": "              border: '1px solid var(--color-brand-primary)',\n              color: 'var(--color-brand-primary)',",
        "replacement": "              border: '1px solid var(--color-brand-primary)',\n              color: '#60a5fa',",
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
    parser = argparse.ArgumentParser(description="Test Card 276 mutations across ApprovalDetail and Header components")
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
