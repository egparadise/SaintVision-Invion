import React, { useState, useEffect } from 'react';
import { ModelLineage, ModelCommitObservation, ConformanceStatusResponse } from '@/contracts/types';
import { Button } from '@/shared/ui/Button';
import { fetchModelCommitment } from '@/shared/api/modelCommitmentObservation';
import { fetchConformanceStatus } from '@/shared/api/adapterObservation';
import { MlopsManager } from './mlopsEngine';

export interface ModelLineageViewProps {
  initialLineages?: ModelLineage[];
  currentProjectId?: string;
  initialConformance?: ConformanceStatusResponse;
}

export const ModelLineageView: React.FC<ModelLineageViewProps> = ({
  initialLineages = [],
  currentProjectId,
  initialConformance,
}) => {
  const [mlopsManager] = useState<MlopsManager>(() => new MlopsManager(initialLineages));
  const [lineages, setLineages] = useState<ModelLineage[]>(mlopsManager.getLineages());
  const [selectedModelId, setSelectedModelId] = useState<string>(lineages[0]?.modelId || '');
  const [searchQuery, setSearchQuery] = useState('');
  const [approvalInput, setApprovalInput] = useState('');
  const [actionNotice, setActionNotice] = useState<{ type: 'success' | 'error'; text: string } | null>(null);

  // Adapter conformance observation state (G-03 Phase 1)
  const [conformanceProjectId, setConformanceProjectId] = useState(currentProjectId || '');
  const [conformanceData, setConformanceData] = useState<ConformanceStatusResponse | null>(
    () => initialConformance || null
  );
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
        setConformanceError({
          code: prob.code,
          status: prob.status,
          title: prob.title,
          detail: prob.detail || '요청이 거절되었습니다.',
        });
      } else {
        const isContractMismatch = err?.message && err.message.includes('계약 불일치');
        setConformanceError({
          detail: isContractMismatch
            ? `클라이언트 응답 계약 검증 실패: ${err.message}`
            : (err?.message || '네트워크 오류가 발생했습니다.'),
        });
      }
    } finally {
      setConformanceLoading(false);
    }
  };

  useEffect(() => {
    if (currentProjectId?.trim() && !initialConformance) {
      setConformanceProjectId(currentProjectId.trim());
      fetchConformanceStatus(currentProjectId.trim())
        .then((data) => setConformanceData(data))
        .catch((err) => {
          const prob = err?.problem;
          if (prob) {
            setConformanceError({
              code: prob.code,
              status: prob.status,
              title: prob.title,
              detail: prob.detail || '요청이 거절되었습니다.',
            });
          } else {
            setConformanceError({ detail: err?.message || '오류가 발생했습니다.' });
          }
        });
    }
  }, [currentProjectId]);

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
            style={{ fontSize: '18px', fontWeight: 700, color: '#e3b341', marginTop: '4px' }}
          >
            {conformanceData ? `미측정 (${conformanceData.status})` : '미측정 (NOT_OBSERVED)'}
          </div>
          <div data-testid="conformance-top-subtext" style={{ fontSize: '12px', color: '#8b949e', marginTop: '4px' }}>
            {conformanceData
              ? `${conformanceData.checks.length}개 정본 체크 항목 미측정 (${conformanceData.scope})`
              : '실제 conformance API (G-03 1단계) 연동'}
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
              Multi-LLM Provider Adapter Conformance (G-03 1단계 API 연동)
            </h4>
            <p style={{ margin: '4px 0 0 0', fontSize: '12px', color: '#8b949e' }}>
              컨트롤 플레인 호스트의 실제 어댑터 적합성 상태를 조회합니다. 1단계는 저장된 결과가 없어 정직하게 <code style={{ color: '#e3b341' }}>NOT_OBSERVED</code>(미측정) 및 15개 정본 체크리스트 규격을 반환합니다.
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
            onChange={(e) => setConformanceProjectId(e.target.value)}
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
          {conformanceError &&
            `❌ ${conformanceError.code && conformanceError.status ? `[${conformanceError.code}] (${conformanceError.status}) ${conformanceError.title ? `${conformanceError.title}: ` : ''}` : ''}${conformanceError.detail}`}
          {!conformanceLoading &&
            !conformanceError &&
            conformanceData &&
            `ℹ️ 어댑터 Conformance 관측 완료: ${conformanceData.status} (${conformanceData.checks.length}개 정본 체크 항목)`}
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
            ℹ️ <strong style={{ color: '#f0883e' }}>미측정 (NOT_OBSERVED)</strong>: 실제 컨트롤 플레인 HTTP 엔드포인트(<code>GET /v1/projects/:projectId/adapters/conformance</code>)를 호출하여 15개 정본 체크리스트 규격 상태를 조회합니다. 프로젝트 ID를 입력하고 조회 버튼을 누르십시오.
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
                    backgroundColor: 'rgba(240, 136, 62, 0.15)',
                    color: '#f0883e',
                  }}
                >
                  미측정 ({conformanceData.status})
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
                <span style={{ color: '#8b949e', fontSize: '11px', display: 'block' }}>RECORDED AT</span>
                <span data-testid="conformance-recorded-at" style={{ color: '#8b949e' }}>
                  {conformanceData.recordedAt === null ? 'null (미측정)' : String(conformanceData.recordedAt)}
                </span>
              </div>
              <div style={{ gridColumn: '1 / -1' }}>
                <span style={{ color: '#8b949e', fontSize: '11px', display: 'block' }}>REASON</span>
                <span data-testid="conformance-reason" style={{ color: '#c9d1d9' }}>
                  {conformanceData.reason}
                </span>
              </div>
            </div>

            {/* Dynamic Checklist Table from API Response (FE Hardcoding Prohibited) */}
            <div style={{ overflowX: 'auto' }}>
              <div style={{ fontSize: '13px', fontWeight: 600, color: '#f0f6fc', marginBottom: '8px' }}>
                정본 Conformance Checklist ({conformanceData.checks.length}개 항목 · 서버 응답 동적 렌더링)
              </div>
              <table
                data-testid="conformance-checks-table"
                style={{ width: '100%', borderCollapse: 'collapse', fontSize: '13px', color: '#c9d1d9' }}
              >
                <thead>
                  <tr style={{ borderBottom: '1px solid #30363d', textAlign: 'left', color: '#8b949e' }}>
                    <th style={{ padding: '8px' }}>#</th>
                    <th style={{ padding: '8px' }}>Check Name (CHECKLIST 정본)</th>
                    <th style={{ padding: '8px' }}>Capability Gated</th>
                    <th style={{ padding: '8px' }}>Status</th>
                  </tr>
                </thead>
                <tbody>
                  {conformanceData.checks.map((check, idx) => (
                    <tr
                      key={check.name}
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
                            backgroundColor: check.capabilityGated ? 'rgba(56, 139, 253, 0.15)' : 'rgba(139, 148, 158, 0.15)',
                            color: check.capabilityGated ? '#58a6ff' : '#8b949e',
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
                            backgroundColor: 'rgba(240, 136, 62, 0.15)',
                            color: '#f0883e',
                          }}
                        >
                          NOT_OBSERVED (미측정)
                        </span>
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          </div>
        )}
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
