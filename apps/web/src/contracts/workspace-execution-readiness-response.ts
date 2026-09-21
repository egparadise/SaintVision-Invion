/* Generated from contracts/workspace-execution-readiness-response.schema.json. Do not edit by hand. */

export type Admissionrequired = true;
export type Blockedby = string[];
export type Check = string;
export type Detail = string;
export type Maxcontentbytes = number | null;
export type Maxsnapshotbytes = number | null;
export type Remedy = string | null;
export type Resolvedby = string | null;
export type Runid = string | null;
export type Satisfied = boolean;
export type Snapshotbytes = number | null;
export type Checks = ExecutionReadinessCheckResponse[];
export type Executable = false;
export type Nodereadiness = 'unknown';
export type Projectid = string;
export type Scope = 'workspace-preconditions-not-execution-admission';
export type Summary = string;
export type Workspaceid = string;

export interface WorkspaceExecutionReadinessResponse {
  admissionRequired: Admissionrequired;
  blockedBy: Blockedby;
  checks: Checks;
  executable: Executable;
  nodeReadiness: Nodereadiness;
  projectId: Projectid;
  scope: Scope;
  summary: Summary;
  workspaceId: Workspaceid;
}
export interface ExecutionReadinessCheckResponse {
  check: Check;
  detail: Detail;
  maxContentBytes?: Maxcontentbytes;
  maxSnapshotBytes?: Maxsnapshotbytes;
  remedy?: Remedy;
  resolvedBy?: Resolvedby;
  runId?: Runid;
  satisfied: Satisfied;
  snapshotBytes?: Snapshotbytes;
}
