import React from 'react';
import { describe, it, expect } from 'vitest';
import { renderToStaticMarkup } from 'react-dom/server';
import { PlacementSimulator } from '../src/features/placement/PlacementSimulator';
import { NodeItem } from '../src/contracts/types';

const sampleNodes: NodeItem[] = [
  {
    id: 'nod_01JABCDEF01',
    hostname: 'Node-01-WinMain',
    status: 'online',
    os: 'windows',
    cpuCores: 16,
    cpuUsagePercent: 20,
    memoryTotalBytes: 64 * 1024 ** 3,
    memoryUsedBytes: 20 * 1024 ** 3,
    allocatableCores: 12,
    allocatableMemoryBytes: 36 * 1024 ** 3,
    gpuCount: 1,
    gpuName: 'NVIDIA RTX 4090',
    gpuVramTotalBytes: 24 * 1024 ** 3,
    gpuVramUsedBytes: 6 * 1024 ** 3,
    storageTotalBytes: 2000 * 1024 ** 3,
    storageUsedBytes: 500 * 1024 ** 3,
    heartbeatAt: new Date().toISOString(),
  },
  {
    id: 'nod_01JABCDEF02',
    hostname: 'Node-02-WinWork',
    status: 'online',
    os: 'windows',
    cpuCores: 8,
    cpuUsagePercent: 30,
    memoryTotalBytes: 32 * 1024 ** 3,
    memoryUsedBytes: 15 * 1024 ** 3,
    allocatableCores: 4,
    allocatableMemoryBytes: 12 * 1024 ** 3,
    gpuCount: 0,
    storageTotalBytes: 1000 * 1024 ** 3,
    storageUsedBytes: 400 * 1024 ** 3,
    heartbeatAt: new Date().toISOString(),
  },
];

describe('UI-FB-02 PlacementSimulator Negative Controls & Verification Boundaries', () => {
  it('renders explicit UNVERIFIED badge for local heuristic evaluation', () => {
    const markup = renderToStaticMarkup(
      <PlacementSimulator nodes={sampleNodes} initialPools={[]} initialCandidates={[]} initialServerShards={[]} />
    );
    expect(markup).toContain('로컬 결정론적 평가 (UNVERIFIED: 로컬 시뮬레이션 전용)');
    expect(markup).toContain('data-testid="local-simulation-badge"');
  });

  it('renders pools-idle-banner when pools query is in idle state', () => {
    const markup = renderToStaticMarkup(
      <PlacementSimulator nodes={sampleNodes} initialPoolsState="idle" initialPools={[]} initialCandidates={[]} initialServerShards={[]} />
    );
    expect(markup).toContain('data-testid="pools-idle-banner"');
    expect(markup).toContain('자원 풀 연동 대기 중입니다');
    expect(markup).toContain('[로컬 결정론적 평가 (UNVERIFIED)]');
  });

  it('renders pools-fallback-banner with UNVERIFIED label after successful empty query', () => {
    const markup = renderToStaticMarkup(
      <PlacementSimulator nodes={sampleNodes} initialPoolsState="success" initialPools={[]} initialCandidates={[]} initialServerShards={[]} />
    );
    expect(markup).toContain('data-testid="pools-fallback-banner"');
    expect(markup).toContain('[로컬 결정론적 평가 (UNVERIFIED)]');
  });

  it('renders pools-error-banner and suppresses pool cards when pool fetch fails', () => {
    const markup = renderToStaticMarkup(
      <PlacementSimulator
        nodes={sampleNodes}
        initialPoolsState="error"
        initialPoolsError="자원 풀 서비스 503 Service Unavailable"
        initialCandidates={[]}
        initialServerShards={[]}
      />
    );
    expect(markup).toContain('data-testid="pools-error-banner"');
    expect(markup).toContain('자원 풀 연동 실패');
    expect(markup).toContain('자원 풀 서비스 503 Service Unavailable');
    expect(markup).toContain('data-testid="pools-retry-btn"');
    expect(markup).not.toContain('풀 할당 가용 코어');
  });

  it('renders preview-error-banner and never synthesizes fake shards when placement-preview fails', () => {
    const markup = renderToStaticMarkup(
      <PlacementSimulator
        nodes={sampleNodes}
        initialPools={[]}
        initialPreviewState="error"
        initialPreviewError="엔드포인트 403 Forbidden: 클러스터 스케줄러 권한 부족"
        initialCandidates={[]}
        initialServerShards={[]}
      />
    );
    expect(markup).toContain('data-testid="preview-error-banner"');
    expect(markup).toContain('서버 배치 미리보기 실패');
    expect(markup).toContain('403 Forbidden: 클러스터 스케줄러 권한 부족');
    expect(markup).toContain('서버 어드미션 미검증: 가짜 샤드 상태를 생성하지 않습니다');
    expect(markup).toContain('data-testid="preview-retry-btn"');
    expect(markup).not.toContain('배치 적격 (Eligible)');
  });

  it('renders candidates-error-banner when discovery candidates fetch fails', () => {
    const markup = renderToStaticMarkup(
      <PlacementSimulator
        nodes={sampleNodes}
        initialPools={[]}
        initialCandidatesState="error"
        initialCandidatesError="디스커버리 500 내부 오류"
        initialServerShards={[]}
      />
    );
    expect(markup).toContain('data-testid="candidates-error-banner"');
    expect(markup).toContain('디스커버리 후보 조회 실패');
    expect(markup).toContain('디스커버리 500 내부 오류');
    expect(markup).toContain('data-testid="candidates-retry-btn"');
  });

  it('renders real server preview shards when placement-preview succeeds', () => {
    const sampleShards = [
      { shardId: 'shd_test_01', targetNodeId: 'Node-01-WinMain', status: '배치 적격 (Eligible)' },
    ];
    const markup = renderToStaticMarkup(
      <PlacementSimulator
        nodes={sampleNodes}
        initialPools={[]}
        initialPreviewState="success"
        initialServerShards={sampleShards}
        initialCandidates={[]}
      />
    );
    expect(markup).not.toContain('data-testid="preview-error-banner"');
    expect(markup).toContain('shd_test_01');
    expect(markup).toContain('Node-01-WinMain');
    expect(markup).toContain('배치 적격 (Eligible)');
  });

  it('renders preview-empty-state when placement preview returns 0 shards', () => {
    const markup = renderToStaticMarkup(
      <PlacementSimulator
        nodes={sampleNodes}
        initialPools={[]}
        initialPreviewState="success"
        initialServerShards={[]}
        initialCandidates={[]}
      />
    );
    expect(markup).toContain('data-testid="preview-empty-state"');
    expect(markup).toContain('가용 샤드가 없습니다');
  });

  it('renders candidates-empty-state when discovery returns 0 candidates', () => {
    const markup = renderToStaticMarkup(
      <PlacementSimulator
        nodes={sampleNodes}
        initialPools={[]}
        initialPreviewState="idle"
        initialCandidatesState="success"
        initialCandidates={[]}
        initialServerShards={[]}
      />
    );
    expect(markup).toContain('data-testid="candidates-empty-state"');
    expect(markup).toContain('승인 대기 중인 디스커버리 후보가 없습니다');
  });

  it('renders canonical pool capacity when pool list and capacity are provided', () => {
    const samplePools = [
      {
        poolId: 'pol_test_01',
        projectId: 'prj_test_01',
        name: 'Standard Compute Pool',
        status: 'active' as const,
        memberCount: 3,
      },
    ];
    const sampleCapacity = {
      poolId: 'pol_test_01',
      name: 'Standard Compute Pool',
      memberCount: 3,
      activeMemberCount: 2,
      totalOffered: { cpuMillicores: 16000, ramBytes: 64 * 1024 ** 3, gpuDevices: 2 },
      spareNow: { cpuMillicores: 12000, ramBytes: 48 * 1024 ** 3, gpuDevices: 1 },
      largestSingleNode: { cpuMillicores: 8000, ramBytes: 32 * 1024 ** 3, gpuDevices: 1 },
      nodes: [],
      note: 'pool capacity fixture',
      units: {},
      unmeasuredNodes: [],
    };

    const markup = renderToStaticMarkup(
      <PlacementSimulator
        nodes={sampleNodes}
        initialPools={samplePools}
        initialPoolCapacity={sampleCapacity}
        initialPoolCapacityState="success"
        initialCandidates={[]}
        initialServerShards={[]}
      />
    );
    expect(markup).toContain('Standard Compute Pool (3 노드)');
    expect(markup).toContain('12 / 16 Cores');
    expect(markup).toContain('48 / 64 GB');
    expect(markup).toContain('1/2 GPUs');
    expect(markup).toContain('활성 멤버: 2/3 노드');
  });

  it('renders honest claimed specs and unverified status for discovery candidates without fake online synthesis', () => {
    const sampleCandidates = [
      {
        announcementId: 'ann_test_01',
        instanceId: 'inst_01',
        sourceIp: '192.0.2.10',
        claimedHostname: 'cand-worker-01',
        claimedOsType: 'linux',
        claimedCpuCores: 8,
        claimedRamBytes: 32 * 1024 ** 3,
        claimedGpuCount: 1,
        firstSeenAt: '2026-09-22T08:00:00Z',
        lastSeenAt: '2026-09-22T08:10:00Z',
        announceCount: 5,
        stale: false,
        state: 'candidate' as const,
        verified: false as const,
      },
    ];

    const markup = renderToStaticMarkup(
      <PlacementSimulator
        nodes={sampleNodes}
        initialPools={[]}
        initialCandidates={sampleCandidates}
        initialCandidatesState="success"
        initialServerShards={[]}
      />
    );
    expect(markup).toContain('cand-worker-01');
    expect(markup).toContain('(linux)');
    expect(markup).toContain('신고 스펙 (Claimed · 실측 가용량 아님): 8C / 32 GB · 1 GPU (모델: 미제공)');
    expect(markup).toContain('CANDIDATE (미검증)');
    expect(markup).not.toContain('online');
    expect(markup).not.toContain('가용 코어');
  });
});

