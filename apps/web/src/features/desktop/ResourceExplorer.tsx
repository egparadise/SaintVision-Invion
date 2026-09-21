import React, { useState, useMemo, useEffect, useCallback } from 'react';
import { NodeItem } from '@/contracts/types';
import { LogicalResourceSummary } from '@/contracts/virtualFabric';
import {
  StorageContribution,
  StorageLocation,
  PoolCapacity,
  PlacementPreviewResponse,
  DistributedPlanResponse,
  NodeDetailResponse,
  DiscoveryCandidate,
  AdmissionResponse,
  getStorageContributions,
  registerStorageContribution,
  activateStorageContribution,
  revokeStorageContribution,
  getStorageLocations,
  getPoolCapacity,
  getPoolPlacementPreview,
  createPoolPlan,
  addPoolMember,
  removePoolMember,
  getNodeDetail,
  postNodeHeartbeat,
  triggerLivenessSweep,
  getDiscoveryCandidates,
  broadcastAnnouncement,
  admitDiscoveryCandidate,
  declineDiscoveryCandidate,
} from './fabricControlApi';
import { fetchStorageObservation } from '@/shared/api/storageObservation';
import type { StorageObservationView } from '@/contracts/types';

export interface ResourceExplorerProps {
  nodes: NodeItem[];
  nodesState?: 'idle' | 'loading' | 'success' | 'error';
  nodesError?: string | null;
  onRetryNodes?: () => void;
  tenantId?: string;
  projectId?: string;
  runId?: string;
  initialTab?: 'overview' | 'storage' | 'pools' | 'nodes' | 'discovery';
  onSelectNode?: (nodeId: string) => void;
  onOpenTerminal?: (nodeId: string) => void;
  initialCandidates?: DiscoveryCandidate[];
  initialCandidatesState?: 'idle' | 'loading' | 'success' | 'error';
  initialCandidatesError?: string | null;
  initialPoolCapacity?: PoolCapacity | null;
  initialPoolCapacityState?: 'idle' | 'loading' | 'success' | 'error';
  initialPoolCapacityError?: string | null;
  initialNodeDetail?: NodeDetailResponse | null;
  initialNodeDetailError?: string | null;
  initialSampleRequestId?: string;
}

export const ResourceExplorer: React.FC<ResourceExplorerProps> = ({
  nodes,
  nodesState = 'success',
  nodesError = null,
  onRetryNodes,
  tenantId,
  projectId,
  runId,
  initialTab = 'overview',
  onSelectNode,
  onOpenTerminal,
  initialCandidates,
  initialCandidatesState,
  initialCandidatesError,
  initialPoolCapacity,
  initialPoolCapacityState,
  initialPoolCapacityError,
  initialNodeDetail,
  initialNodeDetailError,
  initialSampleRequestId,
}) => {
  const [activeTab, setActiveTab] = useState<'overview' | 'storage' | 'pools' | 'nodes' | 'discovery'>(initialTab);
  const [filterMode, setFilterMode] = useState<'all' | 'schedulable' | 'gpu' | 'observe'>('all');
  const [selectedNodeId, setSelectedNodeId] = useState<string | null>(nodes[0]?.id || null);

  // ---------------------------------------------------------------------------
  // 1. Storage State
  // ---------------------------------------------------------------------------
  const [contributions, setContributions] = useState<StorageContribution[]>([]);
  const [locations, setLocations] = useState<StorageLocation[]>([]);
  const [isLoadingStorage, setIsLoadingStorage] = useState(false);
  const [storageError, setStorageError] = useState<string | null>(null);
  const [storageMessage, setStorageMessage] = useState<string | null>(null);
  const [newContribPath, setNewContribPath] = useState('C:\\SaintVision\\StorageData');
  const [newContribNode, setNewContribNode] = useState(nodes[0]?.id || '');
  const [newContribMode, setNewContribMode] = useState<'read_write' | 'read_only'>('read_write');
  const [newContribCapacityGB, setNewContribCapacityGB] = useState(500);

  // Storage Observation State (StorageObservationView)
  const [sampleRequestId, setSampleRequestId] = useState(initialSampleRequestId || '');
  const [storageObservation, setStorageObservation] = useState<StorageObservationView | null>(null);
  const [isLoadingObservation, setIsLoadingObservation] = useState(false);
  const [observationError, setObservationError] = useState<string | null>(null);

  const handleFetchStorageObservation = async () => {
    if (!projectId?.trim() || !runId?.trim() || !sampleRequestId.trim()) {
      setObservationError('프로젝트 ID, Run ID 및 요청 ID가 필요합니다.');
      return;
    }
    setIsLoadingObservation(true);
    setObservationError(null);
    try {
      const obs = await fetchStorageObservation(projectId.trim(), runId.trim(), sampleRequestId.trim());
      setStorageObservation(obs);
    } catch (err: any) {
      setObservationError(err?.message || '스토리지 샘플 관측 조회 실패');
    } finally {
      setIsLoadingObservation(false);
    }
  };

  // ---------------------------------------------------------------------------
  // 2. Pools State
  // ---------------------------------------------------------------------------
  const [selectedPoolId, setSelectedPoolId] = useState('pool-default');
  const [poolCapacity, setPoolCapacity] = useState<PoolCapacity | null>(initialPoolCapacity || null);
  const [poolCapacityState, setPoolCapacityState] = useState<'idle' | 'loading' | 'success' | 'error'>(initialPoolCapacityState || 'idle');
  const [poolCapacityError, setPoolCapacityError] = useState<string | null>(initialPoolCapacityError || null);
  const [poolMembers, setPoolMembers] = useState<string[]>([]);
  const [memberNodeToAdd, setMemberNodeToAdd] = useState(nodes[0]?.id || '');
  const [placementReq, setPlacementReq] = useState({ cpuMillicores: 2000, ramBytes: 4 * 1024 ** 3, gpuDevices: 1 });
  const [placementPreview, setPlacementPreview] = useState<PlacementPreviewResponse | null>(null);
  const [planRunId, setPlanRunId] = useState('');
  const [planStrategy, setPlanStrategy] = useState<'binpack' | 'spread'>('spread');
  const [planShardCount, setPlanShardCount] = useState(2);
  const [planResult, setPlanResult] = useState<DistributedPlanResponse | null>(null);
  const [poolMessage, setPoolMessage] = useState<string | null>(null);

  // ---------------------------------------------------------------------------
  // 3. Nodes Telemetry & Liveness State
  // ---------------------------------------------------------------------------
  const [nodeDetail, setNodeDetail] = useState<NodeDetailResponse | null>(initialNodeDetail || null);
  const [isLoadingNodeDetail, setIsLoadingNodeDetail] = useState(false);
  const [nodeDetailError, setNodeDetailError] = useState<string | null>(initialNodeDetailError || null);
  const [heartbeatSeq, setHeartbeatSeq] = useState(1);
  const [livenessMessage, setLivenessMessage] = useState<string | null>(null);

  // ---------------------------------------------------------------------------
  // 4. Discovery State (Truthful zero-mock initialization: empty array by default)
  // ---------------------------------------------------------------------------
  const [candidates, setCandidates] = useState<DiscoveryCandidate[]>(initialCandidates || []);
  const [candidatesState, setCandidatesState] = useState<'idle' | 'loading' | 'success' | 'error'>(initialCandidatesState || 'idle');
  const [candidatesError, setCandidatesError] = useState<string | null>(initialCandidatesError || null);
  const [admissionResult, setAdmissionResult] = useState<AdmissionResponse | null>(null);
  const [announcementHostname, setAnnouncementHostname] = useState('Node-07-Candidate');
  const [announcementOs, setAnnouncementOs] = useState<'windows' | 'linux'>('windows');
  const [discoveryMessage, setDiscoveryMessage] = useState<string | null>(null);

  // ---------------------------------------------------------------------------
  // Honest Aggregate Logical Pool (Zero-Mock calculation from live nodes)
  // ---------------------------------------------------------------------------
  // Summary Calculation (Strict Distinction: Static Capacity vs Dynamic Utilization)
  // ---------------------------------------------------------------------------
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

    let hasKnownCores = false;
    let hasKnownAllocatableCores = false;
    let hasKnownUsedCores = false;
    let hasKnownMemory = false;
    let hasKnownAllocatableMemory = false;
    let hasKnownUsedMemory = false;
    let hasKnownGpu = false;
    let hasKnownStorage = false;
    let hasKnownUsedStorage = false;

    for (const node of nodes) {
      if (node.status === 'online' || node.status === 'draining') {
        onlineNodeCount++;
      }
      if (typeof node.cpuCores === 'number' && Number.isFinite(node.cpuCores) && node.cpuCores > 0) {
        totalCores += node.cpuCores;
        hasKnownCores = true;
      }
      if (typeof node.allocatableCores === 'number' && Number.isFinite(node.allocatableCores)) {
        allocatableCores += node.allocatableCores;
        hasKnownAllocatableCores = true;
      }
      // Dynamic utilization is ONLY counted if node has finite non-negative usage and telemetry is NOT marked unavailable
      if (!node.telemetryUnavailable && typeof node.cpuUsagePercent === 'number' && Number.isFinite(node.cpuUsagePercent) && typeof node.cpuCores === 'number' && Number.isFinite(node.cpuCores)) {
        usedCores += (node.cpuCores * node.cpuUsagePercent) / 100;
        hasKnownUsedCores = true;
      }

      if (typeof node.memoryTotalBytes === 'number' && Number.isFinite(node.memoryTotalBytes) && node.memoryTotalBytes > 0) {
        totalMemoryBytes += node.memoryTotalBytes;
        hasKnownMemory = true;
      }
      if (typeof node.allocatableMemoryBytes === 'number' && Number.isFinite(node.allocatableMemoryBytes)) {
        allocatableMemoryBytes += node.allocatableMemoryBytes;
        hasKnownAllocatableMemory = true;
      }
      if (!node.telemetryUnavailable && typeof node.memoryUsedBytes === 'number' && Number.isFinite(node.memoryUsedBytes)) {
        usedMemoryBytes += node.memoryUsedBytes;
        hasKnownUsedMemory = true;
      }

      if (typeof node.gpuCount === 'number' && Number.isFinite(node.gpuCount)) {
        totalGpuCount += node.gpuCount;
        hasKnownGpu = true;
      }
      if (typeof node.gpuVramTotalBytes === 'number' && Number.isFinite(node.gpuVramTotalBytes)) {
        totalGpuVramBytes += node.gpuVramTotalBytes;
      }
      if (!node.telemetryUnavailable && typeof node.gpuVramUsedBytes === 'number' && Number.isFinite(node.gpuVramUsedBytes)) {
        usedGpuVramBytes += node.gpuVramUsedBytes;
      }

      if (typeof node.storageTotalBytes === 'number' && Number.isFinite(node.storageTotalBytes) && node.storageTotalBytes > 0) {
        totalStorageBytes += node.storageTotalBytes;
        hasKnownStorage = true;
      }
      if (!node.telemetryUnavailable && typeof node.storageUsedBytes === 'number' && Number.isFinite(node.storageUsedBytes)) {
        usedStorageBytes += node.storageUsedBytes;
        hasKnownUsedStorage = true;
      }
    }

    return {
      totalCores: hasKnownCores ? totalCores : 0,
      allocatableCores: hasKnownAllocatableCores ? allocatableCores : 0,
      usedCores: hasKnownUsedCores ? Math.round(usedCores * 10) / 10 : null,
      totalMemoryBytes: hasKnownMemory ? totalMemoryBytes : 0,
      allocatableMemoryBytes: hasKnownAllocatableMemory ? allocatableMemoryBytes : 0,
      usedMemoryBytes: hasKnownUsedMemory ? usedMemoryBytes : null,
      totalGpuCount: hasKnownGpu ? totalGpuCount : 0,
      totalGpuVramBytes: hasKnownGpu ? totalGpuVramBytes : 0,
      usedGpuVramBytes: !hasKnownGpu || totalGpuCount === 0 ? 0 : (usedGpuVramBytes > 0 ? usedGpuVramBytes : null),
      totalStorageBytes: hasKnownStorage ? totalStorageBytes : 0,
      usedStorageBytes: hasKnownUsedStorage ? usedStorageBytes : null,
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

  const formatBytes = (bytes: number | null | undefined) => {
    if (bytes === null || bytes === undefined || !Number.isFinite(bytes)) return '미확인';
    if (bytes === 0) return '0 B';
    const k = 1024;
    const sizes = ['B', 'KB', 'MB', 'GB', 'TB', 'PB'];
    const i = Math.floor(Math.log(bytes) / Math.log(k));
    return parseFloat((bytes / Math.pow(k, i)).toFixed(1)) + ' ' + sizes[i];
  };

  // ---------------------------------------------------------------------------
  // Data Loaders for Tabs
  // ---------------------------------------------------------------------------

  const loadStorage = useCallback(async () => {
    setIsLoadingStorage(true);
    setStorageError(null);
    try {
      const [contribRes, locRes] = await Promise.all([
        getStorageContributions(),
        getStorageLocations(),
      ]);
      setContributions(contribRes?.items || []);
      setLocations(locRes?.items || []);
    } catch (err: any) {
      setContributions([]);
      setLocations([]);
      setStorageError(err?.message || '스토리지 백엔드에 연결할 수 없습니다. (오프라인 또는 오류)');
    } finally {
      setIsLoadingStorage(false);
    }
  }, []);

  const loadPoolData = useCallback(async (poolId: string) => {
    setPoolCapacityState('loading');
    setPoolCapacityError(null);
    try {
      const cap = await getPoolCapacity(poolId);
      setPoolCapacity(cap);
      setPoolCapacityState('success');
    } catch (err: any) {
      setPoolCapacity(null);
      setPoolCapacityError(err?.message || `자원 풀 '${poolId}'의 용량 정보를 조회할 수 없습니다. (오프라인 또는 오류)`);
      setPoolCapacityState('error');
    }
  }, []);

  const loadNodeDetailData = useCallback(async (nodeId: string) => {
    setIsLoadingNodeDetail(true);
    setNodeDetailError(null);
    try {
      const detail = await getNodeDetail(nodeId);
      setNodeDetail(detail);
    } catch (err: any) {
      setNodeDetail(null);
      setNodeDetailError(err?.message || `노드 '${nodeId}'의 상세 및 역량 정보를 조회할 수 없습니다. (오프라인 또는 오류)`);
    } finally {
      setIsLoadingNodeDetail(false);
    }
  }, []);

  const loadDiscoveryCandidates = useCallback(async () => {
    setCandidatesState('loading');
    setCandidatesError(null);
    try {
      const res = await getDiscoveryCandidates();
      setCandidates(res?.items || []);
      setCandidatesState('success');
    } catch (err: any) {
      setCandidates([]);
      setCandidatesError(err?.message || '디스커버리 서비스에 연결할 수 없습니다. (오프라인 또는 오류)');
      setCandidatesState('error');
    }
  }, []);

  useEffect(() => {
    if (activeTab === 'storage') {
      loadStorage();
    } else if (activeTab === 'pools') {
      if (!initialPoolCapacityState) {
        loadPoolData(selectedPoolId);
      }
    } else if (activeTab === 'nodes' && selectedNodeId) {
      if (!initialNodeDetail && !initialNodeDetailError) {
        loadNodeDetailData(selectedNodeId);
      }
    } else if (activeTab === 'discovery') {
      if (!initialCandidatesState) {
        loadDiscoveryCandidates();
      }
    }
  }, [activeTab, loadStorage, loadPoolData, loadNodeDetailData, loadDiscoveryCandidates, selectedPoolId, selectedNodeId, initialCandidatesState, initialPoolCapacityState, initialNodeDetail, initialNodeDetailError]);

  // ---------------------------------------------------------------------------
  // Handlers for Control Plane Mutations
  // ---------------------------------------------------------------------------

  const handleRegisterContribution = async () => {
    const targetNodeId = newContribNode || nodes[0]?.id;
    if (!targetNodeId) {
      setStorageMessage('❌ 스토리지 기여 등록 실패: 등록할 유효한 대상 노드가 없습니다. (위조 노드 합성 차단)');
      return;
    }
    try {
      const idempotencyKey = `idemp_contrib_${Date.now()}`;
      const res = await registerStorageContribution(
        {
          nodeId: targetNodeId,
          declaredPath: newContribPath,
          mode: newContribMode,
          capacityBytes: newContribCapacityGB * 1024 ** 3,
          availableBytes: (newContribCapacityGB - 50) * 1024 ** 3,
        },
        idempotencyKey
      );
      setContributions((prev) => [res.contribution, ...prev]);
      setStorageMessage(`✔ 스토리지 기여 등록 완료 (${res.contribution.contributionId})`);
    } catch (err: any) {
      const msg = err?.problem?.detail || err?.detail || err?.message || '스토리지 기여 등록 요청 실패';
      setStorageMessage(`❌ 등록 실패: ${msg}`);
    }
  };

  const handleActivateContribution = async (id: string) => {
    try {
      const res = await activateStorageContribution(id);
      setContributions((prev) => prev.map((c) => (c.contributionId === id ? res.contribution : c)));
      setStorageMessage(`✔ 스토리지 활성화 완료 (${id})`);
    } catch (err: any) {
      const msg = err?.problem?.detail || err?.detail || err?.message || '활성화 요청 실패';
      setStorageMessage(`❌ 활성화 실패 (${id}): ${msg}`);
    }
  };

  const handleRevokeContribution = async (id: string) => {
    try {
      const res = await revokeStorageContribution(id);
      setContributions((prev) => prev.map((c) => (c.contributionId === id ? res.contribution : c)));
      setStorageMessage(`✔ 스토리지 기여 해제 완료 (${id})`);
    } catch (err: any) {
      const msg = err?.problem?.detail || err?.detail || err?.message || '기여 해제 요청 실패';
      setStorageMessage(`❌ 해제 실패 (${id}): ${msg}`);
    }
  };

  const handlePlacementPreview = async () => {
    try {
      const res = await getPoolPlacementPreview(selectedPoolId, placementReq);
      setPlacementPreview(res);
      setPoolMessage(`✔ 배치 미리보기 완료 (적격 노드: ${res.candidateCount}대)`);
    } catch (err: any) {
      const msg = err?.problem?.detail || err?.detail || err?.message || '배치 미리보기 조회 실패';
      setPoolMessage(`❌ 배치 미리보기 실패: ${msg}`);
    }
  };

  const handleCreatePlan = async () => {
    if (!planRunId.trim()) {
      setPoolMessage('❌ 분산 배치 계획 수립 실패: 유효한 승인 실행 ID(runId)를 입력해야 합니다. (위조 식별자 합성 방지)');
      return;
    }
    try {
      const res = await createPoolPlan(selectedPoolId, {
        runId: planRunId.trim(),
        strategy: planStrategy,
        shardCount: planShardCount,
        shardCpuMillicores: placementReq.cpuMillicores,
        shardRamBytes: placementReq.ramBytes,
        shardGpuDevices: placementReq.gpuDevices,
        splittableDeclared: true,
      });
      setPlanResult(res);
      setPoolMessage(`✔ 분산 배치 계획 수립 완료 (${res.planId})`);
    } catch (err: any) {
      const msg = err?.problem?.detail || err?.detail || err?.message || '분산 배치 계획 수립 실패';
      setPoolMessage(`❌ 계획 수립 실패: ${msg}`);
    }
  };

  const handleAddMember = async () => {
    if (!memberNodeToAdd) return;
    const targetNode = nodes.find((n) => n.id === memberNodeToAdd);
    if (targetNode?.observationOnly || targetNode?.schedulable === false) {
      setPoolMessage(`❌ 멤버 추가 거부: 노드 '${targetNode?.hostname || memberNodeToAdd}'은(는) 관측 전용(schedulable: false)이므로 연산 풀에 편입할 수 없습니다.`);
      return;
    }
    try {
      await addPoolMember(selectedPoolId, memberNodeToAdd);
      setPoolMembers((prev) => Array.from(new Set([...prev, memberNodeToAdd])));
      setPoolMessage(`✔ 노드 풀 멤버 추가 완료 (${memberNodeToAdd})`);
    } catch (err: any) {
      const msg = err?.problem?.detail || err?.detail || err?.message || '멤버 추가 실패';
      setPoolMessage(`❌ 멤버 추가 실패: ${msg}`);
    }
  };

  const handleRemoveMember = async (nodeId: string) => {
    try {
      await removePoolMember(selectedPoolId, nodeId);
      setPoolMembers((prev) => prev.filter((id) => id !== nodeId));
      setPoolMessage(`✔ 노드 풀 멤버 제거 완료 (${nodeId})`);
    } catch (err: any) {
      const msg = err?.problem?.detail || err?.detail || err?.message || '멤버 제거 실패';
      setPoolMessage(`❌ 멤버 제거 실패: ${msg}`);
    }
  };

  const handleSendHeartbeat = async () => {
    if (!selectedNodeId) return;
    try {
      const nextSeq = heartbeatSeq + 1;
      const res = await postNodeHeartbeat(selectedNodeId, {
        sequence: nextSeq,
        observations: [
          { capabilityId: 'cap_cpu', usedQuantity: 4, unit: 'cores' },
          { capabilityId: 'cap_ram', usedQuantity: 16 * 1024 ** 3, unit: 'bytes' },
        ],
      });
      setHeartbeatSeq(res.heartbeatSequence || nextSeq);
      setLivenessMessage(`✔ 하트비트 시퀀스 #${res.heartbeatSequence || nextSeq} 반영 완료`);
    } catch (err: any) {
      const msg = err?.problem?.detail || err?.detail || err?.message || '하트비트 전송 실패';
      setLivenessMessage(`❌ 하트비트 전송 실패: ${msg}`);
    }
  };

  const handleLivenessSweep = async () => {
    try {
      const res = await triggerLivenessSweep();
      setLivenessMessage(`✔ 라이브니스 스윕 완료 (만료 노드: ${res.markedLost}대, 타임아웃: ${res.timeoutSeconds}s)`);
    } catch (err: any) {
      const msg = err?.problem?.detail || err?.detail || err?.message || '라이브니스 스윕 실패';
      setLivenessMessage(`❌ 라이브니스 스윕 실패: ${msg}`);
    }
  };

  const handleBroadcastAnnouncement = async () => {
    if (!tenantId || !tenantId.trim()) {
      setDiscoveryMessage('⚠️ [테넌트 격리 차단]: 인증된 세션 테넌트 식별자(tenantId)가 없어 안내 방송을 전송할 수 없습니다. (위조 테넌트 합성 및 후보 한도 소진 방지)');
      return;
    }
    try {
      const res = await broadcastAnnouncement(
        {
          instanceId: `inst_${Date.now().toString(36)}`,
          hostname: announcementHostname,
          osType: announcementOs,
          osVersion: announcementOs === 'windows' ? 'Windows 11 Pro' : 'Ubuntu 24.04',
          agentVersion: '0.1.0',
          cpuCores: 8,
          ramBytes: 32 * 1024 ** 3,
          gpuCount: announcementOs === 'windows' ? 1 : 0,
          labels: { role: 'worker', network: 'intranet' },
        },
        tenantId.trim()
      );
      setDiscoveryMessage(`✔ 안내 방송 승인됨 (state: ${res.state})`);
      await loadDiscoveryCandidates();
    } catch (err: any) {
      const msg = err?.problem?.detail || err?.detail || err?.message || '안내 방송 전송 실패';
      setDiscoveryMessage(`❌ 안내 방송 실패: ${msg}`);
    }
  };

  const handleAdmitCandidate = async (id: string) => {
    try {
      const res = await admitDiscoveryCandidate(id);
      setAdmissionResult(res);
      setCandidates((prev) => prev.map((c) => (c.announcementId === id ? { ...c, state: 'admitted' } : c)));
      setDiscoveryMessage(`🎉 후보 승인 완료! 일회용 토큰 발급됨: ${res.bootstrapToken}`);
    } catch (err: any) {
      const msg = err?.problem?.detail || err?.detail || err?.message || '후보 승인 실패';
      setDiscoveryMessage(`❌ 후보 승인 실패: ${msg}`);
    }
  };

  const handleDeclineCandidate = async (id: string) => {
    try {
      await declineDiscoveryCandidate(id, '운영자 수동 거절');
      setCandidates((prev) => prev.map((c) => (c.announcementId === id ? { ...c, state: 'declined' } : c)));
      setDiscoveryMessage(`✔ 후보 거절 완료 (${id})`);
    } catch (err: any) {
      const msg = err?.problem?.detail || err?.detail || err?.message || '후보 거절 실패';
      setDiscoveryMessage(`❌ 후보 거절 실패: ${msg}`);
    }
  };

  return (
    <div
      style={{
        padding: '20px 24px',
        backgroundColor: 'var(--color-bg-surface, #0f172a)',
        color: 'var(--color-text-primary, #f8fafc)',
        display: 'flex',
        flexDirection: 'column',
        gap: '20px',
        minHeight: '100%',
      }}
    >
      {/* 1. Header with System Banner */}
      <div
        style={{
          display: 'flex',
          justifyContent: 'space-between',
          alignItems: 'center',
          borderBottom: '1px solid var(--color-border-subtle, #334155)',
          paddingBottom: '16px',
        }}
      >
        <div style={{ display: 'flex', alignItems: 'center', gap: '14px' }}>
          <div
            style={{
              width: '44px',
              height: '44px',
              borderRadius: '12px',
              backgroundColor: 'rgba(59, 130, 246, 0.15)',
              display: 'flex',
              alignItems: 'center',
              justifyContent: 'center',
              fontSize: '1.5rem',
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
                margin: '3px 0 0 0',
              }}
            >
              제어 평면 패브릭 탐색기 · 스토리지 기여 · 자원 풀 · 노드 텔레메트리 & 디스커버리 승인
            </p>
          </div>
        </div>

        {/* Global Cluster Sweep Button */}
        <div style={{ display: 'flex', gap: '8px', alignItems: 'center' }}>
          <button
            type="button"
            data-testid="liveness-sweep-btn"
            onClick={handleLivenessSweep}
            style={{
              padding: '6px 12px',
              fontSize: '0.75rem',
              fontWeight: 600,
              borderRadius: '6px',
              backgroundColor: 'rgba(239, 68, 68, 0.15)',
              color: '#f87171',
              border: '1px solid rgba(239, 68, 68, 0.3)',
              cursor: 'pointer',
            }}
          >
            ⚡ 라이브니스 스윕 실행
          </button>
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
            ● 온라인: {logicalSummary.onlineNodeCount} / {logicalSummary.totalNodeCount} Nodes
          </span>
        </div>
      </div>

      {/* 2. Top-Level Operational Navigation Tabs */}
      <div
        style={{
          display: 'flex',
          gap: '8px',
          borderBottom: '1px solid var(--color-border-subtle, #334155)',
          paddingBottom: '10px',
          overflowX: 'auto',
        }}
      >
        {(
          [
            { id: 'overview', label: '🖥️ 패브릭 및 토폴로지' },
            { id: 'storage', label: '💾 스토리지 기여 원장' },
            { id: 'pools', label: '🏊 자원 풀 & 배치 계획' },
            { id: 'nodes', label: '⚙️ 노드 상세 & 라이브니스' },
            { id: 'discovery', label: '📡 디스커버리 & 후보 승인' },
          ] as const
        ).map((t) => {
          const active = activeTab === t.id;
          return (
            <button
              key={t.id}
              type="button"
              onClick={() => setActiveTab(t.id)}
              style={{
                padding: '8px 16px',
                fontSize: '0.8125rem',
                fontWeight: active ? 700 : 500,
                borderRadius: '8px',
                border: '1px solid',
                borderColor: active ? '#3b82f6' : 'transparent',
                backgroundColor: active ? 'rgba(59, 130, 246, 0.2)' : 'rgba(255, 255, 255, 0.03)',
                color: active ? '#60a5fa' : '#94a3b8',
                cursor: 'pointer',
                transition: 'all 0.15s ease',
              }}
            >
              {t.label}
            </button>
          );
        })}
      </div>

      {/* Feedback Messages with Honest Error/Success Distinction & role="alert" */}
      {storageMessage && activeTab === 'storage' && (
        <div
          role={storageMessage.startsWith('❌') ? 'alert' : 'status'}
          data-testid={storageMessage.startsWith('❌') ? 'storage-action-error' : 'storage-action-success'}
          style={{
            padding: '8px 12px',
            borderRadius: '6px',
            backgroundColor: storageMessage.startsWith('❌') ? 'rgba(239, 68, 68, 0.2)' : 'rgba(16, 185, 129, 0.2)',
            color: storageMessage.startsWith('❌') ? '#fca5a5' : '#34d399',
            border: storageMessage.startsWith('❌') ? '1px solid rgba(239, 68, 68, 0.4)' : '1px solid rgba(16, 185, 129, 0.3)',
            fontSize: '0.75rem',
          }}
        >
          {storageMessage}
        </div>
      )}
      {poolMessage && activeTab === 'pools' && (
        <div
          role={poolMessage.startsWith('❌') ? 'alert' : 'status'}
          data-testid={poolMessage.startsWith('❌') ? 'pool-action-error' : 'pool-action-success'}
          style={{
            padding: '8px 12px',
            borderRadius: '6px',
            backgroundColor: poolMessage.startsWith('❌') ? 'rgba(239, 68, 68, 0.2)' : 'rgba(59, 130, 246, 0.2)',
            color: poolMessage.startsWith('❌') ? '#fca5a5' : '#93c5fd',
            border: poolMessage.startsWith('❌') ? '1px solid rgba(239, 68, 68, 0.4)' : '1px solid rgba(59, 130, 246, 0.3)',
            fontSize: '0.75rem',
          }}
        >
          {poolMessage}
        </div>
      )}
      {livenessMessage && (activeTab === 'nodes' || activeTab === 'overview') && (
        <div
          role={livenessMessage.startsWith('❌') ? 'alert' : 'status'}
          data-testid={livenessMessage.startsWith('❌') ? 'liveness-action-error' : 'liveness-action-success'}
          style={{
            padding: '8px 12px',
            borderRadius: '6px',
            backgroundColor: livenessMessage.startsWith('❌') ? 'rgba(239, 68, 68, 0.2)' : 'rgba(245, 158, 11, 0.2)',
            color: livenessMessage.startsWith('❌') ? '#fca5a5' : '#fbbf24',
            border: livenessMessage.startsWith('❌') ? '1px solid rgba(239, 68, 68, 0.4)' : '1px solid rgba(245, 158, 11, 0.3)',
            fontSize: '0.75rem',
          }}
        >
          {livenessMessage}
        </div>
      )}
      {discoveryMessage && activeTab === 'discovery' && (
        <div
          role={discoveryMessage.startsWith('❌') || discoveryMessage.startsWith('⚠️') ? 'alert' : 'status'}
          data-testid={discoveryMessage.startsWith('❌') || discoveryMessage.startsWith('⚠️') ? 'discovery-action-error' : 'discovery-action-success'}
          style={{
            padding: '8px 12px',
            borderRadius: '6px',
            backgroundColor: discoveryMessage.startsWith('❌') || discoveryMessage.startsWith('⚠️') ? 'rgba(239, 68, 68, 0.2)' : 'rgba(168, 85, 247, 0.2)',
            color: discoveryMessage.startsWith('❌') || discoveryMessage.startsWith('⚠️') ? '#fca5a5' : '#c084fc',
            border: discoveryMessage.startsWith('❌') || discoveryMessage.startsWith('⚠️') ? '1px solid rgba(239, 68, 68, 0.4)' : '1px solid rgba(168, 85, 247, 0.3)',
            fontSize: '0.75rem',
          }}
        >
          {discoveryMessage}
        </div>
      )}

      {/* ======================================================================= */}
      {/* TAB 1: 패브릭 및 토폴로지 개요 (Overview)                               */}
      {/* ======================================================================= */}
      {activeTab === 'overview' && (
        <div style={{ display: 'flex', flexDirection: 'column', gap: '20px' }}>
          {/* Architecture Disclaimer */}
          <div
            role="alert"
            data-testid="fabric-disclaimer-banner"
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

          {/* Logical Unified Fabric Capacity Cards */}
          <div
            style={{
              display: 'grid',
              gridTemplateColumns: 'repeat(auto-fit, minmax(220px, 1fr))',
              gap: '14px',
            }}
          >
            <div
              data-testid="logical-vcpu-card"
              style={{ padding: '16px', backgroundColor: '#1e293b', borderRadius: '10px', border: '1px solid #334155' }}
            >
              <div style={{ fontSize: '0.75rem', color: '#94a3b8', fontWeight: 600 }}>논리 vCPU 풀</div>
              <div style={{ fontSize: '1.5rem', fontWeight: 700, marginTop: '6px' }}>
                {nodesError ? (
                  <span style={{ fontSize: '1.125rem', color: '#f87171' }}>조회 실패</span>
                ) : logicalSummary.totalCores > 0 ? (
                  <>{logicalSummary.totalCores} <span style={{ fontSize: '0.875rem', fontWeight: 400 }}>Cores</span></>
                ) : (
                  '용량 미확인'
                )}
              </div>
              <div style={{ fontSize: '0.75rem', color: '#94a3b8', marginTop: '4px' }}>
                스케줄 가용: <strong>{logicalSummary.allocatableCores > 0 ? `${logicalSummary.allocatableCores} Cores` : '0 Cores'}</strong> · 실시간 점유: <span data-testid="logical-vcpu-used">{logicalSummary.usedCores !== null ? `${logicalSummary.usedCores} Cores` : '미제공 (API 미노출)'}</span>
              </div>
            </div>

            <div
              data-testid="logical-ram-card"
              style={{ padding: '16px', backgroundColor: '#1e293b', borderRadius: '10px', border: '1px solid #334155' }}
            >
              <div style={{ fontSize: '0.75rem', color: '#94a3b8', fontWeight: 600 }}>논리 통합 RAM 풀</div>
              <div style={{ fontSize: '1.5rem', fontWeight: 700, marginTop: '6px' }}>
                {nodesError ? (
                  <span style={{ fontSize: '1.125rem', color: '#f87171' }}>조회 실패</span>
                ) : logicalSummary.totalMemoryBytes > 0 ? (
                  formatBytes(logicalSummary.totalMemoryBytes)
                ) : (
                  '용량 미확인'
                )}
              </div>
              <div style={{ fontSize: '0.75rem', color: '#94a3b8', marginTop: '4px' }}>
                스케줄 가용: <strong>{formatBytes(logicalSummary.allocatableMemoryBytes)}</strong> · 점유: <span data-testid="logical-ram-used">{logicalSummary.usedMemoryBytes !== null ? formatBytes(logicalSummary.usedMemoryBytes) : '미제공 (API 미노출)'}</span>
              </div>
            </div>

            <div
              data-testid="logical-gpu-card"
              style={{ padding: '16px', backgroundColor: '#1e293b', borderRadius: '10px', border: '1px solid #334155' }}
            >
              <div style={{ fontSize: '0.75rem', color: '#94a3b8', fontWeight: 600 }}>논리 가속기 풀 (GPU)</div>
              <div style={{ fontSize: '1.5rem', fontWeight: 700, marginTop: '6px' }}>
                {nodesError ? (
                  <span style={{ fontSize: '1.125rem', color: '#f87171' }}>조회 실패</span>
                ) : logicalSummary.totalGpuCount > 0 ? (
                  <>{logicalSummary.totalGpuCount} <span style={{ fontSize: '0.875rem', fontWeight: 400 }}>장 (독립)</span></>
                ) : (
                  '없음 (0장)'
                )}
              </div>
              <div style={{ fontSize: '0.75rem', color: '#94a3b8', marginTop: '4px' }}>
                총 VRAM: <strong>{formatBytes(logicalSummary.totalGpuVramBytes)}</strong>
              </div>
            </div>

            <div
              data-testid="logical-storage-card"
              style={{ padding: '16px', backgroundColor: '#1e293b', borderRadius: '10px', border: '1px solid #334155' }}
            >
              <div style={{ fontSize: '0.75rem', color: '#94a3b8', fontWeight: 600 }}>분산 패브릭 스토리지 (inv://)</div>
              <div style={{ fontSize: '1.5rem', fontWeight: 700, marginTop: '6px' }}>
                {nodesError ? (
                  <span style={{ fontSize: '1.125rem', color: '#f87171' }}>조회 실패</span>
                ) : logicalSummary.totalStorageBytes > 0 ? (
                  formatBytes(logicalSummary.totalStorageBytes)
                ) : (
                  '용량 미확인'
                )}
              </div>
              <div style={{ fontSize: '0.75rem', color: '#94a3b8', marginTop: '4px' }}>
                점유: <span data-testid="logical-storage-used">{logicalSummary.usedStorageBytes !== null ? formatBytes(logicalSummary.usedStorageBytes) : '미제공 (API 미노출)'}</span>
              </div>
            </div>
          </div>

          {/* Physical Node Topology */}
          <div>
            <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: '12px' }}>
              <h2 style={{ fontSize: '0.9375rem', fontWeight: 600, margin: 0 }}>
                🖥️ 물리 노드별 실제 토폴로지 (Physical Nodes)
              </h2>
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
                      data-testid={`filter-${filter.id}-btn`}
                      onClick={() => setFilterMode(filter.id)}
                      style={{
                        padding: '4px 8px',
                        fontSize: '0.6875rem',
                        fontWeight: active ? 600 : 500,
                        borderRadius: '6px',
                        border: '1px solid',
                        borderColor: active ? '#3b82f6' : '#334155',
                        backgroundColor: active ? 'rgba(59, 130, 246, 0.2)' : 'transparent',
                        color: active ? '#93c5fd' : '#94a3b8',
                        cursor: 'pointer',
                      }}
                    >
                      {filter.label}
                    </button>
                  );
                })}
              </div>
            </div>

            {nodesError && (
              <div
                role="alert"
                data-testid="nodes-fetch-error-banner"
                style={{
                  padding: '16px',
                  backgroundColor: 'rgba(239, 68, 68, 0.1)',
                  border: '1px solid #ef4444',
                  borderRadius: '8px',
                  color: '#fca5a5',
                  marginBottom: '16px',
                }}
              >
                <div style={{ fontWeight: 600, fontSize: '0.8125rem' }}>
                  ⚠️ 물리 노드 레지스트리(GET /v1/nodes) 통신 오류
                </div>
                <div style={{ fontSize: '0.75rem', marginTop: '4px' }}>
                  {nodesError}
                </div>
                <div style={{ fontSize: '0.75rem', color: '#fca5a5', marginTop: '4px' }}>
                  ⚠️ 주의: 노드 목록이 비어 있는 것은 클러스터 노드가 제거된 것이 아니라, 제어 평면 API 조회가 실패한 것입니다. 섣부른 노드 재등록이나 장애 조치를 수행하지 마십시오.
                </div>
                {onRetryNodes && (
                  <button
                    type="button"
                    data-testid="nodes-retry-btn"
                    onClick={onRetryNodes}
                    style={{
                      marginTop: '10px',
                      padding: '6px 12px',
                      fontSize: '0.75rem',
                      backgroundColor: '#334155',
                      color: '#f8fafc',
                      border: '1px solid #475569',
                      borderRadius: '4px',
                      cursor: 'pointer',
                    }}
                  >
                    노드 목록 재조회 (Retry)
                  </button>
                )}
              </div>
            )}

            {!nodesError && nodesState === 'loading' && (
              <div
                data-testid="nodes-loading-state"
                style={{
                  padding: '24px',
                  textAlign: 'center',
                  color: '#94a3b8',
                  backgroundColor: '#1e293b',
                  borderRadius: '8px',
                  border: '1px solid #334155',
                }}
              >
                물리 노드 목록을 조회하는 중입니다...
              </div>
            )}

            {!nodesError && nodesState === 'idle' && (
              <div
                data-testid="nodes-idle-state"
                style={{
                  padding: '24px',
                  textAlign: 'center',
                  color: '#64748b',
                  backgroundColor: '#1e293b',
                  borderRadius: '8px',
                }}
              >
                노드 조회가 대기 상태입니다.
              </div>
            )}

            {!nodesError && nodesState !== 'loading' && nodesState !== 'idle' && filteredNodes.length === 0 && (
              <div
                data-testid="nodes-empty-state"
                role="status"
                aria-live="polite"
                style={{
                  padding: '24px',
                  backgroundColor: '#1e293b',
                  borderRadius: '8px',
                  border: '1px dashed #334155',
                  textAlign: 'center',
                }}
              >
                <div style={{ fontWeight: 600, fontSize: '0.875rem', color: '#94a3b8' }}>
                  ℹ️ 등록된 물리 노드가 없습니다 (정상 조회 결과: 0대).
                </div>
                <div style={{ fontSize: '0.75rem', color: '#cbd5e1', marginTop: '6px' }}>
                  클러스터에 등록된 활성 노드가 존재하지 않거나 현재 선택된 필터 조건에 부합하는 노드가 없습니다.
                </div>
              </div>
            )}

            {!nodesError && filteredNodes.length > 0 && (
              <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fill, minmax(300px, 1fr))', gap: '12px' }}>
                {filteredNodes.map((node) => {
                  const isSelected = selectedNodeId === node.id;
                  return (
                    <div
                      key={node.id}
                      data-testid={`node-card-${node.id}`}
                      onClick={() => {
                        setSelectedNodeId(node.id);
                        onSelectNode?.(node.id);
                      }}
                      style={{
                        padding: '14px',
                        backgroundColor: isSelected ? '#1e293b' : '#0f172a',
                        borderRadius: '8px',
                        border: isSelected ? '1.5px solid #3b82f6' : '1px solid #334155',
                        cursor: 'pointer',
                      }}
                    >
                      <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'flex-start' }}>
                        <div>
                          <div style={{ fontWeight: 600, fontSize: '0.875rem' }}>{node.hostname}</div>
                          <div style={{ fontSize: '0.6875rem', color: '#64748b' }}>
                            {node.id} {node.ipAddress ? `· ${node.ipAddress}` : ''}
                          </div>
                        </div>
                        <div style={{ display: 'flex', gap: '4px', alignItems: 'center' }}>
                          {node.observationOnly && (
                            <span
                              data-testid={`observe-only-badge-${node.id}`}
                              style={{
                                fontSize: '0.6875rem',
                                fontWeight: 600,
                                padding: '2px 6px',
                                borderRadius: '4px',
                                backgroundColor: 'rgba(234, 179, 8, 0.2)',
                                color: '#fbbf24',
                                border: '1px solid rgba(234, 179, 8, 0.4)',
                              }}
                            >
                              관측 전용
                            </span>
                          )}
                          {node.schedulable === false && (
                            <span
                              data-testid={`unschedulable-badge-${node.id}`}
                              style={{
                                fontSize: '0.6875rem',
                                fontWeight: 600,
                                padding: '2px 6px',
                                borderRadius: '4px',
                                backgroundColor: 'rgba(239, 68, 68, 0.15)',
                                color: '#f87171',
                                border: '1px solid rgba(239, 68, 68, 0.3)',
                              }}
                            >
                              스케줄 불가
                            </span>
                          )}
                          <span
                            style={{
                              fontSize: '0.6875rem',
                              fontWeight: 600,
                              padding: '2px 6px',
                              borderRadius: '4px',
                              backgroundColor: node.status === 'online' ? 'rgba(16, 185, 129, 0.15)' : 'rgba(239, 68, 68, 0.15)',
                              color: node.status === 'online' ? '#34d399' : '#f87171',
                            }}
                          >
                            {node.status.toUpperCase()}
                          </span>
                        </div>
                      </div>

                      <div style={{ fontSize: '0.75rem', color: '#94a3b8', marginTop: '8px', display: 'grid', gridTemplateColumns: '1fr 1fr', gap: '4px' }}>
                        <div data-testid={`node-cpu-${node.id}`}>CPU: {typeof node.cpuCores === 'number' && Number.isFinite(node.cpuCores) ? `${node.cpuCores}C` : '용량 미확인'} ({typeof node.allocatableCores === 'number' && Number.isFinite(node.allocatableCores) ? `${node.allocatableCores} 가용` : '0 가용'})</div>
                        <div data-testid={`node-ram-${node.id}`}>RAM: {formatBytes(node.memoryTotalBytes)}</div>
                        <div data-testid={`node-gpu-${node.id}`}>GPU: {typeof node.gpuCount === 'number' && Number.isFinite(node.gpuCount) ? (node.gpuCount === 0 ? '없음 (0대)' : `${node.gpuName || 'GPU'} (${node.gpuCount}대)`) : '장치 미확인'}</div>
                        <div data-testid={`node-storage-${node.id}`}>스토리지: {formatBytes(node.storageTotalBytes)}</div>
                      </div>

                      <div
                        data-testid={`node-utilization-status-${node.id}`}
                        role="status"
                        style={{
                          marginTop: '8px',
                          padding: '4px 8px',
                          borderRadius: '4px',
                          backgroundColor: 'rgba(51, 65, 85, 0.5)',
                          border: '1px solid #334155',
                          fontSize: '0.6875rem',
                          color: '#94a3b8',
                        }}
                      >
                        📊 자원 사용률: {node.telemetryUnavailable ? '미제공 (HTTP 읽기 경로 부재)' : `CPU ${node.cpuUsagePercent ?? 0}% · RAM ${formatBytes(node.memoryUsedBytes)}`}
                      </div>

                      <div style={{ display: 'flex', gap: '6px', marginTop: '10px', justifyContent: 'flex-end' }}>
                        <button
                          type="button"
                          onClick={(e) => {
                            e.stopPropagation();
                            setSelectedNodeId(node.id);
                            setActiveTab('nodes');
                          }}
                          style={{
                            padding: '4px 8px',
                            fontSize: '0.6875rem',
                            backgroundColor: 'rgba(59, 130, 246, 0.15)',
                            color: '#60a5fa',
                            border: '1px solid rgba(59, 130, 246, 0.3)',
                            borderRadius: '4px',
                            cursor: 'pointer',
                          }}
                        >
                          ⚙️ 상세 진단
                        </button>
                        {onOpenTerminal && (
                          <button
                            type="button"
                            onClick={(e) => {
                              e.stopPropagation();
                              onOpenTerminal(node.id);
                            }}
                            style={{
                              padding: '4px 8px',
                              fontSize: '0.6875rem',
                              backgroundColor: 'rgba(255, 255, 255, 0.05)',
                              color: '#e2e8f0',
                              border: '1px solid #334155',
                              borderRadius: '4px',
                              cursor: 'pointer',
                            }}
                          >
                            ⌨️ 터미널
                          </button>
                        )}
                      </div>
                    </div>
                  );
                })}
              </div>
            )}
          </div>
        </div>
      )}

      {/* ======================================================================= */}
      {/* TAB 2: 스토리지 기여 원장 (Storage Contributions & Locations)            */}
      {/* ======================================================================= */}
      {activeTab === 'storage' && (
        <div style={{ display: 'flex', flexDirection: 'column', gap: '20px' }}>
          {/* New Contribution Form */}
          <div style={{ padding: '16px', backgroundColor: '#1e293b', borderRadius: '8px', border: '1px solid #334155' }}>
            <h3 style={{ fontSize: '0.875rem', fontWeight: 600, margin: '0 0 12px 0' }}>
              ➕ 새 스토리지 폴더 기여 등록 (POST /v1/storage/contributions)
            </h3>
            <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fit, minmax(200px, 1fr))', gap: '10px' }}>
              <div>
                <label style={{ fontSize: '0.6875rem', color: '#94a3b8' }}>대상 물리 노드</label>
                <select
                  value={newContribNode}
                  data-testid="storage-node-select"
                  onChange={(e) => setNewContribNode(e.target.value)}
                  style={{ width: '100%', padding: '6px', borderRadius: '4px', backgroundColor: '#0f172a', border: '1px solid #334155', color: '#f8fafc', fontSize: '0.75rem' }}
                >
                  {nodes.map((n) => (
                    <option key={n.id} value={n.id}>
                      {n.hostname} ({n.id})
                    </option>
                  ))}
                </select>
              </div>

              <div>
                <label style={{ fontSize: '0.6875rem', color: '#94a3b8' }}>기여 경로 (Declared Path)</label>
                <input
                  type="text"
                  value={newContribPath}
                  data-testid="storage-path-input"
                  onChange={(e) => setNewContribPath(e.target.value)}
                  style={{ width: '100%', padding: '6px', borderRadius: '4px', backgroundColor: '#0f172a', border: '1px solid #334155', color: '#f8fafc', fontSize: '0.75rem' }}
                />
              </div>

              <div>
                <label style={{ fontSize: '0.6875rem', color: '#94a3b8' }}>접근 모드</label>
                <select
                  value={newContribMode}
                  onChange={(e) => setNewContribMode(e.target.value as any)}
                  style={{ width: '100%', padding: '6px', borderRadius: '4px', backgroundColor: '#0f172a', border: '1px solid #334155', color: '#f8fafc', fontSize: '0.75rem' }}
                >
                  <option value="read_write">읽기/쓰기 (Read/Write)</option>
                  <option value="read_only">읽기 전용 (Read Only)</option>
                </select>
              </div>

              <div>
                <label style={{ fontSize: '0.6875rem', color: '#94a3b8' }}>용량 (GB)</label>
                <input
                  type="number"
                  value={newContribCapacityGB}
                  onChange={(e) => setNewContribCapacityGB(Number(e.target.value))}
                  style={{ width: '100%', padding: '6px', borderRadius: '4px', backgroundColor: '#0f172a', border: '1px solid #334155', color: '#f8fafc', fontSize: '0.75rem' }}
                />
              </div>
            </div>

            <button
              type="button"
              data-testid="register-contribution-btn"
              onClick={handleRegisterContribution}
              disabled={nodes.length === 0}
              aria-disabled={nodes.length === 0}
              aria-describedby={nodes.length === 0 ? 'storage-no-nodes-notice' : undefined}
              title={nodes.length === 0 ? '등록 가능한 온라인 노드가 없습니다 (운영자 조치 필요).' : '기여 등록 제출'}
              style={{
                marginTop: '12px',
                padding: '6px 14px',
                fontSize: '0.75rem',
                fontWeight: 600,
                borderRadius: '6px',
                backgroundColor: nodes.length > 0 ? '#3b82f6' : '#475569',
                color: '#ffffff',
                border: 'none',
                cursor: nodes.length > 0 ? 'pointer' : 'not-allowed',
              }}
            >
              {nodes.length > 0 ? '기여 등록 제출' : '등록 가능 노드 없음 (제출 차단)'}
            </button>
            {nodes.length === 0 && (
              <div
                id="storage-no-nodes-notice"
                role="alert"
                data-testid="storage-no-nodes-notice"
                style={{ marginTop: '8px', fontSize: '0.75rem', color: '#f87171' }}
              >
                🛠️ <strong>[운영자 조치 필요]</strong>: 클러스터에 등록된 온라인 노드가 없습니다. 인프라 운영자에게 신규 노드 편입(Node 온보딩)을 요청하십시오.
              </div>
            )}
          </div>

          {/* Contributions List */}
          <div>
            <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: '8px' }}>
              <h3 style={{ fontSize: '0.875rem', fontWeight: 600, margin: 0 }}>
                📂 등록된 스토리지 기여 목록 (GET /v1/storage/contributions) {isLoadingStorage && <span style={{ fontSize: '0.75rem', color: '#94a3b8', fontWeight: 400 }}>(조회 중...)</span>}
              </h3>
              <button
                type="button"
                onClick={loadStorage}
                style={{ padding: '3px 8px', fontSize: '0.6875rem', backgroundColor: 'transparent', border: '1px solid #334155', color: '#94a3b8', borderRadius: '4px', cursor: 'pointer' }}
              >
                새로고침
              </button>
            </div>

            {storageError && (
              <div
                role="alert"
                data-testid="storage-error-banner"
                style={{
                  padding: '12px 14px',
                  backgroundColor: 'rgba(239, 68, 68, 0.1)',
                  border: '1px solid #ef4444',
                  borderRadius: '6px',
                  color: '#fca5a5',
                  marginBottom: '10px',
                  fontSize: '0.75rem',
                }}
              >
                <div style={{ fontWeight: 600, fontSize: '0.8125rem' }}>⚠️ 스토리지 정보 조회 실패</div>
                <div style={{ marginTop: '2px' }}>{storageError}</div>
                <button
                  type="button"
                  data-testid="storage-retry-btn"
                  onClick={loadStorage}
                  style={{ marginTop: '6px', padding: '3px 8px', fontSize: '0.6875rem', backgroundColor: '#334155', color: '#fff', border: 'none', borderRadius: '4px', cursor: 'pointer' }}
                >
                  재시도 (Retry)
                </button>
              </div>
            )}

            {!storageError && !isLoadingStorage && contributions.length === 0 && (
              <div data-testid="storage-empty-state" style={{ padding: '16px', textAlign: 'center', backgroundColor: '#1e293b', borderRadius: '8px', color: '#94a3b8', fontSize: '0.75rem' }}>
                등록된 스토리지 기여가 없습니다. 상단 폼에서 폴더를 기여하세요.
              </div>
            )}

            {!storageError && contributions.length > 0 && (
              <table style={{ width: '100%', borderCollapse: 'collapse', fontSize: '0.75rem', backgroundColor: '#1e293b', borderRadius: '8px', overflow: 'hidden' }}>
                <thead>
                  <tr style={{ backgroundColor: 'rgba(0,0,0,0.3)', textAlign: 'left', color: '#94a3b8' }}>
                    <th style={{ padding: '8px 12px' }}>기여 ID</th>
                    <th style={{ padding: '8px 12px' }}>노드</th>
                    <th style={{ padding: '8px 12px' }}>경로</th>
                    <th style={{ padding: '8px 12px' }}>모드</th>
                    <th style={{ padding: '8px 12px' }}>상태</th>
                    <th style={{ padding: '8px 12px' }}>가용 / 총용량</th>
                    <th style={{ padding: '8px 12px', textAlign: 'right' }}>조작</th>
                  </tr>
                </thead>
                <tbody>
                  {contributions.map((c) => (
                    <tr key={c.contributionId} style={{ borderBottom: '1px solid #334155' }}>
                      <td style={{ padding: '8px 12px', fontFamily: 'monospace' }}>{c.contributionId}</td>
                      <td style={{ padding: '8px 12px' }}>{c.nodeId}</td>
                      <td style={{ padding: '8px 12px' }}>{c.declaredPath}</td>
                      <td style={{ padding: '8px 12px' }}>
                        <span style={{ padding: '2px 5px', borderRadius: '3px', backgroundColor: c.mode === 'read_write' ? 'rgba(59, 130, 246, 0.2)' : 'rgba(148, 163, 184, 0.2)', color: c.mode === 'read_write' ? '#60a5fa' : '#94a3b8' }}>
                          {c.mode}
                        </span>
                      </td>
                      <td style={{ padding: '8px 12px' }}>
                        <span style={{ padding: '2px 5px', borderRadius: '3px', backgroundColor: c.status === 'active' ? 'rgba(16, 185, 129, 0.2)' : 'rgba(239, 68, 68, 0.2)', color: c.status === 'active' ? '#34d399' : '#f87171' }}>
                          {c.status}
                        </span>
                      </td>
                      <td style={{ padding: '8px 12px' }}>{formatBytes(c.availableBytes)} / {formatBytes(c.capacityBytes)}</td>
                      <td style={{ padding: '8px 12px', textAlign: 'right' }}>
                        {c.status === 'active' ? (
                          <button
                            type="button"
                            onClick={() => handleRevokeContribution(c.contributionId)}
                            style={{ padding: '2px 6px', fontSize: '0.6875rem', backgroundColor: 'rgba(239, 68, 68, 0.15)', color: '#f87171', border: '1px solid rgba(239, 68, 68, 0.3)', borderRadius: '4px', cursor: 'pointer' }}
                          >
                            해제 (Revoke)
                          </button>
                        ) : (
                          <button
                            type="button"
                            onClick={() => handleActivateContribution(c.contributionId)}
                            style={{ padding: '2px 6px', fontSize: '0.6875rem', backgroundColor: 'rgba(16, 185, 129, 0.15)', color: '#34d399', border: '1px solid rgba(16, 185, 129, 0.3)', borderRadius: '4px', cursor: 'pointer' }}
                          >
                            활성화 (Activate)
                          </button>
                        )}
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            )}
          </div>

          {/* Locations Section */}
          <div>
            <h3 style={{ fontSize: '0.875rem', fontWeight: 600, margin: '0 0 8px 0' }}>
              📍 데이터 위치 원장 (GET /v1/storage/locations)
            </h3>
            {locations.length === 0 ? (
              <div style={{ padding: '16px', textAlign: 'center', backgroundColor: '#1e293b', borderRadius: '8px', color: '#94a3b8', fontSize: '0.75rem' }}>
                확인된 데이터 위치 항목이 없습니다.
              </div>
            ) : (
              <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fill, minmax(280px, 1fr))', gap: '10px' }}>
                {locations.map((loc) => (
                  <div key={loc.locationId} style={{ padding: '10px', backgroundColor: '#1e293b', borderRadius: '6px', border: '1px solid #334155', fontSize: '0.75rem' }}>
                    <div style={{ fontWeight: 600, color: '#38bdf8', wordBreak: 'break-all' }}>{loc.uri}</div>
                    <div style={{ color: '#94a3b8', marginTop: '4px' }}>크기: {formatBytes(loc.byteSize)} · 종류: {loc.kind}</div>
                    <div style={{ color: '#64748b', fontSize: '0.6875rem', marginTop: '2px', fontFamily: 'monospace' }}>SHA: {loc.checksumSha256 || '미생성'}</div>
                  </div>
                ))}
              </div>
            )}
          </div>

          {/* Storage Observation Section (StorageObservationView) */}
          <div
            data-testid="storage-observation-section"
            style={{ padding: '16px', backgroundColor: '#1e293b', borderRadius: '8px', border: '1px solid #334155' }}
          >
            <h3 style={{ fontSize: '0.875rem', fontWeight: 600, margin: '0 0 8px 0' }}>
              🔬 스토리지 샘플 무결성 관측 (StorageObservationView)
            </h3>
            <p style={{ fontSize: '0.75rem', color: '#94a3b8', margin: '0 0 12px 0' }}>
              노드 에이전트가 기록한 스토리지 점유 증명(verify_sample) 관측 결과를 대조합니다. currentHealth는 서버 정의에 따라 "unknown"으로 보존되며, 임의의 "healthy" 상태를 합성하지 않습니다.
            </p>

            <div style={{ display: 'flex', gap: '8px', alignItems: 'center', marginBottom: '12px' }}>
              <input
                type="text"
                data-testid="storage-sample-req-input"
                value={sampleRequestId}
                onChange={(e) => setSampleRequestId(e.target.value)}
                placeholder="샘플 요청 ID (예: 66666666-6666-4666-8666-666666666666)"
                style={{
                  flex: 1,
                  padding: '6px 10px',
                  borderRadius: '4px',
                  backgroundColor: '#0f172a',
                  border: '1px solid #334155',
                  color: '#f8fafc',
                  fontSize: '0.75rem',
                  fontFamily: 'monospace',
                }}
              />
              <button
                type="button"
                data-testid="fetch-storage-observation-btn"
                onClick={handleFetchStorageObservation}
                disabled={isLoadingObservation || !projectId?.trim() || !runId?.trim() || !sampleRequestId.trim()}
                aria-disabled={isLoadingObservation || !projectId?.trim() || !runId?.trim() || !sampleRequestId.trim()}
                aria-describedby={(!projectId?.trim() || !runId?.trim()) ? 'storage-observation-context-warning' : undefined}
                title={(!projectId?.trim() || !runId?.trim()) ? '프로젝트 및 실행 컨텍스트가 필요합니다 (사용자 조치 필요).' : !sampleRequestId.trim() ? '샘플 요청 ID가 필요합니다.' : '샘플 관측 조회'}
                style={{
                  padding: '6px 14px',
                  fontSize: '0.75rem',
                  fontWeight: 600,
                  borderRadius: '4px',
                  backgroundColor: (!projectId?.trim() || !runId?.trim() || !sampleRequestId.trim()) ? '#475569' : '#3b82f6',
                  color: '#ffffff',
                  border: 'none',
                  cursor: (!projectId?.trim() || !runId?.trim() || !sampleRequestId.trim()) ? 'not-allowed' : 'pointer',
                }}
              >
                {isLoadingObservation ? '조회 중...' : '샘플 관측 조회'}
              </button>
            </div>

            {(!projectId?.trim() || !runId?.trim()) && (
              <div
                id="storage-observation-context-warning"
                role="alert"
                data-testid="storage-observation-context-warning"
                style={{ fontSize: '0.6875rem', color: '#fbbf24', marginBottom: '8px', lineHeight: '1.4' }}
              >
                <div>⚠️ 활성 프로젝트/실행(Run) 컨텍스트가 없어 스토리지 샘플 조회가 비활성화되었습니다 (근거 없는 호출 방지).</div>
                <div style={{ marginTop: '2px', color: '#fed7aa' }}>
                  👉 <strong>[사용자 조치 필요]</strong>: 상단 탐색기 또는 작업 공간(Workspace)에서 프로젝트 및 실행(Run)을 선택하여 컨텍스트를 활성화하십시오.
                </div>
              </div>
            )}

            {observationError && (
              <div
                role="alert"
                data-testid="storage-observation-error"
                style={{
                  padding: '8px 12px',
                  borderRadius: '6px',
                  backgroundColor: 'rgba(239, 68, 68, 0.2)',
                  border: '1px solid #ef4444',
                  color: '#fca5a5',
                  fontSize: '0.75rem',
                  marginBottom: '10px',
                }}
              >
                ❌ {observationError}
              </div>
            )}

            {storageObservation && (
              <div
                data-testid="storage-observation-container"
                style={{
                  padding: '12px',
                  borderRadius: '6px',
                  backgroundColor: '#0f172a',
                  border: '1px solid #334155',
                  display: 'flex',
                  flexDirection: 'column',
                  gap: '8px',
                  fontSize: '0.75rem',
                }}
              >
                <div style={{ display: 'flex', justifyContent: 'space-between' }}>
                  <span>요청 ID: <code data-testid="storage-observation-req-id" style={{ color: '#38bdf8' }}>{storageObservation.requestId}</code></span>
                  <span
                    data-testid="storage-observation-status"
                    style={{
                      fontWeight: 600,
                      padding: '2px 6px',
                      borderRadius: '4px',
                      backgroundColor: storageObservation.status === 'recorded' ? 'rgba(16, 185, 129, 0.2)' : 'rgba(234, 179, 8, 0.2)',
                      color: storageObservation.status === 'recorded' ? '#34d399' : '#fbbf24',
                    }}
                  >
                    상태: {storageObservation.status}
                  </span>
                </div>

                <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fit, minmax(180px, 1fr))', gap: '8px' }}>
                  <div>
                    현재 건전성:{' '}
                    <strong data-testid="storage-observation-health" style={{ color: '#94a3b8' }}>
                      {storageObservation.currentHealth}
                    </strong>
                    <span style={{ fontSize: '0.6875rem', color: '#64748b', marginLeft: '4px' }}>(불변 unknown)</span>
                  </div>
                  <div>
                    운영 인수 평가:{' '}
                    <strong data-testid="storage-observation-acceptance" style={{ color: '#94a3b8' }}>
                      {storageObservation.operationalAcceptanceAssessed ? 'true' : 'false (미평가)'}
                    </strong>
                  </div>
                </div>

                {storageObservation.observation ? (
                  <div
                    data-testid="storage-observation-detail"
                    style={{
                      marginTop: '6px',
                      padding: '8px',
                      borderRadius: '4px',
                      backgroundColor: 'rgba(255, 255, 255, 0.03)',
                      display: 'flex',
                      flexDirection: 'column',
                      gap: '4px',
                    }}
                  >
                    <div style={{ display: 'flex', justifyContent: 'space-between' }}>
                      <span>
                        무결성 증명:{' '}
                        <strong data-testid="storage-observation-integrity" style={{ color: '#34d399' }}>
                          {storageObservation.observation.integrityVerified ? '무결성 확인됨 (VERIFIED)' : '미확인'}
                        </strong>
                      </span>
                      <span>
                        증거 ID: <code data-testid="storage-observation-evidence">{storageObservation.observation.evidenceId}</code>
                      </span>
                    </div>
                    <div data-testid="storage-observation-counts" style={{ color: '#94a3b8' }}>
                      표본수: {storageObservation.observation.sampled} · 검사: {storageObservation.observation.examined} · 불일치: {storageObservation.observation.mismatches} · 검증불가: {storageObservation.observation.unverifiable} · 미표본: {storageObservation.observation.unsampled}
                    </div>
                  </div>
                ) : (
                  <div data-testid="storage-observation-empty" style={{ color: '#94a3b8', fontStyle: 'italic' }}>
                    관측 결과 없음 (status: {storageObservation.status})
                  </div>
                )}
              </div>
            )}
          </div>
        </div>
      )}

      {/* ======================================================================= */}
      {/* TAB 3: 자원 풀 및 분산 배치 계획 (Pools & Placement Plans)              */}
      {/* ======================================================================= */}
      {activeTab === 'pools' && (
        <div style={{ display: 'flex', flexDirection: 'column', gap: '20px' }}>
          {/* Pool Capacity Card */}
          <div style={{ padding: '16px', backgroundColor: '#1e293b', borderRadius: '8px', border: '1px solid #334155' }}>
            <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: '10px' }}>
              <h3 style={{ fontSize: '0.875rem', fontWeight: 600, margin: 0 }}>
                🏊 풀 집계 용량 (GET /v1/pools/{selectedPoolId}/capacity)
              </h3>
              <div style={{ display: 'flex', alignItems: 'center', gap: '6px', fontSize: '0.75rem', color: '#94a3b8' }}>
                <span>풀 ID:</span>
                <input
                  type="text"
                  value={selectedPoolId}
                  onChange={(e) => {
                    setSelectedPoolId(e.target.value);
                    loadPoolData(e.target.value);
                  }}
                  style={{ padding: '2px 6px', backgroundColor: '#0f172a', border: '1px solid #334155', color: '#fff', borderRadius: '4px', fontSize: '0.75rem', width: '120px' }}
                />
              </div>
            </div>

            {poolCapacityState === 'loading' && (
              <div data-testid="pool-capacity-loading" style={{ padding: '16px', textAlign: 'center', color: '#94a3b8', backgroundColor: 'rgba(0,0,0,0.2)', borderRadius: '6px' }}>
                자원 풀 용량 정보를 조회 중입니다...
              </div>
            )}

            {poolCapacityState === 'error' && (
              <div role="alert" data-testid="pool-capacity-error" style={{ padding: '14px', backgroundColor: 'rgba(239, 68, 68, 0.1)', border: '1px solid #ef4444', borderRadius: '6px', color: '#fca5a5' }}>
                <div style={{ fontWeight: 600, fontSize: '0.8125rem' }}>⚠️ 자원 풀 용량 조회 실패</div>
                <div style={{ fontSize: '0.75rem', marginTop: '2px' }}>{poolCapacityError}</div>
                <button
                  type="button"
                  data-testid="pool-capacity-retry"
                  onClick={() => loadPoolData(selectedPoolId)}
                  style={{ marginTop: '8px', padding: '4px 10px', fontSize: '0.6875rem', backgroundColor: '#334155', color: '#fff', border: 'none', borderRadius: '4px', cursor: 'pointer' }}
                >
                  재시도 (Retry)
                </button>
              </div>
            )}

            {poolCapacity && poolCapacityState !== 'error' && (
              <div style={{ display: 'grid', gridTemplateColumns: 'repeat(3, 1fr)', gap: '10px' }}>
                <div style={{ padding: '10px', backgroundColor: 'rgba(0,0,0,0.2)', borderRadius: '6px' }}>
                  <div style={{ fontSize: '0.6875rem', color: '#94a3b8' }}>총 제공량 (Total Offered)</div>
                  <div style={{ fontSize: '1.125rem', fontWeight: 700, color: '#60a5fa', marginTop: '4px' }}>
                    {poolCapacity.totalOffered.cpuMillicores / 1000}C · {formatBytes(poolCapacity.totalOffered.ramBytes)} · {poolCapacity.totalOffered.gpuDevices} GPU
                  </div>
                </div>

                <div style={{ padding: '10px', backgroundColor: 'rgba(0,0,0,0.2)', borderRadius: '6px' }}>
                  <div style={{ fontSize: '0.6875rem', color: '#f59e0b' }}>단일 노드 최대 한도 (Largest Single)</div>
                  <div style={{ fontSize: '1.125rem', fontWeight: 700, color: '#fbbf24', marginTop: '4px' }}>
                    {poolCapacity.largestSingleNode.cpuMillicores / 1000}C · {formatBytes(poolCapacity.largestSingleNode.ramBytes)} · {poolCapacity.largestSingleNode.gpuDevices} GPU
                  </div>
                </div>

                <div style={{ padding: '10px', backgroundColor: 'rgba(0,0,0,0.2)', borderRadius: '6px' }}>
                  <div style={{ fontSize: '0.6875rem', color: '#10b981' }}>현재 유휴 여유량 (Spare Now)</div>
                  <div style={{ fontSize: '1.125rem', fontWeight: 700, color: '#34d399', marginTop: '4px' }}>
                    {poolCapacity.spareNow.cpuMillicores / 1000}C · {formatBytes(poolCapacity.spareNow.ramBytes)} · {poolCapacity.spareNow.gpuDevices} GPU
                  </div>
                </div>
              </div>
            )}
          </div>

          {/* Inline Pool Action Banner */}
          {poolMessage && (
            <div
              role={poolMessage.startsWith('❌') ? 'alert' : 'status'}
              data-testid={poolMessage.startsWith('❌') ? 'pool-action-error-banner-inline' : 'pool-action-success-banner-inline'}
              style={{
                padding: '10px 14px',
                borderRadius: '6px',
                backgroundColor: poolMessage.startsWith('❌') ? 'rgba(239, 68, 68, 0.2)' : 'rgba(59, 130, 246, 0.2)',
                color: poolMessage.startsWith('❌') ? '#fca5a5' : '#93c5fd',
                border: poolMessage.startsWith('❌') ? '1px solid rgba(239, 68, 68, 0.4)' : '1px solid rgba(59, 130, 246, 0.3)',
                fontSize: '0.8125rem',
              }}
            >
              {poolMessage}
            </div>
          )}

          {/* Pool Member Management */}
          <div style={{ padding: '16px', backgroundColor: '#1e293b', borderRadius: '8px', border: '1px solid #334155' }}>
            <h3 style={{ fontSize: '0.875rem', fontWeight: 600, margin: '0 0 10px 0' }}>
              👥 풀 멤버 노드 관리 (PUT/DELETE /v1/pools/{selectedPoolId}/members/&#123;node_id&#125;)
            </h3>
            <div style={{ display: 'flex', gap: '8px', alignItems: 'center', marginBottom: '12px' }}>
              <select
                value={memberNodeToAdd}
                data-testid="pool-member-select"
                onChange={(e) => setMemberNodeToAdd(e.target.value)}
                style={{ padding: '6px', borderRadius: '4px', backgroundColor: '#0f172a', border: '1px solid #334155', color: '#f8fafc', fontSize: '0.75rem' }}
              >
                {nodes.map((n) => (
                  <option
                    key={n.id}
                    value={n.id}
                    disabled={n.observationOnly || n.schedulable === false}
                  >
                    {n.hostname} ({n.id}){n.observationOnly ? ' [관측 전용 - 편입 불가]' : ''}
                  </option>
                ))}
              </select>
              <button
                type="button"
                data-testid="add-pool-member-btn"
                onClick={handleAddMember}
                style={{ padding: '6px 12px', fontSize: '0.75rem', backgroundColor: '#3b82f6', color: '#ffffff', border: 'none', borderRadius: '6px', cursor: 'pointer' }}
              >
                멤버 추가
              </button>
            </div>

            <div style={{ display: 'flex', flexWrap: 'wrap', gap: '8px' }}>
              {poolMembers.map((mId) => (
                <div key={mId} style={{ display: 'flex', alignItems: 'center', gap: '6px', padding: '4px 10px', backgroundColor: '#0f172a', border: '1px solid #334155', borderRadius: '6px', fontSize: '0.75rem' }}>
                  <span>🖥️ {mId}</span>
                  <button
                    type="button"
                    onClick={() => handleRemoveMember(mId)}
                    style={{ background: 'none', border: 'none', color: '#f87171', cursor: 'pointer', fontWeight: 700 }}
                  >
                    ×
                  </button>
                </div>
              ))}
            </div>
          </div>

          {/* Placement Preview & Distributed Planning */}
          <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fit, minmax(320px, 1fr))', gap: '14px' }}>
            {/* Preview Box */}
            <div style={{ padding: '16px', backgroundColor: '#1e293b', borderRadius: '8px', border: '1px solid #334155' }}>
              <h3 style={{ fontSize: '0.875rem', fontWeight: 600, margin: '0 0 10px 0' }}>
                🔍 배치 미리보기 (GET /v1/pools/{selectedPoolId}/placement-preview)
              </h3>
              <div style={{ display: 'grid', gridTemplateColumns: 'repeat(3, 1fr)', gap: '6px', fontSize: '0.75rem' }}>
                <div>
                  <label style={{ color: '#94a3b8' }}>CPU (mC)</label>
                  <input
                    type="number"
                    value={placementReq.cpuMillicores}
                    onChange={(e) => setPlacementReq((p) => ({ ...p, cpuMillicores: Number(e.target.value) }))}
                    style={{ width: '100%', padding: '4px', backgroundColor: '#0f172a', border: '1px solid #334155', color: '#fff', borderRadius: '4px' }}
                  />
                </div>
                <div>
                  <label style={{ color: '#94a3b8' }}>RAM (GB)</label>
                  <input
                    type="number"
                    value={placementReq.ramBytes / 1024 ** 3}
                    onChange={(e) => setPlacementReq((p) => ({ ...p, ramBytes: Number(e.target.value) * 1024 ** 3 }))}
                    style={{ width: '100%', padding: '4px', backgroundColor: '#0f172a', border: '1px solid #334155', color: '#fff', borderRadius: '4px' }}
                  />
                </div>
                <div>
                  <label style={{ color: '#94a3b8' }}>GPU 장수</label>
                  <input
                    type="number"
                    value={placementReq.gpuDevices}
                    onChange={(e) => setPlacementReq((p) => ({ ...p, gpuDevices: Number(e.target.value) }))}
                    style={{ width: '100%', padding: '4px', backgroundColor: '#0f172a', border: '1px solid #334155', color: '#fff', borderRadius: '4px' }}
                  />
                </div>
              </div>

              <button
                type="button"
                onClick={handlePlacementPreview}
                style={{ marginTop: '10px', padding: '6px 12px', fontSize: '0.75rem', backgroundColor: '#10b981', color: '#fff', border: 'none', borderRadius: '6px', cursor: 'pointer' }}
              >
                적격 노드 순위 조회
              </button>

              {placementPreview && (
                <div style={{ marginTop: '10px', fontSize: '0.75rem' }}>
                  <div style={{ fontWeight: 600, color: '#34d399', marginBottom: '4px' }}>유휴 우선 추천 노드:</div>
                  {placementPreview.candidates.map((c, idx) => (
                    <div key={c.nodeId} style={{ padding: '4px 6px', backgroundColor: 'rgba(0,0,0,0.2)', borderRadius: '4px', marginBottom: '4px' }}>
                      {idx + 1}. <strong>{c.hostname}</strong> ({c.availableCpuMillicores / 1000}C 가용, {c.availableGpuDevices} GPU)
                    </div>
                  ))}
                </div>
              )}
            </div>

            {/* Plan Box */}
            <div style={{ padding: '16px', backgroundColor: '#1e293b', borderRadius: '8px', border: '1px solid #334155' }}>
              <h3 style={{ fontSize: '0.875rem', fontWeight: 600, margin: '0 0 10px 0' }}>
                🗺️ 분산 배치 계획 수립 (POST /v1/pools/{selectedPoolId}/plans)
              </h3>
              <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr 1fr', gap: '6px', fontSize: '0.75rem' }}>
                <div>
                  <label style={{ color: '#94a3b8' }}>Run ID</label>
                  <input
                    type="text"
                    data-testid="plan-run-id-input"
                    value={planRunId}
                    onChange={(e) => setPlanRunId(e.target.value)}
                    placeholder="승인 Run ID 입력..."
                    style={{ width: '100%', padding: '4px', backgroundColor: '#0f172a', border: '1px solid #334155', color: '#fff', borderRadius: '4px' }}
                  />
                </div>
                <div>
                  <label style={{ color: '#94a3b8' }}>전략</label>
                  <select
                    value={planStrategy}
                    onChange={(e) => setPlanStrategy(e.target.value as any)}
                    style={{ width: '100%', padding: '4px', backgroundColor: '#0f172a', border: '1px solid #334155', color: '#fff', borderRadius: '4px' }}
                  >
                    <option value="spread">분산 (Spread - 권장)</option>
                    <option value="binpack">밀집 (Binpack)</option>
                  </select>
                </div>
                <div>
                  <label style={{ color: '#94a3b8' }}>샤드 수 (Shards)</label>
                  <input
                    type="number"
                    value={planShardCount}
                    onChange={(e) => setPlanShardCount(Number(e.target.value))}
                    style={{ width: '100%', padding: '4px', backgroundColor: '#0f172a', border: '1px solid #334155', color: '#fff', borderRadius: '4px' }}
                  />
                </div>
              </div>

              <button
                type="button"
                data-testid="create-plan-btn"
                onClick={handleCreatePlan}
                disabled={!planRunId.trim()}
                aria-disabled={!planRunId.trim()}
                aria-describedby={!planRunId.trim() ? 'plan-run-id-user-action-notice' : undefined}
                title={!planRunId.trim() ? '승인된 분산 실행 Run ID(planRunId)가 필요합니다 (사용자 조치 필요).' : '계획 확정 및 샤드 할당'}
                style={{
                  marginTop: '10px',
                  padding: '6px 12px',
                  fontSize: '0.75rem',
                  backgroundColor: planRunId.trim() ? '#8b5cf6' : '#475569',
                  color: '#fff',
                  border: 'none',
                  borderRadius: '6px',
                  cursor: planRunId.trim() ? 'pointer' : 'not-allowed',
                }}
              >
                {planRunId.trim() ? '계획 확정 및 샤드 할당' : '승인 Run ID 필요 (생성 불가)'}
              </button>

              {!planRunId.trim() && (
                <div
                  id="plan-run-id-user-action-notice"
                  role="alert"
                  data-testid="plan-run-id-user-action-notice"
                  style={{ marginTop: '6px', fontSize: '0.6875rem', color: '#fed7aa' }}
                >
                  👉 <strong>[사용자 조치 필요]</strong>: 승인된 분산 실행 Run ID(예: run_...)를 입력창에 입력하면 배치 계획 생성이 활성화됩니다.
                </div>
              )}

              {planResult && (
                <div style={{ marginTop: '10px', fontSize: '0.75rem' }}>
                  <div style={{ fontWeight: 600, color: '#c084fc' }}>생성된 계획: {planResult.planId}</div>
                  {planResult.placements.map((p) => (
                    <div key={p.shardIndex} style={{ padding: '3px 6px', backgroundColor: 'rgba(0,0,0,0.2)', borderRadius: '4px', marginTop: '2px' }}>
                      샤드 #{p.shardIndex} ➔ 노드 {p.nodeId}
                    </div>
                  ))}
                </div>
              )}
            </div>
          </div>
        </div>
      )}

      {/* ======================================================================= */}
      {/* TAB 4: 노드 상세 & 라이브니스 통제 (Node Inspector & Liveness)         */}
      {/* ======================================================================= */}
      {activeTab === 'nodes' && (
        <div style={{ display: 'flex', flexDirection: 'column', gap: '20px' }}>
          {/* Node Selector & Actions */}
          <div style={{ padding: '16px', backgroundColor: '#1e293b', borderRadius: '8px', border: '1px solid #334155', display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
            <div style={{ display: 'flex', gap: '10px', alignItems: 'center' }}>
              <label style={{ fontSize: '0.75rem', color: '#94a3b8' }}>검사 노드:</label>
              <select
                value={selectedNodeId || ''}
                data-testid="node-selector"
                onChange={(e) => setSelectedNodeId(e.target.value)}
                style={{ padding: '6px', borderRadius: '4px', backgroundColor: '#0f172a', border: '1px solid #334155', color: '#f8fafc', fontSize: '0.75rem' }}
              >
                {nodes.map((n) => (
                  <option key={n.id} value={n.id}>
                    {n.hostname} ({n.id})
                  </option>
                ))}
              </select>
            </div>

            <div style={{ display: 'flex', gap: '8px' }}>
              <button
                type="button"
                data-testid="send-heartbeat-btn"
                onClick={handleSendHeartbeat}
                style={{ padding: '6px 12px', fontSize: '0.75rem', backgroundColor: '#10b981', color: '#fff', border: 'none', borderRadius: '6px', cursor: 'pointer' }}
              >
                💓 하트비트 시퀀스 전송 (POST /v1/nodes/{selectedNodeId}/heartbeats)
              </button>
            </div>
          </div>

          {/* Detailed Hardware Capabilities */}
          {isLoadingNodeDetail && (
            <div data-testid="node-detail-loading" style={{ padding: '16px', backgroundColor: '#1e293b', borderRadius: '8px', border: '1px solid #334155', color: '#94a3b8', textAlign: 'center' }}>
              노드 상세 정보를 조회 중입니다...
            </div>
          )}

          {nodeDetailError && !isLoadingNodeDetail && (
            <div role="alert" data-testid="node-detail-error" style={{ padding: '14px', backgroundColor: 'rgba(239, 68, 68, 0.1)', border: '1px solid #ef4444', borderRadius: '8px', color: '#fca5a5' }}>
              <div style={{ fontWeight: 600, fontSize: '0.8125rem' }}>⚠️ 노드 상세 정보 조회 실패</div>
              <div style={{ fontSize: '0.75rem', marginTop: '2px' }}>{nodeDetailError}</div>
              {selectedNodeId && (
                <button
                  type="button"
                  data-testid="node-detail-retry"
                  onClick={() => loadNodeDetailData(selectedNodeId)}
                  style={{ marginTop: '8px', padding: '4px 10px', fontSize: '0.6875rem', backgroundColor: '#334155', color: '#fff', border: 'none', borderRadius: '4px', cursor: 'pointer' }}
                >
                  재시도 (Retry)
                </button>
              )}
            </div>
          )}

          {nodeDetail && !nodeDetailError && (
            <div style={{ padding: '16px', backgroundColor: '#1e293b', borderRadius: '8px', border: '1px solid #334155' }}>
              <h3 style={{ fontSize: '0.875rem', fontWeight: 600, margin: '0 0 10px 0' }}>
                🔍 노드 상세 및 자원 역량 (GET /v1/nodes/{nodeDetail.node.nodeId}) {isLoadingNodeDetail && <span style={{ fontSize: '0.75rem', color: '#94a3b8', fontWeight: 400 }}>(조회 중...)</span>}
              </h3>
              <div style={{ display: 'grid', gridTemplateColumns: 'repeat(4, 1fr)', gap: '10px', fontSize: '0.75rem', marginBottom: '14px' }}>
                <div>호스트: <strong>{nodeDetail.node.hostname}</strong></div>
                <div>OS: <strong>{nodeDetail.node.osType}</strong></div>
                <div>하트비트 시퀀스: <strong>#{nodeDetail.node.heartbeatSequence}</strong></div>
                <div>상태: <strong style={{ color: '#34d399' }}>{nodeDetail.node.status}</strong></div>
              </div>

              <div
                data-testid="capabilities-static-capacity-notice"
                role="status"
                style={{
                  padding: '8px 12px',
                  marginBottom: '12px',
                  borderRadius: '6px',
                  backgroundColor: 'rgba(59, 130, 246, 0.1)',
                  border: '1px solid rgba(59, 130, 246, 0.3)',
                  color: '#93c5fd',
                  fontSize: '0.75rem',
                  lineHeight: '1.4',
                }}
              >
                ℹ️ <strong>정적 용량과 사용률 구별 고지</strong>: 아래 원장의 수량은 노드가 등록(Enrollment) 시점에 신고한 <strong>정적 하드웨어 총용량(Total Capacity)</strong>입니다. 실시간 동적 사용량(Used Quantity)은 백엔드 내부에서만 수집되며 현재 외부에 노출되는 HTTP 읽기 라우트가 부재(미제공)하여 표시되지 않습니다.
              </div>

              <div style={{ fontWeight: 600, fontSize: '0.75rem', marginBottom: '6px', color: '#94a3b8' }}>하드웨어 Capabilities 원장:</div>
              <table style={{ width: '100%', borderCollapse: 'collapse', fontSize: '0.75rem', backgroundColor: '#0f172a', borderRadius: '6px', overflow: 'hidden' }}>
                <thead>
                  <tr style={{ textAlign: 'left', color: '#94a3b8', borderBottom: '1px solid #334155' }}>
                    <th style={{ padding: '6px 10px' }}>종류 (Kind)</th>
                    <th style={{ padding: '6px 10px' }}>벤더 / 모델</th>
                    <th style={{ padding: '6px 10px' }}>수량</th>
                    <th style={{ padding: '6px 10px' }}>단위</th>
                    <th style={{ padding: '6px 10px' }}>분할 가능 여부</th>
                  </tr>
                </thead>
                <tbody>
                  {nodeDetail.capabilities.map((c) => (
                    <tr key={c.capabilityId} style={{ borderBottom: '1px solid #1e293b' }}>
                      <td style={{ padding: '6px 10px', fontWeight: 600 }}>{c.kind}</td>
                      <td style={{ padding: '6px 10px' }}>{c.vendor || '-'} {c.model || ''}</td>
                      <td style={{ padding: '6px 10px' }}>{c.totalQuantity}</td>
                      <td style={{ padding: '6px 10px' }}>{c.unit}</td>
                      <td style={{ padding: '6px 10px' }}>{c.divisible ? '예 (Divisible)' : '단일 장치'}</td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          )}
        </div>
      )}

      {/* ======================================================================= */}
      {/* TAB 5: 디스커버리 & 노드 승인 (Discovery & Candidate Admission)          */}
      {/* ======================================================================= */}
      {activeTab === 'discovery' && (
        <div style={{ display: 'flex', flexDirection: 'column', gap: '20px' }}>
          {/* Announcement Broadcast Form */}
          <div style={{ padding: '16px', backgroundColor: '#1e293b', borderRadius: '8px', border: '1px solid #334155' }}>
            <h3 style={{ fontSize: '0.875rem', fontWeight: 600, margin: '0 0 10px 0' }}>
              📡 미등록 머신 안내 방송 전송 (POST /v1/discovery/announcements)
            </h3>
            {(!tenantId || !tenantId.trim()) && (
              <div
                id="discovery-tenant-required-notice"
                role="alert"
                aria-live="assertive"
                data-testid="discovery-tenant-required-notice"
                style={{
                  padding: '8px 12px',
                  marginBottom: '12px',
                  borderRadius: '6px',
                  backgroundColor: 'rgba(239, 68, 68, 0.15)',
                  border: '1px solid #ef4444',
                  color: '#fca5a5',
                  fontSize: '0.75rem',
                  lineHeight: '1.4',
                }}
              >
                <div>⚠️ [테넌트 격리 차단]: 인증된 세션 테넌트 식별자(tenantId)가 없어 안내 방송 전송이 비활성화되었습니다. (위조 테넌트 합성 및 후보 한도 소진 방지)</div>
                <div style={{ marginTop: '4px', fontSize: '0.6875rem', color: '#fed7aa' }}>
                  👉 <strong>[사용자 조치 필요]</strong>: 상단 프로필/인증 설정에서 테넌트가 할당된 계정으로 로그인하거나 활성 테넌트를 선택하면 안내 방송 전송이 활성화됩니다.
                </div>
              </div>
            )}
            <div style={{ display: 'flex', gap: '10px', alignItems: 'center' }}>
              <input
                type="text"
                value={announcementHostname}
                onChange={(e) => setAnnouncementHostname(e.target.value)}
                placeholder="호스트 이름"
                style={{ padding: '6px', borderRadius: '4px', backgroundColor: '#0f172a', border: '1px solid #334155', color: '#fff', fontSize: '0.75rem' }}
              />
              <select
                value={announcementOs}
                onChange={(e) => setAnnouncementOs(e.target.value as any)}
                style={{ padding: '6px', borderRadius: '4px', backgroundColor: '#0f172a', border: '1px solid #334155', color: '#fff', fontSize: '0.75rem' }}
              >
                <option value="windows">Windows</option>
                <option value="linux">Linux</option>
              </select>
              <button
                type="button"
                data-testid="broadcast-announcement-btn"
                onClick={handleBroadcastAnnouncement}
                disabled={!tenantId || !tenantId.trim()}
                aria-disabled={!tenantId || !tenantId.trim()}
                aria-describedby={!tenantId || !tenantId.trim() ? 'discovery-tenant-required-notice' : undefined}
                title={!tenantId || !tenantId.trim() ? '인증된 세션 테넌트(tenantId)가 필요합니다 (사용자 조치 필요).' : '안내 방송 브로드캐스트'}
                style={{
                  padding: '6px 12px',
                  fontSize: '0.75rem',
                  backgroundColor: tenantId && tenantId.trim() ? '#3b82f6' : '#475569',
                  color: '#fff',
                  border: 'none',
                  borderRadius: '6px',
                  cursor: tenantId && tenantId.trim() ? 'pointer' : 'not-allowed',
                }}
              >
                안내 방송 브로드캐스트
              </button>
            </div>
          </div>

          {/* Inline Discovery Action Banner */}
          {discoveryMessage && (
            <div
              role={discoveryMessage.startsWith('❌') || discoveryMessage.startsWith('⚠️') ? 'alert' : 'status'}
              data-testid={discoveryMessage.startsWith('❌') || discoveryMessage.startsWith('⚠️') ? 'discovery-action-error-banner-inline' : 'discovery-action-success-banner-inline'}
              style={{
                padding: '10px 14px',
                borderRadius: '6px',
                backgroundColor: discoveryMessage.startsWith('❌') || discoveryMessage.startsWith('⚠️') ? 'rgba(239, 68, 68, 0.2)' : 'rgba(16, 185, 129, 0.2)',
                color: discoveryMessage.startsWith('❌') || discoveryMessage.startsWith('⚠️') ? '#fca5a5' : '#34d399',
                border: discoveryMessage.startsWith('❌') || discoveryMessage.startsWith('⚠️') ? '1px solid rgba(239, 68, 68, 0.4)' : '1px solid rgba(16, 185, 129, 0.3)',
                fontSize: '0.8125rem',
              }}
            >
              {discoveryMessage}
            </div>
          )}

          {/* Admission Token Result Modal / Alert */}
          {admissionResult && (
            <div
              role="status"
              data-testid="admission-result-modal"
              style={{ padding: '14px', borderRadius: '8px', backgroundColor: 'rgba(16, 185, 129, 0.15)', border: '1px solid #10b981' }}
            >
              <div style={{ fontWeight: 700, fontSize: '0.875rem', color: '#34d399' }}>
                🎉 일회용 부트스트랩 토큰 발급 완료 (Bootstrap Token Minted)
              </div>
              <p style={{ fontSize: '0.75rem', color: '#e2e8f0', margin: '4px 0' }}>
                이 토큰은 평문으로 단 1회만 반환되며 이후 안전하게 암호화 해시 처리됩니다.
              </p>
              <div style={{ padding: '8px 12px', backgroundColor: '#0f172a', borderRadius: '4px', fontFamily: 'monospace', fontSize: '0.8125rem', color: '#38bdf8', marginTop: '6px' }}>
                {admissionResult.bootstrapToken}
              </div>
              <div style={{ fontSize: '0.6875rem', color: '#94a3b8', marginTop: '4px' }}>
                만료 시각: {new Date(admissionResult.expiresAt).toLocaleString()} · 다음 단계: {admissionResult.next}
              </div>
            </div>
          )}

          {/* Candidates List */}
          <div>
            <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: '8px' }}>
              <h3 style={{ fontSize: '0.875rem', fontWeight: 600, margin: 0 }}>
                📋 승인 대기 중인 디스커버리 후보 (Discovery Candidates)
              </h3>
              <button
                type="button"
                data-testid="discovery-refresh-btn"
                onClick={loadDiscoveryCandidates}
                style={{ padding: '3px 8px', fontSize: '0.6875rem', backgroundColor: 'transparent', border: '1px solid #334155', color: '#94a3b8', borderRadius: '4px', cursor: 'pointer' }}
              >
                🔄 새로고침
              </button>
            </div>
            <div style={{ fontSize: '0.75rem', color: '#f59e0b', marginBottom: '8px' }}>
              * 모든 claimed* 수치는 머신 자체 보고값이며 미검증 상태(verified: false)입니다.
            </div>

            {candidatesState === 'loading' && (
              <div data-testid="discovery-loading" style={{ padding: '20px', textAlign: 'center', color: '#94a3b8', backgroundColor: '#1e293b', borderRadius: '8px', border: '1px solid #334155' }}>
                디스커버리 후보 목록을 조회하는 중입니다...
              </div>
            )}

            {candidatesState === 'error' && (
              <div role="alert" data-testid="discovery-error-banner" style={{ padding: '16px', backgroundColor: 'rgba(239, 68, 68, 0.1)', border: '1px solid #ef4444', borderRadius: '8px', color: '#fca5a5' }}>
                <div style={{ fontWeight: 600, fontSize: '0.8125rem' }}>⚠️ 디스커버리 서비스 연결 오류</div>
                <div style={{ fontSize: '0.75rem', marginTop: '2px' }}>{candidatesError}</div>
                <button
                  type="button"
                  data-testid="discovery-retry-btn"
                  onClick={loadDiscoveryCandidates}
                  style={{ marginTop: '10px', padding: '6px 12px', fontSize: '0.75rem', backgroundColor: '#334155', color: '#f8fafc', border: '1px solid #475569', borderRadius: '4px', cursor: 'pointer' }}
                >
                  재시도 (Retry)
                </button>
              </div>
            )}

            {candidatesState === 'idle' && (
              <div data-testid="discovery-idle-state" style={{ padding: '20px', textAlign: 'center', color: '#64748b', backgroundColor: '#1e293b', borderRadius: '8px' }}>
                디스커버리 후보 조회가 대기 상태입니다.
              </div>
            )}

            {candidatesState === 'success' && candidates.length === 0 && (
              <div
                data-testid="discovery-empty-state"
                role="status"
                aria-live="polite"
                style={{
                  padding: '24px',
                  backgroundColor: '#1e293b',
                  borderRadius: '8px',
                  border: '1px dashed #334155',
                  display: 'flex',
                  flexDirection: 'column',
                  gap: '10px',
                  textAlign: 'center',
                }}
              >
                <div style={{ fontWeight: 600, fontSize: '0.875rem', color: '#94a3b8' }}>
                  ℹ️ 승인 대기 중인 디스커버리 후보가 없습니다. (0 Candidates Pending)
                </div>
                <div style={{ fontSize: '0.75rem', color: '#cbd5e1', lineHeight: '1.5', maxWidth: '680px', margin: '0 auto' }}>
                  <strong>후보 목록이 비어 있는 이유 (시스템 아키텍처 규칙):</strong><br />
                  테넌트 격리 및 무단 노드 오염 방지 정책에 따라, 운영자 CLI(<code>saint operator issue-grant</code>)를 통해 일회용 자격증명을 부여받은 노드만 디스커버리 안내 방송이 승인되어 목록에 나타납니다.
                </div>
                <div style={{ fontSize: '0.75rem', color: '#93c5fd', backgroundColor: 'rgba(59, 130, 246, 0.1)', padding: '6px 12px', borderRadius: '4px', maxWidth: '680px', margin: '0 auto' }}>
                  🛠️ <strong>[운영자 조치 필요]</strong>: 일반 사용자는 노드 자격증명을 직접 발급할 수 없습니다. 클러스터 인프라 운영자에게 머신 등록을 요청하십시오 (운영자 절차: Node 운영 런북 <code>docs/vault/20_Operations/노드 운영 런북.md</code>의 <code>saint operator issue-grant</code> 발급 절차 참조). 자격증명이 주입된 노드가 부트스트랩되면 목록에 자동 표출됩니다.
                </div>
                <div style={{ fontSize: '0.6875rem', color: '#64748b' }}>
                  신규 머신 부트스트랩 및 안내 방송 수신 대기 중 · 상단 '새로고침' 버튼으로 갱신 가능
                </div>
              </div>
            )}

            {candidatesState !== 'error' && candidates.length > 0 && (
              <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fill, minmax(320px, 1fr))', gap: '12px' }}>
                {candidates.map((cand) => (
                <div key={cand.announcementId} style={{ padding: '14px', backgroundColor: '#1e293b', borderRadius: '8px', border: '1px solid #334155' }}>
                  <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'flex-start' }}>
                    <div>
                      <div style={{ fontWeight: 600, fontSize: '0.875rem' }}>{cand.claimedHostname}</div>
                      <div style={{ fontSize: '0.6875rem', color: '#64748b' }}>IP: {cand.sourceIp} · ID: {cand.announcementId}</div>
                    </div>
                    <span
                      style={{
                        fontSize: '0.6875rem',
                        fontWeight: 600,
                        padding: '2px 6px',
                        borderRadius: '4px',
                        backgroundColor:
                          cand.state === 'admitted'
                            ? 'rgba(16, 185, 129, 0.2)'
                            : cand.state === 'declined'
                            ? 'rgba(239, 68, 68, 0.2)'
                            : 'rgba(234, 179, 8, 0.2)',
                        color:
                          cand.state === 'admitted'
                            ? '#34d399'
                            : cand.state === 'declined'
                            ? '#f87171'
                            : '#fbbf24',
                      }}
                    >
                      {cand.state.toUpperCase()}
                    </span>
                  </div>

                  <div style={{ fontSize: '0.75rem', color: '#94a3b8', marginTop: '8px' }}>
                    자체 보고: {cand.claimedOsType} · {cand.claimedCpuCores}C · {formatBytes(cand.claimedRamBytes)} · {cand.claimedGpuCount} GPU
                  </div>

                  {(cand.state === 'pending' || cand.state === 'candidate') && (
                    <div style={{ display: 'flex', gap: '8px', marginTop: '12px', justifyContent: 'flex-end' }}>
                      <button
                        type="button"
                        data-testid="decline-candidate-btn"
                        onClick={() => handleDeclineCandidate(cand.announcementId)}
                        style={{ padding: '4px 8px', fontSize: '0.6875rem', backgroundColor: 'rgba(239, 68, 68, 0.15)', color: '#f87171', border: '1px solid rgba(239, 68, 68, 0.3)', borderRadius: '4px', cursor: 'pointer' }}
                      >
                        거부 (DELETE /candidates/{cand.announcementId})
                      </button>
                      <button
                        type="button"
                        data-testid="admit-candidate-btn"
                        onClick={() => handleAdmitCandidate(cand.announcementId)}
                        style={{ padding: '4px 10px', fontSize: '0.6875rem', backgroundColor: '#10b981', color: '#fff', border: 'none', borderRadius: '4px', cursor: 'pointer', fontWeight: 600 }}
                      >
                        승인 & 토큰 발급 (POST /candidates/{cand.announcementId}/admission)
                      </button>
                    </div>
                  )}
                </div>
              ))}
            </div>
          )}
          </div>
        </div>
      )}
    </div>
  );
};
