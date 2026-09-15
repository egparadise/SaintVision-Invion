import React from 'react';
import { DesktopWindow as IDesktopWindow } from '@/contracts/virtualFabric';

export interface DesktopWindowProps {
  window: IDesktopWindow;
  isActive: boolean;
  onFocus: () => void;
  onClose: () => void;
  onMinimize: () => void;
  onToggleMaximize: () => void;
  children: React.ReactNode;
}

export const DesktopWindowComponent: React.FC<DesktopWindowProps> = ({
  window,
  isActive,
  onFocus,
  onClose,
  onMinimize,
  onToggleMaximize,
  children,
}) => {
  if (!window.isOpen || window.isMinimized) {
    return null;
  }

  const { isMaximized, position, size, zIndex, title, icon } = window;

  const style: React.CSSProperties = isMaximized
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
        boxShadow: isActive
          ? '0 12px 36px rgba(0, 0, 0, 0.45)'
          : '0 4px 16px rgba(0, 0, 0, 0.25)',
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
          ? '0 16px 40px rgba(0, 0, 0, 0.5), 0 0 0 1px var(--color-brand-primary)'
          : '0 6px 20px rgba(0, 0, 0, 0.3)',
        border: '1px solid var(--color-border-strong, #333)',
        overflow: 'hidden',
        transition: 'box-shadow 0.15s ease',
      };

  return (
    <div
      role="dialog"
      aria-labelledby={`window-title-${window.id}`}
      aria-modal="false"
      tabIndex={-1}
      style={style}
      onMouseDown={onFocus}
    >
      {/* Window Title Bar */}
      <div
        style={{
          display: 'flex',
          alignItems: 'center',
          justifyContent: 'space-between',
          padding: '8px 14px',
          backgroundColor: isActive ? 'var(--color-bg-subtle, #1e293b)' : 'var(--color-bg-surface, #0f172a)',
          borderBottom: '1px solid var(--color-border-subtle, #334155)',
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
            title="창 닫기 (Esc)"
            aria-label={`창 닫기: ${title}`}
            onClick={(e) => {
              e.stopPropagation();
              onClose();
            }}
            style={{
              width: '12px',
              height: '12px',
              borderRadius: '50%',
              backgroundColor: '#ef4444',
              border: 'none',
              cursor: 'pointer',
              padding: 0,
              boxShadow: '0 1px 3px rgba(0,0,0,0.3)',
            }}
          />
          <button
            type="button"
            title="최소화"
            aria-label={`창 최소화: ${title}`}
            onClick={(e) => {
              e.stopPropagation();
              onMinimize();
            }}
            style={{
              width: '12px',
              height: '12px',
              borderRadius: '50%',
              backgroundColor: '#f59e0b',
              border: 'none',
              cursor: 'pointer',
              padding: 0,
              boxShadow: '0 1px 3px rgba(0,0,0,0.3)',
            }}
          />
          <button
            type="button"
            title={isMaximized ? '원래 크기로 복원' : '최대화'}
            aria-label={isMaximized ? `원래 크기로 복원: ${title}` : `최대화: ${title}`}
            onClick={(e) => {
              e.stopPropagation();
              onToggleMaximize();
            }}
            style={{
              width: '12px',
              height: '12px',
              borderRadius: '50%',
              backgroundColor: '#10b981',
              border: 'none',
              cursor: 'pointer',
              padding: 0,
              boxShadow: '0 1px 3px rgba(0,0,0,0.3)',
            }}
          />
        </div>

        {/* Center: Title & Icon */}
        <div
          id={`window-title-${window.id}`}
          style={{
            display: 'flex',
            alignItems: 'center',
            gap: '8px',
            fontSize: '0.8125rem',
            fontWeight: 600,
            color: isActive ? 'var(--color-text-primary, #f8fafc)' : 'var(--color-text-muted, #94a3b8)',
            letterSpacing: '0.02em',
          }}
        >
          <span style={{ fontSize: '1rem' }}>{icon}</span>
          <span>{title}</span>
        </div>

        {/* Right: Window Status indicator */}
        <div style={{ display: 'flex', alignItems: 'center', gap: '6px', fontSize: '0.6875rem', color: 'var(--color-text-muted, #64748b)' }}>
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
