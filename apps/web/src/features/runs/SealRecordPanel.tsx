import React, { useState, useEffect, useCallback, useRef } from 'react';
import type { RunRecordResponse } from '@/contracts/run-record-response';
import type { RunRecordArtifactPageResponse } from '@/contracts/run-record-artifact-page-response';
import type { ArtifactPinVerificationResponse } from '@/contracts/artifact-pin-verification-response';
import type { ContextBundleResponse } from '@/contracts/context-bundle-response';
import { Button } from '@/shared/ui/Button';
import {
  fetchRunRecord,
  fetchRunRecordArtifacts,
  verifyRunRecordArtifact,
  fetchContextBundle,
} from '@/shared/api/runSealObservation';

export interface SealRecordPanelProps {
  projectId?: string;
  runId: string;
}

interface VerificationState {
  verified?: boolean;
  pinnedChecksumSha256?: string;
  isVerifying?: boolean;
  error?: string;
}

interface PanelError {
  code?: string;
  status?: number;
  title?: string;
  detail?: string;
  message: string;
}

export const SealRecordPanel: React.FC<SealRecordPanelProps> = ({ projectId, runId }) => {
  const [runRecord, setRunRecord] = useState<RunRecordResponse | null>(null);
  const [artifactsPage, setArtifactsPage] = useState<RunRecordArtifactPageResponse | null>(null);
  const [artifactsError, setArtifactsError] = useState<PanelError | null>(null);
  const [isLoadingMoreArtifacts, setIsLoadingMoreArtifacts] = useState(false);
  const [verifications, setVerifications] = useState<Record<string, VerificationState>>({});
  const [contextBundle, setContextBundle] = useState<ContextBundleResponse | null>(null);
  const [bundleError, setBundleError] = useState<PanelError | null>(null);
  const [bundleSpecialStatus, setBundleSpecialStatus] = useState<'not_found' | 'reproduction_failed' | null>(null);
  const [isLoading, setIsLoading] = useState(false);
  const [isUnsealed, setIsUnsealed] = useState(false);
  const [error, setError] = useState<PanelError | null>(null);
  const [liveAnnouncement, setLiveAnnouncement] = useState('봉인 기록 대기 중');

  const abortControllerRef = useRef<AbortController | null>(null);
  const generationRef = useRef<number>(0);

  const cleanErrorMessage = (err: any): PanelError => {
    const problem = typeof err?.problem === 'object' && err?.problem !== null ? err.problem : undefined;
    const rawDetail = String(problem?.detail || err?.detail || '');
    const rawMessage = String(err?.message || problem?.title || err?.title || (typeof err?.problem === 'string' ? err.problem : '') || err || '');

    const status = Number(err?.status || problem?.status || 0);
    const isHtmlOrGateway =
      /<[a-z][\s\S]*>/i.test(rawDetail) ||
      /<[a-z][\s\S]*>/i.test(rawMessage) ||
      rawMessage.includes('SyntaxError') ||
      status === 502 ||
      status === 504 ||
      rawDetail.includes('Bad Gateway') ||
      rawMessage.includes('Bad Gateway') ||
      rawDetail.includes('Gateway Timeout') ||
      rawMessage.includes('Gateway Timeout');

    if (isHtmlOrGateway) {
      return {
        status: status === 504 ? 504 : 502,
        code: problem?.code || err?.code || (status === 504 ? 'NET-0504' : 'NET-0502'),
        message: '서버 또는 게이트웨이 오류가 발생했습니다. (잠시 후 다시 시도해 주세요)',
      };
    }

    if (problem) {
      return {
        code: problem.code || err?.code,
        status: problem.status ?? err?.status,
        title: problem.title,
        detail: problem.detail,
        message: problem.detail || problem.title || err?.message || '오류가 발생했습니다.',
      };
    }

    if (err && typeof err === 'object' && (err.status || err.code || err.detail || err.title)) {
      return {
        code: err.code,
        status: err.status,
        title: err.title,
        detail: err.detail,
        message: err.detail || err.title || err.message || '오류가 발생했습니다.',
      };
    }

    return {
      status: err?.status,
      code: err?.code,
      message: rawMessage || '봉인 기록 조회 중 오류가 발생했습니다.',
    };
  };

  const loadData = useCallback(async () => {
    generationRef.current += 1;
    const currentGen = generationRef.current;

    if (!projectId || !runId) {
      setRunRecord(null);
      setArtifactsPage(null);
      setArtifactsError(null);
      setVerifications({});
      setContextBundle(null);
      setBundleError(null);
      setBundleSpecialStatus(null);
      setIsUnsealed(false);
      setError({ message: '프로젝트 또는 Run 식별자가 제공되지 않았습니다.' });
      setLiveAnnouncement('식별자 누락으로 봉인 기록을 조회할 수 없습니다.');
      return;
    }

    // Cancel ongoing request
    if (abortControllerRef.current) {
      abortControllerRef.current.abort();
    }
    const controller = new AbortController();
    abortControllerRef.current = controller;
    const { signal } = controller;

    // Clear all state to prevent stale data leak across Run ID switches
    setRunRecord(null);
    setArtifactsPage(null);
    setArtifactsError(null);
    setVerifications({});
    setContextBundle(null);
    setBundleError(null);
    setBundleSpecialStatus(null);
    setIsUnsealed(false);
    setError(null);
    setIsLoading(true);
    setLiveAnnouncement('봉인 기록 조회 중...');

    try {
      let record: RunRecordResponse | null = null;
      let recordMissing = false;

      // 1. Fetch R1 RunRecord
      try {
        record = await fetchRunRecord(projectId, runId, signal);
        if (signal.aborted || generationRef.current !== currentGen) return;
        setRunRecord(record);
      } catch (err: any) {
        if (signal.aborted || generationRef.current !== currentGen) return;
        const pErr = cleanErrorMessage(err);
        // Canonical unsealed state: 404 RES-0004 with exact detail 'No sealed record for this run.'
        // Any other 404 (e.g. 'No such run.') is an actual resource error
        if (
          pErr.status === 404 &&
          pErr.code === 'RES-0004' &&
          pErr.detail === 'No sealed record for this run.'
        ) {
          recordMissing = true;
          setIsUnsealed(true);
        } else {
          setError(pErr);
          setIsLoading(false);
          setLiveAnnouncement('❌ 봉인 기록 조회 실패');
          return;
        }
      }

      // If unsealed, check if latest unsealed Context Bundle exists
      if (recordMissing) {
        let bundleStatusDesc = '';
        try {
          const bundle = await fetchContextBundle(projectId, runId, signal);
          if (!signal.aborted && bundle) {
            setContextBundle(bundle);
            bundleStatusDesc = ', 최신 컨텍스트 번들 존재';
          }
        } catch (bErr: any) {
          if (signal.aborted || generationRef.current !== currentGen) return;
          const bPErr = cleanErrorMessage(bErr);
          if (bPErr.status === 404 && (bPErr.detail?.includes('No context bundle') || bPErr.message?.includes('No context bundle'))) {
            setBundleSpecialStatus('not_found');
          } else if (bPErr.status === 409 && (bPErr.code === 'GRAPH-0002' || bPErr.detail?.includes('cannot be reproduced') || bPErr.message?.includes('cannot be reproduced'))) {
            setBundleSpecialStatus('reproduction_failed');
            bundleStatusDesc = ', 번들 재현불가';
          } else {
            setBundleError(bPErr);
            bundleStatusDesc = `, 번들 조회 실패 (${bPErr.code || bPErr.status || '오류'})`;
          }
        }
        if (signal.aborted || generationRef.current !== currentGen) return;
        setIsLoading(false);
        setLiveAnnouncement(`봉인 기록 없음: 미봉인 실행${bundleStatusDesc}`);
        return;
      }

      // 2. Sealed run: fetch R2 (Artifacts) and R3 (Context Bundle) in parallel
      const [artifactsResult, bundleResult] = await Promise.allSettled([
        fetchRunRecordArtifacts(projectId, runId, undefined, signal),
        fetchContextBundle(projectId, runId, signal),
      ]);

      if (signal.aborted || generationRef.current !== currentGen) return;

      let artifactMsg = '없음';
      if (artifactsResult.status === 'fulfilled') {
        setArtifactsPage(artifactsResult.value);
        artifactMsg = `이 페이지 ${artifactsResult.value.count}건${artifactsResult.value.nextCursor ? ' (다음 페이지 있음)' : ''}`;
      } else {
        const aErr = cleanErrorMessage(artifactsResult.reason);
        setArtifactsError(aErr);
        artifactMsg = '조회 실패';
      }

      let bundleMsg = '없음';
      if (bundleResult.status === 'fulfilled') {
        setContextBundle(bundleResult.value);
        bundleMsg = bundleResult.value.hashVerified ? '해시일치' : '해시불일치';
      } else {
        const bErr = cleanErrorMessage(bundleResult.reason);
        if (bErr.status === 404 && (bErr.detail?.includes('No context bundle') || bErr.message?.includes('No context bundle'))) {
          setBundleSpecialStatus('not_found');
          bundleMsg = '없음';
        } else if (bErr.status === 409 && (bErr.code === 'GRAPH-0002' || bErr.detail?.includes('cannot be reproduced') || bErr.message?.includes('cannot be reproduced'))) {
          setBundleSpecialStatus('reproduction_failed');
          bundleMsg = '재현불가';
        } else {
          setBundleError(bErr);
          bundleMsg = '조회실패';
        }
      }

      setIsLoading(false);
      setLiveAnnouncement(`봉인 기록 조회 완료: 봉인됨 (아티팩트 ${artifactMsg}, 번들 ${bundleMsg})`);
    } catch (err: any) {
      if (signal.aborted || generationRef.current !== currentGen) return;
      setIsLoading(false);
      setError(cleanErrorMessage(err));
      setLiveAnnouncement('❌ 봉인 기록 조회 실패');
    }
  }, [projectId, runId]);

  useEffect(() => {
    loadData();
    return () => {
      if (abortControllerRef.current) {
        abortControllerRef.current.abort();
      }
    };
  }, [loadData]);

  const handleLoadNextPage = async () => {
    if (!projectId || !runId || !artifactsPage?.nextCursor || isLoadingMoreArtifacts) return;
    const currentGen = generationRef.current;
    const reqRunId = runId;
    setIsLoadingMoreArtifacts(true);
    setLiveAnnouncement(`아티팩트 다음 페이지 조회 중 (cursor: ${artifactsPage.nextCursor.slice(0, 12)}...)...`);

    try {
      const nextPage = await fetchRunRecordArtifacts(projectId, reqRunId, { cursor: artifactsPage.nextCursor });
      if (generationRef.current !== currentGen || runId !== reqRunId) return;
      setArtifactsPage(nextPage);
      setLiveAnnouncement(`아티팩트 다음 페이지 조회 완료: 이 페이지 ${nextPage.count}건${nextPage.nextCursor ? ' (추가 페이지 있음)' : ''}`);
    } catch (err: any) {
      if (generationRef.current !== currentGen || runId !== reqRunId) return;
      const pErr = cleanErrorMessage(err);
      setArtifactsError(pErr);
      setLiveAnnouncement(`❌ 아티팩트 다음 페이지 조회 실패: ${pErr.message}`);
    } finally {
      if (generationRef.current === currentGen && runId === reqRunId) {
        setIsLoadingMoreArtifacts(false);
      }
    }
  };

  const handleVerifyArtifact = async (artifactId: string) => {
    if (!projectId || !runId) return;
    const currentGen = generationRef.current;
    const currentRunId = runId;

    setVerifications((prev) => ({
      ...prev,
      [artifactId]: { ...prev[artifactId], isVerifying: true, error: undefined },
    }));
    setLiveAnnouncement(`아티팩트 ${artifactId} 무결성 검증 중...`);

    try {
      const res: ArtifactPinVerificationResponse = await verifyRunRecordArtifact(projectId, runId, artifactId);
      if (generationRef.current !== currentGen || runId !== currentRunId) return;

      setVerifications((prev) => ({
        ...prev,
        [artifactId]: {
          verified: res.verified,
          pinnedChecksumSha256: res.pinnedChecksumSha256,
          isVerifying: false,
        },
      }));
      setLiveAnnouncement(
        `아티팩트 ${artifactId} 검증 완료: ${res.verified ? '일치' : '불일치'}`
      );
    } catch (err: any) {
      if (generationRef.current !== currentGen || runId !== currentRunId) return;
      const pErr = cleanErrorMessage(err);
      setVerifications((prev) => ({
        ...prev,
        [artifactId]: {
          isVerifying: false,
          error: pErr.message,
        },
      }));
      setLiveAnnouncement(`❌ 아티팩트 ${artifactId} 검증 실패`);
    }
  };

  return (
    <div
      data-testid="seal-record-panel"
      style={{
        padding: '24px',
        backgroundColor: '#0d1117',
        color: '#c9d1d9',
        borderRadius: '8px',
        minHeight: '400px',
        fontFamily: 'system-ui, -apple-system, sans-serif',
      }}
    >
      {/* Live Region: Constant in DOM for screen readers (F1/F6 adherence) */}
      <div
        role="status"
        aria-live="polite"
        data-testid="seal-record-live-status"
        style={{
          position: 'absolute',
          width: '1px',
          height: '1px',
          padding: 0,
          margin: '-1px',
          overflow: 'hidden',
          clip: 'rect(0, 0, 0, 0)',
          whiteSpace: 'nowrap',
          border: 0,
        }}
      >
        {liveAnnouncement}
      </div>

      {/* Header */}
      <div
        style={{
          display: 'flex',
          justifyContent: 'space-between',
          alignItems: 'center',
          marginBottom: '20px',
          borderBottom: '1px solid #30363d',
          paddingBottom: '14px',
        }}
      >
        <div>
          <div style={{ display: 'flex', alignItems: 'center', gap: '10px' }}>
            <h3 style={{ fontSize: '1.125rem', fontWeight: 600, color: '#f0f6fc', margin: 0 }}>
              실행 봉인 기록 (Run Seal Record)
            </h3>
            {isUnsealed && (
              <span
                data-testid="seal-status-badge"
                style={{
                  fontSize: '0.75rem',
                  fontWeight: 600,
                  padding: '2px 8px',
                  borderRadius: '12px',
                  backgroundColor: 'rgba(210, 153, 34, 0.15)',
                  color: '#e3b341',
                  border: '1px solid rgba(210, 153, 34, 0.4)',
                }}
              >
                미봉인 (UNSEALED)
              </span>
            )}
            {runRecord && (
              <span
                data-testid="seal-status-badge"
                style={{
                  fontSize: '0.75rem',
                  fontWeight: 600,
                  padding: '2px 8px',
                  borderRadius: '12px',
                  backgroundColor: 'rgba(46, 160, 67, 0.15)',
                  color: '#3fb950',
                  border: '1px solid rgba(46, 160, 67, 0.4)',
                }}
              >
                ✔ 봉인됨 (SEALED)
              </span>
            )}
          </div>
          <p style={{ fontSize: '0.8125rem', color: '#8b949e', marginTop: '4px', margin: 0 }}>
            G-04 불변 봉인 원장 규격: 서버 파생 아티팩트 핀, 컨텍스트 번들 해시 및 무결성 검증 (R1·R2·R3)
          </p>
        </div>

        <Button
          variant="secondary"
          size="sm"
          data-testid="seal-record-refresh-btn"
          onClick={loadData}
          disabled={isLoading}
        >
          {isLoading ? '조회 중...' : '🔄 새로고침'}
        </Button>
      </div>

      {/* Loading indicator */}
      {isLoading && (
        <div
          data-testid="seal-record-loading"
          style={{
            padding: '20px',
            textAlign: 'center',
            color: '#58a6ff',
            fontSize: '0.875rem',
          }}
        >
          ⏳ 봉인 기록 및 아티팩트 무결성 확인 중...
        </div>
      )}

      {/* Main Error alert banner */}
      {error && (
        <div
          role="alert"
          data-testid="seal-record-error-banner"
          style={{
            padding: '14px 18px',
            marginBottom: '20px',
            backgroundColor: 'rgba(248, 81, 73, 0.15)',
            border: '1px solid #f85149',
            borderRadius: '6px',
            color: '#ff7b72',
            fontSize: '0.875rem',
          }}
        >
          <div style={{ fontWeight: 600, marginBottom: '4px' }}>
            ⚠️ 봉인 기록 조회 실패 {error.code ? `[${error.code}]` : ''} {error.status ? `(${error.status})` : ''}
          </div>
          <div style={{ fontSize: '0.8125rem', color: '#f0f6fc' }}>
            {error.detail || error.message}
          </div>
        </div>
      )}

      {/* Unsealed notice banner */}
      {isUnsealed && (
        <div
          data-testid="seal-record-unsealed-notice"
          style={{
            padding: '16px 20px',
            backgroundColor: 'rgba(210, 153, 34, 0.1)',
            border: '1px solid #d29922',
            borderRadius: '6px',
            color: '#f0f6fc',
            marginBottom: '20px',
          }}
        >
          <div style={{ display: 'flex', alignItems: 'center', gap: '8px', marginBottom: '6px' }}>
            <span style={{ fontSize: '1.125rem' }}>ℹ️</span>
            <span style={{ fontWeight: 600, color: '#e3b341', fontSize: '0.9375rem' }}>
              미봉인 실행 (Run Not Sealed)
            </span>
          </div>
          <p style={{ margin: 0, fontSize: '0.8125rem', color: '#c9d1d9', lineHeight: 1.5 }}>
            이 실행(Run)은 아직 봉인(Seal)되지 않은 실행입니다. 원장 불변 고정 기록(RunRecord)이
            생성되지 않았으므로 봉인 다이제스트 및 핀 아티팩트 목록이 비어 있습니다. (404 RES-0004)
          </p>
        </div>
      )}

      {/* Sealed RunRecord Details (R1) */}
      {runRecord && (
        <div
          data-testid="seal-record-details"
          style={{
            marginBottom: '24px',
            padding: '16px',
            backgroundColor: '#0d1117',
            borderRadius: '6px',
            border: '1px solid #30363d',
          }}
        >
          <h4 style={{ fontSize: '0.9375rem', fontWeight: 600, color: '#f0f6fc', marginTop: 0, marginBottom: '12px' }}>
            1. 원장 봉인 메타데이터 (Run Record Ledger)
          </h4>

          <div
            style={{
              display: 'grid',
              gridTemplateColumns: 'repeat(auto-fit, minmax(220px, 1fr))',
              gap: '12px',
              fontSize: '0.8125rem',
            }}
          >
            <div style={{ padding: '8px 12px', backgroundColor: '#161b22', borderRadius: '4px' }}>
              <div style={{ color: '#8b949e', fontSize: '0.75rem' }}>기록 식별자 (Record ID)</div>
              <div data-testid="seal-record-id" style={{ fontFamily: 'monospace', fontWeight: 600, color: '#f0f6fc', marginTop: '2px' }}>
                {runRecord.recordId}
              </div>
            </div>

            <div style={{ padding: '8px 12px', backgroundColor: '#161b22', borderRadius: '4px' }}>
              <div style={{ color: '#8b949e', fontSize: '0.75rem' }}>봉인 시각 (Sealed At)</div>
              <div data-testid="seal-record-sealed-at" style={{ color: '#f0f6fc', marginTop: '2px' }}>
                {new Date(runRecord.sealedAt).toLocaleString('ko-KR')}
              </div>
            </div>

            <div style={{ padding: '8px 12px', backgroundColor: '#161b22', borderRadius: '4px' }}>
              <div style={{ color: '#8b949e', fontSize: '0.75rem' }}>최종 상태 / 사유</div>
              <div style={{ marginTop: '2px', display: 'flex', gap: '6px', alignItems: 'center' }}>
                <span data-testid="seal-final-state" style={{ fontWeight: 600, color: '#58a6ff' }}>
                  {runRecord.finalState}
                </span>
                <span style={{ color: '#8b949e' }}>/</span>
                <span data-testid="seal-termination-reason" style={{ color: '#c9d1d9' }}>
                  {runRecord.terminationReason}
                </span>
              </div>
            </div>

            <div style={{ padding: '8px 12px', backgroundColor: '#161b22', borderRadius: '4px' }}>
              <div style={{ color: '#8b949e', fontSize: '0.75rem' }}>시도 횟수 (Attempt Count)</div>
              <div data-testid="seal-attempt-count" style={{ fontWeight: 600, color: '#f0f6fc', marginTop: '2px' }}>
                {runRecord.attemptCount}회
              </div>
            </div>

            <div style={{ padding: '8px 12px', backgroundColor: '#161b22', borderRadius: '4px' }}>
              <div style={{ color: '#8b949e', fontSize: '0.75rem' }}>에비던스 식별자 (Evidence ID)</div>
              <div data-testid="seal-evidence-id" style={{ fontFamily: 'monospace', color: '#c9d1d9', marginTop: '2px' }}>
                {runRecord.evidenceId ?? '없음'}
              </div>
            </div>

            <div style={{ padding: '8px 12px', backgroundColor: '#161b22', borderRadius: '4px', gridColumn: '1 / -1' }}>
              <div style={{ color: '#8b949e', fontSize: '0.75rem' }}>워크로드 사양 해시 (Workload Spec SHA-256)</div>
              <div data-testid="seal-workload-spec-sha" style={{ fontFamily: 'monospace', color: '#58a6ff', marginTop: '2px', wordBreak: 'break-all' }}>
                {runRecord.workloadSpecSha256}
              </div>
            </div>

            {runRecord.bundleId && (
              <div style={{ padding: '8px 12px', backgroundColor: '#161b22', borderRadius: '4px', gridColumn: '1 / -1' }}>
                <div style={{ color: '#8b949e', fontSize: '0.75rem' }}>고정 컨텍스트 번들 (Pinned Context Bundle)</div>
                <div data-testid="seal-bundle-info" style={{ fontFamily: 'monospace', marginTop: '2px', color: '#c9d1d9' }}>
                  <code>{runRecord.bundleId}</code>
                  {runRecord.bundleHash && (
                    <span style={{ marginLeft: '10px', color: '#8b949e' }}>
                      (Hash: {runRecord.bundleHash.slice(0, 16)}...)
                    </span>
                  )}
                </div>
              </div>
            )}
          </div>

          {/* Component versions */}
          {runRecord.componentVersions && Object.keys(runRecord.componentVersions).length > 0 && (
            <div style={{ marginTop: '14px' }}>
              <div style={{ fontSize: '0.75rem', color: '#8b949e', marginBottom: '6px' }}>
                봉인 컴포넌트 버전 (Component Versions)
              </div>
              <div style={{ display: 'flex', gap: '8px', flexWrap: 'wrap' }}>
                {Object.entries(runRecord.componentVersions).map(([k, v]) => (
                  <span
                    key={k}
                    style={{
                      fontSize: '0.75rem',
                      fontFamily: 'monospace',
                      padding: '2px 8px',
                      backgroundColor: '#161b22',
                      borderRadius: '4px',
                      border: '1px solid #30363d',
                      color: '#a0a8b2',
                    }}
                  >
                    <strong>{k}</strong>: {v}
                  </span>
                ))}
              </div>
            </div>
          )}
        </div>
      )}

      {/* Pinned Artifacts Table (R2) */}
      {runRecord && (artifactsPage || artifactsError) && (
        <div
          data-testid="seal-artifacts-section"
          style={{
            marginBottom: '24px',
            padding: '16px',
            backgroundColor: '#0d1117',
            borderRadius: '6px',
            border: '1px solid #30363d',
          }}
        >
          <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: '12px' }}>
            <h4 style={{ fontSize: '0.9375rem', fontWeight: 600, color: '#f0f6fc', margin: 0 }}>
              2. 봉인 아티팩트 핀 목록 (Pinned Artifacts)
            </h4>
            {artifactsPage && (
              <span data-testid="seal-artifacts-page-count" style={{ fontSize: '0.75rem', color: '#8b949e' }}>
                이 페이지 {artifactsPage.count}건{artifactsPage.nextCursor ? ' (추가 항목 있음)' : ''}
              </span>
            )}
          </div>

          {artifactsError && (
            <div
              role="alert"
              data-testid="seal-artifacts-error"
              style={{
                padding: '12px 16px',
                backgroundColor: 'rgba(248, 81, 73, 0.15)',
                border: '1px solid #f85149',
                borderRadius: '6px',
                color: '#ff7b72',
                fontSize: '0.8125rem',
                marginBottom: '12px',
              }}
            >
              ⚠️ 아티팩트 목록 조회 실패 {artifactsError.code ? `[${artifactsError.code}]` : ''} {artifactsError.status ? `(${artifactsError.status})` : ''}: {artifactsError.detail || artifactsError.message}
            </div>
          )}

          {artifactsPage && artifactsPage.items.length === 0 ? (
            <div style={{ padding: '16px', textAlign: 'center', color: '#8b949e', fontSize: '0.8125rem' }}>
              봉인된 아티팩트가 없습니다.
            </div>
          ) : artifactsPage && (
            <div style={{ overflowX: 'auto' }}>
              <table style={{ width: '100%', borderCollapse: 'collapse', fontSize: '0.8125rem' }}>
                <caption style={{ textAlign: 'left', fontSize: '0.75rem', color: '#8b949e', marginBottom: '8px' }}>
                  봉인된 아티팩트 목록 및 무결성 검증
                </caption>
                <thead>
                  <tr style={{ borderBottom: '1px solid #30363d', color: '#8b949e', textAlign: 'left' }}>
                    <th scope="col" style={{ padding: '8px' }}>아티팩트 ID</th>
                    <th scope="col" style={{ padding: '8px' }}>역할 (Role)</th>
                    <th scope="col" style={{ padding: '8px' }}>버전</th>
                    <th scope="col" style={{ padding: '8px' }}>URI / 저장 위치</th>
                    <th scope="col" style={{ padding: '8px' }}>봉인 체크섬 (SHA-256)</th>
                    <th scope="col" style={{ padding: '8px' }}>크기</th>
                    <th scope="col" style={{ padding: '8px' }}>무결성 검증 (Verify)</th>
                  </tr>
                </thead>
                <tbody>
                  {artifactsPage.items.map((item) => {
                    const vState = verifications[item.artifactId];
                    return (
                      <tr
                        key={item.artifactId}
                        data-testid={`seal-artifact-row-${item.artifactId}`}
                        style={{ borderBottom: '1px solid #21262d' }}
                      >
                        <td
                          data-testid={`seal-artifact-id-${item.artifactId}`}
                          style={{ padding: '8px', fontFamily: 'monospace', fontWeight: 600, color: '#f0f6fc' }}
                        >
                          {item.artifactId}
                        </td>
                        <td style={{ padding: '8px' }}>
                          <span
                            data-testid={`seal-artifact-role-${item.artifactId}`}
                            style={{
                              fontSize: '0.6875rem',
                              padding: '2px 6px',
                              borderRadius: '4px',
                              backgroundColor: 'rgba(56, 139, 253, 0.15)',
                              color: '#58a6ff',
                              border: '1px solid rgba(56, 139, 253, 0.3)',
                              fontWeight: 600,
                            }}
                          >
                            {item.role}
                          </span>
                        </td>
                        <td
                          data-testid={`seal-artifact-version-${item.artifactId}`}
                          style={{ padding: '8px', fontFamily: 'monospace', color: '#8b949e', fontSize: '0.75rem' }}
                        >
                          {item.objectVersion ?? '-'}
                        </td>
                        <td
                          data-testid={`seal-artifact-uri-${item.artifactId}`}
                          style={{ padding: '8px', fontFamily: 'monospace', color: '#c9d1d9', maxWidth: '240px', overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap' }}
                          title={item.uri}
                        >
                          {item.uri}
                        </td>
                        <td
                          data-testid={`seal-artifact-checksum-${item.artifactId}`}
                          style={{ padding: '8px', fontFamily: 'monospace', color: '#8b949e', fontSize: '0.75rem' }}
                          title={item.checksumSha256}
                        >
                          {item.checksumSha256.slice(0, 16)}...
                        </td>
                        <td
                          data-testid={`seal-artifact-size-${item.artifactId}`}
                          style={{ padding: '8px', color: '#c9d1d9' }}
                        >
                          {item.byteSize.toLocaleString()} B
                        </td>
                        <td style={{ padding: '8px' }}>
                          <div style={{ display: 'flex', alignItems: 'center', gap: '8px' }}>
                            {vState?.isVerifying && (
                              <span style={{ color: '#58a6ff', fontSize: '0.75rem' }}>⏳ 검증 중...</span>
                            )}

                            {vState?.verified === true && (
                              <span
                                data-testid={`seal-artifact-verify-status-${item.artifactId}`}
                                data-tone="match"
                                style={{
                                  fontSize: '0.75rem',
                                  fontWeight: 600,
                                  color: '#3fb950',
                                  backgroundColor: 'rgba(46, 160, 67, 0.15)',
                                  padding: '2px 6px',
                                  borderRadius: '4px',
                                  border: '1px solid rgba(46, 160, 67, 0.4)',
                                }}
                              >
                                ✔ 일치 (Verified)
                              </span>
                            )}

                            {vState?.verified === false && (
                              <span
                                data-testid={`seal-artifact-verify-status-${item.artifactId}`}
                                data-tone="mismatch"
                                style={{
                                  fontSize: '0.75rem',
                                  fontWeight: 600,
                                  color: '#ff7b72',
                                  backgroundColor: 'rgba(248, 81, 73, 0.15)',
                                  padding: '2px 6px',
                                  borderRadius: '4px',
                                  border: '1px solid rgba(248, 81, 73, 0.4)',
                                }}
                              >
                                ⚠️ 불일치 (봉인 다이제스트와 다름·대상 없음)
                              </span>
                            )}

                            {vState?.error && (
                              <span style={{ fontSize: '0.75rem', color: '#ff7b72' }}>
                                오류: {vState.error}
                              </span>
                            )}

                            {vState?.verified === undefined && !vState?.isVerifying && (
                              <div style={{ display: 'flex', alignItems: 'center', gap: '6px' }}>
                                <span
                                  data-testid={`seal-artifact-verify-status-${item.artifactId}`}
                                  style={{
                                    fontSize: '0.75rem',
                                    color: '#a0a8b2',
                                    backgroundColor: 'rgba(160, 168, 178, 0.15)',
                                    padding: '2px 6px',
                                    borderRadius: '4px',
                                  }}
                                >
                                  미검증 (검증 대기)
                                </span>
                                <Button
                                  variant="ghost"
                                  size="sm"
                                  aria-label={`아티팩트 ${item.artifactId} 무결성 검증`}
                                  data-testid={`seal-verify-btn-${item.artifactId}`}
                                  onClick={() => handleVerifyArtifact(item.artifactId)}
                                  style={{ padding: '2px 6px', fontSize: '0.6875rem' }}
                                >
                                  🔍 무결성 검증
                                </Button>
                              </div>
                            )}
                          </div>
                        </td>
                      </tr>
                    );
                  })}
                </tbody>
              </table>

              {/* Pagination when nextCursor is present */}
              {artifactsPage.nextCursor && (
                <div style={{ marginTop: '12px', display: 'flex', justifyContent: 'flex-end', alignItems: 'center', gap: '8px' }}>
                  <span style={{ fontSize: '0.75rem', color: '#8b949e' }}>
                    추가 항목 있음 (Next cursor: {artifactsPage.nextCursor.slice(0, 16)}...)
                  </span>
                  <Button
                    variant="secondary"
                    size="sm"
                    data-testid="seal-artifacts-next-page-btn"
                    onClick={handleLoadNextPage}
                    disabled={isLoadingMoreArtifacts}
                  >
                    {isLoadingMoreArtifacts ? '불러오는 중...' : '다음 페이지 (더보기)'}
                  </Button>
                </div>
              )}
            </div>
          )}
        </div>
      )}

      {/* Context Bundle Metadata (R3) */}
      {(!isUnsealed
        ? (contextBundle || bundleError || bundleSpecialStatus)
        : (contextBundle || bundleError || bundleSpecialStatus === 'reproduction_failed')) && (
        <div
          data-testid="seal-bundle-section"
          style={{
            padding: '16px',
            backgroundColor: '#0d1117',
            borderRadius: '6px',
            border: '1px solid #30363d',
          }}
        >
          <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: '12px' }}>
            <h4 style={{ fontSize: '0.9375rem', fontWeight: 600, color: '#f0f6fc', margin: 0 }}>
              3. 컨텍스트 번들 메타데이터 (Context Bundle)
            </h4>
            {contextBundle && (
              <div style={{ display: 'flex', gap: '8px', alignItems: 'center' }}>
                <span
                  data-testid="bundle-sealed-status"
                  style={{
                    fontSize: '0.75rem',
                    padding: '2px 8px',
                    borderRadius: '12px',
                    fontWeight: 600,
                    backgroundColor: contextBundle.sealed ? 'rgba(46, 160, 67, 0.15)' : 'rgba(210, 153, 34, 0.15)',
                    color: contextBundle.sealed ? '#3fb950' : '#e3b341',
                    border: contextBundle.sealed ? '1px solid rgba(46, 160, 67, 0.4)' : '1px solid rgba(210, 153, 34, 0.4)',
                  }}
                >
                  {contextBundle.sealed ? '봉인 고정 (Sealed Pin)' : '최신 빌드 (Latest Build)'}
                </span>
                <span
                  data-testid="bundle-hash-verified-status"
                  data-tone={contextBundle.hashVerified ? 'match' : 'mismatch'}
                  style={{
                    fontSize: '0.75rem',
                    padding: '2px 8px',
                    borderRadius: '12px',
                    fontWeight: 600,
                    backgroundColor: contextBundle.hashVerified ? 'rgba(46, 160, 67, 0.15)' : 'rgba(248, 81, 73, 0.15)',
                    color: contextBundle.hashVerified ? '#3fb950' : '#ff7b72',
                    border: contextBundle.hashVerified ? '1px solid rgba(46, 160, 67, 0.4)' : '1px solid rgba(248, 81, 73, 0.4)',
                  }}
                >
                  {contextBundle.hashVerified ? '✔ 해시 일치 (Hash Verified)' : '⚠️ 해시 불일치 (Hash Mismatch)'}
                </span>
              </div>
            )}
          </div>

          {/* R3 Error banner */}
          {bundleError && (
            <div
              role="alert"
              data-testid="seal-bundle-error"
              style={{
                padding: '12px 16px',
                backgroundColor: 'rgba(248, 81, 73, 0.15)',
                border: '1px solid #f85149',
                borderRadius: '6px',
                color: '#ff7b72',
                fontSize: '0.8125rem',
              }}
            >
              ⚠️ 컨텍스트 번들 조회 실패 {bundleError.code ? `[${bundleError.code}]` : ''} {bundleError.status ? `(${bundleError.status})` : ''}: {bundleError.detail || bundleError.message}
            </div>
          )}

          {/* R3 409 Reproduction Failed banner */}
          {bundleSpecialStatus === 'reproduction_failed' && (
            <div
              data-testid="seal-bundle-reproduction-failed"
              data-tone="mismatch"
              style={{
                padding: '12px 16px',
                backgroundColor: 'rgba(248, 81, 73, 0.15)',
                border: '1px solid #f85149',
                borderRadius: '6px',
                color: '#ff7b72',
                fontSize: '0.875rem',
              }}
            >
              <div style={{ fontWeight: 600, marginBottom: '4px' }}>
                ⚠️ 번들 재현 불가 (Snapshot Missing / GRAPH-0002)
              </div>
              <div style={{ fontSize: '0.8125rem', color: '#f0f6fc' }}>
                고정된 컨텍스트 스냅숏을 찾을 수 없거나 재현할 수 없습니다 (무결성 검증 실패 사실 보고).
              </div>
            </div>
          )}

          {/* R3 404 Not Found notice */}
          {bundleSpecialStatus === 'not_found' && (
            <div
              data-testid="seal-bundle-not-found"
              style={{
                padding: '12px 16px',
                backgroundColor: '#161b22',
                border: '1px solid #30363d',
                borderRadius: '6px',
                color: '#8b949e',
                fontSize: '0.8125rem',
              }}
            >
              ℹ️ 컨텍스트 번들 없음 (이 실행에 등록된 컨텍스트 번들이 없습니다).
            </div>
          )}

          {contextBundle && (
            <>
              <div
                style={{
                  display: 'grid',
                  gridTemplateColumns: 'repeat(auto-fit, minmax(220px, 1fr))',
                  gap: '12px',
                  fontSize: '0.8125rem',
                  marginBottom: '14px',
                }}
              >
                <div style={{ padding: '8px 12px', backgroundColor: '#161b22', borderRadius: '4px' }}>
                  <div style={{ color: '#8b949e', fontSize: '0.75rem' }}>번들 식별자 (Bundle ID)</div>
                  <div data-testid="bundle-id" style={{ fontFamily: 'monospace', fontWeight: 600, color: '#f0f6fc', marginTop: '2px' }}>
                    {contextBundle.bundleId}
                  </div>
                </div>

                <div style={{ padding: '8px 12px', backgroundColor: '#161b22', borderRadius: '4px' }}>
                  <div style={{ color: '#8b949e', fontSize: '0.75rem' }}>빌드 시각 (Built At)</div>
                  <div style={{ color: '#f0f6fc', marginTop: '2px' }}>
                    {new Date(contextBundle.builtAt).toLocaleString('ko-KR')}
                  </div>
                </div>

                <div style={{ padding: '8px 12px', backgroundColor: '#161b22', borderRadius: '4px' }}>
                  <div style={{ color: '#8b949e', fontSize: '0.75rem' }}>검색 전략 / 아이템 수 / 토큰 추정</div>
                  <div style={{ color: '#f0f6fc', marginTop: '2px' }}>
                    <span data-testid="bundle-retrieval-strategy" style={{ fontWeight: 600, color: '#58a6ff' }}>
                      {contextBundle.retrievalStrategy}
                    </span>
                    <span style={{ color: '#8b949e', margin: '0 6px' }}>•</span>
                    <span data-testid="bundle-item-token-summary">
                      {contextBundle.itemCount}개 ({contextBundle.totalBytes.toLocaleString()} B, 토큰 추정: {contextBundle.tokenEstimate !== null && contextBundle.tokenEstimate !== undefined ? contextBundle.tokenEstimate.toLocaleString() : '미제공'})
                    </span>
                  </div>
                </div>

                <div style={{ padding: '8px 12px', backgroundColor: '#161b22', borderRadius: '4px', gridColumn: '1 / -1' }}>
                  <div style={{ color: '#8b949e', fontSize: '0.75rem' }}>번들 해시 (Bundle Hash SHA-256)</div>
                  <div data-testid="bundle-hash" style={{ fontFamily: 'monospace', color: '#58a6ff', marginTop: '2px', wordBreak: 'break-all' }}>
                    {contextBundle.bundleHash}
                  </div>
                </div>
              </div>

              {/* Items table */}
              {contextBundle.items && contextBundle.items.length > 0 && (
                <div style={{ overflowX: 'auto' }}>
                  <table style={{ width: '100%', borderCollapse: 'collapse', fontSize: '0.8125rem' }}>
                    <thead>
                      <tr style={{ borderBottom: '1px solid #30363d', color: '#8b949e', textAlign: 'left' }}>
                        <th scope="col" style={{ padding: '8px' }}>순번</th>
                        <th scope="col" style={{ padding: '8px' }}>항목 ID</th>
                        <th scope="col" style={{ padding: '8px' }}>종류 (Kind)</th>
                        <th scope="col" style={{ padding: '8px' }}>버전</th>
                        <th scope="col" style={{ padding: '8px' }}>비식별화</th>
                        <th scope="col" style={{ padding: '8px' }}>신뢰도</th>
                        <th scope="col" style={{ padding: '8px' }}>콘텐츠 해시 (SHA-256)</th>
                        <th scope="col" style={{ padding: '8px' }}>바이트 크기</th>
                      </tr>
                    </thead>
                    <tbody>
                      {contextBundle.items.map((item, idx) => (
                        <tr key={`${item.itemId}-${idx}`} style={{ borderBottom: '1px solid #21262d' }}>
                          <td style={{ padding: '8px', color: '#8b949e' }}>{item.ordinal ?? idx + 1}</td>
                          <td style={{ padding: '8px', fontFamily: 'monospace', color: '#c9d1d9' }}>{item.itemId}</td>
                          <td style={{ padding: '8px', color: '#58a6ff' }}>{item.kind}</td>
                          <td style={{ padding: '8px', color: '#8b949e' }}>v{item.itemVersion}</td>
                          <td style={{ padding: '8px' }}>
                            {item.redacted ? (
                              <span style={{ fontSize: '0.6875rem', padding: '1px 6px', borderRadius: '4px', backgroundColor: 'rgba(210, 153, 34, 0.2)', color: '#d29922', fontWeight: 600 }}>
                                [비식별화]
                              </span>
                            ) : (
                              <span style={{ color: '#8b949e' }}>-</span>
                            )}
                          </td>
                          <td style={{ padding: '8px', color: '#8b949e' }}>
                            {item.confidence !== undefined && item.confidence !== null ? `${(item.confidence * 100).toFixed(0)}%` : '-'}
                          </td>
                          <td style={{ padding: '8px', fontFamily: 'monospace', color: '#8b949e', fontSize: '0.75rem' }}>
                            {item.contentHash.slice(0, 16)}...
                          </td>
                          <td style={{ padding: '8px', color: '#c9d1d9' }}>{item.byteSize.toLocaleString()} B</td>
                        </tr>
                      ))}
                    </tbody>
                  </table>
                </div>
              )}
            </>
          )}
        </div>
      )}
    </div>
  );
};
