import React, { useState, useRef, useEffect } from 'react';
import { ModelLineage, ProblemDetails, ModelCommitObservation } from '@/contracts/types';
import type { ConformanceStatusResponse } from '@/contracts/conformance-status-response';
import { Button } from '@/shared/ui/Button';
import { ApiError } from '@/shared/api/client';
import { fetchModelCommitment } from '@/shared/api/modelCommitmentObservation';
import { fetchConformanceStatus } from '@/shared/api/adapterObservation';
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

// Server canonical kind labels (Claude G1: no aliases, declared below imports)
const SERVER_KIND_LABELS: Record<string, string> = {
  eval_run: '정량 평가 실행 (eval_run)',
  code_commit: 'Git 커밋 (code_commit)',
  approval: '거버넌스 승인 원장 (approval)',
  container_image: '컨테이너 이미지 (container_image)',
  dataset_version: '데이터셋 버전 (dataset_version)',
  deployment: '배포 내역 (deployment)',
};

export interface ModelLineageViewProps {
  initialLineages?: ModelLineage[];
  projectId?: string;
  currentProjectId?: string;
  currentUser?: { role?: string; canApprove?: boolean; canRequest?: boolean } | null;
  initialModelId?: string;
  initialVersion?: string;
}

export const ModelLineageView: React.FC<ModelLineageViewProps> = ({
  initialLineages = [],
  projectId: propProjectId = '',
  currentProjectId,
  currentUser,
  initialModelId = '',
  initialVersion = '',
}) => {
  // --- Simulation / Legacy Mock State (Preserved for existing suites) ---
  const [mlopsManager] = useState<MlopsManager>(() => new MlopsManager(initialLineages));
  const [lineages, setLineages] = useState<ModelLineage[]>(mlopsManager.getLineages());
  const [selectedModelId, setSelectedModelId] = useState<string>(
    initialModelId || (lineages.length > 0 ? lineages[0].modelId : '')
  );
  const [searchQuery, setSearchQuery] = useState('');
  const [actionNotice, setActionNotice] = useState<{ type: 'success' | 'info' | 'error'; text: string } | null>(null);

  // Multi-LLM provider adapter conformance observation state
  const effectiveProjectId = propProjectId || currentProjectId || '';
  const [conformanceProjectId, setConformanceProjectId] = useState<string>(effectiveProjectId);
  const [conformanceData, setConformanceData] = useState<ConformanceStatusResponse | null>(null);
  const [conformanceLoading, setConformanceLoading] = useState<boolean>(false);
  const [conformanceLiveStatus, setConformanceLiveStatus] = useState<string>('');
  const [conformanceError, setConformanceError] = useState<{
    code?: string;
    status?: number;
    title?: string;
    detail: string;
  } | null>(null);

  const handleFetchConformance = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!conformanceProjectId.trim()) return;

    setConformanceLoading(true);
    setConformanceError(null);
    setConformanceLiveStatus(`어댑터 적합성 상태 조회 중 (프로젝트: ${conformanceProjectId})...`);

    try {
      const res = await fetchConformanceStatus(conformanceProjectId.trim());
      setConformanceData(res);
      setConformanceLiveStatus(
        `어댑터 적합성 조회 완료: 총 ${res.totalChecks}개 검사 항목 중 ${res.observedChecks}개 관측됨.`
      );
    } catch (err: any) {
      const prob = err instanceof ApiError ? err.problem : null;
      if (prob) {
        let safeDetail = prob.detail || '요청이 거절되었습니다.';
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

  // Model commitment observation state
  const [commitmentProject, setCommitmentProject] = useState(effectiveProjectId);
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

  // --- Real HTTP API / Model Registry State ---
  const [projectId, setProjectId] = useState<string>(effectiveProjectId);
  const [modelId, setModelId] = useState<string>(initialModelId);
  const [version, setVersion] = useState<string>(initialVersion);

  const [activeTab, setActiveTab] = useState<'trace' | 'register' | 'pin' | 'release'>('trace');
  const [queryLoading, setQueryLoading] = useState(false);
  const [realTrace, setRealTrace] = useState<ModelLineageTraceResponse | null>(null);

  // W2 Register form state
  const [regVersion, setRegVersion] = useState('');
  const [regSha256, setRegSha256] = useState('');
  const [regByteSize, setRegByteSize] = useState('0');
  const [regUri, setRegUri] = useState('');
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

  // Idempotency keys preserved per submission intent
  const [regIdempotencyKey, setRegIdempotencyKey] = useState<string>(() =>
    modelRegistryObservation.generateIdempotencyKey('w2')
  );
  const [pinIdempotencyKey, setPinIdempotencyKey] = useState<string>(() =>
    modelRegistryObservation.generateIdempotencyKey('pin')
  );

  // ProblemDetails error and Live Region
  const [problemDetails, setProblemDetails] = useState<ProblemDetails | null>(null);
  const [generalError, setGeneralError] = useState<string | null>(null);
  const [liveAnnouncement, setLiveAnnouncement] = useState<string>('');

  // Claude G3: Separate AbortControllers and generation refs for each write/query action
  const queryAbortControllerRef = useRef<AbortController | null>(null);
  const queryGenerationRef = useRef(0);

  const regAbortControllerRef = useRef<AbortController | null>(null);
  const regGenerationRef = useRef(0);

  const pinAbortControllerRef = useRef<AbortController | null>(null);
  const pinGenerationRef = useRef(0);

  const relAbortControllerRef = useRef<AbortController | null>(null);
  const relGenerationRef = useRef(0);

  useEffect(() => {
    if (effectiveProjectId) {
      setProjectId(effectiveProjectId);
      setCommitmentProject(effectiveProjectId);
      setConformanceProjectId(effectiveProjectId);
    }
  }, [effectiveProjectId]);

  useEffect(() => {
    return () => {
      queryAbortControllerRef.current?.abort();
      regAbortControllerRef.current?.abort();
      pinAbortControllerRef.current?.abort();
      relAbortControllerRef.current?.abort();
    };
  }, []);

  // Strict Fail-closed check: requires explicit canApprove === true
  const canApprove = currentUser?.canApprove === true;

  const clearErrors = () => {
    setProblemDetails(null);
    setGeneralError(null);
  };

  const handleApiError = (err: any, fallbackTitle: string) => {
    if (err instanceof ApiError && err.problem) {
      setProblemDetails(err.problem);
      setLiveAnnouncement(`오류 발생: [${err.problem.code}] ${err.problem.title}`);
    } else {
      const msg = err?.message || '알 수 없는 네트워크 오류가 발생했습니다.';
      setGeneralError(`${fallbackTitle}: ${msg}`);
      setLiveAnnouncement(`오류 발생: ${msg}`);
    }
  };

  // G2 / G3: Input change handlers that rotate Idempotency-Keys and invalidate in-flight generation
  const handleProjectIdChange = (val: string) => {
    setProjectId(val);
    queryGenerationRef.current++;
    regGenerationRef.current++;
    pinGenerationRef.current++;
    relGenerationRef.current++;
    setRegIdempotencyKey(modelRegistryObservation.generateIdempotencyKey('w2'));
    setPinIdempotencyKey(modelRegistryObservation.generateIdempotencyKey('pin'));
  };

  const handleModelIdChange = (val: string) => {
    setModelId(val);
    queryGenerationRef.current++;
    regGenerationRef.current++;
    pinGenerationRef.current++;
    relGenerationRef.current++;
    setRegIdempotencyKey(modelRegistryObservation.generateIdempotencyKey('w2'));
    setPinIdempotencyKey(modelRegistryObservation.generateIdempotencyKey('pin'));
  };

  const handleVersionChange = (val: string) => {
    setVersion(val);
    queryGenerationRef.current++;
    pinGenerationRef.current++;
    relGenerationRef.current++;
    setPinIdempotencyKey(modelRegistryObservation.generateIdempotencyKey('pin'));
  };

  const handlePinUntilChange = (val: string) => {
    setPinUntil(val);
    pinGenerationRef.current++;
    setPinIdempotencyKey(modelRegistryObservation.generateIdempotencyKey('pin'));
  };

  const handleRegVersionChange = (val: string) => {
    setRegVersion(val);
    regGenerationRef.current++;
    setRegIdempotencyKey(modelRegistryObservation.generateIdempotencyKey('w2'));
  };

  const handleRegShaChange = (val: string) => {
    setRegSha256(val);
    regGenerationRef.current++;
    setRegIdempotencyKey(modelRegistryObservation.generateIdempotencyKey('w2'));
  };

  const handleRegByteSizeChange = (val: string) => {
    setRegByteSize(val);
    regGenerationRef.current++;
    setRegIdempotencyKey(modelRegistryObservation.generateIdempotencyKey('w2'));
  };

  const handleQueryLineage = async (e?: React.FormEvent) => {
    if (e) e.preventDefault();
    clearErrors();
    if (!projectId.trim() || !modelId.trim() || !version.trim()) {
      setGeneralError('프로젝트 ID, 모델 ID, 버전 정보를 모두 입력해야 정본 계보 조회가 가능합니다.');
      return;
    }

    queryAbortControllerRef.current?.abort();
    const ctrl = new AbortController();
    queryAbortControllerRef.current = ctrl;
    const currentGen = ++queryGenerationRef.current;

    setQueryLoading(true);
    setLiveAnnouncement(`서버 정본 계보 조회 중... [${modelId}:${version}]`);
    try {
      const res = await modelRegistryObservation.fetchModelLineage(
        projectId.trim(),
        modelId.trim(),
        version.trim(),
        ctrl.signal
      );
      if (queryGenerationRef.current !== currentGen || ctrl.signal.aborted) return;
      setRealTrace(res);
      setLiveAnnouncement(`계보 조회 성공: [${res.version}]`);
    } catch (err: any) {
      if (queryGenerationRef.current !== currentGen || ctrl.signal.aborted) return;
      handleApiError(err, '정본 계보 조회 실패');
    } finally {
      setQueryLoading(false);
    }
  };

  const handleRegisterVersion = async (e: React.FormEvent) => {
    e.preventDefault();
    clearErrors();
    if (!canApprove) {
      setGeneralError('승인 권한(canApprove)이 없는 계정은 모델 버전을 등록할 수 없습니다.');
      return;
    }
    if (!projectId.trim() || !modelId.trim()) {
      setGeneralError('프로젝트 ID와 모델 ID를 입력하세요.');
      return;
    }
    if (!regVersion.trim()) {
      setGeneralError('등록할 버전 문자열을 입력하세요.');
      return;
    }
    if (!/^[0-9a-f]{64}$/i.test(regSha256.trim())) {
      setGeneralError('contentSha256은 64자리 16진수여야 합니다.');
      return;
    }
    if (!/^\d+$/.test(regByteSize.trim()) || !Number.isSafeInteger(Number(regByteSize.trim()))) {
      setGeneralError('byteSize는 0 이상의 유효한 정수여야 합니다.');
      return;
    }

    regAbortControllerRef.current?.abort();
    const ctrl = new AbortController();
    regAbortControllerRef.current = ctrl;
    const currentGen = ++regGenerationRef.current;

    setRegLoading(true);
    setLiveAnnouncement(`모델 버전 [${regVersion}] 등록 요청 중...`);
    try {
      const res = await modelRegistryObservation.registerModelVersion(
        projectId.trim(),
        modelId.trim(),
        {
          version: regVersion.trim(),
          contentSha256: regSha256.trim().toLowerCase(),
          byteSize: Number(regByteSize.trim()),
          uri: regUri.trim() || undefined,
        },
        { signal: ctrl.signal, idempotencyKey: regIdempotencyKey }
      );
      if (regGenerationRef.current !== currentGen || ctrl.signal.aborted) return;
      setRegResult(res);
      setLiveAnnouncement(`모델 버전 등록 성공: [${res.version}] (단계: ${res.stage})`);
      setRegIdempotencyKey(modelRegistryObservation.generateIdempotencyKey('w2'));
    } catch (err: any) {
      if (regGenerationRef.current !== currentGen || ctrl.signal.aborted) return;
      handleApiError(err, '모델 버전 등록 실패');
    } finally {
      // Claude G3: ALWAYS clear loading state for register action
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
    if (!pinUntil.trim()) {
      setGeneralError('보존 만료 일시(retentionPinnedUntil)를 입력하세요.');
      return;
    }
    if (!isValidIsoDateTime(pinUntil.trim())) {
      setGeneralError('유효한 RFC 3339 날짜/시간(예: 2026-12-31T23:59:59Z, 실제 달력 일치)이어야 합니다.');
      return;
    }

    pinAbortControllerRef.current?.abort();
    const ctrl = new AbortController();
    pinAbortControllerRef.current = ctrl;
    const currentGen = ++pinGenerationRef.current;

    setPinLoading(true);
    setLiveAnnouncement(`모델 버전 [${version}] 보존 고정 연장 요청 중...`);
    try {
      const res = await modelRegistryObservation.extendRetentionPin(
        projectId.trim(),
        modelId.trim(),
        version.trim(),
        { retentionPinnedUntil: pinUntil.trim() },
        { signal: ctrl.signal, idempotencyKey: pinIdempotencyKey }
      );
      if (pinGenerationRef.current !== currentGen || ctrl.signal.aborted) return;
      setPinResult(res);
      setLiveAnnouncement(`보존 고정 연장 성공: [${res.retentionPinnedUntil}]`);
      setPinIdempotencyKey(modelRegistryObservation.generateIdempotencyKey('pin'));
    } catch (err: any) {
      if (pinGenerationRef.current !== currentGen || ctrl.signal.aborted) return;
      handleApiError(err, '보존 고정 연장 실패');
    } finally {
      // Claude G3: ALWAYS clear loading state for pin action
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

    relAbortControllerRef.current?.abort();
    const ctrl = new AbortController();
    relAbortControllerRef.current = ctrl;
    const currentGen = ++relGenerationRef.current;

    setRelLoading(true);
    setLiveAnnouncement(`모델 [${modelId}:${version}] 릴리스 요청 중...`);
    try {
      const res = await modelRegistryObservation.releaseModelVersion(
        projectId.trim(),
        modelId.trim(),
        version.trim(),
        {
          licensePolicy: relLicensePolicy.trim(),
          classification: relClassification,
        },
        { signal: ctrl.signal }
      );
      if (relGenerationRef.current !== currentGen || ctrl.signal.aborted) return;
      setRelResult(res);
      setLiveAnnouncement(`모델 릴리스 성공: [${res.modelVersionId}] (단계: ${res.stage})`);
    } catch (err: any) {
      if (relGenerationRef.current !== currentGen || ctrl.signal.aborted) return;
      handleApiError(err, '모델 릴리스 실패');
    } finally {
      // Claude G3: ALWAYS clear loading state for release action
      setRelLoading(false);
    }
  };

  // --- Simulation / Legacy Handlers (Preserved) ---
  const handleSelectModel = (mId: string) => {
    setSelectedModelId(mId);
    const m = lineages.find((item) => item.modelId === mId);
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
        text: `❌ 검색 실패: '${searchQuery}'에 해당하는 모델 또는 아티팩트를 찾을 수 없습니다.`,
      });
    }
  };

  const handleFetchCommitment = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!commitmentProject.trim() || !commitmentModelId.trim() || !commitmentVersion.trim()) return;

    setCommitmentLoading(true);
    setCommitmentError(null);

    try {
      const result = await fetchModelCommitment(
        commitmentProject.trim(),
        commitmentModelId.trim(),
        commitmentVersion.trim()
      );
      setCommitmentData(result);
    } catch (err: any) {
      const prob = err instanceof ApiError ? err.problem : null;
      if (prob) {
        setCommitmentError({
          code: prob.code,
          status: prob.status,
          title: prob.title,
          detail: prob.detail || '요청이 거절되었습니다.',
        });
      } else {
        setCommitmentError({
          detail: err?.message || '네트워크 오류가 발생했습니다.',
        });
      }
    } finally {
      setCommitmentLoading(false);
    }
  };

  return (
    <div style={{ padding: '24px', maxWidth: '1280px', margin: '0 auto', display: 'flex', flexDirection: 'column', gap: '24px' }}>
      {/* Permanent Live Region for Dynamic Announcements */}
      <div
        role="status"
        aria-live="polite"
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

      {/* Global Fail-Closed Permission Banner (Codex F1) */}
      {!canApprove && (
        <div
          data-testid="banner-no-approve-permission"
          style={{
            padding: '12px 16px',
            backgroundColor: '#161b22',
            border: '1px solid #d29922',
            borderRadius: '8px',
            color: '#d29922',
            fontSize: '13px',
            display: 'flex',
            alignItems: 'center',
            gap: '8px',
          }}
        >
          <span aria-hidden="true">⚠️</span>
          <span>
            거버넌스 승인 권한(canApprove)이 없어 조회만 가능합니다. 모델 버전 등록, 보존 고정 연장, 릴리스 쓰기 작업은 비활성화됩니다.
          </span>
        </div>
      )}

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
              onChange={(e) => handleProjectIdChange(e.target.value)}
              style={{
                width: '100%',
                padding: '8px 10px',
                backgroundColor: '#0d1117',
                border: '1px solid #30363d',
                borderRadius: '6px',
                color: '#c9d1d9',
                fontSize: '13px',
                fontFamily: 'var(--font-mono, monospace)',
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
              placeholder="mdl_..."
              value={modelId}
              onChange={(e) => handleModelIdChange(e.target.value)}
              style={{
                width: '100%',
                padding: '8px 10px',
                backgroundColor: '#0d1117',
                border: '1px solid #30363d',
                borderRadius: '6px',
                color: '#c9d1d9',
                fontSize: '13px',
                fontFamily: 'var(--font-mono, monospace)',
              }}
            />
          </div>
          <div>
            <label htmlFor="reg-version" style={{ display: 'block', fontSize: '11px', color: '#8b949e', marginBottom: '4px' }}>
              Version (Semantic)
            </label>
            <input
              id="reg-version"
              data-testid="input-version"
              type="text"
              placeholder="예: 1.0.0"
              value={version}
              onChange={(e) => handleVersionChange(e.target.value)}
              style={{
                width: '100%',
                padding: '8px 10px',
                backgroundColor: '#0d1117',
                border: '1px solid #30363d',
                borderRadius: '6px',
                color: '#c9d1d9',
                fontSize: '13px',
                fontFamily: 'var(--font-mono, monospace)',
              }}
            />
          </div>
        </div>

        {/* Tab Selection */}
        <div style={{ display: 'flex', gap: '8px', borderBottom: '1px solid #30363d', paddingBottom: '8px', flexWrap: 'wrap' }}>
          <button
            type="button"
            onClick={() => setActiveTab('trace')}
            style={{
              padding: '6px 14px',
              borderRadius: '6px',
              fontSize: '13px',
              fontWeight: 600,
              backgroundColor: activeTab === 'trace' ? '#21262d' : 'transparent',
              color: activeTab === 'trace' ? '#58a6ff' : '#8b949e',
              border: 'none',
              cursor: 'pointer',
            }}
          >
            정본 계보 조회 (Trace)
          </button>
          <button
            type="button"
            onClick={() => setActiveTab('register')}
            style={{
              padding: '6px 14px',
              borderRadius: '6px',
              fontSize: '13px',
              fontWeight: 600,
              backgroundColor: activeTab === 'register' ? '#21262d' : 'transparent',
              color: activeTab === 'register' ? '#58a6ff' : '#8b949e',
              border: 'none',
              cursor: 'pointer',
            }}
          >
            W2 버전 등록 (Register)
          </button>
          <button
            type="button"
            onClick={() => setActiveTab('pin')}
            style={{
              padding: '6px 14px',
              borderRadius: '6px',
              fontSize: '13px',
              fontWeight: 600,
              backgroundColor: activeTab === 'pin' ? '#21262d' : 'transparent',
              color: activeTab === 'pin' ? '#58a6ff' : '#8b949e',
              border: 'none',
              cursor: 'pointer',
            }}
          >
            W4 보존 고정 연장 (Retention Pin)
          </button>
          <button
            type="button"
            onClick={() => setActiveTab('release')}
            style={{
              padding: '6px 14px',
              borderRadius: '6px',
              fontSize: '13px',
              fontWeight: 600,
              backgroundColor: activeTab === 'release' ? '#21262d' : 'transparent',
              color: activeTab === 'release' ? '#58a6ff' : '#8b949e',
              border: 'none',
              cursor: 'pointer',
            }}
          >
            모델 릴리스 (Release)
          </button>
        </div>

        {/* RFC 9457 Problem Details Alert Banner */}
        {problemDetails && (
          <div
            role="alert"
            data-testid="registry-problem-alert"
            style={{
              backgroundColor: '#3d1214',
              border: '1px solid #f85149',
              borderRadius: '6px',
              padding: '14px',
              color: '#f85149',
              fontSize: '13px',
              display: 'flex',
              flexDirection: 'column',
              gap: '6px',
            }}
          >
            <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
              <span style={{ fontWeight: 700 }}>
                <span aria-hidden="true" style={{ marginRight: '6px' }}>❌</span>
                [<span data-testid="problem-code">{problemDetails.code}</span>] {problemDetails.title} (HTTP {problemDetails.status})
              </span>
              {problemDetails.retryable && (
                <span style={{ fontSize: '11px', backgroundColor: 'rgba(210, 153, 34, 0.2)', color: '#d29922', padding: '2px 8px', borderRadius: '4px', fontWeight: 600 }}>
                  (재시도 가능)
                </span>
              )}
            </div>
            <div data-testid="problem-detail" style={{ color: '#ff7b72' }}>
              {problemDetails.detail}
            </div>
            {problemDetails.traceId && (
              <div style={{ fontSize: '11px', color: '#8b949e', fontFamily: 'var(--font-mono, monospace)' }}>
                Trace ID: <span data-testid="problem-trace-id">{problemDetails.traceId}</span>
              </div>
            )}
          </div>
        )}

        {/* General Error Alert Banner */}
        {generalError && (
          <div
            role="alert"
            data-testid="registry-general-alert"
            style={{
              backgroundColor: '#3d1214',
              border: '1px solid #f85149',
              borderRadius: '6px',
              padding: '12px',
              color: '#f85149',
              fontSize: '13px',
            }}
          >
            <span aria-hidden="true" style={{ marginRight: '6px' }}>❌</span>
            {generalError}
          </div>
        )}

        {/* Tab 1: Lineage Trace Query View */}
        {activeTab === 'trace' && (
          <div style={{ display: 'flex', flexDirection: 'column', gap: '16px' }}>
            <div style={{ display: 'flex', gap: '10px', alignItems: 'center' }}>
              <Button
                variant="primary"
                size="sm"
                data-testid="btn-query-lineage"
                onClick={handleQueryLineage}
                disabled={queryLoading || !projectId.trim() || !modelId.trim() || !version.trim()}
              >
                {queryLoading ? '계보 조회 중...' : '정본 계보 조회 (GET /lineage)'}
              </Button>
            </div>

            {realTrace && (
              <div
                data-testid="real-lineage-container"
                style={{
                  backgroundColor: '#0d1117',
                  border: '1px solid #30363d',
                  borderRadius: '6px',
                  padding: '16px',
                  display: 'flex',
                  flexDirection: 'column',
                  gap: '16px',
                }}
              >
                {/* Meta summary badges */}
                <div style={{ display: 'flex', gap: '10px', flexWrap: 'wrap', alignItems: 'center' }}>
                  <span
                    data-testid="badge-stage"
                    style={{
                      padding: '2px 8px',
                      borderRadius: '4px',
                      fontSize: '11px',
                      fontWeight: 600,
                      backgroundColor: '#21262d',
                      color: '#58a6ff',
                      border: '1px solid #30363d',
                    }}
                  >
                    Stage: {realTrace.stage}
                  </span>
                  <span
                    data-testid="badge-fully-traceable"
                    style={{
                      padding: '2px 8px',
                      borderRadius: '4px',
                      fontSize: '11px',
                      fontWeight: 600,
                      backgroundColor: realTrace.fullyTraceable ? 'rgba(46, 160, 67, 0.15)' : 'rgba(218, 54, 51, 0.15)',
                      color: realTrace.fullyTraceable ? '#3fb950' : '#f85149',
                      border: `1px solid ${realTrace.fullyTraceable ? '#2ea043' : '#da3633'}`,
                    }}
                  >
                    {realTrace.fullyTraceable ? '완전 추적 (Fully Traceable)' : '불완전 추적 (Incomplete Trace)'}
                  </span>
                  {realTrace.traceabilityLimitedByScope && (
                    <span
                      data-testid="badge-scope-limited"
                      style={{
                        padding: '2px 8px',
                        borderRadius: '4px',
                        fontSize: '11px',
                        fontWeight: 600,
                        backgroundColor: 'rgba(210, 153, 34, 0.15)',
                        color: '#d29922',
                        border: '1px solid #d29922',
                      }}
                    >
                      프로젝트 범위 제한 적용 (Scope Limited)
                    </span>
                  )}
                  <span style={{ fontSize: '12px', color: '#8b949e', fontFamily: 'var(--font-mono, monospace)' }}>
                    SHA256: {realTrace.contentSha256.substring(0, 16)}...
                  </span>
                </div>

                {/* Missing Items Warning (Claude G1) */}
                {realTrace.missing.length > 0 && (
                  <div
                    data-testid="real-lineage-missing"
                    style={{
                      padding: '12px',
                      backgroundColor: '#3d1214',
                      border: '1px solid #f85149',
                      borderRadius: '6px',
                      color: '#ff7b72',
                      fontSize: '12px',
                    }}
                  >
                    <div style={{ fontWeight: 700, marginBottom: '4px' }}>
                      <span aria-hidden="true" style={{ marginRight: '6px' }}>⚠️</span>
                      필수 추적 항목 누락 (Missing Required Lineage Kinds):
                    </div>
                    <ul style={{ margin: 0, paddingLeft: '20px' }}>
                      {realTrace.missing.map((item, idx) => (
                        <li key={idx} style={{ fontFamily: 'var(--font-mono, monospace)' }}>
                          {item}
                        </li>
                      ))}
                    </ul>
                  </div>
                )}

                {/* Dynamic Unresolved / CountOnly Kinds Honest Cards (Claude G1: server kinds only) */}
                <div
                  style={{
                    display: 'grid',
                    gridTemplateColumns: 'repeat(auto-fit, minmax(240px, 1fr))',
                    gap: '12px',
                  }}
                >
                  {realTrace.countOnlyKinds.map((kind) => {
                    const unresolvedItem = realTrace.unresolved.find((u) => u.kind === kind);
                    const label = SERVER_KIND_LABELS[kind] || `${kind} 항목`;
                    return (
                      <div
                        key={kind}
                        data-testid={`trace-${kind}-unobserved`}
                        style={{
                          backgroundColor: '#0d1117',
                          border: '1px solid #30363d',
                          borderRadius: '6px',
                          padding: '12px',
                        }}
                      >
                        <div style={{ fontSize: '11px', color: '#8b949e', fontWeight: 600 }}>{label}</div>
                        <div style={{ fontSize: '14px', fontWeight: 700, color: unresolvedItem ? '#58a6ff' : '#8b949e', marginTop: '4px' }}>
                          {unresolvedItem ? `상세 범위 외 (${unresolvedItem.count}건 관측)` : '관측된 항목 없음 (0건)'}
                        </div>
                        <div style={{ fontSize: '11px', color: '#8b949e', marginTop: '2px' }}>
                          프로젝트 멤버 조회 경계 밖으로 서버에서 미제공됩니다.
                        </div>
                      </div>
                    );
                  })}
                </div>

                {/* Datasets Table */}
                <div data-testid="real-lineage-datasets">
                  <h4 style={{ margin: '0 0 8px 0', fontSize: '14px', color: '#f0f6fc' }}>
                    연결된 데이터셋 버전 ({realTrace.datasets.length}건)
                  </h4>
                  {realTrace.datasets.length === 0 ? (
                    <div style={{ fontSize: '12px', color: '#8b949e' }}>연결된 데이터셋이 없습니다.</div>
                  ) : (
                    <div style={{ overflowX: 'auto' }}>
                      <table style={{ width: '100%', borderCollapse: 'collapse', fontSize: '12px' }}>
                        <thead>
                          <tr style={{ borderBottom: '1px solid #30363d', textAlign: 'left', color: '#8b949e' }}>
                            <th style={{ padding: '6px' }}>Dataset Version ID</th>
                            <th style={{ padding: '6px' }}>Version</th>
                            <th style={{ padding: '6px' }}>SHA256</th>
                            <th style={{ padding: '6px' }}>URI</th>
                          </tr>
                        </thead>
                        <tbody>
                          {realTrace.datasets.map((ds) => (
                            <tr key={ds.datasetVersionId} style={{ borderBottom: '1px solid #21262d' }}>
                              <td style={{ padding: '6px', fontFamily: 'var(--font-mono, monospace)', color: '#58a6ff' }}>
                                {ds.datasetVersionId}
                              </td>
                              <td style={{ padding: '6px', color: '#f0f6fc' }}>{ds.version}</td>
                              <td style={{ padding: '6px', fontFamily: 'var(--font-mono, monospace)', color: '#8b949e' }}>
                                {ds.contentSha256.substring(0, 16)}...
                              </td>
                              <td style={{ padding: '6px', color: '#8b949e' }}>{ds.uri}</td>
                            </tr>
                          ))}
                        </tbody>
                      </table>
                    </div>
                  )}
                </div>

                {/* Deployments Table */}
                <div data-testid="real-lineage-deployments">
                  <h4 style={{ margin: '0 0 8px 0', fontSize: '14px', color: '#f0f6fc' }}>
                    배포 이력 ({realTrace.deployments.length}건)
                  </h4>
                  {realTrace.deployments.length === 0 ? (
                    <div style={{ fontSize: '12px', color: '#8b949e' }}>배포 이력이 없습니다.</div>
                  ) : (
                    <div style={{ overflowX: 'auto' }}>
                      <table style={{ width: '100%', borderCollapse: 'collapse', fontSize: '12px' }}>
                        <thead>
                          <tr style={{ borderBottom: '1px solid #30363d', textAlign: 'left', color: '#8b949e' }}>
                            <th style={{ padding: '6px' }}>Deployment ID</th>
                            <th style={{ padding: '6px' }}>Environment</th>
                            <th style={{ padding: '6px' }}>Status</th>
                            <th style={{ padding: '6px' }}>Approval ID</th>
                            <th style={{ padding: '6px' }}>Deployed At</th>
                          </tr>
                        </thead>
                        <tbody>
                          {realTrace.deployments.map((dpl) => (
                            <tr key={dpl.deploymentId} style={{ borderBottom: '1px solid #21262d' }}>
                              <td style={{ padding: '6px', fontFamily: 'var(--font-mono, monospace)', color: '#58a6ff' }}>
                                {dpl.deploymentId}
                              </td>
                              <td style={{ padding: '6px', color: '#f0f6fc' }}>{dpl.environment}</td>
                              <td style={{ padding: '6px', color: '#8b949e' }}>{dpl.status}</td>
                              <td style={{ padding: '6px', fontFamily: 'var(--font-mono, monospace)', color: '#8b949e' }}>
                                {dpl.approvalId || '-'}
                              </td>
                              <td style={{ padding: '6px', color: '#8b949e' }}>{dpl.deployedAt}</td>
                            </tr>
                          ))}
                        </tbody>
                      </table>
                    </div>
                  )}
                </div>
              </div>
            )}
          </div>
        )}

        {/* Tab 2: W2 Model Version Register Form */}
        {activeTab === 'register' && (
          <form onSubmit={handleRegisterVersion} style={{ display: 'flex', flexDirection: 'column', gap: '14px' }}>
            <h4 style={{ margin: 0, fontSize: '15px', color: '#f0f6fc' }}>
              W2 Model Version 등록 (POST /projects/:project/models/:model/versions)
            </h4>
            <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fit, minmax(220px, 1fr))', gap: '12px' }}>
              <div>
                <label htmlFor="w2-reg-ver" style={{ display: 'block', fontSize: '11px', color: '#8b949e', marginBottom: '4px' }}>
                  버전 (Version) *
                </label>
                <input
                  id="w2-reg-ver"
                  data-testid="input-register-version"
                  type="text"
                  placeholder="예: 1.0.0-rc1"
                  value={regVersion}
                  onChange={(e) => handleRegVersionChange(e.target.value)}
                  style={{
                    width: '100%',
                    padding: '8px 10px',
                    backgroundColor: '#0d1117',
                    border: '1px solid #30363d',
                    borderRadius: '6px',
                    color: '#c9d1d9',
                    fontSize: '13px',
                    fontFamily: 'var(--font-mono, monospace)',
                  }}
                />
              </div>
              <div>
                <label htmlFor="w2-reg-sha" style={{ display: 'block', fontSize: '11px', color: '#8b949e', marginBottom: '4px' }}>
                  Content SHA256 (64자 16진수) *
                </label>
                <input
                  id="w2-reg-sha"
                  data-testid="input-register-sha256"
                  type="text"
                  placeholder="64자 16진수 해시"
                  value={regSha256}
                  onChange={(e) => handleRegShaChange(e.target.value)}
                  style={{
                    width: '100%',
                    padding: '8px 10px',
                    backgroundColor: '#0d1117',
                    border: '1px solid #30363d',
                    borderRadius: '6px',
                    color: '#c9d1d9',
                    fontSize: '13px',
                    fontFamily: 'var(--font-mono, monospace)',
                  }}
                />
              </div>
              <div>
                <label htmlFor="w2-reg-bytes" style={{ display: 'block', fontSize: '11px', color: '#8b949e', marginBottom: '4px' }}>
                  Byte Size (바이트 크기 정수)
                </label>
                <input
                  id="w2-reg-bytes"
                  data-testid="input-register-bytesize"
                  type="text"
                  inputMode="numeric"
                  value={regByteSize}
                  onChange={(e) => handleRegByteSizeChange(e.target.value)}
                  style={{
                    width: '100%',
                    padding: '8px 10px',
                    backgroundColor: '#0d1117',
                    border: '1px solid #30363d',
                    borderRadius: '6px',
                    color: '#c9d1d9',
                    fontSize: '13px',
                    fontFamily: 'var(--font-mono, monospace)',
                  }}
                />
              </div>
              <div>
                <label htmlFor="w2-reg-uri" style={{ display: 'block', fontSize: '11px', color: '#8b949e', marginBottom: '4px' }}>
                  스토리지 URI (선택)
                </label>
                <input
                  id="w2-reg-uri"
                  data-testid="input-register-uri"
                  type="text"
                  placeholder="inv://models/..."
                  value={regUri}
                  onChange={(e) => setRegUri(e.target.value)}
                  style={{
                    width: '100%',
                    padding: '8px 10px',
                    backgroundColor: '#0d1117',
                    border: '1px solid #30363d',
                    borderRadius: '6px',
                    color: '#c9d1d9',
                    fontSize: '13px',
                  }}
                />
              </div>
            </div>

            <div>
              <Button
                variant="primary"
                size="sm"
                type="submit"
                data-testid="btn-register-version"
                disabled={regLoading || !canApprove}
                aria-disabled={regLoading || !canApprove ? 'true' : 'false'}
              >
                {regLoading ? '등록 중...' : 'W2 모델 버전 등록 제출'}
              </Button>
            </div>

            {regResult && (
              <div
                style={{
                  backgroundColor: '#0d1117',
                  border: '1px solid #238636',
                  borderRadius: '6px',
                  padding: '12px',
                  fontSize: '13px',
                  color: '#3fb950',
                }}
              >
                ✔ 모델 버전 등록 성공: <strong>{regResult.modelVersionId}</strong> (Version: {regResult.version}, Stage: {regResult.stage})
              </div>
            )}
          </form>
        )}

        {/* Tab 3: W4 Retention Pin Form */}
        {activeTab === 'pin' && (
          <form onSubmit={handleExtendPin} style={{ display: 'flex', flexDirection: 'column', gap: '14px' }}>
            <h4 style={{ margin: 0, fontSize: '15px', color: '#f0f6fc' }}>
              W4 보존 고정 연장 (POST /projects/:project/models/:model/versions/:version/retention-pin)
            </h4>
            <div style={{ maxWidth: '400px' }}>
              <label htmlFor="w4-pin-until" style={{ display: 'block', fontSize: '11px', color: '#8b949e', marginBottom: '4px' }}>
                보존 고정 만료 일시 (RFC 3339 UTC 예: 2026-12-31T23:59:59Z) *
              </label>
              <input
                id="w4-pin-until"
                data-testid="input-pin-until"
                type="text"
                placeholder="2026-12-31T23:59:59Z"
                value={pinUntil}
                onChange={(e) => handlePinUntilChange(e.target.value)}
                style={{
                  width: '100%',
                  padding: '8px 10px',
                  backgroundColor: '#0d1117',
                  border: '1px solid #30363d',
                  borderRadius: '6px',
                  color: '#c9d1d9',
                  fontSize: '13px',
                  fontFamily: 'var(--font-mono, monospace)',
                }}
              />
            </div>

            <div>
              <Button
                variant="primary"
                size="sm"
                type="submit"
                data-testid="btn-pin-retention"
                disabled={pinLoading || !canApprove}
                aria-disabled={pinLoading || !canApprove ? 'true' : 'false'}
              >
                {pinLoading ? '연장 중...' : 'W4 보존 고정 연장 제출'}
              </Button>
            </div>

            {pinResult && (
              <div
                style={{
                  backgroundColor: '#0d1117',
                  border: '1px solid #238636',
                  borderRadius: '6px',
                  padding: '12px',
                  fontSize: '13px',
                  color: '#3fb950',
                }}
              >
                ✔ 보존 고정 연장 성공: 만료 시각 <strong>{pinResult.retentionPinnedUntil}</strong> (확장 여부: {pinResult.extended ? 'true' : 'false'})
              </div>
            )}
          </form>
        )}

        {/* Tab 4: Model Release Form */}
        {activeTab === 'release' && (
          <form onSubmit={handleReleaseModel} style={{ display: 'flex', flexDirection: 'column', gap: '14px' }}>
            <h4 style={{ margin: 0, fontSize: '15px', color: '#f0f6fc' }}>
              모델 릴리스 (POST /projects/:project/models/:model/versions/:version/release)
            </h4>
            <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fit, minmax(220px, 1fr))', gap: '12px' }}>
              <div>
                <label htmlFor="rel-license" style={{ display: 'block', fontSize: '11px', color: '#8b949e', marginBottom: '4px' }}>
                  라이선스 정책 (SPDX) *
                </label>
                <input
                  id="rel-license"
                  data-testid="input-release-license"
                  type="text"
                  value={relLicensePolicy}
                  onChange={(e) => setRelLicensePolicy(e.target.value)}
                  style={{
                    width: '100%',
                    padding: '8px 10px',
                    backgroundColor: '#0d1117',
                    border: '1px solid #30363d',
                    borderRadius: '6px',
                    color: '#c9d1d9',
                    fontSize: '13px',
                  }}
                />
              </div>
              <div>
                <label htmlFor="rel-class" style={{ display: 'block', fontSize: '11px', color: '#8b949e', marginBottom: '4px' }}>
                  배포 분류 (Classification) *
                </label>
                <select
                  id="rel-class"
                  data-testid="select-release-classification"
                  value={relClassification}
                  onChange={(e) => setRelClassification(e.target.value as any)}
                  style={{
                    width: '100%',
                    padding: '8px 10px',
                    backgroundColor: '#0d1117',
                    border: '1px solid #30363d',
                    borderRadius: '6px',
                    color: '#c9d1d9',
                    fontSize: '13px',
                  }}
                >
                  <option value="internal">internal (사내 전용)</option>
                  <option value="public">public (외부 공개)</option>
                  <option value="restricted">restricted (제한 배포)</option>
                </select>
              </div>
            </div>

            <div style={{ fontSize: '11px', color: '#8b949e' }}>
              <span aria-hidden="true" style={{ marginRight: '4px' }}>ℹ️</span>
              서버는 비멱등 단발 릴리스 요청으로 처리하며, 역추적이 불완전할 경우 409 GRAPH-0002 오류를 반환합니다.
            </div>

            <div>
              <Button
                variant="primary"
                size="sm"
                type="submit"
                data-testid="btn-release-model"
                disabled={relLoading || !canApprove}
                aria-disabled={relLoading || !canApprove ? 'true' : 'false'}
              >
                {relLoading ? '릴리스 중...' : '모델 릴리스 실행'}
              </Button>
            </div>

            {relResult && (
              <div
                style={{
                  backgroundColor: '#0d1117',
                  border: '1px solid #238636',
                  borderRadius: '6px',
                  padding: '12px',
                  fontSize: '13px',
                  color: '#3fb950',
                }}
              >
                ✔ 모델 릴리스 성공: <strong>{relResult.modelVersionId}</strong> (Stage: {relResult.stage})
              </div>
            )}
          </form>
        )}
      </div>

      {/* Real Multi-LLM Provider Adapter Conformance Panel (G-03 Phase 1: GET /v1/projects/{project_id}/adapters/conformance) */}
      <div
        data-testid="adapter-conformance-panel"
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
            <h4 style={{ margin: 0, fontSize: '15px', color: '#f0f6fc' }}>
              Multi-LLM Provider Adapter Conformance (G-03 1단계 API 연동)
            </h4>
            <p style={{ margin: '4px 0 0 0', fontSize: '12px', color: '#8b949e' }}>
              컨트롤 플레인 호스트의 실제 어댑터 적합성 상태를 조회합니다. 1단계는 저장된 결과가 없어 정직하게 <code style={{ color: '#e3b341' }}>NOT_OBSERVED</code>(미측정) 및 정본 체크리스트 규격을 반환합니다.
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
          {conformanceLiveStatus}
        </div>

        {conformanceError && (
          <div
            role="alert"
            data-testid="conformance-error-banner"
            style={{
              padding: '10px 14px',
              borderRadius: '6px',
              fontSize: '13px',
              backgroundColor: 'rgba(248, 81, 73, 0.15)',
              border: '1px solid #f85149',
              color: '#f85149',
            }}
          >
            <span aria-hidden="true" style={{ marginRight: '6px' }}>❌</span>
            {conformanceError.code && conformanceError.status ? `[${conformanceError.code}] (${conformanceError.status}) ${conformanceError.title ? `${conformanceError.title}: ` : ''}` : ''}{conformanceError.detail}
          </div>
        )}

        {conformanceData && (
          <div
            data-testid="conformance-result-container"
            style={{
              backgroundColor: '#0d1117',
              border: '1px solid #30363d',
              borderRadius: '6px',
              padding: '16px',
              display: 'flex',
              flexDirection: 'column',
              gap: '14px',
            }}
          >
            {/* Meta summary badges */}
            <div style={{ display: 'flex', gap: '10px', flexWrap: 'wrap', alignItems: 'center' }}>
              <span
                data-testid="conformance-overall-status"
                style={{
                  padding: '2px 8px',
                  borderRadius: '4px',
                  fontSize: '11px',
                  fontWeight: 600,
                  backgroundColor: 'rgba(240, 136, 62, 0.15)',
                  color: '#f0883e',
                  border: '1px solid #f0883e',
                }}
              >
                전체 상태: NOT_OBSERVED (미측정)
              </span>
              <span style={{ fontSize: '12px', color: '#8b949e' }}>
                체크리스트 버전: <code data-testid="conformance-checklist-version" style={{ color: '#c9d1d9' }}>{conformanceData.checklistVersion}</code>
              </span>
              <span style={{ fontSize: '12px', color: '#8b949e' }}>
                총 <strong style={{ color: '#f0f6fc' }}>{conformanceData.totalChecks}</strong>개 항목 중 <strong style={{ color: '#f0f6fc' }}>{conformanceData.observedChecks}</strong>개 관측됨
              </span>
            </div>

            {/* Checklist Table */}
            <div style={{ overflowX: 'auto' }}>
              <table style={{ width: '100%', borderCollapse: 'collapse', fontSize: '12px' }}>
                <thead>
                  <tr style={{ borderBottom: '1px solid #30363d', textAlign: 'left', color: '#8b949e' }}>
                    <th style={{ padding: '8px' }}>체크 ID</th>
                    <th style={{ padding: '8px' }}>공통 계약 불변식 (Invariants)</th>
                    <th style={{ padding: '8px' }}>분류</th>
                    <th style={{ padding: '8px' }}>측정 상태</th>
                  </tr>
                </thead>
                <tbody>
                  {conformanceData.checks.map((check, idx) => (
                    <tr key={check.checkId} style={{ borderBottom: '1px solid #21262d' }}>
                      <td style={{ padding: '8px', fontFamily: 'var(--font-mono, monospace)', color: '#58a6ff' }}>
                        {check.checkId}
                      </td>
                      <td style={{ padding: '8px', color: '#f0f6fc' }}>
                        {check.description}
                      </td>
                      <td style={{ padding: '8px' }}>
                        <span
                          style={{
                            padding: '2px 6px',
                            borderRadius: '4px',
                            fontSize: '10px',
                            backgroundColor: check.capabilityGated ? 'rgba(88, 166, 255, 0.15)' : 'rgba(139, 148, 158, 0.15)',
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
            <span aria-hidden="true" style={{ marginRight: '6px' }}>❌</span>
            {commitmentError.code && commitmentError.status ? `[${commitmentError.code}] (${commitmentError.status}) ${commitmentError.title ? `${commitmentError.title}: ` : ''}` : ''}{commitmentError.detail}
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
