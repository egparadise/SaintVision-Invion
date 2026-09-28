/* Generated from contracts/artifact-pin-verification-response.schema.json. Do not edit by hand. */

export type Artifactid = string;
export type Pinnedchecksumsha256 = string;
export type Recordid = string;
export type Runid = string;
export type Verified = boolean;

/**
 * Whether a pinned artifact still matches the digest sealed into the record.
 *
 * ``verified: false`` is a reported fact, not an error: the record stays the
 * account of what was true at sealing, and a changed object is an integrity
 * finding for the caller.
 */
export interface ArtifactPinVerificationResponse {
  artifactId: Artifactid;
  pinnedChecksumSha256: Pinnedchecksumsha256;
  recordId: Recordid;
  runId: Runid;
  verified: Verified;
}
