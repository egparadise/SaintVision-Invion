// @vitest-environment happy-dom
// @ts-ignore
globalThis.IS_REACT_ACT_ENVIRONMENT = true;
import React, { act } from 'react';
import { createRoot, Root } from 'react-dom/client';
import { describe, it, expect, vi, beforeEach, afterEach } from 'vitest';
import { IntranetDeploymentView } from '../src/features/deployment/IntranetDeploymentView';
import {
  fetchReleaseManifests,
  fetchReleaseManifestDetail,
  isValidReleaseManifest,
  ReleaseManifestResponse,
  ReleaseManifestDetailResponse,
} from '../src/shared/api/releaseObservation';

describe('Card 183 / S12-FE: Server Release Manifests & Operator Sign-off Binding', () => {
  let container: HTMLDivElement;
  let root: Root;

  beforeEach(() => {
    container = document.createElement('div');
    document.body.appendChild(container);
    root = createRoot(container);
    vi.restoreAllMocks();
  });

  afterEach(() => {
    act(() => {
      root.unmount();
    });
    container.remove();
    vi.restoreAllMocks();
  });

  const sampleManifestSha = '0123456789abcdef0123456789abcdef0123456789abcdef0123456789abcdef';
  const sampleDigest1 = 'sha256:1111222233334444555566667777888899990000aaaabbbbccccddddeeeeffff';
  const sampleDigest2 = 'sha256:555566667777888899990000aaaabbbbccccddddeeeeffff1111222233334444';

  const mockReleaseItem: ReleaseManifestResponse = {
    releaseId: 'rel-2026-s12-001',
    version: '1.2.0-rc.1',
    componentCount: 2,
    manifestSha256: sampleManifestSha,
    createdAt: '2026-10-01T10:00:00Z',
    operatorSignOff: false,
    acceptanceCount: 0,
    components: [
      { name: 'control-plane', kind: 'service', digest: sampleDigest1 },
      { name: 'agent-runtime', kind: 'daemon', digest: sampleDigest2 },
    ],
  };

  const mockDetailUnsigned: ReleaseManifestDetailResponse = {
    release: { ...mockReleaseItem, operatorSignOff: false, acceptanceCount: 0 },
    acceptances: [],
  };

  const mockDetailSigned: ReleaseManifestDetailResponse = {
    release: { ...mockReleaseItem, operatorSignOff: true, acceptanceCount: 1 },
    acceptances: [
      {
        acceptanceId: 'acc-2026-0001',
        acceptanceIdRef: 'crit-pilot-prod-01',
        acceptedManifestSha256: sampleManifestSha,
        outcome: 'accepted',
        manifestMatches: true,
        decidedAt: '2026-10-01T10:15:00Z',
        knownLimitations: ['Air-gapped deployment only'],
      },
    ],
  };

  // =========================================================================
  // 1. API observation helper unit tests
  // =========================================================================
  describe('API observation helper: releaseObservation', () => {
    it('isValidReleaseManifest returns true for compliant manifest and false for malformed shapes', () => {
      expect(isValidReleaseManifest(mockReleaseItem)).toBe(true);
      expect(isValidReleaseManifest(null)).toBe(false);
      expect(isValidReleaseManifest({})).toBe(false);
      expect(isValidReleaseManifest({ ...mockReleaseItem, manifestSha256: 'short-sha' })).toBe(false);
      expect(isValidReleaseManifest({ ...mockReleaseItem, operatorSignOff: 'not-a-boolean' })).toBe(false);
    });

    it('fetchReleaseManifests issues GET /v1/release-manifests and parses page response', async () => {
      const mockPage = { items: [mockReleaseItem], nextCursor: null };
      vi.spyOn(globalThis, 'fetch').mockResolvedValueOnce({
        ok: true,
        status: 200,
        headers: new Headers({ 'Content-Type': 'application/json' }),
        json: async () => mockPage,
      } as Response);

      const res = await fetchReleaseManifests({ limit: 50 });
      expect(res.items).toHaveLength(1);
      expect(res.items?.[0].releaseId).toBe('rel-2026-s12-001');
      expect(res.items?.[0].operatorSignOff).toBe(false);
    });

    it('fetchReleaseManifestDetail issues GET /v1/release-manifests/:id and parses detail response', async () => {
      vi.spyOn(globalThis, 'fetch').mockResolvedValueOnce({
        ok: true,
        status: 200,
        headers: new Headers({ 'Content-Type': 'application/json' }),
        json: async () => mockDetailSigned,
      } as Response);

      const res = await fetchReleaseManifestDetail('rel-2026-s12-001');
      expect(res.release.releaseId).toBe('rel-2026-s12-001');
      expect(res.release.operatorSignOff).toBe(true);
      expect(res.acceptances).toHaveLength(1);
      expect(res.acceptances?.[0].outcome).toBe('accepted');
    });

    it('fetchReleaseManifestDetail throws on empty releaseId', async () => {
      await expect(fetchReleaseManifestDetail('')).rejects.toThrow('releaseId must be a non-empty string');
      await expect(fetchReleaseManifestDetail('   ')).rejects.toThrow('releaseId must be a non-empty string');
    });
  });

  // =========================================================================
  // 2. Server binding in IntranetDeploymentView
  // =========================================================================
  describe('IntranetDeploymentView server manifest binding', () => {
    it('renders server release manifest details when loaded from backend API', async () => {
      vi.spyOn(globalThis, 'fetch')
        .mockResolvedValueOnce({
          ok: true,
          status: 200,
          headers: new Headers({ 'Content-Type': 'application/json' }),
          json: async () => ({ items: [mockReleaseItem], nextCursor: null }),
        } as Response)
        .mockResolvedValueOnce({
          ok: true,
          status: 200,
          headers: new Headers({ 'Content-Type': 'application/json' }),
          json: async () => mockDetailSigned,
        } as Response);

      await act(async () => {
        root.render(
          <IntranetDeploymentView
            autoFetch={true}
            currentUser={{ id: 'usr_operator_lead', name: 'Lead', role: 'operator' }}
          />
        );
      });

      // 1. Verify server banner is rendered
      const serverBanner = container.querySelector('[data-testid="deployment-manifest-server-banner"]');
      expect(serverBanner).not.toBeNull();
      expect(serverBanner?.textContent).toContain('GET /v1/release-manifests');

      // 2. Verify server manifest metadata
      const versionEl = container.querySelector('[data-testid="server-release-version"]');
      expect(versionEl?.textContent).toBe('1.2.0-rc.1');

      const idEl = container.querySelector('[data-testid="server-release-id"]');
      expect(idEl?.textContent).toBe('rel-2026-s12-001');

      const shaEl = container.querySelector('[data-testid="server-manifest-sha"]');
      expect(shaEl?.textContent).toBe(sampleManifestSha);

      const countEl = container.querySelector('[data-testid="server-component-count"]');
      expect(countEl?.textContent).toBe('2 개');

      // 3. Verify server operator sign-off reflects server true state
      const signoffEl = container.querySelector('[data-testid="server-operator-signoff"]');
      expect(signoffEl?.textContent).toContain('서명 완료');
      expect(signoffEl?.textContent).toContain('operatorSignOff=true');

      // 4. Verify acceptances list
      const acceptancesEl = container.querySelector('[data-testid="server-acceptances-list"]');
      expect(acceptancesEl).not.toBeNull();
      expect(acceptancesEl?.textContent).toContain('acc-2026-0001');
      expect(acceptancesEl?.textContent).toContain('accepted');
      expect(acceptancesEl?.textContent).toContain('Air-gapped deployment only');

      // 5. Verify components list
      const compList = container.querySelector('[data-testid="server-components-list"]');
      expect(compList).not.toBeNull();
      expect(compList?.textContent).toContain('control-plane');
      expect(compList?.textContent).toContain('agent-runtime');
    });

    it('renders explicit empty state (기록 없음) without fabricating default data when tenant has 0 releases', async () => {
      vi.spyOn(globalThis, 'fetch').mockResolvedValueOnce({
        ok: true,
        status: 200,
        headers: new Headers({ 'Content-Type': 'application/json' }),
        json: async () => ({ items: [], nextCursor: null }),
      } as Response);

      await act(async () => {
        root.render(
          <IntranetDeploymentView
            autoFetch={true}
            currentUser={{ id: 'usr_operator_lead', name: 'Lead', role: 'operator' }}
          />
        );
      });

      // Explicit empty state banner
      const emptyState = container.querySelector('[data-testid="deployment-manifest-empty-state"]');
      expect(emptyState).not.toBeNull();
      expect(emptyState?.textContent).toContain('기록 없음');
      expect(emptyState?.textContent).toContain('등록된 릴리스 선언서(Release Manifest)가 없습니다');

      // Server detail section must NOT render fabricated values
      expect(container.querySelector('[data-testid="server-release-version"]')).toBeNull();
      expect(container.querySelector('[data-testid="server-manifest-sha"]')).toBeNull();
    });

    it('renders unsigned state (operatorSignOff: false) honestly when release has no acceptances', async () => {
      await act(async () => {
        root.render(
          <IntranetDeploymentView
            autoFetch={false}
            initialManifests={[mockReleaseItem]}
            initialDetail={mockDetailUnsigned}
            currentUser={{ id: 'usr_operator_lead', name: 'Lead', role: 'operator' }}
          />
        );
      });

      const signoffEl = container.querySelector('[data-testid="server-operator-signoff"]');
      expect(signoffEl).not.toBeNull();
      expect(signoffEl?.textContent).toContain('미서명 (operatorSignOff: false)');

      const acceptancesEmpty = container.querySelector('[data-testid="server-acceptances-empty"]');
      expect(acceptancesEmpty).not.toBeNull();
      expect(acceptancesEmpty?.textContent).toContain('기록된 수락 결정 없음');
    });

    it('handles 403 Forbidden cleanly with alert role and error message', async () => {
      vi.spyOn(globalThis, 'fetch').mockResolvedValueOnce({
        ok: false,
        status: 403,
        headers: new Headers({ 'Content-Type': 'application/problem+json' }),
        json: async () => ({
          type: 'about:blank',
          title: 'Forbidden',
          status: 403,
          code: 'AUTH-0403',
          category: 'AUTH',
          detail: '접근 권한이 부족하여 릴리스 선언서를 조회할 수 없습니다.',
          retryable: false,
          traceId: '0123456789abcdef0123456789abcdef',
          causeRef: null,
          evidenceId: null,
        }),
      } as Response);

      await act(async () => {
        root.render(
          <IntranetDeploymentView
            autoFetch={true}
            currentUser={{ id: 'usr_viewer', name: 'Viewer', role: 'viewer' }}
          />
        );
      });

      const errEl = container.querySelector('[data-testid="deployment-manifest-error-403"]');
      expect(errEl).not.toBeNull();
      expect(errEl?.getAttribute('role')).toBe('alert');
      expect(errEl?.textContent).toContain('403 Forbidden: 접근 권한 없음');
      expect(errEl?.textContent).toContain('접근 권한이 부족하여');
    });

    it('handles 404 Not Found cleanly when release does not exist or belongs to another tenant', async () => {
      vi.spyOn(globalThis, 'fetch').mockResolvedValueOnce({
        ok: false,
        status: 404,
        headers: new Headers({ 'Content-Type': 'application/problem+json' }),
        json: async () => ({
          type: 'about:blank',
          title: 'Release Not Found',
          status: 404,
          code: 'RES-0404',
          category: 'RES',
          detail: '요청한 릴리스 선언서를 찾을 수 없습니다.',
          retryable: false,
          traceId: '0123456789abcdef0123456789abcdef',
          causeRef: null,
          evidenceId: null,
        }),
      } as Response);

      await act(async () => {
        root.render(
          <IntranetDeploymentView
            autoFetch={true}
            currentUser={{ id: 'usr_operator_lead', name: 'Lead', role: 'operator' }}
          />
        );
      });

      const errEl = container.querySelector('[data-testid="deployment-manifest-error-404"]');
      expect(errEl).not.toBeNull();
      expect(errEl?.getAttribute('role')).toBe('alert');
      expect(errEl?.textContent).toContain('404 Not Found: 릴리스 선언서 부재');
    });

    it('strictly maintains localSimulationCompleted separated from server operatorSignOff and prohibits write UI', async () => {
      await act(async () => {
        root.render(
          <IntranetDeploymentView
            autoFetch={false}
            initialManifests={[mockReleaseItem]}
            initialDetail={mockDetailUnsigned}
            currentUser={{ id: 'usr_operator_lead', name: 'Lead', role: 'operator' }}
          />
        );
      });

      // 1. Initial state: server operatorSignOff is false, local simulation is false
      const serverSignOffBefore = container.querySelector('[data-testid="server-operator-signoff"]');
      expect(serverSignOffBefore?.textContent).toContain('미서명 (operatorSignOff: false)');

      // 2. Perform local simulation sign-off
      const localSignOffBtn = container.querySelector('[data-testid="deployment-signoff-btn"]') as HTMLButtonElement;
      expect(localSignOffBtn).not.toBeNull();
      await act(async () => {
        localSignOffBtn.click();
      });

      // 3. Local simulation signoff is now complete
      expect(localSignOffBtn.textContent).toContain('모의 서명 완료됨');

      // 4. Server operatorSignOff remains FALSE because client simulation cannot forge backend server sign-off!
      const serverSignOffAfter = container.querySelector('[data-testid="server-operator-signoff"]');
      expect(serverSignOffAfter?.textContent).toContain('미서명 (operatorSignOff: false)');

      // 5. Verify prohibition of write UI (write boundary notice present, no write forms)
      const boundaryNotice = container.querySelector('[data-testid="server-write-boundary-notice"]');
      expect(boundaryNotice).not.toBeNull();
      expect(boundaryNotice?.textContent).toContain('수락 및 서명 쓰기 경계');
      expect(boundaryNotice?.textContent).toContain('임의 쓰기 서명 UI는 엄격히 금지됩니다');

      // Ensure server section has NO POST forms
      const serverSection = container.querySelector('[data-testid="deployment-server-manifest-section"]');
      expect(serverSection?.querySelectorAll('form')).toHaveLength(0);
    });

    // =========================================================================
    // 3. Revert-Fail Mutation Invariant
    // =========================================================================
    it('mutation invariant: fails if server release manifest binding is reverted to static fixture', () => {
      // If code were reverted to static fixture, serverManifestDetail would never render
      // dynamic server data like version '1.2.0-rc.1' or SHA '0123456789abcdef...'
      const testDetail: ReleaseManifestDetailResponse = {
        release: {
          releaseId: 'rel-dynamic-check',
          version: 'v9.9.9-mutation-test',
          componentCount: 7,
          manifestSha256: 'deadbeefdeadbeefdeadbeefdeadbeefdeadbeefdeadbeefdeadbeefdeadbeef',
          createdAt: '2026-10-01T12:00:00Z',
          operatorSignOff: true,
          acceptanceCount: 3,
        },
        acceptances: [],
      };

      act(() => {
        root.render(
          <IntranetDeploymentView
            autoFetch={false}
            initialManifests={[testDetail.release]}
            initialDetail={testDetail}
            currentUser={{ id: 'usr_operator_lead', name: 'Lead', role: 'operator' }}
          />
        );
      });

      // Must render the exact dynamic server properties, proving real binding
      const versionEl = container.querySelector('[data-testid="server-release-version"]');
      expect(versionEl?.textContent).toBe('v9.9.9-mutation-test');

      const idEl = container.querySelector('[data-testid="server-release-id"]');
      expect(idEl?.textContent).toBe('rel-dynamic-check');

      const shaEl = container.querySelector('[data-testid="server-manifest-sha"]');
      expect(shaEl?.textContent).toBe('deadbeefdeadbeefdeadbeefdeadbeefdeadbeefdeadbeefdeadbeefdeadbeef');

      const countEl = container.querySelector('[data-testid="server-component-count"]');
      expect(countEl?.textContent).toBe('7 개');

      const signoffEl = container.querySelector('[data-testid="server-operator-signoff"]');
      expect(signoffEl?.textContent).toContain('operatorSignOff=true');
    });
  });
});
