import React from 'react';
import { Button } from '@/shared/ui/Button';
import { useModalA11y } from '@/shared/ui/useModalA11y';
import { FileDiffResult } from '@/contracts/types';
import { DiffViewer } from './DiffViewer';

export type UiConflictStatus = 'etag_mismatch' | 'concurrency_conflict';

export interface ConflictStatusConfigItem {
  colorVar: string;
  bgVar: string;
  borderVar: string;
  badgeBgVar: string;
  badgeFgVar: string;
  label: string;
  badgeLabel: string;
}

export const CONFLICT_STATUS_CONFIG: Record<UiConflictStatus, ConflictStatusConfigItem> = {
  etag_mismatch: {
    colorVar: 'var(--color-status-offline)',
    bgVar: 'var(--color-risk-l3-bg)',
    borderVar: 'var(--color-risk-l3-border)',
    badgeBgVar: 'var(--color-status-offline)',
    badgeFgVar: 'var(--color-brand-primary-fg)',
    label: '⚠️ 412 Precondition Failed — Concurrency Conflict',
    badgeLabel: 'ETag Mismatch',
  },
  concurrency_conflict: {
    colorVar: 'var(--color-status-degraded)',
    bgVar: 'var(--color-bg-subtle)',
    borderVar: 'var(--color-border-subtle)',
    badgeBgVar: 'var(--color-status-degraded)',
    badgeFgVar: 'var(--color-brand-primary-fg)',
    label: '⚠️ Concurrency Revision Conflict',
    badgeLabel: 'Conflict Detected',
  },
} as const satisfies Record<UiConflictStatus, ConflictStatusConfigItem>;

export function getConflictStatusConfig(status: string): ConflictStatusConfigItem {
  if (Object.hasOwn(CONFLICT_STATUS_CONFIG, status)) {
    return CONFLICT_STATUS_CONFIG[status as UiConflictStatus];
  }
  return {
    colorVar: 'var(--color-status-unknown)',
    bgVar: 'var(--color-bg-subtle)',
    borderVar: 'var(--color-border-subtle)',
    badgeBgVar: 'var(--color-status-unknown)',
    badgeFgVar: 'var(--color-brand-primary-fg)',
    label: `⚠️ UNKNOWN (${status})`,
    badgeLabel: `UNKNOWN (${status})`,
  };
}

export type UiConflictResolutionAction = 'accept_remote' | 'keep_mine' | 'merge';

export interface ConflictResolutionActionConfigItem {
  colorVar: string;
  borderColorVar: string;
  label: string;
}

export const CONFLICT_RESOLUTION_ACTION_CONFIG: Record<UiConflictResolutionAction, ConflictResolutionActionConfigItem> = {
  accept_remote: {
    colorVar: 'var(--color-text-secondary)',
    borderColorVar: 'var(--color-border-subtle)',
    label: 'Discard Local (Accept Remote)',
  },
  keep_mine: {
    colorVar: 'var(--color-status-offline)',
    borderColorVar: 'var(--color-status-offline)',
    label: 'Force Overwrite (Keep Mine)',
  },
  merge: {
    colorVar: 'var(--color-brand-hover)',
    borderColorVar: 'var(--color-brand-primary)',
    label: 'Merge & Save',
  },
} as const satisfies Record<UiConflictResolutionAction, ConflictResolutionActionConfigItem>;

export function getConflictResolutionActionConfig(action: string): ConflictResolutionActionConfigItem {
  if (Object.hasOwn(CONFLICT_RESOLUTION_ACTION_CONFIG, action)) {
    return CONFLICT_RESOLUTION_ACTION_CONFIG[action as UiConflictResolutionAction];
  }
  return {
    colorVar: 'var(--color-status-unknown)',
    borderColorVar: 'var(--color-status-unknown)',
    label: `UNKNOWN (${action})`,
  };
}

interface ConflictResolutionModalProps {
  filePath: string;
  diff: FileDiffResult;
  conflictStatus?: UiConflictStatus;
  onKeepMine: () => void;
  onAcceptRemote: () => void;
  onMerge: () => void;
  onCancel: () => void;
}

export const ConflictResolutionModal: React.FC<ConflictResolutionModalProps> = ({
  filePath,
  diff,
  conflictStatus = 'etag_mismatch',
  onKeepMine,
  onAcceptRemote,
  onMerge,
  onCancel,
}) => {
  const { containerRef, handleKeyDown } = useModalA11y({
    isOpen: true,
    onClose: onCancel,
  });

  const statusConfig = getConflictStatusConfig(conflictStatus);
  const keepMineAction = getConflictResolutionActionConfig('keep_mine');

  return (
    <div
      ref={containerRef}
      role="dialog"
      aria-modal="true"
      aria-labelledby="conflict-resolution-title"
      data-testid="conflict-resolution-backdrop"
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
        padding: '24px',
      }}
    >
      <div
        data-testid="conflict-resolution-dialog"
        style={{
          width: '100%',
          maxWidth: '900px',
          height: '80vh',
          backgroundColor: 'var(--color-bg-surface)',
          border: `1px solid ${statusConfig.colorVar}`,
          borderRadius: 'var(--radius-lg, 8px)',
          display: 'flex',
          flexDirection: 'column',
          boxShadow: 'var(--shadow-lg)',
          overflow: 'hidden',
        }}
      >
        {/* Warning Banner */}
        <div
          data-testid="conflict-warning-banner"
          style={{
            padding: '16px 20px',
            backgroundColor: statusConfig.bgVar,
            borderBottom: '1px solid var(--color-border-subtle)',
            display: 'flex',
            justifyContent: 'space-between',
            alignItems: 'center',
          }}
        >
          <div>
            <div style={{ display: 'flex', alignItems: 'center', gap: '8px' }}>
              <span id="conflict-resolution-title" style={{ color: statusConfig.colorVar, fontWeight: 'bold', fontSize: '16px' }}>
                {statusConfig.label}
              </span>
              <span
                data-testid="conflict-status-badge"
                style={{
                  fontSize: '11px',
                  padding: '2px 6px',
                  backgroundColor: statusConfig.badgeBgVar,
                  color: statusConfig.badgeFgVar,
                  borderRadius: '4px',
                  fontWeight: 600,
                }}
              >
                {statusConfig.badgeLabel}
              </span>
            </div>
            <p style={{ margin: '4px 0 0 0', fontSize: '13px', color: 'var(--color-text-muted)' }}>
              File <code style={{ color: 'var(--color-brand-hover)' }}>{filePath}</code> was modified by another agent or background process. Review the diff below before saving.
            </p>
          </div>
          <Button size="sm" variant="secondary" onClick={onCancel}>
            Cancel
          </Button>
        </div>

        {/* Diff Container */}
        <div data-testid="conflict-diff-container" style={{ flex: 1, minHeight: 0 }}>
          <DiffViewer diff={diff} />
        </div>

        {/* Action Footer */}
        <div
          data-testid="conflict-action-footer"
          style={{
            padding: '12px 20px',
            borderTop: '1px solid var(--color-border-subtle)',
            backgroundColor: 'var(--color-bg-canvas)',
            display: 'flex',
            justifyContent: 'space-between',
            alignItems: 'center',
          }}
        >
          <div style={{ fontSize: '12px', color: 'var(--color-text-muted)' }}>
            Choose an option to resolve this revision conflict safely:
          </div>
          <div style={{ display: 'flex', gap: '10px' }}>
            <Button size="sm" variant="secondary" onClick={onAcceptRemote}>
              Discard Local (Accept Remote)
            </Button>
            <Button
              size="sm"
              variant="secondary"
              data-testid="force-overwrite-btn"
              onClick={onKeepMine}
              style={{ color: keepMineAction.colorVar, borderColor: keepMineAction.borderColorVar }}
            >
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
