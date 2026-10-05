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
import {
  DistributedRecoveryView,
  NODE_HEALTH_CONFIG,
  NODE_HEALTH_UNKNOWN_CONFIG,
} from '../src/features/recovery/DistributedRecoveryView';
import {
  DistributedRecoveryManager,
  evaluateInitialHealth,
} from '../src/features/recovery/recoveryEngine';
import { NodeList } from '../src/features/nodes/NodeList';
import { NodeDetail } from '../src/features/nodes/NodeDetail';
import { DeveloperStudio } from '../src/features/studio/DeveloperStudio';
import { ResourceExplorer } from '../src/features/desktop/ResourceExplorer';
import { InvFileExplorer } from '../src/features/desktop/InvFileExplorer';
import { ModelLineageView } from '../src/features/mlops/ModelLineageView';
import { AdminSecurityConsole } from '../src/features/admin/AdminSecurityConsole';
import { IntranetDeploymentView } from '../src/features/deployment/IntranetDeploymentView';
import {
  NaturalLanguageRunView,
  AGENT_RUN_STATUS_CONFIG,
  getAgentRunStatusConfig,
} from '../src/features/agent/NaturalLanguageRunView';
import {
  DesktopShell,
  NOTIFICATION_LEVEL_CONFIG,
  getNotificationLevelConfig,
  DESKTOP_SHORTCUTS,
} from '../src/features/desktop/DesktopShell';
import {
  ApprovalCenter,
  APPROVAL_STATUS_CONFIG,
  getApprovalStatusConfig,
} from '../src/features/approvals/ApprovalCenter';
import {
  ClusterOverview,
  NODE_STATUS_CONFIG,
  getClusterNodeStatusConfig,
} from '../src/features/dashboard/ClusterOverview';
import {
  WorkspaceList,
  WORKSPACE_STATUS_CONFIG,
  getWorkspaceStatusConfig,
} from '../src/features/workspaces/WorkspaceList';
import {
  PlacementSimulator,
  DISCOVERY_CANDIDATE_STATE_CONFIG,
  getDiscoveryCandidateStateConfig,
  PoolItem,
  CandidateItem,
} from '../src/features/placement/PlacementSimulator';
import type { PoolCapacityResponse } from '../src/contracts/pool-capacity-response';
import type { NodeItem } from '../src/contracts/types';
import type { DesktopNotification } from '../src/contracts/virtualFabric';
import {
  ModelStudioView,
  REPLICA_STATUS_CONFIG,
  MODEL_AVAILABILITY_CONFIG,
  PLAN_FEASIBILITY_CONFIG,
  NODE_ELIGIBILITY_CONFIG,
  getReplicaStatusConfig,
  getModelAvailabilityConfig,
  getPlanFeasibilityConfig,
  getNodeEligibilityConfig,
} from '../src/features/desktop/ModelStudioView';
import {
  ReleaseCandidateView,
  SLO_STATUS_CONFIG,
  AUDIT_STATUS_CONFIG,
  CANDIDATE_STATUS_CONFIG,
  getSloStatusConfig,
  getAuditStatusConfig,
  getCandidateStatusConfig,
} from '../src/features/release/ReleaseCandidateView';
import { ReleaseManager } from '../src/features/release/releaseEngine';
import {
  RiskBadge,
  RISK_CONFIG,
  getRiskLevelConfig,
} from '../src/shared/ui/RiskBadge';
import { Button } from '../src/shared/ui/Button';
import { ExecutionResultView } from '../src/features/workspaces/ExecutionResultView';
import { WorkspaceCreateModal } from '../src/features/workspaces/WorkspaceCreateModal';
import { PlacementExplainView } from '../src/features/placement/PlacementExplainView';
import { ResourceTopologyGraph } from '../src/features/placement/ResourceTopologyGraph';
import {
  EvidenceViewer,
  EVIDENCE_INTEGRITY_CONFIG,
  getEvidenceIntegrityConfig,
  UI_INTEGRITY_PROJECTION_STATUSES,
  deriveIntegrityStatus,
  type UiIntegrityProjectionStatus,
} from '../src/features/evidence/EvidenceViewer';
import { ApprovalDetail } from '../src/features/approvals/ApprovalDetail';
import { Header } from '../src/shared/ui/Header';
import {
  DesktopWindowComponent,
  WINDOW_CONTROL_CONFIG,
  getWindowControlConfig,
} from '../src/features/desktop/DesktopWindow';
import {
  TerminalSessionView,
  TERMINAL_SHELL_CONFIG,
  getTerminalShellConfig,
  PTY_AUTH_STATUS_CONFIG,
  getPtyAuthStatusConfig,
  derivePtyAuthStatus,
  UI_PTY_AUTH_PROJECTION_STATUSES,
} from '../src/features/desktop/TerminalSessionView';
import {
  ConflictResolutionModal,
  CONFLICT_STATUS_CONFIG,
  getConflictStatusConfig,
  CONFLICT_RESOLUTION_ACTION_CONFIG,
  getConflictResolutionActionConfig,
  type UiConflictStatus,
  type UiConflictResolutionAction,
} from '../src/features/editor/ConflictResolutionModal';
import {
  DiffViewer,
  DIFF_LINE_TYPE_CONFIG,
  getDiffLineTypeConfig,
  type UiDiffLineType,
} from '../src/features/editor/DiffViewer';
import {
  GitCommitModal,
  GIT_FILE_STATUS_CONFIG,
  getGitFileStatusConfig,
  GIT_STAGE_STATE_CONFIG,
  getGitStageStateConfig,
  type UiGitFileStatus,
  type UiGitStageState,
} from '../src/features/editor/GitCommitModal';
import {
  MonacoWorkspaceEditor,
  WORKSPACE_TERMINAL_STATUS_CONFIG,
  getWorkspaceTerminalStatusStyle,
  type WorkspaceTerminalStatus,
} from '../src/features/editor/MonacoWorkspaceEditor';
import {
  WebTerminal,
  WEB_TERMINAL_CONNECTION_STATUS_CONFIG,
  getWebTerminalConnectionStatusConfig,
  type WebTerminalConnectionStatus,
} from '../src/features/terminal/WebTerminal';
import { APPROVAL_STATUSES, type ApprovalStatus } from '../src/features/approvals/ApprovalCenter';
import type { RiskLevel, PlacementExplainResult, RunResultView, ApprovalItem } from '../src/contracts/types';

import type {
  ReleaseManifestResponse,
  ReleaseManifestDetailResponse,
} from '../src/contracts/release-manifest-detail-response';
import * as client from '../src/shared/api/client';
import * as projectObservation from '../src/shared/api/projectObservation';
import { fabricObservation } from '../src/shared/api/fabricObservation';
import type { ProjectItem, NodeItem, RunItem, WorkspaceItem, WorkspaceStatusName } from '../src/contracts/types';

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
  "app/App.tsx": {},
  "features/admin/AdminSecurityConsole.tsx": {},
  "features/agent/NaturalLanguageRunView.tsx": {},
  "features/approvals/ApprovalCenter.tsx": {},
  "features/approvals/ApprovalDetail.tsx": {},
  "features/dashboard/ClusterOverview.tsx": {},
  "features/deployment/IntranetDeploymentView.tsx": {},
  "features/desktop/DesktopShell.tsx": {},
  "features/desktop/DesktopWindow.tsx": {},
  "features/desktop/InvFileExplorer.tsx": {},
  "features/desktop/ModelStudioView.tsx": {},
  "features/desktop/ResourceExplorer.tsx": {},
  "features/desktop/TerminalSessionView.tsx": {},
  "features/editor/ConflictResolutionModal.tsx": {},
  "features/editor/DiffViewer.tsx": {},
  "features/editor/GitCommitModal.tsx": {},
  "features/editor/MonacoWorkspaceEditor.tsx": {},
  "features/evidence/EvidenceViewer.tsx": {},
  "features/mlops/ModelLineageView.tsx": {},
  "features/nodes/NodeDetail.tsx": {},
  "features/nodes/NodeList.tsx": {},
  "features/placement/PlacementExplainView.tsx": {},
  "features/placement/PlacementSimulator.tsx": {},
  "features/placement/ResourceTopologyGraph.tsx": {},
  "features/recovery/DistributedRecoveryView.tsx": {},
  "features/release/ReleaseCandidateView.tsx": {},
  "features/release/releaseEngine.ts": {},
  "features/runs/RunDetail.tsx": {},
  "features/runs/RunList.tsx": {},
  "features/runs/SealRecordPanel.tsx": {},
  "features/studio/DeveloperStudio.tsx": {},
  "features/terminal/WebTerminal.tsx": {},
  "features/workspaces/ExecutionResultView.tsx": {},
  "features/workspaces/WorkspaceCreateModal.tsx": {},
  "features/workspaces/WorkspaceList.tsx": {},
  "shared/ui/Button.tsx": {},
  "shared/ui/Header.tsx": {},
  "shared/ui/RiskBadge.tsx": {},
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

      // Tokenized background check (ACC-09 Card 274)
      expect(callout.style.backgroundColor, 'Callout background must bind to var(--color-bg-subtle)').toBe('var(--color-bg-subtle)');

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

      // Tokenized background check (ACC-09 Card 274)
      expect(schedBox.style.backgroundColor, 'Schedulable obs background must bind to var(--color-bg-subtle)').toBe('var(--color-bg-subtle)');

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

      // Tokenized background check (ACC-09 Card 274)
      expect(errAlert.style.backgroundColor, 'Error alert background must bind to var(--color-bg-subtle)').toBe('var(--color-bg-subtle)');

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

  // 9j. [Card 218 / ACC-09] Component DOM Rendering Verification: DistributedRecoveryView binds foregrounds and container backgrounds to design tokens with dynamic contrast verification
  it('ACC-09 / Card 218: DistributedRecoveryView component DOM rendering binds foregrounds and container backgrounds to design tokens with dynamic contrast verification', async () => {
    const container = document.createElement('div');
    document.body.appendChild(container);
    const root = createRoot(container);

    const mockNodes: NodeItem[] = [
      {
        id: 'nod_rec_01',
        hostname: 'node-rec-online',
        os: 'linux',
        cpuCores: 8,
        cpuUsagePercent: 20,
        memoryTotalBytes: 32 * 1024 ** 3,
        memoryUsagePercent: 30,
        status: 'online',
        heartbeatAt: new Date(Date.now() - 5000).toISOString(),
      },
      {
        id: 'nod_rec_02',
        hostname: 'node-rec-stale',
        os: 'linux',
        cpuCores: 8,
        cpuUsagePercent: 20,
        memoryTotalBytes: 32 * 1024 ** 3,
        memoryUsagePercent: 30,
        status: 'degraded',
        heartbeatAt: new Date(Date.now() - 75000).toISOString(),
      },
      {
        id: 'nod_rec_03',
        hostname: 'node-rec-offline',
        os: 'linux',
        cpuCores: 8,
        cpuUsagePercent: 20,
        memoryTotalBytes: 32 * 1024 ** 3,
        memoryUsagePercent: 30,
        status: 'offline',
        heartbeatAt: null,
      },
      {
        id: 'nod_rec_04',
        hostname: 'node-rec-recovering',
        os: 'linux',
        cpuCores: 8,
        cpuUsagePercent: 20,
        memoryTotalBytes: 32 * 1024 ** 3,
        memoryUsagePercent: 30,
        status: 'offline',
        heartbeatAt: null,
      },
    ];

    const recoveryMgr = new DistributedRecoveryManager(
      mockNodes.map((n, i) => ({
        nodeId: n.id,
        hostname: n.hostname,
        activeWorkspaces: i + 1,
        status: n.status,
        heartbeatAt: n.heartbeatAt ?? null,
      }))
    );
    // Node 4 was offline, transitions to recovering on fresh heartbeat recovery
    recoveryMgr.evaluateNodeHealth('nod_rec_04', 150);
    recoveryMgr.evaluateNodeHealth('nod_rec_04', 10);

    try {
      // 1. Initial render with 4 nodes (online, stale, offline, recovering)
      await act(async () => {
        root.render(<DistributedRecoveryView nodes={mockNodes} recoveryManager={recoveryMgr} />);
      });

      // 1-a. Notice Banner (var(--color-bg-subtle), var(--color-brand-hover))
      const noticeBanner = container.querySelector('[data-testid="recovery-unexposed-notice"]') as HTMLElement;
      expect(noticeBanner, 'Notice banner must render').not.toBeNull();
      expect(noticeBanner.style.backgroundColor).toBe('var(--color-bg-subtle)');
      expect(noticeBanner.style.borderColor).toBe('var(--color-brand-hover)');
      expect(noticeBanner.style.color).toBe('var(--color-brand-hover)');
      const nbFg = helperExtractVar(noticeBanner.style.color);
      const nbBg = helperExtractVar(noticeBanner.style.backgroundColor);
      const nbBd = helperExtractVar(noticeBanner.style.borderColor);
      expect(getContrast(lightTokens[nbFg], lightTokens[nbBg]), 'Notice banner light text contrast >= 4.5:1').toBeGreaterThanOrEqual(4.5);
      expect(getContrast(darkTokens[nbFg], darkTokens[nbBg]), 'Notice banner dark text contrast >= 4.5:1').toBeGreaterThanOrEqual(4.5);
      expect(getContrast(lightTokens[nbBd], lightTokens[nbBg]), 'Notice banner light border contrast >= 3.0:1').toBeGreaterThanOrEqual(3.0);
      expect(getContrast(darkTokens[nbBd], darkTokens[nbBg]), 'Notice banner dark border contrast >= 3.0:1').toBeGreaterThanOrEqual(3.0);

      // 1-b. KPI Cards & Invariants
      const kpiDetection = container.querySelector('[data-testid="kpi-card-detection"]') as HTMLElement;
      const kpiZombie = container.querySelector('[data-testid="kpi-card-zombie"]') as HTMLElement;
      const kpiRecovery = container.querySelector('[data-testid="kpi-card-recovery"]') as HTMLElement;
      expect(kpiDetection.style.backgroundColor).toBe('var(--color-bg-surface)');
      expect(kpiDetection.style.borderColor).toBe('var(--color-border-subtle)');
      expect(kpiZombie.style.backgroundColor).toBe('var(--color-bg-surface)');
      expect(kpiZombie.style.borderColor).toBe('var(--color-border-subtle)');
      expect(kpiRecovery.style.backgroundColor).toBe('var(--color-bg-surface)');
      expect(kpiRecovery.style.borderColor).toBe('var(--color-border-subtle)');

      const zombieCount = container.querySelector('[data-testid="kpi-zombie-writes"]') as HTMLElement;
      expect(zombieCount.style.color).toBe('var(--color-status-online)');
      const zcFg = helperExtractVar(zombieCount.style.color);
      expect(getContrast(lightTokens[zcFg], lightTokens['--color-bg-surface']), 'Zombie writes count light contrast >= 4.5:1').toBeGreaterThanOrEqual(4.5);
      expect(getContrast(darkTokens[zcFg], darkTokens['--color-bg-surface']), 'Zombie writes count dark contrast >= 4.5:1').toBeGreaterThanOrEqual(4.5);

      // 1-c. Node Card Selection and Global Focus Ring Protection (WCAG 2.4.7)
      const nodeCard1 = container.querySelector('[data-testid="node-card-nod_rec_01"]') as HTMLElement;
      const nodeCard2 = container.querySelector('[data-testid="node-card-nod_rec_02"]') as HTMLElement;
      expect(nodeCard1, 'Node card 1 must render').not.toBeNull();
      expect(nodeCard2, 'Node card 2 must render').not.toBeNull();
      expect(nodeCard1.style.backgroundColor).toBe('var(--color-bg-surface)');
      expect(nodeCard1.style.borderColor).toBe('var(--color-brand-hover)');
      expect(nodeCard1.style.border).toContain('2px');
      // No inline outline overriding global :focus-visible on either card
      expect(nodeCard1.style.outline).toBe('');
      expect(nodeCard2.style.borderColor).toBe('var(--color-border-subtle)');
      expect(nodeCard2.style.outline).toBe('');

      // 1-d. Node Actual & Simulated Badges
      const actualBadge1 = container.querySelector('[data-testid="node-actual-status-nod_rec_01"]') as HTMLElement;
      expect(actualBadge1.style.color).toBe('var(--color-text-secondary)');
      expect(actualBadge1.style.backgroundColor).toBe('var(--color-bg-subtle)');
      expect(actualBadge1.style.borderColor).toBe('var(--color-border-subtle)');
      const abFg = helperExtractVar(actualBadge1.style.color);
      const abBg = helperExtractVar(actualBadge1.style.backgroundColor);
      const abBd = helperExtractVar(actualBadge1.style.borderColor);
      expect(getContrast(lightTokens[abFg], lightTokens[abBg]), 'Actual status light contrast >= 4.5:1').toBeGreaterThanOrEqual(4.5);
      expect(getContrast(darkTokens[abFg], darkTokens[abBg]), 'Actual status dark contrast >= 4.5:1').toBeGreaterThanOrEqual(4.5);
      expect(getContrast(lightTokens[abBd], lightTokens[abBg]), 'Actual status light border contrast >= 3.0:1').toBeGreaterThanOrEqual(3.0);
      expect(getContrast(darkTokens[abBd], darkTokens[abBg]), 'Actual status dark border contrast >= 3.0:1').toBeGreaterThanOrEqual(3.0);

      const simBadgeOnline = container.querySelector('[data-testid="node-sim-status-nod_rec_01"]') as HTMLElement;
      const simBadgeStale = container.querySelector('[data-testid="node-sim-status-nod_rec_02"]') as HTMLElement;
      const simBadgeOffline = container.querySelector('[data-testid="node-sim-status-nod_rec_03"]') as HTMLElement;
      const simBadgeRecovering = container.querySelector('[data-testid="node-sim-status-nod_rec_04"]') as HTMLElement;

      expect(simBadgeOnline.textContent).toBe('시뮬레이션: ONLINE');
      expect(simBadgeOnline.style.color).toBe('var(--color-status-online)');
      expect(simBadgeOnline.style.backgroundColor).toBe('var(--color-bg-subtle)');
      expect(simBadgeOnline.style.borderColor).toBe('var(--color-status-online)');

      expect(simBadgeStale.textContent).toBe('시뮬레이션: STALE');
      expect(simBadgeStale.style.color).toBe('var(--color-status-degraded)');
      expect(simBadgeStale.style.backgroundColor).toBe('var(--color-bg-subtle)');
      expect(simBadgeStale.style.borderColor).toBe('var(--color-status-degraded)');

      expect(simBadgeOffline.textContent).toBe('시뮬레이션: OFFLINE');
      expect(simBadgeOffline.style.color).toBe('var(--color-status-offline)');
      expect(simBadgeOffline.style.backgroundColor).toBe('var(--color-bg-subtle)');
      expect(simBadgeOffline.style.borderColor).toBe('var(--color-status-offline)');

      expect(simBadgeRecovering.textContent).toBe('시뮬레이션: RECOVERING');
      expect(simBadgeRecovering.style.color).toBe('var(--color-status-active)');
      expect(simBadgeRecovering.style.backgroundColor).toBe('var(--color-bg-subtle)');
      expect(simBadgeRecovering.style.borderColor).toBe('var(--color-status-active)');

      expect(simBadgeOnline.style.opacity || '1', 'Online badge must not have degraded opacity').toBe('1');
      expect(simBadgeStale.style.opacity || '1', 'Stale badge must not have degraded opacity').toBe('1');
      expect(simBadgeOffline.style.opacity || '1', 'Offline badge must not have degraded opacity').toBe('1');
      expect(simBadgeRecovering.style.opacity || '1', 'Recovering badge must not have degraded opacity').toBe('1');

      // 1-e. Fault Injection Actions & FENCED state
      const partitionBtn = container.querySelector('[data-testid="simulate-partition-btn"]') as HTMLButtonElement;
      await act(async () => {
        partitionBtn.click();
      });

      const simBadgeFenced = container.querySelector('[data-testid="node-sim-status-nod_rec_01"]') as HTMLElement;
      expect(simBadgeFenced.textContent).toBe('시뮬레이션: FENCED');
      expect(simBadgeFenced.style.color).toBe('var(--color-status-neutral)');
      expect(simBadgeFenced.style.backgroundColor).toBe('var(--color-bg-subtle)');
      expect(simBadgeFenced.style.borderColor).toBe('var(--color-border-strong)');
      expect(simBadgeFenced.style.opacity || '1', 'Fenced badge must not have degraded opacity').toBe('1');

      const actionNoticeErr = container.querySelector('[data-testid="recovery-action-notice"]') as HTMLElement;
      expect(actionNoticeErr, 'Action notice error must render').not.toBeNull();
      expect(actionNoticeErr.style.backgroundColor).toBe('var(--color-bg-subtle)');
      expect(actionNoticeErr.style.borderColor).toBe('var(--color-status-offline)');
      expect(actionNoticeErr.style.color).toBe('var(--color-status-offline)');
      const aneFg = helperExtractVar(actionNoticeErr.style.color);
      const aneBg = helperExtractVar(actionNoticeErr.style.backgroundColor);
      const aneBd = helperExtractVar(actionNoticeErr.style.borderColor);
      expect(getContrast(lightTokens[aneFg], lightTokens[aneBg]), 'Action notice error light text contrast >= 4.5:1').toBeGreaterThanOrEqual(4.5);
      expect(getContrast(darkTokens[aneFg], darkTokens[aneBg]), 'Action notice error dark text contrast >= 4.5:1').toBeGreaterThanOrEqual(4.5);
      expect(getContrast(lightTokens[aneBd], lightTokens[aneBg]), 'Action notice error light border contrast >= 3.0:1').toBeGreaterThanOrEqual(3.0);
      expect(getContrast(darkTokens[aneBd], darkTokens[aneBg]), 'Action notice error dark border contrast >= 3.0:1').toBeGreaterThanOrEqual(3.0);

      // 1-f. Stale write rejection audit stream
      const zombieBtn = container.querySelector('[data-testid="attempt-zombie-write-btn"]') as HTMLButtonElement;
      await act(async () => {
        zombieBtn.click();
      });

      const rejItem = container.querySelector('[data-testid^="rejection-item-"]') as HTMLElement;
      expect(rejItem, 'Rejection item must render').not.toBeNull();
      expect(rejItem.style.backgroundColor).toBe('var(--color-bg-subtle)');
      expect(rejItem.style.borderColor).toBe('var(--color-status-offline)');

      // 1-g. Drain & Reconcile action
      const drainBtn = container.querySelector('[data-testid="drain-reconcile-btn"]') as HTMLButtonElement;
      await act(async () => {
        drainBtn.click();
      });

      const actionNoticeSucc = container.querySelector('[data-testid="recovery-action-notice"]') as HTMLElement;
      expect(actionNoticeSucc.style.backgroundColor).toBe('var(--color-bg-subtle)');
      expect(actionNoticeSucc.style.borderColor).toBe('var(--color-status-online)');
      expect(actionNoticeSucc.style.color).toBe('var(--color-status-online)');

      const recItem = container.querySelector('[data-testid^="reconciliation-item-"]') as HTMLElement;
      expect(recItem, 'Reconciliation item must render').not.toBeNull();
      expect(recItem.style.backgroundColor).toBe('var(--color-bg-subtle)');
      expect(recItem.style.borderColor).toBe('var(--color-border-subtle)');
      expect(recItem.textContent).toContain('RECOVERED (모의)');

      // 1-h. Create checkout action (ADR-043)
      const checkoutBtn = container.querySelector('[data-testid="create-checkout-btn"]') as HTMLButtonElement;
      await act(async () => {
        checkoutBtn.click();
      });
      expect(container.textContent).toContain('sim_chk_1');

      // 1-i. Recovery health states: all 5 states distinct, distinct labels, and recovering mapped to active
      const uniqueColors = new Set(Object.values(NODE_HEALTH_CONFIG).map(t => t.color));
      expect(uniqueColors.size, 'All 5 recovery health states must have unique distinct color tokens').toBe(5);

      // Non-color distinctness: all 5 health labels must be non-empty, unique, and exactly match expected strings (killing M8a & M8d)
      expect(NODE_HEALTH_CONFIG.online.label).toBe('ONLINE');
      expect(NODE_HEALTH_CONFIG.stale.label).toBe('STALE');
      expect(NODE_HEALTH_CONFIG.offline.label).toBe('OFFLINE');
      expect(NODE_HEALTH_CONFIG.recovering.label).toBe('RECOVERING');
      expect(NODE_HEALTH_CONFIG.fenced.label).toBe('FENCED');
      const healthLabels = Object.values(NODE_HEALTH_CONFIG).map(c => c.label);
      expect(healthLabels.every(l => typeof l === 'string' && l.trim().length > 0), 'All health labels must be non-empty strings').toBe(true);
      expect(new Set(healthLabels).size, 'All 5 health labels must be distinct').toBe(5);

      for (const [state, cfg] of Object.entries(NODE_HEALTH_CONFIG)) {
        const cVar = helperExtractVar(cfg.color);
        const bVar = helperExtractVar(cfg.border);
        const bgVar = helperExtractVar(cfg.bg);
        expect(getContrast(lightTokens[cVar], lightTokens[bgVar]), `${state} light text contrast >= 4.5:1`).toBeGreaterThanOrEqual(4.5);
        expect(getContrast(darkTokens[cVar], darkTokens[bgVar]), `${state} dark text contrast >= 4.5:1`).toBeGreaterThanOrEqual(4.5);
        expect(getContrast(lightTokens[bVar], lightTokens[bgVar]), `${state} light border contrast >= 3.0:1`).toBeGreaterThanOrEqual(3.0);
        expect(getContrast(darkTokens[bVar], darkTokens[bgVar]), `${state} dark border contrast >= 3.0:1`).toBeGreaterThanOrEqual(3.0);
      }

      // Parity with RunDetail/RunList recovering status
      expect(NODE_HEALTH_CONFIG.recovering.color, 'recovering color must match active status token').toBe('var(--color-status-active)');
      expect(NODE_HEALTH_CONFIG.fenced.border, 'fenced border must match border-strong token').toBe('var(--color-border-strong)');

      // 1-j. Fail-Closed Non-Color State Contract & Negative Fallback Verification
      // A: Engine level negative checks
      expect(evaluateInitialHealth('unknown', null).health, 'Unreported heartbeat with unknown status must evaluate to offline').toBe('offline');
      expect(evaluateInitialHealth(undefined, null).health, 'Missing status and heartbeat must evaluate to offline').toBe('offline');
      expect(evaluateInitialHealth('corrupted_status' as any, null).health, 'Corrupted status must evaluate to offline').toBe('offline');
      expect(evaluateInitialHealth('online', null).health, 'Online status without heartbeat must evaluate to stale, never silently online').toBe('stale');
      expect(recoveryMgr.getNode('nod_rec_04')?.healthState, 'Recovered node with fresh heartbeat transitions to recovering').toBe('recovering');

      // B: Config fallback contract: unknown telemetry states must never silently fallback to ONLINE
      expect(NODE_HEALTH_UNKNOWN_CONFIG.label).toBe('UNKNOWN');
      expect(NODE_HEALTH_UNKNOWN_CONFIG.color).toBe('var(--color-status-neutral)');
      expect(NODE_HEALTH_UNKNOWN_CONFIG.color).not.toBe('var(--color-status-online)');

      // C: DOM level negative checks: render view with unmapped/corrupted and missing health states
      const failClosedMgr = new DistributedRecoveryManager([
        {
          nodeId: 'nod_rec_unmapped',
          hostname: 'worker-unmapped.saint.local',
          status: 'corrupted_variant',
          heartbeatAt: new Date().toISOString(),
        },
        {
          nodeId: 'nod_rec_missing',
          hostname: 'worker-missing.saint.local',
          status: 'unknown',
          heartbeatAt: null,
        },
      ]);
      // Force unmapped healthState to simulate unhandled or newly introduced backend telemetry variant
      (failClosedMgr.getNodes()[0] as any).healthState = 'unknown_variant';
      // Force null/undefined healthState to simulate missing state field
      (failClosedMgr.getNodes()[1] as any).healthState = undefined;

      await act(async () => {
        root.render(<DistributedRecoveryView key="fail-closed" nodes={[]} recoveryManager={failClosedMgr} />);
      });

      const simBadgeUnmapped = container.querySelector('[data-testid="node-sim-status-nod_rec_unmapped"]') as HTMLElement;
      expect(simBadgeUnmapped, 'Unmapped node badge must render').not.toBeNull();
      expect(simBadgeUnmapped.textContent, 'Unmapped state must render uppercase label, not ONLINE').toBe('시뮬레이션: UNKNOWN_VARIANT');
      expect(simBadgeUnmapped.textContent).not.toContain('ONLINE');
      expect(simBadgeUnmapped.style.color, 'Unmapped state must use neutral token, not online').toBe('var(--color-status-neutral)');
      expect(simBadgeUnmapped.style.color).not.toBe('var(--color-status-online)');
      expect(simBadgeUnmapped.style.backgroundColor).toBe('var(--color-bg-subtle)');
      expect(simBadgeUnmapped.style.borderColor).toBe('var(--color-border-subtle)');

      const simBadgeMissing = container.querySelector('[data-testid="node-sim-status-nod_rec_missing"]') as HTMLElement;
      expect(simBadgeMissing, 'Missing state node badge must render').not.toBeNull();
      expect(simBadgeMissing.textContent, 'Missing state must render UNKNOWN fallback, not ONLINE').toBe('시뮬레이션: UNKNOWN');
      expect(simBadgeMissing.textContent).not.toContain('ONLINE');
      expect(simBadgeMissing.style.color, 'Missing state must use neutral token, not online').toBe('var(--color-status-neutral)');
      expect(simBadgeMissing.style.color).not.toBe('var(--color-status-online)');
      expect(simBadgeMissing.style.backgroundColor).toBe('var(--color-bg-subtle)');
      expect(simBadgeMissing.style.borderColor).toBe('var(--color-border-subtle)');

      // Verify aria-label non-crashing and semantic fallback for unmapped and missing states
      const cardUnmapped = container.querySelector('[data-testid="node-card-nod_rec_unmapped"]') as HTMLElement;
      expect(cardUnmapped.getAttribute('aria-label')).toBe('worker-unmapped.saint.local (실제: corrupted_variant, 시뮬레이션: UNKNOWN_VARIANT)');
      const cardMissing = container.querySelector('[data-testid="node-card-nod_rec_missing"]') as HTMLElement;
      expect(cardMissing.getAttribute('aria-label')).toBe('worker-missing.saint.local (실제: unknown, 시뮬레이션: UNKNOWN)');

      // 2. Empty state screen
      await act(async () => {
        root.render(<DistributedRecoveryView nodes={[]} />);
      });

      const emptyScreen = container.querySelector('[data-testid="recovery-empty-nodes-screen"]') as HTMLElement;
      expect(emptyScreen, 'Empty nodes screen must render').not.toBeNull();
      expect(emptyScreen.style.backgroundColor).toBe('var(--color-bg-surface)');
      expect(emptyScreen.style.borderColor).toBe('var(--color-border-subtle)');
      const esBg = helperExtractVar(emptyScreen.style.backgroundColor);
      const esBd = helperExtractVar(emptyScreen.style.borderColor);
      expect(getContrast(lightTokens[esBd], lightTokens[esBg]), 'Empty screen light border contrast >= 3.0:1').toBeGreaterThanOrEqual(3.0);
      expect(getContrast(darkTokens[esBd], darkTokens[esBg]), 'Empty screen dark border contrast >= 3.0:1').toBeGreaterThanOrEqual(3.0);
    } finally {
      act(() => {
        root.unmount();
      });
      container.remove();
    }
  });


  // 9k. [Card 220 / ACC-09] Component DOM Rendering Verification: ReleaseCandidateView binds foregrounds and container backgrounds to design tokens with dynamic contrast verification
  it('ACC-09 / Card 220: ReleaseCandidateView DOM rendering binds foregrounds and container backgrounds to design tokens with dynamic contrast verification', async () => {
    const container = document.createElement('div');
    document.body.appendChild(container);
    const root = createRoot(container);

    try {
      await act(async () => {
        root.render(<ReleaseCandidateView />);
      });

      // 1. Notice Banner (var(--color-bg-subtle), var(--color-border-subtle), var(--color-text-secondary))
      const noticeBanner = container.querySelector('[data-testid="release-unexposed-notice"]') as HTMLElement;
      expect(noticeBanner, 'Release unexposed notice banner must render').not.toBeNull();
      expect(noticeBanner.style.backgroundColor).toBe('var(--color-bg-subtle)');
      expect(noticeBanner.style.borderColor).toBe('var(--color-border-subtle)');
      expect(noticeBanner.style.color).toBe('var(--color-text-secondary)');
      const nbFg = helperExtractVar(noticeBanner.style.color);
      const nbBg = helperExtractVar(noticeBanner.style.backgroundColor);
      const nbBd = helperExtractVar(noticeBanner.style.borderColor);
      expect(getContrast(lightTokens[nbFg], lightTokens[nbBg]), 'Notice banner light text contrast >= 4.5:1').toBeGreaterThanOrEqual(4.5);
      expect(getContrast(darkTokens[nbFg], darkTokens[nbBg]), 'Notice banner dark text contrast >= 4.5:1').toBeGreaterThanOrEqual(4.5);
      expect(getContrast(lightTokens[nbBd], lightTokens[nbBg]), 'Notice banner light border contrast >= 3.0:1').toBeGreaterThanOrEqual(3.0);
      expect(getContrast(darkTokens[nbBd], darkTokens[nbBg]), 'Notice banner dark border contrast >= 3.0:1').toBeGreaterThanOrEqual(3.0);

      // 2. Top Metrics Cards
      const vulnsCard = container.querySelector('[data-testid="kpi-vulns-card"]') as HTMLElement;
      const sloCard = container.querySelector('[data-testid="kpi-slo-card"]') as HTMLElement;
      const wcagCard = container.querySelector('[data-testid="kpi-wcag-card"]') as HTMLElement;
      const activeRcCard = container.querySelector('[data-testid="active-candidate-card"]') as HTMLElement;
      expect(vulnsCard.style.backgroundColor).toBe('var(--color-bg-surface)');
      expect(vulnsCard.style.borderColor).toBe('var(--color-border-subtle)');
      expect(sloCard.style.backgroundColor).toBe('var(--color-bg-surface)');
      expect(sloCard.style.borderColor).toBe('var(--color-border-subtle)');
      expect(wcagCard.style.backgroundColor).toBe('var(--color-bg-surface)');
      expect(wcagCard.style.borderColor).toBe('var(--color-border-subtle)');
      expect(activeRcCard.style.backgroundColor).toBe('var(--color-bg-surface)');
      expect(activeRcCard.style.borderColor).toBe('var(--color-border-subtle)');

      // Active candidate card has no focus-mimicking inline outline (base non-outline preserved)
      expect(activeRcCard.style.outline, 'Active candidate card must not have inline outline mimicking focus ring').toBe('');
      const computedActive = window.getComputedStyle(activeRcCard);
      expect(computedActive.outlineStyle || 'none', 'Active candidate card must not have solid outline').not.toBe('solid');

      // 3. SLO Status Badges & Ancestor Contrast (M1)
      for (const [status, cfg] of Object.entries(SLO_STATUS_CONFIG)) {
        const cVar = helperExtractVar(cfg.color);
        const bVar = helperExtractVar(cfg.border);
        const bgVar = helperExtractVar(cfg.bg);
        expect(getContrast(lightTokens[cVar], lightTokens[bgVar]), `SLO status ${status} light text contrast >= 4.5:1`).toBeGreaterThanOrEqual(4.5);
        expect(getContrast(darkTokens[cVar], darkTokens[bgVar]), `SLO status ${status} dark text contrast >= 4.5:1`).toBeGreaterThanOrEqual(4.5);
        expect(getContrast(lightTokens[bVar], lightTokens['--color-bg-surface']), `SLO status ${status} light border contrast on surface >= 3.0:1`).toBeGreaterThanOrEqual(3.0);
        expect(getContrast(darkTokens[bVar], darkTokens['--color-bg-surface']), `SLO status ${status} dark border contrast on surface >= 3.0:1`).toBeGreaterThanOrEqual(3.0);
        expect(getContrast(lightTokens[bVar], lightTokens['--color-bg-subtle']), `SLO status ${status} light border contrast on subtle >= 3.0:1`).toBeGreaterThanOrEqual(3.0);
        expect(getContrast(darkTokens[bVar], darkTokens['--color-bg-subtle']), `SLO status ${status} dark border contrast on subtle >= 3.0:1`).toBeGreaterThanOrEqual(3.0);
      }

      const releaseMgr = new ReleaseManager();
      const defaultSlos = releaseMgr.getSloRecords();
      expect(defaultSlos.length).toBeGreaterThan(0);
      for (const slo of defaultSlos) {
        const badge = container.querySelector(`[data-testid="slo-status-badge-${slo.name}"]`) as HTMLElement;
        expect(badge, `SLO badge for ${slo.name} must render in DOM`).not.toBeNull();
        const cfg = getSloStatusConfig(slo.status);
        expect(badge.style.color, `SLO badge color for ${slo.name} must match config color`).toBe(cfg.color);
        expect(badge.style.backgroundColor, `SLO badge bg for ${slo.name} must match config bg`).toBe(cfg.bg);
        expect(badge.style.borderColor, `SLO badge border for ${slo.name} must match config border`).toBe(cfg.border);
        expect(badge.style.opacity || '1', `SLO badge ${slo.name} must not have degraded opacity`).toBe('1');
        expect(badge.textContent!.trim(), `SLO badge text for ${slo.name} must match config label`).toBe(cfg.label);
      }

      // 4. Audit Status Badges & Ancestor Contrast (M1)
      for (const [status, cfg] of Object.entries(AUDIT_STATUS_CONFIG)) {
        const cVar = helperExtractVar(cfg.color);
        const bVar = helperExtractVar(cfg.border);
        const bgVar = helperExtractVar(cfg.bg);
        expect(getContrast(lightTokens[cVar], lightTokens[bgVar]), `Audit status ${status} light text contrast >= 4.5:1`).toBeGreaterThanOrEqual(4.5);
        expect(getContrast(darkTokens[cVar], darkTokens[bgVar]), `Audit status ${status} dark text contrast >= 4.5:1`).toBeGreaterThanOrEqual(4.5);
        expect(getContrast(lightTokens[bVar], lightTokens['--color-bg-subtle']), `Audit status ${status} light border contrast on subtle row >= 3.0:1`).toBeGreaterThanOrEqual(3.0);
        expect(getContrast(darkTokens[bVar], darkTokens['--color-bg-subtle']), `Audit status ${status} dark border contrast on subtle row >= 3.0:1`).toBeGreaterThanOrEqual(3.0);
      }

      const defaultAudits = releaseMgr.getAccessibilityAudits();
      expect(defaultAudits.length).toBeGreaterThan(0);
      for (const audit of defaultAudits) {
        const badge = container.querySelector(`[data-testid="audit-status-badge-${audit.ruleId}"]`) as HTMLElement;
        expect(badge, `Audit badge for ${audit.ruleId} must render in DOM`).not.toBeNull();
        const cfg = getAuditStatusConfig(audit.status);
        expect(badge.style.color, `Audit badge color for ${audit.ruleId} must match config color`).toBe(cfg.color);
        expect(badge.style.backgroundColor, `Audit badge bg for ${audit.ruleId} must match config bg`).toBe(cfg.bg);
        expect(badge.style.borderColor, `Audit badge border for ${audit.ruleId} must match config border`).toBe(cfg.border);
        expect(badge.style.opacity || '1', `Audit badge ${audit.ruleId} must not have degraded opacity`).toBe('1');
        expect(badge.textContent!.trim(), `Audit badge text for ${audit.ruleId} must match config label`).toBe(cfg.label);
      }

      // 5. Candidate Active Badges & Ancestor Contrast
      for (const [status, cfg] of Object.entries(CANDIDATE_STATUS_CONFIG)) {
        const cVar = helperExtractVar(cfg.color);
        const bVar = helperExtractVar(cfg.border);
        const bgVar = helperExtractVar(cfg.bg);
        expect(getContrast(lightTokens[cVar], lightTokens[bgVar]), `Candidate status ${status} light text contrast >= 4.5:1`).toBeGreaterThanOrEqual(4.5);
        expect(getContrast(darkTokens[cVar], darkTokens[bgVar]), `Candidate status ${status} dark text contrast >= 4.5:1`).toBeGreaterThanOrEqual(4.5);
        expect(getContrast(lightTokens[bVar], lightTokens['--color-bg-surface']), `Candidate status ${status} light border contrast >= 3.0:1`).toBeGreaterThanOrEqual(3.0);
        expect(getContrast(darkTokens[bVar], darkTokens['--color-bg-surface']), `Candidate status ${status} dark border contrast >= 3.0:1`).toBeGreaterThanOrEqual(3.0);
      }

      const defaultCandidates = releaseMgr.getReleaseCandidates();
      expect(defaultCandidates.length).toBeGreaterThan(0);
      for (const rc of defaultCandidates) {
        const badge = container.querySelector(`[data-testid="candidate-status-badge-${rc.tag}"]`) as HTMLElement;
        expect(badge, `Candidate badge for ${rc.tag} must render in DOM`).not.toBeNull();
        const cfg = getCandidateStatusConfig(rc.isActive ? 'active' : 'waiting');
        expect(badge.style.color, `Candidate badge color for ${rc.tag} must match config color`).toBe(cfg.color);
        expect(badge.style.backgroundColor, `Candidate badge bg for ${rc.tag} must match config bg`).toBe(cfg.bg);
        expect(badge.style.borderColor, `Candidate badge border for ${rc.tag} must match config border`).toBe(cfg.border);
        expect(badge.style.opacity || '1', `Candidate badge ${rc.tag} must not have degraded opacity`).toBe('1');
        expect(badge.textContent!.trim(), `Candidate badge text for ${rc.tag} must match config label`).toBe(cfg.label);
      }

      // Non-color indication for candidate status (waiting state initially)
      expect(container.textContent, 'Unverified candidate must show waiting indicator').toContain('미측정 (대기)');

      // Pairwise uniqueness across all status states (H2)
      const sloStatuses: SloRecordStatus[] = ['met', 'unmeasured', 'breached'];
      for (let i = 0; i < sloStatuses.length; i++) {
        for (let j = i + 1; j < sloStatuses.length; j++) {
          const s1 = sloStatuses[i], s2 = sloStatuses[j];
          expect(SLO_STATUS_CONFIG[s1].color, `SLO ${s1} and ${s2} must have distinct colors`).not.toBe(SLO_STATUS_CONFIG[s2].color);
          expect(SLO_STATUS_CONFIG[s1].label, `SLO ${s1} and ${s2} must have distinct labels`).not.toBe(SLO_STATUS_CONFIG[s2].label);
        }
      }
      expect(AUDIT_STATUS_CONFIG.pass.color).not.toBe(AUDIT_STATUS_CONFIG.fail.color);
      expect(AUDIT_STATUS_CONFIG.pass.label).not.toBe(AUDIT_STATUS_CONFIG.fail.label);
      expect(CANDIDATE_STATUS_CONFIG.active.color).not.toBe(CANDIDATE_STATUS_CONFIG.waiting.color);
      expect(CANDIDATE_STATUS_CONFIG.active.label).not.toBe(CANDIDATE_STATUS_CONFIG.waiting.label);

      // Fail-closed Unknown status negative verification (H1 / Codex F1)
      const unknownSlo = getSloStatusConfig('bogus_status');
      expect(unknownSlo.color).toBe('var(--color-status-unknown)');
      expect(unknownSlo.border).toBe('var(--color-status-unknown)');
      expect(unknownSlo.label).toBe('UNKNOWN (bogus_status)');

      const unknownAudit = getAuditStatusConfig('bogus_audit');
      expect(unknownAudit.color).toBe('var(--color-status-unknown)');
      expect(unknownAudit.border).toBe('var(--color-status-unknown)');
      expect(unknownAudit.label).toBe('UNKNOWN (bogus_audit)');

      const unknownCandidate = getCandidateStatusConfig('bogus_candidate');
      expect(unknownCandidate.color).toBe('var(--color-status-unknown)');
      expect(unknownCandidate.label).toBe('UNKNOWN (bogus_candidate)');

      // Prototype keys must fail closed and never bypass to Object.prototype properties (Codex F1)
      const protoKeys = ['toString', 'constructor', '__proto__'];
      for (const pk of protoKeys) {
        const unknownSloProto = getSloStatusConfig(pk);
        expect(unknownSloProto.color).toBe('var(--color-status-unknown)');
        expect(unknownSloProto.border).toBe('var(--color-status-unknown)');
        expect(unknownSloProto.label).toBe(`UNKNOWN (${pk})`);

        const unknownAuditProto = getAuditStatusConfig(pk);
        expect(unknownAuditProto.color).toBe('var(--color-status-unknown)');
        expect(unknownAuditProto.border).toBe('var(--color-status-unknown)');
        expect(unknownAuditProto.label).toBe(`UNKNOWN (${pk})`);

        const unknownCandProto = getCandidateStatusConfig(pk);
        expect(unknownCandProto.color).toBe('var(--color-status-unknown)');
        expect(unknownCandProto.border).toBe('var(--color-status-unknown)');
        expect(unknownCandProto.label).toBe(`UNKNOWN (${pk})`);
      }

      // Render with mock evidence having prototype keys and bogus SLO status to verify DOM fail-closed display (H1 / Codex F1)
      const sloSpy = vi.spyOn(ReleaseManager.prototype, 'getSloRecords').mockReturnValueOnce([
        {
          name: 'Unknown Probe SLO',
          targetValue: '99.9%',
          actualValue: '0%',
          status: 'bogus_slo' as any,
          category: 'resilience',
        },
        {
          name: 'Proto Probe toString',
          targetValue: '99.9%',
          actualValue: '0%',
          status: 'toString' as any,
          category: 'resilience',
        },
        {
          name: 'Proto Probe constructor',
          targetValue: '99.9%',
          actualValue: '0%',
          status: 'constructor' as any,
          category: 'resilience',
        },
        {
          name: 'Proto Probe __proto__',
          targetValue: '99.9%',
          actualValue: '0%',
          status: '__proto__' as any,
          category: 'resilience',
        },
      ]);
      await act(async () => {
        root.render(<ReleaseCandidateView key="bogus-and-proto-keys" />);
      });
      const bogusBadge = container.querySelector('[data-testid="slo-status-badge-Unknown Probe SLO"]') as HTMLElement;
      expect(bogusBadge, 'Bogus SLO badge must render in DOM').not.toBeNull();
      expect(bogusBadge.style.color).toBe('var(--color-status-unknown)');
      expect(bogusBadge.style.borderColor).toBe('var(--color-status-unknown)');
      expect(bogusBadge.textContent).toContain('UNKNOWN (bogus_slo)');

      for (const pk of protoKeys) {
        const protoBadge = container.querySelector(`[data-testid="slo-status-badge-Proto Probe ${pk}"]`) as HTMLElement;
        expect(protoBadge, `Prototype key "${pk}" SLO badge must render in DOM as unknown`).not.toBeNull();
        expect(protoBadge.style.color).toBe('var(--color-status-unknown)');
        expect(protoBadge.style.borderColor).toBe('var(--color-status-unknown)');
        expect(protoBadge.textContent).toContain(`UNKNOWN (${pk})`);
      }
      sloSpy.mockRestore();

      // Re-render default to proceed with rollback action notice verification
      await act(async () => {
        root.render(<ReleaseCandidateView key="default-rollback" />);
      });

      // 6. Action Notification
      // 6.a Error action notice via simulated rollback failure
      const rollbackSpy = vi.spyOn(ReleaseManager.prototype, 'rollbackToVersion').mockReturnValueOnce({
        success: false,
        error: '모의 롤백 시뮬레이션 인프라 장애',
      });

      const rollbackBtn = container.querySelector('button[aria-label*="롤백 실행"]') as HTMLButtonElement;
      expect(rollbackBtn, 'Rollback button must render for inactive candidate').not.toBeNull();
      const computedRollback = window.getComputedStyle(rollbackBtn);
      expect(computedRollback.outlineStyle || 'inherit', 'Rollback button must not suppress focus ring with outline-style none').not.toBe('none');
      expect(computedRollback.outlineWidth || 'inherit', 'Rollback button must not suppress focus ring with outline-width 0').not.toMatch(/^(0px|0)$/);
      expect(rollbackBtn.style.outline || 'inherit', 'Rollback button must not have inline outline none/0').not.toMatch(/(none|0px|\b0\b)/);
      expect(rollbackBtn.style.outlineWidth || 'inherit', 'Rollback button must not have inline outline-width 0').not.toMatch(/^(0px|0)$/);
      expect(rollbackBtn.style.outlineStyle || 'inherit', 'Rollback button must not have inline outline-style none').not.toBe('none');
      await act(async () => {
        rollbackBtn.click();
      });

      const errorNotice = container.querySelector('[data-testid="release-action-notice"]') as HTMLElement;
      expect(errorNotice, 'Error action notice banner must render').not.toBeNull();
      expect(errorNotice.style.backgroundColor).toBe('var(--color-bg-subtle)');
      expect(errorNotice.style.borderColor).toBe('var(--color-status-offline)');
      expect(errorNotice.style.color).toBe('var(--color-status-offline)');

      // 6.b Success action notice via normal rollback
      rollbackSpy.mockRestore();
      await act(async () => {
        rollbackBtn.click();
      });

      const actionNotice = container.querySelector('[data-testid="release-action-notice"]') as HTMLElement;
      expect(actionNotice, 'Action notice banner must render').not.toBeNull();
      expect(container.textContent, 'Verified candidate must show checkmark icon after rollback').toContain('✔ 모의 검증 완료');
      expect(actionNotice.style.backgroundColor).toBe('var(--color-bg-subtle)');
      expect(actionNotice.style.borderColor).toBe('var(--color-status-online)');
      expect(actionNotice.style.color).toBe('var(--color-status-online)');
      const anFg = helperExtractVar(actionNotice.style.color);
      const anBg = helperExtractVar(actionNotice.style.backgroundColor);
      const anBd = helperExtractVar(actionNotice.style.borderColor);
      expect(getContrast(lightTokens[anFg], lightTokens[anBg]), 'Action notice light text contrast >= 4.5:1').toBeGreaterThanOrEqual(4.5);
      expect(getContrast(darkTokens[anFg], darkTokens[anBg]), 'Action notice dark text contrast >= 4.5:1').toBeGreaterThanOrEqual(4.5);
      expect(getContrast(lightTokens[anBd], lightTokens[anBg]), 'Action notice light border contrast >= 3.0:1').toBeGreaterThanOrEqual(3.0);
      expect(getContrast(darkTokens[anBd], darkTokens[anBg]), 'Action notice dark border contrast >= 3.0:1').toBeGreaterThanOrEqual(3.0);
    } finally {
      act(() => {
        root.unmount();
      });
      container.remove();
    }
  });

  // 9l. [Card 226 / ACC-09] DOM Real-Render Dynamic Contrast & Accessibility Invariant Verification: ModelStudioView
  it('ACC-09 / Card 226: ModelStudioView component DOM rendering binds foregrounds and container backgrounds to design tokens with dynamic contrast verification', async () => {
    const container = document.createElement('div');
    document.body.appendChild(container);
    const root = createRoot(container);

    const helperExtractVar = (val: string) => {
      const m = val.match(/var\((--color-[a-z0-9-]+)\)/);
      if (!m) {
        throw new Error(`Expected var(--color-*), got: ${val}`);
      }
      return m[1];
    };

    const mockNodes: NodeItem[] = [
      {
        id: 'node-01',
        hostname: 'worker-gpu-01',
        status: 'online',
        schedulable: true,
        observationOnly: false,
        cpuCores: 32,
        allocatableCores: 28,
        memoryBytes: 128 * 1024 * 1024 * 1024,
        gpuName: 'NVIDIA A100-SXM4-80GB',
        gpuVramTotalBytes: 80 * 1024 * 1024 * 1024,
        gpuVramUsedBytes: 10 * 1024 * 1024 * 1024,
      } as any,
      {
        id: 'node-02',
        hostname: 'obs-node-02',
        status: 'online',
        schedulable: false,
        observationOnly: true,
        cpuCores: 16,
        allocatableCores: 0,
        memoryBytes: 64 * 1024 * 1024 * 1024,
      } as any,
      {
        id: 'node-03',
        hostname: 'worker-gpu-03',
        status: 'online',
        schedulable: true,
        observationOnly: false,
        cpuCores: 32,
        allocatableCores: 28,
        memoryBytes: 128 * 1024 * 1024 * 1024,
        gpuName: 'NVIDIA A100-SXM4-80GB',
        gpuVramTotalBytes: 80 * 1024 * 1024 * 1024,
        gpuVramUsedBytes: 0,
      } as any,
    ];

    const mockManifest = {
      modelId: 'mdl-saint-vision-v2',
      modelName: 'SaintVision Core V2',
      version: '2.0.0',
      manifestHash: 'sha256:1234567890abcdef',
      committedAt: '2026-10-02T12:00:00Z',
      sourceRunId: 'run-prod-099',
      format: 'safetensors',
      totalBytes: 40 * 1024 * 1024 * 1024,
      shardCount: 2,
      licensePolicy: 'Enterprise-Internal',
      classification: 'confidential',
      currentAvailability: 'unknown',
      shards: [
        {
          shardIndex: 0,
          byteRange: '0-20GB',
          layers: '1-16',
          sizeBytes: 20 * 1024 * 1024 * 1024,
          replicas: [
            { nodeId: 'node-01', nodeHostname: 'worker-gpu-01', status: 'healthy' },
            { nodeId: 'node-02', nodeHostname: 'obs-node-02', status: 'repairing' },
            { nodeId: 'node-03', nodeHostname: 'worker-gpu-03', status: 'missing' },
          ],
        },
      ],
    };

    try {
      await act(async () => {
        root.render(
          <ModelStudioView
            projectId="prj-test-studio"
            clusterNodes={mockNodes}
            initialModel={mockManifest as any}
          />
        );
      });

      // 1. Root & Container & Form
      const section = container.querySelector('section[aria-label="모델 기록 조회"]') as HTMLElement;
      expect(section, 'Root section must render').not.toBeNull();
      expect(section.style.backgroundColor).toBe('var(--color-bg-canvas)');
      expect(section.style.color).toBe('var(--color-text-primary)');

      // 2. Query Button
      const queryBtn = container.querySelector('[data-testid="query-model-btn"]') as HTMLButtonElement;
      expect(queryBtn).not.toBeNull();
      expect(queryBtn.style.backgroundColor).toBe('var(--color-brand-primary-bg)');
      expect(queryBtn.style.color).toBe('var(--color-brand-primary-fg)');
      const computedQuery = window.getComputedStyle(queryBtn);
      expect(computedQuery.outlineStyle || 'inherit', 'Query button must not suppress focus ring with outline-style none').not.toBe('none');
      expect(computedQuery.outlineWidth || 'inherit', 'Query button must not suppress focus ring with outline-width 0').not.toMatch(/^(0px|0)$/);
      expect(queryBtn.style.outline || 'inherit', 'Query button must not have inline outline none/0').not.toMatch(/(none|0px|\b0\b)/);
      expect(queryBtn.style.outlineWidth || 'inherit', 'Query button must not have inline outline-width 0').not.toMatch(/^(0px|0)$/);
      expect(queryBtn.style.outlineStyle || 'inherit', 'Query button must not have inline outline-style none').not.toBe('none');

      // 3. Manifest Article & Availability
      const article = container.querySelector('[data-testid="model-manifest-article"]') as HTMLElement;
      expect(article).not.toBeNull();
      expect(article.style.backgroundColor).toBe('var(--color-bg-surface)');
      expect(article.style.borderColor).toBe('var(--color-border-subtle)');

      const availBadge = container.querySelector('[data-testid="model-availability-status"]') as HTMLElement;
      expect(availBadge).not.toBeNull();
      expect(availBadge.style.color).toBe('var(--color-status-unknown)');
      expect(availBadge.style.opacity || '1', 'Availability badge must not have degraded opacity').toBe('1');
      expect(window.getComputedStyle(availBadge).opacity || '1').toBe('1');
      expect(window.getComputedStyle(availBadge).opacity).not.toMatch(/^(0\.[0-9]+|0)$/);
      expect(availBadge.textContent).toContain('알 수 없음');

      // 4. Shard Matrix Table & Badges
      const shardsTable = container.querySelector('[data-testid="shards-table"]');
      expect(shardsTable).not.toBeNull();

      // Healthy replica badge
      const healthyBadge = container.querySelector('[data-testid="replica-status-node-01"]') as HTMLElement;
      expect(healthyBadge).not.toBeNull();
      expect(healthyBadge.style.color).toBe('var(--color-status-online)');
      expect(healthyBadge.style.backgroundColor).toBe('var(--color-bg-subtle)');
      expect(healthyBadge.style.borderColor).toBe('var(--color-status-online)');
      expect(healthyBadge.style.opacity || '1', 'Healthy replica must not have degraded opacity').toBe('1');
      expect(window.getComputedStyle(healthyBadge).opacity || '1').toBe('1');
      expect(window.getComputedStyle(healthyBadge).opacity).not.toMatch(/^(0\.[0-9]+|0)$/);
      expect(healthyBadge.textContent).toContain('healthy');

      // Repairing replica badge
      const repairingBadge = container.querySelector('[data-testid="replica-status-node-02"]') as HTMLElement;
      expect(repairingBadge).not.toBeNull();
      expect(repairingBadge.style.color).toBe('var(--color-status-degraded)');
      expect(repairingBadge.style.backgroundColor).toBe('var(--color-bg-subtle)');
      expect(repairingBadge.style.borderColor).toBe('var(--color-status-degraded)');
      expect(repairingBadge.style.opacity || '1', 'Repairing replica must not have degraded opacity').toBe('1');
      expect(window.getComputedStyle(repairingBadge).opacity || '1').toBe('1');
      expect(window.getComputedStyle(repairingBadge).opacity).not.toMatch(/^(0\.[0-9]+|0)$/);
      expect(repairingBadge.textContent).toContain('repairing');

      // Missing replica badge
      const missingBadge = container.querySelector('[data-testid="replica-status-node-03"]') as HTMLElement;
      expect(missingBadge).not.toBeNull();
      expect(missingBadge.style.color).toBe('var(--color-status-offline)');
      expect(missingBadge.style.backgroundColor).toBe('var(--color-bg-subtle)');
      expect(missingBadge.style.borderColor).toBe('var(--color-status-offline)');
      expect(missingBadge.style.opacity || '1', 'Missing replica must not have degraded opacity').toBe('1');
      expect(window.getComputedStyle(missingBadge).opacity || '1').toBe('1');
      expect(window.getComputedStyle(missingBadge).opacity).not.toMatch(/^(0\.[0-9]+|0)$/);
      expect(missingBadge.textContent).toContain('missing');

      // Shard degradation alert badge
      const degBadge = container.querySelector('[data-testid="shard-degradation-badge"]') as HTMLElement;
      expect(degBadge).not.toBeNull();
      expect(degBadge.style.color).toBe('var(--color-status-degraded)');
      expect(degBadge.style.backgroundColor).toBe('var(--color-bg-subtle)');
      expect(degBadge.style.opacity || '1', 'Degradation badge must not have degraded opacity').toBe('1');
      expect(window.getComputedStyle(degBadge).opacity || '1').toBe('1');
      expect(window.getComputedStyle(degBadge).opacity).not.toMatch(/^(0\.[0-9]+|0)$/);
      expect(degBadge.textContent!.trim().length).toBeGreaterThan(0);

      // 5. Execution Planner Section & Badges
      const plannerSection = container.querySelector('[data-testid="execution-planner-section"]') as HTMLElement;
      expect(plannerSection).not.toBeNull();
      expect(plannerSection.style.backgroundColor).toBe('var(--color-bg-surface)');
      expect(plannerSection.style.borderColor).toBe('var(--color-border-subtle)');

      const planBadge = container.querySelector('[data-testid="plan-feasible-badge"]') as HTMLElement;
      expect(planBadge).not.toBeNull();
      expect(planBadge.style.color).toBe('var(--color-status-online)');
      expect(planBadge.style.backgroundColor).toBe('var(--color-bg-subtle)');
      expect(planBadge.style.opacity || '1', 'Plan badge must not have degraded opacity').toBe('1');
      expect(window.getComputedStyle(planBadge).opacity || '1').toBe('1');
      expect(window.getComputedStyle(planBadge).opacity).not.toMatch(/^(0\.[0-9]+|0)$/);
      expect(planBadge.textContent!.trim().length).toBeGreaterThan(0);

      // Trigger LAN warning with tensor_pipeline_parallel and multi-node
      const modeSelect = container.querySelector('[data-testid="execution-mode-select"]') as HTMLSelectElement;
      const node3Check = container.querySelector('[data-testid="node-select-node-03"]') as HTMLInputElement;
      await act(async () => {
        modeSelect.value = 'tensor_pipeline_parallel';
        modeSelect.dispatchEvent(new Event('change', { bubbles: true }));
        node3Check.click();
      });
      const lanWarning = container.querySelector('[data-testid="tensor-parallel-lan-warning"]') as HTMLElement;
      expect(lanWarning, 'Tensor parallel LAN warning must render when cross-node').not.toBeNull();
      expect(lanWarning.textContent).toContain('⚠️');
      expect(lanWarning.style.color).toBe('var(--color-status-degraded)');
      expect(lanWarning.style.backgroundColor).toBe('var(--color-bg-subtle)');
      expect(lanWarning.style.borderColor).toBe('var(--color-status-degraded)');
      expect(lanWarning.style.opacity || '1', 'LAN warning must not have degraded opacity').toBe('1');
      expect(window.getComputedStyle(lanWarning).opacity || '1').toBe('1');
      expect(window.getComputedStyle(lanWarning).opacity).not.toMatch(/^(0\.[0-9]+|0)$/);

      // 6. Node Assignment Table & Ineligible Badge
      const ineligBadge = container.querySelector('[data-testid="node-ineligible-badge"]') as HTMLElement;
      expect(ineligBadge).not.toBeNull();
      expect(ineligBadge.style.color).toBe('var(--color-status-offline)');
      expect(ineligBadge.style.backgroundColor).toBe('var(--color-bg-subtle)');
      expect(ineligBadge.textContent!.trim().length).toBeGreaterThan(0);

      // 7. Status Config Semantics & Contrast checks
      for (const [st, cfg] of Object.entries(REPLICA_STATUS_CONFIG)) {
        const cVar = helperExtractVar(cfg.color);
        const bgVar = helperExtractVar(cfg.bg);
        const bVar = helperExtractVar(cfg.border);
        expect(getContrast(lightTokens[cVar], lightTokens[bgVar]), `Replica status ${st} light text >= 4.5:1`).toBeGreaterThanOrEqual(4.5);
        expect(getContrast(darkTokens[cVar], darkTokens[bgVar]), `Replica status ${st} dark text >= 4.5:1`).toBeGreaterThanOrEqual(4.5);
        expect(getContrast(lightTokens[bVar], lightTokens['--color-bg-surface']), `Replica status ${st} light border >= 3.0:1`).toBeGreaterThanOrEqual(3.0);
        expect(getContrast(darkTokens[bVar], darkTokens['--color-bg-surface']), `Replica status ${st} dark border >= 3.0:1`).toBeGreaterThanOrEqual(3.0);
      }

      for (const [st, cfg] of Object.entries(PLAN_FEASIBILITY_CONFIG)) {
        const cVar = helperExtractVar(cfg.color);
        const bgVar = helperExtractVar(cfg.bg);
        expect(getContrast(lightTokens[cVar], lightTokens[bgVar]), `Plan feasibility ${st} light text >= 4.5:1`).toBeGreaterThanOrEqual(4.5);
        expect(getContrast(darkTokens[cVar], darkTokens[bgVar]), `Plan feasibility ${st} dark text >= 4.5:1`).toBeGreaterThanOrEqual(4.5);
      }

      for (const [st, cfg] of Object.entries(NODE_ELIGIBILITY_CONFIG)) {
        const cVar = helperExtractVar(cfg.color);
        const bgVar = helperExtractVar(cfg.bg);
        expect(getContrast(lightTokens[cVar], lightTokens[bgVar]), `Node eligibility ${st} light text >= 4.5:1`).toBeGreaterThanOrEqual(4.5);
        expect(getContrast(darkTokens[cVar], darkTokens[bgVar]), `Node eligibility ${st} dark text >= 4.5:1`).toBeGreaterThanOrEqual(4.5);
      }

      // F-R1 Invariant: Config keys must match wire contract enum sets EXACTLY
      expect(Object.keys(REPLICA_STATUS_CONFIG).sort(), 'REPLICA_STATUS_CONFIG must match wire contract enum [healthy, missing, repairing]').toEqual(['healthy', 'missing', 'repairing']);
      expect(Object.keys(MODEL_AVAILABILITY_CONFIG).sort(), 'MODEL_AVAILABILITY_CONFIG must match wire contract enum [unknown]').toEqual(['unknown']);

      // State uniqueness & Non-collapse
      expect(REPLICA_STATUS_CONFIG.repairing.color).not.toBe(REPLICA_STATUS_CONFIG.healthy.color);
      expect(REPLICA_STATUS_CONFIG.missing.color).not.toBe(REPLICA_STATUS_CONFIG.healthy.color);
      expect(REPLICA_STATUS_CONFIG.repairing.color).not.toBe(REPLICA_STATUS_CONFIG.missing.color);
      expect(PLAN_FEASIBILITY_CONFIG.feasible.color).not.toBe(PLAN_FEASIBILITY_CONFIG.infeasible.color);
      expect(NODE_ELIGIBILITY_CONFIG.eligible.color).not.toBe(NODE_ELIGIBILITY_CONFIG.ineligible.color);

      // Fail-closed Unknown status handling & Out-of-contract wire status rejection & Prototype key own-key defense (Codex F-R1)
      for (const invalidReplica of ['unhealthy', 'degraded', 'invalid_corrupted_state', 'bogus', 'toString', 'constructor', '__proto__']) {
        const cfg = getReplicaStatusConfig(invalidReplica);
        expect(cfg.color).toBe('var(--color-status-unknown)');
        expect(cfg.border).toBe('var(--color-status-unknown)');
        expect(cfg.label).toBe(`알 수 없음 (${invalidReplica})`);
      }

      for (const invalidAvail of ['observed', 'available', 'invalid_corrupted_state', 'bogus', 'toString', 'constructor', '__proto__', undefined, null]) {
        const availCfg = getModelAvailabilityConfig(invalidAvail as any);
        expect(availCfg.color).toBe('var(--color-status-unknown)');
        expect(availCfg.border).toBe('var(--color-status-unknown)');
        expect(availCfg.label).toContain(`알 수 없음 (${invalidAvail || 'UNKNOWN'})`);
      }

      const unknownPlan = getPlanFeasibilityConfig(false);
      expect(unknownPlan.color).toBe('var(--color-status-offline)');

      // 8. Re-render with repair alert states to test repair error/warning/success contrast
      await act(async () => {
        root.render(
          <ModelStudioView
            projectId="prj-test-studio"
            clusterNodes={mockNodes}
            initialModel={mockManifest as any}
            onRepairShard={async () => ({ success: false, repairedReplicas: [], message: '강제 에러 시뮬레이션' })}
          />
        );
      });

      const repairBtn = container.querySelector('[data-testid="repair-shard-0-btn"]') as HTMLButtonElement;
      expect(repairBtn, 'Repair shard button must be rendered for repairable degraded shard').not.toBeNull();
      const computedRepair = window.getComputedStyle(repairBtn);
      expect(computedRepair.outlineStyle || 'inherit', 'Repair button must not suppress focus ring with outline-style none').not.toBe('none');
      expect(computedRepair.outlineWidth || 'inherit', 'Repair button must not suppress focus ring with outline-width 0').not.toMatch(/^(0px|0)$/);
      expect(repairBtn.style.outline || 'inherit', 'Repair button must not have inline outline none/0').not.toMatch(/(none|0px|\b0\b)/);
      expect(repairBtn.style.outlineWidth || 'inherit', 'Repair button must not have inline outline-width 0').not.toMatch(/^(0px|0)$/);
      expect(repairBtn.style.outlineStyle || 'inherit', 'Repair button must not have inline outline-style none').not.toBe('none');

      await act(async () => {
        repairBtn.click();
      });
      const errAlert = container.querySelector('[data-testid="shard-repair-error"]') as HTMLElement;
      expect(errAlert, 'Repair error alert must render on failed repair').not.toBeNull();
      expect(errAlert.style.backgroundColor).toBe('var(--color-bg-subtle)');
      expect(errAlert.style.borderColor).toBe('var(--color-status-offline)');
      expect(errAlert.style.color).toBe('var(--color-status-offline)');
    } finally {
      act(() => {
        root.unmount();
      });
      container.remove();
    }
  });

  // 9m. [Card 228 / ACC-09] Component DOM Rendering Verification: NaturalLanguageRunView binds foregrounds and container backgrounds to design tokens with dynamic contrast verification
  it('ACC-09 / Card 228: NaturalLanguageRunView component DOM rendering binds foregrounds and container backgrounds to design tokens with dynamic contrast verification', async () => {
    const container = document.createElement('div');
    document.body.appendChild(container);
    const root = createRoot(container);

    const helperExtractVar = (val: string) => {
      const m = val.match(/var\((--color-[a-z0-9-]+)\)/);
      return m ? m[1] : val;
    };

    try {
      await act(async () => {
        root.render(<NaturalLanguageRunView />);
      });

      // 1. Unexposed Notice Banner
      const unexposedNotice = container.querySelector('[data-testid="agent-unexposed-notice"]') as HTMLElement;
      expect(unexposedNotice, 'Unexposed notice banner must render').not.toBeNull();
      expect(unexposedNotice.style.backgroundColor).toBe('var(--color-bg-surface)');
      expect(unexposedNotice.style.borderColor).toBe('var(--color-border-subtle)');
      expect(unexposedNotice.style.color).toBe('var(--color-text-primary)');

      // 2. Form submission to generate active request and diff
      const submitBtn = Array.from(container.querySelectorAll('button[type="submit"]')).find((b) =>
        b.textContent?.includes('자연어 Run 분석 및 제안 Diff 생성')
      ) as HTMLButtonElement;
      expect(submitBtn).toBeDefined();

      await act(async () => {
        submitBtn.click();
      });

      // 3. Status Badge rendering & properties (Exact string and non-color behavior preservation)
      const statusBadge = container.querySelector('[data-testid="agent-status-badge"]') as HTMLElement;
      expect(statusBadge, 'Agent status badge must render').not.toBeNull();
      expect(statusBadge.style.backgroundColor).toBe('var(--color-bg-subtle)');
      expect(statusBadge.style.color).toBe('var(--color-brand-hover)');
      expect(statusBadge.style.borderColor).toBe('var(--color-brand-hover)');
      expect(statusBadge.style.opacity || '1', 'Status badge must not have degraded opacity').toBe('1');
      expect(statusBadge.textContent).toBe('READY');

      // Success action notice from submit
      const actionNotice = container.querySelector('[data-testid="agent-action-notice"]') as HTMLElement;
      expect(actionNotice, 'Action notice must render').not.toBeNull();
      expect(actionNotice.style.backgroundColor).toBe('var(--color-bg-subtle)');
      expect(actionNotice.style.borderColor).toBe('var(--color-status-online)');
      expect(actionNotice.style.color).toBe('var(--color-status-online)');
      expect(actionNotice.style.opacity || '1').toBe('1');
      expect(actionNotice.textContent?.trim().length).toBeGreaterThan(0);

      // 4. Bounded repair loop transition (ready -> repairing)
      const refineBtn = container.querySelector('[data-testid="agent-refine-btn"]') as HTMLButtonElement;
      expect(refineBtn, 'Refine button must render').not.toBeNull();

      const computedRefine = window.getComputedStyle(refineBtn);
      expect(computedRefine.outlineStyle || 'inherit', 'Refine button must not suppress focus ring with outline-style none').not.toBe('none');
      expect(computedRefine.outlineWidth || 'inherit', 'Refine button must not suppress focus ring with outline-width 0').not.toMatch(/^(0px|0)$/);
      expect(refineBtn.style.outline || 'inherit', 'Refine button must not have inline outline none/0').not.toMatch(/(none|0px|\b0\b)/);
      expect(refineBtn.style.outlineWidth || 'inherit', 'Refine button must not have inline outline-width 0').not.toMatch(/^(0px|0)$/);
      expect(refineBtn.style.outlineStyle || 'inherit', 'Refine button must not have inline outline-style none').not.toBe('none');

      await act(async () => {
        refineBtn.click();
      });

      expect(statusBadge.style.color).toBe('var(--color-status-degraded)');
      expect(statusBadge.style.borderColor).toBe('var(--color-status-degraded)');
      expect(statusBadge.textContent).toBe('REPAIRING');

      // Info action notice from repair loop
      expect(actionNotice.style.backgroundColor).toBe('var(--color-bg-subtle)');
      expect(actionNotice.style.borderColor).toBe('var(--color-brand-hover)');
      expect(actionNotice.style.color).toBe('var(--color-brand-hover)');

      // Advance loops to rejection (loop 2, loop 3, loop 4 exceeds limit)
      await act(async () => {
        refineBtn.click();
      });
      await act(async () => {
        refineBtn.click();
      });
      await act(async () => {
        refineBtn.click();
      });

      expect(statusBadge.style.color).toBe('var(--color-status-offline)');
      expect(statusBadge.style.borderColor).toBe('var(--color-status-offline)');
      expect(statusBadge.textContent).toBe('REJECTED');

      // 5. Action Notice Banner (Error state from rejected max loop)
      expect(actionNotice, 'Action notice must render').not.toBeNull();
      expect(actionNotice.style.backgroundColor).toBe('var(--color-bg-subtle)');
      expect(actionNotice.style.borderColor).toBe('var(--color-status-offline)');
      expect(actionNotice.style.color).toBe('var(--color-status-offline)');

      // Also verify apply diff completes run and turns status to COMPLETED
      await act(async () => {
        submitBtn.click(); // generate fresh ready request
      });
      expect(statusBadge.textContent).toBe('READY');
      const applyDiffBtn = container.querySelector('[data-testid="agent-apply-diff-btn"]') as HTMLButtonElement;
      expect(applyDiffBtn, 'Apply diff button must render').not.toBeNull();
      await act(async () => {
        applyDiffBtn.click();
      });
      expect(statusBadge.textContent).toBe('COMPLETED');
      expect(statusBadge.style.color).toBe('var(--color-status-online)');
      expect(statusBadge.style.borderColor).toBe('var(--color-status-online)');

      // 6. Config table exact contract enum key set binding (F-R1)
      const expectedContractStatuses = ['completed', 'draft', 'evaluating', 'ready', 'rejected', 'repairing'];
      expect(Object.keys(AGENT_RUN_STATUS_CONFIG).sort()).toEqual(expectedContractStatuses);

      // Contrast checks for all contract statuses
      for (const [st, cfg] of Object.entries(AGENT_RUN_STATUS_CONFIG)) {
        const cVar = helperExtractVar(cfg.color);
        const bgVar = helperExtractVar(cfg.bg);
        const bVar = helperExtractVar(cfg.border);
        expect(getContrast(lightTokens[cVar], lightTokens[bgVar]), `Agent status ${st} light text >= 4.5:1`).toBeGreaterThanOrEqual(4.5);
        expect(getContrast(darkTokens[cVar], darkTokens[bgVar]), `Agent status ${st} dark text >= 4.5:1`).toBeGreaterThanOrEqual(4.5);
        expect(getContrast(lightTokens[bVar], lightTokens['--color-bg-surface']), `Agent status ${st} light border >= 3.0:1`).toBeGreaterThanOrEqual(3.0);
        expect(getContrast(darkTokens[bVar], darkTokens['--color-bg-surface']), `Agent status ${st} dark border >= 3.0:1`).toBeGreaterThanOrEqual(3.0);
        expect(cfg.label, `Agent status ${st} label must equal uppercase status`).toBe(st.toUpperCase());
      }

      // 7. Non-color distinction & State uniqueness
      expect(AGENT_RUN_STATUS_CONFIG.ready.color).not.toBe(AGENT_RUN_STATUS_CONFIG.rejected.color);
      expect(AGENT_RUN_STATUS_CONFIG.completed.color).not.toBe(AGENT_RUN_STATUS_CONFIG.rejected.color);
      expect(AGENT_RUN_STATUS_CONFIG.repairing.color).not.toBe(AGENT_RUN_STATUS_CONFIG.completed.color);
      expect(AGENT_RUN_STATUS_CONFIG.evaluating.color).not.toBe(AGENT_RUN_STATUS_CONFIG.completed.color);
      expect(AGENT_RUN_STATUS_CONFIG.draft.color).not.toBe(AGENT_RUN_STATUS_CONFIG.ready.color);

      // 8. Fail-closed Unknown status handling, Out-of-contract rejection & Prototype key defense
      const unknownStatus = getAgentRunStatusConfig('invalid_corrupted_state');
      expect(unknownStatus.color).toBe('var(--color-status-unknown)');
      expect(unknownStatus.border).toBe('var(--color-status-unknown)');
      expect(unknownStatus.bg).toBe('var(--color-bg-subtle)');
      expect(unknownStatus.label).toBe('UNKNOWN (invalid_corrupted_state)');

      // Empty / null / undefined fallbacks (X27)
      expect(getAgentRunStatusConfig(null).label).toBe('UNKNOWN');
      expect(getAgentRunStatusConfig('').label).toBe('UNKNOWN');
      expect(getAgentRunStatusConfig(undefined).label).toBe('UNKNOWN');
      expect(getAgentRunStatusConfig(null).color).toBe('var(--color-status-unknown)');

      // Out-of-contract wire enum rejection (F-R1, R2-2, R2-3)
      const outOfContractStatuses = ['planning', 'running', 'executing', 'awaiting_approval', 'failed', 'blocked', 'idle', 'bogus'];
      for (const ooc of outOfContractStatuses) {
        const oocCfg = getAgentRunStatusConfig(ooc);
        expect(oocCfg.color).toBe('var(--color-status-unknown)');
        expect(oocCfg.border).toBe('var(--color-status-unknown)');
        expect(oocCfg.label).toBe(`UNKNOWN (${ooc})`);
      }

      // Prototype key defense (X29)
      for (const pk of ['toString', 'constructor', '__proto__']) {
        const protoStatus = getAgentRunStatusConfig(pk);
        expect(protoStatus.color).toBe('var(--color-status-unknown)');
        expect(protoStatus.border).toBe('var(--color-status-unknown)');
        expect(protoStatus.label).toBe(`UNKNOWN (${pk})`);
      }

      // Strict exact-match lookup invariants: Case-folding, whitespace & alias mutations strictly rejected (X30, X31, X31b)
      // 1. Case variations & leading/trailing whitespace variations must strictly fail to match known keys
      const caseAndWhitespaceVariants = [
        'COMPLETED', 'Completed', ' completed', 'completed ',
        'DRAFT', 'Draft', ' draft',
        'READY', 'Ready', ' ready',
        'REPAIRING', 'Repairing', ' repairing',
        'REJECTED', 'Rejected', ' rejected',
        'EVALUATING', 'Evaluating', ' evaluating',
      ];
      for (const variant of caseAndWhitespaceVariants) {
        const vCfg = getAgentRunStatusConfig(variant);
        expect(vCfg.label).toBe(`UNKNOWN (${variant})`);
        expect(vCfg.color).toBe('var(--color-status-unknown)');
        expect(vCfg.border).toBe('var(--color-status-unknown)');
      }

      // 2. Out-of-contract aliases (succeeded, success, failed, failure) must never map to known statuses
      const aliasVariants = ['succeeded', 'success', 'passed', 'failed', 'failure'];
      for (const alias of aliasVariants) {
        const aCfg = getAgentRunStatusConfig(alias);
        expect(aCfg.label).toBe(`UNKNOWN (${alias})`);
        expect(aCfg.color).toBe('var(--color-status-unknown)');
        expect(aCfg.border).toBe('var(--color-status-unknown)');
      }
      expect(Object.hasOwn(AGENT_RUN_STATUS_CONFIG, 'succeeded')).toBe(false);
      expect(Object.hasOwn(AGENT_RUN_STATUS_CONFIG, 'failed')).toBe(false);

      // 3. Exact key equivalence invariant: getAgentRunStatusConfig(s) === AGENT_RUN_STATUS_CONFIG[s] iff s is a valid contract key
      const knownKeys = new Set(['draft', 'evaluating', 'ready', 'repairing', 'completed', 'rejected']);
      const sampleQueries = [
        ...knownKeys,
        ...caseAndWhitespaceVariants,
        ...aliasVariants,
        'planning', 'running', 'executing', 'awaiting_approval', 'blocked', 'idle', 'bogus',
      ];
      for (const query of sampleQueries) {
        const res = getAgentRunStatusConfig(query);
        if (knownKeys.has(query)) {
          expect(res).toBe(AGENT_RUN_STATUS_CONFIG[query as AgentRunStatusKey]);
          expect(res.label).toBe(query.toUpperCase());
          expect(res.color).not.toBe('var(--color-status-unknown)');
        } else {
          expect(res.label).toBe(`UNKNOWN (${query})`);
          expect(res.color).toBe('var(--color-status-unknown)');
        }
      }
    } finally {
      act(() => {
        root.unmount();
      });
      container.remove();
    }
  });
  // 9n. [Card 230 / ACC-09] Component DOM Rendering Verification: DesktopShell binds foregrounds and container backgrounds to design tokens with dynamic contrast verification
  it('ACC-09 / Card 230: DesktopShell component DOM rendering binds foregrounds and container backgrounds to design tokens with dynamic contrast verification', async () => {
    const container = document.createElement('div');
    document.body.appendChild(container);
    const root = createRoot(container);

    const mockNotifications: DesktopNotification[] = [
      { id: 'notif_1', title: '배포 성공', message: '카나리 배포가 성공적으로 완료되었습니다.', level: 'success', timestamp: '12:00', read: false },
      { id: 'notif_2', title: '시스템 점검', message: '정기 점검 작업이 예정되어 있습니다.', level: 'info', timestamp: '12:01', read: true },
      { id: 'notif_3', title: '자원 경고', message: 'VRAM 사용량이 85%를 초과했습니다.', level: 'warning', timestamp: '12:02', read: true },
      { id: 'notif_4', title: '노드 장애', message: '노드 nod_03 응답 없음 상태입니다.', level: 'error', timestamp: '12:03', read: true },
      { id: 'notif_5', title: '심각 장애', message: '계약외 critical 레벨 알림입니다.', level: 'critical' as any, timestamp: '12:04', read: true },
      { id: 'notif_6', title: '대문자 에러', message: '대소문자 변형 ERROR 레벨 알림입니다.', level: 'ERROR' as any, timestamp: '12:05', read: true },
      { id: 'notif_7', title: '대소문자 인포', message: '대소문자 변형 Info 레벨 알림입니다.', level: 'Info' as any, timestamp: '12:06', read: true },
      { id: 'notif_8', title: '프로토타입 키', message: '프로토타입 toString 레벨 알림입니다.', level: 'toString' as any, timestamp: '12:07', read: true },
    ];

    const mockShellProps = {
      projectId: 'prj_test_01',
      tenantId: 'tnt_test_01',
      checkoutId: 'chk_test_01',
      nodes: [
        {
          id: 'nod_test_01',
          name: 'Node 01',
          hostname: 'node-win-01',
          os: 'windows' as const,
          cpuCores: 16,
          cpuUsagePercent: 20,
          memoryTotalBytes: 64 * 1024 ** 3,
          memoryUsagePercent: 30,
          gpuName: 'RTX 4090',
          gpuCount: 1,
          status: 'online' as const,
          labels: {},
          observationOnly: false,
          schedulable: true,
        },
      ],
      runs: [],
      approvals: [],
      workspaces: [],
      currentReviewerId: 'usr_test_operator',
      onRefreshNodes: vi.fn(),
      onApprove: vi.fn(),
      onReject: vi.fn(),
      onChangeUser: vi.fn(),
      onSwitchToPortalView: vi.fn(),
      currentTheme: 'dark' as const,
      onToggleTheme: vi.fn(),
      notifications: mockNotifications,
    };

    try {
      await act(async () => {
        root.render(<DesktopShell {...mockShellProps} />);
      });

      // 1. Desktop Shell Wallpaper Container
      const shellContainer = container.querySelector('[data-testid="desktop-shell-container"]') as HTMLElement;
      expect(shellContainer, 'Desktop shell container must render').not.toBeNull();
      expect(shellContainer.style.backgroundColor).toBe('var(--color-bg-canvas)');
      expect(shellContainer.style.backgroundImage).toContain('var(--color-brand-subtle)');
      expect(shellContainer.style.backgroundImage).toContain('var(--color-bg-surface)');
      expect(shellContainer.style.backgroundImage).toContain('var(--color-bg-canvas)');

      // 2. Top System Menu Bar
      const startMenuTrigger = container.querySelector('#desktop-start-menu-trigger') as HTMLButtonElement;
      expect(startMenuTrigger, 'Start menu trigger must render').not.toBeNull();
      expect(startMenuTrigger.style.color).toBe('var(--color-brand-hover)');

      const modeSwitcher = container.querySelector('[data-testid="desktop-mode-switcher"]') as HTMLButtonElement;
      expect(modeSwitcher, 'Mode switcher button must render').not.toBeNull();
      expect(modeSwitcher.style.backgroundColor).toBe('var(--color-brand-subtle)');
      expect(modeSwitcher.style.borderColor).toBe('var(--color-brand-hover)');
      expect(modeSwitcher.style.color).toBe('var(--color-brand-hover)');
      expect(modeSwitcher.style.opacity || '1', 'Mode switcher must not have degraded opacity').toBe('1');

      // Focus ring preservation on mode switcher & start menu trigger
      const computedModeSwitcher = window.getComputedStyle(modeSwitcher);
      expect(computedModeSwitcher.outlineStyle || 'inherit', 'Mode switcher must not suppress focus ring with outline-style none').not.toBe('none');
      expect(computedModeSwitcher.outlineWidth || 'inherit', 'Mode switcher must not suppress focus ring with outline-width 0').not.toMatch(/^(0px|0)$/);
      expect(modeSwitcher.style.outline || 'inherit', 'Mode switcher must not have inline outline none/0').not.toMatch(/(none|0px|\b0\b)/);
      expect(modeSwitcher.style.outlineWidth || 'inherit', 'Mode switcher must not have inline outline-width 0').not.toMatch(/^(0px|0)$/);
      expect(modeSwitcher.style.outlineStyle || 'inherit', 'Mode switcher must not have inline outline-style none').not.toBe('none');

      // Focus event verification on mode switcher (kills onFocus outline: none mutant M09b)
      modeSwitcher.focus();
      modeSwitcher.dispatchEvent(new Event('focus'));
      expect(modeSwitcher.style.outline || 'inherit', 'Mode switcher must not set outline none on focus').not.toMatch(/(none|0px|\b0\b)/);
      expect(modeSwitcher.style.outlineStyle || 'inherit', 'Mode switcher must not set outline-style none on focus').not.toBe('none');
      expect(window.getComputedStyle(modeSwitcher).outlineStyle || 'inherit').not.toBe('none');

      // Unread notification dot indicator
      const unreadDot = container.querySelector('[data-testid="desktop-unread-notif-dot"]') as HTMLElement;
      expect(unreadDot, 'Unread notification dot must render').not.toBeNull();
      expect(unreadDot.style.backgroundColor).toBe('var(--color-status-offline)');

      // 3. Floating Dock Toolbar
      const taskbar = container.querySelector('[data-testid="desktop-taskbar"]') as HTMLElement;
      expect(taskbar, 'Taskbar dock must render').not.toBeNull();
      expect(taskbar.style.backgroundColor).toBe('var(--color-bg-surface)');
      expect(taskbar.style.borderColor).toBe('var(--color-border-subtle)');

      // Dock icon rendering for all shortcut items (kills M08c)
      for (const item of DESKTOP_SHORTCUTS) {
        const tile = container.querySelector(`[data-testid="desktop-dock-tile-${item.appId}"]`) as HTMLElement;
        expect(tile, `Dock tile for ${item.appId} must render`).not.toBeNull();
        expect(tile.textContent, `Dock tile for ${item.appId} must render icon ${item.icon}`).toContain(item.icon);
      }

      // Active dock tile & running dot (my-computer is active initially)
      const activeDockTile = container.querySelector('[data-testid="desktop-dock-tile-my-computer"]') as HTMLElement;
      expect(activeDockTile, 'Active dock tile must render').not.toBeNull();
      expect(activeDockTile.style.backgroundColor).toBe('var(--color-brand-subtle)');
      expect(activeDockTile.style.borderColor).toBe('var(--color-brand-hover)');

      const activeRunningDot = container.querySelector('[data-testid="desktop-dock-running-my-computer"]') as HTMLElement;
      expect(activeRunningDot, 'Active running dot must render').not.toBeNull();
      expect(activeRunningDot.style.backgroundColor).toBe('var(--color-brand-hover)');
      expect(activeRunningDot.style.opacity || '1', 'Active running dot must not have degraded opacity').toBe('1');

      // Click my-computer dock button to minimize it, transitioning it to open-but-inactive
      const myComputerTile = container.querySelector('[data-testid="desktop-dock-tile-my-computer"]') as HTMLElement;
      const myComputerDockBtn = myComputerTile?.closest('button') as HTMLButtonElement;
      expect(myComputerDockBtn, 'My computer dock button must exist').not.toBeNull();
      await act(async () => {
        myComputerDockBtn.click();
      });

      // Now my-computer is open but minimized/inactive
      const inactiveDockTile = container.querySelector('[data-testid="desktop-dock-tile-my-computer"]') as HTMLElement;
      expect(inactiveDockTile, 'Inactive dock tile must render').not.toBeNull();
      expect(inactiveDockTile.style.backgroundColor).toBe('var(--color-bg-subtle)');
      expect(inactiveDockTile.style.borderColor).toBe('var(--color-border-subtle)');

      const inactiveRunningDot = container.querySelector('[data-testid="desktop-dock-running-my-computer"]') as HTMLElement;
      expect(inactiveRunningDot, 'Inactive running dot must render when my-computer is open but inactive').not.toBeNull();
      expect(inactiveRunningDot.style.backgroundColor).toBe('var(--color-border-strong)');
      expect(inactiveRunningDot.style.backgroundColor, 'Inactive running dot must not collapse to text-muted').not.toBe('var(--color-text-muted)'); // kills M03
      expect(inactiveRunningDot.style.backgroundColor, 'Inactive running dot must not collapse to brand-hover').not.toBe('var(--color-brand-hover)'); // kills M07b
      expect(inactiveRunningDot.style.opacity || '1', 'Inactive running dot must not have degraded opacity').toBe('1'); // kills M04b

      // 3:1 Non-text contrast verification for running dots and unread badge dot (WCAG 1.4.11)
      const activeDotToken = helperExtractVar(activeRunningDot.style.backgroundColor);
      const inactiveDotToken = helperExtractVar(inactiveRunningDot.style.backgroundColor);
      const unreadDotToken = helperExtractVar(unreadDot.style.backgroundColor);
      expect(getContrast(lightTokens[activeDotToken], lightTokens['--color-bg-surface']), 'Active dot light contrast >= 3.0:1').toBeGreaterThanOrEqual(3.0);
      expect(getContrast(darkTokens[activeDotToken], darkTokens['--color-bg-surface']), 'Active dot dark contrast >= 3.0:1').toBeGreaterThanOrEqual(3.0);
      expect(getContrast(lightTokens[inactiveDotToken], lightTokens['--color-bg-surface']), 'Inactive dot light contrast >= 3.0:1').toBeGreaterThanOrEqual(3.0);
      expect(getContrast(darkTokens[inactiveDotToken], darkTokens['--color-bg-surface']), 'Inactive dot dark contrast >= 3.0:1').toBeGreaterThanOrEqual(3.0);
      expect(getContrast(lightTokens[unreadDotToken], lightTokens['--color-bg-surface']), 'Unread dot light contrast >= 3.0:1').toBeGreaterThanOrEqual(3.0);
      expect(getContrast(darkTokens[unreadDotToken], darkTokens['--color-bg-surface']), 'Unread dot dark contrast >= 3.0:1').toBeGreaterThanOrEqual(3.0);

      // 4. Notification Center Drawer & Badges
      const notifTrigger = container.querySelector('#desktop-notification-trigger') as HTMLButtonElement;
      expect(notifTrigger, 'Notification trigger must render').not.toBeNull();
      expect(notifTrigger.textContent, 'Notification trigger must render bell glyph 🔔').toContain('🔔'); // kills M08b

      await act(async () => {
        notifTrigger.click();
      });

      const notifDrawer = container.querySelector('#desktop-notification-drawer') as HTMLElement;
      expect(notifDrawer, 'Notification drawer must open').not.toBeNull();
      expect(notifDrawer.style.backgroundColor).toBe('var(--color-bg-surface)');
      expect(notifDrawer.style.borderColor).toBe('var(--color-border-subtle)');
      expect(notifDrawer.style.color).toBe('var(--color-text-primary)');

      const notifItems = container.querySelectorAll('[data-testid="desktop-notification-item"]');
      expect(notifItems.length).toBe(8);

      const notifBadges = Array.from(container.querySelectorAll('[data-testid="desktop-notification-badge"]')) as HTMLElement[];
      expect(notifBadges.length).toBe(8);

      // Verify SUCCESS badge
      const successBadge = notifBadges.find((b) => b.textContent === 'SUCCESS');
      expect(successBadge).toBeDefined();
      expect(successBadge!.style.backgroundColor).toBe('var(--color-bg-subtle)');
      expect(successBadge!.style.color).toBe('var(--color-status-online)');
      expect(successBadge!.style.borderColor).toBe('var(--color-status-online)');
      expect(successBadge!.style.opacity || '1', 'Notification badge must not have degraded opacity').toBe('1');

      // Verify INFO badge
      const infoBadge = notifBadges.find((b) => b.textContent === 'INFO');
      expect(infoBadge).toBeDefined();
      expect(infoBadge!.style.backgroundColor).toBe('var(--color-bg-subtle)');
      expect(infoBadge!.style.color).toBe('var(--color-brand-hover)');
      expect(infoBadge!.style.borderColor).toBe('var(--color-brand-hover)');

      // Verify WARNING badge
      const warningBadge = notifBadges.find((b) => b.textContent === 'WARNING');
      expect(warningBadge).toBeDefined();
      expect(warningBadge!.style.backgroundColor).toBe('var(--color-bg-subtle)');
      expect(warningBadge!.style.color).toBe('var(--color-status-degraded)');
      expect(warningBadge!.style.borderColor).toBe('var(--color-status-degraded)');

      // Verify ERROR badge
      const errorBadge = notifBadges.find((b) => b.textContent === 'ERROR');
      expect(errorBadge).toBeDefined();
      expect(errorBadge!.style.backgroundColor).toBe('var(--color-bg-subtle)');
      expect(errorBadge!.style.color).toBe('var(--color-status-offline)');
      expect(errorBadge!.style.borderColor).toBe('var(--color-status-offline)');

      // Verify out-of-contract critical level rendered in DOM (kills M11b & M13)
      const criticalBadge = notifBadges.find((b) => b.textContent === 'UNKNOWN (critical)');
      expect(criticalBadge, 'Out-of-contract critical badge must render in DOM with UNKNOWN (critical)').toBeDefined();
      expect(criticalBadge!.style.backgroundColor).toBe('var(--color-bg-subtle)');
      expect(criticalBadge!.style.color).toBe('var(--color-status-unknown)');
      expect(criticalBadge!.style.borderColor).toBe('var(--color-status-unknown)');

      // Verify case-variant ERROR level rendered in DOM (kills M14)
      const caseErrorBadge = notifBadges.find((b) => b.textContent === 'UNKNOWN (ERROR)');
      expect(caseErrorBadge, 'Case-variant ERROR badge must render in DOM with UNKNOWN (ERROR)').toBeDefined();
      expect(caseErrorBadge!.style.backgroundColor).toBe('var(--color-bg-subtle)');
      expect(caseErrorBadge!.style.color).toBe('var(--color-status-unknown)');
      expect(caseErrorBadge!.style.borderColor).toBe('var(--color-status-unknown)');

      // Verify case-variant Info level rendered in DOM (kills case-insensitive lookup to known info)
      const caseInfoBadge = notifBadges.find((b) => b.textContent === 'UNKNOWN (Info)');
      expect(caseInfoBadge, 'Case-variant Info badge must render in DOM with UNKNOWN (Info)').toBeDefined();
      expect(caseInfoBadge!.style.backgroundColor).toBe('var(--color-bg-subtle)');
      expect(caseInfoBadge!.style.color).toBe('var(--color-status-unknown)');
      expect(caseInfoBadge!.style.borderColor).toBe('var(--color-status-unknown)');

      // Verify prototype key toString level rendered in DOM (kills M12)
      const protoBadge = notifBadges.find((b) => b.textContent === 'UNKNOWN (toString)');
      expect(protoBadge, 'Prototype toString badge must render in DOM with UNKNOWN (toString)').toBeDefined();
      expect(protoBadge!.style.backgroundColor).toBe('var(--color-bg-subtle)');
      expect(protoBadge!.style.color).toBe('var(--color-status-unknown)');
      expect(protoBadge!.style.borderColor).toBe('var(--color-status-unknown)');

      // 5. Config table exact contract enum key set binding
      const expectedContractLevels = ['error', 'info', 'success', 'warning'];
      expect(Object.keys(NOTIFICATION_LEVEL_CONFIG).sort()).toEqual(expectedContractLevels);

      // 6. Fail-closed out-of-contract rejection and prototype key defense
      const corruptedCfg = getNotificationLevelConfig('corrupted_unknown' as any);
      expect(corruptedCfg.color).toBe('var(--color-status-unknown)');
      expect(corruptedCfg.border).toBe('var(--color-status-unknown)');
      expect(corruptedCfg.bg).toBe('var(--color-bg-subtle)');
      expect(corruptedCfg.label).toBe('UNKNOWN (corrupted_unknown)');

      const bogusCfg = getNotificationLevelConfig('bogus' as any);
      expect(bogusCfg.color).toBe('var(--color-status-unknown)');
      expect(bogusCfg.label).toBe('UNKNOWN (bogus)');

      const errorUpperCfg = getNotificationLevelConfig('ERROR' as any);
      expect(errorUpperCfg.color).toBe('var(--color-status-unknown)');
      expect(errorUpperCfg.label).toBe('UNKNOWN (ERROR)');

      const infoCaseCfg = getNotificationLevelConfig('Info' as any);
      expect(infoCaseCfg.color).toBe('var(--color-status-unknown)');
      expect(infoCaseCfg.label).toBe('UNKNOWN (Info)');

      const criticalCfg = getNotificationLevelConfig('critical' as any);
      expect(criticalCfg.color).toBe('var(--color-status-unknown)');
      expect(criticalCfg.label).toBe('UNKNOWN (critical)');

      const debugCfg = getNotificationLevelConfig('debug' as any);
      expect(debugCfg.color).toBe('var(--color-status-unknown)');
      expect(debugCfg.label).toBe('UNKNOWN (debug)');

      const nullCfg = getNotificationLevelConfig(null as any);
      expect(nullCfg.color).toBe('var(--color-status-unknown)');
      expect(nullCfg.label).toBe('UNKNOWN');

      const emptyCfg = getNotificationLevelConfig('' as any);
      expect(emptyCfg.color).toBe('var(--color-status-unknown)');
      expect(emptyCfg.label).toBe('UNKNOWN');

      const undefCfg = getNotificationLevelConfig(undefined as any);
      expect(undefCfg.color).toBe('var(--color-status-unknown)');
      expect(undefCfg.label).toBe('UNKNOWN');

      // Prototype key hijack defense
      const protoKeys = ['toString', 'constructor', '__proto__', 'valueOf', 'hasOwnProperty', 'isPrototypeOf'];
      for (const pk of protoKeys) {
        const protoCfg = getNotificationLevelConfig(pk as any);
        expect(protoCfg.color, `Prototype key ${pk} must fall back to var(--color-status-unknown)`).toBe('var(--color-status-unknown)');
        expect(protoCfg.label).toBe(`UNKNOWN (${pk})`);
      }

      // Close notification drawer
      await act(async () => {
        notifTrigger.click();
      });

      // 7. Open Start Menu and check dropdown
      await act(async () => {
        startMenuTrigger.click();
      });

      const startMenuDropdown = container.querySelector('#desktop-start-menu-dropdown') as HTMLElement;
      expect(startMenuDropdown, 'Start menu dropdown must open').not.toBeNull();
      expect(startMenuDropdown.style.backgroundColor).toBe('var(--color-bg-surface)');
      expect(startMenuDropdown.style.borderColor).toBe('var(--color-border-subtle)');
      expect(startMenuDropdown.style.color).toBe('var(--color-text-primary)');

      // 8. Dynamic contrast ratio verification for all 4 notification levels in Light and Dark
      for (const level of expectedContractLevels as ('error' | 'info' | 'success' | 'warning')[]) {
        const cfg = NOTIFICATION_LEVEL_CONFIG[level];
        const lightFgHex = resolveTokenHex(helperExtractVar(cfg.color), lightTokens);
        const lightBgHex = resolveTokenHex(helperExtractVar(cfg.bg), lightTokens);
        const lightBorderHex = resolveTokenHex(helperExtractVar(cfg.border), lightTokens);

        const darkFgHex = resolveTokenHex(helperExtractVar(cfg.color), darkTokens);
        const darkBgHex = resolveTokenHex(helperExtractVar(cfg.bg), darkTokens);
        const darkBorderHex = resolveTokenHex(helperExtractVar(cfg.border), darkTokens);

        // Text contrast >= 4.5:1
        const lightTextCr = getContrast(lightFgHex, lightBgHex);
        const darkTextCr = getContrast(darkFgHex, darkBgHex);
        expect(lightTextCr, `Notification ${level} light text >= 4.5:1`).toBeGreaterThanOrEqual(4.5);
        expect(darkTextCr, `Notification ${level} dark text >= 4.5:1`).toBeGreaterThanOrEqual(4.5);

        // Border contrast >= 3.0:1
        const lightBorderCr = getContrast(lightBorderHex, lightBgHex);
        const darkBorderCr = getContrast(darkBorderHex, darkBgHex);
        expect(lightBorderCr, `Notification ${level} light border >= 3.0:1`).toBeGreaterThanOrEqual(3.0);
        expect(darkBorderCr, `Notification ${level} dark border >= 3.0:1`).toBeGreaterThanOrEqual(3.0);
      }
    } finally {
      act(() => {
        root.unmount();
      });
      container.remove();
    }
  });


  // 9o. [Card 235 / ACC-09] Component DOM Rendering Verification: PlacementSimulator binds foregrounds and container backgrounds to design tokens with dynamic contrast verification
  it('ACC-09 / Card 235: PlacementSimulator component DOM rendering binds foregrounds and container backgrounds to design tokens with dynamic contrast verification', async () => {
    const container = document.createElement('div');
    document.body.appendChild(container);
    const root = createRoot(container);

    const mockNodes: NodeItem[] = [
      {
        id: 'nod_test_01',
        name: 'Node 01 (Win GPU)',
        hostname: 'node-win-01',
        os: 'windows' as const,
        cpuCores: 16,
        cpuUsagePercent: 20,
        memoryTotalBytes: 64 * 1024 ** 3,
        memoryUsedBytes: 16 * 1024 ** 3,
        memoryUsagePercent: 25,
        gpuName: 'RTX 4090',
        gpuCount: 1,
        status: 'online' as const,
        labels: {},
        observationOnly: false,
        schedulable: true,
        allocatableCores: 14,
        allocatableMemoryBytes: 50 * 1024 ** 3,
      },
      {
        id: 'nod_test_02',
        name: 'Node 02 (Linux CPU)',
        hostname: 'node-linux-02',
        os: 'linux' as const,
        cpuCores: 8,
        cpuUsagePercent: 30,
        memoryTotalBytes: 32 * 1024 ** 3,
        memoryUsedBytes: 8 * 1024 ** 3,
        memoryUsagePercent: 25,
        gpuName: '',
        gpuCount: 0,
        status: 'online' as const,
        labels: {},
        observationOnly: false,
        schedulable: true,
        allocatableCores: 6,
        allocatableMemoryBytes: 24 * 1024 ** 3,
      },
    ];

    const mockPools: PoolItem[] = [
      { poolId: 'pool_01', projectId: 'prj_test_01', name: 'GPU 가속 연산 풀', status: 'active', memberCount: 3 },
      { poolId: 'pool_02', projectId: 'prj_test_01', name: 'CPU 범용 풀', status: 'active', memberCount: 2 },
    ];

    const mockCapacity: PoolCapacityResponse = {
      activeMemberCount: 3,
      memberCount: 3,
      name: 'GPU 가속 연산 풀',
      poolId: 'pool_01',
      note: '정상 가동',
      units: {},
      unmeasuredNodes: [],
      spareNow: { cpuMillicores: 12000, ramBytes: 48 * 1024 ** 3, gpuDevices: 2 },
      totalOffered: { cpuMillicores: 24000, ramBytes: 96 * 1024 ** 3, gpuDevices: 4 },
      largestSingleNode: { cpuMillicores: 8000, ramBytes: 32 * 1024 ** 3, gpuDevices: 2 },
      nodes: [],
    };

    const mockCandidates: CandidateItem[] = [
      {
        announcementId: 'ann_01',
        claimedHostname: 'node-cand-alpha',
        claimedOsType: 'linux',
        claimedCpuCores: 16,
        claimedRamBytes: 64 * 1024 ** 3,
        claimedGpuCount: 1,
        state: 'candidate' as const,
        verified: false as const,
        announceCount: 1,
        firstSeenAt: '2026-10-02T10:00:00Z',
        lastSeenAt: '2026-10-02T10:05:00Z',
        sourceIp: '10.0.0.1',
        stale: false,
        instanceId: 'inst_01',
      },
      {
        announcementId: 'ann_02',
        claimedHostname: 'node-cand-beta',
        claimedOsType: 'windows',
        claimedCpuCores: 8,
        claimedRamBytes: 32 * 1024 ** 3,
        claimedGpuCount: 0,
        state: 'admitted' as any,
        verified: false as const,
        announceCount: 2,
        firstSeenAt: '2026-10-02T10:00:00Z',
        lastSeenAt: '2026-10-02T10:05:00Z',
        sourceIp: '10.0.0.2',
        stale: false,
        instanceId: 'inst_02',
      },
      {
        announcementId: 'ann_03',
        claimedHostname: 'node-cand-gamma',
        claimedOsType: 'linux',
        claimedCpuCores: 4,
        claimedRamBytes: 16 * 1024 ** 3,
        claimedGpuCount: 0,
        state: 'CANDIDATE' as any,
        verified: false as const,
        announceCount: 3,
        firstSeenAt: '2026-10-02T10:00:00Z',
        lastSeenAt: '2026-10-02T10:05:00Z',
        sourceIp: '10.0.0.3',
        stale: false,
        instanceId: 'inst_03',
      },
      {
        announcementId: 'ann_04',
        claimedHostname: 'node-cand-delta',
        claimedOsType: 'linux',
        claimedCpuCores: 8,
        claimedRamBytes: 32 * 1024 ** 3,
        claimedGpuCount: 0,
        state: 'toString' as any,
        verified: false as const,
        announceCount: 1,
        firstSeenAt: '2026-10-02T10:00:00Z',
        lastSeenAt: '2026-10-02T10:05:00Z',
        sourceIp: '10.0.0.4',
        stale: false,
        instanceId: 'inst_04',
      },
    ];

    const mockProps = {
      nodes: mockNodes,
      initialPools: mockPools,
      initialPoolsState: 'success' as const,
      initialPoolCapacity: mockCapacity,
      initialPoolCapacityState: 'error' as const,
      initialPoolCapacityError: '실시간 용량 초과 경고: 모의 한도 도달',
      initialPreviewState: 'error' as const,
      initialPreviewError: '서버 배치 미리보기 실패: 모의 연결 오류',
      initialCandidates: mockCandidates,
      initialCandidatesState: 'success' as const,
    };

    try {
      await act(async () => {
        root.render(<PlacementSimulator {...mockProps} />);
      });

      // 1. Local Simulation Badge
      const localSimBadge = container.querySelector('[data-testid="local-simulation-badge"]') as HTMLElement;
      expect(localSimBadge, 'Local simulation badge must render').not.toBeNull();
      expect(localSimBadge.style.backgroundColor).toBe('var(--color-bg-subtle)');
      expect(localSimBadge.style.borderColor).toBe('var(--color-status-degraded)');
      expect(localSimBadge.style.color).toBe('var(--color-status-degraded)');
      expect(localSimBadge.textContent).toContain('로컬 결정론적 평가 (UNVERIFIED: 로컬 시뮬레이션 전용)');
      expect(localSimBadge.style.opacity || '1', 'Badge must not have degraded opacity').toBe('1');

      // 2. Resource Pool selection buttons (Selected vs Unselected)
      const poolButtons = container.querySelectorAll('button');
      const pool01Btn = Array.from(poolButtons).find((b) => b.textContent?.includes('GPU 가속 연산 풀')) as HTMLButtonElement;
      const pool02Btn = Array.from(poolButtons).find((b) => b.textContent?.includes('CPU 범용 풀')) as HTMLButtonElement;
      expect(pool01Btn, 'Pool 01 button must render').toBeDefined();
      expect(pool02Btn, 'Pool 02 button must render').toBeDefined();

      // Initially pool_01 is selected
      expect(pool01Btn.style.backgroundColor).toBe('var(--color-brand-subtle)');
      expect(pool01Btn.style.borderColor).toBe('var(--color-brand-hover)');
      expect(pool01Btn.style.color).toBe('var(--color-brand-hover)');

      expect(pool02Btn.style.backgroundColor).toBe('var(--color-bg-subtle)');
      expect(pool02Btn.style.borderColor).toBe('var(--color-border-subtle)');
      expect(pool02Btn.style.color).toBe('var(--color-text-secondary)');

      // Click pool_02 to toggle selection
      await act(async () => {
        pool02Btn.click();
      });
      expect(pool02Btn.style.backgroundColor).toBe('var(--color-brand-subtle)');
      expect(pool02Btn.style.borderColor).toBe('var(--color-brand-hover)');
      expect(pool02Btn.style.color).toBe('var(--color-brand-hover)');

      expect(pool01Btn.style.backgroundColor).toBe('var(--color-bg-subtle)');
      expect(pool01Btn.style.borderColor).toBe('var(--color-border-subtle)');
      expect(pool01Btn.style.color).toBe('var(--color-text-secondary)');

      // 3. GPU Toggle Button
      const gpuBtn = Array.from(container.querySelectorAll('button')).find((b) =>
        b.textContent?.includes('CPU 전용 가능') || b.textContent?.includes('GPU 필수 요구')
      ) as HTMLButtonElement;
      expect(gpuBtn, 'GPU toggle button must render').toBeDefined();

      // Initially requiresGpu is false
      expect(gpuBtn.style.backgroundColor).toBe('var(--color-bg-subtle)');
      expect(gpuBtn.style.borderColor).toBe('var(--color-border-subtle)');
      expect(gpuBtn.style.color).toBe('var(--color-text-secondary)');

      // Click to toggle requiresGpu to true
      await act(async () => {
        gpuBtn.click();
      });
      expect(gpuBtn.style.backgroundColor).toBe('var(--color-brand-subtle)');
      expect(gpuBtn.style.borderColor).toBe('var(--color-brand-hover)');
      expect(gpuBtn.style.color).toBe('var(--color-brand-hover)');

      // Focus ring preservation on GPU button
      const computedGpu = window.getComputedStyle(gpuBtn);
      expect(computedGpu.outlineStyle || 'inherit').not.toBe('none');
      expect(computedGpu.outlineWidth || 'inherit').not.toMatch(/^(0px|0)$/);
      expect(gpuBtn.style.outline || 'inherit').not.toMatch(/(none|0px|\b0\b)/);
      expect(gpuBtn.style.outlineWidth || 'inherit').not.toMatch(/^(0px|0)$/);
      expect(gpuBtn.style.outlineStyle || 'inherit').not.toBe('none');

      gpuBtn.focus();
      gpuBtn.dispatchEvent(new Event('focus'));
      expect(gpuBtn.style.outline || 'inherit').not.toMatch(/(none|0px|\b0\b)/);
      expect(gpuBtn.style.outlineStyle || 'inherit').not.toBe('none');

      // Focus ring preservation on pool button
      const computedPool = window.getComputedStyle(pool01Btn);
      expect(computedPool.outlineStyle || 'inherit').not.toBe('none');
      expect(pool01Btn.style.outline || 'inherit').not.toMatch(/(none|0px|\b0\b)/);
      expect(pool01Btn.style.outlineStyle || 'inherit').not.toBe('none');

      // 4. Preview Error Banner & Retry Button
      const prevErrorBanner = container.querySelector('[data-testid="preview-error-banner"]') as HTMLElement;
      expect(prevErrorBanner, 'Preview error banner must render').not.toBeNull();
      expect(prevErrorBanner.style.backgroundColor).toBe('var(--color-bg-subtle)');
      expect(prevErrorBanner.style.borderColor).toBe('var(--color-status-offline)');
      expect(prevErrorBanner.style.color).toBe('var(--color-status-offline)');
      expect(prevErrorBanner.textContent, 'Preview error banner must contain warning icon').toContain('⚠️');
      expect(prevErrorBanner.textContent, 'Preview error banner must contain failure heading').toContain('서버 배치 미리보기 실패');

      const prevRetryBtn = container.querySelector('[data-testid="preview-retry-btn"]') as HTMLButtonElement;
      expect(prevRetryBtn, 'Preview retry button must render').not.toBeNull();
      expect(prevRetryBtn.style.backgroundColor).toBe('var(--color-bg-subtle)');
      expect(prevRetryBtn.style.color).toBe('var(--color-text-primary)');
      expect(prevRetryBtn.style.borderColor).toBe('var(--color-border-subtle)');
      expect(prevRetryBtn.textContent).toContain('재시도 (Retry)');

      // Focus ring preservation on retry button
      const computedRetry = window.getComputedStyle(prevRetryBtn);
      expect(computedRetry.outlineStyle || 'inherit').not.toBe('none');
      expect(prevRetryBtn.style.outline || 'inherit').not.toMatch(/(none|0px|\b0\b)/);
      expect(prevRetryBtn.style.outlineStyle || 'inherit').not.toBe('none');

      // 4a. Pool capacity error in DOM
      const capError = container.querySelector('[data-testid="pool-capacity-error"]') as HTMLElement;
      expect(capError, 'Pool capacity error banner must render').not.toBeNull();
      expect(capError.style.backgroundColor).toBe('var(--color-bg-subtle)');
      expect(capError.style.borderColor).toBe('var(--color-status-offline)');
      expect(capError.style.color).toBe('var(--color-status-offline)');
      expect(capError.textContent).toContain('⚠️');
      expect(capError.textContent).toContain('실시간 용량 초과 경고');

      // 5. Discovery Candidates State Badges (Contract candidate, Out-of-contract, Case variant, Prototype key)
      const candAlphaBadge = container.querySelector('[data-testid="candidate-status-ann_01"]') as HTMLElement;
      expect(candAlphaBadge, 'Candidate alpha badge must render').not.toBeNull();
      expect(candAlphaBadge.textContent).toBe('CANDIDATE (미검증)');
      expect(candAlphaBadge.style.color).toBe('var(--color-status-degraded)');
      expect(candAlphaBadge.style.backgroundColor).toBe('var(--color-bg-subtle)');
      expect(candAlphaBadge.style.borderColor).toBe('var(--color-status-degraded)');
      expect(candAlphaBadge.style.opacity || '1', 'Candidate badge must not have degraded opacity').toBe('1');

      const candBetaBadge = container.querySelector('[data-testid="candidate-status-ann_02"]') as HTMLElement;
      expect(candBetaBadge, 'Out-of-contract candidate beta badge must render with UNKNOWN (admitted)').not.toBeNull();
      expect(candBetaBadge.textContent).toBe('UNKNOWN (admitted)');
      expect(candBetaBadge.style.color).toBe('var(--color-status-unknown)');
      expect(candBetaBadge.style.backgroundColor).toBe('var(--color-bg-subtle)');
      expect(candBetaBadge.style.borderColor).toBe('var(--color-status-unknown)');

      const candGammaBadge = container.querySelector('[data-testid="candidate-status-ann_03"]') as HTMLElement;
      expect(candGammaBadge, 'Case-variant candidate gamma badge must render with UNKNOWN (CANDIDATE)').not.toBeNull();
      expect(candGammaBadge.textContent).toBe('UNKNOWN (CANDIDATE)');
      expect(candGammaBadge.style.color).toBe('var(--color-status-unknown)');
      expect(candGammaBadge.style.backgroundColor).toBe('var(--color-bg-subtle)');
      expect(candGammaBadge.style.borderColor).toBe('var(--color-status-unknown)');

      const candDeltaBadge = container.querySelector('[data-testid="candidate-status-ann_04"]') as HTMLElement;
      expect(candDeltaBadge, 'Prototype key candidate delta badge must render with UNKNOWN (toString)').not.toBeNull();
      expect(candDeltaBadge.textContent).toBe('UNKNOWN (toString)');
      expect(candDeltaBadge.style.color).toBe('var(--color-status-unknown)');
      expect(candDeltaBadge.style.backgroundColor).toBe('var(--color-bg-subtle)');
      expect(candDeltaBadge.style.borderColor).toBe('var(--color-status-unknown)');

      // 5b. Danger Banners in DOM (pools-error-banner and candidates-error-banner)
      await act(async () => {
        root.render(
          <PlacementSimulator
            key="error-state-render"
            {...mockProps}
            initialPoolsState="error"
            initialPoolsError="자원 풀 서버 연결 거부"
            initialCandidatesState="error"
            initialCandidatesError="후보 노드 레지스트리 통신 오류"
          />
        );
      });

      // 5b-1. pools-error-banner
      const poolsErrorBanner = container.querySelector('[data-testid="pools-error-banner"]') as HTMLElement;
      expect(poolsErrorBanner, 'Pools error banner must render').not.toBeNull();
      expect(poolsErrorBanner.style.backgroundColor).toBe('var(--color-bg-subtle)');
      expect(poolsErrorBanner.style.borderColor).toBe('var(--color-status-offline)');
      expect(poolsErrorBanner.style.color).toBe('var(--color-status-offline)');
      expect(poolsErrorBanner.textContent).toContain('⚠️');
      expect(poolsErrorBanner.textContent).toContain('자원 풀 연동 실패');
      expect(poolsErrorBanner.textContent).toContain('자원 풀 서버 연결 거부');

      const poolsRetryBtn = container.querySelector('[data-testid="pools-retry-btn"]') as HTMLButtonElement;
      expect(poolsRetryBtn, 'Pools retry button must render').not.toBeNull();
      expect(poolsRetryBtn.style.backgroundColor).toBe('var(--color-bg-subtle)');
      expect(poolsRetryBtn.style.color).toBe('var(--color-text-primary)');
      expect(poolsRetryBtn.style.borderColor).toBe('var(--color-border-subtle)');
      expect(poolsRetryBtn.textContent).toContain('재시도 (Retry)');
      const computedPoolsRetry = window.getComputedStyle(poolsRetryBtn);
      expect(computedPoolsRetry.outlineStyle || 'inherit').not.toBe('none');
      expect(poolsRetryBtn.style.outline || 'inherit').not.toMatch(/(none|0px|\b0\b)/);

      // 5b-2. candidates-error-banner
      const candErrorBanner = container.querySelector('[data-testid="candidates-error-banner"]') as HTMLElement;
      expect(candErrorBanner, 'Candidates error banner must render').not.toBeNull();
      expect(candErrorBanner.style.backgroundColor).toBe('var(--color-bg-subtle)');
      expect(candErrorBanner.style.borderColor).toBe('var(--color-status-offline)');
      expect(candErrorBanner.style.color).toBe('var(--color-status-offline)');
      expect(candErrorBanner.textContent).toContain('⚠️');
      expect(candErrorBanner.textContent).toContain('디스커버리 후보 조회 실패');
      expect(candErrorBanner.textContent).toContain('후보 노드 레지스트리 통신 오류');

      const candRetryBtn = container.querySelector('[data-testid="candidates-retry-btn"]') as HTMLButtonElement;
      expect(candRetryBtn, 'Candidates retry button must render').not.toBeNull();
      expect(candRetryBtn.style.backgroundColor).toBe('var(--color-bg-subtle)');
      expect(candRetryBtn.style.color).toBe('var(--color-text-primary)');
      expect(candRetryBtn.style.borderColor).toBe('var(--color-border-subtle)');
      expect(candRetryBtn.textContent).toContain('재시도 (Retry)');
      const computedCandRetry = window.getComputedStyle(candRetryBtn);
      expect(computedCandRetry.outlineStyle || 'inherit').not.toBe('none');
      expect(candRetryBtn.style.outline || 'inherit').not.toMatch(/(none|0px|\b0\b)/);

      // 6. DISCOVERY_CANDIDATE_STATE_CONFIG exact key set contract check
      expect(Object.keys(DISCOVERY_CANDIDATE_STATE_CONFIG).sort()).toEqual(['candidate']);

      // 7. Unit helper fail-closed and prototype key defense
      const normCfg = getDiscoveryCandidateStateConfig('candidate');
      expect(normCfg.color).toBe('var(--color-status-degraded)');
      expect(normCfg.label).toBe('CANDIDATE (미검증)');

      const admittedCfg = getDiscoveryCandidateStateConfig('admitted');
      expect(admittedCfg.color).toBe('var(--color-status-unknown)');
      expect(admittedCfg.label).toBe('UNKNOWN (admitted)');

      const upperCandCfg = getDiscoveryCandidateStateConfig('CANDIDATE');
      expect(upperCandCfg.color).toBe('var(--color-status-unknown)');
      expect(upperCandCfg.label).toBe('UNKNOWN (CANDIDATE)');

      const titleCandCfg = getDiscoveryCandidateStateConfig('Candidate');
      expect(titleCandCfg.color).toBe('var(--color-status-unknown)');
      expect(titleCandCfg.label).toBe('UNKNOWN (Candidate)');

      const nullCandCfg = getDiscoveryCandidateStateConfig(null);
      expect(nullCandCfg.color).toBe('var(--color-status-unknown)');
      expect(nullCandCfg.label).toBe('UNKNOWN');

      const undefCandCfg = getDiscoveryCandidateStateConfig(undefined);
      expect(undefCandCfg.color).toBe('var(--color-status-unknown)');
      expect(undefCandCfg.label).toBe('UNKNOWN');

      const emptyCandCfg = getDiscoveryCandidateStateConfig('');
      expect(emptyCandCfg.color).toBe('var(--color-status-unknown)');
      expect(emptyCandCfg.label).toBe('UNKNOWN');

      const protoKeys = ['toString', 'constructor', '__proto__', 'valueOf', 'hasOwnProperty', 'isPrototypeOf'];
      for (const pk of protoKeys) {
        const protoCfg = getDiscoveryCandidateStateConfig(pk as any);
        expect(protoCfg.color, `Prototype key ${pk} must fall back to var(--color-status-unknown)`).toBe('var(--color-status-unknown)');
        expect(protoCfg.label).toBe(`UNKNOWN (${pk})`);
      }
    } finally {
      act(() => {
        root.unmount();
      });
      container.remove();
    }
  });

  // 9p. [Card 245 / ACC-09] ApprovalCenter DOM Rendering & Strict Token Parity
  it('ACC-09 / Card 245: ApprovalCenter component DOM rendering binds foregrounds and container backgrounds to design tokens with dynamic contrast verification', async () => {
    const container = document.createElement('div');
    document.body.appendChild(container);
    const root = createRoot(container);

    const mockApprovals: ApprovalItem[] = [
      {
        id: 'apr_001',
        runId: 'run_001',
        status: 'pending',
        target: 'Worker cluster scaling',
        policyReason: 'High blast radius',
        expiresAt: new Date(Date.now() + 3600000).toISOString(),
        requiredApprovals: 2,
        firstApprovedBy: 'usr_alice',
      },
      {
        id: 'apr_002',
        runId: 'run_002',
        status: 'approved',
        target: 'Model rollout v2',
        policyReason: 'Verified checkpoint',
        expiresAt: new Date(Date.now() + 3600000).toISOString(),
        requiredApprovals: 1,
      },
      {
        id: 'apr_003',
        runId: 'run_003',
        status: 'rejected',
        target: 'Host root shell',
        policyReason: 'Prohibited command',
        expiresAt: new Date(Date.now() + 3600000).toISOString(),
      },
      {
        id: 'apr_004',
        runId: 'run_004',
        status: 'expired',
        target: 'Emergency brake',
        policyReason: 'TTL elapsed',
        expiresAt: new Date(Date.now() - 3600000).toISOString(),
      },
      {
        id: 'apr_005',
        runId: 'run_005',
        status: 'dispatched',
        target: 'Automated remediation',
        policyReason: 'Pre-approved workflow',
        expiresAt: new Date(Date.now() + 3600000).toISOString(),
      },
      {
        id: 'apr_006',
        runId: 'run_006',
        status: 'admitted' as any,
        target: 'Bypassed admission',
        policyReason: 'Invalid state injection',
        expiresAt: new Date(Date.now() + 3600000).toISOString(),
      },
      {
        id: 'apr_007',
        runId: 'run_007',
        status: 'PENDING' as any,
        target: 'Casing bypass',
        policyReason: 'Casing mismatch',
        expiresAt: new Date(Date.now() + 3600000).toISOString(),
      },
      {
        id: 'apr_008',
        runId: 'run_008',
        status: 'toString' as any,
        target: 'Prototype hijack test',
        policyReason: 'Prototype key defense',
        expiresAt: new Date(Date.now() + 3600000).toISOString(),
      },
      {
        id: 'apr_009',
        runId: 'run_009',
        status: 'pending',
        target: 'Two person rule unstarted',
        policyReason: 'Requires 2 approvals',
        expiresAt: new Date(Date.now() + 3600000).toISOString(),
        requiredApprovals: 2,
      },
    ];

    try {
      await act(async () => {
        root.render(
          <ApprovalCenter
            approvals={mockApprovals}
            currentUserId="usr_alice"
            onApprove={vi.fn()}
            onReject={vi.fn()}
            approvalsState="error"
            approvalError="Connection timeout"
            lastFetchedAt={new Date(2026, 9, 2, 23, 30, 0)}
            onRefresh={vi.fn()}
          />
        );
      });

      // 1. Freshness indicator
      const freshnessBadge = container.querySelector('[data-testid="approval-freshness-indicator"]') as HTMLElement;
      expect(freshnessBadge).not.toBeNull();
      expect(freshnessBadge.style.backgroundColor).toBe('var(--color-brand-subtle)');
      expect(freshnessBadge.style.borderColor).toBe('var(--color-brand-hover)');
      expect(freshnessBadge.style.color).toBe('var(--color-brand-hover)');

      // 2. Refresh button
      const refreshBtn = container.querySelector('[data-testid="approval-refresh-btn"]') as HTMLElement;
      expect(refreshBtn).not.toBeNull();
      expect(refreshBtn.style.backgroundColor).toBe('var(--color-bg-subtle)');
      expect(refreshBtn.style.borderColor).toBe('var(--color-border-subtle)');
      expect(refreshBtn.style.color).toBe('var(--color-text-primary)');
      expect(refreshBtn.textContent).toContain('새로고침');

      // Focus ring preservation on refresh button
      const computedRefresh = window.getComputedStyle(refreshBtn);
      expect(computedRefresh.outlineStyle !== 'none' || computedRefresh.outline !== 'none', 'Refresh button focus ring must be preserved').toBe(true);

      // 3. Stale warning banner
      const staleWarning = container.querySelector('[data-testid="approval-stale-warning"]') as HTMLElement;
      expect(staleWarning).not.toBeNull();
      expect(staleWarning.style.backgroundColor).toBe('var(--color-bg-subtle)');
      expect(staleWarning.style.borderColor).toBe('var(--color-status-offline)');
      expect(staleWarning.style.color).toBe('var(--color-status-offline)');
      expect(staleWarning.textContent).toContain('⚠️');
      expect(staleWarning.textContent).toContain('승인 목록 동기화 실패');
      const staleSubtext = staleWarning.children[1] as HTMLElement;
      expect(staleSubtext).not.toBeNull();
      expect(staleSubtext.style.color).toBe('var(--color-status-offline)');
      expect(staleSubtext.textContent).toContain('화면 확인 시점 스냅샷입니다');

      // 4. Status badges
      const status001 = container.querySelector('[data-testid="approval-status-apr_001"]') as HTMLElement;
      expect(status001.textContent).toBe('PENDING');
      expect(status001.style.color).toBe('var(--color-status-degraded)');
      expect(status001.style.backgroundColor).toBe('var(--color-bg-subtle)');
      expect(status001.style.borderColor).toBe('var(--color-status-degraded)');
      expect(status001.style.opacity || '1', 'Pending status badge opacity must not be degraded').toBe('1');

      const status002 = container.querySelector('[data-testid="approval-status-apr_002"]') as HTMLElement;
      expect(status002.textContent).toBe('APPROVED');
      expect(status002.style.color).toBe('var(--color-status-online)');
      expect(status002.style.backgroundColor).toBe('var(--color-bg-subtle)');
      expect(status002.style.borderColor).toBe('var(--color-status-online)');

      const status003 = container.querySelector('[data-testid="approval-status-apr_003"]') as HTMLElement;
      expect(status003.textContent).toBe('REJECTED');
      expect(status003.style.color).toBe('var(--color-status-offline)');
      expect(status003.style.backgroundColor).toBe('var(--color-bg-subtle)');
      expect(status003.style.borderColor).toBe('var(--color-status-offline)');

      const status004 = container.querySelector('[data-testid="approval-status-apr_004"]') as HTMLElement;
      expect(status004.textContent).toBe('EXPIRED');
      expect(status004.style.color).toBe('var(--color-status-offline)');
      expect(status004.style.backgroundColor).toBe('var(--color-bg-subtle)');
      expect(status004.style.borderColor).toBe('var(--color-status-offline)');

      const status005 = container.querySelector('[data-testid="approval-status-apr_005"]') as HTMLElement;
      expect(status005.textContent).toBe('DISPATCHED');
      expect(status005.style.color).toBe('var(--color-brand-hover)');
      expect(status005.style.backgroundColor).toBe('var(--color-bg-subtle)');
      expect(status005.style.borderColor).toBe('var(--color-brand-hover)');

      // Out of contract, casing, prototype defense in DOM
      const status006 = container.querySelector('[data-testid="approval-status-apr_006"]') as HTMLElement;
      expect(status006.textContent).toBe('UNKNOWN (admitted)');
      expect(status006.style.color).toBe('var(--color-status-unknown)');
      expect(status006.style.backgroundColor).toBe('var(--color-bg-subtle)');
      expect(status006.style.borderColor).toBe('var(--color-status-unknown)');

      const status007 = container.querySelector('[data-testid="approval-status-apr_007"]') as HTMLElement;
      expect(status007.textContent).toBe('UNKNOWN (PENDING)');
      expect(status007.style.color).toBe('var(--color-status-unknown)');
      expect(status007.style.backgroundColor).toBe('var(--color-bg-subtle)');
      expect(status007.style.borderColor).toBe('var(--color-status-unknown)');

      const status008 = container.querySelector('[data-testid="approval-status-apr_008"]') as HTMLElement;
      expect(status008.textContent).toBe('UNKNOWN (toString)');
      expect(status008.style.color).toBe('var(--color-status-unknown)');
      expect(status008.style.backgroundColor).toBe('var(--color-bg-subtle)');
      expect(status008.style.borderColor).toBe('var(--color-status-unknown)');

      // Two-person progression badges
      const twoPerson001 = container.querySelector('[data-testid="approval-two-person-apr_001"]') as HTMLElement;
      expect(twoPerson001).not.toBeNull();
      expect(twoPerson001.textContent).toBe('1/2 승인 (2차 대기)');
      expect(twoPerson001.style.color).toBe('var(--color-brand-hover)');
      expect(twoPerson001.style.borderColor).toBe('var(--color-brand-hover)');
      expect(twoPerson001.style.opacity || '1', 'Two-person badge opacity must not be degraded').toBe('1');

      const twoPerson009 = container.querySelector('[data-testid="approval-two-person-apr_009"]') as HTMLElement;
      expect(twoPerson009).not.toBeNull();
      expect(twoPerson009.textContent).toBe('2인 필수');
      expect(twoPerson009.style.color).toBe('var(--color-text-secondary)');
      expect(twoPerson009.style.borderColor).toBe('var(--color-border-subtle)');

      // 5. Empty error state with retry button
      await act(async () => {
        root.render(
          <ApprovalCenter
            approvals={[]}
            currentUserId="usr_alice"
            onApprove={vi.fn()}
            onReject={vi.fn()}
            approvalsState="error"
            approvalError="Network unreachable"
            onRefresh={vi.fn()}
          />
        );
      });

      const errBox = container.querySelector('[data-testid="approval-fetch-error-state"]') as HTMLElement;
      expect(errBox).not.toBeNull();
      expect(errBox.style.borderColor).toBe('var(--color-status-offline)');
      expect(errBox.style.backgroundColor).toBe('var(--color-bg-surface)');
      expect(errBox.textContent).toContain('⚠️');

      const errHeading = errBox.querySelector('h3') as HTMLElement;
      expect(errHeading).not.toBeNull();
      expect(errHeading.textContent).toBe('승인 안건 동기화 실패');
      expect(errHeading.style.color).toBe('var(--color-status-offline)');

      const errBody = errBox.querySelector('p') as HTMLElement;
      expect(errBody).not.toBeNull();
      expect(errBody.textContent).toContain('서버와 통신할 수 없어 승인 요청 목록을 조회하지 못했습니다');
      expect(errBody.style.color).toBe('var(--color-text-muted)');

      const retryBtn = container.querySelector('[data-testid="approval-error-retry-btn"]') as HTMLElement;
      expect(retryBtn).not.toBeNull();
      expect(retryBtn.style.backgroundColor).toBe('var(--color-bg-subtle)');
      expect(retryBtn.style.color).toBe('var(--color-text-primary)');
      expect(retryBtn.style.borderColor).toBe('var(--color-border-subtle)');
      expect(retryBtn.textContent).toContain('재시도 (Retry)');

      // Focus ring preservation on retry button
      const computedRetry = window.getComputedStyle(retryBtn);
      expect(computedRetry.outlineStyle !== 'none' || computedRetry.outline !== 'none', 'Retry button focus ring must be preserved').toBe(true);

      // 6. Contract exact key set check
      expect(Object.keys(APPROVAL_STATUS_CONFIG).sort()).toEqual(['approved', 'dispatched', 'expired', 'pending', 'rejected']);

      // 7. Unit helper fail-closed and prototype defense
      const normPending = getApprovalStatusConfig('pending');
      expect(normPending.color).toBe('var(--color-status-degraded)');
      expect(normPending.label).toBe('PENDING');

      const normApproved = getApprovalStatusConfig('approved');
      expect(normApproved.color).toBe('var(--color-status-online)');
      expect(normApproved.label).toBe('APPROVED');

      const normRejected = getApprovalStatusConfig('rejected');
      expect(normRejected.color).toBe('var(--color-status-offline)');
      expect(normRejected.label).toBe('REJECTED');

      const normExpired = getApprovalStatusConfig('expired');
      expect(normExpired.color).toBe('var(--color-status-offline)');
      expect(normExpired.label).toBe('EXPIRED');

      const normDispatched = getApprovalStatusConfig('dispatched');
      expect(normDispatched.color).toBe('var(--color-brand-hover)');
      expect(normDispatched.label).toBe('DISPATCHED');

      const unknownOut = getApprovalStatusConfig('admitted');
      expect(unknownOut.color).toBe('var(--color-status-unknown)');
      expect(unknownOut.label).toBe('UNKNOWN (admitted)');

      const unknownUpper = getApprovalStatusConfig('PENDING');
      expect(unknownUpper.color).toBe('var(--color-status-unknown)');
      expect(unknownUpper.label).toBe('UNKNOWN (PENDING)');

      const nullCfg = getApprovalStatusConfig(null);
      expect(nullCfg.color).toBe('var(--color-status-unknown)');
      expect(nullCfg.label).toBe('UNKNOWN');

      const undefCfg = getApprovalStatusConfig(undefined);
      expect(undefCfg.color).toBe('var(--color-status-unknown)');
      expect(undefCfg.label).toBe('UNKNOWN');

      const emptyCfg = getApprovalStatusConfig('');
      expect(emptyCfg.color).toBe('var(--color-status-unknown)');
      expect(emptyCfg.label).toBe('UNKNOWN');

      const protoKeys = ['toString', 'constructor', '__proto__', 'valueOf', 'hasOwnProperty', 'isPrototypeOf'];
      for (const pk of protoKeys) {
        const protoCfg = getApprovalStatusConfig(pk as any);
        expect(protoCfg.color, `Prototype key ${pk} must fall back to var(--color-status-unknown)`).toBe('var(--color-status-unknown)');
        expect(protoCfg.label).toBe(`UNKNOWN (${pk})`);
      }

      // 8. Contrast verification for getApprovalStatusConfig UNKNOWN fallback
      const unkLightCr = getContrast(resolveTokenHex('--color-status-unknown', lightTokens), resolveTokenHex('--color-bg-subtle', lightTokens));
      expect(unkLightCr, 'ApprovalCenter UNKNOWN status fallback on light subtle must pass 4.5:1').toBeCloseTo(6.47, 2);
      expect(unkLightCr).toBeGreaterThanOrEqual(4.5);
      const unkDarkCr = getContrast(resolveTokenHex('--color-status-unknown', darkTokens), resolveTokenHex('--color-bg-subtle', darkTokens));
      expect(unkDarkCr, 'ApprovalCenter UNKNOWN status fallback on dark subtle must pass 4.5:1').toBeCloseTo(5.82, 2);
      expect(unkDarkCr).toBeGreaterThanOrEqual(4.5);
    } finally {
      act(() => {
        root.unmount();
      });
      container.remove();
    }
  });

  // 9q. [Card 248 / ACC-09] ClusterOverview DOM Rendering & Strict Token Parity
  it('ACC-09 / Card 248: ClusterOverview component DOM rendering binds foregrounds and container backgrounds to design tokens with dynamic contrast verification', async () => {
    const container = document.createElement('div');
    document.body.appendChild(container);
    const root = createRoot(container);

    const mockNodes: NodeItem[] = [
      {
        id: 'nod_001',
        hostname: 'node-online.sv.lan',
        status: 'online',
        os: 'linux',
        cpuCores: 32,
        cpuUsagePercent: 45,
        memoryTotalBytes: 64 * 1024 ** 3,
        memoryUsedBytes: 32 * 1024 ** 3,
        gpuName: 'NVIDIA H100',
        gpuCount: 2,
        gpuVramTotalBytes: 160 * 1024 ** 3,
        gpuVramUsedBytes: 80 * 1024 ** 3,
        storageTotalBytes: 2 * 1024 ** 4,
        storageUsedBytes: 1 * 1024 ** 4,
        heartbeatAt: new Date(2026, 9, 3, 2, 0, 0).toISOString(),
      },
      {
        id: 'nod_002',
        hostname: 'node-active.sv.lan',
        status: 'active',
        os: 'linux',
        cpuCores: 16,
        cpuUsagePercent: 20,
        memoryTotalBytes: 32 * 1024 ** 3,
        memoryUsedBytes: 16 * 1024 ** 3,
        gpuCount: 0,
        storageTotalBytes: 1 * 1024 ** 4,
        storageUsedBytes: 500 * 1024 ** 3,
        heartbeatAt: new Date(2026, 9, 3, 2, 0, 0).toISOString(),
      },
      {
        id: 'nod_003',
        hostname: 'node-degraded.sv.lan',
        status: 'degraded',
        os: 'linux',
        cpuCores: 8,
        cpuUsagePercent: 85,
        memoryTotalBytes: 16 * 1024 ** 3,
        memoryUsedBytes: 14 * 1024 ** 3,
        gpuCount: 0,
        storageTotalBytes: 500 * 1024 ** 3,
        storageUsedBytes: 400 * 1024 ** 3,
        heartbeatAt: new Date(2026, 9, 3, 2, 0, 0).toISOString(),
      },
      {
        id: 'nod_004',
        hostname: 'node-lost.sv.lan',
        status: 'lost',
        os: 'linux',
        cpuCores: 16,
        cpuUsagePercent: 0,
        memoryTotalBytes: 32 * 1024 ** 3,
        memoryUsedBytes: 0,
        gpuCount: 0,
        storageTotalBytes: 1 * 1024 ** 4,
        storageUsedBytes: 0,
        heartbeatAt: new Date(2026, 9, 3, 1, 0, 0).toISOString(),
      },
      {
        id: 'nod_005',
        hostname: 'node-unknown.sv.lan',
        status: 'unknown',
        os: 'linux',
        cpuCores: 8,
        cpuUsagePercent: 10,
        memoryTotalBytes: 16 * 1024 ** 3,
        memoryUsedBytes: 2 * 1024 ** 3,
        gpuCount: 0,
        storageTotalBytes: 500 * 1024 ** 3,
        storageUsedBytes: 100 * 1024 ** 3,
        heartbeatAt: new Date(2026, 9, 3, 2, 0, 0).toISOString(),
      },
      {
        id: 'nod_006',
        hostname: 'node-offline.sv.lan',
        status: 'offline',
        os: 'linux',
        cpuCores: 8,
        cpuUsagePercent: 0,
        memoryTotalBytes: 16 * 1024 ** 3,
        memoryUsedBytes: 0,
        gpuCount: 0,
        storageTotalBytes: 500 * 1024 ** 3,
        storageUsedBytes: 0,
        heartbeatAt: new Date(2026, 9, 3, 0, 0, 0).toISOString(),
      },
      {
        id: 'nod_007',
        hostname: 'node-draining.sv.lan',
        status: 'draining',
        os: 'linux',
        cpuCores: 8,
        cpuUsagePercent: 5,
        memoryTotalBytes: 16 * 1024 ** 3,
        memoryUsedBytes: 1 * 1024 ** 3,
        gpuCount: 0,
        storageTotalBytes: 500 * 1024 ** 3,
        storageUsedBytes: 50 * 1024 ** 3,
        heartbeatAt: new Date(2026, 9, 3, 2, 0, 0).toISOString(),
      },
      {
        id: 'nod_008',
        hostname: 'node-enrolling.sv.lan',
        status: 'enrolling',
        os: 'linux',
        cpuCores: 8,
        cpuUsagePercent: 0,
        memoryTotalBytes: 16 * 1024 ** 3,
        memoryUsedBytes: 0,
        gpuCount: 0,
        storageTotalBytes: 500 * 1024 ** 3,
        storageUsedBytes: 0,
        heartbeatAt: new Date(2026, 9, 3, 2, 0, 0).toISOString(),
      },
      {
        id: 'nod_009',
        hostname: 'node-retired.sv.lan',
        status: 'retired',
        os: 'linux',
        cpuCores: 8,
        cpuUsagePercent: 0,
        memoryTotalBytes: 16 * 1024 ** 3,
        memoryUsedBytes: 0,
        gpuCount: 0,
        storageTotalBytes: 500 * 1024 ** 3,
        storageUsedBytes: 0,
        heartbeatAt: new Date(2026, 9, 2, 0, 0, 0).toISOString(),
      },
      {
        id: 'nod_010',
        hostname: 'node-admitted.sv.lan',
        status: 'admitted' as any,
        os: 'linux',
        cpuCores: 8,
        cpuUsagePercent: 0,
        memoryTotalBytes: 16 * 1024 ** 3,
        memoryUsedBytes: 0,
        gpuCount: 0,
        storageTotalBytes: 500 * 1024 ** 3,
        storageUsedBytes: 0,
        heartbeatAt: new Date(2026, 9, 3, 2, 0, 0).toISOString(),
      },
      {
        id: 'nod_011',
        hostname: 'node-upper.sv.lan',
        status: 'ONLINE' as any,
        os: 'linux',
        cpuCores: 8,
        cpuUsagePercent: 0,
        memoryTotalBytes: 16 * 1024 ** 3,
        memoryUsedBytes: 0,
        gpuCount: 0,
        storageTotalBytes: 500 * 1024 ** 3,
        storageUsedBytes: 0,
        heartbeatAt: new Date(2026, 9, 3, 2, 0, 0).toISOString(),
      },
      {
        id: 'nod_012',
        hostname: 'node-proto.sv.lan',
        status: 'toString' as any,
        os: 'linux',
        cpuCores: 8,
        cpuUsagePercent: 0,
        memoryTotalBytes: 16 * 1024 ** 3,
        memoryUsedBytes: 0,
        gpuCount: 0,
        storageTotalBytes: 500 * 1024 ** 3,
        storageUsedBytes: 0,
        heartbeatAt: new Date(2026, 9, 3, 2, 0, 0).toISOString(),
      },
    ];

    const mockRuns: RunItem[] = [
      {
        id: 'run_101',
        state: 'running',
        objective: 'Batch model inference',
        datasetRef: 'ds_test',
        modelRef: 'mod_llama',
        createdAt: new Date(2026, 9, 3, 2, 0, 0).toISOString(),
      },
    ];

    try {
      // 1. Normal render with warning banner (nodesState="error", nodes present)
      await act(async () => {
        root.render(
          <ClusterOverview
            nodes={mockNodes}
            runs={mockRuns}
            pendingApprovalsCount={3}
            onNavigate={vi.fn()}
            nodesState="error"
            nodeError="Connection reset by peer"
            lastFetchedAt={new Date(2026, 9, 3, 2, 30, 0)}
            onRefresh={vi.fn()}
          />
        );
      });

      // 1a. Warning Banner in normal branch
      const warningBanner = container.querySelector('[data-testid="cluster-stale-warning"]') as HTMLElement;
      expect(warningBanner, 'Cluster stale warning banner must be present').not.toBeNull();
      expect(warningBanner.style.backgroundColor).toBe('var(--color-bg-subtle)');
      expect(warningBanner.style.borderColor).toBe('var(--color-status-offline)');
      expect(warningBanner.style.color).toBe('var(--color-status-offline)');
      expect(warningBanner.textContent).toContain('⚠️');
      expect(warningBanner.textContent).toContain('[동기화 실패]');

      // 1b. Freshness indicator
      const freshness = container.querySelector('[data-testid="cluster-freshness-indicator"]') as HTMLElement;
      expect(freshness).not.toBeNull();
      expect(freshness.style.backgroundColor).toBe('var(--color-bg-subtle)');
      expect(freshness.style.borderColor).toBe('var(--color-border-subtle)');
      expect(freshness.style.color).toBe('var(--color-text-muted)');

      // 1c. Refresh button focus ring preservation
      const refreshBtn = container.querySelector('[data-testid="cluster-refresh-btn"]') as HTMLButtonElement;
      expect(refreshBtn).not.toBeNull();
      expect(refreshBtn.style.borderColor).toBe('var(--color-border-subtle)');
      expect(refreshBtn.style.color).toBe('var(--color-text-secondary)');
      refreshBtn.focus();
      const compRefresh = window.getComputedStyle(refreshBtn);
      expect(compRefresh.outlineStyle !== 'none' || compRefresh.outline !== 'none', 'Refresh button focus ring must be preserved').toBe(true);

      // 1d. Resource gauge bar tokens
      const gaugeTracks = container.querySelectorAll('div[style*="height: 6px"]');
      const ramBar = gaugeTracks[1]?.firstElementChild as HTMLElement;
      expect(ramBar).not.toBeNull();
      expect(ramBar.style.backgroundColor).toBe('var(--color-status-online)');

      const gpuBar = gaugeTracks[2]?.firstElementChild as HTMLElement;
      expect(gpuBar).not.toBeNull();
      expect(gpuBar.style.backgroundColor).toBe('var(--color-brand-hover)');

      const storageBar = gaugeTracks[3]?.firstElementChild as HTMLElement;
      expect(storageBar).not.toBeNull();
      expect(storageBar.style.backgroundColor).toBe('var(--color-status-degraded)');

      // 1e. Heartbeat color token
      const hb001 = container.querySelector('[data-testid="node-heartbeat-nod_001"]') as HTMLElement;
      expect(hb001).not.toBeNull();
      expect(hb001.style.color).toBe('var(--color-text-muted)');

      // 1f. Status badges in DOM for all wire contract statuses
      const badgeOnline = container.querySelector('[data-testid="node-status-badge-nod_001"]') as HTMLElement;
      expect(badgeOnline.textContent).toBe('● ONLINE');
      expect(badgeOnline.style.color).toBe('var(--color-status-online)');
      expect(badgeOnline.style.opacity, 'Node status badge opacity must not be degraded').toBe('');

      const badgeActive = container.querySelector('[data-testid="node-status-badge-nod_002"]') as HTMLElement;
      expect(badgeActive.textContent).toBe('● ACTIVE (활성 · 헬스 미결정)');
      expect(badgeActive.style.color).toBe('var(--color-status-active)');

      const badgeDegraded = container.querySelector('[data-testid="node-status-badge-nod_003"]') as HTMLElement;
      expect(badgeDegraded.textContent).toBe('● DEGRADED');
      expect(badgeDegraded.style.color).toBe('var(--color-status-degraded)');

      const badgeLost = container.querySelector('[data-testid="node-status-badge-nod_004"]') as HTMLElement;
      expect(badgeLost.textContent).toBe('● LOST (단절)');
      expect(badgeLost.style.color).toBe('var(--color-status-lost)');

      const badgeUnknown = container.querySelector('[data-testid="node-status-badge-nod_005"]') as HTMLElement;
      expect(badgeUnknown.textContent).toBe('● UNKNOWN (미확인)');
      expect(badgeUnknown.style.color).toBe('var(--color-status-unknown)');

      const badgeOffline = container.querySelector('[data-testid="node-status-badge-nod_006"]') as HTMLElement;
      expect(badgeOffline.textContent).toBe('● OFFLINE');
      expect(badgeOffline.style.color).toBe('var(--color-status-offline)');

      const badgeDraining = container.querySelector('[data-testid="node-status-badge-nod_007"]') as HTMLElement;
      expect(badgeDraining.textContent).toBe('● DRAINING');
      expect(badgeDraining.style.color).toBe('var(--color-status-offline)');

      const badgeEnrolling = container.querySelector('[data-testid="node-status-badge-nod_008"]') as HTMLElement;
      expect(badgeEnrolling.textContent).toBe('● ENROLLING');
      expect(badgeEnrolling.style.color).toBe('var(--color-status-offline)');

      const badgeRetired = container.querySelector('[data-testid="node-status-badge-nod_009"]') as HTMLElement;
      expect(badgeRetired.textContent).toBe('● RETIRED');
      expect(badgeRetired.style.color).toBe('var(--color-status-offline)');

      // Out-of-contract, casing, prototype defense in DOM
      const badgeAdmitted = container.querySelector('[data-testid="node-status-badge-nod_010"]') as HTMLElement;
      expect(badgeAdmitted.textContent).toBe('● UNKNOWN (admitted)');
      expect(badgeAdmitted.style.color).toBe('var(--color-status-unknown)');

      const badgeUpper = container.querySelector('[data-testid="node-status-badge-nod_011"]') as HTMLElement;
      expect(badgeUpper.textContent).toBe('● UNKNOWN (ONLINE)');
      expect(badgeUpper.style.color).toBe('var(--color-status-unknown)');

      const badgeProto = container.querySelector('[data-testid="node-status-badge-nod_012"]') as HTMLElement;
      expect(badgeProto.textContent).toBe('● UNKNOWN (toString)');
      expect(badgeProto.style.color).toBe('var(--color-status-unknown)');

      // 2. Fetch error view (nodesState="error" and nodes.length === 0)
      await act(async () => {
        root.render(
          <ClusterOverview
            nodes={[]}
            runs={[]}
            pendingApprovalsCount={0}
            onNavigate={vi.fn()}
            nodesState="error"
            nodeError="Failed to reach control plane"
            onRefresh={vi.fn()}
          />
        );
      });

      const fetchErrorSection = container.querySelector('[data-testid="cluster-overview-fetch-error"]') as HTMLElement;
      expect(fetchErrorSection).not.toBeNull();
      expect(fetchErrorSection.style.backgroundColor).toBe('var(--color-bg-surface)');
      expect(fetchErrorSection.style.borderColor).toBe('var(--color-status-offline)');
      expect(fetchErrorSection.textContent).toContain('⚠️');
      expect(fetchErrorSection.textContent).toContain('클러스터 노드 동기화 실패');

      const heading = fetchErrorSection.querySelector('h1') as HTMLElement;
      expect(heading).not.toBeNull();
      expect(heading.style.color).toBe('var(--color-status-offline)');

      const errorRetryBtn = container.querySelector('[data-testid="cluster-error-retry-btn"]') as HTMLButtonElement;
      expect(errorRetryBtn).not.toBeNull();
      expect(errorRetryBtn.style.backgroundColor).toBe('var(--color-bg-subtle)');
      expect(errorRetryBtn.style.color).toBe('var(--color-text-primary)');
      expect(errorRetryBtn.style.borderColor).toBe('var(--color-border-subtle)');
      expect(errorRetryBtn.textContent).toContain('다시 시도');
      errorRetryBtn.focus();
      const compErrRetry = window.getComputedStyle(errorRetryBtn);
      expect(compErrRetry.outlineStyle !== 'none' || compErrRetry.outline !== 'none', 'Error retry button focus ring must be preserved').toBe(true);

      // 3. Telemetry unavailable branch
      const telemetryNode: NodeItem = {
        id: 'nod_telemetry',
        hostname: 'node-telemetry.sv.lan',
        status: 'online',
        os: 'linux',
        cpuCores: 8,
        cpuUsagePercent: 0,
        memoryTotalBytes: 16 * 1024 ** 3,
        memoryUsedBytes: 0,
        gpuCount: 0,
        storageTotalBytes: 500 * 1024 ** 3,
        storageUsedBytes: 0,
        heartbeatAt: new Date(2026, 9, 3, 2, 0, 0).toISOString(),
        telemetryUnavailable: true,
      };

      await act(async () => {
        root.render(
          <ClusterOverview
            nodes={[telemetryNode]}
            runs={[]}
            pendingApprovalsCount={0}
            onNavigate={vi.fn()}
            nodesState="error"
            nodeError="Telemetry agent disconnected"
            lastFetchedAt={new Date(2026, 9, 3, 2, 35, 0)}
            onRefresh={vi.fn()}
          />
        );
      });

      const telemWarning = container.querySelector('[data-testid="cluster-stale-warning"]') as HTMLElement;
      expect(telemWarning).not.toBeNull();
      expect(telemWarning.style.backgroundColor).toBe('var(--color-bg-subtle)');
      expect(telemWarning.style.borderColor).toBe('var(--color-status-offline)');
      expect(telemWarning.style.color).toBe('var(--color-status-offline)');

      const telemHb = container.querySelector('[data-testid="node-heartbeat-nod_telemetry"]') as HTMLElement;
      expect(telemHb).not.toBeNull();
      expect(telemHb.style.color).toBe('var(--color-text-muted)');

      // 4. Contract exact key set check
      expect(Object.keys(NODE_STATUS_CONFIG).sort()).toEqual([
        'active',
        'degraded',
        'draining',
        'enrolling',
        'lost',
        'offline',
        'online',
        'retired',
        'unknown',
      ]);

      // 5. Unit helper fail-closed and prototype defense
      const normOnline = getClusterNodeStatusConfig('online');
      expect(normOnline.color).toBe('var(--color-status-online)');
      expect(normOnline.label).toBe('ONLINE');

      const normActive = getClusterNodeStatusConfig('active');
      expect(normActive.color).toBe('var(--color-status-active)');
      expect(normActive.label).toBe('ACTIVE (활성 · 헬스 미결정)');

      const normDegraded = getClusterNodeStatusConfig('degraded');
      expect(normDegraded.color).toBe('var(--color-status-degraded)');
      expect(normDegraded.label).toBe('DEGRADED');

      const normLost = getClusterNodeStatusConfig('lost');
      expect(normLost.color).toBe('var(--color-status-lost)');
      expect(normLost.label).toBe('LOST (단절)');

      const normUnknown = getClusterNodeStatusConfig('unknown');
      expect(normUnknown.color).toBe('var(--color-status-unknown)');
      expect(normUnknown.label).toBe('UNKNOWN (미확인)');

      const normOffline = getClusterNodeStatusConfig('offline');
      expect(normOffline.color).toBe('var(--color-status-offline)');
      expect(normOffline.label).toBe('OFFLINE');

      const normDraining = getClusterNodeStatusConfig('draining');
      expect(normDraining.color).toBe('var(--color-status-offline)');
      expect(normDraining.label).toBe('DRAINING');

      const normEnrolling = getClusterNodeStatusConfig('enrolling');
      expect(normEnrolling.color).toBe('var(--color-status-offline)');
      expect(normEnrolling.label).toBe('ENROLLING');

      const normRetired = getClusterNodeStatusConfig('retired');
      expect(normRetired.color).toBe('var(--color-status-offline)');
      expect(normRetired.label).toBe('RETIRED');

      const unknownOut = getClusterNodeStatusConfig('admitted');
      expect(unknownOut.color).toBe('var(--color-status-unknown)');
      expect(unknownOut.label).toBe('UNKNOWN (admitted)');

      const unknownUpper = getClusterNodeStatusConfig('ONLINE');
      expect(unknownUpper.color).toBe('var(--color-status-unknown)');
      expect(unknownUpper.label).toBe('UNKNOWN (ONLINE)');

      const nullCfg = getClusterNodeStatusConfig(null);
      expect(nullCfg.color).toBe('var(--color-status-unknown)');
      expect(nullCfg.label).toBe('UNKNOWN');

      const undefCfg = getClusterNodeStatusConfig(undefined);
      expect(undefCfg.color).toBe('var(--color-status-unknown)');
      expect(undefCfg.label).toBe('UNKNOWN');

      const emptyCfg = getClusterNodeStatusConfig('');
      expect(emptyCfg.color).toBe('var(--color-status-unknown)');
      expect(emptyCfg.label).toBe('UNKNOWN');

      const protoKeys = ['toString', 'constructor', '__proto__', 'valueOf', 'hasOwnProperty', 'isPrototypeOf'];
      for (const pk of protoKeys) {
        const protoCfg = getClusterNodeStatusConfig(pk as any);
        expect(protoCfg.color, `Prototype key ${pk} must fall back to var(--color-status-unknown)`).toBe('var(--color-status-unknown)');
        expect(protoCfg.label).toBe(`UNKNOWN (${pk})`);
      }

      // 6. Contrast verification for getClusterNodeStatusConfig UNKNOWN fallback and NODE_STATUS_CONFIG entries on canvas
      const unkLightCr = getContrast(resolveTokenHex('--color-status-unknown', lightTokens), resolveTokenHex('--color-bg-canvas', lightTokens));
      expect(unkLightCr, 'ClusterOverview UNKNOWN status fallback on light canvas must pass 4.5:1').toBeCloseTo(6.78, 2);
      expect(unkLightCr).toBeGreaterThanOrEqual(4.5);
      const unkDarkCr = getContrast(resolveTokenHex('--color-status-unknown', darkTokens), resolveTokenHex('--color-bg-canvas', darkTokens));
      expect(unkDarkCr, 'ClusterOverview UNKNOWN status fallback on dark canvas must pass 4.5:1').toBeCloseTo(7.70, 2);
      expect(unkDarkCr).toBeGreaterThanOrEqual(4.5);

      for (const [stKey, cfg] of Object.entries(NODE_STATUS_CONFIG)) {
        const tokenMatch = cfg.color.match(/var\((--color-[a-z0-9-]+)\)/);
        expect(tokenMatch, `Status ${stKey} color must be a CSS variable`).not.toBeNull();
        const token = tokenMatch![1];
        const lCr = getContrast(resolveTokenHex(token, lightTokens), resolveTokenHex('--color-bg-canvas', lightTokens));
        expect(lCr, `NODE_STATUS_CONFIG.${stKey} contrast on light canvas must pass 4.5:1`).toBeGreaterThanOrEqual(4.5);
        const dCr = getContrast(resolveTokenHex(token, darkTokens), resolveTokenHex('--color-bg-canvas', darkTokens));
        expect(dCr, `NODE_STATUS_CONFIG.${stKey} contrast on dark canvas must pass 4.5:1`).toBeGreaterThanOrEqual(4.5);
      }
    } finally {
      act(() => {
        root.unmount();
      });
      container.remove();
    }
  });

  // 9r. [Card 270 / ACC-09] WorkspaceList Contrast & DOM Token Binding: 5 canonical states, fail-closed UNKNOWN (<raw>), error banner, and focus rings
  it('ACC-09 / Card 270: WorkspaceList status badges, error banner, and interactive buttons comply with WCAG 2.2 AA contrast and fail-closed contracts', () => {
    const container = document.createElement('div');
    document.body.appendChild(container);
    const root = createRoot(container);

    try {
      // 1. Config key set exact equality with wire enum
      const expectedKeys: WorkspaceStatusName[] = ['deleted', 'deleting', 'provisioning', 'ready', 'suspended'];
      expect(Object.keys(WORKSPACE_STATUS_CONFIG).sort(), 'WORKSPACE_STATUS_CONFIG keys must exactly match WorkspaceStatusName wire enum').toEqual(expectedKeys.sort());

      // 2. Render all 5 canonical statuses in DOM and verify styling & tokens
      const sampleNodes: NodeItem[] = [
        {
          id: 'nod_01JABCDEF01',
          hostname: 'pacs-worker-01',
          ip: '192.168.1.10',
          status: 'active',
          cpuCores: 16,
          memoryTotalBytes: 64 * 1024 ** 3,
          memoryUsedBytes: 16 * 1024 ** 3,
          gpuCount: 2,
          gpuModels: ['NVIDIA RTX 4090'],
          storagePools: [],
          telemetryUnavailable: false,
          schedulable: true,
          labels: {},
          annotations: {},
        },
      ];

      const sampleWorkspaces: WorkspaceItem[] = [
        {
          id: 'wsp-ready',
          projectId: 'prj-1',
          name: 'Ready Workspace',
          targetNodeId: 'nod_01JABCDEF01',
          isolationMode: 'process_sandbox',
          allowedPaths: [],
          prohibitedPaths: [],
          cpuLimitCores: 2,
          memoryLimitBytes: 1024,
          status: 'ready',
          createdAt: '2026-10-05T00:00:00Z',
        },
        {
          id: 'wsp-prov',
          projectId: 'prj-1',
          name: 'Provisioning Workspace',
          targetNodeId: 'nod_01JABCDEF01',
          isolationMode: 'process_sandbox',
          allowedPaths: [],
          prohibitedPaths: [],
          cpuLimitCores: 2,
          memoryLimitBytes: 1024,
          status: 'provisioning',
          createdAt: '2026-10-05T00:00:00Z',
        },
        {
          id: 'wsp-susp',
          projectId: 'prj-1',
          name: 'Suspended Workspace',
          targetNodeId: 'nod_01JABCDEF01',
          isolationMode: 'process_sandbox',
          allowedPaths: [],
          prohibitedPaths: [],
          cpuLimitCores: 2,
          memoryLimitBytes: 1024,
          status: 'suspended',
          createdAt: '2026-10-05T00:00:00Z',
        },
        {
          id: 'wsp-del',
          projectId: 'prj-1',
          name: 'Deleting Workspace',
          targetNodeId: 'nod_01JABCDEF01',
          isolationMode: 'process_sandbox',
          allowedPaths: [],
          prohibitedPaths: [],
          cpuLimitCores: 2,
          memoryLimitBytes: 1024,
          status: 'deleting',
          createdAt: '2026-10-05T00:00:00Z',
        },
        {
          id: 'wsp-deleted',
          projectId: 'prj-1',
          name: 'Deleted Workspace',
          targetNodeId: null,
          isolationMode: 'process_sandbox',
          allowedPaths: [],
          prohibitedPaths: [],
          cpuLimitCores: 2,
          memoryLimitBytes: 1024,
          status: 'deleted',
          createdAt: '2026-10-05T00:00:00Z',
        },
      ];

      act(() => {
        root.render(
          <WorkspaceList
            workspaces={sampleWorkspaces}
            nodes={sampleNodes}
            errorMessage="클러스터 동기화 오류가 발생했습니다"
            onCreateWorkspace={vi.fn()}
            onSelectWorkspace={vi.fn()}
            onOpenStudio={vi.fn()}
          />
        );
      });

      // Verify status badges
      for (const wsp of sampleWorkspaces) {
        const badge = container.querySelector(`[data-testid="wsp-status-${wsp.id}"]`) as HTMLElement;
        expect(badge, `Status badge for ${wsp.id} must be rendered`).not.toBeNull();
        const cfg = WORKSPACE_STATUS_CONFIG[wsp.status];
        expect(badge.textContent).toBe(cfg.label);
        expect(badge.style.backgroundColor).toContain(cfg.bg.replace(/var\(|\)/g, ''));
        expect(badge.style.color).toContain(cfg.color.replace(/var\(|\)/g, ''));
        expect(badge.style.borderColor || badge.style.border).toContain(cfg.border.replace(/var\(|\)/g, ''));
      }

      // 3. Error banner DOM assertions
      const errorBanner = container.querySelector('[data-testid="workspace-error-banner"]') as HTMLElement;
      expect(errorBanner, 'Workspace error banner must be rendered when errorMessage is passed').not.toBeNull();
      expect(errorBanner.getAttribute('role')).toBe('alert');
      expect(errorBanner.textContent).toContain('⚠️');
      expect(errorBanner.textContent).toContain('작업공간 오류');
      expect(errorBanner.textContent).toContain('클러스터 동기화 오류가 발생했습니다');
      expect(errorBanner.style.backgroundColor).toContain('var(--color-bg-subtle)');
      expect(errorBanner.style.borderColor || errorBanner.style.border).toContain('var(--color-status-offline)');
      expect(errorBanner.style.color).toContain('var(--color-status-offline)');

      // 4. Focus ring preservation
      const createBtn = container.querySelector('button');
      expect(createBtn).not.toBeNull();
      expect(createBtn?.style.outline).not.toBe('none');
      expect(createBtn?.style.outline).not.toBe('0');

      const studioBtns = container.querySelectorAll('button');
      const studioBtn = Array.from(studioBtns).find((b) => b.textContent?.includes('Studio에서 열기'));
      expect(studioBtn).toBeDefined();
      expect(studioBtn?.style.outline).not.toBe('none');
      expect(studioBtn?.style.outline).not.toBe('0');

      const cards = container.querySelectorAll('div[role="button"]');
      expect(cards.length).toBeGreaterThan(0);
      for (const card of Array.from(cards)) {
        const cardEl = card as HTMLElement;
        expect(cardEl.style.outline).not.toBe('none');
        expect(cardEl.style.outline).not.toBe('0');
      }

      // 5. Fail-closed UNKNOWN (<raw>) contract handling
      const unk1 = getWorkspaceStatusConfig('migrating_cluster');
      expect(unk1.color).toBe('var(--color-status-unknown)');
      expect(unk1.bg).toBe('var(--color-bg-subtle)');
      expect(unk1.border).toBe('var(--color-status-unknown)');
      expect(unk1.label).toBe('UNKNOWN (migrating_cluster)');

      const unkCase = getWorkspaceStatusConfig('READY');
      expect(unkCase.color).toBe('var(--color-status-unknown)');
      expect(unkCase.label).toBe('UNKNOWN (READY)');

      const unkAdmitted = getWorkspaceStatusConfig('admitted');
      expect(unkAdmitted.color).toBe('var(--color-status-unknown)');
      expect(unkAdmitted.label).toBe('UNKNOWN (admitted)');

      const nullCfg = getWorkspaceStatusConfig(null);
      expect(nullCfg.color).toBe('var(--color-status-unknown)');
      expect(nullCfg.label).toBe('UNKNOWN');

      const emptyCfg = getWorkspaceStatusConfig('');
      expect(emptyCfg.color).toBe('var(--color-status-unknown)');
      expect(emptyCfg.label).toBe('UNKNOWN');

      const protoKeys = ['toString', 'constructor', '__proto__', 'valueOf', 'hasOwnProperty', 'isPrototypeOf'];
      for (const pk of protoKeys) {
        const protoCfg = getWorkspaceStatusConfig(pk as any);
        expect(protoCfg.color, `Prototype key ${pk} must fall back to var(--color-status-unknown)`).toBe('var(--color-status-unknown)');
        expect(protoCfg.label).toBe(`UNKNOWN (${pk})`);
      }

      // 6. Explicit numerical contrast calculations
      const unkLightCr = getContrast(resolveTokenHex('--color-status-unknown', lightTokens), resolveTokenHex('--color-bg-subtle', lightTokens));
      expect(unkLightCr, 'WorkspaceList UNKNOWN fallback on light subtle must pass 4.5:1').toBeCloseTo(6.47, 2);
      expect(unkLightCr).toBeGreaterThanOrEqual(4.5);
      const unkDarkCr = getContrast(resolveTokenHex('--color-status-unknown', darkTokens), resolveTokenHex('--color-bg-subtle', darkTokens));
      expect(unkDarkCr, 'WorkspaceList UNKNOWN fallback on dark subtle must pass 4.5:1').toBeCloseTo(5.82, 2);
      expect(unkDarkCr).toBeGreaterThanOrEqual(4.5);

      for (const [stKey, cfg] of Object.entries(WORKSPACE_STATUS_CONFIG)) {
        const tokenMatch = cfg.color.match(/var\((--color-[a-z0-9-]+)\)/);
        expect(tokenMatch, `Status ${stKey} color must be a CSS variable`).not.toBeNull();
        const token = tokenMatch![1];
        const lCr = getContrast(resolveTokenHex(token, lightTokens), resolveTokenHex('--color-bg-subtle', lightTokens));
        expect(lCr, `WORKSPACE_STATUS_CONFIG.${stKey} color contrast on light subtle must pass 4.5:1`).toBeGreaterThanOrEqual(4.5);
        const dCr = getContrast(resolveTokenHex(token, darkTokens), resolveTokenHex('--color-bg-subtle', darkTokens));
        expect(dCr, `WORKSPACE_STATUS_CONFIG.${stKey} color contrast on dark subtle must pass 4.5:1`).toBeGreaterThanOrEqual(4.5);

        const borderTokenMatch = cfg.border.match(/var\((--color-[a-z0-9-]+)\)/);
        expect(borderTokenMatch, `Status ${stKey} border must be a CSS variable`).not.toBeNull();
        const borderToken = borderTokenMatch![1];
        const lBorderCr = getContrast(resolveTokenHex(borderToken, lightTokens), resolveTokenHex('--color-bg-subtle', lightTokens));
        expect(lBorderCr, `WORKSPACE_STATUS_CONFIG.${stKey} border contrast on light subtle must pass 3.0:1`).toBeGreaterThanOrEqual(3.0);
        const dBorderCr = getContrast(resolveTokenHex(borderToken, darkTokens), resolveTokenHex('--color-bg-subtle', darkTokens));
        expect(dBorderCr, `WORKSPACE_STATUS_CONFIG.${stKey} border contrast on dark subtle must pass 3.0:1`).toBeGreaterThanOrEqual(3.0);
      }
    } finally {
      act(() => {
        root.unmount();
      });
      container.remove();
    }
  });

// 9v. [Card 271 / ACC-09] Component DOM Rendering & Binding Verification: NodeList Status Badges, Notices, Code Bootstrap, and Interactive Buttons
  it('ACC-09 / Card 271: NodeList status badges, notices, code bootstrap, and interactive buttons comply with WCAG 2.2 AA contrast and fail-closed contracts', async () => {
    const container = document.createElement('div');
    container.setAttribute('data-theme', 'light');
    document.body.appendChild(container);
    const root = createRoot(container);

    try {
      // 1. Config contract parity & helper fail-closed guard
      const sampleStatuses: NodeStatus[] = ['active', 'degraded', 'draining', 'enrolling', 'lost', 'offline', 'online', 'retired', 'unknown'];
      for (const st of sampleStatuses) {
        const cfg = getClusterNodeStatusConfig(st);
        expect(cfg.color, `Status ${st} must resolve to a valid CSS variable`).toMatch(/^var\(--color-status-[a-z]+\)$/);
        expect(cfg.label, `Status ${st} must have non-empty label`).toBeTruthy();
      }

      // Fail-closed UNKNOWN fallback handling
      const unkCustom = getClusterNodeStatusConfig('custom_future_state');
      expect(unkCustom.color).toBe('var(--color-status-unknown)');
      expect(unkCustom.label).toBe('UNKNOWN (custom_future_state)');

      const nullCfg = getClusterNodeStatusConfig(null);
      expect(nullCfg.color).toBe('var(--color-status-unknown)');
      expect(nullCfg.label).toBe('UNKNOWN');

      const undefCfg = getClusterNodeStatusConfig(undefined);
      expect(undefCfg.color).toBe('var(--color-status-unknown)');
      expect(undefCfg.label).toBe('UNKNOWN');

      const emptyCfg = getClusterNodeStatusConfig('');
      expect(emptyCfg.color).toBe('var(--color-status-unknown)');
      expect(emptyCfg.label).toBe('UNKNOWN');

      const protoKeys = ['toString', 'constructor', '__proto__', 'valueOf', 'hasOwnProperty', 'isPrototypeOf'];
      for (const pk of protoKeys) {
        const protoCfg = getClusterNodeStatusConfig(pk as any);
        expect(protoCfg.color).toBe('var(--color-status-unknown)');
        expect(protoCfg.label).toBe(`UNKNOWN (${pk})`);
      }

      // 2. Render NodeList with nodes spanning canonical statuses & special states
      const testNodes: NodeItem[] = [
        {
          id: 'nod-online',
          hostname: 'node-online-worker',
          status: 'online',
          os: 'linux',
          cpuCores: 16,
          cpuUsagePercent: 20,
          memoryTotalBytes: 64 * 1024 ** 3,
          memoryUsedBytes: 16 * 1024 ** 3,
          storageTotalBytes: 1000 * 1024 ** 3,
          storageUsedBytes: 200 * 1024 ** 3,
          allocatableCores: 12,
          gpuCount: 1,
          gpuName: 'NVIDIA RTX 4090',
          gpuVramTotalBytes: 24 * 1024 ** 3,
          gpuVramUsedBytes: 8 * 1024 ** 3,
          heartbeatAt: '2026-10-05T00:00:00Z',
        },
        {
          id: 'nod-active',
          hostname: 'node-active-worker',
          status: 'active',
          os: 'linux',
          cpuCores: 8,
          cpuUsagePercent: 40,
          memoryTotalBytes: 32 * 1024 ** 3,
          memoryUsedBytes: 12 * 1024 ** 3,
          storageTotalBytes: 500 * 1024 ** 3,
          storageUsedBytes: 100 * 1024 ** 3,
          allocatableCores: 4,
          gpuCount: 0,
          heartbeatAt: '2026-10-05T00:00:00Z',
        },
        {
          id: 'nod-obs',
          hostname: 'node-obs-worker',
          status: 'unknown',
          observationOnly: true,
          os: 'linux',
          cpuCores: 4,
          cpuUsagePercent: 10,
          memoryTotalBytes: 16 * 1024 ** 3,
          memoryUsedBytes: 2 * 1024 ** 3,
          storageTotalBytes: 250 * 1024 ** 3,
          storageUsedBytes: 20 * 1024 ** 3,
          gpuCount: 0,
          heartbeatAt: '2026-10-05T00:00:00Z',
        },
        {
          id: 'nod-telem-lost',
          hostname: 'node-telem-lost-worker',
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
          heartbeatAt: '2026-10-05T00:00:00Z',
        },
      ];

      const onSelect = vi.fn();
      const onStudio = vi.fn();

      act(() => {
        root.render(<NodeList nodes={testNodes} isLoading={false} error={null} onSelectNode={onSelect} onOpenStudio={onStudio} />);
      });

      // 3. Status badges verification
      for (const node of testNodes) {
        const badge = container.querySelector(`[data-testid="node-status-badge-${node.id}"]`) as HTMLElement;
        expect(badge, `Status badge for ${node.id} must render`).not.toBeNull();
        const cfg = getClusterNodeStatusConfig(node.status);
        expect(badge.textContent).toContain(cfg.label);
        expect(badge.style.color).toBe(cfg.color);
        expect(badge.style.backgroundColor).toBe('var(--color-bg-subtle)');
        expect(badge.style.borderColor || badge.style.border).toContain(cfg.color.replace(/var\(|\)/g, ''));
      }

      // 4. Observation banner
      const obsBanner = container.querySelector('[data-testid="node-observation-banner-nod-obs"]') as HTMLElement;
      expect(obsBanner, 'Observation banner must render').not.toBeNull();
      expect(obsBanner.textContent).toContain('⚠️');
      expect(obsBanner.textContent).toContain('관측 전용');
      expect(obsBanner.style.color).toBe('var(--color-status-unknown)');
      expect(obsBanner.style.backgroundColor).toBe('var(--color-bg-subtle)');
      expect(obsBanner.style.borderColor || obsBanner.style.border).toContain('var(--color-status-unknown)');

      // 5. Active notice
      const activeNotice = container.querySelector('[data-testid="node-active-status-notice-nod-active"]') as HTMLElement;
      expect(activeNotice, 'Active notice must render').not.toBeNull();
      expect(activeNotice.getAttribute('role')).toBe('status');
      expect(activeNotice.textContent).toContain('ℹ️');
      expect(activeNotice.textContent).toContain('계약 상태: active');
      expect(activeNotice.style.color).toBe('var(--color-status-active)');
      expect(activeNotice.style.backgroundColor).toBe('var(--color-bg-subtle)');
      expect(activeNotice.style.borderColor || activeNotice.style.border).toContain('var(--color-status-active)');

      // 6. Interactive buttons & focus ring preservation
      const selectBtns = container.querySelectorAll('button[data-testid^="node-select-btn-"]');
      expect(selectBtns.length).toBeGreaterThan(0);
      for (const btn of Array.from(selectBtns)) {
        const b = btn as HTMLElement;
        expect(b.style.outline).not.toBe('none');
        expect(b.style.outline).not.toBe('0');
      }

      const studioBtns = container.querySelectorAll('button[data-testid^="node-studio-btn-"]');
      expect(studioBtns.length).toBeGreaterThan(0);
      for (const btn of Array.from(studioBtns)) {
        const b = btn as HTMLElement;
        expect(b.style.outline).not.toBe('none');
        expect(b.style.outline).not.toBe('0');
      }

      const obsStudioBtn = container.querySelector('[data-testid="node-studio-btn-nod-obs"]') as HTMLElement;
      expect(obsStudioBtn.style.backgroundColor).toBe('var(--color-border-strong)');
      expect(obsStudioBtn.style.color).toBe('var(--color-text-inverse)');

      const regularStudioBtn = container.querySelector('[data-testid="node-studio-btn-nod-online"]') as HTMLElement;
      expect(regularStudioBtn.style.backgroundColor).toBe('var(--color-brand-primary-bg)');
      expect(regularStudioBtn.style.color).toBe('var(--color-brand-primary-fg)');

      // Hardware specs (CPU bar & GPU box) and telemetry detail button bindings
      const onlineCard = container.querySelector('[data-testid="node-card-nod-online"]') as HTMLElement;
      expect(onlineCard, 'Online card must render').not.toBeNull();
      const cpuBarTrack = Array.from(onlineCard.querySelectorAll('div')).find((d) => d.style.height === '4px');
      const cpuBar = cpuBarTrack?.firstElementChild as HTMLElement;
      expect(cpuBar, 'CPU bar must exist').toBeDefined();
      expect(cpuBar.style.backgroundColor).toBe('var(--color-brand-primary)');

      const gpuBox = Array.from(onlineCard.querySelectorAll('div')).find((d) => d.textContent?.includes('🎮') && d.style.padding === '6px 8px') as HTMLElement;
      expect(gpuBox, 'GPU box must exist').toBeDefined();
      expect(gpuBox.style.backgroundColor).toBe('var(--color-bg-subtle)');

      const detailBtn = container.querySelector('[data-testid="node-detail-btn-nod-telem-lost"]') as HTMLElement;
      expect(detailBtn, 'Telemetry detail button must render').not.toBeNull();
      expect(detailBtn.style.backgroundColor).toBe('var(--color-bg-subtle)');
      expect(detailBtn.style.color).toBe('var(--color-text-primary)');

      // 7. Empty state install guide & copy button
      act(() => {
        root.render(<NodeList nodes={[]} isLoading={false} error={null} />);
      });

      const guideToggleBtn = Array.from(container.querySelectorAll('button')).find((b) => b.textContent?.includes('Node Agent 설치 안내'));
      expect(guideToggleBtn).toBeDefined();

      act(() => {
        guideToggleBtn?.click();
      });

      const copyBtn = container.querySelector('[data-testid="copy-agent-bootstrap-btn"]') as HTMLElement;
      expect(copyBtn, 'Copy bootstrap button must render').not.toBeNull();
      expect(copyBtn.style.backgroundColor).toBe('var(--color-bg-subtle)');
      expect(copyBtn.style.color).toBe('var(--color-text-primary)');
      expect(copyBtn.style.borderColor || copyBtn.style.border).toContain('var(--color-border-subtle)');
      expect(copyBtn.style.outline).not.toBe('none');
      expect(copyBtn.style.outline).not.toBe('0');

      // 8. Numerical contrast calculations on subtle
      const unkLightCr = getContrast(resolveTokenHex('--color-status-unknown', lightTokens), resolveTokenHex('--color-bg-subtle', lightTokens));
      expect(unkLightCr, 'NodeList UNKNOWN fallback on light subtle must pass 4.5:1').toBeCloseTo(6.47, 2);
      expect(unkLightCr).toBeGreaterThanOrEqual(4.5);
      const unkDarkCr = getContrast(resolveTokenHex('--color-status-unknown', darkTokens), resolveTokenHex('--color-bg-subtle', darkTokens));
      expect(unkDarkCr, 'NodeList UNKNOWN fallback on dark subtle must pass 4.5:1').toBeCloseTo(5.82, 2);
      expect(unkDarkCr).toBeGreaterThanOrEqual(4.5);

      for (const st of sampleStatuses) {
        const cfg = getClusterNodeStatusConfig(st);
        const tokenMatch = cfg.color.match(/var\((--color-[a-z0-9-]+)\)/);
        expect(tokenMatch).not.toBeNull();
        const tok = tokenMatch![1];
        const lCr = getContrast(resolveTokenHex(tok, lightTokens), resolveTokenHex('--color-bg-subtle', lightTokens));
        expect(lCr, `Status ${st} on light subtle must pass 4.5:1`).toBeGreaterThanOrEqual(4.5);
        const dCr = getContrast(resolveTokenHex(tok, darkTokens), resolveTokenHex('--color-bg-subtle', darkTokens));
        expect(dCr, `Status ${st} on dark subtle must pass 4.5:1`).toBeGreaterThanOrEqual(4.5);
      }
    } finally {
      act(() => {
        root.unmount();
      });
      container.remove();
    }
  });

  // 9w. [Card 273 / ACC-09] Shared & Minor UI Components Contrast & DOM Token Binding: Button, RiskBadge, ExecutionResultView, and WorkspaceCreateModal
  it('ACC-09 / Card 273: Button, RiskBadge, ExecutionResultView, and WorkspaceCreateModal comply with WCAG 2.2 AA contrast and fail-closed contracts', () => {
    const container = document.createElement('div');
    document.body.appendChild(container);
    const root = createRoot(container);

    try {
      // 1. RISK_CONFIG exact key set equality with canonical RiskLevel wire enum (F-R3)
      const schemaPath = path.resolve(__dirname, '../../../contracts/v1alpha1/core.schema.json');
      const canonicalCoreSchema = JSON.parse(fs.readFileSync(schemaPath, 'utf-8'));
      const expectedRiskKeys: RiskLevel[] = canonicalCoreSchema.$defs?.RiskLevel?.enum ?? [];
      expect(expectedRiskKeys.length, 'Canonical schema must define RiskLevel enum').toBe(4);
      expect(Object.keys(RISK_CONFIG).sort(), 'RISK_CONFIG keys must exactly match canonical RiskLevel wire enum').toEqual([...expectedRiskKeys].sort());

      // 2. RISK_CONFIG entries numerical contrast calculation (text >= 4.5:1, border >= 3.0:1)
      for (const [level, cfg] of Object.entries(RISK_CONFIG)) {
        expect(cfg.bgVar, `RiskBadge ${level} must use subtle background`).toBe('var(--color-bg-subtle)');
        const fgTok = cfg.colorVar.replace(/^var\(|\)$/g, '');
        const bgTok = cfg.bgVar.replace(/^var\(|\)$/g, '');
        const lightFg = resolveTokenHex(fgTok, lightTokens);
        const lightBg = resolveTokenHex(bgTok, lightTokens);
        const darkFg = resolveTokenHex(fgTok, darkTokens);
        const darkBg = resolveTokenHex(bgTok, darkTokens);

        const lightTextCr = getContrast(lightFg, lightBg);
        expect(lightTextCr, `RiskBadge ${level} text on light subtle must achieve >= 4.5:1`).toBeGreaterThanOrEqual(4.5);
        const darkTextCr = getContrast(darkFg, darkBg);
        expect(darkTextCr, `RiskBadge ${level} text on dark subtle must achieve >= 4.5:1`).toBeGreaterThanOrEqual(4.5);

        const lightBorderCr = getContrast(lightFg, lightBg);
        expect(lightBorderCr, `RiskBadge ${level} border on light subtle must achieve >= 3.0:1`).toBeGreaterThanOrEqual(3.0);
        const darkBorderCr = getContrast(darkFg, darkBg);
        expect(darkBorderCr, `RiskBadge ${level} border on dark subtle must achieve >= 3.0:1`).toBeGreaterThanOrEqual(3.0);
      }

      // 3. Fail-closed UNKNOWN fallback verification with Object.hasOwn
      const fallbackPrototypeKeys = ['toString', 'constructor', '__proto__', 'valueOf', 'toLocaleString', 'hasOwnProperty'];
      for (const key of fallbackPrototypeKeys) {
        const fallbackConfig = getRiskLevelConfig(key);
        expect(fallbackConfig.label, `Prototype key ${key} must resolve to fail-closed UNKNOWN fallback`).toBe(`UNKNOWN (${key})`);
        expect(fallbackConfig.colorVar).toBe('var(--color-status-unknown)');
        expect(fallbackConfig.bgVar).toBe('var(--color-bg-subtle)');
      }

      const invalidRiskKeys = ['l0', 'L4', 'HIGH', 'CRITICAL', ''];
      for (const key of invalidRiskKeys) {
        const fallbackConfig = getRiskLevelConfig(key);
        const expectedLabel = key ? `UNKNOWN (${key})` : 'UNKNOWN';
        expect(fallbackConfig.label, `Invalid key '${key}' must resolve to fail-closed UNKNOWN fallback`).toBe(expectedLabel);
        expect(fallbackConfig.colorVar).toBe('var(--color-status-unknown)');
        expect(fallbackConfig.bgVar).toBe('var(--color-bg-subtle)');
      }

      const nullUndefinedConfig = getRiskLevelConfig(null);
      expect(nullUndefinedConfig.label).toBe('UNKNOWN');
      expect(nullUndefinedConfig.colorVar).toBe('var(--color-status-unknown)');
      expect(nullUndefinedConfig.bgVar).toBe('var(--color-bg-subtle)');

      // Fallback numerical contrast calculation
      const lightUnknownFg = resolveTokenHex('--color-status-unknown', lightTokens);
      const lightUnknownBg = resolveTokenHex('--color-bg-subtle', lightTokens);
      const darkUnknownFg = resolveTokenHex('--color-status-unknown', darkTokens);
      const darkUnknownBg = resolveTokenHex('--color-bg-subtle', darkTokens);
      expect(getContrast(lightUnknownFg, lightUnknownBg), 'UNKNOWN fallback text on light subtle must achieve >= 4.5:1').toBeGreaterThanOrEqual(4.5);
      expect(getContrast(darkUnknownFg, darkUnknownBg), 'UNKNOWN fallback text on dark subtle must achieve >= 4.5:1').toBeGreaterThanOrEqual(4.5);

      // 4. DOM Rendering of RiskBadge for all canonical levels and UNKNOWN
      for (const level of expectedRiskKeys) {
        act(() => {
          root.render(<RiskBadge level={level} />);
        });
        const badge = container.querySelector('[role="status"]');
        expect(badge, `RiskBadge ${level} must render with role="status"`).not.toBeNull();
        expect(badge?.getAttribute('aria-label')).toContain(`위험 등급 ${RISK_CONFIG[level].label}`);
        expect((badge as HTMLElement)?.style.color).toBe(RISK_CONFIG[level].colorVar);
        expect((badge as HTMLElement)?.style.backgroundColor).toBe(RISK_CONFIG[level].bgVar);
        expect(badge?.getAttribute('style')).toContain(`border-color: ${RISK_CONFIG[level].colorVar}`);
      }

      // Render UNKNOWN RiskBadge
      act(() => {
        root.render(<RiskBadge level={'ATTACK' as any} />);
      });
      const unknownBadge = container.querySelector('[role="status"]');
      expect(unknownBadge?.textContent).toContain('UNKNOWN (ATTACK)');
      expect((unknownBadge as HTMLElement)?.style.color).toBe('var(--color-status-unknown)');
      expect((unknownBadge as HTMLElement)?.style.backgroundColor).toBe('var(--color-bg-subtle)');

      // 5. Button variant token contrast and DOM rendering
      // Primary button
      const lightBtnPrimaryFg = resolveTokenHex('--color-brand-primary-fg', lightTokens);
      const lightBtnPrimaryBg = resolveTokenHex('--color-brand-primary-bg', lightTokens);
      const darkBtnPrimaryFg = resolveTokenHex('--color-brand-primary-fg', darkTokens);
      const darkBtnPrimaryBg = resolveTokenHex('--color-brand-primary-bg', darkTokens);
      expect(getContrast(lightBtnPrimaryFg, lightBtnPrimaryBg), 'Button primary text on primary bg light must pass 4.5:1').toBeGreaterThanOrEqual(4.5);
      expect(getContrast(darkBtnPrimaryFg, darkBtnPrimaryBg), 'Button primary text on primary bg dark must pass 4.5:1').toBeGreaterThanOrEqual(4.5);

      // Danger button
      const lightBtnDangerBg = resolveTokenHex('--color-status-offline-bg', lightTokens);
      const darkBtnDangerBg = resolveTokenHex('--color-status-offline-bg', darkTokens);
      expect(getContrast(lightBtnPrimaryFg, lightBtnDangerBg), 'Button danger text on offline bg light must pass 4.5:1').toBeGreaterThanOrEqual(4.5);
      expect(getContrast(darkBtnPrimaryFg, darkBtnDangerBg), 'Button danger text on offline bg dark must pass 4.5:1').toBeGreaterThanOrEqual(4.5);

      // Secondary button
      const lightBtnSecFg = resolveTokenHex('--color-text-primary', lightTokens);
      const lightBtnSecBg = resolveTokenHex('--color-bg-subtle', lightTokens);
      const darkBtnSecFg = resolveTokenHex('--color-text-primary', darkTokens);
      const darkBtnSecBg = resolveTokenHex('--color-bg-subtle', darkTokens);
      expect(getContrast(lightBtnSecFg, lightBtnSecBg), 'Button secondary text on subtle light must pass 4.5:1').toBeGreaterThanOrEqual(4.5);
      expect(getContrast(darkBtnSecFg, darkBtnSecBg), 'Button secondary text on subtle dark must pass 4.5:1').toBeGreaterThanOrEqual(4.5);

      // Secondary border
      const lightBtnSecBorder = resolveTokenHex('--color-border-strong', lightTokens);
      const darkBtnSecBorder = resolveTokenHex('--color-border-strong', darkTokens);
      expect(getContrast(lightBtnSecBorder, lightBtnSecBg), 'Button secondary border on subtle light must pass 3.0:1').toBeGreaterThanOrEqual(3.0);
      expect(getContrast(darkBtnSecBorder, darkBtnSecBg), 'Button secondary border on subtle dark must pass 3.0:1').toBeGreaterThanOrEqual(3.0);

      // DOM render Button
      act(() => {
        root.render(
          <div>
            <Button variant="primary">실행</Button>
            <Button variant="secondary">취소</Button>
            <Button variant="danger">삭제</Button>
            <Button variant="ghost">더보기</Button>
          </div>
        );
      });
      const buttons = container.querySelectorAll('button');
      expect(buttons).toHaveLength(4);
      for (const btn of buttons) {
        expect(btn.style.outline, 'Button outline must not be none').not.toBe('none');
        expect(btn.style.outline, 'Button outline must not be 0').not.toBe('0');
      }
      expect(buttons[0].style.color).toBe('var(--color-brand-primary-fg)');
      expect(buttons[0].style.backgroundColor).toBe('var(--color-brand-primary-bg, var(--color-brand-primary))');
      expect(buttons[1].style.color).toBe('var(--color-text-primary)');
      expect(buttons[1].style.backgroundColor).toBe('var(--color-bg-subtle)');
      expect(buttons[1].getAttribute('style')).toContain('var(--color-border-strong');
      expect(buttons[2].style.color).toBe('var(--color-brand-primary-fg)');
      expect(buttons[2].style.backgroundColor).toBe('var(--color-status-offline-bg, var(--color-status-offline))');

      // 6. ExecutionResultView DOM rendering & token verification
      const sampleExecutionResult = {
        runId: 'run-c273-01',
        workspaceId: 'wsp-c273-01',
        command: 'python test.py',
        exitCode: 0,
        executedAt: '2026-10-05T00:00:00Z',
        completedAt: '2026-10-05T00:00:01Z',
        resourceReclaimed: true,
        evidenceId: 'evi-c273-001',
        allowedEvents: [{ action: 'READ', path: '/app', timestamp: '2026-10-05T00:00:00Z' }],
        deniedEvents: [],
      };

      act(() => {
        root.render(<ExecutionResultView result={sampleExecutionResult} onBack={() => {}} />);
      });
      expect(container.textContent).toContain('격리 실행 결과 (AC-03 증거 뷰)');
      expect(container.textContent).toContain('정상 종료 (SUCCESS)');

      // Verify success status pill background and text color
      const successPill = Array.from(container.querySelectorAll('span')).find(el => el.textContent === '정상 종료 (SUCCESS)');
      expect(successPill, 'Success pill element must exist').toBeDefined();
      expect(successPill?.style.backgroundColor).toBe('var(--color-bg-subtle)');
      expect(successPill?.style.color).toBe('var(--color-brand-success)');

      // Verify exit code card background
      const exitCodeSpan = Array.from(container.querySelectorAll('span')).find(
        el => el.textContent?.includes('종료 코드 (EXIT CODE)')
      );
      const exitCodeCard = exitCodeSpan?.parentElement as HTMLElement;
      expect(exitCodeCard?.style.backgroundColor).toBe('var(--color-bg-surface)');

      // Verify allowed event row background
      const eventCode = Array.from(container.querySelectorAll('code')).find(
        el => el.textContent === '/app'
      );
      const eventRow = eventCode?.parentElement?.parentElement as HTMLElement;
      expect(eventRow?.style.backgroundColor).toBe('var(--color-bg-subtle)');

      // 7. WorkspaceCreateModal DOM rendering & backdrop token verification
      act(() => {
        root.render(<WorkspaceCreateModal isOpen={true} onClose={() => {}} onCreate={async () => {}} projectId="prj-c273" />);
      });
      const modalBackdrop = container.querySelector('[role="dialog"]');
      expect(modalBackdrop, 'Modal dialog container must exist').not.toBeNull();
      expect((modalBackdrop as HTMLElement)?.style.backgroundColor).toBe('var(--color-bg-backdrop)');
      const dialogSurface = modalBackdrop?.firstElementChild as HTMLElement;
      expect(dialogSurface?.style.backgroundColor).toBe('var(--color-bg-surface)');

      // 8. Explicit numerical contrast calculations for the 6 Card 273 design tokens
      const lBrandSuccess = resolveTokenHex('--color-brand-success', lightTokens);
      const dBrandSuccess = resolveTokenHex('--color-brand-success', darkTokens);
      const lSurface = resolveTokenHex('--color-bg-surface', lightTokens);
      const dSurface = resolveTokenHex('--color-bg-surface', darkTokens);
      const lSubtle = resolveTokenHex('--color-bg-subtle', lightTokens);
      const dSubtle = resolveTokenHex('--color-bg-subtle', darkTokens);
      const lCanvas = resolveTokenHex('--color-bg-canvas', lightTokens);
      const dCanvas = resolveTokenHex('--color-bg-canvas', darkTokens);

      expect(getContrast(lBrandSuccess, lSurface), 'brand-success on light surface >= 4.5:1').toBeGreaterThanOrEqual(4.5);
      expect(getContrast(dBrandSuccess, dSurface), 'brand-success on dark surface >= 4.5:1').toBeGreaterThanOrEqual(4.5);
      expect(getContrast(lBrandSuccess, lSubtle), 'brand-success on light subtle >= 4.5:1').toBeGreaterThanOrEqual(4.5);
      expect(getContrast(dBrandSuccess, dSubtle), 'brand-success on dark subtle >= 4.5:1').toBeGreaterThanOrEqual(4.5);

      const lBrandDanger = resolveTokenHex('--color-brand-danger', lightTokens);
      const dBrandDanger = resolveTokenHex('--color-brand-danger', darkTokens);
      expect(getContrast(lBrandDanger, lSurface), 'brand-danger on light surface >= 4.5:1').toBeGreaterThanOrEqual(4.5);
      expect(getContrast(dBrandDanger, dSurface), 'brand-danger on dark surface >= 4.5:1').toBeGreaterThanOrEqual(4.5);
      expect(getContrast(lBrandDanger, lSubtle), 'brand-danger on light subtle >= 4.5:1').toBeGreaterThanOrEqual(4.5);
      expect(getContrast(dBrandDanger, dSubtle), 'brand-danger on dark subtle >= 4.5:1').toBeGreaterThanOrEqual(4.5);

      const lBrandWarning = resolveTokenHex('--color-brand-warning', lightTokens);
      const dBrandWarning = resolveTokenHex('--color-brand-warning', darkTokens);
      expect(getContrast(lBrandWarning, lSurface), 'brand-warning on light surface >= 4.5:1').toBeGreaterThanOrEqual(4.5);
      expect(getContrast(dBrandWarning, dSurface), 'brand-warning on dark surface >= 4.5:1').toBeGreaterThanOrEqual(4.5);
      expect(getContrast(lBrandWarning, lSubtle), 'brand-warning on light subtle >= 4.5:1').toBeGreaterThanOrEqual(4.5);
      expect(getContrast(dBrandWarning, dSubtle), 'brand-warning on dark subtle >= 4.5:1').toBeGreaterThanOrEqual(4.5);

      const lRiskL3Border = resolveTokenHex('--color-risk-l3-border', lightTokens);
      const dRiskL3Border = resolveTokenHex('--color-risk-l3-border', darkTokens);
      const lRiskL3Bg = resolveTokenHex('--color-risk-l3-bg', lightTokens);
      const dRiskL3Bg = resolveTokenHex('--color-risk-l3-bg', darkTokens);
      expect(getContrast(lRiskL3Border, lSurface), 'risk-l3-border on light surface >= 3.0:1').toBeGreaterThanOrEqual(3.0);
      expect(getContrast(dRiskL3Border, dSurface), 'risk-l3-border on dark surface >= 3.0:1').toBeGreaterThanOrEqual(3.0);
      expect(getContrast(lRiskL3Border, lCanvas), 'risk-l3-border on light canvas >= 3.0:1').toBeGreaterThanOrEqual(3.0);
      expect(getContrast(dRiskL3Border, dCanvas), 'risk-l3-border on dark canvas >= 3.0:1').toBeGreaterThanOrEqual(3.0);
      expect(getContrast(lRiskL3Border, lRiskL3Bg), 'risk-l3-border on light risk-l3-bg >= 3.0:1').toBeGreaterThanOrEqual(3.0);
      expect(getContrast(dRiskL3Border, dRiskL3Bg), 'risk-l3-border on dark risk-l3-bg >= 3.0:1').toBeGreaterThanOrEqual(3.0);

      const lRiskL3Text = resolveTokenHex('--color-risk-l3-text', lightTokens);
      const dRiskL3Text = resolveTokenHex('--color-risk-l3-text', darkTokens);
      expect(getContrast(lRiskL3Text, lRiskL3Bg), 'risk-l3-text on light risk-l3-bg >= 4.5:1').toBeGreaterThanOrEqual(4.5);
      expect(getContrast(dRiskL3Text, dRiskL3Bg), 'risk-l3-text on dark risk-l3-bg >= 4.5:1').toBeGreaterThanOrEqual(4.5);
      expect(getContrast(lRiskL3Text, lSurface), 'risk-l3-text on light surface >= 4.5:1').toBeGreaterThanOrEqual(4.5);
      expect(getContrast(dRiskL3Text, dSurface), 'risk-l3-text on dark surface >= 4.5:1').toBeGreaterThanOrEqual(4.5);

      // 9. Fail-closed undefined token containment check (Card 273 target files var(--x) ⊆ index.css declared tokens)
      const card273Files = [
        'shared/ui/Button.tsx',
        'shared/ui/RiskBadge.tsx',
        'features/workspaces/ExecutionResultView.tsx',
        'features/workspaces/WorkspaceCreateModal.tsx',
      ];
      const cssPath = path.resolve(__dirname, '../src/index.css');
      const cssContent = fs.readFileSync(cssPath, 'utf-8');
      const declaredCssTokens = new Set<string>();
      const tokenDeclRegex = /(--[a-z0-9-]+)\s*:\s*([^;]+);/g;
      let declMatch;
      while ((declMatch = tokenDeclRegex.exec(cssContent)) !== null) {
        declaredCssTokens.add(declMatch[1].trim());
      }
      for (const rel of card273Files) {
        const fPath = path.resolve(__dirname, '../src', rel);
        const fContent = fs.readFileSync(fPath, 'utf-8');
        const varMatches = fContent.match(/var\((--[a-z0-9-]+)/g) || [];
        for (const v of varMatches) {
          const tokenName = v.replace('var(', '');
          expect(declaredCssTokens.has(tokenName), `Token ${tokenName} used in ${rel} must be declared in index.css`).toBe(true);
        }
      }
    } finally {
      act(() => {
        root.unmount();
      });
      container.remove();
    }
  });

  // 9x. [Card 274 / ACC-09] Node & Placement Detail Screens Contrast & DOM Token Binding: NodeDetail, PlacementExplainView, and ResourceTopologyGraph
  it('ACC-09 / Card 274: NodeDetail, PlacementExplainView, and ResourceTopologyGraph comply with WCAG 2.2 AA contrast and fail-closed contracts', async () => {
    const container = document.createElement('div');
    document.body.appendChild(container);
    const root = createRoot(container);

    try {
      // 1. PlacementExplainView DOM rendering & token verification
      const mockExplainResult: PlacementExplainResult = {
        selectedNodeId: 'node-01',
        evaluations: [
          {
            nodeId: 'node-01',
            hostname: 'compute-alpha',
            os: 'linux',
            hardFilterPassed: true,
            rejectionReasons: [],
            scores: { localityScore: 90, headroomScore: 85, networkCostScore: 80, totalScore: 86 },
          },
          {
            nodeId: 'node-02',
            hostname: 'compute-beta',
            os: 'linux',
            hardFilterPassed: true,
            rejectionReasons: [],
            scores: { localityScore: 70, headroomScore: 60, networkCostScore: 75, totalScore: 68 },
          },
          {
            nodeId: 'node-03',
            hostname: 'storage-gamma',
            os: 'linux',
            hardFilterPassed: false,
            rejectionReasons: ['VRAM 부족: 필요 16GB / 가용 8GB'],
          },
        ],
        policyVersion: 'v1.4',
        snapshotVersion: 'snap-402',
        decidedAt: '2026-10-05T12:00:00Z',
      };

      await act(async () => {
        root.render(<PlacementExplainView explainResult={mockExplainResult} />);
      });

      // 1-1. Simulation badge: token binding and contrast
      const simBadge = container.querySelector('[data-testid="placement-explain-simulation-badge"]') as HTMLElement;
      expect(simBadge, 'Simulation badge must render').not.toBeNull();
      expect(simBadge.style.backgroundColor, 'Simulation badge bg must bind to var(--color-bg-subtle)').toBe('var(--color-bg-subtle)');
      expect(simBadge.style.color, 'Simulation badge text must bind to var(--color-status-unknown)').toBe('var(--color-status-unknown)');
      expect(simBadge.style.borderColor || simBadge.style.border, 'Simulation badge border must bind to var(--color-status-unknown)').toContain('var(--color-status-unknown)');

      const simTextCrLight = getContrast(lightTokens['--color-status-unknown'], lightTokens['--color-bg-subtle']);
      const simTextCrDark = getContrast(darkTokens['--color-status-unknown'], darkTokens['--color-bg-subtle']);
      expect(simTextCrLight, 'Simulation badge text light contrast >= 4.5:1').toBeGreaterThanOrEqual(4.5);
      expect(simTextCrDark, 'Simulation badge text dark contrast >= 4.5:1').toBeGreaterThanOrEqual(4.5);

      const simBorderCrLight = getContrast(lightTokens['--color-status-unknown'], lightTokens['--color-bg-subtle']);
      const simBorderCrDark = getContrast(darkTokens['--color-status-unknown'], darkTokens['--color-bg-subtle']);
      expect(simBorderCrLight, 'Simulation badge border light contrast >= 3.0:1').toBeGreaterThanOrEqual(3.0);
      expect(simBorderCrDark, 'Simulation badge border dark contrast >= 3.0:1').toBeGreaterThanOrEqual(3.0);

      // 1-2. Winner banner with selected node
      const winnerBanner = container.querySelector('[data-testid="placement-explain-winner-banner"]') as HTMLElement;
      expect(winnerBanner, 'Winner banner must render').not.toBeNull();
      expect(winnerBanner.style.backgroundColor, 'Winner banner bg must bind to var(--color-bg-subtle)').toBe('var(--color-bg-subtle)');
      expect(winnerBanner.style.borderColor || winnerBanner.style.border, 'Winner banner border must bind to var(--color-status-online)').toContain('var(--color-status-online)');
      expect(winnerBanner.textContent).toContain('최적 배치 노드 선정: node-01');

      // 1-3. Candidate badges: passed vs rejected
      const candidateBadges = Array.from(container.querySelectorAll('[data-testid="placement-explain-candidate-badge"]')) as HTMLElement[];
      expect(candidateBadges.length, 'Must render candidate badges for each evaluation').toBe(3);

      // Passed candidate badge (node-01)
      expect(candidateBadges[0].style.backgroundColor).toBe('var(--color-bg-subtle)');
      expect(candidateBadges[0].style.color).toBe('var(--color-status-online)');
      expect(candidateBadges[0].style.borderColor || candidateBadges[0].style.border).toContain('var(--color-status-online)');
      expect(candidateBadges[0].textContent).toContain('통과 (PASSED)');

      // Rejected candidate badge (node-03)
      expect(candidateBadges[2].style.backgroundColor).toBe('var(--color-bg-subtle)');
      expect(candidateBadges[2].style.color).toBe('var(--color-status-lost)');
      expect(candidateBadges[2].style.borderColor || candidateBadges[2].style.border).toContain('var(--color-status-lost)');
      expect(candidateBadges[2].textContent).toContain('탈락 (REJECTED)');

      // 1-4. Score labels and winner score highlight
      const scoreValues = Array.from(container.querySelectorAll('[data-testid="placement-explain-score-value"]')) as HTMLElement[];
      expect(scoreValues.length, 'Must render score values for passed candidates').toBe(2);
      expect(scoreValues[0].style.color, 'Winner score value must use var(--color-status-online)').toBe('var(--color-status-online)');
      expect(scoreValues[1].style.color, 'Non-winner score value must use var(--color-text-primary)').toBe('var(--color-text-primary)');

      // 1-5. Winner banner without selected node (fail-closed/no winner path)
      const noWinnerResult: PlacementExplainResult = {
        ...mockExplainResult,
        selectedNodeId: null,
      };
      await act(async () => {
        root.render(<PlacementExplainView explainResult={noWinnerResult} />);
      });
      const noWinnerBanner = container.querySelector('[data-testid="placement-explain-winner-banner"]') as HTMLElement;
      expect(noWinnerBanner.style.backgroundColor).toBe('var(--color-bg-subtle)');
      expect(noWinnerBanner.style.borderColor || noWinnerBanner.style.border).toContain('var(--color-status-lost)');
      expect(noWinnerBanner.textContent).toContain('배치 가능한 노드가 없습니다');

      // 2. ResourceTopologyGraph DOM rendering & token verification
      const mockGraphNodes: NodeItem[] = [
        {
          id: 'node-alpha',
          hostname: 'compute-alpha',
          status: 'online',
          ipAddress: '192.168.1.10',
          os: 'linux',
          cpuCores: 16,
          cpuUsagePercent: 25,
          memoryTotalBytes: 64 * 1024 ** 3,
          memoryUsedBytes: 16 * 1024 ** 3,
          gpuCount: 0,
          gpuName: '',
          gpuVramTotalBytes: 0,
          gpuVramUsedBytes: 0,
          telemetryUnavailable: false,
          observationOnly: false,
        },
        {
          id: 'node-fenced',
          hostname: 'compute-fenced',
          status: 'online',
          ipAddress: '192.168.1.11',
          os: 'linux',
          cpuCores: 8,
          cpuUsagePercent: 50,
          memoryTotalBytes: 32 * 1024 ** 3,
          memoryUsedBytes: 16 * 1024 ** 3,
          gpuCount: 0,
          gpuName: '',
          gpuVramTotalBytes: 0,
          gpuVramUsedBytes: 0,
          telemetryUnavailable: false,
          observationOnly: false,
        },
        {
          id: 'node-normal',
          hostname: 'compute-normal',
          status: 'online',
          ipAddress: '192.168.1.12',
          os: 'linux',
          cpuCores: 8,
          cpuUsagePercent: 10,
          memoryTotalBytes: 32 * 1024 ** 3,
          memoryUsedBytes: 4 * 1024 ** 3,
          gpuCount: 0,
          gpuName: '',
          gpuVramTotalBytes: 0,
          gpuVramUsedBytes: 0,
          telemetryUnavailable: false,
          observationOnly: false,
        },
      ];

      const fencedSet = new Set(['node-fenced']);
      let toggledNodeId: string | null = null;
      await act(async () => {
        root.render(
          <ResourceTopologyGraph
            nodes={mockGraphNodes}
            fencedNodeIds={fencedSet}
            selectedNodeId="node-alpha"
            onToggleFence={(id) => {
              toggledNodeId = id;
            }}
          />
        );
      });

      // 2-1. Selected node card & badge
      const selectedNodeEl = container.querySelector('[data-testid="resource-topology-node-node-alpha"]') as HTMLElement;
      expect(selectedNodeEl, 'Selected node card must render').not.toBeNull();
      expect(selectedNodeEl.style.borderColor || selectedNodeEl.style.border, 'Selected node card border must bind to var(--color-status-online)').toContain('var(--color-status-online)');
      expect(selectedNodeEl.style.backgroundColor, 'Selected node card bg must bind to var(--color-bg-subtle)').toBe('var(--color-bg-subtle)');

      const selectedBadge = container.querySelector('[data-testid="resource-topology-selected-badge"]') as HTMLElement;
      expect(selectedBadge, 'Selected badge must render').not.toBeNull();
      expect(selectedBadge.style.backgroundColor, 'Selected badge bg must bind to var(--color-bg-subtle)').toBe('var(--color-bg-subtle)');
      expect(selectedBadge.style.color, 'Selected badge text must bind to var(--color-status-online)').toBe('var(--color-status-online)');
      expect(selectedBadge.style.borderColor || selectedBadge.style.border, 'Selected badge border must bind to var(--color-status-online)').toContain('var(--color-status-online)');
      expect(selectedBadge.textContent).toContain('1순위 배치');

      // Contrast for selected badge: text >= 4.5:1, border >= 3.0:1
      const selTextCrLight = getContrast(lightTokens['--color-status-online'], lightTokens['--color-bg-subtle']);
      const selTextCrDark = getContrast(darkTokens['--color-status-online'], darkTokens['--color-bg-subtle']);
      expect(selTextCrLight, 'Selected badge text light contrast >= 4.5:1').toBeGreaterThanOrEqual(4.5);
      expect(selTextCrDark, 'Selected badge text dark contrast >= 4.5:1').toBeGreaterThanOrEqual(4.5);

      const selBorderCrLight = getContrast(lightTokens['--color-status-online'], lightTokens['--color-bg-subtle']);
      const selBorderCrDark = getContrast(darkTokens['--color-status-online'], darkTokens['--color-bg-subtle']);
      expect(selBorderCrLight, 'Selected badge border light contrast >= 3.0:1').toBeGreaterThanOrEqual(3.0);
      expect(selBorderCrDark, 'Selected badge border dark contrast >= 3.0:1').toBeGreaterThanOrEqual(3.0);

      // Non-text card border contrast on surface: >= 3.0:1
      const selCardBorderCrLight = getContrast(lightTokens['--color-status-online'], lightTokens['--color-bg-surface']);
      const selCardBorderCrDark = getContrast(darkTokens['--color-status-online'], darkTokens['--color-bg-surface']);
      expect(selCardBorderCrLight, 'Selected card border on light surface >= 3.0:1').toBeGreaterThanOrEqual(3.0);
      expect(selCardBorderCrDark, 'Selected card border on dark surface >= 3.0:1').toBeGreaterThanOrEqual(3.0);

      // 2-2. Fenced node card & badge
      const fencedNodeEl = container.querySelector('[data-testid="resource-topology-node-node-fenced"]') as HTMLElement;
      expect(fencedNodeEl, 'Fenced node card must render').not.toBeNull();
      expect(fencedNodeEl.style.borderColor || fencedNodeEl.style.border, 'Fenced node card border must bind to var(--color-status-lost)').toContain('var(--color-status-lost)');
      expect(fencedNodeEl.style.backgroundColor, 'Fenced node card bg must bind to var(--color-bg-subtle)').toBe('var(--color-bg-subtle)');

      const fencedBadge = container.querySelector('[data-testid="resource-topology-fenced-badge"]') as HTMLElement;
      expect(fencedBadge, 'Fenced badge must render').not.toBeNull();
      expect(fencedBadge.style.backgroundColor, 'Fenced badge bg must bind to var(--color-bg-subtle)').toBe('var(--color-bg-subtle)');
      expect(fencedBadge.style.color, 'Fenced badge text must bind to var(--color-status-lost)').toBe('var(--color-status-lost)');
      expect(fencedBadge.style.borderColor || fencedBadge.style.border, 'Fenced badge border must bind to var(--color-status-lost)').toContain('var(--color-status-lost)');
      expect(fencedBadge.textContent).toContain('FENCED');

      const fencedTextCrLight = getContrast(lightTokens['--color-status-lost'], lightTokens['--color-bg-subtle']);
      const fencedTextCrDark = getContrast(darkTokens['--color-status-lost'], darkTokens['--color-bg-subtle']);
      expect(fencedTextCrLight, 'Fenced badge text light contrast >= 4.5:1').toBeGreaterThanOrEqual(4.5);
      expect(fencedTextCrDark, 'Fenced badge text dark contrast >= 4.5:1').toBeGreaterThanOrEqual(4.5);

      const fencedBorderCrLight = getContrast(lightTokens['--color-status-lost'], lightTokens['--color-bg-subtle']);
      const fencedBorderCrDark = getContrast(darkTokens['--color-status-lost'], darkTokens['--color-bg-subtle']);
      expect(fencedBorderCrLight, 'Fenced badge border light contrast >= 3.0:1').toBeGreaterThanOrEqual(3.0);
      expect(fencedBorderCrDark, 'Fenced badge border dark contrast >= 3.0:1').toBeGreaterThanOrEqual(3.0);

      // Non-text fenced card border contrast on surface: >= 3.0:1
      const fencedCardBorderCrLight = getContrast(lightTokens['--color-status-lost'], lightTokens['--color-bg-surface']);
      const fencedCardBorderCrDark = getContrast(darkTokens['--color-status-lost'], darkTokens['--color-bg-surface']);
      expect(fencedCardBorderCrLight, 'Fenced card border on light surface >= 3.0:1').toBeGreaterThanOrEqual(3.0);
      expect(fencedCardBorderCrDark, 'Fenced card border on dark surface >= 3.0:1').toBeGreaterThanOrEqual(3.0);

      // 2-3. Normal node card
      const normalNodeEl = container.querySelector('[data-testid="resource-topology-node-node-normal"]') as HTMLElement;
      expect(normalNodeEl, 'Normal node card must render').not.toBeNull();
      expect(normalNodeEl.style.borderColor || normalNodeEl.style.border, 'Normal node card border must bind to var(--color-border-subtle)').toContain('var(--color-border-subtle)');
      expect(normalNodeEl.style.backgroundColor, 'Normal node card bg must bind to var(--color-bg-subtle)').toBe('var(--color-bg-subtle)');

      // 3. NodeDetail fail-closed timeline status & getClusterNodeStatusConfig integration
      const testOfflineNode = {
        ...mockGraphNodes[0],
        status: 'offline',
      };
      await act(async () => {
        root.render(<NodeDetail node={testOfflineNode as any} onBack={() => {}} />);
      });
      const timelineOffline = container.querySelector('[data-testid="node-detail-timeline-status"]') as HTMLElement;
      expect(timelineOffline.style.color, 'Offline timeline must bind to var(--color-status-offline)').toBe('var(--color-status-offline)');
      expect(timelineOffline.textContent).toContain('Heartbeat FAILED (OFFLINE)');

      const testCorruptNode = {
        ...mockGraphNodes[0],
        status: 'corrupted_state',
      };
      await act(async () => {
        root.render(<NodeDetail node={testCorruptNode as any} onBack={() => {}} />);
      });
      const timelineCorrupt = container.querySelector('[data-testid="node-detail-timeline-status"]') as HTMLElement;
      expect(timelineCorrupt.style.color, 'Corrupt status must bind to var(--color-status-unknown)').toBe('var(--color-status-unknown)');
      expect(timelineCorrupt.textContent).toContain('Heartbeat FAILED (UNKNOWN (corrupted_state))');
    } finally {
      act(() => {
        root.unmount();
      });
      container.remove();
    }
  });

  // 9y. [Card 275 / ACC-09] EvidenceViewer Contrast, Strict Wire Contracts, & Fail-Closed DOM Token Binding
  it('ACC-09 / Card 275: EvidenceViewer complies with WCAG 2.2 AA contrast, fail-closed contracts, and DOM token bindings', async () => {
    const container = document.createElement('div');
    document.body.appendChild(container);
    const root = createRoot(container);

    try {
      // 1. EVIDENCE_INTEGRITY_CONFIG exact key set equality with UI-derived projection statuses
      const expectedIntegrityKeys = [...UI_INTEGRITY_PROJECTION_STATUSES];
      expect(expectedIntegrityKeys.length, 'UI integrity projection must define 4 status items').toBe(4);
      expect(Object.keys(EVIDENCE_INTEGRITY_CONFIG).sort(), 'EVIDENCE_INTEGRITY_CONFIG keys must exactly match UI projection statuses').toEqual([...expectedIntegrityKeys].sort());

      // 1b. Verify derivation projection rules strictly derive all statuses from canonical RunResultView fields:
      expect(deriveIntegrityStatus({ output: { verified: true } })).toBe('PASS');
      expect(deriveIntegrityStatus({ output: { verified: false } })).toBe('FAIL');
      expect(deriveIntegrityStatus({ state: 'failed' })).toBe('RUN_FAILED');
      expect(deriveIntegrityStatus({})).toBe('UNVERIFIED');

      // 2. Numerical contrast calculations for each status config (text >= 4.5:1, border >= 3.0:1 on subtle & surface)
      const lSurface = resolveTokenHex('--color-bg-surface', lightTokens);
      const dSurface = resolveTokenHex('--color-bg-surface', darkTokens);
      const lSubtle = resolveTokenHex('--color-bg-subtle', lightTokens);
      const dSubtle = resolveTokenHex('--color-bg-subtle', darkTokens);

      for (const [status, cfg] of Object.entries(EVIDENCE_INTEGRITY_CONFIG)) {
        const fgTok = cfg.colorVar.replace(/^var\(|\)$/g, '');
        const bgTok = cfg.bgVar.replace(/^var\(|\)$/g, '');
        const borderTok = cfg.borderVar.replace(/^var\(|\)$/g, '');

        const lFg = resolveTokenHex(fgTok, lightTokens);
        const dFg = resolveTokenHex(fgTok, darkTokens);
        const lBg = resolveTokenHex(bgTok, lightTokens);
        const dBg = resolveTokenHex(bgTok, darkTokens);
        const lBorder = resolveTokenHex(borderTok, lightTokens);
        const dBorder = resolveTokenHex(borderTok, darkTokens);

        // Text contrast on own badge background
        const lightTextCr = getContrast(lFg, lBg);
        const darkTextCr = getContrast(dFg, dBg);
        expect(lightTextCr, `EVIDENCE_INTEGRITY_CONFIG[${status}] text light contrast >= 4.5:1`).toBeGreaterThanOrEqual(4.5);
        expect(darkTextCr, `EVIDENCE_INTEGRITY_CONFIG[${status}] text dark contrast >= 4.5:1`).toBeGreaterThanOrEqual(4.5);

        // Border contrast on parent card surface
        const lightBorderCr = getContrast(lBorder, lSurface);
        const darkBorderCr = getContrast(dBorder, dSurface);
        expect(lightBorderCr, `EVIDENCE_INTEGRITY_CONFIG[${status}] border light contrast >= 3.0:1`).toBeGreaterThanOrEqual(3.0);
        expect(darkBorderCr, `EVIDENCE_INTEGRITY_CONFIG[${status}] border dark contrast >= 3.0:1`).toBeGreaterThanOrEqual(3.0);
      }

      // 3. Fail-closed UNKNOWN fallback test: Object.hasOwn defense & prototype key rejection
      const unknownFallback = getEvidenceIntegrityConfig('UNKNOWN_STATUS');
      expect(unknownFallback.label).toContain('UNKNOWN: UNKNOWN_STATUS');
      expect(unknownFallback.colorVar).toBe('var(--color-status-unknown)');
      expect(unknownFallback.bgVar).toBe('var(--color-bg-subtle)');
      expect(unknownFallback.borderVar).toBe('var(--color-status-unknown)');

      // Prototype property injection attacks must fall back to UNKNOWN
      for (const protoKey of ['toString', 'constructor', '__proto__', 'valueOf']) {
        const protoRes = getEvidenceIntegrityConfig(protoKey);
        expect(protoRes.label, `Prototype key ${protoKey} must trigger UNKNOWN fallback`).toContain('UNKNOWN');
      }

      // Null and undefined fall back to clean UNKNOWN without raw string
      expect(getEvidenceIntegrityConfig(null).label).toBe('미확인 무결성 상태 (UNKNOWN)');
      expect(getEvidenceIntegrityConfig(undefined).label).toBe('미확인 무결성 상태 (UNKNOWN)');

      // UNKNOWN fallback contrast verification
      const lUnknownFg = resolveTokenHex('--color-status-unknown', lightTokens);
      const dUnknownFg = resolveTokenHex('--color-status-unknown', darkTokens);
      expect(getContrast(lUnknownFg, lSubtle), 'UNKNOWN text light contrast on subtle >= 4.5:1').toBeGreaterThanOrEqual(4.5);
      expect(getContrast(dUnknownFg, dSubtle), 'UNKNOWN text dark contrast on subtle >= 4.5:1').toBeGreaterThanOrEqual(4.5);
      expect(getContrast(lUnknownFg, lSurface), 'UNKNOWN border light contrast on surface >= 3.0:1').toBeGreaterThanOrEqual(3.0);
      expect(getContrast(dUnknownFg, dSurface), 'UNKNOWN border dark contrast on surface >= 3.0:1').toBeGreaterThanOrEqual(3.0);

      // 4. DOM Rendering tests for all 4 integrity states, UNKNOWN, sealed, and error alert
      const baseRunResult: RunResultView = {
        id: 'run-c275-pass',
        runId: 'run-c275-pass',
        projectId: 'prj-c275',
        status: 'succeeded',
        state: 'succeeded',
        nodeId: 'node-01',
        objective: 'Evidence Viewer Contrast Verification',
        output: { sha256: 'e3b0c44298fc1c149afbf4c8996fb92427ae41e4649b934ca495991b7852b855', sizeBytes: 2048, verified: true },
        evidence: { evidenceId: 'ev-c275-01', outputSha256: 'e3b0c44298fc1c149afbf4c8996fb92427ae41e4649b934ca495991b7852b855' },
        stopReceipt: { exitCode: 0, physicallyStopped: true, resourceReclaimed: true, verified: true },
        completedAt: '2026-10-05T12:00:00Z',
        sealed: true,
      };

      // 4-1. PASS state DOM verification
      vi.spyOn(client, 'apiClient').mockResolvedValueOnce(baseRunResult);
      await act(async () => {
        root.render(<EvidenceViewer runId="run-c275-pass" projectId="prj-c275" onBack={() => {}} />);
      });

      const passBadge = container.querySelector('[data-testid="evidence-status-pass"]') as HTMLElement;
      expect(passBadge, 'PASS badge must render').not.toBeNull();
      expect(passBadge.textContent).toContain('출력 무결성 검증 통과 (PASS)');
      expect(passBadge.style.backgroundColor).toBe('var(--color-bg-subtle)');
      expect(passBadge.style.color).toBe('var(--color-brand-success)');
      expect(passBadge.style.borderColor || passBadge.style.border).toContain('var(--color-brand-success)');

      // Sealed badge verification
      const sealedBadge = container.querySelector('[data-testid="evidence-status-sealed"]') as HTMLElement;
      expect(sealedBadge, 'SEALED badge must render').not.toBeNull();
      expect(sealedBadge.textContent).toContain('불변 봉인 (SEALED)');
      expect(sealedBadge.style.backgroundColor).toBe('var(--color-bg-subtle)');
      expect(sealedBadge.style.color).toBe('var(--color-brand-primary)');
      expect(sealedBadge.style.borderColor || sealedBadge.style.border).toContain('var(--color-brand-primary)');

      // 4-2. FAIL state DOM verification
      const failRunResult: RunResultView = {
        ...baseRunResult,
        id: 'run-c275-fail',
        runId: 'run-c275-fail',
        output: { sha256: 'f'.repeat(64), sizeBytes: 1024, verified: false as any },
      };
      vi.spyOn(client, 'apiClient').mockResolvedValueOnce(failRunResult);
      await act(async () => {
        root.render(<EvidenceViewer runId="run-c275-fail" projectId="prj-c275" onBack={() => {}} />);
      });

      const failBadge = container.querySelector('[data-testid="evidence-status-fail"]') as HTMLElement;
      expect(failBadge, 'FAIL badge must render').not.toBeNull();
      expect(failBadge.textContent).toContain('출력 무결성 검증 실패 (FAIL)');
      expect(failBadge.style.backgroundColor).toBe('var(--color-bg-subtle)');
      expect(failBadge.style.color).toBe('var(--color-brand-danger)');
      expect(failBadge.style.borderColor || failBadge.style.border).toContain('var(--color-brand-danger)');

      const failNotice = container.querySelector('[data-testid="evidence-failed-notice"]') as HTMLElement;
      expect(failNotice, 'FAIL notice banner must render').not.toBeNull();
      expect(failNotice.style.backgroundColor).toBe('var(--color-risk-l3-bg)');
      expect(failNotice.style.color).toBe('var(--color-risk-l3-text)');
      expect(failNotice.style.borderColor || failNotice.style.border).toContain('var(--color-risk-l3-border)');

      // 4-3. RUN_FAILED state DOM verification
      const runFailedResult: RunResultView = {
        ...baseRunResult,
        id: 'run-c275-run-failed',
        runId: 'run-c275-run-failed',
        state: 'failed',
        output: undefined,
        stopReceipt: { exitCode: 1, physicallyStopped: true, resourceReclaimed: true, verified: false },
      };
      vi.spyOn(client, 'apiClient').mockResolvedValueOnce(runFailedResult);
      await act(async () => {
        root.render(<EvidenceViewer runId="run-c275-run-failed" projectId="prj-c275" onBack={() => {}} />);
      });

      const runFailedBadge = container.querySelector('[data-testid="evidence-status-run-failed"]') as HTMLElement;
      expect(runFailedBadge, 'RUN_FAILED badge must render').not.toBeNull();
      expect(runFailedBadge.textContent).toContain('실행 실패 · 출력 부재 (RUN_FAILED)');
      expect(runFailedBadge.style.backgroundColor).toBe('var(--color-bg-subtle)');
      expect(runFailedBadge.style.color).toBe('var(--color-brand-danger)');
      expect(runFailedBadge.style.borderColor || runFailedBadge.style.border).toContain('var(--color-brand-danger)');

      const runFailedNotice = container.querySelector('[data-testid="evidence-run-failed-notice"]') as HTMLElement;
      expect(runFailedNotice, 'RUN_FAILED notice banner must render').not.toBeNull();
      expect(runFailedNotice.style.backgroundColor).toBe('var(--color-risk-l3-bg)');
      expect(runFailedNotice.style.color).toBe('var(--color-risk-l3-text)');
      expect(runFailedNotice.style.borderColor || runFailedNotice.style.border).toContain('var(--color-risk-l3-border)');

      // 4-4. UNVERIFIED state DOM verification
      const unverifiedResult: RunResultView = {
        ...baseRunResult,
        id: 'run-c275-unverified',
        runId: 'run-c275-unverified',
        output: { sha256: 'b'.repeat(64), sizeBytes: 1024 },
      };
      vi.spyOn(client, 'apiClient').mockResolvedValueOnce(unverifiedResult);
      await act(async () => {
        root.render(<EvidenceViewer runId="run-c275-unverified" projectId="prj-c275" onBack={() => {}} />);
      });

      const unverifiedBadge = container.querySelector('[data-testid="evidence-status-unverified"]') as HTMLElement;
      expect(unverifiedBadge, 'UNVERIFIED badge must render').not.toBeNull();
      expect(unverifiedBadge.textContent).toContain('출력 무결성 미검증 (UNVERIFIED)');
      expect(unverifiedBadge.style.backgroundColor).toBe('var(--color-bg-subtle)');
      expect(unverifiedBadge.style.color).toBe('var(--color-status-unknown)');
      expect(unverifiedBadge.style.borderColor || unverifiedBadge.style.border).toContain('var(--color-status-unknown)');

      const unverifiedNotice = container.querySelector('[data-testid="evidence-unverified-notice"]') as HTMLElement;
      expect(unverifiedNotice, 'UNVERIFIED notice banner must render').not.toBeNull();
      expect(unverifiedNotice.style.backgroundColor).toBe('var(--color-bg-subtle)');
      expect(unverifiedNotice.style.color).toBe('var(--color-status-unknown)');
      expect(unverifiedNotice.style.borderColor || unverifiedNotice.style.border).toContain('var(--color-status-unknown)');

      // 4-5. Error alert banner DOM verification (missing projectId)
      await act(async () => {
        root.render(<EvidenceViewer runId="run-c275-err" projectId="" onBack={() => {}} />);
      });

      const errorAlert = container.querySelector('[data-testid="evidence-error-alert"]') as HTMLElement;
      expect(errorAlert, 'Error alert banner must render when projectId missing').not.toBeNull();
      expect(errorAlert.style.backgroundColor).toBe('var(--color-risk-l3-bg)');
      expect(errorAlert.style.color).toBe('var(--color-risk-l3-text)');
      expect(errorAlert.style.borderColor || errorAlert.style.border).toContain('var(--color-risk-l3-border)');
      expect(errorAlert.textContent).toContain('증거 패키지 동기화 오류');

      // 4-6. UNKNOWN fallback state DOM verification
      const unknownResult: RunResultView = {
        ...baseRunResult,
        id: 'run-c275-unknown',
        runId: 'run-c275-unknown',
        output: { sha256: 'c'.repeat(64), sizeBytes: 1024, verified: 'CORRUPTED_VALUE' as any },
      };
      vi.spyOn(client, 'apiClient').mockResolvedValueOnce(unknownResult);
      await act(async () => {
        root.render(<EvidenceViewer runId="run-c275-unknown" projectId="prj-c275" onBack={() => {}} />);
      });

      const unknownBadge = container.querySelector('[data-testid="evidence-status-unknown"]') as HTMLElement;
      expect(unknownBadge, 'UNKNOWN badge must render when integrityVerification is unrecognized').not.toBeNull();
      expect(unknownBadge.textContent).toContain('UNKNOWN');
      expect(unknownBadge.style.backgroundColor).toBe('var(--color-bg-subtle)');
      expect(unknownBadge.style.color).toBe('var(--color-status-unknown)');
      expect(unknownBadge.style.borderColor || unknownBadge.style.border).toContain('var(--color-status-unknown)');

      // 5. Fail-closed undefined token containment check (EvidenceViewer var(--x) ⊆ index.css declared tokens)
      const cssPath = path.resolve(__dirname, '../src/index.css');
      const cssContent = fs.readFileSync(cssPath, 'utf-8');
      const declaredCssTokens = new Set<string>();
      const tokenDeclRegex = /(--[a-z0-9-]+)\s*:\s*([^;]+);/g;
      let declMatch;
      while ((declMatch = tokenDeclRegex.exec(cssContent)) !== null) {
        declaredCssTokens.add(declMatch[1].trim());
      }

      const evPath = path.resolve(__dirname, '../src/features/evidence/EvidenceViewer.tsx');
      const evContent = fs.readFileSync(evPath, 'utf-8');
      const varMatches = evContent.match(/var\((--[a-z0-9-]+)/g) || [];
      for (const v of varMatches) {
        const tokenName = v.replace('var(', '');
        expect(declaredCssTokens.has(tokenName), `Token ${tokenName} used in EvidenceViewer.tsx must be declared in index.css`).toBe(true);
      }
    } finally {
      act(() => {
        root.unmount();
      });
      container.remove();
    }
  });

  // 9z. [Card 276 / ACC-09] ApprovalDetail & Header Contrast, Canonical Wire Contracts, & Fail-Closed DOM Token Binding
  it('ACC-09 / Card 276: ApprovalDetail and Header comply with WCAG 2.2 AA contrast, fail-closed contracts, and DOM token bindings', async () => {
    const container = document.createElement('div');
    document.body.appendChild(container);
    const root = createRoot(container);

    try {
      // 1. APPROVAL_STATUS_CONFIG exact key set equality with canonical ApprovalView wire enum (Card 273 F-R3 pattern)
      const schemaPath = path.resolve(__dirname, '../../../contracts/v1alpha1/core.schema.json');
      const canonicalCoreSchema = JSON.parse(fs.readFileSync(schemaPath, 'utf-8'));
      const expectedApprovalKeys: string[] = canonicalCoreSchema.$defs?.ApprovalView?.properties?.status?.enum ?? [];
      expect(expectedApprovalKeys.length, 'Canonical schema must define 5 ApprovalView status items').toBe(5);
      expect(Object.keys(APPROVAL_STATUS_CONFIG).sort(), 'APPROVAL_STATUS_CONFIG keys must exactly match canonical ApprovalView status wire enum').toEqual([...expectedApprovalKeys].sort());
      expect([...APPROVAL_STATUSES].sort(), 'APPROVAL_STATUSES exported from ApprovalCenter must match canonical ApprovalView status wire enum').toEqual([...expectedApprovalKeys].sort());

      // 2. Numerical contrast calculations for each status config (text >= 4.5:1, border >= 3.0:1 on subtle & surface)
      const lSurface = resolveTokenHex('--color-bg-surface', lightTokens);
      const dSurface = resolveTokenHex('--color-bg-surface', darkTokens);
      const lSubtle = resolveTokenHex('--color-bg-subtle', lightTokens);
      const dSubtle = resolveTokenHex('--color-bg-subtle', darkTokens);

      for (const [status, cfg] of Object.entries(APPROVAL_STATUS_CONFIG)) {
        const fgTok = cfg.color.replace(/^var\(|\)$/g, '');
        const bgTok = cfg.bg.replace(/^var\(|\)$/g, '');
        const borderTok = cfg.border.replace(/^var\(|\)$/g, '');

        const lFg = resolveTokenHex(fgTok, lightTokens);
        const dFg = resolveTokenHex(fgTok, darkTokens);
        const lBg = resolveTokenHex(bgTok, lightTokens);
        const dBg = resolveTokenHex(bgTok, darkTokens);
        const lBorder = resolveTokenHex(borderTok, lightTokens);
        const dBorder = resolveTokenHex(borderTok, darkTokens);

        // Text contrast on own badge background
        const lightTextCr = getContrast(lFg, lBg);
        const darkTextCr = getContrast(dFg, dBg);
        expect(lightTextCr, `APPROVAL_STATUS_CONFIG[${status}] text light contrast >= 4.5:1`).toBeGreaterThanOrEqual(4.5);
        expect(darkTextCr, `APPROVAL_STATUS_CONFIG[${status}] text dark contrast >= 4.5:1`).toBeGreaterThanOrEqual(4.5);

        // Border contrast on parent card surface
        const lightBorderCr = getContrast(lBorder, lSurface);
        const darkBorderCr = getContrast(dBorder, dSurface);
        expect(lightBorderCr, `APPROVAL_STATUS_CONFIG[${status}] border light contrast >= 3.0:1`).toBeGreaterThanOrEqual(3.0);
        expect(darkBorderCr, `APPROVAL_STATUS_CONFIG[${status}] border dark contrast >= 3.0:1`).toBeGreaterThanOrEqual(3.0);
      }

      // 3. Fail-closed UNKNOWN fallback test: Object.hasOwn defense & prototype key rejection
      const unknownFallback = getApprovalStatusConfig('UNKNOWN_STATUS');
      expect(unknownFallback.label).toContain('UNKNOWN (UNKNOWN_STATUS)');
      expect(unknownFallback.color).toBe('var(--color-status-unknown)');
      expect(unknownFallback.bg).toBe('var(--color-bg-subtle)');
      expect(unknownFallback.border).toBe('var(--color-status-unknown)');

      // Prototype property injection attacks must fall back to UNKNOWN
      for (const protoKey of ['toString', 'constructor', '__proto__', 'valueOf']) {
        const protoRes = getApprovalStatusConfig(protoKey);
        expect(protoRes.label, `Prototype key ${protoKey} must trigger UNKNOWN fallback`).toContain('UNKNOWN');
      }

      // Null and undefined fall back to clean UNKNOWN without raw string
      expect(getApprovalStatusConfig(null).label).toBe('UNKNOWN');
      expect(getApprovalStatusConfig(undefined).label).toBe('UNKNOWN');

      // UNKNOWN fallback contrast verification
      const lUnknownFg = resolveTokenHex('--color-status-unknown', lightTokens);
      const dUnknownFg = resolveTokenHex('--color-status-unknown', darkTokens);
      expect(getContrast(lUnknownFg, lSubtle), 'UNKNOWN text light contrast on subtle >= 4.5:1').toBeGreaterThanOrEqual(4.5);
      expect(getContrast(dUnknownFg, dSubtle), 'UNKNOWN text dark contrast on subtle >= 4.5:1').toBeGreaterThanOrEqual(4.5);
      expect(getContrast(lUnknownFg, lSurface), 'UNKNOWN border light contrast on surface >= 3.0:1').toBeGreaterThanOrEqual(3.0);
      expect(getContrast(dUnknownFg, dSurface), 'UNKNOWN border dark contrast on surface >= 3.0:1').toBeGreaterThanOrEqual(3.0);

      // 4. ApprovalDetail DOM rendering tests
      const testApproval: ApprovalItem = {
        id: 'app-c276-01',
        requestedBy: 'operator-1',
        requestedAt: '2026-10-05T12:00:00Z',
        expiresAt: new Date(Date.now() + 3600000).toISOString(),
        riskLevel: 'L2',
        status: 'pending',
        actionType: 'HOTFIX_DEPLOY',
        description: 'Card 276 contrast tokenization verification',
        boundRunVersion: '1.4.2-hotfix',
        unifiedDiff: '--- a/kernel.c\n+++ b/kernel.c\n@@ -10,3 +10,3 @@\n- old_code();\n+ new_code();',
        nonce: 'nonce-c276',
        target: 'node-01',
        command: 'systemctl restart saintvision',
        actionDigest: 'sha256-abcdef1234567890',
        requiredApprovals: 1,
      };

      await act(async () => {
        root.render(
          <ApprovalDetail
            approval={testApproval}
            currentUserId="reviewer-2"
            onApprove={async () => {}}
            onReject={async () => {}}
          />
        );
      });

      // 4-1. Status badge in ApprovalDetail top banner
      const statusBadge = container.querySelector('[data-testid="approval-detail-status-pending"]') as HTMLElement;
      expect(statusBadge, 'Approval status badge must render').not.toBeNull();
      expect(statusBadge.textContent).toContain('PENDING');
      expect(statusBadge.style.backgroundColor).toBe('var(--color-bg-subtle)');
      expect(statusBadge.style.color).toBe('var(--color-status-degraded)');
      expect(statusBadge.style.borderColor || statusBadge.style.border).toContain('var(--color-status-degraded)');

      // 4-2. Bound Version badge
      const boundBadge = container.querySelector('[data-testid="bound-version-badge"]') as HTMLElement;
      expect(boundBadge, 'Bound version badge must render').not.toBeNull();
      expect(boundBadge.textContent).toContain('1.4.2-hotfix');
      expect(boundBadge.style.backgroundColor).toBe('var(--color-bg-surface)');
      expect(boundBadge.style.color).toBe('var(--color-brand-primary)');
      expect(boundBadge.style.borderColor || boundBadge.style.border).toContain('var(--color-brand-primary)');

      // 4-3. Rollback risk warning banner
      const rollbackBanner = container.querySelector('[data-testid="rollback-warning-banner"]') as HTMLElement;
      expect(rollbackBanner, 'Rollback warning banner must render').not.toBeNull();
      expect(rollbackBanner.style.backgroundColor).toBe('var(--color-risk-l3-bg)');
      expect(rollbackBanner.style.color).toBe('var(--color-risk-l3-text)');
      expect(rollbackBanner.style.borderColor || rollbackBanner.style.border).toContain('var(--color-risk-l3-border)');

      // 4-4. Unified Diff <pre>
      const diffPre = container.querySelector('pre') as HTMLElement;
      expect(diffPre, 'Unified Diff <pre> must render').not.toBeNull();
      expect(diffPre.style.backgroundColor).toBe('var(--color-bg-canvas)');
      expect(diffPre.style.color).toBe('var(--color-text-primary)');
      expect(diffPre.style.borderColor || diffPre.style.border).toContain('var(--color-border-strong)');

      // 4-5. Reject modal backdrop tokenization
      const rejectButton = container.querySelector('[data-testid="approval-reject-button"]') as HTMLButtonElement;
      expect(rejectButton, 'Reject button must exist').not.toBeNull();
      await act(async () => {
        rejectButton.click();
      });

      const modalDialog = container.querySelector('[role="dialog"]') as HTMLElement;
      expect(modalDialog, 'Reject modal dialog must open').not.toBeNull();
      expect(modalDialog.style.backgroundColor).toBe('var(--color-bg-backdrop)');

      // 5. Header DOM rendering tests
      await act(async () => {
        root.render(
          <Header
            currentTheme="dark"
            onToggleTheme={() => {}}
            onlineNodesCount={5}
            totalNodesCount={5}
            activeTab="approvals"
            onSelectTab={() => {}}
            currentUser={{ id: 'admin-1', name: 'Master Operator', role: 'SecAdmin' }}
            onLogout={() => {}}
            onSwitchToDesktop={() => {}}
          />
        );
      });

      // 5-1. User name
      const userNameEl = container.querySelector('span[style*="font-weight: 600"]') as HTMLElement;
      expect(userNameEl, 'User name element must render').not.toBeNull();
      expect(userNameEl.textContent).toContain('Master Operator');
      expect(userNameEl.style.color).toBe('var(--color-brand-primary)');

      // 5-2. Role badge
      const roleBadgeEl = container.querySelector('span[style*="font-size: 0.6875rem"]') as HTMLElement;
      expect(roleBadgeEl, 'Role badge element must render').not.toBeNull();
      expect(roleBadgeEl.textContent).toContain('SecAdmin');
      expect(roleBadgeEl.style.backgroundColor).toBe('var(--color-bg-surface)');
      expect(roleBadgeEl.style.color).toBe('var(--color-text-secondary)');

      // 5-3. Web Desktop switch button
      const desktopButton = container.querySelector('button[aria-label="Web Desktop으로 전환"]') as HTMLButtonElement;
      expect(desktopButton, 'Web Desktop switch button must render').not.toBeNull();
      expect(desktopButton.style.backgroundColor).toBe('var(--color-bg-subtle)');
      expect(desktopButton.style.color).toBe('var(--color-brand-primary)');
      expect(desktopButton.style.borderColor || desktopButton.style.border).toContain('var(--color-brand-primary)');

      // 6. Token Declaration Verification: all tokens used in ApprovalDetail.tsx & Header.tsx exist in index.css
      const cssPath = path.resolve(__dirname, '../src/index.css');
      const cssContent = fs.readFileSync(cssPath, 'utf-8');
      const declaredCssTokens = new Set<string>();
      const tokenDeclRegex = /(--[a-z0-9-]+)\s*:\s*([^;]+);/g;
      let declMatch;
      while ((declMatch = tokenDeclRegex.exec(cssContent)) !== null) {
        declaredCssTokens.add(declMatch[1].trim());
      }

      for (const relPath of ['features/approvals/ApprovalDetail.tsx', 'shared/ui/Header.tsx']) {
        const fullPath = path.resolve(__dirname, '../src', relPath);
        const fileContent = fs.readFileSync(fullPath, 'utf-8');
        const varMatches = fileContent.match(/var\((--[a-z0-9-]+)/g) || [];
        for (const v of varMatches) {
          const tokenName = v.replace('var(', '');
          expect(declaredCssTokens.has(tokenName), `Token ${tokenName} used in ${relPath} must be declared in index.css`).toBe(true);
        }
      }
    } finally {
      act(() => {
        root.unmount();
      });
      container.remove();
    }
  });

  // 9aa. [Card 277 / ACC-09] App Shell & Release Engine Contrast, Fail-Closed Contracts, & DOM Token Binding
  it('ACC-09 / Card 277: App Shell and releaseEngine comply with WCAG 2.2 AA contrast, fail-closed contracts, and DOM token bindings', async () => {
    // 1. ReleaseManager Accessibility Audits compliance
    const releaseMgr = new ReleaseManager();
    const audits = releaseMgr.getAccessibilityAudits();
    expect(audits.length, 'Accessibility audits must have at least 4 items').toBeGreaterThanOrEqual(4);

    const lCanvas = resolveTokenHex('--color-bg-canvas', lightTokens);
    const dCanvas = resolveTokenHex('--color-bg-canvas', darkTokens);
    const lTextSec = resolveTokenHex('--color-text-secondary', lightTokens);
    const dTextSec = resolveTokenHex('--color-text-secondary', darkTokens);
    const lBorderSubtle = resolveTokenHex('--color-border-subtle', lightTokens);
    const dBorderSubtle = resolveTokenHex('--color-border-subtle', darkTokens);

    const bodyContrastAudit = audits.find((a) => a.ruleId === 'wcag21-1.4.3-contrast-minimum');
    expect(bodyContrastAudit, 'WCAG 1.4.3 body text contrast audit must exist').toBeDefined();
    expect(bodyContrastAudit?.status).toBe('pass');
    const expectedBodyCr = Math.min(
      parseFloat(getContrast(lTextSec, lCanvas).toFixed(2)),
      parseFloat(getContrast(dTextSec, dCanvas).toFixed(2))
    );
    expect(bodyContrastAudit?.contrastRatio).toBe(expectedBodyCr);
    expect(bodyContrastAudit?.contrastRatio).toBe(7.24);

    const nonTextAudit = audits.find((a) => a.ruleId === 'wcag21-1.4.11-non-text-contrast');
    expect(nonTextAudit, 'WCAG 1.4.11 non-text boundary contrast audit must exist').toBeDefined();
    expect(nonTextAudit?.status).toBe('pass');
    const expectedNonTextCr = Math.min(
      parseFloat(getContrast(lBorderSubtle, lCanvas).toFixed(2)),
      parseFloat(getContrast(dBorderSubtle, dCanvas).toFixed(2))
    );
    expect(nonTextAudit?.contrastRatio).toBe(expectedNonTextCr);
    expect(nonTextAudit?.contrastRatio).toBe(3.33);
    expect(nonTextAudit?.description).toContain('--color-border-subtle');
    expect(nonTextAudit?.description).toContain('--color-bg-canvas');
    expect(nonTextAudit?.description).not.toMatch(/#[0-9a-fA-F]{3,8}\b/);

    // 2. Numerical contrast calculations for App Shell tokenized items (WCAG 2.2 AA criteria)
    const lSurface = resolveTokenHex('--color-bg-surface', lightTokens);
    const dSurface = resolveTokenHex('--color-bg-surface', darkTokens);
    const lSubtle = resolveTokenHex('--color-bg-subtle', lightTokens);
    const dSubtle = resolveTokenHex('--color-bg-subtle', darkTokens);
    const lRiskL3Bg = resolveTokenHex('--color-risk-l3-bg', lightTokens);
    const dRiskL3Bg = resolveTokenHex('--color-risk-l3-bg', darkTokens);
    const lRiskL3Text = resolveTokenHex('--color-risk-l3-text', lightTokens);
    const dRiskL3Text = resolveTokenHex('--color-risk-l3-text', darkTokens);
    const lRiskL3Border = resolveTokenHex('--color-risk-l3-border', lightTokens);
    const dRiskL3Border = resolveTokenHex('--color-risk-l3-border', darkTokens);
    const lPrimaryBg = resolveTokenHex('--color-brand-primary-bg', lightTokens);
    const dPrimaryBg = resolveTokenHex('--color-brand-primary-bg', darkTokens);
    const lPrimaryFg = resolveTokenHex('--color-brand-primary-fg', lightTokens);
    const dPrimaryFg = resolveTokenHex('--color-brand-primary-fg', darkTokens);
    const lBorderStrong = resolveTokenHex('--color-border-strong', lightTokens);
    const dBorderStrong = resolveTokenHex('--color-border-strong', darkTokens);
    const lTextMuted = resolveTokenHex('--color-text-muted', lightTokens);
    const dTextMuted = resolveTokenHex('--color-text-muted', darkTokens);
    const lDegraded = resolveTokenHex('--color-status-degraded', lightTokens);
    const dDegraded = resolveTokenHex('--color-status-degraded', darkTokens);

    // Global action error banner text & border
    expect(getContrast(lRiskL3Text, lRiskL3Bg), 'Global error text light contrast >= 4.5:1').toBeGreaterThanOrEqual(4.5);
    expect(getContrast(dRiskL3Text, dRiskL3Bg), 'Global error text dark contrast >= 4.5:1').toBeGreaterThanOrEqual(4.5);
    expect(getContrast(lRiskL3Border, lRiskL3Bg), 'Global error border light contrast >= 3.0:1').toBeGreaterThanOrEqual(3.0);
    expect(getContrast(dRiskL3Border, dRiskL3Bg), 'Global error border dark contrast >= 3.0:1').toBeGreaterThanOrEqual(3.0);

    // Global error dismiss button text & border
    expect(getContrast(lRiskL3Text, lSurface), 'Dismiss button text light contrast >= 4.5:1').toBeGreaterThanOrEqual(4.5);
    expect(getContrast(dRiskL3Text, dSurface), 'Dismiss button text dark contrast >= 4.5:1').toBeGreaterThanOrEqual(4.5);
    expect(getContrast(lRiskL3Border, lSurface), 'Dismiss button border light contrast >= 3.0:1').toBeGreaterThanOrEqual(3.0);
    expect(getContrast(dRiskL3Border, dSurface), 'Dismiss button border dark contrast >= 3.0:1').toBeGreaterThanOrEqual(3.0);

    // Node simulation active button
    expect(getContrast(lPrimaryFg, lPrimaryBg), 'Node sim active text light contrast >= 4.5:1').toBeGreaterThanOrEqual(4.5);
    expect(getContrast(dPrimaryFg, dPrimaryBg), 'Node sim active text dark contrast >= 4.5:1').toBeGreaterThanOrEqual(4.5);
    expect(getContrast(lPrimaryFg, lPrimaryBg), 'Node sim active border light contrast >= 3.0:1').toBeGreaterThanOrEqual(3.0);
    expect(getContrast(dPrimaryFg, dPrimaryBg), 'Node sim active border dark contrast >= 3.0:1').toBeGreaterThanOrEqual(3.0);

    // Node simulation inactive button
    expect(getContrast(lTextSec, lSubtle), 'Node sim inactive text light contrast >= 4.5:1').toBeGreaterThanOrEqual(4.5);
    expect(getContrast(dTextSec, dSubtle), 'Node sim inactive text dark contrast >= 4.5:1').toBeGreaterThanOrEqual(4.5);
    expect(getContrast(lBorderStrong, lSubtle), 'Node sim inactive border light contrast >= 3.0:1').toBeGreaterThanOrEqual(3.0);
    expect(getContrast(dBorderStrong, dSubtle), 'Node sim inactive border dark contrast >= 3.0:1').toBeGreaterThanOrEqual(3.0);

    // Terminal notice container & guidance text
    expect(getContrast(lBorderSubtle, lCanvas), 'Terminal notice border on canvas light contrast >= 3.0:1').toBeGreaterThanOrEqual(3.0);
    expect(getContrast(dBorderSubtle, dCanvas), 'Terminal notice border on canvas dark contrast >= 3.0:1').toBeGreaterThanOrEqual(3.0);
    expect(getContrast(lTextMuted, lSurface), 'Terminal notice muted text light contrast >= 4.5:1').toBeGreaterThanOrEqual(4.5);
    expect(getContrast(dTextMuted, dSurface), 'Terminal notice muted text dark contrast >= 4.5:1').toBeGreaterThanOrEqual(4.5);
    expect(getContrast(lDegraded, lSurface), 'Terminal notice degraded guidance light contrast >= 4.5:1').toBeGreaterThanOrEqual(4.5);
    expect(getContrast(dDegraded, dSurface), 'Terminal notice degraded guidance dark contrast >= 4.5:1').toBeGreaterThanOrEqual(4.5);

    // 3. Token Declaration Verification: all tokens used in App.tsx & releaseEngine.ts exist in index.css
    const cssPath = path.resolve(__dirname, '../src/index.css');
    const cssContent = fs.readFileSync(cssPath, 'utf-8');
    const declaredCssTokens = new Set<string>();
    const tokenDeclRegex = /(--[a-z0-9-]+)\s*:\s*([^;]+);/g;
    let declMatch;
    while ((declMatch = tokenDeclRegex.exec(cssContent)) !== null) {
      declaredCssTokens.add(declMatch[1].trim());
    }

    for (const relPath of ['app/App.tsx', 'features/release/releaseEngine.ts']) {
      const fullPath = path.resolve(__dirname, '../src', relPath);
      const fileContent = fs.readFileSync(fullPath, 'utf-8');
      const varMatches = fileContent.match(/var\((--[a-z0-9-]+)/g) || [];
      for (const v of varMatches) {
        const tokenName = v.replace('var(', '');
        expect(declaredCssTokens.has(tokenName), `Token ${tokenName} used in ${relPath} must be declared in index.css`).toBe(true);
      }
    }
  });

  // 9ab. [Card 278 / ACC-09] DesktopWindow Frame Contrast, Traffic Light Controls, Fail-Closed Contracts, & DOM Token Binding
  it('ACC-09 / Card 278: DesktopWindow frame complies with WCAG 2.2 AA contrast, fail-closed contracts, and DOM token bindings', async () => {
    // 1. Fail-closed WINDOW_CONTROL_CONFIG verification
    expect(Object.keys(WINDOW_CONTROL_CONFIG)).toEqual(['close', 'minimize', 'maximize']);
    for (const action of ['close', 'minimize', 'maximize'] as const) {
      expect(Object.hasOwn(WINDOW_CONTROL_CONFIG, action)).toBe(true);
      const cfg = getWindowControlConfig(action);
      expect(cfg.color).toMatch(/^var\(--color-status-(offline|degraded|online)\)$/);
      expect(cfg.bg).toBe('var(--color-bg-subtle)');
      expect(cfg.border).toMatch(/^var\(--color-status-(offline|degraded|online)\)$/);
      expect(cfg.label).toBeDefined();
    }

    expect(WINDOW_CONTROL_CONFIG.close.color).toBe('var(--color-status-offline)');
    expect(WINDOW_CONTROL_CONFIG.minimize.color).toBe('var(--color-status-degraded)');
    expect(WINDOW_CONTROL_CONFIG.maximize.color).toBe('var(--color-status-online)');
    expect(WINDOW_CONTROL_CONFIG.close.label).toBe('창 닫기');
    expect(WINDOW_CONTROL_CONFIG.minimize.label).toBe('최소화');
    expect(WINDOW_CONTROL_CONFIG.maximize.label).toBe('최대화');

    expect(getWindowControlConfig('close').color).toBe('var(--color-status-offline)');
    expect(getWindowControlConfig('minimize').color).toBe('var(--color-status-degraded)');
    expect(getWindowControlConfig('maximize').color).toBe('var(--color-status-online)');

    // Strict case-sensitive and fallback label tests (kills M38, M40)
    expect(getWindowControlConfig('CLOSE').label).toBe('UNKNOWN (CLOSE)');
    expect(getWindowControlConfig('Close').label).toBe('UNKNOWN (Close)');
    expect(getWindowControlConfig('MINIMIZE').label).toBe('UNKNOWN (MINIMIZE)');

    // Fail-closed fallback verification
    const unknownFallback = getWindowControlConfig('unknown_action');
    expect(unknownFallback.label).toBe('UNKNOWN (unknown_action)');
    expect(unknownFallback.color).toBe('var(--color-status-unknown)');
    expect(unknownFallback.bg).toBe('var(--color-bg-subtle)');
    expect(unknownFallback.border).toBe('var(--color-status-unknown)');

    // Prototype injection attacks fall back to UNKNOWN
    for (const protoKey of ['toString', 'constructor', '__proto__', 'valueOf']) {
      const protoRes = getWindowControlConfig(protoKey);
      expect(protoRes.label, `Prototype key ${protoKey} must trigger UNKNOWN fallback`).toContain('UNKNOWN');
    }
    expect(getWindowControlConfig(null).label).toBe('UNKNOWN');
    expect(getWindowControlConfig(undefined).label).toBe('UNKNOWN');

    // 2. Numerical contrast calculations for DesktopWindow tokens (WCAG 2.2 AA criteria)
    const lCanvas = resolveTokenHex('--color-bg-canvas', lightTokens);
    const dCanvas = resolveTokenHex('--color-bg-canvas', darkTokens);
    const lSurface = resolveTokenHex('--color-bg-surface', lightTokens);
    const dSurface = resolveTokenHex('--color-bg-surface', darkTokens);
    const lSubtle = resolveTokenHex('--color-bg-subtle', lightTokens);
    const dSubtle = resolveTokenHex('--color-bg-subtle', darkTokens);
    const lBorderStrong = resolveTokenHex('--color-border-strong', lightTokens);
    const dBorderStrong = resolveTokenHex('--color-border-strong', darkTokens);
    const lBorderSubtle = resolveTokenHex('--color-border-subtle', lightTokens);
    const dBorderSubtle = resolveTokenHex('--color-border-subtle', darkTokens);
    const lTextPrimary = resolveTokenHex('--color-text-primary', lightTokens);
    const dTextPrimary = resolveTokenHex('--color-text-primary', darkTokens);
    const lTextMuted = resolveTokenHex('--color-text-muted', lightTokens);
    const dTextMuted = resolveTokenHex('--color-text-muted', darkTokens);
    const lStatusOffline = resolveTokenHex('--color-status-offline', lightTokens);
    const dStatusOffline = resolveTokenHex('--color-status-offline', darkTokens);
    const lStatusDegraded = resolveTokenHex('--color-status-degraded', lightTokens);
    const dStatusDegraded = resolveTokenHex('--color-status-degraded', darkTokens);
    const lStatusOnline = resolveTokenHex('--color-status-online', lightTokens);
    const dStatusOnline = resolveTokenHex('--color-status-online', darkTokens);
    const lStatusUnknown = resolveTokenHex('--color-status-unknown', lightTokens);
    const dStatusUnknown = resolveTokenHex('--color-status-unknown', darkTokens);

    // Traffic light buttons on subtle title bar (>= 3.0:1 non-text)
    expect(getContrast(lStatusOffline, lSubtle), 'Close button on subtle light contrast >= 3.0:1').toBeGreaterThanOrEqual(3.0);
    expect(getContrast(dStatusOffline, dSubtle), 'Close button on subtle dark contrast >= 3.0:1').toBeGreaterThanOrEqual(3.0);
    expect(getContrast(lStatusDegraded, lSubtle), 'Minimize button on subtle light contrast >= 3.0:1').toBeGreaterThanOrEqual(3.0);
    expect(getContrast(dStatusDegraded, dSubtle), 'Minimize button on subtle dark contrast >= 3.0:1').toBeGreaterThanOrEqual(3.0);
    expect(getContrast(lStatusOnline, lSubtle), 'Maximize button on subtle light contrast >= 3.0:1').toBeGreaterThanOrEqual(3.0);
    expect(getContrast(dStatusOnline, dSubtle), 'Maximize button on subtle dark contrast >= 3.0:1').toBeGreaterThanOrEqual(3.0);

    // Traffic light buttons on surface title bar (>= 3.0:1 non-text)
    expect(getContrast(lStatusOffline, lSurface), 'Close button on surface light contrast >= 3.0:1').toBeGreaterThanOrEqual(3.0);
    expect(getContrast(dStatusOffline, dSurface), 'Close button on surface dark contrast >= 3.0:1').toBeGreaterThanOrEqual(3.0);
    expect(getContrast(lStatusDegraded, lSurface), 'Minimize button on surface light contrast >= 3.0:1').toBeGreaterThanOrEqual(3.0);
    expect(getContrast(dStatusDegraded, dSurface), 'Minimize button on surface dark contrast >= 3.0:1').toBeGreaterThanOrEqual(3.0);
    expect(getContrast(lStatusOnline, lSurface), 'Maximize button on surface light contrast >= 3.0:1').toBeGreaterThanOrEqual(3.0);
    expect(getContrast(dStatusOnline, dSurface), 'Maximize button on surface dark contrast >= 3.0:1').toBeGreaterThanOrEqual(3.0);

    // UNKNOWN fallback contrast
    expect(getContrast(lStatusUnknown, lSubtle), 'Unknown status on subtle light contrast >= 3.0:1').toBeGreaterThanOrEqual(3.0);
    expect(getContrast(dStatusUnknown, dSubtle), 'Unknown status on subtle dark contrast >= 3.0:1').toBeGreaterThanOrEqual(3.0);

    // Title bar text contrast (>= 4.5:1 text)
    expect(getContrast(lTextPrimary, lSubtle), 'Active title text on subtle light contrast >= 4.5:1').toBeGreaterThanOrEqual(4.5);
    expect(getContrast(dTextPrimary, dSubtle), 'Active title text on subtle dark contrast >= 4.5:1').toBeGreaterThanOrEqual(4.5);
    expect(getContrast(lTextMuted, lSurface), 'Inactive title text on surface light contrast >= 4.5:1').toBeGreaterThanOrEqual(4.5);
    expect(getContrast(dTextMuted, dSurface), 'Inactive title text on surface dark contrast >= 4.5:1').toBeGreaterThanOrEqual(4.5);
    expect(getContrast(lTextMuted, lSubtle), 'Inactive title text on subtle light contrast >= 4.5:1').toBeGreaterThanOrEqual(4.5);
    expect(getContrast(dTextMuted, dSubtle), 'Inactive title text on subtle dark contrast >= 4.5:1').toBeGreaterThanOrEqual(4.5);

    // Frame borders on canvas (>= 3.0:1 non-text)
    expect(getContrast(lBorderStrong, lCanvas), 'Normal window border on canvas light contrast >= 3.0:1').toBeGreaterThanOrEqual(3.0);
    expect(getContrast(dBorderStrong, dCanvas), 'Normal window border on canvas dark contrast >= 3.0:1').toBeGreaterThanOrEqual(3.0);
    expect(getContrast(lBorderSubtle, lCanvas), 'Maximized window border on canvas light contrast >= 3.0:1').toBeGreaterThanOrEqual(3.0);
    expect(getContrast(dBorderSubtle, dCanvas), 'Maximized window border on canvas dark contrast >= 3.0:1').toBeGreaterThanOrEqual(3.0);
    expect(getContrast(lBorderSubtle, lSubtle), 'Title bar border on subtle light contrast >= 3.0:1').toBeGreaterThanOrEqual(3.0);
    expect(getContrast(dBorderSubtle, dSubtle), 'Title bar border on subtle dark contrast >= 3.0:1').toBeGreaterThanOrEqual(3.0);

    // 3. DOM Rendering Verification
    const container = document.createElement('div');
    document.body.appendChild(container);
    const root = createRoot(container);

    try {
      const mockWindow = {
        id: 'win-test-1',
        appId: 'terminal' as const,
        title: '테스트 터미널',
        icon: '🖥️',
        isOpen: true,
        isMinimized: false,
        isMaximized: false,
        zIndex: 10,
        position: { x: 100, y: 100 },
        size: { width: 600, height: 400 },
      };

      await act(async () => {
        root.render(
          <DesktopWindowComponent
            window={mockWindow}
            isActive={true}
            onFocus={() => {}}
            onClose={() => {}}
            onMinimize={() => {}}
            onToggleMaximize={() => {}}
          >
            <div>Window Content</div>
          </DesktopWindowComponent>
        );
      });

      const dialogEl = container.querySelector('div[role="dialog"]') as HTMLElement;
      expect(dialogEl, 'Dialog element must render').not.toBeNull();
      expect(dialogEl.style.backgroundColor).toBe('var(--color-bg-surface)');
      expect(dialogEl.style.borderColor || dialogEl.style.border).toContain('var(--color-border-strong)');
      expect(dialogEl.style.boxShadow).toContain('var(--shadow-lg)');
      expect(dialogEl.style.boxShadow).toContain('var(--color-brand-primary)');
      expect(dialogEl.style.outline || 'inherit', 'Dialog must not suppress focus ring').not.toMatch(/(none|0px|\b0\b)/);
      expect(dialogEl.style.outlineStyle || 'inherit').not.toBe('none');

      const titlebarEl = dialogEl.firstElementChild as HTMLElement;
      expect(titlebarEl, 'Titlebar must render').not.toBeNull();
      expect(titlebarEl.style.backgroundColor).toBe('var(--color-bg-subtle)');
      expect(titlebarEl.style.borderBottom || titlebarEl.style.border).toContain('var(--color-border-subtle)');

      const titleWrapper = container.querySelector('[id^="window-title-"]') as HTMLElement;
      expect(titleWrapper, 'Title wrapper must render').not.toBeNull();
      expect(titleWrapper.style.color).toBe('var(--color-text-primary)');

      const appIdWrapper = titlebarEl.lastElementChild as HTMLElement;
      expect(appIdWrapper, 'AppId wrapper must render').not.toBeNull();
      expect(appIdWrapper.style.color).toBe('var(--color-text-muted)');

      const closeBtn = container.querySelector('button[title="창 닫기"]') as HTMLButtonElement;
      expect(closeBtn, 'Close button must render').not.toBeNull();
      expect(closeBtn.style.backgroundColor).toBe('var(--color-status-offline)');
      expect(closeBtn.style.boxShadow).toBe('var(--shadow-sm)');
      expect(closeBtn.style.outline || 'inherit').not.toMatch(/(none|0px|\b0\b)/);

      const minBtn = container.querySelector('button[title="최소화"]') as HTMLButtonElement;
      expect(minBtn, 'Minimize button must render').not.toBeNull();
      expect(minBtn.style.backgroundColor).toBe('var(--color-status-degraded)');
      expect(minBtn.style.boxShadow).toBe('var(--shadow-sm)');
      expect(minBtn.style.outline || 'inherit').not.toMatch(/(none|0px|\b0\b)/);

      const maxBtn = container.querySelector('button[title="최대화"]') as HTMLButtonElement;
      expect(maxBtn, 'Maximize button must render').not.toBeNull();
      expect(maxBtn.style.backgroundColor).toBe('var(--color-status-online)');
      expect(maxBtn.style.boxShadow).toBe('var(--shadow-sm)');
      expect(maxBtn.style.outline || 'inherit').not.toMatch(/(none|0px|\b0\b)/);

      // Inactive Maximized Render
      await act(async () => {
        root.render(
          <DesktopWindowComponent
            window={{ ...mockWindow, isMaximized: true }}
            isActive={false}
            onFocus={() => {}}
            onClose={() => {}}
            onMinimize={() => {}}
            onToggleMaximize={() => {}}
          >
            <div>Window Content</div>
          </DesktopWindowComponent>
        );
      });

      expect(dialogEl.style.backgroundColor).toBe('var(--color-bg-surface)');
      expect(dialogEl.style.borderColor || dialogEl.style.border).toContain('var(--color-border-subtle)');
      expect(dialogEl.style.boxShadow).toBe('var(--shadow-md)');
      expect(titlebarEl.style.backgroundColor).toBe('var(--color-bg-surface)');
      expect(titlebarEl.style.borderBottom || titlebarEl.style.border).toContain('var(--color-border-subtle)');
      expect(titleWrapper.style.color).toBe('var(--color-text-muted)');
      expect(appIdWrapper.style.color).toBe('var(--color-text-muted)');
    } finally {
      act(() => {
        root.unmount();
      });
      container.remove();
    }

    // 4. Token Declaration Verification: all tokens used in DesktopWindow.tsx exist in index.css
    const cssPath = path.resolve(__dirname, '../src/index.css');
    const cssContent = fs.readFileSync(cssPath, 'utf-8');
    const declaredCssTokens = new Set<string>();
    const tokenDeclRegex = /(--[a-z0-9-]+)\s*:\s*([^;]+);/g;
    let declMatch;
    while ((declMatch = tokenDeclRegex.exec(cssContent)) !== null) {
      declaredCssTokens.add(declMatch[1].trim());
    }

    const dwPath = path.resolve(__dirname, '../src/features/desktop/DesktopWindow.tsx');
    const dwContent = fs.readFileSync(dwPath, 'utf-8');
    const varMatches = dwContent.match(/var\((--[a-z0-9-]+)/g) || [];
    for (const v of varMatches) {
      const tokenName = v.replace('var(', '');
      expect(declaredCssTokens.has(tokenName), `Token ${tokenName} used in DesktopWindow.tsx must be declared in index.css`).toBe(true);
    }
  });

  // 9ac. [Card 279 / ACC-09] TerminalSessionView Contrast, Shell/PTY Configs, Fail-Closed Contracts, & DOM Token Binding
  it('ACC-09 / Card 279: TerminalSessionView complies with WCAG 2.2 AA contrast, fail-closed contracts, and DOM token bindings', async () => {
    // 1. Fail-closed TERMINAL_SHELL_CONFIG verification (powershell, bash, zsh, cmd)
    expect(Object.keys(TERMINAL_SHELL_CONFIG).sort()).toEqual(['bash', 'cmd', 'powershell', 'zsh']);
    for (const shell of ['powershell', 'bash', 'zsh', 'cmd'] as const) {
      expect(Object.hasOwn(TERMINAL_SHELL_CONFIG, shell)).toBe(true);
      const cfg = getTerminalShellConfig(shell);
      expect(cfg.label).toBeDefined();
      expect(cfg.color).toMatch(/^var\(--color-(brand-hover|status-online|text-primary)\)$/);
    }

    expect(TERMINAL_SHELL_CONFIG.powershell.color).toBe('var(--color-brand-hover)');
    expect(TERMINAL_SHELL_CONFIG.bash.color).toBe('var(--color-status-online)');
    expect(TERMINAL_SHELL_CONFIG.zsh.color).toBe('var(--color-brand-hover)');
    expect(TERMINAL_SHELL_CONFIG.cmd.color).toBe('var(--color-text-primary)');

    expect(getTerminalShellConfig('powershell').color).toBe('var(--color-brand-hover)');
    expect(getTerminalShellConfig('bash').color).toBe('var(--color-status-online)');
    expect(getTerminalShellConfig('zsh').color).toBe('var(--color-brand-hover)');
    expect(getTerminalShellConfig('cmd').color).toBe('var(--color-text-primary)');

    // Strict case-sensitive and fallback label tests (kills mutation variations)
    expect(getTerminalShellConfig('POWERSHELL').label).toBe('UNKNOWN (POWERSHELL)');
    expect(getTerminalShellConfig('Bash').label).toBe('UNKNOWN (Bash)');
    expect(getTerminalShellConfig('ZSH').label).toBe('UNKNOWN (ZSH)');
    expect(getTerminalShellConfig('CMD').label).toBe('UNKNOWN (CMD)');

    // Fail-closed fallback verification for shell
    const unknownShell = getTerminalShellConfig('unknown_shell');
    expect(unknownShell.label).toBe('UNKNOWN (unknown_shell)');
    expect(unknownShell.color).toBe('var(--color-status-unknown)');

    // Prototype injection attacks fall back to UNKNOWN (<protoKey>)
    for (const protoKey of ['toString', 'constructor', '__proto__', 'valueOf']) {
      const protoRes = getTerminalShellConfig(protoKey);
      expect(protoRes.color).toBe('var(--color-status-unknown)');
      expect(protoRes.label).toBe(`UNKNOWN (${protoKey})`);
    }
    expect(getTerminalShellConfig(null).label).toBe('UNKNOWN');
    expect(getTerminalShellConfig(undefined).label).toBe('UNKNOWN');
    expect(getTerminalShellConfig('').label).toBe('UNKNOWN');
    expect(getTerminalShellConfig('   ').label).toBe('UNKNOWN');

    // 2. Fail-closed PTY_AUTH_STATUS_CONFIG verification (ticket_bound, awaiting_command)
    expect(UI_PTY_AUTH_PROJECTION_STATUSES).toEqual(['ticket_bound', 'awaiting_command']);
    expect(Object.keys(PTY_AUTH_STATUS_CONFIG).sort()).toEqual(['awaiting_command', 'ticket_bound']);
    for (const st of UI_PTY_AUTH_PROJECTION_STATUSES) {
      expect(Object.hasOwn(PTY_AUTH_STATUS_CONFIG, st)).toBe(true);
      const cfg = getPtyAuthStatusConfig(st);
      expect(cfg.label).toBeDefined();
      expect(cfg.color).toMatch(/^var\(--color-(status-degraded|text-muted)\)$/);
    }

    expect(derivePtyAuthStatus('cmd-123')).toBe('ticket_bound');
    expect(derivePtyAuthStatus(undefined)).toBe('awaiting_command');
    expect(derivePtyAuthStatus('')).toBe('awaiting_command');
    expect(derivePtyAuthStatus('   ')).toBe('awaiting_command');

    expect(getPtyAuthStatusConfig('ticket_bound').color).toBe('var(--color-status-degraded)');
    expect(getPtyAuthStatusConfig('awaiting_command').color).toBe('var(--color-text-muted)');

    // Strict case-sensitive and fallback label tests
    expect(getPtyAuthStatusConfig('TICKET_BOUND').label).toBe('UNKNOWN (TICKET_BOUND)');
    expect(getPtyAuthStatusConfig('Awaiting_Command').label).toBe('UNKNOWN (Awaiting_Command)');

    // Fail-closed fallback verification for PTY auth
    const unknownPty = getPtyAuthStatusConfig('unknown_status');
    expect(unknownPty.label).toBe('UNKNOWN (unknown_status)');
    expect(unknownPty.color).toBe('var(--color-status-unknown)');

    for (const protoKey of ['toString', 'constructor', '__proto__', 'valueOf']) {
      const protoRes = getPtyAuthStatusConfig(protoKey);
      expect(protoRes.color).toBe('var(--color-status-unknown)');
    }
    expect(getPtyAuthStatusConfig(null).label).toBe('UNKNOWN');
    expect(getPtyAuthStatusConfig(undefined).label).toBe('UNKNOWN');

    // 3. Numerical contrast calculations for TerminalSessionView tokens (WCAG 2.2 AA criteria)
    const lCanvas = resolveTokenHex('--color-bg-canvas', lightTokens);
    const dCanvas = resolveTokenHex('--color-bg-canvas', darkTokens);
    const lSurface = resolveTokenHex('--color-bg-surface', lightTokens);
    const dSurface = resolveTokenHex('--color-bg-surface', darkTokens);
    const lSubtle = resolveTokenHex('--color-bg-subtle', lightTokens);
    const dSubtle = resolveTokenHex('--color-bg-subtle', darkTokens);
    const lBorderStrong = resolveTokenHex('--color-border-strong', lightTokens);
    const dBorderStrong = resolveTokenHex('--color-border-strong', darkTokens);
    const lBorderSubtle = resolveTokenHex('--color-border-subtle', lightTokens);
    const dBorderSubtle = resolveTokenHex('--color-border-subtle', darkTokens);
    const lTextPrimary = resolveTokenHex('--color-text-primary', lightTokens);
    const dTextPrimary = resolveTokenHex('--color-text-primary', darkTokens);
    const lTextMuted = resolveTokenHex('--color-text-muted', lightTokens);
    const dTextMuted = resolveTokenHex('--color-text-muted', darkTokens);
    const lBrandHover = resolveTokenHex('--color-brand-hover', lightTokens);
    const dBrandHover = resolveTokenHex('--color-brand-hover', darkTokens);
    const lStatusOnline = resolveTokenHex('--color-status-online', lightTokens);
    const dStatusOnline = resolveTokenHex('--color-status-online', darkTokens);
    const lStatusDegraded = resolveTokenHex('--color-status-degraded', lightTokens);
    const dStatusDegraded = resolveTokenHex('--color-status-degraded', darkTokens);
    const lStatusOffline = resolveTokenHex('--color-status-offline', lightTokens);
    const dStatusOffline = resolveTokenHex('--color-status-offline', darkTokens);
    const lStatusUnknown = resolveTokenHex('--color-status-unknown', lightTokens);
    const dStatusUnknown = resolveTokenHex('--color-status-unknown', darkTokens);

    // Shell badges on subtle header (>= 4.5:1 text)
    expect(getContrast(lBrandHover, lSubtle), 'Powershell badge on subtle light contrast >= 4.5:1').toBeGreaterThanOrEqual(4.5);
    expect(getContrast(dBrandHover, dSubtle), 'Powershell badge on subtle dark contrast >= 4.5:1').toBeGreaterThanOrEqual(4.5);
    expect(getContrast(lStatusOnline, lSubtle), 'Bash badge on subtle light contrast >= 4.5:1').toBeGreaterThanOrEqual(4.5);
    expect(getContrast(dStatusOnline, dSubtle), 'Bash badge on subtle dark contrast >= 4.5:1').toBeGreaterThanOrEqual(4.5);
    expect(getContrast(lTextPrimary, lSubtle), 'Cmd badge on subtle light contrast >= 4.5:1').toBeGreaterThanOrEqual(4.5);
    expect(getContrast(dTextPrimary, dSubtle), 'Cmd badge on subtle dark contrast >= 4.5:1').toBeGreaterThanOrEqual(4.5);

    // PTY auth badges on subtle header (>= 4.5:1 text)
    expect(getContrast(lStatusDegraded, lSubtle), 'Ticket bound badge on subtle light contrast >= 4.5:1').toBeGreaterThanOrEqual(4.5);
    expect(getContrast(dStatusDegraded, dSubtle), 'Ticket bound badge on subtle dark contrast >= 4.5:1').toBeGreaterThanOrEqual(4.5);
    expect(getContrast(lTextMuted, lSubtle), 'Awaiting command badge on subtle light contrast >= 4.5:1').toBeGreaterThanOrEqual(4.5);
    expect(getContrast(dTextMuted, dSubtle), 'Awaiting command badge on subtle dark contrast >= 4.5:1').toBeGreaterThanOrEqual(4.5);

    // Unknown fallback on subtle (>= 4.5:1 text)
    expect(getContrast(lStatusUnknown, lSubtle), 'Unknown fallback on subtle light contrast >= 4.5:1').toBeGreaterThanOrEqual(4.5);
    expect(getContrast(dStatusUnknown, dSubtle), 'Unknown fallback on subtle dark contrast >= 4.5:1').toBeGreaterThanOrEqual(4.5);

    // Terminal log text on dark terminal canvas background (--color-bg-canvas in dark theme: #0f172a)
    // Coordinator directive: "터미널 출력 영역은 실제 배경(어두운 터미널 배경 토큰)과 각 로그 레벨 색의 텍스트 4.5 대비"
    const terminalDarkBg = dCanvas; // #0f172a
    expect(getContrast(dTextPrimary, terminalDarkBg), 'Terminal stdout text on dark canvas contrast >= 4.5:1').toBeGreaterThanOrEqual(4.5);
    expect(getContrast(dStatusOffline, terminalDarkBg), 'Terminal stderr text on dark canvas contrast >= 4.5:1').toBeGreaterThanOrEqual(4.5);
    expect(getContrast(dStatusDegraded, terminalDarkBg), 'Terminal warning text on dark canvas contrast >= 4.5:1').toBeGreaterThanOrEqual(4.5);
    expect(getContrast(dStatusOnline, terminalDarkBg), 'Terminal success text on dark canvas contrast >= 4.5:1').toBeGreaterThanOrEqual(4.5);
    expect(getContrast(dTextMuted, terminalDarkBg), 'Terminal timestamp/meta text on dark canvas contrast >= 4.5:1').toBeGreaterThanOrEqual(4.5);

    // Interactive borders on surface / subtle (>= 3.0:1 non-text)
    expect(getContrast(lBorderStrong, lSurface), 'Form control border on surface light contrast >= 3.0:1').toBeGreaterThanOrEqual(3.0);
    expect(getContrast(dBorderStrong, dSurface), 'Form control border on surface dark contrast >= 3.0:1').toBeGreaterThanOrEqual(3.0);
    expect(getContrast(lBorderStrong, lSubtle), 'Form control border on subtle light contrast >= 3.0:1').toBeGreaterThanOrEqual(3.0);
    expect(getContrast(dBorderStrong, dSubtle), 'Form control border on subtle dark contrast >= 3.0:1').toBeGreaterThanOrEqual(3.0);
    expect(getContrast(lBorderSubtle, lSurface), 'Subtle border on surface light contrast >= 3.0:1').toBeGreaterThanOrEqual(3.0);
    expect(getContrast(dBorderSubtle, dSurface), 'Subtle border on surface dark contrast >= 3.0:1').toBeGreaterThanOrEqual(3.0);

    // 4. DOM Rendering Verification
    const container = document.createElement('div');
    document.body.appendChild(container);
    const root = createRoot(container);

    try {
      const mockNodes: NodeItem[] = [
        {
          id: 'nod_01',
          hostname: 'Node-01-WinMain',
          ipAddress: '192.168.45.101',
          os: 'windows',
          role: 'worker',
          status: 'online',
          schedulable: true,
          observationOnly: false,
          cpuCoresTotal: 16,
          memoryTotalBytes: 64 * 1024 * 1024 * 1024,
        },
        {
          id: 'nod_02',
          hostname: 'Node-02-LinuxSec',
          ipAddress: '192.168.45.102',
          os: 'linux',
          role: 'worker',
          status: 'online',
          schedulable: true,
          observationOnly: false,
          cpuCoresTotal: 8,
          memoryTotalBytes: 32 * 1024 * 1024 * 1024,
        },
        {
          id: 'nod_obs',
          hostname: 'Node-03-ObsOnly',
          ipAddress: '192.168.45.103',
          os: 'linux',
          role: 'observer',
          status: 'online',
          schedulable: false,
          observationOnly: true,
          cpuCoresTotal: 4,
          memoryTotalBytes: 16 * 1024 * 1024 * 1024,
        },
      ];

      await act(async () => {
        root.render(
          <TerminalSessionView
            nodes={mockNodes}
            defaultNodeId="nod_01"
            commandId=""
          />
        );
      });

      const sectionEl = container.querySelector('div[data-testid="terminal-session-view-container"]') as HTMLElement;
      expect(sectionEl, 'Terminal section must render').not.toBeNull();
      expect(sectionEl.style.backgroundColor).toBe('var(--color-bg-surface)');
      expect(sectionEl.style.color).toBe('var(--color-text-primary)');

      const tablistEl = container.querySelector('div[role="tablist"]') as HTMLElement;
      expect(tablistEl, 'Tablist must render').not.toBeNull();
      expect(tablistEl.style.backgroundColor).toBe('var(--color-bg-subtle)');
      expect(tablistEl.style.borderBottom || tablistEl.style.border).toContain('var(--color-border-subtle)');

      const activeTab = container.querySelector('div[role="tab"][aria-selected="true"]') as HTMLElement;
      expect(activeTab, 'Active tab must render').not.toBeNull();
      expect(activeTab.style.backgroundColor).toBe('var(--color-bg-surface)');
      expect(activeTab.style.borderTop || activeTab.style.border).toContain('var(--color-brand-primary)');
      expect(activeTab.style.color).toBe('var(--color-text-primary)');

      const inactiveTab = container.querySelector('div[role="tab"][aria-selected="false"]') as HTMLElement;
      expect(inactiveTab, 'Inactive tab must render').not.toBeNull();
      expect(inactiveTab.style.backgroundColor).toBe('transparent');
      expect(inactiveTab.style.color).toBe('var(--color-text-muted)');

      const newSessionSelect = container.querySelector('select[data-testid="new-session-select"]') as HTMLSelectElement;
      expect(newSessionSelect, 'New session select must render').not.toBeNull();
      expect(newSessionSelect.style.backgroundColor).toBe('var(--color-bg-surface)');
      expect(newSessionSelect.style.borderColor || newSessionSelect.style.border).toContain('var(--color-border-strong)');
      expect(newSessionSelect.style.outline || 'inherit').not.toMatch(/(none|0px|\b0\b)/);

      // Trigger observation node error alert
      await act(async () => {
        newSessionSelect.value = 'terminal:nod_obs';
        newSessionSelect.dispatchEvent(new Event('change', { bubbles: true }));
      });
      const errorAlert = container.querySelector('[data-testid="terminal-session-error-alert"]') as HTMLElement;
      expect(errorAlert, 'Observation error alert must render').not.toBeNull();
      expect(errorAlert.style.backgroundColor).toBe('var(--color-risk-l3-bg)');
      expect(errorAlert.style.color).toBe('var(--color-risk-l3-text)');
      expect(errorAlert.style.borderBottom || errorAlert.style.border).toContain('var(--color-risk-l3-border)');

      const activeNodeEl = container.querySelector('[data-testid="active-node-hostname"]') as HTMLElement;
      expect(activeNodeEl, 'Active node hostname must render').not.toBeNull();
      expect(activeNodeEl.style.color).toBe('var(--color-text-primary)');

      const shellBadge = container.querySelector('[data-testid="active-shell-type"]') as HTMLElement;
      expect(shellBadge, 'Shell badge must render').not.toBeNull();
      expect(shellBadge.style.color).toBe('var(--color-brand-hover)');
      expect(shellBadge.textContent).toBe('POWERSHELL');

      // Verify case variants, unknown values, and prototype keys render UNKNOWN (<raw>) with unknown color in DOM
      for (const fallbackShell of ['POWERSHELL', 'Bash', 'ZSH', 'CMD', 'unknown_custom_shell', 'toString']) {
        await act(async () => {
          root.render(
            <TerminalSessionView
              key={`term_fb_${fallbackShell}`}
              nodes={mockNodes}
              defaultNodeId="nod_01"
              commandId=""
              initialSessions={[
                {
                  id: `sess_test_${fallbackShell}`,
                  title: `Test ${fallbackShell}`,
                  nodeId: 'nod_01',
                  shellType: fallbackShell,
                  mode: 'terminal',
                  workspaceId: 'ws_test',
                },
              ]}
            />
          );
        });
        const fbShellBadge = container.querySelector('[data-testid="active-shell-type"]') as HTMLElement;
        expect(fbShellBadge.textContent).toBe(`UNKNOWN (${fallbackShell})`);
        expect(fbShellBadge.style.color).toBe('var(--color-status-unknown)');
      }

      const authBadge = container.querySelector('[data-testid="pty-ticket-badge"]') as HTMLElement;
      expect(authBadge, 'PTY auth badge must render').not.toBeNull();
      expect(authBadge.style.color).toBe('var(--color-text-muted)');

      const cmdInput = container.querySelector('input[data-testid="terminal-command-id-input"]') as HTMLInputElement;
      expect(cmdInput, 'Command ID input must render').not.toBeNull();
      expect(cmdInput.style.backgroundColor).toBe('var(--color-bg-surface)');
      expect(cmdInput.style.borderColor || cmdInput.style.border).toContain('var(--color-border-strong)');
      expect(cmdInput.style.outline || 'inherit').not.toMatch(/(none|0px|\b0\b)/);

      const switchBtn = container.querySelector('button[data-testid="switch-mode-btn"]') as HTMLButtonElement;
      expect(switchBtn, 'Switch mode button must render').not.toBeNull();
      expect(switchBtn.style.backgroundColor).toBe('var(--color-brand-subtle)');
      expect(switchBtn.style.borderColor || switchBtn.style.border).toContain('var(--color-brand-primary)');
      expect(switchBtn.style.color).toBe('var(--color-brand-hover)');
      expect(switchBtn.style.outline || 'inherit').not.toMatch(/(none|0px|\b0\b)/);

      // Empty state test
      await act(async () => {
        root.render(
          <TerminalSessionView
            nodes={[]}
          />
        );
      });

      const emptyContainer = container.querySelector('[data-testid="terminal-session-view-container"]') as HTMLElement;
      expect(emptyContainer, 'Empty container must render').not.toBeNull();
      expect(emptyContainer.style.backgroundColor).toBe('var(--color-bg-surface)');

      const emptyNotice = container.querySelector('[data-testid="terminal-empty-nodes-notice"]') as HTMLElement;
      expect(emptyNotice, 'Empty status notice must render').not.toBeNull();
      expect(emptyNotice.style.backgroundColor).toBe('var(--color-bg-subtle)');
      expect(emptyNotice.style.borderBottom || emptyNotice.style.border).toContain('var(--color-border-subtle)');
      expect(emptyNotice.style.color).toBe('var(--color-text-muted)');

      const warnSpan = container.querySelector('[data-testid="terminal-no-nodes-notice"] span') as HTMLElement;
      expect(warnSpan, 'Operator warning span must render').not.toBeNull();
      expect(warnSpan.style.color).toBe('var(--color-status-degraded)');
    } finally {
      act(() => {
        root.unmount();
      });
      container.remove();
    }

    // 5. Token Declaration Verification: all tokens used in TerminalSessionView.tsx exist in index.css
    const cssPath = path.resolve(__dirname, '../src/index.css');
    const cssContent = fs.readFileSync(cssPath, 'utf-8');
    const declaredCssTokens = new Set<string>();
    const tokenDeclRegex = /(--[a-z0-9-]+)\s*:\s*([^;]+);/g;
    let declMatch;
    while ((declMatch = tokenDeclRegex.exec(cssContent)) !== null) {
      declaredCssTokens.add(declMatch[1].trim());
    }

    const tsvPath = path.resolve(__dirname, '../src/features/desktop/TerminalSessionView.tsx');
    const tsvContent = fs.readFileSync(tsvPath, 'utf-8');
    const varMatches = tsvContent.match(/var\((--[a-z0-9-]+)/g) || [];
    for (const v of varMatches) {
      const tokenName = v.replace('var(', '');
      expect(declaredCssTokens.has(tokenName), `Token ${tokenName} used in TerminalSessionView.tsx must be declared in index.css`).toBe(true);
    }
  });

  // 9ad. [Card 280 / ACC-09] ConflictResolutionModal, DiffViewer, and GitCommitModal Contrast, Configs, Fail-Closed Contracts, & DOM Token Binding
  it('ACC-09 / Card 280: ConflictResolutionModal, DiffViewer, and GitCommitModal comply with WCAG 2.2 AA contrast, fail-closed contracts, and DOM token bindings', async () => {
    // 1. ConflictResolutionModal configs and fail-closed lookups
    expect(Object.keys(CONFLICT_STATUS_CONFIG).sort()).toEqual(['concurrency_conflict', 'etag_mismatch']);
    for (const status of ['etag_mismatch', 'concurrency_conflict'] as const) {
      expect(Object.hasOwn(CONFLICT_STATUS_CONFIG, status)).toBe(true);
      const cfg = getConflictStatusConfig(status);
      expect(cfg.label).toBeDefined();
      expect(cfg.colorVar).toMatch(/^var\(--color-(status-offline|status-degraded)\)$/);
      expect(cfg.bgVar).toMatch(/^var\(--color-(risk-l3-bg|bg-subtle)\)$/);
      expect(cfg.badgeFgVar).toBe('var(--color-brand-primary-fg)');
    }
    // Fail-closed fallback for conflict status
    const unknownConflict = getConflictStatusConfig('unknown_status');
    expect(unknownConflict.label).toBe('⚠️ UNKNOWN (unknown_status)');
    expect(unknownConflict.colorVar).toBe('var(--color-status-unknown)');
    for (const protoKey of ['toString', 'constructor', '__proto__', 'valueOf']) {
      expect(getConflictStatusConfig(protoKey).colorVar).toBe('var(--color-status-unknown)');
    }

    // CONFLICT_RESOLUTION_ACTION_CONFIG
    expect(Object.keys(CONFLICT_RESOLUTION_ACTION_CONFIG).sort()).toEqual(['accept_remote', 'keep_mine', 'merge']);
    for (const action of ['accept_remote', 'keep_mine', 'merge'] as const) {
      expect(Object.hasOwn(CONFLICT_RESOLUTION_ACTION_CONFIG, action)).toBe(true);
      const actCfg = getConflictResolutionActionConfig(action);
      expect(actCfg.label).toBeDefined();
    }
    expect(CONFLICT_RESOLUTION_ACTION_CONFIG.keep_mine.colorVar).toBe('var(--color-status-offline)');
    expect(CONFLICT_RESOLUTION_ACTION_CONFIG.keep_mine.borderColorVar).toBe('var(--color-status-offline)');
    expect(getConflictResolutionActionConfig('unknown_action').colorVar).toBe('var(--color-status-unknown)');
    for (const protoKey of ['toString', 'constructor', '__proto__', 'valueOf']) {
      expect(getConflictResolutionActionConfig(protoKey).colorVar).toBe('var(--color-status-unknown)');
    }

    // 2. DiffViewer DIFF_LINE_TYPE_CONFIG verification and contrast calculations
    expect(Object.keys(DIFF_LINE_TYPE_CONFIG).sort()).toEqual(['added', 'removed', 'unchanged']);
    for (const lineType of ['added', 'removed', 'unchanged'] as const) {
      expect(Object.hasOwn(DIFF_LINE_TYPE_CONFIG, lineType)).toBe(true);
      const cfg = getDiffLineTypeConfig(lineType);
      expect(cfg.label).toBeDefined();
    }

    // Dynamic contrast verification for diff line tokens
    const addedBgL = lightTokens['--color-diff-added-bg'];
    const addedTextL = lightTokens['--color-diff-added-text'];
    const addedBorderL = lightTokens['--color-diff-added-border'];
    const addedBgD = darkTokens['--color-diff-added-bg'];
    const addedTextD = darkTokens['--color-diff-added-text'];
    const addedBorderD = darkTokens['--color-diff-added-border'];

    const removedBgL = lightTokens['--color-diff-removed-bg'];
    const removedTextL = lightTokens['--color-diff-removed-text'];
    const removedBorderL = lightTokens['--color-diff-removed-border'];
    const removedBgD = darkTokens['--color-diff-removed-bg'];
    const removedTextD = darkTokens['--color-diff-removed-text'];
    const removedBorderD = darkTokens['--color-diff-removed-border'];

    expect(getContrast(addedTextL, addedBgL), 'Light added text on added bg >= 4.5:1').toBeGreaterThanOrEqual(4.5);
    expect(getContrast(addedTextD, addedBgD), 'Dark added text on added bg >= 4.5:1').toBeGreaterThanOrEqual(4.5);
    expect(getContrast(removedTextL, removedBgL), 'Light removed text on removed bg >= 4.5:1').toBeGreaterThanOrEqual(4.5);
    expect(getContrast(removedTextD, removedBgD), 'Dark removed text on removed bg >= 4.5:1').toBeGreaterThanOrEqual(4.5);

    expect(getContrast(addedBorderL, lightTokens['--color-bg-canvas']), 'Light added border >= 3.0:1').toBeGreaterThanOrEqual(3.0);
    expect(getContrast(addedBorderD, darkTokens['--color-bg-canvas']), 'Dark added border >= 3.0:1').toBeGreaterThanOrEqual(3.0);
    expect(getContrast(removedBorderL, lightTokens['--color-bg-canvas']), 'Light removed border >= 3.0:1').toBeGreaterThanOrEqual(3.0);
    expect(getContrast(removedBorderD, darkTokens['--color-bg-canvas']), 'Dark removed border >= 3.0:1').toBeGreaterThanOrEqual(3.0);

    const unknownLineType = getDiffLineTypeConfig('unknown_diff_line');
    expect(unknownLineType.label).toBe('UNKNOWN (unknown_diff_line)');
    expect(unknownLineType.colorVar).toBe('var(--color-status-unknown)');
    for (const protoKey of ['toString', 'constructor', '__proto__', 'valueOf']) {
      expect(getDiffLineTypeConfig(protoKey).colorVar).toBe('var(--color-status-unknown)');
    }

    // 3. GitCommitModal GIT_FILE_STATUS_CONFIG & GIT_STAGE_STATE_CONFIG
    expect(Object.keys(GIT_FILE_STATUS_CONFIG).sort()).toEqual(['clean', 'modified']);
    for (const fs of ['modified', 'clean'] as const) {
      expect(Object.hasOwn(GIT_FILE_STATUS_CONFIG, fs)).toBe(true);
      const cfg = getGitFileStatusConfig(fs);
      expect(cfg.badgeText).toBeDefined();
    }
    expect(GIT_FILE_STATUS_CONFIG.modified.colorVar).toBe('var(--color-status-degraded)');
    expect(GIT_FILE_STATUS_CONFIG.modified.badgeColorVar).toBe('var(--color-status-degraded)');
    expect(getGitFileStatusConfig('unknown_status').colorVar).toBe('var(--color-status-unknown)');
    for (const protoKey of ['toString', 'constructor', '__proto__', 'valueOf']) {
      expect(getGitFileStatusConfig(protoKey).colorVar).toBe('var(--color-status-unknown)');
    }

    expect(Object.keys(GIT_STAGE_STATE_CONFIG).sort()).toEqual(['staged', 'unstaged']);
    expect(GIT_STAGE_STATE_CONFIG.staged.bgVar).toBe('var(--color-brand-subtle)');
    expect(GIT_STAGE_STATE_CONFIG.unstaged.bgVar).toBe('transparent');
    expect(getGitStageStateConfig('staged').bgVar).toBe('var(--color-brand-subtle)');
    expect(getGitStageStateConfig('unstaged').bgVar).toBe('transparent');
    expect(getGitStageStateConfig('unknown').bgVar).toBe('transparent');
    for (const protoKey of ['toString', 'constructor', '__proto__', 'valueOf']) {
      expect(getGitStageStateConfig(protoKey).bgVar).toBe('transparent');
    }

    // 4. DOM Rendering and Token Binding
    const sampleDiff: FileDiffResult = {
      path: 'src/contracts/virtualFabric.ts',
      originalEtag: 'etag_base_1234567890abcdef',
      modifiedEtag: 'etag_mod_9876543210fedcba',
      additionsCount: 5,
      deletionsCount: 2,
      lines: [
        { type: 'unchanged', originalLineNumber: 1, modifiedLineNumber: 1, content: 'export interface VirtualMachine {' },
        { type: 'removed', originalLineNumber: 2, content: '  legacyState: string;' },
        { type: 'added', modifiedLineNumber: 2, content: '  contractState: NodeState;' },
      ],
    };

    // 4-a. ConflictResolutionModal DOM test
    const container = document.createElement('div');
    document.body.appendChild(container);
    const root = createRoot(container);

    await act(async () => {
      root.render(
        <ConflictResolutionModal
          filePath="src/contracts/virtualFabric.ts"
          diff={sampleDiff}
          onKeepMine={vi.fn()}
          onAcceptRemote={vi.fn()}
          onMerge={vi.fn()}
          onCancel={vi.fn()}
        />
      );
    });

    const conflictDialog = container.querySelector('[data-testid="conflict-resolution-dialog"]') as HTMLElement;
    expect(conflictDialog, 'Conflict dialog must render').not.toBeNull();
    expect(conflictDialog.style.backgroundColor).toBe('var(--color-bg-surface)');
    expect(conflictDialog.style.borderColor || conflictDialog.style.border).toContain('var(--color-status-offline)');
    expect(conflictDialog.style.boxShadow).toBe('var(--shadow-lg)');

    const conflictBackdrop = container.querySelector('[data-testid="conflict-resolution-backdrop"]') as HTMLElement;
    expect(conflictBackdrop.style.backgroundColor).toBe('var(--color-bg-backdrop)');

    const warningBanner = container.querySelector('[data-testid="conflict-warning-banner"]') as HTMLElement;
    expect(warningBanner.style.backgroundColor).toBe('var(--color-risk-l3-bg)');
    expect(warningBanner.style.borderBottom || warningBanner.style.border).toContain('var(--color-border-subtle)');

    const statusBadge = container.querySelector('[data-testid="conflict-status-badge"]') as HTMLElement;
    expect(statusBadge.style.backgroundColor).toBe('var(--color-status-offline)');
    expect(statusBadge.style.color).toBe('var(--color-brand-primary-fg)');

    const forceOverwriteBtn = container.querySelector('[data-testid="force-overwrite-btn"]') as HTMLElement;
    expect(forceOverwriteBtn.style.color).toBe('var(--color-status-offline)');
    expect(forceOverwriteBtn.style.borderColor || forceOverwriteBtn.style.border).toContain('var(--color-status-offline)');

    // 4-b. DiffViewer direct DOM test
    await act(async () => {
      root.render(
        <DiffViewer
          diff={sampleDiff}
          onClose={vi.fn()}
          onApply={vi.fn()}
          onRevert={vi.fn()}
        />
      );
    });

    const diffContainer = container.querySelector('[data-testid="diff-viewer-container"]') as HTMLElement;
    expect(diffContainer.style.backgroundColor).toBe('var(--color-bg-canvas)');
    expect(diffContainer.style.color).toBe('var(--color-text-secondary)');

    const additionsEl = container.querySelector('[data-testid="diff-additions-count"]') as HTMLElement;
    expect(additionsEl.style.color).toBe('var(--color-diff-added-text)');

    const deletionsEl = container.querySelector('[data-testid="diff-deletions-count"]') as HTMLElement;
    expect(deletionsEl.style.color).toBe('var(--color-diff-removed-text)');

    const addedLine = container.querySelector('[data-testid="diff-line-2"]') as HTMLElement;
    expect(addedLine.style.backgroundColor).toBe('var(--color-diff-added-bg)');
    expect(addedLine.style.borderLeft).toContain('var(--color-diff-added-border)');

    const removedLine = container.querySelector('[data-testid="diff-line-1"]') as HTMLElement;
    expect(removedLine.style.backgroundColor).toBe('var(--color-diff-removed-bg)');
    expect(removedLine.style.borderLeft).toContain('var(--color-diff-removed-border)');

    // 4-c. GitCommitModal DOM test
    const sampleFiles = [
      { path: 'src/main.ts', content: 'console.log("hello");', isDirty: true },
      { path: 'README.md', content: '# Documentation', isDirty: false },
    ];

    await act(async () => {
      root.render(
        <GitCommitModal
          files={sampleFiles}
          parentCommit={{ commitId: '0123456789abcdef0123456789abcdef01234567', parentCommitId: null, author: 'Gemini', message: 'init', timestamp: '2026-10-06T00:00:00Z', stagedFiles: ['src/main.ts'], treeHash: 'tree_123' }}
          onCommit={vi.fn()}
          onCancel={vi.fn()}
        />
      );
    });

    const gitDialog = container.querySelector('[data-testid="git-commit-dialog"]') as HTMLElement;
    expect(gitDialog.style.backgroundColor).toBe('var(--color-bg-surface)');
    expect(gitDialog.style.borderColor || gitDialog.style.border).toContain('var(--color-border-subtle)');
    expect(gitDialog.style.boxShadow).toBe('var(--shadow-lg)');

    const authorInput = container.querySelector('[data-testid="commit-author-input"]') as HTMLInputElement;
    expect(authorInput.style.backgroundColor).toBe('var(--color-bg-canvas)');
    expect(authorInput.style.borderColor || authorInput.style.border).toContain('var(--color-border-subtle)');

    const messageInput = container.querySelector('[data-testid="commit-message-input"]') as HTMLTextAreaElement;
    expect(messageInput.style.backgroundColor).toBe('var(--color-bg-canvas)');
    expect(messageInput.style.borderColor || messageInput.style.border).toContain('var(--color-border-subtle)');

    const reqIndicator = container.querySelector('[data-testid="commit-required-indicator"]') as HTMLElement;
    expect(reqIndicator.style.color).toBe('var(--color-status-offline)');

    const dirtyRow = container.querySelector('[data-testid="file-row-src_main_ts"]') as HTMLElement;
    expect(dirtyRow.style.backgroundColor).toBe('var(--color-brand-subtle)');

    const dirtyBadge = container.querySelector('[data-testid="file-badge-src_main_ts"]') as HTMLElement;
    expect(dirtyBadge.style.color).toBe('var(--color-status-degraded)');

    await act(async () => {
      root.unmount();
    });
    container.remove();
  });

  // 9ae. [Card 281 / ACC-09] MonacoWorkspaceEditor Contrast, Configs, Fail-Closed Contracts, & DOM Token Binding
  it('ACC-09 / Card 281: MonacoWorkspaceEditor complies with WCAG 2.2 AA contrast, fail-closed contracts, and DOM token bindings', async () => {
    // 1. WORKSPACE_TERMINAL_STATUS_CONFIG verification
    expect(Object.keys(WORKSPACE_TERMINAL_STATUS_CONFIG).sort()).toEqual(['connected', 'disconnected', 'reconnecting', 'recovered']);
    for (const status of ['connected', 'disconnected', 'reconnecting', 'recovered'] as const) {
      expect(Object.hasOwn(WORKSPACE_TERMINAL_STATUS_CONFIG, status)).toBe(true);
      const cfg = getWorkspaceTerminalStatusStyle(status);
      expect(cfg.label).toBeDefined();
      expect(cfg.colorVar).toMatch(/^var\(--color-(status-online|status-offline|status-degraded|brand-hover)\)$/);
      expect(cfg.bgVar).toMatch(/^var\(--color-(diff-added-bg|risk-l3-bg|bg-subtle|brand-subtle)\)$/);
      expect(cfg.borderVar).toMatch(/^var\(--color-(diff-added-border|risk-l3-border|status-degraded|brand-primary)\)$/);
    }

    // Dynamic contrast verification for terminal status tokens
    const connBgL = lightTokens['--color-diff-added-bg'];
    const connFgL = lightTokens['--color-status-online'];
    const connBorderL = lightTokens['--color-diff-added-border'];
    const connBgD = darkTokens['--color-diff-added-bg'];
    const connFgD = darkTokens['--color-status-online'];
    const connBorderD = darkTokens['--color-diff-added-border'];

    expect(getContrast(connFgL, connBgL), 'Light connected text on added bg >= 4.5:1').toBeGreaterThanOrEqual(4.5);
    expect(getContrast(connFgD, connBgD), 'Dark connected text on added bg >= 4.5:1').toBeGreaterThanOrEqual(4.5);
    expect(getContrast(connBorderL, connBgL), 'Light connected border on added bg >= 3.0:1').toBeGreaterThanOrEqual(3.0);
    expect(getContrast(connBorderD, connBgD), 'Dark connected border on added bg >= 3.0:1').toBeGreaterThanOrEqual(3.0);

    const recovBgL = lightTokens['--color-brand-subtle'];
    const recovFgL = lightTokens['--color-brand-hover'];
    const recovBorderL = lightTokens['--color-brand-primary'];
    const recovBgD = darkTokens['--color-brand-subtle'];
    const recovFgD = darkTokens['--color-brand-hover'];
    const recovBorderD = darkTokens['--color-brand-primary'];

    expect(getContrast(recovFgL, recovBgL), 'Light recovered text on brand subtle >= 4.5:1').toBeGreaterThanOrEqual(4.5);
    expect(getContrast(recovFgD, recovBgD), 'Dark recovered text on brand subtle >= 4.5:1').toBeGreaterThanOrEqual(4.5);
    expect(getContrast(recovBorderL, recovBgL), 'Light recovered border on brand subtle >= 3.0:1').toBeGreaterThanOrEqual(3.0);
    expect(getContrast(recovBorderD, recovBgD), 'Dark recovered border on brand subtle >= 3.0:1').toBeGreaterThanOrEqual(3.0);

    // Fail-closed fallback for unknown and prototype keys
    const unknownStatus = getWorkspaceTerminalStatusStyle('unknown_terminal_status');
    expect(unknownStatus.label).toBe('UNKNOWN (unknown_terminal_status)');
    expect(unknownStatus.colorVar).toBe('var(--color-status-unknown)');
    expect(unknownStatus.bgVar).toBe('var(--color-bg-subtle)');
    expect(unknownStatus.borderVar).toBe('var(--color-border-subtle)');
    for (const protoKey of ['toString', 'constructor', '__proto__', 'valueOf']) {
      const protoStyle = getWorkspaceTerminalStatusStyle(protoKey);
      expect(protoStyle.colorVar).toBe('var(--color-status-unknown)');
      expect(protoStyle.label).toBe(`UNKNOWN (${protoKey})`);
    }

    // 2. DOM Rendering & Token Binding
    const container = document.createElement('div');
    document.body.appendChild(container);
    const root = createRoot(container);

    await act(async () => {
      root.render(
        <MonacoWorkspaceEditor
          workspaceId="wsp_test_dom"
          projectId="proj_1"
          runId="run_1"
          checkoutId="chk_1"
        />
      );
    });

    const unexposedNotice = container.querySelector('[data-testid="editor-unexposed-notice"]') as HTMLElement;
    expect(unexposedNotice).toBeDefined();
    expect(unexposedNotice.style.backgroundColor).toBe('var(--color-diff-added-bg)');
    expect(unexposedNotice.style.color).toBe('var(--color-status-online)');
    expect(unexposedNotice.style.borderBottom || unexposedNotice.style.border).toContain('var(--color-diff-added-border)');

    const terminalBadge = container.querySelector('[data-testid="editor-terminal-status-badge"]') as HTMLElement;
    expect(terminalBadge).toBeDefined();
    expect(terminalBadge.textContent).toBe('CONNECTED');
    expect(terminalBadge.style.backgroundColor).toBe('var(--color-diff-added-bg)');
    expect(terminalBadge.style.color).toBe('var(--color-status-online)');
    expect(terminalBadge.style.borderColor || terminalBadge.style.border).toContain('var(--color-diff-added-border)');

    const mockNotice = container.querySelector('[data-testid="editor-terminal-mock-notice"]') as HTMLElement;
    expect(mockNotice).toBeDefined();
    expect(mockNotice.style.color).toBe('var(--color-status-degraded)');
    expect(mockNotice.style.backgroundColor).toBe('var(--color-bg-subtle)');
    expect(mockNotice.style.borderColor || mockNotice.style.border).toContain('var(--color-status-degraded)');

    await act(async () => {
      root.unmount();
    });
    container.remove();
  });

  // 9af. [Card 282 / ACC-09] WebTerminal Contrast, Configs, Fail-Closed Contracts, & DOM Token Binding
  it('ACC-09 / Card 282: WebTerminal complies with WCAG 2.2 AA contrast, fail-closed contracts, and DOM token bindings', async () => {
    // 1. WEB_TERMINAL_CONNECTION_STATUS_CONFIG verification
    expect(Object.keys(WEB_TERMINAL_CONNECTION_STATUS_CONFIG).sort()).toEqual(['connected', 'connecting', 'disconnected', 'error']);
    for (const status of ['connected', 'connecting', 'disconnected', 'error'] as const) {
      expect(Object.hasOwn(WEB_TERMINAL_CONNECTION_STATUS_CONFIG, status)).toBe(true);
      const cfg = getWebTerminalConnectionStatusConfig(status);
      expect(cfg.label).toBeDefined();
      expect(cfg.dotColor).toMatch(/^var\(--color-(status-online|status-degraded|text-muted|status-offline)\)$/);
      expect(cfg.promptColor).toMatch(/^var\(--color-(brand-primary|status-degraded|text-muted|status-offline)\)$/);
      expect(cfg.borderVar).toMatch(/^var\(--color-(status-online|status-degraded|border-subtle|status-offline)\)$/);
      expect(cfg.bgVar).toMatch(/^var\(--color-(diff-added-bg|bg-subtle|risk-l3-bg)\)$/);
    }

    // Pin connected terminal status tokens explicitly to kill subtle token collisions (M4)
    const connCfg = getWebTerminalConnectionStatusConfig('connected');
    expect(connCfg.bgVar, 'Connected bgVar must strictly bind to diff-added-bg').toBe('var(--color-diff-added-bg)');
    expect(connCfg.dotColor, 'Connected dotColor must strictly bind to status-online').toBe('var(--color-status-online)');
    expect(connCfg.textColor, 'Connected textColor must strictly bind to status-online').toBe('var(--color-status-online)');
    expect(connCfg.promptColor, 'Connected promptColor must strictly bind to brand-primary').toBe('var(--color-brand-primary)');
    expect(connCfg.borderVar, 'Connected borderVar must strictly bind to status-online').toBe('var(--color-status-online)');

    // Dynamic contrast verification for terminal status tokens
    const connBgL = lightTokens['--color-diff-added-bg'];
    const connFgL = lightTokens['--color-status-online'];
    const connBorderL = lightTokens['--color-diff-added-border'];
    const connBgD = darkTokens['--color-diff-added-bg'];
    const connFgD = darkTokens['--color-status-online'];
    const connBorderD = darkTokens['--color-diff-added-border'];

    expect(getContrast(connFgL, connBgL), 'Light connected text on added bg >= 4.5:1').toBeGreaterThanOrEqual(4.5);
    expect(getContrast(connFgD, connBgD), 'Dark connected text on added bg >= 4.5:1').toBeGreaterThanOrEqual(4.5);
    expect(getContrast(connBorderL, connBgL), 'Light connected border on added bg >= 3.0:1').toBeGreaterThanOrEqual(3.0);
    expect(getContrast(connBorderD, connBgD), 'Dark connected border on added bg >= 3.0:1').toBeGreaterThanOrEqual(3.0);

    const degBgL = lightTokens['--color-bg-subtle'];
    const degFgL = lightTokens['--color-status-degraded'];
    const degBgD = darkTokens['--color-bg-subtle'];
    const degFgD = darkTokens['--color-status-degraded'];

    expect(getContrast(degFgL, degBgL), 'Light degraded text on subtle bg >= 4.5:1').toBeGreaterThanOrEqual(4.5);
    expect(getContrast(degFgD, degBgD), 'Dark degraded text on subtle bg >= 4.5:1').toBeGreaterThanOrEqual(4.5);

    const offBgL = lightTokens['--color-risk-l3-bg'];
    const offFgL = lightTokens['--color-status-offline'];
    const offBorderL = lightTokens['--color-risk-l3-border'];
    const offBgD = darkTokens['--color-risk-l3-bg'];
    const offFgD = darkTokens['--color-status-offline'];
    const offBorderD = darkTokens['--color-risk-l3-border'];

    expect(getContrast(offFgL, offBgL), 'Light offline text on risk-l3 bg >= 4.5:1').toBeGreaterThanOrEqual(4.5);
    expect(getContrast(offFgD, offBgD), 'Dark offline text on risk-l3 bg >= 4.5:1').toBeGreaterThanOrEqual(4.5);
    expect(getContrast(offBorderL, offBgL), 'Light offline border on risk-l3 bg >= 3.0:1').toBeGreaterThanOrEqual(3.0);
    expect(getContrast(offBorderD, offBgD), 'Dark offline border on risk-l3 bg >= 3.0:1').toBeGreaterThanOrEqual(3.0);

    // Fail-closed fallback for unknown and prototype keys
    const unknownStatus = getWebTerminalConnectionStatusConfig('unknown_status');
    expect(unknownStatus.label).toBe('UNKNOWN (unknown_status)');
    expect(unknownStatus.dotColor).toBe('var(--color-status-unknown)');
    expect(unknownStatus.bgVar).toBe('var(--color-bg-subtle)');
    expect(unknownStatus.borderVar).toBe('var(--color-status-unknown)');
    for (const protoKey of ['toString', 'constructor', '__proto__', 'valueOf']) {
      const protoStyle = getWebTerminalConnectionStatusConfig(protoKey);
      expect(protoStyle.dotColor).toBe('var(--color-status-unknown)');
      expect(protoStyle.label).toBe(`UNKNOWN (${protoKey})`);
    }

    // Null and undefined fall back to clean UNKNOWN without raw string
    expect(getWebTerminalConnectionStatusConfig(null).label).toBe('UNKNOWN');
    expect(getWebTerminalConnectionStatusConfig(undefined).label).toBe('UNKNOWN');

    // 2. DOM Rendering & Token Binding
    const container = document.createElement('div');
    document.body.appendChild(container);
    const root = createRoot(container);

    await act(async () => {
      root.render(
        <WebTerminal
          workspaceId="wsp_test_term"
          sessionId="sess_1"
          commandId="cmd_authorized_1"
        />
      );
    });

    const termContainer = container.querySelector('[data-testid="web-terminal-container"]') as HTMLElement;
    expect(termContainer).toBeDefined();
    expect(termContainer.style.backgroundColor).toBe('var(--color-bg-canvas)');
    expect(termContainer.style.color).toBe('var(--color-text-primary)');
    expect(termContainer.style.borderColor || termContainer.style.border).toContain('var(--color-border-subtle)');

    const dot = container.querySelector('[data-testid="connection-status-dot"]') as HTMLElement;
    expect(dot).toBeDefined();
    expect(dot.style.backgroundColor).toBe('var(--color-status-offline)');

    const reconnectBtn = container.querySelector('[data-testid="terminal-reconnect-btn"]') as HTMLElement;
    expect(reconnectBtn).toBeDefined();

    const a11yBtn = container.querySelector('[data-testid="terminal-toggle-a11y-btn"]') as HTMLElement;
    expect(a11yBtn).toBeDefined();
    expect(a11yBtn.style.color).toBe('var(--color-text-primary)');

    // Render with missing command to verify warning notice banner
    await act(async () => {
      root.render(
        <WebTerminal
          workspaceId="wsp_test_term"
          sessionId="sess_1"
          commandId=""
        />
      );
    });

    const cmdNotice = container.querySelector('[data-testid="terminal-command-required-notice"]') as HTMLElement;
    expect(cmdNotice).toBeDefined();
    expect(cmdNotice.style.backgroundColor).toBe('var(--color-bg-subtle)');
    expect(cmdNotice.style.color).toBe('var(--color-status-degraded)');
    expect(cmdNotice.style.borderBottom || cmdNotice.style.border).toContain('var(--color-status-degraded)');

    await act(async () => {
      root.unmount();
    });
    container.remove();
  });





  // 9j-2. [Card 215 & Card 218 & Card 220 & Card 226 & Card 228 & Card 230 & Card 235 & Card 245 & Card 248 & Card 270 & Card 271 & Card 273 & Card 274 & Card 275 & Card 276 & Card 277 & Card 278 & Card 279 / ACC-09] Dynamic AST Style-Pair Contrast Calculator & Strict Coverage Ratchet
  it('ACC-09 / Card 215 & Card 218 & Card 220 & Card 226 & Card 228 & Card 230 & Card 235 & Card 245 & Card 248 & Card 270 & Card 271 & Card 273 & Card 274 & Card 275 & Card 276 & Card 277 & Card 278 & Card 279 & Card 280 & Card 281: Style objects maintain valid contrast pairings and reject 1:1 collisions and defective combinations', () => {
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
            } else {
              const clean = text.replace(/['"`]/g, '').trim().toLowerCase();
              const allowedNonTokens = ['transparent', 'inherit', 'currentcolor', 'none', 'initial', 'unset'];
              const namedColors = ['white', 'black', 'red', 'green', 'blue', 'gray', 'yellow', 'orange', 'purple', 'lightgray', 'darkgray', 'silver', 'cyan', 'magenta', 'lime', 'maroon', 'navy', 'olive', 'teal', 'aqua', 'fuchsia'];
              if (clean.startsWith('#') || clean.startsWith('rgb') || clean.startsWith('hsl') || namedColors.includes(clean) || (!allowedNonTokens.includes(clean) && /^[a-z]+$/.test(clean))) {
                const { line } = sf.getLineAndCharacterOfPosition(n.getStart(sf));
                violations.push(`L${line + 1}: Raw color literal detected instead of design token: ${text}`);
              } else {
                const subTokens = clean.split(/\s+/);
                for (const tok of subTokens) {
                  if (tok.startsWith('#') || tok.startsWith('rgb') || tok.startsWith('hsl') || namedColors.includes(tok)) {
                    const { line } = sf.getLineAndCharacterOfPosition(n.getStart(sf));
                    violations.push(`L${line + 1}: Raw color literal detected in shorthand expression instead of design token: ${text}`);
                    break;
                  }
                }
              }
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

      function checkOutlineProp(p: ts.ObjectLiteralElementLike) {
        if (!ts.isPropertyAssignment(p)) return;
        const name = p.name.getText(sf);
        if (name === 'outline') {
          let initExpr: ts.Expression = p.initializer;
          while (ts.isAsExpression(initExpr) || ts.isSatisfiesExpression(initExpr) || ts.isParenthesizedExpression(initExpr)) {
            initExpr = initExpr.expression;
          }
          const outlineVal = initExpr.getText(sf).replace(/['"`]/g, '').trim().toLowerCase();
          if (outlineVal === 'none' || outlineVal === '0' || outlineVal === '0px') {
            const { line } = sf.getLineAndCharacterOfPosition(p.getStart(sf));
            violations.push(`L${line + 1}: Inline outline: ${outlineVal} suppressing focus ring`);
          }
        }
        if (name === 'outlineWidth') {
          let initExpr: ts.Expression = p.initializer;
          while (ts.isAsExpression(initExpr) || ts.isSatisfiesExpression(initExpr) || ts.isParenthesizedExpression(initExpr)) {
            initExpr = initExpr.expression;
          }
          const widthVal = initExpr.getText(sf).replace(/['"`]/g, '').trim().toLowerCase();
          if (widthVal === '0' || widthVal === '0px') {
            const { line } = sf.getLineAndCharacterOfPosition(p.getStart(sf));
            violations.push(`L${line + 1}: Inline outlineWidth: 0 suppressing focus ring`);
          }
        }
        if (name === 'outlineStyle') {
          let initExpr: ts.Expression = p.initializer;
          while (ts.isAsExpression(initExpr) || ts.isSatisfiesExpression(initExpr) || ts.isParenthesizedExpression(initExpr)) {
            initExpr = initExpr.expression;
          }
          const styleVal = initExpr.getText(sf).replace(/['"`]/g, '').trim().toLowerCase();
          if (styleVal === 'none') {
            const { line } = sf.getLineAndCharacterOfPosition(p.getStart(sf));
            violations.push(`L${line + 1}: Inline outlineStyle: none suppressing focus ring`);
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
          const styleObjs: ts.ObjectLiteralExpression[] = [];

          function extractStyleObjects(expr: ts.Expression): ts.ObjectLiteralExpression[] {
            let current: ts.Expression = expr;
            while (ts.isAsExpression(current) || ts.isSatisfiesExpression(current) || ts.isParenthesizedExpression(current)) {
              current = current.expression;
            }
            if (ts.isObjectLiteralExpression(current)) {
              return [current];
            }
            if (ts.isConditionalExpression(current)) {
              return [...extractStyleObjects(current.whenTrue), ...extractStyleObjects(current.whenFalse)];
            }
            if (ts.isBinaryExpression(current) && current.operatorToken.kind === ts.SyntaxKind.BarBarToken) {
              return [...extractStyleObjects(current.left), ...extractStyleObjects(current.right)];
            }
            if (ts.isBinaryExpression(current) && current.operatorToken.kind === ts.SyntaxKind.AmpersandAmpersandToken) {
              return extractStyleObjects(current.right);
            }
            return [];
          }

          for (const attr of attrs) {
            if (ts.isJsxAttribute(attr) && attr.name.text === 'style') {
              totalStyleAttrs++;
              if (attr.initializer && ts.isJsxExpression(attr.initializer) && attr.initializer.expression) {
                styleObjs.push(...extractStyleObjects(attr.initializer.expression));
              }
            }
          }

          for (const styleObj of styleObjs) {
            let bgNode: ts.Expression | null = null;
            let fgNode: ts.Expression | null = null;
            let borderNode: ts.Expression | null = null;
            let opacityNode: ts.Expression | null = null;

            for (const p of styleObj.properties) {
              if (ts.isPropertyAssignment(p)) {
                const name = p.name.getText(sf);
                if (name === 'backgroundColor' || name === 'background') bgNode = p.initializer;
                if (name === 'color') fgNode = p.initializer;
                if (name === 'border' || name === 'borderColor' || name === 'borderBottom' || name === 'borderLeft' || name === 'borderTop') borderNode = p.initializer;
                if (name === 'opacity') opacityNode = p.initializer;
                checkOutlineProp(p);
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
        if (ts.isVariableDeclaration(node)) {
          let varInit = node.initializer;
          while (varInit && (ts.isAsExpression(varInit) || ts.isSatisfiesExpression(varInit) || ts.isParenthesizedExpression(varInit))) {
            varInit = varInit.expression;
          }
          if (varInit && ts.isObjectLiteralExpression(varInit)) {
            for (const p of varInit.properties) {
              checkOutlineProp(p);
            }
          }
        }

        if (ts.isVariableDeclaration(node) && (node.name.getText(sf) === 'RUN_STATE_CONFIG' || node.name.getText(sf) === 'NODE_HEALTH_CONFIG' || node.name.getText(sf) === 'SLO_STATUS_CONFIG' || node.name.getText(sf) === 'AUDIT_STATUS_CONFIG' || node.name.getText(sf) === 'CANDIDATE_STATUS_CONFIG' || node.name.getText(sf) === 'REPLICA_STATUS_CONFIG' || node.name.getText(sf) === 'MODEL_AVAILABILITY_CONFIG' || node.name.getText(sf) === 'PLAN_FEASIBILITY_CONFIG' || node.name.getText(sf) === 'NODE_ELIGIBILITY_CONFIG' || node.name.getText(sf) === 'AGENT_RUN_STATUS_CONFIG' || node.name.getText(sf) === 'NOTIFICATION_LEVEL_CONFIG' || node.name.getText(sf) === 'DISCOVERY_CANDIDATE_STATE_CONFIG' || node.name.getText(sf) === 'APPROVAL_STATUS_CONFIG' || node.name.getText(sf) === 'NODE_STATUS_CONFIG' || node.name.getText(sf) === 'WORKSPACE_STATUS_CONFIG' || node.name.getText(sf) === 'RISK_CONFIG' || node.name.getText(sf) === 'EVIDENCE_INTEGRITY_CONFIG' || node.name.getText(sf) === 'WINDOW_CONTROL_CONFIG' || node.name.getText(sf) === 'TERMINAL_SHELL_CONFIG' || node.name.getText(sf) === 'PTY_AUTH_STATUS_CONFIG' || node.name.getText(sf) === 'DIFF_LINE_TYPE_CONFIG' || node.name.getText(sf) === 'CONFLICT_STATUS_CONFIG' || node.name.getText(sf) === 'CONFLICT_RESOLUTION_ACTION_CONFIG' || node.name.getText(sf) === 'GIT_FILE_STATUS_CONFIG' || node.name.getText(sf) === 'GIT_STAGE_STATE_CONFIG' || node.name.getText(sf) === 'WORKSPACE_TERMINAL_STATUS_CONFIG' || node.name.getText(sf) === 'WEB_TERMINAL_CONNECTION_STATUS_CONFIG') && node.initializer) {
          const varName = node.name.getText(sf);
          let init = node.initializer;
          while (ts.isAsExpression(init) || ts.isSatisfiesExpression(init) || ts.isParenthesizedExpression(init)) {
            init = init.expression;
          }
          if (init && ts.isObjectLiteralExpression(init)) {
            for (const prop of init.properties) {
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
                      if (pName === 'bg' || pName === 'bgVar') bgToken = m[1];
                      if (pName === 'color' || pName === 'colorVar') fgToken = m[1];
                      if (pName === 'border' || pName === 'borderVar' || pName === 'borderColorVar') borderToken = m[1];
                    }
                  }
                }
                if (varName === 'NODE_STATUS_CONFIG' && !bgToken) {
                  bgToken = '--color-bg-canvas';
                }
                if ((varName === 'TERMINAL_SHELL_CONFIG' || varName === 'PTY_AUTH_STATUS_CONFIG' || varName === 'GIT_FILE_STATUS_CONFIG' ) && !bgToken) {
                  bgToken = '--color-bg-subtle';
                }
                if (varName === 'DIFF_LINE_TYPE_CONFIG' && !bgToken) {
                  bgToken = '--color-bg-canvas';
                }
                if (varName === 'RISK_CONFIG' && !borderToken && fgToken) {
                  borderToken = fgToken;
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

    const recoveryStats = analyzeFile('features/recovery/DistributedRecoveryView.tsx');
    expect(recoveryStats.totalStyleAttrs, 'Total style attributes in DistributedRecoveryView must be exactly 68').toBe(68);
    expect(recoveryStats.checkedObjects, 'Explicit style objects in DistributedRecoveryView must be exactly 8').toBe(8);
    expect(recoveryStats.checkedPairs, 'Evaluated pairs in DistributedRecoveryView must be exactly 47').toBe(47);
    expect(recoveryStats.unboundColorObjects, 'Unbound color objects in DistributedRecoveryView must be exactly 34').toBe(34);
    expect(recoveryStats.coveredColorObjects, 'Total covered color objects in DistributedRecoveryView must be exactly 42').toBe(42);
    expect(recoveryStats.checkedBorderObjects, 'Border objects in DistributedRecoveryView must be exactly 20').toBe(20);
    expect(recoveryStats.checkedBorderPairs, 'Border pairs in DistributedRecoveryView must be exactly 23').toBe(23);
    expect(recoveryStats.violations, `DistributedRecoveryView violations:\n${recoveryStats.violations.join('\n')}`).toEqual([]);

    const releaseStats = analyzeFile('features/release/ReleaseCandidateView.tsx');
    expect(releaseStats.totalStyleAttrs, 'Total style attributes in ReleaseCandidateView must be exactly 80').toBe(80);
    expect(releaseStats.checkedObjects, 'Explicit style objects in ReleaseCandidateView must be exactly 9').toBe(9);
    expect(releaseStats.checkedPairs, 'Evaluated pairs in ReleaseCandidateView must be exactly 52').toBe(52);
    expect(releaseStats.unboundColorObjects, 'Unbound color objects in ReleaseCandidateView must be exactly 35').toBe(35);
    expect(releaseStats.coveredColorObjects, 'Total covered color objects in ReleaseCandidateView must be exactly 44').toBe(44);
    expect(releaseStats.checkedBorderObjects, 'Border objects in ReleaseCandidateView must be exactly 21').toBe(21);
    expect(releaseStats.checkedBorderPairs, 'Border pairs in ReleaseCandidateView must be exactly 22').toBe(22);
    expect(releaseStats.violations, `ReleaseCandidateView violations:\n${releaseStats.violations.join('\n')}`).toEqual([]);

    const modelStudioStats = analyzeFile('features/desktop/ModelStudioView.tsx');
    expect(modelStudioStats.totalStyleAttrs, 'Total style attributes in ModelStudioView must be exactly 83').toBe(83);
    expect(modelStudioStats.checkedObjects, 'Explicit style objects in ModelStudioView must be exactly 21').toBe(21);
    expect(modelStudioStats.checkedPairs, 'Evaluated pairs in ModelStudioView must be exactly 39').toBe(39);
    expect(modelStudioStats.unboundColorObjects, 'Unbound color objects in ModelStudioView must be exactly 18').toBe(18);
    expect(modelStudioStats.coveredColorObjects, 'Total covered color objects in ModelStudioView must be exactly 39').toBe(39);
    expect(modelStudioStats.checkedBorderObjects, 'Border objects in ModelStudioView must be exactly 26').toBe(26);
    expect(modelStudioStats.checkedBorderPairs, 'Border pairs in ModelStudioView must be exactly 26').toBe(26);
    expect(modelStudioStats.violations, `ModelStudioView violations:\n${modelStudioStats.violations.join('\n')}`).toEqual([]);

    const nlRunStats = analyzeFile('features/agent/NaturalLanguageRunView.tsx');
    expect(nlRunStats.totalStyleAttrs, 'Total style attributes in NaturalLanguageRunView must be exactly 56').toBe(56);
    expect(nlRunStats.checkedObjects, 'Explicit style objects in NaturalLanguageRunView must be exactly 13').toBe(13);
    expect(nlRunStats.checkedPairs, 'Evaluated pairs in NaturalLanguageRunView must be exactly 45').toBe(45);
    expect(nlRunStats.unboundColorObjects, 'Unbound color objects in NaturalLanguageRunView must be exactly 27').toBe(27);
    expect(nlRunStats.coveredColorObjects, 'Total covered color objects in NaturalLanguageRunView must be exactly 40').toBe(40);
    expect(nlRunStats.checkedBorderObjects, 'Border objects in NaturalLanguageRunView must be exactly 20').toBe(20);
    expect(nlRunStats.checkedBorderPairs, 'Border pairs in NaturalLanguageRunView must be exactly 23').toBe(23);
    expect(nlRunStats.violations, `NaturalLanguageRunView violations:\n${nlRunStats.violations.join('\n')}`).toEqual([]);

    const desktopShellStats = analyzeFile('features/desktop/DesktopShell.tsx');
    expect(desktopShellStats.totalStyleAttrs, 'Total style attributes in DesktopShell must be exactly 50').toBe(50);
    expect(desktopShellStats.checkedObjects, 'Explicit style objects in DesktopShell must be exactly 8').toBe(8);
    expect(desktopShellStats.checkedPairs, 'Evaluated pairs in DesktopShell must be exactly 22').toBe(22);
    expect(desktopShellStats.unboundColorObjects, 'Unbound color objects in DesktopShell must be exactly 14').toBe(14);
    expect(desktopShellStats.coveredColorObjects, 'Total covered color objects in DesktopShell must be exactly 22').toBe(22);
    expect(desktopShellStats.checkedBorderObjects, 'Border objects in DesktopShell must be exactly 14').toBe(14);
    expect(desktopShellStats.checkedBorderPairs, 'Border pairs in DesktopShell must be exactly 15').toBe(15);
    expect(desktopShellStats.violations, `DesktopShell violations:\n${desktopShellStats.violations.join('\n')}`).toEqual([]);

    const placementStats = analyzeFile('features/placement/PlacementSimulator.tsx');
    expect(placementStats.totalStyleAttrs, 'Total style attributes in PlacementSimulator must be exactly 78').toBe(78);
    expect(placementStats.checkedObjects, 'Explicit style objects in PlacementSimulator must be exactly 16').toBe(16);
    expect(placementStats.checkedPairs, 'Evaluated pairs in PlacementSimulator must be exactly 41').toBe(41);
    expect(placementStats.unboundColorObjects, 'Unbound color objects in PlacementSimulator must be exactly 23').toBe(23);
    expect(placementStats.coveredColorObjects, 'Total covered color objects in PlacementSimulator must be exactly 39').toBe(39);
    expect(placementStats.checkedBorderObjects, 'Border objects in PlacementSimulator must be exactly 21').toBe(21);
    expect(placementStats.checkedBorderPairs, 'Border pairs in PlacementSimulator must be exactly 23').toBe(23);
    expect(placementStats.violations, `PlacementSimulator violations:\n${placementStats.violations.join('\n')}`).toEqual([]);

    const approvalStats = analyzeFile('features/approvals/ApprovalCenter.tsx');
    expect(approvalStats.totalStyleAttrs, 'Total style attributes in ApprovalCenter must be exactly 42').toBe(42);
    expect(approvalStats.checkedObjects, 'Explicit style objects in ApprovalCenter must be exactly 10').toBe(10);
    expect(approvalStats.checkedPairs, 'Evaluated pairs in ApprovalCenter must be exactly 24').toBe(24);
    expect(approvalStats.unboundColorObjects, 'Unbound color objects in ApprovalCenter must be exactly 13').toBe(13);
    expect(approvalStats.coveredColorObjects, 'Total covered color objects in ApprovalCenter must be exactly 23').toBe(23);
    expect(approvalStats.checkedBorderObjects, 'Border objects in ApprovalCenter must be exactly 18').toBe(18);
    expect(approvalStats.checkedBorderPairs, 'Border pairs in ApprovalCenter must be exactly 19').toBe(19);
    expect(approvalStats.violations, `ApprovalCenter violations:\n${approvalStats.violations.join('\n')}`).toEqual([]);

    const clusterStats = analyzeFile('features/dashboard/ClusterOverview.tsx');
    expect(clusterStats.violations, `ClusterOverview violations:\n${clusterStats.violations.join('\n')}`).toEqual([]);
    expect(clusterStats.totalStyleAttrs, 'Total style attributes in ClusterOverview must be exactly 76').toBe(76);
    expect(clusterStats.checkedObjects, 'Explicit style objects in ClusterOverview must be exactly 15').toBe(15);
    expect(clusterStats.checkedPairs, 'Evaluated pairs in ClusterOverview must be exactly 38').toBe(38);
    expect(clusterStats.unboundColorObjects, 'Unbound color objects in ClusterOverview must be exactly 23').toBe(23);
    expect(clusterStats.coveredColorObjects, 'Total covered color objects in ClusterOverview must be exactly 38').toBe(38);
    expect(clusterStats.checkedBorderObjects, 'Border objects in ClusterOverview must be exactly 16').toBe(16);
    expect(clusterStats.checkedBorderPairs, 'Border pairs in ClusterOverview must be exactly 16').toBe(16);

    const workspaceListStats = analyzeFile('features/workspaces/WorkspaceList.tsx');
    expect(workspaceListStats.violations, `WorkspaceList violations:\n${workspaceListStats.violations.join('\n')}`).toEqual([]);
    expect(workspaceListStats.totalStyleAttrs, 'Total style attributes in WorkspaceList must be exactly 37').toBe(37);
    expect(workspaceListStats.checkedObjects, 'Explicit style objects in WorkspaceList must be exactly 8').toBe(8);
    expect(workspaceListStats.checkedPairs, 'Evaluated pairs in WorkspaceList must be exactly 20').toBe(20);
    expect(workspaceListStats.unboundColorObjects, 'Unbound color objects in WorkspaceList must be exactly 12').toBe(12);
    expect(workspaceListStats.coveredColorObjects, 'Total covered color objects in WorkspaceList must be exactly 20').toBe(20);
    expect(workspaceListStats.checkedBorderObjects, 'Border objects in WorkspaceList must be exactly 11').toBe(11);
    expect(workspaceListStats.checkedBorderPairs, 'Border pairs in WorkspaceList must be exactly 11').toBe(11);

    const nodeListStats = analyzeFile('features/nodes/NodeList.tsx');
    expect(nodeListStats.violations, `NodeList violations:\n${nodeListStats.violations.join('\n')}`).toEqual([]);
    expect(nodeListStats.totalStyleAttrs, 'Total style attributes in NodeList must be exactly 53').toBe(53);
    expect(nodeListStats.checkedObjects, 'Explicit style objects in NodeList must be exactly 7').toBe(7);
    expect(nodeListStats.checkedPairs, 'Evaluated pairs in NodeList must be exactly 26').toBe(26);
    expect(nodeListStats.unboundColorObjects, 'Unbound color objects in NodeList must be exactly 14').toBe(14);
    expect(nodeListStats.coveredColorObjects, 'Total covered color objects in NodeList must be exactly 21').toBe(21);
    expect(nodeListStats.checkedBorderObjects, 'Border objects in NodeList must be exactly 11').toBe(11);
    expect(nodeListStats.checkedBorderPairs, 'Border pairs in NodeList must be exactly 13').toBe(13);

    const buttonStats = analyzeFile('shared/ui/Button.tsx');
    expect(buttonStats.violations, `Button violations:\n${buttonStats.violations.join('\n')}`).toEqual([]);
    expect(buttonStats.totalStyleAttrs, 'Total style attributes in Button must be exactly 3').toBe(3);
    expect(buttonStats.checkedObjects, 'Explicit style objects in Button must be exactly 0').toBe(0);
    expect(buttonStats.checkedPairs, 'Evaluated pairs in Button must be exactly 0').toBe(0);
    expect(buttonStats.unboundColorObjects, 'Unbound color objects in Button must be exactly 0').toBe(0);
    expect(buttonStats.coveredColorObjects, 'Total covered color objects in Button must be exactly 0').toBe(0);
    expect(buttonStats.checkedBorderObjects, 'Border objects in Button must be exactly 0').toBe(0);
    expect(buttonStats.checkedBorderPairs, 'Border pairs in Button must be exactly 0').toBe(0);

    const riskBadgeStats = analyzeFile('shared/ui/RiskBadge.tsx');
    expect(riskBadgeStats.violations, `RiskBadge violations:\n${riskBadgeStats.violations.join('\n')}`).toEqual([]);
    expect(riskBadgeStats.totalStyleAttrs, 'Total style attributes in RiskBadge must be exactly 6').toBe(6);
    expect(riskBadgeStats.checkedObjects, 'Explicit style objects in RiskBadge must be exactly 4').toBe(4);
    expect(riskBadgeStats.checkedPairs, 'Evaluated pairs in RiskBadge must be exactly 4').toBe(4);
    expect(riskBadgeStats.unboundColorObjects, 'Unbound color objects in RiskBadge must be exactly 0').toBe(0);
    expect(riskBadgeStats.coveredColorObjects, 'Total covered color objects in RiskBadge must be exactly 4').toBe(4);
    expect(riskBadgeStats.checkedBorderObjects, 'Border objects in RiskBadge must be exactly 4').toBe(4);
    expect(riskBadgeStats.checkedBorderPairs, 'Border pairs in RiskBadge must be exactly 4').toBe(4);

    const executionStats = analyzeFile('features/workspaces/ExecutionResultView.tsx');
    expect(executionStats.violations, `ExecutionResultView violations:\n${executionStats.violations.join('\n')}`).toEqual([]);
    expect(executionStats.totalStyleAttrs, 'Total style attributes in ExecutionResultView must be exactly 44').toBe(44);
    expect(executionStats.checkedObjects, 'Explicit style objects in ExecutionResultView must be exactly 2').toBe(2);
    expect(executionStats.checkedPairs, 'Evaluated pairs in ExecutionResultView must be exactly 20').toBe(20);
    expect(executionStats.unboundColorObjects, 'Unbound color objects in ExecutionResultView must be exactly 15').toBe(15);
    expect(executionStats.coveredColorObjects, 'Total covered color objects in ExecutionResultView must be exactly 17').toBe(17);
    expect(executionStats.checkedBorderObjects, 'Border objects in ExecutionResultView must be exactly 7').toBe(7);
    expect(executionStats.checkedBorderPairs, 'Border pairs in ExecutionResultView must be exactly 8').toBe(8);

    const modalStats = analyzeFile('features/workspaces/WorkspaceCreateModal.tsx');
    expect(modalStats.violations, `WorkspaceCreateModal violations:\n${modalStats.violations.join('\n')}`).toEqual([]);
    expect(modalStats.totalStyleAttrs, 'Total style attributes in WorkspaceCreateModal must be exactly 15').toBe(15);
    expect(modalStats.checkedObjects, 'Explicit style objects in WorkspaceCreateModal must be exactly 3').toBe(3);
    expect(modalStats.checkedPairs, 'Evaluated pairs in WorkspaceCreateModal must be exactly 8').toBe(8);
    expect(modalStats.unboundColorObjects, 'Unbound color objects in WorkspaceCreateModal must be exactly 5').toBe(5);
    expect(modalStats.coveredColorObjects, 'Total covered color objects in WorkspaceCreateModal must be exactly 8').toBe(8);
    expect(modalStats.checkedBorderObjects, 'Border objects in WorkspaceCreateModal must be exactly 4').toBe(4);
    expect(modalStats.checkedBorderPairs, 'Border pairs in WorkspaceCreateModal must be exactly 4').toBe(4);

    const nodeDetailStats = analyzeFile('features/nodes/NodeDetail.tsx');
    expect(nodeDetailStats.violations, `NodeDetail violations:\n${nodeDetailStats.violations.join('\n')}`).toEqual([]);
    expect(nodeDetailStats.totalStyleAttrs, 'Total style attributes in NodeDetail must be exactly 66').toBe(66);
    expect(nodeDetailStats.checkedObjects, 'Explicit style objects in NodeDetail must be exactly 6').toBe(6);
    expect(nodeDetailStats.checkedPairs, 'Evaluated pairs in NodeDetail must be exactly 38').toBe(38);
    expect(nodeDetailStats.unboundColorObjects, 'Unbound color objects in NodeDetail must be exactly 27').toBe(27);
    expect(nodeDetailStats.coveredColorObjects, 'Total covered color objects in NodeDetail must be exactly 33').toBe(33);
    expect(nodeDetailStats.checkedBorderObjects, 'Border objects in NodeDetail must be exactly 16').toBe(16);
    expect(nodeDetailStats.checkedBorderPairs, 'Border pairs in NodeDetail must be exactly 18').toBe(18);

    const explainStats = analyzeFile('features/placement/PlacementExplainView.tsx');
    expect(explainStats.violations, `PlacementExplainView violations:\n${explainStats.violations.join('\n')}`).toEqual([]);
    expect(explainStats.totalStyleAttrs, 'Total style attributes in PlacementExplainView must be exactly 30').toBe(30);
    expect(explainStats.checkedObjects, 'Explicit style objects in PlacementExplainView must be exactly 2').toBe(2);
    expect(explainStats.checkedPairs, 'Evaluated pairs in PlacementExplainView must be exactly 14').toBe(14);
    expect(explainStats.unboundColorObjects, 'Unbound color objects in PlacementExplainView must be exactly 10').toBe(10);
    expect(explainStats.coveredColorObjects, 'Total covered color objects in PlacementExplainView must be exactly 12').toBe(12);
    expect(explainStats.checkedBorderObjects, 'Border objects in PlacementExplainView must be exactly 5').toBe(5);
    expect(explainStats.checkedBorderPairs, 'Border pairs in PlacementExplainView must be exactly 8').toBe(8);

    const topologyStats = analyzeFile('features/placement/ResourceTopologyGraph.tsx');
    expect(topologyStats.violations, `ResourceTopologyGraph violations:\n${topologyStats.violations.join('\n')}`).toEqual([]);
    expect(topologyStats.totalStyleAttrs, 'Total style attributes in ResourceTopologyGraph must be exactly 23').toBe(23);
    expect(topologyStats.checkedObjects, 'Explicit style objects in ResourceTopologyGraph must be exactly 2').toBe(2);
    expect(topologyStats.checkedPairs, 'Evaluated pairs in ResourceTopologyGraph must be exactly 9').toBe(9);
    expect(topologyStats.unboundColorObjects, 'Unbound color objects in ResourceTopologyGraph must be exactly 7').toBe(7);
    expect(topologyStats.coveredColorObjects, 'Total covered color objects in ResourceTopologyGraph must be exactly 9').toBe(9);
    expect(topologyStats.checkedBorderObjects, 'Border objects in ResourceTopologyGraph must be exactly 4').toBe(4);
    expect(topologyStats.checkedBorderPairs, 'Border pairs in ResourceTopologyGraph must be exactly 6').toBe(6);

    const evidenceStats = analyzeFile('features/evidence/EvidenceViewer.tsx');
    expect(evidenceStats.violations, `EvidenceViewer violations:\n${evidenceStats.violations.join('\n')}`).toEqual([]);
    expect(evidenceStats.totalStyleAttrs, 'Total style attributes in EvidenceViewer must be exactly 31').toBe(31);
    expect(evidenceStats.checkedObjects, 'Explicit style objects in EvidenceViewer must be exactly 11').toBe(11);
    expect(evidenceStats.checkedPairs, 'Evaluated pairs in EvidenceViewer must be exactly 15').toBe(15);
    expect(evidenceStats.unboundColorObjects, 'Unbound color objects in EvidenceViewer must be exactly 4').toBe(4);
    expect(evidenceStats.coveredColorObjects, 'Total covered color objects in EvidenceViewer must be exactly 15').toBe(15);
    expect(evidenceStats.checkedBorderObjects, 'Border objects in EvidenceViewer must be exactly 12').toBe(12);
    expect(evidenceStats.checkedBorderPairs, 'Border pairs in EvidenceViewer must be exactly 12').toBe(12);

    const approvalDetailStats = analyzeFile('features/approvals/ApprovalDetail.tsx');
    expect(approvalDetailStats.violations, `ApprovalDetail violations:\n${approvalDetailStats.violations.join('\n')}`).toEqual([]);
    expect(approvalDetailStats.totalStyleAttrs, 'Total style attributes in ApprovalDetail must be exactly 35').toBe(35);
    expect(approvalDetailStats.checkedObjects, 'Explicit style objects in ApprovalDetail must be exactly 3').toBe(3);
    expect(approvalDetailStats.checkedPairs, 'Evaluated pairs in ApprovalDetail must be exactly 14').toBe(14);
    expect(approvalDetailStats.unboundColorObjects, 'Unbound color objects in ApprovalDetail must be exactly 10').toBe(10);
    expect(approvalDetailStats.coveredColorObjects, 'Total covered color objects in ApprovalDetail must be exactly 13').toBe(13);
    expect(approvalDetailStats.checkedBorderObjects, 'Border objects in ApprovalDetail must be exactly 5').toBe(5);
    expect(approvalDetailStats.checkedBorderPairs, 'Border pairs in ApprovalDetail must be exactly 6').toBe(6);

    const headerStats = analyzeFile('shared/ui/Header.tsx');
    expect(headerStats.violations, `Header violations:\n${headerStats.violations.join('\n')}`).toEqual([]);
    expect(headerStats.totalStyleAttrs, 'Total style attributes in Header must be exactly 20').toBe(20);
    expect(headerStats.checkedObjects, 'Explicit style objects in Header must be exactly 3').toBe(3);
    expect(headerStats.checkedPairs, 'Evaluated pairs in Header must be exactly 11').toBe(11);
    expect(headerStats.unboundColorObjects, 'Unbound color objects in Header must be exactly 7').toBe(7);
    expect(headerStats.coveredColorObjects, 'Total covered color objects in Header must be exactly 10').toBe(10);
    expect(headerStats.checkedBorderObjects, 'Border objects in Header must be exactly 4').toBe(4);
    expect(headerStats.checkedBorderPairs, 'Border pairs in Header must be exactly 4').toBe(4);

    const appStats = analyzeFile('app/App.tsx');
    expect(appStats.violations, `App violations:\n${appStats.violations.join('\n')}`).toEqual([]);
    expect(appStats.totalStyleAttrs, 'Total style attributes in App must be exactly 19').toBe(19);
    expect(appStats.checkedObjects, 'Explicit style objects in App must be exactly 7').toBe(7);
    expect(appStats.checkedPairs, 'Evaluated pairs in App must be exactly 12').toBe(12);
    expect(appStats.unboundColorObjects, 'Unbound color objects in App must be exactly 4').toBe(4);
    expect(appStats.coveredColorObjects, 'Total covered color objects in App must be exactly 11').toBe(11);
    expect(appStats.checkedBorderObjects, 'Border objects in App must be exactly 9').toBe(9);
    expect(appStats.checkedBorderPairs, 'Border pairs in App must be exactly 10').toBe(10);

    const releaseEngineStats = analyzeFile('features/release/releaseEngine.ts');
    expect(releaseEngineStats.violations, `releaseEngine violations:\n${releaseEngineStats.violations.join('\n')}`).toEqual([]);
    expect(releaseEngineStats.totalStyleAttrs, 'Total style attributes in releaseEngine must be exactly 0').toBe(0);

    const desktopWindowStats = analyzeFile('features/desktop/DesktopWindow.tsx');
    expect(desktopWindowStats.violations, `DesktopWindow violations:\n${desktopWindowStats.violations.join('\n')}`).toEqual([]);
    expect(desktopWindowStats.totalStyleAttrs, 'Total style attributes in DesktopWindow must be exactly 13').toBe(13);
    expect(desktopWindowStats.checkedObjects, 'Explicit style objects in DesktopWindow must be exactly 3').toBe(3);
    expect(desktopWindowStats.checkedPairs, 'Evaluated pairs in DesktopWindow must be exactly 9').toBe(9);
    expect(desktopWindowStats.unboundColorObjects, 'Unbound color objects in DesktopWindow must be exactly 2').toBe(2);
    expect(desktopWindowStats.coveredColorObjects, 'Total covered color objects in DesktopWindow must be exactly 5').toBe(5);
    expect(desktopWindowStats.checkedBorderObjects, 'Border objects in DesktopWindow must be exactly 6').toBe(6);
    expect(desktopWindowStats.checkedBorderPairs, 'Border pairs in DesktopWindow must be exactly 7').toBe(7);

    const terminalSessionStats = analyzeFile('features/desktop/TerminalSessionView.tsx');
    expect(terminalSessionStats.violations, `TerminalSessionView violations:\n${terminalSessionStats.violations.join('\n')}`).toEqual([]);
    expect(terminalSessionStats.totalStyleAttrs, 'Total style attributes in TerminalSessionView must be exactly 34').toBe(34);
    expect(terminalSessionStats.checkedObjects, 'Explicit style objects in TerminalSessionView must be exactly 15').toBe(15);
    expect(terminalSessionStats.checkedPairs, 'Evaluated pairs in TerminalSessionView must be exactly 19').toBe(19);
    expect(terminalSessionStats.unboundColorObjects, 'Unbound color objects in TerminalSessionView must be exactly 4').toBe(4);
    expect(terminalSessionStats.coveredColorObjects, 'Total covered color objects in TerminalSessionView must be exactly 19').toBe(19);
    expect(terminalSessionStats.checkedBorderObjects, 'Border objects in TerminalSessionView must be exactly 9').toBe(9);
    expect(terminalSessionStats.checkedBorderPairs, 'Border pairs in TerminalSessionView must be exactly 9').toBe(9);

    const conflictResolutionStats = analyzeFile('features/editor/ConflictResolutionModal.tsx');
    expect(conflictResolutionStats.violations, `ConflictResolutionModal violations:\n${conflictResolutionStats.violations.join('\n')}`).toEqual([]);
    expect(conflictResolutionStats.totalStyleAttrs, 'Total style attributes in ConflictResolutionModal must be exactly 18').toBe(18);
    expect(conflictResolutionStats.checkedObjects, 'Explicit style objects in ConflictResolutionModal must be exactly 2').toBe(2);
    expect(conflictResolutionStats.checkedPairs, 'Evaluated pairs in ConflictResolutionModal must be exactly 5').toBe(5);
    expect(conflictResolutionStats.unboundColorObjects, 'Unbound color objects in ConflictResolutionModal must be exactly 3').toBe(3);
    expect(conflictResolutionStats.coveredColorObjects, 'Total covered color objects in ConflictResolutionModal must be exactly 5').toBe(5);
    expect(conflictResolutionStats.checkedBorderObjects, 'Border objects in ConflictResolutionModal must be exactly 4').toBe(4);
    expect(conflictResolutionStats.checkedBorderPairs, 'Border pairs in ConflictResolutionModal must be exactly 4').toBe(4);

    const diffViewerStats = analyzeFile('features/editor/DiffViewer.tsx');
    expect(diffViewerStats.violations, `DiffViewer violations:\n${diffViewerStats.violations.join('\n')}`).toEqual([]);
    expect(diffViewerStats.totalStyleAttrs, 'Total style attributes in DiffViewer must be exactly 17').toBe(17);
    expect(diffViewerStats.checkedObjects, 'Explicit style objects in DiffViewer must be exactly 4').toBe(4);
    expect(diffViewerStats.checkedPairs, 'Evaluated pairs in DiffViewer must be exactly 8').toBe(8);
    expect(diffViewerStats.unboundColorObjects, 'Unbound color objects in DiffViewer must be exactly 4').toBe(4);
    expect(diffViewerStats.coveredColorObjects, 'Total covered color objects in DiffViewer must be exactly 8').toBe(8);
    expect(diffViewerStats.checkedBorderObjects, 'Border objects in DiffViewer must be exactly 3').toBe(3);
    expect(diffViewerStats.checkedBorderPairs, 'Border pairs in DiffViewer must be exactly 3').toBe(3);

    const gitCommitStats = analyzeFile('features/editor/GitCommitModal.tsx');
    expect(gitCommitStats.violations, `GitCommitModal violations:\n${gitCommitStats.violations.join('\n')}`).toEqual([]);
    expect(gitCommitStats.totalStyleAttrs, 'Total style attributes in GitCommitModal must be exactly 25').toBe(25);
    expect(gitCommitStats.checkedObjects, 'Explicit style objects in GitCommitModal must be exactly 4').toBe(4);
    expect(gitCommitStats.checkedPairs, 'Evaluated pairs in GitCommitModal must be exactly 12').toBe(12);
    expect(gitCommitStats.unboundColorObjects, 'Unbound color objects in GitCommitModal must be exactly 8').toBe(8);
    expect(gitCommitStats.coveredColorObjects, 'Total covered color objects in GitCommitModal must be exactly 12').toBe(12);
    expect(gitCommitStats.checkedBorderObjects, 'Border objects in GitCommitModal must be exactly 6').toBe(6);
    expect(gitCommitStats.checkedBorderPairs, 'Border pairs in GitCommitModal must be exactly 6').toBe(6);

    const monacoStats = analyzeFile('features/editor/MonacoWorkspaceEditor.tsx');
    expect(monacoStats.violations, `MonacoWorkspaceEditor violations:\n${monacoStats.violations.join('\n')}`).toEqual([]);
    expect(monacoStats.totalStyleAttrs, 'Total style attributes in MonacoWorkspaceEditor must be exactly 69').toBe(69);
    expect(monacoStats.checkedObjects, 'Explicit style objects in MonacoWorkspaceEditor must be exactly 15').toBe(15);
    expect(monacoStats.checkedPairs, 'Evaluated pairs in MonacoWorkspaceEditor must be exactly 42').toBe(42);
    expect(monacoStats.unboundColorObjects, 'Unbound color objects in MonacoWorkspaceEditor must be exactly 26').toBe(26);
    expect(monacoStats.coveredColorObjects, 'Total covered color objects in MonacoWorkspaceEditor must be exactly 41').toBe(41);
    expect(monacoStats.checkedBorderObjects, 'Border objects in MonacoWorkspaceEditor must be exactly 21').toBe(21);
    expect(monacoStats.checkedBorderPairs, 'Border pairs in MonacoWorkspaceEditor must be exactly 22').toBe(22);

    const webTerminalStats = analyzeFile('features/terminal/WebTerminal.tsx');
    expect(webTerminalStats.violations, `WebTerminal violations:\n${webTerminalStats.violations.join('\n')}`).toEqual([]);
    expect(webTerminalStats.totalStyleAttrs, 'Total style attributes in WebTerminal must be exactly 28').toBe(28);
    expect(webTerminalStats.checkedObjects, 'Explicit style objects in WebTerminal must be exactly 6').toBe(6);
    expect(webTerminalStats.checkedPairs, 'Evaluated pairs in WebTerminal must be exactly 15').toBe(15);
    expect(webTerminalStats.unboundColorObjects, 'Unbound color objects in WebTerminal must be exactly 8').toBe(8);
    expect(webTerminalStats.coveredColorObjects, 'Total covered color objects in WebTerminal must be exactly 14').toBe(14);
    expect(webTerminalStats.checkedBorderObjects, 'Border objects in WebTerminal must be exactly 9').toBe(9);
    expect(webTerminalStats.checkedBorderPairs, 'Border pairs in WebTerminal must be exactly 9').toBe(9);
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

    // Probe 71 [Card 218]: DistributedRecoveryView former hardcoded #58a6ff on light subtle strictly fails 4.5:1
    const probe71Cr = getContrast('#58a6ff', lightTokens['--color-bg-subtle']);
    expect(probe71Cr, 'DistributedRecoveryView former #58a6ff on light subtle fails 4.5:1').toBeLessThan(4.5);
    expect(probe71Cr).toBeCloseTo(2.31, 2);

    // Probe 72 [Card 218]: DistributedRecoveryView former hardcoded #3fb950 on light subtle strictly fails 4.5:1
    const probe72Cr = getContrast('#3fb950', lightTokens['--color-bg-subtle']);
    expect(probe72Cr, 'DistributedRecoveryView former #3fb950 on light subtle fails 4.5:1').toBeLessThan(4.5);
    expect(probe72Cr).toBeCloseTo(2.32, 2);

    // Probe 73 [Card 218]: DistributedRecoveryView former hardcoded #8b949e on light surface strictly fails 4.5:1
    const probe73Cr = getContrast('#8b949e', lightTokens['--color-bg-surface']);
    expect(probe73Cr, 'DistributedRecoveryView former #8b949e on light surface fails 4.5:1').toBeLessThan(4.5);
    expect(probe73Cr).toBeCloseTo(3.08, 2);

    // Probe 74 [Card 218]: DistributedRecoveryView former hardcoded #f85149 on light subtle strictly fails 4.5:1
    const probe74Cr = getContrast('#f85149', lightTokens['--color-bg-subtle']);
    expect(probe74Cr, 'DistributedRecoveryView former #f85149 on light subtle fails 4.5:1').toBeLessThan(4.5);
    expect(probe74Cr).toBeCloseTo(3.06, 2);

    // Probe 75 [Card 218]: DistributedRecoveryView former hardcoded #e3b341 on light subtle strictly fails 4.5:1
    const probe75Cr = getContrast('#e3b341', lightTokens['--color-bg-subtle']);
    expect(probe75Cr, 'DistributedRecoveryView former #e3b341 on light subtle fails 4.5:1').toBeLessThan(4.5);
    expect(probe75Cr).toBeCloseTo(1.78, 2);

    // Probe 76 [Card 220]: ReleaseCandidateView former hardcoded #58a6ff on light canvas notice composite #e1edfc strictly fails 4.5:1
    const lightCanvasNoticeComposite = blendRgba([56, 139, 253], 0.12, lightTokens['--color-bg-canvas']);
    const probe76Cr = getContrast('#58a6ff', lightCanvasNoticeComposite);
    expect(probe76Cr, 'ReleaseCandidateView former #58a6ff on light canvas notice composite fails 4.5:1').toBeLessThan(4.5);
    expect(probe76Cr).toBeCloseTo(2.13, 1);

    // Probe 77 [Card 220]: ReleaseCandidateView former hardcoded #f85149 on light canvas error composite #f8e1e1 strictly fails 4.5:1
    const lightCanvasErrorComposite = blendRgba([248, 81, 73], 0.15, lightTokens['--color-bg-canvas']);
    const probe77Cr = getContrast('#f85149', lightCanvasErrorComposite);
    expect(probe77Cr, 'ReleaseCandidateView former #f85149 on light canvas error composite fails 4.5:1').toBeLessThan(4.5);
    expect(probe77Cr).toBeCloseTo(2.69, 1);

    // Probe 78 [Card 220]: ReleaseCandidateView former hardcoded #3fb950 on light canvas success composite #daece0 strictly fails 4.5:1
    const lightCanvasSuccessComposite = blendRgba([46, 160, 67], 0.15, lightTokens['--color-bg-canvas']);
    const probe78Cr = getContrast('#3fb950', lightCanvasSuccessComposite);
    expect(probe78Cr, 'ReleaseCandidateView former #3fb950 on light canvas success composite fails 4.5:1').toBeLessThan(4.5);
    expect(probe78Cr).toBeCloseTo(2.06, 1);

    // Probe 79 [Card 220]: ReleaseCandidateView former hardcoded #8b949e on dark subtle unmeasured badge composite #2d333b strictly fails 4.5:1
    const darkSubtleUnmeasuredComposite = blendRgba([139, 148, 158], 0.2, '#161b22');
    const probe79Cr = getContrast('#8b949e', darkSubtleUnmeasuredComposite);
    expect(probe79Cr, 'ReleaseCandidateView former #8b949e on dark unmeasured composite fails 4.5:1').toBeLessThan(4.5);
    expect(probe79Cr).toBeCloseTo(4.14, 1);

    // Probe 80 [Card 220]: ReleaseCandidateView former hardcoded #f85149 on dark subtle breached badge composite #43262a strictly fails 4.5:1
    const darkSubtleBreachedComposite = blendRgba([248, 81, 73], 0.2, '#161b22');
    const probe80Cr = getContrast('#f85149', darkSubtleBreachedComposite);
    expect(probe80Cr, 'ReleaseCandidateView former #f85149 on dark breached composite fails 4.5:1').toBeLessThan(4.5);
    expect(probe80Cr).toBeCloseTo(4.04, 1);

    // Probe 81 [Card 226]: ModelStudioView query desc with former #64748b on base #0f172a
    const defectiveQueryDesc = '#64748b';
    const probe81Cr = getContrast(defectiveQueryDesc, '#0f172a');
    expect(probe81Cr, 'Defective query desc #64748b on #0f172a must fail 4.5:1').toBeLessThan(4.5);
    expect(probe81Cr).toBeCloseTo(3.75, 1);

    // Probe 82 [Card 226]: ModelStudioView query button text with former #ffffff on #3b82f6
    const defectiveQueryBtnFg = '#ffffff';
    const probe82Cr = getContrast(defectiveQueryBtnFg, '#3b82f6');
    expect(probe82Cr, 'Defective query button white on #3b82f6 must fail 4.5:1').toBeLessThan(4.5);
    expect(probe82Cr).toBeCloseTo(3.68, 1);

    // Probe 83 [Card 226]: ModelStudioView shard repair button with former #ffffff on #d97706
    const defectiveRepairBtnFg = '#ffffff';
    const probe83Cr = getContrast(defectiveRepairBtnFg, '#d97706');
    expect(probe83Cr, 'Defective shard repair button white on #d97706 must fail 4.5:1').toBeLessThan(4.5);
    expect(probe83Cr).toBeCloseTo(3.19, 1);

    // Probe 84 [Card 226]: ModelStudioView former replica unhealthy badge text #fca5a5 on light subtle strictly fails 4.5:1
    const probe84Cr = getContrast('#fca5a5', lightTokens['--color-bg-subtle']);
    expect(probe84Cr, 'Former unhealthy replica text #fca5a5 on light subtle fails 4.5:1').toBeLessThan(4.5);
    expect(probe84Cr).toBeCloseTo(1.73, 1);

    // Probe 85 [Card 226]: ModelStudioView former LAN alert text #fde68a on light subtle strictly fails 4.5:1
    const probe85Cr = getContrast('#fde68a', lightTokens['--color-bg-subtle']);
    expect(probe85Cr, 'Former LAN alert text #fde68a on light subtle fails 4.5:1').toBeLessThan(4.5);
    expect(probe85Cr).toBeCloseTo(1.14, 1);

    // Probe 86 [Card 228]: NaturalLanguageRunView former notice error tint on light canvas (#f8fafc) strictly fails 4.5:1
    const lightCanvasNoticeErrorComposite = blendRgba([248, 81, 73], 0.15, lightTokens['--color-bg-canvas']);
    const probe86Cr = getContrast('#f85149', lightCanvasNoticeErrorComposite);
    expect(probe86Cr, 'NaturalLanguageRunView former error notice #f85149 on light canvas error composite fails 4.5:1').toBeLessThan(4.5);
    expect(probe86Cr).toBeCloseTo(2.69, 1);

    // Probe 87 [Card 228]: NaturalLanguageRunView former notice success tint on light canvas (#f8fafc) strictly fails 4.5:1
    const lightCanvasNoticeSuccessComposite = blendRgba([46, 160, 67], 0.15, lightTokens['--color-bg-canvas']);
    const probe87Cr = getContrast('#3fb950', lightCanvasNoticeSuccessComposite);
    expect(probe87Cr, 'NaturalLanguageRunView former success notice #3fb950 on light canvas success composite fails 4.5:1').toBeLessThan(4.5);
    expect(probe87Cr).toBeCloseTo(2.06, 1);

    // Probe 88 [Card 228]: NaturalLanguageRunView former notice info tint on light canvas (#f8fafc) strictly fails 4.5:1
    const lightCanvasNoticeInfoComposite = blendRgba([56, 139, 253], 0.15, lightTokens['--color-bg-canvas']);
    const probe88Cr = getContrast('#58a6ff', lightCanvasNoticeInfoComposite);
    expect(probe88Cr, 'NaturalLanguageRunView former info notice #58a6ff on light canvas info composite fails 4.5:1').toBeLessThan(4.5);
    expect(probe88Cr).toBeCloseTo(2.05, 1);

    // Probe 89 [Card 228]: NaturalLanguageRunView former notice title #93c5fd on light surface (#ffffff) strictly fails 4.5:1
    const probe89Cr = getContrast('#93c5fd', lightTokens['--color-bg-surface']);
    expect(probe89Cr, 'NaturalLanguageRunView former #93c5fd on light surface fails 4.5:1').toBeLessThan(4.5);
    expect(probe89Cr).toBeCloseTo(1.80, 1);

    // Probe 90 [Card 228]: NaturalLanguageRunView former rejected text #ff7b72 on light surface (#ffffff) strictly fails 4.5:1
    const probe90Cr = getContrast('#ff7b72', lightTokens['--color-bg-surface']);
    expect(probe90Cr, 'NaturalLanguageRunView former #ff7b72 on light surface fails 4.5:1').toBeLessThan(4.5);
    expect(probe90Cr).toBeCloseTo(2.52, 1);

    // Probe 91 [Card 230]: DesktopShell former muted text literal #94a3b8 on light surface strictly fails 4.5:1
    const probe91Cr = getContrast('#94a3b8', lightTokens['--color-bg-surface']);
    expect(probe91Cr, 'DesktopShell former #94a3b8 on light surface fails 4.5:1').toBeLessThan(4.5);
    expect(probe91Cr).toBeCloseTo(2.56, 1);

    // Probe 92 [Card 230]: DesktopShell former brand text literal #38bdf8 on light surface strictly fails 4.5:1
    const probe92Cr = getContrast('#38bdf8', lightTokens['--color-bg-surface']);
    expect(probe92Cr, 'DesktopShell former #38bdf8 on light surface fails 4.5:1').toBeLessThan(4.5);
    expect(probe92Cr).toBeCloseTo(2.14, 1);

    // Probe 93 [Card 230]: DesktopShell former online text literal #34d399 on light surface strictly fails 4.5:1
    const probe93Cr = getContrast('#34d399', lightTokens['--color-bg-surface']);
    expect(probe93Cr, 'DesktopShell former #34d399 on light surface fails 4.5:1').toBeLessThan(4.5);
    expect(probe93Cr).toBeCloseTo(1.92, 1);

    // Probe 94 [Card 230]: DesktopShell former mode switcher text literal #60a5fa on light surface strictly fails 4.5:1
    const probe94Cr = getContrast('#60a5fa', lightTokens['--color-bg-surface']);
    expect(probe94Cr, 'DesktopShell former #60a5fa on light surface fails 4.5:1').toBeLessThan(4.5);
    expect(probe94Cr).toBeCloseTo(2.53, 1);

    // Probe 95 [Card 230]: DesktopShell former white text literal #ffffff on light canvas strictly fails 4.5:1
    const probe95Cr = getContrast('#ffffff', lightTokens['--color-bg-canvas']);
    expect(probe95Cr, 'DesktopShell former #ffffff on light canvas fails 4.5:1').toBeLessThan(4.5);
    expect(probe95Cr).toBeCloseTo(1.05, 1);

    // Probe 96 [Card 235]: PlacementSimulator former unverified badge text #fbbf24 on light canvas strictly fails 4.5:1
    const probe96Cr = getContrast('#fbbf24', lightTokens['--color-bg-canvas']);
    expect(probe96Cr, 'PlacementSimulator former #fbbf24 on light canvas fails 4.5:1').toBeLessThan(4.5);
    expect(probe96Cr).toBeCloseTo(1.60, 1);

    // Probe 97 [Card 235]: PlacementSimulator former error text #fca5a5 on light canvas strictly fails 4.5:1
    const probe97Cr = getContrast('#fca5a5', lightTokens['--color-bg-canvas']);
    expect(probe97Cr, 'PlacementSimulator former #fca5a5 on light canvas fails 4.5:1').toBeLessThan(4.5);
    expect(probe97Cr).toBeCloseTo(1.81, 1);

    // Probe 98 [Card 235]: PlacementSimulator former error subtext #f87171 on light canvas strictly fails 4.5:1
    const probe98Cr = getContrast('#f87171', lightTokens['--color-bg-canvas']);
    expect(probe98Cr, 'PlacementSimulator former #f87171 on light canvas fails 4.5:1').toBeLessThan(4.5);
    expect(probe98Cr).toBeCloseTo(2.64, 1);

    // Probe 99 [Card 235]: PlacementSimulator former unverified badge border rgba(234, 179, 8, 0.3) on light canvas strictly fails 3.0:1
    const defectiveUnverifiedBorder = blendRgba([234, 179, 8], 0.3, lightTokens['--color-bg-canvas']);
    const probe99Cr = getContrast(defectiveUnverifiedBorder, lightTokens['--color-bg-canvas']);
    expect(probe99Cr, 'PlacementSimulator former unverified border on canvas fails 3.0:1').toBeLessThan(3.0);
    expect(probe99Cr).toBeCloseTo(1.20, 1);

    // Probe 100 [Card 235]: PlacementSimulator former operator note #93c5fd on light surface strictly fails 4.5:1
    const probe100Cr = getContrast('#93c5fd', lightTokens['--color-bg-surface']);
    expect(probe100Cr, 'PlacementSimulator former #93c5fd on light surface fails 4.5:1').toBeLessThan(4.5);
    expect(probe100Cr).toBeCloseTo(1.80, 1);

    // Probe 101 [Card 245]: ApprovalCenter former freshness indicator #93c5fd on light surface strictly fails 4.5:1
    const probe101Cr = getContrast('#93c5fd', lightTokens['--color-bg-surface']);
    expect(probe101Cr, 'ApprovalCenter former #93c5fd on light surface fails 4.5:1').toBeLessThan(4.5);
    expect(probe101Cr).toBeCloseTo(1.80, 1);

    // Probe 102 [Card 245]: ApprovalCenter former stale warning title #fca5a5 on light surface strictly fails 4.5:1
    const probe102Cr = getContrast('#fca5a5', lightTokens['--color-bg-surface']);
    expect(probe102Cr, 'ApprovalCenter former #fca5a5 on light surface fails 4.5:1').toBeLessThan(4.5);
    expect(probe102Cr).toBeCloseTo(1.90, 1);

    // Probe 103 [Card 245]: ApprovalCenter former snapshot note #fed7aa on light surface strictly fails 4.5:1
    const probe103Cr = getContrast('#fed7aa', lightTokens['--color-bg-surface']);
    expect(probe103Cr, 'ApprovalCenter former #fed7aa on light surface fails 4.5:1').toBeLessThan(4.5);
    expect(probe103Cr).toBeCloseTo(1.35, 1);

    // Probe 104 [Card 245]: ApprovalCenter former retry button #3b82f6 on light surface strictly fails 4.5:1
    const probe104Cr = getContrast('#3b82f6', lightTokens['--color-bg-surface']);
    expect(probe104Cr, 'ApprovalCenter former #3b82f6 on light surface fails 4.5:1').toBeLessThan(4.5);
    expect(probe104Cr).toBeCloseTo(3.68, 1);

    // Probe 105 [Card 245]: ApprovalCenter former stale warning border #ef4444 on dark subtle strictly fails 4.5:1 text
    const probe105Cr = getContrast('#ef4444', darkTokens['--color-bg-subtle']);
    expect(probe105Cr, 'ApprovalCenter former #ef4444 on dark subtle fails 4.5:1').toBeLessThan(4.5);
    expect(probe105Cr).toBeCloseTo(3.89, 1);

    // Probe 106 [Card 248]: ClusterOverview former error heading #fca5a5 on light surface strictly fails 4.5:1
    const probe106Cr = getContrast('#fca5a5', lightTokens['--color-bg-surface']);
    expect(probe106Cr, 'ClusterOverview former #fca5a5 on light surface fails 4.5:1').toBeLessThan(4.5);
    expect(probe106Cr).toBeCloseTo(1.90, 1);

    // Probe 107 [Card 248]: ClusterOverview former retry button text #ffffff on #ef4444 strictly fails 4.5:1
    const probe107Cr = getContrast('#ffffff', '#ef4444');
    expect(probe107Cr, 'ClusterOverview former #ffffff on #ef4444 fails 4.5:1').toBeLessThan(4.5);
    expect(probe107Cr).toBeCloseTo(3.76, 1);

    // Probe 108 [Card 248]: ClusterOverview former heartbeat text #64748b on dark canvas strictly fails 4.5:1
    const probe108Cr = getContrast('#64748b', darkTokens['--color-bg-canvas']);
    expect(probe108Cr, 'ClusterOverview former #64748b on dark canvas fails 4.5:1').toBeLessThan(4.5);
    expect(probe108Cr).toBeCloseTo(4.08, 1);

    // Probe 109 [Card 248]: ClusterOverview former active node text #38bdf8 on light canvas strictly fails 4.5:1
    const probe109Cr = getContrast('#38bdf8', lightTokens['--color-bg-canvas']);
    expect(probe109Cr, 'ClusterOverview former #38bdf8 on light canvas fails 4.5:1').toBeLessThan(4.5);
    expect(probe109Cr).toBeCloseTo(2.05, 1);

    // Probe 110 [Card 248]: ClusterOverview former degraded node text #d29922 on light canvas strictly fails 4.5:1
    const probe110Cr = getContrast('#d29922', lightTokens['--color-bg-canvas']);
    expect(probe110Cr, 'ClusterOverview former #d29922 on light canvas fails 4.5:1').toBeLessThan(4.5);
    expect(probe110Cr).toBeCloseTo(2.41, 1);

    // Probe 111 [Card 270]: WorkspaceList former ready text #34d399 on light composite #dbf4ec strictly fails 4.5:1
    const lightReadyComposite = blendRgba([16, 185, 129], 0.15, lightTokens['--color-bg-surface']);
    const probe111Cr = getContrast('#34d399', lightReadyComposite);
    expect(probe111Cr, 'WorkspaceList former #34d399 on light composite fails 4.5:1').toBeLessThan(4.5);
    expect(probe111Cr).toBeCloseTo(1.66, 1);

    // Probe 112 [Card 270]: WorkspaceList former provisioning text #f59e0b on light composite #fef4e7 strictly fails 4.5:1
    const lightProvComposite = blendRgba([245, 158, 11], 0.15, lightTokens['--color-bg-surface']);
    const probe112Cr = getContrast('#f59e0b', lightProvComposite);
    expect(probe112Cr, 'WorkspaceList former #f59e0b on light composite fails 4.5:1').toBeLessThan(4.5);
    expect(probe112Cr).toBeCloseTo(1.91, 1);

    // Probe 113 [Card 270]: WorkspaceList former deleting text #f87171 on light composite #fde9e9 strictly fails 4.5:1
    const lightDelComposite = blendRgba([239, 68, 68], 0.15, lightTokens['--color-bg-surface']);
    const probe113Cr = getContrast('#f87171', lightDelComposite);
    expect(probe113Cr, 'WorkspaceList former #f87171 on light composite fails 4.5:1').toBeLessThan(4.5);
    expect(probe113Cr).toBeCloseTo(2.28, 1);

    // Probe 114 [Card 270]: WorkspaceList former ready border rgba(16,185,129,0.3) on light surface strictly fails 3.0:1
    const lightReadyBorder = blendRgba([16, 185, 129], 0.3, lightTokens['--color-bg-surface']);
    const probe114Cr = getContrast(lightReadyBorder, lightTokens['--color-bg-surface']);
    expect(probe114Cr, 'WorkspaceList former ready border on light surface fails 3.0:1').toBeLessThan(3.0);
    expect(probe114Cr).toBeCloseTo(1.33, 1);

    // Probe 115 [Card 270]: WorkspaceList former deleting border rgba(239,68,68,0.3) on dark surface strictly fails 3.0:1
    const darkDelBorder = blendRgba([239, 68, 68], 0.3, darkTokens['--color-bg-surface']);
    const probe115Cr = getContrast(darkDelBorder, darkTokens['--color-bg-surface']);
    expect(probe115Cr, 'WorkspaceList former deleting border on dark surface fails 3.0:1').toBeLessThan(3.0);
    expect(probe115Cr).toBeCloseTo(1.42, 1);

    // Probe 116 [Card 271]: NodeList former copy feedback text #4ade80 on light surface strictly fails 4.5:1
    const probe116Cr = getContrast('#4ade80', lightTokens['--color-bg-surface']);
    expect(probe116Cr, 'NodeList former copy feedback #4ade80 on light surface fails 4.5:1').toBeLessThan(4.5);
    expect(probe116Cr).toBeCloseTo(1.74, 1);

    // Probe 117 [Card 271]: NodeList former active notice border rgba(56,189,248,0.3) on light surface strictly fails 3.0:1
    const lightActiveBorder = blendRgba([56, 189, 248], 0.3, lightTokens['--color-bg-surface']);
    const probe117Cr = getContrast(lightActiveBorder, lightTokens['--color-bg-surface']);
    expect(probe117Cr, 'NodeList former active notice border on light surface fails 3.0:1').toBeLessThan(3.0);
    expect(probe117Cr).toBeCloseTo(1.26, 1);

    // Probe 118 [Card 271]: NodeList former active notice border rgba(56,189,248,0.3) on dark surface strictly fails 3.0:1
    const darkActiveBorder = blendRgba([56, 189, 248], 0.3, darkTokens['--color-bg-surface']);
    const probe118Cr = getContrast(darkActiveBorder, darkTokens['--color-bg-surface']);
    expect(probe118Cr, 'NodeList former active notice border on dark surface fails 3.0:1').toBeLessThan(3.0);
    expect(probe118Cr).toBeCloseTo(1.88, 1);

    // Probe 119 [Card 271]: NodeList online status badge synchronized mutation to var(--color-text-inverse) on light subtle strictly fails 4.5:1
    const probe119Cr = getContrast(lightTokens['--color-text-inverse'], lightTokens['--color-bg-subtle']);
    expect(probe119Cr, 'Synchronized text-inverse mutation on light subtle fails 4.5:1').toBeLessThan(4.5);
    expect(probe119Cr).toBeCloseTo(1.10, 1);

    // Probe 120 [Card 271]: NodeList active status badge synchronized mutation to var(--color-text-inverse) on light subtle strictly fails 4.5:1
    const probe120Cr = getContrast(lightTokens['--color-text-inverse'], lightTokens['--color-bg-subtle']);
    expect(probe120Cr, 'Synchronized text-inverse mutation on light subtle fails 4.5:1').toBeLessThan(4.5);
    expect(probe120Cr).toBeCloseTo(1.10, 1);

    // Probe 121 [Card 273]: ExecutionResultView former success badge text (#059669) on former rgba(16, 185, 129, 0.15) over light surface composite (#dbf4ec) strictly fails 4.5:1
    const lightSuccessComp = blendRgba([16, 185, 129], 0.15, lightTokens['--color-bg-surface']);
    const probe121Cr = getContrast('#059669', lightSuccessComp);
    expect(probe121Cr, 'ExecutionResultView former success badge on light surface composite strictly fails 4.5:1').toBeLessThan(4.5);
    expect(probe121Cr).toBeCloseTo(3.26, 1);

    // Probe 122 [Card 273]: RiskBadge synchronized mutation to var(--color-text-inverse) on light subtle strictly fails 4.5:1
    const probe122Cr = getContrast(lightTokens['--color-text-inverse'], lightTokens['--color-bg-subtle']);
    expect(probe122Cr, 'RiskBadge synchronized text-inverse mutation on light subtle fails 4.5:1').toBeLessThan(4.5);
    expect(probe122Cr).toBeCloseTo(1.10, 1);

    // Probe 123 [Card 273]: Button primary text mutated to var(--color-text-muted) on primary bg strictly fails 4.5:1
    const probe123Cr = getContrast(lightTokens['--color-text-muted'], lightTokens['--color-brand-primary-bg']);
    expect(probe123Cr, 'Button text-muted on primary bg fails 4.5:1').toBeLessThan(4.5);
    expect(probe123Cr).toBeCloseTo(1.11, 1);

    // Probe 124 [Card 273]: Button danger text mutated to var(--color-text-secondary) on offline bg strictly fails 4.5:1
    const probe124Cr = getContrast(lightTokens['--color-text-secondary'], lightTokens['--color-status-offline-bg']);
    expect(probe124Cr, 'Button secondary text on offline bg fails 4.5:1').toBeLessThan(4.5);
    expect(probe124Cr).toBeCloseTo(1.57, 1);

    // Probe 125 [Card 273]: RiskBadge former 15% red tint border rgba(239, 68, 68, 0.15) on light subtle fails 3.0:1
    const lightRedTint = blendRgba([239, 68, 68], 0.15, lightTokens['--color-bg-subtle']);
    const probe125Cr = getContrast(lightRedTint, lightTokens['--color-bg-subtle']);
    expect(probe125Cr, 'RiskBadge former 15% red tint border on light subtle fails 3.0:1').toBeLessThan(3.0);
    expect(probe125Cr).toBeCloseTo(1.21, 1);

    // Probe 126 [Card 274]: Hardcoded #ffffff text on dark --color-status-online (#22c55e) strictly fails 4.5:1
    const probe126Cr = getContrast('#ffffff', darkTokens['--color-status-online']);
    expect(probe126Cr, 'Hardcoded #ffffff text on dark status-online strictly fails 4.5:1').toBeLessThan(4.5);
    expect(probe126Cr).toBeCloseTo(2.28, 1);

    // Probe 127 [Card 274]: Former ResourceTopologyGraph selected card bg rgba(16, 185, 129, 0.08) border contrast on light surface fails 3.0:1
    const lightGreenComp = blendRgba([16, 185, 129], 0.08, lightTokens['--color-bg-surface']);
    const probe127Cr = getContrast(lightGreenComp, lightTokens['--color-bg-surface']);
    expect(probe127Cr, 'ResourceTopologyGraph former selected card bg tint on light surface fails 3.0:1').toBeLessThan(3.0);
    expect(probe127Cr).toBeCloseTo(1.08, 1);

    // Probe 128 [Card 274]: Former PlacementExplainView simulation badge #d97706 text on light surface composite fails 4.5:1
    const lightAmberComp = blendRgba([234, 179, 8], 0.15, lightTokens['--color-bg-surface']);
    const probe128Cr = getContrast('#d97706', lightAmberComp);
    expect(probe128Cr, 'PlacementExplainView former simulation badge text on light composite fails 4.5:1').toBeLessThan(4.5);
    expect(probe128Cr).toBeCloseTo(2.90, 1);

    // Probe 129 [Card 274]: Former PlacementExplainView simulation badge border rgba(234, 179, 8, 0.3) on composite fails 3.0:1
    const lightAmberBorderComp = blendRgba([234, 179, 8], 0.30, lightTokens['--color-bg-surface']);
    const probe129Cr = getContrast(lightAmberBorderComp, lightAmberComp);
    expect(probe129Cr, 'PlacementExplainView former simulation badge border on composite fails 3.0:1').toBeLessThan(3.0);
    expect(probe129Cr).toBeCloseTo(1.11, 1);

    // Probe 130 [Card 274]: NodeDetail former observation callout text mutated to --color-text-inverse (#ffffff) on light subtle strictly fails 4.5:1
    const probe130Cr = getContrast(lightTokens['--color-text-inverse'], lightTokens['--color-bg-subtle']);
    expect(probe130Cr, 'NodeDetail observation text-inverse mutation on light subtle fails 4.5:1').toBeLessThan(4.5);
    expect(probe130Cr).toBeCloseTo(1.10, 1);

    // Probe 131 [Card 275]: Former EvidenceViewer unverified badge #d97706 on light surface composite strictly fails 4.5:1
    const lightAmberComp275 = blendRgba([234, 179, 8], 0.15, lightTokens['--color-bg-surface']);
    const probe131Cr = getContrast('#d97706', lightAmberComp275);
    expect(probe131Cr, 'EvidenceViewer former unverified badge text on light composite fails 4.5:1').toBeLessThan(4.5);
    expect(probe131Cr).toBeCloseTo(2.90, 1);

    // Probe 132 [Card 275]: Former EvidenceViewer RUN_FAILED notice text #f87171 on light risk-l3 composite fails 4.5:1
    const lightRedNoticeComp275 = blendRgba([248, 81, 73], 0.08, lightTokens['--color-bg-surface']);
    const probe132Cr = getContrast('#f87171', lightRedNoticeComp275);
    expect(probe132Cr, 'EvidenceViewer former RUN_FAILED notice text on light composite fails 4.5:1').toBeLessThan(4.5);
    expect(probe132Cr).toBeCloseTo(2.51, 1);

    // Probe 133 [Card 275]: Former EvidenceViewer PASS badge border rgba(16, 185, 129, 0.15) on light surface fails 3.0:1
    const lightPassBorderComp275 = blendRgba([16, 185, 129], 0.15, lightTokens['--color-bg-surface']);
    const probe133Cr = getContrast(lightPassBorderComp275, lightTokens['--color-bg-surface']);
    expect(probe133Cr, 'EvidenceViewer former PASS badge border on light surface fails 3.0:1').toBeLessThan(3.0);
    expect(probe133Cr).toBeCloseTo(1.16, 1);

    // Probe 134 [Card 275]: Former EvidenceViewer UNVERIFIED notice border rgba(234, 179, 8, 0.3) on light surface fails 3.0:1
    const lightUnverifiedBorderComp275 = blendRgba([234, 179, 8], 0.30, lightTokens['--color-bg-surface']);
    const probe134Cr = getContrast(lightUnverifiedBorderComp275, lightTokens['--color-bg-surface']);
    expect(probe134Cr, 'EvidenceViewer former UNVERIFIED notice border on light surface fails 3.0:1').toBeLessThan(3.0);
    expect(probe134Cr).toBeCloseTo(1.22, 1);

    // Probe 135 [Card 275]: Former EvidenceViewer copy feedback #10b981 on light surface fails 4.5:1
    const probe135Cr = getContrast('#10b981', lightTokens['--color-bg-surface']);
    expect(probe135Cr, 'EvidenceViewer former copy feedback text #10b981 on light surface fails 4.5:1').toBeLessThan(4.5);
    expect(probe135Cr).toBeCloseTo(2.54, 1);

    // Probe 136 [Card 276]: Former ApprovalDetail bound version badge text #58a6ff on light subtle composite strictly fails 4.5:1
    const lightSubtleComp276 = blendRgba([56, 139, 253], 0.15, lightTokens['--color-bg-subtle']);
    const probe136Cr = getContrast('#58a6ff', lightSubtleComp276);
    expect(probe136Cr, 'ApprovalDetail former bound version text on light composite fails 4.5:1').toBeLessThan(4.5);
    expect(probe136Cr).toBeCloseTo(1.97, 1);

    // Probe 137 [Card 276]: Former Header user pill border rgba(56, 139, 253, 0.3) on light surface composite strictly fails 3.0:1
    const lightPillBorderComp276 = blendRgba([56, 139, 253], 0.30, lightTokens['--color-bg-surface']);
    const probe137Cr = getContrast(lightPillBorderComp276, lightTokens['--color-bg-surface']);
    expect(probe137Cr, 'Header former user pill border on light surface fails 3.0:1').toBeLessThan(3.0);
    expect(probe137Cr).toBeCloseTo(1.40, 1);

    // Probe 138 [Card 276]: Former Header user name #58a6ff on light surface composite strictly fails 4.5:1
    const lightUserNameComp276 = blendRgba([56, 139, 253], 0.12, lightTokens['--color-bg-surface']);
    const probe138Cr = getContrast('#58a6ff', lightUserNameComp276);
    expect(probe138Cr, 'Header former user name on light composite fails 4.5:1').toBeLessThan(4.5);
    expect(probe138Cr).toBeCloseTo(2.22, 1);

    // Probe 139 [Card 276]: Former Header role badge text #79c0ff on light surface composite strictly fails 4.5:1
    const lightRoleComp276 = blendRgba([56, 139, 253], 0.25, lightTokens['--color-bg-surface']);
    const probe139Cr = getContrast('#79c0ff', lightRoleComp276);
    expect(probe139Cr, 'Header former role badge text on light composite fails 4.5:1').toBeLessThan(4.5);
    expect(probe139Cr).toBeCloseTo(1.47, 1);

    // Probe 140 [Card 276]: Former Header Web Desktop button text #60a5fa on light surface composite strictly fails 4.5:1
    const lightDesktopComp276 = blendRgba([59, 130, 246], 0.20, lightTokens['--color-bg-surface']);
    const probe140Cr = getContrast('#60a5fa', lightDesktopComp276);
    expect(probe140Cr, 'Header former Web Desktop button text on light composite fails 4.5:1').toBeLessThan(4.5);
    expect(probe140Cr).toBeCloseTo(2.02, 1);

    // Probe 141 [Card 277]: Former workspace-error text #fca5a5 on light canvas fails 4.5:1 (1.81:1)
    const probe141Cr = getContrast('#fca5a5', lightTokens['--color-bg-canvas']);
    expect(probe141Cr, 'App former workspace-error text #fca5a5 on light canvas fails 4.5:1').toBeLessThan(4.5);
    expect(probe141Cr).toBeCloseTo(1.81, 1);

    // Probe 142 [Card 277]: Former terminal notice text #fed7aa on light surface fails 4.5:1 (1.35:1)
    const probe142Cr = getContrast('#fed7aa', lightTokens['--color-bg-surface']);
    expect(probe142Cr, 'App former terminal notice text #fed7aa on light surface fails 4.5:1').toBeLessThan(4.5);
    expect(probe142Cr).toBeCloseTo(1.35, 1);

    // Probe 143 [Card 277]: Former workspace-error text #fca5a5 on rgba(239, 68, 68, 0.1) over light canvas composite fails 4.5:1 (1.60:1)
    const lightWorkspaceComp277 = blendRgba([239, 68, 68], 0.10, lightTokens['--color-bg-canvas']);
    const probe143Cr = getContrast('#fca5a5', lightWorkspaceComp277);
    expect(probe143Cr, 'App former workspace-error text on light composite fails 4.5:1').toBeLessThan(4.5);
    expect(probe143Cr).toBeCloseTo(1.60, 1);

    // Probe 144 [Card 277]: Former nodeSimState button text #ffffff on light subtle fails 4.5:1 (1.10:1)
    const probe144Cr = getContrast('#ffffff', lightTokens['--color-bg-subtle']);
    expect(probe144Cr, 'App former nodeSimState button text #ffffff on light subtle fails 4.5:1').toBeLessThan(4.5);
    expect(probe144Cr).toBeCloseTo(1.10, 1);

    // Probe 145 [Card 277]: Former terminal notice text #fed7aa on light subtle fails 4.5:1 (1.24:1)
    const probe145Cr = getContrast('#fed7aa', lightTokens['--color-bg-subtle']);
    expect(probe145Cr, 'App former terminal notice text #fed7aa on light subtle fails 4.5:1').toBeLessThan(4.5);
    expect(probe145Cr).toBeCloseTo(1.24, 1);

    // Probe 146 [Card 278]: Former traffic light minimize #f59e0b on light subtle fails 3.0:1 (1.96:1)
    const probe146Cr = getContrast('#f59e0b', lightTokens['--color-bg-subtle']);
    expect(probe146Cr, 'DesktopWindow former minimize button #f59e0b on light subtle fails 3.0:1').toBeLessThan(3.0);
    expect(probe146Cr).toBeCloseTo(1.96, 1);

    // Probe 147 [Card 278]: Former traffic light maximize #10b981 on light subtle fails 3.0:1 (2.32:1)
    const probe147Cr = getContrast('#10b981', lightTokens['--color-bg-subtle']);
    expect(probe147Cr, 'DesktopWindow former maximize button #10b981 on light subtle fails 3.0:1').toBeLessThan(3.0);
    expect(probe147Cr).toBeCloseTo(2.32, 1);

    // Probe 148 [Card 278]: Former traffic light minimize #f59e0b on light surface fails 3.0:1 (2.15:1)
    const probe148Cr = getContrast('#f59e0b', lightTokens['--color-bg-surface']);
    expect(probe148Cr, 'DesktopWindow former minimize button #f59e0b on light surface fails 3.0:1').toBeLessThan(3.0);
    expect(probe148Cr).toBeCloseTo(2.15, 1);

    // Probe 149 [Card 278]: Former inactive title text #94a3b8 on light subtle fails 4.5:1 (2.34:1)
    const probe149Cr = getContrast('#94a3b8', lightTokens['--color-bg-subtle']);
    expect(probe149Cr, 'DesktopWindow former inactive title text #94a3b8 on light subtle fails 4.5:1').toBeLessThan(4.5);
    expect(probe149Cr).toBeCloseTo(2.34, 1);

    // Probe 150 [Card 278]: Former appId text #64748b on dark title bar #0f172a fails 4.5:1 (3.75:1)
    const probe150Cr = getContrast('#64748b', '#0f172a');
    expect(probe150Cr, 'DesktopWindow former appId text #64748b on dark title bar #0f172a fails 4.5:1').toBeLessThan(4.5);
    expect(probe150Cr).toBeCloseTo(3.75, 1);

    // Probe 151 [Card 279]: Former powershell text #38bdf8 on light subtle fails 4.5:1 (1.96:1)
    const probe151Cr = getContrast('#38bdf8', lightTokens['--color-bg-subtle']);
    expect(probe151Cr, 'TerminalSessionView former powershell text #38bdf8 on light subtle fails 4.5:1').toBeLessThan(4.5);
    expect(probe151Cr).toBeCloseTo(1.96, 1);

    // Probe 152 [Card 279]: Former bash text #4ade80 on light subtle fails 4.5:1 (1.59:1)
    const probe152Cr = getContrast('#4ade80', lightTokens['--color-bg-subtle']);
    expect(probe152Cr, 'TerminalSessionView former bash text #4ade80 on light subtle fails 4.5:1').toBeLessThan(4.5);
    expect(probe152Cr).toBeCloseTo(1.59, 1);

    // Probe 153 [Card 279]: Former zsh text #fbbf24 on light subtle fails 4.5:1 (1.52:1)
    const probe153Cr = getContrast('#fbbf24', lightTokens['--color-bg-subtle']);
    expect(probe153Cr, 'TerminalSessionView former zsh text #fbbf24 on light subtle fails 4.5:1').toBeLessThan(4.5);
    expect(probe153Cr).toBeCloseTo(1.52, 1);

    // Probe 154 [Card 279]: Former terminal operator notice text #fed7aa on light subtle fails 4.5:1 (1.24:1)
    const probe154Cr = getContrast('#fed7aa', lightTokens['--color-bg-subtle']);
    expect(probe154Cr, 'TerminalSessionView former operator notice #fed7aa on light subtle fails 4.5:1').toBeLessThan(4.5);
    expect(probe154Cr).toBeCloseTo(1.24, 1);

    // Probe 155 [Card 279]: Former switch-mode button text #60a5fa on light subtle fails 4.5:1 (2.32:1)
    const probe155Cr = getContrast('#60a5fa', lightTokens['--color-bg-subtle']);
    expect(probe155Cr, 'TerminalSessionView former switch-mode text #60a5fa on light subtle fails 4.5:1').toBeLessThan(4.5);
    expect(probe155Cr).toBeCloseTo(2.32, 1);

    // Probe 156 [Card 280]: ConflictResolutionModal baseline raw #f85149 on light canvas fails 4.5:1 (3.20:1)
    const probe156Cr = getContrast('#f85149', lightTokens['--color-bg-canvas']);
    expect(probe156Cr, 'ConflictResolutionModal former raw #f85149 on light canvas fails 4.5:1').toBeLessThan(4.5);
    expect(probe156Cr).toBeCloseTo(3.20, 1);

    // Probe 157 [Card 280]: DiffViewer baseline raw #3fb950 on 15% tint over light surface fails 4.5:1 (2.16:1)
    const lightSurfaceCompositeDiffGreen = blendRgba([46, 160, 67], 0.15, lightTokens['--color-bg-surface']);
    const probe157Cr = getContrast('#3fb950', lightSurfaceCompositeDiffGreen);
    expect(probe157Cr, 'DiffViewer former raw #3fb950 on 15% tint fails 4.5:1').toBeLessThan(4.5);
    expect(probe157Cr).toBeCloseTo(2.16, 1);

    // Probe 158 [Card 280]: DiffViewer baseline raw #f85149 on 15% tint over light surface fails 4.5:1 (2.80:1)
    const lightSurfaceCompositeDiffRed = blendRgba([248, 81, 73], 0.15, lightTokens['--color-bg-surface']);
    const probe158Cr = getContrast('#f85149', lightSurfaceCompositeDiffRed);
    expect(probe158Cr, 'DiffViewer former raw #f85149 on 15% tint fails 4.5:1').toBeLessThan(4.5);
    expect(probe158Cr).toBeCloseTo(2.80, 1);

    // Probe 159 [Card 280]: GitCommitModal baseline raw #e3b341 on light canvas fails 4.5:1 (1.86:1)
    const probe159Cr = getContrast('#e3b341', lightTokens['--color-bg-canvas']);
    expect(probe159Cr, 'GitCommitModal former raw #e3b341 on light canvas fails 4.5:1').toBeLessThan(4.5);
    expect(probe159Cr).toBeCloseTo(1.86, 1);

    // Probe 160 [Card 280]: GitCommitModal baseline raw #58a6ff on light surface fails 4.5:1 (2.53:1)
    const probe160Cr = getContrast('#58a6ff', lightTokens['--color-bg-surface']);
    expect(probe160Cr, 'GitCommitModal former raw #58a6ff on light surface fails 4.5:1').toBeLessThan(4.5);
    expect(probe160Cr).toBeCloseTo(2.53, 1);

    // Probe 161 [Card 281]: MonacoWorkspaceEditor baseline raw #58a6ff on light canvas fails 4.5:1 (2.41:1)
    const probe161Cr = getContrast('#58a6ff', lightTokens['--color-bg-canvas']);
    expect(probe161Cr, 'MonacoWorkspaceEditor former raw #58a6ff on light canvas fails 4.5:1').toBeLessThan(4.5);
    expect(probe161Cr).toBeCloseTo(2.41, 1);

    // Probe 162 [Card 281]: MonacoWorkspaceEditor baseline raw #8b949e on light subtle fails 4.5:1 (2.81:1)
    const probe162Cr = getContrast('#8b949e', lightTokens['--color-bg-subtle']);
    expect(probe162Cr, 'MonacoWorkspaceEditor former raw #8b949e on light subtle fails 4.5:1').toBeLessThan(4.5);
    expect(probe162Cr).toBeCloseTo(2.81, 1);

    // Probe 163 [Card 281]: MonacoWorkspaceEditor baseline raw #e3b341 on light surface fails 4.5:1 (1.95:1)
    const probe163Cr = getContrast('#e3b341', lightTokens['--color-bg-surface']);
    expect(probe163Cr, 'MonacoWorkspaceEditor former raw #e3b341 on light surface fails 4.5:1').toBeLessThan(4.5);
    expect(probe163Cr).toBeCloseTo(1.95, 1);

    // Probe 164 [Card 281]: MonacoWorkspaceEditor baseline raw #3fb950 on light canvas fails 4.5:1 (2.43:1)
    const probe164Cr = getContrast('#3fb950', lightTokens['--color-bg-canvas']);
    expect(probe164Cr, 'MonacoWorkspaceEditor former raw #3fb950 on light canvas fails 4.5:1').toBeLessThan(4.5);
    expect(probe164Cr).toBeCloseTo(2.43, 1);

    // Probe 165 [Card 281]: MonacoWorkspaceEditor baseline raw #f85149 on light canvas fails 4.5:1 (3.20:1)
    const probe165Cr = getContrast('#f85149', lightTokens['--color-bg-canvas']);
    expect(probe165Cr, 'MonacoWorkspaceEditor former raw #f85149 on light canvas fails 4.5:1').toBeLessThan(4.5);
    expect(probe165Cr).toBeCloseTo(3.20, 1);

    // Probe 166 [Card 282]: WebTerminal baseline raw #fb923c on light canvas fails 4.5:1 (2.16:1)
    const probe166Cr = getContrast('#fb923c', lightTokens['--color-bg-canvas']);
    expect(probe166Cr, 'WebTerminal former raw #fb923c on light canvas fails 4.5:1').toBeLessThan(4.5);
    expect(probe166Cr).toBeCloseTo(2.16, 1);

    // Probe 167 [Card 282]: WebTerminal baseline raw #fecaca on light canvas fails 4.5:1 (1.38:1)
    const probe167Cr = getContrast('#fecaca', lightTokens['--color-bg-canvas']);
    expect(probe167Cr, 'WebTerminal former raw #fecaca on light canvas fails 4.5:1').toBeLessThan(4.5);
    expect(probe167Cr).toBeCloseTo(1.38, 1);

    // Probe 168 [Card 282]: WebTerminal baseline raw #fde68a on light canvas fails 4.5:1 (1.19:1)
    const probe168Cr = getContrast('#fde68a', lightTokens['--color-bg-canvas']);
    expect(probe168Cr, 'WebTerminal former raw #fde68a on light canvas fails 4.5:1').toBeLessThan(4.5);
    expect(probe168Cr).toBeCloseTo(1.19, 1);

    // Probe 169 [Card 282]: WebTerminal baseline raw #ef4444 on light canvas fails 4.5:1 (3.60:1)
    const probe169Cr = getContrast('#ef4444', lightTokens['--color-bg-canvas']);
    expect(probe169Cr, 'WebTerminal former raw #ef4444 on light canvas fails 4.5:1').toBeLessThan(4.5);
    expect(probe169Cr).toBeCloseTo(3.60, 1);

    // Probe 170 [Card 282]: WebTerminal baseline raw #238636 on light canvas fails 4.5:1 (4.43:1)
    const probe170Cr = getContrast('#238636', lightTokens['--color-bg-canvas']);
    expect(probe170Cr, 'WebTerminal former raw #238636 on light canvas fails 4.5:1').toBeLessThan(4.5);
    expect(probe170Cr).toBeCloseTo(4.43, 1);



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

  // 10. [F2 Fail-Closed Multiset Inventory & Ratchet] var(--color-border-subtle) exact 458/31 and exact per-file literal multisets strictly bounded
  it('ACC-09 / F2 Fail-Closed Multiset Inventory & Ratchet: var(--color-border-subtle) exact 458/31 and exact per-file literal multisets strictly bounded', () => {
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
    expect(borderSubtleCount, 'var(--color-border-subtle) exact occurrence count in apps/web/src must be 487').toBe(487);
    expect(borderSubtleFiles.size, 'var(--color-border-subtle) file count in apps/web/src must be 36').toBe(36);

    // Fail-closed check 3: Total files with color literals must not exceed baseline file count
    const baselineFileCount = Object.keys(COLOR_LITERAL_MULTISET_BASELINE).length;
    expect(Object.keys(observedFileMultisets).length, 'Total files with color literals must not exceed baseline').toBeLessThanOrEqual(baselineFileCount);

    // ACC-09 Milestone Grand Completion Invariant: All registered files in COLOR_LITERAL_MULTISET_BASELINE must have empty multiset ({})
    for (const [file, multiset] of Object.entries(COLOR_LITERAL_MULTISET_BASELINE)) {
      expect(
        Object.keys(multiset).length,
        `File ${file} in COLOR_LITERAL_MULTISET_BASELINE must be empty (0 color literals remaining in ACC-09)`
      ).toBe(0);
    }
    expect(Object.keys(observedFileMultisets).length, 'Zero files with color literals must remain across entire apps/web/src').toBe(0);

    // Ratchet assertions for specific legacy literals (occurrences & files)
    expect(legacyCounts['#64748b'], 'Legacy #64748b literal count must not exceed 1').toBeLessThanOrEqual(1);
    expect(legacyFiles['#64748b'].size, 'Legacy #64748b file count must not exceed 1').toBeLessThanOrEqual(1);

    expect(legacyCounts['#d97706'], 'Legacy #d97706 literal count must not exceed 4').toBeLessThanOrEqual(4);
    expect(legacyFiles['#d97706'].size, 'Legacy #d97706 file count must not exceed 2').toBeLessThanOrEqual(2);

    expect(legacyCounts['#e2e8f0'], 'Legacy #e2e8f0 literal count must not exceed 0').toBeLessThanOrEqual(0);
    expect(legacyFiles['#e2e8f0'].size, 'Legacy #e2e8f0 file count must not exceed 0').toBeLessThanOrEqual(0);

    expect(legacyCounts['#dc2626'], 'Legacy #dc2626 literal count must not exceed 1').toBeLessThanOrEqual(1);
    expect(legacyFiles['#dc2626'].size, 'Legacy #dc2626 file count must not exceed 1').toBeLessThanOrEqual(1);

    expect(legacyCounts['#30363d'], 'Legacy #30363d literal count must not exceed 22').toBeLessThanOrEqual(22);
    expect(legacyFiles['#30363d'].size, 'Legacy #30363d file count must not exceed 6').toBeLessThanOrEqual(6);
  }, 30000);

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
