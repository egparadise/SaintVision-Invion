/* Generated from contracts/conformance-status-response.schema.json. Do not edit by hand. */

export type Adapters = string[];
export type Capabilitygated = boolean;
export type Name = string;
export type Checks = ConformanceCheckDescriptor[];
export type Contractversion = string;
export type Reason = string;
export type Recordedat = null;
export type Scope = 'control-plane-host';
export type Status = 'NOT_OBSERVED';

/**
 * What this platform can honestly say about adapter conformance (G-03).
 *
 * Phase one says **NOT_OBSERVED** and nothing more, because nothing is stored:
 * ``run_conformance`` has no product caller and no table. The consequences are
 * in the field list rather than in a comment --
 *
 * * ``status`` is ``Literal["NOT_OBSERVED"]``, one value. A widened literal
 *   would advertise ``RECORDED`` in the generated schema before any code can
 *   produce it; phase two brings that branch in with the counts that make it
 *   mean something.
 * * there is **no** ``conformant`` boolean. A boolean has no third value, so
 *   "not measured" would have to be spelled ``false``, which reads as "it was
 *   run and it failed".
 * * there are **no counts**. ``passed: 0`` is not the absence of a
 *   measurement; it is a measurement of zero.
 * * ``recordedAt`` is typed ``None``: the only honest value is null, so the
 *   contract says so rather than trusting the route.
 *
 * ``scope`` is the same word ``GET /v1/adapters`` uses. The project in the path
 * is who may read this, not who owns it: conformance is a property of the
 * control-plane host, not of a tenant's data.
 */
export interface ConformanceStatusResponse {
  adapters: Adapters;
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
