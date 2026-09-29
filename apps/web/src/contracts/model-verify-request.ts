/* Generated from contracts/model-verify-request.schema.json. Do not edit by hand. */

export type Measurementid = string;

/**
 * What a caller asks of W3: apply this kernel-recorded measurement.
 *
 * One field, and ``extra="forbid"`` is load-bearing: a digest, a size or a
 * URI in the body would be a value the caller supplied, and verification
 * is exactly the thing a caller's value must not be able to establish
 * (design #209 v1.1 §6).
 */
export interface ModelVerifyRequest {
  measurementId: Measurementid;
}
