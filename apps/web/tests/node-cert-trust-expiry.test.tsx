// @vitest-environment happy-dom
import React, { act } from 'react';
import { createRoot, Root } from 'react-dom/client';
import { describe, it, expect, beforeEach, afterEach, vi } from 'vitest';
import { ResourceExplorer, formatKstDateTime, getTrustBannerInfo } from '../src/features/desktop/ResourceExplorer';
import { observedNode } from '../src/shared/api/nodeObservation';
import type { NodeItem, ClusterTrustSummary } from '../src/contracts/types';

describe('Card 303: Node Certificate Expiry & Trust Renewal State', () => {
  let container: HTMLDivElement;
  let root: Root;

  const mockNodeOnline: NodeItem = {
    id: 'nod_pilot_01',
    hostname: 'pilot-node-01',
    status: 'online',
    os: 'linux',
    cpuCores: 8,
    cpuUsagePercent: 15,
    memoryTotalBytes: 32 * 1024 ** 3,
    memoryUsedBytes: 8 * 1024 ** 3,
    storageTotalBytes: 500 * 1024 ** 3,
    storageUsedBytes: 100 * 1024 ** 3,
    gpuCount: 0,
    heartbeatAt: '2026-10-27T05:00:00Z',
    certificateNotAfter: '2026-11-02T03:32:25Z', // 2026-11-02 12:32:25 KST
  };

  const mockNodeSecond: NodeItem = {
    id: 'nod_pilot_02',
    hostname: 'pilot-node-02',
    status: 'online',
    os: 'linux',
    cpuCores: 8,
    cpuUsagePercent: 20,
    memoryTotalBytes: 32 * 1024 ** 3,
    memoryUsedBytes: 10 * 1024 ** 3,
    storageTotalBytes: 500 * 1024 ** 3,
    storageUsedBytes: 120 * 1024 ** 3,
    gpuCount: 0,
    heartbeatAt: '2026-10-27T05:00:00Z',
    certificateNotAfter: '2026-11-02T03:32:25Z',
  };

  beforeEach(() => {
    (globalThis as any).IS_REACT_ACT_ENVIRONMENT = true;
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

  // =========================================================================
  // 1. observedNode projection & validation (Wire Contract Verification)
  // =========================================================================
  describe('observedNode certificateNotAfter contract pass-through & fail-closed', () => {
    const validMetrics = {
      nodeId: 'nod_raw_01',
      hostname: 'node-raw',
      status: 'online',
      os: 'linux',
      cpuCores: 4,
      cpuUsagePercent: 10,
      memoryTotalBytes: 16000,
      memoryUsedBytes: 4000,
      storageTotalBytes: 50000,
      storageUsedBytes: 10000,
      gpuCount: 0,
      heartbeatAt: '2026-10-27T05:00:00Z',
    };

    it('passes through valid ISO-8601 UTC string', () => {
      const projected = observedNode({
        ...validMetrics,
        certificateNotAfter: '2026-11-02T03:32:25Z',
      });
      expect(projected.certificateNotAfter).toBe('2026-11-02T03:32:25Z');
    });

    it('passes through backend snake_case certificate_not_after', () => {
      const projected = observedNode({
        ...validMetrics,
        certificate_not_after: '2026-11-02T03:32:25Z',
      });
      expect(projected.certificateNotAfter).toBe('2026-11-02T03:32:25Z');
    });

    it('preserves explicit null without decorating or guessing', () => {
      const projected = observedNode({
        ...validMetrics,
        certificateNotAfter: null,
      });
      expect(projected.certificateNotAfter).toBeNull();
    });

    it('converts invalid date string to undefined (Anti-Fabrication)', () => {
      const projected = observedNode({
        ...validMetrics,
        certificateNotAfter: 'invalid-iso-timestamp',
      });
      expect(projected.certificateNotAfter).toBeUndefined();
    });

    it('converts non-string non-null values to undefined', () => {
      expect(observedNode({ ...validMetrics, certificateNotAfter: 1730518345 }).certificateNotAfter).toBeUndefined();
      expect(observedNode({ ...validMetrics, certificateNotAfter: true }).certificateNotAfter).toBeUndefined();
      expect(observedNode({ ...validMetrics, certificateNotAfter: {} }).certificateNotAfter).toBeUndefined();
    });

    it('leaves omitted certificateNotAfter field as undefined', () => {
      const projected = observedNode(validMetrics);
      expect(projected.certificateNotAfter).toBeUndefined();
    });
  });

  // =========================================================================
  // 2. formatKstDateTime timezone unit tests
  // =========================================================================
  describe('formatKstDateTime explicit Asia/Seoul formatting', () => {
    it('formats UTC ISO timestamp into Asia/Seoul (KST) display string', () => {
      // 2026-11-02T03:32:25Z + 9h = 2026-11-02 12:32 KST
      expect(formatKstDateTime('2026-11-02T03:32:25Z')).toBe('2026-11-02 12:32 KST');
      // 2026-10-31T03:32:25Z + 9h = 2026-10-31 12:32 KST
      expect(formatKstDateTime('2026-10-31T03:32:25Z')).toBe('2026-10-31 12:32 KST');
    });

    it('fails-closed to 미확인 for null, undefined, empty, or invalid ISO', () => {
      expect(formatKstDateTime(null)).toBe('미확인');
      expect(formatKstDateTime(undefined)).toBe('미확인');
      expect(formatKstDateTime('')).toBe('미확인');
      expect(formatKstDateTime('malformed-date-string')).toBe('미확인');
    });
  });

  // =========================================================================
  // 3. getTrustBannerInfo banner logic unit tests
  // =========================================================================
  describe('getTrustBannerInfo resolver logic', () => {
    it('returns null for ok state (ok=badge only)', () => {
      const trust: ClusterTrustSummary = {
        state: 'ok',
        earliestCertificateNotAfter: '2026-11-02T03:32:25Z',
        renewalWindowStartsAt: '2026-10-31T03:32:25Z',
        secondsUntilEarliestExpiry: 518400,
      };
      expect(getTrustBannerInfo(trust)).toBeNull();
    });

    it('returns null for unknown state or absent trust', () => {
      expect(getTrustBannerInfo(null)).toBeNull();
      expect(getTrustBannerInfo(undefined)).toBeNull();
      expect(getTrustBannerInfo({ state: 'unknown', earliestCertificateNotAfter: null, renewalWindowStartsAt: null, secondsUntilEarliestExpiry: null })).toBeNull();
    });

    it('returns expired banner message for expired state', () => {
      const trust: ClusterTrustSummary = {
        state: 'expired',
        earliestCertificateNotAfter: '2026-10-23T03:32:25Z',
        renewalWindowStartsAt: '2026-10-21T03:32:25Z',
        secondsUntilEarliestExpiry: 0,
      };
      expect(getTrustBannerInfo(trust)).toEqual({
        level: 'expired',
        message: '인증서 만료 — 노드 연결 끊김',
      });
    });

    it('returns renewal-window banner message with days and hours', () => {
      const trust: ClusterTrustSummary = {
        state: 'renewal-window',
        earliestCertificateNotAfter: '2026-11-02T03:32:25Z',
        renewalWindowStartsAt: '2026-10-31T03:32:25Z',
        secondsUntilEarliestExpiry: 172800, // 2 days
      };
      expect(getTrustBannerInfo(trust)).toEqual({
        level: 'renewal-window',
        message: '자동 갱신 창 — 만료까지 2일 0시간',
      });
    });

    it('handles negative seconds gracefully by clamping to 0', () => {
      const trust: ClusterTrustSummary = {
        state: 'renewal-window',
        earliestCertificateNotAfter: '2026-11-02T03:32:25Z',
        renewalWindowStartsAt: null,
        secondsUntilEarliestExpiry: -3600,
      };
      expect(getTrustBannerInfo(trust)).toEqual({
        level: 'renewal-window',
        message: '자동 갱신 창 — 만료까지 0일 0시간',
      });
    });
  });

  // =========================================================================
  // 4. ResourceExplorer DOM rendering: 4 Trust States
  // =========================================================================
  describe('ResourceExplorer 4 Trust States DOM rendering', () => {
    it('State 1 (ok): renders trust badge in header and NO banner (ok=배지만)', async () => {
      const trust: ClusterTrustSummary = {
        state: 'ok',
        earliestCertificateNotAfter: '2026-11-02T03:32:25Z',
        renewalWindowStartsAt: '2026-10-31T03:32:25Z',
        secondsUntilEarliestExpiry: 518400,
      };

      await act(async () => {
        root.render(<ResourceExplorer nodes={[mockNodeOnline, mockNodeSecond]} trust={trust} />);
      });

      // Banner should NOT exist
      const banner = container.querySelector('[data-testid="trust-expiry-banner"]');
      expect(banner).toBeNull();

      // Trust badge in toolbar should exist with online color
      const badge = container.querySelector('[data-testid="trust-status-badge"]');
      expect(badge).not.toBeNull();
      expect(badge?.textContent).toContain('인증서 정상');
      expect((badge as HTMLElement).style.color).toBe('var(--color-status-online)');
      expect((badge as HTMLElement).style.backgroundColor).toBe('var(--color-bg-subtle)');
    });

    it('State 2 (renewal-window): renders banner with remaining days and hours', async () => {
      const trust: ClusterTrustSummary = {
        state: 'renewal-window',
        earliestCertificateNotAfter: '2026-11-02T03:32:25Z',
        renewalWindowStartsAt: '2026-10-31T03:32:25Z',
        secondsUntilEarliestExpiry: 172800, // 2 days
      };

      await act(async () => {
        root.render(<ResourceExplorer nodes={[mockNodeOnline, mockNodeSecond]} trust={trust} />);
      });

      const banner = container.querySelector('[data-testid="trust-expiry-banner"]');
      expect(banner).not.toBeNull();
      expect(banner?.getAttribute('role')).toBe('status');
      expect(banner?.textContent).toContain('자동 갱신 창 — 만료까지 2일 0시간');
      expect((banner as HTMLElement).style.color).toBe('var(--color-status-degraded)');
      expect((banner as HTMLElement).style.backgroundColor).toBe('var(--color-bg-subtle)');

      const badge = container.querySelector('[data-testid="trust-status-badge"]');
      expect(badge).not.toBeNull();
      expect(badge?.textContent).toContain('자동 갱신 창');
    });

    it('State 3 (expired): renders banner with alert role and disconnected notice', async () => {
      const trust: ClusterTrustSummary = {
        state: 'expired',
        earliestCertificateNotAfter: '2026-10-23T03:32:25Z',
        renewalWindowStartsAt: '2026-10-21T03:32:25Z',
        secondsUntilEarliestExpiry: 0,
      };

      await act(async () => {
        root.render(<ResourceExplorer nodes={[mockNodeOnline, mockNodeSecond]} trust={trust} />);
      });

      const banner = container.querySelector('[data-testid="trust-expiry-banner"]');
      expect(banner).not.toBeNull();
      expect(banner?.getAttribute('role')).toBe('alert');
      expect(banner?.textContent).toContain('인증서 만료 — 노드 연결 끊김');
      expect((banner as HTMLElement).style.color).toBe('var(--color-status-offline)');
      expect((banner as HTMLElement).style.backgroundColor).toBe('var(--color-bg-subtle)');

      const badge = container.querySelector('[data-testid="trust-status-badge"]');
      expect(badge).not.toBeNull();
      expect(badge?.textContent).toContain('인증서 만료');
    });

    it('State 4 (unknown): renders NO banner (unknown/필드 없음=배너 없음)', async () => {
      const trust: ClusterTrustSummary = {
        state: 'unknown',
        earliestCertificateNotAfter: null,
        renewalWindowStartsAt: null,
        secondsUntilEarliestExpiry: null,
      };

      await act(async () => {
        root.render(<ResourceExplorer nodes={[mockNodeOnline, mockNodeSecond]} trust={trust} />);
      });

      const banner = container.querySelector('[data-testid="trust-expiry-banner"]');
      expect(banner).toBeNull();
      const badge = container.querySelector('[data-testid="trust-status-badge"]');
      expect(badge).toBeNull();
    });
  });

  // =========================================================================
  // 5. Missing fields / invalid ISO / negative numbers / boundaries
  // =========================================================================
  describe('Robustness: Missing fields, invalid ISO, negative numbers, and boundary conditions', () => {
    it('handles absent trust prop (필드 없음=배너 없음)', async () => {
      await act(async () => {
        root.render(<ResourceExplorer nodes={[mockNodeOnline]} />);
      });
      expect(container.querySelector('[data-testid="trust-expiry-banner"]')).toBeNull();
      expect(container.querySelector('[data-testid="trust-status-badge"]')).toBeNull();
    });

    it('handles null trust prop (필드 없음=배너 없음)', async () => {
      await act(async () => {
        root.render(<ResourceExplorer nodes={[mockNodeOnline]} trust={null} />);
      });
      expect(container.querySelector('[data-testid="trust-expiry-banner"]')).toBeNull();
      expect(container.querySelector('[data-testid="trust-status-badge"]')).toBeNull();
    });

    it('handles renewal-window with missing seconds and missing earliest date without crashing', async () => {
      const trust: ClusterTrustSummary = {
        state: 'renewal-window',
        earliestCertificateNotAfter: null,
        renewalWindowStartsAt: null,
        secondsUntilEarliestExpiry: null,
      };

      await act(async () => {
        root.render(<ResourceExplorer nodes={[mockNodeOnline]} trust={trust} />);
      });

      const banner = container.querySelector('[data-testid="trust-expiry-banner"]');
      expect(banner).not.toBeNull();
      expect(banner?.textContent).toContain('자동 갱신 창 — 만료까지 0일 0시간');
    });

    it('handles invalid ISO date in trust without crashing', async () => {
      const trust: ClusterTrustSummary = {
        state: 'renewal-window',
        earliestCertificateNotAfter: 'not-a-valid-iso',
        renewalWindowStartsAt: null,
        secondsUntilEarliestExpiry: null,
      };

      await act(async () => {
        root.render(<ResourceExplorer nodes={[mockNodeOnline]} trust={trust} />);
      });

      const banner = container.querySelector('[data-testid="trust-expiry-banner"]');
      expect(banner).not.toBeNull();
      expect(banner?.textContent).toContain('자동 갱신 창 — 만료까지 0일 0시간');
    });

    it('handles negative secondsUntilEarliestExpiry without showing negative numbers or crashing', async () => {
      const trust: ClusterTrustSummary = {
        state: 'renewal-window',
        earliestCertificateNotAfter: '2026-11-02T03:32:25Z',
        renewalWindowStartsAt: null,
        secondsUntilEarliestExpiry: -7200,
      };

      await act(async () => {
        root.render(<ResourceExplorer nodes={[mockNodeOnline]} trust={trust} />);
      });

      const banner = container.querySelector('[data-testid="trust-expiry-banner"]');
      expect(banner).not.toBeNull();
      expect(banner?.textContent).toContain('자동 갱신 창 — 만료까지 0일 0시간');
    });

    it('handles boundary condition: exactly at window start (2 days = 172800s)', async () => {
      const trust: ClusterTrustSummary = {
        state: 'renewal-window',
        earliestCertificateNotAfter: '2026-11-02T03:32:25Z',
        renewalWindowStartsAt: '2026-10-31T03:32:25Z',
        secondsUntilEarliestExpiry: 172800,
      };

      await act(async () => {
        root.render(<ResourceExplorer nodes={[mockNodeOnline]} trust={trust} />);
      });

      const banner = container.querySelector('[data-testid="trust-expiry-banner"]');
      expect(banner?.textContent).toContain('자동 갱신 창 — 만료까지 2일 0시간');
    });

    it('handles boundary condition: 1 day 23 hours remaining (169200s)', async () => {
      const trust: ClusterTrustSummary = {
        state: 'renewal-window',
        earliestCertificateNotAfter: '2026-11-02T03:32:25Z',
        renewalWindowStartsAt: '2026-10-31T03:32:25Z',
        secondsUntilEarliestExpiry: 169200, // 86400 + 23 * 3600
      };

      await act(async () => {
        root.render(<ResourceExplorer nodes={[mockNodeOnline]} trust={trust} />);
      });

      const banner = container.querySelector('[data-testid="trust-expiry-banner"]');
      expect(banner?.textContent).toContain('자동 갱신 창 — 만료까지 1일 23시간');
    });
  });

  // =========================================================================
  // 6. Node row & detail KST expiration display
  // =========================================================================
  describe('Node row and node detail KST certificate expiry display', () => {
    it('renders KST expiration time in Overview tab node card', async () => {
      await act(async () => {
        root.render(<ResourceExplorer nodes={[mockNodeOnline]} initialTab="overview" />);
      });

      const expiryDiv = container.querySelector(`[data-testid="node-card-cert-expiry-${mockNodeOnline.id}"]`);
      expect(expiryDiv).not.toBeNull();
      // Must explicitly display in Asia/Seoul: 2026-11-02 12:32 KST
      expect(expiryDiv?.textContent).toContain('인증서 만료 (KST): 2026-11-02 12:32 KST');
    });

    it('renders 미확인 in Overview tab when node certificateNotAfter is missing or invalid', async () => {
      const nodeMissingCert: NodeItem = {
        ...mockNodeOnline,
        id: 'nod_missing_cert',
        certificateNotAfter: undefined,
      };

      await act(async () => {
        root.render(<ResourceExplorer nodes={[nodeMissingCert]} initialTab="overview" />);
      });

      const expiryDiv = container.querySelector(`[data-testid="node-card-cert-expiry-${nodeMissingCert.id}"]`);
      expect(expiryDiv).not.toBeNull();
      expect(expiryDiv?.textContent).toContain('인증서 만료 (KST): 미확인');
    });

    it('renders KST expiration time in Nodes tab node selector and node detail', async () => {
      await act(async () => {
        root.render(
          <ResourceExplorer
            nodes={[mockNodeOnline]}
            initialTab="nodes"
            initialNodeDetail={{
              node: {
                nodeId: mockNodeOnline.id,
                hostname: mockNodeOnline.hostname,
                osType: 'linux',
                status: 'online',
                heartbeatSequence: 42,
                lastHeartbeatAt: '2026-10-27T05:00:00Z',
              },
              capabilities: [],
            }}
          />
        );
      });

      // Selector bar span
      const selectorExpiry = container.querySelector('[data-testid="selected-node-cert-expiry"]');
      expect(selectorExpiry).not.toBeNull();
      expect(selectorExpiry?.textContent).toContain('인증서 만료 (KST): 2026-11-02 12:32 KST');

      // Detail grid div
      const detailExpiry = container.querySelector('[data-testid="node-detail-cert-expiry"]');
      expect(detailExpiry).not.toBeNull();
      expect(detailExpiry?.textContent).toContain('인증서 만료 (KST): 2026-11-02 12:32 KST');
    });
  });
});
