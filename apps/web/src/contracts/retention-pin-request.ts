/* Generated from contracts/retention-pin-request.schema.json. Do not edit by hand. */

export type Until = string;

/**
 * What a caller asks of W4: keep this version at least until ``until``.
 *
 * One field, because ``pin_retention`` takes one: the service decides what the
 * request means (extend, never shorten). The instant must carry an offset --
 * a naive time would be compared with the stored aware value by whatever the
 * driver assumes, and "retained until when?" is not a question to answer with
 * an assumption.
 */
export interface RetentionPinRequest {
  until: Until;
}
