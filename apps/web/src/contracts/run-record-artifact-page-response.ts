/* Generated from contracts/run-record-artifact-page-response.schema.json. Do not edit by hand. */

export type Count = number;
export type Artifactid = string;
export type Bytesize = number;
export type Checksumsha256 = string;
export type Objectversion = string | null;
export type Role = string;
export type Uri = string;
/**
 * @maxItems 200
 */
export type Items = RunRecordArtifactPin[];
export type Nextcursor = string | null;
export type Recordid = string;
export type Role1 = string | null;
export type Runid = string;

/**
 * One bounded page of the artifacts pinned into a sealed record.
 *
 * A record pins the run's whole artifact set, which has no bound of its own,
 * so the list is paged: at most ``limit`` (default 50, maximum 200) items in
 * stable ``artifactId`` order. ``count`` is the number of items in *this
 * page*, never the record's total. ``nextCursor`` is the last item's
 * ``artifactId`` when more follow, and null on the last page. ``role`` echoes
 * the filter, which holds across pages.
 */
export interface RunRecordArtifactPageResponse {
  count: Count;
  items: Items;
  nextCursor?: Nextcursor;
  recordId: Recordid;
  role?: Role1;
  runId: Runid;
}
/**
 * One artifact as the record pinned it: reference, digest and size, no content.
 */
export interface RunRecordArtifactPin {
  artifactId: Artifactid;
  byteSize: Bytesize;
  checksumSha256: Checksumsha256;
  objectVersion?: Objectversion;
  role: Role;
  uri: Uri;
}
