import React from 'react';
import { FileDiffResult } from '@/contracts/types';
import { Button } from '@/shared/ui/Button';

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
  return (
    <div
      style={{
        display: 'flex',
        flexDirection: 'column',
        height: '100%',
        backgroundColor: '#0d1117',
        color: '#c9d1d9',
        fontFamily: 'var(--font-mono, monospace)',
        fontSize: '13px',
      }}
    >
      {/* Diff Header Bar */}
      <div
        style={{
          display: 'flex',
          justifyContent: 'space-between',
          alignItems: 'center',
          padding: '8px 16px',
          borderBottom: '1px solid #30363d',
          backgroundColor: '#161b22',
        }}
      >
        <div style={{ display: 'flex', alignItems: 'center', gap: '12px' }}>
          <span style={{ fontWeight: 600, color: '#f0f6fc' }}>{diff.path}</span>
          <span style={{ color: '#3fb950', fontWeight: 600 }}>+{diff.additionsCount}</span>
          <span style={{ color: '#f85149', fontWeight: 600 }}>-{diff.deletionsCount}</span>
          <span style={{ fontSize: '11px', color: '#8b949e' }}>
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
        style={{
          flex: 1,
          overflowY: 'auto',
          padding: '8px 0',
          lineHeight: '20px',
        }}
      >
        {diff.lines.map((line, idx) => {
          let bg = 'transparent';
          let textColor = '#c9d1d9';
          let prefix = ' ';

          if (line.type === 'added') {
            bg = 'rgba(46, 160, 67, 0.15)';
            textColor = '#3fb950';
            prefix = '+';
          } else if (line.type === 'removed') {
            bg = 'rgba(248, 81, 73, 0.15)';
            textColor = '#f85149';
            prefix = '-';
          }

          return (
            <div
              key={idx}
              style={{
                display: 'flex',
                backgroundColor: bg,
                padding: '0 8px',
                borderLeft:
                  line.type === 'added'
                    ? '3px solid #3fb950'
                    : line.type === 'removed'
                    ? '3px solid #f85149'
                    : '3px solid transparent',
              }}
            >
              {/* Line Numbers */}
              <div
                style={{
                  width: '40px',
                  color: '#484f58',
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
                  color: '#484f58',
                  textAlign: 'right',
                  userSelect: 'none',
                  paddingRight: '12px',
                  borderRight: '1px solid #30363d',
                }}
              >
                {line.modifiedLineNumber ?? ''}
              </div>

              {/* Marker & Code content */}
              <div
                style={{
                  width: '20px',
                  textAlign: 'center',
                  color: textColor,
                  userSelect: 'none',
                }}
              >
                {prefix}
              </div>
              <div
                style={{
                  flex: 1,
                  whiteSpace: 'pre',
                  color: textColor,
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
