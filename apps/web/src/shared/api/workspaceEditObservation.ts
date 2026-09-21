import { apiClient } from './client';
import type { WorkspaceEditView, WorkspaceSnapshotFile } from '@/contracts/types';
import type { InvFileItem } from '@/contracts/virtualFabric';

const HEX_64_REGEX = /^[0-9a-f]{64}$/i;

export async function fetchWorkspaceEditView(
  projectId: string,
  runId: string,
  checkoutId: string,
  signal?: AbortSignal
): Promise<WorkspaceEditView> {
  if (!projectId || !runId || !checkoutId) {
    throw new Error('프로젝트 ID, Run ID, Checkout ID를 확인하세요.');
  }

  const path = [projectId, runId, checkoutId].map(encodeURIComponent);
  const result = await apiClient<WorkspaceEditView>(
    `/v1/projects/${path[0]}/runs/${path[1]}/checkouts/${path[2]}/files`,
    { method: 'GET', signal }
  );

  if (
    !result ||
    result.checkoutId !== checkoutId ||
    typeof result.revision !== 'number' ||
    !HEX_64_REGEX.test(result.sha256) ||
    !result.snapshot ||
    result.snapshot.format !== 'workspace-snapshot:1' ||
    !Array.isArray(result.snapshot.files)
  ) {
    throw new Error('WorkspaceEditView 응답 계약 불일치');
  }

  for (const f of result.snapshot.files) {
    if (
      !f.path ||
      typeof f.executable !== 'boolean' ||
      !HEX_64_REGEX.test(f.sha256) ||
      typeof f.sizeBytes !== 'number' ||
      typeof f.dataBase64 !== 'string'
    ) {
      throw new Error('WorkspaceSnapshotFile 응답 계약 불일치');
    }
  }

  return result;
}

export function mapWorkspaceFilesToInvItems(
  editView: WorkspaceEditView
): InvFileItem[] {
  const wsId = editView.snapshot.workspaceId || 'default-workspace';
  return editView.snapshot.files.map((f: WorkspaceSnapshotFile) => {
    let decodedContent: string | undefined;
    try {
      if (typeof globalThis.atob === 'function') {
        decodedContent = globalThis.atob(f.dataBase64);
      } else {
        decodedContent = Buffer.from(f.dataBase64, 'base64').toString('utf8');
      }
    } catch {
      decodedContent = f.dataBase64;
    }

    return {
      uri: `inv://workspaces/${wsId}/${f.path}`,
      namespace: 'workspaces',
      relativePath: f.path,
      name: f.path.split('/').pop() || f.path,
      type: 'file',
      sizeBytes: f.sizeBytes,
      version: String(editView.revision),
      contentHash: f.sha256,
      contentType: f.path.endsWith('.py') ? 'text/x-python' : 'text/plain',
      replicas: [],
      requiredReplicas: 1,
      isPinned: false,
      classification: 'internal',
      updatedAt: new Date().toISOString(),
      content: decodedContent,
      source: 'kernel-checkout',
    };
  });
}
