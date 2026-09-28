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
    status: 'online',
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

    it('Defect 1: nodes=[] 일 때 selectedNode.hostname 렌더 예외 없이 recovery-empty-nodes-screen 빈 화면을 안전하게 렌더링한다', () => {
      act(() => {
        root.render(<DistributedRecoveryView nodes={[]} />);
      });

      const emptyScreen = container.querySelector('[data-testid="recovery-empty-nodes-screen"]');
      expect(emptyScreen).not.toBeNull();
      expect(emptyScreen?.textContent).toContain('클러스터에 등록된 노드가 없거나 관측 대기 중입니다');
      expect(emptyScreen?.textContent).toContain('0대');
      const nodeCards = container.querySelectorAll('[data-testid^="node-card-"]');
      expect(nodeCards.length).toBe(0);
    });

    it('Defect 2: KPI 타일에 UNMEASURED(미측정/물리 실측)를 올바르게 표기하고, Heartbeat Drop 시 AC-07 verified 허위 문구를 배제한다', () => {
      act(() => {
        root.render(<DistributedRecoveryView nodes={MOCK_NODES} />);
      });

      // 1. KPI detection time 검증 (정적 ≤60초 실측 통과 리터럴 제거 확인)
      const detectionTile = container.querySelector('[data-testid="kpi-detection-time"]');
      expect(detectionTile).not.toBeNull();
      expect(detectionTile?.textContent).toContain('UNMEASURED (물리 실측)');

      // 2. 초기 recovery rate 검증 (0건일 때 100% 하드코딩 제거 확인)
      const rateTile = container.querySelector('[data-testid="kpi-recovery-rate"]');
      expect(rateTile).not.toBeNull();
      expect(rateTile?.textContent).toContain('UNMEASURED (미측정)');

      // 3. Heartbeat Delay 버튼 클릭 (정확한 data-testid 셀렉터 사용)
      const hbBtn = container.querySelector('[data-testid="simulate-heartbeat-delay-btn"]') as HTMLButtonElement;
      expect(hbBtn).not.toBeNull();

      act(() => {
        hbBtn.click();
      });

      // 4. 액션 알림창에서 '(AC-07 verified)'가 없어야 하고 '(모의 시뮬레이션; 물리 AC-07 UNMEASURED)'가 포함되어야 함
      const notice = container.querySelector('[data-testid="recovery-action-notice"]');
      expect(notice).not.toBeNull();
      expect(notice?.textContent).not.toContain('(AC-07 verified)');
      expect(notice?.textContent).toContain('(모의 시뮬레이션; 물리 AC-07 UNMEASURED)');
    });

    it('Defect 3: 노드 카드에 백엔드 제어 평면 실제 보고 상태(offline/lost/degraded)와 클라이언트 시뮬레이션 상태를 정확히 분리 표기한다', () => {
      const TEST_NODES: NodeItem[] = [
        {
          id: 'nod_offline_01',
          hostname: 'node-offline-01',
          os: 'windows',
          cpuCores: 8,
          cpuUsagePercent: 10,
          memoryTotalBytes: 32 * 1024 ** 3,
          memoryUsagePercent: 20,
          status: 'offline',
          heartbeatAt: new Date(Date.now() - 75000).toISOString(),
        },
        {
          id: 'nod_lost_02',
          hostname: 'node-lost-02',
          os: 'linux',
          cpuCores: 4,
          cpuUsagePercent: 5,
          memoryTotalBytes: 16 * 1024 ** 3,
          memoryUsagePercent: 10,
          status: 'lost',
          heartbeatAt: null,
        },
        {
          id: 'nod_degraded_03',
          hostname: 'node-degraded-03',
          os: 'linux',
          cpuCores: 16,
          cpuUsagePercent: 50,
          memoryTotalBytes: 64 * 1024 ** 3,
          memoryUsagePercent: 60,
          status: 'degraded',
          heartbeatAt: new Date(Date.now() - 10000).toISOString(),
        },
      ];

      act(() => {
        root.render(<DistributedRecoveryView nodes={TEST_NODES} />);
      });

      // 1. offline 노드 검증
      const cardOffline = container.querySelector('[data-testid="node-card-nod_offline_01"]');
      expect(cardOffline?.textContent).toMatch(/Heartbeat: 7[5-6]s ago/);
      const actualOffline = container.querySelector('[data-testid="node-actual-status-nod_offline_01"]');
      expect(actualOffline).not.toBeNull();
      expect(actualOffline?.textContent).toContain('실제: offline');
      const simOffline = container.querySelector('[data-testid="node-sim-status-nod_offline_01"]');
      expect(simOffline).not.toBeNull();
      expect(simOffline?.textContent).toContain('시뮬레이션: OFFLINE');

      // 2. lost 노드 검증 (하트비트 부재 시 ONLINE으로 둔갑하지 않고 OFFLINE, DOM 'Heartbeat: 미보고' 단언)
      const cardLost = container.querySelector('[data-testid="node-card-nod_lost_02"]');
      expect(cardLost?.textContent).toContain('Heartbeat: 미보고');
      const actualLost = container.querySelector('[data-testid="node-actual-status-nod_lost_02"]');
      expect(actualLost).not.toBeNull();
      expect(actualLost?.textContent).toContain('실제: lost');
      const simLost = container.querySelector('[data-testid="node-sim-status-nod_lost_02"]');
      expect(simLost).not.toBeNull();
      expect(simLost?.textContent).toContain('시뮬레이션: OFFLINE');

      // 3. degraded 노드 검증 (STALE 매핑)
      const actualDegraded = container.querySelector('[data-testid="node-actual-status-nod_degraded_03"]');
      expect(actualDegraded).not.toBeNull();
      expect(actualDegraded?.textContent).toContain('실제: degraded');
      const simDegraded = container.querySelector('[data-testid="node-sim-status-nod_degraded_03"]');
      expect(simDegraded).not.toBeNull();
      expect(simDegraded?.textContent).toContain('시뮬레이션: STALE');
    });

    it('Defect 4: 조작 시 액션 알림창(recovery-action-notice)에 role="status" / "alert" 및 aria-live 속성을 올바르게 적용한다', () => {
      act(() => {
        root.render(<DistributedRecoveryView nodes={MOCK_NODES} />);
      });

      // Network Partition 버튼 클릭 -> 에러 알림 (role="alert", aria-live="assertive")
      const partitionBtn = container.querySelector('[data-testid="simulate-partition-btn"]') as HTMLButtonElement;
      expect(partitionBtn).not.toBeNull();

      act(() => {
        partitionBtn.click();
      });

      const notice = container.querySelector('[data-testid="recovery-action-notice"]');
      expect(notice).not.toBeNull();
      expect(notice?.getAttribute('role')).toBe('alert');
      expect(notice?.getAttribute('aria-live')).toBe('assertive');
      expect(notice?.textContent).toContain('Network partition simulated');

      // 체크아웃 생성 버튼 클릭 -> 정보 알림 (role="status", aria-live="polite")
      const checkoutBtn = container.querySelector('[data-testid="create-checkout-btn"]') as HTMLButtonElement;
      expect(checkoutBtn).not.toBeNull();

      act(() => {
        checkoutBtn.click();
      });

      const infoNotice = container.querySelector('[data-testid="recovery-action-notice"]');
      expect(infoNotice).not.toBeNull();
      expect(infoNotice?.getAttribute('role')).toBe('status');
      expect(infoNotice?.getAttribute('aria-live')).toBe('polite');
    });

    it('Defect 5: 노드 카드에 role="button", tabIndex=0, aria-pressed 속성을 부여하고 키보드(Enter/Space) 조작을 지원한다', () => {
      const TWO_NODES: NodeItem[] = [
        ...MOCK_NODES,
        {
          id: 'nod_test_02',
          hostname: 'node-win-02',
          os: 'linux',
          cpuCores: 8,
          cpuUsagePercent: 15,
          memoryTotalBytes: 32 * 1024 ** 3,
          memoryUsagePercent: 25,
          gpuName: 'NVIDIA RTX 3080',
          gpuCount: 1,
          status: 'online',
          labels: { tier: 'general' },
        },
      ];

      act(() => {
        root.render(<DistributedRecoveryView nodes={TWO_NODES} />);
      });

      const card1 = container.querySelector('[data-testid="node-card-nod_test_01"]');
      const card2 = container.querySelector('[data-testid="node-card-nod_test_02"]');
      expect(card1).not.toBeNull();
      expect(card2).not.toBeNull();

      expect(card1?.getAttribute('role')).toBe('button');
      expect(card1?.getAttribute('tabindex')).toBe('0');
      expect(card1?.getAttribute('aria-pressed')).toBe('true');
      expect(card2?.getAttribute('aria-pressed')).toBe('false');

      // 키보드 Enter 키로 2번 노드 선택
      act(() => {
        card2?.dispatchEvent(new KeyboardEvent('keydown', { key: 'Enter', bubbles: true }));
      });

      expect(card1?.getAttribute('aria-pressed')).toBe('false');
      expect(card2?.getAttribute('aria-pressed')).toBe('true');

      // 키보드 Space 키로 1번 노드 재선택
      act(() => {
        card1?.dispatchEvent(new KeyboardEvent('keydown', { key: ' ', bubbles: true }));
      });

      expect(card1?.getAttribute('aria-pressed')).toBe('true');
      expect(card2?.getAttribute('aria-pressed')).toBe('false');
    });

    it('체크아웃 영역의 recovery-no-checkouts testid와 0400/0600/0700 권한 설명 및 Reconcile 모의 배지를 단언한다', () => {
      act(() => {
        root.render(<DistributedRecoveryView nodes={MOCK_NODES} />);
      });

      // 1. 체크아웃 비어있을 때 recovery-no-checkouts testid 및 실제 view:479 모의 표기 단언
      const noCheckouts = container.querySelector('[data-testid="recovery-no-checkouts"]');
      expect(noCheckouts).not.toBeNull();
      expect(noCheckouts?.textContent).toContain('생성된 시뮬레이션 체크아웃이 없습니다. (모의)');

      // 2. 권한 설명 문구 단언 (ADR-043 원문: 0400 readonly, 0600 file / 0700 dir, 단조 epoch 보증)
      expect(container.textContent).toContain('0400 readonly');
      expect(container.textContent).toContain('0600 file / 0700 dir');
      expect(container.textContent).toContain('단조 epoch 보증');

      // 3. Reconcile 헤더의 모의 표기 및 물리 AC-07 UNMEASURED 단언
      expect(container.textContent).toContain('Cluster Reconciliation Audit Trail (AC-07 모의 복구 시뮬레이션; 물리 AC-07 UNMEASURED)');

      // 4. Drain & Reconcile 실행 후 Reconcile 표의 RECOVERED (모의) 배지 단언 (실제 view:429 drain-reconcile-btn 사용)
      const reconcileBtn = container.querySelector('[data-testid="drain-reconcile-btn"]') as HTMLButtonElement;
      expect(reconcileBtn).not.toBeNull();
      act(() => {
        reconcileBtn.click();
      });

      expect(container.textContent).toContain('RECOVERED (모의)');
      expect(container.textContent).not.toContain('RECOVERY COMPLETE');
    });

    it('nodes=[] 빈 상태 마운트 후 nodes 공급 시 동적으로 뷰를 갱신한다 (root.render([]) -> root.render(nodes))', () => {
      // 1. 빈 노드 배열로 초기 렌더링 -> 실제 view:275 recovery-empty-nodes-screen 표시 확인
      act(() => {
        root.render(<DistributedRecoveryView nodes={[]} />);
      });

      const emptyScreen = container.querySelector('[data-testid="recovery-empty-nodes-screen"]');
      expect(emptyScreen).not.toBeNull();
      expect(emptyScreen?.textContent).toContain('클러스터에 등록된 노드가 없거나 관측 대기 중입니다');
      expect(emptyScreen?.textContent).toContain('0대 또는 관측 수집 대기');
      expect(container.querySelector('[data-testid="node-card-nod_test_01"]')).toBeNull();

      // 2. 후속으로 노드 공급하여 재렌더링 -> recovery-empty-nodes-screen 소멸 및 실제 MOCK_NODES 노드 카드(node-win-01) 노출 확인
      act(() => {
        root.render(<DistributedRecoveryView nodes={MOCK_NODES} />);
      });

      expect(container.querySelector('[data-testid="recovery-empty-nodes-screen"]')).toBeNull();
      const nodeCard = container.querySelector('[data-testid="node-card-nod_test_01"]');
      expect(nodeCard).not.toBeNull();
      expect(nodeCard?.textContent).toContain('node-win-01');
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
