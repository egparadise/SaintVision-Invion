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
  workspaceStart?: WorkspaceStartRef;
  targetNodeId?: NodeId;
  terminal?: TerminalSpec;
  modelInput?: ModelExecutionRef;
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
  workspaceMode: "ephemeral" | "restored" | "initialized";
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
  terminal?: TerminalSpec;
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
  resumeId?: string;
  stepId: string;
  sha256: string;
  sizeBytes: number;
  dataBase64: string;
  startId?: string;
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

export interface ControlRunView {
  runId: RunId;
  tenantId: TenantId;
  projectId: ProjectId;
  state: RunState;
  version: number;
  attempt: number;
}

export interface ControlRunPage {
  items: Array<ControlRunView>;
  nextCursor: (RunId | null);
}

export interface WorkspaceFrozenFile {
  path: string;
  sizeBytes: number;
  sha256: ActionDigest;
}

export interface WorkspacePrepareResult {
  resumeId: string;
  workload: WorkloadSpec;
  approval: ApprovalView;
  run: ControlRunView;
}

export interface WorkspaceResumptionView {
  resumeId: string;
  workload: WorkloadSpec;
  run: ControlRunView;
  approval: (ApprovalView | null);
  frozenFiles: Array<WorkspaceFrozenFile>;
}

export interface WorkspaceEnqueueResult {
  resumeId: string;
  runId: RunId;
  commandId: string;
  accepted: true;
}

export type ShardPlanId = string;

export interface ShardReplacementIntent {
  nodeId: NodeId;
  workload: WorkloadSpec;
}

export interface ShardRecoveryPrepareInput {
  sourcePlanId: ShardPlanId;
  planId: ShardPlanId;
  intents: Array<ShardReplacementIntent>;
}

export interface ShardRecoveryPreparedMember {
  index: number;
  runId: RunId;
  nodeId: NodeId;
  approval: ApprovalView;
}

export interface ShardRecoveryPrepared {
  planId: ShardPlanId;
  sourcePlanId: ShardPlanId;
  generation: number;
  shards: Array<ShardRecoveryPreparedMember>;
}

export interface ShardRecoveryEnqueued {
  planId: ShardPlanId;
  sourcePlanId: ShardPlanId;
  rootPlanId: ShardPlanId;
  generation: number;
  queued: number;
  replayed: boolean;
  parentRunId: RunId;
}

export interface BusinessEditLockInput {
  projectId: ProjectId;
  runId: RunId;
  checkoutId: string;
  expectedVersion: number;
}

export interface BusinessBindingInput {
  projectId: ProjectId;
  lockId: string;
  prepare: WorkspacePrepareInput;
}

export interface BusinessApprovalInput {
  approvalId: ApprovalId;
}

export interface BusinessBindingView {
  bindingId: string;
  projectId: ProjectId;
  runId: RunId;
  workspaceId: WorkspaceId;
  lockId: string;
  resumeId: string;
  checkoutId: string;
  recoveryEpoch: string;
  boundRunVersion: number;
  inputSha256: string;
  inputSizeBytes: number;
  approval: ApprovalView;
  state: "frozen" | "approved" | "queued" | "executing" | "settled" | "abandoned";
  run: ControlRunView;
  commandId: (string | null);
  attempt: (number | null);
  stopReceiptId: (string | null);
  deliveryPhase: ("queued" | "uncertain" | "stopped" | null);
  executionConfirmed: boolean;
  evidenceId: (EvidenceId | null);
  releaseAllowed: boolean;
  resourceReleasePending: boolean;
  releasedAt: (string | null);
  workload: WorkloadSpec;
}

export interface ContainmentInput {
  expectedVersion: number;
  reasonCode: "maintenance" | "incident" | "operator_request";
  approvalId: string;
}

export interface ContainmentView {
  nodeId: (NodeId | null);
  version: number;
  killSwitchActive: boolean;
  nodeStatus: ("online" | "offline" | "draining" | "quarantined" | null);
  activeLeases: number;
  pendingDeliveries: number;
  unsettledRuns: number;
  settled: boolean;
}

export interface ContainmentResult {
  requestId: string;
  operation: "kill" | "clear" | "drain" | "resume";
  control: ContainmentView;
  approvalId: string;
}

export interface ContainmentProposalInput {
  operation: "kill" | "clear" | "drain" | "resume";
  nodeId: (NodeId | null);
  expectedVersion: number;
  reasonCode: "maintenance" | "incident" | "operator_request";
}

export interface ContainmentDecisionInput {
  decision: "approve" | "reject";
  contentDigest: string;
  nonce: string;
}

export interface ContainmentApprovalView {
  approvalId: string;
  operation: "kill" | "clear" | "drain" | "resume";
  nodeId: (NodeId | null);
  expectedVersion: number;
  gateVersion: number;
  reasonCode: "maintenance" | "incident" | "operator_request";
  contentDigest: string;
  status: "pending" | "approved" | "rejected" | "consumed";
  expiresAt: string;
  requiredApprovals: 2;
}

export interface WorkspaceStartRef {
  startId: string;
  stepId: string;
  inputSha256: string;
  inputSizeBytes: number;
  nodeId: NodeId;
  cpuResourceId: ResourceId;
  memoryResourceId: ResourceId;
  profileVersion: string;
  policyVersion: string;
}

export interface WorkspaceStartPrepareInput {
  stepId: string;
  workload: WorkloadSpec;
  expectedVersion: number;
  startId: string;
  snapshotBase64: string;
  targetNodeId: NodeId;
}

export interface WorkspaceStartPrepareResult {
  workload: WorkloadSpec;
  approval: ApprovalView;
  run: ControlRunView;
  startId: string;
}

export interface WorkspaceStartView {
  workload: WorkloadSpec;
  run: ControlRunView;
  approval: (ApprovalView | null);
  frozenFiles: Array<WorkspaceFrozenFile>;
  startId: string;
}

export interface WorkspaceStartEnqueueInput {
  approvalId: ApprovalId;
  expectedVersion: number;
  startId: string;
}

export interface WorkspaceStartEnqueueResult {
  runId: RunId;
  commandId: string;
  accepted: true;
  startId: string;
}

export interface ResultOutputMetadata {
  sha256: string;
  sizeBytes: number;
  verified: true;
}

export interface ResultStopReceipt {
  receiptId: string;
  processStarted: boolean;
  exitCode: number;
  reason: string;
  finishedAt: Timestamp;
}

export interface RunResultView {
  source: "execution-kernel";
  runId: RunId;
  projectId: ProjectId;
  state: RunState;
  version: number;
  attemptCount: number;
  sealed: boolean;
  executionConfirmed: boolean;
  commandId: (string | null);
  nodeId: (NodeId | null);
  stopReceipt: (ResultStopReceipt | null);
  evidence: (EvidenceEnvelope | null);
  completedAt: (Timestamp | null);
  output: (ResultOutputMetadata | null);
  outputAbsentReason: (string | null);
  resourceReleasePending: boolean;
}

export interface RunArtifactFile {
  path: string;
  checksumSha256: string;
  byteSize: number;
  verified: true;
  evidenceId: EvidenceId;
}

export interface RunArtifactList {
  source: "execution-kernel";
  runId: RunId;
  artifacts: Array<RunArtifactFile>;
  count: number;
  verifiedCount: number;
  absentReason: (string | null);
}

export interface RunLogView {
  source: "execution-kernel";
  runId: RunId;
  stdout: (string | null);
  stderr: (string | null);
  redacted: boolean;
  truncated: (boolean | null);
  absentReason: (string | null);
}

export interface RunAttemptObservation {
  attemptNumber: number;
  startedAt: (Timestamp | null);
  nodeId: (NodeId | null);
  commandId: (string | null);
  stopReceiptId: (string | null);
  exitCode: (number | null);
  reason: (string | null);
  evidenceId: (EvidenceId | null);
}

export interface RunAttemptList {
  source: "execution-kernel";
  runId: RunId;
  attempts: Array<RunAttemptObservation>;
  count: number;
  nextCursor: (number | null);
}

export interface WorkspaceFileEdit {
  path: string;
  expectedSha256: (string | null);
  dataBase64: (string | null);
  executable: boolean;
}

export interface WorkspaceEditInput {
  expectedRevision: number;
  expectedSha256: string;
  changes: Array<WorkspaceFileEdit>;
}

export interface WorkspaceEditView {
  checkoutId: string;
  revision: number;
  sha256: string;
  snapshot: WorkspaceSnapshot;
}

export interface TerminalSpec {
  sessionId: string;
  rows: number;
  columns: number;
  maxInputBytes: number;
  maxOutputBytes: number;
}

export interface TerminalFrameInput {
  sequence: number;
  cursor: number;
  operation: "poll" | "input" | "resize";
  dataBase64: string;
  rows: number;
  columns: number;
  nonce: string;
}

export interface NodeTerminalInput {
  permit: SignedNodePermit;
  frame: TerminalFrameInput;
}

export interface NodeTerminalResult {
  commandId: CommandId;
  sessionId: string;
  sequence: number;
  cursor: number;
  dataBase64: string;
  nonce: string;
}

export interface TerminalTicketInput {
  commandId: CommandId;
}

export interface TerminalTicketAuthFrame {
  ticket: string;
}

export interface TerminalTicketResult {
  ticket: string;
  expiresAt: string;
  sessionId: string;
  websocketPath: string;
}

export interface RemoteGitProposalInput {
  alias: string;
  mode: "pull" | "push";
  commit: string;
  expectedRevision: number;
  expectedSha256: string;
}

export interface RemoteGitVoteInput {
  contentDigest: string;
  decision: "approve" | "reject";
}

export interface RemoteGitFileAddition {
  path: string;
  contents: string;
}

export interface RemoteGitFileDeletion {
  path: string;
}

export interface RemoteGitChanges {
  additions: Array<RemoteGitFileAddition>;
  deletions: Array<RemoteGitFileDeletion>;
}

export interface RemoteGitProposal {
  alias: string;
  mode: "pull" | "push";
  commit: string;
  expectedRevision: number;
  expectedSha256: string;
  repository: string;
  branch: string;
  repositoryFingerprint: string;
  workspaceId: WorkspaceId;
  snapshotSha256: string;
  changes: (RemoteGitChanges | null);
  operationId: string;
  requesterId: string;
  requesterPersonId: string;
  projectId: ProjectId;
  runId: RunId;
  checkoutId: string;
  recoveryEpoch: string;
  gateVersion: number;
  expiresAt: string;
}

export interface RemoteGitVoteView {
  actorId: string;
  decision: "approve" | "reject";
}

export interface RemoteGitObservation {
  commit: string;
  revision?: number;
  sha256: string;
}

export interface RemoteGitView {
  operationId: string;
  projectId: ProjectId;
  runId: RunId;
  phase: "pending" | "rejected" | "dispatched" | "completed";
  contentDigest: string;
  expiresAt: string;
  requiredApprovals: 2;
  votes: Array<RemoteGitVoteView>;
  proposal: RemoteGitProposal;
  snapshot: WorkspaceSnapshot;
  result: (RemoteGitObservation | null);
}

export interface TerminalBrowserOutput {
  sessionId: string;
  sequence: number;
  cursor: number;
  text: string;
  outputMode: "redacted-complete-lines";
}

export interface NodeStorageChannel {
  tenant_id: TenantId;
  node_id: NodeId;
  recovery_epoch: string;
  version: number;
  endpoint: string;
  certificate_sha256: string;
}

export interface NodeStorageItem {
  location_id: string;
  version: number;
  relative_path: string;
  byte_size: number;
  checksum_sha256: (string | null);
}

export interface NodeStorageChallenge {
  channel: NodeStorageChannel;
  project_id: ProjectId;
  run_id: RunId;
  contribution_id: string;
  root_version: number;
  catalogued: number;
  items: Array<NodeStorageItem>;
  nonce: string;
  issued_at: number;
  expires_at: number;
}

export interface NodeStorageSampleInput {
  challenge: string;
}

export interface NodeStorageSignedSample {
  payload: string;
  signature: string;
}

export interface NodeStorageRootConfig {
  channel: NodeStorageChannel;
  contribution_id: string;
  root_version: number;
  root: string;
}

export interface RecordedStorageObservation {
  evidenceId: EvidenceId;
  checkId: string;
  observedAt: number;
  integrityVerified: true;
  sampleHealthy: boolean;
  sampled: number;
  mismatches: number;
  unverifiable: number;
  examined: number;
  unsampled: number;
}

export interface StorageObservationView {
  requestId: string;
  tenantId: TenantId;
  projectId: ProjectId;
  runId: RunId;
  contributionId: string;
  status: "pending" | "expired" | "recorded";
  createdAt: string;
  expiresAt: number;
  currentHealth: "unknown";
  operationalAcceptanceAssessed: false;
  observation: (RecordedStorageObservation | null);
}

export interface ApprovalPage {
  items: Array<ApprovalView>;
  nextCursor: (ApprovalId | null);
}

export interface ShardObservedMember {
  index: number;
  runId: RunId;
  nodeId: NodeId;
  phase: "queued" | "uncertain" | "stopped";
  state: RunState;
  evidenceId: (EvidenceId | null);
}

export interface ShardResultMember {
  index: number;
  runId: RunId;
  evidenceId: EvidenceId;
  objectId: string;
  sha256: string;
  sizeBytes: number;
}

export interface ShardObservation {
  planId: ShardPlanId;
  sourcePlanId: (ShardPlanId | null);
  rootPlanId: ShardPlanId;
  generation: number;
  parentRunId: (RunId | null);
  parentState: (RunState | null);
  aggregateManifestSha256: (string | null);
  shardCount: number;
  allPhysicallyStopped: boolean;
  allSucceeded: boolean;
  resultManifest: (Array<ShardResultMember> | null);
  resultManifestSha256: (string | null);
  shards: Array<ShardObservedMember>;
}

export interface ApprovalReviewView {
  approval: ApprovalView;
  workload: WorkloadSpec;
  riskLevel: "L0" | "L1" | "L2";
  policyDigest: ActionDigest;
}

export interface SessionView {
  subjectId: string;
  tenantId: string;
  expiresAt: number;
}

export type ModelId = string;

export interface ModelShard {
  index: number;
  offset: number;
  byteLength: number;
  sha256: string;
}

export interface ModelReplica {
  shardIndex: number;
  locationId: string;
  locationVersion: number;
  nodeId: NodeId;
  state: "unverified" | "verified" | "unavailable";
}

export interface ModelRuntimeCompatibility {
  adapter: string;
  version: string;
  modes: Array<"single-node" | "request-routing" | "data-parallel" | "tensor-parallel" | "pipeline-parallel" | "offload">;
}

export interface ModelManifest {
  modelId: ModelId;
  version: string;
  format: string;
  totalBytes: number;
  contentHash: string;
  shards: Array<ModelShard>;
  replicas: Array<ModelReplica>;
  runtimeCompatibility: Array<ModelRuntimeCompatibility>;
  licensePolicy: string;
  classification: "public" | "internal" | "restricted";
  encryption: "none" | "aes256-gcm";
  keyRef: (string | null);
}

export interface ModelExecutionRef {
  inputId: string;
  runId: RunId;
  modelId: ModelId;
  version: string;
  manifestHash: ActionDigest;
  inputSha256: ActionDigest;
  inputSizeBytes: number;
  nodeId: NodeId;
  adapter: "python-files";
  adapterVersion: "1";
  mode: "single-node";
}

export interface ModelCommitObservation {
  projectId: ProjectId;
  modelId: ModelId;
  version: string;
  manifestHash: string;
  sourceRunId: RunId;
  committedAt: string;
  commitRecoveryEpoch: string;
  format: string;
  totalBytes: number;
  shardCount: number;
  licensePolicy: string;
  classification: "public" | "internal" | "restricted";
  committed: true;
  currentAvailability: "unknown";
  requiresExecutionRevalidation: true;
}
