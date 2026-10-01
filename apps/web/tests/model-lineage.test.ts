// @vitest-environment happy-dom
import fs from 'fs';
import path from 'path';
import React, { act } from 'react';
import { createRoot, Root } from 'react-dom/client';
import { describe, it, expect, beforeAll, afterAll, beforeEach, afterEach, vi } from 'vitest';
import { MlopsManager } from '../src/features/mlops/mlopsEngine';
import { TEST_FIXTURE_LINEAGES } from './fixtures/model-lineage';
import { ModelLineageView } from '../src/features/mlops/ModelLineageView';
import type { ProblemDetails } from '../src/contracts/types';
import type { ConformanceStatusResponse, ConformanceCheckDescriptor } from '../src/contracts/conformance-status-response';
import type { ConformanceStatusRecordedResponse, ConformanceRecordItem } from '../src/contracts/conformance-status-recorded-response';
import type { AdapterConformanceNotObservedResponse } from '../src/contracts/adapter-conformance-not-observed-response';
import type { AdapterConformanceRecordedResponse } from '../src/contracts/adapter-conformance-recorded-response';
import {
  isConformanceStatusResponse,
  isConformanceCheckDescriptor,
  isConformanceStatusRecordedResponse,
  isConformanceRecordItem,
  isConformanceCheckOutcome,
  isConformanceStatusUnion,
  isAdapterConformanceNotObservedResponse,
  isAdapterConformanceRecordedResponse,
  isAdapterConformanceUnion,
  fetchAdapterConformance,
} from '../src/shared/api/adapterObservation';

describe('S10-FE: Model Lineage, Multi-Provider Conformance & Gated Deployment (AC-10)', () => {
  const originalFetch = globalThis.fetch;
  beforeAll(() => {
    globalThis.fetch = vi.fn().mockImplementation(() =>
      Promise.resolve(new Response(JSON.stringify({}), { status: 200, headers: { 'Content-Type': 'application/json' } }))
    );
  });
  afterAll(() => {
    globalThis.fetch = originalFetch;
  });
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

    it('verifies Adapter Conformance displays unmeasured "미측정 (미조회)" and NEVER "100% CONFORMING" or fake PASS counts', async () => {
      await act(async () => {
        root.render(React.createElement(ModelLineageView, { initialLineages: TEST_FIXTURE_LINEAGES }));
      });

      // Strict Invariant 1: "100% CONFORMING" is strictly forbidden (must be unmeasured)
      expect(container.textContent).not.toContain('100% CONFORMING');
      expect(container.textContent).not.toContain('100%');
      expect(container.textContent).not.toMatch(/pass/i);

      // Strict Invariant 2: Explicit unmeasured status is rendered in top metrics and panel
      const topStatus = container.querySelector('[data-testid="conformance-top-status"]');
      expect(topStatus?.textContent).toBe('미측정 (미조회)');
      expect(container.textContent).toContain('미측정 (미조회)');

      // Strict Invariant 3: Unmeasured notice guides user to real control-plane API
      const unmeasuredNotice = container.querySelector('[data-testid="conformance-unmeasured-notice"]');
      expect(unmeasuredNotice).not.toBeNull();
      expect(unmeasuredNotice?.textContent).toContain('미측정 (미조회)');
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

      // F2: Real 15 CHECKLIST items and capability gating from adapters/conformance.py:358-389
      const canonical15Checks: ConformanceCheckDescriptor[] = [
        { name: 'declares_contract_version', capabilityGated: false },
        { name: 'implements_every_member', capabilityGated: false },
        { name: 'probe_without_credentials', capabilityGated: false },
        { name: 'install_reports_without_installing', capabilityGated: false },
        { name: 'authenticate_takes_a_reference', capabilityGated: false },
        { name: 'run_returns_a_usable_handle', capabilityGated: false },
        { name: 'collect_returns_redacted_content', capabilityGated: false },
        { name: 'redact_removes_known_secrets', capabilityGated: false },
        { name: 'redact_is_idempotent', capabilityGated: false },
        { name: 'cancel_returns_a_tri_state', capabilityGated: false },
        { name: 'cancel_after_completion_is_not_stopped', capabilityGated: false },
        { name: 'attest_does_not_overclaim', capabilityGated: false },
        { name: 'declared_server_cancel_actually_stops', capabilityGated: true },
        { name: 'declared_usage_is_reported', capabilityGated: true },
        { name: 'declared_model_pinning_returns_an_id', capabilityGated: true },
      ];

      // F2: Real adapters from agents.py:99 and reason from conformance_status.py
      // NOT_OBSERVED_REASON (G-03 stage two, #221: the platform now persists records, so
      // the sentence states the absence only -- design #218 v1.2 §4-4 / T5b).
      const NOT_OBSERVED_REASON = 'No conformance run is recorded for this host and these adapters.';
      const canonicalConformancePayload: ConformanceStatusResponse = {
        contractVersion: '1.0.0',
        scope: 'control-plane-host',
        status: 'NOT_OBSERVED',
        recordedAt: null,
        adapters: ['claude-code', 'codex-cli', 'gemini-cli', 'antigravity'],
        checks: canonical15Checks,
        reason: NOT_OBSERVED_REASON,
      };

      // G-03 stage two: one record, the fixture adapter's real result shape (15 checks,
      // the one ungated-but-undeclared capability check skipped).
      const canonicalRecord: ConformanceRecordItem = {
        adapter: 'codex-cli',
        subject: 'fixture-adapter',
        provenance: 'in-server',
        contractVersion: '1.0.0',
        suiteContractVersion: '1.0.0',
        total: 15,
        passed: 14,
        failed: 0,
        skipped: 1,
        outcomes: canonical15Checks.map((check) => ({
          name: check.name,
          passed: check.name !== 'declared_server_cancel_actually_stops',
          skipped: check.name === 'declared_server_cancel_actually_stops',
        })),
        recordedAt: '2026-09-28T06:00:00Z',
      };
      const canonicalRecordedPayload: ConformanceStatusRecordedResponse = {
        status: 'RECORDED',
        scope: 'control-plane-host',
        contractVersion: '1.0.0',
        adapters: ['claude-code', 'codex-cli', 'gemini-cli', 'antigravity'],
        checks: canonical15Checks,
        records: [canonicalRecord],
        latestRecordedAt: '2026-09-28T06:00:00Z',
      };

      it('pins the stage-two NOT_OBSERVED reason and no longer carries the stage-one sentence (design #218 T5b)', () => {
        expect(canonicalConformancePayload.reason).toBe('No conformance run is recorded for this host and these adapters.');
        expect(canonicalConformancePayload.reason).not.toContain('does not persist');
        expect(isConformanceStatusResponse(canonicalConformancePayload)).toBe(true);
      });

      it('accepts the RECORDED branch and rejects every invariant break (design #218 §2-8, §4-1)', () => {
        expect(isConformanceStatusRecordedResponse(canonicalRecordedPayload)).toBe(true);
        expect(isConformanceStatusUnion(canonicalRecordedPayload)).toBe(true);
        expect(isConformanceStatusUnion(canonicalConformancePayload)).toBe(true);
        expect(isConformanceRecordItem(canonicalRecord)).toBe(true);
        expect(isConformanceCheckOutcome(canonicalRecord.outcomes[0])).toBe(true);

        // T1: no detail on an outcome; T2: counts must be one measurement.
        expect(isConformanceCheckOutcome({ ...canonicalRecord.outcomes[0], detail: 'x' })).toBe(false);
        expect(isConformanceCheckOutcome({ name: 'a', passed: true, skipped: true })).toBe(false);
        expect(isConformanceRecordItem({ ...canonicalRecord, passed: 13 })).toBe(false);
        expect(isConformanceRecordItem({ ...canonicalRecord, total: 16 })).toBe(false);
        expect(isConformanceRecordItem({ ...canonicalRecord, outcomes: canonicalRecord.outcomes.slice(1) })).toBe(false);
        // T3: only the producible subject/provenance.
        expect(isConformanceRecordItem({ ...canonicalRecord, subject: 'installed-cli' })).toBe(false);
        expect(isConformanceRecordItem({ ...canonicalRecord, provenance: 'hosted-ci-import' })).toBe(false);
        // T4: the aggregate has latestRecordedAt (the maximum) and no recordedAt/reason.
        expect(isConformanceStatusRecordedResponse({ ...canonicalRecordedPayload, latestRecordedAt: '2026-09-28T05:00:00Z' })).toBe(false);
        expect(isConformanceStatusRecordedResponse({ ...canonicalRecordedPayload, recordedAt: null })).toBe(false);
        expect(isConformanceStatusRecordedResponse({ ...canonicalRecordedPayload, reason: 'x' })).toBe(false);
        expect(isConformanceStatusRecordedResponse({ ...canonicalRecordedPayload, records: [] })).toBe(false);
        expect(isConformanceStatusRecordedResponse({ ...canonicalRecordedPayload, records: [canonicalRecord, canonicalRecord] })).toBe(false);
        expect(isConformanceStatusRecordedResponse({ ...canonicalRecordedPayload, records: [{ ...canonicalRecord, adapter: 'not-a-tool' }] })).toBe(false);
        expect(isConformanceStatusRecordedResponse({ ...canonicalRecordedPayload, conformant: true })).toBe(false);
        // A NOT_OBSERVED payload is not a RECORDED one and vice versa.
        expect(isConformanceStatusRecordedResponse(canonicalConformancePayload)).toBe(false);
        expect(isConformanceStatusResponse(canonicalRecordedPayload)).toBe(false);
        expect(isConformanceStatusUnion({ ...canonicalRecordedPayload, status: 'PASS' })).toBe(false);
      });

      it('renders a RECORDED response as per-adapter records of the fixture subject without a conformant verdict', async () => {
        const originalFetch = globalThis.fetch;
        const testProjectId = 'prj_0123456789ABCDEFGHJKMNPQRS';

        try {
          globalThis.fetch = vi.fn().mockResolvedValue({
            ok: true,
            status: 200,
            headers: new Headers({ 'content-type': 'application/json' }),
            json: async () => canonicalRecordedPayload,
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

          expect(container.querySelector('[data-testid="conformance-top-status"]')?.textContent).toBe('기록됨 (RECORDED)');
          expect(container.querySelector('[data-testid="conformance-top-subtext"]')?.textContent).toBe(
            '1/4 어댑터 기록 · fixture-adapter 측정 (control-plane-host)'
          );
          expect(container.querySelector('[data-testid="conformance-status-badge"]')?.textContent).toBe('기록됨 (RECORDED)');
          expect(container.querySelector('[data-testid="conformance-recorded-at"]')?.textContent).toBe('2026-09-28T06:00:00Z');
          // No reason on the RECORDED branch; the subject note says what was measured.
          expect(container.querySelector('[data-testid="conformance-reason"]')).toBeNull();
          expect(container.querySelector('[data-testid="conformance-subject-note"]')?.textContent).toContain('fixture-adapter');
          expect(container.querySelector('[data-testid="conformance-subject-note"]')?.textContent).toContain('설치된 CLI');

          const recordsTable = container.querySelector('[data-testid="conformance-records-table"]');
          expect(recordsTable).not.toBeNull();
          expect(container.querySelector('[data-testid="conformance-record-adapter-0"]')?.textContent).toBe('codex-cli');
          expect(container.querySelector('[data-testid="conformance-record-subject-0"]')?.textContent).toBe('fixture-adapter');
          expect(container.querySelector('[data-testid="conformance-record-provenance-0"]')?.textContent).toBe('in-server');
          expect(container.querySelector('[data-testid="conformance-record-counts-0"]')?.textContent).toBe('전체 15 · 통과 14 · 실패 0 · 건너뜀 1');
          expect(container.querySelector('[data-testid="conformance-record-row-1"]')).toBeNull();

          // The checklist is still the server's descriptor list, tallied from outcomes only.
          expect(container.querySelector('[data-testid="conformance-check-status-0"]')?.textContent).toBe('통과 1 · 실패 0 · 건너뜀 0 (1개 기록)');
          expect(container.querySelector('[data-testid="conformance-check-status-12"]')?.textContent).toBe('통과 0 · 실패 0 · 건너뜀 1 (1개 기록)');

          // No verdict: a record of the fixture is not "conforming", and there is no percentage.
          const resultContainer = container.querySelector('[data-testid="conformance-result-container"]');
          expect(resultContainer?.textContent).not.toContain('100%');
          expect(resultContainer?.textContent).not.toMatch(/conforming/i);
          expect(resultContainer?.textContent).not.toMatch(/\bPASS\b/);
          expect(container.querySelector('[data-testid="conformance-live-status"]')?.textContent).toContain('기록됨(RECORDED)');
        } finally {
          globalThis.fetch = originalFetch;
        }
      });

      it('statically and dynamically verifies types are bound to generated @/contracts/conformance-status-response (Codex F-R1)', () => {
        expect(isConformanceStatusResponse(canonicalConformancePayload)).toBe(true);
        expect(isConformanceCheckDescriptor(canonical15Checks[0])).toBe(true);

        // Kills mutation M6: check descriptor with extra property (e.g. passed: true) must be rejected
        expect(isConformanceCheckDescriptor({ name: 'check_a', capabilityGated: false, passed: true })).toBe(false);
        expect(isConformanceCheckDescriptor({ name: '', capabilityGated: false })).toBe(false);
        expect(isConformanceCheckDescriptor({ name: 'check_a' })).toBe(false);
      });

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

          // Invariant 1: Top metrics card updates honestly to unmeasured NOT_OBSERVED (F6)
          const topStatus = container.querySelector('[data-testid="conformance-top-status"]');
          expect(topStatus?.textContent).toBe('미측정 (NOT_OBSERVED)');
          const topSubtext = container.querySelector('[data-testid="conformance-top-subtext"]');
          expect(topSubtext?.textContent).toBe('15개 정본 체크 항목 미측정 (control-plane-host)');

          // Invariant 2: Result container rendered
          const resultContainer = container.querySelector('[data-testid="conformance-result-container"]');
          expect(resultContainer).not.toBeNull();

          // Invariant 3: Status badge explicitly displays 미측정 (NOT_OBSERVED)
          const statusBadge = container.querySelector('[data-testid="conformance-status-badge"]');
          expect(statusBadge?.textContent).toContain('미측정 (NOT_OBSERVED)');

          // Invariant 4: Zero fake scores or fake pass counts (case-insensitive regex, F2)
          expect(resultContainer?.textContent).not.toMatch(/pass/i);
          expect(resultContainer?.textContent).not.toContain('100%');
          expect(resultContainer?.textContent).not.toContain('0 / 15');
          expect(resultContainer?.textContent).not.toContain('15 / 15');

          // Invariant 5: Metadata fields match canonical response
          expect(container.querySelector('[data-testid="conformance-scope"]')?.textContent).toBe('control-plane-host');
          expect(container.querySelector('[data-testid="conformance-contract-version"]')?.textContent).toBe('1.0.0');
          expect(container.querySelector('[data-testid="conformance-adapters"]')?.textContent).toBe('claude-code, codex-cli, gemini-cli, antigravity');
          expect(container.querySelector('[data-testid="conformance-recorded-at"]')?.textContent).toBe('null (미측정)');
          expect(container.querySelector('[data-testid="conformance-reason"]')?.textContent).toBe(canonicalConformancePayload.reason);

          // Invariant 6: All 15 checks are rendered in table with exact CHECKLIST names and gating
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

          // Invariant 7: Live status announcements (F6)
          const liveStatus = container.querySelector('[data-testid="conformance-live-status"]');
          expect(liveStatus?.textContent).toContain('조회 완료: 미측정(NOT_OBSERVED)');
          expect(liveStatus?.textContent).toContain('15개 정본 체크 항목');
        } finally {
          globalThis.fetch = originalFetch;
        }
      });

      it('dynamically reads and renders check names directly from server response without FE hardcoding (F4)', async () => {
        const originalFetch = globalThis.fetch;
        const testProjectId = 'prj_0123456789ABCDEFGHJKMNPQRS';
        const dynamicCustomChecks = [
          { name: 'runtime_kernel_boundary_test', capabilityGated: true },
          { name: 'custom_trace_probe_check', capabilityGated: false },
          { name: 'fail_closed_gate_verification', capabilityGated: true },
        ];

        const customPayload: ConformanceStatusResponse = {
          contractVersion: '1.0.0',
          scope: 'control-plane-host',
          status: 'NOT_OBSERVED',
          recordedAt: null,
          adapters: ['codex-cli'],
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

          // F4 Invariant: Panel textContent MUST NOT contain '15개' when dynamic checks are rendered
          const panel = container.querySelector('[data-testid="adapter-conformance-panel"]');
          expect(panel?.textContent).not.toContain('15개');
        } finally {
          globalThis.fetch = originalFetch;
        }
      });

      it('handles canonical 403 Forbidden, 401 Unauthorized legacy shape, and 404 Route Not Deployed without crashing (F2)', async () => {
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

          // Case A: Real 403 Forbidden (#200 problem.py AUTH-0030)
          const canonical403Problem: ProblemDetails = {
            type: 'about:blank',
            title: 'AUTH-0030',
            status: 403,
            code: 'AUTH-0030',
            category: 'AUTH',
            detail: 'This project is not accessible.',
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
            json: async () => canonical403Problem,
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
          expect(errorBanner?.textContent).toContain('403');
          expect(errorBanner?.textContent).toContain('This project is not accessible.');
          expect(container.querySelector('[data-testid="conformance-top-status"]')?.textContent).toBe('조회 실패');
          expect(container.querySelector('[data-testid="conformance-top-subtext"]')?.textContent).toBe('어댑터 conformance 조회 실패');
          expect(container.querySelector('[data-testid="conformance-result-container"]')).toBeNull();

          // Case B: Real 401 Unauthorized legacy shape (#200 deps.py AUTH_MISSING_CREDENTIAL)
          const real401LegacyPayload = {
            type: 'https://saintvision.invenio/problems/auth-missing-credential',
            title: 'a bearer credential is required',
            status: 401,
            code: 'AUTH-MISSING-CREDENTIAL',
            detail: 'a bearer credential is required',
            instance: `/v1/projects/${testProjectId}/adapters/conformance`,
          };

          globalThis.fetch = vi.fn().mockResolvedValue({
            ok: false,
            status: 401,
            statusText: 'Unauthorized',
            headers: new Headers({ 'content-type': 'application/problem+json' }),
            json: async () => real401LegacyPayload,
          } as any);

          await act(async () => {
            fetchBtn!.click();
          });
          await act(async () => {
            await new Promise((resolve) => setTimeout(resolve, 0));
          });

          errorBanner = container.querySelector('[data-testid="conformance-error-banner"]');
          expect(errorBanner).not.toBeNull();
          // client.ts rejects legacy problem -> localProblem classifies as NET-0401 Request rejected
          expect(errorBanner?.textContent).toContain('NET-0401');
          expect(errorBanner?.textContent).toContain('401');
          expect(errorBanner?.textContent).toContain('Request rejected');
          expect(errorBanner?.textContent).toContain('a bearer credential is required');
          expect(container.querySelector('[data-testid="conformance-result-container"]')).toBeNull();

          // Case C: 404 Route Not Deployed (Starlette standard 404 {"detail": "Not Found"})
          globalThis.fetch = vi.fn().mockResolvedValue({
            ok: false,
            status: 404,
            statusText: 'Not Found',
            headers: new Headers({ 'content-type': 'application/json' }),
            json: async () => ({ detail: 'Not Found' }),
          } as any);

          await act(async () => {
            fetchBtn!.click();
          });
          await act(async () => {
            await new Promise((resolve) => setTimeout(resolve, 0));
          });

          errorBanner = container.querySelector('[data-testid="conformance-error-banner"]');
          expect(errorBanner).not.toBeNull();
          expect(errorBanner?.textContent).toContain('NET-0404');
          expect(errorBanner?.textContent).toContain('404');
          expect(errorBanner?.textContent).toContain('Not Found');
        } finally {
          globalThis.fetch = originalFetch;
        }
      });

      it('isolates state across fetch transitions (killing M8 setConformanceData null mutation) (F3)', async () => {
        const originalFetch = globalThis.fetch;
        const testProjectIdA = 'prj_0123456789ABCDEFGHJKMNPQRA';
        const testProjectIdB = 'prj_0123456789ABCDEFGHJKMNPQRB';

        try {
          await act(async () => {
            root.render(React.createElement(ModelLineageView, { initialLineages: TEST_FIXTURE_LINEAGES }));
          });

          const projectInput = container.querySelector<HTMLInputElement>('[data-testid="conformance-project-input"]');
          const fetchBtn = container.querySelector<HTMLButtonElement>('[data-testid="conformance-fetch-btn"]');

          // Step 1: Project A succeeds
          globalThis.fetch = vi.fn().mockResolvedValue({
            ok: true,
            status: 200,
            headers: new Headers({ 'content-type': 'application/json' }),
            json: async () => canonicalConformancePayload,
          } as any);

          await act(async () => {
            setInputValue(projectInput!, testProjectIdA);
          });
          await act(async () => {
            fetchBtn!.click();
          });
          await act(async () => {
            await new Promise((resolve) => setTimeout(resolve, 0));
          });

          expect(container.querySelector('[data-testid="conformance-result-container"]')).not.toBeNull();
          expect(container.querySelector('[data-testid="conformance-error-banner"]')).toBeNull();

          // Step 2: Project B is refused with 403 AUTH-0030
          const problem403: ProblemDetails = {
            type: 'about:blank',
            title: 'AUTH-0030',
            status: 403,
            code: 'AUTH-0030',
            category: 'AUTH',
            detail: 'This project is not accessible.',
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
            setInputValue(projectInput!, testProjectIdB);
          });
          await act(async () => {
            fetchBtn!.click();
          });
          await act(async () => {
            await new Promise((resolve) => setTimeout(resolve, 0));
          });

          // Invariant: Result container from Project A MUST be cleared (setConformanceData(null) is executed)
          expect(container.querySelector('[data-testid="conformance-result-container"]')).toBeNull();
          const errorBanner = container.querySelector('[data-testid="conformance-error-banner"]');
          expect(errorBanner).not.toBeNull();
          expect(errorBanner?.textContent).toContain('AUTH-0030');
          expect(errorBanner?.textContent).toContain('This project is not accessible.');
        } finally {
          globalThis.fetch = originalFetch;
        }
      });

      it('handles network failure, canonical 500 SYS-0002, and 502 HTML without leaking markup (F3)', async () => {
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

          // Sub-case 1: Network TypeError (fetch rejected)
          globalThis.fetch = vi.fn().mockRejectedValue(new TypeError('Failed to fetch'));

          await act(async () => {
            fetchBtn!.click();
          });
          await act(async () => {
            await new Promise((resolve) => setTimeout(resolve, 0));
          });

          let errorBanner = container.querySelector('[data-testid="conformance-error-banner"]');
          expect(errorBanner).not.toBeNull();
          expect(errorBanner?.textContent).toContain('Failed to fetch');
          expect(container.querySelector('[data-testid="conformance-result-container"]')).toBeNull();

          // Sub-case 2: Canonical 500 SYS-0002 ProblemDetails
          const canonical500: ProblemDetails = {
            type: 'about:blank',
            title: 'Internal Server Error',
            status: 500,
            code: 'SYS-0002',
            category: 'SYS',
            detail: 'Internal server error occurred.',
            retryable: true,
            traceId: '0123456789abcdef0123456789abcdef',
            causeRef: null,
            evidenceId: null,
          };

          globalThis.fetch = vi.fn().mockResolvedValue({
            ok: false,
            status: 500,
            statusText: 'Internal Server Error',
            headers: new Headers({ 'content-type': 'application/problem+json' }),
            json: async () => canonical500,
          } as any);

          await act(async () => {
            fetchBtn!.click();
          });
          await act(async () => {
            await new Promise((resolve) => setTimeout(resolve, 0));
          });

          errorBanner = container.querySelector('[data-testid="conformance-error-banner"]');
          expect(errorBanner).not.toBeNull();
          expect(errorBanner?.textContent).toContain('SYS-0002');
          expect(errorBanner?.textContent).toContain('500');
          expect(errorBanner?.textContent).toContain('Internal server error occurred.');
          expect(container.querySelector('[data-testid="conformance-result-container"]')).toBeNull();

          // Sub-case 3: 502 HTML Proxy Error (MUST NOT leak raw HTML tags)
          globalThis.fetch = vi.fn().mockResolvedValue({
            ok: false,
            status: 502,
            statusText: 'Bad Gateway',
            headers: new Headers({ 'content-type': 'text/html' }),
            text: async () => '<html><body><h1>502 Bad Gateway</h1><p>Proxy connection failed</p></body></html>',
          } as any);

          await act(async () => {
            fetchBtn!.click();
          });
          await act(async () => {
            await new Promise((resolve) => setTimeout(resolve, 0));
          });

          errorBanner = container.querySelector('[data-testid="conformance-error-banner"]');
          expect(errorBanner).not.toBeNull();
          expect(errorBanner?.textContent).toContain('502');
          expect(errorBanner?.textContent).not.toContain('<html>');
          expect(errorBanner?.textContent).not.toContain('<body>');
          expect(errorBanner?.textContent).not.toContain('<h1>');
          expect(errorBanner?.textContent).toContain('서버 게이트웨이 또는 프록시 오류가 발생했습니다.');
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
          expect(completedLiveRegion?.textContent).toContain('조회 완료: 미측정(NOT_OBSERVED)');
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

      it('satisfies WCAG AA text contrast ratio (>= 4.5:1) in dark theme by reading rendered DOM styles directly (F5)', async () => {
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

          await act(async () => {
            setInputValue(projectInput!, testProjectId);
          });
          await act(async () => {
            fetchBtn!.click();
          });
          await act(async () => {
            await new Promise((resolve) => setTimeout(resolve, 0));
          });

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

          const indexCssPath = path.resolve(__dirname, '../src/index.css');
          const indexCssContent = fs.readFileSync(indexCssPath, 'utf-8');
          const darkMatch = indexCssContent.match(/\[data-theme=['"]dark['"]\]\s*\{([\s\S]*?)\}/);
          if (!darkMatch) throw new Error('Could not find [data-theme="dark"] block in index.css');
          const darkCleanBlock = darkMatch[1].replace(/\/\*[\s\S]*?\*\//g, '');
          const darkTokenMap: Record<string, string> = {};
          const tokenRegex = /(--color-[a-z0-9-]+)\s*:\s*([^;]+);/g;
          let tm;
          while ((tm = tokenRegex.exec(darkCleanBlock)) !== null) {
            const val = tm[2].trim();
            if (val.startsWith('#')) {
              darkTokenMap[tm[1].trim()] = val;
            }
          }

          const parseRgba = (colorStr: string): [number, number, number, number] => {
            if (colorStr.startsWith('var(')) {
              const varName = colorStr.replace(/var\(|\)/g, '').trim();
              if (darkTokenMap[varName]) {
                colorStr = darkTokenMap[varName];
              } else {
                throw new Error(`Unresolved CSS token: ${varName}`);
              }
            }
            if (colorStr.startsWith('#')) {
              const clean = colorStr.replace('#', '');
              return [
                parseInt(clean.substring(0, 2), 16),
                parseInt(clean.substring(2, 4), 16),
                parseInt(clean.substring(4, 6), 16),
                1,
              ];
            }
            const match = colorStr.match(/rgba?\((\d+),\s*(\d+),\s*(\d+)(?:,\s*([\d.]+))?\)/);
            if (match) {
              return [
                parseInt(match[1], 10),
                parseInt(match[2], 10),
                parseInt(match[3], 10),
                match[4] !== undefined ? parseFloat(match[4]) : 1,
              ];
            }
            throw new Error(`Unrecognized color format: ${colorStr}`);
          };

          const blend = (fgRgba: [number, number, number, number], bgRgb: [number, number, number]): [number, number, number] => {
            const alpha = fgRgba[3];
            return [
              Math.round(fgRgba[0] * alpha + bgRgb[0] * (1 - alpha)),
              Math.round(fgRgba[1] * alpha + bgRgb[1] * (1 - alpha)),
              Math.round(fgRgba[2] * alpha + bgRgb[2] * (1 - alpha)),
            ];
          };

          const subtleHex = darkTokenMap['--color-bg-subtle'] || '#1f2937';
          const darkBgRgb: [number, number, number] = [
            parseInt(subtleHex.replace('#', '').substring(0, 2), 16),
            parseInt(subtleHex.replace('#', '').substring(2, 4), 16),
            parseInt(subtleHex.replace('#', '').substring(4, 6), 16),
          ];

          // 1. Read DOM style of Status Badge (미측정 NOT_OBSERVED)
          const statusBadge = container.querySelector<HTMLElement>('[data-testid="conformance-status-badge"]');
          expect(statusBadge).not.toBeNull();
          const badgeFg = parseRgba(statusBadge!.style.color);
          const badgeBg = parseRgba(statusBadge!.style.backgroundColor);
          const blendedBadgeBg = blend(badgeBg, darkBgRgb);
          const badgeContrast = getContrastRatio(
            getRelativeLuminance(badgeFg[0], badgeFg[1], badgeFg[2]),
            getRelativeLuminance(...blendedBadgeBg)
          );
          expect(badgeContrast).toBeGreaterThanOrEqual(4.5);

          // 2. Read DOM style of Standard Capability Badge (check 0 is standard)
          const standardBadge = container.querySelector<HTMLElement>('[data-testid="conformance-check-gated-0"]');
          expect(standardBadge).not.toBeNull();
          expect(standardBadge!.textContent).toBe('Standard');
          const stdFg = parseRgba(standardBadge!.style.color);
          const stdBg = parseRgba(standardBadge!.style.backgroundColor);
          const blendedStdBg = blend(stdBg, darkBgRgb);
          const stdContrast = getContrastRatio(
            getRelativeLuminance(stdFg[0], stdFg[1], stdFg[2]),
            getRelativeLuminance(...blendedStdBg)
          );
          expect(stdContrast).toBeGreaterThanOrEqual(4.5);
          expect(stdContrast).toBeGreaterThanOrEqual(5.0); // comfortably above WCAG AA threshold

          // 3. Read DOM style of Capability Gated Badge (check 12 is gated)
          const gatedBadge = container.querySelector<HTMLElement>('[data-testid="conformance-check-gated-12"]');
          expect(gatedBadge).not.toBeNull();
          expect(gatedBadge!.textContent).toBe('Capability Gated');
          const gatedFg = parseRgba(gatedBadge!.style.color);
          const gatedBg = parseRgba(gatedBadge!.style.backgroundColor);
          const blendedGatedBg = blend(gatedBg, darkBgRgb);
          const gatedContrast = getContrastRatio(
            getRelativeLuminance(gatedFg[0], gatedFg[1], gatedFg[2]),
            getRelativeLuminance(...blendedGatedBg)
          );
          expect(gatedContrast).toBeGreaterThanOrEqual(4.5);
        } finally {
          globalThis.fetch = originalFetch;
        }
      });

      // =========================================================================
      // G-03 Stage Two Single Route: GET /v1/projects/:projectId/adapters/:name/conformance
      // =========================================================================
      const ADAPTER_NOT_OBSERVED_REASON = 'No conformance run is recorded for this host and this adapter.';

      const canonicalSingleNotObservedPayload: AdapterConformanceNotObservedResponse = {
        status: 'NOT_OBSERVED',
        reason: ADAPTER_NOT_OBSERVED_REASON,
        scope: 'control-plane-host',
        adapter: 'gemini-cli',
        contractVersion: '1.0.0',
        checks: canonical15Checks,
        recordedAt: null,
      };

      const canonicalSingleRecordedPayload: AdapterConformanceRecordedResponse = {
        status: 'RECORDED',
        scope: 'control-plane-host',
        adapter: 'codex-cli',
        subject: 'fixture-adapter',
        provenance: 'in-server',
        contractVersion: '1.0.0',
        suiteContractVersion: '1.0.0',
        total: 15,
        passed: 14,
        failed: 0,
        skipped: 1,
        outcomes: canonical15Checks.map((check) => ({
          name: check.name,
          passed: check.name !== 'declared_server_cancel_actually_stops',
          skipped: check.name === 'declared_server_cancel_actually_stops',
        })),
        recordedAt: '2026-09-28T06:00:00Z',
      };

      it('strictly guards single adapter NOT_OBSERVED and RECORDED schemas and rejects invalid mutations', () => {
        // Valid responses pass
        expect(isAdapterConformanceNotObservedResponse(canonicalSingleNotObservedPayload)).toBe(true);
        expect(isAdapterConformanceUnion(canonicalSingleNotObservedPayload)).toBe(true);

        expect(isAdapterConformanceRecordedResponse(canonicalSingleRecordedPayload)).toBe(true);
        expect(isAdapterConformanceUnion(canonicalSingleRecordedPayload)).toBe(true);

        // NOT_OBSERVED rejects mutations
        expect(isAdapterConformanceNotObservedResponse({ ...canonicalSingleNotObservedPayload, recordedAt: '2026-09-28T06:00:00Z' })).toBe(false);
        expect(isAdapterConformanceNotObservedResponse({ ...canonicalSingleNotObservedPayload, status: 'RECORDED' })).toBe(false);
        expect(isAdapterConformanceNotObservedResponse({ ...canonicalSingleNotObservedPayload, scope: 'worker-node' })).toBe(false);
        expect(isAdapterConformanceNotObservedResponse({ ...canonicalSingleNotObservedPayload, extraKey: 'invalid' })).toBe(false);
        expect(isAdapterConformanceNotObservedResponse({ ...canonicalSingleNotObservedPayload, reason: '' })).toBe(false);

        // RECORDED rejects mutations (invariant enforcement)
        expect(isAdapterConformanceRecordedResponse({ ...canonicalSingleRecordedPayload, subject: 'installed-cli' })).toBe(false);
        expect(isAdapterConformanceRecordedResponse({ ...canonicalSingleRecordedPayload, provenance: 'hosted-ci-import' })).toBe(false);
        expect(isAdapterConformanceRecordedResponse({ ...canonicalSingleRecordedPayload, passed: 15 })).toBe(false);
        expect(isAdapterConformanceRecordedResponse({ ...canonicalSingleRecordedPayload, total: 16 })).toBe(false);
        expect(isAdapterConformanceRecordedResponse({ ...canonicalSingleRecordedPayload, outcomes: canonicalSingleRecordedPayload.outcomes.slice(1) })).toBe(false);
        expect(isAdapterConformanceRecordedResponse({ ...canonicalSingleRecordedPayload, conformant: true })).toBe(false);
        expect(isAdapterConformanceRecordedResponse({ ...canonicalSingleRecordedPayload, reason: 'unwanted' })).toBe(false);
        expect(isAdapterConformanceRecordedResponse({ ...canonicalSingleRecordedPayload, checks: canonical15Checks })).toBe(false);

        // Cross-branch rejection
        expect(isAdapterConformanceRecordedResponse(canonicalSingleNotObservedPayload)).toBe(false);
        expect(isAdapterConformanceNotObservedResponse(canonicalSingleRecordedPayload)).toBe(false);
        expect(isAdapterConformanceUnion({ ...canonicalSingleRecordedPayload, status: 'PASS' })).toBe(false);
      });

      it('fetches single adapter conformance via fetchAdapterConformance and enforces client guards', async () => {
        const originalFetch = globalThis.fetch;
        const testProjectId = 'prj_0123456789ABCDEFGHJKMNPQRS';
        const testAdapter = 'gemini-cli';

        try {
          // 1. Successful NOT_OBSERVED fetch
          globalThis.fetch = vi.fn().mockResolvedValue({
            ok: true,
            status: 200,
            headers: new Headers({ 'content-type': 'application/json' }),
            json: async () => canonicalSingleNotObservedPayload,
          } as any);

          const res1 = await fetchAdapterConformance(testProjectId, testAdapter);
          expect(res1.status).toBe('NOT_OBSERVED');
          expect((res1 as AdapterConformanceNotObservedResponse).reason).toBe(ADAPTER_NOT_OBSERVED_REASON);

          // 2. Successful RECORDED fetch
          globalThis.fetch = vi.fn().mockResolvedValue({
            ok: true,
            status: 200,
            headers: new Headers({ 'content-type': 'application/json' }),
            json: async () => canonicalSingleRecordedPayload,
          } as any);

          const res2 = await fetchAdapterConformance(testProjectId, 'codex-cli');
          expect(res2.status).toBe('RECORDED');
          expect((res2 as AdapterConformanceRecordedResponse).total).toBe(15);
          expect((res2 as AdapterConformanceRecordedResponse).subject).toBe('fixture-adapter');

          // 3. Rejects on contract mismatch
          globalThis.fetch = vi.fn().mockResolvedValue({
            ok: true,
            status: 200,
            headers: new Headers({ 'content-type': 'application/json' }),
            json: async () => ({ ...canonicalSingleRecordedPayload, subject: 'fake-adapter' }),
          } as any);

          await expect(fetchAdapterConformance(testProjectId, 'codex-cli')).rejects.toThrow(
            'AdapterConformanceResponse 응답 계약 불일치'
          );

          // 4. Guard against empty inputs
          await expect(fetchAdapterConformance('', 'codex-cli')).rejects.toThrow('프로젝트 ID를 확인하세요.');
          await expect(fetchAdapterConformance(testProjectId, '')).rejects.toThrow('어댑터 이름을 확인하세요.');
        } finally {
          globalThis.fetch = originalFetch;
        }
      });

      it('renders single adapter NOT_OBSERVED response with exact reason and check descriptors in UI', async () => {
        const originalFetch = globalThis.fetch;
        const testProjectId = 'prj_0123456789ABCDEFGHJKMNPQRS';

        try {
          globalThis.fetch = vi.fn().mockResolvedValue({
            ok: true,
            status: 200,
            headers: new Headers({ 'content-type': 'application/json' }),
            json: async () => canonicalSingleNotObservedPayload,
          } as any);

          await act(async () => {
            root.render(React.createElement(ModelLineageView, { initialLineages: TEST_FIXTURE_LINEAGES }));
          });

          const projectInput = container.querySelector<HTMLInputElement>('[data-testid="conformance-project-input"]');
          const adapterInput = container.querySelector<HTMLInputElement>('[data-testid="single-conformance-adapter-input"]');
          const singleFetchBtn = container.querySelector<HTMLButtonElement>('[data-testid="single-conformance-fetch-btn"]');

          await act(async () => {
            setInputValue(projectInput!, testProjectId);
            setInputValue(adapterInput!, 'gemini-cli');
          });

          await act(async () => {
            singleFetchBtn!.click();
          });
          await act(async () => {
            await new Promise((resolve) => setTimeout(resolve, 0));
          });

          expect(container.querySelector('[data-testid="single-conformance-status-badge"]')?.textContent).toBe('미측정 (NOT_OBSERVED)');
          expect(container.querySelector('[data-testid="single-conformance-adapter"]')?.textContent).toBe('gemini-cli');
          expect(container.querySelector('[data-testid="single-conformance-scope"]')?.textContent).toBe('control-plane-host');
          expect(container.querySelector('[data-testid="single-conformance-contract-version"]')?.textContent).toBe('1.0.0');
          expect(container.querySelector('[data-testid="single-conformance-recorded-at"]')?.textContent).toBe('null (미측정)');
          expect(container.querySelector('[data-testid="single-conformance-reason"]')?.textContent).toBe(ADAPTER_NOT_OBSERVED_REASON);

          const checksTable = container.querySelector('[data-testid="single-conformance-checks-table"]');
          expect(checksTable).not.toBeNull();
          expect(container.querySelector('[data-testid="single-conformance-check-name-0"]')?.textContent).toBe('declares_contract_version');
          expect(container.querySelector('[data-testid="single-conformance-live-status"]')?.textContent).toContain('조회 완료: 미측정(NOT_OBSERVED)');
        } finally {
          globalThis.fetch = originalFetch;
        }
      });

      it('renders single adapter RECORDED response with exact counts, outcomes, and subject note in UI', async () => {
        const originalFetch = globalThis.fetch;
        const testProjectId = 'prj_0123456789ABCDEFGHJKMNPQRS';

        try {
          globalThis.fetch = vi.fn().mockResolvedValue({
            ok: true,
            status: 200,
            headers: new Headers({ 'content-type': 'application/json' }),
            json: async () => canonicalSingleRecordedPayload,
          } as any);

          await act(async () => {
            root.render(React.createElement(ModelLineageView, { initialLineages: TEST_FIXTURE_LINEAGES }));
          });

          const projectInput = container.querySelector<HTMLInputElement>('[data-testid="conformance-project-input"]');
          const adapterInput = container.querySelector<HTMLInputElement>('[data-testid="single-conformance-adapter-input"]');
          const singleFetchBtn = container.querySelector<HTMLButtonElement>('[data-testid="single-conformance-fetch-btn"]');

          await act(async () => {
            setInputValue(projectInput!, testProjectId);
            setInputValue(adapterInput!, 'codex-cli');
          });

          await act(async () => {
            singleFetchBtn!.click();
          });
          await act(async () => {
            await new Promise((resolve) => setTimeout(resolve, 0));
          });

          expect(container.querySelector('[data-testid="single-conformance-status-badge"]')?.textContent).toBe('기록됨 (RECORDED)');
          expect(container.querySelector('[data-testid="single-conformance-adapter"]')?.textContent).toBe('codex-cli');
          expect(container.querySelector('[data-testid="single-conformance-subject"]')?.textContent).toBe('fixture-adapter / in-server');
          expect(container.querySelector('[data-testid="single-conformance-suite-contract-version"]')?.textContent).toBe('1.0.0');
          expect(container.querySelector('[data-testid="single-conformance-counts"]')?.textContent).toBe('전체 15 · 통과 14 · 실패 0 · 건너뜀 1');
          expect(container.querySelector('[data-testid="single-conformance-recorded-at"]')?.textContent).toBe('2026-09-28T06:00:00Z');
          expect(container.querySelector('[data-testid="single-conformance-subject-note"]')?.textContent).toContain('fixture-adapter');

          // Outcomes table
          const outcomesTable = container.querySelector('[data-testid="single-conformance-outcomes-table"]');
          expect(outcomesTable).not.toBeNull();
          expect(container.querySelector('[data-testid="single-conformance-outcome-name-0"]')?.textContent).toBe('declares_contract_version');
          expect(container.querySelector('[data-testid="single-conformance-outcome-status-0"]')?.textContent).toBe('통과 (Passed)');
          expect(container.querySelector('[data-testid="single-conformance-outcome-name-12"]')?.textContent).toBe('declared_server_cancel_actually_stops');
          expect(container.querySelector('[data-testid="single-conformance-outcome-status-12"]')?.textContent).toBe('건너뜀 (Skipped)');

          // Zero-verdict invariant: no fake 100% or conformant label
          const singleContainer = container.querySelector('[data-testid="single-conformance-result-container"]');
          expect(singleContainer?.textContent).not.toContain('100%');
          expect(singleContainer?.textContent).not.toMatch(/conforming/i);
          expect(container.querySelector('[data-testid="single-conformance-live-status"]')?.textContent).toContain('조회 완료: 기록됨(RECORDED)');
        } finally {
          globalThis.fetch = originalFetch;
        }
      });

      it('handles single route ProblemDetails (404 RES-0004 without echo, 500 SYS-0002 without retry, 503 SYS-0001 with retry)', async () => {
        const originalFetch = globalThis.fetch;
        const testProjectId = 'prj_0123456789ABCDEFGHJKMNPQRS';

        try {
          await act(async () => {
            root.render(React.createElement(ModelLineageView, { initialLineages: TEST_FIXTURE_LINEAGES }));
          });

          const projectInput = container.querySelector<HTMLInputElement>('[data-testid="conformance-project-input"]');
          const adapterInput = container.querySelector<HTMLInputElement>('[data-testid="single-conformance-adapter-input"]');
          const singleFetchBtn = container.querySelector<HTMLButtonElement>('[data-testid="single-conformance-fetch-btn"]');

          await act(async () => {
            setInputValue(projectInput!, testProjectId);
            setInputValue(adapterInput!, 'unknown-adapter');
          });

          // 1. 404 RES-0004 (retryable: false): do not echo input string, no retry button
          globalThis.fetch = vi.fn().mockResolvedValue({
            ok: false,
            status: 404,
            headers: new Headers({ 'content-type': 'application/problem+json' }),
            json: async () => ({
              type: 'about:blank',
              title: 'RES-0004',
              status: 404,
              code: 'RES-0004',
              category: 'RES',
              detail: 'No adapter with that name exists.',
              retryable: false,
              traceId: '00000000000000000000000000000000',
              causeRef: null,
              evidenceId: null,
            }),
          } as any);

          await act(async () => {
            singleFetchBtn!.click();
          });
          await act(async () => {
            await new Promise((resolve) => setTimeout(resolve, 0));
          });

          let errBanner = container.querySelector('[data-testid="single-conformance-error-banner"]');
          expect(errBanner).not.toBeNull();
          expect(errBanner?.textContent).toContain('[RES-0004]');
          expect(errBanner?.textContent).toContain('(404)');
          expect(errBanner?.textContent).toContain('어댑터 없음');
          // Must not echo user's input string "unknown-adapter" in error banner or live status
          expect(errBanner?.textContent).not.toContain('unknown-adapter');
          const liveStatus = container.querySelector('[data-testid="single-conformance-live-status"]');
          expect(liveStatus?.textContent).toBe('❌ 단건 어댑터 Conformance 조회 실패');
          expect(liveStatus?.textContent).not.toContain('unknown-adapter');
          const singleSection = container.querySelector('[data-testid="single-conformance-live-status"]')?.parentElement;
          expect(singleSection?.textContent).not.toContain('unknown-adapter');
          // Retry button must NOT be present
          expect(container.querySelector('[data-testid="single-conformance-retry-btn"]')).toBeNull();

          // 2. 500 SYS-0002 (retryable: false): no retry button
          globalThis.fetch = vi.fn().mockResolvedValue({
            ok: false,
            status: 500,
            headers: new Headers({ 'content-type': 'application/problem+json' }),
            json: async () => ({
              type: 'about:blank',
              title: 'SYS-0002',
              status: 500,
              code: 'SYS-0002',
              category: 'SYS',
              detail: 'This control plane has no host identity configured, so it cannot report conformance records.',
              retryable: false,
              traceId: '00000000000000000000000000000000',
              causeRef: null,
              evidenceId: null,
            }),
          } as any);

          await act(async () => {
            singleFetchBtn!.click();
          });
          await act(async () => {
            await new Promise((resolve) => setTimeout(resolve, 0));
          });

          errBanner = container.querySelector('[data-testid="single-conformance-error-banner"]');
          expect(errBanner?.textContent).toContain('[SYS-0002]');
          expect(errBanner?.textContent).toContain('host identity');
          expect(container.querySelector('[data-testid="single-conformance-retry-btn"]')).toBeNull();

          // 3. 503 SYS-0001 (retryable: true): displays retry button
          globalThis.fetch = vi.fn().mockResolvedValue({
            ok: false,
            status: 503,
            headers: new Headers({ 'content-type': 'application/problem+json' }),
            json: async () => ({
              type: 'about:blank',
              title: 'SYS-0001',
              status: 503,
              code: 'SYS-0001',
              category: 'SYS',
              detail: 'The resource is locked by another request; retry.',
              retryable: true,
              traceId: '00000000000000000000000000000000',
              causeRef: null,
              evidenceId: null,
            }),
          } as any);

          await act(async () => {
            singleFetchBtn!.click();
          });
          await act(async () => {
            await new Promise((resolve) => setTimeout(resolve, 0));
          });

          errBanner = container.querySelector('[data-testid="single-conformance-error-banner"]');
          expect(errBanner?.textContent).toContain('[SYS-0001]');
          expect(errBanner?.textContent).toContain('locked');
          const retryBtn = container.querySelector<HTMLButtonElement>('[data-testid="single-conformance-retry-btn"]');
          expect(retryBtn).not.toBeNull();
          expect(retryBtn?.textContent).toBe('다시 시도');
        } finally {
          globalThis.fetch = originalFetch;
        }
      });

      it('supports single adapter drilldown from list records table and clears state on input change', async () => {
        const originalFetch = globalThis.fetch;
        const testProjectId = 'prj_0123456789ABCDEFGHJKMNPQRS';

        try {
          // List route fetch mock
          globalThis.fetch = vi.fn().mockResolvedValue({
            ok: true,
            status: 200,
            headers: new Headers({ 'content-type': 'application/json' }),
            json: async () => canonicalRecordedPayload,
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

          // Records table contains inspect button
          const inspectBtn = container.querySelector<HTMLButtonElement>('[data-testid="conformance-inspect-btn-0"]');
          expect(inspectBtn).not.toBeNull();

          // Single route fetch mock
          globalThis.fetch = vi.fn().mockResolvedValue({
            ok: true,
            status: 200,
            headers: new Headers({ 'content-type': 'application/json' }),
            json: async () => canonicalSingleRecordedPayload,
          } as any);

          await act(async () => {
            inspectBtn!.click();
          });
          await act(async () => {
            await new Promise((resolve) => setTimeout(resolve, 0));
          });

          expect(container.querySelector('[data-testid="single-conformance-result-container"]')).not.toBeNull();
          expect(container.querySelector('[data-testid="single-conformance-adapter"]')?.textContent).toBe('codex-cli');

          // State isolation on input change: changing single adapter input clears single result container
          const adapterInput = container.querySelector<HTMLInputElement>('[data-testid="single-conformance-adapter-input"]');
          await act(async () => {
            setInputValue(adapterInput!, 'claude-code');
          });
          expect(container.querySelector('[data-testid="single-conformance-result-container"]')).toBeNull();

          // Changing project input clears both list and single results
          await act(async () => {
            setInputValue(projectInput!, 'prj_DIFFERENT');
          });
          expect(container.querySelector('[data-testid="conformance-result-container"]')).toBeNull();
          expect(container.querySelector('[data-testid="single-conformance-result-container"]')).toBeNull();
        } finally {
          globalThis.fetch = originalFetch;
        }
      });

      it('M2: ignores late in-flight response when adapter input changes and guards against concurrent requests', async () => {
        const originalFetch = globalThis.fetch;
        const testProjectId = 'prj_0123456789ABCDEFGHJKMNPQRS';
        let resolveFirstFetch: ((res: any) => void) | null = null;
        let firstFetchSignal: AbortSignal | null = null;

        try {
          globalThis.fetch = vi.fn().mockImplementation((url: string, init?: RequestInit) => {
            if (url.includes('/adapters/codex-cli/conformance')) {
              firstFetchSignal = init?.signal || null;
              return new Promise((resolve) => {
                resolveFirstFetch = resolve;
              });
            }
            if (url.includes('/adapters/gemini-cli/conformance')) {
              return Promise.resolve({
                ok: true,
                status: 200,
                headers: new Headers({ 'content-type': 'application/json' }),
                json: async () => canonicalSingleNotObservedPayload,
              } as any);
            }
            return Promise.reject(new Error(`Unhandled URL: ${url}`));
          });

          await act(async () => {
            root.render(React.createElement(ModelLineageView, { initialLineages: TEST_FIXTURE_LINEAGES }));
          });

          const projectInput = container.querySelector<HTMLInputElement>('[data-testid="conformance-project-input"]');
          const setInputValue = (el: HTMLInputElement, val: string) => {
            const setter = Object.getOwnPropertyDescriptor(window.HTMLInputElement.prototype, 'value')?.set;
            setter?.call(el, val);
            el.dispatchEvent(new Event('input', { bubbles: true }));
            el.dispatchEvent(new Event('change', { bubbles: true }));
          };

          await act(async () => {
            setInputValue(projectInput!, testProjectId);
          });

          const adapterInput = container.querySelector<HTMLInputElement>('[data-testid="single-conformance-adapter-input"]');
          const singleFetchBtn = container.querySelector<HTMLButtonElement>('[data-testid="single-conformance-fetch-btn"]');

          await act(async () => {
            setInputValue(adapterInput!, 'codex-cli');
          });

          // 1. Submit first request -> in-flight
          await act(async () => {
            singleFetchBtn!.click();
          });

          // Loading is true: button is disabled
          expect(singleFetchBtn?.disabled).toBe(true);
          expect(singleFetchBtn?.textContent).toBe('조회 중...');
          const inspectBtn0 = container.querySelector<HTMLButtonElement>('[data-testid="conformance-inspect-btn-0"]');
          if (inspectBtn0) {
            expect(inspectBtn0.disabled).toBe(true);
          }

          // Submitting again while loading must be ignored (early return guard)
          await act(async () => {
            singleFetchBtn!.closest('form')?.dispatchEvent(new Event('submit', { bubbles: true, cancelable: true }));
          });
          expect((globalThis.fetch as any).mock.calls.length).toBe(1);

          // 2. While first request is in-flight, change adapter input to 'gemini-cli'
          await act(async () => {
            setInputValue(adapterInput!, 'gemini-cli');
          });

          // Signal should be aborted and loading cleared
          expect(firstFetchSignal?.aborted).toBe(true);
          expect(singleFetchBtn?.disabled).toBe(false);
          expect(singleFetchBtn?.textContent).toBe('어댑터 Conformance 조회');

          // 3. Resolve delayed first request (which carries codex-cli recorded response)
          await act(async () => {
            resolveFirstFetch!({
              ok: true,
              status: 200,
              headers: new Headers({ 'content-type': 'application/json' }),
              json: async () => canonicalSingleRecordedPayload,
            });
            await new Promise((resolve) => setTimeout(resolve, 0));
          });

          // Late response must be discarded! No result container, no codex-cli rendered
          expect(container.querySelector('[data-testid="single-conformance-result-container"]')).toBeNull();
          expect(container.querySelector('[data-testid="single-conformance-live-status"]')?.textContent).not.toContain('codex-cli');
        } finally {
          globalThis.fetch = originalFetch;
        }
      });
    });
  });
});
