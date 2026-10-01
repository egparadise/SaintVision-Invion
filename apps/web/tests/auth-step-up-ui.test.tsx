// @vitest-environment happy-dom
// @ts-ignore
globalThis.IS_REACT_ACT_ENVIRONMENT = true;
import React, { act } from 'react';
import { createRoot, Root } from 'react-dom/client';
import { describe, it, expect, vi, beforeEach, afterEach } from 'vitest';
import { IntranetDeploymentView } from '../src/features/deployment/IntranetDeploymentView';
import * as authSession from '../src/features/auth/session';
import { ReleaseManifestResponse, ReleaseManifestDetailResponse } from '../src/shared/api/releaseObservation';

describe('Card 192 / S12-FE: Portal Step-Up Re-Authentication UI Entry Point', () => {
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

  const mockReleaseItem: ReleaseManifestResponse = {
    releaseId: 'rel-2026-s12-001',
    version: '1.2.0-rc.1',
    componentCount: 2,
    manifestSha256: sampleManifestSha,
    createdAt: '2026-10-01T10:00:00Z',
    operatorSignOff: false,
    operatorSignOffBlockedBy: 'human-attestation-implementation-unavailable',
    requiredDistinctOperatorCount: 2,
    confirmedOperatorCount: 0,
    matchingAcceptedUserCount: 1,
    acceptanceCount: 1,
  };

  const mockDetail: ReleaseManifestDetailResponse = {
    release: mockReleaseItem,
    components: [
      {
        name: 'kernel-mesh',
        version: '1.2.0',
        digest: 'sha256:1111222233334444555566667777888899990000aaaabbbbccccddddeeeeffff',
        status: 'ready',
      },
    ],
    acceptances: [
      {
        acceptanceId: 'acc-2026-0001',
        releaseId: 'rel-2026-s12-001',
        userId: 'usr_operator_1',
        role: 'operator',
        decision: 'accepted',
        manifestSha256: sampleManifestSha,
        observedAt: '2026-10-01T10:05:00Z',
      },
    ],
  };

  it('renders step-up section with status badge, informative notice, and step-up login button', async () => {
    await act(async () => {
      root.render(
        <IntranetDeploymentView
          currentUser={{ id: 'usr_operator_lead', name: 'Lead', role: 'operator' }}
          initialManifests={[mockReleaseItem]}
          initialDetail={mockDetail}
          autoFetch={false}
        />
      );
    });

    const stepUpSection = container.querySelector('[data-testid="deployment-step-up-section"]');
    expect(stepUpSection).not.toBeNull();

    const badge = container.querySelector('[data-testid="deployment-step-up-status-badge"]');
    expect(badge).not.toBeNull();
    expect(badge?.textContent).toContain('재인증 필요 (Step-Up Required)');

    // Informational honest notices
    expect(stepUpSection?.textContent).toContain('INV_RELEASE_ACCEPTANCE_WRITE_ENABLED=false');
    expect(stepUpSection?.textContent).toContain('BLOCKED_EXTERNAL');
    expect(stepUpSection?.textContent).toContain('idp.sv.lan');
    expect(stepUpSection?.textContent).toContain('prompt=login, max_age=300');

    // Step-up action button
    const stepUpBtn = container.querySelector('[data-testid="deployment-step-up-button"]');
    expect(stepUpBtn).not.toBeNull();
    expect(stepUpBtn?.textContent).toContain('재인증 필요 (Step-Up 로그인)');
  });

  it('clicking step-up button invokes beginStepUp and redirects to authorize URL', async () => {
    const assignMock = vi.fn();
    delete (window as any).location;
    (window as any).location = {
      pathname: '/intranet/deployment',
      assign: assignMock,
      origin: 'http://localhost:3000',
    };

    const beginStepUpSpy = vi.spyOn(authSession, 'beginStepUp').mockResolvedValueOnce(
      'https://idp.sv.lan/oauth2/authorize?response_type=code&client_id=portal-web&prompt=login&max_age=300'
    );

    await act(async () => {
      root.render(
        <IntranetDeploymentView
          currentUser={{ id: 'usr_operator_lead', name: 'Lead', role: 'operator' }}
          initialManifests={[mockReleaseItem]}
          initialDetail={mockDetail}
          autoFetch={false}
        />
      );
    });

    const stepUpBtn = container.querySelector('[data-testid="deployment-step-up-button"]') as HTMLButtonElement;
    expect(stepUpBtn).not.toBeNull();

    await act(async () => {
      stepUpBtn.click();
    });

    expect(beginStepUpSpy).toHaveBeenCalledWith({
      returnUrl: '/intranet/deployment',
    });
    expect(assignMock).toHaveBeenCalledWith(
      'https://idp.sv.lan/oauth2/authorize?response_type=code&client_id=portal-web&prompt=login&max_age=300'
    );
  });

  it('button click executes unmocked beginStepUp and redirects to authorize URL with exact prompt and max_age', async () => {
    const storage = new Map<string, string>();
    vi.stubGlobal('sessionStorage', {
      getItem: (k: string) => storage.get(k) ?? null,
      setItem: (k: string, v: string) => storage.set(k, v),
      removeItem: (k: string) => storage.delete(k),
    });

    const assignMock = vi.fn();
    delete (window as any).location;
    (window as any).location = {
      pathname: '/intranet/deployment',
      assign: assignMock,
      origin: 'https://portal.saintvision.lan',
    };
    (window as any).__SAINTVISION_CONFIG__ = {
      issuer: 'https://idp.saintvision.lan:8443/realms/saintvision',
      idpAuthorizeUrl: 'https://idp.saintvision.lan:8443/realms/saintvision/protocol/openid-connect/auth',
      idpTokenUrl: 'https://idp.saintvision.lan:8443/realms/saintvision/protocol/openid-connect/token',
      clientId: 'saintvision-web',
      scope: 'openid inv.api',
      redirectUri: 'https://portal.saintvision.lan/callback',
    };

    await act(async () => {
      root.render(
        <IntranetDeploymentView
          currentUser={{ id: 'usr_operator_lead', name: 'Lead', role: 'operator' }}
          initialManifests={[mockReleaseItem]}
          initialDetail={mockDetail}
          autoFetch={false}
        />
      );
    });

    const stepUpBtn = container.querySelector('[data-testid="deployment-step-up-button"]') as HTMLButtonElement;
    expect(stepUpBtn).not.toBeNull();

    await act(async () => {
      stepUpBtn.click();
    });

    expect(assignMock).toHaveBeenCalledTimes(1);
    const assignedUrl = new URL(assignMock.mock.calls[0][0]);
    expect(assignedUrl.origin + assignedUrl.pathname).toBe('https://idp.saintvision.lan:8443/realms/saintvision/protocol/openid-connect/auth');
    expect(assignedUrl.searchParams.get('prompt')).toBe('login');
    expect(assignedUrl.searchParams.get('max_age')).toBe('300');
    expect(assignedUrl.searchParams.get('client_id')).toBe('saintvision-web');
    expect(assignedUrl.searchParams.get('response_type')).toBe('code');
  });

  it('displays error notice if beginStepUp fails', async () => {
    vi.spyOn(authSession, 'beginStepUp').mockRejectedValueOnce(
      new Error('OIDC Discovery failed')
    );

    await act(async () => {
      root.render(
        <IntranetDeploymentView
          currentUser={{ id: 'usr_operator_lead', name: 'Lead', role: 'operator' }}
          initialManifests={[mockReleaseItem]}
          initialDetail={mockDetail}
          autoFetch={false}
        />
      );
    });

    const stepUpBtn = container.querySelector('[data-testid="deployment-step-up-button"]') as HTMLButtonElement;
    expect(stepUpBtn).not.toBeNull();

    await act(async () => {
      stepUpBtn.click();
    });

    expect(container.textContent).toContain('🛑 재인증 요청 실패: OIDC Discovery failed');
  });

  it('strictly prohibits write UI: zero acceptance submit forms or mutation endpoints', async () => {
    await act(async () => {
      root.render(
        <IntranetDeploymentView
          currentUser={{ id: 'usr_operator_lead', name: 'Lead', role: 'operator' }}
          initialManifests={[mockReleaseItem]}
          initialDetail={mockDetail}
          autoFetch={false}
        />
      );
    });

    const stepUpSection = container.querySelector('[data-testid="deployment-step-up-section"]');
    expect(stepUpSection).not.toBeNull();
    // No input forms or accept submission buttons
    expect(stepUpSection?.querySelectorAll('form')).toHaveLength(0);
    expect(stepUpSection?.querySelectorAll('input')).toHaveLength(0);
  });
});
