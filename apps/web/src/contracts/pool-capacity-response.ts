/* Generated from contracts/pool-capacity-response.schema.json. Do not edit by hand. */

export type Activemembercount = number;
export type Cpumillicores = number;
export type Gpudevices = number;
export type Rambytes = number;
export type Membercount = number;
export type Name = string;
export type Hostname = string;
export type Measured = boolean;
export type Nodeid = string;
export type Nodes = PoolCapacityNodeResponse[];
export type Note = string;
export type Poolid = string;
export type Unmeasurednodes = string[];

export interface PoolCapacityResponse {
  activeMemberCount: Activemembercount;
  largestSingleNode: PoolResourceAmounts;
  memberCount: Membercount;
  name: Name;
  nodes: Nodes;
  note: Note;
  poolId: Poolid;
  spareNow: PoolResourceAmounts;
  totalOffered: PoolResourceAmounts;
  units: Units;
  unmeasuredNodes: Unmeasurednodes;
}
export interface PoolResourceAmounts {
  cpuMillicores: Cpumillicores;
  gpuDevices: Gpudevices;
  ramBytes: Rambytes;
}
export interface PoolCapacityNodeResponse {
  hostname: Hostname;
  measured: Measured;
  nodeId: Nodeid;
  offered: PoolResourceAmounts;
  spare: PoolResourceAmounts;
  used: PoolResourceAmounts;
}
export interface Units {
  [k: string]: string;
}
