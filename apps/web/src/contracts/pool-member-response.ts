/* Generated from contracts/pool-member-response.schema.json. Do not edit by hand. */

export type Member = true;
export type Nodeid = string;
export type Poolid = string;

export interface PoolMemberResponse {
  member: Member;
  nodeId: Nodeid;
  poolId: Poolid;
}
