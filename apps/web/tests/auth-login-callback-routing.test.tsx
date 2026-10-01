// @vitest-environment happy-dom
// @ts-ignore
globalThis.IS_REACT_ACT_ENVIRONMENT = true;
import React, { act } from 'react';
import { createRoot, Root } from 'react-dom/client';
import { describe, it, expect, vi, beforeEach, afterEach } from 'vitest';
import { Login } from '../src/features/auth/Login';
import * as sessionModule from '../src/features/auth/session';
import { getAuthToken, setAuthToken, clearAuthToken } from '../src/shared/api/client';

describe('Card 192 / U3: Login Component Callback Routing and Failure Handling Invariants', () => {
  let container: HTMLDivElement;
  let root: Root;
  const originalLocation = window.location;
  const originalConfig = (window as any).__SAINTVISION_CONFIG__;

  beforeEach(() => {
    container = document.createElement('div');
    document.body.appendChild(container);
    root = createRoot(container);
    clearAuthToken();
    vi.restoreAllMocks();

    delete (window as any).location;
    (window as any).location = {
      origin: 'https://portal.saintvision.lan',
      pathname: '/callback',
      search: '?code=mock_code&state=mock_state',
      assign: vi.fn(),
    };
    (window as any).__SAINTVISION_CONFIG__ = {
      clientId: 'sv-web',
      issuer: 'https://idp.saintvision.lan:8443/realms/saintvision',
    };
  });

  afterEach(() => {
    act(() => {
      root.unmount();
    });
    container.remove();
    clearAuthToken();
    vi.unstubAllGlobals();
    vi.restoreAllMocks();
    (window as any).location = originalLocation;
    (window as any).__SAINTVISION_CONFIG__ = originalConfig;
  });

  const mockUser: sessionModule.SessionUser = {
    id: 'usr_operator_lead',
    name: 'Operator Lead',
    role: 'operator',
    tenantId: 'ten_main',
  };

  it('L1 Mutation Guard 1: When isStepUpPending() is true, Login delegates strictly to completeStepUp() and commits session on success', async () => {
    vi.spyOn(sessionModule, 'hasLoginCallback').mockReturnValue(true);
    vi.spyOn(sessionModule, 'isStepUpPending').mockReturnValue(true);

    const completeStepUpSpy = vi.spyOn(sessionModule, 'completeStepUp').mockResolvedValue({
      token: 'fresh-step-up-jwt-token',
      user: mockUser,
      expiresAt: Math.floor(Date.now() / 1000) + 300,
      isStepUp: true,
    });
    const completeLoginSpy = vi.spyOn(sessionModule, 'completeLogin');
    const onLoginSuccessSpy = vi.fn();

    await act(async () => {
      root.render(<Login onLoginSuccess={onLoginSuccessSpy} />);
    });
    await act(async () => {
      await new Promise((r) => setTimeout(r, 50));
    });

    // 1. Must invoke completeStepUp, NEVER completeLogin
    expect(completeStepUpSpy, 'Must call completeStepUp when step-up is pending').toHaveBeenCalledTimes(1);
    expect(completeLoginSpy, 'Must NOT call completeLogin when step-up is pending').not.toHaveBeenCalled();

    // 2. Must commit session token and trigger success callback
    expect(getAuthToken(), 'Active token must be committed').toBe('fresh-step-up-jwt-token');
    expect(onLoginSuccessSpy, 'onLoginSuccess callback must receive user').toHaveBeenCalledWith(mockUser);
  });

  it('L1 Mutation Guard 2: When isStepUpPending() is false, Login delegates strictly to completeLogin(), NEVER completeStepUp()', async () => {
    vi.spyOn(sessionModule, 'hasLoginCallback').mockReturnValue(true);
    vi.spyOn(sessionModule, 'isStepUpPending').mockReturnValue(false);

    const completeLoginSpy = vi.spyOn(sessionModule, 'completeLogin').mockResolvedValue({
      token: 'standard-login-jwt-token',
      user: mockUser,
      expiresAt: Math.floor(Date.now() / 1000) + 1800,
      isStepUp: false,
    });
    const completeStepUpSpy = vi.spyOn(sessionModule, 'completeStepUp');
    const onLoginSuccessSpy = vi.fn();

    await act(async () => {
      root.render(<Login onLoginSuccess={onLoginSuccessSpy} />);
    });
    await act(async () => {
      await new Promise((r) => setTimeout(r, 50));
    });

    // 1. Must invoke completeLogin, NEVER completeStepUp
    expect(completeLoginSpy, 'Must call completeLogin when step-up is NOT pending').toHaveBeenCalledTimes(1);
    expect(completeStepUpSpy, 'Must NOT call completeStepUp when step-up is NOT pending').not.toHaveBeenCalled();

    // 2. Must commit session token and trigger success callback
    expect(getAuthToken(), 'Active token must be committed').toBe('standard-login-jwt-token');
    expect(onLoginSuccessSpy).toHaveBeenCalledWith(mockUser);
  });

  it('L2 Mutation Guard: When completeStepUp() rejects, Login catch strictly executes clearAuthToken() and renders error', async () => {
    vi.spyOn(sessionModule, 'hasLoginCallback').mockReturnValue(true);
    vi.spyOn(sessionModule, 'isStepUpPending').mockReturnValue(true);

    // Pre-populate memory token to verify it gets cleared on failure
    setAuthToken('pre-existing-bearer-token');
    expect(getAuthToken()).toBe('pre-existing-bearer-token');

    vi.spyOn(sessionModule, 'completeStepUp').mockRejectedValue(
      new Error('ID 토큰 전자 서명 검증에 실패했습니다')
    );
    const onLoginSuccessSpy = vi.fn();

    await act(async () => {
      root.render(<Login onLoginSuccess={onLoginSuccessSpy} />);
    });
    await act(async () => {
      await new Promise((r) => setTimeout(r, 50));
    });

    // 1. Error message rendered
    expect(container.textContent).toContain('ID 토큰 전자 서명 검증에 실패했습니다');

    // 2. Invariant: Active token MUST be cleared (null), no hidden residual token
    expect(getAuthToken(), 'Active token must be strictly null after failure (kills L2)').toBeNull();
    expect(onLoginSuccessSpy, 'onLoginSuccess must NOT be called on failure').not.toHaveBeenCalled();
  });

  it('L2 Mutation Guard 2: When completeLogin() rejects, Login catch strictly executes clearAuthToken() and renders error', async () => {
    vi.spyOn(sessionModule, 'hasLoginCallback').mockReturnValue(true);
    vi.spyOn(sessionModule, 'isStepUpPending').mockReturnValue(false);

    setAuthToken('pre-existing-bearer-token');
    expect(getAuthToken()).toBe('pre-existing-bearer-token');

    vi.spyOn(sessionModule, 'completeLogin').mockRejectedValue(
      new Error('인증 제공자가 로그인을 완료하지 못했습니다')
    );
    const onLoginSuccessSpy = vi.fn();

    await act(async () => {
      root.render(<Login onLoginSuccess={onLoginSuccessSpy} />);
    });
    await act(async () => {
      await new Promise((r) => setTimeout(r, 50));
    });

    expect(container.textContent).toContain('인증 제공자가 로그인을 완료하지 못했습니다');
    expect(getAuthToken(), 'Active token must be strictly null after failure (kills L2)').toBeNull();
    expect(onLoginSuccessSpy).not.toHaveBeenCalled();
  });

  it('Codex Requirement 5: Non-boolean truthy isStepUp marker ("false", 1, {}) forces isStepUpPending() to false, selecting completeLogin()', async () => {
    const storageMap = new Map<string, string>();
    storageMap.set(sessionModule.STORAGE_KEY, JSON.stringify({
      isStepUp: 'false', // String truthy value
      state: 'mock_state',
      verifier: 'mock_verifier',
      createdAt: Date.now(),
      redirectUri: 'https://portal.saintvision.lan/callback',
      config: (window as any).__SAINTVISION_CONFIG__,
    }));

    vi.stubGlobal('sessionStorage', {
      getItem: (k: string) => storageMap.get(k) ?? null,
      setItem: (k: string, v: string) => storageMap.set(k, v),
      removeItem: (k: string) => storageMap.delete(k),
    });

    vi.spyOn(sessionModule, 'hasLoginCallback').mockReturnValue(true);

    const completeStepUpSpy = vi.spyOn(sessionModule, 'completeStepUp');
    const completeLoginSpy = vi.spyOn(sessionModule, 'completeLogin').mockRejectedValue(
      new Error('로그인 요청 검증에 실패했습니다')
    );

    await act(async () => {
      root.render(<Login onLoginSuccess={vi.fn()} />);
    });
    await vi.waitFor(() => {
      expect(completeLoginSpy).toHaveBeenCalledTimes(1);
    });

    // completeStepUp must NOT be selected for truthy string marker "false"
    expect(completeStepUpSpy, 'Must NEVER select completeStepUp for non-boolean marker').not.toHaveBeenCalled();
    expect(completeLoginSpy, 'Must fallback to completeLogin for non-boolean marker').toHaveBeenCalledTimes(1);
  });

  it('V1 Mutation Guard: End-to-end Login callback with non-boolean marker executes real completeLogin(), rejects before network calls, and clears active token', async () => {
    const fetchSpy = vi.fn();
    vi.stubGlobal('fetch', fetchSpy);

    const cfg = sessionModule.authConfig();
    const storageMap = new Map<string, string>();
    storageMap.set(sessionModule.STORAGE_KEY, JSON.stringify({
      isStepUp: 'false', // String non-boolean marker
      state: 'mock_state',
      verifier: 'mock_verifier_abcdefghijklmnopqrstuvwxyz0123456789',
      createdAt: Date.now(),
      redirectUri: 'https://portal.saintvision.lan/callback',
      config: cfg,
    }));

    vi.stubGlobal('sessionStorage', {
      getItem: (k: string) => storageMap.get(k) ?? null,
      setItem: (k: string, v: string) => storageMap.set(k, v),
      removeItem: (k: string) => storageMap.delete(k),
    });

    setAuthToken('pre-existing-bearer-token');
    expect(getAuthToken()).toBe('pre-existing-bearer-token');

    const onLoginSuccessSpy = vi.fn();

    // Do NOT mock completeLogin or completeStepUp - run real implementation
    await act(async () => {
      root.render(<Login onLoginSuccess={onLoginSuccessSpy} />);
    });

    await vi.waitFor(() => {
      expect(container.textContent).toContain('로그인 요청 검증에 실패했습니다. 다시 로그인하세요.');
    });

    // Invariants: 0 network calls, active token cleared by Login catch block, onLoginSuccess not called
    expect(fetchSpy, 'Must NEVER call network endpoints when non-boolean marker is rejected').not.toHaveBeenCalled();
    expect(getAuthToken(), 'Active token must be cleared by Login failure handler').toBeNull();
    expect(onLoginSuccessSpy).not.toHaveBeenCalled();
    expect(storageMap.size).toBe(0);
  });
});
