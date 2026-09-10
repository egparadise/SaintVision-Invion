// Code generated from core.schema.json; DO NOT EDIT.
package contracts

type NodeId string

type ProjectId string

type WorkspaceId string

type RunId string

type ResourceId string

type LeaseId string

type EvidenceId string

type WorkloadId string

type Timestamp string

type TenantId string

type TraceId string

type RunState string

type RiskLevel string

type NodeRegistration struct {
    NodeId NodeId `json:"nodeId"`
    TenantId TenantId `json:"tenantId"`
    Hostname string `json:"hostname"`
    OsFamily string `json:"osFamily"`
    Architecture string `json:"architecture"`
    AgentVersion string `json:"agentVersion"`
    CsrPem string `json:"csrPem"`
}

type ResourceRequest struct {
    CpuMillis int64 `json:"cpuMillis"`
    MemoryBytes int64 `json:"memoryBytes"`
    GpuCount int64 `json:"gpuCount"`
    MinVramBytes int64 `json:"minVramBytes"`
}

type ResourceOffer struct {
    ResourceId ResourceId `json:"resourceId"`
    Kind string `json:"kind"`
    Capacity int64 `json:"capacity"`
    Offered int64 `json:"offered"`
}

type Heartbeat struct {
    NodeId NodeId `json:"nodeId"`
    ObservedAt Timestamp `json:"observedAt"`
    Sequence int64 `json:"sequence"`
    Status string `json:"status"`
    Resources []ResourceOffer `json:"resources"`
}

type ResourceSnapshot struct {
    SnapshotId string `json:"snapshotId"`
    ObservedAt Timestamp `json:"observedAt"`
    NodeId NodeId `json:"nodeId"`
    Resources []ResourceOffer `json:"resources"`
}

type WorkloadSpec struct {
    ApiVersion string `json:"apiVersion"`
    Kind string `json:"kind"`
    WorkloadId WorkloadId `json:"workloadId"`
    TenantId TenantId `json:"tenantId"`
    ProjectId ProjectId `json:"projectId"`
    WorkspaceId WorkspaceId `json:"workspaceId"`
    Resources ResourceRequest `json:"resources"`
    ImageDigest string `json:"imageDigest"`
    Command []string `json:"command"`
    TimeoutSeconds int64 `json:"timeoutSeconds"`
    WorkspaceResume *WorkspaceResumeRef `json:"workspaceResume,omitempty"`
    TargetNodeId *NodeId `json:"targetNodeId,omitempty"`
    Terminal *TerminalSpec `json:"terminal,omitempty"`
}

type ResourceLease struct {
    LeaseId LeaseId `json:"leaseId"`
    TenantId TenantId `json:"tenantId"`
    RunId RunId `json:"runId"`
    ResourceId ResourceId `json:"resourceId"`
    Amount int64 `json:"amount"`
    FencingToken string `json:"fencingToken"`
    GrantedAt Timestamp `json:"grantedAt"`
    ExpiresAt Timestamp `json:"expiresAt"`
}

type PolicyDecision struct {
    DecisionId string `json:"decisionId"`
    TenantId TenantId `json:"tenantId"`
    ProjectId ProjectId `json:"projectId"`
    SubjectId string `json:"subjectId"`
    Effect string `json:"effect"`
    RiskLevel RiskLevel `json:"riskLevel"`
    ActionDigest string `json:"actionDigest"`
    ExpiresAt Timestamp `json:"expiresAt"`
    RequiredApprovals int64 `json:"requiredApprovals"`
    ApprovedBy []string `json:"approvedBy"`
}

type EvidenceEnvelope struct {
    EvidenceId EvidenceId `json:"evidenceId"`
    TenantId TenantId `json:"tenantId"`
    RunId RunId `json:"runId"`
    TraceId TraceId `json:"traceId"`
    Timestamp Timestamp `json:"timestamp"`
    ActorId string `json:"actorId"`
    Action string `json:"action"`
    PolicyDecisionId string `json:"policyDecisionId"`
    InputSha256 string `json:"inputSha256"`
    OutputSha256 string `json:"outputSha256"`
    Result string `json:"result"`
}

type RunRecord struct {
    RunId RunId `json:"runId"`
    TenantId TenantId `json:"tenantId"`
    WorkloadId WorkloadId `json:"workloadId"`
    State RunState `json:"state"`
    Version int64 `json:"version"`
    Attempt int64 `json:"attempt"`
    PolicyVersion string `json:"policyVersion"`
    ContractVersion string `json:"contractVersion"`
    ContextHash string `json:"contextHash"`
}

type StepResult struct {
    RunId RunId `json:"runId"`
    StepId string `json:"stepId"`
    Status string `json:"status"`
    ExitCode int64 `json:"exitCode"`
    EvidenceIds []EvidenceId `json:"evidenceIds"`
}

type IntentSpec struct {
    Objective string `json:"objective"`
    MissingFields []string `json:"missingFields"`
    RequestedRisk RiskLevel `json:"requestedRisk"`
}

type ContextItem struct {
    SourceId string `json:"sourceId"`
    Version string `json:"version"`
    ContentHash string `json:"contentHash"`
    RedactedContent string `json:"redactedContent"`
    ValidUntil Timestamp `json:"validUntil"`
}

type ContextBundle struct {
    ContextId string `json:"contextId"`
    TenantId TenantId `json:"tenantId"`
    ProjectId ProjectId `json:"projectId"`
    Items []ContextItem `json:"items"`
    ContentHash string `json:"contentHash"`
    TokenCount int64 `json:"tokenCount"`
}

type ToolManifest struct {
    ToolId string `json:"toolId"`
    Version string `json:"version"`
    RequiredScope string `json:"requiredScope"`
    RiskLevel RiskLevel `json:"riskLevel"`
    TimeoutSeconds int64 `json:"timeoutSeconds"`
    Idempotent bool `json:"idempotent"`
}

type GraphStep struct {
    StepId string `json:"stepId"`
    ToolId string `json:"toolId"`
    DependsOn []string `json:"dependsOn"`
}

type RunGraphSpec struct {
    GraphId string `json:"graphId"`
    Version string `json:"version"`
    Steps []GraphStep `json:"steps"`
    RetryBudget int64 `json:"retryBudget"`
    MaxWallTimeSeconds int64 `json:"maxWallTimeSeconds"`
}

type AgentRunSpec struct {
    RunId RunId `json:"runId"`
    TenantId TenantId `json:"tenantId"`
    ProjectId ProjectId `json:"projectId"`
    WorkspaceId WorkspaceId `json:"workspaceId"`
    Objective string `json:"objective"`
    AllowedTools []string `json:"allowedTools"`
    GraphRef string `json:"graphRef"`
    MaxWallTimeSeconds int64 `json:"maxWallTimeSeconds"`
    RetryBudget int64 `json:"retryBudget"`
}

type ApprovalId string

type CommandId string

type ApprovalNonce string

type ActionDigest string

type ApprovalChallenge struct {
    ApprovalId ApprovalId `json:"approvalId"`
    Nonce ApprovalNonce `json:"nonce"`
    ExpiresAt Timestamp `json:"expiresAt"`
}

type ApprovalDecisionInput struct {
    Decision string `json:"decision"`
    Nonce ApprovalNonce `json:"nonce"`
    ActionDigest ActionDigest `json:"actionDigest"`
}

type ApprovalView struct {
    ApprovalId ApprovalId `json:"approvalId"`
    RunId RunId `json:"runId"`
    ProjectId ProjectId `json:"projectId"`
    RequesterId string `json:"requesterId"`
    ActionDigest ActionDigest `json:"actionDigest"`
    PolicyVersion string `json:"policyVersion"`
    RequiredApprovals int64 `json:"requiredApprovals"`
    Status string `json:"status"`
    ExpiresAt Timestamp `json:"expiresAt"`
    RunVersion int64 `json:"runVersion"`
}

type AuthorizedCommand struct {
    CommandId CommandId `json:"commandId"`
    ApprovalId ApprovalId `json:"approvalId"`
    RunId RunId `json:"runId"`
    TenantId TenantId `json:"tenantId"`
    ProjectId ProjectId `json:"projectId"`
    ActionDigest ActionDigest `json:"actionDigest"`
    PolicyVersion string `json:"policyVersion"`
    RecoveryEpoch string `json:"recoveryEpoch"`
    ExpiresAt Timestamp `json:"expiresAt"`
}

type ClaimId string

type SandboxLaunchSpec struct {
    ProfileVersion string `json:"profileVersion"`
    ImageDigest string `json:"imageDigest"`
    Argv []string `json:"argv"`
    WorkspaceId WorkspaceId `json:"workspaceId"`
    WorkingDirectory string `json:"workingDirectory"`
    WorkspaceMode string `json:"workspaceMode"`
    CpuMillis int64 `json:"cpuMillis"`
    MemoryBytes int64 `json:"memoryBytes"`
    TimeoutSeconds int64 `json:"timeoutSeconds"`
    PidsLimit int64 `json:"pidsLimit"`
    UserId int64 `json:"userId"`
    Network string `json:"network"`
    RootfsReadOnly bool `json:"rootfsReadOnly"`
    CapDropAll bool `json:"capDropAll"`
    NoNewPrivileges bool `json:"noNewPrivileges"`
    Privileged bool `json:"privileged"`
    HostAccess bool `json:"hostAccess"`
    WorkspaceInput *WorkspaceInput `json:"workspaceInput,omitempty"`
    Terminal *TerminalSpec `json:"terminal,omitempty"`
}

type ExecutionClaim struct {
    CommandId CommandId `json:"commandId"`
    ClaimId ClaimId `json:"claimId"`
    RunId RunId `json:"runId"`
    TenantId TenantId `json:"tenantId"`
    ProjectId ProjectId `json:"projectId"`
    NodeId NodeId `json:"nodeId"`
    ActionDigest ActionDigest `json:"actionDigest"`
    PlanDigest ActionDigest `json:"planDigest"`
    PolicyVersion string `json:"policyVersion"`
    ProfileVersion string `json:"profileVersion"`
    RecoveryEpoch string `json:"recoveryEpoch"`
    NotAfter Timestamp `json:"notAfter"`
}

type NodeAllocation struct {
    Lease ResourceLease `json:"lease"`
    NodeId NodeId `json:"nodeId"`
    Kind string `json:"kind"`
}

type NodeExecutionPermit struct {
    Claim ExecutionClaim `json:"claim"`
    Launch SandboxLaunchSpec `json:"launch"`
    Allocations []NodeAllocation `json:"allocations"`
    IssuedAt Timestamp `json:"issuedAt"`
}

type SignedNodePermit struct {
    Payload string `json:"payload"`
    Signature string `json:"signature"`
}

type NodeStopReceipt struct {
    ReceiptId string `json:"receiptId"`
    ClaimId ClaimId `json:"claimId"`
    CommandId CommandId `json:"commandId"`
    TenantId TenantId `json:"tenantId"`
    ProjectId ProjectId `json:"projectId"`
    RunId RunId `json:"runId"`
    NodeId NodeId `json:"nodeId"`
    RecoveryEpoch string `json:"recoveryEpoch"`
    PlanDigest ActionDigest `json:"planDigest"`
    ContainerId string `json:"containerId"`
    Stopped bool `json:"stopped"`
    ProcessStarted bool `json:"processStarted"`
    ExitCode int64 `json:"exitCode"`
    Reason string `json:"reason"`
    FinishedAt Timestamp `json:"finishedAt"`
    Allocations []NodeAllocation `json:"allocations"`
    Output *NodeOutput `json:"output,omitempty"`
}

type NodeExecutionResult struct {
    Duplicate bool `json:"duplicate"`
    Receipt NodeStopReceipt `json:"receipt"`
    CleanupPending bool `json:"cleanupPending"`
}

type NodePeerPolicy struct {
    Version int64 `json:"version"`
    TenantId TenantId `json:"tenantId"`
    NodeId NodeId `json:"nodeId"`
    RecoveryEpoch string `json:"recoveryEpoch"`
    ExpiresAt Timestamp `json:"expiresAt"`
    ClientFingerprints []string `json:"clientFingerprints"`
}

type EmptyRequest struct {
}

type RunCancelInput struct {
    ExpectedVersion int64 `json:"expectedVersion"`
}

type NodeProbeInput struct {
    Nonce string `json:"nonce"`
}

type NodeProbeResult struct {
    Nonce string `json:"nonce"`
    TenantId TenantId `json:"tenantId"`
    NodeId NodeId `json:"nodeId"`
    RecoveryEpoch string `json:"recoveryEpoch"`
    ProfileVersion string `json:"profileVersion"`
    ObservedAt Timestamp `json:"observedAt"`
}

type ProblemDetails struct {
    Type string `json:"type"`
    Title string `json:"title"`
    Status int64 `json:"status"`
    Code string `json:"code"`
    Category string `json:"category"`
    Detail string `json:"detail"`
    Retryable bool `json:"retryable"`
    TraceId TraceId `json:"traceId"`
    CauseRef *string `json:"causeRef"`
    EvidenceId *EvidenceId `json:"evidenceId"`
}

type NodeResourceSnapshot struct {
    Nonce string `json:"nonce"`
    TenantId TenantId `json:"tenantId"`
    NodeId NodeId `json:"nodeId"`
    RecoveryEpoch string `json:"recoveryEpoch"`
    ProfileVersion string `json:"profileVersion"`
    ObservedAt Timestamp `json:"observedAt"`
    SampleMillis int64 `json:"sampleMillis"`
    CpuCapacityMillis int64 `json:"cpuCapacityMillis"`
    CpuBusyMillis int64 `json:"cpuBusyMillis"`
    MemoryCapacityBytes int64 `json:"memoryCapacityBytes"`
    MemoryAvailableBytes int64 `json:"memoryAvailableBytes"`
    OsType string `json:"osType"`
    AgentVersion string `json:"agentVersion"`
}

type NodeChunkInput struct {
    Sha256 string `json:"sha256"`
    SizeBytes int64 `json:"sizeBytes"`
    Offset int64 `json:"offset"`
    Nonce string `json:"nonce"`
}

type NodeChunkResult struct {
    Sha256 string `json:"sha256"`
    SizeBytes int64 `json:"sizeBytes"`
    Offset int64 `json:"offset"`
    Nonce string `json:"nonce"`
    DataBase64 string `json:"dataBase64"`
    ChunkSha256 string `json:"chunkSha256"`
}

type NodeOutput struct {
    Data string `json:"data"`
    Sha256 string `json:"sha256"`
    SizeBytes int64 `json:"sizeBytes"`
}

type WorkspaceResumeRef struct {
    ResumeId string `json:"resumeId"`
    CheckoutId string `json:"checkoutId"`
    SourceAttempt int64 `json:"sourceAttempt"`
    SourceStepId string `json:"sourceStepId"`
    StepId string `json:"stepId"`
    InputSha256 string `json:"inputSha256"`
    InputSizeBytes int64 `json:"inputSizeBytes"`
    CheckpointAttempt int64 `json:"checkpointAttempt"`
}

type WorkspaceInput struct {
    ResumeId string `json:"resumeId"`
    StepId string `json:"stepId"`
    Sha256 string `json:"sha256"`
    SizeBytes int64 `json:"sizeBytes"`
    DataBase64 string `json:"dataBase64"`
}

type WorkspaceSnapshotFile struct {
    Path string `json:"path"`
    Executable bool `json:"executable"`
    Sha256 string `json:"sha256"`
    SizeBytes int64 `json:"sizeBytes"`
    DataBase64 string `json:"dataBase64"`
}

type WorkspaceSnapshot struct {
    Format string `json:"format"`
    WorkspaceId WorkspaceId `json:"workspaceId"`
    Directories []string `json:"directories"`
    Files []WorkspaceSnapshotFile `json:"files"`
}

type WorkspacePrepareInput struct {
    CheckoutId string `json:"checkoutId"`
    ResumeId string `json:"resumeId"`
    StepId string `json:"stepId"`
    Workload WorkloadSpec `json:"workload"`
    ExpectedVersion int64 `json:"expectedVersion"`
}

type WorkspaceEnqueueInput struct {
    ResumeId string `json:"resumeId"`
    ApprovalId ApprovalId `json:"approvalId"`
    ExpectedVersion int64 `json:"expectedVersion"`
}

type ControlRunView struct {
    RunId RunId `json:"runId"`
    TenantId TenantId `json:"tenantId"`
    ProjectId ProjectId `json:"projectId"`
    State RunState `json:"state"`
    Version int64 `json:"version"`
    Attempt int64 `json:"attempt"`
}

type WorkspaceFrozenFile struct {
    Path string `json:"path"`
    SizeBytes int64 `json:"sizeBytes"`
    Sha256 ActionDigest `json:"sha256"`
}

type WorkspacePrepareResult struct {
    ResumeId string `json:"resumeId"`
    Workload WorkloadSpec `json:"workload"`
    Approval ApprovalView `json:"approval"`
    Run ControlRunView `json:"run"`
}

type WorkspaceResumptionView struct {
    ResumeId string `json:"resumeId"`
    Workload WorkloadSpec `json:"workload"`
    Run ControlRunView `json:"run"`
    Approval *ApprovalView `json:"approval"`
    FrozenFiles []WorkspaceFrozenFile `json:"frozenFiles"`
}

type WorkspaceEnqueueResult struct {
    ResumeId string `json:"resumeId"`
    RunId RunId `json:"runId"`
    CommandId string `json:"commandId"`
    Accepted bool `json:"accepted"`
}

type ShardPlanId string

type ShardReplacementIntent struct {
    NodeId NodeId `json:"nodeId"`
    Workload WorkloadSpec `json:"workload"`
}

type ShardRecoveryPrepareInput struct {
    SourcePlanId ShardPlanId `json:"sourcePlanId"`
    PlanId ShardPlanId `json:"planId"`
    Intents []ShardReplacementIntent `json:"intents"`
}

type ShardRecoveryPreparedMember struct {
    Index int64 `json:"index"`
    RunId RunId `json:"runId"`
    NodeId NodeId `json:"nodeId"`
    Approval ApprovalView `json:"approval"`
}

type ShardRecoveryPrepared struct {
    PlanId ShardPlanId `json:"planId"`
    SourcePlanId ShardPlanId `json:"sourcePlanId"`
    Generation int64 `json:"generation"`
    Shards []ShardRecoveryPreparedMember `json:"shards"`
}

type ShardRecoveryEnqueued struct {
    PlanId ShardPlanId `json:"planId"`
    SourcePlanId ShardPlanId `json:"sourcePlanId"`
    RootPlanId ShardPlanId `json:"rootPlanId"`
    Generation int64 `json:"generation"`
    Queued int64 `json:"queued"`
    Replayed bool `json:"replayed"`
    ParentRunId RunId `json:"parentRunId"`
}

type BusinessEditLockInput struct {
    ProjectId ProjectId `json:"projectId"`
    RunId RunId `json:"runId"`
    CheckoutId string `json:"checkoutId"`
    ExpectedVersion int64 `json:"expectedVersion"`
}

type BusinessBindingInput struct {
    ProjectId ProjectId `json:"projectId"`
    LockId string `json:"lockId"`
    Prepare WorkspacePrepareInput `json:"prepare"`
}

type BusinessApprovalInput struct {
    ApprovalId ApprovalId `json:"approvalId"`
}

type BusinessBindingView struct {
    BindingId string `json:"bindingId"`
    ProjectId ProjectId `json:"projectId"`
    RunId RunId `json:"runId"`
    WorkspaceId WorkspaceId `json:"workspaceId"`
    LockId string `json:"lockId"`
    ResumeId string `json:"resumeId"`
    CheckoutId string `json:"checkoutId"`
    RecoveryEpoch string `json:"recoveryEpoch"`
    BoundRunVersion int64 `json:"boundRunVersion"`
    InputSha256 string `json:"inputSha256"`
    InputSizeBytes int64 `json:"inputSizeBytes"`
    Approval ApprovalView `json:"approval"`
    State string `json:"state"`
    Run ControlRunView `json:"run"`
    CommandId *string `json:"commandId"`
    Attempt *int64 `json:"attempt"`
    StopReceiptId *string `json:"stopReceiptId"`
    DeliveryPhase *string `json:"deliveryPhase"`
    ExecutionConfirmed bool `json:"executionConfirmed"`
    EvidenceId *EvidenceId `json:"evidenceId"`
    ReleaseAllowed bool `json:"releaseAllowed"`
    ResourceReleasePending bool `json:"resourceReleasePending"`
    ReleasedAt *string `json:"releasedAt"`
    Workload WorkloadSpec `json:"workload"`
}

type ContainmentInput struct {
    ExpectedVersion int64 `json:"expectedVersion"`
    ReasonCode string `json:"reasonCode"`
    ApprovalId string `json:"approvalId"`
}

type ContainmentView struct {
    NodeId *NodeId `json:"nodeId"`
    Version int64 `json:"version"`
    KillSwitchActive bool `json:"killSwitchActive"`
    NodeStatus *string `json:"nodeStatus"`
    ActiveLeases int64 `json:"activeLeases"`
    PendingDeliveries int64 `json:"pendingDeliveries"`
    UnsettledRuns int64 `json:"unsettledRuns"`
    Settled bool `json:"settled"`
}

type ContainmentResult struct {
    RequestId string `json:"requestId"`
    Operation string `json:"operation"`
    Control ContainmentView `json:"control"`
    ApprovalId string `json:"approvalId"`
}

type ContainmentProposalInput struct {
    Operation string `json:"operation"`
    NodeId *NodeId `json:"nodeId"`
    ExpectedVersion int64 `json:"expectedVersion"`
    ReasonCode string `json:"reasonCode"`
}

type ContainmentDecisionInput struct {
    Decision string `json:"decision"`
    ContentDigest string `json:"contentDigest"`
    Nonce string `json:"nonce"`
}

type ContainmentApprovalView struct {
    ApprovalId string `json:"approvalId"`
    Operation string `json:"operation"`
    NodeId *NodeId `json:"nodeId"`
    ExpectedVersion int64 `json:"expectedVersion"`
    GateVersion int64 `json:"gateVersion"`
    ReasonCode string `json:"reasonCode"`
    ContentDigest string `json:"contentDigest"`
    Status string `json:"status"`
    ExpiresAt string `json:"expiresAt"`
    RequiredApprovals int64 `json:"requiredApprovals"`
}

type WorkspaceFileEdit struct {
    Path string `json:"path"`
    ExpectedSha256 *string `json:"expectedSha256"`
    DataBase64 *string `json:"dataBase64"`
    Executable bool `json:"executable"`
}

type WorkspaceEditInput struct {
    ExpectedRevision int64 `json:"expectedRevision"`
    ExpectedSha256 string `json:"expectedSha256"`
    Changes []WorkspaceFileEdit `json:"changes"`
}

type WorkspaceEditView struct {
    CheckoutId string `json:"checkoutId"`
    Revision int64 `json:"revision"`
    Sha256 string `json:"sha256"`
    Snapshot WorkspaceSnapshot `json:"snapshot"`
}

type TerminalSpec struct {
    SessionId string `json:"sessionId"`
    Rows int64 `json:"rows"`
    Columns int64 `json:"columns"`
    MaxInputBytes int64 `json:"maxInputBytes"`
    MaxOutputBytes int64 `json:"maxOutputBytes"`
}

type TerminalFrameInput struct {
    Sequence int64 `json:"sequence"`
    Cursor int64 `json:"cursor"`
    Operation string `json:"operation"`
    DataBase64 string `json:"dataBase64"`
    Rows int64 `json:"rows"`
    Columns int64 `json:"columns"`
    Nonce string `json:"nonce"`
}

type NodeTerminalInput struct {
    Permit SignedNodePermit `json:"permit"`
    Frame TerminalFrameInput `json:"frame"`
}

type NodeTerminalResult struct {
    CommandId CommandId `json:"commandId"`
    SessionId string `json:"sessionId"`
    Sequence int64 `json:"sequence"`
    Cursor int64 `json:"cursor"`
    DataBase64 string `json:"dataBase64"`
    Nonce string `json:"nonce"`
}

type TerminalTicketInput struct {
    CommandId CommandId `json:"commandId"`
}

type TerminalTicketResult struct {
    Ticket string `json:"ticket"`
    ExpiresAt string `json:"expiresAt"`
    SessionId string `json:"sessionId"`
    WebsocketPath string `json:"websocketPath"`
}

type RemoteGitProposalInput struct {
    Alias string `json:"alias"`
    Mode string `json:"mode"`
    Commit string `json:"commit"`
    ExpectedRevision int64 `json:"expectedRevision"`
    ExpectedSha256 string `json:"expectedSha256"`
}

type RemoteGitVoteInput struct {
    ContentDigest string `json:"contentDigest"`
    Decision string `json:"decision"`
}

type RemoteGitFileAddition struct {
    Path string `json:"path"`
    Contents string `json:"contents"`
}

type RemoteGitFileDeletion struct {
    Path string `json:"path"`
}

type RemoteGitChanges struct {
    Additions []RemoteGitFileAddition `json:"additions"`
    Deletions []RemoteGitFileDeletion `json:"deletions"`
}

type RemoteGitProposal struct {
    Alias string `json:"alias"`
    Mode string `json:"mode"`
    Commit string `json:"commit"`
    ExpectedRevision int64 `json:"expectedRevision"`
    ExpectedSha256 string `json:"expectedSha256"`
    Repository string `json:"repository"`
    Branch string `json:"branch"`
    RepositoryFingerprint string `json:"repositoryFingerprint"`
    WorkspaceId WorkspaceId `json:"workspaceId"`
    SnapshotSha256 string `json:"snapshotSha256"`
    Changes *RemoteGitChanges `json:"changes"`
    OperationId string `json:"operationId"`
    RequesterId string `json:"requesterId"`
    RequesterPersonId string `json:"requesterPersonId"`
    ProjectId ProjectId `json:"projectId"`
    RunId RunId `json:"runId"`
    CheckoutId string `json:"checkoutId"`
    RecoveryEpoch string `json:"recoveryEpoch"`
    GateVersion int64 `json:"gateVersion"`
    ExpiresAt string `json:"expiresAt"`
}

type RemoteGitVoteView struct {
    ActorId string `json:"actorId"`
    Decision string `json:"decision"`
}

type RemoteGitObservation struct {
    Commit string `json:"commit"`
    Revision *int64 `json:"revision,omitempty"`
    Sha256 string `json:"sha256"`
}

type RemoteGitView struct {
    OperationId string `json:"operationId"`
    ProjectId ProjectId `json:"projectId"`
    RunId RunId `json:"runId"`
    Phase string `json:"phase"`
    ContentDigest string `json:"contentDigest"`
    ExpiresAt string `json:"expiresAt"`
    RequiredApprovals int64 `json:"requiredApprovals"`
    Votes []RemoteGitVoteView `json:"votes"`
    Proposal RemoteGitProposal `json:"proposal"`
    Snapshot WorkspaceSnapshot `json:"snapshot"`
    Result *RemoteGitObservation `json:"result"`
}

type TerminalBrowserOutput struct {
    SessionId string `json:"sessionId"`
    Sequence int64 `json:"sequence"`
    Cursor int64 `json:"cursor"`
    Text string `json:"text"`
    OutputMode string `json:"outputMode"`
}
