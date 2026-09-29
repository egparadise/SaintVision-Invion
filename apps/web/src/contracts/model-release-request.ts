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
 *
 * The request carries a required ``Idempotency-Key`` header (card 113). The
 * same key with this same body and path replays the stored
 * ``ModelReleaseResponse``; the same key with a different body or path is
 * ``GRAPH-0002``/409; a version that is already released is ``GRAPH-0002``/409
 * under any other key.
 */
export interface ModelReleaseRequest {
  classification: Classification;
  licensePolicy: Licensepolicy;
}
