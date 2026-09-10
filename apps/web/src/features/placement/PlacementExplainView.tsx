import React from 'react';
import { PlacementExplainResult } from '@/contracts/types';

export interface PlacementExplainViewProps {
  explainResult: PlacementExplainResult;
}

export const PlacementExplainView: React.FC<PlacementExplainViewProps> = ({
  explainResult,
}) => {
  const { selectedNodeId, evaluations, policyVersion, snapshotVersion, decidedAt } =
    explainResult;

  return (
    <div
      style={{
        padding: '24px',
        backgroundColor: 'var(--color-bg-surface)',
        borderRadius: 'var(--radius-lg)',
        border: '1px solid var(--color-border-subtle)',
        boxShadow: 'var(--shadow-sm)',
      }}
    >
      <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'flex-start', marginBottom: '20px' }}>
        <div>
          <h3 style={{ fontSize: '1.125rem', fontWeight: 600 }}>후보 노드 평가 및 제외 Explain 원장 (AC-05)</h3>
          <p style={{ fontSize: '0.8125rem', color: 'var(--color-text-muted)', marginTop: '2px' }}>
            Hard Filter 탈락 사유 및 가중치 점수 합산에 따른 결정론적 배치 추적
          </p>
        </div>
        <div style={{ textAlign: 'right', fontSize: '0.75rem', color: 'var(--color-text-muted)' }}>
          <div>정책: <code>{policyVersion}</code></div>
          <div>스냅샷: <code>{snapshotVersion}</code></div>
          <div>결정 시각: {new Date(decidedAt).toLocaleTimeString('ko-KR')}</div>
        </div>
      </div>

      {/* Winner Summary Banner */}
      <div
        style={{
          padding: '16px 20px',
          borderRadius: 'var(--radius-md)',
          backgroundColor: selectedNodeId ? 'rgba(16, 185, 129, 0.1)' : 'var(--color-risk-l3-bg)',
          border: `1px solid ${selectedNodeId ? 'var(--color-brand-success)' : 'var(--color-risk-l3-border)'}`,
          marginBottom: '24px',
          display: 'flex',
          alignItems: 'center',
          justifyContent: 'space-between',
        }}
      >
        <div style={{ display: 'flex', alignItems: 'center', gap: '12px' }}>
          <span style={{ fontSize: '1.5rem' }}>{selectedNodeId ? '🎯' : '⚠️'}</span>
          <div>
            <div style={{ fontWeight: 700, fontSize: '1rem' }}>
              {selectedNodeId ? `최적 배치 노드 선정: ${selectedNodeId}` : '배치 가능한 노드가 없습니다 (전원 탈락)'}
            </div>
            <p style={{ fontSize: '0.8125rem', color: 'var(--color-text-muted)', marginTop: '2px' }}>
              {selectedNodeId
                ? '모든 Hard Filter를 통과하고 가중 종합 점수가 가장 높은 노드가 초과 예약 없이 선정되었습니다.'
                : '요구 자원량 또는 제약 조건이 5개 노드의 가용 한도를 초과했습니다. 요구사항을 완화하십시오.'}
            </p>
          </div>
        </div>
      </div>

      {/* Evaluations Breakdown Cards */}
      <div style={{ display: 'flex', flexDirection: 'column', gap: '12px' }}>
        {evaluations.map((cand) => {
          const isWinner = cand.nodeId === selectedNodeId;
          const passed = cand.hardFilterPassed;

          return (
            <div
              key={cand.nodeId}
              style={{
                padding: '16px',
                borderRadius: 'var(--radius-md)',
                backgroundColor: 'var(--color-bg-subtle)',
                border: `1px solid ${isWinner ? 'var(--color-brand-success)' : 'var(--color-border-subtle)'}`,
                display: 'grid',
                gridTemplateColumns: '220px 1fr auto',
                gap: '16px',
                alignItems: 'center',
              }}
            >
              {/* Node Identifier & Status */}
              <div>
                <div style={{ display: 'flex', alignItems: 'center', gap: '8px' }}>
                  <span style={{ fontWeight: 700, fontSize: '0.9375rem' }}>{cand.hostname}</span>
                  <span
                    style={{
                      padding: '2px 6px',
                      borderRadius: '4px',
                      fontSize: '0.6875rem',
                      fontWeight: 600,
                      backgroundColor: passed ? 'rgba(16, 185, 129, 0.15)' : 'var(--color-risk-l3-bg)',
                      color: passed ? 'var(--color-brand-success)' : 'var(--color-brand-danger)',
                    }}
                  >
                    {passed ? '통과 (PASSED)' : '탈락 (REJECTED)'}
                  </span>
                </div>
                <code style={{ fontSize: '0.6875rem', color: 'var(--color-text-muted)' }}>
                  {cand.nodeId} ({cand.os.toUpperCase()})
                </code>
              </div>

              {/* Middle: Details (Rejection reasons OR Scores) */}
              <div>
                {!passed ? (
                  <div style={{ display: 'flex', flexDirection: 'column', gap: '4px' }}>
                    {cand.rejectionReasons.map((reason, idx) => (
                      <div
                        key={idx}
                        style={{
                          fontSize: '0.75rem',
                          color: 'var(--color-brand-danger)',
                          display: 'flex',
                          alignItems: 'center',
                          gap: '6px',
                        }}
                      >
                        <span>✕</span> {reason}
                      </div>
                    ))}
                  </div>
                ) : (
                  <div style={{ display: 'grid', gridTemplateColumns: 'repeat(3, 1fr)', gap: '8px', fontSize: '0.75rem' }}>
                    <div style={{ padding: '6px 8px', backgroundColor: 'var(--color-bg-surface)', borderRadius: '4px' }}>
                      <span style={{ color: 'var(--color-text-muted)' }}>지역성(40%): </span>
                      <strong>{cand.scores?.localityScore}점</strong>
                    </div>
                    <div style={{ padding: '6px 8px', backgroundColor: 'var(--color-bg-surface)', borderRadius: '4px' }}>
                      <span style={{ color: 'var(--color-text-muted)' }}>가용여유(30%): </span>
                      <strong>{cand.scores?.headroomScore}점</strong>
                    </div>
                    <div style={{ padding: '6px 8px', backgroundColor: 'var(--color-bg-surface)', borderRadius: '4px' }}>
                      <span style={{ color: 'var(--color-text-muted)' }}>네트워크(30%): </span>
                      <strong>{cand.scores?.networkCostScore}점</strong>
                    </div>
                  </div>
                )}
              </div>

              {/* Right: Total Score */}
              <div style={{ textAlign: 'right', minWidth: '80px' }}>
                {passed && cand.scores && (
                  <div>
                    <span style={{ fontSize: '0.6875rem', color: 'var(--color-text-muted)', display: 'block' }}>
                      가중 종합 점수
                    </span>
                    <span
                      style={{
                        fontSize: '1.25rem',
                        fontWeight: 700,
                        color: isWinner ? 'var(--color-brand-success)' : 'var(--color-text-primary)',
                      }}
                    >
                      {cand.scores.totalScore}점
                    </span>
                  </div>
                )}
              </div>
            </div>
          );
        })}
      </div>
    </div>
  );
};
