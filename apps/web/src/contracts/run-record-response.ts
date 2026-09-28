/* Generated from contracts/run-record-response.schema.json. Do not edit by hand. */

export type Attemptcount = number;
export type Bundlehash = string | null;
export type Bundleid = string | null;
export type Evidenceid = string | null;
export type Finalstate = string;
export type Recordid = string;
export type Runid = string;
export type Sealedat = string;
export type Terminationreason = string;
export type Workloadspecsha256 = string;

/**
 * The sealed record of a run, reduced to identifiers, digests and counts.
 *
 * No person and no free text: who requested the run and what it produced are
 * other routes' business. ``bundleId``/``bundleHash`` are null when the run
 * was sealed without a context bundle; that is a fact about the record, not a
 * gap in this response.
 */
export interface RunRecordResponse {
  attemptCount: Attemptcount;
  bundleHash?: Bundlehash;
  bundleId?: Bundleid;
  componentVersions: Componentversions;
  evidenceId?: Evidenceid;
  finalState: Finalstate;
  recordId: Recordid;
  runId: Runid;
  sealedAt: Sealedat;
  terminationReason: Terminationreason;
  workloadSpecSha256: Workloadspecsha256;
}
export interface Componentversions {
  [k: string]: string;
}
