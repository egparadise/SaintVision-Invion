import React from 'react';
import { FileDiffResult, DiffLine } from '@/contracts/types';
import { Button } from '@/shared/ui/Button';

export type UiDiffLineType = DiffLine['type'];

export interface DiffLineTypeConfigItem {
  colorVar: string;
  bgVar: string;
  borderVar: string;
  prefix: string;
  label: string;
}

export const DIFF_LINE_TYPE_CONFIG: Record<UiDiffLineType, DiffLineTypeConfigItem> = {
  added: {
    colorVar: 'var(--color-diff-added-text)',
    bgVar: 'var(--color-diff-added-bg)',
    borderVar: 'var(--color-diff-added-border)',
    prefix: '+',
    label: 'Added',
  },
  removed: {
    colorVar: 'var(--color-diff-removed-text)',
    bgVar: 'var(--color-diff-removed-bg)',
    borderVar: 'var(--color-diff-removed-border)',
    prefix: '-',
    label: 'Removed',
  },
  unchanged: {
    colorVar: 'var(--color-text-secondary)',
    bgVar: 'transparent',
    borderVar: 'transparent',
    prefix: ' ',
    label: 'Unchanged',
  },
} as const satisfies Record<UiDiffLineType, DiffLineTypeConfigItem>;

export function getDiffLineTypeConfig(type: string): DiffLineTypeConfigItem {
  if (Object.hasOwn(DIFF_LINE_TYPE_CONFIG, type)) {
    return DIFF_LINE_TYPE_CONFIG[type as UiDiffLineType];
  }
  return {
    colorVar: 'var(--color-status-unknown)',
    bgVar: 'transparent',
    borderVar: 'transparent',
    prefix: '?',
    label: `UNKNOWN (${type})`,
  };
}

interface DiffViewerProps {
  diff: FileDiffResult;
  onClose?: () => void;
  onApply?: () => void;
  onRevert?: () => void;
}

export const DiffViewer: React.FC<DiffViewerProps> = ({
  diff,
  onClose,
  onApply,
  onRevert,
}) => {
  const addedConfig = getDiffLineTypeConfig('added');
  const removedConfig = getDiffLineTypeConfig('removed');

  return (
    <div
      data-testid="diff-viewer-container"
      style={{
        display: 'flex',
        flexDirection: 'column',
        height: '100%',
        backgroundColor: 'var(--color-bg-canvas)',
        color: 'var(--color-text-secondary)',
        fontFamily: 'var(--font-mono, monospace)',
        fontSize: '13px',
      }}
    >
      {/* Diff Header Bar */}
      <div
        data-testid="diff-header-bar"
        style={{
          display: 'flex',
          justifyContent: 'space-between',
          alignItems: 'center',
          padding: '8px 16px',
          borderBottom: '1px solid var(--color-border-subtle)',
          backgroundColor: 'var(--color-bg-surface)',
        }}
      >
        <div style={{ display: 'flex', alignItems: 'center', gap: '12px' }}>
          <span data-testid="diff-file-path" style={{ fontWeight: 600, color: 'var(--color-text-primary)' }}>{diff.path}</span>
          <span data-testid="diff-additions-count" style={{ color: addedConfig.colorVar, fontWeight: 600 }}>+{diff.additionsCount}</span>
          <span data-testid="diff-deletions-count" style={{ color: removedConfig.colorVar, fontWeight: 600 }}>-{diff.deletionsCount}</span>
          <span data-testid="diff-etag-info" style={{ fontSize: '11px', color: 'var(--color-text-muted)' }}>
            Base ETag: {diff.originalEtag.slice(0, 12)}... → New ETag: {diff.modifiedEtag.slice(0, 12)}...
          </span>
        </div>
        <div style={{ display: 'flex', gap: '8px' }}>
          {onRevert && (
            <Button size="sm" variant="secondary" onClick={onRevert}>
              Revert Changes
            </Button>
          )}
          {onApply && (
            <Button size="sm" variant="primary" onClick={onApply}>
              Keep & Save
            </Button>
          )}
          {onClose && (
            <Button size="sm" variant="secondary" onClick={onClose}>
              Close Diff
            </Button>
          )}
        </div>
      </div>

      {/* Diff Content Body */}
      <div
        data-testid="diff-content-body"
        style={{
          flex: 1,
          overflowY: 'auto',
          padding: '8px 0',
          lineHeight: '20px',
        }}
      >
        {diff.lines.map((line, idx) => {
          const lineConfig = getDiffLineTypeConfig(line.type);
          const borderLeft =
            lineConfig.borderVar === 'transparent'
              ? '3px solid transparent'
              : `3px solid ${lineConfig.borderVar}`;

          return (
            <div
              key={idx}
              data-testid={`diff-line-${idx}`}
              style={{
                display: 'flex',
                backgroundColor: lineConfig.bgVar,
                padding: '0 8px',
                borderLeft,
              }}
            >
              {/* Line Numbers */}
              <div
                style={{
                  width: '40px',
                  color: 'var(--color-text-muted)',
                  textAlign: 'right',
                  userSelect: 'none',
                  paddingRight: '8px',
                }}
              >
                {line.originalLineNumber ?? ''}
              </div>
              <div
                style={{
                  width: '40px',
                  color: 'var(--color-text-muted)',
                  textAlign: 'right',
                  userSelect: 'none',
                  paddingRight: '12px',
                  borderRight: '1px solid var(--color-border-subtle)',
                }}
              >
                {line.modifiedLineNumber ?? ''}
              </div>

              {/* Marker & Code content */}
              <div
                style={{
                  width: '20px',
                  textAlign: 'center',
                  color: lineConfig.colorVar,
                  userSelect: 'none',
                }}
              >
                {lineConfig.prefix}
              </div>
              <div
                style={{
                  flex: 1,
                  whiteSpace: 'pre',
                  color: lineConfig.colorVar,
                  overflowX: 'auto',
                }}
              >
                {line.content || ' '}
              </div>
            </div>
          );
        })}
      </div>
    </div>
  );
};
