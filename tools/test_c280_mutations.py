#!/usr/bin/env python3
"""
tools/test_c280_mutations.py:
Verification runner for 40 accessibility, contrast, contract, and fail-closed mutants (M1-M40)
targeting Card 280:
  - apps/web/src/features/editor/ConflictResolutionModal.tsx (M1-M14)
  - apps/web/src/features/editor/DiffViewer.tsx (M15-M27)
  - apps/web/src/features/editor/GitCommitModal.tsx (M28-M40)

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
RESULTS_FILE = WORKTREE_ROOT / "tools" / ".c280_mutation_results.json"

TARGET_FILES = {
    "conflict": APPS_WEB / "src" / "features" / "editor" / "ConflictResolutionModal.tsx",
    "diff": APPS_WEB / "src" / "features" / "editor" / "DiffViewer.tsx",
    "git": APPS_WEB / "src" / "features" / "editor" / "GitCommitModal.tsx",
}

MUTANTS = [
    # M1-M14: ConflictResolutionModal.tsx
    {
        "id": "M1",
        "file": "conflict",
        "desc": "etag_mismatch color subtle collision: colorVar: 'var(--color-bg-subtle)'",
        "target": "    colorVar: 'var(--color-status-offline)',\n    bgVar: 'var(--color-risk-l3-bg)',",
        "replacement": "    colorVar: 'var(--color-bg-subtle)',\n    bgVar: 'var(--color-risk-l3-bg)',",
    },
    {
        "id": "M2",
        "file": "conflict",
        "desc": "etag_mismatch color literal regression: colorVar: '#f85149'",
        "target": "  etag_mismatch: {\n    colorVar: 'var(--color-status-offline)',",
        "replacement": "  etag_mismatch: {\n    colorVar: '#f85149',",
    },
    {
        "id": "M3",
        "file": "conflict",
        "desc": "etag_mismatch bg literal regression: bgVar: 'rgba(248, 81, 73, 0.1)'",
        "target": "    colorVar: 'var(--color-status-offline)',\n    bgVar: 'var(--color-risk-l3-bg)',\n    borderVar: 'var(--color-risk-l3-border)',",
        "replacement": "    colorVar: 'var(--color-status-offline)',\n    bgVar: 'rgba(248, 81, 73, 0.1)',\n    borderVar: 'var(--color-risk-l3-border)',",
    },
    {
        "id": "M4",
        "file": "conflict",
        "desc": "etag_mismatch badgeBgVar subtle collision: badgeBgVar: 'var(--color-bg-subtle)'",
        "target": "    badgeBgVar: 'var(--color-status-offline)',\n    badgeFgVar: 'var(--color-brand-primary-fg)',",
        "replacement": "    badgeBgVar: 'var(--color-bg-subtle)',\n    badgeFgVar: 'var(--color-brand-primary-fg)',",
    },
    {
        "id": "M5",
        "file": "conflict",
        "desc": "concurrency_conflict color subtle collision: colorVar: 'var(--color-bg-subtle)'",
        "target": "  concurrency_conflict: {\n    colorVar: 'var(--color-status-degraded)',",
        "replacement": "  concurrency_conflict: {\n    colorVar: 'var(--color-bg-subtle)',",
    },
    {
        "id": "M6",
        "file": "conflict",
        "desc": "concurrency_conflict color literal regression: colorVar: '#d29922'",
        "target": "  concurrency_conflict: {\n    colorVar: 'var(--color-status-degraded)',\n    bgVar: 'var(--color-bg-subtle)',",
        "replacement": "  concurrency_conflict: {\n    colorVar: '#d29922',\n    bgVar: 'var(--color-bg-subtle)',",
    },
    {
        "id": "M7",
        "file": "conflict",
        "desc": "getConflictStatusConfig prototype key vulnerability: in instead of Object.hasOwn",
        "target": "  if (Object.hasOwn(CONFLICT_STATUS_CONFIG, status)) {",
        "replacement": "  if (status in CONFLICT_STATUS_CONFIG) {",
    },
    {
        "id": "M8",
        "file": "conflict",
        "desc": "getConflictStatusConfig fallback color changed to normal text",
        "target": "    colorVar: 'var(--color-status-unknown)',\n    bgVar: 'var(--color-bg-subtle)',\n    borderVar: 'var(--color-border-subtle)',\n    badgeBgVar: 'var(--color-status-unknown)',\n    badgeFgVar: 'var(--color-brand-primary-fg)',\n    label: `⚠️ UNKNOWN (${status})`,",
        "replacement": "    colorVar: 'var(--color-text-primary)',\n    bgVar: 'var(--color-bg-subtle)',\n    borderVar: 'var(--color-border-subtle)',\n    badgeBgVar: 'var(--color-status-unknown)',\n    badgeFgVar: 'var(--color-brand-primary-fg)',\n    label: `⚠️ UNKNOWN (${status})`,",
    },
    {
        "id": "M9",
        "file": "conflict",
        "desc": "keep_mine color subtle collision: colorVar: 'var(--color-bg-subtle)'",
        "target": "  keep_mine: {\n    colorVar: 'var(--color-status-offline)',",
        "replacement": "  keep_mine: {\n    colorVar: 'var(--color-bg-subtle)',",
    },
    {
        "id": "M10",
        "file": "conflict",
        "desc": "keep_mine color literal regression: colorVar: '#f85149'",
        "target": "  keep_mine: {\n    colorVar: 'var(--color-status-offline)',\n    borderColorVar: 'var(--color-status-offline)',",
        "replacement": "  keep_mine: {\n    colorVar: '#f85149',\n    borderColorVar: 'var(--color-status-offline)',",
    },
    {
        "id": "M11",
        "file": "conflict",
        "desc": "keep_mine borderColor literal regression: borderColorVar: '#f85149'",
        "target": "    borderColorVar: 'var(--color-status-offline)',\n    label: 'Force Overwrite (Keep Mine)',",
        "replacement": "    borderColorVar: '#f85149',\n    label: 'Force Overwrite (Keep Mine)',",
    },
    {
        "id": "M12",
        "file": "conflict",
        "desc": "accept_remote color literal regression: colorVar: '#c9d1d9'",
        "target": "  accept_remote: {\n    colorVar: 'var(--color-text-secondary)',",
        "replacement": "  accept_remote: {\n    colorVar: '#c9d1d9',",
    },
    {
        "id": "M13",
        "file": "conflict",
        "desc": "warning banner background literal regression: backgroundColor: 'rgba(248, 81, 73, 0.1)'",
        "target": "        {/* Warning Banner */}\n        <div\n          data-testid=\"conflict-warning-banner\"\n          style={{\n            padding: '16px 20px',\n            backgroundColor: statusConfig.bgVar,",
        "replacement": "        {/* Warning Banner */}\n        <div\n          data-testid=\"conflict-warning-banner\"\n          style={{\n            padding: '16px 20px',\n            backgroundColor: 'rgba(248, 81, 73, 0.1)',",
    },
    {
        "id": "M14",
        "file": "conflict",
        "desc": "modal backdrop literal regression: backgroundColor: 'rgba(0, 0, 0, 0.75)'",
        "target": "        position: 'fixed',\n        inset: 0,\n        backgroundColor: 'var(--color-bg-backdrop)',",
        "replacement": "        position: 'fixed',\n        inset: 0,\n        backgroundColor: 'rgba(0, 0, 0, 0.75)',",
    },

    # M15-M27: DiffViewer.tsx
    {
        "id": "M15",
        "file": "diff",
        "desc": "diff added color subtle collision: colorVar: 'var(--color-bg-subtle)'",
        "target": "  added: {\n    colorVar: 'var(--color-diff-added-text)',",
        "replacement": "  added: {\n    colorVar: 'var(--color-bg-subtle)',",
    },
    {
        "id": "M16",
        "file": "diff",
        "desc": "diff added color literal regression: colorVar: '#3fb950'",
        "target": "  added: {\n    colorVar: 'var(--color-diff-added-text)',\n    bgVar: 'var(--color-diff-added-bg)',",
        "replacement": "  added: {\n    colorVar: '#3fb950',\n    bgVar: 'var(--color-diff-added-bg)',",
    },
    {
        "id": "M17",
        "file": "diff",
        "desc": "diff added bg literal regression: bgVar: 'rgba(46, 160, 67, 0.15)'",
        "target": "    colorVar: 'var(--color-diff-added-text)',\n    bgVar: 'var(--color-diff-added-bg)',\n    borderVar: 'var(--color-diff-added-border)',",
        "replacement": "    colorVar: 'var(--color-diff-added-text)',\n    bgVar: 'rgba(46, 160, 67, 0.15)',\n    borderVar: 'var(--color-diff-added-border)',",
    },
    {
        "id": "M18",
        "file": "diff",
        "desc": "diff added border literal regression: borderVar: '#3fb950'",
        "target": "    borderVar: 'var(--color-diff-added-border)',\n    prefix: '+',",
        "replacement": "    borderVar: '#3fb950',\n    prefix: '+',",
    },
    {
        "id": "M19",
        "file": "diff",
        "desc": "diff removed color subtle collision: colorVar: 'var(--color-bg-subtle)'",
        "target": "  removed: {\n    colorVar: 'var(--color-diff-removed-text)',",
        "replacement": "  removed: {\n    colorVar: 'var(--color-bg-subtle)',",
    },
    {
        "id": "M20",
        "file": "diff",
        "desc": "diff removed color literal regression: colorVar: '#f85149'",
        "target": "  removed: {\n    colorVar: 'var(--color-diff-removed-text)',\n    bgVar: 'var(--color-diff-removed-bg)',",
        "replacement": "  removed: {\n    colorVar: '#f85149',\n    bgVar: 'var(--color-diff-removed-bg)',",
    },
    {
        "id": "M21",
        "file": "diff",
        "desc": "diff removed bg literal regression: bgVar: 'rgba(248, 81, 73, 0.15)'",
        "target": "    colorVar: 'var(--color-diff-removed-text)',\n    bgVar: 'var(--color-diff-removed-bg)',\n    borderVar: 'var(--color-diff-removed-border)',",
        "replacement": "    colorVar: 'var(--color-diff-removed-text)',\n    bgVar: 'rgba(248, 81, 73, 0.15)',\n    borderVar: 'var(--color-diff-removed-border)',",
    },
    {
        "id": "M22",
        "file": "diff",
        "desc": "diff removed border literal regression: borderVar: '#f85149'",
        "target": "    borderVar: 'var(--color-diff-removed-border)',\n    prefix: '-',",
        "replacement": "    borderVar: '#f85149',\n    prefix: '-',",
    },
    {
        "id": "M23",
        "file": "diff",
        "desc": "diff unchanged color subtle collision: colorVar: 'var(--color-bg-subtle)'",
        "target": "  unchanged: {\n    colorVar: 'var(--color-text-secondary)',",
        "replacement": "  unchanged: {\n    colorVar: 'var(--color-bg-subtle)',",
    },
    {
        "id": "M24",
        "file": "diff",
        "desc": "diff unchanged color literal regression: colorVar: '#c9d1d9'",
        "target": "  unchanged: {\n    colorVar: 'var(--color-text-secondary)',\n    bgVar: 'transparent',",
        "replacement": "  unchanged: {\n    colorVar: '#c9d1d9',\n    bgVar: 'transparent',",
    },
    {
        "id": "M25",
        "file": "diff",
        "desc": "getDiffLineTypeConfig prototype key vulnerability: in instead of Object.hasOwn",
        "target": "  if (Object.hasOwn(DIFF_LINE_TYPE_CONFIG, type)) {",
        "replacement": "  if (type in DIFF_LINE_TYPE_CONFIG) {",
    },
    {
        "id": "M26",
        "file": "diff",
        "desc": "getDiffLineTypeConfig fallback color changed to normal text",
        "target": "  return {\n    colorVar: 'var(--color-status-unknown)',",
        "replacement": "  return {\n    colorVar: 'var(--color-text-primary)',",
    },
    {
        "id": "M27",
        "file": "diff",
        "desc": "diff header background literal regression: backgroundColor: '#161b22'",
        "target": "        data-testid=\"diff-header-bar\"\n        style={{\n          display: 'flex',\n          justifyContent: 'space-between',\n          alignItems: 'center',\n          padding: '8px 16px',\n          borderBottom: '1px solid var(--color-border-subtle)',\n          backgroundColor: 'var(--color-bg-surface)',",
        "replacement": "        data-testid=\"diff-header-bar\"\n        style={{\n          display: 'flex',\n          justifyContent: 'space-between',\n          alignItems: 'center',\n          padding: '8px 16px',\n          borderBottom: '1px solid var(--color-border-subtle)',\n          backgroundColor: '#161b22',",
    },

    # M28-M40: GitCommitModal.tsx
    {
        "id": "M28",
        "file": "git",
        "desc": "modified color subtle collision: colorVar: 'var(--color-bg-subtle)'",
        "target": "  modified: {\n    colorVar: 'var(--color-status-degraded)',",
        "replacement": "  modified: {\n    colorVar: 'var(--color-bg-subtle)',",
    },
    {
        "id": "M29",
        "file": "git",
        "desc": "modified color literal regression: colorVar: '#e3b341'",
        "target": "  modified: {\n    colorVar: 'var(--color-status-degraded)',\n    badgeColorVar: 'var(--color-status-degraded)',",
        "replacement": "  modified: {\n    colorVar: '#e3b341',\n    badgeColorVar: 'var(--color-status-degraded)',",
    },
    {
        "id": "M30",
        "file": "git",
        "desc": "modified badgeColor literal regression: badgeColorVar: '#e3b341'",
        "target": "    badgeColorVar: 'var(--color-status-degraded)',\n    badgeText: 'modified',",
        "replacement": "    badgeColorVar: '#e3b341',\n    badgeText: 'modified',",
    },
    {
        "id": "M31",
        "file": "git",
        "desc": "clean color subtle collision: colorVar: 'var(--color-bg-subtle)'",
        "target": "  clean: {\n    colorVar: 'var(--color-text-secondary)',",
        "replacement": "  clean: {\n    colorVar: 'var(--color-bg-subtle)',",
    },
    {
        "id": "M32",
        "file": "git",
        "desc": "clean color literal regression: colorVar: '#c9d1d9'",
        "target": "  clean: {\n    colorVar: 'var(--color-text-secondary)',\n    badgeColorVar: 'var(--color-text-muted)',",
        "replacement": "  clean: {\n    colorVar: '#c9d1d9',\n    badgeColorVar: 'var(--color-text-muted)',",
    },
    {
        "id": "M33",
        "file": "git",
        "desc": "getGitFileStatusConfig prototype key vulnerability: in instead of Object.hasOwn",
        "target": "  if (Object.hasOwn(GIT_FILE_STATUS_CONFIG, status)) {",
        "replacement": "  if (status in GIT_FILE_STATUS_CONFIG) {",
    },
    {
        "id": "M34",
        "file": "git",
        "desc": "getGitFileStatusConfig fallback color changed to normal text",
        "target": "  return {\n    colorVar: 'var(--color-status-unknown)',\n    badgeColorVar: 'var(--color-status-unknown)',",
        "replacement": "  return {\n    colorVar: 'var(--color-text-primary)',\n    badgeColorVar: 'var(--color-status-unknown)',",
    },
    {
        "id": "M35",
        "file": "git",
        "desc": "staged row bg literal regression: bgVar: 'rgba(56, 139, 253, 0.1)'",
        "target": "  staged: {\n    bgVar: 'var(--color-brand-subtle)',",
        "replacement": "  staged: {\n    bgVar: 'rgba(56, 139, 253, 0.1)',",
    },
    {
        "id": "M36",
        "file": "git",
        "desc": "getGitStageStateConfig prototype key vulnerability: in instead of Object.hasOwn",
        "target": "  if (Object.hasOwn(GIT_STAGE_STATE_CONFIG, state)) {",
        "replacement": "  if (state in GIT_STAGE_STATE_CONFIG) {",
    },
    {
        "id": "M37",
        "file": "git",
        "desc": "modal container background literal regression: backgroundColor: '#161b22'",
        "target": "        data-testid=\"git-commit-dialog\"\n        style={{\n          width: '100%',\n          maxWidth: '650px',\n          backgroundColor: 'var(--color-bg-surface)',",
        "replacement": "        data-testid=\"git-commit-dialog\"\n        style={{\n          width: '100%',\n          maxWidth: '650px',\n          backgroundColor: '#161b22',",
    },
    {
        "id": "M38",
        "file": "git",
        "desc": "author input background literal regression: backgroundColor: '#0d1117'",
        "target": "            <input\n              type=\"text\"\n              data-testid=\"commit-author-input\"\n              value={author}\n              onChange={(e) => setAuthor(e.target.value)}\n              style={{\n                width: '100%',\n                padding: '8px 12px',\n                backgroundColor: 'var(--color-bg-canvas)',",
        "replacement": "            <input\n              type=\"text\"\n              data-testid=\"commit-author-input\"\n              value={author}\n              onChange={(e) => setAuthor(e.target.value)}\n              style={{\n                width: '100%',\n                padding: '8px 12px',\n                backgroundColor: '#0d1117',",
    },
    {
        "id": "M39",
        "file": "git",
        "desc": "required asterisk literal regression: color: '#f85149'",
        "target": "              Commit Message <span data-testid=\"commit-required-indicator\" style={{ color: 'var(--color-status-offline)' }}>*</span>",
        "replacement": "              Commit Message <span data-testid=\"commit-required-indicator\" style={{ color: '#f85149' }}>*</span>",
    },
    {
        "id": "M40",
        "file": "git",
        "desc": "stage all button literal regression: color: '#58a6ff'",
        "target": "                  data-testid=\"stage-all-btn\"\n                  onClick={handleStageAll}\n                  style={{ background: 'none', border: 'none', color: 'var(--color-brand-hover)',",
        "replacement": "                  data-testid=\"stage-all-btn\"\n                  onClick={handleStageAll}\n                  style={{ background: 'none', border: 'none', color: '#58a6ff',",
    },
]


def get_clean_status():
    res = subprocess.run(
        ["git", "status", "--porcelain", "--untracked-files=no"],
        cwd=WORKTREE_ROOT,
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
    )
    return res.stdout.strip()


def run_single_mutant(mutant, originals):
    mid = mutant["id"]
    fkey = mutant["file"]
    target_path = TARGET_FILES[fkey]
    original_bytes = originals[fkey]

    content = original_bytes.decode("utf-8")
    tgt = mutant["target"]
    rep = mutant["replacement"]

    if tgt not in content:
        return {
            "id": mid,
            "desc": mutant["desc"],
            "status": "target_not_found",
            "error": "Target string not found in source file",
        }

    mutated_content = content.replace(tgt, rep, 1)
    target_path.write_bytes(mutated_content.encode("utf-8"))

    tsc_ok = False
    killed = False
    error_msg = None

    try:
        # 1. Typecheck: MUST compile cleanly
        tsc_cmd = ["cmd", "/c", "npx", "tsc", "-b"] if os.name == "nt" else ["npx", "tsc", "-b"]
        tsc_res = subprocess.run(
            tsc_cmd,
            cwd=APPS_WEB,
            capture_output=True,
            text=True,
            encoding="utf-8",
            errors="replace",
            timeout=60,
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
        target_path.write_bytes(original_bytes)
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
    parser = argparse.ArgumentParser(description="Card 280 Mutation Verification Runner")
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
