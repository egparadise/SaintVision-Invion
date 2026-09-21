// @vitest-environment happy-dom
import React, { act } from 'react';
import { createRoot, Root } from 'react-dom/client';
import { describe, it, expect, vi, beforeEach, afterEach } from 'vitest';
import { DeveloperStudio } from '../src/features/studio/DeveloperStudio';
import * as projectObservation from '../src/shared/api/projectObservation';
import type { ProjectItem, RunItem } from '../src/contracts/types';

const sampleProject: ProjectItem = {
  id: 'prj_status_test',
  name: 'Status Test Project',
};

const sampleRun: RunItem = {
  id: 'run_sample',
  projectId: 'prj_status_test',
  status: 'succeeded',
  state: 'succeeded',
  targetNodeId: 'nod_test',
  createdAt: '2026-09-21T10:00:00Z',
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

  it('renders "ready" workspace with green badge (#3fb950 and rgba(46, 160, 67, 0.2))', async () => {
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

    // Wait for state update
    await act(async () => {
      await Promise.resolve();
    });

    const badge = container.querySelector('[data-testid="studio-wsp-status-wsp_ready_01"]') as HTMLElement;
    expect(badge).not.toBeNull();
    expect(badge.textContent).toBe('ready');
    expect(badge.style.color).toBe('#3fb950');
    expect(badge.style.backgroundColor).toContain('rgba(46, 160, 67, 0.2)');
  });

  it('renders "provisioning" workspace with warning amber badge', async () => {
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
    expect(badge.style.color).toBe('#d29922');
    expect(badge.style.backgroundColor).toContain('rgba(210, 153, 34, 0.2)');
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
    expect(delBadge.style.color).toBe('#f85149');
    expect(delBadge.style.backgroundColor).toContain('rgba(248, 81, 73, 0.2)');

    const suspBadge = container.querySelector('[data-testid="studio-wsp-status-wsp_susp_01"]') as HTMLElement;
    expect(suspBadge).not.toBeNull();
    expect(suspBadge.textContent).toBe('suspended');
    expect(suspBadge.style.color).toBe('var(--color-text-muted)');
  });
});
