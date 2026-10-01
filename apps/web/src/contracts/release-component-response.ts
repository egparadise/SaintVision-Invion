/* Generated from contracts/release-component-response.schema.json. Do not edit by hand. */

export type Digest = string;
export type Kind = string;
export type Name = string;

/**
 * One pinned component of a release.
 *
 * Every entry carries a digest because the manifest hash covers the list: a
 * name is not an identity, so "we shipped R4" has to be checkable rather than
 * asserted (``operations_pilot.ReleaseManifest``).
 */
export interface ReleaseComponentResponse {
  digest: Digest;
  kind: Kind;
  name: Name;
}
