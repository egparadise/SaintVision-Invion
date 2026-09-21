/* Generated from contracts/node-page-response.schema.json. Do not edit by hand. */

export type Agentversion = string;
export type Enrolledat = string;
export type Heartbeatsequence = number;
export type Hostname = string;
export type Lastheartbeatat = string | null;
export type Nodeid = string;
export type Ostype = string;
export type Osversion = string;
export type Status = string;
export type Items = NodeResponse[];
export type Nextcursor = string | null;

/**
 * Tenant-scoped node inventory page; telemetry is intentionally absent.
 */
export interface NodePageResponse {
  items: Items;
  nextCursor: Nextcursor;
}
export interface NodeResponse {
  agentVersion: Agentversion;
  enrolledAt: Enrolledat;
  heartbeatSequence: Heartbeatsequence;
  hostname: Hostname;
  labels?: Labels;
  lastHeartbeatAt?: Lastheartbeatat;
  nodeId: Nodeid;
  osType: Ostype;
  osVersion: Osversion;
  status: Status;
}
export interface Labels {
  [k: string]: string;
}
