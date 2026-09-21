/* Generated from contracts/pool-member-removal-response.schema.json. Do not edit by hand. */

export type Nodeid = string;
export type Poolid = string;
export type Removed = boolean;

export interface PoolMemberRemovalResponse {
  nodeId: Nodeid;
  poolId: Poolid;
  removed: Removed;
}
