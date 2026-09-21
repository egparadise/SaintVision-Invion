/**
 * SaintVision Core Contracts
 * Synchronized with src/saintvision/errors.py, ids.py, and PLAN-FRONTEND-001.
 */

import type {
  ProblemDetails as CanonicalProblemDetails,
  RunState,
  RiskLevel,
  StorageObservationView,
  RecordedStorageObservation,
} from '../../../../packages/contracts-ts/src/index';

export type {
  RunState,
  RiskLevel,
  StorageObservationView,
  RecordedStorageObservation,
};

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

export type NodeStatus =
  | 'online'
  | 'degraded'
  | 'offline'
  | 'draining'
  | 'enrolling'
  | 'retired'
  | 'lost'
  | 'active'
  | 'unknown';

/** Canonical server error envelope; never maintain a parallel hand-written wire shape. */
export type ProblemDetails = CanonicalProblemDetails;

export interface NodeItem {
  telemetryUnavailable?: boolean;
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
  observationOnly?: boolean;
  schedulable?: boolean;
  isDraining?: boolean;
  killSwitchEngaged?: boolean;
  allocatableCores?: number;
  allocatableMemoryBytes?: number;
  ipAddress?: string;
}

export interface ProjectItem {
  id: string; // prj_...
  name: string;
  description?: string;
  ownerId?: string;
  workspaceCount?: number;
  createdAt: string;
  gitRepo?: string;
  gitBranch?: string;
  budgetKrw?: number;
  remainingBudgetKrw?: number;
  kernelLinked?: boolean;
  kernelEnabled?: boolean;
}

export type { WorkspaceExecutionReadinessResponse as WorkspaceReadiness } from './workspace-execution-readiness-response';

export type WorkspaceStatusName = 'provisioning' | 'ready' | 'suspended' | 'deleting' | 'deleted';

export interface WorkspaceItem {
  id: string; // wsp_...
  projectId: string;
  name: string;
  targetNodeId: string | null;
  isolationMode: 'process_sandbox' | 'container_isolated';
  allowedPaths: string[];
  prohibitedPaths: string[];
  cpuLimitCores: number;
  memoryLimitBytes: number;
  status: WorkspaceStatusName;
  createdAt: string;
}

export interface ExecutionResultItem {
  runId: string;
  workspaceId: string;
  command: string;
  exitCode: number;
  state: RunState;
  evidenceId: string;
  resourceReclaimed: boolean;
  allowedEvents: Array<{ timestamp: string; action: string; path?: string }>;
  deniedEvents: Array<{ timestamp: string; action: string; path?: string; reason: string }>;
  executedAt: string;
  completedAt: string;
}

export interface ApprovalItem {
  id: string; // apr_...
  actionDigest?: string;
  requiredApprovals?: 1 | 2;
  projectId?: string;
  runId: string;
  workspaceId?: string;
  nodeId?: string;
  riskLevel?: RiskLevel;
  target?: string;
  command?: string;
  unifiedDiff?: string;
  estimatedCostKrw?: number;
  remainingBudgetKrw?: number;
  blastRadius?: 'workspace_isolated' | 'host_boundary' | 'network_wide';
  rollbackPlan?: string;
  status: 'pending' | 'approved' | 'rejected' | 'expired' | 'dispatched';
  nonce?: string;
  expiresAt: string;
  requestedBy?: string;
  firstApprovedBy?: string;
  secondApprovedBy?: string;
  policyReason: string;
  boundRunVersion?: number;
  createdAt?: string;
}

export interface RunItem {
  id: string; // run_...
  projectId: string;
  workspaceId?: string;
  objective?: string;
  state: RunState;
  requestedBy?: string;
  createdAt?: string;
  updatedAt?: string;
  stateUpdatedAt?: string;
  completedAt?: string | null;
  parentId?: string;
  childRunIds?: string[];
  resourceReleasePending?: boolean;
  attempt?: number;
  outputEvidenceId?: string;
  shardIndex?: number;
  shardCount?: number;
  allPhysicallyStopped?: boolean;
  allSucceeded?: boolean;
  aggregateEvidenceId?: string;
  manifestDigest?: string;
  maxAttempts?: number;
  boundRunVersion?: number;
  version?: number;
  frozenInputHash?: string;
  frozenInputSizeBytes?: number;
  nodeId?: string;
  entrypoint?: string;
  leaseId?: string;
  stopReceipt?: NodeStopReceiptView;
}

export interface WorkspaceResumeSpec {
  resumeId: string;
  runId: string;
  checkoutId: string;
  sourceAttempt: number;
  checkpointAttempt: number;
  sourceStepId: string;
  nextStepId: string;
  inputHash: string;
  inputSizeBytes: number;
  boundRunVersion: number;
  maxAttempts: number;
  currentAttempt: number;
  frozenFiles: Array<{ path: string; size: number; sha256: string }>;
  approvalId?: string;
  createdAt: string;
}

/** UI projection of stop evidence; distinct from the canonical NodeStopReceipt wire contract. */
export interface NodeStopReceiptView {
  receiptId: string;
  runId: string;
  nodeId: string;
  commandId: string;
  exitCode: number;
  physicallyStopped: boolean;
  resourceReclaimed: boolean;
  verified: boolean;
  output?: {
    data?: string;
    sha256: string;
    sizeBytes: number;
  };
  stoppedAt: string;
  supervisorLabel?: string;
}

export interface ShardExecutionItem {
  shardId: string;
  runId: string;
  parentId: string;
  nodeId: string;
  hostname: string;
  attempt?: number;
  executionState: RunState;
  physicallyStopped: boolean;
  verified: boolean;
  resourceReleasePending?: boolean;
  outputHash?: string;
  evidenceId?: string;
  exitCode?: number;
  receiptId?: string;
  receipt?: NodeStopReceiptView;
}

export interface DistributedPlanItem {
  planId: string;
  parentRunId: string;
  state: 'placed' | 'running' | 'completed' | 'cancelled' | 'failed';
  shards: ShardExecutionItem[];
  allPhysicallyStopped: boolean;
  allSucceeded: boolean;
  resourceReleasePending: boolean;
  aggregateEvidenceId?: string;
  manifestDigest?: string;
  createdAt: string;
}

export interface PlacementRequirement {
  requiredCores: number;
  requiredMemoryBytes: number;
  requiresGpu: boolean;
  preferredOs?: 'windows' | 'linux';
  dataLocalityNodeId?: string;
}

export interface CandidateEvaluation {
  nodeId: string;
  hostname: string;
  os: 'windows' | 'linux';
  hardFilterPassed: boolean;
  rejectionReasons: string[];
  scores?: {
    localityScore: number;
    headroomScore: number;
    networkCostScore: number;
    totalScore: number;
  };
}

export interface PlacementExplainResult {
  runId: string;
  selectedNodeId: string | null;
  policyVersion: string;
  snapshotVersion: string;
  evaluations: CandidateEvaluation[];
  decidedAt: string;
}

export type EditorLanguage = 'typescript' | 'javascript' | 'json' | 'markdown' | 'yaml' | 'python';

export interface EditorFile {
  path: string;
  name: string;
  content: string;
  etag: string;
  language: EditorLanguage;
  isDirty?: boolean;
}

export interface DiffLine {
  type: 'added' | 'removed' | 'unchanged';
  originalLineNumber?: number;
  modifiedLineNumber?: number;
  content: string;
}

export interface FileDiffResult {
  path: string;
  originalEtag: string;
  modifiedEtag: string;
  lines: DiffLine[];
  additionsCount: number;
  deletionsCount: number;
}

export interface GitCommitRecord {
  commitId: string; // 40-char SHA
  parentCommitId: string | null;
  author: string;
  message: string;
  timestamp: string;
  stagedFiles: string[];
  treeHash: string;
}

export interface TerminalSessionState {
  sessionId: string;
  workspaceId: string;
  cols: number;
  rows: number;
  lastSeq: number;
  checkpointHash: string;
  reconnectToken: string;
  status: 'connected' | 'reconnecting' | 'disconnected' | 'recovered';
  duplicateExecutions: number;
}

export type NodeHealthState = 'online' | 'stale' | 'offline' | 'recovering' | 'fenced';

export interface FencingToken {
  nodeId: string;
  epoch: number;
  sequence: number;
  issuedAt: string;
}

export interface LateResultRejection {
  requestId: string;
  nodeId: string;
  attemptedToken: { epoch: number; sequence: number };
  currentToken: { epoch: number; sequence: number };
  rejectedAt: string;
  reason: string;
}

export interface ReconciliationRecord {
  reconciliationId: string;
  nodeId: string;
  evacuatedWorkspacesCount: number;
  newEpoch: number;
  recoverySuccess: boolean;
  timestamp: string;
}

export interface AuditLogEntry {
  id: string;
  timestamp: string;
  traceId: string;
  actor: string;
  action: string;
  target: string;
  outcome: 'allowed' | 'denied';
  details: string;
  integrityHash: string;
}

export interface SyntheticGpuResult {
  nodeId: string;
  gpuName: string;
  benchmarkName: string;
  vramAllocatedBytes: number;
  computeThroughputTflops: number;
  exitCode: number;
  completedAt: string;
  evidenceId: string;
}

export interface SecurityControlStatus {
  dockerSocketExposed: boolean;
  approvalBypassesBlocked: number;
  emergencyKillSwitchActive: boolean;
  drainedNodesCount?: number;
  gpuWorkloadStatus: 'healthy' | 'degraded' | 'idle';
  latestBackupAt: string;
  rpoMinutes: number;
  rtoMinutes: number;
}

export interface AgentRunRequest {
  id: string;
  objective: string;
  contextFiles: string[];
  estimatedTokens: number;
  estimatedCostKrw: number;
  tenantRemainingBudgetKrw: number;
  boundedRepairLoops: number;
  maxRepairLoops: number;
  status: 'draft' | 'evaluating' | 'ready' | 'repairing' | 'completed' | 'rejected';
  proposedDiff?: string;
  leakDetectionPassed: boolean;
}

export interface GoldenEvalMetric {
  promptTotal: number;
  promptValid: number;
  promptValidityRate: number;
  codingTasksTotal: number;
  codingTasksPassed: number;
  codingSuccessRate: number;
  secretLeaksDetected: number;
  evaluatedAt: string;
}

export interface ModelLineage {
  modelId: string;
  modelName: string;
  version: string;
  datasetDigest: string; // dset_sha256
  sourceCommitSha: string; // 40-char git sha
  trainingRunId: string; // run_...
  evalAccuracy: number; // e.g. 0.942
  evalF1Score: number; // e.g. 0.915
  approvalId: string; // apr_...
  deploymentDigest: string; // sha256:...
  deployedAt: string;
  status: 'staging' | 'deployed' | 'deprecated';
}

export interface ProviderAdapterConformance {
  provider: 'Codex' | 'Claude' | 'Local-vLLM';
  conformancePassed: boolean;
  contractVersion: string;
  avgLatencyMs: number;
  tokensPerSec: number;
  supportedProtocols: string[];
}

export interface SloMetricRecord {
  name: string;
  targetValue: string;
  actualValue: string;
  status: 'met' | 'breached';
  category: 'latency' | 'resilience' | 'security' | 'storage';
}

export interface AccessibilityAuditResult {
  ruleId: string;
  wcagLevel: 'A' | 'AA' | 'AAA';
  description: string;
  status: 'pass' | 'fail';
  contrastRatio?: number;
}

export interface ReleaseCandidate {
  tag: string;
  buildSha: string;
  builtAt: string;
  unresolvedVulnerabilities: number;
  sloComplianceRate: number;
  rollbackVerified: boolean;
  isActive: boolean;
}

export interface TlsCertificateDetail {
  domain: string;
  issuer: string;
  tlsVersion: string;
  cipherSuite: string;
  validFrom: string;
  validTo: string;
  hstsEnabled: boolean;
  sanList: string[];
}

export interface NginxRoutingRule {
  location: string;
  targetUpstream: string;
  protocol: 'HTTP' | 'SSE' | 'WebSocket' | 'Static';
  bufferingOff: boolean;
  cacheControl: string;
  upgradeHeader: boolean;
}

export interface NodeJourneyVerification {
  nodeId: string;
  hostname: string;
  os: 'windows' | 'linux';
  roles: string[];
  smokeStatus: 'passed' | 'failed';
  latencyMs: number;
  lastVerifiedAt: string;
}

export interface ReleaseManifest {
  releaseId: string;
  version: string;
  imageDigest: string;
  builtCommitSha: string;
  targetClusters: string[];
  totalNodes: number;
  smokePassedRatio: number;
  knownLimitations: string[];
  operatorSignOff: boolean;
}

export interface TrainingModuleStep {
  stepNumber: number;
  title: string;
  description: string;
  actionRequired: string;
  status: 'pending' | 'completed';
}

import type {
  RunResultView,
  ResultStopReceipt,
  ResultOutputMetadata,
  RunArtifactList,
  RunArtifactFile,
  RunLogView,
  RunAttemptObservation,
  RunAttemptList,
  TerminalTicketInput,
  TerminalTicketResult,
  ApprovalView,
  ApprovalPage,
  ApprovalId,
  ControlRunPage,
  ControlRunView,
  ShardPlanId,
  ShardObservedMember,
  ShardResultMember,
  ShardObservation,
  WorkspaceEditView,
  WorkspaceSnapshot,
  WorkspaceSnapshotFile,
} from '../../../../packages/contracts-ts/src/index';

export type {
  RunResultView,
  ResultStopReceipt,
  ResultOutputMetadata,
  RunArtifactList,
  RunArtifactFile,
  RunLogView,
  RunAttemptObservation,
  RunAttemptList,
  TerminalTicketInput,
  TerminalTicketResult,
  ApprovalView,
  ApprovalPage,
  ApprovalId,
  ControlRunPage,
  ControlRunView,
  ShardPlanId,
  ShardObservedMember,
  ShardResultMember,
  ShardObservation,
  WorkspaceEditView,
  WorkspaceSnapshot,
  WorkspaceSnapshotFile,
};

export type RunArtifactItem = RunArtifactFile;
export type RunAttemptItem = RunAttemptObservation;
