#!/usr/bin/env python3
"""
tools/test_c270_mutations.py:
Verification runner for 40 accessibility, contrast, contract, and fail-closed mutants (W1-W40)
targeting WorkspaceList.tsx.

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
TARGET_FILE = APPS_WEB / "src" / "features" / "workspaces" / "WorkspaceList.tsx"
RESULTS_FILE = WORKTREE_ROOT / "tools" / ".c270_mutation_results.json"

MUTANTS = [
    # 1. fg==bg collisions in WORKSPACE_STATUS_CONFIG (W1-W5)
    {
        "id": "W1",
        "desc": "ready config: fg==bg collision (color: var(--color-bg-subtle))",
        "target": "  ready: {\n    label: '준비 완료 (Ready)',\n    bg: 'var(--color-bg-subtle)',\n    color: 'var(--color-status-online)',\n    border: 'var(--color-status-online)',\n  },",
        "replacement": "  ready: {\n    label: '준비 완료 (Ready)',\n    bg: 'var(--color-bg-subtle)',\n    color: 'var(--color-bg-subtle)',\n    border: 'var(--color-status-online)',\n  },",
    },
    {
        "id": "W2",
        "desc": "provisioning config: fg==bg collision (color: var(--color-bg-subtle))",
        "target": "  provisioning: {\n    label: '프로비저닝 중 (Provisioning)',\n    bg: 'var(--color-bg-subtle)',\n    color: 'var(--color-status-degraded)',\n    border: 'var(--color-status-degraded)',\n  },",
        "replacement": "  provisioning: {\n    label: '프로비저닝 중 (Provisioning)',\n    bg: 'var(--color-bg-subtle)',\n    color: 'var(--color-bg-subtle)',\n    border: 'var(--color-status-degraded)',\n  },",
    },
    {
        "id": "W3",
        "desc": "suspended config: fg==bg collision (color: var(--color-bg-subtle))",
        "target": "  suspended: {\n    label: '일시 중단 (Suspended)',\n    bg: 'var(--color-bg-subtle)',\n    color: 'var(--color-text-muted)',\n    border: 'var(--color-border-subtle)',\n  },",
        "replacement": "  suspended: {\n    label: '일시 중단 (Suspended)',\n    bg: 'var(--color-bg-subtle)',\n    color: 'var(--color-bg-subtle)',\n    border: 'var(--color-border-subtle)',\n  },",
    },
    {
        "id": "W4",
        "desc": "deleting config: fg==bg collision (color: var(--color-bg-subtle))",
        "target": "  deleting: {\n    label: '삭제 중 (Deleting)',\n    bg: 'var(--color-bg-subtle)',\n    color: 'var(--color-status-offline)',\n    border: 'var(--color-status-offline)',\n  },",
        "replacement": "  deleting: {\n    label: '삭제 중 (Deleting)',\n    bg: 'var(--color-bg-subtle)',\n    color: 'var(--color-bg-subtle)',\n    border: 'var(--color-status-offline)',\n  },",
    },
    {
        "id": "W5",
        "desc": "deleted config: fg==bg collision (color: var(--color-bg-subtle))",
        "target": "  deleted: {\n    label: '삭제됨 (Deleted)',\n    bg: 'var(--color-bg-subtle)',\n    color: 'var(--color-text-muted)',\n    border: 'var(--color-border-subtle)',\n  },",
        "replacement": "  deleted: {\n    label: '삭제됨 (Deleted)',\n    bg: 'var(--color-bg-subtle)',\n    color: 'var(--color-bg-subtle)',\n    border: 'var(--color-border-subtle)',\n  },",
    },

    # 2. border==bg collisions in WORKSPACE_STATUS_CONFIG (W6-W10)
    {
        "id": "W6",
        "desc": "ready config: border==bg collision (border: var(--color-bg-subtle))",
        "target": "  ready: {\n    label: '준비 완료 (Ready)',\n    bg: 'var(--color-bg-subtle)',\n    color: 'var(--color-status-online)',\n    border: 'var(--color-status-online)',\n  },",
        "replacement": "  ready: {\n    label: '준비 완료 (Ready)',\n    bg: 'var(--color-bg-subtle)',\n    color: 'var(--color-status-online)',\n    border: 'var(--color-bg-subtle)',\n  },",
    },
    {
        "id": "W7",
        "desc": "provisioning config: border==bg collision (border: var(--color-bg-subtle))",
        "target": "  provisioning: {\n    label: '프로비저닝 중 (Provisioning)',\n    bg: 'var(--color-bg-subtle)',\n    color: 'var(--color-status-degraded)',\n    border: 'var(--color-status-degraded)',\n  },",
        "replacement": "  provisioning: {\n    label: '프로비저닝 중 (Provisioning)',\n    bg: 'var(--color-bg-subtle)',\n    color: 'var(--color-status-degraded)',\n    border: 'var(--color-bg-subtle)',\n  },",
    },
    {
        "id": "W8",
        "desc": "suspended config: border==bg collision (border: var(--color-bg-subtle))",
        "target": "  suspended: {\n    label: '일시 중단 (Suspended)',\n    bg: 'var(--color-bg-subtle)',\n    color: 'var(--color-text-muted)',\n    border: 'var(--color-border-subtle)',\n  },",
        "replacement": "  suspended: {\n    label: '일시 중단 (Suspended)',\n    bg: 'var(--color-bg-subtle)',\n    color: 'var(--color-text-muted)',\n    border: 'var(--color-bg-subtle)',\n  },",
    },
    {
        "id": "W9",
        "desc": "deleting config: border==bg collision (border: var(--color-bg-subtle))",
        "target": "  deleting: {\n    label: '삭제 중 (Deleting)',\n    bg: 'var(--color-bg-subtle)',\n    color: 'var(--color-status-offline)',\n    border: 'var(--color-status-offline)',\n  },",
        "replacement": "  deleting: {\n    label: '삭제 중 (Deleting)',\n    bg: 'var(--color-bg-subtle)',\n    color: 'var(--color-status-offline)',\n    border: 'var(--color-bg-subtle)',\n  },",
    },
    {
        "id": "W10",
        "desc": "deleted config: border==bg collision (border: var(--color-bg-subtle))",
        "target": "  deleted: {\n    label: '삭제됨 (Deleted)',\n    bg: 'var(--color-bg-subtle)',\n    color: 'var(--color-text-muted)',\n    border: 'var(--color-border-subtle)',\n  },",
        "replacement": "  deleted: {\n    label: '삭제됨 (Deleted)',\n    bg: 'var(--color-bg-subtle)',\n    color: 'var(--color-text-muted)',\n    border: 'var(--color-bg-subtle)',\n  },",
    },

    # 3. Synchronized low-contrast mutations & comment decoys (W11-W16)
    {
        "id": "W11",
        "desc": "ready config: synchronized low-contrast mutation (color: var(--color-text-inverse))",
        "target": "  ready: {\n    label: '준비 완료 (Ready)',\n    bg: 'var(--color-bg-subtle)',\n    color: 'var(--color-status-online)',\n    border: 'var(--color-status-online)',\n  },",
        "replacement": "  ready: {\n    label: '준비 완료 (Ready)',\n    bg: 'var(--color-bg-subtle)',\n    color: 'var(--color-text-inverse)',\n    border: 'var(--color-status-online)',\n  },",
    },
    {
        "id": "W12",
        "desc": "provisioning config: synchronized low-contrast mutation (color: var(--color-text-inverse))",
        "target": "  provisioning: {\n    label: '프로비저닝 중 (Provisioning)',\n    bg: 'var(--color-bg-subtle)',\n    color: 'var(--color-status-degraded)',\n    border: 'var(--color-status-degraded)',\n  },",
        "replacement": "  provisioning: {\n    label: '프로비저닝 중 (Provisioning)',\n    bg: 'var(--color-bg-subtle)',\n    color: 'var(--color-text-inverse)',\n    border: 'var(--color-status-degraded)',\n  },",
    },
    {
        "id": "W13",
        "desc": "suspended config: synchronized low-contrast mutation (color: var(--color-text-inverse))",
        "target": "  suspended: {\n    label: '일시 중단 (Suspended)',\n    bg: 'var(--color-bg-subtle)',\n    color: 'var(--color-text-muted)',\n    border: 'var(--color-border-subtle)',\n  },",
        "replacement": "  suspended: {\n    label: '일시 중단 (Suspended)',\n    bg: 'var(--color-bg-subtle)',\n    color: 'var(--color-text-inverse)',\n    border: 'var(--color-border-subtle)',\n  },",
    },
    {
        "id": "W14",
        "desc": "deleting config: synchronized low-contrast mutation (color: var(--color-text-inverse))",
        "target": "  deleting: {\n    label: '삭제 중 (Deleting)',\n    bg: 'var(--color-bg-subtle)',\n    color: 'var(--color-status-offline)',\n    border: 'var(--color-status-offline)',\n  },",
        "replacement": "  deleting: {\n    label: '삭제 중 (Deleting)',\n    bg: 'var(--color-bg-subtle)',\n    color: 'var(--color-text-inverse)',\n    border: 'var(--color-status-offline)',\n  },",
    },
    {
        "id": "W15",
        "desc": "ready config: comment decoy with legacy hex #34d399",
        "target": "  ready: {\n    label: '준비 완료 (Ready)',\n    bg: 'var(--color-bg-subtle)',\n    color: 'var(--color-status-online)',\n    border: 'var(--color-status-online)',\n  },",
        "replacement": "  ready: {\n    label: '준비 완료 (Ready)',\n    bg: 'var(--color-bg-subtle)',\n    color: 'var(--color-status-online) /* #34d399 */',\n    border: 'var(--color-status-online)',\n  },",
    },
    {
        "id": "W16",
        "desc": "provisioning config: comment decoy with legacy hex #f59e0b",
        "target": "  provisioning: {\n    label: '프로비저닝 중 (Provisioning)',\n    bg: 'var(--color-bg-subtle)',\n    color: 'var(--color-status-degraded)',\n    border: 'var(--color-status-degraded)',\n  },",
        "replacement": "  provisioning: {\n    label: '프로비저닝 중 (Provisioning)',\n    bg: 'var(--color-bg-subtle)',\n    color: 'var(--color-status-degraded) /* #f59e0b */',\n    border: 'var(--color-status-degraded)',\n  },",
    },

    # 4. Revert to legacy literals (#34d399, #f59e0b, #f87171, rgba) (W17-W25)
    {
        "id": "W17",
        "desc": "ready config: revert color to legacy hex #34d399",
        "target": "  ready: {\n    label: '준비 완료 (Ready)',\n    bg: 'var(--color-bg-subtle)',\n    color: 'var(--color-status-online)',\n    border: 'var(--color-status-online)',\n  },",
        "replacement": "  ready: {\n    label: '준비 완료 (Ready)',\n    bg: 'var(--color-bg-subtle)',\n    color: '#34d399',\n    border: 'var(--color-status-online)',\n  },",
    },
    {
        "id": "W18",
        "desc": "ready config: revert border to legacy rgba(16, 185, 129, 0.3)",
        "target": "  ready: {\n    label: '준비 완료 (Ready)',\n    bg: 'var(--color-bg-subtle)',\n    color: 'var(--color-status-online)',\n    border: 'var(--color-status-online)',\n  },",
        "replacement": "  ready: {\n    label: '준비 완료 (Ready)',\n    bg: 'var(--color-bg-subtle)',\n    color: 'var(--color-status-online)',\n    border: 'rgba(16, 185, 129, 0.3)',\n  },",
    },
    {
        "id": "W19",
        "desc": "ready config: revert bg to legacy rgba(16, 185, 129, 0.15)",
        "target": "  ready: {\n    label: '준비 완료 (Ready)',\n    bg: 'var(--color-bg-subtle)',\n    color: 'var(--color-status-online)',\n    border: 'var(--color-status-online)',\n  },",
        "replacement": "  ready: {\n    label: '준비 완료 (Ready)',\n    bg: 'rgba(16, 185, 129, 0.15)',\n    color: 'var(--color-status-online)',\n    border: 'var(--color-status-online)',\n  },",
    },
    {
        "id": "W20",
        "desc": "provisioning config: revert color to legacy hex #f59e0b",
        "target": "  provisioning: {\n    label: '프로비저닝 중 (Provisioning)',\n    bg: 'var(--color-bg-subtle)',\n    color: 'var(--color-status-degraded)',\n    border: 'var(--color-status-degraded)',\n  },",
        "replacement": "  provisioning: {\n    label: '프로비저닝 중 (Provisioning)',\n    bg: 'var(--color-bg-subtle)',\n    color: '#f59e0b',\n    border: 'var(--color-status-degraded)',\n  },",
    },
    {
        "id": "W21",
        "desc": "provisioning config: revert border to legacy rgba(245, 158, 11, 0.3)",
        "target": "  provisioning: {\n    label: '프로비저닝 중 (Provisioning)',\n    bg: 'var(--color-bg-subtle)',\n    color: 'var(--color-status-degraded)',\n    border: 'var(--color-status-degraded)',\n  },",
        "replacement": "  provisioning: {\n    label: '프로비저닝 중 (Provisioning)',\n    bg: 'var(--color-bg-subtle)',\n    color: 'var(--color-status-degraded)',\n    border: 'rgba(245, 158, 11, 0.3)',\n  },",
    },
    {
        "id": "W22",
        "desc": "provisioning config: revert bg to legacy rgba(245, 158, 11, 0.15)",
        "target": "  provisioning: {\n    label: '프로비저닝 중 (Provisioning)',\n    bg: 'var(--color-bg-subtle)',\n    color: 'var(--color-status-degraded)',\n    border: 'var(--color-status-degraded)',\n  },",
        "replacement": "  provisioning: {\n    label: '프로비저닝 중 (Provisioning)',\n    bg: 'rgba(245, 158, 11, 0.15)',\n    color: 'var(--color-status-degraded)',\n    border: 'var(--color-status-degraded)',\n  },",
    },
    {
        "id": "W23",
        "desc": "deleting config: revert color to legacy hex #f87171",
        "target": "  deleting: {\n    label: '삭제 중 (Deleting)',\n    bg: 'var(--color-bg-subtle)',\n    color: 'var(--color-status-offline)',\n    border: 'var(--color-status-offline)',\n  },",
        "replacement": "  deleting: {\n    label: '삭제 중 (Deleting)',\n    bg: 'var(--color-bg-subtle)',\n    color: '#f87171',\n    border: 'var(--color-status-offline)',\n  },",
    },
    {
        "id": "W24",
        "desc": "deleting config: revert border to legacy rgba(239, 68, 68, 0.3)",
        "target": "  deleting: {\n    label: '삭제 중 (Deleting)',\n    bg: 'var(--color-bg-subtle)',\n    color: 'var(--color-status-offline)',\n    border: 'var(--color-status-offline)',\n  },",
        "replacement": "  deleting: {\n    label: '삭제 중 (Deleting)',\n    bg: 'var(--color-bg-subtle)',\n    color: 'var(--color-status-offline)',\n    border: 'rgba(239, 68, 68, 0.3)',\n  },",
    },
    {
        "id": "W25",
        "desc": "deleting config: revert bg to legacy rgba(239, 68, 68, 0.15)",
        "target": "  deleting: {\n    label: '삭제 중 (Deleting)',\n    bg: 'var(--color-bg-subtle)',\n    color: 'var(--color-status-offline)',\n    border: 'var(--color-status-offline)',\n  },",
        "replacement": "  deleting: {\n    label: '삭제 중 (Deleting)',\n    bg: 'rgba(239, 68, 68, 0.15)',\n    color: 'var(--color-status-offline)',\n    border: 'var(--color-status-offline)',\n  },",
    },

    # 5. Error banner collisions & Button/Card collisions (W26-W29)
    {
        "id": "W26",
        "desc": "error banner: fg==bg collision (backgroundColor: offline)",
        "target": "          style={{\n            padding: '12px 16px',\n            backgroundColor: 'var(--color-bg-subtle)',\n            border: '1px solid var(--color-status-offline)',\n            borderRadius: 'var(--radius-md)',\n            color: 'var(--color-status-offline)',\n            fontSize: '0.875rem',\n            marginBottom: '16px',\n          }}",
        "replacement": "          style={{\n            padding: '12px 16px',\n            backgroundColor: 'var(--color-status-offline)',\n            border: '1px solid var(--color-status-offline)',\n            borderRadius: 'var(--radius-md)',\n            color: 'var(--color-status-offline)',\n            fontSize: '0.875rem',\n            marginBottom: '16px',\n          }}",
    },
    {
        "id": "W27",
        "desc": "error banner: border==bg collision (border: bg-subtle)",
        "target": "          style={{\n            padding: '12px 16px',\n            backgroundColor: 'var(--color-bg-subtle)',\n            border: '1px solid var(--color-status-offline)',\n            borderRadius: 'var(--radius-md)',\n            color: 'var(--color-status-offline)',\n            fontSize: '0.875rem',\n            marginBottom: '16px',\n          }}",
        "replacement": "          style={{\n            padding: '12px 16px',\n            backgroundColor: 'var(--color-bg-subtle)',\n            border: '1px solid var(--color-bg-subtle)',\n            borderRadius: 'var(--radius-md)',\n            color: 'var(--color-status-offline)',\n            fontSize: '0.875rem',\n            marginBottom: '16px',\n          }}",
    },
    {
        "id": "W28",
        "desc": "studio button: fg==bg collision (color: bg-subtle)",
        "target": "                        backgroundColor: 'var(--color-bg-subtle)',\n                        border: '1px solid var(--color-border-strong)',\n                        color: 'var(--color-text-primary)',\n                        cursor: 'pointer',",
        "replacement": "                        backgroundColor: 'var(--color-bg-subtle)',\n                        border: '1px solid var(--color-border-strong)',\n                        color: 'var(--color-bg-subtle)',\n                        cursor: 'pointer',",
    },
    {
        "id": "W29",
        "desc": "studio button: border==bg collision (border: bg-subtle)",
        "target": "                        backgroundColor: 'var(--color-bg-subtle)',\n                        border: '1px solid var(--color-border-strong)',\n                        color: 'var(--color-text-primary)',\n                        cursor: 'pointer',",
        "replacement": "                        backgroundColor: 'var(--color-bg-subtle)',\n                        border: '1px solid var(--color-bg-subtle)',\n                        color: 'var(--color-text-primary)',\n                        cursor: 'pointer',",
    },

    # 6. Focus ring suppressions (W30-W32)
    {
        "id": "W30",
        "desc": "workspace card: outline: 'none' suppressing focus ring",
        "target": "                style={{\n                  padding: '20px',\n                  backgroundColor: 'var(--color-bg-surface)',\n                  borderRadius: 'var(--radius-lg)',\n                  border: '1px solid var(--color-border-subtle)',\n                  boxShadow: 'var(--shadow-sm)',\n                  cursor: 'pointer',\n                  transition: 'border-color 0.2s, transform 0.15s',\n                }}",
        "replacement": "                style={{\n                  padding: '20px',\n                  backgroundColor: 'var(--color-bg-surface)',\n                  borderRadius: 'var(--radius-lg)',\n                  border: '1px solid var(--color-border-subtle)',\n                  boxShadow: 'var(--shadow-sm)',\n                  cursor: 'pointer',\n                  transition: 'border-color 0.2s, transform 0.15s',\n                  outline: 'none',\n                }}",
    },
    {
        "id": "W31",
        "desc": "workspace card: outline: 0 suppressing focus ring",
        "target": "                style={{\n                  padding: '20px',\n                  backgroundColor: 'var(--color-bg-surface)',\n                  borderRadius: 'var(--radius-lg)',\n                  border: '1px solid var(--color-border-subtle)',\n                  boxShadow: 'var(--shadow-sm)',\n                  cursor: 'pointer',\n                  transition: 'border-color 0.2s, transform 0.15s',\n                }}",
        "replacement": "                style={{\n                  padding: '20px',\n                  backgroundColor: 'var(--color-bg-surface)',\n                  borderRadius: 'var(--radius-lg)',\n                  border: '1px solid var(--color-border-subtle)',\n                  boxShadow: 'var(--shadow-sm)',\n                  cursor: 'pointer',\n                  transition: 'border-color 0.2s, transform 0.15s',\n                  outline: 0,\n                }}",
    },
    {
        "id": "W32",
        "desc": "studio button: outline: 'none' suppressing focus ring",
        "target": "                        backgroundColor: 'var(--color-bg-subtle)',\n                        border: '1px solid var(--color-border-strong)',\n                        color: 'var(--color-text-primary)',\n                        cursor: 'pointer',\n                      }}",
        "replacement": "                        backgroundColor: 'var(--color-bg-subtle)',\n                        border: '1px solid var(--color-border-strong)',\n                        color: 'var(--color-text-primary)',\n                        cursor: 'pointer',\n                        outline: 'none',\n                      }}",
    },

    # 7. Fail-closed contract & prototype defense (W33-W37)
    {
        "id": "W33",
        "desc": "fail-closed: bypass Object.hasOwn with in operator",
        "target": "  if (status && typeof status === 'string' && Object.hasOwn(WORKSPACE_STATUS_CONFIG, status)) {",
        "replacement": "  if (status && typeof status === 'string' && (status in WORKSPACE_STATUS_CONFIG)) {",
    },
    {
        "id": "W34",
        "desc": "fail-closed: prototype key hijack with direct indexing lookup",
        "target": "  if (status && typeof status === 'string' && Object.hasOwn(WORKSPACE_STATUS_CONFIG, status)) {\n    return WORKSPACE_STATUS_CONFIG[status as keyof typeof WORKSPACE_STATUS_CONFIG];\n  }",
        "replacement": "  if (status && typeof status === 'string' && ((WORKSPACE_STATUS_CONFIG as any)[status] || Object.hasOwn(WORKSPACE_STATUS_CONFIG, status))) {\n    return (WORKSPACE_STATUS_CONFIG as any)[status] || WORKSPACE_STATUS_CONFIG[status as keyof typeof WORKSPACE_STATUS_CONFIG];\n  }",
    },
    {
        "id": "W35",
        "desc": "fail-closed: fallback returns online color instead of unknown",
        "target": "    color: 'var(--color-status-unknown)',\n    border: 'var(--color-status-unknown)',",
        "replacement": "    color: 'var(--color-status-online)',\n    border: 'var(--color-status-unknown)',",
    },
    {
        "id": "W36",
        "desc": "contract bypass: map out-of-contract 'admitted' to ready",
        "target": "  if (status && typeof status === 'string' && Object.hasOwn(WORKSPACE_STATUS_CONFIG, status)) {\n    return WORKSPACE_STATUS_CONFIG[status as keyof typeof WORKSPACE_STATUS_CONFIG];\n  }",
        "replacement": "  if (status === 'admitted') return WORKSPACE_STATUS_CONFIG['ready'];\n  if (status && typeof status === 'string' && Object.hasOwn(WORKSPACE_STATUS_CONFIG, status)) {\n    return WORKSPACE_STATUS_CONFIG[status as keyof typeof WORKSPACE_STATUS_CONFIG];\n  }",
    },
    {
        "id": "W37",
        "desc": "case-insensitive lookup: toLowerCase() lookup bypass",
        "target": "  if (status && typeof status === 'string' && Object.hasOwn(WORKSPACE_STATUS_CONFIG, status)) {",
        "replacement": "  const sKey = typeof status === 'string' ? status.toLowerCase() : status;\n  if (sKey && typeof sKey === 'string' && Object.hasOwn(WORKSPACE_STATUS_CONFIG, sKey as any)) {",
    },

    # 8. Labels, icons, and heading defense (W38-W40)
    {
        "id": "W38",
        "desc": "unknown label: remove 'UNKNOWN (' prefix",
        "target": "    label: raw ? `UNKNOWN (${raw})` : 'UNKNOWN',",
        "replacement": "    label: raw ? `(${raw})` : 'UNKNOWN',",
    },
    {
        "id": "W39",
        "desc": "error banner: remove '⚠️' icon",
        "target": "            <span aria-hidden=\"true\">⚠️</span>",
        "replacement": "            <span aria-hidden=\"true\"></span>",
    },
    {
        "id": "W40",
        "desc": "error banner: mutated heading to '작업공간 알림'",
        "target": "            <strong style={{ color: 'var(--color-status-offline)' }}>작업공간 오류</strong>",
        "replacement": "            <strong style={{ color: 'var(--color-status-offline)' }}>작업공간 알림</strong>",
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
    parser = argparse.ArgumentParser(description="Test Card 270 mutations on WorkspaceList.tsx")
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
