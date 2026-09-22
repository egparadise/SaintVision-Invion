/* Generated from contracts/pool-list-response.schema.json. Do not edit by hand. */

export type PoolStatus = 'active' | 'archived';

export interface PoolListItemResponse {
  poolId: string;
  projectId: string;
  name: string;
  status: PoolStatus;
  memberCount: number;
}

export interface PoolListResponse {
  items: PoolListItemResponse[];
  count: number;
}
