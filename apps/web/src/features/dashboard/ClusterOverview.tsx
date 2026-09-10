import React from 'react';
import { NodeItem, RunItem } from '@/contracts/types';
import { Button } from '@/shared/ui/Button';

export interface ClusterOverviewProps {
  nodes: NodeItem[];
  runs: RunItem[];
  pendingApprovalsCount: number;
  onNavigate: (tab: string) => void;
}

export const ClusterOverview: React.FC<ClusterOverviewProps> = ({
  nodes,
  runs,
  pendingApprovalsCount,
  onNavigate,
}) => {
  // Aggregate Cluster Metrics
  const totalCores = nodes.reduce((acc, n) => acc + n.cpuCores, 0);
  const avgCpuUsage = Math.round(
    nodes.reduce((acc, n) => acc + n.cpuUsagePercent, 0) / (nodes.length || 1)
  );

  const totalRamGb = Math.round(
    nodes.reduce((acc, n) => acc + n.memoryTotalBytes, 0) / (1024 ** 3)
  );
  const usedRamGb = Math.round(
    nodes.reduce((acc, n) => acc + n.memoryUsedBytes, 0) / (1024 ** 3)
  );

  const totalGpus = nodes.reduce((acc, n) => acc + n.gpuCount, 0);
  const totalVramGb = Math.round(
    nodes.reduce((acc, n) => acc + (n.gpuVramTotalBytes || 0), 0) / (1024 ** 3)
  );
  const usedVramGb = Math.round(
    nodes.reduce((acc, n) => acc + (n.gpuVramUsedBytes || 0), 0) / (1024 ** 3)
  );

  const totalStorageTb = (
    nodes.reduce((acc, n) => acc + n.storageTotalBytes, 0) / (1024 ** 4)
  ).toFixed(1);
  const usedStorageTb = (
    nodes.reduce((acc, n) => acc + n.storageUsedBytes, 0) / (1024 ** 4)
  ).toFixed(1);

  const onlineNodes = nodes.filter((n) => n.status === 'online').length;
  const runningRuns = runs.filter((r) => r.state === 'running').length;

  return (
    <div>
      {/* Top Banner: Status & Quick Action */}
      <div
        style={{
          display: 'flex',
          justifyContent: 'space-between',
          alignItems: 'center',
          marginBottom: '28px',
          padding: '20px 24px',
          backgroundColor: 'var(--color-bg-surface)',
          borderRadius: 'var(--radius-lg)',
          border: '1px solid var(--color-border-subtle)',
          boxShadow: 'var(--shadow-sm)',
        }}
      >
        <div>
          <h1 style={{ fontSize: '1.375rem', fontWeight: 700 }}>5개 분산 Node 클러스터 개요</h1>
          <p style={{ fontSize: '0.875rem', color: 'var(--color-text-muted)', marginTop: '4px' }}>
            Windows 3대 + Linux 2대 사내 물리 기기 연동 (온라인 {onlineNodes}/{nodes.length}대, 활성 실행 {runningRuns}건)
          </p>
        </div>

        <div style={{ display: 'flex', gap: '12px' }}>
          {pendingApprovalsCount > 0 && (
            <Button variant="danger" size="md" onClick={() => onNavigate('approvals')}>
              🚨 승인 대기 ({pendingApprovalsCount}건)
            </Button>
          )}
          <Button variant="primary" size="md" onClick={() => onNavigate('runs')}>
            Run 대시보드 이동
          </Button>
        </div>
      </div>

      {/* Resource Gauge Metric Cards */}
      <div
        style={{
          display: 'grid',
          gridTemplateColumns: 'repeat(auto-fit, minmax(240px, 1fr))',
          gap: '16px',
          marginBottom: '28px',
        }}
      >
        {/* CPU Gauge */}
        <div
          style={{
            padding: '20px',
            backgroundColor: 'var(--color-bg-surface)',
            borderRadius: 'var(--radius-lg)',
            border: '1px solid var(--color-border-subtle)',
          }}
        >
          <div style={{ fontSize: '0.8125rem', color: 'var(--color-text-muted)', marginBottom: '6px' }}>
            가상 CPU 코어 풀
          </div>
          <div style={{ fontSize: '1.75rem', fontWeight: 700, color: 'var(--color-text-primary)' }}>
            {totalCores} Cores
          </div>
          <div style={{ fontSize: '0.8125rem', color: 'var(--color-text-secondary)', marginTop: '4px' }}>
            평균 가동률: {avgCpuUsage}%
          </div>
          <div
            style={{
              height: '6px',
              backgroundColor: 'var(--color-bg-subtle)',
              borderRadius: '3px',
              overflow: 'hidden',
              marginTop: '12px',
            }}
          >
            <div
              style={{
                width: `${avgCpuUsage}%`,
                height: '100%',
                backgroundColor: 'var(--color-brand-primary)',
              }}
            />
          </div>
        </div>

        {/* RAM Gauge */}
        <div
          style={{
            padding: '20px',
            backgroundColor: 'var(--color-bg-surface)',
            borderRadius: 'var(--radius-lg)',
            border: '1px solid var(--color-border-subtle)',
          }}
        >
          <div style={{ fontSize: '0.8125rem', color: 'var(--color-text-muted)', marginBottom: '6px' }}>
            물리 메모리 (RAM) 풀
          </div>
          <div style={{ fontSize: '1.75rem', fontWeight: 700, color: 'var(--color-text-primary)' }}>
            {usedRamGb} / {totalRamGb} GiB
          </div>
          <div style={{ fontSize: '0.8125rem', color: 'var(--color-text-secondary)', marginTop: '4px' }}>
            할당률: {Math.round((usedRamGb / (totalRamGb || 1)) * 100)}%
          </div>
          <div
            style={{
              height: '6px',
              backgroundColor: 'var(--color-bg-subtle)',
              borderRadius: '3px',
              overflow: 'hidden',
              marginTop: '12px',
            }}
          >
            <div
              style={{
                width: `${Math.round((usedRamGb / (totalRamGb || 1)) * 100)}%`,
                height: '100%',
                backgroundColor: '#10b981',
              }}
            />
          </div>
        </div>

        {/* GPU & VRAM Gauge */}
        <div
          style={{
            padding: '20px',
            backgroundColor: 'var(--color-bg-surface)',
            borderRadius: 'var(--radius-lg)',
            border: '1px solid var(--color-border-subtle)',
          }}
        >
          <div style={{ fontSize: '0.8125rem', color: 'var(--color-text-muted)', marginBottom: '6px' }}>
            가속 GPU & VRAM 풀
          </div>
          <div style={{ fontSize: '1.75rem', fontWeight: 700, color: 'var(--color-text-primary)' }}>
            {totalGpus} GPUs ({totalVramGb} GiB)
          </div>
          <div style={{ fontSize: '0.8125rem', color: 'var(--color-text-secondary)', marginTop: '4px' }}>
            VRAM 할당: {usedVramGb} GiB ({Math.round((usedVramGb / (totalVramGb || 1)) * 100)}%)
          </div>
          <div
            style={{
              height: '6px',
              backgroundColor: 'var(--color-bg-subtle)',
              borderRadius: '3px',
              overflow: 'hidden',
              marginTop: '12px',
            }}
          >
            <div
              style={{
                width: `${Math.round((usedVramGb / (totalVramGb || 1)) * 100)}%`,
                height: '100%',
                backgroundColor: '#8b5cf6',
              }}
            />
          </div>
        </div>

        {/* Storage Gauge */}
        <div
          style={{
            padding: '20px',
            backgroundColor: 'var(--color-bg-surface)',
            borderRadius: 'var(--radius-lg)',
            border: '1px solid var(--color-border-subtle)',
          }}
        >
          <div style={{ fontSize: '0.8125rem', color: 'var(--color-text-muted)', marginBottom: '6px' }}>
            제공 로컬 스토리지 합계
          </div>
          <div style={{ fontSize: '1.75rem', fontWeight: 700, color: 'var(--color-text-primary)' }}>
            {usedStorageTb} / {totalStorageTb} TB
          </div>
          <div style={{ fontSize: '0.8125rem', color: 'var(--color-text-secondary)', marginTop: '4px' }}>
            사용량: {Math.round((Number(usedStorageTb) / (Number(totalStorageTb) || 1)) * 100)}%
          </div>
          <div
            style={{
              height: '6px',
              backgroundColor: 'var(--color-bg-subtle)',
              borderRadius: '3px',
              overflow: 'hidden',
              marginTop: '12px',
            }}
          >
            <div
              style={{
                width: `${Math.round((Number(usedStorageTb) / (Number(totalStorageTb) || 1)) * 100)}%`,
                height: '100%',
                backgroundColor: '#f59e0b',
              }}
            />
          </div>
        </div>
      </div>

      {/* Cluster Node Status Grid */}
      <div
        style={{
          display: 'grid',
          gridTemplateColumns: 'repeat(auto-fit, minmax(340px, 1fr))',
          gap: '20px',
        }}
      >
        {/* Node Status Summary */}
        <div
          style={{
            padding: '24px',
            backgroundColor: 'var(--color-bg-surface)',
            borderRadius: 'var(--radius-lg)',
            border: '1px solid var(--color-border-subtle)',
          }}
        >
          <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: '16px' }}>
            <h3 style={{ fontSize: '1.0625rem', fontWeight: 600 }}>물리 Node 상태 요약</h3>
            <Button variant="ghost" size="sm" onClick={() => onNavigate('nodes')}>
              전체 보기 →
            </Button>
          </div>

          <div style={{ display: 'flex', flexDirection: 'column', gap: '10px' }}>
            {nodes.map((node) => (
              <div
                key={node.id}
                style={{
                  display: 'flex',
                  justifyContent: 'space-between',
                  alignItems: 'center',
                  padding: '10px 14px',
                  backgroundColor: 'var(--color-bg-canvas)',
                  borderRadius: 'var(--radius-md)',
                }}
              >
                <div>
                  <div style={{ fontWeight: 600, fontSize: '0.875rem' }}>{node.hostname}</div>
                  <div style={{ fontSize: '0.75rem', color: 'var(--color-text-muted)' }}>
                    {node.os.toUpperCase()} · {node.cpuCores}C / {Math.round(node.memoryTotalBytes / 1024 ** 3)}G
                    {node.gpuCount > 0 && ` · ${node.gpuName}`}
                  </div>
                </div>

                <span
                  style={{
                    fontSize: '0.75rem',
                    fontWeight: 600,
                    color: node.status === 'online' ? 'var(--color-status-online)' : 'var(--color-status-offline)',
                  }}
                >
                  ● {node.status.toUpperCase()}
                </span>
              </div>
            ))}
          </div>
        </div>

        {/* Active Runs Summary */}
        <div
          style={{
            padding: '24px',
            backgroundColor: 'var(--color-bg-surface)',
            borderRadius: 'var(--radius-lg)',
            border: '1px solid var(--color-border-subtle)',
          }}
        >
          <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: '16px' }}>
            <h3 style={{ fontSize: '1.0625rem', fontWeight: 600 }}>활성 실행 작업 (Run)</h3>
            <Button variant="ghost" size="sm" onClick={() => onNavigate('runs')}>
              전체 보기 →
            </Button>
          </div>

          <div style={{ display: 'flex', flexDirection: 'column', gap: '10px' }}>
            {runs.slice(0, 3).map((run) => (
              <div
                key={run.id}
                style={{
                  padding: '12px 14px',
                  backgroundColor: 'var(--color-bg-canvas)',
                  borderRadius: 'var(--radius-md)',
                }}
              >
                <div style={{ display: 'flex', justifyContent: 'space-between', marginBottom: '4px' }}>
                  <span style={{ fontFamily: 'monospace', fontWeight: 600, fontSize: '0.8125rem' }}>
                    {run.id}
                  </span>
                  <span style={{ fontSize: '0.75rem', fontWeight: 600, color: 'var(--color-brand-primary)' }}>
                    {run.state.toUpperCase()}
                  </span>
                </div>
                <div style={{ fontSize: '0.875rem', color: 'var(--color-text-secondary)' }}>
                  {run.objective}
                </div>
              </div>
            ))}
          </div>
        </div>
      </div>
    </div>
  );
};
