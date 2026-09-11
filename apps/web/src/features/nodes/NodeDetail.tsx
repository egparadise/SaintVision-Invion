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
        </div>
        {onOpenStudio && (
          <Button variant="primary" size="sm" onClick={() => onOpenStudio(node.id)}>
            ⚡ 이 노드에서 Studio 열기
          </Button>
        )}
      </div>

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
          <h3 style={{ fontSize: '1.0625rem', fontWeight: 600, marginBottom: '16px' }}>활성 자원 Lease & 예약</h3>
          <div
            style={{
              padding: '16px',
              backgroundColor: 'var(--color-bg-subtle)',
              borderRadius: 'var(--radius-md)',
              fontSize: '0.8125rem',
              lineHeight: 1.6,
            }}
          >
            <div><strong>현재 할당된 Workspace:</strong> wsp_01JABCDE (wsp-saint-pilot)</div>
            <div><strong>점유 CPU / RAM:</strong> 4 코어 / 8 GiB</div>
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
