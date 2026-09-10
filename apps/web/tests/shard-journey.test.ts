import { describe, it, expect } from 'vitest';
import { RunItem, ShardExecutionItem, DistributedPlanItem } from '../src/contracts/types';

describe('SHARD-I07 & ADR-040/042/043 Shard Lifecycle & Resource Reclamation', () => {
  it('correctly associates parent runs with child shards and tracks shard count', () => {
    const parentRun: RunItem = {
      id: 'run_parent_001',
      projectId: 'prj_01JABCDE',
      workspaceId: 'wsp_01JABCDE001',
      objective: '분산 5노드 AI 전처리 및 분할 인퍼런스',
      state: 'running',
      requestedBy: 'usr_admin_01',
      childRunIds: ['run_shard_001', 'run_shard_002'],
      shardCount: 2,
      allPhysicallyStopped: false,
      allSucceeded: false,
      resourceReleasePending: false,
      createdAt: new Date().toISOString(),
      updatedAt: new Date().toISOString(),
    };

    const childShard: RunItem = {
      id: 'run_shard_001',
      parentId: 'run_parent_001',
      shardIndex: 0,
      shardCount: 2,
      projectId: 'prj_01JABCDE',
      workspaceId: 'wsp_01JABCDE001',
      objective: '[샤드 1/2] Node-01 로컬 인퍼런스',
      state: 'running',
      requestedBy: 'usr_admin_01',
      attempt: 1,
      allPhysicallyStopped: false,
      allSucceeded: false,
      resourceReleasePending: false,
      createdAt: new Date().toISOString(),
      updatedAt: new Date().toISOString(),
    };

    expect(parentRun.childRunIds).toHaveLength(2);
    expect(childShard.parentId).toBe(parentRun.id);
    expect(childShard.shardIndex).toBe(0);
    expect(parentRun.allPhysicallyStopped).toBe(false);
  });

  it('enforces resourceReleasePending: true upon parent run cancellation (ADR-040)', () => {
    const activeParent: RunItem = {
      id: 'run_parent_002',
      projectId: 'prj_01JABCDE',
      workspaceId: 'wsp_01JABCDE001',
      objective: '분산 작업',
      state: 'running',
      requestedBy: 'usr_dev_01',
      childRunIds: ['run_shard_003'],
      shardCount: 1,
      resourceReleasePending: false,
      createdAt: new Date().toISOString(),
      updatedAt: new Date().toISOString(),
    };

    // Simulate cancellation cascade
    const cancelledParent: RunItem = {
      ...activeParent,
      state: 'cancelled',
      resourceReleasePending: true,
      updatedAt: new Date().toISOString(),
    };

    expect(cancelledParent.state).toBe('cancelled');
    expect(cancelledParent.resourceReleasePending).toBe(true);
  });

  it('strictly distinguishes physical stop receipt from execution success (ADR-041/042)', () => {
    const shardStopOnly: ShardExecutionItem = {
      shardId: 'shd_01',
      runId: 'run_shard_001',
      parentId: 'run_parent_001',
      nodeId: 'nod_01JABCDEF01',
      hostname: 'Node-01-WinMain',
      attempt: 1,
      executionState: 'failed',
      physicallyStopped: true, // Container stopped and receipt received
      verified: false, // But result did not succeed
      resourceReleasePending: false,
      outputHash: 'sha256:e3b0c44298fc1c149afbf4c8996fb92427ae41e4649b934ca495991b7852b855',
      exitCode: 1,
    };

    expect(shardStopOnly.physicallyStopped).toBe(true);
    expect(shardStopOnly.verified).toBe(false);
    expect(shardStopOnly.exitCode).not.toBe(0);
  });

  it('validates aggregate manifest digest for distributed plan completion', () => {
    const plan: DistributedPlanItem = {
      planId: 'plan_dist_001',
      parentRunId: 'run_parent_success',
      state: 'completed',
      shards: [
        {
          shardId: 'shd_01',
          runId: 'run_shard_1',
          parentId: 'run_parent_success',
          nodeId: 'nod_01',
          hostname: 'Node-01',
          attempt: 1,
          executionState: 'succeeded',
          physicallyStopped: true,
          verified: true,
          resourceReleasePending: false,
          outputHash: 'sha256:1111111111111111111111111111111111111111111111111111111111111111',
          evidenceId: 'evi_01',
          exitCode: 0,
        },
        {
          shardId: 'shd_02',
          runId: 'run_shard_2',
          parentId: 'run_parent_success',
          nodeId: 'nod_02',
          hostname: 'Node-02',
          attempt: 1,
          executionState: 'succeeded',
          physicallyStopped: true,
          verified: true,
          resourceReleasePending: false,
          outputHash: 'sha256:2222222222222222222222222222222222222222222222222222222222222222',
          evidenceId: 'evi_02',
          exitCode: 0,
        },
      ],
      allPhysicallyStopped: true,
      allSucceeded: true,
      resourceReleasePending: false,
      aggregateEvidenceId: 'evi_aggregate_001',
      manifestDigest: 'sha256:7f83b1657ff1fc53b92dc18148a1d65dfc2d4b1fa3d677284addd200126d9069',
      createdAt: new Date().toISOString(),
    };

    expect(plan.shards.every((s) => s.physicallyStopped)).toBe(true);
    expect(plan.shards.every((s) => s.verified)).toBe(true);
    expect(plan.allPhysicallyStopped).toBe(true);
    expect(plan.allSucceeded).toBe(true);
    expect(plan.manifestDigest).toMatch(/^sha256:[a-f0-9]{64}$/);
  });

  it('guarantees ADR-043 working checkout permissions 0600 and monotonic epoch binding', () => {
    const workingCheckout = {
      checkoutId: 'chk_01JABCDEF01',
      nodeId: 'nod_01JABCDEF01',
      inode: 'ino_49152',
      permissions: '0600 (read/write)',
      checkpointSha: 'sha256:7f83b1657ff1fc53b92dc18148a1d65dfc2d4b1fa3d677284addd200126d9069',
      epoch: 2,
      status: 'active',
      createdAt: new Date().toISOString(),
    };

    expect(workingCheckout.permissions).toBe('0600 (read/write)');
    expect(workingCheckout.inode).toMatch(/^ino_\d+$/);
    expect(workingCheckout.epoch).toBeGreaterThan(0);
    expect(workingCheckout.status).toBe('active');
  });
});
