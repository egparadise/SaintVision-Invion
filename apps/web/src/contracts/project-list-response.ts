/* Generated from contracts/project-list-response.schema.json. Do not edit by hand. */

export type Count = number;
export type Canapprove = boolean;
export type Canrequest = boolean;
export type Code = string;
export type Createdat = string;
export type Displayname = string;
export type Kernelenabled = boolean;
export type Kernellinked = boolean;
export type Kernelnote = string | null;
export type Membercount = number;
export type Projectid = string;
export type Rolecode = string;
export type Status = string;
export type Projects = ProjectListItemResponse[];

/**
 * Canonical business API envelope for GET /v1/projects.
 */
export interface ProjectListResponse {
  count: Count;
  projects: Projects;
}
/**
 * Business project row shown in the project selector.
 */
export interface ProjectListItemResponse {
  canApprove: Canapprove;
  canRequest: Canrequest;
  code: Code;
  createdAt: Createdat;
  displayName: Displayname;
  kernelEnabled: Kernelenabled;
  kernelLinked: Kernellinked;
  kernelNote?: Kernelnote;
  memberCount: Membercount;
  projectId: Projectid;
  roleCode: Rolecode;
  status: Status;
}
