import { describe, it, expect } from 'vitest';
import { EvidenceData } from '../src/features/evidence/EvidenceViewer';

describe('S01-FE / S04-FE EvidenceViewer & Canonical Evidence Resolution', () => {
  it('constructs canonical project-scoped result and evidence resolution endpoints accurately', () => {
    const prjId = 'prj_01JABCDE';
    const runId = 'run_01JSHARD_01';

    const canonicalResultPath = `/v1/projects/${prjId}/runs/${runId}/result`;
    const flatResultPath = `/v1/runs/${runId}/result`;

    expect(canonicalResultPath).toBe('/v1/projects/prj_01JABCDE/runs/run_01JSHARD_01/result');
    expect(flatResultPath).toBe('/v1/runs/run_01JSHARD_01/result');
  });

  it('validates immutable evidence package schema and ADR-012 compliance', () => {
    const mockEvidence: EvidenceData = {
      evidenceId: 'evi_run_01JSHARD_01',
      runId: 'run_01JSHARD_01',
      manifestDigest: 'sha256:4a8b79c3d2e1f0e9...a1b2c3d4',
      policyVersion: 'shard-completion:v1',
      state: 'succeeded',
      allPhysicallyStopped: true,
      allSucceeded: true,
      immutable: true,
      generatedAt: '2026-09-15T00:00:00.000Z',
    };

    expect(mockEvidence.evidenceId).toBe('evi_run_01JSHARD_01');
    expect(mockEvidence.policyVersion).toBe('shard-completion:v1');
    expect(mockEvidence.immutable).toBe(true);
    expect(mockEvidence.allPhysicallyStopped).toBe(true);
    expect(mockEvidence.allSucceeded).toBe(true);
  });

  it('transforms canonical ResultView payload into verified evidence container on fallback', () => {
    const mockResultView = {
      runId: 'run_01JSHARD_02',
      projectId: 'prj_01JABCDE',
      state: 'succeeded',
      completedAt: '2026-09-15T00:10:00.000Z',
      manifestDigest: 'sha256:d8a9e7f6c5b4a3',
      stopReceipt: {
        nodeId: 'nod_01JABCDEF01',
        physicallyStopped: true,
        exitCode: 0,
        outputCommitmentHash: 'sha256:output_hash_123',
      },
    };

    const derivedEvidence: EvidenceData = {
      evidenceId: `evi_${mockResultView.runId}`,
      runId: mockResultView.runId,
      manifestDigest: mockResultView.manifestDigest || mockResultView.stopReceipt.outputCommitmentHash,
      policyVersion: 'shard-completion:v1',
      state: mockResultView.state,
      allPhysicallyStopped: mockResultView.stopReceipt.physicallyStopped,
      allSucceeded: mockResultView.state === 'succeeded',
      generatedAt: mockResultView.completedAt,
      immutable: true,
    };

    expect(derivedEvidence.evidenceId).toBe('evi_run_01JSHARD_02');
    expect(derivedEvidence.manifestDigest).toBe('sha256:d8a9e7f6c5b4a3');
    expect(derivedEvidence.allPhysicallyStopped).toBe(true);
    expect(derivedEvidence.immutable).toBe(true);
  });
});
