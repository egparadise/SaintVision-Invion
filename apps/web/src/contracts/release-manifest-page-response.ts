/* Generated from contracts/release-manifest-page-response.schema.json. Do not edit by hand. */

export type Acceptancecount = number;
export type Componentcount = number;
export type Digest = string;
export type Kind = string;
export type Name = string;
/**
 * @maxItems 512
 */
export type Components = ReleaseComponentResponse[];
export type Createdat = string;
export type Manifestsha256 = string;
export type Operatorsignoff = boolean;
export type Releaseid = string;
export type Version = string;
/**
 * @maxItems 200
 */
export type Items = ReleaseManifestResponse[];
export type Nextcursor = string | null;

/**
 * A page of releases. An empty tenant is an empty list, not a 404.
 */
export interface ReleaseManifestPageResponse {
  items?: Items;
  nextCursor?: Nextcursor;
}
/**
 * A recorded release, and whether a person has signed it off.
 *
 * ``operatorSignOff`` is **computed from the acceptance rows**, never stored
 * and never supplied by a caller. It is true only when an ``accepted``
 * decision exists whose pinned hash equals this manifest's hash. A
 * ``conditional`` decision, a ``rejected`` one, and an acceptance of a
 * different composition all leave it false, which is the whole point: DEF-S12
 * recorded ``operatorSignOff=false`` because no server route existed to answer
 * the question, and a route that answered ``true`` from anything less than a
 * person's matching acceptance would be worse than no route at all.
 */
export interface ReleaseManifestResponse {
  acceptanceCount: Acceptancecount;
  componentCount: Componentcount;
  components?: Components;
  createdAt: Createdat;
  manifestSha256: Manifestsha256;
  operatorSignOff: Operatorsignoff;
  releaseId: Releaseid;
  version: Version;
}
/**
 * One pinned component of a release.
 *
 * Every entry carries a digest because the manifest hash covers the list: a
 * name is not an identity, so "we shipped R4" has to be checkable rather than
 * asserted (``operations_pilot.ReleaseManifest``).
 */
export interface ReleaseComponentResponse {
  digest: Digest;
  kind: Kind;
  name: Name;
}
