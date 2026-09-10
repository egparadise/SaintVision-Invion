// Generated; runtime validation must use the canonical JSON Schema.
export type NodeId = string;

export type ProjectId = string;

export type WorkspaceId = string;

export type RunId = string;

export type ResourceId = string;

export type LeaseId = string;

export type EvidenceId = string;

export type WorkloadId = string;

export type Timestamp = string;

export type TenantId = string;

export type TraceId = string;

export type RunState = "draft" | "validated" | "planned" | "awaiting_approval" | "scheduled" | "running" | "verifying" | "recovering" | "succeeded" | "failed" | "cancelled";

export type RiskLevel = "L0" | "L1" | "L2" | "L3";

export interface NodeRegistration {
  nodeId: NodeId;
  tenantId: TenantId;
  hostname: string;
  osFamily: "windows" | "linux";
  architecture: "amd64" | "arm64";
  agentVersion: string;
  csrPem: string;
}

export interface ResourceRequest {
  cpuMillis: number;
  memoryBytes: number;
  gpuCount: number;
  minVramBytes: number;
}

export interface ResourceOffer {
  resourceId: ResourceId;
  kind: "cpu" | "memory" | "gpu" | "storage" | "network";
  capacity: number;
  offered: number;
}

export interface Heartbeat {
  nodeId: NodeId;
  observedAt: Timestamp;
  sequence: number;
  status: "online" | "draining" | "quarantined";
  resources: Array<ResourceOffer>;
}

export interface ResourceSnapshot {
  snapshotId: string;
  observedAt: Timestamp;
  nodeId: NodeId;
  resources: Array<ResourceOffer>;
}

export interface WorkloadSpec {
  apiVersion: "inv.saintvision.ai/v1alpha1";
  kind: "Workload";
  workloadId: WorkloadId;
  tenantId: TenantId;
  projectId: ProjectId;
  workspaceId: WorkspaceId;
  resources: ResourceRequest;
  imageDigest: string;
  command: Array<string>;
  timeoutSeconds: number;
  workspaceResume?: WorkspaceResumeRef;
}

export interface ResourceLease {
  leaseId: LeaseId;
  tenantId: TenantId;
  runId: RunId;
  resourceId: ResourceId;
  amount: number;
  fencingToken: string;
  grantedAt: Timestamp;
  expiresAt: Timestamp;
}

export interface PolicyDecision {
  decisionId: string;
  tenantId: TenantId;
  projectId: ProjectId;
  subjectId: string;
  effect: "allow" | "deny" | "require_approval";
  riskLevel: RiskLevel;
  actionDigest: string;
  expiresAt: Timestamp;
  requiredApprovals: 1 | 2;
  approvedBy: Array<string>;
}

export interface EvidenceEnvelope {
  evidenceId: EvidenceId;
  tenantId: TenantId;
  runId: RunId;
  traceId: TraceId;
  timestamp: Timestamp;
  actorId: string;
  action: string;
  policyDecisionId: string;
  inputSha256: string;
  outputSha256: string;
  result: "succeeded" | "failed" | "denied";
}

export interface RunRecord {
  runId: RunId;
  tenantId: TenantId;
  workloadId: WorkloadId;
  state: RunState;
  version: number;
  attempt: number;
  policyVersion: string;
  contractVersion: "v1alpha1";
  contextHash: string;
}

export interface StepResult {
  runId: RunId;
  stepId: string;
  status: "succeeded" | "failed" | "cancelled";
  exitCode: number;
  evidenceIds: Array<EvidenceId>;
}

export interface IntentSpec {
  objective: string;
  missingFields: Array<string>;
  requestedRisk: RiskLevel;
}

export interface ContextItem {
  sourceId: string;
  version: string;
  contentHash: string;
  redactedContent: string;
  validUntil: Timestamp;
}

export interface ContextBundle {
  contextId: string;
  tenantId: TenantId;
  projectId: ProjectId;
  items: Array<ContextItem>;
  contentHash: string;
  tokenCount: number;
}

export interface ToolManifest {
  toolId: string;
  version: string;
  requiredScope: string;
  riskLevel: RiskLevel;
  timeoutSeconds: number;
  idempotent: boolean;
}

export interface GraphStep {
  stepId: string;
  toolId: string;
  dependsOn: Array<string>;
}

export interface RunGraphSpec {
  graphId: string;
  version: string;
  steps: Array<GraphStep>;
  retryBudget: number;
  maxWallTimeSeconds: number;
}

export interface AgentRunSpec {
  runId: RunId;
  tenantId: TenantId;
  projectId: ProjectId;
  workspaceId: WorkspaceId;
  objective: string;
  allowedTools: Array<string>;
  graphRef: string;
  maxWallTimeSeconds: number;
  retryBudget: number;
}

export type ApprovalId = string;

export type CommandId = string;

export type ApprovalNonce = string;

export type ActionDigest = string;

export interface ApprovalChallenge {
  approvalId: ApprovalId;
  nonce: ApprovalNonce;
  expiresAt: Timestamp;
}

export interface ApprovalDecisionInput {
  decision: "approve" | "reject";
  nonce: ApprovalNonce;
  actionDigest: ActionDigest;
}

export interface ApprovalView {
  approvalId: ApprovalId;
  runId: RunId;
  projectId: ProjectId;
  requesterId: string;
  actionDigest: ActionDigest;
  policyVersion: string;
  requiredApprovals: 1 | 2;
  status: "pending" | "approved" | "rejected" | "expired" | "dispatched";
  expiresAt: Timestamp;
  runVersion: number;
}

export interface AuthorizedCommand {
  commandId: CommandId;
  approvalId: ApprovalId;
  runId: RunId;
  tenantId: TenantId;
  projectId: ProjectId;
  actionDigest: ActionDigest;
  policyVersion: string;
  recoveryEpoch: string;
  expiresAt: Timestamp;
}

export type ClaimId = string;

export interface SandboxLaunchSpec {
  profileVersion: string;
  imageDigest: string;
  argv: Array<string>;
  workspaceId: WorkspaceId;
  workingDirectory: "/workspace";
  workspaceMode: "ephemeral" | "restored";
  cpuMillis: number;
  memoryBytes: number;
  timeoutSeconds: number;
  pidsLimit: 64;
  userId: 65532;
  network: "none";
  rootfsReadOnly: true;
  capDropAll: true;
  noNewPrivileges: true;
  privileged: false;
  hostAccess: false;
  workspaceInput?: WorkspaceInput;
}

export interface ExecutionClaim {
  commandId: CommandId;
  claimId: ClaimId;
  runId: RunId;
  tenantId: TenantId;
  projectId: ProjectId;
  nodeId: NodeId;
  actionDigest: ActionDigest;
  planDigest: ActionDigest;
  policyVersion: string;
  profileVersion: string;
  recoveryEpoch: string;
  notAfter: Timestamp;
}

export interface NodeAllocation {
  lease: ResourceLease;
  nodeId: NodeId;
  kind: "cpu" | "memory";
}

export interface NodeExecutionPermit {
  claim: ExecutionClaim;
  launch: SandboxLaunchSpec;
  allocations: Array<NodeAllocation>;
  issuedAt: Timestamp;
}

export interface SignedNodePermit {
  payload: string;
  signature: string;
}

export interface NodeStopReceipt {
  receiptId: string;
  claimId: ClaimId;
  commandId: CommandId;
  tenantId: TenantId;
  projectId: ProjectId;
  runId: RunId;
  nodeId: NodeId;
  recoveryEpoch: string;
  planDigest: ActionDigest;
  containerId: string;
  stopped: true;
  processStarted: boolean;
  exitCode: number;
  reason: "exited" | "timeout" | "cancelled" | "recovered" | "not_started";
  finishedAt: Timestamp;
  allocations: Array<NodeAllocation>;
  output?: NodeOutput;
}

export interface NodeExecutionResult {
  duplicate: boolean;
  receipt: NodeStopReceipt;
  cleanupPending: false;
}

export interface NodePeerPolicy {
  version: number;
  tenantId: TenantId;
  nodeId: NodeId;
  recoveryEpoch: string;
  expiresAt: Timestamp;
  clientFingerprints: Array<string>;
}

export interface EmptyRequest {
}

export interface RunCancelInput {
  expectedVersion: number;
}

export interface NodeProbeInput {
  nonce: string;
}

export interface NodeProbeResult {
  nonce: string;
  tenantId: TenantId;
  nodeId: NodeId;
  recoveryEpoch: string;
  profileVersion: string;
  observedAt: Timestamp;
}

export interface ProblemDetails {
  type: "about:blank";
  title: string;
  status: number;
  code: string;
  category: string;
  detail: string;
  retryable: boolean;
  traceId: TraceId;
  causeRef: (string | null);
  evidenceId: (EvidenceId | null);
}

export interface NodeResourceSnapshot {
  nonce: string;
  tenantId: TenantId;
  nodeId: NodeId;
  recoveryEpoch: string;
  profileVersion: string;
  observedAt: Timestamp;
  sampleMillis: number;
  cpuCapacityMillis: number;
  cpuBusyMillis: number;
  memoryCapacityBytes: number;
  memoryAvailableBytes: number;
  osType: "linux";
  agentVersion: "0.1.0";
}

export interface NodeChunkInput {
  sha256: string;
  sizeBytes: number;
  offset: number;
  nonce: string;
}

export interface NodeChunkResult {
  sha256: string;
  sizeBytes: number;
  offset: number;
  nonce: string;
  dataBase64: string;
  chunkSha256: string;
}

export interface NodeOutput {
  data: string;
  sha256: string;
  sizeBytes: number;
}

export interface WorkspaceResumeRef {
  resumeId: string;
  checkoutId: string;
  sourceAttempt: number;
  sourceStepId: string;
  stepId: string;
  inputSha256: string;
  inputSizeBytes: number;
  checkpointAttempt: number;
}

export interface WorkspaceInput {
  resumeId: string;
  stepId: string;
  sha256: string;
  sizeBytes: number;
  dataBase64: string;
}

export interface WorkspaceSnapshotFile {
  path: string;
  executable: boolean;
  sha256: string;
  sizeBytes: number;
  dataBase64: string;
}

export interface WorkspaceSnapshot {
  format: "workspace-snapshot:1";
  workspaceId: WorkspaceId;
  directories: Array<string>;
  files: Array<WorkspaceSnapshotFile>;
}

export interface WorkspacePrepareInput {
  checkoutId: string;
  resumeId: string;
  stepId: string;
  workload: WorkloadSpec;
  expectedVersion: number;
}

export interface WorkspaceEnqueueInput {
  resumeId: string;
  approvalId: ApprovalId;
  expectedVersion: number;
}
