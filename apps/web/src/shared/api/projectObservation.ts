import type { ProjectItem } from '@/contracts/types';
import type { ProjectListResponse } from '@/contracts/project-list-response';
import type { ProjectWorkspacesResponse, WorkspaceSummaryResponse } from '@/contracts/project-workspaces-response';
import { apiClient } from './client';

export type ProjectWorkspace = WorkspaceSummaryResponse;
export async function fetchProjects(): Promise<ProjectItem[]> {
  const page = await apiClient<ProjectListResponse>('/v1/projects');
  if (!Array.isArray(page.projects) || page.count !== page.projects.length) {
    throw new Error('프로젝트 응답 형식 불일치');
  }
  return page.projects.map(p => {
    if (!p.projectId || !p.displayName || !p.createdAt ||
        typeof p.kernelLinked !== 'boolean' || typeof p.kernelEnabled !== 'boolean') {
      throw new Error('프로젝트 응답 필드 누락');
    }
    return { id: p.projectId, name: p.displayName, createdAt: p.createdAt,
      kernelLinked: p.kernelLinked, kernelEnabled: p.kernelEnabled };
  });
}
export async function fetchProjectWorkspaces(projectId: string): Promise<ProjectWorkspace[]> {
  const page = await apiClient<ProjectWorkspacesResponse>(
    `/v1/projects/${encodeURIComponent(projectId)}/workspaces`);
  if (page.projectId !== projectId || !Array.isArray(page.workspaces) ||
      page.workspaces.some(w => w.projectId !== projectId || !w.workspaceId)) {
    throw new Error('Workspace 프로젝트 응답 불일치');
  }
  return page.workspaces;
}
