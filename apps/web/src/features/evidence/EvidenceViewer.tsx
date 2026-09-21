import React, { useState, useEffect } from 'react';
import { Button } from '@/shared/ui/Button';
import { apiClient } from '@/shared/api/client';

export interface EvidenceViewerProps {
  runId: string;
  projectId?: string;
  onBack: () => void;
}

export interface EvidenceData {
  evidenceId: string;
  runId: string;
  projectId?: string;
  timestamp?: string;
  generatedAt?: string;
  manifestDigest?: string;
  specDigest?: string;
  policyVersion?: string;
  integrityVerification: 'PASS' | 'FAIL' | 'UNVERIFIED';
  policySpecifications?: {
    retention: string;
    tamperProtection: string;
  };
  retentionPolicy?: string;
  tamperCheck?: string;
  state?: string;
  allPhysicallyStopped?: boolean;
  allSucceeded?: boolean;
  immutable?: boolean;
}

export const EvidenceViewer: React.FC<EvidenceViewerProps> = ({ runId, projectId, onBack }) => {
  const [evidenceData, setEvidenceData] = useState<EvidenceData | null>(null);
  const [isLoading, setIsLoading] = useState(true);
  const [errorMessage, setErrorMessage] = useState<string | null>(null);
  const [copySuccess, setCopySuccess] = useState(false);

  const fetchEvidence = React.useCallback(async () => {
    if (!projectId || !projectId.trim()) {
      setIsLoading(false);
      setErrorMessage('프로젝트 식별자(projectId)가 제공되지 않아 증적을 조회할 수 없습니다. (위조 식별자 합성 차단)');
      return;
    }
    setIsLoading(true);
    setErrorMessage(null);
    try {
      const prjId = projectId.trim();
      const res = await apiClient<any>(`/v1/projects/${prjId}/runs/${runId}/result`);
      let integrityStatus: 'PASS' | 'FAIL' | 'UNVERIFIED' = 'PASS';
      if (res.sealed && res.output?.sha256) {
        integrityStatus = 'PASS';
      } else if (res.outputAbsentReason) {
        integrityStatus = 'FAIL';
      } else {
        integrityStatus = 'UNVERIFIED';
      }

      const data: EvidenceData = {
        evidenceId: res.evidence?.evidenceId || res.evidenceId || `evi_${runId}`,
        runId,
        projectId: prjId,
        manifestDigest: res.output?.sha256 || res.evidence?.outputSha256 || res.manifestDigest || res.stopReceipt?.outputCommitmentHash || undefined,
        specDigest: res.evidence?.specDigest || res.evidence?.inputSha256 || undefined,
        policyVersion: res.evidence?.policyVersion || res.policyVersion || 'shard-completion:v1',
        state: res.state || 'succeeded',
        allPhysicallyStopped: res.stopReceipt?.physicallyStopped ?? (res.stopReceipt?.processStarted ? res.stopReceipt?.exitCode !== undefined : true),
        allSucceeded: res.state === 'succeeded',
        generatedAt: res.completedAt || res.stopReceipt?.finishedAt || undefined,
        immutable: res.sealed ?? true,
        integrityVerification: integrityStatus,
        policySpecifications: {
          retention: '1_YEAR_PINNED (ADR-012)',
          tamperProtection: 'IMMUTABLE_STORAGE_APPEND_ONLY',
        },
        retentionPolicy: '1_YEAR_PINNED (ADR-012)',
        tamperCheck: 'IMMUTABLE_STORAGE_APPEND_ONLY',
      };
      setEvidenceData(data);
    } catch (err: any) {
      console.warn('Evidence load failed:', err);
      // Surface actual backend error; never synthesize fake PASS or mock data on failure
      setEvidenceData(null);
      setErrorMessage(`증거 패키지 로드 실패: ${err?.message || '백엔드 응답을 불러올 수 없습니다.'}`);
    } finally {
      setIsLoading(false);
    }
  }, [runId, projectId]);

  useEffect(() => {
    fetchEvidence();
  }, [fetchEvidence]);

  const displayId = evidenceData?.evidenceId || `evi_${runId}`;

  return (
    <div>
      <div style={{ display: 'flex', alignItems: 'center', gap: '16px', marginBottom: '24px' }}>
        <Button variant="ghost" size="sm" onClick={onBack}>
          ← 이전으로 돌아가기
        </Button>
        <h2 style={{ fontSize: '1.25rem', fontWeight: 600 }}>
          불변 증거 (Evidence) 패키지: <code>{displayId}</code>
        </h2>
        {isLoading && (
          <span style={{ fontSize: '0.8125rem', color: 'var(--color-text-secondary)' }}>
            증거 패키지 동기화 중...
          </span>
        )}
      </div>

      {errorMessage && (
        <div
          role="alert"
          style={{
            padding: '16px 20px',
            marginBottom: '20px',
            backgroundColor: 'rgba(248, 81, 73, 0.1)',
            border: '1px solid var(--color-status-error)',
            borderRadius: 'var(--radius-md)',
            color: 'var(--color-status-error)',
            fontSize: '0.875rem',
            display: 'flex',
            justifyContent: 'space-between',
            alignItems: 'center',
          }}
        >
          <div>
            <strong>증거 패키지 동기화 오류</strong>
            <p style={{ marginTop: '4px', marginBottom: 0, opacity: 0.9 }}>{errorMessage}</p>
          </div>
          <Button variant="secondary" size="sm" onClick={() => fetchEvidence()}>
            재시도
          </Button>
        </div>
      )}

      {evidenceData && (
        <div
          style={{
            padding: '24px',
            backgroundColor: 'var(--color-bg-surface)',
            borderRadius: 'var(--radius-lg)',
            border: '1px solid var(--color-border-subtle)',
            boxShadow: 'var(--shadow-sm)',
          }}
        >
          <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: '16px' }}>
            <div style={{ display: 'flex', gap: '8px', flexWrap: 'wrap', alignItems: 'center' }}>
              <span style={{ fontSize: '0.75rem', fontWeight: 600, color: 'var(--color-text-secondary)', marginRight: '4px' }}>
                동적 무결성 판정:
              </span>
              {/* Dynamic Per-Run Verification Result */}
              {evidenceData.integrityVerification === 'PASS' && (
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
                  ✓ 출력 무결성 검증 통과 (PASS)
                </span>
              )}
              {evidenceData.integrityVerification === 'FAIL' && (
                <span
                  style={{
                    padding: '4px 10px',
                    borderRadius: 'var(--radius-sm)',
                    fontSize: '0.75rem',
                    fontWeight: 700,
                    backgroundColor: 'rgba(248, 81, 73, 0.15)',
                    color: 'var(--color-status-error)',
                    border: '1px solid var(--color-status-error)',
                  }}
                >
                  ✗ 출력 무결성 검증 실패 (FAIL)
                </span>
              )}
              {evidenceData.integrityVerification === 'UNVERIFIED' && (
                <span
                  style={{
                    padding: '4px 10px',
                    borderRadius: 'var(--radius-sm)',
                    fontSize: '0.75rem',
                    fontWeight: 700,
                    backgroundColor: 'rgba(234, 179, 8, 0.15)',
                    color: '#d97706',
                    border: '1px solid #d97706',
                  }}
                >
                  ⚠️ 출력 무결성 미검증 (UNVERIFIED)
                </span>
              )}
              {evidenceData.immutable && (
                <span
                  style={{
                    padding: '4px 10px',
                    borderRadius: 'var(--radius-sm)',
                    fontSize: '0.75rem',
                    fontWeight: 600,
                    backgroundColor: 'rgba(56, 139, 253, 0.15)',
                    color: 'var(--color-brand-primary)',
                    border: '1px solid var(--color-brand-primary)',
                  }}
                >
                  🔒 불변 봉인 (SEALED)
                </span>
              )}
            </div>

            <div style={{ display: 'flex', alignItems: 'center', gap: '8px' }}>
              {copySuccess && (
                <span role="status" data-testid="copy-evidence-success" style={{ fontSize: '0.75rem', color: '#10b981' }}>
                  ✓ 클립보드에 복사되었습니다
                </span>
              )}
              <Button
                variant="secondary"
                size="sm"
                data-testid="copy-evidence-json-btn"
                onClick={() => {
                  navigator.clipboard.writeText(JSON.stringify(evidenceData, null, 2));
                  setCopySuccess(true);
                  setTimeout(() => setCopySuccess(false), 2500);
                }}
              >
                Evidence JSON 복사
              </Button>
            </div>
          </div>

          {/* Static System Architecture Policy Specifications (Design Requirements, Not Per-Run Dynamic Tests) */}
          <div
            style={{
              marginBottom: '20px',
              padding: '10px 14px',
              backgroundColor: 'var(--color-bg-canvas)',
              borderRadius: 'var(--radius-sm)',
              border: '1px dashed var(--color-border-subtle)',
              display: 'flex',
              gap: '16px',
              flexWrap: 'wrap',
              alignItems: 'center',
              fontSize: '0.75rem',
              color: 'var(--color-text-secondary)',
            }}
          >
            <span style={{ fontWeight: 600, color: 'var(--color-text-muted)' }}>
              [시스템 정책 사양]
            </span>
            <span title="시스템에 사전 구성된 정적 보존 정책 규격입니다">
              정책 규격: 1년 보존 Pin (ADR-012)
            </span>
            <span title="시스템에 사전 구성된 정적 불변 저장 설계 규격입니다">
              설계 규격: 불변 단일 봉인
            </span>
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
      )}
    </div>
  );
};
