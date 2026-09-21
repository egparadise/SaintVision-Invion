import React, { useState } from 'react';
import { Button } from '@/shared/ui/Button';

export interface WorkspaceCreateModalProps {
  projectId: string;
  isOpen: boolean;
  onClose: () => void;
  onCreate: (workspace: { name: string }) => Promise<void>;
}

export const WorkspaceCreateModal: React.FC<WorkspaceCreateModalProps> = ({
  projectId,
  isOpen,
  onClose,
  onCreate,
}) => {
  const [name, setName] = useState('');
  const [error, setError] = useState<string | null>(null);
  const [isSubmitting, setIsSubmitting] = useState(false);

  if (!isOpen) return null;

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    setError(null);

    const trimmedName = name.trim();
    if (trimmedName.length < 2) {
      setError('작업공간 명칭은 최소 2자 이상이어야 합니다 (백엔드 스키마 제약: 2–128자).');
      return;
    }
    if (trimmedName.length > 128) {
      setError('작업공간 명칭은 최대 128자 이하여야 합니다.');
      return;
    }

    setIsSubmitting(true);
    try {
      await onCreate({
        name: trimmedName,
      });
      setName('');
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
        <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: '16px' }}>
          <div>
            <h3 style={{ fontSize: '1.25rem', fontWeight: 600 }}>작업공간 생성 (Workspace Provisioning)</h3>
            <p style={{ fontSize: '0.8125rem', color: 'var(--color-text-muted)', marginTop: '2px' }}>
              프로젝트: <code>{projectId}</code> · 백엔드 초기 레코드 등록
            </p>
          </div>
          <button
            onClick={onClose}
            aria-label="닫기"
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

        {/* 정직한 단계 안내 배너: 생성은 provisioning 레코드 등록이며, 노드/자원/체크아웃은 별도 커널 prepare 단계임 */}
        <div
          role="status"
          data-testid="workspace-create-phase-notice"
          style={{
            padding: '12px 14px',
            backgroundColor: 'var(--color-bg-subtle)',
            border: '1px solid var(--color-border-subtle)',
            borderRadius: 'var(--radius-md)',
            fontSize: '0.8125rem',
            lineHeight: '1.5',
            color: 'var(--color-text-secondary)',
            marginBottom: '16px',
          }}
        >
          <div style={{ fontWeight: 600, color: 'var(--color-text-primary)', marginBottom: '4px' }}>
            📌 생성 단계 안내 (Phase Notice)
          </div>
          <div>
            작업공간 생성(POST /v1/projects/.../workspaces)은 <strong>프로비저닝(provisioning)</strong> 초기 레코드만 등록합니다.
          </div>
          <div style={{ marginTop: '4px', fontSize: '0.75rem', color: 'var(--color-text-muted)' }}>
            * 물리 노드 배치, CPU/RAM 자원 할당, 실행 도구 바인딩 및 파일 체크아웃은 생성 스키마에 포함되지 않으며, 생성 완료 후 <strong>실행(Run) 준비(prepare) 커널 단계</strong>에서 수행됩니다.
          </div>
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
            <label
              htmlFor="wsp-name-input"
              style={{ display: 'block', fontSize: '0.875rem', fontWeight: 600, marginBottom: '6px' }}
            >
              Workspace 명칭 (필수)
            </label>
            <input
              id="wsp-name-input"
              data-testid="workspace-name-input"
              type="text"
              value={name}
              onChange={(e) => setName(e.target.value)}
              placeholder="예: wsp-pacs-core-sandbox"
              minLength={2}
              maxLength={128}
              required
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
              * 2–128자의 고유한 작업공간 식별 명칭을 입력하십시오.
            </span>
          </div>

          <div style={{ display: 'flex', justifyContent: 'flex-end', gap: '10px', marginTop: '8px' }}>
            <Button variant="secondary" size="md" type="button" onClick={onClose} disabled={isSubmitting}>
              취소
            </Button>
            <Button variant="primary" size="md" type="submit" disabled={isSubmitting} data-testid="workspace-submit-btn">
              {isSubmitting ? '생성 중...' : 'Workspace 생성 (Provisioning)'}
            </Button>
          </div>
        </form>
      </div>
    </div>
  );
};

