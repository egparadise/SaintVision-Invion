/* Generated from contracts/model-version-response.schema.json. Do not edit by hand. */

export type Bytesize = number;
export type Contentsha256 = string;
export type Createdat = string;
export type Modelid = string;
export type Modelversionid = string;
export type Stage = 'draft';
export type Uri = string;
export type Version = string;

/**
 * The registered build, echoed back by identity.
 *
 * ``stage`` is a literal: registration creates a draft and nothing else, so a
 * change that returns a released version under this type breaks the contract
 * rather than widening it quietly. There is no person and no free text here --
 * the same rule ``LineageDeployment`` states.
 *
 * Python field names avoid the ``model_`` prefix because Pydantic reserves
 * that namespace; the wire names are the aliases.
 */
export interface ModelVersionResponse {
  byteSize: Bytesize;
  contentSha256: Contentsha256;
  createdAt: Createdat;
  modelId: Modelid;
  modelVersionId: Modelversionid;
  stage: Stage;
  uri: Uri;
  version: Version;
}
