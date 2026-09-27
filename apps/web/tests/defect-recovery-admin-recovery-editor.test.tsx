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
  describe('Priority 4: AdminSecurityConsole 행위자(actor) 실배선 및 세션 부재 0-call 가드', () => {
    it('인증된 currentUser가 주어졌을 때 노드 Drain 요청에 실제 actor 식별자를 전송한다', async () => {
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

      // 3. Drain 액션 버튼 클릭
      const drainBtn = Array.from(container.querySelectorAll('button')).find((b) =>
        b.textContent?.includes('Node Drain')
      );
      expect(drainBtn).toBeDefined();

      await act(async () => {
        drainBtn?.click();
      });

      // 4. apiClient에 하드코딩 'usr_admin_01'이 아니라 실제 로그인 사용자 'usr_actual_admin_77'이 전달되어야 함
      expect(apiClientSpy).toHaveBeenCalledWith(
        '/v1/nodes/nod_test_01/drain',
        expect.objectContaining({
          method: 'POST',
          body: JSON.stringify({
            actor: 'usr_actual_admin_77',
            reason: 'Admin manual maintenance and isolation protocol',
          }),
        })
      );
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

      // 2. Drain 탭으로 이동 후 클릭 시도
      const drainTabBtn = Array.from(container.querySelectorAll('button')).find((b) =>
        b.textContent?.includes('노드 Drain 통제')
      );
      expect(drainTabBtn).toBeDefined();
      act(() => {
        drainTabBtn?.click();
      });

      const drainBtn = Array.from(container.querySelectorAll('button')).find((b) =>
        b.textContent?.includes('Node Drain')
      );
      expect(drainBtn).toBeDefined();

      await act(async () => {
        drainBtn?.click();
      });

      // 3. 네트워크 0회 호출 가드 검증 (0 network calls)
      expect(apiClientSpy).not.toHaveBeenCalled();

      // 4. 에러 배너 표출 검증
      const drainError = container.querySelector('[data-testid="admin-drain-error-banner"]');
      expect(drainError).not.toBeNull();
      expect(drainError?.textContent).toContain('인증된 관리자 세션이 없습니다');
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
      const actualOffline = container.querySelector('[data-testid="node-actual-status-nod_offline_01"]');
      expect(actualOffline).not.toBeNull();
      expect(actualOffline?.textContent).toContain('실제: offline');
      const simOffline = container.querySelector('[data-testid="node-sim-status-nod_offline_01"]');
      expect(simOffline).not.toBeNull();
      expect(simOffline?.textContent).toContain('시뮬레이션: OFFLINE');

      // 2. lost 노드 검증 (하트비트 부재 시 ONLINE으로 둔갑하지 않고 OFFLINE)
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

    it('Defect 5: 노드 카드에 role="button", tabIndex=0, aria-pressed, aria-current 속성을 부여하고 키보드(Enter/Space) 조작을 지원한다', () => {
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
      expect(card1?.getAttribute('aria-current')).toBe('true');
      expect(card2?.getAttribute('aria-pressed')).toBe('false');
      expect(card2?.getAttribute('aria-current')).toBe('false');

      // 키보드 Enter 키로 2번 노드 선택
      act(() => {
        card2?.dispatchEvent(new KeyboardEvent('keydown', { key: 'Enter', bubbles: true }));
      });

      expect(card1?.getAttribute('aria-pressed')).toBe('false');
      expect(card1?.getAttribute('aria-current')).toBe('false');
      expect(card2?.getAttribute('aria-pressed')).toBe('true');
      expect(card2?.getAttribute('aria-current')).toBe('true');

      // 키보드 Space 키로 1번 노드 재선택
      act(() => {
        card1?.dispatchEvent(new KeyboardEvent('keydown', { key: ' ', bubbles: true }));
      });

      expect(card1?.getAttribute('aria-pressed')).toBe('true');
      expect(card1?.getAttribute('aria-current')).toBe('true');
      expect(card2?.getAttribute('aria-pressed')).toBe('false');
      expect(card2?.getAttribute('aria-current')).toBe('false');
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
