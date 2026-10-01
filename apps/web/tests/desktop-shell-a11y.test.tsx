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
    expect(startBtn.getAttribute('aria-haspopup')).toBe('dialog');
    expect(startBtn.getAttribute('aria-expanded')).toBe('false');

    // 1. Open Start Menu by clicking trigger
    await act(async () => {
      startBtn.click();
      vi.advanceTimersByTime(50);
    });

    const startMenu = container.querySelector('#desktop-start-menu-dropdown') as HTMLDivElement;
    expect(startMenu).not.toBeNull();
    expect(startMenu.getAttribute('role')).toBe('dialog');
    expect(startMenu.getAttribute('aria-label')).toBe('시작 메뉴');
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

  it('F3: Notification Center: Focus Trap cycles inside single-control drawer (Tab & Shift+Tab)', async () => {
    await act(async () => {
      root.render(<DesktopShell {...MOCK_PROPS} />);
    });

    const notifBtn = container.querySelector('button[aria-label="알림 센터"]') as HTMLButtonElement;
    await act(async () => {
      notifBtn.click();
      vi.advanceTimersByTime(50);
    });

    const notifDrawer = container.querySelector('#desktop-notification-drawer') as HTMLDivElement;
    expect(notifDrawer).not.toBeNull();

    const focusable = notifDrawer.querySelectorAll<HTMLElement>(
      'button:not([disabled]), [href], input:not([disabled]), [tabindex]:not([tabindex="-1"])'
    );
    // Strict WCAG 2.4.3: Dialog contains only the close button (no fake controls)
    expect(focusable.length).toBe(1);
    const closeBtn = focusable[0];
    expect(closeBtn.getAttribute('aria-label')).toBe('알림 센터 닫기');

    // 1. Focus on close button -> Tab remains trapped on close button
    closeBtn.focus();
    expect(document.activeElement).toBe(closeBtn);
    await act(async () => {
      const tabEvent = new KeyboardEvent('keydown', { key: 'Tab', bubbles: true, cancelable: true });
      window.dispatchEvent(tabEvent);
      expect(tabEvent.defaultPrevented).toBe(true);
    });
    expect(document.activeElement).toBe(closeBtn);

    // 2. Focus on close button -> Shift+Tab remains trapped on close button
    await act(async () => {
      const shiftTabEvent = new KeyboardEvent('keydown', { key: 'Tab', shiftKey: true, bubbles: true, cancelable: true });
      window.dispatchEvent(shiftTabEvent);
      expect(shiftTabEvent.defaultPrevented).toBe(true);
    });
    expect(document.activeElement).toBe(closeBtn);

    // 3. Focus escaped to document.body while drawer open -> Tab pulls focus back to close button
    document.body.focus();
    expect(document.activeElement).toBe(document.body);
    await act(async () => {
      const extTabEvent = new KeyboardEvent('keydown', { key: 'Tab', bubbles: true, cancelable: true });
      window.dispatchEvent(extTabEvent);
      expect(extTabEvent.defaultPrevented).toBe(true);
    });
    expect(document.activeElement).toBe(closeBtn);

    // 4. Focus escaped to document.body -> Shift+Tab pulls focus back to close button
    document.body.focus();
    expect(document.activeElement).toBe(document.body);
    await act(async () => {
      const extShiftTabEvent = new KeyboardEvent('keydown', { key: 'Tab', shiftKey: true, bubbles: true, cancelable: true });
      window.dispatchEvent(extShiftTabEvent);
      expect(extShiftTabEvent.defaultPrevented).toBe(true);
    });
    expect(document.activeElement).toBe(closeBtn);
  });

  it('F3: useModalA11y: initial closed state (isOpen=false) does NOT steal focus on mount', async () => {
    const handleClose = vi.fn();
    const externalTrigger = document.createElement('button');
    externalTrigger.id = 'trigger-btn';
    externalTrigger.textContent = 'Trigger';
    document.body.appendChild(externalTrigger);

    const unrelatedBtn = document.createElement('button');
    unrelatedBtn.id = 'unrelated-btn';
    unrelatedBtn.textContent = 'Unrelated Focus Target';
    document.body.appendChild(unrelatedBtn);

    unrelatedBtn.focus();
    expect(document.activeElement).toBe(unrelatedBtn);

    const triggerRefHolder = { current: externalTrigger };

    const ModalComponent: React.FC<{ isOpen: boolean }> = ({ isOpen }) => {
      const { containerRef, handleKeyDown } = useModalA11y({
        isOpen,
        onClose: handleClose,
        triggerRef: triggerRefHolder,
      });
      if (!isOpen) return null;
      return (
        <div ref={containerRef} role="dialog" aria-modal="true" onKeyDown={handleKeyDown}>
          <button id="modal-content-btn">Inside</button>
        </div>
      );
    };

    // Mount with isOpen = false
    await act(async () => {
      root.render(<ModalComponent isOpen={false} />);
      vi.advanceTimersByTime(50);
    });

    // CRITICAL: Focus MUST NOT be stolen by externalTrigger on initial mount!
    expect(document.activeElement).toBe(unrelatedBtn);

    // Open modal
    await act(async () => {
      root.render(<ModalComponent isOpen={true} />);
      vi.advanceTimersByTime(50);
    });
    const insideBtn = container.querySelector('#modal-content-btn');
    expect(document.activeElement).toBe(insideBtn);

    // Close modal -> now focus SHOULD restore to trigger
    await act(async () => {
      root.render(<ModalComponent isOpen={false} />);
      vi.advanceTimersByTime(50);
    });
    expect(document.activeElement).toBe(externalTrigger);

    externalTrigger.remove();
    unrelatedBtn.remove();
  });

  it('F2: Start -> Notification transition: closes Start, opens Notification, transfers focus trap, and Escape returns to Notification trigger', async () => {
    await act(async () => {
      root.render(<DesktopShell {...MOCK_PROPS} />);
    });

    const startBtn = container.querySelector('button[aria-label="SaintVision 시작 메뉴"]') as HTMLButtonElement;
    const notifBtn = container.querySelector('button[aria-label="알림 센터"]') as HTMLButtonElement;

    // 1. Open Start Menu
    await act(async () => {
      startBtn.click();
      vi.advanceTimersByTime(50);
    });
    expect(container.querySelector('#desktop-start-menu-dropdown')).not.toBeNull();
    expect(container.querySelector('#desktop-notification-drawer')).toBeNull();

    // 2. Click Notification button while Start Menu is open
    await act(async () => {
      notifBtn.click();
      vi.advanceTimersByTime(50);
    });

    // 3. Verify Start Menu is closed and Notification Center is open (mutual exclusion)
    expect(container.querySelector('#desktop-start-menu-dropdown')).toBeNull();
    expect(container.querySelector('#desktop-notification-drawer')).not.toBeNull();
    expect(startBtn.getAttribute('aria-expanded')).toBe('false');
    expect(notifBtn.getAttribute('aria-expanded')).toBe('true');

    // 4. Verify Start Menu focus trap does NOT intercept Tab key in Notification Center
    const notifDrawer = container.querySelector('#desktop-notification-drawer') as HTMLDivElement;
    const focusable = notifDrawer.querySelectorAll<HTMLElement>(
      'button:not([disabled]), [href], input:not([disabled]), [tabindex]:not([tabindex="-1"])'
    );
    expect(focusable.length).toBe(1);
    const closeNotifBtn = focusable[0];
    expect(closeNotifBtn.getAttribute('aria-label')).toBe('알림 센터 닫기');

    // R10 & R13: Drawer opening automatically focuses its close button without manual .focus()
    expect(document.activeElement).toBe(closeNotifBtn);

    // Notification trap Tab keeps focus on close button
    await act(async () => {
      const tabEvent = new KeyboardEvent('keydown', { key: 'Tab', bubbles: true, cancelable: true });
      window.dispatchEvent(tabEvent);
      expect(tabEvent.defaultPrevented).toBe(true);
    });
    expect(document.activeElement).toBe(closeNotifBtn);

    // Notification trap Shift+Tab keeps focus on close button
    await act(async () => {
      const shiftTabEvent = new KeyboardEvent('keydown', { key: 'Tab', shiftKey: true, bubbles: true, cancelable: true });
      window.dispatchEvent(shiftTabEvent);
      expect(shiftTabEvent.defaultPrevented).toBe(true);
    });
    expect(document.activeElement).toBe(closeNotifBtn);

    // 5. Press Escape: drawer closes, and focus returns specifically to Notification trigger (not Start trigger!)
    await act(async () => {
      const escEvent = new KeyboardEvent('keydown', { key: 'Escape', bubbles: true, cancelable: true });
      window.dispatchEvent(escEvent);
      vi.advanceTimersByTime(50);
    });
    expect(container.querySelector('#desktop-notification-drawer')).toBeNull();
    expect(document.activeElement).toBe(notifBtn);
  });

  it('F2: Notification -> Start transition: closes Notification, opens Start, transfers focus trap, and Escape returns to Start trigger', async () => {
    await act(async () => {
      root.render(<DesktopShell {...MOCK_PROPS} />);
    });

    const startBtn = container.querySelector('button[aria-label="SaintVision 시작 메뉴"]') as HTMLButtonElement;
    const notifBtn = container.querySelector('button[aria-label="알림 센터"]') as HTMLButtonElement;

    // 1. Open Notification Center
    await act(async () => {
      notifBtn.click();
      vi.advanceTimersByTime(50);
    });
    expect(container.querySelector('#desktop-notification-drawer')).not.toBeNull();
    expect(container.querySelector('#desktop-start-menu-dropdown')).toBeNull();

    // 2. Click Start Menu button while Notification Center is open
    await act(async () => {
      startBtn.click();
      vi.advanceTimersByTime(50);
    });

    // 3. Verify Notification Center is closed and Start Menu is open (mutual exclusion)
    expect(container.querySelector('#desktop-notification-drawer')).toBeNull();
    expect(container.querySelector('#desktop-start-menu-dropdown')).not.toBeNull();
    expect(notifBtn.getAttribute('aria-expanded')).toBe('false');
    expect(startBtn.getAttribute('aria-expanded')).toBe('true');

    // 4. Verify Start Menu trap is active
    const startMenu = container.querySelector('#desktop-start-menu-dropdown') as HTMLDivElement;
    const focusable = startMenu.querySelectorAll<HTMLElement>(
      'button:not([disabled]), [href], input:not([disabled]), [tabindex]:not([tabindex="-1"])'
    );
    const firstStartBtn = focusable[0];
    const lastStartBtn = focusable[focusable.length - 1];

    // R9 & R13: Start menu opening automatically focuses first interactive item without manual .focus()
    expect(document.activeElement).toBe(firstStartBtn);

    // Start trap forward wrap: last -> first
    lastStartBtn.focus();
    await act(async () => {
      const tabEvent = new KeyboardEvent('keydown', { key: 'Tab', bubbles: true, cancelable: true });
      window.dispatchEvent(tabEvent);
    });
    expect(document.activeElement).toBe(firstStartBtn);

    // Start trap backward wrap: first -> last
    firstStartBtn.focus();
    await act(async () => {
      const shiftTabEvent = new KeyboardEvent('keydown', { key: 'Tab', shiftKey: true, bubbles: true, cancelable: true });
      window.dispatchEvent(shiftTabEvent);
    });
    expect(document.activeElement).toBe(lastStartBtn);

    // 5. Press Escape: Start menu closes, and focus returns specifically to Start trigger (not Notification trigger!)
    await act(async () => {
      const escEvent = new KeyboardEvent('keydown', { key: 'Escape', bubbles: true, cancelable: true });
      window.dispatchEvent(escEvent);
      vi.advanceTimersByTime(50);
    });
    expect(container.querySelector('#desktop-start-menu-dropdown')).toBeNull();
    expect(document.activeElement).toBe(startBtn);
  });

  it('D1 & F1: Start Menu is a dialog (role="dialog", aria-label="시작 메뉴") with 0 menu/menuitem roles and supporting arrow key navigation', async () => {
    await act(async () => {
      root.render(<DesktopShell {...MOCK_PROPS} />);
    });

    const startBtn = container.querySelector('button[aria-label="SaintVision 시작 메뉴"]') as HTMLButtonElement;
    await act(async () => {
      startBtn.click();
      vi.advanceTimersByTime(50);
    });

    const startMenu = container.querySelector('#desktop-start-menu-dropdown') as HTMLDivElement;
    expect(startMenu).not.toBeNull();
    expect(startMenu.getAttribute('role')).toBe('dialog');
    expect(startMenu.getAttribute('aria-label')).toBe('시작 메뉴');
    expect(startMenu.getAttribute('aria-modal')).toBe('true');

    // Strict assertion: 0 menu and 0 menuitem roles across Start Menu and entire container
    expect(startMenu.querySelectorAll('[role="menu"]').length).toBe(0);
    expect(startMenu.querySelectorAll('[role="menuitem"]').length).toBe(0);
    expect(container.querySelectorAll('[role="menu"]').length).toBe(0);
    expect(container.querySelectorAll('[role="menuitem"]').length).toBe(0);

    // 9 plain native buttons with role === null
    const allButtons = Array.from(startMenu.querySelectorAll<HTMLButtonElement>('button'));
    expect(allButtons.length).toBe(9);
    for (const btn of allButtons) {
      expect(btn.getAttribute('role')).toBeNull();
    }

    // Initial focus on first button
    allButtons[0].focus();
    expect(document.activeElement).toBe(allButtons[0]);

    // Arrow navigation across buttons as auxiliary navigation
    // ArrowDown moves to next item
    await act(async () => {
      const downEvent = new KeyboardEvent('keydown', { key: 'ArrowDown', bubbles: true, cancelable: true });
      window.dispatchEvent(downEvent);
      expect(downEvent.defaultPrevented).toBe(true);
    });
    expect(document.activeElement).toBe(allButtons[1]);

    // ArrowUp moves to previous item
    await act(async () => {
      const upEvent = new KeyboardEvent('keydown', { key: 'ArrowUp', bubbles: true, cancelable: true });
      window.dispatchEvent(upEvent);
      expect(upEvent.defaultPrevented).toBe(true);
    });
    expect(document.activeElement).toBe(allButtons[0]);

    // ArrowUp on first item wraps to last item
    await act(async () => {
      const wrapUpEvent = new KeyboardEvent('keydown', { key: 'ArrowUp', bubbles: true, cancelable: true });
      window.dispatchEvent(wrapUpEvent);
      expect(wrapUpEvent.defaultPrevented).toBe(true);
    });
    expect(document.activeElement).toBe(allButtons[allButtons.length - 1]);

    // ArrowDown on last item wraps to first item
    await act(async () => {
      const wrapDownEvent = new KeyboardEvent('keydown', { key: 'ArrowDown', bubbles: true, cancelable: true });
      window.dispatchEvent(wrapDownEvent);
      expect(wrapDownEvent.defaultPrevented).toBe(true);
    });
    expect(document.activeElement).toBe(allButtons[0]);

    // Home key jumps to first item
    allButtons[4].focus();
    await act(async () => {
      const homeEvent = new KeyboardEvent('keydown', { key: 'Home', bubbles: true, cancelable: true });
      window.dispatchEvent(homeEvent);
      expect(homeEvent.defaultPrevented).toBe(true);
    });
    expect(document.activeElement).toBe(allButtons[0]);

    // End key jumps to last item
    await act(async () => {
      const endEvent = new KeyboardEvent('keydown', { key: 'End', bubbles: true, cancelable: true });
      window.dispatchEvent(endEvent);
      expect(endEvent.defaultPrevented).toBe(true);
    });
    expect(document.activeElement).toBe(allButtons[allButtons.length - 1]);
  });

  it('D2: Launching app from Start Menu (openApp) moves focus to newly opened window/title, NOT Start Menu trigger', async () => {
    await act(async () => {
      root.render(<DesktopShell {...MOCK_PROPS} />);
    });

    const startBtn = container.querySelector('button[aria-label="SaintVision 시작 메뉴"]') as HTMLButtonElement;

    // 1. Open Start Menu
    await act(async () => {
      startBtn.click();
      vi.advanceTimersByTime(50);
    });
    expect(container.querySelector('#desktop-start-menu-dropdown')).not.toBeNull();

    // 2. Click an app shortcut inside Start Menu (e.g. inv:// 파일)
    const fileExplorerBtn = Array.from(container.querySelectorAll<HTMLButtonElement>('#desktop-start-menu-dropdown button')).find(
      (b) => b.textContent?.includes('inv:// 파일')
    );
    expect(fileExplorerBtn).toBeDefined();

    await act(async () => {
      fileExplorerBtn?.click();
      vi.advanceTimersByTime(50);
    });

    // 3. Start Menu is dismissed
    expect(container.querySelector('#desktop-start-menu-dropdown')).toBeNull();

    // 4. Focus MUST NOT be pulled back to Start Menu trigger button!
    expect(document.activeElement).not.toBe(startBtn);

    // 5. Focus is placed on the newly opened window or its title
    const expectedTitleEl = container.querySelector('#window-title-win_file_explorer');
    expect(expectedTitleEl).not.toBeNull();
    // W1: Assert tabindex="-1" on window title element so plain-div without tabindex is rejected
    expect(expectedTitleEl?.getAttribute('tabindex')).toBe('-1');
    expect(document.activeElement).toBe(expectedTitleEl);
  });

  it('T4: Meta/Win key closes Start Menu and restores focus to Start trigger button', async () => {
    await act(async () => {
      root.render(<DesktopShell {...MOCK_PROPS} />);
    });

    const startBtn = container.querySelector('button[aria-label="SaintVision 시작 메뉴"]') as HTMLButtonElement;

    // Open Start Menu
    await act(async () => {
      startBtn.click();
      vi.advanceTimersByTime(50);
    });
    expect(container.querySelector('#desktop-start-menu-dropdown')).not.toBeNull();

    // Press Meta key to close Start Menu
    await act(async () => {
      const metaEvent = new KeyboardEvent('keydown', { key: 'Meta', bubbles: true, cancelable: true });
      window.dispatchEvent(metaEvent);
      vi.advanceTimersByTime(50);
    });

    expect(container.querySelector('#desktop-start-menu-dropdown')).toBeNull();
    expect(document.activeElement).toBe(startBtn);
  });

  it('T5: Outside click on desktop surface closes Start Menu and restores focus to Start trigger button', async () => {
    await act(async () => {
      root.render(<DesktopShell {...MOCK_PROPS} />);
    });

    const startBtn = container.querySelector('button[aria-label="SaintVision 시작 메뉴"]') as HTMLButtonElement;
    const desktopMain = container.querySelector('main') as HTMLElement;

    // Open Start Menu
    await act(async () => {
      startBtn.click();
      vi.advanceTimersByTime(50);
    });
    expect(container.querySelector('#desktop-start-menu-dropdown')).not.toBeNull();

    // Click outside on desktop canvas
    await act(async () => {
      desktopMain.click();
      vi.advanceTimersByTime(50);
    });

    expect(container.querySelector('#desktop-start-menu-dropdown')).toBeNull();
    expect(document.activeElement).toBe(startBtn);
  });

  it('T6: useModalA11y restores focus to trigger element on unmount when open', async () => {
    const externalTrigger = document.createElement('button');
    externalTrigger.id = 't6-external-trigger';
    document.body.appendChild(externalTrigger);
    externalTrigger.focus();
    expect(document.activeElement).toBe(externalTrigger);

    const triggerRefHolder = { current: externalTrigger };

    const UnmountTestModal: React.FC<{ mounted: boolean }> = ({ mounted }) => {
      const { containerRef, handleKeyDown } = useModalA11y({
        isOpen: true,
        onClose: vi.fn(),
        triggerRef: triggerRefHolder,
      });
      if (!mounted) return null;
      return (
        <div ref={containerRef} role="dialog" aria-modal="true" onKeyDown={handleKeyDown}>
          <button id="t6-modal-btn">Modal Button</button>
        </div>
      );
    };

    // Mount open modal
    await act(async () => {
      root.render(<UnmountTestModal mounted={true} />);
      vi.advanceTimersByTime(50);
    });

    const modalBtn = container.querySelector('#t6-modal-btn');
    expect(document.activeElement).toBe(modalBtn);

    // Unmount component while open
    await act(async () => {
      root.render(<div>Unmounted</div>);
      vi.advanceTimersByTime(50);
    });

    // Cleanup hook effect restores focus to externalTrigger
    expect(document.activeElement).toBe(externalTrigger);

    externalTrigger.remove();
  });
});
