import { readFileSync } from 'node:fs';
import type { ProjectWorkspacesResponse } from '@/contracts/project-workspaces-response';
import type { WorkspaceExecutionReadinessResponse } from '@/contracts/workspace-execution-readiness-response';
import type { ProjectListResponse } from '@/contracts/project-list-response';

function readFixture<T>(name: string): T {
  return JSON.parse(readFileSync(
    new URL(`../../../../contracts/fixtures/${name}.json`, import.meta.url),
    'utf8',
  )) as T;
}

export const projectWorkspacesFixture = readFixture<ProjectWorkspacesResponse>('project-workspaces-response');
export const projectListFixture = readFixture<ProjectListResponse>('project-list-response');
export const workspaceExecutionReadinessFixture = readFixture<WorkspaceExecutionReadinessResponse>(
  'workspace-execution-readiness-response',
);
