/* Generated from contracts/conformance-status-recorded-response.schema.json. Do not edit by hand. */

export type Adapters = string[];
export type Capabilitygated = boolean;
export type Name = string;
export type Checks = ConformanceCheckDescriptor[];
export type Contractversion = string;
export type Latestrecordedat = string;
/**
 * @minItems 1
 */
export type Records = [ConformanceRecordItem, ...ConformanceRecordItem[]];
export type Adapter = string;
export type Contractversion1 = string;
export type Failed = number;
export type Name1 = string;
export type Passed = boolean;
export type Skipped = boolean;
export type Outcomes = ConformanceCheckOutcome[];
export type Passed1 = number;
export type Provenance = 'in-server';
export type Recordedat = string;
export type Skipped1 = number;
export type Subject = 'fixture-adapter';
export type Suitecontractversion = string;
export type Total = number;
export type Scope = 'control-plane-host';
export type Status = 'RECORDED';

/**
 * The list route when at least one record exists.
 *
 * ``records`` follows the order of ``adapters`` and holds only adapters that
 * have a record: absence from ``records`` is the absence of a measurement,
 * so there is no per-adapter NOT_OBSERVED entry. ``latestRecordedAt`` is the
 * maximum of the items' ``recordedAt`` -- the aggregate freshness -- and the
 * key is deliberately not ``recordedAt``, which in the NOT_OBSERVED branch is
 * always null (§4-1, R2). No ``reason``: nothing is being explained.
 */
export interface ConformanceStatusRecordedResponse {
  adapters: Adapters;
  checks: Checks;
  contractVersion: Contractversion;
  latestRecordedAt: Latestrecordedat;
  records: Records;
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
/**
 * One stored record inside ``records[]``. Nested, not a contract file.
 */
export interface ConformanceRecordItem {
  adapter: Adapter;
  contractVersion: Contractversion1;
  failed: Failed;
  outcomes: Outcomes;
  passed: Passed1;
  provenance: Provenance;
  recordedAt: Recordedat;
  skipped: Skipped1;
  subject: Subject;
  suiteContractVersion: Suitecontractversion;
  total: Total;
}
/**
 * One check's result as stored: name, passed, skipped. No ``detail``: the
 * suite's detail is stringified exceptions and host process output, and this
 * row is readable by every project's members (§2-5).
 */
export interface ConformanceCheckOutcome {
  name: Name1;
  passed: Passed;
  skipped: Skipped;
}
