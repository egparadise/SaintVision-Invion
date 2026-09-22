export type {
  ApprovalPage,
  ControlRunDetail,
  ControlRunPage,
  ControlRunView,
  RunState,
  NodeResourceUsageResponse,
  ResourceUsageMeasurement,
} from '../../../../packages/contracts-ts/src/index';

import type {
  ControlRunDetail,
  ControlRunPage,
  ControlRunView,
  NodeResourceUsageResponse,
  ResourceUsageMeasurement,
} from '../../../../packages/contracts-ts/src/index';
import type { RunItem } from './types';

/**
 * Projects a canonical wire run (ControlRunView | ControlRunDetail) into the UI RunItem ViewModel.
 * Fields absent from the wire remain undefined, rather than being synthesized.
 */
export function observedRun(view: ControlRunView | ControlRunDetail): RunItem {
  return {
    id: view.runId,
    projectId: view.projectId,
    state: view.state,
    version: view.version,
    attempt: view.attempt,
    resourceReleasePending: 'resourceReleasePending' in view ? Boolean(view.resourceReleasePending) : undefined,
  };
}

/**
 * Projects a canonical ControlRunPage wire response into UI RunItem array with pagination cursor.
 */
export function observedRunPage(page: ControlRunPage): { items: RunItem[]; nextCursor: string | null } {
  return {
    items: (page.items || []).map(observedRun),
    nextCursor: page.nextCursor ?? null,
  };
}

export interface ObservedResourceMeasurement {
  resourceId: string;
  kind: 'cpu' | 'memory' | 'gpu' | 'storage' | 'network';
  unit: 'millicores' | 'bytes' | 'devices' | 'bitsPerSecond';
  capacity: number;
  offered: number;
  reserved: number | null;
  spare: number | null;
  measured: boolean;
  observedAt: string | null;
}

export interface ObservedNodeResourceUsage {
  source: 'execution-kernel';
  nodeId: string;
  stateAsOf: string | null;
  resources: ObservedResourceMeasurement[];
}

/**
 * Projects a canonical NodeResourceUsageResponse wire response into UI ViewModel.
 * When a resource is unmeasured (measured === false), reserved, spare, and observedAt
 * remain null, strictly preventing synthetic zero values or forged client timestamps.
 */
export function observedNodeResourceUsage(view: NodeResourceUsageResponse): ObservedNodeResourceUsage {
  return {
    source: view.source,
    nodeId: view.nodeId,
    stateAsOf: typeof view.stateAsOf === 'string' ? view.stateAsOf : null,
    resources: (view.resources || []).map((m: ResourceUsageMeasurement) => ({
      resourceId: m.resourceId,
      kind: m.kind,
      unit: m.unit,
      capacity: typeof m.capacity === 'number' && Number.isFinite(m.capacity) ? m.capacity : 0,
      offered: typeof m.offered === 'number' && Number.isFinite(m.offered) ? m.offered : 0,
      reserved: m.measured && typeof m.reserved === 'number' && Number.isFinite(m.reserved) ? m.reserved : null,
      spare: m.measured && typeof m.spare === 'number' && Number.isFinite(m.spare) ? m.spare : null,
      measured: Boolean(m.measured),
      observedAt: m.measured && typeof m.observedAt === 'string' ? m.observedAt : null,
    })),
  };
}


