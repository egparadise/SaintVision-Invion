/**
 * SaintVision Virtual Computer Fabric Contracts
 * Architecture Reference: ARCH-WEB-FABRIC-001 & ROADMAP-VIRTUAL-COMPUTER-001
 * Strict Invariant: Logical aggregate view is provided alongside physical node topology.
 * No false claims of unified hardware buses or magical single-device VRAM pooling.
 */

// ==========================================
// 1. Web Desktop Shell & Window Manager Types
// ==========================================

export type AppId =
  | 'my-computer'
  | 'file-explorer'
  | 'model-studio'
  | 'terminal'
  | 'developer-studio'
  | 'approvals'
  | 'cluster-overview'
  | 'settings';

export interface WindowPosition {
  x: number;
  y: number;
}

export interface WindowSize {
  width: number;
  height: number;
}

export interface DesktopWindow {
  id: string;
  appId: AppId;
  title: string;
  icon: string;
  isOpen: boolean;
  isMinimized: boolean;
  isMaximized: boolean;
  zIndex: number;
  position: WindowPosition;
  size: WindowSize;
  params?: Record<string, any>;
}

export interface DesktopNotification {
  id: string;
  title: string;
  message: string;
  level: 'info' | 'success' | 'warning' | 'error';
  timestamp: string;
  read: boolean;
  actionUrl?: string;
}

export interface VirtualDesktopState {
  activeWindowId: string | null;
  windows: DesktopWindow[];
  theme: 'light' | 'dark';
  wallpaper: string;
  viewMode: 'desktop' | 'portal';
  notifications: DesktopNotification[];
}

// ==========================================
// 2. My Computer / Resource Explorer Types (VF-GM-02)
// ==========================================

export interface LogicalResourceSummary {
  totalCores: number;
  allocatableCores: number;
  usedCores: number;
  totalMemoryBytes: number;
  allocatableMemoryBytes: number;
  usedMemoryBytes: number;
  totalGpuCount: number;
  totalGpuVramBytes: number;
  usedGpuVramBytes: number;
  totalStorageBytes: number;
  usedStorageBytes: number;
  onlineNodeCount: number;
  totalNodeCount: number;
  disclaimer: string;
}

export interface PhysicalNodeTopology {
  id: string;
  hostname: string;
  os: 'windows' | 'linux';
  ipAddress: string;
  status: 'online' | 'degraded' | 'offline' | 'draining';
  schedulable: boolean;
  observationOnly: boolean;
  cpuCores: number;
  cpuUsagePercent: number;
  memoryTotalBytes: number;
  memoryUsedBytes: number;
  allocatableCores: number;
  allocatableMemoryBytes: number;
  gpus: Array<{
    name: string;
    vramTotalBytes: number;
    vramUsedBytes: number;
    driverVersion: string;
    cudaComputeCapability?: string;
  }>;
  contributedStorageDrives: Array<{
    mountPath: string;
    driveLabel: string;
    totalBytes: number;
    usedBytes: number;
    storageClass: 'nvme_ssd' | 'sata_ssd' | 'hdd' | 'object_store';
  }>;
  localityZone: string;
  heartbeatAt: string;
}

export interface FabricInterconnect {
  sourceNodeId: string;
  targetNodeId: string;
  latencyMs: number;
  bandwidthGbps: number;
  transport: 'lan_mtls' | 'local_shm';
  isHealthy: boolean;
}

// ==========================================
// 3. inv:// File Explorer Types (VF-GM-03)
// ==========================================

export type InvNamespace = 'workspaces' | 'models' | 'datasets' | 'artifacts';

export interface InvReplicaLocation {
  nodeId: string;
  nodeHostname: string;
  status: 'healthy' | 'stale' | 'missing' | 'unreachable';
  localPath: string;
  updatedAt: string;
}

export interface InvFileItem {
  uri: string; // e.g. inv://models/pacs-segmentation-v2/1.0.0/model.safetensors
  namespace: InvNamespace;
  relativePath: string;
  name: string;
  type: 'file' | 'directory';
  sizeBytes: number;
  version: string;
  contentHash: string; // SHA-256
  contentType: string;
  replicas: InvReplicaLocation[];
  requiredReplicas: number;
  isPinned: boolean;
  classification: 'public' | 'internal' | 'confidential' | 'restricted';
  updatedAt: string;
  content?: string | Uint8Array;
  source?: 'kernel-checkout' | 'demo' | 'user';
}

export interface InvDriveSummary {
  namespace: InvNamespace;
  label: string;
  uriPrefix: string;
  description: string;
  totalItems: number;
  totalSizeBytes: number;
  icon: string;
}

// ==========================================
// 4. Model Studio & Shard Fabric Types (VF-GM-04)
// ==========================================

export type ModelFormat = 'safetensors' | 'gguf' | 'pytorch' | 'onnx';

export type ExecutionPlanMode =
  | 'single_node'
  | 'request_routing'
  | 'data_parallel'
  | 'tensor_pipeline_parallel'
  | 'cpu_gpu_offload';

export interface ModelShard {
  shardIndex: number;
  shardId: string;
  byteRange: string;
  layers: string;
  contentHash: string; // SHA-256
  sizeBytes: number;
  replicas: Array<{
    nodeId: string;
    nodeHostname: string;
    status: 'healthy' | 'repairing' | 'missing';
  }>;
}

export interface ModelManifest {
  modelId: string;
  name: string;
  version: string;
  format: ModelFormat;
  totalBytes: number;
  contentHash: string; // SHA-256 of entire manifest/weights
  shards: ModelShard[];
  runtimeCompatibility: string[];
  licensePolicy: string;
  classification: string;
  encryption: {
    enabled: boolean;
    keyRef?: string;
  };
  supportedModes: ExecutionPlanMode[];
  status: 'committed' | 'importing' | 'degraded' | 'repairing';
  createdAt: string;
  updatedAt: string;
}

export interface ExecutionPlanNodeAssignment {
  nodeId: string;
  nodeHostname: string;
  role: string;
  vramRequiredBytes: number;
  assignedShards: number[];
  isEligible: boolean;
}

export interface ExecutionPlan {
  modelId: string;
  modelVersion: string;
  mode: ExecutionPlanMode;
  assignedNodes: ExecutionPlanNodeAssignment[];
  interconnectMinGbps: number;
  localityScore: number;
  explain: string;
  isFeasible: boolean;
  rejectionReason?: string;
}

// ==========================================
// 5. Terminal / IDE Session Types (VF-GM-05)
// ==========================================

export type TerminalShellType = 'powershell' | 'bash' | 'zsh' | 'cmd';

export interface TerminalSessionSpec {
  sessionId: string;
  workspaceId: string;
  targetNodeId: string;
  targetNodeHostname: string;
  shellType: TerminalShellType;
  ticket?: string;
  ticketExpiresAt?: string;
  status: 'idle' | 'connecting' | 'connected' | 'disconnected' | 'expired' | 'permission_denied';
  sequenceNumber: number;
  idleTimeoutSeconds: number;
  createdAt: string;
}
