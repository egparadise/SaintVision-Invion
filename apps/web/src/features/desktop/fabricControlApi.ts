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
import type { ContributionPageResponse, ContributionResponse } from '@/contracts/contribution-page-response';
import type { ContributionRegistrationResponse } from '@/contracts/contribution-registration-response';
import type { DataLocationPageResponse, DataLocationResponse } from '@/contracts/data-location-page-response';
import type { DiscoveryCandidateResponse, DiscoveryCandidatesResponse } from '@/contracts/discovery-candidates-response';
import type { DiscoveryAdmissionResponse } from '@/contracts/discovery-admission-response';
import type { DiscoveryAnnouncementResponse } from '@/contracts/discovery-announcement-response';
import type { DiscoveryDeclineResponse } from '@/contracts/discovery-decline-response';
import type { HeartbeatAcceptedResponse } from '@/contracts/heartbeat-accepted-response';
import type { NodeLivenessSweepResponse } from '@/contracts/node-liveness-sweep-response';
import type { PoolCapacityResponse } from '@/contracts/pool-capacity-response';
import type { PoolListResponse } from '@/contracts/pool-list-response';
import type { PlacementPreviewResponse as PlacementPreviewWireResponse } from '@/contracts/placement-preview-response';
import type { DistributedPlanResponse } from '@/contracts/distributed-plan-response';
export type { DistributedPlanResponse };
import type { PoolMemberResponse } from '@/contracts/pool-member-response';
import type { PoolMemberRemovalResponse } from '@/contracts/pool-member-removal-response';
import type { NodeCapability as NodeCapabilityWire, NodeDetailResponse as NodeDetailWireResponse } from '@/contracts/node-detail-response';
import {
  type NodeResourceUsageResponse,
  type ObservedNodeResourceUsage,
  observedNodeResourceUsage,
} from '@/contracts/kernel-observation';
export type { ObservedNodeResourceUsage };

export type StorageContribution = ContributionResponse;
export type StorageLocation = DataLocationResponse;

export type PoolCapacity = PoolCapacityResponse;

export async function getPoolList(): Promise<PoolListResponse> {
  return apiClient<PoolListResponse>('/v1/pools');
}

/** UI view mapped from the generated placement-preview wire contract. */
export interface PlacementPreviewResponse {
  poolId: string;
  candidates: Array<{
    nodeId: string;
    hostname: string;
    availableCpuMillicores: number;
    availableRamBytes: number;
    availableGpuDevices: number;
    eligible: true;
  }>;
  candidateCount: number;
}

export type NodeCapability = NodeCapabilityWire;
export type NodeDetailResponse = NodeDetailWireResponse;

/** UI state grows as admission actions complete; the wire response stays candidate-only. */
export type DiscoveryCandidate = Omit<DiscoveryCandidateResponse, 'state' | 'verified'> & {
  state: 'pending' | 'candidate' | 'admitted' | 'declined';
  verified: boolean;
};

export type AdmissionResponse = DiscoveryAdmissionResponse;

// -----------------------------------------------------------------------------
// 1. Storage Contributions & Locations APIs
// -----------------------------------------------------------------------------

export async function getStorageContributions(
  nodeId?: string
): Promise<ContributionPageResponse> {
  const base = '/v1/storage/contributions';
  const url = nodeId ? `${base}?nodeId=${encodeURIComponent(nodeId)}` : base;
  return apiClient<ContributionPageResponse>(url);
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
): Promise<ContributionRegistrationResponse> {
  return apiClient<ContributionRegistrationResponse>('/v1/storage/contributions', {
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
): Promise<ContributionRegistrationResponse> {
  return apiClient<ContributionRegistrationResponse>(
    `/v1/storage/contributions/${contributionId}/activation`,
    {
      method: 'POST',
    }
  );
}

export async function revokeStorageContribution(
  contributionId: string
): Promise<ContributionRegistrationResponse> {
  return apiClient<ContributionRegistrationResponse>(
    `/v1/storage/contributions/${contributionId}`,
    {
      method: 'DELETE',
    }
  );
}

export async function getStorageLocations(
  contributionId?: string
): Promise<DataLocationPageResponse> {
  const base = '/v1/storage/locations';
  const url = contributionId ? `${base}?contributionId=${encodeURIComponent(contributionId)}` : base;
  return apiClient<DataLocationPageResponse>(url);
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
  const response = await apiClient<PlacementPreviewWireResponse>(url);
  return {
    poolId: response.poolId,
    candidateCount: response.candidateCount,
    candidates: response.candidates.map((candidate) => ({
      nodeId: candidate.nodeId,
      hostname: candidate.hostname,
      availableCpuMillicores: candidate.spare.cpuMillicores,
      availableRamBytes: candidate.spare.ramBytes,
      availableGpuDevices: candidate.spare.gpuDevices,
      eligible: true,
    })),
  };
}

export async function createPoolPlan(
  poolId: string,
  data: {
    runId: string;
    // UI vocabulary currently differs from the backend request enum. Keep this
    // input boundary explicit until Gemini maps the visible choices to domain
    // strategies; response typing remains generated and strict.
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
): Promise<PoolMemberResponse> {
  return apiClient<PoolMemberResponse>(
    `/v1/pools/${poolId}/members/${nodeId}`,
    {
      method: 'PUT',
    }
  );
}

export async function removePoolMember(
  poolId: string,
  nodeId: string
): Promise<PoolMemberRemovalResponse> {
  return apiClient<PoolMemberRemovalResponse>(
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
): Promise<HeartbeatAcceptedResponse> {
  return apiClient<HeartbeatAcceptedResponse>(
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

export async function triggerLivenessSweep(): Promise<NodeLivenessSweepResponse> {
  return apiClient<NodeLivenessSweepResponse>(
    '/v1/nodes/liveness-sweeps',
    {
      method: 'POST',
    }
  );
}

// -----------------------------------------------------------------------------
// 4. Discovery Announcements & Candidate Admission APIs
// -----------------------------------------------------------------------------

export async function getDiscoveryCandidates(
  includeStale: boolean = false
): Promise<DiscoveryCandidatesResponse> {
  const endpoint = includeStale
    ? '/v1/discovery/candidates?includeStale=true'
    : '/v1/discovery/candidates';
  return apiClient<DiscoveryCandidatesResponse>(endpoint);
}

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
): Promise<DiscoveryAnnouncementResponse> {
  return apiClient<DiscoveryAnnouncementResponse>('/v1/discovery/announcements', {
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
): Promise<DiscoveryDeclineResponse> {
  const base = `/v1/discovery/candidates/${announcementId}`;
  const url = reason ? `${base}?reason=${encodeURIComponent(reason)}` : base;
  return apiClient<DiscoveryDeclineResponse>(url, {
    method: 'DELETE',
  });
}

export async function getNodeResourceUsage(
  nodeId: string,
  projectId: string
): Promise<ObservedNodeResourceUsage> {
  const encProject = encodeURIComponent(projectId);
  const encNode = encodeURIComponent(nodeId);
  const raw = await apiClient<NodeResourceUsageResponse>(
    `/v1/projects/${encProject}/nodes/${encNode}/resource-usage`
  );
  return observedNodeResourceUsage(raw);
}


