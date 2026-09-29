/* Generated from contracts/model-lineage-trace-response.schema.json. Do not edit by hand. */

export type Contentsha256 = string;
/**
 * @maxItems 16
 */
export type Countonlykinds =
  | []
  | [string]
  | [string, string]
  | [string, string, string]
  | [string, string, string, string]
  | [string, string, string, string, string]
  | [string, string, string, string, string, string]
  | [string, string, string, string, string, string, string]
  | [string, string, string, string, string, string, string, string]
  | [string, string, string, string, string, string, string, string, string]
  | [string, string, string, string, string, string, string, string, string, string]
  | [string, string, string, string, string, string, string, string, string, string, string]
  | [string, string, string, string, string, string, string, string, string, string, string, string]
  | [string, string, string, string, string, string, string, string, string, string, string, string, string]
  | [string, string, string, string, string, string, string, string, string, string, string, string, string, string]
  | [
      string,
      string,
      string,
      string,
      string,
      string,
      string,
      string,
      string,
      string,
      string,
      string,
      string,
      string,
      string
    ]
  | [
      string,
      string,
      string,
      string,
      string,
      string,
      string,
      string,
      string,
      string,
      string,
      string,
      string,
      string,
      string,
      string
    ];
export type Contentsha2561 = string;
export type Datasetversionid = string;
export type Uri = string;
export type Version = string;
/**
 * @maxItems 200
 */
export type Datasets = LineageDatasetVersion[];
export type Approvalid = string | null;
export type Deployedat = string;
export type Deployeddigest = string;
export type Deploymentid = string;
export type Environment = string;
export type Imageid = string | null;
export type Status = string;
export type Supersededat = string | null;
/**
 * @maxItems 200
 */
export type Deployments = LineageDeployment[];
/**
 * @maxItems 16
 */
export type Detailedkinds =
  | []
  | [string]
  | [string, string]
  | [string, string, string]
  | [string, string, string, string]
  | [string, string, string, string, string]
  | [string, string, string, string, string, string]
  | [string, string, string, string, string, string, string]
  | [string, string, string, string, string, string, string, string]
  | [string, string, string, string, string, string, string, string, string]
  | [string, string, string, string, string, string, string, string, string, string]
  | [string, string, string, string, string, string, string, string, string, string, string]
  | [string, string, string, string, string, string, string, string, string, string, string, string]
  | [string, string, string, string, string, string, string, string, string, string, string, string, string]
  | [string, string, string, string, string, string, string, string, string, string, string, string, string, string]
  | [
      string,
      string,
      string,
      string,
      string,
      string,
      string,
      string,
      string,
      string,
      string,
      string,
      string,
      string,
      string
    ]
  | [
      string,
      string,
      string,
      string,
      string,
      string,
      string,
      string,
      string,
      string,
      string,
      string,
      string,
      string,
      string,
      string
    ];
export type Fullytraceable = boolean;
/**
 * @maxItems 16
 */
export type Missing =
  | []
  | [string]
  | [string, string]
  | [string, string, string]
  | [string, string, string, string]
  | [string, string, string, string, string]
  | [string, string, string, string, string, string]
  | [string, string, string, string, string, string, string]
  | [string, string, string, string, string, string, string, string]
  | [string, string, string, string, string, string, string, string, string]
  | [string, string, string, string, string, string, string, string, string, string]
  | [string, string, string, string, string, string, string, string, string, string, string]
  | [string, string, string, string, string, string, string, string, string, string, string, string]
  | [string, string, string, string, string, string, string, string, string, string, string, string, string]
  | [string, string, string, string, string, string, string, string, string, string, string, string, string, string]
  | [
      string,
      string,
      string,
      string,
      string,
      string,
      string,
      string,
      string,
      string,
      string,
      string,
      string,
      string,
      string
    ]
  | [
      string,
      string,
      string,
      string,
      string,
      string,
      string,
      string,
      string,
      string,
      string,
      string,
      string,
      string,
      string,
      string
    ];
export type Modelversionid = string;
export type Producedbyrunid = string | null;
export type Stage = string;
export type Traceabilitylimitedbyscope = boolean;
/**
 * @maxItems 16
 */
export type Unresolved =
  | []
  | [LineageUnresolved]
  | [LineageUnresolved, LineageUnresolved]
  | [LineageUnresolved, LineageUnresolved, LineageUnresolved]
  | [LineageUnresolved, LineageUnresolved, LineageUnresolved, LineageUnresolved]
  | [LineageUnresolved, LineageUnresolved, LineageUnresolved, LineageUnresolved, LineageUnresolved]
  | [LineageUnresolved, LineageUnresolved, LineageUnresolved, LineageUnresolved, LineageUnresolved, LineageUnresolved]
  | [
      LineageUnresolved,
      LineageUnresolved,
      LineageUnresolved,
      LineageUnresolved,
      LineageUnresolved,
      LineageUnresolved,
      LineageUnresolved
    ]
  | [
      LineageUnresolved,
      LineageUnresolved,
      LineageUnresolved,
      LineageUnresolved,
      LineageUnresolved,
      LineageUnresolved,
      LineageUnresolved,
      LineageUnresolved
    ]
  | [
      LineageUnresolved,
      LineageUnresolved,
      LineageUnresolved,
      LineageUnresolved,
      LineageUnresolved,
      LineageUnresolved,
      LineageUnresolved,
      LineageUnresolved,
      LineageUnresolved
    ]
  | [
      LineageUnresolved,
      LineageUnresolved,
      LineageUnresolved,
      LineageUnresolved,
      LineageUnresolved,
      LineageUnresolved,
      LineageUnresolved,
      LineageUnresolved,
      LineageUnresolved,
      LineageUnresolved
    ]
  | [
      LineageUnresolved,
      LineageUnresolved,
      LineageUnresolved,
      LineageUnresolved,
      LineageUnresolved,
      LineageUnresolved,
      LineageUnresolved,
      LineageUnresolved,
      LineageUnresolved,
      LineageUnresolved,
      LineageUnresolved
    ]
  | [
      LineageUnresolved,
      LineageUnresolved,
      LineageUnresolved,
      LineageUnresolved,
      LineageUnresolved,
      LineageUnresolved,
      LineageUnresolved,
      LineageUnresolved,
      LineageUnresolved,
      LineageUnresolved,
      LineageUnresolved,
      LineageUnresolved
    ]
  | [
      LineageUnresolved,
      LineageUnresolved,
      LineageUnresolved,
      LineageUnresolved,
      LineageUnresolved,
      LineageUnresolved,
      LineageUnresolved,
      LineageUnresolved,
      LineageUnresolved,
      LineageUnresolved,
      LineageUnresolved,
      LineageUnresolved,
      LineageUnresolved
    ]
  | [
      LineageUnresolved,
      LineageUnresolved,
      LineageUnresolved,
      LineageUnresolved,
      LineageUnresolved,
      LineageUnresolved,
      LineageUnresolved,
      LineageUnresolved,
      LineageUnresolved,
      LineageUnresolved,
      LineageUnresolved,
      LineageUnresolved,
      LineageUnresolved,
      LineageUnresolved
    ]
  | [
      LineageUnresolved,
      LineageUnresolved,
      LineageUnresolved,
      LineageUnresolved,
      LineageUnresolved,
      LineageUnresolved,
      LineageUnresolved,
      LineageUnresolved,
      LineageUnresolved,
      LineageUnresolved,
      LineageUnresolved,
      LineageUnresolved,
      LineageUnresolved,
      LineageUnresolved,
      LineageUnresolved
    ]
  | [
      LineageUnresolved,
      LineageUnresolved,
      LineageUnresolved,
      LineageUnresolved,
      LineageUnresolved,
      LineageUnresolved,
      LineageUnresolved,
      LineageUnresolved,
      LineageUnresolved,
      LineageUnresolved,
      LineageUnresolved,
      LineageUnresolved,
      LineageUnresolved,
      LineageUnresolved,
      LineageUnresolved,
      LineageUnresolved
    ];
export type Count = number;
export type Kind = string;
export type Version1 = string;

/**
 * AC-10's traceback, reduced to what a project member may be shown.
 *
 * ``commits``, ``images``, ``evaluations`` and ``approvals`` are absent rather
 * than empty. An empty array would read as "nothing was recorded", which is a
 * different and much more alarming statement than "this route cannot prove who
 * owns those rows"; the second is what ``unresolved`` and ``countOnlyKinds``
 * say.
 *
 * ``deployments: []`` *is* an empty array, because it means something
 * complete: nothing has been deployed. That difference is the reason the two
 * are shaped differently.
 */
export interface ModelLineageTraceResponse {
  contentSha256: Contentsha256;
  countOnlyKinds: Countonlykinds;
  datasets: Datasets;
  deployments: Deployments;
  detailedKinds: Detailedkinds;
  fullyTraceable: Fullytraceable;
  missing: Missing;
  modelVersionId: Modelversionid;
  producedByRunId?: Producedbyrunid;
  stage: Stage;
  traceabilityLimitedByScope: Traceabilitylimitedbyscope;
  truncated?: Truncated;
  unresolved: Unresolved;
  version: Version1;
}
export interface LineageDatasetVersion {
  contentSha256: Contentsha2561;
  datasetVersionId: Datasetversionid;
  uri: Uri;
  version: Version;
}
/**
 * A deployment of the traced version.
 *
 * ``deployedByUserId`` and ``notes`` are on the row and are deliberately not
 * here: reading lineage does not need a person's identifier or free text.
 */
export interface LineageDeployment {
  approvalId?: Approvalid;
  deployedAt: Deployedat;
  deployedDigest: Deployeddigest;
  deploymentId: Deploymentid;
  environment: Environment;
  imageId?: Imageid;
  status: Status;
  supersededAt?: Supersededat;
}
export interface Truncated {
  [k: string]: number;
}
/**
 * How many subjects of one kind this response does not describe.
 *
 * A count and a kind, and nothing else. An identifier would leak another
 * project's row, and a reason would tell the caller whether a hidden
 * identifier exists -- which is the same disclosure by a longer route.
 */
export interface LineageUnresolved {
  count: Count;
  kind: Kind;
}
