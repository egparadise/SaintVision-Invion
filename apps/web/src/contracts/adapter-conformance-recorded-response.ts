/* Generated from contracts/adapter-conformance-recorded-response.schema.json. Do not edit by hand. */

export type Adapter = string;
export type Contractversion = string;
export type Failed = number;
export type Name = string;
export type Passed = boolean;
export type Skipped = boolean;
export type Outcomes = ConformanceCheckOutcome[];
export type Passed1 = number;
export type Provenance = 'in-server';
export type Recordedat = string;
export type Scope = 'control-plane-host';
export type Skipped1 = number;
export type Status = 'RECORDED';
export type Subject = 'fixture-adapter';
export type Suitecontractversion = string;
export type Total = number;

/**
 * The single-adapter route's record. Its own class rather than the list
 * item, so one side's needs cannot drag the other's contract; the field
 * names and types are the item's exactly (§4-1).
 */
export interface AdapterConformanceRecordedResponse {
  adapter: Adapter;
  contractVersion: Contractversion;
  failed: Failed;
  outcomes: Outcomes;
  passed: Passed1;
  provenance: Provenance;
  recordedAt: Recordedat;
  scope: Scope;
  skipped: Skipped1;
  status: Status;
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
  name: Name;
  passed: Passed;
  skipped: Skipped;
}
