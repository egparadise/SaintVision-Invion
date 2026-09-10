import React, { useState } from 'react';
import { ProblemDetails } from '@/contracts/types';
import { Button } from './Button';

export interface ErrorStateProps {
  problem: ProblemDetails;
  onRetry?: () => void;
}

export const ErrorState: React.FC<ErrorStateProps> = ({ problem, onRetry }) => {
  const [copied, setCopied] = useState(false);

  const handleCopyTrace = () => {
    const text = `Error Code: ${problem.code}\nCategory: ${problem.category}\nTrace ID: ${problem.traceId}\nDetail: ${problem.detail}`;
    navigator.clipboard.writeText(text);
    setCopied(true);
    setTimeout(() => setCopied(false), 2000);
  };

  return (
    <div
      role="alert"
      style={{
        padding: '24px',
        backgroundColor: 'var(--color-bg-surface)',
        borderRadius: 'var(--radius-lg)',
        border: '1px solid var(--color-status-offline)',
        boxShadow: 'var(--shadow-md)',
      }}
    >
      <div style={{ display: 'flex', alignItems: 'center', gap: '10px', marginBottom: '12px' }}>
        <span style={{ fontSize: '1.5rem' }} aria-hidden="true">⚠️</span>
        <div>
          <h3 style={{ fontSize: '1.125rem', fontWeight: 600, color: 'var(--color-status-offline)' }}>
            {problem.title || '요청 처리 실패'}
          </h3>
          <span style={{ fontSize: '0.8125rem', color: 'var(--color-text-muted)' }}>
            코드: <code>{problem.code}</code> ({problem.category})
          </span>
        </div>
      </div>

      <p style={{ fontSize: '0.875rem', color: 'var(--color-text-secondary)', marginBottom: '16px', lineHeight: 1.6 }}>
        {problem.detail}
      </p>

      <div
        style={{
          display: 'flex',
          alignItems: 'center',
          justifyContent: 'space-between',
          padding: '10px 14px',
          backgroundColor: 'var(--color-bg-subtle)',
          borderRadius: 'var(--radius-md)',
          marginBottom: '16px',
          fontSize: '0.8125rem',
        }}
      >
        <div style={{ display: 'flex', alignItems: 'center', gap: '8px' }}>
          <span style={{ color: 'var(--color-text-muted)' }}>추적 ID:</span>
          <code style={{ color: 'var(--color-text-primary)', fontWeight: 600 }}>{problem.traceId}</code>
        </div>
        <Button variant="ghost" size="sm" onClick={handleCopyTrace}>
          {copied ? '복사 완료!' : '오류 정보 복사'}
        </Button>
      </div>

      <div style={{ display: 'flex', gap: '12px' }}>
        {problem.retryable && onRetry && (
          <Button variant="primary" size="md" onClick={onRetry}>
            다시 시도
          </Button>
        )}
      </div>
    </div>
  );
};
