import Ajv2020 from 'ajv/dist/2020.js';
import addFormats from 'ajv-formats';
import schema from '../../../../../contracts/v1alpha1/core.schema.json';
import type { ProjectNodeCertificateObservationResponse } from '@/contracts/node-certificate-observation';
import { apiClient } from './client';

const ajv = new Ajv2020({ strict: false });
addFormats(ajv);
ajv.addSchema(schema);
const validate = ajv.compile<ProjectNodeCertificateObservationResponse>({
  $ref: `${schema.$id}#/$defs/ProjectNodeCertificateObservationResponse`,
});
const renewalWindowMillis = 2 * 86400 * 1000;

function timestampMicros(value: string): bigint {
  const millis = Date.parse(value);
  const fraction = value.match(/\.(\d+)(?:z|[+-]\d{2}:\d{2})$/i)?.[1] ?? '';
  if (!Number.isFinite(millis) || fraction.length > 6) throw new Error('Node certificate timestamp mismatch');
  return BigInt(millis) * 1000n + BigInt(fraction.padEnd(6, '0').slice(3));
}

/** Validate both the wire and its claimed summary before a UI can show healthy trust. */
export function checkedNodeCertificateObservation(
  value: unknown,
  projectId: string,
  now = Date.now(),
): ProjectNodeCertificateObservationResponse {
  const invalid = () => new Error('Node certificate observation contract mismatch');
  if (!validate(value) || value.projectId !== projectId) throw invalid();
  const observed = Date.parse(value.observedAt);
  const age = now - observed;
  if (!Number.isFinite(observed) || age < -5000 || age > 60000) throw invalid();
  if (new Set(value.items.map(item => item.nodeId)).size !== value.items.length) throw invalid();
  const expiries = value.items.flatMap(item => item.certificateNotAfter === null ? [] : [timestampMicros(item.certificateNotAfter)]);
  const known = value.complete && value.items.length > 0 && value.items.every(
    item => item.channelEnabled === true,
  ) && expiries.length === value.items.length;
  const trust = value.trust;
  if (!known) {
    if (trust.state !== 'unknown' || trust.earliestCertificateNotAfter !== null ||
        trust.renewalWindowStartsAt !== null || trust.secondsUntilEarliestExpiry !== null) throw invalid();
  } else {
    const observedMicros = timestampMicros(value.observedAt);
    const earliest = expiries.reduce((left, right) => left < right ? left : right);
    const starts = earliest - BigInt(renewalWindowMillis) * 1000n;
    const state = earliest <= observedMicros ? 'expired' : starts <= observedMicros ? 'renewal-window' : 'ok';
    const remaining = earliest - observedMicros;
    const seconds = Number(remaining >= 0n ? remaining / 1000000n : -((-remaining + 999999n) / 1000000n));
    if (trust.state !== state || timestampMicros(trust.earliestCertificateNotAfter ?? '') !== earliest ||
        timestampMicros(trust.renewalWindowStartsAt ?? '') !== starts ||
        trust.secondsUntilEarliestExpiry !== seconds) throw invalid();
  }
  return value;
}

export async function fetchProjectNodeCertificates(
  projectId: string,
  signal?: AbortSignal,
): Promise<ProjectNodeCertificateObservationResponse> {
  if (!projectId || !projectId.trim()) throw new Error('Project is required');
  const value = await apiClient<unknown>(`/v1/projects/${encodeURIComponent(projectId)}/node-certificates`, {
    method: 'GET', signal,
  });
  return checkedNodeCertificateObservation(value, projectId);
}
