/* Generated from contracts/release-manifest-response.schema.json. Do not edit by hand. */

export type Acceptancecount = number;
export type Componentcount = number;
export type Digest = string;
export type Kind = string;
export type Name = string;
/**
 * @maxItems 512
 */
export type Components = ReleaseComponentResponse[];
export type Confirmedoperatorcount = number;
export type Createdat = string;
export type Manifestsha256 = string;
export type Operatorsignoff = false;
export type Operatorsignoffblockedby = 'human-attestation-contract-absent';
export type Releaseid = string;
export type Requireddistinctoperatorcount = 2;
export type Version = string;

/**
 * A recorded release, and what is recorded about accepting it.
 *
 * ``operatorSignOff`` is **``Literal[False]``**: this reader cannot emit true,
 * and the contract says so rather than the docstring promising it.
 *
 * The first version of this model computed it from the acceptance rows and
 * called an ``accepted`` row with a matching hash a sign-off, on the reasoning
 * that ``acceptance_records.accepted_by_user_id`` is a foreign key to ``users``
 * so "the system cannot sign its own acceptance". **That reasoning was wrong,
 * and Codex measured it**: ``users`` draws no line between a person and a
 * service -- ``identity.py`` builds a Principal from any ``external_subject``
 * -- and the foreign key proves only that the row names a user that exists. A
 * principal whose subject was ``svc:release-bot`` wrote an ``accepted`` row and
 * the field read true. A key that proves existence was read as proof of
 * humanity.
 *
 * So the field is pinned false until there is a contract for attesting that a
 * person decided. ``requiredDistinctOperatorCount`` and
 * ``confirmedOperatorCount`` carry the recorded fact in the meantime, named as
 * the write contract (``#282``, card 184) names them: two distinct operators
 * are required, and a count below that is not sign-off however it was written.
 */
export interface ReleaseManifestResponse {
  acceptanceCount: Acceptancecount;
  componentCount: Componentcount;
  components?: Components;
  confirmedOperatorCount: Confirmedoperatorcount;
  createdAt: Createdat;
  manifestSha256: Manifestsha256;
  operatorSignOff: Operatorsignoff;
  operatorSignOffBlockedBy: Operatorsignoffblockedby;
  releaseId: Releaseid;
  requiredDistinctOperatorCount: Requireddistinctoperatorcount;
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
