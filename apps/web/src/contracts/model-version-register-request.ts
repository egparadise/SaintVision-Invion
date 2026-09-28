/* Generated from contracts/model-version-register-request.schema.json. Do not edit by hand. */

export type Bytesize = number;
export type Contentsha256 = string;
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
 * ``producedByRunId`` and ``lineage`` are deliberately absent -- see the
 * module docstring of ``api/v1/model_versions.py`` for why neither can be
 * bound to the path's project on this branch.
 */
export interface ModelVersionRegisterRequest {
  byteSize?: Bytesize;
  contentSha256: Contentsha256;
  version: Version;
}
