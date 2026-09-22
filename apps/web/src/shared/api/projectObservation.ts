import type { ProjectItem } from '@/contracts/types';
import type { ProjectWorkspacesResponse, WorkspaceSummaryResponse } from '@/contracts/project-workspaces-response';
import { apiClient } from './client';

export type ProjectWorkspace = WorkspaceSummaryResponse;
export async function fetchProjects(): Promise<ProjectItem[]> {
  const page = await apiClient<any>('/v1/projects');
  if (Array.isArray(page?.projects)) {
    return page.projects.map((p: any) => ({
      id: p.projectId,
      name: p.displayName || p.projectId,
      createdAt: p.createdAt || new Date().toISOString(),
      kernelLinked: p.kernelLinked ?? true,
      kernelEnabled: p.kernelEnabled ?? true,
    }));
  }
  if (Array.isArray(page?.items)) {
    return page.items.map((p: any) => {
      const id = p.projectId || p.id;
      return {
        id,
        name: p.displayName || p.name || id,
        createdAt: p.createdAt || new Date().toISOString(),
        kernelLinked: p.kernelLinked ?? true,
        kernelEnabled: p.kernelEnabled ?? true,
      };
    });
  }
  throw new Error('프로젝트 응답 형식 불일치');
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

export async function createProjectWorkspace(projectId: string, name: string): Promise<WorkspaceSummaryResponse> {
  const body = await apiClient<WorkspaceSummaryResponse>(
    `/v1/projects/${encodeURIComponent(projectId)}/workspaces`,
    {
      method: 'POST',
      body: JSON.stringify({ name }),
    }
  );
  if (!body.workspaceId || body.projectId !== projectId || body.name !== name) {
    throw new Error('Workspace 생성 응답 불일치');
  }
  return body;
}

