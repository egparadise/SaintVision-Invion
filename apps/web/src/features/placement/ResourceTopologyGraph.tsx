import React from 'react';
import { NodeItem } from '@/contracts/types';
import { Button } from '@/shared/ui/Button';

export interface ResourceTopologyGraphProps {
  nodes: NodeItem[];
  fencedNodeIds: Set<string>;
  selectedNodeId: string | null;
  onToggleFence: (nodeId: string) => void;
}

export const ResourceTopologyGraph: React.FC<ResourceTopologyGraphProps> = ({
  nodes,
  fencedNodeIds,
  selectedNodeId,
  onToggleFence,
}) => {
  return (
    <div
      style={{
        padding: '24px',
        backgroundColor: 'var(--color-bg-surface)',
        borderRadius: 'var(--radius-lg)',
        border: '1px solid var(--color-border-subtle)',
        boxShadow: 'var(--shadow-sm)',
        marginBottom: '28px',
      }}
    >
      <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: '20px' }}>
        <div>
          <h3 style={{ fontSize: '1.125rem', fontWeight: 600 }}>5개 노드 자원 토폴로지 (S05-FE)</h3>
          <p style={{ fontSize: '0.8125rem', color: 'var(--color-text-muted)', marginTop: '2px' }}>
            물리 노드 가용 자원 및 Fencing 잠금 상태 (초과 예약 방지 및 설명 가능한 배치)
          </p>
        </div>
        <div style={{ fontSize: '0.75rem', color: 'var(--color-text-muted)', display: 'flex', gap: '16px' }}>
          <span>🟩 선정 노드 (Winner)</span>
          <span>🟥 Fenced (안전 격리)</span>
          <span>🟦 정상 가동</span>
        </div>
      </div>

      <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fit, minmax(210px, 1fr))', gap: '16px' }}>
        {nodes.map((node) => {
          const isFenced = fencedNodeIds.has(node.id);
          const isSelected = node.id === selectedNodeId;

          const availableCores = (node.cpuCores * (1 - node.cpuUsagePercent / 100)).toFixed(1);
          const availableRamGb = ((node.memoryTotalBytes - node.memoryUsedBytes) / 1024 ** 3).toFixed(1);
          const totalRamGb = (node.memoryTotalBytes / 1024 ** 3).toFixed(0);

          let borderColor = 'var(--color-border-subtle)';
          let bgColor = 'var(--color-bg-subtle)';

          if (isFenced) {
            borderColor = 'var(--color-risk-l3-border)';
            bgColor = 'var(--color-risk-l3-bg)';
          } else if (isSelected) {
            borderColor = 'var(--color-brand-success)';
            bgColor = 'rgba(16, 185, 129, 0.08)';
          }

          return (
            <div
              key={node.id}
              style={{
                padding: '16px',
                borderRadius: 'var(--radius-md)',
                border: `2px solid ${borderColor}`,
                backgroundColor: bgColor,
                display: 'flex',
                flexDirection: 'column',
                gap: '10px',
                position: 'relative',
              }}
            >
              <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'flex-start' }}>
                <div>
                  <div style={{ fontWeight: 700, fontSize: '0.875rem' }}>{node.hostname}</div>
                  <code style={{ fontSize: '0.6875rem', color: 'var(--color-text-muted)' }}>{node.id}</code>
                </div>
                {isSelected && (
                  <span
                    style={{
                      padding: '2px 6px',
                      borderRadius: '4px',
                      fontSize: '0.6875rem',
                      fontWeight: 700,
                      backgroundColor: 'var(--color-brand-success)',
                      color: '#ffffff',
                    }}
                  >
                    1순위 배치
                  </span>
                )}
                {isFenced && (
                  <span
                    style={{
                      padding: '2px 6px',
                      borderRadius: '4px',
                      fontSize: '0.6875rem',
                      fontWeight: 700,
                      backgroundColor: 'var(--color-brand-danger)',
                      color: '#ffffff',
                    }}
                  >
                    FENCED
                  </span>
                )}
              </div>

              <div style={{ fontSize: '0.75rem', display: 'flex', flexDirection: 'column', gap: '4px' }}>
                <div style={{ display: 'flex', justifyContent: 'space-between' }}>
                  <span style={{ color: 'var(--color-text-muted)' }}>OS:</span>
                  <strong>{node.os.toUpperCase()}</strong>
                </div>
                <div style={{ display: 'flex', justifyContent: 'space-between' }}>
                  <span style={{ color: 'var(--color-text-muted)' }}>CPU 가용:</span>
                  <strong>
                    {availableCores} / {node.cpuCores} Cores ({node.cpuUsagePercent}%)
                  </strong>
                </div>
                <div style={{ display: 'flex', justifyContent: 'space-between' }}>
                  <span style={{ color: 'var(--color-text-muted)' }}>RAM 가용:</span>
                  <strong>
                    {availableRamGb} / {totalRamGb} GB
                  </strong>
                </div>
                <div style={{ display: 'flex', justifyContent: 'space-between' }}>
                  <span style={{ color: 'var(--color-text-muted)' }}>GPU:</span>
                  <span>{node.gpuCount > 0 ? `${node.gpuName}` : '없음'}</span>
                </div>
              </div>

              <div style={{ marginTop: 'auto', paddingTop: '8px' }}>
                <Button
                  variant={isFenced ? 'secondary' : 'danger'}
                  size="sm"
                  onClick={() => onToggleFence(node.id)}
                  style={{ width: '100%', fontSize: '0.6875rem', padding: '4px 6px' }}
                >
                  {isFenced ? '격리 해제 (Unfence)' : '노드 Fencing 격리'}
                </Button>
              </div>
            </div>
          );
        })}
      </div>
    </div>
  );
};
