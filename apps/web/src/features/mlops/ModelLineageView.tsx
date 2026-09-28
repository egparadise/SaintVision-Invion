import React, { useState, useRef } from 'react';
import { ModelLineage, ModelCommitObservation } from '@/contracts/types';
import { Button } from '@/shared/ui/Button';
import { fetchModelCommitment } from '@/shared/api/modelCommitmentObservation';
import { fetchConformanceStatus, fetchAdapterConformance, type ConformanceStatusUnion, type AdapterConformanceUnion } from '@/shared/api/adapterObservation';
import { MlopsManager } from './mlopsEngine';

/** Per-check tally across the recorded adapters, from the server's outcomes only. */
function outcomeSummary(
  records: ReadonlyArray<{ adapter: string; outcomes: ReadonlyArray<{ name: string; passed: boolean; skipped: boolean }> }>,
  checkName: string
): string {
  let ok = 0;
  let failed = 0;
  let skipped = 0;
  for (const record of records) {
    const outcome = record.outcomes.find((o) => o.name === checkName);
    if (!outcome) continue;
    if (outcome.skipped) skipped += 1;
    else if (outcome.passed) ok += 1;
    else failed += 1;
  }
  return `통과 ${ok} · 실패 ${failed} · 건너뜀 ${skipped} (${records.length}개 기록)`;
}

export interface ModelLineageViewProps {
  initialLineages?: ModelLineage[];
  currentProjectId?: string;
}

export const ModelLineageView: React.FC<ModelLineageViewProps> = ({
  initialLineages = [],
  currentProjectId,
}) => {
  const [mlopsManager] = useState<MlopsManager>(() => new MlopsManager(initialLineages));
  const [lineages, setLineages] = useState<ModelLineage[]>(mlopsManager.getLineages());
  const [selectedModelId, setSelectedModelId] = useState<string>(lineages[0]?.modelId || '');
  const [searchQuery, setSearchQuery] = useState('');
  const [approvalInput, setApprovalInput] = useState('');
  const [actionNotice, setActionNotice] = useState<{ type: 'success' | 'error'; text: string } | null>(null);

  // Adapter conformance observation state (G-03 stage one NOT_OBSERVED / stage two RECORDED)
  const [conformanceProjectId, setConformanceProjectId] = useState(currentProjectId || '');
  const [conformanceData, setConformanceData] = useState<ConformanceStatusUnion | null>(null);
  const [conformanceLoading, setConformanceLoading] = useState(false);
  const [conformanceError, setConformanceError] = useState<{
    code?: string;
    status?: number;
    title?: string;
    detail: string;
  } | null>(null);

  const handleFetchConformance = async (e?: React.FormEvent) => {
    if (e) e.preventDefault();
    if (!conformanceProjectId.trim()) {
      return;
    }
    setConformanceLoading(true);
    setConformanceError(null);
    try {
      const data = await fetchConformanceStatus(conformanceProjectId.trim());
      setConformanceData(data);
    } catch (err: any) {
      setConformanceData(null);
      const prob = err?.problem;
      if (prob) {
        let safeDetail = prob.detail || '요청이 거절되었습니다.';
        // Prevent raw HTML / proxy markup leakage (F3)
        if (/<[a-z][\s\S]*>/i.test(safeDetail)) {
          safeDetail = '서버 게이트웨이 또는 프록시 오류가 발생했습니다. (HTML 응답 수신)';
        } else if (prob.status && prob.status >= 500 && prob.category === 'NET') {
          safeDetail = '서버 내부 오류 또는 업스트림 통신 장애가 발생했습니다.';
        }
        setConformanceError({
          code: prob.code,
          status: prob.status,
          title: prob.title,
          detail: safeDetail,
        });
      } else {
        const isContractMismatch = err?.message && err.message.includes('계약 불일치');
        let fallbackMessage = err?.message || '네트워크 오류가 발생했습니다.';
        if (/<[a-z][\s\S]*>/i.test(fallbackMessage)) {
          fallbackMessage = '서버 또는 프록시 오류가 발생했습니다.';
        }
        setConformanceError({
          detail: isContractMismatch
            ? `클라이언트 응답 계약 검증 실패: ${err.message}`
            : fallbackMessage,
        });
      }
    } finally {
      setConformanceLoading(false);
    }
  };

  // Single adapter conformance observation state (G-03 stage two single route)
  const [singleAdapterName, setSingleAdapterName] = useState('codex-cli');
  const [singleConformanceData, setSingleConformanceData] = useState<AdapterConformanceUnion | null>(null);
  const [singleConformanceLoading, setSingleConformanceLoading] = useState(false);
  const [singleConformanceError, setSingleConformanceError] = useState<{
    code?: string;
    status?: number;
    title?: string;
    detail: string;
    retryable?: boolean;
  } | null>(null);
  const singleConformanceAbortRef = useRef<AbortController | null>(null);
  const singleConformanceGenRef = useRef<number>(0);

  const handleFetchSingleConformance = async (e?: React.FormEvent, targetAdapter?: string) => {
    if (e) e.preventDefault();
    if (singleConformanceLoading) return;
    const adapterToFetch = (targetAdapter !== undefined ? targetAdapter : singleAdapterName).trim();
    if (!conformanceProjectId.trim() || !adapterToFetch) {
      return;
    }

    singleConformanceAbortRef.current?.abort();
    const ctrl = new AbortController();
    singleConformanceAbortRef.current = ctrl;
    const currentGen = ++singleConformanceGenRef.current;

    setSingleConformanceLoading(true);
    setSingleConformanceError(null);
    setSingleConformanceData(null);
    try {
      const data = await fetchAdapterConformance(conformanceProjectId.trim(), adapterToFetch, ctrl.signal);
      if (singleConformanceGenRef.current !== currentGen || ctrl.signal.aborted) return;
      setSingleConformanceData(data);
    } catch (err: any) {
      if (singleConformanceGenRef.current !== currentGen || ctrl.signal.aborted) return;
      setSingleConformanceData(null);
      const prob = err?.problem;
      if (prob) {
        let safeDetail = prob.detail || '요청이 거절되었습니다.';
        if (prob.code === 'RES-0004') {
          safeDetail = '어댑터 없음';
        } else if (/<[a-z][\s\S]*>/i.test(safeDetail)) {
          safeDetail = '서버 게이트웨이 또는 프록시 오류가 발생했습니다. (HTML 응답 수신)';
        } else if (prob.status && prob.status >= 500 && prob.category === 'NET') {
          safeDetail = '서버 내부 오류 또는 업스트림 통신 장애가 발생했습니다.';
        }
        setSingleConformanceError({
          code: prob.code,
          status: prob.status,
          title: prob.title,
          detail: safeDetail,
          retryable: prob.retryable === true,
        });
      } else {
        const isContractMismatch = err?.message && err.message.includes('계약 불일치');
        let fallbackMessage = err?.message || '네트워크 오류가 발생했습니다.';
        if (/<[a-z][\s\S]*>/i.test(fallbackMessage)) {
          fallbackMessage = '서버 또는 프록시 오류가 발생했습니다.';
        }
        setSingleConformanceError({
          detail: isContractMismatch
            ? `클라이언트 응답 계약 검증 실패: ${err.message}`
            : fallbackMessage,
          retryable: false,
        });
      }
    } finally {
      if (singleConformanceGenRef.current === currentGen || singleConformanceAbortRef.current === ctrl) {
        setSingleConformanceLoading(false);
      }
    }
  };

  // Model commitment observation state (starts empty, requiring explicit project/model context)
  const [commitmentProject, setCommitmentProject] = useState(currentProjectId || '');
  const [commitmentModelId, setCommitmentModelId] = useState('');
  const [commitmentVersion, setCommitmentVersion] = useState('');
  const [commitmentData, setCommitmentData] = useState<ModelCommitObservation | null>(null);
  const [commitmentLoading, setCommitmentLoading] = useState(false);
  const [commitmentError, setCommitmentError] = useState<{
    code?: string;
    status?: number;
    title?: string;
    detail: string;
  } | null>(null);

  const selectedModel = lineages.find((m) => m.modelId === selectedModelId) || lineages[0];

  const handleSelectModel = (modelId: string) => {
    setSelectedModelId(modelId);
    const m = lineages.find((item) => item.modelId === modelId);
    if (m) {
      setCommitmentModelId(m.modelId);
      setCommitmentVersion(m.version || '');
    }
  };

  const handleSearch = (e: React.FormEvent) => {
    e.preventDefault();
    if (!searchQuery.trim()) return;

    const matched = mlopsManager.queryLineage(searchQuery);
    if (matched) {
      handleSelectModel(matched.modelId);
      setActionNotice({
        type: 'success',
        text: `✔ 역추적(Reverse Query) 성공: [${matched.modelName}] 계보가 일치합니다.`,
      });
    } else {
      setActionNotice({
        type: 'error',
        text: `❌ 검색 결과 없음: 입력된 식별자 '${searchQuery}'와 일치하는 모델/커밋/데이터셋/다이제스트가 없습니다.`,
      });
    }
  };

  const handleDeploy = (modelId: string) => {
    if (!approvalInput.trim()) {
      setActionNotice({
        type: 'error',
        text: '🛑 배포 게이트 차단: 승인 식별자(approvalId)가 입력되지 않았습니다. (위조 번호 승인 게이트 통과 방지)',
      });
      return;
    }
    const res = mlopsManager.deployModel({
      modelId,
      approvalId: approvalInput.trim(),
    });

    if (!res.success) {
      setActionNotice({
        type: 'error',
        text: `🛑 배포 게이트 차단: ${res.error}`,
      });
    } else {
      setLineages(mlopsManager.getLineages());
      setActionNotice({
        type: 'success',
        text: `✔ [모의 시뮬레이션] [${res.deployedModel?.modelName}] 로컬 배포 게이트 시뮬레이션 완료 (백엔드 서빙 배포 API 미노출 상태로 실제 인프라 미반영 · 백엔드 digest 고정과 무관 · Digest: ${res.deployedModel?.deploymentDigest.slice(0, 24)}...)`,
      });
    }
  };

  const handleFetchCommitment = async (e?: React.FormEvent) => {
    if (e) e.preventDefault();
    if (!commitmentProject.trim() || !commitmentModelId.trim() || !commitmentVersion.trim()) {
      return;
    }
    setCommitmentLoading(true);
    setCommitmentError(null);
    try {
      const data = await fetchModelCommitment(
        commitmentProject.trim(),
        commitmentModelId.trim(),
        commitmentVersion.trim()
      );
      setCommitmentData(data);
    } catch (err: any) {
      setCommitmentData(null);
      const prob = err?.problem;
      if (prob) {
        setCommitmentError({
          code: prob.code,
          status: prob.status,
          title: prob.title,
          detail: prob.detail || '요청이 거절되었습니다.',
        });
      } else {
        const isContractMismatch = err?.message && err.message.includes('계약 불일치');
        setCommitmentError({
          detail: isContractMismatch
            ? `클라이언트 응답 계약 검증 실패: ${err.message}`
            : (err?.message || '네트워크 오류가 발생했습니다.'),
        });
      }
    } finally {
      setCommitmentLoading(false);
    }
  };

  return (
    <div style={{ padding: '24px', maxWidth: '1400px', margin: '0 auto', display: 'flex', flexDirection: 'column', gap: '20px' }}>
      {/* Honest Notice: Backend Lineage & Evaluation Scores Not Exposed via HTTP */}
      <div
        data-testid="lineage-unexposed-notice"
        role="status"
        style={{
          padding: '14px 18px',
          borderRadius: '8px',
          backgroundColor: 'rgba(234, 179, 8, 0.12)',
          border: '1px solid #eab308',
          color: '#fde047',
          fontSize: '0.8125rem',
          lineHeight: 1.5,
        }}
      >
        <div>
          <strong>⚠️ 모델 계보 및 평가 점수 미노출 (백엔드 HTTP API 부재) ℹ️ [제품 기능 미제공]:</strong> 실제 계보 데이터는 saintvision 내부 서비스(services/lineage.py)에만 존재하며 외부 HTTP 서빙 엔드포인트가 제공되지 않습니다.
        </div>
        <div style={{ marginTop: '4px', fontSize: '0.75rem', color: '#fed7aa' }}>
          의사결정 왜곡을 방지하기 위해 가짜 계보 및 평가 점수(Accuracy/F1)의 합성을 전면 차단하고 미노출 상태를 유지합니다. (엔드포인트 신설: Codex 레인 인계)
        </div>
      </div>

      {/* Top MLOps & AC-10 Metrics Banner */}
      <div
        style={{
          display: 'grid',
          gridTemplateColumns: 'repeat(auto-fit, minmax(260px, 1fr))',
          gap: '16px',
        }}
      >
        <div style={{ backgroundColor: '#161b22', border: '1px solid #30363d', borderRadius: '8px', padding: '16px 20px' }}>
          <div style={{ fontSize: '12px', color: '#8b949e', fontWeight: 600 }}>Provider 계약 동일성 (AC-10 / G-03)</div>
          <div
            data-testid="conformance-top-status"
            style={{
              fontSize: '18px',
              fontWeight: 700,
              color: conformanceError
                ? '#ff7b72'
                : conformanceData
                ? conformanceData.status === 'RECORDED'
                  ? '#58a6ff'
                  : '#f0883e'
                : '#8b949e',
              marginTop: '4px',
            }}
          >
            {conformanceError
              ? '조회 실패'
              : conformanceData
              ? conformanceData.status === 'RECORDED'
                ? '기록됨 (RECORDED)'
                : `미측정 (${conformanceData.status})`
              : '미측정 (미조회)'}
          </div>
          <div data-testid="conformance-top-subtext" style={{ fontSize: '12px', color: '#8b949e', marginTop: '4px' }}>
            {conformanceError
              ? '어댑터 conformance 조회 실패'
              : conformanceData
              ? conformanceData.status === 'RECORDED'
                ? `${conformanceData.records.length}/${conformanceData.adapters.length} 어댑터 기록 · fixture-adapter 측정 (${conformanceData.scope})`
                : `${conformanceData.checks.length}개 정본 체크 항목 미측정 (${conformanceData.scope})`
              : '실제 conformance API (G-03 1단계) 연동 대기'}
          </div>
        </div>

        <div style={{ backgroundColor: '#161b22', border: '1px solid #30363d', borderRadius: '8px', padding: '16px 20px' }}>
          <div style={{ fontSize: '12px', color: '#8b949e', fontWeight: 600 }}>End-to-End 모델 계보 역추적</div>
          <div style={{ fontSize: '20px', fontWeight: 700, color: lineages.length > 0 ? '#3fb950' : '#f59e0b', marginTop: '4px' }}>
            {lineages.length > 0 ? '추적 가능' : '미노출 (API 부재)'}
          </div>
          <div style={{ fontSize: '12px', color: '#8b949e', marginTop: '4px' }}>
            {lineages.length > 0 ? 'Dataset → Commit → Run → Eval → Approval' : '서버 계보 앵커 부재 · 신설 대기'}
          </div>
        </div>

        <div style={{ backgroundColor: '#161b22', border: '1px solid #30363d', borderRadius: '8px', padding: '16px 20px' }}>
          <div style={{ fontSize: '12px', color: '#8b949e', fontWeight: 600 }}>프로덕션 배포 게이트 기준</div>
          <div style={{ fontSize: '20px', fontWeight: 700, color: '#58a6ff', marginTop: '4px' }}>
            Accuracy ≥ 85.0%
          </div>
          <div style={{ fontSize: '12px', color: '#8b949e', marginTop: '4px' }}>
            {lineages.length > 0 ? '2인 승인 ID 필수 충족 (모의 게이트)' : '평가 점수 부재로 게이트 대기'}
          </div>
        </div>

        <div style={{ backgroundColor: '#161b22', border: '1px solid #30363d', borderRadius: '8px', padding: '16px 20px' }}>
          <div style={{ fontSize: '12px', color: '#8b949e', fontWeight: 600 }}>등록 모델 수</div>
          <div style={{ fontSize: '24px', fontWeight: 700, color: '#f0f6fc', marginTop: '4px' }}>
            {lineages.length} 개 모델 {lineages.length === 0 && <span style={{ fontSize: '14px', color: '#f59e0b' }}>(미노출)</span>}
          </div>
          <div style={{ fontSize: '12px', color: '#8b949e', marginTop: '4px' }}>
            {lineages.filter((m) => m.status === 'deployed').length}개 Deployed, {lineages.filter((m) => m.status === 'staging').length}개 Staging
          </div>
        </div>
      </div>

      {/* Action Notification Banner */}
      {actionNotice && (
        <div
          role={actionNotice.type === 'error' ? 'alert' : 'status'}
          data-testid={`lineage-action-${actionNotice.type}-banner`}
          style={{
            padding: '12px 18px',
            borderRadius: '6px',
            fontSize: '13px',
            fontWeight: 500,
            backgroundColor: actionNotice.type === 'error' ? 'rgba(248, 81, 73, 0.15)' : 'rgba(46, 160, 67, 0.15)',
            border: `1px solid ${actionNotice.type === 'error' ? '#f85149' : '#3fb950'}`,
            color: actionNotice.type === 'error' ? '#f85149' : '#3fb950',
          }}
        >
          {actionNotice.text}
        </div>
      )}

      {/* Reverse Lineage Query Search Bar */}
      <div
        style={{
          backgroundColor: '#161b22',
          border: '1px solid #30363d',
          borderRadius: '8px',
          padding: '16px 20px',
          display: 'flex',
          flexDirection: 'column',
          gap: '12px',
        }}
      >
        <div>
          <h3 style={{ margin: 0, fontSize: '15px', color: '#f0f6fc' }}>
            계보 역추적 검색 (Reverse Lineage Query — AC-10)
          </h3>
          <p style={{ margin: '4px 0 0 0', fontSize: '12px', color: '#8b949e' }}>
            배포 다이제스트(sha256:...), Git 커밋 SHA, 데이터셋 해시(dset_sha256...)로 역추적하여 픽스처 계보를 검색합니다.
          </p>
        </div>

        <form onSubmit={handleSearch} style={{ display: 'flex', gap: '10px' }}>
          <input
            type="text"
            data-testid="lineage-search-input"
            placeholder="Search by commit SHA (58cabd3...), deployment digest (sha256:...), dataset hash (dset_sha256...), or model name..."
            value={searchQuery}
            onChange={(e) => setSearchQuery(e.target.value)}
            style={{
              flex: 1,
              padding: '8px 12px',
              backgroundColor: '#0d1117',
              border: '1px solid #30363d',
              borderRadius: '6px',
              color: '#c9d1d9',
              fontSize: '13px',
              fontFamily: 'var(--font-mono, monospace)',
            }}
          />
          <Button size="sm" variant="primary" type="submit" data-testid="lineage-search-btn">
            역추적 질의 (Query)
          </Button>
        </form>
      </div>

      {/* Model Selection Tabs or Empty State */}
      {lineages.length === 0 ? (
        <div
          data-testid="lineage-empty-state"
          role="status"
          style={{
            backgroundColor: '#161b22',
            border: '1px solid #30363d',
            borderRadius: '8px',
            padding: '48px 24px',
            textAlign: 'center',
            color: '#94a3b8',
          }}
        >
          <div style={{ fontSize: '2rem', marginBottom: '12px' }}>📊</div>
          <h3 style={{ margin: '0 0 8px 0', fontSize: '1rem', color: '#f0f6fc' }}>
            등록된 모델 계보 및 평가 점수 데이터가 없습니다.
          </h3>
          <p style={{ margin: 0, fontSize: '0.8125rem', color: '#8b949e', maxWidth: '600px', display: 'inline-block' }}>
            현재 백엔드(saintvision)의 모델 계보 데이터는 내부 서비스에만 위치하며 클라이언트 조회용 HTTP 엔드포인트가 부재합니다. 신뢰할 수 없는 가짜 평가 점수(Accuracy/F1)의 임의 합성을 차단하기 위해 미노출로 표시합니다.
          </p>
        </div>
      ) : (
        <>
          {/* Model Selection Tabs */}
          <div style={{ display: 'flex', gap: '10px' }}>
            {lineages.map((model) => {
              const isSelected = model.modelId === selectedModelId;
              return (
                <button
                  key={model.modelId}
                  type="button"
                  onClick={() => handleSelectModel(model.modelId)}
                  style={{
                    padding: '8px 16px',
                    borderRadius: '6px',
                    border: isSelected ? '1px solid #58a6ff' : '1px solid #30363d',
                    backgroundColor: isSelected ? '#1f242c' : '#161b22',
                    color: isSelected ? '#58a6ff' : '#c9d1d9',
                    cursor: 'pointer',
                    fontWeight: isSelected ? 600 : 400,
                    fontSize: '13px',
                  }}
                >
                  {model.modelName} (v{model.version})
                </button>
              );
            })}
          </div>

          {/* End-to-End Lineage Provenance Flow Graph */}
          {selectedModel && (
            <div
              style={{
                backgroundColor: '#161b22',
                border: '1px solid #30363d',
                borderRadius: '8px',
                padding: '24px',
                display: 'flex',
                flexDirection: 'column',
                gap: '20px',
              }}
            >
              <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
                <div>
                  <h3 style={{ margin: 0, fontSize: '16px', color: '#f0f6fc' }}>
                    [{selectedModel.modelName}] End-to-End 계보 추적 그래프
                  </h3>
                  <span style={{ fontSize: '12px', color: '#8b949e' }}>
                    Model ID: <code>{selectedModel.modelId}</code> • Status: <strong>{selectedModel.status.toUpperCase()}</strong>
                  </span>
                </div>

                {selectedModel.status === 'staging' && (
                  <div style={{ display: 'flex', alignItems: 'center', gap: '8px' }}>
                    <input
                      type="text"
                      data-testid="approval-input"
                      value={approvalInput}
                      onChange={(e) => setApprovalInput(e.target.value)}
                      placeholder="승인 식별자 입력 (apr_...)"
                      style={{
                        padding: '6px 10px',
                        backgroundColor: '#0d1117',
                        border: '1px solid #30363d',
                        borderRadius: '4px',
                        color: '#c9d1d9',
                        fontSize: '12px',
                        fontFamily: 'var(--font-mono, monospace)',
                      }}
                    />
                    <Button
                      size="sm"
                      variant="primary"
                      data-testid="lineage-deploy-btn"
                      disabled={!approvalInput.trim()}
                      aria-disabled={!approvalInput.trim()}
                      aria-describedby={!approvalInput.trim() ? 'approval-input-user-action-notice' : undefined}
                      title={!approvalInput.trim() ? '승인 번호(approvalId)를 입력해야 배포할 수 있습니다 (사용자 조치 필요).' : '게이트 배포 시도'}
                      onClick={() => handleDeploy(selectedModel.modelId)}
                    >
                      게이트 배포 시도
                    </Button>
                    {!approvalInput.trim() && (
                      <span
                        id="approval-input-user-action-notice"
                        role="alert"
                        data-testid="approval-input-user-action-notice"
                        style={{ fontSize: '11px', color: '#fed7aa', marginLeft: '4px' }}
                      >
                        👉 <strong>[사용자 조치 필요]</strong>: 승인 번호(apr_...)를 입력해야 배포 시도가 활성화됩니다.
                      </span>
                    )}
                  </div>
                )}
              </div>

              {/* Horizontal Lineage Pipeline Nodes */}
              <div
                style={{
                  display: 'grid',
                  gridTemplateColumns: 'repeat(6, 1fr)',
                  gap: '12px',
                }}
              >
                {/* Node 1: Dataset Digest */}
                <div style={{ backgroundColor: '#0d1117', border: '1px solid #30363d', borderRadius: '6px', padding: '12px' }}>
                  <div style={{ fontSize: '11px', color: '#8b949e', fontWeight: 600 }}>1. DATASET DIGEST</div>
                  <div style={{ fontSize: '12px', color: '#58a6ff', fontFamily: 'var(--font-mono, monospace)', marginTop: '6px' }}>
                    {selectedModel.datasetDigest ? selectedModel.datasetDigest.slice(0, 16) + '...' : '미지정'}
                  </div>
                  <div style={{ fontSize: '11px', color: selectedModel.datasetDigest ? '#3fb950' : '#8b949e', marginTop: '4px' }}>
                    {selectedModel.datasetDigest ? 'SHA-256 (모의 표기)' : '미검증'}
                  </div>
                </div>

                {/* Node 2: Source Git Commit */}
                <div style={{ backgroundColor: '#0d1117', border: '1px solid #30363d', borderRadius: '6px', padding: '12px' }}>
                  <div style={{ fontSize: '11px', color: '#8b949e', fontWeight: 600 }}>2. SOURCE COMMIT</div>
                  <div style={{ fontSize: '12px', color: '#58a6ff', fontFamily: 'var(--font-mono, monospace)', marginTop: '6px' }}>
                    {selectedModel.sourceCommitSha ? selectedModel.sourceCommitSha.slice(0, 12) : '미지정'}
                  </div>
                  <div style={{ fontSize: '11px', color: '#8b949e', marginTop: '4px' }}>
                    {selectedModel.sourceCommitSha ? 'Git Signed SHA (모의 표기)' : '커밋 없음'}
                  </div>
                </div>

                {/* Node 3: Training Run ID */}
                <div style={{ backgroundColor: '#0d1117', border: '1px solid #30363d', borderRadius: '6px', padding: '12px' }}>
                  <div style={{ fontSize: '11px', color: '#8b949e', fontWeight: 600 }}>3. TRAINING RUN</div>
                  <div style={{ fontSize: '12px', color: '#f0f6fc', fontFamily: 'var(--font-mono, monospace)', marginTop: '6px' }}>
                    {selectedModel.trainingRunId || '미실행'}
                  </div>
                  <div style={{ fontSize: '11px', color: '#8b949e', marginTop: '4px' }}>Isolated Runtime (모의)</div>
                </div>

                {/* Node 4: Evaluation Score */}
                <div style={{ backgroundColor: '#0d1117', border: '1px solid #30363d', borderRadius: '6px', padding: '12px' }}>
                  <div style={{ fontSize: '11px', color: '#8b949e', fontWeight: 600 }}>4. EVALUATION (모의 점수)</div>
                  <div style={{ fontSize: '14px', color: selectedModel.evalAccuracy !== undefined && selectedModel.evalAccuracy >= 0.85 ? '#3fb950' : '#f85149', fontWeight: 700, marginTop: '4px' }}>
                    Acc: {selectedModel.evalAccuracy !== undefined ? (selectedModel.evalAccuracy * 100).toFixed(1) + '%' : '미평가'}
                  </div>
                  <div style={{ fontSize: '11px', color: '#8b949e', marginTop: '2px' }}>
                    F1 Score: {selectedModel.evalF1Score !== undefined ? selectedModel.evalF1Score.toFixed(3) : 'N/A'}
                  </div>
                </div>

                {/* Node 5: Governance Approval */}
                <div style={{ backgroundColor: '#0d1117', border: '1px solid #30363d', borderRadius: '6px', padding: '12px' }}>
                  <div style={{ fontSize: '11px', color: '#8b949e', fontWeight: 600 }}>5. APPROVAL</div>
                  <div style={{ fontSize: '12px', color: selectedModel.approvalId ? '#3fb950' : '#8b949e', fontFamily: 'var(--font-mono, monospace)', marginTop: '6px' }}>
                    {selectedModel.approvalId ? selectedModel.approvalId : 'None (Pending)'}
                  </div>
                  <div style={{ fontSize: '11px', color: '#8b949e', marginTop: '4px' }}>Two-Person Rule (모의)</div>
                </div>

                {/* Node 6: Deployment Digest (Simulated) */}
                <div style={{ backgroundColor: '#0d1117', border: '1px solid #30363d', borderRadius: '6px', padding: '12px' }}>
                  <div style={{ fontSize: '11px', color: '#8b949e', fontWeight: 600 }}>6. DEPLOYMENT DIGEST (모의 시뮬레이션)</div>
                  <div style={{ fontSize: '12px', color: selectedModel.deploymentDigest ? '#58a6ff' : '#8b949e', fontFamily: 'var(--font-mono, monospace)', marginTop: '6px' }}>
                    {selectedModel.deploymentDigest ? selectedModel.deploymentDigest.slice(0, 16) + '...' : 'Not deployed'}
                  </div>
                  <div style={{ fontSize: '11px', color: selectedModel.deploymentDigest ? '#e3b341' : '#8b949e', marginTop: '4px' }}>
                    {selectedModel.deploymentDigest ? '모의 배포 완료 (백엔드 digest 고정과 무관 · 실 환경 미배포)' : 'Pending Gate'}
                  </div>
                </div>
              </div>
            </div>
          )}
        </>
      )}

      {/* Real Multi-LLM Provider Adapter Conformance Panel (G-03 Phase 1: GET /v1/projects/{project_id}/adapters/conformance) */}
      <div
        data-testid="adapter-conformance-panel"
        style={{
          backgroundColor: '#161b22',
          border: '1px solid #30363d',
          borderRadius: '8px',
          padding: '20px',
        }}
      >
        <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: '14px' }}>
          <div>
            <h4 style={{ margin: 0, fontSize: '15px', color: '#f0f6fc' }}>
              Multi-LLM Provider Adapter Conformance (G-03 2단계 API 연동)
            </h4>
            <p style={{ margin: '4px 0 0 0', fontSize: '12px', color: '#8b949e' }}>
              컨트롤 플레인 호스트의 실제 어댑터 적합성 상태를 조회합니다. 저장된 기록이 없으면 정직하게 <code style={{ color: '#e3b341' }}>NOT_OBSERVED</code>(미측정)와 정본 체크리스트 규격을, 기록이 있으면 <code style={{ color: '#e3b341' }}>RECORDED</code>와 어댑터별 기록을 반환합니다. 기록의 측정 대상은 설치된 CLI가 아니라 제품 fixture adapter입니다(<code>subject: fixture-adapter</code>).
            </p>
          </div>
        </div>

        {/* Project ID input & Fetch Form */}
        <form
          onSubmit={handleFetchConformance}
          style={{ display: 'flex', gap: '8px', alignItems: 'center', marginBottom: '16px', flexWrap: 'wrap' }}
        >
          <input
            type="text"
            data-testid="conformance-project-input"
            placeholder="Project ID (prj_...)"
            value={conformanceProjectId}
            onChange={(e) => {
              setConformanceProjectId(e.target.value);
              setConformanceData(null);
              setConformanceError(null);
              singleConformanceAbortRef.current?.abort();
              ++singleConformanceGenRef.current;
              setSingleConformanceLoading(false);
              setSingleConformanceData(null);
              setSingleConformanceError(null);
            }}
            style={{
              padding: '6px 10px',
              backgroundColor: '#0d1117',
              border: '1px solid #30363d',
              borderRadius: '6px',
              color: '#c9d1d9',
              fontSize: '13px',
              fontFamily: 'var(--font-mono, monospace)',
              minWidth: '220px',
            }}
          />
          <Button
            size="sm"
            variant="primary"
            type="submit"
            data-testid="conformance-fetch-btn"
            disabled={conformanceLoading || !conformanceProjectId.trim()}
          >
            {conformanceLoading ? '조회 중...' : 'Conformance 조회'}
          </Button>
        </form>

        {/* Permanent Live Region for Conformance Status Announcements (WAI-ARIA a11y, F1 lesson) */}
        <div
          data-testid="conformance-live-status"
          role="status"
          aria-live="polite"
          style={
            conformanceLoading || conformanceError || conformanceData
              ? {
                  padding: '10px 14px',
                  borderRadius: '6px',
                  fontSize: '13px',
                  fontWeight: 500,
                  marginBottom: '14px',
                  backgroundColor: conformanceLoading
                    ? 'rgba(56, 139, 253, 0.15)'
                    : conformanceError
                    ? 'rgba(248, 81, 73, 0.15)'
                    : 'rgba(240, 136, 62, 0.15)',
                  border: `1px solid ${
                    conformanceLoading
                      ? '#58a6ff'
                      : conformanceError
                      ? '#ff7b72'
                      : '#f0883e'
                  }`,
                  color: conformanceLoading
                    ? '#58a6ff'
                    : conformanceError
                    ? '#ff7b72'
                    : '#f0883e',
                }
              : undefined
          }
        >
          {conformanceLoading && '⏳ 어댑터 Conformance 상태 조회 중...'}
          {conformanceError && '❌ 어댑터 Conformance 조회 실패'}
          {!conformanceLoading &&
            !conformanceError &&
            conformanceData &&
            (conformanceData.status === 'RECORDED'
              ? `ℹ️ 어댑터 Conformance 조회 완료: 기록됨(RECORDED) (${conformanceData.records.length}개 어댑터 기록 · fixture-adapter 측정)`
              : `ℹ️ 어댑터 Conformance 조회 완료: 미측정(NOT_OBSERVED) (${conformanceData.checks.length}개 정본 체크 항목)`)}
        </div>

        {/* Explicit Role Alert Error Banner on ProblemDetails (401, 403, 404) */}
        {conformanceError && (
          <div
            role="alert"
            data-testid="conformance-error-banner"
            style={{
              padding: '10px 14px',
              borderRadius: '6px',
              fontSize: '13px',
              backgroundColor: 'rgba(248, 81, 73, 0.15)',
              border: '1px solid #ff7b72',
              color: '#ff7b72',
              marginBottom: '14px',
            }}
          >
            ❌ {conformanceError.code && conformanceError.status ? `[${conformanceError.code}] (${conformanceError.status}) ${conformanceError.title ? `${conformanceError.title}: ` : ''}` : ''}{conformanceError.detail}
          </div>
        )}

        {/* Initial Unmeasured Guidance Notice */}
        {!conformanceData && !conformanceError && !conformanceLoading && (
          <div
            data-testid="conformance-unmeasured-notice"
            style={{
              padding: '12px 14px',
              borderRadius: '6px',
              backgroundColor: '#0d1117',
              border: '1px solid #30363d',
              color: '#8b949e',
              fontSize: '13px',
              lineHeight: '1.5',
            }}
          >
            ℹ️ <strong style={{ color: '#f0883e' }}>미측정 (미조회)</strong>: 실제 컨트롤 플레인 HTTP 엔드포인트(<code>GET /v1/projects/:projectId/adapters/conformance</code>)를 호출하여 정본 체크리스트 규격 상태를 조회합니다. 프로젝트 ID를 입력하고 조회 버튼을 누르십시오.
          </div>
        )}

        {/* Conformance Observation Results Container */}
        {conformanceData && (
          <div
            data-testid="conformance-result-container"
            style={{
              display: 'flex',
              flexDirection: 'column',
              gap: '16px',
            }}
          >
            {/* Metadata Summary Grid */}
            <div
              style={{
                backgroundColor: '#0d1117',
                border: '1px solid #30363d',
                borderRadius: '6px',
                padding: '16px',
                display: 'grid',
                gridTemplateColumns: 'repeat(auto-fit, minmax(220px, 1fr))',
                gap: '12px',
                fontSize: '13px',
              }}
            >
              <div>
                <span style={{ color: '#8b949e', fontSize: '11px', display: 'block' }}>CONFORMANCE STATUS</span>
                <span
                  data-testid="conformance-status-badge"
                  style={{
                    display: 'inline-block',
                    marginTop: '4px',
                    padding: '2px 8px',
                    borderRadius: '4px',
                    fontSize: '11px',
                    fontWeight: 700,
                    backgroundColor: conformanceData.status === 'RECORDED' ? 'rgba(56, 139, 253, 0.15)' : 'rgba(240, 136, 62, 0.15)',
                    color: conformanceData.status === 'RECORDED' ? '#58a6ff' : '#f0883e',
                  }}
                >
                  {conformanceData.status === 'RECORDED' ? '기록됨 (RECORDED)' : `미측정 (${conformanceData.status})`}
                </span>
              </div>
              <div>
                <span style={{ color: '#8b949e', fontSize: '11px', display: 'block' }}>SCOPE</span>
                <code data-testid="conformance-scope" style={{ color: '#58a6ff' }}>
                  {conformanceData.scope}
                </code>
              </div>
              <div>
                <span style={{ color: '#8b949e', fontSize: '11px', display: 'block' }}>CONTRACT VERSION</span>
                <span data-testid="conformance-contract-version" style={{ color: '#c9d1d9', fontFamily: 'var(--font-mono, monospace)' }}>
                  {conformanceData.contractVersion}
                </span>
              </div>
              <div>
                <span style={{ color: '#8b949e', fontSize: '11px', display: 'block' }}>TARGET ADAPTERS</span>
                <span data-testid="conformance-adapters" style={{ color: '#f0f6fc' }}>
                  {conformanceData.adapters.join(', ')}
                </span>
              </div>
              <div>
                <span style={{ color: '#8b949e', fontSize: '11px', display: 'block' }}>
                  {conformanceData.status === 'RECORDED' ? 'LATEST RECORDED AT' : 'RECORDED AT'}
                </span>
                <span data-testid="conformance-recorded-at" style={{ color: '#8b949e' }}>
                  {conformanceData.status === 'RECORDED' ? conformanceData.latestRecordedAt : 'null (미측정)'}
                </span>
              </div>
              {conformanceData.status === 'NOT_OBSERVED' ? (
                <div style={{ gridColumn: '1 / -1' }}>
                  <span style={{ color: '#8b949e', fontSize: '11px', display: 'block' }}>REASON</span>
                  <span data-testid="conformance-reason" style={{ color: '#c9d1d9' }}>
                    {conformanceData.reason}
                  </span>
                </div>
              ) : (
                <div style={{ gridColumn: '1 / -1' }}>
                  <span style={{ color: '#8b949e', fontSize: '11px', display: 'block' }}>SUBJECT</span>
                  <span data-testid="conformance-subject-note" style={{ color: '#c9d1d9' }}>
                    fixture-adapter · in-server — 제품 fixture adapter에 대한 suite 실행 기록이며 설치된 CLI의 적합성이 아닙니다. 기록이 없는 어댑터는 목록에 없습니다(미측정).
                  </span>
                </div>
              )}
            </div>

            {/* Records per adapter (RECORDED branch, design #218 v1.2 §4-1) */}
            {conformanceData.status === 'RECORDED' && (
              <div style={{ overflowX: 'auto' }}>
                <div style={{ fontSize: '13px', fontWeight: 600, color: '#f0f6fc', marginBottom: '8px' }}>
                  어댑터별 기록 ({conformanceData.records.length}개 · 서버 응답 동적 렌더링)
                </div>
                <table
                  data-testid="conformance-records-table"
                  style={{ width: '100%', borderCollapse: 'collapse', fontSize: '13px', color: '#c9d1d9' }}
                >
                  <caption style={{ textAlign: 'left', fontSize: '12px', color: '#8b949e', marginBottom: '8px' }}>
                    컨트롤 플레인 호스트의 어댑터별 최신 conformance 기록
                  </caption>
                  <thead>
                    <tr style={{ borderBottom: '1px solid #30363d', textAlign: 'left', color: '#8b949e' }}>
                      <th scope="col" style={{ padding: '8px' }}>Adapter</th>
                      <th scope="col" style={{ padding: '8px' }}>Subject / Provenance</th>
                      <th scope="col" style={{ padding: '8px' }}>Contract / Suite</th>
                      <th scope="col" style={{ padding: '8px' }}>결과 (전체 · 통과 · 실패 · 건너뜀)</th>
                      <th scope="col" style={{ padding: '8px' }}>Recorded At</th>
                      <th scope="col" style={{ padding: '8px' }}>단건 조회</th>
                    </tr>
                  </thead>
                  <tbody>
                    {conformanceData.records.map((record, idx) => (
                      <tr
                        key={`${idx}-${record.adapter}`}
                        data-testid={`conformance-record-row-${idx}`}
                        style={{ borderBottom: '1px solid #21262d' }}
                      >
                        <td style={{ padding: '8px', fontWeight: 600, color: '#f0f6fc', fontFamily: 'var(--font-mono, monospace)' }}>
                          <span data-testid={`conformance-record-adapter-${idx}`}>{record.adapter}</span>
                        </td>
                        <td style={{ padding: '8px' }}>
                          <span data-testid={`conformance-record-subject-${idx}`}>{record.subject}</span>
                          {' / '}
                          <span data-testid={`conformance-record-provenance-${idx}`}>{record.provenance}</span>
                        </td>
                        <td style={{ padding: '8px', fontFamily: 'var(--font-mono, monospace)' }}>
                          {record.contractVersion} / {record.suiteContractVersion}
                        </td>
                        <td style={{ padding: '8px' }}>
                          <span data-testid={`conformance-record-counts-${idx}`}>
                            {`전체 ${record.total} · 통과 ${record.passed} · 실패 ${record.failed} · 건너뜀 ${record.skipped}`}
                          </span>
                        </td>
                        <td style={{ padding: '8px', color: '#8b949e' }}>
                          <span data-testid={`conformance-record-recorded-at-${idx}`}>{record.recordedAt}</span>
                        </td>
                        <td style={{ padding: '8px' }}>
                          <Button
                            size="sm"
                            variant="secondary"
                            disabled={singleConformanceLoading}
                            data-testid={`conformance-inspect-btn-${idx}`}
                            onClick={() => {
                              setSingleAdapterName(record.adapter);
                              handleFetchSingleConformance(undefined, record.adapter);
                            }}
                          >
                            단건 상세 조회
                          </Button>
                        </td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
            )}

            {/* Dynamic Checklist Table from API Response (FE Hardcoding Prohibited) */}
            <div style={{ overflowX: 'auto' }}>
              <div style={{ fontSize: '13px', fontWeight: 600, color: '#f0f6fc', marginBottom: '8px' }}>
                정본 Conformance Checklist ({conformanceData.checks.length}개 항목 · 서버 응답 동적 렌더링)
              </div>
              <table
                data-testid="conformance-checks-table"
                style={{ width: '100%', borderCollapse: 'collapse', fontSize: '13px', color: '#c9d1d9' }}
              >
                <caption style={{ textAlign: 'left', fontSize: '12px', color: '#8b949e', marginBottom: '8px' }}>
                  컨트롤 플레인 호스트 어댑터 Conformance 체크리스트
                </caption>
                <thead>
                  <tr style={{ borderBottom: '1px solid #30363d', textAlign: 'left', color: '#8b949e' }}>
                    <th scope="col" style={{ padding: '8px' }}>#</th>
                    <th scope="col" style={{ padding: '8px' }}>Check Name (CHECKLIST 정본)</th>
                    <th scope="col" style={{ padding: '8px' }}>Capability Gated</th>
                    <th scope="col" style={{ padding: '8px' }}>Status</th>
                  </tr>
                </thead>
                <tbody>
                  {conformanceData.checks.map((check, idx) => (
                    <tr
                      key={`${idx}-${check.name}`}
                      data-testid={`conformance-check-row-${idx}`}
                      style={{ borderBottom: '1px solid #21262d' }}
                    >
                      <td style={{ padding: '8px', color: '#8b949e' }}>{idx + 1}</td>
                      <td style={{ padding: '8px', fontWeight: 600, color: '#f0f6fc', fontFamily: 'var(--font-mono, monospace)' }}>
                        <span data-testid={`conformance-check-name-${idx}`}>{check.name}</span>
                      </td>
                      <td style={{ padding: '8px' }}>
                        <span
                          data-testid={`conformance-check-gated-${idx}`}
                          style={{
                            padding: '2px 6px',
                            borderRadius: '4px',
                            fontSize: '11px',
                            fontWeight: 600,
                            backgroundColor: check.capabilityGated ? 'rgba(56, 139, 253, 0.15)' : 'rgba(160, 168, 178, 0.15)',
                            color: check.capabilityGated ? '#58a6ff' : '#a0a8b2',
                          }}
                        >
                          {check.capabilityGated ? 'Capability Gated' : 'Standard'}
                        </span>
                      </td>
                      <td style={{ padding: '8px' }}>
                        <span
                          data-testid={`conformance-check-status-${idx}`}
                          style={{
                            padding: '2px 8px',
                            borderRadius: '4px',
                            fontSize: '11px',
                            fontWeight: 600,
                            backgroundColor: conformanceData.status === 'RECORDED' ? 'rgba(56, 139, 253, 0.15)' : 'rgba(240, 136, 62, 0.15)',
                            color: conformanceData.status === 'RECORDED' ? '#58a6ff' : '#f0883e',
                          }}
                        >
                          {conformanceData.status === 'RECORDED'
                            ? outcomeSummary(conformanceData.records, check.name)
                            : 'NOT_OBSERVED (미측정)'}
                        </span>
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          </div>
        )}

        {/* Single Adapter Conformance Observation Section (GET /v1/projects/:projectId/adapters/:name/conformance) */}
        <div
          data-testid="single-adapter-conformance-section"
          style={{
            marginTop: '24px',
            paddingTop: '20px',
            borderTop: '1px solid #30363d',
            display: 'flex',
            flexDirection: 'column',
            gap: '14px',
          }}
        >
          <div>
            <h5 style={{ margin: 0, fontSize: '14px', color: '#f0f6fc' }}>
              단건 어댑터 Conformance 조회 (Single Route)
            </h5>
            <p style={{ margin: '4px 0 0 0', fontSize: '12px', color: '#8b949e' }}>
              엔드포인트 <code>GET /v1/projects/:projectId/adapters/:name/conformance</code>를 통해 개별 어댑터의 정본 체크리스트 규격 또는 상세 테스트 결과를 조회합니다.
            </p>
          </div>

          <form
            onSubmit={handleFetchSingleConformance}
            style={{ display: 'flex', gap: '8px', alignItems: 'center', flexWrap: 'wrap' }}
          >
            <input
              type="text"
              data-testid="single-conformance-adapter-input"
              aria-label="어댑터 이름"
              placeholder="Adapter Name (e.g. codex-cli)"
              value={singleAdapterName}
              onChange={(e) => {
                setSingleAdapterName(e.target.value);
                singleConformanceAbortRef.current?.abort();
                ++singleConformanceGenRef.current;
                setSingleConformanceLoading(false);
                setSingleConformanceData(null);
                setSingleConformanceError(null);
              }}
              style={{
                padding: '6px 10px',
                backgroundColor: '#0d1117',
                border: '1px solid #30363d',
                borderRadius: '6px',
                color: '#c9d1d9',
                fontSize: '13px',
                fontFamily: 'var(--font-mono, monospace)',
                minWidth: '200px',
              }}
            />
            <Button
              size="sm"
              variant="primary"
              type="submit"
              data-testid="single-conformance-fetch-btn"
              disabled={singleConformanceLoading || !conformanceProjectId.trim() || !singleAdapterName.trim()}
            >
              {singleConformanceLoading ? '조회 중...' : '어댑터 Conformance 조회'}
            </Button>
          </form>

          {/* Live Region for Single Conformance Status Announcements */}
          <div
            data-testid="single-conformance-live-status"
            role="status"
            aria-live="polite"
            style={
              singleConformanceLoading || singleConformanceError || singleConformanceData
                ? {
                    padding: '8px 12px',
                    borderRadius: '6px',
                    fontSize: '12px',
                    fontWeight: 500,
                    backgroundColor: singleConformanceLoading
                      ? 'rgba(56, 139, 253, 0.15)'
                      : singleConformanceError
                      ? 'rgba(248, 81, 73, 0.15)'
                      : 'rgba(240, 136, 62, 0.15)',
                    border: `1px solid ${
                      singleConformanceLoading
                        ? '#58a6ff'
                        : singleConformanceError
                        ? '#ff7b72'
                        : '#f0883e'
                    }`,
                    color: singleConformanceLoading
                      ? '#58a6ff'
                      : singleConformanceError
                      ? '#ff7b72'
                      : '#f0883e',
                  }
                : undefined
            }
          >
            {singleConformanceLoading && '⏳ 단건 어댑터 Conformance 상태 조회 중...'}
            {singleConformanceError && '❌ 단건 어댑터 Conformance 조회 실패'}
            {!singleConformanceLoading &&
              !singleConformanceError &&
              singleConformanceData &&
              (singleConformanceData.status === 'RECORDED'
                ? `ℹ️ [${singleConformanceData.adapter}] 조회 완료: 기록됨(RECORDED) (총 ${singleConformanceData.total}개 테스트 완료)`
                : `ℹ️ [${singleConformanceData.adapter}] 조회 완료: 미측정(NOT_OBSERVED) (${singleConformanceData.checks.length}개 정본 체크 항목)`)}
          </div>

          {/* Single Conformance Error Banner on ProblemDetails (401, 403, 404 RES-0004, 500 SYS-0002, 503 SYS-0001) */}
          {singleConformanceError && (
            <div
              role="alert"
              data-testid="single-conformance-error-banner"
              style={{
                padding: '10px 14px',
                borderRadius: '6px',
                fontSize: '13px',
                backgroundColor: 'rgba(248, 81, 73, 0.15)',
                border: '1px solid #ff7b72',
                color: '#ff7b72',
                display: 'flex',
                alignItems: 'center',
                justifyContent: 'space-between',
                flexWrap: 'wrap',
                gap: '8px',
              }}
            >
              <div>
                ❌ {singleConformanceError.code && singleConformanceError.status
                  ? `[${singleConformanceError.code}] (${singleConformanceError.status}) `
                  : ''}
                {singleConformanceError.detail}
                {singleConformanceError.retryable === false && (
                  <span style={{ marginLeft: '8px', fontSize: '11px', color: '#8b949e' }}>
                    (재시도 불가)
                  </span>
                )}
              </div>
              {singleConformanceError.retryable && (
                <Button
                  size="sm"
                  variant="secondary"
                  data-testid="single-conformance-retry-btn"
                  onClick={() => handleFetchSingleConformance()}
                >
                  다시 시도
                </Button>
              )}
            </div>
          )}

          {/* Single Conformance Result Container */}
          {singleConformanceData && (
            <div
              data-testid="single-conformance-result-container"
              style={{
                display: 'flex',
                flexDirection: 'column',
                gap: '14px',
              }}
            >
              {/* Metadata Grid */}
              <div
                style={{
                  backgroundColor: '#0d1117',
                  border: '1px solid #30363d',
                  borderRadius: '6px',
                  padding: '14px',
                  display: 'grid',
                  gridTemplateColumns: 'repeat(auto-fit, minmax(200px, 1fr))',
                  gap: '10px',
                  fontSize: '13px',
                }}
              >
                <div>
                  <span style={{ color: '#8b949e', fontSize: '11px', display: 'block' }}>CONFORMANCE STATUS</span>
                  <span
                    data-testid="single-conformance-status-badge"
                    style={{
                      display: 'inline-block',
                      marginTop: '4px',
                      padding: '2px 8px',
                      borderRadius: '4px',
                      fontSize: '11px',
                      fontWeight: 700,
                      backgroundColor:
                        singleConformanceData.status === 'RECORDED'
                          ? 'rgba(56, 139, 253, 0.15)'
                          : 'rgba(240, 136, 62, 0.15)',
                      color: singleConformanceData.status === 'RECORDED' ? '#58a6ff' : '#f0883e',
                    }}
                  >
                    {singleConformanceData.status === 'RECORDED' ? '기록됨 (RECORDED)' : `미측정 (${singleConformanceData.status})`}
                  </span>
                </div>
                <div>
                  <span style={{ color: '#8b949e', fontSize: '11px', display: 'block' }}>ADAPTER</span>
                  <code data-testid="single-conformance-adapter" style={{ color: '#f0f6fc', fontWeight: 600 }}>
                    {singleConformanceData.adapter}
                  </code>
                </div>
                <div>
                  <span style={{ color: '#8b949e', fontSize: '11px', display: 'block' }}>SCOPE</span>
                  <code data-testid="single-conformance-scope" style={{ color: '#58a6ff' }}>
                    {singleConformanceData.scope}
                  </code>
                </div>
                <div>
                  <span style={{ color: '#8b949e', fontSize: '11px', display: 'block' }}>CONTRACT VERSION</span>
                  <span data-testid="single-conformance-contract-version" style={{ color: '#c9d1d9', fontFamily: 'var(--font-mono, monospace)' }}>
                    {singleConformanceData.contractVersion}
                  </span>
                </div>

                {singleConformanceData.status === 'NOT_OBSERVED' ? (
                  <>
                    <div>
                      <span style={{ color: '#8b949e', fontSize: '11px', display: 'block' }}>RECORDED AT</span>
                      <span data-testid="single-conformance-recorded-at" style={{ color: '#8b949e' }}>
                        null (미측정)
                      </span>
                    </div>
                    <div style={{ gridColumn: '1 / -1' }}>
                      <span style={{ color: '#8b949e', fontSize: '11px', display: 'block' }}>REASON</span>
                      <span data-testid="single-conformance-reason" style={{ color: '#c9d1d9' }}>
                        {singleConformanceData.reason}
                      </span>
                    </div>
                  </>
                ) : (
                  <>
                    <div>
                      <span style={{ color: '#8b949e', fontSize: '11px', display: 'block' }}>SUBJECT / PROVENANCE</span>
                      <span data-testid="single-conformance-subject" style={{ color: '#c9d1d9' }}>
                        {singleConformanceData.subject} / {singleConformanceData.provenance}
                      </span>
                    </div>
                    <div>
                      <span style={{ color: '#8b949e', fontSize: '11px', display: 'block' }}>SUITE CONTRACT VERSION</span>
                      <span data-testid="single-conformance-suite-contract-version" style={{ color: '#c9d1d9', fontFamily: 'var(--font-mono, monospace)' }}>
                        {singleConformanceData.suiteContractVersion}
                      </span>
                    </div>
                    <div>
                      <span style={{ color: '#8b949e', fontSize: '11px', display: 'block' }}>RESULTS</span>
                      <span data-testid="single-conformance-counts" style={{ color: '#f0f6fc', fontWeight: 600 }}>
                        {`전체 ${singleConformanceData.total} · 통과 ${singleConformanceData.passed} · 실패 ${singleConformanceData.failed} · 건너뜀 ${singleConformanceData.skipped}`}
                      </span>
                    </div>
                    <div>
                      <span style={{ color: '#8b949e', fontSize: '11px', display: 'block' }}>RECORDED AT</span>
                      <span data-testid="single-conformance-recorded-at" style={{ color: '#8b949e' }}>
                        {singleConformanceData.recordedAt}
                      </span>
                    </div>
                    <div style={{ gridColumn: '1 / -1' }}>
                      <span style={{ color: '#8b949e', fontSize: '11px', display: 'block' }}>SUBJECT NOTE</span>
                      <span data-testid="single-conformance-subject-note" style={{ color: '#c9d1d9' }}>
                        fixture-adapter · in-server — 제품 fixture adapter에 대한 suite 실행 기록이며 설치된 CLI의 적합성이 아닙니다.
                      </span>
                    </div>
                  </>
                )}
              </div>

              {/* When NOT_OBSERVED: Render Checks Descriptors */}
              {singleConformanceData.status === 'NOT_OBSERVED' && (
                <div style={{ overflowX: 'auto' }}>
                  <div style={{ fontSize: '13px', fontWeight: 600, color: '#f0f6fc', marginBottom: '8px' }}>
                    정본 Conformance Checklist ({singleConformanceData.checks.length}개 항목)
                  </div>
                  <table
                    data-testid="single-conformance-checks-table"
                    style={{ width: '100%', borderCollapse: 'collapse', fontSize: '13px', color: '#c9d1d9' }}
                  >
                    <thead>
                      <tr style={{ borderBottom: '1px solid #30363d', textAlign: 'left', color: '#8b949e' }}>
                        <th scope="col" style={{ padding: '8px' }}>#</th>
                        <th scope="col" style={{ padding: '8px' }}>Check Name</th>
                        <th scope="col" style={{ padding: '8px' }}>Capability Gated</th>
                      </tr>
                    </thead>
                    <tbody>
                      {singleConformanceData.checks.map((check, idx) => (
                        <tr
                          key={`${idx}-${check.name}`}
                          data-testid={`single-conformance-check-row-${idx}`}
                          style={{ borderBottom: '1px solid #21262d' }}
                        >
                          <td style={{ padding: '8px', color: '#8b949e' }}>{idx + 1}</td>
                          <td style={{ padding: '8px', fontWeight: 600, color: '#f0f6fc', fontFamily: 'var(--font-mono, monospace)' }}>
                            <span data-testid={`single-conformance-check-name-${idx}`}>{check.name}</span>
                          </td>
                          <td style={{ padding: '8px' }}>
                            <span
                              data-testid={`single-conformance-check-gated-${idx}`}
                              style={{
                                padding: '2px 6px',
                                borderRadius: '4px',
                                fontSize: '11px',
                                fontWeight: 600,
                                backgroundColor: check.capabilityGated ? 'rgba(56, 139, 253, 0.15)' : 'rgba(160, 168, 178, 0.15)',
                                color: check.capabilityGated ? '#58a6ff' : '#a0a8b2',
                              }}
                            >
                              {check.capabilityGated ? 'Capability Gated' : 'Standard'}
                            </span>
                          </td>
                        </tr>
                      ))}
                    </tbody>
                  </table>
                </div>
              )}

              {/* When RECORDED: Render Detailed Outcomes */}
              {singleConformanceData.status === 'RECORDED' && (
                <div style={{ overflowX: 'auto' }}>
                  <div style={{ fontSize: '13px', fontWeight: 600, color: '#f0f6fc', marginBottom: '8px' }}>
                    상세 체크 결과 ({singleConformanceData.outcomes.length}개 항목)
                  </div>
                  <table
                    data-testid="single-conformance-outcomes-table"
                    style={{ width: '100%', borderCollapse: 'collapse', fontSize: '13px', color: '#c9d1d9' }}
                  >
                    <thead>
                      <tr style={{ borderBottom: '1px solid #30363d', textAlign: 'left', color: '#8b949e' }}>
                        <th scope="col" style={{ padding: '8px' }}>#</th>
                        <th scope="col" style={{ padding: '8px' }}>Check Name</th>
                        <th scope="col" style={{ padding: '8px' }}>Status</th>
                      </tr>
                    </thead>
                    <tbody>
                      {singleConformanceData.outcomes.map((outcome, idx) => (
                        <tr
                          key={`${idx}-${outcome.name}`}
                          data-testid={`single-conformance-outcome-row-${idx}`}
                          style={{ borderBottom: '1px solid #21262d' }}
                        >
                          <td style={{ padding: '8px', color: '#8b949e' }}>{idx + 1}</td>
                          <td style={{ padding: '8px', fontWeight: 600, color: '#f0f6fc', fontFamily: 'var(--font-mono, monospace)' }}>
                            <span data-testid={`single-conformance-outcome-name-${idx}`}>{outcome.name}</span>
                          </td>
                          <td style={{ padding: '8px' }}>
                            <span
                              data-testid={`single-conformance-outcome-status-${idx}`}
                              style={{
                                padding: '2px 8px',
                                borderRadius: '4px',
                                fontSize: '11px',
                                fontWeight: 600,
                                backgroundColor: outcome.skipped
                                  ? 'rgba(139, 148, 158, 0.15)'
                                  : outcome.passed
                                  ? 'rgba(56, 139, 253, 0.15)'
                                  : 'rgba(248, 81, 73, 0.15)',
                                color: outcome.skipped ? '#8b949e' : outcome.passed ? '#58a6ff' : '#ff7b72',
                              }}
                            >
                              {outcome.skipped ? '건너뜀 (Skipped)' : outcome.passed ? '통과 (Passed)' : '실패 (Failed)'}
                            </span>
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
      </div>

      {/* Real Model Commitment Observation Panel (Control-Plane GET /v1/.../commitment) */}
      <div
        data-testid="model-commitment-panel"
        style={{
          backgroundColor: '#161b22',
          border: '1px solid #30363d',
          borderRadius: '8px',
          padding: '20px',
          display: 'flex',
          flexDirection: 'column',
          gap: '14px',
        }}
      >
        <div>
          <h4 style={{ margin: 0, fontSize: '15px', color: '#f0f6fc' }}>
            실제 모델 Commitment 조회 (Control-Plane HTTP API)
          </h4>
          <p style={{ margin: '4px 0 0 0', fontSize: '12px', color: '#8b949e' }}>
            백엔드 엔드포인트 <code>GET /v1/projects/:project/models/:model_id/versions/:version/commitment</code>로부터 정본 manifestHash와 sourceRunId를 조회합니다.
          </p>
        </div>

        <form onSubmit={handleFetchCommitment} style={{ display: 'flex', flexWrap: 'wrap', gap: '10px', alignItems: 'center' }}>
          <input
            type="text"
            data-testid="commitment-project-input"
            placeholder="Project ID (prj_...)"
            value={commitmentProject}
            onChange={(e) => setCommitmentProject(e.target.value)}
            style={{
              padding: '6px 10px',
              backgroundColor: '#0d1117',
              border: '1px solid #30363d',
              borderRadius: '6px',
              color: '#c9d1d9',
              fontSize: '13px',
              fontFamily: 'var(--font-mono, monospace)',
              minWidth: '180px',
            }}
          />
          <input
            type="text"
            data-testid="commitment-model-input"
            placeholder="Model ID (mdl_...)"
            value={commitmentModelId}
            onChange={(e) => setCommitmentModelId(e.target.value)}
            style={{
              padding: '6px 10px',
              backgroundColor: '#0d1117',
              border: '1px solid #30363d',
              borderRadius: '6px',
              color: '#c9d1d9',
              fontSize: '13px',
              fontFamily: 'var(--font-mono, monospace)',
              minWidth: '180px',
            }}
          />
          <input
            type="text"
            data-testid="commitment-version-input"
            placeholder="Version (예: 1.0.0)"
            value={commitmentVersion}
            onChange={(e) => setCommitmentVersion(e.target.value)}
            style={{
              padding: '6px 10px',
              backgroundColor: '#0d1117',
              border: '1px solid #30363d',
              borderRadius: '6px',
              color: '#c9d1d9',
              fontSize: '13px',
              fontFamily: 'var(--font-mono, monospace)',
              minWidth: '120px',
            }}
          />
          <Button
            size="sm"
            variant="primary"
            type="submit"
            data-testid="commitment-fetch-btn"
            disabled={commitmentLoading || !commitmentProject.trim() || !commitmentModelId.trim() || !commitmentVersion.trim()}
          >
            {commitmentLoading ? '조회 중...' : 'Commitment 조회'}
          </Button>
        </form>

        {commitmentError && (
          <div
            role="alert"
            data-testid="commitment-error-banner"
            style={{
              padding: '10px 14px',
              borderRadius: '6px',
              fontSize: '13px',
              backgroundColor: 'rgba(248, 81, 73, 0.15)',
              border: '1px solid #f85149',
              color: '#f85149',
            }}
          >
            ❌ {commitmentError.code && commitmentError.status ? `[${commitmentError.code}] (${commitmentError.status}) ${commitmentError.title ? `${commitmentError.title}: ` : ''}` : ''}{commitmentError.detail}
          </div>
        )}

        {commitmentData && (
          <div
            data-testid="commitment-result-container"
            style={{
              backgroundColor: '#0d1117',
              border: '1px solid #30363d',
              borderRadius: '6px',
              padding: '16px',
              display: 'grid',
              gridTemplateColumns: 'repeat(auto-fit, minmax(220px, 1fr))',
              gap: '12px',
              fontSize: '13px',
            }}
          >
            <div>
              <span style={{ color: '#8b949e', fontSize: '11px', display: 'block' }}>MANIFEST HASH</span>
              <code data-testid="commitment-manifest-hash" style={{ color: '#58a6ff', wordBreak: 'break-all' }}>
                {commitmentData.manifestHash}
              </code>
            </div>
            <div>
              <span style={{ color: '#8b949e', fontSize: '11px', display: 'block' }}>SOURCE RUN ID</span>
              <code data-testid="commitment-source-run-id" style={{ color: '#f0f6fc', wordBreak: 'break-all' }}>
                {commitmentData.sourceRunId}
              </code>
            </div>
            <div>
              <span style={{ color: '#8b949e', fontSize: '11px', display: 'block' }}>COMMITTED AT</span>
              <span data-testid="commitment-committed-at" style={{ color: '#c9d1d9' }}>
                {commitmentData.committedAt}
              </span>
            </div>
            <div>
              <span style={{ color: '#8b949e', fontSize: '11px', display: 'block' }}>RECOVERY EPOCH</span>
              <span data-testid="commitment-recovery-epoch" style={{ color: '#c9d1d9' }}>
                {commitmentData.commitRecoveryEpoch}
              </span>
            </div>
            <div>
              <span style={{ color: '#8b949e', fontSize: '11px', display: 'block' }}>CURRENT AVAILABILITY</span>
              <code data-testid="commitment-availability" style={{ color: '#f59e0b' }}>
                {commitmentData.currentAvailability}
              </code>
            </div>
            <div>
              <span style={{ color: '#8b949e', fontSize: '11px', display: 'block' }}>EXECUTION REVALIDATION</span>
              <span data-testid="commitment-revalidation" style={{ color: '#f0f6fc' }}>
                {commitmentData.requiresExecutionRevalidation ? 'Required (true)' : 'False'}
              </span>
            </div>
            <div>
              <span style={{ color: '#8b949e', fontSize: '11px', display: 'block' }}>FORMAT / TOTAL BYTES</span>
              <span data-testid="commitment-format-bytes" style={{ color: '#c9d1d9' }}>
                {commitmentData.format} ({commitmentData.totalBytes.toLocaleString()} bytes)
              </span>
            </div>
            <div>
              <span style={{ color: '#8b949e', fontSize: '11px', display: 'block' }}>SHARD COUNT</span>
              <span data-testid="commitment-shard-count" style={{ color: '#c9d1d9' }}>
                {commitmentData.shardCount} shard(s)
              </span>
            </div>
          </div>
        )}
      </div>
    </div>
  );
};
