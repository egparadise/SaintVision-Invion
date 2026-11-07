import type { WorkspaceFirstIntent, WorkspaceFirstIntentPage, WorkspaceFirstIntentCreateInput } from '../../../../../packages/contracts-ts/src';
import { apiClient, generateTraceId, getAuthToken } from './client';
import { assertFirstWorkload, canonicalWorkspaceJSON, workspaceSHA256, type WorkspaceScope } from './firstWorkspace';
export type { WorkspaceFirstIntent, WorkspaceFirstIntentPage, WorkspaceFirstIntentCreateInput };
export function intentBase(scope: WorkspaceScope, workspaceId: string) {
  return `/v1/projects/${encodeURIComponent(scope.projectId)}/workspaces/${encodeURIComponent(workspaceId)}/first-intents`;
}
export async function assertReadyIntent(item: WorkspaceFirstIntent, scope: WorkspaceScope, workspaceId: string, nodeId: string) {
  assertFirstWorkload(item?.workload, scope, workspaceId, nodeId);
  if (item.workspaceId !== workspaceId || !Number.isSafeInteger(item.workspaceVersion) || item.workspaceVersion < 1 ||
      !Number.isSafeInteger(item.workloadVersion) || item.workloadVersion < 1 ||
      !Number.isFinite(Date.parse(item.observedAt)) ||
      item.intentEtag !== `"workspace-v${item.workspaceVersion}-workload-v${item.workloadVersion}-sha256-${item.workloadSha256}"` ||
      item.workloadSha256 !== await workspaceSHA256(new TextEncoder().encode(canonicalWorkspaceJSON(item.workload))))
    throw new Error('서버 intent의 실제 scope·version·canonical SHA·ETag가 일치하지 않습니다.');
}
export async function fetchReadyIntents(scope: WorkspaceScope, workspaceId: string, after?: string): Promise<WorkspaceFirstIntentPage> {
  const credential = getAuthToken(); if (!credential) throw new Error('현재 인증이 필요합니다.');
  const page = await apiClient<WorkspaceFirstIntentPage>(`${intentBase(scope, workspaceId)}?limit=20${after ? `&after=${encodeURIComponent(after)}` : ''}`);
  if (getAuthToken() !== credential) throw new Error('Intent 조회 중 인증이 변경되었습니다.');
  const p = page?.profile;
  if (page.projectId !== scope.projectId || page.workspaceId !== workspaceId || !Number.isSafeInteger(page.workspaceVersion) || page.workspaceVersion < 1 ||
      !Number.isFinite(Date.parse(page.observedAt)) || !Array.isArray(page.items) || page.items.length > 20 ||
      !(page.nextCursor === null || /^wld_[0-9A-HJKMNP-TV-Z]{26}$/.test(page.nextCursor)) ||
      !p || !/^nod_[0-9A-HJKMNP-TV-Z]{26}$/.test(p.nodeId) || !p.profileVersion || p.minMemoryBytes !== 8388608 || p.terminalAllowed !== false ||
      !Number.isSafeInteger(p.maxMemoryBytes) || p.maxMemoryBytes < p.minMemoryBytes || p.maxMemoryBytes > 67108864 ||
      !Number.isSafeInteger(p.maxCpuMillis) || p.maxCpuMillis < 1 || p.maxCpuMillis > 500 ||
      !Number.isSafeInteger(p.maxTimeoutSeconds) || p.maxTimeoutSeconds < 1 || p.maxTimeoutSeconds > 30 ||
      !Array.isArray(p.images) || p.images.length === 0 || p.images.some(image => !/^sha256:[a-f0-9]{64}$/.test(image)) ||
      !Array.isArray(p.executables) || p.executables.length === 0 || p.executables.some(exe => typeof exe !== 'string' || !exe.startsWith('/')))
    throw new Error('Ready intent 또는 CPU profile 관측 계약이 다릅니다.');
  let previous = after ?? '';
  for (const item of page.items) {
    await assertReadyIntent(item, scope, workspaceId, p.nodeId);
    if (item.workspaceVersion !== page.workspaceVersion || item.workload.workloadId <= previous) throw new Error('Intent 선택 순서·Workspace version이 다릅니다.');
    previous = item.workload.workloadId;
  }
  if (page.nextCursor !== null && page.nextCursor !== previous) throw new Error('Intent 페이지 cursor가 다릅니다.');
  return page;
}
export class FirstIntentCreation {
  private readonly key = generateTraceId();
  private readonly credential = getAuthToken();
  private readonly body: string;
  constructor(private readonly scope: WorkspaceScope, private readonly workspaceId: string,
    private readonly page: WorkspaceFirstIntentPage, input: WorkspaceFirstIntentCreateInput) {
    this.body = JSON.stringify(input);
    if (new TextEncoder().encode(this.body).length > 65536) throw new Error('전체 intent 요청은 65536 UTF-8 bytes 이하여야 합니다.');
  }
  async submit(): Promise<WorkspaceFirstIntent> {
    if (!this.credential || getAuthToken() !== this.credential) throw new Error('현재 인증이 필요합니다.');
    const item = await apiClient<WorkspaceFirstIntent>(intentBase(this.scope, this.workspaceId), { method: 'POST', body: this.body,
      idempotencyKey: this.key, headers: { 'If-Match': `"workspace-v${this.page.workspaceVersion}"` }, expectedStatus: 201 });
    if (getAuthToken() !== this.credential) throw new Error('Intent 등록 중 인증이 변경되었습니다.');
    await assertReadyIntent(item, this.scope, this.workspaceId, this.page.profile.nodeId);
    return item;
  }
}
