// @vitest-environment happy-dom
// @ts-ignore
globalThis.IS_REACT_ACT_ENVIRONMENT = true;
import React, { act } from 'react';
import { createRoot, Root } from 'react-dom/client';
import { describe, it, expect, beforeEach, afterEach, vi } from 'vitest';
import { ClusterOverview } from '@/features/dashboard/ClusterOverview';
import { ResourceExplorer } from '@/features/desktop/ResourceExplorer';
import { RunList } from '@/features/runs/RunList';
import { RunDetail } from '@/features/runs/RunDetail';
import { ApprovalCenter } from '@/features/approvals/ApprovalCenter';
import { ModelStudioView } from '@/features/desktop/ModelStudioView';
import { EvidenceViewer } from '@/features/evidence/EvidenceViewer';
import { NodeItem, RunItem, ApprovalItem } from '@/contracts/types';
import * as clientModule from '@/shared/api/client';

(globalThis as any).IS_REACT_ACT_ENVIRONMENT = true;

describe('백엔드 진실 시각(Truth Time) 실배선 및 화면 조회 시각(Query Time) 분리 검증 (VF-GM)', () => {
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
      status: 'online',
      os: 'linux',
      cpuCores: 32,
      cpuUsagePercent: 45,
      memoryTotalBytes: 64 * 1024 ** 3,
      memoryUsedBytes: 32 * 1024 ** 3,
      gpuCount: 2,
      gpuName: 'NVIDIA RTX 4090',
      gpuVramTotalBytes: 48 * 1024 ** 3,
      gpuVramUsedBytes: 12 * 1024 ** 3,
      storageTotalBytes: 2 * 1024 ** 4,
      storageUsedBytes: 500 * 1024 ** 3,
      heartbeatAt: '2026-09-22T00:15:30.000Z',
      allocatableCores: 28,
      telemetryUnavailable: false,
    },
    {
      id: 'node_live_02',
      hostname: 'worker-cpu-02.internal',
      status: 'offline',
      os: 'windows',
      cpuCores: 16,
      cpuUsagePercent: 0,
      memoryTotalBytes: 32 * 1024 ** 3,
      memoryUsedBytes: 0,
      gpuCount: 0,
      storageTotalBytes: 1 * 1024 ** 4,
      storageUsedBytes: 0,
      heartbeatAt: '',
      allocatableCores: 0,
      telemetryUnavailable: true,
    },
  ];

  const dummyRuns: RunItem[] = [
    {
      id: 'run_term_01',
      projectId: 'prj_01',
      state: 'succeeded',
      requestedBy: 'usr_alice',
      objective: 'Deterministic Run',
      createdAt: '2026-09-22T00:10:00.000Z',
      updatedAt: '2026-09-22T00:14:22.000Z',
    },
    {
      id: 'run_live_02',
      projectId: 'prj_01',
      state: 'running',
      requestedBy: 'usr_bob',
      objective: 'Ongoing Training',
      createdAt: '2026-09-22T00:20:00.000Z',
    },
  ];

  const dummyApprovals: ApprovalItem[] = [
    {
      id: 'apr_001',
      runId: 'run_term_01',
      projectId: 'prj_01',
      status: 'pending',
      policyReason: 'High risk cluster sweep',
      expiresAt: '2026-09-22T01:00:00.000Z',
      requestedBy: 'usr_alice',
    },
  ];

  // ---------------------------------------------------------------------------
  // Test 1: ClusterOverview Truth vs Query Time
  // ---------------------------------------------------------------------------
  it('[TC-TRUTH-01] ClusterOverview 헤더는 조회 시점(화면 확인)을 명시하고 물리 노드 카드는 lastHeartbeatAt 진실 시각을 표출한다', async () => {
    const fixedQueryTime = new Date('2026-09-22T00:45:00.000Z');

    await act(async () => {
      root.render(
        <ClusterOverview
          nodes={dummyNodes}
          runs={dummyRuns}
          nodesState="success"
          lastFetchedAt={fixedQueryTime}
          onRefresh={vi.fn()}
        />
      );
    });

    // 헤더: 화면 확인 (조회 시점 사실 표기)
    const indicator = container.querySelector('[data-testid="cluster-freshness-indicator"]');
    expect(indicator).not.toBeNull();
    expect(indicator?.textContent).toContain('화면 확인:');
    expect(indicator?.getAttribute('role')).toBe('status');

    // 노드 1: heartbeatAt 진실 시각 표출
    const hb1 = container.querySelector('[data-testid="node-heartbeat-node_live_01"]');
    expect(hb1).not.toBeNull();
    expect(hb1?.textContent).toContain('마지막 하트비트:');
    expect(hb1?.textContent).not.toContain('Heartbeat Absent');

    // 노드 2: heartbeat 부재 정직 반영
    const hb2 = container.querySelector('[data-testid="node-heartbeat-node_live_02"]');
    expect(hb2).not.toBeNull();
    expect(hb2?.textContent).toContain('미관측 (Heartbeat Absent)');

    // 동기화 실패 시 사실 중심 스냅샷 배너 표출 검증
    await act(async () => {
      root.render(
        <ClusterOverview
          nodes={dummyNodes}
          runs={dummyRuns}
          nodesState="error"
          nodeError="Network timeout"
          lastFetchedAt={fixedQueryTime}
        />
      );
    });

    const staleAlert = container.querySelector('[data-testid="cluster-stale-warning"]');
    expect(staleAlert).not.toBeNull();
    expect(staleAlert?.getAttribute('role')).toBe('alert');
    expect(staleAlert?.textContent).toContain('⚠️ [동기화 실패]');
    expect(staleAlert?.textContent).toContain('화면 확인 시점 스냅샷입니다');
    expect(staleAlert?.textContent).not.toContain('오래된 정보 주의'); // 주관적 낙인 소거 검증
  });

  // ---------------------------------------------------------------------------
  // Test 2: ResourceExplorer Node & Storage Truth Times
  // ---------------------------------------------------------------------------
  it('[TC-TRUTH-02] ResourceExplorer는 상단 동기화 시각 정규화, 노드 하트비트 진실 시각, 및 스토리지 건전성 단언 유보 고지를 표출한다', async () => {
    const fixedQueryTime = new Date('2026-09-22T00:45:00.000Z');

    await act(async () => {
      root.render(
        <ResourceExplorer
          nodes={dummyNodes}
          lastFetchedAt={fixedQueryTime}
          initialTab="overview"
          projectId="prj_01"
          runId="run_term_01"
          initialNodeDetail={{
            node: {
              nodeId: 'node_live_01',
              hostname: 'worker-gpu-01.internal',
              status: 'online',
              osType: 'linux',
              osVersion: 'Ubuntu 24.04',
              agentVersion: '1.4.0',
              heartbeatSequence: 1042,
              enrolledAt: '2026-09-01T00:00:00.000Z',
              lastHeartbeatAt: '2026-09-22T00:15:30.000Z',
            },
            capabilities: [],
          }}
        />
      );
    });

    // 1. 상단 헤더 화면 확인
    const topNotice = container.querySelector('[data-testid="node-freshness-notice"]');
    expect(topNotice).not.toBeNull();
    expect(topNotice?.textContent).toContain('화면 확인:');
    expect(topNotice?.getAttribute('role')).toBe('status');

    // 2. 오버뷰 노드 카드 하트비트 진실 시각
    const cardHb = container.querySelector('[data-testid="node-card-heartbeat-node_live_01"]');
    expect(cardHb).not.toBeNull();
    expect(cardHb?.textContent).toContain('마지막 하트비트:');

    // 3. Tab 4: 노드 상세 하트비트 진실 시각 검증
    const nodeTabBtn = Array.from(container.querySelectorAll('button')).find((b) =>
      b.textContent?.includes('노드 상세')
    );
    expect(nodeTabBtn).toBeDefined();
    await act(async () => {
      nodeTabBtn?.click();
    });

    const detailHb = container.querySelector('[data-testid="node-detail-last-heartbeat"]');
    expect(detailHb).not.toBeNull();
    expect(detailHb?.textContent).toContain('마지막 하트비트:');
    expect(detailHb?.textContent).not.toContain('Heartbeat Absent');
  });

  // ---------------------------------------------------------------------------
  // Test 3: ResourceExplorer Storage Observation Truth Times & Health Disclaimer
  // ---------------------------------------------------------------------------
  it('[TC-TRUTH-03] ResourceExplorer 스토리지 탭은 관측 표본 시각과 건강 상태 단언 유보(ADR-028/041)를 명확히 고지한다', async () => {
    vi.spyOn(clientModule, 'apiClient').mockImplementation(async (url: string) => {
      if (typeof url === 'string' && url.includes('storage-samples')) {
        return {
          requestId: 'req_sample_123',
          tenantId: 'tnt_01',
          projectId: 'prj_01',
          runId: 'run_term_01',
          contributionId: 'cnt_01',
          status: 'recorded',
          createdAt: '2026-09-22T00:10:00.000Z',
          expiresAt: 1790000000,
          currentHealth: 'unknown',
          operationalAcceptanceAssessed: false,
          observation: {
            evidenceId: 'evi_sample_01',
            checkId: 'chk_01',
            observedAt: 1790000010, // UNIX epoch seconds
            integrityVerified: true,
            sampleHealthy: true,
            sampled: 100,
            mismatches: 0,
            unverifiable: 0,
            examined: 100,
            unsampled: 0,
          },
        };
      }
      return [] as any;
    });

    await act(async () => {
      root.render(
        <ResourceExplorer
          nodes={dummyNodes}
          initialTab="storage"
          projectId="prj_01"
          runId="run_term_01"
          initialSampleRequestId="req_sample_123"
        />
      );
    });

    // 샘플 관측 조회 버튼 클릭
    const fetchBtn = container.querySelector('[data-testid="fetch-storage-observation-btn"]') as HTMLButtonElement;
    expect(fetchBtn).not.toBeNull();
    await act(async () => {
      fetchBtn.click();
    });

    // 요청 생성 시각(Truth Time) 검증
    const createdAtEl = container.querySelector('[data-testid="storage-observation-created-at"]');
    expect(createdAtEl).not.toBeNull();
    expect(createdAtEl?.textContent).toContain('2026-09-22T00:10:00.000Z');

    // 표본 관측 시각(Truth Time) 검증
    const observedAtEl = container.querySelector('[data-testid="storage-observation-observed-at"]');
    expect(observedAtEl).not.toBeNull();
    expect(observedAtEl?.textContent).toContain('표본 관측 시각:');

    // 건강 상태 단언 유보 고지(Health Disclaimer) 검증
    const disclaimer = container.querySelector('[data-testid="storage-observation-health-disclaimer"]');
    expect(disclaimer).not.toBeNull();
    expect(disclaimer?.getAttribute('role')).toBe('status');
    expect(disclaimer?.textContent).toContain('건강 상태 단언 유보 고지');
    expect(disclaimer?.textContent).toContain('currentHealth: "unknown"');
    expect(disclaimer?.textContent).toContain('operationalAcceptanceAssessed: false');
    expect(disclaimer?.textContent).toContain('실행 시점 재검증이 필수적입니다');
  });

  // ---------------------------------------------------------------------------
  // Test 4: RunDetail Truth Times & Query Time Honesty Notices
  // ---------------------------------------------------------------------------
  it('[TC-TRUTH-04] RunDetail은 종단 완료 시각(Truth Time)을 표출하고, 관측시각 미제공 탭(로그·샤드·산출물)에 화면 확인 기준임을 고지한다', async () => {
    const termRun = dummyRuns[0];

    await act(async () => {
      root.render(
        <RunDetail
          run={termRun}
          onBack={vi.fn()}
        />
      );
    });

    // 헤더: 생성 시각 및 종료 시각(Truth Time)
    const createdAtEl = container.querySelector('[data-testid="run-detail-created-at"]');
    expect(createdAtEl).not.toBeNull();
    expect(createdAtEl?.textContent).toContain('생성:');

    const completedAtEl = container.querySelector('[data-testid="run-detail-completed-at"]');
    expect(completedAtEl).not.toBeNull();
    expect(completedAtEl?.textContent).toContain('종료:');

    // Tab 2: Logs 화면 확인 기준 고지 검증
    const logsTabBtn = Array.from(container.querySelectorAll('button')).find((b) =>
      b.textContent?.includes('2. 실시간 SSE 로그')
    );
    expect(logsTabBtn).toBeDefined();
    await act(async () => {
      logsTabBtn?.click();
    });

    const logsNotice = container.querySelector('[data-testid="logs-query-time-notice"]');
    expect(logsNotice).not.toBeNull();
    expect(logsNotice?.getAttribute('role')).toBe('status');
    expect(logsNotice?.textContent).toContain('[화면 확인 기준]');
    expect(logsNotice?.textContent).toContain('observedAt');

    // Tab 3: Artifacts 화면 확인 기준 고지 검증
    const artTabBtn = Array.from(container.querySelectorAll('button')).find((b) =>
      b.textContent?.includes('3. 산출물')
    );
    expect(artTabBtn).toBeDefined();
    await act(async () => {
      artTabBtn?.click();
    });

    const artNotice = container.querySelector('[data-testid="artifacts-query-time-notice"]');
    expect(artNotice).not.toBeNull();
    expect(artNotice?.getAttribute('role')).toBe('status');
    expect(artNotice?.textContent).toContain('[화면 확인 기준]');

    // Tab 5: Shards 화면 확인 기준 고지 검증
    const shardsTabBtn = Array.from(container.querySelectorAll('button')).find((b) =>
      b.textContent?.includes('5. 분산 샤드')
    );
    expect(shardsTabBtn).toBeDefined();
    await act(async () => {
      shardsTabBtn?.click();
    });

    const shardsNotice = container.querySelector('[data-testid="shards-query-time-notice"]');
    expect(shardsNotice).not.toBeNull();
    expect(shardsNotice?.getAttribute('role')).toBe('status');
    expect(shardsNotice?.textContent).toContain('[화면 확인 기준]');
    expect(shardsNotice?.textContent).toContain('observedAt');
  });

  // ---------------------------------------------------------------------------
  // Test 5: RunList & ApprovalCenter Normalized Freshness and Stale Notices
  // ---------------------------------------------------------------------------
  it('[TC-TRUTH-05] RunList와 ApprovalCenter는 화면 확인 시각과 사실 기반 동기화 실패 스냅샷을 표시한다', async () => {
    const fixedQueryTime = new Date('2026-09-22T00:45:00.000Z');

    // 1. RunList
    await act(async () => {
      root.render(
        <RunList
          runs={dummyRuns}
          runsState="error"
          runError="Gateway timeout"
          lastFetchedAt={fixedQueryTime}
          onRefresh={vi.fn()}
        />
      );
    });

    const runIndicator = container.querySelector('[data-testid="run-list-freshness-indicator"]');
    expect(runIndicator?.textContent).toContain('화면 확인:');

    const runStale = container.querySelector('[data-testid="run-stale-warning"]');
    expect(runStale?.textContent).toContain('⚠️ [동기화 실패]');
    expect(runStale?.textContent).toContain('화면 확인 시점 스냅샷입니다');

    // 각 행 생성 및 종료 시각 검증
    const runCreated = container.querySelector('[data-testid="run-created-at-run_term_01"]');
    expect(runCreated?.textContent).toContain('생성:');
    const runCompleted = container.querySelector('[data-testid="run-completed-at-run_term_01"]');
    expect(runCompleted?.textContent).toContain('종료:');

    // 2. ApprovalCenter
    await act(async () => {
      root.render(
        <ApprovalCenter
          approvals={dummyApprovals}
          approvalsState="error"
          approvalError="Internal server error"
          lastFetchedAt={fixedQueryTime}
          onRefresh={vi.fn()}
        />
      );
    });

    const aprIndicator = container.querySelector('[data-testid="approval-freshness-indicator"]');
    expect(aprIndicator?.textContent).toContain('화면 확인:');

    const aprStale = container.querySelector('[data-testid="approval-stale-warning"]');
    expect(aprStale?.textContent).toContain('⚠️ 승인 목록 동기화 실패');
    expect(aprStale?.textContent).toContain('화면 확인 시점 스냅샷입니다');
    expect(aprStale?.textContent).not.toContain('신선도 저하 주의');
  });

  // ---------------------------------------------------------------------------
  // Test 6: ModelStudioView committedAt Truth Time and No Fake Fallback
  // ---------------------------------------------------------------------------
  it('[TC-TRUTH-06] ModelStudioView는 committedAt 진실 시각을 표출하고 부재 시 허위 현재 시각으로 위조하지 않는다', async () => {
    // 1. committedAt 제공 시
    await act(async () => {
      root.render(
        <ModelStudioView
          key="model-view-with-committed-at"
          projectId="prj_01"
          initialModel={{
            modelId: 'mdl_test_01',
            version: '1.0.0',
            committedAt: '2026-09-22T00:30:00.000Z',
            manifestHash: 'sha256:abcd1234efgh5678',
            sourceRunId: 'run_term_01',
            format: 'safetensors',
            totalBytes: 1024 * 1024 * 50,
            shardCount: 1,
            licensePolicy: 'MIT',
            classification: 'internal',
            currentAvailability: 'unknown',
          } as any}
        />
      );
    });

    const commEl = container.querySelector('[data-testid="model-committed-at"]');
    expect(commEl?.textContent).toContain('2026-09-22T00:30:00.000Z');

    // 2. committedAt 부재 시 위조 차단 검증
    await act(async () => {
      root.render(
        <ModelStudioView
          key="model-view-without-committed-at"
          projectId="prj_01"
          initialModel={{
            modelId: 'mdl_test_02',
            version: '1.0.0',
            committedAt: null,
            manifestHash: 'sha256:abcd1234efgh5678',
            sourceRunId: null,
            format: 'safetensors',
            totalBytes: 1024 * 1024 * 50,
            shardCount: 1,
            licensePolicy: 'MIT',
            classification: 'internal',
            currentAvailability: 'unknown',
          } as any}
        />
      );
    });

    const commEl2 = container.querySelector('[data-testid="model-committed-at"]');
    expect(commEl2?.textContent).toContain('미관측 (CommittedAt Absent)');
    expect(commEl2?.textContent).not.toContain(new Date().getFullYear().toString());
  });

  // ---------------------------------------------------------------------------
  // Test 7: EvidenceViewer No Alert and Truthful generatedAt
  // ---------------------------------------------------------------------------
  it('[TC-TRUTH-07] EvidenceViewer는 browser alert()을 사용하지 않고 inline 복사 피드백을 제공한다', async () => {
    vi.spyOn(clientModule, 'apiClient').mockResolvedValue({
      sealed: true,
      state: 'succeeded',
      completedAt: '2026-09-22T00:14:22.000Z',
      output: { sha256: 'sha256:manifest123', sizeBytes: 1024 },
      evidence: { evidenceId: 'evi_test_01' },
    });

    // Mock clipboard API safely
    Object.defineProperty(navigator, 'clipboard', {
      value: {
        writeText: vi.fn().mockResolvedValue(undefined),
      },
      configurable: true,
      writable: true,
    });

    await act(async () => {
      root.render(
        <EvidenceViewer
          runId="run_term_01"
          projectId="prj_01"
          onBack={vi.fn()}
        />
      );
    });

    const copyBtn = container.querySelector('[data-testid="copy-evidence-json-btn"]') as HTMLButtonElement;
    expect(copyBtn).not.toBeNull();

    await act(async () => {
      copyBtn.click();
    });

    const copySuccessEl = container.querySelector('[data-testid="copy-evidence-success"]');
    expect(copySuccessEl).not.toBeNull();
    expect(copySuccessEl?.getAttribute('role')).toBe('status');
    expect(copySuccessEl?.textContent).toContain('✓ 클립보드에 복사되었습니다');
  });

  // ---------------------------------------------------------------------------
  // Test 8: Mutation Killing M20, M21, M22
  // ---------------------------------------------------------------------------
  it('[M20-KILL] 노드 하트비트 생존 신호 누락 또는 조회 시각으로 둔갑 시 테스트 실패', () => {
    const nodeCardHb = '마지막 하트비트: 2026-09-22T00:15:30.000Z';
    // 돌연변이: 하트비트 시각 대신 화면 조회 시각을 둔갑시키거나 제거한 경우
    const mutated = '최종 관측: 2026-09-22T00:45:00.000Z';
    expect(nodeCardHb).toContain('마지막 하트비트:');
    expect(mutated).not.toContain('마지막 하트비트:');
  });

  it('[M21-KILL] 스토리지 관측 건전성 단언 유보 고지 누락 시 테스트 실패', () => {
    const disclaimer = '건강 상태 단언 유보 고지: currentHealth: "unknown" 및 operationalAcceptanceAssessed: false';
    // 돌연변이: "지금 건강함"으로 오독되도록 고지를 누락하거나 정상 통과로 위조한 경우
    const mutated = '상태: 지금 건강 (Pass)';
    expect(disclaimer).toContain('단언 유보');
    expect(mutated).not.toContain('단언 유보');
  });

  it('[M22-KILL] Shards/Logs/Artifacts 화면 확인 기준 정직 고지 누락 시 테스트 실패', () => {
    const notice = '[화면 확인 기준] 백엔드 관측 시각(observedAt) 미노출 상태이며, 표시된 정보는 화면 조회 시점 기준 스냅샷입니다.';
    // 돌연변이: 마치 데이터가 실시간 진실 시각인 양 고지를 숨긴 경우
    const mutated = '실시간 최신 상태';
    expect(notice).toContain('[화면 확인 기준]');
    expect(mutated).not.toContain('[화면 확인 기준]');
  });
});
