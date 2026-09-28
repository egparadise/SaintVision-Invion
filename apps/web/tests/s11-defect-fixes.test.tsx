// @vitest-environment happy-dom
// @ts-ignore
globalThis.IS_REACT_ACT_ENVIRONMENT = true;
import React, { act, useRef, useState } from 'react';
import { createRoot, Root } from 'react-dom/client';
import { describe, it, expect, vi, beforeEach, afterEach } from 'vitest';

import fs from 'node:fs';
import path from 'node:path';

const indexCss = fs.readFileSync(path.resolve(__dirname, '../src/index.css'), 'utf-8');
import { Button } from '../src/shared/ui/Button';
import { Header } from '../src/shared/ui/Header';
import { useModalA11y } from '../src/shared/ui/useModalA11y';
import { WorkspaceList } from '../src/features/workspaces/WorkspaceList';
import { WorkspaceCreateModal } from '../src/features/workspaces/WorkspaceCreateModal';
import { GitCommitModal } from '../src/features/editor/GitCommitModal';
import { ConflictResolutionModal } from '../src/features/editor/ConflictResolutionModal';
import { ReleaseCandidateView } from '../src/features/release/ReleaseCandidateView';
import { ReleaseManager } from '../src/features/release/releaseEngine';
import { DesktopWindowComponent } from '../src/features/desktop/DesktopWindow';
import { DesktopShell } from '../src/features/desktop/DesktopShell';
import { ApprovalDetail } from '../src/features/approvals/ApprovalDetail';
import { AdminSecurityConsole } from '../src/features/admin/AdminSecurityConsole';
import { RunDetail } from '../src/features/runs/RunDetail';
import { RunList } from '../src/features/runs/RunList';
import { DeveloperStudio } from '../src/features/studio/DeveloperStudio';
import * as clientModule from '../src/shared/api/client';
import { WorkspaceItem, NodeItem, ApprovalItem, RunItem, ProjectItem, NodeStopReceiptView } from '../src/contracts/types';
import { DesktopWindow as IDesktopWindow } from '../src/contracts/virtualFabric';

describe('S11-FE Defect Fixes Verification (DEF-S11-01 ~ DEF-S11-19)', () => {
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
  });

  // DEF-S11-01: Focus visibility on buttons and index.css :focus-visible
  it('DEF-S11-01: Button does not hardcode outline: none and index.css defines :focus-visible ring', async () => {
    // Assert index.css has :focus-visible with outline 2px solid and offset 2px
    expect(indexCss).toContain(':focus-visible');
    expect(indexCss).toMatch(/:focus-visible\s*\{[^}]*outline:\s*2px solid var\(--color-brand-primary\)/);
    expect(indexCss).toMatch(/:focus-visible\s*\{[^}]*outline-offset:\s*2px/);

    await act(async () => {
      root.render(<Button variant="primary">Accessibility Button</Button>);
    });
    const btn = container.querySelector('button') as HTMLButtonElement;
    expect(btn).not.toBeNull();
    expect(btn.style.outline).not.toBe('none');
  });

  // DEF-S11-02: WorkspaceList keyboard navigation and activation
  it('DEF-S11-02: WorkspaceList cards have role=button, tabIndex=0 and onKeyDown support', async () => {
    const handleSelect = vi.fn();
    const handleOpenStudio = vi.fn();
    const mockWorkspaces: WorkspaceItem[] = [
      {
        id: 'wsp-101',
        name: 'Workspace 101',
        projectId: 'prj-alpha',
        status: 'ready',
        targetNodeId: 'nod-01',
        isolationMode: 'container_isolated',
        allowedPaths: ['/data'],
        prohibitedPaths: ['/etc'],
        cpuLimitCores: 4,
        memoryLimitBytes: 8 * 1024 ** 3,
        createdAt: '2026-09-28T00:00:00Z',
      },
    ];
    const mockNodes: NodeItem[] = [
      {
        id: 'nod-01',
        hostname: 'node1.saintvision.internal',
        status: 'online',
        os: 'linux',
        cpuCores: 16,
        cpuUsagePercent: 20,
        memoryTotalBytes: 32 * 1024 ** 3,
        memoryUsedBytes: 8 * 1024 ** 3,
        storageTotalBytes: 500 * 1024 ** 3,
        storageUsedBytes: 100 * 1024 ** 3,
        gpuCount: 0,
        heartbeatAt: '2026-09-28T00:00:00Z',
      },
    ];

    await act(async () => {
      root.render(
        <WorkspaceList
          workspaces={mockWorkspaces}
          nodes={mockNodes}
          onSelectWorkspace={handleSelect}
          onOpenStudio={handleOpenStudio}
          onCreateWorkspace={vi.fn()}
        />
      );
    });

    const card = container.querySelector('div[role="button"]') as HTMLDivElement;
    expect(card).not.toBeNull();
    expect(card.getAttribute('tabindex')).toBe('0');
    expect(card.getAttribute('aria-label')).toBe('작업공간 Workspace 101 선택');

    // Trigger Enter key on card
    act(() => {
      card.dispatchEvent(new KeyboardEvent('keydown', { key: 'Enter', bubbles: true }));
    });
    expect(handleSelect).toHaveBeenCalledWith('wsp-101');

    // Trigger Space key on card
    act(() => {
      card.dispatchEvent(new KeyboardEvent('keydown', { key: ' ', bubbles: true }));
    });
    expect(handleSelect).toHaveBeenCalledTimes(2);

    // Verify Studio button inside card triggers onOpenStudio and does not trigger onSelectWorkspace
    const studioBtn = Array.from(card.querySelectorAll('button')).find((b) => b.textContent?.includes('Studio에서 열기')) as HTMLButtonElement;
    expect(studioBtn).not.toBeNull();
    act(() => {
      studioBtn.click();
    });
    expect(handleOpenStudio).toHaveBeenCalledWith('wsp-101');
    // handleSelect should NOT be called from inner button
    expect(handleSelect).toHaveBeenCalledTimes(2);
  });

  // DEF-S11-03, 04, 05: useModalA11y focus trap, container wrap, initial focus, and trigger restoration
  it('DEF-S11-03 & DEF-S11-04: useModalA11y handles focus trap, container wrap, and restores focus to trigger', async () => {
    const handleClose = vi.fn();

    const TestModalComponent: React.FC<{ isOpen: boolean }> = ({ isOpen }) => {
      const { containerRef, handleKeyDown } = useModalA11y({ isOpen, onClose: handleClose });
      if (!isOpen) return null;
      return (
        <div ref={containerRef} role="dialog" aria-modal="true" tabIndex={-1} onKeyDown={handleKeyDown}>
          <button id="btn-first">First</button>
          <button id="btn-middle">Middle</button>
          <button id="btn-last">Last</button>
        </div>
      );
    };

    const triggerBtn = document.createElement('button');
    triggerBtn.id = 'external-trigger-btn';
    document.body.appendChild(triggerBtn);
    triggerBtn.focus();
    expect(document.activeElement).toBe(triggerBtn);

    // Open modal
    await act(async () => {
      root.render(<TestModalComponent isOpen={true} />);
    });

    const dialog = container.querySelector('div[role="dialog"]') as HTMLDivElement;
    expect(dialog).not.toBeNull();
    const btnFirst = container.querySelector('#btn-first') as HTMLButtonElement;
    const btnLast = container.querySelector('#btn-last') as HTMLButtonElement;

    // Initial focus on first element
    expect(document.activeElement).toBe(btnFirst);

    // Tab on last element wraps to first element
    btnLast.focus();
    expect(document.activeElement).toBe(btnLast);
    act(() => {
      dialog.dispatchEvent(new KeyboardEvent('keydown', { key: 'Tab', bubbles: true }));
    });
    expect(document.activeElement).toBe(btnFirst);

    // Shift+Tab on first element wraps to last element
    act(() => {
      dialog.dispatchEvent(new KeyboardEvent('keydown', { key: 'Tab', shiftKey: true, bubbles: true }));
    });
    expect(document.activeElement).toBe(btnLast);

    // Shift+Tab when container is focused wraps to last element
    dialog.focus();
    expect(document.activeElement).toBe(dialog);
    act(() => {
      dialog.dispatchEvent(new KeyboardEvent('keydown', { key: 'Tab', shiftKey: true, bubbles: true }));
    });
    expect(document.activeElement).toBe(btnLast);

    // Escape triggers onClose
    act(() => {
      dialog.dispatchEvent(new KeyboardEvent('keydown', { key: 'Escape', bubbles: true }));
    });
    expect(handleClose).toHaveBeenCalledTimes(1);

    // Close modal and verify focus restores to triggerBtn
    await act(async () => {
      root.render(<TestModalComponent isOpen={false} />);
    });
    expect(document.activeElement).toBe(triggerBtn);
    triggerBtn.remove();
  });

  // DEF-S11-03 ~ DEF-S11-06: Priority Modals Verification (ApprovalDetail, AdminSecurityConsole, WorkspaceCreateModal, GitCommitModal, ConflictResolutionModal)
  it('DEF-S11-03 ~ DEF-S11-06: Priority Modals enforce dialog ARIA, Esc handler and labeled title', async () => {
    // 1. WorkspaceCreateModal
    const handleWspClose = vi.fn();
    await act(async () => {
      root.render(
        <WorkspaceCreateModal
          projectId="prj-test"
          isOpen={true}
          onClose={handleWspClose}
          onCreate={vi.fn()}
        />
      );
    });
    const wspDialog = container.querySelector('div[role="dialog"]') as HTMLDivElement;
    expect(wspDialog).not.toBeNull();
    expect(wspDialog.getAttribute('aria-modal')).toBe('true');
    expect(wspDialog.getAttribute('aria-labelledby')).toBe('workspace-create-title');
    act(() => {
      wspDialog.dispatchEvent(new KeyboardEvent('keydown', { key: 'Escape', bubbles: true }));
    });
    expect(handleWspClose).toHaveBeenCalledTimes(1);

    // 2. GitCommitModal
    const handleCommitCancel = vi.fn();
    await act(async () => {
      root.render(
        <GitCommitModal
          files={[{ path: 'src/main.ts', content: 'console.log("ok");', isDirty: true }]}
          parentCommit={null}
          onCommit={vi.fn()}
          onCancel={handleCommitCancel}
        />
      );
    });
    const commitDialog = container.querySelector('div[role="dialog"]') as HTMLDivElement;
    expect(commitDialog).not.toBeNull();
    expect(commitDialog.getAttribute('aria-modal')).toBe('true');
    expect(commitDialog.getAttribute('aria-labelledby')).toBe('git-commit-modal-title');
    act(() => {
      commitDialog.dispatchEvent(new KeyboardEvent('keydown', { key: 'Escape', bubbles: true }));
    });
    expect(handleCommitCancel).toHaveBeenCalledTimes(1);

    // 3. ConflictResolutionModal
    const handleConflictCancel = vi.fn();
    await act(async () => {
      root.render(
        <ConflictResolutionModal
          filePath="src/kernel.ts"
          diff={{
            path: 'src/kernel.ts',
            originalEtag: 'abcdef1234567890',
            modifiedEtag: '1234567890abcdef',
            additionsCount: 1,
            deletionsCount: 0,
            lines: [{ type: 'same', content: 'const a = 1;' }],
            hunks: [],
            hasConflict: true,
          } as any}
          onKeepMine={vi.fn()}
          onAcceptRemote={vi.fn()}
          onMerge={vi.fn()}
          onCancel={handleConflictCancel}
        />
      );
    });
    const conflictDialog = container.querySelector('div[role="dialog"]') as HTMLDivElement;
    expect(conflictDialog).not.toBeNull();
    expect(conflictDialog.getAttribute('aria-modal')).toBe('true');
    expect(conflictDialog.getAttribute('aria-labelledby')).toBe('conflict-resolution-title');
    act(() => {
      conflictDialog.dispatchEvent(new KeyboardEvent('keydown', { key: 'Escape', bubbles: true }));
    });
    expect(handleConflictCancel).toHaveBeenCalledTimes(1);

    // 4. ApprovalDetail (rejection modal)
    const mockApproval: ApprovalItem = {
      id: 'app-01',
      projectId: 'prj-alpha',
      runId: 'run-01',
      nonce: 'nonce-123',
      actionDigest: 'sha256-mock-digest-1234567890',
      riskLevel: 'L2',
      command: 'echo deploy',
      policyReason: 'AC-10 Policy Requirement',
      status: 'pending',
      expiresAt: new Date(Date.now() + 60000).toISOString(),
    };
    await act(async () => {
      root.render(
        <ApprovalDetail
          approval={mockApproval}
          currentUserId="user-01"
          onApprove={vi.fn()}
          onReject={vi.fn()}
        />
      );
    });
    const rejectBtn = Array.from(container.querySelectorAll('button')).find((b) => b.textContent?.includes('반려'));
    expect(rejectBtn).not.toBeUndefined();
    await act(async () => {
      rejectBtn?.click();
    });
    const rejectDialog = container.querySelector('[role="dialog"]');
    expect(rejectDialog).not.toBeNull();
    expect(rejectDialog?.getAttribute('aria-modal')).toBe('true');
    expect(rejectDialog?.getAttribute('aria-labelledby')).toBe('reject-modal-title');
    act(() => {
      rejectDialog?.dispatchEvent(new KeyboardEvent('keydown', { key: 'Escape', bubbles: true }));
    });
    expect(container.querySelector('[role="dialog"]')).toBeNull();

    // 5. AdminSecurityConsole (kill-switch modal)
    await act(async () => {
      root.render(
        <AdminSecurityConsole
          nodes={[]}
          currentUser={{ id: 'admin-1', name: 'Admin', role: 'admin' }}
        />
      );
    });
    const killSwitchTrigger = Array.from(container.querySelectorAll('button')).find((b) => b.textContent?.includes('Kill Switch'));
    expect(killSwitchTrigger).not.toBeUndefined();
    await act(async () => {
      killSwitchTrigger?.click();
    });
    const killSwitchDialog = container.querySelector('[data-testid="kill-switch-modal"]') as HTMLDivElement;
    expect(killSwitchDialog).not.toBeNull();
    expect(killSwitchDialog.getAttribute('role')).toBe('dialog');
    expect(killSwitchDialog.getAttribute('aria-modal')).toBe('true');
    expect(killSwitchDialog.getAttribute('aria-labelledby')).toBe('kill-switch-modal-title');
    act(() => {
      killSwitchDialog.dispatchEvent(new KeyboardEvent('keydown', { key: 'Escape', bubbles: true }));
    });
    expect(container.querySelector('[data-testid="kill-switch-modal"]')).toBeNull();

    // 6. RunDetail (run cancellation modal)
    const mockRun: RunItem = {
      id: 'run-alpha',
      projectId: 'prj-alpha',
      state: 'running',
    };
    await act(async () => {
      root.render(
        <RunDetail
          run={mockRun}
          onBack={vi.fn()}
          onCancelRun={vi.fn()}
        />
      );
    });
    const cancelRunBtn = Array.from(container.querySelectorAll('button')).find((b) => b.textContent?.includes('Run 취소'));
    expect(cancelRunBtn).not.toBeUndefined();
    await act(async () => {
      cancelRunBtn?.click();
    });
    const runCancelDialog = container.querySelector('div[aria-labelledby="run-cancel-modal-title"]') as HTMLDivElement;
    expect(runCancelDialog).not.toBeNull();
    expect(runCancelDialog.getAttribute('role')).toBe('dialog');
    expect(runCancelDialog.getAttribute('aria-modal')).toBe('true');
    act(() => {
      runCancelDialog.dispatchEvent(new KeyboardEvent('keydown', { key: 'Escape', bubbles: true }));
    });
    expect(container.querySelector('div[aria-labelledby="run-cancel-modal-title"]')).toBeNull();
  });

  // PR #178 Follow-up: DeveloperStudio Cancellation Modal direct verification (useModalA11y at :153, role=dialog at :2657)
  it('PR #178 Follow-up: DeveloperStudio cancel modal enforces role="dialog", aria-modal, aria-labelledby, Tab/Shift+Tab cycle, Esc close, and trigger restoration', async () => {
    const mockStudioProject: ProjectItem = {
      id: 'prj_studio_cancel',
      name: 'Studio Cancel Test Project',
      createdAt: '2026-09-28T00:00:00Z',
    };
    const mockRunningRun: RunItem = {
      id: 'run_studio_cancel_01',
      projectId: 'prj_studio_cancel',
      state: 'running',
      objective: 'Run cancellation test',
      createdAt: '2026-09-28T00:00:00Z',
    };

    const clientSpy = vi.spyOn(clientModule, 'apiClient').mockImplementation(async (endpoint: string) => {
      if (endpoint.includes('/workspaces')) {
        return { projectId: mockStudioProject.id, workspaces: [] } as any;
      }
      return {} as any;
    });

    try {
      await act(async () => {
        root.render(
          <DeveloperStudio
            project={mockStudioProject}
            nodes={[]}
            runs={[mockRunningRun]}
            initialStep={4}
            initialRunId={mockRunningRun.id}
          />
        );
      });

      // 1. Find and focus actual trigger button from DeveloperStudio.tsx:2117
      const cancelTrigger = Array.from(container.querySelectorAll('button')).find((b) =>
        b.textContent?.includes('즉시 취소 (Cancel)')
      );
      expect(cancelTrigger).not.toBeUndefined();
      expect(cancelTrigger).not.toBeNull();

      cancelTrigger!.focus();
      expect(document.activeElement).toBe(cancelTrigger);

      // Click trigger to open cancellation modal
      await act(async () => {
        cancelTrigger!.click();
      });

      // 2. Assert role, aria-modal, aria-labelledby
      const cancelDialog = container.querySelector('div[aria-labelledby="cancel-title"]') as HTMLDivElement;
      expect(cancelDialog).not.toBeNull();
      expect(cancelDialog.getAttribute('role')).toBe('dialog');
      expect(cancelDialog.getAttribute('aria-modal')).toBe('true');
      expect(cancelDialog.getAttribute('aria-labelledby')).toBe('cancel-title');

      // 3. Assert Tab / Shift+Tab focus trap cycling
      const focusable = Array.from(
        cancelDialog.querySelectorAll<HTMLElement>(
          'button:not([disabled]), [href], input:not([disabled]), select:not([disabled]), textarea:not([disabled]), [tabindex]:not([tabindex="-1"])'
        )
      );
      expect(focusable.length).toBeGreaterThan(1);
      const firstFocusable = focusable[0];
      const lastFocusable = focusable[focusable.length - 1];

      // Initial focus on first element
      expect(document.activeElement).toBe(firstFocusable);

      // Tab on last element wraps to first
      lastFocusable.focus();
      expect(document.activeElement).toBe(lastFocusable);
      act(() => {
        cancelDialog.dispatchEvent(new KeyboardEvent('keydown', { key: 'Tab', bubbles: true }));
      });
      expect(document.activeElement).toBe(firstFocusable);

      // Shift+Tab on first element wraps to last
      act(() => {
        cancelDialog.dispatchEvent(new KeyboardEvent('keydown', { key: 'Tab', shiftKey: true, bubbles: true }));
      });
      expect(document.activeElement).toBe(lastFocusable);

      // 4. Assert Esc closes modal
      act(() => {
        cancelDialog.dispatchEvent(new KeyboardEvent('keydown', { key: 'Escape', bubbles: true }));
      });
      expect(container.querySelector('div[aria-labelledby="cancel-title"]')).toBeNull();

      // 5. Assert focus restored to trigger
      expect(document.activeElement).toBe(cancelTrigger);
    } finally {
      clientSpy.mockRestore();
    }
  });

  // PR #178 Follow-up: DeveloperStudio Receipt Modal direct verification (useModalA11y at :158, role=dialog at :2731)
  it('PR #178 Follow-up: DeveloperStudio receipt-modal enforces role="dialog", aria-modal, aria-labelledby, Tab/Shift+Tab cycle, Esc close, and trigger restoration', async () => {
    const mockStudioProject: ProjectItem = {
      id: 'prj_studio_receipt',
      name: 'Studio Receipt Test Project',
      createdAt: '2026-09-28T00:00:00Z',
    };
    const mockReceipt: NodeStopReceiptView = {
      receiptId: 'rcp_run_studio_rcp_01',
      runId: 'run_studio_rcp_01',
      nodeId: 'nod_studio_01',
      commandId: 'cmd_studio_01',
      exitCode: 0,
      physicallyStopped: true,
      resourceReclaimed: true,
      verified: true,
      stoppedAt: '2026-09-28T10:00:00Z',
      supervisorLabel: 'isolated_sandbox',
    };
    const mockCompletedRun: RunItem = {
      id: 'run_studio_rcp_01',
      projectId: 'prj_studio_receipt',
      state: 'succeeded',
      objective: 'Run receipt inspection test',
      createdAt: '2026-09-28T00:00:00Z',
      stopReceipt: mockReceipt,
    };

    const clientSpy = vi.spyOn(clientModule, 'apiClient').mockImplementation(async (endpoint: string) => {
      if (endpoint.includes('/workspaces')) {
        return { projectId: mockStudioProject.id, workspaces: [] } as any;
      }
      return {} as any;
    });

    try {
      await act(async () => {
        root.render(
          <DeveloperStudio
            project={mockStudioProject}
            nodes={[]}
            runs={[mockCompletedRun]}
            initialStep={4}
            initialRunId={mockCompletedRun.id}
          />
        );
      });

      // 1. Find and focus actual trigger button from DeveloperStudio.tsx:2123 (data-testid="inspect-receipt-btn")
      const receiptTrigger = container.querySelector('[data-testid="inspect-receipt-btn"]') as HTMLButtonElement;
      expect(receiptTrigger).not.toBeNull();

      receiptTrigger.focus();
      expect(document.activeElement).toBe(receiptTrigger);

      // Click trigger to open receipt modal
      await act(async () => {
        receiptTrigger.click();
      });

      // 2. Assert role, aria-modal, aria-labelledby, data-testid
      const receiptDialog = container.querySelector('[data-testid="receipt-modal"]') as HTMLDivElement;
      expect(receiptDialog).not.toBeNull();
      expect(receiptDialog.getAttribute('role')).toBe('dialog');
      expect(receiptDialog.getAttribute('aria-modal')).toBe('true');
      expect(receiptDialog.getAttribute('aria-labelledby')).toBe('receipt-title');

      // 3. Assert Tab / Shift+Tab focus trap cycling
      const focusable = Array.from(
        receiptDialog.querySelectorAll<HTMLElement>(
          'button:not([disabled]), [href], input:not([disabled]), select:not([disabled]), textarea:not([disabled]), [tabindex]:not([tabindex="-1"])'
        )
      );
      expect(focusable.length).toBeGreaterThan(1);
      const firstFocusable = focusable[0];
      const lastFocusable = focusable[focusable.length - 1];

      // Initial focus on first element
      expect(document.activeElement).toBe(firstFocusable);

      // Tab on last element wraps to first
      lastFocusable.focus();
      expect(document.activeElement).toBe(lastFocusable);
      act(() => {
        receiptDialog.dispatchEvent(new KeyboardEvent('keydown', { key: 'Tab', bubbles: true }));
      });
      expect(document.activeElement).toBe(firstFocusable);

      // Shift+Tab on first element wraps to last
      act(() => {
        receiptDialog.dispatchEvent(new KeyboardEvent('keydown', { key: 'Tab', shiftKey: true, bubbles: true }));
      });
      expect(document.activeElement).toBe(lastFocusable);

      // 4. Assert Esc closes modal
      act(() => {
        receiptDialog.dispatchEvent(new KeyboardEvent('keydown', { key: 'Escape', bubbles: true }));
      });
      expect(container.querySelector('[data-testid="receipt-modal"]')).toBeNull();

      // 5. Assert focus restored to trigger
      expect(document.activeElement).toBe(receiptTrigger);
    } finally {
      clientSpy.mockRestore();
    }
  });

  // DEF-S11-05: DesktopWindow Escape isolation
  it('DEF-S11-05: DesktopWindow ignores Esc when input is focused and closes on window body Esc', async () => {
    const handleClose = vi.fn();
    const mockWin: IDesktopWindow = {
      id: 'win-1',
      appId: 'terminal',
      title: 'Terminal Window',
      icon: '⌨️',
      isOpen: true,
      isMinimized: false,
      isMaximized: false,
      position: { x: 10, y: 10 },
      size: { width: 600, height: 400 },
      zIndex: 10,
    };
    await act(async () => {
      root.render(
        <DesktopWindowComponent
          window={mockWin}
          isActive={true}
          onFocus={vi.fn()}
          onClose={handleClose}
          onMinimize={vi.fn()}
          onToggleMaximize={vi.fn()}
        >
          <input data-testid="term-input" />
        </DesktopWindowComponent>
      );
    });
    const termInput = container.querySelector('[data-testid="term-input"]') as HTMLInputElement;
    termInput.focus();
    // Esc while typing in input must NOT close window
    act(() => {
      termInput.dispatchEvent(new KeyboardEvent('keydown', { key: 'Escape', bubbles: true }));
    });
    expect(handleClose).not.toHaveBeenCalled();

    // Esc on window body closes window
    const winEl = container.firstElementChild as HTMLElement;
    act(() => {
      winEl.dispatchEvent(new KeyboardEvent('keydown', { key: 'Escape', bubbles: true }));
    });
    expect(handleClose).toHaveBeenCalledTimes(1);
  });

  // DEF-S11-05: DesktopShell window Escape keydown does not close active desktop window
  it('DEF-S11-05: DesktopShell window Escape keydown does not close active desktop window', async () => {
    await act(async () => {
      root.render(
        <DesktopShell
          currentUser={{ id: 'gemini', name: 'Gemini', role: 'admin' }}
          nodes={[]}
          runs={[]}
          currentTheme="dark"
          onChangeUser={vi.fn()}
          onSwitchToPortalView={vi.fn()}
          onToggleTheme={vi.fn()}
        />
      );
    });

    // win_my_computer is open by default
    const myCompWin = container.querySelector('[aria-labelledby="window-title-win_my_computer"]');
    expect(myCompWin).not.toBeNull();

    // Dispatch Escape on window
    act(() => {
      window.dispatchEvent(new KeyboardEvent('keydown', { key: 'Escape', bubbles: true }));
    });

    // Window must remain open (global window listener does not close active window)
    const myCompWinAfter = container.querySelector('[aria-labelledby="window-title-win_my_computer"]');
    expect(myCompWinAfter).not.toBeNull();
  });

  // DEF-S11-06: Header active tab aria-current="page"
  it('DEF-S11-06: Header active tab has aria-current="page"', async () => {
    await act(async () => {
      root.render(
        <Header
          currentUser={{ id: 'gemini', name: 'Gemini Agent', role: 'admin' }}
          activeTab="workspaces"
          onSelectTab={vi.fn()}
          currentTheme="dark"
          onToggleTheme={vi.fn()}
        />
      );
    });

    const activeTabBtn = container.querySelector('[data-testid="header-tab-workspaces"]');
    expect(activeTabBtn).not.toBeNull();
    expect(activeTabBtn?.getAttribute('aria-current')).toBe('page');

    const inactiveTabBtn = container.querySelector('[data-testid="header-tab-nodes"]');
    expect(inactiveTabBtn).not.toBeNull();
    expect(inactiveTabBtn?.getAttribute('aria-current')).toBeNull();
  });

  // DEF-S11-15 & DEF-S11-08, 11~19: ReleaseCandidateView integrity and dynamic audit status binding
  it('DEF-S11-15: ReleaseCandidateView dynamically binds audit status and displays FAIL on failure', async () => {
    // Spy on getAccessibilityAudits to inject a failed audit
    const spy = vi.spyOn(ReleaseManager.prototype, 'getAccessibilityAudits').mockReturnValue([
      {
        ruleId: 'wcag21-1.4.3-contrast-minimum',
        wcagLevel: 'AA',
        description: '본문 텍스트와 배경 간 명도 대비 미달',
        status: 'fail',
      },
    ]);

    await act(async () => {
      root.render(<ReleaseCandidateView />);
    });

    const badges = Array.from(container.querySelectorAll('span')).map((s) => s.textContent?.trim());
    expect(badges).toContain('FAIL');
    spy.mockRestore();
  });

  it('DEF-S11-08, 11~19: ReleaseCandidateView removes false claims and enforces truthful simulation status', async () => {
    await act(async () => {
      root.render(<ReleaseCandidateView />);
    });

    const text = container.textContent || '';

    // False claims eliminated
    expect(text).not.toContain('(ZERO BUG)');

    // Truthful simulation / unmeasured labels confirmed per Card 126 / F1
    expect(text).toContain('주요 SLO 실측치 및 목표 비교 (AC-11)');
    expect(text).toContain('UNMEASURED (미측정)');
    expect(text).toContain('미측정 (NOT_OBSERVED)');
    expect(text).toContain('측정 환경: 실측 텔레메트리 연동 대기 (미측정)');
    expect(text).toContain('ACTIVE LIVE');
    expect(text).toContain('✔ 검증 완료');

    // DEF-S11-17: Table wrapper has overflowX auto
    const tableWrappers = container.querySelectorAll('div[style*="overflow-x: auto"], div[style*="overflowX: auto"]');
    expect(tableWrappers.length).toBeGreaterThanOrEqual(1);

    // DEF-S11-18: Viewport buttons dynamically affect container maxWidth
    const mobileBtn = Array.from(container.querySelectorAll('button')).find((b) => b.textContent?.trim() === 'MOBILE');
    expect(mobileBtn).not.toBeUndefined();
    await act(async () => {
      mobileBtn?.click();
    });
    const mainWrapper = container.firstElementChild as HTMLElement;
    expect(mainWrapper.style.maxWidth).toBe('375px');

    const tabletBtn = Array.from(container.querySelectorAll('button')).find((b) => b.textContent?.trim() === 'TABLET');
    expect(tabletBtn).not.toBeUndefined();
    await act(async () => {
      tabletBtn?.click();
    });
    expect(mainWrapper.style.maxWidth).toBe('768px');

    const desktopBtn = Array.from(container.querySelectorAll('button')).find((b) => b.textContent?.trim() === 'DESKTOP');
    expect(desktopBtn).not.toBeUndefined();
    await act(async () => {
      desktopBtn?.click();
    });
    expect(mainWrapper.style.maxWidth).toBe('1400px');

    // DEF-S11-19: Rollback button has explicit aria-label with version tag
    const rollbackBtn = container.querySelector('button[aria-label*="롤백 실행 (AC-11)"]');
    expect(rollbackBtn).not.toBeNull();
    expect(rollbackBtn?.getAttribute('aria-label')).toBe('이 버전(v1.0.0-rc.1)으로 롤백 실행 (AC-11)');
  });

  // DEF-S11-16: ReleaseManager candidate initial state
  it('DEF-S11-16: ReleaseManager initializes v1.0.0-rc.1 with rollbackVerified: true and verifies rollback transition', () => {
    const rm = new ReleaseManager();
    const candidates = rm.getReleaseCandidates();
    const rc1 = candidates.find((c) => c.tag === 'v1.0.0-rc.1');
    expect(rc1).not.toBeUndefined();
    expect(rc1?.rollbackVerified).toBe(true);

    // After rollback execution, rollbackVerified remains true and activeCandidate is rc1
    const res = rm.rollbackToVersion('v1.0.0-rc.1');
    expect(res.success).toBe(true);
    expect(res.activeCandidate?.rollbackVerified).toBe(true);
  });

  // DEF-S11-09 & DEF-S11-10: Mathematical contrast verification by dynamically parsing index.css ?raw tokens
  it('DEF-S11-09 & DEF-S11-10: Parses index.css tokens dynamically and confirms contrast ratios exceed AA standards', () => {
    // Relative Luminance calculation per WCAG 2.1 specs:
    // L = 0.2126 * R + 0.7152 * G + 0.0722 * B
    const parseHex = (hex: string) => {
      const clean = hex.replace('#', '').trim();
      const num = parseInt(clean, 16);
      return [(num >> 16) & 255, (num >> 8) & 255, num & 255];
    };

    const getLuminance = (hex: string) => {
      const [r, g, b] = parseHex(hex);
      const a = [r, g, b].map((v) => {
        v /= 255;
        return v <= 0.04045 ? v / 12.92 : Math.pow((v + 0.055) / 1.055, 2.4);
      });
      return a[0] * 0.2126 + a[1] * 0.7152 + a[2] * 0.0722;
    };

    const getContrast = (hex1: string, hex2: string) => {
      const l1 = getLuminance(hex1);
      const l2 = getLuminance(hex2);
      const lighter = Math.max(l1, l2);
      const darker = Math.min(l1, l2);
      return (lighter + 0.05) / (darker + 0.05);
    };

    // Extract tokens from index.css dynamically
    const rootBlock = indexCss.match(/:root\s*\{([^}]+)\}/)?.[1] || '';
    const darkBlock = indexCss.match(/\[data-theme=['"]dark['"]\]\s*\{([^}]+)\}/)?.[1] || '';

    const extractToken = (block: string, name: string): string => {
      const regex = new RegExp(`${name}\\s*:\\s*([^;]+);`);
      const match = block.match(regex);
      if (!match) throw new Error(`Token ${name} not found in CSS block`);
      return match[1].split('/*')[0].trim();
    };

    const darkPrimaryBg = extractToken(darkBlock, '--color-brand-primary-bg');
    const darkPrimaryText = extractToken(darkBlock, '--color-brand-primary');
    const darkDangerBg = extractToken(darkBlock, '--color-status-offline-bg');
    const darkDangerText = extractToken(darkBlock, '--color-status-offline');
    const darkBorderStrong = extractToken(darkBlock, '--color-border-strong');
    const darkBgSurface = extractToken(darkBlock, '--color-bg-surface');
    const darkBgSubtle = extractToken(darkBlock, '--color-bg-subtle');

    const rootBorderStrong = extractToken(rootBlock, '--color-border-strong');
    const rootBgSubtle = extractToken(rootBlock, '--color-bg-subtle');

    // 1. Dark primary button bg on white text exceeds 4.5:1 (actual 6.70:1)
    const primaryBgContrast = getContrast('#ffffff', darkPrimaryBg);
    expect(primaryBgContrast).toBeGreaterThanOrEqual(4.5);

    // 2. Dark danger button bg on white text exceeds 4.5:1 (actual 4.83:1)
    const dangerBgContrast = getContrast('#ffffff', darkDangerBg);
    expect(dangerBgContrast).toBeGreaterThanOrEqual(4.5);

    // 3. Dark brand text/ring on dark surface exceeds 4.5:1 for text, 3.0:1 for ring (actual 6.98:1)
    const darkTextContrast = getContrast(darkPrimaryText, darkBgSurface);
    expect(darkTextContrast).toBeGreaterThanOrEqual(4.5);

    // 4. Dark danger text on dark surface exceeds 4.5:1 (actual 6.41:1)
    const darkDangerTextContrast = getContrast(darkDangerText, darkBgSurface);
    expect(darkDangerTextContrast).toBeGreaterThanOrEqual(4.5);

    // 5. Non-text progress bar UI contrast exceeds 3.0:1 (actual 5.77:1 on subtle)
    const progressBarContrast = getContrast(darkPrimaryText, darkBgSubtle);
    expect(progressBarContrast).toBeGreaterThanOrEqual(3.0);

    // 6. Non-text form input borders exceed 3.0:1 (WCAG 1.4.11)
    const darkBorderContrast = getContrast(darkBorderStrong, darkBgSubtle);
    const lightBorderContrast = getContrast(rootBorderStrong, rootBgSubtle);
    expect(darkBorderContrast).toBeGreaterThanOrEqual(3.0);
    expect(lightBorderContrast).toBeGreaterThanOrEqual(3.0);
  });

  // DEF-S11-09: Button and non-button components bind -bg tokens and enforce revert-fail
  it('DEF-S11-09: Button and non-button components bind -bg tokens and enforce revert-fail', async () => {
    // 1. Button variant="primary" binds var(--color-brand-primary-bg)
    await act(async () => {
      root.render(<Button variant="primary">Submit Primary</Button>);
    });
    const btn = container.querySelector('button') as HTMLButtonElement;
    expect(btn).not.toBeNull();
    expect(btn.style.backgroundColor).toContain('var(--color-brand-primary-bg');

    // 2. Button variant="danger" binds var(--color-status-offline-bg)
    await act(async () => {
      root.render(<Button variant="danger">Delete Danger</Button>);
    });
    const dangerBtn = container.querySelector('button') as HTMLButtonElement;
    expect(dangerBtn).not.toBeNull();
    expect(dangerBtn.style.backgroundColor).toContain('var(--color-status-offline-bg');

    // 3. RunList active filter binds var(--color-brand-primary-bg)
    await act(async () => {
      root.render(
        <RunList
          runs={[]}
          selectedFilter="ALL"
          onSelectFilter={vi.fn()}
          onSelectRun={vi.fn()}
        />
      );
    });
    const allFilterBtn = Array.from(container.querySelectorAll('button')).find((b) => b.textContent?.includes('전체'));
    expect(allFilterBtn).not.toBeUndefined();
    expect(allFilterBtn?.style.backgroundColor).toBe('var(--color-brand-primary-bg)');
  });

  // DEF-S11-09: Source scan ensures zero instances of var(--color-brand-primary) with white text in apps/web/src
  it('DEF-S11-09: Source scan ensures zero instances of var(--color-brand-primary) with white text in apps/web/src', () => {
    const srcDir = path.resolve(__dirname, '../src');
    const files: string[] = [];
    const walk = (dir: string) => {
      for (const ent of fs.readdirSync(dir, { withFileTypes: true })) {
        const full = path.join(dir, ent.name);
        if (ent.isDirectory()) walk(full);
        else if (ent.name.endsWith('.ts') || ent.name.endsWith('.tsx')) files.push(full);
      }
    };
    walk(srcDir);

    const brandPrimaryBgMatches: { file: string; line: number; content: string }[] = [];
    for (const file of files) {
      const rel = path.relative(srcDir, file).replace(/\\/g, '/');
      const lines = fs.readFileSync(file, 'utf-8').split('\n');
      lines.forEach((line, idx) => {
        if (/backgroundColor:\s*.*'var\(--color-brand-primary\)'/.test(line)) {
          brandPrimaryBgMatches.push({ file: rel, line: idx + 1, content: line.trim() });
        }
      });
    }

    // Exactly three matches are permitted: progress bars and step indicator without text (ClusterOverview.tsx, NodeList.tsx, DeveloperStudio.tsx)
    expect(brandPrimaryBgMatches).toHaveLength(3);
    const matchedFiles = brandPrimaryBgMatches.map((m) => m.file);
    expect(matchedFiles).toContain('features/dashboard/ClusterOverview.tsx');
    expect(matchedFiles).toContain('features/nodes/NodeList.tsx');
    expect(matchedFiles).toContain('features/studio/DeveloperStudio.tsx');

    // Verify none of the matches contain white text
    for (const match of brandPrimaryBgMatches) {
      expect(match.content).not.toContain('#ffffff');
      expect(match.content).not.toContain('color:');
    }
  });
});
