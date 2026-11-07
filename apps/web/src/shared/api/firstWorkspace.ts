import type {
  ApprovalView, ControlRunView, ControlRunDetail, WorkloadSpec,
  WorkspaceStartPrepareInput, WorkspaceStartPrepareResult, WorkspaceStartView,
  WorkspaceStartEnqueueInput, WorkspaceStartEnqueueResult,
  WorkspaceFirstIntent, WorkspaceFirstRunCreateResult,
} from '../../../../../packages/contracts-ts/src';
import { apiClient, generateTraceId, getAuthToken, onAuthTeardown } from './client';

export type { WorkloadSpec, WorkspaceStartView, WorkspaceStartPrepareResult };
export interface WorkspaceScope { projectId: string; tenantId: string; subjectId: string }
export interface InputFile { path: string; content: string }
const encoder = new TextEncoder();
const hex = /^[a-f0-9]{64}$/;
const id = (prefix: string, value: unknown) => typeof value === 'string' && new RegExp(`^${prefix}_[0-9A-HJKMNP-TV-Z]{26}$`).test(value);
const uuid = (value: unknown) => typeof value === 'string' && /^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$/.test(value);
const integer = (value: unknown, min = 0) => Number.isSafeInteger(value) && Number(value) >= min;
const states = ['draft', 'validated', 'planned', 'awaiting_approval', 'scheduled', 'running', 'verifying', 'recovering', 'succeeded', 'failed', 'cancelled'];

// Python workspace_files.canonical / policy.action_digest use sorted keys and ensure_ascii.
// Inputs here contain only bounded integers; JSON float formatting is deliberately excluded.
export function canonicalWorkspaceJSON(value: unknown): string {
  if (Array.isArray(value)) return `[${value.map(canonicalWorkspaceJSON).join(',')}]`;
  if (value !== null && typeof value === 'object') {
    const object = value as Record<string, unknown>;
    return `{${Object.keys(object).sort().map(key => `${canonicalWorkspaceJSON(key)}:${canonicalWorkspaceJSON(object[key])}`).join(',')}}`;
  }
  const json = JSON.stringify(value);
  if (json === undefined || (typeof value === 'number' && !Number.isSafeInteger(value))) throw new Error('Canonical integer JSON required');
  return json.replace(/[\u007f-\uffff]/g, char => `\\u${char.charCodeAt(0).toString(16).padStart(4, '0')}`);
}
export async function workspaceSHA256(bytes: Uint8Array): Promise<string> {
  const digest = await crypto.subtle.digest('SHA-256', new Uint8Array(bytes).buffer);
  return Array.from(new Uint8Array(digest), byte => byte.toString(16).padStart(2, '0')).join('');
}
function base64(bytes: Uint8Array): string {
  return btoa(Array.from(bytes, byte => String.fromCharCode(byte)).join(''));
}

export async function canonicalCPUInput(workspaceId: string, files: InputFile[]) {
  if (!id('wsp', workspaceId) || files.length === 0 || files.length > 64) throw new Error('Workspace와 1–64개 입력 파일이 필요합니다.');
  const directories = new Set<string>(); const names = new Set<string>(); let contentBytes = 0;
  const rows = [];
  for (const file of [...files].sort((a, b) => a.path < b.path ? -1 : a.path > b.path ? 1 : 0)) {
    // A bounded subset of portable_path: ASCII names avoid locale/casefold ambiguity.
    const parts = file.path.split('/');
    if (file.path.length > 1024 || parts.length > 16 || parts.some(part =>
      !/^[a-zA-Z0-9_. -]+$/.test(part) || part.length > 255 || ['.', '..'].includes(part) ||
      /[. ]$/.test(part) || /^(CON|PRN|AUX|NUL|COM[1-9]|LPT[1-9])(?:\..*)?$/i.test(part)))
      throw new Error('상대 경로와 이식 가능한 ASCII 파일 이름을 사용하세요.');
    const lower = file.path.toLowerCase();
    if (names.has(lower)) throw new Error('중복 입력 경로입니다.');
    names.add(lower);
    for (let n = 1; n < parts.length; n++) directories.add(parts.slice(0, n).join('/'));
    const raw = encoder.encode(file.content); contentBytes += raw.length;
    if (contentBytes > 32768) throw new Error('입력 내용의 UTF-8 합계는 32768 bytes 이하여야 합니다.');
    rows.push({ path: file.path, executable: false, sha256: await workspaceSHA256(raw), sizeBytes: raw.length, dataBase64: base64(raw) });
  }
  const allDirectories = [...directories].sort();
  const directoryNames = new Set<string>();
  for (const path of allDirectories) {
    if (names.has(path.toLowerCase()) || directoryNames.has(path.toLowerCase())) throw new Error('파일·디렉터리 경로가 충돌합니다.');
    directoryNames.add(path.toLowerCase());
  }
  const manifest = { format: 'workspace-snapshot:1', workspaceId, directories: allDirectories, files: rows };
  const bytes = encoder.encode(canonicalWorkspaceJSON(manifest));
  if (bytes.length > 65536) throw new Error('Canonical archive는 65536 bytes 이하여야 합니다.');
  return { manifest, snapshotBase64: base64(bytes), sha256: await workspaceSHA256(bytes), sizeBytes: bytes.length, contentBytes };
}

export function assertFirstWorkload(workload: WorkloadSpec, scope: WorkspaceScope, workspaceId: string, nodeId?: string): void {
  const resources = workload?.resources;
  if (workload?.apiVersion !== 'inv.saintvision.ai/v1alpha1' || workload.kind !== 'Workload' ||
      workload.projectId !== scope.projectId || workload.tenantId !== scope.tenantId || workload.workspaceId !== workspaceId ||
      !id('wld', workload.workloadId) || !id('wsp', workspaceId) || !id('nod', workload.targetNodeId ?? nodeId) ||
      (nodeId !== undefined && workload.targetNodeId !== undefined && nodeId !== workload.targetNodeId) ||
      !/^sha256:[a-f0-9]{64}$/.test(workload.imageDigest) ||
      !Array.isArray(workload.command) || workload.command.length === 0 || workload.command.length > 64 ||
      workload.command.some(arg => typeof arg !== 'string' || arg.length > 4096) ||
      !integer(workload.timeoutSeconds, 1) || workload.timeoutSeconds > 30 ||
      !resources || !integer(resources.cpuMillis, 1) || resources.cpuMillis > 500 ||
      !integer(resources.memoryBytes, 8388608) || resources.memoryBytes > 67108864 ||
      resources.gpuCount !== 0 || resources.minVramBytes !== 0 || workload.terminal ||
      workload.modelInput || workload.workspaceStart || workload.workspaceResume ||
      JSON.stringify(workload).includes('ROOT_ONLY_UNBOUND'))
    throw new Error('현재 프로젝트의 실제 CPU intent(500m/64MiB/30s 이하, 명시된 대상 Node, terminal 없음)가 필요합니다.');
}

export function assertFirstRun(run: ControlRunView, scope: WorkspaceScope, runId?: string): void {
  if (!run || !id('run', run.runId) || (runId && run.runId !== runId) ||
      run.projectId !== scope.projectId || run.tenantId !== scope.tenantId ||
      !states.includes(run.state) || !integer(run.version, 1) || !integer(run.attempt))
    throw new Error('서버 Run 식별자·scope·state·version 계약이 일치하지 않습니다. 결과는 미확정입니다.');
}

function assertApproval(a: ApprovalView, scope: WorkspaceScope, runId: string) {
  if (!a || !id('apr', a.approvalId) || a.projectId !== scope.projectId || a.runId !== runId ||
      typeof a.requesterId !== 'string' || !a.requesterId || !hex.test(a.actionDigest) ||
      a.requiredApprovals !== 2 || !integer(a.runVersion, 1) || !a.policyVersion ||
      !Number.isFinite(Date.parse(a.expiresAt)) || !['pending', 'approved', 'rejected', 'expired', 'dispatched'].includes(a.status))
    throw new Error('서버의 두 사람 승인 결속을 확인하지 못했습니다.');
}

let authGeneration = 0;
const requests = new Map<string, FirstWorkspaceRequest>();
onAuthTeardown(() => { authGeneration++; requests.forEach(request => request.dispose()); requests.clear(); });
export function firstScopeKey(scope: WorkspaceScope) { return JSON.stringify([scope.tenantId, scope.subjectId, scope.projectId]); }
export function currentFirstWorkspaceRequest(scope: WorkspaceScope, selected?: { intent: WorkspaceFirstIntent; nodeId: string }) {
  const key = firstScopeKey(scope) + (selected ? JSON.stringify([selected.intent.workload.workspaceId, selected.intent.workload.workloadId, selected.intent.intentEtag]) : '');
  let request = requests.get(key);
  if (request && !request.belongsToCurrentAuthentication()) { request.dispose(); request = undefined; }
  if (!request) { request = new FirstWorkspaceRequest(scope, selected); requests.set(key, request); }
  return request;
}

/** One explicit logical request. An uncertain mutation retains the exact key AND bytes.
 * A generation/token change invalidates all later requests and responses from this object.
 * This class never retries automatically, selects an alternate endpoint or creates replacement Runs.
 */
export class FirstWorkspaceRequest {
  readonly createKey: string;
  readonly startId: string;
  private readonly prepareKey: string;
  private readonly enqueueKey: string;
  private readonly token = getAuthToken();
  private readonly generation = authGeneration;
  private disposed = false;
  private busy = false;
  private run: ControlRunView | null = null;
  private prepareBody: string | null = null;
  private prepared: WorkspaceStartPrepareResult | null = null;
  private enqueueBody: string | null = null;
  get inputLocked() { return this.prepareBody !== null; }
  constructor(readonly scope: WorkspaceScope, private readonly selected?: { intent: WorkspaceFirstIntent; nodeId: string }) {
    this.scope = { ...scope };
    // Only opaque request IDs are persisted, never tokens, votes, code or workload bytes.
    // Reopening this browser tab replays creation with the same logical key.
    if (selected) this.selected = structuredClone(selected);
    const storageKey = `saintvision.first-workspace.request:${firstScopeKey(scope)}${selected ? JSON.stringify([selected.intent.workload.workspaceId, selected.intent.workload.workloadId, selected.intent.intentEtag]) : ''}`;
    const saved = sessionStorage.getItem(storageKey);
    const ids = saved ? JSON.parse(saved) as Record<string, string> : {
      createKey: generateTraceId(), startId: crypto.randomUUID(), prepareKey: generateTraceId(), enqueueKey: generateTraceId(),
    };
    if (!uuid(ids.startId) || !['createKey', 'prepareKey', 'enqueueKey'].every(k => /^[a-f0-9]{32}$/.test(ids[k])))
      throw new Error('기존 논리 요청 식별자가 손상되었습니다. 새 요청 대신 운영자에게 확인하세요.');
    sessionStorage.setItem(storageKey, JSON.stringify(ids));
    this.createKey = ids.createKey; this.startId = ids.startId;
    this.prepareKey = ids.prepareKey; this.enqueueKey = ids.enqueueKey;
  }
  dispose() { this.disposed = true; }
  belongsToCurrentAuthentication() { return !this.disposed && this.generation === authGeneration && this.token === getAuthToken(); }
  assertCurrent() {
    if (this.disposed || this.generation !== authGeneration || !this.token || getAuthToken() !== this.token ||
        !this.scope.subjectId || !this.scope.tenantId || !id('prj', this.scope.projectId))
      throw new Error('인증 또는 프로젝트가 변경되었습니다. 현재 세션에서 다시 조회하세요.');
  }
  private get base() { return `/v1/projects/${encodeURIComponent(this.scope.projectId)}/runs`; }
  private async exclusive<T>(operation: () => Promise<T>): Promise<T> {
    this.assertCurrent();
    if (this.busy) throw new Error('같은 요청의 응답을 기다리고 있습니다.');
    this.busy = true;
    try { return await operation(); } finally { this.busy = false; }
  }
  async create(): Promise<ControlRunView> {
    return this.exclusive(async () => {
      if (this.run) return this.run;
      const selected = this.selected;
      const endpoint = selected ? `/v1/projects/${encodeURIComponent(this.scope.projectId)}/workspaces/${selected.intent.workspaceId}/first-intents/${selected.intent.workload.workloadId}/runs` : this.base;
      const raw = await apiClient<ControlRunView | WorkspaceFirstRunCreateResult>(endpoint, {
        method: 'POST', body: '{}', idempotencyKey: this.createKey, expectedStatus: 201,
        ...(selected ? { headers: { 'If-Match': selected.intent.intentEtag } } : {}),
      });
      let result: ControlRunView;
      if (selected) {
        const created = raw as WorkspaceFirstRunCreateResult;
        if (created?.requesterId !== this.scope.subjectId || !/^oidc:[a-f0-9]{64}$/.test(created.requesterId) ||
            !Number.isFinite(Date.parse(created.observedAt)) || created.intent?.intentEtag !== selected.intent.intentEtag ||
            canonicalWorkspaceJSON(created.intent.workload) !== canonicalWorkspaceJSON(selected.intent.workload))
          throw new Error('선택한 업무 intent·실제 요청자와 생성 응답이 다릅니다.');
        result = created.run;
      } else result = raw as ControlRunView;
      this.assertCurrent(); assertFirstRun(result, this.scope);
      this.run = result; return result;
    });
  }
  async prepare(workload: WorkloadSpec, files: InputFile[], stepId: string): Promise<WorkspaceStartPrepareResult> {
    return this.exclusive(async () => {
      if (!this.run) throw new Error('먼저 실제 draft Run을 생성하세요.');
      if (this.prepared) return this.prepared;
      if (!this.prepareBody) {
        assertFirstWorkload(workload, this.scope, workload.workspaceId, this.selected?.nodeId);
        if (this.selected && canonicalWorkspaceJSON(workload) !== canonicalWorkspaceJSON(this.selected.intent.workload))
          throw new Error('선택한 실제 intent를 바꿀 수 없습니다.');
        if (!stepId.trim() || stepId.length > 200) throw new Error('Step ID는 1–200자여야 합니다.');
        const input = await canonicalCPUInput(workload.workspaceId, files);
        this.assertCurrent();
        const current = await apiClient<ControlRunDetail>(`${this.base}/${this.run.runId}`);
        this.assertCurrent(); assertFirstRun(current, this.scope, this.run.runId);
        if (current.state !== 'draft' || current.attempt !== 0) throw new Error('첫 준비에는 현재 draft / attempt 0 Run이 필요합니다.');
        const payload: WorkspaceStartPrepareInput = {
          startId: this.startId, stepId, workload: structuredClone(workload), expectedVersion: current.version,
          snapshotBase64: input.snapshotBase64, targetNodeId: workload.targetNodeId ?? this.selected!.nodeId,
        };
        const body = JSON.stringify(payload);
        if (encoder.encode(body).length > 65536) throw new Error('Base64와 메타데이터를 포함한 전체 요청은 65536 UTF-8 bytes 이하여야 합니다. 입력을 줄이세요.');
        this.prepareBody = body;
      }
      this.assertCurrent();
      const result = await apiClient<WorkspaceStartPrepareResult>(`${this.base}/${this.run.runId}/start/prepare`, {
        method: 'POST', body: this.prepareBody, idempotencyKey: this.prepareKey, expectedStatus: 201,
      });
      this.assertCurrent();
      await this.validateFrozen(result);
      if (result.run.state !== 'awaiting_approval' || result.run.attempt !== 0 ||
          result.approval.runVersion !== result.run.version || result.approval.requesterId !== this.scope.subjectId)
        throw new Error('첫 준비 응답의 요청자·Run version·승인 대기 상태가 다릅니다.');
      this.assertCurrent(); this.prepared = result; this.run = result.run; return result;
    });
  }
  private async validateFrozen(result: WorkspaceStartPrepareResult | WorkspaceStartView) {
    if (!this.run || result?.startId !== this.startId || !result.workload?.workspaceStart) throw new Error('동결된 첫 입력 식별자가 다릅니다.');
    assertFirstRun(result.run, this.scope, this.run.runId);
    if (result.run.version < this.run.version) throw new Error('이전 Run version 응답입니다.');
    const ref = result.workload.workspaceStart;
    if (ref.startId !== this.startId || !hex.test(ref.inputSha256) || !integer(ref.inputSizeBytes, 1) ||
        ref.inputSizeBytes > 65536 || !id('nod', ref.nodeId) || !id('res', ref.cpuResourceId) ||
        !id('res', ref.memoryResourceId) || ref.cpuResourceId === ref.memoryResourceId || !ref.policyVersion || !ref.profileVersion)
      throw new Error('동결 입력과 실제 runtime 결속을 확인하지 못했습니다.');
    if (this.prepareBody) {
      const input = JSON.parse(this.prepareBody) as WorkspaceStartPrepareInput;
      const raw = Uint8Array.from(atob(input.snapshotBase64), char => char.charCodeAt(0));
      const original = { ...result.workload }; delete original.workspaceStart;
      if (canonicalWorkspaceJSON(original) !== canonicalWorkspaceJSON(input.workload) || ref.nodeId !== input.targetNodeId ||
          ref.stepId !== input.stepId || ref.inputSizeBytes !== raw.length || ref.inputSha256 !== await workspaceSHA256(raw))
        throw new Error('서버 동결 입력이 요청한 바이트·작업·대상과 다릅니다.');
    }
    if (!result.approval) throw new Error('서버 승인 안건이 없습니다.');
    assertApproval(result.approval, this.scope, this.run.runId);
    if (result.approval.actionDigest !== await workspaceSHA256(encoder.encode(canonicalWorkspaceJSON(result.workload))))
      throw new Error('서버 actionDigest와 동결 작업이 다릅니다.');
    if (this.prepared && (result.approval.approvalId !== this.prepared.approval.approvalId ||
        result.approval.actionDigest !== this.prepared.approval.actionDigest ||
        canonicalWorkspaceJSON(result.workload) !== canonicalWorkspaceJSON(this.prepared.workload)))
      throw new Error('현재 승인 안건이 바뀌었습니다.');
    if (this.prepared && result.approval.requesterId !== this.prepared.approval.requesterId)
      throw new Error('원래 요청자 결속이 다릅니다.');
    if ('frozenFiles' in result) {
      if (!Array.isArray(result.frozenFiles) || result.frozenFiles.some(file => !file.path || !hex.test(file.sha256) || !integer(file.sizeBytes)))
        throw new Error('동결 파일 관측 계약이 다릅니다.');
      if (this.prepareBody) {
        const input = JSON.parse(this.prepareBody) as WorkspaceStartPrepareInput;
        const archive = JSON.parse(atob(input.snapshotBase64)) as { files: { path: string; sha256: string; sizeBytes: number }[] };
        if (canonicalWorkspaceJSON(result.frozenFiles) !== canonicalWorkspaceJSON(archive.files.map(({ path, sha256, sizeBytes }) => ({ path, sha256, sizeBytes }))))
          throw new Error('동결 파일 목록과 업로드한 실제 입력이 다릅니다.');
      }
    }
  }
  async observe(): Promise<WorkspaceStartView> {
    this.assertCurrent();
    if (!this.run || !this.prepared) throw new Error('현재 동결 입력이 없습니다.');
    const result = await apiClient<WorkspaceStartView>(`${this.base}/${this.run.runId}/starts/${this.startId}`);
    this.assertCurrent(); await this.validateFrozen(result); this.assertCurrent();
    this.run = result.run; return result;
  }
  async recoverFrozen(): Promise<WorkspaceStartView> {
    this.assertCurrent();
    if (!this.run) throw new Error('같은 논리 요청의 Run을 먼저 재확인하세요.');
    const result = await apiClient<WorkspaceStartView>(`${this.base}/${this.run.runId}/starts/${this.startId}`);
    this.assertCurrent(); await this.validateFrozen(result); this.assertCurrent();
    if (!result.approval) throw new Error('승인 안건이 없습니다.');
    this.prepared = { startId: result.startId, workload: result.workload, run: result.run, approval: result.approval };
    this.run = result.run; return result;
  }
  async enqueue(): Promise<WorkspaceStartEnqueueResult> {
    return this.exclusive(async () => {
      if (!this.run || !this.prepared) throw new Error('먼저 입력과 승인 안건을 준비하세요.');
      if (!this.enqueueBody) {
        const current = await this.observe(); const a = current.approval!;
        if (a.requesterId !== this.scope.subjectId) throw new Error('원래 요청자만 enqueue할 수 있습니다.');
        if (a.status !== 'approved' || a.requiredApprovals !== 2 || Date.parse(a.expiresAt) <= Date.now() ||
            a.runVersion !== current.run.version || current.run.state !== 'awaiting_approval')
          throw new Error('현재 안건에 대한 실제 비요청자 두 사람 승인과 Run version이 필요합니다.');
        const input: WorkspaceStartEnqueueInput = { startId: this.startId, approvalId: a.approvalId, expectedVersion: current.run.version };
        this.enqueueBody = JSON.stringify(input);
      }
      this.assertCurrent();
      const result = await apiClient<WorkspaceStartEnqueueResult>(`${this.base}/${this.run.runId}/start/enqueue`, {
        method: 'POST', body: this.enqueueBody, idempotencyKey: this.enqueueKey, expectedStatus: 202,
      });
      this.assertCurrent();
      if (result?.accepted !== true || result.runId !== this.run.runId || result.startId !== this.startId || !uuid(result.commandId))
        throw new Error('Enqueue 응답 결속이 다릅니다. 전달 결과는 미확정입니다.');
      return result;
    });
  }
}
