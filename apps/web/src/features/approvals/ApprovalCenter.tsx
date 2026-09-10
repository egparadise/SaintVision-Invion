import React, { useState } from 'react';
import { ApprovalItem } from '@/contracts/types';
import { ApprovalDetail } from './ApprovalDetail';
import { RiskBadge } from '@/shared/ui/RiskBadge';

export interface ApprovalCenterProps {
  approvals: ApprovalItem[];
  currentUserId: string;
  onChangeUser: (newUserId: string) => void;
  onApprove: (approvalId: string, nonce: string) => Promise<void>;
  onReject: (approvalId: string, reason: string) => Promise<void>;
}

export const ApprovalCenter: React.FC<ApprovalCenterProps> = ({
  approvals,
  currentUserId,
  onChangeUser,
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
            L1~L3 고위험 작업 통제 · 2인 승인 원칙(Two-Person Rule) 및 15분 만료 타이머 강제
          </p>
        </div>

        {/* User Identity Switcher */}
        <div style={{ display: 'flex', alignItems: 'center', gap: '10px' }}>
          <span style={{ fontSize: '0.8125rem', color: 'var(--color-text-muted)', fontWeight: 600 }}>
            현재 검토자 계정:
          </span>
          <select
            value={currentUserId}
            onChange={(e) => onChangeUser(e.target.value)}
            style={{
              padding: '6px 12px',
              borderRadius: 'var(--radius-md)',
              border: '1px solid var(--color-border-strong)',
              backgroundColor: 'var(--color-bg-subtle)',
              color: 'var(--color-text-primary)',
              fontSize: '0.8125rem',
              fontWeight: 600,
            }}
          >
            <option value="usr_reviewer_01">usr_reviewer_01 (1차 승인자 담당)</option>
            <option value="usr_reviewer_02">usr_reviewer_02 (2차 독립 승인자)</option>
            <option value="usr_requester_alice">usr_requester_alice (요청자 - 승인 권한 없음)</option>
          </select>
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
                    <RiskBadge level={item.riskLevel} />
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
            <ApprovalDetail
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
    </div>
  );
};
