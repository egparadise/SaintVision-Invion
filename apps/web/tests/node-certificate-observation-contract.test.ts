import { readFileSync } from 'node:fs';
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest';
import { checkedNodeCertificateObservation, fetchProjectNodeCertificates } from '../src/shared/api/nodeCertificateObservation';
import { apiClient } from '../src/shared/api/client';

vi.mock('../src/shared/api/client', () => ({ apiClient: vi.fn() }));
const api = vi.mocked(apiClient);
const fixture = () => JSON.parse(readFileSync(new URL('../../../contracts/fixtures/project-node-certificate-observation-response.json', import.meta.url), 'utf8'));
const now = Date.parse('2026-11-04T04:00:00+00:00');

describe('canonical project Node certificate observations', () => {
  beforeEach(() => { vi.useFakeTimers(); vi.setSystemTime(now); api.mockReset(); });
  afterEach(() => { vi.useRealTimers(); });

  it('validates the shared provider fixture and binds the request to the current project', async () => {
    const value = fixture();
    api.mockResolvedValue(value);
    expect(await fetchProjectNodeCertificates(value.projectId)).toEqual(value);
    expect(api).toHaveBeenCalledWith(`/v1/projects/${value.projectId}/node-certificates`, { method: 'GET', signal: undefined });
    expect(() => checkedNodeCertificateObservation(value, 'another-project', now)).toThrow();
  });

  it.each(['observedAt', 'scope', 'complete', 'trust', 'projectId'])('rejects a missing %s boundary field', field => {
    const value = fixture();
    delete value[field];
    expect(() => checkedNodeCertificateObservation(value, fixture().projectId, now)).toThrow();
  });

  it.each(['missing', 'disabled', 'truncated', 'empty'])('rejects a healthy summary over %s observations', kind => {
    const value = fixture();
    if (kind === 'missing') value.items[0].certificateNotAfter = null;
    if (kind === 'disabled') value.items[0].channelEnabled = false;
    if (kind === 'truncated') value.complete = false;
    if (kind === 'empty') value.items = [];
    expect(() => checkedNodeCertificateObservation(value, value.projectId, now)).toThrow();
    value.trust = { state: 'unknown', earliestCertificateNotAfter: null, renewalWindowStartsAt: null, secondsUntilEarliestExpiry: null };
    expect(checkedNodeCertificateObservation(value, value.projectId, now).trust.state).toBe('unknown');
  });

  it('refuses stale, future, duplicate, and falsely reassuring observations', () => {
    const value = fixture();
    expect(() => checkedNodeCertificateObservation(value, value.projectId, now + 60001)).toThrow();
    expect(() => checkedNodeCertificateObservation(value, value.projectId, now - 5001)).toThrow();
    value.items.push({ ...value.items[0] });
    expect(() => checkedNodeCertificateObservation(value, value.projectId, now)).toThrow();
    const expired = fixture();
    expired.items[0].certificateNotAfter = expired.observedAt;
    expect(() => checkedNodeCertificateObservation(expired, expired.projectId, now)).toThrow();
  });

  it('propagates authentication failures without returning an earlier success', async () => {
    const value = fixture();
    api.mockResolvedValueOnce(value).mockRejectedValueOnce(new Error('401'));
    await fetchProjectNodeCertificates(value.projectId);
    await expect(fetchProjectNodeCertificates(value.projectId)).rejects.toThrow('401');
  });

  it.each([
    ['2026-11-04T04:00:00.000002+00:00', '2026-11-02T04:00:00.000002+00:00', 'renewal-window', 0],
    ['2026-11-04T04:00:00+00:00', '2026-11-02T04:00:00+00:00', 'expired', -1],
  ])('preserves provider microseconds around the expiry boundary', (expiry, starts, state, seconds) => {
    const value = fixture();
    value.observedAt = '2026-11-04T04:00:00.000001+00:00';
    value.items[0].certificateNotAfter = expiry;
    value.trust = { state, earliestCertificateNotAfter: expiry, renewalWindowStartsAt: starts, secondsUntilEarliestExpiry: seconds };
    expect(checkedNodeCertificateObservation(value, value.projectId, now).trust.state).toBe(state);
  });
});
