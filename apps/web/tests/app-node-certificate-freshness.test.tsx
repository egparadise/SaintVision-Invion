// @vitest-environment happy-dom
// @ts-ignore
globalThis.IS_REACT_ACT_ENVIRONMENT = true;
import React, { act } from 'react';
import { createRoot, type Root } from 'react-dom/client';
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest';
import { App } from '../src/app/App';
import * as session from '../src/features/auth/session';
import * as client from '../src/shared/api/client';
import * as projects from '../src/shared/api/projectObservation';
import * as runs from '../src/shared/api/runApprovalObservation';
import * as fabric from '../src/features/desktop/fabricControlApi';
import * as storage from '../src/shared/api/storageObservation';
import type { ProjectNodeCertificateObservationResponse } from '../src/contracts/node-certificate-observation';

const initialTime = Date.parse('2026-11-04T04:00:00Z');
const projectA = 'prj_01ARZ3NDEKTSV4RRFFQ69G5FAV';
const projectB = 'prj_01ARZ3NDEKTSV4RRFFQ69G5FAW';
const nodeId = 'nod_01ARZ3NDEKTSV4RRFFQ69G5FAV';
const day = 86400000;

function observation(projectId = projectA, expiry = initialTime + 3 * day): ProjectNodeCertificateObservationResponse {
  const now = Date.now();
  return {
    source: 'execution-kernel', scope: 'project-node-certificates', projectId,
    observedAt: new Date(now).toISOString(), complete: true,
    items: [{ nodeId, certificateNotAfter: new Date(expiry).toISOString(), channelEnabled: true }],
    trust: {
      state: expiry <= now ? 'expired' : expiry - 2 * day <= now ? 'renewal-window' : 'ok',
      earliestCertificateNotAfter: new Date(expiry).toISOString(),
      renewalWindowStartsAt: new Date(expiry - 2 * day).toISOString(),
      secondsUntilEarliestExpiry: Math.floor((expiry - now) / 1000),
    },
  };
}

describe('App canonical certificate trust remains bounded while refreshes hang', () => {
  let root: Root;
  let container: HTMLDivElement;
  let mode: 'valid' | 'pending-node' | 'pending-certificate' | 'reject' | 'missing-item';
  let expiry: number;
  let nodeCalls: number;
  let pending: Array<(value: ProjectNodeCertificateObservationResponse) => void>;
  let unauthorized: Parameters<typeof client.onUnauthorized>[0];

  beforeEach(() => {
    vi.useFakeTimers();
    vi.setSystemTime(initialTime);
    localStorage.clear();
    container = document.createElement('div');
    document.body.appendChild(container);
    root = createRoot(container);
    mode = 'valid'; expiry = initialTime + 3 * day; nodeCalls = 0; pending = [];
    vi.spyOn(session, 'hasLoginCallback').mockReturnValue(true);
    vi.spyOn(session, 'completeLogin').mockImplementation(async () => ({
      token: 'test-token',
      user: { id: 'usr_test', name: 'Certificate Observer', role: 'developer', tenantId: 'ten_test' },
      expiresAt: Math.floor(Date.now() / 1000) + 1800,
    }));
    vi.spyOn(session, 'commitSession').mockImplementation(() => {});
    vi.spyOn(client, 'onUnauthorized').mockImplementation(listener => { unauthorized = listener; });
    vi.spyOn(projects, 'fetchProjects').mockResolvedValue([projectA, projectB].map(id => ({
      id, name: id, tenantId: 'ten_test', createdAt: new Date(initialTime).toISOString(),
    })));
    vi.spyOn(projects, 'fetchProjectWorkspaces').mockResolvedValue([]);
    vi.spyOn(runs, 'fetchObservedRuns').mockResolvedValue([]);
    vi.spyOn(runs, 'fetchObservedApprovals').mockResolvedValue([]);
    vi.spyOn(fabric, 'getDiscoveryCandidates').mockResolvedValue([]);
    vi.spyOn(fabric, 'getStorageContributions').mockResolvedValue([]);
    vi.spyOn(fabric, 'getNodeResourceUsage').mockResolvedValue(null);
    vi.spyOn(storage, 'fetchStorageObservation').mockResolvedValue(null);
    vi.spyOn(client, 'apiClient').mockImplementation(async (path: string) => {
      if (path.endsWith('/node-certificates')) {
        if (mode === 'pending-certificate') {
          return new Promise<ProjectNodeCertificateObservationResponse>(resolve => pending.push(resolve));
        }
        if (mode === 'reject') throw new Error('Certificate observation unavailable');
        const value = observation(path.includes(projectB) ? projectB : projectA, expiry);
        if (mode === 'missing-item') {
          value.items = [];
          value.trust = { state: 'unknown', earliestCertificateNotAfter: null, renewalWindowStartsAt: null, secondsUntilEarliestExpiry: null };
        }
        return value;
      }
      if (path.endsWith('/nodes')) {
        nodeCalls++;
        if (mode === 'pending-node') return new Promise(() => {});
        return { items: [{
          nodeId, hostname: 'observed-node', status: 'online', osType: 'linux',
          // This tempting but unvalidated fallback must never reach certificate UI.
          certificateNotAfter: '2099-01-01T00:00:00Z',
        }], total: 1 };
      }
      return {};
    });
  });

  afterEach(() => {
    act(() => root.unmount());
    container.remove();
    vi.restoreAllMocks();
    vi.useRealTimers();
  });

  const badge = () => container.querySelector('[data-testid="trust-status-badge"]')?.textContent;
  const certificate = () => container.querySelector(`[data-testid="node-card-cert-expiry-${nodeId}"]`)?.textContent;
  async function advance(ms: number) {
    await act(async () => { await vi.advanceTimersByTimeAsync(ms); });
  }
  async function clickButton(label: string) {
    const button = Array.from(container.querySelectorAll('button')).find(button =>
      button.textContent?.includes(label) || button.getAttribute('aria-label')?.includes(label));
    expect(button, label).toBeDefined();
    await act(async () => button!.click());
  }
  async function mountDesktop() {
    await act(async () => root.render(<App />));
    await advance(0);
    await clickButton('Web Desktop');
  }
  async function chooseProject(projectId: string) {
    const selector = container.querySelector<HTMLSelectElement>('[data-testid="project-selector"]');
    expect(selector).not.toBeNull();
    await act(async () => {
      selector!.value = projectId;
      selector!.dispatchEvent(new Event('change', { bubbles: true }));
    });
  }

  it.each(['pending-node', 'pending-certificate'] as const)(
    'shows unknown after 60s when every subsequent %s refresh stays pending, without poll flicker', async pendingMode => {
      await mountDesktop();
      expect(badge()).toBe('● 인증서 정상');
      expect(certificate()).toContain('2026-11-07');
      mode = pendingMode;
      await advance(5000);
      expect(badge()).toBe('● 인증서 정상');
      await advance(55000);
      expect(nodeCalls).toBeGreaterThan(10);
      expect(badge()).toBe('● 인증서 정상'); // The verifier permits exactly 60s.
      await advance(1);
      expect(badge()).toBe('● 신뢰 미확인');
      expect(certificate()).toContain('미확인');
      expect(container.querySelector('[data-testid="trust-expiry-banner"]')).toBeNull();
      await advance(10000);
      expect(badge()).toBe('● 신뢰 미확인');
    },
  );

  it('crosses a fresh near-expiry observation into expired between polls while refreshes remain pending', async () => {
    expiry = initialTime + 12345;
    await mountDesktop();
    expect(badge()).toBe('● 인증서 갱신 창');
    mode = 'pending-certificate';
    await advance(12344);
    expect(badge()).toBe('● 인증서 갱신 창');
    await advance(1);
    expect(badge()).toBe('● 인증서 만료');
    expect(container.querySelector('[data-testid="trust-expiry-banner"]')?.textContent).toContain('인증서 만료');
    expect(certificate()).toContain('(만료됨)');
  });

  it('enters the renewal window on its time boundary without requiring a completed refresh', async () => {
    expiry = initialTime + 2 * day + 12345;
    await mountDesktop();
    expect(badge()).toBe('● 인증서 정상');
    mode = 'pending-node';
    await advance(12345);
    expect(badge()).toBe('● 인증서 갱신 창');
    const banner = container.querySelector('[data-testid="trust-expiry-banner"]')?.textContent;
    expect(banner).toContain('갱신 필요');
    expect(banner).not.toContain('스케줄러');
  });

  it.each(['reject', 'missing-item'] as const)('clears per-node certificate values on %s observation instead of using NodePage fallback', async failureMode => {
    await mountDesktop();
    expect(badge()).toBe('● 인증서 정상');
    mode = failureMode;
    await advance(5000);
    expect(badge()).toBe('● 신뢰 미확인');
    expect(certificate()).toContain('미확인');
    expect(container.textContent).not.toContain('2099-01-01');
  });

  it('ignores an old project-scope response even after switching away and back to the same project', async () => {
    await mountDesktop();
    mode = 'pending-certificate';
    await advance(5000);
    expect(pending).toHaveLength(1);
    await clickButton('클래식 포털 뷰로 전환');
    mode = 'reject';
    await chooseProject(projectB);
    await chooseProject(projectA);
    await clickButton('Web Desktop');
    expect(badge()).toBe('● 신뢰 미확인');
    // A newly observed timestamp prevents freshness validation alone from hiding the scope bug.
    await act(async () => pending[0](observation()));
    expect(badge()).toBe('● 신뢰 미확인');
    expect(certificate()).toContain('미확인');
  });

  it('ignores an earlier session response after reauthentication to the same project', async () => {
    await mountDesktop();
    mode = 'pending-certificate';
    await advance(5000);
    expect(pending).toHaveLength(1);
    mode = 'reject';
    await act(async () => unauthorized?.({
      status: 401, code: 'AUTH-0050', title: 'Expired', detail: 'Session expired',
      instance: '/v1/nodes', traceId: 'test-session', isServerFault: false,
    }));
    // The mocked OIDC callback authenticates a new session with the same project/actor IDs.
    await advance(0);
    await clickButton('Web Desktop');
    expect(badge()).toBe('● 신뢰 미확인');
    await act(async () => pending[0](observation()));
    expect(badge()).toBe('● 신뢰 미확인');
    expect(certificate()).toContain('미확인');
  });
});
