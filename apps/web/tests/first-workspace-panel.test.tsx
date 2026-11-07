// @vitest-environment happy-dom
import React, { act } from 'react';
import { createRoot, type Root } from 'react-dom/client';
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest';
import { webcrypto } from 'node:crypto';
import { FirstWorkspacePanel } from '../src/features/studio/FirstWorkspacePanel';
import { DeveloperStudio } from '../src/features/studio/DeveloperStudio';
import * as client from '../src/shared/api/client';
import golden from './fixtures/first-workspace-golden.json';
import { runResultViewFixture } from './fixtures/run-result';
let root: Root; let host: HTMLDivElement;
const ready = { workspaceId: golden.workload.workspaceId, projectId: golden.scope.projectId, name: 'Isolated CPU Workspace',
  status: 'ready', nodeId: golden.workload.targetNodeId, toolName: null, createdAt: '2026-11-07T00:00:00Z', allowedNext: ['suspended'] };
const buttons = () => Array.from(host.querySelectorAll('button'));
async function untilVisible(test: () => boolean) {
  const deadline = Date.now() + 2000;
  while (!test() && Date.now() < deadline) {
    await act(async () => { await new Promise(resolve => setTimeout(resolve, 10)); });
  }
  expect(test(), host.textContent ?? 'Missing first Workspace UI').toBe(true);
}
beforeEach(() => {
  (globalThis as any).IS_REACT_ACT_ENVIRONMENT = true;
  sessionStorage.clear(); client.clearAuthToken(); client.setAuthToken('isolated-panel-token');
  vi.stubGlobal('crypto', webcrypto);
  host = document.createElement('div'); document.body.appendChild(host); root = createRoot(host);
});
afterEach(() => { act(() => root.unmount()); host.remove(); client.clearAuthToken(); vi.restoreAllMocks(); vi.unstubAllGlobals(); });
describe('first Workspace visible prerequisite and scope guards', () => {
  it('is reachable from the real Studio stepper with no simulated placement or Run creation', async () => {
    const api = vi.spyOn(client, 'apiClient').mockResolvedValue({ projectId: golden.scope.projectId, count: 0, workspaces: [] });
    await act(async () => root.render(<DeveloperStudio project={{ id: golden.scope.projectId, name: 'Isolated project' }} nodes={[]} runs={[]}
      currentUser={{ id: golden.scope.subjectId, tenantId: golden.scope.tenantId, name: 'Isolated requester', role: 'owner' }} />));
    await act(async () => (host.querySelector('[data-testid="studio-stepper-step-3"]') as HTMLButtonElement).click());
    expect(host.querySelector('[data-testid="first-workspace-panel"]')).not.toBeNull();
    expect(host.querySelector('[data-testid="first-intent-prerequisite"]')).not.toBeNull();
    expect(api.mock.calls.some(([, options]) => options?.method === 'POST')).toBe(false);
  });
  it('shows no ready Workspace honestly and cannot create/prepare/enqueue', async () => {
    const api = vi.spyOn(client, 'apiClient').mockResolvedValue({ projectId: golden.scope.projectId, count: 0, workspaces: [] });
    await act(async () => root.render(<FirstWorkspacePanel scope={golden.scope} approvals={[]} />));
    expect(host.textContent).toContain('실제 ready Workspace가 없습니다');
    expect(host.querySelector('[data-testid="first-intent-prerequisite"]')).not.toBeNull();
    expect(buttons().find(b => b.textContent?.includes('Draft Run'))?.disabled).toBe(true);
    expect(buttons().find(b => b.textContent?.includes('입력 동결'))?.disabled).toBe(true);
    expect(api.mock.calls.every(([, options]) => !options?.method || options.method === 'GET')).toBe(true);
    expect(host.querySelector('[data-testid="first-enqueue-accepted"]')).toBeNull();
  });
  it('does not turn ready workspace summaries into an invented intent or mutable generic Run binding', async () => {
    const api = vi.spyOn(client, 'apiClient').mockResolvedValue({ projectId: golden.scope.projectId, count: 1, workspaces: [ready] });
    await act(async () => root.render(<FirstWorkspacePanel scope={golden.scope} approvals={[]} />));
    const select = host.querySelector('select')!;
    await act(async () => { select.value = ready.workspaceId; select.dispatchEvent(new Event('change', { bubbles: true })); });
    expect(host.querySelector('[data-testid="first-intent"]')).toBeNull();
    expect(buttons().find(b => b.textContent?.includes('Draft Run'))?.disabled).toBe(true);
    expect(api.mock.calls.some(([, options]) => options?.method === 'POST')).toBe(false);
  });
  it('renders actual selected intent, draft, frozen action and pending approval without claiming execution', async () => {
    vi.stubGlobal('crypto', { getRandomValues: webcrypto.getRandomValues.bind(webcrypto), subtle: webcrypto.subtle,
      randomUUID: () => golden.prepared.startId });
    const api = vi.spyOn(client, 'apiClient').mockImplementation(async (endpoint, options = {}) => {
      if (endpoint.endsWith('/workspaces')) return { projectId: golden.scope.projectId, count: 1, workspaces: [ready] };
      if (endpoint.includes('/first-intents?')) return golden.intentPage;
      if (endpoint.endsWith('/first-intents/'+golden.workload.workloadId+'/runs')) return golden.businessCreated;
      if (endpoint.endsWith('/start/prepare')) return golden.prepared;
      if (endpoint.endsWith('/result')) return { ...runResultViewFixture, runId: golden.run.runId, projectId: golden.scope.projectId, version: 1 };
      if (endpoint.endsWith('/runs/'+golden.run.runId)) return { ...golden.run, resourceReleasePending: false };
      if (endpoint.includes('/starts/')) return golden.view;
      throw new Error('Unexpected isolated route '+endpoint);
    });
    const observed = vi.fn();
    await act(async () => root.render(<FirstWorkspacePanel scope={golden.scope} approvals={[]} onRunObserved={observed} />));
    const select = host.querySelector('[aria-label="Ready Workspace"]') as HTMLSelectElement;
    await act(async () => { select.value = ready.workspaceId; select.dispatchEvent(new Event('change', { bubbles: true })); });
    await untilVisible(() => host.querySelector('[aria-label="현재 CPU intent"]') !== null);
    const intentSelect = host.querySelector('[aria-label="현재 CPU intent"]') as HTMLSelectElement;
    expect(intentSelect).not.toBeNull();
    await act(async () => { intentSelect.value = golden.workload.workloadId; intentSelect.dispatchEvent(new Event('change', { bubbles: true })); });
    await act(async () => buttons().find(b => b.textContent?.startsWith('Draft Run'))!.click());
    expect(host.querySelector('[data-testid="first-run-state"]')?.textContent).toContain('draft');
    expect(host.textContent).not.toContain('Headroom & Lease verified');
    expect(host.querySelector('[data-testid="first-enqueue-accepted"]')).toBeNull();
    const text = host.querySelector('textarea')!;
    const step = host.querySelector('[aria-label="Step ID"]') as HTMLInputElement;
    await act(async () => {
      Object.getOwnPropertyDescriptor(window.HTMLTextAreaElement.prototype, 'value')!.set!.call(text, golden.files[0].content);
      text.dispatchEvent(new Event('input', { bubbles: true })); text.dispatchEvent(new Event('change', { bubbles: true }));
      Object.getOwnPropertyDescriptor(window.HTMLInputElement.prototype, 'value')!.set!.call(step, 'cpu-step');
      step.dispatchEvent(new Event('input', { bubbles: true })); step.dispatchEvent(new Event('change', { bubbles: true }));
    });
    const prepare = buttons().find(b => b.textContent?.startsWith('입력 동결'))!;
    expect(prepare.disabled).toBe(false);
    await act(async () => prepare.click());
    await untilVisible(() => host.querySelector('[data-testid="first-frozen-action"]') !== null);
    expect(host.querySelector('[data-testid="first-frozen-action"]')?.textContent).toContain(golden.prepared.approval.actionDigest);
    expect(host.querySelector('[data-testid="first-run-state"]')?.textContent).toContain('awaiting_approval');
    expect(buttons().find(b => b.textContent?.startsWith('원래 요청자 enqueue'))?.disabled).toBe(true);
    expect(api.mock.calls.some(([url]) => url.endsWith('/start/enqueue'))).toBe(false);
    expect(observed).toHaveBeenCalledWith(golden.prepared.run);
    await act(async () => buttons().find(b => b.textContent?.startsWith('현재 승인·Run·결과 조회'))!.click());
    await untilVisible(() => Boolean(host.querySelector('[role="alert"]')?.textContent?.includes('현재 Run보다 오래되었거나')));
    expect(host.querySelector('[data-testid="first-run-result"]')).toBeNull();
    expect(host.querySelector('[data-testid="first-enqueue-accepted"]')).toBeNull();
  });
  it('sends no requests without a current credential', async () => {
    client.clearAuthToken(); const api = vi.spyOn(client, 'apiClient');
    await act(async () => root.render(<FirstWorkspacePanel scope={golden.scope} approvals={[]} />));
    expect(host.textContent).toContain('현재 인증이 필요'); expect(api).not.toHaveBeenCalled();
  });
  it('ignores a previous project response after project selection changes', async () => {
    let resolveOld!: (value: unknown) => void;
    const another = { ...golden.scope, projectId: 'prj_01ARZ3NDEKTSV4RRFFQ69G5FAW' };
    vi.spyOn(client, 'apiClient').mockImplementation(async endpoint => {
      if (endpoint.includes(golden.scope.projectId)) return new Promise(resolve => { resolveOld = resolve; });
      return { projectId: another.projectId, count: 0, workspaces: [] };
    });
    const observed = vi.fn();
    await act(async () => root.render(<FirstWorkspacePanel scope={golden.scope} approvals={[]} onRunObserved={observed} />));
    await act(async () => root.render(<FirstWorkspacePanel scope={another} approvals={[]} onRunObserved={observed} />));
    await act(async () => resolveOld({ projectId: golden.scope.projectId, count: 1, workspaces: [ready] }));
    expect(host.textContent).not.toContain(ready.name); expect(observed).not.toHaveBeenCalled();
  });
  it('ignores a delayed inventory response after session expiry', async () => {
    let resolveOld!: (value: unknown) => void;
    vi.spyOn(client, 'apiClient').mockImplementation(async () => new Promise(resolve => { resolveOld = resolve; }));
    await act(async () => root.render(<FirstWorkspacePanel scope={golden.scope} approvals={[]} />));
    await act(async () => { client.clearAuthToken(); resolveOld({ projectId: golden.scope.projectId, count: 1, workspaces: [ready] }); });
    expect(host.textContent).not.toContain(ready.name); expect(host.textContent).toContain('인증이 종료');
  });
});
