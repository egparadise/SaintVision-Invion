import { apiClient } from './client';
import type { ReleaseManifestResponse, ReleaseComponentResponse } from '@/contracts/release-manifest-response';
import type { ReleaseManifestPageResponse } from '@/contracts/release-manifest-page-response';
import type { ReleaseManifestDetailResponse, ReleaseAcceptanceResponse } from '@/contracts/release-manifest-detail-response';

export type {
  ReleaseManifestResponse,
  ReleaseComponentResponse,
  ReleaseManifestPageResponse,
  ReleaseManifestDetailResponse,
  ReleaseAcceptanceResponse,
};

export interface FetchReleaseManifestsOptions {
  cursor?: string | null;
  limit?: number;
  signal?: AbortSignal;
}

/**
 * Validates a single ReleaseManifestResponse against the canonical contract.
 */
export function isValidReleaseManifest(val: unknown): val is ReleaseManifestResponse {
  if (!val || typeof val !== 'object' || Array.isArray(val)) return false;
  const m = val as Record<string, unknown>;
  return (
    typeof m.releaseId === 'string' &&
    m.releaseId.length > 0 &&
    typeof m.version === 'string' &&
    m.version.length > 0 &&
    typeof m.manifestSha256 === 'string' &&
    /^[0-9a-f]{64}$/.test(m.manifestSha256) &&
    typeof m.componentCount === 'number' &&
    m.componentCount >= 0 &&
    typeof m.operatorSignOff === 'boolean' &&
    typeof m.acceptanceCount === 'number' &&
    m.acceptanceCount >= 0 &&
    typeof m.createdAt === 'string' &&
    (m.components === undefined || Array.isArray(m.components))
  );
}

/**
 * Fetch a page of recorded release manifests.
 * Canonical route: GET /v1/release-manifests
 * Empty tenant returns an empty list (items: []), never 404.
 */
export async function fetchReleaseManifests(
  options: FetchReleaseManifestsOptions = {}
): Promise<ReleaseManifestPageResponse> {
  const query = new URLSearchParams();
  if (options.cursor) {
    query.set('cursor', options.cursor);
  }
  if (typeof options.limit === 'number' && Number.isInteger(options.limit) && options.limit > 0) {
    query.set('limit', String(Math.min(options.limit, 200)));
  }

  const queryString = query.toString();
  const endpoint = queryString ? `/v1/release-manifests?${queryString}` : '/v1/release-manifests';

  const res = await apiClient<ReleaseManifestPageResponse>(endpoint, {
    method: 'GET',
    signal: options.signal,
  });

  if (!res || typeof res !== 'object' || (res.items !== undefined && !Array.isArray(res.items))) {
    throw new Error('ReleaseManifestPageResponse contract violation: items must be an array');
  }

  if (res.items && !res.items.every(isValidReleaseManifest)) {
    throw new Error('ReleaseManifestPageResponse contract violation: invalid item in items array');
  }

  return {
    items: res.items || [],
    nextCursor: res.nextCursor ?? null,
  };
}

/**
 * Fetch a specific release manifest detail with recorded acceptances.
 * Canonical route: GET /v1/release-manifests/{release_id}
 * Non-existent or other-tenant release returns RFC 9457 ProblemDetails 404 (RES-RELEASE-NOT-FOUND).
 */
export async function fetchReleaseManifestDetail(
  releaseId: string,
  signal?: AbortSignal
): Promise<ReleaseManifestDetailResponse> {
  if (!releaseId || typeof releaseId !== 'string' || !releaseId.trim()) {
    throw new Error('releaseId must be a non-empty string');
  }

  const endpoint = `/v1/release-manifests/${encodeURIComponent(releaseId.trim())}`;
  const res = await apiClient<ReleaseManifestDetailResponse>(endpoint, {
    method: 'GET',
    signal,
  });

  if (!res || typeof res !== 'object' || !isValidReleaseManifest(res.release)) {
    throw new Error('ReleaseManifestDetailResponse contract violation: missing or invalid release field');
  }

  if (res.acceptances !== undefined && !Array.isArray(res.acceptances)) {
    throw new Error('ReleaseManifestDetailResponse contract violation: acceptances must be an array');
  }

  return res;
}
