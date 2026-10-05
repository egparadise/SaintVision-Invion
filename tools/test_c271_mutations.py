#!/usr/bin/env python3
"""
tools/test_c271_mutations.py:
Verification runner for 40 accessibility, contrast, contract, and fail-closed mutants (W1-W40)
targeting NodeList.tsx.

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
TARGET_FILE = APPS_WEB / "src" / "features" / "nodes" / "NodeList.tsx"
RESULTS_FILE = WORKTREE_ROOT / "tools" / ".c271_mutation_results.json"

MUTANTS = [
    # Batch 1 (W1-W8): Telemetry card & badge mutants
    {
        "id": "W1",
        "desc": "telemetry badge: color==bg collision (color: var(--color-bg-subtle))",
        "target": "                    color: statusCfg.color,\n                    backgroundColor: 'var(--color-bg-subtle)',\n                    border: `1px solid ${statusCfg.color}`,",
        "replacement": "                    color: 'var(--color-bg-subtle)',\n                    backgroundColor: 'var(--color-bg-subtle)',\n                    border: `1px solid ${statusCfg.color}`,",
    },
    {
        "id": "W2",
        "desc": "telemetry badge: border==bg collision (border: 1px solid var(--color-bg-subtle))",
        "target": "                    color: statusCfg.color,\n                    backgroundColor: 'var(--color-bg-subtle)',\n                    border: `1px solid ${statusCfg.color}`,",
        "replacement": "                    color: statusCfg.color,\n                    backgroundColor: 'var(--color-bg-subtle)',\n                    border: '1px solid var(--color-bg-subtle)',",
    },
    {
        "id": "W3",
        "desc": "telemetry badge: synchronized low-contrast mutation (color: var(--color-text-inverse))",
        "target": "                    color: statusCfg.color,\n                    backgroundColor: 'var(--color-bg-subtle)',\n                    border: `1px solid ${statusCfg.color}`,",
        "replacement": "                    color: 'var(--color-text-inverse)',\n                    backgroundColor: 'var(--color-bg-subtle)',\n                    border: `1px solid ${statusCfg.color}`,",
    },
    {
        "id": "W4",
        "desc": "telemetry badge: dot background collision with subtle",
        "target": "                  <span style={{\n                    width: '6px',\n                    height: '6px',\n                    borderRadius: '50%',\n                    backgroundColor: statusCfg.color,\n                  }} />",
        "replacement": "                  <span style={{\n                    width: '6px',\n                    height: '6px',\n                    borderRadius: '50%',\n                    backgroundColor: 'var(--color-bg-subtle)',\n                  }} />",
    },
    {
        "id": "W5",
        "desc": "telemetry card: lost border collision with surface",
        "target": "border: `1px solid ${node.status === 'lost' ? 'var(--color-status-lost)' : node.status === 'unknown' ? 'var(--color-status-unknown)' : 'var(--color-border-subtle)'}`,",
        "replacement": "border: `1px solid ${node.status === 'lost' ? 'var(--color-bg-surface)' : node.status === 'unknown' ? 'var(--color-status-unknown)' : 'var(--color-border-subtle)'}`,",
    },
    {
        "id": "W6",
        "desc": "telemetry card: unknown border collision with surface",
        "target": "border: `1px solid ${node.status === 'lost' ? 'var(--color-status-lost)' : node.status === 'unknown' ? 'var(--color-status-unknown)' : 'var(--color-border-subtle)'}`,",
        "replacement": "border: `1px solid ${node.status === 'lost' ? 'var(--color-status-lost)' : node.status === 'unknown' ? 'var(--color-bg-surface)' : 'var(--color-border-subtle)'}`,",
    },
    {
        "id": "W7",
        "desc": "telemetry notice: lost text collision with surface",
        "target": "color: node.status === 'lost' ? 'var(--color-status-lost)' : node.status === 'unknown' ? 'var(--color-status-unknown)' : node.status === 'active' ? 'var(--color-status-active)' : 'var(--color-text-muted)',",
        "replacement": "color: node.status === 'lost' ? 'var(--color-bg-surface)' : node.status === 'unknown' ? 'var(--color-status-unknown)' : node.status === 'active' ? 'var(--color-status-active)' : 'var(--color-text-muted)',",
    },
    {
        "id": "W8",
        "desc": "telemetry notice: unknown text collision with surface",
        "target": "color: node.status === 'lost' ? 'var(--color-status-lost)' : node.status === 'unknown' ? 'var(--color-status-unknown)' : node.status === 'active' ? 'var(--color-status-active)' : 'var(--color-text-muted)',",
        "replacement": "color: node.status === 'lost' ? 'var(--color-status-lost)' : node.status === 'unknown' ? 'var(--color-bg-surface)' : node.status === 'active' ? 'var(--color-status-active)' : 'var(--color-text-muted)',",
    },

    # Batch 2 (W9-W16): Standard card & badge mutants
    {
        "id": "W9",
        "desc": "standard badge: color==bg collision (color: var(--color-bg-subtle))",
        "target": "                    color: statusCfg.color,\n                    backgroundColor: 'var(--color-bg-subtle)',\n                    border: `1px solid ${statusCfg.color}`,\n                  }}\n                >\n                  <span style={{ width: '6px', height: '6px', borderRadius: '50%', backgroundColor: statusCfg.color }} />",
        "replacement": "                    color: 'var(--color-bg-subtle)',\n                    backgroundColor: 'var(--color-bg-subtle)',\n                    border: `1px solid ${statusCfg.color}`,\n                  }}\n                >\n                  <span style={{ width: '6px', height: '6px', borderRadius: '50%', backgroundColor: statusCfg.color }} />",
    },
    {
        "id": "W10",
        "desc": "standard badge: border==bg collision (border: 1px solid var(--color-bg-subtle))",
        "target": "                    color: statusCfg.color,\n                    backgroundColor: 'var(--color-bg-subtle)',\n                    border: `1px solid ${statusCfg.color}`,\n                  }}\n                >\n                  <span style={{ width: '6px', height: '6px', borderRadius: '50%', backgroundColor: statusCfg.color }} />",
        "replacement": "                    color: statusCfg.color,\n                    backgroundColor: 'var(--color-bg-subtle)',\n                    border: '1px solid var(--color-bg-subtle)',\n                  }}\n                >\n                  <span style={{ width: '6px', height: '6px', borderRadius: '50%', backgroundColor: statusCfg.color }} />",
    },
    {
        "id": "W11",
        "desc": "standard badge: synchronized low-contrast mutation (color: var(--color-text-inverse))",
        "target": "                    color: statusCfg.color,\n                    backgroundColor: 'var(--color-bg-subtle)',\n                    border: `1px solid ${statusCfg.color}`,\n                  }}\n                >\n                  <span style={{ width: '6px', height: '6px', borderRadius: '50%', backgroundColor: statusCfg.color }} />",
        "replacement": "                    color: 'var(--color-text-inverse)',\n                    backgroundColor: 'var(--color-bg-subtle)',\n                    border: `1px solid ${statusCfg.color}`,\n                  }}\n                >\n                  <span style={{ width: '6px', height: '6px', borderRadius: '50%', backgroundColor: statusCfg.color }} />",
    },
    {
        "id": "W12",
        "desc": "standard badge: dot collision with subtle",
        "target": "<span style={{ width: '6px', height: '6px', borderRadius: '50%', backgroundColor: statusCfg.color }} />",
        "replacement": "<span style={{ width: '6px', height: '6px', borderRadius: '50%', backgroundColor: 'var(--color-bg-subtle)' }} />",
    },
    {
        "id": "W13",
        "desc": "standard card: border collision with surface",
        "target": "                border: '1px solid var(--color-border-subtle)',\n                boxShadow: 'var(--shadow-sm)',\n                transition: 'border-color 0.2s, box-shadow 0.2s',",
        "replacement": "                border: '1px solid var(--color-bg-surface)',\n                boxShadow: 'var(--shadow-sm)',\n                transition: 'border-color 0.2s, box-shadow 0.2s',",
    },
    {
        "id": "W14",
        "desc": "standard card: CPU usage bar color collision with subtle",
        "target": "<div style={{ width: `${node.cpuUsagePercent}%`, height: '100%', backgroundColor: 'var(--color-brand-primary)' }} />",
        "replacement": "<div style={{ width: `${node.cpuUsagePercent}%`, height: '100%', backgroundColor: 'var(--color-bg-subtle)' }} />",
    },
    {
        "id": "W15",
        "desc": "standard card: GPU box background collision with surface",
        "target": "                  <div style={{ padding: '6px 8px', backgroundColor: 'var(--color-bg-subtle)', borderRadius: 'var(--radius-sm)' }}>\n                    <div style={{ fontWeight: 600, color: 'var(--color-text-primary)' }}>",
        "replacement": "                  <div style={{ padding: '6px 8px', backgroundColor: 'var(--color-bg-surface)', borderRadius: 'var(--radius-sm)' }}>\n                    <div style={{ fontWeight: 600, color: 'var(--color-text-primary)' }}>",
    },
    {
        "id": "W16",
        "desc": "telemetry detail button: background collision with surface",
        "target": "                      backgroundColor: 'var(--color-bg-subtle)',\n                      border: '1px solid var(--color-border-subtle)',\n                      color: 'var(--color-text-primary)',\n                      cursor: 'pointer',\n                    }}\n                  >\n                    상세 및 자원 보기 →",
        "replacement": "                      backgroundColor: 'var(--color-bg-surface)',\n                      border: '1px solid var(--color-border-subtle)',\n                      color: 'var(--color-text-primary)',\n                      cursor: 'pointer',\n                    }}\n                  >\n                    상세 및 자원 보기 →",
    },

    # Batch 3 (W17-W24): Observation banner & Active notice mutants
    {
        "id": "W17",
        "desc": "observation banner: bg==color collision (color: var(--color-bg-subtle))",
        "target": "                  data-testid={`node-observation-banner-${node.id}`}\n                  style={{\n                    marginTop: '8px',\n                    padding: '4px 8px',\n                    borderRadius: 'var(--radius-sm)',\n                    backgroundColor: 'var(--color-bg-subtle)',\n                    border: '1px solid var(--color-status-unknown)',\n                    color: 'var(--color-status-unknown)',",
        "replacement": "                  data-testid={`node-observation-banner-${node.id}`}\n                  style={{\n                    marginTop: '8px',\n                    padding: '4px 8px',\n                    borderRadius: 'var(--radius-sm)',\n                    backgroundColor: 'var(--color-bg-subtle)',\n                    border: '1px solid var(--color-status-unknown)',\n                    color: 'var(--color-bg-subtle)',",
    },
    {
        "id": "W18",
        "desc": "observation banner: border==bg collision (border: 1px solid var(--color-bg-subtle))",
        "target": "                  data-testid={`node-observation-banner-${node.id}`}\n                  style={{\n                    marginTop: '8px',\n                    padding: '4px 8px',\n                    borderRadius: 'var(--radius-sm)',\n                    backgroundColor: 'var(--color-bg-subtle)',\n                    border: '1px solid var(--color-status-unknown)',\n                    color: 'var(--color-status-unknown)',",
        "replacement": "                  data-testid={`node-observation-banner-${node.id}`}\n                  style={{\n                    marginTop: '8px',\n                    padding: '4px 8px',\n                    borderRadius: 'var(--radius-sm)',\n                    backgroundColor: 'var(--color-bg-subtle)',\n                    border: '1px solid var(--color-bg-subtle)',\n                    color: 'var(--color-status-unknown)',",
    },
    {
        "id": "W19",
        "desc": "observation banner: revert to raw rgba background",
        "target": "                  data-testid={`node-observation-banner-${node.id}`}\n                  style={{\n                    marginTop: '8px',\n                    padding: '4px 8px',\n                    borderRadius: 'var(--radius-sm)',\n                    backgroundColor: 'var(--color-bg-subtle)',",
        "replacement": "                  data-testid={`node-observation-banner-${node.id}`}\n                  style={{\n                    marginTop: '8px',\n                    padding: '4px 8px',\n                    borderRadius: 'var(--radius-sm)',\n                    backgroundColor: 'rgba(210, 153, 34, 0.15)',",
    },
    {
        "id": "W20",
        "desc": "observation banner: remove warning emoji icon",
        "target": "                  ⚠️ 관측 전용 (192.168.45.225 - 원격 프로필 미설치)",
        "replacement": "                  관측 전용 (192.168.45.225 - 원격 프로필 미설치)",
    },
    {
        "id": "W21",
        "desc": "active notice: bg==color collision (color: var(--color-bg-subtle))",
        "target": "                  data-testid={`node-active-status-notice-${node.id}`}\n                  style={{\n                    marginTop: '8px',\n                    padding: '4px 8px',\n                    borderRadius: 'var(--radius-sm)',\n                    backgroundColor: 'var(--color-bg-subtle)',\n                    border: '1px solid var(--color-status-active)',\n                    color: 'var(--color-status-active)',",
        "replacement": "                  data-testid={`node-active-status-notice-${node.id}`}\n                  style={{\n                    marginTop: '8px',\n                    padding: '4px 8px',\n                    borderRadius: 'var(--radius-sm)',\n                    backgroundColor: 'var(--color-bg-subtle)',\n                    border: '1px solid var(--color-status-active)',\n                    color: 'var(--color-bg-subtle)',",
    },
    {
        "id": "W22",
        "desc": "active notice: border==bg collision (border: 1px solid var(--color-bg-subtle))",
        "target": "                  data-testid={`node-active-status-notice-${node.id}`}\n                  style={{\n                    marginTop: '8px',\n                    padding: '4px 8px',\n                    borderRadius: 'var(--radius-sm)',\n                    backgroundColor: 'var(--color-bg-subtle)',\n                    border: '1px solid var(--color-status-active)',\n                    color: 'var(--color-status-active)',",
        "replacement": "                  data-testid={`node-active-status-notice-${node.id}`}\n                  style={{\n                    marginTop: '8px',\n                    padding: '4px 8px',\n                    borderRadius: 'var(--radius-sm)',\n                    backgroundColor: 'var(--color-bg-subtle)',\n                    border: '1px solid var(--color-bg-subtle)',\n                    color: 'var(--color-status-active)',",
    },
    {
        "id": "W23",
        "desc": "active notice: revert to raw rgba background",
        "target": "                  data-testid={`node-active-status-notice-${node.id}`}\n                  style={{\n                    marginTop: '8px',\n                    padding: '4px 8px',\n                    borderRadius: 'var(--radius-sm)',\n                    backgroundColor: 'var(--color-bg-subtle)',",
        "replacement": "                  data-testid={`node-active-status-notice-${node.id}`}\n                  style={{\n                    marginTop: '8px',\n                    padding: '4px 8px',\n                    borderRadius: 'var(--radius-sm)',\n                    backgroundColor: 'rgba(56, 189, 248, 0.12)',",
    },
    {
        "id": "W24",
        "desc": "active notice: remove info emoji icon",
        "target": "                  ℹ️ 계약 상태: active (정상 가동 노드 · liveness 및 헬스 초록 표기 정책은 사용자 결정 대기 중)",
        "replacement": "                  계약 상태: active (정상 가동 노드 · liveness 및 헬스 초록 표기 정책은 사용자 결정 대기 중)",
    },

    # Batch 4 (W25-W32): Schedulable capacity & Studio Open button mutants
    {
        "id": "W25",
        "desc": "schedulable text: observationOnly color collision with surface",
        "target": "data-testid={`node-schedulable-${node.id}`}\n                    style={{ fontWeight: 700, color: node.observationOnly ? 'var(--color-status-unknown)' : (node.allocatableCores !== undefined ? 'var(--color-status-online)' : 'var(--color-text-muted)') }}",
        "replacement": "data-testid={`node-schedulable-${node.id}`}\n                    style={{ fontWeight: 700, color: node.observationOnly ? 'var(--color-bg-surface)' : (node.allocatableCores !== undefined ? 'var(--color-status-online)' : 'var(--color-text-muted)') }}",
    },
    {
        "id": "W26",
        "desc": "schedulable text: allocatable color collision with surface",
        "target": "data-testid={`node-schedulable-${node.id}`}\n                    style={{ fontWeight: 700, color: node.observationOnly ? 'var(--color-status-unknown)' : (node.allocatableCores !== undefined ? 'var(--color-status-online)' : 'var(--color-text-muted)') }}",
        "replacement": "data-testid={`node-schedulable-${node.id}`}\n                    style={{ fontWeight: 700, color: node.observationOnly ? 'var(--color-status-unknown)' : (node.allocatableCores !== undefined ? 'var(--color-bg-surface)' : 'var(--color-text-muted)') }}",
    },
    {
        "id": "W27",
        "desc": "studio open button: normal color collision (color: var(--color-brand-primary-bg))",
        "target": "                        backgroundColor: node.observationOnly ? 'var(--color-border-strong)' : 'var(--color-brand-primary-bg)',\n                        color: node.observationOnly ? 'var(--color-text-inverse)' : 'var(--color-brand-primary-fg)',",
        "replacement": "                        backgroundColor: node.observationOnly ? 'var(--color-border-strong)' : 'var(--color-brand-primary-bg)',\n                        color: node.observationOnly ? 'var(--color-text-inverse)' : 'var(--color-brand-primary-bg)',",
    },
    {
        "id": "W28",
        "desc": "studio open button: normal revert to raw literal #ffffff",
        "target": "color: node.observationOnly ? 'var(--color-text-inverse)' : 'var(--color-brand-primary-fg)',",
        "replacement": "color: node.observationOnly ? 'var(--color-text-inverse)' : '#ffffff',",
    },
    {
        "id": "W29",
        "desc": "studio open button: obsOnly color collision with border-strong",
        "target": "                        backgroundColor: node.observationOnly ? 'var(--color-border-strong)' : 'var(--color-brand-primary-bg)',\n                        color: node.observationOnly ? 'var(--color-text-inverse)' : 'var(--color-brand-primary-fg)',",
        "replacement": "                        backgroundColor: node.observationOnly ? 'var(--color-border-strong)' : 'var(--color-brand-primary-bg)',\n                        color: node.observationOnly ? 'var(--color-border-strong)' : 'var(--color-brand-primary-fg)',",
    },
    {
        "id": "W30",
        "desc": "studio open button: focus ring suppression via outline: none",
        "target": "                        border: 'none',\n                        cursor: 'pointer',\n                      }}\n                    >\n                      ⚡ Studio 열기",
        "replacement": "                        border: 'none',\n                        outline: 'none',\n                        cursor: 'pointer',\n                      }}\n                    >\n                      ⚡ Studio 열기",
    },
    {
        "id": "W31",
        "desc": "studio open button: focus ring suppression via outline: '0'",
        "target": "                        border: 'none',\n                        cursor: 'pointer',\n                      }}\n                    >\n                      ⚡ Studio 열기",
        "replacement": "                        border: 'none',\n                        outline: '0',\n                        cursor: 'pointer',\n                      }}\n                    >\n                      ⚡ Studio 열기",
    },
    {
        "id": "W32",
        "desc": "schedulable section: borderTop collision with surface",
        "target": "                  borderTop: '1px solid var(--color-border-subtle)',\n                  display: 'flex',\n                  justifyContent: 'space-between',",
        "replacement": "                  borderTop: '1px solid var(--color-bg-surface)',\n                  display: 'flex',\n                  justifyContent: 'space-between',",
    },

    # Batch 5 (W33-W40): Empty state, Code Bootstrap, Copy Button & Select Button
    {
        "id": "W33",
        "desc": "code block: revert background to raw literal #1e1e1e",
        "target": "                  padding: '8px 12px',\n                  backgroundColor: 'var(--color-bg-subtle)',\n                  color: 'var(--color-status-online)',",
        "replacement": "                  padding: '8px 12px',\n                  backgroundColor: '#1e1e1e',\n                  color: 'var(--color-status-online)',",
    },
    {
        "id": "W34",
        "desc": "code block: revert text to raw literal #4ade80",
        "target": "                  backgroundColor: 'var(--color-bg-subtle)',\n                  color: 'var(--color-status-online)',\n                  borderRadius: '4px',",
        "replacement": "                  backgroundColor: 'var(--color-bg-subtle)',\n                  color: '#4ade80',\n                  borderRadius: '4px',",
    },
    {
        "id": "W35",
        "desc": "code block: bg==color collision (color: var(--color-bg-subtle))",
        "target": "                  backgroundColor: 'var(--color-bg-subtle)',\n                  color: 'var(--color-status-online)',\n                  borderRadius: '4px',",
        "replacement": "                  backgroundColor: 'var(--color-bg-subtle)',\n                  color: 'var(--color-bg-subtle)',\n                  borderRadius: '4px',",
    },
    {
        "id": "W36",
        "desc": "copy button: bg==color collision (color: var(--color-bg-subtle))",
        "target": "                  padding: '8px 12px',\n                  backgroundColor: 'var(--color-bg-subtle)',\n                  color: 'var(--color-text-primary)',\n                  border: '1px solid var(--color-border-subtle)',",
        "replacement": "                  padding: '8px 12px',\n                  backgroundColor: 'var(--color-bg-subtle)',\n                  color: 'var(--color-bg-subtle)',\n                  border: '1px solid var(--color-border-subtle)',",
    },
    {
        "id": "W37",
        "desc": "copy button: focus ring suppression via outline: none",
        "target": "                  border: '1px solid var(--color-border-subtle)',\n                  borderRadius: '4px',\n                  cursor: 'pointer',",
        "replacement": "                  border: '1px solid var(--color-border-subtle)',\n                  outline: 'none',\n                  borderRadius: '4px',\n                  cursor: 'pointer',",
    },
    {
        "id": "W38",
        "desc": "copy button: revert background to raw literal #2d3748",
        "target": "                  padding: '8px 12px',\n                  backgroundColor: 'var(--color-bg-subtle)',\n                  color: 'var(--color-text-primary)',",
        "replacement": "                  padding: '8px 12px',\n                  backgroundColor: '#2d3748',\n                  color: 'var(--color-text-primary)',",
    },
    {
        "id": "W39",
        "desc": "copy feedback text: revert to raw literal #4ade80",
        "target": "style={{ display: 'block', marginTop: '8px', fontSize: '0.75rem', color: 'var(--color-status-online)' }}",
        "replacement": "style={{ display: 'block', marginTop: '8px', fontSize: '0.75rem', color: '#4ade80' }}",
    },
    {
        "id": "W40",
        "desc": "node select button: focus ring suppression via outline: none",
        "target": "                        backgroundColor: 'var(--color-bg-subtle)',\n                        border: '1px solid var(--color-border-subtle)',\n                        color: 'var(--color-text-primary)',\n                        cursor: 'pointer',\n                      }}\n                    >\n                      노드 선택",
        "replacement": "                        backgroundColor: 'var(--color-bg-subtle)',\n                        border: '1px solid var(--color-border-subtle)',\n                        outline: 'none',\n                        color: 'var(--color-text-primary)',\n                        cursor: 'pointer',\n                      }}\n                    >\n                      노드 선택",
    },
]


def apply_mutation(target: str, replacement: str):
    content = TARGET_FILE.read_text(encoding="utf-8")
    if target not in content:
        raise ValueError(f"Target pattern not found in {TARGET_FILE}:\n{target[:100]}...")
    new_content = content.replace(target, replacement, 1)
    TARGET_FILE.write_text(new_content, encoding="utf-8", newline="")


def restore_file(original_bytes: bytes):
    TARGET_FILE.write_bytes(original_bytes)
    current_bytes = TARGET_FILE.read_bytes()
    if current_bytes != original_bytes:
        raise RuntimeError(
            f"Byte mismatch after restoration of {TARGET_FILE}! Expected {len(original_bytes)} bytes, got {len(current_bytes)} bytes"
        )


def run_tsc_check():
    """Run npx tsc -b to ensure the mutant compiles."""
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


def test_mutant(mutant, original_bytes: bytes, timeout=120, head_sha=""):
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
    parser = argparse.ArgumentParser(description="Test Card 271 mutations on NodeList.tsx")
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

    results = []

    for m in selected_mutants:
        res = test_mutant(m, original_bytes, timeout=args.timeout, head_sha=clean_head_sha)
        results.append(res)

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
