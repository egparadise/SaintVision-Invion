import { restoreDesktopLayout } from './desktopLayout';
import React, { useState, useEffect, useCallback } from 'react';
import {
  AppId,
  DesktopWindow as IDesktopWindow,
  DesktopNotification,
} from '@/contracts/virtualFabric';
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

const DESKTOP_SHORTCUTS = [
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
  currentReviewerId,
  nodes,
  runs,
  approvals = [],
  workspaces = [],
  onRefreshNodes,
  onApprove,
  onReject,
  onSwitchToPortalView,
  currentTheme,
  onToggleTheme,
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
  const [isStartMenuOpen, setIsStartMenuOpen] = useState(false);
  const [notifications] = useState<DesktopNotification[]>([]);
  const [isNotifOpen, setIsNotifOpen] = useState(false);

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

  // Global Keyboard Shortcuts (Alt+Tab window cycling, Escape to close modals, Win/Meta to toggle Start menu)
  useEffect(() => {
    const handleKeyDown = (e: KeyboardEvent) => {
      // Escape: Close Start Menu or Notifications
      if (e.key === 'Escape') {
        if (isStartMenuOpen) setIsStartMenuOpen(false);
        if (isNotifOpen) setIsNotifOpen(false);
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
        setIsStartMenuOpen((prev) => !prev);
      }
    };

    window.addEventListener('keydown', handleKeyDown);
    return () => window.removeEventListener('keydown', handleKeyDown);
  }, [isStartMenuOpen, isNotifOpen, windows, activeWindowId, focusWindow]);

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
      setIsStartMenuOpen(false);
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
        backgroundColor: '#090d16',
        backgroundImage: `radial-gradient(circle at 50% 30%, #1e3a8a 0%, #0f172a 50%, #030712 100%)`,
        userSelect: 'none',
        display: 'flex',
        flexDirection: 'column',
      }}
    >
      {/* 1. Top System Menu Bar */}
      <header
        style={{
          height: '36px',
          backgroundColor: 'rgba(15, 23, 42, 0.85)',
          backdropFilter: 'blur(16px)',
          borderBottom: '1px solid rgba(255, 255, 255, 0.1)',
          display: 'flex',
          alignItems: 'center',
          justifyContent: 'space-between',
          padding: '0 16px',
          zIndex: 9999,
          color: '#f8fafc',
          fontSize: '0.8125rem',
        }}
      >
        {/* Left: Brand / Apple Logo / Start Menu / Active Window Title */}
        <div style={{ display: 'flex', alignItems: 'center', gap: '16px' }}>
          <button
            type="button"
            onClick={() => setIsStartMenuOpen(!isStartMenuOpen)}
            aria-expanded={isStartMenuOpen}
            aria-label="SaintVision 시작 메뉴"
            style={{
              display: 'flex',
              alignItems: 'center',
              gap: '6px',
              fontWeight: 700,
              fontSize: '0.875rem',
              color: '#38bdf8',
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
            <div style={{ display: 'flex', alignItems: 'center', gap: '6px', color: '#94a3b8' }}>
              <span>|</span>
              <span style={{ fontWeight: 600, color: '#f8fafc' }}>{activeWindow.title}</span>
            </div>
          )}
        </div>

        {/* Right: Fabric Status / View Toggle / Notifications / Clock */}
        <div style={{ display: 'flex', alignItems: 'center', gap: '14px' }}>
          <span
            style={{
              fontSize: '0.6875rem',
              fontWeight: 600,
              color: '#34d399',
              display: 'flex',
              alignItems: 'center',
              gap: '4px',
            }}
          >
            ● 5 Nodes (4 Schedulable)
          </span>

          <span style={{ fontSize: '0.6875rem', color: '#94a3b8' }}>RTT: 8ms</span>

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
              backgroundColor: 'rgba(59, 130, 246, 0.2)',
              border: '1px solid rgba(59, 130, 246, 0.4)',
              color: '#60a5fa',
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
            }}
            title="테마 전환"
          >
            {currentTheme === 'dark' ? '🌙' : '☀️'}
          </button>

          {/* Notifications */}
          <button
            type="button"
            onClick={() => setIsNotifOpen(!isNotifOpen)}
            style={{
              background: 'none',
              border: 'none',
              cursor: 'pointer',
              fontSize: '0.875rem',
              position: 'relative',
              padding: '2px',
            }}
            title="알림 센터"
          >
            🔔
            {notifications.some((n) => !n.read) && (
              <span
                style={{
                  position: 'absolute',
                  top: '-2px',
                  right: '-4px',
                  width: '6px',
                  height: '6px',
                  borderRadius: '50%',
                  backgroundColor: '#ef4444',
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
          role="menu"
          style={{
            position: 'absolute',
            top: '40px',
            left: '16px',
            width: '280px',
            backgroundColor: 'rgba(15, 23, 42, 0.95)',
            backdropFilter: 'blur(20px)',
            border: '1px solid rgba(255, 255, 255, 0.15)',
            borderRadius: '12px',
            boxShadow: '0 16px 36px rgba(0,0,0,0.6)',
            padding: '12px',
            zIndex: 10000,
            color: '#f8fafc',
          }}
        >
          <div style={{ padding: '6px 10px', borderBottom: '1px solid rgba(255,255,255,0.1)', marginBottom: '8px' }}>
            <div style={{ fontWeight: 700, fontSize: '0.875rem' }}>SaintVision / INV 가상 컴퓨터</div>
            <div style={{ fontSize: '0.6875rem', color: '#94a3b8' }}>사용자: {currentReviewerId}</div>
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
                  color: 'inherit',
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

          <div style={{ borderTop: '1px solid rgba(255,255,255,0.1)', marginTop: '8px', paddingTop: '8px' }}>
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
                color: '#60a5fa',
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
          role="region"
          aria-label="알림 센터"
          style={{
            position: 'absolute',
            top: '40px',
            right: '16px',
            width: '320px',
            backgroundColor: 'rgba(15, 23, 42, 0.95)',
            backdropFilter: 'blur(20px)',
            border: '1px solid rgba(255, 255, 255, 0.15)',
            borderRadius: '12px',
            boxShadow: '0 16px 36px rgba(0,0,0,0.6)',
            padding: '16px',
            zIndex: 10000,
            color: '#f8fafc',
          }}
        >
          <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: '12px' }}>
            <span style={{ fontWeight: 700, fontSize: '0.875rem' }}>알림 센터</span>
            <button
              type="button"
              onClick={() => setIsNotifOpen(false)}
              style={{ background: 'none', border: 'none', color: '#94a3b8', cursor: 'pointer' }}
            >
              ×
            </button>
          </div>
          {notifications.map((n) => (
            <div
              key={n.id}
              style={{
                padding: '10px',
                borderRadius: '8px',
                backgroundColor: 'rgba(255,255,255,0.05)',
                marginBottom: '8px',
                fontSize: '0.75rem',
              }}
            >
              <div style={{ fontWeight: 600, color: n.level === 'success' ? '#34d399' : '#f8fafc' }}>
                {n.title}
              </div>
              <div style={{ color: '#94a3b8', marginTop: '2px' }}>{n.message}</div>
            </div>
          ))}
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
          setIsStartMenuOpen(false);
          setIsNotifOpen(false);
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
                transition: 'background-color 0.15s ease',
                padding: '6px',
              }}
              onMouseEnter={(e) => (e.currentTarget.style.backgroundColor = 'rgba(255,255,255,0.1)')}
              onMouseLeave={(e) => (e.currentTarget.style.backgroundColor = 'transparent')}
            >
              <div
                style={{
                  width: '44px',
                  height: '44px',
                  borderRadius: '12px',
                  backgroundColor: 'rgba(255,255,255,0.08)',
                  backdropFilter: 'blur(8px)',
                  display: 'flex',
                  alignItems: 'center',
                  justifyContent: 'center',
                  fontSize: '1.5rem',
                  boxShadow: '0 4px 12px rgba(0,0,0,0.3)',
                  border: '1px solid rgba(255,255,255,0.15)',
                }}
              >
                {item.icon}
              </div>
              <span
                style={{
                  marginTop: '6px',
                  fontSize: '0.6875rem',
                  fontWeight: 600,
                  color: '#ffffff',
                  textShadow: '0 1px 3px rgba(0,0,0,0.8)',
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
              onFocus={() => focusWindow(win.id)}
              onClose={() => closeWindow(win.id)}
              onMinimize={() => minimizeWindow(win.id)}
              onToggleMaximize={() => toggleMaximizeWindow(win.id)}
            >
              {win.appId === 'my-computer' && (
                <ResourceExplorer
                  nodes={nodes}
                  tenantId={tenantId}
                  onOpenTerminal={() => openApp('terminal')}
                />
              )}

              {win.appId === 'file-explorer' && (
                <InvFileExplorer
                  projectId={projectId}
                  runId={runs[0]?.id}
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
            backgroundColor: 'rgba(15, 23, 42, 0.75)',
            backdropFilter: 'blur(24px)',
            borderRadius: '20px',
            border: '1px solid rgba(255, 255, 255, 0.15)',
            boxShadow: '0 12px 32px rgba(0,0,0,0.5)',
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
                  style={{
                    width: '44px',
                    height: '44px',
                    borderRadius: '12px',
                    backgroundColor: isActive ? 'rgba(59, 130, 246, 0.3)' : 'rgba(255, 255, 255, 0.08)',
                    display: 'flex',
                    alignItems: 'center',
                    justifyContent: 'center',
                    fontSize: '1.5rem',
                    boxShadow: isActive ? '0 0 12px rgba(59, 130, 246, 0.5)' : 'none',
                    border: isActive ? '1.5px solid #38bdf8' : '1px solid rgba(255,255,255,0.1)',
                  }}
                >
                  {item.icon}
                </div>

                {/* Running dot indicator */}
                {isOpen && (
                  <div
                    style={{
                      width: '4px',
                      height: '4px',
                      borderRadius: '50%',
                      backgroundColor: isActive ? '#38bdf8' : 'rgba(255,255,255,0.5)',
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
