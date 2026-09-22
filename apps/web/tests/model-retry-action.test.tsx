// @vitest-environment happy-dom
import React, { act } from 'react';
import { createRoot, Root } from 'react-dom/client';
import { describe, it, expect, vi, beforeEach, afterEach } from 'vitest';
import { RunDetail } from '../src/features/runs/RunDetail';
import * as client from '../src/shared/api/client';
import type { RunItem, ModelRetryPrepareResult, ProblemDetails } from '../src/contracts/types';

(globalThis as any).IS_REACT_ACT_ENVIRONMENT = true;

const failedRun: RunItem = {
  id: 'run_parent_failed_01',
  projectId: 'prj_test_gemini',
  status: 'failed',
  state: 'failed',
  targetNodeId: 'nod_01JABCDEF01',
  createdAt: '2026-09-22T10:00:00Z',
  startedAt: '2026-09-22T10:00:01Z',
  completedAt: '2026-09-22T10:05:00Z',
  resourceRequest: {
    cpuMillis: 1000,
    memoryBytes: 2147483648,
    gpuCount: 1,
  },
};

const mockRetryResult: ModelRetryPrepareResult = {
  rootRunId: 'run_parent_failed_01',
  parentRunId: 'run_parent_failed_01',
  generation: 1,
  run: {
    runId: 'run_child_retry_02',
    tenantId: 'tnt_default',
    projectId: 'prj_test_gemini',
    state: 'planned',
    version: 1,
    attempt: 1,
  },
  placement: {
    runId: 'run_child_retry_02',
    nodeId: 'nod_worker_gpu_03',
    snapshotId: 'snp_frozen_input_001',
    policyVersion: 'model-retry:1',
    leases: [
      {
        leaseId: 'lse_01',
        nodeId: 'nod_worker_gpu_03',
        resourceType: 'cpu',
        amount: 1000,
        expiresAt: '2026-09-22T10:05:30Z',
      },
    ],
  },
  requiresFrozenInputAndApproval: true,
};

describe('RunDetail Model Retry UI Action (Decision #6 6a, Contract 563c54ce)', () => {
  let container: HTMLDivElement;
  let root: Root;

  beforeEach(() => {
    vi.restoreAllMocks();
    container = document.createElement('div');
    document.body.appendChild(container);
    root = createRoot(container);
  });

  afterEach(() => {
    act(() => {
      root.unmount();
    });
    container.remove();
    vi.restoreAllMocks();
  });

  it('Test 1: test_model_retry_button_visibility_terminal_failed_only - Visible ONLY on failed terminal state', async () => {
    // 1) On failed state: button must exist in DOM
    await act(async () => {
      root.render(<RunDetail run={failedRun} onBack={() => {}} />);
    });
    const retryBtn = container.querySelector('[data-testid="model-retry-prepare-btn"]');
    expect(retryBtn).not.toBeNull();
    expect(retryBtn?.textContent).toContain('Model Retry 준비');

    // 2) On non-failed states (succeeded, running, cancelled): button must NOT exist
    const otherStates: RunItem['state'][] = ['succeeded', 'running', 'cancelled', 'scheduled', 'draft'];
    for (const state of otherStates) {
      await act(async () => {
        root.render(<RunDetail run={{ ...failedRun, state, status: state }} onBack={() => {}} />);
      });
      const btn = container.querySelector('[data-testid="model-retry-prepare-btn"]');
      expect(btn).toBeNull();
    }
  });

  it('Test 2: test_model_retry_request_wire_contract_and_headers - Calls POST /v1/projects/{prj}/runs/{parent}/model-retries with Idempotency-Key', async () => {
    let capturedUrl = '';
    let capturedOptions: any = null;

    vi.spyOn(client, 'apiClient').mockImplementation(async (url: string, opts: any) => {
      capturedUrl = url;
      capturedOptions = opts;
      if (url.includes('/model-retries')) {
        return mockRetryResult as any;
      }
      return {} as any;
    });

    await act(async () => {
      root.render(<RunDetail run={failedRun} onBack={() => {}} />);
    });

    const retryBtn = container.querySelector('[data-testid="model-retry-prepare-btn"]') as HTMLButtonElement;
    expect(retryBtn).not.toBeNull();

    await act(async () => {
      retryBtn.click();
    });

    expect(capturedUrl).toBe('/v1/projects/prj_test_gemini/runs/run_parent_failed_01/model-retries');
    expect(capturedOptions?.method).toBe('POST');
    expect(capturedOptions?.idempotencyKey).toBe('model-retry:prj_test_gemini:run_parent_failed_01:1');

    const body = JSON.parse(capturedOptions?.body);
    expect(body.cpuMillis).toBe(1000);
    expect(body.memoryBytes).toBe(2147483648);
    expect(body.gpuCount).toBe(1);
    expect(body.runtime).toBe('container');
    expect(body.policyVersion).toBe('model-retry:1');
    expect(body.ttlSeconds).toBe(30);
  });

  it('Test 3: test_model_retry_button_loading_state - Disables button and displays loading text during preparation', async () => {
    let resolveApi: (val: any) => void;
    const pendingPromise = new Promise((resolve) => {
      resolveApi = resolve;
    });

    vi.spyOn(client, 'apiClient').mockImplementation(async (url: string) => {
      if (url.includes('/model-retries')) {
        return pendingPromise as any;
      }
      return {} as any;
    });

    await act(async () => {
      root.render(<RunDetail run={failedRun} onBack={() => {}} />);
    });

    const retryBtn = container.querySelector('[data-testid="model-retry-prepare-btn"]') as HTMLButtonElement;
    expect(retryBtn.disabled).toBe(false);

    // Click to start request
    act(() => {
      retryBtn.click();
    });

    // In loading state: button disabled, text shows loading
    expect(retryBtn.disabled).toBe(true);
    expect(retryBtn.textContent).toContain('배치 예약 준비 중...');

    // Resolve API request
    await act(async () => {
      resolveApi!(mockRetryResult);
    });

    // Post-completion: button is back to ready or unblocked
    expect(retryBtn.disabled).toBe(false);
  });

  it('Test 4: test_model_retry_success_banner_and_honest_approval_notice - Honest disclosure banner on 201 Created', async () => {
    vi.spyOn(client, 'apiClient').mockImplementation(async (url: string) => {
      if (url.includes('/model-retries')) {
        return mockRetryResult as any;
      }
      return {} as any;
    });

    await act(async () => {
      root.render(<RunDetail run={failedRun} onBack={() => {}} />);
    });

    const retryBtn = container.querySelector('[data-testid="model-retry-prepare-btn"]') as HTMLButtonElement;
    await act(async () => {
      retryBtn.click();
    });

    const successBanner = container.querySelector('[data-testid="model-retry-success-banner"]');
    expect(successBanner).not.toBeNull();
    expect(successBanner?.getAttribute('role')).toBe('status');
    expect(successBanner?.textContent).toContain('Generation 1');
    expect(successBanner?.textContent).toContain('run_child_retry_02');
    expect(successBanner?.textContent).toContain('nod_worker_gpu_03');
    expect(successBanner?.textContent).toContain('배치 예약만 준비됨');
    expect(successBanner?.textContent).toContain('requiresFrozenInputAndApproval: true');
    // Critical honest disclosure invariant
    expect(successBanner?.textContent).toContain('정직 고지');
    expect(successBanner?.textContent).toContain('본 재시도는 자동 실행되지 않으며');
    expect(successBanner?.textContent).toContain('거버넌스 승인 센터(S04)');
  });

  it('Test 5: test_model_retry_child_lineage_metadata_rendering - Renders lineage metadata for root, parent, child, node', async () => {
    vi.spyOn(client, 'apiClient').mockImplementation(async (url: string) => {
      if (url.includes('/model-retries')) {
        return mockRetryResult as any;
      }
      return {} as any;
    });

    await act(async () => {
      root.render(<RunDetail run={failedRun} onBack={() => {}} />);
    });

    const retryBtn = container.querySelector('[data-testid="model-retry-prepare-btn"]') as HTMLButtonElement;
    await act(async () => {
      retryBtn.click();
    });

    const lineageSection = container.querySelector('[data-testid="retry-child-lineage-section"]');
    expect(lineageSection).not.toBeNull();
    expect(lineageSection?.textContent).toContain('루트: run_parent_failed_01');
    expect(lineageSection?.textContent).toContain('부모: run_parent_failed_01');
    expect(lineageSection?.textContent).toContain('Gen 1');
    expect(lineageSection?.textContent).toContain('자식 Run: run_child_retry_02');
    expect(lineageSection?.textContent).toContain('PLANNED');
    expect(lineageSection?.textContent).toContain('노드: nod_worker_gpu_03');
  });

  it('Test 6: test_model_retry_409_conflict_handling - Displays RFC 9457 409 Conflict problem details in alert', async () => {
    const conflictProblem: ProblemDetails = {
      type: 'about:blank',
      title: 'Run State Conflict',
      status: 409,
      code: 'MODEL-0003',
      category: 'RES',
      detail: 'Parent run is not in failed state or active retry exists',
      retryable: false,
      traceId: '0123456789abcdef0123456789abcdef',
      causeRef: null,
      evidenceId: null,
    };

    vi.spyOn(client, 'apiClient').mockImplementation(async (url: string) => {
      if (url.includes('/model-retries')) {
        throw new client.ApiError(conflictProblem);
      }
      return {} as any;
    });

    await act(async () => {
      root.render(<RunDetail run={failedRun} onBack={() => {}} />);
    });

    const retryBtn = container.querySelector('[data-testid="model-retry-prepare-btn"]') as HTMLButtonElement;
    await act(async () => {
      retryBtn.click();
    });

    const errorAlert = container.querySelector('[data-testid="model-retry-error-alert"]');
    expect(errorAlert).not.toBeNull();
    expect(errorAlert?.getAttribute('role')).toBe('alert');
    expect(errorAlert?.textContent).toContain('재시도 충돌 (409 MODEL-0003)');
    expect(errorAlert?.textContent).toContain('부모 Run이 실패 종단 상태가 아니거나');
  });

  it('Test 7: test_model_retry_503_unavailable_handling - Displays 503 Unavailable when scheduler is unconfigured', async () => {
    const unavailProblem: ProblemDetails = {
      type: 'about:blank',
      title: 'Model Retry Unavailable',
      status: 503,
      code: 'MODEL-0002',
      category: 'RES',
      detail: 'Model retry is not configured',
      retryable: true,
      traceId: '0123456789abcdef0123456789abcdef',
      causeRef: null,
      evidenceId: null,
    };

    vi.spyOn(client, 'apiClient').mockImplementation(async (url: string) => {
      if (url.includes('/model-retries')) {
        throw new client.ApiError(unavailProblem);
      }
      return {} as any;
    });

    await act(async () => {
      root.render(<RunDetail run={failedRun} onBack={() => {}} />);
    });

    const retryBtn = container.querySelector('[data-testid="model-retry-prepare-btn"]') as HTMLButtonElement;
    await act(async () => {
      retryBtn.click();
    });

    const errorAlert = container.querySelector('[data-testid="model-retry-error-alert"]');
    expect(errorAlert).not.toBeNull();
    expect(errorAlert?.getAttribute('role')).toBe('alert');
    expect(errorAlert?.textContent).toContain('서비스 이용 불가 (503)');
    expect(errorAlert?.textContent).toContain('제어 평면의 Model Retry 스케줄러가 구성되지 않았거나');
  });

  it('Test 8: test_model_retry_navigation_handlers_triggered - Calls onNavigateApproval and onNavigateRun from banner', async () => {
    const onApprovalMock = vi.fn();
    const onRunMock = vi.fn();

    vi.spyOn(client, 'apiClient').mockImplementation(async (url: string) => {
      if (url.includes('/model-retries')) {
        return mockRetryResult as any;
      }
      return {} as any;
    });

    await act(async () => {
      root.render(
        <RunDetail
          run={failedRun}
          onBack={() => {}}
          onNavigateApproval={onApprovalMock}
          onNavigateRun={onRunMock}
        />
      );
    });

    const retryBtn = container.querySelector('[data-testid="model-retry-prepare-btn"]') as HTMLButtonElement;
    await act(async () => {
      retryBtn.click();
    });

    // Click approval center button
    const approvalBtn = container.querySelector('[data-testid="goto-approval-from-retry-btn"]') as HTMLButtonElement;
    expect(approvalBtn).not.toBeNull();
    await act(async () => {
      approvalBtn.click();
    });
    expect(onApprovalMock).toHaveBeenCalledWith('run_child_retry_02');

    // Click new run detail button
    const runBtn = container.querySelector('[data-testid="goto-child-run-btn"]') as HTMLButtonElement;
    expect(runBtn).not.toBeNull();
    await act(async () => {
      runBtn.click();
    });
    expect(onRunMock).toHaveBeenCalledWith('run_child_retry_02');
  });

  it('Test 9: test_model_retry_disabled_when_resource_specs_unobserved - Disabled with honest label when resource specs missing', async () => {
    const runWithoutResources: RunItem = {
      ...failedRun,
      resourceRequest: undefined,
    };
    await act(async () => {
      root.render(<RunDetail run={runWithoutResources} onBack={() => {}} />);
    });
    const retryBtn = container.querySelector('[data-testid="model-retry-prepare-btn"]') as HTMLButtonElement;
    expect(retryBtn).not.toBeNull();
    expect(retryBtn.disabled).toBe(true);
    expect(retryBtn.textContent).toContain('입력 사양 미관측');
    expect(retryBtn.title).toContain('입력 사양 미관측');
  });
});
