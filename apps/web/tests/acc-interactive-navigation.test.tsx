// @vitest-environment happy-dom
// @ts-ignore
globalThis.IS_REACT_ACT_ENVIRONMENT = true;
import React, { act } from 'react';
import { createRoot, Root } from 'react-dom/client';
import { describe, it, expect, vi, beforeEach, afterEach } from 'vitest';

import { ApprovalCenter } from '../src/features/approvals/ApprovalCenter';
import { NodeList } from '../src/features/nodes/NodeList';
import { RunList } from '../src/features/runs/RunList';
import { NaturalLanguageRunView } from '../src/features/agent/NaturalLanguageRunView';
import { DeveloperStudio } from '../src/features/studio/DeveloperStudio';
import { ResourceExplorer } from '../src/features/desktop/ResourceExplorer';
import * as fabricApi from '../src/features/desktop/fabricControlApi';
import * as storageObsApi from '../src/shared/api/storageObservation';
import * as projectObservation from '../src/shared/api/projectObservation';
import { ApprovalItem, NodeItem, RunItem, ProjectItem } from '../src/contracts/types';

describe('ACC-01~09 Interactive Navigation & Tablist WAI-ARIA Suite', () => {
  let container: HTMLDivElement;
  let root: Root;

  beforeEach(() => {
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

  // --------------------------------------------------------------------------
  // ACC-02: ApprovalCenter Keyboard Navigation
  // --------------------------------------------------------------------------
  it('ACC-02: ApprovalCenter approval cards have role=button, tabIndex=0, aria-pressed, and respond to Enter/Space keys', async () => {
    const mockApprovals: ApprovalItem[] = [
      {
        id: 'app-001',
        runId: 'run-101',
        actionType: 'deploy',
        status: 'pending',
        riskLevel: 'high',
        requestedBy: 'user-alice',
        requestedAt: '2026-10-01T12:00:00Z',
        description: 'Deploy to cluster alpha',
        riskScore: 85,
        riskReasons: ['Cluster scope'],
      },
      {
        id: 'app-002',
        runId: 'run-102',
        actionType: 'db_migration',
        status: 'pending',
        riskLevel: 'medium',
        requestedBy: 'user-bob',
        requestedAt: '2026-10-01T12:05:00Z',
        description: 'Schema migration v2',
        riskScore: 50,
        riskReasons: ['Schema DDL change'],
      },
    ];

    await act(async () => {
      root.render(
        <ApprovalCenter
          approvals={mockApprovals}
          currentUserId="user-alice"
          onApprove={vi.fn()}
          onReject={vi.fn()}
        />
      );
    });

    const card1 = container.querySelector('[data-testid="approval-item-app-001"]') as HTMLElement;
    const card2 = container.querySelector('[data-testid="approval-item-app-002"]') as HTMLElement;

    expect(card1).not.toBeNull();
    expect(card2).not.toBeNull();

    // Verify WAI-ARIA button pattern
    expect(card1.getAttribute('role')).toBe('button');
    expect(card1.getAttribute('tabindex')).toBe('0');
    expect(card1.getAttribute('aria-pressed')).toBe('true'); // First item is selected by default
    expect(card1.getAttribute('aria-label')).toContain('승인 안건 app-001');

    expect(card2.getAttribute('role')).toBe('button');
    expect(card2.getAttribute('tabindex')).toBe('0');
    expect(card2.getAttribute('aria-pressed')).toBe('false');

    // Simulate Enter key on second approval card
    await act(async () => {
      card2.dispatchEvent(new KeyboardEvent('keydown', { key: 'Enter', bubbles: true }));
    });

    expect(card2.getAttribute('aria-pressed')).toBe('true');
    expect(card1.getAttribute('aria-pressed')).toBe('false');

    // Simulate Space key on first approval card
    await act(async () => {
      card1.dispatchEvent(new KeyboardEvent('keydown', { key: ' ', bubbles: true }));
    });

    expect(card1.getAttribute('aria-pressed')).toBe('true');
    expect(card2.getAttribute('aria-pressed')).toBe('false');
  });

  // --------------------------------------------------------------------------
  // ACC-02: NodeList Keyboard Navigation (F3: No nested buttons, sibling native controls)
  // --------------------------------------------------------------------------
  it('ACC-02 (F3): NodeList separates card surface and secondary action into sibling native controls without nested interactive buttons', async () => {
    const mockNodes: NodeItem[] = [
      {
        id: 'node-online-1',
        hostname: 'worker-node-1',
        ip: '192.168.1.10',
        status: 'online',
        os: 'linux',
        labels: { tier: 'primary' },
        resources: { cpuTotal: 16, cpuUsage: 25, memoryTotal: 32768, memoryUsage: 45, diskTotal: 1000, diskUsage: 30, gpus: [] },
        cpuCores: 16,
        cpuUsagePercent: 25,
        memoryTotalBytes: 32768 * 1024 * 1024,
        memoryUsedBytes: 14745 * 1024 * 1024,
        allocatableCores: 12,
        allocatableMemoryBytes: 16384 * 1024 * 1024,
        lastHeartbeat: new Date().toISOString(),
      },
      {
        id: 'node-lost-2',
        hostname: 'worker-node-2',
        ip: '192.168.1.11',
        status: 'lost',
        os: 'linux',
        telemetryUnavailable: true,
        labels: { tier: 'edge' },
        resources: { cpuTotal: 8, cpuUsage: 0, memoryTotal: 16384, memoryUsage: 0, diskTotal: 500, diskUsage: 0, gpus: [] },
        lastHeartbeat: new Date(Date.now() - 3600000).toISOString(),
      },
    ];

    const onSelectNode = vi.fn();
    const onOpenStudio = vi.fn();

    await act(async () => {
      root.render(<NodeList nodes={mockNodes} onSelectNode={onSelectNode} onOpenStudio={onOpenStudio} />);
    });

    const card1 = container.querySelector('[data-testid="node-card-node-online-1"]') as HTMLElement;
    const card2 = container.querySelector('[data-testid="node-card-node-lost-2"]') as HTMLElement;

    expect(card1).not.toBeNull();
    expect(card2).not.toBeNull();

    // 1. F3: Normal card container MUST NOT have role="button" or tabIndex (avoids nested button antipattern)
    expect(card1.getAttribute('role')).toBeNull();
    expect(card1.getAttribute('tabindex')).toBeNull();

    // 2. F3: Sibling native buttons inside normal card
    const selectBtn = container.querySelector('[data-testid="node-select-btn-node-online-1"]') as HTMLButtonElement;
    const studioBtn = container.querySelector('[data-testid="node-studio-btn-node-online-1"]') as HTMLButtonElement;

    expect(selectBtn).not.toBeNull();
    expect(selectBtn.tagName.toLowerCase()).toBe('button');
    expect(selectBtn.getAttribute('aria-label')).toBe('노드 worker-node-1 선택');

    expect(studioBtn).not.toBeNull();
    expect(studioBtn.tagName.toLowerCase()).toBe('button');

    // Trigger select via Enter on native button
    await act(async () => {
      selectBtn.dispatchEvent(new KeyboardEvent('keydown', { key: 'Enter', bubbles: true }));
      selectBtn.click();
    });
    expect(onSelectNode).toHaveBeenCalledWith('node-online-1');

    // Trigger Studio via click on native button
    await act(async () => {
      studioBtn.click();
    });
    expect(onOpenStudio).toHaveBeenCalledWith('node-online-1');

    // 3. F3: Telemetry-unavailable card retains role="alert" container without click/tabIndex on outer container
    expect(card2.getAttribute('role')).toBe('alert');
    expect(card2.getAttribute('tabindex')).toBeNull();

    // Sibling detail button inside telemetry-unavailable card handles selection
    const detailBtn = container.querySelector('[data-testid="node-detail-btn-node-lost-2"]') as HTMLButtonElement;
    expect(detailBtn).not.toBeNull();
    expect(detailBtn.tagName.toLowerCase()).toBe('button');
    expect(detailBtn.getAttribute('aria-label')).toBe('노드 worker-node-2 상세 및 자원 보기');

    await act(async () => {
      detailBtn.click();
    });
    expect(onSelectNode).toHaveBeenCalledWith('node-lost-2');
  });

  // --------------------------------------------------------------------------
  // ACC-02: RunList Keyboard Navigation (F2: Native table semantics, cell action button)
  // --------------------------------------------------------------------------
  it('ACC-02 (F2): RunList preserves native table row semantics and provides accessible cell control for selection', async () => {
    const mockRuns: RunItem[] = [
      {
        id: 'run-001',
        workspaceId: 'wsp-1',
        status: 'running',
        state: 'running',
        createdAt: new Date().toISOString(),
        triggerType: 'manual',
        taskDescription: 'Build pipeline run',
      },
    ];

    const onSelectRun = vi.fn();

    await act(async () => {
      root.render(<RunList runs={mockRuns} onSelectRun={onSelectRun} />);
    });

    const tr = container.querySelector('tbody tr') as HTMLTableRowElement;
    expect(tr).not.toBeNull();

    // F2: <tr> MUST retain native table row semantics — NO role="button" or tabIndex on <tr>!
    expect(tr.getAttribute('role')).toBeNull();
    expect(tr.getAttribute('tabindex')).toBeNull();

    // F2: Native accessible action button inside first table cell
    const runBtn = container.querySelector('[data-testid="run-select-btn-run-001"]') as HTMLButtonElement;
    expect(runBtn).not.toBeNull();
    expect(runBtn.tagName.toLowerCase()).toBe('button');
    expect(runBtn.getAttribute('aria-label')).toBe('실행 작업 run-001 상세 조회');

    // Enter key triggers onSelectRun
    await act(async () => {
      runBtn.dispatchEvent(new KeyboardEvent('keydown', { key: 'Enter', bubbles: true }));
      runBtn.click();
    });
    expect(onSelectRun).toHaveBeenCalledWith('run-001');

    // Space key triggers onSelectRun
    await act(async () => {
      runBtn.dispatchEvent(new KeyboardEvent('keydown', { key: ' ', bubbles: true }));
      runBtn.click();
    });
    expect(onSelectRun).toHaveBeenCalledTimes(2);
  });

  // --------------------------------------------------------------------------
  // ACC-02: NaturalLanguageRunView Context Chips Keyboard Navigation
  // --------------------------------------------------------------------------
  it('ACC-02: NaturalLanguageRunView context chips have role=button, tabIndex=0, aria-pressed, and toggle via Enter/Space', async () => {
    await act(async () => {
      root.render(<NaturalLanguageRunView />);
    });

    const chips = container.querySelectorAll<HTMLSpanElement>('span[role="button"][tabindex="0"]');
    expect(chips.length).toBeGreaterThanOrEqual(4);

    const firstChip = chips[0];
    const initialPressed = firstChip.getAttribute('aria-pressed') === 'true';

    // Toggle via Enter
    await act(async () => {
      firstChip.dispatchEvent(new KeyboardEvent('keydown', { key: 'Enter', bubbles: true }));
    });
    expect(firstChip.getAttribute('aria-pressed')).toBe((!initialPressed).toString());

    // Toggle back via Space
    await act(async () => {
      firstChip.dispatchEvent(new KeyboardEvent('keydown', { key: ' ', bubbles: true }));
    });
    expect(firstChip.getAttribute('aria-pressed')).toBe(initialPressed.toString());
  });

  // --------------------------------------------------------------------------
  // ACC-02: DeveloperStudio Workspace and Node Placement Card Keyboard Navigation
  // --------------------------------------------------------------------------
  it('ACC-02: DeveloperStudio workspace cards and node placement cards support keyboard activation and ARIA states', async () => {
    const mockProject: ProjectItem = {
      id: 'prj-101',
      name: 'Alpha Project',
    };

    const mockWorkspaces: projectObservation.ProjectWorkspace[] = [
      {
        workspaceId: 'wsp-01',
        name: 'Workspace Alpha',
        baseBranch: 'main',
        isolationType: 'git_worktree',
        status: 'active',
      },
      {
        workspaceId: 'wsp-02',
        name: 'Workspace Beta',
        baseBranch: 'feat/test',
        isolationType: 'git_worktree',
        status: 'active',
      },
    ];

    const mockNodes: NodeItem[] = [
      {
        id: 'node-schedulable',
        hostname: 'node-schedulable',
        status: 'online',
        os: 'linux',
        ip: '192.168.1.50',
        labels: {},
        cpuCores: 16,
        cpuUsagePercent: 10,
        memoryTotalBytes: 32 * 1024 ** 3,
        memoryUsedBytes: 8 * 1024 ** 3,
        allocatableCores: 8,
        allocatableMemoryBytes: 16 * 1024 ** 3,
        storageTotalBytes: 500 * 1024 ** 3,
        storageUsedBytes: 100 * 1024 ** 3,
        lastHeartbeat: new Date().toISOString(),
      },
      {
        id: 'node-unschedulable',
        hostname: 'node-unschedulable',
        status: 'lost',
        os: 'linux',
        telemetryUnavailable: true,
        observationOnly: true,
        ip: '192.168.1.51',
        labels: {},
        cpuCores: 8,
        cpuUsagePercent: 0,
        memoryTotalBytes: 16 * 1024 ** 3,
        memoryUsedBytes: 0,
        allocatableCores: 0,
        allocatableMemoryBytes: 0,
        storageTotalBytes: 500 * 1024 ** 3,
        storageUsedBytes: 0,
        lastHeartbeat: new Date().toISOString(),
      },
    ];

    const mockRuns: RunItem[] = [
      {
        id: 'run-sample',
        projectId: 'prj-101',
        status: 'succeeded',
        state: 'succeeded',
        createdAt: '2026-10-01T10:00:00Z',
      },
    ];

    vi.spyOn(projectObservation, 'fetchProjectWorkspaces').mockResolvedValue(mockWorkspaces);

    await act(async () => {
      root.render(
        <DeveloperStudio
          project={mockProject}
          nodes={mockNodes}
          runs={mockRuns}
        />
      );
    });

    // Step 1: Workspace Selection Cards
    const wspCard1 = container.querySelector('[aria-label="워크스페이스 Workspace Alpha 선택"]') as HTMLElement;
    const wspCard2 = container.querySelector('[aria-label="워크스페이스 Workspace Beta 선택"]') as HTMLElement;

    expect(wspCard1).not.toBeNull();
    expect(wspCard2).not.toBeNull();
    expect(wspCard1.getAttribute('role')).toBe('button');
    expect(wspCard1.getAttribute('tabindex')).toBe('0');

    // Activate wsp-02 via Enter
    await act(async () => {
      wspCard2.dispatchEvent(new KeyboardEvent('keydown', { key: 'Enter', bubbles: true }));
    });
    expect(wspCard2.getAttribute('aria-pressed')).toBe('true');
    expect(wspCard1.getAttribute('aria-pressed')).toBe('false');

    // Advance to Step 2 (Node Selection / Placement)
    const stepTabs = container.querySelectorAll<HTMLButtonElement>('div[role="tablist"] button[role="tab"]');
    expect(stepTabs.length).toBe(4);

    await act(async () => {
      stepTabs[1].click(); // Step 2: Node Selection
    });

    const schedNodeCard = container.querySelector('[aria-label*="노드 node-schedulable 배치 선택"]') as HTMLElement;
    const unschedNodeCard = container.querySelector('[aria-label*="노드 node-unschedulable 배치 선택"]') as HTMLElement;

    expect(schedNodeCard).not.toBeNull();
    expect(unschedNodeCard).not.toBeNull();

    // Schedulable node has tabIndex=0 and aria-disabled="false"
    expect(schedNodeCard.getAttribute('role')).toBe('button');
    expect(schedNodeCard.getAttribute('tabindex')).toBe('0');
    expect(schedNodeCard.getAttribute('aria-disabled')).toBe('false');

    // Unschedulable node has tabIndex=-1 and aria-disabled="true"
    expect(unschedNodeCard.getAttribute('role')).toBe('button');
    expect(unschedNodeCard.getAttribute('tabindex')).toBe('-1');
    expect(unschedNodeCard.getAttribute('aria-disabled')).toBe('true');

    // Activate schedulable node via Enter
    await act(async () => {
      schedNodeCard.dispatchEvent(new KeyboardEvent('keydown', { key: 'Enter', bubbles: true }));
    });
    expect(schedNodeCard.getAttribute('aria-pressed')).toBe('true');
  });

  // --------------------------------------------------------------------------
  // ACC-06: ResourceExplorer Tablist WAI-ARIA and Keyboard Navigation (F1: Focus assertions & Up/Down scrolling)
  // --------------------------------------------------------------------------
  it('ACC-06 (F1): ResourceExplorer implements horizontal WAI-ARIA tablist roving tabindex with activeElement assertions and preserves vertical scroll', async () => {
    vi.spyOn(fabricApi, 'getDiscoveryCandidates').mockResolvedValue({ items: [] });
    vi.spyOn(storageObsApi, 'fetchStorageObservation').mockResolvedValue({
      status: 'success',
      observedAt: new Date().toISOString(),
      observation: { sampled: 10, examined: 10, mismatches: 0, unverifiable: 0, unsampled: 0 },
    } as any);

    await act(async () => {
      root.render(<ResourceExplorer nodes={[]} />);
    });

    // 1. Tablist container
    const tablist = container.querySelector('div[role="tablist"]');
    expect(tablist).not.toBeNull();
    expect(tablist?.getAttribute('aria-label')).toBe('자원 탐색기 탭 목록');

    // 2. Tabs
    const tabs = container.querySelectorAll<HTMLButtonElement>('div[role="tablist"] button[role="tab"]');
    expect(tabs.length).toBe(5);

    const [overviewTab, storageTab, poolsTab, nodesTab, discoveryTab] = Array.from(tabs);

    expect(overviewTab.id).toBe('tab-overview');
    expect(overviewTab.getAttribute('aria-controls')).toBe('tabpanel-overview');
    expect(overviewTab.getAttribute('aria-selected')).toBe('true');
    expect(overviewTab.getAttribute('tabindex')).toBe('0');

    expect(storageTab.id).toBe('tab-storage');
    expect(storageTab.getAttribute('aria-controls')).toBe('tabpanel-storage');
    expect(storageTab.getAttribute('aria-selected')).toBe('false');
    expect(storageTab.getAttribute('tabindex')).toBe('-1');

    // 3. Tabpanel
    const overviewPanel = container.querySelector('#tabpanel-overview');
    expect(overviewPanel).not.toBeNull();
    expect(overviewPanel?.getAttribute('role')).toBe('tabpanel');
    expect(overviewPanel?.getAttribute('aria-labelledby')).toBe('tab-overview');
    expect(overviewPanel?.getAttribute('tabindex')).toBe('0');

    // Initial focus on overviewTab
    overviewTab.focus();
    expect(document.activeElement).toBe(overviewTab);

    // 4. Keyboard Arrow Navigation (ArrowRight: overview -> storage)
    // F1 requirement: document.activeElement MUST be asserted for each roving navigation step
    await act(async () => {
      overviewTab.dispatchEvent(new KeyboardEvent('keydown', { key: 'ArrowRight', bubbles: true }));
    });

    expect(storageTab.getAttribute('aria-selected')).toBe('true');
    expect(storageTab.getAttribute('tabindex')).toBe('0');
    expect(overviewTab.getAttribute('aria-selected')).toBe('false');
    expect(overviewTab.getAttribute('tabindex')).toBe('-1');
    expect(document.activeElement).toBe(storageTab); // F1: Assert roving focus explicitly transferred

    const storagePanel = container.querySelector('#tabpanel-storage');
    expect(storagePanel).not.toBeNull();
    expect(storagePanel?.getAttribute('role')).toBe('tabpanel');
    expect(storagePanel?.getAttribute('aria-labelledby')).toBe('tab-storage');

    // 5. Keyboard Navigation (End: storage -> discovery)
    await act(async () => {
      storageTab.dispatchEvent(new KeyboardEvent('keydown', { key: 'End', bubbles: true }));
    });

    expect(discoveryTab.getAttribute('aria-selected')).toBe('true');
    expect(discoveryTab.getAttribute('tabindex')).toBe('0');
    expect(document.activeElement).toBe(discoveryTab); // F1: Assert roving focus on End

    const discoveryPanel = container.querySelector('#tabpanel-discovery');
    expect(discoveryPanel).not.toBeNull();
    expect(discoveryPanel?.getAttribute('role')).toBe('tabpanel');
    expect(discoveryPanel?.getAttribute('aria-labelledby')).toBe('tab-discovery');

    // 6. Keyboard Navigation (Home: discovery -> overview)
    await act(async () => {
      discoveryTab.dispatchEvent(new KeyboardEvent('keydown', { key: 'Home', bubbles: true }));
    });

    expect(overviewTab.getAttribute('aria-selected')).toBe('true');
    expect(overviewTab.getAttribute('tabindex')).toBe('0');
    expect(document.activeElement).toBe(overviewTab); // F1: Assert roving focus on Home

    // 7. Keyboard Navigation (ArrowLeft: overview -> discovery wrap-around)
    await act(async () => {
      overviewTab.dispatchEvent(new KeyboardEvent('keydown', { key: 'ArrowLeft', bubbles: true }));
    });

    expect(discoveryTab.getAttribute('aria-selected')).toBe('true');
    expect(discoveryTab.getAttribute('tabindex')).toBe('0');
    expect(document.activeElement).toBe(discoveryTab); // F1: Assert roving focus on ArrowLeft wrap

    // 8. F1: Horizontal tablist MUST NOT intercept ArrowDown or ArrowUp (preserve page/browser vertical scroll)
    const downEvent = new KeyboardEvent('keydown', { key: 'ArrowDown', bubbles: true, cancelable: true });
    discoveryTab.dispatchEvent(downEvent);
    expect(downEvent.defaultPrevented).toBe(false); // F1: preventDefault not called
    expect(document.activeElement).toBe(discoveryTab); // F1: focus and selection remained unchanged
    expect(discoveryTab.getAttribute('aria-selected')).toBe('true');

    const upEvent = new KeyboardEvent('keydown', { key: 'ArrowUp', bubbles: true, cancelable: true });
    discoveryTab.dispatchEvent(upEvent);
    expect(upEvent.defaultPrevented).toBe(false); // F1: preventDefault not called
    expect(document.activeElement).toBe(discoveryTab); // F1: focus and selection remained unchanged
    expect(discoveryTab.getAttribute('aria-selected')).toBe('true');
  });
});
