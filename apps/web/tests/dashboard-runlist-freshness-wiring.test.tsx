// @vitest-environment happy-dom
// @ts-ignore
globalThis.IS_REACT_ACT_ENVIRONMENT = true;
import React, { act } from 'react';
import { createRoot, Root } from 'react-dom/client';
import { describe, it, expect, beforeEach, afterEach, vi } from 'vitest';
import { ClusterOverview } from '@/features/dashboard/ClusterOverview';
import { RunList } from '@/features/runs/RunList';
import { RunDetail } from '@/features/runs/RunDetail';
import { NodeItem, RunItem } from '@/contracts/types';

(globalThis as any).IS_REACT_ACT_ENVIRONMENT = true;

describe('대시보드(ClusterOverview) 및 RunList/RunDetail 신선도·정직성 배선 검증 (VF-GM)', () => {
  let container: HTMLDivElement;
  let root: Root;

  beforeEach(() => {
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

  const dummyNodes: NodeItem[] = [
    {
      id: 'node_live_01',
      hostname: 'worker-gpu-01.internal',
      ip: '10.0.1.10',
      status: 'online',
      os: 'linux',
      cpuCores: 32,
      cpuUsagePercent: 45,
      memoryTotalBytes: 64 * 1024 ** 3,
      memoryUsedBytes: 32 * 1024 ** 3,
      gpuCount: 2,
      gpuVramTotalBytes: 48 * 1024 ** 3,
      gpuVramUsedBytes: 12 * 1024 ** 3,
      storageTotalBytes: 2 * 1024 ** 4,
      storageUsedBytes: 500 * 1024 ** 3,
      telemetryUnavailable: false,
    },
  ];

  const dummyRuns: RunItem[] = [
    {
      id: 'run_live_01',
      projectId: 'prj_01',
      state: 'running',
      requestedBy: 'usr_operator',
      objective: 'PACS Inference Pipeline',
      createdAt: new Date().toISOString(),
    },
  ];

  // =========================================================================
  // 1. ClusterOverview: 동기화 실패 시 에러 은폐 차단 및 신선도 표출
  // =========================================================================
  describe('Priority 13-16: ClusterOverview 신선도 지표화 및 장애 은폐 차단', () => {
    it('동기화 실패(nodesState=error) 시 노드가 0대일 때 정상 빈 상태로 둔갑하지 않고 cluster-overview-fetch-error(role=alert)를 표출한다', async () => {
      const handleRefresh = vi.fn();

      await act(async () => {
        root.render(
          <ClusterOverview
            nodes={[]}
            runs={[]}
            pendingApprovalsCount={0}
            onNavigate={vi.fn()}
            nodesState="error"
            nodeError="Connection Refused by Gateway"
            lastFetchedAt={null}
            onRefresh={handleRefresh}
          />
        );
      });

      // 정상 0대 빈 상태 문구가 없어야 함
      expect(container.textContent).not.toContain('등록된 노드가 없습니다 (정상 조회 결과: 0대)');

      // 에러 배너 확인
      const errorSection = container.querySelector('[data-testid="cluster-overview-fetch-error"]');
      expect(errorSection).not.toBeNull();
      expect(errorSection?.getAttribute('role')).toBe('alert');
      expect(errorSection?.textContent).toContain('클러스터 노드 동기화 실패');
      expect(errorSection?.textContent).toContain('Connection Refused by Gateway');
      expect(errorSection?.textContent).toContain('정상 0대 아님');

      // 재시도 버튼 클릭
      const retryBtn = container.querySelector('[data-testid="cluster-error-retry-btn"]') as HTMLButtonElement;
      expect(retryBtn).not.toBeNull();
      await act(async () => {
        retryBtn.click();
      });
      expect(handleRefresh).toHaveBeenCalledTimes(1);
    });

    it('정상 조회 성공 시 노드가 0대이면 정상 0대 빈 상태(role=status)를 정직하게 표출한다', async () => {
      const testTimestamp = new Date(2026, 8, 22, 1, 0, 0);

      await act(async () => {
        root.render(
          <ClusterOverview
            nodes={[]}
            runs={[]}
            pendingApprovalsCount={0}
            onNavigate={vi.fn()}
            nodesState="success"
            nodeError={null}
            lastFetchedAt={testTimestamp}
          />
        );
      });

      const emptySection = container.querySelector('[data-testid="cluster-overview-empty-state"]');
      expect(emptySection).not.toBeNull();
      expect(emptySection?.getAttribute('role')).toBe('status');
      expect(emptySection?.textContent).toContain('등록된 노드가 없습니다 (정상 조회 결과: 0대)');
    });

    it('노드 데이터가 있을 때 상단에 신선도 표시기(role=status) 및 새로고침 버튼이 렌더링된다', async () => {
      const testTimestamp = new Date(2026, 8, 22, 1, 15, 0);
      const handleRefresh = vi.fn();

      await act(async () => {
        root.render(
          <ClusterOverview
            nodes={dummyNodes}
            runs={dummyRuns}
            pendingApprovalsCount={0}
            onNavigate={vi.fn()}
            nodesState="success"
            lastFetchedAt={testTimestamp}
            onRefresh={handleRefresh}
          />
        );
      });

      const indicator = container.querySelector('[data-testid="cluster-freshness-indicator"]');
      expect(indicator).not.toBeNull();
      expect(indicator?.getAttribute('role')).toBe('status');
      expect(indicator?.textContent).toContain('자동 갱신 (5초 주기)');

      const refreshBtn = container.querySelector('[data-testid="cluster-refresh-btn"]') as HTMLButtonElement;
      expect(refreshBtn).not.toBeNull();
      await act(async () => {
        refreshBtn.click();
      });
      expect(handleRefresh).toHaveBeenCalledTimes(1);
    });

    it('과거 캐시 노드가 있는 상태에서 동기화 실패 시 cluster-stale-warning(role=alert)를 표출한다', async () => {
      const testTimestamp = new Date(2026, 8, 22, 1, 10, 0);

      await act(async () => {
        root.render(
          <ClusterOverview
            nodes={dummyNodes}
            runs={dummyRuns}
            pendingApprovalsCount={0}
            onNavigate={vi.fn()}
            nodesState="error"
            nodeError="Heartbeat Timeout"
            lastFetchedAt={testTimestamp}
          />
        );
      });

      const staleWarning = container.querySelector('[data-testid="cluster-stale-warning"]');
      expect(staleWarning).not.toBeNull();
      expect(staleWarning?.getAttribute('role')).toBe('alert');
      expect(staleWarning?.textContent).toContain('동기화 실패');
      expect(staleWarning?.textContent).toContain('Heartbeat Timeout');
    });
  });

  // =========================================================================
  // 2. RunList: 신선도 지표화 및 동기화 실패 시 허위 빈 상태 둔갑 차단
  // =========================================================================
  describe('Priority 17-18: RunList 신선도 지표화 및 장애 은폐 차단', () => {
    it('동기화 실패(runsState=error) 시 작업이 0건일 때 허위 빈 상태를 렌더링하지 않고 run-fetch-error-state(role=alert)를 표출한다', async () => {
      const handleRefresh = vi.fn();

      await act(async () => {
        root.render(
          <RunList
            runs={[]}
            isLoading={false}
            runsState="error"
            runError="503 Service Unavailable"
            lastFetchedAt={null}
            onRefresh={handleRefresh}
          />
        );
      });

      // 허위 0건 빈 상태 문구 차단 확인
      expect(container.textContent).not.toContain('해당 상태의 Run이 없습니다.');

      // 전용 에러 뷰 확인
      const errorView = container.querySelector('[data-testid="run-fetch-error-state"]');
      expect(errorView).not.toBeNull();
      expect(errorView?.getAttribute('role')).toBe('alert');
      expect(errorView?.textContent).toContain('Run 작업 목록 동기화 실패');
      expect(errorView?.textContent).toContain('503 Service Unavailable');
      expect(errorView?.textContent).toContain('정상 0건 아님');

      // 재시도 버튼 클릭
      const retryBtn = container.querySelector('[data-testid="run-error-retry-btn"]') as HTMLButtonElement;
      expect(retryBtn).not.toBeNull();
      await act(async () => {
        retryBtn.click();
      });
      expect(handleRefresh).toHaveBeenCalledTimes(1);
    });

    it('상단 헤더에 신선도 표시기(role=status) 및 새로고침 버튼이 표출되고 클릭 시 onRefresh가 호출된다', async () => {
      const testTimestamp = new Date(2026, 8, 22, 1, 20, 0);
      const handleRefresh = vi.fn();

      await act(async () => {
        root.render(
          <RunList
            runs={dummyRuns}
            isLoading={false}
            runsState="success"
            lastFetchedAt={testTimestamp}
            onRefresh={handleRefresh}
          />
        );
      });

      const indicator = container.querySelector('[data-testid="run-list-freshness-indicator"]');
      expect(indicator).not.toBeNull();
      expect(indicator?.getAttribute('role')).toBe('status');
      expect(indicator?.textContent).toContain('자동 갱신 (5초 주기)');

      const refreshBtn = container.querySelector('[data-testid="run-list-refresh-btn"]') as HTMLButtonElement;
      expect(refreshBtn).not.toBeNull();
      await act(async () => {
        refreshBtn.click();
      });
      expect(handleRefresh).toHaveBeenCalledTimes(1);
    });

    it('과거 작업 목록이 있는 상태에서 동기화 실패 시 run-stale-warning(role=alert)를 표출한다', async () => {
      const testTimestamp = new Date(2026, 8, 22, 1, 18, 0);

      await act(async () => {
        root.render(
          <RunList
            runs={dummyRuns}
            isLoading={false}
            runsState="error"
            runError="Postgres Read Replica Timeout"
            lastFetchedAt={testTimestamp}
          />
        );
      });

      const staleWarning = container.querySelector('[data-testid="run-stale-warning"]');
      expect(staleWarning).not.toBeNull();
      expect(staleWarning?.getAttribute('role')).toBe('alert');
      expect(staleWarning?.textContent).toContain('동기화 실패');
      expect(staleWarning?.textContent).toContain('Postgres Read Replica Timeout');
    });
  });

  // =========================================================================
  // 3. RunDetail: alert() 소거 및 정직한 DOM 피드백 배너 검증
  // =========================================================================
  describe('Priority 19: RunDetail alert() 소거 및 정직한 DOM 알림 배너', () => {
    it('아티팩트 탭에서 다운로드 클릭 시 브라우저 alert 대신 인라인 고지(role=status)를 표출한다', async () => {
      const runWithArtifacts: RunItem = {
        ...dummyRuns[0],
        state: 'succeeded',
        artifacts: [
          {
            name: 'inference_output.dcm',
            size: '24.5 MB',
            sha: 'sha256:abcd1234efgh5678',
            url: '/download/inference_output.dcm',
          },
        ],
      };

      await act(async () => {
        root.render(
          <RunDetail
            run={runWithArtifacts}
            onBack={vi.fn()}
          />
        );
      });

      // 아티팩트 탭 선택
      const tabs = container.querySelectorAll('button');
      const artifactTab = Array.from(tabs).find((b) => b.textContent?.includes('산출물'));
      expect(artifactTab).toBeDefined();
      await act(async () => {
        artifactTab?.click();
      });

      // 다운로드 버튼 확인
      const downloadBtn = container.querySelector('[data-testid="download-artifact-inference_output.dcm"]') as HTMLButtonElement;
      expect(downloadBtn).not.toBeNull();
      expect(downloadBtn.textContent).toContain('API 미노출');

      // 클릭 시 브라우저 alert가 아닌 action notice 배너 표출
      await act(async () => {
        downloadBtn.click();
      });

      const notice = container.querySelector('[data-testid="run-action-info-notice"]');
      expect(notice).not.toBeNull();
      expect(notice?.getAttribute('role')).toBe('status');
      expect(notice?.textContent).toContain('서버 아티팩트 파일 스트림 다운로드 API 미노출 상태');
    });

    it('취소 요청 실패 시 취소 모달 내부에 cancel-modal-error(role=alert)를 정직하게 표출한다', async () => {
      const handleCancelRun = vi.fn().mockRejectedValue(new Error('Kernel Cancel Lease Expired (AUTH-0070)'));

      await act(async () => {
        root.render(
          <RunDetail
            run={dummyRuns[0]}
            onBack={vi.fn()}
            onCancelRun={handleCancelRun}
          />
        );
      });

      // 취소 버튼 클릭하여 모달 열기
      const cancelTriggerBtn = Array.from(container.querySelectorAll('button')).find((b) =>
        b.textContent?.includes('Run 취소')
      );
      expect(cancelTriggerBtn).toBeDefined();
      await act(async () => {
        cancelTriggerBtn?.click();
      });

      // 모달 내 '즉시 취소 실행' 클릭
      const modalSubmitBtn = Array.from(container.querySelectorAll('button')).find((b) =>
        b.textContent?.includes('즉시 취소 실행')
      );
      expect(modalSubmitBtn).toBeDefined();
      await act(async () => {
        modalSubmitBtn?.click();
      });

      // cancel-modal-error 배너 표출 확인
      const cancelErrorBanner = container.querySelector('[data-testid="cancel-modal-error"]');
      expect(cancelErrorBanner).not.toBeNull();
      expect(cancelErrorBanner?.getAttribute('role')).toBe('alert');
      expect(cancelErrorBanner?.textContent).toContain('Kernel Cancel Lease Expired (AUTH-0070)');
    });
  });
});
