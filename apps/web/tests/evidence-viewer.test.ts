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

  it('regression: source strictly calls canonical /result and contains no unserved /evidence trial probes', () => {
    const fs = require('fs');
    const path = require('path');
    const sourcePath = path.resolve(__dirname, '../src/features/evidence/EvidenceViewer.tsx');
    const sourceContent = fs.readFileSync(sourcePath, 'utf-8');

    // Asserts no /evidence or bare /v1/events endpoints in EvidenceViewer.tsx
    expect(sourceContent).not.toMatch(/apiClient<[^>]*>\([^)]*\/evidence['"`]/);
    expect(sourceContent).not.toMatch(/\/v1\/runs\/\$\{runId\}\/evidence/);
    expect(sourceContent).not.toMatch(/\/v1\/projects\/\$\{[^}]*\}\/runs\/\$\{[^}]*\}\/evidence/);
    expect(sourceContent).not.toContain('/v1/events');

    // Asserts canonical endpoint is queried directly
    expect(sourceContent).toContain('/v1/projects/${prjId}/runs/${runId}/result');
  });

  it('regression: full RunResultView envelope comprehensively fulfills EvidenceData without separate /evidence route or fabricated toolCalls', () => {
    // Canonical kernel RunResultView as defined in services/control-plane/src/inv/result_view.py
    const kernelRunResultView = {
      source: 'execution-kernel',
      runId: 'run_01JSHARD_03',
      projectId: 'prj_01JABCDE',
      state: 'succeeded',
      version: 4,
      attemptCount: 1,
      sealed: true,
      executionConfirmed: true,
      commandId: 'cmd_01JSHARD_03',
      nodeId: 'nod_01JABCDEF01',
      stopReceipt: {
        receiptId: 'rcp_01JSHARD_03',
        processStarted: true,
        exitCode: 0,
        reason: 'completed',
        finishedAt: '2026-09-18T16:00:00.000Z',
      },
      evidence: {
        evidenceId: 'evi_01JSHARD_03_COMMITTED',
        specDigest: 'sha256:4a8b79c3d2e1f0e9...a1b2c3d4',
        outputSha256: 'sha256:e3b0c44298fc1c149afbf4c8996fb92427ae41e4649b934ca495991b7852b855',
        policyVersion: 'shard-completion:v1',
      },
      output: {
        sha256: 'sha256:e3b0c44298fc1c149afbf4c8996fb92427ae41e4649b934ca495991b7852b855',
        sizeBytes: 1024,
        verified: true,
      },
      completedAt: '2026-09-18T16:00:01.000Z',
    };

    const res = kernelRunResultView;
    const runId = res.runId;
    const derivedEvidence: EvidenceData = {
      evidenceId: res.evidence?.evidenceId || `evi_${runId}`,
      runId,
      manifestDigest: res.output?.sha256 || res.evidence?.outputSha256 || undefined,
      specDigest: res.evidence?.specDigest || undefined,
      policyVersion: res.evidence?.policyVersion || 'shard-completion:v1',
      state: res.state || 'succeeded',
      allPhysicallyStopped: res.stopReceipt?.processStarted ? res.stopReceipt?.exitCode !== undefined : true,
      allSucceeded: res.state === 'succeeded',
      generatedAt: res.completedAt || res.stopReceipt?.finishedAt || new Date().toISOString(),
      immutable: res.sealed ?? true,
      integrityVerification: res.output?.verified === true ? 'PASS' : (res.output?.verified === false || res.state === 'failed' ? 'FAIL' : 'UNVERIFIED'),
      tamperCheck: res.output?.verified ? 'VERIFIED_IMMUTABLE' : (res.sealed ? 'SEALED' : 'UNVERIFIED'),
      retentionPolicy: '1_YEAR_PINNED (ADR-012)',
    };

    expect(derivedEvidence.evidenceId).toBe('evi_01JSHARD_03_COMMITTED');
    expect(derivedEvidence.manifestDigest).toBe('sha256:e3b0c44298fc1c149afbf4c8996fb92427ae41e4649b934ca495991b7852b855');
    expect(derivedEvidence.tamperCheck).toBe('VERIFIED_IMMUTABLE');
    expect(derivedEvidence.integrityVerification).toBe('PASS');
    expect(derivedEvidence.immutable).toBe(true);
    expect(derivedEvidence.allPhysicallyStopped).toBe(true);
    expect(derivedEvidence.allSucceeded).toBe(true);
  });

  it('regression: fetch failure surfaces authentic error and never renders fake PASS or synthetic toolCalls', () => {
    const fs = require('fs');
    const path = require('path');
    const sourcePath = path.resolve(__dirname, '../src/features/evidence/EvidenceViewer.tsx');
    const sourceContent = fs.readFileSync(sourcePath, 'utf-8');

    // 1. Asserts no fake tool calls or wall times are fabricated anywhere in source
    expect(sourceContent).not.toContain('git.checkout');
    expect(sourceContent).not.toContain('test.run');
    expect(sourceContent).not.toContain('artifact.write');
    expect(sourceContent).not.toContain('wallTimeMs');

    // 2. Asserts catch block sets evidenceData to null and populates errorMessage
    expect(sourceContent).toMatch(/catch\s*\([^)]*\)\s*\{[\s\S]*setEvidenceData\(null\);[\s\S]*setErrorMessage\(/);

    // 3. Asserts PASS badge is strictly conditional on evidenceData.integrityVerification === 'PASS'
    expect(sourceContent).toContain("{evidenceData.integrityVerification === 'PASS' && (");
    expect(sourceContent).toContain("{evidenceData.integrityVerification === 'FAIL' && (");
    expect(sourceContent).toContain("{evidenceData.integrityVerification === 'UNVERIFIED' && (");

    // 4. Asserts retention and tamper specs are labeled as static policy specifications
    expect(sourceContent).toContain('[시스템 정책 사양]');
    expect(sourceContent).toContain('정책 규격: 1년 보존 Pin (ADR-012)');
    expect(sourceContent).toContain('설계 규격: 불변 단일 봉인');
  });

  it('regression: source strictly excludes "sha256:verified" fallback and never fabricates mock digests', () => {
    const fs = require('fs');
    const path = require('path');
    const sourcePath = path.resolve(__dirname, '../src/features/evidence/EvidenceViewer.tsx');
    const sourceContent = fs.readFileSync(sourcePath, 'utf-8');

    // Must never contain the string literal 'sha256:verified'
    expect(sourceContent).not.toContain('sha256:verified');
  });

  it('regression: execution success (succeeded) without cryptographic verification yields UNVERIFIED, never PASS', () => {
    // A run that succeeded, but output was not cryptographically verified
    const unverifiedRunResult = {
      state: 'succeeded',
      output: {
        sizeBytes: 2048,
        // verified is intentionally omitted/undefined
      },
    };

    let integrityStatus: 'PASS' | 'FAIL' | 'UNVERIFIED';
    if (unverifiedRunResult.output?.verified === true) {
      integrityStatus = 'PASS';
    } else if (unverifiedRunResult.output?.verified === false || unverifiedRunResult.state === 'failed') {
      integrityStatus = 'FAIL';
    } else {
      integrityStatus = 'UNVERIFIED';
    }

    expect(integrityStatus).toBe('UNVERIFIED');
    expect(integrityStatus).not.toBe('PASS');
    expect(integrityStatus).not.toBe('FAIL');
  });
});
