import React from 'react';
import { describe, it, expect } from 'vitest';
import { renderToStaticMarkup } from 'react-dom/server';
import { WorkspaceList } from '../src/features/workspaces/WorkspaceList';
import { WorkspaceItem, NodeItem } from '../src/contracts/types';

describe('WorkspaceList Canonical 5-State Contract & Unknown Handling', () => {
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

  it('renders all 5 canonical backend states honestly without active/terminating/reclaimed dead branches', () => {
    const workspaces: WorkspaceItem[] = [
      {
        id: 'wsp_01',
        projectId: 'prj_pacs',
        name: 'Ready Workspace',
        targetNodeId: 'nod_01JABCDEF01',
        isolationMode: 'process_sandbox',
        allowedPaths: ['./workspace'],
        prohibitedPaths: ['/etc'],
        cpuLimitCores: 4,
        memoryLimitBytes: 8 * 1024 ** 3,
        status: 'ready',
        createdAt: '2026-09-22T00:00:00Z',
      },
      {
        id: 'wsp_02',
        projectId: 'prj_pacs',
        name: 'Provisioning Workspace',
        targetNodeId: 'nod_01JABCDEF01',
        isolationMode: 'process_sandbox',
        allowedPaths: ['./workspace'],
        prohibitedPaths: ['/etc'],
        cpuLimitCores: 4,
        memoryLimitBytes: 8 * 1024 ** 3,
        status: 'provisioning',
        createdAt: '2026-09-22T00:00:00Z',
      },
      {
        id: 'wsp_03',
        projectId: 'prj_pacs',
        name: 'Suspended Workspace',
        targetNodeId: 'nod_01JABCDEF01',
        isolationMode: 'process_sandbox',
        allowedPaths: ['./workspace'],
        prohibitedPaths: ['/etc'],
        cpuLimitCores: 4,
        memoryLimitBytes: 8 * 1024 ** 3,
        status: 'suspended',
        createdAt: '2026-09-22T00:00:00Z',
      },
      {
        id: 'wsp_04',
        projectId: 'prj_pacs',
        name: 'Deleting Workspace',
        targetNodeId: 'nod_01JABCDEF01',
        isolationMode: 'process_sandbox',
        allowedPaths: ['./workspace'],
        prohibitedPaths: ['/etc'],
        cpuLimitCores: 4,
        memoryLimitBytes: 8 * 1024 ** 3,
        status: 'deleting',
        createdAt: '2026-09-22T00:00:00Z',
      },
      {
        id: 'wsp_05',
        projectId: 'prj_pacs',
        name: 'Deleted Workspace',
        targetNodeId: null,
        isolationMode: 'process_sandbox',
        allowedPaths: ['./workspace'],
        prohibitedPaths: ['/etc'],
        cpuLimitCores: 4,
        memoryLimitBytes: 8 * 1024 ** 3,
        status: 'deleted',
        createdAt: '2026-09-22T00:00:00Z',
      },
    ];

    const html = renderToStaticMarkup(
      <WorkspaceList
        workspaces={workspaces}
        nodes={sampleNodes}
        onCreateWorkspace={() => {}}
        onSelectWorkspace={() => {}}
      />
    );

    expect(html).toContain('준비 완료 (Ready)');
    expect(html).toContain('프로비저닝 중 (Provisioning)');
    expect(html).toContain('일시 중단 (Suspended)');
    expect(html).toContain('삭제 중 (Deleting)');
    expect(html).toContain('삭제됨 (Deleted)');

    // Ensure legacy virtual names are NOT used
    expect(html).not.toContain('회수/삭제됨 (Reclaimed)');
  });

  it('honestly renders unrecognized future status without silent promotion or fallback', () => {
    const unknownWsp = {
      id: 'wsp_06',
      projectId: 'prj_pacs',
      name: 'Future Status Workspace',
      targetNodeId: null,
      isolationMode: 'process_sandbox' as const,
      allowedPaths: ['./workspace'],
      prohibitedPaths: ['/etc'],
      cpuLimitCores: 4,
      memoryLimitBytes: 8 * 1024 ** 3,
      status: 'migrating_cluster' as any, // Simulating wire value outside known 5
      createdAt: '2026-09-22T00:00:00Z',
    };

    const html = renderToStaticMarkup(
      <WorkspaceList
        workspaces={[unknownWsp]}
        nodes={sampleNodes}
        onCreateWorkspace={() => {}}
        onSelectWorkspace={() => {}}
      />
    );

    expect(html).toContain('미확인 상태 (migrating_cluster)');
    // Must never silently convert to ready or deleted
    expect(html).not.toContain('준비 완료 (Ready)');
    expect(html).not.toContain('삭제됨 (Deleted)');
  });
});
