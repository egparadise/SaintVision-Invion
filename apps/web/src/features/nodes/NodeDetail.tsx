import React from 'react';
import { NodeItem } from '@/contracts/types';
import { Button } from '@/shared/ui/Button';
import type { ObservedNodeResourceUsage } from '@/contracts/kernel-observation';

export interface NodeDetailProps {
  node: NodeItem;
  resourceUsage?: ObservedNodeResourceUsage | null;
  resourceUsageState?: 'idle' | 'unselected' | 'loading' | 'success' | 'error';
  resourceUsageError?: string | null;
  onBack: () => void;
  onOpenStudio?: (nodeId: string) => void;
}

export const NodeDetail: React.FC<NodeDetailProps> = ({
  node,
  resourceUsage,
  resourceUsageState,
  resourceUsageError,
  onBack,
  onOpenStudio,
}) => {
  const hasTelemetry =
    !node.telemetryUnavailable &&
    typeof node.cpuUsagePercent === 'number' &&
    Number.isFinite(node.cpuUsagePercent) &&
    typeof node.memoryUsedBytes === 'number' &&
    Number.isFinite(node.memoryUsedBytes);

  const cpuCoresDisplay =
    typeof node.cpuCores === 'number' && Number.isFinite(node.cpuCores)
      ? `${node.cpuCores} 코어`
      : '미관측';
  const memoryDisplay =
    typeof node.memoryTotalBytes === 'number' && Number.isFinite(node.memoryTotalBytes)
      ? `${(node.memoryTotalBytes / 1024 ** 3).toFixed(1)} GiB`
      : '미관측';
  const storageDisplay =
    typeof node.storageTotalBytes === 'number' && Number.isFinite(node.storageTotalBytes)
      ? `${(node.storageTotalBytes / 1024 ** 3).toFixed(1)} GiB`
      : '미관측';
  const totalPhysicalDisplay =
    typeof node.cpuCores === 'number' &&
    Number.isFinite(node.cpuCores) &&
    typeof node.memoryTotalBytes === 'number' &&
    Number.isFinite(node.memoryTotalBytes)
      ? `${node.cpuCores}C / ${(node.memoryTotalBytes / 1024 ** 3).toFixed(0)}GB`
      : '미관측';

  return (
    <div>
      <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', marginBottom: '24px' }}>
        <div style={{ display: 'flex', alignItems: 'center', gap: '16px' }}>
          <Button variant="ghost" size="sm" onClick={onBack}>
            ← 인벤토리로 돌아가기
          </Button>
          <h2 style={{ fontSize: '1.25rem', fontWeight: 600 }}>
            Node 상세 정보: <code>{node.hostname}</code> ({node.id})
          </h2>
          {node.ipAddress && (
            <span
              style={{
                fontSize: '0.75rem',
                fontFamily: 'monospace',
                backgroundColor: 'var(--color-bg-subtle)',
                padding: '2px 8px',
                borderRadius: 'var(--radius-sm)',
                border: '1px solid var(--color-border-subtle)',
              }}
            >
              IP: {node.ipAddress}
            </span>
          )}
        </div>
        {onOpenStudio && (
          <Button
            variant={node.observationOnly ? 'secondary' : 'primary'}
            size="sm"
            onClick={() => {
              if (!node.observationOnly) {
                onOpenStudio(node.id);
              }
            }}
            disabled={node.observationOnly}
            title={
              node.observationOnly
                ? '관측 전용 노드는 원격 실행 프로필이 미설치되어 Studio 배치가 비활성화되어 있습니다.'
                : '이 노드로 Studio 열기'
            }
          >
            {node.observationOnly ? '⚠️ 관측 전용 (Studio 배치 차단)' : '⚡ 이 노드에서 Studio 열기'}
          </Button>
        )}
      </div>

      {/* Observation-Only Alert Callout */}
      {node.observationOnly && (
        <div
          style={{
            marginBottom: '20px',
            padding: '16px 20px',
            backgroundColor: 'rgba(210, 153, 34, 0.12)',
            borderRadius: 'var(--radius-lg)',
            border: '1px solid #d29922',
            color: '#d29922',
          }}
        >
          <div style={{ display: 'flex', alignItems: 'center', gap: '8px', fontWeight: 700, fontSize: '0.9375rem' }}>
            <span>⚠️ 관측 전용 노드 (Observation-Only Node - {node.ipAddress || '192.168.45.225'})</span>
          </div>
          <p style={{ fontSize: '0.8125rem', marginTop: '6px', color: 'var(--color-text-primary)', lineHeight: 1.5 }}>
            이 노드는 mTLS 텔레메트리 관측 및 모니터링 전용으로 연결되어 있습니다. 원격 실행 프로필(Remote Execution Profile)이 설치되지 않아
            업무 배치(Workload Scheduling) 및 컨테이너 작업 제출이 거부됩니다. 스케줄링 예약 가능량은 <strong>0 코어 (차단)</strong>로 고정됩니다.
          </p>
        </div>
      )}

      {/* Telemetry Unavailable Banner */}
      {node.telemetryUnavailable && (
        <div
          data-testid="node-telemetry-unavailable-banner"
          role="status"
          style={{
            marginBottom: '20px',
            padding: '14px 18px',
            backgroundColor: 'var(--color-bg-subtle)',
            borderRadius: 'var(--radius-lg)',
            border: '1px solid var(--color-border-subtle)',
            color: 'var(--color-text-secondary)',
            fontSize: '0.875rem',
            lineHeight: 1.5,
          }}
        >
          <div style={{ display: 'flex', alignItems: 'center', gap: '8px', fontWeight: 600, color: 'var(--color-text-primary)' }}>
            <span>ℹ️ 동적 텔레메트리 미관측 상태</span>
          </div>
          <p style={{ marginTop: '4px', marginBottom: 0 }}>
            자원 정보가 미관측 상태입니다. 동적 텔레메트리(CPU/메모리 실시간 사용률)가 수집되지 않는 환경에서는 정적 사양 및 커널 자원 할당 상태를 표시합니다.
          </p>
        </div>
      )}

      {/* Capability Resource Usage Guidance & Tri-state */}
      {resourceUsageState === 'unselected' && (
        <div
          data-testid="node-resource-usage-unselected-notice"
          role="status"
          style={{
            marginBottom: '20px',
            padding: '16px 20px',
            backgroundColor: 'var(--color-bg-subtle)',
            borderRadius: 'var(--radius-md)',
            border: '1px solid var(--color-border-subtle)',
            color: 'var(--color-text-muted)',
            fontSize: '0.875rem',
          }}
        >
          <strong>프로젝트 미선택 안내:</strong> 노드 자원 할당 사용량(Capability Resource Usage)은 프로젝트 단위로 격리되어 제공됩니다. 상단에서 프로젝트를 선택하시면 커널 자원 할당 상태를 조회할 수 있습니다.
        </div>
      )}

      {resourceUsageState === 'loading' && (
        <div
          data-testid="node-resource-usage-loading"
          role="status"
          style={{
            marginBottom: '20px',
            padding: '16px 20px',
            backgroundColor: 'var(--color-bg-subtle)',
            borderRadius: 'var(--radius-md)',
            border: '1px solid var(--color-border-subtle)',
            color: 'var(--color-text-muted)',
            fontSize: '0.875rem',
          }}
        >
          커널 자원 할당 사용량 조회 중...
        </div>
      )}

      {(resourceUsageState === 'error' || Boolean(resourceUsageError)) && (
        <div
          data-testid="node-resource-usage-error"
          role="alert"
          style={{
            marginBottom: '20px',
            padding: '16px 20px',
            backgroundColor: 'rgba(248, 81, 73, 0.1)',
            borderRadius: 'var(--radius-md)',
            border: '1px solid #f85149',
            color: '#f85149',
            fontSize: '0.875rem',
          }}
        >
          <strong>자원 사용량 조회 실패:</strong> {resourceUsageError || '노드 자원 사용량(Capability Resource Usage)을 불러올 수 없습니다.'}
        </div>
      )}

      {/* Capability Resource Usage Panel */}
      {resourceUsage && (
        <div
          data-testid="capability-resource-usage-panel"
          style={{
            marginBottom: '20px',
            padding: '24px',
            backgroundColor: 'var(--color-bg-surface)',
            borderRadius: 'var(--radius-lg)',
            border: '1px solid var(--color-border-subtle)',
          }}
        >
          <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', marginBottom: '16px', flexWrap: 'wrap', gap: '8px' }}>
            <h3 style={{ fontSize: '1.0625rem', fontWeight: 600, margin: 0 }}>
              커널 자원 할당 사용량 (Capability Resource Usage)
            </h3>
            <div style={{ fontSize: '0.8125rem', color: 'var(--color-text-muted)' }}>
              기준 시각: <strong>{resourceUsage.stateAsOf ?? '미기록'}</strong>
              <span style={{ fontSize: '0.75rem', color: 'var(--color-text-muted)', marginLeft: '6px' }}>
                (실시간 캡처나 화면 갱신 시각이 아닙니다)
              </span>
            </div>
          </div>
          <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fit, minmax(280px, 1fr))', gap: '16px' }}>
            {resourceUsage.resources.map((res) => (
              <div
                key={res.resourceId}
                data-testid={`resource-usage-card-${res.kind}`}
                style={{
                  padding: '16px',
                  backgroundColor: 'var(--color-bg-subtle)',
                  borderRadius: 'var(--radius-md)',
                  border: '1px solid var(--color-border-subtle)',
                  display: 'flex',
                  flexDirection: 'column',
                  gap: '8px',
                  fontSize: '0.8125rem',
                }}
              >
                <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between' }}>
                  <strong style={{ textTransform: 'uppercase', color: 'var(--color-text-primary)' }}>
                    {res.kind} ({res.unit})
                  </strong>
                  <span
                    data-testid={`resource-measured-badge-${res.kind}`}
                    style={{
                      fontSize: '0.6875rem',
                      padding: '2px 6px',
                      borderRadius: 'var(--radius-sm)',
                      fontWeight: 600,
                      backgroundColor: res.measured ? 'rgba(46, 160, 67, 0.15)' : 'rgba(110, 118, 129, 0.2)',
                      color: res.measured ? '#3fb950' : 'var(--color-text-muted)',
                      border: `1px solid ${res.measured ? '#2ea043' : 'var(--color-border-subtle)'}`,
                    }}
                  >
                    {res.measured ? '측정됨 (Measured)' : '미측정 (Unmeasured)'}
                  </span>
                </div>
                <div style={{ display: 'grid', gridTemplateColumns: 'repeat(2, 1fr)', gap: '8px', marginTop: '4px' }}>
                  <div>
                    <span style={{ color: 'var(--color-text-muted)' }}>총 용량 (Capacity):</span>{' '}
                    <strong>{res.capacity !== null ? res.capacity.toLocaleString('ko-KR') : '미측정'}</strong>
                  </div>
                  <div>
                    <span style={{ color: 'var(--color-text-muted)' }}>제공량 (Offered):</span>{' '}
                    <strong>{res.offered !== null ? res.offered.toLocaleString('ko-KR') : '미측정'}</strong>
                  </div>
                  <div>
                    <span style={{ color: 'var(--color-text-muted)' }}>예약 할당 (Reserved):</span>{' '}
                    <strong style={{ color: res.reserved !== null ? '#58a6ff' : 'var(--color-text-muted)' }}>
                      {res.reserved !== null ? res.reserved.toLocaleString('ko-KR') : '미측정'}
                    </strong>
                  </div>
                  <div>
                    <span style={{ color: 'var(--color-text-muted)' }}>가용 잔여 (Spare):</span>{' '}
                    <strong style={{ color: res.spare !== null ? '#3fb950' : 'var(--color-text-muted)' }}>
                      {res.spare !== null ? res.spare.toLocaleString('ko-KR') : '미측정'}
                    </strong>
                  </div>
                </div>
                {res.observedAt && (
                  <div style={{ fontSize: '0.75rem', color: 'var(--color-text-muted)', marginTop: '4px' }}>
                    관측 시각: {res.observedAt}
                  </div>
                )}
              </div>
            ))}
          </div>
        </div>
      )}

      <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fit, minmax(320px, 1fr))', gap: '20px' }}>
        {/* Hardware Capability Panel */}
        <div
          style={{
            padding: '24px',
            backgroundColor: 'var(--color-bg-surface)',
            borderRadius: 'var(--radius-lg)',
            border: '1px solid var(--color-border-subtle)',
          }}
        >
          <h3 style={{ fontSize: '1.0625rem', fontWeight: 600, marginBottom: '16px' }}>하드웨어 Capability</h3>
          <div style={{ display: 'flex', flexDirection: 'column', gap: '12px', fontSize: '0.875rem' }}>
            <div style={{ display: 'flex', justifyContent: 'space-between', borderBottom: '1px solid var(--color-border-subtle)', paddingBottom: '8px' }}>
              <span style={{ color: 'var(--color-text-muted)' }}>운영체제:</span>
              <strong>{node.os ? node.os.toUpperCase() : '알 수 없음'}</strong>
            </div>

            <div style={{ display: 'flex', justifyContent: 'space-between', borderBottom: '1px solid var(--color-border-subtle)', paddingBottom: '8px' }}>
              <span style={{ color: 'var(--color-text-muted)' }}>CPU 아키텍처 및 물리 코어:</span>
              <strong>x86_64 ({cpuCoresDisplay})</strong>
            </div>

            <div style={{ display: 'flex', justifyContent: 'space-between', borderBottom: '1px solid var(--color-border-subtle)', paddingBottom: '8px' }}>
              <span style={{ color: 'var(--color-text-muted)' }}>물리 RAM 용량:</span>
              <strong>{memoryDisplay}</strong>
            </div>

            {node.gpuCount > 0 && (
              <div style={{ display: 'flex', justifyContent: 'space-between', borderBottom: '1px solid var(--color-border-subtle)', paddingBottom: '8px' }}>
                <span style={{ color: 'var(--color-text-muted)' }}>가속 GPU & VRAM:</span>
                <strong>{node.gpuName || 'GPU'} ({node.gpuCount}대{typeof node.gpuVramTotalBytes === 'number' && Number.isFinite(node.gpuVramTotalBytes) ? `, ${(node.gpuVramTotalBytes / 1024 ** 3).toFixed(1)} GiB` : ''})</strong>
              </div>
            )}

            <div style={{ display: 'flex', justifyContent: 'space-between', paddingBottom: '8px' }}>
              <span style={{ color: 'var(--color-text-muted)' }}>로컬 스토리지 제공량:</span>
              <strong>{storageDisplay}</strong>
            </div>
          </div>
        </div>

        {/* Active Lease & Allocations Panel */}
        <div
          style={{
            padding: '24px',
            backgroundColor: 'var(--color-bg-surface)',
            borderRadius: 'var(--radius-lg)',
            border: '1px solid var(--color-border-subtle)',
          }}
        >
          <h3 style={{ fontSize: '1.0625rem', fontWeight: 600, marginBottom: '16px' }}>활성 자원 Lease & 스케줄링 용량</h3>
          
          {/* 4-Tier Resource Capacity Breakdown */}
          <div
            style={{
              display: 'grid',
              gridTemplateColumns: 'repeat(2, 1fr)',
              gap: '10px',
              marginBottom: '16px',
            }}
          >
            <div style={{ padding: '10px', backgroundColor: 'var(--color-bg-subtle)', borderRadius: 'var(--radius-sm)', fontSize: '0.75rem' }}>
              <div style={{ color: 'var(--color-text-muted)', marginBottom: '2px' }}>총 물리 자원</div>
              <div style={{ fontWeight: 700, fontSize: '0.875rem' }}>
                {totalPhysicalDisplay}
              </div>
            </div>
            <div style={{ padding: '10px', backgroundColor: 'var(--color-bg-subtle)', borderRadius: 'var(--radius-sm)', fontSize: '0.75rem' }}>
              <div style={{ color: 'var(--color-text-muted)', marginBottom: '2px' }}>관측 사용량</div>
              <div style={{ fontWeight: 700, fontSize: '0.875rem', color: '#58a6ff' }}>
                {hasTelemetry
                  ? `${node.cpuUsagePercent}% / ${(node.memoryUsedBytes / 1024 ** 3).toFixed(1)}GB`
                  : '미측정'}
              </div>
            </div>
            <div style={{ padding: '10px', backgroundColor: 'var(--color-bg-subtle)', borderRadius: 'var(--radius-sm)', fontSize: '0.75rem' }}>
              <div style={{ color: 'var(--color-text-muted)', marginBottom: '2px' }}>관측 여유량 (Headroom)</div>
              <div style={{ fontWeight: 700, fontSize: '0.875rem', color: '#3fb950' }}>
                {hasTelemetry
                  ? `${(node.cpuCores * (1 - (node.cpuUsagePercent || 0) / 100)).toFixed(1)}C / ${(((node.memoryTotalBytes - (node.memoryUsedBytes || 0))) / 1024 ** 3).toFixed(1)}GB`
                  : '미측정'}
              </div>
            </div>
            <div
              style={{
                padding: '10px',
                backgroundColor: node.observationOnly ? 'rgba(210, 153, 34, 0.15)' : 'rgba(46, 160, 67, 0.15)',
                border: `1px solid ${node.observationOnly ? '#d29922' : '#2ea043'}`,
                borderRadius: 'var(--radius-sm)',
                fontSize: '0.75rem',
              }}
            >
              <div style={{ color: node.observationOnly ? '#d29922' : '#3fb950', marginBottom: '2px', fontWeight: 600 }}>
                예약 가능량 (Schedulable)
              </div>
              <div style={{ fontWeight: 800, fontSize: '0.875rem', color: node.observationOnly ? '#d29922' : (node.allocatableCores !== undefined ? '#3fb950' : 'var(--color-text-muted)') }}>
                {node.observationOnly
                  ? '0C (차단)'
                  : node.allocatableCores !== undefined && node.allocatableMemoryBytes !== undefined
                  ? `${node.allocatableCores}C / ${(node.allocatableMemoryBytes / 1024 ** 3).toFixed(1)}GB`
                  : '미확인 (선택 불가)'}
              </div>
            </div>
          </div>

          <div
            style={{
              padding: '16px',
              backgroundColor: 'var(--color-bg-subtle)',
              borderRadius: 'var(--radius-md)',
              fontSize: '0.8125rem',
              lineHeight: 1.6,
            }}
          >
            <div><strong>현재 할당된 Workspace:</strong> {node.observationOnly ? '없음 (원격 배치 차단)' : '미할당 (유휴 상태 대기)'}</div>
            <div><strong>실측 부하 (Observed Usage):</strong> {hasTelemetry && typeof node.cpuCores === 'number' && Number.isFinite(node.cpuCores) ? `${node.cpuUsagePercent}% (${(node.cpuCores * (node.cpuUsagePercent || 0) / 100).toFixed(1)}C) / ${((node.memoryUsedBytes / 1024 ** 3)).toFixed(1)} GiB` : '동적 텔레메트리 미관측'}</div>
            {node.gpuCount > 0 && <div><strong>GPU VRAM 사용량:</strong> {hasTelemetry && node.gpuVramUsedBytes && node.gpuVramTotalBytes ? `${((node.gpuVramUsedBytes) / (1024 ** 3)).toFixed(1)} / ${((node.gpuVramTotalBytes) / (1024 ** 3)).toFixed(1)} GiB` : '미측정'}</div>}
            <div style={{ marginTop: '8px', color: 'var(--color-text-muted)' }}>
              하트비트 수신 시각: {node.heartbeatAt ? new Date(node.heartbeatAt).toLocaleString('ko-KR') : '미기록'} {hasTelemetry ? '(실시간 텔레메트리 연동)' : '(정적 등록 상태)'}
            </div>
          </div>

          <h4 style={{ fontSize: '0.9375rem', fontWeight: 600, marginTop: '20px', marginBottom: '10px' }}>
            최근 하트비트 스냅샷 타임라인
          </h4>
          <div style={{ fontSize: '0.75rem', color: 'var(--color-text-muted)', fontFamily: 'monospace', display: 'flex', flexDirection: 'column', gap: '4px' }}>
            <div>
              [{node.heartbeatAt ? new Date(node.heartbeatAt).toLocaleTimeString() : '미기록'}]{' '}
              <span style={{
                color: node.status === 'online' ? '#3fb950' : node.status === 'active' ? '#38bdf8' : node.status === 'degraded' || node.status === 'unknown' ? '#d29922' : '#f85149',
                fontWeight: 600
              }}>
                {node.status === 'online'
                  ? 'Heartbeat OK'
                  : node.status === 'active'
                  ? 'Heartbeat ACTIVE (계약 상태 · 헬스 미결정)'
                  : node.status === 'degraded'
                  ? 'Heartbeat Warning (Degraded)'
                  : node.status === 'lost'
                  ? 'Heartbeat LOST (노드 단절)'
                  : node.status === 'unknown'
                  ? 'Heartbeat UNKNOWN (미확인 상태)'
                  : 'Heartbeat FAILED (Offline)'}
              </span>{' '}
              {hasTelemetry
                ? `- CPU ${node.cpuUsagePercent}% | RAM ${((node.memoryUsedBytes / node.memoryTotalBytes) * 100).toFixed(0)}%${node.gpuCount > 0 ? ` | GPU ${node.gpuVramUsedBytes && node.gpuVramTotalBytes ? ((node.gpuVramUsedBytes / node.gpuVramTotalBytes) * 100).toFixed(0) : 0}%` : ''} (${node.status === 'online' ? 'mTLS 텔레메트리 수신' : node.status === 'active' ? '계약 상태 active 수신' : '통신 상태 확인 필요'})`
                : `- 동적 메트릭 미측정 (${node.status === 'active' ? '계약 상태 active 수신' : '정적 등록 상태'})`}
            </div>
            <div style={{ color: 'var(--color-text-secondary)', fontSize: '0.6875rem' }}>
              • 상태: <strong>{node.status === 'lost' ? 'LOST (단절)' : node.status === 'unknown' ? 'UNKNOWN (미확인)' : node.status === 'active' ? 'ACTIVE (활성 · 헬스 미결정)' : node.status.toUpperCase()}</strong> | 하트비트 원본 시각: {node.heartbeatAt || '미기록'} | 모의 지터: 없음
            </div>
          </div>
        </div>
      </div>
    </div>
  );
};
