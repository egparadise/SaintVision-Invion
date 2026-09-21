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
});
