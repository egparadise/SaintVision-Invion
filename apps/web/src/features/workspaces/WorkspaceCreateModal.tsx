import React, { useState } from 'react';
import { NodeItem, WorkspaceItem } from '@/contracts/types';
import { Button } from '@/shared/ui/Button';

export interface WorkspaceCreateModalProps {
  projectId: string;
  availableNodes: NodeItem[];
  isOpen: boolean;
  onClose: () => void;
  onCreate: (workspace: Omit<WorkspaceItem, 'id' | 'createdAt'>) => Promise<void>;
}

export const WorkspaceCreateModal: React.FC<WorkspaceCreateModalProps> = ({
  projectId,
  availableNodes,
  isOpen,
  onClose,
  onCreate,
}) => {
  const [name, setName] = useState('');
  const [targetNodeId, setTargetNodeId] = useState(availableNodes[0]?.id || '');
  const [isolationMode, setIsolationMode] = useState<'process_sandbox' | 'container_isolated'>('process_sandbox');
  const [allowedPaths, setAllowedPaths] = useState('./workspace, ./data');
  const [cpuLimit, setCpuLimit] = useState(4);
  const [ramLimitGb, setRamLimitGb] = useState(8);
  const [error, setError] = useState<string | null>(null);
  const [isSubmitting, setIsSubmitting] = useState(false);

  if (!isOpen) return null;

  const validatePaths = (pathsStr: string): string | null => {
    const paths = pathsStr.split(',').map((p) => p.trim());
    for (const p of paths) {
      if (p.includes('..')) {
        return '상위 디렉터리 탐색(Path Traversal "..")은 보안 정책(ADR-005)에 의해 엄격히 금지됩니다.';
      }
      if (p === '/' || p === '\\' || /^[a-zA-Z]:\\?$/.test(p)) {
        return '루트 파일시스템 전체 경로는 작업공간으로 지정할 수 없습니다.';
      }
    }
    return null;
  };

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    setError(null);

    if (!name.trim()) {
      setError('작업공간 이름을 입력하십시오.');
      return;
    }

    const pathError = validatePaths(allowedPaths);
    if (pathError) {
      setError(pathError);
      return;
    }

    const selectedNode = availableNodes.find((n) => n.id === targetNodeId);
    if (selectedNode && cpuLimit > selectedNode.cpuCores) {
      setError(`요청 CPU 코어(${cpuLimit})가 대상 노드 가용 코어(${selectedNode.cpuCores})를 초과합니다.`);
      return;
    }

    setIsSubmitting(true);
    try {
      await onCreate({
        projectId,
        name: name.trim(),
        targetNodeId,
        isolationMode,
        allowedPaths: allowedPaths.split(',').map((p) => p.trim()),
        prohibitedPaths: ['/etc', 'C:\\Windows', '..', '/var/run', 'C:\\Program Files'],
        cpuLimitCores: cpuLimit,
        memoryLimitBytes: ramLimitGb * 1024 ** 3,
        status: 'active',
      });
      onClose();
    } catch (err: any) {
      setError(err.message || '작업공간 생성에 실패했습니다.');
    } finally {
      setIsSubmitting(false);
    }
  };

  return (
    <div
      role="dialog"
      aria-modal="true"
      style={{
        position: 'fixed',
        inset: 0,
        backgroundColor: 'rgba(0, 0, 0, 0.65)',
        display: 'flex',
        alignItems: 'center',
        justifyContent: 'center',
        zIndex: 1000,
        padding: '16px',
      }}
    >
      <div
        style={{
          backgroundColor: 'var(--color-bg-surface)',
          borderRadius: 'var(--radius-lg)',
          border: '1px solid var(--color-border-subtle)',
          width: '100%',
          maxWidth: '560px',
          padding: '24px',
          boxShadow: 'var(--shadow-md)',
        }}
      >
        <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: '20px' }}>
          <div>
            <h3 style={{ fontSize: '1.25rem', fontWeight: 600 }}>격리 Workspace 생성 (S03-FE)</h3>
            <p style={{ fontSize: '0.8125rem', color: 'var(--color-text-muted)', marginTop: '2px' }}>
              프로젝트: <code>{projectId}</code> · 물리 노드 샌드박스 할당
            </p>
          </div>
          <button
            onClick={onClose}
            style={{
              background: 'none',
              border: 'none',
              fontSize: '1.25rem',
              color: 'var(--color-text-muted)',
              cursor: 'pointer',
            }}
          >
            ✕
          </button>
        </div>

        {error && (
          <div
            role="alert"
            style={{
              padding: '10px 14px',
              backgroundColor: 'var(--color-risk-l3-bg)',
              color: 'var(--color-risk-l3-text)',
              border: '1px solid var(--color-risk-l3-border)',
              borderRadius: 'var(--radius-md)',
              fontSize: '0.8125rem',
              marginBottom: '16px',
            }}
          >
            ⚠️ {error}
          </div>
        )}

        <form onSubmit={handleSubmit} style={{ display: 'flex', flexDirection: 'column', gap: '16px' }}>
          <div>
            <label style={{ display: 'block', fontSize: '0.875rem', fontWeight: 600, marginBottom: '6px' }}>
              Workspace 명칭
            </label>
            <input
              type="text"
              value={name}
              onChange={(e) => setName(e.target.value)}
              placeholder="예: wsp-pacs-core-sandbox"
              style={{
                width: '100%',
                padding: '8px 12px',
                borderRadius: 'var(--radius-md)',
                border: '1px solid var(--color-border-strong)',
                backgroundColor: 'var(--color-bg-subtle)',
                color: 'var(--color-text-primary)',
                fontSize: '0.875rem',
              }}
            />
          </div>

          <div>
            <label style={{ display: 'block', fontSize: '0.875rem', fontWeight: 600, marginBottom: '6px' }}>
              대상 물리 노드 선택 (Windows 3대 / Linux 2대)
            </label>
            <select
              value={targetNodeId}
              onChange={(e) => setTargetNodeId(e.target.value)}
              style={{
                width: '100%',
                padding: '8px 12px',
                borderRadius: 'var(--radius-md)',
                border: '1px solid var(--color-border-strong)',
                backgroundColor: 'var(--color-bg-subtle)',
                color: 'var(--color-text-primary)',
                fontSize: '0.875rem',
              }}
            >
              {availableNodes.map((n) => (
                <option key={n.id} value={n.id}>
                  {n.hostname} ({n.os.toUpperCase()}, {n.cpuCores} Cores, {(n.memoryTotalBytes / 1024 ** 3).toFixed(0)} GB
                  {n.gpuCount > 0 ? `, ${n.gpuName}` : ''})
                </option>
              ))}
            </select>
          </div>

          <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: '12px' }}>
            <div>
              <label style={{ display: 'block', fontSize: '0.875rem', fontWeight: 600, marginBottom: '6px' }}>
                격리 모드 (Isolation)
              </label>
              <select
                value={isolationMode}
                onChange={(e) => setIsolationMode(e.target.value as any)}
                style={{
                  width: '100%',
                  padding: '8px 12px',
                  borderRadius: 'var(--radius-md)',
                  border: '1px solid var(--color-border-strong)',
                  backgroundColor: 'var(--color-bg-subtle)',
                  color: 'var(--color-text-primary)',
                  fontSize: '0.875rem',
                }}
              >
                <option value="process_sandbox">프로세스 샌드박스 (기본)</option>
                <option value="container_isolated">컨테이너 완전 격리</option>
              </select>
            </div>

            <div>
              <label style={{ display: 'block', fontSize: '0.875rem', fontWeight: 600, marginBottom: '6px' }}>
                CPU / RAM 할당 한도
              </label>
              <div style={{ display: 'flex', gap: '8px' }}>
                <input
                  type="number"
                  min={1}
                  max={32}
                  value={cpuLimit}
                  onChange={(e) => setCpuLimit(Number(e.target.value))}
                  title="CPU 코어 수"
                  style={{
                    width: '50%',
                    padding: '8px 8px',
                    borderRadius: 'var(--radius-md)',
                    border: '1px solid var(--color-border-strong)',
                    backgroundColor: 'var(--color-bg-subtle)',
                    color: 'var(--color-text-primary)',
                    fontSize: '0.875rem',
                  }}
                />
                <input
                  type="number"
                  min={1}
                  max={128}
                  value={ramLimitGb}
                  onChange={(e) => setRamLimitGb(Number(e.target.value))}
                  title="RAM GiB"
                  style={{
                    width: '50%',
                    padding: '8px 8px',
                    borderRadius: 'var(--radius-md)',
                    border: '1px solid var(--color-border-strong)',
                    backgroundColor: 'var(--color-bg-subtle)',
                    color: 'var(--color-text-primary)',
                    fontSize: '0.875rem',
                  }}
                />
              </div>
            </div>
          </div>

          <div>
            <label style={{ display: 'block', fontSize: '0.875rem', fontWeight: 600, marginBottom: '6px' }}>
              허용 작업 경로 (Allowed Paths, 쉼표 구분)
            </label>
            <input
              type="text"
              value={allowedPaths}
              onChange={(e) => setAllowedPaths(e.target.value)}
              placeholder="./src, ./data, ./output"
              style={{
                width: '100%',
                padding: '8px 12px',
                borderRadius: 'var(--radius-md)',
                border: '1px solid var(--color-border-strong)',
                backgroundColor: 'var(--color-bg-subtle)',
                color: 'var(--color-text-primary)',
                fontSize: '0.875rem',
              }}
            />
            <span style={{ fontSize: '0.75rem', color: 'var(--color-text-muted)', marginTop: '4px', display: 'block' }}>
              * 금지 경로: 시스템 디렉터리(`C:\Windows`, `/etc`), 상위 탐색(`..`)은 자동 차단됩니다.
            </span>
          </div>

          <div style={{ display: 'flex', justifyContent: 'flex-end', gap: '10px', marginTop: '12px' }}>
            <Button variant="secondary" size="md" type="button" onClick={onClose} disabled={isSubmitting}>
              취소
            </Button>
            <Button variant="primary" size="md" type="submit" disabled={isSubmitting}>
              {isSubmitting ? '생성 중...' : 'Workspace 생성'}
            </Button>
          </div>
        </form>
      </div>
    </div>
  );
};
