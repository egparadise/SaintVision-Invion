#!/usr/bin/env python3
"""
tools/test_c278_mutations.py:
Verification runner for 40 accessibility, contrast, contract, and fail-closed mutants (M1-M40)
targeting Card 278:
  - apps/web/src/features/desktop/DesktopWindow.tsx (M1-M40)

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
RESULTS_FILE = WORKTREE_ROOT / "tools" / ".c278_mutation_results.json"

TARGET_FILE = APPS_WEB / "src" / "features" / "desktop" / "DesktopWindow.tsx"

MUTANTS = [
    {
        "id": "M1",
        "desc": "Maximized window bg collision: backgroundColor: 'var(--color-bg-canvas)'",
        "target": "              backgroundColor: 'var(--color-bg-surface)',\n              borderRadius: 0,",
        "replacement": "              backgroundColor: 'var(--color-bg-canvas)',\n              borderRadius: 0,",
    },
    {
        "id": "M2",
        "desc": "Maximized window border collision: border: '1px solid var(--color-bg-surface)'",
        "target": "              boxShadow: isActive ? 'var(--shadow-lg)' : 'var(--shadow-md)',\n              border: '1px solid var(--color-border-subtle)',",
        "replacement": "              boxShadow: isActive ? 'var(--shadow-lg)' : 'var(--shadow-md)',\n              border: '1px solid var(--color-bg-surface)',",
    },
    {
        "id": "M3",
        "desc": "Maximized window border literal regression: border: '1px solid #334155'",
        "target": "              border: '1px solid var(--color-border-subtle)',\n              overflow: 'hidden',",
        "replacement": "              border: '1px solid #334155',\n              overflow: 'hidden',",
    },
    {
        "id": "M4",
        "desc": "Maximized window shadow literal regression: 0 12px 36px rgba(0, 0, 0, 0.45)",
        "target": "              borderRadius: 0,\n              boxShadow: isActive ? 'var(--shadow-lg)' : 'var(--shadow-md)',",
        "replacement": "              borderRadius: 0,\n              boxShadow: isActive ? '0 12px 36px rgba(0, 0, 0, 0.45)' : 'var(--shadow-md)',",
    },
    {
        "id": "M5",
        "desc": "Floating window bg collision: backgroundColor: 'var(--color-bg-canvas)'",
        "target": "              backgroundColor: 'var(--color-bg-surface)',\n              borderRadius: 'var(--radius-lg, 12px)',",
        "replacement": "              backgroundColor: 'var(--color-bg-canvas)',\n              borderRadius: 'var(--radius-lg, 12px)',",
    },
    {
        "id": "M6",
        "desc": "Floating focused window border collision: border: '1px solid var(--color-bg-surface)'",
        "target": "                : 'var(--shadow-md)',\n              border: '1px solid var(--color-border-strong)',",
        "replacement": "                : 'var(--shadow-md)',\n              border: '1px solid var(--color-bg-surface)',",
    },
    {
        "id": "M7",
        "desc": "Floating focused window border literal regression: border: '1px solid #333'",
        "target": "              border: '1px solid var(--color-border-strong)',\n              overflow: 'hidden',",
        "replacement": "              border: '1px solid #333',\n              overflow: 'hidden',",
    },
    {
        "id": "M8",
        "desc": "Floating window brand ring outline regression: remove 0 0 0 1px var(--color-brand-primary)",
        "target": "              boxShadow: isActive\n                ? 'var(--shadow-lg), 0 0 0 1px var(--color-brand-primary)'\n                : 'var(--shadow-md)',",
        "replacement": "              boxShadow: isActive\n                ? 'var(--shadow-lg)'\n                : 'var(--shadow-md)',",
    },
    {
        "id": "M9",
        "desc": "Floating window shadow literal regression: 0 6px 20px rgba(0, 0, 0, 0.3)",
        "target": "              boxShadow: isActive\n                ? 'var(--shadow-lg), 0 0 0 1px var(--color-brand-primary)'\n                : 'var(--shadow-md)',\n              border: '1px solid var(--color-border-strong)',",
        "replacement": "              boxShadow: isActive\n                ? 'var(--shadow-lg), 0 0 0 1px var(--color-brand-primary)'\n                : '0 6px 20px rgba(0, 0, 0, 0.3)',\n              border: '1px solid var(--color-border-strong)',",
    },
    {
        "id": "M10",
        "desc": "Window dialog inline outline: none focus suppression",
        "target": "              position: 'absolute',\n              top: '36px', // below top menu bar",
        "replacement": "              outline: 'none',\n              position: 'absolute',\n              top: '36px', // below top menu bar",
    },
    {
        "id": "M11",
        "desc": "Titlebar active bg collision: backgroundColor: isActive ? 'var(--color-bg-surface)' : 'var(--color-bg-surface)'",
        "target": "          backgroundColor: isActive ? 'var(--color-bg-subtle)' : 'var(--color-bg-surface)',\n          borderBottom: '1px solid var(--color-border-subtle)',",
        "replacement": "          backgroundColor: isActive ? 'var(--color-bg-surface)' : 'var(--color-bg-surface)',\n          borderBottom: '1px solid var(--color-border-subtle)',",
    },
    {
        "id": "M12",
        "desc": "Titlebar active borderBottom collision: borderBottom: '1px solid var(--color-bg-subtle)'",
        "target": "          borderBottom: '1px solid var(--color-border-subtle)',\n          userSelect: 'none',",
        "replacement": "          borderBottom: '1px solid var(--color-bg-subtle)',\n          userSelect: 'none',",
    },
    {
        "id": "M13",
        "desc": "Titlebar active bg literal regression: #1e293b",
        "target": "          backgroundColor: isActive ? 'var(--color-bg-subtle)' : 'var(--color-bg-surface)',",
        "replacement": "          backgroundColor: isActive ? '#1e293b' : 'var(--color-bg-surface)',",
    },
    {
        "id": "M14",
        "desc": "Titlebar inactive bg literal regression: #0f172a",
        "target": "          backgroundColor: isActive ? 'var(--color-bg-subtle)' : 'var(--color-bg-surface)',",
        "replacement": "          backgroundColor: isActive ? 'var(--color-bg-subtle)' : '#0f172a',",
    },
    {
        "id": "M15",
        "desc": "Titlebar borderBottom literal regression: #334155",
        "target": "          borderBottom: '1px solid var(--color-border-subtle)',",
        "replacement": "          borderBottom: '1px solid #334155',",
    },
    {
        "id": "M16",
        "desc": "Title text active color collision: color: isActive ? 'var(--color-bg-subtle)' : 'var(--color-text-muted)'",
        "target": "            color: isActive ? 'var(--color-text-primary)' : 'var(--color-text-muted)',\n            letterSpacing: '0.02em',",
        "replacement": "            color: isActive ? 'var(--color-bg-subtle)' : 'var(--color-text-muted)',\n            letterSpacing: '0.02em',",
    },
    {
        "id": "M17",
        "desc": "Title text active literal regression: #f8fafc",
        "target": "            color: isActive ? 'var(--color-text-primary)' : 'var(--color-text-muted)',",
        "replacement": "            color: isActive ? '#f8fafc' : 'var(--color-text-muted)',",
    },
    {
        "id": "M18",
        "desc": "Title text inactive literal regression: #94a3b8",
        "target": "            color: isActive ? 'var(--color-text-primary)' : 'var(--color-text-muted)',",
        "replacement": "            color: isActive ? 'var(--color-text-primary)' : '#94a3b8',",
    },
    {
        "id": "M19",
        "desc": "Title text low-contrast text: color: 'var(--color-text-inverse)'",
        "target": "            color: isActive ? 'var(--color-text-primary)' : 'var(--color-text-muted)',",
        "replacement": "            color: 'var(--color-text-inverse)',",
    },
    {
        "id": "M20",
        "desc": "AppId text literal regression: color: 'var(--color-text-muted, #64748b)'",
        "target": "        <div style={{ display: 'flex', alignItems: 'center', gap: '6px', fontSize: '0.6875rem', color: 'var(--color-text-muted)' }}>",
        "replacement": "        <div style={{ display: 'flex', alignItems: 'center', gap: '6px', fontSize: '0.6875rem', color: 'var(--color-text-muted, #64748b)' }}>",
    },
    {
        "id": "M21",
        "desc": "AppId text color collision: color: 'var(--color-bg-surface)'",
        "target": "        <div style={{ display: 'flex', alignItems: 'center', gap: '6px', fontSize: '0.6875rem', color: 'var(--color-text-muted)' }}>",
        "replacement": "        <div style={{ display: 'flex', alignItems: 'center', gap: '6px', fontSize: '0.6875rem', color: 'var(--color-bg-surface)' }}>",
    },
    {
        "id": "M22",
        "desc": "AppId text low contrast: color: 'var(--color-text-inverse)'",
        "target": "        <div style={{ display: 'flex', alignItems: 'center', gap: '6px', fontSize: '0.6875rem', color: 'var(--color-text-muted)' }}>",
        "replacement": "        <div style={{ display: 'flex', alignItems: 'center', gap: '6px', fontSize: '0.6875rem', color: 'var(--color-text-inverse)' }}>",
    },
    {
        "id": "M23",
        "desc": "Traffic light close button literal regression: backgroundColor: '#ef4444'",
        "target": "              borderRadius: '50%',\n              backgroundColor: closeControl.color,",
        "replacement": "              borderRadius: '50%',\n              backgroundColor: '#ef4444',",
    },
    {
        "id": "M24",
        "desc": "Traffic light close button shadow literal regression: 0 1px 3px rgba(0,0,0,0.3)",
        "target": "              padding: 0,\n              boxShadow: 'var(--shadow-sm)',\n            }}\n          />\n          <button\n            type=\"button\"\n            title={minControl.label}",
        "replacement": "              padding: 0,\n              boxShadow: '0 1px 3px rgba(0,0,0,0.3)',\n            }}\n          />\n          <button\n            type=\"button\"\n            title={minControl.label}",
    },
    {
        "id": "M25",
        "desc": "Traffic light close button collision on active subtle: backgroundColor: 'var(--color-bg-subtle)'",
        "target": "              borderRadius: '50%',\n              backgroundColor: closeControl.color,\n              border: 'none',",
        "replacement": "              borderRadius: '50%',\n              backgroundColor: 'var(--color-bg-subtle)',\n              border: 'none',",
    },
    {
        "id": "M26",
        "desc": "Traffic light close button inline outline: none focus suppression",
        "target": "              backgroundColor: closeControl.color,\n              border: 'none',\n              cursor: 'pointer',",
        "replacement": "              backgroundColor: closeControl.color,\n              border: 'none',\n              outline: 'none',\n              cursor: 'pointer',",
    },
    {
        "id": "M27",
        "desc": "Traffic light minimize button literal regression: backgroundColor: '#f59e0b'",
        "target": "              borderRadius: '50%',\n              backgroundColor: minControl.color,",
        "replacement": "              borderRadius: '50%',\n              backgroundColor: '#f59e0b',",
    },
    {
        "id": "M28",
        "desc": "Traffic light minimize button shadow literal regression: 0 1px 3px rgba(0,0,0,0.3)",
        "target": "              padding: 0,\n              boxShadow: 'var(--shadow-sm)',\n            }}\n          />\n          <button\n            type=\"button\"\n            title={isMaximized",
        "replacement": "              padding: 0,\n              boxShadow: '0 1px 3px rgba(0,0,0,0.3)',\n            }}\n          />\n          <button\n            type=\"button\"\n            title={isMaximized",
    },
    {
        "id": "M29",
        "desc": "Traffic light minimize button collision on active subtle: backgroundColor: 'var(--color-bg-subtle)'",
        "target": "              borderRadius: '50%',\n              backgroundColor: minControl.color,\n              border: 'none',",
        "replacement": "              borderRadius: '50%',\n              backgroundColor: 'var(--color-bg-subtle)',\n              border: 'none',",
    },
    {
        "id": "M30",
        "desc": "Traffic light minimize button inline outline: none focus suppression",
        "target": "              backgroundColor: minControl.color,\n              border: 'none',\n              cursor: 'pointer',",
        "replacement": "              backgroundColor: minControl.color,\n              border: 'none',\n              outline: 'none',\n              cursor: 'pointer',",
    },
    {
        "id": "M31",
        "desc": "Traffic light maximize button literal regression: backgroundColor: '#10b981'",
        "target": "              borderRadius: '50%',\n              backgroundColor: maxControl.color,",
        "replacement": "              borderRadius: '50%',\n              backgroundColor: '#10b981',",
    },
    {
        "id": "M32",
        "desc": "Traffic light maximize button shadow literal regression: 0 1px 3px rgba(0,0,0,0.3)",
        "target": "              padding: 0,\n              boxShadow: 'var(--shadow-sm)',\n            }}\n          />\n        </div>",
        "replacement": "              padding: 0,\n              boxShadow: '0 1px 3px rgba(0,0,0,0.3)',\n            }}\n          />\n        </div>",
    },
    {
        "id": "M33",
        "desc": "Traffic light maximize button collision on active subtle: backgroundColor: 'var(--color-bg-subtle)'",
        "target": "              borderRadius: '50%',\n              backgroundColor: maxControl.color,\n              border: 'none',",
        "replacement": "              borderRadius: '50%',\n              backgroundColor: 'var(--color-bg-subtle)',\n              border: 'none',",
    },
    {
        "id": "M34",
        "desc": "WINDOW_CONTROL_CONFIG close bg token mutation: color: 'var(--color-brand-primary)'",
        "target": "  close: {\n    color: 'var(--color-status-offline)',\n    bg: 'var(--color-bg-subtle)',",
        "replacement": "  close: {\n    color: 'var(--color-brand-primary)',\n    bg: 'var(--color-bg-subtle)',",
    },
    {
        "id": "M35",
        "desc": "WINDOW_CONTROL_CONFIG minimize bg token mutation: color: 'var(--color-status-offline)'",
        "target": "  minimize: {\n    color: 'var(--color-status-degraded)',\n    bg: 'var(--color-bg-subtle)',",
        "replacement": "  minimize: {\n    color: 'var(--color-status-offline)',\n    bg: 'var(--color-bg-subtle)',",
    },
    {
        "id": "M36",
        "desc": "WINDOW_CONTROL_CONFIG maximize bg token mutation: color: 'var(--color-status-degraded)'",
        "target": "  maximize: {\n    color: 'var(--color-status-online)',\n    bg: 'var(--color-bg-subtle)',",
        "replacement": "  maximize: {\n    color: 'var(--color-status-degraded)',\n    bg: 'var(--color-bg-subtle)',",
    },
    {
        "id": "M37",
        "desc": "getWindowControlConfig prototype pollution fail-open: replace Object.hasOwn with in operator",
        "target": "export function getWindowControlConfig(action?: string | null): WindowControlStyle {\n  if (action && Object.hasOwn(WINDOW_CONTROL_CONFIG, action)) {",
        "replacement": "export function getWindowControlConfig(action?: string | null): WindowControlStyle {\n  if (action && (action in WINDOW_CONTROL_CONFIG)) {",
    },
    {
        "id": "M38",
        "desc": "getWindowControlConfig case-insensitive fail-open: add toLowerCase() lookup",
        "target": "  if (action && Object.hasOwn(WINDOW_CONTROL_CONFIG, action)) {\n    return WINDOW_CONTROL_CONFIG[action as WindowControlAction];\n  }",
        "replacement": "  if (action && (Object.hasOwn(WINDOW_CONTROL_CONFIG, action) || Object.hasOwn(WINDOW_CONTROL_CONFIG, action.toLowerCase()))) {\n    return WINDOW_CONTROL_CONFIG[(action.toLowerCase() in WINDOW_CONTROL_CONFIG ? action.toLowerCase() : action) as WindowControlAction];\n  }",
    },
    {
        "id": "M39",
        "desc": "getWindowControlConfig fallback color mutation: color: 'var(--color-status-online)'",
        "target": "  return {\n    color: 'var(--color-status-unknown)',\n    bg: 'var(--color-bg-subtle)',",
        "replacement": "  return {\n    color: 'var(--color-status-online)',\n    bg: 'var(--color-bg-subtle)',",
    },
    {
        "id": "M40",
        "desc": "getWindowControlConfig fallback label mutation: omit UNKNOWN prefix",
        "target": "    border: 'var(--color-status-unknown)',\n    label: action ? `UNKNOWN (${action})` : 'UNKNOWN',",
        "replacement": "    border: 'var(--color-status-unknown)',\n    label: action || 'UNKNOWN',",
    },
]

def check_clean_tree():
    status = subprocess.check_output(
        ["git", "status", "--porcelain", "--untracked-files=no"],
        cwd=WORKTREE_ROOT,
        text=True,
        encoding="utf-8",
        errors="replace"
    )
    tracked_changes = [line for line in status.splitlines() if line.strip() and not line.startswith("??")]
    if tracked_changes:
        raise RuntimeError(f"Worktree has uncommitted tracked changes:\n{chr(10).join(tracked_changes)}")

def get_head_sha():
    return subprocess.check_output(["git", "rev-parse", "HEAD"], cwd=WORKTREE_ROOT, text=True, encoding="utf-8", errors="replace").strip()

def run_test(mutant):
    orig_bytes = TARGET_FILE.read_bytes()
    orig_content = orig_bytes.decode('utf-8')
    target = mutant["target"]
    replacement = mutant["replacement"]

    if target not in orig_content:
        return {"status": "ERROR", "reason": "Target snippet not found in file"}
    if orig_content.count(target) > 1:
        return {"status": "ERROR", "reason": "Target snippet matched multiple times"}

    mutated_content = orig_content.replace(target, replacement)
    TARGET_FILE.write_bytes(mutated_content.encode('utf-8'))

    try:
        # 1. Compile check (tsc -b)
        tsc_cmd = ["npx.cmd" if sys.platform == "win32" else "npx", "tsc", "-b"]
        tsc_res = subprocess.run(tsc_cmd, cwd=APPS_WEB, capture_output=True, text=True, encoding="utf-8", errors="replace", timeout=60)
        if tsc_res.returncode != 0:
            return {"status": "TSC_FAIL", "output": tsc_res.stderr or tsc_res.stdout}

        # 2. Vitest run
        vitest_cmd = [
            "npx.cmd" if sys.platform == "win32" else "npx",
            "vitest",
            "run",
            "tests/acc09-contrast-tokens.test.tsx"
        ]
        test_res = subprocess.run(vitest_cmd, cwd=APPS_WEB, capture_output=True, text=True, encoding="utf-8", errors="replace", timeout=120)

        if test_res.returncode != 0:
            return {
                "status": "KILLED",
                "retcode": test_res.returncode,
                "stdout": test_res.stdout[-1500:] if test_res.stdout else "",
            }
        else:
            return {"status": "SURVIVED", "stdout": test_res.stdout[-1000:] if test_res.stdout else ""}
    except subprocess.TimeoutExpired:
        return {"status": "TIMEOUT"}
    finally:
        TARGET_FILE.write_bytes(orig_bytes)
        # Double check restoration byte equality
        restored_bytes = TARGET_FILE.read_bytes()
        if restored_bytes != orig_bytes:
            raise RuntimeError(f"Failed to restore original bytes of {TARGET_FILE}")
        # Fail-closed check: verify tracked tree is byte-clean
        git_st = subprocess.check_output(
            ["git", "status", "--porcelain", "--untracked-files=no"],
            cwd=WORKTREE_ROOT,
            text=True,
            encoding="utf-8",
            errors="replace"
        ).strip()
        if git_st:
            raise RuntimeError(f"Tracked tree is not clean after mutant restoration:\n{git_st}")

def main():
    parser = argparse.ArgumentParser(description="Run Card 278 mutation tests")
    parser.add_argument("--verify-targets", action="store_true", help="Verify all mutant targets exist uniquely")
    parser.add_argument("--mutant", type=str, help="Run single mutant by ID (e.g. M1)")
    parser.add_argument("--all", action="store_true", help="Run all 40 mutants and save results")
    parser.add_argument("--list", action="store_true", help="List all mutants")
    args = parser.parse_args()

    if args.list:
        for m in MUTANTS:
            print(f"{m['id']:4}: {m['desc']}")
        return

    if args.verify_targets:
        content = TARGET_FILE.read_bytes().decode('utf-8')
        errors = 0
        for m in MUTANTS:
            cnt = content.count(m["target"])
            if cnt != 1:
                print(f"FAIL {m['id']}: target matched {cnt} times!")
                errors += 1
            else:
                print(f"OK   {m['id']}: uniquely found")
        if errors > 0:
            print(f"Verification failed with {errors} errors")
            sys.exit(1)
        print("All 40 mutant targets verified uniquely!")
        return

    check_clean_tree()
    head_sha = get_head_sha()

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
            "card": "CARD-278",
            "component": "DesktopWindow",
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
