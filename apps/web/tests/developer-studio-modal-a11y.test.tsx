/** @vitest-environment happy-dom */
import React, { act } from 'react';
import { createRoot, Root } from 'react-dom/client';
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest';
import { DeveloperStudio } from '../src/features/studio/DeveloperStudio';
import * as clientModule from '../src/shared/api/client';
import type { ProjectItem, RunItem, NodeStopReceiptView } from '../src/contracts/types';

(globalThis as any).IS_REACT_ACT_ENVIRONMENT = true;

describe('DeveloperStudio Modal A11y (Card 138 Item 3)', () => {
  let root: Root;
  let container: HTMLDivElement;

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

  it('DeveloperStudio cancel modal enforces role="dialog", aria-modal, aria-labelledby, Tab/Shift+Tab cycle, Esc close, and trigger restoration', async () => {
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

      // 1. Find and focus actual trigger button from DeveloperStudio
      const cancelTrigger = Array.from(container.querySelectorAll('button')).find((b) =>
        b.textContent?.includes('즉시 취소 (Cancel)')
      );
      expect(cancelTrigger).toBeDefined();

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

  it('DeveloperStudio receipt-modal enforces role="dialog", aria-modal, aria-labelledby, Tab/Shift+Tab cycle, Esc close, and trigger restoration', async () => {
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

      // 1. Find and focus actual trigger button (data-testid="inspect-receipt-btn")
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
});
