import { restoreDesktopLayout } from './desktopLayout';
import React, { useState, useEffect, useCallback, useRef } from 'react';
import {
  AppId,
  DesktopWindow as IDesktopWindow,
  DesktopNotification,
} from '@/contracts/virtualFabric';

export type NotificationLevelKey = DesktopNotification['level'];

export interface NotificationLevelStyle {
  color: string;
  bg: string;
  border: string;
  label: string;
}

export const NOTIFICATION_LEVEL_CONFIG = {
  info: {
    color: 'var(--color-brand-hover)',
    bg: 'var(--color-bg-subtle)',
    border: 'var(--color-brand-hover)',
    label: 'INFO',
  },
  success: {
    color: 'var(--color-status-online)',
    bg: 'var(--color-bg-subtle)',
    border: 'var(--color-status-online)',
    label: 'SUCCESS',
  },
  warning: {
    color: 'var(--color-status-degraded)',
    bg: 'var(--color-bg-subtle)',
    border: 'var(--color-status-degraded)',
    label: 'WARNING',
  },
  error: {
    color: 'var(--color-status-offline)',
    bg: 'var(--color-bg-subtle)',
    border: 'var(--color-status-offline)',
    label: 'ERROR',
  },
} as const satisfies Record<NotificationLevelKey, NotificationLevelStyle>;

export function getNotificationLevelConfig(level?: string | null): NotificationLevelStyle {
  if (level && Object.hasOwn(NOTIFICATION_LEVEL_CONFIG, level)) {
    return NOTIFICATION_LEVEL_CONFIG[level as NotificationLevelKey];
  }
  return {
    color: 'var(--color-status-unknown)',
    bg: 'var(--color-bg-subtle)',
    border: 'var(--color-status-unknown)',
    label: level ? `UNKNOWN (${level})` : 'UNKNOWN',
  };
}
import { NodeItem, RunItem, ApprovalItem, WorkspaceItem } from '@/contracts/types';
import { DesktopWindowComponent } from './DesktopWindow';
import { ResourceExplorer } from './ResourceExplorer';
import { InvFileExplorer } from './InvFileExplorer';
import { ModelStudioView } from './ModelStudioView';
import { ClusterOverview } from '@/features/dashboard/ClusterOverview';
import { ApprovalCenter } from '@/features/approvals/ApprovalCenter';
import { TerminalSessionView } from './TerminalSessionView';
import { AdminSecurityConsole } from '@/features/admin/AdminSecurityConsole';

export interface DesktopShellProps {
  projectId: string;
  tenantId?: string;
  checkoutId?: string;
  nodes: NodeItem[];
  runs: RunItem[];
  approvals: ApprovalItem[];
  workspaces: WorkspaceItem[];
  currentReviewerId: string;
  onRefreshNodes: () => Promise<void>;
  onApprove: (id: string, nonce: string) => Promise<void>;
  onReject: (id: string, reason: string) => Promise<void>;
  onChangeUser: (id: string) => void;
  onSwitchToPortalView: () => void;
  currentTheme: 'light' | 'dark';
  onToggleTheme: () => void;
  notifications?: DesktopNotification[];
}

const DEFAULT_WINDOWS: IDesktopWindow[] = [
  {
    id: 'win_my_computer',
    appId: 'my-computer',
    title: '내 컴퓨터 (Resource Explorer)',
    icon: '💻',
    isOpen: true,
    isMinimized: false,
    isMaximized: false,
    zIndex: 10,
    position: { x: 40, y: 50 },
    size: { width: 920, height: 600 },
  },
  {
    id: 'win_file_explorer',
    appId: 'file-explorer',
    title: 'inv:// 파일 탐색기',
    icon: '📁',
    isOpen: false,
    isMinimized: false,
    isMaximized: false,
    zIndex: 9,
    position: { x: 80, y: 70 },
    size: { width: 960, height: 580 },
  },
  {
    id: 'win_model_studio',
    appId: 'model-studio',
    title: 'AI Model Studio',
    icon: '🧠',
    isOpen: false,
    isMinimized: false,
    isMaximized: false,
    zIndex: 8,
    position: { x: 120, y: 90 },
    size: { width: 1000, height: 640 },
  },
  {
    id: 'win_terminal',
    appId: 'terminal',
    title: '웹 터미널 (Bash/PowerShell)',
    icon: '⌨️',
    isOpen: false,
    isMinimized: false,
    isMaximized: false,
    zIndex: 7,
    position: { x: 160, y: 110 },
    size: { width: 880, height: 520 },
  },
  {
    id: 'win_developer_studio',
    appId: 'developer-studio',
    title: '개발 Studio (IDE & Runs)',
    icon: '🚀',
    isOpen: false,
    isMinimized: false,
    isMaximized: false,
    zIndex: 6,
    position: { x: 60, y: 60 },
    size: { width: 1060, height: 680 },
  },
  {
    id: 'win_approvals',
    appId: 'approvals',
    title: '거버넌스 승인 센터 (S04)',
    icon: '🛡️',
    isOpen: false,
    isMinimized: false,
    isMaximized: false,
    zIndex: 5,
    position: { x: 100, y: 80 },
    size: { width: 900, height: 580 },
  },
  {
    id: 'win_cluster_overview',
    appId: 'cluster-overview',
    title: '클러스터 개요 대시보드',
    icon: '📊',
    isOpen: false,
    isMinimized: false,
    isMaximized: false,
    zIndex: 4,
    position: { x: 140, y: 100 },
    size: { width: 920, height: 580 },
  },
  {
    id: 'win_settings',
    appId: 'settings',
    title: '보안 및 감사 콘솔',
    icon: '⚙️',
    isOpen: false,
    isMinimized: false,
    isMaximized: false,
    zIndex: 3,
    position: { x: 180, y: 120 },
    size: { width: 860, height: 540 },
  },
];

export const DESKTOP_SHORTCUTS = [
  { appId: 'my-computer' as AppId, title: '내 컴퓨터', icon: '💻' },
  { appId: 'file-explorer' as AppId, title: 'inv:// 파일', icon: '📁' },
  { appId: 'model-studio' as AppId, title: 'Model Studio', icon: '🧠' },
  { appId: 'terminal' as AppId, title: '웹 터미널', icon: '⌨️' },
  { appId: 'developer-studio' as AppId, title: '개발 Studio', icon: '🚀' },
  { appId: 'approvals' as AppId, title: '승인 센터', icon: '🛡️' },
  { appId: 'cluster-overview' as AppId, title: '클러스터', icon: '📊' },
  { appId: 'settings' as AppId, title: '보안 설정', icon: '⚙️' },
];

export const DesktopShell: React.FC<DesktopShellProps> = ({
  projectId,
  tenantId,
  checkoutId,
  currentReviewerId,
  nodes = [],
  runs = [],
  approvals = [],
  workspaces = [],
  onRefreshNodes,
  onApprove,
  onReject,
  onSwitchToPortalView,
  currentTheme,
  onToggleTheme,
  notifications: initialNotifications,
}) => {
  const [windows, setWindows] = useState<IDesktopWindow[]>(() => {
    try {
      const saved = localStorage.getItem('saintvision_desktop_windows');
      return restoreDesktopLayout(saved, DEFAULT_WINDOWS,
        typeof window === 'undefined' ? 1280 : window.innerWidth,
        typeof window === 'undefined' ? 800 : window.innerHeight);
    } catch {
      // Fallback
    }
    return DEFAULT_WINDOWS;
  });

  const [activeWindowId, setActiveWindowId] = useState<string | null>('win_my_computer');
  const [currentTime, setCurrentTime] = useState<string>('');
  const [notifications] = useState<DesktopNotification[]>(initialNotifications || []);

  // Overlays mutual exclusion: only one of 'none', 'start', 'notifications' can be active at a time (F2)
  type ActiveOverlay = 'none' | 'start' | 'notifications';
  const [activeOverlay, setActiveOverlay] = useState<ActiveOverlay>('none');
  const isStartMenuOpen = activeOverlay === 'start';
  const isNotifOpen = activeOverlay === 'notifications';



  // A11y trigger & container refs for focus trapping and trigger focus return (DEF-S11-03, DEF-S11-04, ACC-03, ACC-04)
  const startMenuTriggerRef = useRef<HTMLButtonElement>(null);
  const startMenuContainerRef = useRef<HTMLDivElement>(null);
  const notifTriggerRef = useRef<HTMLButtonElement>(null);
  const notifContainerRef = useRef<HTMLDivElement>(null);

  // Track reason for dismissing an overlay (DEF-S11-03, ACC-04, Claude D2)
  const dismissReasonRef = useRef<'escape' | 'dismiss' | 'open_app' | null>(null);

  // Restore focus to trigger button post-dismissal:
  // When closing an overlay to 'none', restore focus to the trigger button of the dismissed overlay
  // ONLY if dismissed via Escape, close button, or canvas click (NOT when an app was opened, Claude D2).
  // When switching directly between overlays ('start' <-> 'notifications'), do NOT restore focus to previous trigger,
  // allowing the newly active overlay's auto-focus to take effect cleanly (F2).
  const prevActiveOverlayRef = useRef<ActiveOverlay>('none');
  useEffect(() => {
    const prev = prevActiveOverlayRef.current;
    prevActiveOverlayRef.current = activeOverlay;

    if (activeOverlay === 'none') {
      const reason = dismissReasonRef.current;
      if (reason !== 'open_app') {
        dismissReasonRef.current = null;
        if (prev === 'start') {
          startMenuTriggerRef.current?.focus();
        } else if (prev === 'notifications') {
          notifTriggerRef.current?.focus();
        }
      }
    }
  }, [activeOverlay]);

  // Focus newly opened or activated window title after DOM mount (Claude D2)
  useEffect(() => {
    if (dismissReasonRef.current === 'open_app' && activeWindowId) {
      dismissReasonRef.current = null;
      const titleEl = document.getElementById(`window-title-${activeWindowId}`);
      if (titleEl) {
        titleEl.focus();
      } else {
        const winDialog = document.querySelector<HTMLElement>(`[aria-labelledby="window-title-${activeWindowId}"]`);
        winDialog?.focus();
      }
    }
  }, [activeWindowId, windows]);

  // Auto-focus first interactive element when Start Menu or Notification drawer opens
  useEffect(() => {
    if (activeOverlay === 'start') {
      const firstBtn = startMenuContainerRef.current?.querySelector<HTMLElement>(
        'button:not([disabled]), [href], input:not([disabled]), [tabindex]:not([tabindex="-1"])'
      );
      firstBtn?.focus();
    }
  }, [activeOverlay]);

  useEffect(() => {
    if (activeOverlay === 'notifications') {
      const firstBtn = notifContainerRef.current?.querySelector<HTMLElement>(
        'button:not([disabled]), [href], input:not([disabled]), [tabindex]:not([tabindex="-1"])'
      );
      firstBtn?.focus();
    }
  }, [activeOverlay]);

  // Clock timer
  useEffect(() => {
    const updateTime = () => {
      const now = new Date();
      setCurrentTime(
        now.toLocaleTimeString('ko-KR', { hour12: false, hour: '2-digit', minute: '2-digit', second: '2-digit' })
      );
    };
    updateTime();
    const interval = setInterval(updateTime, 1000);
    return () => clearInterval(interval);
  }, []);

  // Save window layout to localStorage
  useEffect(() => {
    try {
      localStorage.setItem('saintvision_desktop_windows', JSON.stringify(windows));
    } catch {
      // Ignore
    }
  }, [windows]);

  // Bring window to front
  const focusWindow = useCallback((windowId: string) => {
    setActiveWindowId(windowId);
    setWindows((prev) => {
      const maxZ = Math.max(...prev.map((w) => w.zIndex), 10);
      return prev.map((w) => (w.id === windowId ? { ...w, zIndex: maxZ + 1, isMinimized: false } : w));
    });
  }, []);

  // Global Keyboard Shortcuts (Alt+Tab window cycling, Escape to close overlays with focus return, Win/Meta to toggle Start menu)
  useEffect(() => {
    const handleKeyDown = (e: KeyboardEvent) => {
      // Escape: Close Start Menu or Notifications first (overlays) and restore focus to trigger button
      if (e.key === 'Escape') {
        if (activeOverlay === 'start') {
          e.preventDefault();
          e.stopPropagation();
          dismissReasonRef.current = 'escape';
          setActiveOverlay('none');
          startMenuTriggerRef.current?.focus();
          return;
        }
        if (activeOverlay === 'notifications') {
          e.preventDefault();
          e.stopPropagation();
          dismissReasonRef.current = 'escape';
          setActiveOverlay('none');
          notifTriggerRef.current?.focus();
          return;
        }
      }

      // Arrow navigation for Start Menu (보조 기능: ArrowDown, ArrowUp, Home, End - WAI-ARIA dialog 보조)
      if (activeOverlay === 'start') {
        if (e.key === 'ArrowDown' || e.key === 'ArrowUp' || e.key === 'Home' || e.key === 'End') {
          const container = startMenuContainerRef.current;
          if (container) {
            const menuButtons = Array.from(container.querySelectorAll<HTMLButtonElement>('button:not([disabled])'));
            if (menuButtons.length > 0) {
              e.preventDefault();
              const currentIndex = menuButtons.indexOf(document.activeElement as HTMLButtonElement);
              if (e.key === 'Home') {
                menuButtons[0].focus();
              } else if (e.key === 'End') {
                menuButtons[menuButtons.length - 1].focus();
              } else if (e.key === 'ArrowDown') {
                const nextIndex = currentIndex === -1 || currentIndex === menuButtons.length - 1 ? 0 : currentIndex + 1;
                menuButtons[nextIndex].focus();
              } else if (e.key === 'ArrowUp') {
                const prevIndex = currentIndex <= 0 ? menuButtons.length - 1 : currentIndex - 1;
                menuButtons[prevIndex].focus();
              }
            }
          }
          return;
        }
      }

      // Tab trapping for Start Menu (WCAG 2.4.3 Focus Trap)
      if (activeOverlay === 'start' && e.key === 'Tab') {
        const container = startMenuContainerRef.current;
        if (container) {
          const focusable = container.querySelectorAll<HTMLElement>(
            'button:not([disabled]), [href], input:not([disabled]), [tabindex]:not([tabindex="-1"])'
          );
          if (focusable.length > 0) {
            const first = focusable[0];
            const last = focusable[focusable.length - 1];
            if (e.shiftKey) {
              if (document.activeElement === first || !container.contains(document.activeElement)) {
                e.preventDefault();
                last.focus();
              }
            } else {
              if (document.activeElement === last || !container.contains(document.activeElement)) {
                e.preventDefault();
                first.focus();
              }
            }
          }
        }
        return;
      }

      // Tab trapping for Notification Center Drawer (WCAG 2.4.3 Focus Trap)
      if (activeOverlay === 'notifications' && e.key === 'Tab') {
        const container = notifContainerRef.current;
        if (container) {
          const focusable = container.querySelectorAll<HTMLElement>(
            'button:not([disabled]), [href], input:not([disabled]), [tabindex]:not([tabindex="-1"])'
          );
          if (focusable.length > 0) {
            const first = focusable[0];
            const last = focusable[focusable.length - 1];
            if (e.shiftKey) {
              if (document.activeElement === first || !container.contains(document.activeElement)) {
                e.preventDefault();
                last.focus();
              }
            } else {
              if (document.activeElement === last || !container.contains(document.activeElement)) {
                e.preventDefault();
                first.focus();
              }
            }
          }
        }
        return;
      }

      // Alt + Tab: Cycle through open windows
      if (e.altKey && (e.key === 'Tab' || e.code === 'Tab')) {
        e.preventDefault();
        const openWindows = windows.filter((w) => w.isOpen && !w.isMinimized);
        if (openWindows.length > 1) {
          const currentIndex = openWindows.findIndex((w) => w.id === activeWindowId);
          const nextIndex = (currentIndex + 1) % openWindows.length;
          focusWindow(openWindows[nextIndex].id);
        }
      }
      // Meta / Win Key: Toggle Start Menu
      if (e.key === 'Meta') {
        if (activeOverlay === 'start') {
          dismissReasonRef.current = 'dismiss';
          setActiveOverlay('none');
          startMenuTriggerRef.current?.focus();
        } else {
          setActiveOverlay('start');
        }
      }
    };

    window.addEventListener('keydown', handleKeyDown);
    return () => window.removeEventListener('keydown', handleKeyDown);
  }, [activeOverlay, windows, activeWindowId, focusWindow]);

  const openApp = useCallback(
    (appId: AppId) => {
      setWindows((prev) => {
        const existing = prev.find((w) => w.appId === appId);
        if (existing) {
          const maxZ = Math.max(...prev.map((w) => w.zIndex), 10);
          return prev.map((w) =>
            w.id === existing.id
              ? { ...w, isOpen: true, isMinimized: false, zIndex: maxZ + 1 }
              : w
          );
        }
        return prev;
      });
      const win = windows.find((w) => w.appId === appId);
      if (win) {
        setActiveWindowId(win.id);
      }
      dismissReasonRef.current = 'open_app';
      setActiveOverlay('none');
    },
    [windows]
  );

  const closeWindow = (windowId: string) => {
    setWindows((prev) =>
      prev.map((w) => (w.id === windowId ? { ...w, isOpen: false } : w))
    );
    if (activeWindowId === windowId) {
      setActiveWindowId(null);
    }
  };

  const minimizeWindow = (windowId: string) => {
    setWindows((prev) =>
      prev.map((w) => (w.id === windowId ? { ...w, isMinimized: true } : w))
    );
    if (activeWindowId === windowId) {
      setActiveWindowId(null);
    }
  };

  const toggleMaximizeWindow = (windowId: string) => {
    setWindows((prev) =>
      prev.map((w) => (w.id === windowId ? { ...w, isMaximized: !w.isMaximized } : w))
    );
  };

  const activeWindow = windows.find((w) => w.id === activeWindowId && w.isOpen && !w.isMinimized);

  return (
    <div
      role="application"
      aria-label="SaintVision Web Desktop Virtual Computer"
      data-testid="desktop-shell-container"
      style={{
        position: 'fixed',
        top: 0,
        left: 0,
        right: 0,
        bottom: 0,
        width: '100vw',
        height: '100vh',
        overflow: 'hidden',
        backgroundColor: 'var(--color-bg-canvas)',
        backgroundImage: `radial-gradient(circle at 50% 30%, var(--color-brand-subtle) 0%, var(--color-bg-surface) 50%, var(--color-bg-canvas) 100%)`,
        userSelect: 'none',
        display: 'flex',
        flexDirection: 'column',
      }}
    >
      {/* 1. Top System Menu Bar */}
      <header
        style={{
          height: '36px',
          backgroundColor: 'var(--color-bg-surface)',
          backdropFilter: 'blur(16px)',
          borderBottom: '1px solid var(--color-border-subtle)',
          display: 'flex',
          alignItems: 'center',
          justifyContent: 'space-between',
          padding: '0 16px',
          zIndex: 9999,
          color: 'var(--color-text-primary)',
          fontSize: '0.8125rem',
        }}
      >
        {/* Left: Brand / Apple Logo / Start Menu / Active Window Title */}
        <div style={{ display: 'flex', alignItems: 'center', gap: '16px' }}>
          <button
            ref={startMenuTriggerRef}
            type="button"
            id="desktop-start-menu-trigger"
            onClick={() => setActiveOverlay((prev) => (prev === 'start' ? 'none' : 'start'))}
            aria-expanded={isStartMenuOpen}
            aria-haspopup="dialog"
            aria-controls="desktop-start-menu-dropdown"
            aria-label="SaintVision 시작 메뉴"
            style={{
              display: 'flex',
              alignItems: 'center',
              gap: '6px',
              fontWeight: 700,
              fontSize: '0.875rem',
              color: 'var(--color-brand-hover)',
              background: 'none',
              border: 'none',
              cursor: 'pointer',
              padding: '2px 6px',
              borderRadius: '4px',
            }}
          >
            <span>🌐</span>
            <span>SaintVision / INV</span>
          </button>

          {activeWindow && (
            <div style={{ display: 'flex', alignItems: 'center', gap: '6px', color: 'var(--color-text-muted)' }}>
              <span>|</span>
              <span style={{ fontWeight: 600, color: 'var(--color-text-primary)' }}>{activeWindow.title}</span>
            </div>
          )}
        </div>

        {/* Right: Fabric Status / View Toggle / Notifications / Clock */}
        <div style={{ display: 'flex', alignItems: 'center', gap: '14px' }}>
          <span
            style={{
              fontSize: '0.6875rem',
              fontWeight: 600,
              color: 'var(--color-status-online)',
              display: 'flex',
              alignItems: 'center',
              gap: '4px',
            }}
          >
            ● 5 Nodes (4 Schedulable)
          </span>

          <span style={{ fontSize: '0.6875rem', color: 'var(--color-text-muted)' }}>RTT: 8ms</span>

          {/* Switch to Classic Portal Button */}
          <button
            type="button"
            data-testid="desktop-mode-switcher"
            onClick={onSwitchToPortalView}
            style={{
              padding: '3px 8px',
              fontSize: '0.6875rem',
              fontWeight: 600,
              borderRadius: '4px',
              backgroundColor: 'var(--color-brand-subtle)',
              border: '1px solid var(--color-brand-hover)',
              color: 'var(--color-brand-hover)',
              cursor: 'pointer',
            }}
          >
            📑 클래식 포털 뷰로 전환
          </button>

          {/* Theme Toggle */}
          <button
            type="button"
            onClick={onToggleTheme}
            style={{
              background: 'none',
              border: 'none',
              cursor: 'pointer',
              fontSize: '0.875rem',
              padding: '2px',
              color: 'var(--color-text-secondary)',
            }}
            title="테마 전환"
          >
            {currentTheme === 'dark' ? '🌙' : '☀️'}
          </button>

          {/* Notifications */}
          <button
            ref={notifTriggerRef}
            type="button"
            id="desktop-notification-trigger"
            onClick={() => setActiveOverlay((prev) => (prev === 'notifications' ? 'none' : 'notifications'))}
            aria-expanded={isNotifOpen}
            aria-haspopup="dialog"
            aria-controls="desktop-notification-drawer"
            aria-label="알림 센터"
            style={{
              background: 'none',
              border: 'none',
              cursor: 'pointer',
              fontSize: '0.875rem',
              position: 'relative',
              padding: '2px',
              color: 'var(--color-text-secondary)',
            }}
            title="알림 센터"
          >
            🔔
            {notifications.some((n) => !n.read) && (
              <span
                data-testid="desktop-unread-notif-dot"
                style={{
                  position: 'absolute',
                  top: '-2px',
                  right: '-4px',
                  width: '6px',
                  height: '6px',
                  borderRadius: '50%',
                  backgroundColor: 'var(--color-status-offline)',
                }}
              />
            )}
          </button>

          {/* Clock */}
          <span style={{ fontWeight: 600, fontVariantNumeric: 'tabular-nums' }}>
            {currentTime}
          </span>
        </div>
      </header>

      {/* 2. Start Menu Dropdown */}
      {isStartMenuOpen && (
        <div
          ref={startMenuContainerRef}
          id="desktop-start-menu-dropdown"
          role="dialog"
          aria-label="시작 메뉴"
          aria-modal={true}
          tabIndex={-1}
          style={{
            position: 'absolute',
            top: '40px',
            left: '16px',
            width: '280px',
            backgroundColor: 'var(--color-bg-surface)',
            backdropFilter: 'blur(20px)',
            border: '1px solid var(--color-border-subtle)',
            borderRadius: '12px',
            boxShadow: 'var(--shadow-lg)',
            padding: '12px',
            zIndex: 10000,
            color: 'var(--color-text-primary)',
          }}
        >
          <div style={{ padding: '6px 10px', borderBottom: '1px solid var(--color-border-subtle)', marginBottom: '8px' }}>
            <div style={{ fontWeight: 700, fontSize: '0.875rem' }}>SaintVision / INV 가상 컴퓨터</div>
            <div style={{ fontSize: '0.6875rem', color: 'var(--color-text-muted)' }}>사용자: {currentReviewerId}</div>
          </div>

          <div style={{ display: 'flex', flexDirection: 'column', gap: '4px' }}>
            {DESKTOP_SHORTCUTS.map((app) => (
              <button
                key={app.appId}
                type="button"
                onClick={() => openApp(app.appId)}
                style={{
                  display: 'flex',
                  alignItems: 'center',
                  gap: '10px',
                  padding: '8px 10px',
                  borderRadius: '6px',
                  border: 'none',
                  backgroundColor: 'transparent',
                  color: 'var(--color-text-primary)',
                  fontSize: '0.8125rem',
                  fontWeight: 500,
                  cursor: 'pointer',
                  textAlign: 'left',
                }}
              >
                <span style={{ fontSize: '1.125rem' }}>{app.icon}</span>
                <span>{app.title}</span>
              </button>
            ))}
          </div>

          <div style={{ borderTop: '1px solid var(--color-border-subtle)', marginTop: '8px', paddingTop: '8px' }}>
            <button
              type="button"
              onClick={onSwitchToPortalView}
              style={{
                width: '100%',
                display: 'flex',
                alignItems: 'center',
                gap: '8px',
                padding: '6px 10px',
                borderRadius: '6px',
                border: 'none',
                backgroundColor: 'transparent',
                color: 'var(--color-brand-hover)',
                fontSize: '0.75rem',
                cursor: 'pointer',
                textAlign: 'left',
              }}
            >
              <span>📑</span>
              <span>클래식 브라우저 포털 뷰로 나가기</span>
            </button>
          </div>
        </div>
      )}

      {/* 3. Notification Center Drawer */}
      {isNotifOpen && (
        <div
          ref={notifContainerRef}
          id="desktop-notification-drawer"
          role="dialog"
          aria-modal="true"
          aria-label="알림 센터"
          aria-labelledby="desktop-notification-trigger"
          tabIndex={-1}
          style={{
            position: 'absolute',
            top: '40px',
            right: '16px',
            width: '320px',
            backgroundColor: 'var(--color-bg-surface)',
            backdropFilter: 'blur(20px)',
            border: '1px solid var(--color-border-subtle)',
            borderRadius: '12px',
            boxShadow: 'var(--shadow-lg)',
            padding: '16px',
            zIndex: 10000,
            color: 'var(--color-text-primary)',
          }}
        >
          <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: '12px' }}>
            <span style={{ fontWeight: 700, fontSize: '0.875rem' }}>알림 센터</span>
            <button
              type="button"
              onClick={() => {
                setActiveOverlay('none');
                notifTriggerRef.current?.focus();
              }}
              aria-label="알림 센터 닫기"
              style={{ background: 'none', border: 'none', color: 'var(--color-text-muted)', cursor: 'pointer' }}
            >
              ×
            </button>
          </div>
          {notifications.map((n) => {
            const notifCfg = getNotificationLevelConfig(n.level);
            return (
              <div
                key={n.id}
                data-testid="desktop-notification-item"
                style={{
                  padding: '10px',
                  borderRadius: '8px',
                  backgroundColor: 'var(--color-bg-subtle)',
                  border: '1px solid var(--color-border-subtle)',
                  marginBottom: '8px',
                  fontSize: '0.75rem',
                }}
              >
                <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', gap: '8px', marginBottom: '4px' }}>
                  <span style={{ fontWeight: 600, color: 'var(--color-text-primary)' }}>
                    {n.title}
                  </span>
                  <span
                    data-testid="desktop-notification-badge"
                    style={{
                      padding: '1px 6px',
                      borderRadius: '4px',
                      fontSize: '10px',
                      fontWeight: 700,
                      backgroundColor: notifCfg.bg,
                      color: notifCfg.color,
                      border: `1px solid ${notifCfg.border}`,
                    }}
                  >
                    {notifCfg.label}
                  </span>
                </div>
                <div style={{ color: 'var(--color-text-secondary)', marginTop: '2px' }}>{n.message}</div>
              </div>
            );
          })}
        </div>
      )}

      {/* 4. Desktop Surface Canvas with Shortcuts Grid */}
      <main
        style={{
          flex: 1,
          position: 'relative',
          overflow: 'hidden',
          padding: '24px',
        }}
        onClick={() => {
          if (activeOverlay === 'start') {
            setActiveOverlay('none');
            startMenuTriggerRef.current?.focus();
          } else if (activeOverlay === 'notifications') {
            setActiveOverlay('none');
            notifTriggerRef.current?.focus();
          }
        }}
      >
        {/* Desktop Icons */}
        <div
          style={{
            display: 'grid',
            gridAutoFlow: 'column',
            gridTemplateRows: 'repeat(auto-fill, 90px)',
            gap: '16px',
            width: 'max-content',
            zIndex: 1,
            position: 'relative',
          }}
        >
          {DESKTOP_SHORTCUTS.map((item) => (
            <div
              key={item.appId}
              role="button"
              tabIndex={0}
              onClick={() => openApp(item.appId)}
              onKeyDown={(e) => {
                if (e.key === 'Enter') openApp(item.appId);
              }}
              style={{
                width: '84px',
                height: '84px',
                display: 'flex',
                flexDirection: 'column',
                alignItems: 'center',
                justifyContent: 'center',
                borderRadius: '10px',
                cursor: 'pointer',
                padding: '6px',
                transition: 'background-color 0.15s ease',
              }}
              onMouseEnter={(e) => (e.currentTarget.style.backgroundColor = 'var(--color-bg-subtle)')}
              onMouseLeave={(e) => (e.currentTarget.style.backgroundColor = 'transparent')}
            >
              <div
                style={{
                  width: '44px',
                  height: '44px',
                  borderRadius: '12px',
                  backgroundColor: 'var(--color-bg-surface)',
                  backdropFilter: 'blur(8px)',
                  display: 'flex',
                  alignItems: 'center',
                  justifyContent: 'center',
                  fontSize: '1.5rem',
                  boxShadow: 'var(--shadow-md)',
                  border: '1px solid var(--color-border-subtle)',
                }}
              >
                {item.icon}
              </div>
              <span
                style={{
                  marginTop: '6px',
                  fontSize: '0.6875rem',
                  fontWeight: 600,
                  color: 'var(--color-text-primary)',
                  textAlign: 'center',
                  lineHeight: 1.2,
                }}
              >
                {item.title}
              </span>
            </div>
          ))}
        </div>

        {/* Windows Rendering Area */}
        {windows.map((win) => {
          return (
            <DesktopWindowComponent
              key={win.id}
              window={win}
              isActive={activeWindowId === win.id}
              isOverlayOpen={isStartMenuOpen || isNotifOpen}
              onFocus={() => focusWindow(win.id)}
              onClose={() => closeWindow(win.id)}
              onMinimize={() => minimizeWindow(win.id)}
              onToggleMaximize={() => toggleMaximizeWindow(win.id)}
            >
              {win.appId === 'my-computer' && (
                <ResourceExplorer
                  nodes={nodes}
                  tenantId={tenantId}
                  projectId={projectId}
                  runId={runs[0]?.id}
                  onOpenTerminal={() => openApp('terminal')}
                />
              )}

              {win.appId === 'file-explorer' && (
                <InvFileExplorer
                  projectId={projectId}
                  runId={runs[0]?.id}
                  checkoutId={checkoutId}
                  clusterNodes={nodes}
                />
              )}

              {win.appId === 'model-studio' && (
                <ModelStudioView projectId={projectId} clusterNodes={nodes} />
              )}

              {win.appId === 'approvals' && (
                <div style={{ padding: 16, height: '100%', overflow: 'auto' }}>
                  <ApprovalCenter
                    approvals={approvals}
                    currentUserId={currentReviewerId}
                    onApprove={onApprove}
                    onReject={onReject}
                  />
                </div>
              )}

              {win.appId === 'terminal' && (
                <div style={{ height: '100%' }}>
                  <TerminalSessionView
                    nodes={nodes}
                    defaultNodeId={nodes.find((n) => !n.observationOnly && n.schedulable !== false)?.id || nodes[0]?.id}
                    defaultWorkspaceId={workspaces[0]?.id || ''}
                    projectId={projectId}
                    commandId={runs.find((r) => r.state === 'scheduled' || r.state === 'verifying')?.id || runs[0]?.id || null}
                  />
                </div>
              )}

              {win.appId === 'settings' && (
                <div style={{ padding: 16, height: '100%', overflow: 'auto' }}>
                  <AdminSecurityConsole
                    nodes={nodes}
                    onRefreshNodes={onRefreshNodes}
                  />
                </div>
              )}

              {win.appId === 'developer-studio' && (
                <section style={{padding: 24}}><p>이 기능은 포털에서 프로젝트와 세션을 선택한 뒤 이용하세요.</p>
                  <button onClick={onSwitchToPortalView}>포털로 이동</button></section>
              )}

              {win.appId === 'cluster-overview' && (
                <ClusterOverview
                  nodes={nodes}
                  runs={runs}
                  pendingApprovalsCount={approvals.filter((a) => a.status === 'pending').length}
                  onNavigate={(tab) => {
                    if (tab === 'nodes') openApp('my-computer');
                    else if (tab === 'runs') openApp('developer-studio');
                    else if (tab === 'approvals') openApp('approvals');
                  }}
                />
              )}

            </DesktopWindowComponent>
          );
        })}
      </main>

      {/* 5. Bottom Floating Dock */}
      <footer
        style={{
          height: '68px',
          display: 'flex',
          alignItems: 'center',
          justifyContent: 'center',
          position: 'absolute',
          bottom: '8px',
          left: 0,
          right: 0,
          pointerEvents: 'none',
          zIndex: 9999,
        }}
      >
        <div
          role="toolbar"
          aria-label="Desktop Application Dock"
          data-testid="desktop-taskbar"
          style={{
            pointerEvents: 'auto',
            display: 'flex',
            alignItems: 'center',
            gap: '8px',
            padding: '6px 14px',
            backgroundColor: 'var(--color-bg-surface)',
            backdropFilter: 'blur(24px)',
            borderRadius: '20px',
            border: '1px solid var(--color-border-subtle)',
            boxShadow: 'var(--shadow-lg)',
          }}
        >
          {DESKTOP_SHORTCUTS.map((item) => {
            const win = windows.find((w) => w.appId === item.appId);
            const isOpen = win?.isOpen;
            const isActive = win && activeWindowId === win.id && !win.isMinimized;

            return (
              <button
                key={item.appId}
                type="button"
                onClick={() => {
                  if (isOpen && !win.isMinimized) {
                    if (activeWindowId === win.id) {
                      minimizeWindow(win.id);
                    } else {
                      focusWindow(win.id);
                    }
                  } else {
                    openApp(item.appId);
                  }
                }}
                title={item.title}
                aria-label={`실행 또는 활성화: ${item.title}`}
                style={{
                  display: 'flex',
                  flexDirection: 'column',
                  alignItems: 'center',
                  background: 'none',
                  border: 'none',
                  cursor: 'pointer',
                  padding: '4px',
                  borderRadius: '10px',
                  position: 'relative',
                  transition: 'transform 0.15s ease',
                }}
              >
                <div
                  data-testid={`desktop-dock-tile-${item.appId}`}
                  style={{
                    width: '44px',
                    height: '44px',
                    borderRadius: '12px',
                    backgroundColor: isActive ? 'var(--color-brand-subtle)' : 'var(--color-bg-subtle)',
                    display: 'flex',
                    alignItems: 'center',
                    justifyContent: 'center',
                    fontSize: '1.5rem',
                    boxShadow: isActive ? 'var(--shadow-md)' : 'none',
                    border: isActive ? '1.5px solid var(--color-brand-hover)' : '1px solid var(--color-border-subtle)',
                  }}
                >
                  {item.icon}
                </div>

                {/* Running dot indicator */}
                {isOpen && (
                  <div
                    data-testid={`desktop-dock-running-${item.appId}`}
                    style={{
                      width: '4px',
                      height: '4px',
                      borderRadius: '50%',
                      backgroundColor: isActive ? 'var(--color-brand-hover)' : 'var(--color-border-strong)',
                      marginTop: '3px',
                    }}
                  />
                )}
              </button>
            );
          })}
        </div>
      </footer>
    </div>
  );
};
