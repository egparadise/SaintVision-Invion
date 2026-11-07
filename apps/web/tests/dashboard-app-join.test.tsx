// @vitest-environment happy-dom
import React, { act } from 'react';
import { createRoot, type Root } from 'react-dom/client';
import { readFileSync } from 'node:fs';
import { beforeEach, afterEach, expect, it, vi } from 'vitest';
import { App } from '../src/app/App';
import * as session from '../src/features/auth/session';
import * as client from '../src/shared/api/client';
import * as projects from '../src/shared/api/projectObservation';
import * as runs from '../src/shared/api/runApprovalObservation';
import * as fabric from '../src/features/desktop/fabricControlApi';
import * as storage from '../src/shared/api/storageObservation';

const input = (file: string) => JSON.parse(readFileSync(new URL('../../../docs/vault/30_Development/Evidence/fleet5-dashboard-canonical-resource-health-r1-20261108-codex/root-inputs/actual-canonical-API-inputs/' + file, import.meta.url), 'utf8'));
const project = input('capacity.json').projectId;
const otherProject = 'prj_01ARZ3NDEKTSV4RRFFQ69G5FAW';
const page = input('nodes.json');
const usage = (id: string) => input(`resource-usage-${id}.json`);
let root: Root, host: HTMLDivElement;
let mode: 'good' | 'pending' | 'fail';
let calls: string[];
let pending: Array<{ resolve: (value: unknown) => void; signal?: AbortSignal; nodeId: string }>;
beforeEach(() => {
  (globalThis as any).IS_REACT_ACT_ENVIRONMENT = true;
  vi.useFakeTimers(); vi.setSystemTime(Date.parse(usage(page.items[0].nodeId).stateAsOf) + 2000);
  localStorage.clear(); sessionStorage.clear(); client.setAuthToken('isolated-dashboard-session');
  host = document.createElement('div'); document.body.appendChild(host); root = createRoot(host);
  mode = 'good'; calls = []; pending = [];
  vi.spyOn(session, 'hasLoginCallback').mockReturnValueOnce(true).mockReturnValue(false);
  vi.spyOn(session, 'completeLogin').mockResolvedValue({ token: 'isolated-dashboard-session', expiresAt: Math.floor(Date.now() / 1000) + 1800,
    user: { id: 'isolated-dashboard-subject', name: 'Isolated observer', role: 'developer', tenantId: 'isolated-dashboard-tenant' } });
  vi.spyOn(session, 'commitSession').mockImplementation(() => {});
  vi.spyOn(session, 'performLogout').mockImplementation((() => {}) as any);
  vi.spyOn(projects, 'fetchProjects').mockResolvedValue([project, otherProject].map(id => ({ id, name: id, tenantId: 'isolated-dashboard-tenant', createdAt: new Date().toISOString() })));
  vi.spyOn(projects, 'fetchProjectWorkspaces').mockResolvedValue([]);
  vi.spyOn(runs, 'fetchObservedRuns').mockResolvedValue([]); vi.spyOn(runs, 'fetchObservedApprovals').mockResolvedValue([]);
  vi.spyOn(fabric, 'getDiscoveryCandidates').mockResolvedValue([]); vi.spyOn(fabric, 'getStorageContributions').mockResolvedValue([]);
  vi.spyOn(storage, 'fetchStorageObservation').mockResolvedValue(null);
  vi.spyOn(globalThis, 'fetch').mockResolvedValue(new Response(JSON.stringify({ status: 'ok', version: 'isolated-cp' }), { headers: { 'content-type': 'application/json' } }));
  vi.spyOn(client, 'apiClient').mockImplementation(async (path, options) => {
    if (path.endsWith('/node-certificates')) throw new Error('isolated certificate prerequisite absent');
    if (path.endsWith('/nodes')) return path.includes(otherProject) ? { items: [] } : structuredClone(page);
    if (path.endsWith('/resource-usage')) {
      calls.push(path);
      const id = path.split('/nodes/')[1].split('/')[0];
      if (mode === 'pending') return new Promise(resolve => pending.push({ resolve, signal: options?.signal, nodeId: id }));
      if (mode === 'fail') throw new Error('isolated resource read failed');
      return usage(id);
    }
    return {};
  });
});
afterEach(() => { act(() => root.unmount()); host.remove(); vi.restoreAllMocks(); client.clearAuthToken(); vi.useRealTimers(); });
const advance = async (ms = 0) => act(async () => { await vi.advanceTimersByTimeAsync(ms); });
const mount = async () => { await act(async () => root.render(<App />)); await advance(); };
const text = () => host.textContent ?? '';

it('App joins exact canonical three-field nodes on genuine5sec polls without card/badge remounts or per-render fanout', async () => {
  await mount();
  expect(text()).toContain('제공 1500m'); expect(text()).toContain('제공 192 MiB');
  const card = host.querySelector('[data-testid="shared-total-cpu"]');
  const badge = host.querySelector(`[data-testid="node-status-badge-${page.items[0].nodeId}"]`);
  expect(badge?.textContent).toContain('ONLINE'); expect(calls).toHaveLength(3);
  await advance(1000); expect(calls).toHaveLength(3);
  await advance(9000); expect(calls).toHaveLength(9);
  expect(host.querySelector('[data-testid="shared-total-cpu"]')).toBe(card);
  expect(host.querySelector(`[data-testid="node-status-badge-${page.items[0].nodeId}"]`)).toBe(badge);
});

it('identity/status/heartbeat remain visible while usage hangs; last-good becomes explicit stale on per-node failure', async () => {
  mode = 'pending'; await mount();
  expect(host.querySelectorAll('[data-testid^="node-status-badge-"]')).toHaveLength(3);
  expect(text()).toContain('자원 관측 확인 중'); expect(text()).not.toContain('제공 1500m');
  mode = 'good'; await advance(5000); expect(text()).toContain('제공 1500m');
  mode = 'fail'; await advance(5000);
  expect(text()).toContain('isolated resource read failed'); expect(text()).toContain('이전 제공 500m');
  expect(host.querySelector('[data-testid="shared-total-cpu"]')?.textContent).toContain('현재 자원 미관측');
});

it('late aborted prior-project usage cannot restore the old project, even when transport ignores AbortSignal', async () => {
  mode = 'pending'; await mount(); const old = [...pending];
  const selector = host.querySelector<HTMLSelectElement>('[data-testid="project-selector"]')!;
  await act(async () => { selector.value = otherProject; selector.dispatchEvent(new Event('change', { bubbles: true })); });
  await advance(); expect(old.every(row => row.signal?.aborted)).toBe(true);
  await act(async () => old.forEach(row => row.resolve(usage(row.nodeId))));
  expect(text()).not.toContain(page.items[0].nodeId); expect(text()).not.toContain('제공 1500m');
});

it('logout and manual refresh invalidate outstanding resource responses without reviving stale data', async () => {
  await mount(); mode = 'pending'; await advance(5000); const old = [...pending]; mode = 'good';
  await act(async () => (host.querySelector('[data-testid="cluster-refresh-btn"]') as HTMLButtonElement).click()); await advance();
  expect(old.every(row => row.signal?.aborted)).toBe(true);
  await act(async () => old.forEach(row => { const bad = usage(row.nodeId); bad.resources.forEach((r: any) => { if (r.kind === 'cpu') r.offered = 999; }); row.resolve(bad); }));
  expect(text()).toContain('제공 1500m'); expect(text()).not.toContain('999m');
  mode = 'pending'; await advance(5000); const late = [...pending];
  const logout = Array.from(host.querySelectorAll('button')).find(button => button.textContent?.includes('로그아웃'))!;
  await act(async () => logout.click());
  await act(async () => late.forEach(row => row.resolve(usage(row.nodeId))));
  expect(text()).not.toContain('제공 1500m'); expect(host.querySelector('[data-testid="canonical-cluster-resources"]')).toBeNull();
});
