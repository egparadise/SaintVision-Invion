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

export class ContractViolationError extends Error {
  readonly isContractViolation = true;
  readonly code = 'CONTRACT-VIOLATION';

  constructor(message: string) {
    super(message);
    this.name = 'ContractViolationError';
  }
}

export const ALLOWED_COMPONENT_KEYS = new Set(['name', 'kind', 'digest']);
export const ALLOWED_MANIFEST_KEYS = new Set([
  'releaseId',
  'version',
  'componentCount',
  'manifestSha256',
  'components',
  'createdAt',
  'operatorSignOff',
  'operatorSignOffBlockedBy',
  'requiredDistinctOperatorCount',
  'confirmedOperatorCount',
  'matchingAcceptedUserCount',
  'acceptanceCount',
]);
export const ALLOWED_ACCEPTANCE_KEYS = new Set([
  'acceptanceId',
  'acceptanceIdRef',
  'outcome',
  'acceptedManifestSha256',
  'manifestMatches',
  'decidedAt',
  'knownLimitations',
]);
export const ALLOWED_PAGE_KEYS = new Set(['items', 'nextCursor']);
export const ALLOWED_DETAIL_KEYS = new Set(['release', 'acceptances']);

export const VALID_OUTCOMES = new Set(['accepted', 'conditional', 'rejected']);

function hasOnlyAllowedKeys(obj: Record<string, unknown>, allowed: Set<string>): boolean {
  return Object.keys(obj).every((key) => allowed.has(key));
}

function isValidIsoDateTime(val: unknown): boolean {
  if (typeof val !== 'string' || val.length === 0) return false;
  const time = Date.parse(val);
  return !Number.isNaN(time);
}

/**
 * Validates a single ReleaseComponentResponse against the canonical contract.
 * JSON schema: additionalProperties: false, required: [name, kind, digest]
 */
export function isValidReleaseComponent(val: unknown): val is ReleaseComponentResponse {
  if (!val || typeof val !== 'object' || Array.isArray(val)) return false;
  const c = val as Record<string, unknown>;
  if (!hasOnlyAllowedKeys(c, ALLOWED_COMPONENT_KEYS)) return false;

  return (
    typeof c.name === 'string' &&
    c.name.length >= 1 &&
    c.name.length <= 200 &&
    typeof c.kind === 'string' &&
    c.kind.length >= 1 &&
    c.kind.length <= 64 &&
    typeof c.digest === 'string' &&
    c.digest.length >= 1 &&
    c.digest.length <= 200
  );
}

/**
 * Validates a single ReleaseManifestResponse against the canonical contract.
 * JSON schema: additionalProperties: false, componentCount >= 1, manifestSha256 64-hex, etc.
 */
export function isValidReleaseManifest(val: unknown): val is ReleaseManifestResponse {
  if (!val || typeof val !== 'object' || Array.isArray(val)) return false;
  const m = val as Record<string, unknown>;
  if (!hasOnlyAllowedKeys(m, ALLOWED_MANIFEST_KEYS)) return false;

  if (
    typeof m.releaseId !== 'string' ||
    m.releaseId.length < 1 ||
    m.releaseId.length > 64 ||
    typeof m.version !== 'string' ||
    m.version.length < 1 ||
    m.version.length > 64 ||
    typeof m.manifestSha256 !== 'string' ||
    !/^[0-9a-f]{64}$/.test(m.manifestSha256) ||
    typeof m.componentCount !== 'number' ||
    !Number.isInteger(m.componentCount) ||
    m.componentCount < 1 ||
    m.operatorSignOff !== false ||
    m.operatorSignOffBlockedBy !== 'human-attestation-implementation-unavailable' ||
    m.requiredDistinctOperatorCount !== 2 ||
    m.confirmedOperatorCount !== 0 ||
    typeof m.matchingAcceptedUserCount !== 'number' ||
    !Number.isInteger(m.matchingAcceptedUserCount) ||
    m.matchingAcceptedUserCount < 0 ||
    typeof m.acceptanceCount !== 'number' ||
    !Number.isInteger(m.acceptanceCount) ||
    m.acceptanceCount < 0 ||
    !isValidIsoDateTime(m.createdAt)
  ) {
    return false;
  }

  if (!Array.isArray(m.components) || m.components.length > 512 || !m.components.every(isValidReleaseComponent)) {
    return false;
  }

  return true;
}

/**
 * Validates a single ReleaseAcceptanceResponse against the canonical contract.
 * JSON schema: additionalProperties: false, outcome enum, manifestMatches boolean, etc.
 */
export function isValidReleaseAcceptance(val: unknown): val is ReleaseAcceptanceResponse {
  if (!val || typeof val !== 'object' || Array.isArray(val)) return false;
  const a = val as Record<string, unknown>;
  if (!hasOnlyAllowedKeys(a, ALLOWED_ACCEPTANCE_KEYS)) return false;

  if (
    typeof a.acceptanceId !== 'string' ||
    a.acceptanceId.length < 1 ||
    a.acceptanceId.length > 64 ||
    typeof a.acceptanceIdRef !== 'string' ||
    a.acceptanceIdRef.length < 1 ||
    a.acceptanceIdRef.length > 16 ||
    typeof a.outcome !== 'string' ||
    !VALID_OUTCOMES.has(a.outcome) ||
    typeof a.acceptedManifestSha256 !== 'string' ||
    !/^[0-9a-f]{64}$/.test(a.acceptedManifestSha256) ||
    typeof a.manifestMatches !== 'boolean' ||
    !isValidIsoDateTime(a.decidedAt)
  ) {
    return false;
  }

  if (!Array.isArray(a.knownLimitations) || a.knownLimitations.length > 64 || !a.knownLimitations.every((item) => typeof item === 'string')) {
    return false;
  }

  return true;
}

/**
 * Validates a ReleaseManifestPageResponse against the canonical contract.
 * JSON schema: additionalProperties: false, items array (max 200), required nullable nextCursor.
 */
export function isValidReleaseManifestPage(val: unknown): val is ReleaseManifestPageResponse {
  if (!val || typeof val !== 'object' || Array.isArray(val)) return false;
  const p = val as Record<string, unknown>;
  if (!hasOnlyAllowedKeys(p, ALLOWED_PAGE_KEYS)) return false;

  if (!Array.isArray(p.items) || p.items.length > 200) return false;
  if (!p.items.every(isValidReleaseManifest)) return false;

  if (p.nextCursor !== null && typeof p.nextCursor !== 'string') {
    return false;
  }

  return true;
}

/**
 * Validates a ReleaseManifestDetailResponse against the canonical contract.
 * JSON schema: additionalProperties: false, release required, acceptances array required.
 */
export function isValidReleaseManifestDetail(val: unknown): val is ReleaseManifestDetailResponse {
  if (!val || typeof val !== 'object' || Array.isArray(val)) return false;
  const d = val as Record<string, unknown>;
  if (!hasOnlyAllowedKeys(d, ALLOWED_DETAIL_KEYS)) return false;

  if (!isValidReleaseManifest(d.release)) return false;

  if (!Array.isArray(d.acceptances) || d.acceptances.length > 256 || !d.acceptances.every(isValidReleaseAcceptance)) {
    return false;
  }

  return true;
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

  const res = await apiClient<unknown>(endpoint, {
    method: 'GET',
    signal: options.signal,
  });

  if (!isValidReleaseManifestPage(res)) {
    throw new ContractViolationError('ReleaseManifestPageResponse contract violation: invalid page shape or items');
  }

  return res;
}

/**
 * Fetch a specific release manifest detail with recorded acceptances.
 * Canonical route: GET /v1/release-manifests/{release_id}
 * Non-existent or other-tenant release returns RFC 9457 ProblemDetails 404 (RES-0004).
 */
export async function fetchReleaseManifestDetail(
  releaseId: string,
  signal?: AbortSignal
): Promise<ReleaseManifestDetailResponse> {
  if (!releaseId || typeof releaseId !== 'string' || !releaseId.trim()) {
    throw new Error('releaseId must be a non-empty string');
  }

  const endpoint = `/v1/release-manifests/${encodeURIComponent(releaseId.trim())}`;
  const res = await apiClient<unknown>(endpoint, {
    method: 'GET',
    signal,
  });

  if (!isValidReleaseManifestDetail(res)) {
    throw new ContractViolationError('ReleaseManifestDetailResponse contract violation: invalid detail shape or acceptances');
  }

  return res;
}
