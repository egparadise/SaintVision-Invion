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
export type Confirmedoperatorcount = 0;
export type Createdat = string;
export type Manifestsha256 = string;
export type Matchingacceptedusercount = number;
export type Operatorsignoff = false;
export type Operatorsignoffblockedby = 'release-acceptance-prerequisites-unavailable';
export type Releaseid = string;
export type Requireddistinctoperatorcount = 2;
export type Version = string;

/**
 * One release with every acceptance decision recorded against it.
 */
export interface ReleaseManifestDetailResponse {
  acceptances: Acceptances;
  release: ReleaseManifestResponse;
}
/**
 * One recorded acceptance decision, without the person who made it.
 *
 * The accepting user is deliberately absent: a read surface that names people
 * turns an audit column into a directory, and ``RunRecordResponse`` set that
 * rule first. ``notes`` is free text and is absent for the same reason.
 *
 * This docstring used to add that ``accepted_by_user_id`` is a foreign key
 * "precisely so the system cannot sign its own acceptance". **That is false**,
 * and Codex measured it: ``users`` does not distinguish a person from a service,
 * so a principal whose subject was ``svc:release-bot`` wrote an ``accepted`` row
 * through this very column. The key constrains the row to name a user that
 * exists and says nothing about who that user is -- which is why
 * ``operatorSignOff`` is pinned false in ``ReleaseManifestResponse`` rather than
 * computed from these records.
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
  knownLimitations: Knownlimitations;
  manifestMatches: Manifestmatches;
  outcome: Outcome;
}
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
 * So the field is pinned false, and the two counts beside it say different
 * things on purpose, by the coordinator's decision of 2026-10-01:
 *
 * * ``confirmedOperatorCount`` is **distinct operators whose decision a person
 *   is attested to have made**, as the write contract (``#282``, card 184)
 *   defines attestation. That implementation does not exist yet, so on this
 *   read surface the field is ``Literal[0]``. It is not "no acceptances"; it is
 *   "no decision here has been attested to a person";
 * * ``matchingAcceptedUserCount`` is the **raw recorded fact**: distinct user
 *   ids with an ``accepted`` row pinning this manifest's hash. A service
 *   principal can be one of them, which is precisely why it is a different
 *   field with a different name. The first version of this model called this
 *   count ``confirmedOperatorCount``, which read as though a person had been
 *   confirmed.
 *
 * ``requiredDistinctOperatorCount`` is the quorum, so a reader sees "0 of 2"
 * and can tell it apart from "1 of 2".
 */
export interface ReleaseManifestResponse {
  acceptanceCount: Acceptancecount;
  componentCount: Componentcount;
  components: Components;
  confirmedOperatorCount: Confirmedoperatorcount;
  createdAt: Createdat;
  manifestSha256: Manifestsha256;
  matchingAcceptedUserCount: Matchingacceptedusercount;
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
