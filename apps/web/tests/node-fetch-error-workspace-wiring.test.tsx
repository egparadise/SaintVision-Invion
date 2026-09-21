// @vitest-environment happy-dom
// @ts-ignore
globalThis.IS_REACT_ACT_ENVIRONMENT = true;
import React, { act } from 'react';
import { createRoot, Root } from 'react-dom/client';
import { describe, it, expect, vi, beforeEach, afterEach } from 'vitest';
import { ResourceExplorer } from '../src/features/desktop/ResourceExplorer';
import { WorkspaceList } from '../src/features/workspaces/WorkspaceList';
import { WorkspaceCreateModal } from '../src/features/workspaces/WorkspaceCreateModal';
import { NaturalLanguageRunView } from '../src/features/agent/NaturalLanguageRunView';
import { createProjectWorkspace } from '../src/shared/api/projectObservation';
import * as client from '../src/shared/api/client';
import type { WorkspaceItem } from '../src/contracts/types';
import type { WorkspaceSummaryResponse } from '../src/contracts/project-workspaces-response';

describe('화면 결함 5대 부류 치유 트랙 (Priority 1: 노드 에러 은폐 치유, Priority 2: 작업공간 실배선, Priority 3: 자연어 KPI/조기성공 치유)', () => {
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
  // Priority 1: 노드 API 실패 시 에러 은폐 치유 (조회 실패 vs 0대 정상 조회 vs 미조회 3상태 분리)
  // =========================================================================
  describe('Priority 1: 노드 API 실패 시 에러 은폐 치유 (ResourceExplorer)', () => {
    it('노드 조회 실패 시 에러 배너(role=alert)를 표출하고 0대 정상 빈 상태로 오인 은폐하지 않는다', () => {
      const onRetry = vi.fn();

      act(() => {
        root.render(
          <ResourceExplorer
            nodes={[]}
            nodesState="error"
            nodesError="503 Service Unavailable: Node Registry cluster unreachable"
            onRetryNodes={onRetry}
          />
        );
      });

      // 1. 에러 배너는 role="alert"과 함께 표출되어야 함
      const errorBanner = container.querySelector('[data-testid="nodes-fetch-error-banner"]');
      expect(errorBanner).not.toBeNull();
      expect(errorBanner?.getAttribute('role')).toBe('alert');
      expect(errorBanner?.textContent).toContain('물리 노드 레지스트리(GET /v1/nodes) 통신 오류');
      expect(errorBanner?.textContent).toContain('503 Service Unavailable');
      expect(errorBanner?.textContent).toContain('섣부른 노드 재등록이나 장애 조치를 수행하지 마십시오');

      // 2. 재시도 버튼 연결 확인
      const retryBtn = container.querySelector('[data-testid="nodes-retry-btn"]') as HTMLButtonElement;
      expect(retryBtn).not.toBeNull();
      act(() => {
        retryBtn.click();
      });
      expect(onRetry).toHaveBeenCalledTimes(1);

      // 3. 빈 상태(0대 정상 조회)로 속이지 않아야 함
      const emptyState = container.querySelector('[data-testid="nodes-empty-state"]');
      expect(emptyState).toBeNull();

      // 4. 통합 논리 자원 카드에 0 코어 / 0 RAM이 아닌 "조회 실패" 표시
      const vcpuCard = container.querySelector('[data-testid="logical-vcpu-card"]');
      expect(vcpuCard?.textContent).toContain('조회 실패');

      const ramCard = container.querySelector('[data-testid="logical-ram-card"]');
      expect(ramCard?.textContent).toContain('조회 실패');
    });

    it('정상 조회 결과 물리 노드가 0대일 때는 role=status 빈 상태를 표출하고 에러 배너를 노출하지 않는다', () => {
      act(() => {
        root.render(
          <ResourceExplorer
            nodes={[]}
            nodesState="success"
            nodesError={null}
          />
        );
      });

      // 1. 정상 0대 빈 상태 표출
      const emptyState = container.querySelector('[data-testid="nodes-empty-state"]');
      expect(emptyState).not.toBeNull();
      expect(emptyState?.getAttribute('role')).toBe('status');
      expect(emptyState?.textContent).toContain('등록된 물리 노드가 없습니다 (정상 조회 결과: 0대)');

      // 2. 에러 배너는 절대 노출되지 않음
      const errorBanner = container.querySelector('[data-testid="nodes-fetch-error-banner"]');
      expect(errorBanner).toBeNull();
    });

    it('노드 조회가 loading 또는 idle 상태일 때 각각의 대기 표시를 렌더링한다', () => {
      act(() => {
        root.render(
          <ResourceExplorer
            nodes={[]}
            nodesState="loading"
            nodesError={null}
          />
        );
      });
      expect(container.querySelector('[data-testid="nodes-loading-state"]')).not.toBeNull();
      expect(container.querySelector('[data-testid="nodes-fetch-error-banner"]')).toBeNull();
      expect(container.querySelector('[data-testid="nodes-empty-state"]')).toBeNull();

      act(() => {
        root.render(
          <ResourceExplorer
            nodes={[]}
            nodesState="idle"
            nodesError={null}
          />
        );
      });
      expect(container.querySelector('[data-testid="nodes-idle-state"]')).not.toBeNull();
    });
  });

  // =========================================================================
  // Priority 2: 작업공간 생성의 가짜 ID 합성 제거 및 백엔드 실배선
  // =========================================================================
  describe('Priority 2: 작업공간 생성의 가짜 ID 합성 제거 및 실배선', () => {
    it('createProjectWorkspace API가 백엔드 POST /v1/projects/{projectId}/workspaces를 정확한 계약으로 호출한다', async () => {
      const mockWorkspaceResponse: WorkspaceSummaryResponse = {
        workspaceId: 'wsp_srv_actual_uuid_01',
        projectId: 'prj_alpha',
        name: 'real-workspace-01',
        status: 'provisioning',
        nodeId: null,
        toolName: null,
        createdAt: '2026-09-21T14:30:00Z',
        allowedNext: ['ready', 'failed'],
      };

      const apiClientSpy = vi.spyOn(client, 'apiClient').mockResolvedValueOnce(mockWorkspaceResponse);

      const result = await createProjectWorkspace('prj_alpha', 'real-workspace-01');

      expect(apiClientSpy).toHaveBeenCalledWith(
        '/v1/projects/prj_alpha/workspaces',
        expect.objectContaining({
          method: 'POST',
          body: JSON.stringify({ name: 'real-workspace-01' }),
        })
      );
      expect(result.workspaceId).toBe('wsp_srv_actual_uuid_01');
      expect(result.status).toBe('provisioning');
      expect(result.nodeId).toBeNull();
    });

    it('WorkspaceList가 작업공간 0개일 때 workspaces-empty-state(role=status)를 렌더링한다', () => {
      act(() => {
        root.render(
          <WorkspaceList
            workspaces={[]}
            nodes={[]}
            onCreateWorkspace={vi.fn()}
            onSelectWorkspace={vi.fn()}
          />
        );
      });

      const emptyState = container.querySelector('[data-testid="workspaces-empty-state"]');
      expect(emptyState).not.toBeNull();
      expect(emptyState?.getAttribute('role')).toBe('status');
      expect(emptyState?.textContent).toContain('등록된 작업공간이 없습니다 (정상 조회 결과: 0개)');
    });

    it('서버에서 반환된 provisioning 상태의 작업공간을 조기 성공(Active)으로 위장하지 않고 정직하게 표시한다', () => {
      const workspaces: WorkspaceItem[] = [
        {
          id: 'wsp_srv_actual_uuid_01',
          projectId: 'prj_alpha',
          name: 'real-workspace-01',
          targetNodeId: null,
          isolationMode: 'process_sandbox',
          allowedPaths: ['./workspace'],
          prohibitedPaths: ['/etc', 'C:\\Windows', '..'],
          cpuLimitCores: 4,
          memoryLimitBytes: 8 * 1024 ** 3,
          status: 'provisioning',
          createdAt: '2026-09-21T14:30:00Z',
        },
      ];

      act(() => {
        root.render(
          <WorkspaceList
            workspaces={workspaces}
            nodes={[]}
            onCreateWorkspace={vi.fn()}
            onSelectWorkspace={vi.fn()}
          />
        );
      });

      const statusBadge = container.querySelector('[data-testid="wsp-status-wsp_srv_actual_uuid_01"]');
      expect(statusBadge).not.toBeNull();
      // 조기 성공 "활성 (Active)"이 아니라 실제 서버 상태인 "프로비저닝 중 (Provisioning)"이어야 함
      expect(statusBadge?.textContent).toBe('프로비저닝 중 (Provisioning)');
      expect(container.textContent).toContain('배치 노드:');
      expect(container.textContent).toContain('미할당 (Unassigned)');
    });

    it('WorkspaceCreateModal이 생성 단계 고지(role=status)를 표출하고 허위 노드/자원 입력 폼을 배제하며 name만 전송한다', async () => {
      const onCreateMock = vi.fn().mockResolvedValue(undefined);
      const onCloseMock = vi.fn();

      act(() => {
        root.render(
          <WorkspaceCreateModal
            projectId="prj_alpha"
            isOpen={true}
            onClose={onCloseMock}
            onCreate={onCreateMock}
          />
        );
      });

      // 1. 생성 단계 안내 배너(phase notice) 검증
      const phaseNotice = container.querySelector('[data-testid="workspace-create-phase-notice"]');
      expect(phaseNotice).not.toBeNull();
      expect(phaseNotice?.getAttribute('role')).toBe('status');
      expect(phaseNotice?.textContent).toContain('생성 단계 안내 (Phase Notice)');
      expect(phaseNotice?.textContent).toContain('초기 레코드만 등록');
      expect(phaseNotice?.textContent).toContain('실행(Run) 준비(prepare) 커널 단계');

      // 2. 스키마 외 허위 노드 선택기 및 CPU/RAM 조작 폼 부재 검증 (백엔드 extra=forbid 준수)
      const selectElements = container.querySelectorAll('select');
      expect(selectElements.length).toBe(0); // 노드 선택 셀렉트 박스 완전 소거

      const numberInputs = container.querySelectorAll('input[type="number"]');
      expect(numberInputs.length).toBe(0); // 허위 CPU/RAM 입력 박스 완전 소거

      // 3. 작업공간 이름 입력 및 제출 검증
      const nameInput = container.querySelector('[data-testid="workspace-name-input"]') as HTMLInputElement;
      expect(nameInput).not.toBeNull();

      const setInputValue = (input: HTMLInputElement, val: string) => {
        const nativeSetter = Object.getOwnPropertyDescriptor(window.HTMLInputElement.prototype, 'value')?.set;
        nativeSetter?.call(input, val);
        input.dispatchEvent(new Event('input', { bubbles: true }));
      };

      // 2자 미만 입력 시도
      act(() => {
        setInputValue(nameInput, 'a');
      });

      const form = container.querySelector('form') as HTMLFormElement;
      expect(form).not.toBeNull();

      await act(async () => {
        form.dispatchEvent(new Event('submit', { bubbles: true, cancelable: true }));
      });

      // 2자 미만이므로 onCreateMock 미호출 및 role="alert" 에러 표출
      expect(onCreateMock).not.toHaveBeenCalled();
      const alertBox = container.querySelector('[role="alert"]');
      expect(alertBox).not.toBeNull();
      expect(alertBox?.textContent).toContain('작업공간 명칭은 최소 2자 이상이어야 합니다');

      // 정상 명칭 입력 후 제출
      act(() => {
        setInputValue(nameInput, 'valid-workspace-name');
      });

      await act(async () => {
        form.dispatchEvent(new Event('submit', { bubbles: true, cancelable: true }));
      });

      // 오직 { name: 'valid-workspace-name' }만 전달되어야 함 (targetNodeId, cpuLimit 등 가짜 합성 절대 불가)
      expect(onCreateMock).toHaveBeenCalledTimes(1);
      expect(onCreateMock).toHaveBeenCalledWith({
        name: 'valid-workspace-name',
      });
      expect(onCloseMock).toHaveBeenCalledTimes(1);
    });
  });

  // =========================================================================
  // Priority 3: 자연어 에이전트 뷰의 가상 KPI 합성 및 허위 성공 배너 치유
  // =========================================================================
  describe('Priority 3: 자연어 실행 뷰의 가상 KPI 합성 및 허위 성공 배너 치유', () => {
    it('NaturalLanguageRunView가 agent-unexposed-notice(role=status)를 렌더링하고 모의 픽스처임을 명시한다', () => {
      act(() => {
        root.render(<NaturalLanguageRunView />);
      });

      const unexposedNotice = container.querySelector('[data-testid="agent-unexposed-notice"]');
      expect(unexposedNotice).not.toBeNull();
      expect(unexposedNotice?.getAttribute('role')).toBe('status');
      expect(unexposedNotice?.textContent).toContain('자연어 에이전트 실행 및 골든 평가 제어기 (API 미노출)');
      expect(unexposedNotice?.textContent).toContain('엔드포인트(/v1/agent/*)가 배선되어 있지 않습니다');

      // KPI 배너 텍스트가 [AC-09 픽스처 / 로컬 시뮬레이션]으로 정직하게 고지되어 있는지 확인
      expect(container.textContent).toContain('Prompt 100건 유효율 (AC-09 픽스처)');
      expect(container.textContent).toContain('코딩 과제 30건 성공률 (AC-09 픽스처)');
      expect(container.textContent).toContain('목표: ≥99% (로컬 시뮬레이션)');
    });

    it('코드 Diff 적용 시 실제 파일시스템에 기록된 양 허위 성공 배너를 표출하지 않고 모의 적용 고지를 표시한다', () => {
      act(() => {
        root.render(<NaturalLanguageRunView />);
      });

      // 먼저 자연어 Run 요청 제출하여 제안 diff 생성
      const submitBtn = Array.from(container.querySelectorAll('button')).find((b) =>
        b.textContent?.includes('자연어 Run 분석 및 제안 Diff 생성')
      );
      expect(submitBtn).toBeDefined();
      act(() => {
        submitBtn?.click();
      });

      // Diff 적용 버튼 클릭
      const applyBtn = Array.from(container.querySelectorAll('button')).find((b) =>
        b.textContent?.includes('Diff 승인 및 코드 적용')
      );
      expect(applyBtn).toBeDefined();

      act(() => {
        applyBtn?.click();
      });

      // 이전의 "🎉 코드 Diff가 성공적으로 승인 및 적용되었습니다!" 허위 배너가 나오지 않아야 함
      expect(container.textContent).not.toContain('코드 Diff가 성공적으로 승인 및 적용되었습니다');
      // 정직한 안내문 표출 확인
      expect(container.textContent).toContain('코드 Diff 모의 적용 완료: 백엔드 코드 패치 API가 미노출 상태이므로 실제 작업공간 파일시스템에는 기록되지 않았습니다');
    });
  });
});
