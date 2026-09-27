// @vitest-environment happy-dom
// @ts-ignore
globalThis.IS_REACT_ACT_ENVIRONMENT = true;
import React, { act } from 'react';
import { createRoot, Root } from 'react-dom/client';
import { describe, it, expect, vi, beforeEach, afterEach } from 'vitest';
import { AdminSecurityConsole } from '../src/features/admin/AdminSecurityConsole';
import { DistributedRecoveryView } from '../src/features/recovery/DistributedRecoveryView';
import { MonacoWorkspaceEditor } from '../src/features/editor/MonacoWorkspaceEditor';
import * as client from '../src/shared/api/client';
import type { NodeItem } from '../src/contracts/types';

const MOCK_NODES: NodeItem[] = [
  {
    id: 'nod_test_01',
    hostname: 'node-win-01',
    os: 'windows',
    cpuCores: 16,
    cpuUsagePercent: 20,
    memoryTotalBytes: 64 * 1024 ** 3,
    memoryUsagePercent: 30,
    gpuName: 'NVIDIA RTX 4090',
    gpuCount: 1,
    status: 'healthy',
    labels: { tier: 'gpu' },
  },
];

describe('화면 결함 5대 부류 치유 트랙 2차 (Priority 4: 관리자 콘솔 행위자 실배선, Priority 5: 분산 복구 모의 고지, Priority 6: 에디터 저장 샌드박스 고지)', () => {
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

  // =========================================================================
  // Priority 4: AdminSecurityConsole usr_admin_01 하드코딩 제거 및 세션 실배선
  // =========================================================================
  describe('Priority 4: AdminSecurityConsole canonical Containment 계약 및 세션/승인ID 가드', () => {
    it('인증된 currentUser와 유효한 approval UUID가 주어졌을 때 Idempotency-Key와 ContainmentInput(조회된 expectedVersion=7)을 전송한다 (body에 actor 미포함)', async () => {
      const apiClientSpy = vi.spyOn(client, 'apiClient').mockImplementation(async (endpoint: string) => {
        if (endpoint.includes('/control')) {
          return { version: 7, killSwitchActive: false, nodeStatus: 'online' } as any;
        }
        return {} as any;
      });

      await act(async () => {
        root.render(
          <AdminSecurityConsole
            nodes={MOCK_NODES}
            currentUser={{ id: 'usr_actual_admin_77', name: 'Actual Admin', role: 'admin' }}
          />
        );
      });

      // 1. 인증 부재 경고 배너가 없어야 함
      const authNotice = container.querySelector('[data-testid="admin-auth-required-notice"]');
      expect(authNotice).toBeNull();

      // 2. Drain 탭으로 이동
      const drainTabBtn = Array.from(container.querySelectorAll('button')).find((b) =>
        b.textContent?.includes('노드 Drain 통제')
      );
      expect(drainTabBtn).toBeDefined();
      await act(async () => {
        drainTabBtn?.click();
      });

      // 3. Approval UUID 입력 전에는 Drain 버튼이 비활성화되고 안내 배너 표시
      const drainBtn = Array.from(container.querySelectorAll('button')).find((b) =>
        b.textContent?.includes('Node Drain')
      ) as HTMLButtonElement;
      expect(drainBtn).toBeDefined();
      expect(drainBtn.disabled).toBe(true);

      const approvalNotice = container.querySelector('[data-testid="drain-approval-required-notice"]');
      expect(approvalNotice).not.toBeNull();
      expect(approvalNotice?.textContent).toContain('유효한 Containment 승인 UUID');

      // 4. 유효한 UUIDv4 입력 (nativeSetter 사용)
      const approvalInput = container.querySelector('[data-testid="drain-approval-id-input"]') as HTMLInputElement;
      expect(approvalInput).not.toBeNull();
      await act(async () => {
        const nativeSetter = Object.getOwnPropertyDescriptor(window.HTMLInputElement.prototype, 'value')?.set;
        nativeSetter?.call(approvalInput, '550e8400-e29b-41d4-a716-446655440000');
        approvalInput.dispatchEvent(new Event('input', { bubbles: true }));
        approvalInput.dispatchEvent(new Event('change', { bubbles: true }));
      });

      // 입력 후 Drain 버튼 활성화
      expect(drainBtn.disabled).toBe(false);

      // 5. Drain 액션 버튼 클릭
      await act(async () => {
        drainBtn?.click();
      });

      // 6. apiClient에 canonical ContainmentInput 및 Idempotency-Key 전달, body에 actor 미포함 검증
      const drainCall = apiClientSpy.mock.calls.find((call) => call[0].includes('/drain'));
      expect(drainCall).toBeDefined();
      const drainOptions = drainCall?.[1] as any;
      expect(drainOptions.method).toBe('POST');
      expect(drainOptions.idempotencyKey).toBeDefined();
      expect(typeof drainOptions.idempotencyKey).toBe('string');
      expect(drainOptions.idempotencyKey.length).toBeGreaterThan(0);
      expect(drainOptions.idempotencyKey.length).toBeLessThanOrEqual(200);

      const parsedBody = JSON.parse(drainOptions.body);
      expect(parsedBody).toEqual({
        expectedVersion: 7, // 서버에서 조회한 version=7 반영 단언 (합성 fallback 1 방지)
        reasonCode: 'maintenance',
        approvalId: '550e8400-e29b-41d4-a716-446655440000',
      });
      // actor는 body에 포함되지 않아야 함 (서버에서 Bearer principal 추출)
      expect(parsedBody.actor).toBeUndefined();
    });

    it('currentUser가 null일 때 경고 배너(role=alert)를 렌더링하고 Drain 네트워크 호출을 0회로 원천 차단한다', async () => {
      const apiClientSpy = vi.spyOn(client, 'apiClient').mockResolvedValue({});

      await act(async () => {
        root.render(
          <AdminSecurityConsole
            nodes={MOCK_NODES}
            currentUser={null}
          />
        );
      });

      // 1. 인증 세션 부재 경고 배너 검증
      const authNotice = container.querySelector('[data-testid="admin-auth-required-notice"]');
      expect(authNotice).not.toBeNull();
      expect(authNotice?.getAttribute('role')).toBe('alert');
      expect(authNotice?.textContent).toContain('인증된 관리자 세션 부재');

      // 2. Drain 탭으로 이동 후 버튼 비활성화 상태 확인
      const drainTabBtn = Array.from(container.querySelectorAll('button')).find((b) =>
        b.textContent?.includes('노드 Drain 통제')
      );
      expect(drainTabBtn).toBeDefined();
      await act(async () => {
        drainTabBtn?.click();
      });

      const drainBtn = Array.from(container.querySelectorAll('button')).find((b) =>
        b.textContent?.includes('Node Drain')
      ) as HTMLButtonElement;
      expect(drainBtn).toBeDefined();
      expect(drainBtn.disabled).toBe(true);

      await act(async () => {
        drainBtn?.click();
      });

      // 3. Drain 네트워크 호출 0회 검증
      const drainCalls = apiClientSpy.mock.calls.filter((c) => c[0].includes('/drain') || c[0].includes('/resume'));
      expect(drainCalls).toHaveLength(0);
    });

    it('Drain API 실패 시 RFC 9457 ProblemDetails(409 GRAPH-0003)를 정직하게 에러 배너에 표시한다', async () => {
      const problem = {
        type: 'about:blank',
        title: 'Control version changed; reload before retry',
        status: 409,
        code: 'GRAPH-0003',
        category: 'GRAPH',
        detail: 'Stored version 2 does not match expected version 1',
        retryable: false,
        traceId: '0123456789abcdef0123456789abcdef',
        causeRef: null,
        evidenceId: null,
      };
      const apiError = new client.ApiError(problem as any);
      vi.spyOn(client, 'apiClient').mockImplementation(async (endpoint: string) => {
        if (endpoint.includes('/control')) {
          return { version: 1, killSwitchActive: false, nodeStatus: 'online' } as any;
        }
        if (endpoint.includes('/drain')) {
          throw apiError;
        }
        return {} as any;
      });

      await act(async () => {
        root.render(
          <AdminSecurityConsole
            nodes={MOCK_NODES}
            currentUser={{ id: 'usr_admin', name: 'Admin', role: 'admin' }}
          />
        );
      });

      const drainTabBtn = Array.from(container.querySelectorAll('button')).find((b) =>
        b.textContent?.includes('노드 Drain 통제')
      );
      await act(async () => {
        drainTabBtn?.click();
      });

      const approvalInput = container.querySelector('[data-testid="drain-approval-id-input"]') as HTMLInputElement;
      expect(approvalInput).not.toBeNull();
      await act(async () => {
        const nativeSetter = Object.getOwnPropertyDescriptor(window.HTMLInputElement.prototype, 'value')?.set;
        nativeSetter?.call(approvalInput, '550e8400-e29b-41d4-a716-446655440000');
        approvalInput.dispatchEvent(new Event('input', { bubbles: true }));
        approvalInput.dispatchEvent(new Event('change', { bubbles: true }));
      });

      const drainBtn = Array.from(container.querySelectorAll('button')).find((b) =>
        b.textContent?.includes('Node Drain')
      ) as HTMLButtonElement;

      await act(async () => {
        drainBtn?.click();
      });

      const errorBanner = container.querySelector('[data-testid="admin-drain-error-banner"]');
      expect(errorBanner).not.toBeNull();
      expect(errorBanner?.textContent).toContain('GRAPH-0003 (409)');
      expect(errorBanner?.textContent).toContain('Control version changed; reload before retry');
      expect(errorBanner?.textContent).toContain('Stored version 2 does not match expected version 1');
    });

    it('노드 제어 버전(/control) 사전 조회 실패 시 Drain POST를 호출하지 않고 에러 배너를 표시한다 (0 network mutations)', async () => {
      const apiClientSpy = vi.spyOn(client, 'apiClient').mockImplementation(async (endpoint: string) => {
        if (endpoint.includes('/control')) {
          const problem = {
            type: 'about:blank',
            title: 'Control plane unavailable',
            status: 503,
            code: 'NET-0503',
            category: 'NET',
            detail: 'Control database unreachable',
            retryable: true,
            traceId: '0123456789abcdef0123456789abcdef',
            causeRef: null,
            evidenceId: null,
          };
          throw new client.ApiError(problem as any);
        }
        return {} as any;
      });

      await act(async () => {
        root.render(
          <AdminSecurityConsole
            nodes={MOCK_NODES}
            currentUser={{ id: 'usr_actual_admin_77', name: 'Actual Admin', role: 'admin' }}
          />
        );
      });

      const drainTabBtn = Array.from(container.querySelectorAll('button')).find((b) =>
        b.textContent?.includes('노드 Drain 통제')
      );
      await act(async () => {
        drainTabBtn?.click();
      });

      const approvalInput = container.querySelector('[data-testid="drain-approval-id-input"]') as HTMLInputElement;
      expect(approvalInput).not.toBeNull();
      await act(async () => {
        const nativeSetter = Object.getOwnPropertyDescriptor(window.HTMLInputElement.prototype, 'value')?.set;
        nativeSetter?.call(approvalInput, '550e8400-e29b-41d4-a716-446655440000');
        approvalInput.dispatchEvent(new Event('input', { bubbles: true }));
        approvalInput.dispatchEvent(new Event('change', { bubbles: true }));
      });

      const drainBtn = Array.from(container.querySelectorAll('button')).find((b) =>
        b.textContent?.includes('Node Drain')
      ) as HTMLButtonElement;

      await act(async () => {
        drainBtn?.click();
      });

      const errorBanner = container.querySelector('[data-testid="admin-drain-error-banner"]');
      expect(errorBanner).not.toBeNull();
      expect(errorBanner?.textContent).toContain('노드 제어 버전(expectedVersion) 사전 조회 실패');
      expect(errorBanner?.textContent).toContain('NET-0503 (503)');

      const drainPosts = apiClientSpy.mock.calls.filter((c) => c[0].includes('/drain') || c[0].includes('/resume'));
      expect(drainPosts).toHaveLength(0);
    });

    it('로컬 Kill Switch가 활성화된 상태에서도 백엔드 정본 Drain 버튼이 활성화되어 있고 /drain POST를 1회 호출한다', async () => {
      const apiClientSpy = vi.spyOn(client, 'apiClient').mockImplementation(async (endpoint: string, options?: any) => {
        if (endpoint.includes('/control')) {
          return {
            version: 5,
            killSwitchActive: false,
            nodeStatus: 'online',
          } as any;
        }
        if (endpoint.includes('/drain')) {
          return {
            control: {
              nodeStatus: 'draining',
              version: 6,
            },
          } as any;
        }
        if (endpoint === '/v1/operations/kill-switch') {
          return {
            version: 1,
            killSwitchActive: false,
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

      // 1. 로컬 비상 Kill Switch 활성화
      const killSwitchToggleBtn = container.querySelector('[data-testid="emergency-kill-switch-toggle-btn"]') as HTMLButtonElement;
      expect(killSwitchToggleBtn).not.toBeNull();
      await act(async () => {
        killSwitchToggleBtn.click();
      });

      const confirmBtn = container.querySelector('[data-testid="kill-switch-confirm-btn"]') as HTMLButtonElement;
      expect(confirmBtn).not.toBeNull();
      await act(async () => {
        confirmBtn.click();
      });

      // 상단 활성 배너 노출 확인
      const activeBanner = container.querySelector('[data-testid="kill-switch-active-banner"]');
      expect(activeBanner).not.toBeNull();

      // 2. Drain 통제 서브탭으로 전환
      const drainTabBtn = Array.from(container.querySelectorAll('button')).find((b) =>
        b.textContent?.includes('노드 Drain 통제')
      );
      await act(async () => {
        drainTabBtn?.click();
      });

      // 3. 승인 UUID 입력
      const approvalInput = container.querySelector('[data-testid="drain-approval-id-input"]') as HTMLInputElement;
      expect(approvalInput).not.toBeNull();
      await act(async () => {
        const nativeSetter = Object.getOwnPropertyDescriptor(window.HTMLInputElement.prototype, 'value')?.set;
        nativeSetter?.call(approvalInput, '11111111-2222-4333-8444-555555555555');
        approvalInput.dispatchEvent(new Event('input', { bubbles: true }));
        approvalInput.dispatchEvent(new Event('change', { bubbles: true }));
      });

      // 4. 로컬 Kill Switch 활성 상태임에도 백엔드 정본 격리 제어 버튼은 활성(disabled=false) 유지 단언
      const drainBtn = Array.from(container.querySelectorAll('button')).find((b) =>
        b.textContent?.includes('Node Drain')
      ) as HTMLButtonElement;
      expect(drainBtn).toBeDefined();
      expect(drainBtn.disabled).toBe(false);

      // 5. Drain 액션 실행 및 /drain POST 1회 호출 단언
      await act(async () => {
        drainBtn.click();
      });

      const drainPosts = apiClientSpy.mock.calls.filter((c) => c[0].includes('/drain'));
      expect(drainPosts).toHaveLength(1);
      const parsedBody = JSON.parse(drainPosts[0][1].body);
      expect(parsedBody.expectedVersion).toBe(5);
      expect(parsedBody.approvalId).toBe('11111111-2222-4333-8444-555555555555');
    });

    it('동일한 노드·의도·승인ID의 재시도 시 동일한 Idempotency-Key와 동일한 payload(expectedVersion 포함)를 재전송한다', async () => {
      let postCount = 0;
      let controlCallCount = 0;
      const apiClientSpy = vi.spyOn(client, 'apiClient').mockImplementation(async (endpoint: string, options?: any) => {
        if (endpoint.includes('/control')) {
          controlCallCount++;
          // Invariant: If code erroneously re-queries /control on retry, it returns version 8 instead of 7
          return { version: controlCallCount === 1 ? 7 : 8, killSwitchActive: false, nodeStatus: 'online' } as any;
        }
        if (endpoint.includes('/drain')) {
          postCount++;
          if (postCount === 1) {
            // First call fails with 503 network error
            const problem = {
              type: 'about:blank',
              title: 'Transient network failure',
              status: 503,
              code: 'NET-0503',
              category: 'NET',
              detail: 'Connection reset by peer',
              retryable: true,
              traceId: '0123456789abcdef0123456789abcdef',
            };
            throw new client.ApiError(problem as any);
          }
          return {
            requestId: 'req_drain_retry_success',
            operation: 'drain',
            control: { nodeStatus: 'draining', version: 8 },
            approvalId: '550e8400-e29b-41d4-a716-446655440000',
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

      // Switch to Drain tab
      const drainTabBtn = Array.from(container.querySelectorAll('button')).find((b) =>
        b.textContent?.includes('노드 Drain 통제')
      );
      await act(async () => {
        drainTabBtn?.click();
      });

      // Enter approval UUID
      const approvalInput = container.querySelector('[data-testid="drain-approval-id-input"]') as HTMLInputElement;
      await act(async () => {
        const nativeSetter = Object.getOwnPropertyDescriptor(window.HTMLInputElement.prototype, 'value')?.set;
        nativeSetter?.call(approvalInput, '550e8400-e29b-41d4-a716-446655440000');
        approvalInput.dispatchEvent(new Event('input', { bubbles: true }));
        approvalInput.dispatchEvent(new Event('change', { bubbles: true }));
      });

      const drainBtn = Array.from(container.querySelectorAll('button')).find((b) =>
        b.textContent?.includes('Node Drain')
      ) as HTMLButtonElement;

      // 1st attempt (fails with 503)
      await act(async () => {
        drainBtn.click();
      });

      const firstDrainCall = apiClientSpy.mock.calls.find((c) => c[0].includes('/drain'));
      expect(firstDrainCall).toBeDefined();
      const firstKey = firstDrainCall?.[1]?.idempotencyKey;
      const firstBody = JSON.parse(firstDrainCall?.[1]?.body);
      expect(firstKey).toBeDefined();
      expect(firstBody.expectedVersion).toBe(7);

      // 2nd attempt (same operation retry)
      await act(async () => {
        drainBtn.click();
      });

      // Invariant: Retrying MUST NOT re-query /control! Exactly 1 call.
      const controlCalls = apiClientSpy.mock.calls.filter((c) => c[0].includes('/control'));
      expect(controlCalls).toHaveLength(1);
      expect(controlCallCount).toBe(1);

      const drainCalls = apiClientSpy.mock.calls.filter((c) => c[0].includes('/drain'));
      expect(drainCalls).toHaveLength(2);
      const secondKey = drainCalls[1]?.[1]?.idempotencyKey;
      const secondBody = JSON.parse(drainCalls[1]?.[1]?.body);

      // Invariant: Retrying MUST reuse the exact same Idempotency-Key AND identical payload (including expectedVersion)
      expect(secondKey).toBe(firstKey);
      expect(secondBody).toEqual(firstBody);
      expect(secondBody.expectedVersion).toBe(7);
    });

    it('409 GRAPH-0003 최종 실패 뒤 재클릭 시 캐시를 삭제하고 /control을 다시 조회하여 최신 expectedVersion으로 요청한다', async () => {
      let controlCallCount = 0;
      let drainCallCount = 0;
      const apiClientSpy = vi.spyOn(client, 'apiClient').mockImplementation(async (endpoint: string, options?: any) => {
        if (endpoint.includes('/control')) {
          controlCallCount++;
          // First query returns stale version 7, second query returns refreshed version 8
          return {
            version: controlCallCount === 1 ? 7 : 8,
            killSwitchActive: false,
            nodeStatus: 'online',
          } as any;
        }
        if (endpoint.includes('/drain')) {
          drainCallCount++;
          if (drainCallCount === 1) {
            // First call fails with 409 Conflict GRAPH-0003 (non-retryable final failure)
            const problem = {
              type: 'about:blank',
              title: 'Conflict',
              status: 409,
              code: 'GRAPH-0003',
              category: 'GRAPH',
              detail: 'Control version conflict: expected version 7 differs from server',
              retryable: false,
              traceId: '0123456789abcdef0123456789abcdef',
            };
            throw new client.ApiError(problem as any);
          }
          // Second call succeeds with updated version 8
          return {
            requestId: 'req_drain_recovered_after_409',
            operation: 'drain',
            control: { nodeStatus: 'draining', version: 9 },
            approvalId: '550e8400-e29b-41d4-a716-446655440000',
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

      // Switch to Drain tab
      const drainTabBtn = Array.from(container.querySelectorAll('button')).find((b) =>
        b.textContent?.includes('노드 Drain 통제')
      );
      await act(async () => {
        drainTabBtn?.click();
      });

      // Enter approval UUID
      const approvalInput = container.querySelector('[data-testid="drain-approval-id-input"]') as HTMLInputElement;
      await act(async () => {
        const nativeSetter = Object.getOwnPropertyDescriptor(window.HTMLInputElement.prototype, 'value')?.set;
        nativeSetter?.call(approvalInput, '550e8400-e29b-41d4-a716-446655440000');
        approvalInput.dispatchEvent(new Event('input', { bubbles: true }));
        approvalInput.dispatchEvent(new Event('change', { bubbles: true }));
      });

      const drainBtn = Array.from(container.querySelectorAll('button')).find((b) =>
        b.textContent?.includes('Node Drain')
      ) as HTMLButtonElement;

      // 1st attempt: fails with 409 Conflict
      await act(async () => {
        drainBtn.click();
      });

      // Verify 409 error banner is displayed
      const errorBanner = container.querySelector('[data-testid="drain-error-banner"]');
      expect(errorBanner?.textContent).toContain('GRAPH-0003 (409)');

      const firstDrainCall = apiClientSpy.mock.calls.find((c) => c[0].includes('/drain'));
      expect(firstDrainCall).toBeDefined();
      const firstKey = firstDrainCall?.[1]?.idempotencyKey;
      const firstBody = JSON.parse(firstDrainCall?.[1]?.body);
      expect(firstBody.expectedVersion).toBe(7);

      // 2nd attempt: click drain again after 409 final failure
      await act(async () => {
        drainBtn.click();
      });

      // Invariant: Non-retryable error MUST have purged cache.
      // Therefore, /control MUST be queried a second time, obtaining version 8!
      const controlCalls = apiClientSpy.mock.calls.filter((c) => c[0].includes('/control'));
      expect(controlCalls).toHaveLength(2);
      expect(controlCallCount).toBe(2);

      const drainCalls = apiClientSpy.mock.calls.filter((c) => c[0].includes('/drain'));
      expect(drainCalls).toHaveLength(2);
      const secondKey = drainCalls[1]?.[1]?.idempotencyKey;
      const secondBody = JSON.parse(drainCalls[1]?.[1]?.body);

      // Fresh idempotency key and updated expectedVersion (8 instead of 7)
      expect(secondKey).not.toBe(firstKey);
      expect(secondBody.expectedVersion).toBe(8);

      // Successfully resolved
      expect(container.querySelector('[data-testid="drain-error-banner"]')).toBeNull();
    });

    it('화면 표시 의도와 서버 상태 불일치 시 POST를 수행하지 않고(POST 0회) 상태 변경 안내를 표시한다', async () => {
      const apiClientSpy = vi.spyOn(client, 'apiClient').mockImplementation(async (endpoint: string) => {
        if (endpoint.includes('/control')) {
          // Server reports node is already draining while UI displays 'Node Drain' (undrained)
          return {
            version: 15,
            killSwitchActive: false,
            nodeStatus: 'draining',
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

      const drainTabBtn = Array.from(container.querySelectorAll('button')).find((b) =>
        b.textContent?.includes('노드 Drain 통제')
      );
      await act(async () => {
        drainTabBtn?.click();
      });

      const approvalInput = container.querySelector('[data-testid="drain-approval-id-input"]') as HTMLInputElement;
      await act(async () => {
        const nativeSetter = Object.getOwnPropertyDescriptor(window.HTMLInputElement.prototype, 'value')?.set;
        nativeSetter?.call(approvalInput, '550e8400-e29b-41d4-a716-446655440000');
        approvalInput.dispatchEvent(new Event('input', { bubbles: true }));
        approvalInput.dispatchEvent(new Event('change', { bubbles: true }));
      });

      const drainBtn = Array.from(container.querySelectorAll('button')).find((b) =>
        b.textContent?.includes('Node Drain')
      ) as HTMLButtonElement;

      await act(async () => {
        drainBtn.click();
      });

      // Invariant: Because server state differed from displayed intention, POST must NOT be called (0 calls)
      const postCalls = apiClientSpy.mock.calls.filter((c) => c[1]?.method === 'POST');
      expect(postCalls).toHaveLength(0);

      // Error banner indicates state changed and asks to refresh
      const banner = container.querySelector('[data-testid="admin-drain-error-banner"]');
      expect(banner?.textContent).toContain('상태 변경됨·새로고침');
    });

    it('서버 성공 응답에 canonical control 필드가 누락되면 합성하지 않고 오류 배너를 표시한다', async () => {
      vi.spyOn(client, 'apiClient').mockImplementation(async (endpoint: string) => {
        if (endpoint.includes('/control')) {
          return {
            version: 3,
            killSwitchActive: false,
            nodeStatus: 'online',
          } as any;
        }
        if (endpoint.includes('/drain')) {
          // Success status 200 but control field is missing!
          return {
            requestId: 'req_missing_control',
            operation: 'drain',
            // No control field!
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

      const drainTabBtn = Array.from(container.querySelectorAll('button')).find((b) =>
        b.textContent?.includes('노드 Drain 통제')
      );
      await act(async () => {
        drainTabBtn?.click();
      });

      const approvalInput = container.querySelector('[data-testid="drain-approval-id-input"]') as HTMLInputElement;
      await act(async () => {
        const nativeSetter = Object.getOwnPropertyDescriptor(window.HTMLInputElement.prototype, 'value')?.set;
        nativeSetter?.call(approvalInput, '550e8400-e29b-41d4-a716-446655440000');
        approvalInput.dispatchEvent(new Event('input', { bubbles: true }));
        approvalInput.dispatchEvent(new Event('change', { bubbles: true }));
      });

      const drainBtn = Array.from(container.querySelectorAll('button')).find((b) =>
        b.textContent?.includes('Node Drain')
      ) as HTMLButtonElement;

      await act(async () => {
        drainBtn.click();
      });

      // Error banner displays missing control error rather than synthesizing state
      const banner = container.querySelector('[data-testid="admin-drain-error-banner"]');
      expect(banner?.textContent).toContain('canonical control 필드가 누락');
    });

    it('Kill Switch 모달은 열릴 때 취소 버튼에 초기 포커스되고, Tab/Shift+Tab 순환 후 Esc 닫기 시 열기 전 요소로 포커스를 복원한다', async () => {
      vi.useFakeTimers();
      vi.spyOn(client, 'apiClient').mockResolvedValue({});

      await act(async () => {
        root.render(
          <AdminSecurityConsole
            nodes={MOCK_NODES}
            currentUser={{ id: 'usr_sec_admin', name: 'Sec Admin', role: 'admin' }}
          />
        );
      });

      // 1. Focus toggle button and open modal
      const toggleBtn = container.querySelector('[data-testid="emergency-kill-switch-toggle-btn"]') as HTMLButtonElement;
      toggleBtn.focus();
      expect(document.activeElement).toBe(toggleBtn);

      await act(async () => {
        toggleBtn.click();
      });

      // Advance timers for initial focus
      act(() => {
        vi.runAllTimers();
      });

      const modal = container.querySelector('[data-testid="kill-switch-modal"]');
      expect(modal).not.toBeNull();

      const cancelBtn = container.querySelector('[data-testid="kill-switch-cancel-btn"]') as HTMLButtonElement;
      const confirmBtn = container.querySelector('[data-testid="kill-switch-confirm-btn"]') as HTMLButtonElement;
      expect(cancelBtn).not.toBeNull();
      expect(confirmBtn).not.toBeNull();

      // Initial focus on cancel button
      expect(document.activeElement).toBe(cancelBtn);

      // 2. Focus trap: Shift+Tab from cancelBtn (first element) wraps to confirmBtn (last element)
      const shiftTabEvent = new KeyboardEvent('keydown', { key: 'Tab', shiftKey: true, bubbles: true, cancelable: true });
      window.dispatchEvent(shiftTabEvent);
      expect(document.activeElement).toBe(confirmBtn);

      // Tab from confirmBtn (last element) wraps back to cancelBtn (first element)
      const tabEvent = new KeyboardEvent('keydown', { key: 'Tab', shiftKey: false, bubbles: true, cancelable: true });
      window.dispatchEvent(tabEvent);
      expect(document.activeElement).toBe(cancelBtn);

      // 3. Esc key closes modal and restores focus to toggle button
      const escEvent = new KeyboardEvent('keydown', { key: 'Escape', bubbles: true, cancelable: true });
      act(() => {
        window.dispatchEvent(escEvent);
        vi.runAllTimers();
      });

      expect(container.querySelector('[data-testid="kill-switch-modal"]')).toBeNull();
      expect(document.activeElement).toBe(toggleBtn);
      vi.useRealTimers();
    });

    it('GPU 탭 전환 시 ReferenceError 없이 렌더링되고 GPU 벤치마크 컨트롤이 표시된다', async () => {
      vi.spyOn(client, 'apiClient').mockResolvedValue({});

      await act(async () => {
        root.render(
          <AdminSecurityConsole
            nodes={MOCK_NODES}
            currentUser={{ id: 'usr_sec_admin', name: 'Sec Admin', role: 'admin' }}
          />
        );
      });

      // Find and click the GPU sub-tab button
      const gpuTabBtn = Array.from(container.querySelectorAll('button')).find((b) =>
        b.textContent?.includes('합성 GPU')
      );
      expect(gpuTabBtn).toBeDefined();

      await act(async () => {
        gpuTabBtn?.click();
      });

      // Verify GPU tab content renders without crashing
      const heading = Array.from(container.querySelectorAll('h3')).find((h) =>
        h.textContent?.includes('합성 GPU 작업 실행 성능 검증')
      );
      expect(heading).toBeDefined();

      const gpuSelect = container.querySelector('[data-testid="gpu-node-select"]');
      expect(gpuSelect).not.toBeNull();
    });

    it('백엔드 Kill Switch 403 AUTH-0062 실패 시 "조회 실패 [AUTH-0062]"를 표시한다', async () => {
      vi.spyOn(client, 'apiClient').mockImplementation(async (endpoint: string) => {
        if (endpoint === '/v1/operations/kill-switch') {
          const problem = {
            type: 'about:blank',
            title: 'Current operator permission required',
            status: 403,
            code: 'AUTH-0062',
            category: 'AUTH',
            detail: 'Operator grant missing',
            retryable: false,
            traceId: '0123456789abcdef0123456789abcdef',
            causeRef: null,
            evidenceId: null,
          };
          throw new client.ApiError(problem as any);
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

      const statusEl = container.querySelector('[data-testid="backend-kill-switch-status"]');
      expect(statusEl).not.toBeNull();
      expect(statusEl?.textContent).toContain('조회 실패 [AUTH-0062]');
    });

    it('백엔드 Kill Switch 빈 응답({}) 시 "조회 실패 [응답 형식 불일치]"를 표시한다', async () => {
      vi.spyOn(client, 'apiClient').mockImplementation(async (endpoint: string) => {
        if (endpoint === '/v1/operations/kill-switch') {
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

      const statusEl = container.querySelector('[data-testid="backend-kill-switch-status"]');
      expect(statusEl).not.toBeNull();
      expect(statusEl?.textContent).toContain('조회 실패 [응답 형식 불일치]');
    });

    it('백엔드 Kill Switch 정상 조회 시 INACTIVE 및 ACTIVE 상태를 정직하게 표시한다', async () => {
      // INACTIVE case
      vi.spyOn(client, 'apiClient').mockImplementation(async (endpoint: string) => {
        if (endpoint === '/v1/operations/kill-switch') {
          return { killSwitchActive: false, version: 1, nodeId: null, nodeStatus: 'online', activeLeases: 0, pendingDeliveries: 0, unsettledRuns: 0, settled: true } as any;
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

      const statusElInactive = container.querySelector('[data-testid="backend-kill-switch-status"]');
      expect(statusElInactive?.textContent).toContain('✔ INACTIVE');

      // Unmount and re-mount for ACTIVE case
      act(() => {
        root.unmount();
      });
      root = createRoot(container);

      vi.spyOn(client, 'apiClient').mockImplementation(async (endpoint: string) => {
        if (endpoint === '/v1/operations/kill-switch') {
          return { killSwitchActive: true, version: 2, nodeId: null, nodeStatus: 'quarantined', activeLeases: 0, pendingDeliveries: 0, unsettledRuns: 0, settled: true } as any;
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

      const statusElActive = container.querySelector('[data-testid="backend-kill-switch-status"]');
      expect(statusElActive?.textContent).toContain('🚨 ACTIVE');
    });

    it('상단 보안 KPI 타일 및 재해복구/백업 탭의 모의 및 UNMEASURED 고지를 DOM에서 검증한다', async () => {
      vi.spyOn(client, 'apiClient').mockResolvedValue({});

      await act(async () => {
        root.render(
          <AdminSecurityConsole
            nodes={MOCK_NODES}
            currentUser={{ id: 'usr_sec_admin', name: 'Sec Admin', role: 'admin' }}
          />
        );
      });

      // 1. 상단 KPI 타일 모의/UNMEASURED 표기 검증 (seedInitialAuditLogs로 인해 각 1건 차단 초기값)
      expect(container.textContent).toContain('1 건 차단 (모의 격리; 물리 컨테이너 UNMEASURED)');
      expect(container.textContent).toContain('건 차단 (모의 차단; 물리 승인은 UNMEASURED)');
      expect(container.textContent).toContain('RTX 4090 / A4000 합성 벤치마크 (물리 GPU 미측정)');
      expect(container.textContent).toContain('분 전 (모의; 물리 S3 오프사이트 UNMEASURED)');
      expect(container.textContent).toContain('RTO 12분 (모의; 물리 PITR UNMEASURED)');

      // 2. 재해 복구 및 WAL 백업 서브탭으로 이동하여 RPO/RTO 표기 검증
      const backupTabBtn = Array.from(container.querySelectorAll('button')).find((b) =>
        b.textContent?.includes('재해 복구 및 WAL 백업')
      );
      expect(backupTabBtn).toBeDefined();
      await act(async () => {
        backupTabBtn?.click();
      });

      expect(container.textContent).toContain('4분 전 기록 (모의 시뮬레이션; 물리 WAL UNMEASURED)');
      expect(container.textContent).toContain('4.2 분 (모의 PASS; 물리 S3 RPO UNMEASURED)');
      expect(container.textContent).toContain('RTO 모의 추정치 (Target ≤ 60m; 물리 RTO UNMEASURED)');
      expect(container.textContent).toContain('12.5 분 (모의 PASS; 물리 PITR 복원 UNMEASURED)');
      expect(container.textContent).toContain('Epoch 전진 포함 (물리 재해 복구 UNMEASURED)');
    });

    it('ADR-054 탭 버튼 및 섹션 헤더, 그리고 불변 감사 로그 원장의 모의 고지 제목을 DOM에서 단언한다', async () => {
      vi.spyOn(client, 'apiClient').mockResolvedValue({});

      await act(async () => {
        root.render(
          <AdminSecurityConsole
            nodes={MOCK_NODES}
            currentUser={{ id: 'usr_sec_admin', name: 'Sec Admin', role: 'admin' }}
          />
        );
      });

      // 1. 감사 로그 원장 제목 고지 검증
      const auditHeading = container.querySelector('h3');
      expect(auditHeading?.textContent).toContain('불변 감사 로그 원장 (로컬 합성 원장; 백엔드 감사 아님)');

      // 2. Drain 탭 버튼의 ADR-054 명칭 검증
      const drainTabBtn = Array.from(container.querySelectorAll('button')).find((b) =>
        b.textContent?.includes('노드 Drain 통제 (ADR-054)')
      );
      expect(drainTabBtn).toBeDefined();

      await act(async () => {
        drainTabBtn?.click();
      });

      // 3. 섹션 헤더의 ADR-054 명칭 검증
      const sectionHeader = Array.from(container.querySelectorAll('h3')).find((h) =>
        h.textContent?.includes('클러스터 노드 Drain 및 스케줄링 통제 (ADR-054)')
      );
      expect(sectionHeader).toBeDefined();
    });
  });

  // =========================================================================
  // Priority 5: DistributedRecoveryView 체크아웃 시뮬레이션 및 unexposed notice
  // =========================================================================
  describe('Priority 5: DistributedRecoveryView 체크아웃 시뮬레이션 및 unexposed notice', () => {
    it('상단에 recovery-unexposed-notice(role=status)를 렌더링하고 백엔드 API 부재를 고지한다', () => {
      act(() => {
        root.render(<DistributedRecoveryView nodes={MOCK_NODES} />);
      });

      const notice = container.querySelector('[data-testid="recovery-unexposed-notice"]');
      expect(notice).not.toBeNull();
      expect(notice?.getAttribute('role')).toBe('status');
      expect(notice?.textContent).toContain('분산 장애 복구 및 펜싱 시뮬레이션 제어기 (API 미노출)');
      expect(notice?.textContent).toContain('클라이언트 인메모리 시뮬레이션입니다');
    });

    it('체크아웃 생성 시 실제 파일시스템에 기록된 양 속이지 않고 모의 시뮬레이션 고지를 표시한다', () => {
      act(() => {
        root.render(<DistributedRecoveryView nodes={MOCK_NODES} />);
      });

      const checkoutBtn = container.querySelector('[data-testid="create-checkout-btn"]') as HTMLButtonElement;
      expect(checkoutBtn).not.toBeNull();

      act(() => {
        checkoutBtn.click();
      });

      // 이전의 "✓ ADR-043 Writable Generation 생성 완료" 허위 완료 배너가 아니어야 함
      expect(container.textContent).toContain('ℹ️ [모의 시뮬레이션] ADR-043 Writable Generation 생성');
      expect(container.textContent).toContain('백엔드 파일시스템에는 기록되지 않습니다');
      expect(container.textContent).toContain('sim_chk_1');
    });
  });

  // =========================================================================
  // Priority 6: MonacoWorkspaceEditor 인메모리 샌드박스 고지
  // =========================================================================
  describe('Priority 6: MonacoWorkspaceEditor 인메모리 샌드박스 고지', () => {
    it('상단에 editor-unexposed-notice(role=status)를 렌더링하고 저장 버튼에 로컬 샌드박스 명칭을 적용한다', () => {
      act(() => {
        root.render(<MonacoWorkspaceEditor workspaceId="wsp_test_01" projectId="prj_alpha" />);
      });

      const notice = container.querySelector('[data-testid="editor-unexposed-notice"]');
      expect(notice).not.toBeNull();
      expect(notice?.getAttribute('role')).toBe('status');
      expect(notice?.textContent).toContain('인메모리 워크스페이스 에디터 (체크아웃 컨텍스트 미연결)');
      expect(notice?.textContent).toContain('WorkspaceEditView 계약');

      const saveBtn = container.querySelector('[data-testid="editor-save-btn"]');
      expect(saveBtn).not.toBeNull();
      expect(saveBtn?.textContent).toContain('Save File (Local Sandbox)');
      expect(saveBtn?.getAttribute('title')).toContain('체크아웃 컨텍스트 미연결');
    });
  });
});
