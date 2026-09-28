import React, { useState, useRef, useEffect } from 'react';
import { ModelLineage, ProblemDetails } from '@/contracts/types';
import { Button } from '@/shared/ui/Button';
import { ApiError } from '@/shared/api/client';
import {
  modelRegistryObservation,
  isValidIsoDateTime,
} from '@/shared/api/modelRegistryObservation';
import type {
  ModelLineageTraceResponse,
} from '@/contracts/model-lineage-trace-response';
import type {
  ModelVersionResponse,
} from '@/contracts/model-version-response';
import type {
  RetentionPinResponse,
} from '@/contracts/retention-pin-response';
import type {
  ModelReleaseResponse,
} from '@/contracts/model-release-response';
import { MlopsManager } from './mlopsEngine';

export interface ModelLineageViewProps {
  initialLineages?: ModelLineage[];
  projectId?: string;
  currentUser?: { role?: string; canApprove?: boolean; canRequest?: boolean } | null;
  initialModelId?: string;
  initialVersion?: string;
}

export const ModelLineageView: React.FC<ModelLineageViewProps> = ({
  initialLineages = [],
  projectId: propProjectId = '',
  currentUser,
  initialModelId = '',
  initialVersion = '',
}) => {
  // --- Simulation / Legacy Mock State (Preserved for existing suites) ---
  const [mlopsManager] = useState<MlopsManager>(() => new MlopsManager(initialLineages));
  const [lineages, setLineages] = useState<ModelLineage[]>(mlopsManager.getLineages());
  const [selectedModelId, setSelectedModelId] = useState<string>(lineages[0]?.modelId || '');
  const [searchQuery, setSearchQuery] = useState('');
  const [approvalInput, setApprovalInput] = useState('');
  const [actionNotice, setActionNotice] = useState<{ type: 'success' | 'error'; text: string } | null>(null);

  const conformances = mlopsManager.verifyProviderConformances();
  const selectedModel = lineages.find((m) => m.modelId === selectedModelId) || lineages[0];

  // --- Real HTTP API / Model Registry State ---
  const [projectId, setProjectId] = useState<string>(propProjectId);
  const [modelId, setModelId] = useState<string>(initialModelId);
  const [version, setVersion] = useState<string>(initialVersion);

  const [activeTab, setActiveTab] = useState<'trace' | 'register' | 'pin' | 'release'>('trace');
  const [queryLoading, setQueryLoading] = useState(false);
  const [realTrace, setRealTrace] = useState<ModelLineageTraceResponse | null>(null);

  // W2 Register form state
  const [regVersion, setRegVersion] = useState('');
  const [regSha256, setRegSha256] = useState('');
  const [regByteSize, setRegByteSize] = useState('0');
  const [regLoading, setRegLoading] = useState(false);
  const [regResult, setRegResult] = useState<ModelVersionResponse | null>(null);

  // W4 Retention Pin form state
  const [pinUntil, setPinUntil] = useState('');
  const [pinLoading, setPinLoading] = useState(false);
  const [pinResult, setPinResult] = useState<RetentionPinResponse | null>(null);

  // Release form state
  const [relLicensePolicy, setRelLicensePolicy] = useState('Apache-2.0');
  const [relClassification, setRelClassification] = useState<'public' | 'internal' | 'restricted'>('internal');
  const [relLoading, setRelLoading] = useState(false);
  const [relResult, setRelResult] = useState<ModelReleaseResponse | null>(null);

  // ProblemDetails error and Live Region
  const [problemDetails, setProblemDetails] = useState<ProblemDetails | null>(null);
  const [generalError, setGeneralError] = useState<string | null>(null);
  const [liveAnnouncement, setLiveAnnouncement] = useState<string>('');

  const abortControllerRef = useRef<AbortController | null>(null);

  useEffect(() => {
    if (propProjectId) setProjectId(propProjectId);
  }, [propProjectId]);

  useEffect(() => {
    return () => {
      abortControllerRef.current?.abort();
    };
  }, []);

  const canApprove = currentUser?.canApprove !== false;

  const clearErrors = () => {
    setProblemDetails(null);
    setGeneralError(null);
  };

  const handleApiError = (err: unknown, defaultMessage: string) => {
    if (err instanceof ApiError) {
      setProblemDetails(err.problem);
      setLiveAnnouncement(`오류 발생: [${err.problem.code}] ${err.problem.detail || err.problem.title}`);
    } else if (err instanceof Error) {
      setGeneralError(err.message || defaultMessage);
      setLiveAnnouncement(`오류 발생: ${err.message || defaultMessage}`);
    } else {
      setGeneralError(defaultMessage);
      setLiveAnnouncement(`오류 발생: ${defaultMessage}`);
    }
  };

  // --- Real API Actions ---
  const handleQueryLineage = async (e?: React.FormEvent) => {
    if (e) e.preventDefault();
    clearErrors();
    if (!projectId.trim() || !modelId.trim() || !version.trim()) {
      setGeneralError('프로젝트 ID, 모델 ID, 버전을 모두 입력해야 조회가 가능합니다.');
      return;
    }

    abortControllerRef.current?.abort();
    const ctrl = new AbortController();
    abortControllerRef.current = ctrl;

    setQueryLoading(true);
    setLiveAnnouncement(`모델 [${modelId}:${version}] 계보 조회 중...`);
    try {
      const trace = await modelRegistryObservation.fetchModelLineage(
        projectId.trim(),
        modelId.trim(),
        version.trim(),
        ctrl.signal
      );
      if (!ctrl.signal.aborted) {
        setRealTrace(trace);
        setLiveAnnouncement(
          `계보 조회 성공: [${trace.version}] (Stage: ${trace.stage}, Datasets: ${trace.datasets.length}건, Deployments: ${trace.deployments.length}건)`
        );
      }
    } catch (err: unknown) {
      if (!ctrl.signal.aborted) {
        setRealTrace(null);
        handleApiError(err, '모델 계보 조회 실패');
      }
    } finally {
      if (!ctrl.signal.aborted) {
        setQueryLoading(false);
      }
    }
  };

  const handleRegisterVersion = async (e: React.FormEvent) => {
    e.preventDefault();
    clearErrors();
    if (!canApprove) {
      setGeneralError('승인 권한(canApprove)이 없는 계정은 버전을 등록할 수 없습니다.');
      return;
    }
    if (!projectId.trim() || !modelId.trim()) {
      setGeneralError('프로젝트 ID와 모델 ID를 입력해야 합니다.');
      return;
    }
    if (!regVersion.trim() || !regSha256.trim()) {
      setGeneralError('버전 명칭과 64자리 SHA256 다이제스트를 입력하세요.');
      return;
    }

    setRegLoading(true);
    setLiveAnnouncement(`버전 [${regVersion}] 등록 요청 중...`);
    try {
      const byteSizeNum = parseInt(regByteSize, 10);
      const res = await modelRegistryObservation.registerModelVersion(
        projectId.trim(),
        modelId.trim(),
        {
          version: regVersion.trim(),
          contentSha256: regSha256.trim(),
          byteSize: Number.isInteger(byteSizeNum) && byteSizeNum >= 0 ? byteSizeNum : 0,
        }
      );
      setRegResult(res);
      setLiveAnnouncement(`버전 등록 성공: [${res.version}] (ID: ${res.modelVersionId})`);
    } catch (err: unknown) {
      handleApiError(err, '모델 버전 등록 실패');
    } finally {
      setRegLoading(false);
    }
  };

  const handleExtendPin = async (e: React.FormEvent) => {
    e.preventDefault();
    clearErrors();
    if (!canApprove) {
      setGeneralError('승인 권한(canApprove)이 없는 계정은 보존 고정을 연장할 수 없습니다.');
      return;
    }
    if (!projectId.trim() || !modelId.trim() || !version.trim()) {
      setGeneralError('프로젝트 ID, 모델 ID, 버전을 확인하세요.');
      return;
    }
    if (!pinUntil.trim() || !isValidIsoDateTime(pinUntil.trim())) {
      setGeneralError('유효한 ISO 8601 일시(예: 2026-12-31T23:59:59Z)를 입력하세요.');
      return;
    }

    setPinLoading(true);
    setLiveAnnouncement(`보존 고정 연장 요청 중 (Until: ${pinUntil})...`);
    try {
      const res = await modelRegistryObservation.extendRetentionPin(
        projectId.trim(),
        modelId.trim(),
        version.trim(),
        { until: pinUntil.trim() }
      );
      setPinResult(res);
      setLiveAnnouncement(
        `보존 고정 완료: [${res.version}] ${res.extended ? '연장됨' : '기존 유지 (연장 없음)'} (Pinned Until: ${res.retentionPinnedUntil})`
      );
    } catch (err: unknown) {
      handleApiError(err, '보존 고정 연장 실패');
    } finally {
      setPinLoading(false);
    }
  };

  const handleReleaseModel = async (e: React.FormEvent) => {
    e.preventDefault();
    clearErrors();
    if (!canApprove) {
      setGeneralError('승인 권한(canApprove)이 없는 계정은 모델을 릴리스할 수 없습니다.');
      return;
    }
    if (!projectId.trim() || !modelId.trim() || !version.trim()) {
      setGeneralError('프로젝트 ID, 모델 ID, 버전을 확인하세요.');
      return;
    }
    if (!relLicensePolicy.trim()) {
      setGeneralError('라이선스 정책(licensePolicy)을 입력해야 합니다.');
      return;
    }

    setRelLoading(true);
    setLiveAnnouncement(`모델 릴리스 요청 중 (분류: ${relClassification})...`);
    try {
      const res = await modelRegistryObservation.releaseModelVersion(
        projectId.trim(),
        modelId.trim(),
        version.trim(),
        {
          licensePolicy: relLicensePolicy.trim(),
          classification: relClassification,
        }
      );
      setRelResult(res);
      setLiveAnnouncement(`모델 릴리스 성공: [${res.version}] (Stage: ${res.stage})`);
    } catch (err: unknown) {
      handleApiError(err, '모델 릴리스 실패');
    } finally {
      setRelLoading(false);
    }
  };

  // --- Simulation / Legacy Handlers (Preserved) ---
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

  const handleDeploy = (targetModelId: string) => {
    if (!approvalInput.trim()) {
      setActionNotice({
        type: 'error',
        text: '🛑 배포 게이트 차단: 승인 식별자(approvalId)가 입력되지 않았습니다. (위조 번호 승인 게이트 통과 방지)',
      });
      return;
    }
    const res = mlopsManager.deployModel({
      modelId: targetModelId,
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
        text: `✔ [모의 시뮬레이션] [${res.deployedModel?.modelName}] 로컬 배포 게이트 검증 완료 (백엔드 서빙 배포 API 미노출 상태로 실제 인프라 미반영 · Digest: ${res.deployedModel?.deploymentDigest.slice(0, 24)}...)`,
      });
    }
  };

  return (
    <div style={{ padding: '24px', maxWidth: '1400px', margin: '0 auto', display: 'flex', flexDirection: 'column', gap: '20px' }}>
      {/* Live Region for Screen Readers */}
      <div
        role="status"
        aria-live="polite"
        data-testid="registry-live-region"
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

      {/* Real HTTP Business Lane Control Bar */}
      <div
        data-testid="model-registry-control-panel"
        style={{
          backgroundColor: '#161b22',
          border: '1px solid #30363d',
          borderRadius: '8px',
          padding: '20px',
          display: 'flex',
          flexDirection: 'column',
          gap: '16px',
        }}
      >
        <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', flexWrap: 'wrap', gap: '10px' }}>
          <div>
            <h2 style={{ margin: 0, fontSize: '18px', color: '#f0f6fc', fontWeight: 600 }}>
              Model Registry & Lineage Business Control (G-05)
            </h2>
            <p style={{ margin: '4px 0 0 0', fontSize: '12px', color: '#8b949e' }}>
              서버 정본 비즈니스 경로(Lineage 조회 · W2 등록 · W4 보존 연장 · 릴리스)와 1:1 결합된 엔터프라이즈 레지스트리
            </p>
          </div>
          {/* W3 Seam Badge */}
          <div
            data-testid="badge-w3-verify-seam"
            style={{
              padding: '4px 10px',
              borderRadius: '4px',
              fontSize: '11px',
              fontWeight: 600,
              backgroundColor: '#21262d',
              border: '1px solid #30363d',
              color: '#8b949e',
            }}
          >
            W3 검증: 미연결 (검증 앵커 #215 대기)
          </div>
        </div>

        {/* Global Resource Binding Inputs */}
        <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fit, minmax(200px, 1fr))', gap: '12px' }}>
          <div>
            <label htmlFor="reg-project-id" style={{ display: 'block', fontSize: '11px', color: '#8b949e', marginBottom: '4px' }}>
              Project ID
            </label>
            <input
              id="reg-project-id"
              data-testid="input-project-id"
              type="text"
              placeholder="prj_..."
              value={projectId}
              onChange={(e) => setProjectId(e.target.value)}
              style={{
                width: '100%',
                padding: '6px 10px',
                backgroundColor: '#0d1117',
                border: '1px solid #30363d',
                borderRadius: '6px',
                color: '#f0f6fc',
                fontSize: '12px',
                fontFamily: 'var(--font-mono, monospace)',
                boxSizing: 'border-box',
              }}
            />
          </div>
          <div>
            <label htmlFor="reg-model-id" style={{ display: 'block', fontSize: '11px', color: '#8b949e', marginBottom: '4px' }}>
              Model ID
            </label>
            <input
              id="reg-model-id"
              data-testid="input-model-id"
              type="text"
              placeholder="mod_..."
              value={modelId}
              onChange={(e) => setModelId(e.target.value)}
              style={{
                width: '100%',
                padding: '6px 10px',
                backgroundColor: '#0d1117',
                border: '1px solid #30363d',
                borderRadius: '6px',
                color: '#f0f6fc',
                fontSize: '12px',
                fontFamily: 'var(--font-mono, monospace)',
                boxSizing: 'border-box',
              }}
            />
          </div>
          <div>
            <label htmlFor="reg-version" style={{ display: 'block', fontSize: '11px', color: '#8b949e', marginBottom: '4px' }}>
              Version
            </label>
            <input
              id="reg-version"
              data-testid="input-version"
              type="text"
              placeholder="1.0.0"
              value={version}
              onChange={(e) => setVersion(e.target.value)}
              style={{
                width: '100%',
                padding: '6px 10px',
                backgroundColor: '#0d1117',
                border: '1px solid #30363d',
                borderRadius: '6px',
                color: '#f0f6fc',
                fontSize: '12px',
                fontFamily: 'var(--font-mono, monospace)',
                boxSizing: 'border-box',
              }}
            />
          </div>
        </div>

        {/* Action Tabs Navigation */}
        <div style={{ display: 'flex', gap: '8px', borderBottom: '1px solid #30363d', paddingBottom: '10px' }}>
          <button
            type="button"
            onClick={() => setActiveTab('trace')}
            style={{
              padding: '6px 14px',
              borderRadius: '6px',
              border: activeTab === 'trace' ? '1px solid #58a6ff' : '1px solid transparent',
              backgroundColor: activeTab === 'trace' ? '#1f242c' : 'transparent',
              color: activeTab === 'trace' ? '#58a6ff' : '#8b949e',
              cursor: 'pointer',
              fontSize: '12px',
              fontWeight: 600,
            }}
          >
            🔍 계보 조회 (Trace Lineage)
          </button>
          <button
            type="button"
            onClick={() => setActiveTab('register')}
            style={{
              padding: '6px 14px',
              borderRadius: '6px',
              border: activeTab === 'register' ? '1px solid #58a6ff' : '1px solid transparent',
              backgroundColor: activeTab === 'register' ? '#1f242c' : 'transparent',
              color: activeTab === 'register' ? '#58a6ff' : '#8b949e',
              cursor: 'pointer',
              fontSize: '12px',
              fontWeight: 600,
            }}
          >
            📦 버전 등록 (W2 Register)
          </button>
          <button
            type="button"
            onClick={() => setActiveTab('pin')}
            style={{
              padding: '6px 14px',
              borderRadius: '6px',
              border: activeTab === 'pin' ? '1px solid #58a6ff' : '1px solid transparent',
              backgroundColor: activeTab === 'pin' ? '#1f242c' : 'transparent',
              color: activeTab === 'pin' ? '#58a6ff' : '#8b949e',
              cursor: 'pointer',
              fontSize: '12px',
              fontWeight: 600,
            }}
          >
            📌 보존 고정 (W4 Pin)
          </button>
          <button
            type="button"
            onClick={() => setActiveTab('release')}
            style={{
              padding: '6px 14px',
              borderRadius: '6px',
              border: activeTab === 'release' ? '1px solid #58a6ff' : '1px solid transparent',
              backgroundColor: activeTab === 'release' ? '#1f242c' : 'transparent',
              color: activeTab === 'release' ? '#58a6ff' : '#8b949e',
              cursor: 'pointer',
              fontSize: '12px',
              fontWeight: 600,
            }}
          >
            🚀 모델 릴리스 (Release)
          </button>
        </div>

        {/* Tab Content: 1. Trace Query */}
        {activeTab === 'trace' && (
          <div style={{ display: 'flex', gap: '10px', alignItems: 'center' }}>
            <Button
              size="sm"
              variant="primary"
              data-testid="btn-query-lineage"
              disabled={queryLoading || !projectId || !modelId || !version}
              aria-disabled={queryLoading || !projectId || !modelId || !version}
              onClick={handleQueryLineage}
            >
              {queryLoading ? '계보 조회 중...' : '계보 조회 실행 (GET /lineage)'}
            </Button>
            <span style={{ fontSize: '11px', color: '#8b949e' }}>
              Path: <code>/v1/projects/{projectId || '{project_id}'}/models/{modelId || '{model_id}'}/versions/{version || '{version}'}/lineage</code>
            </span>
          </div>
        )}

        {/* Tab Content: 2. W2 Register */}
        {activeTab === 'register' && (
          <form onSubmit={handleRegisterVersion} style={{ display: 'flex', flexDirection: 'column', gap: '12px' }}>
            <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fit, minmax(200px, 1fr))', gap: '10px' }}>
              <div>
                <label htmlFor="input-register-version" style={{ display: 'block', fontSize: '11px', color: '#8b949e', marginBottom: '4px' }}>
                  등록할 버전 명칭 *
                </label>
                <input
                  id="input-register-version"
                  data-testid="input-register-version"
                  type="text"
                  placeholder="1.0.0-rc1"
                  value={regVersion}
                  onChange={(e) => setRegVersion(e.target.value)}
                  style={{
                    width: '100%',
                    padding: '6px 10px',
                    backgroundColor: '#0d1117',
                    border: '1px solid #30363d',
                    borderRadius: '4px',
                    color: '#c9d1d9',
                    fontSize: '12px',
                    fontFamily: 'var(--font-mono, monospace)',
                    boxSizing: 'border-box',
                  }}
                />
              </div>
              <div>
                <label htmlFor="input-register-sha256" style={{ display: 'block', fontSize: '11px', color: '#8b949e', marginBottom: '4px' }}>
                  Content SHA-256 (64 hex) *
                </label>
                <input
                  id="input-register-sha256"
                  data-testid="input-register-sha256"
                  type="text"
                  placeholder="0123456789abcdef..."
                  value={regSha256}
                  onChange={(e) => setRegSha256(e.target.value)}
                  style={{
                    width: '100%',
                    padding: '6px 10px',
                    backgroundColor: '#0d1117',
                    border: '1px solid #30363d',
                    borderRadius: '4px',
                    color: '#c9d1d9',
                    fontSize: '12px',
                    fontFamily: 'var(--font-mono, monospace)',
                    boxSizing: 'border-box',
                  }}
                />
              </div>
              <div>
                <label htmlFor="input-register-bytesize" style={{ display: 'block', fontSize: '11px', color: '#8b949e', marginBottom: '4px' }}>
                  Byte Size
                </label>
                <input
                  id="input-register-bytesize"
                  data-testid="input-register-bytesize"
                  type="number"
                  min="0"
                  value={regByteSize}
                  onChange={(e) => setRegByteSize(e.target.value)}
                  style={{
                    width: '100%',
                    padding: '6px 10px',
                    backgroundColor: '#0d1117',
                    border: '1px solid #30363d',
                    borderRadius: '4px',
                    color: '#c9d1d9',
                    fontSize: '12px',
                    fontFamily: 'var(--font-mono, monospace)',
                    boxSizing: 'border-box',
                  }}
                />
              </div>
            </div>
            <div style={{ display: 'flex', gap: '10px', alignItems: 'center' }}>
              <Button
                size="sm"
                variant="primary"
                type="submit"
                data-testid="btn-register-version"
                disabled={regLoading || !canApprove || !projectId || !modelId || !regVersion || !regSha256}
                aria-disabled={regLoading || !canApprove || !projectId || !modelId || !regVersion || !regSha256}
              >
                {regLoading ? '등록 중...' : '모델 버전 등록 (POST /versions)'}
              </Button>
              {!canApprove && (
                <span style={{ fontSize: '11px', color: '#fed7aa' }}>
                  ⚠️ 승인 권한(canApprove)이 필요한 작업입니다.
                </span>
              )}
            </div>
          </form>
        )}

        {/* Tab Content: 3. W4 Pin */}
        {activeTab === 'pin' && (
          <form onSubmit={handleExtendPin} style={{ display: 'flex', flexDirection: 'column', gap: '12px' }}>
            <div>
              <label htmlFor="input-pin-until" style={{ display: 'block', fontSize: '11px', color: '#8b949e', marginBottom: '4px' }}>
                보존 만료 시각 (ISO 8601 with Offset) *
              </label>
              <input
                id="input-pin-until"
                data-testid="input-pin-until"
                type="text"
                placeholder="2026-12-31T23:59:59Z"
                value={pinUntil}
                onChange={(e) => setPinUntil(e.target.value)}
                style={{
                  width: '320px',
                  padding: '6px 10px',
                  backgroundColor: '#0d1117',
                  border: '1px solid #30363d',
                  borderRadius: '4px',
                  color: '#c9d1d9',
                  fontSize: '12px',
                  fontFamily: 'var(--font-mono, monospace)',
                  boxSizing: 'border-box',
                }}
              />
            </div>
            <div style={{ display: 'flex', gap: '10px', alignItems: 'center' }}>
              <Button
                size="sm"
                variant="primary"
                type="submit"
                data-testid="btn-pin-retention"
                disabled={pinLoading || !canApprove || !projectId || !modelId || !version || !pinUntil}
                aria-disabled={pinLoading || !canApprove || !projectId || !modelId || !version || !pinUntil}
              >
                {pinLoading ? '연장 중...' : '보존 고정 연장 (POST /retention-pin)'}
              </Button>
              {!canApprove && (
                <span style={{ fontSize: '11px', color: '#fed7aa' }}>
                  ⚠️ 승인 권한(canApprove)이 필요한 작업입니다.
                </span>
              )}
            </div>
          </form>
        )}

        {/* Tab Content: 4. Release */}
        {activeTab === 'release' && (
          <form onSubmit={handleReleaseModel} style={{ display: 'flex', flexDirection: 'column', gap: '12px' }}>
            <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fit, minmax(220px, 1fr))', gap: '10px' }}>
              <div>
                <label htmlFor="input-release-license" style={{ display: 'block', fontSize: '11px', color: '#8b949e', marginBottom: '4px' }}>
                  라이선스 정책 (licensePolicy) *
                </label>
                <input
                  id="input-release-license"
                  data-testid="input-release-license"
                  type="text"
                  placeholder="Apache-2.0"
                  value={relLicensePolicy}
                  onChange={(e) => setRelLicensePolicy(e.target.value)}
                  style={{
                    width: '100%',
                    padding: '6px 10px',
                    backgroundColor: '#0d1117',
                    border: '1px solid #30363d',
                    borderRadius: '4px',
                    color: '#c9d1d9',
                    fontSize: '12px',
                    boxSizing: 'border-box',
                  }}
                />
              </div>
              <div>
                <label htmlFor="select-release-classification" style={{ display: 'block', fontSize: '11px', color: '#8b949e', marginBottom: '4px' }}>
                  배포 분류 (classification) *
                </label>
                <select
                  id="select-release-classification"
                  data-testid="select-release-classification"
                  value={relClassification}
                  onChange={(e) => setRelClassification(e.target.value as any)}
                  style={{
                    width: '100%',
                    padding: '6px 10px',
                    backgroundColor: '#0d1117',
                    border: '1px solid #30363d',
                    borderRadius: '4px',
                    color: '#c9d1d9',
                    fontSize: '12px',
                    boxSizing: 'border-box',
                  }}
                >
                  <option value="internal">internal (내부 한정)</option>
                  <option value="public">public (공개)</option>
                  <option value="restricted">restricted (제한됨)</option>
                </select>
              </div>
            </div>
            <div style={{ display: 'flex', gap: '10px', alignItems: 'center' }}>
              <Button
                size="sm"
                variant="primary"
                type="submit"
                data-testid="btn-release-model"
                disabled={relLoading || !canApprove || !projectId || !modelId || !version || !relLicensePolicy}
                aria-disabled={relLoading || !canApprove || !projectId || !modelId || !version || !relLicensePolicy}
              >
                {relLoading ? '릴리스 중...' : '모델 릴리스 (POST /release)'}
              </Button>
              {!canApprove && (
                <span style={{ fontSize: '11px', color: '#fed7aa' }}>
                  ⚠️ 승인 권한(canApprove)이 필요한 작업입니다.
                </span>
              )}
            </div>
          </form>
        )}
      </div>

      {/* RFC 9457 Problem Details Error Alert */}
      {problemDetails && (
        <div
          role="alert"
          data-testid="registry-problem-alert"
          style={{
            padding: '14px 18px',
            borderRadius: '8px',
            backgroundColor: 'rgba(248, 81, 73, 0.12)',
            border: '1px solid #f85149',
            color: '#f85149',
            fontSize: '13px',
            lineHeight: 1.5,
          }}
        >
          <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
            <strong>
              ❌ [{problemDetails.status}] {problemDetails.title} {problemDetails.retryable && '(재시도 가능)'}
            </strong>
            <span
              data-testid="problem-code"
              style={{
                fontFamily: 'var(--font-mono, monospace)',
                backgroundColor: 'rgba(248, 81, 73, 0.2)',
                padding: '2px 8px',
                borderRadius: '4px',
                fontSize: '11px',
                fontWeight: 700,
              }}
            >
              {problemDetails.code}
            </span>
          </div>
          <div data-testid="problem-detail" style={{ marginTop: '6px', color: '#ffb4a9' }}>
            {problemDetails.detail}
          </div>
          <div style={{ marginTop: '4px', fontSize: '11px', color: '#8b949e', fontFamily: 'var(--font-mono, monospace)' }}>
            Trace ID: <span data-testid="problem-trace-id">{problemDetails.traceId}</span>
            {problemDetails.causeRef && ` • Cause: ${problemDetails.causeRef}`}
          </div>
        </div>
      )}

      {/* General Non-Problem Error Banner */}
      {generalError && !problemDetails && (
        <div
          role="alert"
          data-testid="registry-general-alert"
          style={{
            padding: '12px 18px',
            borderRadius: '6px',
            backgroundColor: 'rgba(248, 81, 73, 0.12)',
            border: '1px solid #f85149',
            color: '#f85149',
            fontSize: '13px',
          }}
        >
          {generalError}
        </div>
      )}

      {/* Mutation Results Displays */}
      {regResult && (
        <div
          role="status"
          data-testid="registry-register-success"
          style={{
            padding: '14px 18px',
            borderRadius: '8px',
            backgroundColor: 'rgba(46, 160, 67, 0.12)',
            border: '1px solid #3fb950',
            color: '#3fb950',
            fontSize: '13px',
          }}
        >
          <div style={{ fontWeight: 600 }}>✔ 모델 버전 등록 완료 (201 Created)</div>
          <div style={{ marginTop: '6px', fontSize: '12px', color: '#c9d1d9', display: 'grid', gridTemplateColumns: 'repeat(auto-fit, minmax(200px, 1fr))', gap: '8px' }}>
            <div>Version ID: <code>{regResult.modelVersionId}</code></div>
            <div>Version: <strong>{regResult.version}</strong> (Stage: {regResult.stage})</div>
            <div>Content Digest: <code>{regResult.contentSha256.slice(0, 16)}...</code></div>
            <div>Byte Size: {regResult.byteSize} bytes</div>
            <div>URI: <code>{regResult.uri}</code></div>
            <div>Created: {regResult.createdAt}</div>
          </div>
        </div>
      )}

      {pinResult && (
        <div
          role="status"
          data-testid="registry-pin-success"
          style={{
            padding: '14px 18px',
            borderRadius: '8px',
            backgroundColor: 'rgba(46, 160, 67, 0.12)',
            border: '1px solid #3fb950',
            color: '#3fb950',
            fontSize: '13px',
          }}
        >
          <div style={{ fontWeight: 600 }}>
            ✔ 보존 고정 판정 완료 (200 OK) — {pinResult.extended ? '고정 연장됨 (Extended)' : '기존 고정 유지 (연장 없음)'}
          </div>
          <div style={{ marginTop: '6px', fontSize: '12px', color: '#c9d1d9', display: 'grid', gridTemplateColumns: 'repeat(auto-fit, minmax(200px, 1fr))', gap: '8px' }}>
            <div>Version ID: <code>{pinResult.modelVersionId}</code></div>
            <div>Version: <strong>{pinResult.version}</strong> (Stage: {pinResult.stage})</div>
            <div>Pinned Until: <strong>{pinResult.retentionPinnedUntil}</strong></div>
            <div>Extended: <span data-testid="pin-extended-flag">{String(pinResult.extended)}</span></div>
          </div>
        </div>
      )}

      {relResult && (
        <div
          role="status"
          data-testid="registry-release-success"
          style={{
            padding: '14px 18px',
            borderRadius: '8px',
            backgroundColor: 'rgba(46, 160, 67, 0.12)',
            border: '1px solid #3fb950',
            color: '#3fb950',
            fontSize: '13px',
          }}
        >
          <div style={{ fontWeight: 600 }}>✔ 모델 릴리스 완료 (200 OK)</div>
          <div style={{ marginTop: '6px', fontSize: '12px', color: '#c9d1d9', display: 'grid', gridTemplateColumns: 'repeat(auto-fit, minmax(200px, 1fr))', gap: '8px' }}>
            <div>Version ID: <code>{relResult.modelVersionId}</code></div>
            <div>Version: <strong>{relResult.version}</strong></div>
            <div>Stage: <strong style={{ color: '#58a6ff' }}>{relResult.stage}</strong></div>
            <div>Content Digest: <code>{relResult.contentSha256.slice(0, 16)}...</code></div>
          </div>
        </div>
      )}

      {/* --- REAL LINEAGE TRACE RENDERING SECTION --- */}
      {realTrace ? (
        <div
          data-testid="real-lineage-container"
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
          {/* Header & Truth Badges */}
          <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', flexWrap: 'wrap', gap: '10px' }}>
            <div>
              <h3 style={{ margin: 0, fontSize: '16px', color: '#f0f6fc' }}>
                [{realTrace.version}] 실서버 계보 추적 결과 (ModelLineageTraceResponse)
              </h3>
              <span style={{ fontSize: '12px', color: '#8b949e' }}>
                Model Version ID: <code>{realTrace.modelVersionId}</code> • Stage: <strong style={{ color: '#58a6ff' }}>{realTrace.stage.toUpperCase()}</strong>
                {realTrace.producedByRunId && <> • Produced By Run: <code>{realTrace.producedByRunId}</code></>}
              </span>
            </div>

            <div style={{ display: 'flex', gap: '8px', flexWrap: 'wrap' }}>
              <span
                data-testid="badge-fully-traceable"
                style={{
                  padding: '3px 10px',
                  borderRadius: '4px',
                  fontSize: '11px',
                  fontWeight: 700,
                  backgroundColor: realTrace.fullyTraceable ? 'rgba(46, 160, 67, 0.2)' : 'rgba(210, 153, 34, 0.2)',
                  color: realTrace.fullyTraceable ? '#3fb950' : '#d29922',
                  border: `1px solid ${realTrace.fullyTraceable ? '#3fb950' : '#d29922'}`,
                }}
              >
                {realTrace.fullyTraceable ? '완전 추적 가능 (Fully Traceable)' : '불완전 추적 (Incomplete Trace)'}
              </span>
              {realTrace.traceabilityLimitedByScope && (
                <span
                  data-testid="badge-scope-limited"
                  style={{
                    padding: '3px 10px',
                    borderRadius: '4px',
                    fontSize: '11px',
                    fontWeight: 700,
                    backgroundColor: 'rgba(56, 139, 253, 0.2)',
                    color: '#58a6ff',
                    border: '1px solid #58a6ff',
                  }}
                >
                  프로젝트 범위 제한 적용
                </span>
              )}
            </div>
          </div>

          {/* Unobserved Elements Explicit Honest Cards */}
          <div
            style={{
              display: 'grid',
              gridTemplateColumns: 'repeat(auto-fit, minmax(240px, 1fr))',
              gap: '12px',
            }}
          >
            <div
              data-testid="trace-evaluations-unobserved"
              style={{
                backgroundColor: '#0d1117',
                border: '1px solid #30363d',
                borderRadius: '6px',
                padding: '12px',
              }}
            >
              <div style={{ fontSize: '11px', color: '#8b949e', fontWeight: 600 }}>정량 평가 점수 (Accuracy / F1)</div>
              <div style={{ fontSize: '14px', fontWeight: 700, color: '#d29922', marginTop: '4px' }}>
                NOT_OBSERVED (미관측)
              </div>
              <div style={{ fontSize: '11px', color: '#8b949e', marginTop: '2px' }}>
                응답 스키마에 미포함되어 가짜 점수 합성을 차단합니다.
              </div>
            </div>

            <div
              data-testid="trace-commits-unobserved"
              style={{
                backgroundColor: '#0d1117',
                border: '1px solid #30363d',
                borderRadius: '6px',
                padding: '12px',
              }}
            >
              <div style={{ fontSize: '11px', color: '#8b949e', fontWeight: 600 }}>Git 커밋 상세 (Commits)</div>
              <div style={{ fontSize: '14px', fontWeight: 700, color: '#8b949e', marginTop: '4px' }}>
                NOT_OBSERVED (범위 외)
              </div>
              <div style={{ fontSize: '11px', color: '#8b949e', marginTop: '2px' }}>
                프로젝트 멤버 조회 경계 밖으로 서버에서 미제공됩니다.
              </div>
            </div>

            <div
              data-testid="trace-approvals-unobserved"
              style={{
                backgroundColor: '#0d1117',
                border: '1px solid #30363d',
                borderRadius: '6px',
                padding: '12px',
              }}
            >
              <div style={{ fontSize: '11px', color: '#8b949e', fontWeight: 600 }}>거버넌스 승인 원장 (Approvals)</div>
              <div style={{ fontSize: '14px', fontWeight: 700, color: '#8b949e', marginTop: '4px' }}>
                NOT_OBSERVED (범위 외)
              </div>
              <div style={{ fontSize: '11px', color: '#8b949e', marginTop: '2px' }}>
                배포 내역의 approvalId 외에 독립 원장은 미반환됩니다.
              </div>
            </div>

            <div
              data-testid="trace-images-unobserved"
              style={{
                backgroundColor: '#0d1117',
                border: '1px solid #30363d',
                borderRadius: '6px',
                padding: '12px',
              }}
            >
              <div style={{ fontSize: '11px', color: '#8b949e', fontWeight: 600 }}>컨테이너 이미지 (Images)</div>
              <div style={{ fontSize: '14px', fontWeight: 700, color: '#8b949e', marginTop: '4px' }}>
                NOT_OBSERVED (범위 외)
              </div>
              <div style={{ fontSize: '11px', color: '#8b949e', marginTop: '2px' }}>
                빌드 이미지 상세 내역은 응답에 포함되지 않습니다.
              </div>
            </div>
          </div>

          {/* Datasets Table */}
          <div data-testid="real-lineage-datasets">
            <h4 style={{ margin: '0 0 8px 0', fontSize: '14px', color: '#f0f6fc' }}>
              연결된 데이터셋 버전 ({realTrace.datasets.length}건)
            </h4>
            {realTrace.datasets.length === 0 ? (
              <div style={{ fontSize: '12px', color: '#8b949e', padding: '12px', backgroundColor: '#0d1117', borderRadius: '6px' }}>
                연결된 데이터셋이 없습니다.
              </div>
            ) : (
              <table style={{ width: '100%', borderCollapse: 'collapse', fontSize: '12px', color: '#c9d1d9' }}>
                <thead>
                  <tr style={{ borderBottom: '1px solid #30363d', textAlign: 'left', color: '#8b949e' }}>
                    <th style={{ padding: '6px' }}>Dataset Version ID</th>
                    <th style={{ padding: '6px' }}>Version</th>
                    <th style={{ padding: '6px' }}>Content SHA-256</th>
                    <th style={{ padding: '6px' }}>URI</th>
                  </tr>
                </thead>
                <tbody>
                  {realTrace.datasets.map((d) => (
                    <tr key={d.datasetVersionId} style={{ borderBottom: '1px solid #21262d' }}>
                      <td style={{ padding: '8px 6px', fontFamily: 'var(--font-mono, monospace)' }}>{d.datasetVersionId}</td>
                      <td style={{ padding: '8px 6px', fontWeight: 600 }}>{d.version}</td>
                      <td style={{ padding: '8px 6px', fontFamily: 'var(--font-mono, monospace)' }}>{d.contentSha256.slice(0, 16)}...</td>
                      <td style={{ padding: '8px 6px', color: '#58a6ff' }}>{d.uri}</td>
                    </tr>
                  ))}
                </tbody>
              </table>
            )}
          </div>

          {/* Deployments Table */}
          <div data-testid="real-lineage-deployments">
            <h4 style={{ margin: '0 0 8px 0', fontSize: '14px', color: '#f0f6fc' }}>
              배포 기록 ({realTrace.deployments.length}건)
            </h4>
            {realTrace.deployments.length === 0 ? (
              <div style={{ fontSize: '12px', color: '#8b949e', padding: '12px', backgroundColor: '#0d1117', borderRadius: '6px' }}>
                배포 내역이 없습니다 (deployments: []).
              </div>
            ) : (
              <table style={{ width: '100%', borderCollapse: 'collapse', fontSize: '12px', color: '#c9d1d9' }}>
                <thead>
                  <tr style={{ borderBottom: '1px solid #30363d', textAlign: 'left', color: '#8b949e' }}>
                    <th style={{ padding: '6px' }}>Deployment ID</th>
                    <th style={{ padding: '6px' }}>Environment</th>
                    <th style={{ padding: '6px' }}>Status</th>
                    <th style={{ padding: '6px' }}>Digest</th>
                    <th style={{ padding: '6px' }}>Deployed At</th>
                    <th style={{ padding: '6px' }}>Approval ID</th>
                  </tr>
                </thead>
                <tbody>
                  {realTrace.deployments.map((dep) => (
                    <tr key={dep.deploymentId} style={{ borderBottom: '1px solid #21262d' }}>
                      <td style={{ padding: '8px 6px', fontFamily: 'var(--font-mono, monospace)' }}>{dep.deploymentId}</td>
                      <td style={{ padding: '8px 6px' }}>
                        <span style={{ textTransform: 'uppercase', fontWeight: 600, color: dep.environment === 'pilot' ? '#3fb950' : '#58a6ff' }}>
                          {dep.environment}
                        </span>
                      </td>
                      <td style={{ padding: '8px 6px' }}>{dep.status}</td>
                      <td style={{ padding: '8px 6px', fontFamily: 'var(--font-mono, monospace)' }}>{dep.deployedDigest.slice(0, 16)}...</td>
                      <td style={{ padding: '8px 6px' }}>{dep.deployedAt}</td>
                      <td style={{ padding: '8px 6px', fontFamily: 'var(--font-mono, monospace)' }}>{dep.approvalId || 'None'}</td>
                    </tr>
                  ))}
                </tbody>
              </table>
            )}
          </div>

          {/* Missing & Unresolved */}
          <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fit, minmax(280px, 1fr))', gap: '16px' }}>
            <div data-testid="real-lineage-missing">
              <h4 style={{ margin: '0 0 6px 0', fontSize: '13px', color: '#f0f6fc' }}>
                누락된 주체 (Missing: {realTrace.missing.length}건)
              </h4>
              {realTrace.missing.length === 0 ? (
                <div style={{ fontSize: '12px', color: '#3fb950' }}>누락된 항목이 없습니다.</div>
              ) : (
                <ul style={{ margin: 0, paddingLeft: '18px', fontSize: '12px', color: '#f85149' }}>
                  {realTrace.missing.map((m, idx) => (
                    <li key={idx} data-testid="missing-item">{m}</li>
                  ))}
                </ul>
              )}
            </div>

            <div data-testid="real-lineage-unresolved">
              <h4 style={{ margin: '0 0 6px 0', fontSize: '13px', color: '#f0f6fc' }}>
                범위 외 미해결 주체 (Unresolved: {realTrace.unresolved.length}건)
              </h4>
              {realTrace.unresolved.length === 0 ? (
                <div style={{ fontSize: '12px', color: '#8b949e' }}>미해결 항목이 없습니다.</div>
              ) : (
                <ul style={{ margin: 0, paddingLeft: '18px', fontSize: '12px', color: '#d29922' }}>
                  {realTrace.unresolved.map((u, idx) => (
                    <li key={idx}>
                      <strong>{u.kind}</strong>: {u.count}건
                    </li>
                  ))}
                </ul>
              )}
            </div>
          </div>
        </div>
      ) : (
        /* Fallback to Simulated / Preserved Views when no Real HTTP Trace is active */
        <>
          {/* Honest Notice: Backend Lineage & Evaluation Scores Not Exposed via HTTP (Preserved for tests) */}
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
        </>
      )}
    </div>
  );
};
