import type { ReviewedAction } from '@/shared/api/approvalReview';
import React, { useState } from 'react';
import { ApprovalItem } from '@/contracts/types';
import { ApprovalReviewPanel } from './ApprovalReviewPanel';
import { reviewIdentity } from '@/shared/api/approvalReview';
import { RiskBadge } from '@/shared/ui/RiskBadge';
import { EmptyState } from '@/shared/ui/EmptyState';

export interface ApprovalCenterProps {
  approvals: ApprovalItem[];
  currentUserId: string;
  onApprove: (approvalId: string, nonce: string, shown?: ReviewedAction) => Promise<void>;
  onReject: (approvalId: string, reason: string) => Promise<void>;
}

export const ApprovalCenter: React.FC<ApprovalCenterProps> = ({
  approvals,
  currentUserId,
  onApprove,
  onReject,
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
      {/* Top Header with User Identity Switcher (for Two-Person Rule testing) */}
      <div
        style={{
          display: 'flex',
          justifyContent: 'space-between',
          alignItems: 'center',
          marginBottom: '24px',
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

        {/* User Identity Switcher */}
        <div style={{ display: 'flex', alignItems: 'center', gap: '10px' }}>
          <span style={{ fontSize: '0.8125rem', color: 'var(--color-text-muted)', fontWeight: 600 }}>
            현재 검토자 계정:
          </span>
          <strong>{currentUserId || '로그인 필요'}</strong>
        </div>
      </div>

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
          <div style={{ fontSize: '1.5rem', fontWeight: 700, color: 'var(--color-brand-warning)', marginTop: '4px' }}>
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
          <div style={{ fontSize: '1.5rem', fontWeight: 700, color: 'var(--color-brand-success)', marginTop: '4px' }}>
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
          <div style={{ fontSize: '1.5rem', fontWeight: 700, color: 'var(--color-brand-danger)', marginTop: '4px' }}>
            {rejectedCount}건
          </div>
        </div>
      </div>

      {/* Main Layout: Left Approvals List / Right Approval Detail */}
      {approvals.length === 0 ? (
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
              return (
                <div
                  key={item.id}
                  onClick={() => setSelectedApprovalId(item.id)}
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
                    <span
                      style={{
                        fontSize: '0.6875rem',
                        fontWeight: 600,
                        padding: '2px 6px',
                        borderRadius: 'var(--radius-sm)',
                        backgroundColor:
                          item.status === 'pending'
                            ? 'rgba(234, 179, 8, 0.15)'
                            : item.status === 'approved'
                            ? 'rgba(16, 185, 129, 0.15)'
                            : 'rgba(239, 68, 68, 0.15)',
                        color:
                          item.status === 'pending'
                            ? 'var(--color-brand-warning)'
                            : item.status === 'approved'
                            ? 'var(--color-brand-success)'
                            : 'var(--color-brand-danger)',
                      }}
                    >
                      {item.status.toUpperCase()}
                    </span>
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
