import React, { useState, useEffect } from 'react';
import { Button } from './Button';

export interface HeaderProps {
  currentTheme: 'light' | 'dark';
  onToggleTheme: () => void;
  onlineNodesCount?: number;
  totalNodesCount?: number;
  activeTab: string;
  onSelectTab: (tab: string) => void;
  currentUser?: { id: string; name: string; role: string } | null;
  onLogout?: () => void;
}

export const Header: React.FC<HeaderProps> = ({
  currentTheme,
  onToggleTheme,
  onlineNodesCount = 0,
  totalNodesCount = 0,
  activeTab,
  onSelectTab,
  currentUser,
  onLogout,
}) => {
  const [gatewayStatus, setGatewayStatus] = useState<{ online: boolean | null; rttMs: number | null }>({
    online: null,
    rttMs: null,
  });

  useEffect(() => {
    let isMounted = true;
    const checkGateway = async () => {
      const start = performance.now();
      try {
        const res = await fetch('/readyz');
        const rtt = Math.round(performance.now() - start);
        if (isMounted) {
          if (res.ok) {
            setGatewayStatus({ online: true, rttMs: rtt });
          } else {
            setGatewayStatus({ online: false, rttMs: null });
          }
        }
      } catch {
        if (isMounted) {
          setGatewayStatus({ online: false, rttMs: null });
        }
      }
    };
    checkGateway();
    const interval = setInterval(checkGateway, 5000);
    return () => {
      isMounted = false;
      clearInterval(interval);
    };
  }, []);

  const tabs = [
    { id: 'dashboard', label: '클러스터 개요' },
    { id: 'studio', label: '🚀 개발 Studio (통합)' },
    { id: 'nodes', label: 'Nodes 인벤토리' },
    { id: 'workspaces', label: 'Workspaces (S03)' },
    { id: 'editor', label: '개발 에디터 (S06)' },
    { id: 'placement', label: '자원 배치 (S05)' },
    { id: 'recovery', label: '분산 복구 (S07)' },
    { id: 'admin', label: '보안·감사 (S08)' },
    { id: 'agent', label: '자연어 요청 (S09)' },
    { id: 'mlops', label: '모델 계보 (S10)' },
    { id: 'release', label: '배포 후보 (S11)' },
    { id: 'deployment', label: '내부망 배포 (S12)' },
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
        minHeight: '60px',
        flexWrap: 'wrap',
        gap: '12px',
        backgroundColor: 'var(--color-bg-surface)',
        borderBottom: '1px solid var(--color-border-subtle)',
        position: 'sticky',
        top: 0,
        zIndex: 50,
      }}
    >
      <div style={{ display: 'flex', alignItems: 'center', gap: '24px', flex: 1, minWidth: 0 }}>
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

        <nav aria-label="주 메뉴" style={{ display: 'flex', gap: '8px', minWidth: 0, overflowX: 'auto' }}>
          {tabs.map((tab) => {
            const isActive = activeTab === tab.id;
            return (
              <button
                key={tab.id}
                onClick={() => onSelectTab(tab.id)}
                style={{
                  whiteSpace: 'nowrap', flexShrink: 0,
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

      <div style={{ display: 'flex', alignItems: 'center', gap: '16px', flexWrap: 'wrap', whiteSpace: 'nowrap' }}>
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
          title="Control Plane Gateway 실시간 RTT 지연시간"
        >
          <span
            style={{
              width: '8px',
              height: '8px',
              borderRadius: '50%',
              backgroundColor: gatewayStatus.online ? 'var(--color-status-online)' : '#f85149',
              display: 'inline-block',
            }}
          />
          <span style={{ color: 'var(--color-text-secondary)' }}>
            Gateway: {gatewayStatus.online === null ? <strong>확인 중</strong> : gatewayStatus.online ? <strong>{gatewayStatus.rttMs ?? 0}ms</strong> : <strong style={{ color: '#f85149' }}>Offline</strong>}
          </span>
        </div>

        {currentUser ? (
          <div
            style={{
              display: 'flex',
              alignItems: 'center',
              gap: '8px',
              padding: '4px 10px',
              backgroundColor: 'rgba(56, 139, 253, 0.12)',
              border: '1px solid rgba(56, 139, 253, 0.3)',
              borderRadius: 'var(--radius-md)',
              fontSize: '0.8125rem',
            }}
          >
            <span style={{ fontWeight: 600, color: '#58a6ff' }}>
              👤 <span title={currentUser.id}>{currentUser.name.length > 24 ? `${currentUser.name.slice(0, 20)}…` : currentUser.name}</span>
            </span>
            <span
              style={{
                fontSize: '0.6875rem',
                backgroundColor: 'rgba(56, 139, 253, 0.25)',
                padding: '1px 5px',
                borderRadius: 'var(--radius-sm)',
                color: '#79c0ff',
              }}
            >
              {currentUser.role}
            </span>
            {onLogout && (
              <Button variant="ghost" size="sm" onClick={onLogout} style={{ padding: '2px 6px', fontSize: '0.75rem', color: '#f85149' }}>
                로그아웃
              </Button>
            )}
          </div>
        ) : (
          <Button variant="primary" size="sm" onClick={() => onSelectTab('login')}>
            SSO 로그인
          </Button>
        )}

        <Button variant="secondary" size="sm" onClick={onToggleTheme} aria-label="테마 전환">
          {currentTheme === 'dark' ? '☀️ 라이트 모드' : '🌙 다크 모드'}
        </Button>
      </div>
    </header>
  );
};
