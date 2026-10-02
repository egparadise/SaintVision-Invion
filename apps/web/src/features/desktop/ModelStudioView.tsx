import React, { useEffect, useMemo, useRef, useState } from 'react';
import { fabricObservation as api } from '@/shared/api/fabricObservation';
import { NodeItem } from '@/contracts/types';
import {
  ModelManifest,
  ExecutionPlanMode,
  ExecutionPlan,
} from '@/contracts/virtualFabric';

export interface ModelStudioViewProps {
  projectId: string;
  clusterNodes?: NodeItem[];
  initialModel?: ModelManifest | null;
  onQueryModel?: (projectId: string, modelId: string, version: string) => Promise<any>;
  onRepairShard?: (
    modelId: string,
    shardIndex: number,
    targetNodeId: string
  ) => Promise<{ success: boolean; repairedReplicas: any[]; message?: string }>;
}

export const REPLICA_STATUS_CONFIG = {
  healthy: {
    color: 'var(--color-status-online)',
    bg: 'var(--color-bg-subtle)',
    border: 'var(--color-status-online)',
    label: '정상 (HEALTHY)',
  },
  unhealthy: {
    color: 'var(--color-status-offline)',
    bg: 'var(--color-bg-subtle)',
    border: 'var(--color-status-offline)',
    label: '이상 (UNHEALTHY)',
  },
  degraded: {
    color: 'var(--color-status-degraded)',
    bg: 'var(--color-bg-subtle)',
    border: 'var(--color-status-degraded)',
    label: '저하 (DEGRADED)',
  },
} as const;

export const MODEL_AVAILABILITY_CONFIG = {
  observed: {
    color: 'var(--color-status-active)',
    bg: 'var(--color-bg-subtle)',
    border: 'var(--color-status-active)',
    label: '관측 완료 · 분산 패브릭 연동',
  },
  unknown: {
    color: 'var(--color-status-unknown)',
    bg: 'var(--color-bg-subtle)',
    border: 'var(--color-status-unknown)',
    label: '알 수 없음 (unknown) · 실행 재검증 필요 (requiresExecutionRevalidation: true)',
  },
} as const;

export const PLAN_FEASIBILITY_CONFIG = {
  feasible: {
    color: 'var(--color-status-online)',
    bg: 'var(--color-bg-subtle)',
    border: 'var(--color-status-online)',
    label: '배치 가능 (Feasible)',
  },
  infeasible: {
    color: 'var(--color-status-offline)',
    bg: 'var(--color-bg-subtle)',
    border: 'var(--color-status-offline)',
    label: '배치 불가',
  },
} as const;

export const NODE_ELIGIBILITY_CONFIG = {
  eligible: {
    color: 'var(--color-status-online)',
    bg: 'var(--color-bg-subtle)',
    border: 'var(--color-status-online)',
    label: '할당 가능',
  },
  ineligible: {
    color: 'var(--color-status-offline)',
    bg: 'var(--color-bg-subtle)',
    border: 'var(--color-status-offline)',
    label: '관측 전용 노드 (연산 할당 불가)',
  },
} as const;

export function getReplicaStatusConfig(status?: string | null) {
  if (status && status in REPLICA_STATUS_CONFIG) {
    return REPLICA_STATUS_CONFIG[status as keyof typeof REPLICA_STATUS_CONFIG];
  }
  return {
    color: 'var(--color-status-unknown)',
    bg: 'var(--color-bg-subtle)',
    border: 'var(--color-status-unknown)',
    label: `알 수 없음 (${status || 'UNKNOWN'})`,
  };
}

export function getModelAvailabilityConfig(availability?: string | null) {
  if (availability === 'unknown') {
    return MODEL_AVAILABILITY_CONFIG.unknown;
  }
  if (availability && availability !== 'unknown') {
    return MODEL_AVAILABILITY_CONFIG.observed;
  }
  return MODEL_AVAILABILITY_CONFIG.unknown;
}

export function getPlanFeasibilityConfig(isFeasible: boolean) {
  return isFeasible ? PLAN_FEASIBILITY_CONFIG.feasible : PLAN_FEASIBILITY_CONFIG.infeasible;
}

export function getNodeEligibilityConfig(isObservation: boolean) {
  return isObservation ? NODE_ELIGIBILITY_CONFIG.ineligible : NODE_ELIGIBILITY_CONFIG.eligible;
}

function formatBytes(bytes: number): string {
  if (bytes === 0) return '0 B';
  const k = 1024;
  const sizes = ['B', 'KB', 'MB', 'GB', 'TB'];
  const i = Math.floor(Math.log(bytes) / Math.log(k));
  return `${(bytes / Math.pow(k, i)).toFixed(1)} ${sizes[i]}`;
}

export const ModelStudioView: React.FC<ModelStudioViewProps> = ({
  projectId,
  clusterNodes = [],
  initialModel = null,
  onQueryModel,
  onRepairShard,
}) => {
  const [modelId, setModelId] = useState('');
  const [version, setVersion] = useState('');
  const [result, setResult] = useState<any | null>(initialModel);
  const [error, setError] = useState('');
  const [loading, setLoading] = useState(false);
  const request = useRef<AbortController | null>(null);

  // Shard Repair State
  const [repairState, setRepairState] = useState<{
    repairingShardIndex: number | null;
    message: string | null;
    error: string | null;
  }>({
    repairingShardIndex: null,
    message: null,
    error: null,
  });

  // Execution Planner State
  const [selectedMode, setSelectedMode] = useState<ExecutionPlanMode>('single_node');
  const [selectedNodeIds, setSelectedNodeIds] = useState<string[]>(() => {
    // Default to first eligible node with GPU if available
    const eligible = clusterNodes.filter((n) => !n.observationOnly && n.schedulable !== false && n.status === 'online');
    return eligible.length > 0 ? [eligible[0].id] : [];
  });

  const clear = () => {
    request.current?.abort();
    setResult(initialModel);
    setError('');
    setLoading(false);
    setRepairState({
      repairingShardIndex: null,
      message: null,
      error: null,
    });
  };

  useEffect(() => {
    clear();
    setModelId('');
    setVersion('');
    return () => request.current?.abort();
  }, [projectId]);

  const query = async () => {
    clear();
    const controller = new AbortController();
    request.current = controller;
    setLoading(true);
    try {
      if (onQueryModel) {
        const value = await onQueryModel(projectId, modelId, version);
        if (!controller.signal.aborted) setResult(value);
      } else {
        const value = await api.model(projectId, modelId, version, controller.signal);
        if (!controller.signal.aborted) setResult(value);
      }
    } catch {
      if (!controller.signal.aborted) {
        setError('모델 기록을 조회할 수 없습니다. 프로젝트 권한과 모델 ID·버전을 확인하세요.');
      }
    } finally {
      if (!controller.signal.aborted) setLoading(false);
    }
  };

  // Only recognize ModelManifest when genuine shards array is provided
  const modelManifest: ModelManifest | null = useMemo(() => {
    if (!result) return null;
    if (result.shards && Array.isArray(result.shards) && result.shards.length > 0) {
      return result as ModelManifest;
    }
    return null;
  }, [result]);

  // Shard Repair Logic
  const handleRepairShard = async (shardIndex: number) => {
    if (!modelManifest) return;
    const shard = modelManifest.shards.find((s) => s.shardIndex === shardIndex);
    if (!shard) return;

    // Filter surviving nodes (eligible, online, not observation-only, not already hosting healthy replica)
    const surviving = clusterNodes.filter(
      (n) =>
        n.status === 'online' &&
        !n.observationOnly &&
        n.schedulable !== false &&
        !shard.replicas.some((r) => r.nodeId === n.id && r.status === 'healthy')
    );

    if (surviving.length === 0) {
      setRepairState({
        repairingShardIndex: shardIndex,
        message: null,
        error: '생존 가용 노드가 없어 샤드 복구를 진행할 수 없습니다.',
      });
      return;
    }

    setRepairState({
      repairingShardIndex: shardIndex,
      message: null,
      error: null,
    });

    try {
      const targetNode = surviving[0];
      if (!onRepairShard) {
        setRepairState({
          repairingShardIndex: shardIndex,
          message: null,
          error: '서버에 온디맨드 샤드 복구 API가 부재하여 복구를 수행할 수 없습니다. (복구 불가 / 미수행) ℹ️ [제품 기능 미제공]: 분산 샤드 온디맨드 복구 API는 현재 백엔드 제품 사양에 구현되어 있지 않습니다. 일시적 네트워크 장애가 아니므로 재시도해도 복구되지 않습니다.',
        });
        return;
      }

      const res = await onRepairShard(modelManifest.modelId, shardIndex, targetNode.id);

      if (!res.success) {
        setRepairState({
          repairingShardIndex: shardIndex,
          message: null,
          error: res.message || '샤드 복구 요청이 거절되었습니다.',
        });
        return;
      }

      // Update shard in modelManifest
      const healthyCount = res.repairedReplicas.filter((r) => r.status === 'healthy').length;
      const updatedShards = modelManifest.shards.map((s) =>
        s.shardIndex === shardIndex ? { ...s, replicas: res.repairedReplicas } : s
      );
      setResult({ ...modelManifest, shards: updatedShards });

      if (healthyCount < 2) {
        setRepairState({
          repairingShardIndex: shardIndex,
          message: `⚠️ 샤드 복구 부분 완료: ${healthyCount}/2 복제본 (여전히 저하 상태)`,
          error: null,
        });
      } else {
        setRepairState({
          repairingShardIndex: shardIndex,
          message: `✔ 샤드 복구 완료 (${healthyCount}/2 정상 복제본 확보)`,
          error: null,
        });
      }
    } catch (err: any) {
      setRepairState({
        repairingShardIndex: shardIndex,
        message: null,
        error: err?.message || '샤드 복구 중 통신 오류가 발생했습니다.',
      });
    }
  };

  // Execution Plan Evaluation
  const executionPlan: ExecutionPlan | null = useMemo(() => {
    if (!modelManifest) return null;

    // Filter assigned nodes
    const assigned = (clusterNodes || []).map((node) => {
      const isSelected = selectedNodeIds.includes(node.id);
      const isEligible = !node.observationOnly && node.schedulable !== false && node.status === 'online';
      return {
        nodeId: node.id,
        nodeHostname: node.hostname,
        role: isSelected ? 'worker' : 'idle',
        vramRequiredBytes: isSelected ? Math.floor(modelManifest.totalBytes / Math.max(1, selectedNodeIds.length)) : 0,
        assignedShards: isSelected ? modelManifest.shards.map((s) => s.shardIndex) : [],
        isEligible,
      };
    });

    const activeEligibleAssignments = assigned.filter((a) => selectedNodeIds.includes(a.nodeId) && a.isEligible);
    const totalAllocatedVram = activeEligibleAssignments.reduce((acc, a) => {
      const node = clusterNodes.find((n) => n.id === a.nodeId);
      const avail = node?.gpuVramTotalBytes ? node.gpuVramTotalBytes - (node.gpuVramUsedBytes || 0) : 0;
      return acc + avail;
    }, 0);

    const isFeasible = selectedMode === 'cpu_gpu_offload' || totalAllocatedVram >= modelManifest.totalBytes;
    let rejectionReason: string | undefined;
    if (!isFeasible) {
      rejectionReason = `가용 VRAM 부족 (요구: ${formatBytes(modelManifest.totalBytes)}, 가용: ${formatBytes(totalAllocatedVram)})`;
    }

    return {
      modelId: modelManifest.modelId,
      modelVersion: modelManifest.version,
      mode: selectedMode,
      assignedNodes: assigned,
      interconnectMinGbps: 1,
      localityScore: selectedMode === 'single_node' ? 95 : 60,
      explain: `${selectedMode} 모드로 ${activeEligibleAssignments.length}개 노드에 배치 평가 완료.`,
      isFeasible,
      rejectionReason,
    };
  }, [modelManifest, selectedMode, selectedNodeIds, clusterNodes]);

  // ADR-041: Cross-node tensor parallel warning
  const showTensorLanWarning = useMemo(() => {
    return selectedMode === 'tensor_pipeline_parallel' && selectedNodeIds.length > 1;
  }, [selectedMode, selectedNodeIds]);

  return (
    <section
      style={{
        padding: '24px',
        overflow: 'auto',
        height: '100%',
        backgroundColor: 'var(--color-bg-canvas)',
        color: 'var(--color-text-primary)',
        display: 'flex',
        flexDirection: 'column',
        gap: '20px',
      }}
      aria-label="모델 기록 조회"
    >
      <div>
        <h2 style={{ margin: '0 0 8px 0', fontSize: '1.25rem', fontWeight: 700 }}>
          모델 기록 조회
        </h2>
        <p style={{ margin: '0 0 4px 0', fontSize: '0.875rem', color: 'var(--color-text-secondary)' }}>
          프로젝트: <strong>{projectId}</strong>
        </p>
        <p style={{ margin: 0, fontSize: '0.8125rem', color: 'var(--color-text-muted)' }}>
          정확한 모델 ID와 버전으로 과거 커밋 기록을 조회합니다.
        </p>
      </div>

      <form
        onSubmit={(event) => {
          event.preventDefault();
          void query();
        }}
        style={{
          display: 'flex',
          gap: '12px',
          alignItems: 'center',
          flexWrap: 'wrap',
          padding: '12px 16px',
          backgroundColor: 'var(--color-bg-surface)',
          borderRadius: '8px',
          border: '1px solid var(--color-border-subtle)',
        }}
      >
        <label style={{ fontSize: '0.8125rem', color: 'var(--color-text-secondary)' }}>
          모델 ID{' '}
          <input
            data-testid="model-id-input"
            value={modelId}
            maxLength={30}
            onChange={(event) => {
              clear();
              setModelId(event.target.value);
            }}
            style={{
              padding: '6px 10px',
              backgroundColor: 'var(--color-bg-subtle)',
              border: '1px solid var(--color-border-subtle)',
              borderRadius: '4px',
              color: 'var(--color-text-primary)',
            }}
          />
        </label>
        <label style={{ fontSize: '0.8125rem', color: 'var(--color-text-secondary)' }}>
          버전{' '}
          <input
            data-testid="model-version-input"
            value={version}
            maxLength={64}
            onChange={(event) => {
              clear();
              setVersion(event.target.value);
            }}
            style={{
              padding: '6px 10px',
              backgroundColor: 'var(--color-bg-subtle)',
              border: '1px solid var(--color-border-subtle)',
              borderRadius: '4px',
              color: 'var(--color-text-primary)',
            }}
          />
        </label>
        <button
          data-testid="query-model-btn"
          disabled={!projectId || !modelId || !version || loading}
          style={{
            padding: '6px 14px',
            backgroundColor: 'var(--color-brand-primary)',
            color: 'var(--color-text-inverse)',
            border: 'none',
            borderRadius: '4px',
            cursor: loading ? 'not-allowed' : 'pointer',
            fontWeight: 600,
          }}
        >
          기록 조회
        </button>
      </form>

      {loading && <p role="status" style={{ color: 'var(--color-brand-hover)' }}>조회 중…</p>}
      {error && <p role="alert" style={{ color: 'var(--color-status-offline)' }}>{error}</p>}

      {result && (
        <article
          data-testid="model-manifest-article"
          style={{
            padding: '16px',
            backgroundColor: 'var(--color-bg-surface)',
            borderRadius: '8px',
            border: '1px solid var(--color-bg-surface)',
            display: 'flex',
            flexDirection: 'column',
            gap: '8px',
          }}
        >
          <h3 style={{ margin: 0, fontSize: '1.125rem' }}>
            {result.modelId} · {result.version}
          </h3>
          <p data-testid="model-committed-at" style={{ margin: 0, fontSize: '0.8125rem', color: 'var(--color-text-secondary)' }}>
            커밋 시각: {result.committedAt ? result.committedAt : '미관측 (CommittedAt Absent)'}
          </p>
          <p style={{ margin: 0, fontSize: '0.8125rem', color: 'var(--color-text-secondary)', fontFamily: 'monospace' }}>
            Manifest SHA-256: {result.manifestHash || result.contentHash}
          </p>
          <p style={{ margin: 0, fontSize: '0.8125rem', color: 'var(--color-text-secondary)' }}>
            원본 Run: {result.sourceRunId ? result.sourceRunId : '미지정 (Run ID Absent)'}
          </p>
          <p style={{ margin: 0, fontSize: '0.8125rem', color: 'var(--color-text-secondary)' }}>
            {result.format} · {result.totalBytes} bytes · {result.shardCount || result.shards?.length || 1} shards
          </p>
          <p style={{ margin: 0, fontSize: '0.8125rem', color: 'var(--color-text-secondary)' }}>
            라이선스: {result.licensePolicy} · 분류: {result.classification}
          </p>
          {(() => {
            const availCfg = getModelAvailabilityConfig(result.currentAvailability);
            return (
              <p
                data-testid="model-availability-status"
                style={{
                  margin: 0,
                  fontSize: '0.8125rem',
                  color: availCfg.color,
                }}
              >
                현재 가용성: {availCfg.label}
              </p>
            );
          })()}
          <p
            data-testid="model-verification-notice"
            role="status"
            style={{
              margin: 0,
              fontSize: '0.8125rem',
              color: 'var(--color-status-degraded)',
            }}
          >
            무결성 상태: 검증 라우트 부재 (내부 verify만 존재) · 실행 재검증 필요 (requiresExecutionRevalidation: true)
            <br />
            <span style={{ fontSize: '0.75rem', color: 'var(--color-text-secondary)' }}>
              ℹ️ <strong>[제품 기능 미제공 (원격 검증 라우트 부재)]</strong>: 원격 HTTP 모델 검증 API는 현재 백엔드에서 서빙되지 않으며 커널 내부 검증만 존재합니다. 모델 무결성을 갱신하려면 작업 공간 실행(Run)을 통해 재검증을 수행하십시오.
            </span>
          </p>
        </article>
      )}

      {/* Unobserved Shards Notice when queried without shards */}
      {result && (!modelManifest || !modelManifest.shards || modelManifest.shards.length === 0) && (
        <div
          data-testid="unobserved-shards-notice"
          role="status"
          style={{
            padding: '12px 16px',
            backgroundColor: 'var(--color-bg-surface)',
            borderRadius: '8px',
            border: '1px solid var(--color-border-subtle)',
            color: 'var(--color-text-secondary)',
            fontSize: '0.8125rem',
            display: 'flex',
            alignItems: 'center',
            gap: '8px',
          }}
        >
          <span>ℹ️ (개별 샤드 및 per-shard 복제본 건강 관측 데이터가 백엔드에 부재합니다. 실행 재검증 후 수집됩니다.)</span>
        </div>
      )}

      {/* Shard & Replica Fabric Matrix */}
      {modelManifest && modelManifest.shards && modelManifest.shards.length > 0 && (
        <section
          data-testid="shards-matrix-section"
          style={{
            padding: '16px',
            backgroundColor: 'var(--color-bg-surface)',
            borderRadius: '8px',
            border: '1px solid var(--color-border-subtle)',
            display: 'flex',
            flexDirection: 'column',
            gap: '12px',
          }}
        >
          <h3 style={{ margin: 0, fontSize: '1rem', fontWeight: 600 }}>
            샤드 및 복제본 패브릭 매트릭스 (Shard & Replica Matrix)
          </h3>

          {repairState.error && (
            <div
              data-testid="shard-repair-error"
              role="alert"
              style={{
                padding: '8px 12px',
                backgroundColor: 'var(--color-bg-subtle)',
                border: '1px solid var(--color-status-offline)',
                borderRadius: '6px',
                color: 'var(--color-status-offline)',
                fontSize: '0.8125rem',
              }}
            >
              샤드 복구 실패: {repairState.error}
            </div>
          )}

          {repairState.message && repairState.message.includes('⚠️') && (
            <div
              data-testid="shard-repair-warning"
              role="alert"
              style={{
                padding: '8px 12px',
                backgroundColor: 'var(--color-bg-subtle)',
                border: '1px solid var(--color-status-degraded)',
                borderRadius: '6px',
                color: 'var(--color-status-degraded)',
                fontSize: '0.8125rem',
              }}
            >
              {repairState.message}
            </div>
          )}

          {repairState.message && repairState.message.includes('✔') && (
            <div
              data-testid="shard-repair-success"
              role="status"
              aria-live="polite"
              style={{
                padding: '8px 12px',
                backgroundColor: 'var(--color-bg-subtle)',
                border: '1px solid var(--color-status-online)',
                borderRadius: '6px',
                color: 'var(--color-status-online)',
                fontSize: '0.8125rem',
              }}
            >
              {repairState.message}
            </div>
          )}

          <div style={{ overflowX: 'auto' }}>
            <table
              data-testid="shards-table"
              style={{
                width: '100%',
                borderCollapse: 'collapse',
                fontSize: '0.8125rem',
                textAlign: 'left',
              }}
            >
              <thead>
                <tr style={{ borderBottom: '1px solid var(--color-border-subtle)', color: 'var(--color-text-secondary)' }}>
                  <th style={{ padding: '8px' }}>샤드 #</th>
                  <th style={{ padding: '8px' }}>바이트 범위</th>
                  <th style={{ padding: '8px' }}>레이어</th>
                  <th style={{ padding: '8px' }}>크기</th>
                  <th style={{ padding: '8px' }}>복제본 상태</th>
                  <th style={{ padding: '8px' }}>복구 작업</th>
                </tr>
              </thead>
              <tbody>
                {modelManifest.shards.map((shard) => {
                  const healthyReplicas = shard.replicas.filter((r) => r.status === 'healthy').length;
                  const isDegraded = healthyReplicas < 2 || shard.replicas.some((r) => r.status !== 'healthy');
                  const survivingNodes = clusterNodes.filter(
                    (n) =>
                      n.status === 'online' &&
                      !n.observationOnly &&
                      n.schedulable !== false &&
                      !shard.replicas.some((r) => r.nodeId === n.id && r.status === 'healthy')
                  );
                  const canRepair = survivingNodes.length > 0;

                  return (
                    <tr
                      key={shard.shardIndex}
                      data-testid={`shard-row-${shard.shardIndex}`}
                      style={{ borderBottom: '1px solid var(--color-border-subtle)' }}
                    >
                      <td style={{ padding: '8px', fontWeight: 600 }}>Shard {shard.shardIndex}</td>
                      <td style={{ padding: '8px', fontFamily: 'monospace' }}>{shard.byteRange}</td>
                      <td style={{ padding: '8px' }}>{shard.layers}</td>
                      <td style={{ padding: '8px' }}>{formatBytes(shard.sizeBytes)}</td>
                      <td style={{ padding: '8px' }}>
                        <div style={{ display: 'flex', gap: '6px', alignItems: 'center' }}>
                          {shard.replicas.map((r) => {
                            const repCfg = getReplicaStatusConfig(r.status);
                            return (
                              <span
                                key={r.nodeId}
                                data-testid={`replica-status-${r.nodeId}`}
                                style={{
                                  padding: '2px 6px',
                                  borderRadius: '4px',
                                  fontSize: '0.6875rem',
                                  backgroundColor: repCfg.bg,
                                  border: `1px solid ${repCfg.border}`,
                                  color: repCfg.color,
                                }}
                              >
                                {r.nodeHostname}: {r.status}
                              </span>
                            );
                          })}
                          {isDegraded && (
                            <span
                              data-testid="shard-degradation-badge"
                              role="alert"
                              style={{
                                padding: '2px 6px',
                                borderRadius: '4px',
                                fontSize: '0.6875rem',
                                backgroundColor: 'var(--color-bg-subtle)',
                                border: '1px solid var(--color-status-degraded)',
                                color: 'var(--color-status-degraded)',
                                fontWeight: 600,
                              }}
                            >
                              저하 ({healthyReplicas}/2)
                            </span>
                          )}
                        </div>
                      </td>
                      <td style={{ padding: '8px' }}>
                        {isDegraded ? (
                          canRepair ? (
                            <button
                              type="button"
                              data-testid={`repair-shard-${shard.shardIndex}-btn`}
                              onClick={() => void handleRepairShard(shard.shardIndex)}
                              style={{
                                padding: '4px 8px',
                                fontSize: '0.75rem',
                                backgroundColor: 'var(--color-status-degraded)',
                                color: 'var(--color-text-inverse)',
                                border: 'none',
                                borderRadius: '4px',
                                cursor: 'pointer',
                              }}
                            >
                              복제본 복구
                            </button>
                          ) : (
                            <span
                              data-testid={`no-surviving-nodes-${shard.shardIndex}`}
                              role="alert"
                              style={{ color: 'var(--color-status-offline)', fontSize: '0.75rem', fontWeight: 600 }}
                            >
                              생존 노드 없음 (복구 불가)
                            </span>
                          )
                        ) : (
                          <span style={{ color: 'var(--color-status-online)', fontSize: '0.75rem' }}>정상</span>
                        )}
                      </td>
                    </tr>
                  );
                })}
              </tbody>
            </table>
          </div>
        </section>
      )}

      {/* Locality & Capability Aware Execution Planner */}
      {modelManifest && executionPlan && (
        <section
          data-testid="execution-planner-section"
          style={{
            padding: '16px',
            backgroundColor: 'var(--color-bg-surface)',
            borderRadius: '8px',
            border: '1px solid var(--color-border-subtle)',
            display: 'flex',
            flexDirection: 'column',
            gap: '12px',
          }}
        >
          <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
            <h3 style={{ margin: 0, fontSize: '1rem', fontWeight: 600 }}>
              분산 실행 계획기 (Execution Planner - ADR-028/041)
            </h3>
            {(() => {
              const planCfg = getPlanFeasibilityConfig(executionPlan.isFeasible);
              return (
                <span
                  data-testid={executionPlan.isFeasible ? 'plan-feasible-badge' : 'plan-infeasible-badge'}
                  role={executionPlan.isFeasible ? undefined : 'alert'}
                  style={{
                    padding: '4px 8px',
                    backgroundColor: planCfg.bg,
                    border: `1px solid ${planCfg.border}`,
                    color: planCfg.color,
                    borderRadius: '4px',
                    fontSize: '0.75rem',
                    fontWeight: 600,
                  }}
                >
                  {executionPlan.isFeasible
                    ? `${planCfg.label} · 점수 ${executionPlan.localityScore}점`
                    : planCfg.label}
                </span>
              );
            })()}
          </div>

          {/* ADR-041 LAN Constraint Warning */}
          {showTensorLanWarning && (
            <div
              data-testid="tensor-parallel-lan-warning"
              role="alert"
              style={{
                padding: '10px 14px',
                backgroundColor: 'var(--color-bg-subtle)',
                border: '1px solid var(--color-status-degraded)',
                borderRadius: '6px',
                color: 'var(--color-status-degraded)',
                fontSize: '0.8125rem',
                lineHeight: 1.5,
              }}
            >
              ⚠️ <strong>네트워크 제약 경고 (ADR-041)</strong>: 1Gbps 이더넷 환경에서 교차 노드 텐서 병렬 처리는 심각한 통신 대기시간(All-Reduce Latency) 병목을 유발합니다. 단일 노드(Single-Node) 또는 파이프라인 병렬/오프로드 배치를 권장합니다.
            </div>
          )}

          {/* Feasibility Alert on Failure */}
          {!executionPlan.isFeasible && (
            <div
              data-testid="plan-infeasible-alert"
              role="alert"
              style={{
                padding: '10px 14px',
                backgroundColor: 'var(--color-bg-subtle)',
                border: '1px solid var(--color-status-offline)',
                borderRadius: '6px',
                color: 'var(--color-status-offline)',
                fontSize: '0.8125rem',
              }}
            >
              배치 불가: {executionPlan.rejectionReason}
            </div>
          )}

          {/* Mode Selector */}
          <div style={{ display: 'flex', gap: '10px', alignItems: 'center' }}>
            <label style={{ fontSize: '0.8125rem', color: 'var(--color-text-secondary)' }}>실행 모드:</label>
            <select
              data-testid="execution-mode-select"
              value={selectedMode}
              onChange={(e) => setSelectedMode(e.target.value as ExecutionPlanMode)}
              style={{
                padding: '6px 10px',
                backgroundColor: 'var(--color-bg-subtle)',
                color: 'var(--color-text-primary)',
                border: '1px solid var(--color-border-subtle)',
                borderRadius: '4px',
                fontSize: '0.8125rem',
              }}
            >
              <option value="single_node">단일 노드 (Single-Node Co-located)</option>
              <option value="request_routing">요청 라우팅 (Request Routing)</option>
              <option value="data_parallel">데이터 병렬 (Data Parallel)</option>
              <option value="tensor_pipeline_parallel">텐서/파이프라인 병렬 (Tensor/Pipeline Parallel)</option>
              <option value="cpu_gpu_offload">CPU/GPU 오프로드 (Host Memory Offload)</option>
            </select>
          </div>

          {/* Node Assignment & Observation Guard Table */}
          <div style={{ overflowX: 'auto', marginTop: '6px' }}>
            <table
              data-testid="node-assignment-table"
              style={{ width: '100%', borderCollapse: 'collapse', fontSize: '0.8125rem' }}
            >
              <thead>
                <tr style={{ borderBottom: '1px solid var(--color-border-subtle)', color: 'var(--color-text-secondary)' }}>
                  <th style={{ padding: '6px 8px' }}>선택</th>
                  <th style={{ padding: '6px 8px' }}>노드</th>
                  <th style={{ padding: '6px 8px' }}>GPU / VRAM</th>
                  <th style={{ padding: '6px 8px' }}>가용 코어</th>
                  <th style={{ padding: '6px 8px' }}>할당 자격 (Eligibility)</th>
                </tr>
              </thead>
              <tbody>
                {clusterNodes.map((node) => {
                  const isObservation = node.observationOnly || node.schedulable === false;
                  const isChecked = selectedNodeIds.includes(node.id);
                  const eligCfg = getNodeEligibilityConfig(isObservation);

                  return (
                    <tr
                      key={node.id}
                      data-testid={`node-row-${node.id}`}
                      style={{ borderBottom: '1px solid var(--color-border-subtle)' }}
                    >
                      <td style={{ padding: '6px 8px' }}>
                        <input
                          type="checkbox"
                          data-testid={`node-select-${node.id}`}
                          disabled={isObservation}
                          checked={isChecked}
                          onChange={(e) => {
                            if (e.target.checked) {
                              setSelectedNodeIds((prev) => [...prev, node.id]);
                            } else {
                              setSelectedNodeIds((prev) => prev.filter((id) => id !== node.id));
                            }
                          }}
                        />
                      </td>
                      <td style={{ padding: '6px 8px', fontWeight: 600 }}>{node.hostname}</td>
                      <td style={{ padding: '6px 8px' }}>
                        {node.gpuName || 'GPU 없음'}{' '}
                        {node.gpuVramTotalBytes ? `(${formatBytes(node.gpuVramTotalBytes)})` : ''}
                      </td>
                      <td style={{ padding: '6px 8px' }}>{node.allocatableCores ?? node.cpuCores}C</td>
                      <td style={{ padding: '6px 8px' }}>
                        {isObservation ? (
                          <span
                            data-testid="node-ineligible-badge"
                            role="alert"
                            style={{
                              padding: '2px 6px',
                              borderRadius: '4px',
                              fontSize: '0.6875rem',
                              backgroundColor: eligCfg.bg,
                              border: `1px solid ${eligCfg.border}`,
                              color: eligCfg.color,
                              fontWeight: 600,
                            }}
                          >
                            {eligCfg.label}
                          </span>
                        ) : (
                          <span style={{ color: eligCfg.color, fontSize: '0.75rem' }}>{eligCfg.label}</span>
                        )}
                      </td>
                    </tr>
                  );
                })}
              </tbody>
            </table>
          </div>
        </section>
      )}
    </section>
  );
};
