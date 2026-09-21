/* Generated from contracts/contribution-page-response.schema.json. Do not edit by hand. */

export type Availablebytes = number | null;
export type Capacitybytes = number | null;
export type Contributionid = string;
export type Declaredpath = string;
export type Mode = 'read_only' | 'read_write';
export type Nodeid = string;
export type Normalizedpath = string;
export type Registeredat = string;
export type Status = 'pending' | 'active' | 'revoked';
export type Items = ContributionResponse[];
export type Nextcursor = string | null;

/**
 * Paginated storage contributions returned to the Resource Explorer.
 */
export interface ContributionPageResponse {
  items: Items;
  nextCursor: Nextcursor;
}
export interface ContributionResponse {
  availableBytes?: Availablebytes;
  capacityBytes?: Capacitybytes;
  contributionId: Contributionid;
  declaredPath: Declaredpath;
  mode: Mode;
  nodeId: Nodeid;
  normalizedPath: Normalizedpath;
  registeredAt: Registeredat;
  status: Status;
}
