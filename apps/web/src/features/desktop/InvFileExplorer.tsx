import React, { useState, useMemo, useCallback, useEffect } from 'react';
import { InvFileItem, InvReplicaLocation, InvNamespace } from '@/contracts/virtualFabric';
import { NodeItem } from '@/contracts/types';
import { fetchWorkspaceEditView, mapWorkspaceFilesToInvItems } from '@/shared/api/workspaceEditObservation';

export interface InvFileExplorerProps {
  projectId?: string;
  runId?: string;
  checkoutId?: string;
  initialUri?: string;
  initialNamespace?: InvNamespace;
  initialFiles?: InvFileItem[];
  clusterNodes?: NodeItem[];
  onOpenFile?: (file: InvFileItem) => void;
  onVerifyIntegrity?: (file: InvFileItem) => Promise<{ calculatedHash: string; matches: boolean }>;
  onRepairReplicas?: (
    fileUri: string,
    targetNodeId: string
  ) => Promise<{ success: boolean; repairedReplicas: InvReplicaLocation[]; message?: string }>;
}

export async function calculateSha256(content: string | Uint8Array): Promise<string> {
  const data = typeof content === 'string' ? new TextEncoder().encode(content) : content;
  if (typeof globalThis.crypto?.subtle?.digest === 'function') {
    const hashBuffer = await globalThis.crypto.subtle.digest('SHA-256', data as unknown as BufferSource);
    const hashArray = Array.from(new Uint8Array(hashBuffer));
    return hashArray.map((b) => b.toString(16).padStart(2, '0')).join('');
  }
  throw new Error('WebCrypto API가 지원되지 않아 무결성을 검증할 수 없습니다.');
}

export const InvFileExplorer: React.FC<InvFileExplorerProps> = ({
  projectId,
  runId,
  checkoutId,
  initialUri = 'inv://models',
  initialNamespace = 'models',
  initialFiles = [],
  clusterNodes = [],
  onOpenFile,
  onVerifyIntegrity,
  onRepairReplicas,
}) => {
  const [currentUri, setCurrentUri] = useState<string>(initialUri);
  const [activeNamespace, setActiveNamespace] = useState<InvNamespace>(initialNamespace);
  const [files, setFiles] = useState<InvFileItem[]>(initialFiles);
  const [selectedFile, setSelectedFile] = useState<InvFileItem | null>(initialFiles[0] || null);
  const [targetNodeId, setTargetNodeId] = useState<string>('');
  const [checkoutLoading, setCheckoutLoading] = useState(false);
  const [checkoutError, setCheckoutError] = useState<string | null>(null);
  const [inputCheckoutId, setInputCheckoutId] = useState<string>(checkoutId || '');

  const loadCheckoutFiles = useCallback(async (pId: string, rId: string, cId: string) => {
    setCheckoutLoading(true);
    setCheckoutError(null);
    try {
      const view = await fetchWorkspaceEditView(pId, rId, cId);
      const invFiles = mapWorkspaceFilesToInvItems(view);
      setFiles((prev) => {
        const nonWorkspace = prev.filter((f) => f.namespace !== 'workspaces');
        return [...nonWorkspace, ...invFiles];
      });
      if (invFiles.length > 0) {
        setSelectedFile(invFiles[0]);
        setCurrentUri(invFiles[0].uri);
        setActiveNamespace('workspaces');
      }
    } catch (err: any) {
      setCheckoutError(err?.message || '체크아웃 파일 조회 실패');
    } finally {
      setCheckoutLoading(false);
    }
  }, []);

  useEffect(() => {
    if (checkoutId) {
      setInputCheckoutId(checkoutId);
    }
  }, [checkoutId]);

  useEffect(() => {
    if (projectId && runId && checkoutId) {
      loadCheckoutFiles(projectId, runId, checkoutId);
    }
  }, [projectId, runId, checkoutId, loadCheckoutFiles]);

  const handleLoadCheckout = useCallback(() => {
    const cid = inputCheckoutId.trim();
    if (!projectId?.trim() || !runId?.trim() || !cid) return;
    loadCheckoutFiles(projectId.trim(), runId.trim(), cid);
  }, [projectId, runId, inputCheckoutId, loadCheckoutFiles]);

  // ---------------------------------------------------------------------------
  // Integrity Verification State (Strict Tri-State: unverified | verified | mismatch | error)
  // ---------------------------------------------------------------------------
  const [integrityState, setIntegrityState] = useState<{
    status: 'unverified' | 'verifying' | 'verified' | 'mismatch' | 'error';
    expectedHash: string | null;
    calculatedHash: string | null;
    lastVerifiedAt: string | null;
    integrityError: string | null;
  }>({
    status: 'unverified',
    expectedHash: initialFiles[0]?.contentHash || null,
    calculatedHash: null,
    lastVerifiedAt: null,
    integrityError: null,
  });

  // ---------------------------------------------------------------------------
  // Replica Repair State
  // ---------------------------------------------------------------------------
  const [repairState, setRepairState] = useState<{
    isRepairing: boolean;
    repairMessage: string | null;
    repairError: string | null;
  }>({
    isRepairing: false,
    repairMessage: null,
    repairError: null,
  });

  const formatBytes = (bytes: number | null | undefined) => {
    if (bytes === null || bytes === undefined) return '0 B';
    if (bytes === 0) return '0 B';
    const k = 1024;
    const sizes = ['B', 'KB', 'MB', 'GB', 'TB', 'PB'];
    const i = Math.floor(Math.log(bytes) / Math.log(k));
    return parseFloat((bytes / Math.pow(k, i)).toFixed(1)) + ' ' + sizes[i];
  };

  // Filter files by current namespace / URI
  const filteredFiles = useMemo(() => {
    return files.filter((f) => {
      const fileNs = f.namespace || (f.uri?.startsWith('inv://') ? (f.uri.replace('inv://', '').split('/')[0] as InvNamespace) : undefined);
      if (activeNamespace && fileNs && fileNs !== activeNamespace) return false;
      if (currentUri && currentUri !== `inv://${activeNamespace}`) {
        return f.uri.startsWith(currentUri) || f.uri === currentUri;
      }
      return true;
    });
  }, [files, activeNamespace, currentUri]);

  // Select file handler
  const handleSelectFile = useCallback((file: InvFileItem) => {
    setSelectedFile(file);
    setCurrentUri(file.uri);
    setIntegrityState({
      status: 'unverified',
      expectedHash: file.contentHash,
      calculatedHash: null,
      lastVerifiedAt: null,
      integrityError: null,
    });
    setRepairState({
      isRepairing: false,
      repairMessage: null,
      repairError: null,
    });
  }, []);

  // Namespace navigation
  const navigateToNamespace = (ns: InvNamespace) => {
    setActiveNamespace(ns);
    const newUri = `inv://${ns}`;
    setCurrentUri(newUri);
    const matching = files.find((f) => f.namespace === ns);
    if (matching) {
      handleSelectFile(matching);
    } else {
      setSelectedFile(null);
    }
  };

  const handleAddressSubmit = (e: React.FormEvent) => {
    e.preventDefault();
    const parts = currentUri.replace('inv://', '').split('/');
    const ns = parts[0] as InvNamespace;
    if (['workspaces', 'models', 'datasets', 'artifacts'].includes(ns)) {
      setActiveNamespace(ns);
    }
    const matched = files.find((f) => f.uri === currentUri);
    if (matched) {
      handleSelectFile(matched);
    }
  };

  // ---------------------------------------------------------------------------
  // Requirement 1 & 2: Actual Hash Comparison & Strict Tri-State Verification
  // ---------------------------------------------------------------------------
  const handleVerifyIntegrity = async () => {
    if (!selectedFile) return;

    setIntegrityState((prev) => ({
      ...prev,
      status: 'verifying',
      integrityError: null,
    }));

    try {
      // Missing expected checksum is strictly UNVERIFIED, never VERIFIED
      if (!selectedFile.contentHash || selectedFile.contentHash.trim() === '') {
        setIntegrityState({
          status: 'unverified',
          expectedHash: null,
          calculatedHash: null,
          lastVerifiedAt: null,
          integrityError: '카탈로그에 등록된 SHA-256 체크섬이 없습니다. (검증 불가)',
        });
        return;
      }

      let calculated = '';
      let isMatch = false;

      if (onVerifyIntegrity) {
        const res = await onVerifyIntegrity(selectedFile);
        calculated = res.calculatedHash;
        // Strict equality comparison
        isMatch = res.matches && calculated.toLowerCase() === selectedFile.contentHash.toLowerCase();
      } else if (typeof selectedFile.content === 'string') {
        if (selectedFile.source !== 'kernel-checkout') {
          // Honest refusal: cannot verify in-memory demo or unconnected data as real storage integrity
          setIntegrityState({
            status: 'unverified',
            expectedHash: selectedFile.contentHash,
            calculatedHash: null,
            lastVerifiedAt: null,
            integrityError: '데모/미연결 데이터: 실제 저장소 바이트(WorkspaceEditView)가 연결되지 않아 무결성을 검증할 수 없습니다. (미검증 유지) 👉 [사용자 조치 필요]: 상단 커널 체크아웃 바에서 유효한 체크아웃 ID를 로드하십시오.',
          });
          return;
        }
        // Genuine client-side SHA-256 computation over actual file bytes
        calculated = await calculateSha256(selectedFile.content);
        isMatch = calculated.toLowerCase() === selectedFile.contentHash.toLowerCase();
      } else {
        // Honest refusal: cannot verify without bytes or verification adapter
        setIntegrityState({
          status: 'unverified',
          expectedHash: selectedFile.contentHash,
          calculatedHash: null,
          lastVerifiedAt: null,
          integrityError: '파일 본문 바이트(content) 또는 검증 어댑터가 부재하여 무결성을 검증할 수 없습니다. 👉 [사용자 조치 필요]: 상단 커널 체크아웃 바에서 파일을 로드하거나 프로젝트/실행을 연결하십시오.',
        });
        return;
      }

      // Requirement 1 & 2: Mismatch must NEVER be marked verified
      if (isMatch) {
        setIntegrityState({
          status: 'verified',
          expectedHash: selectedFile.contentHash,
          calculatedHash: calculated,
          lastVerifiedAt: new Date().toISOString(),
          integrityError: null,
        });
      } else {
        setIntegrityState({
          status: 'mismatch',
          expectedHash: selectedFile.contentHash,
          calculatedHash: calculated,
          lastVerifiedAt: new Date().toISOString(),
          integrityError: null,
        });
      }
    } catch (err: any) {
      // Requirement 3: Fresh failure MUST wipe out previous verified state
      setIntegrityState({
        status: 'error',
        expectedHash: selectedFile.contentHash,
        calculatedHash: null,
        lastVerifiedAt: null,
        integrityError: err?.message || '무결성 검증 통신 오류가 발생했습니다.',
      });
    }
  };

  // ---------------------------------------------------------------------------
  // Requirement 4: Surviving Nodes & Replica Repair Guard
  // ---------------------------------------------------------------------------
  const healthyReplicasCount = useMemo(() => {
    if (!selectedFile) return 0;
    return selectedFile.replicas.filter((r) => r.status === 'healthy').length;
  }, [selectedFile]);

  const isDegraded = useMemo(() => {
    if (!selectedFile) return false;
    return healthyReplicasCount < selectedFile.requiredReplicas;
  }, [selectedFile, healthyReplicasCount]);

  // Surviving nodes = online, not observationOnly, schedulable, not already hosting a healthy replica
  const survivingNodes = useMemo(() => {
    if (!selectedFile) return [];
    return (clusterNodes || []).filter(
      (n) =>
        n.status === 'online' &&
        !n.observationOnly &&
        n.schedulable !== false &&
        !selectedFile.replicas.some((r) => r.nodeId === n.id && r.status === 'healthy')
    );
  }, [clusterNodes, selectedFile]);

  const handleRepairReplicas = async () => {
    if (!selectedFile) return;

    if (survivingNodes.length === 0) {
      setRepairState({
        isRepairing: false,
        repairMessage: null,
        repairError: '생존 가용 노드가 없어 복구를 진행할 수 없습니다.',
      });
      return;
    }

    setRepairState({
      isRepairing: true,
      repairMessage: null,
      repairError: null,
    });

    try {
      const targetId = targetNodeId || survivingNodes[0]?.id;
      if (!onRepairReplicas) {
        setRepairState({
          isRepairing: false,
          repairMessage: null,
          repairError: '서버에 온디맨드 복구 실행 API가 부재하여 복구를 수행할 수 없습니다. (복구 불가 / 미수행) ℹ️ [제품 기능 미제공]: 파일 복제본 온디맨드 복구 API는 현재 백엔드 커널 사양에 구현되어 있지 않습니다. 일시적 시스템 장애가 아니므로 재시도해도 복구되지 않으며, 향후 커널 복구 기능 지원 시 제공될 예정입니다.',
        });
        return;
      }

      const repairResult = await onRepairReplicas(selectedFile.uri, targetId);

      // Case A: Repair failed on server
      if (!repairResult.success) {
        setRepairState({
          isRepairing: false,
          repairMessage: null,
          repairError: repairResult.message || '복구 작업이 서버에서 거절되었습니다.',
        });
        return;
      }

      // Update state
      const newHealthyCount = repairResult.repairedReplicas.filter((r) => r.status === 'healthy').length;
      const updatedFile = {
        ...selectedFile,
        replicas: repairResult.repairedReplicas,
      };
      setSelectedFile(updatedFile);
      setFiles((prev) => prev.map((f) => (f.uri === selectedFile.uri ? updatedFile : f)));

      // Case B: Succeeded but STILL degraded
      if (newHealthyCount < updatedFile.requiredReplicas) {
        setRepairState({
          isRepairing: false,
          repairMessage: `⚠️ 복구 부분 완료: ${newHealthyCount}/${updatedFile.requiredReplicas} 복제본 (여전히 저하 상태)`,
          repairError: null,
        });
      } else {
        // Case C: Succeeded and fully restored
        setRepairState({
          isRepairing: false,
          repairMessage: `✔ 복제본 복구 완료 (${newHealthyCount}/${updatedFile.requiredReplicas} 정상)`,
          repairError: null,
        });
      }
    } catch (err: any) {
      setRepairState({
        isRepairing: false,
        repairMessage: null,
        repairError: err?.message || '복구 요청 중 네트워크 오류가 발생했습니다.',
      });
    }
  };

  return (
    <section
      style={{
        padding: '20px 24px',
        backgroundColor: 'var(--color-bg-surface, #0f172a)',
        color: 'var(--color-text-primary, #f8fafc)',
        display: 'flex',
        flexDirection: 'column',
        gap: '16px',
        minHeight: '100%',
        overflow: 'auto',
      }}
      aria-label="내 저장소"
    >
      {/* 1. Header & Title (Preserves existing heading for regression compatibility) */}
      <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
        <div>
          <h2 style={{ fontSize: '1.25rem', fontWeight: 700, margin: 0 }}>내 저장소</h2>
          <p style={{ fontSize: '0.8125rem', color: '#94a3b8', margin: '2px 0 0 0' }}>
            내가 등록한 활성 저장소의 파일 목록입니다. 현재 접근 가능 여부는 별도 확인이 필요합니다.
          </p>
        </div>
      </div>

      {/* 2. Address Bar & Namespace Tabs */}
      <div style={{ display: 'flex', flexDirection: 'column', gap: '8px' }}>
        <form onSubmit={handleAddressSubmit} style={{ display: 'flex', gap: '8px', alignItems: 'center' }}>
          <span style={{ fontSize: '1.25rem' }}>📁</span>
          <input
            data-testid="inv-address-bar"
            type="text"
            value={currentUri}
            maxLength={2048}
            onChange={(e) => setCurrentUri(e.target.value)}
            placeholder="inv://models/..."
            style={{
              flex: 1,
              padding: '8px 12px',
              borderRadius: '6px',
              backgroundColor: '#1e293b',
              border: '1px solid #334155',
              color: '#f8fafc',
              fontSize: '0.8125rem',
              fontFamily: 'monospace',
            }}
          />
          <button
            data-testid="inv-navigate-btn"
            type="submit"
            style={{
              padding: '8px 16px',
              fontSize: '0.8125rem',
              fontWeight: 600,
              backgroundColor: '#3b82f6',
              color: '#ffffff',
              border: 'none',
              borderRadius: '6px',
              cursor: 'pointer',
            }}
          >
            이동
          </button>
        </form>

        <div style={{ display: 'flex', gap: '6px' }}>
          {(['models', 'datasets', 'workspaces', 'artifacts'] as const).map((ns) => {
            const active = activeNamespace === ns;
            return (
              <button
                key={ns}
                type="button"
                data-testid={`nav-namespace-${ns}`}
                onClick={() => navigateToNamespace(ns)}
                style={{
                  padding: '6px 12px',
                  fontSize: '0.75rem',
                  fontWeight: active ? 700 : 500,
                  borderRadius: '6px',
                  border: '1px solid',
                  borderColor: active ? '#3b82f6' : '#334155',
                  backgroundColor: active ? 'rgba(59, 130, 246, 0.2)' : 'transparent',
                  color: active ? '#93c5fd' : '#94a3b8',
                  cursor: 'pointer',
                }}
              >
                inv://{ns}
              </button>
            );
          })}
        </div>

        {activeNamespace === 'workspaces' && (
          <div
            data-testid="workspace-checkout-bar"
            style={{
              display: 'flex',
              gap: '8px',
              alignItems: 'center',
              padding: '8px 12px',
              backgroundColor: '#1e293b',
              borderRadius: '6px',
              border: '1px solid #334155',
            }}
          >
            <span style={{ fontSize: '0.75rem', color: '#94a3b8' }}>커널 체크아웃:</span>
            <input
              type="text"
              data-testid="checkout-id-input"
              value={inputCheckoutId}
              onChange={(e) => setInputCheckoutId(e.target.value)}
              placeholder="체크아웃 ID (예: 55555555-5555-4555-8555-555555555555)"
              style={{
                flex: 1,
                padding: '4px 8px',
                borderRadius: '4px',
                backgroundColor: '#0f172a',
                border: '1px solid #334155',
                color: '#f8fafc',
                fontSize: '0.75rem',
                fontFamily: 'monospace',
              }}
            />
            <button
              type="button"
              data-testid="load-checkout-btn"
              onClick={handleLoadCheckout}
              disabled={checkoutLoading || !projectId?.trim() || !runId?.trim() || !inputCheckoutId.trim()}
              aria-disabled={checkoutLoading || !projectId?.trim() || !runId?.trim() || !inputCheckoutId.trim()}
              aria-describedby={(!projectId?.trim() || !runId?.trim()) ? 'checkout-context-warning' : undefined}
              title={
                checkoutLoading
                  ? '체크아웃 파일 로딩 중입니다.'
                  : (!projectId?.trim() || !runId?.trim())
                  ? '프로젝트 및 실행(Run) 컨텍스트가 필요합니다 (사용자 조치 필요).'
                  : !inputCheckoutId.trim()
                  ? '체크아웃 ID를 입력해야 로드할 수 있습니다 (사용자 조치 필요).'
                  : '체크아웃 파일 로드'
              }
              style={{
                padding: '4px 12px',
                fontSize: '0.75rem',
                fontWeight: 600,
                borderRadius: '4px',
                backgroundColor: (!projectId?.trim() || !runId?.trim() || !inputCheckoutId.trim()) ? '#475569' : '#3b82f6',
                color: '#ffffff',
                border: 'none',
                cursor: (!projectId?.trim() || !runId?.trim() || !inputCheckoutId.trim()) ? 'not-allowed' : 'pointer',
              }}
            >
              {checkoutLoading ? '로딩 중...' : '체크아웃 파일 로드'}
            </button>
          </div>
        )}
        {activeNamespace === 'workspaces' && (!projectId?.trim() || !runId?.trim()) && (
          <div
            id="checkout-context-warning"
            role="alert"
            data-testid="checkout-context-warning"
            style={{ fontSize: '0.6875rem', color: '#fbbf24', padding: '0 4px', lineHeight: '1.4' }}
          >
            <div>⚠️ 활성 프로젝트/실행(Run) 정보가 없어 커널 체크아웃 조회가 제한됩니다 (근거 없는 호출 방지).</div>
            <div style={{ color: '#fed7aa', marginTop: '2px' }}>
              👉 <strong>[사용자 조치 필요]</strong>: 상단 메뉴에서 프로젝트 및 실행(Run)을 선택하면 커널 체크아웃 조회가 활성화됩니다.
            </div>
          </div>
        )}
      </div>

      {checkoutLoading && (
        <div data-testid="checkout-loading" style={{ padding: '6px 12px', fontSize: '0.75rem', color: '#38bdf8' }}>
          ⏳ 커널 체크아웃 파일(WorkspaceEditView) 불러오는 중...
        </div>
      )}
      {checkoutError && (
        <div role="alert" data-testid="checkout-error" style={{ padding: '6px 12px', fontSize: '0.75rem', color: '#f87171' }}>
          ⚠️ 체크아웃 파일 로드 오류: {checkoutError}
        </div>
      )}

      {/* 3. Main Split View: File List on Left, Detail & Integrity & Replicas on Right */}
      <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: '16px', flex: 1 }}>
        {/* Left: Files Explorer */}
        <div style={{ padding: '16px', backgroundColor: '#1e293b', borderRadius: '8px', border: '1px solid #334155' }}>
          <h3 style={{ fontSize: '0.875rem', fontWeight: 600, margin: '0 0 10px 0' }}>
            파일 목록 ({filteredFiles.length}개)
          </h3>

          {filteredFiles.length === 0 ? (
            <p data-testid="inv-empty-state" style={{ color: '#94a3b8', fontSize: '0.8125rem' }}>
              등록된 파일이 없습니다.
            </p>
          ) : (
            <div style={{ display: 'flex', flexDirection: 'column', gap: '6px' }}>
              {filteredFiles.map((file) => {
                const isSelected = selectedFile?.uri === file.uri;
                const healthy = file.replicas.filter((r) => r.status === 'healthy').length;
                const degraded = healthy < file.requiredReplicas;
                return (
                  <div
                    key={file.uri}
                    data-testid={`file-row-${file.uri}`}
                    onClick={() => handleSelectFile(file)}
                    onDoubleClick={() => onOpenFile?.(file)}
                    style={{
                      padding: '10px 12px',
                      backgroundColor: isSelected ? 'rgba(59, 130, 246, 0.15)' : '#0f172a',
                      borderRadius: '6px',
                      border: isSelected ? '1px solid #3b82f6' : '1px solid #334155',
                      cursor: 'pointer',
                      display: 'flex',
                      justifyContent: 'space-between',
                      alignItems: 'center',
                    }}
                  >
                    <div>
                      <div style={{ fontWeight: 600, fontSize: '0.8125rem' }}>{file.name}</div>
                      <div style={{ fontSize: '0.6875rem', color: '#64748b', fontFamily: 'monospace' }}>
                        {file.uri}
                      </div>
                    </div>
                    <div style={{ textAlign: 'right', fontSize: '0.75rem' }}>
                      <div style={{ color: '#94a3b8' }}>{formatBytes(file.sizeBytes)}</div>
                      <span
                        aria-label={`복제본 상태: ${file.requiredReplicas}개 중 ${healthy}개 가용 (${degraded ? '저하' : '정상'})`}
                        style={{
                          fontSize: '0.6875rem',
                          fontWeight: 600,
                          padding: '2px 6px',
                          borderRadius: '4px',
                          backgroundColor: degraded ? 'rgba(239, 68, 68, 0.2)' : 'rgba(16, 185, 129, 0.2)',
                          color: degraded ? '#f87171' : '#34d399',
                        }}
                      >
                        {healthy}/{file.requiredReplicas} 복제본 ({degraded ? '저하' : '정상'})
                      </span>
                    </div>
                  </div>
                );
              })}
            </div>
          )}
        </div>

        {/* Right: File Detail, Integrity Verification & Replicas */}
        {selectedFile && (
          <div
            data-testid="file-detail-pane"
            style={{ display: 'flex', flexDirection: 'column', gap: '14px' }}
          >
            {/* File Metadata Card */}
            <div style={{ padding: '16px', backgroundColor: '#1e293b', borderRadius: '8px', border: '1px solid #334155' }}>
              <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'flex-start' }}>
                <h3 style={{ fontSize: '0.9375rem', fontWeight: 600, margin: 0 }}>{selectedFile.name}</h3>
                <span
                  style={{
                    fontSize: '0.6875rem',
                    fontWeight: 600,
                    padding: '2px 6px',
                    borderRadius: '4px',
                    backgroundColor: 'rgba(59, 130, 246, 0.2)',
                    color: '#60a5fa',
                  }}
                >
                  v{selectedFile.version} · {selectedFile.classification}
                </span>
              </div>
              <p style={{ fontSize: '0.75rem', color: '#94a3b8', margin: '4px 0 0 0', fontFamily: 'monospace' }}>
                {selectedFile.uri}
              </p>
              <div style={{ fontSize: '0.75rem', color: '#94a3b8', marginTop: '6px' }}>
                크기: <strong>{formatBytes(selectedFile.sizeBytes)}</strong> · 유형: {selectedFile.contentType} ·{' '}
                {selectedFile.isPinned ? '📌 고정(Pinned - GC 면제)' : '임시 저장'}
              </div>
            </div>

            {/* Integrity Verification Card (Requirement 1 & 2) */}
            <div
              data-testid="integrity-verification-section"
              style={{ padding: '16px', backgroundColor: '#1e293b', borderRadius: '8px', border: '1px solid #334155' }}
            >
              <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: '10px' }}>
                <h4 style={{ fontSize: '0.8125rem', fontWeight: 600, margin: 0 }}>
                  🔒 클라이언트 측 SHA-256 무결성 검증
                </h4>
                {/* Tri-State Badge */}
                <span
                  data-testid="integrity-badge"
                  role={
                    integrityState.status === 'mismatch' || integrityState.status === 'error'
                      ? 'alert'
                      : 'status'
                  }
                  aria-live={
                    integrityState.status === 'mismatch' || integrityState.status === 'error'
                      ? 'assertive'
                      : 'polite'
                  }
                  style={{
                    fontSize: '0.75rem',
                    fontWeight: 700,
                    padding: '3px 8px',
                    borderRadius: '4px',
                    backgroundColor:
                      integrityState.status === 'verified'
                        ? 'rgba(16, 185, 129, 0.2)'
                        : integrityState.status === 'mismatch' || integrityState.status === 'error'
                        ? 'rgba(239, 68, 68, 0.2)'
                        : 'rgba(234, 179, 8, 0.2)',
                    color:
                      integrityState.status === 'verified'
                        ? '#34d399'
                        : integrityState.status === 'mismatch' || integrityState.status === 'error'
                        ? '#f87171'
                        : '#fbbf24',
                    border: '1px solid',
                    borderColor:
                      integrityState.status === 'verified'
                        ? 'rgba(16, 185, 129, 0.4)'
                        : integrityState.status === 'mismatch' || integrityState.status === 'error'
                        ? 'rgba(239, 68, 68, 0.4)'
                        : 'rgba(234, 179, 8, 0.4)',
                  }}
                >
                  <span data-testid={`integrity-status-${integrityState.status}`} style={{ display: 'none' }} />
                  {integrityState.status === 'verified' && '검증 통과 (VERIFIED)'}
                  {integrityState.status === 'unverified' && '미검증 (UNVERIFIED)'}
                  {integrityState.status === 'verifying' && '계산 중... (VERIFYING)'}
                  {integrityState.status === 'mismatch' && '검증 실패 (해시 불일치 / TAMPERED)'}
                  {integrityState.status === 'error' && '검증 오류 (ERROR)'}
                </span>
              </div>

              <div style={{ fontSize: '0.75rem', color: '#94a3b8', display: 'flex', flexDirection: 'column', gap: '4px' }}>
                <div>
                  파일 출처:{' '}
                  <span
                    data-testid="file-source-badge"
                    style={{
                      color: selectedFile.source === 'kernel-checkout' ? '#34d399' : '#fbbf24',
                      fontWeight: 600,
                    }}
                  >
                    {selectedFile.source === 'kernel-checkout'
                      ? '커널 체크아웃 (WorkspaceEditView 실 바이트)'
                      : '로컬/데모 (실제 저장소 미연결 · 무결성 검증 유보)'}
                  </span>
                </div>
                <div>
                  카탈로그 기대 해시: <code data-testid="expected-hash" style={{ color: '#38bdf8' }}>{selectedFile.contentHash || '미등록'}</code>
                </div>
                <div>
                  클라이언트 계산 해시:{' '}
                  <code data-testid="calculated-hash" style={{ color: integrityState.status === 'verified' ? '#34d399' : '#f87171' }}>
                    {integrityState.calculatedHash || '미계산'}
                  </code>
                </div>
              </div>

              {/* Requirement 1: Mismatch Banner */}
              {integrityState.status === 'mismatch' && (
                <div
                  role="alert"
                  data-testid="integrity-mismatch-banner"
                  style={{
                    marginTop: '10px',
                    padding: '8px 12px',
                    borderRadius: '6px',
                    backgroundColor: 'rgba(239, 68, 68, 0.2)',
                    border: '1px solid #ef4444',
                    color: '#fca5a5',
                    fontSize: '0.75rem',
                  }}
                >
                  ⚠️ 무결성 검증 실패: 계산된 해시가 카탈로그 체크섬과 불일치합니다 (변조 감지)
                </div>
              )}

              {/* Requirement 3: Error Banner */}
              {integrityState.integrityError && (
                <div
                  role="alert"
                  data-testid="integrity-action-error"
                  style={{
                    marginTop: '10px',
                    padding: '8px 12px',
                    borderRadius: '6px',
                    backgroundColor: 'rgba(239, 68, 68, 0.2)',
                    border: '1px solid #ef4444',
                    color: '#fca5a5',
                    fontSize: '0.75rem',
                  }}
                >
                  ❌ 무결성 검증 오류: {integrityState.integrityError}
                </div>
              )}

              <button
                type="button"
                data-testid="verify-integrity-btn"
                onClick={handleVerifyIntegrity}
                disabled={integrityState.status === 'verifying'}
                aria-disabled={integrityState.status === 'verifying'}
                title={integrityState.status === 'verifying' ? '무결성 해시 계산 진행 중입니다.' : 'SHA-256 무결성 검증 실행'}
                style={{
                  marginTop: '10px',
                  padding: '6px 14px',
                  fontSize: '0.75rem',
                  fontWeight: 600,
                  borderRadius: '6px',
                  backgroundColor: '#3b82f6',
                  color: '#ffffff',
                  border: 'none',
                  cursor: 'pointer',
                }}
              >
                🔍 SHA-256 무결성 검증 실행
              </button>
            </div>

            {/* Replicas & Repair Card (Requirement 4) */}
            <div
              data-testid="replica-pane"
              style={{ padding: '16px', backgroundColor: '#1e293b', borderRadius: '8px', border: '1px solid #334155' }}
            >
              <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: '10px' }}>
                <h4 style={{ fontSize: '0.8125rem', fontWeight: 600, margin: 0 }}>
                  🌐 분산 복제본 상태 (Replicas)
                </h4>
                {isDegraded ? (
                  <div
                    role="alert"
                    data-testid="replica-degradation-badge"
                    style={{
                      fontSize: '0.6875rem',
                      fontWeight: 700,
                      padding: '2px 8px',
                      borderRadius: '4px',
                      backgroundColor: 'rgba(239, 68, 68, 0.2)',
                      color: '#f87171',
                      border: '1px solid rgba(239, 68, 68, 0.4)',
                    }}
                  >
                    ⚠️ {healthyReplicasCount}/{selectedFile.requiredReplicas} Replicas Available (Degraded)
                  </div>
                ) : (
                  <div
                    data-testid="replica-healthy-badge"
                    style={{
                      fontSize: '0.6875rem',
                      fontWeight: 700,
                      padding: '2px 8px',
                      borderRadius: '4px',
                      backgroundColor: 'rgba(16, 185, 129, 0.2)',
                      color: '#34d399',
                      border: '1px solid rgba(16, 185, 129, 0.4)',
                    }}
                  >
                    ✔ {healthyReplicasCount}/{selectedFile.requiredReplicas} Replicas Healthy
                  </div>
                )}
              </div>

              {/* Replicas List */}
              <div style={{ display: 'flex', flexDirection: 'column', gap: '6px', marginBottom: '12px' }}>
                {selectedFile.replicas.map((rep) => (
                  <div
                    key={rep.nodeId}
                    data-testid={`replica-item-${rep.nodeId}`}
                    style={{
                      padding: '8px 10px',
                      backgroundColor: '#0f172a',
                      borderRadius: '4px',
                      border: '1px solid #334155',
                      display: 'flex',
                      justifyContent: 'space-between',
                      alignItems: 'center',
                      fontSize: '0.75rem',
                    }}
                  >
                    <div>
                      <strong>{rep.nodeHostname}</strong> ({rep.nodeId})
                      <div style={{ color: '#64748b', fontSize: '0.6875rem' }}>{rep.localPath}</div>
                    </div>
                    <span
                      style={{
                        padding: '2px 6px',
                        borderRadius: '4px',
                        fontSize: '0.6875rem',
                        fontWeight: 600,
                        backgroundColor: rep.status === 'healthy' ? 'rgba(16, 185, 129, 0.15)' : 'rgba(239, 68, 68, 0.15)',
                        color: rep.status === 'healthy' ? '#34d399' : '#f87171',
                      }}
                    >
                      {rep.status.toUpperCase()}
                    </span>
                  </div>
                ))}
              </div>

              {/* Repair Controls & Warnings */}
              {repairState.repairError && (
                <div
                  role="alert"
                  data-testid="repair-action-error"
                  style={{
                    padding: '8px 12px',
                    borderRadius: '6px',
                    backgroundColor: 'rgba(239, 68, 68, 0.2)',
                    border: '1px solid #ef4444',
                    color: '#fca5a5',
                    fontSize: '0.75rem',
                    marginBottom: '8px',
                  }}
                >
                  ❌ 복구 실패: {repairState.repairError}
                </div>
              )}

              {repairState.repairMessage && (
                <div
                  role={repairState.repairMessage.startsWith('⚠️') ? 'alert' : 'status'}
                  aria-live={repairState.repairMessage.startsWith('⚠️') ? 'assertive' : 'polite'}
                  data-testid={
                    repairState.repairMessage.startsWith('⚠️') ? 'repair-action-warning' : 'repair-action-success'
                  }
                  style={{
                    padding: '8px 12px',
                    borderRadius: '6px',
                    backgroundColor: repairState.repairMessage.startsWith('⚠️')
                      ? 'rgba(234, 179, 8, 0.2)'
                      : 'rgba(16, 185, 129, 0.2)',
                    border: repairState.repairMessage.startsWith('⚠️') ? '1px solid #eab308' : '1px solid #10b981',
                    color: repairState.repairMessage.startsWith('⚠️') ? '#fde047' : '#34d399',
                    fontSize: '0.75rem',
                    marginBottom: '8px',
                  }}
                >
                  {repairState.repairMessage}
                </div>
              )}

              {survivingNodes.length === 0 ? (
                <div
                  id="no-surviving-nodes-notice"
                  role="alert"
                  data-testid="no-surviving-nodes-notice"
                  style={{
                    padding: '8px 12px',
                    borderRadius: '6px',
                    backgroundColor: 'rgba(239, 68, 68, 0.15)',
                    border: '1px solid rgba(239, 68, 68, 0.3)',
                    color: '#f87171',
                    fontSize: '0.75rem',
                    lineHeight: '1.4',
                  }}
                >
                  <div>⚠️ 생존 노드 없음 (복구 불가 - 복제본을 수용할 가용 노드가 없습니다)</div>
                  <div style={{ marginTop: '4px', fontSize: '0.6875rem', color: '#fca5a5' }}>
                    🛠️ <strong>[운영자 조치 필요]</strong>: 복제본을 배치할 수 있는 정상 스케줄링 가능 노드가 없습니다. 인프라 운영자에게 추가 노드 투입 또는 오프라인 노드 복구를 요청하십시오.
                  </div>
                </div>
              ) : (
                <div style={{ display: 'flex', gap: '8px', alignItems: 'center' }}>
                  <select
                    data-testid="repair-target-node-select"
                    value={targetNodeId || survivingNodes[0]?.id}
                    onChange={(e) => setTargetNodeId(e.target.value)}
                    disabled={repairState.isRepairing}
                    style={{
                      padding: '6px',
                      borderRadius: '4px',
                      backgroundColor: '#0f172a',
                      border: '1px solid #334155',
                      color: '#f8fafc',
                      fontSize: '0.75rem',
                    }}
                  >
                    {survivingNodes.map((n) => (
                      <option key={n.id} value={n.id}>
                        {n.hostname} ({n.id})
                      </option>
                    ))}
                  </select>
                  <button
                    type="button"
                    data-testid="repair-replicas-btn"
                    onClick={handleRepairReplicas}
                    disabled={!isDegraded || repairState.isRepairing}
                    style={{
                      padding: '6px 14px',
                      fontSize: '0.75rem',
                      fontWeight: 600,
                      borderRadius: '6px',
                      backgroundColor: isDegraded ? '#10b981' : '#334155',
                      color: '#ffffff',
                      border: 'none',
                      cursor: isDegraded ? 'pointer' : 'not-allowed',
                    }}
                  >
                    {repairState.isRepairing ? '복구 진행 중...' : '원클릭 복제본 복구'}
                  </button>
                </div>
              )}
            </div>
          </div>
        )}
      </div>
    </section>
  );
};
