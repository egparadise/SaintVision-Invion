import React, { useState, useMemo } from 'react';
import { NodeItem, PlacementRequirement } from '@/contracts/types';
import { evaluatePlacement } from './placementEngine';
import { ResourceTopologyGraph } from './ResourceTopologyGraph';
import { PlacementExplainView } from './PlacementExplainView';

export interface PlacementSimulatorProps {
  nodes: NodeItem[];
}

export const PlacementSimulator: React.FC<PlacementSimulatorProps> = ({ nodes }) => {
  const [requiredCores, setRequiredCores] = useState<number>(4);
  const [requiredRamGb, setRequiredRamGb] = useState<number>(8);
  const [requiresGpu, setRequiresGpu] = useState<boolean>(false);
  const [preferredOs, setPreferredOs] = useState<'windows' | 'linux' | undefined>(undefined);
  const [localityNodeId, setLocalityNodeId] = useState<string>('nod_01JABCDEF01');
  const [fencedNodeIds, setFencedNodeIds] = useState<Set<string>>(new Set());

  const handleToggleFence = (nodeId: string) => {
    setFencedNodeIds((prev) => {
      const next = new Set(prev);
      if (next.has(nodeId)) {
        next.delete(nodeId);
      } else {
        next.add(nodeId);
      }
      return next;
    });
  };

  const requirement: PlacementRequirement = useMemo(
    () => ({
      requiredCores,
      requiredMemoryBytes: requiredRamGb * 1024 ** 3,
      requiresGpu,
      preferredOs,
      dataLocalityNodeId: localityNodeId,
    }),
    [requiredCores, requiredRamGb, requiresGpu, preferredOs, localityNodeId]
  );

  const explainResult = useMemo(
    () => evaluatePlacement(nodes, requirement, fencedNodeIds),
    [nodes, requirement, fencedNodeIds]
  );

  return (
    <div>
      <div style={{ marginBottom: '24px' }}>
        <h2 style={{ fontSize: '1.25rem', fontWeight: 600 }}>설명 가능한 자원 배치 시뮬레이터 (S05-FE)</h2>
        <p style={{ fontSize: '0.875rem', color: 'var(--color-text-muted)', marginTop: '4px' }}>
          5개 분산 노드 대상 Hard Filter 검사 및 다기준 가중치 산정에 따른 결정론적 자원 스케줄링 (AC-05)
        </p>
      </div>

      {/* Control Panel for Requirements */}
      <div
        style={{
          padding: '20px 24px',
          backgroundColor: 'var(--color-bg-surface)',
          borderRadius: 'var(--radius-lg)',
          border: '1px solid var(--color-border-subtle)',
          boxShadow: 'var(--shadow-sm)',
          marginBottom: '28px',
        }}
      >
        <h3 style={{ fontSize: '1rem', fontWeight: 600, marginBottom: '16px' }}>워크로드 배치 요구사항 설정</h3>
        <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fit, minmax(180px, 1fr))', gap: '16px' }}>
          {/* CPU Cores */}
          <div>
            <label style={{ display: 'block', fontSize: '0.8125rem', fontWeight: 600, marginBottom: '6px' }}>
              필요 CPU 코어: {requiredCores} Cores
            </label>
            <input
              type="range"
              min={1}
              max={16}
              value={requiredCores}
              onChange={(e) => setRequiredCores(Number(e.target.value))}
              style={{ width: '100%' }}
            />
          </div>

          {/* Memory GB */}
          <div>
            <label style={{ display: 'block', fontSize: '0.8125rem', fontWeight: 600, marginBottom: '6px' }}>
              필요 RAM: {requiredRamGb} GB
            </label>
            <input
              type="range"
              min={2}
              max={64}
              step={2}
              value={requiredRamGb}
              onChange={(e) => setRequiredRamGb(Number(e.target.value))}
              style={{ width: '100%' }}
            />
          </div>

          {/* GPU Toggle */}
          <div>
            <label style={{ display: 'block', fontSize: '0.8125rem', fontWeight: 600, marginBottom: '6px' }}>
              가속 GPU 필수 여부
            </label>
            <button
              onClick={() => setRequiresGpu((prev) => !prev)}
              style={{
                width: '100%',
                padding: '7px 12px',
                borderRadius: 'var(--radius-md)',
                fontSize: '0.8125rem',
                fontWeight: 600,
                cursor: 'pointer',
                border: '1px solid var(--color-border-strong)',
                backgroundColor: requiresGpu ? 'var(--color-brand-primary)' : 'var(--color-bg-subtle)',
                color: requiresGpu ? '#ffffff' : 'var(--color-text-secondary)',
              }}
            >
              {requiresGpu ? '⚡ GPU 필수 요구 (CUDA)' : '무관 (CPU 전용 가능)'}
            </button>
          </div>

          {/* OS Preference */}
          <div>
            <label style={{ display: 'block', fontSize: '0.8125rem', fontWeight: 600, marginBottom: '6px' }}>
              운영체제 선호
            </label>
            <select
              value={preferredOs || 'any'}
              onChange={(e) => setPreferredOs(e.target.value === 'any' ? undefined : (e.target.value as any))}
              style={{
                width: '100%',
                padding: '7px 12px',
                borderRadius: 'var(--radius-md)',
                border: '1px solid var(--color-border-strong)',
                backgroundColor: 'var(--color-bg-subtle)',
                color: 'var(--color-text-primary)',
                fontSize: '0.8125rem',
              }}
            >
              <option value="any">무관 (Any OS)</option>
              <option value="windows">Windows만 허용</option>
              <option value="linux">Linux만 허용</option>
            </select>
          </div>

          {/* Data Locality Preference */}
          <div>
            <label style={{ display: 'block', fontSize: '0.8125rem', fontWeight: 600, marginBottom: '6px' }}>
              데이터 원본 지역성 노드
            </label>
            <select
              value={localityNodeId}
              onChange={(e) => setLocalityNodeId(e.target.value)}
              style={{
                width: '100%',
                padding: '7px 12px',
                borderRadius: 'var(--radius-md)',
                border: '1px solid var(--color-border-strong)',
                backgroundColor: 'var(--color-bg-subtle)',
                color: 'var(--color-text-primary)',
                fontSize: '0.8125rem',
              }}
            >
              {nodes.map((n) => (
                <option key={n.id} value={n.id}>
                  {n.hostname} ({n.os.toUpperCase()})
                </option>
              ))}
            </select>
          </div>
        </div>
      </div>

      {/* Resource Topology Graph */}
      <ResourceTopologyGraph
        nodes={nodes}
        fencedNodeIds={fencedNodeIds}
        selectedNodeId={explainResult.selectedNodeId}
        onToggleFence={handleToggleFence}
      />

      {/* Placement Explain View */}
      <PlacementExplainView explainResult={explainResult} />
    </div>
  );
};
