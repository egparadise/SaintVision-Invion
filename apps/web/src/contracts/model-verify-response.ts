/* Generated from contracts/model-verify-response.schema.json. Do not edit by hand. */

export type Contentsha256 = string;
export type Modelid = string;
export type Modelversionid = string;
export type Newlyverified = boolean;
export type Stage = 'draft' | 'candidate' | 'released' | 'retired';
export type Verifiedat = string;
export type Verifiedmeasurementid = string;
export type Version = string;

/**
 * The version after the measurement was bound (or found already bound).
 *
 * ``newlyVerified`` is false when the row was already verified by this very
 * measurement, so a repeat with a fresh idempotency key is visible as the
 * no-op it was.
 */
export interface ModelVerifyResponse {
  contentSha256: Contentsha256;
  modelId: Modelid;
  modelVersionId: Modelversionid;
  newlyVerified: Newlyverified;
  stage: Stage;
  verifiedAt: Verifiedat;
  verifiedMeasurementId: Verifiedmeasurementid;
  version: Version;
}
