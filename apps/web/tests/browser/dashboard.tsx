// Hosted HTTP replay only. No real session, identity, approvals or hardware actions.
import { useEffect, useState } from 'react';
import { createRoot } from 'react-dom/client';
import { Header } from '@/shared/ui/Header';
import { ClusterOverview } from '@/features/dashboard/ClusterOverview';
import { apiClient, setAuthToken } from '@/shared/api/client';
import { observedNode } from '@/shared/api/nodeObservation';
import { joinDashboardResources } from '@/shared/api/dashboardResources';
import type { NodeItem } from '@/contracts/types';
import type { NodePageResponse } from '@/contracts/node-page-response';
import type { DashboardNodeResourceObservation } from '@/contracts/dashboard-resources';

const project = 'prj_01M6NDBHVD2DZQ1Q38DCKN1XE3';
setAuthToken('isolated-hosted-replay-not-a-real-token');
function Replay() {
  const [nodes, setNodes] = useState<NodeItem[]>([]);
  const [error, setError] = useState<string | null>(null);
  useEffect(() => {
    const previous = new Map<string, DashboardNodeResourceObservation>();
    const controller = new AbortController();
    let busy = false;
    const poll = async () => {
      if (busy) return;
      busy = true;
      try {
        const page = await apiClient<NodePageResponse>(`/v1/projects/${project}/nodes`, { signal: controller.signal });
        const joined = await joinDashboardResources(page.items.map(observedNode), project, controller.signal, previous);
        if (!controller.signal.aborted) {
          joined.forEach(node => previous.set(node.id, node.resourceObservation!));
          setNodes(joined);
        }
      } catch (failure) { if (!controller.signal.aborted) setError(String(failure)); }
      finally { busy = false; }
    };
    void poll();
    const timer = setInterval(() => void poll(), 5000);
    return () => { clearInterval(timer); controller.abort(); };
  }, []);
  return <><Header currentTheme="light" onToggleTheme={() => {}} activeTab="dashboard" onSelectTab={() => {}}
    onlineNodesCount={nodes.filter(node => node.status === 'online').length} totalNodesCount={nodes.length} />
    {error && <p role="alert">{error}</p>}
    <ClusterOverview nodes={nodes} runs={[]} pendingApprovalsCount={0} onNavigate={() => {}}
      nodesState={nodes.length ? 'success' : 'loading'} /></>;
}
createRoot(document.getElementById('root')!).render(<Replay />);
