import React from 'react';
import { ExecutionResultItem } from '@/contracts/types';
import { Button } from '@/shared/ui/Button';

export interface ExecutionResultViewProps {
  result: ExecutionResultItem;
  onBack: () => void;
  onViewEvidence?: (evidenceId: string) => void;
}

export const ExecutionResultView: React.FC<ExecutionResultViewProps> = ({
  result,
  onBack,
  onViewEvidence,
}) => {
  const isSuccess = result.exitCode === 0;

  return (
    <div>
      <div style={{ display: 'flex', alignItems: 'center', gap: '16px', marginBottom: '24px' }}>
        <Button variant="ghost" size="sm" onClick={onBack}>
          ← 이전으로
        </Button>
        <h2 style={{ fontSize: '1.25rem', fontWeight: 600 }}>
          격리 실행 결과 (AC-03 증거 뷰): <code>{result.runId}</code>
        </h2>
      </div>

      {/* Summary Banner */}
      <div
        style={{
          display: 'grid',
          gridTemplateColumns: 'repeat(auto-fit, minmax(220px, 1fr))',
          gap: '16px',
          marginBottom: '24px',
        }}
      >
        {/* Exit Code Card */}
        <div
          style={{
            padding: '20px',
            backgroundColor: 'var(--color-bg-surface)',
            borderRadius: 'var(--radius-lg)',
            border: `1px solid ${isSuccess ? 'var(--color-brand-success)' : 'var(--color-risk-l3-border)'}`,
          }}
        >
          <span style={{ fontSize: '0.75rem', fontWeight: 600, color: 'var(--color-text-muted)' }}>
            종료 코드 (EXIT CODE)
          </span>
          <div style={{ display: 'flex', alignItems: 'center', gap: '8px', marginTop: '8px' }}>
            <span
              style={{
                fontSize: '1.75rem',
                fontWeight: 700,
                color: isSuccess ? 'var(--color-brand-success)' : 'var(--color-brand-danger)',
              }}
            >
              {result.exitCode}
            </span>
            <span
              style={{
                padding: '3px 8px',
                borderRadius: 'var(--radius-sm)',
                fontSize: '0.75rem',
                fontWeight: 600,
                backgroundColor: isSuccess ? 'rgba(16, 185, 129, 0.15)' : 'var(--color-risk-l3-bg)',
                color: isSuccess ? 'var(--color-brand-success)' : 'var(--color-brand-danger)',
              }}
            >
              {isSuccess ? '정상 종료 (SUCCESS)' : '비정상 종료 (FAILED)'}
            </span>
          </div>
        </div>

        {/* Evidence Envelope ID Card */}
        <div
          style={{
            padding: '20px',
            backgroundColor: 'var(--color-bg-surface)',
            borderRadius: 'var(--radius-lg)',
            border: '1px solid var(--color-border-subtle)',
          }}
        >
          <span style={{ fontSize: '0.75rem', fontWeight: 600, color: 'var(--color-text-muted)' }}>
            불변 증거 봉투 (EVIDENCE ENVELOPE)
          </span>
          <div style={{ marginTop: '8px' }}>
            <span style={{ fontFamily: 'monospace', fontWeight: 600, fontSize: '0.9375rem', color: 'var(--color-brand-primary)' }}>
              {result.evidenceId}
            </span>
            {onViewEvidence && (
              <div style={{ marginTop: '6px' }}>
                <button
                  onClick={() => onViewEvidence(result.evidenceId)}
                  style={{
                    background: 'none',
                    border: 'none',
                    padding: 0,
                    fontSize: '0.75rem',
                    color: 'var(--color-brand-primary)',
                    textDecoration: 'underline',
                    cursor: 'pointer',
                  }}
                >
                  증거 봉투 원장 보기 →
                </button>
              </div>
            )}
          </div>
        </div>

        {/* Resource Reclamation Status Card */}
        <div
          style={{
            padding: '20px',
            backgroundColor: 'var(--color-bg-surface)',
            borderRadius: 'var(--radius-lg)',
            border: '1px solid var(--color-border-subtle)',
          }}
        >
          <span style={{ fontSize: '0.75rem', fontWeight: 600, color: 'var(--color-text-muted)' }}>
            자원 회수 상태 (AC-03 RECLAMATION)
          </span>
          <div style={{ marginTop: '8px', display: 'flex', alignItems: 'center', gap: '6px' }}>
            <span style={{ fontSize: '1.25rem' }}>{result.resourceReclaimed ? '♻️' : '⏳'}</span>
            <span
              style={{
                fontSize: '0.875rem',
                fontWeight: 600,
                color: result.resourceReclaimed ? 'var(--color-brand-success)' : 'var(--color-brand-warning)',
              }}
            >
              {result.resourceReclaimed ? '자원 완전 회수 완료' : '자원 회수 대기 중'}
            </span>
          </div>
          <span style={{ fontSize: '0.75rem', color: 'var(--color-text-muted)', marginTop: '4px', display: 'block' }}>
            CPU/RAM/GPU Lease 해제 및 임시 마운트 언마운트
          </span>
        </div>
      </div>

      {/* Command & Workspace Context */}
      <div
        style={{
          padding: '20px',
          backgroundColor: 'var(--color-bg-surface)',
          borderRadius: 'var(--radius-lg)',
          border: '1px solid var(--color-border-subtle)',
          marginBottom: '24px',
        }}
      >
        <h3 style={{ fontSize: '1rem', fontWeight: 600, marginBottom: '12px' }}>실행 명령 및 작업공간</h3>
        <div style={{ display: 'grid', gridTemplateColumns: 'auto 1fr', gap: '8px 16px', fontSize: '0.875rem' }}>
          <span style={{ color: 'var(--color-text-muted)' }}>작업공간:</span>
          <code>{result.workspaceId}</code>
          <span style={{ color: 'var(--color-text-muted)' }}>실행 명령:</span>
          <code style={{ backgroundColor: 'var(--color-bg-subtle)', padding: '2px 6px', borderRadius: '4px' }}>
            {result.command}
          </code>
          <span style={{ color: 'var(--color-text-muted)' }}>실행 시각:</span>
          <span>
            {new Date(result.executedAt).toLocaleString('ko-KR')} ~ {new Date(result.completedAt).toLocaleString('ko-KR')}
          </span>
        </div>
      </div>

      {/* Security Audit Trail: Allowed vs Blocked Operations (AC-03) */}
      <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: '20px' }}>
        {/* Allowed Operations */}
        <div
          style={{
            padding: '20px',
            backgroundColor: 'var(--color-bg-surface)',
            borderRadius: 'var(--radius-lg)',
            border: '1px solid var(--color-border-subtle)',
          }}
        >
          <div style={{ display: 'flex', alignItems: 'center', gap: '8px', marginBottom: '14px' }}>
            <span style={{ color: 'var(--color-brand-success)' }}>✓</span>
            <h3 style={{ fontSize: '1rem', fontWeight: 600 }}>허용된 실행 로그 ({result.allowedEvents.length}건)</h3>
          </div>
          <div style={{ display: 'flex', flexDirection: 'column', gap: '8px', maxHeight: '280px', overflowY: 'auto' }}>
            {result.allowedEvents.map((evt, idx) => (
              <div
                key={idx}
                style={{
                  padding: '8px 12px',
                  backgroundColor: 'var(--color-bg-subtle)',
                  borderRadius: 'var(--radius-md)',
                  fontSize: '0.8125rem',
                  fontFamily: 'monospace',
                }}
              >
                <div style={{ color: 'var(--color-text-muted)', fontSize: '0.6875rem' }}>{evt.timestamp}</div>
                <div>
                  <strong>{evt.action}</strong>: <code>{evt.path || 'N/A'}</code>
                </div>
              </div>
            ))}
          </div>
        </div>

        {/* Denied / Blocked Operations */}
        <div
          style={{
            padding: '20px',
            backgroundColor: 'var(--color-bg-surface)',
            borderRadius: 'var(--radius-lg)',
            border: '1px solid var(--color-border-subtle)',
          }}
        >
          <div style={{ display: 'flex', alignItems: 'center', gap: '8px', marginBottom: '14px' }}>
            <span style={{ color: 'var(--color-brand-danger)' }}>🚫</span>
            <h3 style={{ fontSize: '1rem', fontWeight: 600 }}>
              차단된 금지 작업 로그 ({result.deniedEvents.length}건)
            </h3>
          </div>
          {result.deniedEvents.length === 0 ? (
            <div style={{ padding: '24px', textAlign: 'center', color: 'var(--color-text-muted)', fontSize: '0.875rem' }}>
              금지 정책 위반 없이 안전하게 실행되었습니다.
            </div>
          ) : (
            <div style={{ display: 'flex', flexDirection: 'column', gap: '8px', maxHeight: '280px', overflowY: 'auto' }}>
              {result.deniedEvents.map((evt, idx) => (
                <div
                  key={idx}
                  style={{
                    padding: '8px 12px',
                    backgroundColor: 'var(--color-risk-l3-bg)',
                    border: '1px solid var(--color-risk-l3-border)',
                    borderRadius: 'var(--radius-md)',
                    fontSize: '0.8125rem',
                    fontFamily: 'monospace',
                    color: 'var(--color-risk-l3-text)',
                  }}
                >
                  <div style={{ fontSize: '0.6875rem', opacity: 0.8 }}>{evt.timestamp}</div>
                  <div>
                    <strong>{evt.action}</strong>: <code>{evt.path}</code>
                  </div>
                  <div style={{ fontSize: '0.75rem', marginTop: '2px', fontWeight: 600 }}>
                    사유: {evt.reason}
                  </div>
                </div>
              ))}
            </div>
          )}
        </div>
      </div>
    </div>
  );
};
