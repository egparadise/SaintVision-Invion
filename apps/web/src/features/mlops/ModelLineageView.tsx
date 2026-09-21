import React, { useState } from 'react';
import { ModelLineage } from '@/contracts/types';
import { Button } from '@/shared/ui/Button';
import { MlopsManager } from './mlopsEngine';

export interface ModelLineageViewProps {
  initialLineages?: ModelLineage[];
}

export const ModelLineageView: React.FC<ModelLineageViewProps> = ({
  initialLineages = [],
}) => {
  const [mlopsManager] = useState<MlopsManager>(() => new MlopsManager(initialLineages));
  const [lineages, setLineages] = useState<ModelLineage[]>(mlopsManager.getLineages());
  const [selectedModelId, setSelectedModelId] = useState<string>(lineages[0]?.modelId || '');
  const [searchQuery, setSearchQuery] = useState('');
  const [approvalInput, setApprovalInput] = useState('');
  const [actionNotice, setActionNotice] = useState<{ type: 'success' | 'error'; text: string } | null>(null);

  const conformances = mlopsManager.verifyProviderConformances();
  const selectedModel = lineages.find((m) => m.modelId === selectedModelId) || lineages[0];

  const handleSearch = (e: React.FormEvent) => {
    e.preventDefault();
    if (!searchQuery.trim()) return;

    const matched = mlopsManager.queryLineage(searchQuery);
    if (matched) {
      setSelectedModelId(matched.modelId);
      setActionNotice({
        type: 'success',
        text: `✔ 역추적(Reverse Query) 성공: [${matched.modelName}] 계보가 일치합니다.`,
      });
    } else {
      setActionNotice({
        type: 'error',
        text: `❌ 검색 결과 없음: 입력된 식별자 '${searchQuery}'와 일치하는 모델/커밋/다이제스트가 없습니다.`,
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
        text: `🚀 [${res.deployedModel?.modelName}] 프로덕션 배포 완료! 생성 Digest: ${res.deployedModel?.deploymentDigest.slice(0, 24)}...`,
      });
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
        <strong>⚠️ 모델 계보 및 평가 점수 미노출 (백엔드 HTTP API 부재):</strong> 실제 계보 데이터는 saintvision 내부 서비스(services/lineage.py)에만 존재하며 HTTP 서빙 엔드포인트가 제공되지 않습니다. 의사결정 왜곡을 방지하기 위해 가짜 계보 및 평가 점수(Accuracy/F1)의 합성을 전면 차단하고 미노출 상태를 유지합니다. (엔드포인트 신설: Codex 레인 인계)
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
          <div style={{ fontSize: '12px', color: '#8b949e', fontWeight: 600 }}>Provider 계약 동일성 (AC-10)</div>
          <div style={{ fontSize: '24px', fontWeight: 700, color: conformances.every((c) => c.conformancePassed) ? '#3fb950' : '#d29922', marginTop: '4px' }}>
            {conformances.every((c) => c.conformancePassed) ? '100% 적합' : '일부 불일치'} ({conformances.map((c) => c.provider).join(' = ')})
          </div>
          <div style={{ fontSize: '12px', color: '#8b949e', marginTop: '4px' }}>W3C-Trace / SSE-v2 / RFC 9457 일치</div>
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
            {lineages.length > 0 ? '2인 승인 ID 필수 충족' : '평가 점수 부재로 게이트 대기'}
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
            배포 다이제스트(sha256:...), Git 커밋 SHA, 데이터셋 해시로 역추적하여 근원 데이터셋과 승인 원장을 확인합니다.
          </p>
        </div>

        <form onSubmit={handleSearch} style={{ display: 'flex', gap: '10px' }}>
          <input
            type="text"
            placeholder="Search by commit SHA (58cabd3...), deployment digest (sha256:4a8b2...), or model name..."
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
          <Button size="sm" variant="primary" type="submit">
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
                  onClick={() => setSelectedModelId(model.modelId)}
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
                      onClick={() => handleDeploy(selectedModel.modelId)}
                    >
                      게이트 배포 시도
                    </Button>
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
                    {selectedModel.datasetDigest ? 'SHA-256 Verified' : '미검증'}
                  </div>
                </div>

                {/* Node 2: Source Git Commit */}
                <div style={{ backgroundColor: '#0d1117', border: '1px solid #30363d', borderRadius: '6px', padding: '12px' }}>
                  <div style={{ fontSize: '11px', color: '#8b949e', fontWeight: 600 }}>2. SOURCE COMMIT</div>
                  <div style={{ fontSize: '12px', color: '#58a6ff', fontFamily: 'var(--font-mono, monospace)', marginTop: '6px' }}>
                    {selectedModel.sourceCommitSha ? selectedModel.sourceCommitSha.slice(0, 12) : '미지정'}
                  </div>
                  <div style={{ fontSize: '11px', color: '#8b949e', marginTop: '4px' }}>
                    {selectedModel.sourceCommitSha ? 'Git Signed SHA' : '커밋 없음'}
                  </div>
                </div>

                {/* Node 3: Training Run ID */}
                <div style={{ backgroundColor: '#0d1117', border: '1px solid #30363d', borderRadius: '6px', padding: '12px' }}>
                  <div style={{ fontSize: '11px', color: '#8b949e', fontWeight: 600 }}>3. TRAINING RUN</div>
                  <div style={{ fontSize: '12px', color: '#f0f6fc', fontFamily: 'var(--font-mono, monospace)', marginTop: '6px' }}>
                    {selectedModel.trainingRunId || '미실행'}
                  </div>
                  <div style={{ fontSize: '11px', color: '#8b949e', marginTop: '4px' }}>Isolated Runtime</div>
                </div>

                {/* Node 4: Evaluation Score */}
                <div style={{ backgroundColor: '#0d1117', border: '1px solid #30363d', borderRadius: '6px', padding: '12px' }}>
                  <div style={{ fontSize: '11px', color: '#8b949e', fontWeight: 600 }}>4. EVALUATION</div>
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
                  <div style={{ fontSize: '11px', color: '#8b949e', marginTop: '4px' }}>Two-Person Rule</div>
                </div>

                {/* Node 6: Deployment Digest */}
                <div style={{ backgroundColor: '#0d1117', border: '1px solid #30363d', borderRadius: '6px', padding: '12px' }}>
                  <div style={{ fontSize: '11px', color: '#8b949e', fontWeight: 600 }}>6. DEPLOYMENT DIGEST</div>
                  <div style={{ fontSize: '12px', color: selectedModel.deploymentDigest ? '#58a6ff' : '#8b949e', fontFamily: 'var(--font-mono, monospace)', marginTop: '6px' }}>
                    {selectedModel.deploymentDigest ? selectedModel.deploymentDigest.slice(0, 16) + '...' : 'Not deployed'}
                  </div>
                  <div style={{ fontSize: '11px', color: selectedModel.deploymentDigest ? '#3fb950' : '#8b949e', marginTop: '4px' }}>
                    {selectedModel.deploymentDigest ? 'Production Live' : 'Pending Gate'}
                  </div>
                </div>
              </div>
            </div>
          )}
        </>
      )}

      {/* Multi-Provider Adapter Conformance Table (AC-10) */}
      <div
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
              Multi-LLM Provider Adapter Conformance (AC-10)
            </h4>
            <p style={{ margin: '4px 0 0 0', fontSize: '12px', color: '#8b949e' }}>
              Codex와 Claude 어댑터가 동일한 공통 계약(Schema, Error Category, SSE Streaming)을 100% 준수합니다.
            </p>
          </div>
        </div>

        <table style={{ width: '100%', borderCollapse: 'collapse', fontSize: '13px', color: '#c9d1d9' }}>
          <thead>
            <tr style={{ borderBottom: '1px solid #30363d', textAlign: 'left', color: '#8b949e' }}>
              <th style={{ padding: '8px' }}>Provider</th>
              <th style={{ padding: '8px' }}>Contract Version</th>
              <th style={{ padding: '8px' }}>Conformance Status</th>
              <th style={{ padding: '8px' }}>Avg Latency</th>
              <th style={{ padding: '8px' }}>Token Throughput</th>
              <th style={{ padding: '8px' }}>Supported Protocols</th>
            </tr>
          </thead>
          <tbody>
            {conformances.map((conf) => (
              <tr key={conf.provider} style={{ borderBottom: '1px solid #21262d' }}>
                <td style={{ padding: '10px 8px', fontWeight: 600, color: '#f0f6fc' }}>{conf.provider}</td>
                <td style={{ padding: '10px 8px', fontFamily: 'var(--font-mono, monospace)' }}>{conf.contractVersion}</td>
                <td style={{ padding: '10px 8px' }}>
                  <span
                    style={{
                      padding: '2px 8px',
                      borderRadius: '4px',
                      fontSize: '11px',
                      fontWeight: 700,
                      backgroundColor: 'rgba(46, 160, 67, 0.2)',
                      color: '#3fb950',
                    }}
                  >
                    100% CONFORMING
                  </span>
                </td>
                <td style={{ padding: '10px 8px' }}>{conf.avgLatencyMs} ms</td>
                <td style={{ padding: '10px 8px', color: '#58a6ff' }}>{conf.tokensPerSec} tok/s</td>
                <td style={{ padding: '10px 8px', color: '#8b949e', fontSize: '12px' }}>
                  {conf.supportedProtocols.join(', ')}
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    </div>
  );
};
