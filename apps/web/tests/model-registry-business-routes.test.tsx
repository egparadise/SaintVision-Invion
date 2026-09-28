// @vitest-environment happy-dom
import React from 'react';
import { describe, it, expect, beforeEach, afterEach, vi } from 'vitest';
import { createRoot, Root } from 'react-dom/client';
import { act } from 'react';
import { ModelLineageView } from '../src/features/mlops/ModelLineageView';
import { isProblemDetails } from '../src/shared/api/client';
import {
  modelRegistryObservation,
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

  // Server exact entity prefixes (ids.py): mdv_, mdl_, dsv_, dpl_, apv_
  // Server exact kind vocabulary (services/lineage.py): dataset_version, deployment, code_commit, container_image, eval_run, approval
  // Server exact kind vocabulary (services/lineage.py): dataset_version, deployment, code_commit, container_image, eval_run, approval
  // Server invariant: fullyTraceable = not missing and not unresolved and not truncated (services/lineage.py:762)
  const validTraceResponse: ModelLineageTraceResponse = {
    modelVersionId: 'mdv_01JABCDEF1234567890ABCDEF',
    version: '1.0.0',
    stage: 'released',
    contentSha256: '0123456789abcdef0123456789abcdef0123456789abcdef0123456789abcdef',
    producedByRunId: 'run_01J9876543210',
    fullyTraceable: false,
    traceabilityLimitedByScope: true,
    detailedKinds: ['dataset_version', 'deployment'],
    countOnlyKinds: ['code_commit', 'container_image', 'eval_run', 'approval'],
    missing: [],
    unresolved: [
      { kind: 'approval', count: 1 },
      { kind: 'code_commit', count: 1 },
      { kind: 'container_image', count: 1 },
      { kind: 'eval_run', count: 2 },
    ],
    datasets: [
      {
        datasetVersionId: 'dsv_01J112233445566778899001',
        version: 'v2.1',
        contentSha256: 'aaaabbbbccccdddd0123456789abcdef0123456789abcdef0123456789abcdef',
        uri: 'inv://datasets/curated-v2@v2.1',
      },
    ],
    deployments: [
      {
        deploymentId: 'dpl_01J998877665544332211001',
        environment: 'pilot',
        status: 'active',
        deployedDigest: '0123456789abcdef0123456789abcdef0123456789abcdef0123456789abcdef',
        deployedAt: '2026-09-28T12:00:00Z',
        approvalId: 'apv_01JLEGALAPPROVE1122334455',
        imageId: null,
      },
    ],
  };

  const validVersionResponse: ModelVersionResponse = {
    modelVersionId: 'mdv_01JNEWREGISTERED001',
    modelId: 'mdl_01JLLAMA30000000000000000',
    version: '1.0.0-rc1',
    stage: 'draft',
    contentSha256: '11112222333344445555666677778888aaaabbbbccccddddeeeeffff00001111',
    byteSize: 1048576,
    uri: 'inv://models/llama3@1.0.0-rc1',
    createdAt: '2026-09-28T14:30:00Z',
  };

  const validPinResponse: RetentionPinResponse = {
    modelVersionId: 'mdv_01JNEWREGISTERED001',
    modelId: 'mdl_01JLLAMA30000000000000000',
    version: '1.0.0-rc1',
    stage: 'draft',
    retentionPinnedUntil: '2026-12-31T23:59:59Z',
    extended: true,
  };

  const validReleaseResponse: ModelReleaseResponse = {
    modelVersionId: 'mdv_01JNEWREGISTERED001',
    modelId: 'mdl_01JLLAMA30000000000000000',
    version: '1.0.0-rc1',
    stage: 'released',
    contentSha256: '11112222333344445555666677778888aaaabbbbccccddddeeeeffff00001111',
  };

  const setInputValue = (input: HTMLInputElement, val: string) => {
    const setNative = Object.getOwnPropertyDescriptor(window.HTMLInputElement.prototype, 'value')?.set;
    setNative?.call(input, val);
    input.dispatchEvent(new Event('input', { bubbles: true }));
    input.dispatchEvent(new Event('change', { bubbles: true }));
  };

  // 1. Lineage Query Success Path & Honest Dynamic Rendering (Claude G1, G5)
  it('queries real GET /lineage route and honestly renders dynamic trace cards with NOT_OBSERVED for unobserved metrics', async () => {
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
          initialModelId="mdl_01JLLAMA30000000000000000"
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
    expect(capturedUrl).toBe('/v1/projects/prj_alpha/models/mdl_01JLLAMA30000000000000000/versions/1.0.0/lineage');

    // Real lineage container must appear
    const realContainer = container.querySelector('[data-testid="real-lineage-container"]');
    expect(realContainer).not.toBeNull();
    expect(realContainer?.textContent).toContain('[1.0.0] 실서버 계보 추적 결과');

    // Incomplete trace and scope limited badges (server invariant: unresolved items exist -> not fully traceable)
    const traceableBadge = container.querySelector('[data-testid="badge-fully-traceable"]');
    expect(traceableBadge?.textContent).toContain('불완전 추적 (Incomplete Trace)');
    const scopeBadge = container.querySelector('[data-testid="badge-scope-limited"]');
    expect(scopeBadge?.textContent).toContain('프로젝트 범위 제한 적용');

    // Datasets Table with real dsv_ prefix
    const datasetsSection = container.querySelector('[data-testid="real-lineage-datasets"]');
    expect(datasetsSection?.textContent).toContain('dsv_01J112233445566778899001');
    expect(datasetsSection?.textContent).toContain('inv://datasets/curated-v2@v2.1');

    // Deployments Table with real dpl_ and apv_ prefix
    const deploymentsSection = container.querySelector('[data-testid="real-lineage-deployments"]');
    expect(deploymentsSection?.textContent).toContain('dpl_01J998877665544332211001');
    expect(deploymentsSection?.textContent).toContain('pilot');
    expect(deploymentsSection?.textContent).toContain('apv_01JLEGALAPPROVE1122334455');

    // Dynamic unobserved rendering from server kinds (Claude G1 & G5)
    const evalUnobserved = container.querySelector('[data-testid="trace-eval_run-unobserved"]');
    expect(evalUnobserved).not.toBeNull();
    expect(evalUnobserved?.textContent).toContain('상세 범위 외 (2건 관측)');
    expect(evalUnobserved?.textContent).toContain('상세 범위 외 (2건 관측)');

    const commitsUnobserved = container.querySelector('[data-testid="trace-code_commit-unobserved"]');
    expect(commitsUnobserved?.textContent).toContain('상세 범위 외 (1건 관측)');

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
          initialModelId="mdl_01JLLAMA30000000000000000"
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
      setInputValue(versionInput, '1.0.0-rc1');
      setInputValue(shaInput, '11112222333344445555666677778888aaaabbbbccccddddeeeeffff00001111');
      setInputValue(byteInput, '1048576');
    });

    const submitBtn = container.querySelector('[data-testid="btn-register-version"]') as HTMLButtonElement;
    expect(submitBtn.disabled).toBe(false);

    await act(async () => {
      submitBtn.click();
    });

    expect(capturedMethod).toBe('POST');
    expect(capturedUrl).toBe('/v1/projects/prj_alpha/models/mdl_01JLLAMA30000000000000000/versions');
    expect(capturedHeaders['idempotency-key']).toBeDefined();
    expect(capturedHeaders['idempotency-key'].length).toBeGreaterThan(5);

    const parsedBody = JSON.parse(capturedBody);
    expect(parsedBody.version).toBe('1.0.0-rc1');
    expect(parsedBody.contentSha256).toBe('11112222333344445555666677778888aaaabbbbccccddddeeeeffff00001111');
    expect(parsedBody.byteSize).toBe(1048576);

    // Verify success banner rendered
    const banner = container.querySelector('[data-testid="registry-register-success"]');
    expect(banner).not.toBeNull();
    expect(banner?.textContent).toContain('모델 버전 등록 완료 (201 Created)');
    expect(banner?.textContent).toContain('mdv_01JNEWREGISTERED001');
  });

  // 3. W4 Retention Pin Route
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
          initialModelId="mdl_01JLLAMA30000000000000000"
          initialVersion="1.0.0-rc1"
          currentUser={{ canApprove: true }}
        />
      );
    });

    const tabs = container.querySelectorAll('button');
    const pinTabBtn = Array.from(tabs).find((b) => b.textContent?.includes('보존 고정'));
    expect(pinTabBtn).toBeDefined();

    await act(async () => {
      pinTabBtn?.click();
    });

    const untilInput = container.querySelector('[data-testid="input-pin-until"]') as HTMLInputElement;
    expect(untilInput).not.toBeNull();

    await act(async () => {
      setInputValue(untilInput, '2026-12-31T23:59:59Z');
    });

    const pinBtn = container.querySelector('[data-testid="btn-pin-retention"]') as HTMLButtonElement;
    expect(pinBtn.disabled).toBe(false);

    await act(async () => {
      pinBtn.click();
    });

    expect(capturedMethod).toBe('POST');
    expect(capturedUrl).toBe('/v1/projects/prj_alpha/models/mdl_01JLLAMA30000000000000000/versions/1.0.0-rc1/retention-pin');
    expect(capturedHeaders['idempotency-key']).toBeDefined();

    const parsedBody = JSON.parse(capturedBody);
    expect(parsedBody.until).toBe('2026-12-31T23:59:59Z');

    const banner = container.querySelector('[data-testid="registry-pin-success"]');
    expect(banner).not.toBeNull();
    expect(banner?.textContent).toContain('보존 고정 판정 완료 (200 OK)');
  });

  // 4. Model Release Route Client (Card 118: Idempotency-Key header enabled)
  it('calls releaseModelVersion via POST /release with Idempotency-Key and parses 200 response', async () => {
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
      } else if (init?.headers) {
        Object.entries(init.headers).forEach(([k, v]) => {
          capturedHeaders[k.toLowerCase()] = String(v);
        });
      }
      return Promise.resolve(
        new Response(JSON.stringify(validReleaseResponse), {
          status: 200,
          headers: { 'Content-Type': 'application/json' },
        })
      );
    });

    const res = await modelRegistryObservation.releaseModelVersion(
      'prj_alpha',
      'mdl_01JLLAMA30000000000000000',
      '1.0.0-rc1',
      { licensePolicy: 'Apache-2.0', classification: 'internal' },
      { idempotencyKey: 'idem_rel_sample_001' }
    );

    expect(capturedMethod).toBe('POST');
    expect(capturedUrl).toBe('/v1/projects/prj_alpha/models/mdl_01JLLAMA30000000000000000/versions/1.0.0-rc1/release');
    // Release consumes Idempotency-Key on server (Card 113 & Card 118)
    expect(capturedHeaders['idempotency-key']).toBe('idem_rel_sample_001');

    const parsedBody = JSON.parse(capturedBody);
    expect(parsedBody.licensePolicy).toBe('Apache-2.0');
    expect(parsedBody.classification).toBe('internal');
    expect(res.version).toBe('1.0.0-rc1');
    expect(res.stage).toBe('released');
  });

  // 5. RFC 9457 Problem Details: 409 Conflict with exact server detail string (Claude G5)
  it('renders RFC 9457 ProblemDetails with exact code, title, detail, and traceId on 409 Conflict', async () => {
    const canonical409Problem = {
      type: 'about:blank',
      title: 'GRAPH-0002',
      status: 409,
      code: 'GRAPH-0002',
      category: 'GRAPH',
      detail: 'The model version is not fully traceable: missing dataset_version',
      retryable: false,
      traceId: '0123456789abcdef0123456789abcdef',
      causeRef: 'mdv_01JNEWREGISTERED001',
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
          initialModelId="mdl_01JLLAMA30000000000000000"
          initialVersion="1.0.0-rc1"
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
      setInputValue(untilInput, '2026-12-31T23:59:59Z');
    });

    const pinBtn = container.querySelector('[data-testid="btn-pin-retention"]') as HTMLButtonElement;
    await act(async () => {
      pinBtn.click();
    });

    const alert = container.querySelector('[data-testid="registry-problem-alert"]');
    expect(alert).not.toBeNull();
    expect(container.querySelector('[data-testid="problem-code"]')?.textContent).toBe('GRAPH-0002');
    expect(alert?.textContent).toContain('GRAPH-0002');
    expect(container.querySelector('[data-testid="problem-detail"]')?.textContent).toBe(
      'The model version is not fully traceable: missing dataset_version'
    );
    expect(container.querySelector('[data-testid="problem-trace-id"]')?.textContent).toContain(
      '0123456789abcdef0123456789abcdef'
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
          initialModelId="mdl_01JLLAMA30000000000000000"
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
      setInputValue(versionInput, '2.0.0');
      setInputValue(shaInput, '00001111222233334444555566667777aaaabbbbccccddddeeeeffff01234567');
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
          initialModelId="mdl_01JLLAMA30000000000000000"
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
      setInputValue(untilInput, '2026-12-31T23:59:59Z');
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

  // 8. Permission Guard: strictly fail-closed when canApprove !== true (Codex F1)
  it('strictly fails closed on all write actions when canApprove is undefined, false, or role-only', async () => {
    // Case A: currentUser is undefined (unauthenticated or no context)
    await act(async () => {
      root.render(
        <ModelLineageView
          projectId="prj_alpha"
          initialModelId="mdl_01JLLAMA30000000000000000"
          initialVersion="1.0.0-rc1"
        />
      );
    });

    expect(container.textContent).toContain('거버넌스 승인 권한(canApprove)이 없어 조회만 가능합니다');

    const tabs = container.querySelectorAll('button');
    const registerTabBtn = Array.from(tabs).find((b) => b.textContent?.includes('버전 등록'));
    const pinTabBtn = Array.from(tabs).find((b) => b.textContent?.includes('보존 고정'));
    const releaseTabBtn = Array.from(tabs).find((b) => b.textContent?.includes('모델 릴리스'));

    // Test Register tab
    await act(async () => {
      registerTabBtn?.click();
    });
    const regBtn = container.querySelector('[data-testid="btn-register-version"]') as HTMLButtonElement;
    expect(regBtn.disabled).toBe(true);
    expect(regBtn.getAttribute('aria-disabled')).toBe('true');

    // Test Pin tab
    await act(async () => {
      pinTabBtn?.click();
    });
    const pinBtn = container.querySelector('[data-testid="btn-pin-retention"]') as HTMLButtonElement;
    expect(pinBtn.disabled).toBe(true);
    expect(pinBtn.getAttribute('aria-disabled')).toBe('true');

    // Test Release tab
    await act(async () => {
      releaseTabBtn?.click();
    });
    const relBtn = container.querySelector('[data-testid="btn-release-model"]') as HTMLButtonElement;
    expect(relBtn.disabled).toBe(true);
    expect(relBtn.getAttribute('aria-disabled')).toBe('true');

    // Case B: currentUser has role: 'owner' but NO canApprove field (role fallback forbidden!)
    await act(async () => {
      root.render(
        <ModelLineageView
          projectId="prj_alpha"
          initialModelId="mdl_01JLLAMA30000000000000000"
          initialVersion="1.0.0-rc1"
          currentUser={{ role: 'owner' } as any}
        />
      );
    });

    const regTabBtnRole = Array.from(container.querySelectorAll('button')).find((b) => b.textContent?.includes('버전 등록'));
    await act(async () => {
      regTabBtnRole?.click();
    });
    const regBtnRole = container.querySelector('[data-testid="btn-register-version"]') as HTMLButtonElement;
    expect(regBtnRole.disabled).toBe(true);
    expect(regBtnRole.getAttribute('aria-disabled')).toBe('true');

    // Case C: currentUser has canApprove: true -> actions enabled
    await act(async () => {
      root.render(
        <ModelLineageView
          projectId="prj_alpha"
          initialModelId="mdl_01JLLAMA30000000000000000"
          initialVersion="1.0.0-rc1"
          currentUser={{ canApprove: true }}
        />
      );
    });

    expect(container.querySelector('[data-testid="banner-no-approve-permission"]')).toBeNull();
  });

  // 9. Real Lineage with Missing Items & Scope Limitation (Server-Consistent)
  it('renders missing items and traceabilityLimitedByScope correctly', async () => {
    // In server services/lineage.py:762-768:
    // traceabilityLimitedByScope = any(kind in unresolved for kind in COUNT_ONLY_KINDS)
    // missing contains kinds from REQUIRED_KINDS not present in by_kind
    const traceWithMissing: ModelLineageTraceResponse = {
      ...validTraceResponse,
      fullyTraceable: false,
      traceabilityLimitedByScope: true,
      missing: ['dataset_version'],
      unresolved: [{ kind: 'code_commit', count: 2 }],
      countOnlyKinds: ['code_commit', 'eval_run'],
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
          initialModelId="mdl_01JLLAMA30000000000000000"
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
    expect(missingSection?.textContent).toContain('dataset_version');

    // Unresolved item from countOnlyKinds
    const codeCommitCard = container.querySelector('[data-testid="trace-code_commit-unobserved"]');
    expect(codeCommitCard?.textContent).toContain('상세 범위 외 (2건 관측)');

    // Empty datasets & deployments message
    expect(container.querySelector('[data-testid="real-lineage-datasets"]')?.textContent).toContain(
      '연결된 데이터셋이 없습니다'
    );
  });

  // 10. ARIA Live Region Updates
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
          initialModelId="mdl_01JLLAMA30000000000000000"
          initialVersion="1.0.0"
        />
      );
    });

    const liveRegion = container.querySelector('[aria-live="polite"]');
    expect(liveRegion).not.toBeNull();

    const queryBtn = container.querySelector('[data-testid="btn-query-lineage"]') as HTMLButtonElement;
    await act(async () => {
      queryBtn.click();
    });

    expect(liveRegion?.textContent).toContain('계보 조회 성공: [1.0.0]');
  });

  // 11. In-flight Double Submission Prevention
  it('disables query and write buttons while in-flight to prevent duplicate submission', async () => {
    let resolveQuery: (res: Response) => void;
    globalThis.fetch = vi.fn().mockImplementation(() => {
      return new Promise<Response>((resolve) => {
        resolveQuery = resolve;
      });
    });

    await act(async () => {
      root.render(
        <ModelLineageView
          projectId="prj_alpha"
          initialModelId="mdl_01JLLAMA30000000000000000"
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

  // 12. Abort on Unmount (Query)
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
          initialModelId="mdl_01JLLAMA30000000000000000"
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

  // 13. Idempotency-Key Stability on Retry & Rotation on Edit (Codex F2, Claude G2)
  it('preserves the exact same Idempotency-Key on retry after failure, and rotates key when inputs change', async () => {
    const capturedKeys: string[] = [];

    globalThis.fetch = vi.fn().mockImplementation((url, init) => {
      if (init?.headers instanceof Headers) {
        capturedKeys.push(init.headers.get('idempotency-key') || '');
      }
      return Promise.resolve(
        new Response(
          JSON.stringify({
            type: 'about:blank',
            title: 'Temporary lock contention',
            status: 503,
            code: 'SYS-0001',
            category: 'SYS',
            detail: 'Locked; retry later.',
            retryable: true,
            traceId: '0123456789abcdef0123456789abcdef',
            causeRef: null,
            evidenceId: null,
          }),
          {
            status: 503,
            headers: { 'Content-Type': 'application/problem+json' },
          }
        )
      );
    });

    await act(async () => {
      root.render(
        <ModelLineageView
          projectId="prj_alpha"
          initialModelId="mdl_01JLLAMA30000000000000000"
          currentUser={{ canApprove: true }}
        />
      );
    });

    // Go to Register Tab
    const tabs = container.querySelectorAll('button');
    const registerTabBtn = Array.from(tabs).find((b) => b.textContent?.includes('버전 등록'));
    await act(async () => {
      registerTabBtn?.click();
    });

    const versionInput = container.querySelector('[data-testid="input-register-version"]') as HTMLInputElement;
    const shaInput = container.querySelector('[data-testid="input-register-sha256"]') as HTMLInputElement;
    await act(async () => {
      setInputValue(versionInput, '3.0.0');
      setInputValue(shaInput, 'aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa');
    });

    const submitBtn = container.querySelector('[data-testid="btn-register-version"]') as HTMLButtonElement;

    // First attempt -> 503
    await act(async () => {
      submitBtn.click();
    });
    expect(capturedKeys.length).toBe(1);
    const firstKey = capturedKeys[0];
    expect(firstKey.length).toBeGreaterThan(10);

    // Retry without changing inputs -> must resend the EXACT same key!
    await act(async () => {
      submitBtn.click();
    });
    expect(capturedKeys.length).toBe(2);
    expect(capturedKeys[1]).toBe(firstKey);

    // Edit an input -> must rotate key!
    await act(async () => {
      setInputValue(versionInput, '3.0.1');
    });

    await act(async () => {
      submitBtn.click();
    });
    expect(capturedKeys.length).toBe(3);
    const secondKey = capturedKeys[2];
    expect(secondKey).not.toBe(firstKey);
    expect(secondKey.length).toBeGreaterThan(10);

    // Retry with changed input -> must preserve secondKey!
    await act(async () => {
      submitBtn.click();
    });
    expect(capturedKeys.length).toBe(4);
    expect(capturedKeys[3]).toBe(secondKey);

    // Change model path -> must rotate to third key!
    const modelInput = container.querySelector('[data-testid="input-model-id"]') as HTMLInputElement;
    await act(async () => {
      setInputValue(modelInput, 'mdl_NEWMODEL00000000000000001');
    });

    await act(async () => {
      submitBtn.click();
    });
    expect(capturedKeys.length).toBe(5);
    const thirdKey = capturedKeys[4];
    expect(thirdKey).not.toBe(secondKey);
    expect(thirdKey).not.toBe(firstKey);

    // Retry with new model path -> must preserve thirdKey!
    await act(async () => {
      submitBtn.click();
    });
    expect(capturedKeys.length).toBe(6);
    expect(capturedKeys[5]).toBe(thirdKey);
  });

  // 14. Calendar Round-Trip & ByteSize Integer Validation (Codex F4, Claude G4)
  it('validates calendar dates strictly and rejects non-integer or negative byteSize before sending', async () => {
    // Leap year calendar validation
    expect(isValidIsoDateTime('2024-02-29T12:00:00Z')).toBe(true); // 2024 is leap year
    expect(isValidIsoDateTime('2025-02-29T12:00:00Z')).toBe(false); // 2025 is not leap year
    expect(isValidIsoDateTime('2026-02-30T12:00:00Z')).toBe(false); // Feb 30 does not exist
    expect(isValidIsoDateTime('2026-04-31T12:00:00Z')).toBe(false); // April has 30 days

    // ByteSize validation in Register UI
    let fetchCalled = false;
    globalThis.fetch = vi.fn().mockImplementation(() => {
      fetchCalled = true;
      return Promise.resolve(new Response('{}', { status: 200 }));
    });

    await act(async () => {
      root.render(
        <ModelLineageView
          projectId="prj_alpha"
          initialModelId="mdl_01JLLAMA30000000000000000"
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
    const byteInput = container.querySelector('[data-testid="input-register-bytesize"]') as HTMLInputElement;
    const submitBtn = container.querySelector('[data-testid="btn-register-version"]') as HTMLButtonElement;

    // Fill valid version and sha first so submit is enabled
    await act(async () => {
      setInputValue(versionInput, '1.0.0-rc1');
      setInputValue(shaInput, '11112222333344445555666677778888aaaabbbbccccddddeeeeffff00001111');
      setInputValue(byteInput, '1024.5');
    });

    expect(submitBtn.disabled).toBe(false);

    await act(async () => {
      submitBtn.click();
    });

    expect(fetchCalled).toBe(false);
    expect(container.textContent).toContain('byteSize는 0 이상의 정수여야 합니다');

    // Test negative byteSize
    await act(async () => {
      setInputValue(byteInput, '-100');
    });

    await act(async () => {
      submitBtn.click();
    });

    expect(fetchCalled).toBe(false);
    expect(container.textContent).toContain('byteSize는 0 이상의 정수여야 합니다');
  });

  // 15. ProblemDetails Status Binding Fail-Closed (Codex F5)
  it('enforces ProblemDetails status binding to HTTP response status', () => {
    const canonical404 = {
      type: 'about:blank',
      title: 'Not Found',
      status: 404,
      code: 'SYS-0004',
      category: 'SYS',
      detail: 'Model not found',
      retryable: false,
      traceId: '0123456789abcdef0123456789abcdef',
      causeRef: null,
      evidenceId: null,
    };

    // When status matches HTTP status -> accepted
    expect(isProblemDetails(canonical404, 404)).toBe(true);

    // When status mismatches HTTP status -> rejected as malformed
    expect(isProblemDetails(canonical404, 403)).toBe(false);
  });

  // 16. Runtime Guard Fail-Closed Tests: additionalProperties: false & Collection Bounds (Codex F3)
  it('runtime type guards strictly enforce additionalProperties: false and collection bounds', () => {
    // 1. Lineage Trace Guard
    expect(isModelLineageTraceResponse(validTraceResponse)).toBe(true);

    // Top-level extra property -> must fail closed
    expect(isModelLineageTraceResponse({ ...validTraceResponse, unknownExtraProperty: 'forbidden' })).toBe(false);

    // Nested dataset extra property -> must fail closed
    expect(
      isModelLineageTraceResponse({
        ...validTraceResponse,
        datasets: [{ ...validTraceResponse.datasets[0], unknownExtra: 'rejected' }],
      })
    ).toBe(false);

    // Nested deployment extra property -> must fail closed
    expect(
      isModelLineageTraceResponse({
        ...validTraceResponse,
        deployments: [{ ...validTraceResponse.deployments[0], unknownExtra: 'rejected' }],
      })
    ).toBe(false);

    // Nested unresolved extra property -> must fail closed
    expect(
      isModelLineageTraceResponse({
        ...validTraceResponse,
        unresolved: [{ kind: 'code_commit', count: 1, unknownExtra: 'rejected' } as any],
      })
    ).toBe(false);

    // Collection bounds
    const overflowDatasets = Array.from({ length: 201 }, (_, i) => ({
      datasetVersionId: `dsv_${i}`,
      version: `v${i}`,
      contentSha256: '0123456789abcdef0123456789abcdef0123456789abcdef0123456789abcdef',
      uri: `inv://ds/${i}`,
    }));
    expect(isModelLineageTraceResponse({ ...validTraceResponse, datasets: overflowDatasets })).toBe(false);

    const overflowDeployments = Array.from({ length: 201 }, (_, i) => ({
      deploymentId: `dpl_${i}`,
      environment: 'pilot',
      status: 'active',
      deployedDigest: '0123456789abcdef0123456789abcdef0123456789abcdef0123456789abcdef',
      deployedAt: '2026-09-28T12:00:00Z',
      approvalId: null,
      imageId: null,
    }));
    expect(isModelLineageTraceResponse({ ...validTraceResponse, deployments: overflowDeployments })).toBe(false);

    const overflowMissing = Array.from({ length: 17 }, (_, i) => `item_${i}`);
    expect(isModelLineageTraceResponse({ ...validTraceResponse, missing: overflowMissing })).toBe(false);

    const overflowUnresolved = Array.from({ length: 17 }, (_, i) => ({ kind: `k_${i}`, count: i + 1 }));
    expect(isModelLineageTraceResponse({ ...validTraceResponse, unresolved: overflowUnresolved })).toBe(false);

    const overflowDetailedKinds = Array.from({ length: 17 }, (_, i) => `kind_${i}`);
    expect(isModelLineageTraceResponse({ ...validTraceResponse, detailedKinds: overflowDetailedKinds })).toBe(false);

    const overflowCountOnlyKinds = Array.from({ length: 17 }, (_, i) => `kind_${i}`);
    expect(isModelLineageTraceResponse({ ...validTraceResponse, countOnlyKinds: overflowCountOnlyKinds })).toBe(false);

    // 2. Version Response Guard
    expect(isModelVersionResponse(validVersionResponse)).toBe(true);
    expect(isModelVersionResponse({ ...validVersionResponse, extraKey: 'bad' })).toBe(false);
    expect(isModelVersionResponse({ ...validVersionResponse, stage: 'released' })).toBe(false); // MUST be draft
    expect(isModelVersionResponse({ ...validVersionResponse, byteSize: -1 })).toBe(false);

    // 3. Retention Pin Guard
    expect(isRetentionPinResponse(validPinResponse)).toBe(true);
    expect(isRetentionPinResponse({ ...validPinResponse, extraKey: 'bad' })).toBe(false);
    expect(isRetentionPinResponse({ ...validPinResponse, extended: 'not-bool' })).toBe(false);

    // 4. Release Guard
    expect(isModelReleaseResponse(validReleaseResponse)).toBe(true);
    expect(isModelReleaseResponse({ ...validReleaseResponse, extraKey: 'bad' })).toBe(false);
    expect(isModelReleaseResponse({ ...validReleaseResponse, stage: 'draft' })).toBe(false); // MUST be released

    // 5. Idempotency Key Generator format
    const key = generateIdempotencyKey('w2');
    expect(key.startsWith('w2_')).toBe(true);
    expect(key.length).toBeLessThanOrEqual(128);
    expect(/^[A-Za-z0-9._:-]+$/.test(key)).toBe(true);
  });

  // 17. Abort on Unmount for Write Operations (Claude G3)
  it('aborts in-flight write operation when component unmounts', async () => {
    let capturedSignal: AbortSignal | undefined;

    globalThis.fetch = vi.fn().mockImplementation((url, init) => {
      capturedSignal = init?.signal;
      return new Promise(() => {}); // never resolves
    });

    await act(async () => {
      root.render(
        <ModelLineageView
          projectId="prj_alpha"
          initialModelId="mdl_01JLLAMA30000000000000000"
          initialVersion="1.0.0-rc1"
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
      setInputValue(versionInput, '4.0.0');
      setInputValue(shaInput, '2222333344445555666677778888aaaabbbbccccddddeeeeffff000011112222');
    });

    const submitBtn = container.querySelector('[data-testid="btn-register-version"]') as HTMLButtonElement;
    act(() => {
      submitBtn.click();
    });

    expect(capturedSignal).toBeDefined();
    expect(capturedSignal?.aborted).toBe(false);

    act(() => {
      root.unmount();
    });

    expect(capturedSignal?.aborted).toBe(true);
  });

  // 18. Pin Idempotency-Key Rotation on Parameter Change (Claude G2)
  it('preserves pin Idempotency-Key across identical retries but rotates upon parameter change', async () => {
    let capturedKeys: string[] = [];

    globalThis.fetch = vi.fn().mockImplementation((url, init) => {
      let key = '';
      if (init?.headers instanceof Headers) {
        key = init.headers.get('Idempotency-Key') || '';
      } else if (init?.headers) {
        key = (init.headers as any)['Idempotency-Key'] || (init.headers as any)['idempotency-key'] || '';
      }
      capturedKeys.push(key);
      return Promise.resolve(
        new Response(
          JSON.stringify({
            type: 'about:blank',
            title: 'Temporary lock contention',
            status: 503,
            code: 'SYS-0001',
            category: 'SYS',
            detail: 'Locked; retry later.',
            retryable: true,
            traceId: '0123456789abcdef0123456789abcdef',
            causeRef: null,
            evidenceId: null,
          }),
          {
            status: 503,
            headers: { 'Content-Type': 'application/problem+json' },
          }
        )
      );
    });

    await act(async () => {
      root.render(
        <ModelLineageView
          projectId="prj_alpha"
          initialModelId="mdl_01JLLAMA30000000000000000"
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
    const pinBtn = container.querySelector('[data-testid="btn-pin-retention"]') as HTMLButtonElement;

    // First submission
    await act(async () => {
      setInputValue(untilInput, '2026-12-31T23:59:59Z');
    });
    await act(async () => {
      pinBtn.click();
    });

    // Second submission with exact same input (retry scenario after failure)
    await act(async () => {
      pinBtn.click();
    });

    // Third submission: change until date
    await act(async () => {
      setInputValue(untilInput, '2027-06-30T23:59:59Z');
    });
    await act(async () => {
      pinBtn.click();
    });

    expect(capturedKeys.length).toBe(3);
    expect(capturedKeys[0]).toBeTruthy();
    // Key 1 and Key 2 should be the same on retry
    expect(capturedKeys[1]).toBe(capturedKeys[0]);
    // Key 3 should rotate because until parameter changed
    expect(capturedKeys[2]).not.toBe(capturedKeys[0]);
    const rotatedUntilKey = capturedKeys[2];

    // Key 4: retry with new until -> must preserve rotatedUntilKey
    await act(async () => {
      pinBtn.click();
    });
    expect(capturedKeys.length).toBe(4);
    expect(capturedKeys[3]).toBe(rotatedUntilKey);

    // Key 5: change model path -> must rotate!
    const modelInput = container.querySelector('[data-testid="input-model-id"]') as HTMLInputElement;
    await act(async () => {
      setInputValue(modelInput, 'mdl_PINROTATEMODEL000000000001');
    });
    await act(async () => {
      pinBtn.click();
    });
    expect(capturedKeys.length).toBe(5);
    expect(capturedKeys[4]).not.toBe(rotatedUntilKey);
    const rotatedModelKey = capturedKeys[4];

    // Key 6: retry with changed model path -> must preserve rotatedModelKey!
    await act(async () => {
      pinBtn.click();
    });
    expect(capturedKeys.length).toBe(6);
    expect(capturedKeys[5]).toBe(rotatedModelKey);

    // Key 7: change version path -> must rotate!
    const versionInput = container.querySelector('[data-testid="input-version"]') as HTMLInputElement;
    await act(async () => {
      setInputValue(versionInput, '2.0.0-pin');
    });
    await act(async () => {
      pinBtn.click();
    });
    expect(capturedKeys.length).toBe(7);
    expect(capturedKeys[6]).not.toBe(rotatedModelKey);
    const rotatedVersionKey = capturedKeys[6];

    // Key 8: retry with changed version path -> must preserve rotatedVersionKey!
    await act(async () => {
      pinBtn.click();
    });
    expect(capturedKeys.length).toBe(8);
    expect(capturedKeys[7]).toBe(rotatedVersionKey);
  });

  // 19. Separate Abort Controllers and Non-stuck Loading across Writes (Claude G3)
  it('releases loading state and ignores stale responses when write operations overlap', async () => {
    let resolveRegister: (res: Response) => void;
    const registerPromise = new Promise<Response>((resolve) => {
      resolveRegister = resolve;
    });

    globalThis.fetch = vi.fn().mockImplementation((url) => {
      const urlStr = String(url);
      if (urlStr.endsWith('/versions')) {
        return registerPromise;
      }
      if (urlStr.endsWith('/retention-pin')) {
        return Promise.resolve(
          new Response(JSON.stringify(validPinResponse), {
            status: 200,
            headers: { 'Content-Type': 'application/json' },
          })
        );
      }
      return Promise.reject(new Error('Unexpected URL'));
    });

    await act(async () => {
      root.render(
        <ModelLineageView
          projectId="prj_alpha"
          initialModelId="mdl_01JLLAMA30000000000000000"
          initialVersion="1.0.0"
          currentUser={{ canApprove: true }}
        />
      );
    });

    // 1. Start Register operation (will be delayed in-flight)
    const tabs = container.querySelectorAll('button');
    const registerTabBtn = Array.from(tabs).find((b) => b.textContent?.includes('버전 등록'));
    await act(async () => {
      registerTabBtn?.click();
    });

    const versionInput = container.querySelector('[data-testid="input-register-version"]') as HTMLInputElement;
    const shaInput = container.querySelector('[data-testid="input-register-sha256"]') as HTMLInputElement;
    await act(async () => {
      setInputValue(versionInput, '2.0.0-rc1');
      setInputValue(shaInput, '00001111222233334444555566667777aaaabbbbccccddddeeeeffff01234567');
    });

    const regBtn = container.querySelector('[data-testid="btn-register-version"]') as HTMLButtonElement;
    act(() => {
      regBtn.click();
    });

    // Register is now in-flight
    expect(regBtn.textContent).toContain('등록 중...');
    expect(regBtn.disabled).toBe(true);

    // 2. While Register is in-flight, change an input (invalidates currentGen)
    await act(async () => {
      setInputValue(versionInput, '2.0.0-final');
    });

    // 3. Switch to Pin tab and submit Pin
    const pinTabBtn = Array.from(tabs).find((b) => b.textContent?.includes('보존 고정'));
    await act(async () => {
      pinTabBtn?.click();
    });

    const untilInput = container.querySelector('[data-testid="input-pin-until"]') as HTMLInputElement;
    await act(async () => {
      setInputValue(untilInput, '2026-12-31T23:59:59Z');
    });

    const pinBtn = container.querySelector('[data-testid="btn-pin-retention"]') as HTMLButtonElement;
    await act(async () => {
      pinBtn.click();
    });

    // Pin should succeed
    expect(container.querySelector('[data-testid="registry-pin-success"]')).not.toBeNull();

    // 4. Switch back to Register tab: Register button must NOT be permanently stuck! (Claude G3)
    await act(async () => {
      registerTabBtn?.click();
    });

    const regBtnAfterPin = container.querySelector('[data-testid="btn-register-version"]') as HTMLButtonElement;

    // Resolve the delayed in-flight register response
    await act(async () => {
      resolveRegister!(
        new Response(
          JSON.stringify({
            ...validVersionResponse,
            modelVersionId: 'mdv_STALE_OVERWRITE',
            version: '2.0.0-rc1',
          }),
          { status: 201, headers: { 'Content-Type': 'application/json' } }
        )
      );
    });

    // Stale register response must NOT overwrite DOM with success banner (since version was changed)
    // AND register button must NOT remain stuck in loading!
    expect(regBtnAfterPin.disabled).toBe(false);
    expect(regBtnAfterPin.textContent).toContain('모델 버전 등록');
    expect(container.querySelector('[data-testid="registry-register-success"]')).toBeNull();
  });

  // 20. Release Write UI Re-exposed (Card 118: Server Idempotency Contract Active)
  it('re-exposes release write UI with enabled submit button and Idempotency-Key lifecycle', async () => {
    let capturedHeaders: Record<string, string>[] = [];
    globalThis.fetch = vi.fn().mockImplementation((url, init) => {
      const h: Record<string, string> = {};
      if (init?.headers instanceof Headers) {
        init.headers.forEach((v, k) => {
          h[k.toLowerCase()] = v;
        });
      } else if (init?.headers) {
        Object.entries(init.headers).forEach(([k, v]) => {
          h[k.toLowerCase()] = String(v);
        });
      }
      capturedHeaders.push(h);
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
          initialModelId="mdl_01JLLAMA30000000000000000"
          initialVersion="1.0.0-rc1"
          currentUser={{ canApprove: true }}
        />
      );
    });

    const tabs = container.querySelectorAll('button');
    const releaseTabBtn = Array.from(tabs).find((b) => b.textContent?.includes('모델 릴리스'));
    expect(releaseTabBtn).toBeDefined();
    await act(async () => {
      releaseTabBtn?.click();
    });

    // 1. Release button must be enabled and pending banner must be absent
    const releaseBtn = container.querySelector('[data-testid="btn-release-model"]') as HTMLButtonElement;
    expect(releaseBtn).not.toBeNull();
    expect(releaseBtn.disabled).toBe(false);
    expect(releaseBtn.textContent).toContain('모델 릴리스 (POST /release)');
    expect(container.querySelector('[data-testid="banner-release-pending-idempotency"]')).toBeNull();

    // 2. Submit release and verify Idempotency-Key header is sent
    await act(async () => {
      releaseBtn.click();
    });

    expect(capturedHeaders.length).toBe(1);
    const firstKey = capturedHeaders[0]['idempotency-key'];
    expect(firstKey).toBeDefined();
    expect(firstKey).toMatch(/^rel_/);

    // 3. Verify success card and fresh release indicator
    const successCard = container.querySelector('[data-testid="registry-release-success"]');
    expect(successCard).not.toBeNull();
    expect(successCard?.textContent).toContain('모델 릴리스 완료 (200 OK)');
    const indicator = container.querySelector('[data-testid="release-replay-indicator"]');
    expect(indicator?.textContent).toBe('신규 릴리스 완료 (Fresh)');

    // 4. On subsequent submit after success, key must rotate to a new intent
    await act(async () => {
      releaseBtn.click();
    });
    expect(capturedHeaders.length).toBe(2);
    const secondKey = capturedHeaders[1]['idempotency-key'];
    expect(secondKey).toBeDefined();
    expect(secondKey).not.toBe(firstKey);
  });

  // 21. Release Idempotency-Key Preservation Across Failures and Replay Indication
  it('preserves Idempotency-Key on failure retry and distinguishes replay response', async () => {
    let capturedHeaders: Record<string, string>[] = [];
    let callCount = 0;

    globalThis.fetch = vi.fn().mockImplementation(() => {
      callCount++;
      if (callCount === 1) {
        // First attempt fails with 503 transient lock
        return Promise.resolve(
          new Response(
            JSON.stringify({
              type: 'about:blank',
              title: 'SYS-0001',
              status: 503,
              code: 'SYS-0001',
              category: 'SYS',
              detail: 'The resource is locked by another request; retry.',
              retryable: true,
            }),
            { status: 503, headers: { 'Content-Type': 'application/problem+json' } }
          )
        );
      }
      // Second attempt succeeds
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
          initialModelId="mdl_01JLLAMA30000000000000000"
          initialVersion="1.0.0-rc1"
          currentUser={{ canApprove: true }}
        />
      );
    });

    const releaseTabBtn = Array.from(container.querySelectorAll('button')).find((b) =>
      b.textContent?.includes('모델 릴리스')
    );
    await act(async () => {
      releaseTabBtn?.click();
    });

    const releaseBtn = container.querySelector('[data-testid="btn-release-model"]') as HTMLButtonElement;

    // First attempt fails
    await act(async () => {
      releaseBtn.click();
    });

    expect(container.querySelector('[data-testid="registry-problem-alert"]')).not.toBeNull();
    expect(container.querySelector('[data-testid="registry-release-success"]')).toBeNull();

    function extractIdempotencyKey(init: any): string | null {
      if (init?.headers instanceof Headers) {
        return init.headers.get('idempotency-key') || init.headers.get('Idempotency-Key');
      }
      if (init?.headers) {
        return init.headers['Idempotency-Key'] || init.headers['idempotency-key'] || null;
      }
      return null;
    }

    // Now inspect fetch calls for idempotency-key preservation
    const fetchCalls = (globalThis.fetch as any).mock.calls;
    expect(fetchCalls.length).toBe(1);
    const key1 = extractIdempotencyKey(fetchCalls[0][1]);
    expect(key1).not.toBeNull();
    expect(key1).toMatch(/^rel_/);

    // Retry submission without changing inputs: MUST reuse identical key
    await act(async () => {
      releaseBtn.click();
    });

    expect(fetchCalls.length).toBe(2);
    const key2 = extractIdempotencyKey(fetchCalls[1][1]);
    expect(key2).toBe(key1); // Preserved on retry!

    // Second attempt succeeded
    expect(container.querySelector('[data-testid="registry-release-success"]')).not.toBeNull();

    // M1 Invariant: replay response must NOT be displayed as fresh release
    const replayIndicator = container.querySelector('[data-testid="release-replay-indicator"]');
    expect(replayIndicator).not.toBeNull();
    expect(replayIndicator?.textContent).not.toBe('신규 릴리스 완료 (Fresh)');
    expect(replayIndicator?.textContent).toContain('재시도 응답 — 서버 원장 결과');
  });

  // 22. Release Idempotency-Key Rotation on Input Changes
  it('rotates release Idempotency-Key when licensePolicy or classification changes', async () => {
    function extractIdempotencyKey(init: any): string | null {
      if (init?.headers instanceof Headers) {
        return init.headers.get('idempotency-key') || init.headers.get('Idempotency-Key');
      }
      if (init?.headers) {
        return init.headers['Idempotency-Key'] || init.headers['idempotency-key'] || null;
      }
      return null;
    }

    globalThis.fetch = vi.fn().mockResolvedValue(
      new Response(JSON.stringify(validReleaseResponse), {
        status: 200,
        headers: { 'Content-Type': 'application/json' },
      })
    );

    await act(async () => {
      root.render(
        <ModelLineageView
          projectId="prj_alpha"
          initialModelId="mdl_01JLLAMA30000000000000000"
          initialVersion="1.0.0-rc1"
          currentUser={{ canApprove: true }}
        />
      );
    });

    const releaseTabBtn = Array.from(container.querySelectorAll('button')).find((b) =>
      b.textContent?.includes('모델 릴리스')
    );
    await act(async () => {
      releaseTabBtn?.click();
    });

    const releaseBtn = container.querySelector('[data-testid="btn-release-model"]') as HTMLButtonElement;
    await act(async () => {
      releaseBtn.click();
    });

    const fetchCalls = (globalThis.fetch as any).mock.calls;
    const initialKey = extractIdempotencyKey(fetchCalls[0][1]);
    expect(initialKey).not.toBeNull();

    // Change licensePolicy input
    const licenseInput = container.querySelector('#input-release-license') as HTMLInputElement;
    await act(async () => {
      setInputValue(licenseInput, 'MIT');
    });

    await act(async () => {
      releaseBtn.click();
    });

    expect(fetchCalls.length).toBe(2);
    const changedKey = extractIdempotencyKey(fetchCalls[1][1]);
    expect(changedKey).not.toBeNull();
    expect(changedKey).not.toBe(initialKey);

    // L1: Change classification select
    const classificationSelect = container.querySelector('#select-release-classification') as HTMLSelectElement;
    await act(async () => {
      classificationSelect.value = 'public';
      classificationSelect.dispatchEvent(new Event('change', { bubbles: true }));
    });

    await act(async () => {
      releaseBtn.click();
    });

    expect(fetchCalls.length).toBe(3);
    const classificationKey = extractIdempotencyKey(fetchCalls[2][1]);
    expect(classificationKey).not.toBeNull();
    expect(classificationKey).not.toBe(changedKey);
    expect(classificationKey).not.toBe(initialKey);
  });

  // 23. Fail-Closed Release Authorization Guard
  it('disables release submit button when canApprove is false or undefined', async () => {
    globalThis.fetch = vi.fn().mockImplementation(() =>
      Promise.reject(new Error('Network should not be reached'))
    );

    await act(async () => {
      root.render(
        <ModelLineageView
          projectId="prj_alpha"
          initialModelId="mdl_01JLLAMA30000000000000000"
          initialVersion="1.0.0-rc1"
          currentUser={{ canApprove: false }}
        />
      );
    });

    const releaseTabBtn = Array.from(container.querySelectorAll('button')).find((b) =>
      b.textContent?.includes('모델 릴리스')
    );
    await act(async () => {
      releaseTabBtn?.click();
    });

    const releaseBtn = container.querySelector('[data-testid="btn-release-model"]') as HTMLButtonElement;
    expect(releaseBtn.disabled).toBe(true);
    expect(container.textContent).toContain('승인 권한(canApprove)이 필요한 작업입니다.');

    const form = releaseBtn.closest('form');
    await act(async () => {
      form?.dispatchEvent(new Event('submit', { bubbles: true, cancelable: true }));
    });

    // Zero calls to /release
    expect((globalThis.fetch as any).mock.calls.length).toBe(0);
    expect(container.querySelector('[role="alert"]')?.textContent).toContain('승인 권한(canApprove)이 없는 계정은 모델을 릴리스할 수 없습니다.');

    // L2: Re-render with canApprove undefined (must also fail closed)
    await act(async () => {
      root.render(
        <ModelLineageView
          projectId="prj_alpha"
          initialModelId="mdl_01JLLAMA30000000000000000"
          initialVersion="1.0.0-rc1"
          currentUser={{ canApprove: undefined }}
        />
      );
    });

    const releaseTabBtn2 = Array.from(container.querySelectorAll('button')).find((b) =>
      b.textContent?.includes('모델 릴리스')
    );
    await act(async () => {
      releaseTabBtn2?.click();
    });

    const releaseBtn2 = container.querySelector('[data-testid="btn-release-model"]') as HTMLButtonElement;
    expect(releaseBtn2.disabled).toBe(true);
    expect(container.textContent).toContain('승인 권한(canApprove)이 필요한 작업입니다.');
  });

  // 24. Release Loading State & In-Flight Abort on Input Change (L3 / N1 pattern)
  it('aborts in-flight release request and unlocks button when input changes during submission', async () => {
    let resolveFirstCall: (res: any) => void;
    let signalAborted = false;

    globalThis.fetch = vi.fn().mockImplementation((_url, init) => {
      init.signal?.addEventListener('abort', () => {
        signalAborted = true;
      });
      return new Promise((resolve) => {
        resolveFirstCall = resolve;
      });
    });

    await act(async () => {
      root.render(
        <ModelLineageView
          projectId="prj_alpha"
          initialModelId="mdl_01JLLAMA30000000000000000"
          initialVersion="1.0.0-rc1"
          currentUser={{ canApprove: true }}
        />
      );
    });

    const releaseTabBtn = Array.from(container.querySelectorAll('button')).find((b) =>
      b.textContent?.includes('모델 릴리스')
    );
    await act(async () => {
      releaseTabBtn?.click();
    });

    const releaseBtn = container.querySelector('[data-testid="btn-release-model"]') as HTMLButtonElement;
    expect(releaseBtn.disabled).toBe(false);

    // 1. Trigger release submission (in-flight)
    await act(async () => {
      releaseBtn.click();
    });
    expect(releaseBtn.disabled).toBe(true);
    expect(releaseBtn.textContent).toContain('릴리스 중...');

    // 2. Change licensePolicy input while request is in-flight
    const licenseInput = container.querySelector('#input-release-license') as HTMLInputElement;
    await act(async () => {
      setInputValue(licenseInput, 'Apache-2.0-Modified');
    });

    // In-flight request MUST be aborted and loading flag cleared
    expect(signalAborted).toBe(true);
    expect(releaseBtn.disabled).toBe(false);
    expect(releaseBtn.textContent).toContain('모델 릴리스 (POST /release)');

    // 3. Late resolution of old request must be discarded without showing success card
    await act(async () => {
      resolveFirstCall!(
        new Response(JSON.stringify(validReleaseResponse), {
          status: 200,
          headers: { 'Content-Type': 'application/json' },
        })
      );
    });
    expect(container.querySelector('[data-testid="registry-release-success"]')).toBeNull();
  });

});
