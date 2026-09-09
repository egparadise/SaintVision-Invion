/**
 * SaintVision Core Contracts
 * Synchronized with src/saintvision/errors.py, ids.py, and PLAN-FRONTEND-001.
 */

export type RunState =
  | 'draft'
  | 'validated'
  | 'planned'
  | 'awaiting_approval'
  | 'scheduled'
  | 'running'
  | 'verifying'
  | 'recovering'
  | 'succeeded'
  | 'failed'
  | 'cancelled';

export type ErrorCategory =
  | 'VAL'
  | 'AUTH'
  | 'CTX'
  | 'TOOL'
  | 'RES'
  | 'NET'
  | 'GRAPH'
  | 'VERIFY'
  | 'SEC'
  | 'BUDGET';

export type RiskLevel = 'L0' | 'L1' | 'L2' | 'L3';

export type NodeStatus = 'online' | 'degraded' | 'offline';

export interface ProblemDetails {
  type: string;
  title: string;
  status: number;
  detail: string;
  instance?: string;
  code: string;
  category: ErrorCategory;
  retryable: boolean;
  traceId: string;
  causeRef?: string;
  evidenceId?: string;
}

export interface NodeItem {
  id: string; // nod_...
  hostname: string;
  status: NodeStatus;
  os: 'windows' | 'linux';
  cpuCores: number;
  cpuUsagePercent: number;
  memoryTotalBytes: number;
  memoryUsedBytes: number;
  gpuName?: string;
  gpuCount: number;
  gpuVramTotalBytes?: number;
  gpuVramUsedBytes?: number;
  storageTotalBytes: number;
  storageUsedBytes: number;
  heartbeatAt: string;
}

export interface ProjectItem {
  id: string; // prj_...
  name: string;
  description: string;
  ownerId: string;
  workspaceCount: number;
  createdAt: string;
}

export interface WorkspaceItem {
  id: string; // wsp_...
  projectId: string;
  name: string;
  targetNodeId: string;
  status: 'active' | 'suspended' | 'terminating';
  createdAt: string;
}

export interface ApprovalItem {
  id: string; // apr_...
  runId: string;
  workspaceId: string;
  nodeId: string;
  riskLevel: RiskLevel;
  target: string;
  command: string;
  unifiedDiff?: string;
  estimatedCostKrw: number;
  remainingBudgetKrw: number;
  blastRadius: 'workspace_isolated' | 'host_boundary' | 'network_wide';
  rollbackPlan?: string;
  status: 'pending' | 'approved' | 'rejected' | 'expired';
  nonce: string;
  expiresAt: string;
  firstApprovedBy?: string;
  secondApprovedBy?: string;
  policyReason: string;
  createdAt: string;
}

export interface RunItem {
  id: string; // run_...
  projectId: string;
  workspaceId: string;
  objective: string;
  state: RunState;
  requestedBy: string;
  createdAt: string;
  updatedAt: string;
}
