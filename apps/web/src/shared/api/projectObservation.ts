import type { ProjectItem } from '@/contracts/types';
import { apiClient } from './client';

export interface ProjectWorkspace {
  workspaceId: string; projectId: string; name: string;
  status: string; nodeId: string | null; toolName: string | null; createdAt: string;
}
export async function fetchProjects(): Promise<ProjectItem[]> {
  const page = await apiClient<{ items?: Array<{ projectId: string }>; projects?: Array<{
    projectId: string; displayName: string; createdAt: string;
    kernelLinked: boolean; kernelEnabled: boolean;
  }> }>('/v1/projects');
  if (Array.isArray(page.items) && page.projects === undefined) {
    return page.items.map(p => {
      if (typeof p.projectId !== 'string' || !p.projectId) throw new Error('프로젝트 식별자 누락');
      return { id: p.projectId, name: p.projectId, createdAt: '' };
    });
  }
  if (page.items !== undefined || !Array.isArray(page.projects)) throw new Error('프로젝트 응답 형식 불일치');
  return page.projects.map(p => {
    if (!p.projectId || !p.displayName) throw new Error('프로젝트 식별자 누락');
    return { id: p.projectId, name: p.displayName, createdAt: p.createdAt,
      kernelLinked: p.kernelLinked, kernelEnabled: p.kernelEnabled };
  });
}
export async function fetchProjectWorkspaces(projectId: string): Promise<ProjectWorkspace[]> {
  const page = await apiClient<{ projectId: string; workspaces: ProjectWorkspace[] }>(
    `/v1/projects/${encodeURIComponent(projectId)}/workspaces`);
  if (page.projectId !== projectId || !Array.isArray(page.workspaces) ||
      page.workspaces.some(w => w.projectId !== projectId || !w.workspaceId)) {
    throw new Error('Workspace 프로젝트 응답 불일치');
  }
  return page.workspaces;
}
