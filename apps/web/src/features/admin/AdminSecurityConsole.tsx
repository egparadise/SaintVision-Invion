import React, { useState, useEffect, useRef } from 'react';
import { NodeItem, SyntheticGpuResult, ContainmentInput, ContainmentView, ContainmentResult } from '@/contracts/types';
import { Button } from '@/shared/ui/Button';
import { useModalA11y } from '@/shared/ui/useModalA11y';
import { apiClient } from '@/shared/api/client';
import { SecurityControlManager } from './securityEngine';


function isValidUuid(id: string): boolean {
  return /^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$/i.test(id.trim());
}

function generateIdempotencyKey(prefix: string): string {
  return `${prefix}_${Date.now()}_${Math.random().toString(36).slice(2, 10)}`;
}

export interface AdminSecurityConsoleProps {
  nodes: NodeItem[];
  onRefreshNodes?: () => void;
  currentUser?: { id: string; name: string; role: string; tenantId?: string } | null;
}

export const AdminSecurityConsole: React.FC<AdminSecurityConsoleProps> = ({ nodes, onRefreshNodes, currentUser }) => {
  const [secManager] = useState<SecurityControlManager>(() => new SecurityControlManager());
  const [activeSubTab, setActiveSubTab] = useState<'audit' | 'isolation' | 'gpu' | 'backup' | 'drain'>('audit');
  const [status, setStatus] = useState(secManager.getStatus());
  const [auditLogs, setAuditLogs] = useState(secManager.getAuditLogs());
  const [drainError, setDrainError] = useState<string | null>(null);
  const [drainReasonCode, setDrainReasonCode] = useState<'maintenance' | 'incident' | 'operator_request'>('maintenance');
  const [drainApprovalId, setDrainApprovalId] = useState<string>('');
  type BackendKillSwitchState =
    | { status: 'loading' }
    | { status: 'active'; version?: number }
    | { status: 'inactive'; version?: number }
    | { status: 'error'; message: string };

  const [backendKillSwitch, setBackendKillSwitch] = useState<BackendKillSwitchState>({ status: 'loading' });
  const [gpuRunError, setGpuRunError] = useState<string | null>(null);
  interface CachedOperation {
    idempotencyKey: string;
    payload: ContainmentInput;
    targetAction: 'drain' | 'resume';
  }
  const cachedOperationsRef = useRef<Map<string, CachedOperation>>(new Map());
  const [nodeControlStatuses, setNodeControlStatuses] = useState<Record<string, { nodeStatus: string | null; version: number }>>({});

  const actor = currentUser?.id?.trim() || null;

  useEffect(() => {
    let isMounted = true;
    apiClient<ContainmentView>('/v1/operations/kill-switch')
      .then((res) => {
        if (!isMounted) return;
        if (res && typeof res.killSwitchActive === 'boolean') {
          setBackendKillSwitch({
            status: res.killSwitchActive ? 'active' : 'inactive',
            version: typeof res.version === 'number' ? res.version : undefined,
          });
        } else {
          setBackendKillSwitch({
            status: 'error',
            message: '조회 실패 [응답 형식 불일치]',
          });
        }
      })
      .catch((err: any) => {
        if (!isMounted) return;
        const code = err?.problem?.code || (err?.problem?.status ? `HTTP ${err.problem.status}` : err?.status ? `HTTP ${err.status}` : 'UNKNOWN');
        setBackendKillSwitch({
          status: 'error',
          message: `조회 실패 [${code}]`,
        });
      });
    return () => {
      isMounted = false;
    };
  }, []);

  // Interactive states
  const [ledgerVerification, setLedgerVerification] = useState<{ isValid: boolean; checked: number } | null>(null);
  const [mountTestPath, setMountTestPath] = useState('/var/run/docker.sock');
  const [mountTestResult, setMountTestResult] = useState<string | null>(null);

  useEffect(() => {
    let changed = false;
    nodes.forEach((n) => {
      const isDrainingOnServer = n.status === 'draining' || (n as any).isDraining === true;
      if (isDrainingOnServer && !secManager.isNodeDrained(n.id)) {
        secManager.drainNode(n.id, 'system', 'Cluster control plane reported draining status');
        changed = true;
      }
    });
    if (changed) {
      refreshState();
    }
  }, [nodes]);

  const handleToggleDrain = async (nodeId: string, currentlyDrained?: boolean) => {
    if (!actor) {
      setDrainError('인증된 관리자 세션이 없습니다. 노드 격리(Drain) 명령은 로그인된 관리자 식별자(actor)가 필수입니다.');
      return;
    }
    if (!isValidUuid(drainApprovalId)) {
      setDrainError('유효한 Containment 승인 UUID(approvalId)가 필요합니다. 합성 UUID는 거부됩니다.');
      return;
    }
    setDrainError(null);

    // 1. Determine targetAction strictly from UI's displayed intent
    const isNodeCurrentlyDrained = currentlyDrained !== undefined
      ? currentlyDrained
      : (nodeControlStatuses[nodeId]?.nodeStatus === 'draining' || nodeControlStatuses[nodeId]?.nodeStatus === 'quarantined' || secManager.isNodeDrained(nodeId));
    const targetAction: 'drain' | 'resume' = isNodeCurrentlyDrained ? 'resume' : 'drain';

    const opKey = `${nodeId}:${targetAction}:${drainReasonCode}:${drainApprovalId.trim()}`;
    let idempotencyKey: string;
    let payload: ContainmentInput;

    const cachedOp = cachedOperationsRef.current.get(opKey);
    if (cachedOp) {
      // Retry attempt: exactly reuse the same Idempotency-Key and first payload (including original expectedVersion)
      idempotencyKey = cachedOp.idempotencyKey;
      payload = cachedOp.payload;
    } else {
      // First attempt: check control version and server status
      let expectedVersion: number;
      let serverNodeStatus: string | null;
      try {
        const ctrl = await apiClient<ContainmentView>(`/v1/nodes/${encodeURIComponent(nodeId)}/control`);
        if (typeof ctrl?.version === 'number') {
          expectedVersion = ctrl.version;
          serverNodeStatus = ctrl.nodeStatus ?? null;
        } else {
          setDrainError('노드 제어 버전(expectedVersion) 응답 형식 불일치로 작업을 중단했습니다.');
          return;
        }

        // Update local cache of server control status
        setNodeControlStatuses((prev) => ({
          ...prev,
          [nodeId]: { nodeStatus: serverNodeStatus, version: expectedVersion },
        }));

        // Invariant: Server status must match user's displayed intention
        // If user wants 'drain', server must NOT already be draining/quarantined.
        // If user wants 'resume', server MUST be draining/quarantined.
        const isServerDrained = serverNodeStatus === 'draining' || serverNodeStatus === 'quarantined';
        const serverDiffers = targetAction === 'drain' ? isServerDrained : !isServerDrained;
        if (serverDiffers) {
          setDrainError('상태 변경됨·새로고침: 서버의 노드 제어 상태가 화면에 표시된 의도와 달라 작업을 중단했습니다. 새로고침 후 다시 시도하십시오.');
          return;
        }
      } catch (err: any) {
        console.error('Failed to fetch node control version:', err);
        const codeStr = err?.problem?.code ? `[${err.problem.code} (${err.problem.status})]` : err?.problem?.status ? `[${err.problem.status}]` : '';
        setDrainError(`노드 제어 버전(expectedVersion) 사전 조회 실패: ${codeStr} ${err?.problem?.title || err?.message || '조회 실패'}`);
        return;
      }

      idempotencyKey = generateIdempotencyKey(`containment_${nodeId}_${targetAction}`);
      payload = {
        expectedVersion,
        reasonCode: drainReasonCode,
        approvalId: drainApprovalId.trim(),
      };

      // Cache for retry idempotency
      cachedOperationsRef.current.set(opKey, {
        idempotencyKey,
        payload,
        targetAction,
      });
    }

    const endpoint = `/v1/nodes/${encodeURIComponent(nodeId)}/${targetAction}`;

    try {
      const result = await apiClient<ContainmentResult>(endpoint, {
        method: 'POST',
        idempotencyKey,
        body: JSON.stringify(payload),
      });

      // Invariant: Successful response MUST contain canonical control field. Do NOT synthesize!
      if (!result?.control || typeof result.control.nodeStatus !== 'string' || typeof result.control.version !== 'number') {
        setDrainError('응답 오류: 서버 응답에 canonical control 필드가 누락되었거나 형식이 올바르지 않습니다.');
        return;
      }

      // Success: clear cached retry operation
      cachedOperationsRef.current.delete(opKey);

      const canonicalStatus = result.control.nodeStatus;
      const canonicalVersion = result.control.version;

      setNodeControlStatuses((prev) => ({
        ...prev,
        [nodeId]: { nodeStatus: canonicalStatus, version: canonicalVersion },
      }));

      if (canonicalStatus === 'draining' || canonicalStatus === 'quarantined') {
        secManager.drainNode(nodeId, actor, `[${drainReasonCode}] approval: ${drainApprovalId.trim()}`);
      } else {
        secManager.undrainNode(nodeId, actor);
      }
      refreshState();
    } catch (err: any) {
      console.error(`Failed to execute node ${targetAction} on control plane:`, err);
      // Invariant: Non-retryable final failures (e.g. 409 GRAPH-0003, 403, 422, or retryable === false)
      // MUST clear the cache so subsequent user clicks re-query canonical /control and get fresh expectedVersion.
      // Cache is maintained ONLY for network errors or transient/retryable failures (5xx, 408, 429, retryable === true).
      const isProblem = !!err?.problem;
      const status = err?.problem?.status;
      const retryableFlag = err?.problem?.retryable;

      let shouldKeepCache = false;
      if (!isProblem) {
        // Network error (fetch failure, timeout before HTTP response)
        shouldKeepCache = true;
      } else if (retryableFlag === false) {
        // Explicitly marked non-retryable by server (e.g. 409 GRAPH-0003, 403, 422)
        shouldKeepCache = false;
      } else if (status === 408 || status === 429 || (typeof status === 'number' && status >= 500)) {
        // Transient server or rate-limit errors
        shouldKeepCache = true;
      } else if (retryableFlag === true && status !== 409 && status !== 403 && status !== 422) {
        shouldKeepCache = true;
      } else {
        // Other 4xx client errors (400, 401, 403, 404, 409, 422)
        shouldKeepCache = false;
      }

      if (!shouldKeepCache) {
        cachedOperationsRef.current.delete(opKey);
      }

      if (err?.problem) {
        const p = err.problem;
        const codeStr = p.code ? `[${p.code} (${p.status})]` : `[${p.status}]`;
        setDrainError(`${codeStr} ${p.title}: ${p.detail}`);
      } else {
        setDrainError(`노드 ${targetAction === 'drain' ? '격리(Drain)' : '재개'} 동기화 실패: ${err?.message || '제어 평면 오류'}`);
      }
    }

    if (onRefreshNodes) {
      onRefreshNodes();
    }
  };

  const gpuNodes = nodes.filter((n) => n.gpuName && n.gpuCount > 0);
  const [bypassRiskLevel, setBypassRiskLevel] = useState<'L1' | 'L2' | 'L3'>('L2');
  const [bypassTestResult, setBypassTestResult] = useState<string | null>(null);
  const [selectedGpuNodeId, setSelectedGpuNodeId] = useState<string>(() => gpuNodes[0]?.id || '');
  const [gpuResult, setGpuResult] = useState<SyntheticGpuResult | null>(null);
  const [isGpuRunning, setIsGpuRunning] = useState(false);
  const [showKillSwitchModal, setShowKillSwitchModal] = useState(false);
  const modalRef = useRef<HTMLDivElement>(null);
  const cancelBtnRef = useRef<HTMLButtonElement>(null);
  const previousActiveElementRef = useRef<HTMLElement | null>(null);

  const handleOpenKillSwitchModal = () => {
    previousActiveElementRef.current = (document.activeElement as HTMLElement) || null;
    setShowKillSwitchModal(true);
  };

  const handleCloseKillSwitchModal = () => {
    setShowKillSwitchModal(false);
    setTimeout(() => {
      const toggleBtn = document.querySelector('[data-testid="emergency-kill-switch-toggle-btn"]') as HTMLElement | null;
      const prevEl = previousActiveElementRef.current;
      if (prevEl && document.body.contains(prevEl) && !prevEl.textContent?.includes('Deactivate Kill Switch')) {
        prevEl.focus();
      } else if (toggleBtn) {
        toggleBtn.focus();
      }
    }, 0);
  };

  useEffect(() => {
    if (!showKillSwitchModal) return;

    // Initial focus on cancel button
    const timer = setTimeout(() => {
      cancelBtnRef.current?.focus();
    }, 0);

    const handleKeyDown = (e: KeyboardEvent) => {
      if (e.key === 'Escape') {
        e.preventDefault();
        handleCloseKillSwitchModal();
        return;
      }

      if (e.key === 'Tab') {
        if (!modalRef.current) return;
        const focusableEls = modalRef.current.querySelectorAll<HTMLElement>(
          'button:not([disabled]), [href], input:not([disabled]), select:not([disabled]), textarea:not([disabled]), [tabindex]:not([tabindex="-1"])'
        );
        if (focusableEls.length === 0) return;
        const firstEl = focusableEls[0];
        const lastEl = focusableEls[focusableEls.length - 1];

        if (e.shiftKey) {
          if (document.activeElement === firstEl || !modalRef.current.contains(document.activeElement)) {
            e.preventDefault();
            lastEl.focus();
          }
        } else {
          if (document.activeElement === lastEl || !modalRef.current.contains(document.activeElement)) {
            e.preventDefault();
            firstEl.focus();
          }
        }
      }
    };

    window.addEventListener('keydown', handleKeyDown);
    return () => {
      clearTimeout(timer);
      window.removeEventListener('keydown', handleKeyDown);
    };
  }, [showKillSwitchModal]);

  const { containerRef: killSwitchModalRef, handleKeyDown: handleKillSwitchKeyDown } = useModalA11y({
    isOpen: showKillSwitchModal,
    onClose: () => setShowKillSwitchModal(false),
  });

  const refreshState = () => {
    setStatus(secManager.getStatus());
    setAuditLogs(secManager.getAuditLogs());
  };

  // 1. Verify Ledger Cryptographic Hash Chaining
  const handleVerifyLedger = () => {
    const res = secManager.verifyLedgerIntegrity();
    setLedgerVerification({ isValid: res.isValid, checked: res.checkedRecords });
  };

  // 2. Test Docker Socket Mount
  const handleTestMount = (e: React.FormEvent) => {
    e.preventDefault();
    if (status.emergencyKillSwitchActive) {
      setMountTestResult('🛑 KILL SWITCH BLOCKED: 긴급 비상 정지(Kill Switch) 상태로 인해 마운트 검증 요청이 차단되었습니다.');
      return;
    }
    if (!actor) {
      setMountTestResult('🛑 ACCESS DENIED: 인증된 관리자 세션 식별자(actor)가 없어 마운트 경로 검증을 수행할 수 없습니다. (위조 식별자 합성 차단)');
      return;
    }
    const res = secManager.validateMountPath(mountTestPath, actor);
    refreshState();
    if (!res.allowed) {
      setMountTestResult(`🛑 ACCESS DENIED: ${res.reason}`);
    } else {
      setMountTestResult(`✔ MOUNT ALLOWED: Path ${mountTestPath} passed security checks.`);
    }
  };

  // 3. Test Approval Bypass
  const handleTestBypass = () => {
    if (status.emergencyKillSwitchActive) {
      setBypassTestResult('🛑 KILL SWITCH BLOCKED: 긴급 비상 정지(Kill Switch) 상태로 인해 승인 우회 검증 요청이 차단되었습니다.');
      return;
    }
    if (!actor) {
      setBypassTestResult('🛑 BYPASS BLOCKED: 인증된 관리자 세션 식별자(actor)가 없어 승인 우회 검증을 수행할 수 없습니다. (위조 식별자 합성 차단)');
      return;
    }
    const res = secManager.validateExecutionApproval(bypassRiskLevel, undefined, actor);
    refreshState();
    if (!res.allowed) {
      setBypassTestResult(`🛑 BYPASS BLOCKED: ${res.reason}`);
    } else {
      setBypassTestResult(`✔ TASK ALLOWED: ${bypassRiskLevel} does not require two-person rule.`);
    }
  };

  // 4. Run Synthetic GPU Benchmark
  const handleRunGpuBenchmark = () => {
    setGpuRunError(null);
    if (status.emergencyKillSwitchActive) {
      setGpuRunError('🛑 KILL SWITCH BLOCKED: 긴급 비상 정지(Kill Switch) 상태로 인해 합성 GPU 벤치마크 실행이 차단되었습니다.');
      return;
    }
    const targetNode = gpuNodes.find((n) => n.id === selectedGpuNodeId) || gpuNodes[0];
    if (!targetNode) return;
    setIsGpuRunning(true);
    setGpuResult(null);

    setTimeout(() => {
      const res = secManager.runSyntheticGpuBenchmark(targetNode.id, targetNode.gpuName || 'GPU');
      setGpuResult(res);
      setIsGpuRunning(false);
      refreshState();
    }, 600);
  };

  // 5. Toggle Emergency Kill Switch
  const handleConfirmKillSwitch = () => {
    if (!actor) {
      setDrainError('비상 정지(Kill Switch) 명령을 실행하려면 인증된 관리자 식별자(actor)가 필수입니다.');
      handleCloseKillSwitchModal();
      return;
    }
    secManager.toggleEmergencyKillSwitch(actor, 'Admin manual emergency intervention');
    handleCloseKillSwitchModal();
    refreshState();
  };

  return (
    <div style={{ padding: '24px', maxWidth: '1400px', margin: '0 auto', display: 'flex', flexDirection: 'column', gap: '20px' }}>
      {/* Emergency Kill Switch Banner if Active */}
      {status.emergencyKillSwitchActive && (
        <div
          role="alert"
          data-testid="kill-switch-active-banner"
          style={{
            backgroundColor: 'rgba(248, 81, 73, 0.2)',
            border: '2px solid #f85149',
            borderRadius: '8px',
            padding: '16px 20px',
            display: 'flex',
            justifyContent: 'space-between',
            alignItems: 'center',
          }}
        >
          <div>
            <div style={{ color: '#f85149', fontWeight: 'bold', fontSize: '16px' }}>
              🚨 [모의 시뮬레이션] EMERGENCY KILL SWITCH ACTIVE — LOCAL SECURITY ENGINE ISOLATION
            </div>
            <div style={{ color: '#c9d1d9', fontSize: '13px', marginTop: '4px' }}>
              로컬 보안 통제 엔진이 모의 격리 상태입니다. (백엔드 제어 평면 비상 정지 API(GET/POST /v1/operations/kill-switch)가 존재하며, 본 토글은 UI 로컬 보안 엔진 시뮬레이션 격리 상태입니다)
            </div>
          </div>
          <Button variant="danger" size="sm" onClick={handleOpenKillSwitchModal}>
            Deactivate Kill Switch
          </Button>
        </div>
      )}

      {/* Admin Session Actor Missing Notice */}
      {!actor && (
        <div
          role="alert"
          data-testid="admin-auth-required-notice"
          style={{
            padding: '12px 16px',
            backgroundColor: 'rgba(248, 81, 73, 0.15)',
            border: '1px solid #f85149',
            borderRadius: '6px',
            color: '#f85149',
            fontSize: '13px',
          }}
        >
          ⚠️ <strong>인증된 관리자 세션 부재</strong>: 관리자 세션 식별자(actor)가 확인되지 않았습니다. 노드 격리(Drain) 및 비상 정지(Kill Switch)와 같은 제어 평면 변경 작업이 차단됩니다.
        </div>
      )}

      {drainError && (
        <div
          role="alert"
          data-testid="admin-drain-error-banner"
          style={{
            padding: '12px 16px',
            backgroundColor: 'rgba(248, 81, 73, 0.15)',
            border: '1px solid #f85149',
            borderRadius: '6px',
            color: '#f85149',
            fontSize: '13px',
          }}
        >
          ❌ {drainError}
        </div>
      )}

      {/* Top Security KPI Tiles */}
      <div
        style={{
          display: 'grid',
          gridTemplateColumns: 'repeat(auto-fit, minmax(260px, 1fr))',
          gap: '16px',
        }}
      >
        <div style={{ backgroundColor: '#161b22', border: '1px solid #30363d', borderRadius: '8px', padding: '16px 20px' }}>
          <div style={{ fontSize: '12px', color: '#8b949e', fontWeight: 600 }}>Docker Socket 노출 여부</div>
          <div style={{ fontSize: '20px', fontWeight: 700, color: '#3fb950', marginTop: '4px' }}>
            {status.dockerSocketAttemptsBlocked} 건 차단 (모의 격리; 물리 컨테이너 UNMEASURED)
          </div>
          <div style={{ fontSize: '12px', color: '#8b949e', marginTop: '4px' }}>AC-08 미노출 보증 (모의 통과)</div>
        </div>

        <div style={{ backgroundColor: '#161b22', border: '1px solid #30363d', borderRadius: '8px', padding: '16px 20px' }}>
          <div style={{ fontSize: '12px', color: '#8b949e', fontWeight: 600 }}>승인 우회 시도 차단 수</div>
          <div style={{ fontSize: '20px', fontWeight: 700, color: '#3fb950', marginTop: '4px' }}>
            {status.approvalBypassesBlocked} 건 차단 (모의 차단; 물리 승인은 UNMEASURED)
          </div>
          <div style={{ fontSize: '12px', color: '#8b949e', marginTop: '4px' }}>L2/L3 위험 작업 Two-Person 강제</div>
        </div>

        <div style={{ backgroundColor: '#161b22', border: '1px solid #30363d', borderRadius: '8px', padding: '16px 20px' }}>
          <div style={{ fontSize: '12px', color: '#8b949e', fontWeight: 600 }}>합성 GPU 실행 검증</div>
          <div style={{ fontSize: '20px', fontWeight: 700, color: '#58a6ff', marginTop: '4px' }}>
            {gpuResult
              ? (gpuResult.exitCode === 0 ? '성공 (Exit 0; 모의)' : `실패 (Exit ${gpuResult.exitCode})`)
              : (gpuNodes.length > 0 ? '대기 중 (모의 검증 준비; 물리 GPU UNMEASURED)' : 'UNMEASURED (GPU 노드 없음)')}
          </div>
          <div style={{ fontSize: '12px', color: '#8b949e', marginTop: '4px' }}>RTX 4090 / A4000 합성 벤치마크 (물리 GPU 미측정)</div>
        </div>

        <div style={{ backgroundColor: '#161b22', border: '1px solid #30363d', borderRadius: '8px', padding: '16px 20px' }}>
          <div style={{ fontSize: '12px', color: '#8b949e', fontWeight: 600 }}>WAL 백업 RPO 현황</div>
          <div style={{ fontSize: '20px', fontWeight: 700, color: '#3fb950', marginTop: '4px' }}>
            {status.rpoMinutes} 분 전 (모의; 물리 S3 오프사이트 UNMEASURED)
          </div>
          <div style={{ fontSize: '12px', color: '#8b949e', marginTop: '4px' }}>RTO 12분 (모의; 물리 PITR UNMEASURED)</div>
        </div>
      </div>

      {/* Header Bar with Sub-tabs and Emergency Kill Switch Button */}
      <div
        style={{
          display: 'flex',
          justifyContent: 'space-between',
          alignItems: 'center',
          backgroundColor: '#161b22',
          border: '1px solid #30363d',
          borderRadius: '8px',
          padding: '12px 20px',
        }}
      >
        <div style={{ display: 'flex', gap: '8px' }}>
          <Button
            size="sm"
            variant={activeSubTab === 'audit' ? 'primary' : 'secondary'}
            onClick={() => setActiveSubTab('audit')}
          >
            감사 로그 원장 (Audit Trail)
          </Button>
          <Button
            size="sm"
            variant={activeSubTab === 'isolation' ? 'primary' : 'secondary'}
            onClick={() => setActiveSubTab('isolation')}
          >
            소켓·승인 격리 검증 (AC-08)
          </Button>
          <Button
            size="sm"
            variant={activeSubTab === 'gpu' ? 'primary' : 'secondary'}
            onClick={() => setActiveSubTab('gpu')}
          >
            합성 GPU 성능 검증
          </Button>
          <Button
            size="sm"
            variant={activeSubTab === 'backup' ? 'primary' : 'secondary'}
            onClick={() => setActiveSubTab('backup')}
          >
            재해 복구 및 WAL 백업
          </Button>
          <Button
            size="sm"
            variant={activeSubTab === 'drain' ? 'primary' : 'secondary'}
            onClick={() => setActiveSubTab('drain')}
          >
            노드 Drain 통제 (ADR-054)
          </Button>
        </div>

        <div style={{ display: 'flex', flexDirection: 'column', alignItems: 'flex-end', gap: '4px' }}>
          <Button
            size="sm"
            variant={status.emergencyKillSwitchActive ? 'secondary' : 'danger'}
            onClick={handleOpenKillSwitchModal}
            disabled={!actor}
            aria-disabled={!actor}
            title={!actor ? '관리자 세션 식별자(actor)가 필요합니다.' : undefined}
            data-testid="emergency-kill-switch-toggle-btn"
          >
            {status.emergencyKillSwitchActive ? 'Kill Switch 해제 (모의)' : '🚨 긴급 Kill Switch 발동 (모의)'}
          </Button>
          <div data-testid="backend-kill-switch-status" style={{ fontSize: '11px', color: '#8b949e' }}>
            백엔드 제어 평면: {
              backendKillSwitch.status === 'loading'
                ? '확인 중...'
                : backendKillSwitch.status === 'active'
                ? '🚨 ACTIVE'
                : backendKillSwitch.status === 'inactive'
                ? '✔ INACTIVE'
                : `⚠️ ${backendKillSwitch.message}`
            } (GET /v1/operations/kill-switch)
          </div>
        </div>
      </div>

      {/* Sub-Tab 1: Immutable Audit Trail */}
      {activeSubTab === 'audit' && (
        <div
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
          <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
            <div>
              <h3 style={{ margin: 0, fontSize: '16px', color: '#f0f6fc' }}>
                불변 감사 로그 원장 (로컬 합성 원장; 백엔드 감사 아님)
              </h3>
              <p style={{ margin: '4px 0 0 0', fontSize: '12px', color: '#8b949e' }}>
                W3C Trace ID 기반 단방향 해시 체이닝 (Append-Only Cryptographic Ledger; 로컬 시뮬레이션)
              </p>
            </div>
            <div style={{ display: 'flex', alignItems: 'center', gap: '12px' }}>
              {ledgerVerification && (
                <span style={{ fontSize: '12px', color: ledgerVerification.isValid ? '#3fb950' : '#f85149', fontWeight: 600 }}>
                  {ledgerVerification.isValid ? `✔ ${ledgerVerification.checked}개 레코드 무결성 검증 완료` : '❌ 원장 변조 감지됨'}
                </span>
              )}
              <Button size="sm" variant="secondary" onClick={handleVerifyLedger}>
                원장 암호화 무결성 검사
              </Button>
            </div>
          </div>

          <table style={{ width: '100%', borderCollapse: 'collapse', fontSize: '13px', color: '#c9d1d9' }}>
            <thead>
              <tr style={{ borderBottom: '1px solid #30363d', textAlign: 'left', color: '#8b949e' }}>
                <th style={{ padding: '10px 8px' }}>Timestamp</th>
                <th style={{ padding: '10px 8px' }}>Actor</th>
                <th style={{ padding: '10px 8px' }}>Action</th>
                <th style={{ padding: '10px 8px' }}>Target</th>
                <th style={{ padding: '10px 8px' }}>Outcome</th>
                <th style={{ padding: '10px 8px' }}>Details</th>
                <th style={{ padding: '10px 8px' }}>Integrity Hash</th>
              </tr>
            </thead>
            <tbody>
              {auditLogs.map((log) => (
                <tr key={log.id} style={{ borderBottom: '1px solid #21262d' }}>
                  <td style={{ padding: '10px 8px', color: '#8b949e', whiteSpace: 'nowrap' }}>
                    {new Date(log.timestamp).toLocaleTimeString()}
                  </td>
                  <td style={{ padding: '10px 8px', fontFamily: 'var(--font-mono, monospace)', color: '#58a6ff' }}>
                    {log.actor}
                  </td>
                  <td style={{ padding: '10px 8px', fontWeight: 600 }}>{log.action}</td>
                  <td style={{ padding: '10px 8px' }}><code>{log.target}</code></td>
                  <td style={{ padding: '10px 8px' }}>
                    <span
                      style={{
                        padding: '2px 6px',
                        borderRadius: '4px',
                        fontSize: '11px',
                        fontWeight: 700,
                        backgroundColor: log.outcome === 'allowed' ? 'rgba(46, 160, 67, 0.2)' : 'rgba(248, 81, 73, 0.2)',
                        color: log.outcome === 'allowed' ? '#3fb950' : '#f85149',
                      }}
                    >
                      {log.outcome.toUpperCase()}
                    </span>
                  </td>
                  <td style={{ padding: '10px 8px', color: '#8b949e' }}>{log.details}</td>
                  <td style={{ padding: '10px 8px', fontFamily: 'var(--font-mono, monospace)', color: '#8b949e', fontSize: '11px' }}>
                    {log.integrityHash.slice(0, 12)}...
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}

      {/* Sub-Tab 2: Socket & Approval Isolation */}
      {activeSubTab === 'isolation' && (
        <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: '20px' }}>
          {/* Docker Socket Inspector */}
          <div
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
            <div>
              <h4 style={{ margin: 0, fontSize: '15px', color: '#f0f6fc' }}>
                Docker Socket 미노출 검증 (AC-08)
              </h4>
              <p style={{ margin: '4px 0 0 0', fontSize: '12px', color: '#8b949e' }}>
                컨테이너 호스트 제어권 탈취를 유발하는 `/var/run/docker.sock` 마운트 시도 원천 차단 검증
              </p>
            </div>

            <form onSubmit={handleTestMount} style={{ display: 'flex', gap: '8px' }}>
              <input
                type="text"
                value={mountTestPath}
                onChange={(e) => setMountTestPath(e.target.value)}
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
              <Button size="sm" variant="secondary" type="submit">
                마운트 요청 시험
              </Button>
            </form>

            {mountTestResult && (
              <div
                data-testid="mount-test-result"
                style={{
                  padding: '10px 14px',
                  borderRadius: '6px',
                  fontSize: '12px',
                  backgroundColor: mountTestResult.includes('DENIED') ? 'rgba(248, 81, 73, 0.15)' : 'rgba(46, 160, 67, 0.15)',
                  border: mountTestResult.includes('DENIED') ? '1px solid #f85149' : '1px solid #3fb950',
                  color: mountTestResult.includes('DENIED') ? '#f85149' : '#3fb950',
                }}
              >
                {mountTestResult}
              </div>
            )}
          </div>

          {/* Approval Bypass Filter */}
          <div
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
            <div>
              <h4 style={{ margin: 0, fontSize: '15px', color: '#f0f6fc' }}>
                승인 우회 방지 검증 (AC-08)
              </h4>
              <p style={{ margin: '4px 0 0 0', fontSize: '12px', color: '#8b949e' }}>
                L2/L3 등급 고위험 명령이 거버넌스 승인 ID 없이 단독 실행되는 시도를 100% 차단
              </p>
            </div>

            <div style={{ display: 'flex', alignItems: 'center', gap: '12px' }}>
              <label style={{ fontSize: '13px', color: '#8b949e' }}>시험할 위험 등급:</label>
              <select
                value={bypassRiskLevel}
                onChange={(e) => setBypassRiskLevel(e.target.value as any)}
                style={{
                  padding: '8px 12px',
                  backgroundColor: '#0d1117',
                  border: '1px solid #30363d',
                  borderRadius: '6px',
                  color: '#c9d1d9',
                  fontSize: '13px',
                }}
              >
                <option value="L1">L1 (저위험, 자가 승인 가능)</option>
                <option value="L2">L2 (중위험, 승인 ID 필수)</option>
                <option value="L3">L3 (고위험, 2인 승인 필수)</option>
              </select>
              <Button size="sm" variant="secondary" onClick={handleTestBypass} data-testid="test-bypass-btn">
                우회 실행 시험
              </Button>
            </div>

            {bypassTestResult && (
              <div
                data-testid="bypass-test-result"
                style={{
                  padding: '10px 14px',
                  borderRadius: '6px',
                  fontSize: '12px',
                  backgroundColor: bypassTestResult.includes('BLOCKED') ? 'rgba(248, 81, 73, 0.15)' : 'rgba(46, 160, 67, 0.15)',
                  border: bypassTestResult.includes('BLOCKED') ? '1px solid #f85149' : '1px solid #3fb950',
                  color: bypassTestResult.includes('BLOCKED') ? '#f85149' : '#3fb950',
                }}
              >
                {bypassTestResult}
              </div>
            )}
          </div>
        </div>
      )}

      {/* Sub-Tab 3: Synthetic GPU Capability */}
      {activeSubTab === 'gpu' && (
        <div
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
          <div>
            <h3 style={{ margin: 0, fontSize: '16px', color: '#f0f6fc' }}>
              합성 GPU 작업 실행 성능 검증 (AC-08)
            </h3>
            <p style={{ margin: '4px 0 0 0', fontSize: '12px', color: '#8b949e' }}>
              FP16 GEMM 텐서 연산 벤치마크 및 VRAM 할당 격리 검증
            </p>
          </div>

          <div style={{ display: 'flex', alignItems: 'center', gap: '16px' }}>
            <label style={{ fontSize: '13px', color: '#8b949e' }}>대상 GPU 노드:</label>
            <select
              data-testid="gpu-node-select"
              value={selectedGpuNodeId}
              onChange={(e) => setSelectedGpuNodeId(e.target.value)}
              disabled={gpuNodes.length === 0}
              style={{
                padding: '8px 12px',
                backgroundColor: '#0d1117',
                border: '1px solid #30363d',
                borderRadius: '6px',
                color: '#c9d1d9',
                fontSize: '13px',
              }}
            >
              {gpuNodes.length === 0 ? (
                <option value="">(클러스터 내 가용 GPU 노드 없음)</option>
              ) : (
                gpuNodes.map((n) => (
                  <option key={n.id} value={n.id}>
                    {n.hostname} — {n.gpuName} ({Math.round((n.gpuVramTotalBytes || 0) / 1024 ** 3)}GB VRAM)
                  </option>
                ))
              )}
            </select>

            <Button
              size="sm"
              variant="primary"
              data-testid="run-gpu-benchmark-btn"
              onClick={handleRunGpuBenchmark}
              disabled={isGpuRunning || gpuNodes.length === 0}
            >
              {isGpuRunning ? '합성 GPU 벤치마크 실행 중...' : '합성 GPU 벤치마크 실행'}
            </Button>
          </div>

          {gpuRunError && (
            <div
              role="alert"
              data-testid="gpu-benchmark-error"
              style={{
                padding: '10px 14px',
                borderRadius: '6px',
                fontSize: '12px',
                backgroundColor: 'rgba(248, 81, 73, 0.15)',
                border: '1px solid #f85149',
                color: '#f85149',
              }}
            >
              {gpuRunError}
            </div>
          )}

          {gpuNodes.length === 0 && (
            <div
              data-testid="no-gpu-nodes-notice"
              style={{
                padding: '8px 12px',
                borderRadius: '6px',
                fontSize: '12px',
                backgroundColor: 'rgba(239, 68, 68, 0.15)',
                border: '1px solid #ef4444',
                color: '#fca5a5',
              }}
            >
              ⚠️ 클러스터 내에 가용한 GPU 노드가 없습니다. (위조 노드 합성 차단)
            </div>
          )}

          {gpuResult && (
            <div
              style={{
                backgroundColor: '#0d1117',
                border: '1px solid #3fb950',
                borderRadius: '6px',
                padding: '16px',
                display: 'flex',
                flexDirection: 'column',
                gap: '10px',
              }}
            >
              <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
                <span style={{ color: '#3fb950', fontWeight: 600, fontSize: '14px' }}>
                  ✔ 합성 GPU 벤치마크 정상 완료 (Exit Code: {gpuResult.exitCode})
                </span>
                <span style={{ fontSize: '12px', color: '#8b949e' }}>Evidence: <code>{gpuResult.evidenceId}</code></span>
              </div>

              <div style={{ display: 'grid', gridTemplateColumns: 'repeat(4, 1fr)', gap: '12px', fontSize: '13px' }}>
                <div>
                  <span style={{ color: '#8b949e' }}>Target GPU:</span>
                  <div style={{ fontWeight: 600, color: '#f0f6fc' }}>{gpuResult.gpuName}</div>
                </div>
                <div>
                  <span style={{ color: '#8b949e' }}>Allocated VRAM:</span>
                  <div style={{ fontWeight: 600, color: '#f0f6fc' }}>{Math.round(gpuResult.vramAllocatedBytes / 1024 ** 3)} GB</div>
                </div>
                <div>
                  <span style={{ color: '#8b949e' }}>Compute Throughput:</span>
                  <div style={{ fontWeight: 600, color: '#58a6ff' }}>{gpuResult.computeThroughputTflops} TFLOPS</div>
                </div>
                <div>
                  <span style={{ color: '#8b949e' }}>Completed:</span>
                  <div style={{ color: '#c9d1d9' }}>{new Date(gpuResult.completedAt).toLocaleTimeString()}</div>
                </div>
              </div>
            </div>
          )}
        </div>
      )}

      {/* Sub-Tab 4: Backup & Disaster Recovery */}
      {activeSubTab === 'backup' && (
        <div
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
          <div>
            <h3 style={{ margin: 0, fontSize: '16px', color: '#f0f6fc' }}>
              재해 복구 및 WAL 백업 원장 (AC-08)
            </h3>
            <p style={{ margin: '4px 0 0 0', fontSize: '12px', color: '#8b949e' }}>
              PostgreSQL WAL 기반 PITR 복원 및 Fencing Epoch 단조 전진 연계
            </p>
          </div>

          <div style={{ display: 'grid', gridTemplateColumns: 'repeat(3, 1fr)', gap: '16px' }}>
            <div style={{ backgroundColor: '#0d1117', padding: '14px', borderRadius: '6px', border: '1px solid #30363d' }}>
              <div style={{ fontSize: '12px', color: '#8b949e' }}>Latest Snapshot WAL</div>
              <div style={{ fontSize: '18px', fontWeight: 600, color: '#f0f6fc', marginTop: '4px' }}>
                000000010000000A0000002F
              </div>
              <div style={{ fontSize: '11px', color: '#3fb950', marginTop: '2px' }}>4분 전 기록 (모의 시뮬레이션; 물리 WAL UNMEASURED)</div>
            </div>

            <div style={{ backgroundColor: '#0d1117', padding: '14px', borderRadius: '6px', border: '1px solid #30363d' }}>
              <div style={{ fontSize: '12px', color: '#8b949e' }}>RPO 달성도 (Target ≤ 15m)</div>
              <div style={{ fontSize: '18px', fontWeight: 600, color: '#3fb950', marginTop: '4px' }}>
                4.2 분 (모의 PASS; 물리 S3 RPO UNMEASURED)
              </div>
              <div style={{ fontSize: '11px', color: '#8b949e', marginTop: '2px' }}>S3 복제 (모의 시뮬레이션; 물리 오프사이트 UNMEASURED)</div>
            </div>

            <div style={{ backgroundColor: '#0d1117', padding: '14px', borderRadius: '6px', border: '1px solid #30363d' }}>
              <div style={{ fontSize: '12px', color: '#8b949e' }}>RTO 모의 추정치 (Target ≤ 60m; 물리 RTO UNMEASURED)</div>
              <div style={{ fontSize: '18px', fontWeight: 600, color: '#58a6ff', marginTop: '4px' }}>
                12.5 분 (모의 PASS; 물리 PITR 복원 UNMEASURED)
              </div>
              <div style={{ fontSize: '11px', color: '#8b949e', marginTop: '2px' }}>Epoch 전진 포함 (물리 재해 복구 UNMEASURED)</div>
            </div>
          </div>
        </div>
      )}

      {/* Sub-Tab 5: Node Drain & Schedulable Control (ADR-054) */}
      {activeSubTab === 'drain' && (
        <div
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
          <div>
            <h3 style={{ margin: 0, fontSize: '16px', color: '#f0f6fc' }}>
              클러스터 노드 Drain 및 스케줄링 통제 (ADR-054)
            </h3>
            <p style={{ margin: '4px 0 0 0', fontSize: '12px', color: '#8b949e' }}>
              점검 또는 장애 노드를 스케줄링에서 즉시 제외(Drain)하고 실행 중인 워크로드를 안전하게 격리합니다.
            </p>
          </div>

          <div
            style={{
              display: 'flex',
              flexDirection: 'column',
              gap: '10px',
              padding: '14px',
              backgroundColor: '#0d1117',
              borderRadius: '6px',
              border: '1px solid #30363d',
            }}
          >
            <div style={{ display: 'flex', gap: '16px', alignItems: 'center', flexWrap: 'wrap' }}>
              <label style={{ fontSize: '12px', color: '#8b949e' }}>
                사유 코드 (Reason Code):
                <select
                  data-testid="drain-reason-code-select"
                  value={drainReasonCode}
                  onChange={(e) => setDrainReasonCode(e.target.value as any)}
                  style={{
                    marginLeft: '8px',
                    padding: '6px 10px',
                    backgroundColor: '#161b22',
                    border: '1px solid #30363d',
                    borderRadius: '4px',
                    color: '#c9d1d9',
                    fontSize: '12px',
                  }}
                >
                  <option value="maintenance">maintenance (유지보수)</option>
                  <option value="incident">incident (장애 조치)</option>
                  <option value="operator_request">operator_request (운영자 요청)</option>
                </select>
              </label>

              <label style={{ fontSize: '12px', color: '#8b949e', flex: 1, minWidth: '320px', display: 'flex', alignItems: 'center' }}>
                <span>승인 식별자 (Approval ID):</span>
                <input
                  type="text"
                  data-testid="drain-approval-id-input"
                  value={drainApprovalId}
                  onChange={(e) => setDrainApprovalId(e.target.value)}
                  placeholder="UUIDv4 (예: 550e8400-e29b-41d4-a716-446655440000)"
                  style={{
                    marginLeft: '8px',
                    flex: 1,
                    padding: '6px 10px',
                    backgroundColor: '#161b22',
                    border: `1px solid ${isValidUuid(drainApprovalId) ? '#3fb950' : '#f85149'}`,
                    borderRadius: '4px',
                    color: '#c9d1d9',
                    fontSize: '12px',
                    fontFamily: 'var(--font-mono, monospace)',
                  }}
                />
              </label>
            </div>

            {!isValidUuid(drainApprovalId) && (
              <div
                role="alert"
                data-testid="drain-approval-required-notice"
                style={{ fontSize: '12px', color: '#f85149' }}
              >
                ⚠️ 유효한 Containment 승인 UUID(UUIDv4) 입력이 필수입니다. 합성 UUID는 거부되며, 입력되지 않으면 노드 Drain/Resume 실행이 비활성화됩니다.
              </div>
            )}
          </div>

          <div style={{ display: 'flex', flexDirection: 'column', gap: '10px' }}>
            {nodes.map((n) => {
              const serverStatus = nodeControlStatuses[n.id]?.nodeStatus;
              const isDrained = serverStatus
                ? (serverStatus === 'draining' || serverStatus === 'quarantined')
                : (n.status === 'draining' || secManager.isNodeDrained(n.id));
              return (
                <div
                  key={n.id}
                  style={{
                    display: 'flex',
                    justifyContent: 'space-between',
                    alignItems: 'center',
                    padding: '14px 18px',
                    backgroundColor: '#0d1117',
                    border: `1px solid ${isDrained ? '#f85149' : '#30363d'}`,
                    borderRadius: '6px',
                  }}
                >
                  <div style={{ display: 'flex', flexDirection: 'column', gap: '4px' }}>
                    <div style={{ display: 'flex', alignItems: 'center', gap: '10px' }}>
                      <span style={{ fontWeight: 600, color: '#f0f6fc', fontSize: '14px' }}>
                        {n.hostname}
                      </span>
                      <code style={{ fontSize: '11px', color: '#58a6ff' }}>{n.id}</code>
                      <span
                        style={{
                          fontSize: '11px',
                          padding: '2px 8px',
                          borderRadius: '12px',
                          backgroundColor: isDrained ? 'rgba(248,81,73,0.2)' : 'rgba(63,185,80,0.2)',
                          color: isDrained ? '#f85149' : '#3fb950',
                          fontWeight: 600,
                        }}
                      >
                        {isDrained ? '🚨 DRAINED (스케줄링 제외)' : '✔ SCHEDULABLE (가용)'}
                      </span>
                      {n.observationOnly && (
                        <span style={{ fontSize: '11px', padding: '2px 8px', borderRadius: '12px', backgroundColor: 'rgba(210,153,34,0.2)', color: '#d29922' }}>
                          관측 전용
                        </span>
                      )}
                    </div>
                    <div style={{ fontSize: '12px', color: '#8b949e' }}>
                      {n.telemetryUnavailable ? '자원 정보 미관측' : `OS: ${n.os.toUpperCase()} • CPU: ${n.cpuCores}C (${n.cpuUsagePercent}%) • RAM: ${(n.memoryTotalBytes / 1024 ** 3).toFixed(0)} GiB`}
                      {n.gpuName && ` • GPU: ${n.gpuName}`}
                    </div>
                  </div>

                  <Button
                    size="sm"
                    variant={isDrained ? 'primary' : 'danger'}
                    onClick={() => handleToggleDrain(n.id, isDrained)}
                    disabled={!actor || !isValidUuid(drainApprovalId)}
                    title={
                      !actor
                        ? '관리자 세션 식별자(actor)가 필요합니다.'
                        : !isValidUuid(drainApprovalId)
                        ? '유효한 승인 UUID(approvalId)가 필요합니다.'
                        : undefined
                    }
                    data-testid={`drain-node-btn-${n.id}`}
                  >
                    {isDrained ? '✔ Drain 해제 (Schedulable)' : '🚨 Node Drain'}
                  </Button>
                </div>
              );
            })}
          </div>
        </div>
      )}

      {/* Emergency Kill Switch Confirmation Modal */}
      {showKillSwitchModal && (
        <div
          ref={killSwitchModalRef}
          role="dialog"
          aria-modal="true"
          aria-labelledby="kill-switch-modal-title"
          onKeyDown={handleKillSwitchKeyDown}
          tabIndex={-1}
          data-testid="kill-switch-modal"
          style={{
            position: 'fixed',
            inset: 0,
            backgroundColor: 'rgba(0,0,0,0.75)',
            display: 'flex',
            alignItems: 'center',
            justifyContent: 'center',
            zIndex: 1000,
            padding: '20px',
          }}
        >
          <div
            ref={modalRef}
            tabIndex={-1}
            style={{
              width: '100%',
              maxWidth: '520px',
              backgroundColor: '#161b22',
              border: '2px solid #f85149',
              borderRadius: '8px',
              padding: '24px',
              display: 'flex',
              flexDirection: 'column',
              gap: '16px',
            }}
          >
            <h3 id="kill-switch-modal-title" style={{ margin: 0, color: '#f85149', fontSize: '18px' }}>
              {status.emergencyKillSwitchActive ? 'Kill Switch 비활성화 확인' : '🚨 [모의 시뮬레이션] 긴급 Kill Switch 발동 확인'}
            </h3>
            <div
              role="status"
              data-testid="kill-switch-mock-notice"
              style={{
                padding: '10px 14px',
                borderRadius: '6px',
                backgroundColor: 'rgba(234, 179, 8, 0.15)',
                border: '1px solid #eab308',
                color: '#fde047',
                fontSize: '12px',
                lineHeight: '1.5',
              }}
            >
              ⚠️ <strong>[모의 시뮬레이션 고지]</strong>: 백엔드 제어 평면에 비상 정지 API(GET/POST /v1/operations/kill-switch)가 존재합니다. 현재 화면의 토글은 프론트엔드 보안 엔진의 로컬 모의 에뮬레이션(Local Simulation)으로 동작하며, 로컬 비상 정지 발동 시 화면 내 모의 작업 디스패치(소켓 마운트 시험, 승인 우회 시험, GPU 벤치마크)가 차단됩니다. 백엔드 계약 불변식에 따라 노드 격리(Drain/Resume) 제어는 비상 정지 상태에서도 안전한 장애 격리를 위해 계속 허용됩니다.
            </div>
            <p style={{ margin: 0, color: '#c9d1d9', fontSize: '13px', lineHeight: '20px' }}>
              {status.emergencyKillSwitchActive
                ? 'Kill Switch를 해제하면 클러스터 보안 엔진 모의 작업 디스패치가 재개됩니다.'
                : 'Kill Switch를 발동하면 프론트엔드 보안 통제 계층에서 모든 모의 작업 디스패치가 일시 중지됩니다.'}
            </p>
            <div style={{ display: 'flex', justifyContent: 'flex-end', gap: '10px' }}>
              <Button
                ref={cancelBtnRef}
                size="sm"
                variant="secondary"
                onClick={handleCloseKillSwitchModal}
                data-testid="kill-switch-cancel-btn"
              >
                취소
              </Button>
              <Button
                size="sm"
                variant={status.emergencyKillSwitchActive ? 'primary' : 'danger'}
                onClick={handleConfirmKillSwitch}
                data-testid="kill-switch-confirm-btn"
              >
                {status.emergencyKillSwitchActive ? '해제 실행' : '긴급 발동 확정'}
              </Button>
            </div>
          </div>
        </div>
      )}
    </div>
  );
};
