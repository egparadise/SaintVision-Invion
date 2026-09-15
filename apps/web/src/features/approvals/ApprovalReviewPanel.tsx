import { useEffect, useState } from 'react';
import { ApprovalDetail, type ApprovalDetailProps } from './ApprovalDetail';
import { fetchApprovalReview, reviewIdentity, reviewedAction, type ApprovalReview } from '@/shared/api/approvalReview';

export function ApprovalReviewPanel(props: ApprovalDetailProps) {
  const identity = reviewIdentity(props.approval);
  const [loaded, setLoaded] = useState<{ identity: string; review: ApprovalReview } | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [reload, setReload] = useState(0);
  useEffect(() => {
    let active = true;
    setLoaded(null); setError(null);
    fetchApprovalReview(props.approval).then(review => {
      if (active) setLoaded({ identity, review });
    }).catch(() => { if (active) setError('검토 내용을 확인하지 못했습니다. 승인이 보류됩니다.'); });
    return () => { active = false; };
  }, [identity, props.currentUserId, reload]);
  const review = loaded?.identity === identity ? loaded.review : null;
  const approval = review ? { ...props.approval, command: JSON.stringify(review.workload.command),
    riskLevel: review.riskLevel, workspaceId: review.workload.workspaceId,
    target: review.workload.workspaceId } : { ...props.approval, command: undefined, riskLevel: undefined };
  return <section>
    {error ? <p role="alert">{error} <button onClick={() => { setLoaded(null); setReload(n => n + 1); }}>다시 조회</button></p>
      : !review && <p role="status">승인할 작업 내용을 조회하고 있습니다.</p>}
    {review && <div>
      <h3>승인할 작업 스냅샷</h3>
      <p>명령은 인자 배열 그대로 표시됩니다. 작업·정책 결속은 서버가 검증합니다.</p>
      <pre style={{ whiteSpace: 'pre-wrap', overflowWrap: 'anywhere' }}>{JSON.stringify(review.workload, null, 2)}</pre>
      <p>정책 다이제스트: <code>{review.policyDigest}</code></p>
    </div>}
    <ApprovalDetail {...props} approval={approval} reviewedAction={review ? reviewedAction(review) : undefined} />
  </section>;
}
