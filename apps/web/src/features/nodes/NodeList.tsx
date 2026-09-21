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
  onOpenStudio?: (nodeId: string) => void;
}

export const NodeList: React.FC<NodeListProps> = ({
  nodes,
  isLoading,
  error,
  isForbidden = false,
  onRefresh,
  onSelectNode,
  onOpenStudio,
}) => {
  const [showInstallGuide, setShowInstallGuide] = React.useState(false);
  const [copiedGuide, setCopiedGuide] = React.useState(false);

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
              display: 'flex',
              flexDirection: 'column',
              gap: '12px',
            }}
          >
            <Skeleton width="60%" height="1.25rem" />
            <Skeleton width="40%" height="0.875rem" />
            <Skeleton width="80%" height="1rem" />
            <Skeleton width="90%" height="0.75rem" />
          </div>
        ))}
      </div>
    );
  }

  // State 4: Empty
  if (nodes.length === 0) {
    return (
      <div style={{ display: 'flex', flexDirection: 'column', gap: '16px' }}>
        <EmptyState
          title="등록된 Node가 없습니다"
          description="SaintVision Agent 데몬을 PC에 실행하여 클러스터에 합류시키십시오. 아래 설치 안내를 확인하세요."
          icon="🖥️"
          actionLabel={showInstallGuide ? '설치 가이드 접기' : 'Node Agent 설치 안내'}
          onAction={() => setShowInstallGuide((prev) => !prev)}
        />
        {showInstallGuide && (
          <div
            role="status"
            data-testid="node-agent-install-guide"
            style={{
              padding: '16px 20px',
              backgroundColor: 'var(--color-bg-surface)',
              borderRadius: 'var(--radius-lg)',
              border: '1px solid var(--color-border-subtle)',
              maxWidth: '600px',
              margin: '0 auto',
              width: '100%',
              boxSizing: 'border-box',
            }}
          >
            <h4 style={{ margin: '0 0 8px 0', fontSize: '1rem', fontWeight: 600 }}>
              Node Agent 데몬 부트스트랩 가이드
            </h4>
            <p style={{ margin: '0 0 12px 0', fontSize: '0.875rem', color: 'var(--color-text-muted)' }}>
              터미널에서 아래 명령을 실행하여 현재 시스템을 클러스터 작업 노드로 등록하십시오:
            </p>
            <div style={{ display: 'flex', alignItems: 'center', gap: '8px' }}>
              <code
                style={{
                  flex: 1,
                  padding: '8px 12px',
                  backgroundColor: 'var(--color-bg-code, #1e1e1e)',
                  color: '#4ade80',
                  borderRadius: '4px',
                  fontSize: '0.875rem',
                  fontFamily: 'monospace',
                }}
              >
                python -m saintvision.agent --bootstrap
              </code>
              <button
                type="button"
                data-testid="copy-agent-bootstrap-btn"
                onClick={() => {
                  if (typeof navigator !== 'undefined' && navigator.clipboard) {
                    navigator.clipboard.writeText('python -m saintvision.agent --bootstrap');
                  }
                  setCopiedGuide(true);
                  setTimeout(() => setCopiedGuide(false), 3000);
                }}
                style={{
                  padding: '8px 12px',
                  backgroundColor: 'var(--color-bg-surface-hover, #2d3748)',
                  color: 'var(--color-text-primary, #fff)',
                  border: '1px solid var(--color-border-subtle)',
                  borderRadius: '4px',
                  cursor: 'pointer',
                  fontSize: '0.8125rem',
                  whiteSpace: 'nowrap',
                }}
              >
                {copiedGuide ? '✓ 복사됨' : '📋 명령어 복사'}
              </button>
            </div>
            {copiedGuide && (
              <span
                role="status"
                data-testid="node-agent-copy-feedback"
                style={{ display: 'block', marginTop: '8px', fontSize: '0.75rem', color: '#4ade80' }}
              >
                설치 명령어가 클립보드에 복사되었습니다.
              </span>
            )}
          </div>
        )}
      </div>
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
          if (node.telemetryUnavailable) return (
            <div
              key={node.id}
              role={node.status === 'lost' ? 'alert' : 'status'}
              data-testid={`node-card-${node.id}`}
              style={{
                padding: '20px',
                backgroundColor: 'var(--color-bg-surface)',
                borderRadius: 'var(--radius-lg)',
                border: `1px solid ${node.status === 'lost' ? '#ef4444' : node.status === 'unknown' ? '#f59e0b' : 'var(--color-border-subtle)'}`,
                boxShadow: 'var(--shadow-sm)',
              }}
            >
              <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'flex-start', marginBottom: '8px' }}>
                <div>
                  <h3 style={{ fontSize: '1rem', fontWeight: 600 }}>{node.hostname}</h3>
                  <span style={{ fontSize: '0.75rem', color: 'var(--color-text-muted)', fontFamily: 'monospace' }}>
                    {node.id} · {node.os.toUpperCase()}
                  </span>
                </div>
                <span
                  data-testid={`node-status-badge-${node.id}`}
                  style={{
                    display: 'inline-flex',
                    alignItems: 'center',
                    gap: '4px',
                    padding: '2px 8px',
                    borderRadius: 'var(--radius-sm)',
                    fontSize: '0.75rem',
                    fontWeight: 600,
                    color: node.status === 'lost' ? '#f85149' : node.status === 'unknown' ? '#d29922' : node.status === 'active' ? '#38bdf8' : 'var(--color-text-muted)',
                    backgroundColor: 'var(--color-bg-subtle)',
                    border: `1px solid ${node.status === 'lost' ? '#f85149' : node.status === 'unknown' ? '#d29922' : node.status === 'active' ? '#38bdf8' : 'var(--color-border-subtle)'}`,
                  }}
                >
                  <span style={{
                    width: '6px',
                    height: '6px',
                    borderRadius: '50%',
                    backgroundColor: node.status === 'lost' ? '#f85149' : node.status === 'unknown' ? '#d29922' : node.status === 'active' ? '#38bdf8' : 'var(--color-text-muted)',
                  }} />
                  {node.status === 'lost' ? 'LOST (단절)' : node.status === 'unknown' ? 'UNKNOWN (미확인)' : node.status === 'active' ? 'ACTIVE (활성 · 헬스 미결정)' : node.status.toUpperCase()}
                </span>
              </div>
              <p style={{ margin: 0, fontSize: '0.8125rem', color: node.status === 'lost' ? '#fca5a5' : node.status === 'unknown' ? '#fde68a' : node.status === 'active' ? '#7dd3fc' : 'var(--color-text-muted)', lineHeight: 1.4 }}>
                {node.status === 'lost'
                  ? '🔴 노드와의 통신이 두절되어 상태가 유실(Lost)되었습니다. 제어 평면 연결이 끊어졌으므로 즉시 인프라 점검이 필요합니다.'
                  : node.status === 'unknown'
                  ? '⚠️ 서버에서 관측된 노드 상태를 화면에서 해석할 수 없습니다 (미확인 상태 · 조용한 합류 둔갑 차단).'
                  : node.status === 'active'
                  ? 'ℹ️ 계약 상태: active (정상 가동 노드 · liveness 및 헬스 초록 표기 정책은 사용자 결정 대기 중).'
                  : '자원 정보 미관측 · 실행 대상에서 제외'}
              </p>
            </div>
          );

          const statusColor =
            node.status === 'online'
              ? 'var(--color-status-online)'
              : node.status === 'active'
              ? '#38bdf8'
              : node.status === 'degraded'
              ? 'var(--color-status-degraded)'
              : node.status === 'lost'
              ? '#f85149'
              : node.status === 'unknown'
              ? '#d29922'
              : 'var(--color-status-offline)';

          const ramUsedGb = (node.memoryUsedBytes / (1024 ** 3)).toFixed(1);
          const ramTotalGb = (node.memoryTotalBytes / (1024 ** 3)).toFixed(1);
          const storageUsedGb = (node.storageUsedBytes / (1024 ** 3)).toFixed(1);
          const storageTotalGb = (node.storageTotalBytes / (1024 ** 3)).toFixed(1);

          return (
            <div
              key={node.id}
              data-testid={`node-card-${node.id}`}
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
                  data-testid={`node-status-badge-${node.id}`}
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
                  {node.status === 'lost' ? 'LOST (단절)' : node.status === 'unknown' ? 'UNKNOWN (미확인)' : node.status === 'active' ? 'ACTIVE (활성 · 헬스 미결정)' : node.status.toUpperCase()}
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

              {/* Observation-Only and Schedulable Capacity */}
              {node.observationOnly && (
                <div
                  style={{
                    marginTop: '8px',
                    padding: '4px 8px',
                    borderRadius: 'var(--radius-sm)',
                    backgroundColor: 'rgba(210, 153, 34, 0.15)',
                    border: '1px solid #d29922',
                    color: '#d29922',
                    fontSize: '0.6875rem',
                    fontWeight: 600,
                  }}
                >
                  ⚠️ 관측 전용 (192.168.45.225 - 원격 프로필 미설치)
                </div>
              )}

              {node.status === 'active' && (
                <div
                  role="status"
                  data-testid={`node-active-status-notice-${node.id}`}
                  style={{
                    marginTop: '8px',
                    padding: '4px 8px',
                    borderRadius: 'var(--radius-sm)',
                    backgroundColor: 'rgba(56, 189, 248, 0.12)',
                    border: '1px solid rgba(56, 189, 248, 0.3)',
                    color: '#38bdf8',
                    fontSize: '0.6875rem',
                    fontWeight: 500,
                  }}
                >
                  ℹ️ 계약 상태: active (정상 가동 노드 · liveness 및 헬스 초록 표기 정책은 사용자 결정 대기 중)
                </div>
              )}

              {/* Resource Headroom & Studio Jump Action */}
              <div
                style={{
                  marginTop: '14px',
                  paddingTop: '10px',
                  borderTop: '1px solid var(--color-border-subtle)',
                  display: 'flex',
                  justifyContent: 'space-between',
                  alignItems: 'center',
                }}
              >
                <div style={{ fontSize: '0.75rem', display: 'flex', flexDirection: 'column', gap: '2px' }}>
                  <span style={{ color: 'var(--color-text-muted)' }}>
                    관측여유: {(node.cpuCores * (1 - node.cpuUsagePercent / 100)).toFixed(1)}C · {((node.memoryTotalBytes - node.memoryUsedBytes) / 1024 ** 3).toFixed(1)}G
                  </span>
                  <span style={{ fontWeight: 700, color: node.observationOnly ? '#d29922' : (node.allocatableCores !== undefined ? '#3fb950' : 'var(--color-text-muted)') }}>
                    예약가능: {node.observationOnly ? '0C (차단)' : (node.allocatableCores !== undefined ? `${node.allocatableCores}C` : '미확인 (선택 불가)')}
                  </span>
                </div>
                {onOpenStudio && (
                  <button
                    onClick={(e) => {
                      e.stopPropagation();
                      onOpenStudio(node.id);
                    }}
                    title={node.observationOnly ? '관측 전용 노드는 업무 배치가 비활성화되어 있습니다' : '이 노드로 Studio 열기'}
                    style={{
                      padding: '4px 10px',
                      fontSize: '0.75rem',
                      fontWeight: 600,
                      borderRadius: 'var(--radius-sm)',
                      backgroundColor: node.observationOnly ? 'var(--color-border-strong)' : 'var(--color-brand-primary)',
                      color: '#ffffff',
                      border: 'none',
                      cursor: 'pointer',
                    }}
                  >
                    ⚡ Studio 열기
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
