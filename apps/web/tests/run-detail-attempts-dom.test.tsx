// @vitest-environment happy-dom
import React, { act } from 'react';
import { createRoot, Root } from 'react-dom/client';
import { describe, it, expect, vi, beforeEach, afterEach } from 'vitest';
import { RunDetail } from '../src/features/runs/RunDetail';
import * as client from '../src/shared/api/client';
import { fetchRunAttempts } from '../src/shared/api/runAttemptObservation';
import type { RunItem, RunAttemptList } from '../src/contracts/types';
import { runAttemptListFixture } from './fixtures/run-attempt';

(globalThis as any).IS_REACT_ACT_ENVIRONMENT = true;

const sampleRun: RunItem = {
  id: 'run_test_01',
  projectId: 'prj_test_01',
  status: 'running',
  state: 'running',
  targetNodeId: 'nod_01JABCDEF01',
  createdAt: '2026-09-21T10:00:00Z',
  startedAt: '2026-09-21T10:00:01Z',
};

describe('RunDetail Attempts Tab - Kernel RunAttemptList Contract Binding (Claude Handoff)', () => {
  let container: HTMLDivElement;
  let root: Root;

  beforeEach(() => {
    vi.restoreAllMocks();
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

  it('Scenario 1: Switches to attempts tab and renders kernel attempt row with nodeId and startedAt from shared fixture', async () => {
    const apiSpy = vi.spyOn(client, 'apiClient').mockImplementation(async (url: string) => {
      if (url.includes('/attempts')) {
        return runAttemptListFixture as any;
      }
      if (url.includes('/shards')) {
        return { shards: [] } as any;
      }
      return {} as any;
    });

    await act(async () => {
      root.render(<RunDetail run={sampleRun} onBack={() => {}} />);
    });

    const attemptsTabBtn = Array.from(container.querySelectorAll('button')).find((b) =>
      b.textContent?.includes('6. 시도 이력')
    );
    expect(attemptsTabBtn).toBeDefined();

    await act(async () => {
      attemptsTabBtn!.click();
    });

    expect(apiSpy).toHaveBeenCalledWith(
      expect.stringContaining('/v1/projects/prj_test_01/runs/run_test_01/attempts')
    );

    const panel = container.querySelector('[data-testid="run-detail-attempts-panel"]');
    expect(panel).not.toBeNull();

    const sourceBadge = container.querySelector('[data-testid="run-attempts-source-badge"]');
    expect(sourceBadge).not.toBeNull();
    expect(sourceBadge?.textContent).toContain('출처: execution-kernel');

    const row = container.querySelector('[data-testid="run-attempt-row-1"]');
    expect(row).not.toBeNull();

    const nodeSpan = container.querySelector('[data-testid="run-attempt-node-1"]');
    expect(nodeSpan?.textContent).toBe('nod_0123456789ABCDEFGHJKMNPQRS');

    const exitSpan = container.querySelector('[data-testid="run-attempt-exit-1"]');
    expect(exitSpan?.textContent).toBe('0');
  });

  it('Scenario 2: Renders attempt with nullable startedAt: null and nodeId: null without crashing (contract richness)', async () => {
    const nullableAttempts: RunAttemptList = {
      source: 'execution-kernel',
      runId: 'run_test_01',
      attempts: [
        {
          attemptNumber: 1,
          startedAt: null,
          nodeId: null,
          commandId: null,
          stopReceiptId: null,
          exitCode: null,
          reason: 'queued_in_control_plane',
          evidenceId: null,
        },
      ],
      count: 1,
      nextCursor: null,
    };

    vi.spyOn(client, 'apiClient').mockImplementation(async (url: string) => {
      if (url.includes('/attempts')) {
        return nullableAttempts as any;
      }
      return { shards: [] } as any;
    });

    await act(async () => {
      root.render(<RunDetail run={sampleRun} onBack={() => {}} />);
    });

    const attemptsTabBtn = Array.from(container.querySelectorAll('button')).find((b) =>
      b.textContent?.includes('6. 시도 이력')
    );
    await act(async () => {
      attemptsTabBtn!.click();
    });

    const unassignedSpan = container.querySelector('[data-testid="run-attempt-node-unassigned-1"]');
    expect(unassignedSpan).not.toBeNull();
    expect(unassignedSpan?.textContent).toContain('(미배정)');

    const pendingSpan = container.querySelector('[data-testid="run-attempt-started-pending-1"]');
    expect(pendingSpan).not.toBeNull();
    expect(pendingSpan?.textContent).toContain('(대기 중)');
  });

  it('Scenario 3: Renders empty state notice when attempts array is empty', async () => {
    const emptyAttempts: RunAttemptList = {
      source: 'execution-kernel',
      runId: 'run_test_01',
      attempts: [],
      count: 0,
      nextCursor: null,
    };

    vi.spyOn(client, 'apiClient').mockImplementation(async (url: string) => {
      if (url.includes('/attempts')) {
        return emptyAttempts as any;
      }
      return { shards: [] } as any;
    });

    await act(async () => {
      root.render(<RunDetail run={sampleRun} onBack={() => {}} />);
    });

    const attemptsTabBtn = Array.from(container.querySelectorAll('button')).find((b) =>
      b.textContent?.includes('6. 시도 이력')
    );
    await act(async () => {
      attemptsTabBtn!.click();
    });

    const emptyNotice = container.querySelector('[data-testid="run-attempts-empty"]');
    expect(emptyNotice).not.toBeNull();
    expect(emptyNotice?.textContent).toContain('기록된 실행 시도가 없습니다');
  });

  it('Scenario 4: Error handling - server 500 rejection displays role="alert" with message', async () => {
    vi.spyOn(client, 'apiClient').mockImplementation(async (url: string) => {
      if (url.includes('/attempts')) {
        throw new Error('HTTP 500: Internal Server Error');
      }
      return { shards: [] } as any;
    });

    await act(async () => {
      root.render(<RunDetail run={sampleRun} onBack={() => {}} />);
    });

    const attemptsTabBtn = Array.from(container.querySelectorAll('button')).find((b) =>
      b.textContent?.includes('6. 시도 이력')
    );
    await act(async () => {
      attemptsTabBtn!.click();
    });

    const alert = container.querySelector('[role="alert"][data-testid="run-attempts-error"]');
    expect(alert).not.toBeNull();
    expect(alert?.textContent).toContain('HTTP 500: Internal Server Error');
  });

  it('Scenario 5: fetchRunAttempts adapter rejects non-canonical source mutation', async () => {
    vi.spyOn(client, 'apiClient').mockResolvedValueOnce({
      ...runAttemptListFixture,
      source: 'third-party-kernel',
    } as any);

    await expect(fetchRunAttempts('prj_test_01', 'run_test_01')).rejects.toThrow(
      "RunAttemptList source 계약 불일치: expected 'execution-kernel', got 'third-party-kernel'"
    );
  });

  it('Scenario 6: fetchRunAttempts adapter rejects missing runId', async () => {
    vi.spyOn(client, 'apiClient').mockResolvedValueOnce({
      ...runAttemptListFixture,
      runId: '',
    } as any);

    await expect(fetchRunAttempts('prj_test_01', 'run_test_01')).rejects.toThrow(
      'RunAttemptList runId 누락'
    );
  });

  it('Scenario 7: fetchRunAttempts adapter rejects invalid non-null/non-string nodeId in attempt', async () => {
    vi.spyOn(client, 'apiClient').mockResolvedValueOnce({
      ...runAttemptListFixture,
      attempts: [
        {
          attemptNumber: 1,
          startedAt: null,
          nodeId: 12345, // invalid type
          commandId: null,
          stopReceiptId: null,
          exitCode: null,
          reason: null,
          evidenceId: null,
        },
      ],
    } as any);

    await expect(fetchRunAttempts('prj_test_01', 'run_test_01')).rejects.toThrow(
      'RunAttemptItem nodeId 계약 불일치'
    );
  });

  it('Scenario 8: fetchRunAttempts adapter serializes after and limit query params correctly', async () => {
    const apiSpy = vi.spyOn(client, 'apiClient').mockResolvedValueOnce(runAttemptListFixture as any);

    await fetchRunAttempts('prj_test_01', 'run_test_01', { after: 10, limit: 25 });

    expect(apiSpy).toHaveBeenCalledWith(
      '/v1/projects/prj_test_01/runs/run_test_01/attempts?after=10&limit=25'
    );
  });
});
