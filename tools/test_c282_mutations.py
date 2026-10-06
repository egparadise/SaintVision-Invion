#!/usr/bin/env python3
"""
tools/test_c282_mutations.py:
Verification runner for 40 accessibility, contrast, contract, and fail-closed mutants (M1-M40)
targeting Card 282:
  - apps/web/src/features/terminal/WebTerminal.tsx (M1-M40)

Requirements:
- Each mutant MUST compile cleanly under TypeScript (npx tsc -b).
- Each mutant MUST be killed by vitest run tests/acc09-contrast-tokens.test.tsx with timeout=120s.
- Restore original code after each mutant using binary read_bytes/write_bytes and verify git status clean.
- Sequential execution only.
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
RESULTS_FILE = WORKTREE_ROOT / "tools" / ".c282_mutation_results.json"

TARGET_FILES = {
    "web_terminal": APPS_WEB / "src" / "features" / "terminal" / "WebTerminal.tsx",
}

MUTANTS = [
    {
        "id": "M1",
        "file": "web_terminal",
        "desc": "connected dotColor literal regression: dotColor: '#238636'",
        "target": "  connected: {\n    label: 'connected',\n    dotColor: 'var(--color-status-online)',",
        "replacement": "  connected: {\n    label: 'connected',\n    dotColor: '#238636',"
    },
    {
        "id": "M2",
        "file": "web_terminal",
        "desc": "connected promptColor literal regression: promptColor: '#58a6ff'",
        "target": "    textColor: 'var(--color-status-online)',\n    promptColor: 'var(--color-brand-primary)',",
        "replacement": "    textColor: 'var(--color-status-online)',\n    promptColor: '#58a6ff',"
    },
    {
        "id": "M3",
        "file": "web_terminal",
        "desc": "connected borderVar literal regression: borderVar: '#238636'",
        "target": "    promptColor: 'var(--color-brand-primary)',\n    borderVar: 'var(--color-status-online)',",
        "replacement": "    promptColor: 'var(--color-brand-primary)',\n    borderVar: '#238636',"
    },
    {
        "id": "M4",
        "file": "web_terminal",
        "desc": "connected bgVar subtle collision: bgVar: 'var(--color-bg-subtle)'",
        "target": "    borderVar: 'var(--color-status-online)',\n    bgVar: 'var(--color-diff-added-bg)',",
        "replacement": "    borderVar: 'var(--color-status-online)',\n    bgVar: 'var(--color-bg-subtle)',"
    },
    {
        "id": "M5",
        "file": "web_terminal",
        "desc": "connecting dotColor literal regression: dotColor: '#d29922'",
        "target": "  connecting: {\n    label: 'connecting',\n    dotColor: 'var(--color-status-degraded)',",
        "replacement": "  connecting: {\n    label: 'connecting',\n    dotColor: '#d29922',"
    },
    {
        "id": "M6",
        "file": "web_terminal",
        "desc": "connecting promptColor literal regression: promptColor: '#d29922'",
        "target": "    textColor: 'var(--color-status-degraded)',\n    promptColor: 'var(--color-status-degraded)',\n    borderVar: 'var(--color-status-degraded)',",
        "replacement": "    textColor: 'var(--color-status-degraded)',\n    promptColor: '#d29922',\n    borderVar: 'var(--color-status-degraded)',"
    },
    {
        "id": "M7",
        "file": "web_terminal",
        "desc": "connecting colorVar 1:1 collision with bgVar: colorVar: 'var(--color-bg-subtle)'",
        "target": "    dotColor: 'var(--color-status-degraded)',\n    colorVar: 'var(--color-status-degraded)',\n    textColor: 'var(--color-status-degraded)',",
        "replacement": "    dotColor: 'var(--color-status-degraded)',\n    colorVar: 'var(--color-bg-subtle)',\n    textColor: 'var(--color-bg-subtle)',"
    },
    {
        "id": "M8",
        "file": "web_terminal",
        "desc": "connecting borderVar literal regression: borderVar: '#ea580c'",
        "target": "    promptColor: 'var(--color-status-degraded)',\n    borderVar: 'var(--color-status-degraded)',\n    bgVar: 'var(--color-bg-subtle)',",
        "replacement": "    promptColor: 'var(--color-status-degraded)',\n    borderVar: '#ea580c',\n    bgVar: 'var(--color-bg-subtle)',"
    },
    {
        "id": "M9",
        "file": "web_terminal",
        "desc": "disconnected dotColor literal regression: dotColor: '#8b949e'",
        "target": "  disconnected: {\n    label: 'disconnected',\n    dotColor: 'var(--color-text-muted)',",
        "replacement": "  disconnected: {\n    label: 'disconnected',\n    dotColor: '#8b949e',"
    },
    {
        "id": "M10",
        "file": "web_terminal",
        "desc": "disconnected promptColor literal regression: promptColor: '#8b949e'",
        "target": "    textColor: 'var(--color-text-muted)',\n    promptColor: 'var(--color-text-muted)',\n    borderVar: 'var(--color-border-subtle)',",
        "replacement": "    textColor: 'var(--color-text-muted)',\n    promptColor: '#8b949e',\n    borderVar: 'var(--color-border-subtle)',"
    },
    {
        "id": "M11",
        "file": "web_terminal",
        "desc": "disconnected borderVar literal regression: borderVar: '#30363d'",
        "target": "    promptColor: 'var(--color-text-muted)',\n    borderVar: 'var(--color-border-subtle)',\n    bgVar: 'var(--color-bg-subtle)',",
        "replacement": "    promptColor: 'var(--color-text-muted)',\n    borderVar: '#30363d',\n    bgVar: 'var(--color-bg-subtle)',"
    },
    {
        "id": "M12",
        "file": "web_terminal",
        "desc": "error dotColor literal regression: dotColor: '#f85149'",
        "target": "  error: {\n    label: 'error',\n    dotColor: 'var(--color-status-offline)',",
        "replacement": "  error: {\n    label: 'error',\n    dotColor: '#f85149',"
    },
    {
        "id": "M13",
        "file": "web_terminal",
        "desc": "error promptColor literal regression: promptColor: '#f85149'",
        "target": "    textColor: 'var(--color-status-offline)',\n    promptColor: 'var(--color-status-offline)',\n    borderVar: 'var(--color-status-offline)',",
        "replacement": "    textColor: 'var(--color-status-offline)',\n    promptColor: '#f85149',\n    borderVar: 'var(--color-status-offline)',"
    },
    {
        "id": "M14",
        "file": "web_terminal",
        "desc": "error borderVar literal regression: borderVar: '#ef4444'",
        "target": "    promptColor: 'var(--color-status-offline)',\n    borderVar: 'var(--color-status-offline)',\n    bgVar: 'var(--color-risk-l3-bg)',",
        "replacement": "    promptColor: 'var(--color-status-offline)',\n    borderVar: '#ef4444',\n    bgVar: 'var(--color-risk-l3-bg)',"
    },
    {
        "id": "M15",
        "file": "web_terminal",
        "desc": "error bgVar literal regression: bgVar: '#7f1d1d'",
        "target": "    borderVar: 'var(--color-status-offline)',\n    bgVar: 'var(--color-risk-l3-bg)',\n  },",
        "replacement": "    borderVar: 'var(--color-status-offline)',\n    bgVar: '#7f1d1d',\n  },"
    },
    {
        "id": "M16",
        "file": "web_terminal",
        "desc": "prototype pollution breach: status in WEB_TERMINAL_CONNECTION_STATUS_CONFIG",
        "target": "Object.hasOwn(WEB_TERMINAL_CONNECTION_STATUS_CONFIG, status)",
        "replacement": "status in WEB_TERMINAL_CONNECTION_STATUS_CONFIG"
    },
    {
        "id": "M17",
        "file": "web_terminal",
        "desc": "fail-closed UNKNOWN label dropped: raw instead of UNKNOWN (raw)",
        "target": "label: raw ? `UNKNOWN (${raw})` : 'UNKNOWN',",
        "replacement": "label: raw ? `${raw}` : 'UNKNOWN',"
    },
    {
        "id": "M18",
        "file": "web_terminal",
        "desc": "fallback dotColor elevates to online: var(--color-status-online)",
        "target": "dotColor: 'var(--color-status-unknown)',",
        "replacement": "dotColor: 'var(--color-status-online)',"
    },
    {
        "id": "M19",
        "file": "web_terminal",
        "desc": "root container backgroundColor literal regression: '#0d1117'",
        "target": "backgroundColor: 'var(--color-bg-canvas)',\n        color: 'var(--color-text-primary)',",
        "replacement": "backgroundColor: '#0d1117',\n        color: 'var(--color-text-primary)',"
    },
    {
        "id": "M20",
        "file": "web_terminal",
        "desc": "root container color literal regression: '#c9d1d9'",
        "target": "color: 'var(--color-text-primary)',\n        borderRadius: 'var(--radius-lg)',",
        "replacement": "color: '#c9d1d9',\n        borderRadius: 'var(--radius-lg)',"
    },
    {
        "id": "M21",
        "file": "web_terminal",
        "desc": "root container border literal regression: '1px solid #30363d'",
        "target": "border: '1px solid var(--color-border-subtle)',",
        "replacement": "border: '1px solid #30363d',"
    },
    {
        "id": "M22",
        "file": "web_terminal",
        "desc": "title bar backgroundColor literal regression: '#161b22'",
        "target": "backgroundColor: 'var(--color-bg-surface)',\n          borderBottom: '1px solid var(--color-border-subtle)',",
        "replacement": "backgroundColor: '#161b22',\n          borderBottom: '1px solid var(--color-border-subtle)',"
    },
    {
        "id": "M23",
        "file": "web_terminal",
        "desc": "title bar borderBottom literal regression: '1px solid #30363d'",
        "target": "borderBottom: '1px solid var(--color-border-subtle)',\n          fontSize: '0.8125rem',",
        "replacement": "borderBottom: '1px solid #30363d',\n          fontSize: '0.8125rem',"
    },
    {
        "id": "M24",
        "file": "web_terminal",
        "desc": "session ID color literal regression: '#8b949e'",
        "target": "data-testid=\"terminal-session-id\"\n                    style={{ fontSize: '0.75rem', color: 'var(--color-text-muted)' }}",
        "replacement": "data-testid=\"terminal-session-id\"\n                    style={{ fontSize: '0.75rem', color: '#8b949e' }}"
    },
    {
        "id": "M25",
        "file": "web_terminal",
        "desc": "connection status color literal regression: '#8b949e'",
        "target": "data-testid=\"terminal-connection-status\"\n                    role=\"status\"\n                    aria-live=\"polite\"\n                    style={{\n                      fontSize: '0.75rem',\n                      display: 'inline-flex',\n                      alignItems: 'center',\n                      padding: '1px 6px',\n                      borderRadius: '4px',\n                      backgroundColor: statusConfig.bgVar,\n                      color: statusConfig.colorVar,",
        "replacement": "data-testid=\"terminal-connection-status\"\n                    role=\"status\"\n                    aria-live=\"polite\"\n                    style={{\n                      fontSize: '0.75rem',\n                      display: 'inline-flex',\n                      alignItems: 'center',\n                      padding: '1px 6px',\n                      borderRadius: '4px',\n                      backgroundColor: statusConfig.bgVar,\n                      color: '#8b949e',"
    },
    {
        "id": "M26",
        "file": "web_terminal",
        "desc": "toggle a11y button color literal regression: '#c9d1d9'",
        "target": "data-testid=\"terminal-toggle-a11y-btn\"\n            variant=\"ghost\"\n            size=\"sm\"\n            style={{ color: 'var(--color-text-primary)', fontSize: '0.75rem', padding: '2px 8px' }}",
        "replacement": "data-testid=\"terminal-toggle-a11y-btn\"\n            variant=\"ghost\"\n            size=\"sm\"\n            style={{ color: '#c9d1d9', fontSize: '0.75rem', padding: '2px 8px' }}"
    },
    {
        "id": "M27",
        "file": "web_terminal",
        "desc": "close button color literal regression: '#f85149'",
        "target": "data-testid=\"terminal-close-btn\"\n              variant=\"ghost\"\n              size=\"sm\"\n              style={{ color: 'var(--color-status-offline)', fontSize: '0.75rem', padding: '2px 8px' }}",
        "replacement": "data-testid=\"terminal-close-btn\"\n              variant=\"ghost\"\n              size=\"sm\"\n              style={{ color: '#f85149', fontSize: '0.75rem', padding: '2px 8px' }}"
    },
    {
        "id": "M28",
        "file": "web_terminal",
        "desc": "missing command notice backgroundColor literal regression: '#1c1917'",
        "target": "id=\"terminal-command-required-notice\"\n          role=\"alert\"\n          data-testid=\"terminal-command-required-notice\"\n          style={{\n            padding: '8px 16px',\n            backgroundColor: 'var(--color-bg-subtle)',",
        "replacement": "id=\"terminal-command-required-notice\"\n          role=\"alert\"\n          data-testid=\"terminal-command-required-notice\"\n          style={{\n            padding: '8px 16px',\n            backgroundColor: '#1c1917',"
    },
    {
        "id": "M29",
        "file": "web_terminal",
        "desc": "missing command notice color literal regression: '#fb923c'",
        "target": "backgroundColor: 'var(--color-bg-subtle)',\n            color: 'var(--color-status-degraded)',\n            fontSize: '0.8125rem',",
        "replacement": "backgroundColor: 'var(--color-bg-subtle)',\n            color: '#fb923c',\n            fontSize: '0.8125rem',"
    },
    {
        "id": "M30",
        "file": "web_terminal",
        "desc": "missing command notice borderBottom literal regression: '1px solid #ea580c'",
        "target": "fontSize: '0.8125rem',\n            borderBottom: '1px solid var(--color-status-degraded)',",
        "replacement": "fontSize: '0.8125rem',\n            borderBottom: '1px solid #ea580c',"
    },
    {
        "id": "M31",
        "file": "web_terminal",
        "desc": "missing command notice hint color literal regression: '#fed7aa'",
        "target": "<span style={{ fontSize: '0.75rem', color: 'var(--color-text-secondary)' }}>",
        "replacement": "<span style={{ fontSize: '0.75rem', color: '#fed7aa' }}>"
    },
    {
        "id": "M32",
        "file": "web_terminal",
        "desc": "error banner backgroundColor literal regression: '#7f1d1d'",
        "target": "role=\"alert\"\n          data-testid=\"terminal-error-alert\"\n          style={{\n            padding: '8px 16px',\n            backgroundColor: 'var(--color-risk-l3-bg)',",
        "replacement": "role=\"alert\"\n          data-testid=\"terminal-error-alert\"\n          style={{\n            padding: '8px 16px',\n            backgroundColor: '#7f1d1d',"
    },
    {
        "id": "M33",
        "file": "web_terminal",
        "desc": "error banner color literal regression: '#fecaca'",
        "target": "backgroundColor: 'var(--color-risk-l3-bg)',\n            color: 'var(--color-status-offline)',",
        "replacement": "backgroundColor: 'var(--color-risk-l3-bg)',\n            color: '#fecaca',"
    },
    {
        "id": "M34",
        "file": "web_terminal",
        "desc": "error banner borderBottom literal regression: '1px solid #ef4444'",
        "target": "color: 'var(--color-status-offline)',\n            fontSize: '0.8125rem',\n            borderBottom: '1px solid var(--color-risk-l3-border)',",
        "replacement": "color: 'var(--color-status-offline)',\n            fontSize: '0.8125rem',\n            borderBottom: '1px solid #ef4444',"
    },
    {
        "id": "M35",
        "file": "web_terminal",
        "desc": "retry button backgroundColor literal regression: '#ef4444'",
        "target": "backgroundColor: isAuthorizedCommandId(commandId) ? 'var(--color-status-offline-bg)' : 'var(--color-bg-subtle)',",
        "replacement": "backgroundColor: isAuthorizedCommandId(commandId) ? '#ef4444' : 'var(--color-bg-subtle)',"
    },
    {
        "id": "M36",
        "file": "web_terminal",
        "desc": "retry button color literal regression: '#fff'",
        "target": "color: isAuthorizedCommandId(commandId) ? 'var(--color-brand-primary-fg)' : 'var(--color-text-muted)',",
        "replacement": "color: isAuthorizedCommandId(commandId) ? '#fff' : 'var(--color-text-muted)',"
    },
    {
        "id": "M37",
        "file": "web_terminal",
        "desc": "disconnected alert banner backgroundColor literal regression: '#451a03'",
        "target": "role=\"alert\"\n          data-testid=\"terminal-disconnected-cmd-alert\"\n          style={{\n            padding: '6px 16px',\n            backgroundColor: 'var(--color-bg-subtle)',",
        "replacement": "role=\"alert\"\n          data-testid=\"terminal-disconnected-cmd-alert\"\n          style={{\n            padding: '6px 16px',\n            backgroundColor: '#451a03',"
    },
    {
        "id": "M38",
        "file": "web_terminal",
        "desc": "disconnected alert banner color literal regression: '#fde68a'",
        "target": "data-testid=\"terminal-disconnected-cmd-alert\"\n          style={{\n            padding: '6px 16px',\n            backgroundColor: 'var(--color-bg-subtle)',\n            color: 'var(--color-status-degraded)',",
        "replacement": "data-testid=\"terminal-disconnected-cmd-alert\"\n          style={{\n            padding: '6px 16px',\n            backgroundColor: 'var(--color-bg-subtle)',\n            color: '#fde68a',"
    },
    {
        "id": "M39",
        "file": "web_terminal",
        "desc": "retry button focus ring suppression: outline: 'none'",
        "target": "border: 'none',\n              borderRadius: '4px',",
        "replacement": "border: 'none',\n              outline: 'none',\n              borderRadius: '4px',"
    },
    {
        "id": "M40",
        "file": "web_terminal",
        "desc": "root container 1:1 color collision: bg and fg both text-primary",
        "target": "height: '520px',\n        backgroundColor: 'var(--color-bg-canvas)',\n        color: 'var(--color-text-primary)',",
        "replacement": "height: '520px',\n        backgroundColor: 'var(--color-text-primary)',\n        color: 'var(--color-text-primary)',"
    }
]


def get_clean_status():
    res = subprocess.run(
        ["git", "status", "--porcelain"],
        cwd=WORKTREE_ROOT,
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
    )
    # Ignore the results file itself
    lines = [line for line in res.stdout.splitlines() if not line.endswith(".c282_mutation_results.json")]
    return "\n".join(lines).strip()


def run_single_mutant(mutant, originals):
    mid = mutant["id"]
    target_path = TARGET_FILES[mutant["file"]]
    target_str = mutant["target"]
    replacement_str = mutant["replacement"]

    content = target_path.read_text(encoding="utf-8")
    if target_str not in content:
        return {
            "id": mid,
            "desc": mutant["desc"],
            "status": "target_not_found",
            "error": f"Target string not found in {target_path}",
        }

    # Apply mutation
    mutated_content = content.replace(target_str, replacement_str, 1)
    target_path.write_text(mutated_content, encoding="utf-8")

    tsc_ok = False
    killed = False
    error_msg = ""

    try:
        # 1. TypeScript compilation check: MUST succeed
        tsc_cmd = ["cmd", "/c", "npx", "tsc", "-b"] if os.name == "nt" else ["npx", "tsc", "-b"]
        tsc_res = subprocess.run(
            tsc_cmd,
            cwd=APPS_WEB,
            capture_output=True,
            text=True,
            encoding="utf-8",
            errors="replace",
            timeout=120,
        )
        if tsc_res.returncode != 0:
            return {
                "id": mid,
                "desc": mutant["desc"],
                "status": "tsc_failed",
                "error": f"TypeScript compilation failed:\n{tsc_res.stderr or tsc_res.stdout}",
            }
        tsc_ok = True

        # 2. Vitest: MUST fail (be killed)
        vitest_cmd = [
            "cmd", "/c", "npx", "vitest", "run", "tests/acc09-contrast-tokens.test.tsx"
        ] if os.name == "nt" else [
            "npx", "vitest", "run", "tests/acc09-contrast-tokens.test.tsx"
        ]

        vitest_res = subprocess.run(
            vitest_cmd,
            cwd=APPS_WEB,
            capture_output=True,
            text=True,
            encoding="utf-8",
            errors="replace",
            timeout=120,
        )

        if vitest_res.returncode != 0:
            killed = True
            error_msg = f"Killed successfully (exit {vitest_res.returncode})"
        else:
            killed = False
            error_msg = "SURVIVED: test suite unexpectedly passed with mutant!"

    except subprocess.TimeoutExpired:
        return {
            "id": mid,
            "desc": mutant["desc"],
            "status": "timeout",
            "error": "Test run timed out (>120s)",
        }
    finally:
        # CRITICAL: Always restore byte-clean using original bytes
        target_path.write_bytes(originals[mutant["file"]])
        status = get_clean_status()
        if status:
            print(f"FATAL: Working tree dirty after restoring {mid}: {status}", file=sys.stderr)
            sys.exit(1)

    return {
        "id": mid,
        "desc": mutant["desc"],
        "status": "killed" if killed else "survived",
        "tsc_ok": tsc_ok,
        "detail": error_msg,
    }


def main():
    parser = argparse.ArgumentParser(description="Card 282 Mutation Verification Runner")
    parser.add_argument("--mutant", help="Run a specific mutant by ID (e.g. M1)")
    parser.add_argument("--all", action="store_true", help="Run all 40 mutants sequentially")
    parser.add_argument("--list", action="store_true", help="List all available mutants")
    args = parser.parse_args()

    if args.list:
        print(f"Total Mutants: {len(MUTANTS)}")
        for m in MUTANTS:
            print(f"  [{m['id']}] ({m['file']}) {m['desc']}")
        return

    # Check clean working tree before starting
    init_status = get_clean_status()
    if init_status:
        print(f"Error: Git working tree must be clean before running mutants!\n{init_status}", file=sys.stderr)
        sys.exit(1)

    # Read original bytes for all target files
    originals = {fkey: path.read_bytes() for fkey, path in TARGET_FILES.items()}

    to_run = MUTANTS
    if args.mutant:
        to_run = [m for m in MUTANTS if m["id"] == args.mutant]
        if not to_run:
            print(f"Error: Mutant ID {args.mutant} not found!", file=sys.stderr)
            sys.exit(1)
    elif not args.all:
        print("Please specify --all or --mutant <id> (use --list to view all)")
        return

    # Record commit SHA before running
    head_sha = subprocess.check_output(
        ["git", "rev-parse", "HEAD"], cwd=WORKTREE_ROOT, text=True, encoding="utf-8", errors="replace"
    ).strip()

    start_time = datetime.now(timezone.utc)
    results = []

    print(f"Starting execution of {len(to_run)} mutants at {start_time.isoformat()}...")
    print(f"Head SHA: {head_sha}")
    print("-" * 70)

    for i, m in enumerate(to_run, 1):
        print(f"[{i}/{len(to_run)}] Running {m['id']}: {m['desc']} ...", end=" ", flush=True)
        res = run_single_mutant(m, originals)
        print(f"{res['status'].upper()}")
        results.append(res)
        if res["status"] != "killed":
            print(f"   --> {res.get('error') or res.get('detail')}")

    end_time = datetime.now(timezone.utc)
    duration_s = (end_time - start_time).total_seconds()

    killed_count = sum(1 for r in results if r["status"] == "killed")
    survived_count = sum(1 for r in results if r["status"] == "survived")
    timeout_count = sum(1 for r in results if r["status"] == "timeout")
    tsc_fail_count = sum(1 for r in results if r["status"] == "tsc_failed")

    summary = {
        "timestamp": end_time.isoformat(),
        "sourceHeadSha": head_sha,
        "totalMutants": len(to_run),
        "killed": killed_count,
        "survived": survived_count,
        "timeouts": timeout_count,
        "tsc_fails": tsc_fail_count,
        "durationSeconds": round(duration_s, 2),
        "killRate": f"{(killed_count / len(to_run) * 100):.1f}%",
        "mutants": results,
    }

    # Save to receipt file only when running --all
    if args.all and len(to_run) == len(MUTANTS):
        RESULTS_FILE.write_text(json.dumps(summary, indent=2), encoding="utf-8")
        print(f"Saved mutation receipt to {RESULTS_FILE}")

    print("=" * 70)
    print(f"SUMMARY: Kill Rate: {killed_count}/{len(to_run)} ({summary['killRate']}) in {duration_s:.1f}s")
    print(f"  killed: {killed_count}, survived: {survived_count}, timeouts: {timeout_count}, tsc_fails: {tsc_fail_count}")

    if killed_count != len(to_run):
        sys.exit(1)


if __name__ == "__main__":
    main()
