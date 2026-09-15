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

export type NodeStatus = 'online' | 'degraded' | 'offline' | 'draining' | 'enrolling' | 'retired';

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

export type ReadinessResolver = 'operator' | 'project owner' | 'node owner' | 'requester';

export interface ExecutionReadinessCheck {
  check: string;
  satisfied: boolean;
  detail: string;
  resolvedBy?: ReadinessResolver;
  remedy?: string;
  snapshotBytes?: number | null;
  maxSnapshotBytes?: number;
  maxContentBytes?: number;
  runId?: string | null;
}

export interface WorkspaceReadiness {
  workspaceId: string;
  projectId: string;
  executable: boolean;
  scope: string;
  nodeReadiness: string;
  admissionRequired: boolean;
  checks: ExecutionReadinessCheck[];
  blockedBy: ReadinessResolver[];
  summary: string;
}

export interface WorkspaceItem {
  id: string; // wsp_...
  projectId: string;
  name: string;
  targetNodeId: string;
  isolationMode: 'process_sandbox' | 'container_isolated';
  allowedPaths: string[];
  prohibitedPaths: string[];
  cpuLimitCores: number;
  memoryLimitBytes: number;
  status: 'active' | 'suspended' | 'terminating' | 'reclaimed';
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
  stopReceipt?: NodeStopReceipt;
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

export interface NodeStopReceipt {
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
  receipt?: NodeStopReceipt;
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

export interface RunResultView {
  source: 'execution-kernel' | string;
  runId: string;
  projectId: string;
  state: RunState;
  version: number;
  attemptCount: number;
  sealed: boolean;
  executionConfirmed: boolean;
  commandId?: string | null;
  nodeId?: string | null;
  stopReceipt?: NodeStopReceipt | {
    receiptId: string;
    processStarted?: boolean;
    exitCode: number;
    reason?: string;
    finishedAt?: string;
    physicallyStopped?: boolean;
    resourceReclaimed?: boolean;
    verified?: boolean;
  } | null;
  evidence?: {
    evidenceId?: string;
    [key: string]: any;
  } | null;
  completedAt?: string | null;
  output?: {
    sha256: string;
    sizeBytes: number;
    verified: boolean;
  } | null;
  outputAbsentReason?: string | null;
  resourceReleasePending?: boolean;
}

export interface RunArtifactItem {
  path: string;
  checksumSha256: string;
  byteSize: number;
  verified: boolean;
  evidenceId?: string;
}

export interface RunArtifactList {
  source: 'execution-kernel' | string;
  runId: string;
  artifacts: RunArtifactItem[];
  count: number;
  verifiedCount: number;
  absentReason?: string | null;
}

export interface RunLogView {
  source: 'execution-kernel' | string;
  runId: string;
  stdout: string | null;
  stderr: string | null;
  redacted: boolean;
  truncated?: boolean | null;
  absentReason?: string | null;
}

export interface RunAttemptItem {
  attemptNumber: number;
  startedAt: string;
  nodeId: string;
  commandId?: string | null;
  stopReceiptId?: string | null;
  exitCode?: number | null;
  reason?: string | null;
  evidenceId?: string | null;
}

export interface RunAttemptList {
  source: 'execution-kernel' | string;
  runId: string;
  attempts: RunAttemptItem[];
  count: number;
  nextCursor?: number | null;
}

export interface ApprovalView {
  approvalId: string;
  runId: string;
  projectId: string;
  requesterId: string;
  actionDigest: string;
  policyVersion: string;
  requiredApprovals: 1 | 2;
  status: 'pending' | 'approved' | 'rejected' | 'expired' | 'dispatched';
  expiresAt: string;
  runVersion: number;
}

export interface ApprovalPage {
  items: ApprovalView[];
  nextCursor: string | null;
}

export type ShardPlanId = string;

export interface ShardObservedMember {
  index: number;
  runId: string;
  nodeId: string;
  phase: 'queued' | 'uncertain' | 'stopped';
  state: RunState;
  evidenceId: string | null;
}

export interface ShardResultMember {
  index: number;
  runId: string;
  evidenceId: string;
  objectId: string;
  sha256: string;
  sizeBytes: number;
}

export interface ShardObservation {
  planId: ShardPlanId;
  sourcePlanId: ShardPlanId | null;
  rootPlanId: ShardPlanId;
  generation: number;
  parentRunId: string | null;
  parentState: RunState | null;
  aggregateManifestSha256: string | null;
  shardCount: number;
  allPhysicallyStopped: boolean;
  allSucceeded: boolean;
  resultManifest: ShardResultMember[] | null;
  resultManifestSha256: string | null;
  shards: ShardObservedMember[];
  items?: ShardExecutionItem[];
  total?: number;
}
