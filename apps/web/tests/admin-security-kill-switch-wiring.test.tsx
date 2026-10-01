// @vitest-environment happy-dom
// @ts-ignore
globalThis.IS_REACT_ACT_ENVIRONMENT = true;
import React, { act } from 'react';
import { createRoot, Root } from 'react-dom/client';
import { describe, it, expect, vi, beforeEach, afterEach } from 'vitest';
import { AdminSecurityConsole } from '../src/features/admin/AdminSecurityConsole';
import * as client from '../src/shared/api/client';
import type { NodeItem, ContainmentView, ContainmentResult } from '../src/contracts/types';

const MOCK_NODES: NodeItem[] = [
  {
    id: 'nod_sec_01',
    hostname: 'node-gpu-01',
    os: 'linux',
    cpuCores: 32,
    cpuUsagePercent: 15,
    memoryTotalBytes: 128 * 1024 ** 3,
    memoryUsagePercent: 25,
    gpuName: 'NVIDIA RTX 4090',
    gpuCount: 2,
    status: 'online',
    labels: { tier: 'gpu' },
  },
];

const VALID_INACTIVE_VIEW: ContainmentView = {
  nodeId: null,
  version: 5,
  killSwitchActive: false,
  nodeStatus: 'online',
  activeLeases: 0,
  pendingDeliveries: 0,
  unsettledRuns: 0,
  settled: true,
};

const VALID_ACTIVE_VIEW: ContainmentView = {
  nodeId: null,
  version: 8,
  killSwitchActive: true,
  nodeStatus: 'quarantined',
  activeLeases: 0,
  pendingDeliveries: 0,
  unsettledRuns: 0,
  settled: true,
};

describe('AdminSecurityConsole Emergency Kill Switch Real Backend Wiring Tests (Card 169)', () => {
  let container: HTMLDivElement;
  let root: Root;

  beforeEach(() => {
    container = document.createElement('div');
    document.body.appendChild(container);
    root = createRoot(container);
    vi.restoreAllMocks();
  });

  afterEach(() => {
    act(() => {
      root.unmount();
    });
    container.remove();
    vi.restoreAllMocks();
  });

  it('비상 정지가 비활성 상태일 때 긴급 발동 확정 시 POST /v1/operations/kill-switch (202 Accepted)와 Idempotency-Key, expectedVersion, reasonCode, approvalId를 전송하고 활성 상태로 갱신한다', async () => {
    let capturedEndpoint: string | null = null;
    let capturedOptions: any = null;
    let observedResponseStatus: number | null = null;

    vi.spyOn(client, 'apiClient').mockImplementation(async (endpoint: string, options?: any) => {
      if (endpoint === '/v1/operations/kill-switch' && (!options || options.method === 'GET')) {
        return VALID_INACTIVE_VIEW as any;
      }
      if (endpoint === '/v1/operations/kill-switch' && options?.method === 'POST') {
        capturedEndpoint = endpoint;
        capturedOptions = options;
        observedResponseStatus = 202; // app.py:400 @api.post("/v1/operations/kill-switch", status_code=202)
        const res: ContainmentResult = {
          requestId: 'req-00000000-0000-4000-8000-000000000001',
          operation: 'kill',
          approvalId: '11111111-2222-4333-8444-555555555555',
          control: {
            nodeId: null,
            version: 6,
            killSwitchActive: true,
            nodeStatus: 'online',
            activeLeases: 0,
            pendingDeliveries: 0,
            unsettledRuns: 0,
            settled: true,
          },
        };
        return res as any;
      }
      return {} as any;
    });

    await act(async () => {
      root.render(
        <AdminSecurityConsole
          nodes={MOCK_NODES}
          currentUser={{ id: 'usr_sec_admin', name: 'Sec Admin', role: 'admin' }}
        />
      );
    });

    const backendStatus = container.querySelector('[data-testid="backend-kill-switch-status"]');
    expect(backendStatus?.textContent).toContain('INACTIVE (v5)');

    // 1. 헤더에서 사유 코드와 승인 ID 변경
    const reasonSelect = container.querySelector('[data-testid="kill-switch-reason-select"]') as HTMLSelectElement;
    await act(async () => {
      reasonSelect.value = 'incident';
      reasonSelect.dispatchEvent(new Event('change', { bubbles: true }));
    });

    const approvalInput = container.querySelector('[data-testid="input-kill-switch-approval-id"]') as HTMLInputElement;
    await act(async () => {
      const nativeSetter = Object.getOwnPropertyDescriptor(window.HTMLInputElement.prototype, 'value')?.set;
      nativeSetter?.call(approvalInput, '11111111-2222-4333-8444-555555555555');
      approvalInput.dispatchEvent(new Event('input', { bubbles: true }));
      approvalInput.dispatchEvent(new Event('change', { bubbles: true }));
    });

    // 2. 모달 열기
    const toggleBtn = container.querySelector('[data-testid="emergency-kill-switch-toggle-btn"]') as HTMLButtonElement;
    await act(async () => {
      toggleBtn.click();
    });

    const confirmBtn = container.querySelector('[data-testid="kill-switch-confirm-btn"]') as HTMLButtonElement;
    expect(confirmBtn.disabled).toBe(false);

    // 3. 비상 정지 발동 확정
    await act(async () => {
      confirmBtn.click();
    });

    expect(capturedEndpoint).toBe('/v1/operations/kill-switch');
    expect(observedResponseStatus).toBe(202);
    expect(capturedOptions.method).toBe('POST');
    expect(capturedOptions.headers['Idempotency-Key']).toMatch(/^killswitch_/);

    const sentPayload = JSON.parse(capturedOptions.body);
    expect(sentPayload).toEqual({
      expectedVersion: 5,
      reasonCode: 'incident',
      approvalId: '11111111-2222-4333-8444-555555555555',
    });

    expect(container.querySelector('[data-testid="kill-switch-modal"]')).toBeNull();
    const activeBanner = container.querySelector('[data-testid="kill-switch-active-banner"]');
    expect(activeBanner).not.toBeNull();
    expect(backendStatus?.textContent).toContain('ACTIVE (v6)');
  });

  it('비상 정지가 활성 상태일 때 해제 실행 시 POST /v1/operations/kill-switch/clear (200 OK)를 호출하고 비활성 상태로 복귀한다', async () => {
    let capturedEndpoint: string | null = null;
    let capturedOptions: any = null;
    let observedResponseStatus: number | null = null;

    vi.spyOn(client, 'apiClient').mockImplementation(async (endpoint: string, options?: any) => {
      if (endpoint === '/v1/operations/kill-switch' && (!options || options.method === 'GET')) {
        return VALID_ACTIVE_VIEW as any;
      }
      if (endpoint === '/v1/operations/kill-switch/clear' && options?.method === 'POST') {
        capturedEndpoint = endpoint;
        capturedOptions = options;
        observedResponseStatus = 200; // app.py:412 @api.post("/v1/operations/kill-switch/clear") default status 200
        const res: ContainmentResult = {
          requestId: 'req-00000000-0000-4000-8000-000000000002',
          operation: 'clear',
          approvalId: '22222222-3333-4444-8555-666666666666',
          control: {
            nodeId: null,
            version: 9,
            killSwitchActive: false,
            nodeStatus: 'online',
            activeLeases: 0,
            pendingDeliveries: 0,
            unsettledRuns: 0,
            settled: true,
          },
        };
        return res as any;
      }
      return {} as any;
    });

    await act(async () => {
      root.render(
        <AdminSecurityConsole
          nodes={MOCK_NODES}
          currentUser={{ id: 'usr_sec_admin', name: 'Sec Admin', role: 'admin' }}
        />
      );
    });

    const backendStatus = container.querySelector('[data-testid="backend-kill-switch-status"]');
    expect(backendStatus?.textContent).toContain('ACTIVE (v8)');

    // 승인 ID 입력
    const approvalInput = container.querySelector('[data-testid="input-kill-switch-approval-id"]') as HTMLInputElement;
    await act(async () => {
      const nativeSetter = Object.getOwnPropertyDescriptor(window.HTMLInputElement.prototype, 'value')?.set;
      nativeSetter?.call(approvalInput, '22222222-3333-4444-8555-666666666666');
      approvalInput.dispatchEvent(new Event('input', { bubbles: true }));
      approvalInput.dispatchEvent(new Event('change', { bubbles: true }));
    });

    const toggleBtn = container.querySelector('[data-testid="emergency-kill-switch-toggle-btn"]') as HTMLButtonElement;
    await act(async () => {
      toggleBtn.click();
    });

    const confirmBtn = container.querySelector('[data-testid="kill-switch-confirm-btn"]') as HTMLButtonElement;
    expect(confirmBtn.textContent).toContain('해제 실행');
    expect(confirmBtn.disabled).toBe(false);

    await act(async () => {
      confirmBtn.click();
    });

    expect(capturedEndpoint).toBe('/v1/operations/kill-switch/clear');
    expect(observedResponseStatus).toBe(200);
    const sentPayload = JSON.parse(capturedOptions.body);
    expect(sentPayload).toEqual({
      expectedVersion: 8,
      reasonCode: 'operator_request',
      approvalId: '22222222-3333-4444-8555-666666666666',
    });

    expect(container.querySelector('[data-testid="kill-switch-active-banner"]')).toBeNull();
    expect(backendStatus?.textContent).toContain('INACTIVE (v9)');
  });

  // =========================================================================
  // Review Point (1): GET ContainmentView 계약 검증 실패 / 로딩 시 쓰기 비활성화 (fail-closed)
  // =========================================================================
  it('GET /v1/operations/kill-switch 응답이 부분 응답이거나 필수 필드(version 등) 누락 시 오류를 표시하고 확정 버튼을 비활성화한다 (fail-closed)', async () => {
    vi.spyOn(client, 'apiClient').mockImplementation(async (endpoint: string) => {
      if (endpoint === '/v1/operations/kill-switch') {
        // version 및 canonical 필드 누락 부분 응답
        return { killSwitchActive: false } as any;
      }
      return {} as any;
    });

    await act(async () => {
      root.render(
        <AdminSecurityConsole
          nodes={MOCK_NODES}
          currentUser={{ id: 'usr_sec_admin', name: 'Sec Admin', role: 'admin' }}
        />
      );
    });

    const backendStatus = container.querySelector('[data-testid="backend-kill-switch-status"]');
    expect(backendStatus?.textContent).toContain('조회 실패 [응답 형식 불일치]');

    // 유효한 UUID를 입력하더라도
    const approvalInput = container.querySelector('[data-testid="input-kill-switch-approval-id"]') as HTMLInputElement;
    await act(async () => {
      const nativeSetter = Object.getOwnPropertyDescriptor(window.HTMLInputElement.prototype, 'value')?.set;
      nativeSetter?.call(approvalInput, '550e8400-e29b-41d4-a716-446655440000');
      approvalInput.dispatchEvent(new Event('input', { bubbles: true }));
      approvalInput.dispatchEvent(new Event('change', { bubbles: true }));
    });

    const toggleBtn = container.querySelector('[data-testid="emergency-kill-switch-toggle-btn"]') as HTMLButtonElement;
    await act(async () => {
      toggleBtn.click();
    });

    // 모달 내부 경고 배너 확인
    const unreadyNotice = container.querySelector('[data-testid="kill-switch-backend-unready-notice"]');
    expect(unreadyNotice).not.toBeNull();
    expect(unreadyNotice?.textContent).toContain('비상 정지 변경이 비활성화되었습니다');

    // 확정 버튼은 반드시 비활성화되어야 함
    const confirmBtn = container.querySelector('[data-testid="kill-switch-confirm-btn"]') as HTMLButtonElement;
    expect(confirmBtn.disabled).toBe(true);
    expect(confirmBtn.getAttribute('aria-disabled')).toBe('true');
  });

  // =========================================================================
  // Review Point (2): POST 응답 정본 shape 검증 실패 시 오류 표출, 상태 미변경, 재조회
  // =========================================================================
  it('POST 응답에 control이 누락되거나 위장된 경우(빈 응답 {}) 상태를 합성하지 않고 오류를 표시하며 재조회한다', async () => {
    let getCallCount = 0;
    vi.spyOn(client, 'apiClient').mockImplementation(async (endpoint: string, options?: any) => {
      if (endpoint === '/v1/operations/kill-switch' && (!options || options.method === 'GET')) {
        getCallCount++;
        return VALID_INACTIVE_VIEW as any;
      }
      if (endpoint === '/v1/operations/kill-switch' && options?.method === 'POST') {
        // 위장: control 누락 빈 객체
        return {} as any;
      }
      return {} as any;
    });

    await act(async () => {
      root.render(
        <AdminSecurityConsole
          nodes={MOCK_NODES}
          currentUser={{ id: 'usr_sec_admin', name: 'Sec Admin', role: 'admin' }}
        />
      );
    });

    expect(getCallCount).toBe(1);

    const approvalInput = container.querySelector('[data-testid="input-kill-switch-approval-id"]') as HTMLInputElement;
    await act(async () => {
      const nativeSetter = Object.getOwnPropertyDescriptor(window.HTMLInputElement.prototype, 'value')?.set;
      nativeSetter?.call(approvalInput, '550e8400-e29b-41d4-a716-446655440000');
      approvalInput.dispatchEvent(new Event('input', { bubbles: true }));
      approvalInput.dispatchEvent(new Event('change', { bubbles: true }));
    });

    const toggleBtn = container.querySelector('[data-testid="emergency-kill-switch-toggle-btn"]') as HTMLButtonElement;
    await act(async () => {
      toggleBtn.click();
    });

    const confirmBtn = container.querySelector('[data-testid="kill-switch-confirm-btn"]') as HTMLButtonElement;
    await act(async () => {
      confirmBtn.click();
    });

    // 상태 미변경 단언: 여전히 모달이 열려있고 상단 활성 배너는 미표출
    expect(container.querySelector('[data-testid="kill-switch-active-banner"]')).toBeNull();
    const errorBanner = container.querySelector('[data-testid="kill-switch-error-banner"]');
    expect(errorBanner?.textContent).toContain('[CONTRACT-MISMATCH]');

    // 재조회 호출 실측 (GET이 다시 호출됨)
    expect(getCallCount).toBe(2);
  });

  it('POST 응답의 operation이 요청 의도와 불일치하거나 killSwitchActive가 모순된 경우 계약 불일치로 거부한다', async () => {
    vi.spyOn(client, 'apiClient').mockImplementation(async (endpoint: string, options?: any) => {
      if (endpoint === '/v1/operations/kill-switch' && (!options || options.method === 'GET')) {
        return VALID_INACTIVE_VIEW as any;
      }
      if (endpoint === '/v1/operations/kill-switch' && options?.method === 'POST') {
        // kill 요청인데 operation이 clear로 오거나 killSwitchActive가 false인 모순
        return {
          requestId: 'req-bad',
          operation: 'clear', // mismatch!
          approvalId: '550e8400-e29b-41d4-a716-446655440000',
          control: {
            ...VALID_INACTIVE_VIEW,
            killSwitchActive: false, // contradiction!
          },
        } as any;
      }
      return {} as any;
    });

    await act(async () => {
      root.render(
        <AdminSecurityConsole
          nodes={MOCK_NODES}
          currentUser={{ id: 'usr_sec_admin', name: 'Sec Admin', role: 'admin' }}
        />
      );
    });

    const approvalInput = container.querySelector('[data-testid="input-kill-switch-approval-id"]') as HTMLInputElement;
    await act(async () => {
      const nativeSetter = Object.getOwnPropertyDescriptor(window.HTMLInputElement.prototype, 'value')?.set;
      nativeSetter?.call(approvalInput, '550e8400-e29b-41d4-a716-446655440000');
      approvalInput.dispatchEvent(new Event('input', { bubbles: true }));
      approvalInput.dispatchEvent(new Event('change', { bubbles: true }));
    });

    const toggleBtn = container.querySelector('[data-testid="emergency-kill-switch-toggle-btn"]') as HTMLButtonElement;
    await act(async () => {
      toggleBtn.click();
    });

    const confirmBtn = container.querySelector('[data-testid="kill-switch-confirm-btn"]') as HTMLButtonElement;
    await act(async () => {
      confirmBtn.click();
    });

    const errorBanner = container.querySelector('[data-testid="kill-switch-error-banner"]');
    expect(errorBanner?.textContent).toContain('[CONTRACT-MISMATCH]');
    expect(container.querySelector('[data-testid="kill-switch-active-banner"]')).toBeNull();
  });

  // =========================================================================
  // Review Point (3): 승인 ID 기본값 빈 값 & 입력 전 전송 불가
  // =========================================================================
  it('승인 ID가 빈 값일 때 모달에 필수 경고를 표출하고 확정 버튼을 비활성화하여 전송을 차단한다', async () => {
    const postCalls: any[] = [];
    vi.spyOn(client, 'apiClient').mockImplementation(async (endpoint: string, options?: any) => {
      if (endpoint === '/v1/operations/kill-switch' && (!options || options.method === 'GET')) {
        return VALID_INACTIVE_VIEW as any;
      }
      if (options?.method === 'POST') {
        postCalls.push({ endpoint, options });
        return {} as any;
      }
      return {} as any;
    });

    await act(async () => {
      root.render(
        <AdminSecurityConsole
          nodes={MOCK_NODES}
          currentUser={{ id: 'usr_sec_admin', name: 'Sec Admin', role: 'admin' }}
        />
      );
    });

    // 기본값이 빈 문자열임을 확인
    const approvalInput = container.querySelector('[data-testid="input-kill-switch-approval-id"]') as HTMLInputElement;
    expect(approvalInput.value).toBe('');

    const toggleBtn = container.querySelector('[data-testid="emergency-kill-switch-toggle-btn"]') as HTMLButtonElement;
    await act(async () => {
      toggleBtn.click();
    });

    // 필수 입력 안내 배너 확인
    const notice = container.querySelector('[data-testid="kill-switch-approval-required-notice"]');
    expect(notice).not.toBeNull();
    expect(notice?.textContent).toContain('유효한 Containment 승인 UUID(UUIDv4) 입력이 필수입니다');

    // 확정 버튼 비활성화 확인
    const confirmBtn = container.querySelector('[data-testid="kill-switch-confirm-btn"]') as HTMLButtonElement;
    expect(confirmBtn.disabled).toBe(true);
    expect(confirmBtn.getAttribute('aria-disabled')).toBe('true');

    // 클릭 시도에도 0 network mutations
    await act(async () => {
      confirmBtn.click();
    });
    expect(postCalls.length).toBe(0);
  });

  it('비상 정지 API 409 GRAPH-0003 충돌 발생 시 에러 배너에 RFC 9457 ProblemDetails를 표시하고 모달을 닫지 않는다', async () => {
    vi.spyOn(client, 'apiClient').mockImplementation(async (endpoint: string, options?: any) => {
      if (endpoint === '/v1/operations/kill-switch' && (!options || options.method === 'GET')) {
        return VALID_INACTIVE_VIEW as any;
      }
      if (options?.method === 'POST') {
        const error: any = new Error('Control version conflict: expected version 5 differs from server version 7');
        error.problem = {
          type: 'about:blank',
          title: 'Conflict',
          status: 409,
          code: 'GRAPH-0003',
          category: 'GRAPH',
          detail: 'Control version conflict: expected version 5 differs from server version 7',
          retryable: false,
          traceId: 'trace-409-conflict',
        };
        throw error;
      }
      return {} as any;
    });

    await act(async () => {
      root.render(
        <AdminSecurityConsole
          nodes={MOCK_NODES}
          currentUser={{ id: 'usr_sec_admin', name: 'Sec Admin', role: 'admin' }}
        />
      );
    });

    const approvalInput = container.querySelector('[data-testid="input-kill-switch-approval-id"]') as HTMLInputElement;
    await act(async () => {
      const nativeSetter = Object.getOwnPropertyDescriptor(window.HTMLInputElement.prototype, 'value')?.set;
      nativeSetter?.call(approvalInput, '550e8400-e29b-41d4-a716-446655440000');
      approvalInput.dispatchEvent(new Event('input', { bubbles: true }));
      approvalInput.dispatchEvent(new Event('change', { bubbles: true }));
    });

    const toggleBtn = container.querySelector('[data-testid="emergency-kill-switch-toggle-btn"]') as HTMLButtonElement;
    await act(async () => {
      toggleBtn.click();
    });

    const confirmBtn = container.querySelector('[data-testid="kill-switch-confirm-btn"]') as HTMLButtonElement;
    await act(async () => {
      confirmBtn.click();
    });

    const modal = container.querySelector('[data-testid="kill-switch-modal"]');
    expect(modal).not.toBeNull();

    const errorBanner = container.querySelector('[data-testid="kill-switch-error-banner"]');
    expect(errorBanner).not.toBeNull();
    expect(errorBanner?.getAttribute('role')).toBe('alert');
    expect(errorBanner?.textContent).toContain('[GRAPH-0003]');
    expect(errorBanner?.textContent).toContain('Control version conflict');
  });

  it('비상 정지 API 403 AUTH-0062 권한 부족 발생 시 에러 배너에 오류를 명확히 표시한다', async () => {
    vi.spyOn(client, 'apiClient').mockImplementation(async (endpoint: string, options?: any) => {
      if (endpoint === '/v1/operations/kill-switch' && (!options || options.method === 'GET')) {
        return VALID_INACTIVE_VIEW as any;
      }
      if (options?.method === 'POST') {
        const error: any = new Error('Operator containment grant required');
        error.problem = {
          type: 'about:blank',
          title: 'Forbidden',
          status: 403,
          code: 'AUTH-0062',
          category: 'AUTH',
          detail: 'Operator containment grant required',
          retryable: false,
        };
        throw error;
      }
      return {} as any;
    });

    await act(async () => {
      root.render(
        <AdminSecurityConsole
          nodes={MOCK_NODES}
          currentUser={{ id: 'usr_sec_viewer', name: 'Sec Viewer', role: 'viewer' }}
        />
      );
    });

    const approvalInput = container.querySelector('[data-testid="input-kill-switch-approval-id"]') as HTMLInputElement;
    await act(async () => {
      const nativeSetter = Object.getOwnPropertyDescriptor(window.HTMLInputElement.prototype, 'value')?.set;
      nativeSetter?.call(approvalInput, '550e8400-e29b-41d4-a716-446655440000');
      approvalInput.dispatchEvent(new Event('input', { bubbles: true }));
      approvalInput.dispatchEvent(new Event('change', { bubbles: true }));
    });

    const toggleBtn = container.querySelector('[data-testid="emergency-kill-switch-toggle-btn"]') as HTMLButtonElement;
    await act(async () => {
      toggleBtn.click();
    });

    const confirmBtn = container.querySelector('[data-testid="kill-switch-confirm-btn"]') as HTMLButtonElement;
    await act(async () => {
      confirmBtn.click();
    });

    const errorBanner = container.querySelector('[data-testid="kill-switch-error-banner"]');
    expect(errorBanner?.textContent).toContain('[AUTH-0062]');
    expect(errorBanner?.textContent).toContain('Operator containment grant required');
  });

  it('currentUser가 null일 때 관리자 세션 부재 배너를 렌더링하고 토글 버튼과 확정 버튼을 비활성화하여 위조 합성을 방지한다', async () => {
    vi.spyOn(client, 'apiClient').mockResolvedValue(VALID_INACTIVE_VIEW as any);

    await act(async () => {
      root.render(
        <AdminSecurityConsole
          nodes={MOCK_NODES}
          currentUser={null}
        />
      );
    });

    const authNotice = container.querySelector('[data-testid="admin-auth-required-notice"]');
    expect(authNotice).not.toBeNull();
    expect(authNotice?.textContent).toContain('인증된 관리자 세션 부재');

    const toggleBtn = container.querySelector('[data-testid="emergency-kill-switch-toggle-btn"]') as HTMLButtonElement;
    expect(toggleBtn.disabled).toBe(true);
    expect(toggleBtn.getAttribute('aria-disabled')).toBe('true');
  });
});
