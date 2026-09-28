// @vitest-environment happy-dom
import React from 'react';
import { describe, it, expect, beforeEach, afterEach, vi } from 'vitest';
import { createRoot, Root } from 'react-dom/client';
import { act } from 'react';
import { ModelLineageView } from '../src/features/mlops/ModelLineageView';
import {
  isModelLineageTraceResponse,
  isModelVersionResponse,
  isRetentionPinResponse,
  isModelReleaseResponse,
  isValidIsoDateTime,
  generateIdempotencyKey,
} from '../src/shared/api/modelRegistryObservation';
import type { ModelLineageTraceResponse } from '../src/contracts/model-lineage-trace-response';
import type { ModelVersionResponse } from '../src/contracts/model-version-response';
import type { RetentionPinResponse } from '../src/contracts/retention-pin-response';
import type { ModelReleaseResponse } from '../src/contracts/model-release-response';

describe('G-05 Model Registry & Lineage Business Routes (Card 94)', () => {
  let container: HTMLDivElement;
  let root: Root;
  let originalFetch: typeof globalThis.fetch;

  beforeEach(() => {
    (globalThis as any).IS_REACT_ACT_ENVIRONMENT = true;
    container = document.createElement('div');
    document.body.appendChild(container);
    root = createRoot(container);
    originalFetch = globalThis.fetch;
  });

  afterEach(() => {
    globalThis.fetch = originalFetch;
    act(() => {
      root?.unmount();
    });
    container?.remove();
    vi.restoreAllMocks();
  });

  const validTraceResponse: ModelLineageTraceResponse = {
    modelVersionId: 'mv_01JABCDEF1234567890ABCDEF',
    version: '1.0.0',
    stage: 'released',
    contentSha256: '0123456789abcdef0123456789abcdef0123456789abcdef0123456789abcdef',
    producedByRunId: 'run_01J9876543210',
    fullyTraceable: true,
    traceabilityLimitedByScope: false,
    detailedKinds: ['datasets', 'deployments'],
    countOnlyKinds: ['evaluations', 'commits', 'approvals'],
    missing: [],
    unresolved: [
      { kind: 'evaluations', count: 2 },
      { kind: 'commits', count: 1 },
    ],
    datasets: [
      {
        datasetVersionId: 'ds_01J11223344',
        version: 'v2.1',
        contentSha256: 'aaaabbbbccccdddd0123456789abcdef0123456789abcdef0123456789abcdef',
        uri: 'inv://datasets/curated-v2@v2.1',
      },
    ],
    deployments: [
      {
        deploymentId: 'dep_01J99887766',
        environment: 'pilot',
        status: 'active',
        deployedDigest: '0123456789abcdef0123456789abcdef0123456789abcdef0123456789abcdef',
        deployedAt: '2026-09-28T12:00:00Z',
        approvalId: 'apr_01JLEGALAPPROVE',
        imageId: null,
      },
    ],
  };

  const validVersionResponse: ModelVersionResponse = {
    modelVersionId: 'mv_01JNEWREGISTERED001',
    modelId: 'mod_llama3',
    version: '1.0.0-rc1',
    stage: 'draft',
    contentSha256: '11112222333344445555666677778888aaaabbbbccccddddeeeeffff00001111',
    byteSize: 1048576,
    uri: 'inv://models/llama3@1.0.0-rc1',
    createdAt: '2026-09-28T14:30:00Z',
  };

  const validPinResponse: RetentionPinResponse = {
    modelVersionId: 'mv_01JNEWREGISTERED001',
    modelId: 'mod_llama3',
    version: '1.0.0-rc1',
    stage: 'draft',
    retentionPinnedUntil: '2026-12-31T23:59:59Z',
    extended: true,
  };

  const validReleaseResponse: ModelReleaseResponse = {
    modelVersionId: 'mv_01JNEWREGISTERED001',
    modelId: 'mod_llama3',
    version: '1.0.0-rc1',
    stage: 'released',
    contentSha256: '11112222333344445555666677778888aaaabbbbccccddddeeeeffff00001111',
  };

  // 1. Lineage Query Success Path & Honest NOT_OBSERVED Rendering
  it('queries real GET /lineage route and honestly renders trace data with NOT_OBSERVED for unobserved metrics', async () => {
    let capturedUrl = '';
    let capturedMethod = '';

    globalThis.fetch = vi.fn().mockImplementation((url, init) => {
      capturedUrl = String(url);
      capturedMethod = init?.method || 'GET';
      return Promise.resolve(
        new Response(JSON.stringify(validTraceResponse), {
          status: 200,
          headers: { 'Content-Type': 'application/json' },
        })
      );
    });

    await act(async () => {
      root.render(
        <ModelLineageView
          projectId="prj_alpha"
          initialModelId="mod_llama3"
          initialVersion="1.0.0"
        />
      );
    });

    // Verify W3 seam badge is always present
    const w3Badge = container.querySelector('[data-testid="badge-w3-verify-seam"]');
    expect(w3Badge).not.toBeNull();
    expect(w3Badge?.textContent).toContain('W3 검증: 미연결 (검증 앵커 #215 대기)');

    const queryBtn = container.querySelector('[data-testid="btn-query-lineage"]') as HTMLButtonElement;
    expect(queryBtn).not.toBeNull();

    await act(async () => {
      queryBtn.click();
    });

    expect(capturedMethod).toBe('GET');
    expect(capturedUrl).toBe('/v1/projects/prj_alpha/models/mod_llama3/versions/1.0.0/lineage');

    // Real lineage container must appear
    const realContainer = container.querySelector('[data-testid="real-lineage-container"]');
    expect(realContainer).not.toBeNull();
    expect(realContainer?.textContent).toContain('[1.0.0] 실서버 계보 추적 결과');

    // Fully traceable and scope limited badges
    const traceableBadge = container.querySelector('[data-testid="badge-fully-traceable"]');
    expect(traceableBadge?.textContent).toContain('완전 추적 가능');

    // Datasets Table
    const datasetsSection = container.querySelector('[data-testid="real-lineage-datasets"]');
    expect(datasetsSection?.textContent).toContain('ds_01J11223344');
    expect(datasetsSection?.textContent).toContain('inv://datasets/curated-v2@v2.1');

    // Deployments Table
    const deploymentsSection = container.querySelector('[data-testid="real-lineage-deployments"]');
    expect(deploymentsSection?.textContent).toContain('dep_01J99887766');
    expect(deploymentsSection?.textContent).toContain('pilot');
    expect(deploymentsSection?.textContent).toContain('apr_01JLEGALAPPROVE');

    // CRITICAL: Honest NOT_OBSERVED rendering for unserved evaluation/commit/approval fields
    const evalUnobserved = container.querySelector('[data-testid="trace-evaluations-unobserved"]');
    expect(evalUnobserved).not.toBeNull();
    expect(evalUnobserved?.textContent).toContain('NOT_OBSERVED (미관측)');
    expect(evalUnobserved?.textContent).toContain('응답 스키마에 미포함되어 가짜 점수 합성을 차단합니다.');

    const commitsUnobserved = container.querySelector('[data-testid="trace-commits-unobserved"]');
    expect(commitsUnobserved?.textContent).toContain('NOT_OBSERVED (범위 외)');

    // Ensure NO fake accuracy (85.0% or 95.0% or fake F1) in real lineage container
    expect(realContainer?.textContent).not.toContain('85.0%');
    expect(realContainer?.textContent).not.toContain('95.0%');
    expect(realContainer?.textContent).not.toContain('F1 Score: 0');
  });

  // 2. W2 Register Model Version Route & Idempotency Key
  it('registers model version via POST /versions with Idempotency-Key and renders 201 response', async () => {
    let capturedUrl = '';
    let capturedMethod = '';
    let capturedHeaders: Record<string, string> = {};
    let capturedBody = '';

    globalThis.fetch = vi.fn().mockImplementation((url, init) => {
      capturedUrl = String(url);
      capturedMethod = init?.method || 'GET';
      capturedBody = String(init?.body || '');
      if (init?.headers instanceof Headers) {
        init.headers.forEach((v, k) => {
          capturedHeaders[k.toLowerCase()] = v;
        });
      }
      return Promise.resolve(
        new Response(JSON.stringify(validVersionResponse), {
          status: 201,
          headers: { 'Content-Type': 'application/json' },
        })
      );
    });

    await act(async () => {
      root.render(
        <ModelLineageView
          projectId="prj_alpha"
          initialModelId="mod_llama3"
          currentUser={{ canApprove: true }}
        />
      );
    });

    // Switch to Register tab
    const tabs = container.querySelectorAll('button');
    const registerTabBtn = Array.from(tabs).find((b) => b.textContent?.includes('버전 등록'));
    expect(registerTabBtn).toBeDefined();

    await act(async () => {
      registerTabBtn?.click();
    });

    // Fill inputs
    const versionInput = container.querySelector('[data-testid="input-register-version"]') as HTMLInputElement;
    const shaInput = container.querySelector('[data-testid="input-register-sha256"]') as HTMLInputElement;
    const byteInput = container.querySelector('[data-testid="input-register-bytesize"]') as HTMLInputElement;

    await act(async () => {
      const setNative = Object.getOwnPropertyDescriptor(window.HTMLInputElement.prototype, 'value')?.set;
      setNative?.call(versionInput, '1.0.0-rc1');
      versionInput.dispatchEvent(new Event('input', { bubbles: true }));
      versionInput.dispatchEvent(new Event('change', { bubbles: true }));

      setNative?.call(shaInput, '11112222333344445555666677778888aaaabbbbccccddddeeeeffff00001111');
      shaInput.dispatchEvent(new Event('input', { bubbles: true }));
      shaInput.dispatchEvent(new Event('change', { bubbles: true }));

      setNative?.call(byteInput, '1048576');
      byteInput.dispatchEvent(new Event('input', { bubbles: true }));
      byteInput.dispatchEvent(new Event('change', { bubbles: true }));
    });

    const submitBtn = container.querySelector('[data-testid="btn-register-version"]') as HTMLButtonElement;
    expect(submitBtn.disabled).toBe(false);

    await act(async () => {
      submitBtn.click();
    });

    expect(capturedMethod).toBe('POST');
    expect(capturedUrl).toBe('/v1/projects/prj_alpha/models/mod_llama3/versions');
    expect(capturedHeaders['idempotency-key']).toBeDefined();
    expect(capturedHeaders['idempotency-key'].length).toBeGreaterThan(5);

    const parsedBody = JSON.parse(capturedBody);
    expect(parsedBody.version).toBe('1.0.0-rc1');
    expect(parsedBody.contentSha256).toBe('11112222333344445555666677778888aaaabbbbccccddddeeeeffff00001111');
    expect(parsedBody.byteSize).toBe(1048576);

    const successBanner = container.querySelector('[data-testid="registry-register-success"]');
    expect(successBanner).not.toBeNull();
    expect(successBanner?.textContent).toContain('모델 버전 등록 완료 (201 Created)');
    expect(successBanner?.textContent).toContain('mv_01JNEWREGISTERED001');
    expect(successBanner?.textContent).toContain('draft');
  });

  // 3. W4 Extend Retention Pin Route & Idempotency Key
  it('extends retention pin via POST /retention-pin with Idempotency-Key and renders 200 response', async () => {
    let capturedUrl = '';
    let capturedMethod = '';
    let capturedHeaders: Record<string, string> = {};
    let capturedBody = '';

    globalThis.fetch = vi.fn().mockImplementation((url, init) => {
      capturedUrl = String(url);
      capturedMethod = init?.method || 'GET';
      capturedBody = String(init?.body || '');
      if (init?.headers instanceof Headers) {
        init.headers.forEach((v, k) => {
          capturedHeaders[k.toLowerCase()] = v;
        });
      }
      return Promise.resolve(
        new Response(JSON.stringify(validPinResponse), {
          status: 200,
          headers: { 'Content-Type': 'application/json' },
        })
      );
    });

    await act(async () => {
      root.render(
        <ModelLineageView
          projectId="prj_alpha"
          initialModelId="mod_llama3"
          initialVersion="1.0.0-rc1"
          currentUser={{ canApprove: true }}
        />
      );
    });

    // Switch to Pin tab
    const tabs = container.querySelectorAll('button');
    const pinTabBtn = Array.from(tabs).find((b) => b.textContent?.includes('보존 고정'));
    expect(pinTabBtn).toBeDefined();

    await act(async () => {
      pinTabBtn?.click();
    });

    const untilInput = container.querySelector('[data-testid="input-pin-until"]') as HTMLInputElement;

    await act(async () => {
      const setNative = Object.getOwnPropertyDescriptor(window.HTMLInputElement.prototype, 'value')?.set;
      setNative?.call(untilInput, '2026-12-31T23:59:59Z');
      untilInput.dispatchEvent(new Event('input', { bubbles: true }));
      untilInput.dispatchEvent(new Event('change', { bubbles: true }));
    });

    const pinBtn = container.querySelector('[data-testid="btn-pin-retention"]') as HTMLButtonElement;
    expect(pinBtn.disabled).toBe(false);

    await act(async () => {
      pinBtn.click();
    });

    expect(capturedMethod).toBe('POST');
    expect(capturedUrl).toBe('/v1/projects/prj_alpha/models/mod_llama3/versions/1.0.0-rc1/retention-pin');
    expect(capturedHeaders['idempotency-key']).toBeDefined();

    const parsedBody = JSON.parse(capturedBody);
    expect(parsedBody.until).toBe('2026-12-31T23:59:59Z');

    const pinSuccess = container.querySelector('[data-testid="registry-pin-success"]');
    expect(pinSuccess).not.toBeNull();
    expect(pinSuccess?.textContent).toContain('보존 고정 판정 완료 (200 OK)');
    expect(container.querySelector('[data-testid="pin-extended-flag"]')?.textContent).toBe('true');
  });

  // 4. Model Release Route
  it('releases model version via POST /release with declaration and renders 200 response', async () => {
    let capturedUrl = '';
    let capturedMethod = '';
    let capturedBody = '';

    globalThis.fetch = vi.fn().mockImplementation((url, init) => {
      capturedUrl = String(url);
      capturedMethod = init?.method || 'GET';
      capturedBody = String(init?.body || '');
      return Promise.resolve(
        new Response(JSON.stringify(validReleaseResponse), {
          status: 200,
          headers: { 'Content-Type': 'application/json' },
        })
      );
    });

    await act(async () => {
      root.render(
        <ModelLineageView
          projectId="prj_alpha"
          initialModelId="mod_llama3"
          initialVersion="1.0.0-rc1"
          currentUser={{ canApprove: true }}
        />
      );
    });

    // Switch to Release tab
    const tabs = container.querySelectorAll('button');
    const releaseTabBtn = Array.from(tabs).find((b) => b.textContent?.includes('모델 릴리스'));
    expect(releaseTabBtn).toBeDefined();

    await act(async () => {
      releaseTabBtn?.click();
    });

    const releaseBtn = container.querySelector('[data-testid="btn-release-model"]') as HTMLButtonElement;
    expect(releaseBtn.disabled).toBe(false);

    await act(async () => {
      releaseBtn.click();
    });

    expect(capturedMethod).toBe('POST');
    expect(capturedUrl).toBe('/v1/projects/prj_alpha/models/mod_llama3/versions/1.0.0-rc1/release');

    const parsedBody = JSON.parse(capturedBody);
    expect(parsedBody.licensePolicy).toBe('Apache-2.0');
    expect(parsedBody.classification).toBe('internal');

    const releaseSuccess = container.querySelector('[data-testid="registry-release-success"]');
    expect(releaseSuccess).not.toBeNull();
    expect(releaseSuccess?.textContent).toContain('모델 릴리스 완료 (200 OK)');
    expect(releaseSuccess?.textContent).toContain('released');
  });

  // 5. RFC 9457 Problem Details Canonical Error Rendering (409 Conflict)
  it('renders RFC 9457 ProblemDetails with exact code, title, detail, and traceId on 409 Conflict', async () => {
    const canonical409Problem = {
      type: 'about:blank',
      title: 'Graph precondition failed',
      status: 409,
      code: 'GRAPH-0002',
      category: 'GRAPH',
      detail: 'The model version is not fully traceable: missing datasets',
      retryable: false,
      traceId: '1234567890abcdef1234567890abcdef',
      causeRef: 'mv_01JABCDEF1234567890ABCDEF',
      evidenceId: null,
    };

    globalThis.fetch = vi.fn().mockImplementation(() => {
      return Promise.resolve(
        new Response(JSON.stringify(canonical409Problem), {
          status: 409,
          headers: { 'Content-Type': 'application/problem+json' },
        })
      );
    });

    await act(async () => {
      root.render(
        <ModelLineageView
          projectId="prj_alpha"
          initialModelId="mod_llama3"
          initialVersion="1.0.0-rc1"
          currentUser={{ canApprove: true }}
        />
      );
    });

    const queryBtn = container.querySelector('[data-testid="btn-query-lineage"]') as HTMLButtonElement;
    await act(async () => {
      queryBtn.click();
    });

    const alert = container.querySelector('[data-testid="registry-problem-alert"]');
    expect(alert).not.toBeNull();
    expect(alert?.getAttribute('role')).toBe('alert');

    expect(container.querySelector('[data-testid="problem-code"]')?.textContent).toBe('GRAPH-0002');
    expect(container.querySelector('[data-testid="problem-detail"]')?.textContent).toBe(
      'The model version is not fully traceable: missing datasets'
    );
    expect(container.querySelector('[data-testid="problem-trace-id"]')?.textContent).toBe(
      '1234567890abcdef1234567890abcdef'
    );
  });

  // 6. RFC 9457 Problem Details: 403 Forbidden AUTH-0030
  it('renders 403 Forbidden with AUTH-0030 when approval grade is required', async () => {
    const canonical403Problem = {
      type: 'about:blank',
      title: 'Action forbidden for project scope',
      status: 403,
      code: 'AUTH-0030',
      category: 'AUTH',
      detail: 'Registering a model version requires approval permission.',
      retryable: false,
      traceId: 'abcdef0123456789abcdef0123456789',
      causeRef: null,
      evidenceId: null,
    };

    globalThis.fetch = vi.fn().mockImplementation(() => {
      return Promise.resolve(
        new Response(JSON.stringify(canonical403Problem), {
          status: 403,
          headers: { 'Content-Type': 'application/problem+json' },
        })
      );
    });

    await act(async () => {
      root.render(
        <ModelLineageView
          projectId="prj_alpha"
          initialModelId="mod_llama3"
          currentUser={{ canApprove: true }}
        />
      );
    });

    const tabs = container.querySelectorAll('button');
    const registerTabBtn = Array.from(tabs).find((b) => b.textContent?.includes('버전 등록'));
    await act(async () => {
      registerTabBtn?.click();
    });

    const versionInput = container.querySelector('[data-testid="input-register-version"]') as HTMLInputElement;
    const shaInput = container.querySelector('[data-testid="input-register-sha256"]') as HTMLInputElement;
    await act(async () => {
      const setNative = Object.getOwnPropertyDescriptor(window.HTMLInputElement.prototype, 'value')?.set;
      setNative?.call(versionInput, '2.0.0');
      versionInput.dispatchEvent(new Event('input', { bubbles: true }));
      setNative?.call(shaInput, '00001111222233334444555566667777aaaabbbbccccddddeeeeffff01234567');
      shaInput.dispatchEvent(new Event('input', { bubbles: true }));
    });

    const submitBtn = container.querySelector('[data-testid="btn-register-version"]') as HTMLButtonElement;
    await act(async () => {
      submitBtn.click();
    });

    const alert = container.querySelector('[data-testid="registry-problem-alert"]');
    expect(alert).not.toBeNull();
    expect(container.querySelector('[data-testid="problem-code"]')?.textContent).toBe('AUTH-0030');
    expect(container.querySelector('[data-testid="problem-detail"]')?.textContent).toContain(
      'Registering a model version requires approval permission'
    );
  });

  // 7. RFC 9457 Problem Details: 503 Retryable Lock Contention
  it('renders 503 Service Unavailable with retryable indicator', async () => {
    const lockWaitProblem = {
      type: 'about:blank',
      title: 'Upstream unavailable',
      status: 503,
      code: 'SYS-0001',
      category: 'SYS',
      detail: 'The model version is locked by another request; retry.',
      retryable: true,
      traceId: 'fedcba9876543210fedcba9876543210',
      causeRef: null,
      evidenceId: null,
    };

    globalThis.fetch = vi.fn().mockImplementation(() => {
      return Promise.resolve(
        new Response(JSON.stringify(lockWaitProblem), {
          status: 503,
          headers: { 'Content-Type': 'application/problem+json' },
        })
      );
    });

    await act(async () => {
      root.render(
        <ModelLineageView
          projectId="prj_alpha"
          initialModelId="mod_llama3"
          initialVersion="1.0.0"
          currentUser={{ canApprove: true }}
        />
      );
    });

    const tabs = container.querySelectorAll('button');
    const pinTabBtn = Array.from(tabs).find((b) => b.textContent?.includes('보존 고정'));
    await act(async () => {
      pinTabBtn?.click();
    });

    const untilInput = container.querySelector('[data-testid="input-pin-until"]') as HTMLInputElement;
    await act(async () => {
      const setNative = Object.getOwnPropertyDescriptor(window.HTMLInputElement.prototype, 'value')?.set;
      setNative?.call(untilInput, '2026-12-31T23:59:59Z');
      untilInput.dispatchEvent(new Event('input', { bubbles: true }));
    });

    const pinBtn = container.querySelector('[data-testid="btn-pin-retention"]') as HTMLButtonElement;
    await act(async () => {
      pinBtn.click();
    });

    const alert = container.querySelector('[data-testid="registry-problem-alert"]');
    expect(alert).not.toBeNull();
    expect(alert?.textContent).toContain('(재시도 가능)');
    expect(container.querySelector('[data-testid="problem-code"]')?.textContent).toBe('SYS-0001');
  });

  // 8. Permission Guard: canApprove === false disables write buttons
  it('gates write actions when currentUser.canApprove === false', async () => {
    await act(async () => {
      root.render(
        <ModelLineageView
          projectId="prj_alpha"
          initialModelId="mod_llama3"
          initialVersion="1.0.0-rc1"
          currentUser={{ canApprove: false }}
        />
      );
    });

    // Check Register tab
    const tabs = container.querySelectorAll('button');
    const registerTabBtn = Array.from(tabs).find((b) => b.textContent?.includes('버전 등록'));
    await act(async () => {
      registerTabBtn?.click();
    });

    const registerBtn = container.querySelector('[data-testid="btn-register-version"]') as HTMLButtonElement;
    expect(registerBtn.disabled).toBe(true);
    expect(registerBtn.getAttribute('aria-disabled')).toBe('true');
    expect(container.textContent).toContain('승인 권한(canApprove)이 필요한 작업입니다');
  });

  // 9. Real Lineage with Missing Items & Scope Limitation
  it('renders missing items and traceabilityLimitedByScope correctly', async () => {
    const traceWithMissing: ModelLineageTraceResponse = {
      ...validTraceResponse,
      fullyTraceable: false,
      traceabilityLimitedByScope: true,
      missing: ['dataset:curated-v2', 'commit:abcdef123456'],
      datasets: [],
      deployments: [],
    };

    globalThis.fetch = vi.fn().mockImplementation(() => {
      return Promise.resolve(
        new Response(JSON.stringify(traceWithMissing), {
          status: 200,
          headers: { 'Content-Type': 'application/json' },
        })
      );
    });

    await act(async () => {
      root.render(
        <ModelLineageView
          projectId="prj_alpha"
          initialModelId="mod_llama3"
          initialVersion="1.0.0"
        />
      );
    });

    const queryBtn = container.querySelector('[data-testid="btn-query-lineage"]') as HTMLButtonElement;
    await act(async () => {
      queryBtn.click();
    });

    expect(container.querySelector('[data-testid="badge-fully-traceable"]')?.textContent).toContain(
      '불완전 추적 (Incomplete Trace)'
    );
    expect(container.querySelector('[data-testid="badge-scope-limited"]')?.textContent).toContain(
      '프로젝트 범위 제한 적용'
    );

    const missingSection = container.querySelector('[data-testid="real-lineage-missing"]');
    expect(missingSection?.textContent).toContain('dataset:curated-v2');
    expect(missingSection?.textContent).toContain('commit:abcdef123456');

    // Empty datasets & deployments message
    expect(container.querySelector('[data-testid="real-lineage-datasets"]')?.textContent).toContain(
      '연결된 데이터셋이 없습니다'
    );
    expect(container.querySelector('[data-testid="real-lineage-deployments"]')?.textContent).toContain(
      '배포 내역이 없습니다 (deployments: [])'
    );
  });

  // 10. Live Region Accessibility Updates
  it('updates aria-live region during queries and operations', async () => {
    globalThis.fetch = vi.fn().mockImplementation(() => {
      return Promise.resolve(
        new Response(JSON.stringify(validTraceResponse), {
          status: 200,
          headers: { 'Content-Type': 'application/json' },
        })
      );
    });

    await act(async () => {
      root.render(
        <ModelLineageView
          projectId="prj_alpha"
          initialModelId="mod_llama3"
          initialVersion="1.0.0"
        />
      );
    });

    const liveRegion = container.querySelector('[data-testid="registry-live-region"]');
    expect(liveRegion).not.toBeNull();
    expect(liveRegion?.getAttribute('role')).toBe('status');
    expect(liveRegion?.getAttribute('aria-live')).toBe('polite');

    const queryBtn = container.querySelector('[data-testid="btn-query-lineage"]') as HTMLButtonElement;
    await act(async () => {
      queryBtn.click();
    });

    expect(liveRegion?.textContent).toContain('계보 조회 성공');
  });

  // 11. Anti-Double-Submission: Buttons disabled while request in flight
  it('disables query and write buttons while in-flight to prevent duplicate submission', async () => {
    let resolveQuery: (res: Response) => void;
    const pendingQuery = new Promise<Response>((resolve) => {
      resolveQuery = resolve;
    });

    globalThis.fetch = vi.fn().mockImplementation(() => pendingQuery);

    await act(async () => {
      root.render(
        <ModelLineageView
          projectId="prj_alpha"
          initialModelId="mod_llama3"
          initialVersion="1.0.0"
          currentUser={{ canApprove: true }}
        />
      );
    });

    const queryBtn = container.querySelector('[data-testid="btn-query-lineage"]') as HTMLButtonElement;
    expect(queryBtn.disabled).toBe(false);

    act(() => {
      queryBtn.click();
    });

    // In flight
    expect(queryBtn.disabled).toBe(true);
    expect(queryBtn.textContent).toContain('계보 조회 중');

    // Resolve request
    await act(async () => {
      resolveQuery!(
        new Response(JSON.stringify(validTraceResponse), {
          status: 200,
          headers: { 'Content-Type': 'application/json' },
        })
      );
    });

    expect(queryBtn.disabled).toBe(false);
  });

  // 12. Abort on Unmount
  it('aborts ongoing network request when unmounted', async () => {
    let capturedSignal: AbortSignal | undefined;

    globalThis.fetch = vi.fn().mockImplementation((url, init) => {
      capturedSignal = init?.signal;
      return new Promise(() => {}); // never resolves
    });

    await act(async () => {
      root.render(
        <ModelLineageView
          projectId="prj_alpha"
          initialModelId="mod_llama3"
          initialVersion="1.0.0"
        />
      );
    });

    const queryBtn = container.querySelector('[data-testid="btn-query-lineage"]') as HTMLButtonElement;
    act(() => {
      queryBtn.click();
    });

    expect(capturedSignal?.aborted).toBe(false);

    act(() => {
      root.unmount();
    });

    expect(capturedSignal?.aborted).toBe(true);
  });

  // 13. Runtime Guard Fail-Closed Tests (Schema 1:1 validation)
  it('runtime type guards fail closed on malformed responses', () => {
    // Valid ISO Date check
    expect(isValidIsoDateTime('2026-09-28T12:00:00Z')).toBe(true);
    expect(isValidIsoDateTime('2026-09-28T12:00:00+09:00')).toBe(true);
    expect(isValidIsoDateTime('2026-09-28 12:00:00')).toBe(false); // naive rejected
    expect(isValidIsoDateTime('not-a-date')).toBe(false);

    // Lineage Trace Guard
    expect(isModelLineageTraceResponse(validTraceResponse)).toBe(true);
    expect(isModelLineageTraceResponse({ ...validTraceResponse, stage: 'invalid_stage' })).toBe(false);
    expect(isModelLineageTraceResponse({ ...validTraceResponse, contentSha256: 'short_hex' })).toBe(false);
    expect(isModelLineageTraceResponse({ ...validTraceResponse, datasets: null })).toBe(false);
    expect(isModelLineageTraceResponse({ ...validTraceResponse, deployments: [{ invalid: true }] })).toBe(false);

    // Version Response Guard
    expect(isModelVersionResponse(validVersionResponse)).toBe(true);
    expect(isModelVersionResponse({ ...validVersionResponse, stage: 'released' })).toBe(false); // MUST be draft
    expect(isModelVersionResponse({ ...validVersionResponse, byteSize: -1 })).toBe(false); // MUST be >= 0
    expect(isModelVersionResponse({ ...validVersionResponse, createdAt: 'naive-date' })).toBe(false);

    // Retention Pin Guard
    expect(isRetentionPinResponse(validPinResponse)).toBe(true);
    expect(isRetentionPinResponse({ ...validPinResponse, extended: 'not-bool' })).toBe(false);
    expect(isRetentionPinResponse({ ...validPinResponse, retentionPinnedUntil: 'naive-date' })).toBe(false);

    // Release Guard
    expect(isModelReleaseResponse(validReleaseResponse)).toBe(true);
    expect(isModelReleaseResponse({ ...validReleaseResponse, stage: 'draft' })).toBe(false); // MUST be released
    expect(isModelReleaseResponse({ ...validReleaseResponse, contentSha256: 'xyz' })).toBe(false);

    // Idempotency Key Generator
    const key = generateIdempotencyKey('test');
    expect(key.startsWith('test_')).toBe(true);
    expect(key.length).toBeLessThanOrEqual(128);
    expect(/^[A-Za-z0-9._:-]+$/.test(key)).toBe(true);
  });
});
