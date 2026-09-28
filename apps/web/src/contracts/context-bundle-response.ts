/* Generated from contracts/context-bundle-response.schema.json. Do not edit by hand. */

export type Builtat = string;
export type Bundlehash = string;
export type Bundleid = string;
export type Hashverified = boolean;
export type Itemcount = number;
export type Bytesize = number;
export type Confidence = number | null;
export type Contenthash = string;
export type Itemid = string;
export type Itemversion = number;
export type Kind = string;
export type Ordinal = number;
export type Redacted = boolean;
export type Items = ContextBundleItemSummary[];
export type Retrievalstrategy = string;
export type Runid = string;
export type Sealed = boolean;
export type Tokenestimate = number | null;
export type Totalbytes = number;

/**
 * A run's context bundle as metadata (G-04 R3).
 *
 * ``hashVerified`` is ``verify_bundle``'s answer, reported as a fact: false
 * means the stored content no longer reproduces the bundle hash. ``sealed``
 * says whether this is the bundle the run's sealed record pins (true) or the
 * run's most recently built bundle (false). ``itemCount``/``totalBytes`` are
 * the bundle's own columns; ``items`` is the ordered item list. No content,
 * no person, no free text.
 */
export interface ContextBundleResponse {
  builtAt: Builtat;
  bundleHash: Bundlehash;
  bundleId: Bundleid;
  componentVersions: Componentversions;
  hashVerified: Hashverified;
  itemCount: Itemcount;
  items: Items;
  retrievalStrategy: Retrievalstrategy;
  runId: Runid;
  sealed: Sealed;
  tokenEstimate?: Tokenestimate;
  totalBytes: Totalbytes;
}
export interface Componentversions {
  [k: string]: string;
}
/**
 * One bundle item without its content: what was read, in what version,
 * and the digest and byte length of the text -- never the text itself and
 * not the caller-written source URI.
 */
export interface ContextBundleItemSummary {
  byteSize: Bytesize;
  confidence?: Confidence;
  contentHash: Contenthash;
  itemId: Itemid;
  itemVersion: Itemversion;
  kind: Kind;
  ordinal: Ordinal;
  redacted: Redacted;
}
