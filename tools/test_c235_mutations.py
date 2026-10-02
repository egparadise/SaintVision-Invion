#!/usr/bin/env python3
"""
tools/test_c235_mutations.py:
Verification runner for 40 accessibility, contrast, contract, and fail-closed mutants (Z1-Z40)
targeting PlacementSimulator.tsx.

Requirements:
- Each mutant MUST compile cleanly under TypeScript (tsc -p tsconfig.app.json --noEmit).
- Each mutant MUST be killed by vitest run tests/acc09-contrast-tokens.test.tsx with timeout=120s.
- If timeout, record as TIMEOUT (do not count as killed).
- Restore original code after each mutant and verify git diff 0.
- 5~10 mutants per batch (8 per batch across 5 batches).
- Sequential execution only (under 1GB memory).
- 100% kill rate (40/40) required.
"""

import os
import sys
import json
import argparse
import subprocess
from pathlib import Path

WORKTREE_ROOT = Path(r"D:\Project\SaintVisionI-Invion\https-github.com-egparadise-SaintVision-Invion.git\.worktrees\gemini-c235")
APPS_WEB = WORKTREE_ROOT / "apps" / "web"
TARGET_FILE = APPS_WEB / "src" / "features" / "placement" / "PlacementSimulator.tsx"
RESULTS_FILE = WORKTREE_ROOT / "tools" / ".c235_mutation_results.json"

MUTANTS = [
    # 1. fg==bg & border==bg collisions (Z1-Z9)
    {
        "id": "Z1",
        "desc": "candidate config: fg==bg collision (color: var(--color-bg-subtle))",
        "target": "color: 'var(--color-status-degraded)',\n    bg: 'var(--color-bg-subtle)',",
        "replacement": "color: 'var(--color-bg-subtle)',\n    bg: 'var(--color-bg-subtle)',",
    },
    {
        "id": "Z2",
        "desc": "candidate config: border==bg collision (border: var(--color-bg-subtle))",
        "target": "border: 'var(--color-status-degraded)',\n    label: 'CANDIDATE (미검증)',",
        "replacement": "border: 'var(--color-bg-subtle)',\n    label: 'CANDIDATE (미검증)',",
    },
    {
        "id": "Z3",
        "desc": "pool button selected: fg==bg collision (color: brand-subtle)",
        "target": "color: isSelected ? 'var(--color-brand-hover)' : 'var(--color-text-secondary)',",
        "replacement": "color: isSelected ? 'var(--color-brand-subtle)' : 'var(--color-text-secondary)',",
    },
    {
        "id": "Z4",
        "desc": "pool button selected: border==bg collision (border: brand-subtle)",
        "target": "border: isSelected ? '1px solid var(--color-brand-hover)' : '1px solid var(--color-border-subtle)',",
        "replacement": "border: isSelected ? '1px solid var(--color-brand-subtle)' : '1px solid var(--color-border-subtle)',",
    },
    {
        "id": "Z5",
        "desc": "unverified badge: fg==bg collision (color: bg-subtle)",
        "target": "color: 'var(--color-status-degraded)',\n              fontSize: '0.6875rem',",
        "replacement": "color: 'var(--color-bg-subtle)',\n              fontSize: '0.6875rem',",
    },
    {
        "id": "Z6",
        "desc": "unverified badge: border==bg collision (border: bg-subtle)",
        "target": "border: '1px solid var(--color-status-degraded)',\n              color: 'var(--color-status-degraded)',",
        "replacement": "border: '1px solid var(--color-bg-subtle)',\n              color: 'var(--color-status-degraded)',",
    },
    {
        "id": "Z7",
        "desc": "gpu button selected: border==bg collision (border: brand-subtle)",
        "target": "border: requiresGpu ? '1px solid var(--color-brand-hover)' : '1px solid var(--color-border-subtle)',",
        "replacement": "border: requiresGpu ? '1px solid var(--color-brand-subtle)' : '1px solid var(--color-border-subtle)',",
    },
    {
        "id": "Z8",
        "desc": "error banner: border==bg collision (border: bg-subtle)",
        "target": "border: '1px solid var(--color-status-offline)',\n            color: 'var(--color-status-offline)',\n            marginBottom: '20px',",
        "replacement": "border: '1px solid var(--color-bg-subtle)',\n            color: 'var(--color-status-offline)',\n            marginBottom: '20px',",
    },
    {
        "id": "Z9",
        "desc": "preview retry button: border==bg collision (border: bg-subtle)",
        "target": "data-testid=\"preview-retry-btn\"\n                onClick={loadPlacementPreview}\n                style={{ marginTop: '8px', padding: '3px 8px', fontSize: '0.6875rem', backgroundColor: 'var(--color-bg-subtle)', color: 'var(--color-text-primary)', border: '1px solid var(--color-border-subtle)', borderRadius: '4px', cursor: 'pointer' }}",
        "replacement": "data-testid=\"preview-retry-btn\"\n                onClick={loadPlacementPreview}\n                style={{ marginTop: '8px', padding: '3px 8px', fontSize: '0.6875rem', backgroundColor: 'var(--color-bg-subtle)', color: 'var(--color-text-primary)', border: '1px solid var(--color-bg-subtle)', borderRadius: '4px', cursor: 'pointer' }}",
    },

    # 2. text token as bg (Z10-Z11)
    {
        "id": "Z10",
        "desc": "candidate config: text token as bg (bg: var(--color-text-primary))",
        "target": "bg: 'var(--color-bg-subtle)',\n    border: 'var(--color-status-degraded)',",
        "replacement": "bg: 'var(--color-text-primary)',\n    border: 'var(--color-status-degraded)',",
    },
    {
        "id": "Z11",
        "desc": "pool button selected: text token as bg (backgroundColor: text-primary)",
        "target": "backgroundColor: isSelected ? 'var(--color-brand-subtle)' : 'var(--color-bg-subtle)',",
        "replacement": "backgroundColor: isSelected ? 'var(--color-text-primary)' : 'var(--color-bg-subtle)',",
    },

    # 3. opacity degradation (Z12-Z14)
    {
        "id": "Z12",
        "desc": "candidate badge: opacity degradation (opacity: 0.4)",
        "target": "data-testid={`candidate-status-${candKey}`}\n                      style={{\n                        padding: '2px 6px',",
        "replacement": "data-testid={`candidate-status-${candKey}`}\n                      style={{\n                        opacity: 0.4,\n                        padding: '2px 6px',",
    },
    {
        "id": "Z13",
        "desc": "unverified badge: opacity degradation (opacity: 0.45)",
        "target": "data-testid=\"local-simulation-badge\"\n            style={{\n              padding: '3px 8px',",
        "replacement": "data-testid=\"local-simulation-badge\"\n            style={{\n              opacity: 0.45,\n              padding: '3px 8px',",
    },
    {
        "id": "Z14",
        "desc": "pool button: opacity degradation (opacity: 0.35)",
        "target": "onClick={() => setSelectedPoolId(pId)}\n                  style={{\n                    padding: '8px 14px',",
        "replacement": "onClick={() => setSelectedPoolId(pId)}\n                  style={{\n                    opacity: 0.35,\n                    padding: '8px 14px',",
    },

    # 4. comment decoys (Z15-Z16)
    {
        "id": "Z15",
        "desc": "candidate config: comment decoy with legacy hex",
        "target": "color: 'var(--color-status-degraded)',\n    bg: 'var(--color-bg-subtle)',",
        "replacement": "color: 'var(--color-status-degraded) /* #fbbf24 */',\n    bg: 'var(--color-bg-subtle)',",
    },
    {
        "id": "Z16",
        "desc": "unverified badge: comment decoy with legacy hex",
        "target": "color: 'var(--color-status-degraded)',\n              fontSize: '0.6875rem',",
        "replacement": "color: 'var(--color-status-degraded) /* #fbbf24 */',\n              fontSize: '0.6875rem',",
    },

    # 5. legacy literal reverts (Z17-Z20)
    {
        "id": "Z17",
        "desc": "candidate config: revert to legacy #fbbf24",
        "target": "color: 'var(--color-status-degraded)',\n    bg: 'var(--color-bg-subtle)',",
        "replacement": "color: '#fbbf24',\n    bg: 'var(--color-bg-subtle)',",
    },
    {
        "id": "Z18",
        "desc": "error banner: revert text to legacy #fca5a5",
        "target": "color: 'var(--color-status-offline)',\n            marginBottom: '20px',",
        "replacement": "color: '#fca5a5',\n            marginBottom: '20px',",
    },
    {
        "id": "Z19",
        "desc": "error banner: revert border to legacy #ef4444",
        "target": "border: '1px solid var(--color-status-offline)',\n            color: 'var(--color-status-offline)',\n            marginBottom: '20px',",
        "replacement": "border: '1px solid #ef4444',\n            color: 'var(--color-status-offline)',\n            marginBottom: '20px',",
    },
    {
        "id": "Z20",
        "desc": "operator note: revert text to legacy #93c5fd",
        "target": "color: 'var(--color-brand-hover)' }}>\n                🛠️ <strong>[운영자 조치 필요]</strong>",
        "replacement": "color: '#93c5fd' }}>\n                🛠️ <strong>[운영자 조치 필요]</strong>",
    },

    # 6. state color collapse (Z21-Z23)
    {
        "id": "Z21",
        "desc": "candidate config: degraded color collapsed to status-online",
        "target": "color: 'var(--color-status-degraded)',\n    bg: 'var(--color-bg-subtle)',",
        "replacement": "color: 'var(--color-status-online)',\n    bg: 'var(--color-bg-subtle)',",
    },
    {
        "id": "Z22",
        "desc": "error banner: offline color collapsed to status-online",
        "target": "border: '1px solid var(--color-status-offline)',\n            color: 'var(--color-status-offline)',\n            marginBottom: '20px',",
        "replacement": "border: '1px solid var(--color-status-online)',\n            color: 'var(--color-status-online)',\n            marginBottom: '20px',",
    },
    {
        "id": "Z23",
        "desc": "unverified badge: degraded color collapsed to status-online",
        "target": "border: '1px solid var(--color-status-degraded)',\n              color: 'var(--color-status-degraded)',",
        "replacement": "border: '1px solid var(--color-status-online)',\n              color: 'var(--color-status-online)',",
    },

    # 7. label & text mutation (Z24-Z26)
    {
        "id": "Z24",
        "desc": "candidate config: label mutated to '대기'",
        "target": "label: 'CANDIDATE (미검증)',",
        "replacement": "label: '대기',",
    },
    {
        "id": "Z25",
        "desc": "unverified badge: text mutated to '[시뮬레이션]'",
        "target": "로컬 결정론적 평가 (UNVERIFIED: 로컬 시뮬레이션 전용)",
        "replacement": "[시뮬레이션]",
    },
    {
        "id": "Z26",
        "desc": "preview retry button: text mutated to '!'",
        "target": "style={{ marginTop: '8px', padding: '3px 8px', fontSize: '0.6875rem', backgroundColor: 'var(--color-bg-subtle)', color: 'var(--color-text-primary)', border: '1px solid var(--color-border-subtle)', borderRadius: '4px', cursor: 'pointer' }}\n              >\n                재시도 (Retry)\n              </button>",
        "replacement": "style={{ marginTop: '8px', padding: '3px 8px', fontSize: '0.6875rem', backgroundColor: 'var(--color-bg-subtle)', color: 'var(--color-text-primary)', border: '1px solid var(--color-border-subtle)', borderRadius: '4px', cursor: 'pointer' }}\n              >\n                !\n              </button>",
    },

    # 8. outline suppression (Z27-Z30)
    {
        "id": "Z27",
        "desc": "gpu button: outline: 'none' suppressing focus ring",
        "target": "onClick={() => setRequiresGpu((prev) => !prev)}\n              style={{\n                width: '100%',",
        "replacement": "onClick={() => setRequiresGpu((prev) => !prev)}\n              style={{\n                outline: 'none',\n                width: '100%',",
    },
    {
        "id": "Z28",
        "desc": "retry button: outline: 0 suppressing focus ring",
        "target": "data-testid=\"pools-retry-btn\"\n            onClick={loadPools}\n            style={{ marginTop: '8px',",
        "replacement": "data-testid=\"pools-retry-btn\"\n            onClick={loadPools}\n            style={{ outline: 0, marginTop: '8px',",
    },
    {
        "id": "Z29",
        "desc": "pool button: outlineWidth: '0px' suppressing focus ring",
        "target": "onClick={() => setSelectedPoolId(pId)}\n                  style={{\n                    padding: '8px 14px',",
        "replacement": "onClick={() => setSelectedPoolId(pId)}\n                  style={{\n                    outlineWidth: '0px',\n                    padding: '8px 14px',",
    },
    {
        "id": "Z30",
        "desc": "gpu button: outline: '0px' suppressing focus ring",
        "target": "onClick={() => setRequiresGpu((prev) => !prev)}\n              style={{\n                width: '100%',",
        "replacement": "onClick={() => setRequiresGpu((prev) => !prev)}\n              style={{\n                outline: '0px',\n                width: '100%',",
    },

    # 9. fail-closed bypass & prototype key hijack (Z31-Z33)
    {
        "id": "Z31",
        "desc": "fail-closed: bypass Object.hasOwn with plain indexing",
        "target": "if (state && Object.hasOwn(DISCOVERY_CANDIDATE_STATE_CONFIG, state)) {",
        "replacement": "if (state && (DISCOVERY_CANDIDATE_STATE_CONFIG as any)[state]) {",
    },
    {
        "id": "Z32",
        "desc": "prototype key: hijack toString into candidate config",
        "target": "if (state && Object.hasOwn(DISCOVERY_CANDIDATE_STATE_CONFIG, state)) {",
        "replacement": "if (state && (Object.hasOwn(DISCOVERY_CANDIDATE_STATE_CONFIG, state) || state === 'toString')) {",
    },
    {
        "id": "Z33",
        "desc": "fail-closed: fallback returns candidate color instead of unknown",
        "target": "return {\n    color: 'var(--color-status-unknown)',\n    bg: 'var(--color-bg-subtle)',",
        "replacement": "return {\n    color: 'var(--color-status-degraded)',\n    bg: 'var(--color-bg-subtle)',",
    },

    # 10. out-of-contract additions & contract bypass (Z34-Z35)
    {
        "id": "Z34",
        "desc": "contract bypass: map out-of-contract 'admitted' to candidate",
        "target": "if (state && Object.hasOwn(DISCOVERY_CANDIDATE_STATE_CONFIG, state)) {",
        "replacement": "if (state && (Object.hasOwn(DISCOVERY_CANDIDATE_STATE_CONFIG, state) || state === 'admitted')) {",
    },
    {
        "id": "Z35",
        "desc": "contract bypass: state !== 'admitted' guard bypass",
        "target": "return DISCOVERY_CANDIDATE_STATE_CONFIG[state as DiscoveryCandidateStateKey];",
        "replacement": "return state === 'admitted' ? DISCOVERY_CANDIDATE_STATE_CONFIG.candidate : DISCOVERY_CANDIDATE_STATE_CONFIG[state as DiscoveryCandidateStateKey];",
    },

    # 11. named color injections (Z36-Z37)
    {
        "id": "Z36",
        "desc": "named color: candidate badge border injected with yellow",
        "target": "border: `1px solid ${candStateCfg.border}`,",
        "replacement": "border: '1px solid yellow',",
    },
    {
        "id": "Z37",
        "desc": "named color: error banner color injected with red",
        "target": "color: 'var(--color-status-offline)',\n            marginBottom: '20px',",
        "replacement": "color: 'red',\n            marginBottom: '20px',",
    },

    # 12. prefix removal, uppercase bypass, case-insensitive lookup (Z38-Z40)
    {
        "id": "Z38",
        "desc": "unknown label: remove 'UNKNOWN (' prefix",
        "target": "label: state ? `UNKNOWN (${state})` : 'UNKNOWN',",
        "replacement": "label: state ? `${state}` : 'UNKNOWN',",
    },
    {
        "id": "Z39",
        "desc": "unknown label: bypass UNKNOWN format and return raw uppercase",
        "target": "label: state ? `UNKNOWN (${state})` : 'UNKNOWN',",
        "replacement": "label: state ? state.toUpperCase() : 'UNKNOWN',",
    },
    {
        "id": "Z40",
        "desc": "case-insensitive lookup: toLowerCase() lookup bypass",
        "target": "if (state && Object.hasOwn(DISCOVERY_CANDIDATE_STATE_CONFIG, state)) {",
        "replacement": "if (state && Object.hasOwn(DISCOVERY_CANDIDATE_STATE_CONFIG, state.toLowerCase())) {",
    },
]


def run_vitest_acc09(timeout=120):
    cmd = [
        "npx.cmd" if os.name == "nt" else "npx",
        "vitest",
        "run",
        "tests/acc09-contrast-tokens.test.tsx",
    ]
    try:
        res = subprocess.run(
            cmd,
            cwd=str(APPS_WEB),
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
            encoding="utf-8",
            errors="replace",
            timeout=timeout,
        )
        return res.returncode, res.stdout, res.stderr, False
    except subprocess.TimeoutExpired as e:
        stdout = e.stdout.decode("utf-8", errors="replace") if e.stdout else ""
        stderr = e.stderr.decode("utf-8", errors="replace") if e.stderr else ""
        return -1, stdout, stderr, True


def run_tsc(timeout=60):
    cmd = [
        "npx.cmd" if os.name == "nt" else "npx",
        "tsc",
        "-p",
        "tsconfig.app.json",
        "--noEmit",
    ]
    try:
        res = subprocess.run(
            cmd,
            cwd=str(APPS_WEB),
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
            encoding="utf-8",
            errors="replace",
            timeout=timeout,
        )
        return res.returncode, res.stdout, res.stderr
    except subprocess.TimeoutExpired:
        return -1, "", "TSC Timeout"


def verify_git_diff_clean():
    diff_res = subprocess.run(
        ["git", "diff", "--exit-code", "--", str(TARGET_FILE)],
        cwd=str(WORKTREE_ROOT),
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True,
        encoding="utf-8",
        errors="replace",
    )
    return diff_res.returncode == 0


def load_saved_results():
    if RESULTS_FILE.exists():
        try:
            return json.loads(RESULTS_FILE.read_text(encoding="utf-8"))
        except Exception:
            return {}
    return {}


def save_results(results):
    RESULTS_FILE.write_text(json.dumps(results, indent=2, ensure_ascii=False), encoding="utf-8")


def run_batch(start_idx, end_idx):
    original_code = TARGET_FILE.read_text(encoding="utf-8")
    results = load_saved_results()

    print(f"\n--- Running Mutants {start_idx} to {end_idx} (Total: {end_idx - start_idx + 1}) ---")

    for idx in range(start_idx, end_idx + 1):
        m = MUTANTS[idx - 1]
        mid = m["id"]
        desc = m["desc"]
        target = m["target"]
        replacement = m["replacement"]

        print(f"\n[{idx:02d}/40] Testing {mid}: {desc}")

        # Check target uniqueness in original code
        cnt = original_code.count(target)
        if cnt != 1:
            print(f"  [ERROR] Target occurrence count is {cnt} (must be 1). Aborting.")
            sys.exit(1)

        # Apply mutation
        mutated_code = original_code.replace(target, replacement, 1)
        TARGET_FILE.write_text(mutated_code, encoding="utf-8", newline="\n")

        status = "UNKNOWN"
        detail = ""

        try:
            # 1. TSC check
            tsc_rc, tsc_out, tsc_err = run_tsc(timeout=60)
            if tsc_rc != 0:
                print(f"  [INVALID] Mutant {mid} failed compilation (TS error):\n{tsc_out[:300]}")
                status = "COMPILATION_ERROR"
                detail = tsc_out[:300]
            else:
                # 2. Vitest check with 120s timeout
                v_rc, v_out, v_err, timed_out = run_vitest_acc09(timeout=120)
                if timed_out:
                    print(f"  [TIMEOUT] Mutant {mid} timed out after 120s (NOT counted as killed)!")
                    status = "TIMEOUT"
                    detail = "Execution timed out (> 120s)"
                elif v_rc != 0:
                    # Find failed assertion line
                    fail_line = ""
                    for line in v_out.splitlines():
                        if "AssertionError:" in line or "FAIL " in line or "violations:" in line:
                            fail_line = line.strip()
                            break
                    print(f"  [KILLED] {mid} compiled cleanly (rc=0) and was KILLED by tests (rc={v_rc}): {fail_line}")
                    status = "KILLED"
                    detail = fail_line
                else:
                    print(f"  [SURVIVED] Mutant {mid} compiled and passed all tests! (SURVIVED)")
                    status = "SURVIVED"
                    detail = "Tests passed cleanly"

        finally:
            # 3. Always restore original code and verify git diff 0
            TARGET_FILE.write_text(original_code, encoding="utf-8", newline="\n")
            if not verify_git_diff_clean():
                print(f"  [FATAL] Git diff not clean after restoring {mid}! Halting.")
                sys.exit(1)

        results[mid] = {
            "id": mid,
            "index": idx,
            "desc": desc,
            "status": status,
            "detail": detail,
        }
        save_results(results)

    print(f"\n--- Batch {start_idx}-{end_idx} Completed ---")


def print_summary():
    results = load_saved_results()
    total = len(MUTANTS)
    killed = sum(1 for r in results.values() if r["status"] == "KILLED")
    survived = [mid for mid, r in results.items() if r["status"] == "SURVIVED"]
    timed_out = [mid for mid, r in results.items() if r["status"] == "TIMEOUT"]
    comp_errors = [mid for mid, r in results.items() if r["status"] == "COMPILATION_ERROR"]

    print("\n" + "=" * 80)
    print(" CARD 235 (PlacementSimulator): 40-MUTANT VERIFICATION SUMMARY (Z1-Z40)")
    print("=" * 80)
    print(f"Total Mutants Evaluated: {len(results)} / {total}")
    print(f"Killed (100% Valid):     {killed} / {total} ({killed/total*100:.1f}%)")
    print(f"Survived:                {len(survived)}")
    print(f"Timed Out:               {len(timed_out)}")
    print(f"Compilation Errors:      {len(comp_errors)}")
    print("-" * 80)

    for i, m in enumerate(MUTANTS, 1):
        mid = m["id"]
        res = results.get(mid)
        if res:
            st = res["status"]
            det = res["detail"][:50]
            print(f"  [{i:02d}] {mid:4s}: {st:17s} | {m['desc'][:45]:45s} | {det}")
        else:
            print(f"  [{i:02d}] {mid:4s}: NOT RUN          | {m['desc'][:45]:45s}")

    print("=" * 80)
    if killed == total:
        print("[SUCCESS] All 40 mutants KILLED (100.0% kill rate, exit code 0).")
        return 0
    else:
        print(f"[INCOMPLETE/FAILED] Only {killed}/{total} mutants killed.")
        return 1


def main():
    parser = argparse.ArgumentParser(description="Card 235 40-Mutant Runner")
    parser.add_argument("--batch", type=int, choices=[1, 2, 3, 4, 5], help="Run specific batch (1=Z1-Z8, 2=Z9-Z16, 3=Z17-Z24, 4=Z25-Z32, 5=Z33-Z40)")
    parser.add_argument("--start", type=int, default=1, help="Start mutant index (1-40)")
    parser.add_argument("--end", type=int, default=40, help="End mutant index (1-40)")
    parser.add_argument("--batch-all", action="store_true", help="Run all 5 batches sequentially")
    parser.add_argument("--summary", action="store_true", help="Print summary of recorded results")
    parser.add_argument("--preflight", action="store_true", help="Run preflight check only")
    args = parser.parse_args()

    # Preflight check
    print("=" * 80)
    print(" Card 235 Mutation Test Suite (PlacementSimulator.tsx)")
    print("=" * 80)
    print("[Preflight] Verifying clean codebase passes tsc and vitest...")
    tsc_rc, tsc_out, _ = run_tsc(timeout=60)
    if tsc_rc != 0:
        print(f"[Preflight] FAILED: TSC errors on clean codebase:\n{tsc_out}")
        sys.exit(1)

    v_rc, v_out, _, _ = run_vitest_acc09(timeout=120)
    if v_rc != 0:
        print(f"[Preflight] FAILED: Vitest failed on clean codebase:\n{v_out}")
        sys.exit(1)
    print("[Preflight] Clean codebase PASSED (tsc 0, vitest 0).\n")

    if args.preflight:
        sys.exit(0)

    if args.summary:
        sys.exit(print_summary())

    if args.batch:
        batch_ranges = {
            1: (1, 8),
            2: (9, 16),
            3: (17, 24),
            4: (25, 32),
            5: (33, 40),
        }
        s, e = batch_ranges[args.batch]
        run_batch(s, e)
        print_summary()
        sys.exit(0)

    if args.batch_all:
        for b in range(1, 6):
            s = (b - 1) * 8 + 1
            e = b * 8
            run_batch(s, e)
        sys.exit(print_summary())

    # Default custom range
    run_batch(args.start, args.end)
    sys.exit(print_summary())


if __name__ == "__main__":
    main()
