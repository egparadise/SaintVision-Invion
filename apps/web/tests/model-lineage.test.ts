import { describe, it, expect } from 'vitest';
import { MlopsManager } from '../src/features/mlops/mlopsEngine';

describe('S10-FE: Model Lineage, Multi-Provider Conformance & Gated Deployment (AC-10)', () => {
  describe('Provider Adapter Conformance (AC-10 Codex = Claude)', () => {
    it('verifies Codex and Claude adapters conform to identical schemas and protocols', () => {
      const mlops = new MlopsManager();
      const conformances = mlops.verifyProviderConformances();

      const codex = conformances.find((c) => c.provider === 'Codex');
      const claude = conformances.find((c) => c.provider === 'Claude');

      expect(codex).toBeDefined();
      expect(claude).toBeDefined();

      // Identical contract version
      expect(codex?.contractVersion).toBe('v1.0.0-ADR-004');
      expect(claude?.contractVersion).toBe('v1.0.0-ADR-004');
      expect(codex?.contractVersion).toBe(claude?.contractVersion);

      // Conformance passed
      expect(codex?.conformancePassed).toBe(true);
      expect(claude?.conformancePassed).toBe(true);

      // Common protocols supported
      expect(codex?.supportedProtocols).toContain('SSE-v2');
      expect(codex?.supportedProtocols).toContain('W3C-TraceContext');
      expect(claude?.supportedProtocols).toContain('SSE-v2');
      expect(claude?.supportedProtocols).toContain('W3C-TraceContext');
    });
  });

  describe('Reverse Lineage Traceability Query (AC-10 역추적)', () => {
    it('reversely traces model lineage from deployment digest to root dataset and commit', () => {
      const mlops = new MlopsManager();

      // Query by deployment digest
      const digest = 'sha256:4a8b2c1d9f3e5a7b8c9d0e1f2a3b4c5d6e7f8a9b0c1d2e3f4a5b6c7d8e9f0a1b';
      const lineage = mlops.queryLineage(digest);

      expect(lineage).toBeDefined();
      expect(lineage?.modelId).toBe('mod_pacs_seg_v2');
      expect(lineage?.datasetDigest).toMatch(/^dset_sha256_/);
      expect(lineage?.sourceCommitSha).toBe('58cabd3e4f5a6b7c8d9e0f1a2b3c4d5e6f7a8b9c');
      expect(lineage?.trainingRunId).toBe('run_01JABCDE0001');
      expect(lineage?.evalAccuracy).toBe(0.948);
      expect(lineage?.approvalId).toBe('apr_01JXYZ987654');
    });

    it('reversely traces model lineage from git commit SHA to deployed model', () => {
      const mlops = new MlopsManager();

      // Query by commit SHA
      const commitSha = '39699e9b0c1d2e3f4a5b6c7d8e9f0a1b2c3d4e5f';
      const lineage = mlops.queryLineage(commitSha);

      expect(lineage).toBeDefined();
      expect(lineage?.modelId).toBe('mod_pacs_cls_v1');
      expect(lineage?.deploymentDigest).toMatch(/^sha256:/);
      expect(lineage?.status).toBe('deployed');
    });
  });

  describe('Gated Model Deployment (AC-10)', () => {
    it('blocks deployment if accuracy is below 85% threshold or approval is missing', () => {
      const mlops = new MlopsManager();
      const targetModelId = 'mod_experimental_vit_v3'; // Acc: 81.2% (< 85%)

      // 1. Missing approval ID -> blocked
      const attempt1 = mlops.deployModel({
        modelId: targetModelId,
        approvalId: '',
      });
      expect(attempt1.success).toBe(false);
      expect(attempt1.error).toContain('Two-Person Rule approval ID is required');

      // 2. Below accuracy threshold -> blocked
      const attempt2 = mlops.deployModel({
        modelId: targetModelId,
        approvalId: 'apr_01JXYZ999999',
      });
      expect(attempt2.success).toBe(false);
      expect(attempt2.error).toContain('below mandatory threshold (85.0%)');

      // 3. Qualified model with Acc >= 85% and approval ID -> deployed with digest
      const qualifiedModel = mlops.getLineages().find((m) => m.evalAccuracy >= 0.85)!;
      const attempt3 = mlops.deployModel({
        modelId: qualifiedModel.modelId,
        approvalId: 'apr_01JXYZ777777',
      });
      expect(attempt3.success).toBe(true);
      expect(attempt3.deployedModel?.deploymentDigest).toMatch(/^sha256:[0-9a-f]{64}$/);
      expect(attempt3.deployedModel?.status).toBe('deployed');
    });
  });
});
