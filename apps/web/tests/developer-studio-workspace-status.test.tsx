// @vitest-environment happy-dom
import React, { act } from 'react';
import { createRoot, Root } from 'react-dom/client';
import { describe, it, expect, vi, beforeEach, afterEach } from 'vitest';
import fs from 'node:fs';
import path from 'node:path';
import { DeveloperStudio } from '../src/features/studio/DeveloperStudio';
import * as projectObservation from '../src/shared/api/projectObservation';
import type { ProjectItem, RunItem } from '../src/contracts/types';

const indexCss = fs.readFileSync(path.resolve(__dirname, '../src/index.css'), 'utf-8');

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

function extractTokens(block: string): Record<string, string> {
  const cleanBlock = block.replace(/\/\*[\s\S]*?\*\//g, '');
  const tokens: Record<string, string> = {};
  const regex = /(--color-[a-z0-9-]+)\s*:\s*([^;]+);/g;
  let match;
  while ((match = regex.exec(cleanBlock)) !== null) {
    const name = match[1].trim();
    const val = match[2].trim();
    if (val.startsWith('#')) {
      tokens[name] = val;
    }
  }
  return tokens;
}

const lightBlockMatch = indexCss.match(/:root\s*\{([^}]+)\}/);
const darkBlockMatch = indexCss.match(/\[data-theme=['"]dark['"]\]\s*\{([^}]+)\}/);
if (!lightBlockMatch || !darkBlockMatch) {
  throw new Error('Failed to extract token blocks from index.css');
}
const lightTokens = extractTokens(lightBlockMatch[1]);
const darkTokens = extractTokens(darkBlockMatch[1]);

function helperExtractVar(val: string): string {
  const m = val.match(/var\((--[a-z0-9-]+)\)/);
  if (!m) throw new Error(`Expected CSS variable in value: "${val}"`);
  return m[1];
}

const sampleProject: ProjectItem = {
  id: 'prj_status_test',
  name: 'Status Test Project',
};

describe('DeveloperStudio Workspace Status 5-State Contract Styling', () => {
  let container: HTMLDivElement;
  let root: Root;

  beforeEach(() => {
    (globalThis as any).IS_REACT_ACT_ENVIRONMENT = true;
    container = document.createElement('div');
    document.body.appendChild(container);
    root = createRoot(container);
  });

  afterEach(() => {
    act(() => {
      root.unmount();
    });
    container.remove();
    vi.restoreAllMocks();
  });

  it('renders "ready" workspace with semantic token badge and verified WCAG AA contrast', async () => {
    vi.spyOn(projectObservation, 'fetchProjectWorkspaces').mockResolvedValueOnce([
      {
        workspaceId: 'wsp_ready_01',
        projectId: 'prj_status_test',
        name: 'Ready Production Workspace',
        status: 'ready',
        nodeId: 'nod_01',
        toolName: 'python-pacs',
        createdAt: '2026-09-22T00:00:00Z',
        allowedNext: ['suspended', 'deleting'],
      },
    ]);

    await act(async () => {
      root.render(
        <DeveloperStudio
          project={sampleProject}
          nodes={[]}
          runs={[]}
          initialStep={1}
        />
      );
    });

    await act(async () => {
      await Promise.resolve();
    });

    const badge = container.querySelector('[data-testid="studio-wsp-status-wsp_ready_01"]') as HTMLElement;
    expect(badge).not.toBeNull();
    expect(badge.textContent).toBe('ready');
    expect(badge.style.color).toBe('var(--color-status-online)');
    expect(badge.style.backgroundColor).toBe('var(--color-bg-subtle)');
    expect(badge.style.borderColor).toBe('var(--color-status-online)');

    // Light/Dark contrast ratio assertions (F1 requirement)
    const fgVar = helperExtractVar(badge.style.color);
    const bgVar = helperExtractVar(badge.style.backgroundColor);
    const borderVar = helperExtractVar(badge.style.borderColor);

    const lightTextCr = getContrast(lightTokens[fgVar], lightTokens[bgVar]);
    const darkTextCr = getContrast(darkTokens[fgVar], darkTokens[bgVar]);
    expect(lightTextCr, 'Ready text contrast in light theme must be >= 4.5:1').toBeGreaterThanOrEqual(4.5);
    expect(darkTextCr, 'Ready text contrast in dark theme must be >= 4.5:1').toBeGreaterThanOrEqual(4.5);

    const lightBorderCr = getContrast(lightTokens[borderVar], lightTokens[bgVar]);
    const darkBorderCr = getContrast(darkTokens[borderVar], darkTokens[bgVar]);
    expect(lightBorderCr, 'Ready border contrast in light theme must be >= 3.0:1').toBeGreaterThanOrEqual(3.0);
    expect(darkBorderCr, 'Ready border contrast in dark theme must be >= 3.0:1').toBeGreaterThanOrEqual(3.0);
  });

  it('renders "provisioning" workspace with warning amber badge and verified contrast', async () => {
    vi.spyOn(projectObservation, 'fetchProjectWorkspaces').mockResolvedValueOnce([
      {
        workspaceId: 'wsp_prov_01',
        projectId: 'prj_status_test',
        name: 'Provisioning Workspace',
        status: 'provisioning',
        nodeId: 'nod_01',
        toolName: 'python-pacs',
        createdAt: '2026-09-22T00:00:00Z',
        allowedNext: ['ready', 'deleting'],
      },
    ]);

    await act(async () => {
      root.render(
        <DeveloperStudio
          project={sampleProject}
          nodes={[]}
          runs={[]}
          initialStep={1}
        />
      );
    });

    await act(async () => {
      await Promise.resolve();
    });

    const badge = container.querySelector('[data-testid="studio-wsp-status-wsp_prov_01"]') as HTMLElement;
    expect(badge).not.toBeNull();
    expect(badge.textContent).toBe('provisioning');
    expect(badge.style.color).toBe('var(--color-status-degraded)');
    expect(badge.style.backgroundColor).toBe('var(--color-bg-subtle)');
    expect(badge.style.borderColor).toBe('var(--color-status-degraded)');

    const fgVar = helperExtractVar(badge.style.color);
    const bgVar = helperExtractVar(badge.style.backgroundColor);
    const borderVar = helperExtractVar(badge.style.borderColor);

    const lightTextCr = getContrast(lightTokens[fgVar], lightTokens[bgVar]);
    const darkTextCr = getContrast(darkTokens[fgVar], darkTokens[bgVar]);
    expect(lightTextCr, 'Provisioning text contrast in light theme must be >= 4.5:1').toBeGreaterThanOrEqual(4.5);
    expect(darkTextCr, 'Provisioning text contrast in dark theme must be >= 4.5:1').toBeGreaterThanOrEqual(4.5);

    const lightBorderCr = getContrast(lightTokens[borderVar], lightTokens[bgVar]);
    const darkBorderCr = getContrast(darkTokens[borderVar], darkTokens[bgVar]);
    expect(lightBorderCr, 'Provisioning border contrast in light theme must be >= 3.0:1').toBeGreaterThanOrEqual(3.0);
    expect(darkBorderCr, 'Provisioning border contrast in dark theme must be >= 3.0:1').toBeGreaterThanOrEqual(3.0);
  });

  it('renders "deleting" workspace with danger red badge and "suspended" with muted badge', async () => {
    vi.spyOn(projectObservation, 'fetchProjectWorkspaces').mockResolvedValueOnce([
      {
        workspaceId: 'wsp_del_01',
        projectId: 'prj_status_test',
        name: 'Deleting Workspace',
        status: 'deleting',
        nodeId: 'nod_01',
        toolName: 'python-pacs',
        createdAt: '2026-09-22T00:00:00Z',
        allowedNext: ['deleted'],
      },
      {
        workspaceId: 'wsp_susp_01',
        projectId: 'prj_status_test',
        name: 'Suspended Workspace',
        status: 'suspended',
        nodeId: 'nod_01',
        toolName: 'python-pacs',
        createdAt: '2026-09-22T00:00:00Z',
        allowedNext: ['ready', 'deleting'],
      },
    ]);

    await act(async () => {
      root.render(
        <DeveloperStudio
          project={sampleProject}
          nodes={[]}
          runs={[]}
          initialStep={1}
        />
      );
    });

    await act(async () => {
      await Promise.resolve();
    });

    const delBadge = container.querySelector('[data-testid="studio-wsp-status-wsp_del_01"]') as HTMLElement;
    expect(delBadge).not.toBeNull();
    expect(delBadge.textContent).toBe('deleting');
    expect(delBadge.style.color).toBe('var(--color-status-offline)');
    expect(delBadge.style.backgroundColor).toBe('var(--color-bg-subtle)');
    expect(delBadge.style.borderColor).toBe('var(--color-status-offline)');

    const delFg = helperExtractVar(delBadge.style.color);
    const delBg = helperExtractVar(delBadge.style.backgroundColor);
    const delBorder = helperExtractVar(delBadge.style.borderColor);
    expect(getContrast(lightTokens[delFg], lightTokens[delBg]), 'Deleting text contrast in light theme >= 4.5:1').toBeGreaterThanOrEqual(4.5);
    expect(getContrast(darkTokens[delFg], darkTokens[delBg]), 'Deleting text contrast in dark theme >= 4.5:1').toBeGreaterThanOrEqual(4.5);
    expect(getContrast(lightTokens[delBorder], lightTokens[delBg]), 'Deleting border contrast in light theme >= 3.0:1').toBeGreaterThanOrEqual(3.0);
    expect(getContrast(darkTokens[delBorder], darkTokens[delBg]), 'Deleting border contrast in dark theme >= 3.0:1').toBeGreaterThanOrEqual(3.0);

    const suspBadge = container.querySelector('[data-testid="studio-wsp-status-wsp_susp_01"]') as HTMLElement;
    expect(suspBadge).not.toBeNull();
    expect(suspBadge.textContent).toBe('suspended');
    expect(suspBadge.style.color).toBe('var(--color-text-muted)');
    expect(suspBadge.style.backgroundColor).toBe('var(--color-bg-subtle)');
    expect(suspBadge.style.borderColor).toBe('var(--color-border-subtle)');

    const suspFg = helperExtractVar(suspBadge.style.color);
    const suspBg = helperExtractVar(suspBadge.style.backgroundColor);
    const suspBorder = helperExtractVar(suspBadge.style.borderColor);
    expect(getContrast(lightTokens[suspFg], lightTokens[suspBg]), 'Suspended text contrast in light theme >= 4.5:1').toBeGreaterThanOrEqual(4.5);
    expect(getContrast(darkTokens[suspFg], darkTokens[suspBg]), 'Suspended text contrast in dark theme >= 4.5:1').toBeGreaterThanOrEqual(4.5);
    expect(getContrast(lightTokens[suspBorder], lightTokens[suspBg]), 'Suspended border contrast in light theme >= 3.0:1').toBeGreaterThanOrEqual(3.0);
    expect(getContrast(darkTokens[suspBorder], darkTokens[suspBg]), 'Suspended border contrast in dark theme >= 3.0:1').toBeGreaterThanOrEqual(3.0);
  });

  it('renders default/unrecognized workspace status with fallback subtle token and verified contrast', async () => {
    vi.spyOn(projectObservation, 'fetchProjectWorkspaces').mockResolvedValueOnce([
      {
        workspaceId: 'wsp_other_01',
        projectId: 'prj_status_test',
        name: 'Unknown Status Workspace',
        status: 'archived' as any,
        nodeId: 'nod_01',
        toolName: 'python-pacs',
        createdAt: '2026-09-22T00:00:00Z',
        allowedNext: [],
      },
    ]);

    await act(async () => {
      root.render(
        <DeveloperStudio
          project={sampleProject}
          nodes={[]}
          runs={[]}
          initialStep={1}
        />
      );
    });

    await act(async () => {
      await Promise.resolve();
    });

    const otherBadge = container.querySelector('[data-testid="studio-wsp-status-wsp_other_01"]') as HTMLElement;
    expect(otherBadge).not.toBeNull();
    expect(otherBadge.textContent).toBe('archived');
    expect(otherBadge.style.color).toBe('var(--color-text-muted)');
    expect(otherBadge.style.backgroundColor).toBe('var(--color-bg-subtle)');
    expect(otherBadge.style.borderColor).toBe('var(--color-border-subtle)');

    const otherFg = helperExtractVar(otherBadge.style.color);
    const otherBg = helperExtractVar(otherBadge.style.backgroundColor);
    expect(getContrast(lightTokens[otherFg], lightTokens[otherBg]), 'Default status text contrast in light theme >= 4.5:1').toBeGreaterThanOrEqual(4.5);
    expect(getContrast(darkTokens[otherFg], darkTokens[otherBg]), 'Default status text contrast in dark theme >= 4.5:1').toBeGreaterThanOrEqual(4.5);
  });
});
