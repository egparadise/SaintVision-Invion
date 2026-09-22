import React, { useEffect, useRef, useState } from 'react';
import { Button } from '@/shared/ui/Button';
import { setAuthToken } from '@/shared/api/client';
import { authConfig, beginLogin, completeLogin, hasLoginCallback, type SessionUser } from './session';

export interface LoginProps {
  onLoginSuccess: (user: SessionUser) => void;
  initialError?: string | null;
}
export const Login: React.FC<LoginProps> = ({ onLoginSuccess, initialError }) => {
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(initialError || null);

  useEffect(() => {
    if (initialError) setError(initialError);
  }, [initialError]);
  // StrictMode reattaches to one exchange; it must not reuse the authorization code.
  const exchange = useRef<ReturnType<typeof completeLogin> | null>(null);
  const success = useRef(onLoginSuccess); success.current = onLoginSuccess;
  useEffect(() => {
    let active = true;
    if (!exchange.current && hasLoginCallback()) exchange.current = completeLogin();
    if (exchange.current) {
      setLoading(true);
      exchange.current.then(({ token, user }) => {
        if (active) { setAuthToken(token); success.current(user); }
      }).catch(err => { if (active) setError(err.message); })
        .finally(() => { if (active) setLoading(false); });
    } else {
      try { authConfig(); } catch (err) { setError((err as Error).message); }
    }
    return () => { active = false; };
  }, []);
  const login = async () => {
    setLoading(true); setError(null);
    try { window.location.assign(await beginLogin()); }
    catch (err) { setError((err as Error).message); setLoading(false); }
  };
  return <section style={{ maxWidth: 480, margin: '80px auto', padding: 32 }}>
    <h1>SaintVision 로그인</h1>
    <p>조직에서 설정한 인증 제공자의 계정으로 로그인하세요.</p>
    <p>프로젝트 권한은 서버에서 확인합니다. 새로고침하거나 로그아웃하면 다시 로그인해야 합니다.</p>
    {error && <p role="alert" data-testid="login-error-alert">{error}</p>}
    <Button isLoading={loading} onClick={login}>조직 계정으로 로그인</Button>
  </section>;
};
