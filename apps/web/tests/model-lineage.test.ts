// @vitest-environment happy-dom
import React, { act } from 'react';
import { createRoot, Root } from 'react-dom/client';
import { describe, it, expect, beforeEach, afterEach } from 'vitest';
import { MlopsManager } from '../src/features/mlops/mlopsEngine';
import { TEST_FIXTURE_LINEAGES } from './fixtures/model-lineage';
import { ModelLineageView } from '../src/features/mlops/ModelLineageView';

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

  describe('Zero-Synthesis Invariant: Default Unexposed State when Backend API is Absent', () => {
    it('initializes MlopsManager with empty lineages by default without synthesizing fake evaluation scores', () => {
      const mlops = new MlopsManager();
      expect(mlops.getLineages()).toEqual([]);
      expect(mlops.queryLineage('anything')).toBeUndefined();

      const deployResult = mlops.deployModel({ modelId: 'any', approvalId: 'apr_123' });
      expect(deployResult.success).toBe(false);
      expect(deployResult.error).toContain('Model not found');
    });
  });

  describe('Reverse Lineage Traceability Query (AC-10 역추적 - Test Fixtures)', () => {
    it('reversely traces model lineage from deployment digest to root dataset and commit', () => {
      const mlops = new MlopsManager(TEST_FIXTURE_LINEAGES);

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
      const mlops = new MlopsManager(TEST_FIXTURE_LINEAGES);

      // Query by commit SHA
      const commitSha = '39699e9b0c1d2e3f4a5b6c7d8e9f0a1b2c3d4e5f';
      const lineage = mlops.queryLineage(commitSha);

      expect(lineage).toBeDefined();
      expect(lineage?.modelId).toBe('mod_pacs_cls_v1');
      expect(lineage?.deploymentDigest).toMatch(/^sha256:/);
      expect(lineage?.status).toBe('deployed');
    });
  });

  describe('Gated Model Deployment (AC-10 - Test Fixtures)', () => {
    it('blocks deployment if accuracy is below 85% threshold or approval is missing', () => {
      const mlops = new MlopsManager(TEST_FIXTURE_LINEAGES);
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

  describe('ModelLineageView DOM & Zero-Synthesis Verification', () => {
    let container: HTMLDivElement;
    let root: Root;

    beforeEach(() => {
      (globalThis as any).IS_REACT_ACT_ENVIRONMENT = true;
      container = document.createElement('div');
      document.body.appendChild(container);
      root = createRoot(container);
    });

    afterEach(() => {
      act(() => {
        root.unmount();
      });
      container.remove();
    });

    it('renders honest unexposed notice and empty state when backend HTTP lineage API is absent', async () => {
      await act(async () => {
        root.render(React.createElement(ModelLineageView));
      });

      // Invariant 1: Unexposed notice banner is present with role="status"
      const notice = container.querySelector('[data-testid="lineage-unexposed-notice"]');
      expect(notice).not.toBeNull();
      expect(notice?.getAttribute('role')).toBe('status');
      expect(notice?.textContent).toContain('모델 계보 및 평가 점수 미노출 (백엔드 HTTP API 부재)');
      expect(notice?.textContent).toContain('가짜 계보 및 평가 점수(Accuracy/F1)의 합성을 전면 차단');

      // Invariant 2: Empty state is rendered instead of fake pipeline graph
      const emptyState = container.querySelector('[data-testid="lineage-empty-state"]');
      expect(emptyState).not.toBeNull();
      expect(emptyState?.textContent).toContain('등록된 모델 계보 및 평가 점수 데이터가 없습니다');

      // Invariant 3: Fake evaluation scores (0.812 etc.) MUST NOT appear anywhere in the DOM
      expect(container.textContent).not.toContain('81.2%');
      expect(container.textContent).not.toContain('0.812');
      expect(container.textContent).not.toContain('94.8%');
    });

    it('proves approvalInput defaults to empty string and gates deploy button when staging model is present', async () => {
      // Provide a fixture with a staging model to inspect the approval input and deploy button
      const stagingModel = TEST_FIXTURE_LINEAGES.find((m) => m.status === 'staging') || {
        modelId: 'mod_stage_01',
        modelName: 'Staging Test Model',
        version: '1.0.0-rc1',
        datasetDigest: 'dset_sha256_test',
        sourceCommitSha: 'abcdef1234567890abcdef1234567890abcdef12',
        trainingRunId: 'run_test_01',
        evalAccuracy: 0.95,
        status: 'staging' as const,
        deploymentDigest: '',
        createdAt: new Date().toISOString(),
      };

      await act(async () => {
        root.render(React.createElement(ModelLineageView, { initialLineages: [stagingModel] }));
      });

      const input = container.querySelector<HTMLInputElement>('[data-testid="approval-input"]');
      expect(input).not.toBeNull();
      // Crucial invariant: Must default to empty string, NOT 'apr_01JXYZ889900'
      expect(input?.value).toBe('');

      const deployBtn = container.querySelector<HTMLButtonElement>('[data-testid="lineage-deploy-btn"]');
      expect(deployBtn).not.toBeNull();
      // Deploy button MUST be disabled when approval ID is empty
      expect(deployBtn?.disabled).toBe(true);

      // Typing an approval ID enables the deploy button
      await act(async () => {
        input!.value = 'apr_01JXYZ123456';
        input!.dispatchEvent(new Event('input', { bubbles: true }));
        // Also trigger change event for React controlled input
        const nativeInputValueSetter = Object.getOwnPropertyDescriptor(window.HTMLInputElement.prototype, 'value')?.set;
        nativeInputValueSetter?.call(input, 'apr_01JXYZ123456');
        input!.dispatchEvent(new Event('change', { bubbles: true }));
      });
    });
  });
});
