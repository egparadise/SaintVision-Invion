import type { ReviewedAction } from '@/shared/api/approvalReview';
import React, { useState } from 'react';
import { ApprovalItem } from '@/contracts/types';
import { ApprovalReviewPanel } from './ApprovalReviewPanel';
import { reviewIdentity } from '@/shared/api/approvalReview';
import { RiskBadge } from '@/shared/ui/RiskBadge';
import { EmptyState } from '@/shared/ui/EmptyState';

export const APPROVAL_STATUS_CONFIG = {
  approved: {
    bg: 'var(--color-bg-subtle)',
    color: 'var(--color-status-online)',
    border: 'var(--color-status-online)',
    label: 'APPROVED',
  },
  dispatched: {
    bg: 'var(--color-bg-subtle)',
    color: 'var(--color-brand-hover)',
    border: 'var(--color-brand-hover)',
    label: 'DISPATCHED',
  },
  expired: {
    bg: 'var(--color-bg-subtle)',
    color: 'var(--color-status-offline)',
    border: 'var(--color-status-offline)',
    label: 'EXPIRED',
  },
  pending: {
    bg: 'var(--color-bg-subtle)',
    color: 'var(--color-status-degraded)',
    border: 'var(--color-status-degraded)',
    label: 'PENDING',
  },
  rejected: {
    bg: 'var(--color-bg-subtle)',
    color: 'var(--color-status-offline)',
    border: 'var(--color-status-offline)',
    label: 'REJECTED',
  },
} as const;

export function getApprovalStatusConfig(status: unknown) {
  if (status && typeof status === 'string' && Object.hasOwn(APPROVAL_STATUS_CONFIG, status)) {
    return APPROVAL_STATUS_CONFIG[status as keyof typeof APPROVAL_STATUS_CONFIG];
  }
  const raw = status ? String(status) : '';
  return {
    bg: 'var(--color-bg-subtle)',
    color: 'var(--color-status-unknown)',
    border: 'var(--color-status-unknown)',
    label: raw ? `UNKNOWN (${raw})` : 'UNKNOWN',
  };
}

export interface ApprovalCenterProps {
  approvals: ApprovalItem[];
  currentUserId: string;
  onApprove: (approvalId: string, nonce: string, shown?: ReviewedAction) => Promise<void>;
  onReject: (approvalId: string, reason: string) => Promise<void>;
  approvalsState?: 'idle' | 'loading' | 'success' | 'error';
  approvalError?: string | null;
  lastFetchedAt?: Date | null;
  onRefresh?: () => Promise<void> | void;
}

export const ApprovalCenter: React.FC<ApprovalCenterProps> = ({
  approvals,
  currentUserId,
  onApprove,
  onReject,
  approvalsState = 'idle',
  approvalError = null,
  lastFetchedAt = null,
  onRefresh,
}) => {
  const [selectedApprovalId, setSelectedApprovalId] = useState<string>(
    approvals[0]?.id || ''
  );

  const selectedApproval =
    approvals.find((a) => a.id === selectedApprovalId) || approvals[0];

  const pendingCount = approvals.filter((a) => a.status === 'pending').length;
  const approvedCount = approvals.filter((a) => a.status === 'approved').length;
  const rejectedCount = approvals.filter((a) => a.status === 'rejected').length;

  return (
    <div>
      {/* Top Header with User Identity Switcher and Freshness Indicator */}
      <div
        style={{
          display: 'flex',
          justifyContent: 'space-between',
          alignItems: 'center',
          marginBottom: '16px',
          padding: '16px 20px',
          backgroundColor: 'var(--color-bg-surface)',
          borderRadius: 'var(--radius-lg)',
          border: '1px solid var(--color-border-subtle)',
        }}
      >
        <div>
          <h2 style={{ fontSize: '1.25rem', fontWeight: 600 }}>거버넌스 승인 센터 (S04-FE)</h2>
          <p style={{ fontSize: '0.8125rem', color: 'var(--color-text-muted)', marginTop: '2px' }}>
            서버 정책과 만료 시각을 기준으로 승인 요청을 확인합니다.
          </p>
        </div>

        {/* Freshness Badge & User Identity */}
        <div style={{ display: 'flex', alignItems: 'center', gap: '16px' }}>
          <div
            role="status"
            data-testid="approval-freshness-indicator"
            style={{
              display: 'flex',
              alignItems: 'center',
              gap: '6px',
              padding: '6px 12px',
              borderRadius: '6px',
              backgroundColor: 'var(--color-brand-subtle)',
              border: '1px solid var(--color-brand-hover)',
              fontSize: '0.75rem',
              color: 'var(--color-brand-hover)',
            }}
          >
            <span>🔄 <strong>자동 갱신 (5초 주기)</strong></span>
            {lastFetchedAt && <span>· 화면 확인: {lastFetchedAt.toLocaleTimeString('ko-KR')}</span>}
          </div>

          {onRefresh && (
            <button
              type="button"
              data-testid="approval-refresh-btn"
              onClick={() => onRefresh()}
              style={{
                padding: '6px 12px',
                fontSize: '0.75rem',
                borderRadius: '6px',
                backgroundColor: 'var(--color-bg-subtle)',
                border: '1px solid var(--color-border-subtle)',
                color: 'var(--color-text-primary)',
                cursor: 'pointer',
              }}
            >
              🔄 새로고침
            </button>
          )}

          <div style={{ display: 'flex', alignItems: 'center', gap: '8px' }}>
            <span style={{ fontSize: '0.8125rem', color: 'var(--color-text-muted)', fontWeight: 600 }}>
              검토자:
            </span>
            <strong>{currentUserId || '로그인 필요'}</strong>
          </div>
        </div>
      </div>

      {/* Stale Warning Banner if Polling Failed (Silent Aging Defense) */}
      {(approvalsState === 'error' || approvalError) && (
        <div
          role="alert"
          data-testid="approval-stale-warning"
          style={{
            padding: '12px 16px',
            backgroundColor: 'var(--color-bg-subtle)',
            border: '1px solid var(--color-status-offline)',
            borderRadius: 'var(--radius-md)',
            color: 'var(--color-status-offline)',
            fontSize: '0.8125rem',
            lineHeight: 1.5,
            marginBottom: '16px',
          }}
        >
          <div>
            ⚠️ <strong>승인 목록 동기화 실패</strong>: 최신 승인 안건을 서버에서 조회하지 못했습니다 ({approvalError || '서버 응답 오류'}).
          </div>
          <div style={{ marginTop: '4px', fontSize: '0.75rem', color: 'var(--color-status-offline)' }}>
            {lastFetchedAt
              ? `현재 표시 중인 목록은 ${lastFetchedAt.toLocaleTimeString('ko-KR')} 화면 확인 시점 스냅샷입니다.`
              : '현재 유효한 승인 스냅샷이 없습니다. 서버 연결 상태를 확인하고 새로고침을 시도하십시오.'}
          </div>
        </div>
      )}

      {/* Metrics Row */}
      <div style={{ display: 'grid', gridTemplateColumns: 'repeat(3, 1fr)', gap: '16px', marginBottom: '24px' }}>
        <div
          style={{
            padding: '16px',
            backgroundColor: 'var(--color-bg-surface)',
            borderRadius: 'var(--radius-md)',
            border: '1px solid var(--color-border-subtle)',
            textAlign: 'center',
          }}
        >
          <div style={{ fontSize: '0.75rem', color: 'var(--color-text-muted)' }}>승인 대기</div>
          <div style={{ fontSize: '1.5rem', fontWeight: 700, color: 'var(--color-status-degraded)', marginTop: '4px' }}>
            {pendingCount}건
          </div>
        </div>
        <div
          style={{
            padding: '16px',
            backgroundColor: 'var(--color-bg-surface)',
            borderRadius: 'var(--radius-md)',
            border: '1px solid var(--color-border-subtle)',
            textAlign: 'center',
          }}
        >
          <div style={{ fontSize: '0.75rem', color: 'var(--color-text-muted)' }}>승인 완료</div>
          <div style={{ fontSize: '1.5rem', fontWeight: 700, color: 'var(--color-status-online)', marginTop: '4px' }}>
            {approvedCount}건
          </div>
        </div>
        <div
          style={{
            padding: '16px',
            backgroundColor: 'var(--color-bg-surface)',
            borderRadius: 'var(--radius-md)',
            border: '1px solid var(--color-border-subtle)',
            textAlign: 'center',
          }}
        >
          <div style={{ fontSize: '0.75rem', color: 'var(--color-text-muted)' }}>반려 / 만료</div>
          <div style={{ fontSize: '1.5rem', fontWeight: 700, color: 'var(--color-status-offline)', marginTop: '4px' }}>
            {rejectedCount}건
          </div>
        </div>
      </div>

      {/* Main Layout: Left Approvals List / Right Approval Detail */}
      {approvalsState === 'error' && approvals.length === 0 ? (
        <div
          role="alert"
          data-testid="approval-fetch-error-state"
          style={{
            padding: '40px 20px',
            textAlign: 'center',
            backgroundColor: 'var(--color-bg-surface)',
            border: '1px solid var(--color-status-offline)',
            borderRadius: 'var(--radius-lg)',
          }}
        >
          <div style={{ fontSize: '2rem', marginBottom: '8px' }}>⚠️</div>
          <h3 style={{ fontSize: '1rem', fontWeight: 600, color: 'var(--color-status-offline)', margin: '0 0 6px 0' }}>
            승인 안건 동기화 실패
          </h3>
          <p style={{ fontSize: '0.8125rem', color: 'var(--color-text-muted)', margin: '0 auto 16px auto', maxWidth: '480px' }}>
            서버와 통신할 수 없어 승인 요청 목록을 조회하지 못했습니다 ({approvalError || '오류 발생'}). 이는 '대기 안건 0건'(정상 0건 아님)이며, 미확인된 고위험 안건이 대기 중일 수 있습니다.
          </p>
          {onRefresh && (
            <button
              type="button"
              data-testid="approval-error-retry-btn"
              onClick={() => onRefresh()}
              style={{
                padding: '6px 14px',
                fontSize: '0.75rem',
                backgroundColor: 'var(--color-bg-subtle)',
                color: 'var(--color-text-primary)',
                border: '1px solid var(--color-border-subtle)',
                borderRadius: '4px',
                cursor: 'pointer',
                fontWeight: 600,
              }}
            >
              🔄 재시도 (Retry)
            </button>
          )}
        </div>
      ) : approvals.length === 0 ? (
        <EmptyState
          icon="🛡️"
          title="대기 중인 거버넌스 승인 안건 없음"
          description="현재 클러스터에 검토 또는 승인이 필요한 L1~L3 위험 작업 요청이 없습니다."
        />
      ) : (
        <div style={{ display: 'grid', gridTemplateColumns: '320px 1fr', gap: '20px', alignItems: 'start' }}>
          {/* Left List */}
          <div
            style={{
              backgroundColor: 'var(--color-bg-surface)',
              borderRadius: 'var(--radius-lg)',
              border: '1px solid var(--color-border-subtle)',
              overflow: 'hidden',
            }}
          >
            <div
              style={{
                padding: '14px 16px',
                borderBottom: '1px solid var(--color-border-subtle)',
                fontWeight: 600,
                fontSize: '0.875rem',
              }}
            >
              승인 안건 목록 ({approvals.length}건)
            </div>
            <div style={{ display: 'flex', flexDirection: 'column' }}>
              {approvals.map((item) => {
                const isSelected = item.id === selectedApproval?.id;
                const statusCfg = getApprovalStatusConfig(item.status);
                const isTwoPerson = item.requiredApprovals === 2;
                const isWaitingSecond = Boolean(item.firstApprovedBy && !item.secondApprovedBy);

                return (
                  <div
                    key={item.id}
                    role="button"
                    tabIndex={0}
                    data-testid={`approval-item-${item.id}`}
                    aria-label={`승인 안건 ${item.id} 선택`}
                    aria-pressed={isSelected}
                    onClick={() => setSelectedApprovalId(item.id)}
                    onKeyDown={(e) => {
                      if (e.key === 'Enter' || e.key === ' ') {
                        e.preventDefault();
                        setSelectedApprovalId(item.id);
                      }
                    }}
                    style={{
                      padding: '14px 16px',
                      borderBottom: '1px solid var(--color-border-subtle)',
                      cursor: 'pointer',
                      backgroundColor: isSelected ? 'var(--color-bg-subtle)' : 'transparent',
                      borderLeft: isSelected ? '3px solid var(--color-brand-primary)' : '3px solid transparent',
                      transition: 'background-color 0.15s',
                    }}
                  >
                    <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: '6px' }}>
                      {item.riskLevel ? <RiskBadge level={item.riskLevel} /> : <span>위험도 미관측</span>}
                      <div style={{ display: 'flex', alignItems: 'center', gap: '6px' }}>
                        {isTwoPerson && (
                          <span
                            data-testid={`approval-two-person-${item.id}`}
                            style={{
                              fontSize: '0.625rem',
                              fontWeight: 600,
                              padding: '2px 4px',
                              borderRadius: 'var(--radius-sm)',
                              backgroundColor: 'var(--color-bg-subtle)',
                              color: isWaitingSecond ? 'var(--color-brand-hover)' : 'var(--color-text-secondary)',
                              border: isWaitingSecond ? '1px solid var(--color-brand-hover)' : '1px solid var(--color-border-subtle)',
                            }}
                          >
                            {isWaitingSecond ? '1/2 승인 (2차 대기)' : '2인 필수'}
                          </span>
                        )}
                        <span
                          data-testid={`approval-status-${item.id}`}
                          style={{
                            fontSize: '0.6875rem',
                            fontWeight: 600,
                            padding: '2px 6px',
                            borderRadius: 'var(--radius-sm)',
                            backgroundColor: statusCfg.bg,
                            color: statusCfg.color,
                            border: `1px solid ${statusCfg.border}`,
                          }}
                        >
                          {statusCfg.label}
                        </span>
                      </div>
                    </div>
                    <div style={{ fontWeight: 600, fontSize: '0.8125rem', marginBottom: '4px' }}>
                      {item.target}
                    </div>
                    <code style={{ fontSize: '0.6875rem', color: 'var(--color-text-muted)' }}>
                      {item.id}
                    </code>
                  </div>
                );
              })}
            </div>
          </div>

          {/* Right Detail */}
          <div>
            {selectedApproval ? (
              <ApprovalReviewPanel
                key={`${currentUserId}:${reviewIdentity(selectedApproval)}`}
                approval={selectedApproval}
                currentUserId={currentUserId}
                onApprove={onApprove}
                onReject={onReject}
              />
            ) : (
              <div style={{ padding: '48px', textAlign: 'center', color: 'var(--color-text-muted)' }}>
                선택된 승인 안건이 없습니다.
              </div>
            )}
          </div>
        </div>
      )}
    </div>
  );
};
