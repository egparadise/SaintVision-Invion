import React from 'react';
import { DesktopWindow as IDesktopWindow } from '@/contracts/virtualFabric';

export type WindowControlAction = 'close' | 'minimize' | 'maximize';

export interface WindowControlStyle {
  color: string;
  bg: string;
  border: string;
  label: string;
}

export const WINDOW_CONTROL_CONFIG: Record<WindowControlAction, WindowControlStyle> = {
  close: {
    color: 'var(--color-status-offline)',
    bg: 'var(--color-bg-subtle)',
    border: 'var(--color-status-offline)',
    label: '창 닫기',
  },
  minimize: {
    color: 'var(--color-status-degraded)',
    bg: 'var(--color-bg-subtle)',
    border: 'var(--color-status-degraded)',
    label: '최소화',
  },
  maximize: {
    color: 'var(--color-status-online)',
    bg: 'var(--color-bg-subtle)',
    border: 'var(--color-status-online)',
    label: '최대화',
  },
} as const satisfies Record<WindowControlAction, WindowControlStyle>;

export function getWindowControlConfig(action?: string | null): WindowControlStyle {
  if (action && Object.hasOwn(WINDOW_CONTROL_CONFIG, action)) {
    return WINDOW_CONTROL_CONFIG[action as WindowControlAction];
  }
  return {
    color: 'var(--color-status-unknown)',
    bg: 'var(--color-bg-subtle)',
    border: 'var(--color-status-unknown)',
    label: action ? `UNKNOWN (${action})` : 'UNKNOWN',
  };
}

export interface DesktopWindowProps {
  window: IDesktopWindow;
  isActive: boolean;
  isOverlayOpen?: boolean;
  onFocus: () => void;
  onClose: () => void;
  onMinimize: () => void;
  onToggleMaximize: () => void;
  children: React.ReactNode;
}

export const DesktopWindowComponent: React.FC<DesktopWindowProps> = ({
  window,
  isActive,
  isOverlayOpen = false,
  onFocus,
  onClose,
  onMinimize,
  onToggleMaximize,
  children,
}) => {
  const handleKeyDown = (e: React.KeyboardEvent<HTMLDivElement>) => {
    if (e.key === 'Escape') {
      if (e.defaultPrevented || isOverlayOpen) return;
      const target = e.target as HTMLElement | null;
      if (target) {
        const tag = target.tagName?.toLowerCase();
        if (
          tag === 'input' ||
          tag === 'textarea' ||
          tag === 'select' ||
          target.isContentEditable ||
          target.closest('.xterm') ||
          target.closest('[data-terminal]')
        ) {
          return;
        }
      }
      e.stopPropagation();
      onClose();
    }
  };

  if (!window.isOpen || window.isMinimized) {
    return null;
  }

  const { isMaximized, position, size, zIndex, title, icon } = window;

  return (
    <div
      role="dialog"
      aria-labelledby={`window-title-${window.id}`}
      aria-modal="false"
      tabIndex={-1}
      style={
        isMaximized
          ? {
              position: 'absolute',
              top: '36px', // below top menu bar
              left: 0,
              right: 0,
              bottom: '68px', // above bottom dock
              width: '100%',
              height: 'calc(100% - 104px)',
              zIndex,
              display: 'flex',
              flexDirection: 'column',
              backgroundColor: 'var(--color-bg-surface)',
              borderRadius: 0,
              boxShadow: isActive ? 'var(--shadow-lg)' : 'var(--shadow-md)',
              border: '1px solid var(--color-border-subtle)',
              overflow: 'hidden',
              transition: 'all 0.15s ease-out',
            }
          : {
              position: 'absolute',
              top: `${Math.max(40, position.y)}px`,
              left: `${Math.max(16, position.x)}px`,
              width: `${size.width}px`,
              height: `${size.height}px`,
              maxWidth: 'calc(100vw - 32px)',
              maxHeight: 'calc(100vh - 120px)',
              zIndex,
              display: 'flex',
              flexDirection: 'column',
              backgroundColor: 'var(--color-bg-surface)',
              borderRadius: 'var(--radius-lg, 12px)',
              boxShadow: isActive
                ? 'var(--shadow-lg), 0 0 0 1px var(--color-brand-primary)'
                : 'var(--shadow-md)',
              border: '1px solid var(--color-border-strong)',
              overflow: 'hidden',
              transition: 'box-shadow 0.15s ease',
            }
      }
      onMouseDown={onFocus}
      onKeyDown={isActive ? handleKeyDown : undefined}
    >
      {/* Window Title Bar */}
      <div
        style={{
          display: 'flex',
          alignItems: 'center',
          justifyContent: 'space-between',
          padding: '8px 14px',
          backgroundColor: isActive ? 'var(--color-bg-subtle)' : 'var(--color-bg-surface)',
          borderBottom: '1px solid var(--color-border-subtle)',
          userSelect: 'none',
          cursor: 'grab',
          minHeight: '38px',
        }}
        onDoubleClick={onToggleMaximize}
      >
        {/* Left: Traffic Lights */}
        <div style={{ display: 'flex', alignItems: 'center', gap: '8px' }}>
          <button
            type="button"
            title={WINDOW_CONTROL_CONFIG.close.label}
            aria-label={`창 닫기: ${title}`}
            onClick={(e) => {
              e.stopPropagation();
              onClose();
            }}
            style={{
              width: '12px',
              height: '12px',
              borderRadius: '50%',
              backgroundColor: 'var(--color-status-offline)',
              border: 'none',
              cursor: 'pointer',
              padding: 0,
              boxShadow: 'var(--shadow-sm)',
            }}
          />
          <button
            type="button"
            title={WINDOW_CONTROL_CONFIG.minimize.label}
            aria-label={`창 최소화: ${title}`}
            onClick={(e) => {
              e.stopPropagation();
              onMinimize();
            }}
            style={{
              width: '12px',
              height: '12px',
              borderRadius: '50%',
              backgroundColor: 'var(--color-status-degraded)',
              border: 'none',
              cursor: 'pointer',
              padding: 0,
              boxShadow: 'var(--shadow-sm)',
            }}
          />
          <button
            type="button"
            title={isMaximized ? '원래 크기로 복원' : WINDOW_CONTROL_CONFIG.maximize.label}
            aria-label={isMaximized ? `원래 크기로 복원: ${title}` : `최대화: ${title}`}
            onClick={(e) => {
              e.stopPropagation();
              onToggleMaximize();
            }}
            style={{
              width: '12px',
              height: '12px',
              borderRadius: '50%',
              backgroundColor: 'var(--color-status-online)',
              border: 'none',
              cursor: 'pointer',
              padding: 0,
              boxShadow: 'var(--shadow-sm)',
            }}
          />
        </div>

        {/* Center: Title & Icon */}
        <div
          id={`window-title-${window.id}`}
          tabIndex={-1}
          style={{
            display: 'flex',
            alignItems: 'center',
            gap: '8px',
            fontSize: '0.8125rem',
            fontWeight: 600,
            color: isActive ? 'var(--color-text-primary)' : 'var(--color-text-muted)',
            letterSpacing: '0.02em',
          }}
        >
          <span style={{ fontSize: '1rem' }}>{icon}</span>
          <span>{title}</span>
        </div>

        {/* Right: Window Status indicator */}
        <div style={{ display: 'flex', alignItems: 'center', gap: '6px', fontSize: '0.6875rem', color: 'var(--color-text-muted)' }}>
          <span>{window.appId}</span>
        </div>
      </div>

      {/* Window Body */}
      <div
        style={{
          flex: 1,
          overflow: 'auto',
          position: 'relative',
          display: 'flex',
          flexDirection: 'column',
          backgroundColor: 'var(--color-bg-surface)',
        }}
      >
        {children}
      </div>
    </div>
  );
};
