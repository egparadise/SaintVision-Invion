// @vitest-environment happy-dom
// @ts-ignore
globalThis.IS_REACT_ACT_ENVIRONMENT = true;
import React, { act } from 'react';
import { createRoot, Root } from 'react-dom/client';
import { describe, it, expect, vi, beforeEach, afterEach } from 'vitest';
import { AdminSecurityConsole } from '../src/features/admin/AdminSecurityConsole';
import * as client from '../src/shared/api/client';
import type { NodeItem } from '../src/contracts/types';

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

    vi.spyOn(client, 'apiClient').mockImplementation(async (endpoint: string, options?: any) => {
      if (endpoint === '/v1/operations/kill-switch' && (!options || options.method === 'GET')) {
        return { version: 5, killSwitchActive: false, nodeStatus: 'online' } as any;
      }
      if (endpoint === '/v1/operations/kill-switch' && options?.method === 'POST') {
        capturedEndpoint = endpoint;
        capturedOptions = options;
        return {
          operation: 'kill',
          control: {
            version: 6,
            killSwitchActive: true,
            nodeStatus: 'online',
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

    // 백엔드 제어 평면 상태 반영 확인
    const backendStatus = container.querySelector('[data-testid="backend-kill-switch-status"]');
    expect(backendStatus?.textContent).toContain('INACTIVE (v5)');

    // 1. 헤더에서 사유 코드와 승인 ID 변경
    const reasonSelect = container.querySelector('[data-testid="kill-switch-reason-select"]') as HTMLSelectElement;
    expect(reasonSelect).not.toBeNull();
    await act(async () => {
      reasonSelect.value = 'incident';
      reasonSelect.dispatchEvent(new Event('change', { bubbles: true }));
    });

    const approvalInput = container.querySelector('[data-testid="input-kill-switch-approval-id"]') as HTMLInputElement;
    expect(approvalInput).not.toBeNull();
    await act(async () => {
      const nativeSetter = Object.getOwnPropertyDescriptor(window.HTMLInputElement.prototype, 'value')?.set;
      nativeSetter?.call(approvalInput, '11111111-2222-4333-8444-555555555555');
      approvalInput.dispatchEvent(new Event('input', { bubbles: true }));
      approvalInput.dispatchEvent(new Event('change', { bubbles: true }));
    });

    // 2. 모달 열기
    const toggleBtn = container.querySelector('[data-testid="emergency-kill-switch-toggle-btn"]') as HTMLButtonElement;
    expect(toggleBtn).not.toBeNull();
    expect(toggleBtn.textContent).toContain('🚨 긴급 Kill Switch 발동');

    await act(async () => {
      toggleBtn.click();
    });

    const modal = container.querySelector('[data-testid="kill-switch-modal"]');
    expect(modal).not.toBeNull();

    // 요약 표시 검증
    const summary = container.querySelector('[data-testid="kill-switch-params-summary"]');
    expect(summary?.textContent).toContain('incident');
    expect(summary?.textContent).toContain('11111111-2222-4333-8444-555555555555');

    // 3. 비상 정지 발동 확정
    const confirmBtn = container.querySelector('[data-testid="kill-switch-confirm-btn"]') as HTMLButtonElement;
    await act(async () => {
      confirmBtn.click();
    });

    // 실배선 API 호출 단언
    expect(capturedEndpoint).toBe('/v1/operations/kill-switch');
    expect(capturedOptions).not.toBeNull();
    expect(capturedOptions.method).toBe('POST');
    expect(capturedOptions.headers['Idempotency-Key']).toMatch(/^killswitch_/);

    const sentPayload = JSON.parse(capturedOptions.body);
    expect(sentPayload).toEqual({
      expectedVersion: 5,
      reasonCode: 'incident',
      approvalId: '11111111-2222-4333-8444-555555555555',
    });

    // 발동 후 모달 닫힘 및 상단 활성 배너 표출 확인
    expect(container.querySelector('[data-testid="kill-switch-modal"]')).toBeNull();
    const activeBanner = container.querySelector('[data-testid="kill-switch-active-banner"]');
    expect(activeBanner).not.toBeNull();
    expect(activeBanner?.getAttribute('role')).toBe('alert');
    expect(backendStatus?.textContent).toContain('ACTIVE (v6)');
  });

  it('비상 정지가 활성 상태일 때 해제 실행 시 POST /v1/operations/kill-switch/clear (202 Accepted)를 호출하고 비활성 상태로 복귀한다', async () => {
    let capturedEndpoint: string | null = null;
    let capturedOptions: any = null;

    vi.spyOn(client, 'apiClient').mockImplementation(async (endpoint: string, options?: any) => {
      if (endpoint === '/v1/operations/kill-switch' && (!options || options.method === 'GET')) {
        return { version: 8, killSwitchActive: true, nodeStatus: 'online' } as any;
      }
      if (endpoint === '/v1/operations/kill-switch/clear' && options?.method === 'POST') {
        capturedEndpoint = endpoint;
        capturedOptions = options;
        return {
          operation: 'clear',
          control: {
            version: 9,
            killSwitchActive: false,
            nodeStatus: 'online',
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

    const backendStatus = container.querySelector('[data-testid="backend-kill-switch-status"]');
    expect(backendStatus?.textContent).toContain('ACTIVE (v8)');

    // 활성 상태이므로 토글 버튼 문구는 'Kill Switch 해제'
    const toggleBtn = container.querySelector('[data-testid="emergency-kill-switch-toggle-btn"]') as HTMLButtonElement;
    expect(toggleBtn.textContent).toContain('Kill Switch 해제');

    // 모달 열기
    await act(async () => {
      toggleBtn.click();
    });

    const modalTitle = container.querySelector('#kill-switch-modal-title');
    expect(modalTitle?.textContent).toContain('Kill Switch 비활성화(해제) 확인');

    const confirmBtn = container.querySelector('[data-testid="kill-switch-confirm-btn"]') as HTMLButtonElement;
    expect(confirmBtn.textContent).toContain('해제 실행');

    // 해제 확정 실행
    await act(async () => {
      confirmBtn.click();
    });

    expect(capturedEndpoint).toBe('/v1/operations/kill-switch/clear');
    expect(capturedOptions.method).toBe('POST');
    const sentPayload = JSON.parse(capturedOptions.body);
    expect(sentPayload).toEqual({
      expectedVersion: 8,
      reasonCode: 'operator_request',
      approvalId: '00000000-0000-4000-8000-000000000001',
    });

    // 해제 후 활성 배너 제거 및 INACTIVE 갱신
    expect(container.querySelector('[data-testid="kill-switch-active-banner"]')).toBeNull();
    expect(backendStatus?.textContent).toContain('INACTIVE (v9)');
  });

  it('비상 정지 API 409 GRAPH-0003 충돌 발생 시 에러 배너에 RFC 9457 ProblemDetails를 표시하고 모달을 닫지 않는다', async () => {
    vi.spyOn(client, 'apiClient').mockImplementation(async (endpoint: string, options?: any) => {
      if (endpoint === '/v1/operations/kill-switch' && (!options || options.method === 'GET')) {
        return { version: 2, killSwitchActive: false, nodeStatus: 'online' } as any;
      }
      if (options?.method === 'POST') {
        const error: any = new Error('Control version conflict: expected version 2 differs from server version 4');
        error.problem = {
          type: 'about:blank',
          title: 'Conflict',
          status: 409,
          code: 'GRAPH-0003',
          category: 'GRAPH',
          detail: 'Control version conflict: expected version 2 differs from server version 4',
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

    const toggleBtn = container.querySelector('[data-testid="emergency-kill-switch-toggle-btn"]') as HTMLButtonElement;
    await act(async () => {
      toggleBtn.click();
    });

    const confirmBtn = container.querySelector('[data-testid="kill-switch-confirm-btn"]') as HTMLButtonElement;
    await act(async () => {
      confirmBtn.click();
    });

    // 모달이 닫히지 않고 내부 에러 배너에 정직하게 표시
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
        return { version: 1, killSwitchActive: false, nodeStatus: 'online' } as any;
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

  it('승인 식별자가 유효한 UUIDv4가 아닐 경우 네트워크 POST를 0회로 원천 차단하고 오류를 표시한다', async () => {
    const postCalls: any[] = [];
    vi.spyOn(client, 'apiClient').mockImplementation(async (endpoint: string, options?: any) => {
      if (endpoint === '/v1/operations/kill-switch' && (!options || options.method === 'GET')) {
        return { version: 1, killSwitchActive: false, nodeStatus: 'online' } as any;
      }
      if (options?.method === 'POST') {
        postCalls.push({ endpoint, options });
        return { operation: 'kill' } as any;
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

    // 잘못된 UUID 입력
    const approvalInput = container.querySelector('[data-testid="input-kill-switch-approval-id"]') as HTMLInputElement;
    await act(async () => {
      const nativeSetter = Object.getOwnPropertyDescriptor(window.HTMLInputElement.prototype, 'value')?.set;
      nativeSetter?.call(approvalInput, 'invalid-uuid-string-1234');
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

    // 네트워크 POST 호출이 0회여야 함
    expect(postCalls.length).toBe(0);

    const errorBanner = container.querySelector('[data-testid="kill-switch-error-banner"]');
    expect(errorBanner).not.toBeNull();
    expect(errorBanner?.textContent).toContain('유효한 Containment 승인 UUID(approvalId)가 필요합니다');
  });

  it('currentUser가 null일 때 관리자 세션 부재 배너를 렌더링하고 토글 버튼과 확정 버튼을 비활성화하여 위조 합성을 방지한다', async () => {
    vi.spyOn(client, 'apiClient').mockResolvedValue({ version: 1, killSwitchActive: false });

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
