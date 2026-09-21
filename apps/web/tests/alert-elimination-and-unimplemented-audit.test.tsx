// @vitest-environment happy-dom
// @ts-ignore
globalThis.IS_REACT_ACT_ENVIRONMENT = true;
import React, { act } from 'react';
import { createRoot, Root } from 'react-dom/client';
import { describe, it, expect, beforeEach, afterEach, vi } from 'vitest';
import * as fs from 'fs';
import * as path from 'path';
import { App } from '@/app/App';
import { NodeList } from '@/features/nodes/NodeList';
import { DeveloperStudio } from '@/features/studio/DeveloperStudio';
import * as clientModule from '@/shared/api/client';
import * as sessionModule from '@/features/auth/session';
import * as kernelMutationsModule from '@/shared/api/kernelMutations';
import { RunItem, ProjectItem } from '@/contracts/types';

(globalThis as any).IS_REACT_ACT_ENVIRONMENT = true;

describe('브라우저 alert() 18개소 전소 및 3분류(오류·성공·미구현) 정직화 검증 (VF-GM)', () => {
  let container: HTMLDivElement;
  let root: Root;
  let alertSpy: any;

  const mockProject: ProjectItem = {
    id: 'prj_live',
    name: 'Test Project',
  };

  beforeEach(() => {
    container = document.createElement('div');
    document.body.appendChild(container);
    root = createRoot(container);
    if (typeof window.alert !== 'function') {
      window.alert = () => {};
    }
    alertSpy = vi.spyOn(window, 'alert').mockImplementation(() => {});
  });

  afterEach(() => {
    act(() => {
      root.unmount();
    });
    container.remove();
    vi.restoreAllMocks();
  });

  it('불변식: apps/web/src 전역에서 브라우저 블로킹 alert() 호출이 0건이어야 한다 (M23 사살)', () => {
    const srcDir = path.resolve(__dirname, '../src');
    const tsFiles: string[] = [];

    function collectFiles(dir: string) {
      const entries = fs.readdirSync(dir, { withFileTypes: true });
      for (const entry of entries) {
        const full = path.join(dir, entry.name);
        if (entry.isDirectory()) {
          collectFiles(full);
        } else if (entry.isFile() && (entry.name.endsWith('.ts') || entry.name.endsWith('.tsx'))) {
          tsFiles.push(full);
        }
      }
    }

    collectFiles(srcDir);
    expect(tsFiles.length).toBeGreaterThan(10);

    const alertMatches: { file: string; line: number; text: string }[] = [];
    const alertRegex = /\balert\s*\(/g;

    for (const file of tsFiles) {
      const content = fs.readFileSync(file, 'utf-8');
      const lines = content.split('\n');
      lines.forEach((line, idx) => {
        const trimmed = line.trim();
        if (trimmed.startsWith('//') || trimmed.startsWith('/*') || trimmed.startsWith('*')) return;
        if (alertRegex.test(line)) {
          alertMatches.push({ file: path.relative(srcDir, file), line: idx + 1, text: line });
        }
      });
    }

    expect(alertMatches).toEqual([]);
    expect(alertMatches.length).toBe(0);
  });

  it('NodeList: 노드가 0개일 때 빈 상태에서 설치 가이드 토글 시 alert() 없이 role="status" 인라인 안내 및 복사 피드백이 렌더링된다', async () => {
    await act(async () => {
      root.render(
        <NodeList
          nodes={[]}
          isLoading={false}
          error={null}
        />
      );
    });

    // Verify initial empty state
    expect(container.textContent).toContain('등록된 Node가 없습니다');
    const toggleBtn = Array.from(container.querySelectorAll('button')).find((b) =>
      b.textContent?.includes('Node Agent 설치 안내')
    );
    expect(toggleBtn).toBeDefined();

    // Click toggle button
    await act(async () => {
      toggleBtn?.dispatchEvent(new MouseEvent('click', { bubbles: true }));
    });

    // Zero window.alert call invariant
    expect(alertSpy).not.toHaveBeenCalled();

    // Verify role="status" inline guide rendered
    const guideBox = container.querySelector('[data-testid="node-agent-install-guide"]');
    expect(guideBox).not.toBeNull();
    expect(guideBox?.getAttribute('role')).toBe('status');
    expect(guideBox?.textContent).toContain('python -m saintvision.agent --bootstrap');

    // Test clipboard copy action
    const writeTextMock = vi.fn().mockResolvedValue(undefined);
    try {
      Object.defineProperty(navigator, 'clipboard', {
        value: { writeText: writeTextMock },
        configurable: true,
        writable: true,
      });
    } catch {
      // Ignore if cannot redefine
    }

    const copyBtn = container.querySelector('[data-testid="copy-agent-bootstrap-btn"]') as HTMLButtonElement;
    expect(copyBtn).not.toBeNull();

    await act(async () => {
      copyBtn.dispatchEvent(new MouseEvent('click', { bubbles: true }));
    });

    const copyFeedback = container.querySelector('[data-testid="node-agent-copy-feedback"]');
    expect(copyFeedback?.getAttribute('role')).toBe('status');
    expect(copyFeedback?.textContent).toContain('클립보드에 복사되었습니다');

    // Toggle button changes to fold
    expect(toggleBtn?.textContent).toContain('설치 가이드 접기');

    // Toggle back
    await act(async () => {
      toggleBtn?.dispatchEvent(new MouseEvent('click', { bubbles: true }));
    });
    expect(container.querySelector('[data-testid="node-agent-install-guide"]')).toBeNull();
  });

  it('DeveloperStudio: 실행 중일 때 다운로드 버튼이 사전 비활성화되고 설명 title이 제공된다 (M24 사살)', async () => {
    const runningRun: RunItem = {
      id: 'run_running_01',
      projectId: 'prj_live',
      state: 'running',
      objective: 'Long running task',
      createdAt: '2026-09-22T00:00:00Z',
    };

    vi.spyOn(clientModule, 'apiClient').mockImplementation(async (path: string) => {
      if (path.includes('/execution-readiness')) {
        return { executable: true, reasons: [] };
      }
      return {};
    });

    await act(async () => {
      root.render(
        <DeveloperStudio
          project={mockProject}
          initialStep={4}
          initialRunId="run_running_01"
          runs={[runningRun]}
          nodes={[]}
        />
      );
    });

    // Artifact action download button should be disabled because state is 'running'
    const downloadBtn = container.querySelector('[data-testid="artifact-action-download-btn"]') as HTMLButtonElement;
    expect(downloadBtn).not.toBeNull();
    expect(downloadBtn.disabled).toBe(true);
    expect(downloadBtn.title).toContain('실행 진행 중인 작업의 아티팩트는 다운로드할 수 없습니다');
  });

  it('DeveloperStudio: 영수증 미발행 시 alert() 대신 studio-action-notice(role="status")가 인라인으로 표출된다', async () => {
    const failedRun: RunItem = {
      id: 'run_failed_01',
      projectId: 'prj_live',
      state: 'failed',
      objective: 'Failed task',
      createdAt: '2026-09-22T00:00:00Z',
    };

    vi.spyOn(clientModule, 'apiClient').mockImplementation(async (path: string) => {
      if (path.includes('/result')) {
        throw { problem: { detail: '결과 아티팩트가 서버에 생성되지 않았습니다', status: 404 } };
      }
      if (path.includes('/artifacts')) {
        throw { problem: { detail: '레거시 경로 산출물 부재', status: 404 } };
      }
      return {};
    });

    await act(async () => {
      root.render(
        <DeveloperStudio
          project={mockProject}
          initialStep={4}
          initialRunId="run_failed_01"
          runs={[failedRun]}
          nodes={[]}
        />
      );
    });

    // Inspect Receipt button click
    const inspectBtn = container.querySelector('[data-testid="inspect-receipt-btn"]') as HTMLButtonElement;
    expect(inspectBtn).not.toBeNull();

    await act(async () => {
      inspectBtn.dispatchEvent(new MouseEvent('click', { bubbles: true }));
    });

    // alert() was NOT called
    expect(alertSpy).not.toHaveBeenCalled();

    // studio-action-notice banner is rendered with role="status" (info 안내)
    const notice = container.querySelector('[data-testid="studio-action-notice"]');
    expect(notice).not.toBeNull();
    expect(notice?.getAttribute('role')).toBe('status');
    expect(notice?.textContent).toContain('물리 정지 영수증(NodeStopReceipt) 안내');

    // Dismiss button
    const dismissBtn = container.querySelector('[data-testid="studio-action-notice-dismiss"]') as HTMLButtonElement;
    expect(dismissBtn).not.toBeNull();
    await act(async () => {
      dismissBtn.dispatchEvent(new MouseEvent('click', { bubbles: true }));
    });
    expect(container.querySelector('[data-testid="studio-action-notice"]')).toBeNull();
  });

  it('DeveloperStudio: ADR-044 복구 Step 준비 성공 시 role="status" 완료 배너가 표출된다', async () => {
    const recoveringRun: RunItem = {
      id: 'run_rec_02',
      projectId: 'prj_live',
      state: 'recovering',
      objective: 'Recover task',
      createdAt: '2026-09-22T00:00:00Z',
    };

    vi.spyOn(clientModule, 'apiClient').mockImplementation(async (path: string) => {
      if (path.includes('/resume/prepare')) {
        return { status: 'prepared' };
      }
      return {};
    });

    await act(async () => {
      root.render(
        <DeveloperStudio
          project={mockProject}
          initialStep={4}
          initialRunId="run_rec_02"
          runs={[recoveringRun]}
          nodes={[]}
        />
      );
    });

    // Look for prepare resume button
    const resumeBtns = Array.from(container.querySelectorAll('button')).filter((b) =>
      b.textContent?.includes('복구 Step 준비')
    );
    expect(resumeBtns.length).toBeGreaterThan(0);

    await act(async () => {
      resumeBtns[0].dispatchEvent(new MouseEvent('click', { bubbles: true }));
    });

    // alert() not called
    expect(alertSpy).not.toHaveBeenCalled();

    // Notice banner rendered with status role
    const notice = container.querySelector('[data-testid="studio-action-notice"]');
    expect(notice).not.toBeNull();
    expect(notice?.getAttribute('role')).toBe('status');
    expect(notice?.textContent).toContain('ADR-044 Frozen Input Hash 고정 및 복구 단계가 준비되었습니다');
  });

  it('App: 로그인 세션 주입 후 전역 승인 반려 실패 시 alert() 대신 role="alert" 인라인 배너가 표출된다', async () => {
    vi.spyOn(sessionModule, 'hasLoginCallback').mockReturnValue(true);
    vi.spyOn(sessionModule, 'completeLogin').mockResolvedValue({
      token: 'mock-jwt',
      user: { id: 'admin_1', name: 'Admin', role: 'admin', tenantId: 'tenant_live' },
    });

    vi.spyOn(clientModule, 'apiClient').mockImplementation(async (path: string) => {
      if (path === '/v1/projects') {
        return [{ id: 'prj_01', name: 'Test Project', tenantId: 'tenant_live', createdAt: '2026-09-22T00:00:00Z' }];
      }
      if (path === '/v1/nodes') {
        return { items: [], total: 0 };
      }
      if (path === '/v1/projects/prj_01/runs') {
        return { items: [] };
      }
      if (path === '/v1/projects/prj_01/approvals') {
        return {
          items: [
            {
              id: 'appr_01',
              projectId: 'prj_01',
              decision: 'pending',
              actionType: 'run_dispatch',
              riskScore: 40,
              createdAt: '2026-09-22T00:00:00Z',
              policyFingerprint: 'fp-123',
            },
          ],
        };
      }
      if (path === '/v1/projects/prj_01/workspaces') {
        return [];
      }
      return {};
    });

    vi.spyOn(kernelMutationsModule, 'decideApproval').mockRejectedValue({
      problem: { detail: '보안 정책 반려 거부 (권한 없음)', code: 'SEC-403' },
    });

    await act(async () => {
      root.render(<App />);
    });

    // Find and switch to approvals tab
    const tabs = Array.from(container.querySelectorAll('button'));
    const approvalsNav = tabs.find((b) => b.textContent?.includes('승인'));
    if (approvalsNav) {
      await act(async () => {
        approvalsNav.dispatchEvent(new MouseEvent('click', { bubbles: true }));
      });
    }

    // Find Reject button
    const buttons = Array.from(container.querySelectorAll('button'));
    const rejectBtn = buttons.find((b) => b.textContent?.includes('반려'));

    if (rejectBtn) {
      await act(async () => {
        try {
          rejectBtn.dispatchEvent(new MouseEvent('click', { bubbles: true }));
        } catch {
          // Expected throw
        }
      });

      // alert() must NOT be called
      expect(alertSpy).not.toHaveBeenCalled();

      // App global action error banner rendered
      const errorBanner = container.querySelector('[data-testid="app-global-action-error"]');
      expect(errorBanner).not.toBeNull();
      expect(errorBanner?.getAttribute('role')).toBe('alert');
      expect(errorBanner?.textContent).toContain('승인 반려 실패');

      // Dismiss button test
      const dismissBtn = container.querySelector('[data-testid="app-global-action-error-dismiss"]') as HTMLButtonElement;
      expect(dismissBtn).not.toBeNull();
      await act(async () => {
        dismissBtn.dispatchEvent(new MouseEvent('click', { bubbles: true }));
      });
      expect(container.querySelector('[data-testid="app-global-action-error"]')).toBeNull();
    }
  });
});
