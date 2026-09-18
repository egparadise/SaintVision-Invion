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

const SHA256_HEX_REGEX = /^sha256:[a-f0-9]{64}$/;

function isValidSha256Digest(val) {
  return typeof val === 'string' && SHA256_HEX_REGEX.test(val);
}

let totalChecks = 0;
let passedChecks = 0;
let unverifiedChecks = 0;

function base64Url(buf) {
  return buf.toString('base64').replace(/\+/g, '-').replace(/\//g, '_').replace(/=+$/, '');
}

async function sha256Base64Url(plain) {
  const hash = crypto.createHash('sha256').update(plain).digest();
  return base64Url(hash);
}

let bearerToken = null;
function authHeaders(extra = {}) {
  return bearerToken ? { Authorization: `Bearer ${bearerToken}`, ...extra } : { ...extra };
}

function assert(title, condition, extra = '') {
  totalChecks++;
  if (condition) {
    passedChecks++;
    console.log(`  ✔ [PASS] ${title} ${extra}`);
  } else {
    console.error(`  ✖ [FAIL] ${title} ${extra}`);
  }
}

function unverified(title, reason) {
  unverifiedChecks++;
  console.log(`  ◌ [UNVERIFIED] ${title} (${reason})`);
}

async function runTwoPcVerification() {
  console.log('================================================================================');
  console.log('🌐 SaintVision 2-PC Distributed Execution, Sharding & GPU Training Verification');
  console.log('   [API Contract Smoke Suite - Control Plane Gateway & In-Memory Contracts]');
  console.log('   (Note: Validates HTTP API contracts; not a substitute for physical 5-node acceptance)');
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

    // 1.3 OIDC PKCE S256 Cryptographic Authentication (ADR-004 / RFC 7636)
    const codeVerifier = base64Url(crypto.randomBytes(32));
    const codeChallenge = await sha256Base64Url(codeVerifier);
    const tokenRes = await fetch(`${BACKEND_URL}/v1/auth/token`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({
        grant_type: 'authorization_code',
        code: `auth_code_${crypto.randomBytes(8).toString('hex')}`,
        code_verifier: codeVerifier,
        code_challenge: codeChallenge,
        code_challenge_method: 'S256',
        client_id: 'saintvision-2pc-runner',
        idp: 'internal-keycloak',
      }),
    });
    assert('2-PC Suite OIDC PKCE token exchange returns HTTP 200', tokenRes.status === 200);
    const tokenData = await tokenRes.json();
    bearerToken = tokenData.access_token;
    assert('2-PC Suite Bearer access token granted', Boolean(bearerToken));

    const userinfoRes = await fetch(`${BACKEND_URL}/v1/auth/userinfo`, {
      headers: authHeaders(),
    });
    assert('2-PC Suite operator identity verified at /v1/auth/userinfo', userinfoRes.status === 200);
    const userinfo = await userinfoRes.json();
    assert('2-PC Suite operator role confirmed as cluster:admin', userinfo.roles?.includes('cluster:admin'));

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

    // 4.1-A 거버넌스 검증: 관측 전용 노드 (192.168.45.225) 업무 제출 차단 (Codex P1 / Zero Mock)
    const rejectRes = await fetch(`${BACKEND_URL}/v1/projects/prj_saint_mlops/runs`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({
        workspaceId: 'wsp_saint_mlops_gpu',
        targetNodeId: 'nod_01JABCDEF04', // 192.168.45.225 observation-only node
        objective: 'Disallowed run on observation-only worker',
        requestedBy: 'usr_researcher_02',
      }),
    });
    assert('Dispatch to observation-only node is rejected with HTTP 400', rejectRes.status === 400);
    const rejectProblem = await rejectRes.json();
    assert('Rejection code is VAL-NODE-OBSERVATION-ONLY (no mock run created)', rejectProblem.code === 'VAL-NODE-OBSERVATION-ONLY');

    // 4.1-B 실행 (Execution): Dispatch with complete contract payload to Linux Node-05
    const dispatchRes = await fetch(`${BACKEND_URL}/v1/projects/prj_saint_mlops/runs`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({
        workspaceId: 'wsp_saint_mlops_gpu',
        targetNodeId: 'nod_01JABCDEF05',
        entrypoint: 'src/server.ts',
        files: [{ path: 'src/server.ts', content: 'console.log("SaintVision 2PC Execution");\n', size: 1024 }],
        resourceRequests: { requiredCores: 8, requiredMemoryBytes: 16 * 1024 ** 3, requiresGpu: true },
        objective: '2-PC Cross-Node DICOM Preprocessing & GPU Validation',
        requestedBy: 'usr_researcher_02',
      }),
    });
    assert('Dispatch cross-node run returns HTTP 201 Created', dispatchRes.status === 201);
    const run = await dispatchRes.json();
    const runId = run.id;
    assert('Run assigned valid id and running state', Boolean(runId && run.state === 'running'));
    assert('Run binds targetNodeId nod_01JABCDEF05', run.nodeId === 'nod_01JABCDEF05');
    assert('Run binds entrypoint and leaseId', Boolean(run.entrypoint && run.leaseId));

    // 4.1-C 결과 아티팩트 다운로드 엔드포인트 및 원본 바이트 해시 검증
    const artRes = await fetch(`${BACKEND_URL}/v1/runs/${runId}/artifacts/download`);
    assert('GET /v1/runs/{id}/artifacts/download returns HTTP 200', artRes.status === 200);
    const artData = await artRes.json();
    assert('Downloaded artifact contains valid 64-hex SHA-256 outputHash', isValidSha256Digest(artData.outputHash));

    // 원본 아티팩트 바이트 다운로드 및 SHA-256 해시 재계산 대조
    const rawArtRes = await fetch(`${BACKEND_URL}/v1/runs/${runId}/artifacts/content?path=src/server.ts`);
    assert('GET /v1/runs/{id}/artifacts/content returns HTTP 200', rawArtRes.status === 200);
    const rawBuffer = Buffer.from(await rawArtRes.arrayBuffer());
    const rawComputedHash = `sha256:${crypto.createHash('sha256').update(rawBuffer).digest('hex')}`;
    const headerChecksum = rawArtRes.headers.get('x-checksum-sha256');
    assert('Raw artifact bytes yield valid 64-hex SHA-256', isValidSha256Digest(rawComputedHash));
    assert('Raw artifact computed hash matches X-Checksum-SHA256 header', rawComputedHash === headerChecksum);

    // 4.2 취소 (Cancellation): Outbox hold and resource release pending
    const cancelRunRes = await fetch(`${BACKEND_URL}/v1/projects/prj_saint_mlops/runs`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({
        workspaceId: 'wsp_saint_mlops_gpu',
        targetNodeId: 'nod_01JABCDEF05',
        entrypoint: 'src/worker.ts',
        files: [{ path: 'src/worker.ts', size: 512 }],
        objective: 'Dedicated cancellation test execution',
        requestedBy: 'usr_researcher_02',
      }),
    });
    assert('Dispatch cancellation candidate run returns HTTP 201', cancelRunRes.status === 201);
    const cancelRun = await cancelRunRes.json();
    const cancelRunId = cancelRun.id;

    const cancelRes = await fetch(`${BACKEND_URL}/v1/runs/${cancelRunId}/cancel`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ reason: 'two_pc_test_interruption' }),
    });
    assert('Cancel cross-node run returns HTTP 200', cancelRes.status === 200);
    const cancelledRun = await (await fetch(`${BACKEND_URL}/v1/runs/${cancelRunId}`)).json();
    assert('Run state transitioned to cancelled', cancelledRun.state === 'cancelled');

    // 4.3 복구 (Recovery): ADR-044/045 Frozen snapshot, version binding & 3-attempt ceiling
    const resetRes = await fetch(`${BACKEND_URL}/v1/runs/run_01JRECOVERING/reset-recovering`, { method: 'POST' });
    assert('Reset recovering test run returns HTTP 200', resetRes.status === 200);

    const prepRes = await fetch(`${BACKEND_URL}/v1/runs/run_01JRECOVERING/resume/prepare`, { method: 'POST' });
    assert('Prepare resume for interrupted run returns HTTP 200', prepRes.status === 200);
    const prepData = await prepRes.json();
    const resumeSpec = prepData.spec || prepData;
    assert('Resume spec defines valid 64-hex SHA-256 inputHash', isValidSha256Digest(resumeSpec?.inputHash));
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
    // Query receipt for the dispatched run (runId) and verify identity & hash binding
    let receipt = null;
    const deadline = Date.now() + 4000;
    while (Date.now() < deadline) {
      const runReceiptsRes = await fetch(`${BACKEND_URL}/v1/runs/${runId}/receipts`);
      if (runReceiptsRes.status === 200) {
        const receiptsPayload = await runReceiptsRes.json();
        const found = (receiptsPayload.items || []).find((r) => r.runId === runId);
        if (found) {
          receipt = found;
          break;
        }
      }
      const directReceiptRes = await fetch(`${BACKEND_URL}/v1/receipts/rcp_${runId}`);
      if (directReceiptRes.status === 200) {
        receipt = await directReceiptRes.json();
        break;
      }
      await new Promise((res) => setTimeout(res, 200));
    }

    assert('Fetch NodeStopReceipt for dispatched run returns valid object', Boolean(receipt));
    if (receipt) {
      assert('NodeStopReceipt binds to dispatched runId', receipt.runId === runId);
      assert('NodeStopReceipt binds to targetNodeId nod_01JABCDEF05', receipt.nodeId === run.nodeId);
      assert('NodeStopReceipt binds to run attempt', (receipt.attempt ?? 1) === (run.attempt ?? 1));
      assert('NodeStopReceipt binds to run epoch', !receipt.epoch || receipt.epoch === (run.epoch ?? 1));
      assert('NodeStopReceipt exitCode: 0', receipt.exitCode === 0);
      assert('NodeStopReceipt physicallyStopped: true', receipt.physicallyStopped === true);
      assert('NodeStopReceipt verified: true', receipt.verified === true);
      assert('NodeStopReceipt resourceReclaimed: true', receipt.resourceReclaimed === true);
      assert('NodeStopReceipt output SHA-256 matches 64-hex format', isValidSha256Digest(receipt.output?.sha256));
      assert('NodeStopReceipt output SHA-256 matches run outputHash', receipt.output?.sha256 === artData.outputHash);
    }

    // Negative controls must reach a real API rejection path. Local comparisons
    // of constants or this file's own digest helper are not rejection evidence.
    const unknownRunId = `${runId}-negative-unknown`;
    try {
      const unknownReceiptRes = await fetch(`${BACKEND_URL}/v1/runs/${unknownRunId}/receipts`, { headers: authHeaders() });
      assert(
        'Negative control: unknown run receipt query reaches API and is rejected',
        unknownReceiptRes.status === 404,
        `(HTTP ${unknownReceiptRes.status})`
      );
    } catch (err) {
      unverified('Negative control: unknown run receipt query', `backend not reachable (${err.message})`);
    }
    unverified('Negative control: mismatched receipt nodeId', 'no receipt-submission endpoint is exercised by this suite');
    unverified('Negative control: malformed receipt digest', 'no receipt-submission endpoint is exercised by this suite');

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
    if (passedChecks === totalChecks && totalChecks > 0) {
      console.log(`🎉 2-PC Distributed Execution & GPU Scaling Summary: ${passedChecks}/${totalChecks} checks passed (100%)`);
      console.log(`   Unverified negative controls: ${unverifiedChecks} (excluded from PASS count)`);
      console.log('   All 5 collaborative steps (Codex, Claude, Gemini, 2-PC Execution, GPU Scaling) verified!');
      console.log('   (Control Plane Gateway API Contract Smoke Suite; not physical 5-node hardware acceptance)');
      console.log('================================================================================\n');
    } else {
      console.error(`❌ 2-PC Distributed Execution & GPU Scaling FAILED: ${totalChecks - passedChecks} failed out of ${totalChecks} checks (${passedChecks}/${totalChecks} passed).`);
      console.error('   Verification incomplete or boundary audit assertions failed.');
      console.log('================================================================================\n');
      process.exit(1);
    }
  } catch (err) {
    console.error('Fatal 2-PC Verification Error:', err);
    process.exit(1);
  }
}

runTwoPcVerification();
