import React, { useState, useEffect } from 'react';
import { Header } from '@/shared/ui/Header';
import { ClusterOverview } from '@/features/dashboard/ClusterOverview';
import { NodeList } from '@/features/nodes/NodeList';
import { NodeDetail } from '@/features/nodes/NodeDetail';
import { RunList } from '@/features/runs/RunList';
import { RunDetail } from '@/features/runs/RunDetail';
import { EvidenceViewer } from '@/features/evidence/EvidenceViewer';
import { ApprovalDetail } from '@/features/approvals/ApprovalDetail';
import { WebTerminal } from '@/features/terminal/WebTerminal';
import { Login } from '@/features/auth/Login';
import { NodeItem, RunItem, ApprovalItem } from '@/contracts/types';

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
  policyReason: '외부 접근 포트 변경 및 TLS 암호화 활성화 정책에 따른 L2 승인 요구 (Rule #304)',
  createdAt: new Date().toISOString(),
};

export const App: React.FC = () => {
  const [theme, setTheme] = useState<'light' | 'dark'>('dark');
  const [activeTab, setActiveTab] = useState('dashboard');
  const [nodes, setNodes] = useState<NodeItem[]>(INITIAL_NODES);
  const [selectedNodeId, setSelectedNodeId] = useState<string | null>(null);
  const [selectedRunId, setSelectedRunId] = useState<string | null>(null);
  const [evidenceRunId, setEvidenceRunId] = useState<string | null>(null);
  const [approval, setApproval] = useState<ApprovalItem>(DEMO_APPROVAL);
  const [nodeSimState, setNodeSimState] = useState<'normal' | 'loading' | 'empty' | 'error' | 'forbidden'>('normal');

  useEffect(() => {
    document.documentElement.setAttribute('data-theme', theme);
  }, [theme]);

  // Live Heartbeat & Metric Fluctuations Simulation
  useEffect(() => {
    const interval = setInterval(() => {
      setNodes((prevNodes) =>
        prevNodes.map((n) => {
          const delta = Math.floor(Math.random() * 5) - 2; // -2% ~ +2%
          const newCpu = Math.min(95, Math.max(5, n.cpuUsagePercent + delta));
          return {
            ...n,
            cpuUsagePercent: newCpu,
            heartbeatAt: new Date().toISOString(),
          };
        })
      );
    }, 4000);
    return () => clearInterval(interval);
  }, []);

  const toggleTheme = () => {
    setTheme((prev) => (prev === 'dark' ? 'light' : 'dark'));
  };

  const handleApprove = async (approvalId: string, nonce: string) => {
    alert(`승인 성공!\nApproval ID: ${approvalId}\nNonce: ${nonce}`);
    setApproval((prev) => ({ ...prev, status: 'approved' }));
  };

  const handleReject = async (approvalId: string, reason: string) => {
    alert(`반려 완료!\nApproval ID: ${approvalId}\n사유: ${reason}`);
    setApproval((prev) => ({ ...prev, status: 'rejected' }));
  };

  const selectedNode = nodes.find((n) => n.id === selectedNodeId);
  const selectedRun = INITIAL_RUNS.find((r) => r.id === selectedRunId);

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
          setSelectedRunId(null);
          setEvidenceRunId(null);
        }}
      />

      <main style={{ flex: 1, padding: '32px 24px', maxWidth: '1200px', margin: '0 auto', width: '100%' }}>
        {/* Tab 1: Dashboard */}
        {activeTab === 'dashboard' && (
          <ClusterOverview
            nodes={INITIAL_NODES}
            runs={INITIAL_RUNS}
            pendingApprovalsCount={approval.status === 'pending' ? 1 : 0}
            onNavigate={(tab) => {
              setActiveTab(tab);
              setSelectedNodeId(null);
              setSelectedRunId(null);
            }}
          />
        )}

        {/* Tab 2: Nodes */}
        {activeTab === 'nodes' && (
          <div>
            {selectedNode ? (
              <NodeDetail node={selectedNode} onBack={() => setSelectedNodeId(null)} />
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
                />
              </div>
            )}
          </div>
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
              />
            ) : (
              <RunList
                runs={INITIAL_RUNS}
                isLoading={false}
                onSelectRun={(id) => setSelectedRunId(id)}
                onCreateRun={() => alert('새 Run 요청 폼')}
              />
            )}
          </div>
        )}

        {/* Tab 4: Approvals */}
        {activeTab === 'approvals' && (
          <div>
            <div style={{ marginBottom: '20px' }}>
              <h2 style={{ fontSize: '1.25rem', fontWeight: 600 }}>승인 센터 (최우선 거버넌스 관문)</h2>
              <p style={{ fontSize: '0.875rem', color: 'var(--color-text-muted)', marginTop: '4px' }}>
                L2/L3 위험 작업 실행 전 필수 거버넌스 검토 및 안전장치 통제 화면입니다.
              </p>
            </div>
            <ApprovalDetail
              approval={approval}
              currentUserId="usr_reviewer_02"
              onApprove={handleApprove}
              onReject={handleReject}
            />
          </div>
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
              alert(`로그인 성공: ${user.name} (${user.role})`);
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
