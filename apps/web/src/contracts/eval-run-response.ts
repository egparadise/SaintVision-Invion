/* Generated from contracts/eval-run-response.schema.json. Do not edit by hand. */

export type Endedat = string | null;
export type Evalrunid = string;
export type Passedcases = number;
export type Passedgate = boolean;
export type Startedat = string;
export type Status = 'running' | 'completed' | 'aborted';
export type Suiteid = string;
export type Totalcases = number;
export type Violations = number;

/**
 * The finished run, by identity and by count.
 *
 * No case content and no model output: ``eval_results.observed`` is a redacted
 * summary and this response does not carry even that. What a caller needs from
 * starting a run is which run it was and whether it passed.
 *
 * ``passedGate`` is its own field rather than something a reader derives from
 * the counts, because the row's own rule is stricter than "passed == total": a
 * run with any forbidden-behaviour violation is not a pass whatever the score
 * says.
 */
export interface EvalRunResponse {
  componentVersions: Componentversions;
  endedAt?: Endedat;
  evalRunId: Evalrunid;
  passedCases: Passedcases;
  passedGate: Passedgate;
  startedAt: Startedat;
  status: Status;
  suiteId: Suiteid;
  totalCases: Totalcases;
  violations: Violations;
}
export interface Componentversions {
  [k: string]: string;
}
