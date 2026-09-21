/* Generated from contracts/project-workspaces-response.schema.json. Do not edit by hand. */

export type Count = number;
export type Projectid = string;
export type Allowednext = string[];
export type Createdat = string;
export type Name = string;
export type Nodeid = string | null;
export type Projectid1 = string;
export type Status = string;
export type Toolname = string | null;
export type Workspaceid = string;
export type Workspaces = WorkspaceSummaryResponse[];

export interface ProjectWorkspacesResponse {
  count: Count;
  projectId: Projectid;
  workspaces: Workspaces;
}
export interface WorkspaceSummaryResponse {
  allowedNext: Allowednext;
  createdAt: Createdat;
  name: Name;
  nodeId: Nodeid;
  projectId: Projectid1;
  status: Status;
  toolName: Toolname;
  workspaceId: Workspaceid;
}
