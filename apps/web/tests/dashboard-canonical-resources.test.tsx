// @vitest-environment happy-dom
import React, { act } from 'react';
import { createRoot, type Root } from 'react-dom/client';
import { readFileSync } from 'node:fs';
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest';
import { observedNode } from '../src/shared/api/nodeObservation';
import { checkedDashboardResources, currentResourceRows, joinDashboardResources } from '../src/shared/api/dashboardResources';
import { ClusterOverview } from '../src/features/dashboard/ClusterOverview';
import { Header } from '../src/shared/ui/Header';
import * as client from '../src/shared/api/client';

const input = (file: string) => JSON.parse(readFileSync(new URL('../../../docs/vault/30_Development/Evidence/fleet5-dashboard-canonical-resource-health-r1-20261108-codex/root-inputs/actual-canonical-API-inputs/' + file, import.meta.url), 'utf8'));
const nodePage = () => input('nodes.json');
const usage = (id = nodePage().items[0].nodeId) => input(`resource-usage-${id}.json`);
const project = input('capacity.json').projectId;
const now = Date.parse(usage().stateAsOf) + 2000;
const nodes = () => nodePage().items.map((row: any) => ({ ...observedNode(row), resourceObservation: checkedDashboardResources(usage(row.nodeId), project, row.nodeId) }));
let root: Root, host: HTMLDivElement;
beforeEach(() => {
  (globalThis as any).IS_REACT_ACT_ENVIRONMENT = true;
  vi.useFakeTimers(); vi.setSystemTime(now); client.setAuthToken('isolated-resource-reader');
  host = document.createElement('div'); document.body.appendChild(host); root = createRoot(host);
});
afterEach(() => { act(() => root.unmount()); host.remove(); vi.restoreAllMocks(); client.clearAuthToken(); vi.useRealTimers(); });
const render = async (value = nodes(), state: 'success' | 'error' = 'success') => act(async () => root.render(
  <ClusterOverview nodes={value} runs={[]} pendingApprovalsCount={0} onNavigate={() => {}} nodesState={state} lastFetchedAt={new Date(now)} nodeError="isolated read failure" />));

describe('DASH-RESOURCE-01 recorded canonical three-field identities and two-resource usage', () => {
  it('shows real500m/64MiB each and1500m/192MiB aggregate, independently of missing legacy telemetry', async () => {
    expect(Object.keys(nodePage().items[0]).sort()).toEqual(['lastHeartbeatAt', 'nodeId', 'status']);
    expect(observedNode(nodePage().items[0])).toMatchObject({ os: 'unknown', observationOnly: true, killSwitchEngaged: true, schedulable: false });
    await render();
    expect(host.querySelector('[data-testid="shared-total-cpu"]')?.textContent).toContain('제공 1500m');
    expect(host.querySelector('[data-testid="shared-total-memory"]')?.textContent).toContain('제공 192 MiB');
    for (const row of nodePage().items) {
      expect(host.querySelector(`[data-testid="node-status-badge-${row.nodeId}"]`)?.textContent).toContain('ONLINE');
      expect(host.querySelector(`[data-testid="node-cpu-${row.nodeId}"]`)?.textContent).toContain('제공 500m');
      expect(host.querySelector(`[data-testid="node-memory-${row.nodeId}"]`)?.textContent).toContain('제공 64 MiB');
    }
    expect(host.textContent).toContain('OS·주소·실사용률: 미관측');
    expect(host.textContent).toContain('물리 하드웨어 부재를 뜻하지 않음');
    expect(host.textContent).not.toMatch(/NaN|0 GiB|평균 가동률|물리 메모리 \(RAM\) 풀/);
  });
  it('retains CPU when memory is unmeasured, with no false measured zero or physical utilization', async () => {
    const value = nodes();
    const memory = value[0].resourceObservation.usage.resources.find((r: any) => r.kind === 'memory');
    Object.assign(memory, { measured: false, reserved: null, spare: null, observedAt: null });
    await render(value);
    expect(host.querySelector('[data-testid="shared-total-cpu"]')?.textContent).toContain('1500m');
    expect(host.querySelector('[data-testid="shared-total-memory"]')?.textContent).toContain('2/3대');
    expect(host.querySelector('[data-testid="shared-total-memory"]')?.textContent).toContain('128 MiB');
  });
  it.each(['source', 'nodeId', 'stateAsOf', 'shape'])('refuses wrong outer binding/clock: %s', kind => {
    const value = usage();
    if (kind === 'source') value.source = 'discovery';
    if (kind === 'nodeId') value.nodeId = nodePage().items[1].nodeId;
    if (kind === 'stateAsOf') value.stateAsOf = 'November 7, 2026';
    if (kind === 'shape') value.projectId = project;
    expect(() => checkedDashboardResources(value, project, nodePage().items[0].nodeId)).toThrow();
  });
  it.each(['string-boolean', 'negative', 'fraction', 'unsafe', 'calendar', 'extra', 'duplicate'])('reports malformed memory without discarding valid CPU: %s', kind => {
    const value = usage(); const memory = value.resources.find((r: any) => r.kind === 'memory');
    if (kind === 'string-boolean') memory.measured = 'true';
    if (kind === 'negative') memory.offered = -1;
    if (kind === 'fraction') memory.reserved = 0.5;
    if (kind === 'unsafe') memory.capacity = Number.MAX_SAFE_INTEGER + 1;
    if (kind === 'calendar') memory.observedAt = '2026-11-31T00:00:00Z';
    if (kind === 'extra') memory.busyPercent = 0;
    if (kind === 'duplicate') value.resources.push({ ...memory });
    const checked = checkedDashboardResources(value, project, value.nodeId);
    expect(checked.issues.length).toBeGreaterThan(0);
    expect(currentResourceRows(checked, 'cpu', 'millicores', now)).toHaveLength(1);
    expect(currentResourceRows(checked, 'memory', 'bytes', now)).toHaveLength(0);
  });
  it.each(['stale', 'future', 'node-clock', 'network-error'])('keeps identity and honest previous data for %s', async kind => {
    const value = nodes();
    for (const node of value) {
      const obs = node.resourceObservation;
      if (kind === 'network-error') obs.error = 'actual fixture failure';
      else if (kind === 'node-clock') obs.usage.stateAsOf = null;
      else obs.usage.resources.forEach((r: any) => { r.observedAt = new Date(now + (kind === 'stale' ? -60001 : 5001)).toISOString(); });
    }
    await render(value);
    expect(host.querySelector('[data-testid="shared-total-cpu"]')?.textContent).toContain('현재 자원 미관측');
    expect(host.querySelectorAll('[data-testid^="node-status-badge-"]')).toHaveLength(3);
    if (kind === 'future') expect(host.textContent).not.toContain('이전 제공 500m');
    else expect(host.textContent).toContain('이전 제공 500m');
  });
  it('keeps cards/badges mounted across repeated polls and expires observations even without network completion', async () => {
    await render(); const card = host.querySelector('[data-testid="shared-total-cpu"]');
    const badge = host.querySelector('[data-testid^="node-status-badge-"]');
    for (let n = 0; n < 6; n++) { await act(async () => { await vi.advanceTimersByTimeAsync(5000); }); await render(); }
    expect(host.querySelector('[data-testid="shared-total-cpu"]')).toBe(card);
    expect(host.querySelector('[data-testid^="node-status-badge-"]')).toBe(badge);
    await act(async () => { await vi.advanceTimersByTimeAsync(31000); });
    expect(card?.textContent).toContain('현재 자원 미관측');
    await render(nodes(), 'error'); expect(host.textContent).toContain('동기화 실패');
  });
  it('joins encoded scoped reads, preserves last-good on error, and never borrows another project cache', async () => {
    const one = [observedNode(nodePage().items[0])];
    const api = vi.spyOn(client, 'apiClient').mockResolvedValueOnce(usage()).mockRejectedValue(new Error('resource unavailable'));
    const good = await joinDashboardResources(one, project, new AbortController().signal, new Map());
    expect(api).toHaveBeenCalledWith(`/v1/projects/${project}/nodes/${one[0].id}/resource-usage`, expect.objectContaining({ signal: expect.any(Object) }));
    const previous = new Map([[one[0].id, good[0].resourceObservation!]]);
    const stale = await joinDashboardResources(one, project, new AbortController().signal, previous);
    expect(stale[0].resourceObservation?.usage).toEqual(good[0].resourceObservation?.usage);
    expect(stale[0].resourceObservation?.error).toContain('resource unavailable');
    const other = await joinDashboardResources(one, 'other-project', new AbortController().signal, previous);
    expect(other[0].resourceObservation?.usage).toBeNull();
  });
  it('bounds parallel reads to four and settles hung transports on deadline/abort', async () => {
    const list = Array.from({ length: 8 }, (_, n) => ({ ...observedNode(nodePage().items[0]), id: `fixture-node-${n}` }));
    const api = vi.spyOn(client, 'apiClient').mockImplementation(() => new Promise(() => {}));
    const controller = new AbortController();
    const work = joinDashboardResources(list, project, controller.signal, new Map()).catch(error => error);
    expect(api).toHaveBeenCalledTimes(4);
    await vi.advanceTimersByTimeAsync(4000);
    expect(api).toHaveBeenCalledTimes(8);
    controller.abort(); await vi.advanceTimersByTimeAsync(0);
    expect(await work).toBeInstanceOf(Error);
  });
  it('rejects duplicate identities and stops queued work when authentication changes', async () => {
    const one = observedNode(nodePage().items[0]);
    await expect(joinDashboardResources([one, one], project, new AbortController().signal, new Map())).rejects.toThrow('identity');
    let resolve!: (value: unknown) => void;
    vi.spyOn(client, 'apiClient').mockImplementation(() => new Promise(r => { resolve = r; }));
    const work = joinDashboardResources([one], project, new AbortController().signal, new Map());
    client.setAuthToken('different-isolated-session'); resolve(usage());
    await expect(work).rejects.toThrow('auth changed');
  });
});

describe('DASH-HEALTH-02 CP-only health', () => {
  it.each(['text', 'html', 'bad-json', 'error'])('refuses %s and never substitutes portal liveness', async mode => {
    vi.spyOn(globalThis, 'fetch').mockResolvedValue(new Response(mode === 'html' ? '<html>portal</html>' : mode === 'bad-json' ? '{' : 'OK',
      { status: mode === 'error' ? 503 : 200, headers: { 'content-type': mode === 'bad-json' ? 'application/json' : mode === 'html' ? 'text/html' : 'text/plain' } }));
    await act(async () => root.render(<Header currentTheme="dark" onToggleTheme={() => {}} activeTab="dashboard" onSelectTab={() => {}} />));
    expect(fetch).toHaveBeenCalledWith('/gateway-healthz', expect.objectContaining({ credentials: 'omit', cache: 'no-store' }));
    expect(host.textContent).toContain('비정상 응답');
  });
});
