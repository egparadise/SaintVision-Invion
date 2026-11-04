// @vitest-environment happy-dom
// @ts-ignore
globalThis.IS_REACT_ACT_ENVIRONMENT = true;
import React, { act } from 'react';
import { createRoot, Root } from 'react-dom/client';
import { describe, it, expect, vi, beforeEach, afterEach } from 'vitest';
import { App } from '../src/app/App';
import * as sessionModule from '../src/features/auth/session';
import * as clientModule from '../src/shared/api/client';
import * as projectObsModule from '../src/shared/api/projectObservation';
import * as runApprovalObsModule from '../src/shared/api/runApprovalObservation';
import * as fabricApi from '../src/features/desktop/fabricControlApi';
import * as storageObsApi from '../src/shared/api/storageObservation';

describe('App Level OIDC Integration (Card 153 M1/M2/L5 Verification)', () => {
  let container: HTMLDivElement;
  let root: Root;
  let locationAssignSpy: ReturnType<typeof vi.fn>;

  beforeEach(() => {
    container = document.createElement('div');
    document.body.appendChild(container);
    root = createRoot(container);
    vi.restoreAllMocks();

    locationAssignSpy = vi.fn();
    delete (window as any).location;
    window.location = {
      origin: 'https://portal.saintvision.lan',
      pathname: '/studio',
      search: '',
      assign: locationAssignSpy,
      href: 'https://portal.saintvision.lan/studio',
    } as any;

    (window as any).__SAINTVISION_CONFIG__ = {
      issuer: 'https://idp.sv.lan/realms/saintvision',
      clientId: 'sv-portal',
    };

    vi.stubGlobal('fetch', vi.fn().mockResolvedValue({ ok: true, status: 200, json: async () => ({}) }));
    vi.spyOn(fabricApi, 'getDiscoveryCandidates').mockResolvedValue([]);
    vi.spyOn(fabricApi, 'getStorageContributions').mockResolvedValue([]);
    vi.spyOn(fabricApi, 'getNodeResourceUsage').mockResolvedValue(null);
    vi.spyOn(storageObsApi, 'fetchStorageObservation').mockResolvedValue({
      source: 'storage-kernel',
      observedAt: '2026-09-30T00:00:00Z',
      clusterId: 'cluster-dev-01',
      observation: {
        currentHealth: 'healthy',
        operationalAcceptanceAssessed: true,
        replicaCount: 1,
        activeReplicas: 1,
        syncLagMs: 0,
        unhealthyReplicas: [],
        degradedReasons: [],
      },
    });

    vi.spyOn(clientModule, 'apiClient').mockImplementation(async (path: string) => {
      if (path === '/v1/projects') {
        return [{ id: 'prj_test', name: 'Test Project', tenantId: 'ten_test', createdAt: '2026-09-30T00:00:00Z' }];
      }
      if (path.includes('/nodes')) {
        return { items: [], total: 0 };
      }
      return {};
    });

    vi.spyOn(projectObsModule, 'fetchProjects').mockResolvedValue([
      { id: 'prj_test', name: 'Test Project', tenantId: 'ten_test', createdAt: '2026-09-30T00:00:00Z' },
    ]);
    vi.spyOn(projectObsModule, 'fetchProjectWorkspaces').mockResolvedValue([]);
    vi.spyOn(runApprovalObsModule, 'fetchObservedRuns').mockResolvedValue([]);
    vi.spyOn(runApprovalObsModule, 'fetchObservedApprovals').mockResolvedValue([]);
  });

  afterEach(() => {
    act(() => {
      root.unmount();
    });
    container.remove();
    vi.unstubAllGlobals();
    vi.restoreAllMocks();
  });

  it('wires Header logout button to performLogout with redirectIdp: true and executes location.assign', async () => {
    // 1. Initial login via callback
    vi.spyOn(sessionModule, 'hasLoginCallback').mockReturnValue(true);
    vi.spyOn(sessionModule, 'completeLogin').mockResolvedValue({
      token: 'jwt-authenticated-token',
      user: { id: 'usr_oidc_user', name: 'Portal User', role: 'developer', tenantId: 'ten_portal' },
      expiresAt: Math.floor(Date.now() / 1000) + 1800,
    });

    const performLogoutSpy = vi.spyOn(sessionModule, 'performLogout');

    // Mount App
    await act(async () => {
      root.render(<App />);
    });
    await act(async () => {
      await new Promise((r) => setTimeout(r, 50));
    });

    // Verify user is logged in and header shows username
    expect(container.textContent).toContain('Portal User');

    // Find and click the Header logout button
    const buttons = Array.from(container.querySelectorAll('button'));
    const logoutBtn = buttons.find((b) => b.textContent?.includes('로그아웃'));
    expect(logoutBtn).toBeDefined();

    await act(async () => {
      logoutBtn?.click();
    });

    // Verify performLogout was called with redirectIdp: true and postLogoutRedirectUri
    expect(performLogoutSpy).toHaveBeenCalledWith({
      redirectIdp: true,
      postLogoutRedirectUri: 'https://portal.saintvision.lan',
    });

    // Verify location.assign was invoked with Keycloak end_session URL
    expect(locationAssignSpy).toHaveBeenCalledWith(
      'https://idp.sv.lan/realms/saintvision/protocol/openid-connect/logout?client_id=sv-portal&post_logout_redirect_uri=https%3A%2F%2Fportal.saintvision.lan'
    );
  });

  it('transitions to Login screen and renders [AUTH-0050] alert when onTokenExpired triggers', async () => {
    let expirationListener: ((reason: string) => void) | null = null;
    vi.spyOn(sessionModule, 'onTokenExpired').mockImplementation((cb) => {
      expirationListener = cb;
      return () => {
        expirationListener = null;
      };
    });

    // 1. Initial login
    const hasCb = vi.spyOn(sessionModule, 'hasLoginCallback').mockReturnValue(true);
    vi.spyOn(sessionModule, 'completeLogin').mockResolvedValue({
      token: 'jwt-authenticated-token',
      user: { id: 'usr_oidc_user', name: 'Portal User', role: 'developer', tenantId: 'ten_portal' },
      expiresAt: Math.floor(Date.now() / 1000) + 1800,
    });

    // Mount App
    await act(async () => {
      root.render(<App />);
    });
    await act(async () => {
      await new Promise((r) => setTimeout(r, 50));
    });
    hasCb.mockReturnValue(false);

    expect(container.textContent).toContain('Portal User');
    expect(expirationListener).not.toBeNull();

    // 2. Trigger token expiration event
    await act(async () => {
      expirationListener!('[AUTH-0050] 인증 세션이 만료되었습니다. 다시 로그인하세요.');
    });

    // Verify transition to Login screen with role="alert" banner
    const alertEl = container.querySelector('[role="alert"][data-testid="login-error-alert"]');
    expect(alertEl).not.toBeNull();
    expect(alertEl?.textContent).toContain('[AUTH-0050] 인증 세션이 만료되었습니다. 다시 로그인하세요.');

    // Verify "조직 계정으로 로그인" button is present for re-login
    const loginBtn = Array.from(container.querySelectorAll('button')).find((b) =>
      b.textContent?.includes('조직 계정으로 로그인')
    );
    expect(loginBtn).toBeDefined();
  });

  it('handles authentication failure (HTTP 401 onUnauthorized) after previous successful login by clearing authenticated state and transitioning to Login with alert banner', async () => {
    let unauthorizedListener: ((problem: any) => void) | null = null;
    vi.spyOn(clientModule, 'onUnauthorized').mockImplementation((cb: any) => {
      unauthorizedListener = cb;
    });

    const clearTokenSpy = vi.spyOn(clientModule, 'clearAuthToken');
    const clearExpSpy = vi.spyOn(sessionModule, 'clearSessionExpiration');

    // 1. Initial successful login via OIDC callback
    const hasCb = vi.spyOn(sessionModule, 'hasLoginCallback').mockReturnValue(true);
    vi.spyOn(sessionModule, 'completeLogin').mockResolvedValue({
      token: 'jwt-authenticated-token',
      user: { id: 'usr_oidc_user', name: 'Portal User', role: 'developer', tenantId: 'ten_portal' },
      expiresAt: Math.floor(Date.now() / 1000) + 1800,
    });

    // Mount App
    await act(async () => {
      root.render(<App />);
    });
    await act(async () => {
      await new Promise((r) => setTimeout(r, 50));
    });
    hasCb.mockReturnValue(false);

    // Verify user is logged in
    expect(container.textContent).toContain('Portal User');
    expect(unauthorizedListener).not.toBeNull();

    // 2. Trigger HTTP 401 Unauthorized ProblemDetails (e.g. token revoked/expired on backend)
    await act(async () => {
      unauthorizedListener!({
        status: 401,
        code: 'AUTH-MISSING-CREDENTIAL',
        title: 'Unauthorized',
        detail: '세션 자격증명이 만료되었거나 무효화되었습니다. 다시 로그인하세요.',
        instance: '/v1/projects',
        traceId: 'trc_401_revoked',
        isServerFault: false,
      });
    });

    // 3. Verify security teardown: tokens cleared, user logged out, Login screen with alert
    expect(clearTokenSpy).toHaveBeenCalled();
    expect(clearExpSpy).toHaveBeenCalled();
    expect(container.textContent).not.toContain('Portal User');

    const alertEl = container.querySelector('[role="alert"][data-testid="login-error-alert"]');
    expect(alertEl).not.toBeNull();
    expect(alertEl?.textContent).toContain('[AUTH-MISSING-CREDENTIAL] 세션 자격증명이 만료되었거나 무효화되었습니다. 다시 로그인하세요.');

    // 4. Verify re-login button is available and functional
    const loginBtn = Array.from(container.querySelectorAll('button')).find((b) =>
      b.textContent?.includes('조직 계정으로 로그인')
    );
    expect(loginBtn).toBeDefined();
  });

  it('handles authentication failure (HTTP 401) while operating inside Desktop Shell, safely resetting desktop mode', async () => {
    let unauthorizedListener: ((problem: any) => void) | null = null;
    vi.spyOn(clientModule, 'onUnauthorized').mockImplementation((cb: any) => {
      unauthorizedListener = cb;
    });

    // 1. Initial successful login
    const hasCb = vi.spyOn(sessionModule, 'hasLoginCallback').mockReturnValue(true);
    vi.spyOn(sessionModule, 'completeLogin').mockResolvedValue({
      token: 'jwt-authenticated-token',
      user: { id: 'usr_oidc_user', name: 'Portal User', role: 'developer', tenantId: 'ten_portal' },
      expiresAt: Math.floor(Date.now() / 1000) + 1800,
    });

    await act(async () => {
      root.render(<App />);
    });
    await act(async () => {
      await new Promise((r) => setTimeout(r, 50));
    });
    hasCb.mockReturnValue(false);

    expect(container.textContent).toContain('Portal User');

    // Switch to desktop view if available
    const desktopBtn = Array.from(container.querySelectorAll('button')).find((b) =>
      b.textContent?.includes('데스크톱') || b.textContent?.includes('가상 데스크톱')
    );
    if (desktopBtn) {
      await act(async () => {
        desktopBtn.click();
      });
    }

    // 2. Trigger 401 Unauthorized
    await act(async () => {
      unauthorizedListener!({
        status: 401,
        code: 'AUTH-0050',
        title: 'Session Revoked',
        detail: '세션이 취소되었습니다.',
        instance: '/v1/nodes',
        traceId: 'trc_desktop_401',
        isServerFault: false,
      });
    });

    // 3. Desktop view must be closed, returning to Login screen
    const alertEl = container.querySelector('[role="alert"][data-testid="login-error-alert"]');
    expect(alertEl).not.toBeNull();
    expect(alertEl?.textContent).toContain('[AUTH-0050] 세션이 취소되었습니다.');
  });

  it('wires clusterTrust from backend /node-certificates endpoint through App into DesktopShell and ResourceExplorer truthfully', async () => {
    // 1. Mock API with canonical /node-certificates endpoint
    vi.spyOn(clientModule, 'apiClient').mockImplementation(async (path: string) => {
      if (path === '/v1/projects') {
        return [{ id: 'prj_test', name: 'Test Project', tenantId: 'ten_portal', createdAt: '2026-09-30T00:00:00Z' }];
      }
      if (path.includes('/node-certificates')) {
        return {
          source: 'execution-kernel',
          scope: 'project-node-certificates',
          observedAt: '2026-11-04T04:00:00Z',
          complete: true,
          items: [
            {
              nodeId: 'nod_pilot_01',
              certificateNotAfter: '2026-11-02T03:32:25Z',
              channelEnabled: true,
            },
          ],
          trust: {
            state: 'renewal-window',
            earliestCertificateNotAfter: '2026-11-02T03:32:25Z',
            renewalWindowStartsAt: '2026-10-31T03:32:25Z',
            secondsUntilEarliestExpiry: 172800,
          },
        };
      }
      if (path.includes('/nodes')) {
        return {
          items: [
            {
              nodeId: 'nod_pilot_01',
              hostname: 'pilot-01',
              status: 'online',
            },
          ],
          total: 1,
        };
      }
      return {};
    });

    vi.spyOn(sessionModule, 'hasLoginCallback').mockReturnValue(true);
    vi.spyOn(sessionModule, 'completeLogin').mockResolvedValue({
      token: 'jwt-authenticated-token',
      user: { id: 'usr_oidc_user', name: 'Portal User', role: 'developer', tenantId: 'ten_portal' },
      expiresAt: Math.floor(Date.now() / 1000) + 1800,
    });

    await act(async () => {
      root.render(<App />);
    });
    await act(async () => {
      await new Promise((r) => setTimeout(r, 80));
    });

    // Switch to desktop view
    const desktopBtn = Array.from(container.querySelectorAll('button')).find((b) =>
      b.textContent?.includes('Web Desktop') || b.getAttribute('aria-label')?.includes('Web Desktop')
    );
    expect(desktopBtn).toBeDefined();
    await act(async () => {
      desktopBtn?.click();
    });

    // Verify DesktopShell received trust and rendered ResourceExplorer with renewal window banner & badge
    const badge = container.querySelector('[data-testid="trust-status-badge"]');
    expect(badge).not.toBeNull();
    expect(badge?.textContent).toContain('인증서 갱신 창');

    const banner = container.querySelector('[data-testid="trust-expiry-banner"]');
    expect(banner).not.toBeNull();
    expect(banner?.textContent).toContain('인증서 갱신 창 (스케줄러 미등록) — 만료까지 2일 0시간');
  });

  it('keeps unknown trust visible when /node-certificates endpoint is unobserved or fails', async () => {
    // 1. Mock API where node-certificates returns 404 route not found
    vi.spyOn(clientModule, 'apiClient').mockImplementation(async (path: string) => {
      if (path === '/v1/projects') {
        return [{ id: 'prj_test', name: 'Test Project', tenantId: 'ten_portal', createdAt: '2026-09-30T00:00:00Z' }];
      }
      if (path.includes('/node-certificates')) {
        const notFoundErr: any = new Error('Route not found');
        notFoundErr.status = 404;
        throw notFoundErr;
      }
      if (path.includes('/nodes')) {
        return {
          items: [
            {
              nodeId: 'nod_pilot_01',
              hostname: 'pilot-01',
              status: 'online',
            },
          ],
          total: 1,
        };
      }
      return {};
    });

    vi.spyOn(sessionModule, 'hasLoginCallback').mockReturnValue(true);
    vi.spyOn(sessionModule, 'completeLogin').mockResolvedValue({
      token: 'jwt-authenticated-token',
      user: { id: 'usr_oidc_user', name: 'Portal User', role: 'developer', tenantId: 'ten_portal' },
      expiresAt: Math.floor(Date.now() / 1000) + 1800,
    });

    await act(async () => {
      root.render(<App />);
    });
    await act(async () => {
      await new Promise((r) => setTimeout(r, 80));
    });

    // Switch to desktop view
    const desktopBtn = Array.from(container.querySelectorAll('button')).find((b) =>
      b.textContent?.includes('Web Desktop') || b.getAttribute('aria-label')?.includes('Web Desktop')
    );
    await act(async () => {
      desktopBtn?.click();
    });

    // Trust badge must be visibly rendered with '● 신뢰 미확인' (never silently hidden or faked healthy)
    const badge = container.querySelector('[data-testid="trust-status-badge"]');
    expect(badge).not.toBeNull();
    expect(badge?.textContent).toBe('● 신뢰 미확인');

    // No renewal banner should be rendered
    const banner = container.querySelector('[data-testid="trust-expiry-banner"]');
    expect(banner).toBeNull();
  });
});
