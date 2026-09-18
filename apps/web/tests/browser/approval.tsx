import '../../src/index.css';
// Test-only entry; not referenced by the production index or bundle.
import { useEffect, useState } from 'react';
import { createRoot } from 'react-dom/client';
import { ApprovalCenter } from '../../src/features/approvals/ApprovalCenter';
import { setAuthToken } from '../../src/shared/api/client';
import { fetchObservedApprovals } from '../../src/shared/api/runApprovalObservation';
import { approveReviewed } from '../../src/shared/api/approvalReview';
import { decideApproval } from '../../src/shared/api/kernelMutations';
import type { ApprovalItem } from '../../src/contracts/types';
function Harness({ projectId, subject }: { projectId: string; subject: string }) {
  const [items, setItems] = useState<ApprovalItem[]>([]);
  const [result, setResult] = useState('');
  const refresh = async () => setItems(await fetchObservedApprovals(projectId));
  useEffect(() => { refresh().catch(() => setResult('load failed')); }, [projectId]);
  return <><output data-testid="mutation-result">{result}</output><ApprovalCenter approvals={items} currentUserId={subject}
    onApprove={async (id, _nonce, shown) => {
      try { await approveReviewed(items.find(a => a.id === id)!, shown); setResult('decision committed'); await refresh(); }
      catch { setResult('decision rejected'); }
    }} onReject={async id => { await decideApproval(items.find(a => a.id === id)!, 'reject'); await refresh(); }} /></>;
}
document.documentElement.setAttribute('data-theme', 'dark');
const root = createRoot(document.getElementById('root')!);
(window as any).mountApprovalTest = (input: { token: string; projectId: string; subject: string }) => {
  setAuthToken(input.token); root.render(<Harness key={input.subject} projectId={input.projectId} subject={input.subject} />);
};
