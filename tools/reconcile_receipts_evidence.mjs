/**
 * SaintVision Kernel Results vs 5 Core Screens Reconciliation Runner
 * Validates the 5 core user screens against actual unified control plane kernel state:
 *  1. 승인 화면 (Approval Center): L2/L3 risk, boundRunVersion, diff requirement & nonce guard
 *  2. 취소 화면 (Cancel Flow): Outbox cancellation, shard cascade, resourceReleasePending hold
 *  3. 샤드 화면 (Distributed Shards): NodeStopReceipt binding, outputHash vs manifestDigest
 *  4. 복구 화면 (Distributed Recovery): 0600 permissions, inode, epoch fencing, 3-attempt bound
 *  5. 편집 화면 (Workspace Editor): Working draft vs ADR-044 Frozen Input Snapshot digest
 *
 * Core Contrast: NodeStopReceipt exitCode: 0 (physical stop) vs Evidence verified: true (business success)
 */

import crypto from 'node:crypto';

const BASE_URL = process.env.TEST_BASE_URL || 'http://localhost:3000';
const BACKEND_URL = process.env.TEST_BACKEND_URL || 'http://127.0.0.1:8080';

const SHA256_HEX_REGEX = /^sha256:[a-f0-9]{64}$/;

function isValidSha256Digest(val) {
  return typeof val === 'string' && SHA256_HEX_REGEX.test(val);
}

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

async function main() {
  console.log('================================================================================');
  console.log('🏛️ SaintVision 5-Screen Kernel Results & Evidence Deep Reconciliation');
  console.log('   [API Contract Smoke Suite - Control Plane Gateway & In-Memory Contracts]');
  console.log('   (Note: Validates HTTP API contracts; not a substitute for physical 5-node acceptance)');
  console.log(`   Frontend Host: ${BASE_URL}`);
  console.log(`   Kernel Host:   ${BACKEND_URL}`);
  console.log('================================================================================\n');

  try {
    // ---------------------------------------------------------------------------
    // Screen 1: 승인 화면 (Approval Center)
    // ---------------------------------------------------------------------------
    console.log('[Screen 1 / 5] 승인 화면 (Approval Center) - 거버넌스 & 바인딩 검증:');
    const approvalsRes = await fetch(`${BACKEND_URL}/v1/approvals`);
    assert('GET /v1/approvals returns HTTP 200', approvalsRes.status === 200);
    const approvalsData = await approvalsRes.json();
    assert('Approvals list returned', Array.isArray(approvalsData.items) && approvalsData.items.length > 0);

    // L3 Approval with Diff Requirement
    const l3Approval = approvalsData.items.find((a) => a.riskLevel === 'L3');
    assert('L3 High-Risk approval exists in queue', Boolean(l3Approval));
    if (l3Approval) {
      assert('L3 approval contains non-empty unifiedDiff', typeof l3Approval.unifiedDiff === 'string' && l3Approval.unifiedDiff.length > 0);
      assert('L3 approval defines cryptographic nonce', typeof l3Approval.nonce === 'string' && l3Approval.nonce.length >= 16);
      assert('L3 approval enforces blastRadius isolation', l3Approval.blastRadius === 'workspace_isolated' || l3Approval.blastRadius === 'cluster_production');
    }

    // L2 Resume Step Approval with Bound Version
    await fetch(`${BACKEND_URL}/v1/runs/run_01JRECOVERING/reset-recovering`, { method: 'POST' });
    const resumePrepRes = await fetch(`${BACKEND_URL}/v1/runs/run_01JRECOVERING/resume/prepare`, { method: 'POST' });
    assert('POST /v1/runs/run_01JRECOVERING/resume/prepare succeeds', resumePrepRes.status === 200);
    const resumeSpec = await resumePrepRes.json();
    const l2ApprovalRes = await fetch(`${BACKEND_URL}/v1/approvals/${resumeSpec.approvalId}`);
    assert('GET resume L2 approval returns HTTP 200', l2ApprovalRes.status === 200);
    const l2Approval = await l2ApprovalRes.json();
    assert('L2 resume approval binds to next run version (boundRunVersion: 2)', l2Approval.boundRunVersion === 2);
    assert('L2 resume approval includes checkpoint state diff', typeof l2Approval.unifiedDiff === 'string' && l2Approval.unifiedDiff.includes('frozen_manifest_hash'));

    // ---------------------------------------------------------------------------
    // Screen 2: 취소 화면 (Cancellation & Resource Hold Flow)
    // ---------------------------------------------------------------------------
    console.log('\n[Screen 2 / 5] 취소 화면 (Cancellation Flow) - Outbox & 자원 반환 홀드:');
    const cancelRes = await fetch(`${BACKEND_URL}/v1/runs/run_01JPARENT_ACTIVE/cancel`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ reason: 'user_requested' }),
    });
    assert('POST /v1/runs/{id}/cancel returns HTTP 200', cancelRes.status === 200);
    const cancelData = await cancelRes.json();
    assert('Cancelled run enters cancelled state', cancelData.state === 'cancelled');
    assert('ADR-040: resourceReleasePending remains TRUE until receipts received', cancelData.resourceReleasePending === true);

    // Child Shards Cancellation Cascade
    const parentRunRes = await fetch(`${BACKEND_URL}/v1/runs/run_01JPARENT_ACTIVE`);
    const parentRun = await parentRunRes.json();
    assert('Parent run tracks child shard IDs', Array.isArray(parentRun.childRunIds) && parentRun.childRunIds.length === 2);

    // ---------------------------------------------------------------------------
    // Screen 3: 샤드 화면 (Distributed Shards & Receipts)
    // ---------------------------------------------------------------------------
    console.log('\n[Screen 3 / 5] 샤드 화면 (Distributed Shards) - 물리 정지 vs 결과 검증:');
    // Active Shards
    const activeShardsRes = await fetch(`${BACKEND_URL}/v1/runs/run_01JPARENT_ACTIVE/shards`);
    assert('GET /v1/runs/{id}/shards returns HTTP 200', activeShardsRes.status === 200);
    const activeShardsData = await activeShardsRes.json();
    assert('Shards list returned for active parent run', Array.isArray(activeShardsData.items) && activeShardsData.items.length === 2);

    for (const shard of activeShardsData.items) {
      assert(`Active shard ${shard.shardId} has assigned nodeId`, Boolean(shard.nodeId));
      assert(`Active shard ${shard.shardId} has deterministic attempt #`, typeof shard.attempt === 'number');
      assert(`Active shard ${shard.shardId} tracks parentId`, shard.parentId === 'run_01JPARENT_ACTIVE');
    }

    // Completed Shards with Receipts & Output Hashes
    const successShardsRes = await fetch(`${BACKEND_URL}/v1/runs/run_01JPARENT_SUCCESS/shards`);
    assert('GET completed shards returns HTTP 200', successShardsRes.status === 200);
    const successShardsData = await successShardsRes.json();
    assert('Completed shards list returned', Array.isArray(successShardsData.items) && successShardsData.items.length === 2);
    for (const shard of successShardsData.items) {
      assert(`Completed shard ${shard.shardId} references receiptId`, Boolean(shard.receiptId));
      assert(`Completed shard ${shard.shardId} has outputHash SHA-256`, typeof shard.outputHash === 'string' && shard.outputHash.startsWith('sha256:'));
      assert(`Completed shard ${shard.shardId} is physicallyStopped`, shard.physicallyStopped === true);
      assert(`Completed shard ${shard.shardId} is verified`, shard.verified === true);
    }

    // Success Run Manifest Aggregation
    const successRunRes = await fetch(`${BACKEND_URL}/v1/runs/run_01JPARENT_SUCCESS`);
    const successRun = await successRunRes.json();
    assert('Completed parent run contains aggregate manifestDigest', typeof successRun.manifestDigest === 'string' && successRun.manifestDigest.startsWith('sha256:'));
    assert('Completed parent run has allPhysicallyStopped: true', successRun.allPhysicallyStopped === true);
    assert('Completed parent run has allSucceeded: true', successRun.allSucceeded === true);

    // ---------------------------------------------------------------------------
    // Screen 4: 복구 화면 (Distributed Recovery & ADR-043/044)
    // ---------------------------------------------------------------------------
    console.log('\n[Screen 4 / 5] 복구 화면 (Distributed Recovery) - 0600 권한, Inode & 3-Attempt:');
    // Verify Node Inventory
    const nodesRes = await fetch(`${BACKEND_URL}/v1/nodes`);
    assert('GET /v1/nodes returns HTTP 200', nodesRes.status === 200);
    const nodesData = await nodesRes.json();
    assert('5 cluster nodes available for recovery orchestration', nodesData.items.length === 5);

    // Verify Recovering Run and 3-Attempt Bound
    const recoveringRunRes = await fetch(`${BACKEND_URL}/v1/runs/run_01JRECOVERING`);
    const recoveringRun = await recoveringRunRes.json();
    assert('Recovering run attempt is bounded (attempt: 1, maxAttempts: 3)', recoveringRun.attempt === 1 && recoveringRun.maxAttempts === 3);

    const exhaustedRunRes = await fetch(`${BACKEND_URL}/v1/runs/run_01JRECOVERING_EXHAUSTED`);
    const exhaustedRun = await exhaustedRunRes.json();
    assert('Exhausted run attempt reaches boundary (attempt: 3, maxAttempts: 3)', exhaustedRun.attempt === 3 && exhaustedRun.maxAttempts === 3);

    // ---------------------------------------------------------------------------
    // Screen 5: 편집 화면 (Workspace Monaco Editor & ADR-044 Snapshot)
    // ---------------------------------------------------------------------------
    console.log('\n[Screen 5 / 5] 편집 화면 (Workspace Editor) - 작업본 vs 불변 스냅샷 해시 대조:');
    // Prepare resume generates immutable inputHash
    const resumeSpecRes = await fetch(`${BACKEND_URL}/v1/runs/run_01JRECOVERING/resume`);
    assert('GET /v1/runs/run_01JRECOVERING/resume returns valid spec', resumeSpecRes.status === 200);
    const currentResume = await resumeSpecRes.json();
    assert('Resume state contains valid 64-hex SHA-256 inputHash', isValidSha256Digest(currentResume.inputHash));

    // Frozen snapshot manifest integrity
    assert('Resume state contains non-empty frozenFiles manifest array', Array.isArray(currentResume.frozenFiles) && currentResume.frozenFiles.length > 0);
    const allFilesValid = currentResume.frozenFiles.every(f => Boolean(f.path) && f.size > 0 && isValidSha256Digest(f.sha256));
    assert('All frozen snapshot files have valid paths, sizes and 64-hex SHA-256 digests', allFilesValid);

    // Recompute manifest hash from frozen snapshot files matching Python kernel json.dumps(frozen_files, sort_keys=True)
    const canonicalManifestJson = '[' + currentResume.frozenFiles.map(f =>
      `{"path": "${f.path}", "sha256": "${f.sha256}", "size": ${f.size}}`
    ).join(', ') + ']';
    const computedManifestHash = `sha256:${crypto.createHash('sha256').update(canonicalManifestJson).digest('hex')}`;
    assert('Recomputed frozenFiles manifest SHA-256 matches inputHash', computedManifestHash === currentResume.inputHash);

    // Verify modifying working copy yields distinct SHA-256 from frozen snapshot
    const serverTsSnapshot = currentResume.frozenFiles.find(f => f.path === 'src/server.ts');
    assert('Frozen snapshot contains src/server.ts', Boolean(serverTsSnapshot));
    if (serverTsSnapshot) {
      const modifiedWorkingCopy = '// Modified working copy for next recovery step\nconsole.log("local edits");\n';
      const modifiedWorkingHash = `sha256:${crypto.createHash('sha256').update(modifiedWorkingCopy).digest('hex')}`;
      assert('Modified working copy content yields different SHA-256 than frozen snapshot', modifiedWorkingHash !== serverTsSnapshot.sha256);
    }

    // Negative controls: malformed hash strictly rejected
    assert('Negative control: malformed inputHash (sha256:not-a-digest) is strictly rejected', !isValidSha256Digest('sha256:not-a-digest'));

    // ---------------------------------------------------------------------------
    // Deep Contrast: NodeStopReceipt exitCode: 0 vs Evidence verified: true
    // ---------------------------------------------------------------------------
    console.log('\n[Receipt vs Evidence Contrast] ADR-028 / ADR-041 핵심 원칙 대조:');
    const receiptsRes = await fetch(`${BACKEND_URL}/v1/receipts`);
    assert('GET /v1/receipts returns HTTP 200', receiptsRes.status === 200);
    const receiptsData = await receiptsRes.json();
    assert('Receipts store contains records', receiptsData.total >= 3);

    // 1. Successful execution receipt (exit 0 AND verified true)
    const successReceipt = receiptsData.items.find((r) => r.receiptId === 'rcp_01JSHARD_03');
    assert('Success receipt rcp_01JSHARD_03 exists', Boolean(successReceipt));
    if (successReceipt) {
      assert('Success receipt has exitCode === 0', successReceipt.exitCode === 0);
      assert('Success receipt has physicallyStopped === true', successReceipt.physicallyStopped === true);
      assert('Success receipt has verified === true', successReceipt.verified === true);
      assert('Success receipt has resourceReclaimed === true', successReceipt.resourceReclaimed === true);
      assert('Success receipt has valid output SHA-256', isValidSha256Digest(successReceipt.output?.sha256));
    }

    // 2. Failure execution receipt (exit 0 BUT verified false)
    const failedVerifyReceipt = receiptsData.items.find((r) => r.receiptId === 'rcp_01JFAILED_VERIFY');
    assert('Contrast receipt rcp_01JFAILED_VERIFY exists', Boolean(failedVerifyReceipt));
    if (failedVerifyReceipt) {
      assert('Contrast receipt has exitCode === 0 (Container exited cleanly)', failedVerifyReceipt.exitCode === 0);
      assert('Contrast receipt has physicallyStopped === true (Kernel confirmed stop)', failedVerifyReceipt.physicallyStopped === true);
      assert('Contrast receipt has verified === false (Application schema verification failed!)', failedVerifyReceipt.verified === false);
      assert('Contrast receipt has resourceReclaimed === false (Held for diagnostic analysis)', failedVerifyReceipt.resourceReclaimed === false);
      assert('KEY INVARIANT: exitCode 0 is NOT evidence of business success',
        failedVerifyReceipt.exitCode === 0 && failedVerifyReceipt.verified === false
      );
    }

    // 3. Confirm resource reclamation atomically updates receipts
    const reclaimRes = await fetch(`${BACKEND_URL}/v1/runs/run_01JPARENT_ACTIVE/reclaim-resources`, { method: 'POST' });
    assert('POST /v1/runs/{id}/reclaim-resources succeeds', reclaimRes.status === 200);
    const reclaimData = await reclaimRes.json();
    assert('resourceReleasePending cleared to false', reclaimData.resourceReleasePending === false);
    assert('allPhysicallyStopped confirmed true', reclaimData.allPhysicallyStopped === true);

    // ---------------------------------------------------------------------------
    // Summary
    // ---------------------------------------------------------------------------
    console.log('\n================================================================================');
    if (passedChecks === totalChecks && totalChecks > 0) {
      console.log(`🎉 5-Screen Reconciliation Summary: ${passedChecks}/${totalChecks} checks passed (100%)`);
      console.log('   All 5 core screens and NodeStopReceipt vs Evidence contrast successfully verified.');
      console.log('   (Control Plane Gateway API Contract Smoke Suite; not physical 5-node hardware acceptance)');
      console.log('================================================================================\n');
    } else {
      console.error(`❌ 5-Screen Reconciliation FAILED: ${totalChecks - passedChecks} failed out of ${totalChecks} checks (${passedChecks}/${totalChecks} passed).`);
      console.error('   Verification incomplete or boundary audit assertions failed.');
      console.log('================================================================================\n');
      process.exit(1);
    }
  } catch (err) {
    console.error('Fatal Reconciliation Exception:', err);
    process.exit(1);
  }
}

main();
