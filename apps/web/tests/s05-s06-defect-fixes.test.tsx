// @vitest-environment happy-dom
// @ts-ignore
globalThis.IS_REACT_ACT_ENVIRONMENT = true;
import React, { act } from 'react';
import { createRoot, Root } from 'react-dom/client';
import { describe, it, expect, vi, beforeEach, afterEach } from 'vitest';

import { PlacementExplainView } from '../src/features/placement/PlacementExplainView';
import { PlacementSimulator } from '../src/features/placement/PlacementSimulator';
import { WorkspaceCreateModal } from '../src/features/workspaces/WorkspaceCreateModal';
import { WorkspaceList } from '../src/features/workspaces/WorkspaceList';
import { TerminalSessionView } from '../src/features/desktop/TerminalSessionView';
import { DesktopWindowComponent } from '../src/features/desktop/DesktopWindow';
import { PlacementExplainResult, WorkspaceItem } from '../src/contracts/types';
import { DesktopShell } from '../src/features/desktop/DesktopShell';
import { PoolListItemResponse } from '../src/contracts/pool-list-response';
import { DesktopWindow as IDesktopWindow } from '../src/contracts/virtualFabric';
import { ResourceExplorer } from '../src/features/desktop/ResourceExplorer';
import * as clientModule from '../src/shared/api/client';
import * as fabricApi from '../src/features/desktop/fabricControlApi';

describe('S05-FE & S06-FE Product Defect Fixes Regression Suite', () => {
  let container: HTMLDivElement;
  let root: Root;

  beforeEach(() => {
    container = document.createElement('div');
    document.body.appendChild(container);
    root = createRoot(container);
    vi.restoreAllMocks();
  });

  afterEach(() => {
    act(() => {
      root.unmount();
    });
    container.remove();
    vi.restoreAllMocks();
  });

  // ---------------------------------------------------------------------------
  // 1. S05 Defect A: PlacementExplainView local simulation disclaimer & score qualification
  // ---------------------------------------------------------------------------
  it('[S05-DEF-A] renders local simulation disclaimer badge and qualifies scores as unmeasured on server', async () => {
    const mockExplain: PlacementExplainResult = {
      runId: 'run_test_01',
      selectedNodeId: 'node-01',
      policyVersion: 'pol-v1.0.0',
      snapshotVersion: 'snap-001',
      decidedAt: '2026-09-28T10:00:00Z',
      evaluations: [
        {
          nodeId: 'node-01',
          hostname: 'node-01-primary',
          os: 'linux',
          hardFilterPassed: true,
          rejectionReasons: [],
          scores: {
            localityScore: 40,
            headroomScore: 30,
            networkCostScore: 30,
            totalScore: 100,
          },
        },
      ],
    };

    await act(async () => {
      root.render(<PlacementExplainView explainResult={mockExplain} />);
    });

    const badge = container.querySelector('[data-testid="placement-explain-simulation-badge"]');
    expect(badge).not.toBeNull();
    expect(badge?.textContent).toContain('[로컬 시뮬레이션 (UNVERIFIED · 모의)]');

    const scoreLabel = container.querySelector('[data-testid="placement-explain-score-label"]');
    expect(scoreLabel).not.toBeNull();
    expect(scoreLabel?.textContent).toContain('로컬 모의 점수 (미측정)');

    const scoreValue = container.querySelector('[data-testid="placement-explain-score-value"]');
    expect(scoreValue?.textContent).toContain('100점');

    expect(container.textContent).toContain('정책(모의):');
    expect(container.textContent).toContain('스냅샷(모의):');
    expect(container.textContent).toContain('클라이언트 결정론적 가중치 시뮬레이션');
  });

  // ---------------------------------------------------------------------------
  // 2. S05 Defect B: PlacementSimulator does not fabricate capacity from non-contract pool fields (F-4, F-6, F-8)
  // ---------------------------------------------------------------------------
  it('[S05-DEF-B] displays pending capacity indicator only when idle and rejects phantom capacity fields', async () => {
    // Pool containing legacy/non-contract availableCores & totalCores fields
    const activePool: PoolListItemResponse = {
      poolId: 'pool-test-01',
      projectId: 'prj-test-01',
      name: 'GPU Training Pool',
      status: 'active',
      memberCount: 3,
    };
    const legacyPool = {
      ...activePool,
      availableCores: 8,
      totalCores: 16,
    } as any;

    vi.spyOn(clientModule, 'apiClient').mockImplementation(async (path: string) => {
      if (path.includes('/v1/pools/pool-test-01/capacity')) {
        return new Promise(() => {}); // hang to simulate pending
      }
      if (path.includes('/v1/pools')) {
        return { items: [legacyPool], count: 1 };
      }
      return {};
    });

    // 1) When poolCapacityState is 'idle', pending banner shows and non-contract capacity is NOT rendered
    await act(async () => {
      root.render(
        <PlacementSimulator
          nodes={[]}
          initialPools={[legacyPool]}
          initialPoolsState="success"
          initialPoolCapacity={null}
          initialPoolCapacityState="idle"
        />
      );
    });

    const pendingBanner = container.querySelector('[data-testid="pool-capacity-pending"]');
    expect(pendingBanner).not.toBeNull();
    expect(pendingBanner?.textContent).toContain('풀 3원 용량 조회 대기 중 (미측정 · GET /v1/pools/pool-test-01/capacity)');

    // Ensure non-contract phantom text like "8 / 16 Cores" is NOT rendered
    expect(container.textContent).not.toContain('8 / 16 Cores');

    // 2) When poolCapacityState is 'error' (F-6, C-3), unmount and render fresh component to verify error state
    await act(async () => {
      root.unmount();
    });
    container = document.createElement('div');
    document.body.appendChild(container);
    root = createRoot(container);

    await act(async () => {
      root.render(
        <PlacementSimulator
          nodes={[]}
          initialPools={[legacyPool]}
          initialPoolsState="success"
          initialPoolCapacity={null}
          initialPoolCapacityState="error"
          initialPoolCapacityError="풀 용량 조회 실패 (503 Service Unavailable)"
        />
      );
    });

    expect(container.querySelector('[data-testid="pool-capacity-pending"]')).toBeNull();
    const errorBanner = container.querySelector('[data-testid="pool-capacity-error"]');
    expect(errorBanner).not.toBeNull();
    expect(errorBanner?.textContent).toContain('503 Service Unavailable');
  });

  // ---------------------------------------------------------------------------
  // 3. S05 Defect C: ResourceExplorer placement preview displays 0C and does not fabricate '미측정' (F-5)
  // ---------------------------------------------------------------------------
  it('[S05-DEF-C] ResourceExplorer placement preview renders 0C 가용 and does not fabricate 미측정 for 0 spare cores', async () => {
    vi.spyOn(fabricApi, 'getPoolList').mockResolvedValue({
      items: [
        {
          poolId: 'pool-preview-01',
          projectId: 'prj-01',
          name: 'Preview Pool',
          status: 'active',
          memberCount: 1,
        },
      ],
      count: 1,
    });

    vi.spyOn(fabricApi, 'getPoolPlacementPreview').mockResolvedValue({
      poolId: 'pool-preview-01',
      candidates: [
        {
          nodeId: 'node-zero-cores',
          hostname: 'node-zero',
          availableCpuMillicores: 0,
          availableRamBytes: 1024 * 1024 * 1024,
          availableGpuDevices: 0,
          eligible: true,
        },
      ],
      candidateCount: 1,
    });

    await act(async () => {
      root.render(
        <ResourceExplorer
          projectId="prj-01"
          nodes={[]}
          initialTab="pools"
        />
      );
    });

    // Click '적격 노드 순위 조회' button
    const previewBtn = Array.from(container.querySelectorAll('button')).find((b) =>
      b.textContent?.includes('적격 노드 순위 조회')
    );
    expect(previewBtn).toBeDefined();

    await act(async () => {
      previewBtn?.click();
    });

    const results = container.querySelector('[data-testid="placement-preview-results"]');
    expect(results).not.toBeNull();
    expect(results?.textContent).toContain('node-zero');
    expect(results?.textContent).toContain('0C 가용');
    expect(results?.textContent).toContain('0 GPU');
    expect(results?.textContent).not.toContain('미측정');
  });

  // ---------------------------------------------------------------------------
  // 4. S06 Defect D: WorkspaceCreateModal Escape handler, Focus Trap, and Focus Restoration (F-2)
  // ---------------------------------------------------------------------------
  it('[S06-DEF-D] WorkspaceCreateModal handles Escape on dialog, traps focus, and preserves focus during rerenders', async () => {
    let handleClose = vi.fn();
    const handleCreate = vi.fn().mockResolvedValue(undefined);

    const triggerBtn = document.createElement('button');
    triggerBtn.textContent = 'Open Modal';
    document.body.appendChild(triggerBtn);
    triggerBtn.focus();
    expect(document.activeElement).toBe(triggerBtn);

    await act(async () => {
      root.render(
        <WorkspaceCreateModal
          projectId="prj-core-01"
          isOpen={true}
          onClose={handleClose}
          onCreate={handleCreate}
        />
      );
    });

    const dialog = container.querySelector('div[role="dialog"]');
    expect(dialog).not.toBeNull();
    expect(dialog?.getAttribute('aria-modal')).toBe('true');
    expect(dialog?.getAttribute('aria-labelledby')).toBe('workspace-create-title');

    // Initial focus placed on wsp-name-input
    const nameInput = container.querySelector<HTMLInputElement>('#wsp-name-input');
    expect(nameInput).not.toBeNull();
    expect(document.activeElement).toBe(nameInput);

    // Rerender with a NEW onClose reference (simulating App 5s polling rerender)
    handleClose = vi.fn();
    await act(async () => {
      root.render(
        <WorkspaceCreateModal
          projectId="prj-core-01"
          isOpen={true}
          onClose={handleClose}
          onCreate={handleCreate}
        />
      );
    });

    // Focus must REMAIN on nameInput, not jumping to triggerBtn!
    expect(document.activeElement).toBe(nameInput);

    // Test Escape key closes modal via dialog keydown
    dialog?.dispatchEvent(new KeyboardEvent('keydown', { key: 'Escape', bubbles: true }));
    expect(handleClose).toHaveBeenCalledTimes(1);

    // Test Focus Trap
    const closeBtn = container.querySelector<HTMLButtonElement>('button[aria-label="닫기"]');
    const submitBtn = container.querySelector<HTMLButtonElement>('[data-testid="workspace-submit-btn"]');
    expect(closeBtn).not.toBeNull();
    expect(submitBtn).not.toBeNull();

    submitBtn?.focus();
    expect(document.activeElement).toBe(submitBtn);

    // Tab on last element should cycle to first element (closeBtn)
    dialog?.dispatchEvent(new KeyboardEvent('keydown', { key: 'Tab', bubbles: true }));
    expect(document.activeElement).toBe(closeBtn);

    // Shift+Tab on first element should cycle to last element (submitBtn)
    dialog?.dispatchEvent(new KeyboardEvent('keydown', { key: 'Tab', shiftKey: true, bubbles: true }));
    expect(document.activeElement).toBe(submitBtn);

    // Unmount / close should restore focus to triggerBtn
    await act(async () => {
      root.render(
        <WorkspaceCreateModal
          projectId="prj-core-01"
          isOpen={false}
          onClose={handleClose}
          onCreate={handleCreate}
        />
      );
    });

    expect(document.activeElement).toBe(triggerBtn);
    triggerBtn.remove();
  });

  // ---------------------------------------------------------------------------
  // 5. S06 Defect E: WorkspaceList cards keyboard access & Studio button isolation (F-1, F-8)
  // ---------------------------------------------------------------------------
  it('[S06-DEF-E] WorkspaceList cards are keyboard-accessible and inner Studio button Enter does not trigger workspace selection', async () => {
    const handleSelect = vi.fn();
    const handleOpenStudio = vi.fn();
    const mockWorkspaces: WorkspaceItem[] = [
      {
        id: 'wsp-01',
        projectId: 'prj-01',
        name: 'Alpha Workspace',
        targetNodeId: null,
        isolationMode: 'process_sandbox',
        allowedPaths: [],
        prohibitedPaths: [],
        cpuLimitCores: 2,
        memoryLimitBytes: 1024,
        status: 'ready',
        createdAt: '2026-09-28T00:00:00Z',
      },
    ];

    await act(async () => {
      root.render(
        <WorkspaceList
          workspaces={mockWorkspaces}
          nodes={[]}
          onSelectWorkspace={handleSelect}
          onCreateWorkspace={vi.fn()}
          onOpenStudio={handleOpenStudio}
        />
      );
    });

    const card = container.querySelector('div[role="button"][tabindex="0"]');
    expect(card).not.toBeNull();
    expect(card?.getAttribute('aria-label')).toBe('작업공간 Alpha Workspace 선택');

    // Trigger Enter key on card -> selects workspace
    card?.dispatchEvent(new KeyboardEvent('keydown', { key: 'Enter', bubbles: true }));
    expect(handleSelect).toHaveBeenCalledWith('wsp-01');

    // Trigger Space key on card -> selects workspace
    card?.dispatchEvent(new KeyboardEvent('keydown', { key: ' ', bubbles: true }));
    expect(handleSelect).toHaveBeenCalledWith('wsp-01');

    handleSelect.mockClear();

    // Trigger Enter on inner '⚡ Studio에서 열기' button -> must call onOpenStudio, NOT onSelectWorkspace!
    const studioBtn = Array.from(container.querySelectorAll('button')).find((b) =>
      b.textContent?.includes('Studio에서 열기')
    );
    expect(studioBtn).toBeDefined();

    studioBtn?.dispatchEvent(new KeyboardEvent('keydown', { key: 'Enter', bubbles: true }));
    expect(handleOpenStudio).toHaveBeenCalledWith('wsp-01');
    expect(handleSelect).not.toHaveBeenCalled();
  });

  // ---------------------------------------------------------------------------
  // 6. S06 Defect F: TerminalSessionView displays ticket auth mechanism description (F-7)
  // ---------------------------------------------------------------------------
  it('[S06-DEF-F] TerminalSessionView pty-ticket-badge describes authentication method and pending status', async () => {
    const mockNodes = [
      {
        id: 'node-01',
        hostname: 'Node-01-Win',
        os: 'windows' as const,
        ipAddress: '192.168.1.10',
        observationOnly: false,
        schedulable: true,
      },
    ];

    await act(async () => {
      root.render(
        <TerminalSessionView
          nodes={mockNodes as any}
          defaultNodeId="node-01"
          projectId="prj-01"
          commandId=""
        />
      );
    });

    const badge = container.querySelector('[data-testid="pty-ticket-badge"]');
    expect(badge).not.toBeNull();
    expect(badge?.textContent).toContain('승인 명령 ID 대기 중 (인증 대기 · mTLS)');

    // When valid commandId is supplied
    await act(async () => {
      root.render(
        <TerminalSessionView
          nodes={mockNodes as any}
          defaultNodeId="node-01"
          projectId="prj-01"
          commandId="cmd_authorized_123"
        />
      );
    });

    const activeBadge = container.querySelector('[data-testid="pty-ticket-badge"]');
    expect(activeBadge?.textContent).toContain('30초 암호학적 1회용 PTY 티켓 인증 연동 (mTLS 격리)');
  });

  // ---------------------------------------------------------------------------
  // 7. S06 Defect G: DesktopWindow closes on Escape on window and ignores input/terminal (F-3, F-8)
  // ---------------------------------------------------------------------------
  it('[S06-DEF-G] DesktopWindow handles Escape on window element and does not close on terminal/input Escape', async () => {
    const handleClose = vi.fn();
    const mockWindow: IDesktopWindow = {
      id: 'win-01',
      appId: 'terminal',
      title: 'Resource Explorer',
      icon: '💻',
      isOpen: true,
      isMinimized: false,
      isMaximized: false,
      position: { x: 50, y: 50 },
      size: { width: 800, height: 600 },
      zIndex: 10,
    };

    // When inactive, Escape should NOT close window
    await act(async () => {
      root.render(
        <DesktopWindowComponent
          window={mockWindow}
          isActive={false}
          onFocus={vi.fn()}
          onClose={handleClose}
          onMinimize={vi.fn()}
          onToggleMaximize={vi.fn()}
        >
          <div>
            <input data-testid="test-inner-input" type="text" />
          </div>
        </DesktopWindowComponent>
      );
    });

    const windowDiv = container.querySelector('div[role="dialog"]');
    expect(windowDiv).not.toBeNull();

    windowDiv?.dispatchEvent(new KeyboardEvent('keydown', { key: 'Escape', bubbles: true }));
    expect(handleClose).not.toHaveBeenCalled();

    // When active:
    await act(async () => {
      root.render(
        <DesktopWindowComponent
          window={mockWindow}
          isActive={true}
          onFocus={vi.fn()}
          onClose={handleClose}
          onMinimize={vi.fn()}
          onToggleMaximize={vi.fn()}
        >
          <div>
            <input data-testid="test-inner-input" type="text" />
          </div>
        </DesktopWindowComponent>
      );
    });

    const activeWindowDiv = container.querySelector('div[role="dialog"]');
    const innerInput = container.querySelector<HTMLInputElement>('[data-testid="test-inner-input"]');
    expect(innerInput).not.toBeNull();

    // 1) Escape fired from inside an input must NOT close window
    innerInput?.dispatchEvent(new KeyboardEvent('keydown', { key: 'Escape', bubbles: true }));
    expect(handleClose).not.toHaveBeenCalled();

    // 2) Escape fired on window itself closes window
    activeWindowDiv?.dispatchEvent(new KeyboardEvent('keydown', { key: 'Escape', bubbles: true }));
    expect(handleClose).toHaveBeenCalledTimes(1);

    // 3) Close button title is "창 닫기" (without Esc)
    const closeBtn = container.querySelector<HTMLButtonElement>('button[title="창 닫기"]');
    expect(closeBtn).not.toBeNull();
  });

  // ---------------------------------------------------------------------------
  // 8. S06 Defect G (C-1): DesktopShell Start Menu vs Window Escape priority
  // ---------------------------------------------------------------------------
  it('[S06-DEF-G-C1] DesktopShell: 시작 메뉴가 열린 상태의 Esc는 메뉴만 닫고 활성 창은 닫지 않는다', async () => {
    await act(async () => {
      root.render(
        <DesktopShell
          projectId="prj-01"
          tenantId="tenant-01"
          checkoutId="chk-01"
          currentReviewerId="rev-01"
          nodes={[]}
          runs={[]}
          onSwitchToPortalView={vi.fn()}
          currentTheme="dark"
          onToggleTheme={vi.fn()}
          onRefreshNodes={vi.fn()}
          onApprove={vi.fn()}
          onReject={vi.fn()}
          currentUserRole="operator"
          onChangeUser={vi.fn()}
        />
      );
    });

    // 1) By default win_my_computer is open
    const windowDialog = container.querySelector('div[role="dialog"]');
    expect(windowDialog).not.toBeNull();

    // 2) Open Start Menu
    const startBtn = container.querySelector<HTMLButtonElement>('button[aria-label="SaintVision 시작 메뉴"]');
    expect(startBtn).not.toBeNull();
    await act(async () => {
      startBtn?.click();
    });

    const startMenu = container.querySelector('[role="menu"]');
    expect(startMenu).not.toBeNull();
    expect(startBtn?.getAttribute('aria-expanded')).toBe('true');

    // 3) Fire Escape while focus is inside active window
    await act(async () => {
      windowDialog?.dispatchEvent(new KeyboardEvent('keydown', { key: 'Escape', code: 'Escape', bubbles: true }));
    });

    // Expect: Start Menu is closed, but Window remains open!
    expect(container.querySelector('[role="menu"]')).toBeNull();
    expect(startBtn?.getAttribute('aria-expanded')).toBe('false');
    expect(container.querySelector('div[role="dialog"]')).not.toBeNull();

    // 4) Fire Escape again when Start Menu is closed
    await act(async () => {
      windowDialog?.dispatchEvent(new KeyboardEvent('keydown', { key: 'Escape', code: 'Escape', bubbles: true }));
    });

    // Now window closes
    expect(container.querySelector('div[role="dialog"]')).toBeNull();
  });
});
