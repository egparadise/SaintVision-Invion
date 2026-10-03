/* Generated from contracts/model-version-register-request.schema.json. Do not edit by hand. */

export type Bytesize = number;
export type Contentsha256 = string;
export type Lineage = ProvableLineageEdge[] | null;
export type Kind = 'approval' | 'dataset_version' | 'eval_run';
export type Relation = string;
export type Subjectid = string;
export type Producedbyrunid = string | null;
export type Version = string;

/**
 * What an importer must state to register one model build (G-04 W2).
 *
 * The fields are exactly ``register_model_version``'s own required arguments,
 * and nothing more: the service is the judge of what a registration means, so
 * a field here that it does not take would be this route inventing state.
 *
 * ``contentSha256`` carries the service's rule as a pattern rather than
 * trusting it: the service raises ``VAL-SCHEMA`` for a non-lowercase digest
 * and the column has ``checksum_is_lowercase``, so a caller who sends
 * ``ABC...`` gets a request error at the boundary instead of a service error
 * translated later. Both defences stay.
 *
 * ``uri`` is **not** here (Codex #191 F2). A caller-supplied URI was accepted
 * and stored verbatim, so ``https://user:secret@host``, ``javascript:...`` and
 * another model version's ``inv://`` address all persisted -- and the kernel
 * manifest's join key assumes the URI's version *is* the row's version. The
 * canonical address is fully determined by the model's name and the version, so
 * the server derives it instead of validating a string that has no reason to
 * vary.
 *
 * ``producedByRunId`` and ``lineage`` are here **since card 261**, and each one
 * waited for a different thing to exist (card 257 §4-1·§4-2):
 *
 * * ``producedByRunId`` needed a way to prove the run belongs to the path's
 *   project. ``project_scope.run_in_project`` does that through the workload,
 *   so an unbound value can no longer attach this version to another project's
 *   run, and ``0064`` adds the composite key underneath.
 * * ``lineage`` needed subject validation. ``record_lineage`` now refuses a
 *   subject that is not in this tenant, and the kinds accepted **here** are
 *   only the three whose project can be proven -- ``code_commit`` and
 *   ``container_image`` carry no project anywhere in the schema, so a caller
 *   cannot assert them (the service still writes them for server-derived
 *   paths; see the design's §4-2-1).
 */
export interface ModelVersionRegisterRequest {
  byteSize?: Bytesize;
  contentSha256: Contentsha256;
  lineage?: Lineage;
  producedByRunId?: Producedbyrunid;
  version: Version;
}
/**
 * One asserted lineage edge, in a kind whose project can be proven.
 */
export interface ProvableLineageEdge {
  kind: Kind;
  relation?: Relation;
  subjectId: Subjectid;
}
