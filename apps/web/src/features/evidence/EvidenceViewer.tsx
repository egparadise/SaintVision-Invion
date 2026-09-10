import React from 'react';
import { Button } from '@/shared/ui/Button';

export interface EvidenceViewerProps {
  runId: string;
  onBack: () => void;
}

export const EvidenceViewer: React.FC<EvidenceViewerProps> = ({ runId, onBack }) => {
  const evidenceData = {
    evidenceId: `evd_01JABCDEF_${runId.slice(-6)}`,
    runId,
    timestamp: '2026-09-09T17:35:25+09:00',
    specDigest: 'sha256:4a8b79c3d2e1f0e9...a1b2c3d4',
    toolCalls: [
      { tool: 'git.checkout', exitCode: 0, wallTimeMs: 420 },
      { tool: 'test.run', exitCode: 0, wallTimeMs: 12400 },
      { tool: 'artifact.write', exitCode: 0, wallTimeMs: 180 },
    ],
    integrityVerification: 'PASS',
    retentionPolicy: '1_YEAR_PINNED (ADR-012)',
    tamperCheck: 'VERIFIED_IMMUTABLE',
  };

  return (
    <div>
      <div style={{ display: 'flex', alignItems: 'center', gap: '16px', marginBottom: '24px' }}>
        <Button variant="ghost" size="sm" onClick={onBack}>
          ← 이전으로 돌아가기
        </Button>
        <h2 style={{ fontSize: '1.25rem', fontWeight: 600 }}>
          불변 증거 (Evidence) 패키지: <code>{evidenceData.evidenceId}</code>
        </h2>
      </div>

      <div
        style={{
          padding: '24px',
          backgroundColor: 'var(--color-bg-surface)',
          borderRadius: 'var(--radius-lg)',
          border: '1px solid var(--color-border-subtle)',
          boxShadow: 'var(--shadow-sm)',
        }}
      >
        <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: '20px' }}>
          <div style={{ display: 'flex', gap: '8px' }}>
            <span
              style={{
                padding: '4px 10px',
                borderRadius: 'var(--radius-sm)',
                fontSize: '0.75rem',
                fontWeight: 700,
                backgroundColor: 'rgba(16, 185, 129, 0.15)',
                color: 'var(--color-status-online)',
                border: '1px solid var(--color-status-online)',
              }}
            >
              ✓ 무결성 검증 통과 (PASS)
            </span>
            <span
              style={{
                padding: '4px 10px',
                borderRadius: 'var(--radius-sm)',
                fontSize: '0.75rem',
                fontWeight: 600,
                backgroundColor: 'var(--color-bg-subtle)',
                color: 'var(--color-text-secondary)',
              }}
            >
              📌 1년 보존 Pin 적용
            </span>
          </div>

          <Button
            variant="secondary"
            size="sm"
            onClick={() => {
              navigator.clipboard.writeText(JSON.stringify(evidenceData, null, 2));
              alert('Evidence JSON이 클립보드에 복사되었습니다.');
            }}
          >
            Evidence JSON 복사
          </Button>
        </div>

        <pre
          style={{
            padding: '16px',
            backgroundColor: 'var(--color-bg-canvas)',
            color: 'var(--color-text-primary)',
            borderRadius: 'var(--radius-md)',
            fontFamily: 'monospace',
            fontSize: '0.8125rem',
            lineHeight: 1.5,
            border: '1px solid var(--color-border-strong)',
            overflowX: 'auto',
          }}
        >
          {JSON.stringify(evidenceData, null, 2)}
        </pre>
      </div>
    </div>
  );
};
