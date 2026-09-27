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
    it('인증된 currentUser와 유효한 approval UUID가 주어졌을 때 Idempotency-Key와 ContainmentInput을 전송한다 (body에 actor 미포함)', async () => {
      const apiClientSpy = vi.spyOn(client, 'apiClient').mockResolvedValue({});

      act(() => {
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
      act(() => {
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

      // 4. 유효한 UUIDv4 입력
      const approvalInput = container.querySelector('[data-testid="drain-approval-id-input"]') as HTMLInputElement;
      expect(approvalInput).not.toBeNull();
      act(() => {
        approvalInput.value = '550e8400-e29b-41d4-a716-446655440000';
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
      const drainCall = apiClientSpy.mock.calls.find((call) => call[0] === '/v1/nodes/nod_test_01/drain');
      expect(drainCall).toBeDefined();
      const drainOptions = drainCall?.[1] as any;
      expect(drainOptions.method).toBe('POST');
      expect(drainOptions.idempotencyKey).toBeDefined();
      expect(typeof drainOptions.idempotencyKey).toBe('string');
      expect(drainOptions.idempotencyKey.length).toBeGreaterThan(0);
      expect(drainOptions.idempotencyKey.length).toBeLessThanOrEqual(200);

      const parsedBody = JSON.parse(drainOptions.body);
      expect(parsedBody).toEqual({
        expectedVersion: 1,
        reasonCode: 'maintenance',
        approvalId: '550e8400-e29b-41d4-a716-446655440000',
      });
      // actor는 body에 포함되지 않아야 함 (서버에서 Bearer principal 추출)
      expect(parsedBody.actor).toBeUndefined();
    });

    it('currentUser가 null일 때 경고 배너(role=alert)를 렌더링하고 Drain 네트워크 호출을 0회로 원천 차단한다', async () => {
      const apiClientSpy = vi.spyOn(client, 'apiClient').mockResolvedValue({});

      act(() => {
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
      act(() => {
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
        if (endpoint.endsWith('/drain')) {
          throw apiError;
        }
        return {} as any;
      });

      act(() => {
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
      act(() => {
        drainTabBtn?.click();
      });

      const approvalInput = container.querySelector('[data-testid="drain-approval-id-input"]') as HTMLInputElement;
      act(() => {
        approvalInput.value = '550e8400-e29b-41d4-a716-446655440000';
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
