/* Generated from contracts/release-manifest-detail-response.schema.json. Do not edit by hand. */

export type Acceptanceid = string;
export type Acceptanceidref = string;
export type Acceptedmanifestsha256 = string;
export type Decidedat = string;
/**
 * @maxItems 64
 */
export type Knownlimitations = string[];
export type Manifestmatches = boolean;
export type Outcome = 'accepted' | 'conditional' | 'rejected';
/**
 * @maxItems 256
 */
export type Acceptances = ReleaseAcceptanceResponse[];
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
 * One release with every acceptance decision recorded against it.
 */
export interface ReleaseManifestDetailResponse {
  acceptances?: Acceptances;
  release: ReleaseManifestResponse;
}
/**
 * One recorded acceptance decision, without the person who made it.
 *
 * The accepting user is deliberately absent. ``accepted_by_user_id`` is a real
 * foreign key precisely so the system cannot sign its own acceptance, but a
 * read surface that names people turns an audit column into a directory;
 * ``RunRecordResponse`` set that rule first and this follows it. ``notes`` is
 * free text and is absent for the same reason.
 *
 * ``manifestMatches`` is computed, not stored: an acceptance pins the manifest
 * hash as it stood when it was granted, and accepting one composition while
 * shipping another is the failure that pinning exists to catch. A reader that
 * only saw ``outcome`` could not tell the two apart.
 */
export interface ReleaseAcceptanceResponse {
  acceptanceId: Acceptanceid;
  acceptanceIdRef: Acceptanceidref;
  acceptedManifestSha256: Acceptedmanifestsha256;
  decidedAt: Decidedat;
  knownLimitations?: Knownlimitations;
  manifestMatches: Manifestmatches;
  outcome: Outcome;
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
