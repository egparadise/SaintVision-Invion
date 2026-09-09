import React, { useState } from 'react';
import { Button } from '@/shared/ui/Button';
import { GitCommitRecord } from '@/contracts/types';
import { createGitCommit } from './diffEngine';

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
      style={{
        position: 'fixed',
        inset: 0,
        backgroundColor: 'rgba(0, 0, 0, 0.75)',
        display: 'flex',
        alignItems: 'center',
        justifyContent: 'center',
        zIndex: 1000,
        padding: '20px',
      }}
    >
      <div
        style={{
          width: '100%',
          maxWidth: '650px',
          backgroundColor: '#161b22',
          border: '1px solid #30363d',
          borderRadius: 'var(--radius-lg, 8px)',
          display: 'flex',
          flexDirection: 'column',
          boxShadow: '0 12px 32px rgba(0, 0, 0, 0.5)',
          overflow: 'hidden',
        }}
      >
        {/* Header */}
        <div
          style={{
            padding: '16px 20px',
            borderBottom: '1px solid #30363d',
            display: 'flex',
            justifyContent: 'space-between',
            alignItems: 'center',
          }}
        >
          <div>
            <h3 style={{ margin: 0, fontSize: '16px', color: '#f0f6fc' }}>
              Git Source Commit (AC-06)
            </h3>
            <p style={{ margin: '4px 0 0 0', fontSize: '12px', color: '#8b949e' }}>
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
            <label style={{ display: 'block', fontSize: '12px', fontWeight: 600, color: '#8b949e', marginBottom: '6px' }}>
              Author
            </label>
            <input
              type="text"
              value={author}
              onChange={(e) => setAuthor(e.target.value)}
              style={{
                width: '100%',
                padding: '8px 12px',
                backgroundColor: '#0d1117',
                border: '1px solid #30363d',
                borderRadius: '6px',
                color: '#c9d1d9',
                fontSize: '13px',
              }}
            />
          </div>

          {/* Commit Message */}
          <div>
            <label style={{ display: 'block', fontSize: '12px', fontWeight: 600, color: '#8b949e', marginBottom: '6px' }}>
              Commit Message <span style={{ color: '#f85149' }}>*</span>
            </label>
            <textarea
              rows={3}
              required
              placeholder="feat(workspace): implement editor session recovery protocol"
              value={commitMessage}
              onChange={(e) => setCommitMessage(e.target.value)}
              style={{
                width: '100%',
                padding: '8px 12px',
                backgroundColor: '#0d1117',
                border: '1px solid #30363d',
                borderRadius: '6px',
                color: '#c9d1d9',
                fontSize: '13px',
                fontFamily: 'var(--font-mono, monospace)',
              }}
            />
          </div>

          {/* Staged Files List */}
          <div>
            <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: '8px' }}>
              <label style={{ fontSize: '12px', fontWeight: 600, color: '#8b949e' }}>
                Changes to Commit
              </label>
              <div style={{ display: 'flex', gap: '8px' }}>
                <button
                  type="button"
                  onClick={handleStageAll}
                  style={{ background: 'none', border: 'none', color: '#58a6ff', fontSize: '12px', cursor: 'pointer' }}
                >
                  Stage All
                </button>
                <button
                  type="button"
                  onClick={handleUnstageAll}
                  style={{ background: 'none', border: 'none', color: '#8b949e', fontSize: '12px', cursor: 'pointer' }}
                >
                  Unstage All
                </button>
              </div>
            </div>

            <div
              style={{
                maxHeight: '160px',
                overflowY: 'auto',
                backgroundColor: '#0d1117',
                border: '1px solid #30363d',
                borderRadius: '6px',
                padding: '8px',
              }}
            >
              {files.map((file) => {
                const isStaged = stagedFiles.includes(file.path);
                return (
                  <label
                    key={file.path}
                    style={{
                      display: 'flex',
                      alignItems: 'center',
                      gap: '10px',
                      padding: '6px 8px',
                      borderRadius: '4px',
                      cursor: 'pointer',
                      fontSize: '13px',
                      backgroundColor: isStaged ? 'rgba(56, 139, 253, 0.1)' : 'transparent',
                    }}
                  >
                    <input
                      type="checkbox"
                      checked={isStaged}
                      onChange={() => toggleStage(file.path)}
                    />
                    <span style={{ fontFamily: 'var(--font-mono, monospace)', color: file.isDirty ? '#e3b341' : '#c9d1d9' }}>
                      {file.path}
                    </span>
                    {file.isDirty && (
                      <span style={{ fontSize: '11px', color: '#e3b341', marginLeft: 'auto' }}>
                        modified
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
              borderTop: '1px solid #30363d',
              paddingTop: '16px',
            }}
          >
            <Button type="button" variant="secondary" onClick={onCancel}>
              Cancel
            </Button>
            <Button
              type="submit"
              variant="primary"
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
