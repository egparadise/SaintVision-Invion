import React from 'react';
import { NodeItem, RunItem } from '@/contracts/types';
import { Button } from '@/shared/ui/Button';

export interface ClusterOverviewProps {
  nodes: NodeItem[];
  runs: RunItem[];
  pendingApprovalsCount: number;
  onNavigate: (tab: string) => void;
  nodesState?: 'idle' | 'loading' | 'success' | 'error';
  nodeError?: string | null;
  lastFetchedAt?: Date | null;
  onRefresh?: () => void;
}

export const ClusterOverview: React.FC<ClusterOverviewProps> = ({
  nodes,
  runs = [],
  pendingApprovalsCount,
  onNavigate,
  nodesState = 'idle',
  nodeError = null,
  lastFetchedAt = null,
  onRefresh,
}) => {
  // 1. 에러 상태이면서 노드가 0대인 경우: 정상 0대 빈 상태로 둔갑하지 않고 즉시 에러 표출
  if (nodesState === 'error' && nodes.length === 0) {
    return (
      <section
        role="alert"
        data-testid="cluster-overview-fetch-error"
        style={{
          padding: '40px 20px',
          textAlign: 'center',
          backgroundColor: 'var(--color-bg-surface)',
          border: '1px solid #ef4444',
          borderRadius: 'var(--radius-lg)',
          margin: '20px 0',
        }}
      >
        <div style={{ fontSize: '2rem', marginBottom: '8px' }}>⚠️</div>
        <h1 style={{ fontSize: '1.25rem', fontWeight: 600, color: '#fca5a5', margin: '0 0 8px 0' }}>
          클러스터 노드 동기화 실패
        </h1>
        <p style={{ fontSize: '0.875rem', color: 'var(--color-text-muted)', margin: '0 auto 16px auto', maxWidth: '500px' }}>
          서버와 통신할 수 없어 클러스터 노드 정보를 조회하지 못했습니다 ({nodeError || '오류 발생'}). 이는 '노드 0대'(정상 0대 아님)이며, 물리 노드가 정상 가동 중일 수 있습니다.
        </p>
        {onRefresh && (
          <button
            type="button"
            data-testid="cluster-error-retry-btn"
            onClick={() => onRefresh()}
            style={{
              padding: '8px 16px',
              backgroundColor: '#ef4444',
              color: '#fff',
              border: 'none',
              borderRadius: 'var(--radius-md)',
              fontWeight: 600,
              cursor: 'pointer',
            }}
          >
            다시 시도
          </button>
        )}
      </section>
    );
  }

  // 2. 정상 조회 결과 노드가 0대인 경우 (정상 빈 클러스터)
  if (nodes.length === 0 && (nodesState === 'success' || nodesState === 'idle')) {
    return (
      <section
        role="status"
        data-testid="cluster-overview-empty-state"
        style={{
          padding: '40px 20px',
          textAlign: 'center',
          backgroundColor: 'var(--color-bg-surface)',
          borderRadius: 'var(--radius-lg)',
          border: '1px solid var(--color-border-subtle)',
          margin: '20px 0',
        }}
      >
        <h1 style={{ fontSize: '1.25rem', fontWeight: 600 }}>분산 Node 클러스터 개요</h1>
        <p style={{ color: 'var(--color-text-muted)', marginTop: '8px' }}>
          등록된 노드가 없습니다 (정상 조회 결과: 0대). 관리자 승인을 통해 노드를 온보딩하세요.
        </p>
        {lastFetchedAt && (
          <div
            data-testid="cluster-freshness-indicator"
            style={{ fontSize: '0.75rem', color: 'var(--color-text-muted)', marginTop: '12px' }}
          >
            화면 확인: {lastFetchedAt.toLocaleTimeString('ko-KR')}
          </div>
        )}
      </section>
    );
  }

  // 3. 텔레메트리 미제공/미관측 노드가 포함된 경우
  if (nodes.some(node => node.telemetryUnavailable)) {
    return (
      <section>
        {nodesState === 'error' && (
          <div
            role="alert"
            data-testid="cluster-stale-warning"
            style={{
              padding: '12px 16px',
              marginBottom: '16px',
              backgroundColor: 'rgba(239, 68, 68, 0.1)',
              border: '1px solid #ef4444',
              borderRadius: 'var(--radius-md)',
              color: '#fca5a5',
              fontSize: '0.8125rem',
            }}
          >
            ⚠️ [동기화 실패] 클러스터 노드 동기화에 실패했습니다 ({nodeError || '통신 오류'}).
            현재 표시된 노드 정보는 {lastFetchedAt ? lastFetchedAt.toLocaleTimeString('ko-KR') : '과거'} 화면 확인 시점 스냅샷입니다.
          </div>
        )}
        <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: '16px' }}>
          <h1>분산 Node 클러스터 개요</h1>
          <div style={{ display: 'flex', alignItems: 'center', gap: '8px' }}>
            <span
              role="status"
              data-testid="cluster-freshness-indicator"
              style={{
                fontSize: '0.75rem',
                color: 'var(--color-text-muted)',
                backgroundColor: 'var(--color-bg-subtle)',
                padding: '3px 8px',
                borderRadius: 'var(--radius-sm)',
                border: '1px solid var(--color-border-subtle)',
              }}
            >
              🔄 클러스터 자동 갱신 (5초 주기) · 화면 확인: {lastFetchedAt ? lastFetchedAt.toLocaleTimeString('ko-KR') : '동기화 중...'}
            </span>
            {onRefresh && (
              <button
                type="button"
                data-testid="cluster-refresh-btn"
                onClick={() => onRefresh()}
                style={{
                  fontSize: '0.75rem',
                  padding: '3px 8px',
                  backgroundColor: 'var(--color-bg-surface)',
                  border: '1px solid var(--color-border-subtle)',
                  borderRadius: 'var(--radius-sm)',
                  cursor: 'pointer',
                  color: 'var(--color-text-secondary)',
                }}
              >
                새로고침
              </button>
            )}
          </div>
        </div>
        <ul>
          {nodes.map(node => (
            <li key={node.id} data-testid={`node-item-${node.id}`}>
              {node.hostname} — {node.telemetryUnavailable ? '자원 미관측' : '자원 관측됨'}
              <span data-testid={`node-heartbeat-${node.id}`} style={{ fontSize: '0.6875rem', color: '#64748b', marginLeft: '8px' }}>
                마지막 하트비트: {node.heartbeatAt ? new Date(node.heartbeatAt).toLocaleTimeString('ko-KR') : '미관측 (Heartbeat Absent)'}
              </span>
            </li>
          ))}
        </ul>
        <p>표시된 노드 {nodes.length}대 · 활성 실행 {runs.filter(run => run.state === 'running').length}건</p>
      </section>
    );
  }
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
      {/* Stale Warning Banner when polling failed with cached nodes */}
      {nodesState === 'error' && (
        <div
          role="alert"
          data-testid="cluster-stale-warning"
          style={{
            padding: '12px 16px',
            marginBottom: '16px',
            backgroundColor: 'rgba(239, 68, 68, 0.1)',
            border: '1px solid #ef4444',
            borderRadius: 'var(--radius-md)',
            color: '#fca5a5',
            fontSize: '0.8125rem',
          }}
        >
          ⚠️ [동기화 실패] 클러스터 노드 동기화에 실패했습니다 ({nodeError || '통신 오류'}).
          현재 표시된 노드 정보는 {lastFetchedAt ? lastFetchedAt.toLocaleTimeString('ko-KR') : '과거'} 화면 확인 시점 스냅샷입니다.
        </div>
      )}

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
          <div style={{ display: 'flex', alignItems: 'center', gap: '12px', marginBottom: '4px' }}>
            <h1 style={{ fontSize: '1.375rem', fontWeight: 700, margin: 0 }}>분산 Node 클러스터 개요</h1>
            <span
              role="status"
              data-testid="cluster-freshness-indicator"
              style={{
                fontSize: '0.75rem',
                color: 'var(--color-text-muted)',
                backgroundColor: 'var(--color-bg-subtle)',
                padding: '2px 8px',
                borderRadius: 'var(--radius-sm)',
                border: '1px solid var(--color-border-subtle)',
              }}
            >
              🔄 자동 갱신 (5초 주기) · 화면 확인: {lastFetchedAt ? lastFetchedAt.toLocaleTimeString('ko-KR') : '동기화 중...'}
            </span>
            {onRefresh && (
              <button
                type="button"
                data-testid="cluster-refresh-btn"
                onClick={() => onRefresh()}
                style={{
                  fontSize: '0.75rem',
                  padding: '2px 8px',
                  backgroundColor: 'transparent',
                  border: '1px solid var(--color-border-subtle)',
                  borderRadius: 'var(--radius-sm)',
                  cursor: 'pointer',
                  color: 'var(--color-text-secondary)',
                }}
              >
                새로고침
              </button>
            )}
          </div>
          <p style={{ fontSize: '0.875rem', color: 'var(--color-text-muted)', margin: 0 }}>
            관측된 노드 (온라인 {onlineNodes}/{nodes.length}대, 활성 실행 {runningRuns}건)
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
                    {(node.os ? node.os.toUpperCase() : 'LINUX')} · {node.cpuCores}C / {Math.round(node.memoryTotalBytes / 1024 ** 3)}G
                    {node.gpuCount > 0 && ` · ${node.gpuName}`}
                    <div data-testid={`node-heartbeat-${node.id}`} style={{ fontSize: '0.6875rem', color: '#64748b', marginTop: '2px' }}>
                      마지막 하트비트: {node.heartbeatAt ? new Date(node.heartbeatAt).toLocaleTimeString('ko-KR') : '미관측 (Heartbeat Absent)'}
                    </div>
                  </div>
                </div>

                <span
                  style={{
                    fontSize: '0.75rem',
                    fontWeight: 600,
                    color:
                      node.status === 'online'
                        ? 'var(--color-status-online)'
                        : node.status === 'active'
                        ? '#38bdf8'
                        : node.status === 'degraded' || node.status === 'unknown'
                        ? '#d29922'
                        : 'var(--color-status-offline)',
                  }}
                >
                  ● {node.status === 'lost' ? 'LOST (단절)' : node.status === 'unknown' ? 'UNKNOWN (미확인)' : node.status === 'active' ? 'ACTIVE (활성 · 헬스 미결정)' : node.status.toUpperCase()}
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
