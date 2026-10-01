// @vitest-environment happy-dom
// @ts-ignore
globalThis.IS_REACT_ACT_ENVIRONMENT = true;
import React, { act } from 'react';
import { createRoot, Root } from 'react-dom/client';
import { describe, it, expect, vi, beforeEach, afterEach } from 'vitest';
import {
  AdminSecurityConsole,
  isValidContainmentView,
  isValidContainmentResult,
  isValidUuid,
  isValidNodeId,
} from '../src/features/admin/AdminSecurityConsole';
import type { NodeItem, ContainmentView, ContainmentResult } from '../src/contracts/types';

const MOCK_NODES: NodeItem[] = [
  {
    id: 'nod_01ARZ3NDEKTSV4RRFFQ69G5FAV',
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

  // =========================================================================
  // V3 & V5: Pure Function Contract Validator Unit Tests
  // =========================================================================
  describe('isValidContainmentView pure validator tests', () => {
    it('유효한 ContainmentView 정본 객체를 승인한다', () => {
      expect(isValidContainmentView(VALID_INACTIVE_VIEW)).toBe(true);
      expect(isValidContainmentView(VALID_ACTIVE_VIEW)).toBe(true);
      expect(isValidContainmentView({ ...VALID_INACTIVE_VIEW, nodeId: 'nod_01ARZ3NDEKTSV4RRFFQ69G5FAV' })).toBe(true);
      expect(isValidContainmentView({ ...VALID_INACTIVE_VIEW, nodeStatus: 'offline' })).toBe(true);
      expect(isValidContainmentView({ ...VALID_INACTIVE_VIEW, nodeStatus: 'draining' })).toBe(true);
      expect(isValidContainmentView({ ...VALID_INACTIVE_VIEW, nodeStatus: null })).toBe(true);
      // 경계값: MAX_SAFE_CONTRACT_INTEGER (9007199254740991)
      expect(isValidContainmentView({ ...VALID_INACTIVE_VIEW, version: 9007199254740991 })).toBe(true);
      expect(isValidContainmentView({ ...VALID_INACTIVE_VIEW, activeLeases: 9007199254740991 })).toBe(true);
      expect(isValidContainmentView({ ...VALID_INACTIVE_VIEW, pendingDeliveries: 9007199254740991 })).toBe(true);
      expect(isValidContainmentView({ ...VALID_INACTIVE_VIEW, unsettledRuns: 9007199254740991 })).toBe(true);
    });

    it('필수 필드 누락 및 타입 불일치 반례를 전수 거부한다', () => {
      // 기본 타입 불일치
      expect(isValidContainmentView(null)).toBe(false);
      expect(isValidContainmentView(undefined)).toBe(false);
      expect(isValidContainmentView(123)).toBe(false);
      expect(isValidContainmentView('view')).toBe(false);
      expect(isValidContainmentView([])).toBe(false);
      expect(isValidContainmentView({})).toBe(false);

      // (b) nodeId: Crockford base32 ULID 규격 (^nod_[0-9A-HJKMNP-TV-Z]{26}$) 및 null만 허용
      expect(isValidContainmentView({ ...VALID_INACTIVE_VIEW, nodeId: 123 })).toBe(false);
      expect(isValidContainmentView({ ...VALID_INACTIVE_VIEW, nodeId: '' })).toBe(false);
      expect(isValidContainmentView({ ...VALID_INACTIVE_VIEW, nodeId: 'nod_sec_01' })).toBe(false); // 길이 부족 및 소문자
      expect(isValidContainmentView({ ...VALID_INACTIVE_VIEW, nodeId: 'nod_01ARZ3NDEKTSV4RRFFQ69G5FAI' })).toBe(false); // 금지문자 'I'
      expect(isValidContainmentView({ ...VALID_INACTIVE_VIEW, nodeId: 'nod_01ARZ3NDEKTSV4RRFFQ69G5FAL' })).toBe(false); // 금지문자 'L'
      expect(isValidContainmentView({ ...VALID_INACTIVE_VIEW, nodeId: 'nod_01ARZ3NDEKTSV4RRFFQ69G5FAO' })).toBe(false); // 금지문자 'O'
      expect(isValidContainmentView({ ...VALID_INACTIVE_VIEW, nodeId: 'nod_01ARZ3NDEKTSV4RRFFQ69G5FAU' })).toBe(false); // 금지문자 'U'

      // (c) version: 0 이상 9007199254740991 이하 정수
      expect(isValidContainmentView({ ...VALID_INACTIVE_VIEW, version: -1 })).toBe(false);
      expect(isValidContainmentView({ ...VALID_INACTIVE_VIEW, version: 1.5 })).toBe(false);
      expect(isValidContainmentView({ ...VALID_INACTIVE_VIEW, version: '1' })).toBe(false);
      expect(isValidContainmentView({ ...VALID_INACTIVE_VIEW, version: 9007199254740992 })).toBe(false); // 상한 초과

      // killSwitchActive
      expect(isValidContainmentView({ ...VALID_INACTIVE_VIEW, killSwitchActive: 'true' })).toBe(false);
      expect(isValidContainmentView({ ...VALID_INACTIVE_VIEW, killSwitchActive: null })).toBe(false);

      // nodeStatus enum
      expect(isValidContainmentView({ ...VALID_INACTIVE_VIEW, nodeStatus: 'drained' })).toBe(false);
      expect(isValidContainmentView({ ...VALID_INACTIVE_VIEW, nodeStatus: 'active' })).toBe(false);
      expect(isValidContainmentView({ ...VALID_INACTIVE_VIEW, nodeStatus: 'unknown' })).toBe(false);

      // (c) activeLeases
      expect(isValidContainmentView({ ...VALID_INACTIVE_VIEW, activeLeases: -1 })).toBe(false);
      expect(isValidContainmentView({ ...VALID_INACTIVE_VIEW, activeLeases: 1.2 })).toBe(false);
      expect(isValidContainmentView({ ...VALID_INACTIVE_VIEW, activeLeases: 9007199254740992 })).toBe(false); // 상한 초과

      // (c) pendingDeliveries
      expect(isValidContainmentView({ ...VALID_INACTIVE_VIEW, pendingDeliveries: -1 })).toBe(false);
      expect(isValidContainmentView({ ...VALID_INACTIVE_VIEW, pendingDeliveries: 2.5 })).toBe(false);
      expect(isValidContainmentView({ ...VALID_INACTIVE_VIEW, pendingDeliveries: 9007199254740992 })).toBe(false); // 상한 초과

      // (c) unsettledRuns
      expect(isValidContainmentView({ ...VALID_INACTIVE_VIEW, unsettledRuns: -1 })).toBe(false);
      expect(isValidContainmentView({ ...VALID_INACTIVE_VIEW, unsettledRuns: 3.14 })).toBe(false);
      expect(isValidContainmentView({ ...VALID_INACTIVE_VIEW, unsettledRuns: 9007199254740992 })).toBe(false); // 상한 초과

      // settled
      expect(isValidContainmentView({ ...VALID_INACTIVE_VIEW, settled: 1 })).toBe(false);
      expect(isValidContainmentView({ ...VALID_INACTIVE_VIEW, settled: 'true' })).toBe(false);

      // (a) V5: additionalProperties: false 검증
      expect(isValidContainmentView({ ...VALID_INACTIVE_VIEW, extraProperty: 'malicious' })).toBe(false);
    });
  });

  describe('isValidContainmentResult pure validator tests', () => {
    const validResult: ContainmentResult = {
      requestId: 'c0000000-0000-4000-8000-000000000001',
      operation: 'kill',
      approvalId: '550e8400-e29b-41d4-a716-446655440000',
      control: VALID_ACTIVE_VIEW,
    };

    it('유효한 ContainmentResult 객체를 승인한다', () => {
      expect(isValidContainmentResult(validResult, 'kill', '550e8400-e29b-41d4-a716-446655440000')).toBe(true);
      // 대소문자 무관 일치
      expect(isValidContainmentResult(validResult, 'kill', '550E8400-E29B-41D4-A716-446655440000')).toBe(true);
    });

    it('필드 누락, 의도 불일치, approvalId echo 불일치 및 모순 상태를 전수 거부한다', () => {
      expect(isValidContainmentResult(null, 'kill', '550e8400-e29b-41d4-a716-446655440000')).toBe(false);
      expect(isValidContainmentResult({}, 'kill', '550e8400-e29b-41d4-a716-446655440000')).toBe(false);

      // (d) requestId: RFC 4122 UUID 포맷 검증
      expect(isValidContainmentResult({ ...validResult, requestId: '' }, 'kill', '550e8400-e29b-41d4-a716-446655440000')).toBe(false);
      expect(isValidContainmentResult({ ...validResult, requestId: 'req-001' }, 'kill', '550e8400-e29b-41d4-a716-446655440000')).toBe(false);
      expect(isValidContainmentResult({ ...validResult, requestId: 'not-a-valid-uuid' }, 'kill', '550e8400-e29b-41d4-a716-446655440000')).toBe(false);

      // (d) approvalId: RFC 4122 UUID 포맷 검증
      expect(isValidContainmentResult({ ...validResult, approvalId: 'not-a-valid-uuid' }, 'kill', 'not-a-valid-uuid')).toBe(false);

      // operation mismatch
      expect(isValidContainmentResult({ ...validResult, operation: 'clear' }, 'kill', '550e8400-e29b-41d4-a716-446655440000')).toBe(false);

      // approvalId echo mismatch
      expect(isValidContainmentResult(validResult, 'kill', '11111111-2222-4333-8444-555555555555')).toBe(false);

      // control 누락 / 무효
      expect(isValidContainmentResult({ ...validResult, control: {} as any }, 'kill', '550e8400-e29b-41d4-a716-446655440000')).toBe(false);

      // killSwitchActive 상태 모순: kill 요청인데 false인 경우
      expect(isValidContainmentResult({ ...validResult, control: VALID_INACTIVE_VIEW }, 'kill', '550e8400-e29b-41d4-a716-446655440000')).toBe(false);

      // clear 요청인데 true인 경우
      const clearResult: ContainmentResult = {
        requestId: 'c0000000-0000-4000-8000-000000000002',
        operation: 'clear',
        approvalId: '550e8400-e29b-41d4-a716-446655440000',
        control: VALID_ACTIVE_VIEW, // 모순!
      };
      expect(isValidContainmentResult(clearResult, 'clear', '550e8400-e29b-41d4-a716-446655440000')).toBe(false);

      // (b) Global kill-switch route는 nodeId === null 결속 단언 (nodeId가 null이 아니면 거부)
      expect(
        isValidContainmentResult(
          { ...validResult, control: { ...VALID_ACTIVE_VIEW, nodeId: 'nod_01ARZ3NDEKTSV4RRFFQ69G5FAV' } },
          'kill',
          '550e8400-e29b-41d4-a716-446655440000'
        )
      ).toBe(false);

      // (b) Node-scoped drain 연산의 canonical 승인 및 nodeId 불일치 거부
      const validDrainResult: ContainmentResult = {
        requestId: 'c0000000-0000-4000-8000-000000000003',
        operation: 'drain',
        approvalId: '550e8400-e29b-41d4-a716-446655440000',
        control: {
          ...VALID_INACTIVE_VIEW,
          nodeId: 'nod_01ARZ3NDEKTSV4RRFFQ69G5FAV',
          nodeStatus: 'draining',
        },
      };
      expect(isValidContainmentResult(validDrainResult, 'drain', '550e8400-e29b-41d4-a716-446655440000', 'nod_01ARZ3NDEKTSV4RRFFQ69G5FAV')).toBe(true);
      expect(isValidContainmentResult(validDrainResult, 'drain', '550e8400-e29b-41d4-a716-446655440000', 'nod_01ARZ3NDEKTSV4RRFFQ69G5FAW')).toBe(false);

      // (Codex r4) operation 'drain'인데 nodeStatus 'online'인 모순 응답 거부
      const contradictoryDrainResultOnline: ContainmentResult = {
        ...validDrainResult,
        control: {
          ...validDrainResult.control,
          nodeStatus: 'online',
        },
      };
      expect(isValidContainmentResult(contradictoryDrainResultOnline, 'drain', '550e8400-e29b-41d4-a716-446655440000', 'nod_01ARZ3NDEKTSV4RRFFQ69G5FAV')).toBe(false);

      // (Codex r4) Node-scoped resume 연산의 canonical 승인 및 nodeStatus 'draining'/'drained' 모순 응답 거부
      const validResumeResult: ContainmentResult = {
        requestId: 'c0000000-0000-4000-8000-000000000004',
        operation: 'resume',
        approvalId: '550e8400-e29b-41d4-a716-446655440000',
        control: {
          ...VALID_INACTIVE_VIEW,
          nodeId: 'nod_01ARZ3NDEKTSV4RRFFQ69G5FAV',
          nodeStatus: 'online',
        },
      };
      expect(isValidContainmentResult(validResumeResult, 'resume', '550e8400-e29b-41d4-a716-446655440000', 'nod_01ARZ3NDEKTSV4RRFFQ69G5FAV')).toBe(true);

      // operation 'resume'인데 nodeStatus 'draining'인 모순 응답 거부
      const contradictoryResumeResultDraining: ContainmentResult = {
        ...validResumeResult,
        control: {
          ...validResumeResult.control,
          nodeStatus: 'draining',
        },
      };
      expect(isValidContainmentResult(contradictoryResumeResultDraining, 'resume', '550e8400-e29b-41d4-a716-446655440000', 'nod_01ARZ3NDEKTSV4RRFFQ69G5FAV')).toBe(false);

      // operation 'resume'인데 nodeStatus 'drained'인 모순 응답 거부
      const contradictoryResumeResultDrained: any = {
        ...validResumeResult,
        control: {
          ...validResumeResult.control,
          nodeStatus: 'drained',
        },
      };
      expect(isValidContainmentResult(contradictoryResumeResultDrained, 'resume', '550e8400-e29b-41d4-a716-446655440000', 'nod_01ARZ3NDEKTSV4RRFFQ69G5FAV')).toBe(false);

      // (d) 공백 포함 approvalId 거부 (whitespace rejection)
      expect(
        isValidContainmentResult(
          { ...validResult, approvalId: ' 550e8400-e29b-41d4-a716-446655440000 ' },
          'kill',
          '550e8400-e29b-41d4-a716-446655440000'
        )
      ).toBe(false);

      // (d) 공백 포함 requestId 거부
      expect(
        isValidContainmentResult(
          { ...validResult, requestId: ' c0000000-0000-4000-8000-000000000001 ' },
          'kill',
          '550e8400-e29b-41d4-a716-446655440000'
        )
      ).toBe(false);

      // (a) additionalProperties: false 위반
      expect(isValidContainmentResult({ ...validResult, extraField: 'bad' }, 'kill', '550e8400-e29b-41d4-a716-446655440000')).toBe(false);
    });
  });

  describe('isValidUuid & isValidNodeId pure strict format tests', () => {
    it('공백이 포함된 UUID는 원천 거부한다 (leading/trailing whitespace rejection)', () => {
      expect(isValidUuid('550e8400-e29b-41d4-a716-446655440000')).toBe(true);
      expect(isValidUuid(' 550e8400-e29b-41d4-a716-446655440000')).toBe(false);
      expect(isValidUuid('550e8400-e29b-41d4-a716-446655440000 ')).toBe(false);
      expect(isValidUuid('550e8400-e29b-41d4-a716-446655440000\n')).toBe(false);
      expect(isValidUuid('\t550e8400-e29b-41d4-a716-446655440000')).toBe(false);
      expect(isValidUuid('')).toBe(false);
      expect(isValidUuid(null)).toBe(false);
    });

    it('공백이 포함된 NodeId는 원천 거부한다 (leading/trailing whitespace rejection)', () => {
      expect(isValidNodeId('nod_01ARZ3NDEKTSV4RRFFQ69G5FAV')).toBe(true);
      expect(isValidNodeId(' nod_01ARZ3NDEKTSV4RRFFQ69G5FAV')).toBe(false);
      expect(isValidNodeId('nod_01ARZ3NDEKTSV4RRFFQ69G5FAV ')).toBe(false);
      expect(isValidNodeId('nod_01ARZ3NDEKTSV4RRFFQ69G5FAV\n')).toBe(false);
      expect(isValidNodeId('\tnod_01ARZ3NDEKTSV4RRFFQ69G5FAV')).toBe(false);
      expect(isValidNodeId('')).toBe(false);
      expect(isValidNodeId(null)).toBe(false);
    });
  });

  // =========================================================================
  // V2: Real apiClient & globalThis.fetch Mock Testing
  // =========================================================================
  function mockFetch(handler: (url: string, init?: RequestInit) => { status: number; body: unknown }) {
    return vi.spyOn(globalThis, 'fetch').mockImplementation(async (input: RequestInfo | URL, init?: RequestInit) => {
      const url = typeof input === 'string' ? input : input instanceof URL ? input.toString() : (input as Request).url;
      const res = handler(url, init);
      const isProblem = res.status >= 400 && res.body && typeof res.body === 'object' && 'type' in (res.body as any);
      const contentType = isProblem ? 'application/problem+json' : 'application/json';
      return new Response(JSON.stringify(res.body), {
        status: res.status,
        headers: { 'Content-Type': contentType },
      });
    });
  }

  it('비상 정지가 비활성 상태일 때 긴급 발동 확정 시 POST /v1/operations/kill-switch (202 Accepted)와 Idempotency-Key, expectedVersion, reasonCode, approvalId를 전송하고 활성 상태로 갱신한다', async () => {
    let capturedUrl: string | null = null;
    let capturedInit: RequestInit | undefined = undefined;

    mockFetch((url, init) => {
      if (url === '/v1/operations/kill-switch' && (!init?.method || init.method === 'GET')) {
        return { status: 200, body: VALID_INACTIVE_VIEW };
      }
      if (url === '/v1/operations/kill-switch' && init?.method === 'POST') {
        capturedUrl = url;
        capturedInit = init;
        const res: ContainmentResult = {
          requestId: '00000000-0000-4000-8000-000000000001',
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
        return { status: 202, body: res };
      }
      return { status: 404, body: {} };
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

    // 2. 비상 정지 토글 버튼 클릭하여 확인 모달 오픈
    const toggleBtn = container.querySelector('[data-testid="emergency-kill-switch-toggle-btn"]') as HTMLButtonElement;
    expect(toggleBtn).not.toBeNull();
    await act(async () => {
      toggleBtn.click();
    });

    const modal = container.querySelector('[data-testid="kill-switch-modal"]');
    expect(modal).not.toBeNull();

    // 3. 파라미터 요약 검증
    const paramsSummary = container.querySelector('[data-testid="kill-switch-params-summary"]');
    expect(paramsSummary?.textContent).toContain('incident');
    expect(paramsSummary?.textContent).toContain('11111111-2222-4333-8444-555555555555');

    // 4. 긴급 발동 확정 버튼 클릭
    const confirmBtn = container.querySelector('[data-testid="kill-switch-confirm-btn"]') as HTMLButtonElement;
    expect(confirmBtn.textContent).toContain('긴급 발동 확정');
    expect(confirmBtn.disabled).toBe(false);

    await act(async () => {
      confirmBtn.click();
    });

    // 5. 실배선 네트워크 전송 규격 단언
    expect(capturedUrl).toBe('/v1/operations/kill-switch');
    expect(capturedInit?.method).toBe('POST');
    const headers = capturedInit?.headers as Headers;
    expect(headers.get('Idempotency-Key')).toMatch(/^killswitch_/);
    expect(headers.get('Content-Type')).toBe('application/json');

    const sentPayload = JSON.parse(capturedInit?.body as string);
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
    let capturedUrl: string | null = null;
    let capturedInit: RequestInit | undefined = undefined;

    mockFetch((url, init) => {
      if (url === '/v1/operations/kill-switch' && (!init?.method || init.method === 'GET')) {
        return { status: 200, body: VALID_ACTIVE_VIEW };
      }
      if (url === '/v1/operations/kill-switch/clear' && init?.method === 'POST') {
        capturedUrl = url;
        capturedInit = init;
        const res: ContainmentResult = {
          requestId: '00000000-0000-4000-8000-000000000002',
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
        return { status: 200, body: res };
      }
      return { status: 404, body: {} };
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

    expect(capturedUrl).toBe('/v1/operations/kill-switch/clear');
    expect(capturedInit?.method).toBe('POST');
    const sentPayload = JSON.parse(capturedInit?.body as string);
    expect(sentPayload).toEqual({
      expectedVersion: 8,
      reasonCode: 'operator_request',
      approvalId: '22222222-3333-4444-8555-666666666666',
    });

    expect(container.querySelector('[data-testid="kill-switch-active-banner"]')).toBeNull();
    expect(backendStatus?.textContent).toContain('INACTIVE (v9)');
  });

  // =========================================================================
  // V2 음성 시험: 잘못된 HTTP Status(clear에 202 또는 500)에서 실패
  // =========================================================================
  it('clear 요청 시 서버가 202 Accepted(잘못된 status)를 반환하면 클라이언트 expectedStatus=200 검사로 실패하고 상태를 갱신하지 않는다', async () => {
    mockFetch((url, init) => {
      if (url === '/v1/operations/kill-switch' && (!init?.method || init.method === 'GET')) {
        return { status: 200, body: VALID_ACTIVE_VIEW };
      }
      if (url === '/v1/operations/kill-switch/clear' && init?.method === 'POST') {
        // 잘못된 status: clear인데 200이 아닌 202 Accepted 반환
        return {
          status: 202,
          body: {
            requestId: 'req-002',
            operation: 'clear',
            approvalId: '22222222-3333-4444-8555-666666666666',
            control: { ...VALID_INACTIVE_VIEW, version: 9 },
          },
        };
      }
      return { status: 404, body: {} };
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
      nativeSetter?.call(approvalInput, '22222222-3333-4444-8555-666666666666');
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

    // 에러 배너에 Unexpected status code 표시 단언
    const errorBanner = container.querySelector('[data-testid="kill-switch-error-banner"]');
    expect(errorBanner?.textContent).toContain('Unexpected status code');

    // 상태 미변경 유지
    const backendStatus = container.querySelector('[data-testid="backend-kill-switch-status"]');
    expect(backendStatus?.textContent).toContain('ACTIVE (v8)');
  });

  it('clear 요청 시 서버가 500 Internal Server Error를 반환하면 에러 배너를 표출하고 상태를 변경하지 않는다', async () => {
    mockFetch((url, init) => {
      if (url === '/v1/operations/kill-switch' && (!init?.method || init.method === 'GET')) {
        return { status: 200, body: VALID_ACTIVE_VIEW };
      }
      if (url === '/v1/operations/kill-switch/clear' && init?.method === 'POST') {
        return {
          status: 500,
          body: {
            type: 'about:blank',
            title: 'Internal Server Error',
            status: 500,
            code: 'SRV-0500',
            category: 'SRV',
            detail: 'Database write barrier timeout',
            retryable: true,
            traceId: '0123456789abcdef0123456789abcdef',
            causeRef: null,
            evidenceId: null,
          },
        };
      }
      return { status: 404, body: {} };
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
      nativeSetter?.call(approvalInput, '22222222-3333-4444-8555-666666666666');
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
    expect(errorBanner?.textContent).toContain('SRV-0500');
    expect(errorBanner?.textContent).toContain('Database write barrier timeout');

    const backendStatus = container.querySelector('[data-testid="backend-kill-switch-status"]');
    expect(backendStatus?.textContent).toContain('ACTIVE (v8)');
  });

  // =========================================================================
  // Review Point (1): GET ContainmentView 계약 검증 실패 / 로딩 시 쓰기 비활성화 (fail-closed)
  // =========================================================================
  it('GET /v1/operations/kill-switch 응답이 부분 응답이거나 필수 필드(version 등) 누락 시 오류를 표시하고 확정 버튼을 비활성화한다 (fail-closed)', async () => {
    mockFetch((url) => {
      if (url === '/v1/operations/kill-switch') {
        // version 및 canonical 필드 누락 부분 응답
        return { status: 200, body: { killSwitchActive: false } };
      }
      return { status: 404, body: {} };
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
    mockFetch((url, init) => {
      if (url === '/v1/operations/kill-switch' && (!init?.method || init.method === 'GET')) {
        getCallCount++;
        return { status: 200, body: VALID_INACTIVE_VIEW };
      }
      if (url === '/v1/operations/kill-switch' && init?.method === 'POST') {
        // 위장: control 누락 빈 객체
        return { status: 202, body: {} };
      }
      return { status: 404, body: {} };
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

    const errorBanner = container.querySelector('[data-testid="kill-switch-error-banner"]');
    expect(errorBanner?.textContent).toContain('[CONTRACT-MISMATCH]');

    // 상태 미변경 단언
    expect(container.querySelector('[data-testid="kill-switch-active-banner"]')).toBeNull();

    // 재조회 호출 실측 (GET이 다시 호출됨)
    expect(getCallCount).toBe(2);
  });

  it('POST 응답의 operation이 요청 의도와 불일치하거나 killSwitchActive가 모순된 경우 계약 불일치로 거부한다', async () => {
    mockFetch((url, init) => {
      if (url === '/v1/operations/kill-switch' && (!init?.method || init.method === 'GET')) {
        return { status: 200, body: VALID_INACTIVE_VIEW };
      }
      if (url === '/v1/operations/kill-switch' && init?.method === 'POST') {
        // kill 요청인데 operation이 clear로 오거나 killSwitchActive가 false인 모순
        return {
          status: 202,
          body: {
            requestId: 'req-bad',
            operation: 'clear', // mismatch!
            approvalId: '550e8400-e29b-41d4-a716-446655440000',
            control: {
              ...VALID_INACTIVE_VIEW,
              killSwitchActive: false, // contradiction!
            },
          },
        };
      }
      return { status: 404, body: {} };
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
    let postCallCount = 0;
    mockFetch((url, init) => {
      if (url === '/v1/operations/kill-switch' && (!init?.method || init.method === 'GET')) {
        return { status: 200, body: VALID_INACTIVE_VIEW };
      }
      if (init?.method === 'POST') {
        postCallCount++;
        return { status: 200, body: {} };
      }
      return { status: 404, body: {} };
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
    expect(postCallCount).toBe(0);
  });

  it('비상 정지 API 409 GRAPH-0003 충돌 발생 시 에러 배너에 RFC 9457 ProblemDetails를 표시하고 모달을 닫지 않는다', async () => {
    mockFetch((url, init) => {
      if (url === '/v1/operations/kill-switch' && (!init?.method || init.method === 'GET')) {
        return { status: 200, body: VALID_INACTIVE_VIEW };
      }
      if (url === '/v1/operations/kill-switch' && init?.method === 'POST') {
        const problem = {
          type: 'about:blank',
          title: 'Control version conflict: expected version 5 differs from server',
          status: 409,
          code: 'GRAPH-0003',
          category: 'GRAPH',
          detail: 'Expected version 5 does not match current version 7',
          retryable: false,
          traceId: '0123456789abcdef0123456789abcdef',
          causeRef: null,
          evidenceId: null,
        };
        return { status: 409, body: problem };
      }
      return { status: 404, body: {} };
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

    // 모달이 닫히지 않고 에러 배너를 표출하는지 확인
    const modal = container.querySelector('[data-testid="kill-switch-modal"]');
    expect(modal).not.toBeNull();

    const errorBanner = container.querySelector('[data-testid="kill-switch-error-banner"]');
    expect(errorBanner).not.toBeNull();
    expect(errorBanner?.textContent).toContain('GRAPH-0003');
    expect(errorBanner?.textContent).toContain('Expected version 5 does not match current version 7');
  });

  it('비상 정지 API 403 AUTH-0062 거부 시 에러 배너에 RFC 9457 ProblemDetails를 정직하게 표시한다', async () => {
    mockFetch((url, init) => {
      if (url === '/v1/operations/kill-switch' && (!init?.method || init.method === 'GET')) {
        return { status: 200, body: VALID_INACTIVE_VIEW };
      }
      if (url === '/v1/operations/kill-switch' && init?.method === 'POST') {
        const problem = {
          type: 'about:blank',
          title: 'Forbidden: Insufficient privileges for emergency kill-switch',
          status: 403,
          code: 'AUTH-0062',
          category: 'AUTH',
          detail: 'Actor usr_sec_admin lacks cluster:emergency permission',
          retryable: false,
          traceId: '0123456789abcdef0123456789abcdef',
          causeRef: null,
          evidenceId: null,
        };
        return { status: 403, body: problem };
      }
      return { status: 404, body: {} };
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
    expect(errorBanner?.textContent).toContain('AUTH-0062');
    expect(errorBanner?.textContent).toContain('Actor usr_sec_admin lacks cluster:emergency permission');
  });

  it('currentUser가 null인 경우 비상 정지 토글 및 확정 버튼이 원천 비활성화된다', async () => {
    mockFetch((url) => {
      if (url === '/v1/operations/kill-switch') {
        return { status: 200, body: VALID_INACTIVE_VIEW };
      }
      return { status: 404, body: {} };
    });

    await act(async () => {
      root.render(
        <AdminSecurityConsole
          nodes={MOCK_NODES}
          currentUser={null}
        />
      );
    });

    const toggleBtn = container.querySelector('[data-testid="emergency-kill-switch-toggle-btn"]') as HTMLButtonElement;
    expect(toggleBtn.disabled).toBe(true);
    expect(toggleBtn.getAttribute('aria-disabled')).toBe('true');
  });

  // =========================================================================
  // V1 음성 시험: Node Control Pre-query Contract Validation (V1)
  // =========================================================================
  it('V1: Drain 통제 시 node control(/control) 응답이 canonical 규격(enum nodeStatus 등) 불일치 시 fail-closed 중단하고 POST를 0회로 차단한다', async () => {
    let drainPostCallCount = 0;
    mockFetch((url, init) => {
      if (url === '/v1/operations/kill-switch') {
        return { status: 200, body: VALID_INACTIVE_VIEW };
      }
      if (url.includes('/control')) {
        // V1 결함 반례: nodeStatus가 정본 enum('online','offline','draining','quarantined') 밖의 'drained'로 오거나 필수 필드 누락
        return {
          status: 200,
          body: {
            ...VALID_INACTIVE_VIEW,
            nodeStatus: 'drained', // INVALID ENUM!
          },
        };
      }
      if (url.includes('/drain')) {
        drainPostCallCount++;
        return { status: 200, body: {} };
      }
      return { status: 404, body: {} };
    });

    await act(async () => {
      root.render(
        <AdminSecurityConsole
          nodes={MOCK_NODES}
          currentUser={{ id: 'usr_sec_admin', name: 'Sec Admin', role: 'admin' }}
        />
      );
    });

    // Drain 통제 탭으로 이동
    const drainTabBtn = Array.from(container.querySelectorAll('button')).find((b) =>
      b.textContent?.includes('노드 Drain 통제')
    );
    await act(async () => {
      drainTabBtn?.click();
    });

    // 유효한 승인 ID 입력
    const drainApprovalInput = container.querySelector('[data-testid="drain-approval-id-input"]') as HTMLInputElement;
    await act(async () => {
      const nativeSetter = Object.getOwnPropertyDescriptor(window.HTMLInputElement.prototype, 'value')?.set;
      nativeSetter?.call(drainApprovalInput, '550e8400-e29b-41d4-a716-446655440000');
      drainApprovalInput.dispatchEvent(new Event('input', { bubbles: true }));
      drainApprovalInput.dispatchEvent(new Event('change', { bubbles: true }));
    });

    // Drain 실행 클릭
    const drainBtn = Array.from(container.querySelectorAll('button')).find((b) =>
      b.textContent?.includes('Node Drain')
    ) as HTMLButtonElement;
    expect(drainBtn).not.toBeNull();

    await act(async () => {
      drainBtn.click();
    });

    // V1 fail-closed 단언: 에러 배너 표출 및 drain POST 0회 호출
    const banner = container.querySelector('[data-testid="admin-drain-error-banner"]');
    expect(banner).not.toBeNull();
    expect(banner?.textContent).toContain('응답 형식 또는 nodeId 불일치로 작업을 중단했습니다 (fail-closed)');
    expect(drainPostCallCount).toBe(0);
  });

  // =========================================================================
  // Codex r3 Negative Tests (Mismatched Node, Whitespace UUID, Strict ContainmentResult)
  // =========================================================================
  it('Codex r3: /control 사전 조회 시 ctrl.nodeId가 대상 노드와 불일치하면 fail-closed 중단하고 POST를 0회로 차단한다', async () => {
    let drainPostCallCount = 0;
    mockFetch((url) => {
      if (url === '/v1/operations/kill-switch') {
        return { status: 200, body: VALID_INACTIVE_VIEW };
      }
      if (url.includes('/control')) {
        return {
          status: 200,
          body: {
            ...VALID_INACTIVE_VIEW,
            nodeId: 'nod_01ARZ3NDEKTSV4RRFFQ69G5FAW', // 다른 노드 ID 반환 (위장/오류)!
            nodeStatus: 'online',
          },
        };
      }
      if (url.includes('/drain')) {
        drainPostCallCount++;
        return { status: 200, body: {} };
      }
      return { status: 404, body: {} };
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

    const drainApprovalInput = container.querySelector('[data-testid="drain-approval-id-input"]') as HTMLInputElement;
    await act(async () => {
      const nativeSetter = Object.getOwnPropertyDescriptor(window.HTMLInputElement.prototype, 'value')?.set;
      nativeSetter?.call(drainApprovalInput, '550e8400-e29b-41d4-a716-446655440000');
      drainApprovalInput.dispatchEvent(new Event('input', { bubbles: true }));
      drainApprovalInput.dispatchEvent(new Event('change', { bubbles: true }));
    });

    const drainBtn = Array.from(container.querySelectorAll('button')).find((b) =>
      b.textContent?.includes('Node Drain')
    ) as HTMLButtonElement;

    await act(async () => {
      drainBtn.click();
    });

    const banner = container.querySelector('[data-testid="admin-drain-error-banner"]');
    expect(banner).not.toBeNull();
    expect(banner?.textContent).toContain('nodeId 불일치로 작업을 중단했습니다 (fail-closed)');
    expect(drainPostCallCount).toBe(0);
  });

  it('Codex r3: drain POST 응답이 다른 노드(mismatched nodeId)의 control을 포함하거나 규격 불일치 시 fail-closed 중단하고 로컬 상태를 변경하지 않는다', async () => {
    mockFetch((url) => {
      if (url === '/v1/operations/kill-switch') {
        return { status: 200, body: VALID_INACTIVE_VIEW };
      }
      if (url.includes('/control')) {
        return {
          status: 200,
          body: {
            ...VALID_INACTIVE_VIEW,
            nodeId: 'nod_01ARZ3NDEKTSV4RRFFQ69G5FAV', // 정상 대상 노드
            nodeStatus: 'online',
          },
        };
      }
      if (url.includes('/drain')) {
        // 위장 응답: 다른 노드의 control 객체 포함
        return {
          status: 200,
          body: {
            requestId: 'c0000000-0000-4000-8000-000000000001',
            operation: 'drain',
            approvalId: '550e8400-e29b-41d4-a716-446655440000',
            control: {
              ...VALID_INACTIVE_VIEW,
              nodeId: 'nod_01ARZ3NDEKTSV4RRFFQ69G5FAW', // 다른 노드!
              nodeStatus: 'draining',
            },
          },
        };
      }
      return { status: 404, body: {} };
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

    const drainApprovalInput = container.querySelector('[data-testid="drain-approval-id-input"]') as HTMLInputElement;
    await act(async () => {
      const nativeSetter = Object.getOwnPropertyDescriptor(window.HTMLInputElement.prototype, 'value')?.set;
      nativeSetter?.call(drainApprovalInput, '550e8400-e29b-41d4-a716-446655440000');
      drainApprovalInput.dispatchEvent(new Event('input', { bubbles: true }));
      drainApprovalInput.dispatchEvent(new Event('change', { bubbles: true }));
    });

    const drainBtn = Array.from(container.querySelectorAll('button')).find((b) =>
      b.textContent?.includes('Node Drain')
    ) as HTMLButtonElement;

    await act(async () => {
      drainBtn.click();
    });

    const banner = container.querySelector('[data-testid="admin-drain-error-banner"]');
    expect(banner).not.toBeNull();
    expect(banner?.textContent).toContain('ContainmentResult 규격 불일치');

    // 로컬 상태가 변경되지 않았음을 단언 (버튼 텍스트가 Resume으로 바뀌지 않고 여전히 Drain이어야 함)
    const drainBtnAfter = Array.from(container.querySelectorAll('button')).find((b) =>
      b.textContent?.includes('Node Drain')
    );
    expect(drainBtnAfter).not.toBeNull();
  });

  it('Codex r3: 공백이 포함된 drain approvalId 입력 시 유효성 검증 실패로 사전 조회 및 POST를 0회로 차단한다', async () => {
    let fetchCallCount = 0;
    mockFetch((url) => {
      if (url === '/v1/operations/kill-switch') {
        return { status: 200, body: VALID_INACTIVE_VIEW };
      }
      fetchCallCount++;
      return { status: 200, body: {} };
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

    // 공백 포함 approvalId 주입
    const drainApprovalInput = container.querySelector('[data-testid="drain-approval-id-input"]') as HTMLInputElement;
    await act(async () => {
      const nativeSetter = Object.getOwnPropertyDescriptor(window.HTMLInputElement.prototype, 'value')?.set;
      nativeSetter?.call(drainApprovalInput, ' 550e8400-e29b-41d4-a716-446655440000 ');
      drainApprovalInput.dispatchEvent(new Event('input', { bubbles: true }));
      drainApprovalInput.dispatchEvent(new Event('change', { bubbles: true }));
    });

    const drainNotice = container.querySelector('[data-testid="drain-approval-required-notice"]');
    expect(drainNotice).not.toBeNull();
    expect(drainNotice?.textContent).toContain('유효한 Containment 승인 UUID(UUIDv4) 입력이 필수입니다');

    const drainBtn = Array.from(container.querySelectorAll('button')).find((b) =>
      b.textContent?.includes('Node Drain')
    ) as HTMLButtonElement;
    expect(drainBtn).not.toBeNull();
    expect(drainBtn.disabled).toBe(true);

    await act(async () => {
      drainBtn.click();
    });

    expect(fetchCallCount).toBe(0);
  });

  it('Codex r4: operation "drain" 실행 시 서버가 nodeStatus "online"인 모순 응답을 반환하면 fail-closed 에러를 표출하고 로컬 상태를 변경하지 않는다', async () => {
    mockFetch((url) => {
      if (url === '/v1/operations/kill-switch') {
        return { status: 200, body: VALID_INACTIVE_VIEW };
      }
      if (url.includes('/control')) {
        return {
          status: 200,
          body: {
            ...VALID_INACTIVE_VIEW,
            nodeId: 'nod_01ARZ3NDEKTSV4RRFFQ69G5FAV',
            nodeStatus: 'online',
            version: 7,
          },
        };
      }
      if (url.includes('/drain')) {
        // 모순 응답: operation은 drain인데 nodeStatus는 online!
        return {
          status: 200,
          body: {
            requestId: 'c0000000-0000-4000-8000-000000000001',
            operation: 'drain',
            approvalId: '550e8400-e29b-41d4-a716-446655440000',
            control: {
              ...VALID_INACTIVE_VIEW,
              nodeId: 'nod_01ARZ3NDEKTSV4RRFFQ69G5FAV',
              nodeStatus: 'online', // 모순!
              version: 8,
            },
          },
        };
      }
      return { status: 404, body: {} };
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

    const drainApprovalInput = container.querySelector('[data-testid="drain-approval-id-input"]') as HTMLInputElement;
    await act(async () => {
      const nativeSetter = Object.getOwnPropertyDescriptor(window.HTMLInputElement.prototype, 'value')?.set;
      nativeSetter?.call(drainApprovalInput, '550e8400-e29b-41d4-a716-446655440000');
      drainApprovalInput.dispatchEvent(new Event('input', { bubbles: true }));
      drainApprovalInput.dispatchEvent(new Event('change', { bubbles: true }));
    });

    const drainBtn = Array.from(container.querySelectorAll('button')).find((b) =>
      b.textContent?.includes('Node Drain')
    ) as HTMLButtonElement;

    await act(async () => {
      drainBtn.click();
    });

    const banner = container.querySelector('[data-testid="admin-drain-error-banner"]');
    expect(banner).not.toBeNull();
    expect(banner?.textContent).toContain('ContainmentResult 규격 불일치');

    // 로컬 상태가 변경되지 않았음을 단언 (여전히 Node Drain 버튼 노출)
    const drainBtnAfter = Array.from(container.querySelectorAll('button')).find((b) =>
      b.textContent?.includes('Node Drain')
    );
    expect(drainBtnAfter).not.toBeNull();
  });

  it('Codex r4: operation "resume" 실행 시 서버가 nodeStatus "draining"인 모순 응답을 반환하면 fail-closed 에러를 표출하고 로컬 상태를 변경하지 않는다', async () => {
    // 노드가 이미 draining 상태인 노드 목록
    const DRAINING_NODES: NodeItem[] = [
      {
        ...MOCK_NODES[0],
        status: 'draining',
      },
    ];

    mockFetch((url) => {
      if (url === '/v1/operations/kill-switch') {
        return { status: 200, body: VALID_INACTIVE_VIEW };
      }
      if (url.includes('/control')) {
        return {
          status: 200,
          body: {
            ...VALID_INACTIVE_VIEW,
            nodeId: 'nod_01ARZ3NDEKTSV4RRFFQ69G5FAV',
            nodeStatus: 'draining',
            version: 7,
          },
        };
      }
      if (url.includes('/resume')) {
        // 모순 응답: operation은 resume인데 nodeStatus는 draining!
        return {
          status: 200,
          body: {
            requestId: 'c0000000-0000-4000-8000-000000000002',
            operation: 'resume',
            approvalId: '550e8400-e29b-41d4-a716-446655440000',
            control: {
              ...VALID_INACTIVE_VIEW,
              nodeId: 'nod_01ARZ3NDEKTSV4RRFFQ69G5FAV',
              nodeStatus: 'draining', // 모순!
              version: 8,
            },
          },
        };
      }
      return { status: 404, body: {} };
    });

    await act(async () => {
      root.render(
        <AdminSecurityConsole
          nodes={DRAINING_NODES}
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

    const drainApprovalInput = container.querySelector('[data-testid="drain-approval-id-input"]') as HTMLInputElement;
    await act(async () => {
      const nativeSetter = Object.getOwnPropertyDescriptor(window.HTMLInputElement.prototype, 'value')?.set;
      nativeSetter?.call(drainApprovalInput, '550e8400-e29b-41d4-a716-446655440000');
      drainApprovalInput.dispatchEvent(new Event('input', { bubbles: true }));
      drainApprovalInput.dispatchEvent(new Event('change', { bubbles: true }));
    });

    const resumeBtn = (container.querySelector(`[data-testid="drain-node-btn-${DRAINING_NODES[0].id}"]`) ||
      Array.from(container.querySelectorAll('button')).find((b) =>
        b.textContent?.includes('Drain 해제')
      )) as HTMLButtonElement;
    expect(resumeBtn).not.toBeNull();

    await act(async () => {
      resumeBtn.click();
    });

    const banner = container.querySelector('[data-testid="admin-drain-error-banner"]');
    expect(banner).not.toBeNull();
    expect(banner?.textContent).toContain('ContainmentResult 규격 불일치');

    // 로컬 상태가 변경되지 않았음을 단언 (여전히 Drain 해제 버튼 노출)
    const resumeBtnAfter = container.querySelector(`[data-testid="drain-node-btn-${DRAINING_NODES[0].id}"]`);
    expect(resumeBtnAfter?.textContent).toContain('Drain 해제');
  });
});
