/**
 * SaintVision Canonical Control Plane Fabric & Storage Operations API
 *
 * Exposes the 16 canonical endpoints landed in CX-01:
 * - Storage Contributions & Locations:
 *     GET /v1/storage/contributions
 *     POST /v1/storage/contributions
 *     DELETE /v1/storage/contributions/{id}
 *     POST /v1/storage/contributions/{id}/activation
 *     GET /v1/storage/locations
 * - Resource Pools & Distributed Placement:
 *     GET /v1/pools/{id}/capacity
 *     GET /v1/pools/{id}/placement-preview
 *     POST /v1/pools/{id}/plans
 *     PUT /v1/pools/{id}/members/{node_id}
 *     DELETE /v1/pools/{id}/members/{node_id}
 * - Node Telemetry & Liveness Sweeps:
 *     GET /v1/nodes/{node_id}
 *     POST /v1/nodes/{node_id}/heartbeats
 *     POST /v1/nodes/liveness-sweeps
 * - Node Discovery & Candidate Admission:
 *     POST /v1/discovery/announcements
 *     POST /v1/discovery/candidates/{id}/admission
 *     DELETE /v1/discovery/candidates/{id}
 */

import { apiClient } from '@/shared/api/client';

export interface StorageContribution {
  contributionId: string;
  nodeId: string;
  declaredPath: string;
  normalizedPath: string;
  mode: 'read_write' | 'read_only';
  status: 'active' | 'revoked';
  capacityBytes: number;
  availableBytes: number;
  registeredAt: string;
}

export interface StorageLocation {
  locationId: string;
  contributionId: string;
  uri: string;
  kind: string;
  relativePath: string;
  byteSize: number;
  checksumSha256: string | null;
  ready: boolean;
  verifiedAt: string;
  retentionPinnedUntil: string | null;
}

export interface PoolCapacity {
  totalOffered: { cpuMillicores: number; ramBytes: number; gpuDevices: number };
  largestSingleNode: { cpuMillicores: number; ramBytes: number; gpuDevices: number };
  spareNow: { cpuMillicores: number; ramBytes: number; gpuDevices: number };
  units?: Record<string, string>;
}

export interface PlacementCandidate {
  nodeId: string;
  hostname: string;
  availableCpuMillicores: number;
  availableRamBytes: number;
  availableGpuDevices: number;
  eligible: boolean;
  rejectionReasons?: string[];
}

export interface PlacementPreviewResponse {
  poolId: string;
  candidates: PlacementCandidate[];
  candidateCount: number;
  units?: Record<string, string>;
}

export interface DistributedPlanPlacement {
  shardIndex: number;
  nodeId: string;
  assignedCpuMillicores: number;
  assignedRamBytes: number;
  assignedGpuDevices: number;
}

export interface DistributedPlanResponse {
  planId: string;
  runId: string;
  strategy: string;
  shardCount: number;
  units?: Record<string, string>;
  placements: DistributedPlanPlacement[];
}

export interface NodeCapability {
  capabilityId: string;
  kind: string;
  deviceIndex: number | null;
  vendor: string | null;
  model: string | null;
  totalQuantity: number;
  unit: string;
  divisible: boolean;
}

export interface NodeDetailResponse {
  node: {
    nodeId: string;
    hostname: string;
    osType: string;
    osVersion: string;
    agentVersion: string;
    status: string;
    enrolledAt: string;
    lastHeartbeatAt: string;
    heartbeatSequence: number;
    labels: Record<string, string>;
  };
  capabilities: NodeCapability[];
}

export interface DiscoveryCandidate {
  announcementId: string;
  sourceIp: string;
  claimedInstanceId: string;
  claimedHostname: string;
  claimedOsType: string;
  claimedOsVersion?: string;
  claimedAgentVersion?: string;
  claimedCpuCores: number;
  claimedRamBytes: number;
  claimedGpuCount: number;
  claimedLabels: Record<string, string>;
  verified: boolean;
  state: 'pending' | 'admitted' | 'declined';
  announcedAt: string;
}

export interface AdmissionResponse {
  announcementId: string;
  bootstrapToken: string;
  expiresAt: string;
  next: string;
}

// -----------------------------------------------------------------------------
// 1. Storage Contributions & Locations APIs
// -----------------------------------------------------------------------------

export async function getStorageContributions(
  nodeId?: string
): Promise<{ items: StorageContribution[]; nextCursor: string | null }> {
  const base = '/v1/storage/contributions';
  const url = nodeId ? `${base}?nodeId=${encodeURIComponent(nodeId)}` : base;
  return apiClient<{ items: StorageContribution[]; nextCursor: string | null }>(url);
}

export async function registerStorageContribution(
  data: {
    nodeId: string;
    declaredPath: string;
    mode: 'read_write' | 'read_only';
    capacityBytes: number;
    availableBytes: number;
  },
  idempotencyKey?: string
): Promise<{ contribution: StorageContribution }> {
  return apiClient<{ contribution: StorageContribution }>('/v1/storage/contributions', {
    method: 'POST',
    body: JSON.stringify({
      nodeId: data.nodeId,
      declaredPath: data.declaredPath,
      mode: data.mode,
      capacityBytes: data.capacityBytes,
      availableBytes: data.availableBytes,
    }),
    idempotencyKey,
  });
}

export async function activateStorageContribution(
  contributionId: string
): Promise<{ contribution: StorageContribution }> {
  return apiClient<{ contribution: StorageContribution }>(
    `/v1/storage/contributions/${contributionId}/activation`,
    {
      method: 'POST',
    }
  );
}

export async function revokeStorageContribution(
  contributionId: string
): Promise<{ contribution: StorageContribution }> {
  return apiClient<{ contribution: StorageContribution }>(
    `/v1/storage/contributions/${contributionId}`,
    {
      method: 'DELETE',
    }
  );
}

export async function getStorageLocations(
  contributionId?: string
): Promise<{ items: StorageLocation[]; nextCursor: string | null }> {
  const base = '/v1/storage/locations';
  const url = contributionId ? `${base}?contributionId=${encodeURIComponent(contributionId)}` : base;
  return apiClient<{ items: StorageLocation[]; nextCursor: string | null }>(url);
}

// -----------------------------------------------------------------------------
// 2. Resource Pools & Placement Plans APIs
// -----------------------------------------------------------------------------

export async function getPoolCapacity(poolId: string): Promise<PoolCapacity> {
  return apiClient<PoolCapacity>(`/v1/pools/${poolId}/capacity`);
}

export async function getPoolPlacementPreview(
  poolId: string,
  requirements?: { cpuMillicores?: number; ramBytes?: number; gpuDevices?: number }
): Promise<PlacementPreviewResponse> {
  const base = `/v1/pools/${poolId}/placement-preview`;
  const params = new URLSearchParams();
  if (requirements?.cpuMillicores !== undefined)
    params.set('cpuMillicores', requirements.cpuMillicores.toString());
  if (requirements?.ramBytes !== undefined)
    params.set('ramBytes', requirements.ramBytes.toString());
  if (requirements?.gpuDevices !== undefined)
    params.set('gpuDevices', requirements.gpuDevices.toString());
  const qs = params.toString();
  const url = qs ? `${base}?${qs}` : base;
  return apiClient<PlacementPreviewResponse>(url);
}

export async function createPoolPlan(
  poolId: string,
  data: {
    runId: string;
    strategy: 'binpack' | 'spread';
    shardCount: number;
    shardCpuMillicores: number;
    shardRamBytes: number;
    shardGpuDevices: number;
    splittableDeclared: boolean;
  }
): Promise<DistributedPlanResponse> {
  return apiClient<DistributedPlanResponse>(`/v1/pools/${poolId}/plans`, {
    method: 'POST',
    body: JSON.stringify({
      runId: data.runId,
      strategy: data.strategy,
      shardCount: data.shardCount,
      shardCpuMillicores: data.shardCpuMillicores,
      shardRamBytes: data.shardRamBytes,
      shardGpuDevices: data.shardGpuDevices,
      splittableDeclared: data.splittableDeclared,
    }),
  });
}

export async function addPoolMember(
  poolId: string,
  nodeId: string
): Promise<{ poolId: string; nodeId: string; member: boolean }> {
  return apiClient<{ poolId: string; nodeId: string; member: boolean }>(
    `/v1/pools/${poolId}/members/${nodeId}`,
    {
      method: 'PUT',
    }
  );
}

export async function removePoolMember(
  poolId: string,
  nodeId: string
): Promise<{ poolId: string; nodeId: string; removed: boolean }> {
  return apiClient<{ poolId: string; nodeId: string; removed: boolean }>(
    `/v1/pools/${poolId}/members/${nodeId}`,
    {
      method: 'DELETE',
    }
  );
}

// -----------------------------------------------------------------------------
// 3. Node Telemetry, Detail & Liveness APIs
// -----------------------------------------------------------------------------

export async function getNodeDetail(nodeId: string): Promise<NodeDetailResponse> {
  return apiClient<NodeDetailResponse>(`/v1/nodes/${nodeId}`);
}

export async function postNodeHeartbeat(
  nodeId: string,
  data: {
    sequence: number;
    observations?: Array<{ capabilityId: string; usedQuantity: number; unit: string }>;
  }
): Promise<{ nodeId: string; applied: boolean; heartbeatSequence: number }> {
  return apiClient<{ nodeId: string; applied: boolean; heartbeatSequence: number }>(
    `/v1/nodes/${nodeId}/heartbeats`,
    {
      method: 'POST',
      body: JSON.stringify({
        sequence: data.sequence,
        observations: data.observations || [],
      }),
    }
  );
}

export async function triggerLivenessSweep(): Promise<{
  markedLost: number;
  timeoutSeconds: number;
}> {
  return apiClient<{ markedLost: number; timeoutSeconds: number }>(
    '/v1/nodes/liveness-sweeps',
    {
      method: 'POST',
    }
  );
}

// -----------------------------------------------------------------------------
// 4. Discovery Announcements & Candidate Admission APIs
// -----------------------------------------------------------------------------

export async function broadcastAnnouncement(
  data: {
    instanceId: string;
    hostname: string;
    osType: 'windows' | 'linux';
    osVersion: string;
    agentVersion: string;
    cpuCores: number;
    ramBytes: number;
    gpuCount: number;
    labels?: Record<string, string>;
  },
  tenantId: string
): Promise<{ accepted: boolean; state: string }> {
  return apiClient<{ accepted: boolean; state: string }>('/v1/discovery/announcements', {
    method: 'POST',
    headers: {
      'X-Inv-Tenant': tenantId,
    },
    body: JSON.stringify({
      instanceId: data.instanceId,
      hostname: data.hostname,
      osType: data.osType,
      osVersion: data.osVersion,
      agentVersion: data.agentVersion,
      cpuCores: data.cpuCores,
      ramBytes: data.ramBytes,
      gpuCount: data.gpuCount,
      labels: data.labels || {},
    }),
  });
}

export async function admitDiscoveryCandidate(
  announcementId: string
): Promise<AdmissionResponse> {
  return apiClient<AdmissionResponse>(
    `/v1/discovery/candidates/${announcementId}/admission`,
    {
      method: 'POST',
    }
  );
}

export async function declineDiscoveryCandidate(
  announcementId: string,
  reason?: string
): Promise<{ announcementId: string; state: string }> {
  const base = `/v1/discovery/candidates/${announcementId}`;
  const url = reason ? `${base}?reason=${encodeURIComponent(reason)}` : base;
  return apiClient<{ announcementId: string; state: string }>(url, {
    method: 'DELETE',
  });
}
