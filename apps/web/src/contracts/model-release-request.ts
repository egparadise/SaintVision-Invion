/* Generated from contracts/model-release-request.schema.json. Do not edit by hand. */

export type Classification = string;
export type Licensepolicy = string;

/**
 * An importer's claim about what it is releasing (VF-CL-03).
 *
 * The two fields and their constraints are copied from the kernel's
 * ``ModelManifest``, because the point of the request is to be compared
 * against that immutable declaration for exact equality. ``extra="forbid"``
 * is load-bearing here rather than conventional: a proposal carrying a field
 * the declaration does not have is itself a mismatch.
 */
export interface ModelReleaseRequest {
  classification: Classification;
  licensePolicy: Licensepolicy;
}
