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
