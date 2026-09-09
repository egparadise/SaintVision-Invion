import React from 'react';
import { NodeItem, ProblemDetails } from '@/contracts/types';
import { Skeleton } from '@/shared/ui/Skeleton';
import { EmptyState } from '@/shared/ui/EmptyState';
import { ErrorState } from '@/shared/ui/ErrorState';

export interface NodeListProps {
  nodes: NodeItem[];
  isLoading: boolean;
  error: ProblemDetails | null;
  isForbidden?: boolean;
  onRefresh?: () => void;
  onSelectNode?: (nodeId: string) => void;
}

export const NodeList: React.FC<NodeListProps> = ({
  nodes,
  isLoading,
  error,
  isForbidden = false,
  onRefresh,
  onSelectNode,
}) => {
  // State 1: Forbidden (403)
  if (isForbidden) {
    return (
      <div
        role="alert"
        style={{
          padding: '32px',
          textAlign: 'center',
          backgroundColor: 'var(--color-bg-surface)',
          borderRadius: 'var(--radius-lg)',
          border: '1px solid var(--color-border-subtle)',
        }}
      >
        <span style={{ fontSize: '2.5rem' }}>🔒</span>
        <h3 style={{ fontSize: '1.25rem', fontWeight: 600, marginTop: '12px' }}>접근 권한 부족 (403)</h3>
        <p style={{ color: 'var(--color-text-muted)', marginTop: '8px' }}>
          Node 인벤토리를 열람하려면 <code>node:read</code> 권한이 필요합니다. 관리자에게 승인을 요청하십시오.
        </p>
      </div>
    );
  }

  // State 2: Error
  if (error) {
    return <ErrorState problem={error} onRetry={onRefresh} />;
  }

  // State 3: Loading (Skeleton Grid)
  if (isLoading) {
    return (
      <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fill, minmax(300px, 1fr))', gap: '16px' }}>
        {[1, 2, 3, 4, 5].map((i) => (
          <div
            key={i}
            style={{
              padding: '20px',
              backgroundColor: 'var(--color-bg-surface)',
              borderRadius: 'var(--radius-lg)',
              border: '1px solid var(--color-border-subtle)',
            }}
          >
            <Skeleton width="60%" height="1.25rem" style={{ marginBottom: '12px' }} />
            <Skeleton width="40%" height="0.875rem" style={{ marginBottom: '16px' }} />
            <Skeleton width="100%" height="0.75rem" style={{ marginBottom: '8px' }} />
            <Skeleton width="90%" height="0.75rem" />
          </div>
        ))}
      </div>
    );
  }

  // State 4: Empty
  if (nodes.length === 0) {
    return (
      <EmptyState
        title="등록된 Node가 없습니다"
        description="SaintVision Agent 데몬을 PC에 실행하여 클러스터에 합류시키십시오."
        icon="🖥️"
        actionLabel="Node Agent 설치 안내"
        onAction={() => alert('Agent 설치 가이드: python -m saintvision.agent --bootstrap')}
      />
    );
  }

  // State 5: Normal & Partial
  return (
    <div>
      <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: '16px' }}>
        <h2 style={{ fontSize: '1.25rem', fontWeight: 600 }}>Node 인벤토리 ({nodes.length}대)</h2>
        <span style={{ fontSize: '0.8125rem', color: 'var(--color-text-muted)' }}>
          하트비트 주기: 15초 (이탈 감지 한도 60초)
        </span>
      </div>

      <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fill, minmax(320px, 1fr))', gap: '16px' }}>
        {nodes.map((node) => {
          const statusColor =
            node.status === 'online'
              ? 'var(--color-status-online)'
              : node.status === 'degraded'
              ? 'var(--color-status-degraded)'
              : 'var(--color-status-offline)';

          const ramUsedGb = (node.memoryUsedBytes / (1024 ** 3)).toFixed(1);
          const ramTotalGb = (node.memoryTotalBytes / (1024 ** 3)).toFixed(1);
          const storageUsedGb = (node.storageUsedBytes / (1024 ** 3)).toFixed(1);
          const storageTotalGb = (node.storageTotalBytes / (1024 ** 3)).toFixed(1);

          return (
            <div
              key={node.id}
              onClick={() => onSelectNode?.(node.id)}
              style={{
                padding: '20px',
                backgroundColor: 'var(--color-bg-surface)',
                borderRadius: 'var(--radius-lg)',
                border: '1px solid var(--color-border-subtle)',
                boxShadow: 'var(--shadow-sm)',
                cursor: 'pointer',
                transition: 'border-color 0.2s, box-shadow 0.2s',
              }}
            >
              <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'flex-start', marginBottom: '12px' }}>
                <div>
                  <h3 style={{ fontSize: '1rem', fontWeight: 600 }}>{node.hostname}</h3>
                  <span style={{ fontSize: '0.75rem', color: 'var(--color-text-muted)', fontFamily: 'monospace' }}>
                    {node.id} · {node.os.toUpperCase()}
                  </span>
                </div>

                <span
                  style={{
                    display: 'inline-flex',
                    alignItems: 'center',
                    gap: '4px',
                    padding: '2px 8px',
                    borderRadius: 'var(--radius-sm)',
                    fontSize: '0.75rem',
                    fontWeight: 600,
                    color: statusColor,
                    backgroundColor: 'var(--color-bg-subtle)',
                    border: `1px solid ${statusColor}`,
                  }}
                >
                  <span style={{ width: '6px', height: '6px', borderRadius: '50%', backgroundColor: statusColor }} />
                  {node.status.toUpperCase()}
                </span>
              </div>

              {/* Hardware specs */}
              <div style={{ fontSize: '0.8125rem', display: 'flex', flexDirection: 'column', gap: '8px' }}>
                <div>
                  <div style={{ display: 'flex', justifyContent: 'space-between', marginBottom: '2px' }}>
                    <span style={{ color: 'var(--color-text-muted)' }}>CPU Cores:</span>
                    <span>{node.cpuCores} 코어 ({node.cpuUsagePercent}%)</span>
                  </div>
                  <div style={{ height: '4px', backgroundColor: 'var(--color-bg-subtle)', borderRadius: '2px', overflow: 'hidden' }}>
                    <div style={{ width: `${node.cpuUsagePercent}%`, height: '100%', backgroundColor: 'var(--color-brand-primary)' }} />
                  </div>
                </div>

                <div>
                  <div style={{ display: 'flex', justifyContent: 'space-between', marginBottom: '2px' }}>
                    <span style={{ color: 'var(--color-text-muted)' }}>RAM:</span>
                    <span>{ramUsedGb} / {ramTotalGb} GiB</span>
                  </div>
                </div>

                {node.gpuCount > 0 && (
                  <div style={{ padding: '6px 8px', backgroundColor: 'var(--color-bg-subtle)', borderRadius: 'var(--radius-sm)' }}>
                    <div style={{ fontWeight: 600, color: 'var(--color-text-primary)' }}>
                      🎮 {node.gpuName || 'NVIDIA GPU'} ({node.gpuCount}대)
                    </div>
                    {node.gpuVramTotalBytes && (
                      <span style={{ fontSize: '0.75rem', color: 'var(--color-text-muted)' }}>
                        VRAM: {(node.gpuVramUsedBytes! / (1024 ** 3)).toFixed(1)} / {(node.gpuVramTotalBytes / (1024 ** 3)).toFixed(1)} GiB
                      </span>
                    )}
                  </div>
                )}

                <div style={{ display: 'flex', justifyContent: 'space-between', color: 'var(--color-text-muted)', fontSize: '0.75rem', marginTop: '4px' }}>
                  <span>로컬 스토리지:</span>
                  <span>{storageUsedGb} / {storageTotalGb} GiB</span>
                </div>
              </div>
            </div>
          );
        })}
      </div>
    </div>
  );
};
