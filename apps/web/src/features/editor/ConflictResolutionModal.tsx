import React from 'react';
import { Button } from '@/shared/ui/Button';
import { FileDiffResult } from '@/contracts/types';
import { DiffViewer } from './DiffViewer';

interface ConflictResolutionModalProps {
  filePath: string;
  diff: FileDiffResult;
  onKeepMine: () => void;
  onAcceptRemote: () => void;
  onMerge: () => void;
  onCancel: () => void;
}

export const ConflictResolutionModal: React.FC<ConflictResolutionModalProps> = ({
  filePath,
  diff,
  onKeepMine,
  onAcceptRemote,
  onMerge,
  onCancel,
}) => {
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
        padding: '24px',
      }}
    >
      <div
        style={{
          width: '100%',
          maxWidth: '900px',
          height: '80vh',
          backgroundColor: '#161b22',
          border: '1px solid #f85149',
          borderRadius: 'var(--radius-lg, 8px)',
          display: 'flex',
          flexDirection: 'column',
          boxShadow: '0 12px 32px rgba(0, 0, 0, 0.5)',
          overflow: 'hidden',
        }}
      >
        {/* Warning Banner */}
        <div
          style={{
            padding: '16px 20px',
            backgroundColor: 'rgba(248, 81, 73, 0.1)',
            borderBottom: '1px solid #30363d',
            display: 'flex',
            justifyContent: 'space-between',
            alignItems: 'center',
          }}
        >
          <div>
            <div style={{ display: 'flex', alignItems: 'center', gap: '8px' }}>
              <span style={{ color: '#f85149', fontWeight: 'bold', fontSize: '16px' }}>
                ⚠️ 412 Precondition Failed — Concurrency Conflict
              </span>
              <span
                style={{
                  fontSize: '11px',
                  padding: '2px 6px',
                  backgroundColor: '#f85149',
                  color: '#fff',
                  borderRadius: '4px',
                  fontWeight: 600,
                }}
              >
                ETag Mismatch
              </span>
            </div>
            <p style={{ margin: '4px 0 0 0', fontSize: '13px', color: '#8b949e' }}>
              File <code style={{ color: '#58a6ff' }}>{filePath}</code> was modified by another agent or background process. Review the diff below before saving.
            </p>
          </div>
          <Button size="sm" variant="secondary" onClick={onCancel}>
            Cancel
          </Button>
        </div>

        {/* Diff Container */}
        <div style={{ flex: 1, minHeight: 0 }}>
          <DiffViewer diff={diff} />
        </div>

        {/* Action Footer */}
        <div
          style={{
            padding: '12px 20px',
            borderTop: '1px solid #30363d',
            backgroundColor: '#0d1117',
            display: 'flex',
            justifyContent: 'space-between',
            alignItems: 'center',
          }}
        >
          <div style={{ fontSize: '12px', color: '#8b949e' }}>
            Choose an option to resolve this revision conflict safely:
          </div>
          <div style={{ display: 'flex', gap: '10px' }}>
            <Button size="sm" variant="secondary" onClick={onAcceptRemote}>
              Discard Local (Accept Remote)
            </Button>
            <Button size="sm" variant="secondary" onClick={onKeepMine} style={{ color: '#f85149', borderColor: '#f85149' }}>
              Force Overwrite (Keep Mine)
            </Button>
            <Button size="sm" variant="primary" onClick={onMerge}>
              Merge & Save
            </Button>
          </div>
        </div>
      </div>
    </div>
  );
};
