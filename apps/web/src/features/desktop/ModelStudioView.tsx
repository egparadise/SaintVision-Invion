import React, { useState } from 'react';
import {
  ModelManifest,
  ExecutionPlanMode,
  ExecutionPlan,
} from '@/contracts/virtualFabric';
import { NodeItem } from '@/contracts/types';

export interface ModelStudioViewProps {
  nodes: NodeItem[];
  onDispatchRun?: (plan: ExecutionPlan) => void;
}

const SAMPLE_MODELS: ModelManifest[] = [
  {
    modelId: 'pacs-cxr-foundation-v2',
    name: 'PACS CXR Foundation Model v2',
    version: '2.1.0',
    format: 'safetensors',
    totalBytes: 14800 * 1024 * 1024, // 14.8 GB
    contentHash: '6f8c4e3b2a1d0f9e8d7c6b5a4f3e2d1c0b9a8f7e6d5c4b3a2f1e0d9c8b7a6f5e',
    runtimeCompatibility: ['PyTorch >=2.4', 'vLLM >=0.6', 'CUDA 12.4'],
    licensePolicy: 'Internal PACS Medical AI License v1 (Restricted)',
    classification: 'confidential',
    encryption: { enabled: true, keyRef: 'kms://saint-vault/keys/medical-ai-2026' },
    supportedModes: ['single_node', 'request_routing', 'data_parallel', 'tensor_pipeline_parallel', 'cpu_gpu_offload'],
    status: 'committed',
    createdAt: '2026-09-12T10:00:00Z',
    updatedAt: '2026-09-14T20:30:00Z',
    shards: [
      {
        shardIndex: 0,
        shardId: 'shard_00',
        byteRange: '0 - 3.70 GB',
        layers: 'embed_tokens, layers.0 - layers.7',
        contentHash: 'a0b1c2d3e4f5061728394a5b6c7d8e9f0a1b2c3d4e5f60718293a4b5c6d7e8f9',
        sizeBytes: 3700 * 1024 * 1024,
        replicas: [
          { nodeId: 'nod_01JABCDEF01', nodeHostname: 'Node-01-WinMain', status: 'healthy' },
          { nodeId: 'nod_01JABCDEF05', nodeHostname: 'Node-05-LinuxTrain', status: 'healthy' },
        ],
      },
      {
        shardIndex: 1,
        shardId: 'shard_01',
        byteRange: '3.70 - 7.40 GB',
        layers: 'layers.8 - layers.15',
        contentHash: 'b1c2d3e4f5061728394a5b6c7d8e9f0a1b2c3d4e5f60718293a4b5c6d7e8f9a0',
        sizeBytes: 3700 * 1024 * 1024,
        replicas: [
          { nodeId: 'nod_01JABCDEF01', nodeHostname: 'Node-01-WinMain', status: 'healthy' },
          { nodeId: 'nod_01JABCDEF05', nodeHostname: 'Node-05-LinuxTrain', status: 'healthy' },
        ],
      },
      {
        shardIndex: 2,
        shardId: 'shard_02',
        byteRange: '7.40 - 11.10 GB',
        layers: 'layers.16 - layers.23',
        contentHash: 'c2d3e4f5061728394a5b6c7d8e9f0a1b2c3d4e5f60718293a4b5c6d7e8f9a0b1',
        sizeBytes: 3700 * 1024 * 1024,
        replicas: [
          { nodeId: 'nod_01JABCDEF05', nodeHostname: 'Node-05-LinuxTrain', status: 'healthy' },
          { nodeId: 'nod_01JABCDEF04', nodeHostname: 'Node-04-LinuxBuild', status: 'missing' }, // Degraded demo
        ],
      },
      {
        shardIndex: 3,
        shardId: 'shard_03',
        byteRange: '11.10 - 14.80 GB',
        layers: 'layers.24 - layers.31, lm_head',
        contentHash: 'd3e4f5061728394a5b6c7d8e9f0a1b2c3d4e5f60718293a4b5c6d7e8f9a0b1c2',
        sizeBytes: 3700 * 1024 * 1024,
        replicas: [
          { nodeId: 'nod_01JABCDEF01', nodeHostname: 'Node-01-WinMain', status: 'healthy' },
          { nodeId: 'nod_01JABCDEF05', nodeHostname: 'Node-05-LinuxTrain', status: 'healthy' },
        ],
      },
    ],
  },
  {
    modelId: 'saint-segment-3d-lung',
    name: 'SaintVision 3D Lung CT Segmenter',
    version: '1.4.2',
    format: 'safetensors',
    totalBytes: 4200 * 1024 * 1024, // 4.2 GB
    contentHash: '1a2b3c4d5e6f708192a3b4c5d6e7f8091a2b3c4d5e6f708192a3b4c5d6e7f809',
    runtimeCompatibility: ['PyTorch >=2.3', 'MONAI >=1.3'],
    licensePolicy: 'Apache 2.0',
    classification: 'internal',
    encryption: { enabled: false },
    supportedModes: ['single_node', 'request_routing'],
    status: 'committed',
    createdAt: '2026-09-10T14:00:00Z',
    updatedAt: '2026-09-13T11:00:00Z',
    shards: [
      {
        shardIndex: 0,
        shardId: 'shard_00',
        byteRange: '0 - 4.20 GB',
        layers: 'unet_encoder_decoder_all',
        contentHash: '1a2b3c4d5e6f708192a3b4c5d6e7f8091a2b3c4d5e6f708192a3b4c5d6e7f809',
        sizeBytes: 4200 * 1024 * 1024,
        replicas: [
          { nodeId: 'nod_01JABCDEF01', nodeHostname: 'Node-01-WinMain', status: 'healthy' },
        ],
      },
    ],
  },
];

export const ModelStudioView: React.FC<ModelStudioViewProps> = ({
  nodes,
  onDispatchRun,
}) => {
  const [models, setModels] = useState<ModelManifest[]>(SAMPLE_MODELS);
  const [selectedModelId, setSelectedModelId] = useState<string>(SAMPLE_MODELS[0].modelId);
  const [selectedMode, setSelectedMode] = useState<ExecutionPlanMode>('single_node');
  const [targetGpuNodeId, setTargetGpuNodeId] = useState<string>('nod_01JABCDEF01');

  const selectedModel = models.find((m) => m.modelId === selectedModelId) || models[0];

  const formatBytes = (bytes: number) => {
    if (bytes === 0) return '0 B';
    const k = 1024;
    const sizes = ['B', 'KB', 'MB', 'GB', 'TB'];
    const i = Math.floor(Math.log(bytes) / Math.log(k));
    return parseFloat((bytes / Math.pow(k, i)).toFixed(1)) + ' ' + sizes[i];
  };

  const handleRepairShard = (shardIndex: number) => {
    setModels((prev) =>
      prev.map((m) => {
        if (m.modelId === selectedModel.modelId) {
          return {
            ...m,
            shards: m.shards.map((s) => {
              if (s.shardIndex === shardIndex) {
                return {
                  ...s,
                  replicas: s.replicas.map((r) => ({ ...r, status: 'healthy' })),
                };
              }
              return s;
            }),
          };
        }
        return m;
      })
    );
    alert(`[Shard Repair] 샤드 #${shardIndex}의 복제본을 생존 노드(Node-05)에서 Node-01로 복제 복구했습니다.`);
  };

  // Compute Execution Plan based on Selected Mode
  const executionPlan: ExecutionPlan = React.useMemo(() => {
    const requiredVramBytes = selectedModel.totalBytes * 1.25; // Model weights + KV cache headroom

    if (selectedMode === 'single_node') {
      const targetNode = nodes.find((n) => n.id === targetGpuNodeId);
      const targetVram = targetNode?.gpuVramTotalBytes || 0;
      const isFeasible = Boolean(targetNode?.schedulable && targetVram >= requiredVramBytes);

      return {
        modelId: selectedModel.modelId,
        modelVersion: selectedModel.version,
        mode: 'single_node',
        assignedNodes: [
          {
            nodeId: targetGpuNodeId,
            nodeHostname: targetNode?.hostname || targetGpuNodeId,
            role: 'primary_worker',
            vramRequiredBytes: requiredVramBytes,
            assignedShards: selectedModel.shards.map((s) => s.shardIndex),
            isEligible: isFeasible,
          },
        ],
        interconnectMinGbps: 0, // Single node requires zero cross-node bus
        localityScore: 0.95,
        explain: `단일 노드 (${targetNode?.hostname}) 단독 배치: VRAM 요구량 ${formatBytes(requiredVramBytes)} vs 가용 VRAM ${formatBytes(targetVram)}.`,
        isFeasible,
        rejectionReason: isFeasible
          ? undefined
          : `대상 노드의 GPU VRAM(${formatBytes(targetVram)})이 모델 요구량(${formatBytes(requiredVramBytes)})보다 부족하거나 노드가 비배치 상태입니다.`,
      };
    }

    if (selectedMode === 'tensor_pipeline_parallel') {
      return {
        modelId: selectedModel.modelId,
        modelVersion: selectedModel.version,
        mode: 'tensor_pipeline_parallel',
        assignedNodes: [
          {
            nodeId: 'nod_01JABCDEF01',
            nodeHostname: 'Node-01-WinMain',
            role: 'pipeline_stage_0',
            vramRequiredBytes: requiredVramBytes / 2,
            assignedShards: [0, 1],
            isEligible: true,
          },
          {
            nodeId: 'nod_01JABCDEF05',
            nodeHostname: 'Node-05-LinuxTrain',
            role: 'pipeline_stage_1',
            vramRequiredBytes: requiredVramBytes / 2,
            assignedShards: [2, 3],
            isEligible: true,
          },
        ],
        interconnectMinGbps: 10,
        localityScore: 0.85,
        explain:
          '다중 노드 파이프라인 병렬: Node-01(RTX 4090, 샤드 0-1)과 Node-05(A4000, 샤드 2-3)에 계층별 분할 배치. 노드 간 mTLS 파이프라인 전송 지연시간 <2ms 필수.',
        isFeasible: true,
      };
    }

    // Default request routing
    return {
      modelId: selectedModel.modelId,
      modelVersion: selectedModel.version,
      mode: selectedMode,
      assignedNodes: [
        {
          nodeId: 'nod_01JABCDEF01',
          nodeHostname: 'Node-01-WinMain',
          role: 'replica_worker',
          vramRequiredBytes: requiredVramBytes,
          assignedShards: selectedModel.shards.map((s) => s.shardIndex),
          isEligible: true,
        },
      ],
      interconnectMinGbps: 1,
      localityScore: 0.9,
      explain: `선택된 실행 모드(${selectedMode})에 따라 데이터 위치 우선으로 노드가 배치됩니다.`,
      isFeasible: true,
    };
  }, [selectedModel, selectedMode, targetGpuNodeId, nodes]);

  return (
    <div
      style={{
        display: 'flex',
        height: '100%',
        backgroundColor: 'var(--color-bg-surface, #0f172a)',
        color: 'var(--color-text-primary, #f8fafc)',
        overflow: 'hidden',
      }}
    >
      {/* 1. Left Sidebar: Models Catalog */}
      <div
        style={{
          width: '260px',
          borderRight: '1px solid var(--color-border-subtle, #334155)',
          backgroundColor: 'var(--color-bg-subtle, #1e293b)',
          display: 'flex',
          flexDirection: 'column',
          padding: '16px 12px',
          gap: '12px',
        }}
      >
        <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
          <span style={{ fontSize: '0.8125rem', fontWeight: 700, color: 'var(--color-text-muted, #94a3b8)', textTransform: 'uppercase' }}>
            등록된 AI 모델 카탈로그
          </span>
          <span style={{ fontSize: '0.75rem', color: '#38bdf8' }}>{models.length}개</span>
        </div>

        <div style={{ display: 'flex', flexDirection: 'column', gap: '6px', overflow: 'auto', flex: 1 }}>
          {models.map((model) => {
            const isSelected = model.modelId === selectedModel.modelId;
            const hasDegradedShard = model.shards.some((s) =>
              s.replicas.some((r) => r.status !== 'healthy')
            );

            return (
              <div
                key={model.modelId}
                onClick={() => setSelectedModelId(model.modelId)}
                style={{
                  padding: '12px 10px',
                  borderRadius: '8px',
                  backgroundColor: isSelected ? 'rgba(59, 130, 246, 0.2)' : 'transparent',
                  border: isSelected ? '1px solid var(--color-brand-primary, #3b82f6)' : '1px solid transparent',
                  cursor: 'pointer',
                  transition: 'all 0.15s ease',
                }}
              >
                <div style={{ display: 'flex', alignItems: 'center', gap: '6px', marginBottom: '4px' }}>
                  <span style={{ fontSize: '1rem' }}>🧠</span>
                  <span style={{ fontWeight: 600, fontSize: '0.8125rem' }}>{model.name}</span>
                </div>
                <div style={{ fontSize: '0.6875rem', color: 'var(--color-text-muted)' }}>
                  v{model.version} · {formatBytes(model.totalBytes)} · {model.format}
                </div>
                <div style={{ marginTop: '6px', display: 'flex', gap: '4px' }}>
                  <span
                    style={{
                      fontSize: '0.625rem',
                      fontWeight: 600,
                      padding: '1px 5px',
                      borderRadius: '3px',
                      backgroundColor: hasDegradedShard ? 'rgba(245, 158, 11, 0.15)' : 'rgba(16, 185, 129, 0.15)',
                      color: hasDegradedShard ? '#fbbf24' : '#34d399',
                    }}
                  >
                    {hasDegradedShard ? '⚠️ 샤드 점검 필요' : '● 정상 (Healthy)'}
                  </span>
                </div>
              </div>
            );
          })}
        </div>

        <button
          type="button"
          onClick={() => alert('[Import] SafeTensors/GGUF 가중치 임포트 및 ModelManifest 생성 마법사 시작')}
          style={{
            padding: '8px 12px',
            borderRadius: '6px',
            border: '1px solid rgba(59, 130, 246, 0.4)',
            backgroundColor: 'rgba(59, 130, 246, 0.15)',
            color: '#60a5fa',
            fontWeight: 600,
            fontSize: '0.8125rem',
            cursor: 'pointer',
          }}
        >
          ➕ 새 모델 가중치 임포트
        </button>
      </div>

      {/* 2. Main Area: Model Manifest & Shard Matrix & Execution Planner */}
      <div style={{ flex: 1, display: 'flex', flexDirection: 'column', overflow: 'auto', padding: '20px 24px', gap: '24px' }}>
        {/* Header Bar */}
        <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'flex-start', borderBottom: '1px solid var(--color-border-subtle, #334155)', paddingBottom: '16px' }}>
          <div>
            <div style={{ display: 'flex', alignItems: 'center', gap: '10px' }}>
              <h1 style={{ fontSize: '1.25rem', fontWeight: 700, margin: 0 }}>{selectedModel.name}</h1>
              <code style={{ fontSize: '0.75rem', backgroundColor: 'rgba(255,255,255,0.05)', padding: '2px 6px', borderRadius: '4px' }}>
                {selectedModel.modelId}
              </code>
              <span style={{ fontSize: '0.6875rem', fontWeight: 600, padding: '2px 6px', borderRadius: '4px', backgroundColor: 'rgba(59, 130, 246, 0.15)', color: '#60a5fa' }}>
                {selectedModel.format.toUpperCase()}
              </span>
            </div>
            <p style={{ fontSize: '0.8125rem', color: 'var(--color-text-muted)', margin: '4px 0 0 0' }}>
              총 크기: {formatBytes(selectedModel.totalBytes)} · {selectedModel.shards.length}개 Shard 분할 · 런타임: {selectedModel.runtimeCompatibility.join(', ')}
            </p>
          </div>

          <div style={{ textAlign: 'right', fontSize: '0.75rem', color: 'var(--color-text-muted)' }}>
            <div>전체 무결성 SHA-256:</div>
            <code style={{ fontSize: '0.6875rem', color: '#38bdf8' }}>{selectedModel.contentHash}</code>
          </div>
        </div>

        {/* Shards & Replicas Fabric Table */}
        <div>
          <h2 style={{ fontSize: '0.9375rem', fontWeight: 600, marginBottom: '12px', display: 'flex', alignItems: 'center', gap: '8px' }}>
            <span>🧩</span> 분산 샤드 및 물리 노드 복제본 매트릭스 (Shards & Replicas)
          </h2>

          <table style={{ width: '100%', borderCollapse: 'collapse', fontSize: '0.8125rem' }}>
            <thead>
              <tr style={{ borderBottom: '1px solid var(--color-border-subtle, #334155)', backgroundColor: 'rgba(0,0,0,0.2)', textAlign: 'left', color: 'var(--color-text-muted)' }}>
                <th style={{ padding: '8px 12px' }}>샤드 인덱스</th>
                <th style={{ padding: '8px 12px' }}>바이트 범위 및 레이어</th>
                <th style={{ padding: '8px 12px' }}>크기</th>
                <th style={{ padding: '8px 12px' }}>샤드 SHA-256</th>
                <th style={{ padding: '8px 12px' }}>물리 노드 복제본 (Replicas)</th>
                <th style={{ padding: '8px 12px' }}>조치</th>
              </tr>
            </thead>
            <tbody>
              {selectedModel.shards.map((shard) => {
                const isDegraded = shard.replicas.some((r) => r.status !== 'healthy');
                return (
                  <tr key={shard.shardIndex} style={{ borderBottom: '1px solid var(--color-border-subtle, #334155)' }}>
                    <td style={{ padding: '10px 12px', fontWeight: 600 }}>
                      Shard #{shard.shardIndex}
                    </td>
                    <td style={{ padding: '10px 12px' }}>
                      <div style={{ fontWeight: 500 }}>{shard.byteRange}</div>
                      <div style={{ fontSize: '0.6875rem', color: 'var(--color-text-muted)' }}>{shard.layers}</div>
                    </td>
                    <td style={{ padding: '10px 12px', color: 'var(--color-text-muted)' }}>
                      {formatBytes(shard.sizeBytes)}
                    </td>
                    <td style={{ padding: '10px 12px' }}>
                      <code style={{ fontSize: '0.6875rem', color: '#38bdf8' }}>
                        {shard.contentHash.substring(0, 16)}...
                      </code>
                    </td>
                    <td style={{ padding: '10px 12px' }}>
                      <div style={{ display: 'flex', gap: '6px', flexWrap: 'wrap' }}>
                        {shard.replicas.map((rep) => (
                          <span
                            key={rep.nodeId}
                            style={{
                              fontSize: '0.6875rem',
                              fontWeight: 600,
                              padding: '2px 6px',
                              borderRadius: '4px',
                              backgroundColor: rep.status === 'healthy' ? 'rgba(16, 185, 129, 0.15)' : 'rgba(239, 68, 68, 0.15)',
                              color: rep.status === 'healthy' ? '#34d399' : '#f87171',
                            }}
                          >
                            {rep.nodeHostname.replace('-WinMain', '').replace('-LinuxTrain', '').replace('-LinuxBuild', '')} ({rep.status})
                          </span>
                        ))}
                      </div>
                    </td>
                    <td style={{ padding: '10px 12px' }}>
                      {isDegraded ? (
                        <button
                          type="button"
                          onClick={() => handleRepairShard(shard.shardIndex)}
                          style={{
                            padding: '3px 8px',
                            fontSize: '0.6875rem',
                            fontWeight: 600,
                            borderRadius: '4px',
                            border: '1px solid rgba(245, 158, 11, 0.4)',
                            backgroundColor: 'rgba(245, 158, 11, 0.15)',
                            color: '#fbbf24',
                            cursor: 'pointer',
                          }}
                        >
                          ⚡ 샤드 복구 (Repair)
                        </button>
                      ) : (
                        <span style={{ fontSize: '0.6875rem', color: 'var(--color-brand-success, #10b981)' }}>
                          ✓ 검증 완료
                        </span>
                      )}
                    </td>
                  </tr>
                );
              })}
            </tbody>
          </table>
        </div>

        {/* Execution Plan & Scheduler Mode Selection */}
        <div
          style={{
            padding: '16px 20px',
            backgroundColor: 'var(--color-bg-subtle, #1e293b)',
            borderRadius: '10px',
            border: '1px solid var(--color-border-subtle, #334155)',
            display: 'flex',
            flexDirection: 'column',
            gap: '16px',
          }}
        >
          <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
            <h2 style={{ fontSize: '0.9375rem', fontWeight: 600, margin: 0, display: 'flex', alignItems: 'center', gap: '8px' }}>
              <span>⚙️</span> 분산 실행 모드 및 스케줄러 배치 계획 (Execution Plan)
            </h2>
            <span style={{ fontSize: '0.75rem', color: 'var(--color-text-muted)' }}>
              Data Locality & Capability Aware Scheduler (ADR-041)
            </span>
          </div>

          {/* Mode Radio Buttons */}
          <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fit, minmax(180px, 1fr))', gap: '10px' }}>
            {[
              { id: 'single_node', label: 'Single-node 단독', desc: '단일 PC 내 고속 GPU에 전량 적재' },
              { id: 'request_routing', label: 'Request Routing', desc: '다중 노드 복제본에 요청 분산' },
              { id: 'data_parallel', label: 'Data Parallel', desc: '배치 분할 병렬 학습 (동일 복제)' },
              { id: 'tensor_pipeline_parallel', label: 'Pipeline/Tensor Parallel', desc: '노드 간 계층 분할 실행 (10GbE 필수)' },
              { id: 'cpu_gpu_offload', label: 'CPU/GPU Offload', desc: '초과 레이어를 시스템 RAM에 이동' },
            ].map((mode) => {
              const isSelected = selectedMode === mode.id;
              return (
                <div
                  key={mode.id}
                  onClick={() => setSelectedMode(mode.id as ExecutionPlanMode)}
                  style={{
                    padding: '10px 12px',
                    borderRadius: '8px',
                    border: isSelected
                      ? '1.5px solid var(--color-brand-primary, #3b82f6)'
                      : '1px solid var(--color-border-subtle, #334155)',
                    backgroundColor: isSelected ? 'rgba(59, 130, 246, 0.15)' : 'rgba(0,0,0,0.2)',
                    cursor: 'pointer',
                  }}
                >
                  <div style={{ fontWeight: 600, fontSize: '0.8125rem' }}>{mode.label}</div>
                  <div style={{ fontSize: '0.6875rem', color: 'var(--color-text-muted)', marginTop: '2px' }}>
                    {mode.desc}
                  </div>
                </div>
              );
            })}
          </div>

          {/* Target Node Selection for Single-node */}
          {selectedMode === 'single_node' && (
            <div style={{ display: 'flex', alignItems: 'center', gap: '12px', fontSize: '0.8125rem' }}>
              <span style={{ color: 'var(--color-text-muted)' }}>배치 대상 GPU 노드 선택:</span>
              <select
                value={targetGpuNodeId}
                onChange={(e) => setTargetGpuNodeId(e.target.value)}
                style={{
                  padding: '6px 10px',
                  borderRadius: '6px',
                  backgroundColor: 'var(--color-bg-surface, #0f172a)',
                  color: 'inherit',
                  border: '1px solid var(--color-border-strong, #475569)',
                }}
              >
                {nodes
                  .filter((n) => (n.gpuCount || 0) > 0)
                  .map((n) => (
                    <option key={n.id} value={n.id}>
                      {n.hostname} ({n.gpuName}, VRAM {formatBytes(n.gpuVramTotalBytes || 0)})
                    </option>
                  ))}
              </select>
            </div>
          )}

          {/* Plan Explanation & Feasibility Check */}
          <div
            style={{
              padding: '12px 14px',
              borderRadius: '8px',
              backgroundColor: executionPlan.isFeasible ? 'rgba(16, 185, 129, 0.1)' : 'rgba(239, 68, 68, 0.1)',
              border: '1px solid',
              borderColor: executionPlan.isFeasible ? 'rgba(16, 185, 129, 0.3)' : 'rgba(239, 68, 68, 0.3)',
              fontSize: '0.8125rem',
              lineHeight: 1.5,
            }}
          >
            <div style={{ fontWeight: 600, color: executionPlan.isFeasible ? '#34d399' : '#f87171' }}>
              {executionPlan.isFeasible ? '✓ 스케줄러 실행 계획 타당성 통과 (Feasible)' : '✕ 스케줄러 거부 (Infeasible)'}
            </div>
            <div style={{ marginTop: '4px', color: 'var(--color-text-primary)' }}>
              {executionPlan.explain}
            </div>
            {executionPlan.rejectionReason && (
              <div style={{ marginTop: '4px', color: '#f87171', fontWeight: 600 }}>
                거부 사유: {executionPlan.rejectionReason}
              </div>
            )}
          </div>

          {/* Dispatch Button */}
          <div style={{ display: 'flex', justifyContent: 'flex-end' }}>
            <button
              type="button"
              disabled={!executionPlan.isFeasible}
              onClick={() => {
                onDispatchRun?.(executionPlan);
                alert(`[Dispatch] 모델 ${selectedModel.name} 실행 작업이 스케줄러에 등록되었습니다. (Mode: ${executionPlan.mode})`);
              }}
              style={{
                padding: '8px 16px',
                borderRadius: '6px',
                border: 'none',
                backgroundColor: executionPlan.isFeasible ? 'var(--color-brand-primary, #3b82f6)' : '#475569',
                color: '#fff',
                fontWeight: 600,
                fontSize: '0.8125rem',
                cursor: executionPlan.isFeasible ? 'pointer' : 'not-allowed',
              }}
            >
              🚀 분산 모델 실행 디스패치 (Dispatch Run)
            </button>
          </div>
        </div>
      </div>
    </div>
  );
};
