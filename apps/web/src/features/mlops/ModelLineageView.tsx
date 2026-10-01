import React, { useState, useEffect, useRef } from 'react';
import { ModelLineage, ModelCommitObservation, ProblemDetails } from '@/contracts/types';
import type { ModelVersionResponse } from '@/contracts/model-version-response';
import type { RetentionPinResponse } from '@/contracts/retention-pin-response';
import type { ModelReleaseResponse } from '@/contracts/model-release-response';
import type { ModelLineageTraceResponse } from '@/contracts/model-lineage-trace-response';
import type { ModelVerifyResponse } from '@/contracts/model-verify-response';
import type { EvalRunResponse } from '@/contracts/eval-run-response';
import { Button } from '@/shared/ui/Button';
import { fetchModelCommitment } from '@/shared/api/modelCommitmentObservation';
import { fetchConformanceStatus, fetchAdapterConformance, type ConformanceStatusUnion, type AdapterConformanceUnion } from '@/shared/api/adapterObservation';
import { modelRegistryObservation, isValidIsoDateTime } from '@/shared/api/modelRegistryObservation';
import { ApiError } from '@/shared/api/client';
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

const SERVER_KIND_LABELS: Record<string, string> = {
  dataset_version: '데이터셋 버전 (Dataset Version)',
  code_commit: '코드 커밋 (Git Commit)',
  container_image: '컨테이너 이미지 (Container Image)',
  eval_run: '평가 실행 (Evaluation Run)',
  deployment: '배포 이력 (Deployment Record)',
  approval: '승인 기록 (Approval Record)',
};

export interface ModelLineageViewProps {
  initialLineages?: ModelLineage[];
  currentProjectId?: string;
  projectId?: string;
  currentUser?: { canApprove?: boolean; role?: string; permissions?: string[] };
  initialModelId?: string;
  initialVersion?: string;
  modelId?: string;
  version?: string;
  canApprove?: boolean;
}

export const ModelLineageView: React.FC<ModelLineageViewProps> = ({
  initialLineages = [],
  currentProjectId,
  projectId: propProjectId,
  currentUser,
  initialModelId = '',
  initialVersion = '',
  modelId: propModelId,
  version: propVersion,
  canApprove: propCanApprove,
}) => {
  const effectiveProjectId = propProjectId || currentProjectId || '';
  const effectiveInitialModelId = propModelId || initialModelId || '';
  const effectiveInitialVersion = propVersion || initialVersion || '';
  const effectiveCanApprove =
    propCanApprove !== undefined
      ? propCanApprove === true
      : (currentUser as { canApprove?: boolean } | null | undefined)?.canApprove === true;
  const [mlopsManager] = useState<MlopsManager>(() => new MlopsManager(initialLineages));
  const [lineages, setLineages] = useState<ModelLineage[]>(mlopsManager.getLineages());
  const [selectedModelId, setSelectedModelId] = useState<string>(lineages[0]?.modelId || '');
  const [searchQuery, setSearchQuery] = useState('');
  const [approvalInput, setApprovalInput] = useState('');
  const [actionNotice, setActionNotice] = useState<{ type: 'success' | 'error'; text: string } | null>(null);

  // Adapter conformance observation state (G-03 stage one NOT_OBSERVED / stage two RECORDED)
  const [conformanceProjectId, setConformanceProjectId] = useState(effectiveProjectId);
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
    setVerifyResult(null);
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
        text: `✔ [모의 시뮬레이션] [${res.deployedModel?.modelName}] 로컬 배포 게이트 시뮬레이션 완료 (백엔드 서빙 배포 API 미노출 상태로 실제 인프라 미반영 · 백엔드 digest 고정과 무관 · Digest: ${res.deployedModel?.deploymentDigest.slice(0, 24)}...)`,
      });
    }
  };

  // --- Real HTTP API / Business Lanes State (Card 94) ---
  const [projectId, setProjectId] = useState<string>(effectiveProjectId);
  const [modelId, setModelId] = useState<string>(effectiveInitialModelId);
  const [version, setVersion] = useState<string>(effectiveInitialVersion);

  const [activeTab, setActiveTab] = useState<'trace' | 'register' | 'pin' | 'release' | 'verify' | 'eval-run'>('trace');

  // W3 Verify form state
  const [verifyMeasurementId, setVerifyMeasurementId] = useState('');
  const [verifyLoading, setVerifyLoading] = useState(false);
  const [verifyResult, setVerifyResult] = useState<ModelVerifyResponse | null>(null);
  const [verifyTarget, setVerifyTarget] = useState<{ projectId: string; modelId: string; version: string } | null>(null);
  const [verifyIdempotencyKey, setVerifyIdempotencyKey] = useState<string>(() =>
    modelRegistryObservation.generateIdempotencyKey('w3')
  );
  const verifyAbortControllerRef = useRef<AbortController | null>(null);
  const verifyGenerationRef = useRef(0);

  // W5 Eval Run form state
  const [evalSuiteId, setEvalSuiteId] = useState('');
  const [evalAdapter, setEvalAdapter] = useState('codex-cli');
  const [evalPromptVer, setEvalPromptVer] = useState('');
  const [evalCtxVer, setEvalCtxVer] = useState('');
  const [evalRequirePinning, setEvalRequirePinning] = useState(true);
  const [evalLoading, setEvalLoading] = useState(false);
  const [evalResult, setEvalResult] = useState<EvalRunResponse | null>(null);
  const [evalTarget, setEvalTarget] = useState<{ projectId: string; suiteId: string } | null>(null);
  const [evalIdempotencyKey, setEvalIdempotencyKey] = useState<string>(() =>
    modelRegistryObservation.generateIdempotencyKey('w5')
  );
  const evalAbortControllerRef = useRef<AbortController | null>(null);
  const evalGenerationRef = useRef(0);
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

  // Release form state (Card 118: server idempotency contract active)
  const [relLicensePolicy, setRelLicensePolicy] = useState('Apache-2.0');
  const [relClassification, setRelClassification] = useState<'public' | 'internal' | 'restricted'>('internal');
  const [relLoading, setRelLoading] = useState(false);
  const [relResult, setRelResult] = useState<ModelReleaseResponse | null>(null);
  const [relIsReplay, setRelIsReplay] = useState(false);

  // Idempotency keys preserved per submission intent
  const [regIdempotencyKey, setRegIdempotencyKey] = useState<string>(() =>
    modelRegistryObservation.generateIdempotencyKey('w2')
  );
  const [pinIdempotencyKey, setPinIdempotencyKey] = useState<string>(() =>
    modelRegistryObservation.generateIdempotencyKey('pin')
  );
  const [relIdempotencyKey, setRelIdempotencyKey] = useState<string>(() =>
    modelRegistryObservation.generateIdempotencyKey('rel')
  );
  const submittedRelKeysRef = useRef<Set<string>>(new Set());

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
      verifyAbortControllerRef.current?.abort();
      verifyAbortControllerRef.current = null;
      evalAbortControllerRef.current?.abort();
      evalAbortControllerRef.current = null;
      regAbortControllerRef.current?.abort();
      regAbortControllerRef.current = null;
      pinAbortControllerRef.current?.abort();
      pinAbortControllerRef.current = null;
      relAbortControllerRef.current?.abort();
      relAbortControllerRef.current = null;
      verifyGenerationRef.current++;
      evalGenerationRef.current++;
      regGenerationRef.current++;
      pinGenerationRef.current++;
      relGenerationRef.current++;
      setVerifyLoading(false);
      setEvalLoading(false);
      setRegLoading(false);
      setPinLoading(false);
        setVerifyResult(null);
      setVerifyTarget(null);
      setEvalResult(null);
      setEvalTarget(null);
      setVerifyIdempotencyKey(modelRegistryObservation.generateIdempotencyKey('w3'));
      setEvalIdempotencyKey(modelRegistryObservation.generateIdempotencyKey('w5'));
      setRegIdempotencyKey(modelRegistryObservation.generateIdempotencyKey('w2'));
      setPinIdempotencyKey(modelRegistryObservation.generateIdempotencyKey('pin'));
    }
  }, [effectiveProjectId]);

  useEffect(() => {
    return () => {
      abortControllerRef.current?.abort();
      regAbortControllerRef.current?.abort();
      pinAbortControllerRef.current?.abort();
      relAbortControllerRef.current?.abort();
      verifyAbortControllerRef.current?.abort();
      evalAbortControllerRef.current?.abort();
    };
  }, []);

  // F1: Fail-closed strict canApprove check. Missing / undefined canApprove is strictly FALSE!
  const canApprove = effectiveCanApprove;

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

  // G2 & G3 & Card 138 & H2: Invalidate in-flight responses, reset results, and rotate idempotency keys when form inputs change
  const handleProjectIdChange = (val: string) => {
    setProjectId(val);
    setVerifyResult(null);
    setVerifyTarget(null);
    setEvalResult(null);
    setEvalTarget(null);
    verifyAbortControllerRef.current?.abort();
    verifyAbortControllerRef.current = null;
    evalAbortControllerRef.current?.abort();
    evalAbortControllerRef.current = null;
    regAbortControllerRef.current?.abort();
    regAbortControllerRef.current = null;
    pinAbortControllerRef.current?.abort();
    pinAbortControllerRef.current = null;
    relAbortControllerRef.current?.abort();
    relAbortControllerRef.current = null;
    regGenerationRef.current++;
    pinGenerationRef.current++;
    relGenerationRef.current++;
    verifyGenerationRef.current++;
    evalGenerationRef.current++;
    setVerifyLoading(false);
    setEvalLoading(false);
    setRegLoading(false);
    setPinLoading(false);
    setRelLoading(false);
    setRegIdempotencyKey(modelRegistryObservation.generateIdempotencyKey('w2'));
    setPinIdempotencyKey(modelRegistryObservation.generateIdempotencyKey('pin'));
    setRelIdempotencyKey(modelRegistryObservation.generateIdempotencyKey('rel'));
    setVerifyIdempotencyKey(modelRegistryObservation.generateIdempotencyKey('w3'));
    setEvalIdempotencyKey(modelRegistryObservation.generateIdempotencyKey('w5'));
  };

  const handleModelIdChange = (val: string) => {
    setModelId(val);
    setVerifyResult(null);
    setVerifyTarget(null);
    verifyAbortControllerRef.current?.abort();
    verifyAbortControllerRef.current = null;
    regAbortControllerRef.current?.abort();
    regAbortControllerRef.current = null;
    pinAbortControllerRef.current?.abort();
    pinAbortControllerRef.current = null;
    relAbortControllerRef.current?.abort();
    relAbortControllerRef.current = null;
    regGenerationRef.current++;
    pinGenerationRef.current++;
    relGenerationRef.current++;
    verifyGenerationRef.current++;
    setVerifyLoading(false);
    setRegLoading(false);
    setPinLoading(false);
    setRelLoading(false);
    setRegIdempotencyKey(modelRegistryObservation.generateIdempotencyKey('w2'));
    setPinIdempotencyKey(modelRegistryObservation.generateIdempotencyKey('pin'));
    setRelIdempotencyKey(modelRegistryObservation.generateIdempotencyKey('rel'));
    setVerifyIdempotencyKey(modelRegistryObservation.generateIdempotencyKey('w3'));
  };

  const handleVersionChange = (val: string) => {
    setVersion(val);
    setVerifyResult(null);
    setVerifyTarget(null);
    verifyAbortControllerRef.current?.abort();
    verifyAbortControllerRef.current = null;
    regAbortControllerRef.current?.abort();
    regAbortControllerRef.current = null;
    pinAbortControllerRef.current?.abort();
    pinAbortControllerRef.current = null;
    relAbortControllerRef.current?.abort();
    relAbortControllerRef.current = null;
    regGenerationRef.current++;
    pinGenerationRef.current++;
    relGenerationRef.current++;
    verifyGenerationRef.current++;
    setVerifyLoading(false);
    setRegLoading(false);
    setPinLoading(false);
    setRelLoading(false);
    setRegIdempotencyKey(modelRegistryObservation.generateIdempotencyKey('w2'));
    setPinIdempotencyKey(modelRegistryObservation.generateIdempotencyKey('pin'));
    setRelIdempotencyKey(modelRegistryObservation.generateIdempotencyKey('rel'));
    setVerifyIdempotencyKey(modelRegistryObservation.generateIdempotencyKey('w3'));
  };


  const handleRegVersionChange = (val: string) => {
    setRegVersion(val);
    regAbortControllerRef.current?.abort();
    regAbortControllerRef.current = null;
    regGenerationRef.current++;
    setRegLoading(false);
    setRegIdempotencyKey(modelRegistryObservation.generateIdempotencyKey('w2'));
  };

  const handleRegSha256Change = (val: string) => {
    setRegSha256(val);
    regAbortControllerRef.current?.abort();
    regAbortControllerRef.current = null;
    regGenerationRef.current++;
    setRegLoading(false);
    setRegIdempotencyKey(modelRegistryObservation.generateIdempotencyKey('w2'));
  };

  const handleRegByteSizeChange = (val: string) => {
    setRegByteSize(val);
    regAbortControllerRef.current?.abort();
    regAbortControllerRef.current = null;
    regGenerationRef.current++;
    setRegLoading(false);
    setRegIdempotencyKey(modelRegistryObservation.generateIdempotencyKey('w2'));
  };

  const handlePinUntilChange = (val: string) => {
    setPinUntil(val);
    pinAbortControllerRef.current?.abort();
    pinAbortControllerRef.current = null;
    pinGenerationRef.current++;
    setPinLoading(false);
    setPinIdempotencyKey(modelRegistryObservation.generateIdempotencyKey('pin'));
  };

  const handleRelLicensePolicyChange = (val: string) => {
    setRelLicensePolicy(val);
    relAbortControllerRef.current?.abort();
    relAbortControllerRef.current = null;
    relGenerationRef.current++;
    setRelLoading(false);
    setRelIdempotencyKey(modelRegistryObservation.generateIdempotencyKey('rel'));
  };

  const handleRelClassificationChange = (val: 'public' | 'internal' | 'restricted') => {
    setRelClassification(val);
    relAbortControllerRef.current?.abort();
    relAbortControllerRef.current = null;
    relGenerationRef.current++;
    setRelLoading(false);
    setRelIdempotencyKey(modelRegistryObservation.generateIdempotencyKey('rel'));
  };

  const handleVerifyMeasurementIdChange = (val: string) => {
    setVerifyMeasurementId(val);
    setVerifyResult(null);
    setVerifyTarget(null);
    verifyAbortControllerRef.current?.abort();
    verifyAbortControllerRef.current = null;
    verifyGenerationRef.current++;
    setVerifyLoading(false);
    setVerifyIdempotencyKey(modelRegistryObservation.generateIdempotencyKey('w3'));
  };

  const handleEvalSuiteIdChange = (val: string) => {
    setEvalSuiteId(val);
    setEvalResult(null);
    setEvalTarget(null);
    evalAbortControllerRef.current?.abort();
    evalAbortControllerRef.current = null;
    evalGenerationRef.current++;
    setEvalLoading(false);
    setEvalIdempotencyKey(modelRegistryObservation.generateIdempotencyKey('w5'));
  };

  const handleEvalAdapterChange = (val: string) => {
    setEvalAdapter(val);
    setEvalResult(null);
    setEvalTarget(null);
    evalAbortControllerRef.current?.abort();
    evalAbortControllerRef.current = null;
    evalGenerationRef.current++;
    setEvalLoading(false);
    setEvalIdempotencyKey(modelRegistryObservation.generateIdempotencyKey('w5'));
  };

  const handleEvalPromptVerChange = (val: string) => {
    setEvalPromptVer(val);
    setEvalResult(null);
    setEvalTarget(null);
    evalAbortControllerRef.current?.abort();
    evalAbortControllerRef.current = null;
    evalGenerationRef.current++;
    setEvalLoading(false);
    setEvalIdempotencyKey(modelRegistryObservation.generateIdempotencyKey('w5'));
  };

  const handleEvalCtxVerChange = (val: string) => {
    setEvalCtxVer(val);
    setEvalResult(null);
    setEvalTarget(null);
    evalAbortControllerRef.current?.abort();
    evalAbortControllerRef.current = null;
    evalGenerationRef.current++;
    setEvalLoading(false);
    setEvalIdempotencyKey(modelRegistryObservation.generateIdempotencyKey('w5'));
  };

  const handleEvalRequirePinningChange = (checked: boolean) => {
    setEvalRequirePinning(checked);
    setEvalResult(null);
    setEvalTarget(null);
    evalAbortControllerRef.current?.abort();
    evalAbortControllerRef.current = null;
    evalGenerationRef.current++;
    setEvalLoading(false);
    setEvalIdempotencyKey(modelRegistryObservation.generateIdempotencyKey('w5'));
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
      if (regAbortControllerRef.current === ctrl || regGenerationRef.current === currentGen) {
        setRegLoading(false);
      }
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
      if (pinAbortControllerRef.current === ctrl || pinGenerationRef.current === currentGen) {
        setPinLoading(false);
      }
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

    const isReplaySubmission = submittedRelKeysRef.current.has(relIdempotencyKey);
    // Key is recorded at transmission time (regardless of outcome) so that retries with the same key are identified as resubmissions
    submittedRelKeysRef.current.add(relIdempotencyKey);

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
        { signal: ctrl.signal, idempotencyKey: relIdempotencyKey }
      );
      if (relGenerationRef.current !== currentGen || ctrl.signal.aborted) return;
      setRelResult(res);
      setRelIsReplay(isReplaySubmission);
      // Key rotates ONLY after success!
      setRelIdempotencyKey(modelRegistryObservation.generateIdempotencyKey('rel'));
      if (isReplaySubmission) {
        setLiveAnnouncement(`재시도 응답 수신(서버 원장 결과): [${res.version}] (Stage: ${res.stage})`);
      } else {
        setLiveAnnouncement(`신규 모델 릴리스 완료: [${res.version}] (Stage: ${res.stage})`);
      }
    } catch (err: unknown) {
      if (relGenerationRef.current !== currentGen || ctrl.signal.aborted) return;
      handleApiError(err, '모델 릴리스 실패');
      // On failure, Idempotency-Key is preserved for retry!
    } finally {
      if (relGenerationRef.current === currentGen || relAbortControllerRef.current === ctrl) {
        setRelLoading(false);
      }
    }
  };

  const handleVerifyVersion = async (e: React.FormEvent) => {
    e.preventDefault();
    clearErrors();
    setVerifyResult(null);
    if (!canApprove) {
      setGeneralError('승인 권한(canApprove)이 없는 계정은 모델 버전을 검증할 수 없습니다.');
      return;
    }
    if (verifyLoading) return;
    if (!projectId.trim() || !modelId.trim() || !version.trim()) {
      setGeneralError('프로젝트 ID, 모델 ID, 버전을 확인하세요.');
      return;
    }
    const mId = verifyMeasurementId.trim();
    if (!mId) {
      setGeneralError('측정 ID(measurementId)를 입력해야 합니다.');
      return;
    }
    if (!/^mvm_[0-9A-HJKMNP-TV-Z]{26}$/.test(mId)) {
      setGeneralError('유효한 측정 ID 형식(mvm_... 26자리 Crockford Base32)이어야 합니다.');
      return;
    }

    verifyAbortControllerRef.current?.abort();
    const ctrl = new AbortController();
    verifyAbortControllerRef.current = ctrl;
    const currentGen = ++verifyGenerationRef.current;

    setVerifyLoading(true);
    setLiveAnnouncement(`모델 [${modelId}:${version}] W3 커널 측정 검증 요청 중...`);
    try {
      const res = await modelRegistryObservation.verifyModelVersion(
        projectId.trim(),
        modelId.trim(),
        version.trim(),
        { measurementId: mId },
        { signal: ctrl.signal, idempotencyKey: verifyIdempotencyKey }
      );
      if (verifyGenerationRef.current !== currentGen || ctrl.signal.aborted) return;
      setVerifyResult(res);
      setVerifyTarget({ projectId: projectId.trim(), modelId: modelId.trim(), version: version.trim() });
      setVerifyIdempotencyKey(modelRegistryObservation.generateIdempotencyKey('w3'));
      setLiveAnnouncement(
        `W3 커널 측정 검증 완료: ${modelId.trim()}:${version.trim()} (${res.newlyVerified ? '새로 검증됨' : '이미 검증됨'})`
      );
    } catch (err: unknown) {
      if (verifyGenerationRef.current !== currentGen || ctrl.signal.aborted) return;
      setVerifyResult(null);
      handleApiError(err, 'W3 커널 측정 검증 실패');
    } finally {
      if (verifyAbortControllerRef.current === ctrl || verifyGenerationRef.current === currentGen) {
        setVerifyLoading(false);
      }
    }
  };

  const handleStartEvalRun = async (e: React.FormEvent) => {
    e.preventDefault();
    clearErrors();
    setEvalResult(null);
    if (!canApprove) {
      setGeneralError('승인 권한(canApprove)이 없는 계정은 평가 스위트를 실행할 수 없습니다.');
      return;
    }
    if (evalLoading) return;
    if (!projectId.trim() || !evalSuiteId.trim()) {
      setGeneralError('프로젝트 ID와 평가 스위트 ID를 확인하세요.');
      return;
    }
    const adapterTrimmed = evalAdapter.trim();
    if (!adapterTrimmed) {
      setGeneralError('어댑터 식별자(adapter)를 입력해야 합니다.');
      return;
    }
    if (!/^[a-z0-9-]+$/.test(adapterTrimmed)) {
      setGeneralError('어댑터 식별자는 소문자, 숫자, 하이픈만 허용됩니다.');
      return;
    }

    evalAbortControllerRef.current?.abort();
    const ctrl = new AbortController();
    evalAbortControllerRef.current = ctrl;
    const currentGen = ++evalGenerationRef.current;

    setEvalLoading(true);
    setLiveAnnouncement(`W5 평가 실행 요청 중 (스위트: ${evalSuiteId})...`);

    const componentVersions: Record<string, string> = {};
    if (evalPromptVer.trim()) componentVersions.prompt = evalPromptVer.trim();
    if (evalCtxVer.trim()) componentVersions.context = evalCtxVer.trim();

    try {
      const res = await modelRegistryObservation.startEvalRun(
        projectId.trim(),
        evalSuiteId.trim(),
        {
          adapter: adapterTrimmed,
          requireModelPinning: evalRequirePinning,
          ...(Object.keys(componentVersions).length > 0 ? { componentVersions } : {}),
        },
        { signal: ctrl.signal, idempotencyKey: evalIdempotencyKey }
      );
      if (evalGenerationRef.current !== currentGen || ctrl.signal.aborted) return;
      setEvalResult(res);
      setEvalTarget({ projectId: projectId.trim(), suiteId: evalSuiteId.trim() });
      setEvalIdempotencyKey(modelRegistryObservation.generateIdempotencyKey('w5'));
      setLiveAnnouncement(`W5 평가 실행 완료: ${res.evalRunId}`);
    } catch (err: unknown) {
      if (evalGenerationRef.current !== currentGen || ctrl.signal.aborted) return;
      setEvalResult(null);
      handleApiError(err, 'W5 평가 실행 실패');
    } finally {
      if (evalAbortControllerRef.current === ctrl || evalGenerationRef.current === currentGen) {
        setEvalLoading(false);
      }
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
          backgroundColor: 'var(--color-bg-surface)',
          border: '1px solid var(--color-border-subtle)',
          borderRadius: '8px',
          padding: '20px',
          display: 'flex',
          flexDirection: 'column',
          gap: '16px',
        }}
      >
        <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', flexWrap: 'wrap', gap: '10px' }}>
          <div>
            <h2 style={{ margin: 0, fontSize: '18px', color: 'var(--color-text-primary)', fontWeight: 600 }}>
              Model Registry & Lineage Business Control (G-05)
            </h2>
            <p style={{ margin: '4px 0 0 0', fontSize: '12px', color: 'var(--color-text-muted)' }}>
              서버 정본 비즈니스 경로(Lineage 조회 · W2 등록 · W4 보존 연장 · 릴리스)와 1:1 결합된 엔터프라이즈 레지스트리
            </p>
          </div>
          {/* W3 Seam Badge */}
          <span
            data-testid="badge-w3-verify-seam"
            style={{
              padding: '4px 10px',
              borderRadius: '4px',
              fontSize: '11px',
              fontWeight: 600,
              backgroundColor:
                verifyResult &&
                verifyTarget &&
                verifyTarget.projectId === projectId.trim() &&
                verifyTarget.modelId === modelId.trim() &&
                verifyTarget.version === version.trim() &&
                verifyResult.modelId === modelId.trim() &&
                verifyResult.version === version.trim()
                  ? 'var(--color-brand-primary-bg)'
                  : 'var(--color-bg-subtle)',
              border:
                verifyResult &&
                verifyTarget &&
                verifyTarget.projectId === projectId.trim() &&
                verifyTarget.modelId === modelId.trim() &&
                verifyTarget.version === version.trim() &&
                verifyResult.modelId === modelId.trim() &&
                verifyResult.version === version.trim()
                  ? '1px solid var(--color-brand-primary)'
                  : '1px solid var(--color-border-subtle)',
              color:
                verifyResult &&
                verifyTarget &&
                verifyTarget.projectId === projectId.trim() &&
                verifyTarget.modelId === modelId.trim() &&
                verifyTarget.version === version.trim() &&
                verifyResult.modelId === modelId.trim() &&
                verifyResult.version === version.trim()
                  ? 'var(--color-brand-primary-fg)'
                  : 'var(--color-text-muted)',
            }}
          >
            {verifyResult &&
            verifyTarget &&
            verifyTarget.projectId === projectId.trim() &&
            verifyTarget.modelId === modelId.trim() &&
            verifyTarget.version === version.trim() &&
            verifyResult.modelId === modelId.trim() &&
            verifyResult.version === version.trim()
              ? `W3 검증: 검증 완료 (측정: ${verifyResult.verifiedMeasurementId})`
              : 'W3 검증: 미검증 (커널 계측 검증 대기)'}
          </span>
        </div>
        {/* Global Resource Binding Inputs */}
        <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fit, minmax(200px, 1fr))', gap: '12px' }}>
          <div>
            <label htmlFor="reg-project-id" style={{ display: 'block', fontSize: '11px', color: 'var(--color-text-muted)', marginBottom: '4px' }}>
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
                backgroundColor: 'var(--color-bg-subtle)',
                border: '1px solid var(--color-border-subtle)',
                borderRadius: '6px',
                color: 'var(--color-text-primary)',
                fontSize: '12px',
                fontFamily: 'var(--font-mono, monospace)',
                boxSizing: 'border-box',
              }}
            />
          </div>
          <div>
            <label htmlFor="reg-model-id" style={{ display: 'block', fontSize: '11px', color: 'var(--color-text-muted)', marginBottom: '4px' }}>
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
                padding: '6px 10px',
                backgroundColor: 'var(--color-bg-subtle)',
                border: '1px solid var(--color-border-subtle)',
                borderRadius: '6px',
                color: 'var(--color-text-primary)',
                fontSize: '12px',
                fontFamily: 'var(--font-mono, monospace)',
                boxSizing: 'border-box',
              }}
            />
          </div>
          <div>
            <label htmlFor="reg-version" style={{ display: 'block', fontSize: '11px', color: 'var(--color-text-muted)', marginBottom: '4px' }}>
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
                backgroundColor: 'var(--color-bg-subtle)',
                border: '1px solid var(--color-border-subtle)',
                borderRadius: '6px',
                color: 'var(--color-text-primary)',
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
              color: 'var(--color-status-offline)',
              backgroundColor: 'var(--color-bg-subtle)',
              padding: '8px 12px',
              borderRadius: '6px',
              border: '1px solid var(--color-status-offline)',
            }}
          >
            ⚠️ 거버넌스 승인 권한(canApprove)이 없어 조회만 가능합니다. (상태 변경 작업 비활성화)
          </div>
        )}
        {/* Action Tabs Navigation */}
        <div style={{ display: 'flex', gap: '8px', borderBottom: '1px solid var(--color-border-subtle)', paddingBottom: '10px' }}>
          <button
            type="button"
            data-testid="tab-trace"
            onClick={() => setActiveTab('trace')}
            style={{
              padding: '6px 14px',
              borderRadius: '6px',
              border: activeTab === 'trace' ? '1px solid var(--color-brand-primary)' : '1px solid transparent',
              backgroundColor: activeTab === 'trace' ? 'var(--color-bg-subtle)' : 'transparent',
              color: activeTab === 'trace' ? 'var(--color-brand-primary)' : 'var(--color-text-muted)',
              cursor: 'pointer',
              fontSize: '12px',
              fontWeight: 600,
            }}
          >
            🔍 계보 조회 (Trace Lineage)
          </button>
          <button
            type="button"
            data-testid="tab-register"
            onClick={() => setActiveTab('register')}
            style={{
              padding: '6px 14px',
              borderRadius: '6px',
              border: activeTab === 'register' ? '1px solid var(--color-brand-primary)' : '1px solid transparent',
              backgroundColor: activeTab === 'register' ? 'var(--color-bg-subtle)' : 'transparent',
              color: activeTab === 'register' ? 'var(--color-brand-primary)' : 'var(--color-text-muted)',
              cursor: 'pointer',
              fontSize: '12px',
              fontWeight: 600,
            }}
          >
            📦 버전 등록 (W2 Register)
          </button>
          <button
            type="button"
            data-testid="tab-pin"
            onClick={() => setActiveTab('pin')}
            style={{
              padding: '6px 14px',
              borderRadius: '6px',
              border: activeTab === 'pin' ? '1px solid var(--color-brand-primary)' : '1px solid transparent',
              backgroundColor: activeTab === 'pin' ? 'var(--color-bg-subtle)' : 'transparent',
              color: activeTab === 'pin' ? 'var(--color-brand-primary)' : 'var(--color-text-muted)',
              cursor: 'pointer',
              fontSize: '12px',
              fontWeight: 600,
            }}
          >
            📌 보존 고정 (W4 Pin)
          </button>
          <button
            type="button"
            data-testid="tab-release"
            onClick={() => setActiveTab('release')}
            style={{
              padding: '6px 14px',
              borderRadius: '6px',
              border: activeTab === 'release' ? '1px solid var(--color-brand-primary)' : '1px solid transparent',
              backgroundColor: activeTab === 'release' ? 'var(--color-bg-subtle)' : 'transparent',
              color: activeTab === 'release' ? 'var(--color-brand-primary)' : 'var(--color-text-muted)',
              cursor: 'pointer',
              fontSize: '12px',
              fontWeight: 600,
            }}
          >
            🚀 모델 릴리스 (Release)
          </button>
          <button
            type="button"
            data-testid="tab-verify"
            onClick={() => setActiveTab('verify')}
            style={{
              padding: '6px 14px',
              borderRadius: '6px',
              border: activeTab === 'verify' ? '1px solid var(--color-brand-primary)' : '1px solid transparent',
              backgroundColor: activeTab === 'verify' ? 'var(--color-bg-subtle)' : 'transparent',
              color: activeTab === 'verify' ? 'var(--color-brand-primary)' : 'var(--color-text-muted)',
              cursor: 'pointer',
              fontSize: '12px',
              fontWeight: 600,
            }}
          >
            🛡️ W3 검증 (Verify)
          </button>
          <button
            type="button"
            data-testid="tab-eval-run"
            onClick={() => setActiveTab('eval-run')}
            style={{
              padding: '6px 14px',
              borderRadius: '6px',
              border: activeTab === 'eval-run' ? '1px solid var(--color-brand-primary)' : '1px solid transparent',
              backgroundColor: activeTab === 'eval-run' ? 'var(--color-bg-subtle)' : 'transparent',
              color: activeTab === 'eval-run' ? 'var(--color-brand-primary)' : 'var(--color-text-muted)',
              cursor: 'pointer',
              fontSize: '12px',
              fontWeight: 600,
            }}
          >
            🧪 W5 평가 실행 (Eval)
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
            <span style={{ fontSize: '11px', color: 'var(--color-text-muted)' }}>
              Path: <code>/v1/projects/{projectId || '{project_id}'}/models/{modelId || '{model_id}'}/versions/{version || '{version}'}/lineage</code>
            </span>
          </div>
        )}
        {/* Tab Content: 2. W2 Register */}
        {activeTab === 'register' && (
          <form noValidate onSubmit={handleRegisterVersion} style={{ display: 'flex', flexDirection: 'column', gap: '12px' }}>
            <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fit, minmax(200px, 1fr))', gap: '10px' }}>
              <div>
                <label htmlFor="input-register-version" style={{ display: 'block', fontSize: '11px', color: 'var(--color-text-muted)', marginBottom: '4px' }}>
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
                    backgroundColor: 'var(--color-bg-subtle)',
                    border: '1px solid var(--color-border-subtle)',
                    borderRadius: '4px',
                    color: 'var(--color-text-secondary)',
                    fontSize: '12px',
                    fontFamily: 'var(--font-mono, monospace)',
                    boxSizing: 'border-box',
                  }}
                />
              </div>
              <div>
                <label htmlFor="input-register-sha256" style={{ display: 'block', fontSize: '11px', color: 'var(--color-text-muted)', marginBottom: '4px' }}>
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
                    backgroundColor: 'var(--color-bg-subtle)',
                    border: '1px solid var(--color-border-subtle)',
                    borderRadius: '4px',
                    color: 'var(--color-text-secondary)',
                    fontSize: '12px',
                    fontFamily: 'var(--font-mono, monospace)',
                    boxSizing: 'border-box',
                  }}
                />
              </div>
              <div>
                <label htmlFor="input-register-bytesize" style={{ display: 'block', fontSize: '11px', color: 'var(--color-text-muted)', marginBottom: '4px' }}>
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
                    backgroundColor: 'var(--color-bg-subtle)',
                    border: '1px solid var(--color-border-subtle)',
                    borderRadius: '4px',
                    color: 'var(--color-text-secondary)',
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
                <span style={{ fontSize: '11px', color: 'var(--color-status-degraded)' }}>
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
              <label htmlFor="input-pin-until" style={{ display: 'block', fontSize: '11px', color: 'var(--color-text-muted)', marginBottom: '4px' }}>
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
                  backgroundColor: 'var(--color-bg-subtle)',
                  border: '1px solid var(--color-border-subtle)',
                  borderRadius: '4px',
                  color: 'var(--color-text-secondary)',
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
                <span style={{ fontSize: '11px', color: 'var(--color-status-degraded)' }}>
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
                <label htmlFor="input-release-license" style={{ display: 'block', fontSize: '11px', color: 'var(--color-text-muted)', marginBottom: '4px' }}>
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
                    backgroundColor: 'var(--color-bg-subtle)',
                    border: '1px solid var(--color-border-subtle)',
                    borderRadius: '4px',
                    color: 'var(--color-text-secondary)',
                    fontSize: '12px',
                    boxSizing: 'border-box',
                  }}
                />
              </div>
              <div>
                <label htmlFor="select-release-classification" style={{ display: 'block', fontSize: '11px', color: 'var(--color-text-muted)', marginBottom: '4px' }}>
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
                    backgroundColor: 'var(--color-bg-subtle)',
                    border: '1px solid var(--color-border-subtle)',
                    borderRadius: '4px',
                    color: 'var(--color-text-secondary)',
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
                disabled={relLoading || !canApprove || !projectId.trim() || !modelId.trim() || !version.trim() || !relLicensePolicy.trim()}
                aria-disabled={relLoading || !canApprove || !projectId.trim() || !modelId.trim() || !version.trim() || !relLicensePolicy.trim()}
              >
                {relLoading ? '릴리스 중...' : '모델 릴리스 (POST /release)'}
              </Button>
              {!canApprove && (
                <span style={{ fontSize: '11px', color: 'var(--color-status-degraded)' }}>
                  ⚠️ 승인 권한(canApprove)이 필요한 작업입니다.
                </span>
              )}
            </div>
          </form>
        )}
        {/* Tab Content: 5. W3 Verify */}
        {activeTab === 'verify' && (
          <form noValidate onSubmit={handleVerifyVersion} style={{ display: 'flex', flexDirection: 'column', gap: '12px' }}>
            <div style={{ fontSize: '12px', color: 'var(--color-text-muted)' }}>
              ℹ️ W3 커널 측정 검증: 서버 신뢰 워커(trusted-worker)의 계측 기록(measurementId)을 모델 버전에 결속합니다. 측정값(digest, size 등)은 화면이 조작/생성할 수 없으며 오직 커널 기록된 측정 ID만 전송합니다 (정직성 원칙).
            </div>
            <div>
              <label htmlFor="mvm-measurement-id" style={{ display: 'block', fontSize: '11px', color: 'var(--color-text-muted)', marginBottom: '4px' }}>
                커널 측정 ID (measurementId - mvm_ + 26자리 Crockford Base32) *
              </label>
              <input
                id="mvm-measurement-id"
                data-testid="input-verify-measurement-id"
                type="text"
                placeholder="mvm_01JABCDEF1234567890ABCDEFG"
                value={verifyMeasurementId}
                onChange={(e) => handleVerifyMeasurementIdChange(e.target.value)}
                style={{
                  width: '100%',
                  padding: '6px 10px',
                  backgroundColor: 'var(--color-bg-subtle)',
                  border: '1px solid var(--color-border-subtle)',
                  borderRadius: '4px',
                  color: 'var(--color-text-secondary)',
                  fontSize: '12px',
                  boxSizing: 'border-box',
                }}
              />
            </div>
            <div style={{ display: 'flex', gap: '10px', alignItems: 'center' }}>
              <Button
                size="sm"
                variant="primary"
                type="submit"
                data-testid="btn-verify-model"
                disabled={verifyLoading || !canApprove || !projectId || !modelId || !version}
                aria-disabled={verifyLoading || !canApprove || !projectId || !modelId || !version}
              >
                {verifyLoading ? '검증 처리 중...' : 'W3 커널 측정 검증 제출 (POST /models/.../verify)'}
              </Button>
              {!canApprove && (
                <span style={{ fontSize: '11px', color: 'var(--color-status-degraded)' }}>
                  ⚠️ 승인 권한(canApprove)이 필요한 작업입니다.
                </span>
              )}
            </div>
          </form>
        )}
        {/* Tab Content: 6. W5 Eval Run */}
        {activeTab === 'eval-run' && (
          <form noValidate onSubmit={handleStartEvalRun} style={{ display: 'flex', flexDirection: 'column', gap: '12px' }}>
            <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fit, minmax(220px, 1fr))', gap: '10px' }}>
              <div>
                <label htmlFor="eval-suite-id" style={{ display: 'block', fontSize: '11px', color: 'var(--color-text-muted)', marginBottom: '4px' }}>
                  평가 스위트 ID (suiteId) *
                </label>
                <input
                  id="eval-suite-id"
                  data-testid="input-eval-suite-id"
                  type="text"
                  placeholder="evs_01JABCDEF1234567890ABCDEFG"
                  value={evalSuiteId}
                  onChange={(e) => handleEvalSuiteIdChange(e.target.value)}
                  style={{
                    width: '100%',
                    padding: '6px 10px',
                    backgroundColor: 'var(--color-bg-subtle)',
                    border: '1px solid var(--color-border-subtle)',
                    borderRadius: '4px',
                    color: 'var(--color-text-secondary)',
                    fontSize: '12px',
                    boxSizing: 'border-box',
                  }}
                />
              </div>
              <div>
                <label htmlFor="eval-adapter" style={{ display: 'block', fontSize: '11px', color: 'var(--color-text-muted)', marginBottom: '4px' }}>
                  어댑터 식별자 (adapter - codex-cli | claude-code | gemini-cli | antigravity) *
                </label>
                <select
                  id="eval-adapter"
                  data-testid="input-eval-adapter"
                  value={evalAdapter}
                  onChange={(e) => handleEvalAdapterChange(e.target.value)}
                  style={{
                    width: '100%',
                    padding: '6px 10px',
                    backgroundColor: 'var(--color-bg-subtle)',
                    border: '1px solid var(--color-border-subtle)',
                    borderRadius: '4px',
                    color: 'var(--color-text-secondary)',
                    fontSize: '12px',
                    boxSizing: 'border-box',
                  }}
                >
                  <option value="codex-cli">codex-cli</option>
                  <option value="claude-code">claude-code</option>
                  <option value="gemini-cli">gemini-cli</option>
                  <option value="antigravity">antigravity</option>
                </select>
              </div>
            </div>

            <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fit, minmax(220px, 1fr))', gap: '10px' }}>
              <div>
                <label htmlFor="eval-prompt-ver" style={{ display: 'block', fontSize: '11px', color: 'var(--color-text-muted)', marginBottom: '4px' }}>
                  프롬프트 버전 (promptVersion - 선택)
                </label>
                <input
                  id="eval-prompt-ver"
                  data-testid="input-eval-prompt-ver"
                  type="text"
                  placeholder="pmt_01J11111111111111111111111"
                  value={evalPromptVer}
                  onChange={(e) => handleEvalPromptVerChange(e.target.value)}
                  style={{
                    width: '100%',
                    padding: '6px 10px',
                    backgroundColor: 'var(--color-bg-subtle)',
                    border: '1px solid var(--color-border-subtle)',
                    borderRadius: '4px',
                    color: 'var(--color-text-secondary)',
                    fontSize: '12px',
                    boxSizing: 'border-box',
                  }}
                />
              </div>
              <div>
                <label htmlFor="eval-ctx-ver" style={{ display: 'block', fontSize: '11px', color: 'var(--color-text-muted)', marginBottom: '4px' }}>
                  컨텍스트 버전 (contextVersion - 선택)
                </label>
                <input
                  id="eval-ctx-ver"
                  data-testid="input-eval-ctx-ver"
                  type="text"
                  placeholder="ctx_01J22222222222222222222222"
                  value={evalCtxVer}
                  onChange={(e) => handleEvalCtxVerChange(e.target.value)}
                  style={{
                    width: '100%',
                    padding: '6px 10px',
                    backgroundColor: 'var(--color-bg-subtle)',
                    border: '1px solid var(--color-border-subtle)',
                    borderRadius: '4px',
                    color: 'var(--color-text-secondary)',
                    fontSize: '12px',
                    boxSizing: 'border-box',
                  }}
                />
              </div>
            </div>

            <div style={{ display: 'flex', alignItems: 'center', gap: '8px' }}>
              <input
                id="eval-pinning"
                data-testid="checkbox-eval-pinning"
                type="checkbox"
                checked={evalRequirePinning}
                onChange={(e) => handleEvalRequirePinningChange(e.target.checked)}
              />
              <label htmlFor="eval-pinning" style={{ fontSize: '12px', color: 'var(--color-text-secondary)' }}>
                모델 고정 필수 요구 (requireModelPinning — 재현 불가능한 빌드 차단)
              </label>
            </div>

            <div style={{ fontSize: '11px', color: 'var(--color-text-muted)', backgroundColor: 'var(--color-bg-surface)', padding: '8px', borderRadius: '4px' }}>
              ℹ️ W5 평가는 지정된 어댑터 CLI를 통해 테스트 스위트를 실행하고 엄격한 게이트 판정 결과를 반환합니다.
            </div>

            <div style={{ display: 'flex', gap: '10px', alignItems: 'center' }}>
              <Button
                size="sm"
                variant="primary"
                type="submit"
                data-testid="btn-start-eval-run"
                disabled={evalLoading || !canApprove || !projectId || !evalSuiteId || !evalAdapter}
                aria-disabled={evalLoading || !canApprove || !projectId || !evalSuiteId || !evalAdapter}
              >
                {evalLoading ? '평가 실행 중...' : 'W5 평가 실행 시작 (POST /eval/suites/.../runs)'}
              </Button>
              {!canApprove && (
                <span style={{ fontSize: '11px', color: 'var(--color-status-degraded)' }}>
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
            backgroundColor: 'var(--color-bg-subtle)',
            border: '1px solid var(--color-status-offline)',
            color: 'var(--color-status-offline)',
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
                backgroundColor: 'var(--color-bg-subtle)',
                padding: '2px 8px',
                borderRadius: '4px',
                fontSize: '11px',
                fontWeight: 700,
              }}
            >
              {problemDetails.code}
            </span>
          </div>
          <div data-testid="problem-detail" style={{ marginTop: '6px', color: 'var(--color-status-offline)' }}>
            {problemDetails.detail}
          </div>
          <div style={{ marginTop: '4px', fontSize: '11px', color: 'var(--color-text-muted)', fontFamily: 'var(--font-mono, monospace)' }}>
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
            backgroundColor: 'var(--color-bg-subtle)',
            border: '1px solid var(--color-status-offline)',
            color: 'var(--color-status-offline)',
            fontSize: '13px',
          }}
        >
          {generalError}
        </div>
      )}
      {/* Mutation Results Displays */}
      {verifyResult &&
        verifyTarget &&
        verifyTarget.projectId === projectId.trim() &&
        verifyTarget.modelId === modelId.trim() &&
        verifyTarget.version === version.trim() &&
        verifyResult.modelId === modelId.trim() &&
        verifyResult.version === version.trim() && (
        <div
          role="status"
          data-testid="registry-verify-success"
          className="bg-emerald-950/40"
          style={{
            padding: '14px 18px',
            borderRadius: '8px',
            backgroundColor: 'var(--color-bg-subtle)',
            border: '1px solid var(--color-status-online)',
            color: 'var(--color-status-online)',
            fontSize: '13px',
          }}
        >
          <div style={{ fontWeight: 600 }}>
            ✔ 모델 무결성 검증 완료 (200 OK) — {verifyResult.newlyVerified ? '새로 검증됨' : '이미 검증됨'}
          </div>
          <div style={{ marginTop: '6px', fontSize: '12px', color: 'var(--color-text-secondary)', display: 'grid', gridTemplateColumns: 'repeat(auto-fit, minmax(200px, 1fr))', gap: '8px' }}>
            <div>Version ID: <code>{verifyResult.modelVersionId}</code></div>
            <div>Version: <strong>{verifyResult.version}</strong> (Stage: {verifyResult.stage})</div>
            <div>Content Digest: <code>{verifyResult.contentSha256.slice(0, 16)}...</code></div>
            <div>Verified Measurement: <code data-testid="verified-measurement-id">{verifyResult.verifiedMeasurementId}</code></div>
            <div>Verified At: {verifyResult.verifiedAt}</div>
            <div>Newly Verified: <span data-testid="verify-newly-verified-flag">{String(verifyResult.newlyVerified)}</span></div>
          </div>
        </div>
      )}

      {evalResult &&
        evalTarget &&
        evalTarget.projectId === projectId.trim() &&
        evalTarget.suiteId === evalSuiteId.trim() &&
        evalResult.suiteId === evalSuiteId.trim() && (
        <div
          role="status"
          data-testid="registry-eval-success"
          style={{
            padding: '14px 18px',
            borderRadius: '8px',
            backgroundColor: evalResult.passedGate ? 'var(--color-bg-subtle)' : 'var(--color-bg-subtle)',
            border: evalResult.passedGate ? '1px solid var(--color-status-online)' : '1px solid var(--color-status-offline)',
            color: evalResult.passedGate ? 'var(--color-status-online)' : 'var(--color-status-offline)',
            fontSize: '13px',
          }}
        >
          <div style={{ fontWeight: 600, display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
            <span>
              {evalResult.status === 'completed'
                ? `✔ 평가 스위트 실행 완료 (Status: ${evalResult.status})`
                : evalResult.status === 'aborted'
                ? `⚠️ 평가 스위트 중단됨 (Status: ${evalResult.status})`
                : `⏳ 평가 스위트 실행 중 (Status: ${evalResult.status})`}
            </span>
            <span
              data-testid="eval-gate-badge"
              style={{
                padding: '2px 8px',
                borderRadius: '4px',
                fontSize: '11px',
                fontWeight: 700,
                backgroundColor: evalResult.passedGate ? 'var(--color-status-online)' : 'var(--color-status-offline)',
                color: 'var(--color-brand-primary-fg)',
              }}
            >
              {evalResult.passedGate ? 'GATE PASS' : 'GATE FAIL'}
            </span>
          </div>
          <div style={{ marginTop: '6px', fontSize: '12px', color: 'var(--color-text-secondary)' }}>
            <div>통과: {evalResult.passedCases} / {evalResult.totalCases} 케이스 (위반 {evalResult.violations}건)</div>
            <div style={{ marginTop: '4px', display: 'grid', gridTemplateColumns: 'repeat(auto-fit, minmax(200px, 1fr))', gap: '8px' }}>
              <div>Run ID: <code>{evalResult.evalRunId}</code></div>
              <div>Suite ID: <code>{evalResult.suiteId}</code></div>
              <div>Started: {evalResult.startedAt}</div>
              <div>Ended: <span data-testid="eval-ended-at">{evalResult.endedAt ? evalResult.endedAt : 'NOT_OBSERVED'}</span></div>
            </div>
            {evalResult.componentVersions && Object.keys(evalResult.componentVersions).length > 0 && (
              <div style={{ marginTop: '6px', fontSize: '11px', color: 'var(--color-text-muted)' }}>
                <span style={{ fontWeight: 600 }}>구성요소 버전 (componentVersions): </span>
                <span data-testid="eval-component-versions">
                  {Object.entries(evalResult.componentVersions)
                    .map(([k, v]) => `${k}=${v}`)
                    .join(', ')}
                </span>
              </div>
            )}
          </div>
        </div>
      )}
      {regResult && (
        <div
          role="status"
          data-testid="registry-register-success"
          style={{
            padding: '14px 18px',
            borderRadius: '8px',
            backgroundColor: 'var(--color-bg-subtle)',
            border: '1px solid var(--color-status-online)',
            color: 'var(--color-status-online)',
            fontSize: '13px',
          }}
        >
          <div style={{ fontWeight: 600 }}>✔ 모델 버전 등록 완료 (201 Created)</div>
          <div style={{ marginTop: '6px', fontSize: '12px', color: 'var(--color-text-secondary)', display: 'grid', gridTemplateColumns: 'repeat(auto-fit, minmax(200px, 1fr))', gap: '8px' }}>
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
            backgroundColor: 'var(--color-bg-subtle)',
            border: '1px solid var(--color-status-online)',
            color: 'var(--color-status-online)',
            fontSize: '13px',
          }}
        >
          <div style={{ fontWeight: 600 }}>
            ✔ 보존 고정 판정 완료 (200 OK) — {pinResult.extended ? '고정 연장됨 (Extended)' : '기존 고정 유지 (연장 없음)'}
          </div>
          <div style={{ marginTop: '6px', fontSize: '12px', color: 'var(--color-text-secondary)', display: 'grid', gridTemplateColumns: 'repeat(auto-fit, minmax(200px, 1fr))', gap: '8px' }}>
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
            backgroundColor: relIsReplay ? 'var(--color-brand-subtle)' : 'var(--color-bg-subtle)',
            border: `1px solid ${relIsReplay ? 'var(--color-brand-primary)' : 'var(--color-status-online)'}`,
            color: relIsReplay ? 'var(--color-brand-primary)' : 'var(--color-status-online)',
            fontSize: '13px',
          }}
        >
          <div style={{ fontWeight: 600 }}>
            {relIsReplay
              ? 'ℹ️ 모델 릴리스 확인 완료 (재시도 응답 — 서버 원장 결과, 200 OK)'
              : '✔ 모델 릴리스 완료 (200 OK)'}
          </div>
          <div style={{ marginTop: '4px', fontSize: '11px', color: 'var(--color-text-muted)' }}>
            <span data-testid="release-replay-indicator">
              {relIsReplay
                ? '재시도 응답 — 서버 원장 결과 (저장된 응답일 수 있음)'
                : '신규 릴리스 완료 (Fresh)'}
            </span>
          </div>
          <div style={{ marginTop: '6px', fontSize: '12px', color: 'var(--color-text-secondary)', display: 'grid', gridTemplateColumns: 'repeat(auto-fit, minmax(200px, 1fr))', gap: '8px' }}>
            <div>Version ID: <code>{relResult.modelVersionId}</code></div>
            <div>Version: <strong>{relResult.version}</strong></div>
            <div>Stage: <strong style={{ color: 'var(--color-brand-primary)' }}>{relResult.stage}</strong></div>
            <div>Content Digest: <code>{relResult.contentSha256.slice(0, 16)}...</code></div>
          </div>
        </div>
      )}
      {/* --- REAL LINEAGE TRACE RENDERING SECTION --- */}
      {realTrace ? (
        <div
          data-testid="real-lineage-container"
          style={{
            backgroundColor: 'var(--color-bg-surface)',
            border: '1px solid var(--color-border-subtle)',
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
              <h3 style={{ margin: 0, fontSize: '16px', color: 'var(--color-text-primary)' }}>
                [{realTrace.version}] 실서버 계보 추적 결과 (ModelLineageTraceResponse)
              </h3>
              <span style={{ fontSize: '12px', color: 'var(--color-text-muted)' }}>
                Model Version ID: <code>{realTrace.modelVersionId}</code> • Stage: <strong style={{ color: 'var(--color-brand-primary)' }}>{realTrace.stage.toUpperCase()}</strong>
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
                  backgroundColor: realTrace.fullyTraceable ? 'var(--color-bg-subtle)' : 'var(--color-bg-subtle)',
                  color: realTrace.fullyTraceable ? 'var(--color-status-online)' : 'var(--color-status-degraded)',
                  border: `1px solid ${realTrace.fullyTraceable ? 'var(--color-status-online)' : 'var(--color-status-degraded)'}`,
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
                    backgroundColor: 'var(--color-brand-subtle)',
                    color: 'var(--color-brand-primary)',
                    border: '1px solid var(--color-brand-primary)',
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
            {(realTrace.countOnlyKinds || []).map((kind) => {
              const unresolvedItem = realTrace.unresolved.find((u) => u.kind === kind);
              const label = SERVER_KIND_LABELS[kind] || `${kind} 항목`;
              const isEval = kind === 'eval_run';
              return (
                <div
                  key={kind}
                  data-testid={`trace-${kind}-unobserved`}
                  style={{
                    backgroundColor: 'var(--color-bg-subtle)',
                    border: '1px solid var(--color-border-subtle)',
                    borderRadius: '6px',
                    padding: '12px',
                  }}
                >
                  <div style={{ fontSize: '11px', color: 'var(--color-text-muted)', fontWeight: 600 }}>{label}</div>
                  <div style={{ fontSize: '14px', fontWeight: 700, color: unresolvedItem ? 'var(--color-brand-primary)' : 'var(--color-text-muted)', marginTop: '4px' }}>
                    {unresolvedItem ? `상세 범위 외 (${unresolvedItem.count}건 관측)` : '관측된 항목 없음 (0건)'}
                  </div>
                  {isEval && (
                    <div style={{ fontSize: '12px', fontWeight: 600, color: 'var(--color-status-degraded)', marginTop: '4px' }}>
                      정량 평가 점수: NOT_OBSERVED (미관측)
                    </div>
                  )}
                  <div style={{ fontSize: '11px', color: 'var(--color-text-muted)', marginTop: '2px' }}>
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
            <h4 style={{ margin: '0 0 8px 0', fontSize: '14px', color: 'var(--color-text-primary)' }}>
              연결된 데이터셋 버전 ({realTrace.datasets.length}건)
            </h4>
            {realTrace.datasets.length === 0 ? (
              <div style={{ fontSize: '12px', color: 'var(--color-text-muted)', padding: '12px', backgroundColor: 'var(--color-bg-subtle)', borderRadius: '6px' }}>
                연결된 데이터셋이 없습니다.
              </div>
            ) : (
              <table style={{ width: '100%', borderCollapse: 'collapse', fontSize: '12px', color: 'var(--color-text-secondary)' }}>
                <thead>
                  <tr style={{ borderBottom: '1px solid var(--color-border-subtle)', textAlign: 'left', color: 'var(--color-text-muted)' }}>
                    <th style={{ padding: '6px' }}>Dataset Version ID</th>
                    <th style={{ padding: '6px' }}>Version</th>
                    <th style={{ padding: '6px' }}>Content SHA-256</th>
                    <th style={{ padding: '6px' }}>URI</th>
                  </tr>
                </thead>
                <tbody>
                  {realTrace.datasets.map((d) => (
                    <tr key={d.datasetVersionId} style={{ borderBottom: '1px solid var(--color-border-subtle)' }}>
                      <td style={{ padding: '8px 6px', fontFamily: 'var(--font-mono, monospace)' }}>{d.datasetVersionId}</td>
                      <td style={{ padding: '8px 6px', fontWeight: 600 }}>{d.version}</td>
                      <td style={{ padding: '8px 6px', fontFamily: 'var(--font-mono, monospace)' }}>{d.contentSha256.slice(0, 16)}...</td>
                      <td style={{ padding: '8px 6px', color: 'var(--color-brand-primary)' }}>{d.uri}</td>
                    </tr>
                  ))}
                </tbody>
              </table>
            )}
          </div>
          {/* Deployments Table */}
          <div data-testid="real-lineage-deployments">
            <h4 style={{ margin: '0 0 8px 0', fontSize: '14px', color: 'var(--color-text-primary)' }}>
              배포 기록 ({realTrace.deployments.length}건)
            </h4>
            {realTrace.deployments.length === 0 ? (
              <div style={{ fontSize: '12px', color: 'var(--color-text-muted)', padding: '12px', backgroundColor: 'var(--color-bg-subtle)', borderRadius: '6px' }}>
                배포 내역이 없습니다 (deployments: []).
              </div>
            ) : (
              <table style={{ width: '100%', borderCollapse: 'collapse', fontSize: '12px', color: 'var(--color-text-secondary)' }}>
                <thead>
                  <tr style={{ borderBottom: '1px solid var(--color-border-subtle)', textAlign: 'left', color: 'var(--color-text-muted)' }}>
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
                    <tr key={dep.deploymentId} style={{ borderBottom: '1px solid var(--color-border-subtle)' }}>
                      <td style={{ padding: '8px 6px', fontFamily: 'var(--font-mono, monospace)' }}>{dep.deploymentId}</td>
                      <td style={{ padding: '8px 6px' }}>
                        <span style={{ textTransform: 'uppercase', fontWeight: 600, color: dep.environment === 'pilot' ? 'var(--color-status-online)' : 'var(--color-brand-primary)' }}>
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
              <h4 style={{ margin: '0 0 6px 0', fontSize: '13px', color: 'var(--color-text-primary)' }}>
                누락된 주체 (Missing: {realTrace.missing.length}건)
              </h4>
              {realTrace.missing.length === 0 ? (
                <div style={{ fontSize: '12px', color: 'var(--color-status-online)' }}>누락된 항목이 없습니다.</div>
              ) : (
                <ul style={{ margin: 0, paddingLeft: '18px', fontSize: '12px', color: 'var(--color-status-offline)' }}>
                  {realTrace.missing.map((m, idx) => (
                    <li key={idx} data-testid="missing-item">{m}</li>
                  ))}
                </ul>
              )}
            </div>
            <div data-testid="real-lineage-unresolved">
              <h4 style={{ margin: '0 0 6px 0', fontSize: '13px', color: 'var(--color-text-primary)' }}>
                범위 외 미해결 주체 (Unresolved: {realTrace.unresolved.length}건)
              </h4>
              {realTrace.unresolved.length === 0 ? (
                <div style={{ fontSize: '12px', color: 'var(--color-text-muted)' }}>미해결 항목이 없습니다.</div>
              ) : (
                <ul style={{ margin: 0, paddingLeft: '18px', fontSize: '12px', color: 'var(--color-status-degraded)' }}>
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
          backgroundColor: 'var(--color-bg-subtle)',
          border: '1px solid var(--color-status-degraded)',
          color: 'var(--color-status-degraded)',
          fontSize: '0.8125rem',
          lineHeight: 1.5,
        }}
      >
        <div>
          <strong>⚠️ 모델 계보 및 평가 점수 미노출 (백엔드 HTTP API 부재) ℹ️ [제품 기능 미제공]:</strong> 실제 계보 데이터는 saintvision 내부 서비스(services/lineage.py)에만 존재하며 외부 HTTP 서빙 엔드포인트가 제공되지 않습니다.
        </div>
        <div style={{ marginTop: '4px', fontSize: '0.75rem', color: 'var(--color-status-degraded)' }}>
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
        <div style={{ backgroundColor: 'var(--color-bg-surface)', border: '1px solid var(--color-border-subtle)', borderRadius: '8px', padding: '16px 20px' }}>
          <div style={{ fontSize: '12px', color: 'var(--color-text-muted)', fontWeight: 600 }}>Provider 계약 동일성 (AC-10 / G-03)</div>
          <div
            data-testid="conformance-top-status"
            style={{
              fontSize: '18px',
              fontWeight: 700,
              color: conformanceError
                ? 'var(--color-status-offline)'
                : conformanceData
                ? conformanceData.status === 'RECORDED'
                  ? 'var(--color-brand-primary)'
                  : 'var(--color-status-degraded)'
                : 'var(--color-text-muted)',
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
          <div data-testid="conformance-top-subtext" style={{ fontSize: '12px', color: 'var(--color-text-muted)', marginTop: '4px' }}>
            {conformanceError
              ? '어댑터 conformance 조회 실패'
              : conformanceData
              ? conformanceData.status === 'RECORDED'
                ? `${conformanceData.records.length}/${conformanceData.adapters.length} 어댑터 기록 · fixture-adapter 측정 (${conformanceData.scope})`
                : `${conformanceData.checks.length}개 정본 체크 항목 미측정 (${conformanceData.scope})`
              : '실제 conformance API (G-03 1단계) 연동 대기'}
          </div>
        </div>
        <div style={{ backgroundColor: 'var(--color-bg-surface)', border: '1px solid var(--color-border-subtle)', borderRadius: '8px', padding: '16px 20px' }}>
          <div style={{ fontSize: '12px', color: 'var(--color-text-muted)', fontWeight: 600 }}>End-to-End 모델 계보 역추적</div>
          <div style={{ fontSize: '20px', fontWeight: 700, color: lineages.length > 0 ? 'var(--color-status-online)' : 'var(--color-status-degraded)', marginTop: '4px' }}>
            {lineages.length > 0 ? '추적 가능' : '미노출 (API 부재)'}
          </div>
          <div style={{ fontSize: '12px', color: 'var(--color-text-muted)', marginTop: '4px' }}>
            {lineages.length > 0 ? 'Dataset → Commit → Run → Eval → Approval' : '서버 계보 앵커 부재 · 신설 대기'}
          </div>
        </div>
        <div style={{ backgroundColor: 'var(--color-bg-surface)', border: '1px solid var(--color-border-subtle)', borderRadius: '8px', padding: '16px 20px' }}>
          <div style={{ fontSize: '12px', color: 'var(--color-text-muted)', fontWeight: 600 }}>프로덕션 배포 게이트 기준</div>
          <div style={{ fontSize: '20px', fontWeight: 700, color: 'var(--color-brand-primary)', marginTop: '4px' }}>
            Accuracy ≥ 85.0%
          </div>
          <div style={{ fontSize: '12px', color: 'var(--color-text-muted)', marginTop: '4px' }}>
            {lineages.length > 0 ? '2인 승인 ID 필수 충족 (모의 게이트)' : '평가 점수 부재로 게이트 대기'}
          </div>
        </div>
        <div style={{ backgroundColor: 'var(--color-bg-surface)', border: '1px solid var(--color-border-subtle)', borderRadius: '8px', padding: '16px 20px' }}>
          <div style={{ fontSize: '12px', color: 'var(--color-text-muted)', fontWeight: 600 }}>등록 모델 수</div>
          <div style={{ fontSize: '24px', fontWeight: 700, color: 'var(--color-text-primary)', marginTop: '4px' }}>
            {lineages.length} 개 모델 {lineages.length === 0 && <span style={{ fontSize: '14px', color: 'var(--color-status-degraded)' }}>(미노출)</span>}
          </div>
          <div style={{ fontSize: '12px', color: 'var(--color-text-muted)', marginTop: '4px' }}>
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
            backgroundColor: actionNotice.type === 'error' ? 'var(--color-bg-subtle)' : 'var(--color-bg-subtle)',
            border: `1px solid ${actionNotice.type === 'error' ? 'var(--color-status-offline)' : 'var(--color-status-online)'}`,
            color: actionNotice.type === 'error' ? 'var(--color-status-offline)' : 'var(--color-status-online)',
          }}
        >
          {actionNotice.text}
        </div>
      )}
      {/* Reverse Lineage Query Search Bar */}
      <div
        style={{
          backgroundColor: 'var(--color-bg-surface)',
          border: '1px solid var(--color-border-subtle)',
          borderRadius: '8px',
          padding: '16px 20px',
          display: 'flex',
          flexDirection: 'column',
          gap: '12px',
        }}
      >
        <div>
          <h3 style={{ margin: 0, fontSize: '15px', color: 'var(--color-text-primary)' }}>
            계보 역추적 검색 (Reverse Lineage Query — AC-10)
          </h3>
          <p style={{ margin: '4px 0 0 0', fontSize: '12px', color: 'var(--color-text-muted)' }}>
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
              backgroundColor: 'var(--color-bg-subtle)',
              border: '1px solid var(--color-border-subtle)',
              borderRadius: '6px',
              color: 'var(--color-text-secondary)',
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
            backgroundColor: 'var(--color-bg-surface)',
            border: '1px solid var(--color-border-subtle)',
            borderRadius: '8px',
            padding: '48px 24px',
            textAlign: 'center',
            color: 'var(--color-text-muted)',
          }}
        >
          <div style={{ fontSize: '2rem', marginBottom: '12px' }}>📊</div>
          <h3 style={{ margin: '0 0 8px 0', fontSize: '1rem', color: 'var(--color-text-primary)' }}>
            등록된 모델 계보 및 평가 점수 데이터가 없습니다.
          </h3>
          <p style={{ margin: 0, fontSize: '0.8125rem', color: 'var(--color-text-muted)', maxWidth: '600px', display: 'inline-block' }}>
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
                    border: isSelected ? '1px solid var(--color-brand-primary)' : '1px solid var(--color-border-subtle)',
                    backgroundColor: isSelected ? 'var(--color-bg-subtle)' : 'var(--color-bg-surface)',
                    color: isSelected ? 'var(--color-brand-primary)' : 'var(--color-text-secondary)',
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
                backgroundColor: 'var(--color-bg-surface)',
                border: '1px solid var(--color-border-subtle)',
                borderRadius: '8px',
                padding: '24px',
                display: 'flex',
                flexDirection: 'column',
                gap: '20px',
              }}
            >
              <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
                <div>
                  <h3 style={{ margin: 0, fontSize: '16px', color: 'var(--color-text-primary)' }}>
                    [{selectedModel.modelName}] End-to-End 계보 추적 그래프
                  </h3>
                  <span style={{ fontSize: '12px', color: 'var(--color-text-muted)' }}>
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
                        backgroundColor: 'var(--color-bg-subtle)',
                        border: '1px solid var(--color-border-subtle)',
                        borderRadius: '4px',
                        color: 'var(--color-text-secondary)',
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
                        style={{ fontSize: '11px', color: 'var(--color-status-degraded)', marginLeft: '4px' }}
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
                <div style={{ backgroundColor: 'var(--color-bg-subtle)', border: '1px solid var(--color-border-subtle)', borderRadius: '6px', padding: '12px' }}>
                  <div style={{ fontSize: '11px', color: 'var(--color-text-muted)', fontWeight: 600 }}>1. DATASET DIGEST</div>
                  <div style={{ fontSize: '12px', color: 'var(--color-brand-primary)', fontFamily: 'var(--font-mono, monospace)', marginTop: '6px' }}>
                    {selectedModel.datasetDigest ? selectedModel.datasetDigest.slice(0, 16) + '...' : '미지정'}
                  </div>
                  <div style={{ fontSize: '11px', color: selectedModel.datasetDigest ? 'var(--color-status-online)' : 'var(--color-text-muted)', marginTop: '4px' }}>
                    {selectedModel.datasetDigest ? 'SHA-256 (모의 표기)' : '미검증'}
                  </div>
                </div>
                {/* Node 2: Source Git Commit */}
                <div style={{ backgroundColor: 'var(--color-bg-subtle)', border: '1px solid var(--color-border-subtle)', borderRadius: '6px', padding: '12px' }}>
                  <div style={{ fontSize: '11px', color: 'var(--color-text-muted)', fontWeight: 600 }}>2. SOURCE COMMIT</div>
                  <div style={{ fontSize: '12px', color: 'var(--color-brand-primary)', fontFamily: 'var(--font-mono, monospace)', marginTop: '6px' }}>
                    {selectedModel.sourceCommitSha ? selectedModel.sourceCommitSha.slice(0, 12) : '미지정'}
                  </div>
                  <div style={{ fontSize: '11px', color: 'var(--color-text-muted)', marginTop: '4px' }}>
                    {selectedModel.sourceCommitSha ? 'Git Signed SHA (모의 표기)' : '커밋 없음'}
                  </div>
                </div>
                {/* Node 3: Training Run ID */}
                <div style={{ backgroundColor: 'var(--color-bg-subtle)', border: '1px solid var(--color-border-subtle)', borderRadius: '6px', padding: '12px' }}>
                  <div style={{ fontSize: '11px', color: 'var(--color-text-muted)', fontWeight: 600 }}>3. TRAINING RUN</div>
                  <div style={{ fontSize: '12px', color: 'var(--color-text-primary)', fontFamily: 'var(--font-mono, monospace)', marginTop: '6px' }}>
                    {selectedModel.trainingRunId || '미실행'}
                  </div>
                  <div style={{ fontSize: '11px', color: 'var(--color-text-muted)', marginTop: '4px' }}>Isolated Runtime (모의)</div>
                </div>
                {/* Node 4: Evaluation Score */}
                <div style={{ backgroundColor: 'var(--color-bg-subtle)', border: '1px solid var(--color-border-subtle)', borderRadius: '6px', padding: '12px' }}>
                  <div style={{ fontSize: '11px', color: 'var(--color-text-muted)', fontWeight: 600 }}>4. EVALUATION (모의 점수)</div>
                  <div style={{ fontSize: '14px', color: selectedModel.evalAccuracy !== undefined && selectedModel.evalAccuracy >= 0.85 ? 'var(--color-status-online)' : 'var(--color-status-offline)', fontWeight: 700, marginTop: '4px' }}>
                    Acc: {selectedModel.evalAccuracy !== undefined ? (selectedModel.evalAccuracy * 100).toFixed(1) + '%' : '미평가'}
                  </div>
                  <div style={{ fontSize: '11px', color: 'var(--color-text-muted)', marginTop: '2px' }}>
                    F1 Score: {selectedModel.evalF1Score !== undefined ? selectedModel.evalF1Score.toFixed(3) : 'N/A'}
                  </div>
                </div>
                {/* Node 5: Governance Approval */}
                <div style={{ backgroundColor: 'var(--color-bg-subtle)', border: '1px solid var(--color-border-subtle)', borderRadius: '6px', padding: '12px' }}>
                  <div style={{ fontSize: '11px', color: 'var(--color-text-muted)', fontWeight: 600 }}>5. APPROVAL</div>
                  <div style={{ fontSize: '12px', color: selectedModel.approvalId ? 'var(--color-status-online)' : 'var(--color-text-muted)', fontFamily: 'var(--font-mono, monospace)', marginTop: '6px' }}>
                    {selectedModel.approvalId ? selectedModel.approvalId : 'None (Pending)'}
                  </div>
                  <div style={{ fontSize: '11px', color: 'var(--color-text-muted)', marginTop: '4px' }}>Two-Person Rule (모의)</div>
                </div>
                {/* Node 6: Deployment Digest (Simulated) */}
                <div style={{ backgroundColor: 'var(--color-bg-subtle)', border: '1px solid var(--color-border-subtle)', borderRadius: '6px', padding: '12px' }}>
                  <div style={{ fontSize: '11px', color: 'var(--color-text-muted)', fontWeight: 600 }}>6. DEPLOYMENT DIGEST (모의 시뮬레이션)</div>
                  <div style={{ fontSize: '12px', color: selectedModel.deploymentDigest ? 'var(--color-brand-primary)' : 'var(--color-text-muted)', fontFamily: 'var(--font-mono, monospace)', marginTop: '6px' }}>
                    {selectedModel.deploymentDigest ? selectedModel.deploymentDigest.slice(0, 16) + '...' : 'Not deployed'}
                  </div>
                  <div style={{ fontSize: '11px', color: selectedModel.deploymentDigest ? 'var(--color-status-degraded)' : 'var(--color-text-muted)', marginTop: '4px' }}>
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
          backgroundColor: 'var(--color-bg-surface)',
          border: '1px solid var(--color-border-subtle)',
          borderRadius: '8px',
          padding: '20px',
        }}
      >
        <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: '14px' }}>
          <div>
            <h4 style={{ margin: 0, fontSize: '15px', color: 'var(--color-text-primary)' }}>
              Multi-LLM Provider Adapter Conformance (G-03 2단계 API 연동)
            </h4>
            <p style={{ margin: '4px 0 0 0', fontSize: '12px', color: 'var(--color-text-muted)' }}>
              컨트롤 플레인 호스트의 실제 어댑터 적합성 상태를 조회합니다. 저장된 기록이 없으면 정직하게 <code style={{ color: 'var(--color-status-degraded)' }}>NOT_OBSERVED</code>(미측정)와 정본 체크리스트 규격을, 기록이 있으면 <code style={{ color: 'var(--color-status-degraded)' }}>RECORDED</code>와 어댑터별 기록을 반환합니다. 기록의 측정 대상은 설치된 CLI가 아니라 제품 fixture adapter입니다(<code>subject: fixture-adapter</code>).
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
              backgroundColor: 'var(--color-bg-subtle)',
              border: '1px solid var(--color-border-subtle)',
              borderRadius: '6px',
              color: 'var(--color-text-secondary)',
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
                    ? 'var(--color-brand-subtle)'
                    : conformanceError
                    ? 'var(--color-bg-subtle)'
                    : 'var(--color-bg-subtle)',
                  border: `1px solid ${
                    conformanceLoading
                      ? 'var(--color-brand-primary)'
                      : conformanceError
                      ? 'var(--color-status-offline)'
                      : 'var(--color-status-degraded)'
                  }`,
                  color: conformanceLoading
                    ? 'var(--color-brand-primary)'
                    : conformanceError
                    ? 'var(--color-status-offline)'
                    : 'var(--color-status-degraded)',
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
              backgroundColor: 'var(--color-bg-subtle)',
              border: '1px solid var(--color-status-offline)',
              color: 'var(--color-status-offline)',
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
              backgroundColor: 'var(--color-bg-subtle)',
              border: '1px solid var(--color-border-subtle)',
              color: 'var(--color-text-muted)',
              fontSize: '13px',
              lineHeight: '1.5',
            }}
          >
            ℹ️ <strong style={{ color: 'var(--color-status-degraded)' }}>미측정 (미조회)</strong>: 실제 컨트롤 플레인 HTTP 엔드포인트(<code>GET /v1/projects/:projectId/adapters/conformance</code>)를 호출하여 정본 체크리스트 규격 상태를 조회합니다. 프로젝트 ID를 입력하고 조회 버튼을 누르십시오.
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
                backgroundColor: 'var(--color-bg-subtle)',
                border: '1px solid var(--color-border-subtle)',
                borderRadius: '6px',
                padding: '16px',
                display: 'grid',
                gridTemplateColumns: 'repeat(auto-fit, minmax(220px, 1fr))',
                gap: '12px',
                fontSize: '13px',
              }}
            >
              <div>
                <span style={{ color: 'var(--color-text-muted)', fontSize: '11px', display: 'block' }}>CONFORMANCE STATUS</span>
                <span
                  data-testid="conformance-status-badge"
                  style={{
                    display: 'inline-block',
                    marginTop: '4px',
                    padding: '2px 8px',
                    borderRadius: '4px',
                    fontSize: '11px',
                    fontWeight: 700,
                    backgroundColor: conformanceData.status === 'RECORDED' ? 'var(--color-brand-subtle)' : 'var(--color-bg-subtle)',
                    color: conformanceData.status === 'RECORDED' ? 'var(--color-brand-primary)' : 'var(--color-status-degraded)',
                  }}
                >
                  {conformanceData.status === 'RECORDED' ? '기록됨 (RECORDED)' : `미측정 (${conformanceData.status})`}
                </span>
              </div>
              <div>
                <span style={{ color: 'var(--color-text-muted)', fontSize: '11px', display: 'block' }}>SCOPE</span>
                <code data-testid="conformance-scope" style={{ color: 'var(--color-brand-primary)' }}>
                  {conformanceData.scope}
                </code>
              </div>
              <div>
                <span style={{ color: 'var(--color-text-muted)', fontSize: '11px', display: 'block' }}>CONTRACT VERSION</span>
                <span data-testid="conformance-contract-version" style={{ color: 'var(--color-text-secondary)', fontFamily: 'var(--font-mono, monospace)' }}>
                  {conformanceData.contractVersion}
                </span>
              </div>
              <div>
                <span style={{ color: 'var(--color-text-muted)', fontSize: '11px', display: 'block' }}>TARGET ADAPTERS</span>
                <span data-testid="conformance-adapters" style={{ color: 'var(--color-text-primary)' }}>
                  {conformanceData.adapters.join(', ')}
                </span>
              </div>
              <div>
                <span style={{ color: 'var(--color-text-muted)', fontSize: '11px', display: 'block' }}>
                  {conformanceData.status === 'RECORDED' ? 'LATEST RECORDED AT' : 'RECORDED AT'}
                </span>
                <span data-testid="conformance-recorded-at" style={{ color: 'var(--color-text-muted)' }}>
                  {conformanceData.status === 'RECORDED' ? conformanceData.latestRecordedAt : 'null (미측정)'}
                </span>
              </div>
              {conformanceData.status === 'NOT_OBSERVED' ? (
                <div style={{ gridColumn: '1 / -1' }}>
                  <span style={{ color: 'var(--color-text-muted)', fontSize: '11px', display: 'block' }}>REASON</span>
                  <span data-testid="conformance-reason" style={{ color: 'var(--color-text-secondary)' }}>
                    {conformanceData.reason}
                  </span>
                </div>
              ) : (
                <div style={{ gridColumn: '1 / -1' }}>
                  <span style={{ color: 'var(--color-text-muted)', fontSize: '11px', display: 'block' }}>SUBJECT</span>
                  <span data-testid="conformance-subject-note" style={{ color: 'var(--color-text-secondary)' }}>
                    fixture-adapter · in-server — 제품 fixture adapter에 대한 suite 실행 기록이며 설치된 CLI의 적합성이 아닙니다. 기록이 없는 어댑터는 목록에 없습니다(미측정).
                  </span>
                </div>
              )}
            </div>

            {/* Records per adapter (RECORDED branch, design #218 v1.2 §4-1) */}
            {conformanceData.status === 'RECORDED' && (
              <div style={{ overflowX: 'auto' }}>
                <div style={{ fontSize: '13px', fontWeight: 600, color: 'var(--color-text-primary)', marginBottom: '8px' }}>
                  어댑터별 기록 ({conformanceData.records.length}개 · 서버 응답 동적 렌더링)
                </div>
                <table
                  data-testid="conformance-records-table"
                  style={{ width: '100%', borderCollapse: 'collapse', fontSize: '13px', color: 'var(--color-text-secondary)' }}
                >
                  <caption style={{ textAlign: 'left', fontSize: '12px', color: 'var(--color-text-muted)', marginBottom: '8px' }}>
                    컨트롤 플레인 호스트의 어댑터별 최신 conformance 기록
                  </caption>
                  <thead>
                    <tr style={{ borderBottom: '1px solid var(--color-border-subtle)', textAlign: 'left', color: 'var(--color-text-muted)' }}>
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
                        style={{ borderBottom: '1px solid var(--color-border-subtle)' }}
                      >
                        <td style={{ padding: '8px', fontWeight: 600, color: 'var(--color-text-primary)', fontFamily: 'var(--font-mono, monospace)' }}>
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
                        <td style={{ padding: '8px', color: 'var(--color-text-muted)' }}>
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
              <div style={{ fontSize: '13px', fontWeight: 600, color: 'var(--color-text-primary)', marginBottom: '8px' }}>
                정본 Conformance Checklist ({conformanceData.checks.length}개 항목 · 서버 응답 동적 렌더링)
              </div>
              <table
                data-testid="conformance-checks-table"
                style={{ width: '100%', borderCollapse: 'collapse', fontSize: '13px', color: 'var(--color-text-secondary)' }}
              >
                <caption style={{ textAlign: 'left', fontSize: '12px', color: 'var(--color-text-muted)', marginBottom: '8px' }}>
                  컨트롤 플레인 호스트 어댑터 Conformance 체크리스트
                </caption>
                <thead>
                  <tr style={{ borderBottom: '1px solid var(--color-border-subtle)', textAlign: 'left', color: 'var(--color-text-muted)' }}>
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
                      style={{ borderBottom: '1px solid var(--color-border-subtle)' }}
                    >
                      <td style={{ padding: '8px', color: 'var(--color-text-muted)' }}>{idx + 1}</td>
                      <td style={{ padding: '8px', fontWeight: 600, color: 'var(--color-text-primary)', fontFamily: 'var(--font-mono, monospace)' }}>
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
                            backgroundColor: check.capabilityGated ? 'var(--color-brand-subtle)' : 'var(--color-bg-subtle)',
                            color: check.capabilityGated ? 'var(--color-brand-primary)' : 'var(--color-text-muted)',
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
                            backgroundColor: conformanceData.status === 'RECORDED' ? 'var(--color-brand-subtle)' : 'var(--color-bg-subtle)',
                            color: conformanceData.status === 'RECORDED' ? 'var(--color-brand-primary)' : 'var(--color-status-degraded)',
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
            borderTop: '1px solid var(--color-border-subtle)',
            display: 'flex',
            flexDirection: 'column',
            gap: '14px',
          }}
        >
          <div>
            <h5 style={{ margin: 0, fontSize: '14px', color: 'var(--color-text-primary)' }}>
              단건 어댑터 Conformance 조회 (Single Route)
            </h5>
            <p style={{ margin: '4px 0 0 0', fontSize: '12px', color: 'var(--color-text-muted)' }}>
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
                backgroundColor: 'var(--color-bg-subtle)',
                border: '1px solid var(--color-border-subtle)',
                borderRadius: '6px',
                color: 'var(--color-text-secondary)',
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
                      ? 'var(--color-brand-subtle)'
                      : singleConformanceError
                      ? 'var(--color-bg-subtle)'
                      : 'var(--color-bg-subtle)',
                    border: `1px solid ${
                      singleConformanceLoading
                        ? 'var(--color-brand-primary)'
                        : singleConformanceError
                        ? 'var(--color-status-offline)'
                        : 'var(--color-status-degraded)'
                    }`,
                    color: singleConformanceLoading
                      ? 'var(--color-brand-primary)'
                      : singleConformanceError
                      ? 'var(--color-status-offline)'
                      : 'var(--color-status-degraded)',
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
                backgroundColor: 'var(--color-bg-subtle)',
                border: '1px solid var(--color-status-offline)',
                color: 'var(--color-status-offline)',
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
                  <span style={{ marginLeft: '8px', fontSize: '11px', color: 'var(--color-text-muted)' }}>
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
                  backgroundColor: 'var(--color-bg-subtle)',
                  border: '1px solid var(--color-border-subtle)',
                  borderRadius: '6px',
                  padding: '14px',
                  display: 'grid',
                  gridTemplateColumns: 'repeat(auto-fit, minmax(200px, 1fr))',
                  gap: '10px',
                  fontSize: '13px',
                }}
              >
                <div>
                  <span style={{ color: 'var(--color-text-muted)', fontSize: '11px', display: 'block' }}>CONFORMANCE STATUS</span>
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
                          ? 'var(--color-brand-subtle)'
                          : 'var(--color-bg-subtle)',
                      color: singleConformanceData.status === 'RECORDED' ? 'var(--color-brand-primary)' : 'var(--color-status-degraded)',
                    }}
                  >
                    {singleConformanceData.status === 'RECORDED' ? '기록됨 (RECORDED)' : `미측정 (${singleConformanceData.status})`}
                  </span>
                </div>
                <div>
                  <span style={{ color: 'var(--color-text-muted)', fontSize: '11px', display: 'block' }}>ADAPTER</span>
                  <code data-testid="single-conformance-adapter" style={{ color: 'var(--color-text-primary)', fontWeight: 600 }}>
                    {singleConformanceData.adapter}
                  </code>
                </div>
                <div>
                  <span style={{ color: 'var(--color-text-muted)', fontSize: '11px', display: 'block' }}>SCOPE</span>
                  <code data-testid="single-conformance-scope" style={{ color: 'var(--color-brand-primary)' }}>
                    {singleConformanceData.scope}
                  </code>
                </div>
                <div>
                  <span style={{ color: 'var(--color-text-muted)', fontSize: '11px', display: 'block' }}>CONTRACT VERSION</span>
                  <span data-testid="single-conformance-contract-version" style={{ color: 'var(--color-text-secondary)', fontFamily: 'var(--font-mono, monospace)' }}>
                    {singleConformanceData.contractVersion}
                  </span>
                </div>

                {singleConformanceData.status === 'NOT_OBSERVED' ? (
                  <>
                    <div>
                      <span style={{ color: 'var(--color-text-muted)', fontSize: '11px', display: 'block' }}>RECORDED AT</span>
                      <span data-testid="single-conformance-recorded-at" style={{ color: 'var(--color-text-muted)' }}>
                        null (미측정)
                      </span>
                    </div>
                    <div style={{ gridColumn: '1 / -1' }}>
                      <span style={{ color: 'var(--color-text-muted)', fontSize: '11px', display: 'block' }}>REASON</span>
                      <span data-testid="single-conformance-reason" style={{ color: 'var(--color-text-secondary)' }}>
                        {singleConformanceData.reason}
                      </span>
                    </div>
                  </>
                ) : (
                  <>
                    <div>
                      <span style={{ color: 'var(--color-text-muted)', fontSize: '11px', display: 'block' }}>SUBJECT / PROVENANCE</span>
                      <span data-testid="single-conformance-subject" style={{ color: 'var(--color-text-secondary)' }}>
                        {singleConformanceData.subject} / {singleConformanceData.provenance}
                      </span>
                    </div>
                    <div>
                      <span style={{ color: 'var(--color-text-muted)', fontSize: '11px', display: 'block' }}>SUITE CONTRACT VERSION</span>
                      <span data-testid="single-conformance-suite-contract-version" style={{ color: 'var(--color-text-secondary)', fontFamily: 'var(--font-mono, monospace)' }}>
                        {singleConformanceData.suiteContractVersion}
                      </span>
                    </div>
                    <div>
                      <span style={{ color: 'var(--color-text-muted)', fontSize: '11px', display: 'block' }}>RESULTS</span>
                      <span data-testid="single-conformance-counts" style={{ color: 'var(--color-text-primary)', fontWeight: 600 }}>
                        {`전체 ${singleConformanceData.total} · 통과 ${singleConformanceData.passed} · 실패 ${singleConformanceData.failed} · 건너뜀 ${singleConformanceData.skipped}`}
                      </span>
                    </div>
                    <div>
                      <span style={{ color: 'var(--color-text-muted)', fontSize: '11px', display: 'block' }}>RECORDED AT</span>
                      <span data-testid="single-conformance-recorded-at" style={{ color: 'var(--color-text-muted)' }}>
                        {singleConformanceData.recordedAt}
                      </span>
                    </div>
                    <div style={{ gridColumn: '1 / -1' }}>
                      <span style={{ color: 'var(--color-text-muted)', fontSize: '11px', display: 'block' }}>SUBJECT NOTE</span>
                      <span data-testid="single-conformance-subject-note" style={{ color: 'var(--color-text-secondary)' }}>
                        fixture-adapter · in-server — 제품 fixture adapter에 대한 suite 실행 기록이며 설치된 CLI의 적합성이 아닙니다.
                      </span>
                    </div>
                  </>
                )}
              </div>

              {/* When NOT_OBSERVED: Render Checks Descriptors */}
              {singleConformanceData.status === 'NOT_OBSERVED' && (
                <div style={{ overflowX: 'auto' }}>
                  <div style={{ fontSize: '13px', fontWeight: 600, color: 'var(--color-text-primary)', marginBottom: '8px' }}>
                    정본 Conformance Checklist ({singleConformanceData.checks.length}개 항목)
                  </div>
                  <table
                    data-testid="single-conformance-checks-table"
                    style={{ width: '100%', borderCollapse: 'collapse', fontSize: '13px', color: 'var(--color-text-secondary)' }}
                  >
                    <thead>
                      <tr style={{ borderBottom: '1px solid var(--color-border-subtle)', textAlign: 'left', color: 'var(--color-text-muted)' }}>
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
                          style={{ borderBottom: '1px solid var(--color-border-subtle)' }}
                        >
                          <td style={{ padding: '8px', color: 'var(--color-text-muted)' }}>{idx + 1}</td>
                          <td style={{ padding: '8px', fontWeight: 600, color: 'var(--color-text-primary)', fontFamily: 'var(--font-mono, monospace)' }}>
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
                                backgroundColor: check.capabilityGated ? 'var(--color-brand-subtle)' : 'var(--color-bg-subtle)',
                                color: check.capabilityGated ? 'var(--color-brand-primary)' : 'var(--color-text-muted)',
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
                  <div style={{ fontSize: '13px', fontWeight: 600, color: 'var(--color-text-primary)', marginBottom: '8px' }}>
                    상세 체크 결과 ({singleConformanceData.outcomes.length}개 항목)
                  </div>
                  <table
                    data-testid="single-conformance-outcomes-table"
                    style={{ width: '100%', borderCollapse: 'collapse', fontSize: '13px', color: 'var(--color-text-secondary)' }}
                  >
                    <thead>
                      <tr style={{ borderBottom: '1px solid var(--color-border-subtle)', textAlign: 'left', color: 'var(--color-text-muted)' }}>
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
                          style={{ borderBottom: '1px solid var(--color-border-subtle)' }}
                        >
                          <td style={{ padding: '8px', color: 'var(--color-text-muted)' }}>{idx + 1}</td>
                          <td style={{ padding: '8px', fontWeight: 600, color: 'var(--color-text-primary)', fontFamily: 'var(--font-mono, monospace)' }}>
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
                                  ? 'var(--color-bg-subtle)'
                                  : outcome.passed
                                  ? 'var(--color-brand-subtle)'
                                  : 'var(--color-bg-subtle)',
                                color: outcome.skipped ? 'var(--color-text-muted)' : outcome.passed ? 'var(--color-brand-primary)' : 'var(--color-status-offline)',
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
          backgroundColor: 'var(--color-bg-surface)',
          border: '1px solid var(--color-border-subtle)',
          borderRadius: '8px',
          padding: '20px',
          display: 'flex',
          flexDirection: 'column',
          gap: '14px',
        }}
      >
        <div>
          <h4 style={{ margin: 0, fontSize: '15px', color: 'var(--color-text-primary)' }}>
            실제 모델 Commitment 조회 (Control-Plane HTTP API)
          </h4>
          <p style={{ margin: '4px 0 0 0', fontSize: '12px', color: 'var(--color-text-muted)' }}>
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
              backgroundColor: 'var(--color-bg-subtle)',
              border: '1px solid var(--color-border-subtle)',
              borderRadius: '6px',
              color: 'var(--color-text-secondary)',
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
              backgroundColor: 'var(--color-bg-subtle)',
              border: '1px solid var(--color-border-subtle)',
              borderRadius: '6px',
              color: 'var(--color-text-secondary)',
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
              backgroundColor: 'var(--color-bg-subtle)',
              border: '1px solid var(--color-border-subtle)',
              borderRadius: '6px',
              color: 'var(--color-text-secondary)',
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
              backgroundColor: 'var(--color-bg-subtle)',
              border: '1px solid var(--color-status-offline)',
              color: 'var(--color-status-offline)',
            }}
          >
            ❌ {commitmentError.code && commitmentError.status ? `[${commitmentError.code}] (${commitmentError.status}) ${commitmentError.title ? `${commitmentError.title}: ` : ''}` : ''}{commitmentError.detail}
          </div>
        )}
        {commitmentData && (
          <div
            data-testid="commitment-result-container"
            style={{
              backgroundColor: 'var(--color-bg-subtle)',
              border: '1px solid var(--color-border-subtle)',
              borderRadius: '6px',
              padding: '16px',
              display: 'grid',
              gridTemplateColumns: 'repeat(auto-fit, minmax(220px, 1fr))',
              gap: '12px',
              fontSize: '13px',
            }}
          >
            <div>
              <span style={{ color: 'var(--color-text-muted)', fontSize: '11px', display: 'block' }}>MANIFEST HASH</span>
              <code data-testid="commitment-manifest-hash" style={{ color: 'var(--color-brand-primary)', wordBreak: 'break-all' }}>
                {commitmentData.manifestHash}
              </code>
            </div>
            <div>
              <span style={{ color: 'var(--color-text-muted)', fontSize: '11px', display: 'block' }}>SOURCE RUN ID</span>
              <code data-testid="commitment-source-run-id" style={{ color: 'var(--color-text-primary)', wordBreak: 'break-all' }}>
                {commitmentData.sourceRunId}
              </code>
            </div>
            <div>
              <span style={{ color: 'var(--color-text-muted)', fontSize: '11px', display: 'block' }}>COMMITTED AT</span>
              <span data-testid="commitment-committed-at" style={{ color: 'var(--color-text-secondary)' }}>
                {commitmentData.committedAt}
              </span>
            </div>
            <div>
              <span style={{ color: 'var(--color-text-muted)', fontSize: '11px', display: 'block' }}>RECOVERY EPOCH</span>
              <span data-testid="commitment-recovery-epoch" style={{ color: 'var(--color-text-secondary)' }}>
                {commitmentData.commitRecoveryEpoch}
              </span>
            </div>
            <div>
              <span style={{ color: 'var(--color-text-muted)', fontSize: '11px', display: 'block' }}>CURRENT AVAILABILITY</span>
              <code data-testid="commitment-availability" style={{ color: 'var(--color-status-degraded)' }}>
                {commitmentData.currentAvailability}
              </code>
            </div>
            <div>
              <span style={{ color: 'var(--color-text-muted)', fontSize: '11px', display: 'block' }}>EXECUTION REVALIDATION</span>
              <span data-testid="commitment-revalidation" style={{ color: 'var(--color-text-primary)' }}>
                {commitmentData.requiresExecutionRevalidation ? 'Required (true)' : 'False'}
              </span>
            </div>
            <div>
              <span style={{ color: 'var(--color-text-muted)', fontSize: '11px', display: 'block' }}>FORMAT / TOTAL BYTES</span>
              <span data-testid="commitment-format-bytes" style={{ color: 'var(--color-text-secondary)' }}>
                {commitmentData.format} ({commitmentData.totalBytes.toLocaleString()} bytes)
              </span>
            </div>
            <div>
              <span style={{ color: 'var(--color-text-muted)', fontSize: '11px', display: 'block' }}>SHARD COUNT</span>
              <span data-testid="commitment-shard-count" style={{ color: 'var(--color-text-secondary)' }}>
                {commitmentData.shardCount} shard(s)
              </span>
            </div>
          </div>
        )}
      </div>
    </div>
  );
};
