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
import { PlacementExplainResult, PoolListItemResponse } from '../src/contracts/types';
import { DesktopWindow as IDesktopWindow } from '../src/contracts/virtualFabric';
import * as clientModule from '../src/shared/api/client';

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
  // 2. S05 Defect B: PlacementSimulator does not fabricate capacity from non-contract pool fields
  // ---------------------------------------------------------------------------
  it('[S05-DEF-B] displays pending capacity indicator when poolCapacity is not yet loaded without phantom fields', async () => {
    const activePool: PoolListItemResponse = {
      poolId: 'pool-test-01',
      projectId: 'prj-test-01',
      name: 'GPU Training Pool',
      status: 'active',
      memberCount: 3,
    };

    vi.spyOn(clientModule, 'apiClient').mockImplementation(async (path: string) => {
      if (path.includes('/v1/pools/pool-test-01/capacity')) {
        return new Promise(() => {}); // hang to simulate loading/pending
      }
      if (path.includes('/v1/pools')) {
        return [activePool];
      }
      return {};
    });

    await act(async () => {
      root.render(
        <PlacementSimulator
          activePool={activePool}
          allPools={[activePool]}
          projectId="prj-test-01"
        />
      );
    });

    const pendingBanner = container.querySelector('[data-testid="pool-capacity-pending"]');
    expect(pendingBanner).not.toBeNull();
    expect(pendingBanner?.textContent).toContain('풀 3원 용량 조회 대기 중 (미측정 · GET /v1/pools/pool-test-01/capacity)');

    // Ensure non-contract phantom text like "undefined Cores" or "NaN Cores" is NOT rendered
    expect(container.textContent).not.toContain('undefined Cores');
    expect(container.textContent).not.toContain('NaN Cores');
  });

  // ---------------------------------------------------------------------------
  // 3. S06 Defect D: WorkspaceCreateModal Escape handler, Focus Trap, and Focus Restoration
  // ---------------------------------------------------------------------------
  it('[S06-DEF-D] WorkspaceCreateModal supports Escape closing, focus trap, and focus restoration', async () => {
    const handleClose = vi.fn();
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

    // Test Escape key closes modal
    window.dispatchEvent(new KeyboardEvent('keydown', { key: 'Escape', bubbles: true }));
    expect(handleClose).toHaveBeenCalledTimes(1);

    // Test Focus Trap
    const closeBtn = container.querySelector<HTMLButtonElement>('button[aria-label="닫기"]');
    const submitBtn = container.querySelector<HTMLButtonElement>('[data-testid="workspace-submit-btn"]');
    expect(closeBtn).not.toBeNull();
    expect(submitBtn).not.toBeNull();

    submitBtn?.focus();
    expect(document.activeElement).toBe(submitBtn);

    // Tab on last element should cycle to first element (closeBtn)
    window.dispatchEvent(new KeyboardEvent('keydown', { key: 'Tab', bubbles: true }));
    expect(document.activeElement).toBe(closeBtn);

    // Shift+Tab on first element should cycle to last element (submitBtn)
    window.dispatchEvent(new KeyboardEvent('keydown', { key: 'Tab', shiftKey: true, bubbles: true }));
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
  // 4. S06 Defect E: WorkspaceList cards have keyboard role, tabIndex, and Enter/Space handler
  // ---------------------------------------------------------------------------
  it('[S06-DEF-E] WorkspaceList cards are keyboard-accessible (role="button", tabIndex=0, Enter/Space)', async () => {
    const handleSelect = vi.fn();
    const mockWorkspaces = [
      {
        id: 'wsp-01',
        projectId: 'prj-01',
        name: 'Alpha Workspace',
        status: 'active' as const,
        createdAt: '2026-09-28T00:00:00Z',
        updatedAt: '2026-09-28T00:00:00Z',
      },
    ];

    await act(async () => {
      root.render(
        <WorkspaceList
          workspaces={mockWorkspaces}
          onSelectWorkspace={handleSelect}
          onCreateWorkspaceClick={vi.fn()}
        />
      );
    });

    const card = container.querySelector('div[role="button"][tabindex="0"]');
    expect(card).not.toBeNull();
    expect(card?.getAttribute('aria-label')).toBe('작업공간 Alpha Workspace 선택');

    // Trigger Enter key
    card?.dispatchEvent(new KeyboardEvent('keydown', { key: 'Enter', bubbles: true }));
    expect(handleSelect).toHaveBeenCalledWith('wsp-01');

    // Trigger Space key
    card?.dispatchEvent(new KeyboardEvent('keydown', { key: ' ', bubbles: true }));
    expect(handleSelect).toHaveBeenCalledWith('wsp-01');
  });

  // ---------------------------------------------------------------------------
  // 5. S06 Defect F: TerminalSessionView displays ticket pending status when commandId is absent
  // ---------------------------------------------------------------------------
  it('[S06-DEF-F] TerminalSessionView pty-ticket-badge indicates pending status when commandId is missing', async () => {
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
    expect(badge?.textContent).toContain('승인 명령 ID 대기 중 (티켓 미발급 · mTLS)');

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
    expect(activeBadge?.textContent).toContain('30초 암호학적 1회용 PTY 티켓 (mTLS 격리)');
  });

  // ---------------------------------------------------------------------------
  // 6. S06 Defect G: DesktopWindow closes on Escape only when active
  // ---------------------------------------------------------------------------
  it('[S06-DEF-G] DesktopWindow closes on Escape only when isActive is true', async () => {
    const handleClose = vi.fn();
    const mockWindow: IDesktopWindow = {
      id: 'win-01',
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
          <div>Window Content</div>
        </DesktopWindowComponent>
      );
    });

    window.dispatchEvent(new KeyboardEvent('keydown', { key: 'Escape', bubbles: true }));
    expect(handleClose).not.toHaveBeenCalled();

    // When active, Escape MUST close window
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
          <div>Window Content</div>
        </DesktopWindowComponent>
      );
    });

    window.dispatchEvent(new KeyboardEvent('keydown', { key: 'Escape', bubbles: true }));
    expect(handleClose).toHaveBeenCalledTimes(1);
  });
});
