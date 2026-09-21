import React, { useState, useMemo, useEffect } from 'react';
import { NodeItem, PlacementRequirement, PlacementExplainResult } from '@/contracts/types';
import { apiClient } from '@/shared/api/client';
import { evaluatePlacement } from './placementEngine';
import { ResourceTopologyGraph } from './ResourceTopologyGraph';
import { PlacementExplainView } from './PlacementExplainView';

export interface PlacementSimulatorProps {
  nodes: NodeItem[];
  initialPools?: PoolItem[];
  initialPoolsState?: 'idle' | 'loading' | 'success' | 'error';
  initialPoolsError?: string | null;
  initialPreviewState?: 'idle' | 'loading' | 'success' | 'error';
  initialPreviewError?: string | null;
  initialServerShards?: ShardItem[];
  initialCandidates?: CandidateItem[];
  initialCandidatesState?: 'idle' | 'loading' | 'success' | 'error';
  initialCandidatesError?: string | null;
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

export const PlacementSimulator: React.FC<PlacementSimulatorProps> = ({
  nodes,
  initialPools,
  initialPoolsState,
  initialPoolsError,
  initialPreviewState,
  initialPreviewError,
  initialServerShards,
  initialCandidates,
  initialCandidatesState,
  initialCandidatesError,
}) => {
  const [requiredCores, setRequiredCores] = useState<number>(4);
  const [requiredRamGb, setRequiredRamGb] = useState<number>(8);
  const [requiresGpu, setRequiresGpu] = useState<boolean>(false);
  const [preferredOs, setPreferredOs] = useState<'windows' | 'linux' | undefined>(undefined);
  const [localityNodeId, setLocalityNodeId] = useState<string>(() => nodes[0]?.id || '');
  const [fencedNodeIds, setFencedNodeIds] = useState<Set<string>>(new Set());

  // Real backend state
  const [pools, setPools] = useState<PoolItem[]>(initialPools || []);
  const [poolsState, setPoolsState] = useState<'idle' | 'loading' | 'success' | 'error'>(initialPoolsState || 'idle');
  const [poolsError, setPoolsError] = useState<string | null>(initialPoolsError || null);

  const [selectedPoolId, setSelectedPoolId] = useState<string>(() => initialPools?.[0]?.id || '');
  const [candidates, setCandidates] = useState<CandidateItem[]>(initialCandidates || []);
  const [candidatesState, setCandidatesState] = useState<'idle' | 'loading' | 'success' | 'error'>(initialCandidatesState || 'idle');
  const [candidatesError, setCandidatesError] = useState<string | null>(initialCandidatesError || null);

  const [serverShards, setServerShards] = useState<ShardItem[]>(initialServerShards || []);
  const [serverExplanation, setServerExplanation] = useState<string | null>(null);
  const [previewState, setPreviewState] = useState<'idle' | 'loading' | 'success' | 'error'>(initialPreviewState || 'idle');
  const [previewError, setPreviewError] = useState<string | null>(initialPreviewError || null);

  const loadPools = () => {
    setPoolsState('loading');
    setPoolsError(null);
    apiClient<{ items: PoolItem[] }>('/v1/pools')
      .then((res) => {
        setPools(res.items || []);
        if (res.items && res.items.length > 0) {
          setSelectedPoolId((prev) => prev || res.items[0].id);
        }
        setPoolsState('success');
      })
      .catch((err) => {
        setPools([]);
        setPoolsError(err?.message || '자원 풀 목록을 조회할 수 없습니다. (오프라인 또는 오류)');
        setPoolsState('error');
      });
  };

  const loadCandidates = () => {
    setCandidatesState('loading');
    setCandidatesError(null);
    apiClient<{ items: CandidateItem[] }>('/v1/discovery/candidates')
      .then((res) => {
        setCandidates(res.items || []);
        setCandidatesState('success');
      })
      .catch((err) => {
        setCandidates([]);
        setCandidatesError(err?.message || '디스커버리 후보 목록을 조회할 수 없습니다. (오프라인 또는 오류)');
        setCandidatesState('error');
      });
  };

  // Fetch live resource pools & discovery candidates from backend
  useEffect(() => {
    if (initialPools === undefined && initialPoolsState === undefined) {
      loadPools();
    }
    if (initialCandidates === undefined && initialCandidatesState === undefined) {
      loadCandidates();
    }
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

  const loadPlacementPreview = () => {
    if (!selectedPoolId || !selectedPoolId.trim()) {
      setServerShards([]);
      setServerExplanation(null);
      setPreviewState('idle');
      setPreviewError(null);
      return;
    }
    setPreviewState('loading');
    setPreviewError(null);
    const query = new URLSearchParams({
      cpuMillicores: String(requirement.requiredCores * 1000),
      ramBytes: String(requirement.requiredMemoryBytes),
      gpuDevices: String(requirement.requiresGpu ? 1 : 0),
    });
    apiClient<{
      poolId: string;
      candidates: { nodeId: string; hostname: string; eligible?: boolean; availableCpuMillicores?: number }[];
      candidateCount: number;
    }>(`/v1/pools/${selectedPoolId}/placement-preview?${query.toString()}`)
      .then((res) => {
        setServerExplanation(`적격 노드 ${res.candidateCount}대 확인 (풀: ${res.poolId})`);
        if (res.candidates) {
          setServerShards(
            res.candidates.map((c, idx) => ({
              shardId: `shd_${selectedPoolId}_${idx + 1}`,
              targetNodeId: c.nodeId || c.hostname,
              status: c.eligible !== false ? '배치 적격 (Eligible)' : '배치 부적격 (Ineligible)',
            }))
          );
        } else {
          setServerShards([]);
        }
        setPreviewState('success');
      })
      .catch((err) => {
        setServerShards([]);
        setServerExplanation(null);
        setPreviewError(err?.message || `서버 배치 미리보기 실패: 풀 '${selectedPoolId}' 연결 불가`);
        setPreviewState('error');
      });
  };

  // Request real placement preview from backend endpoint
  useEffect(() => {
    if (initialPreviewState === undefined && selectedPoolId && selectedPoolId.trim()) {
      loadPlacementPreview();
    }
  }, [requirement, selectedPoolId]);

  const activePool = pools.find((p) => p.id === selectedPoolId) || pools[0];
  const explainResult: PlacementExplainResult = localExplainResult;

  return (
    <div>
      <div style={{ marginBottom: '24px' }}>
        <div style={{ display: 'flex', alignItems: 'center', gap: '12px', flexWrap: 'wrap' }}>
          <h2 style={{ fontSize: '1.25rem', fontWeight: 600, margin: 0 }}>설명 가능한 자원 배치 시뮬레이터 (S05-FE)</h2>
          <span
            data-testid="local-simulation-badge"
            style={{
              padding: '3px 8px',
              borderRadius: '4px',
              backgroundColor: 'rgba(234, 179, 8, 0.15)',
              border: '1px solid rgba(234, 179, 8, 0.3)',
              color: '#fbbf24',
              fontSize: '0.6875rem',
              fontWeight: 600,
            }}
          >
            로컬 결정론적 평가 (UNVERIFIED: 로컬 시뮬레이션 전용)
          </span>
        </div>
        <p style={{ fontSize: '0.875rem', color: 'var(--color-text-muted)', marginTop: '4px' }}>
          5개 분산 노드 대상 Hard Filter 검사 및 다기준 가중치 산정에 따른 결정론적 자원 스케줄링 (AC-05)
        </p>
      </div>

      {/* Resource Pools & Live Capacity Section */}
      {poolsState === 'loading' && (
        <div data-testid="pools-loading" style={{ padding: '16px', backgroundColor: 'var(--color-bg-surface)', borderRadius: 'var(--radius-lg)', border: '1px solid var(--color-border-subtle)', marginBottom: '20px', textAlign: 'center', color: 'var(--color-text-muted)', fontSize: '0.8125rem' }}>
          자원 풀 목록을 조회 중입니다...
        </div>
      )}

      {poolsState === 'error' && (
        <div
          role="alert"
          data-testid="pools-error-banner"
          style={{
            padding: '14px 18px',
            backgroundColor: 'rgba(239, 68, 68, 0.1)',
            borderRadius: 'var(--radius-lg)',
            border: '1px solid #ef4444',
            color: '#fca5a5',
            marginBottom: '20px',
          }}
        >
          <div style={{ fontWeight: 600, fontSize: '0.8125rem' }}>⚠️ 자원 풀 연동 실패</div>
          <div style={{ fontSize: '0.75rem', marginTop: '2px' }}>{poolsError}</div>
          <button
            type="button"
            data-testid="pools-retry-btn"
            onClick={loadPools}
            style={{ marginTop: '8px', padding: '4px 10px', fontSize: '0.6875rem', backgroundColor: '#334155', color: '#fff', border: 'none', borderRadius: '4px', cursor: 'pointer' }}
          >
            재시도 (Retry)
          </button>
        </div>
      )}

      {poolsState !== 'loading' && poolsState !== 'error' && pools.length > 0 && (
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
      )}

      {poolsState === 'idle' && (
        <div
          data-testid="pools-idle-banner"
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
              자원 풀 연동 대기 중입니다.
            </span>
          </div>
          <span style={{ fontSize: '0.75rem', color: '#fbbf24', fontWeight: 600, fontFamily: 'var(--font-mono)' }}>
            [로컬 결정론적 평가 (UNVERIFIED)]
          </span>
        </div>
      )}

      {poolsState === 'success' && pools.length === 0 && (
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
              자원 풀 정보가 없습니다. 현재 관측된 노드 정보로 배치 가능성을 미리 평가합니다.
            </span>
          </div>
          <span style={{ fontSize: '0.75rem', color: '#fbbf24', fontWeight: 600, fontFamily: 'var(--font-mono)' }}>
            [로컬 결정론적 평가 (UNVERIFIED)]
          </span>
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
              data-testid="locality-node-select"
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
              <option value="">-- 데이터 지역성 선택 안 함 (None) --</option>
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
          {previewState === 'loading' && (
            <div data-testid="preview-loading" style={{ padding: '12px', textAlign: 'center', color: '#94a3b8', fontSize: '0.75rem' }}>
              서버 배치 미리보기 조회 중...
            </div>
          )}

          {previewState === 'error' && (
            <div
              role="alert"
              data-testid="preview-error-banner"
              style={{
                padding: '12px',
                backgroundColor: 'rgba(239, 68, 68, 0.1)',
                border: '1px solid #ef4444',
                borderRadius: '6px',
                color: '#fca5a5',
                fontSize: '0.75rem',
              }}
            >
              <div style={{ fontWeight: 600 }}>⚠️ 서버 배치 미리보기 실패</div>
              <div style={{ marginTop: '2px' }}>{previewError}</div>
              <div style={{ fontSize: '0.6875rem', color: '#f87171', marginTop: '4px' }}>
                서버 어드미션 미검증: 가짜 샤드 상태를 생성하지 않습니다.
              </div>
              <button
                type="button"
                data-testid="preview-retry-btn"
                onClick={loadPlacementPreview}
                style={{ marginTop: '8px', padding: '3px 8px', fontSize: '0.6875rem', backgroundColor: '#334155', color: '#fff', border: 'none', borderRadius: '4px', cursor: 'pointer' }}
              >
                재시도 (Retry)
              </button>
            </div>
          )}

          {previewState === 'idle' && (
            <p data-testid="preview-idle-state" style={{ fontSize: '0.75rem', color: 'var(--color-text-muted)' }}>
              서버 배치 미리보기 요청 대기 중입니다.
            </p>
          )}

          {previewState === 'success' && serverShards.length === 0 && (
            <p data-testid="preview-empty-state" role="status" style={{ fontSize: '0.75rem', color: 'var(--color-text-muted)' }}>
              가용 샤드가 없습니다. 👉 <strong>[사용자 조치 필요]</strong>: 상단 슬라이더에서 모델 크기 또는 샤드 수를 조절하거나 자원 풀 요건을 변경하십시오.
            </p>
          )}

          {previewState !== 'error' && serverShards.length > 0 && (
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
          {candidatesState === 'loading' && (
            <div data-testid="candidates-loading" style={{ padding: '12px', textAlign: 'center', color: '#94a3b8', fontSize: '0.75rem' }}>
              디스커버리 후보 목록 조회 중...
            </div>
          )}

          {candidatesState === 'idle' && (
            <p data-testid="candidates-idle-state" style={{ fontSize: '0.75rem', color: 'var(--color-text-muted)' }}>
              디스커버리 후보 목록 조회 대기 중입니다.
            </p>
          )}

          {candidatesState === 'error' && (
            <div
              role="alert"
              data-testid="candidates-error-banner"
              style={{
                padding: '10px 12px',
                backgroundColor: 'rgba(239, 68, 68, 0.1)',
                border: '1px solid #ef4444',
                borderRadius: '6px',
                color: '#fca5a5',
                fontSize: '0.75rem',
              }}
            >
              <div style={{ fontWeight: 600 }}>⚠️ 디스커버리 후보 조회 실패</div>
              <div style={{ marginTop: '2px' }}>{candidatesError}</div>
              <button
                type="button"
                data-testid="candidates-retry-btn"
                onClick={loadCandidates}
                style={{ marginTop: '6px', padding: '3px 8px', fontSize: '0.6875rem', backgroundColor: '#334155', color: '#fff', border: 'none', borderRadius: '4px', cursor: 'pointer' }}
              >
                재시도 (Retry)
              </button>
            </div>
          )}

          {candidatesState === 'success' && candidates.length === 0 && (
            <p data-testid="candidates-empty-state" role="status" style={{ fontSize: '0.75rem', color: 'var(--color-text-muted)', padding: '8px 0', lineHeight: '1.4' }}>
              승인 대기 중인 디스커버리 후보가 없습니다.<br />
              <span style={{ fontSize: '0.6875rem', color: '#93c5fd' }}>
                🛠️ <strong>[운영자 조치 필요]</strong>: 신규 머신 등록은 클러스터 인프라 운영자에게 요청하십시오 (Node 운영 런북 'docs/vault/20_Operations/노드 운영 런북.md'의 'saint operator issue-grant' 참조).
              </span>
            </p>
          )}

          {candidatesState !== 'error' && candidates.length > 0 && (
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
          )}
        </div>
      </div>
    </div>
  );
};
