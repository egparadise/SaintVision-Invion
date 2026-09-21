/* Generated from contracts/distributed-plan-response.schema.json. Do not edit by hand. */

export type Assignedcpumillicores = number;
export type Assignedgpudevices = number;
export type Assignedrambytes = number;
export type Nodeid = string;
export type Shardindex = number;
export type Placements = DistributedPlanPlacementResponse[];
export type Planid = string;
export type Runid = string;
export type Shardcount = number;
export type Strategy = 'single_node' | 'data_parallel' | 'sharded';

export interface DistributedPlanResponse {
  placements: Placements;
  planId: Planid;
  runId: Runid;
  shardCount: Shardcount;
  strategy: Strategy;
  units: Units;
}
export interface DistributedPlanPlacementResponse {
  assignedCpuMillicores: Assignedcpumillicores;
  assignedGpuDevices: Assignedgpudevices;
  assignedRamBytes: Assignedrambytes;
  nodeId: Nodeid;
  shardIndex: Shardindex;
}
export interface Units {
  [k: string]: string;
}
