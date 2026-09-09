import React from 'react';
import { Button } from './Button';

export interface HeaderProps {
  currentTheme: 'light' | 'dark';
  onToggleTheme: () => void;
  onlineNodesCount?: number;
  totalNodesCount?: number;
  activeTab: string;
  onSelectTab: (tab: string) => void;
}

export const Header: React.FC<HeaderProps> = ({
  currentTheme,
  onToggleTheme,
  onlineNodesCount = 5,
  totalNodesCount = 5,
  activeTab,
  onSelectTab,
}) => {
  const tabs = [
    { id: 'dashboard', label: '클러스터 개요' },
    { id: 'nodes', label: 'Nodes 인벤토리' },
    { id: 'workspaces', label: 'Workspaces (S03)' },
    { id: 'editor', label: '개발 에디터 (S06)' },
    { id: 'placement', label: '자원 배치 (S05)' },
    { id: 'runs', label: 'Runs 실행' },
    { id: 'approvals', label: '승인 센터' },
    { id: 'terminal', label: '웹 터미널' },
    { id: 'login', label: 'SSO 로그인' },
  ];

  return (
    <header
      style={{
        display: 'flex',
        alignItems: 'center',
        justifyContent: 'space-between',
        padding: '0 24px',
        height: '60px',
        backgroundColor: 'var(--color-bg-surface)',
        borderBottom: '1px solid var(--color-border-subtle)',
        position: 'sticky',
        top: 0,
        zIndex: 50,
      }}
    >
      <div style={{ display: 'flex', alignItems: 'center', gap: '24px' }}>
        <div style={{ display: 'flex', alignItems: 'center', gap: '10px' }}>
          <span style={{ fontSize: '1.25rem', fontWeight: 700, color: 'var(--color-brand-primary)' }}>
            SaintVision
          </span>
          <span
            style={{
              fontSize: '0.75rem',
              backgroundColor: 'var(--color-bg-subtle)',
              padding: '2px 6px',
              borderRadius: 'var(--radius-sm)',
              color: 'var(--color-text-muted)',
            }}
          >
            INV Portal
          </span>
        </div>

        <nav style={{ display: 'flex', gap: '8px' }}>
          {tabs.map((tab) => {
            const isActive = activeTab === tab.id;
            return (
              <button
                key={tab.id}
                onClick={() => onSelectTab(tab.id)}
                style={{
                  padding: '8px 12px',
                  fontSize: '0.875rem',
                  fontWeight: isActive ? 600 : 500,
                  color: isActive ? 'var(--color-brand-primary)' : 'var(--color-text-secondary)',
                  borderBottom: isActive ? '2px solid var(--color-brand-primary)' : '2px solid transparent',
                  background: 'none',
                  cursor: 'pointer',
                  borderRadius: 'var(--radius-sm) var(--radius-sm) 0 0',
                }}
              >
                {tab.label}
              </button>
            );
          })}
        </nav>
      </div>

      <div style={{ display: 'flex', alignItems: 'center', gap: '16px' }}>
        <div
          style={{
            display: 'flex',
            alignItems: 'center',
            gap: '6px',
            fontSize: '0.8125rem',
            padding: '4px 10px',
            backgroundColor: 'var(--color-bg-subtle)',
            borderRadius: 'var(--radius-md)',
          }}
        >
          <span
            style={{
              width: '8px',
              height: '8px',
              borderRadius: '50%',
              backgroundColor: 'var(--color-status-online)',
              display: 'inline-block',
            }}
          />
          <span style={{ color: 'var(--color-text-secondary)' }}>
            클러스터: <strong>{onlineNodesCount}/{totalNodesCount}</strong> Node 가동 중
          </span>
        </div>

        <Button variant="secondary" size="sm" onClick={onToggleTheme} aria-label="테마 전환">
          {currentTheme === 'dark' ? '☀️ 라이트 모드' : '🌙 다크 모드'}
        </Button>
      </div>
    </header>
  );
};
