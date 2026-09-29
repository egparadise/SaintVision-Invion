/* Generated from contracts/adapter-conformance-not-observed-response.schema.json. Do not edit by hand. */

export type Adapter = string;
export type Capabilitygated = boolean;
export type Name = string;
export type Checks = ConformanceCheckDescriptor[];
export type Contractversion = string;
export type Reason = string;
export type Recordedat = null;
export type Scope = 'control-plane-host';
export type Status = 'NOT_OBSERVED';

/**
 * The single-adapter route when the adapter is known but has no record.
 *
 * 200, not 404: "no such adapter" and "no measurement of this adapter" are
 * different facts, and folding the second into the first makes it read as
 * the first (§4-3).
 */
export interface AdapterConformanceNotObservedResponse {
  adapter: Adapter;
  checks: Checks;
  contractVersion: Contractversion;
  reason: Reason;
  recordedAt: Recordedat;
  scope: Scope;
  status: Status;
}
/**
 * One check the conformance contract defines, named and gated.
 *
 * A descriptor, not a result: there is no ``passed`` here because nothing has
 * been observed. Read from ``adapters.conformance.CHECKLIST``, which is the
 * single source for the list.
 */
export interface ConformanceCheckDescriptor {
  capabilityGated: Capabilitygated;
  name: Name;
}
