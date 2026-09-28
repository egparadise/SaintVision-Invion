import React, { useState, useEffect, useRef } from 'react';
import { ModelLineage, ModelCommitObservation, ProblemDetails } from '@/contracts/types';
import type { ConformanceStatusResponse } from '@/contracts/conformance-status-response';
import type { ModelVersionResponse } from '@/contracts/model-version-response';
import type { RetentionPinResponse } from '@/contracts/retention-pin-response';
import type { ModelReleaseResponse } from '@/contracts/model-release-response';
import type { ModelLineageTraceResponse } from '@/contracts/model-lineage-trace-response';
import { Button } from '@/shared/ui/Button';
import { fetchModelCommitment } from '@/shared/api/modelCommitmentObservation';
import { fetchConformanceStatus } from '@/shared/api/adapterObservation';
import { modelRegistryObservation } from '@/shared/api/modelRegistryObservation';
import { ApiError } from '@/shared/api/client';
import { MlopsManager } from './mlopsEngine';

const SERVER_KIND_LABELS: Record<string, string> = {
  dataset_version: '데이터셋 버전 (Dataset Version)',
  code_commit: '코드 커밋 (Git Commit)',
  container_image: '컨테이너 이미지 (Container Image)',
  eval_run: '평가 실행 (Evaluation Run)',
  deployment: '배포 이력 (Deployment Record)',
  approval: '승인 기록 (Approval Record)',
};

function isValidIsoDateTime(str: string): boolean {
  if (typeof str !== 'string') return false;
  const regex = /^(\d{4})-(\d{2})-(\d{2})T(\d{2}):(\d{2}):(\d{2})(?:\.\d+)?(Z|[+-]\d{2}:\d{2})$/;
  const match = str.match(regex);
  if (!match) return false;
  const year = parseInt(match[1], 10);
  const month = parseInt(match[2], 10);
  const day = parseInt(match[3], 10);
  const hour = parseInt(match[4], 10);
  const min = parseInt(match[5], 10);
  const sec = parseInt(match[6], 10);
  if (month < 1 || month > 12) return false;
  if (hour < 0 || hour > 23) return false;
  if (min < 0 || min > 59) return false;
  if (sec < 0 || sec > 59) return false;

  const daysInMonth = [31, (year % 4 === 0 && year % 100 !== 0) || year % 400 === 0 ? 29 : 28, 31, 30, 31, 30, 31, 31, 30, 31, 30, 31];
  if (day < 1 || day > daysInMonth[month - 1]) return false;
  return true;
}

export interface ModelLineageViewProps {
  initialLineages?: ModelLineage[];
  currentProjectId?: string;
  projectId?: string;
  currentUser?: { canApprove?: boolean; role?: string; permissions?: string[] };
  initialModelId?: string;
  initialVersion?: string;
}

export const ModelLineageView: React.FC<ModelLineageViewProps> = ({
  initialLineages = [],
  currentProjectId,
  projectId: propProjectId,
  currentUser,
  initialModelId = '',
  initialVersion = '',
}) => {
  const effectiveProjectId = propProjectId || currentProjectId || '';
  const [mlopsManager] = useState<MlopsManager>(() => new MlopsManager(initialLineages));
  const [lineages, setLineages] = useState<ModelLineage[]>(mlopsManager.getLineages());
  const [selectedModelId, setSelectedModelId] = useState<string>(lineages[0]?.modelId || '');
  const [searchQuery, setSearchQuery] = useState('');
  const [approvalInput, setApprovalInput] = useState('');
  const [actionNotice, setActionNotice] = useState<{ type: 'success' | 'error'; text: string } | null>(null);

  // Adapter conformance observation state (G-03 Phase 1)
  const [conformanceProjectId, setConformanceProjectId] = useState(effectiveProjectId);
  const [conformanceData, setConformanceData] = useState<ConformanceStatusResponse | null>(null);
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
      const prob = err instanceof ApiError ? err.problem : (err?.problem || null);
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

  // Model commitment observation state (starts empty, requiring explicit project/model context)
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
        text: `✔ [모의 시뮬레이션] [${res.deployedModel?.modelName}] 로컬 배포 게이트 시뮬레이션 완료 (백엔드 서빙 배포 API 미노출 상태로 실제 인프라 미반영 · Digest: ${res.deployedModel?.deploymentDigest.slice(0, 24)}...)`,
      });
    }
  };

  // --- Real HTTP API / Business Lanes State (Card 94) ---
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

  const abortControllerRef = useRef<AbortController | null>(null);
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
      abortControllerRef.current?.abort();
      regAbortControllerRef.current?.abort();
      pinAbortControllerRef.current?.abort();
      relAbortControllerRef.current?.abort();
    };
  }, []);

  // F1: Fail-closed strict canApprove check. Missing / undefined canApprove is strictly FALSE!
  const canApprove = (currentUser as { canApprove?: boolean } | null | undefined)?.canApprove === true;

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

  // G2 & G3: Invalidate in-flight responses and rotate idempotency keys when form inputs change
  const handleProjectIdChange = (val: string) => {
    setProjectId(val);
    regGenerationRef.current++;
    pinGenerationRef.current++;
    relGenerationRef.current++;
    setRegIdempotencyKey(modelRegistryObservation.generateIdempotencyKey('w2'));
    setPinIdempotencyKey(modelRegistryObservation.generateIdempotencyKey('pin'));
  };

  const handleModelIdChange = (val: string) => {
    setModelId(val);
    regGenerationRef.current++;
    pinGenerationRef.current++;
    relGenerationRef.current++;
    setRegIdempotencyKey(modelRegistryObservation.generateIdempotencyKey('w2'));
    setPinIdempotencyKey(modelRegistryObservation.generateIdempotencyKey('pin'));
  };

  const handleVersionChange = (val: string) => {
    setVersion(val);
    regGenerationRef.current++;
    pinGenerationRef.current++;
    relGenerationRef.current++;
    setRegIdempotencyKey(modelRegistryObservation.generateIdempotencyKey('w2'));
    setPinIdempotencyKey(modelRegistryObservation.generateIdempotencyKey('pin'));
  };

  const handleRegVersionChange = (val: string) => {
    setRegVersion(val);
    regGenerationRef.current++;
    setRegIdempotencyKey(modelRegistryObservation.generateIdempotencyKey('w2'));
  };

  const handleRegSha256Change = (val: string) => {
    setRegSha256(val);
    regGenerationRef.current++;
    setRegIdempotencyKey(modelRegistryObservation.generateIdempotencyKey('w2'));
  };

  const handleRegByteSizeChange = (val: string) => {
    setRegByteSize(val);
    regGenerationRef.current++;
    setRegIdempotencyKey(modelRegistryObservation.generateIdempotencyKey('w2'));
  };

  const handlePinUntilChange = (val: string) => {
    setPinUntil(val);
    pinGenerationRef.current++;
    setPinIdempotencyKey(modelRegistryObservation.generateIdempotencyKey('pin'));
  };

  const handleRelLicensePolicyChange = (val: string) => {
    setRelLicensePolicy(val);
    relGenerationRef.current++;
  };

  const handleRelClassificationChange = (val: 'public' | 'internal' | 'restricted') => {
    setRelClassification(val);
    relGenerationRef.current++;
  };

  // Real API Actions: Lineage, Register, Pin, Release
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

    let byteSizeNum = 0;
    if (regByteSize.trim() !== '') {
      if (!/^\d+$/.test(regByteSize.trim())) {
        setGeneralError('byteSize는 0 이상의 정수여야 합니다.');
        return;
      }
      byteSizeNum = Number(regByteSize.trim());
      if (!Number.isSafeInteger(byteSizeNum) || byteSizeNum < 0) {
        setGeneralError('byteSize는 안전한 양의 정수 범위 내여야 합니다.');
        return;
      }
    }

    regAbortControllerRef.current?.abort();
    const ctrl = new AbortController();
    regAbortControllerRef.current = ctrl;
    const currentGen = ++regGenerationRef.current;

    setRegLoading(true);
    setLiveAnnouncement(`버전 [${regVersion}] 등록 요청 중...`);
    try {
      const res = await modelRegistryObservation.registerModelVersion(
        projectId.trim(),
        modelId.trim(),
        {
          version: regVersion.trim(),
          contentSha256: regSha256.trim(),
          byteSize: byteSizeNum,
        },
        { signal: ctrl.signal, idempotencyKey: regIdempotencyKey }
      );
      if (regGenerationRef.current !== currentGen || ctrl.signal.aborted) return;
      setRegResult(res);
      setRegIdempotencyKey(modelRegistryObservation.generateIdempotencyKey('w2'));
      setLiveAnnouncement(`버전 등록 성공: [${res.version}] (ID: ${res.modelVersionId})`);
    } catch (err: unknown) {
      if (regGenerationRef.current !== currentGen || ctrl.signal.aborted) return;
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

    pinAbortControllerRef.current?.abort();
    const ctrl = new AbortController();
    pinAbortControllerRef.current = ctrl;
    const currentGen = ++pinGenerationRef.current;

    setPinLoading(true);
    setLiveAnnouncement(`보존 고정 연장 요청 중 (Until: ${pinUntil})...`);
    try {
      const res = await modelRegistryObservation.extendRetentionPin(
        projectId.trim(),
        modelId.trim(),
        version.trim(),
        { until: pinUntil.trim() },
        { signal: ctrl.signal, idempotencyKey: pinIdempotencyKey }
      );
      if (pinGenerationRef.current !== currentGen || ctrl.signal.aborted) return;
      setPinResult(res);
      setPinIdempotencyKey(modelRegistryObservation.generateIdempotencyKey('pin'));
      setLiveAnnouncement(
        `보존 고정 완료: [${res.version}] ${res.extended ? '연장됨' : '기존 유지 (연장 없음)'} (Pinned Until: ${res.retentionPinnedUntil})`
      );
    } catch (err: unknown) {
      if (pinGenerationRef.current !== currentGen || ctrl.signal.aborted) return;
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

    relAbortControllerRef.current?.abort();
    const ctrl = new AbortController();
    relAbortControllerRef.current = ctrl;
    const currentGen = ++relGenerationRef.current;

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
        },
        { signal: ctrl.signal }
      );
      if (relGenerationRef.current !== currentGen || ctrl.signal.aborted) return;
      setRelResult(res);
      setLiveAnnouncement(`모델 릴리스 성공: [${res.version}] (Stage: ${res.stage})`);
    } catch (err: unknown) {
      if (relGenerationRef.current !== currentGen || ctrl.signal.aborted) return;
      handleApiError(err, '모델 릴리스 실패');
    } finally {
      setRelLoading(false);
    }
  };

  const selectedModel = lineages.find((m) => m.modelId === selectedModelId) || lineages[0];


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
              onChange={(e) => handleProjectIdChange(e.target.value)}
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
              onChange={(e) => handleModelIdChange(e.target.value)}
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
              onChange={(e) => handleVersionChange(e.target.value)}
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
        {!canApprove && (
          <div
            data-testid="banner-no-approve-permission"
            style={{
              fontSize: '12px',
              color: '#f85149',
              backgroundColor: '#3d1214',
              padding: '8px 12px',
              borderRadius: '6px',
              border: '1px solid #f85149',
            }}
          >
            ⚠️ 거버넌스 승인 권한(canApprove)이 없어 조회만 가능합니다. (상태 변경 작업 비활성화)
          </div>
        )}
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
          <form noValidate onSubmit={handleRegisterVersion} style={{ display: 'flex', flexDirection: 'column', gap: '12px' }}>
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
                  onChange={(e) => handleRegVersionChange(e.target.value)}
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
                  onChange={(e) => handleRegSha256Change(e.target.value)}
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
                  type="text"
                  inputMode="numeric"
                  value={regByteSize}
                  onChange={(e) => handleRegByteSizeChange(e.target.value)}
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
          <form noValidate onSubmit={handleExtendPin} style={{ display: 'flex', flexDirection: 'column', gap: '12px' }}>
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
                onChange={(e) => handlePinUntilChange(e.target.value)}
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
          <form noValidate onSubmit={handleReleaseModel} style={{ display: 'flex', flexDirection: 'column', gap: '12px' }}>
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
                  onChange={(e) => handleRelLicensePolicyChange(e.target.value)}
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
                  onChange={(e) => handleRelClassificationChange(e.target.value as any)}
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
            <div style={{ fontSize: '11px', color: '#8b949e', backgroundColor: '#161b22', padding: '8px', borderRadius: '4px' }}>
              ℹ️ Release는 서버 계약상 Idempotency-Key를 수신하지 않으므로 in-flight 이중 제출 방지 가드로 보호됩니다.
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
          {/* Dynamic Unresolved / CountOnly Kinds Honest Cards (Claude G1) */}
          <div
            style={{
              display: 'grid',
              gridTemplateColumns: 'repeat(auto-fit, minmax(240px, 1fr))',
              gap: '12px',
            }}
          >
            {(realTrace.countOnlyKinds && realTrace.countOnlyKinds.length > 0
              ? realTrace.countOnlyKinds
              : ['eval_run', 'code_commit', 'approval', 'container_image']
            ).map((kind) => {
              const unresolvedItem = realTrace.unresolved.find((u) => u.kind === kind);
              const label = SERVER_KIND_LABELS[kind] || `${kind} 항목`;
              const isEval = kind === 'eval_run' || kind === 'evaluations';
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
                  {isEval && (
                    <div style={{ fontSize: '12px', fontWeight: 600, color: '#d29922', marginTop: '4px' }}>
                      정량 평가 점수: NOT_OBSERVED (미관측)
                    </div>
                  )}
                  <div style={{ fontSize: '11px', color: '#8b949e', marginTop: '2px' }}>
                    {isEval
                      ? '응답 스키마에 미포함되어 가짜 점수 합성을 차단합니다.'
                      : '프로젝트 멤버 조회 경계 밖으로 서버에서 미제공됩니다.'}
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
        <>
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
            style={{ fontSize: '18px', fontWeight: 700, color: conformanceError ? '#ff7b72' : conformanceData ? '#f0883e' : '#8b949e', marginTop: '4px' }}
          >
            {conformanceError
              ? '조회 실패'
              : conformanceData
              ? `미측정 (${conformanceData.status})`
              : '미측정 (미조회)'}
          </div>
          <div data-testid="conformance-top-subtext" style={{ fontSize: '12px', color: '#8b949e', marginTop: '4px' }}>
            {conformanceError
              ? '어댑터 conformance 조회 실패'
              : conformanceData
              ? `${conformanceData.checks.length}개 정본 체크 항목 미측정 (${conformanceData.scope})`
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
            `ℹ️ 어댑터 Conformance 조회 완료: 미측정(NOT_OBSERVED) (${conformanceData.checks.length}개 정본 체크 항목)`}
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
