import { apiClient } from './client';
import type { ConformanceStatusResponse, ConformanceCheckDescriptor } from '@/contracts/conformance-status-response';
import type {
  ConformanceStatusRecordedResponse,
  ConformanceRecordItem,
  ConformanceCheckOutcome,
} from '@/contracts/conformance-status-recorded-response';

/**
 * The list route's response is a discriminated union on `status` (G-03 stage two,
 * design #218 v1.2 §4-1): the stage-one seven-key NOT_OBSERVED shape when nothing is
 * recorded, or the RECORDED branch with `records[]` and `latestRecordedAt`.
 */
export type ConformanceStatusUnion = ConformanceStatusResponse | ConformanceStatusRecordedResponse;

const CONFORMANCE_STATUS_KEYS = new Set([
  'status',
  'reason',
  'scope',
  'contractVersion',
  'adapters',
  'checks',
  'recordedAt',
]);

const CONFORMANCE_RECORDED_KEYS = new Set([
  'status',
  'scope',
  'contractVersion',
  'adapters',
  'checks',
  'records',
  'latestRecordedAt',
]);

const RECORD_ITEM_KEYS = new Set([
  'adapter',
  'subject',
  'provenance',
  'contractVersion',
  'suiteContractVersion',
  'total',
  'passed',
  'failed',
  'skipped',
  'outcomes',
  'recordedAt',
]);

const CHECK_DESCRIPTOR_KEYS = new Set(['name', 'capabilityGated']);
const CHECK_OUTCOME_KEYS = new Set(['name', 'passed', 'skipped']);

const ISO_DATE_TIME_REGEX =
  /^\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}(?:\.\d+)?(?:Z|[+-]\d{2}:\d{2})$/;

function hasExactKeys(o: Record<string, unknown>, expected: Set<string>): boolean {
  const keys = Object.keys(o);
  return keys.length === expected.size && keys.every((key) => expected.has(key));
}

function isVersionString(value: unknown): value is string {
  return typeof value === 'string' && value.length >= 1 && value.length <= 32;
}

function isAwareDateTime(value: unknown): value is string {
  return typeof value === 'string' && ISO_DATE_TIME_REGEX.test(value) && !Number.isNaN(Date.parse(value));
}

function isCount(value: unknown): value is number {
  return typeof value === 'number' && Number.isInteger(value) && value >= 0;
}

/**
 * Strict runtime validator for ConformanceCheckDescriptor.
 * Enforces additionalProperties: false, name string [1, 100], and capabilityGated boolean.
 */
export function isConformanceCheckDescriptor(value: unknown): value is ConformanceCheckDescriptor {
  if (!value || typeof value !== 'object' || Array.isArray(value)) return false;
  const c = value as Record<string, unknown>;
  if (!hasExactKeys(c, CHECK_DESCRIPTOR_KEYS)) return false;
  if (typeof c.name !== 'string' || c.name.length < 1 || c.name.length > 100) return false;
  if (typeof c.capabilityGated !== 'boolean') return false;
  return true;
}

/**
 * Strict runtime validator for one stored check outcome: name, passed, skipped and
 * nothing else (no `detail`), never both passed and skipped (design §2-5, §2-8).
 */
export function isConformanceCheckOutcome(value: unknown): value is ConformanceCheckOutcome {
  if (!value || typeof value !== 'object' || Array.isArray(value)) return false;
  const o = value as Record<string, unknown>;
  if (!hasExactKeys(o, CHECK_OUTCOME_KEYS)) return false;
  if (typeof o.name !== 'string' || o.name.length < 1 || o.name.length > 100) return false;
  if (typeof o.passed !== 'boolean' || typeof o.skipped !== 'boolean') return false;
  if (o.passed && o.skipped) return false;
  return true;
}

/**
 * Strict runtime validator for one record: exact keys, the single subject/provenance
 * this stage produces, counts that add up and match the outcomes, an aware timestamp.
 */
export function isConformanceRecordItem(value: unknown): value is ConformanceRecordItem {
  if (!value || typeof value !== 'object' || Array.isArray(value)) return false;
  const r = value as Record<string, unknown>;
  if (!hasExactKeys(r, RECORD_ITEM_KEYS)) return false;
  if (typeof r.adapter !== 'string' || r.adapter.length < 1 || r.adapter.length > 64) return false;
  if (r.subject !== 'fixture-adapter') return false;
  if (r.provenance !== 'in-server') return false;
  if (!isVersionString(r.contractVersion) || !isVersionString(r.suiteContractVersion)) return false;
  const { total, passed, failed, skipped, outcomes, recordedAt } = r;
  if (!isCount(total) || !isCount(passed) || !isCount(failed) || !isCount(skipped)) return false;
  if (!Array.isArray(outcomes) || !outcomes.every(isConformanceCheckOutcome)) return false;
  if (!isAwareDateTime(recordedAt)) return false;
  const items = outcomes as ConformanceCheckOutcome[];
  if (passed + failed + skipped !== total) return false;
  if (items.length !== total) return false;
  const recount = {
    passed: items.filter((o) => o.passed && !o.skipped).length,
    failed: items.filter((o) => !o.passed && !o.skipped).length,
    skipped: items.filter((o) => o.skipped).length,
  };
  if (recount.passed !== passed || recount.failed !== failed || recount.skipped !== skipped) return false;
  return true;
}

/**
 * Strict runtime schema guard for the stage-one NOT_OBSERVED branch.
 * Enforces additionalProperties: false, status: "NOT_OBSERVED", scope: "control-plane-host",
 * recordedAt: null, and strictly typed checks descriptors against contracts/conformance-status-response.schema.json.
 */
export function isConformanceStatusResponse(value: unknown): value is ConformanceStatusResponse {
  if (!value || typeof value !== 'object' || Array.isArray(value)) return false;
  const o = value as Record<string, unknown>;
  if (!hasExactKeys(o, CONFORMANCE_STATUS_KEYS)) return false;

  if (o.status !== 'NOT_OBSERVED') return false;
  if (typeof o.reason !== 'string' || o.reason.length < 1 || o.reason.length > 300) return false;
  if (o.scope !== 'control-plane-host') return false;
  if (!isVersionString(o.contractVersion)) return false;
  if (!Array.isArray(o.adapters) || !o.adapters.every((a) => typeof a === 'string')) return false;
  if (!Array.isArray(o.checks) || !o.checks.every(isConformanceCheckDescriptor)) return false;
  if (o.recordedAt !== null) return false;

  return true;
}

/**
 * Strict runtime schema guard for the RECORDED branch
 * (contracts/conformance-status-recorded-response.schema.json): no `reason`, no aggregate
 * `recordedAt`; `records` non-empty, one entry per adapter, in the `adapters` order, naming
 * only listed adapters; `latestRecordedAt` is the maximum of the records' `recordedAt`.
 */
export function isConformanceStatusRecordedResponse(value: unknown): value is ConformanceStatusRecordedResponse {
  if (!value || typeof value !== 'object' || Array.isArray(value)) return false;
  const o = value as Record<string, unknown>;
  if (!hasExactKeys(o, CONFORMANCE_RECORDED_KEYS)) return false;

  if (o.status !== 'RECORDED') return false;
  if (o.scope !== 'control-plane-host') return false;
  if (!isVersionString(o.contractVersion)) return false;
  if (!Array.isArray(o.adapters) || !o.adapters.every((a) => typeof a === 'string')) return false;
  if (!Array.isArray(o.checks) || !o.checks.every(isConformanceCheckDescriptor)) return false;
  if (!Array.isArray(o.records) || o.records.length < 1 || !o.records.every(isConformanceRecordItem)) return false;
  const latestRecordedAt = o.latestRecordedAt;
  if (!isAwareDateTime(latestRecordedAt)) return false;

  const adapters = o.adapters as string[];
  const records = o.records as ConformanceRecordItem[];
  const names = records.map((r) => r.adapter);
  if (new Set(names).size !== names.length) return false;
  const expectedOrder = adapters.filter((a) => names.includes(a));
  if (expectedOrder.length !== names.length || expectedOrder.some((a, i) => a !== names[i])) return false;
  const latest = Math.max(...records.map((r) => Date.parse(r.recordedAt)));
  if (Date.parse(latestRecordedAt) !== latest) return false;

  return true;
}

/** Either branch of the list route, told apart by `status`. */
export function isConformanceStatusUnion(value: unknown): value is ConformanceStatusUnion {
  if (!value || typeof value !== 'object' || Array.isArray(value)) return false;
  const status = (value as Record<string, unknown>).status;
  if (status === 'RECORDED') return isConformanceStatusRecordedResponse(value);
  return isConformanceStatusResponse(value);
}

/**
 * Fetch adapter conformance status from control-plane.
 * Endpoint: GET /v1/projects/{project_id}/adapters/conformance
 * Conforms to G-03 (stage one NOT_OBSERVED shape, stage two RECORDED branch) and the
 * contracts/conformance-status-response.schema.json /
 * contracts/conformance-status-recorded-response.schema.json pair.
 */
export async function fetchConformanceStatus(
  projectId: string,
  signal?: AbortSignal
): Promise<ConformanceStatusUnion> {
  const p = projectId?.trim();
  if (!p) {
    throw new Error('프로젝트 ID를 확인하세요.');
  }

  const encoded = encodeURIComponent(p);
  const result = await apiClient<unknown>(
    `/v1/projects/${encoded}/adapters/conformance`,
    { method: 'GET', signal }
  );

  if (!isConformanceStatusUnion(result)) {
    throw new Error('ConformanceStatusResponse 응답 계약 불일치');
  }

  return result;
}
