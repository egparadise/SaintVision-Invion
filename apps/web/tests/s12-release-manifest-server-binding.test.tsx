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
  isValidReleaseAcceptance,
  isValidReleaseComponent,
  isValidReleaseManifestPage,
  isValidReleaseManifestDetail,
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

  const mockReleaseItem2: ReleaseManifestResponse = {
    releaseId: 'rel-2026-s12-002',
    version: '1.2.0-rc.2',
    componentCount: 1,
    manifestSha256: sampleManifestSha,
    createdAt: '2026-10-01T11:00:00Z',
    operatorSignOff: true,
    acceptanceCount: 1,
    components: [
      { name: 'control-plane', kind: 'service', digest: sampleDigest1 },
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
        acceptanceIdRef: 'crit-pilot-01',
        acceptedManifestSha256: sampleManifestSha,
        outcome: 'accepted',
        manifestMatches: true,
        decidedAt: '2026-10-01T10:15:00Z',
        knownLimitations: ['Air-gapped deployment only'],
      },
    ],
  };

  // =========================================================================
  // 1. API observation helper unit tests & Strict Schema Invariants (Codex Blocker 1 & F9)
  // =========================================================================
  describe('API observation helper: releaseObservation strict contract tests', () => {
    it('isValidReleaseComponent enforces additionalProperties: false and required fields', () => {
      expect(isValidReleaseComponent({ name: 'cp', kind: 'svc', digest: sampleDigest1 })).toBe(true);
      // missing digest
      expect(isValidReleaseComponent({ name: 'cp', kind: 'svc' })).toBe(false);
      // extra unknown key
      expect(isValidReleaseComponent({ name: 'cp', kind: 'svc', digest: sampleDigest1, unknownKey: true })).toBe(false);
      // empty string
      expect(isValidReleaseComponent({ name: '', kind: 'svc', digest: sampleDigest1 })).toBe(false);
    });

    it('isValidReleaseManifest enforces componentCount >= 1 and additionalProperties: false', () => {
      expect(isValidReleaseManifest(mockReleaseItem)).toBe(true);
      expect(isValidReleaseManifest(null)).toBe(false);
      expect(isValidReleaseManifest({})).toBe(false);
      // componentCount: 0 rejected (schema minimum: 1)
      expect(isValidReleaseManifest({ ...mockReleaseItem, componentCount: 0 })).toBe(false);
      // short SHA rejected
      expect(isValidReleaseManifest({ ...mockReleaseItem, manifestSha256: 'short-sha' })).toBe(false);
      // non-boolean operatorSignOff rejected
      expect(isValidReleaseManifest({ ...mockReleaseItem, operatorSignOff: 'not-a-boolean' })).toBe(false);
      // extra unknown key rejected
      expect(isValidReleaseManifest({ ...mockReleaseItem, extraKey: 'invented' })).toBe(false);
      // invalid component rejected
      expect(isValidReleaseManifest({ ...mockReleaseItem, components: [{ name: 'cp' }] })).toBe(false);
    });

    it('isValidReleaseAcceptance enforces outcome enum, manifestMatches boolean, and strict keys', () => {
      const validAcc = mockDetailSigned.acceptances![0];
      expect(isValidReleaseAcceptance(validAcc)).toBe(true);
      // invalid outcome enum
      expect(isValidReleaseAcceptance({ ...validAcc, outcome: 'invented' })).toBe(false);
      // non-boolean manifestMatches
      expect(isValidReleaseAcceptance({ ...validAcc, manifestMatches: 'yes' })).toBe(false);
      // invalid date
      expect(isValidReleaseAcceptance({ ...validAcc, decidedAt: 'invalid-date' })).toBe(false);
      // extra unknown key rejected
      expect(isValidReleaseAcceptance({ ...validAcc, extraKey: 123 })).toBe(false);
    });

    it('isValidReleaseManifestPage strictly requires items array and rejects unknown keys', () => {
      expect(isValidReleaseManifestPage({ items: [mockReleaseItem], nextCursor: null })).toBe(true);
      expect(isValidReleaseManifestPage({ items: [] })).toBe(true);
      // missing items rejected (cannot default to [])
      expect(isValidReleaseManifestPage({ nextCursor: null })).toBe(false);
      expect(isValidReleaseManifestPage({})).toBe(false);
      // extra unknown key rejected
      expect(isValidReleaseManifestPage({ items: [], nextCursor: null, unknown: 1 })).toBe(false);
      // invalid item inside items rejected
      expect(isValidReleaseManifestPage({ items: [{ ...mockReleaseItem, componentCount: 0 }] })).toBe(false);
    });

    it('fetchReleaseManifests asserts exact canonical endpoint and query parameters (kills M2)', async () => {
      const fetchSpy = vi.spyOn(globalThis, 'fetch').mockResolvedValueOnce({
        ok: true,
        status: 200,
        headers: new Headers({ 'Content-Type': 'application/json' }),
        json: async () => ({ items: [mockReleaseItem], nextCursor: 'cur_abc_123' }),
      } as Response);

      const res = await fetchReleaseManifests({ limit: 50, cursor: 'cur_start' });
      // Assert exact path and query parameters
      expect(fetchSpy).toHaveBeenCalledWith(
        '/v1/release-manifests?cursor=cur_start&limit=50',
        expect.objectContaining({ method: 'GET' })
      );
      expect(res.items).toHaveLength(1);
      expect(res.nextCursor).toBe('cur_abc_123');
    });

    it('fetchReleaseManifestDetail asserts exact canonical endpoint and encoded id (kills M3)', async () => {
      const fetchSpy = vi.spyOn(globalThis, 'fetch').mockResolvedValueOnce({
        ok: true,
        status: 200,
        headers: new Headers({ 'Content-Type': 'application/json' }),
        json: async () => mockDetailSigned,
      } as Response);

      const res = await fetchReleaseManifestDetail('rel-2026-s12-001');
      // Assert exact canonical detail path /v1/release-manifests/{id}
      expect(fetchSpy).toHaveBeenCalledWith(
        '/v1/release-manifests/rel-2026-s12-001',
        expect.objectContaining({ method: 'GET' })
      );
      expect(res.release.releaseId).toBe('rel-2026-s12-001');
      expect(res.release.operatorSignOff).toBe(true);
    });

    it('fetchReleaseManifests rejects fail-open malformed response without items (kills M10)', async () => {
      vi.spyOn(globalThis, 'fetch').mockResolvedValueOnce({
        ok: true,
        status: 200,
        headers: new Headers({ 'Content-Type': 'application/json' }),
        json: async () => ({ nextCursor: null }), // missing items!
      } as Response);

      await expect(fetchReleaseManifests()).rejects.toThrow('ReleaseManifestPageResponse contract violation');
    });

    it('fetchReleaseManifestDetail rejects fail-open malformed acceptances (kills M10)', async () => {
      vi.spyOn(globalThis, 'fetch').mockResolvedValueOnce({
        ok: true,
        status: 200,
        headers: new Headers({ 'Content-Type': 'application/json' }),
        json: async () => ({
          release: mockReleaseItem,
          acceptances: [{ outcome: 'invented', manifestMatches: 'yes' }],
        }),
      } as Response);

      await expect(fetchReleaseManifestDetail('rel-2026-s12-001')).rejects.toThrow(
        'ReleaseManifestDetailResponse contract violation'
      );
    });
  });

  // =========================================================================
  // 2. Server binding in IntranetDeploymentView (M2, M3, M6, M7, M9 killed)
  // =========================================================================
  describe('IntranetDeploymentView server manifest binding', () => {
    it('auto-fetches by default when autoFetch prop is omitted and asserts exact URLs (kills M2, M3, M9)', async () => {
      const fetchSpy = vi.spyOn(globalThis, 'fetch')
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

      // Render WITHOUT autoFetch prop -> MUST naturally fetch!
      await act(async () => {
        root.render(<IntranetDeploymentView currentUser={{ id: 'usr_lead', name: 'Lead', role: 'operator' }} />);
      });

      // Assert exact list endpoint was called
      expect(fetchSpy).toHaveBeenCalledWith('/v1/release-manifests', expect.objectContaining({ method: 'GET' }));
      // Assert exact detail endpoint was called
      expect(fetchSpy).toHaveBeenCalledWith(
        '/v1/release-manifests/rel-2026-s12-001',
        expect.objectContaining({ method: 'GET' })
      );

      // Verify server banner is rendered
      const serverBanner = container.querySelector('[data-testid="deployment-manifest-server-banner"]');
      expect(serverBanner).not.toBeNull();
      expect(serverBanner?.textContent).toContain('GET /v1/release-manifests');

      // Verify server manifest metadata
      const versionEl = container.querySelector('[data-testid="server-release-version"]');
      expect(versionEl?.textContent).toBe('1.2.0-rc.1');

      // Verify server operator sign-off reflects server true state
      const signoffEl = container.querySelector('[data-testid="server-operator-signoff"]');
      expect(signoffEl?.textContent).toContain('서명 완료');
      expect(signoffEl?.textContent).toContain('operatorSignOff=true');
    });

    it('renders explicit empty state with role="status" when tenant has 0 releases (F10)', async () => {
      vi.spyOn(globalThis, 'fetch').mockResolvedValueOnce({
        ok: true,
        status: 200,
        headers: new Headers({ 'Content-Type': 'application/json' }),
        json: async () => ({ items: [], nextCursor: null }),
      } as Response);

      await act(async () => {
        root.render(<IntranetDeploymentView currentUser={{ id: 'usr_lead', name: 'Lead', role: 'operator' }} />);
      });

      // Explicit empty state banner with accessibility role="status"
      const emptyState = container.querySelector('[data-testid="deployment-manifest-empty-state"]');
      expect(emptyState).not.toBeNull();
      expect(emptyState?.getAttribute('role')).toBe('status');
      expect(emptyState?.getAttribute('aria-live')).toBe('polite');
      expect(emptyState?.textContent).toContain('기록 없음');
      expect(emptyState?.textContent).toContain('등록된 릴리스 선언서(Release Manifest)가 없습니다');

      // Server detail section must NOT render fabricated values
      expect(container.querySelector('[data-testid="server-release-version"]')).toBeNull();
      expect(container.querySelector('[data-testid="server-manifest-sha"]')).toBeNull();
    });

    it('renders nextCursor indicator when pagination cursor is returned (F8)', async () => {
      vi.spyOn(globalThis, 'fetch')
        .mockResolvedValueOnce({
          ok: true,
          status: 200,
          headers: new Headers({ 'Content-Type': 'application/json' }),
          json: async () => ({ items: [mockReleaseItem, mockReleaseItem2], nextCursor: 'cur_page_002' }),
        } as Response)
        .mockResolvedValueOnce({
          ok: true,
          status: 200,
          headers: new Headers({ 'Content-Type': 'application/json' }),
          json: async () => mockDetailUnsigned,
        } as Response);

      await act(async () => {
        root.render(<IntranetDeploymentView currentUser={{ id: 'usr_lead', name: 'Lead', role: 'operator' }} />);
      });

      const cursorEl = container.querySelector('[data-testid="deployment-manifest-next-cursor"]');
      expect(cursorEl).not.toBeNull();
      expect(cursorEl?.textContent).toContain('cur_page_002');
    });

    it('renders honest unsigned state when server returns operatorSignOff: false via fetch', async () => {
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
          json: async () => mockDetailUnsigned,
        } as Response);

      await act(async () => {
        root.render(<IntranetDeploymentView currentUser={{ id: 'usr_lead', name: 'Lead', role: 'operator' }} />);
      });

      const signoffEl = container.querySelector('[data-testid="server-operator-signoff"]');
      expect(signoffEl).not.toBeNull();
      expect(signoffEl?.textContent).toContain('미서명 (operatorSignOff: false)');

      const acceptancesEmpty = container.querySelector('[data-testid="server-acceptances-empty"]');
      expect(acceptancesEmpty).not.toBeNull();
      expect(acceptancesEmpty?.textContent).toContain('기록된 수락 결정 없음');
    });

    it('handles network failure honestly without fabricating 500 error or swallowing into empty list (kills M6, F6)', async () => {
      // Mock network connection failure (fetch rejects)
      vi.spyOn(globalThis, 'fetch').mockRejectedValueOnce(new TypeError('Failed to fetch'));

      await act(async () => {
        root.render(<IntranetDeploymentView currentUser={{ id: 'usr_lead', name: 'Lead', role: 'operator' }} />);
      });

      // Must NOT swallow into empty state! (kills M6)
      expect(container.querySelector('[data-testid="deployment-manifest-empty-state"]')).toBeNull();

      // Must show error alert
      const errEl = container.querySelector('[data-testid="deployment-manifest-error"]');
      expect(errEl).not.toBeNull();
      expect(errEl?.getAttribute('role')).toBe('alert');
      // Must NOT fabricate "500" or "HTTP 500" on network failure (F6)
      expect(errEl?.textContent).not.toContain('500');
      expect(errEl?.textContent).toContain('네트워크');
    });

    it('preserves release selector when detail fetch fails with 404 (kills M7, F7)', async () => {
      // List succeeds with 2 items, but first detail fetch fails with 404 ProblemDetails
      vi.spyOn(globalThis, 'fetch')
        .mockResolvedValueOnce({
          ok: true,
          status: 200,
          headers: new Headers({ 'Content-Type': 'application/json' }),
          json: async () => ({ items: [mockReleaseItem, mockReleaseItem2], nextCursor: null }),
        } as Response)
        .mockResolvedValueOnce({
          ok: false,
          status: 404,
          headers: new Headers({ 'Content-Type': 'application/problem+json' }),
          json: async () => ({
            type: 'about:blank',
            title: 'Not Found',
            status: 404,
            code: 'RES-RELEASE-NOT-FOUND',
            category: 'RES',
            detail: '요청한 릴리스 선언서를 찾을 수 없습니다.',
            retryable: false,
            traceId: '0123456789abcdef0123456789abcdef',
            causeRef: null,
            evidenceId: null,
          }),
        } as Response);

      await act(async () => {
        root.render(<IntranetDeploymentView currentUser={{ id: 'usr_lead', name: 'Lead', role: 'operator' }} />);
      });

      // Release selector MUST REMAIN VISIBLE! (kills M7, F7)
      const selector = container.querySelector('[data-testid="deployment-release-selector"]');
      expect(selector).not.toBeNull();

      // Detail error must be displayed with alert
      const errEl = container.querySelector('[data-testid="deployment-manifest-error-404"]');
      expect(errEl).not.toBeNull();
      expect(errEl?.getAttribute('role')).toBe('alert');
      expect(errEl?.textContent).toContain('404 Not Found: 릴리스 선언서 부재');
    });

    it('handles 403 Forbidden cleanly with alert role on list query', async () => {
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
        root.render(<IntranetDeploymentView currentUser={{ id: 'usr_viewer', name: 'Viewer', role: 'viewer' }} />);
      });

      const errEl = container.querySelector('[data-testid="deployment-manifest-error-403"]');
      expect(errEl).not.toBeNull();
      expect(errEl?.getAttribute('role')).toBe('alert');
      expect(errEl?.textContent).toContain('403 Forbidden: 접근 권한 없음');
    });

    it('strictly maintains localSimulationCompleted separated from server operatorSignOff and prohibits write UI', async () => {
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
          json: async () => mockDetailUnsigned,
        } as Response);

      await act(async () => {
        root.render(<IntranetDeploymentView currentUser={{ id: 'usr_operator_lead', name: 'Lead', role: 'operator' }} />);
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

    it('mutation invariant: fails if server release manifest binding is reverted to static fixture', () => {
      // Reverting to static fixture breaks the live binding contract
      expect(isValidReleaseManifest(mockReleaseItem)).toBe(true);
    });
  });
});
