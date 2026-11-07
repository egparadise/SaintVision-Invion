// @vitest-environment happy-dom
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest';
import { webcrypto } from 'node:crypto';
import Ajv2020 from 'ajv/dist/2020';
import addFormats from 'ajv-formats';
import schema from '../../../contracts/v1alpha1/core.schema.json';
import golden from './fixtures/first-workspace-golden.json';
import {
  FirstWorkspaceRequest, assertFirstWorkload, canonicalCPUInput, canonicalWorkspaceJSON,
  type WorkloadSpec,
} from '../src/shared/api/firstWorkspace';
import { clearAuthToken, setAuthToken } from '../src/shared/api/client';
import { approveReviewed } from '../src/shared/api/approvalReview';
import { _resetKernelMutationCache, decideApproval } from '../src/shared/api/kernelMutations';
import { fetchReadyIntents, FirstIntentCreation } from '../src/shared/api/workspaceFirstIntent';
const copy = <T,>(value: T): T => structuredClone(value);
const workload = golden.workload as WorkloadSpec;
const response = (body: unknown, status = 200) => new Response(JSON.stringify(body), { status, headers: { 'content-type': 'application/json' } });
const problem = (status: number, code: string, detail: string) => response({
  type: 'about:blank', title: 'Denied', status, code, category: code.split('-')[0], detail,
  retryable: false, traceId: 'a'.repeat(32), causeRef: null, evidenceId: null,
}, status);
let view: typeof golden.view;
let fetchMock: ReturnType<typeof vi.fn>;
function calls(ending: string) { return fetchMock.mock.calls.filter(([url]) => String(url).endsWith(ending)); }
const item = () => {
  const a = golden.prepared.approval;
  return { id: a.approvalId, runId: a.runId, projectId: a.projectId, requestedBy: a.requesterId,
    actionDigest: a.actionDigest, status: 'pending' as const, boundRunVersion: a.runVersion,
    policyReason: a.policyVersion, requiredApprovals: 2 as const, expiresAt: a.expiresAt };
};
beforeEach(() => {
  clearAuthToken(); sessionStorage.clear(); _resetKernelMutationCache(); setAuthToken('isolated-requester-token');
  vi.stubGlobal('crypto', { getRandomValues: webcrypto.getRandomValues.bind(webcrypto), subtle: webcrypto.subtle,
    randomUUID: () => golden.prepared.startId });
  view = copy(golden.view);
  fetchMock = vi.fn(async (url: string, init: RequestInit = {}) => {
    if (url.endsWith('/runs') && init.method === 'POST') return response(golden.run, 201);
    if (url.endsWith(`/runs/${golden.run.runId}`)) return response({ ...golden.run, resourceReleasePending: false });
    if (url.endsWith('/start/prepare')) return response(golden.prepared, 201);
    if (url.includes('/starts/')) return response(view);
    if (url.endsWith('/start/enqueue')) return response({ startId: golden.prepared.startId, runId: golden.run.runId, accepted: true, commandId: '00000000-0000-4000-8000-000000000043' }, 202);
    throw new Error(`Unexpected isolated test route: ${url}`);
  });
  vi.stubGlobal('fetch', fetchMock);
});
afterEach(() => { clearAuthToken(); vi.unstubAllGlobals(); vi.restoreAllMocks(); });
async function prepared() {
  const request = new FirstWorkspaceRequest(golden.scope);
  await request.create(); await request.prepare(workload, golden.files, 'cpu-step'); return request;
}

describe('first Workspace canonical source contract', () => {
  it('matches independent Python ensure_ascii/sorted golden bytes, hashes, content and base64', async () => {
    const actual = await canonicalCPUInput(workload.workspaceId, golden.files);
    expect(actual).toEqual({ manifest: golden.snapshot.manifest, snapshotBase64: golden.snapshot.snapshotBase64,
      sha256: golden.snapshot.sha256, sizeBytes: golden.snapshot.sizeBytes, contentBytes: golden.snapshot.contentBytes });
    expect(canonicalWorkspaceJSON(actual.manifest)).toBe(golden.snapshot.rawUTF8);
  });
  it('validates real golden wire examples with the unchanged backend schema', () => {
    const ajv = new Ajv2020({ strict: false }); addFormats(ajv); ajv.addSchema(schema, 'core');
    for (const [name, data] of [['ControlRunView', golden.run], ['WorkspaceStartPrepareResult', golden.prepared], ['WorkspaceStartView', golden.view]]) {
      const validate = ajv.compile({ $ref: `core#/$defs/${name}` });
      expect(validate(data), JSON.stringify(validate.errors)).toBe(true);
    }
  });
  it.each(['../x', '/x', 'src/../x', 'src/CON.txt', 'src/a.', 'src/a\\b', 'src/x:y', 'src/é.py'])('rejects nonportable or out-of-scope path %s', async path => {
    await expect(canonicalCPUInput(workload.workspaceId, [{ path, content: 'x' }])).rejects.toThrow();
  });
  it('rejects duplicate and file/directory case collisions', async () => {
    for (const paths of [['src/a', 'src/A'], ['src', 'src/a'], ['Src/a', 'src/b']])
      await expect(canonicalCPUInput(workload.workspaceId, paths.map(path => ({ path, content: 'x' })))).rejects.toThrow();
  });
  it('counts UTF-8 bytes rather than JS code units at the 32768 content bound', async () => {
    await expect(canonicalCPUInput(workload.workspaceId, [{ path: 'a', content: 'é'.repeat(16385) }])).rejects.toThrow('32768');
    expect((await canonicalCPUInput(workload.workspaceId, [{ path: 'a', content: 'é'.repeat(16384) }])).contentBytes).toBe(32768);
  });
  it('enforces the archive bound independently of content', async () => {
    const files = Array.from({ length: 64 }, (_, n) => ({ path: `${'a'.repeat(240)}/${'b'.repeat(240)}/${'c'.repeat(240)}/${'d'.repeat(240)}${n}`, content: '' }));
    await expect(canonicalCPUInput(workload.workspaceId, files)).rejects.toThrow('archive');
  });
  it('enforces HTTP UTF-8 body after the second base64 expansion and metadata', async () => {
    const request = new FirstWorkspaceRequest(golden.scope); await request.create();
    const files = [{ path: 'a', content: 'a'.repeat(32768) }];
    expect((await canonicalCPUInput(workload.workspaceId, files)).sizeBytes).toBeLessThan(65536);
    // Increase real metadata without increasing input archive/content.
    const metadataHeavy = { ...workload, command: Array.from({ length: 8 }, () => 'a'.repeat(4000)) };
    await expect(request.prepare(metadataHeavy, files, 'cpu-step')).rejects.toThrow('전체 요청');
    expect(calls('/start/prepare')).toHaveLength(0);
  });
  it.each([
    { terminal: { enabled: true } }, { targetNodeId: undefined }, { tenantId: 'another-tenant' },
    { resources: { ...workload.resources, gpuCount: 1 } }, { resources: { ...workload.resources, cpuMillis: 501 } },
    { imageDigest: 'ROOT_ONLY_UNBOUND' }, { workspaceResume: {} }, { workspaceStart: {} },
  ])('rejects unsupported or mismatched CPU intent %j', change => {
    expect(() => assertFirstWorkload({ ...workload, ...change } as WorkloadSpec, golden.scope, workload.workspaceId)).toThrow();
  });
});

describe('first Workspace closed mutations and observed state', () => {
  it('uses exact selected Workspace/workload EmptyRequest create and If-Match without caller authority', async () => {
    fetchMock.mockResolvedValueOnce(response(golden.businessCreated, 201));
    const request = new FirstWorkspaceRequest(golden.scope, { intent: golden.intent, nodeId: workload.targetNodeId! });
    expect(await request.create()).toEqual(golden.run);
    const [url, init] = fetchMock.mock.calls[0];
    expect(url).toBe(`/v1/projects/${golden.scope.projectId}/workspaces/${workload.workspaceId}/first-intents/${workload.workloadId}/runs`);
    expect(init.body).toBe('{}'); expect(new Headers(init.headers).get('If-Match')).toBe(golden.intent.intentEtag);
    expect(new Headers(init.headers).get('Idempotency-Key')).toBe(request.createKey);
  });
  it('creates exact EmptyRequest with bearer and stable logical key and binds returned ID/version', async () => {
    const request = new FirstWorkspaceRequest(golden.scope);
    expect(await request.create()).toEqual(golden.run); expect(await request.create()).toEqual(golden.run);
    const [, init] = calls('/runs')[0]; const headers = new Headers(init.headers);
    expect(init.body).toBe('{}'); expect(headers.get('Idempotency-Key')).toBe(request.createKey);
    expect(headers.get('Authorization')).toBe('Bearer isolated-requester-token');
    expect(calls('/runs')).toHaveLength(1);
  });
  it('keeps creation key across network uncertainty, component replacement and tab reload recovery', async () => {
    const first = new FirstWorkspaceRequest(golden.scope);
    fetchMock.mockRejectedValueOnce(new TypeError('Unknown delivery'));
    await expect(first.create()).rejects.toThrow('Unknown delivery');
    const reopened = new FirstWorkspaceRequest(golden.scope); await reopened.create();
    expect(calls('/runs').map(([, init]) => new Headers(init.headers).get('Idempotency-Key'))).toEqual([first.createKey, first.createKey]);
    expect(sessionStorage.getItem(`saintvision.first-workspace.request:${JSON.stringify([golden.scope.tenantId, golden.scope.subjectId, golden.scope.projectId])}`)).not.toContain('token');
  });
  it('reads current state after creation replay instead of treating the original draft snapshot as current', async () => {
    fetchMock.mockResolvedValueOnce(response(golden.run, 201)).mockResolvedValueOnce(response({ ...golden.run, state: 'running', version: 6, attempt: 1, resourceReleasePending: true }));
    const request = new FirstWorkspaceRequest(golden.scope);
    expect(await request.create()).toMatchObject({ runId: golden.run.runId, state: 'running', version: 6, attempt: 1 });
    expect(calls('/runs')).toHaveLength(1);
  });
  it('does not treat malformed 201 as success or create a different logical Run', async () => {
    const request = new FirstWorkspaceRequest(golden.scope);
    fetchMock.mockResolvedValueOnce(response({ accepted: true }, 201));
    await expect(request.create()).rejects.toThrow('미확정');
    await request.create();
    expect(calls('/runs').map(([, init]) => init.body)).toEqual(['{}', '{}']);
    expect(new Headers(calls('/runs')[0][1].headers).get('Idempotency-Key')).toBe(new Headers(calls('/runs')[1][1].headers).get('Idempotency-Key'));
  });
  it.each([{ projectId: 'prj_01ARZ3NDEKTSV4RRFFQ69G5FAW' }, { tenantId: '00000000-0000-4000-8000-000000000099' }, { version: 0 }, { state: 'executed' }])('rejects returned identity/state/version mismatch %j', async change => {
    fetchMock.mockResolvedValueOnce(response({ ...golden.run, ...change }, 201));
    await expect(new FirstWorkspaceRequest(golden.scope).create()).rejects.toThrow('계약');
  });
  it('does not post without authentication', async () => {
    clearAuthToken(); await expect(new FirstWorkspaceRequest(golden.scope).create()).rejects.toThrow('인증'); expect(fetchMock).not.toHaveBeenCalled();
  });
  it('ignores an old create response after logout/relogin, even to the same token', async () => {
    let resolve!: (r: Response) => void;
    fetchMock.mockImplementationOnce(() => new Promise(r => { resolve = r; }));
    const request = new FirstWorkspaceRequest(golden.scope); const pending = request.create();
    clearAuthToken(); setAuthToken('isolated-requester-token'); resolve(response(golden.run, 201));
    await expect(pending).rejects.toThrow('인증');
    await expect(request.prepare(workload, golden.files, 'cpu-step')).rejects.toThrow('인증');
    expect(calls('/start/prepare')).toHaveLength(0);
  });
  it('does not continue preparation when credentials change during current Run read', async () => {
    const request = new FirstWorkspaceRequest(golden.scope); await request.create();
    fetchMock.mockImplementationOnce(async () => { setAuthToken('new-session-token'); return response({ ...golden.run, resourceReleasePending: false }); });
    await expect(request.prepare(workload, golden.files, 'cpu-step')).rejects.toThrow('인증'); expect(calls('/start/prepare')).toHaveLength(0);
  });
  it('posts exact prepare keys/bytes/current version and binds frozen action digest', async () => {
    const request = await prepared(); const [, init] = calls('/start/prepare')[0]; const body = JSON.parse(init.body);
    expect(body).toEqual({ startId: golden.prepared.startId, stepId: 'cpu-step', workload, expectedVersion: 1,
      snapshotBase64: golden.snapshot.snapshotBase64, targetNodeId: workload.targetNodeId });
    expect(new Headers(init.headers).get('Idempotency-Key')).toMatch(/^[a-f0-9]{32}$/);
    expect(await request.observe()).toEqual(golden.view);
  });
  it('retains exact prepare request and key across unknown delivery even if caller edits parameters', async () => {
    const request = new FirstWorkspaceRequest(golden.scope); await request.create();
    const server = fetchMock.getMockImplementation()!; let failed = false;
    fetchMock.mockImplementation(async (url: string, init: RequestInit) => {
      if (url.endsWith('/start/prepare') && !failed) { failed = true; throw new TypeError('Unknown delivery'); }
      return server(url, init);
    });
    await expect(request.prepare(workload, golden.files, 'cpu-step')).rejects.toThrow();
    await request.prepare(workload, [{ path: 'changed', content: 'changed' }], 'changed');
    const sent = calls('/start/prepare'); expect(sent).toHaveLength(2);
    expect(sent[0][1].body).toBe(sent[1][1].body);
    expect(new Headers(sent[0][1].headers).get('Idempotency-Key')).toBe(new Headers(sent[1][1].headers).get('Idempotency-Key'));
  });
  it.each(['AUTH-0045', 'GRAPH-0003', 'IDEM-0001'])('preserves actual prepare refusal %s without synthesizing frozen state', async code => {
    const request = new FirstWorkspaceRequest(golden.scope); await request.create();
    const server = fetchMock.getMockImplementation()!;
    fetchMock.mockImplementation(async (url: string, init: RequestInit) => url.endsWith('/start/prepare') ? problem(409, code, 'Actual prepare gate') : server(url, init));
    await expect(request.prepare(workload, golden.files, 'cpu-step')).rejects.toMatchObject({ problem: { code } });
    await expect(request.enqueue()).rejects.toThrow('먼저'); expect(calls('/start/enqueue')).toHaveLength(0);
  });
  it('rejects changed frozen bytes and action digest', async () => {
    const request = new FirstWorkspaceRequest(golden.scope); await request.create();
    const changed = copy(golden.prepared); changed.workload.workspaceStart.inputSha256 = 'f'.repeat(64);
    const server = fetchMock.getMockImplementation()!;
    fetchMock.mockImplementation(async (url: string, init: RequestInit) => url.endsWith('/start/prepare') ? response(changed, 201) : server(url, init));
    await expect(request.prepare(workload, golden.files, 'cpu-step')).rejects.toThrow('바이트');
    expect(calls('/start/enqueue')).toHaveLength(0);
  });
  it.each(['pending', 'rejected', 'expired'])('cannot enqueue with server approval status %s', async status => {
    const request = await prepared(); view.approval.status = status;
    await expect(request.enqueue()).rejects.toThrow('실제 비요청자'); expect(calls('/start/enqueue')).toHaveLength(0);
  });
  it('cannot enqueue as a different requester', async () => {
    const request = await prepared(); view.approval.status = 'approved'; view.approval.requesterId = 'isolated-other-person';
    await expect(request.enqueue()).rejects.toThrow('요청자'); expect(calls('/start/enqueue')).toHaveLength(0);
  });
  it.each(['version', 'expiry', 'action'])('rejects stale %s before enqueue', async kind => {
    const request = await prepared(); view.approval.status = 'approved';
    if (kind === 'version') view.run.version = 5;
    if (kind === 'expiry') view.approval.expiresAt = '2000-01-01T00:00:00Z';
    if (kind === 'action') view.approval.actionDigest = 'f'.repeat(64);
    await expect(request.enqueue()).rejects.toThrow(); expect(calls('/start/enqueue')).toHaveLength(0);
  });
  it('sends closed enqueue body with server version and keeps exact key on uncertain replay', async () => {
    const request = await prepared(); view.approval.status = 'approved';
    const server = fetchMock.getMockImplementation()!; let failed = false;
    fetchMock.mockImplementation(async (url: string, init: RequestInit) => {
      if (url.endsWith('/start/enqueue') && !failed) { failed = true; throw new TypeError('Unknown enqueue'); }
      return server(url, init);
    });
    await expect(request.enqueue()).rejects.toThrow('Unknown enqueue');
    // The server may have dispatched already. Replay the original input, not a new nonce/version/key.
    view.run.state = 'running'; view.run.version = 6; view.approval.status = 'dispatched';
    expect((await request.enqueue()).accepted).toBe(true);
    const sent = calls('/start/enqueue'); expect(sent).toHaveLength(2);
    expect(JSON.parse(sent[0][1].body)).toEqual({ startId: golden.prepared.startId, approvalId: golden.prepared.approval.approvalId, expectedVersion: 4 });
    expect(sent[0][1].body).toBe(sent[1][1].body);
    expect(new Headers(sent[0][1].headers).get('Idempotency-Key')).toBe(new Headers(sent[1][1].headers).get('Idempotency-Key'));
  });
  it('does not promote server enqueue denial to accepted', async () => {
    const request = await prepared(); view.approval.status = 'approved'; const server = fetchMock.getMockImplementation()!;
    fetchMock.mockImplementation(async (url: string, init: RequestInit) => url.endsWith('/start/enqueue') ? problem(403, 'AUTH-0045', 'Requester revoked') : server(url, init));
    await expect(request.enqueue()).rejects.toMatchObject({ problem: { code: 'AUTH-0045' } });
    expect((await request.observe()).run.state).toBe('awaiting_approval');
  });
  it('creation, preparation and enqueue do not synthesize running/completion; reads carry actual lifecycle', async () => {
    const request = new FirstWorkspaceRequest(golden.scope);
    expect((await request.create()).state).toBe('draft');
    expect((await request.prepare(workload, golden.files, 'cpu-step')).run.state).toBe('awaiting_approval');
    view.approval.status = 'approved'; expect(await request.enqueue()).not.toHaveProperty('state');
    for (const [state, version] of [['scheduled', 5], ['running', 6], ['verifying', 7], ['succeeded', 8]] as const) {
      view.run.state = state; view.run.version = version; view.approval.status = 'dispatched';
      expect((await request.observe()).run).toMatchObject({ state, version });
    }
  });
  it('restores the server frozen input after reopening with the persisted logical Start ID', async () => {
    const first = await prepared(); const reopened = new FirstWorkspaceRequest(golden.scope); await reopened.create();
    expect(reopened.startId).toBe(first.startId); expect(await reopened.recoverFrozen()).toEqual(golden.view);
    expect(calls('/start/prepare')).toHaveLength(1);
  });
});

describe('Root R1 real intent serving adapter', () => {
  it('binds exact current workload hash/version/profile snapshot without inventing ready state', async () => {
    fetchMock.mockResolvedValueOnce(response(golden.intentPage));
    expect(await fetchReadyIntents(golden.scope, workload.workspaceId)).toEqual(golden.intentPage);
  });
  it.each(['sha', 'workloadId', 'memory', 'workspace', 'cursor'])('refuses changed %s server contract', async kind => {
    const page = copy(golden.intentPage);
    if (kind === 'sha') page.items[0].workloadSha256 = 'f'.repeat(64);
    if (kind === 'workloadId') page.items[0].workload.workloadId = 'invalid';
    if (kind === 'memory') page.profile.minMemoryBytes = 1;
    if (kind === 'workspace') page.workspaceId = 'another-workspace';
    if (kind === 'cursor') page.nextCursor = 'wld_01ARZ3NDEKTSV4RRFFQ69G5FAW';
    fetchMock.mockResolvedValueOnce(response(page));
    await expect(fetchReadyIntents(golden.scope, workload.workspaceId)).rejects.toThrow();
  });
  it('metadata registration sends closed selected-context data and stable headers on unknown outcome', async () => {
    const input = { objective: 'Isolated CPU task', imageDigest: workload.imageDigest, command: workload.command,
      resources: { cpuMillis: 500, memoryBytes: 67108864, gpuCount: 0 as const, minVramBytes: 0 as const }, timeoutSeconds: 30 };
    const request = new FirstIntentCreation(golden.scope, workload.workspaceId, golden.intentPage, input);
    fetchMock.mockRejectedValueOnce(new TypeError('unknown intent delivery')).mockResolvedValueOnce(response(golden.intent, 201));
    await expect(request.submit()).rejects.toThrow('unknown'); expect(await request.submit()).toEqual(golden.intent);
    const [first, second] = fetchMock.mock.calls;
    expect(JSON.parse(first[1].body)).toEqual(input); expect(first[1].body).toBe(second[1].body);
    expect(new Headers(first[1].headers).get('If-Match')).toBe('"workspace-v1"');
    expect(new Headers(first[1].headers).get('Idempotency-Key')).toBe(new Headers(second[1].headers).get('Idempotency-Key'));
  });
});

describe('actual challenge/decision helper, isolated server denials', () => {
  it.each(['self', 'notlinked', 'denied', 'nonce', 'action'])('keeps %s refusal visible without counting a vote', async kind => {
    const a = item(); const code = kind === 'nonce' ? 'AUTH-0034' : kind === 'notlinked' ? 'AUTH-0030' : 'AUTH-0033';
    const shown = { approvalId: a.id, projectId: a.projectId, actionDigest: a.actionDigest, runVersion: a.boundRunVersion };
    fetchMock.mockImplementation(async (url: string) => {
      if (url.endsWith('/challenge')) return kind === 'self' || kind === 'notlinked' ? problem(403, code, 'Actual server gate') : response({ approvalId: a.id, nonce: 'isolated-server-issued-nonce', expiresAt: '2099-01-01T00:00:00Z' });
      return problem(403, code, 'Actual server gate');
    });
    await expect(approveReviewed(a, shown)).rejects.toMatchObject({ problem: { code } });
    expect(calls('/decision')).toHaveLength(kind === 'self' || kind === 'notlinked' ? 0 : 1);
    if (calls('/decision').length) expect(JSON.parse(calls('/decision')[0][1].body)).toEqual({ decision: 'approve', nonce: 'isolated-server-issued-nonce', actionDigest: a.actionDigest });
  });
  it('does not send a decision if auth changes while awaiting a challenge', async () => {
    fetchMock.mockImplementationOnce(async () => { clearAuthToken(); setAuthToken('isolated-new-person'); return response({ nonce: 'old-person-nonce' }); });
    await expect(decideApproval({ id: item().id, projectId: item().projectId, actionDigest: item().actionDigest }, 'approve')).rejects.toThrow('인증');
    expect(calls('/decision')).toHaveLength(0);
  });
});
