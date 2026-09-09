import React, { useState, useEffect } from 'react';
import { ApprovalItem } from '@/contracts/types';
import { RiskBadge } from '@/shared/ui/RiskBadge';
import { Button } from '@/shared/ui/Button';

export interface ApprovalDetailProps {
  approval: ApprovalItem;
  currentUserId: string;
  onApprove: (approvalId: string, nonce: string) => Promise<void>;
  onReject: (approvalId: string, reason: string) => Promise<void>;
}

export const ApprovalDetail: React.FC<ApprovalDetailProps> = ({
  approval,
  currentUserId,
  onApprove,
  onReject,
}) => {
  const [secondsRemaining, setSecondsRemaining] = useState<number>(() => {
    const diff = Math.floor((new Date(approval.expiresAt).getTime() - Date.now()) / 1000);
    return Math.max(0, diff);
  });
  const [isSubmitting, setIsSubmitting] = useState(false);
  const [rejectReason, setRejectReason] = useState('');
  const [showRejectModal, setShowRejectModal] = useState(false);

  // Countdown timer effect
  useEffect(() => {
    if (secondsRemaining <= 0) return;
    const timer = setInterval(() => {
      setSecondsRemaining((prev) => Math.max(0, prev - 1));
    }, 1000);
    return () => clearInterval(timer);
  }, [secondsRemaining]);

  const isExpired = secondsRemaining === 0 || approval.status === 'expired';
  const hasDiff = Boolean(approval.unifiedDiff && approval.unifiedDiff.trim().length > 0);
  const isDiffLoadFailed = !hasDiff;

  // Two-Person Rule constraint
  const isFirstApprover = approval.firstApprovedBy === currentUserId;
  const isWaitingSecondApproval = Boolean(approval.firstApprovedBy && !approval.secondApprovedBy);
  const isSelfApprovalBlocked = isWaitingSecondApproval && isFirstApprover;

  const canApprove =
    !isExpired &&
    !isSubmitting &&
    hasDiff &&
    !isSelfApprovalBlocked &&
    approval.status === 'pending';

  const formatTimer = (totalSec: number) => {
    const min = Math.floor(totalSec / 60);
    const sec = totalSec % 60;
    return `${min.toString().padStart(2, '0')}:${sec.toString().padStart(2, '0')}`;
  };

  const handleConfirmApprove = async () => {
    if (!canApprove) return;
    setIsSubmitting(true);
    try {
      await onApprove(approval.id, approval.nonce);
    } finally {
      setIsSubmitting(false);
    }
  };

  const handleConfirmReject = async () => {
    if (!rejectReason.trim()) return;
    setIsSubmitting(true);
    try {
      await onReject(approval.id, rejectReason);
      setShowRejectModal(false);
    } finally {
      setIsSubmitting(false);
    }
  };

  return (
    <div
      style={{
        maxWidth: '900px',
        margin: '0 auto',
        backgroundColor: 'var(--color-bg-surface)',
        borderRadius: 'var(--radius-lg)',
        border: '1px solid var(--color-border-subtle)',
        boxShadow: 'var(--shadow-md)',
        overflow: 'hidden',
      }}
    >
      {/* Top Banner: ID, Risk Level, Countdown */}
      <div
        style={{
          display: 'flex',
          alignItems: 'center',
          justifyContent: 'space-between',
          padding: '16px 24px',
          backgroundColor: 'var(--color-bg-subtle)',
          borderBottom: '1px solid var(--color-border-subtle)',
        }}
      >
        <div style={{ display: 'flex', alignItems: 'center', gap: '12px' }}>
          <RiskBadge level={approval.riskLevel} />
          <h2 style={{ fontSize: '1.125rem', fontWeight: 600 }}>
            승인 요청: <code>{approval.id}</code>
          </h2>
        </div>

        <div style={{ display: 'flex', alignItems: 'center', gap: '8px' }}>
          <span style={{ fontSize: '0.8125rem', color: 'var(--color-text-muted)' }}>남은 시간:</span>
          <span
            style={{
              fontSize: '1rem',
              fontWeight: 700,
              fontFamily: 'monospace',
              color:
                secondsRemaining < 60
                  ? 'var(--color-status-offline)'
                  : 'var(--color-text-primary)',
              animation: secondsRemaining < 60 && secondsRemaining > 0 ? 'pulse 1s infinite' : 'none',
            }}
          >
            {isExpired ? '만료됨 (00:00)' : formatTimer(secondsRemaining)}
          </span>
        </div>
      </div>

      <div style={{ padding: '24px' }}>
        {/* Key Execution Metadata Grid */}
        <div
          style={{
            display: 'grid',
            gridTemplateColumns: 'repeat(auto-fit, minmax(240px, 1fr))',
            gap: '16px',
            marginBottom: '24px',
            padding: '16px',
            backgroundColor: 'var(--color-bg-canvas)',
            borderRadius: 'var(--radius-md)',
          }}
        >
          <div>
            <span style={{ fontSize: '0.75rem', color: 'var(--color-text-muted)' }}>실행 대상:</span>
            <div style={{ fontSize: '0.875rem', fontWeight: 600, marginTop: '2px' }}>
              {approval.target} (Node: {approval.nodeId})
            </div>
          </div>

          <div>
            <span style={{ fontSize: '0.75rem', color: 'var(--color-text-muted)' }}>명령 / 도구:</span>
            <div style={{ fontSize: '0.875rem', fontWeight: 600, fontFamily: 'monospace', marginTop: '2px' }}>
              {approval.command}
            </div>
          </div>

          <div>
            <span style={{ fontSize: '0.75rem', color: 'var(--color-text-muted)' }}>비용 / 잔여 예산:</span>
            <div style={{ fontSize: '0.875rem', fontWeight: 600, marginTop: '2px' }}>
              {approval.estimatedCostKrw.toLocaleString()} KRW 소모 예상 (잔여 {approval.remainingBudgetKrw.toLocaleString()} KRW)
            </div>
          </div>

          <div>
            <span style={{ fontSize: '0.75rem', color: 'var(--color-text-muted)' }}>영향 반경:</span>
            <div style={{ fontSize: '0.875rem', fontWeight: 600, marginTop: '2px' }}>
              {approval.blastRadius === 'workspace_isolated' ? '🟢 워크스페이스 격리 유지' : '🔴 호스트 경계 / 외부 영향 가능'}
            </div>
          </div>
        </div>

        {/* Rollback Warning Badge */}
        {!approval.rollbackPlan && (
          <div
            style={{
              padding: '12px 16px',
              backgroundColor: 'rgba(220, 38, 38, 0.1)',
              border: '1px solid var(--color-status-offline)',
              borderRadius: 'var(--radius-md)',
              color: 'var(--color-status-offline)',
              fontSize: '0.875rem',
              fontWeight: 500,
              marginBottom: '20px',
              display: 'flex',
              alignItems: 'center',
              gap: '8px',
            }}
          >
            <span>⚠️</span>
            <span>주의: 자동 롤백 절차가 정의되지 않았습니다. 장애 발생 시 수동 조치가 필요합니다.</span>
          </div>
        )}

        {/* Unified Diff Section */}
        <div style={{ marginBottom: '24px' }}>
          <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: '8px' }}>
            <h3 style={{ fontSize: '0.9375rem', fontWeight: 600 }}>변경 Unified Diff:</h3>
            {isDiffLoadFailed && (
              <span style={{ fontSize: '0.8125rem', color: 'var(--color-status-offline)', fontWeight: 600 }}>
                Diff 로드 실패로 인해 승인이 차단되었습니다
              </span>
            )}
          </div>

          <pre
            style={{
              padding: '14px',
              backgroundColor: '#0d1117',
              color: '#c9d1d9',
              borderRadius: 'var(--radius-md)',
              fontFamily: 'SFMono-Regular, Consolas, "Liberation Mono", Menlo, monospace',
              fontSize: '0.8125rem',
              overflowX: 'auto',
              maxHeight: '260px',
              lineHeight: 1.5,
              border: isDiffLoadFailed ? '1px solid var(--color-status-offline)' : '1px solid #30363d',
            }}
          >
            {hasDiff ? approval.unifiedDiff : '(Diff 데이터를 불러올 수 없습니다)'}
          </pre>
        </div>

        {/* Policy Reason & Two-Person Status */}
        <div
          style={{
            padding: '14px',
            backgroundColor: 'var(--color-bg-subtle)',
            borderRadius: 'var(--radius-md)',
            marginBottom: '24px',
            fontSize: '0.875rem',
          }}
        >
          <div style={{ marginBottom: '6px' }}>
            <strong>정책 엔진 재계산 근거:</strong> {approval.policyReason}
          </div>
          {approval.riskLevel === 'L3' && (
            <div style={{ display: 'flex', alignItems: 'center', gap: '8px', color: 'var(--color-text-secondary)' }}>
              <strong>Two-Person Rule 상태:</strong>
              {approval.firstApprovedBy ? (
                <span>1차 승인 완료 ({approval.firstApprovedBy}) · 2차 검토 대기</span>
              ) : (
                <span>1차 승인 대기 중</span>
              )}
            </div>
          )}
          {isSelfApprovalBlocked && (
            <div style={{ marginTop: '8px', color: 'var(--color-status-degraded)', fontWeight: 600 }}>
              자가 승인 차단: 1차 승인자는 동일 요청을 2차 승인할 수 없습니다 (상호 견제 원칙).
            </div>
          )}
        </div>

        {/* Action Buttons */}
        <div style={{ display: 'flex', justifyContent: 'flex-end', gap: '12px' }}>
          <Button
            variant="secondary"
            size="md"
            disabled={isExpired || isSubmitting}
            onClick={() => setShowRejectModal(true)}
          >
            반려
          </Button>

          <Button
            variant="primary"
            size="md"
            disabled={!canApprove}
            isLoading={isSubmitting}
            onClick={handleConfirmApprove}
          >
            {isWaitingSecondApproval ? '2차 최종 승인 확정' : '승인 확정'}
          </Button>
        </div>
      </div>

      {/* Reject Reason Modal */}
      {showRejectModal && (
        <div
          style={{
            position: 'fixed',
            inset: 0,
            backgroundColor: 'rgba(0, 0, 0, 0.5)',
            display: 'flex',
            alignItems: 'center',
            justifyContent: 'center',
            zIndex: 100,
          }}
        >
          <div
            style={{
              width: '100%',
              maxWidth: '480px',
              backgroundColor: 'var(--color-bg-surface)',
              borderRadius: 'var(--radius-lg)',
              padding: '24px',
              boxShadow: 'var(--shadow-lg)',
            }}
          >
            <h3 style={{ fontSize: '1.125rem', fontWeight: 600, marginBottom: '12px' }}>
              승인 반려 사유 입력
            </h3>
            <p style={{ fontSize: '0.875rem', color: 'var(--color-text-muted)', marginBottom: '16px' }}>
              반려 사유는 불변 감사 로그(Evidence)에 영구 기록됩니다.
            </p>
            <textarea
              value={rejectReason}
              onChange={(e) => setRejectReason(e.target.value)}
              placeholder="구체적인 반려 사유를 입력하세요 (예: 불필요한 엔드포인트 변경 감지)"
              rows={4}
              style={{
                width: '100%',
                padding: '10px',
                borderRadius: 'var(--radius-md)',
                border: '1px solid var(--color-border-strong)',
                backgroundColor: 'var(--color-bg-canvas)',
                color: 'var(--color-text-primary)',
                marginBottom: '16px',
                fontSize: '0.875rem',
                fontFamily: 'inherit',
              }}
            />
            <div style={{ display: 'flex', justifyContent: 'flex-end', gap: '8px' }}>
              <Button variant="ghost" size="sm" onClick={() => setShowRejectModal(false)}>
                취소
              </Button>
              <Button
                variant="danger"
                size="sm"
                disabled={!rejectReason.trim() || isSubmitting}
                isLoading={isSubmitting}
                onClick={handleConfirmReject}
              >
                반려 확인
              </Button>
            </div>
          </div>
        </div>
      )}
    </div>
  );
};
