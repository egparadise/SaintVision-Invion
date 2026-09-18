import React, { useState, useMemo, useEffect } from 'react';
import { NodeItem, PlacementRequirement, PlacementExplainResult } from '@/contracts/types';
import { apiClient } from '@/shared/api/client';
import { evaluatePlacement } from './placementEngine';
import { ResourceTopologyGraph } from './ResourceTopologyGraph';
import { PlacementExplainView } from './PlacementExplainView';

export interface PlacementSimulatorProps {
  nodes: NodeItem[];
}

interface PoolItem {
  id: string;
  name: string;
  nodeIds: string[];
  totalCores: number;
  availableCores: number;
  totalMemoryBytes: number;
  availableMemoryBytes: number;
  totalGpus: number;
  availableGpus: number;
  gpuModels: string[];
}

interface CandidateItem {
  nodeId: string;
  hostname: string;
  os: string;
  availableCores: number;
  availableMemoryBytes: number;
  gpuCount: number;
  gpuName?: string;
  healthStatus: string;
}

interface ShardItem {
  shardId: string;
  targetNodeId: string;
  status: string;
}

export const PlacementSimulator: React.FC<PlacementSimulatorProps> = ({ nodes }) => {
  const [requiredCores, setRequiredCores] = useState<number>(4);
  const [requiredRamGb, setRequiredRamGb] = useState<number>(8);
  const [requiresGpu, setRequiresGpu] = useState<boolean>(false);
  const [preferredOs, setPreferredOs] = useState<'windows' | 'linux' | undefined>(undefined);
  const [localityNodeId, setLocalityNodeId] = useState<string>('nod_01JABCDEF01');
  const [fencedNodeIds, setFencedNodeIds] = useState<Set<string>>(new Set());

  // Real backend state
  const [pools, setPools] = useState<PoolItem[]>([]);
  const [selectedPoolId, setSelectedPoolId] = useState<string>('pool_01_training');
  const [candidates, setCandidates] = useState<CandidateItem[]>([]);
  const [serverShards, setServerShards] = useState<ShardItem[]>([]);
  const [serverExplanation, setServerExplanation] = useState<string | null>(null);

  // Fetch live resource pools & discovery candidates from backend
  useEffect(() => {
    let isMounted = true;
    apiClient<{ items: PoolItem[] }>('/v1/pools')
      .then((res) => {
        if (isMounted && res.items?.length > 0) {
          setPools(res.items);
        }
      })
      .catch((err) => console.warn('Live /v1/pools fetch fallback:', err));

    apiClient<{ items: CandidateItem[] }>('/v1/discovery/candidates')
      .then((res) => {
        if (isMounted && res.items?.length > 0) {
          setCandidates(res.items);
        }
      })
      .catch((err) => console.warn('Live /v1/discovery/candidates fetch fallback:', err));

    return () => {
      isMounted = false;
    };
  }, []);

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

  const localExplainResult = useMemo(
    () => evaluatePlacement(nodes, requirement, fencedNodeIds),
    [nodes, requirement, fencedNodeIds]
  );

  // Request real placement preview from backend endpoint
  useEffect(() => {
    let isMounted = true;
    apiClient<{
      poolId: string;
      selectedNodeId: string | null;
      explanation: string;
      shards: ShardItem[];
    }>(`/v1/pools/${selectedPoolId}/placement-preview`, {
      method: 'POST',
      body: JSON.stringify({
        ...requirement,
        fencedNodeIds: Array.from(fencedNodeIds),
      }),
    })
      .then((res) => {
        if (isMounted) {
          setServerExplanation(res.explanation);
          if (res.shards) {
            setServerShards(res.shards);
          }
        }
      })
      .catch((err) => {
        console.warn('Backend placement-preview fallback to deterministic engine:', err);
      });

    return () => {
      isMounted = false;
    };
  }, [requirement, fencedNodeIds, selectedPoolId]);

  const activePool = pools.find((p) => p.id === selectedPoolId) || pools[0];
  const explainResult: PlacementExplainResult = localExplainResult;

  return (
    <div>
      <div style={{ marginBottom: '24px' }}>
        <h2 style={{ fontSize: '1.25rem', fontWeight: 600 }}>설명 가능한 자원 배치 시뮬레이터 (S05-FE)</h2>
        <p style={{ fontSize: '0.875rem', color: 'var(--color-text-muted)', marginTop: '4px' }}>
          5개 분산 노드 대상 Hard Filter 검사 및 다기준 가중치 산정에 따른 결정론적 자원 스케줄링 (AC-05)
        </p>
      </div>

      {/* Resource Pools & Live Capacity Section */}
      {pools.length > 0 ? (
        <div
          style={{
            padding: '16px 20px',
            backgroundColor: 'var(--color-bg-surface)',
            borderRadius: 'var(--radius-lg)',
            border: '1px solid var(--color-border-subtle)',
            marginBottom: '20px',
          }}
        >
          <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', marginBottom: '12px' }}>
            <span style={{ fontSize: '0.875rem', fontWeight: 600 }}>클러스터 자원 풀 (Resource Pools / S05-BE)</span>
            <span style={{ fontSize: '0.75rem', color: 'var(--color-brand-primary)', fontWeight: 600 }}>
              실시간 백엔드 연결 활성: /v1/pools
            </span>
          </div>
          <div style={{ display: 'flex', gap: '8px', marginBottom: '16px' }}>
            {pools.map((p) => (
              <button
                key={p.id}
                onClick={() => setSelectedPoolId(p.id)}
                style={{
                  padding: '8px 14px',
                  borderRadius: 'var(--radius-md)',
                  fontSize: '0.8125rem',
                  fontWeight: 600,
                  cursor: 'pointer',
                  border: '1px solid var(--color-border-strong)',
                  backgroundColor: selectedPoolId === p.id ? 'var(--color-brand-primary)' : 'var(--color-bg-subtle)',
                  color: selectedPoolId === p.id ? '#ffffff' : 'var(--color-text-secondary)',
                }}
              >
                {p.name}
              </button>
            ))}
          </div>

          {activePool && (
            <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fit, minmax(160px, 1fr))', gap: '12px' }}>
              <div style={{ padding: '10px', backgroundColor: 'var(--color-bg-subtle)', borderRadius: 'var(--radius-sm)' }}>
                <div style={{ fontSize: '0.75rem', color: 'var(--color-text-muted)' }}>풀 할당 가용 코어</div>
                <div style={{ fontSize: '1.125rem', fontWeight: 700, color: 'var(--color-text-primary)' }}>
                  {activePool.availableCores} / {activePool.totalCores} Cores
                </div>
              </div>
              <div style={{ padding: '10px', backgroundColor: 'var(--color-bg-subtle)', borderRadius: 'var(--radius-sm)' }}>
                <div style={{ fontSize: '0.75rem', color: 'var(--color-text-muted)' }}>풀 가용 메모리</div>
                <div style={{ fontSize: '1.125rem', fontWeight: 700, color: 'var(--color-text-primary)' }}>
                  {Math.round(activePool.availableMemoryBytes / 1024 ** 3)} / {Math.round(activePool.totalMemoryBytes / 1024 ** 3)} GB
                </div>
              </div>
              <div style={{ padding: '10px', backgroundColor: 'var(--color-bg-subtle)', borderRadius: 'var(--radius-sm)' }}>
                <div style={{ fontSize: '0.75rem', color: 'var(--color-text-muted)' }}>가속 GPU 장치</div>
                <div style={{ fontSize: '1.125rem', fontWeight: 700, color: 'var(--color-text-primary)' }}>
                  {activePool.totalGpus > 0 ? `${activePool.availableGpus}/${activePool.totalGpus} GPUs (${activePool.gpuModels.join(', ')})` : 'GPU 없음 (CPU 풀)'}
                </div>
              </div>
            </div>
          )}
        </div>
      ) : (
        <div
          data-testid="pools-fallback-banner"
          style={{
            padding: '14px 18px',
            backgroundColor: 'var(--color-bg-subtle)',
            borderRadius: 'var(--radius-lg)',
            border: '1px dashed var(--color-border-subtle)',
            marginBottom: '20px',
            display: 'flex',
            alignItems: 'center',
            justifyContent: 'space-between',
          }}
        >
          <div style={{ display: 'flex', alignItems: 'center', gap: '8px' }}>
            <span>ℹ️</span>
            <span style={{ fontSize: '0.8125rem', color: 'var(--color-text-secondary)' }}>
              제어 평면 자원 풀(/v1/pools) 어댑터 연결 대기 중 — 5대 노드 물리 토폴로지 기반 결정론적 스케줄링 시뮬레이터가 독립 동작합니다.
            </span>
          </div>
          <span style={{ fontSize: '0.75rem', color: 'var(--color-text-muted)', fontFamily: 'var(--font-mono)' }}>로컬 결정론적 평가 활성</span>
        </div>
      )}

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

      {serverExplanation && (
        <div
          style={{
            padding: '12px 16px',
            backgroundColor: 'rgba(35, 134, 54, 0.1)',
            border: '1px solid var(--color-success)',
            borderRadius: 'var(--radius-md)',
            fontSize: '0.8125rem',
            color: 'var(--color-text-primary)',
            marginBottom: '20px',
          }}
        >
          🤖 <strong>서버 실시간 배치 설명:</strong> {serverExplanation}
        </div>
      )}

      {/* Resource Topology Graph */}
      <ResourceTopologyGraph
        nodes={nodes}
        fencedNodeIds={fencedNodeIds}
        selectedNodeId={explainResult.selectedNodeId}
        onToggleFence={handleToggleFence}
      />

      {/* Placement Explain View */}
      <PlacementExplainView explainResult={explainResult} />

      {/* Server Shard Placement & Discovery Candidates (S05-BE Live Data) */}
      <div style={{ marginTop: '28px', display: 'grid', gridTemplateColumns: 'repeat(auto-fit, minmax(320px, 1fr))', gap: '20px' }}>
        {/* Shards Status */}
        <div
          style={{
            padding: '20px',
            backgroundColor: 'var(--color-bg-surface)',
            borderRadius: 'var(--radius-lg)',
            border: '1px solid var(--color-border-subtle)',
          }}
        >
          <h4 style={{ fontSize: '0.875rem', fontWeight: 600, marginBottom: '12px' }}>
            분산 데이터 샤드 배치 상태 (/v1/pools/{selectedPoolId}/placement-preview)
          </h4>
          {serverShards.length > 0 ? (
            <table style={{ width: '100%', fontSize: '0.8125rem', borderCollapse: 'collapse' }}>
              <thead>
                <tr style={{ borderBottom: '1px solid var(--color-border-subtle)', textAlign: 'left' }}>
                  <th style={{ padding: '6px 8px' }}>샤드 ID</th>
                  <th style={{ padding: '6px 8px' }}>타겟 노드</th>
                  <th style={{ padding: '6px 8px' }}>배치 상태</th>
                </tr>
              </thead>
              <tbody>
                {serverShards.map((s) => (
                  <tr key={s.shardId} style={{ borderBottom: '1px solid var(--color-border-subtle)' }}>
                    <td style={{ padding: '6px 8px', fontFamily: 'var(--font-mono)' }}>{s.shardId}</td>
                    <td style={{ padding: '6px 8px' }}>{s.targetNodeId}</td>
                    <td style={{ padding: '6px 8px', color: 'var(--color-success)' }}>{s.status}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          ) : (
            <p style={{ fontSize: '0.75rem', color: 'var(--color-text-muted)' }}>샤드 계획 준비 중...</p>
          )}
        </div>

        {/* Discovery Candidates */}
        <div
          style={{
            padding: '20px',
            backgroundColor: 'var(--color-bg-surface)',
            borderRadius: 'var(--radius-lg)',
            border: '1px solid var(--color-border-subtle)',
          }}
        >
          <h4 style={{ fontSize: '0.875rem', fontWeight: 600, marginBottom: '12px' }}>
            자원 디스커버리 후보 목록 (/v1/discovery/candidates)
          </h4>
          {candidates.length > 0 ? (
            <div style={{ display: 'flex', flexDirection: 'column', gap: '8px' }}>
              {candidates.map((c) => (
                <div
                  key={c.nodeId}
                  style={{
                    display: 'flex',
                    justifyContent: 'space-between',
                    alignItems: 'center',
                    padding: '8px 12px',
                    backgroundColor: 'var(--color-bg-subtle)',
                    borderRadius: 'var(--radius-sm)',
                    fontSize: '0.75rem',
                  }}
                >
                  <div>
                    <strong>{c.hostname}</strong> ({c.os})
                    <span style={{ color: 'var(--color-text-muted)', marginLeft: '8px' }}>
                      {c.availableCores} 코어 / {Math.round(c.availableMemoryBytes / 1024 ** 3)} GB 가용
                    </span>
                  </div>
                  <span
                    style={{
                      padding: '2px 6px',
                      borderRadius: 'var(--radius-sm)',
                      backgroundColor: c.healthStatus === 'online' ? 'rgba(35, 134, 54, 0.2)' : 'rgba(218, 54, 51, 0.2)',
                      color: c.healthStatus === 'online' ? 'var(--color-success)' : 'var(--color-danger)',
                      fontWeight: 600,
                    }}
                  >
                    {c.healthStatus}
                  </span>
                </div>
              ))}
            </div>
          ) : (
            <p data-testid="candidates-empty-state" style={{ fontSize: '0.75rem', color: 'var(--color-text-muted)', padding: '8px 0' }}>
              디스커버리 후보 목록 준비 중이거나 노드 등록 대기 중입니다.
            </p>
          )}
        </div>
      </div>
    </div>
  );
};
