#!/usr/bin/env python3
"""
tools/test_c245_mutations.py:
Verification runner for 40 accessibility, contrast, contract, and fail-closed mutants (W1-W40)
targeting ApprovalCenter.tsx.

Requirements:
- Each mutant MUST compile cleanly under TypeScript (npx tsc -b).
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
from datetime import datetime, timezone
from pathlib import Path

WORKTREE_ROOT = Path(__file__).resolve().parent.parent
APPS_WEB = WORKTREE_ROOT / "apps" / "web"
TARGET_FILE = APPS_WEB / "src" / "features" / "approvals" / "ApprovalCenter.tsx"
RESULTS_FILE = WORKTREE_ROOT / "tools" / ".c245_mutation_results.json"

MUTANTS = [
    # 1. fg==bg & border==bg collisions in APPROVAL_STATUS_CONFIG and badges (W1-W6)
    {
        "id": "W1",
        "desc": "pending config: fg==bg collision (color: var(--color-bg-subtle))",
        "target": "  pending: {\n    bg: 'var(--color-bg-subtle)',\n    color: 'var(--color-status-degraded)',\n    border: 'var(--color-status-degraded)',\n    label: 'PENDING',\n  },",
        "replacement": "  pending: {\n    bg: 'var(--color-bg-subtle)',\n    color: 'var(--color-bg-subtle)',\n    border: 'var(--color-status-degraded)',\n    label: 'PENDING',\n  },",
    },
    {
        "id": "W2",
        "desc": "pending config: border==bg collision (border: var(--color-bg-subtle))",
        "target": "  pending: {\n    bg: 'var(--color-bg-subtle)',\n    color: 'var(--color-status-degraded)',\n    border: 'var(--color-status-degraded)',\n    label: 'PENDING',\n  },",
        "replacement": "  pending: {\n    bg: 'var(--color-bg-subtle)',\n    color: 'var(--color-status-degraded)',\n    border: 'var(--color-bg-subtle)',\n    label: 'PENDING',\n  },",
    },
    {
        "id": "W3",
        "desc": "approved config: fg==bg collision (color: var(--color-bg-subtle))",
        "target": "  approved: {\n    bg: 'var(--color-bg-subtle)',\n    color: 'var(--color-status-online)',\n    border: 'var(--color-status-online)',\n    label: 'APPROVED',\n  },",
        "replacement": "  approved: {\n    bg: 'var(--color-bg-subtle)',\n    color: 'var(--color-bg-subtle)',\n    border: 'var(--color-status-online)',\n    label: 'APPROVED',\n  },",
    },
    {
        "id": "W4",
        "desc": "approved config: border==bg collision (border: var(--color-bg-subtle))",
        "target": "  approved: {\n    bg: 'var(--color-bg-subtle)',\n    color: 'var(--color-status-online)',\n    border: 'var(--color-status-online)',\n    label: 'APPROVED',\n  },",
        "replacement": "  approved: {\n    bg: 'var(--color-bg-subtle)',\n    color: 'var(--color-status-online)',\n    border: 'var(--color-bg-subtle)',\n    label: 'APPROVED',\n  },",
    },
    {
        "id": "W5",
        "desc": "two-person badge: fg==bg collision (color: bg-subtle)",
        "target": "color: isWaitingSecond ? 'var(--color-brand-hover)' : 'var(--color-text-secondary)',",
        "replacement": "color: isWaitingSecond ? 'var(--color-bg-subtle)' : 'var(--color-text-secondary)',",
    },
    {
        "id": "W6",
        "desc": "two-person badge: border==bg collision (border: bg-subtle)",
        "target": "border: isWaitingSecond ? '1px solid var(--color-brand-hover)' : '1px solid var(--color-border-subtle)',",
        "replacement": "border: isWaitingSecond ? '1px solid var(--color-bg-subtle)' : '1px solid var(--color-border-subtle)',",
    },

    # 2. text token as bg, stale warning collisions (W7-W10)
    {
        "id": "W7",
        "desc": "dispatched config: text token as bg (bg: var(--color-text-primary))",
        "target": "  dispatched: {\n    bg: 'var(--color-bg-subtle)',\n    color: 'var(--color-brand-hover)',\n    border: 'var(--color-brand-hover)',\n    label: 'DISPATCHED',\n  },",
        "replacement": "  dispatched: {\n    bg: 'var(--color-text-primary)',\n    color: 'var(--color-brand-hover)',\n    border: 'var(--color-brand-hover)',\n    label: 'DISPATCHED',\n  },",
    },
    {
        "id": "W8",
        "desc": "freshness indicator: text token as bg (backgroundColor: text-primary)",
        "target": "              backgroundColor: 'var(--color-brand-subtle)',\n              border: '1px solid var(--color-brand-hover)',\n              fontSize: '0.75rem',\n              color: 'var(--color-brand-hover)',",
        "replacement": "              backgroundColor: 'var(--color-text-primary)',\n              border: '1px solid var(--color-brand-hover)',\n              fontSize: '0.75rem',\n              color: 'var(--color-brand-hover)',",
    },
    {
        "id": "W9",
        "desc": "stale warning banner: fg==bg collision (backgroundColor: offline)",
        "target": "            backgroundColor: 'var(--color-bg-subtle)',\n            border: '1px solid var(--color-status-offline)',\n            borderRadius: 'var(--radius-md)',\n            color: 'var(--color-status-offline)',",
        "replacement": "            backgroundColor: 'var(--color-status-offline)',\n            border: '1px solid var(--color-status-offline)',\n            borderRadius: 'var(--radius-md)',\n            color: 'var(--color-status-offline)',",
    },
    {
        "id": "W10",
        "desc": "stale warning banner: border==bg collision (border: bg-subtle)",
        "target": "            backgroundColor: 'var(--color-bg-subtle)',\n            border: '1px solid var(--color-status-offline)',\n            borderRadius: 'var(--radius-md)',\n            color: 'var(--color-status-offline)',",
        "replacement": "            backgroundColor: 'var(--color-bg-subtle)',\n            border: '1px solid var(--color-bg-subtle)',\n            borderRadius: 'var(--radius-md)',\n            color: 'var(--color-status-offline)',",
    },

    # 3. opacity degradations (W11-W14)
    {
        "id": "W11",
        "desc": "status badge: opacity degradation (opacity: 0.4)",
        "target": "                        <span\n                          data-testid={`approval-status-${item.id}`}\n                          style={{\n                            fontSize: '0.6875rem',",
        "replacement": "                        <span\n                          data-testid={`approval-status-${item.id}`}\n                          style={{\n                            opacity: 0.4,\n                            fontSize: '0.6875rem',",
    },
    {
        "id": "W12",
        "desc": "two-person badge: opacity degradation (opacity: 0.35)",
        "target": "                          <span\n                            data-testid={`approval-two-person-${item.id}`}\n                            style={{\n                              fontSize: '0.625rem',",
        "replacement": "                          <span\n                            data-testid={`approval-two-person-${item.id}`}\n                            style={{\n                              opacity: 0.35,\n                              fontSize: '0.625rem',",
    },
    {
        "id": "W13",
        "desc": "pending badge: opacity degradation (opacity: 0.45)",
        "target": "                            border: `1px solid ${statusCfg.border}`,\n                          }}",
        "replacement": "                            border: `1px solid ${statusCfg.border}`,\n                            opacity: item.status === 'pending' ? 0.45 : 1,\n                          }}",
    },
    {
        "id": "W14",
        "desc": "two-person badge: unstarted opacity degradation (opacity: 0.5)",
        "target": "                              border: isWaitingSecond ? '1px solid var(--color-brand-hover)' : '1px solid var(--color-border-subtle)',\n                            }}",
        "replacement": "                              border: isWaitingSecond ? '1px solid var(--color-brand-hover)' : '1px solid var(--color-border-subtle)',\n                              opacity: 0.5,\n                            }}",
    },

    # 4. comment decoys with legacy hexes (W15-W16)
    {
        "id": "W15",
        "desc": "dispatched config: comment decoy with legacy hex",
        "target": "    color: 'var(--color-brand-hover)',\n    border: 'var(--color-brand-hover)',\n    label: 'DISPATCHED',",
        "replacement": "    color: 'var(--color-brand-hover) /* #93c5fd */',\n    border: 'var(--color-brand-hover)',\n    label: 'DISPATCHED',",
    },
    {
        "id": "W16",
        "desc": "rejected config: comment decoy with legacy hex",
        "target": "    color: 'var(--color-status-offline)',\n    border: 'var(--color-status-offline)',\n    label: 'REJECTED',",
        "replacement": "    color: 'var(--color-status-offline) /* #fca5a5 */',\n    border: 'var(--color-status-offline)',\n    label: 'REJECTED',",
    },

    # 5. legacy literal reverts (W17-W20)
    {
        "id": "W17",
        "desc": "freshness indicator: revert text to legacy #93c5fd",
        "target": "              backgroundColor: 'var(--color-brand-subtle)',\n              border: '1px solid var(--color-brand-hover)',\n              fontSize: '0.75rem',\n              color: 'var(--color-brand-hover)',",
        "replacement": "              backgroundColor: 'var(--color-brand-subtle)',\n              border: '1px solid var(--color-brand-hover)',\n              fontSize: '0.75rem',\n              color: '#93c5fd',",
    },
    {
        "id": "W18",
        "desc": "stale warning banner: revert border to legacy #fca5a5",
        "target": "            backgroundColor: 'var(--color-bg-subtle)',\n            border: '1px solid var(--color-status-offline)',\n            borderRadius: 'var(--radius-md)',\n            color: 'var(--color-status-offline)',",
        "replacement": "            backgroundColor: 'var(--color-bg-subtle)',\n            border: '1px solid #fca5a5',\n            borderRadius: 'var(--radius-md)',\n            color: 'var(--color-status-offline)',",
    },
    {
        "id": "W19",
        "desc": "stale warning note: revert color to legacy #fed7aa",
        "target": "          <div style={{ marginTop: '4px', fontSize: '0.75rem', color: 'var(--color-status-offline)' }}>",
        "replacement": "          <div style={{ marginTop: '4px', fontSize: '0.75rem', color: '#fed7aa' }}>",
    },
    {
        "id": "W20",
        "desc": "error retry button: revert bg to legacy #3b82f6",
        "target": "              onClick={() => onRefresh()}\n              style={{\n                padding: '6px 14px',\n                fontSize: '0.75rem',\n                backgroundColor: 'var(--color-bg-subtle)',\n                color: 'var(--color-text-primary)',",
        "replacement": "              onClick={() => onRefresh()}\n              style={{\n                padding: '6px 14px',\n                fontSize: '0.75rem',\n                backgroundColor: '#3b82f6',\n                color: 'var(--color-text-primary)',",
    },

    # 6. status color collapses (W21-W23)
    {
        "id": "W21",
        "desc": "pending config: degraded color collapsed to status-online",
        "target": "  pending: {\n    bg: 'var(--color-bg-subtle)',\n    color: 'var(--color-status-degraded)',\n    border: 'var(--color-status-degraded)',\n    label: 'PENDING',\n  },",
        "replacement": "  pending: {\n    bg: 'var(--color-bg-subtle)',\n    color: 'var(--color-status-online)',\n    border: 'var(--color-status-degraded)',\n    label: 'PENDING',\n  },",
    },
    {
        "id": "W22",
        "desc": "expired config: offline color collapsed to status-online",
        "target": "  expired: {\n    bg: 'var(--color-bg-subtle)',\n    color: 'var(--color-status-offline)',\n    border: 'var(--color-status-offline)',\n    label: 'EXPIRED',\n  },",
        "replacement": "  expired: {\n    bg: 'var(--color-bg-subtle)',\n    color: 'var(--color-status-online)',\n    border: 'var(--color-status-offline)',\n    label: 'EXPIRED',\n  },",
    },
    {
        "id": "W23",
        "desc": "rejected config: offline color collapsed to status-online",
        "target": "  rejected: {\n    bg: 'var(--color-bg-subtle)',\n    color: 'var(--color-status-offline)',\n    border: 'var(--color-status-offline)',\n    label: 'REJECTED',\n  },",
        "replacement": "  rejected: {\n    bg: 'var(--color-bg-subtle)',\n    color: 'var(--color-status-online)',\n    border: 'var(--color-status-offline)',\n    label: 'REJECTED',\n  },",
    },

    # 7. label & text mutations (W24-W26)
    {
        "id": "W24",
        "desc": "pending config: label mutated to '대기중'",
        "target": "    border: 'var(--color-status-degraded)',\n    label: 'PENDING',\n  },",
        "replacement": "    border: 'var(--color-status-degraded)',\n    label: '대기중',\n  },",
    },
    {
        "id": "W25",
        "desc": "two-person badge: text mutated to '1차 완료'",
        "target": "{isWaitingSecond ? '1/2 승인 (2차 대기)' : '2인 필수'}",
        "replacement": "{isWaitingSecond ? '1차 완료' : '2인 필수'}",
    },
    {
        "id": "W26",
        "desc": "error retry button: text mutated to '다시 시도'",
        "target": "            >\n              🔄 재시도 (Retry)\n            </button>",
        "replacement": "            >\n              다시 시도\n            </button>",
    },

    # 8. outline suppressions (W27-W30)
    {
        "id": "W27",
        "desc": "refresh button: outline: 'none' suppressing focus ring",
        "target": "              style={{\n                padding: '6px 12px',\n                fontSize: '0.75rem',",
        "replacement": "              style={{\n                outline: 'none',\n                padding: '6px 12px',\n                fontSize: '0.75rem',",
    },
    {
        "id": "W28",
        "desc": "error retry button: outline: 'none' suppressing focus ring",
        "target": "              style={{\n                padding: '6px 14px',\n                fontSize: '0.75rem',",
        "replacement": "              style={{\n                outline: 'none',\n                padding: '6px 14px',\n                fontSize: '0.75rem',",
    },
    {
        "id": "W29",
        "desc": "refresh button: outline: 0 suppressing focus ring",
        "target": "              style={{\n                padding: '6px 12px',\n                fontSize: '0.75rem',",
        "replacement": "              style={{\n                outline: 0,\n                padding: '6px 12px',\n                fontSize: '0.75rem',",
    },
    {
        "id": "W30",
        "desc": "error retry button: outlineWidth: '0px' suppressing focus ring",
        "target": "              style={{\n                padding: '6px 14px',\n                fontSize: '0.75rem',",
        "replacement": "              style={{\n                outlineWidth: '0px',\n                padding: '6px 14px',\n                fontSize: '0.75rem',",
    },

    # 9. fail-closed own-key bypasses (W31-W33)
    {
        "id": "W31",
        "desc": "fail-closed: bypass Object.hasOwn with in operator",
        "target": "  if (status && typeof status === 'string' && Object.hasOwn(APPROVAL_STATUS_CONFIG, status)) {",
        "replacement": "  if (status && typeof status === 'string' && (status in APPROVAL_STATUS_CONFIG)) {",
    },
    {
        "id": "W32",
        "desc": "fail-closed: prototype key hijack with plain indexing lookup",
        "target": "  if (status && typeof status === 'string' && Object.hasOwn(APPROVAL_STATUS_CONFIG, status)) {\n    return APPROVAL_STATUS_CONFIG[status as keyof typeof APPROVAL_STATUS_CONFIG];\n  }",
        "replacement": "  if (status && typeof status === 'string' && (APPROVAL_STATUS_CONFIG as any)[status]) {\n    return APPROVAL_STATUS_CONFIG[status as keyof typeof APPROVAL_STATUS_CONFIG];\n  }",
    },
    {
        "id": "W33",
        "desc": "fail-closed: fallback returns approved color instead of unknown",
        "target": "  return {\n    bg: 'var(--color-bg-subtle)',\n    color: 'var(--color-status-unknown)',\n    border: 'var(--color-status-unknown)',\n    label: raw ? `UNKNOWN (${raw})` : 'UNKNOWN',\n  };",
        "replacement": "  return {\n    bg: 'var(--color-bg-subtle)',\n    color: 'var(--color-status-online)',\n    border: 'var(--color-status-online)',\n    label: raw ? `UNKNOWN (${raw})` : 'UNKNOWN',\n  };",
    },

    # 10. out-of-contract status mapping (W34-W35)
    {
        "id": "W34",
        "desc": "contract bypass: map out-of-contract 'admitted' to approved",
        "target": "  if (status && typeof status === 'string' && Object.hasOwn(APPROVAL_STATUS_CONFIG, status)) {\n    return APPROVAL_STATUS_CONFIG[status as keyof typeof APPROVAL_STATUS_CONFIG];\n  }",
        "replacement": "  if (status && typeof status === 'string' && (Object.hasOwn(APPROVAL_STATUS_CONFIG, status) || status === 'admitted')) {\n    return status === 'admitted' ? APPROVAL_STATUS_CONFIG.approved : APPROVAL_STATUS_CONFIG[status as keyof typeof APPROVAL_STATUS_CONFIG];\n  }",
    },
    {
        "id": "W35",
        "desc": "contract bypass: drop approved out of contract to unknown",
        "target": "  if (status && typeof status === 'string' && Object.hasOwn(APPROVAL_STATUS_CONFIG, status)) {",
        "replacement": "  if (status && typeof status === 'string' && Object.hasOwn(APPROVAL_STATUS_CONFIG, status) && status !== 'approved') {",
    },

    # 11. named color injections (W36-W37)
    {
        "id": "W36",
        "desc": "named color: status badge border injected with yellow",
        "target": "                            border: `1px solid ${statusCfg.border}`,\n                          }}",
        "replacement": "                            border: '1px solid yellow',\n                          }}",
    },
    {
        "id": "W37",
        "desc": "named color: error banner color injected with red",
        "target": "            border: '1px solid var(--color-status-offline)',\n            borderRadius: 'var(--radius-md)',\n            color: 'var(--color-status-offline)',\n            fontSize: '0.8125rem',",
        "replacement": "            border: '1px solid var(--color-status-offline)',\n            borderRadius: 'var(--radius-md)',\n            color: 'red',\n            fontSize: '0.8125rem',",
    },

    # 12. prefix removal, uppercase bypass, case-insensitive lookup (W38-W40)
    {
        "id": "W38",
        "desc": "unknown label: remove 'UNKNOWN (' prefix",
        "target": "    label: raw ? `UNKNOWN (${raw})` : 'UNKNOWN',",
        "replacement": "    label: raw ? `${raw}` : 'UNKNOWN',",
    },
    {
        "id": "W39",
        "desc": "unknown label: bypass UNKNOWN format and return raw uppercase",
        "target": "    label: raw ? `UNKNOWN (${raw})` : 'UNKNOWN',",
        "replacement": "    label: raw ? raw.toUpperCase() : 'UNKNOWN',",
    },
    {
        "id": "W40",
        "desc": "case-insensitive lookup: toLowerCase() lookup bypass",
        "target": "  if (status && typeof status === 'string' && Object.hasOwn(APPROVAL_STATUS_CONFIG, status)) {\n    return APPROVAL_STATUS_CONFIG[status as keyof typeof APPROVAL_STATUS_CONFIG];\n  }",
        "replacement": "  const lookupKey = typeof status === 'string' ? status.toLowerCase() : '';\n  if (lookupKey && Object.hasOwn(APPROVAL_STATUS_CONFIG, lookupKey)) {\n    return APPROVAL_STATUS_CONFIG[lookupKey as keyof typeof APPROVAL_STATUS_CONFIG];\n  }",
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


def run_tsc_check():
    cmd = [
        "npx.cmd" if os.name == "nt" else "npx",
        "tsc",
        "-b",
    ]
    res = subprocess.run(
        cmd,
        cwd=str(APPS_WEB),
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True,
        encoding="utf-8",
        errors="replace",
    )
    return res.returncode == 0, res.stdout + res.stderr


def apply_mutation(target_text, replacement_text):
    content = TARGET_FILE.read_text(encoding="utf-8")
    if target_text not in content:
        raise ValueError("Target pattern not found in file")
    new_content = content.replace(target_text, replacement_text, 1)
    TARGET_FILE.write_text(new_content, encoding="utf-8", newline="")


def restore_file(original_bytes):
    TARGET_FILE.write_bytes(original_bytes)
    restored_bytes = TARGET_FILE.read_bytes()
    if restored_bytes != original_bytes:
        raise RuntimeError(f"Byte mismatch after restoration of {TARGET_FILE}! Expected {len(original_bytes)} bytes, got {len(restored_bytes)} bytes")
    # Verify git diff
    res = subprocess.run(
        ["git", "diff", "--exit-code", str(TARGET_FILE)],
        cwd=str(WORKTREE_ROOT),
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
    )
    if res.returncode != 0:
        raise RuntimeError(f"Git diff non-zero after restoration of {TARGET_FILE}")


def test_mutant(mutant, original_bytes, timeout=120):
    mutant_id = mutant["id"]
    desc = mutant["desc"]
    
    print(f"\n--- Testing Mutant {mutant_id}: {desc} ---")
    try:
        apply_mutation(mutant["target"], mutant["replacement"])
    except Exception as e:
        print(f"  [ERROR] Failed to apply mutation: {e}")
        return {
            "id": mutant_id,
            "desc": desc,
            "status": "ERROR",
            "reason": str(e),
            "killed": False,
        }

    # Verify compilation
    compiled_ok, tsc_out = run_tsc_check()
    if not compiled_ok:
        print(f"  [COMPILATION FAILED] Mutant does not compile under TypeScript!")
        restore_file(original_bytes)
        return {
            "id": mutant_id,
            "desc": desc,
            "status": "TSC_FAIL",
            "killed": False,
            "output": tsc_out[:300],
        }

    retcode, stdout, stderr, timed_out = run_vitest_acc09(timeout=timeout)
    restore_file(original_bytes)

    if timed_out:
        print(f"  [TIMEOUT] Execution timed out after {timeout}s (NOT counted as killed)")
        return {
            "id": mutant_id,
            "desc": desc,
            "status": "TIMEOUT",
            "killed": False,
        }

    if retcode != 0:
        # Vitest failed -> mutant was killed!
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
        }
    else:
        print(f"  [SURVIVED] Vitest passed! Mutant was NOT killed!")
        return {
            "id": mutant_id,
            "desc": desc,
            "status": "SURVIVED",
            "killed": False,
        }


def main():
    parser = argparse.ArgumentParser(description="Test Card 245 mutations on ApprovalCenter.tsx")
    parser.add_argument("--batch", type=int, choices=[1, 2, 3, 4, 5], help="Run specific batch (1-5, 8 per batch)")
    parser.add_argument("--mutant", type=str, help="Run single mutant by ID (e.g. W1)")
    parser.add_argument("--all", action="store_true", help="Run all 40 mutants sequentially")
    parser.add_argument("--verify-targets", action="store_true", help="Verify all targets exist in file")
    parser.add_argument("--timeout", type=int, default=120, help="Per-mutant vitest timeout in seconds")
    args = parser.parse_args()

    original_bytes = TARGET_FILE.read_bytes()
    original_content = original_bytes.decode("utf-8")

    if args.verify_targets:
        print("Verifying all mutation targets exist in target file...")
        missing = 0
        for m in MUTANTS:
            if m["target"] not in original_content:
                print(f"  [MISSING] {m['id']}: {m['desc']}")
                missing += 1
            else:
                print(f"  [FOUND] {m['id']}")
        if missing == 0:
            print(f"All {len(MUTANTS)} mutant targets verified!")
            return 0
        else:
            print(f"{missing} mutant targets missing!")
            return 1

    selected_mutants = []
    if args.mutant:
        selected_mutants = [m for m in MUTANTS if m["id"] == args.mutant.upper()]
        if not selected_mutants:
            print(f"Mutant {args.mutant} not found.")
            return 1
    elif args.batch:
        batch_size = 8
        start_idx = (args.batch - 1) * batch_size
        end_idx = start_idx + batch_size
        selected_mutants = MUTANTS[start_idx:end_idx]
        print(f"Running Batch {args.batch} ({len(selected_mutants)} mutants: {selected_mutants[0]['id']}..{selected_mutants[-1]['id']})")
    elif args.all:
        selected_mutants = MUTANTS
        print(f"Running all {len(selected_mutants)} mutants...")
    else:
        parser.print_help()
        return 0

    results = []
    if RESULTS_FILE.exists():
        try:
            raw = json.loads(RESULTS_FILE.read_text(encoding="utf-8"))
            if isinstance(raw, dict) and "mutations" in raw:
                results = raw["mutations"]
            elif isinstance(raw, list):
                results = raw
        except Exception:
            results = []

    res_dict = {r["id"]: r for r in results}

    for m in selected_mutants:
        res = test_mutant(m, original_bytes, timeout=args.timeout)
        res_dict[m["id"]] = res
        all_res = list(res_dict.values())
        killed_count = sum(1 for r in all_res if r.get("killed"))
        survived_count = sum(1 for r in all_res if r.get("status") == "SURVIVED")
        timeouts_count = sum(1 for r in all_res if r.get("status") == "TIMEOUT")
        tsc_fails_count = sum(1 for r in all_res if r.get("status") == "TSC_FAIL")
        head_sha = subprocess.check_output(["git", "rev-parse", "HEAD"], cwd=str(WORKTREE_ROOT), text=True).strip()
        payload = {
            "sourceHeadSha": head_sha,
            "observedAt": datetime.now(timezone.utc).isoformat(),
            "total": len(MUTANTS),
            "killed": killed_count,
            "survived": survived_count,
            "timeouts": timeouts_count,
            "tsc_fails": tsc_fails_count,
            "mutations": all_res,
        }
        RESULTS_FILE.write_text(json.dumps(payload, indent=2, ensure_ascii=False) + "\n", encoding="utf-8", newline="")

    all_res = list(res_dict.values())
    total_tested = len(all_res)
    killed = sum(1 for r in all_res if r.get("killed"))
    survived = sum(1 for r in all_res if r.get("status") == "SURVIVED")
    timeouts = sum(1 for r in all_res if r.get("status") == "TIMEOUT")
    tsc_fails = sum(1 for r in all_res if r.get("status") == "TSC_FAIL")

    print("\n" + "=" * 60)
    print(f"MUTATION TESTING SUMMARY ({total_tested} tested)")
    print(f"  KILLED:   {killed}")
    print(f"  SURVIVED: {survived}")
    print(f"  TIMEOUT:  {timeouts}")
    print(f"  TSC_FAIL: {tsc_fails}")
    print("=" * 60)

    if killed == len(MUTANTS):
        print("ALL 40 MUTANTS KILLED! (100.0% kill rate)")
        return 0
    elif survived > 0 or timeouts > 0 or tsc_fails > 0:
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
