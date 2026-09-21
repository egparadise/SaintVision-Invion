/* Generated from contracts/workspace-summary-response.schema.json. Do not edit by hand. */

export type Allowednext = string[];
export type Createdat = string;
export type Name = string;
export type Nodeid = string | null;
export type Projectid = string;
export type Status = string;
export type Toolname = string | null;
export type Workspaceid = string;

export interface WorkspaceSummaryResponse {
  allowedNext: Allowednext;
  createdAt: Createdat;
  name: Name;
  nodeId: Nodeid;
  projectId: Projectid;
  status: Status;
  toolName: Toolname;
  workspaceId: Workspaceid;
}
