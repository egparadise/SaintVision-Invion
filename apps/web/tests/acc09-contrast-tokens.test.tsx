// @vitest-environment happy-dom
import React, { act } from 'react';
import { createRoot } from 'react-dom/client';
import { describe, it, expect, vi, beforeAll, afterAll } from 'vitest';
import fs from 'node:fs';
import path from 'node:path';
import ts from 'typescript';
import { RunDetail } from '../src/features/runs/RunDetail';
import { SealRecordPanel } from '../src/features/runs/SealRecordPanel';
import { RunList } from '../src/features/runs/RunList';
import { NodeList } from '../src/features/nodes/NodeList';
import { NodeDetail } from '../src/features/nodes/NodeDetail';
import { DeveloperStudio } from '../src/features/studio/DeveloperStudio';
import { ResourceExplorer } from '../src/features/desktop/ResourceExplorer';
import { InvFileExplorer } from '../src/features/desktop/InvFileExplorer';
import { ModelLineageView } from '../src/features/mlops/ModelLineageView';
import { AdminSecurityConsole } from '../src/features/admin/AdminSecurityConsole';
import { IntranetDeploymentView } from '../src/features/deployment/IntranetDeploymentView';
import type {
  ReleaseManifestResponse,
  ReleaseManifestDetailResponse,
} from '../src/contracts/release-manifest-detail-response';
import * as client from '../src/shared/api/client';
import * as projectObservation from '../src/shared/api/projectObservation';
import { fabricObservation } from '../src/shared/api/fabricObservation';
import type { ProjectItem, NodeItem, RunItem } from '../src/contracts/types';

vi.mock('@/shared/api/client', async (importOriginal) => {
  const actual = await importOriginal<typeof import('../src/shared/api/client')>();
  return {
    ...actual,
    apiClient: vi.fn().mockImplementation(async (endpoint: string) => {
      if (typeof endpoint === 'string' && endpoint.includes('/execution-readiness')) {
        return {
          admissionRequired: true,
          blockedBy: [],
          checks: [],
          executable: true,
          nodeReadiness: 'unknown',
          projectId: 'prj_studio_test',
          scope: 'workspace-preconditions-not-execution-admission',
          summary: 'Ready for execution',
          workspaceId: 'wsp_studio_01',
        };
      }
      if (typeof endpoint === 'string' && endpoint.includes('/runs/')) {
        const m = endpoint.match(/\/runs\/([^/]+)/);
        const runId = m ? m[1] : 'run_studio_001';
        let state = 'running';
        if (runId.includes('succeeded')) state = 'succeeded';
        else if (runId.includes('failed')) state = 'failed';
        else if (runId.includes('approval')) state = 'awaiting_approval';
        return {
          id: runId,
          runId,
          projectId: 'prj_studio_test',
          status: state,
          state,
          nodeId: 'nod_studio_01',
          objective: 'PACS Inference Execution Test',
          output: { sha256: 'a'.repeat(64), sizeBytes: 1024 },
          evidence: { evidenceId: 'ev_001' },
          stopReceipt: { exitCode: 0, physicallyStopped: true, resourceReclaimed: true, verified: true },
          completedAt: state === 'succeeded' ? '2026-09-22T10:10:00Z' : undefined,
        };
      }
      return { items: [], nextCursor: null };
    }),
  };
});

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

function helperExtractVar(val: string): string {
  const m = val.match(/var\((--[a-z0-9-]+)\)/);
  if (!m) throw new Error(`Expected CSS variable in value: "${val}"`);
  return m[1];
}

function parseRgba(str: string): { rgb: [number, number, number]; a: number } | null {
  const m = str.trim().match(/^rgba\(\s*(\d+)\s*,\s*(\d+)\s*,\s*(\d+)\s*,\s*([\d.]+)\s*\)$/i);
  if (!m) return null;
  return {
    rgb: [parseInt(m[1], 10), parseInt(m[2], 10), parseInt(m[3], 10)],
    a: parseFloat(m[4]),
  };
}

function resolveDomColor(domValue: string, underlayHex: string, tokens: Record<string, string>): string {
  const trimmed = domValue.trim();
  if (trimmed.startsWith('var(')) {
    const varName = helperExtractVar(trimmed);
    const hex = tokens[varName];
    if (!hex) throw new Error(`Token ${varName} not found in theme tokens`);
    return hex;
  }
  const rgba = parseRgba(trimmed);
  if (rgba) {
    return blendRgba(rgba.rgb, rgba.a, underlayHex);
  }
  const rgbMatch = trimmed.match(/^rgb\(\s*(\d+)\s*,\s*(\d+)\s*,\s*(\d+)\s*\)$/i);
  if (rgbMatch) {
    const r = parseInt(rgbMatch[1], 10);
    const g = parseInt(rgbMatch[2], 10);
    const b = parseInt(rgbMatch[3], 10);
    const toHex = (n: number) => n.toString(16).padStart(2, '0');
    return `#${toHex(r)}${toHex(g)}${toHex(b)}`;
  }
  if (trimmed.startsWith('#')) {
    return trimmed;
  }
  throw new Error(`Unsupported DOM color format: "${domValue}"`);
}

function extractTokens(block: string): Record<string, string> {
  const cleanBlock = block.replace(/\/\*[\s\S]*?\*\//g, '');
  const tokens: Record<string, string> = {};
  const occurrences: Record<string, number> = {};
  const regex = /(--color-[a-z0-9-]+)\s*:\s*([^;]+);/g;
  let match;
  while ((match = regex.exec(cleanBlock)) !== null) {
    const name = match[1].trim();
    const val = match[2].trim();
    occurrences[name] = (occurrences[name] || 0) + 1;
    if (val.startsWith('#') || val.startsWith('rgba(')) {
      tokens[name] = val;
    }
  }
  for (const [name, count] of Object.entries(occurrences)) {
    if (count > 1) {
      throw new Error(`Duplicate CSS variable declaration detected: ${name} is declared ${count} times in the same CSS block`);
    }
  }
  return tokens;
}

function resolveTokenHex(tokenName: string, tokens: Record<string, string>): string {
  const val = tokens[tokenName];
  if (!val) throw new Error(`Token ${tokenName} not found in theme tokens`);
  if (val.startsWith('#')) return val;
  if (val.startsWith('rgba(')) {
    const parsed = parseRgba(val);
    if (!parsed) throw new Error(`Failed to parse rgba token: ${val}`);
    const canvas = tokens['--color-bg-canvas'];
    return blendRgba(parsed.rgb, parsed.a, canvas);
  }
  throw new Error(`Unsupported token format: ${val}`);
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

// Comment-trivia stripping for TS/TSX/JS/JSX sources (ACC-09 ratchet must not count PR/issue
// references such as `#281` in comments as CSS hex colours). The TypeScript parser is used instead of
// a comment regex so that string literals, template literals, regex literals, JSX attribute values and
// JSX text keep their exact contents: only the source text of leaf tokens [getStart, end) is kept, and
// everything between tokens (whitespace, `//`, `/* */` and JSDoc comment trivia) is blanked to spaces
// with line breaks preserved. JSDoc subtrees are skipped so JSDoc text is never treated as code.
function stripCommentTrivia(content: string, fileName: string): string {
  const ext = path.extname(fileName).toLowerCase();
  const scriptKind =
    ext === '.tsx' ? ts.ScriptKind.TSX
      : ext === '.jsx' ? ts.ScriptKind.JSX
        : ext === '.js' ? ts.ScriptKind.JS
          : ext === '.ts' ? ts.ScriptKind.TS
            : undefined;
  if (scriptKind === undefined) {
    return content;
  }
  const sf = ts.createSourceFile(fileName, content, ts.ScriptTarget.Latest, true, scriptKind);
  const out = Array.from(content, (c) => (c === '\n' || c === '\r' ? c : ' '));
  const visit = (node: ts.Node) => {
    if (node.kind >= ts.SyntaxKind.FirstJSDocNode && node.kind <= ts.SyntaxKind.LastJSDocNode) {
      return;
    }
    const children = node.getChildren(sf);
    if (children.length === 0) {
      for (let i = node.getStart(sf); i < node.end; i++) {
        out[i] = content[i];
      }
      return;
    }
    children.forEach(visit);
  };
  visit(sf);
  return out.join('');
}

const HEX_COLOR_REGEX = /#(?:[0-9a-fA-F]{8}|[0-9a-fA-F]{6}|[0-9a-fA-F]{3,4})\b/g;
const RGB_COLOR_REGEX = /rgba?\s*\([^)]+\)/gi;
const HSL_COLOR_REGEX = /hsla?\s*\([^)]+\)/gi;

// Exact multiset of hex/rgb(a)/hsl(a) literals in already comment-stripped text
function scanColorLiterals(text: string): Record<string, number> {
  const multiset: Record<string, number> = {};
  for (const m of text.match(HEX_COLOR_REGEX) || []) {
    const lit = m.toLowerCase();
    multiset[lit] = (multiset[lit] || 0) + 1;
  }
  for (const re of [RGB_COLOR_REGEX, HSL_COLOR_REGEX]) {
    for (const m of text.match(re) || []) {
      const lit = m.toLowerCase().replace(/\s+/g, '');
      multiset[lit] = (multiset[lit] || 0) + 1;
    }
  }
  return multiset;
}

// Fail-closed multiset inventory of registered files and their exact color literal counts (literal -> max allowed occurrences)
const COLOR_LITERAL_MULTISET_BASELINE: Record<string, Record<string, number>> = {
  "app/App.tsx": {"#991b1b": 2, "#dc2626": 1, "#ef4444": 1, "#f87171": 1, "#fca5a5": 1, "#fed7aa": 1, "#fee2e2": 1, "#ffffff": 2, "rgba(239,68,68,0.1)": 1},
  "features/admin/AdminSecurityConsole.tsx": {},
  "features/agent/NaturalLanguageRunView.tsx": {"#0d1117": 6, "#161b22": 7, "#30363d": 12, "#3fb950": 7, "#58a6ff": 8, "#8b949e": 16, "#93c5fd": 1, "#94a3b8": 1, "#c9d1d9": 2, "#cbd5e1": 1, "#f0f6fc": 3, "#f85149": 7, "#ff7b72": 1, "rgba(248,81,73,0.15)": 2, "rgba(46,160,67,0.15)": 1, "rgba(46,160,67,0.2)": 1, "rgba(56,139,253,0.15)": 2, "rgba(56,139,253,0.2)": 1},
  "features/approvals/ApprovalCenter.tsx": {"#1e293b": 1, "#334155": 1, "#3b82f6": 1, "#93c5fd": 1, "#ef4444": 2, "#f8fafc": 1, "#fca5a5": 2, "#fed7aa": 1, "#fff": 1, "rgba(16,185,129,0.15)": 1, "rgba(234,179,8,0.15)": 1, "rgba(239,68,68,0.15)": 2, "rgba(59,130,246,0.1)": 1, "rgba(59,130,246,0.25)": 1},
  "features/approvals/ApprovalDetail.tsx": {"#0d1117": 1, "#30363d": 1, "#58a6ff": 1, "#c9d1d9": 1, "rgba(0,0,0,0.5)": 1, "rgba(220,38,38,0.1)": 1, "rgba(56,139,253,0.15)": 1},
  "features/dashboard/ClusterOverview.tsx": {"#10b981": 1, "#38bdf8": 1, "#64748b": 2, "#8b5cf6": 1, "#d29922": 1, "#ef4444": 4, "#f59e0b": 1, "#fca5a5": 3, "#fff": 1, "rgba(239,68,68,0.1)": 2},
  "features/deployment/IntranetDeploymentView.tsx": {},
  "features/desktop/DesktopShell.tsx": {"#030712": 1, "#090d16": 1, "#0f172a": 1, "#1e3a8a": 1, "#34d399": 2, "#38bdf8": 3, "#60a5fa": 2, "#94a3b8": 5, "#ef4444": 1, "#f8fafc": 5, "#ffffff": 1, "rgba(0,0,0,0.3)": 1, "rgba(0,0,0,0.5)": 1, "rgba(0,0,0,0.6)": 2, "rgba(0,0,0,0.8)": 1, "rgba(15,23,42,0.75)": 1, "rgba(15,23,42,0.85)": 1, "rgba(15,23,42,0.95)": 2, "rgba(255,255,255,0.05)": 1, "rgba(255,255,255,0.08)": 2, "rgba(255,255,255,0.1)": 5, "rgba(255,255,255,0.15)": 4, "rgba(255,255,255,0.5)": 1, "rgba(59,130,246,0.2)": 1, "rgba(59,130,246,0.3)": 1, "rgba(59,130,246,0.4)": 1, "rgba(59,130,246,0.5)": 1},
  "features/desktop/DesktopWindow.tsx": {"#0f172a": 1, "#10b981": 1, "#1e293b": 1, "#333": 1, "#334155": 1, "#64748b": 1, "#94a3b8": 1, "#ef4444": 1, "#f59e0b": 1, "#f8fafc": 1, "rgba(0,0,0,0.25)": 1, "rgba(0,0,0,0.3)": 4, "rgba(0,0,0,0.45)": 1, "rgba(0,0,0,0.5)": 1},
  "features/desktop/InvFileExplorer.tsx": {},
  "features/desktop/ModelStudioView.tsx": {"#0f172a": 4, "#10b981": 3, "#1e293b": 5, "#334155": 7, "#38bdf8": 1, "#3b82f6": 1, "#475569": 5, "#64748b": 1, "#6ee7b7": 3, "#93c5fd": 1, "#94a3b8": 9, "#cbd5e1": 4, "#d97706": 1, "#ef4444": 2, "#f59e0b": 4, "#f87171": 2, "#f8fafc": 4, "#fca5a5": 5, "#fde68a": 3, "#fff": 2, "rgba(16,185,129,0.15)": 1, "rgba(16,185,129,0.2)": 2, "rgba(239,68,68,0.15)": 2, "rgba(239,68,68,0.2)": 3, "rgba(245,158,11,0.15)": 2, "rgba(245,158,11,0.2)": 1},
  "features/desktop/ResourceExplorer.tsx": {},
  "features/desktop/TerminalSessionView.tsx": {"#0f172a": 6, "#1e293b": 2, "#334155": 6, "#38bdf8": 1, "#3b82f6": 1, "#475569": 1, "#4ade80": 1, "#60a5fa": 1, "#7f1d1d": 1, "#94a3b8": 4, "#ef4444": 1, "#f8fafc": 5, "#fbbf24": 1, "#fecaca": 2, "#fed7aa": 1, "rgba(0,0,0,0.2)": 1, "rgba(59,130,246,0.15)": 1, "rgba(59,130,246,0.3)": 1},
  "features/editor/ConflictResolutionModal.tsx": {"#0d1117": 1, "#161b22": 1, "#30363d": 2, "#58a6ff": 1, "#8b949e": 2, "#f85149": 5, "#fff": 1, "rgba(0,0,0,0.5)": 1, "rgba(0,0,0,0.75)": 1, "rgba(248,81,73,0.1)": 1},
  "features/editor/DiffViewer.tsx": {"#0d1117": 1, "#161b22": 1, "#30363d": 2, "#3fb950": 3, "#484f58": 2, "#8b949e": 1, "#c9d1d9": 2, "#f0f6fc": 1, "#f85149": 3, "rgba(248,81,73,0.15)": 1, "rgba(46,160,67,0.15)": 1},
  "features/editor/GitCommitModal.tsx": {"#0d1117": 3, "#161b22": 1, "#30363d": 6, "#58a6ff": 1, "#8b949e": 5, "#c9d1d9": 3, "#e3b341": 2, "#f0f6fc": 1, "#f85149": 1, "rgba(0,0,0,0.5)": 1, "rgba(0,0,0,0.75)": 1, "rgba(56,139,253,0.1)": 1},
  "features/editor/MonacoWorkspaceEditor.tsx": {"#070a0e": 1, "#090d13": 3, "#0d1117": 4, "#161b22": 4, "#1f242c": 1, "#21262d": 6, "#2ea043": 1, "#30363d": 7, "#3fb950": 4, "#484f58": 2, "#58a6ff": 9, "#79c0ff": 1, "#8b949e": 9, "#c9d1d9": 6, "#e3b341": 6, "#f0f6fc": 5, "#f85149": 3, "rgba(210,153,34,0.2)": 1, "rgba(227,179,65,0.15)": 2, "rgba(227,179,65,0.3)": 1, "rgba(248,81,73,0.15)": 1, "rgba(248,81,73,0.2)": 1, "rgba(46,160,67,0.12)": 1, "rgba(46,160,67,0.15)": 1, "rgba(46,160,67,0.2)": 1, "rgba(56,139,253,0.1)": 1, "rgba(56,139,253,0.12)": 2, "rgba(56,139,253,0.2)": 1, "rgba(56,139,253,0.3)": 1},
  "features/evidence/EvidenceViewer.tsx": {"#10b981": 1, "#d97706": 3, "#f87171": 1, "rgba(16,185,129,0.15)": 1, "rgba(234,179,8,0.08)": 1, "rgba(234,179,8,0.15)": 1, "rgba(234,179,8,0.3)": 1, "rgba(248,81,73,0.08)": 1, "rgba(248,81,73,0.1)": 2, "rgba(248,81,73,0.15)": 2, "rgba(248,81,73,0.3)": 1, "rgba(56,139,253,0.15)": 1},
  "features/mlops/ModelLineageView.tsx": {},
  "features/nodes/NodeDetail.tsx": {"rgba(210,153,34,0.12)": 1, "rgba(210,153,34,0.15)": 1, "rgba(248,81,73,0.1)": 1},
  "features/nodes/NodeList.tsx": {"#1e1e1e": 1, "#2d3748": 1, "#4ade80": 2, "#fff": 1, "#ffffff": 1, "rgba(210,153,34,0.15)": 1, "rgba(56,189,248,0.12)": 1, "rgba(56,189,248,0.3)": 1},
  "features/placement/PlacementExplainView.tsx": {"#d97706": 1, "rgba(16,185,129,0.1)": 1, "rgba(16,185,129,0.15)": 1, "rgba(234,179,8,0.15)": 1, "rgba(234,179,8,0.3)": 1},
  "features/placement/PlacementSimulator.tsx": {"#334155": 3, "#93c5fd": 1, "#94a3b8": 2, "#ef4444": 4, "#f87171": 1, "#fbbf24": 4, "#fca5a5": 4, "#fff": 3, "#ffffff": 2, "rgba(234,179,8,0.15)": 2, "rgba(234,179,8,0.3)": 2, "rgba(239,68,68,0.1)": 4, "rgba(35,134,54,0.1)": 1},
  "features/placement/ResourceTopologyGraph.tsx": {"#ffffff": 2, "rgba(16,185,129,0.08)": 1},
  "features/recovery/DistributedRecoveryView.tsx": {"#0d1117": 3, "#161b22": 9, "#21262d": 1, "#30363d": 12, "#3fb950": 6, "#58a6ff": 8, "#8b949e": 20, "#a371f7": 1, "#e3b341": 1, "#f0f6fc": 8, "#f85149": 7, "rgba(248,81,73,0.15)": 1, "rgba(46,160,67,0.15)": 1, "rgba(56,139,253,0.1)": 1, "rgba(56,139,253,0.15)": 1, "rgba(56,139,253,0.4)": 1},
  "features/release/ReleaseCandidateView.tsx": {"#0d1117": 1, "#161b22": 7, "#21262d": 2, "#30363d": 11, "#3fb950": 10, "#58a6ff": 5, "#8b949e": 22, "#c9d1d9": 2, "#d29922": 2, "#f0f6fc": 7, "#f85149": 5, "rgba(139,148,158,0.1)": 1, "rgba(139,148,158,0.2)": 1, "rgba(248,81,73,0.15)": 1, "rgba(248,81,73,0.2)": 2, "rgba(46,160,67,0.15)": 1, "rgba(46,160,67,0.2)": 2, "rgba(56,139,253,0.12)": 1, "rgba(56,139,253,0.2)": 1},
  "features/release/releaseEngine.ts": {"#0d1117": 1, "#6e7681": 1},
  "features/runs/RunDetail.tsx": {},
  "features/runs/RunList.tsx": {},
  "features/runs/SealRecordPanel.tsx": {},
  "features/studio/DeveloperStudio.tsx": {},
  "features/terminal/WebTerminal.tsx": {"#090d16": 1, "#0d1117": 1, "#161b22": 1, "#1c1917": 1, "#238636": 1, "#30363d": 2, "#451a03": 1, "#58a6ff": 1, "#6b7280": 1, "#7f1d1d": 1, "#8b949e": 5, "#c9d1d9": 2, "#d29922": 1, "#d97706": 1, "#ea580c": 1, "#ef4444": 2, "#f0f6fc": 2, "#f85149": 1, "#fb923c": 1, "#fde68a": 2, "#fecaca": 1, "#fed7aa": 1, "#fff": 1},
  "features/workspaces/ExecutionResultView.tsx": {"rgba(16,185,129,0.15)": 1},
  "features/workspaces/WorkspaceCreateModal.tsx": {"rgba(0,0,0,0.65)": 1},
  "features/workspaces/WorkspaceList.tsx": {"#34d399": 1, "#f59e0b": 1, "#f87171": 1, "rgba(16,185,129,0.15)": 1, "rgba(16,185,129,0.3)": 1, "rgba(239,68,68,0.15)": 1, "rgba(239,68,68,0.3)": 1, "rgba(245,158,11,0.15)": 1, "rgba(245,158,11,0.3)": 1},
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

  let originalGlobalFetch: typeof globalThis.fetch;
  let originalWindowFetch: any;
  beforeAll(() => {
    originalGlobalFetch = globalThis.fetch;
    originalWindowFetch = typeof window !== 'undefined' ? (window as any).fetch : undefined;
    const mocked = vi.fn().mockImplementation(() =>
      Promise.resolve(new Response(JSON.stringify({}), { status: 200, headers: { 'Content-Type': 'application/json' } }))
    );
    globalThis.fetch = mocked;
    if (typeof window !== 'undefined') {
      (window as any).fetch = mocked;
    }
  });
  afterAll(() => {
    globalThis.fetch = originalGlobalFetch;
    if (typeof window !== 'undefined' && originalWindowFetch) {
      (window as any).fetch = originalWindowFetch;
    }
  });

  // Codex F2: Status tokens must be declared exactly once per theme block without comment decoys
  it('ACC-09 / Codex F2: Status tokens are declared exactly once per theme block without comment decoys', () => {
    const statusTokens = ['--color-status-active', '--color-status-lost', '--color-status-unknown'];

    // Check root (light)
    const lightClean = lightBlockMatch[1].replace(/\/\*[\s\S]*?\*\//g, '');
    for (const token of statusTokens) {
      const regex = new RegExp(`(?<![\\w-])${token}\\s*:`, 'g');
      const matches = lightClean.match(regex);
      expect(matches, `Light theme block must declare ${token} exactly once`).toHaveLength(1);
      expect(lightTokens[token], `Light theme ${token} value must be parsed`).toBeDefined();
    }

    // Check dark
    const darkClean = darkBlockMatch[1].replace(/\/\*[\s\S]*?\*\//g, '');
    for (const token of statusTokens) {
      const regex = new RegExp(`(?<![\\w-])${token}\\s*:`, 'g');
      const matches = darkClean.match(regex);
      expect(matches, `Dark theme block must declare ${token} exactly once`).toHaveLength(1);
      expect(darkTokens[token], `Dark theme ${token} value must be parsed`).toBeDefined();
    }
  });

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
  it('ACC-09 / Card 186: NodeList Status Badges bind to design tokens and maintain non-color semantic distinction across standard and telemetry branches', async () => {
    const container = document.createElement('div');
    container.setAttribute('data-theme', 'light');
    document.body.appendChild(container);
    const root = createRoot(container);

    const testNodes = [
      // Standard Cards (telemetryUnavailable: false / undefined)
      {
        id: 'nod_std_active',
        hostname: 'node-std-active',
        status: 'active',
        os: 'linux',
        cpuCores: 16,
        cpuUsagePercent: 25,
        memoryTotalBytes: 64 * 1024 ** 3,
        memoryUsedBytes: 16 * 1024 ** 3,
        storageTotalBytes: 1000 * 1024 ** 3,
        storageUsedBytes: 200 * 1024 ** 3,
        allocatableCores: 12,
        gpuCount: 0,
        heartbeatAt: '2026-10-01T10:00:00Z',
      },
      {
        id: 'nod_std_lost',
        hostname: 'node-std-lost',
        status: 'lost',
        os: 'linux',
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
        id: 'nod_std_unknown',
        hostname: 'node-std-unknown',
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
      // Telemetry Unavailable Cards (telemetryUnavailable: true)
      {
        id: 'nod_telem_active',
        hostname: 'node-telem-active',
        status: 'active',
        telemetryUnavailable: true,
        os: 'linux',
        cpuCores: 16,
        cpuUsagePercent: 0,
        memoryTotalBytes: 64 * 1024 ** 3,
        memoryUsedBytes: 0,
        storageTotalBytes: 1000 * 1024 ** 3,
        storageUsedBytes: 0,
        gpuCount: 0,
        heartbeatAt: '2026-10-01T10:00:00Z',
      },
      {
        id: 'nod_telem_lost',
        hostname: 'node-telem-lost',
        status: 'lost',
        telemetryUnavailable: true,
        os: 'linux',
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
        id: 'nod_telem_unknown',
        hostname: 'node-telem-unknown',
        status: 'unknown',
        telemetryUnavailable: true,
        os: 'linux',
        cpuCores: 4,
        cpuUsagePercent: 0,
        memoryTotalBytes: 16 * 1024 ** 3,
        memoryUsedBytes: 0,
        storageTotalBytes: 250 * 1024 ** 3,
        storageUsedBytes: 0,
        gpuCount: 0,
        heartbeatAt: '2026-10-01T10:00:00Z',
      },
    ];

    try {
      await act(async () => {
        root.render(<NodeList nodes={testNodes as any} onSelectNode={() => {}} />);
      });

      // Assert each of the 6 badges across both standard and telemetry branches
      const badgeConfigs = [
        { id: 'nod_std_active', expectedStatus: 'active', expectedToken: '--color-status-active', expectedLabel: 'ACTIVE' },
        { id: 'nod_std_lost', expectedStatus: 'lost', expectedToken: '--color-status-lost', expectedLabel: 'LOST' },
        { id: 'nod_std_unknown', expectedStatus: 'unknown', expectedToken: '--color-status-unknown', expectedLabel: 'UNKNOWN' },
        { id: 'nod_telem_active', expectedStatus: 'active', expectedToken: '--color-status-active', expectedLabel: 'ACTIVE' },
        { id: 'nod_telem_lost', expectedStatus: 'lost', expectedToken: '--color-status-lost', expectedLabel: 'LOST' },
        { id: 'nod_telem_unknown', expectedStatus: 'unknown', expectedToken: '--color-status-unknown', expectedLabel: 'UNKNOWN' },
      ];

      for (const cfg of badgeConfigs) {
        const badge = container.querySelector(`[data-testid="node-status-badge-${cfg.id}"]`) as HTMLElement;
        expect(badge, `Badge for ${cfg.id} must render`).not.toBeNull();
        expect(badge.style.color, `${cfg.id} text color must bind to ${cfg.expectedToken}`).toBe(`var(${cfg.expectedToken})`);
        expect(badge.style.borderColor, `${cfg.id} border must bind to ${cfg.expectedToken}`).toBe(`var(${cfg.expectedToken})`);
        expect(badge.style.backgroundColor, `${cfg.id} background must be var(--color-bg-subtle)`).toBe('var(--color-bg-subtle)');

        const dot = badge.querySelector('span') as HTMLElement;
        expect(dot.style.backgroundColor, `${cfg.id} dot must bind to ${cfg.expectedToken}`).toBe(`var(${cfg.expectedToken})`);
        expect(badge.textContent).toContain(cfg.expectedLabel);

        // Codex F1: Dynamically extract fg and bg tokens directly from the rendered DOM element and calculate contrast!
        const fgVar = helperExtractVar(badge.style.color);
        const bgVar = helperExtractVar(badge.style.backgroundColor);

        // Light theme contrast
        const crLight = getContrast(lightTokens[fgVar], lightTokens[bgVar]);
        expect(crLight, `Light theme contrast for ${cfg.id} (${fgVar} on ${bgVar}) must be >= 4.5:1`).toBeGreaterThanOrEqual(4.5);

        // Dark theme contrast
        const crDark = getContrast(darkTokens[fgVar], darkTokens[bgVar]);
        expect(crDark, `Dark theme contrast for ${cfg.id} (${fgVar} on ${bgVar}) must be >= 4.5:1`).toBeGreaterThanOrEqual(4.5);
      }

      // Semantic distinctions & banner bindings in Standard Cards
      // 1) Standard Active: notice banner
      const stdActiveNotice = container.querySelector('[data-testid="node-active-status-notice-nod_std_active"]') as HTMLElement;
      expect(stdActiveNotice, 'Standard active notice banner must render').not.toBeNull();
      expect(stdActiveNotice.style.color, 'Standard active notice color must bind to var(--color-status-active)').toBe('var(--color-status-active)');
      expect(stdActiveNotice.textContent).toContain('ℹ️');
      // Banner alpha contrast
      const activeBannerLightBg = blendRgba([56, 189, 248], 0.12, lightTokens['--color-bg-surface']);
      expect(getContrast(lightTokens['--color-status-active'], activeBannerLightBg), 'Active banner light alpha contrast >= 4.5:1').toBeGreaterThanOrEqual(4.5);
      const activeBannerDarkBg = blendRgba([56, 189, 248], 0.12, darkTokens['--color-bg-surface']);
      expect(getContrast(darkTokens['--color-status-active'], activeBannerDarkBg), 'Active banner dark alpha contrast >= 4.5:1').toBeGreaterThanOrEqual(4.5);

      // 2) Standard Unknown (observationOnly): observation banner and schedulable capacity label
      const stdUnknownCard = container.querySelector('[data-testid="node-card-nod_std_unknown"]') as HTMLElement;
      expect(stdUnknownCard?.getAttribute('role'), 'Standard unknown card must have status role').toBe('status');

      const obsBanner = container.querySelector('[data-testid="node-observation-banner-nod_std_unknown"]') as HTMLElement;
      expect(obsBanner, 'Observation-only banner must render').not.toBeNull();
      expect(obsBanner.style.color, 'Observation banner color must bind to var(--color-status-unknown)').toBe('var(--color-status-unknown)');
      expect(obsBanner.style.borderColor, 'Observation banner border must bind to var(--color-status-unknown)').toBe('var(--color-status-unknown)');
      expect(obsBanner.textContent).toContain('⚠️');
      expect(obsBanner.textContent).toContain('관측 전용');
      // Observation banner alpha contrast
      const obsBannerLightBg = blendRgba([210, 153, 34], 0.15, lightTokens['--color-bg-surface']);
      expect(getContrast(lightTokens['--color-status-unknown'], obsBannerLightBg), 'Observation banner light alpha contrast >= 4.5:1').toBeGreaterThanOrEqual(4.5);
      const obsBannerDarkBg = blendRgba([210, 153, 34], 0.15, darkTokens['--color-bg-surface']);
      expect(getContrast(darkTokens['--color-status-unknown'], obsBannerDarkBg), 'Observation banner dark alpha contrast >= 4.5:1').toBeGreaterThanOrEqual(4.5);

      // Schedulable capacity label (:415)
      const schedLabel = container.querySelector('[data-testid="node-schedulable-nod_std_unknown"]') as HTMLElement;
      expect(schedLabel, 'Schedulable capacity label must render').not.toBeNull();
      expect(schedLabel.style.color, 'Schedulable label color must bind to var(--color-status-unknown)').toBe('var(--color-status-unknown)');
      expect(schedLabel.textContent).toContain('0C (차단)');

      // Card 189: Schedulable capacity label when allocatable binds to var(--color-status-online) with dynamic contrast
      const stdCard = container.querySelector('[data-testid="node-card-nod_std_active"]') as HTMLElement;
      expect(stdCard.style.backgroundColor, 'Standard active card background must be var(--color-bg-surface)').toBe('var(--color-bg-surface)');
      const stdCardBg = helperExtractVar(stdCard.style.backgroundColor);

      const schedAllocatable = container.querySelector('[data-testid="node-schedulable-nod_std_active"]') as HTMLElement;
      expect(schedAllocatable, 'Schedulable allocatable label must render').not.toBeNull();
      expect(schedAllocatable.style.color, 'Schedulable allocatable label color must bind to var(--color-status-online)').toBe('var(--color-status-online)');
      expect(schedAllocatable.textContent).toContain('12C');
      const schedAllocVar = helperExtractVar(schedAllocatable.style.color);
      expect(getContrast(lightTokens[schedAllocVar], lightTokens[stdCardBg]), 'Schedulable allocatable label light contrast >= 4.5:1').toBeGreaterThanOrEqual(4.5);
      expect(getContrast(darkTokens[schedAllocVar], darkTokens[stdCardBg]), 'Schedulable allocatable label dark contrast >= 4.5:1').toBeGreaterThanOrEqual(4.5);

      // Semantic distinctions in Telemetry Cards
      // 3) Telemetry Lost: role="alert", 🔴, border and notice text bind to var(--color-status-lost)
      const telemLostCard = container.querySelector('[data-testid="node-card-nod_telem_lost"]') as HTMLElement;
      expect(telemLostCard?.getAttribute('role'), 'Telemetry lost card must have alert role').toBe('alert');
      expect(telemLostCard.textContent).toContain('🔴');
      expect(telemLostCard.style.backgroundColor, 'Telemetry lost card background must be var(--color-bg-surface)').toBe('var(--color-bg-surface)');
      expect(telemLostCard.style.borderColor, 'Telemetry lost card border must bind to var(--color-status-lost)').toBe('var(--color-status-lost)');
      const telemLostBgVar = helperExtractVar(telemLostCard.style.backgroundColor);
      const telemLostBorderVar = helperExtractVar(telemLostCard.style.borderColor);
      expect(getContrast(lightTokens[telemLostBorderVar], lightTokens[telemLostBgVar]), 'Telemetry lost card border light contrast >= 3.0:1').toBeGreaterThanOrEqual(3.0);
      expect(getContrast(darkTokens[telemLostBorderVar], darkTokens[telemLostBgVar]), 'Telemetry lost card border dark contrast >= 3.0:1').toBeGreaterThanOrEqual(3.0);

      const telemLostNotice = container.querySelector('[data-testid="node-telemetry-notice-nod_telem_lost"]') as HTMLElement;
      expect(telemLostNotice, 'Telemetry lost notice must render').not.toBeNull();
      expect(telemLostNotice.style.color, 'Telemetry lost notice color must bind to var(--color-status-lost)').toBe('var(--color-status-lost)');
      const telemLostNoticeVar = helperExtractVar(telemLostNotice.style.color);
      expect(getContrast(lightTokens[telemLostNoticeVar], lightTokens[telemLostBgVar]), 'Telemetry lost notice light contrast >= 4.5:1').toBeGreaterThanOrEqual(4.5);
      expect(getContrast(darkTokens[telemLostNoticeVar], darkTokens[telemLostBgVar]), 'Telemetry lost notice dark contrast >= 4.5:1').toBeGreaterThanOrEqual(4.5);

      // 4) Telemetry Unknown: role="status", ⚠️, border and notice text bind to var(--color-status-unknown) (Codex F3)
      const telemUnknownCard = container.querySelector('[data-testid="node-card-nod_telem_unknown"]') as HTMLElement;
      expect(telemUnknownCard?.getAttribute('role'), 'Telemetry unknown card must have status role').toBe('status');
      expect(telemUnknownCard.textContent).toContain('⚠️');
      expect(telemUnknownCard.style.backgroundColor, 'Telemetry unknown card background must be var(--color-bg-surface)').toBe('var(--color-bg-surface)');
      expect(telemUnknownCard.style.borderColor, 'Telemetry unknown card border must bind to var(--color-status-unknown)').toBe('var(--color-status-unknown)');
      const telemUnknownBgVar = helperExtractVar(telemUnknownCard.style.backgroundColor);
      const telemUnknownBorderVar = helperExtractVar(telemUnknownCard.style.borderColor);
      expect(getContrast(lightTokens[telemUnknownBorderVar], lightTokens[telemUnknownBgVar]), 'Telemetry unknown card border light contrast >= 3.0:1').toBeGreaterThanOrEqual(3.0);
      expect(getContrast(darkTokens[telemUnknownBorderVar], darkTokens[telemUnknownBgVar]), 'Telemetry unknown card border dark contrast >= 3.0:1').toBeGreaterThanOrEqual(3.0);

      const telemUnknownNotice = container.querySelector('[data-testid="node-telemetry-notice-nod_telem_unknown"]') as HTMLElement;
      expect(telemUnknownNotice, 'Telemetry unknown notice must render').not.toBeNull();
      expect(telemUnknownNotice.style.color, 'Telemetry unknown notice color must bind to var(--color-status-unknown)').toBe('var(--color-status-unknown)');
      const telemUnknownNoticeVar = helperExtractVar(telemUnknownNotice.style.color);
      expect(getContrast(lightTokens[telemUnknownNoticeVar], lightTokens[telemUnknownBgVar]), 'Telemetry unknown notice light contrast >= 4.5:1').toBeGreaterThanOrEqual(4.5);
      expect(getContrast(darkTokens[telemUnknownNoticeVar], darkTokens[telemUnknownBgVar]), 'Telemetry unknown notice dark contrast >= 4.5:1').toBeGreaterThanOrEqual(4.5);

      // 5) Telemetry Active: role="status", ℹ️, notice text binds to var(--color-status-active)
      const telemActiveCard = container.querySelector('[data-testid="node-card-nod_telem_active"]') as HTMLElement;
      expect(telemActiveCard?.getAttribute('role'), 'Telemetry active card must have status role').toBe('status');
      expect(telemActiveCard.textContent).toContain('ℹ️');
      expect(telemActiveCard.style.backgroundColor, 'Telemetry active card background must be var(--color-bg-surface)').toBe('var(--color-bg-surface)');
      const telemActiveBgVar = helperExtractVar(telemActiveCard.style.backgroundColor);

      const telemActiveNotice = container.querySelector('[data-testid="node-active-status-notice-nod_telem_active"]') as HTMLElement;
      expect(telemActiveNotice, 'Telemetry active notice must render').not.toBeNull();
      expect(telemActiveNotice.style.color, 'Telemetry active notice color must bind to var(--color-status-active)').toBe('var(--color-status-active)');
      const telemActiveNoticeVar = helperExtractVar(telemActiveNotice.style.color);
      expect(getContrast(lightTokens[telemActiveNoticeVar], lightTokens[telemActiveBgVar]), 'Telemetry active notice light contrast >= 4.5:1').toBeGreaterThanOrEqual(4.5);
      expect(getContrast(darkTokens[telemActiveNoticeVar], darkTokens[telemActiveBgVar]), 'Telemetry active notice dark contrast >= 4.5:1').toBeGreaterThanOrEqual(4.5);
    } finally {
      act(() => {
        root.unmount();
      });
      container.remove();
    }
  });

  // 9. [Card 189 / ACC-09] Component DOM Rendering & Binding Verification: NodeDetail Callouts, Alert & Timeline Status
  it('ACC-09 / Card 189: NodeDetail component DOM rendering binds observation callout, error alert, and schedulable cards to design tokens with dynamic contrast verification', async () => {
    const container = document.createElement('div');
    container.setAttribute('data-theme', 'light');
    document.body.appendChild(container);
    const root = createRoot(container);

    const obsNode = {
      id: 'node_obs_detail',
      hostname: 'node-obs-detail',
      status: 'active',
      os: 'linux',
      observationOnly: true,
      cpuCores: 8,
      cpuUsagePercent: 20,
      memoryTotalBytes: 32 * 1024 ** 3,
      memoryUsedBytes: 8 * 1024 ** 3,
      storageTotalBytes: 500 * 1024 ** 3,
      storageUsedBytes: 50 * 1024 ** 3,
      allocatableCores: 0,
      allocatableMemoryBytes: 0,
      heartbeatAt: '2026-10-01T12:00:00Z',
    };

    try {
      // 1) Render observation-only active NodeDetail
      await act(async () => {
        root.render(<NodeDetail node={obsNode as any} onBack={() => {}} />);
      });

      // Observation callout border, background, and text
      const callout = container.querySelector('[data-testid="node-detail-observation-callout"]') as HTMLElement;
      expect(callout, 'NodeDetail observation callout must render').not.toBeNull();
      expect(callout.style.borderColor, 'Observation callout border must bind to var(--color-status-unknown)').toBe('var(--color-status-unknown)');
      expect(callout.style.color, 'Observation callout text color must bind to var(--color-status-unknown)').toBe('var(--color-status-unknown)');
      const calloutBorderVar = helperExtractVar(callout.style.borderColor);
      const calloutTextVar = helperExtractVar(callout.style.color);

      // DOM extraction for background and dynamic blending over canvas (kills B1 1:1 mutation)
      const calloutBgLight = resolveDomColor(callout.style.backgroundColor, lightTokens['--color-bg-canvas'], lightTokens);
      const calloutBgDark = resolveDomColor(callout.style.backgroundColor, darkTokens['--color-bg-canvas'], darkTokens);
      expect(getContrast(lightTokens[calloutBorderVar], calloutBgLight), 'Callout border light contrast >= 3.0:1').toBeGreaterThanOrEqual(3.0);
      expect(getContrast(lightTokens[calloutTextVar], calloutBgLight), 'Callout text light contrast >= 4.5:1').toBeGreaterThanOrEqual(4.5);
      expect(getContrast(darkTokens[calloutBorderVar], calloutBgDark), 'Callout border dark contrast >= 3.0:1').toBeGreaterThanOrEqual(3.0);
      expect(getContrast(darkTokens[calloutTextVar], calloutBgDark), 'Callout text dark contrast >= 4.5:1').toBeGreaterThanOrEqual(4.5);

      // Strict alpha and RGB tint checks (kills alpha mutation)
      const calloutRgba = parseRgba(callout.style.backgroundColor);
      expect(calloutRgba, 'Callout background must be rgba alpha tint').not.toBeNull();
      expect(calloutRgba?.a, 'Callout alpha tint must be exactly 0.12').toBe(0.12);
      expect(calloutRgba?.rgb, 'Callout tint RGB must match amber [210, 153, 34]').toEqual([210, 153, 34]);

      // Schedulable card when observationOnly
      const schedBox = container.querySelector('[data-testid="node-detail-schedulable-box"]') as HTMLElement;
      expect(schedBox, 'Schedulable box must render').not.toBeNull();
      expect(schedBox.style.borderColor, 'Schedulable box border must bind to var(--color-status-unknown)').toBe('var(--color-status-unknown)');
      const schedLabel = container.querySelector('[data-testid="node-detail-schedulable-label"]') as HTMLElement;
      expect(schedLabel.style.color, 'Schedulable label color must bind to var(--color-status-unknown)').toBe('var(--color-status-unknown)');
      const schedValue = container.querySelector('[data-testid="node-detail-schedulable-value"]') as HTMLElement;
      expect(schedValue.style.color, 'Schedulable value color must bind to var(--color-status-unknown)').toBe('var(--color-status-unknown)');
      const schedBorderVar = helperExtractVar(schedBox.style.borderColor);
      const schedLabelVar = helperExtractVar(schedLabel.style.color);
      const schedValueVar = helperExtractVar(schedValue.style.color);

      // DOM extraction for background and dynamic blending over surface
      const schedObsBgLight = resolveDomColor(schedBox.style.backgroundColor, lightTokens['--color-bg-surface'], lightTokens);
      const schedObsBgDark = resolveDomColor(schedBox.style.backgroundColor, darkTokens['--color-bg-surface'], darkTokens);
      expect(getContrast(lightTokens[schedBorderVar], schedObsBgLight), 'Schedulable obs border light contrast >= 3.0:1').toBeGreaterThanOrEqual(3.0);
      expect(getContrast(lightTokens[schedLabelVar], schedObsBgLight), 'Schedulable obs label light contrast >= 4.5:1').toBeGreaterThanOrEqual(4.5);
      expect(getContrast(lightTokens[schedValueVar], schedObsBgLight), 'Schedulable obs value light contrast >= 4.5:1').toBeGreaterThanOrEqual(4.5);
      expect(getContrast(darkTokens[schedBorderVar], schedObsBgDark), 'Schedulable obs border dark contrast >= 3.0:1').toBeGreaterThanOrEqual(3.0);
      expect(getContrast(darkTokens[schedLabelVar], schedObsBgDark), 'Schedulable obs label dark contrast >= 4.5:1').toBeGreaterThanOrEqual(4.5);
      expect(getContrast(darkTokens[schedValueVar], schedObsBgDark), 'Schedulable obs value dark contrast >= 4.5:1').toBeGreaterThanOrEqual(4.5);

      const schedObsRgba = parseRgba(schedBox.style.backgroundColor);
      expect(schedObsRgba, 'Schedulable obs background must be rgba alpha tint').not.toBeNull();
      expect(schedObsRgba?.a, 'Schedulable obs alpha tint must be exactly 0.15').toBe(0.15);
      expect(schedObsRgba?.rgb, 'Schedulable obs tint RGB must match amber [210, 153, 34]').toEqual([210, 153, 34]);

      // Timeline status for active node
      const timelineActive = container.querySelector('[data-testid="node-detail-timeline-status"]') as HTMLElement;
      expect(timelineActive, 'Timeline status must render').not.toBeNull();
      expect(timelineActive.style.color, 'Timeline active status color must bind to var(--color-status-active)').toBe('var(--color-status-active)');
      expect(timelineActive.textContent).toContain('Heartbeat ACTIVE');
      const tlActiveVar = helperExtractVar(timelineActive.style.color);
      expect(getContrast(lightTokens[tlActiveVar], lightTokens['--color-bg-surface']), 'Timeline active light contrast >= 4.5:1').toBeGreaterThanOrEqual(4.5);
      expect(getContrast(darkTokens[tlActiveVar], darkTokens['--color-bg-surface']), 'Timeline active dark contrast >= 4.5:1').toBeGreaterThanOrEqual(4.5);

      // 2) Render lost NodeDetail with resource usage error
      const lostErrorNode = {
        ...obsNode,
        observationOnly: false,
        status: 'lost',
      };
      await act(async () => {
        root.render(
          <NodeDetail
            node={lostErrorNode as any}
            resourceUsageState="error"
            resourceUsageError="커널 연결 시간 초과"
            onBack={() => {}}
          />
        );
      });

      const errAlert = container.querySelector('[data-testid="node-resource-usage-error"]') as HTMLElement;
      expect(errAlert, 'Resource usage error alert must render').not.toBeNull();
      expect(errAlert.style.borderColor, 'Error alert border must bind to var(--color-status-lost)').toBe('var(--color-status-lost)');
      expect(errAlert.style.color, 'Error alert text color must bind to var(--color-status-lost)').toBe('var(--color-status-lost)');
      const errBorderVar = helperExtractVar(errAlert.style.borderColor);
      const errTextVar = helperExtractVar(errAlert.style.color);

      // DOM extraction for background and dynamic blending over canvas
      const errBgLight = resolveDomColor(errAlert.style.backgroundColor, lightTokens['--color-bg-canvas'], lightTokens);
      const errBgDark = resolveDomColor(errAlert.style.backgroundColor, darkTokens['--color-bg-canvas'], darkTokens);
      expect(getContrast(lightTokens[errBorderVar], errBgLight), 'Error border light contrast >= 3.0:1').toBeGreaterThanOrEqual(3.0);
      expect(getContrast(lightTokens[errTextVar], errBgLight), 'Error text light contrast >= 4.5:1').toBeGreaterThanOrEqual(4.5);
      expect(getContrast(darkTokens[errBorderVar], errBgDark), 'Error border dark contrast >= 3.0:1').toBeGreaterThanOrEqual(3.0);
      expect(getContrast(darkTokens[errTextVar], errBgDark), 'Error text dark contrast >= 4.5:1').toBeGreaterThanOrEqual(4.5);

      const errRgba = parseRgba(errAlert.style.backgroundColor);
      expect(errRgba, 'Error alert background must be rgba alpha tint').not.toBeNull();
      expect(errRgba?.a, 'Error alert alpha tint must be exactly 0.1').toBe(0.1);
      expect(errRgba?.rgb, 'Error alert tint RGB must match red [248, 81, 73]').toEqual([248, 81, 73]);

      // Timeline status for lost node
      const timelineLost = container.querySelector('[data-testid="node-detail-timeline-status"]') as HTMLElement;
      expect(timelineLost.style.color, 'Timeline lost status color must bind to var(--color-status-lost)').toBe('var(--color-status-lost)');
      expect(timelineLost.textContent).toContain('Heartbeat LOST');

      // 3) Render degraded NodeDetail (F5: degraded and unknown semantic distinction)
      const degradedNode = {
        ...obsNode,
        observationOnly: false,
        status: 'degraded',
      };
      await act(async () => {
        root.render(<NodeDetail node={degradedNode as any} onBack={() => {}} />);
      });

      const timelineDegraded = container.querySelector('[data-testid="node-detail-timeline-status"]') as HTMLElement;
      expect(timelineDegraded.style.color, 'Timeline degraded status color must bind to var(--color-status-degraded)').toBe('var(--color-status-degraded)');
      expect(timelineDegraded.textContent).toContain('Heartbeat Warning (Degraded)');
      const tlDegradedVar = helperExtractVar(timelineDegraded.style.color);
      expect(getContrast(lightTokens[tlDegradedVar], lightTokens['--color-bg-surface']), 'Timeline degraded light contrast >= 4.5:1').toBeGreaterThanOrEqual(4.5);
      expect(getContrast(darkTokens[tlDegradedVar], darkTokens['--color-bg-surface']), 'Timeline degraded dark contrast >= 4.5:1').toBeGreaterThanOrEqual(4.5);

      // 4) Render unknown NodeDetail
      const unknownNode = {
        ...obsNode,
        observationOnly: false,
        status: 'unknown',
      };
      await act(async () => {
        root.render(<NodeDetail node={unknownNode as any} onBack={() => {}} />);
      });

      const timelineUnknown = container.querySelector('[data-testid="node-detail-timeline-status"]') as HTMLElement;
      expect(timelineUnknown.style.color, 'Timeline unknown status color must bind to var(--color-status-unknown)').toBe('var(--color-status-unknown)');
      expect(timelineUnknown.textContent).toContain('Heartbeat UNKNOWN');

      // 5) Render standard active non-observationOnly NodeDetail (F2: schedulable box non-obs branch)
      const activeSchedNode = {
        ...obsNode,
        observationOnly: false,
        status: 'active',
        allocatableCores: 8,
        allocatableMemoryBytes: 16 * 1024 ** 3,
      };
      await act(async () => {
        root.render(<NodeDetail node={activeSchedNode as any} onBack={() => {}} />);
      });

      const activeSchedBox = container.querySelector('[data-testid="node-detail-schedulable-box"]') as HTMLElement;
      expect(activeSchedBox, 'Active schedulable box must render').not.toBeNull();
      expect(activeSchedBox.style.backgroundColor, 'Non-obs schedulable box background must be var(--color-bg-subtle)').toBe('var(--color-bg-subtle)');
      expect(activeSchedBox.style.borderColor, 'Non-obs schedulable box border must bind to var(--color-status-online)').toBe('var(--color-status-online)');
      const activeSchedLabel = container.querySelector('[data-testid="node-detail-schedulable-label"]') as HTMLElement;
      expect(activeSchedLabel.style.color, 'Non-obs schedulable label must bind to var(--color-status-online)').toBe('var(--color-status-online)');
      const activeSchedValue = container.querySelector('[data-testid="node-detail-schedulable-value"]') as HTMLElement;
      expect(activeSchedValue.style.color, 'Non-obs schedulable value must bind to var(--color-status-online)').toBe('var(--color-status-online)');
      expect(activeSchedValue.textContent).toContain('8C / 16.0GB');

      const activeBoxBgVar = helperExtractVar(activeSchedBox.style.backgroundColor);
      const activeBoxBorderVar = helperExtractVar(activeSchedBox.style.borderColor);
      const activeLabelVar = helperExtractVar(activeSchedLabel.style.color);
      const activeValueVar = helperExtractVar(activeSchedValue.style.color);
      expect(getContrast(lightTokens[activeLabelVar], lightTokens[activeBoxBgVar]), 'Non-obs sched label light contrast on subtle >= 4.5:1').toBeGreaterThanOrEqual(4.5);
      expect(getContrast(darkTokens[activeLabelVar], darkTokens[activeBoxBgVar]), 'Non-obs sched label dark contrast on subtle >= 4.5:1').toBeGreaterThanOrEqual(4.5);
      expect(getContrast(lightTokens[activeValueVar], lightTokens[activeBoxBgVar]), 'Non-obs sched value light contrast on subtle >= 4.5:1').toBeGreaterThanOrEqual(4.5);
      expect(getContrast(darkTokens[activeValueVar], darkTokens[activeBoxBgVar]), 'Non-obs sched value dark contrast on subtle >= 4.5:1').toBeGreaterThanOrEqual(4.5);
      expect(getContrast(lightTokens[activeBoxBorderVar], lightTokens[activeBoxBgVar]), 'Non-obs sched border light contrast on subtle >= 3.0:1').toBeGreaterThanOrEqual(3.0);
      expect(getContrast(darkTokens[activeBoxBorderVar], darkTokens[activeBoxBgVar]), 'Non-obs sched border dark contrast on subtle >= 3.0:1').toBeGreaterThanOrEqual(3.0);

      // 6) Render online NodeDetail with resource usage (Card 193: NodeDetail residual 9 literals resolution)
      const onlineNode = {
        ...obsNode,
        observationOnly: false,
        status: 'online',
        cpuUsagePercent: 35,
        memoryUsedBytes: 12 * 1024 ** 3,
        memoryTotalBytes: 32 * 1024 ** 3,
      };
      const sampleResourceUsage = {
        source: 'execution-kernel' as const,
        nodeId: 'node_obs_detail',
        stateAsOf: '2026-10-01T12:00:00Z',
        resources: [
          {
            resourceId: 'res_cpu_01',
            kind: 'cpu',
            unit: 'cores',
            capacity: 8,
            offered: 8,
            reserved: 4,
            spare: 4,
            measured: true,
            observedAt: '2026-10-01T12:00:00Z',
          },
          {
            resourceId: 'res_gpu_01',
            kind: 'gpu',
            unit: 'devices',
            capacity: 2,
            offered: 2,
            reserved: 0,
            spare: 2,
            measured: false,
            observedAt: '2026-10-01T12:00:00Z',
          },
        ],
      };

      await act(async () => {
        root.render(
          <NodeDetail
            node={onlineNode as any}
            resourceUsage={sampleResourceUsage as any}
            resourceUsageState="success"
            onBack={() => {}}
          />
        );
      });

      // 6.a) Online Timeline Status (replaces #3fb950)
      const timelineOnline = container.querySelector('[data-testid="node-detail-timeline-status"]') as HTMLElement;
      expect(timelineOnline, 'Timeline online status must render').not.toBeNull();
      expect(timelineOnline.style.color, 'Timeline online status must bind to var(--color-status-online)').toBe('var(--color-status-online)');
      expect(timelineOnline.textContent).toContain('Heartbeat OK');
      const tlOnlineVar = helperExtractVar(timelineOnline.style.color);

      // Extract enclosing panel background from DOM
      const timelinePanel = container.querySelector('[data-testid="node-detail-lease-panel"]') as HTMLElement;
      expect(timelinePanel, 'Timeline lease panel must render').not.toBeNull();
      expect(timelinePanel.style.backgroundColor, 'Timeline lease panel background must bind to var(--color-bg-surface)').toBe('var(--color-bg-surface)');
      const tlPanelBgVar = helperExtractVar(timelinePanel.style.backgroundColor);

      expect(getContrast(lightTokens[tlOnlineVar], lightTokens[tlPanelBgVar]), 'Timeline online light contrast on surface >= 4.5:1').toBeGreaterThanOrEqual(4.5);
      expect(getContrast(darkTokens[tlOnlineVar], darkTokens[tlPanelBgVar]), 'Timeline online dark contrast on surface >= 4.5:1').toBeGreaterThanOrEqual(4.5);

      // 6.b) Resource Measured Badge - measured=true (replaces rgba(46,160,67,0.15), #3fb950, #2ea043)
      const measuredBadge = container.querySelector('[data-testid="resource-measured-badge-cpu"]') as HTMLElement;
      expect(measuredBadge, 'Measured badge must render').not.toBeNull();
      expect(measuredBadge.style.backgroundColor, 'Measured badge background must bind to var(--color-bg-subtle)').toBe('var(--color-bg-subtle)');
      expect(measuredBadge.style.color, 'Measured badge text must bind to var(--color-status-online)').toBe('var(--color-status-online)');
      expect(measuredBadge.style.borderColor, 'Measured badge border must bind to var(--color-status-online)').toBe('var(--color-status-online)');
      const mbTextVar = helperExtractVar(measuredBadge.style.color);
      const mbBgVar = helperExtractVar(measuredBadge.style.backgroundColor);
      const mbBorderVar = helperExtractVar(measuredBadge.style.borderColor);
      expect(getContrast(lightTokens[mbTextVar], lightTokens[mbBgVar]), 'Measured badge text light contrast on subtle >= 4.5:1').toBeGreaterThanOrEqual(4.5);
      expect(getContrast(darkTokens[mbTextVar], darkTokens[mbBgVar]), 'Measured badge text dark contrast on subtle >= 4.5:1').toBeGreaterThanOrEqual(4.5);
      expect(getContrast(lightTokens[mbBorderVar], lightTokens[mbBgVar]), 'Measured badge border light contrast on subtle >= 3.0:1').toBeGreaterThanOrEqual(3.0);
      expect(getContrast(darkTokens[mbBorderVar], darkTokens[mbBgVar]), 'Measured badge border dark contrast on subtle >= 3.0:1').toBeGreaterThanOrEqual(3.0);

      // 6.c) Resource Measured Badge - measured=false (replaces rgba(110,118,129,0.2))
      const unmeasuredBadge = container.querySelector('[data-testid="resource-measured-badge-gpu"]') as HTMLElement;
      expect(unmeasuredBadge, 'Unmeasured badge must render').not.toBeNull();
      expect(unmeasuredBadge.style.backgroundColor, 'Unmeasured badge background must bind to var(--color-bg-subtle)').toBe('var(--color-bg-subtle)');
      expect(unmeasuredBadge.style.color, 'Unmeasured badge text must bind to var(--color-text-muted)').toBe('var(--color-text-muted)');
      expect(unmeasuredBadge.style.borderColor, 'Unmeasured badge border must bind to var(--color-border-subtle)').toBe('var(--color-border-subtle)');
      const umbTextVar = helperExtractVar(unmeasuredBadge.style.color);
      const umbBgVar = helperExtractVar(unmeasuredBadge.style.backgroundColor);
      const umbBorderVar = helperExtractVar(unmeasuredBadge.style.borderColor);
      expect(getContrast(lightTokens[umbTextVar], lightTokens[umbBgVar]), 'Unmeasured badge text light contrast on subtle >= 4.5:1').toBeGreaterThanOrEqual(4.5);
      expect(getContrast(darkTokens[umbTextVar], darkTokens[umbBgVar]), 'Unmeasured badge text dark contrast on subtle >= 4.5:1').toBeGreaterThanOrEqual(4.5);
      expect(getContrast(lightTokens[umbBorderVar], lightTokens[umbBgVar]), 'Unmeasured badge border light contrast on subtle >= 3.0:1').toBeGreaterThanOrEqual(3.0);
      expect(getContrast(darkTokens[umbBorderVar], darkTokens[umbBgVar]), 'Unmeasured badge border dark contrast on subtle >= 3.0:1').toBeGreaterThanOrEqual(3.0);

      // 6.d) Resource Reserved & Spare Values (replaces #58a6ff, #3fb950)
      const resCardCpu = container.querySelector('[data-testid="resource-usage-card-cpu"]') as HTMLElement;
      expect(resCardCpu, 'Resource usage card must render').not.toBeNull();
      expect(resCardCpu.style.backgroundColor, 'Resource usage card background must bind to var(--color-bg-subtle)').toBe('var(--color-bg-subtle)');
      const resCardBgVar = helperExtractVar(resCardCpu.style.backgroundColor);

      const resReservedVal = container.querySelector('[data-testid="resource-reserved-val-cpu"]') as HTMLElement;
      expect(resReservedVal, 'Resource reserved value must render').not.toBeNull();
      expect(resReservedVal.style.color, 'Reserved value must bind to var(--color-brand-primary)').toBe('var(--color-brand-primary)');
      const resReservedVar = helperExtractVar(resReservedVal.style.color);
      expect(getContrast(lightTokens[resReservedVar], lightTokens[resCardBgVar]), 'Reserved value light contrast on subtle >= 4.5:1').toBeGreaterThanOrEqual(4.5);
      expect(getContrast(darkTokens[resReservedVar], darkTokens[resCardBgVar]), 'Reserved value dark contrast on subtle >= 4.5:1').toBeGreaterThanOrEqual(4.5);

      const resSpareVal = container.querySelector('[data-testid="resource-spare-val-cpu"]') as HTMLElement;
      expect(resSpareVal, 'Resource spare value must render').not.toBeNull();
      expect(resSpareVal.style.color, 'Spare value must bind to var(--color-status-online)').toBe('var(--color-status-online)');
      const resSpareVar = helperExtractVar(resSpareVal.style.color);
      expect(getContrast(lightTokens[resSpareVar], lightTokens[resCardBgVar]), 'Spare value light contrast on subtle >= 4.5:1').toBeGreaterThanOrEqual(4.5);
      expect(getContrast(darkTokens[resSpareVar], darkTokens[resCardBgVar]), 'Spare value dark contrast on subtle >= 4.5:1').toBeGreaterThanOrEqual(4.5);

      // 6.e) 4-Tier Breakdown Observed Usage & Headroom Values (replaces #58a6ff, #3fb950)
      const obsUsageBox = container.querySelector('[data-testid="node-detail-observed-usage-box"]') as HTMLElement;
      expect(obsUsageBox, 'Observed usage box must render').not.toBeNull();
      expect(obsUsageBox.style.backgroundColor, 'Observed usage box background must bind to var(--color-bg-subtle)').toBe('var(--color-bg-subtle)');
      const obsUsageBoxBgVar = helperExtractVar(obsUsageBox.style.backgroundColor);

      const obsUsageVal = container.querySelector('[data-testid="node-detail-observed-usage-value"]') as HTMLElement;
      expect(obsUsageVal, 'Observed usage value must render').not.toBeNull();
      expect(obsUsageVal.style.color, 'Observed usage value must bind to var(--color-brand-primary)').toBe('var(--color-brand-primary)');
      const obsUsageVar = helperExtractVar(obsUsageVal.style.color);
      expect(getContrast(lightTokens[obsUsageVar], lightTokens[obsUsageBoxBgVar]), 'Observed usage light contrast on subtle >= 4.5:1').toBeGreaterThanOrEqual(4.5);
      expect(getContrast(darkTokens[obsUsageVar], darkTokens[obsUsageBoxBgVar]), 'Observed usage dark contrast on subtle >= 4.5:1').toBeGreaterThanOrEqual(4.5);

      const obsHeadroomBox = container.querySelector('[data-testid="node-detail-observed-headroom-box"]') as HTMLElement;
      expect(obsHeadroomBox, 'Observed headroom box must render').not.toBeNull();
      expect(obsHeadroomBox.style.backgroundColor, 'Observed headroom box background must bind to var(--color-bg-subtle)').toBe('var(--color-bg-subtle)');
      const obsHeadroomBoxBgVar = helperExtractVar(obsHeadroomBox.style.backgroundColor);

      const obsHeadroomVal = container.querySelector('[data-testid="node-detail-observed-headroom-value"]') as HTMLElement;
      expect(obsHeadroomVal, 'Observed headroom value must render').not.toBeNull();
      expect(obsHeadroomVal.style.color, 'Observed headroom value must bind to var(--color-status-online)').toBe('var(--color-status-online)');
      const obsHeadroomVar = helperExtractVar(obsHeadroomVal.style.color);
      expect(getContrast(lightTokens[obsHeadroomVar], lightTokens[obsHeadroomBoxBgVar]), 'Observed headroom light contrast on subtle >= 4.5:1').toBeGreaterThanOrEqual(4.5);
      expect(getContrast(darkTokens[obsHeadroomVar], darkTokens[obsHeadroomBoxBgVar]), 'Observed headroom dark contrast on subtle >= 4.5:1').toBeGreaterThanOrEqual(4.5);
    } finally {
      act(() => {
        root.unmount();
      });
      container.remove();
    }
  });

  // 9c. [Card 195 / ACC-09] Component DOM Rendering & Binding Verification: Desktop Explorers (ResourceExplorer & InvFileExplorer)
  it('ACC-09 / Card 195: Desktop Explorers (ResourceExplorer & InvFileExplorer) DOM rendering binds foregrounds and container backgrounds to design tokens with dynamic contrast verification', async () => {
    const container = document.createElement('div');
    container.setAttribute('data-theme', 'light');
    document.body.appendChild(container);
    const root = createRoot(container);

    const testNodes: any[] = [
      {
        id: 'nod_01JABCDEF01',
        hostname: 'Node-01-WinMain',
        status: 'online',
        os: 'windows',
        cpuCores: 16,
        cpuUsagePercent: 20,
        memoryTotalBytes: 64 * 1024 ** 3,
        memoryUsedBytes: 20 * 1024 ** 3,
        allocatableCores: 12,
        allocatableMemoryBytes: 36 * 1024 ** 3,
        gpuCount: 1,
        gpuName: 'NVIDIA RTX 4090',
        gpuVramTotalBytes: 24 * 1024 ** 3,
        gpuVramUsedBytes: 6 * 1024 ** 3,
        storageTotalBytes: 2000 * 1024 ** 3,
        storageUsedBytes: 500 * 1024 ** 3,
        heartbeatAt: '2026-10-01T12:00:00Z',
      },
      {
        id: 'nod_01JABCDEF02',
        hostname: 'Node-02-WinWork',
        status: 'online',
        os: 'windows',
        cpuCores: 8,
        cpuUsagePercent: 10,
        memoryTotalBytes: 32 * 1024 ** 3,
        memoryUsedBytes: 8 * 1024 ** 3,
        allocatableCores: 6,
        allocatableMemoryBytes: 20 * 1024 ** 3,
        gpuCount: 0,
        storageTotalBytes: 1000 * 1024 ** 3,
        storageUsedBytes: 200 * 1024 ** 3,
        heartbeatAt: '2026-10-01T12:00:00Z',
      },
    ];

    const testFiles: any[] = [
      {
        uri: 'inv://models/weights.safetensors',
        namespace: 'models',
        relativePath: 'weights.safetensors',
        name: 'weights.safetensors',
        type: 'file',
        sizeBytes: 1024 * 1024 * 50,
        version: '2.0.0',
        contentHash: 'abcdef0123456789abcdef0123456789abcdef0123456789abcdef0123456789',
        contentType: 'application/octet-stream',
        replicas: [
          {
            nodeId: 'nod_01JABCDEF01',
            nodeHostname: 'Node-01-WinMain',
            status: 'healthy',
            localPath: 'C:\\Storage\\weights.safetensors',
            updatedAt: '2026-10-01T12:00:00Z',
          },
        ],
        requiredReplicas: 1,
        isPinned: true,
        classification: 'confidential',
        updatedAt: '2026-10-01T12:00:00Z',
      },
    ];

    try {
      // 1) Render ResourceExplorer (overview mode)
      await act(async () => {
        root.render(
          <ResourceExplorer
            nodes={testNodes}
            nodesState="success"
            lastFetchedAt={new Date('2026-10-01T12:00:00Z')}
          />
        );
      });

      // 1.a) Freshness notice: dynamically extract foreground, background, and border
      const freshnessNotice = container.querySelector('[data-testid="node-freshness-notice"]') as HTMLElement;
      expect(freshnessNotice, 'Node freshness notice must render').not.toBeNull();
      expect(freshnessNotice.style.color, 'Freshness notice color must bind to var(--color-brand-primary)').toBe('var(--color-brand-primary)');
      expect(freshnessNotice.style.backgroundColor, 'Freshness notice background must bind to var(--color-bg-subtle)').toBe('var(--color-bg-subtle)');
      expect(freshnessNotice.style.borderColor, 'Freshness notice border must bind to var(--color-brand-primary)').toBe('var(--color-brand-primary)');

      const freshFgVar = helperExtractVar(freshnessNotice.style.color);
      const freshBgVar = helperExtractVar(freshnessNotice.style.backgroundColor);
      const freshBorderVar = helperExtractVar(freshnessNotice.style.borderColor);

      expect(getContrast(lightTokens[freshFgVar], lightTokens[freshBgVar]), 'Freshness notice light text contrast >= 4.5:1').toBeGreaterThanOrEqual(4.5);
      expect(getContrast(darkTokens[freshFgVar], darkTokens[freshBgVar]), 'Freshness notice dark text contrast >= 4.5:1').toBeGreaterThanOrEqual(4.5);
      expect(getContrast(lightTokens[freshBorderVar], lightTokens[freshBgVar]), 'Freshness notice light border contrast >= 3.0:1').toBeGreaterThanOrEqual(3.0);
      expect(getContrast(darkTokens[freshBorderVar], darkTokens[freshBgVar]), 'Freshness notice dark border contrast >= 3.0:1').toBeGreaterThanOrEqual(3.0);

      // 1.b) Liveness sweep button (action): bg var(--color-bg-subtle), text/border var(--color-status-offline)
      const livenessBtn = container.querySelector('[data-testid="liveness-sweep-btn"]') as HTMLElement;
      expect(livenessBtn, 'Liveness sweep button must render').not.toBeNull();
      expect(livenessBtn.style.backgroundColor, 'Liveness btn background must bind to var(--color-bg-subtle)').toBe('var(--color-bg-subtle)');
      expect(livenessBtn.style.color, 'Liveness btn text must bind to var(--color-status-offline)').toBe('var(--color-status-offline)');
      expect(livenessBtn.style.borderColor, 'Liveness btn border must bind to var(--color-status-offline)').toBe('var(--color-status-offline)');

      const liveBtnBgVar = helperExtractVar(livenessBtn.style.backgroundColor);
      const liveBtnFgVar = helperExtractVar(livenessBtn.style.color);
      const liveBtnBorderVar = helperExtractVar(livenessBtn.style.borderColor);
      expect(getContrast(lightTokens[liveBtnFgVar], lightTokens[liveBtnBgVar]), 'Liveness btn light text contrast >= 4.5:1').toBeGreaterThanOrEqual(4.5);
      expect(getContrast(darkTokens[liveBtnFgVar], darkTokens[liveBtnBgVar]), 'Liveness btn dark text contrast >= 4.5:1').toBeGreaterThanOrEqual(4.5);
      expect(getContrast(lightTokens[liveBtnBorderVar], lightTokens[liveBtnBgVar]), 'Liveness btn light border contrast >= 3.0:1').toBeGreaterThanOrEqual(3.0);
      expect(getContrast(darkTokens[liveBtnBorderVar], darkTokens[liveBtnBgVar]), 'Liveness btn dark border contrast >= 3.0:1').toBeGreaterThanOrEqual(3.0);

      // 1.c) Capacity card: logical vCPU card
      const vcpuCard = container.querySelector('[data-testid="logical-vcpu-card"]') as HTMLElement;
      expect(vcpuCard, 'Logical vcpu card must render').not.toBeNull();
      expect(vcpuCard.style.backgroundColor, 'Capacity card bg must bind to var(--color-bg-subtle)').toBe('var(--color-bg-subtle)');
      expect(vcpuCard.style.borderColor, 'Capacity card border must bind to var(--color-border-subtle)').toBe('var(--color-border-subtle)');
      const vcpuCardBgVar = helperExtractVar(vcpuCard.style.backgroundColor);
      const vcpuCardBorderVar = helperExtractVar(vcpuCard.style.borderColor);
      expect(getContrast(lightTokens[vcpuCardBorderVar], lightTokens[vcpuCardBgVar]), 'Capacity card border light contrast >= 3.0:1').toBeGreaterThanOrEqual(3.0);
      expect(getContrast(darkTokens[vcpuCardBorderVar], darkTokens[vcpuCardBgVar]), 'Capacity card border dark contrast >= 3.0:1').toBeGreaterThanOrEqual(3.0);

      // 1.d) Filter button (all filter is active)
      const filterAllBtn = container.querySelector('[data-testid="filter-all-btn"]') as HTMLElement;
      expect(filterAllBtn, 'Filter all button must render').not.toBeNull();
      expect(filterAllBtn.style.backgroundColor, 'Active filter btn bg must bind to var(--color-bg-subtle)').toBe('var(--color-bg-subtle)');
      expect(filterAllBtn.style.color, 'Active filter btn text must bind to var(--color-brand-primary)').toBe('var(--color-brand-primary)');
      expect(filterAllBtn.style.borderColor, 'Active filter btn border must bind to var(--color-brand-primary)').toBe('var(--color-brand-primary)');
      const fAllBgVar = helperExtractVar(filterAllBtn.style.backgroundColor);
      const fAllFgVar = helperExtractVar(filterAllBtn.style.color);
      const fAllBorderVar = helperExtractVar(filterAllBtn.style.borderColor);
      expect(getContrast(lightTokens[fAllFgVar], lightTokens[fAllBgVar]), 'Active filter btn light text contrast >= 4.5:1').toBeGreaterThanOrEqual(4.5);
      expect(getContrast(darkTokens[fAllFgVar], darkTokens[fAllBgVar]), 'Active filter btn dark text contrast >= 4.5:1').toBeGreaterThanOrEqual(4.5);
      expect(getContrast(lightTokens[fAllBorderVar], lightTokens[fAllBgVar]), 'Active filter btn light border contrast >= 3.0:1').toBeGreaterThanOrEqual(3.0);
      expect(getContrast(darkTokens[fAllBorderVar], darkTokens[fAllBgVar]), 'Active filter btn dark border contrast >= 3.0:1').toBeGreaterThanOrEqual(3.0);

      // 1.e) Node card container (both selected on subtle and unselected on surface) and heartbeat status
      const selectedNodeCard = container.querySelector('[data-testid="node-card-nod_01JABCDEF01"]') as HTMLElement;
      expect(selectedNodeCard, 'Selected node card must render').not.toBeNull();
      expect(selectedNodeCard.style.backgroundColor, 'Selected node card bg must bind to var(--color-bg-subtle)').toBe('var(--color-bg-subtle)');
      expect(selectedNodeCard.style.borderColor, 'Selected node card border must bind to var(--color-brand-primary)').toBe('var(--color-brand-primary)');
      const selCardBgVar = helperExtractVar(selectedNodeCard.style.backgroundColor);
      const selCardBorderVar = helperExtractVar(selectedNodeCard.style.borderColor);
      expect(getContrast(lightTokens[selCardBorderVar], lightTokens[selCardBgVar]), 'Selected node card border light contrast >= 3.0:1').toBeGreaterThanOrEqual(3.0);
      expect(getContrast(darkTokens[selCardBorderVar], darkTokens[selCardBgVar]), 'Selected node card border dark contrast >= 3.0:1').toBeGreaterThanOrEqual(3.0);

      const unselectedNodeCard = container.querySelector('[data-testid="node-card-nod_01JABCDEF02"]') as HTMLElement;
      expect(unselectedNodeCard, 'Unselected node card must render').not.toBeNull();
      expect(unselectedNodeCard.style.backgroundColor, 'Unselected node card bg must bind to var(--color-bg-surface)').toBe('var(--color-bg-surface)');
      expect(unselectedNodeCard.style.borderColor, 'Unselected node card border must bind to var(--color-border-subtle)').toBe('var(--color-border-subtle)');
      const unselCardBgVar = helperExtractVar(unselectedNodeCard.style.backgroundColor);
      const unselCardBorderVar = helperExtractVar(unselectedNodeCard.style.borderColor);
      expect(getContrast(lightTokens[unselCardBorderVar], lightTokens[unselCardBgVar]), 'Unselected node card border light contrast >= 3.0:1').toBeGreaterThanOrEqual(3.0);
      expect(getContrast(darkTokens[unselCardBorderVar], darkTokens[unselCardBgVar]), 'Unselected node card border dark contrast >= 3.0:1').toBeGreaterThanOrEqual(3.0);

      const nodeHeartbeat = container.querySelector('[data-testid="node-card-heartbeat-nod_01JABCDEF02"]') as HTMLElement;
      expect(nodeHeartbeat, 'Node heartbeat must render').not.toBeNull();
      expect(nodeHeartbeat.style.color, 'Node heartbeat color must bind to var(--color-text-muted)').toBe('var(--color-text-muted)');
      const nodeHbVar = helperExtractVar(nodeHeartbeat.style.color);
      expect(getContrast(lightTokens[nodeHbVar], lightTokens[unselCardBgVar]), 'Node heartbeat light text contrast >= 4.5:1').toBeGreaterThanOrEqual(4.5);
      expect(getContrast(darkTokens[nodeHbVar], darkTokens[unselCardBgVar]), 'Node heartbeat dark text contrast >= 4.5:1').toBeGreaterThanOrEqual(4.5);

      // 1.g) ResourceExplorer RAM capacity card
      const ramCard = container.querySelector('[data-testid="logical-ram-card"]') as HTMLElement;
      expect(ramCard, 'Logical RAM card must render').not.toBeNull();
      expect(ramCard.style.backgroundColor, 'RAM card bg must bind to var(--color-bg-subtle)').toBe('var(--color-bg-subtle)');
      expect(ramCard.style.borderColor, 'RAM card border must bind to var(--color-border-subtle)').toBe('var(--color-border-subtle)');
      const ramBgVar = helperExtractVar(ramCard.style.backgroundColor);
      const ramBorderVar = helperExtractVar(ramCard.style.borderColor);
      expect(getContrast(lightTokens[ramBorderVar], lightTokens[ramBgVar]), 'RAM card light border contrast >= 3.0:1').toBeGreaterThanOrEqual(3.0);
      expect(getContrast(darkTokens[ramBorderVar], darkTokens[ramBgVar]), 'RAM card dark border contrast >= 3.0:1').toBeGreaterThanOrEqual(3.0);

      // 1.h) ResourceExplorer plan result message
      await act(async () => {
        root.render(
          <ResourceExplorer
            key="pools-tab"
            nodes={testNodes}
            initialTab="pools"
            initialPoolCapacity={{
              poolId: 'pool-default',
              name: 'default',
              memberCount: 2,
              activeMemberCount: 2,
              totalOffered: { cpuMillicores: 8000, ramBytes: 34359738368, gpuDevices: 0 },
              largestSingleNode: { cpuMillicores: 4000, ramBytes: 17179869184, gpuDevices: 0 },
              spareNow: { cpuMillicores: 6000, ramBytes: 25769803776, gpuDevices: 0 },
              note: '',
              nodes: [],
              units: {} as any,
              unmeasuredNodes: [],
            }}
            initialPoolCapacityState="success"
            initialPlanResult={{ planId: 'plan_alpha_001', strategy: 'sharded', placements: [] } as any}
          />
        );
      });
      const planMsg = container.querySelector('[data-testid="plan-result-message"]') as HTMLElement;
      expect(planMsg, 'Plan result message must render').not.toBeNull();
      expect(planMsg.style.color, 'Plan result message text must bind to var(--color-brand-primary)').toBe('var(--color-brand-primary)');
      const planFgVar = helperExtractVar(planMsg.style.color);
      expect(getContrast(lightTokens[planFgVar], lightTokens['--color-bg-subtle']), 'Plan result message light text contrast >= 4.5:1').toBeGreaterThanOrEqual(4.5);
      expect(getContrast(darkTokens[planFgVar], darkTokens['--color-bg-subtle']), 'Plan result message dark text contrast >= 4.5:1').toBeGreaterThanOrEqual(4.5);

      // 1.f) Node error banner
      await act(async () => {
        root.render(
          <ResourceExplorer
            nodes={[]}
            nodesState="error"
            nodesError="통신 장애 발생"
          />
        );
      });
      const errorBanner = container.querySelector('[data-testid="nodes-fetch-error-banner"]') as HTMLElement;
      expect(errorBanner, 'Nodes fetch error banner must render').not.toBeNull();
      expect(errorBanner.style.backgroundColor, 'Error banner bg must bind to var(--color-bg-subtle)').toBe('var(--color-bg-subtle)');
      expect(errorBanner.style.borderColor, 'Error banner border must bind to var(--color-status-offline)').toBe('var(--color-status-offline)');
      expect(errorBanner.style.color, 'Error banner text must bind to var(--color-status-offline)').toBe('var(--color-status-offline)');
      const errBannerBgVar = helperExtractVar(errorBanner.style.backgroundColor);
      const errBannerBorderVar = helperExtractVar(errorBanner.style.borderColor);
      const errBannerTextVar = helperExtractVar(errorBanner.style.color);
      expect(getContrast(lightTokens[errBannerTextVar], lightTokens[errBannerBgVar]), 'Error banner light text contrast >= 4.5:1').toBeGreaterThanOrEqual(4.5);
      expect(getContrast(darkTokens[errBannerTextVar], darkTokens[errBannerBgVar]), 'Error banner dark text contrast >= 4.5:1').toBeGreaterThanOrEqual(4.5);
      expect(getContrast(lightTokens[errBannerBorderVar], lightTokens[errBannerBgVar]), 'Error banner light border contrast >= 3.0:1').toBeGreaterThanOrEqual(3.0);
      expect(getContrast(darkTokens[errBannerBorderVar], darkTokens[errBannerBgVar]), 'Error banner dark border contrast >= 3.0:1').toBeGreaterThanOrEqual(3.0);

      // 1.i) ResourceExplorer discovery success message
      await act(async () => {
        root.render(
          <ResourceExplorer
            key="discovery-tab"
            nodes={testNodes}
            initialTab="discovery"
            initialDiscoveryMessage="노드 검색이 정상적으로 완료되었습니다."
          />
        );
      });
      const discoveryMsg = container.querySelector('[data-testid="discovery-action-success"]') as HTMLElement;
      expect(discoveryMsg, 'Discovery action success message must render').not.toBeNull();
      expect(discoveryMsg.style.backgroundColor, 'Discovery success bg must bind to var(--color-bg-subtle)').toBe('var(--color-bg-subtle)');
      expect(discoveryMsg.style.color, 'Discovery success text must bind to var(--color-brand-primary)').toBe('var(--color-brand-primary)');
      expect(discoveryMsg.style.borderColor, 'Discovery success border must bind to var(--color-brand-primary)').toBe('var(--color-brand-primary)');
      const discBgVar = helperExtractVar(discoveryMsg.style.backgroundColor);
      const discFgVar = helperExtractVar(discoveryMsg.style.color);
      const discBorderVar = helperExtractVar(discoveryMsg.style.borderColor);
      expect(getContrast(lightTokens[discFgVar], lightTokens[discBgVar]), 'Discovery success light text contrast >= 4.5:1').toBeGreaterThanOrEqual(4.5);
      expect(getContrast(darkTokens[discFgVar], darkTokens[discBgVar]), 'Discovery success dark text contrast >= 4.5:1').toBeGreaterThanOrEqual(4.5);
      expect(getContrast(lightTokens[discBorderVar], lightTokens[discBgVar]), 'Discovery success light border contrast >= 3.0:1').toBeGreaterThanOrEqual(3.0);
      expect(getContrast(darkTokens[discBorderVar], darkTokens[discBgVar]), 'Discovery success dark border contrast >= 3.0:1').toBeGreaterThanOrEqual(3.0);

      // 2) Render InvFileExplorer
      const locationsSpy = vi.spyOn(fabricObservation, 'locations').mockResolvedValue({ items: [], nextCursor: null });
      await act(async () => {
        root.render(
          <InvFileExplorer
            clusterNodes={testNodes}
            initialFiles={testFiles}
            initialNamespace="models"
            initialUri="inv://models"
            initialRepairError="복구 실패: 생존 노드 부재"
          />
        );
      });

      // 2.a) Address bar input & navigation button
      const addressBar = container.querySelector('[data-testid="inv-address-bar"]') as HTMLInputElement;
      expect(addressBar, 'Inv address bar must render').not.toBeNull();
      expect(addressBar.style.backgroundColor, 'Address bar bg must bind to var(--color-bg-subtle)').toBe('var(--color-bg-subtle)');
      expect(addressBar.style.color, 'Address bar text must bind to var(--color-text-primary)').toBe('var(--color-text-primary)');
      expect(addressBar.style.borderColor, 'Address bar border must bind to var(--color-border-subtle)').toBe('var(--color-border-subtle)');
      const addrBgVar = helperExtractVar(addressBar.style.backgroundColor);
      const addrFgVar = helperExtractVar(addressBar.style.color);
      const addrBorderVar = helperExtractVar(addressBar.style.borderColor);
      expect(getContrast(lightTokens[addrFgVar], lightTokens[addrBgVar]), 'Address bar light text contrast >= 4.5:1').toBeGreaterThanOrEqual(4.5);
      expect(getContrast(darkTokens[addrFgVar], darkTokens[addrBgVar]), 'Address bar dark text contrast >= 4.5:1').toBeGreaterThanOrEqual(4.5);
      expect(getContrast(lightTokens[addrBorderVar], lightTokens[addrBgVar]), 'Address bar light border contrast >= 3.0:1').toBeGreaterThanOrEqual(3.0);
      expect(getContrast(darkTokens[addrBorderVar], darkTokens[addrBgVar]), 'Address bar dark border contrast >= 3.0:1').toBeGreaterThanOrEqual(3.0);

      const navBtn = container.querySelector('[data-testid="inv-navigate-btn"]') as HTMLElement;
      expect(navBtn, 'Navigate btn must render').not.toBeNull();
      expect(navBtn.style.backgroundColor, 'Navigate btn bg must bind to var(--color-brand-primary-bg)').toBe('var(--color-brand-primary-bg)');
      expect(navBtn.style.color, 'Navigate btn text must bind to var(--color-brand-primary-fg)').toBe('var(--color-brand-primary-fg)');
      const navBtnBgVar = helperExtractVar(navBtn.style.backgroundColor);
      const navBtnFgVar = helperExtractVar(navBtn.style.color);
      expect(getContrast(lightTokens[navBtnFgVar], lightTokens[navBtnBgVar]), 'Navigate btn light text contrast >= 4.5:1').toBeGreaterThanOrEqual(4.5);
      expect(getContrast(darkTokens[navBtnFgVar], darkTokens[navBtnBgVar]), 'Navigate btn dark text contrast >= 4.5:1').toBeGreaterThanOrEqual(4.5);

      // 2.b) File row and selection styling
      const fileRow = container.querySelector('[data-testid="file-row-inv://models/weights.safetensors"]') as HTMLElement;
      expect(fileRow, 'File row must render').not.toBeNull();
      expect(fileRow.style.backgroundColor, 'Selected file row bg must bind to var(--color-brand-subtle)').toBe('var(--color-brand-subtle)');
      expect(fileRow.style.borderColor, 'Selected file row border must bind to var(--color-brand-primary)').toBe('var(--color-brand-primary)');
      const fileRowBgVar = helperExtractVar(fileRow.style.backgroundColor);
      const fileRowBorderVar = helperExtractVar(fileRow.style.borderColor);
      expect(getContrast(lightTokens[fileRowBorderVar], lightTokens[fileRowBgVar]), 'Selected file row border light contrast >= 3.0:1').toBeGreaterThanOrEqual(3.0);
      expect(getContrast(darkTokens[fileRowBorderVar], darkTokens[fileRowBgVar]), 'Selected file row border dark contrast >= 3.0:1').toBeGreaterThanOrEqual(3.0);

      // 2.c) Integrity badge (idle / unverified)
      const integrityBadge = container.querySelector('[data-testid="integrity-badge"]') as HTMLElement;
      expect(integrityBadge, 'Integrity badge must render').not.toBeNull();
      expect(integrityBadge.style.backgroundColor, 'Integrity badge bg must bind to var(--color-bg-subtle)').toBe('var(--color-bg-subtle)');
      expect(integrityBadge.style.color, 'Integrity badge text must bind to var(--color-status-degraded)').toBe('var(--color-status-degraded)');
      expect(integrityBadge.style.borderColor, 'Integrity badge border must bind to var(--color-status-degraded)').toBe('var(--color-status-degraded)');
      const intBadgeBgVar = helperExtractVar(integrityBadge.style.backgroundColor);
      const intBadgeFgVar = helperExtractVar(integrityBadge.style.color);
      const intBadgeBorderVar = helperExtractVar(integrityBadge.style.borderColor);
      expect(getContrast(lightTokens[intBadgeFgVar], lightTokens[intBadgeBgVar]), 'Integrity badge light text contrast >= 4.5:1').toBeGreaterThanOrEqual(4.5);
      expect(getContrast(darkTokens[intBadgeFgVar], darkTokens[intBadgeBgVar]), 'Integrity badge dark text contrast >= 4.5:1').toBeGreaterThanOrEqual(4.5);
      expect(getContrast(lightTokens[intBadgeBorderVar], lightTokens[intBadgeBgVar]), 'Integrity badge light border contrast >= 3.0:1').toBeGreaterThanOrEqual(3.0);
      expect(getContrast(darkTokens[intBadgeBorderVar], darkTokens[intBadgeBgVar]), 'Integrity badge dark border contrast >= 3.0:1').toBeGreaterThanOrEqual(3.0);

      // 2.d) Replica healthy badge
      const replicaHealthyBadge = container.querySelector('[data-testid="replica-healthy-badge"]') as HTMLElement;
      expect(replicaHealthyBadge, 'Replica healthy badge must render').not.toBeNull();
      expect(replicaHealthyBadge.style.backgroundColor, 'Replica healthy badge bg must bind to var(--color-bg-subtle)').toBe('var(--color-bg-subtle)');
      expect(replicaHealthyBadge.style.color, 'Replica healthy badge text must bind to var(--color-status-online)').toBe('var(--color-status-online)');
      expect(replicaHealthyBadge.style.borderColor, 'Replica healthy badge border must bind to var(--color-status-online)').toBe('var(--color-status-online)');
      const repBadgeBgVar = helperExtractVar(replicaHealthyBadge.style.backgroundColor);
      const repBadgeFgVar = helperExtractVar(replicaHealthyBadge.style.color);
      const repBadgeBorderVar = helperExtractVar(replicaHealthyBadge.style.borderColor);
      expect(getContrast(lightTokens[repBadgeFgVar], lightTokens[repBadgeBgVar]), 'Replica healthy badge light text contrast >= 4.5:1').toBeGreaterThanOrEqual(4.5);
      expect(getContrast(darkTokens[repBadgeFgVar], darkTokens[repBadgeBgVar]), 'Replica healthy badge dark text contrast >= 4.5:1').toBeGreaterThanOrEqual(4.5);
      expect(getContrast(lightTokens[repBadgeBorderVar], lightTokens[repBadgeBgVar]), 'Replica healthy badge light border contrast >= 3.0:1').toBeGreaterThanOrEqual(3.0);
      expect(getContrast(darkTokens[repBadgeBorderVar], darkTokens[repBadgeBgVar]), 'Replica healthy badge dark border contrast >= 3.0:1').toBeGreaterThanOrEqual(3.0);

      // 2.e) Active namespace chip (InvFileExplorer)
      const activeChip = container.querySelector('[data-testid="nav-namespace-models"]') as HTMLElement;
      expect(activeChip, 'Active namespace chip must render').not.toBeNull();
      expect(activeChip.style.backgroundColor, 'Active chip bg must bind to var(--color-brand-subtle)').toBe('var(--color-brand-subtle)');
      expect(activeChip.style.color, 'Active chip text must bind to var(--color-brand-hover)').toBe('var(--color-brand-hover)');
      expect(activeChip.style.borderColor, 'Active chip border must bind to var(--color-brand-hover)').toBe('var(--color-brand-hover)');
      const chipBgVar = helperExtractVar(activeChip.style.backgroundColor);
      const chipFgVar = helperExtractVar(activeChip.style.color);
      const chipBorderVar = helperExtractVar(activeChip.style.borderColor);
      expect(getContrast(lightTokens[chipFgVar], lightTokens[chipBgVar]), 'Active chip light text contrast >= 4.5:1').toBeGreaterThanOrEqual(4.5);
      expect(getContrast(darkTokens[chipFgVar], darkTokens[chipBgVar]), 'Active chip dark text contrast >= 4.5:1').toBeGreaterThanOrEqual(4.5);
      expect(getContrast(lightTokens[chipBorderVar], lightTokens[chipBgVar]), 'Active chip light border contrast >= 3.0:1').toBeGreaterThanOrEqual(3.0);
      expect(getContrast(darkTokens[chipBorderVar], darkTokens[chipBgVar]), 'Active chip dark border contrast >= 3.0:1').toBeGreaterThanOrEqual(3.0);

      // 2.f) File version badge (InvFileExplorer)
      const verBadge = container.querySelector('[data-testid="file-version-badge"]') as HTMLElement;
      expect(verBadge, 'File version badge must render').not.toBeNull();
      expect(verBadge.style.backgroundColor, 'File version badge bg must bind to var(--color-brand-subtle)').toBe('var(--color-brand-subtle)');
      expect(verBadge.style.color, 'File version badge text must bind to var(--color-brand-hover)').toBe('var(--color-brand-hover)');
      expect(verBadge.style.borderColor, 'File version badge border must bind to var(--color-brand-hover)').toBe('var(--color-brand-hover)');
      const verBadgeBgVar = helperExtractVar(verBadge.style.backgroundColor);
      const verBadgeFgVar = helperExtractVar(verBadge.style.color);
      const verBadgeBorderVar = helperExtractVar(verBadge.style.borderColor);
      expect(getContrast(lightTokens[verBadgeFgVar], lightTokens[verBadgeBgVar]), 'File version badge light text contrast >= 4.5:1').toBeGreaterThanOrEqual(4.5);
      expect(getContrast(darkTokens[verBadgeFgVar], darkTokens[verBadgeBgVar]), 'File version badge dark text contrast >= 4.5:1').toBeGreaterThanOrEqual(4.5);
      expect(getContrast(lightTokens[verBadgeBorderVar], lightTokens[verBadgeBgVar]), 'File version badge light border contrast >= 3.0:1').toBeGreaterThanOrEqual(3.0);
      expect(getContrast(darkTokens[verBadgeBorderVar], darkTokens[verBadgeBgVar]), 'File version badge dark border contrast >= 3.0:1').toBeGreaterThanOrEqual(3.0);

      // 2.g) Disabled canonical lookup button (InvFileExplorer)
      const lookupBtn = container.querySelector('[data-testid="inv-canonical-lookup-btn"]') as HTMLElement;
      expect(lookupBtn, 'Canonical lookup btn must render').not.toBeNull();
      expect(lookupBtn.style.backgroundColor, 'Disabled lookup btn bg must bind to var(--color-bg-subtle)').toBe('var(--color-bg-subtle)');
      expect(lookupBtn.style.color, 'Disabled lookup btn text must bind to var(--color-text-muted)').toBe('var(--color-text-muted)');
      expect(lookupBtn.style.borderColor, 'Disabled lookup btn border must bind to var(--color-border-subtle)').toBe('var(--color-border-subtle)');
      const lookupBgVar = helperExtractVar(lookupBtn.style.backgroundColor);
      const lookupFgVar = helperExtractVar(lookupBtn.style.color);
      const lookupBorderVar = helperExtractVar(lookupBtn.style.borderColor);
      expect(getContrast(lightTokens[lookupFgVar], lightTokens[lookupBgVar]), 'Disabled lookup btn light text contrast >= 4.5:1').toBeGreaterThanOrEqual(4.5);
      expect(getContrast(darkTokens[lookupFgVar], darkTokens[lookupBgVar]), 'Disabled lookup btn dark text contrast >= 4.5:1').toBeGreaterThanOrEqual(4.5);
      expect(getContrast(lightTokens[lookupBorderVar], lightTokens[lookupBgVar]), 'Disabled lookup btn light border contrast >= 3.0:1').toBeGreaterThanOrEqual(3.0);
      expect(getContrast(darkTokens[lookupBorderVar], darkTokens[lookupBgVar]), 'Disabled lookup btn dark border contrast >= 3.0:1').toBeGreaterThanOrEqual(3.0);

      // 2.h) Disabled repair replicas button (InvFileExplorer)
      const repairBtn = container.querySelector('[data-testid="repair-replicas-btn"]') as HTMLElement;
      expect(repairBtn, 'Repair replicas btn must render').not.toBeNull();
      expect(repairBtn.style.backgroundColor, 'Disabled repair btn bg must bind to var(--color-bg-subtle)').toBe('var(--color-bg-subtle)');
      expect(repairBtn.style.color, 'Disabled repair btn text must bind to var(--color-text-muted)').toBe('var(--color-text-muted)');
      expect(repairBtn.style.borderColor, 'Disabled repair btn border must bind to var(--color-border-subtle)').toBe('var(--color-border-subtle)');
      const repairBgVar = helperExtractVar(repairBtn.style.backgroundColor);
      const repairFgVar = helperExtractVar(repairBtn.style.color);
      const repairBorderVar = helperExtractVar(repairBtn.style.borderColor);
      expect(getContrast(lightTokens[repairFgVar], lightTokens[repairBgVar]), 'Disabled repair btn light text contrast >= 4.5:1').toBeGreaterThanOrEqual(4.5);
      expect(getContrast(darkTokens[repairFgVar], darkTokens[repairBgVar]), 'Disabled repair btn dark text contrast >= 4.5:1').toBeGreaterThanOrEqual(4.5);
      expect(getContrast(lightTokens[repairBorderVar], lightTokens[repairBgVar]), 'Disabled repair btn light border contrast >= 3.0:1').toBeGreaterThanOrEqual(3.0);
      expect(getContrast(darkTokens[repairBorderVar], darkTokens[repairBgVar]), 'Disabled repair btn dark border contrast >= 3.0:1').toBeGreaterThanOrEqual(3.0);

      // 2.i) Repair error banner (InvFileExplorer)
      const repairErr = container.querySelector('[data-testid="repair-action-error"]') as HTMLElement;
      expect(repairErr, 'Repair action error must render').not.toBeNull();
      expect(repairErr.style.backgroundColor, 'Repair error bg must bind to var(--color-bg-surface)').toBe('var(--color-bg-surface)');
      expect(repairErr.style.color, 'Repair error text must bind to var(--color-status-lost)').toBe('var(--color-status-lost)');
      expect(repairErr.style.borderColor, 'Repair error border must bind to var(--color-status-lost)').toBe('var(--color-status-lost)');
      const repErrBgVar = helperExtractVar(repairErr.style.backgroundColor);
      const repErrFgVar = helperExtractVar(repairErr.style.color);
      const repErrBorderVar = helperExtractVar(repairErr.style.borderColor);
      expect(getContrast(lightTokens[repErrFgVar], lightTokens[repErrBgVar]), 'Repair error light text contrast >= 4.5:1').toBeGreaterThanOrEqual(4.5);
      expect(getContrast(darkTokens[repErrFgVar], darkTokens[repErrBgVar]), 'Repair error dark text contrast >= 4.5:1').toBeGreaterThanOrEqual(4.5);
      expect(getContrast(lightTokens[repErrBorderVar], lightTokens[repErrBgVar]), 'Repair error light border contrast >= 3.0:1').toBeGreaterThanOrEqual(3.0);
      expect(getContrast(darkTokens[repErrBorderVar], darkTokens[repErrBgVar]), 'Repair error dark border contrast >= 3.0:1').toBeGreaterThanOrEqual(3.0);
    } finally {
      act(() => {
        root.unmount();
      });
      container.remove();
      vi.restoreAllMocks();
    }
  });

  // 9d. [Card 197 / ACC-09] Component DOM Rendering & Binding Verification: ModelLineageView
  it('ACC-09 / Card 197: ModelLineageView DOM rendering binds foregrounds and container backgrounds to design tokens with dynamic contrast verification', async () => {
    const originalFetch = globalThis.fetch;
    globalThis.fetch = vi.fn().mockImplementation(() =>
      Promise.resolve(new Response(JSON.stringify({}), { status: 200, headers: { 'Content-Type': 'application/json' } }))
    );

    const container = document.createElement('div');
    container.setAttribute('data-theme', 'light');
    document.body.appendChild(container);
    const root = createRoot(container);

    try {
      await act(async () => {
        root.render(<ModelLineageView />);
      });

      // 1. Control Panel and Header
      const controlPanel = container.querySelector('[data-testid="model-registry-control-panel"]') as HTMLElement;
      expect(controlPanel, 'Control panel must render').not.toBeNull();
      expect(controlPanel.style.backgroundColor, 'Control panel bg must bind to var(--color-bg-surface)').toBe('var(--color-bg-surface)');
      expect(controlPanel.style.borderColor, 'Control panel border must bind to var(--color-border-subtle)').toBe('var(--color-border-subtle)');

      const cpBgVar = helperExtractVar(controlPanel.style.backgroundColor);
      const cpBorderVar = helperExtractVar(controlPanel.style.borderColor);
      expect(getContrast(lightTokens[cpBorderVar], lightTokens[cpBgVar]), 'Control panel light border contrast >= 3.0:1').toBeGreaterThanOrEqual(3.0);
      expect(getContrast(darkTokens[cpBorderVar], darkTokens[cpBgVar]), 'Control panel dark border contrast >= 3.0:1').toBeGreaterThanOrEqual(3.0);

      // 2. W3 Seam Badge
      const seamBadge = container.querySelector('[data-testid="badge-w3-verify-seam"]') as HTMLElement;
      expect(seamBadge, 'W3 verify seam badge must render').not.toBeNull();
      expect(seamBadge.style.backgroundColor, 'Seam badge bg must bind to var(--color-bg-subtle)').toBe('var(--color-bg-subtle)');
      expect(seamBadge.style.color, 'Seam badge text must bind to var(--color-text-muted)').toBe('var(--color-text-muted)');
      expect(seamBadge.style.borderColor, 'Seam badge border must bind to var(--color-border-subtle)').toBe('var(--color-border-subtle)');

      const seamBgVar = helperExtractVar(seamBadge.style.backgroundColor);
      const seamFgVar = helperExtractVar(seamBadge.style.color);
      const seamBorderVar = helperExtractVar(seamBadge.style.borderColor);
      expect(getContrast(lightTokens[seamFgVar], lightTokens[seamBgVar]), 'Seam badge light text contrast >= 4.5:1').toBeGreaterThanOrEqual(4.5);
      expect(getContrast(darkTokens[seamFgVar], darkTokens[seamBgVar]), 'Seam badge dark text contrast >= 4.5:1').toBeGreaterThanOrEqual(4.5);
      expect(getContrast(lightTokens[seamBorderVar], lightTokens[seamBgVar]), 'Seam badge light border contrast >= 3.0:1').toBeGreaterThanOrEqual(3.0);
      expect(getContrast(darkTokens[seamBorderVar], darkTokens[seamBgVar]), 'Seam badge dark border contrast >= 3.0:1').toBeGreaterThanOrEqual(3.0);

      // 3. Project ID Input
      const projInput = container.querySelector('[data-testid="input-project-id"]') as HTMLElement;
      expect(projInput, 'Project ID input must render').not.toBeNull();
      expect(projInput.style.backgroundColor, 'Project input bg must bind to var(--color-bg-subtle)').toBe('var(--color-bg-subtle)');
      expect(projInput.style.color, 'Project input text must bind to var(--color-text-primary)').toBe('var(--color-text-primary)');
      expect(projInput.style.borderColor, 'Project input border must bind to var(--color-border-subtle)').toBe('var(--color-border-subtle)');

      const inputBgVar = helperExtractVar(projInput.style.backgroundColor);
      const inputFgVar = helperExtractVar(projInput.style.color);
      const inputBorderVar = helperExtractVar(projInput.style.borderColor);
      expect(getContrast(lightTokens[inputFgVar], lightTokens[inputBgVar]), 'Input light text contrast >= 4.5:1').toBeGreaterThanOrEqual(4.5);
      expect(getContrast(darkTokens[inputFgVar], darkTokens[inputBgVar]), 'Input dark text contrast >= 4.5:1').toBeGreaterThanOrEqual(4.5);
      expect(getContrast(lightTokens[inputBorderVar], lightTokens[inputBgVar]), 'Input light border contrast >= 3.0:1').toBeGreaterThanOrEqual(3.0);
      expect(getContrast(darkTokens[inputBorderVar], darkTokens[inputBgVar]), 'Input dark border contrast >= 3.0:1').toBeGreaterThanOrEqual(3.0);

      // 4. Governance Approval Notice Banner (canApprove = false default)
      const noApproveBanner = container.querySelector('[data-testid="banner-no-approve-permission"]') as HTMLElement;
      expect(noApproveBanner, 'No approve permission banner must render').not.toBeNull();
      expect(noApproveBanner.style.backgroundColor, 'Banner bg must bind to var(--color-bg-subtle)').toBe('var(--color-bg-subtle)');
      expect(noApproveBanner.style.color, 'Banner text must bind to var(--color-status-offline)').toBe('var(--color-status-offline)');
      expect(noApproveBanner.style.borderColor, 'Banner border must bind to var(--color-status-offline)').toBe('var(--color-status-offline)');

      const bannerBgVar = helperExtractVar(noApproveBanner.style.backgroundColor);
      const bannerFgVar = helperExtractVar(noApproveBanner.style.color);
      const bannerBorderVar = helperExtractVar(noApproveBanner.style.borderColor);
      expect(getContrast(lightTokens[bannerFgVar], lightTokens[bannerBgVar]), 'Banner light text contrast >= 4.5:1').toBeGreaterThanOrEqual(4.5);
      expect(getContrast(darkTokens[bannerFgVar], darkTokens[bannerBgVar]), 'Banner dark text contrast >= 4.5:1').toBeGreaterThanOrEqual(4.5);
      expect(getContrast(lightTokens[bannerBorderVar], lightTokens[bannerBgVar]), 'Banner light border contrast >= 3.0:1').toBeGreaterThanOrEqual(3.0);
      expect(getContrast(darkTokens[bannerBorderVar], darkTokens[bannerBgVar]), 'Banner dark border contrast >= 3.0:1').toBeGreaterThanOrEqual(3.0);

      // 5. Action Navigation Tabs: Active Tab (Trace) and Inactive Tab (Register)
      const tabTrace = container.querySelector('[data-testid="tab-trace"]') as HTMLElement;
      expect(tabTrace, 'Tab trace must render').not.toBeNull();
      expect(tabTrace.style.backgroundColor, 'Active tab bg must bind to var(--color-bg-subtle)').toBe('var(--color-bg-subtle)');
      expect(tabTrace.style.color, 'Active tab text must bind to var(--color-brand-primary)').toBe('var(--color-brand-primary)');
      expect(tabTrace.style.borderColor, 'Active tab border must bind to var(--color-brand-primary)').toBe('var(--color-brand-primary)');

      const activeTabBgVar = helperExtractVar(tabTrace.style.backgroundColor);
      const activeTabFgVar = helperExtractVar(tabTrace.style.color);
      const activeTabBorderVar = helperExtractVar(tabTrace.style.borderColor);
      expect(getContrast(lightTokens[activeTabFgVar], lightTokens[activeTabBgVar]), 'Active tab light text contrast >= 4.5:1').toBeGreaterThanOrEqual(4.5);
      expect(getContrast(darkTokens[activeTabFgVar], darkTokens[activeTabBgVar]), 'Active tab dark text contrast >= 4.5:1').toBeGreaterThanOrEqual(4.5);
      expect(getContrast(lightTokens[activeTabBorderVar], lightTokens[activeTabBgVar]), 'Active tab light border contrast >= 3.0:1').toBeGreaterThanOrEqual(3.0);
      expect(getContrast(darkTokens[activeTabBorderVar], darkTokens[activeTabBgVar]), 'Active tab dark border contrast >= 3.0:1').toBeGreaterThanOrEqual(3.0);

      const tabRegister = container.querySelector('[data-testid="tab-register"]') as HTMLElement;
      expect(tabRegister, 'Tab register must render').not.toBeNull();
      expect(tabRegister.style.color, 'Inactive tab text must bind to var(--color-text-muted)').toBe('var(--color-text-muted)');
      const inactiveTabFgVar = helperExtractVar(tabRegister.style.color);
      expect(getContrast(lightTokens[inactiveTabFgVar], lightTokens[cpBgVar]), 'Inactive tab light text contrast >= 4.5:1').toBeGreaterThanOrEqual(4.5);
      expect(getContrast(darkTokens[inactiveTabFgVar], darkTokens[cpBgVar]), 'Inactive tab dark text contrast >= 4.5:1').toBeGreaterThanOrEqual(4.5);

      // 6. Lineage Unexposed Notice Banner
      const unexposedNotice = container.querySelector('[data-testid="lineage-unexposed-notice"]') as HTMLElement;
      expect(unexposedNotice, 'Lineage unexposed notice must render').not.toBeNull();
      expect(unexposedNotice.style.backgroundColor, 'Unexposed notice bg must bind to var(--color-bg-subtle)').toBe('var(--color-bg-subtle)');
      expect(unexposedNotice.style.color, 'Unexposed notice text must bind to var(--color-status-degraded)').toBe('var(--color-status-degraded)');
      expect(unexposedNotice.style.borderColor, 'Unexposed notice border must bind to var(--color-status-degraded)').toBe('var(--color-status-degraded)');

      const unexpBgVar = helperExtractVar(unexposedNotice.style.backgroundColor);
      const unexpFgVar = helperExtractVar(unexposedNotice.style.color);
      const unexpBorderVar = helperExtractVar(unexposedNotice.style.borderColor);
      expect(getContrast(lightTokens[unexpFgVar], lightTokens[unexpBgVar]), 'Unexposed notice light text contrast >= 4.5:1').toBeGreaterThanOrEqual(4.5);
      expect(getContrast(darkTokens[unexpFgVar], darkTokens[unexpBgVar]), 'Unexposed notice dark text contrast >= 4.5:1').toBeGreaterThanOrEqual(4.5);
      expect(getContrast(lightTokens[unexpBorderVar], lightTokens[unexpBgVar]), 'Unexposed notice light border contrast >= 3.0:1').toBeGreaterThanOrEqual(3.0);
      expect(getContrast(darkTokens[unexpBorderVar], darkTokens[unexpBgVar]), 'Unexposed notice dark border contrast >= 3.0:1').toBeGreaterThanOrEqual(3.0);
    } finally {
      globalThis.fetch = originalFetch;
      act(() => {
        root.unmount();
      });
      container.remove();
    }
  });

  // 9d-2. [Card 197 r2 / ACC-09 / Claude r2 & Codex r2] Dynamic AST Style-Pair Contrast Calculator & Strict Coverage Ratchet: ModelLineageView
  it('ACC-09 / Card 197: ModelLineageView style objects maintain valid contrast pairings and reject 1:1 collisions and defective combinations', () => {
    const filePath = path.resolve(__dirname, '../src/features/mlops/ModelLineageView.tsx');
    const content = fs.readFileSync(filePath, 'utf-8');
    const sf = ts.createSourceFile('ModelLineageView.tsx', content, ts.ScriptTarget.Latest, true, ts.ScriptKind.TSX);

    interface Branch {
      cond: string;
      token: string;
    }

    function extractBranches(node: ts.Node): Branch[] {
      const branches: Branch[] = [];
      function collect(n: ts.Node, condPath: string) {
        if (ts.isConditionalExpression(n)) {
          const condText = n.condition.getText(sf).replace(/\s+/g, ' ');
          collect(n.whenTrue, condPath ? `${condPath} && ${condText}` : condText);
          collect(n.whenFalse, condPath ? `${condPath} && !(${condText})` : `!(${condText})`);
        } else if (ts.isTemplateExpression(n)) {
          for (const span of n.templateSpans) {
            collect(span.expression, condPath);
          }
        } else {
          const text = n.getText(sf);
          const m = text.match(/var\((--color-[a-z0-9-]+)\)/);
          if (m) {
            branches.push({ cond: condPath, token: m[1] });
          }
        }
      }
      collect(node, '');
      return branches;
    }

    let checkedPairs = 0;
    let checkedObjects = 0;
    let totalStyleAttrs = 0;
    let unboundColorObjects = 0;
    let checkedBorderObjects = 0;
    let checkedBorderPairs = 0;
    const violations: string[] = [];
    const containerBgs = ['--color-bg-surface', '--color-bg-subtle', '--color-bg-canvas'];

    function checkPair(bgToken: string, fgToken: string, pos: number) {
      checkedPairs++;
      const { line } = sf.getLineAndCharacterOfPosition(pos);
      const lightBg = lightTokens[bgToken];
      const lightFg = lightTokens[fgToken];
      const darkBg = darkTokens[bgToken];
      const darkFg = darkTokens[fgToken];

      if (bgToken === fgToken) {
        violations.push(`L${line + 1}: 1:1 token collision between background and foreground (${bgToken})`);
        return;
      }

      if (lightBg && lightFg) {
        const cr = getContrast(lightFg, lightBg);
        if (cr < 4.5) {
          violations.push(`L${line + 1}: Light text contrast ${cr.toFixed(2)}:1 < 4.5:1 (${fgToken} on ${bgToken})`);
        }
      }
      if (darkBg && darkFg) {
        const cr = getContrast(darkFg, darkBg);
        if (cr < 4.5) {
          violations.push(`L${line + 1}: Dark text contrast ${cr.toFixed(2)}:1 < 4.5:1 (${fgToken} on ${bgToken})`);
        }
      }
    }

    function checkInheritedColor(fgToken: string, pos: number) {
      const { line } = sf.getLineAndCharacterOfPosition(pos);
      const lightFg = lightTokens[fgToken];
      const darkFg = darkTokens[fgToken];

      for (const bgToken of containerBgs) {
        const lightBg = lightTokens[bgToken];
        const darkBg = darkTokens[bgToken];

        if (lightBg && lightFg) {
          const cr = getContrast(lightFg, lightBg);
          if (cr < 4.5) {
            violations.push(`L${line + 1}: Inherited Light text contrast ${cr.toFixed(2)}:1 < 4.5:1 (${fgToken} on container ${bgToken})`);
          }
        }
        if (darkBg && darkFg) {
          const cr = getContrast(darkFg, darkBg);
          if (cr < 4.5) {
            violations.push(`L${line + 1}: Inherited Dark text contrast ${cr.toFixed(2)}:1 < 4.5:1 (${fgToken} on container ${bgToken})`);
          }
        }
      }
    }

    function checkBorderPair(bgToken: string, borderToken: string, pos: number) {
      checkedBorderPairs++;
      const { line } = sf.getLineAndCharacterOfPosition(pos);
      const lBg = lightTokens[bgToken];
      const dBg = darkTokens[bgToken];
      const lBorder = lightTokens[borderToken];
      const dBorder = darkTokens[borderToken];

      if (bgToken === borderToken) {
        violations.push(`L${line + 1}: Identical border-background token collision (1:1 contrast) detected: ${borderToken} on ${bgToken}`);
        return;
      }

      if (lBg && lBorder) {
        const cr = getContrast(lBorder, lBg);
        if (cr < 3.0) {
          violations.push(`L${line + 1}: Light border contrast ${cr.toFixed(2)}:1 < 3.0:1 (${borderToken} on ${bgToken})`);
        }
      }
      if (dBg && dBorder) {
        const cr = getContrast(dBorder, dBg);
        if (cr < 3.0) {
          violations.push(`L${line + 1}: Dark border contrast ${cr.toFixed(2)}:1 < 3.0:1 (${borderToken} on ${bgToken})`);
        }
      }
    }

    function checkInheritedBorder(borderToken: string, pos: number) {
      for (const bgToken of containerBgs) {
        checkBorderPair(bgToken, borderToken, pos);
      }
    }

    function visit(node: ts.Node) {
      if (ts.isJsxAttribute(node) && node.name.text === 'style') {
        totalStyleAttrs++;
        function findObjects(n: ts.Node) {
          if (ts.isObjectLiteralExpression(n)) {
            let bgNode: ts.Expression | null = null;
            let fgNode: ts.Expression | null = null;
            let borderNode: ts.Expression | null = null;
            for (const p of n.properties) {
              if (ts.isPropertyAssignment(p)) {
                const name = p.name.getText(sf);
                if (name === 'backgroundColor' || name === 'background') bgNode = p.initializer;
                if (name === 'color') fgNode = p.initializer;
                if (['border', 'borderColor', 'borderTop', 'borderBottom', 'borderLeft', 'borderRight'].includes(name)) {
                  borderNode = p.initializer;
                }
              }
            }
            if (bgNode && fgNode) {
              checkedObjects++;
              const bgBranches = extractBranches(bgNode);
              const fgBranches = extractBranches(fgNode);

              for (const bgB of bgBranches) {
                for (const fgB of fgBranches) {
                  if (!bgB.cond || !fgB.cond || bgB.cond === fgB.cond) {
                    checkPair(bgB.token, fgB.token, n.getStart(sf));
                  }
                }
              }
            } else if (!bgNode && fgNode) {
              unboundColorObjects++;
              const fgBranches = extractBranches(fgNode);
              for (const fgB of fgBranches) {
                checkInheritedColor(fgB.token, n.getStart(sf));
              }
            }

            if (borderNode) {
              const borderBranches = extractBranches(borderNode);
              if (borderBranches.length > 0) {
                checkedBorderObjects++;
                if (bgNode) {
                  const bgBranches = extractBranches(bgNode);
                  for (const bB of borderBranches) {
                    for (const bgB of bgBranches) {
                      if (!bB.cond || !bgB.cond || bB.cond === bgB.cond) {
                        checkBorderPair(bgB.token, bB.token, n.getStart(sf));
                      }
                    }
                  }
                } else {
                  for (const bB of borderBranches) {
                    checkInheritedBorder(bB.token, n.getStart(sf));
                  }
                }
              }
            }
          }
          ts.forEachChild(n, findObjects);
        }
        findObjects(node);
      }
      ts.forEachChild(node, visit);
    }
    visit(sf);

    // Exact ratchet assertions covering 100% of ModelLineageView style declarations
    expect(totalStyleAttrs, 'Total style attributes in ModelLineageView must be exactly 359').toBe(359);
    expect(checkedObjects, 'Style objects with explicit background and foreground must be exactly 58').toBe(58);
    expect(checkedPairs, 'Evaluated foreground-background pairs across conditional branches must be exactly 76').toBe(76);
    expect(unboundColorObjects, 'Elements with foreground color inheriting container background must be exactly 176').toBe(176);
    expect(checkedObjects + unboundColorObjects, 'Total covered color style objects must be exactly 234').toBe(234);
    expect(checkedBorderObjects, 'Style objects with explicit border token declarations must be exactly 83').toBe(83);
    expect(checkedBorderPairs, 'Evaluated border-background pairs across conditional and container branches must be exactly 122').toBe(122);
    expect(violations, `Expected 0 style-pair contrast/collision violations in ModelLineageView, got:\n${violations.join('\n')}`).toEqual([]);
  });

  // 9e. [Card 199 / ACC-09] Component DOM Rendering & Binding Verification: AdminSecurityConsole
  it('ACC-09 / Card 199: AdminSecurityConsole DOM rendering binds foregrounds and container backgrounds to design tokens with dynamic contrast verification', async () => {
    const originalFetch = globalThis.fetch;
    globalThis.fetch = vi.fn().mockImplementation((url: string) => {
      if (url.includes('/v1/operations/kill-switch')) {
        return Promise.resolve(new Response(JSON.stringify({
          nodeId: null,
          version: 5,
          killSwitchActive: false,
          nodeStatus: 'online',
          activeLeases: 0,
          pendingDeliveries: 0,
          unsettledRuns: 0,
          settled: true,
        }), { status: 200, headers: { 'Content-Type': 'application/json' } }));
      }
      return Promise.resolve(new Response(JSON.stringify({}), { status: 200, headers: { 'Content-Type': 'application/json' } }));
    });

    const container = document.createElement('div');
    container.setAttribute('data-theme', 'light');
    document.body.appendChild(container);
    const root = createRoot(container);

    try {
      await act(async () => {
        root.render(
          <AdminSecurityConsole
            nodes={[
              {
                id: 'nod_01ARZ3NDEKTSV4RRFFQ69G5FAV',
                hostname: 'node-gpu-01',
                os: 'linux',
                cpuCores: 32,
                cpuUsagePercent: 15,
                memoryTotalBytes: 128 * 1024 ** 3,
                memoryUsagePercent: 25,
                gpuName: 'NVIDIA RTX 4090',
                gpuCount: 2,
                status: 'online',
                labels: { tier: 'gpu' },
              },
            ]}
            currentUser={{ id: 'usr_sec_admin', name: 'Sec Admin', role: 'admin' }}
          />
        );
      });

      // 1. Backend kill switch status label
      const backendStatus = container.querySelector('[data-testid="backend-kill-switch-status"]') as HTMLElement;
      expect(backendStatus, 'Backend kill switch status must render').not.toBeNull();
      expect(backendStatus.style.color, 'Backend status color must bind to var(--color-text-secondary)').toBe('var(--color-text-secondary)');
      const bsFg = helperExtractVar(backendStatus.style.color);
      expect(getContrast(lightTokens[bsFg], lightTokens['--color-bg-surface']), 'Backend status light text contrast >= 4.5:1').toBeGreaterThanOrEqual(4.5);
      expect(getContrast(darkTokens[bsFg], darkTokens['--color-bg-surface']), 'Backend status dark text contrast >= 4.5:1').toBeGreaterThanOrEqual(4.5);

      // 2. Kill switch approval ID input
      const approvalInput = container.querySelector('[data-testid="input-kill-switch-approval-id"]') as HTMLInputElement;
      expect(approvalInput, 'Approval input must render').not.toBeNull();
      expect(approvalInput.style.backgroundColor, 'Approval input bg must bind to var(--color-bg-subtle)').toBe('var(--color-bg-subtle)');
      expect(approvalInput.style.color, 'Approval input text must bind to var(--color-text-primary)').toBe('var(--color-text-primary)');
      expect(approvalInput.style.borderColor, 'Approval input border must bind to var(--color-border-subtle)').toBe('var(--color-border-subtle)');
      const appInBg = helperExtractVar(approvalInput.style.backgroundColor);
      const appInFg = helperExtractVar(approvalInput.style.color);
      const appInBorder = helperExtractVar(approvalInput.style.borderColor);
      expect(getContrast(lightTokens[appInFg], lightTokens[appInBg]), 'Approval input light text contrast >= 4.5:1').toBeGreaterThanOrEqual(4.5);
      expect(getContrast(darkTokens[appInFg], darkTokens[appInBg]), 'Approval input dark text contrast >= 4.5:1').toBeGreaterThanOrEqual(4.5);
      expect(getContrast(lightTokens[appInBorder], lightTokens[appInBg]), 'Approval input light border contrast >= 3.0:1').toBeGreaterThanOrEqual(3.0);
      expect(getContrast(darkTokens[appInBorder], darkTokens[appInBg]), 'Approval input dark border contrast >= 3.0:1').toBeGreaterThanOrEqual(3.0);

      // 3. Open Kill Switch Modal
      const toggleBtn = container.querySelector('[data-testid="emergency-kill-switch-toggle-btn"]') as HTMLButtonElement;
      expect(toggleBtn, 'Emergency toggle button must render').not.toBeNull();
      await act(async () => {
        toggleBtn.click();
      });

      const modal = container.querySelector('[data-testid="kill-switch-modal"]') as HTMLElement;
      expect(modal, 'Kill switch modal overlay must render').not.toBeNull();
      expect(modal.style.backgroundColor, 'Modal backdrop must bind to var(--color-bg-backdrop)').toBe('var(--color-bg-backdrop)');

      // T2 Scrim Alpha & Surface Boundary Contrast Invariants
      const lightBackdropVal = lightTokens['--color-bg-backdrop'];
      const darkBackdropVal = darkTokens['--color-bg-backdrop'];
      const lightBackdropParsed = parseRgba(lightBackdropVal);
      const darkBackdropParsed = parseRgba(darkBackdropVal);
      expect(lightBackdropParsed, 'Light backdrop must be rgba format').not.toBeNull();
      expect(darkBackdropParsed, 'Dark backdrop must be rgba format').not.toBeNull();
      expect(lightBackdropParsed!.a, 'Light backdrop alpha must be at least 0.50 (rejecting washed-out scrim)').toBeGreaterThanOrEqual(0.5);
      expect(darkBackdropParsed!.a, 'Dark backdrop alpha must be at least 0.50 (rejecting washed-out scrim)').toBeGreaterThanOrEqual(0.5);

      // Scrim composite contrast: Modal card surface on composite scrim backdrop must maintain >= 3.0:1 UI boundary contrast
      const lightScrimComposite = blendRgba(lightBackdropParsed!.rgb, lightBackdropParsed!.a, lightTokens['--color-bg-canvas']);
      const modalSurfaceLightCr = getContrast(lightTokens['--color-bg-surface'], lightScrimComposite);
      expect(modalSurfaceLightCr, 'Modal card surface on light scrim backdrop must maintain >= 3.0:1 boundary contrast').toBeGreaterThanOrEqual(3.0);

      const modalTitle = container.querySelector('#kill-switch-modal-title') as HTMLElement;
      expect(modalTitle, 'Modal title must render').not.toBeNull();
      expect(modalTitle.style.color, 'Modal title color must bind to var(--color-status-offline)').toBe('var(--color-status-offline)');
      const mtFg = helperExtractVar(modalTitle.style.color);
      expect(getContrast(lightTokens[mtFg], lightTokens['--color-bg-surface']), 'Modal title light text contrast >= 4.5:1').toBeGreaterThanOrEqual(4.5);
      expect(getContrast(darkTokens[mtFg], darkTokens['--color-bg-surface']), 'Modal title dark text contrast >= 4.5:1').toBeGreaterThanOrEqual(4.5);

      // 4. Kill switch approval required notice
      const appNotice = container.querySelector('[data-testid="kill-switch-approval-required-notice"]') as HTMLElement;
      expect(appNotice, 'Approval required notice must render').not.toBeNull();
      expect(appNotice.style.backgroundColor, 'Notice bg must bind to var(--color-bg-subtle)').toBe('var(--color-bg-subtle)');
      expect(appNotice.style.color, 'Notice text must bind to var(--color-status-offline)').toBe('var(--color-status-offline)');
      expect(appNotice.style.borderColor, 'Notice border must bind to var(--color-status-offline)').toBe('var(--color-status-offline)');
      const anBg = helperExtractVar(appNotice.style.backgroundColor);
      const anFg = helperExtractVar(appNotice.style.color);
      const anBorder = helperExtractVar(appNotice.style.borderColor);
      expect(getContrast(lightTokens[anFg], lightTokens[anBg]), 'Notice light text contrast >= 4.5:1').toBeGreaterThanOrEqual(4.5);
      expect(getContrast(darkTokens[anFg], darkTokens[anBg]), 'Notice dark text contrast >= 4.5:1').toBeGreaterThanOrEqual(4.5);
      expect(getContrast(lightTokens[anBorder], lightTokens[anBg]), 'Notice light border contrast >= 3.0:1').toBeGreaterThanOrEqual(3.0);
      expect(getContrast(darkTokens[anBorder], darkTokens[anBg]), 'Notice dark border contrast >= 3.0:1').toBeGreaterThanOrEqual(3.0);

      // 5. Kill switch mock notice
      const mockNotice = container.querySelector('[data-testid="kill-switch-mock-notice"]') as HTMLElement;
      expect(mockNotice, 'Mock notice must render').not.toBeNull();
      expect(mockNotice.style.backgroundColor, 'Mock notice bg must bind to var(--color-bg-subtle)').toBe('var(--color-bg-subtle)');
      expect(mockNotice.style.color, 'Mock notice text must bind to var(--color-status-degraded)').toBe('var(--color-status-degraded)');
      expect(mockNotice.style.borderColor, 'Mock notice border must bind to var(--color-status-degraded)').toBe('var(--color-status-degraded)');
      const mnBg = helperExtractVar(mockNotice.style.backgroundColor);
      const mnFg = helperExtractVar(mockNotice.style.color);
      const mnBorder = helperExtractVar(mockNotice.style.borderColor);
      expect(getContrast(lightTokens[mnFg], lightTokens[mnBg]), 'Mock notice light text contrast >= 4.5:1').toBeGreaterThanOrEqual(4.5);
      expect(getContrast(darkTokens[mnFg], darkTokens[mnBg]), 'Mock notice dark text contrast >= 4.5:1').toBeGreaterThanOrEqual(4.5);
      expect(getContrast(lightTokens[mnBorder], lightTokens[mnBg]), 'Mock notice light border contrast >= 3.0:1').toBeGreaterThanOrEqual(3.0);
      expect(getContrast(darkTokens[mnBorder], darkTokens[mnBg]), 'Mock notice dark border contrast >= 3.0:1').toBeGreaterThanOrEqual(3.0);

      // 6. Kill switch params summary
      const paramsSummary = container.querySelector('[data-testid="kill-switch-params-summary"]') as HTMLElement;
      expect(paramsSummary, 'Params summary must render').not.toBeNull();
      expect(paramsSummary.style.backgroundColor, 'Params summary bg must bind to var(--color-bg-subtle)').toBe('var(--color-bg-subtle)');
      expect(paramsSummary.style.borderColor, 'Params summary border must bind to var(--color-border-subtle)').toBe('var(--color-border-subtle)');
      const psBg = helperExtractVar(paramsSummary.style.backgroundColor);
      const psBorder = helperExtractVar(paramsSummary.style.borderColor);
      expect(getContrast(lightTokens[psBorder], lightTokens[psBg]), 'Params summary light border contrast >= 3.0:1').toBeGreaterThanOrEqual(3.0);
      expect(getContrast(darkTokens[psBorder], darkTokens[psBg]), 'Params summary dark border contrast >= 3.0:1').toBeGreaterThanOrEqual(3.0);

      // 6b. Admin Audit Sub-tab Container (T1 ancestor container background & border binding)
      const auditContainer = container.querySelector('[data-testid="admin-audit-subtab-container"]') as HTMLElement;
      expect(auditContainer, 'Audit container must render in default audit sub-tab').not.toBeNull();
      expect(auditContainer.style.backgroundColor, 'Audit container bg must bind to var(--color-bg-surface)').toBe('var(--color-bg-surface)');
      expect(auditContainer.style.borderColor, 'Audit container border must bind to var(--color-border-subtle)').toBe('var(--color-border-subtle)');
      const acBg = helperExtractVar(auditContainer.style.backgroundColor);
      const acBorder = helperExtractVar(auditContainer.style.borderColor);
      expect(getContrast(lightTokens[acBorder], lightTokens[acBg]), 'Audit container light border contrast >= 3.0:1').toBeGreaterThanOrEqual(3.0);
      expect(getContrast(darkTokens[acBorder], darkTokens[acBg]), 'Audit container dark border contrast >= 3.0:1').toBeGreaterThanOrEqual(3.0);

      // 7. Unauthenticated Admin Notice (render with currentUser=null)
      await act(async () => {
        root.render(<AdminSecurityConsole nodes={[]} currentUser={null} />);
      });
      const authNotice = container.querySelector('[data-testid="admin-auth-required-notice"]') as HTMLElement;
      expect(authNotice, 'Admin auth required notice must render').not.toBeNull();
      expect(authNotice.style.backgroundColor, 'Auth notice bg must bind to var(--color-bg-subtle)').toBe('var(--color-bg-subtle)');
      expect(authNotice.style.color, 'Auth notice text must bind to var(--color-status-offline)').toBe('var(--color-status-offline)');
      expect(authNotice.style.borderColor, 'Auth notice border must bind to var(--color-status-offline)').toBe('var(--color-status-offline)');
      const aunBg = helperExtractVar(authNotice.style.backgroundColor);
      const aunFg = helperExtractVar(authNotice.style.color);
      const aunBorder = helperExtractVar(authNotice.style.borderColor);
      expect(getContrast(lightTokens[aunFg], lightTokens[aunBg]), 'Auth notice light text contrast >= 4.5:1').toBeGreaterThanOrEqual(4.5);
      expect(getContrast(darkTokens[aunFg], darkTokens[aunBg]), 'Auth notice dark text contrast >= 4.5:1').toBeGreaterThanOrEqual(4.5);
      expect(getContrast(lightTokens[aunBorder], lightTokens[aunBg]), 'Auth notice light border contrast >= 3.0:1').toBeGreaterThanOrEqual(3.0);
      expect(getContrast(darkTokens[aunBorder], darkTokens[aunBg]), 'Auth notice dark border contrast >= 3.0:1').toBeGreaterThanOrEqual(3.0);
    } finally {
      globalThis.fetch = originalFetch;
      act(() => {
        root.unmount();
      });
      container.remove();
    }
  });

  // 9e-2. [Card 199 / ACC-09] Dynamic AST Style-Pair Contrast Calculator & Strict Coverage Ratchet: AdminSecurityConsole
  it('ACC-09 / Card 199: AdminSecurityConsole style objects maintain valid contrast pairings and reject 1:1 collisions and defective combinations', () => {
    const filePath = path.resolve(__dirname, '../src/features/admin/AdminSecurityConsole.tsx');
    const content = fs.readFileSync(filePath, 'utf-8');
    const sf = ts.createSourceFile('AdminSecurityConsole.tsx', content, ts.ScriptTarget.Latest, true, ts.ScriptKind.TSX);

    interface Branch {
      cond: string;
      token: string;
    }

    function extractBranches(node: ts.Node): Branch[] {
      const branches: Branch[] = [];
      function collect(n: ts.Node, condPath: string) {
        if (ts.isConditionalExpression(n)) {
          const condText = n.condition.getText(sf).replace(/\s+/g, ' ');
          collect(n.whenTrue, condPath ? `${condPath} && ${condText}` : condText);
          collect(n.whenFalse, condPath ? `${condPath} && !(${condText})` : `!(${condText})`);
        } else if (ts.isTemplateExpression(n)) {
          for (const span of n.templateSpans) {
            collect(span.expression, condPath);
          }
        } else {
          const text = n.getText(sf);
          const m = text.match(/var\((--color-[a-z0-9-]+)\)/);
          if (m) {
            branches.push({ cond: condPath, token: m[1] });
          }
        }
      }
      collect(node, '');
      return branches;
    }

    let checkedPairs = 0;
    let checkedObjects = 0;
    let totalStyleAttrs = 0;
    let unboundColorObjects = 0;
    let checkedBorderObjects = 0;
    let checkedBorderPairs = 0;
    const violations: string[] = [];
    const containerBgs = ['--color-bg-surface', '--color-bg-subtle', '--color-bg-canvas'];

    function checkPair(bgToken: string, fgToken: string, pos: number) {
      checkedPairs++;
      const { line } = sf.getLineAndCharacterOfPosition(pos);
      const lightBg = resolveTokenHex(bgToken, lightTokens);
      const lightFg = resolveTokenHex(fgToken, lightTokens);
      const darkBg = resolveTokenHex(bgToken, darkTokens);
      const darkFg = resolveTokenHex(fgToken, darkTokens);

      if (bgToken === fgToken) {
        violations.push(`L${line + 1}: 1:1 token collision between background and foreground (${bgToken})`);
        return;
      }

      if (bgToken.startsWith('--color-text-')) {
        violations.push(`L${line + 1}: Illegitimate background token derived from text token: ${bgToken}`);
        return;
      }

      if (lightBg && lightFg) {
        const cr = getContrast(lightFg, lightBg);
        if (cr < 4.5) {
          violations.push(`L${line + 1}: Light text contrast ${cr.toFixed(2)}:1 < 4.5:1 (${fgToken} on ${bgToken})`);
        }
      }
      if (darkBg && darkFg) {
        const cr = getContrast(darkFg, darkBg);
        if (cr < 4.5) {
          violations.push(`L${line + 1}: Dark text contrast ${cr.toFixed(2)}:1 < 4.5:1 (${fgToken} on ${bgToken})`);
        }
      }
    }

    function checkBorderPair(bgToken: string, borderToken: string, pos: number) {
      checkedBorderPairs++;
      const { line } = sf.getLineAndCharacterOfPosition(pos);
      const lBg = resolveTokenHex(bgToken, lightTokens);
      const dBg = resolveTokenHex(bgToken, darkTokens);
      const lBorder = resolveTokenHex(borderToken, lightTokens);
      const dBorder = resolveTokenHex(borderToken, darkTokens);

      if (bgToken === borderToken) {
        violations.push(`L${line + 1}: Identical border-background token collision (1:1 contrast) detected: ${borderToken} on ${bgToken}`);
        return;
      }

      if (bgToken.startsWith('--color-text-')) {
        violations.push(`L${line + 1}: Illegitimate background token derived from text token: ${bgToken}`);
        return;
      }

      if (lBg && lBorder) {
        const cr = getContrast(lBorder, lBg);
        if (cr < 3.0) {
          violations.push(`L${line + 1}: Light border contrast ${cr.toFixed(2)}:1 < 3.0:1 (${borderToken} on ${bgToken})`);
        }
      }
      if (dBg && dBorder) {
        const cr = getContrast(dBorder, dBg);
        if (cr < 3.0) {
          violations.push(`L${line + 1}: Dark border contrast ${cr.toFixed(2)}:1 < 3.0:1 (${borderToken} on ${bgToken})`);
        }
      }
    }

    function traverseJsx(node: ts.Node, ancestorBgTokens: string[]) {
      let currentBgTokens = ancestorBgTokens;

      if (ts.isJsxElement(node) || ts.isJsxSelfClosingElement(node)) {
        const opening = ts.isJsxElement(node) ? node.openingElement : node;
        const attrs = opening.attributes?.properties || [];
        let styleObj: ts.ObjectLiteralExpression | null = null;

        for (const attr of attrs) {
          if (ts.isJsxAttribute(attr) && attr.name.text === 'style') {
            totalStyleAttrs++;
            if (attr.initializer && ts.isJsxExpression(attr.initializer) && attr.initializer.expression && ts.isObjectLiteralExpression(attr.initializer.expression)) {
              styleObj = attr.initializer.expression;
            }
          }
        }

        if (styleObj) {
          let bgNode: ts.Expression | null = null;
          let fgNode: ts.Expression | null = null;
          let borderNode: ts.Expression | null = null;
          for (const p of styleObj.properties) {
            if (ts.isPropertyAssignment(p)) {
              const name = p.name.getText(sf);
              if (name === 'backgroundColor' || name === 'background') bgNode = p.initializer;
              if (name === 'color') fgNode = p.initializer;
              if (['border', 'borderColor', 'borderTop', 'borderBottom', 'borderLeft', 'borderRight'].includes(name)) {
                borderNode = p.initializer;
              }
            }
          }

          const bgBranches = bgNode ? extractBranches(bgNode) : [];
          if (bgBranches.length > 0) {
            currentBgTokens = bgBranches.map(b => b.token);
            for (const b of bgBranches) {
              if (b.token.startsWith('--color-text-')) {
                const { line } = sf.getLineAndCharacterOfPosition(bgNode!.getStart(sf));
                violations.push(`L${line + 1}: Illegitimate background token derived from text token: ${b.token}`);
              }
            }
          }

          if (bgNode && fgNode) {
            checkedObjects++;
            const fgBranches = extractBranches(fgNode);
            for (const bgB of bgBranches) {
              for (const fgB of fgBranches) {
                if (!bgB.cond || !fgB.cond || bgB.cond === fgB.cond) {
                  checkPair(bgB.token, fgB.token, styleObj.getStart(sf));
                }
              }
            }
          } else if (!bgNode && fgNode) {
            unboundColorObjects++;
            const fgBranches = extractBranches(fgNode);
            const effectiveBgs = ancestorBgTokens.length > 0 ? ancestorBgTokens : containerBgs;
            for (const fgB of fgBranches) {
              for (const cBg of effectiveBgs) {
                checkPair(cBg, fgB.token, styleObj.getStart(sf));
              }
            }
          }

          if (borderNode) {
            const borderBranches = extractBranches(borderNode);
            if (borderBranches.length > 0) {
              checkedBorderObjects++;
              if (bgNode) {
                for (const bB of borderBranches) {
                  for (const bgB of bgBranches) {
                    if (!bB.cond || !bgB.cond || bB.cond === bgB.cond) {
                      checkBorderPair(bgB.token, bB.token, styleObj.getStart(sf));
                    }
                  }
                }
              } else {
                const effectiveBgs = ancestorBgTokens.length > 0 ? ancestorBgTokens : containerBgs;
                for (const bB of borderBranches) {
                  for (const cBg of effectiveBgs) {
                    checkBorderPair(cBg, bB.token, styleObj.getStart(sf));
                  }
                }
              }
            }
          }
        }
      }

      ts.forEachChild(node, child => traverseJsx(child, currentBgTokens));
    }

    traverseJsx(sf, []);

    // Exact ratchet assertions covering 100% of AdminSecurityConsole style declarations
    expect(totalStyleAttrs, 'Total style attributes in AdminSecurityConsole must be exactly 142').toBe(142);
    expect(checkedObjects, 'Style objects with explicit background and foreground must be exactly 21').toBe(21);
    expect(checkedPairs, 'Evaluated foreground-background pairs across conditional branches must be exactly 98').toBe(98);
    expect(unboundColorObjects, 'Elements with foreground color inheriting container background must be exactly 71').toBe(71);
    expect(checkedObjects + unboundColorObjects, 'Total covered color style objects must be exactly 92').toBe(92);
    expect(checkedBorderObjects, 'Style objects with explicit border token declarations must be exactly 42').toBe(42);
    expect(checkedBorderPairs, 'Evaluated border-background pairs across conditional and container branches must be exactly 48').toBe(48);
    expect(violations, `Expected 0 style-pair contrast/collision violations in AdminSecurityConsole, got:\n${violations.join('\n')}`).toEqual([]);
  });

  // 9f. [Card 202 / ACC-09] Component DOM Rendering & Binding Verification: IntranetDeploymentView
  it('ACC-09 / Card 202: IntranetDeploymentView DOM rendering binds foregrounds and container backgrounds to design tokens with dynamic contrast verification', async () => {
    const strictManifestItem: ReleaseManifestResponse = {
      releaseId: 'rel_01ARZ3NDEKTSV4RRFFQ69G5FAV',
      version: 'v1.4.0',
      manifestSha256: '1234567890abcdef1234567890abcdef1234567890abcdef1234567890abcdef',
      createdAt: '2026-10-02T00:00:00Z',
      componentCount: 1,
      components: [{ name: 'web', kind: 'frontend', digest: 'sha256:fedcba0987654321fedcba0987654321fedcba0987654321fedcba0987654321' }],
      confirmedOperatorCount: 0,
      requiredDistinctOperatorCount: 2,
      matchingAcceptedUserCount: 2,
      acceptanceCount: 1,
      operatorSignOff: false,
      operatorSignOffBlockedBy: 'release-acceptance-prerequisites-unavailable',
    };

    const strictDetailFixture: ReleaseManifestDetailResponse = {
      release: strictManifestItem,
      acceptances: [
        {
          acceptanceId: 'acc_01',
          acceptanceIdRef: 'ref_01',
          acceptedManifestSha256: '1234567890abcdef1234567890abcdef1234567890abcdef1234567890abcdef',
          decidedAt: '2026-10-02T00:00:00Z',
          knownLimitations: [],
          manifestMatches: true,
          outcome: 'accepted',
        },
      ],
    };

    const originalFetch = globalThis.fetch;
    globalThis.fetch = vi.fn().mockImplementation((url: string) => {
      if (url.includes('/v1/release-manifests')) {
        return Promise.resolve(new Response(JSON.stringify({
          items: [strictManifestItem],
          nextCursor: null,
        }), { status: 200, headers: { 'Content-Type': 'application/json' } }));
      }
      return Promise.resolve(new Response(JSON.stringify({}), { status: 200, headers: { 'Content-Type': 'application/json' } }));
    });

    const container = document.createElement('div');
    container.setAttribute('data-theme', 'light');
    document.body.appendChild(container);
    const root = createRoot(container);

    try {
      await act(async () => {
        root.render(
          <IntranetDeploymentView
            currentUser={{ id: 'usr_deployer', name: 'Deployer', role: 'operator' }}
            autoFetch={false}
            initialManifests={[strictManifestItem]}
            initialDetail={strictDetailFixture}
            clusterNodes={[
              {
                id: 'nod_01ARZ3NDEKTSV4RRFFQ69G5FAV',
                hostname: 'node-win-01',
                os: 'windows',
                cpuCores: 16,
                cpuUsagePercent: 20,
                memoryTotalBytes: 64 * 1024 ** 3,
                memoryUsagePercent: 30,
                gpuName: null,
                gpuCount: 0,
                status: 'online',
                labels: {},
              },
            ]}
          />
        );
      });

      // 1. Unexposed Notice Banner
      const unexpNotice = container.querySelector('[data-testid="deployment-unexposed-notice"]') as HTMLElement;
      expect(unexpNotice, 'Unexposed notice must render').not.toBeNull();
      expect(unexpNotice.style.backgroundColor, 'Notice bg must bind to var(--color-bg-subtle)').toBe('var(--color-bg-subtle)');
      expect(unexpNotice.style.color, 'Notice text must bind to var(--color-brand-hover)').toBe('var(--color-brand-hover)');
      expect(unexpNotice.style.borderBottomColor, 'Notice border must bind to var(--color-border-subtle)').toBe('var(--color-border-subtle)');
      const unBg = helperExtractVar(unexpNotice.style.backgroundColor);
      const unFg = helperExtractVar(unexpNotice.style.color);
      const unBorder = helperExtractVar(unexpNotice.style.borderBottomColor);
      expect(getContrast(lightTokens[unFg], lightTokens[unBg]), 'Unexposed notice light text contrast >= 4.5:1').toBeGreaterThanOrEqual(4.5);
      expect(getContrast(darkTokens[unFg], darkTokens[unBg]), 'Unexposed notice dark text contrast >= 4.5:1').toBeGreaterThanOrEqual(4.5);
      expect(getContrast(lightTokens[unBorder], lightTokens[unBg]), 'Unexposed notice light border contrast >= 3.0:1').toBeGreaterThanOrEqual(3.0);
      expect(getContrast(darkTokens[unBorder], darkTokens[unBg]), 'Unexposed notice dark border contrast >= 3.0:1').toBeGreaterThanOrEqual(3.0);

      // 2. Server Manifest Banner
      const serverBanner = container.querySelector('[data-testid="deployment-manifest-server-banner"]') as HTMLElement;
      expect(serverBanner, 'Server banner must render').not.toBeNull();
      expect(serverBanner.style.backgroundColor, 'Server banner bg must bind to var(--color-bg-subtle)').toBe('var(--color-bg-subtle)');
      expect(serverBanner.style.color, 'Server banner text must bind to var(--color-brand-hover)').toBe('var(--color-brand-hover)');
      expect(serverBanner.style.borderColor, 'Server banner border must bind to var(--color-brand-hover)').toBe('var(--color-brand-hover)');
      const sbBg = helperExtractVar(serverBanner.style.backgroundColor);
      const sbFg = helperExtractVar(serverBanner.style.color);
      const sbBorder = helperExtractVar(serverBanner.style.borderColor);
      expect(getContrast(lightTokens[sbFg], lightTokens[sbBg]), 'Server banner light text contrast >= 4.5:1').toBeGreaterThanOrEqual(4.5);
      expect(getContrast(darkTokens[sbFg], darkTokens[sbBg]), 'Server banner dark text contrast >= 4.5:1').toBeGreaterThanOrEqual(4.5);
      expect(getContrast(lightTokens[sbBorder], lightTokens[sbBg]), 'Server banner light border contrast >= 3.0:1').toBeGreaterThanOrEqual(3.0);
      expect(getContrast(darkTokens[sbBorder], darkTokens[sbBg]), 'Server banner dark border contrast >= 3.0:1').toBeGreaterThanOrEqual(3.0);

      // 3. Server Release Version
      const srvVer = container.querySelector('[data-testid="server-release-version"]') as HTMLElement;
      expect(srvVer, 'Server release version must render').not.toBeNull();
      expect(srvVer.style.color, 'Server release version must bind to var(--color-brand-hover)').toBe('var(--color-brand-hover)');
      const svFg = helperExtractVar(srvVer.style.color);
      expect(getContrast(lightTokens[svFg], lightTokens['--color-bg-subtle']), 'Server release version light text contrast >= 4.5:1').toBeGreaterThanOrEqual(4.5);
      expect(getContrast(darkTokens[svFg], darkTokens['--color-bg-subtle']), 'Server release version dark text contrast >= 4.5:1').toBeGreaterThanOrEqual(4.5);

      // 4. Server Acceptance Count
      const accCount = container.querySelector('[data-testid="server-acceptance-count"]') as HTMLElement;
      expect(accCount, 'Server acceptance count must render').not.toBeNull();
      expect(accCount.style.color, 'Server acceptance count must bind to var(--color-text-primary)').toBe('var(--color-text-primary)');
      const acFg = helperExtractVar(accCount.style.color);
      expect(getContrast(lightTokens[acFg], lightTokens['--color-bg-subtle']), 'Server acceptance count light text contrast >= 4.5:1').toBeGreaterThanOrEqual(4.5);
      expect(getContrast(darkTokens[acFg], darkTokens['--color-bg-subtle']), 'Server acceptance count dark text contrast >= 4.5:1').toBeGreaterThanOrEqual(4.5);

      // 5. #281 Status & Quorum Observability Binding (U2 & C1: strict schema & token pinning)
      const opSignoff = container.querySelector('[data-testid="server-operator-signoff"]') as HTMLElement;
      expect(opSignoff, 'Server operator signoff container must render').not.toBeNull();
      const signoffSpan = opSignoff.querySelector('span') as HTMLElement;
      expect(signoffSpan, 'Unconfirmed signoff badge must render').not.toBeNull();
      expect(signoffSpan.style.color, 'Unconfirmed signoff badge must bind to var(--color-status-degraded)').toBe('var(--color-status-degraded)');
      expect(signoffSpan.textContent).toContain('미서명 (operatorSignOff: false)');
      const soFg = helperExtractVar(signoffSpan.style.color);
      expect(getContrast(lightTokens[soFg], lightTokens['--color-bg-subtle']), 'Signoff light text contrast >= 4.5:1').toBeGreaterThanOrEqual(4.5);
      expect(getContrast(darkTokens[soFg], darkTokens['--color-bg-subtle']), 'Signoff dark text contrast >= 4.5:1').toBeGreaterThanOrEqual(4.5);

      const blockedBy = container.querySelector('[data-testid="server-operator-signoff-blocked-by"]') as HTMLElement;
      expect(blockedBy, 'Signoff blocked by notice must render').not.toBeNull();
      expect(blockedBy.style.color, 'Signoff blocked by must bind to var(--color-text-secondary)').toBe('var(--color-text-secondary)');
      expect(blockedBy.textContent).toContain('release-acceptance-prerequisites-unavailable');
      const bbFg = helperExtractVar(blockedBy.style.color);
      expect(getContrast(lightTokens[bbFg], lightTokens['--color-bg-subtle']), 'BlockedBy light text contrast >= 4.5:1').toBeGreaterThanOrEqual(4.5);
      expect(getContrast(darkTokens[bbFg], darkTokens['--color-bg-subtle']), 'BlockedBy dark text contrast >= 4.5:1').toBeGreaterThanOrEqual(4.5);

      const quorum = container.querySelector('[data-testid="server-operator-quorum"]') as HTMLElement;
      expect(quorum, 'Quorum status container must render').not.toBeNull();
      const quorumSpan = quorum.querySelector('span') as HTMLElement;
      expect(quorumSpan, 'Quorum headline must render').not.toBeNull();
      expect(quorumSpan.style.color, 'Quorum headline must bind to var(--color-text-primary)').toBe('var(--color-text-primary)');
      expect(quorumSpan.textContent).toContain('사람 확인 0 / 2 (서명 아님)');
      const qFg = helperExtractVar(quorumSpan.style.color);
      expect(getContrast(lightTokens[qFg], lightTokens['--color-bg-subtle']), 'Quorum light text contrast >= 4.5:1').toBeGreaterThanOrEqual(4.5);
      expect(getContrast(darkTokens[qFg], darkTokens['--color-bg-subtle']), 'Quorum dark text contrast >= 4.5:1').toBeGreaterThanOrEqual(4.5);

      const matchingUsers = container.querySelector('[data-testid="server-matching-user-count"]') as HTMLElement;
      expect(matchingUsers, 'Matching user count notice must render').not.toBeNull();
      expect(matchingUsers.style.color, 'Matching users must bind to var(--color-text-secondary)').toBe('var(--color-text-secondary)');
      expect(matchingUsers.textContent).toContain('해시 일치 수락 기록 2건 (사람 확인 아님)');
      const muFg = helperExtractVar(matchingUsers.style.color);
      expect(getContrast(lightTokens[muFg], lightTokens['--color-bg-subtle']), 'Matching users light text contrast >= 4.5:1').toBeGreaterThanOrEqual(4.5);
      expect(getContrast(darkTokens[muFg], darkTokens['--color-bg-subtle']), 'Matching users dark text contrast >= 4.5:1').toBeGreaterThanOrEqual(4.5);

      // 6. Unauthenticated Notice (render with currentUser=null)
      await act(async () => {
        root.render(<IntranetDeploymentView currentUser={null} autoFetch={false} />);
      });
      const authNotice = container.querySelector('[data-testid="deployment-auth-required-notice"]') as HTMLElement;
      expect(authNotice, 'Deployment auth required notice must render').not.toBeNull();
      expect(authNotice.style.backgroundColor, 'Notice bg must bind to var(--color-bg-subtle)').toBe('var(--color-bg-subtle)');
      expect(authNotice.style.color, 'Notice text must bind to var(--color-status-offline)').toBe('var(--color-status-offline)');
      expect(authNotice.style.borderColor, 'Notice border must bind to var(--color-status-offline)').toBe('var(--color-status-offline)');
      const anBg = helperExtractVar(authNotice.style.backgroundColor);
      const anFg = helperExtractVar(authNotice.style.color);
      const anBorder = helperExtractVar(authNotice.style.borderColor);
      expect(getContrast(lightTokens[anFg], lightTokens[anBg]), 'Auth notice light text contrast >= 4.5:1').toBeGreaterThanOrEqual(4.5);
      expect(getContrast(darkTokens[anFg], darkTokens[anBg]), 'Auth notice dark text contrast >= 4.5:1').toBeGreaterThanOrEqual(4.5);
      expect(getContrast(lightTokens[anBorder], lightTokens[anBg]), 'Auth notice light border contrast >= 3.0:1').toBeGreaterThanOrEqual(3.0);
      expect(getContrast(darkTokens[anBorder], darkTokens[anBg]), 'Auth notice dark border contrast >= 3.0:1').toBeGreaterThanOrEqual(3.0);

      // 7. Contract Violation Error Alert State (#281 Status & Alert Verification)
      vi.spyOn(globalThis, 'fetch').mockResolvedValueOnce({
        ok: true,
        status: 200,
        headers: new Headers({ 'Content-Type': 'application/json' }),
        json: async () => ({
          items: [{ ...strictManifestItem, operatorSignOff: true }], // breach contract
          nextCursor: null,
        }),
      } as Response);

      await act(async () => {
        root.render(<IntranetDeploymentView currentUser={{ id: 'usr_deployer', name: 'Deployer', role: 'operator' }} autoFetch={true} />);
      });

      const contractAlert = container.querySelector('[data-testid="deployment-manifest-error-contract"]') as HTMLElement;
      expect(contractAlert, 'Contract violation alert must render').not.toBeNull();
      expect(contractAlert.getAttribute('role'), 'Contract alert role must be alert').toBe('alert');
      expect(contractAlert.style.backgroundColor, 'Contract alert bg must bind to var(--color-bg-subtle)').toBe('var(--color-bg-subtle)');
      expect(contractAlert.style.color, 'Contract alert text must bind to var(--color-status-offline)').toBe('var(--color-status-offline)');
      expect(contractAlert.style.borderColor, 'Contract alert border must bind to var(--color-status-offline)').toBe('var(--color-status-offline)');
      expect(contractAlert.textContent).toContain('계약 위반 응답: 잘못된 서버 응답 규격');
      expect(contractAlert.textContent).toContain('CONTRACT-VIOLATION');
      const cBg = helperExtractVar(contractAlert.style.backgroundColor);
      const cFg = helperExtractVar(contractAlert.style.color);
      const cBorder = helperExtractVar(contractAlert.style.borderColor);
      expect(getContrast(lightTokens[cFg], lightTokens[cBg]), 'Contract alert light text contrast >= 4.5:1').toBeGreaterThanOrEqual(4.5);
      expect(getContrast(darkTokens[cFg], darkTokens[cBg]), 'Contract alert dark text contrast >= 4.5:1').toBeGreaterThanOrEqual(4.5);
      expect(getContrast(lightTokens[cBorder], lightTokens[cBg]), 'Contract alert light border contrast >= 3.0:1').toBeGreaterThanOrEqual(3.0);
      expect(getContrast(darkTokens[cBorder], darkTokens[cBg]), 'Contract alert dark border contrast >= 3.0:1').toBeGreaterThanOrEqual(3.0);
    } finally {
      globalThis.fetch = originalFetch;
      act(() => {
        root.unmount();
      });
      container.remove();
    }
  });

  // 9f-2. [Card 202 / ACC-09] Dynamic AST Style-Pair Contrast Calculator & Strict Coverage Ratchet: IntranetDeploymentView
  it('ACC-09 / Card 202: IntranetDeploymentView style objects maintain valid contrast pairings and reject 1:1 collisions and defective combinations', () => {
    const filePath = path.resolve(__dirname, '../src/features/deployment/IntranetDeploymentView.tsx');
    const content = fs.readFileSync(filePath, 'utf-8');
    const sf = ts.createSourceFile('IntranetDeploymentView.tsx', content, ts.ScriptTarget.Latest, true, ts.ScriptKind.TSX);

    interface Branch {
      cond: string;
      token: string;
    }

    function extractBranches(node: ts.Node): Branch[] {
      const branches: Branch[] = [];
      function collect(n: ts.Node, condPath: string) {
        if (ts.isConditionalExpression(n)) {
          const condText = n.condition.getText(sf).replace(/\s+/g, ' ');
          collect(n.whenTrue, condPath ? `${condPath} && ${condText}` : condText);
          collect(n.whenFalse, condPath ? `${condPath} && !(${condText})` : `!(${condText})`);
        } else if (ts.isTemplateExpression(n)) {
          for (const span of n.templateSpans) {
            collect(span.expression, condPath);
          }
        } else {
          const text = n.getText(sf);
          const m = text.match(/var\((--color-[a-z0-9-]+)\)/);
          if (m) {
            branches.push({ cond: condPath, token: m[1] });
          }
        }
      }
      collect(node, '');
      return branches;
    }

    function extractOpacity(node: ts.Node): number | null {
      if (ts.isNumericLiteral(node)) return parseFloat(node.text);
      if (ts.isConditionalExpression(node)) {
        const trueOp = extractOpacity(node.whenTrue);
        const falseOp = extractOpacity(node.whenFalse);
        if (trueOp !== null && falseOp !== null) return Math.min(trueOp, falseOp);
        return trueOp ?? falseOp;
      }
      return null;
    }

    let checkedPairs = 0;
    let checkedObjects = 0;
    let totalStyleAttrs = 0;
    let unboundColorObjects = 0;
    let checkedBorderObjects = 0;
    let checkedBorderPairs = 0;
    const violations: string[] = [];
    const containerBgs = ['--color-bg-surface', '--color-bg-subtle', '--color-bg-canvas'];

    function checkPair(bgToken: string, fgToken: string, pos: number, opacity: number = 1.0) {
      checkedPairs++;
      const { line } = sf.getLineAndCharacterOfPosition(pos);
      const lightBg = resolveTokenHex(bgToken, lightTokens);
      const lightFg = resolveTokenHex(fgToken, lightTokens);
      const darkBg = resolveTokenHex(bgToken, darkTokens);
      const darkFg = resolveTokenHex(fgToken, darkTokens);

      if (bgToken === fgToken && opacity >= 1.0) {
        violations.push(`L${line + 1}: 1:1 token collision between background and foreground (${bgToken})`);
        return;
      }

      if (bgToken.startsWith('--color-text-')) {
        violations.push(`L${line + 1}: Illegitimate background token derived from text token: ${bgToken}`);
        return;
      }

      const effectiveLFg = opacity < 1.0 && lightBg && lightFg ? blendRgba(parseHex(lightFg), opacity, lightBg) : lightFg;
      const effectiveDFg = opacity < 1.0 && darkBg && darkFg ? blendRgba(parseHex(darkFg), opacity, darkBg) : darkFg;

      if (lightBg && effectiveLFg) {
        const cr = getContrast(effectiveLFg, lightBg);
        if (cr < 4.5) {
          violations.push(`L${line + 1}: Light text contrast ${cr.toFixed(2)}:1 < 4.5:1 (${fgToken} on ${bgToken}${opacity < 1.0 ? ` opacity ${opacity.toFixed(2)}` : ''})`);
        }
      }
      if (darkBg && effectiveDFg) {
        const cr = getContrast(effectiveDFg, darkBg);
        if (cr < 4.5) {
          violations.push(`L${line + 1}: Dark text contrast ${cr.toFixed(2)}:1 < 4.5:1 (${fgToken} on ${bgToken}${opacity < 1.0 ? ` opacity ${opacity.toFixed(2)}` : ''})`);
        }
      }
    }

    function checkBorderPair(bgToken: string, borderToken: string, pos: number, opacity: number = 1.0) {
      checkedBorderPairs++;
      const { line } = sf.getLineAndCharacterOfPosition(pos);
      const lBg = resolveTokenHex(bgToken, lightTokens);
      const dBg = resolveTokenHex(bgToken, darkTokens);
      const lBorder = resolveTokenHex(borderToken, lightTokens);
      const dBorder = resolveTokenHex(borderToken, darkTokens);

      if (bgToken === borderToken && opacity >= 1.0) {
        violations.push(`L${line + 1}: Identical border-background token collision (1:1 contrast) detected: ${borderToken} on ${bgToken}`);
        return;
      }

      if (bgToken.startsWith('--color-text-')) {
        violations.push(`L${line + 1}: Illegitimate background token derived from text token: ${bgToken}`);
        return;
      }

      const effectiveLBorder = opacity < 1.0 && lBg && lBorder ? blendRgba(parseHex(lBorder), opacity, lBg) : lBorder;
      const effectiveDBorder = opacity < 1.0 && dBg && dBorder ? blendRgba(parseHex(dBorder), opacity, dBg) : dBorder;

      if (lBg && effectiveLBorder) {
        const cr = getContrast(effectiveLBorder, lBg);
        if (cr < 3.0) {
          violations.push(`L${line + 1}: Light border contrast ${cr.toFixed(2)}:1 < 3.0:1 (${borderToken} on ${bgToken}${opacity < 1.0 ? ` opacity ${opacity.toFixed(2)}` : ''})`);
        }
      }
      if (dBg && effectiveDBorder) {
        const cr = getContrast(effectiveDBorder, dBg);
        if (cr < 3.0) {
          violations.push(`L${line + 1}: Dark border contrast ${cr.toFixed(2)}:1 < 3.0:1 (${borderToken} on ${bgToken}${opacity < 1.0 ? ` opacity ${opacity.toFixed(2)}` : ''})`);
        }
      }
    }

    function traverseJsx(node: ts.Node, ancestorBgTokens: string[], ancestorFgTokens: string[], ancestorOpacity: number) {
      let currentBgTokens = ancestorBgTokens;
      let currentFgTokens = ancestorFgTokens;
      let currentOpacity = ancestorOpacity;

      if (ts.isJsxElement(node) || ts.isJsxSelfClosingElement(node)) {
        const opening = ts.isJsxElement(node) ? node.openingElement : node;
        const attrs = opening.attributes?.properties || [];
        let styleObj: ts.ObjectLiteralExpression | null = null;

        for (const attr of attrs) {
          if (ts.isJsxAttribute(attr) && attr.name.text === 'style') {
            totalStyleAttrs++;
            if (attr.initializer && ts.isJsxExpression(attr.initializer) && attr.initializer.expression && ts.isObjectLiteralExpression(attr.initializer.expression)) {
              styleObj = attr.initializer.expression;
            }
          }
        }

        if (styleObj) {
          let bgNode: ts.Expression | null = null;
          let fgNode: ts.Expression | null = null;
          let borderNode: ts.Expression | null = null;
          let opacityNode: ts.Expression | null = null;

          for (const p of styleObj.properties) {
            if (ts.isPropertyAssignment(p)) {
              const name = p.name.getText(sf);
              if (name === 'backgroundColor' || name === 'background') bgNode = p.initializer;
              if (name === 'color') fgNode = p.initializer;
              if (['border', 'borderColor', 'borderTop', 'borderBottom', 'borderLeft', 'borderRight'].includes(name)) {
                borderNode = p.initializer;
              }
              if (name === 'opacity') opacityNode = p.initializer;
            }
          }

          if (opacityNode) {
            const elemOp = extractOpacity(opacityNode);
            if (elemOp !== null) currentOpacity = ancestorOpacity * elemOp;
          }

          const bgBranches = bgNode ? extractBranches(bgNode) : [];
          if (bgBranches.length > 0) {
            currentBgTokens = bgBranches.map(b => b.token);
            for (const b of bgBranches) {
              if (b.token.startsWith('--color-text-')) {
                const { line } = sf.getLineAndCharacterOfPosition(bgNode!.getStart(sf));
                violations.push(`L${line + 1}: Illegitimate background token derived from text token: ${b.token}`);
              }
            }
          }

          const fgBranches = fgNode ? extractBranches(fgNode) : [];
          if (fgBranches.length > 0) {
            currentFgTokens = fgBranches.map(b => b.token);
          }

          if (bgNode && fgNode) {
            checkedObjects++;
            for (const bgB of bgBranches) {
              for (const fgB of fgBranches) {
                if (!bgB.cond || !fgB.cond || bgB.cond === fgB.cond) {
                  checkPair(bgB.token, fgB.token, styleObj.getStart(sf), currentOpacity);
                }
              }
            }
          } else if (!bgNode && fgNode) {
            unboundColorObjects++;
            const effectiveBgs = ancestorBgTokens.length > 0 ? ancestorBgTokens : containerBgs;
            for (const fgB of fgBranches) {
              for (const cBg of effectiveBgs) {
                checkPair(cBg, fgB.token, styleObj.getStart(sf), currentOpacity);
              }
            }
          } else if (opacityNode && !fgNode && currentFgTokens.length > 0) {
            // Element with opacity inheriting foreground from ancestor
            unboundColorObjects++;
            const effectiveBgs = currentBgTokens.length > 0 ? currentBgTokens : (ancestorBgTokens.length > 0 ? ancestorBgTokens : containerBgs);
            for (const fgT of currentFgTokens) {
              for (const cBg of effectiveBgs) {
                checkPair(cBg, fgT, styleObj.getStart(sf), currentOpacity);
              }
            }
          }

          if (borderNode) {
            const borderBranches = extractBranches(borderNode);
            if (borderBranches.length > 0) {
              checkedBorderObjects++;
              if (bgNode) {
                for (const bB of borderBranches) {
                  for (const bgB of bgBranches) {
                    if (!bB.cond || !bgB.cond || bB.cond === bgB.cond) {
                      checkBorderPair(bgB.token, bB.token, styleObj.getStart(sf), currentOpacity);
                    }
                  }
                }
              } else {
                const effectiveBgs = ancestorBgTokens.length > 0 ? ancestorBgTokens : containerBgs;
                for (const bB of borderBranches) {
                  for (const cBg of effectiveBgs) {
                    checkBorderPair(cBg, bB.token, styleObj.getStart(sf), currentOpacity);
                  }
                }
              }
            }
          }
        }
      }

      ts.forEachChild(node, child => traverseJsx(child, currentBgTokens, currentFgTokens, currentOpacity));
    }

    traverseJsx(sf, [], [], 1.0);

    // Exact ratchet assertions covering 100% of IntranetDeploymentView style declarations (ratcheted for #289 step-up section merge)
    expect(totalStyleAttrs, 'Total style attributes in IntranetDeploymentView must be exactly 201').toBe(201);
    expect(checkedObjects, 'Style objects with explicit background and foreground must be exactly 23').toBe(23);
    expect(checkedPairs, 'Evaluated foreground-background pairs across conditional branches must be exactly 150').toBe(150);
    expect(unboundColorObjects, 'Elements with foreground color inheriting container background must be exactly 106').toBe(106);
    expect(checkedObjects + unboundColorObjects, 'Total covered color style objects must be exactly 129').toBe(129);
    expect(checkedBorderObjects, 'Style objects with explicit border token declarations must be exactly 36').toBe(36);
    expect(checkedBorderPairs, 'Evaluated border-background pairs across conditional and container branches must be exactly 38').toBe(38);
    expect(violations, `Expected 0 style-pair contrast/collision violations in IntranetDeploymentView, got:\n${violations.join('\n')}`).toEqual([]);
  });

  // 9g. [Card 206 / ACC-09] Component DOM Rendering Verification: DeveloperStudio binds foregrounds and container backgrounds to design tokens with dynamic contrast verification
  it('ACC-09 / Card 206: DeveloperStudio component DOM rendering binds foregrounds and container backgrounds to design tokens with dynamic contrast verification', async () => {
    const container = document.createElement('div');
    container.setAttribute('data-theme', 'dark');
    document.body.appendChild(container);
    const root = createRoot(container);

    const originalGlobalFetch = globalThis.fetch;
    const originalWindowFetch = typeof window !== 'undefined' ? (window as any).fetch : undefined;
    const mockFetch = vi.fn().mockImplementation(() =>
      Promise.resolve({
        ok: true,
        status: 200,
        headers: new Headers({ 'Content-Type': 'application/json' }),
        json: async () => ({
          items: [],
          nextCursor: null,
          runId: 'run_studio_001',
          completedAt: '2026-09-22T10:10:00Z',
          output: { sha256: 'a'.repeat(64), sizeBytes: 1024 },
          evidence: { evidenceId: 'ev_001' },
          stopReceipt: { exitCode: 0, physicallyStopped: true, resourceReclaimed: true, verified: true },
        }),
        text: async () => JSON.stringify({ items: [] }),
      } as Response)
    );
    vi.stubGlobal('fetch', mockFetch);
    if (typeof window !== 'undefined') {
      (window as any).fetch = mockFetch;
    }

    vi.spyOn(client, 'apiClient').mockImplementation(async (endpoint: string) => {
      if (endpoint.includes('/runs/')) {
        return {
          id: 'run_studio_001',
          runId: 'run_studio_001',
          projectId: 'prj_studio_test',
          status: 'running',
          state: 'running',
          nodeId: 'nod_studio_01',
          objective: 'PACS Inference Execution Test',
          completedAt: '2026-09-22T10:10:00Z',
          output: { sha256: 'a'.repeat(64), sizeBytes: 1024 },
          evidence: { evidenceId: 'ev_001' },
          stopReceipt: { exitCode: 0, physicallyStopped: true, resourceReclaimed: true, verified: true },
        } as any;
      }
      return {
        items: [],
        nextCursor: null,
      } as any;
    });
    vi.spyOn(projectObservation, 'fetchProjectWorkspaces').mockResolvedValue([]);

    const sampleProject: ProjectItem = {
      id: 'prj_studio_test',
      name: 'PACS Inference Studio',
      createdAt: '2026-09-22T00:00:00Z',
    };

    const sampleNode: NodeItem = {
      id: 'nod_studio_01',
      hostname: 'gpu-worker-01.saintvision.internal',
      status: 'online',
      os: 'linux',
      cpuCores: 16,
      cpuUsagePercent: 25,
      memoryTotalBytes: 68719476736,
      memoryUsedBytes: 17179869184,
      gpuCount: 1,
      storageTotalBytes: 1000000000000,
      storageUsedBytes: 250000000000,
      heartbeatAt: '2026-09-22T10:00:00Z',
      schedulable: true,
    };

    const baseSampleRun: RunItem = {
      id: 'run_studio_001',
      projectId: 'prj_studio_test',
      status: 'running',
      state: 'running',
      nodeId: 'nod_studio_01',
      objective: 'PACS Inference Execution Test',
      attempt: 1,
      version: 1,
      createdAt: '2026-09-22T10:00:00Z',
      stateUpdatedAt: '2026-09-22T10:05:00Z',
    };

    try {
      // 1. Initial Render in Step 1 (Project & Workspace)
      await act(async () => {
        root.render(
          <DeveloperStudio
            key="studio-step1"
            project={sampleProject}
            nodes={[sampleNode]}
            runs={[baseSampleRun]}
            initialStep={1}
            initialNodeId={null}
            initialWorkspaceId={null}
          />
        );
      });

      // 1-a. Stepper Step 1 (Active)
      const step1 = container.querySelector('[data-testid="studio-stepper-step-1"]') as HTMLElement;
      expect(step1, 'Stepper step 1 must render').not.toBeNull();
      expect(step1.getAttribute('aria-selected')).toBe('true');
      expect(step1.style.backgroundColor, 'Step 1 bg must bind to var(--color-bg-subtle)').toBe('var(--color-bg-subtle)');
      expect(step1.style.borderColor, 'Step 1 active border must bind to var(--color-brand-primary)').toBe('var(--color-brand-primary)');
      const s1Border = helperExtractVar(step1.style.borderColor);
      expect(getContrast(lightTokens[s1Border], lightTokens['--color-bg-subtle']), 'Step 1 light border contrast >= 3.0:1').toBeGreaterThanOrEqual(3.0);
      expect(getContrast(darkTokens[s1Border], darkTokens['--color-bg-subtle']), 'Step 1 dark border contrast >= 3.0:1').toBeGreaterThanOrEqual(3.0);

      // 1-b. Render with bound Node & Workspace Chips
      await act(async () => {
        root.render(
          <DeveloperStudio
            key="studio-step2"
            project={sampleProject}
            nodes={[sampleNode]}
            runs={[baseSampleRun]}
            initialStep={2}
            initialNodeId="nod_studio_01"
            initialWorkspaceId="wsp_studio_01"
          />
        );
      });

      // Node Chip
      const nodeChip = container.querySelector('[data-testid="studio-node-chip"]') as HTMLElement;
      expect(nodeChip, 'Studio node chip must render').not.toBeNull();
      expect(nodeChip.style.backgroundColor, 'Node chip bg must bind to var(--color-bg-subtle)').toBe('var(--color-bg-subtle)');
      expect(nodeChip.style.color, 'Node chip text must bind to var(--color-brand-hover)').toBe('var(--color-brand-hover)');
      expect(nodeChip.style.borderColor, 'Node chip border must bind to var(--color-border-subtle)').toBe('var(--color-border-subtle)');
      const ncBg = helperExtractVar(nodeChip.style.backgroundColor);
      const ncFg = helperExtractVar(nodeChip.style.color);
      const ncBorder = helperExtractVar(nodeChip.style.borderColor);
      expect(getContrast(lightTokens[ncFg], lightTokens[ncBg]), 'Node chip light text contrast >= 4.5:1').toBeGreaterThanOrEqual(4.5);
      expect(getContrast(darkTokens[ncFg], darkTokens[ncBg]), 'Node chip dark text contrast >= 4.5:1').toBeGreaterThanOrEqual(4.5);
      expect(getContrast(lightTokens[ncBorder], lightTokens[ncBg]), 'Node chip light border contrast >= 3.0:1').toBeGreaterThanOrEqual(3.0);
      expect(getContrast(darkTokens[ncBorder], darkTokens[ncBg]), 'Node chip dark border contrast >= 3.0:1').toBeGreaterThanOrEqual(3.0);

      // Workspace Chip
      const wspChip = container.querySelector('[data-testid="studio-workspace-chip"]') as HTMLElement;
      expect(wspChip, 'Studio workspace chip must render').not.toBeNull();
      expect(wspChip.style.backgroundColor, 'Workspace chip bg must bind to var(--color-bg-subtle)').toBe('var(--color-bg-subtle)');
      expect(wspChip.style.color, 'Workspace chip text must bind to var(--color-status-online)').toBe('var(--color-status-online)');
      expect(wspChip.style.borderColor, 'Workspace chip border must bind to var(--color-border-subtle)').toBe('var(--color-border-subtle)');
      const wcBg = helperExtractVar(wspChip.style.backgroundColor);
      const wcFg = helperExtractVar(wspChip.style.color);
      const wcBorder = helperExtractVar(wspChip.style.borderColor);
      expect(getContrast(lightTokens[wcFg], lightTokens[wcBg]), 'Workspace chip light text contrast >= 4.5:1').toBeGreaterThanOrEqual(4.5);
      expect(getContrast(darkTokens[wcFg], darkTokens[wcBg]), 'Workspace chip dark text contrast >= 4.5:1').toBeGreaterThanOrEqual(4.5);
      expect(getContrast(lightTokens[wcBorder], lightTokens[wcBg]), 'Workspace chip light border contrast >= 3.0:1').toBeGreaterThanOrEqual(3.0);
      expect(getContrast(darkTokens[wcBorder], darkTokens[wcBg]), 'Workspace chip dark border contrast >= 3.0:1').toBeGreaterThanOrEqual(3.0);

      // 2. Step 4 Execution Status Badge: State Transitions (Running, Succeeded, Failed, Awaiting Approval)
      // 2-a. RUNNING state
      await act(async () => {
        root.render(
          <DeveloperStudio
            key="studio-run-running"
            project={sampleProject}
            nodes={[sampleNode]}
            runs={[{ ...baseSampleRun, id: 'run_studio_running', state: 'running' }]}
            initialStep={4}
            initialRunId="run_studio_running"
          />
        );
      });
      const badgeRunning = container.querySelector('[data-testid="studio-execution-status-badge"]') as HTMLElement;
      expect(badgeRunning, 'Status badge (running) must render').not.toBeNull();
      expect(badgeRunning.style.backgroundColor).toBe('var(--color-bg-subtle)');
      expect(badgeRunning.style.color, 'Running status text must bind to var(--color-brand-hover)').toBe('var(--color-brand-hover)');
      expect(badgeRunning.style.borderColor, 'Running status border must bind to var(--color-brand-hover)').toBe('var(--color-brand-hover)');
      expect(badgeRunning.textContent).toContain('RUNNING');
      const rBg = helperExtractVar(badgeRunning.style.backgroundColor);
      const rFg = helperExtractVar(badgeRunning.style.color);
      const rBorder = helperExtractVar(badgeRunning.style.borderColor);
      expect(getContrast(lightTokens[rFg], lightTokens[rBg]), 'Running light text contrast >= 4.5:1').toBeGreaterThanOrEqual(4.5);
      expect(getContrast(darkTokens[rFg], darkTokens[rBg]), 'Running dark text contrast >= 4.5:1').toBeGreaterThanOrEqual(4.5);
      expect(getContrast(lightTokens[rBorder], lightTokens[rBg]), 'Running light border contrast >= 3.0:1').toBeGreaterThanOrEqual(3.0);
      expect(getContrast(darkTokens[rBorder], darkTokens[rBg]), 'Running dark border contrast >= 3.0:1').toBeGreaterThanOrEqual(3.0);

      // 2-b. SUCCEEDED state
      await act(async () => {
        root.render(
          <DeveloperStudio
            key="studio-run-succeeded"
            project={sampleProject}
            nodes={[sampleNode]}
            runs={[{ ...baseSampleRun, id: 'run_studio_succeeded', state: 'succeeded', completedAt: '2026-09-22T10:10:00Z' }]}
            initialStep={4}
            initialRunId="run_studio_succeeded"
          />
        );
      });
      await act(async () => {
        await Promise.resolve();
        await Promise.resolve();
      });
      const badgeSucceeded = container.querySelector('[data-testid="studio-execution-status-badge"]') as HTMLElement;
      expect(badgeSucceeded, 'Status badge (succeeded) must render').not.toBeNull();
      expect(badgeSucceeded.style.color, 'Succeeded status text must bind to var(--color-status-online)').toBe('var(--color-status-online)');
      expect(badgeSucceeded.style.borderColor, 'Succeeded status border must bind to var(--color-status-online)').toBe('var(--color-status-online)');
      expect(badgeSucceeded.textContent).toContain('SUCCEEDED');
      const sFg = helperExtractVar(badgeSucceeded.style.color);
      const sBorder = helperExtractVar(badgeSucceeded.style.borderColor);
      expect(getContrast(lightTokens[sFg], lightTokens[rBg]), 'Succeeded light text contrast >= 4.5:1').toBeGreaterThanOrEqual(4.5);
      expect(getContrast(darkTokens[sFg], darkTokens[rBg]), 'Succeeded dark text contrast >= 4.5:1').toBeGreaterThanOrEqual(4.5);
      expect(getContrast(lightTokens[sBorder], lightTokens[rBg]), 'Succeeded light border contrast >= 3.0:1').toBeGreaterThanOrEqual(3.0);
      expect(getContrast(darkTokens[sBorder], darkTokens[rBg]), 'Succeeded dark border contrast >= 3.0:1').toBeGreaterThanOrEqual(3.0);

      // CompletedAt timestamp badge
      const completedAtBadge = container.querySelector('[data-testid="studio-run-completed-at"]') as HTMLElement;
      expect(completedAtBadge, 'CompletedAt badge must render').not.toBeNull();
      expect(completedAtBadge.style.color).toBe('var(--color-status-online)');
      const caFg = helperExtractVar(completedAtBadge.style.color);
      expect(getContrast(lightTokens[caFg], lightTokens['--color-bg-subtle']), 'CompletedAt light text contrast >= 4.5:1').toBeGreaterThanOrEqual(4.5);
      expect(getContrast(darkTokens[caFg], darkTokens['--color-bg-subtle']), 'CompletedAt dark text contrast >= 4.5:1').toBeGreaterThanOrEqual(4.5);

      // 2-c. FAILED state
      await act(async () => {
        root.render(
          <DeveloperStudio
            key="studio-run-failed"
            project={sampleProject}
            nodes={[sampleNode]}
            runs={[{ ...baseSampleRun, id: 'run_studio_failed', state: 'failed' }]}
            initialStep={4}
            initialRunId="run_studio_failed"
          />
        );
      });
      const badgeFailed = container.querySelector('[data-testid="studio-execution-status-badge"]') as HTMLElement;
      expect(badgeFailed, 'Status badge (failed) must render').not.toBeNull();
      expect(badgeFailed.style.color, 'Failed status text must bind to var(--color-status-offline)').toBe('var(--color-status-offline)');
      expect(badgeFailed.style.borderColor, 'Failed status border must bind to var(--color-status-offline)').toBe('var(--color-status-offline)');
      expect(badgeFailed.textContent).toContain('FAILED');
      const fFg = helperExtractVar(badgeFailed.style.color);
      const fBorder = helperExtractVar(badgeFailed.style.borderColor);
      expect(getContrast(lightTokens[fFg], lightTokens[rBg]), 'Failed light text contrast >= 4.5:1').toBeGreaterThanOrEqual(4.5);
      expect(getContrast(darkTokens[fFg], darkTokens[rBg]), 'Failed dark text contrast >= 4.5:1').toBeGreaterThanOrEqual(4.5);
      expect(getContrast(lightTokens[fBorder], lightTokens[rBg]), 'Failed light border contrast >= 3.0:1').toBeGreaterThanOrEqual(3.0);
      expect(getContrast(darkTokens[fBorder], darkTokens[rBg]), 'Failed dark border contrast >= 3.0:1').toBeGreaterThanOrEqual(3.0);

      // 2-d. AWAITING_APPROVAL state
      await act(async () => {
        root.render(
          <DeveloperStudio
            key="studio-run-approval"
            project={sampleProject}
            nodes={[sampleNode]}
            runs={[{ ...baseSampleRun, id: 'run_studio_approval', state: 'awaiting_approval' }]}
            initialStep={4}
            initialRunId="run_studio_approval"
          />
        );
      });
      const badgeApproval = container.querySelector('[data-testid="studio-execution-status-badge"]') as HTMLElement;
      expect(badgeApproval, 'Status badge (awaiting_approval) must render').not.toBeNull();
      expect(badgeApproval.style.color, 'Awaiting approval text must bind to var(--color-status-degraded)').toBe('var(--color-status-degraded)');
      expect(badgeApproval.style.borderColor, 'Awaiting approval border must bind to var(--color-status-degraded)').toBe('var(--color-status-degraded)');
      expect(badgeApproval.textContent).toContain('AWAITING_APPROVAL');
      const aFg = helperExtractVar(badgeApproval.style.color);
      const aBorder = helperExtractVar(badgeApproval.style.borderColor);
      expect(getContrast(lightTokens[aFg], lightTokens[rBg]), 'Awaiting approval light text contrast >= 4.5:1').toBeGreaterThanOrEqual(4.5);
      expect(getContrast(darkTokens[aFg], darkTokens[rBg]), 'Awaiting approval dark text contrast >= 4.5:1').toBeGreaterThanOrEqual(4.5);
      expect(getContrast(lightTokens[aBorder], lightTokens[rBg]), 'Awaiting approval light border contrast >= 3.0:1').toBeGreaterThanOrEqual(3.0);
      expect(getContrast(darkTokens[aBorder], darkTokens[rBg]), 'Awaiting approval dark border contrast >= 3.0:1').toBeGreaterThanOrEqual(3.0);

      // 2-e. CANCELLED state (F4 differentiation & DOM verification)
      await act(async () => {
        root.render(
          <DeveloperStudio
            key="studio-run-cancelled"
            project={sampleProject}
            nodes={[sampleNode]}
            runs={[{ ...baseSampleRun, id: 'run_studio_cancelled', state: 'cancelled' }]}
            initialStep={4}
            initialRunId="run_studio_cancelled"
          />
        );
      });
      const badgeCancelled = container.querySelector('[data-testid="studio-execution-status-badge"]') as HTMLElement;
      expect(badgeCancelled, 'Status badge (cancelled) must render').not.toBeNull();
      expect(badgeCancelled.style.color, 'Cancelled status text must bind to var(--color-status-neutral)').toBe('var(--color-status-neutral)');
      expect(badgeCancelled.style.borderColor, 'Cancelled status border must bind to var(--color-border-strong)').toBe('var(--color-border-strong)');
      expect(badgeCancelled.textContent).toContain('CANCELLED');
      const cFg = helperExtractVar(badgeCancelled.style.color);
      const cBorder = helperExtractVar(badgeCancelled.style.borderColor);
      expect(getContrast(lightTokens[cFg], lightTokens[rBg]), 'Cancelled light text contrast >= 4.5:1').toBeGreaterThanOrEqual(4.5);
      expect(getContrast(darkTokens[cFg], darkTokens[rBg]), 'Cancelled dark text contrast >= 4.5:1').toBeGreaterThanOrEqual(4.5);
      expect(getContrast(lightTokens[cBorder], lightTokens[rBg]), 'Cancelled light border contrast >= 3.0:1').toBeGreaterThanOrEqual(3.0);
      expect(getContrast(darkTokens[cBorder], darkTokens[rBg]), 'Cancelled dark border contrast >= 3.0:1').toBeGreaterThanOrEqual(3.0);

      // 2-f. RECOVERING state (F4 differentiation & DOM verification)
      await act(async () => {
        root.render(
          <DeveloperStudio
            key="studio-run-recovering"
            project={sampleProject}
            nodes={[sampleNode]}
            runs={[{ ...baseSampleRun, id: 'run_studio_recovering', state: 'recovering' }]}
            initialStep={4}
            initialRunId="run_studio_recovering"
          />
        );
      });
      const badgeRecovering = container.querySelector('[data-testid="studio-execution-status-badge"]') as HTMLElement;
      expect(badgeRecovering, 'Status badge (recovering) must render').not.toBeNull();
      expect(badgeRecovering.style.color, 'Recovering status text must bind to var(--color-status-active)').toBe('var(--color-status-active)');
      expect(badgeRecovering.style.borderColor, 'Recovering status border must bind to var(--color-status-active)').toBe('var(--color-status-active)');
      expect(badgeRecovering.textContent).toContain('RECOVERING');
      const recFg = helperExtractVar(badgeRecovering.style.color);
      const recBorder = helperExtractVar(badgeRecovering.style.borderColor);
      expect(getContrast(lightTokens[recFg], lightTokens[rBg]), 'Recovering light text contrast >= 4.5:1').toBeGreaterThanOrEqual(4.5);
      expect(getContrast(darkTokens[recFg], darkTokens[rBg]), 'Recovering dark text contrast >= 4.5:1').toBeGreaterThanOrEqual(4.5);
      expect(getContrast(lightTokens[recBorder], lightTokens[rBg]), 'Recovering light border contrast >= 3.0:1').toBeGreaterThanOrEqual(3.0);
      expect(getContrast(darkTokens[recBorder], darkTokens[rBg]), 'Recovering dark border contrast >= 3.0:1').toBeGreaterThanOrEqual(3.0);
    } finally {
      vi.unstubAllGlobals();
      if (typeof window !== 'undefined' && originalWindowFetch) {
        Object.defineProperty(window, 'fetch', { value: originalWindowFetch, writable: true, configurable: true });
      }
      act(() => {
        root.unmount();
      });
      container.remove();
    }
  }, 15000);

  // 9g-2. [Card 206 / ACC-09] Dynamic AST Style-Pair Contrast Calculator & Strict Coverage Ratchet: DeveloperStudio
  it('ACC-09 / Card 206: DeveloperStudio style objects maintain valid contrast pairings and reject 1:1 collisions and defective combinations', () => {
    const filePath = path.resolve(__dirname, '../src/features/studio/DeveloperStudio.tsx');
    const content = fs.readFileSync(filePath, 'utf-8');
    const sf = ts.createSourceFile('DeveloperStudio.tsx', content, ts.ScriptTarget.Latest, true, ts.ScriptKind.TSX);

    interface Branch {
      cond: string;
      token: string;
    }

    function extractBranches(node: ts.Node): Branch[] {
      const branches: Branch[] = [];
      function collect(n: ts.Node, condPath: string) {
        if (ts.isConditionalExpression(n)) {
          const condText = n.condition.getText(sf).replace(/\s+/g, ' ');
          collect(n.whenTrue, condPath ? `${condPath} && ${condText}` : condText);
          collect(n.whenFalse, condPath ? `${condPath} && !(${condText})` : `!(${condText})`);
        } else if (ts.isTemplateExpression(n)) {
          for (const span of n.templateSpans) {
            collect(span.expression, condPath);
          }
        } else {
          const text = n.getText(sf);
          const m = text.match(/var\((--color-[a-z0-9-]+)\)/);
          if (m) {
            branches.push({ cond: condPath, token: m[1] });
          }
        }
      }
      collect(node, '');
      return branches;
    }

    function extractOpacity(node: ts.Node): number | null {
      if (ts.isNumericLiteral(node)) return parseFloat(node.text);
      if (ts.isConditionalExpression(node)) {
        const trueOp = extractOpacity(node.whenTrue);
        const falseOp = extractOpacity(node.whenFalse);
        if (trueOp !== null && falseOp !== null) return Math.min(trueOp, falseOp);
        return trueOp ?? falseOp;
      }
      return null;
    }

    let checkedPairs = 0;
    let checkedObjects = 0;
    let totalStyleAttrs = 0;
    let unboundColorObjects = 0;
    let checkedBorderObjects = 0;
    let checkedBorderPairs = 0;
    const violations: string[] = [];
    const containerBgs = ['--color-bg-surface', '--color-bg-subtle', '--color-bg-canvas'];

    function checkPair(bgToken: string, fgToken: string, pos: number, opacity: number = 1.0) {
      checkedPairs++;
      const { line } = sf.getLineAndCharacterOfPosition(pos);
      const lightBg = resolveTokenHex(bgToken, lightTokens);
      const lightFg = resolveTokenHex(fgToken, lightTokens);
      const darkBg = resolveTokenHex(bgToken, darkTokens);
      const darkFg = resolveTokenHex(fgToken, darkTokens);

      if (bgToken === fgToken && opacity >= 1.0) {
        violations.push(`L${line + 1}: 1:1 token collision between background and foreground (${bgToken})`);
        return;
      }

      if (bgToken.startsWith('--color-text-')) {
        violations.push(`L${line + 1}: Illegitimate background token derived from text token: ${bgToken}`);
        return;
      }

      const effectiveLFg = opacity < 1.0 && lightBg && lightFg ? blendRgba(parseHex(lightFg), opacity, lightBg) : lightFg;
      const effectiveDFg = opacity < 1.0 && darkBg && darkFg ? blendRgba(parseHex(darkFg), opacity, darkBg) : darkFg;

      if (lightBg && effectiveLFg) {
        const cr = getContrast(effectiveLFg, lightBg);
        if (cr < 4.5) {
          violations.push(`L${line + 1}: Light text contrast ${cr.toFixed(2)}:1 < 4.5:1 (${fgToken} on ${bgToken}${opacity < 1.0 ? ` opacity ${opacity.toFixed(2)}` : ''})`);
        }
      }
      if (darkBg && effectiveDFg) {
        const cr = getContrast(effectiveDFg, darkBg);
        if (cr < 4.5) {
          violations.push(`L${line + 1}: Dark text contrast ${cr.toFixed(2)}:1 < 4.5:1 (${fgToken} on ${bgToken}${opacity < 1.0 ? ` opacity ${opacity.toFixed(2)}` : ''})`);
        }
      }
    }

    function checkBorderPair(bgToken: string, borderToken: string, pos: number, opacity: number = 1.0) {
      checkedBorderPairs++;
      const { line } = sf.getLineAndCharacterOfPosition(pos);
      const lBg = resolveTokenHex(bgToken, lightTokens);
      const dBg = resolveTokenHex(bgToken, darkTokens);
      const lBorder = resolveTokenHex(borderToken, lightTokens);
      const dBorder = resolveTokenHex(borderToken, darkTokens);

      if (bgToken === borderToken && opacity >= 1.0) {
        violations.push(`L${line + 1}: Identical border-background token collision (1:1 contrast) detected: ${borderToken} on ${bgToken}`);
        return;
      }

      if (bgToken.startsWith('--color-text-')) {
        violations.push(`L${line + 1}: Illegitimate background token derived from text token: ${bgToken}`);
        return;
      }

      const effectiveLBorder = opacity < 1.0 && lBg && lBorder ? blendRgba(parseHex(lBorder), opacity, lBg) : lBorder;
      const effectiveDBorder = opacity < 1.0 && dBg && dBorder ? blendRgba(parseHex(dBorder), opacity, dBg) : dBorder;

      if (lBg && effectiveLBorder) {
        const cr = getContrast(effectiveLBorder, lBg);
        if (cr < 3.0) {
          violations.push(`L${line + 1}: Light border contrast ${cr.toFixed(2)}:1 < 3.0:1 (${borderToken} on ${bgToken}${opacity < 1.0 ? ` opacity ${opacity.toFixed(2)}` : ''})`);
        }
      }
      if (dBg && effectiveDBorder) {
        const cr = getContrast(effectiveDBorder, dBg);
        if (cr < 3.0) {
          violations.push(`L${line + 1}: Dark border contrast ${cr.toFixed(2)}:1 < 3.0:1 (${borderToken} on ${bgToken}${opacity < 1.0 ? ` opacity ${opacity.toFixed(2)}` : ''})`);
        }
      }
    }

    function traverseJsx(node: ts.Node, ancestorBgTokens: string[], ancestorFgTokens: string[], ancestorOpacity: number) {
      let currentBgTokens = ancestorBgTokens;
      let currentFgTokens = ancestorFgTokens;
      let currentOpacity = ancestorOpacity;

      if (ts.isJsxElement(node) || ts.isJsxSelfClosingElement(node)) {
        const opening = ts.isJsxElement(node) ? node.openingElement : node;
        const attrs = opening.attributes?.properties || [];
        let styleObj: ts.ObjectLiteralExpression | null = null;

        for (const attr of attrs) {
          if (ts.isJsxAttribute(attr) && attr.name.text === 'style') {
            totalStyleAttrs++;
            if (attr.initializer && ts.isJsxExpression(attr.initializer) && attr.initializer.expression && ts.isObjectLiteralExpression(attr.initializer.expression)) {
              styleObj = attr.initializer.expression;
            }
          }
        }

        if (styleObj) {
          let bgNode: ts.Expression | null = null;
          let fgNode: ts.Expression | null = null;
          let borderNode: ts.Expression | null = null;
          let opacityNode: ts.Expression | null = null;

          for (const p of styleObj.properties) {
            if (ts.isPropertyAssignment(p)) {
              const name = p.name.getText(sf);
              if (name === 'backgroundColor' || name === 'background') bgNode = p.initializer;
              if (name === 'color') fgNode = p.initializer;
              if (['border', 'borderColor', 'borderTop', 'borderBottom', 'borderLeft', 'borderRight'].includes(name)) {
                borderNode = p.initializer;
              }
              if (name === 'opacity') opacityNode = p.initializer;
            }
          }

          if (opacityNode) {
            const elemOp = extractOpacity(opacityNode);
            if (elemOp !== null) currentOpacity = ancestorOpacity * elemOp;
          }

          const bgBranches = bgNode ? extractBranches(bgNode) : [];
          if (bgBranches.length > 0) {
            currentBgTokens = bgBranches.map(b => b.token);
            for (const b of bgBranches) {
              if (b.token.startsWith('--color-text-')) {
                const { line } = sf.getLineAndCharacterOfPosition(bgNode!.getStart(sf));
                violations.push(`L${line + 1}: Illegitimate background token derived from text token: ${b.token}`);
              }
            }
          }

          const fgBranches = fgNode ? extractBranches(fgNode) : [];
          if (fgBranches.length > 0) {
            currentFgTokens = fgBranches.map(b => b.token);
          }

          if (bgNode && fgNode) {
            checkedObjects++;
            for (const bgB of bgBranches) {
              for (const fgB of fgBranches) {
                if (!bgB.cond || !fgB.cond || bgB.cond === fgB.cond) {
                  checkPair(bgB.token, fgB.token, styleObj.getStart(sf), currentOpacity);
                }
              }
            }
          } else if (!bgNode && fgNode) {
            unboundColorObjects++;
            const effectiveBgs = ancestorBgTokens.length > 0 ? ancestorBgTokens : containerBgs;
            for (const fgB of fgBranches) {
              for (const cBg of effectiveBgs) {
                checkPair(cBg, fgB.token, styleObj.getStart(sf), currentOpacity);
              }
            }
          } else if (opacityNode && !fgNode && currentFgTokens.length > 0) {
            unboundColorObjects++;
            const effectiveBgs = currentBgTokens.length > 0 ? currentBgTokens : (ancestorBgTokens.length > 0 ? ancestorBgTokens : containerBgs);
            for (const fgT of currentFgTokens) {
              for (const cBg of effectiveBgs) {
                checkPair(cBg, fgT, styleObj.getStart(sf), currentOpacity);
              }
            }
          }

          if (borderNode) {
            const borderBranches = extractBranches(borderNode);
            if (borderBranches.length > 0) {
              checkedBorderObjects++;
              if (bgNode) {
                for (const bB of borderBranches) {
                  for (const bgB of bgBranches) {
                    if (!bB.cond || !bgB.cond || bB.cond === bgB.cond) {
                      checkBorderPair(bgB.token, bB.token, styleObj.getStart(sf), currentOpacity);
                    }
                  }
                }
              } else {
                const effectiveBgs = ancestorBgTokens.length > 0 ? ancestorBgTokens : containerBgs;
                for (const bB of borderBranches) {
                  for (const cBg of effectiveBgs) {
                    checkBorderPair(cBg, bB.token, styleObj.getStart(sf), currentOpacity);
                  }
                }
              }
            }
          }
        }
      }

      ts.forEachChild(node, child => traverseJsx(child, currentBgTokens, currentFgTokens, currentOpacity));
    }

    traverseJsx(sf, [], [], 1.0);

    // Exact ratchet assertions covering 100% of DeveloperStudio style declarations
    expect(totalStyleAttrs, 'Total style attributes in DeveloperStudio must be exactly 252').toBe(252);
    expect(checkedObjects, 'Style objects with explicit background and foreground must be exactly 36').toBe(36);
    expect(checkedPairs, 'Evaluated foreground-background pairs across conditional branches must be exactly 157').toBe(157);
    expect(unboundColorObjects, 'Elements with foreground color inheriting container background must be exactly 92').toBe(92);
    expect(checkedObjects + unboundColorObjects, 'Total covered color style objects must be exactly 128').toBe(128);
    expect(checkedBorderObjects, 'Style objects with explicit border token declarations must be exactly 68').toBe(68);
    expect(checkedBorderPairs, 'Evaluated border-background pairs across conditional and container branches must be exactly 93').toBe(93);
    expect(violations, `Expected 0 style-pair contrast/collision violations in DeveloperStudio, got:\n${violations.join('\n')}`).toEqual([]);
  });

  // 9h. [Card 213 / ACC-09] Component DOM Rendering Verification: Runs execution record screens (SealRecordPanel & RunDetail)
  it('ACC-09 / Card 213: Runs execution screens (SealRecordPanel & RunDetail) DOM rendering binds foregrounds and container backgrounds to design tokens with dynamic contrast verification', async () => {
    const container = document.createElement('div');
    container.setAttribute('data-theme', 'dark');
    document.body.appendChild(container);
    const root = createRoot(container);

    const originalGlobalFetch = globalThis.fetch;
    const originalWindowFetch = typeof window !== 'undefined' ? (window as any).fetch : undefined;
    const mockFetch = vi.fn().mockImplementation(() =>
      Promise.resolve({
        ok: true,
        status: 200,
        headers: new Headers({ 'Content-Type': 'application/json' }),
        json: async () => ({ items: [] }),
        text: async () => JSON.stringify({ items: [] }),
      } as Response)
    );
    vi.stubGlobal('fetch', mockFetch);
    if (typeof window !== 'undefined') {
      (window as any).fetch = mockFetch;
    }

    const testRunId = 'run_c213_test_001';
    const testProjectId = 'prj_c213_test_001';

    const sealedFixture = {
      recordId: 'rec_c213_001',
      runId: testRunId,
      finalState: 'succeeded',
      terminationReason: 'completed',
      evidenceId: 'evd_c213_001',
      bundleId: 'bnd_c213_001',
      bundleHash: 'a'.repeat(64),
      workloadSpecSha256: 'b'.repeat(64),
      componentVersions: { adapter: 'reference', kernel: '1.2.0' },
      attemptCount: 1,
      sealedAt: '2026-10-02T05:00:00Z',
    };

    const artifactsFixture = {
      recordId: 'rec_c213_001',
      runId: testRunId,
      role: null,
      nextCursor: null,
      count: 1,
      items: [
        {
          artifactId: 'art_c213_001',
          role: 'model_output',
          objectVersion: 'v1.0',
          uri: 's3://saintvision-artifacts/output.bin',
          checksumSha256: 'c'.repeat(64),
          byteSize: 4096,
        },
      ],
    };

    const bundleFixture = {
      bundleId: 'bnd_c213_001',
      runId: testRunId,
      bundleHash: 'a'.repeat(64),
      hashVerified: true,
      sealed: true,
      itemCount: 1,
      totalBytes: 1024,
      tokenEstimate: 256,
      retrievalStrategy: 'explicit',
      componentVersions: { adapter: 'reference', kernel: '1.2.0' },
      builtAt: '2026-10-02T04:00:00Z',
      items: [
        {
          itemId: 'itm_c213_001',
          itemVersion: 1,
          kind: 'document',
          ordinal: 0,
          contentHash: 'd'.repeat(64),
          byteSize: 1024,
          redacted: false,
        },
      ],
    };

    vi.spyOn(client, 'apiClient').mockImplementation(async (url: string) => {
      if (url.includes('unsealed')) {
        if (url.includes('/record')) {
          throw new client.ApiError({
            type: 'about:blank',
            title: 'RES-0004',
            status: 404,
            code: 'RES-0004',
            detail: 'No sealed record for this run.',
            category: 'RES',
            retryable: false,
          } as any);
        }
        if (url.includes('/context-bundle')) {
          throw new client.ApiError({
            type: 'about:blank',
            title: 'RES-0004',
            status: 404,
            code: 'RES-0004',
            detail: 'No context bundle for this run.',
            category: 'RES',
            retryable: false,
          } as any);
        }
      }
      if (url.includes('/verify')) {
        return {
          runId: testRunId,
          recordId: 'rec_c213_001',
          artifactId: 'art_c213_001',
          pinnedChecksumSha256: 'c'.repeat(64),
          verified: true,
        } as any;
      }
      if (url.includes('/record/artifacts')) return artifactsFixture as any;
      if (url.includes('/context-bundle')) return bundleFixture as any;
      if (url.includes('/record')) return sealedFixture as any;
      if (url.includes('/attempts')) {
        return {
          source: 'execution-kernel',
          runId: testRunId,
          attempts: [
            { attemptNumber: 1, startedAt: '2026-10-02T04:00:05Z', nodeId: 'nod_01JABCDEF01', commandId: 'c1', stopReceiptId: 's1', exitCode: 0, reason: 'completed', evidenceId: null },
            { attemptNumber: 2, startedAt: '2026-10-02T04:01:05Z', nodeId: 'nod_01JABCDEF01', commandId: 'c2', stopReceiptId: 's2', exitCode: 1, reason: 'failed', evidenceId: null },
          ],
          count: 2,
          nextCursor: null,
        } as any;
      }
      if (url.includes('/shards')) return { shards: [] } as any;
      if (url.includes('/logs')) return { runId: testRunId, stdout: 'Sample run logs', stderr: '', completedAt: '2026-10-02T05:05:00Z' } as any;
      return {} as any;
    });

    try {
      // 1. SealRecordPanel (Sealed State)
      await act(async () => {
        root.render(<SealRecordPanel projectId={testProjectId} runId={testRunId} />);
      });
      await act(async () => {
        await Promise.resolve();
        await Promise.resolve();
      });

      const sealBadge = container.querySelector('[data-testid="seal-status-badge"]') as HTMLElement;
      expect(sealBadge, 'Seal status badge must render').not.toBeNull();
      expect(sealBadge.textContent).toContain('봉인됨 (SEALED)');
      expect(sealBadge.style.color).toBe('var(--color-status-online)');
      expect(sealBadge.style.backgroundColor).toBe('var(--color-bg-subtle)');
      expect(sealBadge.style.borderColor).toBe('var(--color-status-online)');

      const sbFg = helperExtractVar(sealBadge.style.color);
      const sbBg = helperExtractVar(sealBadge.style.backgroundColor);
      const sbBorder = helperExtractVar(sealBadge.style.borderColor);
      expect(getContrast(lightTokens[sbFg], lightTokens[sbBg]), 'Seal badge light text contrast >= 4.5:1').toBeGreaterThanOrEqual(4.5);
      expect(getContrast(darkTokens[sbFg], darkTokens[sbBg]), 'Seal badge dark text contrast >= 4.5:1').toBeGreaterThanOrEqual(4.5);
      expect(getContrast(lightTokens[sbBorder], lightTokens[sbBg]), 'Seal badge light border contrast >= 3.0:1').toBeGreaterThanOrEqual(3.0);
      expect(getContrast(darkTokens[sbBorder], darkTokens[sbBg]), 'Seal badge dark border contrast >= 3.0:1').toBeGreaterThanOrEqual(3.0);

      // Seal Record Fields
      const sealRecId = container.querySelector('[data-testid="seal-record-id"]') as HTMLElement;
      expect(sealRecId, 'Seal record ID must render').not.toBeNull();
      expect(sealRecId.style.color).toBe('var(--color-text-primary)');
      const sriFg = helperExtractVar(sealRecId.style.color);
      expect(getContrast(lightTokens[sriFg], lightTokens['--color-bg-surface']), 'Seal record ID light text contrast >= 4.5:1').toBeGreaterThanOrEqual(4.5);
      expect(getContrast(darkTokens[sriFg], darkTokens['--color-bg-surface']), 'Seal record ID dark text contrast >= 4.5:1').toBeGreaterThanOrEqual(4.5);

      const finalState = container.querySelector('[data-testid="seal-final-state"]') as HTMLElement;
      expect(finalState, 'Final state must render').not.toBeNull();
      expect(finalState.style.color).toBe('var(--color-brand-hover)');
      const fsFg = helperExtractVar(finalState.style.color);
      expect(getContrast(lightTokens[fsFg], lightTokens['--color-bg-surface']), 'Final state light text contrast >= 4.5:1').toBeGreaterThanOrEqual(4.5);
      expect(getContrast(darkTokens[fsFg], darkTokens['--color-bg-surface']), 'Final state dark text contrast >= 4.5:1').toBeGreaterThanOrEqual(4.5);

      const specSha = container.querySelector('[data-testid="seal-workload-spec-sha"]') as HTMLElement;
      expect(specSha, 'Workload spec SHA must render').not.toBeNull();
      expect(specSha.style.color).toBe('var(--color-brand-hover)');
      const ssFg = helperExtractVar(specSha.style.color);
      expect(getContrast(lightTokens[ssFg], lightTokens['--color-bg-surface']), 'Spec SHA light text contrast >= 4.5:1').toBeGreaterThanOrEqual(4.5);
      expect(getContrast(darkTokens[ssFg], darkTokens['--color-bg-surface']), 'Spec SHA dark text contrast >= 4.5:1').toBeGreaterThanOrEqual(4.5);

      const bundleHash = container.querySelector('[data-testid="bundle-hash"]') as HTMLElement;
      expect(bundleHash, 'Bundle hash must render').not.toBeNull();
      expect(bundleHash.style.color).toBe('var(--color-brand-hover)');
      const bhFg = helperExtractVar(bundleHash.style.color);
      expect(getContrast(lightTokens[bhFg], lightTokens['--color-bg-surface']), 'Bundle hash light text contrast >= 4.5:1').toBeGreaterThanOrEqual(4.5);
      expect(getContrast(darkTokens[bhFg], darkTokens['--color-bg-surface']), 'Bundle hash dark text contrast >= 4.5:1').toBeGreaterThanOrEqual(4.5);

      // 1b. SealRecordPanel (Unsealed State - 404 RES-0004)
      await act(async () => {
        root.render(<SealRecordPanel projectId={testProjectId} runId="run_c213_unsealed" key="unsealed" />);
      });
      await act(async () => {
        await Promise.resolve();
        await Promise.resolve();
      });

      const unsealedBadge = container.querySelector('[data-testid="seal-status-badge"]') as HTMLElement;
      expect(unsealedBadge, 'Unsealed status badge must render').not.toBeNull();
      expect(unsealedBadge.textContent).toContain('미봉인 (UNSEALED)');
      expect(unsealedBadge.style.color).toBe('var(--color-status-degraded)');
      expect(unsealedBadge.style.backgroundColor).toBe('var(--color-bg-subtle)');
      expect(unsealedBadge.style.borderColor).toBe('var(--color-status-degraded)');
      expect(unsealedBadge.style.color, 'SEALED and UNSEALED status badges must have distinct semantic tokens').not.toBe(sealBadge.style.color);

      const usbFg = helperExtractVar(unsealedBadge.style.color);
      const usbBg = helperExtractVar(unsealedBadge.style.backgroundColor);
      const usbBorder = helperExtractVar(unsealedBadge.style.borderColor);
      expect(getContrast(lightTokens[usbFg], lightTokens[usbBg]), 'Unsealed badge light text contrast >= 4.5:1').toBeGreaterThanOrEqual(4.5);
      expect(getContrast(darkTokens[usbFg], darkTokens[usbBg]), 'Unsealed badge dark text contrast >= 4.5:1').toBeGreaterThanOrEqual(4.5);
      expect(getContrast(lightTokens[usbBorder], lightTokens[usbBg]), 'Unsealed badge light border contrast >= 3.0:1').toBeGreaterThanOrEqual(3.0);
      expect(getContrast(darkTokens[usbBorder], darkTokens[usbBg]), 'Unsealed badge dark border contrast >= 3.0:1').toBeGreaterThanOrEqual(3.0);

      // 2. RunDetail Status Badges (Succeeded, Running, Failed, Cancelled, Recovering, Awaiting Approval)
      const baseRun: RunItem = {
        id: testRunId,
        projectId: testProjectId,
        status: 'succeeded',
        state: 'succeeded',
        targetNodeId: 'nod_01JABCDEF01',
        createdAt: '2026-10-02T04:00:00Z',
        startedAt: '2026-10-02T04:00:05Z',
        stateUpdatedAt: '2026-10-02T05:00:00Z',
        completedAt: '2026-10-02T05:00:00Z',
        objective: 'PACS Inference Run Detail Contrast Verification',
      };

      // 2-a. SUCCEEDED State
      await act(async () => {
        root.render(<RunDetail run={baseRun} onBack={() => {}} />);
      });
      await act(async () => {
        await Promise.resolve();
      });

      const badgeSucceeded = container.querySelector('[data-testid="run-detail-status-badge"]') as HTMLElement;
      expect(badgeSucceeded, 'RunDetail status badge (succeeded) must render').not.toBeNull();
      expect(badgeSucceeded.textContent).toBe('SUCCEEDED');
      expect(badgeSucceeded.style.color).toBe('var(--color-status-online)');
      expect(badgeSucceeded.style.borderColor).toBe('var(--color-status-online)');
      expect(badgeSucceeded.style.backgroundColor).toBe('var(--color-bg-subtle)');

      const bsFg = helperExtractVar(badgeSucceeded.style.color);
      const bsBg = helperExtractVar(badgeSucceeded.style.backgroundColor);
      const bsBorder = helperExtractVar(badgeSucceeded.style.borderColor);
      expect(getContrast(lightTokens[bsFg], lightTokens[bsBg]), 'Succeeded text contrast light >= 4.5:1').toBeGreaterThanOrEqual(4.5);
      expect(getContrast(darkTokens[bsFg], darkTokens[bsBg]), 'Succeeded text contrast dark >= 4.5:1').toBeGreaterThanOrEqual(4.5);
      expect(getContrast(lightTokens[bsBorder], lightTokens[bsBg]), 'Succeeded border contrast light >= 3.0:1').toBeGreaterThanOrEqual(3.0);
      expect(getContrast(darkTokens[bsBorder], darkTokens[bsBg]), 'Succeeded border contrast dark >= 3.0:1').toBeGreaterThanOrEqual(3.0);

      // CompletedAt in RunDetail
      const runCompletedAt = container.querySelector('[data-testid="run-detail-completed-at"]') as HTMLElement;
      expect(runCompletedAt, 'RunDetail completedAt must render').not.toBeNull();
      expect(runCompletedAt.style.color).toBe('var(--color-status-online)');
      const rcaFg = helperExtractVar(runCompletedAt.style.color);
      expect(getContrast(lightTokens[rcaFg], lightTokens['--color-bg-surface']), 'CompletedAt light text contrast >= 4.5:1').toBeGreaterThanOrEqual(4.5);
      expect(getContrast(darkTokens[rcaFg], darkTokens['--color-bg-surface']), 'CompletedAt dark text contrast >= 4.5:1').toBeGreaterThanOrEqual(4.5);

      // 2-b. RUNNING State
      await act(async () => {
        root.render(<RunDetail run={{ ...baseRun, state: 'running', status: 'running', completedAt: undefined }} onBack={() => {}} />);
      });
      const badgeRunning = container.querySelector('[data-testid="run-detail-status-badge"]') as HTMLElement;
      expect(badgeRunning.textContent).toBe('RUNNING');
      expect(badgeRunning.style.color).toBe('var(--color-brand-hover)');
      expect(badgeRunning.style.borderColor).toBe('var(--color-brand-hover)');
      const brFg = helperExtractVar(badgeRunning.style.color);
      const brBorder = helperExtractVar(badgeRunning.style.borderColor);
      expect(getContrast(lightTokens[brFg], lightTokens[bsBg]), 'Running text contrast light >= 4.5:1').toBeGreaterThanOrEqual(4.5);
      expect(getContrast(darkTokens[brFg], darkTokens[bsBg]), 'Running text contrast dark >= 4.5:1').toBeGreaterThanOrEqual(4.5);
      expect(getContrast(lightTokens[brBorder], lightTokens[bsBg]), 'Running border contrast light >= 3.0:1').toBeGreaterThanOrEqual(3.0);
      expect(getContrast(darkTokens[brBorder], darkTokens[bsBg]), 'Running border contrast dark >= 3.0:1').toBeGreaterThanOrEqual(3.0);

      // Lifecycle step ring outline indicator (F5)
      const currentStepIndicator = container.querySelector('[data-testid="run-step-indicator-running"]') as HTMLElement;
      expect(currentStepIndicator, 'Current step indicator must render').not.toBeNull();
      expect(currentStepIndicator.style.outlineColor || currentStepIndicator.style.outline, 'Current step ring outline must be bound to border-strong').toContain('var(--color-border-strong)');

      // 2-c. FAILED State
      await act(async () => {
        root.render(<RunDetail run={{ ...baseRun, state: 'failed', status: 'failed' }} onBack={() => {}} />);
      });
      const badgeFailed = container.querySelector('[data-testid="run-detail-status-badge"]') as HTMLElement;
      expect(badgeFailed.textContent).toBe('FAILED');
      expect(badgeFailed.style.color).toBe('var(--color-status-offline)');
      expect(badgeFailed.style.borderColor).toBe('var(--color-status-offline)');
      const bfFg = helperExtractVar(badgeFailed.style.color);
      const bfBorder = helperExtractVar(badgeFailed.style.borderColor);
      expect(getContrast(lightTokens[bfFg], lightTokens[bsBg]), 'Failed text contrast light >= 4.5:1').toBeGreaterThanOrEqual(4.5);
      expect(getContrast(darkTokens[bfFg], darkTokens[bsBg]), 'Failed text contrast dark >= 4.5:1').toBeGreaterThanOrEqual(4.5);
      expect(getContrast(lightTokens[bfBorder], lightTokens[bsBg]), 'Failed border contrast light >= 3.0:1').toBeGreaterThanOrEqual(3.0);
      expect(getContrast(darkTokens[bfBorder], darkTokens[bsBg]), 'Failed border contrast dark >= 3.0:1').toBeGreaterThanOrEqual(3.0);

      // CompletedAt in failed state
      const runCompletedAtFailed = container.querySelector('[data-testid="run-detail-completed-at"]') as HTMLElement;
      expect(runCompletedAtFailed, 'RunDetail completedAt (failed) must render').not.toBeNull();
      expect(runCompletedAtFailed.style.color).toBe('var(--color-status-offline)');
      expect(runCompletedAtFailed.style.color, 'Succeeded and failed completedAt must have distinct status tokens').not.toBe(runCompletedAt.style.color);
      const rcafFg = helperExtractVar(runCompletedAtFailed.style.color);
      expect(getContrast(lightTokens[rcafFg], lightTokens['--color-bg-surface']), 'CompletedAt (failed) light text contrast >= 4.5:1').toBeGreaterThanOrEqual(4.5);
      expect(getContrast(darkTokens[rcafFg], darkTokens['--color-bg-surface']), 'CompletedAt (failed) dark text contrast >= 4.5:1').toBeGreaterThanOrEqual(4.5);

      // 2-d. CANCELLED State
      await act(async () => {
        root.render(<RunDetail run={{ ...baseRun, state: 'cancelled', status: 'cancelled' }} onBack={() => {}} />);
      });
      const badgeCancelled = container.querySelector('[data-testid="run-detail-status-badge"]') as HTMLElement;
      expect(badgeCancelled.textContent).toBe('CANCELLED');
      expect(badgeCancelled.style.color).toBe('var(--color-status-neutral)');
      expect(badgeCancelled.style.borderColor).toBe('var(--color-border-strong)');
      const bcFg = helperExtractVar(badgeCancelled.style.color);
      const bcBorder = helperExtractVar(badgeCancelled.style.borderColor);
      expect(getContrast(lightTokens[bcFg], lightTokens[bsBg]), 'Cancelled text contrast light >= 4.5:1').toBeGreaterThanOrEqual(4.5);
      expect(getContrast(darkTokens[bcFg], darkTokens[bsBg]), 'Cancelled text contrast dark >= 4.5:1').toBeGreaterThanOrEqual(4.5);
      expect(getContrast(lightTokens[bcBorder], lightTokens[bsBg]), 'Cancelled border contrast light >= 3.0:1').toBeGreaterThanOrEqual(3.0);
      expect(getContrast(darkTokens[bcBorder], darkTokens[bsBg]), 'Cancelled border contrast dark >= 3.0:1').toBeGreaterThanOrEqual(3.0);

      // 2-e. RECOVERING State
      await act(async () => {
        root.render(<RunDetail run={{ ...baseRun, state: 'recovering', status: 'recovering' }} onBack={() => {}} />);
      });
      const badgeRecovering = container.querySelector('[data-testid="run-detail-status-badge"]') as HTMLElement;
      expect(badgeRecovering.textContent).toBe('RECOVERING');
      expect(badgeRecovering.style.color).toBe('var(--color-status-active)');
      expect(badgeRecovering.style.borderColor).toBe('var(--color-status-active)');
      const brecFg = helperExtractVar(badgeRecovering.style.color);
      const brecBorder = helperExtractVar(badgeRecovering.style.borderColor);
      expect(getContrast(lightTokens[brecFg], lightTokens[bsBg]), 'Recovering text contrast light >= 4.5:1').toBeGreaterThanOrEqual(4.5);
      expect(getContrast(darkTokens[brecFg], darkTokens[bsBg]), 'Recovering text contrast dark >= 4.5:1').toBeGreaterThanOrEqual(4.5);
      expect(getContrast(lightTokens[brecBorder], lightTokens[bsBg]), 'Recovering border contrast light >= 3.0:1').toBeGreaterThanOrEqual(3.0);
      expect(getContrast(darkTokens[brecBorder], darkTokens[bsBg]), 'Recovering border contrast dark >= 3.0:1').toBeGreaterThanOrEqual(3.0);

      // 2-f. AWAITING_APPROVAL State
      await act(async () => {
        root.render(<RunDetail run={{ ...baseRun, state: 'awaiting_approval', status: 'awaiting_approval' }} onBack={() => {}} />);
      });
      const badgeApproval = container.querySelector('[data-testid="run-detail-status-badge"]') as HTMLElement;
      expect(badgeApproval.textContent).toBe('AWAITING_APPROVAL');
      expect(badgeApproval.style.color).toBe('var(--color-status-degraded)');
      expect(badgeApproval.style.borderColor).toBe('var(--color-status-degraded)');
      const baFg = helperExtractVar(badgeApproval.style.color);
      const baBorder = helperExtractVar(badgeApproval.style.borderColor);
      expect(getContrast(lightTokens[baFg], lightTokens[bsBg]), 'Awaiting approval text contrast light >= 4.5:1').toBeGreaterThanOrEqual(4.5);
      expect(getContrast(darkTokens[baFg], darkTokens[bsBg]), 'Awaiting approval dark text contrast >= 4.5:1').toBeGreaterThanOrEqual(4.5);
      expect(getContrast(lightTokens[baBorder], lightTokens[bsBg]), 'Awaiting approval border contrast light >= 3.0:1').toBeGreaterThanOrEqual(3.0);
      expect(getContrast(darkTokens[baBorder], darkTokens[bsBg]), 'Awaiting approval border contrast dark >= 3.0:1').toBeGreaterThanOrEqual(3.0);

      // 2-g. Attempts Tab Exit Code Badges (exitCode 0 vs exitCode != 0)
      const attemptsTabBtn = Array.from(container.querySelectorAll('button')).find((b) =>
        b.textContent?.includes('시도 이력')
      );
      expect(attemptsTabBtn, 'Attempts tab button must exist').not.toBeNull();
      await act(async () => {
        attemptsTabBtn!.click();
      });
        await act(async () => {
          await Promise.resolve();
          await Promise.resolve();
        });
        const exit0 = container.querySelector('[data-testid="run-attempt-exit-1"]') as HTMLElement;
        const exit1 = container.querySelector('[data-testid="run-attempt-exit-2"]') as HTMLElement;
        expect(exit0, 'Attempt 1 exitCode 0 must render').not.toBeNull();
        expect(exit1, 'Attempt 2 exitCode 1 must render').not.toBeNull();
        expect(exit0.style.color).toBe('var(--color-status-online)');
        expect(exit1.style.color).toBe('var(--color-status-offline)');
        expect(exit0.style.color, 'ExitCode 0 and non-zero must have distinct status tokens').not.toBe(exit1.style.color);
        const exit0Fg = helperExtractVar(exit0.style.color);
        const exit1Fg = helperExtractVar(exit1.style.color);
        expect(getContrast(lightTokens[exit0Fg], lightTokens['--color-bg-surface']), 'ExitCode 0 light contrast >= 4.5:1').toBeGreaterThanOrEqual(4.5);
        expect(getContrast(darkTokens[exit0Fg], darkTokens['--color-bg-surface']), 'ExitCode 0 dark contrast >= 4.5:1').toBeGreaterThanOrEqual(4.5);
        expect(getContrast(lightTokens[exit1Fg], lightTokens['--color-bg-surface']), 'ExitCode 1 light contrast >= 4.5:1').toBeGreaterThanOrEqual(4.5);
        expect(getContrast(darkTokens[exit1Fg], darkTokens['--color-bg-surface']), 'ExitCode 1 dark contrast >= 4.5:1').toBeGreaterThanOrEqual(4.5);
    } finally {
      vi.unstubAllGlobals();
      if (typeof window !== 'undefined' && originalWindowFetch) {
        Object.defineProperty(window, 'fetch', { value: originalWindowFetch, writable: true, configurable: true });
      }
      act(() => {
        root.unmount();
      });
      container.remove();
    }
  });

  // 9h-2. [Card 213 / ACC-09] Dynamic AST Style-Pair Contrast Calculator & Strict Coverage Ratchet: SealRecordPanel & RunDetail
  it('ACC-09 / Card 213: Runs execution screens (SealRecordPanel & RunDetail) style objects maintain valid contrast pairings and reject 1:1 collisions and defective combinations', () => {
    interface Branch {
      cond: string;
      token: string;
    }

    function analyzeFile(relativePath: string) {
      const filePath = path.resolve(__dirname, '../src', relativePath);
      const content = fs.readFileSync(filePath, 'utf-8');
      const sf = ts.createSourceFile(path.basename(filePath), content, ts.ScriptTarget.Latest, true, ts.ScriptKind.TSX);

      function extractBranches(node: ts.Node): Branch[] {
        const branches: Branch[] = [];
        function collect(n: ts.Node, condPath: string) {
          if (ts.isConditionalExpression(n)) {
            const condText = n.condition.getText(sf).replace(/\s+/g, ' ');
            collect(n.whenTrue, condPath ? `${condPath} && ${condText}` : condText);
            collect(n.whenFalse, condPath ? `${condPath} && !(${condText})` : `!(${condText})`);
          } else if (ts.isTemplateExpression(n)) {
            for (const span of n.templateSpans) {
              collect(span.expression, condPath);
            }
          } else {
            const text = n.getText(sf);
            const m = text.match(/var\((--color-[a-z0-9-]+)\)/);
            if (m) {
              branches.push({ cond: condPath, token: m[1] });
            }
          }
        }
        collect(node, '');
        return branches;
      }

      function extractOpacity(node: ts.Node): number | null {
        if (ts.isNumericLiteral(node)) return parseFloat(node.text);
        if (ts.isConditionalExpression(node)) {
          const trueOp = extractOpacity(node.whenTrue);
          const falseOp = extractOpacity(node.whenFalse);
          if (trueOp !== null && falseOp !== null) return Math.min(trueOp, falseOp);
          return trueOp ?? falseOp;
        }
        return null;
      }

      let checkedPairs = 0;
      let checkedObjects = 0;
      let totalStyleAttrs = 0;
      let unboundColorObjects = 0;
      let checkedBorderObjects = 0;
      let checkedBorderPairs = 0;
      const violations: string[] = [];
      const containerBgs = ['--color-bg-surface', '--color-bg-subtle', '--color-bg-canvas'];

      function checkPair(bgToken: string, fgToken: string, pos: number, opacity: number = 1.0) {
        checkedPairs++;
        const { line } = sf.getLineAndCharacterOfPosition(pos);
        const lightBg = resolveTokenHex(bgToken, lightTokens);
        const lightFg = resolveTokenHex(fgToken, lightTokens);
        const darkBg = resolveTokenHex(bgToken, darkTokens);
        const darkFg = resolveTokenHex(fgToken, darkTokens);

        if (bgToken === fgToken && opacity >= 1.0) {
          violations.push(`L${line + 1}: 1:1 token collision between background and foreground (${bgToken})`);
          return;
        }

        if (bgToken.startsWith('--color-text-')) {
          violations.push(`L${line + 1}: Illegitimate background token derived from text token: ${bgToken}`);
          return;
        }

        const effectiveLFg = opacity < 1.0 && lightBg && lightFg ? blendRgba(parseHex(lightFg), opacity, lightBg) : lightFg;
        const effectiveDFg = opacity < 1.0 && darkBg && darkFg ? blendRgba(parseHex(darkFg), opacity, darkBg) : darkFg;

        if (lightBg && effectiveLFg) {
          const cr = getContrast(effectiveLFg, lightBg);
          if (cr < 4.5) {
            violations.push(`L${line + 1}: Light text contrast ${cr.toFixed(2)}:1 < 4.5:1 (${fgToken} on ${bgToken}${opacity < 1.0 ? ` opacity ${opacity.toFixed(2)}` : ''})`);
          }
        }
        if (darkBg && effectiveDFg) {
          const cr = getContrast(effectiveDFg, darkBg);
          if (cr < 4.5) {
            violations.push(`L${line + 1}: Dark text contrast ${cr.toFixed(2)}:1 < 4.5:1 (${fgToken} on ${bgToken}${opacity < 1.0 ? ` opacity ${opacity.toFixed(2)}` : ''})`);
          }
        }
      }

      function checkBorderPair(bgToken: string, borderToken: string, pos: number, opacity: number = 1.0) {
        checkedBorderPairs++;
        const { line } = sf.getLineAndCharacterOfPosition(pos);
        const lBg = resolveTokenHex(bgToken, lightTokens);
        const dBg = resolveTokenHex(bgToken, darkTokens);
        const lBorder = resolveTokenHex(borderToken, lightTokens);
        const dBorder = resolveTokenHex(borderToken, darkTokens);

        if (bgToken === borderToken && opacity >= 1.0) {
          violations.push(`L${line + 1}: Identical border-background token collision (1:1 contrast) detected: ${borderToken} on ${bgToken}`);
          return;
        }

        if (bgToken.startsWith('--color-text-')) {
          violations.push(`L${line + 1}: Illegitimate background token derived from text token: ${bgToken}`);
          return;
        }

        const effectiveLBorder = opacity < 1.0 && lBg && lBorder ? blendRgba(parseHex(lBorder), opacity, lBg) : lBorder;
        const effectiveDBorder = opacity < 1.0 && dBg && dBorder ? blendRgba(parseHex(dBorder), opacity, dBg) : dBorder;

        if (lBg && effectiveLBorder) {
          const cr = getContrast(effectiveLBorder, lBg);
          if (cr < 3.0) {
            violations.push(`L${line + 1}: Light border contrast ${cr.toFixed(2)}:1 < 3.0:1 (${borderToken} on ${bgToken}${opacity < 1.0 ? ` opacity ${opacity.toFixed(2)}` : ''})`);
          }
        }
        if (dBg && effectiveDBorder) {
          const cr = getContrast(effectiveDBorder, dBg);
          if (cr < 3.0) {
            violations.push(`L${line + 1}: Dark border contrast ${cr.toFixed(2)}:1 < 3.0:1 (${borderToken} on ${bgToken}${opacity < 1.0 ? ` opacity ${opacity.toFixed(2)}` : ''})`);
          }
        }
      }

      function traverseJsx(node: ts.Node, ancestorBgTokens: string[], ancestorFgTokens: string[], ancestorOpacity: number) {
        let currentBgTokens = ancestorBgTokens;
        let currentFgTokens = ancestorFgTokens;
        let currentOpacity = ancestorOpacity;

        if (ts.isJsxElement(node) || ts.isJsxSelfClosingElement(node)) {
          const opening = ts.isJsxElement(node) ? node.openingElement : node;
          const attrs = opening.attributes?.properties || [];
          let styleObj: ts.ObjectLiteralExpression | null = null;

          for (const attr of attrs) {
            if (ts.isJsxAttribute(attr) && attr.name.text === 'style') {
              totalStyleAttrs++;
              if (attr.initializer && ts.isJsxExpression(attr.initializer) && attr.initializer.expression && ts.isObjectLiteralExpression(attr.initializer.expression)) {
                styleObj = attr.initializer.expression;
              }
            }
          }

          if (styleObj) {
            let bgNode: ts.Expression | null = null;
            let fgNode: ts.Expression | null = null;
            let borderNode: ts.Expression | null = null;
            let opacityNode: ts.Expression | null = null;

            for (const p of styleObj.properties) {
              if (ts.isPropertyAssignment(p)) {
                const name = p.name.getText(sf);
                if (name === 'backgroundColor' || name === 'background') bgNode = p.initializer;
                if (name === 'color') fgNode = p.initializer;
                if (['border', 'borderColor', 'borderTop', 'borderBottom', 'borderLeft', 'borderRight'].includes(name)) {
                  borderNode = p.initializer;
                }
                if (name === 'opacity') opacityNode = p.initializer;
              }
            }

            if (opacityNode) {
              const elemOp = extractOpacity(opacityNode);
              if (elemOp !== null) currentOpacity = ancestorOpacity * elemOp;
            }

            const bgBranches = bgNode ? extractBranches(bgNode) : [];
            if (bgBranches.length > 0) {
              currentBgTokens = bgBranches.map(b => b.token);
              for (const b of bgBranches) {
                if (b.token.startsWith('--color-text-')) {
                  const { line } = sf.getLineAndCharacterOfPosition(bgNode!.getStart(sf));
                  violations.push(`L${line + 1}: Illegitimate background token derived from text token: ${b.token}`);
                }
              }
            }

            const fgBranches = fgNode ? extractBranches(fgNode) : [];
            if (fgBranches.length > 0) {
              currentFgTokens = fgBranches.map(b => b.token);
            }

            if (bgNode && fgNode) {
              checkedObjects++;
              for (const bgB of bgBranches) {
                for (const fgB of fgBranches) {
                  if (!bgB.cond || !fgB.cond || bgB.cond === fgB.cond) {
                    checkPair(bgB.token, fgB.token, styleObj.getStart(sf), currentOpacity);
                  }
                }
              }
            } else if (!bgNode && fgNode) {
              unboundColorObjects++;
              const effectiveBgs = ancestorBgTokens.length > 0 ? ancestorBgTokens : containerBgs;
              for (const fgB of fgBranches) {
                for (const cBg of effectiveBgs) {
                  checkPair(cBg, fgB.token, styleObj.getStart(sf), currentOpacity);
                }
              }
            } else if (opacityNode && !fgNode && currentFgTokens.length > 0) {
              unboundColorObjects++;
              const effectiveBgs = currentBgTokens.length > 0 ? currentBgTokens : (ancestorBgTokens.length > 0 ? ancestorBgTokens : containerBgs);
              for (const fgT of currentFgTokens) {
                for (const cBg of effectiveBgs) {
                  checkPair(cBg, fgT, styleObj.getStart(sf), currentOpacity);
                }
              }
            }

            if (borderNode) {
              const borderBranches = extractBranches(borderNode);
              if (borderBranches.length > 0) {
                checkedBorderObjects++;
                if (bgNode) {
                  for (const bB of borderBranches) {
                    for (const bgB of bgBranches) {
                      if (!bB.cond || !bgB.cond || bB.cond === bgB.cond) {
                        checkBorderPair(bgB.token, bB.token, styleObj.getStart(sf), currentOpacity);
                      }
                    }
                  }
                } else {
                  const effectiveBgs = ancestorBgTokens.length > 0 ? ancestorBgTokens : containerBgs;
                  for (const bB of borderBranches) {
                    for (const cBg of effectiveBgs) {
                      checkBorderPair(cBg, bB.token, styleObj.getStart(sf), currentOpacity);
                    }
                  }
                }
              }
            }
          }
        }

        ts.forEachChild(node, child => traverseJsx(child, currentBgTokens, currentFgTokens, currentOpacity));
      }

      traverseJsx(sf, [], [], 1.0);

      return {
        totalStyleAttrs,
        checkedObjects,
        checkedPairs,
        unboundColorObjects,
        coveredColorObjects: checkedObjects + unboundColorObjects,
        checkedBorderObjects,
        checkedBorderPairs,
        violations,
      };
    }

    const sealStats = analyzeFile('features/runs/SealRecordPanel.tsx');
    const runStats = analyzeFile('features/runs/RunDetail.tsx');
    // Ratchet assertions for SealRecordPanel: 76 of 133 style declarations carry color/background properties (100% audited)
    expect(sealStats.totalStyleAttrs, 'Total style attributes in SealRecordPanel must be exactly 133').toBe(133);
    expect(sealStats.checkedObjects, 'Explicit style objects in SealRecordPanel must be exactly 17').toBe(17);
    expect(sealStats.checkedPairs, 'Evaluated pairs in SealRecordPanel must be exactly 78').toBe(78);
    expect(sealStats.unboundColorObjects, 'Unbound color objects in SealRecordPanel must be exactly 59').toBe(59);
    expect(sealStats.coveredColorObjects, 'Total covered color objects in SealRecordPanel must be exactly 76').toBe(76);
    expect(sealStats.checkedBorderObjects, 'Border objects in SealRecordPanel must be exactly 36').toBe(36);
    expect(sealStats.checkedBorderPairs, 'Border pairs in SealRecordPanel must be exactly 38').toBe(38);
    expect(sealStats.violations, `SealRecordPanel violations:\n${sealStats.violations.join('\n')}`).toEqual([]);

    // Ratchet assertions for RunDetail: 103 of 229 style declarations carry color/background properties (100% audited)
    expect(runStats.totalStyleAttrs, 'Total style attributes in RunDetail must be exactly 229').toBe(229);
    expect(runStats.checkedObjects, 'Explicit style objects in RunDetail must be exactly 29').toBe(29);
    expect(runStats.checkedPairs, 'Evaluated pairs in RunDetail must be exactly 135').toBe(135);
    expect(runStats.unboundColorObjects, 'Unbound color objects in RunDetail must be exactly 74').toBe(74);
    expect(runStats.coveredColorObjects, 'Total covered color objects in RunDetail must be exactly 103').toBe(103);
    expect(runStats.checkedBorderObjects, 'Border objects in RunDetail must be exactly 45').toBe(45);
    expect(runStats.checkedBorderPairs, 'Border pairs in RunDetail must be exactly 56').toBe(56);
    expect(runStats.violations, `RunDetail violations:\n${runStats.violations.join('\n')}`).toEqual([]);
  });

  // 9i. [Card 215 / ACC-09] Component DOM Rendering Verification: RunList binds to design tokens with dynamic contrast verification
  it('ACC-09 / Card 215: RunList component DOM rendering binds foregrounds and container backgrounds to design tokens with dynamic contrast verification', async () => {
    const container = document.createElement('div');
    document.body.appendChild(container);
    const root = createRoot(container);

    const sampleRuns: RunItem[] = [
      { id: 'run_draft_01', projectId: 'prj_01', state: 'draft', objective: '초안 작업', requestedBy: 'user_1', createdAt: '2026-10-02T01:00:00Z' },
      { id: 'run_val_01', projectId: 'prj_01', state: 'validated', objective: '검증 작업', requestedBy: 'user_1', createdAt: '2026-10-02T02:00:00Z' },
      { id: 'run_plan_01', projectId: 'prj_01', state: 'planned', objective: '계획 수립', requestedBy: 'user_1', createdAt: '2026-10-02T03:00:00Z' },
      { id: 'run_await_01', projectId: 'prj_01', state: 'awaiting_approval', objective: '승인 대기', requestedBy: 'user_1', createdAt: '2026-10-02T04:00:00Z' },
      { id: 'run_sched_01', projectId: 'prj_01', state: 'scheduled', objective: '스케줄됨', requestedBy: 'user_1', createdAt: '2026-10-02T05:00:00Z' },
      { id: 'run_run_01', projectId: 'prj_01', state: 'running', objective: '실행 중', requestedBy: 'user_1', createdAt: '2026-10-02T06:00:00Z', stateUpdatedAt: '2026-10-02T06:10:00Z' },
      { id: 'run_ver_01', projectId: 'prj_01', state: 'verifying', objective: '결과 검증', requestedBy: 'user_1', createdAt: '2026-10-02T07:00:00Z' },
      { id: 'run_rec_01', projectId: 'prj_01', state: 'recovering', objective: '복구 중', requestedBy: 'user_1', createdAt: '2026-10-02T08:00:00Z', resourceReleasePending: true },
      { id: 'run_succ_01', projectId: 'prj_01', state: 'succeeded', objective: '성공 작업', requestedBy: 'user_1', createdAt: '2026-10-02T09:00:00Z', completedAt: '2026-10-02T09:15:00Z', parentId: 'run_parent_999999999', shardIndex: 2 },
      { id: 'run_fail_01', projectId: 'prj_01', state: 'failed', objective: '실패 작업', requestedBy: 'user_1', createdAt: '2026-10-02T10:00:00Z', completedAt: '2026-10-02T10:05:00Z', childRunIds: ['run_c1', 'run_c2'] },
      { id: 'run_canc_01', projectId: 'prj_01', state: 'cancelled', objective: '취소 작업', requestedBy: 'user_1', createdAt: '2026-10-02T11:00:00Z' },
    ];

    try {
      // 1. Render RunList with 11 states and active warning banner
      await act(async () => {
        root.render(
          <RunList
            runs={sampleRuns}
            isLoading={false}
            runsState="error"
            runError="503 Service Unavailable"
            lastFetchedAt={new Date('2026-10-02T08:00:00Z')}
            onRefresh={vi.fn()}
            onSelectRun={vi.fn()}
          />
        );
      });

      // 1-a. Stale Warning Banner
      const staleWarning = container.querySelector('[data-testid="run-stale-warning"]') as HTMLElement;
      expect(staleWarning, 'RunList stale warning banner must render').not.toBeNull();
      expect(staleWarning.style.backgroundColor).toBe('var(--color-bg-subtle)');
      expect(staleWarning.style.borderColor).toBe('var(--color-status-offline)');
      expect(staleWarning.style.color).toBe('var(--color-status-offline)');
      const swFg = helperExtractVar(staleWarning.style.color);
      const swBg = helperExtractVar(staleWarning.style.backgroundColor);
      const swBorder = helperExtractVar(staleWarning.style.borderColor);
      expect(getContrast(lightTokens[swFg], lightTokens[swBg]), 'Stale warning light contrast >= 4.5:1').toBeGreaterThanOrEqual(4.5);
      expect(getContrast(darkTokens[swFg], darkTokens[swBg]), 'Stale warning dark contrast >= 4.5:1').toBeGreaterThanOrEqual(4.5);
      expect(getContrast(lightTokens[swBorder], lightTokens[swBg]), 'Stale warning border light contrast >= 3.0:1').toBeGreaterThanOrEqual(3.0);
      expect(getContrast(darkTokens[swBorder], darkTokens[swBg]), 'Stale warning border dark contrast >= 3.0:1').toBeGreaterThanOrEqual(3.0);

      // 1-b. Filter pill 'ALL'
      const filterAll = container.querySelector('[data-testid="run-filter-pill-ALL"]') as HTMLElement;
      expect(filterAll, 'ALL filter pill must render').not.toBeNull();
      expect(filterAll.style.backgroundColor).toBe('var(--color-brand-primary-bg)');
      expect(filterAll.style.color).toBe('var(--color-brand-primary-fg)');
      const faFg = helperExtractVar(filterAll.style.color);
      const faBg = helperExtractVar(filterAll.style.backgroundColor);
      expect(getContrast(lightTokens[faFg], lightTokens[faBg]), 'Filter ALL light text contrast >= 4.5:1').toBeGreaterThanOrEqual(4.5);
      expect(getContrast(darkTokens[faFg], darkTokens[faBg]), 'Filter ALL dark text contrast >= 4.5:1').toBeGreaterThanOrEqual(4.5);
      expect(filterAll.textContent, 'Filter ALL textContent must contain 전체').toContain('전체');

      // 1-c. Filter pill unselected (e.g. running)
      const filterRunning = container.querySelector('[data-testid="run-filter-pill-running"]') as HTMLElement;
      expect(filterRunning, 'Running filter pill must render').not.toBeNull();
      expect(filterRunning.textContent, 'Running filter pill must have non-color text label').toContain('실행 중');
      expect(filterRunning.style.color).toBe('var(--color-text-muted)');
      expect(filterRunning.style.backgroundColor).toBe('var(--color-bg-subtle)');
      expect(filterRunning.style.borderColor).toBe('var(--color-border-subtle)');
      const frFg = helperExtractVar(filterRunning.style.color);
      const frBg = helperExtractVar(filterRunning.style.backgroundColor);
      const frBorder = helperExtractVar(filterRunning.style.borderColor);
      expect(getContrast(lightTokens[frFg], lightTokens[frBg]), 'Filter running light text contrast >= 4.5:1').toBeGreaterThanOrEqual(4.5);
      expect(getContrast(darkTokens[frFg], darkTokens[frBg]), 'Filter running dark text contrast >= 4.5:1').toBeGreaterThanOrEqual(4.5);
      expect(getContrast(lightTokens[frBorder], lightTokens[frBg]), 'Filter running border light contrast >= 3.0:1').toBeGreaterThanOrEqual(3.0);
      expect(getContrast(darkTokens[frBorder], darkTokens[frBg]), 'Filter running border dark contrast >= 3.0:1').toBeGreaterThanOrEqual(3.0);

      // 1-d. Table status badges for 11 states
      const badgeSucceeded = container.querySelector('[data-testid="run-status-badge-run_succ_01"]') as HTMLElement;
      const badgeRunning = container.querySelector('[data-testid="run-status-badge-run_run_01"]') as HTMLElement;
      const badgeFailed = container.querySelector('[data-testid="run-status-badge-run_fail_01"]') as HTMLElement;
      const badgeCancelled = container.querySelector('[data-testid="run-status-badge-run_canc_01"]') as HTMLElement;
      const badgeRecovering = container.querySelector('[data-testid="run-status-badge-run_rec_01"]') as HTMLElement;
      const badgeAwaiting = container.querySelector('[data-testid="run-status-badge-run_await_01"]') as HTMLElement;
      const badgeDraft = container.querySelector('[data-testid="run-status-badge-run_draft_01"]') as HTMLElement;
      const badgeValidated = container.querySelector('[data-testid="run-status-badge-run_val_01"]') as HTMLElement;
      const badgePlanned = container.querySelector('[data-testid="run-status-badge-run_plan_01"]') as HTMLElement;
      const badgeScheduled = container.querySelector('[data-testid="run-status-badge-run_sched_01"]') as HTMLElement;
      const badgeVerifying = container.querySelector('[data-testid="run-status-badge-run_ver_01"]') as HTMLElement;

      expect(badgeSucceeded?.style.color).toBe('var(--color-status-online)');
      expect(badgeSucceeded?.style.borderColor).toBe('var(--color-status-online)');
      expect(badgeSucceeded?.style.backgroundColor).toBe('var(--color-bg-subtle)');
      expect(badgeSucceeded.textContent).toBe('성공');

      expect(badgeRunning?.style.color).toBe('var(--color-brand-hover)');
      expect(badgeRunning?.style.borderColor).toBe('var(--color-brand-hover)');
      expect(badgeRunning?.style.backgroundColor).toBe('var(--color-bg-subtle)');
      expect(badgeRunning.textContent).toBe('실행 중');

      expect(badgeFailed?.style.color).toBe('var(--color-status-offline)');
      expect(badgeFailed?.style.borderColor).toBe('var(--color-status-offline)');
      expect(badgeFailed?.style.backgroundColor).toBe('var(--color-bg-subtle)');
      expect(badgeFailed.textContent).toBe('실패');

      expect(badgeCancelled?.style.color).toBe('var(--color-status-neutral)');
      expect(badgeCancelled?.style.borderColor).toBe('var(--color-border-strong)');
      expect(badgeCancelled?.style.backgroundColor).toBe('var(--color-bg-subtle)');
      expect(badgeCancelled.textContent).toBe('취소됨');

      expect(badgeRecovering?.style.color).toBe('var(--color-status-active)');
      expect(badgeRecovering?.style.borderColor).toBe('var(--color-status-active)');
      expect(badgeRecovering?.style.backgroundColor).toBe('var(--color-bg-subtle)');
      expect(badgeRecovering.textContent).toBe('복구 중');

      expect(badgeAwaiting?.style.color).toBe('var(--color-status-degraded)');
      expect(badgeAwaiting?.style.borderColor).toBe('var(--color-status-degraded)');
      expect(badgeAwaiting?.style.backgroundColor).toBe('var(--color-bg-subtle)');
      expect(badgeAwaiting.textContent).toBe('승인 대기');

      expect(badgeDraft?.style.color).toBe('var(--color-text-secondary)');
      expect(badgeDraft?.style.borderColor).toBe('var(--color-border-subtle)');
      expect(badgeDraft?.style.backgroundColor).toBe('var(--color-bg-subtle)');
      expect(badgeDraft.textContent).toBe('초안');

      expect(badgeValidated?.style.color).toBe('var(--color-text-secondary)');
      expect(badgeValidated?.style.borderColor).toBe('var(--color-border-subtle)');
      expect(badgeValidated?.style.backgroundColor).toBe('var(--color-bg-subtle)');
      expect(badgeValidated.textContent).toBe('검증됨');

      expect(badgePlanned?.style.color).toBe('var(--color-text-secondary)');
      expect(badgePlanned?.style.borderColor).toBe('var(--color-border-subtle)');
      expect(badgePlanned?.style.backgroundColor).toBe('var(--color-bg-subtle)');
      expect(badgePlanned.textContent).toBe('계획 수립');

      expect(badgeScheduled?.style.color).toBe('var(--color-text-secondary)');
      expect(badgeScheduled?.style.borderColor).toBe('var(--color-border-subtle)');
      expect(badgeScheduled?.style.backgroundColor).toBe('var(--color-bg-subtle)');
      expect(badgeScheduled.textContent).toBe('스케줄됨');

      expect(badgeVerifying?.style.color).toBe('var(--color-text-secondary)');
      expect(badgeVerifying?.style.borderColor).toBe('var(--color-border-subtle)');
      expect(badgeVerifying?.style.backgroundColor).toBe('var(--color-bg-subtle)');
      expect(badgeVerifying.textContent).toBe('결과 검증');

      // Opacity guard on all badges: must not have degraded opacity (kills C1)
      const allBadges = [
        badgeDraft, badgeValidated, badgePlanned, badgeAwaiting,
        badgeScheduled, badgeRunning, badgeVerifying, badgeRecovering,
        badgeSucceeded, badgeFailed, badgeCancelled
      ];
      for (const b of allBadges) {
        expect(b.style.opacity || '1', 'Badge must not have degraded opacity').toBe('1');
      }

      // Strict distinction assertions: recovering and running tokens must be UNIQUE among all 11 states (F2)
      expect(badgeRecovering.style.color, 'recovering must not collide with planned').not.toBe(badgePlanned.style.color);
      expect(badgeRunning.style.color, 'running must not collide with scheduled').not.toBe(badgeScheduled.style.color);
      expect(badgeRecovering.style.color, 'recovering must not collide with running').not.toBe(badgeRunning.style.color);
      expect(badgeRecovering.style.color, 'recovering must not collide with succeeded').not.toBe(badgeSucceeded.style.color);
      expect(badgeSucceeded.style.color, 'Succeeded and failed must not have identical tokens').not.toBe(badgeFailed.style.color);
      expect(badgeSucceeded.style.color, 'Succeeded and running must not have identical tokens').not.toBe(badgeRunning.style.color);
      expect(badgeFailed.style.color, 'Failed and cancelled must not have identical tokens').not.toBe(badgeCancelled.style.color);
      expect(badgeAwaiting.style.color, 'Awaiting approval and succeeded must not have identical tokens').not.toBe(badgeSucceeded.style.color);
      expect(badgeCancelled.style.borderColor, 'cancelled border must use border-strong').toBe('var(--color-border-strong)');

      const preparationBadges = [badgeDraft, badgeValidated, badgePlanned, badgeScheduled, badgeVerifying];
      for (const pb of preparationBadges) {
        expect(pb.style.color, 'Preparation state must not collide with recovering').not.toBe('var(--color-status-active)');
        expect(pb.style.color, 'Preparation state must not collide with running').not.toBe('var(--color-brand-hover)');
      }

      // Contrast assertions for all 11 states on subtle background (both text and border)
      const bSuccFg = helperExtractVar(badgeSucceeded.style.color);
      const bFailFg = helperExtractVar(badgeFailed.style.color);
      const bRunFg = helperExtractVar(badgeRunning.style.color);
      const bRecFg = helperExtractVar(badgeRecovering.style.color);
      const bCancFg = helperExtractVar(badgeCancelled.style.color);
      const bAwFg = helperExtractVar(badgeAwaiting.style.color);
      const bDraftFg = helperExtractVar(badgeDraft.style.color);
      const bValFg = helperExtractVar(badgeValidated.style.color);
      const bPlanFg = helperExtractVar(badgePlanned.style.color);
      const bSchedFg = helperExtractVar(badgeScheduled.style.color);
      const bVerFg = helperExtractVar(badgeVerifying.style.color);

      expect(getContrast(lightTokens[bSuccFg], lightTokens['--color-bg-subtle']), 'Succeeded badge light contrast >= 4.5:1').toBeGreaterThanOrEqual(4.5);
      expect(getContrast(darkTokens[bSuccFg], darkTokens['--color-bg-subtle']), 'Succeeded badge dark contrast >= 4.5:1').toBeGreaterThanOrEqual(4.5);
      expect(getContrast(lightTokens[bFailFg], lightTokens['--color-bg-subtle']), 'Failed badge light contrast >= 4.5:1').toBeGreaterThanOrEqual(4.5);
      expect(getContrast(darkTokens[bFailFg], darkTokens['--color-bg-subtle']), 'Failed badge dark contrast >= 4.5:1').toBeGreaterThanOrEqual(4.5);
      expect(getContrast(lightTokens[bRunFg], lightTokens['--color-bg-subtle']), 'Running badge light contrast >= 4.5:1').toBeGreaterThanOrEqual(4.5);
      expect(getContrast(darkTokens[bRunFg], darkTokens['--color-bg-subtle']), 'Running badge dark contrast >= 4.5:1').toBeGreaterThanOrEqual(4.5);
      expect(getContrast(lightTokens[bRecFg], lightTokens['--color-bg-subtle']), 'Recovering badge light contrast >= 4.5:1').toBeGreaterThanOrEqual(4.5);
      expect(getContrast(darkTokens[bRecFg], darkTokens['--color-bg-subtle']), 'Recovering badge dark contrast >= 4.5:1').toBeGreaterThanOrEqual(4.5);
      expect(getContrast(lightTokens[bCancFg], lightTokens['--color-bg-subtle']), 'Cancelled badge light contrast >= 4.5:1').toBeGreaterThanOrEqual(4.5);
      expect(getContrast(darkTokens[bCancFg], darkTokens['--color-bg-subtle']), 'Cancelled badge dark contrast >= 4.5:1').toBeGreaterThanOrEqual(4.5);
      expect(getContrast(lightTokens[bAwFg], lightTokens['--color-bg-subtle']), 'Awaiting approval badge light contrast >= 4.5:1').toBeGreaterThanOrEqual(4.5);
      expect(getContrast(darkTokens[bAwFg], darkTokens['--color-bg-subtle']), 'Awaiting approval badge dark contrast >= 4.5:1').toBeGreaterThanOrEqual(4.5);
      expect(getContrast(lightTokens[bDraftFg], lightTokens['--color-bg-subtle']), 'Draft badge light contrast >= 4.5:1').toBeGreaterThanOrEqual(4.5);
      expect(getContrast(darkTokens[bDraftFg], darkTokens['--color-bg-subtle']), 'Draft badge dark contrast >= 4.5:1').toBeGreaterThanOrEqual(4.5);
      expect(getContrast(lightTokens[bValFg], lightTokens['--color-bg-subtle']), 'Validated badge light contrast >= 4.5:1').toBeGreaterThanOrEqual(4.5);
      expect(getContrast(darkTokens[bValFg], darkTokens['--color-bg-subtle']), 'Validated badge dark contrast >= 4.5:1').toBeGreaterThanOrEqual(4.5);
      expect(getContrast(lightTokens[bPlanFg], lightTokens['--color-bg-subtle']), 'Planned badge light contrast >= 4.5:1').toBeGreaterThanOrEqual(4.5);
      expect(getContrast(darkTokens[bPlanFg], darkTokens['--color-bg-subtle']), 'Planned badge dark contrast >= 4.5:1').toBeGreaterThanOrEqual(4.5);
      expect(getContrast(lightTokens[bSchedFg], lightTokens['--color-bg-subtle']), 'Scheduled badge light contrast >= 4.5:1').toBeGreaterThanOrEqual(4.5);
      expect(getContrast(darkTokens[bSchedFg], darkTokens['--color-bg-subtle']), 'Scheduled badge dark contrast >= 4.5:1').toBeGreaterThanOrEqual(4.5);
      expect(getContrast(lightTokens[bVerFg], lightTokens['--color-bg-subtle']), 'Verifying badge light contrast >= 4.5:1').toBeGreaterThanOrEqual(4.5);
      expect(getContrast(darkTokens[bVerFg], darkTokens['--color-bg-subtle']), 'Verifying badge dark contrast >= 4.5:1').toBeGreaterThanOrEqual(4.5);

      // Border contrast assertions for all 11 states
      const bSuccBd = helperExtractVar(badgeSucceeded.style.borderColor);
      const bFailBd = helperExtractVar(badgeFailed.style.borderColor);
      const bRunBd = helperExtractVar(badgeRunning.style.borderColor);
      const bRecBd = helperExtractVar(badgeRecovering.style.borderColor);
      const bCancBd = helperExtractVar(badgeCancelled.style.borderColor);
      const bAwBd = helperExtractVar(badgeAwaiting.style.borderColor);
      const bDraftBd = helperExtractVar(badgeDraft.style.borderColor);
      const bValBd = helperExtractVar(badgeValidated.style.borderColor);
      const bPlanBd = helperExtractVar(badgePlanned.style.borderColor);
      const bSchedBd = helperExtractVar(badgeScheduled.style.borderColor);
      const bVerBd = helperExtractVar(badgeVerifying.style.borderColor);

      expect(getContrast(lightTokens[bSuccBd], lightTokens['--color-bg-subtle']), 'Succeeded border light contrast >= 3.0:1').toBeGreaterThanOrEqual(3.0);
      expect(getContrast(darkTokens[bSuccBd], darkTokens['--color-bg-subtle']), 'Succeeded border dark contrast >= 3.0:1').toBeGreaterThanOrEqual(3.0);
      expect(getContrast(lightTokens[bFailBd], lightTokens['--color-bg-subtle']), 'Failed border light contrast >= 3.0:1').toBeGreaterThanOrEqual(3.0);
      expect(getContrast(darkTokens[bFailBd], darkTokens['--color-bg-subtle']), 'Failed border dark contrast >= 3.0:1').toBeGreaterThanOrEqual(3.0);
      expect(getContrast(lightTokens[bRunBd], lightTokens['--color-bg-subtle']), 'Running border light contrast >= 3.0:1').toBeGreaterThanOrEqual(3.0);
      expect(getContrast(darkTokens[bRunBd], darkTokens['--color-bg-subtle']), 'Running border dark contrast >= 3.0:1').toBeGreaterThanOrEqual(3.0);
      expect(getContrast(lightTokens[bRecBd], lightTokens['--color-bg-subtle']), 'Recovering border light contrast >= 3.0:1').toBeGreaterThanOrEqual(3.0);
      expect(getContrast(darkTokens[bRecBd], darkTokens['--color-bg-subtle']), 'Recovering border dark contrast >= 3.0:1').toBeGreaterThanOrEqual(3.0);
      expect(getContrast(lightTokens[bCancBd], lightTokens['--color-bg-subtle']), 'Cancelled border light contrast >= 3.0:1').toBeGreaterThanOrEqual(3.0);
      expect(getContrast(darkTokens[bCancBd], darkTokens['--color-bg-subtle']), 'Cancelled border dark contrast >= 3.0:1').toBeGreaterThanOrEqual(3.0);
      expect(getContrast(lightTokens[bAwBd], lightTokens['--color-bg-subtle']), 'Awaiting approval border light contrast >= 3.0:1').toBeGreaterThanOrEqual(3.0);
      expect(getContrast(darkTokens[bAwBd], darkTokens['--color-bg-subtle']), 'Awaiting approval border dark contrast >= 3.0:1').toBeGreaterThanOrEqual(3.0);
      expect(getContrast(lightTokens[bDraftBd], lightTokens['--color-bg-subtle']), 'Draft border light contrast >= 3.0:1').toBeGreaterThanOrEqual(3.0);
      expect(getContrast(darkTokens[bDraftBd], darkTokens['--color-bg-subtle']), 'Draft border dark contrast >= 3.0:1').toBeGreaterThanOrEqual(3.0);
      expect(getContrast(lightTokens[bValBd], lightTokens['--color-bg-subtle']), 'Validated border light contrast >= 3.0:1').toBeGreaterThanOrEqual(3.0);
      expect(getContrast(darkTokens[bValBd], darkTokens['--color-bg-subtle']), 'Validated border dark contrast >= 3.0:1').toBeGreaterThanOrEqual(3.0);
      expect(getContrast(lightTokens[bPlanBd], lightTokens['--color-bg-subtle']), 'Planned border light contrast >= 3.0:1').toBeGreaterThanOrEqual(3.0);
      expect(getContrast(darkTokens[bPlanBd], darkTokens['--color-bg-subtle']), 'Planned border dark contrast >= 3.0:1').toBeGreaterThanOrEqual(3.0);
      expect(getContrast(lightTokens[bSchedBd], lightTokens['--color-bg-subtle']), 'Scheduled border light contrast >= 3.0:1').toBeGreaterThanOrEqual(3.0);
      expect(getContrast(darkTokens[bSchedBd], darkTokens['--color-bg-subtle']), 'Scheduled border dark contrast >= 3.0:1').toBeGreaterThanOrEqual(3.0);
      expect(getContrast(lightTokens[bVerBd], lightTokens['--color-bg-subtle']), 'Verifying border light contrast >= 3.0:1').toBeGreaterThanOrEqual(3.0);
      expect(getContrast(darkTokens[bVerBd], darkTokens['--color-bg-subtle']), 'Verifying border dark contrast >= 3.0:1').toBeGreaterThanOrEqual(3.0);

      // 1-e. Shard and Parent badges
      const shardBadge = container.querySelector('[data-testid="run-shard-badge-run_succ_01"]') as HTMLElement;
      expect(shardBadge, 'Shard badge must render').not.toBeNull();
      expect(shardBadge.style.color).toBe('var(--color-brand-hover)');
      expect(shardBadge.style.borderColor).toBe('var(--color-brand-hover)');
      expect(shardBadge.style.backgroundColor).toBe('var(--color-bg-subtle)');

      const parentBadge = container.querySelector('[data-testid="run-parent-shard-badge-run_fail_01"]') as HTMLElement;
      expect(parentBadge, 'Parent shard badge must render').not.toBeNull();
      expect(parentBadge.style.color).toBe('var(--color-status-active)');
      expect(parentBadge.style.borderColor).toBe('var(--color-status-active)');
      expect(parentBadge.style.backgroundColor).toBe('var(--color-bg-subtle)');

      // 1-f. Resource release pending badge
      const releaseBadge = container.querySelector('[data-testid="run-resource-release-badge-run_rec_01"]') as HTMLElement;
      expect(releaseBadge, 'Resource release pending badge must render').not.toBeNull();
      expect(releaseBadge.style.color).toBe('var(--color-status-degraded)');
      expect(releaseBadge.style.borderColor).toBe('var(--color-status-degraded)');
      expect(releaseBadge.style.backgroundColor).toBe('var(--color-bg-subtle)');
      expect(releaseBadge.textContent).toContain('⏳');
      expect(releaseBadge.textContent).toContain('자원 반환 대기');

      // 1-g. Link button & stateUpdatedAt
      const selectBtn = container.querySelector('[data-testid="run-select-btn-run_draft_01"]') as HTMLElement;
      expect(selectBtn, 'Select run button must render').not.toBeNull();
      expect(selectBtn.style.color).toBe('var(--color-brand-hover)');

      const stateUpdated = container.querySelector('[data-testid="run-state-updated-at-run_run_01"]') as HTMLElement;
      expect(stateUpdated, 'State updated at must render').not.toBeNull();
      expect(stateUpdated.style.color).toBe('var(--color-brand-hover)');

      // 1-h. CompletedAt in succeeded and failed states
      const succCompleted = container.querySelector('[data-testid="run-completed-at-run_succ_01"]') as HTMLElement;
      const failCompleted = container.querySelector('[data-testid="run-completed-at-run_fail_01"]') as HTMLElement;
      expect(succCompleted, 'Succeeded completedAt must render').not.toBeNull();
      expect(failCompleted, 'Failed completedAt must render').not.toBeNull();
      expect(succCompleted.style.color).toBe('var(--color-status-online)');
      expect(failCompleted.style.color).toBe('var(--color-status-offline)');
      expect(succCompleted.style.color, 'Succeeded and failed completedAt must have distinct status tokens').not.toBe(failCompleted.style.color);

      // 2. Fetch error empty state
      await act(async () => {
        root.render(
          <RunList
            runs={[]}
            isLoading={false}
            runsState="error"
            runError="Network down"
            onRefresh={vi.fn()}
          />
        );
      });

      const fetchErrorState = container.querySelector('[data-testid="run-fetch-error-state"]') as HTMLElement;
      expect(fetchErrorState, 'Fetch error state container must render').not.toBeNull();
      expect(fetchErrorState.style.backgroundColor).toBe('var(--color-bg-subtle)');
      expect(fetchErrorState.style.borderColor).toBe('var(--color-status-offline)');

      const retryBtn = container.querySelector('[data-testid="run-error-retry-btn"]') as HTMLElement;
      expect(retryBtn, 'Retry button must render').not.toBeNull();
      expect(retryBtn.style.backgroundColor).toBe('var(--color-status-offline-bg)');
      expect(retryBtn.style.color).toBe('var(--color-brand-primary-fg)');
      const rbFg = helperExtractVar(retryBtn.style.color);
      const rbBg = helperExtractVar(retryBtn.style.backgroundColor);
      expect(getContrast(lightTokens[rbFg], lightTokens[rbBg]), 'Retry button light contrast >= 4.5:1').toBeGreaterThanOrEqual(4.5);
      expect(getContrast(darkTokens[rbFg], darkTokens[rbBg]), 'Retry button dark contrast >= 4.5:1').toBeGreaterThanOrEqual(4.5);
    } finally {
      act(() => {
        root.unmount();
      });
      container.remove();
    }
  });

  // 9i-2. [Card 215 / ACC-09] Dynamic AST Style-Pair Contrast Calculator & Strict Coverage Ratchet: RunList
  it('ACC-09 / Card 215: RunList style objects maintain valid contrast pairings and reject 1:1 collisions and defective combinations', () => {
    interface Branch {
      cond: string;
      token: string;
    }

    function analyzeFile(relativePath: string) {
      const filePath = path.resolve(__dirname, '../src', relativePath);
      const content = fs.readFileSync(filePath, 'utf-8');
      const sf = ts.createSourceFile(path.basename(filePath), content, ts.ScriptTarget.Latest, true, ts.ScriptKind.TSX);

      function extractBranches(node: ts.Node): Branch[] {
        const branches: Branch[] = [];
        function collect(n: ts.Node, condPath: string) {
          if (ts.isConditionalExpression(n)) {
            const condText = n.condition.getText(sf).replace(/\s+/g, ' ');
            collect(n.whenTrue, condPath ? `${condPath} && ${condText}` : condText);
            collect(n.whenFalse, condPath ? `${condPath} && !(${condText})` : `!(${condText})`);
          } else if (ts.isTemplateExpression(n)) {
            for (const span of n.templateSpans) {
              collect(span.expression, condPath);
            }
          } else {
            const text = n.getText(sf);
            const m = text.match(/var\((--color-[a-z0-9-]+)\)/);
            if (m) {
              branches.push({ cond: condPath, token: m[1] });
            }
          }
        }
        collect(node, '');
        return branches;
      }

      function extractOpacity(node: ts.Node): number | null {
        if (ts.isNumericLiteral(node)) return parseFloat(node.text);
        if (ts.isConditionalExpression(node)) {
          const trueOp = extractOpacity(node.whenTrue);
          const falseOp = extractOpacity(node.whenFalse);
          if (trueOp !== null && falseOp !== null) return Math.min(trueOp, falseOp);
          return trueOp ?? falseOp;
        }
        return null;
      }

      let checkedPairs = 0;
      let checkedObjects = 0;
      let totalStyleAttrs = 0;
      let unboundColorObjects = 0;
      let checkedBorderObjects = 0;
      let checkedBorderPairs = 0;
      const violations: string[] = [];
      const containerBgs = ['--color-bg-surface', '--color-bg-subtle', '--color-bg-canvas'];

      function checkPair(bgToken: string, fgToken: string, pos: number, opacity: number = 1.0) {
        checkedPairs++;
        const { line } = sf.getLineAndCharacterOfPosition(pos);
        const lightBg = resolveTokenHex(bgToken, lightTokens);
        const lightFg = resolveTokenHex(fgToken, lightTokens);
        const darkBg = resolveTokenHex(bgToken, darkTokens);
        const darkFg = resolveTokenHex(fgToken, darkTokens);

        if (bgToken === fgToken && opacity >= 1.0) {
          violations.push(`L${line + 1}: 1:1 token collision between background and foreground (${bgToken})`);
          return;
        }

        if (bgToken.startsWith('--color-text-')) {
          violations.push(`L${line + 1}: Illegitimate background token derived from text token: ${bgToken}`);
          return;
        }

        const effectiveLFg = opacity < 1.0 && lightBg && lightFg ? blendRgba(parseHex(lightFg), opacity, lightBg) : lightFg;
        const effectiveDFg = opacity < 1.0 && darkBg && darkFg ? blendRgba(parseHex(darkFg), opacity, darkBg) : darkFg;

        if (lightBg && effectiveLFg) {
          const cr = getContrast(effectiveLFg, lightBg);
          if (cr < 4.5) {
            violations.push(`L${line + 1}: Light text contrast ${cr.toFixed(2)}:1 < 4.5:1 (${fgToken} on ${bgToken}${opacity < 1.0 ? ` opacity ${opacity.toFixed(2)}` : ''})`);
          }
        }
        if (darkBg && effectiveDFg) {
          const cr = getContrast(effectiveDFg, darkBg);
          if (cr < 4.5) {
            violations.push(`L${line + 1}: Dark text contrast ${cr.toFixed(2)}:1 < 4.5:1 (${fgToken} on ${bgToken}${opacity < 1.0 ? ` opacity ${opacity.toFixed(2)}` : ''})`);
          }
        }
      }

      function checkBorderPair(bgToken: string, borderToken: string, pos: number, opacity: number = 1.0) {
        checkedBorderPairs++;
        const { line } = sf.getLineAndCharacterOfPosition(pos);
        const lBg = resolveTokenHex(bgToken, lightTokens);
        const dBg = resolveTokenHex(bgToken, darkTokens);
        const lBorder = resolveTokenHex(borderToken, lightTokens);
        const dBorder = resolveTokenHex(borderToken, darkTokens);

        if (bgToken === borderToken && opacity >= 1.0) {
          violations.push(`L${line + 1}: Identical border-background token collision (1:1 contrast) detected: ${borderToken} on ${bgToken}`);
          return;
        }

        if (bgToken.startsWith('--color-text-')) {
          violations.push(`L${line + 1}: Illegitimate background token derived from text token: ${bgToken}`);
          return;
        }

        const effectiveLBorder = opacity < 1.0 && lBg && lBorder ? blendRgba(parseHex(lBorder), opacity, lBg) : lBorder;
        const effectiveDBorder = opacity < 1.0 && dBg && dBorder ? blendRgba(parseHex(dBorder), opacity, dBg) : dBorder;

        if (lBg && effectiveLBorder) {
          const cr = getContrast(effectiveLBorder, lBg);
          if (cr < 3.0) {
            violations.push(`L${line + 1}: Light border contrast ${cr.toFixed(2)}:1 < 3.0:1 (${borderToken} on ${bgToken}${opacity < 1.0 ? ` opacity ${opacity.toFixed(2)}` : ''})`);
          }
        }
        if (dBg && effectiveDBorder) {
          const cr = getContrast(effectiveDBorder, dBg);
          if (cr < 3.0) {
            violations.push(`L${line + 1}: Dark border contrast ${cr.toFixed(2)}:1 < 3.0:1 (${borderToken} on ${bgToken}${opacity < 1.0 ? ` opacity ${opacity.toFixed(2)}` : ''})`);
          }
        }
      }

      function traverseJsx(node: ts.Node, ancestorBgTokens: string[], ancestorFgTokens: string[], ancestorOpacity: number) {
        let currentBgTokens = ancestorBgTokens;
        let currentFgTokens = ancestorFgTokens;
        let currentOpacity = ancestorOpacity;

        if (ts.isJsxElement(node) || ts.isJsxSelfClosingElement(node)) {
          const opening = ts.isJsxElement(node) ? node.openingElement : node;
          const attrs = opening.attributes?.properties || [];
          let styleObj: ts.ObjectLiteralExpression | null = null;

          for (const attr of attrs) {
            if (ts.isJsxAttribute(attr) && attr.name.text === 'style') {
              totalStyleAttrs++;
              if (attr.initializer && ts.isJsxExpression(attr.initializer) && attr.initializer.expression && ts.isObjectLiteralExpression(attr.initializer.expression)) {
                styleObj = attr.initializer.expression;
              }
            }
          }

          if (styleObj) {
            let bgNode: ts.Expression | null = null;
            let fgNode: ts.Expression | null = null;
            let borderNode: ts.Expression | null = null;
            let opacityNode: ts.Expression | null = null;

            for (const p of styleObj.properties) {
              if (ts.isPropertyAssignment(p)) {
                const name = p.name.getText(sf);
                if (name === 'backgroundColor' || name === 'background') bgNode = p.initializer;
                if (name === 'color') fgNode = p.initializer;
                if (name === 'border' || name === 'borderColor' || name === 'borderBottom' || name === 'borderLeft') borderNode = p.initializer;
                if (name === 'opacity') opacityNode = p.initializer;
              }
            }

            const explicitOpacity = opacityNode ? extractOpacity(opacityNode) : null;
            const effectiveOpacity = explicitOpacity !== null ? currentOpacity * explicitOpacity : currentOpacity;

            const bgBranches = bgNode ? extractBranches(bgNode) : [];
            const fgBranches = fgNode ? extractBranches(fgNode) : [];
            const borderBranches = borderNode ? extractBranches(borderNode) : [];

            if (bgBranches.length > 0) {
              currentBgTokens = bgBranches.map(b => b.token);
            }
            if (fgBranches.length > 0) {
              currentFgTokens = fgBranches.map(b => b.token);
            }
            currentOpacity = effectiveOpacity;

            if (bgBranches.length > 0 && fgBranches.length > 0) {
              checkedObjects++;
              for (const b of bgBranches) {
                for (const f of fgBranches) {
                  if (!b.cond || !f.cond || b.cond === f.cond) {
                    checkPair(b.token, f.token, styleObj.getStart(sf), effectiveOpacity);
                  }
                }
              }
            } else if (fgBranches.length > 0) {
              unboundColorObjects++;
              const targetBgs = currentBgTokens.length > 0 ? currentBgTokens : containerBgs;
              for (const bg of targetBgs) {
                for (const f of fgBranches) {
                  checkPair(bg, f.token, styleObj.getStart(sf), effectiveOpacity);
                }
              }
            }

            if (borderBranches.length > 0) {
              checkedBorderObjects++;
              if (bgBranches.length > 0) {
                for (const b of borderBranches) {
                  for (const bgB of bgBranches) {
                    if (!b.cond || !bgB.cond || b.cond === bgB.cond) {
                      checkBorderPair(bgB.token, b.token, styleObj.getStart(sf), effectiveOpacity);
                    }
                  }
                }
              } else {
                const targetBgs = currentBgTokens.length > 0 ? currentBgTokens : containerBgs;
                for (const bg of targetBgs) {
                  for (const b of borderBranches) {
                    checkBorderPair(bg, b.token, styleObj.getStart(sf), effectiveOpacity);
                  }
                }
              }
            }
          }
        }

        ts.forEachChild(node, child => traverseJsx(child, currentBgTokens, currentFgTokens, currentOpacity));
      }

      function checkConfigTables(node: ts.Node) {
        if (ts.isVariableDeclaration(node) && node.name.getText(sf) === 'RUN_STATE_CONFIG' && node.initializer && ts.isObjectLiteralExpression(node.initializer)) {
          for (const prop of node.initializer.properties) {
            if (ts.isPropertyAssignment(prop) && ts.isObjectLiteralExpression(prop.initializer)) {
              totalStyleAttrs++;
              let bgToken: string | null = null;
              let fgToken: string | null = null;
              let borderToken: string | null = null;
              for (const subProp of prop.initializer.properties) {
                if (ts.isPropertyAssignment(subProp)) {
                  const pName = subProp.name.getText(sf);
                  const text = subProp.initializer.getText(sf);
                  const m = text.match(/var\((--color-[a-z0-9-]+)\)/);
                  if (m) {
                    if (pName === 'bg') bgToken = m[1];
                    if (pName === 'color') fgToken = m[1];
                    if (pName === 'border') borderToken = m[1];
                  }
                }
              }
              if (bgToken && fgToken) {
                checkedObjects++;
                checkPair(bgToken, fgToken, prop.initializer.getStart(sf), 1.0);
              }
              if (bgToken && borderToken) {
                checkedBorderObjects++;
                checkBorderPair(bgToken, borderToken, prop.initializer.getStart(sf), 1.0);
              }
            }
          }
        }
        ts.forEachChild(node, checkConfigTables);
      }

      checkConfigTables(sf);
      traverseJsx(sf, ['--color-bg-canvas'], ['--color-text-primary'], 1.0);

      return {
        totalStyleAttrs,
        checkedObjects,
        checkedPairs,
        unboundColorObjects,
        coveredColorObjects: checkedObjects + unboundColorObjects,
        checkedBorderObjects,
        checkedBorderPairs,
        violations,
      };
    }

    const runListStats = analyzeFile('features/runs/RunList.tsx');
    expect(runListStats.totalStyleAttrs, 'Total style attributes in RunList must be exactly 53').toBe(53);
    expect(runListStats.checkedObjects, 'Explicit style objects in RunList must be exactly 19').toBe(19);
    expect(runListStats.checkedPairs, 'Evaluated pairs in RunList must be exactly 36').toBe(36);
    expect(runListStats.unboundColorObjects, 'Unbound color objects in RunList must be exactly 14').toBe(14);
    expect(runListStats.coveredColorObjects, 'Total covered color objects in RunList must be exactly 33').toBe(33);
    expect(runListStats.checkedBorderObjects, 'Border objects in RunList must be exactly 23').toBe(23);
    expect(runListStats.checkedBorderPairs, 'Border pairs in RunList must be exactly 24').toBe(24);
    expect(runListStats.violations, `RunList violations:\n${runListStats.violations.join('\n')}`).toEqual([]);
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

    // Probe 10: Card 189 NodeList telemetry lost notice former #fca5a5 on light surface (1.90:1)
    const defectiveTelemLost = '#fca5a5';
    const probe10Cr = getContrast(defectiveTelemLost, lightTokens['--color-bg-surface']);
    expect(probe10Cr, 'Defective telemetry lost #fca5a5 on light surface must fail 4.5:1').toBeLessThan(4.5);
    expect(probe10Cr).toBeCloseTo(1.90, 1);

    // Probe 11: Card 189 NodeList telemetry unknown notice former #fde68a on light surface (1.25:1)
    const defectiveTelemUnknown = '#fde68a';
    const probe11Cr = getContrast(defectiveTelemUnknown, lightTokens['--color-bg-surface']);
    expect(probe11Cr, 'Defective telemetry unknown #fde68a on light surface must fail 4.5:1').toBeLessThan(4.5);
    expect(probe11Cr).toBeCloseTo(1.25, 1);

    // Probe 12: Card 189 NodeList telemetry active notice former #7dd3fc on light surface (1.67:1)
    const defectiveTelemActive = '#7dd3fc';
    const probe12Cr = getContrast(defectiveTelemActive, lightTokens['--color-bg-surface']);
    expect(probe12Cr, 'Defective telemetry active #7dd3fc on light surface must fail 4.5:1').toBeLessThan(4.5);
    expect(probe12Cr).toBeCloseTo(1.67, 1);

    // Probe 13: Card 189 NodeList schedulable former #3fb950 on light surface (2.54:1)
    const defectiveSchedulable = '#3fb950';
    const probe13Cr = getContrast(defectiveSchedulable, lightTokens['--color-bg-surface']);
    expect(probe13Cr, 'Defective schedulable #3fb950 on light surface must fail 4.5:1').toBeLessThan(4.5);
    expect(probe13Cr).toBeCloseTo(2.54, 1);

    // Probe 14: Card 189 NodeList card border former #f59e0b on light surface (2.15:1)
    const defectiveCardBorder = '#f59e0b';
    const probe14Cr = getContrast(defectiveCardBorder, lightTokens['--color-bg-surface']);
    expect(probe14Cr, 'Defective card border #f59e0b on light surface must fail 3.0:1 UI boundary').toBeLessThan(3.0);
    expect(probe14Cr).toBeCloseTo(2.15, 1);

    // Probe 15 [Codex r1]: Observation callout background replaced with var(--color-status-unknown) (1:1 fg/bg)
    const probe15CalloutBg = lightTokens['--color-status-unknown'];
    const probe15Fg = lightTokens['--color-status-unknown'];
    expect(getContrast(probe15Fg, probe15CalloutBg), '1:1 callout foreground/background must fail 4.5:1').toBe(1.0);

    // Probe 16 [Codex r1]: Observation callout alpha mutated to 0.8 on dark canvas
    const probe16CalloutBg = blendRgba([210, 153, 34], 0.8, darkTokens['--color-bg-canvas']);
    const probe16Fg = darkTokens['--color-status-unknown'];
    expect(getContrast(probe16Fg, probe16CalloutBg), '0.8 alpha callout on dark canvas must fail 4.5:1').toBeLessThan(4.5);

    // Probe 17 [Codex r1]: Defective schedulable non-obs box former #3fb950 on 15% green tint over light subtle
    const defectiveGreenTint = blendRgba([46, 160, 67], 0.15, lightTokens['--color-bg-subtle']);
    expect(getContrast('#3fb950', defectiveGreenTint), 'Defective #3fb950 on green tint must fail 4.5:1').toBeLessThan(4.5);

    // Probe 18 [Codex r1]: Timeline degraded status former #d29922 (2.52:1 on light surface)
    expect(getContrast('#d29922', lightTokens['--color-bg-surface']), 'Defective #d29922 on light surface must fail 4.5:1').toBeLessThan(4.5);

    // Probe 19 [Card 193]: Former #3fb950 on light subtle (#f1f5f9) (2.32:1) strictly fails 4.5:1
    expect(getContrast('#3fb950', lightTokens['--color-bg-subtle']), 'Defective former #3fb950 on light subtle must fail 4.5:1').toBeLessThan(4.5);

    // Probe 20 [Card 193]: Former #3fb950 on light surface (#ffffff) (2.54:1) strictly fails 4.5:1
    expect(getContrast('#3fb950', lightTokens['--color-bg-surface']), 'Defective former #3fb950 on light surface must fail 4.5:1').toBeLessThan(4.5);

    // Probe 21 [Card 193]: Former #58a6ff on light subtle (#f1f5f9) (2.31:1) strictly fails 4.5:1
    expect(getContrast('#58a6ff', lightTokens['--color-bg-subtle']), 'Defective former #58a6ff on light subtle must fail 4.5:1').toBeLessThan(4.5);

    // Probe 22 [Card 193]: Former #58a6ff on light canvas (#f8fafc) (2.41:1) strictly fails 4.5:1
    expect(getContrast('#58a6ff', lightTokens['--color-bg-canvas']), 'Defective former #58a6ff on light canvas must fail 4.5:1').toBeLessThan(4.5);

    // Probe 23 [Card 193]: Former #3fb950 on 15% green tint composite over light subtle (1.98:1) strictly fails 4.5:1
    const defectiveGreenTintBadge = blendRgba([46, 160, 67], 0.15, lightTokens['--color-bg-subtle']);
    expect(getContrast('#3fb950', defectiveGreenTintBadge), 'Defective #3fb950 on green tint over subtle must fail 4.5:1').toBeLessThan(4.5);

    // Probe 24 [Card 195]: Desktop Explorers former muted text literal #94a3b8 on light surface (#ffffff) (2.56:1) strictly fails 4.5:1
    expect(getContrast('#94a3b8', lightTokens['--color-bg-surface']), 'Defective #94a3b8 on light surface must fail 4.5:1').toBeLessThan(4.5);
    expect(getContrast('#94a3b8', lightTokens['--color-bg-subtle']), 'Defective #94a3b8 on light subtle must fail 4.5:1').toBeLessThan(4.5);

    // Probe 25 [Card 195]: Desktop Explorers former online/healthy literal #34d399 on light surface (#ffffff) (1.92:1) strictly fails 4.5:1
    expect(getContrast('#34d399', lightTokens['--color-bg-surface']), 'Defective #34d399 on light surface must fail 4.5:1').toBeLessThan(4.5);
    expect(getContrast('#34d399', lightTokens['--color-bg-subtle']), 'Defective #34d399 on light subtle must fail 4.5:1').toBeLessThan(4.5);

    // Probe 26 [Card 195]: Desktop Explorers former lost/error literal #f87171 on light surface (#ffffff) (2.77:1) strictly fails 4.5:1
    expect(getContrast('#f87171', lightTokens['--color-bg-surface']), 'Defective #f87171 on light surface must fail 4.5:1').toBeLessThan(4.5);
    expect(getContrast('#f87171', lightTokens['--color-bg-subtle']), 'Defective #f87171 on light subtle must fail 4.5:1').toBeLessThan(4.5);

    // Probe 27 [Card 195]: Desktop Explorers former primary/accent literal #60a5fa on light surface (#ffffff) (2.53:1) strictly fails 4.5:1
    expect(getContrast('#60a5fa', lightTokens['--color-bg-surface']), 'Defective #60a5fa on light surface must fail 4.5:1').toBeLessThan(4.5);
    expect(getContrast('#60a5fa', lightTokens['--color-bg-subtle']), 'Defective #60a5fa on light subtle must fail 4.5:1').toBeLessThan(4.5);

    // Probe 28 [Card 195]: Defective active chip former brand-primary on brand-subtle in light theme (4.236:1) strictly fails 4.5:1
    expect(getContrast(lightTokens['--color-brand-primary'], lightTokens['--color-brand-subtle']), 'Defective brand-primary on brand-subtle in light must fail 4.5:1').toBeLessThan(4.5);

    // Probe 29 [Card 195]: Defective disabled button former text-inverse on border-subtle in light (3.483:1) and dark (3.751:1) strictly fails 4.5:1
    expect(getContrast(lightTokens['--color-text-inverse'], lightTokens['--color-border-subtle']), 'Defective text-inverse on border-subtle in light must fail 4.5:1').toBeLessThan(4.5);
    expect(getContrast(darkTokens['--color-text-inverse'], darkTokens['--color-border-subtle']), 'Defective text-inverse on border-subtle in dark must fail 4.5:1').toBeLessThan(4.5);

    // Probe 30 [Card 195 r2]: Defective discovery-action-success text swapped to bg-subtle (1:1 with container)
    expect(getContrast(lightTokens['--color-bg-subtle'], lightTokens['--color-bg-subtle']), 'Defective discovery success text on subtle in light fails 4.5:1').toBe(1.0);
    expect(getContrast(darkTokens['--color-bg-subtle'], darkTokens['--color-bg-subtle']), 'Defective discovery success text on subtle in dark fails 4.5:1').toBe(1.0);

    // Probe 31 [Card 195 r2]: Defective repair-action-error bg swapped to status-lost (1:1 with text/border)
    expect(getContrast(lightTokens['--color-status-lost'], lightTokens['--color-status-lost']), 'Defective repair error text on lost in light fails 4.5:1').toBe(1.0);
    expect(getContrast(darkTokens['--color-status-lost'], darkTokens['--color-status-lost']), 'Defective repair error text on lost in dark fails 4.5:1').toBe(1.0);

    // Probe 32 [Card 197]: ModelLineageView former primary text literal #f0f6fc on light surface (#ffffff) (1.09:1) strictly fails 4.5:1
    expect(getContrast('#f0f6fc', lightTokens['--color-bg-surface']), 'Defective #f0f6fc on light surface must fail 4.5:1').toBeLessThan(4.5);

    // Probe 33 [Card 197]: ModelLineageView former secondary text literal #c9d1d9 on light surface (#ffffff) (1.54:1) strictly fails 4.5:1
    expect(getContrast('#c9d1d9', lightTokens['--color-bg-surface']), 'Defective #c9d1d9 on light surface must fail 4.5:1').toBeLessThan(4.5);

    // Probe 34 [Card 197]: ModelLineageView former muted text literal #8b949e on light surface (#ffffff) (3.08:1) strictly fails 4.5:1
    expect(getContrast('#8b949e', lightTokens['--color-bg-surface']), 'Defective #8b949e on light surface must fail 4.5:1').toBeLessThan(4.5);

    // Probe 35 [Card 197]: ModelLineageView former brand text literal #58a6ff on light surface (#ffffff) (2.53:1) strictly fails 4.5:1
    expect(getContrast('#58a6ff', lightTokens['--color-bg-surface']), 'Defective #58a6ff on light surface must fail 4.5:1').toBeLessThan(4.5);

    // Probe 36 [Card 197]: ModelLineageView former warning badge text #fed7aa on light subtle (#f1f5f9) (1.24:1) strictly fails 4.5:1
    expect(getContrast('#fed7aa', lightTokens['--color-bg-subtle']), 'Defective #fed7aa on light subtle must fail 4.5:1').toBeLessThan(4.5);

    // Probe 37 [Card 197]: ModelLineageView former border literal #30363d on dark surface (#111827) (1.45:1) strictly fails 3.0:1
    expect(getContrast('#30363d', darkTokens['--color-bg-surface']), 'Defective #30363d on dark surface must fail 3.0:1').toBeLessThan(3.0);

    // Probe 38 [Card 197 r1 / Z1 / F2]: Brand primary on brand subtle in light mode (4.24:1) strictly fails 4.5:1
    const probe38Cr = getContrast(lightTokens['--color-brand-primary'], lightTokens['--color-brand-subtle']);
    expect(probe38Cr, 'Defective brand-primary on brand-subtle in light must fail 4.5:1').toBeLessThan(4.5);
    expect(probe38Cr).toBeCloseTo(4.24, 2);

    // Probe 39 [Card 197 r1 / Z2 / F1]: Eval-gate-badge white text on status-online in dark mode (2.28:1) strictly fails 4.5:1
    const probe39Cr = getContrast(darkTokens['--color-brand-primary-fg'], darkTokens['--color-status-online']);
    expect(probe39Cr, 'Defective white on status-online in dark must fail 4.5:1').toBeLessThan(4.5);
    expect(probe39Cr).toBeCloseTo(2.28, 2);

    // Probe 40 [Card 197 r1 / Z2 / F1]: Eval-gate-badge white text on status-offline in dark mode (2.77:1) strictly fails 4.5:1
    const probe40Cr = getContrast(darkTokens['--color-brand-primary-fg'], darkTokens['--color-status-offline']);
    expect(probe40Cr, 'Defective white on status-offline in dark must fail 4.5:1').toBeLessThan(4.5);
    expect(probe40Cr).toBeCloseTo(2.77, 2);

    // Probe 41 [Card 197 r1 / Z3 / F3]: Swapping status-online into background of status-online text (1:1 mutation S3) strictly fails 4.5:1
    expect(getContrast(lightTokens['--color-status-online'], lightTokens['--color-status-online']), 'Defective online on online in light fails 4.5:1').toBe(1.0);
    expect(getContrast(darkTokens['--color-status-online'], darkTokens['--color-status-online']), 'Defective online on online in dark fails 4.5:1').toBe(1.0);

    // Probe 42 [Card 197 r2 / Claude r2 & Codex r2]: Replay foreground brand-hover -> brand-primary-fg on brand-subtle in light mode (1.22:1) strictly fails 4.5:1
    const probe42Cr = getContrast(lightTokens['--color-brand-primary-fg'], lightTokens['--color-brand-subtle']);
    expect(probe42Cr, 'Defective brand-primary-fg on brand-subtle in light must fail 4.5:1').toBeLessThan(4.5);
    expect(probe42Cr).toBeCloseTo(1.22, 2);

    // Probe 43 [Card 197 r3 / Claude r3 W1]: Swapping badge border to same as badge background (1:1 border collision) strictly fails 3.0:1
    expect(getContrast(lightTokens['--color-brand-subtle'], lightTokens['--color-brand-subtle']), 'Defective badge border on subtle background in light fails 3.0:1').toBe(1.0);
    expect(getContrast(darkTokens['--color-brand-subtle'], darkTokens['--color-brand-subtle']), 'Defective badge border on subtle background in dark fails 3.0:1').toBe(1.0);

    // Probe 44 [Card 199]: AdminSecurityConsole former hardcoded #58a6ff on light surface/subtle strictly fails 4.5:1
    expect(getContrast('#58a6ff', lightTokens['--color-bg-surface']), 'Former #58a6ff on light surface fails 4.5:1').toBeLessThan(4.5);
    expect(getContrast('#58a6ff', lightTokens['--color-bg-surface'])).toBeCloseTo(2.526, 2);
    expect(getContrast('#58a6ff', lightTokens['--color-bg-subtle']), 'Former #58a6ff on light subtle fails 4.5:1').toBeLessThan(4.5);
    expect(getContrast('#58a6ff', lightTokens['--color-bg-subtle'])).toBeCloseTo(2.306, 2);

    // Probe 45 [Card 199]: AdminSecurityConsole former hardcoded #8b949e on light surface/subtle strictly fails 4.5:1
    expect(getContrast('#8b949e', lightTokens['--color-bg-surface']), 'Former #8b949e on light surface fails 4.5:1').toBeLessThan(4.5);
    expect(getContrast('#8b949e', lightTokens['--color-bg-surface'])).toBeCloseTo(3.076, 2);
    expect(getContrast('#8b949e', lightTokens['--color-bg-subtle']), 'Former #8b949e on light subtle fails 4.5:1').toBeLessThan(4.5);
    expect(getContrast('#8b949e', lightTokens['--color-bg-subtle'])).toBeCloseTo(2.808, 2);

    // Probe 46 [Card 199]: AdminSecurityConsole former hardcoded #f85149 on light surface/subtle strictly fails 4.5:1
    expect(getContrast('#f85149', lightTokens['--color-bg-surface']), 'Former #f85149 on light surface fails 4.5:1').toBeLessThan(4.5);
    expect(getContrast('#f85149', lightTokens['--color-bg-surface'])).toBeCloseTo(3.352, 2);
    expect(getContrast('#f85149', lightTokens['--color-bg-subtle']), 'Former #f85149 on light subtle fails 4.5:1').toBeLessThan(4.5);
    expect(getContrast('#f85149', lightTokens['--color-bg-subtle'])).toBeCloseTo(3.060, 2);

    // Probe 47 [Card 199]: AdminSecurityConsole 1:1 color collision (swapping modal title to surface background) strictly fails 4.5:1
    expect(getContrast(lightTokens['--color-bg-surface'], lightTokens['--color-bg-surface']), 'Defective modal title 1:1 collision in light fails 4.5:1').toBe(1.0);
    expect(getContrast(darkTokens['--color-bg-surface'], darkTokens['--color-bg-surface']), 'Defective modal title 1:1 collision in dark fails 4.5:1').toBe(1.0);

    // Probe 48 [Card 199]: AdminSecurityConsole 1:1 border collision (swapping notice border to subtle background) strictly fails 3.0:1
    expect(getContrast(lightTokens['--color-bg-subtle'], lightTokens['--color-bg-subtle']), 'Defective notice border 1:1 collision in light fails 3.0:1').toBe(1.0);
    expect(getContrast(darkTokens['--color-bg-subtle'], darkTokens['--color-bg-subtle']), 'Defective notice border 1:1 collision in dark fails 3.0:1').toBe(1.0);

    // Probe 49 [Card 199 r1 / T1 / Claude r1 A1]: Container background mutated to text-primary behind text strictly fails 4.5:1
    expect(getContrast(lightTokens['--color-text-primary'], lightTokens['--color-text-primary']), 'Defective text-primary on text-primary 1:1 collision fails 4.5:1').toBe(1.0);
    const probe49BrandCr = getContrast(lightTokens['--color-brand-hover'], lightTokens['--color-text-primary']);
    expect(probe49BrandCr, 'Defective brand-hover on text-primary container background fails 4.5:1').toBeLessThan(4.5);
    expect(probe49BrandCr).toBeCloseTo(2.66, 2);

    // Probe 50 [Card 199 r1 / T2 / Claude r1 A6]: Modal backdrop scrim alpha mutated to 0.05 yields 1.16:1 boundary contrast, failing 3.0:1
    const defectiveScrim05 = blendRgba([0, 0, 0], 0.05, lightTokens['--color-bg-canvas']);
    const probe50Cr = getContrast(lightTokens['--color-bg-surface'], defectiveScrim05);
    expect(probe50Cr, 'Defective 0.05 alpha scrim on light canvas fails 3.0:1 modal surface boundary').toBeLessThan(3.0);
    expect(probe50Cr).toBeCloseTo(1.16, 2);

    // Probe 51 [Card 202]: IntranetDeploymentView former hardcoded #58a6ff on light subtle fails 4.5:1
    expect(getContrast('#58a6ff', lightTokens['--color-bg-subtle']), 'Former #58a6ff on light subtle fails 4.5:1').toBeLessThan(4.5);
    expect(getContrast('#58a6ff', lightTokens['--color-bg-subtle'])).toBeCloseTo(2.306, 2);

    // Probe 52 [Card 202]: IntranetDeploymentView former hardcoded #8b949e on light subtle fails 4.5:1
    expect(getContrast('#8b949e', lightTokens['--color-bg-subtle']), 'Former #8b949e on light subtle fails 4.5:1').toBeLessThan(4.5);
    expect(getContrast('#8b949e', lightTokens['--color-bg-subtle'])).toBeCloseTo(2.808, 2);

    // Probe 53 [Card 202]: IntranetDeploymentView former hardcoded #d29922 on light subtle fails 4.5:1
    expect(getContrast('#d29922', lightTokens['--color-bg-subtle']), 'Former #d29922 on light subtle fails 4.5:1').toBeLessThan(4.5);
    expect(getContrast('#d29922', lightTokens['--color-bg-subtle'])).toBeCloseTo(2.304, 2);

    // Probe 54 [Card 202]: IntranetDeploymentView 1:1 text-background collision in notice strictly fails 4.5:1
    expect(getContrast(lightTokens['--color-bg-subtle'], lightTokens['--color-bg-subtle']), 'Notice text on notice bg 1:1 collision in light fails 4.5:1').toBe(1.0);
    expect(getContrast(darkTokens['--color-bg-subtle'], darkTokens['--color-bg-subtle']), 'Notice text on notice bg 1:1 collision in dark fails 4.5:1').toBe(1.0);

    // Probe 55 [Card 202]: IntranetDeploymentView 1:1 border collision in notice strictly fails 3.0:1
    expect(getContrast(lightTokens['--color-bg-subtle'], lightTokens['--color-bg-subtle']), 'Notice border on notice bg 1:1 collision in light fails 3.0:1').toBe(1.0);
    expect(getContrast(darkTokens['--color-bg-subtle'], darkTokens['--color-bg-subtle']), 'Notice border on notice bg 1:1 collision in dark fails 3.0:1').toBe(1.0);

    // Probe 56 [Card 202 r1 / U1]: Operator input border with 0.8 opacity over surface fails 3.0:1
    const defectiveBorderOp08Light = blendRgba(parseHex(lightTokens['--color-border-subtle']), 0.8, lightTokens['--color-bg-surface']);
    const defectiveBorderOp08Dark = blendRgba(parseHex(darkTokens['--color-border-subtle']), 0.8, darkTokens['--color-bg-surface']);
    const probe56LightCr = getContrast(defectiveBorderOp08Light, lightTokens['--color-bg-surface']);
    const probe56DarkCr = getContrast(defectiveBorderOp08Dark, darkTokens['--color-bg-surface']);
    expect(probe56LightCr, 'Defective 0.8 opacity border on light surface fails 3.0:1').toBeLessThan(3.0);
    expect(probe56LightCr).toBeCloseTo(2.60, 2);
    expect(probe56DarkCr, 'Defective 0.8 opacity border on dark surface fails 3.0:1').toBeLessThan(3.0);
    expect(probe56DarkCr).toBeCloseTo(2.86, 2);

    // Probe 57 [Card 202 r1 / U1]: Error state message with 0.5 opacity (mutant B5) fails 4.5:1
    const defectiveTextOp05Light = blendRgba(parseHex(lightTokens['--color-status-offline']), 0.5, lightTokens['--color-bg-subtle']);
    const defectiveTextOp05Dark = blendRgba(parseHex(darkTokens['--color-status-offline']), 0.5, darkTokens['--color-bg-subtle']);
    const probe57LightCr = getContrast(defectiveTextOp05Light, lightTokens['--color-bg-subtle']);
    const probe57DarkCr = getContrast(defectiveTextOp05Dark, darkTokens['--color-bg-subtle']);
    expect(probe57LightCr, 'Defective 0.5 opacity text on light subtle fails 4.5:1').toBeLessThan(4.5);
    expect(probe57LightCr).toBeCloseTo(2.46, 2);
    expect(probe57DarkCr, 'Defective 0.5 opacity text on dark subtle fails 4.5:1').toBeLessThan(4.5);
    expect(probe57DarkCr).toBeCloseTo(2.31, 2);

    // Probe 58 [Card 206]: DeveloperStudio former hardcoded #d29922 on light subtle fails 4.5:1
    expect(getContrast('#d29922', lightTokens['--color-bg-subtle']), 'DeveloperStudio former #d29922 on light subtle fails 4.5:1').toBeLessThan(4.5);
    expect(getContrast('#d29922', lightTokens['--color-bg-subtle'])).toBeCloseTo(2.304, 2);

    // Probe 59 [Card 206]: DeveloperStudio non-schedulable node card opacity 0.75 degrades muted text on subtle below 4.5:1
    const defectiveMutedOp075Dark = blendRgba(parseHex(darkTokens['--color-text-muted']), 0.75, darkTokens['--color-bg-subtle']);
    const probe59DarkCr = getContrast(defectiveMutedOp075Dark, darkTokens['--color-bg-subtle']);
    expect(probe59DarkCr, 'Non-schedulable card opacity 0.75 degrades muted text below 4.5:1 in dark mode').toBeLessThan(4.5);
    expect(probe59DarkCr).toBeCloseTo(3.94, 2);

    // Probe 60 [Card 206]: DeveloperStudio active tab borderBottom 1:1 collision with surface background strictly fails 3.0:1
    expect(getContrast(lightTokens['--color-bg-surface'], lightTokens['--color-bg-surface']), 'Active tab border 1:1 collision in light fails 3.0:1').toBe(1.0);
    expect(getContrast(darkTokens['--color-bg-surface'], darkTokens['--color-bg-surface']), 'Active tab border 1:1 collision in dark fails 3.0:1').toBe(1.0);

    // Probe 61 [Card 213]: SealRecordPanel former hardcoded #8b949e on light surface strictly fails 4.5:1
    const probe61Cr = getContrast('#8b949e', lightTokens['--color-bg-surface']);
    expect(probe61Cr, 'SealRecordPanel former #8b949e on light surface fails 4.5:1').toBeLessThan(4.5);
    expect(probe61Cr).toBeCloseTo(3.08, 2);

    // Probe 62 [Card 213]: SealRecordPanel former hardcoded #58a6ff on light surface strictly fails 4.5:1
    const probe62Cr = getContrast('#58a6ff', lightTokens['--color-bg-surface']);
    expect(probe62Cr, 'SealRecordPanel former #58a6ff on light surface fails 4.5:1').toBeLessThan(4.5);
    expect(probe62Cr).toBeCloseTo(2.53, 2);

    // Probe 63 [Card 213]: SealRecordPanel former hardcoded #d29922 on light subtle strictly fails 4.5:1
    const probe63Cr = getContrast('#d29922', lightTokens['--color-bg-subtle']);
    expect(probe63Cr, 'SealRecordPanel former #d29922 on light subtle fails 4.5:1').toBeLessThan(4.5);
    expect(probe63Cr).toBeCloseTo(2.30, 2);

    // Probe 64 [Card 213]: RunDetail former hardcoded #3fb950 on light surface strictly fails 4.5:1
    const probe64Cr = getContrast('#3fb950', lightTokens['--color-bg-surface']);
    expect(probe64Cr, 'RunDetail former #3fb950 on light surface fails 4.5:1').toBeLessThan(4.5);
    expect(probe64Cr).toBeCloseTo(2.54, 2);

    // Probe 65 [Card 213]: RunDetail former hardcoded #d97706 on light surface strictly fails 4.5:1
    const probe65Cr = getContrast('#d97706', lightTokens['--color-bg-surface']);
    expect(probe65Cr, 'RunDetail former #d97706 on light surface fails 4.5:1').toBeLessThan(4.5);
    expect(probe65Cr).toBeCloseTo(3.19, 2);

    // Probe 66 [Card 215]: RunList former hardcoded #64748b on light subtle strictly fails 4.5:1
    const probe66Cr = getContrast('#64748b', lightTokens['--color-bg-subtle']);
    expect(probe66Cr, 'RunList former #64748b on light subtle fails 4.5:1').toBeLessThan(4.5);
    expect(probe66Cr).toBeCloseTo(4.34, 2);

    // Probe 67 [Card 215]: RunList former hardcoded #0284c7 on light subtle strictly fails 4.5:1
    const probe67Cr = getContrast('#0284c7', lightTokens['--color-bg-subtle']);
    expect(probe67Cr, 'RunList former #0284c7 on light subtle fails 4.5:1').toBeLessThan(4.5);
    expect(probe67Cr).toBeCloseTo(3.74, 2);

    // Probe 68 [Card 215]: RunList former hardcoded #3b82f6 on light subtle strictly fails 4.5:1
    const probe68Cr = getContrast('#3b82f6', lightTokens['--color-bg-subtle']);
    expect(probe68Cr, 'RunList former #3b82f6 on light subtle fails 4.5:1').toBeLessThan(4.5);
    expect(probe68Cr).toBeCloseTo(3.36, 2);

    // Probe 69 [Card 215]: RunList former hardcoded #8b5cf6 on light subtle strictly fails 4.5:1
    const probe69Cr = getContrast('#8b5cf6', lightTokens['--color-bg-subtle']);
    expect(probe69Cr, 'RunList former #8b5cf6 on light subtle fails 4.5:1').toBeLessThan(4.5);
    expect(probe69Cr).toBeCloseTo(3.87, 2);

    // Probe 70 [Card 215]: RunList former hardcoded #fca5a5 on light subtle strictly fails 4.5:1
    const probe70Cr = getContrast('#fca5a5', lightTokens['--color-bg-subtle']);
    expect(probe70Cr, 'RunList former #fca5a5 on light subtle fails 4.5:1').toBeLessThan(4.5);
    expect(probe70Cr).toBeCloseTo(1.73, 2);

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

  // 10. [F2 Fail-Closed Multiset Inventory & Ratchet] var(--color-border-subtle) exact 356/25 and exact per-file literal multisets strictly bounded
  it('ACC-09 / F2 Fail-Closed Multiset Inventory & Ratchet: var(--color-border-subtle) exact 356/25 and exact per-file literal multisets strictly bounded', () => {
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

    const observedFileMultisets: Record<string, Record<string, number>> = {};

    for (const f of allFiles) {
      // Comment trivia is excluded (TS/TSX/JS/JSX only); strings, templates and JSX values stay intact
      const content = stripCommentTrivia(fs.readFileSync(f, 'utf-8'), f);
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
        const fileMultiset = scanColorLiterals(content);

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
    expect(borderSubtleCount, 'var(--color-border-subtle) exact occurrence count in apps/web/src must be 388').toBe(388);
    expect(borderSubtleFiles.size, 'var(--color-border-subtle) file count in apps/web/src must be 26').toBe(26);

    // Fail-closed check 3: Total files with color literals must not exceed baseline file count
    const baselineFileCount = Object.keys(COLOR_LITERAL_MULTISET_BASELINE).length;
    expect(Object.keys(observedFileMultisets).length, 'Total files with color literals must not exceed baseline').toBeLessThanOrEqual(baselineFileCount);

    // Ratchet assertions for specific legacy literals (occurrences & files)
    expect(legacyCounts['#64748b'], 'Legacy #64748b literal count must not exceed 4').toBeLessThanOrEqual(4);
    expect(legacyFiles['#64748b'].size, 'Legacy #64748b file count must not exceed 3').toBeLessThanOrEqual(3);

    expect(legacyCounts['#d97706'], 'Legacy #d97706 literal count must not exceed 6').toBeLessThanOrEqual(6);
    expect(legacyFiles['#d97706'].size, 'Legacy #d97706 file count must not exceed 4').toBeLessThanOrEqual(4);

    expect(legacyCounts['#e2e8f0'], 'Legacy #e2e8f0 literal count must not exceed 0').toBeLessThanOrEqual(0);
    expect(legacyFiles['#e2e8f0'].size, 'Legacy #e2e8f0 file count must not exceed 0').toBeLessThanOrEqual(0);

    expect(legacyCounts['#dc2626'], 'Legacy #dc2626 literal count must not exceed 1').toBeLessThanOrEqual(1);
    expect(legacyFiles['#dc2626'].size, 'Legacy #dc2626 file count must not exceed 1').toBeLessThanOrEqual(1);

    expect(legacyCounts['#30363d'], 'Legacy #30363d literal count must not exceed 55').toBeLessThanOrEqual(55);
    expect(legacyFiles['#30363d'].size, 'Legacy #30363d file count must not exceed 9').toBeLessThanOrEqual(9);
  });

  // 11. Comment-trivia exclusion: comments are never colours, but real string/template/JSX values still count
  it('ACC-09 / F2 Comment-trivia exclusion: comment-only #abc is ignored while string, template and JSX literals are still counted', () => {
    const scan = (code: string, fileName = 'probe.tsx') => scanColorLiterals(stripCommentTrivia(code, fileName));

    // Comments (line, block, JSDoc, JSX expression comment, trailing comment) are ignored
    expect(scan('// #abc\nconst a = 1;\n')).toEqual({});
    expect(scan('/* #abc */\nconst a = 1;\n')).toEqual({});
    expect(scan('/**\n * Design #281 / PR #282 rgba(1, 2, 3, 0.5)\n */\nexport interface X { a: string }\n', 'probe.ts')).toEqual({});
    expect(scan('const v = 12.26, // #c9d1d9 on #0d1117\n  w = 1;\n', 'probe.ts')).toEqual({});
    expect(scan('const el = <div>{/* design #218 */}</div>;\n')).toEqual({});
    expect(scan('// #abc\n', 'probe.js')).toEqual({});
    expect(scan('/* #abc */ const el = <i />;\n', 'probe.jsx')).toEqual({});

    // Real literals are still counted
    expect(scan("const color = '#abc';\n")).toEqual({ '#abc': 1 });
    expect(scan("const color = '#abc'; // #def\n")).toEqual({ '#abc': 1 });
    expect(scan('const border = `1px solid #abc`;\n')).toEqual({ '#abc': 1 });
    expect(scan('const border = `${w}px solid #abc ${x} rgba(1, 2, 3, 0.5)`;\n')).toEqual({ '#abc': 1, 'rgba(1,2,3,0.5)': 1 });
    expect(scan("const el = <div style={{ color: '#abc', background: 'hsl(1, 2%, 3%)' }} />;\n")).toEqual({ '#abc': 1, 'hsl(1,2%,3%)': 1 });
    expect(scan('const el = <rect fill="#abc" />;\n')).toEqual({ '#abc': 1 });
    expect(scan("const color = '#abc';\n", 'probe.js')).toEqual({ '#abc': 1 });

    // Comment-like sequences inside strings, regex literals and JSX text are not comments
    expect(scan("const u = 'https://example.com'; const c = '#abc';\n")).toEqual({ '#abc': 1 });
    expect(scan("const s = '/* not a comment'; const c = '#abc'; const t = '*/';\n")).toEqual({ '#abc': 1 });
    expect(scan("const re = /https?:\\/\\//; const c = '#abc';\n", 'probe.ts')).toEqual({ '#abc': 1 });
    expect(scan('const el = <p>see // #abc</p>;\n')).toEqual({ '#abc': 1 });
  });
});
