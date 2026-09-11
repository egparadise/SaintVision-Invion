import React from 'react';
import { NodeItem } from '@/contracts/types';
import { Button } from '@/shared/ui/Button';

export interface NodeDetailProps {
  node: NodeItem;
  onBack: () => void;
  onOpenStudio?: (nodeId: string) => void;
}

export const NodeDetail: React.FC<NodeDetailProps> = ({ node, onBack, onOpenStudio }) => {
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
              <strong>{node.os === 'windows' ? 'Windows 11 Pro 64-bit' : 'Ubuntu 24.04 LTS'}</strong>
            </div>

            <div style={{ display: 'flex', justifyContent: 'space-between', borderBottom: '1px solid var(--color-border-subtle)', paddingBottom: '8px' }}>
              <span style={{ color: 'var(--color-text-muted)' }}>CPU 모델 및 코어:</span>
              <strong>AMD/Intel x86_64 ({node.cpuCores} 코어)</strong>
            </div>

            <div style={{ display: 'flex', justifyContent: 'space-between', borderBottom: '1px solid var(--color-border-subtle)', paddingBottom: '8px' }}>
              <span style={{ color: 'var(--color-text-muted)' }}>물리 RAM 용량:</span>
              <strong>{(node.memoryTotalBytes / 1024 ** 3).toFixed(1)} GiB</strong>
            </div>

            {node.gpuCount > 0 && (
              <div style={{ display: 'flex', justifyContent: 'space-between', borderBottom: '1px solid var(--color-border-subtle)', paddingBottom: '8px' }}>
                <span style={{ color: 'var(--color-text-muted)' }}>가속 GPU & VRAM:</span>
                <strong>{node.gpuName} ({node.gpuCount}대, {(node.gpuVramTotalBytes! / 1024 ** 3).toFixed(1)} GiB)</strong>
              </div>
            )}

            <div style={{ display: 'flex', justifyContent: 'space-between', paddingBottom: '8px' }}>
              <span style={{ color: 'var(--color-text-muted)' }}>로컬 스토리지 제공량:</span>
              <strong>{(node.storageTotalBytes / 1024 ** 3).toFixed(1)} GiB</strong>
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
                {node.cpuCores}C / {(node.memoryTotalBytes / 1024 ** 3).toFixed(0)}GB
              </div>
            </div>
            <div style={{ padding: '10px', backgroundColor: 'var(--color-bg-subtle)', borderRadius: 'var(--radius-sm)', fontSize: '0.75rem' }}>
              <div style={{ color: 'var(--color-text-muted)', marginBottom: '2px' }}>관측 사용량</div>
              <div style={{ fontWeight: 700, fontSize: '0.875rem', color: '#58a6ff' }}>
                {node.cpuUsagePercent}% / {(node.memoryUsedBytes / 1024 ** 3).toFixed(1)}GB
              </div>
            </div>
            <div style={{ padding: '10px', backgroundColor: 'var(--color-bg-subtle)', borderRadius: 'var(--radius-sm)', fontSize: '0.75rem' }}>
              <div style={{ color: 'var(--color-text-muted)', marginBottom: '2px' }}>관측 여유량 (Headroom)</div>
              <div style={{ fontWeight: 700, fontSize: '0.875rem', color: '#3fb950' }}>
                {(node.cpuCores * (1 - node.cpuUsagePercent / 100)).toFixed(1)}C / {((node.memoryTotalBytes - node.memoryUsedBytes) / 1024 ** 3).toFixed(1)}GB
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
              <div style={{ fontWeight: 800, fontSize: '0.875rem', color: node.observationOnly ? '#d29922' : '#3fb950' }}>
                {node.observationOnly
                  ? '0C (차단)'
                  : `${(node.cpuCores * (1 - node.cpuUsagePercent / 100)).toFixed(1)}C / ${((node.memoryTotalBytes - node.memoryUsedBytes) / 1024 ** 3).toFixed(1)}GB`}
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
            <div><strong>현재 할당된 Workspace:</strong> {node.observationOnly ? '없음 (배치 차단)' : 'wsp_01JABCDE (wsp-saint-pilot)'}</div>
            <div><strong>점유 CPU / RAM:</strong> {node.observationOnly ? '0 코어 / 0 GiB' : '4 코어 / 8 GiB'}</div>
            {node.gpuCount > 0 && <div><strong>점유 GPU VRAM:</strong> 6 GiB (Lease ID: lse_01JABCDEF_01)</div>}
            <div style={{ marginTop: '8px', color: 'var(--color-text-muted)' }}>
              Lease 만료 시각: 2026-09-09 18:30:00 KST (자동 갱신 Heartbeat 가동 중)
            </div>
          </div>

          <h4 style={{ fontSize: '0.9375rem', fontWeight: 600, marginTop: '20px', marginBottom: '10px' }}>
            최근 하트비트 스냅샷 타임라인
          </h4>
          <div style={{ fontSize: '0.75rem', color: 'var(--color-text-muted)', fontFamily: 'monospace' }}>
            <div>[17:40:15] Heartbeat OK - CPU 24% | RAM 43% | GPU 33% (정상 수신)</div>
            <div>[17:40:00] Heartbeat OK - CPU 22% | RAM 43% | GPU 33% (정상 수신)</div>
            <div>[17:39:45] Heartbeat OK - CPU 25% | RAM 42% | GPU 32% (정상 수신)</div>
          </div>
        </div>
      </div>
    </div>
  );
};
