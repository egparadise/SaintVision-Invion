/* Generated from contracts/node-detail-response.schema.json. Do not edit by hand. */

export type Capabilityid = string;
export type Deviceindex = number | null;
export type Divisible = boolean;
export type Kind = string;
export type Model = string | null;
export type Totalquantity = number;
export type Unit = string;
export type Vendor = string | null;
export type Capabilities = NodeCapability[];
export type Agentversion = string;
export type Enrolledat = string;
export type Heartbeatsequence = number;
export type Hostname = string;
export type Lastheartbeatat = string | null;
export type Nodeid = string;
export type Ostype = string;
export type Osversion = string;
export type Status = 'enrolling' | 'active' | 'draining' | 'lost' | 'retired';

export interface NodeDetailResponse {
  capabilities: Capabilities;
  node: NodeResponse;
}
export interface NodeCapability {
  capabilityId: Capabilityid;
  deviceIndex: Deviceindex;
  divisible: Divisible;
  kind: Kind;
  model: Model;
  totalQuantity: Totalquantity;
  unit: Unit;
  vendor: Vendor;
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
