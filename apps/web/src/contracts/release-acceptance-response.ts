/* Generated from contracts/release-acceptance-response.schema.json. Do not edit by hand. */

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
