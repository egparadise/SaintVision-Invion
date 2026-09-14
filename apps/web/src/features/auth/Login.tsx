import React, { useState, useEffect } from 'react';
import { Button } from '@/shared/ui/Button';
import { apiClient, setAuthToken } from '@/shared/api/client';
import { generateCodeVerifier, generateCodeChallenge, generateState, generateNonce } from './pkce';

export interface LoginProps {
  onLoginSuccess: (user: { id: string; name: string; role: string; tenantId?: string }) => void;
}

interface TokenResponse {
  access_token: string;
  token_type: string;
  expires_in: number;
  user: {
    id: string;
    name: string;
    role: string;
    tenantId?: string;
  };
}

export const Login: React.FC<LoginProps> = ({ onLoginSuccess }) => {
  const [isLoading, setIsLoading] = useState(false);
  const [selectedIdp, setSelectedIdp] = useState('internal-keycloak');
  const [errorMessage, setErrorMessage] = useState<string | null>(null);

  // Handle OIDC Authorization Code redirect callback with PKCE code_verifier
  useEffect(() => {
    if (typeof window === 'undefined') return;
    const params = new URLSearchParams(window.location.search);
    const code = params.get('code');
    const returnedState = params.get('state');
    const savedState = sessionStorage.getItem('oidc_state');
    const codeVerifier = sessionStorage.getItem('oidc_verifier');

    if (code && codeVerifier && returnedState && returnedState === savedState) {
      sessionStorage.removeItem('oidc_state');
      sessionStorage.removeItem('oidc_verifier');
      window.history.replaceState({}, document.title, window.location.pathname);
      setIsLoading(true);
      apiClient<TokenResponse>('/v1/auth/token', {
        method: 'POST',
        body: JSON.stringify({
          grant_type: 'authorization_code',
          code,
          code_verifier: codeVerifier,
          client_id: 'saintvision-web',
          state: returnedState,
        }),
      })
        .then((response) => {
          setAuthToken(response.access_token);
          onLoginSuccess(response.user);
        })
        .catch((err: any) => {
          console.error('OIDC Callback exchange failed:', err);
          const detail = err.detail || err.message || '인증 코드 교환에 실패했습니다.';
          setErrorMessage(`인증 실패: ${detail}`);
        })
        .finally(() => {
          setIsLoading(false);
        });
    }
  }, [onLoginSuccess]);

  const handleOidcLogin = async () => {
    setIsLoading(true);
    setErrorMessage(null);
    try {
      // 1. Generate RFC 7636 PKCE cryptographic parameters
      const codeVerifier = generateCodeVerifier(43);
      const codeChallenge = await generateCodeChallenge(codeVerifier);
      const state = generateState();
      const nonce = generateNonce();

      // Real external IdP redirect flow (Claude B-6/7 & ADR-014 OIDC specification)
      const externalIdpUrl = (window as any).__SAINTVISION_CONFIG__?.idpAuthorizeUrl;
      if (externalIdpUrl) {
        sessionStorage.setItem('oidc_verifier', codeVerifier);
        sessionStorage.setItem('oidc_state', state);
        const redirectUri = encodeURIComponent(`${window.location.origin}/callback`);
        window.location.href = `${externalIdpUrl}?response_type=code&client_id=saintvision-web&redirect_uri=${redirectUri}&scope=openid%20profile%20email&state=${state}&code_challenge=${codeChallenge}&code_challenge_method=S256`;
        return;
      }

      // Standalone Intranet / Verification Environment: Exchange via control plane broker at /v1/auth/token
      const response = await apiClient<TokenResponse>('/v1/auth/token', {
        method: 'POST',
        body: JSON.stringify({
          grant_type: 'authorization_code',
          code: `auth_code_${generateNonce()}`,
          code_verifier: codeVerifier,
          code_challenge: codeChallenge,
          code_challenge_method: 'S256',
          client_id: 'saintvision-web',
          idp: selectedIdp,
          state,
          nonce,
        }),
      });

      // 3. Store in memory (never in localStorage) and notify parent
      setAuthToken(response.access_token);
      onLoginSuccess(response.user);
    } catch (err: any) {
      console.error('OIDC authentication failed:', err);
      const detail = err.detail || err.message || '인증 서버(/v1/auth/token) 연결에 실패했습니다.';
      setErrorMessage(`인증 실패: ${detail}`);
    } finally {
      setIsLoading(false);
    }
  };

  return (
    <div
      style={{
        display: 'flex',
        alignItems: 'center',
        justifyContent: 'center',
        minHeight: '70vh',
      }}
    >
      <div
        style={{
          width: '100%',
          maxWidth: '420px',
          padding: '36px 32px',
          backgroundColor: 'var(--color-bg-surface)',
          borderRadius: 'var(--radius-lg)',
          border: '1px solid var(--color-border-subtle)',
          boxShadow: 'var(--shadow-lg)',
          textAlign: 'center',
        }}
      >
        <div style={{ marginBottom: '24px' }}>
          <div style={{ fontSize: '2.5rem', marginBottom: '8px' }}>🔐</div>
          <h2 style={{ fontSize: '1.5rem', fontWeight: 700, color: 'var(--color-text-primary)' }}>
            SaintVision-Invion
          </h2>
          <p style={{ fontSize: '0.875rem', color: 'var(--color-text-muted)', marginTop: '4px' }}>
            사내 내부망 단일 인증 (SSO / OIDC + PKCE)
          </p>
        </div>

        <div style={{ marginBottom: '24px', textAlign: 'left' }}>
          <label style={{ display: 'block', fontSize: '0.8125rem', fontWeight: 600, marginBottom: '6px' }}>
            인증 제공자 (IdP) 선택:
          </label>
          <select
            value={selectedIdp}
            onChange={(e) => setSelectedIdp(e.target.value)}
            style={{
              width: '100%',
              padding: '10px 12px',
              borderRadius: 'var(--radius-md)',
              border: '1px solid var(--color-border-strong)',
              backgroundColor: 'var(--color-bg-canvas)',
              color: 'var(--color-text-primary)',
              fontSize: '0.875rem',
            }}
          >
            <option value="internal-keycloak">사내 사설 Keycloak (OIDC Code+PKCE)</option>
            <option value="corporate-ad">사내 Active Directory / ADFS</option>
          </select>
        </div>

        <div
          style={{
            padding: '12px',
            backgroundColor: 'var(--color-bg-subtle)',
            borderRadius: 'var(--radius-md)',
            fontSize: '0.75rem',
            color: 'var(--color-text-secondary)',
            marginBottom: '24px',
            lineHeight: 1.5,
            textAlign: 'left',
          }}
        >
          🔒 <strong>보안 준수 사항:</strong><br />
          - Access Token은 브라우저 메모리에만 보관 (localStorage 금지)<br />
          - Refresh Token은 <code>httpOnly + Secure + SameSite=Strict</code> 쿠키 격리
        </div>

        {errorMessage && (
          <div
            role="alert"
            style={{
              padding: '10px 12px',
              backgroundColor: 'rgba(248, 81, 73, 0.1)',
              border: '1px solid var(--color-danger)',
              borderRadius: 'var(--radius-md)',
              fontSize: '0.75rem',
              color: 'var(--color-danger)',
              marginBottom: '16px',
              textAlign: 'left',
            }}
          >
            ⚠️ {errorMessage}
          </div>
        )}

        <Button
          variant="primary"
          size="lg"
          isLoading={isLoading}
          onClick={handleOidcLogin}
          style={{ width: '100%' }}
        >
          {selectedIdp === 'internal-keycloak' ? 'Keycloak 계정으로 로그인' : 'AD 계정으로 로그인'}
        </Button>
      </div>
    </div>
  );
};
