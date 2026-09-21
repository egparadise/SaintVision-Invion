/* Generated from contracts/data-location-page-response.schema.json. Do not edit by hand. */

export type Bytesize = number;
export type Checksumsha256 = string | null;
export type Contributionid = string;
export type Kind = string;
export type Locationid = string;
export type Ready = boolean;
export type Relativepath = string;
export type Retentionpinneduntil = string | null;
export type Uri = string;
export type Verifiedat = string | null;
export type Items = DataLocationResponse[];
export type Nextcursor = string | null;

/**
 * Paginated catalog locations returned to the Resource Explorer.
 */
export interface DataLocationPageResponse {
  items: Items;
  nextCursor: Nextcursor;
}
export interface DataLocationResponse {
  byteSize: Bytesize;
  checksumSha256?: Checksumsha256;
  contributionId: Contributionid;
  kind: Kind;
  locationId: Locationid;
  ready: Ready;
  relativePath: Relativepath;
  retentionPinnedUntil?: Retentionpinneduntil;
  uri: Uri;
  verifiedAt?: Verifiedat;
}
