#!/usr/bin/env python3
"""
tools/test_c248_mutations.py:
Verification runner for 40 accessibility, contrast, contract, and fail-closed mutants (W1-W40)
targeting ClusterOverview.tsx.

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
TARGET_FILE = APPS_WEB / "src" / "features" / "dashboard" / "ClusterOverview.tsx"
RESULTS_FILE = WORKTREE_ROOT / "tools" / ".c248_mutation_results.json"

MUTANTS = [
    # 1. fg==bg collisions in NODE_STATUS_CONFIG (W1-W6)
    {
        "id": "W1",
        "desc": "online config: fg==bg collision (color: var(--color-bg-canvas))",
        "target": "  online: {\n    color: 'var(--color-status-online)',\n    label: 'ONLINE',\n  },",
        "replacement": "  online: {\n    color: 'var(--color-bg-canvas)',\n    label: 'ONLINE',\n  },",
    },
    {
        "id": "W2",
        "desc": "active config: fg==bg collision (color: var(--color-bg-canvas))",
        "target": "  active: {\n    color: 'var(--color-status-active)',\n    label: 'ACTIVE (활성 · 헬스 미결정)',\n  },",
        "replacement": "  active: {\n    color: 'var(--color-bg-canvas)',\n    label: 'ACTIVE (활성 · 헬스 미결정)',\n  },",
    },
    {
        "id": "W3",
        "desc": "degraded config: fg==bg collision (color: var(--color-bg-canvas))",
        "target": "  degraded: {\n    color: 'var(--color-status-degraded)',\n    label: 'DEGRADED',\n  },",
        "replacement": "  degraded: {\n    color: 'var(--color-bg-canvas)',\n    label: 'DEGRADED',\n  },",
    },
    {
        "id": "W4",
        "desc": "lost config: fg==bg collision (color: var(--color-bg-canvas))",
        "target": "  lost: {\n    color: 'var(--color-status-lost)',\n    label: 'LOST (단절)',\n  },",
        "replacement": "  lost: {\n    color: 'var(--color-bg-canvas)',\n    label: 'LOST (단절)',\n  },",
    },
    {
        "id": "W5",
        "desc": "unknown config: fg==bg collision (color: var(--color-bg-canvas))",
        "target": "  unknown: {\n    color: 'var(--color-status-unknown)',\n    label: 'UNKNOWN (미확인)',\n  },",
        "replacement": "  unknown: {\n    color: 'var(--color-bg-canvas)',\n    label: 'UNKNOWN (미확인)',\n  },",
    },
    {
        "id": "W6",
        "desc": "offline config: fg==bg collision (color: var(--color-bg-canvas))",
        "target": "  offline: {\n    color: 'var(--color-status-offline)',\n    label: 'OFFLINE',\n  },",
        "replacement": "  offline: {\n    color: 'var(--color-bg-canvas)',\n    label: 'OFFLINE',\n  },",
    },

    # 2. Gauge bars & recent run state (W7-W10)
    {
        "id": "W7",
        "desc": "ram gauge bar: fg==bg collision (backgroundColor: bg-canvas)",
        "target": "            <div\n              style={{\n                width: `${Math.round((usedRamGb / (totalRamGb || 1)) * 100)}%`,\n                height: '100%',\n                backgroundColor: 'var(--color-status-online)',\n              }}\n            />",
        "replacement": "            <div\n              style={{\n                width: `${Math.round((usedRamGb / (totalRamGb || 1)) * 100)}%`,\n                height: '100%',\n                backgroundColor: 'var(--color-bg-canvas)',\n              }}\n            />",
    },
    {
        "id": "W8",
        "desc": "vram gauge bar: fg==bg collision (backgroundColor: bg-canvas)",
        "target": "            <div\n              style={{\n                width: `${Math.round((usedVramGb / (totalVramGb || 1)) * 100)}%`,\n                height: '100%',\n                backgroundColor: 'var(--color-brand-hover)',\n              }}\n            />",
        "replacement": "            <div\n              style={{\n                width: `${Math.round((usedVramGb / (totalVramGb || 1)) * 100)}%`,\n                height: '100%',\n                backgroundColor: 'var(--color-bg-canvas)',\n              }}\n            />",
    },
    {
        "id": "W9",
        "desc": "storage gauge bar: fg==bg collision (backgroundColor: bg-canvas)",
        "target": "            <div\n              style={{\n                width: `${Math.round((Number(usedStorageTb) / (Number(totalStorageTb) || 1)) * 100)}%`,\n                height: '100%',\n                backgroundColor: 'var(--color-status-degraded)',\n              }}\n            />",
        "replacement": "            <div\n              style={{\n                width: `${Math.round((Number(usedStorageTb) / (Number(totalStorageTb) || 1)) * 100)}%`,\n                height: '100%',\n                backgroundColor: 'var(--color-bg-canvas)',\n              }}\n            />",
    },
    {
        "id": "W10",
        "desc": "recent run state: fg==bg collision (color: bg-canvas)",
        "target": "                  <span style={{ fontSize: '0.75rem', fontWeight: 600, color: 'var(--color-brand-hover)' }}>\n                    {run.state.toUpperCase()}\n                  </span>",
        "replacement": "                  <span style={{ fontSize: '0.75rem', fontWeight: 600, color: 'var(--color-bg-canvas)' }}>\n                    {run.state.toUpperCase()}\n                  </span>",
    },

    # 3. Error & warning banner collisions (W11-W14)
    {
        "id": "W11",
        "desc": "error banner: fg==bg collision (backgroundColor: offline)",
        "target": "          backgroundColor: 'var(--color-bg-surface)',\n          border: '1px solid var(--color-status-offline)',\n          borderRadius: 'var(--radius-lg)',\n          margin: '20px 0',",
        "replacement": "          backgroundColor: 'var(--color-status-offline)',\n          border: '1px solid var(--color-status-offline)',\n          borderRadius: 'var(--radius-lg)',\n          margin: '20px 0',",
    },
    {
        "id": "W12",
        "desc": "error banner: border==bg collision (border: bg-surface)",
        "target": "          backgroundColor: 'var(--color-bg-surface)',\n          border: '1px solid var(--color-status-offline)',\n          borderRadius: 'var(--radius-lg)',\n          margin: '20px 0',",
        "replacement": "          backgroundColor: 'var(--color-bg-surface)',\n          border: '1px solid var(--color-bg-surface)',\n          borderRadius: 'var(--radius-lg)',\n          margin: '20px 0',",
    },
    {
        "id": "W13",
        "desc": "stale warning: fg==bg collision (backgroundColor: offline)",
        "target": "            backgroundColor: 'var(--color-bg-subtle)',\n            border: '1px solid var(--color-status-offline)',\n            borderRadius: 'var(--radius-md)',\n            color: 'var(--color-status-offline)',\n            fontSize: '0.8125rem',",
        "replacement": "            backgroundColor: 'var(--color-status-offline)',\n            border: '1px solid var(--color-status-offline)',\n            borderRadius: 'var(--radius-md)',\n            color: 'var(--color-status-offline)',\n            fontSize: '0.8125rem',",
    },
    {
        "id": "W14",
        "desc": "stale warning: border==bg collision (border: bg-subtle)",
        "target": "            backgroundColor: 'var(--color-bg-subtle)',\n            border: '1px solid var(--color-status-offline)',\n            borderRadius: 'var(--radius-md)',\n            color: 'var(--color-status-offline)',\n            fontSize: '0.8125rem',",
        "replacement": "            backgroundColor: 'var(--color-bg-subtle)',\n            border: '1px solid var(--color-bg-subtle)',\n            borderRadius: 'var(--radius-md)',\n            color: 'var(--color-status-offline)',\n            fontSize: '0.8125rem',",
    },

    # 4. Opacity & comment decoys (W15-W18)
    {
        "id": "W15",
        "desc": "node status badge: opacity degradation (opacity: 0.35)",
        "target": "                  <span\n                    data-testid={`node-status-badge-${node.id}`}\n                    style={{\n                      fontSize: '0.75rem',",
        "replacement": "                  <span\n                    data-testid={`node-status-badge-${node.id}`}\n                    style={{\n                      opacity: 0.35,\n                      fontSize: '0.75rem',",
    },
    {
        "id": "W16",
        "desc": "stale warning: opacity degradation (opacity: 0.4)",
        "target": "            role=\"alert\"\n            data-testid=\"cluster-stale-warning\"\n            style={{\n              padding: '12px 16px',",
        "replacement": "            role=\"alert\"\n            data-testid=\"cluster-stale-warning\"\n            style={{\n              opacity: 0.4,\n              padding: '12px 16px',",
    },
    {
        "id": "W17",
        "desc": "online config: comment decoy with legacy hex #10b981",
        "target": "  online: {\n    color: 'var(--color-status-online)',\n    label: 'ONLINE',\n  },",
        "replacement": "  online: {\n    color: 'var(--color-status-online) /* #10b981 */',\n    label: 'ONLINE',\n  },",
    },
    {
        "id": "W18",
        "desc": "active config: comment decoy with legacy hex #38bdf8",
        "target": "  active: {\n    color: 'var(--color-status-active)',\n    label: 'ACTIVE (활성 · 헬스 미결정)',\n  },",
        "replacement": "  active: {\n    color: 'var(--color-status-active) /* #38bdf8 */',\n    label: 'ACTIVE (활성 · 헬스 미결정)',\n  },",
    },

    # 5. Revert to legacy hexes (W19-W26)
    {
        "id": "W19",
        "desc": "error heading: revert to legacy hex #fca5a5",
        "target": "        <h1 style={{ fontSize: '1.25rem', fontWeight: 600, color: 'var(--color-status-offline)', margin: '0 0 8px 0' }}>",
        "replacement": "        <h1 style={{ fontSize: '1.25rem', fontWeight: 600, color: '#fca5a5', margin: '0 0 8px 0' }}>",
    },
    {
        "id": "W20",
        "desc": "error retry button: revert bg to legacy hex #ef4444",
        "target": "              backgroundColor: 'var(--color-bg-subtle)',\n              color: 'var(--color-text-primary)',",
        "replacement": "              backgroundColor: '#ef4444',\n              color: 'var(--color-text-primary)',",
    },
    {
        "id": "W21",
        "desc": "heartbeat text: revert color to legacy hex #64748b",
        "target": "                      <div data-testid={`node-heartbeat-${node.id}`} style={{ fontSize: '0.6875rem', color: 'var(--color-text-muted)', marginTop: '2px' }}>",
        "replacement": "                      <div data-testid={`node-heartbeat-${node.id}`} style={{ fontSize: '0.6875rem', color: '#64748b', marginTop: '2px' }}>",
    },
    {
        "id": "W22",
        "desc": "active node config: revert color to legacy hex #38bdf8",
        "target": "  active: {\n    color: 'var(--color-status-active)',\n    label: 'ACTIVE (활성 · 헬스 미결정)',\n  },",
        "replacement": "  active: {\n    color: '#38bdf8',\n    label: 'ACTIVE (활성 · 헬스 미결정)',\n  },",
    },
    {
        "id": "W23",
        "desc": "degraded node config: revert color to legacy hex #d29922",
        "target": "  degraded: {\n    color: 'var(--color-status-degraded)',\n    label: 'DEGRADED',\n  },",
        "replacement": "  degraded: {\n    color: '#d29922',\n    label: 'DEGRADED',\n  },",
    },
    {
        "id": "W24",
        "desc": "ram gauge: revert bg to legacy hex #10b981",
        "target": "            <div\n              style={{\n                width: `${Math.round((usedRamGb / (totalRamGb || 1)) * 100)}%`,\n                height: '100%',\n                backgroundColor: 'var(--color-status-online)',\n              }}\n            />",
        "replacement": "            <div\n              style={{\n                width: `${Math.round((usedRamGb / (totalRamGb || 1)) * 100)}%`,\n                height: '100%',\n                backgroundColor: '#10b981',\n              }}\n            />",
    },
    {
        "id": "W25",
        "desc": "vram gauge: revert bg to legacy hex #8b5cf6",
        "target": "            <div\n              style={{\n                width: `${Math.round((usedVramGb / (totalVramGb || 1)) * 100)}%`,\n                height: '100%',\n                backgroundColor: 'var(--color-brand-hover)',\n              }}\n            />",
        "replacement": "            <div\n              style={{\n                width: `${Math.round((usedVramGb / (totalVramGb || 1)) * 100)}%`,\n                height: '100%',\n                backgroundColor: '#8b5cf6',\n              }}\n            />",
    },
    {
        "id": "W26",
        "desc": "storage gauge: revert bg to legacy hex #f59e0b",
        "target": "            <div\n              style={{\n                width: `${Math.round((Number(usedStorageTb) / (Number(totalStorageTb) || 1)) * 100)}%`,\n                height: '100%',\n                backgroundColor: 'var(--color-status-degraded)',\n              }}\n            />",
        "replacement": "            <div\n              style={{\n                width: `${Math.round((Number(usedStorageTb) / (Number(totalStorageTb) || 1)) * 100)}%`,\n                height: '100%',\n                backgroundColor: '#f59e0b',\n              }}\n            />",
    },

    # 6. Focus ring suppression (W27-W30)
    {
        "id": "W27",
        "desc": "refresh button: outline: 'none' suppressing focus ring",
        "target": "                  border: '1px solid var(--color-border-subtle)',\n                  borderRadius: 'var(--radius-sm)',\n                  cursor: 'pointer',\n                  color: 'var(--color-text-secondary)',\n                }}",
        "replacement": "                  border: '1px solid var(--color-border-subtle)',\n                  borderRadius: 'var(--radius-sm)',\n                  cursor: 'pointer',\n                  color: 'var(--color-text-secondary)',\n                  outline: 'none',\n                }}",
    },
    {
        "id": "W28",
        "desc": "error retry button: outline: 'none' suppressing focus ring",
        "target": "              border: '1px solid var(--color-border-subtle)',\n              borderRadius: 'var(--radius-md)',\n              fontWeight: 600,\n              cursor: 'pointer',\n            }}",
        "replacement": "              border: '1px solid var(--color-border-subtle)',\n              borderRadius: 'var(--radius-md)',\n              fontWeight: 600,\n              cursor: 'pointer',\n              outline: 'none',\n            }}",
    },
    {
        "id": "W29",
        "desc": "refresh button: outline: 0 suppressing focus ring",
        "target": "                  border: '1px solid var(--color-border-subtle)',\n                  borderRadius: 'var(--radius-sm)',\n                  cursor: 'pointer',\n                  color: 'var(--color-text-secondary)',\n                }}",
        "replacement": "                  border: '1px solid var(--color-border-subtle)',\n                  borderRadius: 'var(--radius-sm)',\n                  cursor: 'pointer',\n                  color: 'var(--color-text-secondary)',\n                  outline: 0,\n                }}",
    },
    {
        "id": "W30",
        "desc": "error retry button: outlineWidth: '0px' suppressing focus ring",
        "target": "              border: '1px solid var(--color-border-subtle)',\n              borderRadius: 'var(--radius-md)',\n              fontWeight: 600,\n              cursor: 'pointer',\n            }}",
        "replacement": "              border: '1px solid var(--color-border-subtle)',\n              borderRadius: 'var(--radius-md)',\n              fontWeight: 600,\n              cursor: 'pointer',\n              outlineWidth: '0px',\n            }}",
    },

    # 7. Fail-closed contract & prototype defense (W31-W35)
    {
        "id": "W31",
        "desc": "fail-closed: bypass Object.hasOwn with in operator",
        "target": "  if (status && typeof status === 'string' && Object.hasOwn(NODE_STATUS_CONFIG, status)) {",
        "replacement": "  if (status && typeof status === 'string' && (status in NODE_STATUS_CONFIG)) {",
    },
    {
        "id": "W32",
        "desc": "fail-closed: prototype key hijack with direct indexing lookup",
        "target": "  if (status && typeof status === 'string' && Object.hasOwn(NODE_STATUS_CONFIG, status)) {\n    return NODE_STATUS_CONFIG[status as keyof typeof NODE_STATUS_CONFIG];\n  }",
        "replacement": "  if (status && typeof status === 'string' && ((NODE_STATUS_CONFIG as any)[status] || Object.hasOwn(NODE_STATUS_CONFIG, status))) {\n    return (NODE_STATUS_CONFIG as any)[status] || NODE_STATUS_CONFIG[status as keyof typeof NODE_STATUS_CONFIG];\n  }",
    },
    {
        "id": "W33",
        "desc": "fail-closed: fallback returns online color instead of unknown",
        "target": "  return {\n    color: 'var(--color-status-unknown)',\n    label: raw ? `UNKNOWN (${raw})` : 'UNKNOWN',\n  };",
        "replacement": "  return {\n    color: 'var(--color-status-online)',\n    label: raw ? `UNKNOWN (${raw})` : 'UNKNOWN',\n  };",
    },
    {
        "id": "W34",
        "desc": "contract bypass: map out-of-contract 'admitted' to online",
        "target": "  if (status && typeof status === 'string' && Object.hasOwn(NODE_STATUS_CONFIG, status)) {\n    return NODE_STATUS_CONFIG[status as keyof typeof NODE_STATUS_CONFIG];\n  }",
        "replacement": "  if (status === 'admitted') return NODE_STATUS_CONFIG['online'];\n  if (status && typeof status === 'string' && Object.hasOwn(NODE_STATUS_CONFIG, status)) {\n    return NODE_STATUS_CONFIG[status as keyof typeof NODE_STATUS_CONFIG];\n  }",
    },
    {
        "id": "W35",
        "desc": "contract bypass: drop online out of contract to unknown",
        "target": "  if (status && typeof status === 'string' && Object.hasOwn(NODE_STATUS_CONFIG, status)) {\n    return NODE_STATUS_CONFIG[status as keyof typeof NODE_STATUS_CONFIG];\n  }",
        "replacement": "  if (status && typeof status === 'string' && status !== 'online' && Object.hasOwn(NODE_STATUS_CONFIG, status)) {\n    return NODE_STATUS_CONFIG[status as keyof typeof NODE_STATUS_CONFIG];\n  }",
    },

    # 8. Labels, icons, and casing defense (W36-W40)
    {
        "id": "W36",
        "desc": "unknown label: remove 'UNKNOWN (' prefix",
        "target": "    label: raw ? `UNKNOWN (${raw})` : 'UNKNOWN',",
        "replacement": "    label: raw ? `(${raw})` : 'UNKNOWN',",
    },
    {
        "id": "W37",
        "desc": "unknown label: return raw uppercase directly",
        "target": "    label: raw ? `UNKNOWN (${raw})` : 'UNKNOWN',",
        "replacement": "    label: raw ? raw.toUpperCase() : 'UNKNOWN',",
    },
    {
        "id": "W38",
        "desc": "case-insensitive lookup: toLowerCase() lookup bypass",
        "target": "  if (status && typeof status === 'string' && Object.hasOwn(NODE_STATUS_CONFIG, status)) {",
        "replacement": "  const sKey = typeof status === 'string' ? status.toLowerCase() : status;\n  if (sKey && typeof sKey === 'string' && Object.hasOwn(NODE_STATUS_CONFIG, sKey)) {",
    },
    {
        "id": "W39",
        "desc": "error heading text: mutated to '클러스터 에러 발생'",
        "target": "        <h1 style={{ fontSize: '1.25rem', fontWeight: 600, color: 'var(--color-status-offline)', margin: '0 0 8px 0' }}>\n          클러스터 노드 동기화 실패\n        </h1>",
        "replacement": "        <h1 style={{ fontSize: '1.25rem', fontWeight: 600, color: 'var(--color-status-offline)', margin: '0 0 8px 0' }}>\n          클러스터 에러 발생\n        </h1>",
    },
    {
        "id": "W40",
        "desc": "stale warning: remove '⚠️' icon",
        "target": "        >\n          ⚠️ [동기화 실패] 클러스터 노드 동기화에 실패했습니다 ({nodeError || '통신 오류'}).",
        "replacement": "        >\n          [동기화 실패] 클러스터 노드 동기화에 실패했습니다 ({nodeError || '통신 오류'}).",
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


def test_mutant(mutant, original_bytes, timeout=120, head_sha=""):
    mutant_id = mutant["id"]
    desc = mutant["desc"]
    observed_time = datetime.now(timezone.utc).isoformat()

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
            "sourceHeadSha": head_sha,
            "observedAt": observed_time,
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
            "sourceHeadSha": head_sha,
            "observedAt": observed_time,
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
            "sourceHeadSha": head_sha,
            "observedAt": observed_time,
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
    parser = argparse.ArgumentParser(description="Test Card 248 mutations on ClusterOverview.tsx")
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

    clean_head_sha = subprocess.check_output(["git", "rev-parse", "HEAD"], cwd=str(WORKTREE_ROOT), text=True).strip()
    status_proc = subprocess.check_output(["git", "status", "--porcelain"], cwd=str(WORKTREE_ROOT), text=True).strip()

    if args.all:
        if status_proc:
            print(f"[ERROR] Cannot run --all on a dirty working tree! git status --porcelain returned:\n{status_proc}")
            return 1
        selected_mutants = MUTANTS
        print(f"Running all {len(selected_mutants)} mutants sequentially on clean HEAD {clean_head_sha[:8]}...")
    elif args.batch:
        batch_size = 8
        start_idx = (args.batch - 1) * batch_size
        end_idx = start_idx + batch_size
        selected_mutants = MUTANTS[start_idx:end_idx]
        print(f"Running Batch {args.batch} ({len(selected_mutants)} mutants: {selected_mutants[0]['id']}..{selected_mutants[-1]['id']}) on HEAD {clean_head_sha[:8]}")
    elif args.mutant:
        selected_mutants = [m for m in MUTANTS if m["id"] == args.mutant.upper()]
        if not selected_mutants:
            print(f"Mutant {args.mutant} not found.")
            return 1
        print(f"Running Mutant {args.mutant.upper()} on HEAD {clean_head_sha[:8]}")
    else:
        parser.print_help()
        return 0

    # Only record results for this execution run (no merging of old runs)
    results = []

    for m in selected_mutants:
        res = test_mutant(m, original_bytes, timeout=args.timeout, head_sha=clean_head_sha)
        results.append(res)

        # ONLY write results file when running all mutants sequentially
        if args.all:
            killed_count = sum(1 for r in results if r.get("killed"))
            survived_count = sum(1 for r in results if r.get("status") == "SURVIVED")
            timeouts_count = sum(1 for r in results if r.get("status") == "TIMEOUT")
            tsc_fails_count = sum(1 for r in results if r.get("status") == "TSC_FAIL")
            payload = {
                "sourceHeadSha": clean_head_sha,
                "observedAt": datetime.now(timezone.utc).isoformat(),
                "totalTested": len(results),
                "totalMutants": len(MUTANTS),
                "killed": killed_count,
                "survived": survived_count,
                "timeouts": timeouts_count,
                "tsc_fails": tsc_fails_count,
                "mutations": results,
            }
            RESULTS_FILE.write_text(json.dumps(payload, indent=2, ensure_ascii=False) + "\n", encoding="utf-8", newline="")

    total_tested = len(results)
    killed = sum(1 for r in results if r.get("killed"))
    survived = sum(1 for r in results if r.get("status") == "SURVIVED")
    timeouts = sum(1 for r in results if r.get("status") == "TIMEOUT")
    tsc_fails = sum(1 for r in results if r.get("status") == "TSC_FAIL")

    print("\n" + "=" * 60)
    print(f"MUTATION TESTING SUMMARY ({total_tested} tested in this execution)")
    print(f"  Source Head SHA : {clean_head_sha}")
    print(f"  KILLED          : {killed}")
    print(f"  SURVIVED        : {survived}")
    print(f"  TIMEOUT         : {timeouts}")
    print(f"  TSC_FAIL        : {tsc_fails}")
    print("=" * 60)

    if args.all and killed == len(MUTANTS):
        print("ALL 40 MUTANTS KILLED ON CLEAN HEAD! (100.0% verified kill rate)")
        return 0
    elif survived > 0 or timeouts > 0 or tsc_fails > 0:
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
