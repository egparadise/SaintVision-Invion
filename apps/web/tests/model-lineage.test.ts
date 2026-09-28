// @vitest-environment happy-dom
import React, { act } from 'react';
import { createRoot, Root } from 'react-dom/client';
import { describe, it, expect, beforeEach, afterEach, vi } from 'vitest';
import { MlopsManager } from '../src/features/mlops/mlopsEngine';
import { TEST_FIXTURE_LINEAGES } from './fixtures/model-lineage';
import { ModelLineageView } from '../src/features/mlops/ModelLineageView';
import type { ProblemDetails } from '../src/contracts/types';

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

    it('reversely traces model lineage from dataset digest (dset_sha256...) to root model', () => {
      const mlops = new MlopsManager(TEST_FIXTURE_LINEAGES);

      // Query by dataset digest prefix and full digest
      const targetModel = TEST_FIXTURE_LINEAGES[0];
      const lineageByFullDigest = mlops.queryLineage(targetModel.datasetDigest);
      expect(lineageByFullDigest).toBeDefined();
      expect(lineageByFullDigest?.modelId).toBe(targetModel.modelId);

      const lineageByPartialDigest = mlops.queryLineage('dset_sha256');
      expect(lineageByPartialDigest).toBeDefined();

      // Empty or whitespace term returns undefined
      expect(mlops.queryLineage('')).toBeUndefined();
      expect(mlops.queryLineage('   ')).toBeUndefined();
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
      expect(attempt3.isSimulated).toBe(true);
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

    it('verifies Adapter Conformance displays unmeasured "미측정 (NOT_OBSERVED)" and NEVER "100% CONFORMING" or fake PASS counts', async () => {
      await act(async () => {
        root.render(React.createElement(ModelLineageView, { initialLineages: TEST_FIXTURE_LINEAGES }));
      });

      // Strict Invariant 1: "100% CONFORMING" is strictly forbidden (must be unmeasured)
      expect(container.textContent).not.toContain('100% CONFORMING');
      expect(container.textContent).not.toContain('100%');
      expect(container.textContent).not.toContain('PASS');

      // Strict Invariant 2: Explicit unmeasured status is rendered in top metrics and panel
      const topStatus = container.querySelector('[data-testid="conformance-top-status"]');
      expect(topStatus?.textContent).toBe('미측정 (NOT_OBSERVED)');
      expect(container.textContent).toContain('미측정 (NOT_OBSERVED)');

      // Strict Invariant 3: Unmeasured notice guides user to real control-plane API
      const unmeasuredNotice = container.querySelector('[data-testid="conformance-unmeasured-notice"]');
      expect(unmeasuredNotice).not.toBeNull();
      expect(unmeasuredNotice?.textContent).toContain('미측정 (NOT_OBSERVED)');
      expect(unmeasuredNotice?.textContent).toContain('GET /v1/projects/:projectId/adapters/conformance');

      // Strict Invariant 4: Live region container is permanently mounted in DOM
      const liveStatus = container.querySelector('[data-testid="conformance-live-status"]');
      expect(liveStatus).not.toBeNull();
      expect(liveStatus?.getAttribute('role')).toBe('status');
      expect(liveStatus?.getAttribute('aria-live')).toBe('polite');
    });

    it('verifies Node 1-5 labels are qualified with (모의) and deployed node NEVER displays "Production Live"', async () => {
      const deployedModel = TEST_FIXTURE_LINEAGES.find((m) => m.status === 'deployed')!;
      await act(async () => {
        root.render(React.createElement(ModelLineageView, { initialLineages: [deployedModel] }));
      });

      // Strict Invariant 1: Node labels lowered to mock/qualifier
      expect(container.textContent).toContain('SHA-256 (모의 표기)');
      expect(container.textContent).toContain('Git Signed SHA (모의 표기)');
      expect(container.textContent).toContain('Isolated Runtime (모의)');
      expect(container.textContent).toContain('4. EVALUATION (모의 점수)');
      expect(container.textContent).toContain('Two-Person Rule (모의)');

      // Strict Invariant 2: Deployed model MUST NEVER claim "Production Live"
      expect(container.textContent).not.toContain('Production Live');
      expect(container.textContent).toContain('모의 배포 완료 (백엔드 digest 고정과 무관 · 실 환경 미배포)');
      expect(container.textContent).toContain('6. DEPLOYMENT DIGEST (모의 시뮬레이션)');

      // Strict Invariant 3: Reverse query prompt mentions dataset hash
      expect(container.textContent).toContain('데이터셋 해시(dset_sha256...)로 역추적');
    });

    it('renders Real Model Commitment Observation Panel and fetches commitment via control-plane API', async () => {
      const originalFetch = globalThis.fetch;
      const testProjectId = 'prj_0123456789ABCDEFGHJKMNPQRS';
      const testModelId = 'mdl_0123456789ABCDEFGHJKMNPQRS';
      const testVersion = '1.0.0';
      const testManifestHash = '7f83b1657ff1fc53b92dc18148a1d65dfc2d4b1fa3d677284addd200126d9069';
      const testSourceRunId = 'run_0123456789ABCDEFGHJKMNPQRS';
      const testRecoveryEpoch = '33333333-3333-4333-8333-333333333333';

      const mockCommitmentResponse = {
        projectId: testProjectId,
        modelId: testModelId,
        version: testVersion,
        manifestHash: testManifestHash,
        sourceRunId: testSourceRunId,
        committedAt: '2026-09-28T09:00:00Z',
        commitRecoveryEpoch: testRecoveryEpoch,
        format: 'safetensors',
        totalBytes: 52428800,
        shardCount: 4,
        licensePolicy: 'Apache-2.0',
        classification: 'internal',
        committed: true,
        currentAvailability: 'unknown',
        requiresExecutionRevalidation: true,
      };

      try {
        globalThis.fetch = vi.fn().mockResolvedValue({
          ok: true,
          status: 200,
          headers: new Headers({ 'content-type': 'application/json' }),
          json: async () => mockCommitmentResponse,
        } as any);

        await act(async () => {
          root.render(React.createElement(ModelLineageView, { initialLineages: TEST_FIXTURE_LINEAGES }));
        });

        const panel = container.querySelector('[data-testid="model-commitment-panel"]');
        expect(panel).not.toBeNull();
        expect(panel?.textContent).toContain('실제 모델 Commitment 조회 (Control-Plane HTTP API)');

        const projectInput = container.querySelector<HTMLInputElement>('[data-testid="commitment-project-input"]');
        const modelInput = container.querySelector<HTMLInputElement>('[data-testid="commitment-model-input"]');
        const versionInput = container.querySelector<HTMLInputElement>('[data-testid="commitment-version-input"]');
        const fetchBtn = container.querySelector<HTMLButtonElement>('[data-testid="commitment-fetch-btn"]');

        expect(projectInput).not.toBeNull();
        expect(modelInput).not.toBeNull();
        expect(versionInput).not.toBeNull();
        expect(fetchBtn).not.toBeNull();

        // Inputs default to empty string requiring explicit context
        expect(projectInput?.value).toBe('');

        // Explicitly set inputs according to canonical schema format
        const setInputValue = (el: HTMLInputElement, val: string) => {
          const setter = Object.getOwnPropertyDescriptor(window.HTMLInputElement.prototype, 'value')?.set;
          setter?.call(el, val);
          el.dispatchEvent(new Event('input', { bubbles: true }));
          el.dispatchEvent(new Event('change', { bubbles: true }));
        };

        await act(async () => {
          setInputValue(projectInput!, testProjectId);
          setInputValue(modelInput!, testModelId);
          setInputValue(versionInput!, testVersion);
        });

        // Trigger fetch and flush async execution
        await act(async () => {
          fetchBtn!.click();
        });
        await act(async () => {
          await new Promise((resolve) => setTimeout(resolve, 0));
        });

        expect(globalThis.fetch).toHaveBeenCalled();

        // Invariant: manifestHash, sourceRunId, availability, and revalidation must be displayed
        const manifestHashEl = container.querySelector('[data-testid="commitment-manifest-hash"]');
        const sourceRunIdEl = container.querySelector('[data-testid="commitment-source-run-id"]');
        const availabilityEl = container.querySelector('[data-testid="commitment-availability"]');
        const revalidationEl = container.querySelector('[data-testid="commitment-revalidation"]');

        expect(manifestHashEl?.textContent).toBe(mockCommitmentResponse.manifestHash);
        expect(sourceRunIdEl?.textContent).toBe(mockCommitmentResponse.sourceRunId);
        expect(availabilityEl?.textContent).toBe('unknown');
        expect(revalidationEl?.textContent).toContain('Required (true)');

        // Now test 404 canonical ProblemDetails failure handling
        const canonical404Problem: ProblemDetails = {
          type: 'about:blank',
          title: 'Not Found',
          status: 404,
          code: 'MODEL-0004',
          category: 'RES',
          detail: 'Committed model not found',
          retryable: false,
          traceId: '0123456789abcdef0123456789abcdef',
          causeRef: null,
          evidenceId: null,
        };

        globalThis.fetch = vi.fn().mockResolvedValue({
          ok: false,
          status: 404,
          statusText: 'Not Found',
          headers: new Headers({ 'content-type': 'application/problem+json' }),
          json: async () => canonical404Problem,
        } as any);

        await act(async () => {
          fetchBtn!.click();
        });
        await act(async () => {
          await new Promise((resolve) => setTimeout(resolve, 0));
        });

        const errorBanner = container.querySelector('[data-testid="commitment-error-banner"]');
        expect(errorBanner).not.toBeNull();
        expect(errorBanner?.getAttribute('role')).toBe('alert');
        expect(errorBanner?.textContent).toContain('MODEL-0004');
        expect(errorBanner?.textContent).toContain('404');
        expect(errorBanner?.textContent).toContain('Committed model not found');
      } finally {
        globalThis.fetch = originalFetch;
      }
    });

    it('rejects invalid ModelCommitObservation violating strict schema guard and hides corrupted details', async () => {
      const originalFetch = globalThis.fetch;
      const testProjectId = 'prj_0123456789ABCDEFGHJKMNPQRS';
      const testModelId = 'mdl_0123456789ABCDEFGHJKMNPQRS';
      const testVersion = '1.0.0';

      const corruptedPayload = {
        projectId: testProjectId,
        modelId: testModelId,
        version: testVersion,
        manifestHash: 'bad_hash_not_64_hex', // violates manifestHash schema
        sourceRunId: 'run_0123456789ABCDEFGHJKMNPQRS',
        committedAt: '2026-09-28T09:00:00Z',
        commitRecoveryEpoch: '33333333-3333-4333-8333-333333333333',
        format: 'safetensors',
        totalBytes: 52428800,
        shardCount: 4,
        licensePolicy: 'Apache-2.0',
        classification: 'internal',
        committed: true,
        currentAvailability: 'unknown',
        requiresExecutionRevalidation: true,
      };

      try {
        globalThis.fetch = vi.fn().mockResolvedValue({
          ok: true,
          status: 200,
          headers: new Headers({ 'content-type': 'application/json' }),
          json: async () => corruptedPayload,
        } as any);

        await act(async () => {
          root.render(React.createElement(ModelLineageView, { initialLineages: TEST_FIXTURE_LINEAGES }));
        });

        const projectInput = container.querySelector<HTMLInputElement>('[data-testid="commitment-project-input"]');
        const modelInput = container.querySelector<HTMLInputElement>('[data-testid="commitment-model-input"]');
        const versionInput = container.querySelector<HTMLInputElement>('[data-testid="commitment-version-input"]');
        const fetchBtn = container.querySelector<HTMLButtonElement>('[data-testid="commitment-fetch-btn"]');

        const setInputValue = (el: HTMLInputElement, val: string) => {
          const setter = Object.getOwnPropertyDescriptor(window.HTMLInputElement.prototype, 'value')?.set;
          setter?.call(el, val);
          el.dispatchEvent(new Event('input', { bubbles: true }));
          el.dispatchEvent(new Event('change', { bubbles: true }));
        };

        await act(async () => {
          setInputValue(projectInput!, testProjectId);
          setInputValue(modelInput!, testModelId);
          setInputValue(versionInput!, testVersion);
        });

        await act(async () => {
          fetchBtn!.click();
        });
        await act(async () => {
          await new Promise((resolve) => setTimeout(resolve, 0));
        });

        const errorBanner = container.querySelector('[data-testid="commitment-error-banner"]');
        expect(errorBanner).not.toBeNull();
        expect(errorBanner?.getAttribute('role')).toBe('alert');
        expect(errorBanner?.textContent).toContain('클라이언트 응답 계약 검증 실패');
        expect(errorBanner?.textContent).toContain('ModelCommitObservation 응답 계약 불일치');
        expect(errorBanner?.textContent).not.toContain('500');
        expect(errorBanner?.textContent).not.toContain('(500)');
        expect(errorBanner?.textContent).not.toContain('FETCH_ERROR');

        // Critical: corrupt data must NOT be rendered
        const resultContainer = container.querySelector('[data-testid="commitment-result-container"]');
        expect(resultContainer).toBeNull();
      } finally {
        globalThis.fetch = originalFetch;
      }
    });

    it('rejects ModelCommitObservation with extra property (violating additionalProperties: false)', async () => {
      const originalFetch = globalThis.fetch;
      const testProjectId = 'prj_0123456789ABCDEFGHJKMNPQRS';
      const testModelId = 'mdl_0123456789ABCDEFGHJKMNPQRS';
      const testVersion = '1.0.0';

      const payloadWithExtraProp = {
        projectId: testProjectId,
        modelId: testModelId,
        version: testVersion,
        manifestHash: '7f83b1657ff1fc53b92dc18148a1d65dfc2d4b1fa3d677284addd200126d9069',
        sourceRunId: 'run_0123456789ABCDEFGHJKMNPQRS',
        committedAt: '2026-09-28T09:00:00Z',
        commitRecoveryEpoch: '33333333-3333-4333-8333-333333333333',
        format: 'safetensors',
        totalBytes: 52428800,
        shardCount: 4,
        licensePolicy: 'Apache-2.0',
        classification: 'internal',
        committed: true,
        currentAvailability: 'unknown',
        requiresExecutionRevalidation: true,
        unexpectedProperty: 'violates_additionalProperties_false', // extra property
      };

      try {
        globalThis.fetch = vi.fn().mockResolvedValue({
          ok: true,
          status: 200,
          headers: new Headers({ 'content-type': 'application/json' }),
          json: async () => payloadWithExtraProp,
        } as any);

        await act(async () => {
          root.render(React.createElement(ModelLineageView, { initialLineages: TEST_FIXTURE_LINEAGES }));
        });

        const projectInput = container.querySelector<HTMLInputElement>('[data-testid="commitment-project-input"]');
        const modelInput = container.querySelector<HTMLInputElement>('[data-testid="commitment-model-input"]');
        const versionInput = container.querySelector<HTMLInputElement>('[data-testid="commitment-version-input"]');
        const fetchBtn = container.querySelector<HTMLButtonElement>('[data-testid="commitment-fetch-btn"]');

        const setInputValue = (el: HTMLInputElement, val: string) => {
          const setter = Object.getOwnPropertyDescriptor(window.HTMLInputElement.prototype, 'value')?.set;
          setter?.call(el, val);
          el.dispatchEvent(new Event('input', { bubbles: true }));
          el.dispatchEvent(new Event('change', { bubbles: true }));
        };

        await act(async () => {
          setInputValue(projectInput!, testProjectId);
          setInputValue(modelInput!, testModelId);
          setInputValue(versionInput!, testVersion);
        });

        await act(async () => {
          fetchBtn!.click();
        });
        await act(async () => {
          await new Promise((resolve) => setTimeout(resolve, 0));
        });

        const errorBanner = container.querySelector('[data-testid="commitment-error-banner"]');
        expect(errorBanner).not.toBeNull();
        expect(errorBanner?.getAttribute('role')).toBe('alert');
        expect(errorBanner?.textContent).toContain('클라이언트 응답 계약 검증 실패');
        expect(errorBanner?.textContent).toContain('ModelCommitObservation 응답 계약 불일치');
        expect(errorBanner?.textContent).not.toContain('500');
        expect(errorBanner?.textContent).not.toContain('(500)');
        expect(errorBanner?.textContent).not.toContain('FETCH_ERROR');

        const resultContainer = container.querySelector('[data-testid="commitment-result-container"]');
        expect(resultContainer).toBeNull();
      } finally {
        globalThis.fetch = originalFetch;
      }
    });

    it('rejects ModelCommitObservation with invalid calendar date-time (e.g. 2026-02-30T25:61:00Z)', async () => {
      const originalFetch = globalThis.fetch;
      const testProjectId = 'prj_0123456789ABCDEFGHJKMNPQRS';
      const testModelId = 'mdl_0123456789ABCDEFGHJKMNPQRS';
      const testVersion = '1.0.0';

      const payloadWithInvalidDate = {
        projectId: testProjectId,
        modelId: testModelId,
        version: testVersion,
        manifestHash: '7f83b1657ff1fc53b92dc18148a1d65dfc2d4b1fa3d677284addd200126d9069',
        sourceRunId: 'run_0123456789ABCDEFGHJKMNPQRS',
        committedAt: '2026-02-30T25:61:00Z', // impossible calendar date & time
        commitRecoveryEpoch: '33333333-3333-4333-8333-333333333333',
        format: 'safetensors',
        totalBytes: 52428800,
        shardCount: 4,
        licensePolicy: 'Apache-2.0',
        classification: 'internal',
        committed: true,
        currentAvailability: 'unknown',
        requiresExecutionRevalidation: true,
      };

      try {
        globalThis.fetch = vi.fn().mockResolvedValue({
          ok: true,
          status: 200,
          headers: new Headers({ 'content-type': 'application/json' }),
          json: async () => payloadWithInvalidDate,
        } as any);

        await act(async () => {
          root.render(React.createElement(ModelLineageView, { initialLineages: TEST_FIXTURE_LINEAGES }));
        });

        const projectInput = container.querySelector<HTMLInputElement>('[data-testid="commitment-project-input"]');
        const modelInput = container.querySelector<HTMLInputElement>('[data-testid="commitment-model-input"]');
        const versionInput = container.querySelector<HTMLInputElement>('[data-testid="commitment-version-input"]');
        const fetchBtn = container.querySelector<HTMLButtonElement>('[data-testid="commitment-fetch-btn"]');

        const setInputValue = (el: HTMLInputElement, val: string) => {
          const setter = Object.getOwnPropertyDescriptor(window.HTMLInputElement.prototype, 'value')?.set;
          setter?.call(el, val);
          el.dispatchEvent(new Event('input', { bubbles: true }));
          el.dispatchEvent(new Event('change', { bubbles: true }));
        };

        await act(async () => {
          setInputValue(projectInput!, testProjectId);
          setInputValue(modelInput!, testModelId);
          setInputValue(versionInput!, testVersion);
        });

        await act(async () => {
          fetchBtn!.click();
        });
        await act(async () => {
          await new Promise((resolve) => setTimeout(resolve, 0));
        });

        const errorBanner = container.querySelector('[data-testid="commitment-error-banner"]');
        expect(errorBanner).not.toBeNull();
        expect(errorBanner?.getAttribute('role')).toBe('alert');
        expect(errorBanner?.textContent).toContain('클라이언트 응답 계약 검증 실패');
        expect(errorBanner?.textContent).toContain('ModelCommitObservation 응답 계약 불일치');
        expect(errorBanner?.textContent).not.toContain('500');
        expect(errorBanner?.textContent).not.toContain('(500)');
        expect(errorBanner?.textContent).not.toContain('FETCH_ERROR');

        const resultContainer = container.querySelector('[data-testid="commitment-result-container"]');
        expect(resultContainer).toBeNull();
      } finally {
        globalThis.fetch = originalFetch;
      }
    });

    describe('Adapter Conformance Observation API Integration (G-03 Phase 1 & AC-10)', () => {
      const setInputValue = (el: HTMLInputElement, val: string) => {
        const setter = Object.getOwnPropertyDescriptor(window.HTMLInputElement.prototype, 'value')?.set;
        setter?.call(el, val);
        el.dispatchEvent(new Event('input', { bubbles: true }));
        el.dispatchEvent(new Event('change', { bubbles: true }));
      };

      const canonical15Checks = [
        { name: 'conformance_metadata_present', capabilityGated: false },
        { name: 'schema_validation_passed', capabilityGated: false },
        { name: 'streaming_chunk_boundary_valid', capabilityGated: true },
        { name: 'trace_context_propagated', capabilityGated: true },
        { name: 'cancellation_respected', capabilityGated: true },
        { name: 'timeout_fail_closed', capabilityGated: true },
        { name: 'token_usage_reported', capabilityGated: false },
        { name: 'error_envelope_rfc9457', capabilityGated: false },
        { name: 'auth_credential_isolated', capabilityGated: true },
        { name: 'rate_limit_handled', capabilityGated: false },
        { name: 'payload_size_enforced', capabilityGated: false },
        { name: 'content_type_strictly_checked', capabilityGated: false },
        { name: 'idempotency_key_supported', capabilityGated: true },
        { name: 'lifecycle_hook_executed', capabilityGated: false },
        { name: 'deterministic_fallback_verified', capabilityGated: true },
      ];

      const canonicalConformancePayload = {
        contractVersion: '1.0.0',
        scope: 'control-plane-host',
        status: 'NOT_OBSERVED',
        recordedAt: null,
        adapters: ['codex', 'claude'],
        checks: canonical15Checks,
        reason: 'phase 1 control-plane conformance observation baseline (stored result absent)',
      };

      it('renders unmeasured status NOT_OBSERVED without fake counts or pass indicators on valid canonical API response', async () => {
        const originalFetch = globalThis.fetch;
        const testProjectId = 'prj_0123456789ABCDEFGHJKMNPQRS';

        try {
          globalThis.fetch = vi.fn().mockResolvedValue({
            ok: true,
            status: 200,
            headers: new Headers({ 'content-type': 'application/json' }),
            json: async () => canonicalConformancePayload,
          } as any);

          await act(async () => {
            root.render(React.createElement(ModelLineageView, { initialLineages: TEST_FIXTURE_LINEAGES }));
          });

          const projectInput = container.querySelector<HTMLInputElement>('[data-testid="conformance-project-input"]');
          const fetchBtn = container.querySelector<HTMLButtonElement>('[data-testid="conformance-fetch-btn"]');
          expect(projectInput).not.toBeNull();
          expect(fetchBtn).not.toBeNull();

          await act(async () => {
            setInputValue(projectInput!, testProjectId);
          });

          await act(async () => {
            fetchBtn!.click();
          });
          await act(async () => {
            await new Promise((resolve) => setTimeout(resolve, 0));
          });

          expect(globalThis.fetch).toHaveBeenCalledWith(
            expect.stringContaining(`/v1/projects/${testProjectId}/adapters/conformance`),
            expect.anything()
          );

          // Invariant 1: Top metrics card updates honestly to unmeasured NOT_OBSERVED
          const topStatus = container.querySelector('[data-testid="conformance-top-status"]');
          expect(topStatus?.textContent).toBe('미측정 (NOT_OBSERVED)');

          // Invariant 2: Result container rendered
          const resultContainer = container.querySelector('[data-testid="conformance-result-container"]');
          expect(resultContainer).not.toBeNull();

          // Invariant 3: Status badge explicitly displays 미측정 (NOT_OBSERVED)
          const statusBadge = container.querySelector('[data-testid="conformance-status-badge"]');
          expect(statusBadge?.textContent).toContain('미측정 (NOT_OBSERVED)');

          // Invariant 4: Zero fake scores or fake pass counts
          expect(resultContainer?.textContent).not.toContain('100%');
          expect(resultContainer?.textContent).not.toContain('0 / 15');
          expect(resultContainer?.textContent).not.toContain('15 / 15');
          expect(resultContainer?.textContent).not.toContain('PASS');

          // Invariant 5: Metadata fields match canonical response
          expect(container.querySelector('[data-testid="conformance-scope"]')?.textContent).toBe('control-plane-host');
          expect(container.querySelector('[data-testid="conformance-contract-version"]')?.textContent).toBe('1.0.0');
          expect(container.querySelector('[data-testid="conformance-adapters"]')?.textContent).toBe('codex, claude');
          expect(container.querySelector('[data-testid="conformance-recorded-at"]')?.textContent).toBe('null (미측정)');
          expect(container.querySelector('[data-testid="conformance-reason"]')?.textContent).toBe(canonicalConformancePayload.reason);

          // Invariant 6: All 15 checks are rendered in table
          const checksTable = container.querySelector('[data-testid="conformance-checks-table"]');
          expect(checksTable).not.toBeNull();
          for (let i = 0; i < 15; i++) {
            const checkName = container.querySelector(`[data-testid="conformance-check-name-${i}"]`);
            const checkGated = container.querySelector(`[data-testid="conformance-check-gated-${i}"]`);
            const checkStatus = container.querySelector(`[data-testid="conformance-check-status-${i}"]`);
            expect(checkName?.textContent).toBe(canonical15Checks[i].name);
            expect(checkGated?.textContent).toBe(canonical15Checks[i].capabilityGated ? 'Capability Gated' : 'Standard');
            expect(checkStatus?.textContent).toContain('NOT_OBSERVED (미측정)');
          }

          // Invariant 7: Live status announcements
          const liveStatus = container.querySelector('[data-testid="conformance-live-status"]');
          expect(liveStatus?.textContent).toContain('NOT_OBSERVED');
          expect(liveStatus?.textContent).toContain('15개 정본 체크 항목');
        } finally {
          globalThis.fetch = originalFetch;
        }
      });

      it('dynamically reads and renders check names directly from server response without FE hardcoding', async () => {
        const originalFetch = globalThis.fetch;
        const testProjectId = 'prj_0123456789ABCDEFGHJKMNPQRS';
        const dynamicCustomChecks = [
          { name: 'runtime_kernel_boundary_test', capabilityGated: true },
          { name: 'custom_trace_probe_check', capabilityGated: false },
          { name: 'fail_closed_gate_verification', capabilityGated: true },
        ];

        const customPayload = {
          contractVersion: '1.0.0',
          scope: 'control-plane-host',
          status: 'NOT_OBSERVED',
          recordedAt: null,
          adapters: ['codex'],
          checks: dynamicCustomChecks,
          reason: 'custom test checklist',
        };

        try {
          globalThis.fetch = vi.fn().mockResolvedValue({
            ok: true,
            status: 200,
            headers: new Headers({ 'content-type': 'application/json' }),
            json: async () => customPayload,
          } as any);

          await act(async () => {
            root.render(React.createElement(ModelLineageView, { initialLineages: TEST_FIXTURE_LINEAGES }));
          });

          const projectInput = container.querySelector<HTMLInputElement>('[data-testid="conformance-project-input"]');
          const fetchBtn = container.querySelector<HTMLButtonElement>('[data-testid="conformance-fetch-btn"]');

          await act(async () => {
            setInputValue(projectInput!, testProjectId);
          });
          await act(async () => {
            fetchBtn!.click();
          });
          await act(async () => {
            await new Promise((resolve) => setTimeout(resolve, 0));
          });

          // Invariant: Exactly 3 rows rendered, with dynamic names from payload
          for (let i = 0; i < dynamicCustomChecks.length; i++) {
            const checkName = container.querySelector(`[data-testid="conformance-check-name-${i}"]`);
            const checkGated = container.querySelector(`[data-testid="conformance-check-gated-${i}"]`);
            expect(checkName?.textContent).toBe(dynamicCustomChecks[i].name);
            expect(checkGated?.textContent).toBe(dynamicCustomChecks[i].capabilityGated ? 'Capability Gated' : 'Standard');
          }
          // Row 4 MUST NOT exist
          expect(container.querySelector('[data-testid="conformance-check-row-3"]')).toBeNull();
        } finally {
          globalThis.fetch = originalFetch;
        }
      });

      it('handles canonical 401, 403, and 404 ProblemDetails errors displaying RFC 9457 envelope without crashing', async () => {
        const originalFetch = globalThis.fetch;
        const testProjectId = 'prj_0123456789ABCDEFGHJKMNPQRS';

        try {
          await act(async () => {
            root.render(React.createElement(ModelLineageView, { initialLineages: TEST_FIXTURE_LINEAGES }));
          });

          const projectInput = container.querySelector<HTMLInputElement>('[data-testid="conformance-project-input"]');
          const fetchBtn = container.querySelector<HTMLButtonElement>('[data-testid="conformance-fetch-btn"]');

          await act(async () => {
            setInputValue(projectInput!, testProjectId);
          });

          // Case A: 401 Unauthorized
          const problem401: ProblemDetails = {
            type: 'about:blank',
            title: 'Unauthorized',
            status: 401,
            code: 'AUTH-0030',
            category: 'AUTH',
            detail: '인증 정보가 유효하지 않습니다.',
            retryable: false,
            traceId: '0123456789abcdef0123456789abcdef',
            causeRef: null,
            evidenceId: null,
          };

          globalThis.fetch = vi.fn().mockResolvedValue({
            ok: false,
            status: 401,
            statusText: 'Unauthorized',
            headers: new Headers({ 'content-type': 'application/problem+json' }),
            json: async () => problem401,
          } as any);

          await act(async () => {
            fetchBtn!.click();
          });
          await act(async () => {
            await new Promise((resolve) => setTimeout(resolve, 0));
          });

          let errorBanner = container.querySelector('[data-testid="conformance-error-banner"]');
          expect(errorBanner).not.toBeNull();
          expect(errorBanner?.getAttribute('role')).toBe('alert');
          expect(errorBanner?.textContent).toContain('AUTH-0030');
          expect(errorBanner?.textContent).toContain('401');
          expect(errorBanner?.textContent).toContain('인증 정보가 유효하지 않습니다.');
          expect(container.querySelector('[data-testid="conformance-result-container"]')).toBeNull();

          // Case B: 403 Forbidden
          const problem403: ProblemDetails = {
            type: 'about:blank',
            title: 'Forbidden',
            status: 403,
            code: 'AUTH-0001',
            category: 'AUTH',
            detail: '프로젝트 접근 권한이 없습니다.',
            retryable: false,
            traceId: '0123456789abcdef0123456789abcdef',
            causeRef: null,
            evidenceId: null,
          };

          globalThis.fetch = vi.fn().mockResolvedValue({
            ok: false,
            status: 403,
            statusText: 'Forbidden',
            headers: new Headers({ 'content-type': 'application/problem+json' }),
            json: async () => problem403,
          } as any);

          await act(async () => {
            fetchBtn!.click();
          });
          await act(async () => {
            await new Promise((resolve) => setTimeout(resolve, 0));
          });

          errorBanner = container.querySelector('[data-testid="conformance-error-banner"]');
          expect(errorBanner).not.toBeNull();
          expect(errorBanner?.textContent).toContain('AUTH-0001');
          expect(errorBanner?.textContent).toContain('403');
          expect(errorBanner?.textContent).toContain('프로젝트 접근 권한이 없습니다.');

          // Case C: 404 Project Not Found
          const problem404: ProblemDetails = {
            type: 'about:blank',
            title: 'Not Found',
            status: 404,
            code: 'RES-0004',
            category: 'RES',
            detail: '프로젝트를 찾을 수 없습니다.',
            retryable: false,
            traceId: '0123456789abcdef0123456789abcdef',
            causeRef: null,
            evidenceId: null,
          };

          globalThis.fetch = vi.fn().mockResolvedValue({
            ok: false,
            status: 404,
            statusText: 'Not Found',
            headers: new Headers({ 'content-type': 'application/problem+json' }),
            json: async () => problem404,
          } as any);

          await act(async () => {
            fetchBtn!.click();
          });
          await act(async () => {
            await new Promise((resolve) => setTimeout(resolve, 0));
          });

          errorBanner = container.querySelector('[data-testid="conformance-error-banner"]');
          expect(errorBanner).not.toBeNull();
          expect(errorBanner?.textContent).toContain('RES-0004');
          expect(errorBanner?.textContent).toContain('404');
          expect(errorBanner?.textContent).toContain('프로젝트를 찾을 수 없습니다.');
        } finally {
          globalThis.fetch = originalFetch;
        }
      });

      it('guarantees permanent live region container in DOM for screen reader a11y (#203 F1 invariant)', async () => {
        const originalFetch = globalThis.fetch;
        const testProjectId = 'prj_0123456789ABCDEFGHJKMNPQRS';

        try {
          await act(async () => {
            root.render(React.createElement(ModelLineageView, { initialLineages: TEST_FIXTURE_LINEAGES }));
          });

          // Invariant 1: Live region container exists in DOM BEFORE any action
          const initialLiveRegion = container.querySelector('[data-testid="conformance-live-status"]');
          expect(initialLiveRegion).not.toBeNull();
          expect(initialLiveRegion?.getAttribute('role')).toBe('status');
          expect(initialLiveRegion?.getAttribute('aria-live')).toBe('polite');

          const projectInput = container.querySelector<HTMLInputElement>('[data-testid="conformance-project-input"]');
          const fetchBtn = container.querySelector<HTMLButtonElement>('[data-testid="conformance-fetch-btn"]');

          await act(async () => {
            setInputValue(projectInput!, testProjectId);
          });

          let resolveFetch: (val: any) => void;
          const slowPromise = new Promise((resolve) => {
            resolveFetch = resolve;
          });

          globalThis.fetch = vi.fn().mockReturnValue(slowPromise);

          // Trigger fetch to observe loading state
          await act(async () => {
            fetchBtn!.click();
          });

          const loadingLiveRegion = container.querySelector('[data-testid="conformance-live-status"]');
          // Invariant 2: Element node identity is preserved (never unmounted and remounted)
          expect(loadingLiveRegion).toBe(initialLiveRegion);
          expect(loadingLiveRegion?.textContent).toContain('조회 중...');

          // Resolve fetch
          await act(async () => {
            resolveFetch!({
              ok: true,
              status: 200,
              headers: new Headers({ 'content-type': 'application/json' }),
              json: async () => canonicalConformancePayload,
            });
          });
          await act(async () => {
            await new Promise((resolve) => setTimeout(resolve, 0));
          });

          const completedLiveRegion = container.querySelector('[data-testid="conformance-live-status"]');
          // Invariant 3: Element node identity remains identical
          expect(completedLiveRegion).toBe(initialLiveRegion);
          expect(completedLiveRegion?.textContent).toContain('관측 완료');
        } finally {
          globalThis.fetch = originalFetch;
        }
      });

      it('rejects invalid response payloads violating schema guard (e.g. status !== NOT_OBSERVED, recordedAt !== null, extra properties)', async () => {
        const originalFetch = globalThis.fetch;
        const testProjectId = 'prj_0123456789ABCDEFGHJKMNPQRS';

        try {
          await act(async () => {
            root.render(React.createElement(ModelLineageView, { initialLineages: TEST_FIXTURE_LINEAGES }));
          });

          const projectInput = container.querySelector<HTMLInputElement>('[data-testid="conformance-project-input"]');
          const fetchBtn = container.querySelector<HTMLButtonElement>('[data-testid="conformance-fetch-btn"]');

          await act(async () => {
            setInputValue(projectInput!, testProjectId);
          });

          // Test A: status is PASS instead of NOT_OBSERVED (phase 1 invariant)
          const invalidStatusPayload = {
            ...canonicalConformancePayload,
            status: 'PASS',
          };

          globalThis.fetch = vi.fn().mockResolvedValue({
            ok: true,
            status: 200,
            headers: new Headers({ 'content-type': 'application/json' }),
            json: async () => invalidStatusPayload,
          } as any);

          await act(async () => {
            fetchBtn!.click();
          });
          await act(async () => {
            await new Promise((resolve) => setTimeout(resolve, 0));
          });

          let errorBanner = container.querySelector('[data-testid="conformance-error-banner"]');
          expect(errorBanner).not.toBeNull();
          expect(errorBanner?.textContent).toContain('클라이언트 응답 계약 검증 실패');
          expect(errorBanner?.textContent).toContain('ConformanceStatusResponse 응답 계약 불일치');
          expect(container.querySelector('[data-testid="conformance-result-container"]')).toBeNull();

          // Test B: extra property violating additionalProperties: false
          const extraPropPayload = {
            ...canonicalConformancePayload,
            unauthorizedExtraField: 'dangerous_extension',
          };

          globalThis.fetch = vi.fn().mockResolvedValue({
            ok: true,
            status: 200,
            headers: new Headers({ 'content-type': 'application/json' }),
            json: async () => extraPropPayload,
          } as any);

          await act(async () => {
            fetchBtn!.click();
          });
          await act(async () => {
            await new Promise((resolve) => setTimeout(resolve, 0));
          });

          errorBanner = container.querySelector('[data-testid="conformance-error-banner"]');
          expect(errorBanner).not.toBeNull();
          expect(errorBanner?.textContent).toContain('클라이언트 응답 계약 검증 실패');
          expect(container.querySelector('[data-testid="conformance-result-container"]')).toBeNull();

          // Test C: recordedAt is not null (phase 1 constraint)
          const nonNullRecordedAtPayload = {
            ...canonicalConformancePayload,
            recordedAt: '2026-09-28T09:00:00Z',
          };

          globalThis.fetch = vi.fn().mockResolvedValue({
            ok: true,
            status: 200,
            headers: new Headers({ 'content-type': 'application/json' }),
            json: async () => nonNullRecordedAtPayload,
          } as any);

          await act(async () => {
            fetchBtn!.click();
          });
          await act(async () => {
            await new Promise((resolve) => setTimeout(resolve, 0));
          });

          errorBanner = container.querySelector('[data-testid="conformance-error-banner"]');
          expect(errorBanner).not.toBeNull();
          expect(errorBanner?.textContent).toContain('클라이언트 응답 계약 검증 실패');
          expect(container.querySelector('[data-testid="conformance-result-container"]')).toBeNull();
        } finally {
          globalThis.fetch = originalFetch;
        }
      });

      it('satisfies WCAG AA text contrast ratio (>= 4.5:1) in dark theme for all status elements and badges', () => {
        const getRelativeLuminance = (r: number, g: number, b: number) => {
          const ch = (v: number) => {
            const normalized = v / 255;
            return normalized <= 0.03928 ? normalized / 12.92 : Math.pow((normalized + 0.055) / 1.055, 2.4);
          };
          return 0.2126 * ch(r) + 0.7152 * ch(g) + 0.0722 * ch(b);
        };

        const getContrastRatio = (lum1: number, lum2: number) => {
          const lighter = Math.max(lum1, lum2);
          const darker = Math.min(lum1, lum2);
          return (lighter + 0.05) / (darker + 0.05);
        };

        const hexToRgb = (hex: string): [number, number, number] => {
          const clean = hex.replace('#', '');
          return [
            parseInt(clean.substring(0, 2), 16),
            parseInt(clean.substring(2, 4), 16),
            parseInt(clean.substring(4, 6), 16),
          ];
        };

        const blendRgb = (fg: [number, number, number], alpha: number, bg: [number, number, number]): [number, number, number] => {
          return [
            Math.round(fg[0] * alpha + bg[0] * (1 - alpha)),
            Math.round(fg[1] * alpha + bg[1] * (1 - alpha)),
            Math.round(fg[2] * alpha + bg[2] * (1 - alpha)),
          ];
        };

        const bgDark = hexToRgb('#161b22');
        const bgLum = getRelativeLuminance(...bgDark);

        // 1. Orange status badge text (#f0883e)
        const orangeRgb = hexToRgb('#f0883e');
        const orangeLum = getRelativeLuminance(...orangeRgb);
        const orangeContrast = getContrastRatio(orangeLum, bgLum);
        expect(orangeContrast).toBeGreaterThanOrEqual(4.5);

        // 2. Red error banner text (#ff7b72)
        const redRgb = hexToRgb('#ff7b72');
        const redLum = getRelativeLuminance(...redRgb);
        const redContrast = getContrastRatio(redLum, bgLum);
        expect(redContrast).toBeGreaterThanOrEqual(4.5);

        // 3. Blue loading text (#58a6ff)
        const blueRgb = hexToRgb('#58a6ff');
        const blueLum = getRelativeLuminance(...blueRgb);
        const blueContrast = getContrastRatio(blueLum, bgLum);
        expect(blueContrast).toBeGreaterThanOrEqual(4.5);

        // 4. Muted text (#8b949e)
        const mutedRgb = hexToRgb('#8b949e');
        const mutedLum = getRelativeLuminance(...mutedRgb);
        const mutedContrast = getContrastRatio(mutedLum, bgLum);
        expect(mutedContrast).toBeGreaterThanOrEqual(4.5);

        // 5. Alpha-blended badge backgrounds (15% orange on #161b22)
        const blendedOrange = blendRgb(orangeRgb, 0.15, bgDark);
        const blendedOrangeLum = getRelativeLuminance(...blendedOrange);
        const orangeOnBlended = getContrastRatio(orangeLum, blendedOrangeLum);
        expect(orangeOnBlended).toBeGreaterThanOrEqual(4.5);

        // 6. Alpha-blended error backgrounds (15% red on #161b22)
        const blendedRed = blendRgb(redRgb, 0.15, bgDark);
        const blendedRedLum = getRelativeLuminance(...blendedRed);
        const redOnBlended = getContrastRatio(redLum, blendedRedLum);
        expect(redOnBlended).toBeGreaterThanOrEqual(4.5);
      });
    });
  });
});
