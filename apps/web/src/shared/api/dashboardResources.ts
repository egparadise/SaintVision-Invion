import { apiClient, getAuthToken } from './client';
import { observedNodeResourceUsage, type ObservedResourceMeasurement, type NodeResourceUsageResponse } from '@/contracts/kernel-observation';
import type { DashboardNodeResourceObservation } from '@/contracts/dashboard-resources';
import type { NodeItem } from '@/contracts/types';

export const RESOURCE_MAX_AGE_MS = 60000;
const kinds = ['cpu', 'memory', 'gpu', 'storage', 'network'];
const units = ['millicores', 'bytes', 'devices', 'bitsPerSecond'];
const quantity = (value: unknown): value is number => Number.isSafeInteger(value) && (value as number) >= 0;
const record = (value: unknown): value is Record<string, unknown> => !!value && typeof value === 'object' && !Array.isArray(value);
const closed = (value: Record<string, unknown>, keys: string[]) => Object.keys(value).length === keys.length && keys.every(key => Object.hasOwn(value, key));

export function resourceTimestamp(value: unknown): value is string {
  if (typeof value !== 'string') return false;
  const match = /^(\d{4})-(\d{2})-(\d{2})[Tt](\d{2}):(\d{2}):(\d{2})(?:\.\d+)?(?:[Zz]|[+-](\d{2}):(\d{2}))$/.exec(value);
  if (!match || !Number.isFinite(Date.parse(value))) return false;
  const [, y, m, d, h, minute, second, offsetH = '0', offsetM = '0'] = match;
  const year = Number(y), month = Number(m), day = Number(d);
  const days = [31, year % 4 === 0 && (year % 100 !== 0 || year % 400 === 0) ? 29 : 28, 31, 30, 31, 30, 31, 31, 30, 31, 30, 31];
  return month >= 1 && month <= 12 && day >= 1 && day <= days[month - 1] &&
    Number(h) < 24 && Number(minute) < 60 && Number(second) < 60 && Number(offsetH) < 24 && Number(offsetM) < 60;
}

export function resourceClockCurrent(value: string | null, now: number): boolean {
  if (!resourceTimestamp(value)) return false;
  const age = now - Date.parse(value);
  return age >= -5000 && age <= RESOURCE_MAX_AGE_MS;
}

/** Preserve good dimensions while explicitly reporting malformed resource rows. */
export function checkedDashboardResources(value: unknown, projectId: string, nodeId: string): DashboardNodeResourceObservation {
  if (!record(value) || !closed(value, ['source', 'nodeId', 'stateAsOf', 'resources']) ||
      value.source !== 'execution-kernel' || value.nodeId !== nodeId ||
      !(value.stateAsOf === null || resourceTimestamp(value.stateAsOf)) ||
      !Array.isArray(value.resources) || value.resources.length > 1024) throw new Error('Node resource observation binding/shape mismatch');
  const issues: DashboardNodeResourceObservation['issues'] = [];
  const valid: NodeResourceUsageResponse['resources'] = [];
  const seen = new Set<string>();
  for (const item of value.resources) {
    const kind = record(item) && typeof item.kind === 'string' ? item.kind : 'unknown';
    if (!record(item) || !closed(item, ['resourceId', 'kind', 'unit', 'capacity', 'offered', 'reserved', 'spare', 'measured', 'observedAt']) ||
        typeof item.resourceId !== 'string' || !/^res_[0-9A-HJKMNP-TV-Z]{26}$/.test(item.resourceId) ||
        !kinds.includes(kind) || typeof item.unit !== 'string' || !units.includes(item.unit) ||
        !quantity(item.capacity) || !quantity(item.offered) || typeof item.measured !== 'boolean' ||
        (item.measured ? !quantity(item.reserved) || !quantity(item.spare) || !resourceTimestamp(item.observedAt)
          : item.reserved !== null || item.spare !== null || item.observedAt !== null)) {
      issues.push({ kind, message: '자원 응답 형식 오류' });
      continue;
    }
    if (seen.has(item.resourceId)) {
      issues.push({ kind, message: '중복 resourceId' });
      // A duplicated allocation cannot contribute to any aggregate.
      const duplicate = valid.find(row => row.resourceId === item.resourceId);
      if (duplicate) issues.push({ kind: duplicate.kind, message: '중복 resourceId' });
      continue;
    }
    seen.add(item.resourceId);
    valid.push(item as unknown as NodeResourceUsageResponse['resources'][number]);
  }
  return { projectId, error: null, issues, usage: observedNodeResourceUsage({
    source: 'execution-kernel', nodeId, stateAsOf: value.stateAsOf as string | null, resources: valid,
  }) };
}

/** Four workers per finite poll; abort also settles a transport that ignores cancellation. */
export function assertDashboardIdentities(nodes: NodeItem[]): void {
  if (new Set(nodes.map(node => node.id)).size !== nodes.length || nodes.some(node => !node.id)) throw new Error('Node identity list mismatch');
}

export async function joinDashboardResources(nodes: NodeItem[], projectId: string, signal: AbortSignal,
  previous: ReadonlyMap<string, DashboardNodeResourceObservation>, onNode?: (node: NodeItem) => void): Promise<NodeItem[]> {
  assertDashboardIdentities(nodes);
  const limit = Math.min(nodes.length, 64);
  const joined = nodes.map(node => ({ ...node, resourceObservation: { projectId, usage: null, issues: [],
    error: '이번 관측 주기 조회 상한(64대) / 미관측' } as DashboardNodeResourceObservation }));
  const credential = getAuthToken();
  let next = 0;
  joined.slice(limit).forEach(node => onNode?.(node));
  await Promise.all(Array.from({ length: Math.min(4, nodes.length) }, async () => {
    while (!signal.aborted && getAuthToken() === credential && next < limit) {
      const index = next++;
      const node = nodes[index];
      let observation: DashboardNodeResourceObservation;
      const child = new AbortController();
      const cancel = () => child.abort(signal.reason);
      signal.addEventListener('abort', cancel, { once: true });
      const timer = setTimeout(() => child.abort(new Error('자원 관측 시간 초과 (4s)')), 4000);
      try {
        const value = await new Promise<unknown>((resolve, reject) => {
          const abort = () => reject(child.signal.reason ?? new Error('Node resource request aborted'));
          child.signal.addEventListener('abort', abort, { once: true });
          if (signal.aborted) { cancel(); return; }
          apiClient(`/v1/projects/${encodeURIComponent(projectId)}/nodes/${encodeURIComponent(node.id)}/resource-usage`,
            { signal: child.signal }).then(resolve, reject).finally(() => child.signal.removeEventListener('abort', abort));
        });
        observation = checkedDashboardResources(value, projectId, node.id);
      } catch (error) {
        const old = previous.get(node.id);
        observation = { projectId, usage: old?.projectId === projectId ? old.usage : null,
          issues: old?.projectId === projectId ? old.issues : [], error: error instanceof Error ? error.message : '자원 관측 실패' };
      } finally { clearTimeout(timer); signal.removeEventListener('abort', cancel); }
      joined[index] = { ...node, resourceObservation: observation };
      onNode?.(joined[index]);
    }
  }));
  if (signal.aborted || getAuthToken() !== credential) {
    for (let index = next; index < limit; index++) {
      const node = nodes[index], old = previous.get(node.id);
      onNode?.({ ...node, resourceObservation: { projectId, usage: old?.projectId === projectId ? old.usage : null,
        issues: old?.projectId === projectId ? old.issues : [], error: '자원 조회 취소 / 현재 관측 미확인' } });
    }
    throw new Error('Node resource poll aborted/auth changed');
  }
  return joined;
}

export function currentResourceRows(observation: DashboardNodeResourceObservation | undefined, kind: string,
  unit: string, now: number): ObservedResourceMeasurement[] {
  if (!observation?.usage || observation.error || !resourceClockCurrent(observation.usage.stateAsOf, now) ||
      observation.issues.some(issue => issue.kind === kind || issue.kind === 'unknown')) return [];
  return observation.usage.resources.filter(row => row.kind === kind && row.unit === unit && row.measured &&
    resourceClockCurrent(row.observedAt, now));
}
