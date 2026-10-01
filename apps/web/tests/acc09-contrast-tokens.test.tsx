// @vitest-environment happy-dom
import React, { act } from 'react';
import { createRoot } from 'react-dom/client';
import { describe, it, expect, vi } from 'vitest';
import fs from 'node:fs';
import path from 'node:path';
import { RunDetail } from '../src/features/runs/RunDetail';
import { NodeList } from '../src/features/nodes/NodeList';
import { DeveloperStudio } from '../src/features/studio/DeveloperStudio';
import * as client from '../src/shared/api/client';
import * as projectObservation from '../src/shared/api/projectObservation';

(globalThis as any).IS_REACT_ACT_ENVIRONMENT = true;

const indexCss = fs.readFileSync(path.resolve(__dirname, '../src/index.css'), 'utf-8');

// Helper functions for WCAG 2.1 / 2.2 relative luminance and contrast ratio calculations
function parseHex(hex: string): [number, number, number] {
  let clean = hex.replace('#', '').trim();
  if (clean.length === 3) {
    clean = clean.split('').map((c) => c + c).join('');
  }
  const num = parseInt(clean, 16);
  return [(num >> 16) & 255, (num >> 8) & 255, num & 255];
}

function srgbToLinear(val: number): number {
  const norm = val / 255;
  return norm <= 0.04045 ? norm / 12.92 : Math.pow((norm + 0.055) / 1.055, 2.4);
}

function getLuminance(hex: string): number {
  const [r, g, b] = parseHex(hex);
  return 0.2126 * srgbToLinear(r) + 0.7152 * srgbToLinear(g) + 0.0722 * srgbToLinear(b);
}

function getContrast(hex1: string, hex2: string): number {
  const l1 = getLuminance(hex1);
  const l2 = getLuminance(hex2);
  const lighter = Math.max(l1, l2);
  const darker = Math.min(l1, l2);
  return (lighter + 0.05) / (darker + 0.05);
}

function blendRgba(tintRgb: [number, number, number], alpha: number, underlayHex: string): string {
  const underlayRgb = parseHex(underlayHex);
  const r = Math.round(alpha * tintRgb[0] + (1 - alpha) * underlayRgb[0]);
  const g = Math.round(alpha * tintRgb[1] + (1 - alpha) * underlayRgb[1]);
  const b = Math.round(alpha * tintRgb[2] + (1 - alpha) * underlayRgb[2]);
  const toHex = (n: number) => n.toString(16).padStart(2, '0');
  return `#${toHex(r)}${toHex(g)}${toHex(b)}`;
}

function extractTokens(block: string): Record<string, string> {
  const tokens: Record<string, string> = {};
  const regex = /(--color-[a-z0-9-]+)\s*:\s*([^;]+);/g;
  let match;
  while ((match = regex.exec(block)) !== null) {
    const val = match[2].split('/*')[0].trim();
    if (val.startsWith('#')) {
      tokens[match[1].trim()] = val;
    }
  }
  return tokens;
}

function getAllSourceFiles(dir: string): string[] {
  const entries = fs.readdirSync(dir, { recursive: true, withFileTypes: true });
  const files: string[] = [];
  for (const entry of entries) {
    if (entry.isFile()) {
      const fullPath = path.join(entry.parentPath || dir, entry.name);
      if (/\.(tsx?|jsx?|css)$/.test(entry.name)) {
        files.push(fullPath);
      }
    }
  }
  return files;
}

// Fail-closed multiset inventory of registered files and their exact color literal counts (literal -> max allowed occurrences)
const COLOR_LITERAL_MULTISET_BASELINE: Record<string, Record<string, number>> = {
  "app/App.tsx": {"#991b1b": 2, "#dc2626": 1, "#ef4444": 1, "#f87171": 1, "#fca5a5": 1, "#fed7aa": 1, "#fee2e2": 1, "#ffffff": 2, "rgba(239,68,68,0.1)": 1},
  "contracts/model-verify-request.ts": {"#209": 1},
  "contracts/model-version-register-request.ts": {"#191": 1},
  "features/admin/AdminSecurityConsole.tsx": {"#0d1117": 12, "#161b22": 14, "#21262d": 1, "#30363d": 24, "#3fb950": 16, "#58a6ff": 6, "#8b949e": 40, "#c9d1d9": 12, "#d29922": 1, "#eab308": 1, "#ef4444": 1, "#f0f6fc": 10, "#f85149": 24, "#fca5a5": 1, "#fde047": 1, "#ff7b72": 3, "rgba(0,0,0,0.75)": 1, "rgba(210,153,34,0.2)": 1, "rgba(234,179,8,0.15)": 1, "rgba(239,68,68,0.15)": 1, "rgba(248,81,73,0.15)": 8, "rgba(248,81,73,0.2)": 3, "rgba(46,160,67,0.15)": 2, "rgba(46,160,67,0.2)": 1, "rgba(63,185,80,0.2)": 1},
  "features/agent/NaturalLanguageRunView.tsx": {"#0d1117": 6, "#161b22": 7, "#30363d": 12, "#3fb950": 7, "#58a6ff": 8, "#8b949e": 16, "#93c5fd": 1, "#94a3b8": 1, "#c9d1d9": 2, "#cbd5e1": 1, "#f0f6fc": 3, "#f85149": 7, "#ff7b72": 1, "rgba(248,81,73,0.15)": 2, "rgba(46,160,67,0.15)": 1, "rgba(46,160,67,0.2)": 1, "rgba(56,139,253,0.15)": 2, "rgba(56,139,253,0.2)": 1},
  "features/agent/evalRunner.ts": {"#136": 1},
  "features/approvals/ApprovalCenter.tsx": {"#1e293b": 1, "#334155": 1, "#3b82f6": 1, "#93c5fd": 1, "#ef4444": 2, "#f8fafc": 1, "#fca5a5": 2, "#fed7aa": 1, "#fff": 1, "rgba(16,185,129,0.15)": 1, "rgba(234,179,8,0.15)": 1, "rgba(239,68,68,0.15)": 2, "rgba(59,130,246,0.1)": 1, "rgba(59,130,246,0.25)": 1},
  "features/approvals/ApprovalDetail.tsx": {"#0d1117": 1, "#30363d": 1, "#58a6ff": 1, "#c9d1d9": 1, "rgba(0,0,0,0.5)": 1, "rgba(220,38,38,0.1)": 1, "rgba(56,139,253,0.15)": 1},
  "features/dashboard/ClusterOverview.tsx": {"#10b981": 1, "#38bdf8": 1, "#64748b": 2, "#8b5cf6": 1, "#d29922": 1, "#ef4444": 4, "#f59e0b": 1, "#fca5a5": 3, "#fff": 1, "rgba(239,68,68,0.1)": 2},
  "features/deployment/IntranetDeploymentView.tsx": {"#0d1117": 5, "#161b22": 9, "#21262d": 4, "#238636": 1, "#30363d": 18, "#3fb950": 15, "#58a6ff": 9, "#8b949e": 42, "#a371f7": 1, "#c9d1d9": 2, "#d29922": 3, "#f0883e": 1, "#f0f6fc": 15, "#f85149": 6, "#ffffff": 1, "rgba(139,148,158,0.2)": 4, "rgba(163,113,247,0.2)": 1, "rgba(210,153,34,0.2)": 1, "rgba(219,109,40,0.2)": 1, "rgba(248,81,73,0.15)": 2, "rgba(248,81,73,0.2)": 2, "rgba(46,160,67,0.15)": 1, "rgba(46,160,67,0.2)": 5, "rgba(56,139,253,0.12)": 1, "rgba(56,139,253,0.2)": 2},
  "features/desktop/DesktopShell.tsx": {"#030712": 1, "#090d16": 1, "#0f172a": 1, "#1e3a8a": 1, "#34d399": 2, "#38bdf8": 3, "#60a5fa": 2, "#94a3b8": 5, "#ef4444": 1, "#f8fafc": 5, "#ffffff": 1, "rgba(0,0,0,0.3)": 1, "rgba(0,0,0,0.5)": 1, "rgba(0,0,0,0.6)": 2, "rgba(0,0,0,0.8)": 1, "rgba(15,23,42,0.75)": 1, "rgba(15,23,42,0.85)": 1, "rgba(15,23,42,0.95)": 2, "rgba(255,255,255,0.05)": 1, "rgba(255,255,255,0.08)": 2, "rgba(255,255,255,0.1)": 5, "rgba(255,255,255,0.15)": 4, "rgba(255,255,255,0.5)": 1, "rgba(59,130,246,0.2)": 1, "rgba(59,130,246,0.3)": 1, "rgba(59,130,246,0.4)": 1, "rgba(59,130,246,0.5)": 1},
  "features/desktop/DesktopWindow.tsx": {"#0f172a": 1, "#10b981": 1, "#1e293b": 1, "#333": 1, "#334155": 1, "#64748b": 1, "#94a3b8": 1, "#ef4444": 1, "#f59e0b": 1, "#f8fafc": 1, "rgba(0,0,0,0.25)": 1, "rgba(0,0,0,0.3)": 4, "rgba(0,0,0,0.45)": 1, "rgba(0,0,0,0.5)": 1},
  "features/desktop/InvFileExplorer.tsx": {"#0f172a": 5, "#10b981": 2, "#1e293b": 10, "#2563eb": 1, "#334155": 17, "#34d399": 7, "#38bdf8": 3, "#3b82f6": 5, "#475569": 1, "#60a5fa": 1, "#64748b": 2, "#93c5fd": 1, "#94a3b8": 10, "#eab308": 1, "#ef4444": 4, "#f87171": 7, "#f8fafc": 6, "#fbbf24": 3, "#fca5a5": 5, "#fde047": 1, "#fecaca": 1, "#fed7aa": 2, "#ffffff": 4, "rgba(16,185,129,0.15)": 1, "rgba(16,185,129,0.2)": 4, "rgba(16,185,129,0.4)": 2, "rgba(234,179,8,0.2)": 2, "rgba(234,179,8,0.4)": 1, "rgba(239,68,68,0.15)": 3, "rgba(239,68,68,0.2)": 6, "rgba(239,68,68,0.3)": 1, "rgba(239,68,68,0.4)": 2, "rgba(59,130,246,0.15)": 1, "rgba(59,130,246,0.2)": 2},
  "features/desktop/ModelStudioView.tsx": {"#0f172a": 4, "#10b981": 3, "#1e293b": 5, "#334155": 7, "#38bdf8": 1, "#3b82f6": 1, "#475569": 5, "#64748b": 1, "#6ee7b7": 3, "#93c5fd": 1, "#94a3b8": 9, "#cbd5e1": 4, "#d97706": 1, "#ef4444": 2, "#f59e0b": 4, "#f87171": 2, "#f8fafc": 4, "#fca5a5": 5, "#fde68a": 3, "#fff": 2, "rgba(16,185,129,0.15)": 1, "rgba(16,185,129,0.2)": 2, "rgba(239,68,68,0.15)": 2, "rgba(239,68,68,0.2)": 3, "rgba(245,158,11,0.15)": 2, "rgba(245,158,11,0.2)": 1},
  "features/desktop/ResourceExplorer.tsx": {"#0f172a": 22, "#10b981": 6, "#123": 1, "#125": 1, "#1e293b": 29, "#334155": 55, "#34d399": 12, "#38bdf8": 3, "#3b82f6": 7, "#475569": 6, "#60a5fa": 5, "#64748b": 8, "#8b5cf6": 1, "#93c5fd": 7, "#94a3b8": 52, "#c084fc": 2, "#cbd5e1": 2, "#d8b4fe": 1, "#e2e8f0": 2, "#ef4444": 7, "#f59e0b": 3, "#f87171": 13, "#f8fafc": 12, "#fbbf24": 7, "#fca5a5": 14, "#fde047": 1, "#fed7aa": 3, "#fff": 17, "#ffffff": 3, "rgba(0,0,0,0.2)": 6, "rgba(0,0,0,0.3)": 1, "rgba(148,163,184,0.2)": 1, "rgba(16,185,129,0.15)": 4, "rgba(16,185,129,0.2)": 5, "rgba(16,185,129,0.3)": 4, "rgba(168,85,247,0.08)": 1, "rgba(168,85,247,0.2)": 1, "rgba(168,85,247,0.25)": 1, "rgba(168,85,247,0.3)": 1, "rgba(234,179,8,0.1)": 2, "rgba(234,179,8,0.15)": 1, "rgba(234,179,8,0.2)": 3, "rgba(234,179,8,0.25)": 1, "rgba(234,179,8,0.3)": 1, "rgba(234,179,8,0.4)": 1, "rgba(239,68,68,0.1)": 5, "rgba(239,68,68,0.15)": 6, "rgba(239,68,68,0.2)": 9, "rgba(239,68,68,0.3)": 4, "rgba(239,68,68,0.4)": 6, "rgba(245,158,11,0.2)": 1, "rgba(245,158,11,0.3)": 1, "rgba(255,255,255,0.03)": 2, "rgba(255,255,255,0.05)": 1, "rgba(51,65,85,0.5)": 1, "rgba(59,130,246,0.08)": 1, "rgba(59,130,246,0.1)": 3, "rgba(59,130,246,0.15)": 2, "rgba(59,130,246,0.2)": 6, "rgba(59,130,246,0.25)": 1, "rgba(59,130,246,0.3)": 5},
  "features/desktop/TerminalSessionView.tsx": {"#0f172a": 6, "#1e293b": 2, "#334155": 6, "#38bdf8": 1, "#3b82f6": 1, "#475569": 1, "#4ade80": 1, "#60a5fa": 1, "#7f1d1d": 1, "#94a3b8": 4, "#ef4444": 1, "#f8fafc": 5, "#fbbf24": 1, "#fecaca": 2, "#fed7aa": 1, "rgba(0,0,0,0.2)": 1, "rgba(59,130,246,0.15)": 1, "rgba(59,130,246,0.3)": 1},
  "features/editor/ConflictResolutionModal.tsx": {"#0d1117": 1, "#161b22": 1, "#30363d": 2, "#58a6ff": 1, "#8b949e": 2, "#f85149": 5, "#fff": 1, "rgba(0,0,0,0.5)": 1, "rgba(0,0,0,0.75)": 1, "rgba(248,81,73,0.1)": 1},
  "features/editor/DiffViewer.tsx": {"#0d1117": 1, "#161b22": 1, "#30363d": 2, "#3fb950": 3, "#484f58": 2, "#8b949e": 1, "#c9d1d9": 2, "#f0f6fc": 1, "#f85149": 3, "rgba(248,81,73,0.15)": 1, "rgba(46,160,67,0.15)": 1},
  "features/editor/GitCommitModal.tsx": {"#0d1117": 3, "#161b22": 1, "#30363d": 6, "#58a6ff": 1, "#8b949e": 5, "#c9d1d9": 3, "#e3b341": 2, "#f0f6fc": 1, "#f85149": 1, "rgba(0,0,0,0.5)": 1, "rgba(0,0,0,0.75)": 1, "rgba(56,139,253,0.1)": 1},
  "features/editor/MonacoWorkspaceEditor.tsx": {"#070a0e": 1, "#090d13": 3, "#0d1117": 4, "#161b22": 4, "#1f242c": 1, "#21262d": 6, "#2ea043": 1, "#30363d": 7, "#3fb950": 4, "#484f58": 2, "#58a6ff": 9, "#79c0ff": 1, "#8b949e": 9, "#c9d1d9": 6, "#e3b341": 6, "#f0f6fc": 5, "#f85149": 3, "rgba(210,153,34,0.2)": 1, "rgba(227,179,65,0.15)": 2, "rgba(227,179,65,0.3)": 1, "rgba(248,81,73,0.15)": 1, "rgba(248,81,73,0.2)": 1, "rgba(46,160,67,0.12)": 1, "rgba(46,160,67,0.15)": 1, "rgba(46,160,67,0.2)": 1, "rgba(56,139,253,0.1)": 1, "rgba(56,139,253,0.12)": 2, "rgba(56,139,253,0.2)": 1, "rgba(56,139,253,0.3)": 1},
  "features/evidence/EvidenceViewer.tsx": {"#10b981": 1, "#d97706": 3, "#f87171": 1, "rgba(16,185,129,0.15)": 1, "rgba(234,179,8,0.08)": 1, "rgba(234,179,8,0.15)": 1, "rgba(234,179,8,0.3)": 1, "rgba(248,81,73,0.08)": 1, "rgba(248,81,73,0.1)": 2, "rgba(248,81,73,0.15)": 2, "rgba(248,81,73,0.3)": 1, "rgba(56,139,253,0.15)": 1},
  "features/mlops/ModelLineageView.tsx": {"#0d1117": 34, "#161b22": 13, "#1a7f37": 1, "#1f242c": 7, "#1f6feb": 1, "#21262d": 7, "#218": 1, "#30363d": 53, "#388bfd": 2, "#3d1214": 1, "#3fb950": 20, "#58a6ff": 40, "#8b949e": 108, "#94a3b8": 1, "#a0a8b2": 2, "#c9d1d9": 43, "#cf222e": 1, "#d29922": 4, "#e3b341": 3, "#eab308": 1, "#f0883e": 9, "#f0f6fc": 30, "#f59e0b": 3, "#f85149": 14, "#fde047": 1, "#fed7aa": 7, "#ff7b72": 10, "#ffb4a9": 1, "#ffffff": 2, "rgba(139,148,158,0.15)": 1, "rgba(160,168,178,0.15)": 2, "rgba(210,153,34,0.2)": 1, "rgba(234,179,8,0.12)": 1, "rgba(240,136,62,0.15)": 5, "rgba(248,81,73,0.12)": 3, "rgba(248,81,73,0.15)": 7, "rgba(248,81,73,0.2)": 1, "rgba(46,160,67,0.12)": 5, "rgba(46,160,67,0.15)": 1, "rgba(46,160,67,0.2)": 1, "rgba(56,139,253,0.12)": 1, "rgba(56,139,253,0.15)": 8, "rgba(56,139,253,0.2)": 1},
  "features/nodes/NodeDetail.tsx": {"#2ea043": 2, "#38bdf8": 1, "#3fb950": 6, "#58a6ff": 2, "#d29922": 6, "#f85149": 3, "rgba(110,118,129,0.2)": 1, "rgba(210,153,34,0.12)": 1, "rgba(210,153,34,0.15)": 1, "rgba(248,81,73,0.1)": 1, "rgba(46,160,67,0.15)": 2},
  "features/nodes/NodeList.tsx": {"#1e1e1e": 1, "#2d3748": 1, "#3fb950": 1, "#4ade80": 2, "#7dd3fc": 1, "#ef4444": 1, "#f59e0b": 1, "#fca5a5": 1, "#fde68a": 1, "#fff": 1, "#ffffff": 1, "rgba(210,153,34,0.15)": 1, "rgba(56,189,248,0.12)": 1, "rgba(56,189,248,0.3)": 1},
  "features/placement/PlacementExplainView.tsx": {"#d97706": 1, "rgba(16,185,129,0.1)": 1, "rgba(16,185,129,0.15)": 1, "rgba(234,179,8,0.15)": 1, "rgba(234,179,8,0.3)": 1},
  "features/placement/PlacementSimulator.tsx": {"#334155": 3, "#93c5fd": 1, "#94a3b8": 2, "#ef4444": 4, "#f87171": 1, "#fbbf24": 4, "#fca5a5": 4, "#fff": 3, "#ffffff": 2, "rgba(234,179,8,0.15)": 2, "rgba(234,179,8,0.3)": 2, "rgba(239,68,68,0.1)": 4, "rgba(35,134,54,0.1)": 1},
  "features/placement/ResourceTopologyGraph.tsx": {"#ffffff": 2, "rgba(16,185,129,0.08)": 1},
  "features/recovery/DistributedRecoveryView.tsx": {"#0d1117": 3, "#161b22": 9, "#21262d": 1, "#30363d": 12, "#3fb950": 6, "#58a6ff": 8, "#8b949e": 20, "#a371f7": 1, "#e3b341": 1, "#f0f6fc": 8, "#f85149": 7, "rgba(248,81,73,0.15)": 1, "rgba(46,160,67,0.15)": 1, "rgba(56,139,253,0.1)": 1, "rgba(56,139,253,0.15)": 1, "rgba(56,139,253,0.4)": 1},
  "features/release/ReleaseCandidateView.tsx": {"#0d1117": 1, "#161b22": 7, "#21262d": 2, "#30363d": 11, "#3fb950": 10, "#58a6ff": 5, "#8b949e": 22, "#c9d1d9": 2, "#d29922": 2, "#f0f6fc": 7, "#f85149": 5, "rgba(139,148,158,0.1)": 1, "rgba(139,148,158,0.2)": 1, "rgba(248,81,73,0.15)": 1, "rgba(248,81,73,0.2)": 2, "rgba(46,160,67,0.15)": 1, "rgba(46,160,67,0.2)": 2, "rgba(56,139,253,0.12)": 1, "rgba(56,139,253,0.2)": 1},
  "features/release/releaseEngine.ts": {"#0d1117": 3, "#6e7681": 2, "#c9d1d9": 1},
  "features/runs/RunDetail.tsx": {"#047857": 2, "#0d1117": 1, "#10b981": 9, "#1d4ed8": 1, "#21262d": 1, "#22c55e": 1, "#30363d": 1, "#34d399": 2, "#38bdf8": 2, "#3b82f6": 2, "#3fb950": 1, "#4ade80": 1, "#58a6ff": 6, "#60a5fa": 1, "#8b949e": 4, "#93c5fd": 7, "#94a3b8": 2, "#b45309": 1, "#c9d1d9": 1, "#d97706": 6, "#e2e8f0": 1, "#eab308": 2, "#ef4444": 7, "#f59e0b": 3, "#f85149": 7, "#f87171": 2, "#fca5a5": 3, "#fef08a": 1, "#ffffff": 1, "rgba(0,0,0,0.65)": 2, "rgba(110,118,129,0.2)": 1, "rgba(16,185,129,0.1)": 1, "rgba(16,185,129,0.12)": 2, "rgba(16,185,129,0.15)": 1, "rgba(217,119,6,0.12)": 1, "rgba(217,119,6,0.2)": 2, "rgba(218,54,51,0.2)": 2, "rgba(234,179,8,0.1)": 1, "rgba(234,179,8,0.12)": 1, "rgba(234,179,8,0.3)": 1, "rgba(239,68,68,0.1)": 4, "rgba(239,68,68,0.15)": 1, "rgba(245,158,11,0.12)": 1, "rgba(248,81,73,0.1)": 3, "rgba(34,197,94,0.08)": 1, "rgba(46,160,67,0.2)": 1, "rgba(56,139,253,0.15)": 1, "rgba(59,130,246,0.08)": 1, "rgba(59,130,246,0.1)": 7, "rgba(59,130,246,0.15)": 1, "rgba(59,130,246,0.25)": 6, "rgba(59,130,246,0.3)": 1},
  "features/runs/RunList.tsx": {"#0284c7": 1, "#06b6d4": 1, "#10b981": 3, "#3b82f6": 3, "#60a5fa": 1, "#64748b": 1, "#6b7280": 1, "#8b5cf6": 2, "#d97706": 2, "#ef4444": 4, "#f59e0b": 1, "#f85149": 2, "#f97316": 1, "#fca5a5": 2, "#fff": 1, "#ffffff": 1, "rgba(100,116,139,0.15)": 1, "rgba(107,114,128,0.15)": 1, "rgba(139,92,246,0.1)": 1, "rgba(139,92,246,0.15)": 1, "rgba(139,92,246,0.3)": 1, "rgba(16,185,129,0.15)": 1, "rgba(2,132,199,0.15)": 1, "rgba(217,119,6,0.15)": 1, "rgba(239,68,68,0.08)": 1, "rgba(239,68,68,0.1)": 1, "rgba(239,68,68,0.15)": 1, "rgba(245,158,11,0.15)": 1, "rgba(249,115,22,0.15)": 1, "rgba(59,130,246,0.1)": 1, "rgba(59,130,246,0.15)": 1, "rgba(59,130,246,0.2)": 1, "rgba(59,130,246,0.3)": 1, "rgba(6,182,212,0.15)": 1},
  "features/runs/SealRecordPanel.tsx": {"#0d1117": 4, "#161b22": 13, "#21262d": 2, "#30363d": 8, "#3fb950": 4, "#58a6ff": 8, "#8b949e": 30, "#a0a8b2": 2, "#c9d1d9": 9, "#d29922": 2, "#e3b341": 3, "#f0f6fc": 14, "#f85149": 4, "#ff7b72": 7, "rgba(160,168,178,0.15)": 1, "rgba(210,153,34,0.1)": 1, "rgba(210,153,34,0.15)": 2, "rgba(210,153,34,0.2)": 1, "rgba(210,153,34,0.4)": 2, "rgba(248,81,73,0.15)": 6, "rgba(248,81,73,0.4)": 2, "rgba(46,160,67,0.15)": 4, "rgba(46,160,67,0.4)": 4, "rgba(56,139,253,0.15)": 1, "rgba(56,139,253,0.3)": 1},
  "features/studio/DeveloperStudio.tsx": {"#0d1117": 2, "#161b22": 1, "#22c55e": 1, "#2ea043": 5, "#30363d": 2, "#304": 2, "#388bfd": 1, "#3b82f6": 1, "#3fb950": 25, "#58a6ff": 14, "#86efac": 1, "#8b949e": 4, "#93c5fd": 1, "#bc8cff": 1, "#c9d1d9": 1, "#d29922": 22, "#e6edf3": 2, "#ef4444": 2, "#f85149": 15, "#fbbf24": 1, "#fca5a5": 2, "#ffffff": 2, "rgba(0,0,0,0.2)": 1, "rgba(0,0,0,0.6)": 2, "rgba(139,148,158,0.2)": 1, "rgba(139,148,158,0.3)": 1, "rgba(163,113,247,0.2)": 1, "rgba(210,153,34,0.08)": 3, "rgba(210,153,34,0.12)": 3, "rgba(210,153,34,0.15)": 1, "rgba(210,153,34,0.2)": 5, "rgba(210,153,34,0.25)": 1, "rgba(210,153,34,0.35)": 1, "rgba(210,153,34,0.4)": 3, "rgba(234,179,8,0.15)": 1, "rgba(234,179,8,0.3)": 1, "rgba(239,68,68,0.1)": 1, "rgba(239,68,68,0.15)": 1, "rgba(248,81,73,0.08)": 1, "rgba(248,81,73,0.12)": 1, "rgba(248,81,73,0.15)": 1, "rgba(248,81,73,0.2)": 4, "rgba(248,81,73,0.4)": 2, "rgba(34,197,94,0.15)": 1, "rgba(46,160,67,0.04)": 1, "rgba(46,160,67,0.05)": 3, "rgba(46,160,67,0.15)": 2, "rgba(46,160,67,0.2)": 7, "rgba(46,160,67,0.3)": 3, "rgba(46,160,67,0.4)": 1, "rgba(56,139,253,0.05)": 2, "rgba(56,139,253,0.08)": 5, "rgba(56,139,253,0.15)": 1, "rgba(56,139,253,0.2)": 2, "rgba(56,139,253,0.25)": 1, "rgba(56,139,253,0.3)": 2, "rgba(59,130,246,0.15)": 1},
  "features/terminal/WebTerminal.tsx": {"#090d16": 1, "#0d1117": 1, "#161b22": 1, "#1c1917": 1, "#238636": 1, "#30363d": 2, "#451a03": 1, "#58a6ff": 1, "#6b7280": 1, "#7f1d1d": 1, "#8b949e": 5, "#c9d1d9": 2, "#d29922": 1, "#d97706": 1, "#ea580c": 1, "#ef4444": 2, "#f0f6fc": 2, "#f85149": 1, "#fb923c": 1, "#fde68a": 2, "#fecaca": 1, "#fed7aa": 1, "#fff": 1},
  "features/workspaces/ExecutionResultView.tsx": {"rgba(16,185,129,0.15)": 1},
  "features/workspaces/WorkspaceCreateModal.tsx": {"rgba(0,0,0,0.65)": 1},
  "features/workspaces/WorkspaceList.tsx": {"#34d399": 1, "#f59e0b": 1, "#f87171": 1, "rgba(16,185,129,0.15)": 1, "rgba(16,185,129,0.3)": 1, "rgba(239,68,68,0.15)": 1, "rgba(239,68,68,0.3)": 1, "rgba(245,158,11,0.15)": 1, "rgba(245,158,11,0.3)": 1},
  "shared/api/adapterObservation.ts": {"#218": 2},
  "shared/ui/Button.tsx": {"#ffffff": 2},
  "shared/ui/Header.tsx": {"#58a6ff": 1, "#60a5fa": 1, "#79c0ff": 1, "#f85149": 3, "rgba(56,139,253,0.12)": 1, "rgba(56,139,253,0.25)": 1, "rgba(56,139,253,0.3)": 1, "rgba(59,130,246,0.2)": 1, "rgba(59,130,246,0.4)": 1},
  "shared/ui/RiskBadge.tsx": {"rgba(16,185,129,0.15)": 1, "rgba(239,68,68,0.15)": 1, "rgba(245,158,11,0.15)": 1, "rgba(59,130,246,0.15)": 1},
};

describe('ACC-09 WCAG 2.2 AA Contrast Compliance & Strict Fail-Closed Token Inventory', () => {
  // Extract theme token blocks
  const lightBlockMatch = indexCss.match(/:root\s*\{([^\}]+)\}/);
  const darkBlockMatch = indexCss.match(/\[data-theme=['"]dark['"]\]\s*\{([^\}]+)\}/);

  if (!lightBlockMatch || !darkBlockMatch) {
    throw new Error('Failed to extract light/dark token blocks from index.css');
  }

  const lightTokens = extractTokens(lightBlockMatch[1]);
  const darkTokens = extractTokens(darkBlockMatch[1]);

  // 1. Text Tokens on Canvas & Surface (>= 4.5:1 for regular text)
  it('ACC-09: Text tokens achieve >= 4.5:1 against canvas and surface in both themes', () => {
    const checkTextContrast = (
      tokens: Record<string, string>,
      themeName: string,
      textTokens: string[],
      bgTokens: string[]
    ) => {
      for (const textToken of textTokens) {
        const fg = tokens[textToken];
        expect(fg, `${themeName} ${textToken} exists`).toBeDefined();

        for (const bgToken of bgTokens) {
          const bg = tokens[bgToken];
          expect(bg, `${themeName} ${bgToken} exists`).toBeDefined();

          const cr = getContrast(fg, bg);
          expect(
            cr,
            `${themeName} ${textToken} (${fg}) on ${bgToken} (${bg}) contrast ${cr.toFixed(2)}:1 must be >= 4.5:1`
          ).toBeGreaterThanOrEqual(4.5);
        }
      }
    };

    const textTokenList = [
      '--color-text-primary',
      '--color-text-secondary',
      '--color-text-muted',
    ];
    const bgTokenList = [
      '--color-bg-canvas',
      '--color-bg-surface',
      '--color-bg-subtle',
    ];

    checkTextContrast(lightTokens, 'Light', textTokenList, bgTokenList);
    checkTextContrast(darkTokens, 'Dark', textTokenList, bgTokenList);
  });

  // 2. UI Component Boundaries (>= 3.0:1 for non-text UI contrast)
  it('ACC-09: Interactive borders achieve >= 3.0:1 against subtle and surface in both themes', () => {
    const checkBorderContrast = (
      tokens: Record<string, string>,
      themeName: string,
      borderTokens: string[],
      bgTokens: string[]
    ) => {
      for (const borderToken of borderTokens) {
        const fg = tokens[borderToken];
        expect(fg, `${themeName} ${borderToken} exists`).toBeDefined();

        for (const bgToken of bgTokens) {
          const bg = tokens[bgToken];
          expect(bg, `${themeName} ${bgToken} exists`).toBeDefined();

          const cr = getContrast(fg, bg);
          expect(
            cr,
            `${themeName} ${borderToken} (${fg}) on ${bgToken} (${bg}) contrast ${cr.toFixed(2)}:1 must be >= 3.0:1`
          ).toBeGreaterThanOrEqual(3.0);
        }
      }
    };

    const borderTokenList = [
      '--color-border-subtle',
      '--color-border-strong',
    ];
    const bgTokenList = [
      '--color-bg-surface',
      '--color-bg-subtle',
    ];

    checkBorderContrast(lightTokens, 'Light', borderTokenList, bgTokenList);
    checkBorderContrast(darkTokens, 'Dark', borderTokenList, bgTokenList);
  });

  // 3. Status Colors on Backgrounds (>= 4.5:1 for status indicators/text)
  it('ACC-09: Status text colors achieve >= 4.5:1 against canvas, surface, and subtle in both themes', () => {
    const checkStatusContrast = (
      tokens: Record<string, string>,
      themeName: string,
      statusTokens: string[],
      bgTokens: string[]
    ) => {
      for (const statusToken of statusTokens) {
        const fg = tokens[statusToken];
        expect(fg, `${themeName} ${statusToken} exists`).toBeDefined();

        for (const bgToken of bgTokens) {
          const bg = tokens[bgToken];
          expect(bg, `${themeName} ${bgToken} exists`).toBeDefined();

          const cr = getContrast(fg, bg);
          expect(
            cr,
            `${themeName} ${statusToken} (${fg}) on ${bgToken} (${bg}) contrast ${cr.toFixed(2)}:1 must be >= 4.5:1`
          ).toBeGreaterThanOrEqual(4.5);
        }
      }
    };

    const statusTokenList = [
      '--color-status-online',
      '--color-status-degraded',
      '--color-status-offline',
      '--color-status-neutral',
      '--color-status-active',
      '--color-status-lost',
      '--color-status-unknown',
    ];
    const bgTokenList = [
      '--color-bg-canvas',
      '--color-bg-surface',
      '--color-bg-subtle',
    ];

    checkStatusContrast(lightTokens, 'Light', statusTokenList, bgTokenList);
    checkStatusContrast(darkTokens, 'Dark', statusTokenList, bgTokenList);
  });

  // 4. Border Strong Hierarchy (strong must have greater contrast than subtle)
  it('ACC-09: border-strong provides strictly higher contrast than border-subtle in both themes', () => {
    const lightSubtleCr = getContrast(lightTokens['--color-border-subtle'], lightTokens['--color-bg-surface']);
    const lightStrongCr = getContrast(lightTokens['--color-border-strong'], lightTokens['--color-bg-surface']);
    expect(lightStrongCr).toBeGreaterThan(lightSubtleCr);

    const darkSubtleCr = getContrast(darkTokens['--color-border-subtle'], darkTokens['--color-bg-surface']);
    const darkStrongCr = getContrast(darkTokens['--color-border-strong'], darkTokens['--color-bg-surface']);
    expect(darkStrongCr).toBeGreaterThan(darkSubtleCr);
  });

  // 5. Button Backgrounds on White Text
  it('ACC-09: Button background tokens with white text exceed 4.5:1 in both themes', () => {
    const white = '#ffffff';

    // Light Theme
    const lightPrimaryBg = lightTokens['--color-brand-primary-bg'];
    const lightOfflineBg = lightTokens['--color-status-offline-bg'];
    expect(getContrast(white, lightPrimaryBg)).toBeGreaterThanOrEqual(4.5);
    expect(getContrast(white, lightOfflineBg)).toBeGreaterThanOrEqual(4.5);

    // Dark Theme
    const darkPrimaryBg = darkTokens['--color-brand-primary-bg'];
    const darkOfflineBg = darkTokens['--color-status-offline-bg'];
    expect(getContrast(white, darkPrimaryBg)).toBeGreaterThanOrEqual(4.5);
    expect(getContrast(white, darkOfflineBg)).toBeGreaterThanOrEqual(4.5);
  });

  // 6. [F1.a] RiskBadge Alpha-Composite Contrast Verification across All Themes and Underlays
  it('ACC-09 / RiskBadge F1.a: RiskBadge text on 15% RGBA tint over canvas/surface/subtle achieves >= 4.5:1 in both themes', () => {
    const riskTints: Record<string, [number, number, number]> = {
      '--color-risk-l0': [16, 185, 129], // rgba(16, 185, 129, 0.15)
      '--color-risk-l1': [59, 130, 246], // rgba(59, 130, 246, 0.15)
      '--color-risk-l2': [245, 158, 11], // rgba(245, 158, 11, 0.15)
      '--color-risk-l3': [239, 68, 68],  // rgba(239, 68, 68, 0.15)
    };

    const lightUnderlays = [
      { name: 'canvas', hex: lightTokens['--color-bg-canvas'] },
      { name: 'surface', hex: lightTokens['--color-bg-surface'] },
      { name: 'subtle', hex: lightTokens['--color-bg-subtle'] },
    ];

    const darkUnderlays = [
      { name: 'canvas', hex: darkTokens['--color-bg-canvas'] },
      { name: 'surface', hex: darkTokens['--color-bg-surface'] },
      { name: 'subtle', hex: darkTokens['--color-bg-subtle'] },
    ];

    // Light theme alpha-composite checks
    for (const [tokenName, tint] of Object.entries(riskTints)) {
      const fg = lightTokens[tokenName];
      for (const underlay of lightUnderlays) {
        const compositeBg = blendRgba(tint, 0.15, underlay.hex);
        const cr = getContrast(fg, compositeBg);
        expect(
          cr,
          `Light ${tokenName} (${fg}) on 15% tint over ${underlay.name} (${underlay.hex}) -> composite ${compositeBg} contrast ${cr.toFixed(3)}:1 must be >= 4.5:1`
        ).toBeGreaterThanOrEqual(4.5);
      }
    }

    // Dark theme alpha-composite checks
    for (const [tokenName, tint] of Object.entries(riskTints)) {
      const fg = darkTokens[tokenName];
      for (const underlay of darkUnderlays) {
        const compositeBg = blendRgba(tint, 0.15, underlay.hex);
        const cr = getContrast(fg, compositeBg);
        expect(
          cr,
          `Dark ${tokenName} (${fg}) on 15% tint over ${underlay.name} (${underlay.hex}) -> composite ${compositeBg} contrast ${cr.toFixed(3)}:1 must be >= 4.5:1`
        ).toBeGreaterThanOrEqual(4.5);
      }
    }
  });

  // 7. [F1.b & F1.c] Real Usage Pairs: Component DOM Rendering & Binding Verification for RunDetail, NodeList, and DeveloperStudio
  it('ACC-09 / F1.b & F1.c: Component DOM Rendering Verification: RunDetail, NodeList, and DeveloperStudio bind to var(--color-text-inverse)', async () => {
    const container = document.createElement('div');
    container.setAttribute('data-theme', 'dark');
    document.body.appendChild(container);
    const root = createRoot(container);

    vi.spyOn(client, 'apiClient').mockResolvedValue({} as any);
    vi.spyOn(projectObservation, 'fetchProjectWorkspaces').mockResolvedValue([]);

    try {
      // 1) RunDetail.tsx:1080-1098 Lifecycle Step Indicator (isPassed background)
      const sampleRun = {
        id: 'run_contrast_test',
        projectId: 'prj_contrast_test',
        status: 'running',
        state: 'running',
        targetNodeId: 'nod_01JABCDEF01',
        createdAt: '2026-09-21T10:00:00Z',
      };

      await act(async () => {
        root.render(<RunDetail run={sampleRun as any} onBack={() => {}} />);
      });

      const passedStep = Array.from(container.querySelectorAll('div')).find(
        (el) => el.textContent === '✓' && el.style.borderRadius === '50%'
      );
      expect(passedStep, 'RunDetail lifecycle stepper must render a passed step indicator with checkmark ✓').toBeDefined();
      expect(passedStep?.style.color, 'RunDetail passed step style.color must bind to var(--color-text-inverse)').toBe('var(--color-text-inverse)');
      expect(passedStep?.style.backgroundColor, 'RunDetail passed step background must bind to var(--color-status-online)').toBe('var(--color-status-online)');

      // Verify contrast ratio of the bound token against the bound background (--color-status-online)
      const darkStatusOnline = darkTokens['--color-status-online']; // #22c55e
      const darkTextInverse = darkTokens['--color-text-inverse'];   // #0f172a
      const runDetailDarkCr = getContrast(darkStatusOnline, darkTextInverse);
      expect(runDetailDarkCr, 'RunDetail dark isPassed step with text-inverse must be >= 4.5:1').toBeGreaterThanOrEqual(4.5);

      const lightStatusOnline = lightTokens['--color-status-online']; // #15803d
      const lightTextInverse = lightTokens['--color-text-inverse'];   // #ffffff
      const runDetailLightCr = getContrast(lightStatusOnline, lightTextInverse);
      expect(runDetailLightCr, 'RunDetail light isPassed step with text-inverse must be >= 4.5:1').toBeGreaterThanOrEqual(4.5);

      // 2) NodeList.tsx:431-432 Observation-only Studio Button
      const sampleNode = {
        id: 'nod_01JABCDEF01',
        hostname: 'Node-01-Observation',
        os: 'linux',
        roles: ['Worker'],
        status: 'online',
        observationOnly: true,
      };

      await act(async () => {
        root.render(
          <NodeList
            nodes={[sampleNode as any]}
            onSelectNode={() => {}}
            onOpenStudio={() => {}}
          />
        );
      });

      const obsBtn = Array.from(container.querySelectorAll('button')).find((b) =>
        b.textContent?.includes('Studio 열기')
      );
      expect(obsBtn, 'NodeList observationOnly node must render Studio 열기 button').toBeDefined();
      expect(obsBtn?.style.color, 'NodeList observationOnly button style.color must bind to var(--color-text-inverse)').toBe('var(--color-text-inverse)');
      expect(obsBtn?.style.backgroundColor, 'NodeList observationOnly button background must bind to var(--color-border-strong)').toBe('var(--color-border-strong)');

      const darkBorderStrong = darkTokens['--color-border-strong']; // #9ca3af
      const nodeListDarkCr = getContrast(darkBorderStrong, darkTextInverse);
      expect(nodeListDarkCr, 'NodeList observationOnly dark button with text-inverse must be >= 4.5:1').toBeGreaterThanOrEqual(4.5);

      const lightBorderStrong = lightTokens['--color-border-strong']; // #475569
      const nodeListLightCr = getContrast(lightBorderStrong, lightTextInverse);
      expect(nodeListLightCr, 'NodeList observationOnly light button with text-inverse must be >= 4.5:1').toBeGreaterThanOrEqual(4.5);

      // 3) DeveloperStudio.tsx:905-906 Stepper Circle
      const sampleProject = { id: 'prj_test', name: 'Test' };

      await act(async () => {
        root.render(
          <DeveloperStudio
            project={sampleProject as any}
            nodes={[]}
            runs={[]}
          />
        );
      });

      const step2Circle = Array.from(container.querySelectorAll('span')).find(
        (s) => s.textContent === '2' && s.style.borderRadius === '50%'
      );
      expect(step2Circle, 'DeveloperStudio must render inactive step 2 circle indicator').toBeDefined();
      expect(step2Circle?.style.color, 'DeveloperStudio inactive step circle style.color must bind to var(--color-text-inverse)').toBe('var(--color-text-inverse)');
      expect(step2Circle?.style.backgroundColor, 'DeveloperStudio inactive step circle background must bind to var(--color-border-strong)').toBe('var(--color-border-strong)');

      const devStudioUpcomingDarkCr = getContrast(darkBorderStrong, darkTextInverse);
      expect(devStudioUpcomingDarkCr, 'DeveloperStudio upcoming step dark with text-inverse must be >= 4.5:1').toBeGreaterThanOrEqual(4.5);
      const devStudioPassedDarkCr = getContrast(darkStatusOnline, darkTextInverse);
      expect(devStudioPassedDarkCr, 'DeveloperStudio passed step dark with text-inverse must be >= 4.5:1').toBeGreaterThanOrEqual(4.5);
    } finally {
      act(() => {
        root.unmount();
      });
      container.remove();
      vi.restoreAllMocks();
    }
  });

  // 8. [Card 186 / ACC-09] Component DOM Rendering & Binding Verification: NodeList Status Badges (active, lost, unknown)
  it('ACC-09 / Card 186: NodeList Status Badges bind to design tokens and maintain non-color semantic distinction', async () => {
    const container = document.createElement('div');
    container.setAttribute('data-theme', 'light');
    document.body.appendChild(container);
    const root = createRoot(container);

    const testNodes = [
      {
        id: 'nod_active_01',
        hostname: 'node-active-prod',
        status: 'active',
        os: 'linux',
        cpuCores: 16,
        cpuUsagePercent: 25,
        memoryTotalBytes: 64 * 1024 ** 3,
        memoryUsedBytes: 16 * 1024 ** 3,
        storageTotalBytes: 1000 * 1024 ** 3,
        storageUsedBytes: 200 * 1024 ** 3,
        gpuCount: 0,
        heartbeatAt: '2026-10-01T10:00:00Z',
      },
      {
        id: 'nod_lost_01',
        hostname: 'node-lost-dc2',
        status: 'lost',
        os: 'linux',
        telemetryUnavailable: true,
        cpuCores: 8,
        cpuUsagePercent: 0,
        memoryTotalBytes: 32 * 1024 ** 3,
        memoryUsedBytes: 0,
        storageTotalBytes: 500 * 1024 ** 3,
        storageUsedBytes: 0,
        gpuCount: 0,
        heartbeatAt: '2026-10-01T09:00:00Z',
      },
      {
        id: 'nod_unknown_01',
        hostname: 'node-unknown-edge',
        status: 'unknown',
        os: 'linux',
        observationOnly: true,
        cpuCores: 4,
        cpuUsagePercent: 10,
        memoryTotalBytes: 16 * 1024 ** 3,
        memoryUsedBytes: 2 * 1024 ** 3,
        storageTotalBytes: 250 * 1024 ** 3,
        storageUsedBytes: 20 * 1024 ** 3,
        gpuCount: 0,
        heartbeatAt: '2026-10-01T10:00:00Z',
      },
    ];

    try {
      await act(async () => {
        root.render(<NodeList nodes={testNodes as any} onSelectNode={() => {}} />);
      });

      // 1) Active Node Badge & Notice Binding
      const activeBadge = container.querySelector('[data-testid="node-status-badge-nod_active_01"]') as HTMLElement;
      expect(activeBadge, 'Active node badge must render').not.toBeNull();
      expect(activeBadge.style.color, 'Active badge text color must bind to var(--color-status-active)').toBe('var(--color-status-active)');
      expect(activeBadge.style.borderColor, 'Active badge border must bind to var(--color-status-active)').toBe('var(--color-status-active)');
      const activeDot = activeBadge.querySelector('span') as HTMLElement;
      expect(activeDot.style.backgroundColor, 'Active badge dot must bind to var(--color-status-active)').toBe('var(--color-status-active)');

      const activeNotice = container.querySelector('[data-testid="node-active-status-notice-nod_active_01"]') as HTMLElement;
      expect(activeNotice, 'Active status notice banner must render').not.toBeNull();
      expect(activeNotice.style.color, 'Active notice banner color must bind to var(--color-status-active)').toBe('var(--color-status-active)');

      // Non-color semantic distinction
      expect(activeBadge.textContent).toContain('ACTIVE');
      expect(activeNotice.textContent).toContain('ℹ️');

      // 2) Lost Node Badge (telemetryUnavailable branch) Binding
      const lostBadge = container.querySelector('[data-testid="node-status-badge-nod_lost_01"]') as HTMLElement;
      expect(lostBadge, 'Lost node badge must render').not.toBeNull();
      expect(lostBadge.style.color, 'Lost badge text color must bind to var(--color-status-lost)').toBe('var(--color-status-lost)');
      expect(lostBadge.style.borderColor, 'Lost badge border must bind to var(--color-status-lost)').toBe('var(--color-status-lost)');
      const lostDot = lostBadge.querySelector('span') as HTMLElement;
      expect(lostDot.style.backgroundColor, 'Lost badge dot must bind to var(--color-status-lost)').toBe('var(--color-status-lost)');

      // Non-color semantic distinction
      const lostCard = container.querySelector('[data-testid="node-card-nod_lost_01"]');
      expect(lostCard?.getAttribute('role'), 'Lost node card must have alert role').toBe('alert');
      expect(lostBadge.textContent).toContain('LOST');
      expect(lostCard?.textContent).toContain('🔴');

      // 3) Unknown Node Badge & Observation-only Banner Binding
      const unknownBadge = container.querySelector('[data-testid="node-status-badge-nod_unknown_01"]') as HTMLElement;
      expect(unknownBadge, 'Unknown node badge must render').not.toBeNull();
      expect(unknownBadge.style.color, 'Unknown badge text color must bind to var(--color-status-unknown)').toBe('var(--color-status-unknown)');
      expect(unknownBadge.style.borderColor, 'Unknown badge border must bind to var(--color-status-unknown)').toBe('var(--color-status-unknown)');
      const unknownDot = unknownBadge.querySelector('span') as HTMLElement;
      expect(unknownDot.style.backgroundColor, 'Unknown badge dot must bind to var(--color-status-unknown)').toBe('var(--color-status-unknown)');

      const unknownCard = container.querySelector('[data-testid="node-card-nod_unknown_01"]');
      expect(unknownBadge.textContent).toContain('UNKNOWN');

      // 4) Contrast Verifications in Light Theme
      const lightActiveCr = getContrast(lightTokens['--color-status-active'], lightTokens['--color-bg-surface']);
      expect(lightActiveCr, 'Light --color-status-active on surface must be >= 4.5:1').toBeGreaterThanOrEqual(4.5);
      const lightLostCr = getContrast(lightTokens['--color-status-lost'], lightTokens['--color-bg-surface']);
      expect(lightLostCr, 'Light --color-status-lost on surface must be >= 4.5:1').toBeGreaterThanOrEqual(4.5);
      const lightUnknownCr = getContrast(lightTokens['--color-status-unknown'], lightTokens['--color-bg-surface']);
      expect(lightUnknownCr, 'Light --color-status-unknown on surface must be >= 4.5:1').toBeGreaterThanOrEqual(4.5);

      // 5) Contrast Verifications in Dark Theme
      const darkActiveCr = getContrast(darkTokens['--color-status-active'], darkTokens['--color-bg-surface']);
      expect(darkActiveCr, 'Dark --color-status-active on surface must be >= 4.5:1').toBeGreaterThanOrEqual(4.5);
      const darkLostCr = getContrast(darkTokens['--color-status-lost'], darkTokens['--color-bg-surface']);
      expect(darkLostCr, 'Dark --color-status-lost on surface must be >= 4.5:1').toBeGreaterThanOrEqual(4.5);
      const darkUnknownCr = getContrast(darkTokens['--color-status-unknown'], darkTokens['--color-bg-surface']);
      expect(darkUnknownCr, 'Dark --color-status-unknown on surface must be >= 4.5:1').toBeGreaterThanOrEqual(4.5);
    } finally {
      act(() => {
        root.unmount();
      });
      container.remove();
    }
  });

  // 9. [F1 & Card 186 Revert-Fail Probes] Mutating fixes back to defective combinations strictly fails
  it('ACC-09 Revert-Fail Probes: Defective color combinations strictly fail WCAG AA criteria', () => {
    // Probe 1: RiskBadge light L1 with former #2563eb on 15% tint over light surface
    const defectiveLightL1 = '#2563eb';
    const lightSurfaceCompositeL1 = blendRgba([59, 130, 246], 0.15, lightTokens['--color-bg-surface']);
    const probe1Cr = getContrast(defectiveLightL1, lightSurfaceCompositeL1);
    expect(probe1Cr, 'Defective light L1 on light surface composite must fail 4.5:1').toBeLessThan(4.5);
    expect(probe1Cr).toBeCloseTo(4.347, 2);

    // Probe 2: RiskBadge light L2 with former #b45309 on 15% tint over light surface
    const defectiveLightL2 = '#b45309';
    const lightSurfaceCompositeL2 = blendRgba([245, 158, 11], 0.15, lightTokens['--color-bg-surface']);
    const probe2Cr = getContrast(defectiveLightL2, lightSurfaceCompositeL2);
    expect(probe2Cr, 'Defective light L2 on light surface composite must fail 4.5:1').toBeLessThan(4.5);
    expect(probe2Cr).toBeCloseTo(4.469, 2);

    // Probe 3: RiskBadge light L0 with former #047857 on 15% tint over light subtle
    const defectiveLightL0 = '#047857';
    const lightSubtleCompositeL0 = blendRgba([16, 185, 129], 0.15, lightTokens['--color-bg-subtle']);
    const probe3Cr = getContrast(defectiveLightL0, lightSubtleCompositeL0);
    expect(probe3Cr, 'Defective light L0 on light subtle composite must fail 4.5:1').toBeLessThan(4.5);
    expect(probe3Cr).toBeCloseTo(4.388, 2);

    // Probe 4: RiskBadge dark L0 with former #10b981 on 15% tint over dark subtle
    const defectiveDarkL0 = '#10b981';
    const darkSubtleCompositeL0 = blendRgba([16, 185, 129], 0.15, darkTokens['--color-bg-subtle']);
    const probe4Cr = getContrast(defectiveDarkL0, darkSubtleCompositeL0);
    expect(probe4Cr, 'Defective dark L0 on dark subtle composite must fail 4.5:1').toBeLessThan(4.5);
    expect(probe4Cr).toBeCloseTo(4.495, 2);

    // Probe 5: RunDetail dark isPassed with hardcoded white #ffffff on status-online #22c55e
    const probe5Cr = getContrast('#22c55e', '#ffffff');
    expect(probe5Cr, 'RunDetail dark isPassed white text on status-online must fail 4.5:1').toBeLessThan(4.5);
    expect(probe5Cr).toBeCloseTo(2.279, 2);

    // Probe 6: NodeList & DeveloperStudio dark border-strong #9ca3af with hardcoded white #ffffff
    const probe6Cr = getContrast('#9ca3af', '#ffffff');
    expect(probe6Cr, 'border-strong with hardcoded white text must fail 4.5:1').toBeLessThan(4.5);
    expect(probe6Cr).toBeCloseTo(2.539, 2);

    // Probe 7: Card 186 NodeList active status former hardcoded literal #38bdf8 on light surface (2.14:1)
    const defectiveLightActive = '#38bdf8';
    const probe7Cr = getContrast(defectiveLightActive, lightTokens['--color-bg-surface']);
    expect(probe7Cr, 'Defective light active #38bdf8 on light surface must fail 4.5:1').toBeLessThan(4.5);
    expect(probe7Cr).toBeCloseTo(2.14, 1);

    // Probe 8: Card 186 NodeList lost status former hardcoded literal #f85149 on light surface (3.35:1)
    const defectiveLightLost = '#f85149';
    const probe8Cr = getContrast(defectiveLightLost, lightTokens['--color-bg-surface']);
    expect(probe8Cr, 'Defective light lost #f85149 on light surface must fail 4.5:1').toBeLessThan(4.5);
    expect(probe8Cr).toBeCloseTo(3.35, 1);

    // Probe 9: Card 186 NodeList unknown status former hardcoded literal #d29922 on light surface (2.52:1)
    const defectiveLightUnknown = '#d29922';
    const probe9Cr = getContrast(defectiveLightUnknown, lightTokens['--color-bg-surface']);
    expect(probe9Cr, 'Defective light unknown #d29922 on light surface must fail 4.5:1').toBeLessThan(4.5);
    expect(probe9Cr).toBeCloseTo(2.52, 1);

    // Legacy Token Reverts:
    // Legacy Dark --color-border-subtle: #374151
    expect(getContrast('#374151', darkTokens['--color-bg-surface'])).toBeLessThan(3.0); // 1.72:1
    expect(getContrast('#374151', darkTokens['--color-bg-subtle'])).toBeLessThan(3.0);  // 1.42:1
    // Legacy Light --color-border-subtle: #e2e8f0
    expect(getContrast('#e2e8f0', lightTokens['--color-bg-surface'])).toBeLessThan(3.0); // 1.23:1
    expect(getContrast('#e2e8f0', lightTokens['--color-bg-subtle'])).toBeLessThan(3.0);  // 1.13:1
    // Legacy Light --color-text-muted: #64748b on subtle
    expect(getContrast('#64748b', lightTokens['--color-bg-subtle'])).toBeLessThan(4.5); // 4.34:1
  });

  // 10. [F2 Fail-Closed Multiset Inventory & Ratchet] var(--color-border-subtle) exact 140/21 and exact per-file literal multisets strictly bounded
  it('ACC-09 / F2 Fail-Closed Multiset Inventory & Ratchet: var(--color-border-subtle) exact 140/21 and exact per-file literal multisets strictly bounded', () => {
    const srcDir = path.resolve(__dirname, '../src');
    const allFiles = getAllSourceFiles(srcDir);

    let borderSubtleCount = 0;
    const borderSubtleFiles = new Set<string>();

    const legacyCounts: Record<string, number> = {
      '#64748b': 0,
      '#d97706': 0,
      '#e2e8f0': 0,
      '#dc2626': 0,
      '#30363d': 0,
    };
    const legacyFiles: Record<string, Set<string>> = {
      '#64748b': new Set(),
      '#d97706': new Set(),
      '#e2e8f0': new Set(),
      '#dc2626': new Set(),
      '#30363d': new Set(),
    };

    const borderSubtleRegex = /var\(--color-border-subtle/g;
    const hexRegex = /#(?:[0-9a-fA-F]{8}|[0-9a-fA-F]{6}|[0-9a-fA-F]{3,4})\b/g;
    const rgbRegex = /rgba?\s*\([^)]+\)/gi;
    const hslRegex = /hsla?\s*\([^)]+\)/gi;

    const observedFileMultisets: Record<string, Record<string, number>> = {};

    for (const f of allFiles) {
      const content = fs.readFileSync(f, 'utf-8');
      const relPath = path.relative(srcDir, f).replace(/\\/g, '/');
      const isIndexCss = f.endsWith('index.css');

      // 1) Border subtle token usage count
      const matches = content.match(borderSubtleRegex);
      if (matches) {
        borderSubtleCount += matches.length;
        borderSubtleFiles.add(f);
      }

      // 2) Scan all color literals into exact multiset per file (excluding index.css design token definitions)
      if (!isIndexCss) {
        const fileMultiset: Record<string, number> = {};
        const hMatches = content.match(hexRegex) || [];
        for (const m of hMatches) {
          const lit = m.toLowerCase();
          fileMultiset[lit] = (fileMultiset[lit] || 0) + 1;
        }
        const rMatches = content.match(rgbRegex) || [];
        for (const m of rMatches) {
          const lit = m.toLowerCase().replace(/\s+/g, '');
          fileMultiset[lit] = (fileMultiset[lit] || 0) + 1;
        }
        const sMatches = content.match(hslRegex) || [];
        for (const m of sMatches) {
          const lit = m.toLowerCase().replace(/\s+/g, '');
          fileMultiset[lit] = (fileMultiset[lit] || 0) + 1;
        }

        const totalLiterals = Object.values(fileMultiset).reduce((a, b) => a + b, 0);

        if (totalLiterals > 0) {
          observedFileMultisets[relPath] = fileMultiset;

          // Fail-closed check 1: File must be registered in COLOR_LITERAL_MULTISET_BASELINE
          const allowedMultiset = COLOR_LITERAL_MULTISET_BASELINE[relPath];
          expect(
            allowedMultiset,
            `New unregistered file containing color literals detected: "${relPath}". All files with color literals must be registered in COLOR_LITERAL_MULTISET_BASELINE.`
          ).toBeDefined();

          // Fail-closed check 2: Every literal in the file must exist in baseline and must not exceed its baseline count
          for (const [literal, count] of Object.entries(fileMultiset)) {
            const allowedCount = allowedMultiset[literal] || 0;
            expect(
              allowedCount,
              `Literal '${literal}' in "${relPath}" is not registered in baseline multiset (unregistered new color literal forbidden).`
            ).toBeGreaterThan(0);
            expect(
              count,
              `Literal '${literal}' count in "${relPath}" (${count}) exceeded baseline allowed count (${allowedCount}).`
            ).toBeLessThanOrEqual(allowedCount);
          }
        }

        // Count specific legacy tokens
        const lower = content.toLowerCase();
        for (const lit of Object.keys(legacyCounts)) {
          const occurrences = (lower.match(new RegExp(lit, 'g')) || []).length;
          if (occurrences > 0) {
            legacyCounts[lit] += occurrences;
            legacyFiles[lit].add(relPath);
          }
        }
      }
    }

    // Exact count verification for var(--color-border-subtle)
    expect(borderSubtleCount, 'var(--color-border-subtle) exact occurrence count in apps/web/src must be 140').toBe(140);
    expect(borderSubtleFiles.size, 'var(--color-border-subtle) file count in apps/web/src must be 21').toBe(21);

    // Fail-closed check 3: Total files with color literals must not exceed baseline file count
    const baselineFileCount = Object.keys(COLOR_LITERAL_MULTISET_BASELINE).length;
    expect(Object.keys(observedFileMultisets).length, 'Total files with color literals must not exceed baseline').toBeLessThanOrEqual(baselineFileCount);

    // Ratchet assertions for specific legacy literals (occurrences & files)
    expect(legacyCounts['#64748b'], 'Legacy #64748b literal count must not exceed 15').toBeLessThanOrEqual(15);
    expect(legacyFiles['#64748b'].size, 'Legacy #64748b file count must not exceed 6').toBeLessThanOrEqual(6);

    expect(legacyCounts['#d97706'], 'Legacy #d97706 literal count must not exceed 14').toBeLessThanOrEqual(14);
    expect(legacyFiles['#d97706'].size, 'Legacy #d97706 file count must not exceed 6').toBeLessThanOrEqual(6);

    expect(legacyCounts['#e2e8f0'], 'Legacy #e2e8f0 literal count must not exceed 3').toBeLessThanOrEqual(3);
    expect(legacyFiles['#e2e8f0'].size, 'Legacy #e2e8f0 file count must not exceed 2').toBeLessThanOrEqual(2);

    expect(legacyCounts['#dc2626'], 'Legacy #dc2626 literal count must not exceed 1').toBeLessThanOrEqual(1);
    expect(legacyFiles['#dc2626'].size, 'Legacy #dc2626 file count must not exceed 1').toBeLessThanOrEqual(1);

    expect(legacyCounts['#30363d'], 'Legacy #30363d literal count must not exceed 161').toBeLessThanOrEqual(161);
    expect(legacyFiles['#30363d'].size, 'Legacy #30363d file count must not exceed 15').toBeLessThanOrEqual(15);
  });
});
