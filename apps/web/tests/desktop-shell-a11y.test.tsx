// @vitest-environment happy-dom
// @ts-ignore
globalThis.IS_REACT_ACT_ENVIRONMENT = true;
import React, { act } from 'react';
import { createRoot, Root } from 'react-dom/client';
import { describe, it, expect, vi, beforeEach, afterEach } from 'vitest';
import { DesktopShell } from '../src/features/desktop/DesktopShell';
import { useModalA11y } from '../src/shared/ui/useModalA11y';

const MOCK_PROPS = {
  projectId: 'prj-test-a11y',
  nodes: [
    {
      id: 'nod_01ARZ3NDEKTSV4RRFFQ69G5FAV',
      hostname: 'node-win-main',
      os: 'windows' as const,
      cpuCores: 16,
      cpuUsagePercent: 25,
      memoryTotalBytes: 64 * 1024 ** 3,
      memoryUsagePercent: 35,
      gpuName: 'NVIDIA RTX 4090',
      gpuCount: 1,
      status: 'online' as const,
      labels: { tier: 'general' },
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
};

describe('DesktopShell & useModalA11y Accessibility (ACC-03, ACC-04, focus_is_trigger)', () => {
  let container: HTMLDivElement;
  let root: Root;

  beforeEach(() => {
    vi.useFakeTimers();
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
    vi.useRealTimers();
  });

  it('Start Menu: Escape key closes Start Menu and restores focus to trigger button (focus_is_trigger)', async () => {
    await act(async () => {
      root.render(<DesktopShell {...MOCK_PROPS} />);
    });

    const startBtn = container.querySelector('button[aria-label="SaintVision 시작 메뉴"]') as HTMLButtonElement;
    expect(startBtn).not.toBeNull();
    expect(startBtn.getAttribute('aria-haspopup')).toBe('menu');
    expect(startBtn.getAttribute('aria-expanded')).toBe('false');

    // 1. Open Start Menu by clicking trigger
    await act(async () => {
      startBtn.click();
      vi.advanceTimersByTime(50);
    });

    const startMenu = container.querySelector('#desktop-start-menu-dropdown') as HTMLDivElement;
    expect(startMenu).not.toBeNull();
    expect(startMenu.getAttribute('role')).toBe('menu');
    expect(startBtn.getAttribute('aria-expanded')).toBe('true');

    // 2. Press Escape key to dismiss Start Menu
    await act(async () => {
      const escEvent = new KeyboardEvent('keydown', { key: 'Escape', bubbles: true, cancelable: true });
      window.dispatchEvent(escEvent);
      vi.advanceTimersByTime(50);
    });

    // 3. Verify menu is dismissed and focus returned to trigger button
    expect(container.querySelector('#desktop-start-menu-dropdown')).toBeNull();
    expect(startBtn.getAttribute('aria-expanded')).toBe('false');
    expect(document.activeElement).toBe(startBtn);
    expect(document.activeElement?.getAttribute('aria-label')).toBe('SaintVision 시작 메뉴');
  });

  it('Notification Center: Escape key closes drawer and restores focus to notification trigger button', async () => {
    await act(async () => {
      root.render(<DesktopShell {...MOCK_PROPS} />);
    });

    const notifBtn = container.querySelector('button[aria-label="알림 센터"]') as HTMLButtonElement;
    expect(notifBtn).not.toBeNull();
    expect(notifBtn.getAttribute('aria-haspopup')).toBe('dialog');
    expect(notifBtn.getAttribute('aria-expanded')).toBe('false');

    // 1. Open Notification Center
    await act(async () => {
      notifBtn.click();
      vi.advanceTimersByTime(50);
    });

    const notifDrawer = container.querySelector('#desktop-notification-drawer') as HTMLDivElement;
    expect(notifDrawer).not.toBeNull();
    expect(notifDrawer.getAttribute('role')).toBe('dialog');
    expect(notifDrawer.getAttribute('aria-modal')).toBe('true');
    expect(notifBtn.getAttribute('aria-expanded')).toBe('true');

    // 2. Press Escape key
    await act(async () => {
      const escEvent = new KeyboardEvent('keydown', { key: 'Escape', bubbles: true, cancelable: true });
      window.dispatchEvent(escEvent);
      vi.advanceTimersByTime(50);
    });

    // 3. Verify drawer is dismissed and focus returned to notification trigger button
    expect(container.querySelector('#desktop-notification-drawer')).toBeNull();
    expect(notifBtn.getAttribute('aria-expanded')).toBe('false');
    expect(document.activeElement).toBe(notifBtn);
    expect(document.activeElement?.getAttribute('aria-label')).toBe('알림 센터');
  });

  it('Notification Center: Close button (×) closes drawer and restores focus to notification trigger button', async () => {
    await act(async () => {
      root.render(<DesktopShell {...MOCK_PROPS} />);
    });

    const notifBtn = container.querySelector('button[aria-label="알림 센터"]') as HTMLButtonElement;
    expect(notifBtn).not.toBeNull();

    await act(async () => {
      notifBtn.click();
      vi.advanceTimersByTime(50);
    });

    const closeBtn = container.querySelector('button[aria-label="알림 센터 닫기"]') as HTMLButtonElement;
    expect(closeBtn).not.toBeNull();

    await act(async () => {
      closeBtn.click();
      vi.advanceTimersByTime(50);
    });

    expect(container.querySelector('#desktop-notification-drawer')).toBeNull();
    expect(document.activeElement).toBe(notifBtn);
  });

  it('Start Menu: Focus Trap cycles inside menu (Tab & Shift+Tab)', async () => {
    await act(async () => {
      root.render(<DesktopShell {...MOCK_PROPS} />);
    });

    const startBtn = container.querySelector('button[aria-label="SaintVision 시작 메뉴"]') as HTMLButtonElement;
    await act(async () => {
      startBtn.click();
      vi.advanceTimersByTime(50);
    });

    const startMenu = container.querySelector('#desktop-start-menu-dropdown') as HTMLDivElement;
    const focusable = startMenu.querySelectorAll<HTMLElement>(
      'button:not([disabled]), [href], input:not([disabled]), [tabindex]:not([tabindex="-1"])'
    );
    expect(focusable.length).toBeGreaterThan(1);
    const firstBtn = focusable[0];
    const lastBtn = focusable[focusable.length - 1];

    // Focus last button and press Tab -> should wrap to first button
    lastBtn.focus();
    expect(document.activeElement).toBe(lastBtn);
    await act(async () => {
      const tabEvent = new KeyboardEvent('keydown', { key: 'Tab', bubbles: true, cancelable: true });
      window.dispatchEvent(tabEvent);
    });
    expect(document.activeElement).toBe(firstBtn);

    // Focus first button and press Shift+Tab -> should wrap to last button
    firstBtn.focus();
    expect(document.activeElement).toBe(firstBtn);
    await act(async () => {
      const shiftTabEvent = new KeyboardEvent('keydown', { key: 'Tab', shiftKey: true, bubbles: true, cancelable: true });
      window.dispatchEvent(shiftTabEvent);
    });
    expect(document.activeElement).toBe(lastBtn);
  });

  it('useModalA11y: restores focus to explicit triggerRef when provided', async () => {
    const handleClose = vi.fn();
    const externalTrigger = document.createElement('button');
    externalTrigger.id = 'explicit-test-trigger';
    externalTrigger.textContent = 'Explicit Trigger';
    document.body.appendChild(externalTrigger);

    const triggerRefHolder = { current: externalTrigger };

    const ModalTestComponent: React.FC<{ isOpen: boolean }> = ({ isOpen }) => {
      const { containerRef, handleKeyDown } = useModalA11y({
        isOpen,
        onClose: handleClose,
        triggerRef: triggerRefHolder,
      });
      if (!isOpen) return null;
      return (
        <div ref={containerRef} role="dialog" aria-modal="true" onKeyDown={handleKeyDown}>
          <button id="modal-inner-btn">Inner</button>
        </div>
      );
    };

    // Render modal closed first
    await act(async () => {
      root.render(<ModalTestComponent isOpen={false} />);
    });

    // Blur or focus body so document.activeElement is body
    document.body.focus();

    // Open modal
    await act(async () => {
      root.render(<ModalTestComponent isOpen={true} />);
      vi.advanceTimersByTime(50);
    });

    // Close modal
    await act(async () => {
      root.render(<ModalTestComponent isOpen={false} />);
      vi.advanceTimersByTime(50);
    });

    // Expect focus to have restored to externalTrigger
    expect(document.activeElement).toBe(externalTrigger);
    externalTrigger.remove();
  });
});
