import React, { useState } from 'react';
import { RunItem, RunState } from '@/contracts/types';
import { Button } from '@/shared/ui/Button';

export interface RunListProps {
  runs: RunItem[];
  isLoading: boolean;
  onSelectRun?: (runId: string) => void;
  onCreateRun?: () => void;
  runsState?: 'idle' | 'loading' | 'success' | 'error';
  runError?: string | null;
  lastFetchedAt?: Date | null;
  onRefresh?: () => void;
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
  runsState = 'idle',
  runError = null,
  lastFetchedAt = null,
  onRefresh,
}) => {
  const [selectedFilter, setSelectedFilter] = useState<RunState | 'ALL'>('ALL');

  const filteredRuns = runs.filter((run) => {
    if (selectedFilter === 'ALL') return true;
    return run.state === selectedFilter;
  });

  return (
    <div>
      {/* Stale Warning Banner when polling failed with cached runs */}
      {runsState === 'error' && runs.length > 0 && (
        <div
          role="alert"
          data-testid="run-stale-warning"
          style={{
            padding: '12px 16px',
            marginBottom: '16px',
            backgroundColor: 'rgba(239, 68, 68, 0.1)',
            border: '1px solid #ef4444',
            borderRadius: 'var(--radius-md)',
            color: '#fca5a5',
            fontSize: '0.8125rem',
          }}
        >
          ⚠️ [동기화 실패] Run 작업 목록 동기화에 실패했습니다 ({runError || '통신 오류'}).
          현재 표시된 목록은 {lastFetchedAt ? lastFetchedAt.toLocaleTimeString('ko-KR') : '과거'} 화면 확인 시점 스냅샷입니다.
        </div>
      )}

      <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: '20px' }}>
        <div>
          <div style={{ display: 'flex', alignItems: 'center', gap: '10px' }}>
            <h2 style={{ fontSize: '1.25rem', fontWeight: 600, margin: 0 }}>Run 작업 목록 ({runs.length}건)</h2>
            <span
              role="status"
              data-testid="run-list-freshness-indicator"
              style={{
                fontSize: '0.75rem',
                color: 'var(--color-text-muted)',
                backgroundColor: 'var(--color-bg-subtle)',
                padding: '2px 8px',
                borderRadius: 'var(--radius-sm)',
                border: '1px solid var(--color-border-subtle)',
              }}
            >
              🔄 자동 갱신 (5초 주기) · 화면 확인: {lastFetchedAt ? lastFetchedAt.toLocaleTimeString('ko-KR') : '동기화 중...'}
            </span>
            {onRefresh && (
              <button
                type="button"
                data-testid="run-list-refresh-btn"
                onClick={() => onRefresh()}
                style={{
                  fontSize: '0.75rem',
                  padding: '2px 8px',
                  backgroundColor: 'transparent',
                  border: '1px solid var(--color-border-subtle)',
                  borderRadius: 'var(--radius-sm)',
                  cursor: 'pointer',
                  color: 'var(--color-text-secondary)',
                }}
              >
                새로고침
              </button>
            )}
          </div>
          <span style={{ fontSize: '0.8125rem', color: 'var(--color-text-muted)', display: 'block', marginTop: '4px' }}>
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
            ) : runsState === 'error' && runs.length === 0 ? (
              <tr>
                <td colSpan={5} style={{ padding: '32px 16px', textAlign: 'center' }}>
                  <div
                    role="alert"
                    data-testid="run-fetch-error-state"
                    style={{
                      padding: '24px 20px',
                      backgroundColor: 'rgba(239, 68, 68, 0.08)',
                      border: '1px solid #ef4444',
                      borderRadius: 'var(--radius-md)',
                      maxWidth: '540px',
                      margin: '0 auto',
                    }}
                  >
                    <div style={{ fontSize: '1.5rem', marginBottom: '8px' }}>⚠️</div>
                    <div style={{ fontSize: '1rem', fontWeight: 600, color: '#fca5a5', marginBottom: '6px' }}>
                      Run 작업 목록 동기화 실패
                    </div>
                    <p style={{ fontSize: '0.8125rem', color: 'var(--color-text-muted)', margin: '0 0 16px 0' }}>
                      서버와 통신할 수 없어 Run 작업 목록을 조회하지 못했습니다 ({runError || '오류 발생'}). 이는 '작업 0건'(정상 0건 아님)이며, 실행 중인 작업이 서버에서 구동 중일 수 있습니다.
                    </p>
                    {onRefresh && (
                      <button
                        type="button"
                        data-testid="run-error-retry-btn"
                        onClick={() => onRefresh()}
                        style={{
                          padding: '6px 14px',
                          backgroundColor: '#ef4444',
                          color: '#fff',
                          border: 'none',
                          borderRadius: 'var(--radius-sm)',
                          fontSize: '0.8125rem',
                          fontWeight: 600,
                          cursor: 'pointer',
                        }}
                      >
                        다시 시도
                      </button>
                    )}
                  </div>
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
                    <div>{run.objective ?? '작업 목적 미관측'}</div>
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
                    {run.requestedBy ?? '미관측'}
                  </td>
                  <td style={{ padding: '12px 16px', color: 'var(--color-text-muted)', fontSize: '0.8125rem' }}>
                    <div data-testid={`run-created-at-${run.id}`}>
                      생성: {run.createdAt ? new Date(run.createdAt).toLocaleString('ko-KR') : '미관측'}
                    </div>
                    {(run.state === 'succeeded' || run.state === 'failed') && (
                      <div data-testid={`run-completed-at-${run.id}`} style={{ fontSize: '0.75rem', color: run.state === 'succeeded' ? '#10b981' : '#f85149', marginTop: '2px' }}>
                        종료: {run.updatedAt ? new Date(run.updatedAt).toLocaleString('ko-KR') : '미관측'}
                      </div>
                    )}
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
