import React from 'react';
import { WorkspaceItem, NodeItem } from '@/contracts/types';
import { Button } from '@/shared/ui/Button';

export interface WorkspaceListProps {
  workspaces: WorkspaceItem[];
  nodes: NodeItem[];
  onCreateWorkspace: () => void;
  onSelectWorkspace: (workspaceId: string) => void;
  onOpenStudio?: (workspaceId: string) => void;
}

export const WorkspaceList: React.FC<WorkspaceListProps> = ({
  workspaces,
  nodes,
  onCreateWorkspace,
  onSelectWorkspace,
  onOpenStudio,
}) => {
  const getNodeHostname = (nodeId: string) => {
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

      <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fill, minmax(320px, 1fr))', gap: '16px' }}>
        {workspaces.map((wsp) => {
          const isReclaimed = wsp.status === 'reclaimed';
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
                  style={{
                    padding: '2px 8px',
                    borderRadius: 'var(--radius-sm)',
                    fontSize: '0.6875rem',
                    fontWeight: 600,
                    backgroundColor: isReclaimed ? 'var(--color-bg-subtle)' : 'rgba(16, 185, 129, 0.15)',
                    color: isReclaimed ? 'var(--color-text-muted)' : 'var(--color-brand-success)',
                    border: `1px solid ${isReclaimed ? 'var(--color-border-subtle)' : 'var(--color-brand-success)'}`,
                  }}
                >
                  {isReclaimed ? '회수됨 (Reclaimed)' : '활성 (Active)'}
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
                    {wsp.allowedPaths.join(', ')}
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
                      padding: '3px 8px',
                      fontSize: '0.75rem',
                      fontWeight: 600,
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
    </div>
  );
};
