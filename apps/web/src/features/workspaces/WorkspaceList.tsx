import React from 'react';
import { WorkspaceItem, NodeItem } from '@/contracts/types';
import { Button } from '@/shared/ui/Button';

export interface WorkspaceListProps {
  workspaces: WorkspaceItem[];
  nodes: NodeItem[];
  isLoading?: boolean;
  onCreateWorkspace: () => void;
  onSelectWorkspace: (workspaceId: string) => void;
  onOpenStudio?: (workspaceId: string) => void;
}

export const WorkspaceList: React.FC<WorkspaceListProps> = ({
  workspaces,
  nodes,
  isLoading = false,
  onCreateWorkspace,
  onSelectWorkspace,
  onOpenStudio,
}) => {
  const getNodeHostname = (nodeId: string | null) => {
    if (!nodeId) return '미할당 (Unassigned)';
    return nodes.find((n) => n.id === nodeId)?.hostname || nodeId;
  };

  return (
    <div>
      <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: '24px' }}>
        <div>
          <h2 style={{ fontSize: '1.25rem', fontWeight: 600 }}>격리 Workspace 관리 (S03-FE)</h2>
          <p style={{ fontSize: '0.875rem', color: 'var(--color-text-muted)', marginTop: '4px' }}>
            5개 물리 노드에 배치된 격리 작업공간 인벤토리 및 실행 결과 원장
          </p>
        </div>
        <Button variant="primary" size="md" onClick={onCreateWorkspace}>
          + 새 Workspace 생성
        </Button>
      </div>

      {isLoading ? (
        <div
          data-testid="workspaces-loading-state"
          style={{
            padding: '40px',
            textAlign: 'center',
            color: 'var(--color-text-muted)',
            backgroundColor: 'var(--color-bg-surface)',
            borderRadius: 'var(--radius-lg)',
            border: '1px solid var(--color-border-subtle)',
          }}
        >
          작업공간 목록을 조회하는 중입니다...
        </div>
      ) : workspaces.length === 0 ? (
        <div
          data-testid="workspaces-empty-state"
          role="status"
          aria-live="polite"
          style={{
            padding: '40px',
            textAlign: 'center',
            backgroundColor: 'var(--color-bg-surface)',
            borderRadius: 'var(--radius-lg)',
            border: '1px dashed var(--color-border-subtle)',
          }}
        >
          <div style={{ fontSize: '1.5rem', marginBottom: '8px' }}>📂</div>
          <h3 style={{ fontSize: '1rem', fontWeight: 600, color: 'var(--color-text-primary)' }}>
            등록된 작업공간이 없습니다 (정상 조회 결과: 0개).
          </h3>
          <p style={{ color: 'var(--color-text-muted)', fontSize: '0.8125rem', marginTop: '4px' }}>
            프로젝트에 연결된 Workspace가 존재하지 않습니다. 상단 '+ 새 Workspace 생성' 버튼으로 격리 작업공간을 프로비저닝하십시오.
          </p>
          <Button variant="secondary" size="sm" onClick={onCreateWorkspace} style={{ marginTop: '16px' }}>
            + 새 Workspace 생성하기
          </Button>
        </div>
      ) : (
        <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fill, minmax(320px, 1fr))', gap: '16px' }}>
          {workspaces.map((wsp) => {
            const statusConfig: Record<string, { label: string; bg: string; color: string; border: string }> = {
              provisioning: { label: '프로비저닝 중 (Provisioning)', bg: 'rgba(245, 158, 11, 0.15)', color: 'var(--color-brand-warning, #f59e0b)', border: 'rgba(245, 158, 11, 0.3)' },
              ready: { label: '준비됨 (Ready)', bg: 'rgba(59, 130, 246, 0.15)', color: '#60a5fa', border: 'rgba(59, 130, 246, 0.3)' },
              active: { label: '활성 (Active)', bg: 'rgba(16, 185, 129, 0.15)', color: 'var(--color-brand-success, #34d399)', border: 'rgba(16, 185, 129, 0.3)' },
              suspended: { label: '일시 중단 (Suspended)', bg: 'var(--color-bg-subtle)', color: 'var(--color-text-muted)', border: 'var(--color-border-subtle)' },
              terminating: { label: '종료 중 (Terminating)', bg: 'rgba(239, 68, 68, 0.15)', color: '#f87171', border: 'rgba(239, 68, 68, 0.3)' },
              reclaimed: { label: '회수됨 (Reclaimed)', bg: 'var(--color-bg-subtle)', color: 'var(--color-text-muted)', border: 'var(--color-border-subtle)' },
            };
            const cfg = statusConfig[wsp.status] || {
              label: wsp.status,
              bg: 'var(--color-bg-subtle)',
              color: 'var(--color-text-muted)',
              border: 'var(--color-border-subtle)',
            };
            return (
              <div
                key={wsp.id}
                onClick={() => onSelectWorkspace(wsp.id)}
                style={{
                  padding: '20px',
                  backgroundColor: 'var(--color-bg-surface)',
                  borderRadius: 'var(--radius-lg)',
                  border: '1px solid var(--color-border-subtle)',
                  boxShadow: 'var(--shadow-sm)',
                  cursor: 'pointer',
                  transition: 'border-color 0.2s, transform 0.15s',
                }}
                onMouseEnter={(e) => {
                  e.currentTarget.style.borderColor = 'var(--color-brand-primary)';
                  e.currentTarget.style.transform = 'translateY(-2px)';
                }}
                onMouseLeave={(e) => {
                  e.currentTarget.style.borderColor = 'var(--color-border-subtle)';
                  e.currentTarget.style.transform = 'translateY(0)';
                }}
              >
                <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'flex-start', marginBottom: '12px' }}>
                  <div>
                    <h3 style={{ fontSize: '1rem', fontWeight: 600 }}>{wsp.name}</h3>
                    <code style={{ fontSize: '0.75rem', color: 'var(--color-text-muted)' }}>{wsp.id}</code>
                  </div>
                  <span
                    data-testid={`wsp-status-${wsp.id}`}
                    style={{
                      padding: '2px 8px',
                      borderRadius: 'var(--radius-sm)',
                      fontSize: '0.6875rem',
                      fontWeight: 600,
                      backgroundColor: cfg.bg,
                      color: cfg.color,
                      border: `1px solid ${cfg.border}`,
                    }}
                  >
                    {cfg.label}
                  </span>
                </div>

                <div style={{ fontSize: '0.8125rem', display: 'flex', flexDirection: 'column', gap: '6px' }}>
                  <div style={{ display: 'flex', justifyContent: 'space-between' }}>
                    <span style={{ color: 'var(--color-text-muted)' }}>배치 노드:</span>
                    <strong>{getNodeHostname(wsp.targetNodeId)}</strong>
                  </div>
                  <div style={{ display: 'flex', justifyContent: 'space-between' }}>
                    <span style={{ color: 'var(--color-text-muted)' }}>격리 모드:</span>
                    <code>{wsp.isolationMode}</code>
                  </div>
                  <div style={{ display: 'flex', justifyContent: 'space-between' }}>
                    <span style={{ color: 'var(--color-text-muted)' }}>자원 한도:</span>
                    <span>
                      {wsp.cpuLimitCores} Cores / {(wsp.memoryLimitBytes / 1024 ** 3).toFixed(0)} GB
                    </span>
                  </div>
                  <div style={{ display: 'flex', justifyContent: 'space-between' }}>
                    <span style={{ color: 'var(--color-text-muted)' }}>허용 경로:</span>
                    <span style={{ color: 'var(--color-text-secondary)', fontSize: '0.75rem' }}>
                      {wsp.allowedPaths ? wsp.allowedPaths.join(', ') : '기본 경로'}
                    </span>
                  </div>
                </div>

                <div style={{ marginTop: '16px', paddingTop: '12px', borderTop: '1px solid var(--color-border-subtle)', display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
                  <span style={{ fontSize: '0.75rem', color: 'var(--color-brand-primary)', fontWeight: 600 }}>
                    실행 결과 및 증거 보기 →
                  </span>
                  {onOpenStudio && (
                    <button
                      onClick={(e) => {
                        e.stopPropagation();
                        onOpenStudio(wsp.id);
                      }}
                      style={{
                        padding: '4px 8px',
                        fontSize: '0.75rem',
                        fontWeight: 500,
                        borderRadius: 'var(--radius-sm)',
                        backgroundColor: 'var(--color-bg-subtle)',
                        border: '1px solid var(--color-border-strong)',
                        color: 'var(--color-text-primary)',
                        cursor: 'pointer',
                      }}
                    >
                      ⚡ Studio에서 열기
                    </button>
                  )}
                </div>
              </div>
            );
          })}
        </div>
      )}
    </div>
  );
};
