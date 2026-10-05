import React, { useState } from 'react';
import { Button } from '@/shared/ui/Button';
import { useModalA11y } from '@/shared/ui/useModalA11y';
import { GitCommitRecord } from '@/contracts/types';
import { createGitCommit } from './diffEngine';

export type UiGitFileStatus = 'modified' | 'clean';

export interface GitFileStatusConfigItem {
  colorVar: string;
  badgeColorVar: string;
  badgeText: string;
}

export const GIT_FILE_STATUS_CONFIG: Record<UiGitFileStatus, GitFileStatusConfigItem> = {
  modified: {
    colorVar: 'var(--color-status-degraded)',
    badgeColorVar: 'var(--color-status-degraded)',
    badgeText: 'modified',
  },
  clean: {
    colorVar: 'var(--color-text-secondary)',
    badgeColorVar: 'var(--color-text-muted)',
    badgeText: 'clean',
  },
} as const satisfies Record<UiGitFileStatus, GitFileStatusConfigItem>;

export function getGitFileStatusConfig(status: string): GitFileStatusConfigItem {
  if (Object.hasOwn(GIT_FILE_STATUS_CONFIG, status)) {
    return GIT_FILE_STATUS_CONFIG[status as UiGitFileStatus];
  }
  return {
    colorVar: 'var(--color-status-unknown)',
    badgeColorVar: 'var(--color-status-unknown)',
    badgeText: `UNKNOWN (${status})`,
  };
}

export type UiGitStageState = 'staged' | 'unstaged';

export interface GitStageStateConfigItem {
  bgVar: string;
  label: string;
}

export const GIT_STAGE_STATE_CONFIG: Record<UiGitStageState, GitStageStateConfigItem> = {
  staged: {
    bgVar: 'var(--color-brand-subtle)',
    label: 'Staged',
  },
  unstaged: {
    bgVar: 'transparent',
    label: 'Unstaged',
  },
} as const satisfies Record<UiGitStageState, GitStageStateConfigItem>;

export function getGitStageStateConfig(state: string): GitStageStateConfigItem {
  if (Object.hasOwn(GIT_STAGE_STATE_CONFIG, state)) {
    return GIT_STAGE_STATE_CONFIG[state as UiGitStageState];
  }
  return {
    bgVar: 'transparent',
    label: `UNKNOWN (${state})`,
  };
}

interface GitCommitModalProps {
  files: Array<{ path: string; content: string; isDirty?: boolean }>;
  parentCommit: GitCommitRecord | null;
  onCommit: (commit: GitCommitRecord) => void;
  onCancel: () => void;
}

export const GitCommitModal: React.FC<GitCommitModalProps> = ({
  files,
  parentCommit,
  onCommit,
  onCancel,
}) => {
  const [stagedFiles, setStagedFiles] = useState<string[]>(
    files.filter((f) => f.isDirty).map((f) => f.path)
  );
  const [commitMessage, setCommitMessage] = useState('');
  const [author, setAuthor] = useState('Gemini Developer <gemini@saintvision.internal>');

  const { containerRef, handleKeyDown } = useModalA11y({
    isOpen: true,
    onClose: onCancel,
  });

  const toggleStage = (path: string) => {
    setStagedFiles((prev) =>
      prev.includes(path) ? prev.filter((p) => p !== path) : [...prev, path]
    );
  };

  const handleStageAll = () => {
    setStagedFiles(files.map((f) => f.path));
  };

  const handleUnstageAll = () => {
    setStagedFiles([]);
  };

  const handleSubmit = (e: React.FormEvent) => {
    e.preventDefault();
    if (!commitMessage.trim() || stagedFiles.length === 0) return;

    const fileMap: Record<string, string> = {};
    files.forEach((f) => {
      fileMap[f.path] = f.content;
    });

    const newCommit = createGitCommit({
      author,
      message: commitMessage.trim(),
      parentCommitId: parentCommit?.commitId || null,
      stagedFiles,
      fileContents: fileMap,
    });

    onCommit(newCommit);
  };

  return (
    <div
      ref={containerRef}
      role="dialog"
      aria-modal="true"
      aria-labelledby="git-commit-modal-title"
      data-testid="git-commit-backdrop"
      onKeyDown={handleKeyDown}
      tabIndex={-1}
      style={{
        position: 'fixed',
        inset: 0,
        backgroundColor: 'var(--color-bg-backdrop)',
        display: 'flex',
        alignItems: 'center',
        justifyContent: 'center',
        zIndex: 1000,
        padding: '20px',
      }}
    >
      <div
        data-testid="git-commit-dialog"
        style={{
          width: '100%',
          maxWidth: '650px',
          backgroundColor: 'var(--color-bg-surface)',
          border: '1px solid var(--color-border-subtle)',
          borderRadius: 'var(--radius-lg, 8px)',
          display: 'flex',
          flexDirection: 'column',
          boxShadow: 'var(--shadow-lg)',
          overflow: 'hidden',
        }}
      >
        {/* Header */}
        <div
          data-testid="git-commit-header"
          style={{
            padding: '16px 20px',
            borderBottom: '1px solid var(--color-border-subtle)',
            display: 'flex',
            justifyContent: 'space-between',
            alignItems: 'center',
          }}
        >
          <div>
            <h3 id="git-commit-modal-title" style={{ margin: 0, fontSize: '16px', color: 'var(--color-text-primary)' }}>
              Git Source Commit (AC-06)
            </h3>
            <p data-testid="git-commit-parent-info" style={{ margin: '4px 0 0 0', fontSize: '12px', color: 'var(--color-text-muted)' }}>
              Parent: {parentCommit ? parentCommit.commitId.slice(0, 8) : 'ROOT (initial)'} • Staged: {stagedFiles.length}/{files.length}
            </p>
          </div>
          <Button size="sm" variant="secondary" onClick={onCancel}>
            Cancel
          </Button>
        </div>

        {/* Form Body */}
        <form onSubmit={handleSubmit} style={{ padding: '20px', display: 'flex', flexDirection: 'column', gap: '16px' }}>
          {/* Author */}
          <div>
            <label style={{ display: 'block', fontSize: '12px', fontWeight: 600, color: 'var(--color-text-muted)', marginBottom: '6px' }}>
              Author
            </label>
            <input
              type="text"
              data-testid="commit-author-input"
              value={author}
              onChange={(e) => setAuthor(e.target.value)}
              style={{
                width: '100%',
                padding: '8px 12px',
                backgroundColor: 'var(--color-bg-canvas)',
                border: '1px solid var(--color-border-subtle)',
                borderRadius: '6px',
                color: 'var(--color-text-primary)',
                fontSize: '13px',
              }}
            />
          </div>

          {/* Commit Message */}
          <div>
            <label style={{ display: 'block', fontSize: '12px', fontWeight: 600, color: 'var(--color-text-muted)', marginBottom: '6px' }}>
              Commit Message <span data-testid="commit-required-indicator" style={{ color: 'var(--color-status-offline)' }}>*</span>
            </label>
            <textarea
              rows={3}
              required
              data-testid="commit-message-input"
              placeholder="feat(workspace): implement editor session recovery protocol"
              value={commitMessage}
              onChange={(e) => setCommitMessage(e.target.value)}
              style={{
                width: '100%',
                padding: '8px 12px',
                backgroundColor: 'var(--color-bg-canvas)',
                border: '1px solid var(--color-border-subtle)',
                borderRadius: '6px',
                color: 'var(--color-text-primary)',
                fontSize: '13px',
                fontFamily: 'var(--font-mono, monospace)',
              }}
            />
          </div>

          {/* Staged Files List */}
          <div>
            <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: '8px' }}>
              <label style={{ fontSize: '12px', fontWeight: 600, color: 'var(--color-text-muted)' }}>
                Changes to Commit
              </label>
              <div style={{ display: 'flex', gap: '8px' }}>
                <button
                  type="button"
                  data-testid="stage-all-btn"
                  onClick={handleStageAll}
                  style={{ background: 'none', border: 'none', color: 'var(--color-brand-hover)', fontSize: '12px', cursor: 'pointer' }}
                >
                  Stage All
                </button>
                <button
                  type="button"
                  data-testid="unstage-all-btn"
                  onClick={handleUnstageAll}
                  style={{ background: 'none', border: 'none', color: 'var(--color-text-muted)', fontSize: '12px', cursor: 'pointer' }}
                >
                  Unstage All
                </button>
              </div>
            </div>

            <div
              data-testid="staged-files-list"
              style={{
                maxHeight: '160px',
                overflowY: 'auto',
                backgroundColor: 'var(--color-bg-canvas)',
                border: '1px solid var(--color-border-subtle)',
                borderRadius: '6px',
                padding: '8px',
              }}
            >
              {files.map((file) => {
                const isStaged = stagedFiles.includes(file.path);
                const fileStatus = getGitFileStatusConfig(file.isDirty ? 'modified' : 'clean');
                const stageConfig = getGitStageStateConfig(isStaged ? 'staged' : 'unstaged');

                return (
                  <label
                    key={file.path}
                    data-testid={`file-row-${file.path.replace(/[^a-zA-Z0-9_-]/g, '_')}`}
                    style={{
                      display: 'flex',
                      alignItems: 'center',
                      gap: '10px',
                      padding: '6px 8px',
                      borderRadius: '4px',
                      cursor: 'pointer',
                      fontSize: '13px',
                      backgroundColor: stageConfig.bgVar,
                    }}
                  >
                    <input
                      type="checkbox"
                      checked={isStaged}
                      onChange={() => toggleStage(file.path)}
                    />
                    <span style={{ fontFamily: 'var(--font-mono, monospace)', color: fileStatus.colorVar }}>
                      {file.path}
                    </span>
                    {file.isDirty && (
                      <span data-testid={`file-badge-${file.path.replace(/[^a-zA-Z0-9_-]/g, '_')}`} style={{ fontSize: '11px', color: fileStatus.badgeColorVar, marginLeft: 'auto' }}>
                        {fileStatus.badgeText}
                      </span>
                    )}
                  </label>
                );
              })}
            </div>
          </div>

          {/* Footer Actions */}
          <div
            style={{
              display: 'flex',
              justifyContent: 'flex-end',
              gap: '10px',
              marginTop: '8px',
              borderTop: '1px solid var(--color-border-subtle)',
              paddingTop: '16px',
            }}
          >
            <Button type="button" variant="secondary" onClick={onCancel}>
              Cancel
            </Button>
            <Button
              type="submit"
              variant="primary"
              data-testid="commit-submit-btn"
              disabled={stagedFiles.length === 0 || !commitMessage.trim()}
            >
              Commit & Sign ({stagedFiles.length})
            </Button>
          </div>
        </form>
      </div>
    </div>
  );
};
