/* Generated from contracts/execution-readiness-check-response.schema.json. Do not edit by hand. */

export type Check = string;
export type Detail = string;
export type Maxcontentbytes = number | null;
export type Maxsnapshotbytes = number | null;
export type Remedy = string | null;
export type Resolvedby = string | null;
export type Runid = string | null;
export type Satisfied = boolean;
export type Snapshotbytes = number | null;

export interface ExecutionReadinessCheckResponse {
  check: Check;
  detail: Detail;
  maxContentBytes?: Maxcontentbytes;
  maxSnapshotBytes?: Maxsnapshotbytes;
  remedy?: Remedy;
  resolvedBy?: Resolvedby;
  runId?: Runid;
  satisfied: Satisfied;
  snapshotBytes?: Snapshotbytes;
}
