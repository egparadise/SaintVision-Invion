import React, { useState } from 'react';
import { RunItem, RunState } from '@/contracts/types';
import { Button } from '@/shared/ui/Button';

export interface RunListProps {
  runs: RunItem[];
  isLoading: boolean;
  onSelectRun?: (runId: string) => void;
  onCreateRun?: () => void;
}

const RUN_STATE_CONFIG: Record<
  RunState,
  { label: string; color: string; bg: string }
> = {
  draft: { label: '초안', color: '#64748b', bg: 'rgba(100, 116, 139, 0.15)' },
  validated: { label: '검증됨', color: '#3b82f6', bg: 'rgba(59, 130, 246, 0.15)' },
  planned: { label: '계획 수립', color: '#0284c7', bg: 'rgba(2, 132, 199, 0.15)' },
  awaiting_approval: { label: '승인 대기', color: '#f59e0b', bg: 'rgba(245, 158, 11, 0.15)' },
  scheduled: { label: '스케줄됨', color: '#8b5cf6', bg: 'rgba(139, 92, 246, 0.15)' },
  running: { label: '실행 중', color: '#3b82f6', bg: 'rgba(59, 130, 246, 0.2)' },
  verifying: { label: '결과 검증', color: '#06b6d4', bg: 'rgba(6, 182, 212, 0.15)' },
  recovering: { label: '복구 중', color: '#f97316', bg: 'rgba(249, 115, 22, 0.15)' },
  succeeded: { label: '성공', color: '#10b981', bg: 'rgba(16, 185, 129, 0.15)' },
  failed: { label: '실패', color: '#ef4444', bg: 'rgba(239, 68, 68, 0.15)' },
  cancelled: { label: '취소됨', color: '#6b7280', bg: 'rgba(107, 114, 128, 0.15)' },
};

export const RunList: React.FC<RunListProps> = ({
  runs,
  isLoading,
  onSelectRun,
  onCreateRun,
}) => {
  const [selectedFilter, setSelectedFilter] = useState<RunState | 'ALL'>('ALL');

  const filteredRuns = runs.filter((run) => {
    if (selectedFilter === 'ALL') return true;
    return run.state === selectedFilter;
  });

  return (
    <div>
      <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: '20px' }}>
        <div>
          <h2 style={{ fontSize: '1.25rem', fontWeight: 600 }}>Run 작업 목록 ({runs.length}건)</h2>
          <span style={{ fontSize: '0.8125rem', color: 'var(--color-text-muted)' }}>
            11개 단일 수명주기 상태 및 실시간 SSE 동기화
          </span>
        </div>

        {onCreateRun && (
          <Button variant="primary" size="md" onClick={onCreateRun}>
            새 Run 요청
          </Button>
        )}
      </div>

      {/* State Filter Pills */}
      <div style={{ display: 'flex', flexWrap: 'wrap', gap: '6px', marginBottom: '20px' }}>
        <button
          onClick={() => setSelectedFilter('ALL')}
          style={{
            padding: '4px 10px',
            borderRadius: 'var(--radius-sm)',
            fontSize: '0.75rem',
            fontWeight: 600,
            cursor: 'pointer',
            border: '1px solid var(--color-border-strong)',
            backgroundColor: selectedFilter === 'ALL' ? 'var(--color-brand-primary)' : 'var(--color-bg-subtle)',
            color: selectedFilter === 'ALL' ? '#ffffff' : 'var(--color-text-secondary)',
          }}
        >
          전체 ({runs.length})
        </button>

        {(Object.keys(RUN_STATE_CONFIG) as RunState[]).map((state) => {
          const count = runs.filter((r) => r.state === state).length;
          const isCurrent = selectedFilter === state;
          const cfg = RUN_STATE_CONFIG[state];

          return (
            <button
              key={state}
              onClick={() => setSelectedFilter(state)}
              style={{
                padding: '4px 10px',
                borderRadius: 'var(--radius-sm)',
                fontSize: '0.75rem',
                fontWeight: 600,
                cursor: 'pointer',
                border: `1px solid ${isCurrent ? cfg.color : 'var(--color-border-subtle)'}`,
                backgroundColor: isCurrent ? cfg.bg : 'var(--color-bg-subtle)',
                color: isCurrent ? cfg.color : 'var(--color-text-muted)',
              }}
            >
              {cfg.label} ({count})
            </button>
          );
        })}
      </div>

      {/* Runs Table */}
      <div
        style={{
          backgroundColor: 'var(--color-bg-surface)',
          borderRadius: 'var(--radius-lg)',
          border: '1px solid var(--color-border-subtle)',
          overflow: 'hidden',
          boxShadow: 'var(--shadow-sm)',
        }}
      >
        <table style={{ width: '100%', borderCollapse: 'collapse', textAlign: 'left', fontSize: '0.875rem' }}>
          <thead>
            <tr style={{ backgroundColor: 'var(--color-bg-subtle)', borderBottom: '1px solid var(--color-border-subtle)' }}>
              <th style={{ padding: '12px 16px', fontWeight: 600 }}>Run ID</th>
              <th style={{ padding: '12px 16px', fontWeight: 600 }}>목표 (Objective)</th>
              <th style={{ padding: '12px 16px', fontWeight: 600 }}>수명주기 상태</th>
              <th style={{ padding: '12px 16px', fontWeight: 600 }}>요청자</th>
              <th style={{ padding: '12px 16px', fontWeight: 600 }}>생성 시각</th>
            </tr>
          </thead>
          <tbody>
            {isLoading ? (
              <tr>
                <td colSpan={5} style={{ padding: '32px', textAlign: 'center', color: 'var(--color-text-muted)' }}>
                  Run 목록을 불러오는 중입니다...
                </td>
              </tr>
            ) : filteredRuns.length === 0 ? (
              <tr>
                <td colSpan={5} style={{ padding: '32px', textAlign: 'center', color: 'var(--color-text-muted)' }}>
                  해당 상태의 Run이 없습니다.
                </td>
              </tr>
            ) : (
              filteredRuns.map((run) => {
              const cfg = RUN_STATE_CONFIG[run.state] || RUN_STATE_CONFIG.draft;
              return (
                <tr
                  key={run.id}
                  onClick={() => onSelectRun?.(run.id)}
                  style={{
                    borderBottom: '1px solid var(--color-border-subtle)',
                    cursor: 'pointer',
                    transition: 'background-color 0.15s',
                  }}
                  onMouseEnter={(e) => (e.currentTarget.style.backgroundColor = 'var(--color-bg-subtle)')}
                  onMouseLeave={(e) => (e.currentTarget.style.backgroundColor = 'transparent')}
                >
                  <td style={{ padding: '12px 16px', fontFamily: 'monospace', fontWeight: 600 }}>
                    <div>{run.id}</div>
                    {run.parentId && (
                      <span
                        style={{
                          display: 'inline-block',
                          marginTop: '2px',
                          padding: '1px 6px',
                          borderRadius: 'var(--radius-sm)',
                          fontSize: '0.6875rem',
                          backgroundColor: 'rgba(59, 130, 246, 0.1)',
                          color: '#3b82f6',
                          border: '1px solid rgba(59, 130, 246, 0.3)',
                        }}
                      >
                        ↳ 샤드 #{((run.shardIndex ?? 0) + 1)} (부모: {run.parentId.slice(0, 14)}...)
                      </span>
                    )}
                    {run.childRunIds && run.childRunIds.length > 0 && (
                      <span
                        style={{
                          display: 'inline-block',
                          marginTop: '2px',
                          padding: '1px 6px',
                          borderRadius: 'var(--radius-sm)',
                          fontSize: '0.6875rem',
                          backgroundColor: 'rgba(139, 92, 246, 0.1)',
                          color: '#8b5cf6',
                          border: '1px solid rgba(139, 92, 246, 0.3)',
                        }}
                      >
                        ⚡ 분산 부모 ({run.childRunIds.length}개 샤드)
                      </span>
                    )}
                  </td>
                  <td style={{ padding: '12px 16px', color: 'var(--color-text-primary)' }}>
                    <div>{run.objective}</div>
                    {run.manifestDigest && (
                      <div style={{ fontSize: '0.6875rem', color: 'var(--color-text-muted)', fontFamily: 'monospace', marginTop: '2px' }}>
                        Manifest: {run.manifestDigest.slice(0, 22)}...
                      </div>
                    )}
                  </td>
                  <td style={{ padding: '12px 16px' }}>
                    <div style={{ display: 'flex', flexDirection: 'column', gap: '4px', alignItems: 'flex-start' }}>
                      <span
                        style={{
                          display: 'inline-block',
                          padding: '2px 8px',
                          borderRadius: 'var(--radius-sm)',
                          fontSize: '0.75rem',
                          fontWeight: 600,
                          color: cfg.color,
                          backgroundColor: cfg.bg,
                          border: `1px solid ${cfg.color}`,
                        }}
                      >
                        {cfg.label}
                      </span>
                      {run.resourceReleasePending && (
                        <span
                          style={{
                            display: 'inline-block',
                            padding: '1px 6px',
                            borderRadius: 'var(--radius-sm)',
                            fontSize: '0.6875rem',
                            fontWeight: 600,
                            color: '#d97706',
                            backgroundColor: 'rgba(217, 119, 6, 0.15)',
                            border: '1px solid #d97706',
                          }}
                        >
                          ⏳ 자원 반환 대기 (ADR-040)
                        </span>
                      )}
                    </div>
                  </td>
                  <td style={{ padding: '12px 16px', color: 'var(--color-text-secondary)', fontSize: '0.8125rem' }}>
                    {run.requestedBy}
                  </td>
                  <td style={{ padding: '12px 16px', color: 'var(--color-text-muted)', fontSize: '0.8125rem' }}>
                    {new Date(run.createdAt).toLocaleString('ko-KR')}
                  </td>
                </tr>
              );
            }))}
          </tbody>
        </table>
      </div>
    </div>
  );
};
