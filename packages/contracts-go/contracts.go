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
    WorkspaceStart *WorkspaceStartRef `json:"workspaceStart,omitempty"`
    TargetNodeId *NodeId `json:"targetNodeId,omitempty"`
    Terminal *TerminalSpec `json:"terminal,omitempty"`
    ModelInput *ModelExecutionRef `json:"modelInput,omitempty"`
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
    ResumeId *string `json:"resumeId,omitempty"`
    StepId string `json:"stepId"`
    Sha256 string `json:"sha256"`
    SizeBytes int64 `json:"sizeBytes"`
    DataBase64 string `json:"dataBase64"`
    StartId *string `json:"startId,omitempty"`
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

type ControlRunPage struct {
    Items []ControlRunView `json:"items"`
    NextCursor *RunId `json:"nextCursor"`
}

type ControlRunDetail struct {
    RunId RunId `json:"runId"`
    TenantId TenantId `json:"tenantId"`
    ProjectId ProjectId `json:"projectId"`
    State RunState `json:"state"`
    Version int64 `json:"version"`
    Attempt int64 `json:"attempt"`
    ResourceReleasePending bool `json:"resourceReleasePending"`
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

type WorkspaceStartRef struct {
    StartId string `json:"startId"`
    StepId string `json:"stepId"`
    InputSha256 string `json:"inputSha256"`
    InputSizeBytes int64 `json:"inputSizeBytes"`
    NodeId NodeId `json:"nodeId"`
    CpuResourceId ResourceId `json:"cpuResourceId"`
    MemoryResourceId ResourceId `json:"memoryResourceId"`
    ProfileVersion string `json:"profileVersion"`
    PolicyVersion string `json:"policyVersion"`
}

type WorkspaceStartPrepareInput struct {
    StepId string `json:"stepId"`
    Workload WorkloadSpec `json:"workload"`
    ExpectedVersion int64 `json:"expectedVersion"`
    StartId string `json:"startId"`
    SnapshotBase64 string `json:"snapshotBase64"`
    TargetNodeId NodeId `json:"targetNodeId"`
}

type WorkspaceStartPrepareResult struct {
    Workload WorkloadSpec `json:"workload"`
    Approval ApprovalView `json:"approval"`
    Run ControlRunView `json:"run"`
    StartId string `json:"startId"`
}

type WorkspaceStartView struct {
    Workload WorkloadSpec `json:"workload"`
    Run ControlRunView `json:"run"`
    Approval *ApprovalView `json:"approval"`
    FrozenFiles []WorkspaceFrozenFile `json:"frozenFiles"`
    StartId string `json:"startId"`
}

type WorkspaceStartEnqueueInput struct {
    ApprovalId ApprovalId `json:"approvalId"`
    ExpectedVersion int64 `json:"expectedVersion"`
    StartId string `json:"startId"`
}

type WorkspaceStartEnqueueResult struct {
    RunId RunId `json:"runId"`
    CommandId string `json:"commandId"`
    Accepted bool `json:"accepted"`
    StartId string `json:"startId"`
}

type ResultOutputMetadata struct {
    Sha256 string `json:"sha256"`
    SizeBytes int64 `json:"sizeBytes"`
    Verified bool `json:"verified"`
}

type ResultStopReceipt struct {
    ReceiptId string `json:"receiptId"`
    ProcessStarted bool `json:"processStarted"`
    ExitCode int64 `json:"exitCode"`
    Reason string `json:"reason"`
    FinishedAt Timestamp `json:"finishedAt"`
}

type RunResultView struct {
    Source string `json:"source"`
    RunId RunId `json:"runId"`
    ProjectId ProjectId `json:"projectId"`
    State RunState `json:"state"`
    Version int64 `json:"version"`
    AttemptCount int64 `json:"attemptCount"`
    StateUpdatedAt Timestamp `json:"stateUpdatedAt"`
    Sealed bool `json:"sealed"`
    ExecutionConfirmed bool `json:"executionConfirmed"`
    CommandId *string `json:"commandId"`
    NodeId *NodeId `json:"nodeId"`
    StopReceipt *ResultStopReceipt `json:"stopReceipt"`
    Evidence *EvidenceEnvelope `json:"evidence"`
    CompletedAt *Timestamp `json:"completedAt"`
    Output *ResultOutputMetadata `json:"output"`
    OutputAbsentReason *string `json:"outputAbsentReason"`
    ResourceReleasePending bool `json:"resourceReleasePending"`
}

type ArtifactContentResponse struct {
    StatusCode int64 `json:"statusCode"`
    ContentType string `json:"contentType"`
    ContentDisposition string `json:"contentDisposition"`
    Artifact RunArtifactFile `json:"artifact"`
    ContentTypeOptions string `json:"contentTypeOptions"`
}

type RunArtifactFile struct {
    Path string `json:"path"`
    ChecksumSha256 string `json:"checksumSha256"`
    ByteSize int64 `json:"byteSize"`
    Verified bool `json:"verified"`
    EvidenceId EvidenceId `json:"evidenceId"`
}

type RunArtifactList struct {
    Source string `json:"source"`
    RunId RunId `json:"runId"`
    CompletedAt *Timestamp `json:"completedAt"`
    Artifacts []RunArtifactFile `json:"artifacts"`
    Count int64 `json:"count"`
    VerifiedCount int64 `json:"verifiedCount"`
    AbsentReason *string `json:"absentReason"`
}

type RunLogView struct {
    Source string `json:"source"`
    RunId RunId `json:"runId"`
    CompletedAt *Timestamp `json:"completedAt"`
    Stdout *string `json:"stdout"`
    Stderr *string `json:"stderr"`
    Redacted bool `json:"redacted"`
    Truncated *bool `json:"truncated"`
    AbsentReason *string `json:"absentReason"`
}

type RunAttemptObservation struct {
    AttemptNumber int64 `json:"attemptNumber"`
    StartedAt *Timestamp `json:"startedAt"`
    NodeId *NodeId `json:"nodeId"`
    CommandId *string `json:"commandId"`
    StopReceiptId *string `json:"stopReceiptId"`
    ExitCode *int64 `json:"exitCode"`
    Reason *string `json:"reason"`
    EvidenceId *EvidenceId `json:"evidenceId"`
}

type RunAttemptList struct {
    Source string `json:"source"`
    RunId RunId `json:"runId"`
    Attempts []RunAttemptObservation `json:"attempts"`
    Count int64 `json:"count"`
    NextCursor *int64 `json:"nextCursor"`
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

type TerminalTicketAuthFrame struct {
    Ticket string `json:"ticket"`
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

type NodeStorageChannel struct {
    Tenant_id TenantId `json:"tenant_id"`
    Node_id NodeId `json:"node_id"`
    Recovery_epoch string `json:"recovery_epoch"`
    Version int64 `json:"version"`
    Endpoint string `json:"endpoint"`
    Certificate_sha256 string `json:"certificate_sha256"`
}

type NodeStorageItem struct {
    Location_id string `json:"location_id"`
    Version int64 `json:"version"`
    Relative_path string `json:"relative_path"`
    Byte_size int64 `json:"byte_size"`
    Checksum_sha256 *string `json:"checksum_sha256"`
}

type NodeStorageChallenge struct {
    Channel NodeStorageChannel `json:"channel"`
    Project_id ProjectId `json:"project_id"`
    Run_id RunId `json:"run_id"`
    Contribution_id string `json:"contribution_id"`
    Root_version int64 `json:"root_version"`
    Catalogued int64 `json:"catalogued"`
    Items []NodeStorageItem `json:"items"`
    Nonce string `json:"nonce"`
    Issued_at int64 `json:"issued_at"`
    Expires_at int64 `json:"expires_at"`
}

type NodeStorageSampleInput struct {
    Challenge string `json:"challenge"`
}

type NodeStorageSignedSample struct {
    Payload string `json:"payload"`
    Signature string `json:"signature"`
}

type NodeStorageRootConfig struct {
    Channel NodeStorageChannel `json:"channel"`
    Contribution_id string `json:"contribution_id"`
    Root_version int64 `json:"root_version"`
    Root string `json:"root"`
}

type RecordedStorageObservation struct {
    EvidenceId EvidenceId `json:"evidenceId"`
    CheckId string `json:"checkId"`
    ObservedAt int64 `json:"observedAt"`
    IntegrityVerified bool `json:"integrityVerified"`
    SampleHealthy bool `json:"sampleHealthy"`
    Sampled int64 `json:"sampled"`
    Mismatches int64 `json:"mismatches"`
    Unverifiable int64 `json:"unverifiable"`
    Examined int64 `json:"examined"`
    Unsampled int64 `json:"unsampled"`
}

type StorageObservationView struct {
    RequestId string `json:"requestId"`
    TenantId TenantId `json:"tenantId"`
    ProjectId ProjectId `json:"projectId"`
    RunId RunId `json:"runId"`
    ContributionId string `json:"contributionId"`
    Status string `json:"status"`
    CreatedAt string `json:"createdAt"`
    ExpiresAt int64 `json:"expiresAt"`
    CurrentHealth string `json:"currentHealth"`
    OperationalAcceptanceAssessed bool `json:"operationalAcceptanceAssessed"`
    Observation *RecordedStorageObservation `json:"observation"`
}

type ApprovalPage struct {
    Items []ApprovalView `json:"items"`
    NextCursor *ApprovalId `json:"nextCursor"`
}

type ShardObservedMember struct {
    Index int64 `json:"index"`
    RunId RunId `json:"runId"`
    NodeId NodeId `json:"nodeId"`
    Phase string `json:"phase"`
    State RunState `json:"state"`
    EvidenceId *EvidenceId `json:"evidenceId"`
}

type ShardResultMember struct {
    Index int64 `json:"index"`
    RunId RunId `json:"runId"`
    EvidenceId EvidenceId `json:"evidenceId"`
    ObjectId string `json:"objectId"`
    Sha256 string `json:"sha256"`
    SizeBytes int64 `json:"sizeBytes"`
}

type ShardObservation struct {
    PlanId ShardPlanId `json:"planId"`
    SourcePlanId *ShardPlanId `json:"sourcePlanId"`
    RootPlanId ShardPlanId `json:"rootPlanId"`
    Generation int64 `json:"generation"`
    ParentRunId *RunId `json:"parentRunId"`
    ParentState *RunState `json:"parentState"`
    StateAsOf *Timestamp `json:"stateAsOf"`
    AggregateManifestSha256 *string `json:"aggregateManifestSha256"`
    ShardCount int64 `json:"shardCount"`
    AllPhysicallyStopped bool `json:"allPhysicallyStopped"`
    AllSucceeded bool `json:"allSucceeded"`
    ResultManifest *[]ShardResultMember `json:"resultManifest"`
    ResultManifestSha256 *string `json:"resultManifestSha256"`
    Shards []ShardObservedMember `json:"shards"`
}

type ApprovalReviewView struct {
    Approval ApprovalView `json:"approval"`
    Workload WorkloadSpec `json:"workload"`
    RiskLevel string `json:"riskLevel"`
    PolicyDigest ActionDigest `json:"policyDigest"`
}

type SessionView struct {
    SubjectId string `json:"subjectId"`
    TenantId string `json:"tenantId"`
    ExpiresAt int64 `json:"expiresAt"`
}

type ModelId string

type ModelShard struct {
    Index int64 `json:"index"`
    Offset int64 `json:"offset"`
    ByteLength int64 `json:"byteLength"`
    Sha256 string `json:"sha256"`
}

type ModelReplica struct {
    ShardIndex int64 `json:"shardIndex"`
    LocationId string `json:"locationId"`
    LocationVersion int64 `json:"locationVersion"`
    NodeId NodeId `json:"nodeId"`
    State string `json:"state"`
}

type ModelRuntimeCompatibility struct {
    Adapter string `json:"adapter"`
    Version string `json:"version"`
    Modes []string `json:"modes"`
}

type ModelManifest struct {
    ModelId ModelId `json:"modelId"`
    Version string `json:"version"`
    Format string `json:"format"`
    TotalBytes int64 `json:"totalBytes"`
    ContentHash string `json:"contentHash"`
    Shards []ModelShard `json:"shards"`
    Replicas []ModelReplica `json:"replicas"`
    RuntimeCompatibility []ModelRuntimeCompatibility `json:"runtimeCompatibility"`
    LicensePolicy string `json:"licensePolicy"`
    Classification string `json:"classification"`
    Encryption string `json:"encryption"`
    KeyRef *string `json:"keyRef"`
}

type ModelExecutionRef struct {
    InputId string `json:"inputId"`
    RunId RunId `json:"runId"`
    ModelId ModelId `json:"modelId"`
    Version string `json:"version"`
    ManifestHash ActionDigest `json:"manifestHash"`
    InputSha256 ActionDigest `json:"inputSha256"`
    InputSizeBytes int64 `json:"inputSizeBytes"`
    NodeId NodeId `json:"nodeId"`
    Adapter string `json:"adapter"`
    AdapterVersion string `json:"adapterVersion"`
    Mode string `json:"mode"`
}

type ModelCommitObservation struct {
    ProjectId ProjectId `json:"projectId"`
    ModelId ModelId `json:"modelId"`
    Version string `json:"version"`
    ManifestHash string `json:"manifestHash"`
    SourceRunId RunId `json:"sourceRunId"`
    CommittedAt string `json:"committedAt"`
    CommitRecoveryEpoch string `json:"commitRecoveryEpoch"`
    Format string `json:"format"`
    TotalBytes int64 `json:"totalBytes"`
    ShardCount int64 `json:"shardCount"`
    LicensePolicy string `json:"licensePolicy"`
    Classification string `json:"classification"`
    Committed bool `json:"committed"`
    CurrentAvailability string `json:"currentAvailability"`
    RequiresExecutionRevalidation bool `json:"requiresExecutionRevalidation"`
}
