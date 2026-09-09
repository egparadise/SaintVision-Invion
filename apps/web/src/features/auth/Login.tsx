import React, { useState } from 'react';
import { Button } from '@/shared/ui/Button';

export interface LoginProps {
  onLoginSuccess: (user: { id: string; name: string; role: string }) => void;
}

export const Login: React.FC<LoginProps> = ({ onLoginSuccess }) => {
  const [isLoading, setIsLoading] = useState(false);
  const [selectedIdp, setSelectedIdp] = useState('internal-keycloak');

  const handleOidcLogin = () => {
    setIsLoading(true);
    // Simulate OIDC Authorization Code + PKCE flow:
    // 1. Generate code_verifier & code_challenge
    // 2. Redirect to IdP /auth
    // 3. Callback with code -> POST /v1/auth/token exchange
    setTimeout(() => {
      setIsLoading(false);
      onLoginSuccess({
        id: 'usr_01JABCDEF_ADMIN',
        name: '시스템 관리자',
        role: 'cluster:admin',
      });
    }, 800);
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
