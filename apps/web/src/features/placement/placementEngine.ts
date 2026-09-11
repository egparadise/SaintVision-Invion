import { NodeItem, PlacementRequirement, PlacementExplainResult, CandidateEvaluation } from '@/contracts/types';

export function evaluatePlacement(
  nodes: NodeItem[],
  req: PlacementRequirement,
  fencedNodeIds: Set<string> = new Set()
): PlacementExplainResult {
  const evaluations: CandidateEvaluation[] = nodes.map((node) => {
    const reasons: string[] = [];

    // Check 1: Node status
    if (node.status !== 'online') {
      reasons.push(`노드 상태 비정상 (${node.status})`);
    }

    // Check 2: Fenced or Kill Switch status
    if (fencedNodeIds.has(node.id)) {
      reasons.push('노드가 격리/Fenced 상태로 안전 잠금됨');
    }
    if (node.killSwitchEngaged) {
      reasons.push('비상 Kill Switch 발동으로 신규 워크로드 실행 차단됨');
    }

    // Check 3: Schedulability and Observation-Only
    if (node.observationOnly) {
      reasons.push('원격 실행 프로필 미설치 (관측 전용 노드 - 업무 제출 비활성)');
    }
    if (node.schedulable === false) {
      reasons.push('스케줄러에 의해 배치 비활성화됨 (schedulable=false)');
    }
    if (node.isDraining) {
      reasons.push('노드 Drain 정리 진행 중으로 신규 실행 불가');
    }

    // Check 4: OS preference
    if (req.preferredOs && node.os !== req.preferredOs) {
      reasons.push(`운영체제 불일치 (요청: ${req.preferredOs}, 노드: ${node.os})`);
    }

    // Check 5: CPU Cores Headroom vs Allocatable
    const observedAvailCores = node.cpuCores * (1 - node.cpuUsagePercent / 100);
    const maxSchedCores = node.allocatableCores !== undefined ? Math.min(observedAvailCores, node.allocatableCores) : observedAvailCores;
    if (maxSchedCores < req.requiredCores) {
      reasons.push(
        `가용 CPU 코어 부족 (필요: ${req.requiredCores} 코어, 예약가능: ${maxSchedCores.toFixed(1)} 코어, 관측여유: ${observedAvailCores.toFixed(1)} 코어)`
      );
    }

    // Check 6: Memory Headroom vs Allocatable
    const observedAvailMemory = node.memoryTotalBytes - node.memoryUsedBytes;
    const maxSchedMemory = node.allocatableMemoryBytes !== undefined ? Math.min(observedAvailMemory, node.allocatableMemoryBytes) : observedAvailMemory;
    if (maxSchedMemory < req.requiredMemoryBytes) {
      const availGb = (maxSchedMemory / 1024 ** 3).toFixed(1);
      const reqGb = (req.requiredMemoryBytes / 1024 ** 3).toFixed(1);
      reasons.push(`가용 메모리 부족 (필요: ${reqGb} GB, 예약가능: ${availGb} GB)`);
    }

    // Check 7: GPU requirement
    if (req.requiresGpu && node.gpuCount === 0) {
      reasons.push('가속 GPU 부재 (GPU 워크로드 요구)');
    }

    const hardFilterPassed = reasons.length === 0;

    let scores: CandidateEvaluation['scores'] | undefined = undefined;
    if (hardFilterPassed) {
      // 1. Locality Score (weight: 0.4)
      const localityScore = req.dataLocalityNodeId === node.id ? 100 : 30;

      // 2. Headroom Score (weight: 0.3)
      const cpuHeadroomPct = 100 - node.cpuUsagePercent;
      const memHeadroomPct = ((node.memoryTotalBytes - node.memoryUsedBytes) / node.memoryTotalBytes) * 100;
      const headroomScore = Math.round((cpuHeadroomPct + memHeadroomPct) / 2);

      // 3. Network Cost Score (weight: 0.3)
      const networkCostScore = req.dataLocalityNodeId === node.id ? 100 : 70;

      // Weighted Composite Total Score
      const totalScore = Math.round(localityScore * 0.4 + headroomScore * 0.3 + networkCostScore * 0.3);

      scores = {
        localityScore,
        headroomScore,
        networkCostScore,
        totalScore,
      };
    }

    return {
      nodeId: node.id,
      hostname: node.hostname,
      os: node.os,
      hardFilterPassed,
      rejectionReasons: reasons,
      scores,
    };
  });

  // Filter candidates passing hard filter
  const eligible = evaluations.filter((e) => e.hardFilterPassed && e.scores);

  // Deterministic Winner Selection: highest totalScore, tie-break by lexicographical nodeId
  eligible.sort((a, b) => {
    if (b.scores!.totalScore !== a.scores!.totalScore) {
      return b.scores!.totalScore - a.scores!.totalScore;
    }
    return a.nodeId.localeCompare(b.nodeId);
  });

  const selectedNodeId = eligible.length > 0 ? eligible[0].nodeId : null;

  return {
    runId: `sim_${Date.now().toString(36)}`,
    selectedNodeId,
    policyVersion: 'POLICY-PLACEMENT-v1.0.0',
    snapshotVersion: 'SNAP-5NODE-LIVE',
    evaluations,
    decidedAt: new Date().toISOString(),
  };
}
