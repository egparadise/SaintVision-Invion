// @vitest-environment happy-dom
import React, { act } from 'react';
import { createRoot } from 'react-dom/client';
import { describe, it, expect, vi } from 'vitest';
import fs from 'node:fs';
import path from 'node:path';
import ts from 'typescript';
import { RunDetail } from '../src/features/runs/RunDetail';
import { NodeList } from '../src/features/nodes/NodeList';
import { NodeDetail } from '../src/features/nodes/NodeDetail';
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
    if (val.startsWith('#')) {
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
  "features/admin/AdminSecurityConsole.tsx": {"#0d1117": 12, "#161b22": 14, "#21262d": 1, "#30363d": 24, "#3fb950": 16, "#58a6ff": 6, "#8b949e": 40, "#c9d1d9": 12, "#d29922": 1, "#eab308": 1, "#ef4444": 1, "#f0f6fc": 10, "#f85149": 24, "#fca5a5": 1, "#fde047": 1, "#ff7b72": 3, "rgba(0,0,0,0.75)": 1, "rgba(210,153,34,0.2)": 1, "rgba(234,179,8,0.15)": 1, "rgba(239,68,68,0.15)": 1, "rgba(248,81,73,0.15)": 8, "rgba(248,81,73,0.2)": 3, "rgba(46,160,67,0.15)": 2, "rgba(46,160,67,0.2)": 1, "rgba(63,185,80,0.2)": 1},
  "features/agent/NaturalLanguageRunView.tsx": {"#0d1117": 6, "#161b22": 7, "#30363d": 12, "#3fb950": 7, "#58a6ff": 8, "#8b949e": 16, "#93c5fd": 1, "#94a3b8": 1, "#c9d1d9": 2, "#cbd5e1": 1, "#f0f6fc": 3, "#f85149": 7, "#ff7b72": 1, "rgba(248,81,73,0.15)": 2, "rgba(46,160,67,0.15)": 1, "rgba(46,160,67,0.2)": 1, "rgba(56,139,253,0.15)": 2, "rgba(56,139,253,0.2)": 1},
  "features/approvals/ApprovalCenter.tsx": {"#1e293b": 1, "#334155": 1, "#3b82f6": 1, "#93c5fd": 1, "#ef4444": 2, "#f8fafc": 1, "#fca5a5": 2, "#fed7aa": 1, "#fff": 1, "rgba(16,185,129,0.15)": 1, "rgba(234,179,8,0.15)": 1, "rgba(239,68,68,0.15)": 2, "rgba(59,130,246,0.1)": 1, "rgba(59,130,246,0.25)": 1},
  "features/approvals/ApprovalDetail.tsx": {"#0d1117": 1, "#30363d": 1, "#58a6ff": 1, "#c9d1d9": 1, "rgba(0,0,0,0.5)": 1, "rgba(220,38,38,0.1)": 1, "rgba(56,139,253,0.15)": 1},
  "features/dashboard/ClusterOverview.tsx": {"#10b981": 1, "#38bdf8": 1, "#64748b": 2, "#8b5cf6": 1, "#d29922": 1, "#ef4444": 4, "#f59e0b": 1, "#fca5a5": 3, "#fff": 1, "rgba(239,68,68,0.1)": 2},
  "features/deployment/IntranetDeploymentView.tsx": {"#0d1117": 11, "#161b22": 10, "#21262d": 4, "#238636": 1, "#30363d": 26, "#388bfd": 1, "#3fb950": 17, "#58a6ff": 13, "#6e7681": 1, "#8b949e": 65, "#a371f7": 1, "#c9d1d9": 2, "#d29922": 6, "#f0883e": 1, "#f0f6fc": 27, "#f85149": 12, "#ffffff": 1, "rgba(110,118,129,0.1)": 1, "rgba(139,148,158,0.2)": 4, "rgba(163,113,247,0.2)": 1, "rgba(210,153,34,0.15)": 1, "rgba(210,153,34,0.2)": 1, "rgba(219,109,40,0.2)": 1, "rgba(248,81,73,0.15)": 5, "rgba(248,81,73,0.2)": 2, "rgba(46,160,67,0.15)": 1, "rgba(46,160,67,0.2)": 5, "rgba(56,139,253,0.12)": 1, "rgba(56,139,253,0.15)": 1, "rgba(56,139,253,0.2)": 2, "rgba(63,185,80,0.15)": 1},
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
  "features/mlops/ModelLineageView.tsx": {"#0d1117": 34, "#161b22": 13, "#1a7f37": 1, "#1f242c": 7, "#1f6feb": 1, "#21262d": 7, "#30363d": 53, "#388bfd": 2, "#3d1214": 1, "#3fb950": 20, "#58a6ff": 40, "#8b949e": 108, "#94a3b8": 1, "#a0a8b2": 2, "#c9d1d9": 43, "#cf222e": 1, "#d29922": 4, "#e3b341": 3, "#eab308": 1, "#f0883e": 9, "#f0f6fc": 30, "#f59e0b": 3, "#f85149": 14, "#fde047": 1, "#fed7aa": 7, "#ff7b72": 10, "#ffb4a9": 1, "#ffffff": 2, "rgba(139,148,158,0.15)": 1, "rgba(160,168,178,0.15)": 2, "rgba(210,153,34,0.2)": 1, "rgba(234,179,8,0.12)": 1, "rgba(240,136,62,0.15)": 5, "rgba(248,81,73,0.12)": 3, "rgba(248,81,73,0.15)": 7, "rgba(248,81,73,0.2)": 1, "rgba(46,160,67,0.12)": 5, "rgba(46,160,67,0.15)": 1, "rgba(46,160,67,0.2)": 1, "rgba(56,139,253,0.12)": 1, "rgba(56,139,253,0.15)": 8, "rgba(56,139,253,0.2)": 1},
  "features/nodes/NodeDetail.tsx": {"rgba(210,153,34,0.12)": 1, "rgba(210,153,34,0.15)": 1, "rgba(248,81,73,0.1)": 1},
  "features/nodes/NodeList.tsx": {"#1e1e1e": 1, "#2d3748": 1, "#4ade80": 2, "#fff": 1, "#ffffff": 1, "rgba(210,153,34,0.15)": 1, "rgba(56,189,248,0.12)": 1, "rgba(56,189,248,0.3)": 1},
  "features/placement/PlacementExplainView.tsx": {"#d97706": 1, "rgba(16,185,129,0.1)": 1, "rgba(16,185,129,0.15)": 1, "rgba(234,179,8,0.15)": 1, "rgba(234,179,8,0.3)": 1},
  "features/placement/PlacementSimulator.tsx": {"#334155": 3, "#93c5fd": 1, "#94a3b8": 2, "#ef4444": 4, "#f87171": 1, "#fbbf24": 4, "#fca5a5": 4, "#fff": 3, "#ffffff": 2, "rgba(234,179,8,0.15)": 2, "rgba(234,179,8,0.3)": 2, "rgba(239,68,68,0.1)": 4, "rgba(35,134,54,0.1)": 1},
  "features/placement/ResourceTopologyGraph.tsx": {"#ffffff": 2, "rgba(16,185,129,0.08)": 1},
  "features/recovery/DistributedRecoveryView.tsx": {"#0d1117": 3, "#161b22": 9, "#21262d": 1, "#30363d": 12, "#3fb950": 6, "#58a6ff": 8, "#8b949e": 20, "#a371f7": 1, "#e3b341": 1, "#f0f6fc": 8, "#f85149": 7, "rgba(248,81,73,0.15)": 1, "rgba(46,160,67,0.15)": 1, "rgba(56,139,253,0.1)": 1, "rgba(56,139,253,0.15)": 1, "rgba(56,139,253,0.4)": 1},
  "features/release/ReleaseCandidateView.tsx": {"#0d1117": 1, "#161b22": 7, "#21262d": 2, "#30363d": 11, "#3fb950": 10, "#58a6ff": 5, "#8b949e": 22, "#c9d1d9": 2, "#d29922": 2, "#f0f6fc": 7, "#f85149": 5, "rgba(139,148,158,0.1)": 1, "rgba(139,148,158,0.2)": 1, "rgba(248,81,73,0.15)": 1, "rgba(248,81,73,0.2)": 2, "rgba(46,160,67,0.15)": 1, "rgba(46,160,67,0.2)": 2, "rgba(56,139,253,0.12)": 1, "rgba(56,139,253,0.2)": 1},
  "features/release/releaseEngine.ts": {"#0d1117": 1, "#6e7681": 1},
  "features/runs/RunDetail.tsx": {"#047857": 2, "#0d1117": 1, "#10b981": 9, "#1d4ed8": 1, "#21262d": 1, "#22c55e": 1, "#30363d": 1, "#34d399": 2, "#38bdf8": 2, "#3b82f6": 2, "#3fb950": 1, "#4ade80": 1, "#58a6ff": 6, "#60a5fa": 1, "#8b949e": 4, "#93c5fd": 7, "#94a3b8": 2, "#b45309": 1, "#c9d1d9": 1, "#d97706": 6, "#e2e8f0": 1, "#eab308": 2, "#ef4444": 7, "#f59e0b": 3, "#f85149": 7, "#f87171": 2, "#fca5a5": 3, "#fef08a": 1, "#ffffff": 1, "rgba(0,0,0,0.65)": 2, "rgba(110,118,129,0.2)": 1, "rgba(16,185,129,0.1)": 1, "rgba(16,185,129,0.12)": 2, "rgba(16,185,129,0.15)": 1, "rgba(217,119,6,0.12)": 1, "rgba(217,119,6,0.2)": 2, "rgba(218,54,51,0.2)": 2, "rgba(234,179,8,0.1)": 1, "rgba(234,179,8,0.12)": 1, "rgba(234,179,8,0.3)": 1, "rgba(239,68,68,0.1)": 4, "rgba(239,68,68,0.15)": 1, "rgba(245,158,11,0.12)": 1, "rgba(248,81,73,0.1)": 3, "rgba(34,197,94,0.08)": 1, "rgba(46,160,67,0.2)": 1, "rgba(56,139,253,0.15)": 1, "rgba(59,130,246,0.08)": 1, "rgba(59,130,246,0.1)": 7, "rgba(59,130,246,0.15)": 1, "rgba(59,130,246,0.25)": 6, "rgba(59,130,246,0.3)": 1},
  "features/runs/RunList.tsx": {"#0284c7": 1, "#06b6d4": 1, "#10b981": 3, "#3b82f6": 3, "#58a6ff": 1, "#60a5fa": 1, "#64748b": 1, "#6b7280": 1, "#8b5cf6": 2, "#d97706": 2, "#ef4444": 4, "#f59e0b": 1, "#f85149": 2, "#f97316": 1, "#fca5a5": 2, "#fff": 1, "#ffffff": 1, "rgba(100,116,139,0.15)": 1, "rgba(107,114,128,0.15)": 1, "rgba(139,92,246,0.1)": 1, "rgba(139,92,246,0.15)": 1, "rgba(139,92,246,0.3)": 1, "rgba(16,185,129,0.15)": 1, "rgba(2,132,199,0.15)": 1, "rgba(217,119,6,0.15)": 1, "rgba(239,68,68,0.08)": 1, "rgba(239,68,68,0.1)": 1, "rgba(239,68,68,0.15)": 1, "rgba(245,158,11,0.15)": 1, "rgba(249,115,22,0.15)": 1, "rgba(59,130,246,0.1)": 1, "rgba(59,130,246,0.15)": 1, "rgba(59,130,246,0.2)": 1, "rgba(59,130,246,0.3)": 1, "rgba(6,182,212,0.15)": 1},
  "features/runs/SealRecordPanel.tsx": {"#0d1117": 4, "#161b22": 13, "#21262d": 2, "#30363d": 8, "#3fb950": 4, "#58a6ff": 8, "#8b949e": 30, "#a0a8b2": 2, "#c9d1d9": 9, "#d29922": 2, "#e3b341": 3, "#f0f6fc": 14, "#f85149": 4, "#ff7b72": 7, "rgba(160,168,178,0.15)": 1, "rgba(210,153,34,0.1)": 1, "rgba(210,153,34,0.15)": 2, "rgba(210,153,34,0.2)": 1, "rgba(210,153,34,0.4)": 2, "rgba(248,81,73,0.15)": 6, "rgba(248,81,73,0.4)": 2, "rgba(46,160,67,0.15)": 4, "rgba(46,160,67,0.4)": 4, "rgba(56,139,253,0.15)": 1, "rgba(56,139,253,0.3)": 1},
  "features/studio/DeveloperStudio.tsx": {"#0d1117": 2, "#161b22": 1, "#22c55e": 1, "#2ea043": 5, "#30363d": 2, "#304": 2, "#388bfd": 1, "#3b82f6": 1, "#3fb950": 25, "#58a6ff": 14, "#86efac": 1, "#8b949e": 4, "#93c5fd": 1, "#bc8cff": 1, "#c9d1d9": 1, "#d29922": 22, "#e6edf3": 2, "#ef4444": 2, "#f85149": 15, "#fbbf24": 1, "#fca5a5": 2, "#ffffff": 2, "rgba(0,0,0,0.2)": 1, "rgba(0,0,0,0.6)": 2, "rgba(139,148,158,0.2)": 1, "rgba(139,148,158,0.3)": 1, "rgba(163,113,247,0.2)": 1, "rgba(210,153,34,0.08)": 3, "rgba(210,153,34,0.12)": 3, "rgba(210,153,34,0.15)": 1, "rgba(210,153,34,0.2)": 5, "rgba(210,153,34,0.25)": 1, "rgba(210,153,34,0.35)": 1, "rgba(210,153,34,0.4)": 3, "rgba(234,179,8,0.15)": 1, "rgba(234,179,8,0.3)": 1, "rgba(239,68,68,0.1)": 1, "rgba(239,68,68,0.15)": 1, "rgba(248,81,73,0.08)": 1, "rgba(248,81,73,0.12)": 1, "rgba(248,81,73,0.15)": 1, "rgba(248,81,73,0.2)": 4, "rgba(248,81,73,0.4)": 2, "rgba(34,197,94,0.15)": 1, "rgba(46,160,67,0.04)": 1, "rgba(46,160,67,0.05)": 3, "rgba(46,160,67,0.15)": 2, "rgba(46,160,67,0.2)": 7, "rgba(46,160,67,0.3)": 3, "rgba(46,160,67,0.4)": 1, "rgba(56,139,253,0.05)": 2, "rgba(56,139,253,0.08)": 5, "rgba(56,139,253,0.15)": 1, "rgba(56,139,253,0.2)": 2, "rgba(56,139,253,0.25)": 1, "rgba(56,139,253,0.3)": 2, "rgba(59,130,246,0.15)": 1},
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
      expect(getContrast(lightTokens[tlOnlineVar], lightTokens['--color-bg-surface']), 'Timeline online light contrast on surface >= 4.5:1').toBeGreaterThanOrEqual(4.5);
      expect(getContrast(darkTokens[tlOnlineVar], darkTokens['--color-bg-surface']), 'Timeline online dark contrast on surface >= 4.5:1').toBeGreaterThanOrEqual(4.5);

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
      const resReservedVal = container.querySelector('[data-testid="resource-reserved-val-cpu"]') as HTMLElement;
      expect(resReservedVal, 'Resource reserved value must render').not.toBeNull();
      expect(resReservedVal.style.color, 'Reserved value must bind to var(--color-brand-primary)').toBe('var(--color-brand-primary)');
      const resReservedVar = helperExtractVar(resReservedVal.style.color);
      expect(getContrast(lightTokens[resReservedVar], lightTokens['--color-bg-subtle']), 'Reserved value light contrast on subtle >= 4.5:1').toBeGreaterThanOrEqual(4.5);
      expect(getContrast(darkTokens[resReservedVar], darkTokens['--color-bg-subtle']), 'Reserved value dark contrast on subtle >= 4.5:1').toBeGreaterThanOrEqual(4.5);

      const resSpareVal = container.querySelector('[data-testid="resource-spare-val-cpu"]') as HTMLElement;
      expect(resSpareVal, 'Resource spare value must render').not.toBeNull();
      expect(resSpareVal.style.color, 'Spare value must bind to var(--color-status-online)').toBe('var(--color-status-online)');
      const resSpareVar = helperExtractVar(resSpareVal.style.color);
      expect(getContrast(lightTokens[resSpareVar], lightTokens['--color-bg-subtle']), 'Spare value light contrast on subtle >= 4.5:1').toBeGreaterThanOrEqual(4.5);
      expect(getContrast(darkTokens[resSpareVar], darkTokens['--color-bg-subtle']), 'Spare value dark contrast on subtle >= 4.5:1').toBeGreaterThanOrEqual(4.5);

      // 6.e) 4-Tier Breakdown Observed Usage & Headroom Values (replaces #58a6ff, #3fb950)
      const obsUsageVal = container.querySelector('[data-testid="node-detail-observed-usage-value"]') as HTMLElement;
      expect(obsUsageVal, 'Observed usage value must render').not.toBeNull();
      expect(obsUsageVal.style.color, 'Observed usage value must bind to var(--color-brand-primary)').toBe('var(--color-brand-primary)');
      const obsUsageVar = helperExtractVar(obsUsageVal.style.color);
      expect(getContrast(lightTokens[obsUsageVar], lightTokens['--color-bg-subtle']), 'Observed usage light contrast on subtle >= 4.5:1').toBeGreaterThanOrEqual(4.5);
      expect(getContrast(darkTokens[obsUsageVar], darkTokens['--color-bg-subtle']), 'Observed usage dark contrast on subtle >= 4.5:1').toBeGreaterThanOrEqual(4.5);

      const obsHeadroomVal = container.querySelector('[data-testid="node-detail-observed-headroom-value"]') as HTMLElement;
      expect(obsHeadroomVal, 'Observed headroom value must render').not.toBeNull();
      expect(obsHeadroomVal.style.color, 'Observed headroom value must bind to var(--color-status-online)').toBe('var(--color-status-online)');
      const obsHeadroomVar = helperExtractVar(obsHeadroomVal.style.color);
      expect(getContrast(lightTokens[obsHeadroomVar], lightTokens['--color-bg-subtle']), 'Observed headroom light contrast on subtle >= 4.5:1').toBeGreaterThanOrEqual(4.5);
      expect(getContrast(darkTokens[obsHeadroomVar], darkTokens['--color-bg-subtle']), 'Observed headroom dark contrast on subtle >= 4.5:1').toBeGreaterThanOrEqual(4.5);
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

    // Probe 19 [Card 193]: Former #3fb950 on light subtle (#f1f5f9) (2.26:1) strictly fails 4.5:1
    expect(getContrast('#3fb950', lightTokens['--color-bg-subtle']), 'Defective former #3fb950 on light subtle must fail 4.5:1').toBeLessThan(4.5);

    // Probe 20 [Card 193]: Former #3fb950 on light surface (#ffffff) (2.54:1) strictly fails 4.5:1
    expect(getContrast('#3fb950', lightTokens['--color-bg-surface']), 'Defective former #3fb950 on light surface must fail 4.5:1').toBeLessThan(4.5);

    // Probe 21 [Card 193]: Former #58a6ff on light subtle (#f1f5f9) (2.24:1) strictly fails 4.5:1
    expect(getContrast('#58a6ff', lightTokens['--color-bg-subtle']), 'Defective former #58a6ff on light subtle must fail 4.5:1').toBeLessThan(4.5);

    // Probe 22 [Card 193]: Former #58a6ff on light canvas (#f8fafc) (2.39:1) strictly fails 4.5:1
    expect(getContrast('#58a6ff', lightTokens['--color-bg-canvas']), 'Defective former #58a6ff on light canvas must fail 4.5:1').toBeLessThan(4.5);

    // Probe 23 [Card 193]: Former #3fb950 on 15% green tint composite over light canvas (2.16:1) strictly fails 4.5:1
    const defectiveGreenTintBadge = blendRgba([46, 160, 67], 0.15, lightTokens['--color-bg-canvas']);
    expect(getContrast('#3fb950', defectiveGreenTintBadge), 'Defective #3fb950 on green tint over canvas must fail 4.5:1').toBeLessThan(4.5);

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

  // 10. [F2 Fail-Closed Multiset Inventory & Ratchet] var(--color-border-subtle) exact 141/21 and exact per-file literal multisets strictly bounded
  it('ACC-09 / F2 Fail-Closed Multiset Inventory & Ratchet: var(--color-border-subtle) exact 141/21 and exact per-file literal multisets strictly bounded', () => {
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
    expect(borderSubtleCount, 'var(--color-border-subtle) exact occurrence count in apps/web/src must be 141').toBe(141);
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

    expect(legacyCounts['#30363d'], 'Legacy #30363d literal count must not exceed 169').toBeLessThanOrEqual(169);
    expect(legacyFiles['#30363d'].size, 'Legacy #30363d file count must not exceed 15').toBeLessThanOrEqual(15);
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
