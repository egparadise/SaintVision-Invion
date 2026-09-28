import { apiClient } from './client';
import type { ConformanceStatusResponse, ConformanceCheckDescriptor } from '@/contracts/types';

const CONFORMANCE_STATUS_KEYS = new Set([
  'status',
  'reason',
  'scope',
  'contractVersion',
  'adapters',
  'checks',
  'recordedAt',
]);

const CHECK_DESCRIPTOR_KEYS = new Set(['name', 'capabilityGated']);

/**
 * Strict runtime validator for ConformanceCheckDescriptor.
 * Enforces additionalProperties: false, name string [1, 100], and capabilityGated boolean.
 */
export function isConformanceCheckDescriptor(value: unknown): value is ConformanceCheckDescriptor {
  if (!value || typeof value !== 'object' || Array.isArray(value)) return false;
  const c = value as Record<string, unknown>;
  const keys = Object.keys(c);
  if (keys.length !== CHECK_DESCRIPTOR_KEYS.size) return false;
  if (!keys.every((key) => CHECK_DESCRIPTOR_KEYS.has(key))) return false;
  if (typeof c.name !== 'string' || c.name.length < 1 || c.name.length > 100) return false;
  if (typeof c.capabilityGated !== 'boolean') return false;
  return true;
}

/**
 * Strict runtime schema guard for ConformanceStatusResponse.
 * Enforces additionalProperties: false, status: "NOT_OBSERVED", scope: "control-plane-host",
 * recordedAt: null, and strictly typed checks descriptors against contracts/conformance-status-response.schema.json.
 */
export function isConformanceStatusResponse(value: unknown): value is ConformanceStatusResponse {
  if (!value || typeof value !== 'object' || Array.isArray(value)) return false;
  const o = value as Record<string, unknown>;
  const keys = Object.keys(o);
  if (keys.length !== CONFORMANCE_STATUS_KEYS.size) return false;
  if (!keys.every((key) => CONFORMANCE_STATUS_KEYS.has(key))) return false;

  if (o.status !== 'NOT_OBSERVED') return false;
  if (typeof o.reason !== 'string' || o.reason.length < 1 || o.reason.length > 300) return false;
  if (o.scope !== 'control-plane-host') return false;
  if (typeof o.contractVersion !== 'string' || o.contractVersion.length < 1 || o.contractVersion.length > 32) return false;
  if (!Array.isArray(o.adapters) || !o.adapters.every((a) => typeof a === 'string')) return false;
  if (!Array.isArray(o.checks) || !o.checks.every(isConformanceCheckDescriptor)) return false;
  if (o.recordedAt !== null) return false;

  return true;
}

/**
 * Fetch adapter conformance status from control-plane.
 * Endpoint: GET /v1/projects/{project_id}/adapters/conformance
 * Conforms to G-03 phase one specification and contracts/conformance-status-response.schema.json.
 */
export async function fetchConformanceStatus(
  projectId: string,
  signal?: AbortSignal
): Promise<ConformanceStatusResponse> {
  const p = projectId?.trim();
  if (!p) {
    throw new Error('프로젝트 ID를 확인하세요.');
  }

  const encoded = encodeURIComponent(p);
  const result = await apiClient<unknown>(
    `/v1/projects/${encoded}/adapters/conformance`,
    { method: 'GET', signal }
  );

  if (!isConformanceStatusResponse(result)) {
    throw new Error('ConformanceStatusResponse 응답 계약 불일치');
  }

  return result;
}
