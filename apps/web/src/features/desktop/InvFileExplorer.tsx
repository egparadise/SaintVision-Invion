import React, { useState, useMemo, useCallback } from 'react';
import { InvFileItem, InvReplicaLocation, InvNamespace } from '@/contracts/virtualFabric';
import { NodeItem } from '@/contracts/types';

export interface InvFileExplorerProps {
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
      if (activeNamespace && f.namespace !== activeNamespace) return false;
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
      } else if (selectedFile.content) {
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
          integrityError: '파일 본문 바이트(content) 또는 검증 어댑터가 부재하여 무결성을 검증할 수 없습니다.',
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
          repairError: '서버 복구 어댑터(onRepairReplicas)가 연결되지 않아 복구를 수행할 수 없습니다.',
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
      </div>

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
                        style={{
                          fontSize: '0.6875rem',
                          fontWeight: 600,
                          padding: '2px 6px',
                          borderRadius: '4px',
                          backgroundColor: degraded ? 'rgba(239, 68, 68, 0.2)' : 'rgba(16, 185, 129, 0.2)',
                          color: degraded ? '#f87171' : '#34d399',
                        }}
                      >
                        {healthy}/{file.requiredReplicas} 복제본
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
                  {integrityState.status === 'verified' && '검증 통과 (VERIFIED)'}
                  {integrityState.status === 'unverified' && '미검증 (UNVERIFIED)'}
                  {integrityState.status === 'verifying' && '계산 중... (VERIFYING)'}
                  {integrityState.status === 'mismatch' && '검증 실패 (해시 불일치 / TAMPERED)'}
                  {integrityState.status === 'error' && '검증 오류 (ERROR)'}
                </span>
              </div>

              <div style={{ fontSize: '0.75rem', color: '#94a3b8', display: 'flex', flexDirection: 'column', gap: '4px' }}>
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
                  role={repairState.repairMessage.startsWith('⚠️') ? 'alert' : undefined}
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
                  role="alert"
                  data-testid="no-surviving-nodes-notice"
                  style={{
                    padding: '8px 12px',
                    borderRadius: '6px',
                    backgroundColor: 'rgba(239, 68, 68, 0.15)',
                    border: '1px solid rgba(239, 68, 68, 0.3)',
                    color: '#f87171',
                    fontSize: '0.75rem',
                  }}
                >
                  ⚠️ 생존 노드 없음 (복구 불가 - 복제본을 수용할 가용 노드가 없습니다)
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
