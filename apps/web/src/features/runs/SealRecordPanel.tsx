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
  const [verifications, setVerifications] = useState<Record<string, VerificationState>>({});
  const [contextBundle, setContextBundle] = useState<ContextBundleResponse | null>(null);
  const [isLoading, setIsLoading] = useState(false);
  const [isUnsealed, setIsUnsealed] = useState(false);
  const [error, setError] = useState<PanelError | null>(null);
  const [liveAnnouncement, setLiveAnnouncement] = useState('봉인 기록 대기 중');

  const abortControllerRef = useRef<AbortController | null>(null);

  const cleanErrorMessage = (err: any): PanelError => {
    const problem = typeof err?.problem === 'object' && err?.problem !== null ? err.problem : undefined;
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

    const rawMessage = String(err?.message || err?.detail || (typeof err?.problem === 'string' ? err.problem : '') || err || '');
    if (/<[a-z][\s\S]*>/i.test(rawMessage) || rawMessage.includes('SyntaxError') || rawMessage.includes('502') || rawMessage.includes('504')) {
      return {
        status: err?.status || 502,
        message: '서버 또는 게이트웨이 오류가 발생했습니다. (잠시 후 다시 시도해 주세요)',
      };
    }

    return {
      status: err?.status,
      code: err?.code,
      message: rawMessage || '봉인 기록 조회 중 오류가 발생했습니다.',
    };
  };

  const loadData = useCallback(async () => {
    if (!projectId || !runId) {
      setRunRecord(null);
      setArtifactsPage(null);
      setVerifications({});
      setContextBundle(null);
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

    // Clear stale state
    setRunRecord(null);
    setArtifactsPage(null);
    setVerifications({});
    setContextBundle(null);
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
        if (signal.aborted) return;
        setRunRecord(record);
      } catch (err: any) {
        if (signal.aborted) return;
        const pErr = cleanErrorMessage(err);
        // Canonical unsealed state: 404 RES-0004 or "No sealed record"
        if (pErr.status === 404 && (pErr.code === 'RES-0004' || (pErr.detail && pErr.detail.includes('No sealed record')))) {
          recordMissing = true;
          setIsUnsealed(true);
        } else {
          // Actual error (e.g. 401, 403, 500, network error)
          setError(pErr);
          setIsLoading(false);
          setLiveAnnouncement('❌ 봉인 기록 조회 실패');
          return;
        }
      }

      // If unsealed, also check if a latest Context Bundle exists (G-04 R3: unsealed runs answer latest bundle with sealed: false)
      if (recordMissing) {
        try {
          const bundle = await fetchContextBundle(projectId, runId, signal);
          if (!signal.aborted && bundle) {
            setContextBundle(bundle);
          }
        } catch {
          // No bundle either, expected for unsealed runs with no bundle
        }
        setIsLoading(false);
        setLiveAnnouncement('봉인 기록 없음: 미봉인 실행');
        return;
      }

      // 2. Sealed: fetch R2 (Artifacts) and R3 (Context Bundle) in parallel
      const [artifactsResult, bundleResult] = await Promise.allSettled([
        fetchRunRecordArtifacts(projectId, runId, undefined, signal),
        fetchContextBundle(projectId, runId, signal),
      ]);

      if (signal.aborted) return;

      let artifactCount = 0;
      if (artifactsResult.status === 'fulfilled') {
        setArtifactsPage(artifactsResult.value);
        artifactCount = artifactsResult.value.count;
      }

      let bundleStatusText = '없음';
      if (bundleResult.status === 'fulfilled') {
        setContextBundle(bundleResult.value);
        bundleStatusText = bundleResult.value.hashVerified ? '해시일치' : '해시불일치';
      }

      setIsLoading(false);
      setLiveAnnouncement(`봉인 기록 조회 완료: 봉인됨 (아티팩트 ${artifactCount}건, 번들 ${bundleStatusText})`);
    } catch (err: any) {
      if (signal.aborted) return;
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

  const handleVerifyArtifact = async (artifactId: string) => {
    if (!projectId || !runId) return;

    setVerifications((prev) => ({
      ...prev,
      [artifactId]: { ...prev[artifactId], isVerifying: true, error: undefined },
    }));
    setLiveAnnouncement(`아티팩트 ${artifactId} 무결성 검증 중...`);

    try {
      const res: ArtifactPinVerificationResponse = await verifyRunRecordArtifact(projectId, runId, artifactId);
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
        backgroundColor: '#161b22',
        borderRadius: '8px',
        border: '1px solid #30363d',
        color: '#c9d1d9',
      }}
    >
      {/* Live Region - Always mounted in DOM */}
      <div
        role="status"
        aria-live="polite"
        data-testid="seal-record-live-status"
        style={{
          position: 'absolute',
          width: 1,
          height: 1,
          padding: 0,
          margin: -1,
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

      {/* Error alert banner */}
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
            marginBottom: '20px',
            color: '#e3b341',
          }}
        >
          <div style={{ fontWeight: 600, fontSize: '0.9375rem', marginBottom: '6px' }}>
            ℹ️ 이 실행(Run)은 아직 봉인(Seal)되지 않은 실행입니다.
          </div>
          <div style={{ fontSize: '0.8125rem', color: '#c9d1d9', lineHeight: 1.5 }}>
            서버 원장에 봉인 기록이 존재하지 않습니다 (404 RES-0004). 작업 실행이 완료되더라도 명시적 봉인 절차(W1)가 완료되기 전까지는 불변 아티팩트 핀 및 무결성 다이제스트가 고정되지 않습니다.
          </div>
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
          <h4 style={{ fontSize: '0.9375rem', fontWeight: 600, color: '#f0f6fc', marginBottom: '12px' }}>
            1. 봉인 기본 명세 (RunRecord)
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
      {runRecord && artifactsPage && (
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
            <span style={{ fontSize: '0.75rem', color: '#8b949e' }}>
              총 {artifactsPage.count}개 아티팩트 고정
            </span>
          </div>

          {artifactsPage.items.length === 0 ? (
            <div style={{ padding: '16px', textAlign: 'center', color: '#8b949e', fontSize: '0.8125rem' }}>
              봉인된 아티팩트가 없습니다.
            </div>
          ) : (
            <div style={{ overflowX: 'auto' }}>
              <table style={{ width: '100%', borderCollapse: 'collapse', fontSize: '0.8125rem' }}>
                <caption style={{ textAlign: 'left', fontSize: '0.75rem', color: '#8b949e', marginBottom: '8px' }}>
                  봉인된 아티팩트 목록 및 무결성 검증
                </caption>
                <thead>
                  <tr style={{ borderBottom: '1px solid #30363d', color: '#8b949e', textAlign: 'left' }}>
                    <th scope="col" style={{ padding: '8px' }}>아티팩트 ID</th>
                    <th scope="col" style={{ padding: '8px' }}>역할 (Role)</th>
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
                                ⚠️ 불일치 (Tampered/Mismatch)
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
            </div>
          )}
        </div>
      )}

      {/* Context Bundle Metadata (R3) */}
      {contextBundle && (
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
          </div>

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
              <div style={{ color: '#8b949e', fontSize: '0.75rem' }}>검색 전략 / 아이템 수</div>
              <div style={{ color: '#f0f6fc', marginTop: '2px' }}>
                <span data-testid="bundle-retrieval-strategy" style={{ fontWeight: 600, color: '#58a6ff' }}>
                  {contextBundle.retrievalStrategy}
                </span>
                <span style={{ color: '#8b949e', margin: '0 6px' }}>•</span>
                <span>총 {contextBundle.itemCount}개 ({contextBundle.totalBytes.toLocaleString()} B)</span>
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
                <caption style={{ textAlign: 'left', fontSize: '0.75rem', color: '#8b949e', marginBottom: '8px' }}>
                  컨텍스트 번들 아이템 메타데이터
                </caption>
                <thead>
                  <tr style={{ borderBottom: '1px solid #30363d', color: '#8b949e', textAlign: 'left' }}>
                    <th scope="col" style={{ padding: '6px 8px' }}>#</th>
                    <th scope="col" style={{ padding: '6px 8px' }}>아이템 ID</th>
                    <th scope="col" style={{ padding: '6px 8px' }}>버전</th>
                    <th scope="col" style={{ padding: '6px 8px' }}>종류 (Kind)</th>
                    <th scope="col" style={{ padding: '6px 8px' }}>내용 해시 (SHA-256)</th>
                    <th scope="col" style={{ padding: '6px 8px' }}>크기</th>
                    <th scope="col" style={{ padding: '6px 8px' }}>신뢰도</th>
                  </tr>
                </thead>
                <tbody>
                  {contextBundle.items.map((it) => (
                    <tr
                      key={`${it.ordinal}-${it.itemId}`}
                      data-testid={`bundle-item-row-${it.ordinal}`}
                      style={{ borderBottom: '1px solid #21262d' }}
                    >
                      <td style={{ padding: '6px 8px', color: '#8b949e' }}>{it.ordinal}</td>
                      <td style={{ padding: '6px 8px', fontFamily: 'monospace', fontWeight: 600, color: '#f0f6fc' }}>
                        {it.itemId}
                        {it.redacted && (
                          <span style={{ marginLeft: '6px', fontSize: '0.6875rem', color: '#e3b341' }}>[비식별화]</span>
                        )}
                      </td>
                      <td style={{ padding: '6px 8px', color: '#c9d1d9' }}>v{it.itemVersion}</td>
                      <td style={{ padding: '6px 8px', color: '#58a6ff' }}>{it.kind}</td>
                      <td style={{ padding: '6px 8px', fontFamily: 'monospace', color: '#8b949e', fontSize: '0.75rem' }} title={it.contentHash}>
                        {it.contentHash.slice(0, 16)}...
                      </td>
                      <td style={{ padding: '6px 8px', color: '#c9d1d9' }}>{it.byteSize.toLocaleString()} B</td>
                      <td style={{ padding: '6px 8px', color: '#a0a8b2' }}>
                        {it.confidence !== null && it.confidence !== undefined ? `${Math.round(it.confidence * 100)}%` : '-'}
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          )}
        </div>
      )}
    </div>
  );
};