// @vitest-environment happy-dom
import React, { act } from 'react';
import { createRoot, Root } from 'react-dom/client';
import { describe, it, expect, vi, beforeEach, afterEach } from 'vitest';
import { RunDetail } from '../src/features/runs/RunDetail';
import * as client from '../src/shared/api/client';
import { fetchRunLogs } from '../src/shared/api/runLogObservation';
import type { RunItem } from '../src/contracts/types';
import { runLogViewFixture } from './fixtures/run-log';

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

describe('RunDetail Logs Tab - Kernel RunLogView Contract Binding (Claude Handoff)', () => {
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

  it('Scenario 1: Switches to logs tab and renders kernel stdout from shared fixture', async () => {
    const apiSpy = vi.spyOn(client, 'apiClient').mockImplementation(async (url: string) => {
      if (url.includes('/logs')) {
        return runLogViewFixture as any;
      }
      if (url.includes('/shards')) {
        return { shards: [] } as any;
      }
      return {} as any;
    });

    await act(async () => {
      root.render(<RunDetail run={sampleRun} onBack={() => {}} />);
    });

    // Find tab button for logs
    const buttons = Array.from(container.querySelectorAll('button'));
    const logsTabBtn = buttons.find((b) => b.textContent?.includes('실시간 SSE 로그'));
    expect(logsTabBtn).toBeDefined();

    await act(async () => {
      logsTabBtn!.click();
    });

    expect(apiSpy).toHaveBeenCalledWith(
      '/v1/projects/prj_test_01/runs/run_test_01/logs'
    );

    const stdoutEl = container.querySelector('[data-testid="run-log-stdout"]');
    expect(stdoutEl).not.toBeNull();
    expect(stdoutEl?.textContent).toContain('Compiled 12 modules.');

    const sourceBadge = container.querySelector('[data-testid="run-logs-source-badge"]');
    expect(sourceBadge).not.toBeNull();
    expect(sourceBadge?.textContent).toContain('execution-kernel');

    // No redacted or truncated badge in default clean fixture
    expect(container.querySelector('[data-testid="run-logs-redacted-badge"]')).toBeNull();
    expect(container.querySelector('[data-testid="run-logs-truncated-badge"]')).toBeNull();
  });

  it('Scenario 2: Renders redacted badge when kernel marks sensitive content redacted', async () => {
    vi.spyOn(client, 'apiClient').mockImplementation(async (url: string) => {
      if (url.includes('/logs')) {
        return {
          ...runLogViewFixture,
          redacted: true,
          stdout: 'Masked token: [REDACTED]',
        } as any;
      }
      return { shards: [] } as any;
    });

    await act(async () => {
      root.render(<RunDetail run={sampleRun} onBack={() => {}} />);
    });

    const logsTabBtn = Array.from(container.querySelectorAll('button')).find((b) =>
      b.textContent?.includes('실시간 SSE 로그')
    );
    await act(async () => {
      logsTabBtn!.click();
    });

    const redactedBadge = container.querySelector('[data-testid="run-logs-redacted-badge"]');
    expect(redactedBadge).not.toBeNull();
    expect(redactedBadge?.textContent).toContain('민감정보 마스킹됨');

    const stdoutEl = container.querySelector('[data-testid="run-log-stdout"]');
    expect(stdoutEl?.textContent).toContain('Masked token: [REDACTED]');
  });

  it('Scenario 3: Renders truncated badge when output exceeded max buffer', async () => {
    vi.spyOn(client, 'apiClient').mockImplementation(async (url: string) => {
      if (url.includes('/logs')) {
        return {
          ...runLogViewFixture,
          truncated: true,
        } as any;
      }
      return { shards: [] } as any;
    });

    await act(async () => {
      root.render(<RunDetail run={sampleRun} onBack={() => {}} />);
    });

    const logsTabBtn = Array.from(container.querySelectorAll('button')).find((b) =>
      b.textContent?.includes('실시간 SSE 로그')
    );
    await act(async () => {
      logsTabBtn!.click();
    });

    const truncatedBadge = container.querySelector('[data-testid="run-logs-truncated-badge"]');
    expect(truncatedBadge).not.toBeNull();
    expect(truncatedBadge?.textContent).toContain('로그 잘림 (Truncated)');
  });

  it('Scenario 4: Renders absentReason notice and suppresses empty log sections when logs absent', async () => {
    vi.spyOn(client, 'apiClient').mockImplementation(async (url: string) => {
      if (url.includes('/logs')) {
        return {
          source: 'execution-kernel',
          runId: 'run_test_01',
          stdout: null,
          stderr: null,
          redacted: false,
          truncated: null,
          absentReason: 'No committed process output for this attempt',
        } as any;
      }
      return { shards: [] } as any;
    });

    await act(async () => {
      root.render(<RunDetail run={sampleRun} onBack={() => {}} />);
    });

    const logsTabBtn = Array.from(container.querySelectorAll('button')).find((b) =>
      b.textContent?.includes('실시간 SSE 로그')
    );
    await act(async () => {
      logsTabBtn!.click();
    });

    const absentEl = container.querySelector('[data-testid="run-logs-absent"]');
    expect(absentEl).not.toBeNull();
    expect(absentEl?.textContent).toContain('No committed process output for this attempt');

    // stdout and stderr must not be rendered
    expect(container.querySelector('[data-testid="run-log-stdout"]')).toBeNull();
    expect(container.querySelector('[data-testid="run-log-stderr"]')).toBeNull();
  });

  it('Scenario 5: Renders stderr in red text when present', async () => {
    vi.spyOn(client, 'apiClient').mockImplementation(async (url: string) => {
      if (url.includes('/logs')) {
        return {
          ...runLogViewFixture,
          stderr: 'Warning: Deprecated API version used',
        } as any;
      }
      return { shards: [] } as any;
    });

    await act(async () => {
      root.render(<RunDetail run={sampleRun} onBack={() => {}} />);
    });

    const logsTabBtn = Array.from(container.querySelectorAll('button')).find((b) =>
      b.textContent?.includes('실시간 SSE 로그')
    );
    await act(async () => {
      logsTabBtn!.click();
    });

    const stderrEl = container.querySelector('[data-testid="run-log-stderr"]');
    expect(stderrEl).not.toBeNull();
    expect(stderrEl?.textContent).toContain('Warning: Deprecated API version used');
  });

  it('Scenario 6: Displays role="alert" banner on network/server failure without fabricating fallback fake logs', async () => {
    vi.spyOn(client, 'apiClient').mockImplementation(async (url: string) => {
      if (url.includes('/logs')) {
        throw new Error('HTTP 500: Kernel internal error');
      }
      return { shards: [] } as any;
    });

    await act(async () => {
      root.render(<RunDetail run={sampleRun} onBack={() => {}} />);
    });

    const logsTabBtn = Array.from(container.querySelectorAll('button')).find((b) =>
      b.textContent?.includes('실시간 SSE 로그')
    );
    await act(async () => {
      logsTabBtn!.click();
    });

    const errorAlert = container.querySelector('[data-testid="run-logs-error"][role="alert"]');
    expect(errorAlert).not.toBeNull();
    expect(errorAlert?.textContent).toContain('로그 조회 실패: HTTP 500: Kernel internal error');

    // No fake stdout should be displayed
    expect(container.querySelector('[data-testid="run-log-stdout"]')).toBeNull();
  });

  it('Scenario 7: fetchRunLogs strictly rejects non-"execution-kernel" sources (Zero-Mock)', async () => {
    vi.spyOn(client, 'apiClient').mockResolvedValue({
      source: 'unauthorized-third-party',
      runId: 'run_test_01',
      stdout: 'fake stdout',
      stderr: null,
      redacted: false,
      truncated: null,
      absentReason: null,
    });

    await expect(fetchRunLogs('prj_test', 'run_test')).rejects.toThrow(
      "RunLogView source 계약 불일치: expected 'execution-kernel', got 'unauthorized-third-party'"
    );
  });

  it('Scenario 8: fetchRunLogs strictly rejects invalid redacted boolean (Contract Type Guard)', async () => {
    vi.spyOn(client, 'apiClient').mockResolvedValue({
      source: 'execution-kernel',
      runId: 'run_test_01',
      stdout: 'ok',
      stderr: null,
      redacted: 'not-a-boolean' as any,
      truncated: null,
      absentReason: null,
    });

    await expect(fetchRunLogs('prj_test', 'run_test')).rejects.toThrow(
      'RunLogView redacted 계약 불일치'
    );
  });
});
