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
import { fetchProjects } from '@/shared/api/projectObservation';
import { fetchObservedRuns, fetchObservedApprovals } from '@/shared/api/runApprovalObservation';
import { observedNode } from '@/shared/api/nodeObservation';
import { decideApproval, cancelKernelRun } from '@/shared/api/kernelMutations';

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
  const [runError, setRunError] = useState<string | null>(null);
  const [approvalError, setApprovalError] = useState<string | null>(null);
  const activeProject = useRef('');
  const runRequest = useRef(0);
  const approvalRequest = useRef(0);
  const [nodeSimState, setNodeSimState] = useState<'normal' | 'loading' | 'empty' | 'error' | 'forbidden'>('normal');
  const [currentUser, setCurrentUser] = useState<{ id: string; name: string; role: string; tenantId?: string } | null>(null);

  const [projects, setProjects] = useState<ProjectItem[]>([]);
  const [projectId, setProjectId] = useState('');
  const [projectError, setProjectError] = useState<string | null>(null);
  const scopeRef = useRef(0);
  const measuredNodes = nodes.filter(node => !node.telemetryUnavailable);
  const selectedProject = projects.find(p => p.id === projectId);
  const chooseProject = (id: string) => {
    scopeRef.current += 1;
    activeProject.current = id;
    setRunError(null); setApprovalError(null);
    setProjectId(id); setRuns([]); setApprovals([]); setWorkspaces([]);
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
    if (!currentUser) return;
    const scope = scopeRef.current;
    try {
      const page = await apiClient<{ items: Record<string, unknown>[] }>('/v1/nodes');
      if (scopeRef.current === scope) setNodes(page.items.map(observedNode));
    } catch {
      if (scopeRef.current === scope) setNodes([]);
    }
  }, [currentUser]);

  const fetchRuns = React.useCallback(async () => {
    if (!currentUser || !projectId || activeProject.current !== projectId) return;
    const scope = scopeRef.current;
    const request = ++runRequest.current;
    try {
      const items = await fetchObservedRuns(projectId);
      if (scopeRef.current === scope && request === runRequest.current) { setRuns(items); setRunError(null); }
    } catch {
      if (scopeRef.current === scope && request === runRequest.current) { setRuns([]); setRunError('Run 목록을 확인하지 못했습니다.'); }
    }
  }, [currentUser, projectId]);

  const fetchApprovals = React.useCallback(async () => {
    if (!currentUser || !projectId || activeProject.current !== projectId) return;
    const scope = scopeRef.current;
    const request = ++approvalRequest.current;
    try {
      const items = await fetchObservedApprovals(projectId);
      if (scopeRef.current === scope && request === approvalRequest.current) { setApprovals(items); setApprovalError(null); }
    } catch {
      if (scopeRef.current === scope && request === approvalRequest.current) { setApprovals([]); setApprovalError('승인 목록을 확인하지 못했습니다.'); }
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

  const handleApprove = async (approvalId: string, _nonce: string, shown?: ReviewedAction) => {
    try {
      const approval = approvals.find((a) => a.id === approvalId);
      if (!approval || activeProject.current !== approval.projectId) throw new Error('승인 안건을 다시 선택하세요.');
      await approveReviewed(approval, shown);
      // Fetch fresh runs and approvals after server confirmed approval
      await Promise.all([fetchApprovals(), fetchRuns()]);
    } catch (err: any) {
      console.error('Backend approval API failed:', err);
      const errMsg = err?.problem?.detail || err?.detail || err?.message || '승인 처리 중 오류가 발생했습니다.';
      alert(`승인 처리 실패: ${errMsg}`);
      throw err;
    }
  };

  const handleReject = async (approvalId: string, _reason: string) => {
    try {
      const approval = approvals.find((a) => a.id === approvalId);
      if (!approval) throw new Error('승인 요청을 새로고침하세요.');
      await decideApproval(approval, 'reject');
      // Fetch fresh runs and approvals after server confirmed rejection
      await Promise.all([fetchApprovals(), fetchRuns()]);
    } catch (err: any) {
      console.error('Backend approval reject API failed:', err);
      const errMsg = err?.problem?.detail || err?.detail || err?.message || '승인 반려 처리 중 오류가 발생했습니다.';
      alert(`승인 반려 실패: ${errMsg}`);
      throw err;
    }
  };

  const handleCancelRun = async (runId: string, _reason: string) => {
    try {
      const targetRun = runs.find((r) => r.id === runId);
      await cancelKernelRun(targetRun?.projectId, runId);
      await fetchRuns();
    } catch (err) {
      console.warn('Backend run cancellation API error:', err);
      alert('취소를 확인하지 못했습니다. 실행 상태를 새로고침한 뒤 확인하세요.');
      throw err;
    }
  };

  const selectedNode = nodes.find((n) => n.id === selectedNodeId);
  const selectedRun = runs.find((r) => r.id === selectedRunId);

  if (!currentUser) return <Login onLoginSuccess={user => { setCurrentUser(user); setActiveTab('dashboard'); }} />;

  if (desktop && currentUser && projectId) return <DesktopShell
    key={`${currentUser.tenantId}:${currentUser.id}:${projectId}`} projectId={projectId}
    nodes={nodes} runs={runs} approvals={approvals} workspaces={workspaces}
    currentReviewerId={currentUser.id} onRefreshNodes={fetchNodes}
    onApprove={handleApprove} onReject={handleReject} onChangeUser={() => {}}
    onSwitchToPortalView={() => setDesktop(false)} currentTheme={theme}
    onToggleTheme={() => setTheme(theme === 'dark' ? 'light' : 'dark')} />;

  return (
    <div style={{ minHeight: '100vh', display: 'flex', flexDirection: 'column' }}>
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
        {runError && <p role="alert">{runError}</p>}
        {approvalError && <p role="alert">{approvalError}</p>}
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

        {activeTab === 'studio' && !selectedProject && <p role="status">프로젝트를 선택하면 Studio를 열 수 있습니다.</p>}
        {/* Tab 1.5: Integrated Developer Studio */}
        {activeTab === 'studio' && selectedProject && (
          <DeveloperStudio
            key={projectId}
            project={selectedProject}
            nodes={measuredNodes}
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

        {/* Tab 2.1: Virtual Fabric & Control Plane Explorer (CX-01) */}
        {activeTab === 'fabric' && (
          <ResourceExplorer
            nodes={measuredNodes}
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
          <PlacementSimulator nodes={measuredNodes} />
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
            key={`${currentUser?.tenantId}:${currentUser?.id}:${projectId}`}
            approvals={approvals}
            currentUserId={currentUser?.id ?? ''}
            onApprove={handleApprove}
            onReject={handleReject}
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
                  data-testid="terminal-no-workspace-notice"
                  style={{
                    padding: '16px',
                    backgroundColor: 'var(--color-bg-surface)',
                    border: '1px solid var(--color-border-subtle)',
                    borderRadius: '6px',
                    color: 'var(--color-text-muted)',
                  }}
                >
                  ⚠️ 등록되거나 선택된 워크스페이스가 없습니다. 터미널 세션을 시작할 수 없습니다. (유효 워크스페이스 필요)
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
