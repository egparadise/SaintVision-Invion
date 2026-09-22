import { DesktopShell } from '@/features/desktop/DesktopShell';
import { ResourceExplorer } from '@/features/desktop/ResourceExplorer';
import { approveReviewed, type ReviewedAction } from '@/shared/api/approvalReview';
import React, { useState, useEffect, useRef } from 'react';
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
import { NodeItem, RunItem, ApprovalItem, WorkspaceItem, ExecutionResultItem, ProjectItem } from '@/contracts/types';
import { apiClient, clearAuthToken } from '@/shared/api/client';
import type { NodePageResponse } from '@/contracts/node-page-response';
import type { WorkspaceSummaryResponse } from '@/contracts/project-workspaces-response';
import { fetchProjects, fetchProjectWorkspaces, createProjectWorkspace } from '@/shared/api/projectObservation';
import { fetchObservedRuns, fetchObservedApprovals } from '@/shared/api/runApprovalObservation';
import { observedNode } from '@/shared/api/nodeObservation';
import { decideApproval, cancelKernelRun } from '@/shared/api/kernelMutations';
import { getNodeResourceUsage } from '@/features/desktop/fabricControlApi';
import type { ObservedNodeResourceUsage } from '@/contracts/kernel-observation';

function toWorkspaceItem(w: WorkspaceSummaryResponse): WorkspaceItem {
  return {
    id: w.workspaceId,
    projectId: w.projectId,
    name: w.name,
    targetNodeId: w.nodeId ?? null,
    isolationMode: 'process_sandbox',
    allowedPaths: ['./workspace'],
    prohibitedPaths: ['/etc', 'C:\\Windows', '..'],
    cpuLimitCores: 4,
    memoryLimitBytes: 8 * 1024 ** 3,
    status: w.status,
    createdAt: w.createdAt,
  };
}

export const App: React.FC = () => {
  const [desktop, setDesktop] = useState(false);
  const [theme, setTheme] = useState<'light' | 'dark'>('dark');
  const [activeTab, setActiveTab] = useState('login');
  const [nodes, setNodes] = useState<NodeItem[]>([]);
  const [workspaces, setWorkspaces] = useState<WorkspaceItem[]>([]);
  const [isCreateModalOpen, setIsCreateModalOpen] = useState(false);
  const [selectedWorkspaceId, setSelectedWorkspaceId] = useState<string | null>(null);
  const [executionResult] = useState<ExecutionResultItem | null>(null);
  const [runs, setRuns] = useState<RunItem[]>([]);
  const [selectedNodeId, setSelectedNodeId] = useState<string | null>(null);
  const [selectedRunId, setSelectedRunId] = useState<string | null>(null);
  const [evidenceRunId, setEvidenceRunId] = useState<string | null>(null);
  const [approvals, setApprovals] = useState<ApprovalItem[]>([]);
  const [approvalsState, setApprovalsState] = useState<'idle' | 'loading' | 'success' | 'error'>('idle');
  const [runsState, setRunsState] = useState<'idle' | 'loading' | 'success' | 'error'>('idle');
  const [lastNodesFetchedAt, setLastNodesFetchedAt] = useState<Date | null>(null);
  const [lastApprovalsFetchedAt, setLastApprovalsFetchedAt] = useState<Date | null>(null);
  const [lastRunsFetchedAt, setLastRunsFetchedAt] = useState<Date | null>(null);
  const [runError, setRunError] = useState<string | null>(null);
  const [approvalError, setApprovalError] = useState<string | null>(null);
  const [nodeError, setNodeError] = useState<string | null>(null);
  const [nodesState, setNodesState] = useState<'idle' | 'loading' | 'success' | 'error'>('idle');
  const [workspaceError, setWorkspaceError] = useState<string | null>(null);
  const [workspacesState, setWorkspacesState] = useState<'idle' | 'loading' | 'success' | 'error'>('idle');
  const activeProject = useRef('');
  const runRequest = useRef(0);
  const approvalRequest = useRef(0);
  const workspaceRequest = useRef(0);
  const [nodeSimState, setNodeSimState] = useState<'normal' | 'loading' | 'empty' | 'error' | 'forbidden'>('normal');
  const [currentUser, setCurrentUser] = useState<{ id: string; name: string; role: string; tenantId?: string } | null>(null);

  const [projects, setProjects] = useState<ProjectItem[]>([]);
  const [projectId, setProjectId] = useState('');
  const [projectError, setProjectError] = useState<string | null>(null);
  const [nodeResourceUsage, setNodeResourceUsage] = useState<ObservedNodeResourceUsage | null>(null);
  const [nodeResourceUsageState, setNodeResourceUsageState] = useState<'idle' | 'unselected' | 'loading' | 'success' | 'error'>('idle');
  const [nodeResourceUsageError, setNodeResourceUsageError] = useState<string | null>(null);
  const scopeRef = useRef(0);
  const selectedProject = projects.find(p => p.id === projectId);
  const chooseProject = (id: string) => {
    scopeRef.current += 1;
    activeProject.current = id;
    setRunError(null); setApprovalError(null); setWorkspaceError(null);
    setProjectId(id); setRuns([]); setApprovals([]); setWorkspaces([]);
    setSelectedNodeId(null); setNodeResourceUsage(null); setNodeResourceUsageState('idle'); setNodeResourceUsageError(null);
    setSelectedRunId(null); setSelectedWorkspaceId(null); setEvidenceRunId(null);
    setStudioWorkspaceId(null); setStudioRunId(null); setStudioNodeId(null); setStudioStep(1);
  };
  useEffect(() => {
    let active = true;
    setProjects([]); chooseProject(''); setProjectError(null);
    if (currentUser) fetchProjects().then(items => {
      if (active) { setProjects(items); chooseProject(items[0]?.id ?? ''); }
    }).catch(() => { if (active) setProjectError('프로젝트 목록을 확인하지 못했습니다.'); });
    return () => { active = false; };
  }, [currentUser]);

  useEffect(() => {
    let active = true;
    if (!selectedNodeId) {
      setNodeResourceUsage(null);
      setNodeResourceUsageState('idle');
      setNodeResourceUsageError(null);
      return;
    }
    if (!projectId) {
      setNodeResourceUsage(null);
      setNodeResourceUsageState('unselected');
      setNodeResourceUsageError(null);
      return;
    }
    setNodeResourceUsageState('loading');
    setNodeResourceUsageError(null);
    getNodeResourceUsage(selectedNodeId, projectId)
      .then((usage) => {
        if (active) {
          setNodeResourceUsage(usage);
          setNodeResourceUsageState('success');
          setNodeResourceUsageError(null);
        }
      })
      .catch((err) => {
        if (active) {
          setNodeResourceUsage(null);
          setNodeResourceUsageState('error');
          setNodeResourceUsageError(
            err instanceof Error ? err.message : '노드 자원 사용량을 조회하지 못했습니다.'
          );
        }
      });
    return () => {
      active = false;
    };
  }, [selectedNodeId, projectId]);

  // Integrated Developer Studio navigation state
  const [studioStep, setStudioStep] = useState<1 | 2 | 3 | 4>(1);
  const [studioNodeId, setStudioNodeId] = useState<string | null>(null);
  const [studioWorkspaceId, setStudioWorkspaceId] = useState<string | null>(null);
  const [studioRunId, setStudioRunId] = useState<string | null>(null);
  const [actionError, setActionError] = useState<string | null>(null);

  const handleOpenStudio = (opts: { step?: 1 | 2 | 3 | 4; nodeId?: string; workspaceId?: string; runId?: string }) => {
    if (opts.step) setStudioStep(opts.step);
    if (opts.nodeId) setStudioNodeId(opts.nodeId);
    if (opts.workspaceId) setStudioWorkspaceId(opts.workspaceId);
    if (opts.runId) setStudioRunId(opts.runId);
    setActiveTab('studio');
  };

  const fetchNodes = React.useCallback(async () => {
    if (!currentUser) {
      setNodesState('idle');
      return;
    }
    const scope = scopeRef.current;
    setNodesState('loading');
    setNodeError(null);
    try {
      const page = await apiClient<NodePageResponse>('/v1/nodes');
      if (scopeRef.current === scope) {
        setNodes(page.items.map(observedNode));
        setNodesState('success');
        setLastNodesFetchedAt(new Date());
        setNodeError(null);
      }
    } catch (err: any) {
      if (scopeRef.current === scope) {
        setNodes([]);
        setNodesState('error');
        setNodeError(err?.message || '노드 목록을 확인하지 못했습니다.');
      }
    }
  }, [currentUser]);

  const fetchRuns = React.useCallback(async () => {
    if (!currentUser || !projectId || activeProject.current !== projectId) return;
    const scope = scopeRef.current;
    const request = ++runRequest.current;
    setRunsState('loading');
    try {
      const items = await fetchObservedRuns(projectId);
      if (scopeRef.current === scope && request === runRequest.current) {
        setRuns(items);
        setRunsState('success');
        setLastRunsFetchedAt(new Date());
        setRunError(null);
      }
    } catch {
      if (scopeRef.current === scope && request === runRequest.current) {
        setRuns([]);
        setRunsState('error');
        setRunError('Run 목록을 확인하지 못했습니다.');
      }
    }
  }, [currentUser, projectId]);

  const fetchApprovals = React.useCallback(async () => {
    if (!currentUser || !projectId || activeProject.current !== projectId) return;
    const scope = scopeRef.current;
    const request = ++approvalRequest.current;
    setApprovalsState('loading');
    try {
      const items = await fetchObservedApprovals(projectId);
      if (scopeRef.current === scope && request === approvalRequest.current) {
        setApprovals(items);
        setApprovalsState('success');
        setLastApprovalsFetchedAt(new Date());
        setApprovalError(null);
      }
    } catch {
      if (scopeRef.current === scope && request === approvalRequest.current) {
        setApprovals([]);
        setApprovalsState('error');
        setApprovalError('승인 목록을 확인하지 못했습니다.');
      }
    }
  }, [currentUser, projectId]);

  const fetchWorkspaces = React.useCallback(async () => {
    if (!currentUser || !projectId || activeProject.current !== projectId) {
      setWorkspacesState('idle');
      return;
    }
    const scope = scopeRef.current;
    const request = ++workspaceRequest.current;
    setWorkspacesState('loading');
    setWorkspaceError(null);
    try {
      const items = await fetchProjectWorkspaces(projectId);
      if (scopeRef.current === scope && request === workspaceRequest.current) {
        setWorkspaces(items.map(toWorkspaceItem));
        setWorkspacesState('success');
        setWorkspaceError(null);
      }
    } catch (err: any) {
      if (scopeRef.current === scope && request === workspaceRequest.current) {
        setWorkspaces([]);
        setWorkspacesState('error');
        setWorkspaceError(err?.message || 'Workspace 목록을 확인하지 못했습니다.');
      }
    }
  }, [currentUser, projectId]);

  useEffect(() => {
    document.documentElement.setAttribute('data-theme', theme);
  }, [theme]);

  // Initial load from live backend endpoints
  useEffect(() => {
    fetchNodes();
    fetchRuns();
    fetchApprovals();
    fetchWorkspaces();
  }, [fetchNodes, fetchRuns, fetchApprovals, fetchWorkspaces]);

  // Periodic Telemetry Sync (Genuine Server Polling, Zero Synthetic Fluctuations)
  useEffect(() => {
    const interval = setInterval(() => {
      fetchNodes();
      fetchRuns();
      fetchApprovals();
      fetchWorkspaces();
    }, 5000);
    return () => clearInterval(interval);
  }, [fetchNodes, fetchRuns, fetchApprovals, fetchWorkspaces]);

  const toggleTheme = () => {
    setTheme((prev) => (prev === 'dark' ? 'light' : 'dark'));
  };

  const handleApprove = async (approvalId: string, _nonce: string, shown?: ReviewedAction) => {
    try {
      setActionError(null);
      const approval = approvals.find((a) => a.id === approvalId);
      if (!approval || activeProject.current !== approval.projectId) throw new Error('승인 안건을 다시 선택하세요.');
      await approveReviewed(approval, shown);
      // Fetch fresh runs and approvals after server confirmed approval
      await Promise.all([fetchApprovals(), fetchRuns()]);
    } catch (err: any) {
      console.error('Backend approval API failed:', err);
      const errMsg = err?.problem?.detail || err?.detail || err?.message || '승인 처리 중 오류가 발생했습니다.';
      setActionError(`승인 처리 실패: ${errMsg}`);
      throw err;
    }
  };

  const handleReject = async (approvalId: string, _reason: string) => {
    try {
      setActionError(null);
      const approval = approvals.find((a) => a.id === approvalId);
      if (!approval) throw new Error('승인 요청을 새로고침하세요.');
      await decideApproval(approval, 'reject');
      // Fetch fresh runs and approvals after server confirmed rejection
      await Promise.all([fetchApprovals(), fetchRuns()]);
    } catch (err: any) {
      console.error('Backend approval reject API failed:', err);
      const errMsg = err?.problem?.detail || err?.detail || err?.message || '승인 반려 처리 중 오류가 발생했습니다.';
      setActionError(`승인 반려 실패: ${errMsg}`);
      throw err;
    }
  };

  const handleCancelRun = async (runId: string, _reason: string) => {
    try {
      setActionError(null);
      const targetRun = runs.find((r) => r.id === runId);
      await cancelKernelRun(targetRun?.projectId, runId);
      await fetchRuns();
    } catch (err) {
      console.warn('Backend run cancellation API error:', err);
      setActionError('취소를 확인하지 못했습니다. 실행 상태를 새로고침한 뒤 확인하세요.');
      throw err;
    }
  };

  const selectedNode = nodes.find((n) => n.id === selectedNodeId);
  const selectedRun = runs.find((r) => r.id === selectedRunId);

  const globalErrorBanner = actionError ? (
    <div
      role="alert"
      data-testid="app-global-action-error"
      style={{
        padding: '10px 16px',
        backgroundColor: '#fee2e2',
        color: '#991b1b',
        borderBottom: '1px solid #f87171',
        display: 'flex',
        alignItems: 'center',
        justifyContent: 'space-between',
        fontWeight: 500,
        fontSize: '0.875rem',
        zIndex: 1000,
      }}
    >
      <span>{actionError}</span>
      <button
        type="button"
        data-testid="app-global-action-error-dismiss"
        onClick={() => setActionError(null)}
        style={{
          marginLeft: '12px',
          padding: '2px 8px',
          border: '1px solid #dc2626',
          borderRadius: '4px',
          backgroundColor: '#ffffff',
          color: '#991b1b',
          cursor: 'pointer',
          fontSize: '0.75rem',
        }}
      >
        닫기
      </button>
    </div>
  ) : null;

  if (!currentUser) return <Login onLoginSuccess={user => { setCurrentUser(user); setActiveTab('dashboard'); }} />;

  if (desktop && currentUser && projectId) return (
    <>
      {globalErrorBanner}
      <DesktopShell
        key={`${currentUser.tenantId}:${currentUser.id}:${projectId}`} projectId={projectId}
        tenantId={currentUser.tenantId}
        nodes={nodes} runs={runs} approvals={approvals} workspaces={workspaces}
        currentReviewerId={currentUser.id} onRefreshNodes={fetchNodes}
        onApprove={handleApprove} onReject={handleReject} onChangeUser={() => {}}
        onSwitchToPortalView={() => setDesktop(false)} currentTheme={theme}
        onToggleTheme={() => setTheme(theme === 'dark' ? 'light' : 'dark')} />
    </>
  );

  return (
    <div style={{ minHeight: '100vh', display: 'flex', flexDirection: 'column' }}>
      {globalErrorBanner}
      <Header
        onSwitchToDesktop={currentUser && projectId ? () => setDesktop(true) : undefined}
        currentTheme={theme}
        onToggleTheme={toggleTheme}
        onlineNodesCount={nodes.filter((n) => n.status === 'online').length}
        totalNodesCount={nodes.length}
        activeTab={activeTab}
        onSelectTab={(tab) => {
          setActiveTab(tab);
          setSelectedNodeId(null);
          setNodeResourceUsage(null);
          setNodeResourceUsageState('idle');
          setNodeResourceUsageError(null);
          setSelectedWorkspaceId(null);
          setSelectedRunId(null);
          setEvidenceRunId(null);
        }}
        currentUser={currentUser}
        onLogout={() => {
          clearAuthToken();
          setNodes([]); chooseProject(''); setProjects([]);
          setCurrentUser(null);
          setActiveTab('login');
        }}
      />

      <main style={{ flex: 1, padding: '32px 24px', maxWidth: '1200px', margin: '0 auto', width: '100%' }}>
        {currentUser && <label>프로젝트 <select aria-label="프로젝트" value={projectId} onChange={e => chooseProject(e.target.value)}>
          <option value="">프로젝트 선택</option>
          {projects.map(project => <option key={project.id} value={project.id}>{project.name}</option>)}
        </select>{projectError && <span role="alert">{projectError}</span>}</label>}
        {nodeError && <p role="alert" data-testid="app-node-error">{nodeError}</p>}
        {workspaceError && <p role="alert" data-testid="app-workspace-error">{workspaceError}</p>}
        {runError && <p role="alert">{runError}</p>}
        {approvalError && <p role="alert">{approvalError}</p>}
        {/* Tab 1: Dashboard */}
        {activeTab === 'dashboard' && (
          <ClusterOverview
            nodes={nodes}
            runs={runs}
            pendingApprovalsCount={approvals.filter((a) => a.status === 'pending').length}
            nodesState={nodesState}
            nodeError={nodeError}
            lastFetchedAt={lastNodesFetchedAt}
            onRefresh={fetchNodes}
            onNavigate={(tab) => {
              setActiveTab(tab);
              setSelectedNodeId(null);
              setSelectedRunId(null);
            }}
          />
        )}

        {activeTab === 'studio' && !selectedProject && <p role="status">프로젝트를 선택하면 Studio를 열 수 있습니다.</p>}
        {/* Tab 1.5: Integrated Developer Studio */}
        {activeTab === 'studio' && selectedProject && (
          <DeveloperStudio
            key={projectId}
            project={selectedProject}
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
                resourceUsage={nodeResourceUsage ?? undefined}
                resourceUsageState={nodeResourceUsageState}
                resourceUsageError={nodeResourceUsageError}
                onBack={() => {
                  setSelectedNodeId(null);
                  setNodeResourceUsage(null);
                  setNodeResourceUsageState('idle');
                  setNodeResourceUsageError(null);
                }}
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
                  isLoading={nodeSimState === 'loading' || nodesState === 'loading'}
                  isForbidden={nodeSimState === 'forbidden'}
                  error={
                    nodeSimState === 'error'
                      ? {
                          type: 'about:blank',
                          title: 'Node Registry 통신 실패',
                          status: 503,
                          detail: '백엔드 노드 레지스트리 서비스 응답이 지연되고 있습니다. 잠시 후 재시도하십시오.',
                          code: 'RES-0001',
                          category: 'RES',
                          retryable: true,
                          traceId: '0123456789abcdef0123456789abcdef',
                          causeRef: null,
                          evidenceId: null,
                        }
                      : nodeError
                      ? {
                          type: 'about:blank',
                          title: '노드 레지스트리 조회 실패',
                          status: 500,
                          detail: nodeError,
                          code: 'RES-0001',
                          category: 'RES',
                          retryable: true,
                          traceId: 'err-fetch-nodes',
                          causeRef: null,
                          evidenceId: null,
                        }
                      : null
                  }
                  onRefresh={() => {
                    setNodeSimState('normal');
                    fetchNodes();
                  }}
                  onSelectNode={(id) => setSelectedNodeId(id)}
                  onOpenStudio={(nodeId) => handleOpenStudio({ step: 2, nodeId })}
                />
              </div>
            )}
          </div>
        )}

        {/* Tab 2.1: Virtual Fabric & Control Plane Explorer (CX-01) */}
        {activeTab === 'fabric' && (
          <ResourceExplorer
            nodes={nodes}
            nodesState={nodesState}
            nodesError={nodeError}
            onRetryNodes={fetchNodes}
            tenantId={currentUser?.tenantId}
            lastFetchedAt={lastNodesFetchedAt}
            onSelectNode={(id) => {
              setSelectedNodeId(id);
              setActiveTab('nodes');
            }}
            onOpenTerminal={() => {
              setActiveTab('terminal');
            }}
          />
        )}

        {/* Tab 2.5: Workspaces (S03-FE) */}
        {activeTab === 'workspaces' && (
          <div>
            {workspaceError && (
              <div
                role="alert"
                data-testid="workspace-error-banner"
                style={{
                  padding: '12px 16px',
                  backgroundColor: 'rgba(239, 68, 68, 0.1)',
                  border: '1px solid #ef4444',
                  borderRadius: 'var(--radius-md)',
                  color: '#fca5a5',
                  fontSize: '0.875rem',
                  marginBottom: '16px',
                }}
              >
                ⚠️ {workspaceError}
              </div>
            )}
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
                isLoading={workspacesState === 'loading'}
                onCreateWorkspace={() => setIsCreateModalOpen(true)}
                onSelectWorkspace={(wspId) => setSelectedWorkspaceId(wspId)}
                onOpenStudio={(wspId) => handleOpenStudio({ step: 1, workspaceId: wspId })}
              />
            )}

            <WorkspaceCreateModal
              projectId={projectId}
              isOpen={isCreateModalOpen}
              onClose={() => setIsCreateModalOpen(false)}
              onCreate={async (newWsp) => {
                try {
                  const created = await createProjectWorkspace(projectId, newWsp.name);
                  await fetchWorkspaces();
                  setSelectedWorkspaceId(created.workspaceId);
                } catch (err: any) {
                  setWorkspaceError(err?.message || 'Workspace 생성 실패');
                  throw err;
                }
              }}
            />
          </div>
        )}

        {/* Tab 2.5: Development Workspace Editor (S06-FE) */}
        {activeTab === 'editor' && (
          <MonacoWorkspaceEditor
            workspaceId={selectedWorkspaceId || ''}
            projectId={projectId}
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
          <AdminSecurityConsole nodes={nodes} onRefreshNodes={fetchNodes} currentUser={currentUser} />
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
          <IntranetDeploymentView clusterNodes={nodes} currentUser={currentUser} />
        )}

        {/* Tab 3: Runs & Evidence */}
        {activeTab === 'runs' && (
          <div>
            {evidenceRunId ? (
              <EvidenceViewer runId={evidenceRunId} projectId={projectId} onBack={() => setEvidenceRunId(null)} />
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
                isLoading={runsState === 'loading'}
                onSelectRun={(id) => setSelectedRunId(id)}
                onCreateRun={() => handleOpenStudio({ step: 3 })}
                runsState={runsState}
                runError={runError}
                lastFetchedAt={lastRunsFetchedAt}
                onRefresh={fetchRuns}
              />
            )}
          </div>
        )}

        {/* Tab 4: Approvals (S04-FE) */}
        {activeTab === 'approvals' && (
          <ApprovalCenter
            key={`${currentUser?.tenantId}:${currentUser?.id}:${projectId}`}
            approvals={approvals}
            currentUserId={currentUser?.id ?? ''}
            onApprove={handleApprove}
            onReject={handleReject}
            approvalsState={approvalsState}
            approvalError={approvalError}
            lastFetchedAt={lastApprovalsFetchedAt}
            onRefresh={fetchApprovals}
          />
        )}

        {/* Tab 5: Terminal */}
        {activeTab === 'terminal' && (() => {
          const currentWorkspace = workspaces.find((w) => w.id === selectedWorkspaceId) || workspaces[0];
          return (
            <div>
              <div style={{ marginBottom: '20px' }}>
                <h2 style={{ fontSize: '1.25rem', fontWeight: 600 }}>격리 웹 터미널 (xterm.js + WebSocket)</h2>
                <p style={{ fontSize: '0.875rem', color: 'var(--color-text-muted)', marginTop: '4px' }}>
                  30초 1회용 티켓으로 인증된 PTY 양방향 터미널 세션입니다. (접근성 대체 텍스트 뷰 지원)
                </p>
              </div>

              {!currentWorkspace ? (
                <div
                  id="terminal-no-workspace-notice"
                  role="alert"
                  data-testid="terminal-no-workspace-notice"
                  style={{
                    padding: '16px',
                    backgroundColor: 'var(--color-bg-surface)',
                    border: '1px solid var(--color-border-subtle)',
                    borderRadius: '6px',
                    color: 'var(--color-text-muted)',
                    lineHeight: '1.4',
                  }}
                >
                  <div>⚠️ 등록되거나 선택된 워크스페이스가 없습니다. 터미널 세션을 시작할 수 없습니다. (유효 워크스페이스 필요)</div>
                  <div style={{ marginTop: '4px', fontSize: '0.75rem', color: '#fed7aa' }}>
                    👉 <strong>[사용자 조치 필요]</strong>: 상단 작업 공간 메뉴에서 워크스페이스를 선택하거나 새로 생성하십시오.
                  </div>
                </div>
              ) : (
                <>
                  <div style={{ marginBottom: '16px', display: 'flex', alignItems: 'center', gap: '8px' }}>
                    <label htmlFor="app-terminal-run-select" style={{ fontSize: '0.875rem', color: 'var(--color-text-muted)' }}>
                      승인 실행(Run):
                    </label>
                    <select
                      id="app-terminal-run-select"
                      data-testid="app-terminal-run-select"
                      value={selectedRunId || ''}
                      onChange={(e) => setSelectedRunId(e.target.value || null)}
                      style={{
                        padding: '4px 8px',
                        borderRadius: '4px',
                        backgroundColor: 'var(--color-bg-surface)',
                        color: 'var(--color-text-primary)',
                        border: '1px solid var(--color-border-subtle)',
                        fontSize: '0.875rem',
                      }}
                    >
                      <option value="">-- 승인 실행 선택 안 함 (대기 상태) --</option>
                      {runs.map((r) => (
                        <option key={r.id} value={r.id}>
                          {r.id} ({r.state})
                        </option>
                      ))}
                    </select>
                  </div>
                  <WebTerminal
                    workspaceId={currentWorkspace.id}
                    commandId={selectedRunId || null}
                  />
                </>
              )}
            </div>
          );
        })()}

        {/* Tab 6: Login */}
        {activeTab === 'login' && (
          <Login
            onLoginSuccess={(user) => {
              setCurrentUser(user);
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
