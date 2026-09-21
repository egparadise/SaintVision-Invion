// @vitest-environment happy-dom
// @ts-ignore
globalThis.IS_REACT_ACT_ENVIRONMENT = true;
import React, { act } from 'react';
import { createRoot, Root } from 'react-dom/client';
import { describe, it, expect, beforeEach, afterEach, vi } from 'vitest';
import { RunDetail } from '@/features/runs/RunDetail';
import { RunList } from '@/features/runs/RunList';
import { DeveloperStudio } from '@/features/studio/DeveloperStudio';
import { RunItem, RunResultView, RunLogView, RunArtifactList, ShardObservation, ProjectItem, NodeItem } from '@/contracts/types';
import * as shardApi from '@/shared/api/shardObservation';
import * as logApi from '@/shared/api/runLogObservation';
import * as artifactApi from '@/shared/api/runArtifactObservation';
import * as clientApi from '@/shared/api/client';

describe('백엔드 내구성 시각 필드 3종(stateUpdatedAt, stateAsOf, completedAt) 정직한 UI 실배선 검증', () => {
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

  const dummyRun: RunItem = {
    id: 'run_0123456789ABCDEFGHJKMNPQRS',
    projectId: 'prj_0123456789ABCDEFGHJKMNPQRS',
    state: 'succeeded',
    requestedBy: 'operator',
    objective: 'Test Run for Freshness',
    createdAt: '2026-09-22T00:00:00Z',
    updatedAt: '2026-09-22T00:10:00Z',
    stateUpdatedAt: '2026-09-22T00:09:45Z',
    completedAt: '2026-09-22T00:09:40Z',
  };

  // =========================================================================
  // 1. RunDetail Header: stateUpdatedAt & completedAt 고유 라벨 표출
  // =========================================================================
  describe('1. RunDetail Header: stateUpdatedAt 및 completedAt 정직한 분리 배선', () => {
    it('stateUpdatedAt이 "실행 상태 갱신" 라벨과 함께 data-testid="run-state-updated-at"으로 표출된다', async () => {
      vi.spyOn(clientApi, 'apiClient').mockImplementation(async (url: string) => {
        if (url.includes('/result')) {
          return {
            source: 'execution-kernel',
            runId: dummyRun.id,
            projectId: dummyRun.projectId,
            state: 'succeeded',
            version: 3,
            attemptCount: 1,
            stateUpdatedAt: '2026-09-22T00:09:45Z',
            completedAt: '2026-09-22T00:09:40Z',
            sealed: true,
            executionConfirmed: true,
            commandId: 'cmd-1',
            nodeId: 'node-1',
            stopReceipt: null,
            evidence: null,
            output: { sha256: 'a'.repeat(64), sizeBytes: 1024, verified: true },
            outputAbsentReason: null,
            resourceReleasePending: false,
          } as RunResultView;
        }
        return {};
      });

      await act(async () => {
        root.render(
          <RunDetail
            run={dummyRun}
            onBack={vi.fn()}
          />
        );
      });

      const stateUpdatedEl = container.querySelector('[data-testid="run-state-updated-at"]');
      expect(stateUpdatedEl).not.toBeNull();
      expect(stateUpdatedEl?.textContent).toContain('실행 상태 갱신');

      const completedEl = container.querySelector('[data-testid="run-detail-completed-at"]');
      expect(completedEl).not.toBeNull();
      expect(completedEl?.textContent).toContain('실행 완료 시각');
    });
  });

  // =========================================================================
  // 2. ShardObservation.stateAsOf: Tab 5 샤드 상태 기준
  // =========================================================================
  describe('2. ShardObservation.stateAsOf: Tab 5 분산 샤드 상태 기준 표출 및 스냅샷 왜곡 차단', () => {
    it('stateAsOf가 존재할 때 "샤드 상태 기준" 라벨로 표출되고 단일 공통 스냅샷이 아님을 정직 고지한다', async () => {
      const dummyShardObs: ShardObservation = {
        planId: 'shard_plan_01',
        sourcePlanId: null,
        rootPlanId: 'shard_plan_01',
        generation: 1,
        parentRunId: dummyRun.id,
        parentState: 'succeeded',
        stateAsOf: '2026-09-22T00:08:30Z',
        aggregateManifestSha256: 'b'.repeat(64),
        shardCount: 2,
        allPhysicallyStopped: true,
        allSucceeded: true,
        resultManifest: null,
        resultManifestSha256: null,
        shards: [],
      };

      vi.spyOn(shardApi, 'fetchShardObservation').mockResolvedValue(dummyShardObs);

      await act(async () => {
        root.render(
          <RunDetail
            run={dummyRun}
            onBack={vi.fn()}
          />
        );
      });

      // Tab 5로 전환
      const shardTabBtn = Array.from(container.querySelectorAll('button')).find((b) =>
        b.textContent?.includes('5. 분산 샤드')
      );
      expect(shardTabBtn).toBeDefined();

      await act(async () => {
        shardTabBtn!.click();
      });

      const banner = container.querySelector('[data-testid="shards-freshness-banner"]');
      expect(banner).not.toBeNull();
      expect(banner?.textContent).toContain('샤드 상태 기준');
      expect(banner?.textContent).toContain('단일 공통 스냅샷이나 조회 시각이 아닙니다');

      const stateAsOfEl = container.querySelector('[data-testid="shard-state-as-of"]');
      expect(stateAsOfEl).not.toBeNull();

      const cardEl = container.querySelector('[data-testid="shard-state-as-of-card"]');
      expect(cardEl).not.toBeNull();

      // Mutation killer: "동일 시점 스냅샷" 또는 "단일 공통 스냅샷"으로 사칭하지 않는다
      expect(container.textContent).not.toContain('단일 공통 스냅샷입니다');
      expect(container.textContent).not.toContain('동일 시점 스냅샷입니다');
    });
  });

  // =========================================================================
  // 3. RunLogView.completedAt: Tab 2 실시간 로그의 완료 시각
  // =========================================================================
  describe('3. RunLogView.completedAt: Tab 2 로그 결과 완료 시각 표출 및 로그 캡처 시각 오인 차단', () => {
    it('completedAt이 존재할 때 "실행 완료 시각" 라벨로 표출되고 로그 캡처 시각이 아님을 정직 고지한다', async () => {
      const dummyLogView: RunLogView = {
        source: 'execution-kernel',
        runId: dummyRun.id,
        completedAt: '2026-09-22T00:09:40Z',
        stdout: 'Process output log line 1\nProcess output log line 2',
        stderr: null,
        redacted: false,
        truncated: false,
        absentReason: null,
      };

      vi.spyOn(logApi, 'fetchRunLogs').mockResolvedValue(dummyLogView);

      await act(async () => {
        root.render(
          <RunDetail
            run={dummyRun}
            onBack={vi.fn()}
          />
        );
      });

      // Tab 2로 전환
      const logTabBtn = Array.from(container.querySelectorAll('button')).find((b) =>
        b.textContent?.includes('2. 실시간 SSE 로그')
      );
      expect(logTabBtn).toBeDefined();

      await act(async () => {
        logTabBtn!.click();
      });

      const banner = container.querySelector('[data-testid="logs-freshness-banner"]');
      expect(banner).not.toBeNull();
      expect(banner?.textContent).toContain('실행 완료 시각');
      expect(banner?.textContent).toContain('실시간 로그 캡처나 화면 갱신 시각이 아닙니다');

      const logCompletedEl = container.querySelector('[data-testid="log-completed-at"]');
      expect(logCompletedEl).not.toBeNull();

      const badgeEl = container.querySelector('[data-testid="log-completed-at-badge"]');
      expect(badgeEl).not.toBeNull();
      expect(badgeEl?.textContent).toContain('완료 커밋');

      // Mutation killer: "로그 캡처 시각" 또는 "로그 수집 시각"으로 거짓 라벨링하지 않는다
      expect(container.textContent).not.toContain('로그 캡처 시각:');
      expect(container.textContent).not.toContain('로그 수집 시각:');
    });
  });

  // =========================================================================
  // 4. RunArtifactList.completedAt: Tab 3 산출물의 완료 시각
  // =========================================================================
  describe('4. RunArtifactList.completedAt: Tab 3 산출물 완료 시각 표출 및 다운로드 시각 오인 차단', () => {
    it('completedAt이 존재할 때 "실행 완료 시각" 라벨로 표출되고 파일 다운로드 시각이 아님을 정직 고지한다', async () => {
      const dummyArtifacts: RunArtifactList = {
        source: 'execution-kernel',
        runId: dummyRun.id,
        completedAt: '2026-09-22T00:09:40Z',
        artifacts: [
          {
            path: 'output/result.json',
            checksumSha256: 'c'.repeat(64),
            byteSize: 2048,
            verified: true,
            evidenceId: 'evd_art_01',
          },
        ],
        count: 1,
        verifiedCount: 1,
        absentReason: null,
      };

      vi.spyOn(artifactApi, 'fetchRunArtifacts').mockResolvedValue(dummyArtifacts);

      await act(async () => {
        root.render(
          <RunDetail
            run={dummyRun}
            onBack={vi.fn()}
          />
        );
      });

      // Tab 3로 전환
      const artTabBtn = Array.from(container.querySelectorAll('button')).find((b) =>
        b.textContent?.includes('3. 산출물')
      );
      expect(artTabBtn).toBeDefined();

      await act(async () => {
        artTabBtn!.click();
      });

      const banner = container.querySelector('[data-testid="artifacts-freshness-banner"]');
      expect(banner).not.toBeNull();
      expect(banner?.textContent).toContain('실행 완료 시각');
      expect(banner?.textContent).toContain('파일 다운로드 또는 화면 조회 시각이 아닙니다');

      const artCompletedEl = container.querySelector('[data-testid="artifact-completed-at"]');
      expect(artCompletedEl).not.toBeNull();

      // 실제 아티팩트 행 렌더링 확인
      const artRow = container.querySelector('[data-testid="artifact-row-output/result.json"]');
      expect(artRow).not.toBeNull();
      expect(artRow?.textContent).toContain('output/result.json');
      expect(artRow?.textContent).toContain('2,048 B');

      // 다운로드 링크 확인
      const downloadLink = container.querySelector('[data-testid="download-artifact-output/result.json"]');
      expect(downloadLink).not.toBeNull();
      expect(downloadLink?.getAttribute('href')).toContain('/artifacts/content?path=output%2Fresult.json');

      // Mutation killer: "다운로드 시각"이나 "수집 시각"으로 사칭하지 않는다
      expect(container.textContent).not.toContain('산출물 다운로드 시각:');
      expect(container.textContent).not.toContain('산출물 수집 시각:');
    });
  });

  // =========================================================================
  // 5. RunList: 테이블 행에 stateUpdatedAt 표출
  // =========================================================================
  describe('5. RunList: 테이블 각 행에 stateUpdatedAt 정직한 표출', () => {
    it('stateUpdatedAt이 존재하는 Run 행에 "상태 갱신:" 라벨이 표출된다', async () => {
      await act(async () => {
        root.render(
          <RunList
            runs={[dummyRun]}
            isLoading={false}
          />
        );
      });

      const stateUpdatedEl = container.querySelector(`[data-testid="run-state-updated-at-${dummyRun.id}"]`);
      expect(stateUpdatedEl).not.toBeNull();
      expect(stateUpdatedEl?.textContent).toContain('상태 갱신:');

      const completedEl = container.querySelector(`[data-testid="run-completed-at-${dummyRun.id}"]`);
      expect(completedEl).not.toBeNull();
      expect(completedEl?.textContent).toContain('실행 완료:');
    });
  });

  // =========================================================================
  // 6. DeveloperStudio Step 4: stateUpdatedAt 및 completedAt 헤더 표출
  // =========================================================================
  describe('6. DeveloperStudio Step 4: stateUpdatedAt 실배선 및 현재시각 위조 차단', () => {
    const dummyProject: ProjectItem = {
      id: dummyRun.projectId,
      name: 'Test Project',
      createdAt: '2026-09-22T00:00:00Z',
    };

    const dummyNode: NodeItem = {
      id: 'node-01',
      hostname: 'worker-gpu-01',
      os: 'linux',
      status: 'online',
      cpuCores: 8,
      cpuUsagePercent: 10,
      memoryTotalBytes: 32 * 1024 ** 3,
      memoryUsedBytes: 8 * 1024 ** 3,
      gpuCount: 1,
      storageTotalBytes: 500 * 1024 ** 3,
      storageUsedBytes: 50 * 1024 ** 3,
      heartbeatAt: '2026-09-22T00:00:00Z',
    };

    it('Step 4에서 stateUpdatedAt이 "실행 상태 갱신"으로 표출된다', async () => {
      vi.spyOn(clientApi, 'apiClient').mockImplementation(async (url: string) => {
        if (url.includes('/workspaces')) return [];
        if (url.includes('/result')) {
          return {
            source: 'execution-kernel',
            runId: dummyRun.id,
            projectId: dummyRun.projectId,
            state: 'succeeded',
            version: 1,
            attemptCount: 1,
            stateUpdatedAt: '2026-09-22T00:09:45Z',
            completedAt: '2026-09-22T00:09:40Z',
            sealed: true,
            executionConfirmed: true,
            commandId: 'cmd-1',
            nodeId: 'node-01',
            stopReceipt: { exitCode: 0, finishedAt: '2026-09-22T00:09:40Z', processStarted: true, receiptId: 'rcp-1', reason: 'exited' },
            evidence: null,
            output: { sha256: 'd'.repeat(64), sizeBytes: 512, verified: true },
            outputAbsentReason: null,
            resourceReleasePending: false,
          } as RunResultView;
        }
        if (url.includes('/runs/')) return dummyRun;
        return {};
      });

      await act(async () => {
        root.render(
          <DeveloperStudio
            project={dummyProject}
            nodes={[dummyNode]}
            runs={[dummyRun]}
            initialStep={4}
            initialRunId={dummyRun.id}
          />
        );
      });

      const stateUpdatedEl = container.querySelector('[data-testid="studio-run-state-updated-at"]');
      expect(stateUpdatedEl).not.toBeNull();
      expect(stateUpdatedEl?.textContent).toContain('실행 상태 갱신');

      const completedEl = container.querySelector('[data-testid="studio-run-completed-at"]');
      expect(completedEl).not.toBeNull();
      expect(completedEl?.textContent).toContain('실행 완료 시각');
    });
  });

  // =========================================================================
  // 7. 시각 필드 3종의 독립성과 단일 단어 뭉뚱그리기 금지 검증 (Anti-pattern Invariants)
  // =========================================================================
  describe('7. 시각 필드 3종(stateUpdatedAt, stateAsOf, completedAt) 독립성 보존 불변식', () => {
    it('세 시각 필드가 "갱신됨" 또는 "최종 확인" 같은 모호한 단일 어휘로 뭉뚱그려지지 않고 각각 고유한 라벨을 유지한다', async () => {
      vi.spyOn(clientApi, 'apiClient').mockImplementation(async (url: string) => {
        if (url.includes('/result')) {
          return {
            source: 'execution-kernel',
            runId: dummyRun.id,
            projectId: dummyRun.projectId,
            state: 'succeeded',
            version: 1,
            attemptCount: 1,
            stateUpdatedAt: '2026-09-22T00:09:45Z',
            completedAt: '2026-09-22T00:09:40Z',
            sealed: true,
            executionConfirmed: true,
            commandId: 'cmd-1',
            nodeId: 'node-1',
            stopReceipt: null,
            evidence: null,
            output: { sha256: 'a'.repeat(64), sizeBytes: 1024, verified: true },
            outputAbsentReason: null,
            resourceReleasePending: false,
          } as RunResultView;
        }
        return {};
      });

      vi.spyOn(shardApi, 'fetchShardObservation').mockResolvedValue({
        planId: 'plan-1',
        sourcePlanId: null,
        rootPlanId: 'plan-1',
        generation: 1,
        parentRunId: dummyRun.id,
        parentState: 'succeeded',
        stateAsOf: '2026-09-22T00:08:30Z',
        aggregateManifestSha256: null,
        shardCount: 1,
        allPhysicallyStopped: true,
        allSucceeded: true,
        resultManifest: null,
        resultManifestSha256: null,
        shards: [],
      });

      await act(async () => {
        root.render(
          <RunDetail
            run={dummyRun}
            onBack={vi.fn()}
          />
        );
      });

      // Header 확인
      const headerStateUpdated = container.querySelector('[data-testid="run-state-updated-at"]');
      const headerCompleted = container.querySelector('[data-testid="run-detail-completed-at"]');

      expect(headerStateUpdated?.textContent?.trim().startsWith('실행 상태 갱신:')).toBe(true);
      expect(headerCompleted?.textContent?.trim().startsWith('실행 완료 시각:')).toBe(true);

      // 두 라벨이 서로 완전히 구별됨
      expect(headerStateUpdated?.textContent).not.toEqual(headerCompleted?.textContent);
    });
  });
});
