/* Generated from contracts/retention-pin-response.schema.json. Do not edit by hand. */

export type Extended = boolean;
export type Modelid = string;
export type Modelversionid = string;
export type Retentionpinneduntil = string;
export type Stage = 'draft' | 'candidate' | 'released' | 'retired';
export type Version = string;

/**
 * The version's retention after the request was judged.
 *
 * ``retentionPinnedUntil`` is the committed value, which is the requested one
 * only when it extended the pin; ``extended`` says which, so a no-op is
 * visible to the caller instead of looking like success by coincidence.
 * ``stage`` is whatever the row is in -- a released version can still be
 * extended (design §5-3) -- and is the closed set the column allows.
 */
export interface RetentionPinResponse {
  extended: Extended;
  modelId: Modelid;
  modelVersionId: Modelversionid;
  retentionPinnedUntil: Retentionpinneduntil;
  stage: Stage;
  version: Version;
}
