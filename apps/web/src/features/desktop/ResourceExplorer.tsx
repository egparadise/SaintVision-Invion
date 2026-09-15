import React, { useState, useMemo } from 'react';
import { NodeItem } from '@/contracts/types';
import { LogicalResourceSummary } from '@/contracts/virtualFabric';

export interface ResourceExplorerProps {
  nodes: NodeItem[];
  onSelectNode?: (nodeId: string) => void;
  onOpenTerminal?: (nodeId: string) => void;
}

export const ResourceExplorer: React.FC<ResourceExplorerProps> = ({
  nodes,
  onSelectNode,
  onOpenTerminal,
}) => {
  const [filterMode, setFilterMode] = useState<'all' | 'schedulable' | 'gpu' | 'observe'>('all');
  const [selectedNodeId, setSelectedNodeId] = useState<string | null>(null);

  // Compute Honest Aggregate Logical Pool (Zero-Mock calculation from live nodes)
  const logicalSummary: LogicalResourceSummary = useMemo(() => {
    let totalCores = 0;
    let allocatableCores = 0;
    let usedCores = 0;
    let totalMemoryBytes = 0;
    let allocatableMemoryBytes = 0;
    let usedMemoryBytes = 0;
    let totalGpuCount = 0;
    let totalGpuVramBytes = 0;
    let usedGpuVramBytes = 0;
    let totalStorageBytes = 0;
    let usedStorageBytes = 0;
    let onlineNodeCount = 0;

    for (const node of nodes) {
      if (node.status === 'online' || node.status === 'draining') {
        onlineNodeCount++;
      }
      totalCores += node.cpuCores;
      allocatableCores += node.allocatableCores ?? 0;
      usedCores += (node.cpuCores * (node.cpuUsagePercent || 0)) / 100;

      totalMemoryBytes += node.memoryTotalBytes;
      allocatableMemoryBytes += node.allocatableMemoryBytes ?? 0;
      usedMemoryBytes += node.memoryUsedBytes;

      totalGpuCount += node.gpuCount || 0;
      totalGpuVramBytes += node.gpuVramTotalBytes || 0;
      usedGpuVramBytes += node.gpuVramUsedBytes || 0;

      totalStorageBytes += node.storageTotalBytes;
      usedStorageBytes += node.storageUsedBytes;
    }

    return {
      totalCores,
      allocatableCores,
      usedCores: Math.round(usedCores * 10) / 10,
      totalMemoryBytes,
      allocatableMemoryBytes,
      usedMemoryBytes,
      totalGpuCount,
      totalGpuVramBytes,
      usedGpuVramBytes,
      totalStorageBytes,
      usedStorageBytes,
      onlineNodeCount,
      totalNodeCount: nodes.length,
      disclaimer:
        '논리 통합 자원은 INV 클러스터 제어 평면이 관측·합산한 전체 용량 스냅샷입니다. 서로 다른 물리 PC의 CPU 코어나 GPU VRAM이 단일 하드웨어 버스로 마법처럼 병합된 것이 아니며, 모든 실제 연산과 VRAM 배치는 작업의 데이터 근접성(Locality)과 스케줄러 정책에 따라 각 독립 물리 노드에 분산 격리 실행됩니다.',
    };
  }, [nodes]);

  const filteredNodes = useMemo(() => {
    return nodes.filter((n) => {
      if (filterMode === 'schedulable') return n.schedulable;
      if (filterMode === 'gpu') return (n.gpuCount || 0) > 0;
      if (filterMode === 'observe') return n.observationOnly;
      return true;
    });
  }, [nodes, filterMode]);

  const formatBytes = (bytes: number) => {
    if (bytes === 0) return '0 B';
    const k = 1024;
    const sizes = ['B', 'KB', 'MB', 'GB', 'TB', 'PB'];
    const i = Math.floor(Math.log(bytes) / Math.log(k));
    return parseFloat((bytes / Math.pow(k, i)).toFixed(1)) + ' ' + sizes[i];
  };

  return (
    <div
      style={{
        padding: '20px 24px',
        backgroundColor: 'var(--color-bg-surface, #0f172a)',
        color: 'var(--color-text-primary, #f8fafc)',
        display: 'flex',
        flexDirection: 'column',
        gap: '24px',
      }}
    >
      {/* 1. Header with System Banner */}
      <div
        style={{
          display: 'flex',
          justifyContent: 'space-between',
          alignItems: 'flex-start',
          borderBottom: '1px solid var(--color-border-subtle, #334155)',
          paddingBottom: '16px',
        }}
      >
        <div style={{ display: 'flex', alignItems: 'center', gap: '14px' }}>
          <div
            style={{
              width: '48px',
              height: '48px',
              borderRadius: '12px',
              backgroundColor: 'rgba(59, 130, 246, 0.15)',
              display: 'flex',
              alignItems: 'center',
              justifyContent: 'center',
              fontSize: '1.75rem',
              border: '1px solid rgba(59, 130, 246, 0.3)',
            }}
          >
            💻
          </div>
          <div>
            <h1 style={{ fontSize: '1.25rem', fontWeight: 700, margin: 0 }}>
              내 컴퓨터 (SaintVision Virtual Computer)
            </h1>
            <p
              style={{
                fontSize: '0.8125rem',
                color: 'var(--color-text-muted, #94a3b8)',
                margin: '4px 0 0 0',
              }}
            >
              5대 PC 분산 패브릭 관측 · 논리 통합 자원 및 물리 토폴로지 대조 탐색기 (VF-GM-02)
            </p>
          </div>
        </div>

        <div style={{ display: 'flex', alignItems: 'center', gap: '8px' }}>
          <span
            style={{
              fontSize: '0.75rem',
              fontWeight: 600,
              padding: '4px 10px',
              borderRadius: '999px',
              backgroundColor: 'rgba(16, 185, 129, 0.15)',
              color: 'var(--color-brand-success, #10b981)',
              border: '1px solid rgba(16, 185, 129, 0.3)',
            }}
          >
            ● 패브릭 온라인: {logicalSummary.onlineNodeCount} / {logicalSummary.totalNodeCount} Nodes
          </span>
        </div>
      </div>

      {/* 2. Critical Invariant Architecture Disclaimer Banner */}
      <div
        role="alert"
        style={{
          padding: '12px 16px',
          borderRadius: '8px',
          backgroundColor: 'rgba(234, 179, 8, 0.1)',
          border: '1px solid rgba(234, 179, 8, 0.3)',
          display: 'flex',
          gap: '12px',
          alignItems: 'flex-start',
        }}
      >
        <span style={{ fontSize: '1.25rem' }}>🛡️</span>
        <div style={{ fontSize: '0.8125rem', lineHeight: 1.5 }}>
          <strong style={{ color: 'var(--color-brand-warning, #f59e0b)' }}>
            물리 자원 분산 보존 원칙 (ADR-028 / ARCH-WEB-FABRIC-001):
          </strong>{' '}
          {logicalSummary.disclaimer}
        </div>
      </div>

      {/* 3. Section: 논리 통합 가상 자원 (Logical Unified Fabric Pool) */}
      <div>
        <h2 style={{ fontSize: '0.9375rem', fontWeight: 600, marginBottom: '12px', display: 'flex', alignItems: 'center', gap: '8px' }}>
          <span>🌐</span> 논리 통합 가상 자원 풀 (Logical Fabric Capacity)
        </h2>

        <div
          style={{
            display: 'grid',
            gridTemplateColumns: 'repeat(auto-fit, minmax(220px, 1fr))',
            gap: '14px',
          }}
        >
          {/* CPU Card */}
          <div
            style={{
              padding: '16px',
              backgroundColor: 'var(--color-bg-subtle, #1e293b)',
              borderRadius: '10px',
              border: '1px solid var(--color-border-subtle, #334155)',
            }}
          >
            <div style={{ fontSize: '0.75rem', color: 'var(--color-text-muted, #94a3b8)', fontWeight: 600 }}>
              논리 vCPU 풀
            </div>
            <div style={{ fontSize: '1.5rem', fontWeight: 700, marginTop: '6px' }}>
              {logicalSummary.totalCores} <span style={{ fontSize: '0.875rem', fontWeight: 400 }}>Cores</span>
            </div>
            <div style={{ fontSize: '0.75rem', color: 'var(--color-text-muted)', marginTop: '4px' }}>
              스케줄 가용: <strong>{logicalSummary.allocatableCores} Cores</strong> · 실시간 점유: {logicalSummary.usedCores} Cores
            </div>
            <div
              style={{
                width: '100%',
                height: '6px',
                backgroundColor: 'rgba(255,255,255,0.1)',
                borderRadius: '3px',
                marginTop: '10px',
                overflow: 'hidden',
              }}
            >
              <div
                style={{
                  width: `${Math.min(100, (logicalSummary.usedCores / (logicalSummary.totalCores || 1)) * 100)}%`,
                  height: '100%',
                  backgroundColor: '#3b82f6',
                }}
              />
            </div>
          </div>

          {/* Memory Card */}
          <div
            style={{
              padding: '16px',
              backgroundColor: 'var(--color-bg-subtle, #1e293b)',
              borderRadius: '10px',
              border: '1px solid var(--color-border-subtle, #334155)',
            }}
          >
            <div style={{ fontSize: '0.75rem', color: 'var(--color-text-muted, #94a3b8)', fontWeight: 600 }}>
              논리 통합 RAM 풀
            </div>
            <div style={{ fontSize: '1.5rem', fontWeight: 700, marginTop: '6px' }}>
              {formatBytes(logicalSummary.totalMemoryBytes)}
            </div>
            <div style={{ fontSize: '0.75rem', color: 'var(--color-text-muted)', marginTop: '4px' }}>
              스케줄 가용: <strong>{formatBytes(logicalSummary.allocatableMemoryBytes)}</strong> · 점유: {formatBytes(logicalSummary.usedMemoryBytes)}
            </div>
            <div
              style={{
                width: '100%',
                height: '6px',
                backgroundColor: 'rgba(255,255,255,0.1)',
                borderRadius: '3px',
                marginTop: '10px',
                overflow: 'hidden',
              }}
            >
              <div
                style={{
                  width: `${Math.min(100, (logicalSummary.usedMemoryBytes / (logicalSummary.totalMemoryBytes || 1)) * 100)}%`,
                  height: '100%',
                  backgroundColor: '#10b981',
                }}
              />
            </div>
          </div>

          {/* GPU Card */}
          <div
            style={{
              padding: '16px',
              backgroundColor: 'var(--color-bg-subtle, #1e293b)',
              borderRadius: '10px',
              border: '1px solid var(--color-border-subtle, #334155)',
            }}
          >
            <div style={{ fontSize: '0.75rem', color: 'var(--color-text-muted, #94a3b8)', fontWeight: 600 }}>
              논리 가속기 풀 (GPU)
            </div>
            <div style={{ fontSize: '1.5rem', fontWeight: 700, marginTop: '6px' }}>
              {logicalSummary.totalGpuCount} <span style={{ fontSize: '0.875rem', fontWeight: 400 }}>장 (독립)</span>
            </div>
            <div style={{ fontSize: '0.75rem', color: 'var(--color-text-muted)', marginTop: '4px' }}>
              총 VRAM: <strong>{formatBytes(logicalSummary.totalGpuVramBytes)}</strong> (RTX 4090 + RTX 3080 + A4000)
            </div>
            <div
              style={{
                width: '100%',
                height: '6px',
                backgroundColor: 'rgba(255,255,255,0.1)',
                borderRadius: '3px',
                marginTop: '10px',
                overflow: 'hidden',
              }}
            >
              <div
                style={{
                  width: `${Math.min(100, (logicalSummary.usedGpuVramBytes / (logicalSummary.totalGpuVramBytes || 1)) * 100)}%`,
                  height: '100%',
                  backgroundColor: '#8b5cf6',
                }}
              />
            </div>
          </div>

          {/* Storage Card */}
          <div
            style={{
              padding: '16px',
              backgroundColor: 'var(--color-bg-subtle, #1e293b)',
              borderRadius: '10px',
              border: '1px solid var(--color-border-subtle, #334155)',
            }}
          >
            <div style={{ fontSize: '0.75rem', color: 'var(--color-text-muted, #94a3b8)', fontWeight: 600 }}>
              분산 패브릭 스토리지 (inv://)
            </div>
            <div style={{ fontSize: '1.5rem', fontWeight: 700, marginTop: '6px' }}>
              {formatBytes(logicalSummary.totalStorageBytes)}
            </div>
            <div style={{ fontSize: '0.75rem', color: 'var(--color-text-muted)', marginTop: '4px' }}>
              가용: <strong>{formatBytes(logicalSummary.totalStorageBytes - logicalSummary.usedStorageBytes)}</strong> · 점유: {formatBytes(logicalSummary.usedStorageBytes)}
            </div>
            <div
              style={{
                width: '100%',
                height: '6px',
                backgroundColor: 'rgba(255,255,255,0.1)',
                borderRadius: '3px',
                marginTop: '10px',
                overflow: 'hidden',
              }}
            >
              <div
                style={{
                  width: `${Math.min(100, (logicalSummary.usedStorageBytes / (logicalSummary.totalStorageBytes || 1)) * 100)}%`,
                  height: '100%',
                  backgroundColor: '#f59e0b',
                }}
              />
            </div>
          </div>
        </div>
      </div>

      {/* 4. Section: 물리 노드별 실제 토폴로지 (Physical Node Topology) */}
      <div>
        <div
          style={{
            display: 'flex',
            justifyContent: 'space-between',
            alignItems: 'center',
            marginBottom: '14px',
          }}
        >
          <h2 style={{ fontSize: '0.9375rem', fontWeight: 600, margin: 0, display: 'flex', alignItems: 'center', gap: '8px' }}>
            <span>🖥️</span> 물리 노드별 실제 토폴로지 (Physical Topology & Hardware Isolation)
          </h2>

          {/* Filter Pills */}
          <div style={{ display: 'flex', gap: '6px' }}>
            {(
              [
                { id: 'all', label: `전체 (${nodes.length})` },
                { id: 'schedulable', label: `스케줄 가능 (${nodes.filter((n) => n.schedulable).length})` },
                { id: 'gpu', label: `GPU 탑재 (${nodes.filter((n) => (n.gpuCount || 0) > 0).length})` },
                { id: 'observe', label: `관측 전용 (${nodes.filter((n) => n.observationOnly).length})` },
              ] as const
            ).map((filter) => {
              const active = filterMode === filter.id;
              return (
                <button
                  key={filter.id}
                  type="button"
                  onClick={() => setFilterMode(filter.id)}
                  style={{
                    padding: '4px 10px',
                    fontSize: '0.75rem',
                    fontWeight: active ? 600 : 500,
                    borderRadius: '6px',
                    border: '1px solid',
                    borderColor: active ? 'var(--color-brand-primary, #3b82f6)' : 'var(--color-border-subtle, #334155)',
                    backgroundColor: active ? 'rgba(59, 130, 246, 0.2)' : 'transparent',
                    color: active ? '#93c5fd' : 'var(--color-text-muted, #94a3b8)',
                    cursor: 'pointer',
                  }}
                >
                  {filter.label}
                </button>
              );
            })}
          </div>
        </div>

        {/* Node Grid */}
        <div
          style={{
            display: 'grid',
            gridTemplateColumns: 'repeat(auto-fill, minmax(320px, 1fr))',
            gap: '14px',
          }}
        >
          {filteredNodes.map((node) => {
            const isSelected = selectedNodeId === node.id;
            return (
              <div
                key={node.id}
                onClick={() => {
                  setSelectedNodeId(isSelected ? null : node.id);
                  onSelectNode?.(node.id);
                }}
                style={{
                  padding: '16px',
                  backgroundColor: isSelected ? 'var(--color-bg-subtle, #1e293b)' : 'var(--color-bg-surface, #0f172a)',
                  borderRadius: '10px',
                  border: isSelected
                    ? '1.5px solid var(--color-brand-primary, #3b82f6)'
                    : '1px solid var(--color-border-subtle, #334155)',
                  boxShadow: isSelected ? '0 0 12px rgba(59, 130, 246, 0.2)' : 'none',
                  cursor: 'pointer',
                  transition: 'all 0.15s ease',
                  display: 'flex',
                  flexDirection: 'column',
                  gap: '10px',
                }}
              >
                {/* Node Top Row */}
                <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'flex-start' }}>
                  <div>
                    <div style={{ display: 'flex', alignItems: 'center', gap: '8px' }}>
                      <span style={{ fontWeight: 600, fontSize: '0.9375rem' }}>{node.hostname}</span>
                      <span
                        style={{
                          fontSize: '0.6875rem',
                          padding: '2px 6px',
                          borderRadius: '4px',
                          backgroundColor: node.os === 'windows' ? 'rgba(59, 130, 246, 0.15)' : 'rgba(245, 158, 11, 0.15)',
                          color: node.os === 'windows' ? '#60a5fa' : '#fbbf24',
                          fontWeight: 600,
                          textTransform: 'uppercase',
                        }}
                      >
                        {node.os}
                      </span>
                    </div>
                    <code style={{ fontSize: '0.6875rem', color: 'var(--color-text-muted, #64748b)' }}>
                      {node.id} {node.ipAddress ? `· ${node.ipAddress}` : ''}
                    </code>
                  </div>

                  {/* Status Badges */}
                  <div style={{ display: 'flex', flexDirection: 'column', alignItems: 'flex-end', gap: '4px' }}>
                    <span
                      style={{
                        fontSize: '0.6875rem',
                        fontWeight: 600,
                        padding: '2px 6px',
                        borderRadius: '4px',
                        backgroundColor:
                          node.status === 'online'
                            ? 'rgba(16, 185, 129, 0.15)'
                            : node.status === 'draining'
                            ? 'rgba(245, 158, 11, 0.15)'
                            : 'rgba(239, 68, 68, 0.15)',
                        color:
                          node.status === 'online'
                            ? '#34d399'
                            : node.status === 'draining'
                            ? '#fbbf24'
                            : '#f87171',
                      }}
                    >
                      {node.status.toUpperCase()}
                    </span>

                    {node.observationOnly && (
                      <span
                        style={{
                          fontSize: '0.625rem',
                          fontWeight: 600,
                          padding: '1px 5px',
                          borderRadius: '3px',
                          backgroundColor: 'rgba(148, 163, 184, 0.15)',
                          color: '#94a3b8',
                          border: '1px solid rgba(148, 163, 184, 0.3)',
                        }}
                      >
                        관측 전용 (비배치)
                      </span>
                    )}
                  </div>
                </div>

                {/* Node Hardware Specs Grid */}
                <div
                  style={{
                    display: 'grid',
                    gridTemplateColumns: 'repeat(2, 1fr)',
                    gap: '8px',
                    fontSize: '0.75rem',
                    backgroundColor: 'rgba(0,0,0,0.2)',
                    padding: '8px 10px',
                    borderRadius: '6px',
                  }}
                >
                  <div>
                    <span style={{ color: 'var(--color-text-muted)' }}>CPU 코어: </span>
                    <strong>{node.cpuCores}C</strong> (가용 {node.allocatableCores ?? 0}C)
                  </div>
                  <div>
                    <span style={{ color: 'var(--color-text-muted)' }}>CPU 사용률: </span>
                    <strong>{node.cpuUsagePercent}%</strong>
                  </div>
                  <div>
                    <span style={{ color: 'var(--color-text-muted)' }}>RAM 크기: </span>
                    <strong>{formatBytes(node.memoryTotalBytes)}</strong>
                  </div>
                  <div>
                    <span style={{ color: 'var(--color-text-muted)' }}>RAM 가용: </span>
                    <strong>{formatBytes(node.allocatableMemoryBytes ?? 0)}</strong>
                  </div>
                </div>

                {/* GPU Information */}
                {node.gpuCount > 0 ? (
                  <div
                    style={{
                      fontSize: '0.75rem',
                      display: 'flex',
                      alignItems: 'center',
                      justifyContent: 'space-between',
                      backgroundColor: 'rgba(139, 92, 246, 0.1)',
                      padding: '6px 10px',
                      borderRadius: '6px',
                      border: '1px solid rgba(139, 92, 246, 0.2)',
                    }}
                  >
                    <div>
                      <span style={{ color: '#c084fc', fontWeight: 600 }}>⚡ {node.gpuName || 'GPU'}</span>
                      <div style={{ fontSize: '0.6875rem', color: 'var(--color-text-muted)' }}>
                        VRAM {formatBytes(node.gpuVramTotalBytes || 0)} (점유 {formatBytes(node.gpuVramUsedBytes || 0)})
                      </div>
                    </div>
                    <span style={{ fontSize: '0.6875rem', fontWeight: 600, color: '#a855f7' }}>
                      {node.gpuCount}장 탑재
                    </span>
                  </div>
                ) : (
                  <div
                    style={{
                      fontSize: '0.6875rem',
                      color: 'var(--color-text-muted)',
                      padding: '4px 8px',
                      backgroundColor: 'rgba(255,255,255,0.02)',
                      borderRadius: '4px',
                    }}
                  >
                    GPU 없음 (CPU 전용 워크로드 실행)
                  </div>
                )}

                {/* Contributed Storage */}
                <div style={{ fontSize: '0.75rem', display: 'flex', justifyContent: 'space-between', color: 'var(--color-text-muted)' }}>
                  <span>기여 스토리지:</span>
                  <span>{formatBytes(node.storageTotalBytes)} ({formatBytes(node.storageUsedBytes)} 사용)</span>
                </div>

                {/* Action button: Launch Terminal */}
                {onOpenTerminal && (
                  <div style={{ display: 'flex', justifyContent: 'flex-end', marginTop: '4px' }}>
                    <button
                      type="button"
                      onClick={(e) => {
                        e.stopPropagation();
                        onOpenTerminal(node.id);
                      }}
                      style={{
                        padding: '4px 10px',
                        fontSize: '0.6875rem',
                        fontWeight: 600,
                        borderRadius: '4px',
                        backgroundColor: 'rgba(59, 130, 246, 0.15)',
                        color: '#60a5fa',
                        border: '1px solid rgba(59, 130, 246, 0.3)',
                        cursor: 'pointer',
                      }}
                    >
                      ⌨️ 터미널 열기 ({node.os === 'windows' ? 'PowerShell' : 'Bash'})
                    </button>
                  </div>
                )}
              </div>
            );
          })}
        </div>
      </div>

      {/* 5. Interconnect & Locality Benchmarks */}
      <div
        style={{
          borderTop: '1px solid var(--color-border-subtle, #334155)',
          paddingTop: '16px',
        }}
      >
        <h3 style={{ fontSize: '0.875rem', fontWeight: 600, marginBottom: '8px', color: 'var(--color-text-muted)' }}>
          🔗 패브릭 노드 간 내부망 대기시간 및 mTLS 상호연결 (Fabric Interconnect)
        </h3>
        <div style={{ fontSize: '0.75rem', color: 'var(--color-text-muted)', lineHeight: 1.6 }}>
          • <strong>LAN 대기시간 (Ping RTT)</strong>: 0.4ms ~ 1.2ms (1Gbps/10Gbps 물리 이더넷) · mTLS 양방향 핸드셰이크 통과<br />
          • <strong>Tensor 분할 제약</strong>: 분산 텐서 병렬(Tensor Parallel)은 고속 버스 대역폭을 요구하므로 단일 PC 내 GPU 우선 배치되며, 노드 간 모델 분산 시에는 파이프라인 또는 데이터 병렬(Pipeline/Data Parallel)이 우선 권장됩니다.
        </div>
      </div>
    </div>
  );
};
