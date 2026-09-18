import { apiClient } from './client';
import type { ModelCommitObservation } from '../../../../../packages/contracts-ts/src';
export interface Location { locationId: string; uri: string; byteSize: number; checksumSha256: string | null }
export interface Page<T> { items: T[]; nextCursor: string | null }
export const replicaStates = ['ready', 'transferring', 'stale', 'corrupt', 'evicted'] as const;
export interface ReplicaObservation {
  locationId: string; observedAt: string; recordedStates: Record<typeof replicaStates[number], number>;
  totalRecords: number; currentAvailability: 'unknown'; requiresExecutionRevalidation: true;
}
const get = <T>(path: string, signal?: AbortSignal) => apiClient<T>(path, { method: 'GET', cache: 'no-store', signal });
export const fabricObservation = {
  locations(cursor?: string, signal?: AbortSignal) {
    const query = new URLSearchParams({ limit: '50' });
    if (cursor) query.set('cursor', cursor);
    const qs = query.toString();
    return get<Page<Location>>(`/v1/storage/locations${qs ? '?' + qs : ''}`, signal);
  },
  async resolve(uri: string, signal?: AbortSignal) {
    const qs = new URLSearchParams({ uri }).toString();
    const result = await get<{location: Location}>(`/v1/storage/resolve${qs ? '?' + qs : ''}`, signal);
    if (result.location?.uri !== uri) throw new Error('URI response mismatch');
    return result.location;
  },
  async replicas(location: Location, signal?: AbortSignal) {
    const qs = new URLSearchParams({ uri: location.uri }).toString();
    const { observation } = await get<{observation: ReplicaObservation}>(`/v1/storage/replica-status${qs ? '?' + qs : ''}`, signal);
    if (observation?.locationId !== location.locationId || observation.currentAvailability !== 'unknown'
      || observation.requiresExecutionRevalidation !== true || !replicaStates.every(state =>
        Number.isSafeInteger(observation.recordedStates?.[state]) && observation.recordedStates[state] >= 0)
      || replicaStates.reduce((sum, state) => sum + observation.recordedStates[state], 0) !== observation.totalRecords)
      throw new Error('Replica observation mismatch');
    return observation;
  },
  async model(projectId: string, modelId: string, version: string, signal?: AbortSignal) {
    const path = [projectId, modelId, version].map(encodeURIComponent);
    const result = await get<ModelCommitObservation>(`/v1/projects/${path[0]}/models/${path[1]}/versions/${path[2]}/commitment`, signal);
    if (result.projectId !== projectId || result.modelId !== modelId || result.version !== version
      || result.committed !== true || result.currentAvailability !== 'unknown' || result.requiresExecutionRevalidation !== true)
      throw new Error('Model observation mismatch');
    return result;
  },
};
