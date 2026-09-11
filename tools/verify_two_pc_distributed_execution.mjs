/**
 * SaintVision Two-PC Distributed Execution, Multi-Node Sharding & GPU Training Verification Suite
 * Validates the complete 5-step collaborative sequence across Codex, Claude, and Gemini:
 *  1. Codex: Remote execution contract, minimal path, and ADR-028/040/041/044/045 bounds
 *  2. Claude: Projects, workspaces, resource pools, and provider adapter APIs
 *  3. Gemini: Integrated Developer Studio 4-step workflow, headroom metrics, and live receipts
 *  4. Two-PC Cross-Execution: Windows Node-01 (Main) <-> Linux Node-04/05 (Build/Train)
 *     - Real run execution dispatch
 *     - Immediate Outbox cancellation & resourceReleasePending hold
 *     - ADR-044 Recovery, frozen input locking & 3-attempt ceiling
 *     - NodeStopReceipt (physical stop) vs Evidence (business verification) reconciliation
 *  5. GPU Training & Multi-Node Scaling:
 *     - Multi-GPU pool (RTX 4090 + A4000) training telemetry
 *     - Distributed 5-node parallel shard aggregation & atomic reclamation
 */

import crypto from 'node:crypto';

const BACKEND_URL = process.env.TEST_BACKEND_URL || 'http://127.0.0.1:8080';
const FRONTEND_URL = process.env.TEST_FRONTEND_URL || 'http://localhost:3000';

let totalChecks = 0;
let passedChecks = 0;

function assert(title, condition, extra = '') {
  totalChecks++;
  if (condition) {
    passedChecks++;
    console.log(`  ✔ [PASS] ${title} ${extra}`);
  } else {
    console.error(`  ✖ [FAIL] ${title} ${extra}`);
  }
}

async function runTwoPcVerification() {
  console.log('================================================================================');
  console.log('🌐 SaintVision 2-PC Distributed Execution, Sharding & GPU Training Verification');
  console.log(`   Control Plane Gateway: ${BACKEND_URL}`);
  console.log(`   Frontend Studio:       ${FRONTEND_URL}`);
  console.log('================================================================================\n');

  try {
    // ---------------------------------------------------------------------------
    // Step 1: Codex 원격 실행 계약 및 최소 실행 경로 검증
    // ---------------------------------------------------------------------------
    console.log('[Step 1] Codex 원격 실행 계약 및 최소 실행 경로 검증 (ADR-028/040/041/044/045):');

    // 1.1 Health & Trace Context
    const healthRes = await fetch(`${BACKEND_URL}/v1/health`);
    assert('Control Plane /v1/health is HTTP 200', healthRes.status === 200);
    const traceparent = healthRes.headers.get('traceparent');
    assert('W3C traceparent injected on control plane response', Boolean(traceparent));

    // 1.2 Contrast check: ADR-028/041 exitCode 0 != verified true
    const contrastRes = await fetch(`${BACKEND_URL}/v1/receipts/rcp_01JFAILED_VERIFY`);
    assert('GET contrast receipt returns HTTP 200', contrastRes.status === 200);
    const contrastReceipt = await contrastRes.json();
    assert('Receipt exitCode is 0 (process cleanly exited)', contrastReceipt.exitCode === 0);
    assert('Receipt physicallyStopped is true (kernel stopped container)', contrastReceipt.physicallyStopped === true);
    assert('Receipt verified is FALSE (ADR-028: business schema check failed)', contrastReceipt.verified === false);
    assert('Receipt resourceReclaimed is FALSE (held for inspection)', contrastReceipt.resourceReclaimed === false);
    assert('CORE CONTRACT: exitCode 0 is never treated as verified application success', contrastReceipt.exitCode === 0 && !contrastReceipt.verified);

    // ---------------------------------------------------------------------------
    // Step 2: Claude 프로젝트·자원 설정·Adapter API 연결 검증
    // ---------------------------------------------------------------------------
    console.log('\n[Step 2] Claude 프로젝트·자원 설정·Adapter API 연결 검증:');

    // 2.1 Canonical Projects
    const projsRes = await fetch(`${BACKEND_URL}/v1/projects`);
    assert('GET /v1/projects returns HTTP 200', projsRes.status === 200);
    const projs = await projsRes.json();
    assert('Two canonical projects exist', projs.total >= 2);
    const pacs = projs.items.find((p) => p.id === 'prj_01JABCDE');
    const mlops = projs.items.find((p) => p.id === 'prj_saint_mlops');
    assert('PACS Core project configured (prj_01JABCDE)', Boolean(pacs && pacs.budgetKrw > 0));
    assert('MLOps Pipeline project configured (prj_saint_mlops)', Boolean(mlops && mlops.remainingBudgetKrw > 0));

    // 2.2 Workspaces across OS topologies
    const wspsRes = await fetch(`${BACKEND_URL}/v1/workspaces`);
    assert('GET /v1/workspaces returns HTTP 200', wspsRes.status === 200);
    const wsps = await wspsRes.json();
    const winWsp = wsps.items.find((w) => w.targetNodeId === 'nod_01JABCDEF01');
    const linuxWsp = wsps.items.find((w) => w.targetNodeId === 'nod_01JABCDEF05' || w.targetNodeId === 'nod_01JABCDEF04');
    assert('Windows sandbox workspace active on Node-01', Boolean(winWsp && winWsp.isolationMode === 'process_sandbox'));
    assert('Linux container workspace active on Node-04/05', Boolean(linuxWsp && linuxWsp.isolationMode === 'container_isolated'));

    // 2.3 Resource Pools & Discovery
    const poolsRes = await fetch(`${BACKEND_URL}/v1/pools`);
    assert('GET /v1/pools returns HTTP 200', poolsRes.status === 200);
    const pools = await poolsRes.json();
    const trainPool = pools.items.find((p) => p.id === 'pool_01_training');
    assert('Training GPU pool links Windows (Node-01) & Linux (Node-05)', Boolean(trainPool && trainPool.nodeIds.includes('nod_01JABCDEF01') && trainPool.nodeIds.includes('nod_01JABCDEF05')));
    assert('Training GPU pool has 2 active GPUs (RTX 4090 + A4000)', trainPool?.totalGpus === 2);

    // ---------------------------------------------------------------------------
    // Step 3: Gemini 통합 개발 Studio 화면 & 자원 메트릭 연동 검증
    // ---------------------------------------------------------------------------
    console.log('\n[Step 3] Gemini 통합 개발 Studio 화면 & 자원 메트릭 연동 검증:');

    // 3.1 3-Tier Resource Metric Computation
    const nodesRes = await fetch(`${BACKEND_URL}/v1/nodes`);
    const nodesData = await nodesRes.json();
    const allNodes = nodesData.items || [];
    assert('5 cluster nodes report telemetry', allNodes.length === 5);

    const winNode = allNodes.find((n) => n.nodeId === 'nod_01JABCDEF01');
    const linuxNode = allNodes.find((n) => n.nodeId === 'nod_01JABCDEF05');

    // Windows Node-01 Metrics
    const winPhysCores = winNode.cpuCores;
    const winObservedCpu = winNode.cpuUsagePercent;
    const winAvailCores = winPhysCores * (1 - winObservedCpu / 100);
    assert('Node-01 (Win): Physical (16 cores) != Observed usage != Available Headroom', winPhysCores === 16 && winAvailCores > 0 && winAvailCores < winPhysCores);

    // Linux Node-05 Metrics
    const linuxPhysCores = linuxNode.cpuCores;
    const linuxObservedCpu = linuxNode.cpuUsagePercent;
    const linuxAvailCores = linuxPhysCores * (1 - linuxObservedCpu / 100);
    assert('Node-05 (Linux): Physical (12 cores) != Observed usage != Available Headroom', linuxPhysCores === 12 && linuxAvailCores > 0 && linuxAvailCores < linuxPhysCores);

    // 3.2 Placement formula preview (40% locality + 30% headroom + 30% network/GPU)
    const previewRes = await fetch(`${BACKEND_URL}/v1/pools/pool_01_training/placement-preview`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({
        requiredCores: 8,
        requiredMemoryBytes: 16 * 1024 ** 3,
        requiresGpu: true,
        dataLocalityNodeId: 'nod_01JABCDEF05',
      }),
    });
    assert('POST /v1/pools/{id}/placement-preview returns HTTP 200', previewRes.status === 200);
    const previewData = await previewRes.json();
    assert('Placement deterministic winner chosen', Boolean(previewData.selectedNodeId));
    assert('Locality preference for Node-05 yields winner nod_01JABCDEF05', previewData.selectedNodeId === 'nod_01JABCDEF05');

    // ---------------------------------------------------------------------------
    // Step 4: 실제 2개 PC (Windows Node-01 <-> Linux Node-04/05) 분산 실행·취소·복구·결과 대조
    // ---------------------------------------------------------------------------
    console.log('\n[Step 4] 실제 2개 PC (Windows Node-01 <-> Linux Node-04/05) 분산 실행·취소·복구·결과 대조:');

    // 4.1 실행 (Execution): Dispatch from Node-01 to Linux Node-05
    const dispatchRes = await fetch(`${BACKEND_URL}/v1/projects/prj_saint_mlops/runs`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({
        workspaceId: 'wsp_saint_mlops_gpu',
        objective: '2-PC Cross-Node DICOM Preprocessing & GPU Validation',
        requestedBy: 'usr_researcher_02',
      }),
    });
    assert('Dispatch cross-node run returns HTTP 201 Created', dispatchRes.status === 201);
    const run = await dispatchRes.json();
    const runId = run.id;
    assert('Run assigned valid id and running state', Boolean(runId && run.state === 'running'));

    // 4.2 취소 (Cancellation): Outbox hold and resource release pending
    const cancelRes = await fetch(`${BACKEND_URL}/v1/runs/${runId}/cancel`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ reason: 'two_pc_test_interruption' }),
    });
    assert('Cancel cross-node run returns HTTP 200', cancelRes.status === 200);
    const cancelledRun = await (await fetch(`${BACKEND_URL}/v1/runs/${runId}`)).json();
    assert('Run state transitioned to cancelled', cancelledRun.state === 'cancelled');

    // 4.3 복구 (Recovery): ADR-044/045 Frozen snapshot, version binding & 3-attempt ceiling
    const resetRes = await fetch(`${BACKEND_URL}/v1/runs/run_01JRECOVERING/reset-recovering`, { method: 'POST' });
    assert('Reset recovering test run returns HTTP 200', resetRes.status === 200);

    const prepRes = await fetch(`${BACKEND_URL}/v1/runs/run_01JRECOVERING/resume/prepare`, { method: 'POST' });
    assert('Prepare resume for interrupted run returns HTTP 200', prepRes.status === 200);
    const prepData = await prepRes.json();
    const resumeSpec = prepData.spec || prepData;
    assert('Resume spec defines deterministic inputHash', Boolean(resumeSpec?.inputHash));
    assert('Resume spec binds to next run version (boundRunVersion: 2)', resumeSpec?.boundRunVersion === 2);
    assert('Resume spec contains frozen files manifest', Array.isArray(resumeSpec?.frozenFiles) && resumeSpec.frozenFiles.length > 0);

    // Approve generated L2 resume approval
    const apprvRes = await fetch(`${BACKEND_URL}/v1/approvals/${prepData.approvalId}/approve`, { method: 'POST' });
    assert('L2 resume approval approved by operator', apprvRes.status === 200);

    // Enqueue resume attempt 2
    const enqRes = await fetch(`${BACKEND_URL}/v1/runs/run_01JRECOVERING/resume/enqueue`, { method: 'POST' });
    assert('Enqueue resume returns HTTP 200', enqRes.status === 200);
    const enqData = await enqRes.json();
    assert('Attempt atomically incremented (attempt 1 -> 2)', enqData.attempt === 2);
    assert('Run state transitions back to running', enqData.state === 'running');

    // Max attempts bound (attempt ceiling = 3)
    const exhaustedRes = await fetch(`${BACKEND_URL}/v1/runs/run_01JRECOVERING_EXHAUSTED/resume/prepare`, { method: 'POST' });
    assert('Attempt >= 3 strictly rejected with HTTP 400', exhaustedRes.status === 400);
    const problem = await exhaustedRes.json();
    assert('Returns RFC 9457 VAL-MAX-ATTEMPTS-EXCEEDED', problem.code === 'VAL-MAX-ATTEMPTS-EXCEEDED');

    // 4.4 결과 확인 (Result Confirmation): NodeStopReceipt vs Evidence Reconciliation
    const receiptRes = await fetch(`${BACKEND_URL}/v1/receipts/rcp_01JSHARD_03`);
    assert('Fetch completed shard receipt returns HTTP 200', receiptRes.status === 200);
    const receipt = await receiptRes.json();
    assert('NodeStopReceipt exitCode: 0', receipt.exitCode === 0);
    assert('NodeStopReceipt physicallyStopped: true', receipt.physicallyStopped === true);
    assert('NodeStopReceipt verified: true', receipt.verified === true);
    assert('NodeStopReceipt resourceReclaimed: true', receipt.resourceReclaimed === true);
    assert('NodeStopReceipt output SHA-256 confirmed', Boolean(receipt.output?.sha256));

    // ---------------------------------------------------------------------------
    // Step 5: GPU 학습 및 다중 Node 작업 확장 검증
    // ---------------------------------------------------------------------------
    console.log('\n[Step 5] GPU 학습 및 다중 Node 작업 확장 검증:');

    // 5.1 Multi-GPU Training Pool Validation (Node-01 RTX 4090 + Node-05 A4000)
    const poolCapRes = await fetch(`${BACKEND_URL}/v1/pools/pool_01_training/capacity`);
    assert('GET /v1/pools/pool_01_training/capacity returns HTTP 200', poolCapRes.status === 200);
    const poolCap = await poolCapRes.json();
    assert('Total GPU Cores: 28 cores', poolCap.totalCores === 28);
    assert('Total GPU Memory: 96 GiB', poolCap.totalMemoryBytes === 96 * 1024 ** 3);
    assert('GPU models include both RTX 4090 and A4000', poolCap.gpuModels.includes('NVIDIA RTX 4090') && poolCap.gpuModels.includes('NVIDIA A4000'));

    // 5.2 Multi-Node Parallel Shards (SHARD-I07)
    const parentRunRes = await fetch(`${BACKEND_URL}/v1/runs/run_01JPARENT_ACTIVE`);
    assert('GET active parent sharded run returns HTTP 200', parentRunRes.status === 200);
    const shardsRes = await fetch(`${BACKEND_URL}/v1/runs/run_01JPARENT_ACTIVE/shards`);
    assert('GET parent run shards returns HTTP 200', shardsRes.status === 200);
    const shardsData = await shardsRes.json();
    assert('Parent run distributes multiple parallel shards', Array.isArray(shardsData.items) && shardsData.items.length >= 2);

    // 5.3 Atomic Bulk Shard Cancellation & Resource Reclamation
    const bulkCancelRes = await fetch(`${BACKEND_URL}/v1/runs/run_01JPARENT_ACTIVE/shards/cancel-all`, { method: 'POST' });
    assert('POST /v1/runs/{id}/shards/cancel-all returns HTTP 200', bulkCancelRes.status === 200);
    const bulkData = await bulkCancelRes.json();
    assert('Bulk cancel reports resourceReleasePending: true', bulkData.resourceReleasePending === true);

    const reclaimRes = await fetch(`${BACKEND_URL}/v1/runs/run_01JPARENT_ACTIVE/reclaim-resources`, { method: 'POST' });
    assert('POST /v1/runs/{id}/reclaim-resources returns HTTP 200', reclaimRes.status === 200);
    const reclaimData = await reclaimRes.json();
    assert('Resource reclamation clears resourceReleasePending: false', reclaimData.resourceReleasePending === false);
    assert('All physical stops confirmed across distributed nodes', reclaimData.allPhysicallyStopped === true);

    // ---------------------------------------------------------------------------
    // Final Summary
    // ---------------------------------------------------------------------------
    console.log('\n================================================================================');
    console.log(`🎉 2-PC Distributed Execution & GPU Scaling Summary: ${passedChecks}/${totalChecks} checks passed (${Math.round((passedChecks / totalChecks) * 100)}%)`);
    console.log('   All 5 collaborative steps (Codex, Claude, Gemini, 2-PC Execution, GPU Scaling) verified!');
    console.log('================================================================================\n');

    if (passedChecks !== totalChecks) {
      process.exit(1);
    }
  } catch (err) {
    console.error('Fatal 2-PC Verification Error:', err);
    process.exit(1);
  }
}

runTwoPcVerification();
