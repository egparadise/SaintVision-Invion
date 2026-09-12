import React, { useState, useEffect } from 'react';
import { Header } from '@/shared/ui/Header';
import { ClusterOverview } from '@/features/dashboard/ClusterOverview';
import { NodeList } from '@/features/nodes/NodeList';
import { NodeDetail } from '@/features/nodes/NodeDetail';
import { WorkspaceList } from '@/features/workspaces/WorkspaceList';
import { WorkspaceCreateModal } from '@/features/workspaces/WorkspaceCreateModal';
import { ExecutionResultView } from '@/features/workspaces/ExecutionResultView';
import { PlacementSimulator } from '@/features/placement/PlacementSimulator';
import { MonacoWorkspaceEditor } from '@/features/editor/MonacoWorkspaceEditor';
import { DistributedRecoveryView } from '@/features/recovery/DistributedRecoveryView';
import { AdminSecurityConsole } from '@/features/admin/AdminSecurityConsole';
import { NaturalLanguageRunView } from '@/features/agent/NaturalLanguageRunView';
import { ModelLineageView } from '@/features/mlops/ModelLineageView';
import { ReleaseCandidateView } from '@/features/release/ReleaseCandidateView';
import { IntranetDeploymentView } from '@/features/deployment/IntranetDeploymentView';
import { RunList } from '@/features/runs/RunList';
import { RunDetail } from '@/features/runs/RunDetail';
import { EvidenceViewer } from '@/features/evidence/EvidenceViewer';
import { ApprovalCenter } from '@/features/approvals/ApprovalCenter';
import { WebTerminal } from '@/features/terminal/WebTerminal';
import { Login } from '@/features/auth/Login';
import { DeveloperStudio } from '@/features/studio/DeveloperStudio';
import { NodeItem, RunItem, ApprovalItem, WorkspaceItem, ExecutionResultItem } from '@/contracts/types';
import { apiClient, clearAuthToken } from '@/shared/api/client';

// Mock 5 Nodes (Matching the project specification: 5 Windows/Linux nodes)
const INITIAL_NODES: NodeItem[] = [
  {
    id: 'nod_01JABCDEF01',
    hostname: 'Node-01-WinMain',
    status: 'online',
    os: 'windows',
    cpuCores: 16,
    cpuUsagePercent: 24,
    memoryTotalBytes: 64 * 1024 ** 3,
    memoryUsedBytes: 28 * 1024 ** 3,
    allocatableCores: 12,
    allocatableMemoryBytes: 36 * 1024 ** 3,
    schedulable: true,
    observationOnly: false,
    gpuName: 'NVIDIA RTX 4090',
    gpuCount: 1,
    gpuVramTotalBytes: 24 * 1024 ** 3,
    gpuVramUsedBytes: 8 * 1024 ** 3,
    storageTotalBytes: 2000 * 1024 ** 3,
    storageUsedBytes: 850 * 1024 ** 3,
    heartbeatAt: new Date().toISOString(),
  },
  {
    id: 'nod_01JABCDEF02',
    hostname: 'Node-02-WinWork',
    status: 'online',
    os: 'windows',
    cpuCores: 8,
    cpuUsagePercent: 42,
    memoryTotalBytes: 32 * 1024 ** 3,
    memoryUsedBytes: 19 * 1024 ** 3,
    allocatableCores: 4,
    allocatableMemoryBytes: 12 * 1024 ** 3,
    schedulable: true,
    observationOnly: false,
    gpuName: 'NVIDIA RTX 3080',
    gpuCount: 1,
    gpuVramTotalBytes: 10 * 1024 ** 3,
    gpuVramUsedBytes: 6 * 1024 ** 3,
    storageTotalBytes: 1000 * 1024 ** 3,
    storageUsedBytes: 420 * 1024 ** 3,
    heartbeatAt: new Date().toISOString(),
  },
  {
    id: 'nod_01JABCDEF03',
    hostname: 'Node-03-WinDev',
    status: 'online',
    os: 'windows',
    cpuCores: 8,
    cpuUsagePercent: 15,
    memoryTotalBytes: 32 * 1024 ** 3,
    memoryUsedBytes: 11 * 1024 ** 3,
    allocatableCores: 6,
    allocatableMemoryBytes: 20 * 1024 ** 3,
    schedulable: true,
    observationOnly: false,
    gpuCount: 0,
    storageTotalBytes: 1000 * 1024 ** 3,
    storageUsedBytes: 310 * 1024 ** 3,
    heartbeatAt: new Date().toISOString(),
  },
  {
    id: 'nod_01JABCDEF04',
    hostname: 'Node-04-LinuxBuild',
    status: 'online',
    os: 'linux',
    cpuCores: 16,
    cpuUsagePercent: 68,
    memoryTotalBytes: 64 * 1024 ** 3,
    memoryUsedBytes: 45 * 1024 ** 3,
    allocatableCores: 0,
    allocatableMemoryBytes: 0,
    observationOnly: true,
    schedulable: false,
    ipAddress: '192.168.45.225',
    gpuCount: 0,
    storageTotalBytes: 4000 * 1024 ** 3,
    storageUsedBytes: 1800 * 1024 ** 3,
    heartbeatAt: new Date().toISOString(),
  },
  {
    id: 'nod_01JABCDEF05',
    hostname: 'Node-05-LinuxTrain',
    status: 'online',
    os: 'linux',
    cpuCores: 12,
    cpuUsagePercent: 10,
    memoryTotalBytes: 32 * 1024 ** 3,
    memoryUsedBytes: 8 * 1024 ** 3,
    allocatableCores: 10,
    allocatableMemoryBytes: 24 * 1024 ** 3,
    schedulable: true,
    observationOnly: false,
    gpuName: 'NVIDIA A4000',
    gpuCount: 1,
    gpuVramTotalBytes: 16 * 1024 ** 3,
    gpuVramUsedBytes: 2 * 1024 ** 3,
    storageTotalBytes: 2000 * 1024 ** 3,
    storageUsedBytes: 600 * 1024 ** 3,
    heartbeatAt: new Date().toISOString(),
  },
];

const INITIAL_RUNS: RunItem[] = [
  {
    id: 'run_01JABCDE0001',
    projectId: 'prj_01JABCDE',
    workspaceId: 'wsp_01JABCDE',
    objective: 'SaintVision PACS Core 빌드 및 단위 테스트',
    state: 'running',
    requestedBy: 'usr_developer_01',
    createdAt: new Date(Date.now() - 1000 * 60 * 12).toISOString(),
    updatedAt: new Date().toISOString(),
  },
  {
    id: 'run_01JABCDE0002',
    projectId: 'prj_01JABCDE',
    workspaceId: 'wsp_01JABCDE',
    objective: '합성 데이터셋 전처리 및 로컬 분할 검증',
    state: 'awaiting_approval',
    requestedBy: 'usr_researcher_02',
    createdAt: new Date(Date.now() - 1000 * 60 * 25).toISOString(),
    updatedAt: new Date().toISOString(),
  },
  {
    id: 'run_01JABCDE0003',
    projectId: 'prj_01JABCDE',
    workspaceId: 'wsp_01JABCDE',
    objective: 'GPU 가속 모델 추론 벤치마크 (RTX 4090)',
    state: 'succeeded',
    requestedBy: 'usr_admin_01',
    createdAt: new Date(Date.now() - 1000 * 60 * 120).toISOString(),
    updatedAt: new Date().toISOString(),
  },
];

const DEMO_APPROVAL: ApprovalItem = {
  id: 'apr_01JXYZ987654',
  runId: 'run_01JABCDE0002',
  workspaceId: 'wsp_01JABCDE',
  nodeId: 'nod_01JABCDEF01',
  riskLevel: 'L2',
  target: 'Workspace [wsp-saint-pilot] on Node-01',
  command: 'git.deploy --release prod-v1.0.0',
  unifiedDiff: `--- a/config/environment.prod.json
+++ b/config/environment.prod.json
@@ -12,4 +12,5 @@
-  "GATEWAY_PORT": 8080,
+  "GATEWAY_PORT": 8443,
+  "TLS_STRICT": true,
+  "AUDIT_IMMUTABLE": true`,
  estimatedCostKrw: 3200,
  remainingBudgetKrw: 46800,
  blastRadius: 'workspace_isolated',
  rollbackPlan: undefined, // Demonstrating rollback warning badge
  status: 'pending',
  nonce: 'nonce_987654321',
  expiresAt: new Date(Date.now() + 1000 * 60 * 8).toISOString(), // 8 minutes remaining
  requestedBy: 'usr_requester_alice',
  policyReason: '외부 접근 포트 변경 및 TLS 암호화 활성화 정책에 따른 L2 승인 요구 (Rule #304)',
  createdAt: new Date().toISOString(),
};

const INITIAL_WORKSPACES: WorkspaceItem[] = [
  {
    id: 'wsp_01JABCDE001',
    projectId: 'prj_01JABCDE',
    name: 'pacs-core-build-sandbox',
    targetNodeId: 'nod_01JABCDEF01',
    isolationMode: 'process_sandbox',
    allowedPaths: ['./workspace', './data'],
    prohibitedPaths: ['/etc', 'C:\\Windows', '..', '/var/run'],
    cpuLimitCores: 8,
    memoryLimitBytes: 16 * 1024 ** 3,
    status: 'active',
    createdAt: new Date(Date.now() - 1000 * 60 * 60).toISOString(),
  },
  {
    id: 'wsp_01JABCDE002',
    projectId: 'prj_01JABCDE',
    name: 'dataset-preprocess-container',
    targetNodeId: 'nod_01JABCDEF04',
    isolationMode: 'container_isolated',
    allowedPaths: ['./dataset', './output'],
    prohibitedPaths: ['/etc', '..', '/sys'],
    cpuLimitCores: 8,
    memoryLimitBytes: 32 * 1024 ** 3,
    status: 'reclaimed',
    createdAt: new Date(Date.now() - 1000 * 60 * 180).toISOString(),
  },
];

const SAMPLE_EXECUTION: ExecutionResultItem = {
  runId: 'run_01JABCDE0001',
  workspaceId: 'wsp_01JABCDE001',
  command: 'pytest tests/test_contracts.py -v',
  exitCode: 0,
  state: 'succeeded',
  evidenceId: 'evi_01JABCDEF987654',
  resourceReclaimed: true,
  allowedEvents: [
    { timestamp: '2026-09-09T18:10:01Z', action: 'READ', path: './workspace/tests/test_contracts.py' },
    { timestamp: '2026-09-09T18:10:02Z', action: 'WRITE', path: './data/output_report.json' },
    { timestamp: '2026-09-09T18:10:03Z', action: 'NET_LISTEN', path: '127.0.0.1:8000' },
  ],
  deniedEvents: [
    {
      timestamp: '2026-09-09T18:10:01.4Z',
      action: 'ACCESS',
      path: '/etc/shadow',
      reason: 'BLOCKED: Prohibited system path access denied (ADR-005)',
    },
    {
      timestamp: '2026-09-09T18:10:01.8Z',
      action: 'TRAVERSE',
      path: '../config/keys.json',
      reason: 'BLOCKED: Path traversal ".." is strictly forbidden',
    },
  ],
  executedAt: new Date(Date.now() - 1000 * 60 * 15).toISOString(),
  completedAt: new Date(Date.now() - 1000 * 60 * 14).toISOString(),
};

export const App: React.FC = () => {
  const [theme, setTheme] = useState<'light' | 'dark'>('dark');
  const [activeTab, setActiveTab] = useState('dashboard');
  const [nodes, setNodes] = useState<NodeItem[]>(INITIAL_NODES);
  const [workspaces, setWorkspaces] = useState<WorkspaceItem[]>(INITIAL_WORKSPACES);
  const [isCreateModalOpen, setIsCreateModalOpen] = useState(false);
  const [selectedWorkspaceId, setSelectedWorkspaceId] = useState<string | null>(null);
  const [executionResult] = useState<ExecutionResultItem | null>(SAMPLE_EXECUTION);
  const [runs, setRuns] = useState<RunItem[]>(INITIAL_RUNS);
  const [selectedNodeId, setSelectedNodeId] = useState<string | null>(null);
  const [selectedRunId, setSelectedRunId] = useState<string | null>(null);
  const [evidenceRunId, setEvidenceRunId] = useState<string | null>(null);
  const [approvals, setApprovals] = useState<ApprovalItem[]>([DEMO_APPROVAL]);
  const [currentReviewerId, setCurrentReviewerId] = useState('usr_reviewer_02');
  const [nodeSimState, setNodeSimState] = useState<'normal' | 'loading' | 'empty' | 'error' | 'forbidden'>('normal');
  const [currentUser, setCurrentUser] = useState<{ id: string; name: string; role: string; tenantId?: string } | null>(null);

  // Integrated Developer Studio navigation state
  const [studioStep, setStudioStep] = useState<1 | 2 | 3 | 4>(1);
  const [studioNodeId, setStudioNodeId] = useState<string | null>(null);
  const [studioWorkspaceId, setStudioWorkspaceId] = useState<string | null>(null);
  const [studioRunId, setStudioRunId] = useState<string | null>(null);

  const handleOpenStudio = (opts: { step?: 1 | 2 | 3 | 4; nodeId?: string; workspaceId?: string; runId?: string }) => {
    if (opts.step) setStudioStep(opts.step);
    if (opts.nodeId) setStudioNodeId(opts.nodeId);
    if (opts.workspaceId) setStudioWorkspaceId(opts.workspaceId);
    if (opts.runId) setStudioRunId(opts.runId);
    setActiveTab('studio');
  };

  const fetchNodes = React.useCallback(async () => {
    try {
      const res = await apiClient<{ items: any[] }>('/v1/nodes');
      if (res.items?.length > 0) {
        setNodes(
          res.items.map((srvNode) => ({
            id: srvNode.nodeId || srvNode.id,
            hostname: srvNode.hostname,
            status: srvNode.status || 'online',
            os: srvNode.osType || srvNode.os || 'windows',
            cpuCores: srvNode.cpuCores || 8,
            cpuUsagePercent: srvNode.cpuUsagePercent ?? 20,
            memoryTotalBytes: srvNode.memoryTotalBytes || 32 * 1024 ** 3,
            memoryUsedBytes: srvNode.memoryUsedBytes || 16 * 1024 ** 3,
            allocatableCores: srvNode.allocatableCores,
            allocatableMemoryBytes: srvNode.allocatableMemoryBytes,
            observationOnly: srvNode.observationOnly ?? false,
            schedulable: srvNode.schedulable ?? true,
            isDraining: srvNode.isDraining ?? false,
            killSwitchEngaged: srvNode.killSwitchEngaged ?? false,
            ipAddress: srvNode.ipAddress,
            gpuName: srvNode.gpuName,
            gpuCount: srvNode.gpuCount || 0,
            gpuVramTotalBytes: srvNode.gpuVramTotalBytes || 0,
            gpuVramUsedBytes: srvNode.gpuVramUsedBytes || 0,
            storageTotalBytes: srvNode.storageTotalBytes || 1000 * 1024 ** 3,
            storageUsedBytes: srvNode.storageUsedBytes || 400 * 1024 ** 3,
            heartbeatAt: srvNode.lastHeartbeatAt || srvNode.heartbeatAt || new Date().toISOString(),
          }))
        );
      }
    } catch (err) {
      console.warn('Live /v1/nodes fetch fallback:', err);
    }
  }, []);

  const fetchRuns = React.useCallback(async () => {
    try {
      const res = await apiClient<{ items: RunItem[] }>('/v1/runs');
      if (res.items?.length > 0) {
        setRuns(res.items);
      }
    } catch (err) {
      console.warn('Live /v1/runs fetch fallback:', err);
    }
  }, []);

  const fetchApprovals = React.useCallback(async () => {
    try {
      const res = await apiClient<{ items: ApprovalItem[] }>('/v1/approvals');
      if (res.items?.length > 0) {
        setApprovals(res.items);
      }
    } catch (err) {
      console.warn('Live /v1/approvals fetch fallback:', err);
    }
  }, []);

  useEffect(() => {
    document.documentElement.setAttribute('data-theme', theme);
  }, [theme]);

  // Initial load from live backend endpoints
  useEffect(() => {
    fetchNodes();
    fetchRuns();
    fetchApprovals();
  }, [fetchNodes, fetchRuns, fetchApprovals]);

  // Periodic Telemetry Sync (Genuine Server Polling, Zero Synthetic Fluctuations)
  useEffect(() => {
    const interval = setInterval(() => {
      fetchNodes();
      fetchRuns();
      fetchApprovals();
    }, 5000);
    return () => clearInterval(interval);
  }, [fetchNodes, fetchRuns, fetchApprovals]);

  const toggleTheme = () => {
    setTheme((prev) => (prev === 'dark' ? 'light' : 'dark'));
  };

  const handleApprove = async (approvalId: string, nonce: string) => {
    try {
      const apprv = approvals.find((a) => a.id === approvalId);
      const prjId = apprv?.projectId || 'prj_01JABCDE';
      try {
        // 1. Attempt canonical kernel endpoint: /v1/projects/{project}/approvals/{approvalId}/decision
        await apiClient(`/v1/projects/${prjId}/approvals/${approvalId}/decision`, {
          method: 'POST',
          body: JSON.stringify({ decision: 'approve', nonce }),
        });
      } catch {
        // 2. Fallback to flat endpoint
        await apiClient(`/v1/approvals/${approvalId}/approve`, {
          method: 'POST',
          body: JSON.stringify({ nonce }),
        });
      }
      // Fetch fresh runs and approvals after server confirmed approval
      await Promise.all([fetchApprovals(), fetchRuns()]);
    } catch (err: any) {
      console.error('Backend approval API failed:', err);
      const errMsg = err?.detail || err?.message || '승인 처리 중 오류가 발생했습니다.';
      alert(`승인 처리 실패: ${errMsg}`);
      throw err;
    }
  };

  const handleReject = async (approvalId: string, reason: string) => {
    try {
      const apprv = approvals.find((a) => a.id === approvalId);
      const prjId = apprv?.projectId || 'prj_01JABCDE';
      try {
        // 1. Attempt canonical kernel endpoint: /v1/projects/{project}/approvals/{approvalId}/decision
        await apiClient(`/v1/projects/${prjId}/approvals/${approvalId}/decision`, {
          method: 'POST',
          body: JSON.stringify({ decision: 'reject', reason }),
        });
      } catch {
        // 2. Fallback to flat endpoint
        await apiClient(`/v1/approvals/${approvalId}/reject`, {
          method: 'POST',
          body: JSON.stringify({ reason }),
        });
      }
      // Fetch fresh runs and approvals after server confirmed rejection
      await Promise.all([fetchApprovals(), fetchRuns()]);
    } catch (err: any) {
      console.error('Backend approval reject API failed:', err);
      const errMsg = err?.detail || err?.message || '승인 반려 처리 중 오류가 발생했습니다.';
      alert(`승인 반려 실패: ${errMsg}`);
      throw err;
    }
  };

  const handleCancelRun = async (runId: string, reason: string) => {
    try {
      const targetRun = runs.find((r) => r.id === runId);
      const prjId = targetRun?.projectId || 'prj_01JABCDE';
      try {
        // 1. Attempt canonical kernel endpoint: /v1/projects/{project}/runs/{runId}/cancel
        await apiClient(`/v1/projects/${prjId}/runs/${runId}/cancel`, {
          method: 'POST',
          body: JSON.stringify({ reason }),
        });
      } catch {
        // 2. Fallback to flat endpoint
        await apiClient(`/v1/runs/${runId}/cancel`, {
          method: 'POST',
          body: JSON.stringify({ reason }),
        });
      }
      fetchRuns();
    } catch (err) {
      console.warn('Backend run cancellation API fallback:', err);
      setRuns((prev) =>
        prev.map((r) =>
          r.id === runId
            ? { ...r, state: 'cancelled', updatedAt: new Date().toISOString() }
            : r
        )
      );
    }
  };

  const selectedNode = nodes.find((n) => n.id === selectedNodeId);
  const selectedRun = runs.find((r) => r.id === selectedRunId);

  return (
    <div style={{ minHeight: '100vh', display: 'flex', flexDirection: 'column' }}>
      <Header
        currentTheme={theme}
        onToggleTheme={toggleTheme}
        onlineNodesCount={5}
        totalNodesCount={5}
        activeTab={activeTab}
        onSelectTab={(tab) => {
          setActiveTab(tab);
          setSelectedNodeId(null);
          setSelectedWorkspaceId(null);
          setSelectedRunId(null);
          setEvidenceRunId(null);
        }}
        currentUser={currentUser}
        onLogout={() => {
          clearAuthToken();
          setCurrentUser(null);
          setActiveTab('login');
        }}
      />

      <main style={{ flex: 1, padding: '32px 24px', maxWidth: '1200px', margin: '0 auto', width: '100%' }}>
        {/* Tab 1: Dashboard */}
        {activeTab === 'dashboard' && (
          <ClusterOverview
            nodes={nodes}
            runs={runs}
            pendingApprovalsCount={approvals.filter((a) => a.status === 'pending').length}
            onNavigate={(tab) => {
              setActiveTab(tab);
              setSelectedNodeId(null);
              setSelectedRunId(null);
            }}
          />
        )}

        {/* Tab 1.5: Integrated Developer Studio */}
        {activeTab === 'studio' && (
          <DeveloperStudio
            nodes={nodes}
            runs={runs}
            approvals={approvals}
            currentUser={currentUser}
            initialStep={studioStep}
            initialNodeId={studioNodeId}
            initialWorkspaceId={studioWorkspaceId}
            initialRunId={studioRunId}
            onNavigateTab={(tab, entityId) => {
              setActiveTab(tab as any);
              if (tab === 'runs' && entityId) setSelectedRunId(entityId);
              if (tab === 'nodes' && entityId) setSelectedNodeId(entityId);
            }}
            onRefreshRuns={fetchRuns}
            onApprove={handleApprove}
            onReject={handleReject}
          />
        )}

        {/* Tab 2: Nodes */}
        {activeTab === 'nodes' && (
          <div>
            {selectedNode ? (
              <NodeDetail
                node={selectedNode}
                onBack={() => setSelectedNodeId(null)}
                onOpenStudio={(nodeId) => handleOpenStudio({ step: 2, nodeId })}
              />
            ) : (
              <div>
                {/* 5-State Simulation Controls (FR-01 / FR-02) */}
                <div
                  style={{
                    display: 'flex',
                    alignItems: 'center',
                    gap: '8px',
                    marginBottom: '16px',
                    padding: '8px 12px',
                    backgroundColor: 'var(--color-bg-surface)',
                    borderRadius: 'var(--radius-md)',
                    border: '1px solid var(--color-border-subtle)',
                    fontSize: '0.8125rem',
                  }}
                >
                  <span style={{ fontWeight: 600, color: 'var(--color-text-muted)' }}>화면 상태 시뮬레이션:</span>
                  {(
                    [
                      { key: 'normal', label: '정상 (5대 온라인)' },
                      { key: 'loading', label: '로딩 중 (Skeleton)' },
                      { key: 'empty', label: '빈 상태 (Empty)' },
                      { key: 'error', label: '오류 (RFC 9457)' },
                      { key: 'forbidden', label: '권한 부족 (403)' },
                    ] as const
                  ).map(({ key, label }) => (
                    <button
                      key={key}
                      onClick={() => setNodeSimState(key)}
                      style={{
                        padding: '3px 8px',
                        borderRadius: 'var(--radius-sm)',
                        fontSize: '0.75rem',
                        cursor: 'pointer',
                        border: '1px solid var(--color-border-strong)',
                        backgroundColor: nodeSimState === key ? 'var(--color-brand-primary)' : 'var(--color-bg-subtle)',
                        color: nodeSimState === key ? '#ffffff' : 'var(--color-text-secondary)',
                      }}
                    >
                      {label}
                    </button>
                  ))}
                </div>

                <NodeList
                  nodes={nodeSimState === 'normal' ? nodes : []}
                  isLoading={nodeSimState === 'loading'}
                  isForbidden={nodeSimState === 'forbidden'}
                  error={
                    nodeSimState === 'error'
                      ? {
                          type: 'https://saintvision.invenio/problems/service-unavailable',
                          title: 'Node Registry 통신 실패',
                          status: 503,
                          detail: '백엔드 노드 레지스트리 서비스 응답이 지연되고 있습니다. 잠시 후 재시도하십시오.',
                          code: 'RES-NODE-TIMEOUT',
                          category: 'RES',
                          retryable: true,
                          traceId: 'trace_simulation_987654',
                        }
                      : null
                  }
                  onRefresh={() => setNodeSimState('normal')}
                  onSelectNode={(id) => setSelectedNodeId(id)}
                  onOpenStudio={(nodeId) => handleOpenStudio({ step: 2, nodeId })}
                />
              </div>
            )}
          </div>
        )}

        {/* Tab 2.5: Workspaces (S03-FE) */}
        {activeTab === 'workspaces' && (
          <div>
            {selectedWorkspaceId && executionResult ? (
              <ExecutionResultView
                result={executionResult}
                onBack={() => setSelectedWorkspaceId(null)}
                onViewEvidence={(evidenceId) => {
                  setActiveTab('runs');
                  setEvidenceRunId(evidenceId);
                }}
              />
            ) : (
              <WorkspaceList
                workspaces={workspaces}
                nodes={nodes}
                onCreateWorkspace={() => setIsCreateModalOpen(true)}
                onSelectWorkspace={(wspId) => setSelectedWorkspaceId(wspId)}
                onOpenStudio={(wspId) => handleOpenStudio({ step: 1, workspaceId: wspId })}
              />
            )}

            <WorkspaceCreateModal
              projectId="prj_01JABCDE"
              availableNodes={nodes}
              isOpen={isCreateModalOpen}
              onClose={() => setIsCreateModalOpen(false)}
              onCreate={async (newWsp) => {
                const created: WorkspaceItem = {
                  ...newWsp,
                  id: `wsp_${Date.now().toString(36)}`,
                  createdAt: new Date().toISOString(),
                };
                setWorkspaces((prev) => [created, ...prev]);
              }}
            />
          </div>
        )}

        {/* Tab 2.5: Development Workspace Editor (S06-FE) */}
        {activeTab === 'editor' && (
          <MonacoWorkspaceEditor
            workspaceId={selectedWorkspaceId || 'wsp_01JABCDE'}
            projectId="prj_01JABCDE"
          />
        )}

        {/* Tab 2.7: Resource Placement Simulator (S05-FE) */}
        {activeTab === 'placement' && (
          <PlacementSimulator nodes={nodes} />
        )}

        {/* Tab 2.8: Distributed Recovery & Resilience (S07-FE) */}
        {activeTab === 'recovery' && (
          <DistributedRecoveryView nodes={nodes} />
        )}

        {/* Tab 2.9: Admin Security & Audit Console (S08-FE) */}
        {activeTab === 'admin' && (
          <AdminSecurityConsole nodes={nodes} onRefreshNodes={fetchNodes} />
        )}

        {/* Tab 2.10: Natural Language Requester & Bounded Agent (S09-FE) */}
        {activeTab === 'agent' && (
          <NaturalLanguageRunView />
        )}

        {/* Tab 2.11: Model Lineage & Multi-LLM Conformance (S10-FE) */}
        {activeTab === 'mlops' && (
          <ModelLineageView />
        )}

        {/* Tab 2.12: Release Candidate & Web Rollback (S11-FE) */}
        {activeTab === 'release' && (
          <ReleaseCandidateView />
        )}

        {/* Tab 2.13: Intranet HTTPS Deployment & Operator Training (S12-FE) */}
        {activeTab === 'deployment' && (
          <IntranetDeploymentView clusterNodes={nodes} />
        )}

        {/* Tab 3: Runs & Evidence */}
        {activeTab === 'runs' && (
          <div>
            {evidenceRunId ? (
              <EvidenceViewer runId={evidenceRunId} onBack={() => setEvidenceRunId(null)} />
            ) : selectedRun ? (
              <RunDetail
                run={selectedRun}
                onBack={() => setSelectedRunId(null)}
                onNavigateEvidence={(id) => setEvidenceRunId(id)}
                onNavigateApproval={() => setActiveTab('approvals')}
                onNavigateRun={(id) => setSelectedRunId(id)}
                onCancelRun={handleCancelRun}
                onRefreshRun={fetchRuns}
                onOpenStudio={(runId) => handleOpenStudio({ step: 4, runId })}
              />
            ) : (
              <RunList
                runs={runs}
                isLoading={false}
                onSelectRun={(id) => setSelectedRunId(id)}
                onCreateRun={() => alert('새 Run 요청 폼')}
              />
            )}
          </div>
        )}

        {/* Tab 4: Approvals (S04-FE) */}
        {activeTab === 'approvals' && (
          <ApprovalCenter
            approvals={approvals}
            currentUserId={currentReviewerId}
            onChangeUser={(newId) => setCurrentReviewerId(newId)}
            onApprove={handleApprove}
            onReject={handleReject}
          />
        )}

        {/* Tab 5: Terminal */}
        {activeTab === 'terminal' && (
          <div>
            <div style={{ marginBottom: '20px' }}>
              <h2 style={{ fontSize: '1.25rem', fontWeight: 600 }}>격리 웹 터미널 (xterm.js + WebSocket)</h2>
              <p style={{ fontSize: '0.875rem', color: 'var(--color-text-muted)', marginTop: '4px' }}>
                30초 1회용 티켓으로 인증된 PTY 양방향 터미널 세션입니다. (접근성 대체 텍스트 뷰 지원)
              </p>
            </div>
            <WebTerminal workspaceId="wsp-saint-pilot" sessionId="sid_terminal_01" />
          </div>
        )}

        {/* Tab 6: Login */}
        {activeTab === 'login' && (
          <Login
            onLoginSuccess={(user) => {
              setCurrentUser(user);
              setCurrentReviewerId(user.id);
              setActiveTab('dashboard');
            }}
          />
        )}
      </main>

      <footer
        style={{
          padding: '16px 24px',
          borderTop: '1px solid var(--color-border-subtle)',
          textAlign: 'center',
          fontSize: '0.75rem',
          color: 'var(--color-text-muted)',
          backgroundColor: 'var(--color-bg-surface)',
        }}
      >
        SaintVision-Invion Intranet Web Portal · Owned by Gemini (Antigravity) · Strict Governance L0~L3
      </footer>
    </div>
  );
};
